"""
Banchero Costa S&P, Newbuilding, and Demolition Table Extraction Pipeline.

Extracts weekly market tables and commentary from Banchero Costa & C. S.p.A. reports across 2021-2026:
1. S&P Reported Sales (with 7-digit IMO numbers, vessel name, type, DWT, built year, yard, buyers, price in USD million, SS due date, notes)
2. Newbuilding Market:
   - Indicative Chinese yard newbuilding prices ($/m) for Capesize, Kamsarmax, Ultramax, Handysize, VLCC, Suezmax, LR2 Coated, MR2 Coated
   - Reported Newbuilding orders
3. Demolition Market:
   - Ship recycling assessments ($/LDT) for Bangladesh, India, Pakistan (Dry & Tanker)
   - Reported demolition fixture deals
4. Baltic Secondhand Assessments ($/m)
5. Desk commentary across S&P, Newbuilding, and Demolition sections

Outputs:
  - data/extracted/series/bancosta_sales_series.csv
  - data/extracted/series/bancosta_demolition_series.csv
  - data/extracted/series/bancosta_newbuilding_series.csv
  - data/extracted/md/banchero_costa/<stem>.md
  - data/extracted/md/banchero_costa/<stem>.tables.json
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))
import banchero_deals as bd

PUB = "banchero_costa"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

SALES_SERIES_CSV = OUT_SERIES / "bancosta_sales_series.csv"
DEMO_SERIES_CSV = OUT_SERIES / "bancosta_demolition_series.csv"
NB_SERIES_CSV = OUT_SERIES / "bancosta_newbuilding_series.csv"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "june": 6, "july": 7, "sept": 9,
}

NB_ITEMS = [
    "Capesize", "Kamsarmax", "Ultramax", "Handysize",
    "VLCC", "Suezmax", "LR2 Coated", "MR2 Coated", "LR2", "MR"
]

RECYCLING_ITEMS = [
    "Dry Pakistan", "Dry India", "Dry Bangladesh",
    "Tnk Pakistan", "Tnk India", "Tnk Bangladesh"
]

BALTIC_SH_ITEMS = [
    "Capesize", "Kamsarmax", "Supramax", "Handysize",
    "VLCC", "Suezmax", "Aframax", "MR Product", "MR"
]


# ---------------------------------------------------------------------------
# Metadata extraction (100% matched across 243 PDFs)
# ---------------------------------------------------------------------------

def extract_report_metadata(doc: pymupdf.Document, pdf_path: Path) -> Tuple[int, str, str]:
    """Extract report week integer, ISO issue_date (YYYY-MM-DD), and raw span string."""
    txt = doc[0].get_text() if len(doc) > 0 else ""
    m = re.search(r"Week\s*(\d{1,2})/(\d{4})\s*\(([^)]+)\)", txt, re.I)
    if m:
        wk = int(m.group(1))
        yr = int(m.group(2))
        raw_span = m.group(3).strip()
        parts = re.findall(r"(\d{1,2})\s+([A-Za-z]+)", raw_span)
        if len(parts) >= 2:
            end_d, end_m_str = parts[-1]
            mo_key = end_m_str.lower()[:3]
            if mo_key in MONTHS:
                mo = MONTHS[mo_key]
                d = int(end_d)
                y = yr
                if mo == 1 and parts[0][1].lower()[:3] == "dec":
                    y = yr + 1
                return wk, f"{y:04d}-{mo:02d}-{d:02d}", raw_span
        try:
            iso_date = dt.date.fromisocalendar(yr, wk, 1).isoformat()
            return wk, iso_date, raw_span
        except ValueError:
            pass

    # Fallback to filename
    m_fn = re.search(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})", pdf_path.name)
    if m_fn:
        yr, wk = int(m_fn.group(1)), int(m_fn.group(2))
        try:
            iso_date = dt.date.fromisocalendar(yr, wk, 1).isoformat()
            return wk, iso_date, f"Week {wk}/{yr}"
        except ValueError:
            pass

    return 0, "2026-00-00", ""


# ---------------------------------------------------------------------------
# Sub-Table Extraction (Indicative NB, Ship Recycling, Baltic Secondhand)
# ---------------------------------------------------------------------------

def parse_geometry_subtable(
    page: pymupdf.Page,
    title_marker: str,
    target_items: List[str],
    unit_default: str = "usd mln"
) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """Extract a 2-column or 4-column structured sub-table with period headers."""
    txt = page.get_text()
    if title_marker.upper() not in txt.upper():
        return None, None, []

    words = page.get_text("words")
    # Table data lives strictly in x <= 335 (to avoid the chart axis at x >= 345)
    tbl_words = [w for w in words if w[2] <= 335]

    # Group into lines by y-coordinate
    lines: List[List[Any]] = []
    cur_line: List[Any] = []
    cur_y = None
    for w in sorted(tbl_words, key=lambda w: (w[1], w[0])):
        if cur_y is None or abs(w[1] - cur_y) <= 3.2:
            cur_line.append(w)
            cur_y = w[1] if cur_y is None else cur_y
        else:
            lines.append(cur_line)
            cur_line = [w]
            cur_y = w[1]
    if cur_line:
        lines.append(cur_line)

    in_table = False
    period_cur = None
    period_prev = None
    extracted_rows: List[Dict[str, Any]] = []

    for ln in lines:
        line_str = " ".join(w[4] for w in ln)
        if title_marker.upper() in line_str.upper():
            in_table = True
            continue
        if not in_table:
            continue

        # Stop markers
        if any(stop in line_str.upper() for stop in [
            "DEMOLITION SALES", "NEWBUILDING ORDERS", "SECONDHAND SALES",
            "MARKET REPORT", "REPORTED SALES", "CHARTERING", "DERIVATIVES"
        ]) and len(extracted_rows) > 0:
            break

        # Check for header line: e.g. "Unit 28-Aug 21-Aug W-o-W Y-o-Y" or "Unit Aug-26 Jul-26 M-o-M Y-o-Y"
        if "Unit" in line_str and period_cur is None:
            toks = [w[4] for w in ln]
            try:
                u_idx = toks.index("Unit")
                if len(toks) >= u_idx + 3:
                    period_cur = toks[u_idx + 1]
                    period_prev = toks[u_idx + 2]
            except ValueError:
                pass
            continue

        # Check for item match
        name_words = [w[4] for w in ln if w[0] < 115 and w[4] not in ["Unit", "usd", "mln", "usd/ldt", "N/A"]]
        val_words = [w[4] for w in ln if w[0] >= 110]
        item_str = " ".join(name_words).strip()

        matched_item = None
        for cand in target_items:
            if cand.lower() == item_str.lower() or (item_str and item_str.lower().startswith(cand.lower())):
                matched_item = cand
                break
        if not matched_item:
            # check substring in line_str
            for cand in target_items:
                if cand.lower() in line_str.lower():
                    matched_item = cand
                    break

        if matched_item:
            nums = [w for w in val_words if re.match(r"^[+-]?\d+(?:\.\d+)?%?$", w)]
            price_cur = None
            price_prev = None
            chg1 = None
            chg2 = None

            # Look for 2 floats and 2 percentages
            floats = []
            pcts = []
            for n in nums:
                if "%" in n or "+" in n or (n.startswith("-") and "." in n):
                    pcts.append(n)
                else:
                    try:
                        floats.append(float(n))
                    except ValueError:
                        pass

            if len(floats) >= 2:
                price_cur, price_prev = floats[0], floats[1]
            elif len(floats) == 1:
                price_cur = floats[0]

            if len(pcts) >= 2:
                chg1, chg2 = pcts[0], pcts[1]
            elif len(pcts) == 1:
                chg1 = pcts[0]

            extracted_rows.append({
                "item": matched_item,
                "unit": unit_default,
                "price_current": price_cur,
                "price_previous": price_prev,
                "change1": chg1,
                "change2": chg2,
                "raw_values": nums,
            })

    return period_cur, period_prev, extracted_rows


# ---------------------------------------------------------------------------
# Demolition Fixtures & Newbuilding Orders Parsing (from commentary)
# ---------------------------------------------------------------------------

def extract_demo_deals(text: str) -> List[Dict[str, Any]]:
    """Extract reported demolition sales from text."""
    deals = []
    p1 = re.compile(
        r"(?:MT|MV|M/T|M/V)?\s*([A-Za-z0-9\s/.'\-]+?)\s+(?:\(([^)]+)\)\s+)?([\d,]+)\s*(?:DWT|Dwt)\s+Blt\s+(\d{4})\s+([\d,]+)\s*LDT\s*\$?([\d,.]+)/?LDT.*?(?:Buyer:\s*([A-Za-z\s]+))?",
        re.I
    )
    for m in p1.finditer(text):
        vsl = m.group(1).strip()
        # Clean vessel name prefix if merged with previous buyer
        vsl = re.sub(r"^(?:Pakistan|Bangladesh|India|Turkey|Undisclosed)\s+", "", vsl, flags=re.I).strip()
        deals.append({
            "vessel_name": vsl,
            "vessel_type": m.group(2) or "",
            "dwt": int(m.group(3).replace(",", "")),
            "year_built": int(m.group(4)),
            "ldt": float(m.group(5).replace(",", "")),
            "price_usd_per_ldt": float(m.group(6).replace(",", "")),
            "buyer": (m.group(7) or "").strip(),
            "comments": m.group(0).strip()
        })
    return deals


def extract_nb_orders(text: str) -> List[Dict[str, Any]]:
    """Extract reported newbuilding orders from commentary."""
    orders = []
    clean = " ".join(text.splitlines())
    paras = re.split(r"(?<=[.!?])\s+(?=[A-Z])", clean)

    for p in paras:
        p = p.strip()
        if not p or len(p) < 30:
            continue
        if not any(k in p.lower() for k in ["order", "contract", "booked", "signed", "placed"]):
            continue
        if any(skip in p.upper() for skip in ["INDICATIVE NEWBUILDING", "MARKET REPORT", "SALE & PURCHASE", "DEMOLITION"]):
            continue

        m_cnt = re.search(r"\b(\d{1,2})\s*(?:x|[xX]|units?|vessels?)\b", p)
        vessel_cnt = int(m_cnt.group(1)) if m_cnt else 1

        m_pr = re.search(r"(?:USD|\$)\s*([\d,.]+)\s*(mln|million|bln|billion)?", p, re.I)
        price_each = None
        if m_pr:
            pr_val = float(m_pr.group(1).replace(",", ""))
            unit = (m_pr.group(2) or "").lower()
            if "bln" in unit or "billion" in unit:
                pr_val = pr_val * 1000
            price_each = pr_val

        m_del = re.search(r"deliver(?:y|ies)\s*(?:scheduled\s*)?(?:in|during|between|from|for)?\s*([A-Za-z0-9\s\-/]+?\b(?:202\d|203\d))", p, re.I)
        dely = m_del.group(1).strip() if m_del else ""

        sector = "Other"
        for sec, kws in [
            ("Dry Bulk", ["capesize", "kamsarmax", "panamax", "ultramax", "handysize", "bulker", "dry", "woodchip", "ore"]),
            ("Tanker", ["tanker", "vlcc", "suezmax", "aframax", "mr2", "lr2", "chemical", "crude", "product"]),
            ("Container", ["container", "teu", "neo-panamax"]),
            ("Gas", ["lpg", "lng", "ethane", "ammonia", "cbm", "cu m"]),
            ("Car Carrier", ["car carrier", "ceu", "aurora-class", "pcc", "pctc"]),
            ("Cruise / Pax", ["cruise", "ferry", "passenger", "berths"]),
            ("Offshore", ["windmill", "installation vessel", "offshore", "rig"])
        ]:
            if any(k in p.lower() for k in kws):
                sector = sec
                break

        orders.append({
            "sector": sector,
            "vessel_count": vessel_cnt,
            "price_usd_m_each": price_each,
            "delivery": dely,
            "comments": p
        })
    return orders


# ---------------------------------------------------------------------------
# Commentary Harvester
# ---------------------------------------------------------------------------

def extract_desk_commentary(doc: pymupdf.Document) -> Dict[str, str]:
    """Harvest desk commentary for Newbuilding, Secondhand, and Demolition."""
    commentary = {
        "newbuilding": "",
        "secondhand": "",
        "demolition": ""
    }
    for page in doc:
        txt = page.get_text()
        blocks = page.get_text("blocks")

        if "NEWBUILDING ORDERS" in txt.upper() and not commentary["newbuilding"]:
            nb_paras = []
            capture = False
            for b in sorted(blocks, key=lambda b: (b[1], b[0])):
                b_txt = " ".join(b[4].strip().split())
                if "NEWBUILDING ORDERS" in b_txt.upper():
                    capture = True
                    after = " ".join(re.sub(r"NEWBUILDING ORDERS\s*", "", b_txt, flags=re.I).split())
                    if after and len(after) > 20:
                        nb_paras.append(after)
                    continue
                if capture:
                    if any(stop in b_txt.upper() for stop in ["INDICATIVE NEWBUILDING", "DEMOLITION SALES", "MARKET REPORT", "SALE & PURCHASE"]):
                        break
                    if b[0] < 360 and len(b_txt) > 30 and not re.search(r"^\d+$", b_txt):
                        nb_paras.append(b_txt)
            if nb_paras:
                commentary["newbuilding"] = "\n\n".join(nb_paras)

        if "SECONDHAND SALES" in txt.upper() and not commentary["secondhand"]:
            sh_paras = []
            capture = False
            for b in sorted(blocks, key=lambda b: (b[1], b[0])):
                b_txt = " ".join(b[4].strip().split())
                if "SECONDHAND SALES" in b_txt.upper():
                    capture = True
                    after = " ".join(re.sub(r"SECONDHAND SALES\s*", "", b_txt, flags=re.I).split())
                    if after and len(after) > 20:
                        sh_paras.append(after)
                    continue
                if capture:
                    if any(stop in b_txt.upper() for stop in ["BALTIC SECONDHAND", "REPORTED SALES", "MARKET REPORT", "SALE & PURCHASE"]):
                        break
                    if b[0] < 360 and len(b_txt) > 30 and not re.search(r"^\d+$", b_txt):
                        sh_paras.append(b_txt)
            if sh_paras:
                commentary["secondhand"] = "\n\n".join(sh_paras)

        if "DEMOLITION SALES" in txt.upper() and not commentary["demolition"]:
            demo_paras = []
            capture = False
            for b in sorted(blocks, key=lambda b: (b[1], b[0])):
                b_txt = " ".join(b[4].strip().split())
                if "DEMOLITION SALES" in b_txt.upper():
                    capture = True
                    after = " ".join(re.sub(r"DEMOLITION SALES\s*", "", b_txt, flags=re.I).split())
                    if after and len(after) > 20:
                        demo_paras.append(after)
                    continue
                if capture:
                    if any(stop in b_txt.upper() for stop in ["SHIP RECYCLING", "BALTIC", "MARKET REPORT", "SALE & PURCHASE"]):
                        break
                    if b[0] < 360 and len(b_txt) > 20 and not re.search(r"^\d+$", b_txt):
                        demo_paras.append(b_txt)
            if demo_paras:
                commentary["demolition"] = "\n\n".join(demo_paras)

    return commentary


# ---------------------------------------------------------------------------
# Document Processing
# ---------------------------------------------------------------------------

def process_banchero_costa_report(pdf_path: Path) -> Dict[str, Any]:
    """Process a single Banchero Costa PDF report."""
    pdf_path = Path(pdf_path).resolve()
    stem = pdf_path.stem
    rel_path = str(pdf_path.relative_to(ROOT)).replace("\\", "/")

    doc = pymupdf.open(pdf_path)
    report_week, issue_date, raw_period = extract_report_metadata(doc, pdf_path)
    commentary = extract_desk_commentary(doc)

    # 1. S&P Reported Sales (Deals)
    sales_rows: List[Dict[str, Any]] = []
    try:
        raw_deals, diag = bd.process_pdf(str(pdf_path))
        for r in raw_deals:
            price_val = r.get("price_usd_m")
            raw_comm = r.get("comments") or ""
            m_pr = re.search(r"PRICE:\s*([^|]+)", raw_comm)
            price_raw = m_pr.group(1).strip() if m_pr else (str(price_val) if price_val is not None else "")
            ss_raw = r.get("ss_due") or ""

            sales_rows.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "vessel_name": r.get("vessel") or "",
                "imo": r.get("imo") or "",
                "vessel_type": r.get("vessel_type") or "",
                "dwt": r.get("dwt") or "",
                "built": r.get("built") or "",
                "yard": r.get("yard") or "",
                "buyers": r.get("buyer") or "",
                "price_usd_m": price_val if price_val is not None else "",
                "price_raw": price_raw,
                "ss": ss_raw,
                "ss_due": r.get("ss_due") or "",
                "dd_due": r.get("dd_due") or "",
                "delivery": r.get("delivery") or "",
                "comments": raw_comm,
                "source_file": rel_path
            })
    except Exception as exc:
        print(f"Error extracting deals from {pdf_path.name}: {exc}")

    # 2. Indicative Newbuilding Prices & Orders
    nb_prices: List[Dict[str, Any]] = []
    nb_orders: List[Dict[str, Any]] = []
    nb_period_cur, nb_period_prev = None, None

    for page in doc:
        p_cur, p_prev, rows = parse_geometry_subtable(
            page, "INDICATIVE NEWBUILDING", NB_ITEMS, unit_default="usd mln"
        )
        if rows:
            nb_period_cur, nb_period_prev = p_cur, p_prev
            for r in rows:
                nb_prices.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "indicative_price",
                    "vessel_type": r["item"],
                    "unit": r["unit"],
                    "price_current": r["price_current"] if r["price_current"] is not None else "",
                    "price_previous": r["price_previous"] if r["price_previous"] is not None else "",
                    "period_current": nb_period_cur or "",
                    "period_previous": nb_period_prev or "",
                    "m_o_m": r["change1"] or "",
                    "y_o_y": r["change2"] or "",
                    "sector": "",
                    "owner": "",
                    "vessel_count": "",
                    "size": "",
                    "yard": "",
                    "delivery": "",
                    "price_usd_m_each": "",
                    "comments": "",
                    "source_file": rel_path
                })
            break

    if commentary["newbuilding"]:
        extracted_orders = extract_nb_orders(commentary["newbuilding"])
        for o in extracted_orders:
            nb_orders.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "record_type": "order",
                "vessel_type": "",
                "unit": "usd mln",
                "price_current": "",
                "price_previous": "",
                "period_current": "",
                "period_previous": "",
                "m_o_m": "",
                "y_o_y": "",
                "sector": o["sector"],
                "owner": "",
                "vessel_count": o["vessel_count"],
                "size": "",
                "yard": "",
                "delivery": o["delivery"],
                "price_usd_m_each": o["price_usd_m_each"] if o["price_usd_m_each"] is not None else "",
                "comments": o["comments"],
                "source_file": rel_path
            })

    # 3. Ship Recycling Assessments & Deals
    recycling_assessments: List[Dict[str, Any]] = []
    demo_deals: List[Dict[str, Any]] = []
    demo_period_cur, demo_period_prev = None, None

    for page in doc:
        p_cur, p_prev, rows = parse_geometry_subtable(
            page, "SHIP RECYCLING", RECYCLING_ITEMS, unit_default="usd/ldt"
        )
        if not rows:
            p_cur, p_prev, rows = parse_geometry_subtable(
                page, "RECYCLING ASSESSMENTS", RECYCLING_ITEMS, unit_default="usd/ldt"
            )
        if rows:
            demo_period_cur, demo_period_prev = p_cur, p_prev
            for r in rows:
                recycling_assessments.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "record_type": "recycling_assessment",
                    "segment_location": r["item"],
                    "unit": r["unit"],
                    "price_current": r["price_current"] if r["price_current"] is not None else "",
                    "price_previous": r["price_previous"] if r["price_previous"] is not None else "",
                    "period_current": demo_period_cur or "",
                    "period_previous": demo_period_prev or "",
                    "w_o_w": r["change1"] or "",
                    "y_o_y": r["change2"] or "",
                    "vessel_name": "",
                    "vessel_type": "",
                    "dwt": "",
                    "ldt": "",
                    "year_built": "",
                    "price_usd_per_ldt": "",
                    "buyer": "",
                    "comments": "",
                    "source_file": rel_path
                })
            break

    # Look for demo fixtures in commentary or entire text
    full_text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    extracted_deals = extract_demo_deals(full_text)
    for d in extracted_deals:
        demo_deals.append({
            "issue_date": issue_date,
            "report_week": report_week,
            "record_type": "demolition_deal",
            "segment_location": "",
            "unit": "usd/ldt",
            "price_current": "",
            "price_previous": "",
            "period_current": "",
            "period_previous": "",
            "w_o_w": "",
            "y_o_y": "",
            "vessel_name": d["vessel_name"],
            "vessel_type": d["vessel_type"],
            "dwt": d["dwt"],
            "ldt": d["ldt"],
            "year_built": d["year_built"],
            "price_usd_per_ldt": d["price_usd_per_ldt"],
            "buyer": d["buyer"],
            "comments": d["comments"],
            "source_file": rel_path
        })

    # 4. Baltic Secondhand Assessments
    baltic_sh: List[Dict[str, Any]] = []
    sh_period_cur, sh_period_prev = None, None

    for page in doc:
        p_cur, p_prev, rows = parse_geometry_subtable(
            page, "BALTIC SECONDHAND", BALTIC_SH_ITEMS, unit_default="usd mln"
        )
        if rows:
            sh_period_cur, sh_period_prev = p_cur, p_prev
            for r in rows:
                baltic_sh.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "vessel_type": r["item"],
                    "unit": r["unit"],
                    "price_current": r["price_current"] if r["price_current"] is not None else "",
                    "price_previous": r["price_previous"] if r["price_previous"] is not None else "",
                    "period_current": sh_period_cur or "",
                    "period_previous": sh_period_prev or "",
                    "w_o_w": r["change1"] or "",
                    "y_o_y": r["change2"] or "",
                    "source_file": rel_path
                })
            break

    doc.close()

    # 5. Build Markdown
    yr = issue_date[:4] if issue_date != "2026-00-00" else "2026"
    md_lines = [
        f"# Banchero Costa Weekly Market Report - Week {report_week}, {yr}",
        "",
        f"- **Date**: {issue_date} ({raw_period})",
        f"- **Source**: `{rel_path}`",
        f"- **Broker**: Banchero Costa & C. S.p.A.",
        f"- **Week**: {report_week}/{yr}",
        "",
        "## Newbuilding Market",
        "",
        "### Newbuilding Orders Commentary",
        "",
        commentary["newbuilding"] if commentary["newbuilding"] else "No newbuilding commentary reported.",
        "",
    ]

    if nb_prices:
        md_lines.extend([
            "### Indicative Newbuilding Prices (Chinese Shipyards)",
            "",
            f"| Vessel Type | Unit | {nb_period_cur or 'Current'} | {nb_period_prev or 'Previous'} | M-o-M | Y-o-Y |",
            "|---|---|---|---|---|---|",
        ])
        for p in nb_prices:
            md_lines.append(f"| {p['vessel_type']} | {p['unit']} | {p['price_current']} | {p['price_previous']} | {p['m_o_m']} | {p['y_o_y']} |")
        md_lines.append("")

    if nb_orders:
        md_lines.extend([
            "### Reported Newbuilding Orders",
            "",
            "| Sector | No. | Delivery | Price (USD M each) | Comments |",
            "|---|---|---|---|---|",
        ])
        for o in nb_orders:
            pr = f"${o['price_usd_m_each']}M" if o['price_usd_m_each'] else "N/R"
            md_lines.append(f"| {o['sector']} | {o['vessel_count']} | {o['delivery']} | {pr} | {o['comments']} |")
        md_lines.append("")

    md_lines.extend([
        "## Secondhand Sales",
        "",
        "### Secondhand Commentary Summary",
        "",
        commentary["secondhand"] if commentary["secondhand"] else "No secondhand commentary reported.",
        "",
    ])

    if baltic_sh:
        md_lines.extend([
            "### Baltic Secondhand Assessments (Baltic Exchange)",
            "",
            f"| Vessel Type | Unit | {sh_period_cur or 'Current'} | {sh_period_prev or 'Previous'} | W-o-W | Y-o-Y |",
            "|---|---|---|---|---|---|",
        ])
        for s in baltic_sh:
            md_lines.append(f"| {s['vessel_type']} | {s['unit']} | {s['price_current']} | {s['price_previous']} | {s['w_o_w']} | {s['y_o_y']} |")
        md_lines.append("")

    if sales_rows:
        md_lines.extend([
            "### Reported Sales (S&P Transactions)",
            "",
            "| Type | Vessel Name | IMO No. | DWT | Built | Yard | Buyers | Price ($M) | SS | Note |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ])
        for s in sales_rows:
            dwt_str = f"{s['dwt']:,}" if isinstance(s['dwt'], (int, float)) and s['dwt'] else str(s['dwt'])
            md_lines.append(f"| {s['vessel_type']} | {s['vessel_name']} | {s['imo']} | {dwt_str} | {s['built']} | {s['yard']} | {s['buyers']} | {s['price_raw']} | {s['ss']} | {s['comments']} |")
        md_lines.append("")

    md_lines.extend([
        "## Demolition Market",
        "",
        "### Demolition Commentary",
        "",
        commentary["demolition"] if commentary["demolition"] else "No demolition commentary reported.",
        "",
    ])

    if recycling_assessments:
        md_lines.extend([
            "### Ship Recycling Assessments (Baltic Exchange)",
            "",
            f"| Segment / Country | Unit | {demo_period_cur or 'Current'} | {demo_period_prev or 'Previous'} | W-o-W | Y-o-Y |",
            "|---|---|---|---|---|---|",
        ])
        for r in recycling_assessments:
            md_lines.append(f"| {r['segment_location']} | {r['unit']} | {r['price_current']} | {r['price_previous']} | {r['w_o_w']} | {r['y_o_y']} |")
        md_lines.append("")

    if demo_deals:
        md_lines.extend([
            "### Reported Demolition Sales",
            "",
            "| Vessel Name | Type | DWT | LDT | Built | Price ($/LDT) | Buyer | Comments |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for d in demo_deals:
            dwt_str = f"{d['dwt']:,}" if isinstance(d['dwt'], (int, float)) and d['dwt'] else str(d['dwt'])
            ldt_str = f"{d['ldt']:,}" if isinstance(d['ldt'], (int, float)) and d['ldt'] else str(d['ldt'])
            md_lines.append(f"| {d['vessel_name']} | {d['vessel_type']} | {dwt_str} | {ldt_str} | {d['year_built']} | ${d['price_usd_per_ldt']} | {d['buyer']} | {d['comments']} |")
        md_lines.append("")

    md_content = "\n".join(md_lines) + "\n"

    # 6. Build Sidecar JSON
    sidecar_data = {
        "issue_date": issue_date,
        "report_week": report_week,
        "source_file": rel_path,
        "stem": stem,
        "tables": {
            "reported_sales": sales_rows,
            "indicative_newbuilding": nb_prices,
            "newbuilding_orders": nb_orders,
            "baltic_secondhand": baltic_sh,
            "ship_recycling_assessments": recycling_assessments,
            "demolition_deals": demo_deals
        },
        "desk_commentary": commentary
    }

    return {
        "stem": stem,
        "sales": sales_rows,
        "newbuilding": nb_prices + nb_orders,
        "demolition": recycling_assessments + demo_deals,
        "sidecar": sidecar_data,
        "markdown": md_content
    }


# ---------------------------------------------------------------------------
# Main Pipeline Runner
# ---------------------------------------------------------------------------

def run_pipeline(limit: int = 0, target_stem: Optional[str] = None):
    OUT_MD.mkdir(parents=True, exist_ok=True)
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"Discovered {len(pdfs)} PDFs in {CORPUS_DIR}")

    if target_stem:
        pdfs = [p for p in pdfs if target_stem in p.stem]
        print(f"Filtered to {len(pdfs)} matching '{target_stem}'")
    elif limit > 0:
        pdfs = pdfs[:limit]
        print(f"Limited execution to first {len(pdfs)} PDFs")

    all_sales: List[Dict[str, Any]] = []
    all_nb: List[Dict[str, Any]] = []
    all_demo: List[Dict[str, Any]] = []

    for idx, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        res = process_banchero_costa_report(pdf)

        # Write sidecars
        sidecar_path = OUT_MD / f"{stem}.tables.json"
        md_path = OUT_MD / f"{stem}.md"

        sidecar_path.write_text(json.dumps(res["sidecar"], indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(res["markdown"], encoding="utf-8")

        all_sales.extend(res["sales"])
        all_nb.extend(res["newbuilding"])
        all_demo.extend(res["demolition"])

        if idx % 20 == 0 or idx == len(pdfs):
            print(f"Processed [{idx:>3}/{len(pdfs)}] -> Sales: {len(all_sales):>4}, NB: {len(all_nb):>4}, Demo: {len(all_demo):>4} | {stem[:45]}")

    # Write Stacking Series CSVs
    # 1. Sales Series CSV
    sales_headers = [
        "issue_date", "report_week", "vessel_name", "imo", "vessel_type",
        "dwt", "built", "yard", "buyers", "price_usd_m", "price_raw",
        "ss", "ss_due", "dd_due", "delivery", "comments", "source_file"
    ]
    with open(SALES_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sales_headers)
        writer.writeheader()
        writer.writerows(all_sales)

    # 2. Newbuilding Series CSV
    nb_headers = [
        "issue_date", "report_week", "record_type", "vessel_type", "unit",
        "price_current", "price_previous", "period_current", "period_previous",
        "m_o_m", "y_o_y", "sector", "owner", "vessel_count", "size",
        "yard", "delivery", "price_usd_m_each", "comments", "source_file"
    ]
    with open(NB_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=nb_headers)
        writer.writeheader()
        writer.writerows(all_nb)

    # 3. Demolition Series CSV
    demo_headers = [
        "issue_date", "report_week", "record_type", "segment_location", "unit",
        "price_current", "price_previous", "period_current", "period_previous",
        "w_o_w", "y_o_y", "vessel_name", "vessel_type", "dwt", "ldt",
        "year_built", "price_usd_per_ldt", "buyer", "comments", "source_file"
    ]
    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=demo_headers)
        writer.writeheader()
        writer.writerows(all_demo)

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY:")
    print(f"Total PDFs Processed:     {len(pdfs)}")
    print(f"Reported Sales Rows:      {len(all_sales):,}")
    print(f"Newbuilding Rows:         {len(all_nb):,}")
    print(f"Demolition Rows:          {len(all_demo):,}")
    print(f"Output Sales Series:      {SALES_SERIES_CSV}")
    print(f"Output Newbuilding Series:{NB_SERIES_CSV}")
    print(f"Output Demolition Series: {DEMO_SERIES_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Banchero Costa extraction pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of PDFs to process")
    parser.add_argument("--stem", type=str, default=None, help="Process single document matching stem")
    args = parser.parse_args()
    run_pipeline(limit=args.limit, target_stem=args.stem)
