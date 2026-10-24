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
import io
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


# --- line readers -------------------------------------------------------------------------------------------
# The report's cards and tables are read line by line from the text layer, not by one regex over the page: the
# 2026-10-06 redesign put units on their own line, wrapped card titles ("MMi 61% Seaborne / Index"), replaced the
# SGX most-traded card with a current-month latest-price card, printed "Market closed" for the holiday and dropped
# the Flash News sub-header, and the page-wide regexes matched none of it (tables, flash news and half the cards
# went missing from 2026-10-06 on).
_NUM = re.compile(r'^([\d,]+(?:\.\d+)?)(?:\s+([A-Za-z]+/[A-Za-z]+))?$')
_CHG = re.compile(r'^(?:([▲▼—])\s*)?([+\-]?[\d\.]+)\s+([+\-]?[\d\.]+%)$')
_CLOSED = re.compile(r'^(?:No quotation(?: \(holiday\))?|Market closed)$')


def _section_lines(text: str, start: str, end: str) -> List[str]:
    """Stripped non-empty lines between a heading and the next heading (both regexes, matched across wraps)."""
    m = re.search(start + r'(.*?)(?=' + end + r')', text, re.DOTALL)
    return [l.strip() for l in m.group(1).split("\n") if l.strip()] if m else []


def _quote_after(lines: List[str], i: int) -> Optional[Dict[str, Any]]:
    """Read one quote from lines[i:] (the line after "Daily" / "Latest price"): price, unit, change or closed
    status, and the closing figure (MTD avg, previous-day price or prior-month avg)."""
    m = _NUM.match(lines[i]) if i < len(lines) else None
    if not m:
        return None
    q: Dict[str, Any] = {"price": float(m.group(1).replace(",", "")), "unit": m.group(2), "change": None,
                         "change_pct": None, "closed": False, "tail": None, "tail_kind": None, "code": None}
    i += 1
    if q["unit"] is None and i < len(lines) and re.match(r'^[A-Za-z]+/[A-Za-z]+$', lines[i]):
        q["unit"] = lines[i]
        i += 1
    if i < len(lines):
        c = _CHG.match(lines[i])
        if c:
            q["change"] = parse_change_val(f"{c.group(1) or ''} {c.group(2)}")
            q["change_pct"] = c.group(3)
            i += 1
        elif _CLOSED.match(lines[i]):
            q["closed"] = True
            i += 1
            if i < len(lines) and re.match(r'^as of [\d\-]+$', lines[i]):
                i += 1
        elif re.match(r'^[A-Z]{2,5}[A-Z]\d{2}\b', lines[i]):     # SGX card: "FEFV26 · 2026-10 · SGX"
            q["code"] = lines[i].split("·")[0].strip()
            i += 1
    if i < len(lines):
        t = re.match(r'^(?:as of [\d\-]+\s*·\s*)?(MTD avg|\d{4}-\d{2} avg)\s+([\d\.]+)$', lines[i])
        if t:
            q["tail"], q["tail_kind"] = float(t.group(2)), ("mtd" if t.group(1) == "MTD avg" else "prior_month")
            # "Closed for the National Day holiday · close as of Sep 30": the card repeats an earlier close
            if i + 1 < len(lines) and lines[i + 1].startswith("Closed for"):
                q["closed_note"] = lines[i + 1]
        elif _NUM.match(lines[i]) and not _NUM.match(lines[i]).group(2):
            q["tail"], q["tail_kind"] = float(lines[i].replace(",", "")), "column"
            # a table's MTD column holds the prior month's average, marked on the next line, until the first quote
            p = re.match(r'^(\d{4}-\d{2}) avg$', lines[i + 1]) if i + 1 < len(lines) else None
            if p:
                q["tail_kind"], q["tail_period"] = "prior_month", p.group(1)
    return q


def _card(text: str, title: str) -> Optional[Dict[str, Any]]:
    """The dashboard card whose title (words may wrap across lines) is `title`."""
    m = re.search(r'(?m)^' + r'\s+'.join(re.escape(w) for w in title.split()) + r'\s*$', text)
    if not m:
        return None
    lines = [l.strip() for l in text[m.end():m.end() + 600].split("\n") if l.strip()]
    for i, l in enumerate(lines[:4]):
        if l in ("Daily", "Latest price"):
            return _quote_after(lines, i + 1)
    return None


