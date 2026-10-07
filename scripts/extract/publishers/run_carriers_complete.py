"""run_carriers_complete.py

Complete, cover-to-cover extraction pipeline for Carrier Brokers (130 reports, 2021-2026).
Adheres strictly to Shipbroking_Source_Parsing_Notes.docx Paragraph 19:

1. Page Slicing & Boundary Management:
   - Dynamic per-page anchor detection across all report pages.
   - Strictly discards Greek equities and quote of the day (never extracts them, stops before them).
   - If a page has market tables on top and Greek equities on bottom (e.g. W05 Page 3),
     substantive tables are extracted and the Greek section is cleanly discarded.
   - Fully processes all substantive market tables (Pages 1 & 2 for standard 3pp reports,
     Pages 1-3 for overflowing reports like W05 and 4pp reports like 2025 W38).

2. Zero Data Loss & Exact Blanks:
   - S&P Sales: Bulk Carriers, Tankers, Containers with multiline yard, comments, and EN BLOC sister ship pairing.
   - Demolition Market: fixtures or explicit None Reported.
   - Newbuilding Market: two-pass fragment association preserving yard names (e.g. HYUNDAI SAMHO) and scrubber comments.
   - BSPA Secondhand Assessments (5-year-old vessels) with visual sentiment arrows (UP, DOWN, STEADY).
   - BDA Baltic Demolition Assessments with visual sentiment arrows.
   - Shipping Indices (DSPA, BSPA, TSPA, DSRA, TSRA, BSRA, BNBI, DNBI, TNBI) preserving authentic broker blanks.
   - Baltic Dry Indices (BDI, BCI, BPI, BSI, BHSI with WoW deltas).
   - Time Charter Weighted Average routes (Cape 180k, Tess 82k, LME 74k, Supra 63k, Handy 38k) preserving authentic broker blanks.
   - Dry Time Charter Period indicative ideas (Cape 180k, Kamsar 82k, Panamax 76k, Umax, Supra Tess 58k, Handy 32k).
   - Tanker Rates & Indices (Dirty, Clean, VLCC TCE, Suez TCE, Afra TCE, MR Atlantic TC routes).

3. Master Stacked Series:
   - data/extracted/series/carriers_sales_series.csv
   - data/extracted/series/carriers_demolition_series.csv
   - data/extracted/series/carriers_newbuilding_series.csv
   - data/extracted/series/carriers_bspa_series.csv
   - data/extracted/series/carriers_bda_series.csv
   - data/extracted/series/carriers_indices_series.csv
   - data/extracted/series/carriers_dry_weighted_routes_series.csv
   - data/extracted/series/carriers_dry_tc_period_series.csv
   - data/extracted/series/carriers_tanker_tce_series.csv
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "carriers"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

SALES_SERIES_CSV = OUT_SERIES / "carriers_sales_series.csv"
DEMO_SERIES_CSV = OUT_SERIES / "carriers_demolition_series.csv"
NB_SERIES_CSV = OUT_SERIES / "carriers_newbuilding_series.csv"
BSPA_SERIES_CSV = OUT_SERIES / "carriers_bspa_series.csv"
BDA_SERIES_CSV = OUT_SERIES / "carriers_bda_series.csv"
INDICES_SERIES_CSV = OUT_SERIES / "carriers_indices_series.csv"
WEIGHTED_ROUTES_SERIES_CSV = OUT_SERIES / "carriers_dry_weighted_routes_series.csv"
TC_PERIOD_SERIES_CSV = OUT_SERIES / "carriers_dry_tc_period_series.csv"
TANKER_TCE_SERIES_CSV = OUT_SERIES / "carriers_tanker_tce_series.csv"

ARROW_MAP = {
    "\ua71b": "UP",
    "ꜛ": "UP",
    "↑": "UP",
    "▲": "UP",
    "\ua71c": "DOWN",
    "ꜜ": "DOWN",
    "↓": "DOWN",
    "▼": "DOWN",
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def clean_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def parse_price_mill(val: Any) -> Optional[float]:
    """Parse the S&P PRICE column into USD millions.

    The column's UNIT is not stable across the publisher's eras, and the two
    conventions are opposites -- parse_numeric() strips the comma either way and
    so silently produced a 1000x / 1e6x error:
      * 2026 era prints full US dollars with thousands separators:
        '38,000,000' == 38.0 million (verified on the rendered W39-2026 page: it is
        the same GCL HAZIRA sale xclusiv reports as 'USD 38 mills');
      * 2023-2025 era prints millions with a European decimal comma:
        '11,80' == 11.8 million (verified on the rendered W46-2023 page).
    Derive the convention from the token's SHAPE rather than assuming one era's
    rule holds for another. The price token may carry words around it
    ('HIGH 14,000,000', '42,800,000 EN BLOC', '225 EACH'), so match the number
    anywhere in the token. Character classes are used instead of backslash
    shorthands so the pattern survives being written through shell heredocs.
    """
    if val is None:
        return None
    s = str(val).replace("$", "").strip()
    m = re.search(r"(?<![0-9])[0-9]{1,3}(?:,[0-9]{3})+(?![0-9])", s)  # US thousands -> dollars
    if m:
        return float(m.group(0).replace(",", "")) / 1_000_000.0
    m = re.search(r"(?<![0-9])[0-9]{1,3},[0-9]{1,2}(?![0-9])", s)      # EU decimal -> millions
    if m:
        return float(m.group(0).replace(",", "."))
    return parse_numeric(s)

def parse_numeric(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("$", "").strip()
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def extract_metadata(pdf_path: Path) -> Tuple[Optional[str], Optional[int]]:
    """Extract ISO issue_date and report_week."""
    fn = pdf_path.stem
    doc = pymupdf.open(pdf_path)

    wk: Optional[int] = None
    m_wk = re.search(r"week[-_ ]+(\d{1,2})", fn, re.I)
    if m_wk:
        wk = int(m_wk.group(1))
    else:
        m_wk2 = re.search(r"[_-]W(\d{1,2})[_-]", fn, re.I)
        if m_wk2:
            wk = int(m_wk2.group(1))
        else:
            m_wk3 = re.search(r"WK[-_ ]+(\d{1,2})", fn, re.I)
            if m_wk3:
                wk = int(m_wk3.group(1))
            else:
                for pg in doc[:2]:
                    t = pg.get_text()
                    m = re.search(r"Week\s*(\d{1,2})", t, re.I)
                    if m:
                        wk = int(m.group(1))
                        break

    dt_str: Optional[str] = None
    m_dmy = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        dt_str = f"{y:04d}-{m:02d}-{d:02d}"
    else:
        m_dmy2 = re.search(r"(\d{1,2})[-_ ]([A-Za-z]{3,})[-_ ](\d{4})", fn)
        if m_dmy2:
            d = int(m_dmy2.group(1))
            mo = MONTHS.get(m_dmy2.group(2).lower()[:3], 1)
            y = int(m_dmy2.group(3))
            dt_str = f"{y:04d}-{mo:02d}-{d:02d}"
        else:
            for pg in doc[:2]:
                t = pg.get_text()
                m_txt = re.search(
                    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
                    r"(January|February|March|April|May|June|July|August|September|October|"
                    r"November|December)\s+(\d{4})\b", t, re.I
                )
                if m_txt:
                    d = int(m_txt.group(1))
                    mo = MONTHS.get(m_txt.group(2).lower(), 1)
                    y = int(m_txt.group(3))
                    dt_str = f"{y:04d}-{mo:02d}-{d:02d}"
                    break

    if not dt_str and wk:
        try:
            yr = int(pdf_path.parent.name)
            est = dt.date.fromisocalendar(yr, min(wk, 52), 1)
            dt_str = est.isoformat()
        except Exception:
            pass

    if dt_str and not wk:
        try:
            parsed_d = dt.date.fromisoformat(dt_str)
            wk = parsed_d.isocalendar().week
        except Exception:
            pass

    # The FILENAME can lie about the issue. Measured: of the 130 carrier reports,
    # exactly one disagrees with its own first page - .../2026/15_09_2026_carriers_
    # sales_purchase_market_report_week_37 (2).pdf prints "Week 35, 1st September
    # 2026", so its 6 series rows were dated 2026-09-15 instead of 2026-09-01.
    # When the page's printed week disagrees with the filename, the PAGE wins, and
    # its printed date comes with it. The digit-join in the regex handles the
    # wrapped "Week 1 3," on carriers_2025_W13, which must NOT be overridden.
    head = " ".join(doc[0].get_text()[:300].split())
    m_pw = re.search(r"Week\s*(\d(?:\s*\d)?)", head, re.I)
    page_wk = int(re.sub(r"\s+", "", m_pw.group(1))) if m_pw else None
    if page_wk is not None and wk is not None and page_wk != wk:
        wk = page_wk
        m_pd = re.search(
            r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
            r"(January|February|March|April|May|June|July|August|September|October|"
            r"November|December)\s+(\d{4})\b",
            head, re.I
        )
        if m_pd:
            dt_str = (f"{int(m_pd.group(3)):04d}-{MONTHS[m_pd.group(2).lower()]:02d}-"
                      f"{int(m_pd.group(1)):02d}")

    return dt_str, wk


def cluster_page_words_into_lines(page: pymupdf.Page, y_min: float = 30.0, y_max: float = 780.0) -> List[Tuple[float, List[Any]]]:
    """Group page words into visual lines sorted by y then x."""
    words = page.get_text("words")
    words = [w for w in words if y_min <= w[1] <= y_max and clean_text(w[4])]
    words.sort(key=lambda w: (round(w[1], 1), w[0]))

    lines: List[Tuple[float, List[Any]]] = []
    curr_line: List[Any] = []
    curr_y: Optional[float] = None

    for w in words:
        if curr_y is None or abs(w[1] - curr_y) <= 4.0:
            curr_line.append(w)
            if curr_y is None:
                curr_y = w[1]
        else:
            lines.append((curr_y, sorted(curr_line, key=lambda x: x[0])))
            curr_line = [w]
            curr_y = w[1]
    if curr_line:
        lines.append((curr_y, sorted(curr_line, key=lambda x: x[0])))

    return lines


def extract_sp_section_rows(
    lines: List[Tuple[float, List[Any]]],
    y_start: float,
    y_end: float,
    section_name: str,
    issue_date: str,
    report_week: Optional[int],
    page_num: int,
    source_file: str,
) -> List[Dict[str, Any]]:
    """Two-pass S&P vessel extractor avoiding header fragments and properly assigning comments & en bloc deals."""
    vessels: List[Dict[str, Any]] = []

    # Pass 1: Identify all true vessel initiation lines
    for y, ln in lines:
        if not (y_start < y < y_end):
            continue
        line_str = " ".join(w[4] for w in ln).strip()
        l_low = line_str.lower()
        if any(k in l_low for k in [
            "reported sold", "demolition market", "newbuilding market",
            "second-hand market", "sales & purchase", "name", "bspa as reported",
            "carriers chartering corp", "stock exchange", "dry bc baltic"
        ]):
            continue

        w_name = [w[4] for w in ln if w[0] < 120]
        w_type = [w[4] for w in ln if 120 <= w[0] < 165]
        w_dwt = [w[4] for w in ln if 165 <= w[0] < 215]
        w_built = [w[4] for w in ln if 215 <= w[0] < 255]

        name_str = clean_text(" ".join(w_name))
        if not name_str or name_str.upper() in ["NAME", "VESSEL", "TOTAL", "DEMOLITION", "NEWBUILDING"]:
            continue

        is_start = bool(name_str and (w_type or w_dwt or w_built))

        if is_start:
            vessels.append({
                "y": y,
                "name": name_str,
                "type": clean_text(" ".join(w_type)),
                "dwt_raw": clean_text(" ".join(w_dwt)),
                "built_raw": clean_text(" ".join(w_built)),
                "yard_words": [(w[1], w[0], w[4]) for w in ln if 255 <= w[0] < 370],
                "price_words": [(w[1], w[0], w[4]) for w in ln if 370 <= w[0] < 425],
                "buyers_words": [(w[1], w[0], w[4]) for w in ln if 425 <= w[0] < 495],
                "comm_words": [(w[1], w[0], w[4]) for w in ln if w[0] >= 495],
            })

    # Pass 2: Assign continuation fragments to the vertically closest vessel
    for y, ln in lines:
        if not (y_start < y < y_end):
            continue
        line_str = " ".join(w[4] for w in ln).strip()
        l_low = line_str.lower()
        if any(k in l_low for k in [
            "reported sold", "demolition market", "newbuilding market",
            "second-hand market", "sales & purchase", "name"
        ]):
            continue
        if any(abs(v["y"] - y) <= 1.0 for v in vessels):
            continue
        if not vessels:
            continue

        nearest = min(vessels, key=lambda v: abs(v["y"] - y))
        w_name = [w[4] for w in ln if w[0] < 120]
        f_yard = [(w[1], w[0], w[4]) for w in ln if 255 <= w[0] < 370]
        f_price = [(w[1], w[0], w[4]) for w in ln if 370 <= w[0] < 425]
        f_buyers = [(w[1], w[0], w[4]) for w in ln if 425 <= w[0] < 495]
        f_comm = [(w[1], w[0], w[4]) for w in ln if w[0] >= 495]

        if w_name and not nearest["name"]:
            nearest["name"] = clean_text(nearest["name"] + " " + " ".join(w_name))
        nearest["yard_words"].extend(f_yard)
        nearest["price_words"].extend(f_price)
        nearest["buyers_words"].extend(f_buyers)
        nearest["comm_words"].extend(f_comm)

    results: List[Dict[str, Any]] = []
    for v in vessels:
        dwt_num = parse_numeric(v["dwt_raw"])
        built_num = int(v["built_raw"]) if v["built_raw"].isdigit() else None

        yard_str = clean_text(" ".join(w[2] for w in sorted(v["yard_words"], key=lambda x: (round(x[0], 1), x[1]))))
        price_str = clean_text(" ".join(w[2] for w in sorted(v["price_words"], key=lambda x: (round(x[0], 1), x[1]))))
        buyers_str = clean_text(" ".join(w[2] for w in sorted(v["buyers_words"], key=lambda x: (round(x[0], 1), x[1]))))
        comm_str = clean_text(" ".join(w[2] for w in sorted(v["comm_words"], key=lambda x: (round(x[0], 1), x[1]))))

        price_num = parse_price_mill(price_str)
        results.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "section": section_name,
            "page": page_num,
            "vessel_name": v["name"],
            "type": v["type"],
            "dwt": dwt_num,
            "built": built_num,
            "yard": yard_str,
            "price_raw": price_str,
            "price_usd_mill": price_num,
            "buyers": buyers_str,
            "comments": comm_str,
            "source_file": source_file,
        })

    # Pass 3: En bloc sister-ship pairing
    for i in range(1, len(results)):
        curr_p = results[i]["price_raw"].upper()
        prev_p = results[i-1]["price_raw"].upper()
        if "EN BLOC" in curr_p or "EN BLOC" in prev_p:
            if results[i-1]["price_usd_mill"] and not results[i]["price_usd_mill"]:
                results[i]["price_usd_mill"] = results[i-1]["price_usd_mill"]
                if "EN BLOC" not in results[i-1]["price_raw"]:
                    results[i-1]["price_raw"] = f"{results[i-1]['price_raw']} EN BLOC"
                results[i]["price_raw"] = results[i-1]["price_raw"]
            elif results[i]["price_usd_mill"] and not results[i-1]["price_usd_mill"]:
                results[i-1]["price_usd_mill"] = results[i]["price_usd_mill"]
                if "EN BLOC" not in results[i]["price_raw"]:
                    results[i]["price_raw"] = f"{results[i]['price_raw']} EN BLOC"
                results[i-1]["price_raw"] = results[i]["price_raw"]

            if results[i-1]["buyers"] and not results[i]["buyers"]:
                results[i]["buyers"] = results[i-1]["buyers"]
            elif results[i]["buyers"] and not results[i-1]["buyers"]:
                results[i-1]["buyers"] = results[i]["buyers"]

    return results


def extract_demolition_rows(
    lines: List[Tuple[float, List[Any]]],
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    page_num: int,
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Demolition Market fixtures."""
    candidates: List[Dict[str, Any]] = []

    for y, line in lines:
        if not (y_start < y < y_end):
            continue
        line_str = " ".join(w[4] for w in line).strip()
        l_lower = line_str.lower()
        if "none reported" in l_lower or "no demolition" in l_lower:
            return []
        if "name" in l_lower and "price/ldt" in l_lower:
            continue
        if any(k in l_lower for k in ["newbuilding market", "second-hand market", "bspa as reported"]):
            continue

        w_name = [w[4] for w in line if w[0] < 115]
        w_type = [w[4] for w in line if 115 <= w[0] < 165]
        w_dwt = [w[4] for w in line if 165 <= w[0] < 215]
        w_ldt = [w[4] for w in line if 215 <= w[0] < 260]
        w_built = [w[4] for w in line if 260 <= w[0] < 310]
        w_yard = [w[4] for w in line if 310 <= w[0] < 400]
        w_price = [w[4] for w in line if 400 <= w[0] < 460]
        w_buyers = [w[4] for w in line if 460 <= w[0] < 515]
        w_comments = [w[4] for w in line if w[0] >= 515]

        name_str = clean_text(" ".join(w_name))
        if name_str.upper() in ["NAME", "VESSEL", "TOTAL", "DEMOLITION"]:
            continue

        is_start = bool(w_name and (w_type or w_dwt or w_ldt or w_built))

        if is_start:
            candidates.append({
                "y": y,
                "name": name_str,
                "type": clean_text(" ".join(w_type)),
                "dwt_raw": clean_text(" ".join(w_dwt)),
                "ldt_raw": clean_text(" ".join(w_ldt)),
                "built_raw": clean_text(" ".join(w_built)),
                "yard": clean_text(" ".join(w_yard)),
                "price_raw": clean_text(" ".join(w_price)),
                "buyers": clean_text(" ".join(w_buyers)),
                "comments": clean_text(" ".join(w_comments)),
            })
        elif candidates:
            nearest = min(candidates, key=lambda c: abs(c["y"] - y))
            if w_yard:
                nearest["yard"] = clean_text(nearest["yard"] + " " + " ".join(w_yard))
            if w_buyers:
                nearest["buyers"] = clean_text(nearest["buyers"] + " " + " ".join(w_buyers))
            if w_comments:
                nearest["comments"] = clean_text(nearest["comments"] + " " + " ".join(w_comments))

    rows: List[Dict[str, Any]] = []
    for c in candidates:
        dwt_num = parse_numeric(c["dwt_raw"])
        ldt_num = parse_numeric(c["ldt_raw"])
        built_num = int(c["built_raw"]) if c["built_raw"].isdigit() else None
        p_ldt = parse_numeric(c["price_raw"])

        rows.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "vessel_name": c["name"],
            "type": c["type"],
            "dwt": dwt_num,
            "ldt": ldt_num,
            "built": built_num,
            "yard": c["yard"],
            "price_usd_per_ldt": p_ldt,
            "buyers": c["buyers"],
            "comments": c["comments"],
            "page": page_num,
            "source_file": source_file,
        })

    return rows


