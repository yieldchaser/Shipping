"""Hellenic VesselsValue Valuations & S&P Extraction Runner.

Extracts weekly Vessel Valuations reports published by VesselsValue / Veson Nautical:
- Unbroken weekly series spanning July 2021 to September 2026 (259 weekly reports)
- Discards one-off press releases / webinars
- Extracts sector commentary (Tanker, Bulker, Container, Gas)
- Extracts individual S&P deals comparing actual Sale Price vs VesselsValue valuation
- Computes valuation premium / discount percentage
- Produces:
  data/extracted/md/hellenic/vessel_valuations/<year>/vv_<date>.md
  data/extracted/md/hellenic/vessel_valuations/<year>/vv_<date>.tables.json
  data/extracted/series/hellenic_vv_sales_series.csv
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "corpus" / "02-hellenic" / "vessel_valuations"
OUT_MD = ROOT / "data" / "extracted" / "md" / "hellenic" / "vessel_valuations"
OUT_SERIES = ROOT / "data" / "extracted" / "series"
STATE_FILE = OUT_MD / "_run_state.json"

SECTOR_MAP = {
    "tanker": "Tanker",
    "tankers": "Tanker",
    "bulker": "Bulker",
    "bulkers": "Bulker",
    "container": "Container",
    "containers": "Container",
    "gas": "Gas",
    "small dry": "Small Dry",
}


def clean_text(s: str) -> str:
    """Normalize whitespace and fix unicode artifacts."""
    if not s:
        return ""
    s = s.replace("\ufffd", "'")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_specs(specs_raw: str) -> Tuple[str, str, str]:
    """Parse DWT/TEU/CBM, built date, and shipyard from specs parenthetical string."""
    m_dwt = re.search(r"([\d,]+)\s*(DWT|TEU|CBM)", specs_raw, re.I)
    dwt = f"{m_dwt.group(1)} {m_dwt.group(2).upper()}" if m_dwt else ""

    m_built = re.search(r"([A-Za-z]{3,9}\s*(?:&[A-Za-z\s]+)?\s*\d{4}|\d{4})", specs_raw)
    built = m_built.group(1).strip() if m_built else ""

    yard = ""
    if m_built:
        end_pos = m_built.end()
        after = specs_raw[end_pos:].strip(" ,")
        yard = clean_text(after)
    elif m_dwt:
        end_pos = m_dwt.end()
        after = specs_raw[end_pos:].strip(" ,")
        yard = clean_text(after)

    return dwt, built, yard


def infer_vessel_class(v_raw: str, dwt_spec: str, sector: str) -> str:
    """Infer standardized vessel class from vessel description or DWT."""
    v_low = v_raw.lower()
    if "vlcc" in v_low:
        return "VLCC"
    if "suezmax" in v_low or "suez" in v_low:
        return "Suezmax"
    if "aframax" in v_low or "afra" in v_low:
        return "Aframax"
    if "lr2" in v_low:
        return "LR2"
    if "lr1" in v_low:
        return "LR1"
    if "mr2" in v_low:
        return "MR2"
    if "mr" in v_low:
        return "MR"
    if "handy tanker" in v_low:
        return "Handy Tanker"
    if "capesize" in v_low or "cape" in v_low:
        return "Capesize"
    if "newcastlemax" in v_low:
        return "Newcastlemax"
    if "kamsarmax" in v_low or "kmax" in v_low:
        return "Kamsarmax"
    if "post panamax" in v_low:
        return "Post Panamax"
    if "panamax" in v_low or "pmax" in v_low:
        return "Panamax"
    if "ultramax" in v_low or "umax" in v_low:
        return "Ultramax"
    if "supramax" in v_low or "smax" in v_low:
        return "Supramax"
    if "handy bulker" in v_low or "handysize" in v_low:
        return "Handysize"
    if "feedermax" in v_low or "fmax" in v_low:
        return "Feedermax"
    if "sub panamax" in v_low:
        return "Sub Panamax"

    # Numeric DWT inference
    m_num = re.search(r"[\d,]+", dwt_spec)
    if m_num:
        try:
            dwt_val = int(m_num.group(0).replace(",", ""))
            if sector == "Tanker":
                if dwt_val >= 200000:
                    return "VLCC"
                if dwt_val >= 120000:
                    return "Suezmax"
                if dwt_val >= 80000:
                    return "Aframax"
                if dwt_val >= 60000:
                    return "Panamax"
                if dwt_val >= 40000:
                    return "MR2"
                return "Handy Tanker"
            if sector == "Bulker":
                if dwt_val >= 120000:
                    return "Capesize"
                if dwt_val >= 80000:
                    return "Kamsarmax"
                if dwt_val >= 70000:
                    return "Panamax"
                if dwt_val >= 60000:
                    return "Ultramax"
                if dwt_val >= 45000:
                    return "Supramax"
                return "Handysize"
        except ValueError:
            pass

    return sector if sector else "Vessel"


def clean_vessel_name(v_raw: str) -> str:
    """Strip vessel class prefix to isolate vessel name(s)."""
    prefixes = [
        "VLCCs", "VLCC", "Suezmaxes", "Suezmax", "Aframaxes", "Aframax",
        "LR2s", "LR2", "LR1s", "LR1", "MR2s", "MR2", "MRs", "MR",
        "Handy Tankers", "Handy Tanker", "Capesizes", "Capesize",
        "Newcastlemaxes", "Newcastlemax", "Kamsarmaxes", "Kamsarmax",
        "Post Panamaxes", "Post Panamax", "Panamaxes", "Panamax",
        "Ultramaxes", "Ultramax", "Supramaxes", "Supramax",
        "Handy Bulkers", "Handy Bulker", "Handysizes", "Handysize",
        "Containers", "Container", "Feedermaxes", "Feedermax",
        "Small Dry", "Bulkers", "Bulker", "Tankers", "Tanker"
    ]
    name = v_raw.strip()
    for p in prefixes:
        if name.startswith(p + " "):
            name = name[len(p) + 1:].strip()
            break
    return clean_text(name)


def parse_deal(txt: str, sector: str) -> Optional[Dict[str, Any]]:
    """Parse single reported transaction comparing Sale Price and VV Value."""
    m = re.match(r"^(.*?)\s*\((.*?)\)\s*sold\s*(.*?)$", txt, re.I)
    if not m:
        return None
    v_raw, specs_raw, rest = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()

    dwt, built, yard = parse_specs(specs_raw)
    v_class = infer_vessel_class(v_raw, dwt, sector)
    v_name = clean_vessel_name(v_raw)

    if sector == "General":
        if v_class in ("VLCC", "Suezmax", "Aframax", "LR2", "LR1", "MR2", "MR", "Handy Tanker"):
            sector = "Tanker"
        elif v_class in ("Capesize", "Newcastlemax", "Kamsarmax", "Post Panamax", "Panamax", "Ultramax", "Supramax", "Handysize"):
            sector = "Bulker"
        elif v_class in ("Feedermax", "Sub Panamax") or "TEU" in dwt:
            sector = "Container"
        elif "CBM" in dwt or "LNG" in v_raw.upper() or "LPG" in v_raw.upper():
            sector = "Gas"

    buyer = ""
    m_buyer = re.search(r"to\s+(.*?)\s+for\s+", rest, re.I)
    if m_buyer:
        buyer = clean_text(m_buyer.group(1))
    elif "to " in rest:
        m_b2 = re.search(r"to\s+(.*?)(?:,|\.|$)", rest, re.I)
        if m_b2:
            buyer = clean_text(m_b2.group(1))

    m_price = re.search(r"for\s+(?:USD\s*)?([\d\.]+)\s*mil", rest, re.I)
    price = None
    if m_price:
        try:
            price = float(m_price.group(1).rstrip("."))
        except ValueError:
            pass

    m_vv = re.search(r"VV\s*(?:en\s*bloc\s*)?value\s*(?:USD\s*)?([\d\.]+)\s*mil", rest, re.I)
    vv_val = None
    if m_vv:
        try:
            vv_val = float(m_vv.group(1).rstrip("."))
        except ValueError:
            pass

    comments = ""
    if " - " in rest:
        comments = clean_text(rest.split(" - ", 1)[1])
    elif "in an en bloc" in rest.lower():
        comments = "en bloc"
    elif "internal sale" in rest.lower():
        comments = "internal sale"

    premium_pct = None
    if price is not None and vv_val is not None and vv_val > 0:
        premium_pct = round(((price - vv_val) / vv_val) * 100.0, 2)

    return {
        "sector": sector,
        "vessel_raw": clean_text(v_raw),
        "vessel_name": v_name,
        "vessel_class": v_class,
        "dwt_spec": dwt,
        "built_date": built,
        "yard": yard,
        "buyer": buyer,
        "price_usd_m": price,
        "vv_value_usd_m": vv_val,
        "premium_pct": premium_pct,
        "comments": comments,
        "raw_text": clean_text(txt),
    }


def parse_vv_html(html_path: Path) -> Dict[str, Any]:
    """Parse complete VesselsValue weekly report."""
    fname = html_path.name
    # Extract date YYYY-MM-DD
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    issue_date = m_date.group(1) if m_date else "UNKNOWN"

    content = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else f"Weekly Vessel Valuations Report - {issue_date}"

    # Extract commentary and deals by traversing paragraphs
    sector_commentary: Dict[str, str] = {}
    deals: List[Dict[str, Any]] = []
    current_sector = "General"

    for tag in soup.find_all(["p", "li"]):
        txt = clean_text(tag.get_text(" ", strip=True))
        if not txt:
            continue

        # Check for sector header
        matched_sector = False
        for s_key, s_name in SECTOR_MAP.items():
            if txt.lower().startswith(s_key + ":"):
                current_sector = s_name
                comm = txt[len(s_key) + 1:].strip()
                if comm:
                    sector_commentary[current_sector] = comm
                matched_sector = True
                break

        if matched_sector:
            continue

        # Check if line is a transaction deal
        if "sold" in txt.lower() and ("usd" in txt.lower() or "vv" in txt.lower()):
            deal = parse_deal(txt, current_sector)
            if deal:
                deal["issue_date"] = issue_date
                deal["source_file"] = fname
                deals.append(deal)

    return {
        "issue_date": issue_date,
        "title": title,
        "source_file": fname,
        "year": issue_date[:4] if issue_date != "UNKNOWN" else "UNKNOWN",
        "commentary": sector_commentary,
        "deals": deals,
    }


def build_markdown_document(report: Dict[str, Any]) -> str:
    """Build standardized Markdown document for knowledge base."""
    lines = [
        f"# {report['title']}",
        "",
        f"- **Issue Date**: {report['issue_date']}",
        f"- **Publisher**: VesselsValue / Veson Nautical",
        f"- **Source**: `corpus/02-hellenic/vessel_valuations/{report['year']}/{report['source_file']}`",
        "",
        "## Sector Market Commentary",
        "",
    ]

    if report["commentary"]:
        for sec, comm in report["commentary"].items():
            lines.append(f"### {sec}")
            lines.append(comm)
            lines.append("")
    else:
        lines.append("*No editorial commentary.*")
        lines.append("")

    lines.append("## Reported S&P Transactions & Valuation Benchmarks")
    lines.append("")
    if report["deals"]:
        lines.append("| Sector | Vessel | Class | DWT / TEU | Built | Yard | Buyer | Sale Price ($M) | VV Value ($M) | Premium (%) | Comments |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for d in report["deals"]:
            p_str = f"${d['price_usd_m']:.2f}M" if d["price_usd_m"] is not None else "Undisclosed"
            vv_str = f"${d['vv_value_usd_m']:.2f}M" if d["vv_value_usd_m"] is not None else "N/A"
            prem_str = f"{d['premium_pct']:+.2f}%" if d["premium_pct"] is not None else "N/A"
            lines.append(
                f"| {d['sector']} | {d['vessel_name']} | {d['vessel_class']} | {d['dwt_spec']} | {d['built_date']} | {d['yard']} | {d['buyer']} | {p_str} | {vv_str} | {prem_str} | {d['comments']} |"
            )
    else:
        lines.append("*No sales with disclosed prices confirmed for this week.*")
    lines.append("")

    lines.extend([
        "## Source Note",
        "",
        "> *Vessel valuations and market data provided by VesselsValue (Veson Nautical). Sale prices reflect reported transaction terms against proprietary automated valuation model (AVM) assessments.*",
        ""
    ])

    return "\n".join(lines)


def process_all() -> Dict[str, Any]:
    """Execute complete VesselsValue extraction across all 259 weekly reports."""
    OUT_MD.mkdir(parents=True, exist_ok=True)
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    # Collect all weekly reports (bypassing one-offs)
    html_files = sorted(list(CORPUS_DIR.glob("**/*weekly-vessel-valuations-report*.html")))
    print(f"Discovered {len(html_files)} weekly VesselsValue HTML reports")

    all_deals_rows: List[Dict[str, Any]] = []
    report_summaries: List[Dict[str, Any]] = []

    for i, h_path in enumerate(html_files, 1):
        report = parse_vv_html(h_path)
        year = report["year"]
        issue_date = report["issue_date"]
        stem = f"vv_{issue_date}"

        year_dir = OUT_MD / year
        year_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write <stem>.tables.json
        tab_json_path = year_dir / f"{stem}.tables.json"
        with open(tab_json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 2. Write <stem>.md
        md_content = build_markdown_document(report)
        md_path = year_dir / f"{stem}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        report_summaries.append({
            "stem": stem,
            "filename": report["source_file"],
            "issue_date": issue_date,
            "year": year,
            "deals_count": len(report["deals"]),
            "sectors_covered": list(report["commentary"].keys()),
        })

        for d in report["deals"]:
            csv_row = {
                "issue_date": d["issue_date"],
                "sector": d["sector"],
                "vessel_name": d["vessel_name"],
                "vessel_class": d["vessel_class"],
                "dwt_spec": d["dwt_spec"],
                "built_date": d["built_date"],
                "yard": d["yard"],
                "buyer": d["buyer"],
                "price_usd_m": d["price_usd_m"] if d["price_usd_m"] is not None else "",
                "vv_value_usd_m": d["vv_value_usd_m"] if d["vv_value_usd_m"] is not None else "",
                "premium_pct": d["premium_pct"] if d["premium_pct"] is not None else "",
                "comments": d["comments"],
                "source_file": d["source_file"],
            }
            all_deals_rows.append(csv_row)

        if i % 50 == 0 or i == len(html_files):
            print(f"[{i}/{len(html_files)}] {report['source_file']} -> {len(report['deals'])} deals ({issue_date})")

    # Write data/extracted/series/hellenic_vv_sales_series.csv
    csv_cols = [
        "issue_date", "sector", "vessel_name", "vessel_class", "dwt_spec",
        "built_date", "yard", "buyer", "price_usd_m", "vv_value_usd_m",
        "premium_pct", "comments", "source_file"
    ]
    series_csv_path = OUT_SERIES / "hellenic_vv_sales_series.csv"
    with open(series_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_cols)
        writer.writeheader()
        for row in all_deals_rows:
            writer.writerow(row)

    print(f"\nWritten {len(all_deals_rows)} total VesselsValue transaction deals to {series_csv_path}")

    # Write run state summary
    state = {
        "reports_processed": len(html_files),
        "total_extracted_deals": len(all_deals_rows),
        "unique_issues": len(set(r["issue_date"] for r in report_summaries)),
        "reports": report_summaries,
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return state


if __name__ == "__main__":
    state = process_all()
    print("VesselsValue Extraction Complete.")
