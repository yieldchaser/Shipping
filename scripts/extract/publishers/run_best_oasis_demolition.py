#!/usr/bin/env python3
"""
Best Oasis Ship Recycling Reports - Production Extraction Pipeline
===================================================================

Extracts structured demolition market intelligence from Best Oasis weekly reports:
1. Indicative Demolition Prices ($/LDT for Container, Tanker, Bulker, HMS, Shredded)
2. Demolition Deals / Vessels Sold fixtures (Vessel Name, Type, IMO, Built, Yard, LDT, Terms, Location, Price)
3. Market Commentary & Country Intelligence (General Overview, India, Bangladesh, Pakistan, Turkey)
4. Macro Indicators & Currencies (USD/INR, USD/BDT, USD/PKR, USD/TRY, Brent Crude, WTI Crude)

Output Deliverables:
- Clean Markdown: data/extracted/md/hellenic/demolition/best_oasis/<year>/
- Structured JSON sidecars: data/extracted/md/hellenic/demolition/best_oasis/<year>/*.tables.json
- Master Stacked Series:
  * data/extracted/series/best_oasis_demolition_series.csv
  * data/extracted/series/best_oasis_deals_series.csv
  * data/extracted/series/best_oasis_market_commentary_series.csv
  * data/extracted/series/best_oasis_exchange_rates_series.csv
  (plus mirrors in data/extracted/series/hellenic_best_oasis_*.csv)
"""

import os
import re
import csv
import json
import glob
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

import pymupdf as fitz


REPO_ROOT = Path("c:/Users/Dell/Github/Shipping")
SOURCE_DIR = REPO_ROOT / "corpus/02-hellenic/demolition/pdfs/best_oasis"
MD_BASE_DIR = REPO_ROOT / "data/extracted/md/hellenic/demolition/best_oasis"
SERIES_DIR = REPO_ROOT / "data/extracted/series"
CACHE_DIR = REPO_ROOT / "data/extracted/cache_best_oasis"


def get_unique_files(source_dir: Path) -> List[Tuple[Path, str, str]]:
    """
    Deduplicates PDFs using SHA-256 and extracts ISO date from filename.
    Returns list of (filepath, sha256_hash, issue_date).
    """
    files = sorted(source_dir.glob("*.pdf"))
    by_hash = defaultdict(list)
    for f in files:
        with open(f, "rb") as fp:
            h = hashlib.sha256(fp.read()).hexdigest()
        by_hash[h].append(f)

    unique = []
    for h, flist in by_hash.items():
        # Pick cleanest filename (prefer shorter filename)
        chosen = sorted(flist, key=lambda x: (len(x.name), x.name))[0]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", chosen.name)
        issue_date = m.group(1) if m else "unknown"
        unique.append((chosen, h, issue_date))

    unique.sort(key=lambda x: (x[2], x[0].name))
    return unique


