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
   - Indicative Period Charters: Formats cleanly into 6 or 7 columns (Tenor | Vessel | Built | DWT | [Delivery] | Rate | Charterer).
     Zero dropped charterers, zero delivery-in-charterer shifts, clean message when no fixtures reported.
   - Spot Rates: Explicit 10 columns (Sector | Size | Routes | [Date1 WS] | [Date1 $/day] | [Date2 WS] | [Date2 $/day] | $/day ±% | [Year1] | [Year2]).
   - Baltic Indices: Explicit 9 columns for spot table, separate clean trend table for 1-year historical curves.
   - Indicative Market Values: Aligns Sector and Size into explicit 8 columns for both Tankers and Bulk Carriers.
   - TC Rates: Aligns Sector and Tenor into explicit 8 columns, never hijacked as period charters.
   - Secondhand Sales: Dedicated sections for Tankers, Bulk Carriers, Containers.
   - Indicative Newbuilding Prices: Combines multi-level YTD and 5-year High/Low headers into 13 explicit columns.
   - Demolition Market: Properly segments Indicative Demolition Prices, Currencies, and Demolition Sales with zero heading misplacement.
   - Trend & Forward Curves: Unpacks chart dumps into clean multi-column tables.
6. Table Decoupling & Isolation: Stops consecutive tables from merging into one wide table and strips trailing ghost empty columns.
7. Heading Deduplication: Eliminates repeated headings and cleans orphan headings.
8. Math Mode Protection: Escapes literal currency dollar signs in commentary prose to prevent LaTeX italic/space-stripping collapse in IDE preview.
9. Older Year Averages Sync: Synchronizes historical year averages from tables.json to eliminate omissions.
"""

from __future__ import annotations

import glob
import json
import os
import pathlib
import re
from typing import List, Tuple, Dict, Any

from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "data" / "extracted" / "llamaparse_intermodal_full"
MD_DIR = ROOT / "data" / "extracted" / "md" / "intermodal"

TENOR_PAT = re.compile(
    r'\b(?:\d+(?:\s*(?:to|/|-)\s*\d+)?\s*(?:mos|mons?|months?|yrs?|years?|weeks?)(?!\s*old)|'
    r'min\s+\d+[^/\n]+/max\s+\d+[^/\n]+)\b',
    re.IGNORECASE
)

PORT_OR_DATE_PAT = re.compile(
    r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|dely|del|redel|prompt|cjk|dalian|huangpu|fangcheng|rizhao|longyan|qingdao|zhoushan|singapore|spore|gibraltar|skaw|passero|kashima|yeosu|manila|subic|surabaya|kinnura|port\s+dickson|anjung)\b',
    re.IGNORECASE
)

RATE_PAT = re.compile(
    r'(\$\s*[\d,.]+(?:\s*k)?(?:\s*/\s*day)?|[\d,.]+\s*/\s*day|\$\d+[\d,.]*k[^\n|]*|index\s+linked[^\n|]*)',
    re.IGNORECASE
)

ROUTE_PAT = re.compile(r'^\*?\*?(\d+\s*[kK])\*?\*?\s+(.+)$')


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
    m = re.search(
        r"\n+(?:---\s*(?:PAGE\s*BREAK|-{3,})\s*---\s*\n+)?(?:#+\s*Intermodal\s*\n+)?#*\s*(?:Commodities\s*(?:&|&amp;|and)\s*Ship\s*Finance|Market\s*Data|Bunker\s*Prices|Maritime\s*Stock\s*Data|Contact\s+Directory|Directory|Intermodal\s+Shipbrokers\s+Head\s+Office)",
        text,
        re.I,
    )
    if m:
        text = text[: m.start()]

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


def is_tc_rates_table(r0: List[str], data_rows: List[List[str]]) -> bool:
    """Accurately identifies TC Rates tables and prevents collision with Period Charters."""
    r0_str = " ".join(r0).upper()
    all_text = " ".join(" ".join(r) for r in data_rows[:4]).upper()
    
    if any(k in r0_str for k in ["DIFF", "±%", "%"]) and any(k in r0_str for k in ["TENOR", "$/DAY", "CURRENT", "PREVIOUS"] or any("/" in c for c in r0)):
        if any(k in all_text for k in ["1YR", "3YR", "6MNT", "TC", "CAPESIZE", "VLCC", "PANAMAX"]):
            return True
            
    if any(k in all_text for k in ["300K 1YR TC", "180K 1YR TC", "76K 1YR TC", "58K 1YR TC", "32K 1YR TC", "150K 1YR TC", "110K 1YR TC"]):
        return True
        
    return False


def is_secondhand_table(r0: List[str], data_rows: List[List[str]]) -> bool:
    """Accurately identifies Secondhand S&P vessel tables."""
    all_headers = " ".join(r0).upper()
    if data_rows:
        all_headers += " " + " ".join(data_rows[0]).upper()
    return any(k in all_headers for k in ["SS DUE", "M/E", "BUYERS", "HULL", "GEAR"]) and any(k in all_headers for k in ["DWT", "NAME", "BUILT", "YARD"])


def is_period_charters_table(r0: List[str], data_rows: List[List[str]]) -> bool:
    """Accurately identifies Indicative Period Charters tables."""
    if is_tc_rates_table(r0, data_rows):
        return False
    if is_secondhand_table(r0, data_rows):
        return False
        
    r0_str = " ".join(r0).upper()
    if "INDICATIVE" in r0_str and "CHARTER" in r0_str:
        return True
        
    all_tbl_str = r0_str + " " + " ".join(" ".join(r) for r in data_rows).upper()
    if "DWT" in all_tbl_str and (any(TENOR_PAT.search(c) for c in all_tbl_str.split()) or "MOS" in all_tbl_str or "YEARS" in all_tbl_str):
        return True
        
    return False


def format_period_charters_table(table_lines: List[str]) -> Tuple[str, str]:
    """Formats Indicative Period Charters fixtures into clean 6 or 7 columns."""
    filtered_lines = []
    for l in table_lines:
        if re.match(r"^\|[\s:\-\|]+\|$", l):
            continue
        filtered_lines.append(l)

    records = []
    i = 0
    while i < len(filtered_lines):
        line = filtered_lines[i]
        cols = [c.strip() for c in line.strip("|").split("|")]
        if all("indicative" in c.lower() or "charter" in c.lower() or not c for c in cols):
            i += 1
            continue
        if any(c.lower() in ["tenor", "vessel", "built", "dwt", "rate", "charterer"] for c in cols) and not any(TENOR_PAT.search(c) for c in cols):
            i += 1
            continue

        c0 = cols[0] if cols else ""
        if not c0 and len(cols) > 1:
            cols = cols[1:]
            c0 = cols[0]

        m_t = TENOR_PAT.search(c0)
        if not m_t:
            for idx, c in enumerate(cols):
                m_t = TENOR_PAT.search(c)
                if m_t:
                    cols = cols[idx:]
                    c0 = cols[0]
                    break

        if m_t:
            tenor = m_t.group(0).strip()
            line1_cells = cols
            line2_cells = []
            if i + 1 < len(filtered_lines):
                cand = [c.strip() for c in filtered_lines[i + 1].strip("|").split("|")]
                cand_c0 = cand[0] if cand else ""
                if not cand_c0 and len(cand) > 1:
                    cand_c0 = cand[1]
                if not TENOR_PAT.search(cand_c0) and any(cand):
                    line2_cells = cand
                    i += 1

            c0 = line1_cells[0] if len(line1_cells) > 0 else ""
            c1 = line1_cells[1] if len(line1_cells) > 1 else ""
            c2 = line1_cells[2] if len(line1_cells) > 2 else ""
            c3 = line1_cells[3] if len(line1_cells) > 3 else ""

            vessel = c1.strip(' "\'')
            rem_c0 = TENOR_PAT.sub("", c0).strip(' "\'')
            if rem_c0 and not vessel:
                vessel = rem_c0

            built = c2.strip()
            dwt = c3.strip()
            rate = ""
            delivery = ""
            charterer = ""

            m_r = RATE_PAT.search(vessel)
            if m_r:
                rate = m_r.group(1).strip()
                vessel = vessel[:m_r.start()].strip(' "\'')

            if re.match(r"^\d{4}$", dwt) and not re.match(r"^\d{4}$", built):
                built, dwt = dwt, built

            m_dwt = re.search(r"^([\d,.]+\s*(?:dw\s*t|dwt))\s*(.*)$", dwt, re.I)
            if m_dwt:
                dwt = m_dwt.group(1).strip()
                rem_ch = m_dwt.group(2).strip(' "\'')
                if rem_ch:
                    charterer = rem_ch

            if line2_cells:
                for c in line2_cells:
                    c_str = c.strip()
                    if not c_str:
                        continue
                    if re.search(r"^\s*\$|/day\b|index\s+linked", c_str, re.I):
                        if not rate:
                            rate = c_str
                    elif PORT_OR_DATE_PAT.search(c_str) and not delivery:
                        delivery = c_str
                    elif not charterer:
                        charterer = c_str

            records.append({
                "tenor": tenor,
                "vessel": vessel,
                "built": built,
                "dwt": dwt,
                "delivery": delivery,
                "rate": rate,
                "charterer": charterer
            })
            i += 1
            continue
        i += 1

    heading = "## Indicative Period Charters\n\n"
    if not records:
        return heading, "_No period fixtures reported._"

    has_delivery = any(r["delivery"] for r in records)
    if has_delivery:
        out = [
            "| Tenor | Vessel | Built | DWT | Delivery | Rate | Charterer |",
            "| --- | --- | --- | --- | --- | --- | --- |"
        ]
        for r in records:
            d_val = r["delivery"] if r["delivery"] else "-"
            out.append(f"| {r['tenor']} | {r['vessel']} | {r['built']} | {r['dwt']} | {d_val} | {r['rate']} | {r['charterer']} |")
    else:
        out = [
            "| Tenor | Vessel | Built | DWT | Rate | Charterer |",
            "| --- | --- | --- | --- | --- | --- |"
        ]
        for r in records:
            out.append(f"| {r['tenor']} | {r['vessel']} | {r['built']} | {r['dwt']} | {r['rate']} | {r['charterer']} |")

    return heading, "\n".join(out)


def unpack_curve_dump(cells: List[str], curve_type: str = "DIRTY") -> str:
    """Unpacks a single-row chart curve dump into a clean vertical table."""
    dates = cells[0].split()
    if curve_type == "DIRTY":
        td3 = cells[1].split()[1:] if len(cells) > 1 else []
        td6 = cells[2].split()[1:] if len(cells) > 2 else []
        td9 = cells[3].split()[1:] if len(cells) > 3 else []
        res = [
            "### 1-Year Forward WS Rates - Dirty\n\n",
            "| Date | TD3 | TD6 | TD9 |",
            "| --- | --- | --- | --- |",
        ]
        for idx, d in enumerate(dates):
            v1 = td3[idx] if idx < len(td3) else ""
            v2 = td6[idx] if idx < len(td6) else ""
            v3 = td9[idx] if idx < len(td9) else ""
            res.append(f"| {d} | {v1} | {v2} | {v3} |")
        return "\n".join(res)
    else:
        tc1 = cells[1].split()[1:] if len(cells) > 1 else []
        tc2 = cells[2].split()[1:] if len(cells) > 2 else []
        tc5 = cells[3].split()[1:] if len(cells) > 3 else []
        tc6 = cells[4].split()[1:] if len(cells) > 4 else []
        res = [
            "### 1-Year Forward WS Rates - Clean\n\n",
            "| Date | TC1 | TC2 | TC5 | TC6 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for idx, d in enumerate(dates):
            v1 = tc1[idx] if idx < len(tc1) else ""
            v2 = tc2[idx] if idx < len(tc2) else ""
            v3 = tc5[idx] if idx < len(tc5) else ""
            v4 = tc6[idx] if idx < len(tc6) else ""
            res.append(f"| {d} | {v1} | {v2} | {v3} | {v4} |")
        return "\n".join(res)


def clean_table(table_lines: List[str]) -> str:
    """Transforms, isolates, and aligns a raw Markdown table block with semantic headings."""
    parsed = []
    for l in table_lines:
        cells = [c.strip() for c in l.strip()[1:-1].split("|")]
        parsed.append(cells)

    if len(parsed) < 2:
        return "\n".join(table_lines)

    r0 = parsed[0]
    r1 = parsed[1]
    data_rows = parsed[2:]

    # Promote single-cell title row (e.g. '| Demolition Sales | | | |') to section heading
    prefix_heading = ""
    non_empty_r0 = [c for c in r0 if c]
    if len(non_empty_r0) == 1 and len(data_rows) > 0:
        title_text = non_empty_r0[0].strip()
        t_up = title_text.upper()
        if "DIRTY" in t_up and "WS" in t_up:
            if not any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
                return ""
            prefix_heading = "### Dirty WS Rates (1-Year Trend)\n\n"
            r0 = data_rows[0]
            if not r0[0] and len(r0) > 1:
                r0[0] = "Date"
            data_rows = data_rows[1:]
        elif "CLEAN" in t_up and "WS" in t_up:
            if not any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
                return ""
            prefix_heading = "### Clean WS Rates (1-Year Trend)\n\n"
            r0 = data_rows[0]
            if not r0[0] and len(r0) > 1:
                r0[0] = "Date"
            data_rows = data_rows[1:]
        else:
            prefix_heading = f"## {title_text}\n\n"
            r0 = data_rows[0]
            data_rows = data_rows[1:]

    if len(r0) > 1 and not r0[0] and "WS" in r0[1].upper() and any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
        r0[0] = "Date"

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

    # Stop data_rows if a duplicate header or table title is encountered inside data_rows
    cleaned_rows = []
    for r in data_rows:
        if any(c.lower() in ["name", "size", "ldt", "built", "yard"] for c in r) and any(c.lower() in ["breakers", "comments", "price"] for c in r):
            break
        if len([c for c in r if c]) == 1 and any(k in r[0].lower() for k in ["demolition sales", "newbuilding orders", "indicative"]):
            break
        cleaned_rows.append(r)
    data_rows = cleaned_rows

    r0_str = " ".join(r0).upper()

    # Special Check 1: Indicative Period Charters table
    if is_period_charters_table(r0, data_rows):
        h, body = format_period_charters_table(table_lines)
        return h + body

    # Special Check 2: Tanker WS Rates Trend Charts (Dirty TD3/TD6/TD9 and Clean TC1/TC2/TC5/TC6)
    all_table_text = (r0_str + " " + " ".join(" ".join(r) for r in data_rows)).upper()
    is_spot_routes = any(k in all_table_text for k in ["ROUTES", "MEG-SPORE", "WAF-CHINA", "CARIBS-USG", "ARA-UKC", "CARRIERS"])

    if not is_spot_routes and (any(k in r0_str for k in ["TD3", "TD6", "TD9"]) or any(k in all_table_text for k in ["TD3", "TD6", "TD9"]) or ("DIRTY" in r0_str and "WS" in r0_str)):
        # Dump line check
        if len(r0) >= 4 and len(r0[0].split()) >= 4 and any("/" in d for d in r0[0].split()[:3]):
            return unpack_curve_dump(r0, "DIRTY")
        elif len(data_rows) >= 2 and any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
            if len(r0) <= 2 or (data_rows and len(data_rows[0]) <= 2):
                r0 = ["Date", "WS points"]
                data_rows = [r[:2] for r in data_rows if any(r)]
            else:
                r0 = ["Date", "TD3", "TD6", "TD9"]
                data_rows = [r[:4] for r in data_rows if any(r)]
            res = [
                "### Dirty WS Rates (1-Year Trend)\n\n",
                "| " + " | ".join(r0) + " |",
                "| " + " | ".join(["---"] * len(r0)) + " |",
            ]
            for r in data_rows:
                padded = r + [""] * (len(r0) - len(r))
                res.append("| " + " | ".join(padded[:len(r0)]) + " |")
            return "\n".join(res)
        else:
            return ""

    elif not is_spot_routes and (any(k in r0_str for k in ["TC1", "TC2", "TC5", "TC6"]) or any(k in all_table_text for k in ["TC1", "TC2", "TC5", "TC6"]) or ("CLEAN" in r0_str and "WS" in r0_str)):
        # Dump line check
        if len(r0) >= 4 and len(r0[0].split()) >= 4 and any("/" in d for d in r0[0].split()[:3]):
            return unpack_curve_dump(r0, "CLEAN")
        elif len(data_rows) >= 2 and any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
            if len(r0) <= 2 or (data_rows and len(data_rows[0]) <= 2):
                r0 = ["Date", "WS points"]
                data_rows = [r[:2] for r in data_rows if any(r)]
            else:
                r0 = ["Date", "TC1", "TC2", "TC5", "TC6"]
                data_rows = [r[:5] for r in data_rows if any(r)]
            res = [
                "### Clean WS Rates (1-Year Trend)\n\n",
                "| " + " | ".join(r0) + " |",
                "| " + " | ".join(["---"] * len(r0)) + " |",
            ]
            for r in data_rows:
                padded = r + [""] * (len(r0) - len(r))
                res.append("| " + " | ".join(padded[:len(r0)]) + " |")
            return "\n".join(res)
        else:
            return ""

    # Special Check 3: Page 3 Average T/C Rates chart
    elif any("AVERAGE OF THE" in c.upper() for c in r0) or any("5TC BPI" in c.upper() for c in r0) or any("AVR 5TC" in c.upper() for c in r0):
        # Dump line check
        if len(r0) >= 5 and len(r0[0].split()) >= 4 and any("/" in d for d in r0[0].split()[:3]):
            dump_line = table_lines[0]
            cells = [c.strip() for c in dump_line.strip("|").split("|")]
            if len(cells) >= 5:
                dates = cells[0].split()
                c1_nums = cells[1].split()[len("Average of the 5 T/ C".split()):]
                c2_nums = cells[2].split()[len("AVR 5TC BPI".split()):]
                c3_nums = cells[3].split()[len("AVR 10TC BSI".split()):]
                c4_nums = cells[4].split()[len("AVR 7TC BHSI".split()):]
                res = [
                    "### Average T/C Rates (1-Year Trend)\n\n",
                    "| Date | 5TC Average | 5TC BPI | 10TC BSI | 7TC BHSI |",
                    "| --- | --- | --- | --- | --- |",
                ]
                for idx, d in enumerate(dates):
                    v1 = c1_nums[idx] if idx < len(c1_nums) else ""
                    v2 = c2_nums[idx] if idx < len(c2_nums) else ""
                    v3 = c3_nums[idx] if idx < len(c3_nums) else ""
                    v4 = c4_nums[idx] if idx < len(c4_nums) else ""
                    res.append(f"| {d} | {v1} | {v2} | {v3} | {v4} |")
                return "\n".join(res)
        elif len(data_rows) >= 2 and any(re.search(r"\d{1,2}[/-]", str(r[0])) for r in data_rows):
            r0 = ["Date", "5TC Average", "5TC BPI", "10TC BSI", "7TC BHSI"]
            data_rows = [r[:5] for r in data_rows if any(r)]
            res = [
                "### Average T/C Rates (1-Year Trend)\n\n",
                "| " + " | ".join(r0) + " |",
                "| " + " | ".join(["---"] * len(r0)) + " |",
            ]
            for r in data_rows:
                padded = r + [""] * (len(r0) - len(r))
                res.append("| " + " | ".join(padded[:len(r0)]) + " |")
            return "\n".join(res)
        else:
            return ""

    # Special Check 3B: Baltic Indices Trend (1-Year Trend) vs Spot
    elif any(k in r0_str for k in ["BCI", "BPI", "BSI", "BHSI"]) and any("DATE" in c.upper() for c in r0) and len(data_rows) >= 2:
        if not any(k in r0_str for k in ["DIFF", "$/DAY", "±%", "POINT DIFF"]) and not any("DIFF" in str(r).upper() for r in data_rows) and not any("±%" in str(r) for r in data_rows) and not any("$/DAY" in str(r).upper() for r in data_rows):
            r0 = ["Date", "BCI", "BPI", "BSI", "BHSI", "BDI"][:len(r0)]
            data_rows = [r[:len(r0)] for r in data_rows if any(r)]
            res = [
                "### Baltic Indices (1-Year Trend)\n\n",
                "| " + " | ".join(r0) + " |",
                "| " + " | ".join(["---"] * len(r0)) + " |",
            ]
            for r in data_rows:
                padded = r + [""] * (len(r0) - len(r))
                res.append("| " + " | ".join(padded[:len(r0)]) + " |")
            return "\n".join(res)

    # Special Check 4: Secondhand Sales (Tankers, Bulk Carriers, Containers)
    if is_secondhand_table(r0, data_rows):
        if data_rows and any(c.lower() in ["name", "dwt", "built", "yard"] for c in data_rows[0]):
            r0 = data_rows[0]
            data_rows = data_rows[1:]
        all_r_str = " ".join(" ".join(r) for r in data_rows).upper()
        if any(k in all_r_str for k in ["NEWCASTLEMAX", "CAPE", "KAMSARMAX", "UMAX", "SUPRA", "HANDY"]):
            prefix_heading = "## Bulk Carriers\n\n"
        elif any(k in all_r_str for k in ["VLCC", "AFRA", "SUEZMAX", "LR1", "MR2"]):
            prefix_heading = "## Tankers\n\n"
        elif any(k in all_r_str for k in ["FEEDER", "TEU", "CONTAINER"]):
            prefix_heading = "## Containers\n\n"
        else:
            prefix_heading = "## Secondhand Sales\n\n"

    # Case 0: Tanker Market Spot Rates Table (10 columns)
    elif ("WS POINTS" in r0_str and "$/DAY" in r0_str) or (any("MEG-SPORE" in str(r).upper() for r in data_rows[:3])):
        prefix_heading = "## Spot Rates\n\n"
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
            "Sector", "Size", "Routes",
            f"{d1} WS points", f"{d1} $/day",
            f"{d2} WS points", f"{d2} $/day",
            "$/day ±%", f"{y1} $/day", f"{y2} $/day"
        ]

        fixed_data = []
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            if all(c.strip().lower() in ["", "ws points", "$/day", "index", "$/day ±%", "±%", "diff"] for c in r):
                continue
            sector, size, route, rest = "", "", "", []
            if len(r) >= 2 and ROUTE_PAT.match(re.sub(r"\*+", "", r[1]).strip()):
                sector = r[0]
                m = ROUTE_PAT.match(re.sub(r"\*+", "", r[1]).strip())
                size, route = m.group(1).strip(), m.group(2).strip()
                rest = r[2:]
            elif len(r) >= 1 and ROUTE_PAT.match(re.sub(r"\*+", "", r[0]).strip()):
                m = ROUTE_PAT.match(re.sub(r"\*+", "", r[0]).strip())
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
    elif ("5YRS OLD" in r0_str or "5YR OLD" in r0_str or "5 YRS OLD" in r0_str or 
          ("VESSEL" in r0_str and any("DH" in str(r).upper() for r in data_rows[:3])) or 
          any("300KT DH" in str(r).upper() for r in data_rows[:3]) or
          ("CARRIERS" in r0_str and any("180K" in str(r).upper() for r in data_rows[:3])) or
          ("VESSEL" in r0_str and any("180K" in str(r).upper() for r in data_rows[:3])) or
          ("VESSEL" in r0_str and any("CAPESIZE" in str(r).upper() for r in data_rows[:3]))
         ) and not ("NEWBUILDING" in r0_str or any("NEWCASTLEMAX" in str(r).upper() for r in data_rows[:3])):
        
        is_bulker = any("180K" in str(r).upper() for r in data_rows[:3]) or any("CAPESIZE" in str(r).upper() for r in data_rows[:3])
        prefix_heading = "## Indicative Market Values ($ Million) - Bulk Carriers\n\n" if is_bulker else "## Indicative Market Values ($ Million) - Tankers\n\n"

        r0 = [re.sub(r"^Carriers\s+", "", c, flags=re.I).strip() for c in r0]
        months = []
        for c in r0:
            m_m = re.search(r"[A-Za-z]{3}-\d{2,4}", c)
            if m_m and m_m.group(0) not in months:
                months.append(m_m.group(0))
        years = []
        for c in r0:
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in d for d in months):
                years.append(m_y.group(0))

        m1 = months[0] + " avg" if len(months) > 0 else "Current avg"
        m2 = months[1] + " avg" if len(months) > 1 else "Previous avg"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"
        y3 = years[2] if len(years) > 2 else "Year3"

        r0 = ["Sector", "Size", m1, m2, "±%", y1, y2, y3]

        fixed_data = []
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            c0_clean = re.sub(r"^Carriers\s+", "", r[0], flags=re.I).strip()
            sector, size, rest = "", "", []
            m_sec_size = re.match(r"^(\bCapesize(?:\s+Eco)?\b|\bKamsarmax\b|\bUltramax\b|\bHandysize\b|\bVLCC\b|\bSuezmax\b|\bAframax\b|\bLR1\b|\bMR\b|\bHandy\b)\s+(.+)$", c0_clean, re.I)
            if m_sec_size:
                sector, size = m_sec_size.group(1).strip(), m_sec_size.group(2).strip()
                rest = r[1:]
            elif len(r) > 1 and re.match(r"^(\d+\s*[kK](?:T)?(?:\s*DH)?)$", r[1].strip()):
                sector, size = c0_clean, r[1].strip()
                rest = r[2:]
            else:
                sector = c0_clean
                size = r[1] if len(r) > 1 else ""
                rest = r[2:]
            new_r = [sector, size] + rest
            padded = new_r + [""] * (8 - len(new_r))
            fixed_data.append(padded[:8])
        data_rows = fixed_data

    # Case B: TC Rates Table (8 columns)
    elif is_tc_rates_table(r0, data_rows):
        prefix_heading = "## TC Rates\n\n"
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

        r0 = ["Sector", "Tenor", d1, d2, "±%", "Diff", y1, y2]

        fixed_data = []
        for r in data_rows:
            while r and r[-1] == "":
                r = r[:-1]
            if not r or not any(r):
                continue
            sector, tenor, rest = "", "", []
            m_sec_ten = re.match(r"^(\bCapesize\b|\bPanamax\b|\bSupramax\b|\bHandysize\b|\bVLCC\b|\bSuezmax\b|\bAframax\b|\bMR\b|\bHandy\b)\s+(.+)$", r[0].strip(), re.I)
            if m_sec_ten:
                sector, tenor = m_sec_ten.group(1).strip(), m_sec_ten.group(2).strip()
                rest = r[1:]
            elif len(r) > 1 and any(t in r[1].lower() for t in ["1yr", "3yr", "6mnt", "1 yr", "3 yr"]):
                sector, tenor = r[0].strip(), r[1].strip()
                rest = r[2:]
            else:
                sector = r[0].strip()
                tenor = r[1].strip() if len(r) > 1 else ""
                rest = r[2:]
            new_r = [sector, tenor] + rest
            padded = new_r + [""] * (8 - len(new_r))
            fixed_data.append(padded[:8])
        data_rows = fixed_data

    # Case C: Page 1 Baltic Indices Summary (3 rows, 3 columns)
    elif len(data_rows) == 3 and any(str(r[0]).upper() in ["BDI", "BDTI", "BCTI"] for r in data_rows):
        prefix_heading = "### Baltic Indices Summary\n\n"
        r0 = ["Index", "Date", "Value"]
        fixed_data = []
        for r in data_rows:
            padded = r + [""] * (3 - len(r))
            fixed_data.append(padded[:3])
        data_rows = fixed_data

    # Case D0: Baltic Indices 1-Year Trend Table (horizontal with monthly dates in header)
    elif (
        len(data_rows) > 0
        and any(re.sub(r"[\*\s]", "", str(r[0])).upper() in ["BDI", "BCI", "BPI", "BSI", "BHSI"] for r in data_rows[:3])
        and not any(k in r0_str for k in ["DIFF", "$/DAY", "±%", "POINT DIFF"])
        and len([c for c in r0 if re.search(r"\d{1,2}[/-]\w+", c)]) >= 6
    ):
        dates = [c for c in r0[1:] if c]
        series_names = [re.sub(r"[\*\s]", "", r[0]).upper() for r in data_rows if any(r)]
        header = ["Date"] + series_names
        res = [
            "### Baltic Indices (1-Year Trend)\n\n",
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |"
        ]
        for k_idx, dt in enumerate(dates):
            vals = [r[1+k_idx] if 1+k_idx < len(r) else "" for r in data_rows if any(r)]
            res.append("| " + " | ".join([dt] + vals) + " |")
        return "\n".join(res)

    # Case D: Page 3 Baltic Indices Spot Table (9 columns)
    elif len(data_rows) > 0 and (
        any(re.sub(r"[\*\s]", "", c).upper() in ["BDI", "BCI", "BPI", "BSI", "BHSI"] for c in r0) or 
        any(re.sub(r"[\*\s]", "", str(r[0])).upper() in ["BDI", "BCI", "BPI", "BSI", "BHSI"] for r in data_rows[:3])
    ) and not (any("DATE" in c.upper() for c in r0) and not any(k in r0_str for k in ["DIFF", "$/DAY", "±%", "POINT DIFF"])):
        prefix_heading = "## Baltic Indices\n\n"
        all_cells = r0 + (data_rows[0] if data_rows else [])
        dates = []
        for c in all_cells:
            m_d = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", c)
            if m_d and m_d.group(0) not in dates:
                dates.append(m_d.group(0))
        years = []
        for c in all_cells:
            m_y = re.search(r"20\d\d", c)
            if m_y and m_y.group(0) not in years and not any(m_y.group(0) in d for d in dates):
                years.append(m_y.group(0))

        d1 = dates[0] if len(dates) > 0 else "Current"
        d2 = dates[1] if len(dates) > 1 else "Previous"
        y1 = years[0] if len(years) > 0 else "Year1"
        y2 = years[1] if len(years) > 1 else "Year2"

        r0 = ["Index Name", f"{d1} Index", f"{d1} $/day", f"{d2} Index", f"{d2} $/day", "Point Diff", "$/day ±%", f"{y1} Index", f"{y2} Index"]

        if data_rows and any("INDEX" in c.upper() for c in data_rows[0]) and any("$/DAY" in c.upper() for c in data_rows[0]):
            data_rows = data_rows[1:]

        fixed_data = []
        for r in data_rows:
            while r and not r[-1]:
                r = r[:-1]
            if not r:
                continue
            if all(c.strip().lower() in ["", "ws points", "$/day", "index", "$/day ±%", "±%", "diff", "point diff"] for c in r):
                continue
            clean_sym = re.sub(r"[\*\s]", "", r[0]).upper()
            if re.match(r"^\d[\d,]+$", clean_sym):
                r = ["BDI"] + r
            elif clean_sym in ["BDI", "BCI", "BPI", "BSI", "BHSI"]:
                r[0] = clean_sym
            padded = r + [""] * (len(r0) - len(r))
            fixed_data.append(padded[:len(r0)])
        data_rows = fixed_data

    # Case E: Demolition Currencies Table (5 columns)
    elif any("USD/" in str(r) for r in data_rows):
        prefix_heading = "## Currencies\n\n"
        r0 = ["Markets", "Current", "Previous", "±%", "YTD High"]
        fixed_data = []
        for r in data_rows:
            padded = r + [""] * (5 - len(r))
            fixed_data.append(padded[:5])
        data_rows = fixed_data

    # Case F: Demolition Sales Table
    elif any("LDT" in c.upper() for c in r0) and any(c.upper() in ["BREAKERS", "BUYERS"] for c in r0):
        prefix_heading = "## Demolition Sales\n\n"
        r0 = ["Name", "Size", "Ldt", "Built", "Yard", "Type", "$/ldt", "Breakers", "Comments"]
        fixed_data = []
        for r in data_rows:
            padded = r + [""] * (len(r0) - len(r))
            fixed_data.append(padded[:len(r0)])
        data_rows = fixed_data

    # Case G: Newbuilding Orders Table
    elif any(c.upper() in ["UNITS", "DELIVERY", "BUYER", "OWNER"] for c in r0) and any(c.upper() in ["YARD", "SHIPBUILDER"] for c in r0):
        prefix_heading = "## Newbuilding Orders\n\n"
        r0 = ["Units", "Type", "Size", "Yard", "Delivery", "Buyer", "Price", "Comments"]
        fixed_data = []
        for r in data_rows:
            if len(r) >= 9 and r[3].lower() in ["dwt", "cbm", "teu", ""]:
                r = [r[0], r[1], f"{r[2]} {r[3]}".strip()] + r[4:]
            padded = r + [""] * (len(r0) - len(r))
            fixed_data.append(padded[:len(r0)])
        data_rows = fixed_data

    # Case H: Indicative Demolition Prices Table
    elif any("DEMOLITION" in c.upper() or "MARKET" in c.upper() for c in r0[:2]) and any("BANGLADESH" in str(r).upper() for r in data_rows):
        prefix_heading = "## Indicative Demolition Prices ($/ldt)\n\n"

    # Case I: Indicative Newbuilding Prices Table
    elif (any("NEWCASTLEMAX" in str(r).upper() for r in data_rows[:3]) or any("LNG 174K" in str(r).upper() for r in data_rows)) and not is_secondhand_table(r0, data_rows):
        prefix_heading = "## Indicative Newbuilding Prices ($ Million)\n\n"

    # Case J: Chart Trend Curves vs Spot Table
    elif (any("BCI" in str(r).upper() for r in data_rows) and any("BDI" in str(r).upper() for r in data_rows)) or (any("BCI" in c.upper() for c in r0) and any("BDI" in c.upper() for c in r0)):
        if any("DIFF" in str(r).upper() for r in data_rows) or any("±%" in str(r) for r in data_rows) or any("$/DAY" in str(r).upper() for r in data_rows):
            prefix_heading = "## Baltic Indices\n\n"
        else:
            prefix_heading = "### Baltic Indices (1-Year Trend)\n\n"
    elif any("AVERAGE OF THE" in str(r).upper() for r in data_rows) or any("5TC BPI" in str(r).upper() for r in data_rows):
        prefix_heading = "### Average T/C Rates (1-Year Trend)\n\n"
    elif any("VLCC" in str(r).upper() for r in data_rows) and any("SUEZMAX" in str(r).upper() for r in data_rows) and any("DATE" in c.upper() for c in r0):
        prefix_heading = "### Tankers Newbuilding Prices (Trend)\n\n"
    elif any("CAPESIZE" in str(r).upper() for r in data_rows) and any("KAMSARMAX" in str(r).upper() for r in data_rows) and any("DATE" in c.upper() for c in r0):
        prefix_heading = "### Bulk Carriers Newbuilding Prices (Trend)\n\n"
    elif any("BANGLADESH" in str(r).upper() for r in data_rows) and any("INDIA" in str(r).upper() for r in data_rows) and any("DATE" in c.upper() for c in r0):
        prefix_heading = "### Demolition Prices Trend\n\n"

    # Clean data cells: remove <br/> and pad to match header length
    clean_data = []
    for r in data_rows:
        if any(r):
            c_row = [re.sub(r"<br/?>", " ", cell).strip() for cell in r]
            padded = c_row + [""] * (len(r0) - len(c_row))
            clean_data.append(padded[:len(r0)])

    # Universal trailing empty column stripper
    while len(r0) > 1 and not r0[-1]:
        r0 = r0[:-1]
        clean_data = [r[:len(r0)] for r in clean_data]
    while len(r0) > 3 and len(clean_data) > 0 and all(r[-1] == "" for r in clean_data):
        r0 = r0[:-1]
        clean_data = [r[:-1] for r in clean_data]

    if not any(r0) or len(r0) < 2:
        return ""

    res = []
    res.append("| " + " | ".join(r0) + " |")
    res.append("| " + " | ".join(["---"] * len(r0)) + " |")
    for r in clean_data:
        res.append("| " + " | ".join(r) + " |")

    return prefix_heading + "\n".join(res)


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

    # 1. Convert HTML tables to markdown tables first
    t0 = replace_html_tables(text)

    # 2. Strip strikethroughs
    t1 = strip_strikethrough(t0)

    # 3. Clean boilerplate and enforce page bounds
    t2 = clean_boilerplate_and_bounds(t1, year)

    # 4. Clean tables with strict boundary detection
    lines = t2.splitlines()
    out = []
    i = 0
    seen_tables = set()
    seen_table_data = set()

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and i + 1 < len(lines) and any(s in lines[i + 1] for s in ["| ---", "|:---", "|---"]):
            table_lines = [line, lines[i + 1]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                # Boundary check: stop if line j starts a separate table
                if j + 1 < len(lines) and any(s in lines[j + 1] for s in ["| ---", "|:---", "|---"]):
                    break
                table_lines.append(lines[j])
                j += 1
            cleaned_tbl = clean_table(table_lines)
            if not cleaned_tbl.strip():
                # If preceding line was an orphan chart header for this suppressed table, pop it!
                while out and not out[-1].strip():
                    out.pop()
                if out and out[-1].strip().startswith("#") and "\n" not in out[-1].strip():
                    hdr_core = re.sub(r"[\W_]+", "", out[-1].strip()).lower()
                    if any(hdr_core.startswith(k) for k in ["dirtywsrates", "cleanwsrates", "charts"]):
                        out.pop()
                i = j
                continue

            # Deduplicate headings & remove misplaced headers from out
            tbl_lines = cleaned_tbl.splitlines()
            if tbl_lines and tbl_lines[0].startswith("#"):
                tbl_heading = tbl_lines[0].strip()
                tbl_core = re.sub(r"[\W_]+", "", tbl_heading).lower()

                # Check recent lines in out
                while out and not out[-1].strip():
                    out.pop()
                
                # Check single-line standalone headings in out
                if out and out[-1].strip().startswith("#") and "\n" not in out[-1].strip():
                    prev_hdr = out[-1].strip()
                    prev_core = re.sub(r"[\W_]+", "", prev_hdr).lower()
                    
                    # If exact same heading already exists, strip from cleaned_tbl
                    if prev_core == tbl_core:
                        cleaned_tbl = "\n".join(tbl_lines[1:]).lstrip()
                    # If generic Baltic Indices header before 1-Year Trend table, replace it!
                    elif prev_core == "balticindices" and "trend" in tbl_core:
                        out.pop()
                    # If generic Average T/C Rates header before 1-Year Trend table, replace it!
                    elif any(prev_core.startswith(k) for k in ["averagetcrates", "avgtcrates", "charts"]) and "trend" in tbl_core:
                        out.pop()
                    # If misplaced previous header (e.g. ## Currencies right before Demolition Sales), pop it!
                    elif any(prev_core.startswith(k) for k in ["currencies", "indicativedemolitionprices"]) and not tbl_core.startswith(prev_core[:8]):
                        out.pop()

            # Data hash deduplication
            data_lines = [l.strip() for l in cleaned_tbl.splitlines() if l.strip().startswith("|") and not re.match(r"^\|[\s:\-\|]+\|$", l.strip())]
            data_hash = re.sub(r"\s+", "", "".join(data_lines))
            tbl_hash = re.sub(r"\s+", "", cleaned_tbl)

            if data_hash and data_hash in seen_table_data and len(data_lines) > 2:
                i = j
                continue

            if tbl_hash not in seen_tables or len(table_lines) > 20:
                out.append(cleaned_tbl)
                out.append("")
                seen_tables.add(tbl_hash)
                if data_hash:
                    seen_table_data.add(data_hash)

            i = j
            continue
        out.append(line)
        i += 1

    txt = "\n".join(out)

    # Clean redundant isolated '## Period' headings that immediately follow Period Charters
    txt = re.sub(r'(## Indicative Period Charters\s*\n\s*(?:_No period fixtures reported\._)?\s*\n+)## Period\s*\n+', r'\1', txt)

    # 5. Escape literal dollar signs in prose paragraphs (lines not starting with '|' or '#')
    out_lines = []
    for line in txt.splitlines():
        if line.strip().startswith("|") or line.strip().startswith("#"):
            out_lines.append(line)
        else:
            escaped_line = re.sub(r"(?<!\\)\$", r"\\$", line)
            out_lines.append(escaped_line)

    # Strip orphan headings (empty headings followed immediately by another heading or EOF)
    final_lines = []
    for idx, l in enumerate(out_lines):
        if l.strip().startswith("#"):
            has_content = False
            next_heading = ""
            for nxt in out_lines[idx+1:idx+6]:
                if nxt.strip().startswith("#"):
                    next_heading = nxt.strip()
                    break
                if nxt.strip() and not nxt.strip().startswith("---"):
                    has_content = True
                    break
            if not has_content:
                if idx + 5 >= len(out_lines):
                    continue
                c_low = l.strip().lower()
                n_low = next_heading.lower()
                is_legit = False
                if "weekly market report" in c_low and "week" in n_low:
                    is_legit = True
                elif any(m in c_low for m in ["tanker market", "dry bulk market", "secondhand sales", "newbuilding market", "demolition market"]):
                    is_legit = True
                elif "market insight" in c_low and any(k in n_low for k in ["**by", "by "]):
                    is_legit = True
                if not is_legit and next_heading:
                    continue
        final_lines.append(l)

    res = "\n".join(final_lines)
    res = re.sub(r"\n{3,}", "\n\n", res)
    res = sync_tables_from_json(res, file_path)
    return res.strip() + "\n"


def normalize_file(src_file: pathlib.Path, dest_file: pathlib.Path) -> bool:
    try:
        orig = src_file.read_text(encoding="utf-8", errors="replace")
        cleaned = normalize_markdown(orig, dest_file)
        dest_file.parent.mkdir(parents=True, exist_ok=True)
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
        m_yr = re.search(r"20(2[1-6])", f.name)
        year_str = m_yr.group(0) if m_yr else "2026"
        dest = MD_DIR / year_str / f.name
        if normalize_file(f, dest):
            updated_cnt += 1

    print(f"Normalization complete! Processed {updated_cnt} / {len(src_files)} files.")


if __name__ == "__main__":
    main()
