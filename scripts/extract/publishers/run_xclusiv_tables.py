"""
Source: XCLUSIV SHIPBROKERS - Full Tabular Extraction Pipeline.

Extracts dense proprietary market tables across all eras (2021-2026, 266 reports):
1. Reported S&P Sales (Bulk Carriers, Tankers, Gas, Containers)
2. Reported Demolition Deals (Demo Sales)
3. Newbuilding Orders
4. Indicative Secondhand Prices (Resale, 5Y, 10Y, 15Y for Dry & Tankers)
5. Indicative Demolition Scrap Prices ($/ldt for India, Bangladesh, Pakistan, Turkey)
6. Indicative Newbuilding Prices ($ mills)

Multi-Era Layout Handling:
  - 2021: 6pp (Page 1: NB & Demo Prices, Page 2: Dry SH, Page 3: Wet SH, Page 4: Bulkers, Page 5: Tankers)
  - 2022-2023: 7pp (Page 1: NB & Demo Prices, Page 2: Dry SH, Page 3: Wet SH, Page 4: Bulkers, Page 5: Tankers)
  - 2024-2026: 9pp (Page 4: NB Prices & Orders, Page 5: Dry SH & Bulkers, Page 6: Wet SH & Tankers, Page 7: Demo Prices & Demo Sales)
  - Dynamic page and header location (never hardcoded page numbers).
  - Numbers are standard US/ISO (comma=thousands, dot=decimal).

Outputs:
  - data/extracted/series/xclusiv_sales_series.csv
  - data/extracted/series/xclusiv_demolition_series.csv
  - data/extracted/series/xclusiv_secondhand_series.csv
  - data/extracted/series/xclusiv_demo_sales_series.csv
  - data/extracted/md/xclusiv/<stem>.tables.json
  - data/extracted/md/xclusiv/<stem>.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "xclusiv"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"


def byte_duplicate_stems() -> set:
    """Stems of corpus PDFs that are BYTE-IDENTICAL to another corpus PDF.

    The same weekly issue is re-dropped under a second filename by another
    collection route (measured 2026-10-01: 271 xclusiv PDFs, only 264 unique -
    7 duplicate groups, e.g. xclusiv_2026_xclusiv-2026_09_14.pdf and
    xclusiv_15_09_2026_xclusiv_shipbrokers_weekly_14th_september_2026.pdf are
    the same md5). Both copies were parsed and stacked, so every one of those
    issues double-counted its deals. Keep the lexicographically-first stem and
    skip the rest.
    """
    by_hash: Dict[str, List[Path]] = {}
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


SALES_SERIES_CSV = OUT_SERIES / "xclusiv_sales_series.csv"
DEMO_SERIES_CSV = OUT_SERIES / "xclusiv_demolition_series.csv"
SECONDHAND_SERIES_CSV = OUT_SERIES / "xclusiv_secondhand_series.csv"
DEMO_SALES_SERIES_CSV = OUT_SERIES / "xclusiv_demo_sales_series.csv"
BALTIC_SERIES_CSV = OUT_SERIES / "xclusiv_baltic_indices_series.csv"
NB_PRICES_SERIES_CSV = OUT_SERIES / "xclusiv_newbuilding_series.csv"

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def clean_str(v: Any) -> str:
    """Normalize whitespace and unicode typography."""
    if v is None:
        return ""
    s = str(v).replace("\n", " ").strip()
    s = s.replace("\ufffd", "'").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("`", "'")
    return re.sub(r"\s+", " ", s).strip()


def _dedupe_words(words):
    """Drop words drawn twice at the same spot (an overprinted text layer).

    One xclusiv page (2021-10-04) carries every word twice at almost identical
    coordinates (~0.12pt apart), so get_text("words") returns each word twice
    and the y-bucket row builder - which only groups by y - kept both copies
    ('CONRAD CONRAD', '207,647 207,647'). Measured 2026-10-04 scanning all 271
    xclusiv PDFs: exactly one page affected (195 duplicated of 533 words).

    A word is dropped only when an identical string already sits within 1.0pt
    in BOTH x and y. Real words never coincide that closely; two words that
    merely share a string elsewhere on the page are far apart and preserved.
    """
    seen = {}
    out = []
    for w in words:
        placed = False
        for (px, py) in seen.get(w[4], ()):
            if abs(px - w[0]) <= 1.0 and abs(py - w[1]) <= 1.0:
                placed = True
                break
        if placed:
            continue
        seen.setdefault(w[4], []).append((w[0], w[1]))
        out.append(w)
    return out


def parse_price_mill(p_str: str) -> Optional[float]:
    """Extract numeric million USD from a price string.

    The publisher mixes separators. Measured 2026-10-01 against the source PDF
    (positioned text): 'TANAIS FLYER 28,674 1998 JAPAN IMABARI UNDISCLOSED 4,8
    SS: 02/2024' - a 1998 28,674 dwt Handysize at 4.8m, stored as 48.0 before
    this fix (10x). A comma followed by 1-2 digits is the DECIMAL point; a comma
    followed by 3 digits stays a thousands group ('2,350 ENBLOC' unchanged).
    """
    if not p_str:
        return None
    s = p_str.replace("$", "").replace("USD", "").replace("usd", "").strip()
    m = re.search(r"\d[\d.,]*", s)
    if not m:
        return None
    token = m.group(0).rstrip(".,")
    if "," in token:
        head, tail = token.rsplit(",", 1)
        tail = tail.strip(".")
        if tail.isdigit() and len(tail) <= 2:
            head_digits = re.sub(r"[.,]", "", head)
            if head_digits:
                return float(f"{head_digits}.{tail}")
    if "," in token:
        # a 3-digit group after the comma is a thousands separator ('2,350 ENBLOC')
        digits = re.sub(r"[.,]", "", token)
        return float(digits) if digits.isdigit() else None
    # a lone period is the decimal point: '$17.7' stays 17.7
    try:
        return float(token)
    except ValueError:
        return None


def parse_price_per_ldt(p_str: str) -> Optional[float]:
    """Extract scrap price $/LDT from string."""
    if not p_str:
        return None
    s = p_str.replace("$", "").replace("USD", "").replace("usd", "").replace(",", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            val = float(m.group(1))
            if 100 <= val <= 1500:
                return val
        except ValueError:
            return None
    return None


def extract_meta(doc: pymupdf.Document, pdf_path: Path) -> Tuple[str, int]:
    """Extract standardized ISO issue date (YYYY-MM-DD) and week number."""
    fn = pdf_path.stem
    issue_date = None
    week_num = None

    # Priority 1: Canonical date from filename (immune to prose noise)
    m_fn1 = re.search(r"(\d{4})_(\d{1,2})_(\d{1,2})", fn)
    if m_fn1:
        issue_date = f"{int(m_fn1.group(1)):04d}-{int(m_fn1.group(2)):02d}-{int(m_fn1.group(3)):02d}"
    else:
        m_fn2 = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
        if m_fn2:
            issue_date = f"{int(m_fn2.group(3)):04d}-{int(m_fn2.group(2)):02d}-{int(m_fn2.group(1)):02d}"
        else:
            m_fn3 = re.search(r"(\d{1,2})-[A-Za-z]+-(\d{1,2})-([A-Za-z]+)-(\d{4})", fn)
            if m_fn3:
                issue_date = "2025-09-05"

    t_all = ""
    for p in doc[:3]:
        t_all += p.get_text() + "\n"
    if len(doc) > 3:
        t_all += doc[-1].get_text() + "\n"
        t_all += doc[3].get_text() + "\n"

    # Week number from text
    m_wk = re.search(r"Week\s+(\d{1,2})\b", t_all, re.I)
    if m_wk:
        week_num = int(m_wk.group(1))

    # Priority 2: Fallback to text date if filename lacked date
    if not issue_date:
        m_dmy = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t_all)
        if m_dmy:
            d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            if 1 <= m <= 12 and 1 <= d <= 31:
                issue_date = f"{y:04d}-{m:02d}-{d:02d}"

    if not issue_date:
        m_txtdate = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})\b", t_all)
        if m_txtdate:
            d, mon_str, y = int(m_txtdate.group(1)), m_txtdate.group(2).lower(), int(m_txtdate.group(3))
            if mon_str in MONTH_MAP:
                issue_date = f"{y:04d}-{MONTH_MAP[mon_str]:02d}-{d:02d}"

    if week_num is None and issue_date:
        import datetime
        try:
            dt = datetime.date.fromisoformat(issue_date)
            week_num = dt.isocalendar()[1]
        except Exception:
            week_num = 1

    return issue_date or "2026-01-01", week_num or 1


# ---------------------------------------------------------------------------
def propagate_enbloc_and_spans(sales: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Propagates multi-row vertical spans, en bloc deals, and sister-ship clusters
    so that vertically merged cells in the source PDF do not leave sibling rows blank.
    """
    n = len(sales)
    # Pass 1: Cluster detection for sister ships (e.g. 'EACH' or single centered Buyer spanning 2-5 rows)
    i = 0
    while i < n:
        cluster = [i]
        j = i + 1
        while j < n and sales[j].get("section") == sales[i].get("section"):
            same_yard = bool(sales[j].get("YARD") and sales[j].get("YARD") == sales[i].get("YARD"))
            same_country = bool(sales[j].get("COUNTRY") and sales[j].get("COUNTRY") == sales[i].get("COUNTRY"))
            name_i = sales[i].get("NAME", "").split()[0] if sales[i].get("NAME") else ""
            name_j = sales[j].get("NAME", "").split()[0] if sales[j].get("NAME") else ""
            same_prefix = bool(name_i == name_j and len(name_i) > 2)
            
            if (same_yard and same_country) or same_prefix:
                cluster.append(j)
                j += 1
            else:
                break
        
        if len(cluster) > 1:
            cluster_buyers = [sales[idx].get("BUYERS", "") for idx in cluster if sales[idx].get("BUYERS")]
            cluster_prices = [sales[idx].get("PRICE", "") for idx in cluster if sales[idx].get("PRICE")]
            cluster_mills = [sales[idx].get("PRICE_USD_MILL") for idx in cluster if sales[idx].get("PRICE_USD_MILL")]
            
            # If exactly one buyer for the cluster, propagate to all
            if len(set(cluster_buyers)) == 1:
                single_buyer = cluster_buyers[0]
                for idx in cluster:
                    if not sales[idx].get("BUYERS"):
                        sales[idx]["BUYERS"] = single_buyer
            
            # If price contains 'EACH', propagate to all
            each_prices = [p for p in cluster_prices if "EACH" in str(p).upper()]
            if each_prices:
                rep_price = each_prices[0]
                rep_mill = cluster_mills[0] if cluster_mills else ""
                for idx in cluster:
                    if not sales[idx].get("PRICE"):
                        sales[idx]["PRICE"] = rep_price
                        sales[idx]["PRICE_USD_MILL"] = rep_mill

            # If price contains 'ENBLOC', propagate to all with en bloc note
            enbloc_prices = [p for p in cluster_prices if "ENBLOC" in str(p).upper() or "EN BLOC" in str(p).upper()]
            if enbloc_prices:
                rep_price = enbloc_prices[0]
                rep_mill = cluster_mills[0] if cluster_mills else ""
                for idx in cluster:
                    if not sales[idx].get("PRICE") or str(sales[idx].get("PRICE")).upper() == "ENBLOC":
                        sales[idx]["PRICE"] = rep_price if "ENBLOC" in str(rep_price).upper() else f"{rep_price} ENBLOC"
                        sales[idx]["PRICE_USD_MILL"] = rep_mill
            
            # If only one price reported for the entire cluster and vessels are identical sisters, mark as en bloc
            elif len(cluster_prices) == 1 and len(cluster) == 2:
                rep_price = cluster_prices[0]
                rep_mill = cluster_mills[0] if cluster_mills else ""
                for idx in cluster:
                    if not sales[idx].get("PRICE"):
                        sales[idx]["PRICE"] = f"{rep_price} (en bloc)"
                        sales[idx]["PRICE_USD_MILL"] = rep_mill

        i = j if j > i + 1 else i + 1

    # Pass 2: Sequential pair propagation (e.g. row i is ENBLOC, row i-1 was main deal)
    for k in range(1, n):
        curr = sales[k]
        prev = sales[k - 1]
        if curr.get("section") != prev.get("section"):
            continue
        if "ENBLOC" in str(curr.get("PRICE", "")).upper() or "EN BLOC" in str(curr.get("PRICE", "")).upper():
            if not curr.get("BUYERS") and prev.get("BUYERS"):
                curr["BUYERS"] = prev["BUYERS"]
            if not curr.get("PRICE_USD_MILL") and prev.get("PRICE_USD_MILL"):
                curr["PRICE_USD_MILL"] = prev["PRICE_USD_MILL"]
                if curr.get("PRICE") == "ENBLOC":
                    curr["PRICE"] = f"{prev.get('PRICE')} ENBLOC"

    return sales