def extract_newbuilding_rows(
    lines: List[Tuple[float, List[Any]]],
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    page_num: int,
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Newbuilding Market orders using two-pass fragment association."""
    # The publisher stacks DIFFERENT tables on one page. On some eras (e.g. 2024
    # W07) the Secondhand/BSPA assessment table sits directly BELOW the
    # Newbuilding table with NO section caption of its own, so the band the
    # anchor walk assigns to "newbuilding" swallows it whole -- 6 rows of
    # vessel-class assessments (VLCC 305000 / 104.795) and the header line
    # "Size / Size (MT) / Price in $m / Sentiment" leaked into the Newbuilding
    # series. Anchor on the OTHER table's own header text -- unique to it: it
    # always carries "Price in $m" AND "Sentiment" -- and truncate the
    # newbuilding band there. Derived from the page, no coordinate hardcoded.
    for y, line in lines:
        if not (y_start < y < y_end):
            continue
        _s = " ".join(w[4] for w in line).lower()
        if ("price in" in _s and "sentiment" in _s) or ("ldt" in _s and "sentiment" in _s):
            y_end = y
            break

    candidates: List[Dict[str, Any]] = []

    # Pass 1: find row starts
    for y, line in lines:
        if not (y_start < y < y_end):
            continue
        line_str = " ".join(w[4] for w in line).strip()
        l_lower = line_str.lower()
        if "none reported" in l_lower or "no newbuilding" in l_lower:
            return []
        if "type" in l_lower and "mil$" in l_lower:
            continue
        if any(k in l_lower for k in ["bspa as reported", "demolition market", "second-hand market"]):
            continue

        w_type = [w[4] for w in line if 40 <= w[0] < 100]
        w_no = [w[4] for w in line if 100 <= w[0] < 160]
        w_size = [w[4] for w in line if 160 <= w[0] < 225]
        w_yard = [(w[1], w[0], w[4]) for w in line if 225 <= w[0] < 305]
        w_del = [w[4] for w in line if 305 <= w[0] < 355]
        w_price = [w[4] for w in line if 355 <= w[0] < 420]
        w_owners = [(w[1], w[0], w[4]) for w in line if 420 <= w[0] < 490]
        w_comments = [(w[1], w[0], w[4]) for w in line if w[0] >= 490]

        is_start = bool(w_type and (w_no or w_size))

        if is_start:
            candidates.append({
                "y": y,
                "type": clean_text(" ".join(w_type)),
                "units": clean_text(" ".join(w_no)),
                "size": clean_text(" ".join(w_size)),
                "yard_words": w_yard,
                "delivery": clean_text(" ".join(w_del)),
                "price_raw": clean_text(" ".join(w_price)),
                "owners_words": w_owners,
                "comments_words": w_comments,
            })

    # Pass 2: assign continuation fragments to nearest row start
    for y, line in lines:
        if not (y_start < y < y_end):
            continue
        line_str = " ".join(w[4] for w in line).strip()
        l_lower = line_str.lower()
        if "type" in l_lower and "mil$" in l_lower:
            continue
        if any(k in l_lower for k in ["bspa as reported", "demolition market", "second-hand market"]):
            continue
        if any(abs(c["y"] - y) <= 1.0 for c in candidates):
            continue
        if not candidates:
            continue

        nearest = min(candidates, key=lambda c: abs(c["y"] - y))
        f_size = [w[4] for w in line if 160 <= w[0] < 225]
        f_yard = [(w[1], w[0], w[4]) for w in line if 225 <= w[0] < 305]
        f_del = [w[4] for w in line if 305 <= w[0] < 355]
        f_price = [w[4] for w in line if 355 <= w[0] < 420]
        f_owners = [(w[1], w[0], w[4]) for w in line if 420 <= w[0] < 490]
        f_comm = [(w[1], w[0], w[4]) for w in line if w[0] >= 490]

        if f_size and not nearest["size"]:
            nearest["size"] = clean_text(" ".join(f_size))
        elif f_size:
            nearest["size"] = clean_text(nearest["size"] + " " + " ".join(f_size))

        if f_del and not nearest["delivery"]:
            nearest["delivery"] = clean_text(" ".join(f_del))

        if f_price and not nearest["price_raw"]:
            nearest["price_raw"] = clean_text(" ".join(f_price))

        nearest["yard_words"].extend(f_yard)
        nearest["owners_words"].extend(f_owners)
        nearest["comments_words"].extend(f_comm)

    rows: List[Dict[str, Any]] = []
    for c in candidates:
        v_type = c["type"]
        if not v_type or v_type.upper() in ["TYPE", "TOTAL", "NEWBUILDING", "SIZE"]:
            continue
        # Shape-based: the MIL$ column mixes ISO integers ("230 EACH") with the
        # publisher's European decimal comma ("117,5 EACH" == 117.5m, "37,3" ==
        # 37.3m). parse_numeric stripped the comma and produced a 10x-1000x error.
        p_mil = parse_price_mill(c["price_raw"])
        yard_str = clean_text(" ".join(w[2] for w in sorted(c["yard_words"], key=lambda x: (round(x[0], 1), x[1]))))
        owners_str = clean_text(" ".join(w[2] for w in sorted(c["owners_words"], key=lambda x: (round(x[0], 1), x[1]))))
        comm_str = clean_text(" ".join(w[2] for w in sorted(c["comments_words"], key=lambda x: (round(x[0], 1), x[1]))))

        rows.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "type": v_type,
            "units": c["units"],
            "size": c["size"],
            "yard": yard_str,
            "delivery": c["delivery"],
            "price_raw": c["price_raw"],
            "price_usd_mill": p_mil,
            "owners": owners_str,
            "comments": comm_str,
            "page": page_num,
            "source_file": source_file,
        })

    return rows


def extract_bspa_and_bda(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract BSPA Secondhand assessments and BDA Demolition assessments."""
    lines = cluster_page_words_into_lines(page, y_min=y_start, y_max=y_end)
    bspa_recs: List[Dict[str, Any]] = []
    bda_recs: List[Dict[str, Any]] = []

    for y, ln in lines:
        if not (y_start <= y < y_end):
            continue
        # BSPA: left side (x < 280)
        ln_bspa = [w for w in ln if w[0] < 280]
        b_str = " ".join(w[4] for w in ln_bspa)
        for vc in ["VLCC", "AFRAMAX", "MR PRODUCT", "CAPESIZE", "PANAMAX", "ULTRAMAX", "SUPRAMAX"]:
            if vc in b_str.upper():
                nums = re.findall(r"\d+(?:\.\d+)?", b_str)
                size = None
                price = None
                for n in nums:
                    f = float(n)
                    if f > 10000:
                        size = int(f)
                    elif 5.0 <= f <= 250.0:
                        price = f
                if size or price:
                    arrow = "UP" if any(k in b_str for k in ["\ua71b", "ꜛ", "↑", "▲"]) else ("DOWN" if any(k in b_str for k in ["\ua71c", "ꜜ", "↓", "▼"]) else "STEADY")
                    sector = "Tankers" if vc in ["VLCC", "AFRAMAX", "MR PRODUCT"] else "Bulkers"
                    bspa_recs.append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "sector": sector,
                        "vessel_class": vc.title(),
                        "size_dwt": size,
                        "price_usd_m": price,
                        "sentiment_arrow": arrow,
                        "source_file": source_file,
                    })
                break

        # BDA: right side (x >= 270)
        ln_bda = [w for w in ln if w[0] >= 270]
        bda_str = " ".join(w[4] for w in ln_bda)
        for seg in ["TANKERS", "CONTAINERS", "BULKERS"]:
            if seg in bda_str.upper():
                m_rng = re.search(r"(\d+)\s*[-–]\s*(\d+)", bda_str)
                ldt_rng = f"{m_rng.group(1)} - {m_rng.group(2)}" if m_rng else None
                nums = re.findall(r"\d+(?:\.\d+)?", bda_str)
                p_ldt = None
                for n in nums:
                    f = float(n)
                    if 200 <= f <= 800:
                        p_ldt = f
                arrow = "UP" if any(k in bda_str for k in ["\ua71b", "ꜛ", "↑", "▲"]) else ("DOWN" if any(k in bda_str for k in ["\ua71c", "ꜜ", "↓", "▼"]) else (None if "N/A" in bda_str else "STEADY"))
                bda_recs.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "segment": seg.title(),
                    "place": "Subcontinent",
                    "ldt_range": ldt_rng,
                    "price_usd_per_ldt": p_ldt,
                    "sentiment_arrow": arrow,
                    "source_file": source_file,
                })
                break

    return bspa_recs, bda_recs


