"""SMM Daily Iron Ore Single-Page PDF Extraction Pipeline.

Extracts comprehensive structured data across all sections of the new SMM Iron Ore Daily 1-page PDF format:
- Metadata & Publishing Information
- Futures Contracts (SGX & DCE Most-traded)
- SMM Iron Ore Price Index (Physical Port Spot, Seaborne, Domestic Composite)
- Key View (Full editorial narrative & headlines)
- Today's Highlights (Structured analytical bullets)
- Qingdao Port Imported Ore Spot Prices (CNY brand prices, deltas, MTD averages)
- Imported Ore USD Prices & MMi Indices (USD brand prices, deltas, MTD averages)
- SMM Iron Ore Price Index Weekly / Monthly Statistics (MTD, MoM %, YTD %, Unit)
- Key Price Drivers (4 High-Resolution Vector Chart PNG clips & extracted fundamental numbers)
- Market Commentary: Imported Ore (Futures & Spot, Driver, Demand, Inventory & Supply, Cost & Margin)
- Market Commentary: Domestic Ore (Prices, Supply & Demand, Outlook)
- Market Factors (Supportive Factors & Bearish Factors)
- Flash News (Market briefs & links)

Produces:
- data/extracted/md/hellenic/iron_ore_pdf/<year>/<stem>.md
- data/extracted/md/hellenic/iron_ore_pdf/<year>/<stem>.tables.json
- data/extracted/charts/hellenic_iron_ore/<issue_date>_*.png
- data/extracted/series/hellenic_iron_ore_pdf_dashboard_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_indices_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_brands_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_futures_series.csv
- data/extracted/series/hellenic_iron_ore_pdf_averages_series.csv
- data/extracted/series/hellenic_smm_market_drivers_series.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "iron_ore_pdf"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
OUT_CHARTS_DIR = ROOT / "data" / "extracted" / "charts" / "hellenic_iron_ore"
PDF_CORPUS_DIR = ROOT / "corpus" / "02-hellenic" / "iron_ore" / "pdfs"

OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_change_val(raw_str: str) -> float:
    """Parse numeric delta handling triangles, em-dashes, and sign conventions."""
    if not raw_str:
        return 0.0
    if "—" in raw_str and not any(c.isdigit() for c in raw_str.replace("0", "")):
        return 0.0
    is_neg = ("▼" in raw_str) or ("-" in raw_str)
    cleaned = raw_str.replace("▼", "").replace("▲", "").replace("—", "0").replace("+", "").replace("-", "").strip()
    try:
        val = float(cleaned)
        return -val if (is_neg and val > 0) else val
    except Exception:
        return 0.0


def extract_chart_images(page: pymupdf.Page, issue_date: str) -> Dict[str, str]:
    """Render high-resolution PNG clips of the 4 Key Price Drivers charts."""
    date_chart_dir = OUT_CHARTS_DIR / issue_date
    date_chart_dir.mkdir(parents=True, exist_ok=True)

    charts_def = [
        ("ocean_freight", pymupdf.Rect(35, 3420, 385, 3685)),
        ("port_inventory", pymupdf.Rect(395, 3420, 745, 3685)),
        ("hot_metal_bf", pymupdf.Rect(35, 3685, 385, 3960)),
        ("shipments_arrivals", pymupdf.Rect(395, 3685, 745, 3960))
    ]

    matrix = pymupdf.Matrix(2.0, 2.0)
    chart_paths = {}
    for name, rect in charts_def:
        pix = page.get_pixmap(matrix=matrix, clip=rect)
        img_name = f"{issue_date}_{name}.png"
        img_file = date_chart_dir / img_name
        pix.save(str(img_file))
        # Relative path for Markdown embedding (from data/extracted/md/hellenic/iron_ore_pdf/<year>/)
        rel_path = f"../../../../charts/hellenic_iron_ore/{issue_date}/{img_name}"
        chart_paths[name] = rel_path

    return chart_paths


def parse_smm_single_page_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Parse complete structured contents of an SMM 1-page iron ore report."""
    doc = pymupdf.open(str(pdf_path))
    if len(doc) != 1:
        doc.close()
        raise ValueError(f"Expected 1-page SMM PDF, found {len(doc)} pages: {pdf_path.name}")

    page = doc[0]
    raw_text = page.get_text("text")
    text = raw_text.replace("\u3000", " ")
    blocks = page.get_text("blocks")
    blocks_sorted = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

    # 1. Date & Header
    m_date = re.search(r'(\d{4}-\d{2}-\d{2})\s+([A-Za-z]+)', text)
    if m_date:
        issue_date = m_date.group(1)
        day_of_week = m_date.group(2)
        year = issue_date[:4]
    else:
        m_fn = re.search(r'(\d{4}-\d{2}-\d{2})', pdf_path.name)
        if m_fn:
            issue_date = m_fn.group(1)
            year = issue_date[:4]
            day_of_week = "Unknown"
        else:
            issue_date = "2026-09-01"
            year = "2026"
            day_of_week = "Unknown"

    chart_rel_paths = extract_chart_images(page, issue_date)

    extracted: Dict[str, Any] = {
        "metadata": {
            "title": f"SMM Iron Ore Daily - {issue_date}",
            "issue_date": issue_date,
            "day_of_week": day_of_week,
            "year": year,
            "publisher": "Shanghai Metals Market (SMM)",
            "format": "smm_single_page_v1",
            "source_file": pdf_path.name,
            "page_count": 1,
            "char_count": len(text)
        },
        "chart_images": chart_rel_paths,
        "futures_contracts": [],
        "smm_price_index_summary": [],
        "key_view": {},
        "todays_highlights": [],
        "qingdao_port_spot_cny": [],
        "imported_ore_usd_prices": [],
        "index_statistics_weekly_monthly": [],
        "key_price_drivers": {},
        "market_commentary_imported": {},
        "market_commentary_domestic": {},
        "market_factors": {"supportive": [], "bearish": []},
        "flash_news": []
    }

    # 2. Futures Contracts (SGX & DCE)
    sgx_m = re.search(
        r'SGX Iron Ore Most-traded Contract.*?\n\s*([\d\.]+)\s*USD/dmt\s*\n\s*(?:([▼▲—\-\s\+\d\.]+)\s+([▼▲—\-\s\+\d\.]+%)|No quotation \(holiday\))[^\n]*\n\s*(?:as of [\d\-]+\s*·\s*)?MTD avg\s*([\d\.]+)',
        text, re.DOTALL
    )
    if sgx_m:
        extracted["futures_contracts"].append({
            "exchange": "SGX",
            "contract": "SGX Iron Ore Most-traded",
            "price": float(sgx_m.group(1)),
            "unit": "USD/dmt",
            "change": parse_change_val(sgx_m.group(2)) if sgx_m.group(2) else 0.0,
            "change_pct": sgx_m.group(3).strip() if sgx_m.group(3) else "0.00% (Holiday)",
            "mtd_avg": float(sgx_m.group(4))
        })

    dce_m = re.search(
        r'DCE Iron Ore Most-traded(?:\s+([A-Za-z0-9]+)|[^\n]*?)\n[^\n]*?\n\s*([\d\.]+)\s*yuan/mt\s*\n\s*(?:([▼▲—\-\s\+\d\.]+)\s+([▼▲—\-\s\+\d\.]+%)|No quotation \(holiday\))[^\n]*\n\s*(?:as of [\d\-]+\s*·\s*)?MTD avg\s*([\d\.]+)',
        text, re.DOTALL
    )
    if dce_m:
        c_code = dce_m.group(1) or "Contract"
        extracted["futures_contracts"].append({
            "exchange": "DCE",
            "contract": f"DCE Iron Ore Most-traded {c_code}".strip(),
            "contract_code": c_code,
            "price": float(dce_m.group(2)),
            "unit": "yuan/mt",
            "change": parse_change_val(dce_m.group(3)) if dce_m.group(3) else 0.0,
            "change_pct": dce_m.group(4).strip() if dce_m.group(4) else "0.00% (Holiday)",
            "mtd_avg": float(dce_m.group(5))
        })

    # 3. SMM Iron Ore Price Index (top 6 cards - supports both active trading days and holiday freeze)
    idx_defs = [
        ("MMi 61% Port Spot", r'MM[iI] 61% Port Spot', "yuan/wmt", 61.0, "port_spot"),
        ("MMi 58% Port Spot", r'MM[iI] 58% Port Spot', "yuan/wmt", 58.0, "port_spot"),
        ("MMi 65% Port Spot", r'MM[iI] 65% Port Spot', "yuan/wmt", 65.0, "port_spot"),
        ("MMi 61% Seaborne Index", r'MM[iI] 61% Seaborne Index', "USD/dmt", 61.0, "seaborne"),
        ("MMi 65% Seaborne Index", r'MM[iI] 65% Seaborne Index', "USD/dmt", 65.0, "seaborne"),
        ("SMM Domestic Ore Composite Index", r'SMM Domestic Ore Composite Index', "yuan/mt", 66.0, "domestic_composite")
    ]
    for name, title_pat, unit, fe, mkt in idx_defs:
        pat = (
            rf'{title_pat}(?:[^\n]*\n){{1,3}}?\s*([\d\.]+)\s*{re.escape(unit)}\s*\n\s*'
            rf'(?:([▼▲—\-\s\+\d\.]+)\s+([▼▲—\-\s\+\d\.]+%)|No quotation \(holiday\))\s*'
            rf'(?:as of [\d\-]+\s*(?:·\s*)?)?MTD avg\s*([\d\.]+)'
        )
        m = re.search(pat, text, re.DOTALL)
        if m:
            extracted["smm_price_index_summary"].append({
                "index_name": name,
                "market_type": mkt,
                "fe_content": fe,
                "price": float(m.group(1)),
                "unit": unit,
                "change": parse_change_val(m.group(2)) if m.group(2) else 0.0,
                "change_pct": m.group(3).strip() if m.group(3) else "0.00% (Holiday)",
                "mtd_avg": float(m.group(4))
            })

    # 4. Key View (preserve multi-line bold headlines and join wrapped body lines into clean paragraphs)
    m_kv = re.search(r'Key View\s*\n(.*?)\nToday\'s Highlights', text, re.DOTALL)
    if m_kv:
        # Use PyMuPDF dict spans inside the Key View y-band to accurately separate headline vs body paragraphs
        page_dict = page.get_text("dict")
        kv_y0, kv_y1 = None, None
        for b in blocks_sorted:
            bt = b[4].strip()
            if bt.startswith("Key View"):
                kv_y0 = b[1]
            elif bt.startswith("Today's Highlights"):
                kv_y1 = b[1]
                break

        headline_parts: List[str] = []
        body_paragraphs: List[str] = []
        if kv_y0 is not None and kv_y1 is not None:
            prev_kv_y1 = None
            for b in page_dict.get("blocks", []):
                if b.get("type") != 0:
                    continue
                by0 = b["bbox"][1]
                if by0 < kv_y0 - 2 or by0 >= kv_y1 - 2:
                    continue
                for line in b.get("lines", []):
                    line_txt = "".join(sp.get("text", "") for sp in line.get("spans", [])).strip()
                    if not line_txt or line_txt == "Key View":
                        continue
                    ly0, ly1 = line["bbox"][1], line["bbox"][3]
                    l_height = ly1 - ly0
                    first_color = line["spans"][0].get("color", 0) if line.get("spans") else 0
                    is_hl_line = (l_height >= 14.0 or first_color == 16777215) and not body_paragraphs
                    if is_hl_line and prev_kv_y1 is not None and (ly0 - prev_kv_y1) > 18.0 and headline_parts:
                        is_hl_line = False
                    if is_hl_line:
                        headline_parts.append(line_txt)
                    else:
                        body_paragraphs.append(line_txt)
                    prev_kv_y1 = ly1

        if headline_parts and body_paragraphs:
            extracted["key_view"]["headline"] = " ".join(headline_parts)
            extracted["key_view"]["body"] = " ".join(body_paragraphs)
        else:
            kv_raw = m_kv.group(1).strip()
            kv_lines = [l.strip() for l in kv_raw.split("\n") if l.strip()]
            if kv_lines:
                if len(kv_lines) > 2 and (
                    len(kv_lines[1]) < 105
                    and not kv_lines[0].endswith(".")
                    and re.search(r'(\b(?:of|to|in|on|at|for|with|and|or|as|by|from|that|than|the|a|an)|,)\s*$', kv_lines[0], re.IGNORECASE)
                ):
                    extracted["key_view"]["headline"] = f"{kv_lines[0]} {kv_lines[1]}"
                    extracted["key_view"]["body"] = " ".join(kv_lines[2:])
                else:
                    extracted["key_view"]["headline"] = kv_lines[0]
                    extracted["key_view"]["body"] = " ".join(kv_lines[1:])

    # 5. Today's Highlights
    m_th = re.search(r'Today\'s Highlights\s*\n(.*?)\nQingdao Port Imported Ore Spot\s+Prices', text, re.DOTALL)
    if m_th:
        th_raw = m_th.group(1).strip()
        if re.search(r'[◆•]', th_raw):
            bullets = re.split(r'\n\s*[◆•]\s*', th_raw)
        else:
            # Group lines between 'Today's Highlights' and 'Qingdao Port Imported Ore Spot' using y-gap (>11pt) or lead color (1185565)
            th_y0, th_y1 = None, None
            for b in blocks_sorted:
                bt = b[4].strip()
                if bt.startswith("Today's Highlights"):
                    th_y0 = b[1]
                elif bt.startswith("Qingdao Port Imported Ore Spot"):
                    th_y1 = b[1]
                    break
            grouped_bullets: List[str] = []
            if th_y0 is not None and th_y1 is not None:
                cur_b: List[str] = []
                prev_ly1 = None
                for b in page_dict.get("blocks", []):
                    if b.get("type") != 0:
                        continue
                    by0 = b["bbox"][1]
                    if by0 < th_y0 - 2 or by0 >= th_y1 - 2:
                        continue
                    for line in b.get("lines", []):
                        spans = [sp for sp in line.get("spans", []) if sp.get("text", "").strip()]
                        if not spans:
                            continue
                        line_txt = "".join(sp.get("text", "") for sp in line.get("spans", [])).strip()
                        line_txt = re.sub(r'^[◆•\-\*]\s*', '', line_txt).strip()
                        if not line_txt or line_txt.startswith("Today's Highlights"):
                            continue
                        ly0, ly1 = line["bbox"][1], line["bbox"][3]
                        y_gap = (ly0 - prev_ly1) if prev_ly1 is not None else 99.0
                        first_color = spans[0].get("color", 0)
                        is_new_bullet = (not cur_b) or (y_gap > 11.0) or (first_color == 1185565 and cur_b[-1].rstrip().endswith("."))
                        if is_new_bullet:
                            if cur_b:
                                grouped_bullets.append(" ".join(cur_b))
                            cur_b = [line_txt]
                        else:
                            cur_b.append(line_txt)
                        prev_ly1 = ly1
                if cur_b:
                    grouped_bullets.append(" ".join(cur_b))
            bullets = grouped_bullets if grouped_bullets else re.split(r'\n(?=[◆•]\s*)', th_raw)
        for b in bullets:
            b_clean = re.sub(r'^[◆•\-\*]\s*', '', b.strip()).replace('-\n', '-').replace('\n', ' ')
            b_clean = re.sub(r'\s{2,}', ' ', b_clean)
            if len(b_clean) > 20:
                extracted["todays_highlights"].append(b_clean)

    # 6. Qingdao Port Imported Ore Spot Prices (CNY)
    m_qd = re.search(
        r'Qingdao Port Imported Ore Spot\s+Prices.*?\nProduct\s+.*?Last 12 months\s*\n(.*?)\nImported Ore USD Prices',
        text, re.DOTALL
    )
    if m_qd:
        qd_raw = m_qd.group(1).strip()
        row_pat = re.compile(
            r'([A-Za-z0-9\s\(\)\-]+?\d+(?:\.\d+)?%)\s*\n\s*Daily\s*\n\s*([\d\.]+)\s*\n\s*'
            r'(?:([▲▼—\-]?\s*[\+\-\d\.]+)\s+([▼▲—\-\s\+\d\.]+%)|No quotation \(holiday\)\s*\n\s*as of [\d\-]+)\s*\n\s*([\d\.]+)'
        )
        for m in row_pat.finditer(qd_raw):
            prod = " ".join(m.group(1).split())
            m_fe = re.search(r'(\d+(?:\.\d+)?)%', prod)
            fe_val = float(m_fe.group(1)) if m_fe else 62.0
            prod_type = "Lump" if "Lump" in prod else "Fines"
            extracted["qingdao_port_spot_cny"].append({
                "product": prod,
                "fe_pct": fe_val,
                "product_type": prod_type,
                "price_yuan_wmt": float(m.group(2)),
                "change": parse_change_val(m.group(3)) if m.group(3) else 0.0,
                "change_pct": m.group(4).strip() if m.group(4) else "0.00% (Holiday)",
                "mtd_avg": float(m.group(5)),
                "unit": "yuan/wmt"
            })

    # 7. Imported Ore USD Prices & MMi Indices (USD, including Seaborne Fines Prices sub-table)
    m_usd = re.search(
        r'Imported Ore USD Prices & MMi\s+Indices.*?\nProduct\s+.*?Last 12 months\s*\n(.*?)\nSMM Iron Ore Price Index\s+weekly',
        text, re.DOTALL
    )
    if m_usd:
        usd_raw = m_usd.group(1).strip()
        # Remove sub-table header lines so rows parse uniformly
        usd_raw_clean = re.sub(
            r'Seaborne Fines Prices in USD[^\n]*\n(?:[^\n]*\n){0,3}?Product\s+.*?(?:Last 12 months|MTD avg)\s*\n',
            '\n',
            usd_raw,
            flags=re.DOTALL
        )
        row_pat = re.compile(
            r'([A-Za-z0-9\s\(\)\-]+?\d+(?:\.\d+)?%(?:\s+[A-Za-z\s]+?Index)?)\s*\n\s*Daily\s*\n\s*([\d\.]+)\s*\n\s*'
            r'(?:([▲▼—\-]?\s*[\+\-\d\.]+)\s+([▼▲—\-\s\+\d\.]+%)|No quotation \(holiday\)\s*\n\s*as of [\d\-]+)\s*\n\s*([\d\.]+)'
        )
        for m in row_pat.finditer(usd_raw_clean):
            prod = " ".join(m.group(1).split())
            m_fe = re.search(r'(\d+(?:\.\d+)?)%', prod)
            fe_val = float(m_fe.group(1)) if m_fe else 62.0
            prod_type = "Index" if "Index" in prod else ("Lump" if "Lump" in prod else "Fines")
            extracted["imported_ore_usd_prices"].append({
                "product": prod,
                "fe_pct": fe_val,
                "product_type": prod_type,
                "price_usd_dmt": float(m.group(2)),
                "change": parse_change_val(m.group(3)) if m.group(3) else 0.0,
                "change_pct": m.group(4).strip() if m.group(4) else "0.00% (Holiday)",
                "mtd_avg": float(m.group(5)),
                "unit": "USD/dmt"
            })

    # 8. SMM Iron Ore Price Index weekly / monthly statistics
    m_stat = re.search(r'SMM Iron Ore Price Index\s+weekly / monthly statistics.*?\nIndex\s+Month-to-date avg\s+MoM\s+YTD\s+Unit\s+Last 12 months\s*\n(.*?)\n(?=Onshore and offshore|Key Price Drivers)', text, re.DOTALL)
    if m_stat:
        stat_raw = m_stat.group(1).strip()
        stat_pat = re.compile(r'([A-Za-z0-9\s%]+?(?:Index|Price Index))\s*\n\s*Daily\s*\n\s*([\d\.]+)\s*\n\s*([\+\-\d\.]+%)\s*\n\s*([\+\-\d\.]+%)\s*\n\s*([A-Za-z/]+)')
        for m in stat_pat.finditer(stat_raw):
            idx_name = " ".join(m.group(1).split())
            extracted["index_statistics_weekly_monthly"].append({
                "index_name": idx_name,
                "mtd_avg": float(m.group(2)),
                "mom_pct": m.group(3).strip(),
                "ytd_pct": m.group(4).strip(),
                "unit": m.group(5).strip()
            })

    # 9. Market Commentary (Imported Ore)
    m_imp_comm = re.search(r'Market Commentary · Imported Ore\s*\n(.*?)\nMarket Commentary · Domestic Ore', text, re.DOTALL)
    if m_imp_comm:
        raw_c = m_imp_comm.group(1).strip()
        sub_headers = [
            ("Futures & Spot", r'Futures\s*&\s*spot\s*\n(.*?)(?=\n\s*(?:Drivers?|Demand|Inventory|Cost\s*&\s*margin)\b)'),
            ("Driver", r'Drivers?\s*\n(.*?)(?=\n\s*(?:Demand|Inventory|Cost\s*&\s*margin)\b)'),
            ("Demand", r'Demand\s*\n(.*?)(?=\n\s*(?:Inventory|Cost\s*&\s*margin)\b)'),
            ("Inventory & Supply", r'Inventory\s*&\s*\n?supply\s*\n(.*?)(?=\n\s*(?:Cost\s*&\s*margin)\b)'),
            ("Cost & Margin", r'Cost\s*&\s*\n?margin\s*\n(.*?)$')
        ]
        for name, p_sub in sub_headers:
            m_s = re.search(p_sub, raw_c, re.DOTALL | re.IGNORECASE)
            if m_s:
                extracted["market_commentary_imported"][name] = re.sub(r'\s{2,}', ' ', m_s.group(1).strip().replace("\n", " "))

    # 10. Market Commentary (Domestic Ore)
    m_dom_comm = re.search(r'Market Commentary · Domestic Ore\s*\n(.*?)\nMarket Factors', text, re.DOTALL)
    if m_dom_comm:
        raw_d = m_dom_comm.group(1).strip()
        sub_headers_dom = [
            ("Prices", r'Prices\s*\n(.*?)(?=\n\s*(?:Supply|Outlook)\b)'),
            ("Supply & Demand", r'Supply(?:\s*&\s*\n?demand)?\s*\n(.*?)(?=\n\s*(?:Outlook)\b)'),
            ("Outlook", r'Outlook\s*\n(.*?)$')
        ]
        for name, p_sub in sub_headers_dom:
            m_s = re.search(p_sub, raw_d, re.DOTALL | re.IGNORECASE)
            if m_s:
                extracted["market_commentary_domestic"][name] = re.sub(r'\s{2,}', ' ', m_s.group(1).strip().replace("\n", " "))

    # 11. Market Factors
    m_fac = re.search(r'Market Factors\s*\n(.*?)\nFlash News', text, re.DOTALL)
    if m_fac:
        raw_fac = m_fac.group(1)
        m_sup = re.search(r'▲\s*Supportive factors\s*\n(.*?)(?=▼\s*Bearish factors)', raw_fac, re.DOTALL | re.IGNORECASE)
        m_bear = re.search(r'▼\s*Bearish factors\s*\n(.*?)$', raw_fac, re.DOTALL | re.IGNORECASE)
        def _split_factor_bullets(raw_str: str) -> List[str]:
            if re.search(r'[•◆]', raw_str):
                return [re.sub(r'\s{2,}', ' ', b.replace('-\n', '-').replace('\n', ' ').strip()) for b in re.split(r'[•◆]\s*', raw_str) if len(b.strip()) > 10]
            # When bullet glyphs are vector shapes, each bullet ends with a period at the end of a line followed by a newline and uppercase start
            parts = re.split(r'(?<=\.)\s*\n\s*(?=[A-Z0-9])', raw_str)
            return [re.sub(r'\s{2,}', ' ', re.sub(r'^[•\-\*]\s*', '', p.strip()).replace('-\n', '-').replace('\n', ' ')) for p in parts if len(p.strip()) > 10]

        if m_sup:
            extracted["market_factors"]["supportive"] = _split_factor_bullets(m_sup.group(1).strip())
        if m_bear:
            extracted["market_factors"]["bearish"] = _split_factor_bullets(m_bear.group(1).strip())

    # 12. Key Price Drivers metrics (from text & charts)
    m_fr_c3 = re.search(r'(?:C3(?:\s+Brazil[→–\-]China)?\s+(?:freight\s+)?(?:at|was|stood at|slid[^\n]*?to)?\s*(?:USD\s*)?([\d\.]+)\s*(?:USD)?/mt|USD\s*([\d\.]+)/mt\s+for\s+C3|C3\s+([\d\.]+))', text, re.IGNORECASE)
    if m_fr_c3:
        val_c3 = m_fr_c3.group(1) or m_fr_c3.group(2) or m_fr_c3.group(3)
        extracted["key_price_drivers"]["freight_c3_usd_mt"] = float(val_c3)
    m_fr_c5 = re.search(r'(?:C5(?:\s+Australia[→–\-]China)?\s+(?:freight\s+)?(?:at|was|stood at)?\s*(?:USD\s*)?([\d\.]+)\s*(?:USD)?/mt|([\d\.]+)(?:/mt)?\s+for\s+C5|C5\s+([\d\.]+))', text, re.IGNORECASE)
    if m_fr_c5:
        val_c5 = m_fr_c5.group(1) or m_fr_c5.group(2) or m_fr_c5.group(3)
        extracted["key_price_drivers"]["freight_c5_usd_mt"] = float(val_c5)
    m_hm = re.search(r'(?:hot metal(?:\s+output)?(?:\s+across\s+242\s+mills)?\s+(?:was|at|stood at|remained at|fell[^\n]*?to|rose[^\n]*?to)\s+([\d\.]+)\s*million\s*mt|Hot metal\s*\(([\d\.]+)\s*million\s*mt\))', text, re.IGNORECASE)
    if m_hm:
        extracted["key_price_drivers"]["hot_metal_daily_avg_mt_million"] = float(m_hm.group(1) or m_hm.group(2))
    m_bf = re.search(r'blast furnace operating rate\s+(?:was|at|stood at|of)\s+([\d\.]+)%', text, re.IGNORECASE)
    if m_bf:
        extracted["key_price_drivers"]["bf_operating_rate_pct"] = float(m_bf.group(1))
    m_cap = re.search(r'capacity utilisation\s+(?:was|at|stood at|of)\s+([\d\.]+)%', text, re.IGNORECASE)
    if m_cap:
        extracted["key_price_drivers"]["bf_capacity_utilisation_pct"] = float(m_cap.group(1))
    m_p10 = re.search(r'(?:(?:10-port\s+(?:total|inventory|iron ore inventory|stocks)|inventory across the 10 major ports)\s*(?:was|at|stood at|reached|fell[^\n]*?to|rose[^\n]*?to|\()?\s*([\d\.]+)\s*million\s*mt|([\d\.]+)\s*million\s*mt\s+across\s+10\s+ports)', text, re.IGNORECASE)
    if m_p10:
        extracted["key_price_drivers"]["port_inventory_10_ports_mt_million"] = float(m_p10.group(1) or m_p10.group(2))
    m_p35 = re.search(r'(?:35-port\s+(?:inventory|total|stocks)\s+(?:was|at|stood at|reached|fell[^\n]*?to|rose[^\n]*?to)?\s*([\d\.]+)\s*million\s*mt|([\d\.]+)\s*million\s*mt\s+across\s+35\s+ports)', text, re.IGNORECASE)
    if m_p35:
        extracted["key_price_drivers"]["port_inventory_35_ports_mt_million"] = float(m_p35.group(1) or m_p35.group(2))
    m_out = re.search(r'daily outbound volume\s+(?:was|at|stood at|averaged)?\s*([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_out:
        extracted["key_price_drivers"]["daily_outbound_volume_mt_million"] = float(m_out.group(1))
    m_mstk = re.search(r'imported ore stocks at 242(?:\s+steel)?\s+mills\s+(?:were|was|at|stood at)?\s*([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_mstk:
        extracted["key_price_drivers"]["mill_imported_stocks_242_mills_mt_million"] = float(m_mstk.group(1))
    m_mday = re.search(r'with\s+([\d\.]+)\s+days of cover', text, re.IGNORECASE)
    if m_mday:
        extracted["key_price_drivers"]["mill_stocks_cover_days"] = float(m_mday.group(1))
    m_ship = re.search(r'Global\s+(?:iron ore\s+)?shipments[^\n]*?(?:were|at|totaled|reached|to)\s+([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_ship:
        extracted["key_price_drivers"]["global_shipments_mt_million"] = float(m_ship.group(1))
    m_arr = re.search(r'arrivals\s+(?:at Chinese ports|in China)[^\n]*?(?:were|at|totaled|reached|to|fell[^\n]*?to|rose[^\n]*?to)?\s+([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_arr:
        extracted["key_price_drivers"]["arrivals_chinese_ports_mt_million"] = float(m_arr.group(1))
    m_dom_u = re.search(r'(?:domestic mine capacity utilisation\s+(?:rose to|fell to|was|at|stood at)\s+([\d\.]+)%|([\d\.]+)%\s+mine capacity utilisation rate)', text, re.IGNORECASE)
    if m_dom_u:
        extracted["key_price_drivers"]["domestic_mine_capacity_utilisation_pct"] = float(m_dom_u.group(1) or m_dom_u.group(2))

    # 13. Flash News (handles both 'Last 2 days' and holiday subheaders, joining wrapped lines per item)
    m_fn = re.search(r'Flash News\s*\n(?:Last \d+ days[^\n]*|No SMM items[^\n]*)\n(.*?)\nContact Us', text, re.DOTALL)
    if m_fn:
        fn_raw = m_fn.group(1).strip()
        if '↗' in fn_raw:
            fn_items = [item.strip() for item in fn_raw.split('↗') if item.strip()]
            fn_lines = [re.sub(r'\s{2,}', ' ', re.sub(r'^[•\-\*]\s*', '', item.replace('\n', ' ').strip())) for item in fn_items if len(item.strip()) > 15]
        else:
            fn_lines = [re.sub(r'^[•\-\*]\s*', '', l.strip()) for l in fn_raw.split('\n') if len(l.strip()) > 15]
        extracted["flash_news"] = fn_lines

    doc.close()
    return extracted


def generate_smm_markdown(data: Dict[str, Any]) -> str:
    """Format complete publication-grade GitHub Markdown report for SMM Iron Ore Daily."""
    meta = data["metadata"]
    issue_date = meta["issue_date"]
    day_of_week = meta.get("day_of_week", "")
    charts = data.get("chart_images", {})

    lines: List[str] = [
        "---",
        f'title: "{meta["title"]}"',
        f'subtitle: "Imported & Domestic Ore · Prices · Supply-Demand · Inventory · Commentary"',
        f'issue_date: "{issue_date}"',
        f'day_of_week: "{day_of_week}"',
        f'year: {meta["year"]}',
        f'publisher: "{meta["publisher"]}"',
        f'source: "hellenic"',
        f'category: "iron_ore"',
        f'pages: {meta["page_count"]}',
        f'source_file: "{meta["source_file"]}"',
        f'pipeline_version: "smm_v1_complete"',
        "---",
        "",
        f"# SMM Iron Ore Daily — {issue_date} ({day_of_week})",
        "",
        "**Source:** SMM Data-pro · Shanghai Metals Market (SMM)",
        "",
        "---",
        "",
        "## Futures Contracts",
        "",
        "| Exchange | Contract | Price | Unit | Daily Change | Daily Change % | MTD Avg |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|"
    ]

    for f in data.get("futures_contracts", []):
        chg_sign = f"+{f['change']}" if f["change"] > 0 else str(f["change"])
        lines.append(f"| {f['exchange']} | {f['contract']} | {f['price']:.2f} | {f['unit']} | {chg_sign} | {f['change_pct']} | {f['mtd_avg']:.2f} |")

    lines.extend([
        "",
        "## SMM Iron Ore Price Index (Physical & Benchmark Indices)",
        "",
        "| Index Name | Market Type | Fe % | Price | Unit | Daily Change | Daily Change % | MTD Avg |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|"
    ])

    for idx in data.get("smm_price_index_summary", []):
        chg_sign = f"+{idx['change']}" if idx["change"] > 0 else str(idx["change"])
        lines.append(f"| {idx['index_name']} | {idx['market_type']} | {idx['fe_content']}% | {idx['price']:.2f} | {idx['unit']} | {chg_sign} | {idx['change_pct']} | {idx['mtd_avg']:.2f} |")

    # Key View
    kv = data.get("key_view", {})
    if kv:
        lines.extend([
            "",
            "## Key View",
            "",
            f"### {kv.get('headline', '')}",
            "",
            kv.get("body", "")
        ])

    # Today's Highlights
    th = data.get("todays_highlights", [])
    if th:
        lines.extend([
            "",
            "## Today's Highlights",
            ""
        ])
        for b in th:
            lines.append(f"- {b}")

    # Qingdao Spot CNY Table
    qd_cny = data.get("qingdao_port_spot_cny", [])
    if qd_cny:
        lines.extend([
            "",
            "## Qingdao Port Imported Ore Spot Prices (yuan/wet mt, tax incl.)",
            "",
            "| Product | Fe % | Type | Price (yuan/wmt) | Daily Change | Daily Change % | MTD Avg |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|"
        ])
        for r in qd_cny:
            chg_sign = f"+{r['change']}" if r["change"] > 0 else str(r["change"])
            lines.append(f"| {r['product']} | {r['fe_pct']}% | {r['product_type']} | {r['price_yuan_wmt']:.1f} | {chg_sign} | {r['change_pct']} | {r['mtd_avg']:.1f} |")

    # Imported Ore USD Table
    imp_usd = data.get("imported_ore_usd_prices", [])
    if imp_usd:
        lines.extend([
            "",
            "## Imported Ore USD Prices & MMi Indices (CFR Qingdao, USD/dry mt)",
            "",
            "| Product | Fe % | Type | Price (USD/dmt) | Daily Change | Daily Change % | MTD Avg |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|"
        ])
        for r in imp_usd:
            chg_sign = f"+{r['change']}" if r["change"] > 0 else str(r["change"])
            lines.append(f"| {r['product']} | {r['fe_pct']}% | {r['product_type']} | {r['price_usd_dmt']:.2f} | {chg_sign} | {r['change_pct']} | {r['mtd_avg']:.2f} |")

    # Index Stats Weekly / Monthly
    idx_stats = data.get("index_statistics_weekly_monthly", [])
    if idx_stats:
        lines.extend([
            "",
            "## SMM Iron Ore Price Index — Weekly / Monthly Statistics",
            "",
            "| Index Name | Month-to-date Avg | MoM % | YTD % | Unit |",
            "|:---|:---:|:---:|:---:|:---:|"
        ])
        for r in idx_stats:
            lines.append(f"| {r['index_name']} | {r['mtd_avg']:.2f} | {r['mom_pct']} | {r['ytd_pct']} | {r['unit']} |")

    # Key Price Drivers & Charts
    lines.extend([
        "",
        "## Key Price Drivers (12-Month Charts & Operational Metrics)",
        ""
    ])

    if "ocean_freight" in charts and "port_inventory" in charts:
        lines.extend([
            "### Charts: Freight & Port Inventory",
            "",
            f"![Iron Ore Ocean Freight]({charts['ocean_freight']})",
            "",
            f"![Iron Ore Port Inventory at 10 Ports by Product]({charts['port_inventory']})",
            ""
        ])

    if "hot_metal_bf" in charts and "shipments_arrivals" in charts:
        lines.extend([
            "### Charts: Hot Metal Output & Shipments vs Arrivals",
            "",
            f"![Daily Avg Hot Metal Output & BF Operating Rate]({charts['hot_metal_bf']})",
            "",
            f"![Global Iron Ore Shipments vs Arrivals at Chinese Ports]({charts['shipments_arrivals']})",
            ""
        ])

    kpd = data.get("key_price_drivers", {})
    if kpd:
        kpd_label_map = {
            "freight_c3_usd_mt": ("C3 Freight (Brazil to China)", "USD/mt"),
            "freight_c5_usd_mt": ("C5 Freight (Australia to China)", "USD/mt"),
            "hot_metal_daily_avg_mt_million": ("Daily Avg Hot Metal Output (242 Mills)", "Million MT"),
            "bf_operating_rate_pct": ("Blast Furnace Operating Rate (242 Mills)", "%"),
            "bf_capacity_utilisation_pct": ("Blast Furnace Capacity Utilisation (242 Mills)", "%"),
            "port_inventory_10_ports_mt_million": ("Iron Ore Port Inventory (10 Major Ports)", "Million MT"),
            "port_inventory_35_ports_mt_million": ("Iron Ore Port Inventory (35 Major Ports)", "Million MT"),
            "daily_outbound_volume_mt_million": ("Daily Avg Port Outbound Volume", "Million MT"),
            "mill_imported_stocks_242_mills_mt_million": ("Imported Ore Stocks (242 Steel Mills)", "Million MT"),
            "mill_stocks_cover_days": ("Steel Mill Imported Ore Inventory Cover", "Days"),
            "global_shipments_mt_million": ("Global Iron Ore Shipments (Weekly)", "Million MT"),
            "arrivals_chinese_ports_mt_million": ("Chinese Port Arrivals (Weekly)", "Million MT"),
            "domestic_mine_capacity_utilisation_pct": ("Domestic Mine Capacity Utilisation", "%"),
        }
        lines.extend([
            "### Operational Fundamentals Snapshot",
            "",
            "| Fundamental Indicator | Value | Unit |",
            "|:---|:---:|:---:|"
        ])
        for k, v in kpd.items():
            if k in kpd_label_map:
                label, unit = kpd_label_map[k]
            else:
                label = k.replace("_", " ").title()
                unit = "%" if "pct" in k else ("USD/mt" if "usd" in k else ("Days" if "days" in k else "Million MT"))
            lines.append(f"| {label} | {v} | {unit} |")

    # Market Commentary - Imported Ore
    mc_imp = data.get("market_commentary_imported", {})
    if mc_imp:
        lines.extend([
            "",
            "## Market Commentary · Imported Ore",
            ""
        ])
        for sec, text in mc_imp.items():
            lines.extend([
                f"### {sec}",
                "",
                text,
                ""
            ])

    # Market Commentary - Domestic Ore
    mc_dom = data.get("market_commentary_domestic", {})
    if mc_dom:
        lines.extend([
            "",
            "## Market Commentary · Domestic Ore",
            ""
        ])
        for sec, text in mc_dom.items():
            lines.extend([
                f"### {sec}",
                "",
                text,
                ""
            ])

    # Market Factors
    mf = data.get("market_factors", {})
    if mf.get("supportive") or mf.get("bearish"):
        lines.extend([
            "",
            "## Market Factors",
            "",
            "### Supportive Factors",
            ""
        ])
        for s in mf.get("supportive", []):
            lines.append(f"- {s}")
        lines.extend([
            "",
            "### Bearish Factors",
            ""
        ])
        for b in mf.get("bearish", []):
            lines.append(f"- {b}")

    # Flash News
    fn = data.get("flash_news", [])
    if fn:
        lines.extend([
            "",
            "## Flash News Briefs",
            ""
        ])
        for n in fn:
            lines.append(f"- {n}")

    lines.extend([
        "",
        "---",
        "*(c) 2026 Shanghai Metals Market (SMM) · Iron Ore Value-Chain Data & Research*"
    ])

    return "\n".join(lines) + "\n"


def upsert_rows_to_csv(csv_path: Path, new_rows: List[Dict[str, Any]], key_fields: List[str], all_fields: List[str]) -> int:
    """Safely append/upsert rows into a time series CSV using composite-key deduplication."""
    existing_rows: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    if csv_path.exists() and csv_path.stat().st_size > 0:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                k = tuple(str(row.get(kf, "")).strip() for kf in key_fields)
                existing_rows[k] = row

    added = 0
    for r in new_rows:
        k = tuple(str(r.get(kf, "")).strip() for kf in key_fields)
        if k not in existing_rows:
            added += 1
        existing_rows[k] = r

    # Write back sorted
    sorted_rows = sorted(existing_rows.values(), key=lambda x: [str(x.get(kf, "")) for kf in key_fields])
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    return added


def update_master_series(data: Dict[str, Any], pdf_stem: str) -> None:
    """Update master time series CSVs with records from the SMM 1-page report."""
    meta = data["metadata"]
    issue_date = meta["issue_date"]
    year = meta["year"]
    source_file = meta["source_file"]

    # 1. Dashboard Series (Futures, Spot cards, Freight, Key Drivers)
    dash_rows = []
    for f in data.get("futures_contracts", []):
        dash_rows.append({
            "date": issue_date,
            "year": year,
            "indicator": f["contract"],
            "value": f["price"],
            "unit": f["unit"],
            "change": f["change"],
            "source_file": source_file
        })
    for idx in data.get("smm_price_index_summary", []):
        dash_rows.append({
            "date": issue_date,
            "year": year,
            "indicator": idx["index_name"],
            "value": idx["price"],
            "unit": idx["unit"],
            "change": idx["change"],
            "source_file": source_file
        })
    kpd = data.get("key_price_drivers", {})
    for k, v in kpd.items():
        dash_rows.append({
            "date": issue_date,
            "year": year,
            "indicator": k,
            "value": v,
            "unit": "pct" if "pct" in k else ("USD/mt" if "usd" in k else "mt_m"),
            "change": 0.0,
            "source_file": source_file
        })
    p_dash = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_dashboard_series.csv"
    upsert_rows_to_csv(p_dash, dash_rows, ["date", "indicator"], ["date", "year", "indicator", "value", "unit", "change", "source_file"])

    # 2. Indices Series
    idx_rows = []
    for idx in data.get("smm_price_index_summary", []):
        idx_rows.append({
            "date": issue_date,
            "year": year,
            "index_name": idx["index_name"],
            "market_type": idx["market_type"],
            "fe_content": idx["fe_content"],
            "value": idx["price"],
            "unit": idx["unit"],
            "change": idx["change"],
            "change_pct": idx["change_pct"],
            "source_file": source_file
        })
    p_idx = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_indices_series.csv"
    upsert_rows_to_csv(p_idx, idx_rows, ["date", "index_name"], ["date", "year", "index_name", "market_type", "fe_content", "value", "unit", "change", "change_pct", "source_file"])

    # 3. Brands Series (Qingdao CNY & CFR Qingdao USD)
    brand_rows = []
    for r in data.get("qingdao_port_spot_cny", []):
        brand_rows.append({
            "date": issue_date,
            "year": year,
            "brand": r["product"],
            "market_type": "port_stock_cny",
            "fe_pct": r["fe_pct"],
            "product_type": r["product_type"],
            "price": r["price_yuan_wmt"],
            "unit": r["unit"],
            "change": r["change"],
            "change_pct": r["change_pct"],
            "source_file": source_file
        })
    for r in data.get("imported_ore_usd_prices", []):
        brand_rows.append({
            "date": issue_date,
            "year": year,
            "brand": r["product"],
            "market_type": "seaborne_usd",
            "fe_pct": r["fe_pct"],
            "product_type": r["product_type"],
            "price": r["price_usd_dmt"],
            "unit": r["unit"],
            "change": r["change"],
            "change_pct": r["change_pct"],
            "source_file": source_file
        })
    p_brand = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_brands_series.csv"
    upsert_rows_to_csv(p_brand, brand_rows, ["date", "brand", "market_type"], ["date", "year", "brand", "market_type", "fe_pct", "product_type", "price", "unit", "change", "change_pct", "source_file"])

    # 4. Futures Series
    fut_rows = []
    for f in data.get("futures_contracts", []):
        fut_rows.append({
            "date": issue_date,
            "year": year,
            "exchange": f["exchange"],
            "contract": f["contract"],
            "price": f["price"],
            "unit": f["unit"],
            "change": f["change"],
            "change_pct": f["change_pct"],
            "settlement": "daily",
            "source_file": source_file
        })
    p_fut = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_futures_series.csv"
    upsert_rows_to_csv(p_fut, fut_rows, ["date", "contract"], ["date", "year", "exchange", "contract", "price", "unit", "change", "change_pct", "settlement", "source_file"])

    # 5. Averages Series (Weekly / Monthly stats)
    avg_rows = []
    for s in data.get("index_statistics_weekly_monthly", []):
        avg_rows.append({
            "date": issue_date,
            "year": year,
            "index_name": s["index_name"],
            "market_type": "index_stat",
            "fe_content": 62.0,
            "unit": s["unit"],
            "m_minus_4": None,
            "m_minus_3": None,
            "m_minus_2": None,
            "m_minus_1": None,
            "mtd": s["mtd_avg"],
            "qtd": None,
            "ytd": s["ytd_pct"],
            "source_file": source_file
        })
    p_avg = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_averages_series.csv"
    upsert_rows_to_csv(p_avg, avg_rows, ["date", "index_name"], ["date", "year", "index_name", "market_type", "fe_content", "unit", "m_minus_4", "m_minus_3", "m_minus_2", "m_minus_1", "mtd", "qtd", "ytd", "source_file"])

    # 6. SMM Market Drivers Series (Operational fundamentals)
    if kpd:
        drv_row = {
            "date": issue_date,
            "year": year,
            "freight_c3_usd_mt": kpd.get("freight_c3_usd_mt"),
            "freight_c5_usd_mt": kpd.get("freight_c5_usd_mt"),
            "hot_metal_daily_avg_mt_million": kpd.get("hot_metal_daily_avg_mt_million"),
            "bf_operating_rate_pct": kpd.get("bf_operating_rate_pct"),
            "bf_capacity_utilisation_pct": kpd.get("bf_capacity_utilisation_pct"),
            "port_inventory_10_ports_mt_million": kpd.get("port_inventory_10_ports_mt_million"),
            "port_inventory_35_ports_mt_million": kpd.get("port_inventory_35_ports_mt_million"),
            "daily_outbound_volume_mt_million": kpd.get("daily_outbound_volume_mt_million"),
            "mill_imported_stocks_242_mills_mt_million": kpd.get("mill_imported_stocks_242_mills_mt_million"),
            "mill_stocks_cover_days": kpd.get("mill_stocks_cover_days"),
            "global_shipments_mt_million": kpd.get("global_shipments_mt_million"),
            "arrivals_chinese_ports_mt_million": kpd.get("arrivals_chinese_ports_mt_million"),
            "domestic_mine_capacity_utilisation_pct": kpd.get("domestic_mine_capacity_utilisation_pct"),
            "source_file": source_file
        }
        p_drv = OUT_SERIES_DIR / "hellenic_smm_market_drivers_series.csv"
        drv_fields = list(drv_row.keys())
        upsert_rows_to_csv(p_drv, [drv_row], ["date"], drv_fields)


def process_single_smm_report(pdf_path: Path) -> Dict[str, Any]:
    """Process an SMM 1-page report and write .md, .tables.json, and time series rows."""
    data = parse_smm_single_page_pdf(pdf_path)
    meta = data["metadata"]
    year = meta["year"]
    stem = pdf_path.stem

    out_year_dir = OUT_MD_DIR / year
    out_year_dir.mkdir(parents=True, exist_ok=True)
    md_file = out_year_dir / f"{stem}.md"
    json_file = out_year_dir / f"{stem}.tables.json"

    # Write Markdown
    md_content = generate_smm_markdown(data)
    md_file.write_text(md_content, encoding="utf-8")

    # Write Sidecar JSON
    json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Update Series CSVs
    update_master_series(data, stem)

    return {
        "status": "ok",
        "issue_date": meta["issue_date"],
        "source_file": pdf_path.name,
        "md_file": str(md_file),
        "md_size": len(md_content)
    }


def get_all_1page_reports(pdf_root: Path) -> List[Path]:
    """Find all 1-page SMM reports across the corpus (format introduced in 2026)."""
    all_files: List[Path] = []
    candidates: List[Path] = list(pdf_root.glob("*.pdf"))
    for yr_dir in sorted(pdf_root.iterdir()):
        if yr_dir.is_dir():
            try:
                yr_val = int(yr_dir.name)
                if yr_val >= 2026:
                    candidates.extend(yr_dir.glob("*.pdf"))
            except ValueError:
                candidates.extend(yr_dir.glob("*.pdf"))

    for f in sorted(candidates):
        try:
            doc = pymupdf.open(str(f))
            if len(doc) == 1:
                all_files.append(f)
            doc.close()
        except Exception:
            continue
    return all_files


def main():
    parser = argparse.ArgumentParser(description="SMM Iron Ore Daily Single-Page Pipeline")
    parser.add_argument("--all", action="store_true", help="Process all 1-page reports in corpus")
    parser.add_argument("--file", type=str, default=None, help="Process a specific PDF file")
    args = parser.parse_args()

    if args.file:
        target_files = [Path(args.file)]
    else:
        print("Discovering all 1-page SMM Iron Ore PDFs...", flush=True)
        target_files = get_all_1page_reports(PDF_CORPUS_DIR)

    print(f"Targeting {len(target_files)} SMM reports...", flush=True)

    success = 0
    errors = 0
    for p in target_files:
        try:
            res = process_single_smm_report(p)
            print(f"[OK] {res['issue_date']} | {p.name[:50]}... | MD: {res['md_size']} bytes", flush=True)
            success += 1
        except Exception as e:
            errors += 1
            print(f"[ERROR] {p.name}: {e}", flush=True)

    print(f"\nCompleted SMM single-page pipeline: {success} succeeded, {errors} errors.")


if __name__ == "__main__":
    main()
