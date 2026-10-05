"""
run_banchero_world_class_llama.py

World-Class LlamaParse Extraction Pipeline for Banchero Costa Market Reports (2021-2026).

Strictly adheres to repository zero-data-loss standards and Shipbroking_Source_Parsing_Notes (Section 4):
- Discards page 1 (cover/logos) and last page (employee contacts / office disclaimers).
- Parses all substantive pages (Page 2 to Page N-1) cover-to-cover using LlamaParse (tier="cost_effective", version="latest").
- Extracts 100% complete narrative prose: Macro Thematic Essay (Page 2), Commodity News Dry Bulk & Oil/Gas (Pages 3-4),
  Capesize, Panamax, Supramax, Handysize, Crude Tankers, Product Tankers, Containerships, S&P, Newbuilding, Demolition, FFA.
- Extracts all structured tables: Rate benchmarks, S&P reported sales with 7-digit IMO numbers, FFA curves, Newbuilding prices,
  Demolition recycling assessments, VHSS ConTex index, Freightos index, Currencies, and Commodity prices.
- Extracts vector charts as structured monthly/quarterly data tables.
- Distributes processing across active LlamaParse accounts (Accounts 5-9) concurrently.
- Updates data/extracted/md/banchero_costa/<stem>.md, <stem>.tables.json, and master series CSVs.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from bs4 import BeautifulSoup
from llama_parse import LlamaParse

# Set UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "banchero_costa"
RAW_OUT_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero_v2"
MD_OUT_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"
SERIES_DIR = ROOT / "data" / "extracted" / "series"
STATE_FILE = RAW_OUT_DIR / "_run_state.json"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("banchero_llama")

# Unit tokens a freight-rate row can carry. Used to locate the UNIT column by
# CONTENT (not by index) because the freight table redesigns across years.
FREIGHT_UNIT_TOKENS = {
    "ws", "usd/day", "usd/mt", "usd/t", "days", "usd mln",
    "usd/feu", "points", "index", "idx", "cbm",
}

# Account pool for concurrent workers (Accounts 5 to 9)
ACCOUNTS = [
    {
        "id": "account_5",
        "name": "Account 5 (Prateek Upadhyay)",
        "api_key": "llx-3gIntWgNcRfQ8JldOC2Fb1LjK7PRkuap8th9WCSxvMaVuqRw",
    },
    {
        "id": "account_6",
        "name": "Account 6 (Kumar Ravindra)",
        "api_key": "llx-87GMiUy5mtvFe4aOQ3BaQO4zBfki7Vr0g00QyQkgKodvxqYf",
    },
    {
        "id": "account_7",
        "name": "Account 7 (Saumya Kumar)",
        "api_key": "llx-g8p7UzojxIQocFBeWgvRDUpaQR6U56RK3nWniAtWuBksFjiD",
    },
    {
        "id": "account_8",
        "name": "Account 8 (Amitesh Anand)",
        "api_key": "llx-PZfPrjiaGq7viHwYsEAa1tUnpt4t7qrPmwX1tMhVPv1W6ljB",
    },
    {
        "id": "account_9",
        "name": "Account 9 (HIMANSHU)",
        "api_key": "llx-iPBWeHFR8uLLFnGW4UNb8UWfMpxc3yO8ZZXTGE5vYA4ULhz9",
    },
]

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_state_lock = threading.RLock()


def load_state() -> Dict[str, Any]:
    with _state_lock:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}


def save_state_entry(stem: str, entry: Dict[str, Any]):
    with _state_lock:
        state = load_state()
        state[stem] = entry
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_date_and_week(pdf_path: Path) -> Tuple[int, str]:
    """Extract week number and ISO issue date (YYYY-MM-DD) from PDF."""
    try:
        doc = pymupdf.open(pdf_path)
        txt = doc[0].get_text() if len(doc) > 0 else ""
        doc.close()
        m = re.search(r"Week\s*(\d{1,2})/(\d{4})\s*\(([^)]+)\)", txt, re.I)
        if m:
            wk = int(m.group(1))
            yr = int(m.group(2))
            raw_span = m.group(3).strip()
            parts = re.findall(r"(\d{1,2})\s+([A-Za-z]+)", raw_span)
            if len(parts) >= 2:
                end_d, end_m_str = parts[-1]
                mo_key = end_m_str.lower()[:3]
                if mo_key in MONTHS:
                    mo = MONTHS[mo_key]
                    d = int(end_d)
                    y = yr
                    if mo == 1 and parts[0][1].lower()[:3] == "dec":
                        y = yr + 1
                    return wk, f"{y:04d}-{mo:02d}-{d:02d}"
            iso_date = dt.date.fromisocalendar(yr, wk, 5)
            return wk, iso_date.isoformat()
    except Exception:
        pass

    # Fallback to filename parsing
    m2 = re.search(r"banchero_costa_(\d{4})_W?(\d{1,2})", pdf_path.stem)
    if m2:
        yr = int(m2.group(1))
        wk = int(m2.group(2))
        iso_date = dt.date.fromisocalendar(yr, min(wk, 52), 5)
        return wk, iso_date.isoformat()

    return 1, "2026-01-01"


def get_target_pages(pdf_path: Path) -> Tuple[str, int]:
    """
    Returns comma-separated target page string and total pages count.
    Excludes page 0 (cover/logos) and page N-1 (contacts/disclaimers).
    """
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    if total_pages <= 3:
        # If very short, parse pages 1 to total_pages-1
        pages = list(range(1, total_pages))
    else:
        # Discard page 0 and last page
        pages = list(range(1, total_pages - 1))

    return ",".join(str(p) for p in pages), len(pages)


def parse_single_pdf(
    pdf_path: Path,
    account: Dict[str, str],
    retry_accounts: List[Dict[str, str]]
) -> Tuple[bool, str, Optional[str]]:
    """
    Parses a single PDF using LlamaParse with automatic account failover.
    Returns (success, stem, error_message).
    """
    stem = pdf_path.stem
    target_pages_str, num_target_pages = get_target_pages(pdf_path)

    accounts_to_try = [account] + [a for a in retry_accounts if a["id"] != account["id"]]

    for acc in accounts_to_try:
        try:
            logger.info(f"Parsing {stem} ({num_target_pages} pages) via {acc['name']}...")
            parser = LlamaParse(
                api_key=acc["api_key"],
                result_type="markdown",
                target_pages=target_pages_str,
                tier="cost_effective",
                version="latest",
                verbose=False
            )
            docs = parser.load_data(str(pdf_path))
            if not docs or not docs[0].text:
                raise ValueError("Empty response returned by LlamaParse")

            full_md = "\n\n".join(d.text for d in docs)

            # Save raw parsed markdown
            RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
            raw_path = RAW_OUT_DIR / f"{stem}.md"
            raw_path.write_text(full_md, encoding="utf-8")

            # Save state
            save_state_entry(stem, {
                "status": "success",
                "account": acc["id"],
                "pages": num_target_pages,
                "md_size": len(full_md),
                "timestamp": dt.datetime.now().isoformat()
            })

            logger.info(f"SUCCESS: {stem} parsed ({len(full_md)} chars) via {acc['id']}")
            return True, stem, None

        except Exception as e:
            err = str(e).lower()
            logger.warning(f"Error on {stem} using {acc['name']}: {e}")
            if any(term in err for term in ["429", "quota", "credit", "payment required", "limit exceeded"]):
                logger.warning(f"Quota issue on {acc['name']}, trying next account...")
                continue
            else:
                # Other error, try next account or fail
                continue

    return False, stem, "All accounts failed"


def html_table_to_markdown(html_match):
    html_content = html_match.group(0)
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    if not table:
        return html_content
    rows = []
    headers = []
    header_tr = table.find('tr')
    if header_tr:
        ths = header_tr.find_all(['th', 'td'])
        headers = [re.sub(r'\s+', ' ', th.get_text()).strip() for th in ths]
    for tr in table.find_all('tr')[1:]:
        tds = tr.find_all(['td', 'th'])
        row = [re.sub(r'\s+', ' ', td.get_text()).strip() for td in tds]
        if any(row):
            rows.append(row)
    max_cols = max(len(headers), max((len(r) for r in rows), default=0))
    if max_cols == 0:
        return html_content
    while len(headers) < max_cols:
        headers.append('')
    if not any(headers) and rows:
        headers = [f'Col {k+1}' for k in range(max_cols)]
    md_lines = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * max_cols) + ' |']
    for r in rows:
        while len(r) < max_cols:
            r.append('')
        md_lines.append('| ' + ' | '.join(r[:max_cols]) + ' |')
    return '\n' + '\n'.join(md_lines) + '\n'


def normalize_sales_row(
    row: List[str],
    headers: List[str],
    issue_date: str,
    report_week: int,
    source_file: str
) -> Optional[Dict[str, Any]]:
    if not row or len(row) < 4:
        return None
    row_dict = {h.strip().upper(): val.strip() for h, val in zip(headers, row) if h.strip()}
    v_type = row_dict.get('TYPE') or row_dict.get('CATEGORY') or row_dict.get('SECTOR') or ''
    v_name = row_dict.get('VESSEL NAME') or row_dict.get('VESSEL') or row_dict.get('NAME') or ''
    imo = row_dict.get('IMO NO.') or row_dict.get('IMO NO') or row_dict.get('IMO') or ''
    dwt = row_dict.get('DWT') or ''
    blt = row_dict.get('BLT') or row_dict.get('YEAR') or row_dict.get('BUILT') or row_dict.get('YOB') or ''
    yard = row_dict.get('YARD') or row_dict.get('BUILT BY') or row_dict.get('BUILDER') or ''
    buyer = row_dict.get('BUYERS') or row_dict.get('BUYER') or row_dict.get('PURCHASER') or ''
    seller = row_dict.get('SELLER') or row_dict.get('OWNER') or row_dict.get('SELLERS') or ''
    price = row_dict.get('PRICE') or ''
    comments = row_dict.get('NOTE') or row_dict.get('NOTES') or row_dict.get('COMMENTS') or row_dict.get('DETAILS') or ''

    # Positional fallback if names or types missing
    if not v_name and len(row) >= 5:
        pos = 0
        if row[0].lower() in ['bulk', 'tank', 'container', 'gas', 'lpg', 'lng', 'combo', 'general cargo']:
            v_type = row[0]
            pos = 1
        v_name = row[pos]
        pos += 1
        clean_num = re.sub(r'\D', '', row[pos])
        if len(clean_num) == 7:
            imo = clean_num
            pos += 1
        if pos < len(row):
            dwt = row[pos]
            pos += 1
        if pos < len(row):
            blt = row[pos]
            pos += 1
        if pos < len(row):
            yard = row[pos]
            pos += 1
        if pos < len(row):
            buyer = row[pos]
            pos += 1
        if pos < len(row):
            price = row[pos]
            pos += 1
        if pos < len(row):
            comments = ' '.join(row[pos:])

    if not yard and seller and any(k in seller.lower() for k in ['shipbuilding', 'yard', 'hi', 'zosen', 'koyo', 'imabari', 'namura', 'dacks', 'sws', 'stx', 'hudong', 'samsung', 'hyundai', 'tsuneishi']):
        yard = seller
        seller = ''

    imo_clean = re.sub(r'\D', '', imo)
    imo_final = imo_clean if len(imo_clean) == 7 else ''

    if not v_name or v_name.lower() in ['vessel', 'vessel name', 'name', '---', 'total']:
        return None

    return {
        'issue_date': issue_date,
        'report_week': report_week,
        'vessel_type': v_type,
        'vessel': v_name,
        'imo': imo_final,
        'dwt': dwt,
        'built': blt,
        'yard': yard,
        'buyer': buyer,
        'seller': seller,
        'price_usd_m': price,
        'comments': comments,
        'source_file': source_file
    }


def merge_split_sales_table(md_text: str) -> str:
    """
    Merges S&P Reported Sales tables that were horizontally split by LlamaParse:
    Table 1 has 7 columns (ending in Price) and Table 2 has the vessel comments (SS/DD, BWTS, delivery terms).
    Stitches comments back onto Table 1 rows, sets header to 'Details / Comments', and drops Table 2.
    """
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('|') and i + 1 < len(lines) and any(s in lines[i+1] for s in ['| ---', '|:---', '|---']):
            hdrs = [c.strip() for c in line.split('|')[1:-1]]
            if len(hdrs) == 7 and any('PRICE' in h.upper() for h in hdrs) and any(k in ' '.join(hdrs).upper() for k in ['VESSEL', 'SIZE', 'BUYER', 'CATEGORY']):
                # Collect Table 1
                t1_lines = [line, lines[i+1]]
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith('|'):
                    t1_lines.append(lines[j])
                    j += 1
                t1_rows = [ [c.strip() for c in l.split('|')[1:-1]] for l in t1_lines[2:] ]
                
                # Check lines between table 1 and table 2
                k = j
                inter_headings = []
                while k < min(len(lines), j + 6) and not lines[k].strip().startswith('|'):
                    if lines[k].strip().startswith('###'):
                        inter_headings.append(lines[k].strip('# \t'))
                    k += 1
                    
                if k < len(lines) and lines[k].strip().startswith('|') and ('| ---' in lines[k+1] or '|:---' in lines[k+1]):
                    t2_hdr = [c.strip() for c in lines[k].split('|')[1:-1]]
                    m = k + 2
                    t2_rows = []
                    while m < len(lines) and lines[m].strip().startswith('|'):
                        # Stop if this row is a new table header (e.g. contains 'Unit' or 'Vessel Class')
                        r_cells = [c.strip() for c in lines[m].split('|')[1:-1]]
                        if any(x in ' '.join(r_cells).upper() for x in ['VESSEL CLASS', 'W-O-W', 'Y-O-Y', 'M-O-M', 'UNIT']):
                            break
                        t2_rows.append(r_cells)
                        m += 1
                        
                    comments = list(inter_headings)
                    if t2_hdr and t2_hdr[-1] and not any(t2_hdr[-1].lower().startswith(x) for x in ['details', 'route', 'benchmark', 'col']):
                        comments.append(t2_hdr[-1])
                    for r in t2_rows:
                        if r and r[-1]:
                            comments.append(r[-1])
                            
                    # Check if comments are genuine vessel comments (contain SS, DD, BWTS, etc.)
                    if any(any(x in c.upper() for x in ['SS', 'DD', 'BWTS', 'DELY', 'EN BLOC', 'AUCTION', 'ORDER']) for c in comments):
                        # SUCCESSFUL MATCH! Merge comments into Table 1
                        hdrs = ['Category', 'Vessel Name', 'DWT', 'Year', 'Yard / Builder', 'Buyer', 'Price ($m)', 'Details / Comments']
                        out.append('| ' + ' | '.join(hdrs) + ' |')
                        out.append('| ' + ' | '.join(['---'] * len(hdrs)) + ' |')
                        for r_idx, r in enumerate(t1_rows):
                            cmt = comments[r_idx] if r_idx < len(comments) else ''
                            while len(r) < 7: r.append('')
                            out.append('| ' + ' | '.join(r[:7] + [cmt]) + ' |')
                        out.append('')
                        i = m
                        continue
        out.append(line)
        i += 1
    return '\n'.join(out)


def polish_markdown_tables(md_text: str) -> str:
    """
    Polishes all Markdown tables in the extracted text:
    1. Unpacks <br/> packed time series tables and strips empty trailing dummy columns.
    2. Prunes any completely empty trailing columns from tables.
    3. Handles Title-as-Header pattern: extracts title to ### heading and shifts row 0 to become table headers.
    4. Handles Unit-shifted headers: restores missing column 0 header (Benchmark/Vessel Class/Segment).
    5. Fills missing first header cell (Route / Benchmark / Segment / Currency / etc.).
    6. Replaces generic 'Col 1 | Col 2' headers in S&P tables with domain headers.
    7. Normalizes FFA tables: changes category in column 0 header to 'Tenor' and emits section heading.
    8. Formats all tables with proper markdown pipes and alignments.
    """
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect start of table
        if line.strip().startswith('|') and i + 1 < len(lines) and any(s in lines[i+1] for s in ['| ---', '|:---', '|---']):
            table_lines = [line, lines[i+1]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith('|'):
                table_lines.append(lines[j])
                j += 1
                
            header_line = table_lines[0]
            raw_headers = [c.strip() for c in header_line.split('|')[1:-1]]
            
            # Check if all rows are packed into the header with <br/> (no data rows or empty data rows)
            data_rows = table_lines[2:]
            has_no_real_data_rows = len(data_rows) == 0 or all(not any(c.strip() for c in r.split('|')[1:-1]) for r in data_rows)
            is_packed_br = any(c.count('<br/>') >= 2 for c in raw_headers) and has_no_real_data_rows
            
            if is_packed_br:
                first_parts = [p.strip() for p in raw_headers[0].split('<br/>') if p.strip()]
                title = first_parts[0] if first_parts else ''
                col_headers = []
                col_data = []
                for c in raw_headers:
                    parts = [p.strip() for p in c.split('<br/>') if p.strip()]
                    if not parts: continue
                    if len(parts) == 1 and parts[0].upper() == title.upper(): continue
                    if parts[0].upper() == title.upper() or title.upper() in parts[0].upper():
                        hdr = parts[1] if len(parts) > 1 else 'Value'
                        items = parts[2:] if len(parts) > 2 else []
                    else:
                        hdr = parts[0]
                        items = parts[1:]
                    col_headers.append(hdr)
                    col_data.append(items)
                max_rows = max((len(c) for c in col_data), default=0)
                if col_headers and max_rows > 0:
                    if title and len(title) > 2 and not title.lower().startswith('col'):
                        prev_ctx = ' '.join(out[-3:]).upper() if len(out) >= 3 else ''
                        if title.upper() not in prev_ctx:
                            out.append(f'### {title}\n')
                    out.append('| ' + ' | '.join(col_headers) + ' |')
                    out.append('| ' + ' | '.join(['---'] * len(col_headers)) + ' |')
                    for r_idx in range(max_rows):
                        r_vals = [col_data[c_idx][r_idx] if r_idx < len(col_data[c_idx]) else '' for c_idx in range(len(col_headers))]
                        out.append('| ' + ' | '.join(r_vals) + ' |')
                    out.append('')
                    i = j
                    continue

            # Standard table with rows: Prune empty trailing columns and clean headers
            rows = []
            for r_line in data_rows:
                r_cells = [c.strip() for c in r_line.split('|')[1:-1]]
                rows.append(r_cells)

            # Prune duplicate/hallucinated commodity chart tables (e.g. BUNKER PRICES @ SINGAPORE with empty Item/Unit)
            table_text_upper = ' '.join(raw_headers + [cell for r in rows for cell in r]).upper()
            is_commodity_chart_fake = (
                any(k in table_text_upper for k in ['COAL & IRON ORE PRICE', 'BUNKER PRICES @ SINGAPORE', 'BRENT & WTI OIL PRICE', 'HENRY HUB PRICE', 'STEEL PRICES IN CHINA', 'WHEAT & CORN PRICES'])
                and any(h.lower() == 'item' for h in raw_headers)
                and any(h.lower() == 'unit' for h in raw_headers)
            )
            if is_commodity_chart_fake:
                item_idx = next((idx for idx, h in enumerate(raw_headers) if h.lower() == 'item'), -1)
                unit_idx = next((idx for idx, h in enumerate(raw_headers) if h.lower() == 'unit'), -1)
                if item_idx != -1 and unit_idx != -1:
                    item_empty = all(len(r) <= item_idx or r[item_idx] == '' for r in rows)
                    unit_empty = all(len(r) <= unit_idx or r[unit_idx] == '' for r in rows)
                    if item_empty and unit_empty:
                        i = j
                        continue
                
            num_cols = len(raw_headers)
            cols_with_data = []
            for c_idx in range(num_cols):
                has_data = any(len(r) > c_idx and r[c_idx] != '' for r in rows)
                cols_with_data.append(has_data)
                
            # Keep only columns up to the last column with data
            last_valid_col = -1
            for c_idx in range(num_cols - 1, -1, -1):
                if cols_with_data[c_idx]:
                    last_valid_col = c_idx
                    break
                    
            if last_valid_col != -1 and last_valid_col < num_cols - 1:
                raw_headers = raw_headers[:last_valid_col + 1]
                rows = [r[:last_valid_col + 1] for r in rows]
                num_cols = len(raw_headers)
                
            extracted_title = ''
            # Check Title-as-Header pattern (raw_headers[0] is title, rest empty, rows has headers)
            if raw_headers and raw_headers[0] and len(raw_headers) > 1 and all(c == '' for c in raw_headers[1:]) and len(rows) > 0:
                cand = rows[0]
                if any(c != '' for c in cand):
                    extracted_title = raw_headers[0]
                    raw_headers = list(cand)
                    rows = rows[1:]
                    num_cols = len(raw_headers)

            # Clean headers: remove embedded titles separated by <br/>
            clean_headers = []
            for c in raw_headers:
                if '<br/>' in c:
                    parts = [p.strip() for p in c.split('<br/>') if p.strip()]
                    if len(parts) >= 2:
                        if not extracted_title:
                            extracted_title = parts[0]
                        clean_headers.append(parts[-1])
                    elif parts:
                        clean_headers.append(parts[0])
                    else:
                        clean_headers.append('')
                else:
                    clean_headers.append(c)

            # Unit-shifted headers check (header starts with Unit/Currency, row[0] is benchmark, row[1] is unit)
            if clean_headers and clean_headers[0].lower() in ['unit', 'currency'] and len(rows) > 0 and len(rows[0]) > 1:
                r0 = rows[0]
                if any(u in r0[1].lower() for u in ['usd', 'index', 'days', 'points', 'idx', 'cbm']):
                    prev_ctx = (' '.join(out[-10:]) + ' ' + extracted_title).upper()
                    col0_name = 'Benchmark'
                    if any(k in prev_ctx for k in ['DELAYS', 'STRAITS']):
                        col0_name = 'Direction'
                    elif any(k in prev_ctx for k in ['NEWBUILDING', 'SECONDHAND']):
                        col0_name = 'Vessel Class'
                    elif any(k in prev_ctx for k in ['RECYCLING', 'DEMOLITION']):
                        col0_name = 'Segment'

                    if clean_headers[-1] == '' and len(clean_headers) == len(r0):
                        clean_headers = [col0_name] + clean_headers[:-1]
                    elif len(clean_headers) == len(r0) and len(clean_headers) == 5 and any(p in clean_headers[3].upper() for p in ['M-O-M', 'W-O-W', 'Y-O-Y']):
                        clean_headers = [col0_name, clean_headers[0], clean_headers[1], clean_headers[3], clean_headers[4]]
                    elif len(r0) == len(clean_headers) + 1:
                        clean_headers = [col0_name] + clean_headers
                    else:
                        clean_headers = [col0_name] + clean_headers[:-1]
                    num_cols = len(clean_headers)

            # If clean_headers[0] is still Unit or Currency, infer true column 0 name from row 0
            if clean_headers and clean_headers[0].lower() in ['unit', 'currency'] and len(rows) > 0 and len(rows[0]) > 0:
                first_val = rows[0][0].lower().strip('*').strip()
                if any(m in first_val for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                    clean_headers[0] = 'Date'
                elif any(f in first_val.upper() for f in ['IFO', 'VLSFO', 'LSMGO', 'BRENT', 'GAS', 'OIL', 'WTI']):
                    clean_headers[0] = 'Commodity / Fuel'
                elif any(c in first_val.upper() for c in ['USD', 'EUR', 'JPY', 'GBP', 'CNY']):
                    clean_headers[0] = 'Currency'
                elif any(v in first_val.upper() for v in ['CAPE', 'KAM', 'ULTRA', 'HANDY', 'VLCC', 'SUEZ', 'AFRA', 'MR', 'PANAMAX', 'BULK']):
                    clean_headers[0] = 'Vessel Class'
                elif any(s in first_val.upper() for s in ['DRY', 'TNK', 'SCRAP', 'DEMO']):
                    clean_headers[0] = 'Segment'
                else:
                    clean_headers[0] = 'Benchmark'

            # Empty first header cell check
            if clean_headers and clean_headers[0] == '':
                prev_ctx = (' '.join(out[-10:]) + ' ' + extracted_title).upper()
                if len(clean_headers) > 1 and any(d in clean_headers[1].lower() for d in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                    if any(k in prev_ctx for k in ['DEMOLITION', 'RECYCLING']):
                        clean_headers[0] = 'Segment'
                    elif any(k in prev_ctx for k in ['SECONDHAND', 'S&P', 'VALUES']):
                        clean_headers[0] = 'Vessel Class'
                    else:
                        clean_headers[0] = 'Benchmark'
                elif len(clean_headers) > 1 and clean_headers[1].lower() in ['unit', 'currency', 'usd/day', 'usd/mt', 'usd/feu', 'points', 'idx', 'index', 'days']:
                    if any(k in prev_ctx for k in ['DEMOLITION', 'RECYCLING']):
                        clean_headers[0] = 'Segment'
                    elif any(k in prev_ctx for k in ['SECONDHAND', 'S&P', 'VALUES']):
                        clean_headers[0] = 'Vessel Class'
                    elif 'CURRENC' in prev_ctx:
                        clean_headers[0] = 'Currency'
                    elif any(k in prev_ctx for k in ['COMMODIT', 'BUNKER', 'FUEL']):
                        clean_headers[0] = 'Commodity / Fuel'
                    else:
                        clean_headers[0] = 'Route / Benchmark'
                else:
                    clean_headers[0] = 'Route / Benchmark'
                    
            # If row 0 is an embedded section heading like '**REPORTED SALES:**', extract and drop it
            if len(rows) > 0 and len(rows[0]) > 0 and 'REPORTED SALES' in rows[0][0].upper() and all(c == '' for c in rows[0][1:]):
                if not extracted_title:
                    extracted_title = rows[0][0].replace('*', '').strip()
                rows = rows[1:]

            # Check S&P Sales table headers (generic Col 1, Col 2, empty headers, or 'Route / Benchmark' on sales tables)
            prev_ctx = (' '.join(out[-10:]) + ' ' + extracted_title).upper()
            is_sales_ctx = any(k in prev_ctx for k in ['SECONDHAND', 'REPORTED SALES', 'S&P SALES', 'S&P REPORT'])
            has_sales_data = len(rows) > 0 and len(rows[0]) >= 7 and any(b in rows[0][0].upper() for b in ['BULK', 'TANK', 'CONT', 'GAS'])
            
            if (any(c.startswith('Col ') for c in clean_headers) or all(c == '' for c in clean_headers) or (clean_headers[0] in ['', 'Route / Benchmark'] and all(c == '' for c in clean_headers[1:]))) and (is_sales_ctx or has_sales_data):
                if num_cols == 7:
                    clean_headers = ['Category', 'Vessel Name', 'DWT', 'Year', 'Yard / Builder', 'Buyer', 'Price ($m)']
                elif num_cols == 8:
                    clean_headers = ['Category', 'Vessel Name', 'DWT', 'Year', 'Yard / Builder', 'Buyer', 'Price ($m)', 'Details / Comments']
                elif num_cols >= 9:
                    clean_headers = ['Category', 'Vessel Name', 'IMO No.', 'DWT', 'Year', 'Yard / Builder', 'Buyer', 'Price ($m)', 'Details / Comments'] + [f'Note {k}' for k in range(num_cols-9)]

            # Check Date tables with empty trailing column (e.g. | Date | | -> | Date | Value |)
            if len(clean_headers) == 2 and clean_headers[0] == 'Date' and clean_headers[1] == '':
                clean_headers[1] = 'Value'
            elif clean_headers and clean_headers[0] == 'Date':
                for c_idx in range(1, len(clean_headers)):
                    if clean_headers[c_idx] == '':
                        clean_headers[c_idx] = f'Value {c_idx}' if len(clean_headers) > 2 else 'Value'

            # Check FFA table headers where col 0 is vessel class
            if num_cols >= 4 and any(k in clean_headers[0].upper() for k in ['PANAMAX', 'CAPESIZE', 'SUPRAMAX', 'HANDYSIZE']) and any(k in clean_headers[1].upper() for k in ['UNIT', 'USD/DAY', '1']):
                v_class = clean_headers[0]
                prev_ctx = ' '.join(out[-5:]).upper() if len(out) >= 5 else ''
                if v_class.upper() not in prev_ctx:
                    out.append(f'### {v_class}\n')
                clean_headers[0] = 'Tenor'

            # Emit clean title if found
            if extracted_title and len(extracted_title) > 2 and not extracted_title.lower().startswith('col'):
                prev_ctx = ' '.join(out[-5:]).upper() if len(out) >= 5 else ''
                if extracted_title.upper() not in prev_ctx:
                    out.append(f'### {extracted_title}\n')

            num_cols = len(clean_headers)
            out.append('| ' + ' | '.join(clean_headers) + ' |')
            out.append('| ' + ' | '.join(['---'] * num_cols) + ' |')
            for r in rows:
                while len(r) < num_cols:
                    r.append('')
                out.append('| ' + ' | '.join(r[:num_cols]) + ' |')
            out.append('')
            i = j
            continue
            
        out.append(line)
        i += 1
        
    polished = '\n'.join(out)
    return merge_split_sales_table(polished)


def clean_banchero_document_text(text: str, report_week: int, issue_date: str) -> str:
    """
    Cleans running banners, footers, logo markers, and structures the top macro insight.
    """
    # 1. Normalize unicode replacement artifacts
    text = text.replace('\ufffd', '-')

    # 2. Strip running headers and footer artifacts
    text = re.sub(r'(?m)^[ \t]*#+\s*COMMENT(?:\s+MARKET\s+REPORT.*)?\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*#+\s*.*?(?:MARKET\s+REPORT|RESEARCH|DERIVATIVES|CHARTERING).*?WEEK\s*\d+/\d{4}(?:\s+\d+)?\s*$', '', text, flags=re.I)
    text = re.sub(r'(?m)^[ \t]*(?:CHARTERING|DERIVATIVES|COMMODITIES|NEWS)\s+\d+\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*#+\s*RESEARCH\s*[IVX\d]*\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*RESEARCH\s*[IVX\d]*\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*<!--\s*page\s*\d+\s*-->\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*\[?\s*banchero\s+costa\s+RESEARCH\s*\]?[ \t]*$', '', text, flags=re.I)
    text = re.sub(r'(?m)\[?\s*banchero\s+costa\s+RESEARCH\s*\]?', '', text, flags=re.I)
    text = re.sub(r'(?m)\bebc\s+banchero\s+costa\s+RESEARCH\b', '', text, flags=re.I)
    text = re.sub(r'(?m)^[ \t]*#+\s*ebc\s*$', '', text, flags=re.I)
    text = re.sub(r'(?m)^[ \t]*ebc\s*$', '', text, flags=re.I)

    # 2. Fix typos, double hashes, and spacing
    text = re.sub(r'(?m)^[ \t]*#+\s*#+\s*SUPRAMAX', '# SUPRAMAX', text)
    text = re.sub(r'(?m)^[ \t]*#+\s*#+\s*', '## ', text)
    text = re.sub(r'(?m)^[ \t]*#+\s*(?:NEWS|COMMODITIES)\s*$', '', text)
    text = re.sub(r'\bmln tin\b', 'mln t in', text)
    text = re.sub(r'\blaycan(\d+)', r'laycan \1', text)
    text = re.sub(r'y-\s*o-y', 'y-o-y', text)

    # 3. Structure top Macro Thematic Essay header
    # Check if text begins with article header (e.g. # CHINA SOYBEAN IMPORTS)
    m_art = re.search(r'^\s*#+\s+([A-Z0-9\s,\-\'\/\&]{4,80})\n', text)
    if m_art:
        art_title = m_art.group(1).strip()
        text = text[m_art.end():].lstrip()
        top_header = f"# Banchero Costa Weekly Market Report - Week {report_week:02d}, {issue_date[:4]}\n\n## Weekly Macro Insight: {art_title.title()}\n\n"
        text = top_header + text
    else:
        # Check first 5 lines
        lines = text.splitlines()
        for idx in range(min(5, len(lines))):
            m_l = re.match(r'^\s*#+\s+([A-Z0-9\s,\-\'\/\&]{4,80})$', lines[idx])
            if m_l and not any(k in m_l.group(1).upper() for k in ['NEWS', 'COMMODITY', 'CAPESIZE', 'MARKET', 'WEEK']):
                art_title = m_l.group(1).strip()
                lines[idx] = f"# Banchero Costa Weekly Market Report - Week {report_week:02d}, {issue_date[:4]}\n\n## Weekly Macro Insight: {art_title.title()}"
                text = '\n'.join(lines)
                break

    # Clean multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def build_final_md_and_tables(stem: str, pdf_path: Path):
    """
    Reads LlamaParse markdown and creates:
    1. data/extracted/md/banchero_costa/<stem>.md with YAML frontmatter (HTML tables converted to markdown)
    2. data/extracted/md/banchero_costa/<stem>.tables.json
    3. Mirrored into data/extracted/md/banchero_costa/<year>/
    """
    raw_path = RAW_OUT_DIR / f"{stem}.md"
    if not raw_path.exists():
        return

    content = raw_path.read_text(encoding="utf-8")
    if "<table" in content.lower():
        content = re.sub(r"<table[\s\S]*?</table>", html_table_to_markdown, content, flags=re.I)

    # Polish all markdown tables (unpack <br/> headers, prune dummy columns, prune fake chart tables, normalize headers)
    content = polish_markdown_tables(content)

    report_week, issue_date = parse_date_and_week(pdf_path)

    # Clean frontmatter
    frontmatter = f"""---
