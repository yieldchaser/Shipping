"""Crash-safe batch driver for corpus extraction.

Why this exists (measured 2026-09-21): a plain sequential run over 303 docs
died at document 11 with NO traceback -- a native crash (access violation) in
the PDF stack killed Python outright. A 7,816-document unattended run cannot
behave that way. A 400-page textbook also showed no per-document timeout, so
one slow document can stall the whole batch indefinitely.

Design:
  * one subprocess per document -> a segfault kills only that document
  * hard per-document timeout -> a hung document is abandoned, not waited on
  * append-only JSONL checkpoint -> a crash or Ctrl-C resumes, never restarts
  * N workers -> bounded concurrency for the 8.3 GB RAM envelope

Usage:
  python scripts/extract/run_batch.py --limit 300 --workers 2 \
      --out data/extracted/dryrun --checkpoint data/extracted/batch_checkpoint.jsonl
  python scripts/extract/run_batch.py --resume          # continue where it stopped
"""
import argparse
import collections
import json
import os
import random
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER = os.path.join(REPO, "scripts", "extract", "batch_worker.py")


def load_inventory():
    inv = [json.loads(l) for l in
           open(os.path.join(REPO, "data", "extracted", "inventory.jsonl"), encoding="utf-8")]
    return [r for r in inv if not r.get("dup_of_content")]


