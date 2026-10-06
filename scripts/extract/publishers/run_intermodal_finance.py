"""
Intermodal Commodities & Ship Finance Extraction Pipeline.

Extracts dense financial and macro intelligence from Intermodal Market Reports (2021-2026):
  - Maritime Stock Data (11-16 publicly listed shipping equities: Danaos, Star Bulk, Costamare, etc.)
  - Bunker Prices (MGO, 380cst, VLSFO across Rotterdam, Houston, Singapore)
  - Macro-Economic Indicators & Currencies (10y US Bond, S&P 500, Nasdaq, Dow Jones, FTSE 100,
    CAC40, DAX, Nikkei, Hang Seng, DJ US Maritime, FX rates, Brent, WTI)

Updates:
  - data/extracted/md/intermodal/<stem>.tables.json
Outputs:
  - data/extracted/series/intermodal_maritime_stocks_series.csv
  - data/extracted/series/intermodal_bunkers_series.csv
  - data/extracted/series/intermodal_macro_series.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

try:  # shared byte-duplicate filter (see doc_dedup.py for why)
    from doc_dedup import byte_duplicate_stems
except ImportError:  # run as a script, not via the orchestrator
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from doc_dedup import byte_duplicate_stems

ROOT = Path(__file__).resolve().parents[3]
PUB = "intermodal"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"


def duplicate_stems() -> set:
    """Stems of corpus PDFs that are byte-identical to another corpus PDF.

    Measured 2026-10-01: the intermodal dedup landed in run_intermodal_full.py only, so THIS writer - macro / maritime_stocks / bunkers - still double-counts 36 rows (macro 16, stocks 11, bunkers 9) from the dropped W38 copy. Both copies were parsed and stacked, so the dropped copy's rows
    double-count. Keep the richest extraction, skip the rest.
    """
    return byte_duplicate_stems(CORPUS_DIR, OUT_MD)

STOCKS_SERIES_CSV = OUT_SERIES / "intermodal_maritime_stocks_series.csv"
BUNKERS_SERIES_CSV = OUT_SERIES / "intermodal_bunkers_series.csv"
MACRO_SERIES_CSV = OUT_SERIES / "intermodal_macro_series.csv"

# Ledger 4.3 - the macro table is 5 DAILY columns plus a W-O-W percent. The wide CSV
# keeps only latest/prior (the newest two days) and puts a day-over-day prior beside a
# week-over-week percent, implying a relation that does not hold. The re-key below
# emits the full row x date grid the skill asks for: a series is (row label, column
# header), and here the header is the PRINT DATE. Verified against the page in
# docs/intermodal_macro_423_verdict.md; the numbers were already faithful - this is a
# schema/semantic fix plus recovery of the 3 daily points the wide file drops.
MACRO_DAILY_SERIES_CSV = OUT_SERIES / "intermodal_macro_daily_series.csv"
_DATE_LINE_RX = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2}$")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _iso_from_dmon(s: str):
    m = re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$", s)
    if not m:
        return None
    d, mon, yy = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mo = _MONTHS.get(mon)
    if not mo:
        return None
    return f"20{yy:02d}-{mo:02d}-{d:02d}"


# The publisher's own cover line, e.g. "Week 06 | Tuesday13th February 2024".
# Verified present and unique on page 0 of 252/252 intermodal reports, so it is the
# authoritative issue date. Without it this builder fell back to a fake "2026-00-00"
# on 6 documents (2024 W06/W07/W08/W10/W11/W12) x 3 series = 218 rows.
COVER_RX = re.compile(
    r"Week\s*(\d{1,2})\s*\|\s*[A-Za-z]+\s*(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(20\d{2})", re.I
)
COVER_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def extract_meta(pdf_path: Path) -> Tuple[int, str]:
    """Extract report week and issue date from the cover line, stem, or first page."""
    fn = pdf_path.stem
    # Week
    m_wk = re.search(r"Week[-_ ]+(\d{1,2})", fn, re.I)
    wk = int(m_wk.group(1)) if m_wk else 0

    # Date
    doc = pymupdf.open(pdf_path)
    dt = None
    # Priority 1: the publisher's own cover line.
    for pg in doc[:2]:
        m_cov = COVER_RX.search(pg.get_text())
        if m_cov:
            dt = (f"{int(m_cov.group(4)):04d}-{COVER_MONTHS[m_cov.group(3).lower()]:02d}"
                  f"-{int(m_cov.group(2)):02d}")
            break
    # Priority 2: a date embedded in the filename.
    if not dt:
        m_dmy = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
        if m_dmy:
            d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"
    if not dt:
        for pg in doc[:2]:
            t = pg.get_text()
            m = re.search(r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", t, re.I)
            if m:
                mo_names = {
                    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
                }
                d = int(m.group(1))
                mo = mo_names[m.group(2).lower()]
                y = int(m.group(3))
                dt = f"{y:04d}-{mo:02d}-{d:02d}"
                break
    if not dt:
        # An unknown date is written BLANK, never as a fake "2026-00-00": a zero
        # month parses as a real ISO date and sorts as if it were in 2026.
        dt = ""

    return wk, dt


def find_finance_page(doc: pymupdf.Document) -> Optional[int]:
    """Find the page index (0-based) for Commodities & Ship Finance."""
    for pno, pg in enumerate(doc):
        t = pg.get_text()
        if any(k in t for k in [
            "10year US Bond", "S&P 500", "FTSE 100", "Nikkei",
            "DANAOS", "Bunker Prices", "Commodities & Ship Finance"
        ]):
            return pno
    return None


def parse_finance_page(doc: pymupdf.Document, page_no: int, issue_date: str, report_week: int, source_file: str):
    page = doc[page_no]
    blocks = page.get_text("blocks")
    full_text = page.get_text()

    stocks = []
    bunkers = []
    macro = []

    # 1. Maritime Stocks
    for b in blocks:
        lines = [l.strip() for l in b[4].splitlines() if l.strip()]
        ex_idx = -1
        for i, l in enumerate(lines):
            if any(l.startswith(ex) for ex in ["NASDAQ", "NYSE"]):
                ex_idx = i
                break
        if ex_idx > 0:
            comp = " ".join(lines[:ex_idx])
            rest = lines[ex_idx:]
            ex_val = "NASDAQ" if "NASDAQ" in rest[0] else "NYSE"
            curr_val = "USD"
            nums = []
            pct_val = None
            for item in rest[1:]:
                if item == "USD": continue
                if "%" in item:
                    pct_val = item
                else:
                    m = re.search(r"[-+]?\d+(?:\.\d+)?", item.replace(",", ""))
                    if m:
                        nums.append(float(m.group(0)))
            cur_p = nums[0] if len(nums) > 0 else None
            pri_p = nums[1] if len(nums) > 1 else None
            stocks.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "company": comp,
                "exchange": ex_val,
                "currency": curr_val,
                "current_price": cur_p,
                "prior_price": pri_p,
                "change_pct": pct_val,
                "source_file": source_file,
            })

    # 2. Bunker Prices
    # Extract all bunker rows
    bunker_items = []
    for b in blocks:
        bt = b[4].strip()
        lines = [l.strip() for l in bt.splitlines() if l.strip()]
        if any(p in bt for p in ["Rotterdam", "Houston", "Singapore", "Piraeus", "Fujairah"]) and any("%" in l or any(c.isdigit() for c in l) for l in lines):
            tokens = []
            for l in lines: tokens.extend(l.split())
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok in ["Rotterdam", "Houston", "Singapore", "Piraeus", "Fujairah"]:
                    port = tok
                    j = i + 1
                    nums = []
                    pct = None
                    while j < len(tokens) and tokens[j] not in ["Rotterdam", "Houston", "Singapore", "Piraeus", "Fujairah", "Brent", "WTI"]:
                        t_clean = tokens[j].replace(",", "")
                        if "%" in t_clean: pct = t_clean
                        else:
                            m = re.search(r"[-+]?\d+(?:\.\d+)?", t_clean)
                            if m: nums.append(float(m.group(0)))
                        j += 1
                    if nums:
                        bunker_items.append({"port": port, "price": nums[0], "prior": nums[1] if len(nums) > 1 else None, "change_pct": pct})
                    i = j
                else:
                    i += 1

    # Assign fuel grades (MGO, 380cst, VLSFO)
    # If 9 items: 3 MGO, 3 380cst, 3 VLSFO
    if len(bunker_items) == 9:
        grades = ["MGO"] * 3 + ["380cst"] * 3 + ["VLSFO"] * 3
        for idx, item in enumerate(bunker_items):
            bunkers.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "fuel_grade": grades[idx],
                "port": item["port"],
                "price_usd_per_mt": item["price"],
                "prior_price_usd_per_mt": item["prior"],
                "change_pct": item["change_pct"],
                "source_file": source_file,
            })
    elif len(bunker_items) > 0:
        # Fallback grade assignment
        for item in bunker_items:
            bunkers.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "fuel_grade": "Bunker",
                "port": item["port"],
                "price_usd_per_mt": item["price"],
                "prior_price_usd_per_mt": item["prior"],
                "change_pct": item["change_pct"],
                "source_file": source_file,
            })

    # 3. Macro Indicators - content-anchored row parse.
    # The previous regex required a SIGN on the change and let its greedy middle
    # group swallow a bare positive number, so EVERY positive change was dropped:
    # 2,075 of 3,739 rows carried a blank wow_change_pct and 0 of the 1,664
    # survivors were positive, while the publisher prints a change on essentially
    # every row ("S&P 500 ... 1.7%"). A value cell can also be TEXT
    # ("market closed" on US holidays), which broke the old number-only scan.
    # Anchored on the label plus the cell after it being a value - never on row
    # order or geometry. Measured on the PDF text layer; see
    # docs/intermodal_macro_verdict.md.
    INDICATORS = [
        ("10year US Bond", "Bonds"),
        ("S&P 500", "Stock Indices"),
        ("Nasdaq", "Stock Indices"),
        ("Dow Jones", "Stock Indices"),
        ("FTSE 100", "Stock Indices"),
        ("FTSE All-Share UK", "Stock Indices"),
        ("CAC40", "Stock Indices"),
        ("Xetra Dax", "Stock Indices"),
        ("Nikkei", "Stock Indices"),
        ("Hang Seng", "Stock Indices"),
        ("DJ US Maritime", "Stock Indices"),
        ("€ / $", "Currencies"),
        ("£ / $", "Currencies"),
        ("$ / ¥", "Currencies"),
        ("$ / NoK", "Currencies"),
        ("Yuan / $", "Currencies"),
        ("Won / $", "Currencies"),
        ("$ INDEX", "Currencies"),
        ("Brent", "Commodities"),
        ("WTI", "Commodities"),
    ]
    # Whitespace-insensitive label keys. The publisher's text layer kernels some
    # labels apart in certain eras ("Dow Jones" -> "Dow J ones " across 2023
    # W21-W36, 15 documents), which an exact-match allowlist silently dropped.
    def _nkey(s: str) -> str:
        return re.sub(r"\s+", "", s).lower()
    IND_CAT = {_nkey(k): (k, v) for k, v in INDICATORS}
    NUM_RX = re.compile(r"^[-+]?[\d,]+(?:\.\d+)?$")
    PCT_RX = re.compile(r"^[-+]?\d+(?:\.\d+)?%$")
    # A value column the publisher left blank with words rather than a number.
    # The publisher spells a holiday value cell "mrkt closed" (23x), "market closed"
    # (3x) and once "mrkt close". Measured across 252 documents.
    NONNUM = {"mrkt closed", "mrkt close", "market closed", "n/a", "na", "closed", "-", "--"}
    # A value can also carry a doubled period ("2..756"); normalise it.
    DOTS_RX = re.compile(r"[.]{2,}")

    def parse_float_safe(s: Optional[str]) -> Optional[float]:
        if not s:
            return None
        m_num = re.search(r"[-+]?\d+(?:\.\d+)?", s.replace(",", ""))
        return float(m_num.group(0)) if m_num else None

    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    def _macro_print_dates(rows):
        # The DAILY print dates of the 5-column macro table (newest first).
        # Anchored on CONTENT: the first real macro indicator row, then walk back
        # over the W-O-W / Change header and collect the run of date-shaped lines
        # before it. Layout is NOT stable: 2021-2022 print the dates right after the
        # section title, 2025-2026 insert a nav block ('Market Data / Maritime Stock
        # Data / ...') first - anchoring on the indicator label, never the section
        # title, survives both. Verified on 2021 W26, 2022 W04, 2023 W08, 2025 W10
        # and 2026 W10.
        first = None
        for i, l in enumerate(rows):
            if _nkey(l) in IND_CAT and i + 1 < len(rows) and (
                    NUM_RX.match(rows[i + 1]) or rows[i + 1].lower() in NONNUM):
                first = i
                break
        if first is None:
            return []
        j = first - 1
        dated = []
        # The header sits between the dates and the first indicator, and its form is
        # NOT stable: a bare line ("W-O-W" / "Change %"), or FUSED onto the last date
        # ("20-May-24 W-O-W Change %", 2024+). The text layer also kerned the month in
        # some 2023+ issues ("2-J un-23"). So normalise each line (drop whitespace and
        # the header words) and accept it only if a date remains. Measured: both the
        # fusion and the kerning silently cost a whole document's date run otherwise.
        while j >= 0:
            clean = (re.sub(r"\s+", "", rows[j]).replace("W-O-W", "")
                     .replace("Change", "").replace("%", ""))
            # findall, not a single match: two adjacent date cells are sometimes fused
            # onto one text line ("29-May-24 28-May-24", 7 docs: 2024 W21/W47, 2025
            # W12/W46/W47/W48 + a compressed copy) - a single-match test drops the
            # second date and the row loses its alignment.
            hits = re.findall(r"\d{1,2}-[A-Za-z]{3}-\d{2}", clean)
            if hits:
                # PREPEND: we walk the date run backwards (oldest line first), so the
                # newest date must end up at the front. Prepending also preserves the
                # natural left-to-right order WITHIN a fused line, which a final
                # reverse() would have flipped (measured: it swapped 28/29-May-24).
                dated = hits + dated
                j -= 1
                continue
            if clean == "":
                j -= 1  # a pure header fragment -> keep walking back
                continue
            break  # real content -> the date run has ended
        return [d for d in (_iso_from_dmon(x) for x in dated) if d]

    macro_dates = _macro_print_dates(lines)
    macro_daily = []
    for i, lab in enumerate(lines):
        hit = IND_CAT.get(_nkey(lab))
        if hit is None:
            continue
        lab, cat = hit  # store the CANONICAL label, not the kerned form
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # Anchor: the cell right after the label must be a value or a known
        # non-numeric marker. This rejects a prose mention of the index name.
        if not (NUM_RX.match(nxt) or nxt.lower() in NONNUM):
            continue
        vals: List[str] = []
        # positional view: NONNUM cells stay as None so index k aligns with
        # macro_dates[k]; the wide-file vals (numeric only) keep their old meaning.
        vals_pos: List[Optional[str]] = []
        pct = None
        j = i + 1
        while j < len(lines) and j <= i + 14:
            cell = DOTS_RX.sub(".", lines[j])
            if PCT_RX.match(cell):
                pct = cell
                break
            if NUM_RX.match(cell):
                vals.append(cell)
                vals_pos.append(cell)
            elif cell.lower() in NONNUM:
                vals_pos.append(None)  # a text value cell ("market closed")
            else:
                break  # next label / prose -> end of this row
            j += 1
        val1 = parse_float_safe(vals[0]) if len(vals) >= 1 else None
        val2 = parse_float_safe(vals[1]) if len(vals) >= 2 else None
        if val1 is not None:
            macro.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "category": cat,
                "indicator": lab,
                "latest_value": val1,
                "prior_value": val2,
                "wow_change_pct": pct,
                "source_file": source_file,
            })
            # Date-keyed grid: only when this row's positional cell count matches the
            # detected date run. Otherwise leave it out rather than guess an alignment
            # (a wrong print_date is worse than a missing one).
            if macro_dates and len(vals_pos) == len(macro_dates):
                for off, (d_iso, raw) in enumerate(zip(macro_dates, vals_pos)):
                    macro_daily.append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "category": cat,
                        "indicator": lab,
                        "print_date": d_iso,
                        "day_offset": off,
                        "value": parse_float_safe(raw) if raw is not None else None,
                        "is_latest": 1 if off == 0 else 0,
                        "wow_change_pct": pct,
                        "source_file": source_file,
                    })
    return stocks, bunkers, macro, macro_daily


def run_all():
    files = sorted(glob.glob(str(CORPUS_DIR / "*/*.pdf")))
    _dup = duplicate_stems()
    if _dup:
        _b = len(files)
        files = [f for f in files if Path(f).stem not in _dup]
        print(f"[dedup] skipped {_b - len(files)} byte-identical duplicate document(s)")
    print(f"Processing {len(files)} Intermodal reports for Finance & Macro data...")

    all_stocks = []
    all_bunkers = []
    all_macro = []
    all_macro_daily = []

    for pdf_path_str in files:
        pdf_path = Path(pdf_path_str)
        wk, dt = extract_meta(pdf_path)
        doc = pymupdf.open(pdf_path)
        pno = find_finance_page(doc)
        if pno is None:
            continue

        st, bu, ma, mad = parse_finance_page(doc, pno, dt, wk, pdf_path.name)
        all_stocks.extend(st)
        all_bunkers.extend(bu)
        all_macro.extend(ma)
        all_macro_daily.extend(mad)

        # Update JSON sidecar if it exists
        stem = pdf_path.stem
        # Sidecars are YEAR-PARTITIONED (data/extracted/md/intermodal/<year>/),
        # matching run_intermodal_full.py's writer. The old flat path
        # (OUT_MD / f"{stem}.tables.json") never existed on disk, so this
        # enrichment was a silent no-op (measured: 0/256 sidecars carried
        # macro_indicators).
        year_str = dt[:4] if dt and dt[:4].isdigit() else "2026"
        sidecar_path = OUT_MD / year_str / f"{stem}.tables.json"
        if sidecar_path.exists():
            try:
                sc_data = json.load(open(sidecar_path, encoding="utf-8"))
                if isinstance(sc_data, dict) and "tables" in sc_data:
                    sc_data["tables"]["maritime_stocks"] = st
                    sc_data["tables"]["bunker_prices"] = bu
                    sc_data["tables"]["macro_indicators"] = ma
                    with open(sidecar_path, "w", encoding="utf-8") as fp:
                        json.dump(sc_data, fp, indent=2)
            except Exception as e:
                pass

    print(f"Total extracted: {len(all_stocks)} stocks, {len(all_bunkers)} bunkers, {len(all_macro)} macro indicators")

    # Write series CSVs
    if all_stocks:
        with open(STOCKS_SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "issue_date", "report_week", "company", "exchange", "currency",
                "current_price", "prior_price", "change_pct", "source_file"
            ])
            writer.writeheader()
            writer.writerows(all_stocks)
        print(f"Exported {len(all_stocks)} rows to {STOCKS_SERIES_CSV.name}")

    if all_bunkers:
        with open(BUNKERS_SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "issue_date", "report_week", "fuel_grade", "port",
                "price_usd_per_mt", "prior_price_usd_per_mt", "change_pct", "source_file"
            ])
            writer.writeheader()
            writer.writerows(all_bunkers)
        print(f"Exported {len(all_bunkers)} rows to {BUNKERS_SERIES_CSV.name}")

    if all_macro:
        with open(MACRO_SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "issue_date", "report_week", "category", "indicator",
                "latest_value", "prior_value", "wow_change_pct", "source_file"
            ])
            writer.writeheader()
            writer.writerows(all_macro)
        print(f"Exported {len(all_macro)} rows to {MACRO_SERIES_CSV.name}")

    if all_macro_daily:
        with open(MACRO_DAILY_SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "issue_date", "report_week", "category", "indicator",
                "print_date", "day_offset", "value", "is_latest",
                "wow_change_pct", "source_file"
            ])
            writer.writeheader()
            writer.writerows(all_macro_daily)
        print(f"Exported {len(all_macro_daily)} rows to {MACRO_DAILY_SERIES_CSV.name}")


if __name__ == "__main__":
    run_all()
