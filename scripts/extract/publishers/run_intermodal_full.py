"""
Intermodal Weekly Market Reports - Full Cover-to-Cover High-Fidelity Extraction Pipeline.

Extracts 100% zero-data-loss tabular and narrative data from weekly Intermodal reports:
  - Page 1: Market Insight essay & editorial commentary
  - Page 2: Tanker Market (narrative, tanker spot rates, TC rates, indicative market values)
  - Page 3: Dry Bulk Market (narrative, Baltic dry indices, TC rates, indicative market values)
  - Page 4: Secondhand Sales (Bulk carriers, Tankers, Containers, Gas)
  - Page 5: Newbuilding Prices and Reported Orders
  - Page 6: Indicative Demolition Prices, Currencies, and Demolition Sales
  - Page 7: Commodities, Ship Finance, Bunker Prices, and Maritime Stocks
  - Page 8: Contact & Directory information

Outputs:
  - Full cover-to-cover markdown:
      * data/extracted/llamaparse_intermodal_full/<stem>.md
      * data/extracted/md/intermodal/<stem>.md
  - Run state:
      * data/extracted/llamaparse_intermodal_full/_run_state.json
  - Table sidecars:
      * data/extracted/md/intermodal/<stem>.tables.json
  - Stacked Series CSVs:
      * data/extracted/series/intermodal_tanker_spot_series.csv
      * data/extracted/series/intermodal_tc_rates_series.csv
      * data/extracted/series/intermodal_indicative_values_series.csv
      * data/extracted/series/intermodal_baltic_indices_series.csv
      * data/extracted/series/intermodal_currencies_series.csv
      * data/extracted/series/intermodal_sales_series.csv
      * data/extracted/series/intermodal_newbuilding_series.csv
      * data/extracted/series/intermodal_demolition_series.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from bs4 import BeautifulSoup
from llama_parse import LlamaParse

# ---------------------------------------------------------------------------
# Credentials and Configuration
# ---------------------------------------------------------------------------
DEFAULT_API_KEY = "llx-p1IAIhBMQdXo21E9Wz2jgW6hoTPJ8Xs2VvxJMd7S7b8aXYUR"
API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", DEFAULT_API_KEY)
if API_KEY == "llx-hM8tERqfFZk1JGzLdPcuSgcaBctblBqm76nIieMxIx6AnAgB":
    API_KEY = DEFAULT_API_KEY
os.environ["LLAMA_CLOUD_API_KEY"] = API_KEY

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUB = "intermodal"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_FULL_DIR = ROOT / "data" / "extracted" / "llamaparse_intermodal_full"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
STATE_FILE = OUT_FULL_DIR / "_run_state.json"


def byte_duplicate_stems() -> set:
    """Stems of corpus PDFs that are BYTE-IDENTICAL to another corpus PDF.

    A second collection route re-drops the same weekly report under a different
    filename (measured 2026-10-01: intermodal_2026_W39_*.pdf and
    intermodal_30_09_2026_*week_39*.pdf are the same md5, as are the W38 pair).
    The publisher name of each file is the canonical key, so a file that is a
    byte-for-byte copy of another is a duplicate document, not a new issue.
    Keep the lexicographically-first stem and skip the rest - at BOTH the
    reparse enumeration and the sidecar stack, otherwise the stale sidecar of
    the skipped copy re-adds every row.
    """
    by_hash: Dict[str, List[pathlib.Path]] = {}
    for pdf in sorted(CORPUS_DIR.rglob("*.pdf")):
        try:
            h = hashlib.md5(pdf.read_bytes()).hexdigest()
        except OSError:
            continue
        by_hash.setdefault(h, []).append(pdf)
    skip: set = set()
    for group in by_hash.values():
        if len(group) > 1:
            skip.update(p.stem for p in group[1:])
    return skip


TANKER_SPOT_CSV = OUT_SERIES_DIR / "intermodal_tanker_spot_series.csv"
TC_RATES_CSV = OUT_SERIES_DIR / "intermodal_tc_rates_series.csv"
INDICATIVE_VALUES_CSV = OUT_SERIES_DIR / "intermodal_indicative_values_series.csv"
BALTIC_INDICES_CSV = OUT_SERIES_DIR / "intermodal_baltic_indices_series.csv"
CURRENCIES_CSV = OUT_SERIES_DIR / "intermodal_currencies_series.csv"

SALES_SERIES_CSV = OUT_SERIES_DIR / "intermodal_sales_series.csv"
NB_SERIES_CSV = OUT_SERIES_DIR / "intermodal_newbuilding_series.csv"
NB_PRICES_CSV = OUT_SERIES_DIR / "intermodal_newbuilding_prices_series.csv"
DEMO_SERIES_CSV = OUT_SERIES_DIR / "intermodal_demolition_series.csv"
DEMO_SALES_CSV = OUT_SERIES_DIR / "intermodal_demo_sales_series.csv"
DEMO_PRICES_CSV = OUT_SERIES_DIR / "intermodal_demolition_prices_series.csv"
NB_ORDERS_CSV = OUT_SERIES_DIR / "intermodal_newbuilding_orders_series.csv"

INITIAL_CREDITS = 9733
CREDITS_PER_PAGE = 3  # cost_effective tier

state_lock = threading.Lock()
quota_exceeded_event = threading.Event()

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

LONG_DATE_RX = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\b", re.I
)
DATE_HDR_RX = re.compile(r"(\d{2})/(\d{2})/(\d{2}|\d{4})")
# The publisher's own cover line, e.g. "Week 06 | Tuesday13th February 2024".
# Verified present and unique on page 0 of 252/252 intermodal reports.
# It is the AUTHORITATIVE issue date; the loose LONG_DATE_RX below also fires on
# body prose ("On Friday, February 9th, the BDTI settled at...") and mis-dated 9 docs.
COVER_RX = re.compile(
    r"Week\s*(\d{1,2})\s*\|\s*[A-Za-z]+\s*(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(20\d{2})", re.I
)


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------
def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "done": {},
        "failed": {},
        "pages_parsed": 0,
        "credits_estimated": 0,
        "credits_remaining": INITIAL_CREDITS,
        "tier": "cost_effective"
    }


def save_state(state: Dict[str, Any]):
    OUT_FULL_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Metadata Extraction
# ---------------------------------------------------------------------------
def extract_report_metadata(pdf_path: pathlib.Path) -> Tuple[int, str]:
    """Extract report week integer and ISO issue_date (YYYY-MM-DD)."""
    fn = pdf_path.stem
    doc = pymupdf.open(pdf_path)

    # 1. Report Week
    wk: Optional[int] = None
    m_wk = re.search(r"Week[-_ ]+(\d{1,2})", fn, re.I)
    if m_wk:
        wk = int(m_wk.group(1))
    else:
        for pg in doc[:2]:
            t = pg.get_text()
            m = re.search(r"Week\s*(\d{1,2})", t, re.I)
            if m:
                wk = int(m.group(1))
                break

    # 2. Issue Date
    # Priority 1 is the publisher's own cover line. It is the report's statement of
    # its own date, it is unique on page 0, and it is immune to the body prose that
    # the loose regexes below also match ("On Friday, February 9th, the BDTI ...").
    issue_date: Optional[str] = None
    for pg in doc[:2]:
        m_cov = COVER_RX.search(pg.get_text())
        if m_cov:
            issue_date = (
                f"{int(m_cov.group(4)):04d}-{MONTHS[m_cov.group(3).lower()]:02d}"
                f"-{int(m_cov.group(2)):02d}"
            )
            break

    # Priority 2: a date embedded in the filename.
    if not issue_date:
        m_dmy = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
        if m_dmy:
            d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            issue_date = f"{y:04d}-{m:02d}-{d:02d}"

    # Priority 3: loose in-text dates.
    if not issue_date:
        for pg in doc[:2]:
            t = pg.get_text()
            m_dt = LONG_DATE_RX.search(t)
            if m_dt:
                d, mon, y = int(m_dt.group(1)), m_dt.group(2).lower(), int(m_dt.group(3))
                issue_date = f"{y:04d}-{MONTHS[mon]:02d}-{d:02d}"
                break
            m_num = DATE_HDR_RX.search(t)
            if m_num:
                d, mo, yr = int(m_num.group(1)), int(m_num.group(2)), int(m_num.group(3))
                if yr < 100:
                    yr = 2000 + yr
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    issue_date = f"{yr:04d}-{mo:02d}-{d:02d}"
                    break

    if not issue_date and wk:
        m_y = re.search(r"(202\d)", fn)
        if m_y:
            yr = int(m_y.group(1))
            try:
                issue_date = dt.date.fromisocalendar(yr, wk, 2).isoformat()
            except Exception:
                pass

    if wk is None and issue_date:
        try:
            wk = dt.date.fromisoformat(issue_date).isocalendar()[1]
        except Exception:
            pass

    return wk or 1, issue_date or ""


# ---------------------------------------------------------------------------
# Data Cleaning & Grid Extraction
# ---------------------------------------------------------------------------
def clean_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).replace("**", "").replace("~~", "").replace("\n", " ").replace("<br/>", " ").replace("<br>", " ").strip()
    return re.sub(r"\s+", " ", s)


def parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("%", "").replace("$", "").strip()
    m = re.search(r"([-+]?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def parse_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("%", "").replace("$", "").strip()
    m = re.search(r"([-+]?\d+)", s)
    return int(m.group(1)) if m else None


def read_dual_separator_number(token: str) -> Optional[float]:
    """Read a numeric token that may use '.' OR ',' as its DECIMAL point.

    This publisher prints BOTH conventions inside the same table. Measured
    2026-10-01 against the source PDFs' positioned text, never against another
    extractor:

        'CAPE MOUNT AUSTIN 178,623 2010 MITSUI, Japan MAN-B&W Jun-25 $ 26,75m Chinese'
        'KMAX PEDHOULAS CHERRY 82,013 2015 MAN-B&W Jul-25 $26,625m Greek (Pyxis)'
        'VLCC DONOUSSA 299,999 2016 DAEWOO, South Korea MAN B&W Jan-31 DH $ 123,0m'

    Shape census over the 3,358 price rows of intermodal_sales_series.csv:
    period-decimal 1,629 rows, decimal-comma 179 rows, thousands-grouped only on
    amounts that are not millions figures. Rule, derived from that census:
      1-2 digits after a comma -> the comma IS the decimal point ('21,25' = 21.25)
      3 digits after a comma   -> thousands separator ('470,000' = 470000)
    The 3-digit case is re-read by the caller when the figure is denominated in
    millions (a 26,625m vessel would cost 26.6 billion, so it is 26.625m).
    """
    token = (token or "").strip().rstrip(".,")
    if not token:
        return None
    if "," in token:
        head, tail = token.rsplit(",", 1)
        tail = tail.strip(".")
        if not tail.isdigit():
            return None
        head_digits = re.sub(r"[.,]", "", head)
        if len(tail) <= 2:
            # 1-2 digits after the comma: the comma IS the decimal point
            if not head_digits:
                return float(f"0.{tail}")
            return float(f"{head_digits}.{tail}")
        return float(head_digits + tail) if head_digits else None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        # periods in threes are thousands separators (European style, '60.000')
        return float(token.replace(".", ""))
    # no comma: a lone period is a real decimal point ('47.5' stays 47.5)
    try:
        return float(token)
    except ValueError:
        return None
def parse_price_mill(p_str: Any) -> Optional[float]:
    """Price in million USD, tolerating the publisher's mixed separator.

    Before 2026-10-01 the comma was deleted outright, so every comma-decimal
    price was stored 10x-1000x too large ('$ 21,25m' -> 2125.0 instead of 21.25;
    '$26,625m' -> 26625.0 instead of 26.625). 179 sales rows across 65 documents.
    """
    if not p_str:
        return None
    s = str(p_str)
    m = re.search(r"\d[\d.,]*", s)
    if not m:
        return None
    token = m.group(0).rstrip(".,")
    val = read_dual_separator_number(token)
    if val is None:
        return None
    millions = bool(re.search(r"\d\s*(?:m\b|mn\b|mill)", s, re.I))
    head, comma, tail = token.rpartition(",")
    tail = tail.strip(".")
    if millions and comma and len(tail) >= 3 and val > 1000:
        # no vessel costs 26,625 million: the comma is the decimal point
        return float(f"{re.sub(r'[.,]', '', head)}.{tail}")
    if not millions and val >= 1000:
        # printed in plain dollars, e.g. 'around $ 470,000' (JIN LONG 7, 2021 W46)
        return val / 1_000_000.0
    return val


def parse_price_per_ldt(p_str: Any) -> Optional[float]:
    """Scrap price in $/LDT - the same mixed separator applies.

    Measured: intermodal 2024 W46 p5 'SK SUMMIT ... GAS TANKER 469,5/ldt' is
    469.5 $/LDT; the old parser stored 4695.0 (5 rows, 2 documents). $/LDT is
    always printed in whole dollars, so the 3-digit case stays thousands.
    """
    if not p_str:
        return None
    m = re.search(r"\d[\d.,]*", str(p_str))
    return read_dual_separator_number(m.group(0)) if m else None


def unpack_compressed_row(cells: List[str]) -> Optional[List[List[str]]]:
    """
    If cells in a row contain multiple <br/> tags representing multi-row compression,
    unpack them into multiple distinct rows.
    """
    col_items = []
    for c in cells:
        items = [re.sub(r"<.*?>", "", s).strip() for s in re.split(r"<br\s*/?>", c, flags=re.I) if s.strip()]
        col_items.append(items)
    counts = [len(items) for items in col_items if len(items) > 3]
    if not counts:
        return None
    from collections import Counter
    mode_len = Counter(counts).most_common(1)[0][0]
    unpacked_rows = []
    for i in range(mode_len):
        row = []
        for items in col_items:
            if len(items) == mode_len:
                row.append(items[i])
            elif len(items) == mode_len + 2:
                row.append(items[i + 2])
            elif len(items) == mode_len + 1:
                row.append(items[i + 1])
            elif len(items) == 1:
                row.append(items[0])
            elif i < len(items):
                row.append(items[i])
            else:
                row.append("")
        unpacked_rows.append(row)
    return unpacked_rows


def extract_grids(raw_text: str) -> List[List[List[str]]]:
    raw_text = re.sub(r'(<tr[^>]*>\s*)td>', r'\1<td>', raw_text, flags=re.I)
    # Some pages lose the opening '<' on EVERY cell, not just the first: the whole data
    # block then parses as one cell per row and the values are silently lost (measured:
    # 101 such lines in intermodal_2021_W38, 14 in 2021_W30). Repair them all.
    raw_text = re.sub(r'(?m)^(\s*)td>', r'\1<td>', raw_text)
    grids: List[List[List[str]]] = []
    soup = BeautifulSoup(raw_text, "html.parser")
    for table in soup.find_all("table"):
        grid: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [clean_cell(td.get_text()) for td in tr.find_all(["th", "td"])]
            if not cells and "td>" in tr.get_text():
                cells = [clean_cell(re.sub(r"^td>", "", x.strip())) for x in tr.get_text().splitlines() if x.strip()]
            if any(c for c in cells):
                grid.append(cells)
        if grid:
            grids.append(grid)

    clean_text = re.sub(r"<table[\s\S]*?</table>", "", raw_text, flags=re.I)
    for b in clean_text.split("\n\n"):
        if "|" in b and ("| ---" in b or "|:---" in b or "|---" in b or "| -" in b or ("|" in b and "\n|" in b)):
            lines = [l.strip() for l in b.splitlines() if l.strip().startswith("|")]
            grid = []
            for ln in lines:
                if re.match(r"\|(?:\s*[-:]+\s*\|)+", ln):
                    continue
                if "<br" in ln.lower() and ("MEG-SPORE" in ln or "Routes" in ln or "Newcastlemax" in ln or "Capesize" in ln):
                    raw_cells = [c.strip() for c in ln.strip("|").split("|")]
                    unpacked = unpack_compressed_row(raw_cells)
                    if unpacked:
                        if "MEG-SPORE" in ln or "Routes" in ln:
                            grid.append(["Vessel", "Routes", "WS points", "$/day", "WS points", "$/day", "Change", "Avg1", "Avg2"])
                        else:
                            grid.append(["Vessel", "Size", "Current", "Previous", "Change", "YTD_H", "YTD_L", "5Y_H", "5Y_L"])
                        for ur in unpacked:
                            grid.append(ur)
                        continue
                cells = [clean_cell(c) for c in ln.strip("|").split("|")]
                if any(c for c in cells):
                    grid.append(cells)
            if grid:
                grids.append(grid)
    return grids


# ---------------------------------------------------------------------------
# Table Parsers (Cover-to-Cover)
# ---------------------------------------------------------------------------
# Indicative Newbuilding Prices: a size cell is "205k" / "82K"; a fused cell is
# "Newcastlemax 205k". A fused header artefact ("VesselBulkersTankersGas",
# "SizeNewcastlemax") is not a vessel and must never be published.
_NB_SIZE_RX = re.compile(r"^\d+(?:\.\d+)?\s*[kK]$")
_NB_FUSED_SIZE_RX = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?\s*[kK])$")
_NB_FUSED_RX = re.compile(r"vessel|bulkers|tankers|^size|markets|^current$|^previous$|^change$", re.I)
# The section label is NOT reliable: in intermodal_2021_W38 the publisher prints the
# "Bulkers"/"Tankers"/"Gas" rows AFTER the data rows, so a positional sector labelled all
# 13 rows "Bulkers". Derive the sector from the vessel name itself and fall back to the
# label only for a name the map does not know.
_NB_SECTOR_BY_NAME = (
    ("Newcastlemax", "Bulkers"), ("Capesize", "Bulkers"), ("Kamsarmax", "Bulkers"),
    ("Ultramax", "Bulkers"), ("Handysize", "Bulkers"),
    ("VLCC", "Tankers"), ("Suezmax", "Tankers"), ("Aframax", "Tankers"), ("MR", "Tankers"),
    ("LNG", "Gas"), ("LGC", "Gas"), ("MGC", "Gas"), ("SGC", "Gas"),
)


def _nb_sector(v_type: str) -> str:
    for name, sec in _NB_SECTOR_BY_NAME:
        if v_type == name or v_type.startswith(name + " "):
            return sec
    return ""
_NUM_ONLY = re.compile(r"^-?\d+(?:\.\d+)?$")
_MISSING = re.compile(r"^#(?:DIV/0!|N/A|REF!|VALUE!|NAME\?|NULL!|NUM!)$", re.I)


def parse_indicative_row(row: List[str]):
    """Content-anchored parse of ONE "Indicative Market Values (5 yrs old)" row.

    LlamaParse emits this table in at least THREE shapes for the same publisher
    (all measured - docs/intermodal_indicative_verdict.md):

      A  name | size | cur | prev | pct | y1 | y2 | y3
      B  name | size | cur | pct  | y1  | y2 | y3     <- the prev-month cell was dropped
      C  ''   | name | size | cur | prev | pct | ...  <- a leading empty cell

    Position alone therefore cannot be trusted. Anchor on CONTENT: the +/-% cell
    is the only one carrying a '%', and the tail starts at the first cell that is
    a plain number OR a spreadsheet error token. Returns
    (vessel_class, cur, prev, pct, y1, y2, y3) or None.
    """
    cells = [str(c).strip() for c in row]
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    if len(cells) < 3:
        return None

    tail_start = next(
        (i for i, c in enumerate(cells) if _NUM_ONLY.match(c) or _MISSING.match(c)), None
    )
    pct_idx = next((i for i, c in enumerate(cells) if "%" in c), None)
    if tail_start is None or tail_start == 0:
        return None

    labels = [c for c in cells[:tail_start] if c]
    if not labels:
        return None
    v_class = " ".join(labels)

    if pct_idx is None:
        # No +/-% anywhere: the publisher printed a spreadsheet error instead
        # (measured: intermodal_2025_W27 bulker carries the literal '#DIV/0!'
        # in the PDF itself, for the current month AND the +/-%). The Jun-25 and
        # year values on that row ARE real, so map the tail by its known 6-slot
        # layout rather than dropping the row. A value not on the page stays
        # NULL - never 0.0 (parse_float('#DIV/0!') returns 0.0, which is how the
        # old parser published a $0m price).
        tail = cells[tail_start:]
        if len(tail) != 6:
            return None
        vals = [None if _MISSING.match(c) else parse_float(c) for c in tail]
        chg = "" if _MISSING.match(tail[2]) else tail[2]
        return (v_class, vals[0], vals[1], chg, vals[3], vals[4], vals[5])

    if pct_idx <= tail_start:
        return None

    monthly = [parse_float(c) for c in cells[tail_start:pct_idx]]
    if not monthly or monthly[0] is None:
        return None
    curr_p = monthly[0]
    prev_m = monthly[1] if len(monthly) > 1 else None

    chg = cells[pct_idx]
    yrs = [parse_float(c) for c in cells[pct_idx + 1: pct_idx + 4]]
    while len(yrs) < 3:
        yrs.append(None)
    return v_class, curr_p, prev_m, chg, yrs[0], yrs[1], yrs[2]


def parse_all_intermodal_tables(
    md_text: str,
    issue_date: str,
    report_week: int,
    source_file: str
) -> Dict[str, Any]:
    grids = extract_grids(md_text)

    tanker_spot: List[Dict[str, Any]] = []
    tc_rates: List[Dict[str, Any]] = []
    indicative_values: List[Dict[str, Any]] = []
    baltic_indices: List[Dict[str, Any]] = []
    currencies: List[Dict[str, Any]] = []

    sales_records: List[Dict[str, Any]] = []
    nb_prices: List[Dict[str, Any]] = []
    nb_orders: List[Dict[str, Any]] = []
    demo_prices: List[Dict[str, Any]] = []
    demo_sales: List[Dict[str, Any]] = []

    for grid in grids:
        if len(grid) < 2:
            continue
        hdr0 = [c.lower() for c in grid[0]]
        hdr_all = " ".join(" ".join(r) for r in grid[:3]).lower()
        hdr_any = [c.lower() for r in grid[:3] for c in r]
        grid_text = " ".join(" ".join(r) for r in grid).lower()

        # 1. Tanker Spot Rates (Page 2)
        if "routes" in hdr_all and ("ws" in hdr_all or "$/day" in hdr_all or "spot" in hdr_all):
            cur_vessel = ""
            for row in grid[1:]:
                if not row or len(row) < 3:
                    continue
                has_nums = any(re.search(r"\d", c) for c in row[2:6]) if len(row) > 2 else False
                if not has_nums:
                    continue
                v_col = row[0].strip()
                route = row[1].strip() if len(row) > 1 else ""
                if route.lower() == "routes":
                    continue
                if re.match(r"^routes\s*", route, re.I):
                    route = re.sub(r"^routes\s*", "", route, flags=re.I).strip()
                if any(x in v_col.lower() for x in ["meg-", "waf-", "med-", "bsea-", "baltic", "caribs", "ukc-", "ara-"]):
                    route = v_col
                    v_col = ""

                if not route or any(x in route.lower() for x in ["total", "average"]):
                    continue

                r_low = route.lower()
                if any(x in r_low for x in ["265k", "280k", "260k", "vlcc"]):
                    cur_vessel = "VLCC"
                elif any(x in r_low for x in ["130k", "140k", "suezmax"]):
                    cur_vessel = "Suezmax"
                elif any(x in r_low for x in ["80k", "100k", "70k", "aframax"]):
                    cur_vessel = "Aframax"
                elif any(x in r_low for x in ["75k", "55k", "37k", "30k", "50k", "clean"]):
                    cur_vessel = "Clean"
                elif v_col and not any(x in v_col.lower() for x in ["vessel", "clean", "dirty", "total"]):
                    cur_vessel = v_col

                ws_curr = parse_float(row[2]) if len(row) > 2 else None
                tce_curr = parse_float(row[3]) if len(row) > 3 else None
                ws_prev = parse_float(row[4]) if len(row) > 4 else None
                tce_prev = parse_float(row[5]) if len(row) > 5 else None
                chg = row[6].strip() if len(row) > 6 else ""
                avg_y1 = parse_float(row[7]) if len(row) > 7 else None
                avg_y2 = parse_float(row[8]) if len(row) > 8 else None

                tanker_spot.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "vessel_class": cur_vessel or "Tanker",
                    "route": route,
                    "ws_points_current": ws_curr,
                    "tce_usd_day_current": tce_curr,
                    "ws_points_prev": ws_prev,
                    "tce_usd_day_prev": tce_prev,
                    "change_pct": chg,
                    "avg_prev_year_1": avg_y1,
                    "avg_prev_year_2": avg_y2,
                    "source_file": source_file
                })

        # 2. TC Rates (Tankers & Dry Bulk)
        elif ("diff" in hdr_all or "±%" in hdr_all or "+/-%" in hdr_all or "%" in hdr_all) and any("1yr" in " ".join(r).lower() or "3yr" in " ".join(r).lower() for r in grid):
            is_dry = any(x in grid_text for x in ["capesize", "kamsarmax", "panamax 76k", "supramax", "handysize 32k"])
            sector = "Dry Bulk" if is_dry else "Tanker"

            cur_class = ""
            for row in grid[1:]:
                if not row or len(row) < 4:
                    continue
                if any(x in row[0].lower() for x in ["$/day", "diff", "±%", "+/-%", "202"]):
                    continue

                c0 = row[0].strip()
                c1 = row[1].strip() if len(row) > 1 else ""

                if c0 and not any(x in c0.lower() for x in ["1yr", "3yr", "tc"]):
                    cur_class = c0

                desc = c1 if c1 else c0
                if not any(x in desc.lower() for x in ["1yr", "3yr", "tc", "yr"]):
                    continue

                m_tenor = re.search(r"(\d+\s*(?:yr|y)\s*TC|\d+\s*(?:yr|y))", desc, re.I)
                tenor = m_tenor.group(1).upper() if m_tenor else desc

                size_part = re.sub(r"\s*\d+\s*(?:yr|y)\s*TC.*", "", desc, flags=re.I).strip()
                v_class = f"{cur_class} {size_part}".strip() if size_part and cur_class else (cur_class or size_part)

                curr_rate = parse_float(row[2]) if len(row) > 2 else None
                prev_rate = parse_float(row[3]) if len(row) > 3 else None
                chg = row[4].strip() if len(row) > 4 else ""
                diff = parse_float(row[5]) if len(row) > 5 else None
                y1 = parse_float(row[6]) if len(row) > 6 else None
                y2 = parse_float(row[7]) if len(row) > 7 else None

                tc_rates.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": sector,
                    "vessel_class": v_class,
                    "tenor": tenor,
                    "rate_usd_day_current": curr_rate,
                    "rate_usd_day_prev": prev_rate,
                    "change_pct": chg,
                    "diff_usd_day": diff,
                    "avg_prev_year_1": y1,
                    "avg_prev_year_2": y2,
                    "source_file": source_file
                })

        # 3. Indicative Market Values (5Y Old)
        elif ("5yr" in hdr_all or "5 yr" in hdr_all or "5-year" in hdr_all) and "avg" in hdr_all:
            is_dry = any(x in grid_text for x in ["capesize", "kamsarmax", "ultramax", "handysize 37k"])

            for row in grid[1:]:
                if not row or len(row) < 4:
                    continue
                if any("vessel" in c.lower() for c in row):
                    continue

                parsed_row = parse_indicative_row(row)
                if not parsed_row:
                    continue
                v_class, curr_p, prev_m, chg, y1, y2, y3 = parsed_row

                nm = v_class.lower()
                if any(x in nm for x in ("capesize", "kamsarmax", "ultramax", "handysize", "newcastlemax")):
                    sector = "Bulker"
                elif any(x in nm for x in ("vlcc", "suezmax", "aframax", "lr1", "mr ", "dh")):
                    sector = "Tanker"
                else:
                    sector = "Bulker" if is_dry else "Tanker"

                indicative_values.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": sector,
                    "vessel_class": v_class,
                    "age_profile": "5Y",
                    "price_usd_m_current": curr_p,
                    "price_usd_m_prev_month": prev_m,
                    "change_pct": chg,
                    "avg_prev_year_1": y1,
                    "avg_prev_year_2": y2,
                    "avg_prev_year_3": y3,
                    "source_file": source_file
                })

        # 4. Baltic Indices (Page 3)
        elif ("point diff" in hdr_all or "diff" in hdr_all) and any(x in grid_text for x in ["bdi", "bci", "bpi", "bsi"]):
            for row in grid[1:]:
                if not row or len(row) < 6:
                    continue
                name = row[0].strip()
                if name not in ("BDI", "BCI", "BPI", "BSI", "BHSI"):
                    continue
                idx_curr = parse_float(row[1])
                tce_curr = parse_float(row[2]) if row[2].strip() else None
                idx_prev = parse_float(row[3])
                tce_prev = parse_float(row[4]) if row[4].strip() else None
                pt_diff = parse_float(row[5])
                chg = row[6].strip() if len(row) > 6 else ""
                y1 = parse_float(row[7]) if len(row) > 7 else None
                y2 = parse_float(row[8]) if len(row) > 8 else None

                baltic_indices.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "index_name": name,
                    "index_current": idx_curr,
                    "tce_usd_day_current": tce_curr,
                    "index_prev": idx_prev,
                    "tce_usd_day_prev": tce_prev,
                    "point_diff": pt_diff,
                    "change_pct": chg,
                    "avg_prev_year_1": y1,
                    "avg_prev_year_2": y2,
                    "source_file": source_file
                })

        # 5. Demolition Currencies (Page 6)
        elif any("usd/bdt" in " ".join(r).lower() for r in grid):
            for row in grid[1:]:
                if not row or len(row) < 3:
                    continue
                mkt = row[0].strip()
                if not mkt.startswith("USD/"):
                    continue
                rate_curr = parse_float(row[1])
                rate_prev = parse_float(row[2])
                chg = row[3].strip() if len(row) > 3 else ""
                ytd_h = parse_float(row[4]) if len(row) > 4 else None

                currencies.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "market_currency": mkt,
                    "rate_current": rate_curr,
                    "rate_prev_week": rate_prev,
                    "change_pct": chg,
                    "ytd_high": ytd_h,
                    "source_file": source_file
                })

        # 6. Secondhand Sales (Page 4)
        elif any("name" in c for c in hdr0) and any(x in hdr_all for x in ("built", "dwt", "teu", "cbm", "m/e", "gear", "hull", "size")) and "ldt" not in hdr_all:
            sector_hint = None
            first_row_txt = " ".join(grid[0])
            for s in ("Tankers", "Bulk Carriers", "Containers", "Gas", "MPP/General Cargo", "General Cargo"):
                if s.lower() in first_row_txt.lower():
                    sector_hint = s
                    break

            col_map: Dict[str, int] = {}
            for idx, c in enumerate(hdr0):
                if "name" in c: col_map["name"] = idx
                elif "dwt" in c or "teu" in c or "cbm" in c:
                    # Cbm is a CAPACITY column, not a Dwt column: the Gas
                    # sub-table carries both (Dwt ... Cbm) and letting cbm
                    # overwrite dwt put the SS-due date into dwt on every gas
                    # row (measured 2026-10-01: GLOBAL SCORPIO dwt="-23").
                    # teu/cbm stay the fallback when no literal Dwt exists.
                    if "dwt" in c or "dwt" not in col_map:
                        col_map["dwt"] = idx
                elif "built" in c: col_map["built"] = idx
                elif "yard" in c: col_map["yard"] = idx
                elif re.fullmatch(r"m\s*[/&]?\s*e|me|engine", c.strip()):
                    # NOT a substring test: "comments" contains "me", so the
                    # old test mapped Comments to the engine column and the
                    # comments column was never populated (measured 2026-10-01:
                    # 0 of 3,358 rows carry comments; 824 rows carry comment
                    # text in m_e). Header spellings actually present in the
                    # 818 sales tables: "M/E" and "Comments" only.
                    col_map["me"] = idx
                elif "ss" in c: col_map["ss"] = idx
                elif "price" in c: col_map["price"] = idx
                elif "buyer" in c: col_map["buyers"] = idx
                elif "comment" in c: col_map["comments"] = idx
                elif "size" in c or "type" in c: col_map["size"] = idx
                elif "hull" in c or "gear" in c: col_map["gear_hull"] = idx

            for cols in grid[1:]:
                if len(cols) < len(grid[0]):
                    cols += [""] * (len(grid[0]) - len(cols))
                name = cols[col_map["name"]] if "name" in col_map and col_map["name"] < len(cols) else ""
                if not name or name.lower() in ("name", "total", "subtotal"):
                    continue
                # The Gas sub-table's HEADER OMITS the 'Built' label (11 data cells
                # under 10 labels), so every field from Yard rightward sits one column
                # early. Detected per ROW on content, never on geometry: no 'Built'
                # column exists and the cell under 'Yard' is a 4-digit year.
                # Ground truth, intermodal 2023 W22 p3:
                #   header: Type Name Dwt Yard M/E SS Cbm Price Buyers Comments
                #   data  : LPG GLOBAL SCORPIO 58,814 2003 HYUNDAI, S. Korea ...
                shift = 0
                _ycol = col_map.get("yard")
                if ("built" not in col_map and _ycol is not None and _ycol < len(cols)
                        and re.fullmatch(r"(19|20)\d\d", cols[_ycol].strip())):
                    shift = 1

                def _cell(key: str) -> str:
                    idx = col_map.get(key)
                    if idx is None:
                        # the omitted column is Built, whose value sits under Yard
                        return cols[_ycol] if (shift and key == "built" and _ycol is not None and _ycol < len(cols)) else ""
                    if shift and _ycol is not None and idx >= _ycol:
                        idx += 1
                    return cols[idx] if idx < len(cols) else ""

                v_type = _cell("size")
                _dwt_raw = _cell("dwt")
                dwt = parse_int(_dwt_raw) if _dwt_raw else None
                built = _cell("built")
                yard = _cell("yard")
                me = _cell("me")
                ss = _cell("ss")
                gear_hull = _cell("gear_hull")
                raw_price = _cell("price")
                buyers = _cell("buyers")
                comm = _cell("comments")

                sales_records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "section": sector_hint or "Secondhand Sales",
                    "vessel_name": name,
                    "vessel_type": v_type,
                    "dwt": dwt,
                    "year_built": built,
                    "yard": yard,
                    "m_e": me,
                    "ss_due": ss,
                    "gear_hull": gear_hull,
                    "price_raw": raw_price,
                    "price_usd_m": parse_price_mill(raw_price),
                    "buyers": buyers,
                    "comments": comm,
                    "source_file": source_file
                })

        # 7. Newbuilding Orders (Page 5)
        elif ((any("unit" in c for c in hdr0) or (any("type" in c for c in hdr0) and any("yard" in c for c in hdr0)))
              and any(x in hdr_all for x in ("yard", "buyer", "delivery", "price"))
              and "ldt" not in hdr_all):
            has_units_col = any("unit" in c for c in hdr0)
            for cols in grid[1:]:
                if len(cols) < 4:
                    continue
                if has_units_col:
                    units_val = cols[0].strip()
                    if not units_val or not re.search(r"\d", units_val):
                        continue
                    v_type = cols[1] if len(cols) > 1 else ""
                    size = cols[2] if len(cols) > 2 else ""
                    offset = 0
                    if len(cols) > 3 and cols[3].lower() in ("dwt", "teu", "cbm", "cbm/dwt"):
                        size = f"{size} {cols[3]}".strip()
                        offset = 1
                    yard = cols[3 + offset] if len(cols) > (3 + offset) else ""
                    deliv = cols[4 + offset] if len(cols) > (4 + offset) else ""
                    buyer = cols[5 + offset] if len(cols) > (5 + offset) else ""
                    raw_price = cols[6 + offset] if len(cols) > (6 + offset) else ""
                    comm = cols[7 + offset] if len(cols) > (7 + offset) else ""
                else:
                    v_type = cols[0].strip()
                    if not v_type or v_type.lower() in ("type", "total", "subtotal", "vessel"):
                        continue
                    units_val = "1"
                    size = cols[1] if len(cols) > 1 else ""
                    offset = 0
                    if len(cols) > 2 and cols[2].lower() in ("dwt", "teu", "cbm", "cbm/dwt"):
                        size = f"{size} {cols[2]}".strip()
                        offset = 1
                    yard = cols[2 + offset] if len(cols) > (2 + offset) else ""
                    deliv = cols[3 + offset] if len(cols) > (3 + offset) else ""
                    buyer = cols[4 + offset] if len(cols) > (4 + offset) else ""
                    raw_price = cols[5 + offset] if len(cols) > (5 + offset) else ""
                    comm = cols[6 + offset] if len(cols) > (6 + offset) else ""

                nb_orders.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "reported_order",
                    "units": units_val,
                    "sector": "",
                    "vessel_type": v_type,
                    "size": size,
                    "price_current_usd_m": parse_price_mill(raw_price),
                    "price_previous_usd_m": None,
                    "pct_change": "",
                    "yard": yard,
                    "delivery": deliv,
                    "buyer": buyer,
                    "price_raw": raw_price,
                    "comments": comm,
                    "source_file": source_file
                })

        # 8. Indicative Demolition Prices (Page 6)
        elif (any(x in hdr_all for x in ("market", "demolition")) or any("market" in c for c in hdr0)) and any(x in grid_text for x in ("bangladesh", "india", "pakistan")) and "usd/bdt" not in grid_text and "breaker" not in hdr_all and "dwt" not in hdr0:
            cur_sec = "Tanker"
            for cols in grid[1:]:
                if not cols:
                    continue
                c0 = cols[0].strip()
                c1 = cols[1].strip() if len(cols) > 1 else ""
                if "tanker" in c0.lower():
                    cur_sec = "Tanker"
                elif "dry" in c0.lower():
                    cur_sec = "Dry Bulk"

                country = None
                curr_p, prev_p, pct = None, None, ""
                if c0.lower() in ("bangladesh", "india", "pakistan", "turkey"):
                    country = c0
                    curr_p = parse_float(cols[1]) if len(cols) > 1 else None
                    prev_p = parse_float(cols[2]) if len(cols) > 2 else None
                    pct = cols[3].strip() if len(cols) > 3 else ""
                elif c1.lower() in ("bangladesh", "india", "pakistan", "turkey"):
                    country = c1
                    curr_p = parse_float(cols[2]) if len(cols) > 2 else None
                    prev_p = parse_float(cols[3]) if len(cols) > 3 else None
                    pct = cols[4].strip() if len(cols) > 4 else ""

                if not country or curr_p is None:
                    continue

                demo_prices.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "indicative_price",
                    "sector": cur_sec,
                    "country": country,
                    "price_current_usd_per_ldt": curr_p,
                    "price_previous_usd_per_ldt": prev_p,
                    "pct_change": pct,
                    "vessel_name": "",
                    "dwt": None,
                    "ldt": None,
                    "year_built": "",
                    "yard": "",
                    "vessel_type": "",
                    "price_raw": f"${curr_p}/ldt" if curr_p else "",
                    "price_usd_per_ldt": curr_p,
                    "buyer_breakers": "",
                    "comments": "",
                    "source_file": source_file
                })

        # 9. Indicative Newbuilding Prices (Page 5)
        elif (
            (any(x in c for x in ("vessel", "capesize", "newcastlemax", "bulkers", "tankers") for c in hdr_any) or "newbuilding" in hdr_all)
            and any(x in grid_text for x in ("newcastlemax", "capesize", "kamsarmax", "ultramax", "handysize", "vlcc", "suezmax"))
            and "5-year avg" not in hdr_all
            and "5 yrs old" not in grid_text
            and "5 yr" not in grid_text
            and "dh" not in hdr_all
            and "routes" not in hdr_all
            and "buyer" not in hdr_any[:5]
            and "yard" not in hdr_any[:5]
            and "breaker" not in hdr_all
            and "date" not in hdr_any[:3]
        ):
            cur_sec = "Bulkers"
            # --- content-anchored parse, fixed 2026-09-28 -------------------
            # The vessel NAME and the vessel SIZE print in one or two cells and the shape
            # changes between eras (all measured from the cached markdown):
            #   2021/2022  8 cells : name | size | cur | prev | +/-% | 2020 | 2019 | 2018
            #   2023_W18   8 cells : "Newcastlemax 205k" | cur | prev | +/-% | 2022 | 2021 | 2020
            #   2023_W20+ 13 cells : "Bulkers" fused with the row | name | size | cur | prev | +/-% | ...
            #   2023_W48+ 12 cells : name | size | cur | prev | +/-% | YTD H | YTD L | 5Y H | 5Y L | 2022 | 2021 | 2020
            # The previous version read cols[1..5] unconditionally. On the 8/12/13-cell shapes
            # that is a one-column left shift: it published the vessel SIZE as the price and the
            # printed +/-% as the previous price, on EVERY row (measured: 3,194 rows). Anchor on
            # the +/-% cell - the one landmark present in every era - then walk back to the
            # name/size cells.
            _SEC_LABELS = ("Bulkers", "Tankers", "Gas", "Containers")
            for cols in grid[1:]:
                if len(cols) < 3:
                    continue
                col0 = cols[0].strip()
                if col0 in _SEC_LABELS:
                    # the section label sometimes shares its row with that section's first data
                    # row (2023_W20: "Bulkers | Newcastlemax | 205k | 65.0 | ..."), so set the
                    # sector and keep parsing the row rather than skipping it.
                    cur_sec = col0
                pct_idx = next((i for i in range(1, len(cols)) if "%" in cols[i]), None)
                if pct_idx is not None and pct_idx >= 3:
                    cur_i, prev_i, pct_i = pct_idx - 2, pct_idx - 1, pct_idx
                else:
                    j = next((i for i in range(1, len(cols))
                              if _NB_SIZE_RX.match(cols[i].strip()) or _NB_FUSED_SIZE_RX.match(cols[i].strip())), None)
                    if j is None:
                        continue
                    cur_i, prev_i, pct_i = j + 1, j + 2, j + 3
                pre = [c.strip() for c in cols[:cur_i] if c.strip() and c.strip() not in _SEC_LABELS]
                if not pre:
                    continue
                last = pre[-1]
                if _NB_SIZE_RX.match(last):
                    size = last
                    v_type = pre[-2] if len(pre) >= 2 else ""
                else:
                    _mm = _NB_FUSED_SIZE_RX.match(last)
                    if _mm:
                        v_type, size = _mm.group(1).strip(), _mm.group(2).strip()
                    else:
                        v_type, size = last, ""
                if not v_type or _NB_FUSED_RX.search(v_type):
                    continue
                _row_sec = _nb_sector(v_type) or cur_sec
                curr_p = parse_float(cols[cur_i]) if cur_i < len(cols) else None
                prev_p = parse_float(cols[prev_i]) if prev_i < len(cols) else None
                pct = cols[pct_i].strip() if pct_i < len(cols) and "%" in cols[pct_i] else ""
                if curr_p is None or not (0 < curr_p < 2000):
                    continue
                # Self-check: the printed +/-% must reproduce from (cur-prev)/prev. LlamaParse
                # rotates cells across rows in a handful of issues; those rows are grid
                # corruption, and a wrong value is worse than a missing one.
                if prev_p and pct:
                    _pr = parse_float(pct)
                    if _pr is not None and abs((curr_p - prev_p) / prev_p * 100.0 - _pr) > max(0.2, 0.3 * abs(_pr)):
                        continue

                nb_prices.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "indicative_price",
                    "units": "",
                    "sector": _row_sec,
                    "vessel_type": v_type,
                    "size": size,
                    "price_current_usd_m": curr_p,
                    "price_previous_usd_m": prev_p,
                    "pct_change": pct,
                    "yard": "",
                    "delivery": "",
                    "buyer": "",
                    "price_raw": f"${curr_p}m" if curr_p else "",
                    "comments": "",
                    "source_file": source_file
                })

        # 10. Demolition Sales Fixtures (Page 6)
        elif any("name" in c for c in hdr0) and "ldt" in hdr_all and ("buyer" in hdr_all or "breaker" in hdr_all or "price" in hdr_all):
            col_map: Dict[str, int] = {}
            for idx, c in enumerate(hdr0):
                if "name" in c: col_map["name"] = idx
                elif "size" in c: col_map["size"] = idx
                elif "ldt" in c and "$/" not in c: col_map["ldt"] = idx
                elif "built" in c: col_map["built"] = idx
                elif "yard" in c: col_map["yard"] = idx
                elif "type" in c: col_map["type"] = idx
                elif "$/ldt" in c or "price" in c: col_map["price"] = idx
                elif "breaker" in c or "buyer" in c: col_map["breakers"] = idx
                elif "comment" in c: col_map["comments"] = idx

            for cols in grid[1:]:
                if len(cols) < len(grid[0]):
                    cols += [""] * (len(grid[0]) - len(cols))
                name = cols[col_map["name"]] if "name" in col_map and col_map["name"] < len(cols) else ""
                if not name or name.lower() in ("name", "total"):
                    continue
                dwt = parse_int(cols[col_map["size"]]) if "size" in col_map and col_map["size"] < len(cols) else None
                ldt = parse_int(cols[col_map["ldt"]]) if "ldt" in col_map and col_map["ldt"] < len(cols) else None
                built = cols[col_map["built"]] if "built" in col_map and col_map["built"] < len(cols) else ""
                yard = cols[col_map["yard"]] if "yard" in col_map and col_map["yard"] < len(cols) else ""
                v_type = cols[col_map["type"]] if "type" in col_map and col_map["type"] < len(cols) else ""
                raw_price = cols[col_map["price"]] if "price" in col_map and col_map["price"] < len(cols) else ""
                breakers = cols[col_map["breakers"]] if "breakers" in col_map and col_map["breakers"] < len(cols) else ""
                comm = cols[col_map["comments"]] if "comments" in col_map and col_map["comments"] < len(cols) else ""
                # $/LDT, not a millions figure: use the separator-aware reader
                # ("469,5/ldt" is 469.5, not 4,695 - measured on 2024 W46 p5).
                p_val = parse_price_per_ldt(raw_price)

                demo_sales.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "reported_sale",
                    "sector": "",
                    "country": breakers,
                    "price_current_usd_per_ldt": p_val,
                    "price_previous_usd_per_ldt": None,
                    "pct_change": "",
                    "vessel_name": name,
                    "dwt": dwt,
                    "ldt": ldt,
                    "year_built": built,
                    "yard": yard,
                    "vessel_type": v_type,
                    "price_raw": raw_price,
                    "price_usd_per_ldt": p_val,
                    "buyer_breakers": breakers,
                    "comments": comm,
                    "source_file": source_file
                })

    return {
        "tanker_spot": tanker_spot,
        "tc_rates": tc_rates,
        "indicative_values": indicative_values,
        "baltic_indices": baltic_indices,
        "currencies": currencies,
        "sales": sales_records,
        "nb_prices": nb_prices,
        "nb_orders": nb_orders,
        "demo_prices": demo_prices,
        "demo_sales": demo_sales
    }


# ---------------------------------------------------------------------------
# Single PDF LlamaParse Processor
# ---------------------------------------------------------------------------
def process_single_pdf(
    pdf_path: pathlib.Path,
    tier: str = "cost_effective",
    reparse_only: bool = False
) -> Dict[str, Any]:
    stem = pdf_path.stem
    out_md = OUT_FULL_DIR / f"{stem}.md"
    wk, issue_date = extract_report_metadata(pdf_path)

    full_text = ""
    is_cached = False
    pages_count = 8

    # 1. Check local cache
    if out_md.exists() and out_md.stat().st_size > 500:
        full_text = out_md.read_text(encoding="utf-8")
        is_cached = True
    elif not reparse_only:
        if quota_exceeded_event.is_set():
            raise RuntimeError("LlamaParse quota exceeded. Processing halted for key rotation.")

        try:
            parser = LlamaParse(
                api_key=API_KEY,
                result_type="markdown",
                tier=tier,
                version="latest",
                verbose=False
            )
            docs = parser.load_data(str(pdf_path))
            pages_count = len(docs)
            full_text = "\n\n--- PAGE BREAK ---\n\n".join(d.text for d in docs)
            if not full_text.strip():
                raise RuntimeError(f"LlamaParse returned empty result for {pdf_path.name}")
            OUT_FULL_DIR.mkdir(parents=True, exist_ok=True)
            out_md.write_text(full_text, encoding="utf-8")
        except Exception as e:
            err_str = str(e).lower()
            if any(x in err_str for x in ["quota", "limit", "429", "payment", "credits"]):
                quota_exceeded_event.set()
                print(f"\n[ALERT] Quota limit encountered on {pdf_path.name}: {e}")
            raise e

    # 2. Extract tables across all pages
    parsed = parse_all_intermodal_tables(full_text, issue_date, wk, pdf_path.name)

    # 3. Write / update sidecars
    # 3. Write / update sidecars (year-partitioned)
    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    dest_dir = OUT_MD_DIR / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = dest_dir / f"{stem}.tables.json"
    sidecar_data = {
        "issue_date": issue_date,
        "report_week": wk,
        "source_file": pdf_path.name,
        "stem": stem,
        "tables": {
            "tanker_spot_rates": parsed["tanker_spot"],
            "tc_rates": parsed["tc_rates"],
            "indicative_market_values": parsed["indicative_values"],
            "baltic_dry_indices": parsed["baltic_indices"],
            "demolition_currencies": parsed["currencies"],
            "secondhand_sales": parsed["sales"],
            "indicative_newbuilding": parsed["nb_prices"],
            "newbuilding_orders": parsed["nb_orders"],
            "indicative_demolition": parsed["demo_prices"],
            "demolition_sales": parsed["demo_sales"]
        }
    }
    sidecar_path.write_text(json.dumps(sidecar_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update cover-to-cover md in data/extracted/md/intermodal/<year>/<stem>.md
    dest_md = dest_dir / f"{stem}.md"
    dest_md.write_text(full_text, encoding="utf-8")

    return {
        "stem": stem,
        "status": "cached" if is_cached else "ok",
        "bytes": len(full_text),
        "pages": pages_count,
        "issue_date": issue_date,
        "report_week": wk,
        "parsed": parsed
    }


# ---------------------------------------------------------------------------
# Stack and Save Series CSVs
# ---------------------------------------------------------------------------
TANKER_SPOT_COLUMNS = [
    "issue_date", "report_week", "vessel_class", "route",
    "ws_points_current", "tce_usd_day_current", "ws_points_prev", "tce_usd_day_prev",
    "change_pct", "avg_prev_year_1", "avg_prev_year_2", "source_file"
]

TC_RATES_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_class", "tenor",
    "rate_usd_day_current", "rate_usd_day_prev", "change_pct", "diff_usd_day",
    "avg_prev_year_1", "avg_prev_year_2", "source_file"
]

INDICATIVE_VALUES_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_class", "age_profile",
    "price_usd_m_current", "price_usd_m_prev_month", "change_pct",
    "avg_prev_year_1", "avg_prev_year_2", "avg_prev_year_3", "source_file"
]

BALTIC_INDICES_COLUMNS = [
    "issue_date", "report_week", "index_name", "index_current", "tce_usd_day_current",
    "index_prev", "tce_usd_day_prev", "point_diff", "change_pct",
    "avg_prev_year_1", "avg_prev_year_2", "source_file"
]

CURRENCIES_COLUMNS = [
    "issue_date", "report_week", "market_currency", "rate_current",
    "rate_prev_week", "change_pct", "ytd_high", "source_file"
]

SALES_COLUMNS = [
    "issue_date", "report_week", "section", "vessel_name", "vessel_type",
    "dwt", "year_built", "yard", "m_e", "ss_due", "gear_hull",
    "price_raw", "price_usd_m", "buyers", "comments", "source_file"
]

NB_COLUMNS = [
    "issue_date", "report_week", "record_type", "sector", "vessel_type",
    "size", "price_current_usd_m", "price_previous_usd_m", "pct_change",
    "units", "yard", "delivery", "buyer", "price_raw", "comments", "source_file"
]

# The indicative-newbuilding-price slice of NB_COLUMNS. This file is the one the
# register counts as a deliverable; nothing wrote it before 2026-09-28 (the artefact
# existed but had no producer), so the runner now emits it from the same rows.
NB_PRICES_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_type", "size",
    "price_current_usd_m", "price_previous_usd_m", "pct_change", "source_file"
]

DEMO_COLUMNS = [
    "issue_date", "report_week", "record_type", "sector", "country",
    "price_current_usd_per_ldt", "price_previous_usd_per_ldt", "pct_change",
    "vessel_name", "dwt", "ldt", "year_built", "yard", "vessel_type",
    "price_raw", "price_usd_per_ldt", "buyer_breakers", "comments", "source_file"
]
# The three per-table splits below were previously written by a runner that no
# longer exists, so they went stale (mtime 2026-09-27) while the union files
# intermodal_demolition_series / intermodal_newbuilding_series were rebuilt.
# They are projections of the SAME sidecar tables, so they are written here to
# keep every register deliverable on one code path and one issue_date rule.
DEMO_SALES_COLUMNS = [
    "issue_date", "report_week", "vessel_name", "vessel_type", "dwt", "ldt",
    "year_built", "yard", "price_usd_per_ldt", "buyer_breakers", "comments", "source_file",
]
DEMO_PRICES_COLUMNS = [
    "issue_date", "report_week", "sector", "country", "price_current_usd_per_ldt",
    "price_previous_usd_per_ldt", "pct_change", "source_file",
]
NB_ORDERS_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_type", "units", "size", "yard",
    "delivery", "buyer", "price_raw", "comments", "source_file",
]



def write_series_csv(path: pathlib.Path, columns: List[str], rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort deterministically by issue_date, report_week, source_file
    sorted_rows = sorted(rows, key=lambda x: (str(x.get("issue_date", "")), int(x.get("report_week", 0))))
    # Drop EXACT duplicate rows. The cached LlamaParse markdown for some issues
    # contains the same table twice (measured: intermodal_2024_W21 md carries the
    # tanker indicative table at byte 9014 and again at 12374), so the parser
    # faithfully emitted every row twice. A row identical in every column is
    # always a double count downstream. Measured 2026-09-28: 75 extras in
    # intermodal_indicative_values_series.csv, 48 in intermodal_tc_rates_series.csv,
    # 0 in the other six.
    seen = set()
    deduped = []
    for r in sorted_rows:
        k = tuple(str(r.get(c, "")) for c in columns)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    sorted_rows = deduped
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted_rows)


_PDF_NUM_CACHE: Dict[str, List[float]] = {}


def _pdf_number_stream(source_file: str) -> List[float]:
    """Numeric tokens of a report's PDF text layer, in reading order (cached)."""
    if source_file in _PDF_NUM_CACHE:
        return _PDF_NUM_CACHE[source_file]
    seq: List[float] = []
    try:
        matches = list(CORPUS_DIR.rglob(source_file))
        if matches:
            doc = pymupdf.open(matches[0])
            text = chr(10).join(pg.get_text() for pg in doc)
            for ln in text.splitlines():
                s = ln.strip()
                if re.match(r"^-?\d+(?:\.\d+)?$", s):
                    seq.append(float(s))
                else:
                    for m in re.finditer(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?![\w.])", s):
                        seq.append(float(m.group(1)))
    except Exception:
        seq = []
    _PDF_NUM_CACHE[source_file] = seq
    return seq


