"""Verify the intermodal indicative-newbuilding price series against the source PDFs.

Two independent checks, neither of which the extraction itself produces:

1. TEXT RECONCILIATION (the primary gate). For every published row the (current, previous)
   pair must appear as a CONSECUTIVE numeric run in the source PDF's own text layer. This
   is the substitute for "render the page and look at it" when no vision tool is available.
2. CONTINUITY (secondary). The `previous` value at issue N should equal the `current` value
   at the nearest EARLIER issue for the same (sector, vessel_type, size). A miss usually
   means our corpus is missing an intervening week, not that the value is wrong - so read
   this one as a smell test, not a gate.

Usage:  python scripts/audit/verify_intermodal_newbuilding.py
Result on 2026-09-28: 3,132/3,134 = 99.94% text-verified (docs/intermodal_newbuilding_verdict.md).
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "extracted" / "series" / "intermodal_newbuilding_prices_series.csv"
CORPUS = ROOT / "corpus" / "01-brokers" / "intermodal"
NUM = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")


def text_reconciliation(rows):
    by_doc = collections.defaultdict(list)
    for r in rows:
        by_doc[r["source_file"]].append(r)
    pdfs = {p.name: p for p in CORPUS.rglob("*.pdf")}
    ok = miss = nodoc = 0
    misses = []
    for src, rs in sorted(by_doc.items()):
        p = pdfs.get(src)
        if p is None:
            nodoc += len(rs)
            continue
        doc = pymupdf.open(str(p))
        toks = []
        for page in doc:
            for w in page.get_text("words"):
                t = w[4].strip().rstrip("%")
                if NUM.match(t):
                    toks.append(t.replace(",", ""))
        doc.close()
        fv = []
        for x in toks:
            try:
                fv.append(float(x))
            except ValueError:
                pass
        pairs = list(zip(fv, fv[1:]))
        for r in rs:
            cur = r["price_current_usd_m"].strip()
            prev = r["price_previous_usd_m"].strip()
            if not cur:
                miss += 1
                continue
            cf = float(cur)
            pf = float(prev) if prev else None
            if pf is None:
                hit = any(abs(a - cf) < 1e-6 for a, b in pairs)
            else:
                hit = any(abs(a - cf) < 1e-6 and abs(b - pf) < 1e-6 for a, b in pairs)
            if hit:
                ok += 1
            else:
                miss += 1
                misses.append((src, r["vessel_type"], cur, prev, r["pct_change"]))
    print(f"published rows: {len(rows)}  docs: {len(by_doc)}  pdf-missing: {nodoc}")
    pct = ok / (ok + miss) * 100 if ok + miss else 0.0
    print(f"(cur,prev) found as a consecutive run in the PDF text layer: {ok}/{ok+miss} = {pct:.2f}%")
    for m in misses:
        print("   MISS", m)


def continuity(rows):
    by = collections.defaultdict(list)
    for r in rows:
        if r["price_current_usd_m"]:
            by[(r["sector"], r["vessel_type"], r["size"])].append(r)
    ok = bad = 0
    examples = []
    for k, rs in by.items():
        rs.sort(key=lambda r: r["issue_date"])
        for i in range(1, len(rs)):
            prev = rs[i]["price_previous_usd_m"].strip()
            cur_earlier = rs[i - 1]["price_current_usd_m"].strip()
            if not prev or not cur_earlier:
                continue
            if abs(float(prev) - float(cur_earlier)) < 1e-9:
                ok += 1
            else:
                bad += 1
                if len(examples) < 12:
                    examples.append((k, rs[i - 1]["issue_date"], cur_earlier, rs[i]["issue_date"], prev))
    print(f"\ncontinuity: {ok}/{ok+bad} = {ok/(ok+bad)*100:.2f}% of prev values equal the "
          f"previous issue's current (misses are usually a missing week in the corpus)")
    for e in examples:
        print("   ", e)


if __name__ == "__main__":
    rows = list(csv.DictReader(open(SERIES, encoding="utf-8")))
    text_reconciliation(rows)
    continuity(rows)
