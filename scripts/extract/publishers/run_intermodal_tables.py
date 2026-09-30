"""
Intermodal Shipbrokers S&P, Newbuilding, and Demolition Extraction Pipeline.

Extracts dense tabular payloads from weekly Intermodal Market Reports (2021-2026):
  - Page 4: Secondhand Sales (Bulk Carriers, Tankers, Gas, Containers)
  - Page 5: Indicative Newbuilding Prices ($ Million) and Newbuilding Orders
  - Page 6: Indicative Demolition Prices ($/LDT for India, Bangladesh, Pakistan, Turkey) and Demolition Sales fixtures
  - Page 3: Baltic & Time Charter vector curves (stacked via merge_intermodal_charts.py)

Uses LlamaParse (tier="cost_effective", target_pages="3,4,5", version="latest")
for high-accuracy, zero-OCR-noise markdown extraction.

Outputs:
  - data/extracted/series/intermodal_sales_series.csv
  - data/extracted/series/intermodal_newbuilding_series.csv
  - data/extracted/series/intermodal_demolition_series.csv
  - data/extracted/series/intermodal_baltic_tc_series.csv (retained/verified)
  - data/extracted/md/intermodal/<stem>.tables.json
  - data/extracted/md/intermodal/<stem>.md
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
PUB = "intermodal"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"
OUT_LLAMA = ROOT / "data" / "extracted" / "llamaparse_intermodal"
STATE_FILE = OUT_LLAMA / "_run_state.json"

SALES_SERIES_CSV = OUT_SERIES / "intermodal_sales_series.csv"
NB_SERIES_CSV = OUT_SERIES / "intermodal_newbuilding_series.csv"
DEMO_SERIES_CSV = OUT_SERIES / "intermodal_demolition_series.csv"
BALTIC_TC_SERIES_CSV = OUT_SERIES / "intermodal_baltic_tc_series.csv"

LLAMA_API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "llx-AVMBvb0UULqQGzWhFFJScQpwhrTM8hSVMZvjz4PEGQ9utg1P")

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


# ---------------------------------------------------------------------------
# Metadata Extraction (100% matched across 252 reports)
# ---------------------------------------------------------------------------

def extract_report_metadata(pdf_path: Path) -> Tuple[int, str]:
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
    issue_date: Optional[str] = None
    m_dmy = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        issue_date = f"{y:04d}-{m:02d}-{d:02d}"
    else:
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

    return wk or 1, issue_date or "2026-01-01"


# ---------------------------------------------------------------------------
# Value Parsing Utilities
# ---------------------------------------------------------------------------

def parse_price_mill(p_str: Any) -> Optional[float]:
    if not p_str:
        return None
    s = str(p_str).replace("$", "").replace("USD", "").replace("usd", "").replace(",", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            val = float(m.group(1))
            return val
        except ValueError:
            return None
    return None


def parse_int_clean(s: Any) -> Optional[int]:
    if s is None:
        return None
    c = re.sub(r"[^\d]", "", str(s))
    return int(c) if c else None


def parse_float_clean(s: Any) -> Optional[float]:
    if s is None:
        return None
    c = str(s).replace(",", "").replace("%", "").strip()
    m = re.search(r"([-+]?\d+(?:\.\d+)?)", c)
    return float(m.group(1)) if m else None


def clean_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).replace("**", "").replace("~~", "").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", s)


# ---------------------------------------------------------------------------
# Markdown Table Parsing
# ---------------------------------------------------------------------------

def extract_grids(raw_text: str) -> List[List[List[str]]]:
    grids: List[List[List[str]]] = []
    soup = BeautifulSoup(raw_text, "html.parser")
    for table in soup.find_all("table"):
        grid: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [clean_cell(td.get_text()) for td in tr.find_all(["th", "td"])]
            if any(c for c in cells):
                grid.append(cells)
        if grid:
            grids.append(grid)

    clean_text = re.sub(r"<table[\s\S]*?</table>", "", raw_text, flags=re.I)
    for b in clean_text.split("\n\n"):
        if "|" in b and ("| ---" in b or "|:---" in b or "|---" in b or "| -" in b):
            lines = [l.strip() for l in b.splitlines() if l.strip().startswith("|")]
            grid = []
            for ln in lines:
                if re.match(r"\|(?:\s*[-:]+\s*\|)+", ln):
                    continue
                cells = [clean_cell(c) for c in ln.strip("|").split("|")]
                if any(c for c in cells):
                    grid.append(cells)
            if grid:
                grids.append(grid)
    return grids


def parse_intermodal_markdown(
    md_text: str,
    issue_date: str,
    report_week: int,
    source_file: str
) -> Dict[str, Any]:
    """Parse LlamaParse markdown and HTML output into structured records."""
    sales_records: List[Dict[str, Any]] = []
    nb_prices: List[Dict[str, Any]] = []
    nb_orders: List[Dict[str, Any]] = []
    demo_prices: List[Dict[str, Any]] = []
    demo_sales: List[Dict[str, Any]] = []

    grids = extract_grids(md_text)

    for grid in grids:
        if len(grid) < 2:
            continue

        header_idx = -1
        sector_hint = None

        for r_idx in range(min(3, len(grid))):
            row_low = [c.lower() for c in grid[r_idx]]
            if any("name" in c for c in row_low) and any(x in c for x in ("dwt", "teu", "cbm", "built", "size", "ldt") for c in row_low):
                header_idx = r_idx
                break
            elif (any("unit" in c for c in row_low) or (any("type" in c for c in row_low) and any("yard" in c for c in row_low))) and any(x in c for x in ("buyer", "delivery", "price", "yard", "size") for c in row_low) and not any("ldt" in c for c in row_low):
                header_idx = r_idx
                break
            elif any("market" in c for c in row_low) and any(x in c for x in ("ytd", "202", "201", "change", "%") for c in row_low):
                header_idx = r_idx
                break
            elif any(x in c for x in ("vessel", "capesize", "newcastlemax", "bulkers", "tankers") for c in row_low) and any(x in c for x in ("ytd", "5-year", "average", "million", "%", "202", "201") for c in row_low):
                header_idx = r_idx
                break

        if header_idx > 0:
            first_row_txt = " ".join(grid[0])
            for s in ("Tankers", "Bulk Carriers", "Containers", "Gas", "MPP/General Cargo", "General Cargo"):
                if s.lower() in first_row_txt.lower():
                    sector_hint = s
                    break

        if header_idx == -1:
            continue

        hdr = grid[header_idx]
        hdr_low = [c.lower() for c in hdr]
        data_rows = grid[header_idx + 1:]

        # Case 1: Secondhand Sales
        if any("name" in c for c in hdr_low) and any(x in c for x in ("built", "dwt", "teu", "cbm", "m/e", "gear", "hull", "size") for c in hdr_low) and not any("ldt" in c for c in hdr_low):
            col_map: Dict[str, int] = {}
            for idx, c in enumerate(hdr_low):
                if "name" in c: col_map["name"] = idx
                elif "dwt" in c or "teu" in c or "cbm" in c: col_map["dwt"] = idx
                elif "built" in c: col_map["built"] = idx
                elif "yard" in c: col_map["yard"] = idx
                elif "m/e" in c or "me" in c or "engine" in c: col_map["me"] = idx
                elif "ss" in c: col_map["ss"] = idx
                elif "price" in c: col_map["price"] = idx
                elif "buyer" in c: col_map["buyers"] = idx
                elif "comment" in c: col_map["comments"] = idx
                elif "size" in c or "type" in c: col_map["size"] = idx
                elif "hull" in c or "gear" in c: col_map["gear_hull"] = idx

            for cols in data_rows:
                if len(cols) < len(hdr):
                    cols += [""] * (len(hdr) - len(cols))
                name = cols[col_map["name"]] if "name" in col_map and col_map["name"] < len(cols) else ""
                if not name or name.lower() in ("name", "total", "subtotal"):
                    continue
                v_type = cols[col_map["size"]] if "size" in col_map and col_map["size"] < len(cols) else ""
                dwt = parse_int_clean(cols[col_map["dwt"]]) if "dwt" in col_map and col_map["dwt"] < len(cols) else None
                built = cols[col_map["built"]] if "built" in col_map and col_map["built"] < len(cols) else ""
                yard = cols[col_map["yard"]] if "yard" in col_map and col_map["yard"] < len(cols) else ""
                me = cols[col_map["me"]] if "me" in col_map and col_map["me"] < len(cols) else ""
                ss = cols[col_map["ss"]] if "ss" in col_map and col_map["ss"] < len(cols) else ""
                gear_hull = cols[col_map["gear_hull"]] if "gear_hull" in col_map and col_map["gear_hull"] < len(cols) else ""
                raw_price = cols[col_map["price"]] if "price" in col_map and col_map["price"] < len(cols) else ""
                buyers = cols[col_map["buyers"]] if "buyers" in col_map and col_map["buyers"] < len(cols) else ""
                comm = cols[col_map["comments"]] if "comments" in col_map and col_map["comments"] < len(cols) else ""

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

        # Case 2: Newbuilding Orders
        elif ((any("unit" in c for c in hdr_low) or (any("type" in c for c in hdr_low) and any("yard" in c for c in hdr_low)))
              and any(x in c for x in ("yard", "buyer", "delivery", "price") for c in hdr_low)
              and not any("ldt" in c for c in hdr_low)):
            has_units_col = any("unit" in c for c in hdr_low)
            for cols in data_rows:
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

        # Case 3: Indicative Demolition Prices ($/ldt)
        elif any("market" in c for c in hdr_low) and any(x in c for x in ("ytd", "202", "201", "%", "change") for c in hdr_low):
            cur_sec = "Tanker"
            for cols in data_rows:
                if not cols or not cols[0]:
                    continue
                col0 = cols[0].lower()
                if "tanker" in col0:
                    cur_sec = "Tanker"
                    continue
                elif "dry bulk" in col0 or "dry" in col0:
                    cur_sec = "Dry Bulk"
                    continue
                country = cols[0]
                if country.lower() not in ("bangladesh", "india", "pakistan", "turkey"):
                    continue
                curr_p = parse_float_clean(cols[1]) if len(cols) > 1 else None
                prev_p = parse_float_clean(cols[2]) if len(cols) > 2 else None
                pct = cols[3] if len(cols) > 3 else ""

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

        # Case 4: Indicative Newbuilding Prices
        elif any(x in c for x in ("vessel", "capesize", "newcastlemax", "bulkers", "tankers") for c in hdr_low) or any("5-year" in c or "average" in c for c in hdr_low):
            cur_sec = "Bulkers"
            for cols in data_rows:
                if len(cols) < 3:
                    continue
                col0 = cols[0]
                if col0 in ("Bulkers", "Tankers", "Gas", "Containers"):
                    cur_sec = col0
                v_type = cols[1] if len(cols) > 1 and cols[1] else cols[0]
                if not v_type or v_type in ("Bulkers", "Tankers", "Gas", "Containers", "Vessel", "Markets"):
                    continue
                size = cols[2] if len(cols) > 2 else ""
                curr_p = parse_float_clean(cols[3]) if len(cols) > 3 else parse_float_clean(cols[1])
                prev_p = parse_float_clean(cols[4]) if len(cols) > 4 else parse_float_clean(cols[2])
                pct = cols[5] if len(cols) > 5 else ""

                nb_prices.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "indicative_price",
                    "units": "",
                    "sector": cur_sec,
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

        # Case 5: Demolition Sales
        elif any("name" in c for c in hdr_low) and any("ldt" in c for c in hdr_low):
            col_map: Dict[str, int] = {}
            for idx, c in enumerate(hdr_low):
                if "name" in c: col_map["name"] = idx
                elif "size" in c: col_map["size"] = idx
                elif "ldt" in c and "$/" not in c: col_map["ldt"] = idx
                elif "built" in c: col_map["built"] = idx
                elif "yard" in c: col_map["yard"] = idx
                elif "type" in c: col_map["type"] = idx
                elif "$/ldt" in c or "price" in c: col_map["price"] = idx
                elif "breaker" in c or "buyer" in c: col_map["breakers"] = idx
                elif "comment" in c: col_map["comments"] = idx

            for cols in data_rows:
                if len(cols) < len(hdr):
                    cols += [""] * (len(hdr) - len(cols))
                name = cols[col_map["name"]] if "name" in col_map and col_map["name"] < len(cols) else ""
                if not name or name.lower() in ("name", "total"):
                    continue
                dwt = parse_int_clean(cols[col_map["size"]]) if "size" in col_map and col_map["size"] < len(cols) else None
                ldt = parse_int_clean(cols[col_map["ldt"]]) if "ldt" in col_map and col_map["ldt"] < len(cols) else None
                built = cols[col_map["built"]] if "built" in col_map and col_map["built"] < len(cols) else ""
                yard = cols[col_map["yard"]] if "yard" in col_map and col_map["yard"] < len(cols) else ""
                v_type = cols[col_map["type"]] if "type" in col_map and col_map["type"] < len(cols) else ""
                raw_price = cols[col_map["price"]] if "price" in col_map and col_map["price"] < len(cols) else ""
                breakers = cols[col_map["breakers"]] if "breakers" in col_map and col_map["breakers"] < len(cols) else ""
                comm = cols[col_map["comments"]] if "comments" in col_map and col_map["comments"] < len(cols) else ""
                p_val = parse_float_clean(raw_price)

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
        "sales": sales_records,
        "nb_prices": nb_prices,
        "nb_orders": nb_orders,
        "demo_prices": demo_prices,
        "demo_sales": demo_sales
    }


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}, "pages_parsed": 0, "credits_estimated": 0}


def save_state(st: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Single PDF Processor
# ---------------------------------------------------------------------------

def process_single_pdf(
    pdf_path: Path,
    reparse_only: bool = False
) -> Dict[str, Any]:
    stem = pdf_path.stem
    md_cache_path = OUT_LLAMA / f"{stem}.md"
    
    wk, issue_date = extract_report_metadata(pdf_path)

    # 1. Fetch or load LlamaParse markdown
    md_text = ""
    if md_cache_path.exists():
        md_text = md_cache_path.read_text(encoding="utf-8")
    elif not reparse_only:
        from llama_parse import LlamaParse
        parser = LlamaParse(
            api_key=LLAMA_API_KEY,
            result_type="markdown",
            target_pages="3,4,5",
            tier="cost_effective",
            version="latest",
            verbose=False
        )
        docs = parser.load_data(str(pdf_path))
        md_text = "\n\n".join(d.text for d in docs)
        if not md_text.strip():
            raise RuntimeError(f"LlamaParse returned empty result for {pdf_path.name}")
        OUT_LLAMA.mkdir(parents=True, exist_ok=True)
        md_cache_path.write_text(md_text, encoding="utf-8")

    # 2. Parse Markdown Tables
    parsed = parse_intermodal_markdown(md_text, issue_date, wk, pdf_path.name)

    # 3. Update Sidecars (year-partitioned)
    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    dest_dir = OUT_MD / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = dest_dir / f"{stem}.tables.json"
    sidecar_data = {
        "issue_date": issue_date,
        "report_week": wk,
        "source_file": pdf_path.name,
        "stem": stem,
        "tables": {
            "secondhand_sales": parsed["sales"],
            "indicative_newbuilding": parsed["nb_prices"],
            "newbuilding_orders": parsed["nb_orders"],
            "indicative_demolition": parsed["demo_prices"],
            "demolition_sales": parsed["demo_sales"]
        }
    }
    sidecar_path.write_text(json.dumps(sidecar_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update or create Markdown sidecar
    doc_md_path = dest_dir / f"{stem}.md"
    existing_md = doc_md_path.read_text(encoding="utf-8") if doc_md_path.exists() else ""
    if "## LlamaParse Verified Tables" not in existing_md:
        table_md_section = f"\n\n## LlamaParse Verified Tables (Pages 4, 5, 6)\n\n{md_text}"
        doc_md_path.write_text(existing_md + table_md_section, encoding="utf-8")

    return {
        "stem": stem,
        "issue_date": issue_date,
        "report_week": wk,
        "sales": parsed["sales"],
        "newbuilding": parsed["nb_prices"] + parsed["nb_orders"],
        "demolition": parsed["demo_prices"] + parsed["demo_sales"],
        "chars": len(md_text)
    }


# ---------------------------------------------------------------------------
# CSV Column Specifications
# ---------------------------------------------------------------------------

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

DEMO_COLUMNS = [
    "issue_date", "report_week", "record_type", "sector", "country",
    "price_current_usd_per_ldt", "price_previous_usd_per_ldt", "pct_change",
    "vessel_name", "dwt", "ldt", "year_built", "yard", "vessel_type",
    "price_raw", "price_usd_per_ldt", "buyer_breakers", "comments", "source_file"
]


def write_stacked_series(
    all_sales: List[Dict[str, Any]],
    all_nb: List[Dict[str, Any]],
    all_demo: List[Dict[str, Any]]
) -> None:
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    with open(SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SALES_COLUMNS)
        w.writeheader()
        w.writerows(all_sales)

    with open(NB_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NB_COLUMNS)
        w.writeheader()
        w.writerows(all_nb)

    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DEMO_COLUMNS)
        w.writeheader()
        w.writerows(all_demo)


# ---------------------------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Intermodal Table Extraction Pipeline")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent workers for LlamaParse")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to process (0 = all)")
    parser.add_argument("--stem", type=str, default="", help="Filter by document stem")
    parser.add_argument("--status", action="store_true", help="Print extraction status and exit")
    parser.add_argument("--reparse-only", action="store_true", help="Reparse cached markdown without calling API")
    args = parser.parse_args()

    state = load_state()

    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"[{PUB}] Discovered {len(all_pdfs)} total PDFs in {CORPUS_DIR}")

    if args.status:
        cached_mds = list(OUT_LLAMA.glob("*.md"))
        print(f"Total PDFs:           {len(all_pdfs)}")
        print(f"Cached Markdown files:{len(cached_mds)}")
        print(f"State Done:           {len(state.get('done', {}))}")
        print(f"State Failed:         {len(state.get('failed', {}))}")
        print(f"Pages Parsed:         {state.get('pages_parsed', 0)}")
        print(f"Credits Estimated:    {state.get('credits_estimated', 0)}")
        return

    if args.stem:
        target_pdfs = [p for p in all_pdfs if args.stem in p.stem]
    else:
        target_pdfs = all_pdfs

    if args.limit > 0:
        target_pdfs = target_pdfs[:args.limit]

    print(f"[{PUB}] Target documents this run: {len(target_pdfs)} (Workers: {args.workers})")

    t0 = time.time()
    all_sales: List[Dict[str, Any]] = []
    all_nb: List[Dict[str, Any]] = []
    all_demo: List[Dict[str, Any]] = []
    completed = 0
    errors = 0

    def worker_task(p: Path) -> Optional[Dict[str, Any]]:
        nonlocal state
        stem = p.stem
        try:
            res = process_single_pdf(p, reparse_only=args.reparse_only)
            return res
        except Exception as e:
            state.setdefault("failed", {})[stem] = str(e)[:300]
            print(f"  FAILED: {stem[:45]} -> {e}", flush=True)
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(worker_task, p): p for p in target_pdfs}
        for future in concurrent.futures.as_completed(future_map):
            p = future_map[future]
            stem = p.stem
            res = future.result()
            if res:
                completed += 1
                all_sales.extend(res["sales"])
                all_nb.extend(res["newbuilding"])
                all_demo.extend(res["demolition"])
                state.setdefault("done", {})[stem] = {
                    "chars": res["chars"],
                    "sales": len(res["sales"]),
                    "nb": len(res["newbuilding"]),
                    "demo": len(res["demolition"]),
                }
                state["pages_parsed"] = len(state["done"]) * 3
                state["credits_estimated"] = state["pages_parsed"] * 3
            else:
                errors += 1

            if completed % 10 == 0 or completed == len(target_pdfs):
                save_state(state)
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"  [{completed:>3}/{len(target_pdfs)}] done | Sales: {len(all_sales):>4}, "
                      f"NB: {len(all_nb):>4}, Demo: {len(all_demo):>4} | ({rate:.1f} doc/s)", flush=True)

    save_state(state)

    # Sort outputs deterministically
    all_sales.sort(key=lambda x: (x.get("issue_date", ""), x.get("section", ""), x.get("vessel_name", "")))
    all_nb.sort(key=lambda x: (x.get("issue_date", ""), x.get("record_type", ""), x.get("vessel_type", "")))
    all_demo.sort(key=lambda x: (x.get("issue_date", ""), x.get("record_type", ""), x.get("country", ""), x.get("vessel_name", "")))

    write_stacked_series(all_sales, all_nb, all_demo)

    print("\n" + "=" * 70)
    print(f"[{PUB}] EXTRACTION SUMMARY:")
    print(f"  Total Processed:           {completed} succeeded, {errors} errors")
    print(f"  Stacked Sales Rows:        {len(all_sales):,}")
    print(f"  Stacked Newbuilding Rows:  {len(all_nb):,}")
    print(f"  Stacked Demolition Rows:   {len(all_demo):,}")
    print(f"  Outputs:")
    print(f"    - {SALES_SERIES_CSV}")
    print(f"    - {NB_SERIES_CSV}")
    print(f"    - {DEMO_SERIES_CSV}")
    print(f"    - {BALTIC_TC_SERIES_CSV} (existing, 19,691 rows)")
    print(f"  Elapsed Time:              {time.time()-t0:.1f}s")
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