def recover_missing_prev_month(rows: List[Dict[str, Any]]) -> int:
    """Fill an empty prev-month value from the report's OWN text layer.

    LlamaParse dropped the prev-month cell on 14 rows (docs/intermodal_indicative_verdict.md).
    The value IS printed on the page, so recover it by anchoring on the values we
    already trust: search the PDF's numeric stream for
    [current, <one number>, pct, y1, y2, y3] and require EXACTLY ONE match in the
    whole document. No unique match -> leave it blank. A wrong value is worse
    than a missing one.
    """
    fixed = 0
    for r in rows:
        if r.get("price_usd_m_prev_month") not in (None, ""):
            continue
        cur = parse_float(r.get("price_usd_m_current"))
        chg = parse_float(r.get("change_pct"))
        ys = [parse_float(r.get("avg_prev_year_1")), parse_float(r.get("avg_prev_year_2")),
              parse_float(r.get("avg_prev_year_3"))]
        tail = [v for v in ys if v is not None]
        if cur is None or chg is None or len(tail) < 2:
            continue
        seq = _pdf_number_stream(str(r.get("source_file", "")))
        if not seq:
            continue
        pattern = [cur, None, chg] + ys
        cands = []
        n = len(pattern)
        for i in range(len(seq) - n + 1):
            win = seq[i:i + n]
            if all(p is None or abs(p - w) < 1e-9 for p, w in zip(pattern, win)):
                cands.append(win[1])
        if len(cands) == 1:
            r["price_usd_m_prev_month"] = cands[0]
            fixed += 1
    return fixed