def extract_sales_tables(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    sales_rows: List[Dict[str, Any]] = []

    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        words = _dedupe_words(pg.get_text("words"))
        if not words:
            continue

        footer_y = pg.rect.height - 35.0

        found_sections: List[Tuple[str, float, int]] = []
        for i, w in enumerate(words):
            up = w[4].upper()
            if (
                up == "BULK"
                and i + 2 < len(words)
                and words[i + 1][4].upper() == "CARRIER"
                and words[i + 2][4].upper() == "SALES"
            ):
                found_sections.append(("Bulk Carriers", w[1], pno + 1))
            elif up == "TANKER" and i + 1 < len(words) and words[i + 1][4].upper() == "SALES":
                found_sections.append(("Tankers", w[1], pno + 1))
            elif up == "GAS" and i + 1 < len(words) and words[i + 1][4].upper() == "SALES":
                found_sections.append(("Gas", w[1], pno + 1))
            elif up == "CONTAINER" and i + 1 < len(words) and words[i + 1][4].upper() == "SALES":
                found_sections.append(("Containers", w[1], pno + 1))
            elif up == "GENERAL" and i + 2 < len(words) and words[i + 1][4].upper() == "CARGO" and words[i + 2][4].upper() == "SALES":
                found_sections.append(("General Cargo", w[1], pno + 1))

        found_sections.sort(key=lambda x: x[1])

        for s_idx, (sec_name, ty, page_num) in enumerate(found_sections):
            next_ty = (
                min(found_sections[s_idx + 1][1], footer_y)
                if s_idx + 1 < len(found_sections)
                else footer_y
            )

            hw_dict: Dict[str, Any] = {}
            for w in words:
                if ty < w[1] <= ty + 45:
                    wtxt = w[4].upper()
                    if wtxt in [
                        "NAME", "DWT", "CBM", "TEU", "SIZE", "YEAR", "COUNTRY",
                        "YARD", "BUYERS", "PRICE", "COMMENTS", "NOTES/",
                    ]:
                        key = (
                            "DWT"
                            if wtxt in ["CBM", "TEU", "SIZE"]
                            else ("COMMENTS" if wtxt == "NOTES/" else wtxt)
                        )
                        if key not in hw_dict:
                            hw_dict[key] = w

            if "NAME" not in hw_dict:
                continue

            cols = sorted(hw_dict.items(), key=lambda x: x[1][0])
            bounds: List[Tuple[str, float, float]] = []
            for i in range(len(cols)):
                c_name, c_word = cols[i]
                left = 0.0 if i == 0 else (cols[i - 1][1][2] + c_word[0]) / 2.0
                right = 9999.0 if i == len(cols) - 1 else (c_word[2] + cols[i + 1][1][0]) / 2.0
                bounds.append((c_name, left, right))

            hdr_bottom = max(w[3] for w in hw_dict.values())
            body_words = [
                w
                for w in words
                if hdr_bottom + 3 < w[1] < next_ty - 2
                and "XCLUSIV" not in w[4].upper()
                and "WWW." not in w[4].upper()
                and "PAGE" not in w[4].upper()
                and "RESEARCH" not in w[4].upper()
            ]

            line_buckets: Dict[float, List[Any]] = {}
            for w in sorted(body_words, key=lambda x: x[1]):
                matched = None
                for by in line_buckets:
                    if abs(by - w[1]) <= 5.0:
                        matched = by
                        break
                if matched is None:
                    matched = w[1]
                    line_buckets[matched] = []
                line_buckets[matched].append(w)

            last_valid_row = None
            for by in sorted(line_buckets.keys()):
                lw = sorted(line_buckets[by], key=lambda x: x[0])
                row: Dict[str, List[str]] = {b[0]: [] for b in bounds}
                for w in lw:
                    wx = (w[0] + w[2]) / 2.0
                    for b_name, b_left, b_right in bounds:
                        if b_left <= wx < b_right:
                            row[b_name].append(w[4])
                            break

                row_clean = {k: clean_str(" ".join(v)) for k, v in row.items()}
                name = row_clean.get("NAME", "")
                dwt = row_clean.get("DWT", "")
                year = row_clean.get("YEAR", "")
                yard = row_clean.get("YARD", "")
                buyers = row_clean.get("BUYERS", "")
                price = row_clean.get("PRICE", "")
                comments = row_clean.get("COMMENTS", "")
                country = row_clean.get("COUNTRY", "")

                if name and not any(
                    bad in name.upper()
                    for bad in ["BULK CARRIER", "TANKER", "SALES", "NAME", "WWW.", "PAGE", "WEEKLY"]
                ):
                    if re.match(r"^\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+", name, re.I):
                        continue
                    if re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", name, re.I) and not dwt:
                        continue

                    v_type = sec_name
                    if sec_name == "Bulk Carriers":
                        dwt_num = None
                        m_dwt = re.search(r"(\d+(?:,\d+)?)", dwt)
                        if m_dwt:
                            try:
                                dwt_num = float(m_dwt.group(1).replace(",", ""))
                            except ValueError:
                                pass
                        if dwt_num:
                            if dwt_num >= 110000: v_type = "Capesize"
                            elif dwt_num >= 80000: v_type = "Kamsarmax"
                            elif dwt_num >= 67000: v_type = "Panamax"
                            elif dwt_num >= 60000: v_type = "Ultramax"
                            elif dwt_num >= 45000: v_type = "Supramax"
                            else: v_type = "Handysize"
                    elif sec_name == "Tankers":
                        dwt_num = None
                        m_dwt = re.search(r"(\d+(?:,\d+)?)", dwt)
                        if m_dwt:
                            try:
                                dwt_num = float(m_dwt.group(1).replace(",", ""))
                            except ValueError:
                                pass
                        if dwt_num:
                            if dwt_num >= 200000: v_type = "VLCC"
                            elif dwt_num >= 120000: v_type = "Suezmax"
                            elif dwt_num >= 80000: v_type = "Aframax"
                            elif dwt_num >= 60000: v_type = "Panamax"
                            elif dwt_num >= 40000: v_type = "MR2"
                            else: v_type = "Small Tanker"

                    parsed_p = parse_price_mill(price)
                    item = {
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "section": sec_name,
                        "page": page_num,
                        "NAME": name,
                        "TYPE": v_type,
                        "DWT": dwt,
                        "YEAR": year,
                        "COUNTRY": country,
                        "YARD": yard,
                        "BUYERS": buyers,
                        "PRICE": price,
                        "PRICE_USD_MILL": parsed_p if parsed_p is not None else "",
                        "COMMENTS": comments,
                        "source_file": source_file,
                    }
                    sales_rows.append(item)
                    last_valid_row = item
                elif not name and last_valid_row is not None:
                    if buyers and not last_valid_row["BUYERS"]:
                        last_valid_row["BUYERS"] = buyers
                    if price and not last_valid_row["PRICE"]:
                        last_valid_row["PRICE"] = price
                        p_val = parse_price_mill(price)
                        if p_val is not None:
                            last_valid_row["PRICE_USD_MILL"] = p_val
                    if comments:
                        last_valid_row["COMMENTS"] = (last_valid_row["COMMENTS"] + " " + comments).strip()

    return propagate_enbloc_and_spans(sales_rows)


# ---------------------------------------------------------------------------
# Section 2: Reported Demolition Fixtures (Demo Sales)
# ---------------------------------------------------------------------------

def extract_demo_sales_tables(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    demo_sales: List[Dict[str, Any]] = []

    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        words = _dedupe_words(pg.get_text("words"))
        if not words:
            continue

        for i, w in enumerate(words):
            if w[4].upper() == "DEMO" and i + 1 < len(words) and words[i + 1][4].upper() == "SALES":
                ty = w[1]
                hw_dict: Dict[str, Any] = {}
                for hw in words:
                    if ty < hw[1] <= ty + 45:
                        wtxt = hw[4].upper()
                        if wtxt in [
                            "NAME", "TYPE", "YEAR", "DWT", "LDT", "COUNTRY",
                            "PRICE", "BUYERS", "COMMENTS",
                        ]:
                            if wtxt not in hw_dict:
                                hw_dict[wtxt] = hw

                if "NAME" not in hw_dict:
                    continue

                cols = sorted(hw_dict.items(), key=lambda x: x[1][0])
                bounds: List[Tuple[str, float, float]] = []
                for idx in range(len(cols)):
                    c_name, c_word = cols[idx]
                    left = 0.0 if idx == 0 else (cols[idx - 1][1][2] + c_word[0]) / 2.0
                    right = 9999.0 if idx == len(cols) - 1 else (c_word[2] + cols[idx + 1][1][0]) / 2.0
                    bounds.append((c_name, left, right))

                footer_y = pg.rect.height - 35.0
                hdr_bottom = max(hw[3] for hw in hw_dict.values())
                body_words = [
                    bw
                    for bw in words
                    if hdr_bottom + 3 < bw[1] < footer_y
                    and "XCLUSIV" not in bw[4].upper()
                    and "WWW." not in bw[4].upper()
                    and "PAGE" not in bw[4].upper()
                    and "RESEARCH" not in bw[4].upper()
                ]

                line_buckets: Dict[float, List[Any]] = {}
                for bw in sorted(body_words, key=lambda x: x[1]):
                    matched = None
                    for by in line_buckets:
                        if abs(by - bw[1]) <= 5.0:
                            matched = by
                            break
                    if matched is None:
                        matched = bw[1]
                        line_buckets[matched] = []
                    line_buckets[matched].append(bw)

                for by in sorted(line_buckets.keys()):
                    lw = sorted(line_buckets[by], key=lambda x: x[0])
                    row: Dict[str, List[str]] = {b[0]: [] for b in bounds}
                    for bw in lw:
                        wx = (bw[0] + bw[2]) / 2.0
                        for b_name, b_left, b_right in bounds:
                            if b_left <= wx < b_right:
                                row[b_name].append(bw[4])
                                break

                    row_clean = {k: clean_str(" ".join(v)) for k, v in row.items()}
                    name = row_clean.get("NAME", "")
                    if name and not any(
                        bad in name.upper()
                        for bad in ["DEMO", "SALES", "NAME", "WWW.", "PAGE", "WEEKLY"]
                    ):
                        if re.match(r"^\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+", name, re.I):
                            continue
                        raw_p = row_clean.get("PRICE", "").strip()
                        p_ldt = parse_price_per_ldt(raw_p)
                        demo_sales.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "NAME": name,
                            "TYPE": row_clean.get("TYPE", ""),
                            "YEAR": row_clean.get("YEAR", ""),
                            "DWT": row_clean.get("DWT", ""),
                            "LDT": row_clean.get("LDT", ""),
                            "COUNTRY": row_clean.get("COUNTRY", ""),
                            "PRICE_RAW": raw_p or "N/A",
                            "PRICE_USD_PER_LDT": p_ldt if p_ldt is not None else "",
                            "BUYERS": row_clean.get("BUYERS", ""),
                            "COMMENTS": row_clean.get("COMMENTS", ""),
                            "source_file": source_file,
                        })

    return demo_sales


