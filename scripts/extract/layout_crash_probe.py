"""Isolate pymupdf-layout crashes: run predict in a subprocess, count failures.

A malformed-font PDF segfaults the layout ONNX model inside create_stext_page
(access violation, unrecoverable in-process). This probe measures how often that
happens across the corpus so the extractor can isolate layout safely.

Usage: python scripts/extract/layout_crash_probe.py --n 40
"""
import argparse
import collections
import json
import multiprocessing as mp
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def child(pdf_path, pno, q):
    """Run layout predict on one page; report outcome via queue."""
    try:
        import pymupdf
        from pymupdf.layout import DocumentLayoutAnalyzer
        m = DocumentLayoutAnalyzer.get_model()
        doc = pymupdf.open(pdf_path)
        regions = m.predict(doc[pno])
        q.put(("ok", len(regions or [])))
    except BaseException as exc:  # noqa: BLE001 - report anything
        q.put(("err", f"{type(exc).__name__}: {exc}"[:120]))


def probe(pdf_path, pno=0, timeout=120):
    q = mp.Queue()
    p = mp.Process(target=child, args=(pdf_path, pno, q))
    t0 = time.time()
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(5)
        return {"status": "timeout", "secs": round(time.time() - t0, 1)}
    if p.exitcode != 0:
        return {"status": "CRASH", "exitcode": p.exitcode,
                "secs": round(time.time() - t0, 1)}
    try:
        kind, val = q.get_nowait()
        return {"status": kind, "regions": val if kind == "ok" else None,
                "err": val if kind != "ok" else None,
                "secs": round(time.time() - t0, 1)}
    except Exception:
        return {"status": "noresult", "secs": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(REPO, "scripts", "extract",
                                                  "layout_crash_probe.json"))
    a = ap.parse_args()
    inv = [json.loads(l) for l in
           open(os.path.join(REPO, "data", "extracted", "inventory.jsonl"), encoding="utf-8")]
    uniq = [r for r in inv if not r.get("dup_of_content")]
    # stratify by root
    by = collections.defaultdict(list)
    for r in uniq:
        by[r["root"]].append(r)
    rng = random.Random(a.seed)
    total = len(uniq)
    sample = []
    for root, rows in sorted(by.items()):
        k = max(1, round(a.n * len(rows) / total))
        sample += rng.sample(rows, min(k, len(rows)))
    results = []
    tally = collections.Counter()
    for r in sample:
        p = os.path.join(REPO, r["path"])
        res = probe(p)
        res["path"] = r["path"]
        res["root"] = r["root"]
        tally[res["status"]] += 1
        results.append(res)
        print(f"{res['status']:8s} {res.get('secs', 0):6.1f}s "
              f"{os.path.basename(p)[:52]}", flush=True)
    print("\ntally:", dict(tally))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"tally": dict(tally), "probed": len(sample),
                   "results": results}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