def recover_nb_previous(rows: List[Dict[str, Any]]) -> int:
    """Fill/correct the indicative-newbuilding `previous` price from the report's OWN text layer.

    LlamaParse dropped the previous cell on 7 rows that the PDF does print. The page prints
    cur, prev, +/-% consecutively, so anchor on [cur, <one number>, pct] and require EXACTLY
    ONE match in the document's numeric stream. No unique match -> leave the row alone; a
    wrong value is worse than a missing one. Same doctrine as recover_missing_prev_month().
    """
    fixed = 0
    for r in rows:
        if r.get("record_type") != "indicative_price":
            continue
        cur = parse_float(r.get("price_current_usd_m"))
        chg = parse_float(r.get("pct_change"))
        if cur is None or chg is None:
            continue
        seq = _pdf_number_stream(str(r.get("source_file", "")))
        if not seq:
            continue
        cands = [seq[i + 1] for i in range(len(seq) - 2)
                 if abs(seq[i] - cur) < 1e-9 and abs(seq[i + 2] - chg) < 1e-9]
        if len(cands) != 1:
            continue
        old = parse_float(r.get("price_previous_usd_m"))
        if old is None or abs(old - cands[0]) > 1e-9:
            r["price_previous_usd_m"] = cands[0]
            fixed += 1
    return fixed