def stratified(rows, n, seed=21):
    """Proportional sample across inventory roots; n=0 means all docs."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["root"]].append(r)
    if not n:
        return rows
    rng = random.Random(seed)
    total, out = len(rows), []
    for root, group in sorted(by.items()):
        k = max(1, round(n * len(group) / total))
        out += rng.sample(group, min(k, len(group)))
    return out


def load_done(checkpoint, retry_failed=False):
    """Load completed docs, keeping the LAST record per path.

    Fixed 2026-09-21: two concurrent batches wrote this file (152 rows for 91
    unique docs) after a launch appeared to have died but had not. Duplicates
    must not corrupt resume bookkeeping, so the last record wins.

    retry_failed=True drops records whose last status was not "ok" from the
    done-set so those documents are re-attempted. Default False keeps them,
    which means plain --resume SKIPS failures. Measured 2026-09-21: all 74
    non-ok checkpoint rows (71 not-a-pdf, 3 per-document timeouts) were in the
    done-set, so --resume retried none of them - while the run printed "rerun
    the same command with --resume to retry the failures" and the runbook said
    to raise --timeout and resume.
    """
    done = {}
    if os.path.exists(checkpoint):
        for line in open(checkpoint, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn write from a crash: ignore that line
            if "path" in rec:
                if retry_failed and rec.get("status") != "ok":
                    continue  # re-attempt: a recorded failure is not "done"
                done[rec["path"]] = rec
    return done


LOCK = os.path.join(REPO, "data", "extracted", ".batch.lock")


def acquire_lock():
    """Single-instance guard. Two concurrent batches double-process the corpus
    and contend for CPU on a RAM-capped box, which silently corrupts both the
    checkpoint and the throughput numbers."""
    if os.path.exists(LOCK):
        try:
            holder = int(open(LOCK).read().strip())
        except (ValueError, OSError):
            holder = None
        if holder:
            alive = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {holder} -ErrorAction SilentlyContinue) -ne $null"],
                capture_output=True, text=True).stdout.strip().lower()
            if alive == "true":
                return False, holder
        os.remove(LOCK)  # stale
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
    return True, os.getpid()


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def write_state(state_path, counts, done_total, todo_total, elapsed, pages, tables):
    """Progress state an external verifier or a successor agent can read."""
    ok = counts.get("ok", 0)
    rate = elapsed / max(1, ok)
    state = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "done": sum(counts.values()),
        "planned": todo_total,
        "status_counts": dict(counts),
        "ok": ok,
        "secs_per_doc": round(rate, 1),
        "elapsed_min": round(elapsed / 60, 1),
        "eta_min": round(rate * max(0, todo_total - sum(counts.values())) / 60, 1),
        "pages": pages, "tables": tables,
        "corpus_done_total": done_total,
        "pid": os.getpid(),
    }
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, state_path)


def run_one(doc_path, out_root, timeout):
    """Extract one document in its own process. Returns a result record."""
    t0 = time.time()
    try:
        p = subprocess.run(
            [sys.executable, WORKER, doc_path, out_root],
            capture_output=True, text=True, timeout=timeout, cwd=REPO)
    except subprocess.TimeoutExpired:
        return {"path": doc_path, "status": "timeout",
                "secs": round(time.time() - t0, 1)}
    secs = round(time.time() - t0, 1)
    if p.returncode != 0:
        return {"path": doc_path, "status": "CRASH",
                "exitcode": p.returncode, "secs": secs,
                "stderr": (p.stderr or "")[-300:]}
    try:
        rec = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"path": doc_path, "status": "noresult", "secs": secs,
                "stdout": (p.stdout or "")[-200:]}
    if rec.get("error"):
        return {"path": doc_path, "status": "error", "secs": secs,
                "error": rec["error"]}
    # honour a status the worker set explicitly (e.g. no-extractable-content)
    # instead of blanket-labelling everything "ok"
    worker_status = rec.pop("status", None) or "ok"
    rec.update({"path": doc_path, "status": worker_status, "secs": secs})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--all", action="store_true", help="process every unique doc")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=600, help="per-document seconds")
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted", "batch"))
    ap.add_argument("--checkpoint",
                    default=os.path.join(REPO, "data", "extracted", "batch_checkpoint.jsonl"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--state", default=os.path.join(REPO, "data", "extracted", "batch_state.json"))
    ap.add_argument("--no-lock", action="store_true", help="skip the single-instance guard")
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-attempt documents whose last recorded status was not ok "
                         "(plain --resume treats them as done and skips them). Each "
                         "retry appends another checkpoint row for that path.")
    a = ap.parse_args()

    if not a.no_lock:
        got, holder = acquire_lock()
        if not got:
            print(f"REFUSING TO START: another batch is running (pid {holder}). "
                  f"A second batch double-processes the corpus and corrupts the "
                  f"checkpoint. Remove {LOCK} only if that pid is dead.")
            return 1

    rows = load_inventory()
    # drop provenance-only documents from the work queue entirely: their data is
    # superseded by a richer feed already in the repo, so extracting them (or
    # queuing them for OCR) is wasted effort. See source_configs.PROVENANCE_ONLY.
    try:
        from source_configs import PROVENANCE_ONLY
    except ImportError:
        PROVENANCE_ONLY = {}
    if PROVENANCE_ONLY:
        import fnmatch
        before = len(rows)
        skipped = []

        def _prov_only(path):
            p = path.replace("\\", "/")
            for pat, why in PROVENANCE_ONLY.items():
                if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat + "/*") \
                        or pat.rstrip("*").rstrip("/") in p:
                    return why
            return None

        kept = []
        for r in rows:
            why = _prov_only(r["path"])
            if why:
                skipped.append(r["path"])
            else:
                kept.append(r)
        rows = kept
        if skipped:
            print(f"provenance-only: skipping {before - len(rows)} documents "
                  f"({len(PROVENANCE_ONLY)} rule(s)) - not extracted, not OCR-queued")
    docs = rows if a.all else stratified(rows, a.limit)
    done = load_done(a.checkpoint, a.retry_failed) if a.resume else {}
    done_failed = sum(1 for r in done.values() if r.get("status") != "ok")
    todo = [r for r in docs if r["path"] not in done]
    print(f"batch: {len(docs)} selected, {len(done)} already done, {len(todo)} to run "
          f"({a.workers} workers, {a.timeout}s/doc timeout)", flush=True)
    if not todo:
        print("nothing to do")
        release_lock()
        return 0

    os.makedirs(os.path.dirname(a.checkpoint), exist_ok=True)
    ckpt = open(a.checkpoint, "a", encoding="utf-8")
    counts = collections.Counter()
    t_start = time.time()
    pages = tables = 0

    # simple bounded concurrency without a framework (RAM-capped box)
    from concurrent.futures import ThreadPoolExecutor
    try:
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futs = {pool.submit(run_one, os.path.join(REPO, r["path"]), a.out, a.timeout):
                    r["path"] for r in todo}
            for i, fut in enumerate(futs, 1):
                res = fut.result()
                res["path"] = os.path.relpath(res["path"], REPO) if os.path.isabs(res["path"]) else res["path"]
                ckpt.write(json.dumps(res) + "\n")
                ckpt.flush()
                counts[res["status"]] += 1
                if res["status"] == "ok":
                    pages += res.get("pages", 0)
                    tables += res.get("tables", 0)
                flag = "" if res["status"] == "ok" else f"  <{res['status']}>"
                print(f"[{i}/{len(todo)}] {res['status']:7s} {res.get('secs', 0):6.1f}s "
                      f"{res.get('pages', '-')}pg {res.get('tables', '-')}tbl "
                      f"{os.path.basename(res['path'])[:44]}{flag}", flush=True)
                if i % 10 == 0:
                    write_state(a.state, counts, len(done) + sum(counts.values()),
                                len(todo), time.time() - t_start, pages, tables)
    finally:
        ckpt.close()
        release_lock()
    elapsed = time.time() - t_start
    print(f"\n=== {sum(counts.values())} docs in {elapsed / 60:.1f} min | {dict(counts)}")
    print(f"    {pages} pages, {tables} tables, {elapsed / max(1, sum(counts.values())):.1f}s/doc")
    failed = [k for k in counts if k != "ok"]
    if failed:
        print(f"    failure kinds: {failed}")
        # Corrected 2026-09-21: this line used to claim that rerunning with
        # --resume retries the failures. It does not - resume treats a recorded
        # failure as done and skips it. Print what actually happens instead.
        if a.resume and not a.retry_failed and done_failed:
            print(f"    {done_failed} document(s) already recorded as failed are in "
                  f"the done-set: --resume SKIPS them, it does not retry them.")
            print(f"    to re-attempt: same command plus --retry-failed (each retry "
                  f"appends another checkpoint row for that path).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
