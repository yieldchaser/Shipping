"""
Intermodal Weekly Market Reports - High-Fidelity Normalizer & Polisher.

Comprehensive, zero-defect normalizer for extracted Intermodal weekly reports:
1. Strips all accidental strikethroughs (~~) from negative numbers, diffs, and colored sentiment words.
2. Strips all running footers (www.intermodal.gr, page numbers, trailing address blocks).
3. Converts raw '--- PAGE BREAK ---' markers into clean Markdown dividers.
4. Enforces page boundary limits per Shipbroking_Source_Parsing_Notes.docx:
   - 2024-2026 reports: Excludes the final 2 pages (Commodities & Ship Finance, Market Data, Bunkers, Stocks).
   - 2021-2023 reports: Excludes the final page (Contacts / Directory).
5. Fixes table column alignment & multi-level headers:
   - Tanker Spot Rates: Splits Size and Routes into explicit columns, aligns 10 columns perfectly.
   - Indicative Newbuilding Prices: Combines multi-level YTD and 5-year High/Low headers into 13 explicit columns.
   - TC Rates: Aligns Sector and Tenor into explicit columns, strips unit label $/day from headers.
   - Indicative Market Values: Aligns Sector and Size into explicit columns.
   - Baltic Indices: Combines spanning dates with sub-headers (Index / $/day) and preserves legitimate BDI blank cells.
   - Indicative Demolition Prices: Combines YTD High/Low spanning headers.
6. Strips repeated column prefixes (e.g. 'Containers<br/>', 'Newbuilding Orders<br/>').
7. Replaces internal <br/> tags in headers and cells with clean spaces.
8. Converts raw HTML <table> blocks into clean GitHub-flavored markdown tables.
9. Synchronizes older year averages from tables.json to eliminate any historical omissions.
"""

from __future__ import annotations

import glob
import json
import os
import pathlib
import re
from typing import List, Tuple

from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "data" / "extracted" / "llamaparse_intermodal_full"
MD_DIR = ROOT / "data" / "extracted" / "md" / "intermodal"