def build_all_series_from_sidecars():
    """Aggregate all sidecars in data/extracted/md/intermodal into the 8 series CSVs."""
    _dup = byte_duplicate_stems()
    sidecar_files = sorted(OUT_MD_DIR.rglob("*.tables.json"))
    if _dup:
        _b = len(sidecar_files)
        sidecar_files = [sf for sf in sidecar_files if sf.name[: -len(".tables.json")] not in _dup]
        if len(sidecar_files) != _b:
            print(f"[dedup] skipped {_b - len(sidecar_files)} duplicate sidecar(s)")
    all_tanker_spot = []
    all_tc_rates = []
    all_ind_values = []
    all_baltic = []
    all_currencies = []
    all_sales = []
    all_nb = []
    all_demo = []
    all_demo_sales = []
    all_demo_prices = []
    all_nb_orders = []

    for sf in sidecar_files:
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            tbls = data.get("tables", {})
            all_tanker_spot.extend(tbls.get("tanker_spot_rates", []))
            all_tc_rates.extend(tbls.get("tc_rates", []))
            all_ind_values.extend(tbls.get("indicative_market_values", []))
            all_baltic.extend(tbls.get("baltic_dry_indices", []))
            all_currencies.extend(tbls.get("demolition_currencies", []))
            all_sales.extend(tbls.get("secondhand_sales", []))
            all_nb.extend(tbls.get("indicative_newbuilding", []) + tbls.get("newbuilding_orders", []))
            all_demo.extend(tbls.get("indicative_demolition", []) + tbls.get("demolition_sales", []))
            all_demo_sales.extend(tbls.get("demolition_sales", []))
            all_demo_prices.extend(tbls.get("indicative_demolition", []))
            all_nb_orders.extend(tbls.get("newbuilding_orders", []))
        except Exception as e:
            print(f"Error reading sidecar {sf.name}: {e}")

    write_series_csv(TANKER_SPOT_CSV, TANKER_SPOT_COLUMNS, all_tanker_spot)
    write_series_csv(TC_RATES_CSV, TC_RATES_COLUMNS, all_tc_rates)
    _fixed = recover_missing_prev_month(all_ind_values)
    print(f"  [recover] prev-month values filled from the PDF text layer: {_fixed}")
    write_series_csv(INDICATIVE_VALUES_CSV, INDICATIVE_VALUES_COLUMNS, all_ind_values)
    write_series_csv(BALTIC_INDICES_CSV, BALTIC_INDICES_COLUMNS, all_baltic)
    write_series_csv(CURRENCIES_CSV, CURRENCIES_COLUMNS, all_currencies)
    write_series_csv(SALES_SERIES_CSV, SALES_COLUMNS, all_sales)
    write_series_csv(NB_SERIES_CSV, NB_COLUMNS, all_nb)
    _nbfix = recover_nb_previous(all_nb)
    print(f"  [recover] newbuilding previous prices filled from the PDF text layer: {_nbfix}")
    write_series_csv(NB_PRICES_CSV, NB_PRICES_COLUMNS,
                    [r for r in all_nb if r.get("record_type") == "indicative_price"])
    write_series_csv(DEMO_SERIES_CSV, DEMO_COLUMNS, all_demo)
    write_series_csv(DEMO_SALES_CSV, DEMO_SALES_COLUMNS, all_demo_sales)
    write_series_csv(DEMO_PRICES_CSV, DEMO_PRICES_COLUMNS, all_demo_prices)
    write_series_csv(NB_ORDERS_CSV, NB_ORDERS_COLUMNS, all_nb_orders)

    print(f"\n[Stack Complete] Aggregated from {len(sidecar_files)} sidecars:")
    print(f"  intermodal_tanker_spot_series.csv:     {len(all_tanker_spot):,} rows")
    print(f"  intermodal_tc_rates_series.csv:        {len(all_tc_rates):,} rows")
    print(f"  intermodal_indicative_values_series.csv:{len(all_ind_values):,} rows")
    print(f"  intermodal_baltic_indices_series.csv:  {len(all_baltic):,} rows")
    print(f"  intermodal_currencies_series.csv:      {len(all_currencies):,} rows")
    print(f"  intermodal_sales_series.csv:           {len(all_sales):,} rows")
    print(f"  intermodal_newbuilding_series.csv:     {len(all_nb):,} rows")
    print(f"  intermodal_newbuilding_prices_series.csv: {sum(1 for r in all_nb if r.get('record_type') == 'indicative_price'):,} rows")
    print(f"  intermodal_demolition_series.csv:      {len(all_demo):,} rows")


