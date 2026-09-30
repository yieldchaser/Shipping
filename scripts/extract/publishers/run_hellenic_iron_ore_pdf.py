"""MMi Daily Iron Ore Full 6-Page PDF Extraction Pipeline.

Extracts comprehensive structured data across all 6 pages of MMi Daily Iron Ore Index Reports:
- Page 1: MMi Dashboard (IOPI, IOSI, IOPLI, Futures, Freight C3/C5, Steel Rebar/HRC, Inventories)
- Page 2: Physical Port Stock & Seaborne Indices, Domestic Concentrate, Market Commentary, Multi-period Averages, Freight Rates, Spreads
- Page 3: Brand Spot Price Assessments (28 brand ratings across Port Stock 62%, Seaborne 62%, Port Stock 58%), Normalisation Differentials, 16-Port PB Fines Differentials
- Page 4: Port Inventories (Jingtang, Qingdao, Caofeidian, Tianjin, Rizhao, Total 35 Ports) & Futures Contracts (DCE, SGX)
- Page 5: Chinese Steel Spot Market Prices (7 products) & Steel Mill Profitability Tracking (Costs & Margins)
- Page 6: Index Specifications, Brand Fe/Al/Si/P/Moisture Specs, Bloomberg Tickers

Produces:
- data/extracted/md/hellenic/iron_ore_pdf/<year>/<stem>.md
- data/extracted/md/hellenic/iron_ore_pdf/<year>/<stem>.tables.json
- data/extracted/series/hellenic_iron_ore_pdf_dashboard_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_indices_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_brands_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_domestic_concentrate_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_port_differentials_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_port_inventories_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_futures_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_steel_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_steel_mill_pnl_series.csv
"""

from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pymupdf
from bs4 import BeautifulSoup
from llama_parse import LlamaParse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.extract.llama_manager import manager as key_manager

CACHE_DIR = ROOT / "data" / "extracted" / "cache_mmi_iron_ore_pdf"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "iron_ore_pdf"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
PDF_CORPUS_DIR = ROOT / "corpus" / "02-hellenic" / "iron_ore" / "pdfs"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)

CHINESE_PORTS = [
    "Bayuquan", "Fangcheng", "Lanshan", "Rizhao", "Beilun", "Jiangyin",
    "Lianyungang", "Shekou", "Caofeidian", "Jingtang", "Majishan",
    "Taicang", "Dalian", "Lanqiao", "Qingdao", "Tianjin"
]

KNOWN_BRANDS_62 = [
    "Roy Hill", "SIMEC Fines", "PB Fines", "Newman Fines", "MAC Fines",
    "Jimblebar Blended Fines", "Carajas Fines", "Brazilian SSF",
    "Brazilian Blend Fines", "RTX Fines", "West Pilbara Fines"
]

KNOWN_BRANDS_58 = [
    "SSF", "FMG Blended Fines", "Robe River", "Western Fines",
    "Atlas Fines", "Yandi"
]

KNOWN_STEEL_PRODUCTS = [
    ("ReBar HRB400", "ReBar HRB400 phi18mm"),
    ("Wirerod Q300", "Wirerod Q300 phi6.5mm"),
    ("HRC Q235", "HRC Q235/SS400 5.5mm*1500*C"),
    ("CRC SPCC", "CRC SPCC/ST12 1.0mm*1250*2500"),
    ("Plate Q235B", "Medium & Heavy Plate Q235B 20mm"),
    ("GI ST02Z", "GI ST02Z 1.0mm*1000*C"),
    ("Colour Coated Plate", "Colour Coated Plate")
]


def clean_num(val_str: Any) -> Optional[float]:
    """Parse numeric float from string, handling currencies, commas, parentheses, bolding, and percentage signs."""
    if val_str is None:
        return None
    s = str(val_str).strip()
    s = s.replace("~~", "").replace("*", "").replace("<b>", "").replace("</b>", "").replace("<s>", "").replace("</s>", "").replace("<u>", "").replace("</u>", "").replace("<i>", "").replace("</i>", "")
    s = s.replace(",", "").replace("$", "").replace("%", "").strip()
    if not s or s in ("-", "--", "N/A", "NA", "nan", "HOLIDAY"):
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def clean_cell_text(s: str) -> str:
    """Normalize text cell, removing strikethroughs, bold asterisks, trailing backslashes, and mojibake."""
    if not s:
        return ""
    s = s.replace("~~", "").replace("*", "").replace("<b>", "").replace("</b>", "").replace("<s>", "").replace("</s>", "").replace("<u>", "").replace("</u>", "").replace("<i>", "").replace("</i>", "").strip()
    s = s.replace("\ufffd", "'").replace("`", "'")
    s = s.replace("<br/>", " ").replace("<br>", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fix_unclosed_table_tags(html: str) -> str:
    """Close unclosed <td> and <th> tags often emitted by OCR parsers."""
    html = re.sub(r'(<td[^>]*>[^<]*)(?=<td|<\/tr>)', r'\1</td>', html, flags=re.I)
    html = re.sub(r'(<th[^>]*>[^<]*)(?=<th|<\/tr>)', r'\1</th>', html, flags=re.I)
    return html


def parse_change_and_pct(val_str: Any) -> Tuple[Optional[float], Optional[float]]:
    """Parse cell that may contain both Change and Change % like '15.50 1.55%' or single values."""
    if not val_str:
        return None, None
    s = clean_cell_text(str(val_str))
    parts = s.split()
    if len(parts) >= 2:
        c = clean_num(parts[0])
        cp = clean_num(parts[1])
        return c, cp
    elif len(parts) == 1:
        if "%" in parts[0]:
            return None, clean_num(parts[0])
        else:
            return clean_num(parts[0]), None
    return None, None


def html_table_to_markdown(html: str) -> str:
    """Convert an HTML <table> element into a clean GitHub-flavored markdown pipe table."""
    html = fix_unclosed_table_tags(html)
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    
    headers = []
    thead = soup.find("thead")
    if thead:
        th_tags = thead.find_all("th")
        if th_tags:
            headers = [clean_cell_text(th.get_text()) for th in th_tags]
    
    tbody = soup.find("tbody") or soup
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row_vals = [clean_cell_text(c.get_text()) for c in cells]
        if not headers and all(c.name == "th" for c in cells):
            headers = row_vals
            continue
        rows.append(row_vals)
    
    if not rows and not headers:
        return ""
        
    max_cols = max(len(headers) if headers else 0, max(len(r) for r in rows) if rows else 0)
    if max_cols == 0:
        return ""
        
    if not headers:
        headers = [f"Col {j+1}" for j in range(max_cols)]
    else:
        while len(headers) < max_cols:
            headers.append("")
            
    padded_rows = []
    for r in rows:
        r_pad = list(r)
        while len(r_pad) < max_cols:
            r_pad.append("")
        padded_rows.append(r_pad[:max_cols])
        
    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * max_cols) + " |"
    ]
    for r in padded_rows:
        md_lines.append("| " + " | ".join(r) + " |")
        
    return "\n".join(md_lines) + "\n\n"


def convert_html_tables_in_text(text: str) -> str:
    """Find all <table>...</table> in markdown text and convert to pipe tables."""
    def replacer(match):
        html_code = match.group(0)
        md = html_table_to_markdown(html_code)
        return md if md else html_code
        
    return re.sub(r"<table.*?</table>", replacer, text, flags=re.DOTALL)