# ---------------------------------------------------------------------------
# Section 3: Indicative Demolition Scrap Prices ($/LDT)
# ---------------------------------------------------------------------------

def extract_indicative_demolition(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        txt = pg.get_text()
        if "DRY DEMOLITION PRICES" in txt.upper() and "TANKER DEMOLITION PRICES" in txt.upper():
            words = _dedupe_words(pg.get_text("words"))
            for sec_name, (y_min, y_max) in [("Bulkers", (100, 310)), ("Tankers", (340, 560))]:
                sec_words = [w for w in words if y_min <= w[1] <= y_max and w[0] >= 320]
                regions = [
                    ("India", 320, 380),
                    ("Bangladesh", 380, 445),
                    ("Pakistan", 445, 505),
                    ("Turkey", 505, 570),
                ]
                for cname, rx0, rx1 in regions:
                    c_words = [w for w in sec_words if rx0 <= w[0] < rx1]
                    nums = []
                    for w in sorted(c_words, key=lambda x: (x[0], x[1])):
                        cleaned = w[4].replace("$", "").replace(",", "").strip()
                        m = re.match(r"^(\d{2,3}(?:\.\d+)?)$", cleaned)
                        if m:
                            v = float(m.group(1))
                            if 150 <= v <= 900:
                                nums.append((w[0], v))
                    if nums:
                        nums_by_x = sorted(nums, key=lambda x: x[0])
                        curr_price = nums_by_x[0][1]
                        records.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "segment": sec_name,
                            "country": cname,
                            "price_usd_per_ldt": curr_price,
                            "source_file": source_file,
                        })
            if records:
                return records

    # 2. Check Early Era (2021-2023): Page 1 Demolition Prices table
    if not records and len(doc) > 0:
        pg0 = doc[0]
        words = _dedupe_words(pg0.get_text("words"))
        dw = [w for w in words if "DEMOLITION" in w[4].upper()]
        if dw:
            dy = dw[0][1]
            near = [w for w in words if dy < w[1] <= dy + 110 and w[0] >= 300]
            lines: Dict[float, List[Any]] = {}
            for w in sorted(near, key=lambda x: x[1]):
                matched = None
                for ly in lines:
                    if abs(ly - w[1]) <= 5.0:
                        matched = ly
                        break
                if matched is None:
                    matched = w[1]
                    lines[matched] = []
                lines[matched].append(w)

            countries = ["INDIA", "BANGLADESH", "PAKISTAN", "TURKEY"]
            for ly in sorted(lines.keys()):
                lw = sorted(lines[ly], key=lambda x: x[0])
                ltxt = " ".join(w[4] for w in lw)
                for c in countries:
                    if c in ltxt.upper():
                        nums = re.findall(r"(?:\$\s*)?(\d{3}(?:\.\d+)?)", ltxt)
                        if len(nums) >= 2:
                            bulker_price = float(nums[0])
                            tanker_price = (
                                float(nums[len(nums) // 2]) if len(nums) >= 4 else float(nums[1])
                            )
                            records.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "segment": "Bulkers",
                                "country": c.title(),
                                "price_usd_per_ldt": bulker_price,
                                "source_file": source_file,
                            })
                            records.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "segment": "Tankers",
                                "country": c.title(),
                                "price_usd_per_ldt": tanker_price,
                                "source_file": source_file,
                            })
                        break

    return records


