#!/usr/bin/env python3
"""Per-source data fix: xclusiv_demolition_charts_series.csv (2026-10-09).

DEFECT (measured): every value in this CSV is ~41.6% BELOW the same document's
own printed demolition price. Cause is in run_xclusiv_vector_charts.py::

    dry_val  = extract_panel_value_from_drawings(drawings_demo, 135.0, 225.0, 700.0, 200.0)
    tank_val = extract_panel_value_from_drawings(drawings_demo, 375.0, 465.0, 700.0, 200.0)

which (a) selects the wrong drawing (the colour filter `c[0]<0.35 and c[1]<0.6
and c[2]>0.4` accepts the INDIA curve (0.271,0.518,0.827) - which happens to be
the correct entity - but also) (b) maps its y through a HARDCODED axis band
(y 135..225 -> 700..200).  The page prints its OWN y-axis ticks (700..200 in
2024, 250..550 in 2026), so the hardcoded band is wrong by ~40%.

The correct value for each row is the INDIA curve's latest point, and the
publisher prints that exact number as TEXT on the same page (the "Demolition
Market" chart labels).  `xclusiv_demolition_series.csv` already holds those
printed numbers exactly (country grain).  This script rewrites the values-only
from them, then verifies each new value is verbatim in ITS OWN source PDF.

Idempotent: a re-run finds nothing stale.  Values-only: no other column, no row
order, no row count changes; EOL LF + no BOM preserved.
"""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERIES_DIR = ROOT / "data" / "extracted" / "series"
CHARTS_CSV = SERIES_DIR / "xclusiv_demolition_charts_series.csv"
TEXT_CSV = SERIES_DIR / "xclusiv_demolition_series.csv"
XCLUSIV_DIR = ROOT / "corpus" / "01-brokers" / "xclusiv"

SEG2TXT = {"Dry Demolition Index": "Bulkers", "Tanker Demolition Index": "Tankers"}
COUNTRY = "India"  # the curve the (fixed) extractor selects - see verdict


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def pdf_index(name):
    for p in XCLUSIV_DIR.glob("*/*.pdf"):
        if p.name == name:
            return p
    return None


def page_text(path):
    import pymupdf
    d = pymupdf.open(str(path))
    try:
        idx = 6 if len(d) >= 8 else (4 if len(d) >= 5 else 0)
        t = d[idx].get_text().upper()
        if "DEMOLITION" not in t:
            t = " ".join(pg.get_text().upper() for pg in d)
        return t
    finally:
        d.close()


def main():
    fields, charts = load(CHARTS_CSV)
    _, text = load(TEXT_CSV)
    exact = {
        (r["source_file"], r["segment"], r["country"]): r["price_usd_per_ldt"]
        for r in text
    }

    changed = 0
    stale = 0
    blanked = []
    quarantine = []
    texcache = {}

    for row in charts:
        key = (row["source_file"], SEG2TXT[row["segment"]], COUNTRY)
        new = exact.get(key)
        if new is None:
            quarantine.append({"source_file": row["source_file"], "segment": row["segment"],
                               "reason": "no printed India value in the text tier"})
            new = ""
        else:
            # CONTROL: the new value must be printed on the row's OWN page.
            sf = row["source_file"]
            if sf not in texcache:
                p = pdf_index(sf)
                texcache[sf] = page_text(p) if p else ""
            iv = str(int(float(new)))
            if not re.search(r"(?<![\d.])" + re.escape(iv) + r"(?![\d.,])", texcache[sf]):
                quarantine.append({"source_file": sf, "segment": row["segment"],
                                   "value": new, "reason": "not verbatim on own page"})
                new = ""
                blanked.append(sf)

        cur = row["price_usd_per_ldt"]
        if cur != new:
            stale += 1
            row["price_usd_per_ldt"] = new
        if cur != new:
            changed += 1

    if stale == 0:
        print("idempotent: nothing stale, no write")
        return 0

    with open(CHARTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(charts)

    qpath = ROOT / "data" / "extracted" / "audit" / "xclusiv_demolition_charts_quarantine.json"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    import json
    qpath.write_text(json.dumps(quarantine, indent=2), encoding="utf-8")

    print(f"rows {len(charts)} | cells rewritten {changed} | blanked {len(blanked)}")
    print(f"quarantine -> {qpath.relative_to(ROOT)} ({len(quarantine)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