def extract_date_from_filename(filename: str) -> Tuple[str, str]:
    """Extract standard ISO date (YYYY-MM-DD) and Year string from report filename."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m:
        return m.group(0), m.group(1)
    return "unknown", "unknown"


async def get_or_parse_mmi_pdf(pdf_path: Path, sem: asyncio.Semaphore) -> str:
    """Retrieve cached LlamaParse markdown or parse the 6-page PDF asynchronously."""
    stem = pdf_path.stem
    cache_file = CACHE_DIR / f"{stem}.md"
    if cache_file.exists() and cache_file.stat().st_size > 500:
        return cache_file.read_text(encoding="utf-8")

    async with sem:
        for attempt in range(4):
            current_key = key_manager.get_current_key()
            parser = LlamaParse(
                api_key=current_key,
                result_type="markdown",
                tier="cost_effective",
                version="latest",
                verbose=False
            )
            try:
                docs = await parser.aload_data(str(pdf_path.resolve()))
                full_md = "\n\n---\n\n".join(d.text for d in docs)
                cache_file.write_text(full_md, encoding="utf-8")
                key_manager.record_success(num_pages=len(docs), used_key=current_key)
                return full_md
            except Exception as e:
                err_msg = str(e).lower()
                if "rate limit" in err_msg or "429" in err_msg or "quota" in err_msg or "payment" in err_msg or "credit" in err_msg:
                    print(f"  [LlamaParse] Key exhausted/rate-limited on {pdf_path.name}: {e}. Rotating...", flush=True)
                    key_manager.mark_key_exhausted(reason=err_msg, failed_key=current_key)
                    await asyncio.sleep(2)
                else:
                    print(f"  [LlamaParse] Error parsing {pdf_path.name}: {e}", flush=True)
                    raise e
        raise RuntimeError(f"Failed to parse {pdf_path.name} after 4 key rotation attempts.")


def parse_page1_dashboard(page1_text: str, issue_date: str) -> Dict[str, Any]:
    """Parse Page 1 core MMi dashboard indicators."""
    dash: Dict[str, Any] = {
        "issue_date": issue_date,
        "iopi62_61_price": None,
        "iopi62_61_chg": None,
        "iopi62_61_chg_pct": None,
        "iopi65_price": None,
        "iopi65_chg": None,
        "iopi65_chg_pct": None,
        "iopi58_price": None,
        "iopi58_chg": None,
        "iopi58_chg_pct": None,
        "iosi62_61_price": None,
        "iosi62_61_chg": None,
        "iosi62_61_chg_pct": None,
        "iosi65_price": None,
        "iosi65_chg": None,
        "iosi65_chg_pct": None,
        "iopli_lump_price": None,
        "iopli_lump_chg": None,
        "iopli_lump_chg_pct": None,
        "dce_iron_ore_price": None,
        "dce_iron_ore_chg": None,
        "dce_iron_ore_chg_pct": None,
        "sgx_iron_ore_price": None,
        "sgx_iron_ore_chg": None,
        "sgx_iron_ore_chg_pct": None,
        "shfe_rebar_price": None,
        "shfe_rebar_chg": None,
        "shfe_rebar_chg_pct": None,
        "c3_tubarao_price": None,
        "c5_waust_price": None,
        "steel_rebar_price": None,
        "steel_rebar_chg": None,
        "steel_rebar_chg_pct": None,
        "steel_hrc_price": None,
        "steel_hrc_chg": None,
        "steel_hrc_chg_pct": None,
        "port_iron_ore_inventory_mt": None,
        "port_iron_ore_inventory_chg_mt": None,
        "port_iron_ore_inventory_chg_pct": None,
        "steel_inventory_china_mt": None,
        "steel_inventory_china_chg_mt": None,
    }

    clean_p1 = convert_html_tables_in_text(page1_text).replace("~~", "").replace("*", "")
    
    for line in clean_p1.splitlines():
        if not line.startswith("|") or "Indicator" in line or "---" in line or "Index" in line or "Item" in line:
            continue
        parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
        if len(parts) < 2:
            continue
        ind = parts[0].upper()
        norm_ind = re.sub(r"\s+", "", ind)
        
        val = clean_num(parts[1]) if len(parts) > 1 else None
        
        # Determine change and change %
        chg = None
        chg_pct = None
        if len(parts) > 3 and clean_num(parts[2]) is not None and clean_num(parts[3]) is not None:
            chg = clean_num(parts[2])
            chg_pct = clean_num(parts[3])
        elif len(parts) > 2:
            c, cp = parse_change_and_pct(parts[2])
            chg = c
            chg_pct = cp
            if chg is None and len(parts) > 3:
                chg = clean_num(parts[2])
                chg_pct = clean_num(parts[3])
        
        if re.search(r"IOP[I1]6[12]", norm_ind) or ("PORTSTOCK" in norm_ind and ("61%" in norm_ind or "62%" in norm_ind)):
            dash["iopi62_61_price"] = val
            dash["iopi62_61_chg"] = chg
            dash["iopi62_61_chg_pct"] = chg_pct
        elif re.search(r"IOP[I1]65", norm_ind) or ("PORTSTOCK" in norm_ind and "65%" in norm_ind):
            dash["iopi65_price"] = val
            dash["iopi65_chg"] = chg
            dash["iopi65_chg_pct"] = chg_pct
        elif re.search(r"IOP[I1]58", norm_ind) or ("PORTSTOCK" in norm_ind and "58%" in norm_ind):
            dash["iopi58_price"] = val
            dash["iopi58_chg"] = chg
            dash["iopi58_chg_pct"] = chg_pct
        elif re.search(r"IOS[I1]6[12]", norm_ind) or ("SEABORNE" in norm_ind and ("61%" in norm_ind or "62%" in norm_ind)):
            dash["iosi62_61_price"] = val
            dash["iosi62_61_chg"] = chg
            dash["iosi62_61_chg_pct"] = chg_pct
        elif re.search(r"IOS[I1]65", norm_ind) or ("SEABORNE" in norm_ind and "65%" in norm_ind):
            dash["iosi65_price"] = val
            dash["iosi65_chg"] = chg
            dash["iosi65_chg_pct"] = chg_pct
        elif re.search(r"IOPL[I1]", norm_ind) or "LUMP" in norm_ind:
            dash["iopli_lump_price"] = val
            dash["iopli_lump_chg"] = chg
            dash["iopli_lump_chg_pct"] = chg_pct
        elif "DCEIRONORE" in norm_ind:
            dash["dce_iron_ore_price"] = val
            dash["dce_iron_ore_chg"] = chg
            dash["dce_iron_ore_chg_pct"] = chg_pct
        elif "SGXIRONORE" in norm_ind:
            dash["sgx_iron_ore_price"] = val
            dash["sgx_iron_ore_chg"] = chg
            dash["sgx_iron_ore_chg_pct"] = chg_pct
        elif "SHFEREBAR" in norm_ind:
            dash["shfe_rebar_price"] = val
            dash["shfe_rebar_chg"] = chg
            dash["shfe_rebar_chg_pct"] = chg_pct
        elif "C3" in norm_ind and "TUBARAO" in norm_ind:
            dash["c3_tubarao_price"] = val if val is not None else parts[1]
        elif "C5" in norm_ind and ("AUSTRALIA" in norm_ind or "WAUST" in norm_ind):
            dash["c5_waust_price"] = val if val is not None else parts[1]
        elif "STEELREBAR" in norm_ind:
            dash["steel_rebar_price"] = val
            dash["steel_rebar_chg"] = chg
            dash["steel_rebar_chg_pct"] = chg_pct
        elif "STEELHRC" in norm_ind:
            dash["steel_hrc_price"] = val
            dash["steel_hrc_chg"] = chg
            dash["steel_hrc_chg_pct"] = chg_pct
        elif "PORT" in norm_ind and "INVENTORY" in norm_ind:
            dash["port_iron_ore_inventory_mt"] = val
            dash["port_iron_ore_inventory_chg_mt"] = chg
            dash["port_iron_ore_inventory_chg_pct"] = chg_pct
        elif "STEELINVENTORY" in norm_ind:
            dash["steel_inventory_china_mt"] = val
            dash["steel_inventory_china_chg_mt"] = chg

    return dash


def extract_commentary_from_page2(page2_text: str, pdf_path: Optional[Path] = None) -> str:
    """Extract clean editorial prose commentary from Page 2 with PyMuPDF vector layer fallback."""
    m = re.search(r"MARKET\s*COMMENTARY\s*</th>\s*</tr>\s*<tr>\s*<th[^>]*>.*?</th>\s*<td[^>]*>(.*?)</td>", page2_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw_comm = m.group(1).strip()
        lines = [clean_cell_text(l) for l in raw_comm.splitlines() if not l.strip().startswith("|") and len(l.strip()) > 0]
        cleaned = "\n\n".join(lines)
        if len(cleaned) > 50:
            return cleaned
    
    m2 = re.search(r"##\s*MARKET\s*COMMENTARY\s*\n(.*?)(?=\n##|\Z)", page2_text, re.DOTALL | re.IGNORECASE)
    if m2:
        raw_comm = m2.group(1).strip()
        lines = [clean_cell_text(l) for l in raw_comm.splitlines() if not l.strip().startswith("|") and len(l.strip()) > 0]
        cleaned = "\n\n".join(lines)
        if len(cleaned) > 50:
            return cleaned

    # PyMuPDF vector text fallback (resolves cases where commentary was placed inside an empty table cell)
    if pdf_path and pdf_path.exists():
        try:
            doc = pymupdf.open(pdf_path)
            if len(doc) > 1:
                t = doc[1].get_text()
                LIGATURE_MAP = {
                    "\u019f": "ti", "\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff",
                    "\u2013": "-", "\u2014": "--", "\u2018": "'", "\u2019": "'",
                    "\u201c": '"', "\u201d": '"'
                }
                for k, v in LIGATURE_MAP.items():
                    t = t.replace(k, v)
                idx = t.find("MARKET COMMENTARY")
                if idx != -1:
                    idx_end = t.find("WEEKLY AVERAGE", idx)
                    if idx_end == -1: idx_end = t.find("MONTHLY AVERAGE", idx)
                    if idx_end == -1: idx_end = t.find("INDEX", idx + 50)
                    comm_block = t[idx:idx_end] if idx_end != -1 else t[idx:idx+2500]
                    lines = [l.strip() for l in comm_block.splitlines() if l.strip() and "MARKET COMMENTARY" not in l]
                    cleaned_comm = " ".join(lines)
                    if len(cleaned_comm) > 50:
                        return cleaned_comm
        except Exception:
            pass
    return ""


def parse_page2(page2_text: str, issue_date: str, pdf_path: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Parse Page 2 detailed benchmark indices, domestic concentrates, freight rates, spreads, multi-period averages, and commentary."""
    commentary = extract_commentary_from_page2(page2_text, pdf_path)
    indices: List[Dict[str, Any]] = []
    concentrates: List[Dict[str, Any]] = []
    freight: List[Dict[str, Any]] = []
    spreads: List[Dict[str, Any]] = []
    averages: List[Dict[str, Any]] = []
    
    p2_fixed = fix_unclosed_table_tags(page2_text)
    soup = BeautifulSoup(p2_fixed, "html.parser")
    all_rows = []
    for tr in soup.find_all("tr"):
        tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
        if tds:
            all_rows.append(tds)
            
    for line in page2_text.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [clean_cell_text(c) for c in line.split("|")[1:-1]]
        if cells:
            all_rows.append(cells)

    seen_indices = set()
    seen_concentrates = set()
    seen_freight = set()

    def add_idx(name: str, mkt: str, fe: str, unit: str, p: Any, c: Any, cp: Any, mtd: Any, ytd: Any, low: Any, high: Any):
        key = (name, mkt)
        if key not in seen_indices and p is not None:
            seen_indices.add(key)
            indices.append({
                "date": issue_date, "index_name": name, "market": mkt, "fe_content": fe, "unit": unit,
                "price": p, "change": c, "change_pct": cp, "mtd": mtd, "ytd": ytd, "low_52w": low, "high_52w": high
            })

    for tds in all_rows:
        if not tds:
            continue
        first_col = tds[0].upper()
        norm_first = re.sub(r"\s+", "", first_col)
        
        # IOPI rows
        if re.search(r"^IOP[I1]6[12]$", norm_first):
            if len(tds) >= 15:
                add_idx("IOPI62_61", "Port Stock FOT Qingdao", "62% Fe Fines", "RMB/wet tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]))
                add_idx("IOPI62_61_CFR_EQ", "CFR Qingdao Equivalent", "62% Fe Fines", "USD/dry tonne",
                        clean_num(tds[9]), clean_num(tds[10]), clean_num(tds[11]), clean_num(tds[12]), clean_num(tds[13]), clean_num(tds[14]), clean_num(tds[15]) if len(tds) > 15 else None)
        elif re.search(r"^IOP[I1]58$", norm_first):
            if len(tds) >= 15:
                add_idx("IOPI58", "Port Stock FOT Qingdao", "58% Fe Fines", "RMB/wet tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]))
                add_idx("IOPI58_CFR_EQ", "CFR Qingdao Equivalent", "58% Fe Fines", "USD/dry tonne",
                        clean_num(tds[9]), clean_num(tds[10]), clean_num(tds[11]), clean_num(tds[12]), clean_num(tds[13]), clean_num(tds[14]), clean_num(tds[15]) if len(tds) > 15 else None)
        elif re.search(r"^IOP[I1]65$", norm_first):
            if len(tds) >= 15:
                add_idx("IOPI65", "Port Stock FOT Qingdao", "65% Fe Fines", "RMB/wet tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]))
                add_idx("IOPI65_CFR_EQ", "CFR Qingdao Equivalent", "65% Fe Fines", "USD/dry tonne",
                        clean_num(tds[9]), clean_num(tds[10]), clean_num(tds[11]), clean_num(tds[12]), clean_num(tds[13]), clean_num(tds[14]), clean_num(tds[15]) if len(tds) > 15 else None)
        elif re.search(r"^IOS[I1]6[12]$", norm_first):
            if len(tds) >= 8:
                add_idx("IOSI62_61", "Seaborne CFR Qingdao", "62% Fe Fines", "USD/dry tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]) if len(tds) > 8 else None)
        elif re.search(r"^IOS[I1]65$", norm_first):
            if len(tds) >= 8:
                add_idx("IOSI65", "Seaborne CFR Qingdao", "65% Fe Fines", "USD/dry tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]) if len(tds) > 8 else None)
        elif re.search(r"^IOPL[I1]", norm_first):
            if len(tds) >= 15:
                add_idx("IOPLI62", "Port Lump FOT Qingdao", "62.5% Fe Lump", "RMB/wet tonne",
                        clean_num(tds[2]), clean_num(tds[3]), clean_num(tds[4]), clean_num(tds[5]), clean_num(tds[6]), clean_num(tds[7]), clean_num(tds[8]))
                add_idx("IOPLI62_CFR_EQ", "CFR Qingdao Equivalent", "62.5% Fe Lump", "USD/dry tonne",
                        clean_num(tds[9]), clean_num(tds[10]), clean_num(tds[11]), clean_num(tds[12]), clean_num(tds[13]), clean_num(tds[14]), clean_num(tds[15]) if len(tds) > 15 else None)

        # Domestic Concentrates (Hanxing, Qian'an, Anshan, Zibo)
        top_cols = [clean_cell_text(td).upper() for td in tds[:4]]
        if len(tds) >= 8 and any(reg in " ".join(top_cols) for reg in ["HANXING", "QIAN'AN", "ANSHAN", "ZIBO"]):
            reg = tds[1] if len(tds) > 1 else ""
            if reg not in seen_concentrates:
                seen_concentrates.add(reg)
                concentrates.append({
                    "date": issue_date,
                    "province": tds[0],
                    "region": reg,
                    "product": tds[2] if len(tds) > 2 else "",
                    "basis": tds[3] if len(tds) > 3 else "",
                    "price_rmb_t": clean_num(tds[4]),
                    "change_pct_rmb": clean_num(tds[5]),
                    "low_rmb_t": clean_num(tds[6]),
                    "high_rmb_t": clean_num(tds[7]),
                    "price_usd_t": clean_num(tds[8]) if len(tds) > 8 else None,
                    "change_pct_usd": clean_num(tds[9]) if len(tds) > 9 else None,
                    "low_usd_t": clean_num(tds[10]) if len(tds) > 10 else None,
                    "high_usd_t": clean_num(tds[11]) if len(tds) > 11 else None
                })
        elif "CHINA MINES CONCENTRATE COMPOSITE" in first_col:
            if "Composite" not in seen_concentrates:
                seen_concentrates.add("Composite")
                concentrates.append({
                    "date": issue_date,
                    "province": "National",
                    "region": "Composite",
                    "product": "China Mines Concentrate Composite Index",
                    "basis": "RMB/WT",
                    "price_rmb_t": clean_num(tds[1]) if len(tds) > 1 else None,
                    "change_pct_rmb": clean_num(tds[2]) if len(tds) > 2 else None,
                    "low_rmb_t": clean_num(tds[3]) if len(tds) > 3 else None,
                    "high_rmb_t": clean_num(tds[4]) if len(tds) > 4 else None,
                    "price_usd_t": None, "change_pct_usd": None, "low_usd_t": None, "high_usd_t": None
                })

        # Freight Rates table
        if "AUSTRALIA" in first_col and ("C5" in first_col or (len(tds) > 1 and "C5" in tds[1])):
            if "C5" not in seen_freight:
                seen_freight.add("C5")
                freight.append({
                    "date": issue_date, "route": "C5, W. Australia - Qingdao",
                    "rate_usd_t": clean_num(tds[2]) if len(tds) > 2 else None,
                    "change": clean_num(tds[3]) if len(tds) > 3 else None,
                    "change_pct": clean_num(tds[4]) if len(tds) > 4 else None,
                    "low_52w": clean_num(tds[5]) if len(tds) > 5 else None,
                    "high_52w": clean_num(tds[6]) if len(tds) > 6 else None
                })
        elif "TUBARAO" in first_col and ("C3" in first_col or (len(tds) > 1 and "C3" in tds[1])):
            if "C3" not in seen_freight:
                seen_freight.add("C3")
                freight.append({
                    "date": issue_date, "route": "C3, Tubarao - Qingdao",
                    "rate_usd_t": clean_num(tds[2]) if len(tds) > 2 else None,
                    "change": clean_num(tds[3]) if len(tds) > 3 else None,
                    "change_pct": clean_num(tds[4]) if len(tds) > 4 else None,
                    "low_52w": clean_num(tds[5]) if len(tds) > 5 else None,
                    "high_52w": clean_num(tds[6]) if len(tds) > 6 else None
                })

    # Spreads / Premiums & Discounts Table (HTML + Pipe support)
    idx_sp = page2_text.find("PREMIUMS/DISCOUNTS")
    if idx_sp != -1:
        block_sp = page2_text[idx_sp:idx_sp+2000]
        soup_sp = BeautifulSoup(block_sp, "html.parser")
        for tr in soup_sp.find_all("tr"):
            tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
            idx0 = tds[0].upper().replace(" ", "").replace("*", "") if len(tds) > 0 else ""
            idx4 = tds[4].upper().replace(" ", "").replace("*", "") if len(tds) > 4 else ""
            if len(tds) >= 4 and idx0 in ["IOPI58", "IOPI65"]:
                spreads.append({
                    "date": issue_date, "index_name": idx0, "fe_content": tds[1], "market_type": "Port Stock",
                    "spread_to_benchmark": clean_num(tds[2]), "spread_pct": clean_num(tds[3]), "benchmark_index": "IOPI62"
                })
            if len(tds) >= 8 and idx4 in ["IOSI65"]:
                spreads.append({
                    "date": issue_date, "index_name": idx4, "fe_content": tds[5], "market_type": "Seaborne",
                    "spread_to_benchmark": clean_num(tds[6]), "spread_pct": clean_num(tds[7]), "benchmark_index": "IOSI62"
                })
        if not spreads:
            for line in block_sp.splitlines():
                if not line.startswith("|") or "---" in line:
                    continue
                parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
                idx0 = parts[0].upper().replace(" ", "").replace("*", "") if len(parts) > 0 else ""
                idx4 = parts[4].upper().replace(" ", "").replace("*", "") if len(parts) > 4 else ""
                if len(parts) >= 4 and idx0 in ["IOPI58", "IOPI65"]:
                    spreads.append({
                        "date": issue_date, "index_name": idx0, "fe_content": parts[1], "market_type": "Port Stock",
                        "spread_to_benchmark": clean_num(parts[2]), "spread_pct": clean_num(parts[3]), "benchmark_index": "IOPI62"
                    })
                if len(parts) >= 8 and idx4 in ["IOSI65"]:
                    spreads.append({
                        "date": issue_date, "index_name": idx4, "fe_content": parts[5], "market_type": "Seaborne",
                        "spread_to_benchmark": clean_num(parts[6]), "spread_pct": clean_num(parts[7]), "benchmark_index": "IOSI62"
                    })

    # Multi-period Monthly, Quarterly & YTD Averages (HTML + Pipe support)
    idx_avg = page2_text.find("INDEX MONTHLY, QUARTERLY AND YEAR-TO-DATE AVERAGES")
    if idx_avg != -1:
        block_avg = page2_text[idx_avg:]
        avg_rows = []
        soup_avg = BeautifulSoup(block_avg, "html.parser")
        for tr in soup_avg.find_all("tr"):
            tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
            if tds: avg_rows.append(tds)
        for line in block_avg.splitlines():
            if line.startswith("|") and "---" not in line:
                parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
                if parts: avg_rows.append(parts)
                
        seen_avg = set()
        for r in avg_rows:
            idx_name = None
            start_i = -1
            for i, c in enumerate(r):
                c_clean = c.upper().replace(" ", "").replace("*", "")
                if c_clean in ["IOPI62", "IOPI58", "IOPI65", "IOSI62", "IOSI65", "IOPLI62"]:
                    idx_name = c_clean
                    start_i = i
                    break
            if idx_name and start_i != -1:
                tail = r[start_i:]
                fe = tail[1] if len(tail) > 1 else ""
                if (idx_name.startswith("IOPI") or idx_name.startswith("IOPLI")) and len(tail) >= 16:
                    key1 = (idx_name, "Port Stock")
                    if key1 not in seen_avg:
                        seen_avg.add(key1)
                        averages.append({
                            "date": issue_date, "index_name": idx_name, "market_type": "Port Stock", "fe_content": fe, "unit": "RMB/wet tonne",
                            "m_minus_4": clean_num(tail[2]), "m_minus_3": clean_num(tail[3]), "m_minus_2": clean_num(tail[4]), "m_minus_1": clean_num(tail[5]),
                            "mtd": clean_num(tail[6]), "qtd": clean_num(tail[7]), "ytd": clean_num(tail[8])
                        })
                    key2 = (idx_name + "_CFR_EQ", "CFR Qingdao Eq")
                    if key2 not in seen_avg:
                        seen_avg.add(key2)
                        averages.append({
                            "date": issue_date, "index_name": idx_name + "_CFR_EQ", "market_type": "CFR Qingdao Eq", "fe_content": fe, "unit": "USD/dry tonne",
                            "m_minus_4": clean_num(tail[9]), "m_minus_3": clean_num(tail[10]), "m_minus_2": clean_num(tail[11]), "m_minus_1": clean_num(tail[12]),
                            "mtd": clean_num(tail[13]), "qtd": clean_num(tail[14]), "ytd": clean_num(tail[15])
                        })
                elif (idx_name.startswith("IOPI") or idx_name.startswith("IOPLI")) and len(tail) >= 9:
                    key1 = (idx_name, "Port Stock")
                    if key1 not in seen_avg:
                        seen_avg.add(key1)
                        averages.append({
                            "date": issue_date, "index_name": idx_name, "market_type": "Port Stock", "fe_content": fe, "unit": "RMB/wet tonne",
                            "m_minus_4": clean_num(tail[2]), "m_minus_3": clean_num(tail[3]), "m_minus_2": clean_num(tail[4]), "m_minus_1": clean_num(tail[5]),
                            "mtd": clean_num(tail[6]), "qtd": clean_num(tail[7]), "ytd": clean_num(tail[8])
                        })
                elif idx_name.startswith("IOSI") and len(tail) >= 9:
                    key3 = (idx_name, "Seaborne")
                    if key3 not in seen_avg:
                        seen_avg.add(key3)
                        averages.append({
                            "date": issue_date, "index_name": idx_name, "market_type": "Seaborne", "fe_content": fe, "unit": "USD/dry tonne",
                            "m_minus_4": clean_num(tail[2]), "m_minus_3": clean_num(tail[3]), "m_minus_2": clean_num(tail[4]), "m_minus_1": clean_num(tail[5]),
                            "mtd": clean_num(tail[6]), "qtd": clean_num(tail[7]), "ytd": clean_num(tail[8])
                        })

        # Separate block check for Seaborne Averages if further down
        idx_sea = page2_text.find("SEABORNE INDEX MONTHLY")
        if idx_sea != -1:
            sea_block = page2_text[idx_sea:idx_sea+2500]
            sea_rows = []
            soup_s = BeautifulSoup(sea_block, "html.parser")
            for tr in soup_s.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if tds: sea_rows.append(tds)
            for line in sea_block.splitlines():
                if line.startswith("|") and "---" not in line:
                    parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
                    if parts: sea_rows.append(parts)
            for r in sea_rows:
                for i, c in enumerate(r):
                    c_clean = c.upper().replace(" ", "").replace("*", "")
                    if c_clean in ["IOSI62", "IOSI65"]:
                        tail = r[i:]
                        if len(tail) >= 9:
                            key3 = (c_clean, "Seaborne")
                            if key3 not in seen_avg:
                                seen_avg.add(key3)
                                averages.append({
                                    "date": issue_date, "index_name": c_clean, "market_type": "Seaborne", "fe_content": tail[1], "unit": "USD/dry tonne",
                                    "m_minus_4": clean_num(tail[2]), "m_minus_3": clean_num(tail[3]), "m_minus_2": clean_num(tail[4]), "m_minus_1": clean_num(tail[5]),
                                    "mtd": clean_num(tail[6]), "qtd": clean_num(tail[7]), "ytd": clean_num(tail[8])
                                })
                        break

    return indices, concentrates, freight, spreads, averages, commentary


def parse_page3(page3_text: str, issue_date: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse Page 3 Brand Spot Price Assessments, Normalisation Differentials, Port Differentials, and Comparisons Chart."""
    brands: List[Dict[str, Any]] = []
    normalisations: List[Dict[str, Any]] = []
    port_diffs: List[Dict[str, Any]] = []
    comparisons_chart: List[Dict[str, Any]] = []
    
    p3_fixed = fix_unclosed_table_tags(page3_text)
    soup = BeautifulSoup(p3_fixed, "html.parser")
    
    # 1. Brands Table (HTML format: 62% and 58% brands)
    for table in soup.find_all("table"):
        txt = table.get_text()
        if "PORT STOCK INDEX" in txt and ("Diff to IOPI" in txt or "Diff to IOPi" in txt or "Roy Hill" in txt or "SSF" in txt):
            for tr in table.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 4:
                    b1 = tds[0]
                    p1 = clean_num(tds[1])
                    c1 = clean_num(tds[2])
                    d1 = clean_num(tds[3])
                    if b1 in KNOWN_BRANDS_62 and p1 is not None and b1 not in [x["brand"] for x in brands if x["market_type"] == "Port Stock FOT Qingdao"]:
                        brands.append({
                            "date": issue_date,
                            "market_type": "Port Stock FOT Qingdao",
                            "benchmark_grade": "62% Fe Benchmark",
                            "brand": b1,
                            "price": p1,
                            "unit": "RMB/wmt",
                            "change": c1,
                            "diff_to_benchmark": d1
                        })
                    elif b1 in KNOWN_BRANDS_58 and p1 is not None and b1 not in [x["brand"] for x in brands if x["benchmark_grade"] == "58% Fe Benchmark"]:
                        brands.append({
                            "date": issue_date,
                            "market_type": "Port Stock FOT Qingdao",
                            "benchmark_grade": "58% Fe Benchmark",
                            "brand": b1,
                            "price": p1,
                            "unit": "RMB/wmt",
                            "change": c1,
                            "diff_to_benchmark": d1
                        })
                if len(tds) >= 8:
                    b2 = tds[4]
                    p2 = clean_num(tds[5])
                    c2 = clean_num(tds[6])
                    d2 = clean_num(tds[7])
                    if b2 in KNOWN_BRANDS_62 and p2 is not None and b2 not in [x["brand"] for x in brands if x["market_type"] == "Seaborne CFR Qingdao"]:
                        brands.append({
                            "date": issue_date,
                            "market_type": "Seaborne CFR Qingdao",
                            "benchmark_grade": "62% Fe Benchmark",
                            "brand": b2,
                            "price": p2,
                            "unit": "USD/dmt",
                            "change": c2,
                            "diff_to_benchmark": d2
                        })

    # 2. Brands Table (Pipe format: 62% and 58% brands)
    for line in page3_text.splitlines():
        if not line.startswith("|") or "---" in line or "PORT STOCK" in line or "Applicable" in line:
            continue
        clean_l = re.sub(r"<br\s*/?>", " ", line, flags=re.I)
        parts = [clean_cell_text(p) for p in clean_l.split("|")[1:-1]]
        if len(parts) >= 4:
            b1 = parts[0]
            p1 = clean_num(parts[1])
            c1 = clean_num(parts[2])
            d1 = clean_num(parts[3])
            if b1 in KNOWN_BRANDS_62 and p1 is not None and b1 not in [x["brand"] for x in brands if x["market_type"] == "Port Stock FOT Qingdao"]:
                brands.append({
                    "date": issue_date,
                    "market_type": "Port Stock FOT Qingdao",
                    "benchmark_grade": "62% Fe Benchmark",
                    "brand": b1,
                    "price": p1,
                    "unit": "RMB/wmt",
                    "change": c1,
                    "diff_to_benchmark": d1
                })
            elif b1 in KNOWN_BRANDS_58 and p1 is not None and b1 not in [x["brand"] for x in brands if x["benchmark_grade"] == "58% Fe Benchmark"]:
                brands.append({
                    "date": issue_date,
                    "market_type": "Port Stock FOT Qingdao",
                    "benchmark_grade": "58% Fe Benchmark",
                    "brand": b1,
                    "price": p1,
                    "unit": "RMB/wmt",
                    "change": c1,
                    "diff_to_benchmark": d1
                })
        if len(parts) >= 7:
            b2 = parts[4] if len(parts) >= 8 else parts[3]
            p2 = clean_num(parts[5]) if len(parts) >= 8 else clean_num(parts[4])
            c2 = clean_num(parts[6]) if len(parts) >= 8 else clean_num(parts[5])
            d2 = clean_num(parts[7]) if len(parts) >= 8 else clean_num(parts[6])
            if b2 in KNOWN_BRANDS_62 and p2 is not None and b2 not in [x["brand"] for x in brands if x["market_type"] == "Seaborne CFR Qingdao"]:
                brands.append({
                    "date": issue_date,
                    "market_type": "Seaborne CFR Qingdao",
                    "benchmark_grade": "62% Fe Benchmark",
                    "brand": b2,
                    "price": p2,
                    "unit": "USD/dmt",
                    "change": c2,
                    "diff_to_benchmark": d2
                })

    # 3. Normalisation Differentials Table (Port Stock & Seaborne)
    idx_norm = page3_text.find("NORMALISATION DIFFERENTIALS")
    if idx_norm != -1:
        idx_norm_end = page3_text.find("Differentials to Qingdao Port for PB Fines", idx_norm)
        norm_block = page3_text[idx_norm:idx_norm_end if idx_norm_end != -1 else idx_norm+4000]

        current_element_port = "1% Fe"
        for line in norm_block.splitlines():
            if not line.startswith("|") or "---" in line or "Product Differentials" in line:
                continue
            parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                c0, c1, c2, c3 = parts[0], parts[1], parts[2], parts[3]
                if "1% Fe" in c0: current_element_port = "1% Fe"
                elif "Alumina" in c0: current_element_port = "1% Alumina"
                elif "Silica" in c0: current_element_port = "1% Silica"
                elif "Phosphorus" in c0: current_element_port = "0.01% Phosphorus"
                
                if c1 and clean_num(c2) is not None:
                    elem = current_element_port
                    r_up = c1.upper()
                    if "<P<" in c1 or "PHOS" in r_up: elem = "0.01% Phosphorus"
                    elif "SI" in r_up: elem = "1% Silica"
                    elif "AL" in r_up: elem = "1% Alumina"
                    elif "LOW FE GRADE" in r_up and current_element_port == "1% Silica": elem = "1% Silica"
                    elif "FE" in r_up and current_element_port == "1% Fe": elem = "1% Fe"

                    normalisations.append({
                        "date": issue_date,
                        "market_type": "Port Stock",
                        "element": elem,
                        "applicable_range": c1,
                        "value": clean_num(c2),
                        "change": clean_num(c3),
                        "unit": "RMB/wet tonne"
                    })
                    
            if len(parts) >= 8:
                filtered_tokens = []
                for p in parts[4:]:
                    clean_p = p.strip()
                    if not clean_p or clean_p in ["1% Fe", "1% Alumina", "1% Silica", "0.01%", "Phosphorus", "0.01% Phosphorus"]:
                        continue
                    filtered_tokens.append(clean_p)
                    
                num_indices = [i for i, tok in enumerate(filtered_tokens) if clean_num(tok) is not None]
                if num_indices:
                    val_idx = num_indices[0]
                    val = clean_num(filtered_tokens[val_idx])
                    chg = clean_num(filtered_tokens[val_idx + 1]) if val_idx + 1 < len(filtered_tokens) else None
                    range_parts = filtered_tokens[:val_idx]
                    range_str = " ".join(range_parts).strip()
                    if range_str and val is not None:
                        r_up = range_str.upper()
                        if "<P<" in range_str or "PHOS" in r_up: elem = "0.01% Phosphorus"
                        elif "SI" in r_up: elem = "1% Silica"
                        elif "AL" in r_up: elem = "1% Alumina"
                        else: elem = "1% Fe"
                        
                        normalisations.append({
                            "date": issue_date,
                            "market_type": "Seaborne",
                            "element": elem,
                            "applicable_range": range_str,
                            "value": val,
                            "change": chg,
                            "unit": "USD/dry tonne"
                        })

    # 4. Port Stock Price Differentials to Qingdao Port for PB Fines (16 Chinese ports)
    idx_pb = page3_text.find("Differentials to Qingdao Port for PB Fines")
    if idx_pb == -1:
        idx_pb = page3_text.find("Price Differentials to Qingdao Port for PB Fines")
        
    if idx_pb != -1:
        # Check for isolated HTML table near heading
        t_start = page3_text.rfind("<table", 0, idx_pb + 200)
        t_end = page3_text.find("</table>", idx_pb)
        if t_start != -1 and t_end != -1 and t_end > t_start and (t_end - t_start) < 20000:
            soup_pb = BeautifulSoup(page3_text[t_start:t_end+8], "html.parser")
            for tr in soup_pb.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                for i in range(0, len(tds), 3):
                    if i + 2 < len(tds):
                        p_name = tds[i]
                        val = clean_num(tds[i+1])
                        chg = clean_num(tds[i+2])
                        if p_name in CHINESE_PORTS and val is not None and p_name not in [x["port"] for x in port_diffs]:
                            port_diffs.append({
                                "date": issue_date,
                                "port": p_name,
                                "differential_rmb_wmt": val,
                                "change_rmb_wmt": chg
                            })
                            
        # Check pipe format if not found or incomplete
        if len(port_diffs) < 10:
            block = page3_text[idx_pb:idx_pb+4000]
            for line in block.splitlines():
                if not line.startswith("|") or "---" in line or "Applicable" in line:
                    continue
                clean_l = re.sub(r"<br\s*/?>", " ", line, flags=re.I)
                parts = [clean_cell_text(p) for p in clean_l.split("|")[1:-1]]
                for i in range(0, len(parts), 3):
                    if i + 2 < len(parts):
                        p_name = parts[i]
                        val = clean_num(parts[i+1])
                        chg = clean_num(parts[i+2])
                        if p_name in CHINESE_PORTS and val is not None and p_name not in [x["port"] for x in port_diffs]:
                            port_diffs.append({
                                "date": issue_date,
                                "port": p_name,
                                "differential_rmb_wmt": val,
                                "change_rmb_wmt": chg
                            })

    # Generic pipe table fallback for PB Fines
    if not port_diffs:
        clean_p3 = page3_text.replace("~~", "").replace("*", "")
        for line in clean_p3.splitlines():
            if not line.startswith("|") or "---" in line or "Applicable" in line:
                continue
            clean_l = re.sub(r"<br\s*/?>", " ", line, flags=re.I)
            parts = [clean_cell_text(p) for p in clean_l.split("|")[1:-1]]
            for idx in range(0, len(parts), 3):
                if idx + 2 < len(parts):
                    p_name = parts[idx]
                    val = clean_num(parts[idx + 1])
                    chg = clean_num(parts[idx + 2])
                    if p_name in CHINESE_PORTS and val is not None and p_name not in [x["port"] for x in port_diffs]:
                        port_diffs.append({
                            "date": issue_date,
                            "port": p_name,
                            "differential_rmb_wmt": val,
                            "change_rmb_wmt": chg
                        })

    # 5. Historical Index Comparisons Chart (IOSI62, IOPi62 Eq, IOSI65, IOPi65 Eq)
    idx_comp = page3_text.find("IRON ORE INDEX COMPARISONS")
    if idx_comp != -1:
        comp_block = page3_text[idx_comp:idx_comp+4000]
        soup_comp = BeautifulSoup(comp_block, "html.parser")
        for tr in soup_comp.find_all("tr"):
            tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
            if len(tds) >= 5 and any(m in tds[0] for m in ["-Jan-", "-Mar-", "-May-", "-Jul-", "-Sep-", "-Nov-"]):
                comparisons_chart.append({
                    "date": issue_date,
                    "chart_date": tds[0],
                    "iosi62_usd_dmt": clean_num(tds[1]),
                    "iopi62_eq_usd_dmt": clean_num(tds[2]),
                    "iosi65_usd_dmt": clean_num(tds[3]),
                    "iopi65_eq_usd_dmt": clean_num(tds[4])
                })

    return brands, normalisations, port_diffs, comparisons_chart


def parse_page4(page4_text: str, issue_date: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse Page 4 Port Inventories, Futures Contracts, Freight Rates Chart, and Import Volumes Chart."""
    inventories: List[Dict[str, Any]] = []
    futures: List[Dict[str, Any]] = []
    freight_chart: List[Dict[str, Any]] = []
    imports_chart: List[Dict[str, Any]] = []
    
    # 1. Port Inventories (Jingtang, Qingdao, Caofeidian, Tianjin, Rizhao, Total 35 Ports)
    idx_inv = page4_text.find("PORT INVENTORIES")
    if idx_inv == -1:
        idx_inv = page4_text.find("Port Inventories")
    if idx_inv == -1:
        idx_inv = page4_text.find("TOTAL IRON ORE INVENTORIES")

    if idx_inv != -1:
        # Isolated HTML table
        t_start = page4_text.rfind("<table", 0, idx_inv + 200)
        t_end = page4_text.find("</table>", idx_inv)
        if t_start != -1 and t_end != -1 and t_end > t_start and (t_end - t_start) < 20000:
            soup_inv = BeautifulSoup(page4_text[t_start:t_end+8], "html.parser")
            for tr in soup_inv.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 4:
                    term = tds[0]
                    if any(k in term for k in ["Jingtang", "Qingdao", "Caofeidian", "Tianjin", "Rizhao", "Total (35 Ports)", "Total 35 Ports"]):
                        inv = clean_num(tds[1])
                        chg_pct = clean_num(tds[2])
                        low = clean_num(tds[3])
                        high = clean_num(tds[4]) if len(tds) > 4 else None
                        if inv is not None and term not in [x["terminal"] for x in inventories]:
                            inventories.append({
                                "date": issue_date, "terminal": term, "inventory_mt": inv,
                                "change_pct": chg_pct, "low_12m": low, "high_12m": high
                            })

        # Pipe table (standard and <br/>-stacked)
        if not inventories:
            block = page4_text[idx_inv:idx_inv+4000]
            for line in block.splitlines():
                if not line.startswith("|") or "---" in line:
                    continue
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if len(cells) >= 3 and any(k in cells[0] for k in ["Jingtang", "Qingdao", "35 Ports", "Caofeidian"]):
                    c0_items = [clean_cell_text(x) for x in re.split(r"<br\s*/?>|\n", cells[0], flags=re.I) if clean_cell_text(x)]
                    c1_items = [clean_num(x) for x in re.split(r"<br\s*/?>|\n", cells[1], flags=re.I) if clean_cell_text(x)]
                    c2_items = [clean_num(x) for x in re.split(r"<br\s*/?>|\n", cells[2], flags=re.I) if clean_cell_text(x)] if len(cells) > 2 else []
                    c3_items = [clean_num(x) for x in re.split(r"<br\s*/?>|\n", cells[3], flags=re.I) if clean_cell_text(x)] if len(cells) > 3 else []
                    c4_items = [clean_num(x) for x in re.split(r"<br\s*/?>|\n", cells[4], flags=re.I) if clean_cell_text(x)] if len(cells) > 4 else []
                    
                    port_terms = ["Jingtang", "Qingdao", "Caofeidian", "Tianjin", "Rizhao", "Total (35 Ports)", "Total 35 Ports"]
                    valid_pairs = []
                    for item in c0_items:
                        for pt in port_terms:
                            if pt.lower() in item.lower():
                                valid_pairs.append((item, pt))
                                break
                    
                    if len(valid_pairs) > 0 and len(c1_items) >= len(valid_pairs):
                        v_offset = len(c1_items) - len(valid_pairs)
                        for i, (term_label, pt) in enumerate(valid_pairs):
                            idx_v = v_offset + i
                            inv = c1_items[idx_v] if idx_v < len(c1_items) else None
                            chg_pct = c2_items[idx_v] if idx_v < len(c2_items) else None
                            low = c3_items[idx_v] if idx_v < len(c3_items) else None
                            high = c4_items[idx_v] if idx_v < len(c4_items) else None
                            if inv is not None and pt not in [x["terminal"] for x in inventories]:
                                inventories.append({
                                    "date": issue_date, "terminal": pt, "inventory_mt": inv,
                                    "change_pct": chg_pct, "low_12m": low, "high_12m": high
                                })
                    elif len(cells) >= 4:
                        term = clean_cell_text(cells[0])
                        if any(k in term for k in ["Jingtang", "Qingdao", "Caofeidian", "Tianjin", "Rizhao", "Total (35 Ports)", "Total 35 Ports"]):
                            inv = clean_num(cells[1])
                            chg_pct = clean_num(cells[2])
                            low = clean_num(cells[3])
                            high = clean_num(cells[4]) if len(cells) > 4 else None
                            if inv is not None and term not in [x["terminal"] for x in inventories]:
                                inventories.append({
                                    "date": issue_date, "terminal": term, "inventory_mt": inv,
                                    "change_pct": chg_pct, "low_12m": low, "high_12m": high
                                })

    # Generic pipe table fallback for inventories
    if not inventories:
        clean_p4 = convert_html_tables_in_text(page4_text).replace("~~", "").replace("*", "")
        for line in clean_p4.splitlines():
            if not line.startswith("|") or "---" in line or "Province" in line:
                continue
            parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                term = parts[0]
                if any(k in term for k in ["Jingtang", "Qingdao", "Caofeidian", "Tianjin", "Rizhao", "Total (35 Ports)", "Total 35 Ports"]):
                    inv = clean_num(parts[1])
                    chg_pct = clean_num(parts[2])
                    low = clean_num(parts[3])
                    high = clean_num(parts[4]) if len(parts) > 4 else None
                    if inv is not None and term not in [x["terminal"] for x in inventories]:
                        inventories.append({
                            "date": issue_date, "terminal": term, "inventory_mt": inv,
                            "change_pct": chg_pct, "low_12m": low, "high_12m": high
                        })

    # 2. Futures Contracts (DCE, SGX)
    idx_fut = page4_text.find("FUTURES CONTRACTS")
    if idx_fut != -1:
        fut_block = page4_text[idx_fut:idx_fut+3500]
        for line in fut_block.splitlines():
            if not line.startswith("|") or "---" in line or "<br" not in line:
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 7 and "Closing Date" in cells[0]:
                c0_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[0], flags=re.I) if clean_cell_text(x)]
                c1_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[1], flags=re.I) if clean_cell_text(x)]
                c2_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[2], flags=re.I) if clean_cell_text(x)]
                c3_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[3], flags=re.I) if clean_cell_text(x)]
                c4_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[4], flags=re.I) if clean_cell_text(x)]
                c5_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[5], flags=re.I) if clean_cell_text(x)]
                c6_lines = [clean_cell_text(x) for x in re.split(r"<br\s*/?>", cells[6], flags=re.I) if clean_cell_text(x)]
                
                # DCE Record
                if len(c1_lines) >= 8:
                    dce_contract = c1_lines[2]
                    if dce_contract.startswith("1") and len(dce_contract) == 5 and dce_contract[1:].isdigit():
                        dce_contract = "I" + dce_contract[1:]
                    dce_close = clean_num(c1_lines[3])
                    dce_vol = clean_num(c1_lines[4])
                    dce_oi = clean_num(c1_lines[5])
                    dce_low = clean_num(c1_lines[6])
                    dce_high = clean_num(c1_lines[7])
                    dce_chg = clean_num(c2_lines[3]) if len(c2_lines) > 3 else (clean_num(c2_lines[1]) if len(c2_lines) > 1 else None)
                    dce_chg_pct = clean_num(c3_lines[3]) if len(c3_lines) > 3 else (clean_num(c3_lines[1]) if len(c3_lines) > 1 else None)
                else:
                    dce_idx = 1 if len(c1_lines) > 0 and "DCE" in c1_lines[0] else 0
                    dce_contract = c1_lines[dce_idx + 1] if len(c1_lines) > dce_idx + 1 else "DCE Front Month"
                    dce_close = clean_num(c1_lines[dce_idx + 2]) if len(c1_lines) > dce_idx + 2 else None
                    dce_chg = clean_num(c2_lines[1]) if len(c2_lines) > 1 else (clean_num(c2_lines[0]) if len(c2_lines) > 0 else None)
                    dce_chg_pct = clean_num(c3_lines[1]) if len(c3_lines) > 1 else (clean_num(c3_lines[0]) if len(c3_lines) > 0 else None)
                    dce_vol = clean_num(c1_lines[dce_idx + 3]) if len(c1_lines) > dce_idx + 3 else None
                    dce_oi = clean_num(c1_lines[dce_idx + 4]) if len(c1_lines) > dce_idx + 4 else None
                    dce_low = clean_num(c1_lines[dce_idx + 5]) if len(c1_lines) > dce_idx + 5 else None
                    dce_high = clean_num(c1_lines[dce_idx + 6]) if len(c1_lines) > dce_idx + 6 else None
                if dce_close is not None:
                    futures.append({
                        "date": issue_date, "exchange": "DCE", "contract": dce_contract, "unit": "RMB/WMT",
                        "closing_price": dce_close, "change": dce_chg, "change_pct": dce_chg_pct,
                        "vol_traded_k_lots": dce_vol, "open_positions_k_lots": dce_oi,
                        "day_low": dce_low, "day_high": dce_high
                    })
                    
                # SGX Record
                if len(c4_lines) >= 8:
                    sgx_contract = c4_lines[2]
                    sgx_close = clean_num(c4_lines[3])
                    sgx_vol = clean_num(c4_lines[4])
                    sgx_oi = clean_num(c4_lines[5])
                    sgx_low = clean_num(c4_lines[6])
                    sgx_high = clean_num(c4_lines[7])
                    sgx_chg = clean_num(c5_lines[3]) if len(c5_lines) > 3 else (clean_num(c5_lines[1]) if len(c5_lines) > 1 else None)
                    sgx_chg_pct = clean_num(c6_lines[3]) if len(c6_lines) > 3 else (clean_num(c6_lines[1]) if len(c6_lines) > 1 else None)
                else:
                    sgx_idx = 1 if len(c4_lines) > 0 and "SGX" in c4_lines[0] else 0
                    sgx_contract = c4_lines[sgx_idx + 1] if len(c4_lines) > sgx_idx + 1 else "SGX Front Month"
                    sgx_close = clean_num(c4_lines[sgx_idx + 2]) if len(c4_lines) > sgx_idx + 2 else None
                    sgx_chg = clean_num(c5_lines[1]) if len(c5_lines) > 1 else (clean_num(c5_lines[0]) if len(c5_lines) > 0 else None)
                    sgx_chg_pct = clean_num(c6_lines[1]) if len(c6_lines) > 1 else (clean_num(c6_lines[0]) if len(c6_lines) > 0 else None)
                    sgx_vol = clean_num(c4_lines[sgx_idx + 3]) if len(c4_lines) > sgx_idx + 3 else None
                    sgx_oi = clean_num(c4_lines[sgx_idx + 4]) if len(c4_lines) > sgx_idx + 4 else None
                    sgx_low = clean_num(c4_lines[sgx_idx + 5]) if len(c4_lines) > sgx_idx + 5 else None
                    sgx_high = clean_num(c4_lines[sgx_idx + 6]) if len(c4_lines) > sgx_idx + 6 else None
                if sgx_close is not None:
                    futures.append({
                        "date": issue_date, "exchange": "SGX", "contract": sgx_contract, "unit": "USD/DMT",
                        "closing_price": sgx_close, "change": sgx_chg, "change_pct": sgx_chg_pct,
                        "vol_traded_k_lots": sgx_vol, "open_positions_k_lots": sgx_oi,
                        "day_low": sgx_low, "day_high": sgx_high
                    })

    # Also check standard HTML <table> format if not found above
    if not futures:
        p4_fixed = fix_unclosed_table_tags(page4_text)
        soup = BeautifulSoup(p4_fixed, "html.parser")
        for table in soup.find_all("table"):
            txt = table.get_text()
            if "DCE (RMB/WMT)" in txt or "Closing Price" in txt or "SGX (USD/DMT)" in txt:
                rows = []
                for tr in table.find_all("tr"):
                    tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                    if tds:
                        rows.append(tds)
                
                dce_contract = "DCE Front Month"
                sgx_contract = "SGX Front Month"
                for r in rows:
                    if len(r) >= 5 and "Contract" in r[0]:
                        dce_contract = r[1]
                        sgx_contract = r[4] if len(r) > 4 else ""
                        break
                        
                dce_data: Dict[str, Any] = {"date": issue_date, "exchange": "DCE", "contract": dce_contract, "unit": "RMB/WMT"}
                sgx_data: Dict[str, Any] = {"date": issue_date, "exchange": "SGX", "contract": sgx_contract, "unit": "USD/DMT"}
                
                for r in rows:
                    if not r:
                        continue
                    label = r[0]
                    if "Closing Price" in label and len(r) >= 5:
                        dce_data["closing_price"] = clean_num(r[1])
                        dce_data["change"] = clean_num(r[2])
                        dce_data["change_pct"] = clean_num(r[3])
                        sgx_data["closing_price"] = clean_num(r[4])
                        sgx_data["change"] = clean_num(r[5]) if len(r) > 5 else None
                        sgx_data["change_pct"] = clean_num(r[6]) if len(r) > 6 else None
                    elif "Vol traded" in label and len(r) >= 5:
                        dce_data["vol_traded_k_lots"] = clean_num(r[1])
                        sgx_data["vol_traded_k_lots"] = clean_num(r[4])
                    elif "Open positions" in label and len(r) >= 5:
                        dce_data["open_positions_k_lots"] = clean_num(r[1])
                        sgx_data["open_positions_k_lots"] = clean_num(r[4])
                    elif "Day Low" in label and len(r) >= 5:
                        dce_data["day_low"] = clean_num(r[1])
                        sgx_data["day_low"] = clean_num(r[4])
                    elif "Day High" in label and len(r) >= 5:
                        dce_data["day_high"] = clean_num(r[1])
                        sgx_data["day_high"] = clean_num(r[4])
                        
                if "closing_price" in dce_data and dce_data["closing_price"] is not None:
                    futures.append(dce_data)
                if "closing_price" in sgx_data and sgx_data["closing_price"] is not None:
                    futures.append(sgx_data)

    # Fallback pipe table for standard row-based Futures contracts (e.g. 2021 reports)
    if not futures:
        idx_fut = page4_text.find("FUTURES CONTRACTS")
        if idx_fut == -1:
            idx_fut = page4_text.find("Futures Contracts")
        if idx_fut != -1:
            block = page4_text[idx_fut:idx_fut+3000]
            rows = []
            for line in block.splitlines():
                if not line.startswith("|") or "---" in line:
                    if line.startswith("##") and rows:
                        break
                    continue
                parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
                if parts:
                    rows.append(parts)

            header_row = rows[0] if rows else []
            dce_contract = "DCE Front Month"
            sgx_contract = "SGX Front Month"
            for c in header_row:
                if "DCE" in c:
                    m_c = re.search(r"([A-Z]\d{4}|[A-Z]{3}\.?\s*\d{2})", c)
                    if m_c:
                        dce_contract = m_c.group(1)
                if "SGX" in c:
                    m_c = re.search(r"([A-Z]\d{4}|[A-Z]{3}\.?\s*\d{2})", c)
                    if m_c:
                        sgx_contract = m_c.group(1)

            dce_data = {"date": issue_date, "exchange": "DCE", "contract": dce_contract, "unit": "RMB/WMT"}
            sgx_data = {"date": issue_date, "exchange": "SGX", "contract": sgx_contract, "unit": "USD/DMT"}

            for r in rows:
                label = r[0].lower()
                if "closing price" in label and len(r) >= 5:
                    dce_data["closing_price"] = clean_num(r[1])
                    c_parts = r[2].split()
                    if len(c_parts) >= 2:
                        dce_data["change"] = clean_num(c_parts[0])
                        dce_data["change_pct"] = clean_num(c_parts[1])
                    elif len(c_parts) == 1:
                        dce_data["change"] = clean_num(c_parts[0])

                    sgx_data["closing_price"] = clean_num(r[3])
                    s_parts = r[4].split() if len(r) > 4 else []
                    if len(s_parts) >= 2:
                        sgx_data["change"] = clean_num(s_parts[0])
                        sgx_data["change_pct"] = clean_num(s_parts[1])
                    elif len(s_parts) == 1:
                        sgx_data["change"] = clean_num(s_parts[0])
                elif "vol traded" in label and len(r) >= 4:
                    dce_data["vol_traded_k_lots"] = clean_num(r[1])
                    sgx_data["vol_traded_k_lots"] = clean_num(r[3])
                elif "open positions" in label and len(r) >= 4:
                    dce_data["open_positions_k_lots"] = clean_num(r[1])
                    sgx_data["open_positions_k_lots"] = clean_num(r[3])
                elif "day low" in label and len(r) >= 4:
                    dce_data["day_low"] = clean_num(r[1])
                    sgx_data["day_low"] = clean_num(r[3])
                elif "day high" in label and len(r) >= 4:
                    dce_data["day_high"] = clean_num(r[1])
                    sgx_data["day_high"] = clean_num(r[3])

            if dce_data.get("closing_price") is not None:
                futures.append(dce_data)
            if sgx_data.get("closing_price") is not None:
                futures.append(sgx_data)

    # 3. Freight Rates Chart Table (C5 / C3)
    idx_fr = page4_text.find("DRY BULK FREIGHT RATES")
    if idx_fr != -1:
        t_start = page4_text.rfind("<table", 0, idx_fr + 200)
        t_end = page4_text.find("</table>", idx_fr)
        if t_start != -1 and t_end != -1 and t_end > t_start and (t_end - t_start) < 20000:
            soup_fr = BeautifulSoup(page4_text[t_start:t_end+8], "html.parser")
            for tr in soup_fr.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 3 and tds[0] not in ["Date", "Period", "Route"]:
                    c5_v = clean_num(tds[1])
                    c3_v = clean_num(tds[2])
                    if c5_v is not None or c3_v is not None:
                        freight_chart.append({
                            "date": issue_date,
                            "chart_date": tds[0],
                            "c5_waust_usd_t": c5_v,
                            "c3_tubarao_usd_t": c3_v
                        })
        if not freight_chart:
            block = page4_text[idx_fr:idx_fr+3000]
            for line in block.splitlines():
                if line.startswith("|") and "---" not in line and "Date" not in line and "Route" not in line:
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 3:
                        c5_v = clean_num(parts[1])
                        c3_v = clean_num(parts[2])
                        if c5_v is not None or c3_v is not None:
                            freight_chart.append({
                                "date": issue_date,
                                "chart_date": parts[0],
                                "c5_waust_usd_t": c5_v,
                                "c3_tubarao_usd_t": c3_v
                            })

    # 4. Import Volumes Chart Table
    idx_imp = page4_text.find("TOTAL CHINA IRON ORE IMPORT")
    if idx_imp == -1:
        idx_imp = page4_text.find("IMPORT VOLUMES")
    if idx_imp != -1:
        t_start = page4_text.rfind("<table", 0, idx_imp + 200)
        t_end = page4_text.find("</table>", idx_imp)
        if t_start != -1 and t_end != -1 and t_end > t_start and (t_end - t_start) < 20000:
            soup_imp = BeautifulSoup(page4_text[t_start:t_end+8], "html.parser")
            for tr in soup_imp.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 2 and tds[0] not in ["Date", "Period", "Month"]:
                    v_mt = clean_num(tds[1])
                    if v_mt is not None:
                        imports_chart.append({
                            "date": issue_date,
                            "period": tds[0],
                            "volume_mt": v_mt
                        })
        if not imports_chart:
            block = page4_text[idx_imp:idx_imp+3000]
            for line in block.splitlines():
                if line.startswith("|") and "---" not in line and "Date" not in line and "Month" not in line:
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 2:
                        v_mt = clean_num(parts[1])
                        if v_mt is not None:
                            imports_chart.append({
                                "date": issue_date,
                                "period": parts[0],
                                "volume_mt": v_mt
                            })

    return inventories, futures, freight_chart, imports_chart