def parse_vessels_sold_table(table_data: List[List[Any]], issue_date: str, source_file: str) -> List[Dict[str, Any]]:
    """
    Parses 'List of Vessels Sold this Week' table dynamically into structured records.
    """
    if not table_data or len(table_data) < 2:
        return []

    # Clean headers
    headers = [re.sub(r"\s+", " ", str(c or "")).strip().upper() for c in table_data[0]]

    # Map column roles dynamically
    col_map = {}
    for idx, h in enumerate(headers):
        if "NAME" in h:
            col_map["name"] = idx
        elif "TYPE" in h:
            col_map["type"] = idx
        elif "IMO" in h:
            col_map["imo"] = idx
        elif "YEAR" in h:
            col_map["year"] = idx
        elif "COUNTRY" in h:
            col_map["country"] = idx
        elif "LDT" in h and "PRICE" not in h:
            col_map["ldt"] = idx
        elif "TERM" in h:
            col_map["terms"] = idx
        elif "LOCATION" in h or "DELIVERY" in h:
            col_map["location"] = idx
        elif "PRICE" in h:
            col_map["price"] = idx

    # If header mapping missed, handle standard positional mappings
    if "name" not in col_map and len(table_data[0]) >= 6:
        if len(table_data[0]) >= 10:
            col_map = {"name": 0, "type": 1, "year": 2, "country": 5, "ldt": 6, "terms": 7, "location": 8, "price": 9}
        elif len(table_data[0]) == 9:
            col_map = {"name": 0, "type": 1, "imo": 2, "year": 3, "country": 4, "ldt": 5, "terms": 6, "location": 7, "price": 8}
        elif len(table_data[0]) == 6:
            col_map = {"name": 0, "type": 1, "ldt": 2, "terms": 3, "location": 4, "price": 5}

    records = []
    for r in table_data[1:]:
        if not r or not any(r):
            continue
        first_cell = re.sub(r"\s+", " ", str(r[0] or "")).strip()
        if not first_cell or any(k in first_cell.upper() for k in ["VESSEL", "NAME", "TOTAL", "SOURCE", "YEAR OF", "LIST OF"]):
            continue

        def get_val(key):
            idx = col_map.get(key)
            if idx is not None and idx < len(r) and r[idx] is not None:
                val = str(r[idx]).strip()
                val = re.sub(r"\s+", " ", val)
                return val if val else None
            return None

        v_name = get_val("name")
        if not v_name or len(v_name) < 2:
            continue

        v_type = get_val("type")
        imo_val = get_val("imo")
        if imo_val:
            m_imo = re.search(r"\b(\d{7})\b", imo_val)
            imo_str = m_imo.group(1) if m_imo else re.sub(r"[^\d]", "", imo_val)
        else:
            imo_str = None

        year_val = get_val("year")
        year_str = None
        if year_val:
            m_yr = re.search(r"\b(19\d\d|20\d\d)\b", year_val)
            year_str = int(m_yr.group(1)) if m_yr else None

        country_val = get_val("country")
        ldt_raw = get_val("ldt")
        ldt_clean = None
        if ldt_raw:
            c_ldt = re.sub(r"[^\d.]", "", ldt_raw)
            try:
                ldt_clean = float(c_ldt) if c_ldt else None
            except ValueError:
                pass

        terms_val = get_val("terms")
        loc_val = get_val("location")
        price_raw = get_val("price")

        price_clean = None
        price_status = "Reported"
        comments = None

        if price_raw:
            if "UNDISCLOSED" in price_raw.upper():
                price_status = "Undisclosed"
            else:
                m_num = re.search(r"(\d+(?:\.\d+)?)", price_raw.replace(",", ""))
                if m_num:
                    try:
                        price_clean = float(m_num.group(1))
                    except ValueError:
                        pass
                if "\n" in price_raw or "(" in price_raw:
                    comments = price_raw.replace("\n", " ").strip()

        records.append({
            "issue_date": issue_date,
            "vessel_name": v_name,
            "vessel_type": v_type,
            "imo": imo_str,
            "year_built": year_str,
            "country_built": country_val,
            "ldt": ldt_clean,
            "sale_terms": terms_val,
            "delivery_location": loc_val,
            "price_usd_ldt": price_clean,
            "price_status": price_status,
            "comments": comments,
            "source_file": source_file
        })

    return records


def extract_prices_from_country_page(page) -> Dict[str, float]:
    """
    Extracts ship recycling prices and scrap prices from a country page
    using 2D word geometry across 2021-2025 vector reports.
    Uses the boundary between upper and lower charts to avoid cross-contamination.
    """
    words = page.get_text("words")

    # Locate dividing line: "Price of HMS 1&2 (80:20) and Shredded"
    hms_title_y = None
    for b in page.get_text("blocks"):
        if "PRICE OF HMS" in b[4].upper() or ("HMS" in b[4].upper() and "SHREDDED" in b[4].upper() and "PRICE" in b[4].upper()):
            hms_title_y = b[1]
            break

    # Locate upper chart labels (Container, Tanker, Bulker)
    c_words = [w for w in words if w[4].lower() == "container" and (hms_title_y is None or w[1] < hms_title_y)]
    t_words = [w for w in words if w[4].lower() == "tanker" and (hms_title_y is None or w[1] < hms_title_y)]
    b_words = [w for w in words if w[4].lower() == "bulker" and (hms_title_y is None or w[1] < hms_title_y)]

    labels = {}
    if c_words:
        best_c = c_words[0]
        labels["container"] = (best_c[0], best_c[2], best_c[1], best_c[3])
        for t in t_words:
            if abs(t[1] - best_c[1]) < 20:
                labels["tanker"] = (t[0], t[2], t[1], t[3])
                break
        for b in b_words:
            if abs(b[1] - best_c[1]) < 20:
                labels["bulker"] = (b[0], b[2], b[1], b[3])
                break

    # Locate lower chart labels (HMS, Shredded)
    h_words = [w for w in words if w[4].lower() in ["hms", "hms 1&2", "80:20"] and (hms_title_y is None or w[1] > hms_title_y)]
    s_words = [w for w in words if w[4].lower() == "shredded" and (hms_title_y is None or w[1] > hms_title_y)]

    if s_words:
        best_s = sorted(s_words, key=lambda w: w[1], reverse=True)[0]
        labels["shredded"] = (best_s[0], best_s[2], best_s[1], best_s[3])
        for h in h_words:
            if abs(h[1] - best_s[1]) < 20:
                labels["hms"] = (h[0], h[2], h[1], h[3])
                break

    # Identify true y-axis ticks (columns with 4 or more stacked tick numbers)
    tick_cols = set()
    by_x = defaultdict(list)
    for w in words:
        if w[4].strip() in ["0", "50", "100", "150", "200", "250", "300", "350", "400", "450", "500", "550", "600"]:
            by_x[round(w[0], 0)].append(w[4].strip())
    for x_col, v_list in by_x.items():
        if len(v_list) >= 4:
            tick_cols.add(x_col)

    # Collect numbers (must be pure 3-digit integer like 520, 600, 386)
    nums = []
    for w in words:
        raw = w[4].strip()
        if not re.match(r"^\d{3}$", raw):
            continue
        val = float(raw)
        if any(abs(w[0] - tx) < 5 for tx in tick_cols):
            continue
        if 200 <= val <= 850:
            nums.append({"val": val, "x0": w[0], "x1": w[2], "y0": w[1], "y1": w[3], "xc": (w[0] + w[2]) / 2})

    result = {}

    # Upper chart: Container, Tanker, Bulker
    for seg in ["container", "tanker", "bulker"]:
        if seg in labels:
            lx0, lx1, ly0, ly1 = labels[seg]
            lxc = (lx0 + lx1) / 2
            cands = [n for n in nums if n["y0"] < ly0 and (hms_title_y is None or n["y0"] < hms_title_y) and abs(n["xc"] - lxc) <= 65]
            cands.sort(key=lambda x: x["xc"])
            if len(cands) == 1:
                result[f"{seg}_usd_ldt"] = cands[0]["val"]
            elif len(cands) >= 2:
                result[f"{seg}_usd_ldt"] = cands[1]["val"]

    # Lower chart: HMS, Shredded
    for seg in ["hms", "shredded"]:
        if seg in labels:
            lx0, lx1, ly0, ly1 = labels[seg]
            lxc = (lx0 + lx1) / 2
            cands = [n for n in nums if n["y0"] < ly0 and (hms_title_y is None or n["y0"] > hms_title_y) and abs(n["xc"] - lxc) <= 65]
            cands.sort(key=lambda x: x["xc"])
            key_name = "hms_80_20_usd_mt" if seg == "hms" else "shredded_usd_mt"
            if len(cands) == 1:
                result[key_name] = cands[0]["val"]
            elif len(cands) >= 2:
                result[key_name] = cands[1]["val"]

    return result


