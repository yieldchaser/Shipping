"""Measure the layout layer's opportunity space: pages where BOTH classical
engines find zero tables but the page is text-dense (a possible missed or
borderless table). That is the only case the gate lets layout run.

Usage: python scripts/extract/layout_opportunity.py --n 14
"""
import argparse
import collections
import json
import os
import random
import sys
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "extract"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=14)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    import pymupdf
    import camelot
    import pdfplumber
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

    pages_total = opp = layout_helped = 0
    for r in sample:
        p = os.path.join(REPO, r["path"])
        if not E.is_real_pdf(p):
            continue
        doc = pymupdf.open(p)
        for pno in range(min(len(doc), 12)):
            chars = len(doc[pno].get_text() or "")
            if chars < 200:
                continue
            pages_total += 1
            nt = 0
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    nt += camelot.read_pdf(p, pages=str(pno + 1), flavor="stream").n
                except Exception:
                    pass
                try:
                    with pdfplumber.open(p) as pl:
                        nt += len(pl.pages[pno].find_tables())
                except Exception:
                    pass
            if nt == 0:
                opp += 1
                regions = E._LAYOUT_WORKER.regions(p, pno) if E._LAYOUT_WORKER else None
                if regions is None:
                    E._LAYOUT_WORKER = E.LayoutWorker()
                    regions = E._LAYOUT_WORKER.regions(p, pno)
                tabs = [x for x in (regions or []) if x[4] == "table"]
                if tabs:
                    layout_helped += 1
                    print(f"  layout FOUND {len(tabs)} table region(s) where union found 0: "
                          f"{os.path.basename(p)[:45]} p{pno}", flush=True)
        doc.close()
    print(f"\npages probed: {pages_total}")
    print(f"union found 0 tables on: {opp} pages ({100*opp/max(1,pages_total):.1f}%)")
    print(f"layout found table regions on {layout_helped} of those")
    print(f"=> layout gate fires on ~{100*opp/max(1,pages_total):.0f}% of text pages; "
          f"its unique contribution: {layout_helped} page(s) in this sample")
    return 0


if __name__ == "__main__":
    sys.exit(main())