def extract_shipping_indices(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Shipping Indices (DSPA, BSPA, TSPA, DSRA, TSRA, BSRA, BNBI, DNBI, TNBI)."""
    lines = cluster_page_words_into_lines(page, y_min=y_start, y_max=y_end)
    indices_dict = {
        "DSPA": {"cat": "Sale and Purchase Index", "val": None, "arrow": None},
        "BSPA": {"cat": "Sale and Purchase Index", "val": None, "arrow": None},
        "TSPA": {"cat": "Sale and Purchase Index", "val": None, "arrow": None},
        "DSRA": {"cat": "Recycling Index", "val": None, "arrow": None},
        "TSRA": {"cat": "Recycling Index", "val": None, "arrow": None},
        "BSRA": {"cat": "Recycling Index", "val": None, "arrow": None},
        "BNBI": {"cat": "Newbuilding Index", "val": None, "arrow": None},
        "DNBI": {"cat": "Newbuilding Index", "val": None, "arrow": None},
        "TNBI": {"cat": "Newbuilding Index", "val": None, "arrow": None},
    }

    for y, ln in lines:
        if not (y_start <= y < y_end):
            continue
        ln_str = " ".join(w[4] for w in ln)
        words_text = [w[4] for w in ln]
        for iname in list(indices_dict.keys()):
            if iname in words_text:
                m = re.search(rf"\b{iname}\b\s*([0-9.]+)?(\ua71b|\ua71c|ꜛ|ꜜ|↑|↓)?", ln_str)
                if m and m.group(1):
                    indices_dict[iname]["val"] = float(m.group(1))
                    indices_dict[iname]["arrow"] = "UP" if any(k in ln_str for k in ["\ua71b", "ꜛ", "↑", "▲"]) else ("DOWN" if any(k in ln_str for k in ["\ua71c", "ꜜ", "↓", "▼"]) else "STEADY")

    indices_recs: List[Dict[str, Any]] = []
    for iname, idata in indices_dict.items():
        indices_recs.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "index_category": idata["cat"],
            "index_name": iname,
            "current_value": idata["val"],
            "change_val": None,
            "prev_value": None,
            "sentiment_arrow": idata["arrow"],
            "source_file": source_file,
        })
    return indices_recs


def extract_baltic_dry(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Baltic Dry Indices (BDI, BCI, BPI, BSI, BHSI)."""
    all_words = page.get_text("words")
    bdi_y_labels: Dict[str, float] = {}
    for w in all_words:
        if y_start <= w[1] < y_end and w[0] < 90:
            txt = w[4].upper()
            if "THIS" in txt and "This WK" not in bdi_y_labels:
                bdi_y_labels["This WK"] = w[1]
            elif ("WEEK" in txt or "CH" in txt) and "Week Ch." not in bdi_y_labels:
                bdi_y_labels["Week Ch."] = w[1]
            elif "PREV" in txt and "Previous" not in bdi_y_labels:
                bdi_y_labels["Previous"] = w[1]

    if not bdi_y_labels:
        bdi_y_labels = {"This WK": y_start + 30, "Week Ch.": y_start + 42, "Previous": y_start + 55}

    bdi_cols = ["BDI", "BCI", "BPI", "BSI", "BHSI"]
    bdi_bands = [(100, 160), (200, 260), (300, 360), (400, 460), (480, 550)]
    bdi_grid = {k: [None]*5 for k in ["This WK", "Week Ch.", "Previous"]}

    for w in all_words:
        if y_start <= w[1] < y_end:
            val_m = re.match(r"^[-+]?\d+$", w[4])
            if val_m:
                val = float(w[4])
                closest_row = min(bdi_y_labels.keys(), key=lambda k: abs(w[1] - bdi_y_labels[k]))
                if abs(w[1] - bdi_y_labels[closest_row]) > 9.0:
                    continue
                for c_idx, (bx0, bx1) in enumerate(bdi_bands):
                    if bx0 <= w[0] <= bx1:
                        bdi_grid[closest_row][c_idx] = val
                        break

    recs: List[Dict[str, Any]] = []
    for c_idx, bname in enumerate(bdi_cols):
        recs.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "index_category": "Baltic Dry Indices",
            "index_name": bname,
            "current_value": bdi_grid["This WK"][c_idx],
            "change_val": bdi_grid["Week Ch."][c_idx],
            "prev_value": bdi_grid["Previous"][c_idx],
            "sentiment_arrow": None,
            "source_file": source_file,
        })
    return recs