def _table_rows(lines: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
    """(product, quote) for every "<product> / Daily / <price> / <change> / <last column>" row of a table."""
    out = []
    for i, l in enumerate(lines):
        if l == "Daily" and i > 0:
            q = _quote_after(lines, i + 1)
            if q:
                out.append((lines[i - 1], q))
    return out


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
        "seaborne_brand_usd": [],
        "index_statistics_weekly_monthly": [],
        "key_price_drivers": {},
        "market_commentary_imported": {},
        "market_commentary_domestic": {},
        "market_factors": {"supportive": [], "bearish": []},
        "flash_news": []
    }

    # 2. Futures Contracts (SGX most-traded card until 2026-10-06, current-month latest price from 2026-10-07; DCE)
    for title, contract in (("SGX Iron Ore Most-traded Contract", "SGX Iron Ore Most-traded"),
                            ("SGX Iron Ore Current-month Contract", "SGX Iron Ore Current-month")):
        q = _card(text, title)
        if q:
            extracted["futures_contracts"].append({
                "exchange": "SGX",
                "contract": f"{contract} {q['code']}" if q["code"] else contract,
                "price": q["price"],
                "unit": q["unit"] or "USD/dmt",
                "change": 0.0 if q["closed"] else q["change"],
                "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
                "mtd_avg": q["tail"] if q["tail_kind"] == "mtd" else None,
                **({"closed_note": q["closed_note"]} if q.get("closed_note") else {})
            })
    m_dce = re.search(r'(?m)^(DCE Iron Ore Most-traded(?:\s+([A-Za-z0-9]+))?)\s*$', text)
    q = _card(text, m_dce.group(1)) if m_dce else None
    if q:
        c_code = m_dce.group(2) or "Contract"
        extracted["futures_contracts"].append({
            "exchange": "DCE",
            "contract": f"DCE Iron Ore Most-traded {c_code}".strip(),
            "contract_code": c_code,
            "price": q["price"],
            "unit": q["unit"] or "yuan/mt",
            "change": 0.0 if q["closed"] else q["change"],
            "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
            "mtd_avg": q["tail"] if q["tail_kind"] == "mtd" else None,
            **({"closed_note": q["closed_note"]} if q.get("closed_note") else {})
        })

    # 3. SMM Iron Ore Price Index (top 6 cards; a closed market prints its last quote, kept as a 0.00% holiday row)
    idx_defs = [
        ("MMi 61% Port Spot", "yuan/wmt", 61.0, "port_spot"),
        ("MMi 58% Port Spot", "yuan/wmt", 58.0, "port_spot"),
        ("MMi 65% Port Spot", "yuan/wmt", 65.0, "port_spot"),
        ("MMi 61% Seaborne Index", "USD/dmt", 61.0, "seaborne"),
        ("MMi 65% Seaborne Index", "USD/dmt", 65.0, "seaborne"),
        ("SMM Domestic Ore Composite Index", "yuan/mt", 66.0, "domestic_composite")
    ]
    for name, unit, fe, mkt in idx_defs:
        q = _card(text, name)
        if q:
            extracted["smm_price_index_summary"].append({
                "index_name": name,
                "market_type": mkt,
                "fe_content": fe,
                "price": q["price"],
                "unit": q["unit"] or unit,
                "change": 0.0 if q["closed"] else q["change"],
                "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
                "mtd_avg": q["tail"] if q["tail_kind"] == "mtd" else None,
                **({"closed_note": q["closed_note"]} if q.get("closed_note") else {})
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
    qd_lines = _section_lines(text, r'Qingdao Port Imported Ore Spot\s+Prices',
                              r'\nImported Ore USD Prices|\nSeaborne Brand Prices in USD')
    for prod, q in _table_rows(qd_lines):
        m_fe = re.search(r'(\d+(?:\.\d+)?)%', prod)
        extracted["qingdao_port_spot_cny"].append({
            "product": prod,
            "fe_pct": float(m_fe.group(1)) if m_fe else 62.0,
            "product_type": "Lump" if "Lump" in prod else "Fines",
            "price_yuan_wmt": q["price"],
            "change": 0.0 if q["closed"] else q["change"],
            "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
            "mtd_avg": q["tail"],
            "unit": "yuan/wmt",
            **({"avg_period": q["tail_period"]} if q.get("tail_period") else {})
        })

    # 7. Imported Ore USD Prices & MMi Indices (port spot converted to USD, with MTD avg; printed until 2026-10-05)
    usd_lines = _section_lines(text, r'Imported Ore USD Prices & MMi\s+Indices',
                               r'\nSeaborne Fines Prices in USD|\nSMM Iron Ore Price Index\s+weekly')
    for prod, q in _table_rows(usd_lines):
        m_fe = re.search(r'(\d+(?:\.\d+)?)%', prod)
        extracted["imported_ore_usd_prices"].append({
            "product": prod,
            "fe_pct": float(m_fe.group(1)) if m_fe else 62.0,
            "product_type": "Index" if "Index" in prod else ("Lump" if "Lump" in prod else "Fines"),
            "price_usd_dmt": q["price"],
            "change": 0.0 if q["closed"] else q["change"],
            "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
            "mtd_avg": q["tail"],
            "unit": "USD/dmt",
            **({"avg_period": q["tail_period"]} if q.get("tail_period") else {})
        })

    # 7b. Seaborne brand prices in USD, CFR Qingdao (columns: price on the header date, change, previous price).
    # Printed under the USD table until 2026-10-05 ("Seaborne Fines Prices") and alone after; its quotes can lag
    # the issue (the 2026-10-05 issue prints Oct 2), so each row carries the header's price date.
    sb_m = re.search(r'Seaborne (?:Fines|Brand) Prices in USD CFR Qingdao[^\n]*\nProduct\n(\d{2})-(\d{2})', text)
    sb_lines = _section_lines(text, r'Seaborne (?:Fines|Brand) Prices in USD CFR Qingdao',
                              r'\nSMM Iron Ore Price Index\s+(?:weekly / )?monthly')
    for prod, q in (_table_rows(sb_lines) if sb_m else []):
        mm, dd = int(sb_m.group(1)), int(sb_m.group(2))
        yr = int(year) - (1 if mm > int(issue_date[5:7]) else 0)
        m_fe = None if re.search(r'%\s*-', prod) else re.search(r'(\d+(?:\.\d+)?)%', prod)   # "59%-60%": a range
        extracted["seaborne_brand_usd"].append({
            "product": prod,
            "price_date": f"{yr}-{mm:02d}-{dd:02d}",
            "fe_pct": float(m_fe.group(1)) if m_fe else None,
            "product_type": "Lump" if "Lump" in prod else "Fines",
            "price_usd_dmt": q["price"],
            "change": 0.0 if q["closed"] else q["change"],
            "change_pct": "0.00% (Holiday)" if q["closed"] else q["change_pct"],
            "prev_price": q["tail"],
            "unit": "USD/dmt"
        })

    # 8. SMM Iron Ore Price Index weekly / monthly statistics. Before a month's first quote (the October holiday)
    # a row prints the prior month's average marked "2026-09 avg"; that row keeps its period and is not an MTD.
    st_lines = _section_lines(text, r'SMM Iron Ore Price Index\s+(?:weekly / )?monthly statistics',
                              r'\nKey Price Drivers')
    for i, l in enumerate(st_lines):
        if l == "Daily" and i > 0 and i + 4 < len(st_lines) and re.search(r'Index$', st_lines[i - 1]):
            vals = st_lines[i + 1:i + 6]
            m_per = re.match(r'^(\d{4}-\d{2}) avg$', vals[1]) if len(vals) > 1 else None
            if m_per:
                vals = vals[:1] + vals[2:]
            if len(vals) < 4:
                continue
            mtd, mom, ytd, unit = vals[:4]
            if _NUM.match(mtd) and mom.endswith("%") and ytd.endswith("%"):
                row = {
                    "index_name": st_lines[i - 1],
                    "mtd_avg": float(mtd.replace(",", "")),
                    "mom_pct": mom,
                    "ytd_pct": ytd,
                    "unit": unit
                }
                if m_per:
                    row["avg_period"] = m_per.group(1)
                extracted["index_statistics_weekly_monthly"].append(row)

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
    m_p10 = re.search(r'(?:(?:(?:10|ten)-port\s+(?:total|inventory|iron ore inventory|stocks)|inventory across the 10 major ports)\s*(?:was|were|at|stood at|reached|fell[^\n]*?to|rose[^\n]*?to|\()?\s*([\d\.]+)\s*million\s*mt|([\d\.]+)\s*million\s*mt\s+across\s+10\s+ports)', text, re.IGNORECASE)
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
    # "Global shipments and (Chinese) arrivals (in China) ... were X (million mt) and Y million mt": one sentence
    # carries both, and the single-figure patterns below would read X for arrivals too
    m_sa = re.search(r'Global\s+shipments\s+and\s+(?:Chinese\s+)?arrivals(?:\s+in\s+China|\s+at\s+Chinese\s+ports)?'
                     r'(?:\s+in\s+the\s+week\s+to\s+[A-Z][a-z]{2}\s+\d{1,2})?,?\s+were\s+([\d\.]+)(?:\s+million\s+mt)?\s+and\s+'
                     r'([\d\.]+)\s+million\s+mt', text, re.IGNORECASE)
    if m_sa:
        extracted["key_price_drivers"]["global_shipments_mt_million"] = float(m_sa.group(1))
        extracted["key_price_drivers"]["arrivals_chinese_ports_mt_million"] = float(m_sa.group(2))
    m_ship = None if m_sa else re.search(r'Global\s+(?:iron ore\s+)?shipments[^\n]*?(?:were|at|totaled|reached|to)\s+([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_ship:
        extracted["key_price_drivers"]["global_shipments_mt_million"] = float(m_ship.group(1))
    m_arr = None if m_sa else re.search(r'arrivals\s+(?:at Chinese ports|in China)[^\n]*?(?:were|at|totaled|reached|to|fell[^\n]*?to|rose[^\n]*?to)?\s+([\d\.]+)\s*million\s*mt', text, re.IGNORECASE)
    if m_arr:
        extracted["key_price_drivers"]["arrivals_chinese_ports_mt_million"] = float(m_arr.group(1))
    m_dom_u = re.search(r'(?:domestic mine capacity utilisation\s+(?:rose to|fell to|was|at|stood at)\s+([\d\.]+)%|([\d\.]+)%\s+mine capacity utilisation rate)', text, re.IGNORECASE)
    if m_dom_u:
        extracted["key_price_drivers"]["domestic_mine_capacity_utilisation_pct"] = float(m_dom_u.group(1) or m_dom_u.group(2))

    # 13. Flash News (sub-header 'Last 2 days' / holiday note until 2026-10-05, none after; each item ends at the
    # arrow glyph and from 2026-10-06 carries its date on its last line)
    m_fn = re.search(r'Flash News\s*\n(?:(?:Last \d+ days|No SMM items)[^\n]*\n)?(.*?)\nContact Us', text, re.DOTALL)
    if m_fn:
        fn_raw = m_fn.group(1).strip()
        if '↗' in fn_raw:
            fn_lines = []
            for item in fn_raw.split('↗'):
                item = item.strip()
                m_d = re.search(r'\n(\d{4}-\d{2}-\d{2})$', item)
                body = item[:m_d.start()] if m_d else item
                body = re.sub(r'\s{2,}', ' ', re.sub(r'^[•\-\*]\s*', '', body.replace('\n', ' ').strip()))
                if len(body) > 15:
                    fn_lines.append(f"{body} ({m_d.group(1)})" if m_d else body)
        else:
            fn_lines = [re.sub(r'^[•\-\*]\s*', '', l.strip()) for l in fn_raw.split('\n') if len(l.strip()) > 15]
        extracted["flash_news"] = fn_lines

    doc.close()
    return extracted


def _md_chg(v: Optional[float]) -> str:
    """A change cell: signed, or a dash where the report prints no change (SGX latest-price card)."""
    return "—" if v is None else (f"+{v}" if v > 0 else str(v))


def _md_num(v: Optional[float], nd: int) -> str:
    return "—" if v is None else f"{v:.{nd}f}"


def _md_avg(r: Dict[str, Any], nd: int) -> str:
    """An MTD-average cell; the prior month's average (printed before a month's first quote) says so."""
    return _md_num(r["mtd_avg"], nd) + (f" ({r['avg_period']} avg)" if r.get("avg_period") else "")


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
        lines.append(f"| {f['exchange']} | {f['contract']} | {f['price']:.2f} | {f['unit']} | {_md_chg(f['change'])} | {f['change_pct'] or '—'} | {_md_num(f['mtd_avg'], 2)} |")

    lines.extend([
        "",
        "## SMM Iron Ore Price Index (Physical & Benchmark Indices)",
        "",
        "| Index Name | Market Type | Fe % | Price | Unit | Daily Change | Daily Change % | MTD Avg |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|"
    ])

    for idx in data.get("smm_price_index_summary", []):
        lines.append(f"| {idx['index_name']} | {idx['market_type']} | {idx['fe_content']}% | {idx['price']:.2f} | {idx['unit']} | {_md_chg(idx['change'])} | {idx['change_pct'] or '—'} | {_md_num(idx['mtd_avg'], 2)} |")

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
            lines.append(f"| {r['product']} | {r['fe_pct']}% | {r['product_type']} | {r['price_yuan_wmt']:.1f} | {_md_chg(r['change'])} | {r['change_pct']} | {_md_avg(r, 1)} |")

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
            lines.append(f"| {r['product']} | {r['fe_pct']}% | {r['product_type']} | {r['price_usd_dmt']:.2f} | {_md_chg(r['change'])} | {r['change_pct']} | {_md_avg(r, 2)} |")

    # Seaborne brand prices (CFR Qingdao, quoted on their own date)
    sb = data.get("seaborne_brand_usd", [])
    if sb:
        lines.extend([
            "",
            f"## Seaborne Brand Prices in USD (CFR Qingdao, USD/dry mt, as of {sb[0]['price_date']})",
            "",
            "| Product | Price (USD/dmt) | Daily Change | Daily Change % | Previous |",
            "|:---|:---:|:---:|:---:|:---:|"
        ])
        for r in sb:
            lines.append(f"| {r['product']} | {r['price_usd_dmt']:.2f} | {_md_chg(r['change'])} | {r['change_pct']} | {_md_num(r['prev_price'], 2)} |")

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
            lines.append(f"| {r['index_name']} | {_md_avg(r, 2)} | {r['mom_pct']} | {r['ytd_pct']} | {r['unit']} |")

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
            # The MMi runner writes some of these files with more columns: keep them (writing only
            # all_fields used to blank the MMi price/market columns, docs/iron_ore_two_writer_verdict.md).
            all_fields = list(reader.fieldnames or []) + [k for k in all_fields if k not in (reader.fieldnames or [])]
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
            "change": "" if f["change"] is None else f["change"],
            "source_file": source_file
        })
    for idx in data.get("smm_price_index_summary", []):
        dash_rows.append({
            "date": issue_date,
            "year": year,
            "indicator": idx["index_name"],
            "value": idx["price"],
            "unit": idx["unit"],
            "change": "" if idx["change"] is None else idx["change"],
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
            "change": "",  # the report prints no change for these drivers
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
            "price": idx["price"],
            "unit": idx["unit"],
            "change": idx["change"],
            "change_pct": idx["change_pct"],
            "source_file": source_file
        })
    # one schema with the MMi rows (scripts/extract/publishers/iron_ore_indices_from_md.py)
    p_idx = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_indices_series.csv"
    upsert_rows_to_csv(p_idx, idx_rows, ["date", "index_name"], ["date", "year", "index_name", "market", "market_type", "fe_content", "unit", "price", "change", "change_pct", "mtd", "ytd", "low_52w", "high_52w", "source_file"])

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
    for r in data.get("seaborne_brand_usd", []):
        brand_rows.append({
            "date": r["price_date"],
            "year": r["price_date"][:4],
            "brand": r["product"],
            "market_type": "seaborne_brand_usd",
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
            "change": "" if f["change"] is None else f["change"],
            "change_pct": f["change_pct"],
            "settlement": "daily",
            "source_file": source_file
        })
    p_fut = OUT_SERIES_DIR / "hellenic_iron_ore_pdf_futures_series.csv"
    upsert_rows_to_csv(p_fut, fut_rows, ["date", "contract"], ["date", "year", "exchange", "contract", "price", "unit", "change", "change_pct", "settlement", "source_file"])

    # 5. Averages Series (Weekly / Monthly stats)
    avg_rows = []
    for s in data.get("index_statistics_weekly_monthly", []):
        if s.get("avg_period"):     # the prior month's average, printed before the month's first quote
            continue
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

    # 7. The MMi daily series carried on. HSN's iron ore daily changed from the MMi 6-page report to this SMM page
    # on 2026-09-14; the quotes both print continue hellenic_iron_ore_daily_series and the desk view continues
    # hellenic_iron_ore_commentary_series. Left blank: what the page does not print (lump index, rebar/HRC, steel
    # and 35-port stocks), SGX once the card shows the current-month contract (not the most-traded one), freight
    # (the page quotes it for an earlier date) and a closed market's carried-over quote.
    continue_mmi_series(data)


def _upsert_by_date(csv_path: Path, rows: List[Dict[str, Any]], add_only: bool = False) -> None:
    """Replace (or with add_only, only add) rows keyed on the first column, keeping header, BOM and line ending."""
    raw = csv_path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
    csv.field_size_limit(10 ** 9)
    table = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    hdr, body = table[0], [r for r in table[1:] if r]
    new = {r[hdr[0]]: [("" if r.get(c) is None else str(r[c])) for c in hdr] for r in rows}
    if add_only:
        have = {r[0] for r in body}
        new = {k: v for k, v in new.items() if k not in have}
    body = sorted([r for r in body if r[0] not in new] + list(new.values()), key=lambda r: r[0])
    out = io.StringIO()
    csv.writer(out, lineterminator=nl).writerows([hdr] + body)
    tmp = csv_path.with_suffix(".csv.tmp")     # write-then-replace: in-place rewrites hit OSError 22 on Windows
    tmp.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out.getvalue().encode("utf-8"))
    os.replace(tmp, csv_path)


