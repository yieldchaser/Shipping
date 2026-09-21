"""Re-extract documents whose checkpoint status is CRASH.

Why this exists: between checkpoint rows 3,727-3,930 the extraction workers
failed instantly (0.2-0.4 s, exit code 1) with

    SyntaxError: source code string cannot contain null bytes

because scripts/extract/extract_all.py was transiently partially-written while
the workers were spawning, so `import extract_all` read a file that still had
null bytes in it. The file is correct now and the run recovered by itself, but
204 documents were recorded as CRASH and never produced artefacts.

This re-runs exactly those documents. It deliberately does NOT touch
corpus_checkpoint.jsonl - the live batch holds that file open for append, and
replacing it would silently lose completed rows. Output goes straight into the
corpus tree via batch_worker, the same pattern used to recover the 11
silent-empty documents.

Progress is appended to data/extracted/crash_recovery.jsonl so a timeout or a
crash of this script itself does not lose the work done so far.
"""
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKPOINT = os.path.join(BASE, "data", "extracted", "corpus_checkpoint.jsonl")
OUT_ROOT = os.path.join(BASE, "data", "extracted", "corpus")
PROGRESS = os.path.join(BASE, "data", "extracted", "crash_recovery.jsonl")
WORKER = os.path.join(BASE, "scripts", "extract", "batch_worker.py")


def crashed_paths():
    seen, paths = set(), []
    with open(CHECKPOINT, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") != "CRASH":
                continue
            p = rec.get("path")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


def already_done():
    done = set()
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["path"])
                except Exception:
                    continue
    return done


def main():
    paths = crashed_paths()
    done = already_done()
    todo = [p for p in paths if p not in done]
    print(f"crash recovery: {len(paths)} crashed, {len(done)} already recovered, {len(todo)} to run", flush=True)

    ok = fail = 0
    t0 = time.time()
    with open(PROGRESS, "a", encoding="utf-8", newline="\n") as out:
        for i, rel in enumerate(todo, 1):
            full = os.path.join(BASE, rel)
            started = time.time()
            try:
                r = subprocess.run(
                    [sys.executable, WORKER, full, "data/extracted/corpus"],
                    capture_output=True, text=True, timeout=900, cwd=BASE,
                )
            except subprocess.TimeoutExpired:
                elapsed = time.time() - started
                out.write(json.dumps({"path": rel, "status": "timeout", "secs": round(elapsed, 1)}) + "\n")
                out.flush()
                print(f"[{i}/{len(todo)}] TIMEOUT {elapsed:6.1f}s {os.path.basename(rel)[-46:]}", flush=True)
                fail += 1
                continue

            elapsed = time.time() - started
            if r.returncode != 0:
                status = "crash"
                detail = (r.stderr or "")[-200:]
            else:
                try:
                    rec = json.loads((r.stdout or "").strip().splitlines()[-1])
                    status = rec.get("status") or ("ok" if rec.get("blocks") is not None else "unknown")
                    detail = None
                except Exception:
                    status, detail = "unparsed", (r.stdout or "")[-160:]
            good = status in ("ok", "provenance-only", "no-extractable-content")
            ok += 1 if good else 0
            fail += 0 if good else 1
            out.write(json.dumps({"path": rel, "status": status, "secs": round(elapsed, 1)}) + "\n")
            out.flush()
            print(f"[{i}/{len(todo)}] {status:<22} {elapsed:6.1f}s {os.path.basename(rel)[-46:]}", flush=True)

    total = time.time() - t0
    print(f"\ncrash recovery done: {ok} recovered, {fail} still failing, {total/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