def parse_page5(page5_text: str, issue_date: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse Page 5 Chinese Steel Spot Prices and Steel Mill Profitability."""
    spot_prices: List[Dict[str, Any]] = []
    mill_pnl: List[Dict[str, Any]] = []
    
    # 1. Steel Spot Market: scan both HTML tables and pipe tables
    p5_fixed = fix_unclosed_table_tags(page5_text)
    soup = BeautifulSoup(p5_fixed, "html.parser")
    for table in soup.find_all("table"):
        txt = table.get_text()
        if "ReBar HRB400" in txt or "HRC Q235" in txt or "Steel Spot Market" in txt:
            for tr in table.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 4 and clean_num(tds[1]) is not None:
                    prod = tds[0].replace("\u03c6", "phi")
                    if prod not in [x["product"] for x in spot_prices]:
                        spot_prices.append({
                            "date": issue_date,
                            "product": prod,
                            "price_rmb_t": clean_num(tds[1]),
                            "change_rmb_t": clean_num(tds[2]),
                            "change_pct": clean_num(tds[3])
                        })
                        
        if "Blast furnace" in txt or "Billet Cost" in txt or "Steel Mill P&L" in txt or "Steel Mill Profitability" in txt:
            for tr in table.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 3:
                    cat = tds[0]
                    p = clean_num(tds[1])
                    c = None
                    note = ""
                    if p is not None:
                        c = clean_num(tds[2])
                        note = tds[3] if len(tds) > 3 else ""
                    elif len(tds) >= 4 and clean_num(tds[2]) is not None:
                        p = clean_num(tds[2])
                        c = clean_num(tds[3]) if len(tds) > 3 else None
                        note = tds[4] if len(tds) > 4 else ""
                    if p is not None and cat not in [x["category"] for x in mill_pnl]:
                        unit = "USD/mt" if "USD" in cat else "RMB/tonne"
                        mill_pnl.append({
                            "date": issue_date,
                            "category": cat,
                            "price_or_margin": p,
                            "unit": unit,
                            "change_wow": c,
                            "note": note
                        })

    # Pipe table fallbacks for Steel Spot Market & Steel Mill Profitability
    clean_p5 = page5_text.replace("~~", "").replace("*", "")
    core_pnl_keys = ["mmi (fe 62%)", "mmi (fe 65%)", "coke", "steel scrap", "billet cost", "blast furnace"]
    for line in clean_p5.splitlines():
        if not line.startswith("|") or "---" in line or "Product" in line or "Category" in line:
            continue
        parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
        if len(parts) >= 4:
            p_label = parts[0].replace("\u03c6", "phi")
            for match_key, canon_name in KNOWN_STEEL_PRODUCTS:
                if match_key in p_label and clean_num(parts[1]) is not None:
                    if canon_name not in [x["product"] for x in spot_prices]:
                        spot_prices.append({
                            "date": issue_date,
                            "product": canon_name,
                            "price_rmb_t": clean_num(parts[1]),
                            "change_rmb_t": clean_num(parts[2]),
                            "change_pct": clean_num(parts[3])
                        })
                    break

        # Pipe table fallback for Steel Mill Profitability
        if len(parts) >= 3:
            cat = parts[0]
            cat_lower = cat.lower()
            if any(k in cat_lower for k in core_pnl_keys):
                p = clean_num(parts[1])
                c = None
                note = ""
                if p is not None:
                    c = clean_num(parts[2])
                    note = parts[3] if len(parts) > 3 else ""
                elif len(parts) >= 4 and clean_num(parts[2]) is not None:
                    p = clean_num(parts[2])
                    c = clean_num(parts[3]) if len(parts) > 3 else None
                    note = parts[4] if len(parts) > 4 else ""

                if p is not None and cat not in [x["category"] for x in mill_pnl]:
                    unit = "USD/mt" if "USD" in cat else "RMB/tonne"
                    mill_pnl.append({
                        "date": issue_date,
                        "category": cat,
                        "price_or_margin": p,
                        "unit": unit,
                        "change_wow": c,
                        "note": note
                    })

    # Fallback for single-row pipe tables with <br/> packed cells
    for line in clean_p5.splitlines():
        if "coke" in line.lower() and ("<br" in line.lower() or "\\n" in line):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 2:
                c0_items = [re.sub(r"<[^>]+>", "", x).strip() for x in re.split(r"<br\s*/?>|\\n", cells[0], flags=re.I) if x.strip()]
                c1_items = [re.sub(r"<[^>]+>", "", x).strip() for x in re.split(r"<br\s*/?>|\\n", cells[1], flags=re.I) if x.strip()]
                c2_items = [re.sub(r"<[^>]+>", "", x).strip() for x in re.split(r"<br\s*/?>|\\n", cells[2], flags=re.I) if x.strip()] if len(cells) > 2 else []
                c3_items = [re.sub(r"<[^>]+>", "", x).strip() for x in re.split(r"<br\s*/?>|\\n", cells[3], flags=re.I) if x.strip()] if len(cells) > 3 else []
                
                for idx, c0 in enumerate(c0_items):
                    c0_lower = c0.lower()
                    if any(k in c0_lower for k in core_pnl_keys) and idx < len(c1_items):
                        p = clean_num(c1_items[idx])
                        c = clean_num(c2_items[idx]) if idx < len(c2_items) else None
                        note = c3_items[idx] if idx < len(c3_items) else ""
                        if p is not None and c0 not in [x["category"] for x in mill_pnl]:
                            unit = "USD/mt" if "USD" in c0 else "RMB/tonne"
                            mill_pnl.append({
                                "date": issue_date,
                                "category": c0,
                                "price_or_margin": p,
                                "unit": unit,
                                "change_wow": c,
                                "note": note
                            })

    # 3. Steel Production & Consumption Historical Matrix (Rebar & HRC)
    steel_charts: List[Dict[str, Any]] = []
    for ind_type in ["CONSUMPTION", "PRODUCTION"]:
        pattern = rf"CHINESE STEEL {ind_type}[^\n]*?(?:Rebar|Hot[-\s]*rolled\s*Coil|HRC)"
        for m in re.finditer(pattern, page5_text, re.I):
            matched_header = m.group(0)
            product = "Rebar" if "rebar" in matched_header.lower() else "Hot-rolled Coil"
            ind_label = "Consumption" if ind_type == "CONSUMPTION" else "Production"
            pos = m.end()
            t_snippet = page5_text[pos:pos+4000]
            next_hdr = re.search(r"(?:##|\n---\n)", t_snippet)
            if next_hdr:
                t_snippet = t_snippet[:next_hdr.start()]

            headers = []
            rows = []

            # Check HTML table first
            if "<table" in t_snippet:
                t_end = t_snippet.find("</table>")
                if t_end != -1:
                    soup = BeautifulSoup(t_snippet[:t_end+8], "html.parser")
                    for th in soup.find_all("th"):
                        headers.append(clean_cell_text(th.get_text()))
                    for tr in soup.find_all("tr"):
                        tds = [clean_cell_text(td.get_text()) for td in tr.find_all("td")]
                        if tds:
                            rows.append(tds)
            
            # Check pipe table
            if not rows:
                for line in t_snippet.splitlines():
                    if not line.startswith("|") or "---" in line:
                        continue
                    parts = [clean_cell_text(p) for p in line.split("|")[1:-1]]
                    if not headers and any(k in parts[0].lower() for k in ["year", "month", "date"]):
                        headers = parts
                    elif parts:
                        rows.append(parts)

            if not headers or not rows:
                continue

            # Case A: Orientation 1 (Columns are months 01..12, Rows are years 20xx)
            is_orient_1 = any(re.match(r"^(?:0?1|Jan|M01)$", h.strip(), re.I) for h in headers[1:3])
            if is_orient_1:
                for r in rows:
                    if len(r) >= 13 and re.match(r"^20\d{2}$", r[0]):
                        row_dict = {"date": issue_date, "indicator": ind_label, "product": product, "year_series": r[0]}
                        for mi in range(1, 13):
                            row_dict[f"m{mi:02d}"] = clean_num(r[mi]) if mi < len(r) else None
                        steel_charts.append(row_dict)

            # Case B: Orientation 2 (Columns are years 20xx, Rows are months 01..12)
            elif any(re.match(r"^20\d{2}$", h) for h in headers[1:]):
                year_cols = [(col_idx, h) for col_idx, h in enumerate(headers) if re.match(r"^20\d{2}$", h)]
                for col_idx, y_str in year_cols:
                    row_dict = {"date": issue_date, "indicator": ind_label, "product": product, "year_series": y_str}
                    for m_idx, r in enumerate(rows[:12]):
                        mi = m_idx + 1
                        row_dict[f"m{mi:02d}"] = clean_num(r[col_idx]) if col_idx < len(r) else None
                    steel_charts.append(row_dict)

    return spot_prices, mill_pnl, steel_charts


def parse_page6(page6_text: str, issue_date: str) -> List[Dict[str, Any]]:
    """Parse Page 6 Average Iron Ore Specifications Applied for Brand Price Assessments."""
    specs: List[Dict[str, Any]] = []
    idx = page6_text.find("AVERAGE IRON ORE SPECIFICATIONS")
    if idx == -1:
        idx = page6_text.find("Specifications applied for 62% brand assessments")
    if idx == -1:
        return specs
        
    snippet = page6_text[idx:idx+8000]
    
    # 1. HTML table check
    idx_table = snippet.find("<table")
    if idx_table != -1 and idx_table < 300:
        t_end = snippet.find("</table>", idx_table)
        if t_end != -1:
            table_html = snippet[idx_table:t_end+8]
            soup = BeautifulSoup(table_html, "html.parser")
            for tr in soup.find_all("tr"):
                tds = [clean_cell_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                if not tds:
                    continue
                # Match port brand
                for b in (KNOWN_BRANDS_62 + KNOWN_BRANDS_58):
                    if tds[0] == b or tds[0].startswith(b):
                        nums = [clean_num(x) for x in re.findall(r"(\d+\.?\d*)\s*%", " ".join(tds[:7])) if clean_num(x) is not None]
                        if len(nums) >= 5:
                            specs.append({
                                "date": issue_date,
                                "market_type": "Port Stock",
                                "brand": b,
                                "fe_pct": nums[0],
                                "alumina_pct": nums[1],
                                "silica_pct": nums[2],
                                "phos_pct": nums[3],
                                "moisture_pct": nums[4]
                            })
                        break
                # Match seaborne brand
                if len(tds) >= 7:
                    for b in KNOWN_BRANDS_62:
                        sea_tds = " ".join(tds[6:])
                        if b in sea_tds:
                            nums = [clean_num(x) for x in re.findall(r"(\d+\.?\d*)\s*%", sea_tds) if clean_num(x) is not None]
                            if len(nums) >= 5:
                                sea_nums = nums[-5:]
                                specs.append({
                                    "date": issue_date,
                                    "market_type": "Seaborne",
                                    "brand": b,
                                    "fe_pct": sea_nums[0],
                                    "alumina_pct": sea_nums[1],
                                    "silica_pct": sea_nums[2],
                                    "phos_pct": sea_nums[3],
                                    "moisture_pct": sea_nums[4]
                                })
                            break

    # 2. Pipe table check (covers both wide-pipe and narrow-pipe layouts)
    if not specs:
        for line in snippet.splitlines():
            if not line.startswith("|") or "---" in line:
                if "##" in line and "BLOOMBERG" in line:
                    break
                continue
            
            # Check 62% brands
            found_b62 = None
            for b in KNOWN_BRANDS_62:
                if re.match(r"^\|\s*" + re.escape(b) + r"\b", line, re.I):
                    found_b62 = b
                    break
            if found_b62:
                all_nums = re.findall(r"(\d+\.?\d*)\s*%", line)
                if len(all_nums) >= 5:
                    fe, al, si, ph, mo = [clean_num(x) for x in all_nums[:5]]
                    specs.append({
                        "date": issue_date,
                        "market_type": "Port Stock",
                        "brand": found_b62,
                        "fe_pct": fe,
                        "alumina_pct": al,
                        "silica_pct": si,
                        "phos_pct": ph,
                        "moisture_pct": mo
                    })
                if len(all_nums) >= 10:
                    fe2, al2, si2, ph2, mo2 = [clean_num(x) for x in all_nums[-5:]]
                    specs.append({
                        "date": issue_date,
                        "market_type": "Seaborne",
                        "brand": found_b62,
                        "fe_pct": fe2,
                        "alumina_pct": al2,
                        "silica_pct": si2,
                        "phos_pct": ph2,
                        "moisture_pct": mo2
                    })
                continue

            # Check 58% brands
            found_b58 = None
            for b in KNOWN_BRANDS_58:
                if re.match(r"^\|\s*" + re.escape(b) + r"\b", line, re.I):
                    found_b58 = b
                    break
            if found_b58:
                all_nums = re.findall(r"(\d+\.?\d*)\s*%", line)
                if len(all_nums) >= 5:
                    fe, al, si, ph, mo = [clean_num(x) for x in all_nums[:5]]
                    specs.append({
                        "date": issue_date,
                        "market_type": "Port Stock",
                        "brand": found_b58,
                        "fe_pct": fe,
                        "alumina_pct": al,
                        "silica_pct": si,
                        "phos_pct": ph,
                        "moisture_pct": mo
                    })
    return specs



def generate_report_markdown(sidecar: Dict[str, Any]) -> str:
    """Build publication-grade, perfectly formatted GitHub Markdown report from structured data."""
    meta = sidecar["metadata"]
    dash = sidecar["dashboard_indicators"]
    comm = sidecar["market_commentary"]
    indices = sidecar["benchmark_indices"]
    conc = sidecar["domestic_concentrates"]
    brands = sidecar["brand_spot_assessments"]
    port_diffs = sidecar["port_differentials_pb_fines"]
    inventories = sidecar["port_inventories"]
    futures = sidecar["futures_contracts"]
    steel = sidecar["steel_spot_prices"]
    pnl = sidecar["steel_mill_profitability"]
    freight = sidecar.get("freight_rates", [])
    
    issue_date = meta["issue_date"]
    year = meta["year"]
    source_file = meta["source_file"]

    def fmt_num(v: Any, suffix: str = "") -> str:
        return f"{v:,.2f}{suffix}" if isinstance(v, (int, float)) else (str(v) if v is not None else "-")

    def fmt_pct(v: Any) -> str:
        if v is None:
            return "-"
        return f"{v:+.2f}%" if isinstance(v, (int, float)) else str(v)

    def fmt_chg(v: Any) -> str:
        if v is None:
            return "-"
        return f"{v:+.2f}" if isinstance(v, (int, float)) else str(v)

    # PAGE 1: Executive Dashboard
    p1 = f"""<!-- Page 1 -->

# MMi Dashboard

## Executive Summary & Core Daily Indicators

### Iron Ore Benchmark Price Indices
| Benchmark Index | Fe Grade | Market / Delivery Point | Unit | Price | Change | Change % | Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **IOPI62** | 62% Fe Fines | Port Stock (FOT Qingdao) | RMB/wmt | {fmt_num(dash.get("iopi62_61_price"))} | {fmt_chg(dash.get("iopi62_61_chg"))} | {fmt_pct(dash.get("iopi62_61_chg_pct"))} | {issue_date} |
| **IOPI65** | 65% Fe Fines | Port Stock (FOT Qingdao) | RMB/wmt | {fmt_num(dash.get("iopi65_price"))} | {fmt_chg(dash.get("iopi65_chg"))} | {fmt_pct(dash.get("iopi65_chg_pct"))} | {issue_date} |
| **IOPI58** | 58% Fe Fines | Port Stock (FOT Qingdao) | RMB/wmt | {fmt_num(dash.get("iopi58_price"))} | {fmt_chg(dash.get("iopi58_chg"))} | {fmt_pct(dash.get("iopi58_chg_pct"))} | {issue_date} |
| **IOSI62** | 62% Fe Fines | Seaborne (CFR Qingdao) | USD/dmt | {fmt_num(dash.get("iosi62_61_price"))} | {fmt_chg(dash.get("iosi62_61_chg"))} | {fmt_pct(dash.get("iosi62_61_chg_pct"))} | {issue_date} |
| **IOSI65** | 65% Fe Fines | Seaborne (CFR Qingdao) | USD/dmt | {fmt_num(dash.get("iosi65_price"))} | {fmt_chg(dash.get("iosi65_chg"))} | {fmt_pct(dash.get("iosi65_chg_pct"))} | {issue_date} |
| **IOPLI62** | 62.5% Fe Lump | Port Stock (FOT Qingdao) | RMB/wmt | {fmt_num(dash.get("iopli_lump_price"))} | {fmt_chg(dash.get("iopli_lump_chg"))} | {fmt_pct(dash.get("iopli_lump_chg_pct"))} | {issue_date} |

### Exchange Traded Futures & Derivatives
| Contract | Exchange | Unit | Settlement / Close | Change | Change % | Session |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Iron Ore Front Month** | DCE | RMB/wmt | {fmt_num(dash.get("dce_iron_ore_price"))} | {fmt_chg(dash.get("dce_iron_ore_chg"))} | {fmt_pct(dash.get("dce_iron_ore_chg_pct"))} | 3:00 pm Close |
| **Iron Ore Front Month** | SGX | USD/dmt | {fmt_num(dash.get("sgx_iron_ore_price"))} | {fmt_chg(dash.get("sgx_iron_ore_chg"))} | {fmt_pct(dash.get("sgx_iron_ore_chg_pct"))} | 5:30 pm Print |
| **Steel Rebar** | SHFE | RMB/t | {fmt_num(dash.get("shfe_rebar_price"))} | {fmt_chg(dash.get("shfe_rebar_chg"))} | {fmt_pct(dash.get("shfe_rebar_chg_pct"))} | 3:00 pm Close |

### Dry Bulk Freight Rates, Spot Steel & Inventories
| Indicator | Category / Route | Value | Change | Change % | Basis / Date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **C3 Freight** | Tubarao - Qingdao | {fmt_num(dash.get("c3_tubarao_price"), " USD/t")} | - | - | Capesize Spot |
| **C5 Freight** | W. Australia - Qingdao | {fmt_num(dash.get("c5_waust_price"), " USD/t")} | - | - | Capesize Spot |
| **Steel Rebar** | China Domestic Spot | {fmt_num(dash.get("steel_rebar_price"), " RMB/t")} | {fmt_chg(dash.get("steel_rebar_chg"))} | {fmt_pct(dash.get("steel_rebar_chg_pct"))} | Shanghai Spot |
| **Steel HRC** | China Domestic Spot | {fmt_num(dash.get("steel_hrc_price"), " RMB/t")} | {fmt_chg(dash.get("steel_hrc_chg"))} | {fmt_pct(dash.get("steel_hrc_chg_pct"))} | Shanghai Spot |
| **Port Iron Ore Inventory** | 35 Chinese Ports | {fmt_num(dash.get("port_iron_ore_inventory_mt"), " Mt")} | {fmt_chg(dash.get("port_iron_ore_inventory_chg_mt"))} | {fmt_pct(dash.get("port_iron_ore_inventory_chg_pct"))} | Weekly Survey |
| **Total Steel Inventory** | China Commercial / Mills | {fmt_num(dash.get("steel_inventory_china_mt"), " Mt")} | {fmt_chg(dash.get("steel_inventory_china_chg_mt"))} | - | Weekly Survey |"""

    # PAGE 2: Benchmark Indices & Concentrates
    idx_rows = []
    for item in indices:
        idx_rows.append(f"| **{item.get('index_name')}** | {item.get('market')} | {item.get('fe_content')} | {item.get('unit')} | {fmt_num(item.get('price'))} | {fmt_chg(item.get('change'))} | {fmt_pct(item.get('change_pct'))} | {fmt_num(item.get('mtd'))} | {fmt_num(item.get('ytd'))} | {fmt_num(item.get('low_52w'))} | {fmt_num(item.get('high_52w'))} |")
    idx_table = "\n".join(idx_rows)

    freight_section = ""
    if freight:
        freight_rows = []
        for item in freight:
            freight_rows.append(
                f"| **{item.get('route')}** | Capesize Spot | {fmt_num(item.get('rate_usd_t'), ' USD/t')} | {fmt_chg(item.get('change'))} | {fmt_pct(item.get('change_pct'))} | {fmt_num(item.get('low_52w'))} | {fmt_num(item.get('high_52w'))} |"
            )
        if freight_rows:
            freight_table = "\n".join(freight_rows)
            freight_section = f"""\n\n## Ocean Freight Rates (Capesize)\n| Route | Terms | Spot Freight Rate | Change | Change % | 52-Week Low | 52-Week High |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n{freight_table}"""

    conc_rows = []
    for item in conc:
        conc_rows.append(f"| {item.get('province')} | **{item.get('region')}** | {item.get('product')} | {item.get('basis')} | {fmt_num(item.get('price_rmb_t'))} | {fmt_pct(item.get('change_pct_rmb'))} | {fmt_num(item.get('low_rmb_t'))} | {fmt_num(item.get('high_rmb_t'))} | {fmt_num(item.get('price_usd_t'))} | {fmt_pct(item.get('change_pct_usd'))} | {fmt_num(item.get('low_usd_t'))} | {fmt_num(item.get('high_usd_t'))} |")
    conc_table = "\n".join(conc_rows)

    comm_text = comm if comm else "_No desk commentary reported for this session._"

    idx_block = f"""| Index Name | Delivery Point / Market | Grade Profile | Currency / Unit | Assessment | Change | Change % | MTD Avg | YTD Avg | 52w Low | 52w High |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{idx_table}""" if idx_rows else "_No benchmark index assessments reported for this session._"

    conc_block = f"""| Province | Mining District | Specification | Moisture Basis | Price (RMB/t) | Change % (RMB) | 12m Low (RMB) | 12m High (RMB) | Price (USD/t) | Change % (USD) | 12m Low (USD) | 12m High (USD) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{conc_table}""" if conc_rows else "_No domestic concentrate price assessments reported for this session._"

    p2_parts = [f"""<!-- Page 2 -->

# Benchmark Price Indices & Domestic Concentrates

## Desk Commentary
{comm_text}

## MMi Detailed Iron Ore Benchmark Assessments
{idx_block}{freight_section}

## Domestic Iron Ore Concentrate Spot Price Assessments
{conc_block}"""]

    # Spreads Table
    spreads_data = sidecar.get("index_spreads", [])
    if spreads_data:
        sp_rows = []
        for item in spreads_data:
            sp_rows.append(
                f"| **{item.get('index_name')}** | {item.get('fe_content')} | {item.get('market_type')} | **{item.get('benchmark_index')}** | {fmt_chg(item.get('spread_to_benchmark'))} | {fmt_pct(item.get('spread_pct'))} |"
            )
        sp_block = f"""| Index | Fe Content | Market Profile | Benchmark | Spread | Spread % |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(sp_rows)
        p2_parts.append(f"## Iron Ore Index Premiums / Discounts (Spreads)\n{sp_block}")

    # Multi-period Averages Table
    avg_data = sidecar.get("multi_period_averages", [])
    if avg_data:
        avg_rows = []
        for item in avg_data:
            avg_rows.append(
                f"| **{item.get('index_name')}** | {item.get('fe_content')} | {item.get('market_type')} | {item.get('unit')} | {fmt_num(item.get('m_minus_4'))} | {fmt_num(item.get('m_minus_3'))} | {fmt_num(item.get('m_minus_2'))} | {fmt_num(item.get('m_minus_1'))} | **{fmt_num(item.get('mtd'))}** | {fmt_num(item.get('qtd'))} | {fmt_num(item.get('ytd'))} |"
            )
        avg_block = f"""| Index | Fe Grade | Market Profile | Unit | M-4 | M-3 | M-2 | M-1 | MTD | QTD | YTD |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(avg_rows)
        p2_parts.append(f"## Multi-Period Monthly, Quarterly & YTD Averages\n{avg_block}")

    p2 = "\n\n".join(p2_parts)

    # PAGE 3: Brands & Differentials
    b62_port = [b for b in brands if b.get("benchmark_grade") == "62% Fe Benchmark" and "Port Stock" in b.get("market_type", "")]
    b62_sea = [b for b in brands if b.get("benchmark_grade") == "62% Fe Benchmark" and "Seaborne" in b.get("market_type", "")]
    b58 = [b for b in brands if b.get("benchmark_grade") == "58% Fe Benchmark"]

    b62_table_rows = []
    max_b = max(len(b62_port), len(b62_sea))
    for i in range(max_b):
        p_item = b62_port[i] if i < len(b62_port) else {}
        s_item = b62_sea[i] if i < len(b62_sea) else {}
        b62_table_rows.append(
            f"| **{p_item.get('brand', '-')}** | {fmt_num(p_item.get('price'))} | {fmt_chg(p_item.get('change'))} | {fmt_chg(p_item.get('diff_to_benchmark'))} | **{s_item.get('brand', '-')}** | {fmt_num(s_item.get('price'))} | {fmt_chg(s_item.get('change'))} | {fmt_chg(s_item.get('diff_to_benchmark'))} |"
        )
    b62_table = "\n".join(b62_table_rows)
    b62_block = f"""| Port Stock Brand | Price (RMB/wmt) | Change | Diff to IOPI62 | Seaborne Brand | Price (USD/dmt) | Change | Diff to IOSI62 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{b62_table}""" if b62_table_rows else "_No 62% Fe brand assessments reported for this session._"

    b58_table_rows = []
    for item in b58:
        b58_table_rows.append(
            f"| **{item.get('brand', '-')}** | 58% Fe Fines | Port Stock (FOT Qingdao) | RMB/wmt | {fmt_num(item.get('price'))} | {fmt_chg(item.get('change'))} | {fmt_chg(item.get('diff_to_benchmark'))} |"
        )
    b58_table = "\n".join(b58_table_rows)
    b58_block = f"""| Brand | Fe Grade | Market / Delivery Point | Unit | Price | Change | Diff to IOPI58 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{b58_table}""" if b58_table_rows else "_No 58% Fe brand assessments reported for this session._"

    pd_rows = []
    half = (len(port_diffs) + 1) // 2
    for i in range(half):
        d1 = port_diffs[i]
        d2 = port_diffs[i + half] if (i + half) < len(port_diffs) else {}
        pd_rows.append(
            f"| **{d1.get('port', '-')}** | {fmt_num(d1.get('differential_rmb_wmt'))} | {fmt_chg(d1.get('change_rmb_wmt'))} | **{d2.get('port', '-')}** | {fmt_num(d2.get('differential_rmb_wmt'))} | {fmt_chg(d2.get('change_rmb_wmt'))} |"
        )
    pd_table = "\n".join(pd_rows)
    pd_block = f"""| Port Terminal | Diff (RMB/wmt) | Change | Port Terminal | Diff (RMB/wmt) | Change |
| :--- | :--- | :--- | :--- | :--- | :--- |
{pd_table}""" if pd_rows else "_No port differentials reported for this session._"

    p3_parts = [f"""<!-- Page 3 -->

# Iron Ore Brand Spot Price Assessments & Port Differentials

## 62% Fe Benchmark Brand Assessments
{b62_block}

## 58% Fe Benchmark Brand Assessments (Port Stock FOT Qingdao)
{b58_block}

## PB Fines Port Stock Price Differentials to Qingdao Port
{pd_block}"""]

    # Normalisation Differentials Table
    norm_data = sidecar.get("index_normalisation_differentials", [])
    if norm_data:
        norm_rows = []
        for item in norm_data:
            norm_rows.append(
                f"| **{item.get('market_type')}** | **{item.get('element')}** | {item.get('applicable_range')} | {fmt_num(item.get('value'))} | {item.get('unit')} | {fmt_chg(item.get('change'))} |"
            )
        norm_block = f"""| Market Type | Normalisation Element | Applicable Range | Value | Unit | Change |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(norm_rows)
        p3_parts.append(f"## Iron Ore Index Normalisation Differentials\n{norm_block}")

    # Historical Index Comparisons Chart
    comp_data = sidecar.get("historical_index_comparisons", [])
    if comp_data:
        comp_rows = []
        for item in comp_data:
            comp_rows.append(
                f"| {item.get('chart_date')} | {fmt_num(item.get('iosi62_usd_dmt'))} | {fmt_num(item.get('iopi62_eq_usd_dmt'))} | {fmt_num(item.get('iosi65_usd_dmt'))} | {fmt_num(item.get('iopi65_eq_usd_dmt'))} |"
            )
        comp_block = f"""| Date | IOSI62 (USD/DMT) | IOPi62 CFR Eq (USD/DMT) | IOSI65 (USD/DMT) | IOPi65 CFR Eq (USD/DMT) |\n| :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(comp_rows)
        p3_parts.append(f"## Historical Iron Ore Index Comparisons (USD/DMT)\n{comp_block}")

    p3 = "\n\n".join(p3_parts)

    # PAGE 4: Inventories & Futures
    inv_rows = []
    for item in inventories:
        is_total = "Total" in item.get("terminal", "")
        prefix = "**" if is_total else ""
        inv_rows.append(
            f"| {prefix}{item.get('terminal')}{prefix} | {prefix}{fmt_num(item.get('inventory_mt'))}{prefix} | {prefix}{fmt_pct(item.get('change_pct'))}{prefix} | {fmt_num(item.get('low_12m'))} | {fmt_num(item.get('high_12m'))} |"
        )
    inv_table = "\n".join(inv_rows)
    inv_block = f"""| Port Terminal / Survey Area | Inventory (Mt) | Weekly Change % | 12-Month Low | 12-Month High |
| :--- | :--- | :--- | :--- | :--- |
{inv_table}""" if inv_rows else "_No port inventories reported for this session._"

    fut_rows = []
    for item in futures:
        fut_rows.append(
            f"| **{item.get('exchange')}** | **{item.get('contract')}** | {item.get('unit')} | {fmt_num(item.get('closing_price'))} | {fmt_chg(item.get('change'))} | {fmt_pct(item.get('change_pct'))} | {fmt_num(item.get('vol_traded_k_lots'))} | {fmt_num(item.get('open_positions_k_lots'))} | {fmt_num(item.get('day_low'))} | {fmt_num(item.get('day_high'))} |"
        )
    fut_table = "\n".join(fut_rows)
    fut_block = f"""| Exchange | Contract Month | Unit | Closing Price | Change | Change % | Volume ('000 lots) | Open Positions ('000 lots) | Day Low | Day High |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{fut_table}""" if fut_rows else "_No futures contracts reported for this session._"

    # Dry Bulk Freight Rates Chart
    fr_rows = []
    for item in sidecar.get("historical_freight_rates", []):
        fr_rows.append(f"| {item.get('chart_date')} | {fmt_num(item.get('c5_waust_usd_t'))} | {fmt_num(item.get('c3_tubarao_usd_t'))} |")
    fr_block = (f"""| Date | C5 W. Australia - Qingdao (USD/MT) | C3 Tubarao - Qingdao (USD/MT) |\n| :--- | :--- | :--- |\n""" + "\n".join(fr_rows)) if fr_rows else ""

    # China Iron Ore Import Volumes Chart
    imp_rows = []
    for item in sidecar.get("historical_import_volumes", []):
        imp_rows.append(f"| {item.get('period')} | {fmt_num(item.get('volume_mt'))} |")
    imp_block = (f"""| Month / Period | Import Volume (Million Tonnes) |\n| :--- | :--- |\n""" + "\n".join(imp_rows)) if imp_rows else ""

    p4_parts = [f"""<!-- Page 4 -->\n\n# Port Inventories & Exchange Traded Futures\n\n## Iron Ore Port Inventories (Million Tonnes)\n{inv_block}\n\n## Iron Ore Futures Contracts (DCE & SGX)\n{fut_block}"""]
    if fr_block:
        p4_parts.append(f"## Dry Bulk Freight Rates Historical Line Data (USD/MT)\n{fr_block}")
    if imp_block:
        p4_parts.append(f"## Total China Iron Ore Import Volumes (Million Tonnes)\n{imp_block}")
    p4 = "\n\n".join(p4_parts)

    # PAGE 5: Steel Spot & Mill Profitability
    stl_rows = []
    for item in steel:
        stl_rows.append(
            f"| **{item.get('product')}** | RMB/tonne | {fmt_num(item.get('price_rmb_t'))} | {fmt_chg(item.get('change_rmb_t'))} | {fmt_pct(item.get('change_pct'))} |"
        )
    stl_table = "\n".join(stl_rows)
    stl_block = f"""| Steel Product Profile | Unit | Price | Change | Change % |
| :--- | :--- | :--- | :--- | :--- |
{stl_table}""" if stl_rows else "_No steel spot market prices reported for this session._"

    pnl_rows = []
    for item in pnl:
        pnl_rows.append(
            f"| **{item.get('category')}** | {fmt_num(item.get('price_or_margin'))} | {item.get('unit')} | {fmt_chg(item.get('change_wow'))} | {item.get('note', '')} |"
        )
    if not pnl_rows:
        pnl_block = "_No steel mill profitability model data reported for this session._"
    else:
        pnl_table = "\n".join(pnl_rows)
        pnl_block = f"""| Indicator / Category | Price / Margin | Unit | Change (WoW) | Specification Notes |
| :--- | :--- | :--- | :--- | :--- |
{pnl_table}"""

    # Chinese Steel Consumption & Production Charts
    sc_rows = []
    for item in sidecar.get("historical_steel_production_consumption", []):
        sc_rows.append(
            f"| **{item.get('indicator')}** | **{item.get('product')}** | {item.get('year_series')} | {fmt_num(item.get('m01'))} | {fmt_num(item.get('m02'))} | {fmt_num(item.get('m03'))} | {fmt_num(item.get('m04'))} | {fmt_num(item.get('m05'))} | {fmt_num(item.get('m06'))} | {fmt_num(item.get('m07'))} | {fmt_num(item.get('m08'))} | {fmt_num(item.get('m09'))} | {fmt_num(item.get('m10'))} | {fmt_num(item.get('m11'))} | {fmt_num(item.get('m12'))} |"
        )
    sc_block = (f"""| Metric | Product | Year | M01 | M02 | M03 | M04 | M05 | M06 | M07 | M08 | M09 | M10 | M11 | M12 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(sc_rows)) if sc_rows else ""

    p5_parts = [f"""<!-- Page 5 -->\n\n# Steel Spot Market & Mill Profitability\n\n## Chinese Domestic Steel Spot Market Prices\n{stl_block}\n\n## Chinese Steel Mill Cost & Profitability Model\n{pnl_block}"""]
    if sc_block:
        p5_parts.append(f"## Chinese Steel Consumption & Production Monthly Matrix (Rebar & HRC 2022-Present)\n{sc_block}")
    p5 = "\n\n".join(p5_parts)

    # PAGE 6: Specifications & Directory
    # Brand Specifications Table
    specs_data = sidecar.get("brand_specifications", [])
    spec_rows = []
    for item in specs_data:
        spec_rows.append(
            f"| **{item.get('brand')}** | {item.get('market_type')} | {fmt_num(item.get('fe_pct'), '%')} | {fmt_num(item.get('alumina_pct'), '%')} | {fmt_num(item.get('silica_pct'), '%')} | {fmt_num(item.get('phos_pct'), '%')} | {fmt_num(item.get('moisture_pct'), '%')} |"
        )
    spec_table = (f"""| Brand Name | Market Segment | Fe Content % | Alumina (Al2O3) % | Silica (SiO2) % | Phosphorus (P) % | Moisture Content % |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n""" + "\n".join(spec_rows)) if spec_rows else ""
    spec_block = f"""\n\n## Average Iron Ore Specifications Applied for Brand Price Assessments\n{spec_table}""" if spec_table else ""

    p6 = f"""<!-- Page 6 -->

# Index Specifications & Publisher Information

## Benchmark Specifications & Compilation Methodology
| Index Specification | 65% Fe Fines | 62% Fe Fines | 58% Fe Fines | 62.5% Fe Lump |
| :--- | :--- | :--- | :--- | :--- |
| **Iron Content (Fe %)** | 65.00% | 62.00% | 58.00% | 62.50% |
| **Alumina Content (Al2O3 %)** | 1.40% | 2.25% | 2.25% | 1.50% |
| **Silica Content (SiO2 %)** | 1.50% | 4.00% | 5.50% | 3.50% |
| **Phosphorus Content (P %)** | 0.06% | 0.09% | 0.05% | 0.08% |
| **Sulphur Content (S %)** | 0.01% | 0.02% | 0.02% | 0.02% |
| **Moisture Content** | 8.00% | 8.00% | 9.00% | 4.00% |
| **Pricing Basis** | CFR Qingdao | FOT / CFR Qingdao | FOT / CFR Qingdao | FOT Qingdao |
| **Payment Terms** | L/C at sight | L/C at sight | L/C at sight | L/C at sight or CAD |{spec_block}

## Bloomberg Terminal Tickers
| Index Identifier | Market Segment | Delivery Terms | Bloomberg Ticker |
| :--- | :--- | :--- | :--- |
| **IOPI62** | Port Stock Index | FOT Qingdao (RMB/wet tonne) | `IRCNQ001` |
| **IOPI58** | Port Stock Index | FOT Qingdao (RMB/wet tonne) | `IRCNQ002` |
| **IOPI65** | Port Stock Index | FOT Qingdao (RMB/wet tonne) | `IRCNQ003` |
| **IOPI62 CFR Eq** | Port Stock Index | CFR Qingdao Equivalent (USD/dry tonne) | `IRCNQ004` |
| **IOPI58 CFR Eq** | Port Stock Index | CFR Qingdao Equivalent (USD/dry tonne) | `IRCNQ005` |
| **IOPI65 CFR Eq** | Port Stock Index | CFR Qingdao Equivalent (USD/dry tonne) | `IRCNQ006` |
| **IOSI62** | Seaborne Index | CFR Qingdao (USD/DMT) | `IRCN0034` |
| **IOSI65** | Seaborne Index | CFR Qingdao (USD/DMT) | `IRCN0035` |
| **IOPLI62** | Port Lump Index | FOT Qingdao (RMB/wet tonne) | `IRCN0036` |
| **IOPLI62 CFR Eq** | Port Lump Index | CFR Qingdao Equivalent (USD/dry tonne) | `IRCN0037` |

## Publisher Contact Information
- **MMI Singapore Office:** Level 28, Manulife Tower, 8 Cross Street, Singapore | Tel: +65 6850 7629 | Email: prices@mmiprices.com
- **SMM Singapore Office:** Level 28, Manulife Tower, 8 Cross Street, Singapore | Tel: +65 6850 7630 | Email: service.en@smm.cn
- **SMM Shanghai Office:** 9th FL, Building 9, Lujiazui Software Park, No.20, Lane 91, Pudong, Shanghai | Tel: +86 021 5155 0306 | Email: service.en@smm.cn
- **Website:** [www.mmiprices.com](http://www.mmiprices.com)"""

    body = "\n\n---\n\n".join([p1, p2, p3, p4, p5, p6])
    
    frontmatter = f"""---
title: "MMi Daily Iron Ore Index Report - {issue_date}"
issue_date: "{issue_date}"
year: {year}
publisher: "Metals Market Index (MMi)"
source: "hellenic_iron_ore"
category: "iron_ore"
source_file: "corpus/02-hellenic/iron_ore/pdfs/{year}/{source_file}"
pages: 6
---

# MMi Daily Iron Ore Index Report — {issue_date}

- **Issue Date**: {issue_date}
- **Publisher**: Metals Market Index (MMi)
- **Source**: `corpus/02-hellenic/iron_ore/pdfs/{year}/{source_file}`

{body}
"""
    return frontmatter


def extract_page_sections(raw_md: str) -> Tuple[str, str, str, str, str, str]:
    """Dynamically segment LlamaParse output into 6 page sections based on content signatures."""
    chunks = [c for c in raw_md.split("\n\n---\n\n") if len(c.strip()) > 80]
    
    sec1_chunks, sec2_chunks, sec3_chunks, sec4_chunks, sec5_chunks, sec6_chunks = [], [], [], [], [], []
    for c in chunks:
        clean_c = re.sub(r"[^a-z0-9]", "", c.lower())
        if "mmidashboard" in clean_c or ("exchangetradedcontracts" in clean_c and "freightrates" in clean_c and "shfe" in clean_c):
            sec1_chunks.append(c)
        elif "ironoreportstockindex" in clean_c or "benchmarkcomposite" in clean_c or "chinaexportfecontent" in clean_c or ("iopi62" in clean_c and "fotqingdao" in clean_c and "iopli" in clean_c):
            sec2_chunks.append(c)
        elif "ironorebrandspot" in clean_c or "normalisationdifferentials" in clean_c or ("brandspotprice" in clean_c and "carajas" in clean_c):
            sec3_chunks.append(c)
        elif "portinventories" in clean_c or "totalironoreinventories" in clean_c or "futurescontracts" in clean_c or "futuretrading" in clean_c:
            sec4_chunks.append(c)
        elif "steelspotmarket" in clean_c or "chinesesteelmill" in clean_c or "steelmillprofitability" in clean_c or "billetcost" in clean_c or "rebarcost" in clean_c:
            sec5_chunks.append(c)
        elif "ironoreindexspecifications" in clean_c or "compilationrationale" in clean_c or "bloombergtickers" in clean_c or "contactus" in clean_c:
            sec6_chunks.append(c)
        else:
            if "iopi" in clean_c and "iosi" in clean_c:
                sec2_chunks.append(c)
            elif "rebar" in clean_c and "blastfurnace" in clean_c:
                sec5_chunks.append(c)

    p1 = "\n\n".join(sec1_chunks)
    p2 = "\n\n".join(sec2_chunks)
    p3 = "\n\n".join(sec3_chunks)
    p4 = "\n\n".join(sec4_chunks)
    p5 = "\n\n".join(sec5_chunks)
    p6 = "\n\n".join(sec6_chunks)
    
    # Fallback to standard page indexing if categorization produced empty strings
    raw_pages = raw_md.split("\n\n---\n\n")
    if not p1 and len(raw_pages) > 0: p1 = raw_pages[0]
    if not p2 and len(raw_pages) > 1: p2 = raw_pages[1]
    if not p3 and len(raw_pages) > 2: p3 = raw_pages[2]
    if not p4 and len(raw_pages) > 3: p4 = raw_pages[3]
    if not p5 and len(raw_pages) > 4: p5 = raw_pages[4]
    if not p6 and len(raw_pages) > 5: p6 = raw_pages[5]
    
    return p1, p2, p3, p4, p5, p6


async def process_single_mmi_pdf(pdf_path: Path, sem: asyncio.Semaphore) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str, Dict[str, Any]]:
    """Process a single MMi Daily Iron Ore PDF end-to-end."""
    issue_date, year = extract_date_from_filename(pdf_path.name)
    stem = pdf_path.stem

    out_year_dir = OUT_MD_DIR / year
    out_year_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_year_dir / f"{stem}.md"
    json_path = out_year_dir / f"{stem}.tables.json"

    # Fast path: if sidecar already extracted with brand_specifications and normalisations, reuse
    if json_path.exists() and json_path.stat().st_size > 500:
        try:
            sidecar = json.loads(json_path.read_text(encoding="utf-8"))
            if sidecar.get("pipeline_version") == "v4_perfect" and sidecar.get("index_normalisation_differentials") and len(sidecar.get("index_normalisation_differentials", [])) >= 10:
                full_md = generate_report_markdown(sidecar)
                md_path.write_text(full_md, encoding="utf-8")
                return (
                    sidecar.get("dashboard_indicators", {}),
                    sidecar.get("benchmark_indices", []),
                    sidecar.get("domestic_concentrates", []),
                    sidecar.get("brand_spot_assessments", []),
                    sidecar.get("port_differentials_pb_fines", []),
                    sidecar.get("port_inventories", []),
                    sidecar.get("futures_contracts", []),
                    sidecar.get("steel_spot_prices", []),
                    sidecar.get("steel_mill_profitability", []),
                    sidecar.get("brand_specifications", []),
                    sidecar.get("historical_freight_rates", []),
                    sidecar.get("historical_import_volumes", []),
                    sidecar.get("historical_steel_production_consumption", []),
                    sidecar.get("index_spreads", []),
                    sidecar.get("multi_period_averages", []),
                    sidecar.get("index_normalisation_differentials", []),
                    sidecar.get("historical_index_comparisons", []),
                    sidecar.get("market_commentary", ""),
                    sidecar
                )
        except Exception:
            pass

    # 1. Get LlamaParse markdown
    raw_md = await get_or_parse_mmi_pdf(pdf_path, sem)
    p1, p2, p3, p4, p5, p6 = extract_page_sections(raw_md)

    # 2. Extract structured datasets
    dashboard = parse_page1_dashboard(p1, issue_date)
    dashboard["year"] = year
    dashboard["source_file"] = pdf_path.name
    
    indices, concentrates, freight, spreads, averages, commentary = parse_page2(p2, issue_date, pdf_path)
    for ind in indices:
        ind["year"] = year
        ind["source_file"] = pdf_path.name
    for conc in concentrates:
        conc["year"] = year
        conc["source_file"] = pdf_path.name
    for sp in spreads:
        sp["year"] = year
        sp["source_file"] = pdf_path.name
    for avg in averages:
        avg["year"] = year
        avg["source_file"] = pdf_path.name
        
    brands, normalisations, port_diffs, comparisons_chart = parse_page3(p3, issue_date)
    for b in brands:
        b["year"] = year
        b["source_file"] = pdf_path.name
    for n in normalisations:
        n["year"] = year
        n["source_file"] = pdf_path.name
    for pd_item in port_diffs:
        pd_item["year"] = year
        pd_item["source_file"] = pdf_path.name
    for cmp in comparisons_chart:
        cmp["year"] = year
        cmp["source_file"] = pdf_path.name
        
    inventories, futures, freight_chart, imports_chart = parse_page4(p4, issue_date)
    for inv in inventories:
        inv["year"] = year
        inv["source_file"] = pdf_path.name
    for f in futures:
        f["year"] = year
        f["source_file"] = pdf_path.name
    for fr in freight_chart:
        fr["year"] = year
        fr["source_file"] = pdf_path.name
    for imp in imports_chart:
        imp["year"] = year
        imp["source_file"] = pdf_path.name
        
    steel_prices, mill_pnl, steel_charts = parse_page5(p5, issue_date)
    for sp in steel_prices:
        sp["year"] = year
        sp["source_file"] = pdf_path.name
    for mp in mill_pnl:
        mp["year"] = year
        mp["source_file"] = pdf_path.name
    for sc in steel_charts:
        sc["year"] = year
        sc["source_file"] = pdf_path.name

    brand_specs = parse_page6(p6, issue_date)
    for bs in brand_specs:
        bs["year"] = year
        bs["source_file"] = pdf_path.name

    # 3. Save sidecar JSON
    sidecar = {
        "pipeline_version": "v4_perfect",
        "metadata": {
            "title": f"MMi Daily Iron Ore Index Report - {issue_date}",
            "issue_date": issue_date,
            "year": year,
            "publisher": "Metals Market Index (MMi)",
            "source_file": pdf_path.name,
            "pages_count": 6,
            "pipeline_version": "v4_perfect",
        },
        "dashboard_indicators": dashboard,
        "market_commentary": commentary,
        "benchmark_indices": indices,
        "domestic_concentrates": concentrates,
        "freight_rates": freight,
        "index_spreads": spreads,
        "multi_period_averages": averages,
        "brand_spot_assessments": brands,
        "index_normalisation_differentials": normalisations,
        "port_differentials_pb_fines": port_diffs,
        "historical_index_comparisons": comparisons_chart,
        "port_inventories": inventories,
        "futures_contracts": futures,
        "steel_spot_prices": steel_prices,
        "steel_mill_profitability": mill_pnl,
        "brand_specifications": brand_specs,
        "historical_freight_rates": freight_chart,
        "historical_import_volumes": imports_chart,
        "historical_steel_production_consumption": steel_charts,
    }
    out_year_dir = OUT_MD_DIR / year
    out_year_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_year_dir / f"{stem}.tables.json"
    json_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4. Generate publication-grade, perfectly formatted GitHub Markdown report
    full_md = generate_report_markdown(sidecar)
    md_path = out_year_dir / f"{stem}.md"
    md_path.write_text(full_md, encoding="utf-8")

    return (
        dashboard, indices, concentrates, brands, port_diffs,
        inventories, futures, steel_prices, mill_pnl,
        brand_specs, freight_chart, imports_chart, steel_charts,
        spreads, averages, normalisations, comparisons_chart,
        commentary, sidecar
    )


def process_single_mmi_sync(pdf_path_str: str) -> Dict[str, Any]:
    """Synchronous worker function for multi-core batch processing of cached PDFs."""
    force = False
    if pdf_path_str.endswith("::force"):
        force = True
        pdf_path_str = pdf_path_str[:-7]
    pdf_path = Path(pdf_path_str)
    issue_date, year = extract_date_from_filename(pdf_path.name)
    stem = pdf_path.stem

    out_year_dir = OUT_MD_DIR / year
    out_year_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_year_dir / f"{stem}.md"
    json_path = out_year_dir / f"{stem}.tables.json"

    # Fast path: only skip if already extracted with v4_perfect AND has all datasets populated
    if not force and json_path.exists() and json_path.stat().st_size > 500:
        try:
            sidecar = json.loads(json_path.read_text(encoding="utf-8"))
            if (
                sidecar.get("pipeline_version") == "v4_perfect"
                and len(sidecar.get("index_normalisation_differentials", [])) >= 10
                and len(sidecar.get("index_spreads", [])) >= 1
                and len(sidecar.get("multi_period_averages", [])) >= 2
            ):
                return {"status": "skipped", "name": pdf_path.name, "issue_date": issue_date}
        except Exception:
            pass

    cache_file = CACHE_DIR / f"{stem}.md"
    if not cache_file.exists() or cache_file.stat().st_size < 500:
        return {"status": "error_no_cache", "name": pdf_path.name}

    try:
        raw_md = cache_file.read_text(encoding="utf-8")
        p1, p2, p3, p4, p5, p6 = extract_page_sections(raw_md)

        dashboard = parse_page1_dashboard(p1, issue_date)
        dashboard["year"] = year
        dashboard["source_file"] = pdf_path.name

        indices, concentrates, freight, spreads, averages, commentary = parse_page2(p2, issue_date, pdf_path)
        for ind in indices:
            ind["year"] = year
            ind["source_file"] = pdf_path.name
        for conc in concentrates:
            conc["year"] = year
            conc["source_file"] = pdf_path.name
        for sp in spreads:
            sp["year"] = year
            sp["source_file"] = pdf_path.name
        for avg in averages:
            avg["year"] = year
            avg["source_file"] = pdf_path.name

        brands, normalisations, port_diffs, comparisons_chart = parse_page3(p3, issue_date)
        for b in brands:
            b["year"] = year
            b["source_file"] = pdf_path.name
        for n in normalisations:
            n["year"] = year
            n["source_file"] = pdf_path.name
        for pd_item in port_diffs:
            pd_item["year"] = year
            pd_item["source_file"] = pdf_path.name
        for cmp in comparisons_chart:
            cmp["year"] = year
            cmp["source_file"] = pdf_path.name

        inventories, futures, freight_chart, imports_chart = parse_page4(p4, issue_date)
        for inv in inventories:
            inv["year"] = year
            inv["source_file"] = pdf_path.name
        for f in futures:
            f["year"] = year
            f["source_file"] = pdf_path.name
        for fr in freight_chart:
            fr["year"] = year
            fr["source_file"] = pdf_path.name
        for imp in imports_chart:
            imp["year"] = year
            imp["source_file"] = pdf_path.name

        steel_prices, mill_pnl, steel_charts = parse_page5(p5, issue_date)
        for sp in steel_prices:
            sp["year"] = year
            sp["source_file"] = pdf_path.name
        for mp in mill_pnl:
            mp["year"] = year
            mp["source_file"] = pdf_path.name
        for sc in steel_charts:
            sc["year"] = year
            sc["source_file"] = pdf_path.name

        brand_specs = parse_page6(p6, issue_date)
        for bs in brand_specs:
            bs["year"] = year
            bs["source_file"] = pdf_path.name

        sidecar = {
            "pipeline_version": "v4_perfect",
            "metadata": {
                "title": f"MMi Daily Iron Ore Index Report - {issue_date}",
                "issue_date": issue_date,
                "year": year,
                "publisher": "Metals Market Index (MMi)",
                "source_file": pdf_path.name,
                "pages_count": 6,
                "pipeline_version": "v4_perfect",
            },
            "dashboard_indicators": dashboard,
            "market_commentary": commentary,
            "benchmark_indices": indices,
            "domestic_concentrates": concentrates,
            "freight_rates": freight,
            "index_spreads": spreads,
            "multi_period_averages": averages,
            "brand_spot_assessments": brands,
            "index_normalisation_differentials": normalisations,
            "port_differentials_pb_fines": port_diffs,
            "historical_index_comparisons": comparisons_chart,
            "port_inventories": inventories,
            "futures_contracts": futures,
            "steel_spot_prices": steel_prices,
            "steel_mill_profitability": mill_pnl,
            "brand_specifications": brand_specs,
            "historical_freight_rates": freight_chart,
            "historical_import_volumes": imports_chart,
            "historical_steel_production_consumption": steel_charts,
        }
        json_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        full_md = generate_report_markdown(sidecar)
        md_path.write_text(full_md, encoding="utf-8")

        return {
            "status": "ok",
            "name": pdf_path.name,
            "issue_date": issue_date,
            "brands": len(brands),
            "normalisations": len(normalisations),
            "spreads": len(spreads)
        }
    except Exception as e:
        return {"status": "error", "name": pdf_path.name, "error": str(e)}


def save_stacked_series(
    dashboards: List[Dict[str, Any]],
    indices: List[Dict[str, Any]],
    concentrates: List[Dict[str, Any]],
    brands: List[Dict[str, Any]],
    port_diffs: List[Dict[str, Any]],
    inventories: List[Dict[str, Any]],
    futures: List[Dict[str, Any]],
    steel: List[Dict[str, Any]],
    mill_pnl: List[Dict[str, Any]],
    brand_specs: List[Dict[str, Any]] = None,
    freight_chart: List[Dict[str, Any]] = None,
    imports_chart: List[Dict[str, Any]] = None,
    steel_charts: List[Dict[str, Any]] = None,
    spreads: List[Dict[str, Any]] = None,
    averages: List[Dict[str, Any]] = None,
    normalisations: List[Dict[str, Any]] = None,
    comparisons_chart: List[Dict[str, Any]] = None,
):
    """Stack and persist all 17 extracted time series to CSV across all available sidecars."""
    all_json_files = sorted(OUT_MD_DIR.rglob("*.tables.json"))
    dashboards_dict: Dict[str, Dict[str, Any]] = {}
    indices_dict: Dict[Tuple, Dict[str, Any]] = {}
    concentrates_dict: Dict[Tuple, Dict[str, Any]] = {}
    spreads_dict: Dict[Tuple, Dict[str, Any]] = {}
    averages_dict: Dict[Tuple, Dict[str, Any]] = {}
    brands_dict: Dict[Tuple, Dict[str, Any]] = {}
    normalisations_dict: Dict[Tuple, Dict[str, Any]] = {}
    port_diffs_dict: Dict[Tuple, Dict[str, Any]] = {}
    comparisons_chart_dict: Dict[Tuple, Dict[str, Any]] = {}
    inventories_dict: Dict[Tuple, Dict[str, Any]] = {}
    futures_dict: Dict[Tuple, Dict[str, Any]] = {}
    steel_dict: Dict[Tuple, Dict[str, Any]] = {}
    mill_pnl_dict: Dict[Tuple, Dict[str, Any]] = {}
    brand_specs_dict: Dict[Tuple, Dict[str, Any]] = {}
    freight_chart_dict: Dict[Tuple, Dict[str, Any]] = {}
    imports_chart_dict: Dict[Tuple, Dict[str, Any]] = {}
    steel_charts_dict: Dict[Tuple, Dict[str, Any]] = {}

    for jf in all_json_files:
        try:
            sc = json.loads(jf.read_text(encoding="utf-8"))
            d = sc.get("dashboard_indicators", {})
            if d and d.get("issue_date"):
                dashboards_dict[d["issue_date"]] = d

            for it in sc.get("benchmark_indices", []):
                key = (it.get("date"), it.get("index_name"), it.get("market"))
                indices_dict[key] = it

            for it in sc.get("domestic_concentrates", []):
                key = (it.get("date"), it.get("region"), it.get("basis"))
                concentrates_dict[key] = it

            for it in sc.get("index_spreads", []):
                key = (it.get("date"), it.get("index_name"), it.get("market_type"))
                spreads_dict[key] = it

            for it in sc.get("multi_period_averages", []):
                key = (it.get("date"), it.get("index_name"), it.get("market_type"))
                averages_dict[key] = it

            for it in sc.get("brand_spot_assessments", []):
                key = (it.get("date"), it.get("market_type"), it.get("brand"))
                brands_dict[key] = it

            for it in sc.get("index_normalisation_differentials", []):
                key = (it.get("date"), it.get("market_type"), it.get("element"), it.get("applicable_range"))
                normalisations_dict[key] = it

            for it in sc.get("port_differentials_pb_fines", []):
                key = (it.get("date"), it.get("port"))
                port_diffs_dict[key] = it

            for it in sc.get("historical_index_comparisons", []):
                key = (it.get("date"), it.get("chart_date"))
                comparisons_chart_dict[key] = it

            for it in sc.get("port_inventories", []):
                key = (it.get("date"), it.get("terminal"))
                inventories_dict[key] = it

            for it in sc.get("futures_contracts", []):
                key = (it.get("date"), it.get("exchange"), it.get("contract"))
                futures_dict[key] = it

            for it in sc.get("steel_spot_prices", []):
                key = (it.get("date"), it.get("product"))
                steel_dict[key] = it

            for it in sc.get("steel_mill_profitability", []):
                key = (it.get("date"), it.get("category"))
                mill_pnl_dict[key] = it

            for it in sc.get("brand_specifications", []):
                key = (it.get("date"), it.get("market_type"), it.get("brand"))
                brand_specs_dict[key] = it

            for it in sc.get("historical_freight_rates", []):
                key = (it.get("date"), it.get("chart_date"))
                freight_chart_dict[key] = it

            for it in sc.get("historical_import_volumes", []):
                key = (it.get("date"), it.get("period"))
                imports_chart_dict[key] = it

            for it in sc.get("historical_steel_production_consumption", []):
                key = (it.get("date"), it.get("indicator"), it.get("product"), it.get("year_series"))
                steel_charts_dict[key] = it
        except Exception:
            continue

    # Merge in any in-memory records from current run
    for d in dashboards:
        if d and d.get("issue_date"):
            dashboards_dict[d["issue_date"]] = d
    for it in indices:
        indices_dict[(it.get("date"), it.get("index_name"), it.get("market"))] = it
    for it in concentrates:
        concentrates_dict[(it.get("date"), it.get("region"), it.get("basis"))] = it
    if spreads:
        for it in spreads:
            spreads_dict[(it.get("date"), it.get("index_name"), it.get("market_type"))] = it
    if averages:
        for it in averages:
            averages_dict[(it.get("date"), it.get("index_name"), it.get("market_type"))] = it
    for it in brands:
        brands_dict[(it.get("date"), it.get("market_type"), it.get("brand"))] = it
    if normalisations:
        for it in normalisations:
            normalisations_dict[(it.get("date"), it.get("market_type"), it.get("element"), it.get("applicable_range"))] = it
    for it in port_diffs:
        port_diffs_dict[(it.get("date"), it.get("port"))] = it
    if comparisons_chart:
        for it in comparisons_chart:
            comparisons_chart_dict[(it.get("date"), it.get("chart_date"))] = it
    for it in inventories:
        inventories_dict[(it.get("date"), it.get("terminal"))] = it
    for it in futures:
        futures_dict[(it.get("date"), it.get("exchange"), it.get("contract"))] = it
    for it in steel:
        steel_dict[(it.get("date"), it.get("product"))] = it
    for it in mill_pnl:
        mill_pnl_dict[(it.get("date"), it.get("category"))] = it
    if brand_specs:
        for it in brand_specs:
            brand_specs_dict[(it.get("date"), it.get("market_type"), it.get("brand"))] = it
    if freight_chart:
        for it in freight_chart:
            freight_chart_dict[(it.get("date"), it.get("chart_date"))] = it
    if imports_chart:
        for it in imports_chart:
            imports_chart_dict[(it.get("date"), it.get("period"))] = it
    if steel_charts:
        for it in steel_charts:
            steel_charts_dict[(it.get("date"), it.get("indicator"), it.get("product"), it.get("year_series"))] = it

    # 1. Dashboard Series
    dash_rows = sorted(dashboards_dict.values(), key=lambda x: str(x.get("issue_date", "")))
    if dash_rows:
        p_dash = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_dashboard_series.csv"
        dash_keys = list(dash_rows[0].keys())
        with open(p_dash, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=dash_keys)
            w.writeheader()
            w.writerows(dash_rows)
        print(f"Saved {len(dash_rows)} cumulative rows to {p_dash.name}")

    # 2. Detailed Benchmark Indices
    idx_rows = sorted(indices_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("index_name", ""))))
    if idx_rows:
        p_idx = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_indices_series.csv"
        idx_keys = ["date", "year", "index_name", "market", "fe_content", "unit", "price", "change", "change_pct", "mtd", "ytd", "low_52w", "high_52w", "source_file"]
        with open(p_idx, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=idx_keys)
            w.writeheader()
            w.writerows(idx_rows)
        print(f"Saved {len(idx_rows)} cumulative rows to {p_idx.name}")

    # 3. Brand Spot Assessments
    brand_rows = sorted(brands_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("brand", ""))))
    if brand_rows:
        p_br = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_brands_series.csv"
        br_keys = ["date", "year", "market_type", "benchmark_grade", "brand", "price", "unit", "change", "diff_to_benchmark", "source_file"]
        with open(p_br, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=br_keys)
            w.writeheader()
            w.writerows(brand_rows)
        print(f"Saved {len(brand_rows)} cumulative rows to {p_br.name}")

    # 4. Domestic Concentrates
    conc_rows = sorted(concentrates_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("region", ""))))
    if conc_rows:
        p_conc = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_domestic_concentrate_series.csv"
        conc_keys = ["date", "year", "province", "region", "product", "basis", "price_rmb_t", "change_pct_rmb", "low_rmb_t", "high_rmb_t", "price_usd_t", "change_pct_usd", "low_usd_t", "high_usd_t", "source_file"]
        with open(p_conc, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=conc_keys)
            w.writeheader()
            w.writerows(conc_rows)
        print(f"Saved {len(conc_rows)} cumulative rows to {p_conc.name}")

    # 5. Port Differentials
    pd_rows = sorted(port_diffs_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("port", ""))))
    if pd_rows:
        p_pd = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_port_differentials_series.csv"
        pd_keys = ["date", "year", "port", "differential_rmb_wmt", "change_rmb_wmt", "source_file"]
        with open(p_pd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=pd_keys)
            w.writeheader()
            w.writerows(pd_rows)
        print(f"Saved {len(pd_rows)} cumulative rows to {p_pd.name}")

    # 6. Port Inventories
    inv_rows = sorted(inventories_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("terminal", ""))))
    if inv_rows:
        p_inv = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_port_inventories_series.csv"
        inv_keys = ["date", "year", "terminal", "inventory_mt", "change_pct", "low_12m", "high_12m", "source_file"]
        with open(p_inv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=inv_keys)
            w.writeheader()
            w.writerows(inv_rows)
        print(f"Saved {len(inv_rows)} cumulative rows to {p_inv.name}")

    # 7. Futures Contracts
    fut_rows = sorted(futures_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("contract", ""))))
    if fut_rows:
        p_fut = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_futures_series.csv"
        fut_keys = ["date", "year", "exchange", "contract", "unit", "closing_price", "change", "change_pct", "vol_traded_k_lots", "open_positions_k_lots", "day_low", "day_high", "source_file"]
        with open(p_fut, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fut_keys)
            w.writeheader()
            w.writerows(fut_rows)
        print(f"Saved {len(fut_rows)} cumulative rows to {p_fut.name}")

    # 8. Steel Spot Prices
    steel_rows = sorted(steel_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("product", ""))))
    if steel_rows:
        p_steel = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_steel_series.csv"
        steel_keys = ["date", "year", "product", "price_rmb_t", "change_rmb_t", "change_pct", "source_file"]
        with open(p_steel, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=steel_keys)
            w.writeheader()
            w.writerows(steel_rows)
        print(f"Saved {len(steel_rows)} cumulative rows to {p_steel.name}")

    # 9. Steel Mill Profitability
    pnl_rows = sorted(mill_pnl_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("category", ""))))
    if pnl_rows:
        p_pnl = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_steel_mill_pnl_series.csv"
        pnl_keys = ["date", "year", "category", "price_or_margin", "unit", "change_wow", "note", "source_file"]
        with open(p_pnl, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=pnl_keys)
            w.writeheader()
            w.writerows(pnl_rows)
        print(f"Saved {len(pnl_rows)} cumulative rows to {p_pnl.name}")

    # 10. Brand Specifications (Page 6)
    spec_rows = sorted(brand_specs_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("brand", ""))))
    if spec_rows:
        p_spec = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_brand_specs_series.csv"
        spec_keys = ["date", "year", "market_type", "brand", "fe_pct", "alumina_pct", "silica_pct", "phos_pct", "moisture_pct", "source_file"]
        with open(p_spec, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=spec_keys)
            w.writeheader()
            w.writerows(spec_rows)
        print(f"Saved {len(spec_rows)} cumulative rows to {p_spec.name}")

    # 11. Historical Freight Rates Chart (Page 4)
    fr_rows = sorted(freight_chart_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("chart_date", ""))))
    if fr_rows:
        p_fr = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_freight_rates_series.csv"
        fr_keys = ["date", "year", "chart_date", "c5_waust_usd_t", "c3_tubarao_usd_t", "source_file"]
        with open(p_fr, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fr_keys)
            w.writeheader()
            w.writerows(fr_rows)
        print(f"Saved {len(fr_rows)} cumulative rows to {p_fr.name}")

    # 12. Historical China Import Volumes Chart (Page 4)
    imp_rows = sorted(imports_chart_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("period", ""))))
    if imp_rows:
        p_imp = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_import_volumes_series.csv"
        imp_keys = ["date", "year", "period", "volume_mt", "source_file"]
        with open(p_imp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=imp_keys)
            w.writeheader()
            w.writerows(imp_rows)
        print(f"Saved {len(imp_rows)} cumulative rows to {p_imp.name}")

    # 13. Historical Steel Production & Consumption Monthly Matrix (Page 5)
    sc_rows = sorted(steel_charts_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("indicator", "")), str(x.get("product", "")), str(x.get("year_series", ""))))
    if sc_rows:
        p_sc = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_steel_production_consumption_series.csv"
        sc_keys = ["date", "year", "indicator", "product", "year_series", "m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08", "m09", "m10", "m11", "m12", "source_file"]
        with open(p_sc, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=sc_keys)
            w.writeheader()
            w.writerows(sc_rows)
        print(f"Saved {len(sc_rows)} cumulative rows to {p_sc.name}")

    # 14. Index Premiums / Discounts (Spreads) (Page 2)
    sp_rows = sorted(spreads_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("index_name", ""))))
    if sp_rows:
        p_sp = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_spreads_series.csv"
        sp_keys = ["date", "year", "index_name", "fe_content", "market_type", "benchmark_index", "spread_to_benchmark", "spread_pct", "source_file"]
        with open(p_sp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=sp_keys)
            w.writeheader()
            w.writerows(sp_rows)
        print(f"Saved {len(sp_rows)} cumulative rows to {p_sp.name}")

    # 15. Multi-Period Averages (Page 2)
    avg_rows = sorted(averages_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("index_name", ""))))
    if avg_rows:
        p_avg = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_averages_series.csv"
        avg_keys = ["date", "year", "index_name", "market_type", "fe_content", "unit", "m_minus_4", "m_minus_3", "m_minus_2", "m_minus_1", "mtd", "qtd", "ytd", "source_file"]
        with open(p_avg, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=avg_keys)
            w.writeheader()
            w.writerows(avg_rows)
        print(f"Saved {len(avg_rows)} cumulative rows to {p_avg.name}")

    # 16. Normalisation Differentials (Page 3)
    norm_rows = sorted(normalisations_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("market_type", "")), str(x.get("element", ""))))
    if norm_rows:
        p_norm = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_normalisations_series.csv"
        norm_keys = ["date", "year", "market_type", "element", "applicable_range", "value", "unit", "change", "source_file"]
        with open(p_norm, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=norm_keys)
            w.writeheader()
            w.writerows(norm_rows)
        print(f"Saved {len(norm_rows)} cumulative rows to {p_norm.name}")

    # 17. Historical Index Comparisons Chart (Page 3)
    comp_rows = sorted(comparisons_chart_dict.values(), key=lambda x: (str(x.get("date", "")), str(x.get("chart_date", ""))))
    if comp_rows:
        p_cmp = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_index_comparisons_series.csv"
        cmp_keys = ["date", "year", "chart_date", "iosi62_usd_dmt", "iopi62_eq_usd_dmt", "iosi65_usd_dmt", "iopi65_eq_usd_dmt", "source_file"]
        with open(p_cmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cmp_keys)
            w.writeheader()
            w.writerows(comp_rows)
        print(f"Saved {len(comp_rows)} cumulative rows to {p_cmp.name}")