def continue_mmi_series(data: Dict[str, Any]) -> None:
    meta = data["metadata"]
    d, src = meta["issue_date"], meta["source_file"]
    live = {i["index_name"]: i for i in data.get("smm_price_index_summary", [])
            if "Holiday" not in (i["change_pct"] or "") and not i.get("closed_note")}
    fut = {f["contract"].rsplit(" ", 1)[0] if f["exchange"] == "DCE" else f["contract"]: f
           for f in data.get("futures_contracts", [])
           if "Holiday" not in (f["change_pct"] or "") and not f.get("closed_note")}
    row: Dict[str, Any] = {"date": d, "year": int(d[:4]), "month": int(d[5:7]), "benchmark_fe_grade": 61.0,
                           "source_file": src, "commentary": data.get("key_view", {}).get("body", "")}
    for name, col, chg in (("MMi 61% Port Spot", "iopi_bench_rmb_wmt", "iopi_bench_chg_rmb"),
                           ("MMi 65% Port Spot", "iopi65_rmb_wmt", "iopi65_chg_rmb"),
                           ("MMi 58% Port Spot", "iopi58_rmb_wmt", "iopi58_chg_rmb"),
                           ("MMi 61% Seaborne Index", "iosi_bench_usd_dmt", "iosi_bench_chg_usd"),
                           ("MMi 65% Seaborne Index", "iosi65_usd_dmt", "iosi65_chg_usd")):
        if name in live:
            row[col], row[chg] = live[name]["price"], live[name]["change"]
    if "DCE Iron Ore Most-traded" in fut:
        row["dce_iron_ore_rmb_t"], row["dce_chg_rmb"] = fut["DCE Iron Ore Most-traded"]["price"], fut["DCE Iron Ore Most-traded"]["change"]
    if "SGX Iron Ore Most-traded" in fut:
        row["sgx_iron_ore_usd_dmt"], row["sgx_chg_usd"] = fut["SGX Iron Ore Most-traded"]["price"], fut["SGX Iron Ore Most-traded"]["change"]
    if len(row) > 6:
        _upsert_by_date(OUT_SERIES_DIR / "hellenic_iron_ore_daily_series.csv", [row])
    if row["commentary"]:
        _upsert_by_date(OUT_SERIES_DIR / "hellenic_iron_ore_commentary_series.csv",
                        [{"issue_date": d, "commentary": row["commentary"], "source_file": src}],
                        add_only=True)     # 2026-09-14..21 came from the issue's HTML page; kept as they are


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

    # Write Markdown (frontmatter cites the PDF by its corpus path, like every other MMI MD)
    md_content = generate_smm_markdown(data)
    try:
        rel = pdf_path.resolve().relative_to(ROOT).as_posix()
        md_content = md_content.replace(f'source_file: "{pdf_path.name}"', f'source_file: "{rel}"', 1)
    except ValueError:
        pass
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

    # hellenic_scraper.py saves each issue flat in pdfs/ and sync_hellenic_live.py saves the same bytes in
    # pdfs/<year>/; the year copy is canonical, so a flat copy holding bytes already in a year folder is skipped
    # (otherwise every issue is extracted twice under two names, as 2026-10-06..10-19 were).
    year_md5 = {hashlib.md5(f.read_bytes()).hexdigest() for f in candidates if f.parent != pdf_root}
    for f in sorted(candidates):
        if f.parent == pdf_root and hashlib.md5(f.read_bytes()).hexdigest() in year_md5:
            continue
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