title: "Banchero Costa Weekly Market Report - Week {report_week:02d} {issue_date[:4]}"
issue_date: "{issue_date}"
report_week: {report_week}
year: {issue_date[:4]}
broker: "Banchero Costa"
source_file: "corpus/01-brokers/banchero_costa/{pdf_path.parent.name}/{pdf_path.name}"
parsed_engine: "LlamaParse tier=cost_effective version=latest"
---

"""
    cleaned_body = clean_banchero_document_text(content, report_week, issue_date)
    full_md = frontmatter + cleaned_body

    # Save to both flat root and year subfolder
    MD_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md_path = MD_OUT_DIR / f"{stem}.md"
    out_md_path.write_text(full_md, encoding="utf-8")

    year_dir = MD_OUT_DIR / issue_date[:4]
    year_dir.mkdir(parents=True, exist_ok=True)
    (year_dir / f"{stem}.md").write_text(full_md, encoding="utf-8")

    # Extract tables into .tables.json sidecar
    tables_data = extract_structured_tables_from_md(cleaned_body, issue_date, report_week, pdf_path.name)
    out_json_path = MD_OUT_DIR / f"{stem}.tables.json"
    out_json_path.write_text(json.dumps(tables_data, indent=2), encoding="utf-8")
    (year_dir / f"{stem}.tables.json").write_text(json.dumps(tables_data, indent=2), encoding="utf-8")


# --- commodity-table anchors (layout-independent; see the commodity branch below) ---
_UNIT_RX = re.compile(r"^[A-Za-z]{2,4}\s*/\s*[A-Za-z0-9]{1,8}$")
# Container-TC row labels: "ConTex" and "NNNN teu (1Y, geared)". Used as a CONTENT
# anchor so a container table is claimed even when its heading carries no "VHSS".
# Unit tokens a VHSS-ConTex / Freightos index row can carry. Used to tell a real
# index row from a container CHART point, which the same heading also carries
# (chart rows put a NUMBER where the unit goes). Content anchor, never an index.
_INDEX_UNITS = {"index", "idx", "points", "usd/day", "usd/feu", "usd/mt", "usd/t", "usd", "$", "ws"}

_VHSS_ROW_RX = re.compile(r"^(?:ConTex|\d{3,4}\s*teu)\b", re.I)
_NUMSHAPE_RX = re.compile(r"^[+-]?[0-9][0-9,]*(\.[0-9]+)?$")
_COMMODITY_HEADER_WORDS = {
    "category", "item", "unit", "route", "benchmark", "location",
    "route / benchmark", "route/benchmark", "commodity prices",
    "commodity", "commodity / fuel", "commodity/fuel", "product", "products",
}
_COMMODITY_CATEGORIES = {"BUNKERS", "OIL & GAS", "AGRICULTURAL", "COAL", "IRON ORE & STEEL"}


def extract_structured_tables_from_md(
    md_text: str,
    issue_date: str,
    report_week: int,
    source_file: str
) -> Dict[str, Any]:
    """
    Extracts structured tables from clean markdown into standardized schemas:
    - reported_sales (IMO, vessel, type, dwt, built, yard, buyer, price, etc.)
    - freight_benchmarks (Capesize, Panamax, Supramax, Handysize, Tankers)
    - ffa_assessments (Dry bulk forward curves)
    - newbuilding_prices
    - demolition_assessments
    - secondhand_assessments
    - container_fixtures
    - vhss_contex
    - freightos_index
    - currencies
    - commodity_prices
    - chart_series
    """
    result = {
        "metadata": {
            "issue_date": issue_date,
            "report_week": report_week,
            "source_file": source_file,
        },
        "reported_sales": [],
        "freight_benchmarks": [],
        "ffa_assessments": [],
        "newbuilding_prices": [],
        "demolition_assessments": [],
        "secondhand_assessments": [],
        "container_fixtures": [],
        "vhss_contex": [],
        "freightos_index": [],
        "currencies": [],
        "commodity_prices": [],
        "chart_series": [],
    }

    lines = md_text.splitlines()
    current_h1 = ""
    current_h2 = ""
    current_h3 = ""

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("# "):
            current_h1 = line[2:].strip()
            current_h2 = ""
            current_h3 = ""
        elif line.startswith("## "):
            current_h2 = line[3:].strip()
            current_h3 = ""
        elif line.startswith("### "):
            current_h3 = line[4:].strip()

        if "|" in line and i + 1 < len(lines) and any(s in lines[i+1].replace(" ", "") for s in ["|---", "|:---"]):
            raw_headers = [c.strip().strip("*") for c in line.split("|")[1:-1]]
            headers = []
            for h in raw_headers:
                c = re.sub(r"<[^>]+>", " ", h).strip()
                if ":" in c:
                    c = c.split(":")[-1].strip()
                headers.append(c)
            # Find the end of table block
            j = i + 2
            while j < len(lines) and "|" in lines[j]:
                j += 1

            # Check if columns contain embedded rows separated by <br/>
            if any(h.count("<br/>") >= 2 for h in raw_headers):
                col_data = []
                unpacked_headers = []
                for h in raw_headers:
                    parts = [p.strip() for p in h.split("<br/>") if p.strip()]
                    hdr = ""
                    items = []
                    for p_idx, p in enumerate(parts):
                        if any(k in p.upper() for k in ["TYPE", "VESSEL NAME", "IMO", "DWT", "BLT", "YARD", "BUYER", "PRICE", "SS", "NOTE", "UNIT", "W-O-W", "Y-O-Y"]):
                            hdr = p
                            if ":" in hdr:
                                hdr = hdr.split(":")[-1].strip()
                            items = parts[p_idx + 1:]
                            break
                    unpacked_headers.append(hdr if hdr else (parts[0] if parts else ""))
                    col_data.append(items)

                if any(len(c) > 0 for c in col_data):
                    headers = unpacked_headers
                    max_len = max(len(c) for c in col_data)
                    rows = []
                    for r_idx in range(max_len):
                        r = [col_data[c][r_idx] if r_idx < len(col_data[c]) else "" for c in range(len(col_data))]
                        rows.append(r)
                else:
                    rows = []
            else:
                rows = []
                k = i + 2
                while k < j:
                    cells = [c.strip().strip("*").replace("~~", "") for c in lines[k].split("|")[1:-1]]
                    if any(cells):
                        rows.append(cells)
                    k += 1

            ctx = f"{current_h1} / {current_h2} / {current_h3}".upper()
            header_str = " ".join(headers).lower()

            # If row 0 contains table headers (e.g. when table header line was just 'REPORTED SALES :')
            if len(rows) > 0 and len(rows[0]) >= 3 and any(k in rows[0][0].upper() for k in ["TYPE", "VESSEL"]) and any(k in rows[0][1].upper() or k in rows[0][2].upper() for k in ["VESSEL", "NAME", "IMO"]):
                headers = rows[0]
                rows = rows[1:]
                header_str = " ".join(headers).lower()

            # 1. Reported Sales table
            is_sales_table = False
            if (any(k in ctx for k in ["REPORTED SALES", "SECONDHAND SALES", "REPORTED SECONDHAND"]) or any(k in header_str for k in ["reported sales", "reported secondhand"])) and not any(k in ctx for k in ["DEMOLITION", "NEWBUILDING", "CONTAINER", "BALTIC SECONDHAND"]):
                if not any(k in header_str for k in ["bunker", "brent", "oil", "gas", "coal", "iron", "steel", "wheat", "corn", "sugar", "palm"]):
                    if any(k in header_str for k in ["vessel", "buyer", "price", "dwt", "blt", "built", "year"]) or any(len(r) > 0 and r[0].lower() in ["bulk", "tank", "container", "gas", "lpg"] for r in rows):
                        is_sales_table = True
            elif "imo" in header_str and any(k in header_str for k in ["vessel", "buyer", "price", "dwt"]):
                is_sales_table = True

            if is_sales_table:
                for r in rows:
                    deal = normalize_sales_row(r, headers, issue_date, report_week, source_file)
                    if deal:
                        result["reported_sales"].append(deal)

            # 2. FFA Assessments
            # Anchored on the TABLE, never on ctx alone. The EXCHANGE RATES table and the
            # FFA forward-curve CHART tables also sit under the FFA heading in many issues
            # (the heading tracker keeps h1 = "DRY BULK FFA ASSESSMENTS" while h2/h3 move
            # on), so a bare ctx test swallowed them. Measured over 244 docs / 1,881
            # FFA-branch tables: 7 currency tables (28 rows) were filed as FFA assessments
            # AND were missing from bancosta_fx_series.csv; 3 chart tables published curve
            # titles ("CAPESIZE FORWARD CURVE (USD/DAY)", "JPY/USD EXCHANGE RATE") as tenors
            # (9 rows); 4 all-empty section rows ("Capesize | | | ...") were emitted as
            # assessments; and 2026_W19's table has no Tenor column at all, so a positional
            # read shifted every value one place.
            elif "FFA" in ctx or "PREMIUM" in header_str:
                if os.environ.get("BC_DUMP_FFA"):
                    with open(os.environ["BC_DUMP_FFA"], "a", encoding="utf-8") as _f:
                        _f.write(json.dumps({"doc": source_file, "ctx": ctx, "hdr": header_str, "rows": len(rows), "row0": (rows[0] if rows else None)}) + chr(10))
                _h0 = headers[0].strip().lower() if headers else ""
                _data = [r for r in rows if any(c.strip() for c in r)]
                # Uppercase on purpose: the FX table's codes are USD/EUR, CNY/USD, ...
                # while a rate UNIT is "usd/day" - a case-insensitive test matched the unit.
                _ccy = re.compile(r"[A-Z]{3}/[A-Z]{3}")
                _is_fx = _h0 == "currencies" or (len(_data) > 0 and all(_ccy.fullmatch((r[0] or "").strip()) for r in _data))
                # 2026_W19: the publisher's table lost its Tenor column entirely (the parse
                # returns "Unit | 11-May | 4-May | W-o-W | Premium"), so cell 0 is the UNIT,
                # not a tenor - read it that way instead of shifting the row left.
                _no_tenor_col = _h0 == "currency" and "premium" in header_str and "unit" not in header_str

                v_class = "Capesize"
                if "PANAMAX" in ctx:
                    v_class = "Panamax"
                elif "SUPRAMAX" in ctx:
                    v_class = "Supramax"
                elif "HANDY" in ctx:
                    v_class = "Handysize"

                if _is_fx:
                    # Exchange-rate table that shares the FFA heading -> its own tier
                    for r in _data:
                        if len(r) >= 3:
                            result["currencies"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "currency_pair": r[0].strip(),
                                "rate_current": r[1].strip(),
                                "rate_previous": r[2].strip(),
                                "source_file": source_file
                            })
                elif "date" in header_str and "value" in header_str:
                    # FFA Forward Curve Chart
                    for r in rows:
                        if len(r) >= 2:
                            result["chart_series"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "category": f"FFA_{v_class}_Forward_Curve",
                                "date_or_tenor": r[0].strip(),
                                "value": r[1].strip(),
                                "source_file": source_file
                            })
                elif _no_tenor_col:
                    for r in _data:
                        if len(r) >= 4 and any(c.strip() for c in r[1:]):
                            result["ffa_assessments"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "vessel_class": v_class,
                                "tenor": "",
                                "unit": r[0].strip(),
                                "rate_current": r[1].strip(),
                                "rate_previous": r[2].strip(),
                                "change_wow": r[3].strip() if len(r) > 3 else "",
                                "premium": r[4].strip() if len(r) > 4 else "",
                                "source_file": source_file
                            })
                elif "premium" not in header_str:
                    # A chart table under the FFA heading (header is "Category" + dates, or a
                    # lone curve title). Its rows are chart points, not assessments - keep
                    # them as chart series instead of publishing curve titles as tenors.
                    for r in _data:
                        if len(r) >= 2 and r[0].strip().lower() not in ("date", "value", "category"):
                            result["chart_series"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "category": f"FFA_{v_class}_Forward_Curve",
                                "date_or_tenor": r[0].strip(),
                                "value": r[1].strip(),
                                "source_file": source_file
                            })
                else:
                    for r in _data:
                        if len(r) >= 4 and any(c.strip() for c in r[1:]):
                            tenor = r[0].strip()
                            unit = r[1].strip() if len(r) > 1 else "usd/day"
                            curr_val = r[2].strip() if len(r) > 2 else ""
                            prev_val = r[3].strip() if len(r) > 3 else ""
                            wow = r[4].strip() if len(r) > 4 else ""
                            prem = r[5].strip() if len(r) > 5 else ""

                            result["ffa_assessments"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "vessel_class": v_class,
                                "tenor": tenor,
                                "unit": unit,
                                "rate_current": curr_val,
                                "rate_previous": prev_val,
                                "change_wow": wow,
                                "premium": prem,
                                "source_file": source_file
                            })

            # 3. Indicative Newbuilding Prices
            elif "NEWBUILDING" in ctx and ("m-o-m" in header_str or "y-o-y" in header_str):
                for r in rows:
                    if len(r) >= 3:
                        v_type = r[0].strip()
                        unit = r[1].strip() if len(r) > 1 else "$/m"
                        price_curr = r[2].strip() if len(r) > 2 else ""
                        result["newbuilding_prices"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "vessel_type": v_type,
                            "price_usd_m": price_curr,
                            "source_file": source_file
                        })

            # 4. Ship Recycling Assessments
            elif ("RECYCLING" in ctx or "DEMOLITION" in ctx) and any(r[0].lower() in ["dry pakistan", "dry india", "dry bangladesh", "tnk pakistan", "tnk india", "tnk bangladesh"] for r in rows if len(r) > 0):
                for r in rows:
                    if len(r) >= 3:
                        country_seg = r[0].strip()
                        unit = r[1].strip() if len(r) > 1 else "$/ldt"
                        price_curr = r[2].strip() if len(r) > 2 else ""
                        result["demolition_assessments"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "segment_country": country_seg,
                            "price_usd_per_ldt": price_curr,
                            "source_file": source_file
                        })

            # 5. Baltic Secondhand Assessments
            elif "SECONDHAND" in ctx and any(k in header_str for k in ["w-o-w", "y-o-y"]) and any(r[0].lower() in ["capesize", "kamsarmax", "ultramax", "vlcc", "suezmax"] for r in rows if len(r) > 0):
                for r in rows:
                    if len(r) >= 3:
                        v_type = r[0].strip()
                        unit = r[1].strip() if len(r) > 1 else "$/m"
                        price_curr = r[2].strip() if len(r) > 2 else ""
                        result["secondhand_assessments"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "vessel_type": v_type,
                            "price_usd_m": price_curr,
                            "source_file": source_file
                        })

            # 6. Container Fixtures
            elif "CONTAINER" in ctx and any(k in header_str for k in ["teu", "teus"]):
                for r in rows:
                    if len(r) >= 5:
                        result["container_fixtures"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "vessel_name": r[0] if len(r) > 0 else "",
                            "built": r[1] if len(r) > 1 else "",
                            "teu": r[2] if len(r) > 2 else "",
                            "teu_14": r[3] if len(r) > 3 else "",
                            "gear": r[4] if len(r) > 4 else "",
                            "account": r[5] if len(r) > 5 else "",
                            "period_mos": r[6] if len(r) > 6 else "",
                            "rate_usd_day": r[7] if len(r) > 7 else "",
                            "source_file": source_file
                        })

            # 7. VHSS ConTex
            elif ("VHSS" in ctx or "contex" in header_str or any(_VHSS_ROW_RX.match(re.sub(r"[*_`]", "", (r[0] if r else "")).strip()) for r in rows))                     and any(len(r) > 1 and r[1].strip().lower() in _INDEX_UNITS for r in rows):
                # The container CHARTS sit under this same heading as markdown tables
                # (| Date | 4250 | 3500 | 2700 | / | Jul-20 | 8000 | 8000 | 8000 |).
                # A fixed index published their chart points as segments; the gate above
                # requires a real unit token so those tables fall through to chart_series.
                for r in rows:
                    if len(r) >= 3 and r[1].strip().lower() in _INDEX_UNITS:
                        result["vhss_contex"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "segment": r[0] if len(r) > 0 else "",
                            "unit": r[1] if len(r) > 1 else "",
                            "value_current": r[2] if len(r) > 2 else "",
                            "value_previous": r[3] if len(r) > 3 else "",
                            "source_file": source_file
                        })

            # 8. Freightos
            elif ("FREIGHTOS" in ctx or "freightos" in header_str)                     and any(len(r) > 1 and r[1].strip().lower() in _INDEX_UNITS for r in rows):
                # Same defect as branch 7: the Freightos CHART tables under this heading
                # were published as routes. Require a real unit token.
                for r in rows:
                    if len(r) >= 3 and r[1].strip().lower() in _INDEX_UNITS:
                        result["freightos_index"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "route_or_index": r[0] if len(r) > 0 else "",
                            "unit": r[1] if len(r) > 1 else "",
                            "value_current": r[2] if len(r) > 2 else "",
                            "value_previous": r[3] if len(r) > 3 else "",
                            "source_file": source_file
                        })

            # 9. Currencies / FX
            # Row anchor: the same heading also carries a transposed CHART table
            # ("| JPY/USD EXCHANGE RATE | Feb-22 | Jun-22 | Oct-22 |" / "| 110 | 120 | 150 |"),
            # which was published as currency_pair="110". Only accept a real XXX/YYY row.
            elif ("EXCHANGE RATES" in ctx or "CURRENC" in ctx or "currencies" in header_str) and any(
                    re.fullmatch(r"[A-Z]{3}/[A-Z]{3}", (r[0] or "").strip()) for r in rows if r):
                for r in rows:
                    if len(r) >= 3 and re.fullmatch(r"[A-Z]{3}/[A-Z]{3}", (r[0] or "").strip()):
                        result["currencies"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "currency_pair": r[0] if len(r) > 0 else "",
                            "rate_current": r[1] if len(r) > 1 else "",
                            "rate_previous": r[2] if len(r) > 2 else "",
                            "source_file": source_file
                        })

            # 10. Commodity Prices
            # Anchor on the UNIT cell, never on a column index. Three table shapes exist
            # across the eras and a fixed index is wrong for two of them:
            #   a) "| BUNKERS | Unit | <d> | <d> | W-o-W | Y-o-Y |"      -> block in the header
            #   b) "| OIL & GAS | Unit | ... |" / "## OIL & GAS" heading -> block in ctx
            #   c) "| Category | Location | Unit | ... |"                 -> real category column
            #   d) "| Route / Benchmark | Unit | ... |"                   -> block only in ctx
            # A positional parse shifted the row one place on the blocks that omit the
            # category cell and lost the item label. Measured on 2022_W02 page 12, where the
            # page prints "Crude Oil Shanghai | rmb/bbl | 533.4 | 515.7 | +3.4%" but the
            # sidecar stored item="rmb/bbl", unit=533.4, current=515.7, previous="+3.4%".
            # NB: the gate is "unit"+"w-o-w", NOT the word "category" - the md renders the
            # commodity CHARTS as "| Category | Date | Value |" tables, so matching on
            # "category" parsed chart points as prices (item "Jul-20", unit 380).
            elif "COMMODITY PRICES" in ctx and ("w-o-w" in header_str or "y-o-y" in header_str) and (
                    "unit" in header_str
                    or any(_UNIT_RX.match(re.sub(r"[*_`]", "", c).strip()) for r in rows for c in r)):
                _h0 = headers[0].strip() if headers else ""
                _has_cat_col = _h0.lower() == "category"
                if _h0 and not _has_cat_col and _h0.lower() not in _COMMODITY_HEADER_WORDS                         and not _NUMSHAPE_RX.match(_h0):
                    curr_cat = _h0
                else:
                    curr_cat = next((part.strip() for part in reversed(ctx.split("/"))
                                     if part.strip() in _COMMODITY_CATEGORIES), "GENERAL")
                for r in rows:
                    if len(r) < 3:
                        continue
                    cells = [re.sub(r"[*_`]", "", c).strip() for c in r]
                    if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                        continue  # markdown separator row
                    ui = next((i for i, c in enumerate(cells) if _UNIT_RX.match(c)), None)
                    if ui is None:
                        # no unit cell -> a block banner row ("**OIL & GAS**", "IFO 380 (3.5%)")
                        head = cells[0]
                        if head and head.lower() not in _COMMODITY_HEADER_WORDS and not _NUMSHAPE_RX.match(head):
                            curr_cat = head
                        continue
                    if ui == 0:
                        continue
                    if _has_cat_col and ui >= 2 and cells[0]:
                        curr_cat = cells[0]
                    item = next((cells[j] for j in range(ui - 1, -1, -1) if cells[j]), "")
                    cur = cells[ui + 1] if len(cells) > ui + 1 else ""
                    prev = cells[ui + 2] if len(cells) > ui + 2 else ""
                    # the current value must look like a price; this also drops the
                    # chart-axis tick rows the old positional parse emitted as prices.
                    if not item or not _NUMSHAPE_RX.match(cur):
                        continue
                    result["commodity_prices"].append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "category": curr_cat,
                        "item": item,
                        "unit": cells[ui],
                        "price_current": cur,
                        "price_previous": prev,
                        "source_file": source_file
                    })
                # The restored markdown can carry the same block twice (cover-to-cover stitch),
                # so drop rows identical in EVERY field within this document. Measured: 120
                # groups / 166 rows, every one of them two copies of one row in one file.
                _seen, _dedup = set(), []
                for _r in result["commodity_prices"]:
                    _k = tuple(sorted(_r.items()))
                    if _k in _seen:
                        continue
                    _seen.add(_k)
                    _dedup.append(_r)
                result["commodity_prices"] = _dedup

            # 10c. Commodity CHART point tables. Under the COMMODITY PRICES heading the md renders
            # each embedded chart as a small table ("| Commodity / Fuel | 14-Jun | 7-Jun | W-o-W |
            # Y-o-Y |" with "| Brent | 75 | 85 | 80 | 70 |"). Its header has no Unit column and
            # its rows carry no unit cell, so branch 10's gate missed it and branch 11 published
            # the chart points as DRY_BULK freight benchmarks. They are chart series, not rates
            # (chart Brent 70 vs the printed table's 93.0 on 2022_W35), so they go to chart_series.
            # Banner rows (all cells empty but the first, e.g. "| BUNKER PRICES @ SINGAPORE (USD/T) |")
            # are dropped rather than published.
            elif "COMMODITY PRICES" in ctx and ("w-o-w" in header_str or "y-o-y" in header_str):
                _cname = ctx.replace(" / ", "_").strip("_") or "COMMODITY_PRICES"
                for r in rows:
                    cells = [re.sub(r"[*_`]", "", c).strip() for c in r]
                    if len(cells) < 2 or not cells[0] or not any(cells[1:]):
                        continue
                    if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                        continue
                    result["chart_series"].append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "chart_name": _cname,
                        "date": cells[0],
                        "values": cells[1:],
                        "source_file": source_file,
                    })

            # 11. Freight Benchmarks (Capesize, Panamax, Supramax, Handysize, Crude Tankers, Product Tankers)
            elif any(k in header_str for k in ["w-o-w", "y-o-y"]) and any(k in header_str for k in ["unit", "20-", "27-", "13-", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                if os.environ.get("BC_DUMP_B11"):
                    with open(os.environ["BC_DUMP_B11"], "a", encoding="utf-8") as _f:
                        _f.write(json.dumps({"doc": source_file, "ctx": ctx, "hdr": header_str, "headers": headers, "nrows": len(rows), "rows": rows[:40]}) + chr(10))
                sector = "DRY_BULK"
                if "CAPESIZE" in ctx:
                    sector = "CAPESIZE"
                elif "PANAMAX" in ctx:
                    sector = "PANAMAX"
                elif "SUPRAMAX" in ctx:
                    sector = "SUPRAMAX"
                elif "HANDY" in ctx:
                    sector = "HANDYSIZE"
                elif "CRUDE" in ctx or "VLCC" in ctx or "SUEZMAX" in ctx or "AFRAMAX" in ctx:
                    sector = "DIRTY_TANKER"
                elif "PRODUCT" in ctx or "CLEAN" in ctx or "DIRTY" in ctx:
                    sector = "CLEAN_TANKER"

                for r in rows:
                    if len(r) >= 4:
                        # Content anchor (layout-independent): this table redesigns
                        # across years. 2021-2022 publish a 7-col
                        # `Category | Name | Unit | <d> | <d> | W-o-W | Y-o-Y` grid and
                        # the Turkish-straits block an 8-col one, so a FIXED index read
                        # put the Name in `unit`, the unit in `rate_current` and dropped
                        # W-o-W/Y-o-Y. Anchor on the cell that IS a unit token; a row with
                        # no unit token is a leaked header/banner/empty row, not data.
                        ui = next((k for k, c in enumerate(r)
                                   if c.strip().lower() in FREIGHT_UNIT_TOKENS), None)
                        if ui is None:
                            continue
                        _parts = [x.strip() for x in r[:ui] if x.strip()]
                        route_name = _parts[0] if _parts else ""
                        for _extra in _parts[1:]:
                            # the publisher writes the TCE sub-route as "<code>-TCE <name>"
                            # (2021 splits it across two cells: "TC1" + "TCE MEG-Japan (75k)")
                            route_name += ("-" if _extra.upper().startswith("TCE") else " ") + _extra
                        unit = r[ui].strip()
                        rate_curr = r[ui + 1].strip() if len(r) > ui + 1 else ""
                        rate_prev = r[ui + 2].strip() if len(r) > ui + 2 else ""
                        wow = r[ui + 3].strip() if len(r) > ui + 3 else ""
                        yoy = r[ui + 4].strip() if len(r) > ui + 4 else ""

                        if route_name and not route_name.lower().startswith("category") and not route_name.lower().startswith("clean") and not route_name.lower().startswith("dirty"):
                            result["freight_benchmarks"].append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "sector": sector,
                                "route_or_benchmark": route_name,
                                "unit": unit,
                                "rate_current": rate_curr,
                                "rate_previous": rate_prev,
                                "change_wow": wow,
                                "change_yoy": yoy,
                                "source_file": source_file
                            })

            # 12. Chart Time Series tables
            elif "date" in header_str and len(rows) > 0 and len(rows[0]) >= 2:
                for r in rows:
                    if len(r) >= 2:
                        result["chart_series"].append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "chart_name": ctx.replace(" / ", "_"),
                            "date": r[0].strip(),
                            "values": r[1:],
                            "source_file": source_file
                        })

            i = j
            continue
        i += 1

    return result


def process_corpus(year: Optional[int] = None, limit: Optional[int] = None, workers: int = 5):
    """
    Runs multi-account parallel processing across the Banchero Costa corpus.
    """
    files = sorted(CORPUS_DIR.glob("**/*.pdf"))
    if year:
        files = [f for f in files if f"_{year}_" in f.name or f"/{year}/" in str(f).replace("\\", "/")]

    state = load_state()
    todo_files = []
    for f in files:
        stem = f.stem
        raw_f = RAW_OUT_DIR / f"{stem}.md"
        if raw_f.exists() and raw_f.stat().st_size > 5000:
            # Generate final MD and tables if missing or needs update
            build_final_md_and_tables(stem, f)
            continue
        todo_files.append(f)

    if limit:
        todo_files = todo_files[:limit]

    logger.info(f"Total files in scope: {len(files)} | Already parsed: {len(files) - len(todo_files)} | To parse: {len(todo_files)}")

    if not todo_files:
        logger.info("All files in scope are already parsed!")
        return

    # Assign files round-robin to accounts
    tasks = []
    for idx, f in enumerate(todo_files):
        acc = ACCOUNTS[idx % len(ACCOUNTS)]
        tasks.append((f, acc, ACCOUNTS))

    logger.info(f"Starting ThreadPoolExecutor with {workers} workers across {len(ACCOUNTS)} accounts...")
    success_count = 0
    fail_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="LlamaWorker") as executor:
        futures = {executor.submit(parse_single_pdf, f, acc, all_acc): f for f, acc, all_acc in tasks}

        for fut in concurrent.futures.as_completed(futures):
            f = futures[fut]
            try:
                ok, stem, err = fut.result()
                if ok:
                    success_count += 1
                    # Build final MD and tables sidecar
                    build_final_md_and_tables(stem, f)
                else:
                    fail_count += 1
                    logger.error(f"FAILED: {stem} -> {err}")
            except Exception as e:
                fail_count += 1
                logger.error(f"EXCEPTION: {f.stem} -> {e}")

    logger.info(f"Completed run: {success_count} succeeded, {fail_count} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="World-Class LlamaParse Runner for Banchero Costa")
    parser.add_argument("--year", type=int, help="Target specific year (e.g. 2026)")
    parser.add_argument("--limit", type=int, help="Limit number of PDFs to process")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers (default 5)")
    args = parser.parse_args()

    process_corpus(year=args.year, limit=args.limit, workers=args.workers)
