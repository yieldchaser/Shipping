"""Stratified full-corpus projection probe with the final gated extractor.

Samples proportionally across inventory roots, runs process_one, prints
per-doc timing and a final hours projection. Writes JSON summary.

Usage: python scripts/extract/full_probe.py [--n 30] [--seed 21]
"""
import argparse
import collections
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "extract"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted", "vfinal"))
    ap.add_argument("--summary", default=os.path.join(REPO, "scripts", "extract", "probe_summary.json"))
    a = ap.parse_args()

    import extract_all as E

    inv = [json.loads(l) for l in
           open(os.path.join(REPO, "data", "extracted", "inventory.jsonl"), encoding="utf-8")]
    uniq = [r for r in inv if not r.get("dup_of_content")]
    by = collections.defaultdict(list)
    for r in uniq:
        by[r["root"]].append(r)
    rng = random.Random(a.seed)
    total = len(uniq)
    sample = []
    for root, rows in sorted(by.items()):
        k = max(1, round(a.n * len(rows) / total))
        sample += rng.sample(rows, min(k, len(rows)))
    print(f"stratified sample: {len(sample)} docs from {len(by)} roots", flush=True)

    tot = pg = fired = errs = tbls = 0
    rows_out = []
    for r in sample:
        p = os.path.join(REPO, r["path"])
        t0 = time.time()
        try:
            rec = E.process_one(p, a.out)
            dt = time.time() - t0
            tot += dt
            pg += rec["pages"]
            tbls += rec["tables"]
            tpath = os.path.join(a.out, rec["doc"], "tables.jsonl")
            tabs = [json.loads(l) for l in open(tpath, encoding="utf-8")]
            f = len(set(t["page"] for t in tabs
                        if t["engine"] == "camelot-stream+layout-areas"))
            fired += f
            rows_out.append({"doc": rec["doc"], "pages": rec["pages"],
                             "tables": rec["tables"], "layout_pages": f,
                             "secs": round(dt, 1), "root": r["root"]})
            print(f"{dt:6.1f}s {rec['pages']:3d}pg {rec['tables']:3d}tbl lay={f:2d}  "
                  f"{os.path.basename(p)[:48]}", flush=True)
        except Exception as exc:
            errs += 1
            print("ERR", str(exc)[:70], os.path.basename(p)[:45], flush=True)
    ok = max(1, len(sample) - errs)
    pd = tot / ok
    summary = {
        "docs_probed": len(sample), "errors": errs, "pages": pg, "tables": tbls,
        "layout_page_fires": fired, "total_secs": round(tot, 1),
        "secs_per_page": round(tot / max(1, pg), 2),
        "secs_per_doc": round(pd, 1),
        "projection_docs": len(uniq),
        "hours_1_worker": round(pd * len(uniq) / 3600, 1),
        "hours_2_workers": round(pd * len(uniq) / 2 / 3600, 1),
        "per_root": dict(collections.Counter(r["root"] for r in rows_out)),
        "rows": rows_out,
    }
    with open(a.summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"\n=== {tot:.0f}s / {pg} pages / {tbls} tables / {errs} errors / "
          f"{fired} layout fires")
    print(f"    {pd:.1f}s per doc -> {summary['hours_1_worker']}h single, "
          f"{summary['hours_2_workers']}h on 2 workers")
    print(f"    summary -> {a.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