def convert_html_table(soup_tbl) -> str:
    """Converts an HTML <table> element into a cleanly formatted Markdown table."""
    thead = soup_tbl.find("thead")
    tbody = soup_tbl.find("tbody")

    th_rows = []
    if thead:
        for tr in thead.find_all("tr"):
            th_rows.append([" ".join(c.get_text().split()).strip() for c in tr.find_all(["th", "td"])])

    tb_rows = []
    if tbody:
        for tr in tbody.find_all("tr"):
            tb_rows.append([" ".join(c.get_text().split()).strip() for c in tr.find_all(["th", "td"])])
    else:
        for tr in soup_tbl.find_all("tr"):
            tb_rows.append([" ".join(c.get_text().split()).strip() for c in tr.find_all(["th", "td"])])
        if tb_rows and not th_rows:
            th_rows = [tb_rows[0]]
            tb_rows = tb_rows[1:]

    tb_rows = [r for r in tb_rows if any(r)]

    if not tb_rows and not th_rows:
        return ""

    # TC rates table
    if tb_rows and len(tb_rows[0]) >= 6 and any("TC" in r[1].upper() for r in tb_rows[:3] if len(r) > 1):
        all_th = [c for r in th_rows for c in r if c and c != "$/day"]
        dates = [c for c in all_th if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", c)]
        years = [c for c in all_th if re.search(r"20\d\d", c)]
        hdr = ["Sector", "Tenor"] + dates + ["±%", "Diff"] + years
        n_cols = len(tb_rows[0])
        lines = ["| " + " | ".join(hdr[:n_cols]) + " |", "| " + " | ".join(["---"] * n_cols) + " |"]
        for r in tb_rows:
            padded = r + [""] * (n_cols - len(r))
            lines.append("| " + " | ".join(padded[:n_cols]) + " |")
        return "\n".join(lines)

    # Indicative Market Values
    if tb_rows and len(tb_rows[0]) >= 5 and any(("DH" in r[1].upper() or "K" in r[1].upper() or "ECO" in r[1].upper()) for r in tb_rows[:3] if len(r) > 1):
        all_th = [c for r in th_rows for c in r if c and not any(s in c.lower() for s in ["million", "vessel", "size"])]
        hdr = ["Sector", "Size"] + all_th
        n_cols = len(tb_rows[0])
        lines = ["| " + " | ".join(hdr[:n_cols]) + " |", "| " + " | ".join(["---"] * n_cols) + " |"]
        for r in tb_rows:
            padded = r + [""] * (n_cols - len(r))
            lines.append("| " + " | ".join(padded[:n_cols]) + " |")
        return "\n".join(lines)

    # Indicative Demolition Prices
    if tb_rows and any("BANGLADESH" in r[0].upper() for r in tb_rows if len(r) > 0):
        all_th = [c for r in th_rows for c in r if c and not any(s in c.lower() for s in ["indicative", "prices", "$/ldt"])]
        hdr = ["Markets"] + all_th
        n_cols = len(tb_rows[0])
        lines = ["| " + " | ".join(hdr[:n_cols]) + " |", "| " + " | ".join(["---"] * n_cols) + " |"]
        for r in tb_rows:
            padded = r + [""] * (n_cols - len(r))
            lines.append("| " + " | ".join(padded[:n_cols]) + " |")
        return "\n".join(lines)

    # Generic conversion
    all_rows = th_rows + tb_rows
    max_cols = max(len(r) for r in all_rows)
    padded = [r + [""] * (max_cols - len(r)) for r in all_rows]
    lines = ["| " + " | ".join(padded[0]) + " |", "| " + " | ".join(["---"] * max_cols) + " |"]
    for r in padded[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def replace_html_tables(text: str) -> str:
    """Finds all HTML <table> tags and replaces them with clean Markdown tables."""
    if "<table" not in text:
        return text
    soup = BeautifulSoup(text, "html.parser")
    for tbl in soup.find_all("table"):
        md_tbl = convert_html_table(tbl)
        tbl.replace_with(f"\n\n{md_tbl}\n\n")
    return str(soup)


def strip_strikethrough(text: str) -> str:
    """Removes all strikethrough (~~) tags across the document."""
    return re.sub(r"~~([^~]+)~~", r"\1", text)


def clean_boilerplate_and_bounds(text: str, year: int) -> str:
    """Strips boilerplate headers, footers, and enforces parsing notes page boundaries."""
    # Page boundary truncation per Shipbroking_Source_Parsing_Notes.docx Paragraph 31:
    # Latest years: exclude last 2 pages (Commodities & Ship Finance, Market Data, Bunkers, Stocks, Contacts)
    # Earlier years: exclude last page (Commodities & Ship Finance / Contacts / Directory)
    m = re.search(
        r"\n+(?:---\s*(?:PAGE\s*BREAK|-{3,})\s*---\s*\n+)?(?:#+\s*Intermodal\s*\n+)?#*\s*(?:Commodities\s*(?:&|&amp;|and)\s*Ship\s*Finance|Market\s*Data|Bunker\s*Prices|Maritime\s*Stock\s*Data|Contact\s+Directory|Directory|Intermodal\s+Shipbrokers\s+Head\s+Office)",
        text,
        re.I,
    )
    if m:
        text = text[: m.start()]

    # Also strip trailing address block if present
    m_addr = re.search(r"\n\|?\s*ATHENS\s*\|?\s*17th\s*Km", text, re.I)
    if m_addr:
        text = text[: m_addr.start()]

    lines = text.splitlines()
    cleaned = []

    addr_patterns = [
        re.compile(r"intermodal\.gr", re.I),
        re.compile(r"^\s*#*\s*\*?\*?Intermodal\*?\*?\s*$", re.I),
        re.compile(r"^\s*Page\s+\d+\s*$", re.I),
        re.compile(r"^\s*\d{1,2}\s*$"),
        re.compile(r"17th\s+Km\s+Ethniki", re.I),
        re.compile(r"ATHENS.*TEL:", re.I),
        re.compile(r"SHIPPING\s+365", re.I),
    ]

    for line in lines:
        stripped = line.strip()
        if any(p.search(stripped) for p in addr_patterns):
            continue
        cleaned.append(line)

    res = "\n".join(cleaned)
    res = re.sub(r"\n*--- PAGE BREAK ---\n*", "\n\n---\n\n", res)
    return res


def clean_table(table_lines: List[str]) -> str:
    """Transforms and aligns a raw Markdown table block."""
    parsed = []
    for l in table_lines:
        cells = [c.strip() for c in l.strip()[1:-1].split("|")]
        parsed.append(cells)

    if len(parsed) < 2:
        return "\n".join(table_lines)

    r0 = parsed[0]
    r1 = parsed[1]
    data_rows = parsed[2:]

    # Clean <br/> and repeated prefixes in headers
    cleaned_r0 = []
    for c in r0:
        c_clean = re.sub(r"<br/?>", " ", c).strip()
        c_clean = re.sub(
            r"^(?:Containers|Newbuilding Orders|Indicative Demolition Prices(?:\s*\([^\)]+\))?|Indicative Newbuilding Prices(?:\s*\([^\)]+\))?|Indicative Market Values(?:\s*\([^\)]+\))?(?:\s*-\s*\w+)?)\s+",
            "",
            c_clean,
            flags=re.I,
        ).strip()
        cleaned_r0.append(c_clean)
    r0 = cleaned_r0

    # Strip empty leading/trailing columns across all rows if present
    while len(r0) > 3 and not r0[0] and all(not r[0] for r in data_rows if any(r)):
        r0 = r0[1:]
        data_rows = [r[1:] for r in data_rows if any(r)]
    while len(r0) > 3 and not r0[-1] and all(not r[-1] for r in data_rows if any(r)):
        r0 = r0[:-1]
        data_rows = [r[:-1] for r in data_rows if any(r)]

    r0_str = " ".join(r0).upper()
    data_str = " ".join(" ".join(r) for r in data_rows[:3]).upper()

    route_pat = re.compile(r"^\*?\*?(\d+\s*[kK])\*?\*?\s+(.+)$")
    tenor_pat = re.compile(r"\b(?:\d+\s*[kK]\s+)?(?:1|2|3|4|5)\s*(?:yr|year|mnt)\b|\b(?:6|12|24|36)\s*mos\b", re.I)

    # Case 0: Tanker Market Spot Rates Table
    if ("WS POINTS" in r0_str and "$/DAY" in r0_str) or (any("MEG-SPORE" in str(r).upper() for r in data_rows[:3])):
        dates = []
        for c in r0:
            m_d = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", c)
            if m_d and m_d.group(0) not in dates:
                dates.append(m_d.group(0))
        years = []
        for c in r0:
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in d for d in dates):
                years.append(m_y.group(0))

        d1 = dates[0] if len(dates) > 0 else "Current"
        d2 = dates[1] if len(dates) > 1 else "Previous"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"

        r0 = [
            "Sector",
            "Size",
            "Routes",
            f"{d1} WS points",
            f"{d1} $/day",
            f"{d2} WS points",
            f"{d2} $/day",
            "$/day ±%",
            f"{y1} $/day",
            f"{y2} $/day",
        ]

        fixed_data = []
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            sector, size, route, rest = "", "", "", []
            if len(r) >= 2 and route_pat.match(re.sub(r"\*+", "", r[1]).strip()):
                sector = r[0]
                m = route_pat.match(re.sub(r"\*+", "", r[1]).strip())
                size, route = m.group(1).strip(), m.group(2).strip()
                rest = r[2:]
            elif len(r) >= 1 and route_pat.match(re.sub(r"\*+", "", r[0]).strip()):
                m = route_pat.match(re.sub(r"\*+", "", r[0]).strip())
                size, route = m.group(1).strip(), m.group(2).strip()
                rest = r[1:]
            elif len(r) >= 3 and re.match(r"^\*?\*?\d+\s*[kK]\*?\*?$", r[1]):
                sector, size, route = r[0], r[1], r[2]
                rest = r[3:]
            else:
                sector = r[0]
                rest = r[1:]
            new_r = [sector, size, route] + rest
            fixed_data.append(new_r)
        data_rows = fixed_data

    # Case A: Indicative Market Values (Tankers & Bulkers - 8 columns)
    elif ("5YRS OLD" in r0_str or "5YR OLD" in r0_str or ("VESSEL" in r0_str and any("DH" in str(r).upper() for r in data_rows[:3])) or any("300KT DH" in str(r).upper() for r in data_rows[:3])) and not ("NEWBUILDING" in r0_str or any("NEWCASTLEMAX" in str(r).upper() for r in data_rows[:3])):
        months = []
        for c in r0:
            m_m = re.search(r"[A-Za-z]{3}-\d{2,4}", c)
            if m_m and m_m.group(0) not in months:
                months.append(m_m.group(0))
        years = []
        for c in r0:
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in m for m in months):
                years.append(m_y.group(0))

        m1 = months[0] + " avg" if len(months) > 0 else "Current avg"
        m2 = months[1] + " avg" if len(months) > 1 else "Previous avg"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"
        y3 = years[2] if len(years) > 2 else "Year3"

        r0 = ["Sector", "Size", m1, m2, "±%", y1, y2, y3]
        fixed_data = []
        cur_sec = ""
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            if len(r) > 8 and r[0] == "":
                r = r[1:]
            if len(r) == 7:
                r = [cur_sec] + r
            elif len(r) >= 8 and r[0]:
                cur_sec = r[0]
            fixed_data.append(r)
        data_rows = fixed_data

    # Case B: TC Rates header alignment (Tankers & Bulkers - 8 columns)
    elif len(r0) >= 6 and (any(re.search(r"\b(?:1|2|3)\s*(?:yr|year)\b|\b(?:12|24|36)\s*mos\b", str(r).lower()) for r in data_rows[:5]) or any("TENOR" in c.upper() for c in r0)) and not ("WS POINTS" in r0_str or "TC1" in r0_str or "TD3" in r0_str):
        dates = []
        years = []
        for c in r0:
            m_d = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", c)
            if m_d and m_d.group(0) not in dates:
                dates.append(m_d.group(0))
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in d for d in dates):
                years.append(m_y.group(0))

        d1 = dates[0] if len(dates) > 0 else "Current"
        d2 = dates[1] if len(dates) > 1 else "Previous"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"

        r0 = ["Sector", "Tenor", d1, d2, "±%", "Diff", y1, y2]
        fixed_data = []
        cur_sec = ""
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            clean_cells = [c for c in r if c != ""]
            if len(clean_cells) == 1 and any(s in clean_cells[0].lower() for s in ["cape", "panamax", "supramax", "handy", "vlcc", "suezmax", "aframax"]):
                cur_sec = clean_cells[0]
                fixed_data.append([cur_sec] + [""] * 7)
                continue
            if len(r) == 7 and (tenor_pat.search(r[0]) or "tc" in r[0].lower()):
                r = [cur_sec] + r
            elif len(r) >= 8 and r[0]:
                cur_sec = r[0]
            fixed_data.append(r)
        data_rows = fixed_data

    # Case C: Indicative Newbuilding Prices
    elif ("NEWBUILDING" in r0_str or any("NEWCASTLEMAX" in str(r).upper() for r in data_rows[:3])) and not any(s in r0_str for s in ["DWT", "BUILT", "YARD", "BUYERS", "M/E", "SS DUE"]):
        has_ytd_5y = any("HIGH" in c.upper() or "YTD" in c.upper() or "5-YEAR" in c.upper() for c in r0) or (len(data_rows) > 0 and any("HIGH" in c.upper() for c in data_rows[0]))
        dates = []
        for c in r0:
            m_d = re.search(r"\d{1,2}[/-][A-Za-z]{3}[/-]\d{2,4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", c)
            if m_d and m_d.group(0) not in dates:
                dates.append(m_d.group(0))
        years = []
        for c in r0:
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in d for d in dates):
                years.append(m_y.group(0))
        d1 = dates[0] if len(dates) > 0 else "Current"
        d2 = dates[1] if len(dates) > 1 else "Previous"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"
        y3 = years[2] if len(years) > 2 else "Year3"

        if has_ytd_5y:
            r0 = ["Sector", "Vessel Class", "Size", d1, d2, "±%", "YTD High", "YTD Low", "5-year High", "5-year Low", y1, y2, y3]
            if len(data_rows) > 0 and any("HIGH" in c.upper() for c in data_rows[0]):
                data_rows = data_rows[1:]
            fixed_data = []
            cur_sec = ""
            for r in data_rows:
                while r and r[-1] == "":
                    r = r[:-1]
                if not r or not any(r):
                    continue
                clean_cells = [c for c in r if c != ""]
                if len(clean_cells) == 1 and any(s in clean_cells[0].lower() for s in ["bulker", "tanker", "gas"]):
                    cur_sec = clean_cells[0]
                    fixed_data.append([cur_sec] + [""] * 12)
                    continue
                if len(r) == 12:
                    r = [cur_sec] + r
                elif len(r) >= 13 and r[0]:
                    cur_sec = r[0]
                fixed_data.append(r)
            data_rows = fixed_data
        else:
            r0 = ["Sector", "Size", d1, d2, "±%", y1, y2, y3]
            fixed_data = []
            for r in data_rows:
                while r and r[-1] == "":
                    r = r[:-1]
                if any(r):
                    fixed_data.append(r)
            data_rows = fixed_data

    # Case D: Baltic Indices
    elif len(data_rows) > 0 and (any("BDI" in str(r) for r in data_rows[:3]) or (len(data_rows) > 0 and any("INDEX" in c.upper() for c in data_rows[0])) or (len(data_rows) > 1 and any("BCI" in str(r) for r in data_rows[1:3]))):
        d0 = data_rows[0]
        if any("INDEX" in c.upper() for c in d0) and any("$/DAY" in c.upper() for c in d0):
            new_hdr = ["Index Name"]
            cur_date = ""
            for c_top, c_sub in zip(r0[1:], d0[1:]):
                if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", c_top):
                    cur_date = c_top
                part = f"{cur_date} {c_sub}".strip() if cur_date and c_sub else (c_sub if c_sub else c_top)
                new_hdr.append(part)
            if len(new_hdr) == len(r0):
                r0 = new_hdr
                data_rows = data_rows[1:]
        elif r0[0] == "":
            r0[0] = "Index Name"

        # If first row starts with numeric value and second row is BCI, insert BDI
        for r in data_rows:
            if len(r) > 0 and re.match(r"^\d[\d,]+$", r[0]) and len(data_rows) > 1 and any("BCI" in row[0] for row in data_rows[1:3] if len(row) > 0):
                r.insert(0, "BDI")

    # Case E: Indicative Demolition Prices
    elif len(data_rows) > 0 and any("DEMOLITION" in c.upper() or "MARKET" in c.upper() for c in r0[:2]):
        d0 = data_rows[0]
        if "High" in d0 and "Low" in d0:
            new_hdr = []
            for c_top, c_sub in zip(r0, d0):
                if c_top == "YTD" and c_sub in ["High", "Low"]:
                    new_hdr.append(f"YTD {c_sub}")
                elif not c_top and c_sub in ["High", "Low"]:
                    new_hdr.append(f"YTD {c_sub}")
                else:
                    new_hdr.append(c_top if c_top else c_sub)
            if len(new_hdr) == len(r0):
                r0 = new_hdr
                data_rows = data_rows[1:]

    # Clean data cells: remove <br/> and pad to match header length
    clean_data = []
    for r in data_rows:
        if any(r):
            c_row = [re.sub(r"<br/?>", " ", cell).strip() for cell in r]
            padded = c_row + [""] * (len(r0) - len(c_row))
            clean_data.append(padded[:len(r0)])

    # Universal trailing empty column stripper
    while len(r0) > 3 and len(clean_data) > 0 and all(r[-1] == "" for r in clean_data):
        r0 = r0[:-1]
        clean_data = [r[:-1] for r in clean_data]

    res = []
    res.append("| " + " | ".join(r0) + " |")
    res.append("| " + " | ".join(["---"] * len(r0)) + " |")
    for r in clean_data:
        res.append("| " + " | ".join(r) + " |")

    return "\n".join(res)