# ---------------------------------------------------------------------------
# Section 4: Indicative Secondhand Prices ($ mills)
# ---------------------------------------------------------------------------

def extract_secondhand_prices(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        txt = pg.get_text()

        # Modern Dry
        if "DRY SECONDHAND PRICES" in txt.upper() and ("CAPESIZE" in txt.upper() or "KAMSARMAX" in txt.upper()):
            words = _dedupe_words(pg.get_text("words"))
            sh_words = [w for w in words if 140 <= w[1] <= 415 and 80 <= w[0] <= 210]
            lines: Dict[float, List[Any]] = {}
            for w in sorted(sh_words, key=lambda x: x[1]):
                matched = None
                for ly in lines:
                    if abs(ly - w[1]) <= 4.0:
                        matched = ly
                        break
                if matched is None:
                    matched = w[1]
                    lines[matched] = []
                lines[matched].append(w)

            rows = []
            for ly in sorted(lines.keys()):
                lw = sorted(lines[ly], key=lambda x: x[0])
                ltxt = " ".join(w[4] for w in lw)
                m = re.search(r"\b(15\s*Year|10\s*Year|5\s*Year|Resale)\b\s+(\d+(?:\.\d+)?)", ltxt, re.I)
                if m:
                    tenor = m.group(1).title()
                    tenor = re.sub(r"\s+", " ", tenor)
                    price = float(m.group(2))
                    rows.append((tenor, price))

            dry_types = ["Capesize", "Kamsarmax", "Ultramax", "Handysize"]
            for i, (tenor, price) in enumerate(rows[:16]):
                type_idx = min(i // 4, len(dry_types) - 1)
                records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Dry",
                    "vessel_type": dry_types[type_idx],
                    "tenor": tenor,
                    "price_usd_mill": price,
                    "source_file": source_file,
                })

        # Modern Tanker
        if "TANKER SECONDHAND PRICES" in txt.upper() and ("VLCC" in txt.upper() or "SUEZMAX" in txt.upper()):
            words = _dedupe_words(pg.get_text("words"))
            sh_words = [w for w in words if 140 <= w[1] <= 415 and 80 <= w[0] <= 210]
            lines = {}
            for w in sorted(sh_words, key=lambda x: x[1]):
                matched = None
                for ly in lines:
                    if abs(ly - w[1]) <= 4.0:
                        matched = ly
                        break
                if matched is None:
                    matched = w[1]
                    lines[matched] = []
                lines[matched].append(w)

            rows = []
            for ly in sorted(lines.keys()):
                lw = sorted(lines[ly], key=lambda x: x[0])
                ltxt = " ".join(w[4] for w in lw)
                m = re.search(r"\b(15\s*Year|10\s*Year|5\s*Year|Resale)\b\s+(\d+(?:\.\d+)?)", ltxt, re.I)
                if m:
                    tenor = m.group(1).title()
                    tenor = re.sub(r"\s+", " ", tenor)
                    price = float(m.group(2))
                    rows.append((tenor, price))

            wet_types = ["VLCC", "Suezmax", "Aframax", "MR2"]
            for i, (tenor, price) in enumerate(rows[:16]):
                type_idx = min(i // 4, len(wet_types) - 1)
                records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Tanker",
                    "vessel_type": wet_types[type_idx],
                    "tenor": tenor,
                    "price_usd_mill": price,
                    "source_file": source_file,
                })

    if records:
        return records

    # 2. Check Early Era (2021-2023): Word-clustered table on Page 2 (Dry) and Page 3 (Wet)
    for pno in range(min(4, len(doc))):
        pg = doc[pno]
        txt = pg.get_text()
        sector = None
        if "DRY SECONDHAND PRICES" in txt.upper():
            sector = "Dry"
        elif "WET SECONDHAND PRICES" in txt.upper():
            sector = "Tanker"

        if sector:
            words = _dedupe_words(pg.get_text("words"))
            sh_words = [w for w in words if w[0] >= 350 and w[1] <= 320]
            lines = {}
            for w in sorted(sh_words, key=lambda x: x[1]):
                matched = None
                for ly in lines:
                    if abs(ly - w[1]) <= 4.0:
                        matched = ly
                        break
                if matched is None:
                    matched = w[1]
                    lines[matched] = []
                lines[matched].append(w)

            pat = re.compile(
                r"\b(Capesize|Kamsarmax|Panamax|Ultramax|Supramax|Handy|VLCC|Suezmax|Aframax|MR2)\s*(?:\d+k)?\s*(Resale|15y|10y|5y)\b(?:\s*[\$:])?\s*(\d+(?:\.\d+)?)",
                re.I,
            )
            for ly in sorted(lines.keys()):
                ltxt = " ".join(w[4] for w in sorted(lines[ly], key=lambda x: x[0]))
                m = pat.search(ltxt)
                if m:
                    vtype = m.group(1).title()
                    if vtype == "Handy": vtype = "Handysize"
                    elif vtype == "Suprmax": vtype = "Supramax"
                    elif vtype == "Vlcc": vtype = "VLCC"
                    elif vtype == "Mr2": vtype = "MR2"

                    raw_tenor = m.group(2).lower()
                    if "resale" in raw_tenor: tenor = "Resale"
                    elif "15" in raw_tenor: tenor = "15 Year"
                    elif "10" in raw_tenor: tenor = "10 Year"
                    elif "5" in raw_tenor: tenor = "5 Year"
                    else: tenor = raw_tenor

                    price = float(m.group(3))
                    records.append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "sector": sector,
                        "vessel_type": vtype,
                        "tenor": tenor,
                        "price_usd_mill": price,
                        "source_file": source_file,
                    })

    return records


# ---------------------------------------------------------------------------
# Section 5: Newbuilding Orders & Indicative Newbuilding Prices
# ---------------------------------------------------------------------------

def extract_newbuilding_orders(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    orders: List[Dict[str, Any]] = []

    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        words = _dedupe_words(pg.get_text("words"))
        for i, w in enumerate(words):
            if w[4].upper() == "NEWBUILDING" and i + 1 < len(words) and words[i + 1][4].upper() == "ORDERS":
                ty = w[1]
                hw_dict: Dict[str, Any] = {}
                for hw in words:
                    if ty < hw[1] <= ty + 45:
                        wtxt = hw[4].upper()
                        if wtxt in [
                            "TYPE", "UNITS", "SIZE", "YARD", "BUYER", "PRICE",
                            "DELIVERY", "COMMENTS",
                        ]:
                            if wtxt not in hw_dict:
                                hw_dict[wtxt] = hw

                if "TYPE" not in hw_dict or "YARD" not in hw_dict:
                    continue

                cols = sorted(hw_dict.items(), key=lambda x: x[1][0])
                bounds: List[Tuple[str, float, float]] = []
                for idx in range(len(cols)):
                    c_name, c_word = cols[idx]
                    left = 0.0 if idx == 0 else (cols[idx - 1][1][2] + c_word[0]) / 2.0
                    right = 9999.0 if idx == len(cols) - 1 else (c_word[2] + cols[idx + 1][1][0]) / 2.0
                    bounds.append((c_name, left, right))

                hdr_bottom = max(hw[3] for hw in hw_dict.values())
                body_words = [
                    bw
                    for bw in words
                    if hdr_bottom + 3 < bw[1] < 785
                    and "XCLUSIV" not in bw[4].upper()
                    and "WWW." not in bw[4].upper()
                    and "PAGE" not in bw[4].upper()
                    and "RESEARCH" not in bw[4].upper()
                ]

                line_buckets: Dict[float, List[Any]] = {}
                for bw in sorted(body_words, key=lambda x: x[1]):
                    matched = None
                    for by in line_buckets:
                        if abs(by - bw[1]) <= 5.0:
                            matched = by
                            break
                    if matched is None:
                        matched = bw[1]
                        line_buckets[matched] = []
                    line_buckets[matched].append(bw)

                for by in sorted(line_buckets.keys()):
                    lw = sorted(line_buckets[by], key=lambda x: x[0])
                    row: Dict[str, List[str]] = {b[0]: [] for b in bounds}
                    for bw in lw:
                        wx = (bw[0] + bw[2]) / 2.0
                        for b_name, b_left, b_right in bounds:
                            if b_left <= wx < b_right:
                                row[b_name].append(bw[4])
                                break

                    row_clean = {k: clean_str(" ".join(v)) for k, v in row.items()}
                    vtype = row_clean.get("TYPE", "")
                    yard = row_clean.get("YARD", "")
                    if vtype and yard and not any(bad in vtype.upper() for bad in ["NEWBUILDING", "ORDERS", "TYPE"]):
                        orders.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "page": pno + 1,
                            "type": vtype,
                            "units": row_clean.get("UNITS", ""),
                            "size": row_clean.get("SIZE", ""),
                            "yard": yard,
                            "buyer": row_clean.get("BUYER", ""),
                            "price": row_clean.get("PRICE", ""),
                            "delivery": row_clean.get("DELIVERY", ""),
                            "comments": row_clean.get("COMMENTS", ""),
                            "source_file": source_file,
                        })

    return orders


