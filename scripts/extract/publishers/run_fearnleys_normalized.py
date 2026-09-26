#!/usr/bin/env python3
"""
run_fearnleys_normalized.py
Comprehensive multi-era normalization and structured extraction pipeline
for Fearnleys Weekly Market Reports (2018-2026).

Pillars matching Fearnleys Pulse:
  01 Tankers: Commentary (VLCC, Suezmax, Aframax, Regional) + Spot Dirty Rates + 1Y TC & Fleet Availability
  02 Dry Bulk: Commentary (Capesize, Panamax, Supramax, Handysize) + Spot Rates & BDI + 1Y TC Rates
  03 Gas: Commentary (LPG East/West, LNG) + LPG Spot & FOB Prices + LNG Spot & 1Y TC
  04 Newbuilding: Activity Sentiment Badges + Indicative Prices ($M)
  05 Sale & Purchase: Secondhand Prices ($M) for Dry (5Y, 10Y) & Wet (5Y, 10Y)
  06 Market Brief: Exchange Rates + Interest Rates + Commodity Prices (Brent) + Bunker Prices

Outputs:
  - data/extracted/md/fearnleys/<stem>.md (Beautiful 6-pillar structured markdown)
  - data/extracted/md/fearnleys/<stem>.tables.json (Standardized JSON sidecar)
  - data/extracted/series/fearnleys_rates_series.csv (Comprehensive master series)
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import pymupdf

ROOT = Path(r"c:\Users\Dell\Github\Shipping")
SRC_DIR = ROOT / "corpus" / "01-brokers" / "fearnleys"
MD_DIR = ROOT / "data" / "extracted" / "md" / "fearnleys"
SERIES_CSV = ROOT / "data" / "extracted" / "series" / "fearnleys_rates_series.csv"

MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

TABLE_KEYWORDS = [
    "1 Year T/C", "TCE Far East", "Fixed in all areas", "Available in MEG",
    "USD per Day", "Baltic Dry Index", "COASTER Europe", "LPG/FOB", "Sonatrach",
    "TCE Cont", "Australia/China", "Pacific RV", "Transatlantic RV", "US Gulf - China",
    "South China - Indonesia", "FOB North Sea", "Saudi Arabia/CP", "MT Belvieu",
    "East of Suez", "West of Suez", "Activity Levels", "Commodity Prices",
    "Bunker Prices", "Exchange Rates", "Interest Rates", "Spread MGO",
    "Dirty (Spot WS", "Spot WS", "Rotterdam", "Singapore"
]


def clean_encoding(text: str) -> str:
    """Normalize unicode quotes, dashes, ligatures, and strip PUA control characters."""
    if not text:
        return ""
    text = "".join(ch for ch in text if not (0xF000 <= ord(ch) <= 0xF8FF))
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\xa0", " ")
    # Replace typographic ligatures
    text = text.replace("\ufb00", "ff").replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb03", "ffi").replace("\ufb04", "ffl")
    text = re.sub(r"(\w)\ufffd(\w)", r"\1'\2", text)
    text = text.replace("\ufffd", " ")
    return text


def extract_date_and_week(pdf_path: Path, first_page_text: str) -> Tuple[str, int, int]:
    """Resolves ISO issue_date (YYYY-MM-DD), year (YYYY), and week number."""
    stem = pdf_path.stem

    # Pattern A: 10_09_2026_fearnleys_week_37_2026.pdf
    m_stem = re.search(r"(\d{2})_(\d{2})_(\d{4}).*?week_(\d+)", stem, re.IGNORECASE)
    if m_stem:
        d, m, y, w = m_stem.groups()
        return f"{y}-{m}-{d}", int(y), int(w)

    # Pattern B: fearnleys_YYYY_Www
    m_stem2 = re.search(r"fearnleys_(\d{4})_W(\d+)", stem, re.IGNORECASE)
    if m_stem2:
        y, w = m_stem2.groups()
        m_txt = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})", first_page_text, re.IGNORECASE)
        if m_txt:
            dt_str = m_txt.group(0).replace(",", "")
            try:
                dt = datetime.strptime(dt_str, "%B %d %Y")
                return dt.strftime("%Y-%m-%d"), int(y), int(w)
            except ValueError:
                pass
        return f"{y}-01-01", int(y), int(w)

    # Pattern C: Text scan on page 1
    m_txt = re.search(r"Week\s+(\d+)\s*[-–—]\s*([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", first_page_text, re.IGNORECASE)
    if m_txt:
        w, mon, day, y = m_txt.groups()
        mon_num = MONTH_MAP.get(mon.lower(), "01")
        return f"{y}-{mon_num}-{int(day):02d}", int(y), int(w)

    # Fallback to parent dir year
    try:
        parent_year = int(pdf_path.parent.name)
    except ValueError:
        parent_year = 2024
    return f"{parent_year}-01-01", parent_year, 1


def is_garbage_line(ln: str) -> bool:
    l = ln.strip()
    if not l:
        return True
    if re.search(r"https?://|@|about:blank|Printer version|Click rate|Weekly Report", l, re.I):
        return True
    if re.match(r"^\d+/\d+$|^\d{1,2}/\d{1,2}/\d{2,4}|^Week \d+|^© \d{4}|^Disclaimer|^An Astrup", l):
        return True
    if re.match(r"^(0[1-6]|[1-6])\s*$", l):
        return True
    if re.match(r"^(Rates|Prices|Activity Levels|Exchange Rates|Interest Rates|Commodity Prices|Bunker Prices)$", l, re.I):
        return True
    if re.match(r"^\(?USD/(?:Day|Tonne|Month)|^\(?Spot WS", l, re.I):
        return True
    if re.match(r"^[-+]?\$?[\d,]+(?:\.\d+)?%?$", l):
        return True
    if re.match(r"^\d+[\'’]?$", l):
        return True
    if "Chartering USD per Day" in l or "Jul '" in l or "Oct '" in l or "Nov '" in l:
        return True
    return False


def format_change(chg: Any) -> str:
    if chg is None or chg == "-":
        return "-"
    try:
        val = float(chg)
        if val > 0:
            return f"+{val:,.1f}" if val != int(val) else f"+{int(val):,}"
        elif val < 0:
            return f"{val:,.1f}" if val != int(val) else f"{int(val):,}"
        else:
            return "0.0"
    except (ValueError, TypeError):
        return str(chg)


def format_val(val: Any) -> str:
    try:
        v = float(val)
        return f"{v:,.1f}" if v != int(v) else f"{int(v):,}"
    except (ValueError, TypeError):
        return str(val)


def classify_subheading(section: str, text: str, fallback: str) -> str:
    t = text.lower()
    if section == "Tankers":
        if "north sea" in t[:70]:
            return "North Sea"
        if "mediterranean" in t[:70] or "bsea" in t[:70]:
            return "Mediterranean"
        if "vlcc" in t[:100] or "meg/west" in t:
            return "VLCC"
        if "suezmax" in t[:100] or "td20" in t:
            return "Suezmax"
        if "aframax" in t[:100]:
            return "Aframax"
    elif section == "Dry Bulk":
        if "capesize" in t[:100] or " c5" in t or " c3" in t:
            return "Capesize"
        if "panamax" in t[:100] or "kamsarmax" in t[:100]:
            return "Panamax"
        if "supramax" in t[:100] or "ultramax" in t[:100]:
            return "Supramax"
        if "handysize" in t[:100] or "handy " in t[:100]:
            return "Handysize"
    elif section == "Gas":
        if "lng" in t and "lpg" not in t:
            return "LNG"
        if "east" in t[:60] or "meg" in t[:60]:
            return "LPG East"
        if "west" in t[:60] or "usg" in t[:60]:
            return "LPG West"
        if "lpg" in t or "vlgc" in t:
            return "LPG"
    return fallback


def extract_clean_commentary(doc: pymupdf.Document) -> List[Tuple[str, str, str]]:
    """Extracts pure editorial narrative prose without chart labels or table fragments."""
    sections = {
        "Tankers": ["VLCC", "Suezmax", "Aframax", "NORTH SEA", "MEDITERRANEAN"],
        "Dry Bulk": ["Capesize", "Panamax", "Supramax", "Handysize"],
        "Gas": ["East", "West", "LPG", "LNG"]
    }

    current_sec = "Tankers"
    current_sub = "General"
    current_p_lines = []
    paragraphs = []

    # Commentary lives on pages 1 to 14
    max_pages = min(14, len(doc))
    for pno in range(max_pages):
        raw_text = clean_encoding(doc[pno].get_text("text"))
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        for ln in lines:
            if is_garbage_line(ln):
                continue

            # Check chapter transitions
            if ln in ["Tankers", "Dry Bulk", "Gas"]:
                if current_p_lines:
                    paragraphs.append((current_sec, current_sub, " ".join(current_p_lines)))
                    current_p_lines = []
                current_sec = ln
                current_sub = "General"
                continue

            # Check sub-headings
            is_sub = False
            if current_sec in sections:
                for sub in sections[current_sec]:
                    if ln.lower() == sub.lower():
                        if current_p_lines:
                            paragraphs.append((current_sec, current_sub, " ".join(current_p_lines)))
                            current_p_lines = []
                        current_sub = sub.title()
                        is_sub = True
                        break
            if is_sub:
                continue

            # Stop scanning if rate table encountered
            if any(k in ln for k in ["MEG/WEST", "TCE Cont/Far East", "VLGC", "1 Year T/C Crude", "1 Year T/C Dry Bulk"]):
                continue

            # Add prose line
            if len(ln.split()) >= 3 or (current_p_lines and ln.endswith(".")):
                current_p_lines.append(ln)
                if ln.endswith((".", '."', "!'", "?'")) and len(" ".join(current_p_lines)) > 120:
                    paragraphs.append((current_sec, current_sub, " ".join(current_p_lines)))
                    current_p_lines = []

    if current_p_lines and len(" ".join(current_p_lines)) > 40:
        paragraphs.append((current_sec, current_sub, " ".join(current_p_lines)))

    # Filter genuine prose paragraphs
    clean_paragraphs = []
    for sec, sub, text in paragraphs:
        t = text.strip()
        if len(t) < 80:
            continue
        if not t.endswith((".", '."', ".'", "?", "!")):
            continue
        if any(kw.lower() in t.lower() for kw in TABLE_KEYWORDS):
            continue
        # Strip emails and URLs just in case
        t = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", t).strip()
        t = re.sub(r"https?://[^\s]+", "", t).strip()
        refined_sub = classify_subheading(sec, t, sub)
        clean_paragraphs.append((sec, refined_sub, t))

    return clean_paragraphs


def extract_newbuilding_activity(doc: pymupdf.Document) -> Dict[str, str]:
    """Extracts qualitative activity sentiment levels (Slow, Moderate, Strong)."""
    activities = {}
    for pno in range(len(doc)):
        txt = doc[pno].get_text("text")
        for m in re.finditer(r"(Tank Activity|Dry Bulk Activity|LPG Activity|Container Activity|Other Activity)\s+(Slow|Moderate|Strong)", txt, re.I):
            sec_name = m.group(1).title()
            val = m.group(2).title()
            activities[sec_name] = val
    return activities


def extract_newbuilding_prices(doc: pymupdf.Document) -> Dict[str, Dict[str, Any]]:
    """Extracts Indicative Newbuilding Prices ($M) by vessel type."""
    nb_vessels = [
        ("VLCC", "300'"), ("Suezmax", "150'"), ("Aframax", "110'"), ("Product", "50'"),
        ("Newcastlemax", "210'"), ("Kamsarmax", "82'"), ("Ultramax", "64'"), ("LNGC (MEGI) (cbm)", "170'")
    ]
    nb_prices = {}
    in_nb_section = False

    for pno in range(len(doc)):
        txt = doc[pno].get_text("text")
        if ("04" in txt and "Newbuilding" in txt) or ("Activity Levels" in txt and "Prices" in txt):
            in_nb_section = True

        if in_nb_section:
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            for idx, line in enumerate(lines):
                for v, sz in nb_vessels:
                    if line.lower() == v.lower() or (v.startswith("LNGC") and "lngc" in line.lower()):
                        if v not in nb_prices:
                            for nxt in lines[idx+1:idx+4]:
                                pm = re.match(r"^\$?(\d+(?:\.\d+)?)$", nxt)
                                if pm:
                                    val = float(pm.group(1))
                                    if 20.0 <= val <= 350.0:
                                        nb_prices[v] = {"price_usd_m": val, "size": sz, "page": pno + 1}
                                        break
        if "05" in txt and "Sale & Purchase" in txt and pno > 10:
            in_nb_section = False

    return nb_prices


def extract_secondhand_prices(doc: pymupdf.Document) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """Extracts Secondhand Indicative Prices ($M) for 5 yr old and 10 yr old vessels."""
    sp_dry = {}
    sp_wet = {}

    for pno in range(len(doc)):
        txt = doc[pno].get_text("text")
        lines = [l.strip() for l in txt.splitlines() if l.strip()]

        # Format A (2024-2026): Block format with 5 yr old / 10 yr old side-by-side
        if "5 yr old" in txt:
            blocks = doc[pno].get_text("blocks")
            current_sector = "Dry"
            for b in blocks:
                b_text = b[4].strip()
                if "Wet" in b_text:
                    current_sector = "Wet"
                parts = [p.strip() for p in b_text.splitlines() if p.strip()]
                if len(parts) >= 3:
                    v_name = parts[0]
                    p1 = re.sub(r"[^\d.]", "", parts[1])
                    p2 = re.sub(r"[^\d.]", "", parts[2])
                    if p1 and p2:
                        try:
                            val1, val2 = float(p1), float(p2)
                            if 10.0 <= val1 <= 250.0 and 5.0 <= val2 <= 200.0:
                                if current_sector == "Dry" and v_name in ["Capesize", "Kamsarmax", "Ultramax", "Handysize"]:
                                    sp_dry[v_name] = {"5_yr": val1, "10_yr": val2, "page": pno + 1}
                                elif current_sector == "Wet" and any(k in v_name for k in ["VLCC", "Suezmax", "Aframax", "MR"]):
                                    clean_wet_name = "Aframax / LR2" if "Aframax" in v_name else v_name
                                    sp_wet[clean_wet_name] = {"5_yr": val1, "10_yr": val2, "page": pno + 1}
                        except ValueError:
                            pass

        # Format B (2021-2023): Sequential format 'Dry (5 yr)', 'Dry (10 yr)', 'Wet (5 yr)', 'Wet (10 yr)'
        elif "Dry (5 yr)" in txt or "Dry (5 yr old)" in txt:
            curr_tenor = None
            curr_sector = None
            for idx, line in enumerate(lines):
                if "Dry (5 yr" in line:
                    curr_sector = "Dry"
                    curr_tenor = "5_yr"
                elif "Dry (10 yr" in line:
                    curr_sector = "Dry"
                    curr_tenor = "10_yr"
                elif "Wet (5 yr" in line:
                    curr_sector = "Wet"
                    curr_tenor = "5_yr"
                elif "Wet (10 yr" in line:
                    curr_sector = "Wet"
                    curr_tenor = "10_yr"
                elif curr_sector and curr_tenor:
                    for v_target in ["Capesize", "Kamsarmax", "Ultramax", "Handysize", "VLCC", "Suezmax", "Aframax / LR2", "Aframax", "MR"]:
                        if line.lower() == v_target.lower():
                            if idx + 1 < len(lines):
                                p_str = re.sub(r"[^\d.]", "", lines[idx+1])
                                if p_str:
                                    try:
                                        p_val = float(p_str)
                                        if 5.0 <= p_val <= 250.0:
                                            target_dict = sp_dry if curr_sector == "Dry" else sp_wet
                                            clean_name = "Aframax / LR2" if "Aframax" in v_target else v_target
                                            target_dict.setdefault(clean_name, {})[curr_tenor] = p_val
                                            target_dict[clean_name]["page"] = pno + 1
                                    except ValueError:
                                        pass

    return sp_dry, sp_wet


def extract_rate_cards(doc: pymupdf.Document) -> List[Dict[str, Any]]:
    """Extracts rate cards and standard freight rates across the document."""
    extracted = []
    known_routes = [
        # Tankers Spot
        ("MEG/WEST", "Dirty Spot", "01 Tankers", "280'"),
        ("MEG/Japan", "Dirty Spot", "01 Tankers", "280'"),
        ("MEG/Singapore", "Dirty Spot", "01 Tankers", "280'"),
        ("WAF/FEAST", "Dirty Spot", "01 Tankers", "260'"),
        ("WAF/USAC", "Dirty Spot", "01 Tankers", "130'"),
        ("Sidi Kerir/W Med", "Dirty Spot", "01 Tankers", "135'"),
        ("N. Afr/Euromed", "Dirty Spot", "01 Tankers", "80'"),
        ("UK/Cont", "Dirty Spot", "01 Tankers", "80'"),
        ("Caribs/USG", "Dirty Spot", "01 Tankers", "70'"),
        # Tankers Period & Availability
        ("Fixed in all areas last week", "Period & Availability", "01 Tankers", "-"),
        ("Available in MEG next 30 days", "Period & Availability", "01 Tankers", "-"),
        ("1 Year T/C - ECO / SCRUBBER", "Period & Availability", "01 Tankers", "Modern"),
        # Dry Bulk Spot & Indices
        ("Baltic Dry Index (BDI)", "Dry Spot", "02 Dry Bulk", "Index"),
        ("TCE Cont/Far East", "Dry Spot", "02 Dry Bulk", "Capesize"),
        ("Australia/China", "Dry Spot", "02 Dry Bulk", "Capesize"),
        ("Pacific RV", "Dry Spot", "02 Dry Bulk", "Capesize"),
        ("Transatlantic RV", "Dry Spot", "02 Dry Bulk", "Panamax"),
        ("TCE Far East/Cont", "Dry Spot", "02 Dry Bulk", "Panamax"),
        ("TCE Far East RV", "Dry Spot", "02 Dry Bulk", "Panamax"),
        ("US Gulf - China/South Japan", "Dry Spot", "02 Dry Bulk", "Supramax"),
        ("South China - Indonesia RV", "Dry Spot", "02 Dry Bulk", "Supramax"),
        # Dry Bulk 1Y TC
        ("Newcastlemax", "Dry 1Y TC", "02 Dry Bulk", "208'"),
        ("Capesize", "Dry 1Y TC", "02 Dry Bulk", "180'"),
        ("Kamsarmax", "Dry 1Y TC", "02 Dry Bulk", "82'"),
        ("Panamax", "Dry 1Y TC", "02 Dry Bulk", "75'"),
        ("Ultramax", "Dry 1Y TC", "02 Dry Bulk", "64'"),
        ("Supramax", "Dry 1Y TC", "02 Dry Bulk", "58'"),
        ("Handysize", "Dry 1Y TC", "02 Dry Bulk", "38'"),
        # Gas LPG
        ("VLGC", "LPG Spot", "03 Gas", "84'"),
        ("LGC", "LPG Spot", "03 Gas", "60'"),
        ("MGC", "LPG Spot", "03 Gas", "38'"),
        ("COASTER Europe", "LPG Spot", "03 Gas", "3 500-5 000 cbm"),
        ("FOB North Sea/Ansi", "LPG FOB", "03 Gas", "Propane/Butane"),
        ("Saudi Arabia/CP", "LPG FOB", "03 Gas", "Propane/Butane"),
        ("MT Belvieu", "LPG FOB", "03 Gas", "Propane/Butane"),
        ("Sonatrach/Bethioua", "LPG FOB", "03 Gas", "Propane/Butane"),
        # Gas LNG
        ("East of Suez 155-165k CBM", "LNG", "03 Gas", "155-165k CBM"),
        ("West of Suez 155-165k CBM", "LNG", "03 Gas", "155-165k CBM"),
        ("1 Year T/C 155-165k TFDE", "LNG", "03 Gas", "155-165k TFDE"),
        # Market Brief
        ("USD/JPY", "Exchange Rates", "06 Market Brief", "FX"),
        ("USD/NOK", "Exchange Rates", "06 Market Brief", "FX"),
        ("USD/KRW", "Exchange Rates", "06 Market Brief", "FX"),
        ("EUR/USD", "Exchange Rates", "06 Market Brief", "FX"),
        ("SOFR USD", "Interest Rates", "06 Market Brief", "Rate"),
        ("LIBOR USD", "Interest Rates", "06 Market Brief", "Rate"),
        ("Brent Spot", "Commodity Prices", "06 Market Brief", "Spot"),
        ("380 CST", "Bunker Prices", "06 Market Brief", "Fuel Oil"),
        ("MGO", "Bunker Prices", "06 Market Brief", "Gasoil"),
        ("Spread MGO/380 CST", "Bunker Prices", "06 Market Brief", "Spread"),
    ]

    YEARS = {"2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"}

    # Track chapter boundaries by page
    page_chapters = {}
    current_ch = "01 Tankers"
    for pno in range(len(doc)):
        ptxt = doc[pno].get_text("text")
        if re.search(r"^(?:02|2)\s*\n\s*Dry Bulk", ptxt, re.M) or (len(doc) <= 10 and pno >= 2 and "Dry Bulk" in ptxt):
            current_ch = "02 Dry Bulk"
        elif re.search(r"^(?:03|3)\s*\n\s*Gas", ptxt, re.M) or (len(doc) <= 10 and pno >= 3 and "Gas" in ptxt and "LPG" in ptxt):
            current_ch = "03 Gas"
        elif re.search(r"^(?:04|4)\s*\n\s*Newbuilding", ptxt, re.M) or (len(doc) <= 10 and pno >= 4 and "Newbuilding" in ptxt):
            current_ch = "04 Newbuilding"
        elif re.search(r"^(?:05|5)\s*\n\s*Sale & Purchase", ptxt, re.M) or (len(doc) <= 10 and pno >= 5 and "Sale & Purchase" in ptxt):
            current_ch = "05 Sale & Purchase"
        elif re.search(r"^(?:06|6)\s*\n\s*Market Brief", ptxt, re.M) or (len(doc) <= 10 and pno >= 5 and ("Market Brief" in ptxt or "Commodity Prices" in ptxt)):
            current_ch = "06 Market Brief"
        page_chapters[pno] = current_ch

    for pno in range(len(doc)):
        # Skip disclaimer or trailing chart page
        raw_page_txt = doc[pno].get_text("text")
        if ("Disclaimer" in raw_page_txt and pno >= len(doc) - 2) or "USD per MT" in raw_page_txt:
            continue

        p_chapter = page_chapters.get(pno, "01 Tankers")
        txt = clean_encoding(raw_page_txt)
        lines = [l.strip() for l in txt.splitlines() if l.strip()]

        for i, ln in enumerate(lines):
            for route, sect, chapter, default_sz in known_routes:
                # Chapter affinity: only match if page chapter aligns
                if len(doc) > 5 and chapter != p_chapter:
                    continue

                # Section affinity:
                if sect == "Dry 1Y TC" and "1 Year T/C Dry Bulk" not in raw_page_txt:
                    continue
                if sect == "Dry Spot" and "1 Year T/C Dry Bulk" in raw_page_txt:
                    continue
                if sect == "Period & Availability" and "1 Year T/C" not in raw_page_txt and "Fixed in all areas" not in raw_page_txt:
                    continue

                if route.lower() in ln.lower():
                    val = None
                    chg = None
                    size = default_sz

                    for forward_ln in lines[i+1:min(len(lines), i+6)]:
                        # Skip if forward line is a year like 2025
                        if forward_ln.strip() in YEARS or re.match(r"^\d{4}$", forward_ln.strip()):
                            continue
                        # Skip if forward line is a chart axis tick like '24, '25
                        if re.search(r"'(?:21|22|23|24|25|26)", forward_ln):
                            continue

                        if re.search(r"[-+]?\$?[\d,]+(?:\.\d+)?%?", forward_ln):
                            m = re.search(r"[-+]?\$?[\d,]+(?:\.\d+)?", forward_ln)
                            if m:
                                num_str = m.group(0).replace("$", "").replace(",", "")
                                if num_str not in YEARS:
                                    try:
                                        num_val = float(num_str)
                                        if val is None:
                                            val = num_val
                                        elif chg is None and ("+" in forward_ln or "-" in forward_ln or forward_ln.strip() == "$0" or forward_ln.strip() == "0"):
                                            chg = num_val
                                    except ValueError:
                                        pass
                        if ("'" in forward_ln or "Modern" in forward_ln) and len(forward_ln) < 15:
                            size = forward_ln

                    if val is not None:
                        if not any(r["label"] == route and r["page"] == pno + 1 for r in extracted):
                            extracted.append({
                                "page": pno + 1,
                                "chapter": chapter,
                                "section": sect,
                                "label": route,
                                "value": val,
                                "change": chg if chg is not None else 0.0,
                                "vessel_size": size
                            })
                    break

    return extracted


def normalize_fearnleys():
    print("=================================================================", flush=True)
    print("  FEARNLEYS 6-PILLAR NORMALIZATION & RESTRUCTURE PIPELINE        ", flush=True)
    print("=================================================================", flush=True)

    all_pdfs = sorted(SRC_DIR.rglob("*.pdf"))
    print(f"Total Fearnleys PDFs to normalize: {len(all_pdfs)}", flush=True)

    MD_DIR.mkdir(parents=True, exist_ok=True)
    SERIES_CSV.parent.mkdir(parents=True, exist_ok=True)

    all_series_rows = []
    normalized_count = 0

    for idx, pdf in enumerate(all_pdfs, start=1):
        stem = pdf.stem
        rel_pdf = str(pdf.relative_to(ROOT)).replace("\\", "/")

        try:
            doc = pymupdf.open(pdf)
            page_count = len(doc)
            p1_text = clean_encoding(doc[0].get_text("text"))

            iso_date, year, week_num = extract_date_and_week(pdf, p1_text)

            # 1. Clean Commentary
            commentary = extract_clean_commentary(doc)

            # 2. Structured Rates
            rate_cards = extract_rate_cards(doc)

            # 3. Newbuilding Activity & Prices
            nb_activity = extract_newbuilding_activity(doc)
            nb_prices = extract_newbuilding_prices(doc)

            # 4. Sale & Purchase Secondhand Prices (5Y & 10Y)
            sp_dry, sp_wet = extract_secondhand_prices(doc)

            # Build Series Rows
            stamped_rows = []

            # Add standard rates
            for r in rate_cards:
                row_copy = dict(r)
                row_copy["issue_date"] = iso_date
                row_copy["year"] = year
                row_copy["report_week"] = week_num
                row_copy["source_file"] = rel_pdf
                stamped_rows.append(row_copy)
                all_series_rows.append({
                    "issue_date": iso_date,
                    "report_week": week_num,
                    "page": r["page"],
                    "chapter": r["chapter"],
                    "section": r["section"],
                    "label": r["label"],
                    "value": r["value"],
                    "size": r["vessel_size"],
                    "change": r.get("change", ""),
                    "source_file": rel_pdf
                })

            # Add Newbuilding Prices to Series
            for v_name, nb_info in nb_prices.items():
                p_val = nb_info["price_usd_m"]
                sz = nb_info["size"]
                p_no = nb_info.get("page", 15)
                all_series_rows.append({
                    "issue_date": iso_date,
                    "report_week": week_num,
                    "page": p_no,
                    "chapter": "04 Newbuilding",
                    "section": "Newbuilding Prices",
                    "label": f"{v_name} ({sz})",
                    "value": p_val,
                    "size": sz,
                    "change": 0.0,
                    "source_file": rel_pdf
                })

            # Add S&P Dry & Wet to Series
            for v_name, d_info in sp_dry.items():
                p_no = d_info.get("page", 16)
                if "5_yr" in d_info:
                    all_series_rows.append({
                        "issue_date": iso_date,
                        "report_week": week_num,
                        "page": p_no,
                        "chapter": "05 Sale & Purchase",
                        "section": "Secondhand Prices (5Y)",
                        "label": f"{v_name} (5Y)",
                        "value": d_info["5_yr"],
                        "size": "Dry Bulk",
                        "change": "",
                        "source_file": rel_pdf
                    })
                if "10_yr" in d_info:
                    all_series_rows.append({
                        "issue_date": iso_date,
                        "report_week": week_num,
                        "page": p_no,
                        "chapter": "05 Sale & Purchase",
                        "section": "Secondhand Prices (10Y)",
                        "label": f"{v_name} (10Y)",
                        "value": d_info["10_yr"],
                        "size": "Dry Bulk",
                        "change": "",
                        "source_file": rel_pdf
                    })

            for v_name, w_info in sp_wet.items():
                p_no = w_info.get("page", 16)
                if "5_yr" in w_info:
                    all_series_rows.append({
                        "issue_date": iso_date,
                        "report_week": week_num,
                        "page": p_no,
                        "chapter": "05 Sale & Purchase",
                        "section": "Secondhand Prices (5Y)",
                        "label": f"{v_name} (5Y)",
                        "value": w_info["5_yr"],
                        "size": "Wet Tanker",
                        "change": "",
                        "source_file": rel_pdf
                    })
                if "10_yr" in w_info:
                    all_series_rows.append({
                        "issue_date": iso_date,
                        "report_week": week_num,
                        "page": p_no,
                        "chapter": "05 Sale & Purchase",
                        "section": "Secondhand Prices (10Y)",
                        "label": f"{v_name} (10Y)",
                        "value": w_info["10_yr"],
                        "size": "Wet Tanker",
                        "change": "",
                        "source_file": rel_pdf
                    })

            # Assemble Beautiful 6-Pillar Markdown
            md_lines = [
                "---",
                f'title: "Fearnleys Weekly Report - Week {week_num}, {year}"',
                f'issue_date: "{iso_date}"',
                f"year: {year}",
                f"report_week: {week_num}",
                'publisher: "Fearnleys"',
                'category: "market_report"',
                f"pages: {page_count}",
                f'source_file: "{rel_pdf}"',
                "---",
                "",
                f"# Fearnleys Weekly Market Report (Week {week_num}, {year})",
                "",
                f"**Issue Date:** {iso_date} | **Pages:** {page_count} | **Publisher:** Fearnleys AS  ",
                f"**Source Document:** `{rel_pdf}`  ",
                "",
                "---",
                ""
            ]

            # -------------------------------------------------------------
            # Pillar 01: Tankers
            # -------------------------------------------------------------
            md_lines.append("## 01 Tankers\n")
            tanker_comm = [p for p in commentary if p[0] == "Tankers"]
            if tanker_comm:
                md_lines.append("### Market Commentary\n")
                grouped_tanker = {}
                for _, sub, text in tanker_comm:
                    grouped_tanker.setdefault(sub, []).append(text)
                for sub, plist in grouped_tanker.items():
                    if sub != "General":
                        md_lines.append(f"#### {sub}\n")
                    for p in plist:
                        md_lines.append(f"{p}\n")

            # Tankers Spot Rates
            tanker_spot = [r for r in rate_cards if r["chapter"] == "01 Tankers" and r["section"] == "Dirty Spot"]
            if tanker_spot:
                md_lines.extend([
                    "### Dirty Spot Freight Rates",
                    "",
                    "| Route | Vessel Size | Current (WS) | Change |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in tanker_spot:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            # Tankers Period & Availability
            tanker_period = [r for r in rate_cards if r["chapter"] == "01 Tankers" and r["section"] == "Period & Availability"]
            if tanker_period:
                md_lines.extend([
                    "### Period Rates & Fleet Availability",
                    "",
                    "| Metric / Vessel Class | Vessel Size | Current | Change |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in tanker_period:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            md_lines.append("---\n")

            # -------------------------------------------------------------
            # Pillar 02: Dry Bulk
            # -------------------------------------------------------------
            md_lines.append("## 02 Dry Bulk\n")
            dry_comm = [p for p in commentary if p[0] == "Dry Bulk"]
            if dry_comm:
                md_lines.append("### Market Commentary\n")
                grouped_dry = {}
                for _, sub, text in dry_comm:
                    grouped_dry.setdefault(sub, []).append(text)
                for sub, plist in grouped_dry.items():
                    if sub != "General":
                        md_lines.append(f"#### {sub}\n")
                    for p in plist:
                        md_lines.append(f"{p}\n")

            # Dry Bulk Spot Rates
            dry_spot = [r for r in rate_cards if r["chapter"] == "02 Dry Bulk" and r["section"] == "Dry Spot"]
            if dry_spot:
                md_lines.extend([
                    "### Spot Freight Rates & Indices",
                    "",
                    "| Route / Benchmark | Vessel Size / Type | Current | Change |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in dry_spot:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            # Dry Bulk 1Y TC
            dry_tc = [r for r in rate_cards if r["chapter"] == "02 Dry Bulk" and r["section"] == "Dry 1Y TC"]
            if dry_tc:
                md_lines.extend([
                    "### 1 Year T/C Rates",
                    "",
                    "| Vessel Class | DWT | Current ($/day) | Change ($/day) |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in dry_tc:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            md_lines.append("---\n")

            # -------------------------------------------------------------
            # Pillar 03: Gas
            # -------------------------------------------------------------
            md_lines.append("## 03 Gas\n")
            gas_comm = [p for p in commentary if p[0] == "Gas"]
            if gas_comm:
                md_lines.append("### Market Commentary\n")
                grouped_gas = {}
                for _, sub, text in gas_comm:
                    grouped_gas.setdefault(sub, []).append(text)
                for sub, plist in grouped_gas.items():
                    if sub != "General":
                        md_lines.append(f"#### {sub}\n")
                    for p in plist:
                        md_lines.append(f"{p}\n")

            # LPG Rates
            lpg_rates = [r for r in rate_cards if r["chapter"] == "03 Gas" and r["section"] in ["LPG Spot", "LPG FOB"]]
            if lpg_rates:
                md_lines.extend([
                    "### LPG Rates & FOB Prices",
                    "",
                    "| Benchmark / Route | Vessel / Cargo | Current | Change |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in lpg_rates:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            # LNG Rates
            lng_rates = [r for r in rate_cards if r["chapter"] == "03 Gas" and r["section"] == "LNG"]
            if lng_rates:
                md_lines.extend([
                    "### LNG Rates",
                    "",
                    "| Route / Tenor | Vessel / Cargo | Current | Change |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for r in lng_rates:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            md_lines.append("---\n")

            # -------------------------------------------------------------
            # Pillar 04: Newbuilding
            # -------------------------------------------------------------
            md_lines.append("## 04 Newbuilding\n")
            if nb_activity:
                md_lines.extend([
                    "### Activity Levels",
                    "",
                    "| Sector | Activity Status |",
                    "| :--- | :---: |"
                ])
                for s_act, status in nb_activity.items():
                    md_lines.append(f"| {s_act} | {status} |")
                md_lines.append("")

            if nb_prices:
                md_lines.extend([
                    "### Indicative Newbuilding Prices ($M)",
                    "",
                    "| Vessel Type | Size | Current ($M) | Change ($M) |",
                    "| :--- | :---: | :---: | :---: |"
                ])
                for v_name, nb_item in nb_prices.items():
                    md_lines.append(f"| {v_name} | {nb_item['size']} | ${nb_item['price_usd_m']:.1f} | $0.0 |")
                md_lines.append("")

            md_lines.append("---\n")

            # -------------------------------------------------------------
            # Pillar 05: Sale & Purchase
            # -------------------------------------------------------------
            md_lines.append("## 05 Sale & Purchase\n")
            if sp_dry or sp_wet:
                md_lines.append("### Indicative Secondhand Prices ($M)\n")
                if sp_dry:
                    md_lines.extend([
                        "#### Dry Bulk",
                        "",
                        "| Vessel Class | 5 Year Old ($M) | 10 Year Old ($M) |",
                        "| :--- | :---: | :---: |"
                    ])
                    for v_name, d_item in sp_dry.items():
                        p5 = f"${d_item['5_yr']:.1f}" if "5_yr" in d_item else "-"
                        p10 = f"${d_item['10_yr']:.1f}" if "10_yr" in d_item else "-"
                        md_lines.append(f"| {v_name} | {p5} | {p10} |")
                    md_lines.append("")

                if sp_wet:
                    md_lines.extend([
                        "#### Tankers (Wet)",
                        "",
                        "| Vessel Class | 5 Year Old ($M) | 10 Year Old ($M) |",
                        "| :--- | :---: | :---: |"
                    ])
                    for v_name, w_item in sp_wet.items():
                        p5 = f"${w_item['5_yr']:.1f}" if "5_yr" in w_item else "-"
                        p10 = f"${w_item['10_yr']:.1f}" if "10_yr" in w_item else "-"
                        md_lines.append(f"| {v_name} | {p5} | {p10} |")
                    md_lines.append("")

            md_lines.append("---\n")

            # -------------------------------------------------------------
            # Pillar 06: Market Brief
            # -------------------------------------------------------------
            md_lines.append("## 06 Market Brief\n")
            fx_rates = [r for r in rate_cards if r["chapter"] == "06 Market Brief" and r["section"] in ["Exchange Rates", "Interest Rates"]]
            if fx_rates:
                md_lines.extend([
                    "### Exchange Rates & Interest Rates",
                    "",
                    "| Indicator | Category | Rate | Change |",
                    "| :--- | :--- | :---: | :---: |"
                ])
                for r in fx_rates:
                    md_lines.append(f"| {r['label']} | {r['section']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            bunkers = [r for r in rate_cards if r["chapter"] == "06 Market Brief" and r["section"] in ["Commodity Prices", "Bunker Prices"]]
            if bunkers:
                md_lines.extend([
                    "### Commodity Prices & Bunkers",
                    "",
                    "| Benchmark | Location / Grade | Price | Change |",
                    "| :--- | :--- | :---: | :---: |"
                ])
                for r in bunkers:
                    md_lines.append(f"| {r['label']} | {r['vessel_size']} | {format_val(r['value'])} | {format_change(r.get('change'))} |")
                md_lines.append("")

            # Write Normalized Markdown
            md_out_path = MD_DIR / f"{stem}.md"
            md_out_path.write_text("\n".join(md_lines), encoding="utf-8")

            # Write Sidecar JSON
            sidecar_payload = {
                "convention": "iso",
                "publisher": "Fearnleys",
                "issue_date": iso_date,
                "year": year,
                "report_week": week_num,
                "pages": page_count,
                "source_file": rel_pdf,
                "activity_levels": nb_activity,
                "newbuilding_prices": nb_prices,
                "secondhand_prices": {
                    "dry": sp_dry,
                    "wet": sp_wet
                },
                "rates": stamped_rows
            }
            sidecar_out_path = MD_DIR / f"{stem}.tables.json"
            sidecar_out_path.write_text(json.dumps(sidecar_payload, indent=2, ensure_ascii=False), encoding="utf-8")

            normalized_count += 1
            if idx % 25 == 0 or idx == len(all_pdfs):
                print(f"Normalized {idx}/{len(all_pdfs)} files ({idx*100//len(all_pdfs)}%) - Series rows: {len(all_series_rows):,}", flush=True)

        except Exception as e:
            print(f"Error processing {pdf.name}: {e}", flush=True)

    # Write Master Stacked Series CSV
    if all_series_rows:
        fieldnames = [
            "issue_date", "report_week", "page", "chapter", "section",
            "label", "value", "size", "change", "source_file"
        ]
        with open(SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for r in all_series_rows:
                writer.writerow(r)

    print("\n=================================================================", flush=True)
    print(f"Successfully normalized {normalized_count} Fearnleys files.", flush=True)
    print(f"Generated {SERIES_CSV} with {len(all_series_rows):,} total rows.", flush=True)
    print("=================================================================\n", flush=True)


if __name__ == "__main__":
    normalize_fearnleys()
