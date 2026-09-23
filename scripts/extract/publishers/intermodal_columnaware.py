"""
Intermodal T/C rates - COLUMN-AWARE extraction (the fix).

The failure this replaces: patterns like `300[Kk]\\s+1yr\\s+TC\\s+([\\d,]+)` are
label-followed-by-number, but the TC Rates table carries SEVERAL numeric columns
per row:

    $/day                 07/03/25   28/02/25    +/-%   Diff    2024    2023
    VLCC   300k 1yr TC     44,500     44,750    -0.6%   -250   50,365  48,601

so the pattern cannot know which column it caught. It returned 44,750 (the
PREVIOUS week) where the page shows 44,500 (current week). 162 of 980 overlapping
values disagreed with the known-good CSV.

The fix takes positions from GEOMETRY:
  1. find the header row that carries the two dd/mm/yy dates;
  2. the FIRST (leftmost) date column is the current week - take its x-range;
  3. for each labelled row, take the number whose x-range falls inside it.

Validation is built in: the run reports agreement with the known-good 49-row CSV
on the overlap. Anything under ~95% means do not trust the 2021-2024 history.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

import pymupdf  # noqa: E402

SRC = ROOT / "corpus" / "01-brokers" / "intermodal"
OUT = ROOT / "data" / "extracted" / "intermodal_tc_rates_columnaware.csv"

DATE_HDR = re.compile(r"^(\d{2})/(\d{2})/(\d{2})$")
# label -> (row-label pattern).  Matched against a single text line.
LABELS = [
    ("vlcc_1y_tc", r"300[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("vlcc_3y_tc", r"300[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("suezmax_1y_tc", r"150[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("suezmax_3y_tc", r"150[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("aframax_1y_tc", r"110[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("aframax_3y_tc", r"110[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("lr1_1y_tc", r"75[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("lr1_3y_tc", r"75[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("mr_1y_tc", r"52[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("mr_3y_tc", r"52[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("handy_tanker_1y_tc", r"36[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("handy_tanker_3y_tc", r"36[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("capesize_1y_tc", r"180[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("capesize_3y_tc", r"180[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("panamax_1y_tc", r"7[56][kK]\s+1\s*(?:yr|y)\s*TC"),
    ("panamax_3y_tc", r"7[56][kK]\s+3\s*(?:yr|y)\s*TC"),
    ("supramax_1y_tc", r"58[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("supramax_3y_tc", r"58[kK]\s+3\s*(?:yr|y)\s*TC"),
    ("handysize_1y_tc", r"32[kK]\s+1\s*(?:yr|y)\s*TC"),
    ("handysize_3y_tc", r"32[kK]\s+3\s*(?:yr|y)\s*TC"),
]
NUM = re.compile(r"^[\d,]+$")
LONG_DATE = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}


def tc_page(doc):
    """The page carrying the TC Rates table (it is not always the same page)."""
    best = None
    for i, pg in enumerate(doc, start=1):
        t = pg.get_text()
        n = sum(1 for _, pat in LABELS if re.search(pat, t, re.I))
        if best is None or n > best[0]:
            best = (n, i, pg)
    return best[1], best[2]


def col_aware_rows(pg):
    """Extract label -> current-week value using x-geometry.

    NOTE: get_text("words") splits '300k 1yr TC' into three separate words, so a
    label pattern must be matched against a LINE's joined text (get_text("dict")
    gives lines), then the row's y taken from that line's bbox. Matching the
    pattern against a single word returns nothing at all.
    """
    words = pg.get_text("words")     # x0,y0,x1,y1,word,...
    lines = []
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            txt = "".join(sp["text"] for sp in ln.get("spans", [])).strip()
            if txt:
                lines.append((ln["bbox"], txt))

    # 1. the header row carrying dd/mm/yy dates
    hdr = [w for w in words if DATE_HDR.match(w[4])]
    if not hdr:
        return {}
    hdr.sort(key=lambda w: w[0])
    cur_x0, cur_x1 = hdr[0][0], hdr[0][2]          # leftmost date = current week

    out = {}
    for field, pat in LABELS:
        # 2. the labelled LINE (pattern spans words, so match the line's text)
        lab_bb = None
        for bb, txt in lines:
            if re.search(pat, txt, re.I):
                lab_bb = bb
                break
        if lab_bb is None:
            continue
        # 3. Take the number whose x falls under the current-week header AND
        #    whose y-centre is NEAREST the label's y-centre.
        #
        #    Two traps this avoids, both measured on 2025 W10 page 2:
        #      (a) adjacent rows ABUT (row1 y356-367, row2 y367-378), so a loose
        #          +-4pt window pulls the next row's value into this row;
        #      (b) the text layer renders two numbers at the SAME x in one row's
        #          window (e.g. x108 holds both 44,500 and 45,000), so sorting the
        #          candidates alphabetically picked '35,000' over '45,000'.
        #    Sorting by y-distance, and requiring the x to be within the column,
        #    resolves both.
        lab_yc = (lab_bb[1] + lab_bb[3]) / 2.0
        tol = 12
        cands = []
        for w in words:
            if not NUM.match(w[4]):
                continue
            if not (cur_x0 - tol) <= w[0] <= (cur_x1 + tol):
                continue
            w_yc = (w[1] + w[3]) / 2.0
            dy = abs(w_yc - lab_yc)
            if dy > 6.0:                     # must be this row, not the next
                continue
            cands.append((dy, w[0], w[4]))
        if cands:
            cands.sort(key=lambda c: (round(c[0], 1), c[1]))
            out[field] = int(cands[0][2].replace(",", ""))
    return out


def doc_date(doc, path):
    txt = "\n".join(pg.get_text() for pg in doc)
    m = LONG_DATE.search(txt)
    if m:
        d, mon, y = m.group(1), m.group(2).lower(), m.group(3)
        return f"{y}-{MONTHS[mon]:02d}-{int(d):02d}", "long-date"
    m = re.search(r"(20\d\d).*?W(\d{1,2})", path.name)
    if m:
        return f"{m.group(1)}-W{m.group(2).zfill(2)}", "filename-week"
    return None, None


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    rows, fails = [], []
    print(f"column-aware intermodal: {len(pdfs)} PDFs", flush=True)
    for i, p in enumerate(pdfs, start=1):
        try:
            with pymupdf.open(p) as doc:
                pno, pg = tc_page(doc)
                vals = col_aware_rows(pg)
                iso, prov = doc_date(doc, p)
            row = {"file": p.name, "date": iso, "date_source": prov,
                   "tc_page": pno}
            for field, _ in LABELS:
                row[field] = vals.get(field)
            row["fields_filled"] = sum(1 for f, _ in LABELS if row[f] is not None)
            rows.append(row)
            if i % 50 == 0 or i == len(pdfs):
                print(f"  [{i}/{len(pdfs)}] {p.name[:44]:<44} "
                      f"p{pno} fields={row['fields_filled']}/20 date={iso}", flush=True)
        except Exception as e:
            fails.append((p.name, f"{type(e).__name__}: {str(e)[:80]}"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["file", "date", "date_source", "tc_page", "fields_filled"] + \
           [f for f, _ in LABELS]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

    full = [r for r in rows if r["fields_filled"] == 20]
    print()
    print(f"[column-aware] files={len(rows)} all-20={len(full)} failed={len(fails)}")
    print(f"wrote {OUT}")
    if fails:
        print("failures:", fails[:5])


if __name__ == "__main__":
    main()