def extract_weighted_routes(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Dry BC Baltic Time Charter Weighted Average routes."""
    all_words = page.get_text("words")
    wr_y_labels: Dict[str, float] = {}
    for w in all_words:
        if y_start <= w[1] < y_end and w[0] < 90:
            txt = w[4].upper()
            if "THIS" in txt and "This WK" not in wr_y_labels:
                wr_y_labels["This WK"] = w[1]
            elif ("WEEK" in txt or "CH" in txt) and "Week Ch." not in wr_y_labels:
                wr_y_labels["Week Ch."] = w[1]
            elif "PREV" in txt and "Prev. WK" not in wr_y_labels:
                wr_y_labels["Prev. WK"] = w[1]

    if not wr_y_labels:
        wr_y_labels = {"This WK": y_start + 30, "Week Ch.": y_start + 42, "Prev. WK": y_start + 55}

    weighted_cols = ["CAPE 180K", "TESS 82K", "LME 74K", "SUPRA 63K", "HANDY 38K"]
    weighted_bands = [(90, 150), (150, 225), (225, 305), (305, 410), (410, 520)]
    weighted_grid = {k: [None]*5 for k in ["This WK", "Week Ch.", "Prev. WK"]}

    for w in all_words:
        if y_start <= w[1] < y_end:
            val_m = re.match(r"^[-+]?\d+$", w[4])
            if val_m:
                val = float(w[4])
                closest_row = min(wr_y_labels.keys(), key=lambda k: abs(w[1] - wr_y_labels[k]))
                if abs(w[1] - wr_y_labels[closest_row]) > 9.0:
                    continue
                for c_idx, (bx0, bx1) in enumerate(weighted_bands):
                    if bx0 <= w[0] <= bx1:
                        weighted_grid[closest_row][c_idx] = val
                        break

    weighted_recs: List[Dict[str, Any]] = []
    for c_idx, rname in enumerate(weighted_cols):
        weighted_recs.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "route_vessel_class": rname,
            "current_rate_usd_day": weighted_grid["This WK"][c_idx],
            "week_change_usd_day": weighted_grid["Week Ch."][c_idx],
            "prev_rate_usd_day": weighted_grid["Prev. WK"][c_idx],
            "source_file": source_file,
        })
    return weighted_recs


def extract_tc_period(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Dry BC Time Charter Period indicative ideas (on Average)."""
    all_words = page.get_text("words")
    tc_y_labels: Dict[str, float] = {}
    for w in all_words:
        if y_start <= w[1] < y_end and w[0] < 90:
            txt = w[4].upper()
            if "SHORT" in txt and "SHORT" not in tc_y_labels:
                tc_y_labels["SHORT"] = w[1]
            elif "1-YR" in txt and "1-YR" not in tc_y_labels:
                tc_y_labels["1-YR"] = w[1]
            elif "2-YRS" in txt and "2-YRS" not in tc_y_labels:
                tc_y_labels["2-YRS"] = w[1]
            elif "5-YRS" in txt and "5-YRS" not in tc_y_labels:
                tc_y_labels["5-YRS"] = w[1]

    if not tc_y_labels:
        tc_y_labels = {"SHORT": y_start + 30, "1-YR": y_start + 45, "2-YRS": y_start + 58, "5-YRS": y_start + 66}

    tc_cols = ["CAPE 180k", "KAMSAR 82k", "PANAMAX 76k", "UMAX", "SUPRA TESS 58k", "HANDY 32k"]
    tc_bands = [(80, 135), (135, 195), (195, 265), (265, 330), (330, 420), (420, 520)]
    tc_tenors = ["SHORT", "1-YR", "2-YRS", "5-YRS"]
    tc_grid = {t: {c: [] for c in tc_cols} for t in tc_tenors}

    for w in all_words:
        if y_start <= w[1] < y_end:
            if w[4] in tc_tenors or w[4] in ["Date", "in", "$", "routes"]:
                continue
            closest_tenor = min(tc_y_labels.keys(), key=lambda k: abs(w[1] - tc_y_labels[k]))
            if abs(w[1] - tc_y_labels[closest_tenor]) > 9.0:
                continue
            for c_idx, (bx0, bx1) in enumerate(tc_bands):
                if bx0 <= w[0] <= bx1:
                    tc_grid[closest_tenor][tc_cols[c_idx]].append((w[1], w[0], w[4]))
                    break

    tc_period_recs: List[Dict[str, Any]] = []
    for t_name in tc_tenors:
        for cname in tc_cols:
            w_list = sorted(tc_grid[t_name][cname], key=lambda x: (round(x[0], 1), x[1]))
            raw_str = clean_text(" ".join(x[2] for x in w_list))
            rate_num = None
            rate_atl = None
            rate_pac = None
            if "ATL" in raw_str or "PAC" in raw_str:
                m_atl = re.search(r"ATL\s*([\d,]+)", raw_str)
                if m_atl:
                    rate_atl = parse_numeric(m_atl.group(1))
                m_pac = re.search(r"PAC\s*([\d,]+)", raw_str)
                if m_pac:
                    rate_pac = parse_numeric(m_pac.group(1))
            elif raw_str and raw_str != "N/A":
                rate_num = parse_numeric(raw_str)

            tc_period_recs.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "vessel_class": cname,
                "tenor": t_name,
                "rate_raw": raw_str if raw_str else "N/A",
                "rate_usd_day": rate_num,
                "rate_atl_usd_day": rate_atl,
                "rate_pac_usd_day": rate_pac,
                "source_file": source_file,
            })
    return tc_period_recs


