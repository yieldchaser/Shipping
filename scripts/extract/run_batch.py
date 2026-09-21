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


def load_done(checkpoint):
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
            done[rec["path"]] = rec
    return done


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
    rec.update({"path": doc_path, "status": "ok", "secs": secs})
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
    a = ap.parse_args()

    rows = load_inventory()
    docs = rows if a.all else stratified(rows, a.limit)
    done = load_done(a.checkpoint) if a.resume else {}
    todo = [r for r in docs if r["path"] not in done]
    print(f"batch: {len(docs)} selected, {len(done)} already done, {len(todo)} to run "
          f"({a.workers} workers, {a.timeout}s/doc timeout)", flush=True)
    if not todo:
        print("nothing to do")
        return 0

    os.makedirs(os.path.dirname(a.checkpoint), exist_ok=True)
    ckpt = open(a.checkpoint, "a", encoding="utf-8")
    tally = collections.Counter(k if k == "ok" else "fail" for k in [])
    counts = collections.Counter()
    t_start = time.time()
    pages = tables = 0

    # simple bounded concurrency without a framework (RAM-capped box)
    from concurrent.futures import ThreadPoolExecutor
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
    ckpt.close()
    elapsed = time.time() - t_start
    print(f"\n=== {sum(counts.values())} docs in {elapsed / 60:.1f} min | {dict(counts)}")
    print(f"    {pages} pages, {tables} tables, {elapsed / max(1, sum(counts.values())):.1f}s/doc")
    failed = [k for k in counts if k != "ok"]
    if failed:
        print(f"    failure kinds: {failed}")
        print(f"    rerun the same command with --resume to retry the failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