def extract_macro_indicators(doc) -> Dict[str, float]:
    """
    Extracts currencies and crude oil benchmarks across all eras.
    """
    res = {}
    for p in doc:
        t = p.get_text()
        # 1. Exchange Rates
        if any(k in t.upper() for k in ["EXCHANGE RATES", "USD / INR", "USD/INR"]):
            matches = re.findall(r"This Week\s*:\s*([\d.]+)", t, re.I)
            if len(matches) >= 4:
                try:
                    res["usd_inr"] = float(matches[0])
                    res["usd_bdt"] = float(matches[1])
                    res["usd_pkr"] = float(matches[2])
                    res["usd_try"] = float(matches[3])
                except (ValueError, IndexError):
                    pass

        # 2. Crude Oil
        m_bc = re.search(r"This Week\s*:\s*([\d.]+)[^\n]*\n(?:[^\n]*\n)?\s*Movement[^\n]*\n\s*Brent Crude", t, re.I)
        if not m_bc:
            m_bc = re.search(r"Brent Crude[^\n]*\n\s*This Week\s*:\s*([\d.]+)", t, re.I)
        if m_bc:
            try:
                res["brent_crude_usd"] = float(m_bc.group(1))
            except ValueError:
                pass

        m_wti = re.search(r"WTI Crude[^\n]*\n\s*This Week\s*:\s*([\d.]+)", t, re.I)
        if m_wti:
            try:
                res["wti_crude_usd"] = float(m_wti.group(1))
            except ValueError:
                pass

        # 2026 Crude Pattern
        m_crude_26 = re.findall(r"\(\s*([\d.]+)\s*(?:->|—>|–>|\s+)\s*([\d.]+)\s*\)", t)
        if m_crude_26 and "BRENT CRUDE" in t.upper() and len(m_crude_26) >= 2:
            try:
                res["brent_crude_usd"] = float(m_crude_26[0][1])
                res["wti_crude_usd"] = float(m_crude_26[1][1])
            except (ValueError, IndexError):
                pass

    return res