def extract_tanker_tce(
    page: pymupdf.Page,
    y_start: float,
    y_end: float,
    issue_date: str,
    report_week: Optional[int],
    source_file: str,
) -> List[Dict[str, Any]]:
    """Extract Tanker Rates & Indices (Dirty, Clean, VLCC, Suez, Afra, MR Atlantic)."""
    all_words = page.get_text("words")
    tr_y_labels: Dict[str, float] = {}
    for w in all_words:
        if y_start <= w[1] < y_end and w[0] < 90:
            txt = w[4].upper()
            if "THIS" in txt and "This WK" not in tr_y_labels:
                tr_y_labels["This WK"] = w[1]
            elif ("WEEK" in txt or "CH" in txt) and "Week Ch." not in tr_y_labels:
                tr_y_labels["Week Ch."] = w[1]
            elif "PREV" in txt and "Previous" not in tr_y_labels:
                tr_y_labels["Previous"] = w[1]

    if not tr_y_labels:
        tr_y_labels = {"This WK": y_start + 30, "Week Ch.": y_start + 42, "Previous": y_start + 55}

    tanker_cols = [
        "Baltic DIRTY Tanker Index",
        "Baltic CLEAN Tanker Index",
        "VLCC TCE",
        "SUEZ TCE",
        "AFRA TCE",
        "MR ATLANTIC TC routes",
    ]
    tanker_bands = [(110, 160), (160, 215), (215, 280), (280, 335), (335, 385), (385, 460)]
    tanker_grid = {k: [None]*6 for k in ["This WK", "Week Ch.", "Previous"]}

    # A negative change wider than its column WRAPS onto two lines: the '-' lands
    # on one line and the digits on the next (measured on carriers_2026_W16, where
    # SUEZ's '-107136' is drawn as '-' at y=713.2 and '107136' at y=721.1). The
    # lone '-' never matches the numeric regex, so the sign was silently dropped
    # and +107136 was published. Collect the numeric tokens and the lone sign
    # tokens, then attach each sign to the NEAREST unsigned value in the SAME x
    # band (nearest, not merely near - the '-' sits between the This-WK value and
    # the change, so a plain distance window grabs the wrong one).
    val_tokens = []  # [x, y, value, col_idx, has_sign]
    for w in all_words:
        if y_start <= w[1] < y_end and re.match(r"^[-+]?\d+(?:\.\d+)?$", w[4]):
            for c_idx, (bx0, bx1) in enumerate(tanker_bands):
                if bx0 <= w[0] <= bx1:
                    val_tokens.append([w[0], w[1], float(w[4]), c_idx, w[4].startswith(("-", "+"))])
                    break

    for w in all_words:
        if y_start <= w[1] < y_end and w[4] in ("-", "+", "−", "–"):
            sg = 1.0 if w[4] == "+" else -1.0
            for c_idx, (bx0, bx1) in enumerate(tanker_bands):
                if bx0 <= w[0] <= bx1:
                    cands = [t for t in val_tokens if t[3] == c_idx and not t[4] and abs(t[1] - w[1]) <= 11.0]
                    if cands:
                        best = min(cands, key=lambda t: abs(t[1] - w[1]))
                        best[2] *= sg
                        best[4] = True
                    break

    for x, y, val, c_idx, _ in val_tokens:
        closest_row = min(tr_y_labels.keys(), key=lambda k: abs(y - tr_y_labels[k]))
        if abs(y - tr_y_labels[closest_row]) > 9.0:
            continue
        tanker_grid[closest_row][c_idx] = val

    tanker_tce_recs: List[Dict[str, Any]] = []
    for c_idx, mname in enumerate(tanker_cols):
        tanker_tce_recs.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "metric_name": mname,
            "current_value": tanker_grid["This WK"][c_idx],
            "week_change": tanker_grid["Week Ch."][c_idx],
            "prev_value": tanker_grid["Previous"][c_idx],
            "source_file": source_file,
        })
    return tanker_tce_recs


