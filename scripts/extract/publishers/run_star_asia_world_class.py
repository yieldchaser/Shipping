"""
World-Class Batch Extraction & Polishing Engine for Star Asia Weekly Market Reports.

Executes end-to-end cover-to-cover extraction:
1. Calls LlamaParse (cost_effective tier) via llama_manager automatic failover pool.
2. Caches raw markdown in data/extracted/llamaparse_star_asia_full/<stem>.md.
3. Polishes markdown to publication-grade quality (strips boilerplate, fixes headers, formats tables).
4. Emits structured sidecar in data/extracted/md/star_asia/<stem>.tables.json.
5. Updates stacked time series CSVs in data/extracted/series/.
6. Tracks persistent run state in data/extracted/llamaparse_star_asia_full/_run_state.json.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

warnings.filterwarnings("ignore", category=DeprecationWarning)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

import pymupdf
from llama_parse import LlamaParse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))
import llama_manager

CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "star_asia"
RAW_OUT_DIR = ROOT / "data" / "extracted" / "llamaparse_star_asia_full"
MD_OUT_DIR = ROOT / "data" / "extracted" / "md" / "star_asia"
SERIES_DIR = ROOT / "data" / "extracted" / "series"
STATE_FILE = RAW_OUT_DIR / "_run_state.json"

RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
MD_OUT_DIR.mkdir(parents=True, exist_ok=True)
SERIES_DIR.mkdir(parents=True, exist_ok=True)


def load_run_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}, "total_pages": 0}


def save_run_state(state: Dict[str, Any]):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def format_number_commas(val_str: str) -> str:
    """Format pure integer strings >= 10,000 with commas. Preserves 4-digit years intact."""
    val = val_str.strip()
    if re.fullmatch(r"\d{5,}", val):
        return f"{int(val):,}"
    return val


def html_table_to_md(html_str: str) -> str:
    headers = []
    th_matches = re.findall(r"<th[^>]*>(.*?)</th>", html_str, re.IGNORECASE | re.DOTALL)
    if th_matches:
        headers = [re.sub(r"<[^>]+>", "", h).strip() for h in th_matches]

    rows = []
    tr_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", html_str, re.IGNORECASE | re.DOTALL)
    for tr in tr_matches:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.IGNORECASE | re.DOTALL)
        if tds:
            row = [format_number_commas(re.sub(r"<[^>]+>", " ", td).strip()) for td in tds]
            rows.append(row)

    if not headers and rows:
        headers = [f"Col {i+1}" for i in range(len(rows[0]))]

    if not headers:
        return html_str

    md = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        while len(r) < len(headers):
            r.append("")
        md.append("| " + " | ".join(r[: len(headers)]) + " |")
    return "\n".join(md)


def clean_markdown_table(table_str: str) -> str:
    lines = [ln.strip() for ln in table_str.strip().split("\n") if ln.strip()]
    if len(lines) < 3:
        return table_str

    header_line = lines[0]
    sep_line = lines[1]
    data_lines = []
    footnotes = []

    for ln in lines[2:]:
        lower_ln = ln.lower()
        if "amount in usd" in lower_ln or "eco units" in lower_ln or "all prices are usd" in lower_ln:
            clean_fn = re.sub(r"^[\|\s\*\\]+", "", ln)
            clean_fn = re.sub(r"[\|\s\*\\]+$", "", clean_fn).strip()
            clean_fn = clean_fn.replace("\\*", "").replace("*", "").strip()
            if clean_fn:
                footnotes.append(f"*{clean_fn}*")
            continue

        cols = [c.strip() for c in ln.strip("|").split("|")]
        formatted_cols = [format_number_commas(c) for c in cols]
        data_lines.append("| " + " | ".join(formatted_cols) + " |")

    res = [header_line, sep_line] + data_lines
    res_str = "\n".join(res)
    if footnotes:
        res_str += "\n\n" + "\n\n".join(footnotes)
    return res_str


def parse_md_table_to_dict(table_str: str) -> Optional[Dict[str, Any]]:
    lines = [ln.strip() for ln in table_str.strip().split("\n") if ln.strip()]
    if len(lines) < 3:
        return None
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    data_rows = []
    for line in lines[2:]:
        if line.startswith("*") and not line.startswith("* |"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) == len(headers):
            row_dict = {headers[i]: cols[i] for i in range(len(headers))}
            data_rows.append(row_dict)
    return {"headers": headers, "rows": data_rows}


def extract_metadata_from_pdf(pdf_path: Path) -> Dict[str, Any]:
    doc = pymupdf.open(str(pdf_path))
    num_pages = len(doc)
    fn = pdf_path.stem

    m_wk = re.search(r"_W(\d{1,2})[_\.]", fn, re.I) or re.search(r"week[_\-\s]*(\d{1,2})", fn, re.I) or re.search(r"W(\d{1,2})", fn, re.I)
    wk = int(m_wk.group(1)) if m_wk else 0

    p1 = doc[0].get_text()
    MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    dt = None
    yr = None
    for line in p1.splitlines()[:25]:
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", line, flags=re.I)
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(202\d)", cleaned)
        if m and m.group(1).lower() in MONTHS:
            mo = MONTHS[m.group(1).lower()]
            da = int(m.group(2))
            yr = int(m.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(202\d)", cleaned)
        if m2 and m2.group(2).lower() in MONTHS:
            da = int(m2.group(1))
            mo = MONTHS[m2.group(2).lower()]
            yr = int(m2.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break

    if not dt:
        m_dt = re.search(r"(\d{2})_(\d{2})_(202\d)", fn)
        if m_dt:
            d, m, y = int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"
            yr = y
        else:
            m_yr = re.search(r"(202\d)", str(pdf_path))
            yr = int(m_yr.group(1)) if m_yr else 2026
            dt = f"{yr:04d}-00-00"

    doc.close()
    try:
        rel_src = str(pdf_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        rel_src = str(pdf_path).replace("\\", "/")

    return {
        "source_file": rel_src,
        "publisher": "star_asia",
        "issue_date": dt,
        "report_week": wk,
        "year": yr,
        "pages": num_pages,
    }


def parse_with_llamaparse(pdf_path: Path) -> str:
    """Parse entire PDF using LlamaParse with automatic key failover."""
    def _call(api_key: str) -> str:
        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            tier="cost_effective",
            version="latest",
            verbose=False,
        )
        extra_info = {"file_name": pdf_path.name}
        docs = parser.load_data(str(pdf_path), extra_info=extra_info)
        text = "\n\n---\n\n".join(d.text for d in docs if d.text).strip()
        if not text or len(text) < 200:
            raise RuntimeError(f"LlamaParse returned empty result or credit limit exceeded for {pdf_path.name} (docs count: {len(docs)})")
        return text

    return llama_manager.execute_with_auto_rotate(_call)


def polish_star_asia_document(raw_text: str, meta: Dict[str, Any]) -> str:
    """Polishes raw LlamaParse markdown into publication-grade Markdown."""
    raw_pages = raw_text.split("\n\n---\n\n")

    def clean_page(p_text: str) -> str:
        t = re.sub(r"<table[^>]*>.*?</table>", lambda m: html_table_to_md(m.group(0)), p_text, flags=re.IGNORECASE | re.DOTALL)
        t = re.sub(r"!\[.*?\]\(.*?\)", "", t)
        t = re.sub(r"(?i)^\s*(?:\*\*)?STAR\s*ASIA(?:\*\*)?\s*(?:<u>)?Shipbroking\s*\([^\)]*\)(?:</u>)?\s*$", "", t, flags=re.MULTILINE)
        t = re.sub(r"(?i)^\s*(?:<u>)?Shipbroking\s*\([^\)]*\)(?:</u>)?\s*$", "", t, flags=re.MULTILINE)
        t = re.sub(r"(?i)^\s*\*(?:STAR\s*ASIA\s*)?Shipbroking\s*\([^\)]*\)\*\s*$", "", t, flags=re.MULTILINE)
        t = re.sub(r"(?i)^\s*(?:\*\*)?STAR\s*ASIA(?:\*\*)?\s*$", "", t, flags=re.MULTILINE)
        t = re.sub(r"~~+", "", t)
        t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2018", "'").replace("\u2019", "'")
        t = t.replace("\ufffd", "-")
        t = t.replace("\u20b9", "INR ")
        # Strip unicode arrows
        t = re.sub(r"[\u2190-\u21ff\u2794-\u27bf]", "", t)
        t = t.replace(r"\~", "~")
        t = re.sub(r"__+", "", t)
        t = re.sub(r"<\/?u>", "", t)
        t = re.sub(r"<\/?sup>", "", t)
        t = re.sub(r"IMPROVING\s*/\s*~*", "IMPROVING", t)
        t = re.sub(r"STABLE\s*/\s*~*", "STABLE", t)
        # Strip running footers (standalone or inline)
        t = re.sub(r"(?i)\s*snp@starasiasg\.com\s*\|\s*\+?65\s*6227\s*7264[^\n]*", "", t)
        t = re.sub(r"(?i)^\s*.*(?:star-asia\.com\.sg|Shipbroking|snp@starasiasg\.com).*$", "", t, flags=re.MULTILINE)
        t = re.sub(r"(?i)^\s*.*(?:Member of BIMCO|Singapore Shipping Association).*$", "", t, flags=re.MULTILINE)
        # Convert <br/> inside table cells to ' / '
        t = re.sub(r"(?<=\|)([^\|\n]+)(?=\|)", lambda m: m.group(0).replace("<br/>", " / ").replace("<br>", " / "), t)
        t = re.sub(r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)", lambda m: clean_markdown_table(m.group(0)), t)
        t = re.sub(r"^-{3,}$", "", t, flags=re.MULTILINE)
        return t.strip()

    pages = [clean_page(p) for p in raw_pages]

    doc_sections = []

    # Frontmatter
    wk_str = f"Week {meta['report_week']:02d}" if meta["report_week"] else "Weekly"
    doc_sections.append(f"""---