def extract_report_payload(pdf_path: Path, issue_date: str, sha_hash: str) -> Dict[str, Any]:
    """
    Parses a single Best Oasis report cover-to-cover and extracts all datasets.
    """
    rel_source = f"corpus/02-hellenic/demolition/pdfs/best_oasis/{pdf_path.name}"
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    text_len = sum(len(p.get_text().strip()) for p in doc)

    # 1. Scanned raster fallback (via cached LlamaParse markdown)
    if text_len == 0:
        cache_file = CACHE_DIR / (pdf_path.stem + ".md")
        if cache_file.exists():
            return parse_from_llamaparse_cache(cache_file, issue_date, rel_source, total_pages)
        else:
            raise RuntimeError(f"Scanned PDF {pdf_path.name} has no text and no cached LlamaParse markdown!")

    # 2. Extract Macro Indicators
    macro_data = extract_macro_indicators(doc)

    # 3. Detect Era & Extract Pricing & Commentary
    prices_list = []
    commentary_list = []
    vessels_sold_list = []
    beaching_dates = {}

    is_4_page_era = (total_pages == 4)

    if is_4_page_era:
        # Era C (4 pages): Late 2025 - 2026
        # Page 2: India, Bangladesh, Pakistan Market Summary
        p2_text = doc[1].get_text()
        for c_match in re.finditer(r"(INDIA|BANGLADESH|PAKISTAN)\s*\n(.*?)(?=(?:INDIA|BANGLADESH|PAKISTAN|\Z))", p2_text, re.S):
            country = c_match.group(1).title()
            bullets = [l.strip().lstrip("•-* ") for l in c_match.group(2).split("\n") if l.strip().startswith("•") or (l.strip() and not any(k in l.upper() for k in ["MARKET SUMMARY", "BEST OASIS"]))]
            commentary_list.append({
                "issue_date": issue_date,
                "section": country,
                "headline": "",
                "commentary": "\n".join(bullets),
                "source_file": rel_source
            })

        # Page 3: Turkiye commentary, Macro, and HMS Scrap Table
        p3_text = doc[2].get_text()
        m_trk = re.search(r"TURKIYE\s*\n(.*?)(?=(?:USD|BRENT|EXCHANGE|\Z))", p3_text, re.S | re.I)
        if m_trk:
            bullets = [l.strip().lstrip("•-* ") for l in m_trk.group(1).split("\n") if l.strip().startswith("•") or (l.strip() and not any(k in l.upper() for k in ["TURKIYE", "BEST OASIS"]))]
            commentary_list.append({
                "issue_date": issue_date,
                "section": "Turkey",
                "headline": "",
                "commentary": "\n".join(bullets),
                "source_file": rel_source
            })

        # Page 3 HMS Scrap Table (if present in 2026)
        p3_tabs = list(doc[2].find_tables())
        hms_scraps = {}
        for tab in p3_tabs:
            df = tab.extract()
            if df and any("HMS" in str(c).upper() for c in df[0]):
                for r in df[1:]:
                    if r and len(r) >= 3:
                        loc_name = str(r[0] or "").strip().title()
                        def to_flt(v):
                            m = re.search(r"(\d+(?:\.\d+)?)", str(v or ""))
                            return float(m.group(1)) if m else None
                        hms_scraps[loc_name] = {"hms": to_flt(r[1]), "shredded": to_flt(r[2])}

        # Page 4: Indicative Demolition Prices Table & Vessels Sold Table
        p4 = doc[3]
        tabs = list(p4.find_tables())
        for tab in tabs:
            df = tab.extract()
            if not df:
                continue
            hdr = " ".join([str(c) for c in df[0] if c]).upper()
            if "CONTAINER" in hdr and ("TANKER" in hdr or "BULKER" in hdr):
                # Indicative Demolition Prices Table
                for r in df[1:]:
                    if not r or len(r) < 4:
                        continue
                    loc = re.sub(r"\s+", " ", str(r[0] or "")).strip().title()
                    status = str(r[1] or "").strip().title() if len(r) > 1 else None
                    def to_float(val):
                        m = re.search(r"(\d+(?:\.\d+)?)", str(val or "").replace(",", ""))
                        return float(m.group(1)) if m else None

                    h_vals = hms_scraps.get(loc, {})
                    prices_list.append({
                        "issue_date": issue_date,
                        "location": loc,
                        "market_status": status,
                        "container_usd_ldt": to_float(r[2]),
                        "tanker_usd_ldt": to_float(r[3]),
                        "bulker_usd_ldt": to_float(r[4]) if len(r) > 4 else None,
                        "hms_80_20_usd_mt": h_vals.get("hms"),
                        "shredded_usd_mt": h_vals.get("shredded"),
                        "source_file": rel_source
                    })
            elif "VESSEL" in hdr or "LDT" in hdr or "TERM" in hdr:
                vessels_sold_list.extend(parse_vessels_sold_table(df, issue_date, rel_source))

    else:
        # Era A & B: Multi-page reports (7 to 10 pages)
        overview_text = ""
        for pno in [0, 1]:
            t = doc[pno].get_text()
            if "HIGHLIGHTS OF THE WEEK" in t.upper() or pno == 1:
                blocks = doc[pno].get_text("blocks")
                blocks.sort(key=lambda b: (b[1], b[0]))
                cur_para = []
                paras = []
                prev_bottom = 0
                for b in blocks:
                    if b[1] < 600:
                        txt = b[4].strip()
                        if len(txt) > 30 and not any(k in txt.upper() for k in ["HIGHLIGHTS", "BEST OASIS", "WEEKLY SHIP", "VISIT", "EMAIL", "HEAD OFFICE"]):
                            clean_t = txt.replace("\n", " ").strip()
                            if cur_para and (b[1] - prev_bottom < 18) and not cur_para[-1].endswith((".", "!", "?")):
                                cur_para.append(clean_t)
                            else:
                                if cur_para:
                                    paras.append(" ".join(cur_para))
                                cur_para = [clean_t]
                            prev_bottom = b[3]
                if cur_para:
                    paras.append(" ".join(cur_para))
                if paras:
                    overview_text = "\n\n".join(paras)
                    break
            elif pno == 0 and not overview_text:
                blocks = doc[pno].get_text("blocks")
                for b in blocks:
                    txt = b[4].strip()
                    if len(txt) > 200 and not any(k in txt.upper() for k in ["SABA TOWER", "CONTACT:", "DISCLAIMER"]):
                        overview_text = txt.replace("\n", " ")

        if overview_text:
            commentary_list.append({
                "issue_date": issue_date,
                "section": "General Overview",
                "headline": "",
                "commentary": overview_text,
                "source_file": rel_source
            })

        # Country Pages (India, Bangladesh, Pakistan, Turkey)
        country_aliases = [
            ("India", ["INDIA"]),
            ("Bangladesh", ["BANGLADESH"]),
            ("Pakistan", ["PAKISTAN"]),
            ("Turkey", ["TURKEY", "TÜRKIYE", "TURKIYE", "TRKIYE"])
        ]

        for std_name, aliases in country_aliases:
            found_page = None
            for pno, p in enumerate(doc):
                txt_upper = p.get_text().upper()
                if any(f"RECYCLING SHIPS IN {a}" in txt_upper or f"SHIPS IN {a}" in txt_upper for a in aliases):
                    found_page = p
                    break
                elif pno in [1, 2, 3, 4, 5] and any(a in txt_upper for a in aliases) and "PRICE" in txt_upper:
                    found_page = p
                    break

            if found_page is not None:
                # 1. Geometric Prices
                pr_dict = extract_prices_from_country_page(found_page)
                prices_list.append({
                    "issue_date": issue_date,
                    "location": std_name,
                    "market_status": None,
                    "container_usd_ldt": pr_dict.get("container_usd_ldt"),
                    "tanker_usd_ldt": pr_dict.get("tanker_usd_ldt"),
                    "bulker_usd_ldt": pr_dict.get("bulker_usd_ldt"),
                    "hms_80_20_usd_mt": pr_dict.get("hms_80_20_usd_mt"),
                    "shredded_usd_mt": pr_dict.get("shredded_usd_mt"),
                    "source_file": rel_source
                })

                # 2. Country Narrative & Beaching Dates (Left column x < 800)
                blocks = found_page.get_text("blocks")
                blocks.sort(key=lambda b: (b[1], b[0]))
                headline = ""
                body_lines = []
                beaching = []
                is_beaching = False

                for b in blocks:
                    if b[0] < 800:
                        txt = b[4].strip()
                        if not txt or any(k in txt.upper() for k in ["BEST OASIS", "WEEKLY SHIP"]):
                            continue
                        if "BEACHING DATES" in txt.upper():
                            is_beaching = True
                            b_dates = [l.strip() for l in txt.split("\n")[1:] if l.strip()]
                            beaching.extend(b_dates)
                            continue
                        if is_beaching:
                            beaching.append(txt.replace("\n", " "))
                        else:
                            if txt.upper() in [a.upper() for a in aliases]:
                                continue
                            if any(k in txt.upper() for k in ["PRICE FOR RECYCLING", "PRICE OF HMS", "PREVIOUS WEEK", "THIS WEEK", "CONTAINER", "TANKER", "BULKER"]):
                                continue
                            if not headline and len(txt) < 140 and not txt.startswith("•") and not txt.startswith("-"):
                                headline = txt.replace("\n", " ").strip()
                            else:
                                body_lines.append(txt.replace("\n", " ").strip())

                if headline or body_lines:
                    commentary_list.append({
                        "issue_date": issue_date,
                        "section": std_name,
                        "headline": headline,
                        "commentary": "\n".join(body_lines),
                        "source_file": rel_source
                    })

                if beaching:
                    beaching_dates[std_name] = "; ".join(beaching)

        # Vessels Sold Table (Page 6 or 8)
        for p in doc:
            t = p.get_text().upper()
            if "VESSELS SOLD" in t or "LIST OF VESSELS" in t:
                tabs = list(p.find_tables())
                for tab in tabs:
                    df = tab.extract()
                    if not df:
                        continue
                    hdr = " ".join([str(c) for c in df[0] if c]).upper()
                    if "VESSEL" in hdr or "LDT" in hdr or "TERM" in hdr:
                        vessels_sold_list.extend(parse_vessels_sold_table(df, issue_date, rel_source))
                break

    return {
        "issue_date": issue_date,
        "source_file": rel_source,
        "pages": total_pages,
        "prices": prices_list,
        "vessels_sold": vessels_sold_list,
        "commentary": commentary_list,
        "macro": macro_data,
        "beaching_dates": beaching_dates
    }