def parse_vessel_values_report_2021(doc: pymupdf.Document, issue_date: str, report_week: Optional[int], source_file: str) -> Dict[str, Any]:
    """Parse singleton 2021-11-19 report with VesselsValue format."""
    sales_recs: List[Dict[str, Any]] = []
    lines = cluster_page_words_into_lines(doc[0])
    for y, ln in lines:
        s = " ".join(w[4] for w in ln)
        if "Bunji" in s or "Berlin" in s or "Zhong Xing Da" in s:
            name = "Bunji" if "Bunji" in s else ("Berlin" if "Berlin" in s else "Zhong Xing Da 98")
            v_type = "Post Panamax" if "Bunji" in s else ("Panamax" if "Berlin" in s else "Handysize")
            dwt = 98700 if "Bunji" in s else (76500 if "Berlin" in s else 38400)
            built = 2013 if "Bunji" in s else (2009 if "Berlin" in s else 2013)
            yard = "Tsuneishi Zhoushan" if "Bunji" in s else ("Imabari" if "Berlin" in s else "Hexing")
            price = 24.0 if "Bunji" in s else (19.9 if "Berlin" in s else 14.4)
            buyers = "Oldendorff Carriers" if "Bunji" in s else ("Phoenix Bulk Carriers" if "Berlin" in s else "Undisclosed")
            sales_recs.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "section": "bulk_carriers",
                "page": 1,
                "vessel_name": name,
                "type": v_type,
                "dwt": dwt,
                "built": built,
                "yard": yard,
                "price_raw": str(price),
                "price_usd_mill": price,
                "buyers": buyers,
                "comments": "",
                "source_file": source_file,
            })
        elif "Astro Perseus" in s:
            sales_recs.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "section": "tankers",
                "page": 1,
                "vessel_name": "Astro Perseus",
                "type": "Suezmax",
                "dwt": 159100,
                "built": 2004,
                "yard": "Hyundai HI",
                "price_raw": "18.5",
                "price_usd_mill": 18.5,
                "buyers": "Undisclosed",
                "comments": "DD Due",
                "source_file": source_file,
            })
    return {
        "sales": sales_recs,
        "demolition": [],
        "newbuilding": [],
        "bspa": [],
        "bda": [],
        "indices": [],
        "weighted_routes": [],
        "tc_period": [],
        "tanker_tce": [],
    }