def extract_newbuilding_prices(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    max_pages = min(5, len(doc) - 2) if len(doc) >= 6 else min(5, len(doc))
    for pno in range(max_pages):
        pg = doc[pno]
        txt = pg.get_text()
        if "NEWBUILDING PRICES" in txt.upper() or "NEWBUILDING  PRICES" in txt.upper():
            words = _dedupe_words(pg.get_text("words"))
            dry_types = ["Capesize", "Kamsarmax", "Ultramax", "Handysize"]
            for vt in dry_types:
                for w in words:
                    if w[4].upper() == vt.upper() and w[0] < 320:
                        same_y = [nw for nw in words if abs(nw[1] - w[1]) <= 4.0 and nw[0] > w[2]]
                        nums = [re.search(r"(\d+(?:\.\d+)?)", nw[4]) for nw in sorted(same_y, key=lambda x: x[0])]
                        nums = [float(m.group(1)) for m in nums if m and 10 <= float(m.group(1)) <= 300]
                        if nums:
                            records.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "sector": "Dry",
                                "vessel_type": vt,
                                "price_usd_mill": nums[0],
                                "source_file": source_file,
                            })
                            break

            wet_types = ["VLCC", "Suezmax", "Aframax", "Panamax", "MR2"]
            for vt in wet_types:
                for w in words:
                    if w[4].upper() == vt.upper() and w[0] < 320:
                        same_y = [nw for nw in words if abs(nw[1] - w[1]) <= 4.0 and nw[0] > w[2]]
                        nums = [re.search(r"(\d+(?:\.\d+)?)", nw[4]) for nw in sorted(same_y, key=lambda x: x[0])]
                        nums = [float(m.group(1)) for m in nums if m and 10 <= float(m.group(1)) <= 300]
                        if nums:
                            records.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "sector": "Tanker",
                                "vessel_type": vt,
                                "price_usd_mill": nums[0],
                                "source_file": source_file,
                            })
                            break
            if records:
                break

    return records


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Market & Freight Commentary Extraction (Column-Aware)
# ---------------------------------------------------------------------------

def extract_market_overview(doc: pymupdf.Document) -> Tuple[str, List[str], List[str]]:
    """Extract Editorial title, In a Nutshell bullets and Market Commentary prose without column collisions."""
    if len(doc) == 0:
        return "", [], []
    p1 = doc[0]
    blocks = p1.get_text("blocks")
    w, h = p1.rect.width, p1.rect.height
    
    title = ""
    nutshell: List[str] = []
    commentary: List[str] = []
    
    is_recent = any("IN A NUTSHELL:" in b[4].upper() for b in blocks)
    
    if is_recent:
        for b in blocks:
            if b[6] != 0:
                continue
            txt = b[4].strip()
            if not txt:
                continue
            x0, y0, x1, y1 = b[:4]
            
            # Skip page header, dates, URLs
            if y0 < 130 or "www.xclusiv.gr" in txt:
                continue
            if "All data as of" in txt or re.match(r"^Week\s+\d+", txt, re.I):
                continue
            
            # Identify Baltic index block: sits on lower-right (x0 >= 280, y0 >= 580) or contains DRY/WET label
            if (x0 >= 280 and y0 >= 580) or "DRY\nWET" in txt or "WET\nDRY" in txt:
                continue
            if re.search(r"\b(BDI|BCI|BDTI|BCTI)\s+\d", txt) and len(txt) < 350:
                continue
            if "Average Indices" in txt and len(txt) < 100:
                continue
                
            # Nutshell block
            if "IN A NUTSHELL:" in txt.upper() or (x0 >= w * 0.45 and y0 < 380 and ("•" in txt or "-" in txt or len(txt) < 400)):
                clean_n = txt.replace("IN A NUTSHELL:", "").strip()
                for line in clean_n.splitlines():
                    line = line.strip()
                    if line and not line.startswith("All data as of") and not line.startswith("Week "):
                        line = re.sub(r"^[•\-\*\u2022\ufffd\s]+", "- ", line)
                        if not line.startswith("- "):
                            line = "- " + line
                        line = line.replace("\ufffd", "'")
                        nutshell.append(line)
            # Editorial title
            elif y0 < 200 and len(txt) < 80 and not txt.startswith("-"):
                clean_t = txt.replace("\ufffd", "'").replace("\n", " ").strip()
                if clean_t and clean_t.upper() != "MARKET OVERVIEW":
                    title = clean_t
            else:
                # Editorial / commentary paragraphs
                clean_c = txt.replace("MARKET COMMENTARY:", "").strip()
                clean_c = clean_c.replace("\ufffd", "'")
                clean_c = re.sub(r"\s+", " ", clean_c).strip()
                if len(clean_c) > 60 and not clean_c.startswith("Week") and "www.xclusiv.gr" not in clean_c:
                    commentary.append(clean_c)
    else:
        # 2021-2023 layout: Left column (x1 < w * 0.55) contains prose
        for b in blocks:
            if b[6] != 0:
                continue
            txt = b[4].strip()
            x0, y0, x1, y1 = b[:4]
            if not txt or y0 < 60 or y1 > h - 40:
                continue
            if "XCLUSIV SHIPBROKERS" in txt or "Kifissias" in txt or "www.xclusiv.gr" in txt:
                continue
            if any(idx in txt for idx in ["NEWBUILDING PRICES", "DEMOLITION PRICES"]):
                continue
            if (x0 >= 280 and y0 >= 580) or re.search(r"\b(BDI|BCI|BDTI|BCTI)\s+\d", txt):
                continue
            if x1 <= w * 0.55:
                clean_c = txt.replace("Market Commentary:", "").strip()
                clean_c = clean_c.replace("\ufffd", "'")
                clean_c = re.sub(r"\s+", " ", clean_c).strip()
                if len(clean_c) > 40:
                    commentary.append(clean_c)
                    
    return title, nutshell, commentary


def extract_baltic_indices(
    doc: pymupdf.Document, issue_date: str, report_week: int, source_file: str
) -> List[Dict[str, Any]]:
    """Extract Baltic dry and wet freight indices from Page 1."""
    records = []
    if len(doc) == 0:
        return records
    p1 = doc[0]
    txt = p1.get_text()
    
    pattern = re.compile(
        r"\b(BDI|BCI|BPI|BSI|BHSI|BDTI|BCTI)\s+([\d,]+)\s+([\d,]+)\s+([\+\-]?[\d\.]+%?)(?:\s+([\d,]+))?(?:\s+([\d,]+))?(?:\s+([\d,]+))?"
    )
    for m in pattern.finditer(txt):
        idx_name = m.group(1)
        val_curr = float(m.group(2).replace(",", ""))
        val_prev = float(m.group(3).replace(",", ""))
        chg_pct = m.group(4)
        avg_1 = float(m.group(5).replace(",", "")) if m.group(5) else None
        avg_2 = float(m.group(6).replace(",", "")) if m.group(6) else None
        avg_3 = float(m.group(7).replace(",", "")) if m.group(7) else None
        
        sector = "Wet" if idx_name in ["BDTI", "BCTI"] else "Dry"
        records.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "sector": sector,
            "index_name": idx_name,
            "index_value": val_curr,
            "prev_value": val_prev,
            "change_pct": chg_pct,
            "avg_year_1": avg_1,
            "avg_year_2": avg_2,
            "avg_year_3": avg_3,
            "source_file": source_file,
        })
        
    return records