# ---------------------------------------------------------------------------
# Main Execution CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Intermodal Full Cover-to-Cover Extraction Runner")
    parser.add_argument("--year", type=str, default=str(__import__("datetime").date.today().year), help="Year to process (e.g. '2026', '2025', or 'all')")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to process (0 for all)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads")
    parser.add_argument("--reparse-only", action="store_true", help="Reparse existing cached full markdowns without calling LlamaParse")
    parser.add_argument("--stack-only", action="store_true", help="Only rebuild stacked series CSVs from sidecars")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    args = parser.parse_args()

    OUT_FULL_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()

    if args.status:
        done_cnt = len(state.get("done", {}))
        fail_cnt = len(state.get("failed", {}))
        pages = state.get("pages_parsed", 0)
        credits_used = state.get("credits_estimated", 0)
        rem = INITIAL_CREDITS - credits_used
        print("Intermodal Full Cover-to-Cover Extraction Status:")
        print(f"  Reports Parsed:    {done_cnt}")
        print(f"  Reports Failed:    {fail_cnt}")
        print(f"  Pages Parsed:      {pages}")
        print(f"  Credits Estimated: {credits_used}")
        print(f"  Credits Remaining: ~{rem}")
        return

    if args.stack_only:
        build_all_series_from_sidecars()
        return

    # Find target PDFs
    dup_stems = byte_duplicate_stems()
    if args.year == "all":
        all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    else:
        all_pdfs = sorted((CORPUS_DIR / args.year).glob("*.pdf"))
    if dup_stems:
        before = len(all_pdfs)
        all_pdfs = [p for p in all_pdfs if p.stem not in dup_stems]
        if len(all_pdfs) != before:
            print(f"[dedup] skipped {before - len(all_pdfs)} byte-identical duplicate document(s): "
                  f"{sorted(p.stem for p in sorted(CORPUS_DIR.rglob('*.pdf')) if p.stem in dup_stems)}")

    if not all_pdfs:
        print(f"No PDFs found for year: {args.year}")
        return

    # If not reparse_only, filter by state
    if args.reparse_only:
        todo_pdfs = all_pdfs
    else:
        todo_pdfs = [p for p in all_pdfs if p.stem not in state.get("done", {})]

    if args.limit > 0:
        todo_pdfs = todo_pdfs[:args.limit]

    print(f"\n[Intermodal Full] Processing {len(todo_pdfs)} reports (year={args.year}, workers={args.workers}, reparse_only={args.reparse_only})...")
    t0 = time.time()
    ok_cnt = 0
    fail_cnt = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_pdf = {
            executor.submit(process_single_pdf, p, "cost_effective", args.reparse_only): p
            for p in todo_pdfs
        }
        for idx, future in enumerate(concurrent.futures.as_completed(future_to_pdf), 1):
            p = future_to_pdf[future]
            stem = p.stem
            try:
                res = future.result()
                pages_cnt = res.get("pages", 8)
                is_cached = res.get("status") == "cached"
                
                with state_lock:
                    state["done"][stem] = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "pages": pages_cnt,
                        "bytes": res.get("bytes", 0),
                        "cached": is_cached,
                        "tier": "cost_effective"
                    }
                    if not is_cached:
                        state["pages_parsed"] = state.get("pages_parsed", 0) + pages_cnt
                        cost = pages_cnt * CREDITS_PER_PAGE
                        state["credits_estimated"] = state.get("credits_estimated", 0) + cost
                        used_key2 = state.get("credits_used_active_key", 0) + cost
                        state["credits_used_active_key"] = used_key2
                        state["credits_remaining"] = INITIAL_CREDITS - used_key2
                    ok_cnt += 1

                print(f"  [{idx}/{len(todo_pdfs)}] {stem[:45]:<45} OK ({'cached' if is_cached else 'LlamaParse'}, pages={pages_cnt}, elapsed: {time.time()-t0:.1f}s)", flush=True)

            except Exception as e:
                with state_lock:
                    fail_cnt += 1
                    state["failed"][stem] = str(e)
                print(f"  [{idx}/{len(todo_pdfs)}] {stem[:45]:<45} FAILED: {type(e).__name__}: {e}", flush=True)

            if idx % 5 == 0 or idx == len(todo_pdfs):
                with state_lock:
                    save_state(state)

            if quota_exceeded_event.is_set():
                print("\n[STOPPING] Quota exceeded. Saving state and aborting remaining tasks.")
                break

    with state_lock:
        save_state(state)

    print(f"\n[Intermodal Full] Extraction batch complete: {ok_cnt} OK, {fail_cnt} failed in {time.time()-t0:.1f}s.")
    print("Rebuilding stacked series CSVs...")
    build_all_series_from_sidecars()


if __name__ == "__main__":
    main()