def parse_from_llamaparse_cache(cache_file: Path, issue_date: str, rel_source: str, total_pages: int) -> Dict[str, Any]:
    """
    Parses cached LlamaParse markdown for the single raster scanned PDF.
    """
    with open(cache_file, encoding="utf-8") as f:
        md_text = f.read()

    prices_list = []
    commentary_list = []
    vessels_sold_list = []
    beaching_dates = {}
    macro_data = {}

    pages = md_text.split("--- PAGE BREAK ---")

    # Overview
    if len(pages) > 1:
        ov = pages[1].replace("# Highlights of the Week", "").strip()
        commentary_list.append({
            "issue_date": issue_date,
            "section": "Highlights of the Week",
            "headline": "",
            "commentary": ov,
            "source_file": rel_source
        })

    # Country Pages 3, 4, 5, 6
    country_names = [("India", 2), ("Bangladesh", 3), ("Pakistan", 4), ("Turkey", 5)]
    for std_name, p_idx in country_names:
        if p_idx < len(pages):
            p_text = pages[p_idx]
            # Extract Pricing Table
            c_val, t_val, b_val = None, None, None
            m_c = re.search(r"\|\s*Container\s*\|\s*(\d+)", p_text, re.I)
            if m_c: c_val = float(m_c.group(1))
            m_t = re.search(r"\|\s*Tanker\s*\|\s*(\d+)", p_text, re.I)
            if m_t: t_val = float(m_t.group(1))
            m_b = re.search(r"\|\s*Bulker\s*\|\s*(\d+)", p_text, re.I)
            if m_b: b_val = float(m_b.group(1))

            hms_val, shr_val = None, None
            m_hms = re.search(r"\|\s*HMS[^\n|]*\|\s*(\d+)", p_text, re.I)
            if m_hms: hms_val = float(m_hms.group(1))
            m_shr = re.search(r"\|\s*Shredded\s*\|\s*(\d+)", p_text, re.I)
            if m_shr: shr_val = float(m_shr.group(1))

            prices_list.append({
                "issue_date": issue_date,
                "location": std_name,
                "market_status": None,
                "container_usd_ldt": c_val,
                "tanker_usd_ldt": t_val,
                "bulker_usd_ldt": b_val,
                "hms_80_20_usd_mt": hms_val,
                "shredded_usd_mt": shr_val,
                "source_file": rel_source
            })

            # Extract Commentary Bullets
            bullets = [l.strip().lstrip("-* ") for l in p_text.split("\n") if l.strip().startswith("-") or l.strip().startswith("*")]
            if bullets:
                commentary_list.append({
                    "issue_date": issue_date,
                    "section": std_name,
                    "headline": "",
                    "commentary": "\n".join(bullets),
                    "source_file": rel_source
                })

    # Vessels Sold Table (Page 8 / idx 7)
    if len(pages) > 7:
        p8 = pages[7]
        lines = [l.strip() for l in p8.split("\n") if l.strip().startswith("|")]
        if len(lines) >= 3:
            table_rows = [[cell.strip() for cell in l.strip("|").split("|")] for l in lines]
            table_rows = [r for r in table_rows if not all(re.match(r"^:?-+:?$", c) for c in r)]
            vessels_sold_list.extend(parse_vessels_sold_table(table_rows, issue_date, rel_source))

    return {
        "issue_date": issue_date,
        "source_file": rel_source,
        "pages": total_pages,
        "prices": prices_list,
        "vessels_sold": vessels_sold_list,
        "commentary": commentary_list,
        "macro": macro_data,
        "beaching_dates": beaching_dates
    }