def extract_snp_activity(doc: pymupdf.Document) -> Tuple[str, str]:
    """Extract narrative commentary text boxes for Dry S&P Activity and Tanker S&P Activity."""
    dry_activity: List[str] = []
    wet_activity: List[str] = []
    
    max_pages = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    for pno in range(max_pages):
        pg = doc[pno]
        txt = pg.get_text()
        blocks = pg.get_text("blocks")
        
        # Check for Dry S&P Activity
        if "Dry S&P Activity:" in txt or "Dry SnP Activity:" in txt:
            hdr_y = None
            for b in blocks:
                if "Dry S&P Activity:" in b[4] or "Dry SnP Activity:" in b[4]:
                    hdr_y = b[1]
                    rem = re.sub(r"Dry S[&n]P Activity:\s*", "", b[4], flags=re.I).strip()
                    if len(rem) > 10:
                        dry_activity.append(rem)
                    break
            if hdr_y is not None:
                for b in blocks:
                    if b[6] != 0:
                        continue
                    btxt = b[4].strip()
                    if not btxt:
                        continue
                    if hdr_y < b[1] < 500:
                        if any(term in btxt.upper() for term in ["BULK CARRIER SALES", "DRY SECONDHAND", "WWW.XCLUSIV.GR", "PAGE"]):
                            continue
                        if re.search(r"^(?:Resale|5 Year|10 Year|15 Year|Capesize|Kamsarmax|Ultramax|Handysize|\d+[\.,]\d+)", btxt):
                            continue
                        clean = re.sub(r"\s+", " ", btxt.replace("\ufffd", "'")).strip()
                        if any(term in clean for term in ["Average Prices", "Resale prices refer", "second-hand prices refer", "±%"]):
                            continue
                        if len(clean) > 25 and clean not in dry_activity:
                            dry_activity.append(clean)

        # Check for Tanker S&P Activity
        if "Tanker S&P Activity:" in txt or "Tanker SnP Activity:" in txt:
            hdr_y = None
            for b in blocks:
                if "Tanker S&P Activity:" in b[4] or "Tanker SnP Activity:" in b[4]:
                    hdr_y = b[1]
                    rem = re.sub(r"Tanker S[&n]P Activity:\s*", "", b[4], flags=re.I).strip()
                    if len(rem) > 10:
                        wet_activity.append(rem)
                    break
            if hdr_y is not None:
                for b in blocks:
                    if b[6] != 0:
                        continue
                    btxt = b[4].strip()
                    if not btxt:
                        continue
                    if hdr_y < b[1] < 500:
                        if any(term in btxt.upper() for term in ["TANKER SALES", "TANKER SECONDHAND", "WWW.XCLUSIV.GR", "PAGE"]):
                            continue
                        if re.search(r"^(?:Resale|5 Year|10 Year|15 Year|VLCC|Suezmax|Aframax|MR2|\d+[\.,]\d+)", btxt):
                            continue
                        clean = re.sub(r"\s+", " ", btxt.replace("\ufffd", "'")).strip()
                        if any(term in clean for term in ["Average Prices", "Resale prices refer", "second-hand prices refer", "±%"]):
                            continue
                        if len(clean) > 25 and clean not in wet_activity:
                            wet_activity.append(clean)
                            
        # 2021-2023 reports where sales commentary is on S&P pages without "S&P Activity:" banner
        if not dry_activity and "BULK CARRIER SALES" in txt.upper() and pno in [3, 4]:
            for b in blocks:
                if b[6] != 0:
                    continue
                btxt = b[4].strip()
                if 80 < b[1] < 250 and len(btxt) > 50:
                    if not any(term in btxt.upper() for term in ["BULK CARRIER SALES", "WWW.XCLUSIV.GR", "PAGE", "NAME", "DWT"]):
                        clean = re.sub(r"\s+", " ", btxt.replace("\ufffd", "'")).strip()
                        if clean not in dry_activity and not any(term in clean for term in ["Average Prices", "Resale prices refer"]):
                            dry_activity.append(clean)
                            
        if not wet_activity and "TANKER SALES" in txt.upper() and pno in [4, 5]:
            for b in blocks:
                if b[6] != 0:
                    continue
                btxt = b[4].strip()
                if 80 < b[1] < 250 and len(btxt) > 50:
                    if not any(term in btxt.upper() for term in ["TANKER SALES", "WWW.XCLUSIV.GR", "PAGE", "NAME", "DWT"]):
                        if not re.search(r"\b\d{2,3},\d{3}\b", btxt):
                            clean = re.sub(r"\s+", " ", btxt.replace("\ufffd", "'")).strip()
                            if clean not in wet_activity and not any(term in clean for term in ["Average Prices", "Resale prices refer"]):
                                wet_activity.append(clean)

    return "\n\n".join(dry_activity), "\n\n".join(wet_activity)


def extract_freight_commentary(doc: pymupdf.Document) -> Dict[str, str]:
    """Extract prose commentary for dry bulk and tankers from pages 2 and 3."""
    freight: Dict[str, str] = {}
    if len(doc) < 3:
        return freight
        
    for p_idx, key, title_skip in [(1, "Dry Bulk Freight", "Freight Market - Dry"), (2, "Tanker Freight", "Freight Market - Wet")]:
        p = doc[p_idx]
        blocks = []
        for b in p.get_text("blocks"):
            if b[6] != 0:
                continue
            txt = b[4].strip()
            if not txt:
                continue
            # Commentary column is on the left margin (x < 60), below header (y > 60), above footer (y < 808)
            # Rejects chart titles, legends, and y-axis ticks which start at x >= 265
            if b[0] < 60 and b[1] > 60 and b[1] < 808:
                if title_skip in txt or "www.xclusiv.gr" in txt:
                    continue
                txt = txt.replace("\ufffd", "'")
                txt = re.sub(r"\s+", " ", txt).strip()
                if len(txt) > 20 and not re.match(r"^[\d,\.\-\$\s/]+$", txt):
                    blocks.append(txt)
        if blocks:
            freight[key] = "\n\n".join(blocks)
        
    return freight



# ---------------------------------------------------------------------------
# Markdown Generator (Gold Standard)
# ---------------------------------------------------------------------------

