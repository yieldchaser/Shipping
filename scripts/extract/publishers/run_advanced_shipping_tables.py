"""
Advanced Shipping S&P, Newbuilding, Demolition & Valuation Extraction Pipeline.

Extracts weekly market data from Advanced Shipping & Trading reports:
1. Reported Sales (Bulk Carriers, Tankers, Containers, Gas, General Cargo)
2. Newbuilding Orders
3. Indicative Demolition Prices ($/ldt for India, Bangladesh, Pakistan, Turkey)
4. Demolition Sales
5. Indicative Second-Hand Prices (Resale, 5Y, 10Y, 15Y for Bulkers & Tankers)
6. Market Commentary (Bulkers Commentary, Tankers Commentary, Freight Notes)
7. Baltic Indices & Time Charter Averages

Enforces:
  - max_page = len(doc) - 3: completely ignores and discards the final 3 pages
    (currencies, stock prices, contact details) from every report.
  - European numeric conventions:
      * '60.000' -> 60,000.0 (period = thousands separator)
      * '34,5' -> 34.5 (comma = decimal separator)

Outputs:
  - data/extracted/md/advanced_shipping/<stem>.md
  - data/extracted/md/advanced_shipping/<stem>.tables.json
  - data/extracted/series/advanced_shipping_sales_series.csv
  - data/extracted/series/advanced_shipping_demolition_series.csv
  - data/extracted/series/advanced_shipping_newbuilding_series.csv
  - data/extracted/series/advanced_shipping_secondhand_matrix_series.csv
  - data/extracted/series/advanced_shipping_demo_sales_series.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

# OCR fallback for vector-rendered glyphs
try:
    import pytesseract
    from PIL import Image

    TESSERACT_EXE = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if TESSERACT_EXE.exists():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)
        HAS_OCR = True
    else:
        HAS_OCR = False
except Exception:
    HAS_OCR = False

ROOT = Path(__file__).resolve().parents[3]
PUB = "advanced_shipping"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

SALES_SERIES_CSV = OUT_SERIES / "advanced_shipping_sales_series.csv"
DEMO_SERIES_CSV = OUT_SERIES / "advanced_shipping_demolition_series.csv"
NB_SERIES_CSV = OUT_SERIES / "advanced_shipping_newbuilding_series.csv"
SECONDHAND_SERIES_CSV = OUT_SERIES / "advanced_shipping_secondhand_matrix_series.csv"
DEMO_SALES_SERIES_CSV = OUT_SERIES / "advanced_shipping_demo_sales_series.csv"

# ---------------------------------------------------------------------------
# Number & Date Parsing
# ---------------------------------------------------------------------------

DATE_RX = re.compile(
    r"Week\s+(\d+(?:-\d+)?)\s*\((?:.*?\s+to\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\s+(\d{4})\)",
    re.I,
)
FILENAME_DATE_RX = re.compile(r"(\d{1,2})_(\d{1,2})_(\d{4})")
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def clean_text(s: str) -> str:
    """Normalize whitespace and fix unicode font mojibake."""
    if not s:
        return ""
    s = s.replace("\ufffd", "'").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("`", "'")
    return re.sub(r"\s+", " ", s).strip()


def parse_european_number(val: Any) -> Optional[float]:
    """Parse European numeric format.

    - 60.000 -> 60000.0
    - 34,5   -> 34.5
    - 1.380,50 -> 1380.5
    - 0,00%  -> 0.0
    - -1,16% -> -1.16
    """
    if val is None:
        return None
    s = str(val).strip().replace("%", "").replace("$", "").replace("USD", "").replace("usd", "").strip()
    if not s:
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-").strip()
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def parse_price_mill(price_str: str) -> Optional[float]:
    """Extract numeric million USD from price string."""
    if not price_str:
        return None
    p_clean = price_str.replace("$", "").replace("USD", "").replace("usd", "").strip()
    m = re.search(r"(\d+(?:[.,]\d+)?)", p_clean)
    if m:
        return parse_european_number(m.group(1))
    return None


def parse_report_date(doc: pymupdf.Document, pdf_path: Path) -> Tuple[str, str, str]:
    """Extract standardized ISO date (YYYY-MM-DD), week number, and raw period string."""
    for pno in range(min(2, len(doc))):
        txt = doc[pno].get_text()
        m = DATE_RX.search(txt)
        if m:
            wk = m.group(1)
            day = int(m.group(2))
            mon = m.group(3)[:3].lower()
            yr = m.group(4)
            if mon in MONTH_MAP:
                iso = f"{yr}-{MONTH_MAP[mon]:02d}-{day:02d}"
                return iso, wk, m.group(0)

    # Fallback to filename
    m_fn = FILENAME_DATE_RX.search(pdf_path.name)
    if m_fn:
        dd, mm, yyyy = int(m_fn.group(1)), int(m_fn.group(2)), m_fn.group(3)
        return f"{yyyy}-{mm:02d}-{dd:02d}", "0", pdf_path.name

    return "2026-00-00", "0", pdf_path.name


# ---------------------------------------------------------------------------
# High-Value Table Extraction (Ruled Grids)
# ---------------------------------------------------------------------------

KNOWN_HEADERS = {
    "type", "name", "vessel", "dwt", "teu", "cbm", "yob", "yard", "ss",
    "m/e", "gear", "price", "buyer", "buyers", "owner", "owners", "comments",
    "units", "delivery", "ldt", "country", "price $/ldt", "$/ldt",
}


def extract_ruled_tables_from_page(page: pymupdf.Page, page_kind: str) -> List[Dict[str, Any]]:
    """Extract ruled grid tables using cell rectangles and header column anchoring."""
    drawings = page.get_drawings()
    rects = [d["items"][0][1] for d in drawings if d.get("items") and d["items"][0][0] == "re"]

    hdr_candidates = []
    for r in rects:
        if 10 <= r.height <= 30 and 15 <= r.width <= 150 and 100 <= r.y0 <= 750:
            txt = page.get_text("text", clip=r).strip().lower()
            if txt in KNOWN_HEADERS or txt in ("price $/ldt", "$/ldt"):
                hdr_candidates.append((r, txt))

    # Group header cells by y0
    hdr_rows: Dict[float, List[Tuple[pymupdf.Rect, str]]] = {}
    for r, txt in hdr_candidates:
        matched_y = None
        for y in hdr_rows:
            if abs(y - r.y0) < 3.5:
                matched_y = y
                break
        if matched_y is None:
            matched_y = r.y0
            hdr_rows[matched_y] = []
        hdr_rows[matched_y].append((r, txt))

    # Valid headers have at least 5 distinct header columns
    valid_hdr_ys = sorted([y for y, items in hdr_rows.items() if len(set(t for _, t in items)) >= 5])

    tables = []
    for h_idx, hy in enumerate(valid_hdr_ys):
        next_hy = valid_hdr_ys[h_idx + 1] if h_idx + 1 < len(valid_hdr_ys) else 780.0

        # Columns for this table
        col_rects = sorted(hdr_rows[hy], key=lambda x: x[0].x0)
        cols = []
        for r, txt in col_rects:
            if not cols or (r.x0 - cols[-1][1]) > 10:
                orig_col = clean_text(page.get_text("text", clip=r))
                cols.append((orig_col, r.x0, r.x1))

        # Determine section title (Bulk Carriers, Tankers, Containers, etc.)
        sec_rect = pymupdf.Rect(0, max(50, hy - 45), page.rect.width, hy)
        sec_text_lines = [l.strip() for l in page.get_text("text", clip=sec_rect).splitlines() if l.strip()]
        sec_name = "General"
        for candidate_sec in ("Bulk Carriers", "Tankers", "Containers", "Gas", "General Cargo", "Demolition Sales", "Dry Cargo"):
            for line in reversed(sec_text_lines):
                if candidate_sec.lower() in line.lower():
                    sec_name = candidate_sec
                    break
            if sec_name != "General":
                break
        if sec_name == "General" and sec_text_lines:
            sec_name = sec_text_lines[-1]

        # Extract data rows: outer cell rectangles matching left-most column
        left_x = cols[0][1]
        row_rects = [
            r for r in rects
            if hy + 10 < r.y0 < next_hy - 3 and abs(r.x0 - left_x) < 6 and 15 <= r.height <= 35
        ]
        # Dedup rows by y0
        dedup_row_rects = []
        for rr in sorted(row_rects, key=lambda r: r.y0):
            if not dedup_row_rects or abs(dedup_row_rects[-1].y0 - rr.y0) > 4:
                dedup_row_rects.append(rr)

        rows = []
        for rr in dedup_row_rects:
            ry0, ry1 = rr.y0, rr.y1
            row_dict: Dict[str, str] = {}
            for col_name, cx0, cx1 in cols:
                cell_clip = pymupdf.Rect(cx0 - 2, ry0 - 1, cx1 + 2, ry1 + 1)
                val = clean_text(page.get_text("text", clip=cell_clip))
                if not val:
                    # Check for vertically merged cells across multiple rows
                    for mr in rects:
                        if mr.y0 <= ry0 + 2 and mr.y1 >= ry1 - 2 and mr.height > (ry1 - ry0) * 1.3:
                            if abs(mr.x0 - cx0) < 8:
                                val = clean_text(page.get_text("text", clip=mr))
                                break
                row_dict[col_name] = val

            # Keep row ONLY if it has genuine identity (Name / Vessel / Units) and isn't a banner line
            ident = row_dict.get("Name") or row_dict.get("Vessel") or row_dict.get("Units") or ""

            # OCR Fallback if text stream had blank glyphs (rare vector stroking)
            if not ident and HAS_OCR:
                for id_col in ("Name", "Vessel"):
                    if id_col in row_dict:
                        col_info = next((c for c in cols if c[0] == id_col), None)
                        if col_info:
                            c_clip = pymupdf.Rect(col_info[1] - 2, ry0 - 1, col_info[2] + 2, ry1 + 1)
                            pix = page.get_pixmap(clip=c_clip, dpi=300)
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            ocr_txt = clean_text(pytesseract.image_to_string(img, config="--psm 6"))
                            if ocr_txt:
                                row_dict[id_col] = ocr_txt
                                ident = ocr_txt
                                for other_col in ("Type", "Dwt", "YoB", "Yard", "Price", "Buyer", "Ldt"):
                                    if other_col in row_dict and not row_dict[other_col]:
                                        o_info = next((c for c in cols if c[0] == other_col), None)
                                        if o_info:
                                            oc_clip = pymupdf.Rect(o_info[1] - 2, ry0 - 1, o_info[2] + 2, ry1 + 1)
                                            pix_o = page.get_pixmap(clip=oc_clip, dpi=300)
                                            img_o = Image.frombytes("RGB", [pix_o.width, pix_o.height], pix_o.samples)
                                            row_dict[other_col] = clean_text(pytesseract.image_to_string(img_o, config="--psm 6"))
                                break

            if ident and ident.lower() not in (
                "tankers", "bulk carriers", "containers", "gas", "demolition sales", "newbuilding", "type", "units"
            ):
                rows.append(row_dict)

        if rows:
            tables.append({
                "section": sec_name,
                "header": [c[0] for c in cols],
                "rows": rows,
            })

    return tables


# ---------------------------------------------------------------------------
# Indicative Demolition Prices ($/ldt)
# ---------------------------------------------------------------------------

def extract_indicative_demolition_prices(
    doc: pymupdf.Document, issue_date: str, report_week: str, source_file: str, max_page: int
) -> List[Dict[str, Any]]:
    """Extract $/ldt prices for India, Bangladesh, Pakistan, Turkey for Bulkers and Tankers."""
    results = []
    countries = ["india", "bangladesh", "pakistan", "turkey"]

    for pno in range(max_page):
        page = doc[pno]
        txt = page.get_text()
        if "indicative demolition prices" in txt.lower():
            lines = [clean_text(l) for l in txt.splitlines() if l.strip()]
            try:
                idx = [i for i, l in enumerate(lines) if "indicative demolition prices" in l.lower()][0]
                chunk = lines[idx : idx + 45]

                b_idx = [i for i, l in enumerate(chunk) if l.lower() == "bulkers"][0]
                t_idx = [i for i, l in enumerate(chunk) if l.lower() == "tankers"][0]

                b_lines = chunk[b_idx + 1 : t_idx]
                t_lines = chunk[t_idx + 1 : t_idx + 18]

                for seg_name, seg_lines in [("Bulkers", b_lines), ("Tankers", t_lines)]:
                    for j, l in enumerate(seg_lines):
                        if l.lower() in countries and j + 1 < len(seg_lines):
                            price_val = parse_european_number(seg_lines[j + 1])
                            results.append({
                                "issue_date": issue_date,
                                "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
                                "segment": seg_name,
                                "country": l.title(),
                                "price_usd_per_ldt": price_val,
                                "source_file": source_file,
                            })
                if results:
                    break
            except Exception:
                continue

    return results


# ---------------------------------------------------------------------------
# Indicative Second-Hand Prices (Resale, 5Y, 10Y, 15Y)
# ---------------------------------------------------------------------------

VESSEL_CLASS_RX = re.compile(
    r"^(Capesize|Kamsarmax|Panamax|Ultramax|Supramax|Handysize|VLCC|Suezmax|Aframax|MR)\s*(.*)$",
    re.I,
)

BULKER_TEMPLATE = [
    ("Capesize", "180k", "Resale"),
    ("Capesize", "180k", "5 years"),
    ("Capesize", "180k", "10 years"),
    ("Capesize", "176k", "15 years"),
    ("Kamsarmax", "82k", "Resale"),
    ("Kamsarmax", "82k", "5 years"),
    ("Panamax", "78k", "10 years"),
    ("Panamax", "76k", "15 years"),
    ("Ultramax", "64k", "Resale"),
    ("Ultramax", "63k", "5 years"),
    ("Supramax", "58k", "10 years"),
    ("Supramax", "56k", "15 years"),
    ("Handysize", "40k", "Resale"),
    ("Handysize", "37k", "5 years"),
    ("Handysize", "37k", "10 years"),
    ("Handysize", "32k", "15 years"),
]

TANKER_TEMPLATE = [
    ("VLCC", "310k", "Resale"),
    ("VLCC", "310k", "5 years"),
    ("VLCC", "300k", "10 years"),
    ("VLCC", "300k", "15 years"),
    ("Suezmax", "160k", "Resale"),
    ("Suezmax", "160k", "5 years"),
    ("Suezmax", "150k", "10 years"),
    ("Suezmax", "150k", "15 years"),
    ("Aframax", "110k", "Resale"),
    ("Aframax", "110k", "5 years"),
    ("Aframax", "105k", "10 years"),
    ("Aframax", "105k", "15 years"),
    ("MR", "52k", "Resale"),
    ("MR", "51k", "5 years"),
    ("MR", "47k", "10 years"),
    ("MR", "45k", "15 years"),
]

ROW_YS = [182.6, 200.9, 219.2, 237.5, 255.8, 274.1, 292.5, 310.7, 329.1, 347.3, 365.7, 383.9, 402.3, 420.5, 438.9, 457.1]


def format_vessel_class(cls_str: str) -> str:
    """Standardize vessel class capitalization."""
    upper_classes = {"VLCC", "MR", "LR1", "LR2", "LPG", "LNG"}
    u = cls_str.upper()
    return u if u in upper_classes else cls_str.title()


def extract_indicative_secondhand(
    doc: pymupdf.Document, issue_date: str, report_week: str, source_file: str, max_page: int
) -> List[Dict[str, Any]]:
    """Extract second-hand values (Resale, 5Y, 10Y, 15Y) for Bulkers and Tankers."""
    results = []
    pno = None
    for i in range(max_page):
        txt = doc[i].get_text()
        if ("indicative prices" in txt.lower() or "million us$" in txt.lower()) and "demolition" not in txt.lower()[:50]:
            pno = i
            break
    if pno is None:
        return results

    page = doc[pno]
    b_lines = [clean_text(l) for l in page.get_text("text", clip=pymupdf.Rect(15, 150, 300, 480)).splitlines() if l.strip()]
    t_lines = [clean_text(l) for l in page.get_text("text", clip=pymupdf.Rect(300, 150, 585, 480)).splitlines() if l.strip()]

    def parse_panel(lines: List[str], sector: str):
        i = 0
        while i < len(lines):
            line = lines[i]
            m = VESSEL_CLASS_RX.match(line)
            if m:
                v_class = format_vessel_class(m.group(1))
                v_size = m.group(2).strip()
                age = lines[i + 1] if i + 1 < len(lines) else ""
                offset = 2
                if age in ("5", "10", "15") and i + 2 < len(lines) and "year" in lines[i + 2].lower():
                    age = f"{age} years"
                    offset = 3

                cur_val = parse_european_number(lines[i + offset]) if i + offset < len(lines) else None
                prev_val = parse_european_number(lines[i + offset + 1]) if i + offset + 1 < len(lines) else None
                pct_val = parse_european_number(lines[i + offset + 2]) if i + offset + 2 < len(lines) else None

                results.append({
                    "issue_date": issue_date,
                    "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
                    "sector": sector,
                    "vessel_class": v_class,
                    "size_str": v_size,
                    "age": age,
                    "current_price_usd_mill": cur_val,
                    "prior_price_usd_mill": prev_val,
                    "change_pct": pct_val,
                    "source_file": source_file,
                })
                i += offset + 3
            else:
                i += 1

    parse_panel(b_lines, "Bulkers")
    parse_panel(t_lines, "Tankers")

    # Fallback to coordinate-based template alignment if text stream omitted vessel class text
    if not results:
        words = page.get_text("words")
        for idx, target_y in enumerate(ROW_YS):
            b_words = sorted([w for w in words if abs(w[1] - target_y) < 6 and 140 <= w[0] <= 300], key=lambda x: x[0])
            t_words = sorted([w for w in words if abs(w[1] - target_y) < 6 and 430 <= w[0] <= 585], key=lambda x: x[0])

            # Bulker
            if b_words and idx < len(BULKER_TEMPLATE):
                v_class, v_size, age = BULKER_TEMPLATE[idx]
                c_val = parse_european_number(b_words[0][4]) if len(b_words) > 0 else None
                p_val = parse_european_number(b_words[1][4]) if len(b_words) > 1 else c_val
                pct_val = parse_european_number(b_words[2][4]) if len(b_words) > 2 else 0.0
                results.append({
                    "issue_date": issue_date,
                    "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
                    "sector": "Bulkers",
                    "vessel_class": v_class,
                    "size_str": v_size,
                    "age": age,
                    "current_price_usd_mill": c_val,
                    "prior_price_usd_mill": p_val,
                    "change_pct": pct_val,
                    "source_file": source_file,
                })

            # Tanker
            if t_words and idx < len(TANKER_TEMPLATE):
                v_class, v_size, age = TANKER_TEMPLATE[idx]
                c_val = parse_european_number(t_words[0][4]) if len(t_words) > 0 else None
                p_val = parse_european_number(t_words[1][4]) if len(t_words) > 1 else c_val
                pct_val = parse_european_number(t_words[2][4]) if len(t_words) > 2 else 0.0
                results.append({
                    "issue_date": issue_date,
                    "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
                    "sector": "Tankers",
                    "vessel_class": v_class,
                    "size_str": v_size,
                    "age": age,
                    "current_price_usd_mill": c_val,
                    "prior_price_usd_mill": p_val,
                    "change_pct": pct_val,
                    "source_file": source_file,
                })

    return results


# ---------------------------------------------------------------------------
# Commentary & Baltic Indices Extraction
# ---------------------------------------------------------------------------

def extract_page_1_data(page: pymupdf.Page) -> Dict[str, Any]:
    """Extract Bulkers & Tankers commentary and Baltic Indices tables from Page 1."""
    txt = page.get_text()
    lines = [clean_text(l) for l in txt.splitlines() if clean_text(l)]

    # Strip running headers
    filtered = []
    for l in lines:
        if "weekly shipping market report" in l.lower() or re.match(r"^week\s+\d+", l, re.I):
            continue
        filtered.append(l)

    bulkers_text: List[str] = []
    tankers_text: List[str] = []
    baltic_lines: List[str] = []

    mode = None
    for l in filtered:
        l_low = l.lower()
        if l_low == "bulkers" and mode is None:
            mode = "bulkers"
            continue
        elif l_low == "tankers" and mode == "bulkers":
            mode = "tankers"
            continue
        elif "baltic indices" in l_low or l_low == "baltic indices":
            mode = "baltic"
            baltic_lines.append(l)
            continue

        if mode == "bulkers":
            bulkers_text.append(l)
        elif mode == "tankers":
            tankers_text.append(l)
        elif mode == "baltic":
            baltic_lines.append(l)

    # Parse Baltic tables from baltic_lines
    dry_indices = []
    tc_avg = []
    tanker_indices = []

    b_mode = None
    i = 0
    while i < len(baltic_lines):
        l = baltic_lines[i]
        l_low = l.lower()
        if l_low == "index":
            if i + 3 < len(baltic_lines) and ("%" in baltic_lines[i + 3] or "±" in baltic_lines[i + 3]):
                if not dry_indices:
                    b_mode = "dry"
                else:
                    b_mode = "tanker"
                i += 4
                continue
        elif "daily t/c" in l_low:
            if i + 3 < len(baltic_lines) and ("$" in baltic_lines[i + 3] or "±" in baltic_lines[i + 3]):
                b_mode = "tc"
                i += 4
                continue

        if b_mode == "dry":
            if l in ("BDI", "BCI", "BPI", "BSI", "BHSI"):
                v1 = parse_european_number(baltic_lines[i + 1]) if i + 1 < len(baltic_lines) else None
                v2 = parse_european_number(baltic_lines[i + 2]) if i + 2 < len(baltic_lines) else None
                chg = parse_european_number(baltic_lines[i + 3]) if i + 3 < len(baltic_lines) else None
                dry_indices.append({"index": l, "current": v1, "previous": v2, "change_pct": chg})
                i += 4
                continue
        elif b_mode == "tc":
            if any(k in l_low for k in ("capesize", "kamsarmax", "ultramax", "supramax", "handysize")):
                v1 = parse_european_number(baltic_lines[i + 1]) if i + 1 < len(baltic_lines) else None
                v2 = parse_european_number(baltic_lines[i + 2]) if i + 2 < len(baltic_lines) else None
                chg = parse_european_number(baltic_lines[i + 3]) if i + 3 < len(baltic_lines) else None
                tc_avg.append({"vessel": l, "current": v1, "previous": v2, "change_usd": chg})
                i += 4
                continue
        elif b_mode == "tanker":
            if l in ("BDTI", "BCTI") and len(tanker_indices) < 2:
                v1 = parse_european_number(baltic_lines[i + 1]) if i + 1 < len(baltic_lines) else None
                v2 = parse_european_number(baltic_lines[i + 2]) if i + 2 < len(baltic_lines) else None
                chg = parse_european_number(baltic_lines[i + 3]) if i + 3 < len(baltic_lines) else None
                tanker_indices.append({"index": l, "current": v1, "previous": v2, "change_pct": chg})
                i += 4
                continue
        i += 1

    return {
        "bulkers_commentary": " ".join(bulkers_text),
        "tankers_commentary": " ".join(tankers_text),
        "dry_indices": dry_indices,
        "tc_avg": tc_avg,
        "tanker_indices": tanker_indices,
    }


def extract_freight_commentary(page: pymupdf.Page) -> Dict[str, str]:
    """Extract Dry Bulk freight commentary sections (Capesize, Panamax, etc.)."""
    txt = page.get_text()
    if "capesize" not in txt.lower():
        return {}

    lines = [clean_text(l) for l in txt.splitlines() if clean_text(l)]
    lines = [
        l for l in lines
        if not ("weekly shipping market report" in l.lower() or re.match(r"^week\s+\d+", l, re.I) or l.lower() == "dry bulk commentary")
    ]

    sections: Dict[str, str] = {}
    current_sec = None
    sec_lines: List[str] = []
    known_secs = [
        "capesize", "kamsarmax / panamax", "kamsarmax/panamax", "panamax",
        "ultramax / supramax", "ultramax/supramax", "supramax",
        "handymax / handysize", "handysize"
    ]

    for l in lines:
        l_low = l.lower()
        if l_low in known_secs:
            if current_sec and sec_lines:
                sections[current_sec] = " ".join(sec_lines)
                sec_lines = []
            current_sec = l
        elif current_sec:
            if re.match(r"^\d+(\.\d+)?$", l):
                break
            sec_lines.append(l)

    if current_sec and sec_lines:
        sections[current_sec] = " ".join(sec_lines)

    return sections


# ---------------------------------------------------------------------------
# Data Normalization & Formatting
# ---------------------------------------------------------------------------

def normalize_sales_row(
    row: Dict[str, str], section: str, page_num: int, issue_date: str, report_week: str, source_file: str
) -> Dict[str, Any]:
    """Map raw cell dictionary to standard S&P sales record."""
    v_type = row.get("Type", "")
    name = row.get("Name", "")
    dwt_raw = row.get("Dwt", "")
    teu_raw = row.get("Teu", "")
    cbm_raw = row.get("Cbm", "")
    yob_raw = row.get("YoB", "")
    yard = row.get("Yard", "")
    ss = row.get("SS", "")
    engine = row.get("M/E", "")
    gear = row.get("Gear", "")
    price_raw = row.get("Price", "")
    buyer = row.get("Buyer", "") or row.get("Buyers", "")
    comments = row.get("Comments", "")

    dwt_num = parse_european_number(dwt_raw)
    teu_num = parse_european_number(teu_raw)
    cbm_num = parse_european_number(cbm_raw)
    yob_num = int(float(yob_raw)) if yob_raw and yob_raw.isdigit() else None
    price_usd_mill = parse_price_mill(price_raw)

    extra_json = json.dumps({
        "issue_date": issue_date,
        "report_week": report_week,
        "source_file": source_file,
        "raw_price": price_raw,
    }, ensure_ascii=False)

    return {
        "issue": issue_date,
        "report_week": report_week,
        "section": section,
        "page": str(page_num),
        "NAME": name,
        "TYPE": v_type,
        "DWT": f"{dwt_num:,.0f}" if dwt_num else (f"{teu_num:,.0f} teu" if teu_num else (f"{cbm_num:,.0f} cbm" if cbm_num else "")),
        "TEU": teu_num,
        "CBM": cbm_num,
        "BUILT": str(yob_num) if yob_num else yob_raw,
        "YARD": yard,
        "M_E": engine,
        "GEAR": gear,
        "PRICE": price_raw,
        "PRICE_USD_MILL": price_usd_mill,
        "BUYERS": buyer,
        "SS": ss,
        "COMMENTS": comments,
        "source_file": source_file,
        "extra_json": extra_json,
    }


def normalize_newbuilding_row(
    row: Dict[str, str], section: str, page_num: int, issue_date: str, report_week: str, source_file: str
) -> Dict[str, Any]:
    """Map raw cell dictionary to standard Newbuilding record."""
    units = row.get("Units", "")
    dwt_raw = row.get("Dwt", "")
    cbm_raw = row.get("Cbm", "")
    teu_raw = row.get("Teu", "")

    cap_raw = dwt_raw or cbm_raw or teu_raw
    cap_unit = "dwt" if dwt_raw else ("cbm" if cbm_raw else ("teu" if teu_raw else ""))
    cap_num = parse_european_number(cap_raw)

    yard = row.get("Yard", "")
    delivery = row.get("Delivery", "")
    price_raw = row.get("Price", "")
    price_usd_mill = parse_price_mill(price_raw)
    owner = row.get("Owner", "") or row.get("Owners", "")
    comments = row.get("Comments", "")

    return {
        "issue_date": issue_date,
        "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
        "section": section,
        "units": units,
        "capacity": cap_num,
        "capacity_raw": cap_raw,
        "capacity_unit": cap_unit,
        "yard": yard,
        "delivery": delivery,
        "price_raw": price_raw,
        "price_usd_mill": price_usd_mill,
        "owner": owner,
        "comments": comments,
        "page": page_num,
        "source_file": source_file,
    }


def normalize_demo_sales_row(
    row: Dict[str, str], page_num: int, issue_date: str, report_week: str, source_file: str
) -> Dict[str, Any]:
    """Map raw cell dictionary to standard Demolition Sales record."""
    v_type = row.get("Type", "")
    vessel = row.get("Vessel", "")
    dwt_raw = row.get("Dwt", "")
    yob_raw = row.get("YoB", "")
    ldt_raw = row.get("Ldt", "")
    price_raw = row.get("Price $/ldt", "") or row.get("Price", "")
    country = row.get("Country", "")
    comments = row.get("Comments", "")

    dwt_num = parse_european_number(dwt_raw)
    ldt_num = parse_european_number(ldt_raw)
    price_num = parse_european_number(price_raw)
    yob_num = int(float(yob_raw)) if yob_raw and yob_raw.isdigit() else None

    return {
        "issue_date": issue_date,
        "report_week": int(report_week.split("-")[0]) if report_week.isdigit() else report_week,
        "vessel_name": vessel,
        "vessel_type": v_type,
        "dwt": dwt_num,
        "ldt": ldt_num,
        "yob": yob_num,
        "price_usd_per_ldt": price_num,
        "country": country,
        "comments": comments,
        "page": page_num,
        "source_file": source_file,
    }


# ---------------------------------------------------------------------------
# Markdown Generation
# ---------------------------------------------------------------------------

def generate_markdown(
    stem: str,
    pdf_path: Path,
    doc: pymupdf.Document,
    issue_date: str,
    report_week: str,
    raw_date: str,
    all_tables: List[Dict[str, Any]],
    demo_prices: List[Dict[str, Any]],
    secondhand_prices: List[Dict[str, Any]],
    page_1_data: Dict[str, Any],
    freight_data: Dict[str, str],
    max_page: int,
) -> str:
    """Produce clean GitHub-flavored markdown representation of document."""
    try:
        rel_path = pdf_path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel_path = pdf_path.as_posix()

    md_lines = [
        f"# {stem}",
        "",
        f"- **Publisher**: Advanced Shipping & Trading",
        f"- **Issue Date**: {issue_date}",
        f"- **Report Week**: Week {report_week}",
        f"- **Period**: {raw_date}",
        f"- **Source**: `{rel_path}`",
        f"- **Pages**: {len(doc)} (Content: Pages 1 to {max_page}; Final 3 pages excluded)",
        "",
        "---",
        "",
    ]

    for pno in range(max_page):
        page = doc[pno]
        p_num = pno + 1
        md_lines.append(f"## Page {p_num}\n")

        p_text_lower = page.get_text().lower()

        # Page 1: Narrative Commentary & Baltic Tables
        if pno == 0:
            if page_1_data.get("bulkers_commentary"):
                md_lines.append("### Bulkers Market Commentary\n")
                md_lines.append(page_1_data["bulkers_commentary"])
                md_lines.append("")
            if page_1_data.get("tankers_commentary"):
                md_lines.append("### Tankers Market Commentary\n")
                md_lines.append(page_1_data["tankers_commentary"])
                md_lines.append("")
            if page_1_data.get("dry_indices"):
                md_lines.append("### Baltic Dry Indices\n")
                md_lines.append("| Index | Current | Previous | Change (%) |")
                md_lines.append("| --- | --- | --- | --- |")
                for row in page_1_data["dry_indices"]:
                    md_lines.append(f"| {row['index']} | {row['current']} | {row['previous']} | {row['change_pct']}% |")
                md_lines.append("")
            if page_1_data.get("tc_avg"):
                md_lines.append("### Baltic Daily T/C Average\n")
                md_lines.append("| Vessel Type | Current ($) | Previous ($) | Change ($) |")
                md_lines.append("| --- | --- | --- | --- |")
                for row in page_1_data["tc_avg"]:
                    md_lines.append(f"| {row['vessel']} | {row['current']} | {row['previous']} | {row['change_usd']} |")
                md_lines.append("")
            if page_1_data.get("tanker_indices"):
                md_lines.append("### Baltic Tanker Indices\n")
                md_lines.append("| Index | Current | Previous | Change (%) |")
                md_lines.append("| --- | --- | --- | --- |")
                for row in page_1_data["tanker_indices"]:
                    md_lines.append(f"| {row['index']} | {row['current']} | {row['previous']} | {row['change_pct']}% |")
                md_lines.append("")
            continue

        # Page 2: Freight Commentary
        if pno == 1 and freight_data:
            md_lines.append("### Dry Bulk Freight Commentary\n")
            for sec_name, sec_text in freight_data.items():
                md_lines.append(f"#### {sec_name}\n")
                md_lines.append(sec_text)
                md_lines.append("")
            continue

        # Ruled Tables on this page
        p_tables = [t for t in all_tables if t.get("page") == p_num]
        if p_tables:
            for t in p_tables:
                sec = t.get("section", "Table")
                hdr = t.get("header", [])
                rows = t.get("rows", [])
                md_lines.append(f"### {sec}\n")
                if hdr and rows:
                    md_lines.append("| " + " | ".join(hdr) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(hdr)) + " |")
                    for r in rows:
                        row_vals = [str(r.get(c, "")).replace("|", "\\|") for c in hdr]
                        md_lines.append("| " + " | ".join(row_vals) + " |")
                    md_lines.append("")

        # Indicative Demolition Prices
        if "indicative demolition prices" in p_text_lower and demo_prices:
            md_lines.append("### Indicative Demolition Prices ($/ldt)\n")
            md_lines.append("| Country | Bulkers ($/ldt) | Tankers ($/ldt) |")
            md_lines.append("| --- | --- | --- |")
            countries = ["India", "Bangladesh", "Pakistan", "Turkey"]
            for c in countries:
                b_p = next((d["price_usd_per_ldt"] for d in demo_prices if d["country"] == c and d["segment"] == "Bulkers"), "")
                t_p = next((d["price_usd_per_ldt"] for d in demo_prices if d["country"] == c and d["segment"] == "Tankers"), "")
                md_lines.append(f"| {c} | {b_p} | {t_p} |")
            md_lines.append("")

        # Indicative Second-Hand Prices
        if ("indicative prices" in p_text_lower or "million us$" in p_text_lower) and secondhand_prices:
            md_lines.append("### Indicative Second-Hand Prices\n")
            md_lines.append("| Sector | Vessel Class | Size | Age | Current Price ($M) | Prior Price ($M) | Change (%) |")
            md_lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for sh in secondhand_prices:
                md_lines.append(
                    f"| {sh['sector']} | {sh['vessel_class']} | {sh['size_str']} | {sh['age']} | "
                    f"{sh['current_price_usd_mill']} | {sh['prior_price_usd_mill']} | {sh['change_pct']}% |"
                )
            md_lines.append("")

        # Fallback text if no tables or special blocks on this page
        if not p_tables and "indicative" not in p_text_lower and "million us$" not in p_text_lower:
            raw_text = page.get_text().strip()
            clean_lines = []
            for ln in raw_text.splitlines():
                ln_s = ln.strip()
                if not ln_s or "WEEKLY SHIPPING MARKET REPORT" in ln_s or DATE_RX.search(ln_s):
                    continue
                clean_lines.append(ln_s)
            if clean_lines:
                md_lines.append("\n".join(clean_lines))
                md_lines.append("")

    return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Single Document Processing
# ---------------------------------------------------------------------------

def process_document(pdf_path: Path) -> Dict[str, Any]:
    """Process a single Advanced Shipping PDF report."""
    stem = pdf_path.stem
    source_file = pdf_path.name
    doc = pymupdf.open(pdf_path)

    # Completely ignore and discard the final 3 pages
    max_page = max(1, len(doc) - 3)

    issue_date, report_week, raw_date = parse_report_date(doc, pdf_path)

    # Page 1: Commentary & Baltic tables
    page_1_data = extract_page_1_data(doc[0])

    # Page 2: Freight commentary
    freight_data = extract_freight_commentary(doc[1]) if max_page > 1 else {}

    # Ruled Grid Tables (Reported Sales, Newbuilding, Demolition Sales)
    reported_sales_rows: List[Dict[str, Any]] = []
    newbuilding_rows: List[Dict[str, Any]] = []
    demolition_sales_rows: List[Dict[str, Any]] = []
    raw_tables_for_md: List[Dict[str, Any]] = []

    for pno in range(max_page):
        page = doc[pno]
        p_num = pno + 1
        txt = page.get_text()

        is_sales = "reported sales" in txt.lower()
        is_nb = "newbuilding" in txt.lower()
        is_demo = "demolition" in txt.lower()

        if is_sales or is_nb or is_demo:
            tabs = extract_ruled_tables_from_page(page, "SALES" if is_sales else ("NB" if is_nb else "DEMO"))
            for t in tabs:
                t["page"] = p_num
                raw_tables_for_md.append(t)
                sec = t["section"]

                for r in t["rows"]:
                    if is_sales:
                        norm_s = normalize_sales_row(r, sec, p_num, issue_date, report_week, source_file)
                        if norm_s["NAME"]:
                            reported_sales_rows.append(norm_s)
                    elif is_nb:
                        norm_nb = normalize_newbuilding_row(r, sec, p_num, issue_date, report_week, source_file)
                        if norm_nb["units"]:
                            newbuilding_rows.append(norm_nb)
                    elif is_demo and "demolition sales" in sec.lower():
                        norm_ds = normalize_demo_sales_row(r, p_num, issue_date, report_week, source_file)
                        if norm_ds["vessel_name"]:
                            demolition_sales_rows.append(norm_ds)

    # Indicative Demolition Prices
    demo_prices = extract_indicative_demolition_prices(doc, issue_date, report_week, source_file, max_page)

    # Indicative Second-Hand Prices
    secondhand_prices = extract_indicative_secondhand(doc, issue_date, report_week, source_file, max_page)

    # Build Sidecar JSON
    sidecar_json = {
        "stem": stem,
        "source_file": source_file,
        "issue_date": issue_date,
        "report_week": report_week,
        "report_period": raw_date,
        "commentary": {
            "bulkers": page_1_data.get("bulkers_commentary", ""),
            "tankers": page_1_data.get("tankers_commentary", ""),
            "freight": freight_data,
        },
        "baltic_dry_indices": page_1_data.get("dry_indices", []),
        "baltic_tc_average": page_1_data.get("tc_avg", []),
        "baltic_tanker_indices": page_1_data.get("tanker_indices", []),
        "reported_sales": reported_sales_rows,
        "newbuilding": newbuilding_rows,
        "indicative_demolition_prices": demo_prices,
        "demolition_sales": demolition_sales_rows,
        "indicative_secondhand_prices": secondhand_prices,
    }

    # Build Markdown
    doc_md = generate_markdown(
        stem, pdf_path, doc, issue_date, report_week, raw_date,
        raw_tables_for_md, demo_prices, secondhand_prices,
        page_1_data, freight_data, max_page
    )

    # Save Sidecars (natively year-partitioned)
    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    dest_dir = OUT_MD / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{stem}.md").write_text(doc_md, encoding="utf-8")
    (dest_dir / f"{stem}.tables.json").write_text(
        json.dumps(sidecar_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "stem": stem,
        "issue_date": issue_date,
        "report_week": report_week,
        "sales_count": len(reported_sales_rows),
        "nb_count": len(newbuilding_rows),
        "demo_prices_count": len(demo_prices),
        "demo_sales_count": len(demolition_sales_rows),
        "secondhand_count": len(secondhand_prices),
        "sales_rows": reported_sales_rows,
        "demo_prices_rows": demo_prices,
        "nb_rows": newbuilding_rows,
        "secondhand_rows": secondhand_prices,
        "demo_sales_rows": demolition_sales_rows,
    }


# ---------------------------------------------------------------------------
# Corpus Execution & CSV Series Stacking
# ---------------------------------------------------------------------------

SALES_COLUMNS = [
    "issue", "report_week", "section", "page", "NAME", "TYPE", "DWT", "TEU", "CBM",
    "BUILT", "YARD", "M_E", "GEAR", "PRICE", "PRICE_USD_MILL", "BUYERS",
    "SS", "COMMENTS", "source_file", "extra_json"
]

DEMO_COLUMNS = [
    "issue", "report_week", "segment", "country", "price_usd_per_ldt", "source_file"
]

NB_COLUMNS = [
    "issue_date", "report_week", "section", "units", "capacity", "capacity_raw",
    "capacity_unit", "yard", "delivery", "price_raw", "price_usd_mill",
    "owner", "comments", "page", "source_file"
]

SECONDHAND_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_class", "size_str",
    "age", "current_price_usd_mill", "prior_price_usd_mill", "change_pct", "source_file"
]

DEMO_SALES_COLUMNS = [
    "issue_date", "report_week", "vessel_name", "vessel_type", "dwt", "ldt",
    "yob", "price_usd_per_ldt", "country", "comments", "page", "source_file"
]


def write_series_csvs(
    sales_rows: List[Dict[str, Any]],
    demo_prices_rows: List[Dict[str, Any]],
    nb_rows: List[Dict[str, Any]],
    secondhand_rows: List[Dict[str, Any]],
    demo_sales_rows: List[Dict[str, Any]],
):
    """Write all 5 stacked CSV series files."""
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    # 1. Sales Series CSV
    with open(SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SALES_COLUMNS)
        writer.writeheader()
        for r in sales_rows:
            writer.writerow({k: r.get(k, "") for k in SALES_COLUMNS})

    # 2. Demolition Prices Series CSV
    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEMO_COLUMNS)
        writer.writeheader()
        for r in demo_prices_rows:
            writer.writerow({
                "issue": r.get("issue_date", ""),
                "report_week": r.get("report_week", ""),
                "segment": r.get("segment", ""),
                "country": r.get("country", ""),
                "price_usd_per_ldt": r.get("price_usd_per_ldt", ""),
                "source_file": r.get("source_file", ""),
            })

    # 3. Newbuilding Series CSV
    with open(NB_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NB_COLUMNS)
        writer.writeheader()
        for r in nb_rows:
            writer.writerow({k: r.get(k, "") for k in NB_COLUMNS})

    # 4. Secondhand Valuation Matrix Series CSV
    with open(SECONDHAND_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SECONDHAND_COLUMNS)
        writer.writeheader()
        for r in secondhand_rows:
            writer.writerow({k: r.get(k, "") for k in SECONDHAND_COLUMNS})

    # 5. Demolition Sales Series CSV
    with open(DEMO_SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEMO_SALES_COLUMNS)
        writer.writeheader()
        for r in demo_sales_rows:
            writer.writerow({k: r.get(k, "") for k in DEMO_SALES_COLUMNS})


def main():
    parser = argparse.ArgumentParser(description="Advanced Shipping Table Extractor")
    parser.add_argument("--sample", action="store_true", help="Run 3-report sample")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--all", action="store_true", help="Process all 249 corpus files")
    args = parser.parse_args()

    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))

    if args.file:
        target_pdfs = [Path(args.file)]
    elif args.sample:
        # Sample: 2026 week 38 (19_09_2026), plus 2023 W01, 2021 W26
        sample_names = [
            "advanced_shipping_19_09_2026_advanced_shipping_trading_weekly_shipping_marke.pdf",
            "advanced_shipping_2023_W01_ADVANCED-MARKET-REPORT-WEEK-1.pdf",
            "advanced_shipping_2021_W26_ADVANCED-MARKET-REPORT-WEEK-26.pdf",
        ]
        target_pdfs = [p for p in all_pdfs if p.name in sample_names]
    else:
        # Default to all PDFs across 249 reports
        target_pdfs = all_pdfs

    print(f"[{PUB}] Processing {len(target_pdfs)} document(s)...", flush=True)

    all_sales_rows: List[Dict[str, Any]] = []
    all_demo_prices_rows: List[Dict[str, Any]] = []
    all_nb_rows: List[Dict[str, Any]] = []
    all_secondhand_rows: List[Dict[str, Any]] = []
    all_demo_sales_rows: List[Dict[str, Any]] = []
    t0 = time.time()

    for idx, pdf in enumerate(target_pdfs, start=1):
        try:
            res = process_document(pdf)
            all_sales_rows.extend(res["sales_rows"])
            all_demo_prices_rows.extend(res["demo_prices_rows"])
            all_nb_rows.extend(res["nb_rows"])
            all_secondhand_rows.extend(res["secondhand_rows"])
            all_demo_sales_rows.extend(res["demo_sales_rows"])

            el = time.time() - t0
            print(
                f"  [{idx}/{len(target_pdfs)}] {pdf.stem[:52]:<52} "
                f"date={res['issue_date']} wk={res['report_week']} "
                f"sales={res['sales_count']} nb={res['nb_count']} "
                f"demo_p={res['demo_prices_count']} sh={res['secondhand_count']} "
                f"demo_s={res['demo_sales_count']} ({el:.1f}s)",
                flush=True,
            )
        except Exception as e:
            print(f"  [{idx}/{len(target_pdfs)}] {pdf.name} FAILED: {e}", flush=True)
            traceback.print_exc()

    write_series_csvs(
        all_sales_rows,
        all_demo_prices_rows,
        all_nb_rows,
        all_secondhand_rows,
        all_demo_sales_rows,
    )

    print("\n" + "=" * 60)
    print(f"[{PUB}] EXTRACTION COMPLETE in {time.time() - t0:.1f}s")
    print(f"Total documents processed: {len(target_pdfs)}")
    print(f"Total S&P Sales rows stacked: {len(all_sales_rows)}")
    print(f"Total Indicative Demolition Price rows stacked: {len(all_demo_prices_rows)}")
    print(f"Total Newbuilding Order rows stacked: {len(all_nb_rows)}")
    print(f"Total Secondhand Valuation rows stacked: {len(all_secondhand_rows)}")
    print(f"Total Demolition Sales Fixture rows stacked: {len(all_demo_sales_rows)}")
    print(f"Sales series CSV: {SALES_SERIES_CSV}")
    print(f"Demolition prices series CSV: {DEMO_SERIES_CSV}")
    print(f"Newbuilding series CSV: {NB_SERIES_CSV}")
    print(f"Secondhand series CSV: {SECONDHAND_SERIES_CSV}")
    print(f"Demolition sales series CSV: {DEMO_SALES_SERIES_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