def get_unique_reports(pdf_root: Path) -> List[Path]:
    """Find all unique PDF reports by SHA256 deduplication, caching result for speed."""
    cache_index = CACHE_DIR / "_unique_files.json"
    if cache_index.exists():
        try:
            paths = [Path(p) for p in json.loads(cache_index.read_text(encoding="utf-8"))]
            valid = [p for p in paths if p.exists()]
            if len(valid) >= 1000:
                return valid
        except Exception:
            pass

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
    try:
        cache_index.write_text(json.dumps([str(p.resolve()) for p in unique_files], indent=2), encoding="utf-8")
    except Exception:
        pass
    return unique_files


def main():
    parser = argparse.ArgumentParser(description="MMi Daily Iron Ore PDF Extraction Pipeline")
    parser.add_argument("--sample", action="store_true", help="Process the 3 multi-era validation sample files")
    parser.add_argument("--all", action="store_true", help="Process all unique reports in the corpus")
    parser.add_argument("--force", action="store_true", help="Force re-extraction of all files regardless of sidecar cache")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 8, help="Multiprocessing worker count")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of reports to process")
    args = parser.parse_args()

    if args.sample:
        sample_paths = [
            PDF_CORPUS_DIR / "2026" / "2026-01-05_mmi-daily-iron-ore-index-report-january-05-2026_mmi-daily-iron-ore-report-for-5th-ja_1043a5b8d53a.pdf",
            PDF_CORPUS_DIR / "2024" / "2024-01-03_mmi-daily-iron-ore-index-report-january-03-2024_mmi-daily-iron-ore-report-for-3th-ja_c5ee64e06ebf.pdf",
            PDF_CORPUS_DIR / "2022" / "2022-01-04_mmi-daily-iron-ore-index-report-january-04-2022_mmi-daily-iron-ore-report-for-4th-ja_a6e432e1b566.pdf",
        ]
        target_files = [p for p in sample_paths if p.exists()]
    else:
        print("Scanning and deduplicating Iron Ore PDFs...", flush=True)
        target_files = get_unique_reports(PDF_CORPUS_DIR)
        if args.limit:
            target_files = target_files[:args.limit]

    print(f"Targeting {len(target_files)} unique reports with workers={args.workers} (force={args.force})...", flush=True)

    t0 = time.time()
    success = 0
    skipped = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_single_mmi_sync, str(p.resolve()) + ("::force" if args.force else "")): p for p in target_files}
        done_count = 0
        total = len(futures)
        for fut in as_completed(futures):
            p = futures[fut]
            done_count += 1
            try:
                res = fut.result()
                st = res.get("status")
                if st == "skipped":
                    skipped += 1
                elif st == "ok":
                    success += 1
                else:
                    errors += 1
                    print(f"  [ERROR] {p.name}: {res}", flush=True)
            except Exception as e:
                errors += 1
                print(f"  [EXCEPTION] {p.name}: {e}", flush=True)

            if done_count % 50 == 0 or done_count == total:
                elapsed = time.time() - t0
                rate = done_count / elapsed if elapsed > 0 else 0
                print(f"[{done_count}/{total}] Processed: {success} new, {skipped} skipped, {errors} errors ({rate:.1f} files/sec)", flush=True)

    # Save master series from all accumulated sidecars
    print("\nCompiling and writing 17 master CSV series...", flush=True)
    save_stacked_series([], [], [], [], [], [], [], [], [])

    t1 = time.time()
    print(f"\nProcessing complete in {t1 - t0:.1f}s. New: {success}, Skipped: {skipped}, Errors: {errors}", flush=True)


if __name__ == "__main__":
    main()