title: "Star Asia Weekly Market Report - {wk_str}, {meta['year']}"
issue_date: "{meta['issue_date']}"
report_week: {meta['report_week']}
year: {meta['year']}
publisher: "star_asia"
source_file: "{meta['source_file']}"
pages: {meta['pages']}
---

# STAR ASIA WEEKLY REPORT
**WEEK {meta['report_week']} - {meta['issue_date']}**
""")

    # 1. Executive Lead Editorial (Page 1)
    if len(pages) >= 1:
        p1 = pages[0]
        p1 = re.sub(r"(?i)#+\s*STAR\s*ASIA\s*WEEKLY\s*REPORT", "", p1)
        p1 = re.sub(r"(?i)#+\s*WEEK\s*\d+\s*-\s*[^\n]+", "", p1)
        p1 = re.sub(r"(?i)^\s*WEEK\s*\d+\s*-\s*[^\n]+$", "", p1, flags=re.MULTILINE)
        doc_sections.append("## 1. Executive Lead Editorial\n\n" + p1.strip())

    # 2. Dry Bulk Market (Pages 2-4)
    dry_bulk_content = []
    if len(pages) >= 2:
        p2 = re.sub(r"(?im)^#+\s*Dry\s*Bulk\s*$", "", pages[1]).strip()
        dry_bulk_content.append(p2)
    if len(pages) >= 3:
        p3 = pages[2].strip()
        p3 = re.sub(r"(?im)^#*\s*Handysize:\s*$", "**Handysize:**", p3)
        p3 = re.sub(r"#+\s*Baltic Exchange Dry Bulk Indices", "### Baltic Exchange Dry Bulk Indices", p3)
        p3 = re.sub(r"#+\s*Dry Bulk Values(?:\s*\(Weekly\))?", "### Dry Bulk Values (Weekly)", p3)
        p3 = re.sub(r"(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$", "", p3)
        dry_bulk_content.append(p3)
    if len(pages) >= 4:
        p4 = pages[3].strip()
        p4 = re.sub(r"#+\s*Dry\s*Bulk\s*-\s*S&P\s*Report", "### Dry Bulk - S&P Report", p4, flags=re.IGNORECASE)
        p4 = re.sub(r"#+\s*Dry Bulk 1 year T/C rates", "### Dry Bulk 1-Year T/C Rates (Quarterly Historical)", p4)
        dry_bulk_content.append(p4)
    if dry_bulk_content:
        doc_sections.append("## 2. Dry Bulk Market\n\n" + "\n\n".join(dry_bulk_content))

    # 3. Tanker Market (Pages 5-7)
    tanker_content = []
    if len(pages) >= 5:
        p5 = re.sub(r"(?im)^#+\s*Tankers\s*$", "", pages[4]).strip()
        p5 = re.sub(r"<\/?u>", "", p5)
        tanker_content.append(p5)
    if len(pages) >= 6:
        p6 = pages[5].strip()
        p6 = re.sub(r"#+\s*Baltic Exchange Tanker Indices", "### Baltic Exchange Tanker Indices", p6)
        p6 = re.sub(r"#+\s*Tankers Values(?:\s*\(Weekly\))?", "### Tankers Values (Weekly)", p6)
        p6 = re.sub(r"(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$", "", p6)
        tanker_content.append(p6)
    if len(pages) >= 7:
        p7 = pages[6].strip()
        p7 = re.sub(r"#+\s*Tankers S&P Report", "### Tankers S&P Report", p7)
        p7 = re.sub(r"#+\s*Tanker 1 year T/C rates", "### Tanker 1-Year T/C Rates (Quarterly Historical)", p7)
        tanker_content.append(p7)
    if tanker_content:
        doc_sections.append("## 3. Tanker Market\n\n" + "\n\n".join(tanker_content))

    # 4. Container Market (Pages 8-9)
    container_content = []
    if len(pages) >= 8:
        p8 = re.sub(r"(?im)^#+\s*Containers\s*$", "", pages[7]).strip()
        p8 = re.sub(r"#+\s*Containers Values(?:\s*\(Weekly\))?", "### Containers Values (Weekly)", p8)
        p8 = re.sub(r"(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$", "", p8)
        p8 = re.sub(r"\*\s*\(amount in USD million\)\s*/\s*=\s*Eco units\*", "*(amount in USD million) | (E) - eco units*", p8)
        p8 = re.sub(r"#+\s*S&P Containers Report", "### S&P Containers Report", p8)
        container_content.append(p8)
    if len(pages) >= 9:
        p9 = pages[8].strip()
        p9 = re.sub(r"#+\s*Container 6-12 months T/C rates", "### Container 6-12 Months T/C Rates (Quarterly Historical)", p9)
        container_content.append(p9)
    if container_content:
        doc_sections.append("## 4. Container Market\n\n" + "\n\n".join(container_content))

    # 5. Ship Recycling Market Intelligence (Pages 10-15)
    recycling_content = []
    if len(pages) >= 10:
        p10 = pages[9].strip()
        p10 = re.sub(r"#+\s*Ship Recycling Market Snapshot", "### Ship Recycling Market Snapshot", p10)
        p10 = re.sub(r"##\s*5-Year Ship Recycling Average Historical Prices", "### 5-Year Ship Recycling Average Historical Prices", p10)
        p10 = re.sub(r"\*\*TURKEY\*\*\s*<br\/>\*?[^\n\|]*?(?=\s*\|)", "**TURKEY**", p10, flags=re.IGNORECASE)
        recycling_content.append(p10)
    if len(pages) >= 11:
        p11 = pages[10].strip()
        p11 = re.sub(r"#+\s*Ships Sold for Recycling", "### Ships Sold for Recycling (Fixtures)", p11)
        p11 = re.sub(r"#+\s*Recycling Ships Price Trend", "### Recycling Ships Price Trend (Quarterly Historical)", p11)
        recycling_content.append(p11)
    if len(pages) >= 12:
        p12 = pages[11].strip()
        p12 = re.sub(r"#+\s*Total number of Vessel sold per month", "### Total Number of Vessels Sold Per Month", p12)
        p12 = re.sub(r"#+\s*Sub-continent total Light Displacement Tonnage in metric tons", "### Sub-Continent Total Light Displacement Tonnage (Metric Tons)", p12)
        recycling_content.append(p12)
    if len(pages) >= 13:
        p13 = pages[12].strip()
        p13 = re.sub(r"#+\s*COMPARISON OF TOTAL LIGHT DISPLACEMENT TONNAGE \(LDT\) SOLD 5 YEARS.*", "### Comparison of Total Light Displacement Tonnage (LDT) Sold 5 Years", p13)
        p13 = re.sub(r"##\s*Insights", "### Waterfront Insights & Beaching Positions", p13)
        p13 = re.sub(r"##\s*\*+Alang\*+", "#### Alang (India) Waterfront Insights & Beaching Position of the Mud", p13)
        recycling_content.append(p13)
    if len(pages) >= 14:
        p14 = pages[13].strip()
        p14 = re.sub(r"Anchorage & Beaching Position \([^\)]+\)", f"##### Anchorage & Beaching Position ({wk_str} {meta['year']}) - Alang, India", p14, count=1)
        p14 = re.sub(r"##\s*Chattogram", "#### Chattogram (Bangladesh) Waterfront Insights & Beaching Position of the Mud", p14)
        p14 = re.sub(r"Anchorage & Beaching Position \([^\)]+\)", f"##### Anchorage & Beaching Position ({wk_str} {meta['year']}) - Chattogram, Bangladesh", p14, count=1)
        recycling_content.append(p14)
    if len(pages) >= 15:
        p15 = pages[14].strip()
        p15 = re.sub(r"(?im)^#+\s*Gadani\s*$", "#### Gadani (Pakistan) Waterfront Insights & Beaching Position of the Mud", p15)
        p15 = re.sub(r"#+\s*Anchorage & Beaching Position \([^\)]+\)", f"##### Anchorage & Beaching Position ({wk_str} {meta['year']}) - Gadani, Pakistan", p15, count=1)
        p15 = re.sub(r"#+\s*Aliaga,\s*Turkiye", "#### Aliaga (Turkiye) Waterfront Insights", p15)
        # Clean Beaching Tide Dates & Bunker Prices
        p15 = re.sub(r"\|?\s*#*BEACHING TIDE DATES[^\n]*\n\|[-:\s|]+\|\n", "### Beaching Tide Dates\n\n| LOCATION | FIRST SPRING TIDE PERIOD | SECOND SPRING TIDE PERIOD |\n| --- | --- | --- |\n", p15, flags=re.IGNORECASE)
        p15 = re.sub(r"\|?\s*#*BUNKER PRICES[^\n]*\n\|[-:\s|]+\|\n", "### Bunker Prices (USD/ton)\n\n| PORTS | VLSFO (0.5%) | HSFO (3.5%) | MGO (0.1%) |\n| --- | --- | --- | --- |\n", p15, flags=re.IGNORECASE)
        recycling_content.append(p15)
    if recycling_content:
        doc_sections.append("## 5. Ship Recycling Market Intelligence\n\n" + "\n\n".join(recycling_content))

    # 6. Ferrous Scrap Market & Foreign Exchange (Pages 16-17)
    scrap_content = []
    comm_p17 = ""
    if len(pages) >= 16:
        p16 = pages[15].strip()
        # Clean Forex table and narrative
        p16_no_fx = re.sub(r"\|?\s*EXCHANGE RATES[\s\S]*?(?=\n\n|\Z)", "", p16, flags=re.IGNORECASE).strip()
        p16_no_fx = re.sub(r"#+\s*Sub-Continent and Turkey ferrous scrap markets insights", "", p16_no_fx, flags=re.IGNORECASE).strip()
        p16_no_fx = re.sub(r"^Sub-Continent and Turkey ferrous scrap markets insights\s*", "", p16_no_fx, flags=re.IGNORECASE).strip()
        scrap_content.append("### Sub-Continent and Turkey Ferrous Scrap Market Insights\n\n" + p16_no_fx)

        # Extract Forex table
        fx_match = re.search(r"(\|[^\n]*EXCHANGE RATES[\s\S]*?)(?=\n\n|\Z)", p16, flags=re.IGNORECASE)
        if fx_match:
            fx_raw = fx_match.group(1)
            fx_raw = re.sub(r"EXCHANGE RATES<br\/>CURRENCY", "CURRENCY", fx_raw, flags=re.IGNORECASE)
            fx_raw = re.sub(r"EXCHANGE RATES<br\/>", "", fx_raw, flags=re.IGNORECASE)
            scrap_content.append("### Foreign Exchange Rates\n\n" + fx_raw)

    if len(pages) >= 17:
        p17 = pages[16].strip()
        p17 = re.sub(r"#+\s*\*+Turkiye\*+", "#### Turkiye Ferrous Scrap Insights", p17)
        p17 = re.sub(r"##\s*HMS 1/2 & Tangshan", "### Sub-Continent & China Benchmark Scrap Trends", p17)
        p17 = re.sub(r"###\s*HMS 1/2 TURKEY CFR \(USD/T\)", "#### HMS 1/2 Turkey CFR (USD/T)", p17)
        p17 = re.sub(r"###\s*TANGSHAN BILLET EX-WORKS \(CNY/T\)", "#### Tangshan Billet Ex-Works (CNY/T)", p17)
        comm_split = p17.find("## **Commodities")
        if comm_split != -1:
            scrap_part = p17[:comm_split].strip()
            comm_p17 = p17[comm_split:].strip()
            scrap_content.append(scrap_part)
        else:
            scrap_content.append(p17)

    if scrap_content:
        doc_sections.append("## 6. Ferrous Scrap Market & Foreign Exchange Rates\n\n" + "\n\n".join(scrap_content))

    # 7. Commodities (Week in Focus) (Pages 17-19)
    comm_content = []
    if comm_p17:
        comm_p17 = re.sub(r"##\s*\*+Commodities\s*\(\*+Week in focus\*+\)\*+", "### Industrial Metals & Commodities Macro Commentary", comm_p17)
        comm_content.append(comm_p17)

    if len(pages) >= 18:
        p18 = pages[17].strip()
        if comm_content and comm_content[-1].rstrip().endswith(" as"):
            comm_content[-1] = comm_content[-1].rstrip() + " " + p18.lstrip()
        else:
            p18 = re.sub(r"(?m)^#*\s*~*Iron Ore~*\s*$", "### Iron Ore Spot Prices (China CNF/CFR)", p18)
            comm_content.append(p18)

    if len(pages) >= 19:
        p19 = pages[18].strip()
        p19 = re.sub(r"#+\s*Industrial Metal Rates", "### Industrial Metal Rates", p19)
        p19 = re.sub(r"#+\s*Crude Oil & Natural Gas Rates", "### Crude Oil & Natural Gas Rates", p19)
        p19 = re.sub(r"<\/?sup>", "", p19)
        note_idx = p19.find("*Note: All rates")
        if note_idx != -1:
            note_end = p19.find("\n", note_idx)
            if note_end != -1:
                p19 = p19[:note_end].strip()
            else:
                p19 = p19.strip()
        comm_content.append(p19)

    if comm_content:
        doc_sections.append("## 7. Commodities (Week in Focus)\n\n" + "\n\n".join(comm_content))

    final_md = "\n\n---\n\n".join(doc_sections).strip() + "\n"
    final_md = re.sub(r"(?i)\s*snp@starasiasg\.com\s*\|\s*\+?65\s*6227\s*7264[^\n]*", "", final_md)
    final_md = re.sub(r"(?im)^\s*.*(?:star-asia\.com\.sg|Shipbroking|snp@starasiasg\.com).*$", "", final_md)
    final_md = re.sub(r"(?im)^\s*.*(?:Member of BIMCO|Singapore Shipping Association).*$", "", final_md)
    final_md = re.sub(r"(?im)^\s*STAR\s*ASIA\s*<u>.*$", "", final_md)
    final_md = re.sub(r"(?im)^\s*\*\*STAR\s*ASIA\*\*.*$", "", final_md)
    final_md = re.sub(r"(?im)^\s*STAR\s*ASIA\s*\*+.*$", "", final_md)
    final_md = re.sub(r"\n{3,}", "\n\n", final_md)
    return final_md


def write_series_rows(csv_path: Path, headers: list, new_rows: list, key_fields: list):
    existing_rows = []
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    existing_keys = set()
    for r in existing_rows:
        k = tuple(r.get(kf, "") for kf in key_fields)
        existing_keys.add(k)

    added = 0
    for r in new_rows:
        k = tuple(r.get(kf, "") for kf in key_fields)
        if k not in existing_keys:
            existing_rows.append(r)
            existing_keys.add(k)
            added += 1

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(existing_rows)


def update_all_series(meta: Dict[str, Any], tables_sidecar: Dict[str, Any]):
    dt = meta["issue_date"]
    wk = str(meta["report_week"])
    src = meta["source_file"]

    tables = tables_sidecar.get("tables", [])

    # 1. 5-Year History
    hist_table = next((t for t in tables if any("2021" in h for h in t.get("headers", [])) and any("ALANG" in str(r) for r in t.get("rows", []))), None)
    if hist_table:
        csv_p = SERIES_DIR / "star_asia_5y_history_series.csv"
        hdrs = ["issue_date", "report_week", "destination", "year_2021", "year_2022", "year_2023", "year_2024", "year_2025", "source_file"]
        rows = []
        for r in hist_table.get("rows", []):
            dest = r.get("DESTINATION", "")
            rows.append({
                "issue_date": dt,
                "report_week": wk,
                "destination": dest,
                "year_2021": r.get("2021", ""),
                "year_2022": r.get("2022", ""),
                "year_2023": r.get("2023", ""),
                "year_2024": r.get("2024", ""),
                "year_2025": r.get("2025", ""),
                "source_file": src,
            })
        write_series_rows(csv_p, hdrs, rows, key_fields=["issue_date", "destination"])

    # 2. Iron Ore
    iron_table = next((t for t in tables if any("Iron Ore" in str(r) for r in t.get("rows", []))), None)
    if iron_table:
        csv_p = SERIES_DIR / "star_asia_iron_ore_series.csv"
        hdrs = ["issue_date", "report_week", "commodity", "grade_origin", "price_usd_mt", "change_wow_pct", "change_yoy_pct", "last_week_usd_mt", "last_year_usd_mt", "source_file"]
        rows = []
        for r in iron_table.get("rows", []):
            rows.append({
                "issue_date": dt,
                "report_week": wk,
                "commodity": r.get("COMMODITY", ""),
                "grade_origin": r.get("SIZE / GRADE", ""),
                "price_usd_mt": r.get("THIS WEEK USD / MT", ""),
                "change_wow_pct": r.get("W-O-W", ""),
                "change_yoy_pct": r.get("Y-O-Y", ""),
                "last_week_usd_mt": r.get("LAST WEEK USD / MT", ""),
                "last_year_usd_mt": r.get("LAST YEAR USD / MT", ""),
                "source_file": src,
            })
        write_series_rows(csv_p, hdrs, rows, key_fields=["issue_date", "commodity"])

    # 3. Metals & Energy
    me_rows = []
    metals_table = next((t for t in tables if any("Copper (Comex)" in str(r) for r in t.get("rows", []))), None)
    if metals_table:
        for r in metals_table.get("rows", []):
            me_rows.append({
                "issue_date": dt,
                "report_week": wk,
                "category": "Industrial Metals",
                "index_name": r.get("INDEX", ""),
                "units": r.get("UNITS", ""),
                "price": r.get("PRICE", ""),
                "change": r.get("CHANGE", ""),
                "pct_change": r.get("%CHANGE", ""),
                "contract": r.get("CONTRACT", ""),
                "source_file": src,
            })
    energy_table = next((t for t in tables if any("WTI Crude" in str(r) for r in t.get("rows", []))), None)
    if energy_table:
        for r in energy_table.get("rows", []):
            me_rows.append({
                "issue_date": dt,
                "report_week": wk,
                "category": "Energy",
                "index_name": r.get("INDEX", ""),
                "units": r.get("UNITS", ""),
                "price": r.get("PRICE", ""),
                "change": r.get("CHANGE", ""),
                "pct_change": r.get("%CHANGE", ""),
                "contract": r.get("CONTRACT", ""),
                "source_file": src,
            })
    if me_rows:
        csv_p = SERIES_DIR / "star_asia_metals_energy_series.csv"
        hdrs = ["issue_date", "report_week", "category", "index_name", "units", "price", "change", "pct_change", "contract", "source_file"]
        write_series_rows(csv_p, hdrs, me_rows, key_fields=["issue_date", "index_name"])

    # 4. Valuation Matrix (Dry, Tanker, Container)
    val_rows = []
    # Dry bulk values
    dry_val = next((t for t in tables if any("CAPE" in str(r) for r in t.get("rows", [])) and "NB CONTRACT" in t.get("headers", [])), None)
    if dry_val:
        for r in dry_val.get("rows", []):
            val_rows.append({
                "issue_date": dt, "report_week": wk, "sector": "Dry Bulk",
                "vessel_type": r.get("TYPE", ""), "size_dwt_teu": r.get("DWT", ""),
                "nb_contract_usd_m": r.get("NB CONTRACT", ""), "nb_prompt_usd_m": r.get("NB PROMPT DELIVERY", ""),
                "five_year_usd_m": r.get("5 YEARS", ""), "ten_year_usd_m": r.get("10 YEARS", ""),
                "older_year_usd_m": r.get("15 YEARS", ""), "source_file": src
            })
    # Tanker values
    tanker_val = next((t for t in tables if any("VLCC" in str(r) for r in t.get("rows", [])) and "NB CONTRACT" in t.get("headers", [])), None)
    if tanker_val:
        for r in tanker_val.get("rows", []):
            val_rows.append({
                "issue_date": dt, "report_week": wk, "sector": "Tankers",
                "vessel_type": r.get("TYPE", ""), "size_dwt_teu": r.get("DWT", ""),
                "nb_contract_usd_m": r.get("NB CONTRACT", ""), "nb_prompt_usd_m": r.get("NB PROMPT DELIVERY", ""),
                "five_year_usd_m": r.get("5 YEARS", ""), "ten_year_usd_m": r.get("10 YEARS", ""),
                "older_year_usd_m": r.get("15 YEARS", ""), "source_file": src
            })
    # Container values
    cont_val = next((t for t in tables if any("Geared" in str(r) or "Gearless" in str(r) for r in t.get("rows", []))), None)
    if cont_val:
        for r in cont_val.get("rows", []):
            val_rows.append({
                "issue_date": dt, "report_week": wk, "sector": "Containers",
                "vessel_type": r.get("GEARED / GEARLESS", ""), "size_dwt_teu": r.get("CONTAINERS (BY TEU)", ""),
                "nb_contract_usd_m": r.get("NB CONTRACT", ""), "nb_prompt_usd_m": r.get("NB PROMPT DELIVERY", ""),
                "five_year_usd_m": r.get("5 YEARS", ""), "ten_year_usd_m": r.get("10 YEARS", ""),
                "older_year_usd_m": r.get("15 YEARS", ""), "source_file": src
            })
    if val_rows:
        csv_p = SERIES_DIR / "star_asia_valuation_matrix_series.csv"
        hdrs = ["issue_date", "report_week", "sector", "vessel_type", "size_dwt_teu", "nb_contract_usd_m", "nb_prompt_usd_m", "five_year_usd_m", "ten_year_usd_m", "older_year_usd_m", "source_file"]
        write_series_rows(csv_p, hdrs, val_rows, key_fields=["issue_date", "sector", "vessel_type", "size_dwt_teu"])

    # 5. S&P Sales Series
    snp_rows = []
    for t in tables:
        hdrs = t.get("headers", [])
        if "VESSEL NAME" in hdrs and ("PRICE (MILLION) USD" in hdrs or "PRICE" in hdrs) and "BUYERS" in str(hdrs):
            for r in t.get("rows", []):
                v_name = r.get("VESSEL NAME", "")
                if not v_name or v_name == "-":
                    continue
                v_type = r.get("TYPE", r.get("SIZE", ""))
                dwt_val = r.get("DWT", r.get("TEU", ""))
                snp_rows.append({
                    "issue_date": dt, "report_week": wk, "section": "Reported Sales",
                    "vessel_name": v_name, "vessel_type": v_type, "dwt": dwt_val,
                    "year_built": r.get("YEAR", ""), "built_country": r.get("BUILT", ""),
                    "price_usd_mill": r.get("PRICE (MILLION) USD", r.get("PRICE", "")),
                    "buyers_comments": r.get("COMMENTS / BUYERS", r.get("COMMENTS", "")),
                    "source_file": src
                })
    if snp_rows:
        csv_p = SERIES_DIR / "star_asia_snp_sales_series.csv"
        hdrs = ["issue_date", "report_week", "section", "vessel_name", "vessel_type", "dwt", "year_built", "built_country", "price_usd_mill", "buyers_comments", "source_file"]
        write_series_rows(csv_p, hdrs, snp_rows, key_fields=["issue_date", "vessel_name"])


def process_report(pdf_path: Path, force: bool = False) -> bool:
    stem = pdf_path.stem
    meta = extract_metadata_from_pdf(pdf_path)
    raw_md_file = RAW_OUT_DIR / f"{stem}.md"
    out_md_file = MD_OUT_DIR / f"{stem}.md"
    out_json_file = MD_OUT_DIR / f"{stem}.tables.json"

    # Step 1: LlamaParse
    needs_parse = force or not raw_md_file.exists() or raw_md_file.stat().st_size < 200
    if needs_parse:
        print(f"[{stem}] Calling LlamaParse cost_effective tier ({meta['pages']} pages)...")
        try:
            raw_text = parse_with_llamaparse(pdf_path)
            raw_md_file.write_text(raw_text, encoding="utf-8")
        except Exception as e:
            print(f"[{stem}] LlamaParse ERROR: {e}")
            return False
    else:
        raw_text = raw_md_file.read_text(encoding="utf-8")

    # Step 2: Polish to Publication Grade
    try:
        polished_md = polish_star_asia_document(raw_text, meta)
        out_md_file.write_text(polished_md, encoding="utf-8")

        # Step 3: Structured Tables JSON Sidecar
        table_blocks = re.findall(r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)", polished_md)
        tables_sidecar = {
            "metadata": meta,
            "tables": [],
        }
        for idx, tb in enumerate(table_blocks):
            tdict = parse_md_table_to_dict(tb)
            if tdict:
                tdict["table_id"] = f"table_{idx+1:02d}"
                tables_sidecar["tables"].append(tdict)

        out_json_file.write_text(json.dumps(tables_sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

        # Step 4: Update Stacked Time Series
        try:
            update_all_series(meta, tables_sidecar)
        except Exception as e:
            print(f"[{stem}] Warning updating series: {e}")

        print(f"[{stem}] SUCCESS -> {len(polished_md)} bytes, {len(tables_sidecar['tables'])} tables.")
        return True
    except Exception as e:
        print(f"[{stem}] Polish / series update ERROR: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Star Asia World-Class Batch Extraction Pipeline")
    parser.add_argument("pdf", nargs="?", help="Path to single PDF")
    parser.add_argument("--year", type=int, help="Process all reports for a specific year (e.g. 2026)")
    parser.add_argument("--all", action="store_true", help="Process all reports across all years")
    parser.add_argument("--force", action="store_true", help="Force re-parsing with LlamaParse")
    args = parser.parse_args()

    if args.pdf:
        target = Path(args.pdf)
        process_report(target, force=args.force)
    elif args.year:
        target_dir = CORPUS_DIR / str(args.year)
        pdfs = sorted(target_dir.glob("*.pdf"))
        print(f"[{time.strftime('%H:%M:%S')}] Starting batch extraction for year {args.year} ({len(pdfs)} reports)...", flush=True)
        for i, pdf in enumerate(pdfs):
            stem = pdf.stem
            out_md_file = MD_OUT_DIR / f"{stem}.md"
            is_wc = out_md_file.exists() and out_md_file.stat().st_size > 2000 and out_md_file.read_text(encoding="utf-8", errors="ignore").startswith("---")
            if is_wc and not args.force:
                print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(pdfs)}] SKIP (already world-class): {pdf.name}", flush=True)
                continue
            print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(pdfs)}] Processing {pdf.name}...", flush=True)
            process_report(pdf, force=args.force)
    elif args.all:
        pdfs = sorted(CORPUS_DIR.glob("**/*.pdf"))
        print(f"[{time.strftime('%H:%M:%S')}] Starting full corpus batch extraction ({len(pdfs)} reports)...", flush=True)
        for i, pdf in enumerate(pdfs):
            stem = pdf.stem
            out_md_file = MD_OUT_DIR / f"{stem}.md"
            is_wc = out_md_file.exists() and out_md_file.stat().st_size > 2000 and out_md_file.read_text(encoding="utf-8", errors="ignore").startswith("---")
            if is_wc and not args.force:
                print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(pdfs)}] SKIP (already world-class): {pdf.name}", flush=True)
                continue
            print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(pdfs)}] Processing {pdf.name}...", flush=True)
            process_report(pdf, force=args.force)
    else:
        parser.print_help()