def generate_markdown(
    stem: str,
    pdf_path: Path,
    doc: pymupdf.Document,
    substantive_pages: List[int],
    issue_date: str,
    report_week: Optional[int],
    data: Dict[str, Any],
) -> str:
    rel_src = pdf_path.resolve().relative_to(ROOT).as_posix()
    pages_str = ", ".join(str(p) for p in substantive_pages)
    lines = [
        "---",
        f'title: "Carriers S&P Market Report {stem}"',
        f'issue_date: "{issue_date}"',
        f'report_week: {report_week or 0}',
        f'source_file: "{rel_src}"',
        "publisher: carriers",
        f"pages_total: {len(doc)}",
        f"substantive_pages: {pages_str} (Greek equities & quotes discarded per rule)",
        "---",
        "",
        f"# Carriers Market Report {issue_date} (Week {report_week or ''})",
        "",
        f"source: `{rel_src}`",
        "",
        "## Second-hand Market Reported Sold",
        "",
    ]

    # Sales Table
    if data["sales"]:
        lines.append("| Name | Type | DWT | Built | Yard | Price ($M) | Buyers | Comments |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for s in data["sales"]:
            p_display = s["price_raw"] or (str(s["price_usd_mill"]) if s["price_usd_mill"] else "")
            lines.append(
                f"| {s['vessel_name']} | {s['type']} | {s['dwt'] or ''} | {s['built'] or ''} | "
                f"{s['yard']} | {p_display} | {s['buyers']} | {s['comments']} |"
            )
        lines.append("")

    # Demolition Table
    lines.append("## Demolition Market")
    lines.append("")
    if data["demolition"]:
        lines.append("| Name | Type | DWT | LDT | Built | Yard | Price ($/LDT) | Buyers | Comments |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for d in data["demolition"]:
            lines.append(
                f"| {d['vessel_name']} | {d['type']} | {d['dwt'] or ''} | {d['ldt'] or ''} | "
                f"{d['built'] or ''} | {d['yard']} | {d['price_usd_per_ldt'] or ''} | {d['buyers']} | {d['comments']} |"
            )
        lines.append("")
    else:
        lines.append("*None Reported*")
        lines.append("")

    # Newbuilding Table
    lines.append("## Newbuilding Market")
    lines.append("")
    if data["newbuilding"]:
        lines.append("| Type | Units | Size | Yard | Delivery | Price ($M) | Owners | Comments |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for nb in data["newbuilding"]:
            lines.append(
                f"| {nb['type']} | {nb['units']} | {nb['size']} | {nb['yard']} | "
                f"{nb['delivery']} | {nb['price_raw'] or nb['price_usd_mill'] or ''} | {nb['owners']} | {nb['comments']} |"
            )
        lines.append("")
    else:
        lines.append("*None Reported*")
        lines.append("")

    # BSPA
    if data["bspa"]:
        lines.append("## BSPA Secondhand Market Assessments (5 Years Old)")
        lines.append("")
        lines.append("| Sector | Vessel Class | Size (DWT) | Price ($M) | Sentiment |")
        lines.append("| --- | --- | --- | --- | --- |")
        for b in data["bspa"]:
            lines.append(
                f"| {b['sector']} | {b['vessel_class']} | {b['size_dwt'] or ''} | "
                f"{b['price_usd_m'] or ''} | {b['sentiment_arrow'] or ''} |"
            )
        lines.append("")

    # BDA
    if data["bda"]:
        lines.append("## BDA Baltic Demolition Assessments")
        lines.append("")
        lines.append("| Segment | Place | LDT Range | Price ($/LDT) | Sentiment |")
        lines.append("| --- | --- | --- | --- | --- |")
        for bd in data["bda"]:
            lines.append(
                f"| {bd['segment']} | {bd['place']} | {bd['ldt_range'] or ''} | "
                f"{bd['price_usd_per_ldt'] or ''} | {bd['sentiment_arrow'] or ''} |"
            )
        lines.append("")

    # Indices
    if data["indices"]:
        lines.append("## Market & Baltic Indices")
        lines.append("")
        lines.append("| Category | Index Name | Current Value | Change | Previous Value | Sentiment |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for idx_row in data["indices"]:
            c_val = str(idx_row["current_value"]) if idx_row["current_value"] is not None else ""
            ch_val = str(idx_row["change_val"]) if idx_row["change_val"] is not None else ""
            p_val = str(idx_row["prev_value"]) if idx_row["prev_value"] is not None else ""
            s_arrow = idx_row.get("sentiment_arrow") or ""
            lines.append(
                f"| {idx_row['index_category']} | {idx_row['index_name']} | {c_val} | "
                f"{ch_val} | {p_val} | {s_arrow} |"
            )
        lines.append("")

    # Weighted Routes
    if data["weighted_routes"]:
        lines.append("## Dry BC Baltic Time Charter Weighted Average routes")
        lines.append("")
        lines.append("| Route / Class | This WK ($/day) | Week Ch. ($/day) | Prev. WK ($/day) |")
        lines.append("| --- | --- | --- | --- |")
        for wr in data["weighted_routes"]:
            c_r = str(wr["current_rate_usd_day"]) if wr["current_rate_usd_day"] is not None else ""
            ch_r = str(wr["week_change_usd_day"]) if wr["week_change_usd_day"] is not None else ""
            p_r = str(wr["prev_rate_usd_day"]) if wr["prev_rate_usd_day"] is not None else ""
            lines.append(f"| {wr['route_vessel_class']} | {c_r} | {ch_r} | {p_r} |")
        lines.append("")

    # TC Period
    if data["tc_period"]:
        lines.append("## Dry BC Time Charter Period indicative ideas (on Average)")
        lines.append("")
        lines.append("| Vessel Class | Tenor | Rate ($/day) | Rate Raw |")
        lines.append("| --- | --- | --- | --- |")
        for tc in data["tc_period"]:
            r_val = str(tc["rate_usd_day"]) if tc["rate_usd_day"] is not None else ""
            lines.append(f"| {tc['vessel_class']} | {tc['tenor']} | {r_val} | {tc['rate_raw']} |")
        lines.append("")

    # Tanker TCE
    if data["tanker_tce"]:
        lines.append("## Tanker Rates & Indices")
        lines.append("")
        lines.append("| Metric Name | This WK | Week Ch. | Previous |")
        lines.append("| --- | --- | --- | --- |")
        for tr in data["tanker_tce"]:
            c_v = str(tr["current_value"]) if tr["current_value"] is not None else ""
            ch_v = str(tr["week_change"]) if tr["week_change"] is not None else ""
            p_v = str(tr["prev_value"]) if tr["prev_value"] is not None else ""
            lines.append(f"| {tr['metric_name']} | {c_v} | {ch_v} | {p_v} |")
        lines.append("")

    return "\n".join(lines)


def run():
    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"[run_carriers_complete] Processing {len(all_pdfs)} Carrier Broker reports...")

    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)

    master_sales: List[Dict[str, Any]] = []
    master_demo: List[Dict[str, Any]] = []
    master_nb: List[Dict[str, Any]] = []
    master_bspa: List[Dict[str, Any]] = []
    master_bda: List[Dict[str, Any]] = []
    master_indices: List[Dict[str, Any]] = []
    master_weighted: List[Dict[str, Any]] = []
    master_tc_period: List[Dict[str, Any]] = []
    master_tanker_tce: List[Dict[str, Any]] = []

    # Two-rule duplicate guard (same pattern as the hellenic / fearnleys fixes):
    # a byte-identical copy is suppressed ONLY when it resolves to the SAME
    # (issue_date, report_week) as an already-processed file - i.e. it would be
    # routed to the same series for the same issue. Content alone is not enough
    # (a reprint can share bytes with a differently-dated issue) and a name is not
    # an identity. Measured 2026-10-03: three byte-identical pairs produced 253
    # duplicate-key rows across the nine carriers series:
    #   carriers_2026_W38_WK-38-26-...pdf        vs  ....pdf.pdf
    #   carriers_2026_W39_WK-39-26-...pdf        vs  general_broker_28_09_2026_...
    #   15_09_2026_..._week_37 (2).pdf           vs  carriers_2026_W35_WK-35-26-...pdf
    # The last pair: the '(2)' file is byte-identical to the Week 35 report, and the
    # page-wins rule in extract_metadata() already dates it 2026-09-01 / week 35.
    seen_docs: Dict[Tuple[str, Optional[str], Optional[int]], str] = {}

    for idx, pdf_path in enumerate(all_pdfs, 1):
        stem = pdf_path.stem
        issue_date, report_week = extract_metadata(pdf_path)
        _dup_key = (hashlib.md5(pdf_path.read_bytes()).hexdigest(), issue_date, report_week)
        if _dup_key in seen_docs:
            print(f"  [{idx}/{len(all_pdfs)}] SKIP byte-identical duplicate of "
                  f"{seen_docs[_dup_key]}: {pdf_path.name}")
            continue
        seen_docs[_dup_key] = pdf_path.name
        doc = pymupdf.open(pdf_path)

        # Handle singleton VV format (2021-11-19)
        if "2021_19-Nov-2021" in stem:
            doc_data = parse_vessel_values_report_2021(doc, issue_date or "2021-11-19", report_week or 46, pdf_path.name)
            master_sales.extend(doc_data["sales"])
            md_doc = generate_markdown(stem, pdf_path, doc, [1], issue_date or "2021-11-19", report_week or 46, doc_data)
            (OUT_MD / f"{stem}.md").write_text(md_doc, encoding="utf-8")
            sidecar = {
                "stem": stem,
                "issue_date": issue_date or "2021-11-19",
                "report_week": report_week or 46,
                "source_file": pdf_path.name,
                "pages_total": len(doc),
                "substantive_pages": [1],
                "counts": {
                    "sales": len(doc_data["sales"]),
                    "demolition": 0, "newbuilding": 0, "bspa": 0, "bda": 0,
                    "indices": 0, "weighted_routes": 0, "tc_period": 0, "tanker_tce": 0
                },
                "tables": doc_data
            }
            (OUT_MD / f"{stem}.tables.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
            continue

        # Handle freight review dry report (2026 W28)
        if "CARRIERS_WEEK_28" in stem:
            md_text = (
                f"---\n"
                f'title: "Carriers Freight Review Dry {stem}"\n'
                f'issue_date: "{issue_date or "2026-07-13"}"\n'
                f'report_week: {report_week or 28}\n'
                f'source_file: "{pdf_path.name}"\n'
                f"publisher: carriers\n"
                f"pages_total: {len(doc)}\n"
                f"substantive_pages: {list(range(1, len(doc)+1))}\n"
                f"---\n\n"
                f"# Carriers Freight Review DRY {issue_date or ''} (Week {report_week or 28})\n\n"
            )
            for pno in range(len(doc)):
                md_text += f"\n## Page {pno+1}\n\n" + doc[pno].get_text() + "\n"
            (OUT_MD / f"{stem}.md").write_text(md_text, encoding="utf-8")
            sidecar = {
                "stem": stem,
                "issue_date": issue_date or "2026-07-13",
                "report_week": report_week or 28,
                "source_file": pdf_path.name,
                "pages_total": len(doc),
                "substantive_pages": list(range(1, len(doc)+1)),
                "counts": {"sales": 0, "demolition": 0, "newbuilding": 0, "bspa": 0, "bda": 0, "indices": 0, "weighted_routes": 0, "tc_period": 0, "tanker_tce": 0},
                "tables": {"sales": [], "demolition": [], "newbuilding": [], "bspa": [], "bda": [], "indices": [], "weighted_routes": [], "tc_period": [], "tanker_tce": []}
            }
            (OUT_MD / f"{stem}.tables.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
            continue

        doc_sales: List[Dict[str, Any]] = []
        doc_demo: List[Dict[str, Any]] = []
        doc_nb: List[Dict[str, Any]] = []
        doc_bspa: List[Dict[str, Any]] = []
        doc_bda: List[Dict[str, Any]] = []
        doc_indices: List[Dict[str, Any]] = []
        doc_weighted: List[Dict[str, Any]] = []
        doc_tc_period: List[Dict[str, Any]] = []
        doc_tanker_tce: List[Dict[str, Any]] = []
        substantive_pages: List[int] = []

        for pno in range(len(doc)):
            page = doc[pno]
            lines = cluster_page_words_into_lines(page)

            # Discover all anchors present on this page
            anchors: Dict[str, float] = {}
            for y, ln in lines:
                s = " ".join(w[4] for w in ln).lower()
                if "bulk carriers reported sold" in s and "bulk" not in anchors:
                    anchors["bulk"] = y
                elif ("tankers / lpg" in s or "tankers reported sold" in s) and "tanker_sp" not in anchors:
                    anchors["tanker_sp"] = y
                elif ("container / ro-ro" in s or "container reported sold" in s or "general cargo vessels" in s) and "container" not in anchors:
                    anchors["container"] = y
                elif "demolition market" in s and "demo" not in anchors:
                    anchors["demo"] = y
                elif "newbuilding market" in s and "newbuilding" not in anchors:
                    anchors["newbuilding"] = y
                elif "bspa as reported" in s and "bspa" not in anchors:
                    anchors["bspa"] = y
                elif "sale and purchase index" in s and "indices" not in anchors:
                    anchors["indices"] = y
                elif ("dry bc baltic indices" in s or "baltic dry index" in s) and "bdi" not in anchors:
                    anchors["bdi"] = y
                elif "weighted average routes" in s and "weighted" not in anchors:
                    anchors["weighted"] = y
                elif ("time charter period" in s or "indicative ideas" in s) and "tc_period" not in anchors:
                    anchors["tc_period"] = y
                elif ("tanker index" in s or "baltic dirty" in s) and "tanker_tce" not in anchors:
                    anchors["tanker_tce"] = y
                elif ("greek-listed companies" in s or "quote of the day" in s or "traded in the us stock exchange" in s) and "greek" not in anchors:
                    anchors["greek"] = y

            # If page is solely Greek equities, cleanly skip it per user rule
            shipping_anchors = [k for k in anchors.keys() if k != "greek"]
            if not shipping_anchors:
                continue

            substantive_pages.append(pno + 1)
            sorted_anchors = sorted(anchors.items(), key=lambda x: x[1])

            for a_idx, (sec_name, y_start) in enumerate(sorted_anchors):
                # Never parse the Greek equities section
                if sec_name == "greek":
                    break

                y_end = sorted_anchors[a_idx + 1][1] if a_idx + 1 < len(sorted_anchors) else 770.0

                if sec_name == "bulk":
                    v_rows = extract_sp_section_rows(lines, y_start, y_end, "bulk_carriers", issue_date or "", report_week, pno + 1, pdf_path.name)
                    doc_sales.extend(v_rows)
                elif sec_name == "tanker_sp":
                    v_rows = extract_sp_section_rows(lines, y_start, y_end, "tankers", issue_date or "", report_week, pno + 1, pdf_path.name)
                    doc_sales.extend(v_rows)
                elif sec_name == "container":
                    v_rows = extract_sp_section_rows(lines, y_start, y_end, "containers", issue_date or "", report_week, pno + 1, pdf_path.name)
                    doc_sales.extend(v_rows)
                elif sec_name == "demo":
                    d_rows = extract_demolition_rows(lines, y_start, y_end, issue_date or "", report_week, pno + 1, pdf_path.name)
                    doc_demo.extend(d_rows)
                elif sec_name == "newbuilding":
                    nb_rows = extract_newbuilding_rows(lines, y_start, y_end, issue_date or "", report_week, pno + 1, pdf_path.name)
                    doc_nb.extend(nb_rows)
                elif sec_name == "bspa":
                    bspa_rows, bda_rows = extract_bspa_and_bda(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_bspa.extend(bspa_rows)
                    doc_bda.extend(bda_rows)
                elif sec_name == "indices":
                    idx_rows = extract_shipping_indices(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_indices.extend(idx_rows)
                elif sec_name == "bdi":
                    bdi_rows = extract_baltic_dry(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_indices.extend(bdi_rows)
                elif sec_name == "weighted":
                    wr_rows = extract_weighted_routes(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_weighted.extend(wr_rows)
                elif sec_name == "tc_period":
                    tc_rows = extract_tc_period(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_tc_period.extend(tc_rows)
                elif sec_name == "tanker_tce":
                    tr_rows = extract_tanker_tce(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                    doc_tanker_tce.extend(tr_rows)

        master_sales.extend(doc_sales)
        master_demo.extend(doc_demo)
        master_nb.extend(doc_nb)
        master_bspa.extend(doc_bspa)
        master_bda.extend(doc_bda)
        master_indices.extend(doc_indices)
        master_weighted.extend(doc_weighted)
        master_tc_period.extend(doc_tc_period)
        master_tanker_tce.extend(doc_tanker_tce)

        doc_data_combined = {
            "sales": doc_sales,
            "demolition": doc_demo,
            "newbuilding": doc_nb,
            "bspa": doc_bspa,
            "bda": doc_bda,
            "indices": doc_indices,
            "weighted_routes": doc_weighted,
            "tc_period": doc_tc_period,
            "tanker_tce": doc_tanker_tce,
        }

        # Write markdown
        md_content = generate_markdown(stem, pdf_path, doc, substantive_pages, issue_date or "", report_week, doc_data_combined)
        (OUT_MD / f"{stem}.md").write_text(md_content, encoding="utf-8")

        # Write sidecar JSON
        sidecar = {
            "stem": stem,
            "issue_date": issue_date,
            "report_week": report_week,
            "source_file": pdf_path.name,
            "pages_total": len(doc),
            "substantive_pages": substantive_pages,
            "counts": {
                "sales": len(doc_sales),
                "demolition": len(doc_demo),
                "newbuilding": len(doc_nb),
                "bspa": len(doc_bspa),
                "bda": len(doc_bda),
                "indices": len(doc_indices),
                "weighted_routes": len(doc_weighted),
                "tc_period": len(doc_tc_period),
                "tanker_tce": len(doc_tanker_tce),
            },
            "tables": doc_data_combined,
        }
        (OUT_MD / f"{stem}.tables.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

        if idx % 25 == 0 or idx == len(all_pdfs):
            print(f"  [{idx:>3}/{len(all_pdfs)}] {stem[:45]:<45} sales={len(doc_sales)} bspa={len(doc_bspa)} bdi={len(doc_indices)} wr={len(doc_weighted)} tc={len(doc_tc_period)} tkr={len(doc_tanker_tce)}")

    # Stack Master Series CSVs
    def write_csv(path: Path, data: List[Dict[str, Any]], fieldnames: List[str]):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in data:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

    write_csv(SALES_SERIES_CSV, master_sales, [
        "issue_date", "report_week", "section", "page", "vessel_name", "type",
        "dwt", "built", "yard", "price_raw", "price_usd_mill", "buyers", "comments", "source_file"
    ])
    write_csv(DEMO_SERIES_CSV, master_demo, [
        "issue_date", "report_week", "vessel_name", "type", "dwt", "ldt",
        "built", "yard", "price_usd_per_ldt", "buyers", "comments", "page", "source_file"
    ])
    write_csv(NB_SERIES_CSV, master_nb, [
        "issue_date", "report_week", "type", "units", "size", "yard",
        "delivery", "price_raw", "price_usd_mill", "owners", "comments", "page", "source_file"
    ])
    write_csv(BSPA_SERIES_CSV, master_bspa, [
        "issue_date", "report_week", "sector", "vessel_class", "size_dwt",
        "price_usd_m", "sentiment_arrow", "source_file"
    ])
    write_csv(BDA_SERIES_CSV, master_bda, [
        "issue_date", "report_week", "segment", "place", "ldt_range",
        "price_usd_per_ldt", "sentiment_arrow", "source_file"
    ])
    write_csv(INDICES_SERIES_CSV, master_indices, [
        "issue_date", "report_week", "index_category", "index_name",
        "current_value", "change_val", "prev_value", "sentiment_arrow", "source_file"
    ])
    write_csv(WEIGHTED_ROUTES_SERIES_CSV, master_weighted, [
        "issue_date", "report_week", "route_vessel_class", "current_rate_usd_day",
        "week_change_usd_day", "prev_rate_usd_day", "source_file"
    ])
    write_csv(TC_PERIOD_SERIES_CSV, master_tc_period, [
        "issue_date", "report_week", "vessel_class", "tenor", "rate_usd_day",
        "rate_atl_usd_day", "rate_pac_usd_day", "rate_raw", "source_file"
    ])
    write_csv(TANKER_TCE_SERIES_CSV, master_tanker_tce, [
        "issue_date", "report_week", "metric_name", "current_value",
        "week_change", "prev_value", "source_file"
    ])

    print("\n" + "=" * 70)
    print("CARRIERS CHARTERING FULL COVER-TO-COVER EXTRACTION COMPLETE:")
    print(f"Total reports processed:                 {len(all_pdfs)}")
    print(f"Total S&P Sales rows:                    {len(master_sales)} -> {SALES_SERIES_CSV.name}")
    print(f"Total Demolition deals:                  {len(master_demo)} -> {DEMO_SERIES_CSV.name}")
    print(f"Total Newbuilding orders:                {len(master_nb)} -> {NB_SERIES_CSV.name}")
    print(f"Total BSPA Secondhand assessments:       {len(master_bspa)} -> {BSPA_SERIES_CSV.name}")
    print(f"Total BDA Demolition assessments:        {len(master_bda)} -> {BDA_SERIES_CSV.name}")
    print(f"Total Shipping & Baltic Indices rows:    {len(master_indices)} -> {INDICES_SERIES_CSV.name}")
    print(f"Total Dry Weighted Routes rows:          {len(master_weighted)} -> {WEIGHTED_ROUTES_SERIES_CSV.name}")
    print(f"Total Dry TC Period rows:                {len(master_tc_period)} -> {TC_PERIOD_SERIES_CSV.name}")
    print(f"Total Tanker Rates & Indices rows:       {len(master_tanker_tce)} -> {TANKER_TCE_SERIES_CSV.name}")
    print("=" * 70)


if __name__ == "__main__":
    run()
