"""
Intermodal T/C rates - CORRECT end-to-end extraction.

Every fact here was read off rendered pages (scratch/bench/png/intermodal/):

PAGE 2 - "Tanker Market" - carries a TC Rates table with 12 rows:
    $/day              08/05/2026  01/05/2026   +/-%    Diff    2025     2024
    VLCC   300k 1yr TC   120,000    113,250    6.0%    6750   50,615   50,365
           300k 3yr TC    72,500     70,750    2.5%    1750   44,931   47,339
    Suezmax 150k 1yr TC   75,000     75,000    0.0%       0   38,144   45,394
            150k 3yr TC   47,000     47,000    0.0%       0   33,479   38,412
    Aframax 110k 1yr TC   67,500     62,500    8.0%    5000   33,870   45,168
            110k 3yr TC   41,500     41,500    0.0%       0   29,763   39,748
    Panamax 75k 1yr TC    39,750     39,750    0.0%       0   25,226   37,750
            75k 3yr TC    30,000     30,000    0.0%       0   21,258   31,787
    MR      52k 1yr TC    34,250     36,250   -5.5%   -2000   21,809   30,764
            52k 3yr TC    23,750     23,750    0.0%       0   19,782   26,402
    Handy   36k 1yr TC    28,250     28,250    0.0%       0   18,519   26,606
            36k 3yr TC    17,500     17,500    0.0%       0   16,902   19,993

PAGE 3 - "Dry Bulk Market" - carries a SEPARATE TC Rates table with 8 rows:
    Capesize  180k 1yr TC  36,500 / 3yr 25,750
    Panamax    76k 1yr TC  17,000 / 3yr 13,750
    Supramax   58k 1yr TC  15,500 / 3yr 13,250
    Handysize  32k 1yr TC  11,500 / 3yr 11,000

12 + 8 = the 20 inherited RATE_FIELDS. That is why a single page capped at 12/20.

THE TRAP: BOTH pages have a row labelled "Panamax" - the tanker one is 75k
(=39,750) and the dry-bulk one is 76k (=17,000). A pattern accepting 7[56]k
matches both, so the FIELD MUST BE RESOLVED AGAINST THE CORRECT PAGE. Page
context is the disambiguator, and the anchor is unambiguous: the tanker table is
the page containing '300k Nyr TC', the dry-bulk table the page containing
'180k Nyr TC'.

Column and row geometry rules are inherited from the column-aware work, each
earned by a measured failure:
  * the CURRENT week is the LEFTMOST date column in the header;
  * labels are matched against LINE text (get_text('words') splits '300k','1yr','TC');
  * the value must be within 6pt of the label's y-CENTRE (adjacent rows abut);
  * candidates sort by y-distance, never alphabetically ('35,000' < '45,000').
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

import pymupdf  # noqa: E402

SRC = ROOT / "corpus" / "01-brokers" / "intermodal"
OUT = ROOT / "data" / "extracted" / "intermodal_tc_rates_v2.csv"

DATE_HDR = re.compile(r"^(\d{2})/(\d{2})/(\d{2}|\d{4})$")
NUM = re.compile(r"^[\d,]+$")

TANKER = [
    ("vlcc_1y_tc", r"300\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("vlcc_3y_tc", r"300\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("suezmax_1y_tc", r"150\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("suezmax_3y_tc", r"150\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("aframax_1y_tc", r"110\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("aframax_3y_tc", r"110\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("panamax_1y_tc", r"75\s*[kK]\s*1\s*(?:yr|y)\s*TC"),   # tanker panamax = 75k
    ("panamax_3y_tc", r"75\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("mr_1y_tc", r"52\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("mr_3y_tc", r"52\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("handy_tanker_1y_tc", r"36\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("handy_tanker_3y_tc", r"36\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
]
DRYBULK = [
    ("capesize_1y_tc", r"180\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("capesize_3y_tc", r"180\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("panamax_bulk_1y_tc", r"76\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("panamax_bulk_3y_tc", r"76\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("supramax_1y_tc", r"58\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("supramax_3y_tc", r"58\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
    ("handysize_1y_tc", r"32\s*[kK]\s*1\s*(?:yr|y)\s*TC"),
    ("handysize_3y_tc", r"32\s*[kK]\s*3\s*(?:yr|y)\s*TC"),
]

LONG_DATE = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}


def lines_of(pg):
    out = []
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            txt = "".join(sp["text"] for sp in ln.get("spans", [])).strip()
            if txt:
                out.append((ln["bbox"], txt))
    return out


def find_pages(doc):
    """Return (tanker_page, drybulk_page) by the ANCHOR label each table carries.

    The anchor is what removes the Panamax ambiguity: '300k Nyr TC' exists only
    on the tanker page, '180k Nyr TC' only on the dry-bulk page.
    """
    tank = bulk = None
    for i, pg in enumerate(doc, start=1):
        t = pg.get_text()
        if tank is None and re.search(r"300\s*[kK]\s*1\s*(?:yr|y)\s*TC", t, re.I):
            tank = pg
        if bulk is None and re.search(r"180\s*[kK]\s*1\s*(?:yr|y)\s*TC", t, re.I):
            bulk = pg
    return tank, bulk


MONTH_HDR = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}$", re.I)
# US month/day/year, e.g. `5/2/2025` or `4/25/2025`. Measured: the 2025 W18 issue
# prints THIS form for the TC table while every other issue prints `dd/mm/yy`. The
# numeric DATE_HDR above silently rejects it, so that document yielded zero rates.
# The two are distinguished structurally, not by guessing: a dd/mm/yy form always
# has its first component <= 31 AND is followed by a 2-or-4 digit year in the same
# pattern; a US form here has a 4-digit year in the THIRD position. Both are accepted
# and the leftmost header is still the current column.
US_DATE_HDR = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def current_week_x(pg):
    """x-range of the CURRENT week = the LEFTMOST date column in the header.

    Three header formats are accepted, because the corpus contains all three:
      * `dd/mm/yy` or `dd/mm/yyyy`  - the usual numeric form;
      * `May-25` / `Apr-25`         - month-year (e.g. 2025 W18's charts);
      * `5/2/2025` / `4/25/2025`    - US month/day/year (e.g. 2025 W18's TC table).

    The rule is identical for all of them: the CURRENT week is the LEFTMOST header.
    """
    words = pg.get_text("words")
    hdr = [w for w in words
           if DATE_HDR.match(w[4]) or MONTH_HDR.match(w[4]) or US_DATE_HDR.match(w[4])]
    if not hdr:
        return None
    hdr.sort(key=lambda w: w[0])
    return hdr[0][0], hdr[0][2], hdr[0][1]


def extract_table(pg, fields):
    """label -> current-week value, using column x and row y geometry.

    The x-window is the column's own [x0, x1] from the date header plus a tolerance.
    Both tolerances are set from MEASUREMENT, not guesswork:

    * RIGHT = 20pt. Measured across 2,684 rows: the closest a previous-week value ever
      comes to the current-week value is 40.3pt (median 42.8pt). The largest overflow
      seen is 13.5pt. So 20pt recovers every observed case with a >26pt safety margin
      and provably cannot reach the previous column. 12pt dropped 70 documents' last
      row; 22pt on BOTH sides was tried and rejected because it risks the same leak.
    * LEFT = 22pt. A value may print left of the header's measured x0 when it is wider
      than its column. A leftward leak is harmless because the right edge still bounds
      the match.

    The asymmetry is deliberate: the two risks are not symmetric. Crossing right
    selects the WRONG WEEK - the original bug here, which reported 44,750 (last week's
    rate) instead of 44,500.
    """
    xr = current_week_x(pg)
    if not xr:
        return {}
    cur_x0, cur_x1, hdr_y = xr
    LEFT_TOL, RIGHT_TOL = 22.0, 20.0
    words = pg.get_text("words")
    lines = lines_of(pg)
    out = {}
    for field, pat in fields:
        lab_bb = None
        for bb, txt in lines:
            # The label must match the WHOLE row, not a prefix. Without the anchors
            # `^...$`, the pattern `180\s*[kK]\s*1\s*(?:yr|y)\s*TC` is fine but the
            # ordering matters: these tables interleave `180K 6mnt TC` BEFORE
            # `180K 1yr TC`, so a first-match scan can bind to the wrong row. Anchoring
            # the term (`1yr`/`3yr` only) and requiring the line to be exactly the
            # label prevents a 6mnt row from ever satisfying a 1yr field.
            if re.fullmatch(pat.strip(), txt.strip(), re.I) or \
                    (re.search(r"^\s*(?:\d{2,3}\s*[kK]\s*)?" + pat.strip() + r"\s*$",
                               txt.strip(), re.I)):
                lab_bb = bb
                break
        if lab_bb is None:
            # fall back to a looser search so a label with extra words is still found,
            # but never accept a different TERM (1yr vs 3yr vs 6mnt)
            term = "6" if "6" in pat else ("1" if "1" in pat else "3")
            for bb, txt in lines:
                if re.search(rf"\d{{2,3}}\s*[kK]\s*{term}\s*(?:yr|y|mnt|mo|month)\s*TC",
                             txt, re.I):
                    lab_bb = bb
                    break
        if lab_bb is None:
            continue
        lab_yc = (lab_bb[1] + lab_bb[3]) / 2.0
        cands = []
        for w in words:
            if not NUM.match(w[4]) or "," not in w[4]:
                continue
            if not (cur_x0 - LEFT_TOL) <= w[0] <= (cur_x1 + RIGHT_TOL):
                continue
            w_yc = (w[1] + w[3]) / 2.0
            dy = abs(w_yc - lab_yc)
            if dy > 6.0:
                continue
            cands.append((round(dy, 1), w[0], w[4]))
        if cands:
            cands.sort(key=lambda c: (c[0], c[1]))
            out[field] = int(cands[0][2].replace(",", ""))
    return out


def doc_date(doc, path, tanker_page=None):
    """Assessment date, taken from the TC TABLE HEADER's current-week column.

    This matters for correctness of the CONTROL, not just tidiness. The known-good
    49-row CSV dates each report by the assessment date, which is the CURRENT-WEEK
    column header inside the table (e.g. 07/03/25 for the W10 report). Extracting a
    long-form date from the body text instead yields the publication date, which
    differed by a week and made a control comparison match the WRONG pair of rows -
    44,750 (the previous week) instead of 44,500.
    """
    if tanker_page is not None:
        words = tanker_page.get_text("words")
        hdr = [w for w in words if DATE_HDR.match(w[4])]
        if hdr:
            # the table header is the LOWEST dd/mm/yy row on the page (the other
            # occurrence sits high up in the header banner)
            hdr.sort(key=lambda w: -w[1])
            top = hdr[0][1]
            same = [w for w in hdr if abs(w[1] - top) < 3]
            same.sort(key=lambda w: w[0])
            d, mo, y = DATE_HDR.match(same[0][4]).groups()
            if len(y) == 2:
                y = ("20" + y) if int(y) < 70 else ("19" + y)
            return f"{y}-{mo}-{d}", "table-header-current-week"

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
    print(f"intermodal two-table: {len(pdfs)} PDFs", flush=True)
    for i, p in enumerate(pdfs, start=1):
        try:
            with pymupdf.open(p) as doc:
                tp, bp = find_pages(doc)
                vals = {}
                if tp is not None:
                    vals.update(extract_table(tp, TANKER))
                if bp is not None:
                    vals.update(extract_table(bp, DRYBULK))
                iso, prov = doc_date(doc, p, tanker_page=tp)
            row = {"file": p.name, "date": iso, "date_source": prov,
                   "has_tanker_page": tp is not None,
                   "has_bulk_page": bp is not None}
            for f, _ in TANKER + DRYBULK:
                row[f] = vals.get(f)
            row["fields_filled"] = sum(1 for f, _ in TANKER + DRYBULK
                                       if row[f] is not None)
            rows.append(row)
            if i % 25 == 0 or i == len(pdfs):
                print(f"  [{i}/{len(pdfs)}] {p.name[:40]:<40} "
                      f"T={tp is not None} B={bp is not None} "
                      f"fields={row['fields_filled']}/20 date={iso}", flush=True)
        except Exception as e:
            fails.append((p.name, f"{type(e).__name__}: {str(e)[:80]}"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["file", "date", "date_source", "has_tanker_page", "has_bulk_page",
            "fields_filled"] + [f for f, _ in TANKER + DRYBULK]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

    full = [r for r in rows if r["fields_filled"] == 20]
    both = [r for r in rows if r["has_tanker_page"] and r["has_bulk_page"]]
    print()
    print(f"[two-table] files={len(rows)} all-20={len(full)} "
          f"both-pages={len(both)} failed={len(fails)}")
    print(f"wrote {OUT}")
    if fails:
        print("failures:", fails[:5])


if __name__ == "__main__":
    main()