def generate_markdown(payload: Dict[str, Any]) -> str:
    """
    Renders publication-grade GitHub-Flavored Markdown document.
    """
    issue_date = payload["issue_date"]
    pages = payload["pages"]
    source_file = payload["source_file"]
    prices = payload["prices"]
    vessels = payload["vessels_sold"]
    commentary = payload["commentary"]
    macro = payload["macro"]

    tables_count = (1 if prices else 0) + (1 if vessels else 0) + (1 if macro else 0)

    md = []
    # Frontmatter
    md.append("---")
    md.append(f'title: "Best Oasis Weekly Ship Recycling Report - {issue_date}"')
    md.append(f'issue_date: "{issue_date}"')
    md.append('publisher: "Best Oasis Limited"')
    md.append('source: "best_oasis"')
    md.append('category: "demolition"')
    md.append(f"pages: {pages}")
    md.append(f'source_file: "{source_file}"')
    md.append(f"tables_count: {tables_count}")
    md.append("---\n")

    md.append(f"# Best Oasis Weekly Ship Recycling Report - {issue_date}\n")

    # Macro Overview
    overview = next((c for c in commentary if c["section"] in ["General Overview", "Highlights of the Week"]), None)
    if overview and overview["commentary"]:
        md.append("## Weekly Market Overview\n")
        md.append(overview["commentary"].strip() + "\n")

    # Indicative Demolition Prices
    if prices:
        md.append("## Indicative Demolition Prices\n")
        md.append("| Location | Market Status | Container ($/LDT) | Tanker ($/LDT) | Bulker ($/LDT) | HMS 1&2 ($/MT) | Shredded ($/MT) |")
        md.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|")
        for p in prices:
            loc = p.get("location") or "N/A"
            status = p.get("market_status") or "-"
            c_val = f"${p['container_usd_ldt']:.0f}" if p.get("container_usd_ldt") else "-"
            t_val = f"${p['tanker_usd_ldt']:.0f}" if p.get("tanker_usd_ldt") else "-"
            b_val = f"${p['bulker_usd_ldt']:.0f}" if p.get("bulker_usd_ldt") else "-"
            h_val = f"${p['hms_80_20_usd_mt']:.0f}" if p.get("hms_80_20_usd_mt") else "-"
            s_val = f"${p['shredded_usd_mt']:.0f}" if p.get("shredded_usd_mt") else "-"
            md.append(f"| {loc} | {status} | {c_val} | {t_val} | {b_val} | {h_val} | {s_val} |")
        md.append("")

    # Currencies & Commodities
    if macro:
        md.append("## Exchange Rates & Macro Indicators\n")
        md.append("| Indicator | Value |")
        md.append("|:---|:---:|")
        if "usd_inr" in macro: md.append(f"| USD / INR | {macro['usd_inr']:.2f} |")
        if "usd_bdt" in macro: md.append(f"| USD / BDT | {macro['usd_bdt']:.2f} |")
        if "usd_pkr" in macro: md.append(f"| USD / PKR | {macro['usd_pkr']:.2f} |")
        if "usd_try" in macro: md.append(f"| USD / TRY | {macro['usd_try']:.2f} |")
        if "brent_crude_usd" in macro: md.append(f"| Brent Crude ($/bbl) | ${macro['brent_crude_usd']:.2f} |")
        if "wti_crude_usd" in macro: md.append(f"| WTI Crude ($/bbl) | ${macro['wti_crude_usd']:.2f} |")
        md.append("")

    # Country Intelligence
    country_comms = [c for c in commentary if c["section"] not in ["General Overview", "Highlights of the Week"]]
    if country_comms:
        md.append("## Country Market Intelligence\n")
        for c in country_comms:
            md.append(f"### {c['section']}\n")
            if c.get("headline"):
                md.append(f"**{c['headline']}**\n")
            if c.get("commentary"):
                for line in c["commentary"].split("\n"):
                    line = line.strip()
                    if line:
                        if not line.startswith("-") and not line.startswith("*"):
                            md.append(f"- {line}")
                        else:
                            md.append(line)
                md.append("")

    # Beaching Dates
    if payload.get("beaching_dates"):
        md.append("### Beaching Tide Dates\n")
        for loc, d_str in payload["beaching_dates"].items():
            md.append(f"- **{loc}**: {d_str}")
        md.append("")

    # Demolition Deals
    if vessels:
        md.append("## List of Vessels Sold for Demolition\n")
        has_imo = any(v.get("imo") for v in vessels)
        if has_imo:
            md.append("| Vessel Name | Type | IMO No. | Built | Country | LDT | Terms | Location | Price ($/LDT) |")
            md.append("|:---|:---|:---:|:---:|:---|:---:|:---|:---|:---:|")
            for v in vessels:
                name = v.get("vessel_name") or "-"
                vtype = v.get("vessel_type") or "-"
                imo = v.get("imo") or "-"
                yr = str(v.get("year_built") or "-")
                c_built = v.get("country_built") or "-"
                ldt = f"{v['ldt']:,.0f}" if v.get("ldt") else "-"
                terms = v.get("sale_terms") or "-"
                loc = v.get("delivery_location") or "-"
                pr = f"${v['price_usd_ldt']:.0f}" if v.get("price_usd_ldt") else (v.get("price_status") or "Undisclosed")
                md.append(f"| {name} | {vtype} | {imo} | {yr} | {c_built} | {ldt} | {terms} | {loc} | {pr} |")
        else:
            md.append("| Vessel Name | Type | Built | Country | LDT | Terms | Location | Price ($/LDT) |")
            md.append("|:---|:---|:---:|:---|:---:|:---|:---|:---:|")
            for v in vessels:
                name = v.get("vessel_name") or "-"
                vtype = v.get("vessel_type") or "-"
                yr = str(v.get("year_built") or "-")
                c_built = v.get("country_built") or "-"
                ldt = f"{v['ldt']:,.0f}" if v.get("ldt") else "-"
                terms = v.get("sale_terms") or "-"
                loc = v.get("delivery_location") or "-"
                pr = f"${v['price_usd_ldt']:.0f}" if v.get("price_usd_ldt") else (v.get("price_status") or "Undisclosed")
                md.append(f"| {name} | {vtype} | {yr} | {c_built} | {ldt} | {terms} | {loc} | {pr} |")
        md.append("")

    return "\n".join(md)