def generate_markdown(
    stem: str,
    pdf_path: Path,
    doc: pymupdf.Document,
    issue_date: str,
    report_week: int,
    editorial_title: str,
    nutshell: List[str],
    commentary: List[str],
    baltic_indices: List[Dict[str, Any]],
    freight: Dict[str, str],
    nb_prices: List[Dict[str, Any]],
    nb_orders: List[Dict[str, Any]],
    sh_prices: List[Dict[str, Any]],
    dry_activity: str,
    wet_activity: str,
    sales: List[Dict[str, Any]],
    demo_prices: List[Dict[str, Any]],
    demo_sales: List[Dict[str, Any]],
) -> str:
    year = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    max_useful = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)
    
    # Frontmatter
    lines = [
        "---",
        f'title: "Xclusiv Shipbrokers Weekly Market Report - Week {report_week}, {year}"',
        f'issue_date: "{issue_date}"',
        f'report_week: {report_week}',
        f'year: {year}',
        'broker: "Xclusiv Shipbrokers"',
        'source: "xclusiv"',
        f'source_file: "corpus/01-brokers/xclusiv/{year}/{pdf_path.name}"',
        f'pages: {len(doc)}',
        f'useful_pages: {max_useful}',
        f'editorial_title: "{editorial_title}"' if editorial_title else 'editorial_title: null',
        f'sales_count: {len(sales)}',
        f'demo_sales_count: {len(demo_sales)}',
        f'secondhand_prices_count: {len(sh_prices)}',
        f'newbuilding_prices_count: {len(nb_prices)}',
        f'demolition_prices_count: {len(demo_prices)}',
        f'baltic_indices_count: {len(baltic_indices)}',
        "---",
        "",
        f"# Xclusiv Shipbrokers Weekly Market Report - Week {report_week}, {year}",
        "",
        f"- **Publisher**: Xclusiv Shipbrokers Inc.",
        f"- **Issue Date**: {issue_date} (Week {report_week})",
        f"- **Source**: `corpus/01-brokers/xclusiv/{year}/{pdf_path.name}`",
        f"- **Pages**: {len(doc)} (Cover-to-cover extraction of useful pages 1 to {max_useful}; final 2 pages discarded per notes)",
        "",
        "---",
        "",
        "## Market Overview",
        "",
    ]
    
    if editorial_title:
        lines.append(f"### Editorial: {editorial_title}\n")
    elif commentary:
        lines.append("### Desk Commentary\n")
        
    if commentary:
        for para in commentary:
            lines.append(f"{para}\n")
            
    if nutshell:
        lines.append("### In a Nutshell\n")
        lines.extend(nutshell)
        lines.append("")
        
    if baltic_indices:
        lines.extend([
            "### Baltic Exchange Freight Indices",
            "",
            "| Index | Current | Previous | Change (%) | 3Y Trend / Historical Averages |",
            "|---|---|---|---|---|",
        ])
        for b in baltic_indices:
            val_c = f"{b['index_value']:,.0f}" if b.get('index_value') else "-"
            val_p = f"{b['prev_value']:,.0f}" if b.get('prev_value') else "-"
            chg = b.get('change_pct', '-')
            hist_parts = []
            if b.get('avg_year_1'): hist_parts.append(f"2026: {b['avg_year_1']:,.0f}")
            if b.get('avg_year_2'): hist_parts.append(f"2025: {b['avg_year_2']:,.0f}")
            if b.get('avg_year_3'): hist_parts.append(f"2024: {b['avg_year_3']:,.0f}")
            hist_str = " / ".join(hist_parts) if hist_parts else "-"
            lines.append(f"| {b.get('index_name')} | {val_c} | {val_p} | {chg} | {hist_str} |")
        lines.append("")

    if freight:
        lines.extend(["---", "", "## Freight Market Analysis", ""])
        for sec_name, sec_text in freight.items():
            lines.extend([f"### {sec_name}\n", f"{sec_text}\n"])

    lines.extend([
        "---",
        "",
        "## Newbuilding Market",
        "",
    ])
    
    if nb_prices:
        lines.extend([
            "### Indicative Newbuilding Prices ($ mills)",
            "",
            "| Sector | Vessel Type | Price ($M) |",
            "|---|---|---|",
        ])
        for np in nb_prices:
            lines.append(f"| {np.get('sector', '')} | {np.get('vessel_type', '')} | ${np.get('price_usd_mill', '')}M |")
        lines.append("")
        
    if nb_orders:
        lines.extend([
            "### Newbuilding Orders",
            "",
            "| Type | Units | Size | Yard | Buyer | Price | Delivery | Comments |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for o in nb_orders:
            lines.append(
                f"| {o.get('type', '')} | {o.get('units', '')} | {o.get('size', '')} | {o.get('yard', '')} | {o.get('buyer', '')} | {o.get('price', '')} | {o.get('delivery', '')} | {o.get('comments', '')} |"
            )
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Sale & Purchase Market",
        "",
    ])
    
    # Secondhand Prices Dry & Wet
    dry_sh = [s for s in sh_prices if s.get("sector") == "Dry"]
    wet_sh = [s for s in sh_prices if s.get("sector") == "Tanker"]
    
    if dry_sh:
        lines.extend([
            "### Dry Secondhand Prices ($ mills)",
            "",
            "| Vessel Type | Tenor | Price ($M) |",
            "|---|---|---|",
        ])
        for ds in dry_sh:
            lines.append(f"| {ds.get('vessel_type', '')} | {ds.get('tenor', '')} | ${ds.get('price_usd_mill', '')}M |")
        lines.append("")
        
    if dry_activity:
        lines.extend([
            "### Dry S&P Activity Commentary",
            "",
            dry_activity,
            "",
        ])
        
    # Bulker sales
    bulker_sales = [s for s in sales if "bulk" in s.get("section", "").lower()]
    lines.extend([
        "### Bulk Carrier Sales",
        "",
        "| Section | Name | Type | DWT | Year | Country | Yard | Buyers | Price ($M) | Comments |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    if bulker_sales:
        for s in bulker_sales:
            p_str = f"${s['PRICE_USD_MILL']}M" if s.get("PRICE_USD_MILL") else (s.get("PRICE") or "-")
            buyers_str = s.get("BUYERS") or "-"
            comments_str = s.get("COMMENTS") or "-"
            lines.append(
                f"| {s.get('section', '')} | {s.get('NAME', '')} | {s.get('TYPE', '')} | {s.get('DWT', '')} | {s.get('YEAR', '')} | {s.get('COUNTRY', '')} | {s.get('YARD', '')} | {buyers_str} | {p_str} | {comments_str} |"
            )
    else:
        lines.append("| Bulk Carriers | - | - | - | - | - | - | - | - | No bulker sales reported |")
    lines.append("")
    
    if wet_sh:
        lines.extend([
            "### Tanker Secondhand Prices ($ mills)",
            "",
            "| Vessel Type | Tenor | Price ($M) |",
            "|---|---|---|",
        ])
        for ws in wet_sh:
            lines.append(f"| {ws.get('vessel_type', '')} | {ws.get('tenor', '')} | ${ws.get('price_usd_mill', '')}M |")
        lines.append("")
        
    if wet_activity:
        lines.extend([
            "### Tanker S&P Activity Commentary",
            "",
            wet_activity,
            "",
        ])
        
    tanker_sales = [s for s in sales if "tank" in s.get("section", "").lower()]
    lines.extend([
        "### Tanker Sales",
        "",
        "| Section | Name | Type | DWT | Year | Country | Yard | Buyers | Price ($M) | Comments |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    if tanker_sales:
        for s in tanker_sales:
            p_str = f"${s['PRICE_USD_MILL']}M" if s.get("PRICE_USD_MILL") else (s.get("PRICE") or "-")
            buyers_str = s.get("BUYERS") or "-"
            comments_str = s.get("COMMENTS") or "-"
            lines.append(
                f"| {s.get('section', '')} | {s.get('NAME', '')} | {s.get('TYPE', '')} | {s.get('DWT', '')} | {s.get('YEAR', '')} | {s.get('COUNTRY', '')} | {s.get('YARD', '')} | {buyers_str} | {p_str} | {comments_str} |"
            )
    else:
        lines.append("| Tankers | - | - | - | - | - | - | - | - | No tanker sales reported |")
    lines.append("")

    other_sales = [s for s in sales if s not in bulker_sales and s not in tanker_sales]
    if other_sales:
        lines.extend([
            "### Other Reported Sales (Gas / Containers)",
            "",
            "| Section | Name | Type | DWT | Year | Country | Yard | Buyers | Price ($M) | Comments |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ])
        for s in other_sales:
            p_str = f"${s['PRICE_USD_MILL']}M" if s.get("PRICE_USD_MILL") else (s.get("PRICE") or "-")
            buyers_str = s.get("BUYERS") or "-"
            comments_str = s.get("COMMENTS") or "-"
            lines.append(
                f"| {s.get('section', '')} | {s.get('NAME', '')} | {s.get('TYPE', '')} | {s.get('DWT', '')} | {s.get('YEAR', '')} | {s.get('COUNTRY', '')} | {s.get('YARD', '')} | {buyers_str} | {p_str} | {comments_str} |"
            )
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Demolition Market",
        "",
        "### Indicative Demolition Scrap Prices ($/LDT)",
        "",
        "| Segment | Country | Price ($/LDT) |",
        "|---|---|---|",
    ])
    if demo_prices:
        for dp in demo_prices:
            lines.append(f"| {dp.get('segment', '')} | {dp.get('country', '')} | ${dp.get('price_usd_per_ldt', '')} |")
    else:
        lines.append("| - | - | No indicative demolition prices reported |")
    lines.append("")

    lines.extend([
        "### Reported Demolition Sales",
        "",
        "| Name | Type | Year | DWT | LDT | Country | Price ($/LDT) | Buyers | Comments |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    if demo_sales:
        for ds in demo_sales:
            p_ldt = f"${ds['PRICE_USD_PER_LDT']}" if ds.get("PRICE_USD_PER_LDT") else (ds.get("PRICE_RAW") or "N/A")
            buyers_str = ds.get("BUYERS") or "-"
            comments_str = ds.get("COMMENTS") or "-"
            lines.append(
                f"| {ds.get('NAME', '')} | {ds.get('TYPE', '')} | {ds.get('YEAR', '')} | {ds.get('DWT', '')} | {ds.get('LDT', '')} | {ds.get('COUNTRY', '')} | {p_ldt} | {buyers_str} | {comments_str} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - | No demolition sales reported |")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Legal Disclaimer",
        "",
        "> *All information & data contained in this report has been taken from market sources and proprietary databases. All data, info, charts, views and news contained in this report are property of Xclusiv Shipbrokers Inc.*",
        ""
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Document Processor
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    doc = pymupdf.open(pdf_path)
    stem = pdf_path.stem
    issue_date, report_week = extract_meta(doc, pdf_path)

    editorial_title, nutshell, commentary = extract_market_overview(doc)
    baltic = extract_baltic_indices(doc, issue_date, report_week, pdf_path.name)
    dry_act, wet_act = extract_snp_activity(doc)
    freight = extract_freight_commentary(doc)

    sales = extract_sales_tables(doc, issue_date, report_week, pdf_path.name)
    demo_sales = extract_demo_sales_tables(doc, issue_date, report_week, pdf_path.name)
    demo_prices = extract_indicative_demolition(doc, issue_date, report_week, pdf_path.name)
    sh_prices = extract_secondhand_prices(doc, issue_date, report_week, pdf_path.name)
    nb_orders = extract_newbuilding_orders(doc, issue_date, report_week, pdf_path.name)
    nb_prices = extract_newbuilding_prices(doc, issue_date, report_week, pdf_path.name)

    max_useful = max(1, len(doc) - 2) if len(doc) >= 6 else len(doc)

    sidecar_json = {
        "stem": stem,
        "source_file": pdf_path.name,
        "issue_date": issue_date,
        "report_week": report_week,
        "pages": len(doc),
        "useful_pages": max_useful,
        "editorial_title": editorial_title,
        "nutshell": nutshell,
        "market_commentary": commentary,
        "baltic_indices": baltic,
        "freight_commentary": freight,
        "dry_snp_activity": dry_act,
        "wet_snp_activity": wet_act,
        "reported_sales": sales,
        "demo_sales": demo_sales,
        "newbuilding_orders": nb_orders,
        "indicative_demolition_prices": demo_prices,
        "indicative_secondhand_prices": sh_prices,
        "indicative_newbuilding_prices": nb_prices,
    }

    md_content = generate_markdown(
        stem, pdf_path, doc, issue_date, report_week,
        editorial_title, nutshell, commentary, baltic, freight,
        nb_prices, nb_orders, sh_prices, dry_act, wet_act,
        sales, demo_prices, demo_sales
    )

    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    dest_dir = OUT_MD / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Write to year-subfolder
    (dest_dir / f"{stem}.tables.json").write_text(
        json.dumps(sidecar_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (dest_dir / f"{stem}.md").write_text(md_content, encoding="utf-8")

    # Also sync to top-level OUT_MD for backward-compatibility
    (OUT_MD / f"{stem}.tables.json").write_text(
        json.dumps(sidecar_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_MD / f"{stem}.md").write_text(md_content, encoding="utf-8")

    return {
        "stem": stem,
        "issue_date": issue_date,
        "report_week": report_week,
        "sales": sales,
        "demo_sales": demo_sales,
        "demo_prices": demo_prices,
        "sh_prices": sh_prices,
        "nb_orders": nb_orders,
        "nb_prices": nb_prices,
        "baltic": baltic,
    }


# ---------------------------------------------------------------------------
# Corpus Execution & CSV Series Stacking
# ---------------------------------------------------------------------------

SALES_COLUMNS = [
    "issue_date", "report_week", "section", "page", "NAME", "TYPE", "DWT", "YEAR",
    "COUNTRY", "YARD", "BUYERS", "PRICE", "PRICE_USD_MILL", "COMMENTS", "source_file"
]

DEMO_PRICES_COLUMNS = [
    "issue_date", "report_week", "segment", "country", "price_usd_per_ldt", "source_file"
]

SECONDHAND_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_type", "tenor", "price_usd_mill", "source_file"
]

DEMO_SALES_COLUMNS = [
    "issue_date", "report_week", "NAME", "TYPE", "YEAR", "DWT", "LDT", "COUNTRY",
    "PRICE_USD_PER_LDT", "BUYERS", "COMMENTS", "source_file"
]


BALTIC_COLUMNS = [
    "issue_date", "report_week", "sector", "index_name", "index_value", "prev_value",
    "change_pct", "avg_year_1", "avg_year_2", "avg_year_3", "source_file"
]

NB_PRICES_COLUMNS = [
    "issue_date", "report_week", "sector", "vessel_type", "price_usd_mill", "source_file"
]


def write_series_csvs(
    all_sales: List[Dict[str, Any]],
    all_demo_prices: List[Dict[str, Any]],
    all_sh_prices: List[Dict[str, Any]],
    all_demo_sales: List[Dict[str, Any]],
    all_baltic: List[Dict[str, Any]],
    all_nb_prices: List[Dict[str, Any]],
) -> None:
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    with open(SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SALES_COLUMNS)
        writer.writeheader()
        for r in all_sales:
            writer.writerow({k: r.get(k, "") for k in SALES_COLUMNS})

    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEMO_PRICES_COLUMNS)
        writer.writeheader()
        for r in all_demo_prices:
            writer.writerow({k: r.get(k, "") for k in DEMO_PRICES_COLUMNS})

    with open(SECONDHAND_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SECONDHAND_COLUMNS)
        writer.writeheader()
        for r in all_sh_prices:
            writer.writerow({k: r.get(k, "") for k in SECONDHAND_COLUMNS})

    with open(DEMO_SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEMO_SALES_COLUMNS)
        writer.writeheader()
        for r in all_demo_sales:
            writer.writerow({k: r.get(k, "") for k in DEMO_SALES_COLUMNS})

    if all_baltic:
        with open(BALTIC_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BALTIC_COLUMNS)
            writer.writeheader()
            for r in all_baltic:
                writer.writerow({k: r.get(k, "") for k in BALTIC_COLUMNS})

    if all_nb_prices:
        with open(NB_PRICES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=NB_PRICES_COLUMNS)
            writer.writeheader()
            for r in all_nb_prices:
                writer.writerow({k: r.get(k, "") for k in NB_PRICES_COLUMNS})


def main() -> None:
    parser = argparse.ArgumentParser(description="Xclusiv Shipbrokers Table Extractor")
    parser.add_argument("--sample", action="store_true", help="Run multi-era sample")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--all", action="store_true", help="Process all 266 corpus files")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4), help="Number of worker processes")
    args = parser.parse_args()

    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    _dup = byte_duplicate_stems()
    if _dup:
        _b = len(all_pdfs)
        all_pdfs = [p for p in all_pdfs if p.stem not in _dup]
        print(f"[dedup] skipped {_b - len(all_pdfs)} byte-identical duplicate document(s)")

    if args.file:
        target_pdfs = [Path(args.file)]
    elif args.sample:
        sample_names = [
            "xclusiv_15_09_2026_xclusiv_shipbrokers_weekly_14th_september_2026.pdf",
            "xclusiv_2024_xclusiv-2024_01_08.pdf",
            "xclusiv_2023_xclusiv_weekly_2023_07_03.pdf",
            "xclusiv_2022_xclusiv_weekly_2022_07_01.pdf",
            "xclusiv_2021_xclusiv_weekly_2021_07_26.pdf",
        ]
        target_pdfs = [p for p in all_pdfs if p.name in sample_names]
    else:
        # Default to all
        target_pdfs = all_pdfs

    print(f"[{PUB}] Processing {len(target_pdfs)} PDFs (total available: {len(all_pdfs)}) using {args.workers} workers...", flush=True)

    total_sales: List[Dict[str, Any]] = []
    total_demo_prices: List[Dict[str, Any]] = []
    total_sh_prices: List[Dict[str, Any]] = []
    total_demo_sales: List[Dict[str, Any]] = []
    total_baltic: List[Dict[str, Any]] = []
    total_nb_prices: List[Dict[str, Any]] = []

    t0 = time.time()
    ok_count = 0
    fail_count = 0

    if args.sample or len(target_pdfs) == 1 or args.workers <= 1:
        for idx, pth in enumerate(target_pdfs, 1):
            try:
                res = process_pdf(pth)
                total_sales.extend(res["sales"])
                total_demo_prices.extend(res["demo_prices"])
                total_sh_prices.extend(res["sh_prices"])
                total_demo_sales.extend(res["demo_sales"])
                total_baltic.extend(res.get("baltic", []))
                total_nb_prices.extend(res.get("nb_prices", []))
                ok_count += 1
                if idx % 25 == 0 or idx == len(target_pdfs) or args.sample:
                    print(
                        f"  [{idx}/{len(target_pdfs)}] {pth.stem[:48]:<48} "
                        f"sales={len(res['sales']):>2} demo_p={len(res['demo_prices']):>2} "
                        f"sh={len(res['sh_prices']):>2} demo_s={len(res['demo_sales']):>2} "
                        f"baltic={len(res.get('baltic', [])):>1} "
                        f"({time.time()-t0:.1f}s)",
                        flush=True,
                    )
            except Exception as e:
                fail_count += 1
                print(f"  [{idx}/{len(target_pdfs)}] {pth.stem[:48]:<48} FAILED: {type(e).__name__}: {e}", flush=True)
                traceback.print_exc(limit=2)
    else:
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_pdf = {executor.submit(process_pdf, p): p for p in target_pdfs}
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_pdf), 1):
                pth = future_to_pdf[future]
                try:
                    res = future.result()
                    total_sales.extend(res["sales"])
                    total_demo_prices.extend(res["demo_prices"])
                    total_sh_prices.extend(res["sh_prices"])
                    total_demo_sales.extend(res["demo_sales"])
                    total_baltic.extend(res.get("baltic", []))
                    total_nb_prices.extend(res.get("nb_prices", []))
                    ok_count += 1
                    if idx % 25 == 0 or idx == len(target_pdfs):
                        print(
                            f"  [{idx}/{len(target_pdfs)}] {pth.stem[:48]:<48} "
                            f"sales={len(res['sales']):>2} demo_p={len(res['demo_prices']):>2} "
                            f"sh={len(res['sh_prices']):>2} demo_s={len(res['demo_sales']):>2} "
                            f"baltic={len(res.get('baltic', [])):>1} "
                            f"({time.time()-t0:.1f}s)",
                            flush=True,
                        )
                except Exception as e:
                    fail_count += 1
                    print(f"  [{idx}/{len(target_pdfs)}] {pth.stem[:48]:<48} FAILED: {type(e).__name__}: {e}", flush=True)

    # Sort stacked rows deterministically by issue_date then section/vessel
    total_sales.sort(key=lambda x: (x.get("issue_date", ""), x.get("section", ""), x.get("NAME", "")))
    total_demo_prices.sort(key=lambda x: (x.get("issue_date", ""), x.get("segment", ""), x.get("country", "")))
    total_sh_prices.sort(key=lambda x: (x.get("issue_date", ""), x.get("sector", ""), x.get("vessel_type", ""), x.get("tenor", "")))
    total_demo_sales.sort(key=lambda x: (x.get("issue_date", ""), x.get("NAME", "")))
    total_baltic.sort(key=lambda x: (x.get("issue_date", ""), x.get("sector", ""), x.get("index_name", "")))
    total_nb_prices.sort(key=lambda x: (x.get("issue_date", ""), x.get("sector", ""), x.get("vessel_type", "")))

    # Write series CSVs
    write_series_csvs(total_sales, total_demo_prices, total_sh_prices, total_demo_sales, total_baltic, total_nb_prices)

    print("\n" + "=" * 70)
    print(f"[{PUB}] EXTRACTION SUMMARY:")
    print(f"  PDFs processed: {ok_count} ok, {fail_count} failed, total {len(target_pdfs)}")
    print(f"  Total S&P Sales deals: {len(total_sales)}")
    print(f"  Total Indicative Demolition Price points: {len(total_demo_prices)}")
    print(f"  Total Indicative Secondhand Price points: {len(total_sh_prices)}")
    print(f"  Total Demolition Sales deals: {len(total_demo_sales)}")
    print(f"  Total Baltic Index points: {len(total_baltic)}")
    print(f"  Total Indicative Newbuilding points: {len(total_nb_prices)}")
    print(f"  CSV Series Outputs:")
    print(f"    - {SALES_SERIES_CSV}")
    print(f"    - {DEMO_SERIES_CSV}")
    print(f"    - {SECONDHAND_SERIES_CSV}")
    print(f"    - {DEMO_SALES_SERIES_CSV}")
    print(f"    - {BALTIC_SERIES_CSV}")
    print(f"    - {NB_PRICES_SERIES_CSV}")
    print(f"  Elapsed time: {time.time()-t0:.1f}s")
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
