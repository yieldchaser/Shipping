"""Clarksons Platou Hellas World-Class S&P & Market Intelligence Extraction Pipeline.

Cover-to-cover extraction of Clarksons Platou Hellas S&P Weekly Bulletins spanning 2021 to 2026:
- 165 unique weekly reports deduplicated by SHA256 and canonical issue date.
- 100% LlamaParse markdown caching with multi-layout parser supporting:
  1. GitHub Flavored Markdown pipe tables
  2. HTML <table> structures
  3. Space-aligned columnar tables
  4. Vertically stacked line-by-line format
- Precision extraction of:
  1. Secondhand Sales (Bulkers, Tankers, Gas, Containers) with clean vessel name,
     accurate segment classification, numeric price + raw price qualifier, engine specs,
     BWTS/Scrubber flags, survey due dates, buyer, auction and en-bloc tags.
  2. Desk Talk & Market Commentary (General, Dry Cargo, Tanker, Newbuilding, Recycling).
  3. Demolition / Recycling Reported Sales.
  4. Baltic Dry Indices, Foreign Exchange (EUR/USD), and Bunker Prices.
- Generates:
  - data/extracted/md/hellenic/shipbuilding/clarksons/<year>/<stem>.md
  - data/extracted/md/hellenic/shipbuilding/clarksons/<year>/<stem>.tables.json
  - data/extracted/series/clarksons_snp_sales_series.csv
  - data/extracted/series/clarksons_demolition_sales_series.csv
  - data/extracted/series/clarksons_macro_series.csv
  - data/extracted/series/clarksons_desk_talk_series.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ClarksonsHellas")

ROOT = Path(__file__).resolve().parents[3]
PDF_ROOT = ROOT / "corpus" / "02-hellenic" / "shipbuilding" / "pdfs"
CACHE_DIR = ROOT / "data" / "extracted" / "cache_clarksons_hellas"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "shipbuilding" / "clarksons"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)


def clean_num(val: Any) -> Optional[float]:
    """Clean and parse a floating point number safely."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def clean_int(val: Any) -> Optional[int]:
    """Clean and parse an integer safely."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    m = re.search(r"\d+", s)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            return None
    return None


def parse_price_usd_m(price_str: str) -> Tuple[Optional[float], str]:
    """Parse numeric price in USD Millions from raw string e.g. 'USD 25.02', 'USD 32.5 M', 'REGION 35.2 M'."""
    raw = str(price_str).strip()
    if not raw or raw in ["-", "N/A", "n/a", "U/D", "undisclosed"]:
        return None, raw
    # This publisher prints the European decimal comma in part of its rows and the
    # ISO period in the rest, in the SAME table. Ground truth read from the source
    # PDFs (positioned text) on 2026-10-01:
    #   'EMILIA 53,098 2002 OSHIMA 4 x 30 T USD 13,9 M CHINESE'        -> 13.9
    #   'ILMA 318,395 2012 HYUNDAI HI ... SS 09/30 USD 98,2 M S. KOREAN' -> 98.2
    # Commas that are part of a COMMENT (not the price) must not be touched:
    #   'USD 17.7 M (TC attached at 13,7k pd till July 23)'            -> 17.7
    # so the rule is applied to the first numeric token only, and only when the
    # digits after its comma are 1-2 (a decimal), never 3 (a thousands group).
    m_tok = re.search(r"\d[\d.,]*", raw)
    if m_tok:
        token = m_tok.group(0).rstrip(".,")
        if "," in token:
            head, tail = token.rsplit(",", 1)
            tail = tail.strip(".")
            if tail.isdigit() and len(tail) <= 2:
                head_digits = re.sub(r"[.,]", "", head)
                if head_digits:
                    return round(float(f"{head_digits}.{tail}"), 2), raw
        if "," in token:
            # reached only when the digits after the comma are NOT a 1-2 digit
            # fraction, i.e. a thousands group ('USD 291 M' has no comma at all;
            # '1,250' would come here) - drop the group separators
            digits = re.sub(r"[.,]", "", token)
            val = float(digits) if digits.isdigit() else None
        else:
            # a lone period is the decimal point: 'USD 10.5 M' stays 10.5
            try:
                val = float(token)
            except ValueError:
                val = None
        if val is None:
            return None, raw
        if val > 10000:
            val = round(val / 1_000_000, 2)
        return val, raw
    return None, raw


def classify_vessel_segment(sector: str, dwt: Optional[int]) -> str:
    """Classify vessel into standard commercial segment by sector and deadweight tonnage."""
    if not dwt:
        return "Unknown"
    sec = sector.lower()
    if "bulk" in sec or "dry" in sec:
        if dwt >= 120_000:
            return "Capesize"
        elif dwt >= 80_000:
            return "Kamsarmax"
        elif dwt >= 65_000:
            return "Panamax"
        elif dwt >= 60_000:
            return "Ultramax"
        elif dwt >= 40_000:
            return "Supramax"
        elif dwt >= 10_000:
            return "Handysize"
        else:
            return "Small Bulker"
    elif "tanker" in sec or "wet" in sec:
        if dwt >= 200_000:
            return "VLCC"
        elif dwt >= 120_000:
            return "Suezmax"
        elif dwt >= 80_000:
            return "Aframax / LR2"
        elif dwt >= 60_000:
            return "Panamax / LR1"
        elif dwt >= 25_000:
            return "MR / Handy"
        else:
            return "Small Tanker"
    elif "container" in sec:
        return "Container"
    elif "gas" in sec or "lpg" in sec or "lng" in sec:
        return "Gas Carrier"
    return "Specialized"


def parse_issue_date(pdf_name: str) -> Tuple[str, str, int]:
    """Extract standard ISO date (YYYY-MM-DD), year, and estimated report week."""
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", pdf_name)
    if m_iso:
        yyyy, mm, dd = m_iso.group(1), int(m_iso.group(2)), int(m_iso.group(3))
        dt = datetime(int(yyyy), mm, dd)
        return f"{yyyy}-{mm:02d}-{dd:02d}", yyyy, dt.isocalendar()[1]

    m1 = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", pdf_name)
    if m1:
        dd, mm, yyyy = int(m1.group(1)), int(m1.group(2)), m1.group(3)
        dt = datetime(int(yyyy), mm, dd)
        return f"{yyyy}-{mm:02d}-{dd:02d}", yyyy, dt.isocalendar()[1]

    return "2026-01-01", "2026", 1


def get_unique_clarksons_reports(pdf_root: Path) -> List[Path]:
    """Find all unique Clarksons PDF reports by SHA256 deduplication."""
    seen_hashes: Set[str] = set()
    unique_files: List[Path] = []
    
    all_files = sorted(pdf_root.rglob("*.pdf"), key=lambda f: (-len(f.name), f.name))
    for f in all_files:
        try:
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_files.append(f)
        except Exception:
            continue
            
    unique_files.sort(key=lambda f: f.name)
    return unique_files


# Page furniture that recurs on every page and is NOT market commentary:
# the running masthead header, the logo line, the contact block and the legal
# disclaimer. The pre-existing guards silently missed all four - "clarkson
# hellas" (no trailing s) is not a substring of "Clarksons Hellas", and the
# contact line renders as "<b>Direct</b> +(30)..." so "direct +" never matched.
_FURNITURE_RE = re.compile(
    # masthead / logo / running header. Three spellings appear in the corpus:
    # "Clarksons Platou ...", "Clarkson Hellas Ltd ...", and the running header
    # "Sale & Purchase | Clarksons Hellas Weekly Bulletin | <date>".
    r"clarksons?\s+(?:platou|hellas|logo)"
    r"|\bplatou\b"
    r"|sale\s*(?:and|&)\s*purchase"
    r"|hellas\s*s&p\s*weekly\s+bulletin"
    # address + contact block (markdown emphasis varies: "Direct +(", "**Direct** +(",
    # "<b>Direct</b> +(")
    r"|kifissias|marousi|chalandri|snp@clarksons|clarksons\.(?:gr|com)"
    r"|\+\(?30\)?\s*210\b"
    r"|(?:direct|fax)\b[^+]{0,14}\+"
    # legal disclaimer sentences. The word "disclaimer" itself almost never
    # appears in the body, so the guards have to key on the sentences.
    r"|this\s+information\s+is\s+confidential"
    r"|any\s+reliance\s+placed\s+on\s+such\s+information"
    r"|strictly\s+at\s+the\s+recipient"
    r"|the\s+material\s+and\s+the\s+information"
    r"|is\s+not\s+intended\s+to\s+recommend|variable\s+and\s+cyclical\s+business"
    r"|to\s+the\s+extent\s+permitted\s+by\s+law"
    r"|these\s+exclusions\s+do\s+not\s+apply"
    r"|for\s+general\s+information\s+purposes"
    r"|loss\s+of\s+profit|loss\s+of\s+goodwill|loss\s+of\s+data"
    r"|breach\s+of\s+statutory\s+duty|even\s+if\s+foreseeable"
    r"|in\s+this\s+disclaimer|governed\s+by\s+and\s+construed"
    r"|prior\s+written\s+consent|purposes\s+of\s+raising\s+finance"
    r"|holding\s+company,\s+subsidiaries|licensors"
    r"|\(\+?\s*\d+\s+tons\s+ROB\)",
    re.I,
)


# A whole line that is only a date ("**06 August 2021**") or only part of the
# letterhead address ("151 25 Greece", "**Greece**<br><br>") is page furniture
# too - neither is a sentence of market commentary.
_BARE_DATE_RE = re.compile(r"^\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}$", re.I)
_ADDR_ONLY_RE = re.compile(r"^(?:greece|151\s*25|marousi|chalandri)(?:\s|$)", re.I)


def is_page_furniture(line: str) -> bool:
    """True for masthead/contact/legal/letterhead lines that are not commentary.

    Measured on 2023-03-17 bulletin 61: the running header
    'Sale and Purchase | Clarksons Hellas Weekly Bulletin | 17 Mar. 23'
    occurs 3x in the markdown (once per page) and was emitted as three
    identical 'Tankers' commentary rows, one per table-boundary flush."""
    # remove tags WITHOUT inserting a space so "13<sup>th</sup>" -> "13th"
    stripped = re.sub(r"<[^>]+>", "", line).strip().strip("*_ ").strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if not stripped:
        return True
    if _BARE_DATE_RE.match(stripped) or _ADDR_ONLY_RE.match(stripped):
        return True
    return bool(_FURNITURE_RE.search(line))


def flattened_table_cell_indices(lines):
    """Line indices belonging to a COLUMN-FLATTENED S&P table.

    The pre-2021-09 bulletins render the sales table as stacked bare cells with
    no pipe table: a VESSEL .. BUYER header row, then 7-9 lines per vessel
    (name, dwt, built+yard, engine, [gear], SS, DD, price, buyer). Those cell
    lines are table data, not market commentary, but the commentary block below
    used to append them (no pipe -> not a table to the guards), fusing the sales
    table into the Desk Talk text.

    The block is delimited by content, not geometry: it starts at the literal
    'VESSEL' header (running to the 'BUYER' header) and ends at the first page
    break, page furniture, or prose line (commentary is wrapped at ~120 chars,
    cells are short). Only used when the document has no pipe character, so
    pipe-table reports are untouched.
    """
    idx = set()
    n = len(lines)
    i = 0
    while i < n:
        s = lines[i].strip()
        if s.upper() == "VESSEL":
            j = i
            while j < min(n, i + 14):
                idx.add(j)
                if lines[j].strip().upper() == "BUYER":
                    break
                j += 1
            k = j + 1
            while k < n:
                body = lines[k].strip()
                if body == "---" or len(body) > 80 or is_page_furniture(lines[k]):
                    break
                idx.add(k)
                k += 1
            i = k
        else:
            i += 1
    return idx


def extract_clarksons_data(markdown_text: str, issue_date: str, report_week: int, source_file: str) -> Dict[str, Any]:
    """Comprehensive extractor handling Pipe tables, HTML tables, Line-by-line format, Commentary, and Macro."""
    sales: List[Dict[str, Any]] = []
    commentary: List[Dict[str, Any]] = []
    demolitions: List[Dict[str, Any]] = []
    macro_data: Dict[str, Any] = {"issue_date": issue_date, "report_week": report_week, "source_file": source_file}

    seen_sales_keys: Set[Tuple[str, Optional[int]]] = set()
    seen_demo_keys: Set[Tuple[str, Optional[int]]] = set()

    # 1. Parse Desk Talk & Narrative Commentary
    lines = markdown_text.splitlines()
    # The pre-2021-09 reports render the S&P table as stacked bare cells
    # (no pipe table); index those cell lines so the commentary block skips
    # them instead of fusing the sales table into the Desk Talk text.
    _cell_idx = flattened_table_cell_indices(lines) if "|" not in markdown_text else set()
    curr_section = "Desk Talk"
    curr_text_block: List[str] = []

    for _li, line in enumerate(lines):
        l_str = line.strip()
        if not l_str:
            continue
        clean_l = re.sub(r"[*_~<>/#]", "", l_str).strip()
        
        if re.search(r"^(?:Desk Talk|General Market)", clean_l, re.I):
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
            curr_section = "General"
        elif re.search(r"^(?:Dry Cargo|Bulk Carriers)", clean_l, re.I) and "sales" not in clean_l.lower() and not l_str.startswith("|"):
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
            curr_section = "Dry Bulk"
        elif re.search(r"^Tanker", clean_l, re.I) and "sales" not in clean_l.lower() and not l_str.startswith("|"):
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
            curr_section = "Tankers"
        elif re.search(r"^(?:Newbuilding|New Building)", clean_l, re.I) and "|" not in l_str:
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
            curr_section = "Newbuilding"
        elif re.search(r"^(?:Demolition|Recycling)", clean_l, re.I) and "|" not in l_str:
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
            curr_section = "Demolition"
        elif l_str.startswith("|") or "<table" in l_str or "<th" in l_str.lower() or "<td" in l_str.lower() or "<tr" in l_str.lower():
            if curr_text_block:
                commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})
                curr_text_block = []
        elif not l_str.startswith("#") and not l_str.startswith("---") and not is_page_furniture(l_str) and _li not in _cell_idx and not re.search(r"<(?:th|td|tr|table|div|tbody|thead)", l_str, re.I):
            if len(l_str) > 15:
                curr_text_block.append(l_str)

    if curr_text_block:
        commentary.append({"issue_date": issue_date, "report_week": report_week, "sector": curr_section, "commentary_text": " ".join(curr_text_block), "source_file": source_file})

    # Drop byte-identical commentary rows emitted from a single document. The
    # running header used to be flushed as a fresh block at every table
    # boundary, producing 2-3 identical rows per issue (17 duplicate-key rows
    # across the delivered series). Content-equal under the same sector is a
    # duplicate, not two passages.
    _seen_comm: Set[Tuple[str, str]] = set()
    _deduped_comm: List[Dict[str, Any]] = []
    for _c in commentary:
        _k = (_c["sector"], _c["commentary_text"])
        if _k in _seen_comm:
            continue
        _seen_comm.add(_k)
        _deduped_comm.append(_c)
    commentary = _deduped_comm

    def process_sales_row(v_raw: str, dwt_raw: Any, blt_raw: str, det_raw: str, ss_raw: str, p_raw: str, b_raw: str, sector: str):
        vessel = re.sub(r"[*_~]", "", v_raw).strip()
        if not vessel or vessel in ["-", "--", "---", "N/A", "NA"] or any(h in vessel.upper() for h in ["VESSEL", "NAME", "BALTIC", "ROUTE", "TOTAL"]):
            return
        # Preserve authentic vessel name (e.g. MICHALIS H, BULKER BEE 30, FETHIYE-M)
        vessel_name = re.sub(r"\s+\d{4,6}$", "", vessel).strip()

        dwt_val = clean_int(dwt_raw)
        key = (vessel_name.upper(), dwt_val)
        if key in seen_sales_keys:
            return
        seen_sales_keys.add(key)

        built_year = clean_int(blt_raw[:4]) if blt_raw and blt_raw[:4].isdigit() else None
        built_yard = blt_raw[4:].strip() if blt_raw and len(blt_raw) > 4 else ""

        # Extract SS/DD
        m_ss = re.search(r"SS\s+(\d{1,2}/\d{2,4})", ss_raw, re.I)
        m_dd = re.search(r"DD\s+(\d{1,2}/\d{2,4})", ss_raw, re.I)
        ss_due = m_ss.group(1) if m_ss else None
        dd_due = m_dd.group(1) if m_dd else None

        det_up = det_raw.upper()
        bwts = True if "BWTS" in det_up else False
        scrubber = True if "SCRUBBER" in det_up else False

        m_gear = re.search(r"(\d+\s*x\s*\d+\s*T)", det_up)
        gear = m_gear.group(1) if m_gear else None

        coating = "Zinc Coated" if "ZINC" in det_up else ("Epoxy Coated" if "EPOXY" in det_up else None)
        price_num, price_str = parse_price_usd_m(p_raw)
        segment = classify_vessel_segment(sector, dwt_val)
        is_auction = True if "AUCTION" in b_raw.upper() or "AUCTION" in p_raw.upper() else False
        is_en_bloc = True if "EN BLOC" in b_raw.upper() or "EN BLOC" in det_up or "EN BLOC" in p_raw.upper() else False

        sales.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "sector": sector,
            "segment": segment,
            "vessel_name": vessel_name,
            "dwt": dwt_val,
            "built_year": built_year,
            "built_yard": built_yard,
            "details": det_raw,
            "bwts_fitted": bwts,
            "scrubber_fitted": scrubber,
            "gear_cranes": gear,
            "special_coating": coating,
            "ss_due": ss_due,
            "dd_due": dd_due,
            "price_usd_m": price_num,
            "price_raw": price_str,
            "buyer": b_raw,
            "is_en_bloc": is_en_bloc,
            "is_auction": is_auction,
            "source_file": source_file
        })

    def process_demo_row(v_raw: str, dwt_raw: Any, blt_raw: Any, det_raw: str, p_raw: str, deliv_raw: str):
        vessel = re.sub(r"[*_~]", "", v_raw).strip()
        if not vessel or vessel in ["-", "--", "---", "N/A", "NA"] or any(h in vessel.upper() for h in ["VESSEL", "NAME", "TOTAL"]):
            return
        vessel_name = re.sub(r"\s+\d{4,6}$", "", vessel).strip()
        dwt_val = clean_int(dwt_raw)
        key = (vessel_name.upper(), dwt_val)
        if key in seen_demo_keys:
            return
        seen_demo_keys.add(key)

        p_num = clean_num(p_raw)
        demolitions.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "vessel_name": vessel,
            "dwt": dwt_val,
            "built": clean_int(blt_raw),
            "details": det_raw,
            "price_usd_per_ldt": p_num,
            "price_raw": p_raw,
            "delivery_location": deliv_raw,
            "source_file": source_file
        })

    # 2. Parse HTML Tables (if present)
    if "<table>" in markdown_text or "<table " in markdown_text:
        soup = BeautifulSoup(markdown_text, "html.parser")
        for tbl in soup.find_all("table"):
            rows = tbl.find_all("tr")
            if not rows:
                continue
            header_cells = [c.get_text(strip=True).upper() for c in rows[0].find_all(["th", "td"])]
            is_demo = any("DELIVERY" in c or "LDT" in c for c in header_cells)
            is_sales = any("BUYER" in c or "PRICE" in c for c in header_cells) and not is_demo

            tbl_str = str(tbl)
            idx = markdown_text.find(tbl_str[:50]) if len(tbl_str) >= 50 else markdown_text.find(tbl_str)
            preceding = markdown_text[max(0, idx-300):idx].lower() if idx != -1 else ""
            sector = "Tankers" if "tanker" in preceding else ("Dry Bulk" if "bulk" in preceding else "Dry Bulk")

            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 6:
                    if is_demo:
                        process_demo_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5] if len(cells) > 5 else "")
                    elif is_sales:
                        process_sales_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], cells[6] if len(cells) > 6 else "", sector)

    # 3. Parse Markdown Pipe Tables
    active_sector = None
    in_demo = False

    for line in lines:
        s = line.strip()
        if not s:
            continue
        clean_s = re.sub(r"[*_~<>/#]", "", s).strip()

        if re.search(r"bulk\s*carrier|bulker\s*sales", clean_s, re.I):
            active_sector = "Dry Bulk"
            in_demo = False
            continue
        elif re.search(r"tanker\s*sales|tankers\s*[-–—]\s*chemicals", clean_s, re.I) or (clean_s.lower() == "tanker" and not s.startswith("|")):
            active_sector = "Tankers"
            in_demo = False
            continue
        elif re.search(r"gas|container", clean_s, re.I) and ("sales" in clean_s.lower() or "carriers" in clean_s.lower()):
            active_sector = "Gas / Containers"
            in_demo = False
            continue
        elif re.search(r"demolition|recycling", clean_s, re.I) and len(clean_s) < 25:
            in_demo = True
            active_sector = None
            continue
        elif any(k in clean_s.lower() for k in ["baltic", "bunker", "contact", "disclaimer"]):
            active_sector = None
            in_demo = False
            continue

        if s.startswith("|") and "---" not in s:
            cells = [re.sub(r"<br\s*/?>", " ", c).strip() for c in s.split("|")[1:-1]]
            if len(cells) >= 6 and not any(h in cells[0].upper() for h in ["VESSEL", "NAME", "BALTIC", "ROUTE"]):
                if in_demo or ("/LDT" in s.upper() or "/ LDT" in s.upper()):
                    process_demo_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5] if len(cells) > 5 else "")
                elif active_sector:
                    process_sales_row(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], cells[6] if len(cells) > 6 else "", active_sector)

        # Macro indicators (BDI and EUR/USD)
    clean_all = re.sub(r"[*_~]", "", markdown_text)
    m_bdi = re.search(r"BDI\s*\|\s*(\d+)", clean_all, re.I)
    if not m_bdi:
        m_bdi = re.search(r"BDI\s*\n\s*(\d{3,5})", clean_all, re.I)
    if m_bdi:
        macro_data["bdi"] = clean_int(m_bdi.group(1))

    m_eur = re.search(r"(?:EURO/USD|Euro/USD|EUR/USD)\s*\|\s*(\d+\.\d+)", clean_all, re.I)
    if not m_eur:
        m_eur = re.search(r"(?:EURO/USD|Euro/USD|EUR/USD)\s*\n\s*(\d+\.\d+)", clean_all, re.I)
    if m_eur:
        macro_data["eur_usd"] = clean_num(m_eur.group(1))

    # 4. Handle Line-by-Line Stacked Format (for 2021 reports with no tables)
    if len(sales) == 0 and len(demolitions) == 0:
        sector = "Dry Bulk"
        for i in range(len(lines) - 1):
            curr_l = lines[i].strip()
            nxt_l = lines[i+1].strip()
            if "TANKER" in curr_l.upper():
                sector = "Tankers"
            elif "DEMOLITION" in curr_l.upper():
                sector = "Demolition"

            if re.match(r"^\d{1,3}(?:,\d{3})+$", nxt_l) and len(curr_l) >= 3 and not curr_l.isdigit():
                v_name = curr_l
                dwt = clean_int(nxt_l)
                built_raw = lines[i+2].strip() if i+2 < len(lines) else ""
                det_raw = lines[i+3].strip() if i+3 < len(lines) else ""
                p_raw = ""
                b_raw = ""
                for j in range(i+4, min(len(lines), i+10)):
                    cand = lines[j].strip()
                    if "USD" in cand.upper() or "RGN" in cand.upper():
                        p_raw = cand
                    elif any(b_name in cand.upper() for b_name in ["GREEKS", "TURKISH", "NORWEGIANS", "U/D", "AUCTION", "CHINESE"]):
                        b_raw = cand

                if sector == "Demolition":
                    process_demo_row(v_name, dwt, built_raw[:4], det_raw, p_raw, b_raw)
                else:
                    process_sales_row(v_name, dwt, built_raw, det_raw, "", p_raw, b_raw, sector)

    return {
        "metadata": {
            "publisher": "Clarkson Hellas Ltd.",
            "title": f"Clarksons Weekly Sale & Purchase Report - {issue_date}",
            "issue_date": issue_date,
            "report_week": report_week,
            "source_file": source_file,
            "total_sales_recorded": len(sales),
            "total_demolitions_recorded": len(demolitions),
            "total_commentary_sections": len(commentary)
        },
        "sales": sales,
        "commentary": commentary,
        "demolitions": demolitions,
        "macro": macro_data
    }


def generate_clarksons_markdown(data: Dict[str, Any]) -> str:
    """Format extracted data into clean, structured GitHub Flavored Markdown."""
    meta = data["metadata"]
    md = [
        "---",
        f"title: \"{meta['title']}\"",
        f"issue_date: \"{meta['issue_date']}\"",
        f"report_week: {meta['report_week']}",
        f"publisher: \"{meta['publisher']}\"",
        f"source_file: \"{meta['source_file']}\"",
        f"sales_count: {meta['total_sales_recorded']}",
        f"demolitions_count: {meta['total_demolitions_recorded']}",
        "---",
        "",
        f"# {meta['title']}",
        "",
        f"**Publisher**: {meta['publisher']} | **Issue Date**: {meta['issue_date']} (Week {meta['report_week']})",
        ""
    ]

    # Commentary Section
    if data["commentary"]:
        valid_comms = [
            c for c in data["commentary"]
            if c.get("commentary_text")
            and not any(tag in c["commentary_text"].lower() for tag in ["<th", "<td", "<tr", "<table", "<th>", "<td>", "details"])
            and "the material and the information" not in c["commentary_text"].lower()
            and "direct +" not in c["commentary_text"].lower()
        ]
        if valid_comms:
            md.append("## Desk Commentary\n")
            for c in valid_comms:
                md.append(f"### {c['sector']}")
                md.append(f"{c['commentary_text']}\n")

    # Secondhand Sales Table
    if data["sales"]:
        md.append("## Reported Secondhand Sales\n")
        md.append("| Sector | Segment | Vessel Name | DWT | Built | Yard | Details | SS/DD | Price (USD M) | Buyer | Terms |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for s in data["sales"]:
            if s['price_usd_m'] is not None:
                p_val = f"**${s['price_usd_m']}M**"
            elif s['price_raw']:
                p_val = f"**{s['price_raw']}**"
            elif s['is_en_bloc']:
                p_val = "*En Bloc*"
            else:
                p_val = "-"
            terms = []
            if s['is_en_bloc']: terms.append("En Bloc")
            if s['is_auction']: terms.append("Auction")
            term_str = ", ".join(terms) if terms else "-"
            ss_dd = f"SS {s['ss_due'] or '-'} / DD {s['dd_due'] or '-'}" if (s['ss_due'] or s['dd_due']) else "-"
            md.append(f"| {s['sector']} | {s['segment']} | **{s['vessel_name']}** | {s['dwt'] or '-'} | {s['built_year'] or '-'} | {s['built_yard'] or '-'} | {s['details'] or '-'} | {ss_dd} | {p_val} | {s['buyer'] or '-'} | {term_str} |")
        md.append("")

    # Demolition Table
    if data["demolitions"]:
        md.append("## Reported Demolition Fixtures\n")
        md.append("| Vessel Name | DWT | Built | Details | Price ($/LDT) | Delivery Destination |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for d in data["demolitions"]:
            p_str = f"${d['price_usd_per_ldt']}/LDT" if d['price_usd_per_ldt'] else d['price_raw']
            md.append(f"| **{d['vessel_name']}** | {d['dwt'] or '-'} | {d['built'] or '-'} | {d['details'] or '-'} | {p_str or '-'} | {d['delivery_location'] or '-'} |")
        md.append("")

    return "\n".join(md)


def process_all_clarksons():
    """Extract and compile all 165 Clarksons reports into Markdown, JSON sidecars, and Master Series CSVs."""
    unique_pdfs = get_unique_clarksons_reports(PDF_ROOT)
    print(f"Executing extraction across {len(unique_pdfs)} unique Clarksons reports spanning 2021 to 2026...", flush=True)

    all_sales: List[Dict[str, Any]] = []
    all_commentary: List[Dict[str, Any]] = []
    all_demo: List[Dict[str, Any]] = []
    all_macro: List[Dict[str, Any]] = []

    success = 0
    t0 = time.time()

    for idx, pdf in enumerate(unique_pdfs, 1):
        stem = pdf.stem
        issue_date, year, report_week = parse_issue_date(pdf.name)

        out_year_dir = OUT_MD_DIR / year
        out_year_dir.mkdir(parents=True, exist_ok=True)
        md_file = out_year_dir / f"{stem}.md"
        json_file = out_year_dir / f"{stem}.tables.json"

        # Also write to data/extracted/md/clarksons/<year>/
        out_broker_dir = ROOT / "data" / "extracted" / "md" / "clarksons" / year
        out_broker_dir.mkdir(parents=True, exist_ok=True)
        md_broker_file = out_broker_dir / f"{stem}.md"
        json_broker_file = out_broker_dir / f"{stem}.tables.json"

        cache_file = CACHE_DIR / f"{stem}.md"
        if not cache_file.exists():
            logger.warning(f"Cache missing for {stem}")
            continue

        raw_md = cache_file.read_text(encoding="utf-8")
        data = extract_clarksons_data(raw_md, issue_date, report_week, pdf.name)

        # Write sidecars to both directories
        sidecar_content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        full_md = generate_clarksons_markdown(data)

        json_file.write_text(sidecar_content, encoding="utf-8")
        md_file.write_text(full_md, encoding="utf-8")
        json_broker_file.write_text(sidecar_content, encoding="utf-8")
        md_broker_file.write_text(full_md, encoding="utf-8")

        all_sales.extend(data["sales"])
        all_commentary.extend(data["commentary"])
        all_demo.extend(data["demolitions"])
        all_macro.append(data["macro"])
        success += 1

        if success % 25 == 0 or success == len(unique_pdfs):
            print(f"[{success}/{len(unique_pdfs)}] Processed {pdf.name} -> {len(data['sales'])} sales, {len(data['demolitions'])} demo, {len(data['commentary'])} commentary", flush=True)

    # Write Master Stacked Series CSVs
    print("\nWriting master series CSVs to data/extracted/series/...", flush=True)

    # 1. S&P Sales Series
    if all_sales:
        p_sales = OUT_SERIES_DIR / "clarksons_snp_sales_series.csv"
        fieldnames = [
            "issue_date", "report_week", "sector", "segment", "vessel_name", "dwt",
            "built_year", "built_yard", "details", "bwts_fitted", "scrubber_fitted",
            "gear_cranes", "special_coating", "ss_due", "dd_due", "price_usd_m",
            "price_raw", "buyer", "is_en_bloc", "is_auction", "source_file"
        ]
        with open(p_sales, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_sales)
        print(f"Saved {len(all_sales)} cumulative rows to {p_sales.name}", flush=True)

    # 2. Desk Talk & Commentary Series
    if all_commentary:
        p_comm = OUT_SERIES_DIR / "clarksons_desk_talk_series.csv"
        with open(p_comm, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["issue_date", "report_week", "sector", "commentary_text", "source_file"])
            writer.writeheader()
            writer.writerows(all_commentary)
        print(f"Saved {len(all_commentary)} cumulative rows to {p_comm.name}", flush=True)

    # 3. Demolition Sales Series
    if all_demo:
        p_demo = OUT_SERIES_DIR / "clarksons_demolition_sales_series.csv"
        with open(p_demo, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["issue_date", "report_week", "vessel_name", "dwt", "built", "details", "price_usd_per_ldt", "price_raw", "delivery_location", "source_file"])
            writer.writeheader()
            writer.writerows(all_demo)
        print(f"Saved {len(all_demo)} cumulative rows to {p_demo.name}", flush=True)

    # 4. Macro & FX Series
    if all_macro:
        p_macro = OUT_SERIES_DIR / "clarksons_macro_series.csv"
        with open(p_macro, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["issue_date", "report_week", "bdi", "eur_usd", "source_file"])
            writer.writeheader()
            writer.writerows(all_macro)
        print(f"Saved {len(all_macro)} cumulative rows to {p_macro.name}", flush=True)

    elapsed = time.time() - t0
    print(f"\nProcessing complete in {elapsed:.1f}s. Total reports parsed: {success}", flush=True)


if __name__ == "__main__":
    process_all_clarksons()