def sync_tables_from_json(text: str, file_path: pathlib.Path) -> str:
    """Fills empty historical cells in markdown tables using ground-truth tables.json data."""
    json_path = file_path.with_name(file_path.stem + ".tables.json")
    if not json_path.exists():
        return text
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            tbl_data = json.load(f)
    except Exception:
        return text

    tables = tbl_data.get("tables", {})

    # TC rates map
    tc_records = tables.get("tc_rates", [])
    tc_map = {}
    for r in tc_records:
        k = re.sub(r"[^a-z0-9]", "", (r.get("vessel_class", "") + " " + r.get("tenor", "")).lower())
        tc_map[k] = (r.get("avg_prev_year_1"), r.get("avg_prev_year_2"))

    # Tanker spot map
    spot_records = tables.get("tanker_spot_rates", [])
    spot_map = {}
    for r in spot_records:
        k = re.sub(r"[^a-z0-9]", "", (r.get("vessel_class", "") + " " + r.get("route", "")).lower())
        spot_map[k] = (r.get("avg_prev_year_1"), r.get("avg_prev_year_2"))
        spot_map[re.sub(r"[^a-z0-9]", "", r.get("route", "").lower())] = (r.get("avg_prev_year_1"), r.get("avg_prev_year_2"))

    # Indicative market values map
    mv_records = tables.get("indicative_market_values", [])
    mv_map = {}
    for r in mv_records:
        k = re.sub(r"[^a-z0-9]", "", (r.get("sector", "") + " " + r.get("vessel_class", "")).lower())
        mv_map[k] = (r.get("avg_prev_year_1"), r.get("avg_prev_year_2"), r.get("avg_prev_year_3"))

    lines = text.splitlines()
    out = []
    cur_sec = ""
    for l in lines:
        if not l.strip().startswith("|"):
            out.append(l)
            continue
        cells = [c.strip() for c in l.strip()[1:-1].split("|")]
        if not cells:
            out.append(l)
            continue

        # TC rates table
        if any(t in l.lower() for t in ["1yr", "3yr", "1 yr", "3 yr", "6mnt"]):
            if cells[0]:
                cur_sec = cells[0]
            if len(cells) == 8:
                k = re.sub(r"[^a-z0-9]", "", (cur_sec + " " + cells[1]).lower())
                vals = tc_map.get(k)
                if vals:
                    y1, y2 = vals
                    if y1 and (cells[6] == "" or cells[6] == "0"):
                        cells[6] = f"{int(y1):,}" if isinstance(y1, (int, float)) else str(y1)
                    if y2 and (cells[7] == "" or cells[7] == "0"):
                        cells[7] = f"{int(y2):,}" if isinstance(y2, (int, float)) else str(y2)
                    l = "| " + " | ".join(cells) + " |"

        # Tanker spot table
        elif len(cells) == 10 and any(s in cells[2].upper() for s in ["MEG", "WAF", "MED", "BSEA", "USG", "UKC", "SPORE"]):
            route_k = re.sub(r"[^a-z0-9]", "", (cells[1] + " " + cells[2]).lower())
            vals = spot_map.get(route_k) or spot_map.get(re.sub(r"[^a-z0-9]", "", cells[2].lower()))
            if vals:
                y1, y2 = vals
                if y1 and (cells[8] == "" or cells[8] == "0"):
                    cells[8] = f"{int(y1):,}" if isinstance(y1, (int, float)) else str(y1)
                if y2 and (cells[9] == "" or cells[9] == "0"):
                    cells[9] = f"{int(y2):,}" if isinstance(y2, (int, float)) else str(y2)
                l = "| " + " | ".join(cells) + " |"

        # Indicative market values table
        elif len(cells) == 8 and (any("dh" in cells[1].lower() for _ in [1]) or any(s in cells[0].lower() for s in ["vlcc", "suezmax", "aframax", "capesize", "kamsarmax", "panamax", "ultramax", "handymax", "handysize"])):
            if cells[0]:
                cur_sec = cells[0]
            k = re.sub(r"[^a-z0-9]", "", (cur_sec + " " + cells[1]).lower())
            vals = mv_map.get(k)
            if vals:
                y1, y2, y3 = vals
                if y1 and (cells[5] == "" or cells[5] == "0"):
                    cells[5] = f"{y1:.1f}" if isinstance(y1, float) else str(y1)
                if y2 and (cells[6] == "" or cells[6] == "0"):
                    cells[6] = f"{y2:.1f}" if isinstance(y2, float) else str(y2)
                if y3 and (cells[7] == "" or cells[7] == "0"):
                    cells[7] = f"{y3:.1f}" if isinstance(y3, float) else str(y3)
                l = "| " + " | ".join(cells) + " |"

        out.append(l)
    return "\n".join(out)


