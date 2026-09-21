"""Per-source grid-vs-text recall audit.

For one sample doc per source, measures how much of the page's numeric content
the table grid captures versus what lives in the text layer. This is the
scalable form of the golden set: it needs no hand-verified cells because the
text layer is the reference, and it measures exactly the quantity that matters
for time-series work (does the grid drop values the page actually contains).

Usage: python scripts/analysis/grid_vs_text_audit.py [--per-source 2]
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "extract"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=2)
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--out", default=os.path.join(REPO, "scripts", "analysis",
                                                  "grid_vs_text_audit.json"))
    a = ap.parse_args()
    import pymupdf
    import extract_all as E

    inv = [json.loads(l) for l in
           open(os.path.join(REPO, "data", "extracted", "inventory.jsonl"), encoding="utf-8")]
    uniq = [r for r in inv if not r.get("dup_of_content")]
    by = collections.defaultdict(list)
    for r in uniq:
        by[r["source"]].append(r)
    rng = random.Random(a.seed)

    report = {}
    for src in sorted(by):
        rows = by[src]
        picks = rng.sample(rows, min(a.per_source, len(rows)))
        agg = {"docs": 0, "pages_with_numbers": 0, "grid_captured": 0,
               "text_total": 0, "grid_pct": None, "per_doc": []}
        for r in picks:
            p = os.path.join(REPO, r["path"])
            if not E.is_real_pdf(p):
                continue
            try:
                doc = pymupdf.open(p)
            except Exception:
                continue
            dg = dt = dp = 0
            for pno in range(min(len(doc), 10)):
                try:
                    text = doc[pno].get_text() or ""
                except Exception:
                    continue
                nums = set(re.findall(r"\b\d[\d,]*\.?\d*\b", text))
                if len(nums) < 3:
                    continue
                dp += 1
                tabs = E.extract_tables_union(p, pno)
                blob = " ".join(str(c) for t in tabs
                                for row in (t.get("rows") or []) for c in row).casefold()
                dt += len(nums)
                dg += sum(1 for n in nums if n.casefold() in blob)
            doc.close()
            if dp:
                agg["docs"] += 1
                agg["pages_with_numbers"] += dp
                agg["text_total"] += dt
                agg["grid_captured"] += dg
                agg["per_doc"].append({"doc": r["path"], "pages": dp,
                                       "text_numbers": dt, "grid_captured": dg,
                                       "pct": round(100 * dg / max(1, dt), 1)})
        if agg["text_total"]:
            agg["grid_pct"] = round(100 * agg["grid_captured"] / agg["text_total"], 1)
        report[src] = agg
        print(f"{src:28s} docs={agg['docs']:3d} nums={agg['text_total']:6d} "
              f"grid={agg['grid_captured']:6d} ({agg['grid_pct']}% captured)", flush=True)

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=1)
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