def main():
    print("=" * 70)
    print("BEST OASIS SHIP RECYCLING EXTRACTION PIPELINE")
    print("=" * 70)

    unique_files = get_unique_files(SOURCE_DIR)
    print(f"Total Unique Reports to Process: {len(unique_files)}")

    all_prices = []
    all_vessels = []
    all_commentary = []
    all_macro = []

    success_count = 0
    fail_count = 0

    for idx, (fpath, sha_hash, issue_date) in enumerate(unique_files, 1):
        year = issue_date[:4] if issue_date != "unknown" else "unknown"
        year_dir = MD_BASE_DIR / year
        year_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^\w\-]", "_", fpath.stem.lower())
        md_path = year_dir / f"best_oasis_{issue_date}_{slug}.md"
        json_path = year_dir / f"best_oasis_{issue_date}_{slug}.tables.json"

        try:
            payload = extract_report_payload(fpath, issue_date, sha_hash)

            # Accumulate series data
            all_prices.extend(payload["prices"])
            all_vessels.extend(payload["vessels_sold"])
            all_commentary.extend(payload["commentary"])
            if payload["macro"]:
                m_row = {"issue_date": issue_date, "source_file": payload["source_file"]}
                m_row.update(payload["macro"])
                all_macro.append(m_row)

            # Write Markdown
            md_content = generate_markdown(payload)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Write Table Sidecar JSON
            sidecar = {
                "issue_date": issue_date,
                "source_file": payload["source_file"],
                "indicative_demolition_prices": payload["prices"],
                "vessels_sold": payload["vessels_sold"],
                "market_commentary": payload["commentary"],
                "macro_indicators": payload["macro"],
                "beaching_dates": payload["beaching_dates"]
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(sidecar, f, indent=2, ensure_ascii=False)

            success_count += 1
            if idx % 25 == 0 or idx == len(unique_files):
                print(f"[{idx:3d}/{len(unique_files)}] Processed: {issue_date} - {fpath.name[:35]} (Prices: {len(payload['prices'])}, Deals: {len(payload['vessels_sold'])})")

        except Exception as e:
            fail_count += 1
            print(f"[{idx:3d}/{len(unique_files)}] ERROR on {fpath.name}: {e}")

    # Write Master Series CSVs
    SERIES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Indicative Demolition Prices Series
    p_csv = SERIES_DIR / "best_oasis_demolition_series.csv"
    p_mirror = SERIES_DIR / "hellenic_best_oasis_demolition_series.csv"
    p_cols = ["issue_date", "location", "market_status", "container_usd_ldt", "tanker_usd_ldt", "bulker_usd_ldt", "hms_80_20_usd_mt", "shredded_usd_mt", "source_file"]
    for path in [p_csv, p_mirror]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=p_cols)
            writer.writeheader()
            writer.writerows(all_prices)
    print(f"Saved Demolition Prices: {len(all_prices)} rows -> {p_csv.name}")

    # 2. Vessels Sold / Deals Series
    v_csv = SERIES_DIR / "best_oasis_deals_series.csv"
    v_mirror = SERIES_DIR / "hellenic_best_oasis_deals_series.csv"
    v_cols = ["issue_date", "vessel_name", "vessel_type", "imo", "year_built", "country_built", "ldt", "sale_terms", "delivery_location", "price_usd_ldt", "price_status", "comments", "source_file"]
    for path in [v_csv, v_mirror]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=v_cols)
            writer.writeheader()
            writer.writerows(all_vessels)
    print(f"Saved Demolition Deals: {len(all_vessels)} rows -> {v_csv.name}")

    # 3. Market Commentary Series
    c_csv = SERIES_DIR / "best_oasis_market_commentary_series.csv"
    c_cols = ["issue_date", "section", "headline", "commentary", "source_file"]
    with open(c_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=c_cols)
        writer.writeheader()
        writer.writerows(all_commentary)
    print(f"Saved Market Commentary: {len(all_commentary)} rows -> {c_csv.name}")

    # 4. Macro & Currencies Series
    m_csv = SERIES_DIR / "best_oasis_exchange_rates_series.csv"
    m_cols = ["issue_date", "usd_inr", "usd_bdt", "usd_pkr", "usd_try", "brent_crude_usd", "wti_crude_usd", "source_file"]
    with open(m_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=m_cols)
        writer.writeheader()
        writer.writerows(all_macro)
    print(f"Saved Macro Indicators: {len(all_macro)} rows -> {m_csv.name}")

    print("=" * 70)
    print(f"COMPLETE: {success_count} succeeded, {fail_count} failed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