def normalize_markdown(text: str, file_path: pathlib.Path) -> str:
    """Applies the full sequence of normalization rules to an Intermodal report."""
    m_yr = re.search(r"20(2[1-6])", file_path.name)
    year = int("20" + m_yr.group(1)) if m_yr else 2026

    # 1. Convert any HTML tables to markdown tables first
    t0 = replace_html_tables(text)

    # 2. Strip strikethroughs
    t1 = strip_strikethrough(t0)

    # 3. Clean boilerplate and enforce page bounds
    t2 = clean_boilerplate_and_bounds(t1, year)

    # 4. Clean tables
    lines = t2.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and i + 1 < len(lines) and any(s in lines[i + 1] for s in ["| ---", "|:---", "|---"]):
            table_lines = [line, lines[i + 1]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                table_lines.append(lines[j])
                j += 1
            cleaned_tbl = clean_table(table_lines)
            out.append(cleaned_tbl)
            out.append("")
            i = j
            continue
        out.append(line)
        i += 1

    res = "\n".join(out)
    res = re.sub(r"\n{3,}", "\n\n", res)
    res = sync_tables_from_json(res, file_path)
    return res.strip() + "\n"


def normalize_file(src_file: pathlib.Path, dest_file: pathlib.Path) -> bool:
    try:
        orig = src_file.read_text(encoding="utf-8", errors="replace")
        cleaned = normalize_markdown(orig, dest_file)
        dest_file.write_text(cleaned, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error normalizing {src_file.name}: {e}")
        return False


def main():
    src_files = sorted(SRC_DIR.glob("*.md"))
    print(f"Normalizing {len(src_files)} Intermodal Markdown files from pristine source...")
    updated_cnt = 0
    for f in src_files:
        dest = MD_DIR / f.name
        if normalize_file(f, dest):
            updated_cnt += 1

    print(f"Normalization complete! Processed {updated_cnt} / {len(src_files)} files.")


if __name__ == "__main__":
    main()
