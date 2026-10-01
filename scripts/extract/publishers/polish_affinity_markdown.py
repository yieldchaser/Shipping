"""
Script to polish Affinity Tanker Weekly Markdown files and series datasets.
Complies strictly with Shipbroking_Source_Parsing_Notes.docx Section 2:
- Page 1 comprehensive extraction: Baltic TC Clean & Dirty, BDTI/BCTI, BDA, Crude Tanker Comments, Product Tanker Comments.
- Page 2 legal disclaimer completely ignored and excluded.
- Formats clean YAML frontmatter, self-documenting GFM tables with units, and verbatim commentary.
- Solves column-interleaving by extracting Crude and Product commentaries via true two-column geometric blocks.
- Solves bottom-line truncation by capturing all narrative text down to the page boundary (y <= 585 pt).
- Solves single-word line breaks by assembling spans into geometric visual lines and coherent paragraphs.
- Eliminates raw verbatim OCR dumps at the bottom of the files.
- Removes duplicate _nan_ files and rebuilds master series CSVs.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "affinity"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def panel_rect(page: pymupdf.Page) -> Optional[pymupdf.Rect]:
    """Find the grey card panel on the right of page 0."""
    best = None
    for g in page.get_drawings():
        if g.get("type") != "f":
            continue
        for it in g.get("items", []):
            if it[0] != "re":
                continue
            r = it[1]
            if r.x0 > 400 and r.width > 150 and r.height > 300:
                if best is None or r.get_area() > best.get_area():
                    best = r
    return best


def parse_clean_float(val: Any) -> Optional[float]:
    """Parse numeric values with robust negative, dollar, and whitespace handling."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s in ("-", "N/A", "nan", "None"):
        return None

    is_neg = False
    if s.startswith("(") and s.endswith(")"):
        is_neg = True
        s = s[1:-1].strip()

    s = s.replace("$", "").replace("USD", "").replace("/day", "").replace("/Day", "").replace("/LDT", "").strip()
    if s.startswith("-"):
        is_neg = True
        s = s[1:].strip()

    if s.upper().startswith("WS"):
        s = s[2:].strip()

    s = s.replace(",", "")
    try:
        f = float(s)
        return -f if is_neg else f
    except ValueError:
        return None


def parse_quantity_mt(val: Any) -> Optional[int]:
    """Parse cargo quantity in metric tonnes."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).replace(",", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def format_rate(val: Optional[float]) -> str:
    """Format TCE dollar rate with commas and dollar sign."""
    if val is None:
        return "-"
    if val < 0:
        return f"-${abs(val):,.0f}"
    return f"${val:,.0f}"


def format_trend(trend: Optional[str]) -> str:
    """Standardize trend arrows and labels."""
    if not trend:
        return "-"
    t = str(trend).strip()
    if "Firm" in t:
        return "↑ Firmer"
    if "Soft" in t:
        return "↓ Softer"
    if "Steady" in t or "Flat" in t or "unchanged" in t:
        return "→ Steady"
    return t


def resolve_date_and_week(stem: str, txt: str) -> Tuple[str, int, str]:
    """Resolve ISO date, ISO week, and pretty date string."""
    # 1. Header in markdown / text
    m = re.search(r"AFFINITY TANKER WEEKLY\s+(\d{1,2})\s+([A-Za-z]+)\s+(202\d)", txt, re.I)
    if m:
        mo = MONTH_MAP.get(m.group(2).lower())
        if mo:
            day = int(m.group(1))
            year = int(m.group(3))
            d = dt.date(year, mo, day)
            pretty = f"{day:02d} {MONTH_NAMES[mo]} {year}"
            return d.isoformat(), d.isocalendar()[1], pretty

    # 2. Filename Affinity-Tanker-Weekly-DD.MM.YYYY
    m2 = re.search(r"Affinity-Tanker-Weekly-(\d{2})\.(\d{2})\.(\d{4})", stem, re.I)
    if m2:
        day, month, year = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        d = dt.date(year, month, day)
        pretty = f"{day:02d} {MONTH_NAMES[month]} {year}"
        return d.isoformat(), d.isocalendar()[1], pretty

    # 3. Filename affinity_tanker_weekly_DD_month_YYYY
    m3 = re.search(r"affinity_tanker_weekly_(\d{1,2})_([a-z]+)_(\d{4})", stem, re.I)
    if m3:
        day = int(m3.group(1))
        mo = MONTH_MAP.get(m3.group(2).lower())
        year = int(m3.group(3))
        if mo:
            d = dt.date(year, mo, day)
            pretty = f"{day:02d} {MONTH_NAMES[mo]} {year}"
            return d.isoformat(), d.isocalendar()[1], pretty

    # 4. Filename DD_MM_YYYY
    m4 = re.search(r"(\d{2})_(\d{2})_(\d{4})", stem)
    if m4:
        day, month, year = int(m4.group(1)), int(m4.group(2)), int(m4.group(3))
        d = dt.date(year, month, day)
        pretty = f"{day:02d} {MONTH_NAMES[month]} {year}"
        return d.isoformat(), d.isocalendar()[1], pretty

    raise ValueError(f"Could not resolve date for {stem}")


def assemble_column_paragraphs(spans_in_col: List[Dict[str, Any]]) -> List[str]:
    """Group word spans into geometric lines and assemble lines into paragraphs based on line pitch."""
    if not spans_in_col:
        return []

    lines_by_y: Dict[float, List[Dict[str, Any]]] = {}
    for s in spans_in_col:
        y = s["y0"]
        matched_y = None
        for ey in lines_by_y:
            if abs(y - ey) <= 2.5:
                matched_y = ey
                break
        if matched_y is not None:
            lines_by_y[matched_y].append(s)
        else:
            lines_by_y[y] = [s]

    sorted_ys = sorted(lines_by_y.keys())
    pitches = [sorted_ys[i + 1] - sorted_ys[i] for i in range(len(sorted_ys) - 1)]
    positive_pitches = [p for p in pitches if p > 3.0]
    median_pitch = sorted(positive_pitches)[len(positive_pitches) // 2] if positive_pitches else 10.0

    formatted_lines: List[Tuple[float, str]] = []
    for y in sorted_ys:
        row_spans = sorted(lines_by_y[y], key=lambda s: s["x0"])
        line_text = " ".join(s["t"] for s in row_spans).strip()
        if line_text:
            formatted_lines.append((y, line_text))

    paragraphs: List[str] = []
    curr_para: List[str] = []
    prev_y: Optional[float] = None

    for y, line_text in formatted_lines:
        if prev_y is not None and (y - prev_y) > 1.45 * median_pitch:
            if curr_para:
                paragraphs.append(" ".join(curr_para))
                curr_para = []
        curr_para.append(line_text)
        prev_y = y

    if curr_para:
        paragraphs.append(" ".join(curr_para))

    return paragraphs


def extract_clean_commentary_from_pdf(pdf_path: Path) -> str:
    """
    Extracts Crude Tanker Comments and Product Tanker Comments from the PDF
    strictly respecting the two-column layout on page 0 and capturing down to y=585pt.
    Eliminates column interleaving, single-word wrapping, and bottom-line truncations.
    """
    doc = pymupdf.open(pdf_path)
    p0 = doc[0]
    panel = panel_rect(p0)
    mid_x = (panel.x0 / 2.0) if panel else 295.0
    panel_left = (panel.x0 - 5.0) if panel else 590.0

    c_spans: List[Dict[str, Any]] = []
    p_spans: List[Dict[str, Any]] = []

    for b in p0.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                x0, y0, x1, y1 = s["bbox"]
                if y0 < 80 or y0 > 585 or x0 >= panel_left:
                    continue
                item = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "t": t}
                if (x0 + x1) / 2.0 < mid_x:
                    c_spans.append(item)
                else:
                    p_spans.append(item)

    c_paras = assemble_column_paragraphs(c_spans)
    p_paras = assemble_column_paragraphs(p_spans)

    c_clean = [p for p in c_paras if p.lower() not in ("crude tanker comments", "crude comments", "crude tankers")]
    p_clean = [p for p in p_paras if p.lower() not in ("product tanker comments", "product comments", "product tankers")]

    commentary_md = []
    commentary_md.append("### Crude Tanker Comments\n")
    commentary_md.append("\n\n".join(c_clean))
    commentary_md.append("\n\n### Product Tanker Comments\n")
    commentary_md.append("\n\n".join(p_clean))

    return "\n".join(commentary_md).strip()


def run_polish():
    print("Starting Affinity Markdown and Series Polish Pipeline...")

    # 1. Clean up stale _nan_ files
    stale_files = list(OUT_MD.glob("*_nan_*"))
    for f in stale_files:
        try:
            f.unlink()
            print(f"Removed stale file: {f.name}")
        except Exception as e:
            print(f"Error removing {f}: {e}")

    sidecars = sorted([f for f in OUT_MD.rglob("*.tables.json") if "_nan_" not in f.name])
    print(f"Processing {len(sidecars)} canonical Affinity reports...")

    tce_series: List[Dict[str, Any]] = []
    bda_series: List[Dict[str, Any]] = []
    indices_series: List[Dict[str, Any]] = []

    processed = 0

    for sc_path in sidecars:
        stem = sc_path.name.replace(".tables.json", "")
        md_path = sc_path.parent / f"{stem}.md"
        if not md_path.exists():
            md_path = OUT_MD / f"{stem}.md"

        if not md_path.exists():
            print(f"Missing MD file for {stem}")
            continue

        raw_md = md_path.read_text(encoding="utf-8")
        data = json.loads(sc_path.read_text(encoding="utf-8"))

        issue_date, report_week, pretty_date = resolve_date_and_week(stem, raw_md)
        year = int(issue_date[:4])

        pages_total = data.get("pages", 1)
        pdf_name = f"{stem}.pdf"

        # Locate source PDF
        pdf_matches = list(CORPUS_DIR.rglob(pdf_name))
        if pdf_matches:
            pdf_path = pdf_matches[0]
            source_rel_path = f"corpus/01-brokers/affinity/{pdf_path.parent.name}/{pdf_name}"
        else:
            pdf_path = CORPUS_DIR / str(year) / pdf_name
            source_rel_path = f"corpus/01-brokers/affinity/{year}/{pdf_name}"

        # Extract Pristine Commentary Prose directly from PDF with clean two-column geometry
        try:
            commentary_text = extract_clean_commentary_from_pdf(pdf_path)
        except Exception as e:
            print(f"Warning: could not extract PDF commentary for {stem}: {e}")
            commentary_text = ""

        typed = data.get("typed", {})

        # 1. BDTI / BCTI
        bdti_val = None
        bcti_val = None
        bdti_trend = "-"
        bcti_trend = "-"
        bcti_bdti_data = typed.get("BCTI / BDTI", {})
        if isinstance(bcti_bdti_data, dict):
            bdti_val = parse_clean_float(bcti_bdti_data.get("bdti"))
            bcti_val = parse_clean_float(bcti_bdti_data.get("bcti"))
            arrows = bcti_bdti_data.get("arrows", [])
            if len(arrows) >= 1:
                bdti_trend = format_trend(arrows[0])
            if len(arrows) >= 2:
                bcti_trend = format_trend(arrows[1])

        if bdti_val is not None:
            indices_series.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "index_name": "BDTI",
                "value": bdti_val,
                "trend_wow": bdti_trend,
                "source_file": pdf_name,
            })
        if bcti_val is not None:
            indices_series.append({
                "issue_date": issue_date,
                "report_week": report_week,
                "index_name": "BCTI",
                "value": bcti_val,
                "trend_wow": bcti_trend,
                "source_file": pdf_name,
            })

        # 2. BDA
        bda_rows = []
        bda_data = typed.get("BDA", {})
        if isinstance(bda_data, dict):
            metrics = bda_data.get("metrics", [])
            values = bda_data.get("values", [])
            deltas = bda_data.get("deltas", [])
            for seg, val, chg in zip(metrics, values, deltas):
                p_f = parse_clean_float(val)
                c_f = parse_clean_float(chg)
                bda_rows.append({
                    "segment": seg,
                    "price": p_f,
                    "change": c_f,
                })
                bda_series.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "segment": seg,
                    "price_usd_per_ldt": p_f,
                    "change_wow": c_f,
                    "source_file": pdf_name,
                })

        # 3. Baltic TCE Dirty
        dirty_rows = []
        dirty_data = typed.get("BALTIC TCE DIRTY", [])
        if isinstance(dirty_data, list):
            for r in dirty_data:
                route = r.get("route")
                desc = r.get("description")
                qty = parse_quantity_mt(r.get("qty_dwt"))
                raw_val = r.get("value_raw")
                val = parse_clean_float(r.get("value")) if r.get("value") is not None else parse_clean_float(raw_val)
                trend = format_trend(r.get("wow"))
                dirty_rows.append({
                    "route": route,
                    "description": desc,
                    "quantity": qty,
                    "rate": val,
                    "trend": trend,
                })
                tce_series.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Dirty",
                    "route": route,
                    "description": desc,
                    "quantity_mt": qty,
                    "tce_usd_per_day": val,
                    "trend_wow": trend,
                    "source_file": pdf_name,
                })

        # 4. Baltic TCE Clean
        clean_rows = []
        clean_data = typed.get("BALTIC TCE CLEAN", [])
        if isinstance(clean_data, list):
            for r in clean_data:
                route = r.get("route")
                desc = r.get("description")
                qty = parse_quantity_mt(r.get("qty_dwt"))
                raw_val = r.get("value_raw")
                val = parse_clean_float(r.get("value")) if r.get("value") is not None else parse_clean_float(raw_val)
                trend = format_trend(r.get("wow"))
                clean_rows.append({
                    "route": route,
                    "description": desc,
                    "quantity": qty,
                    "rate": val,
                    "trend": trend,
                })
                tce_series.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Clean",
                    "route": route,
                    "description": desc,
                    "quantity_mt": qty,
                    "tce_usd_per_day": val,
                    "trend_wow": trend,
                    "source_file": pdf_name,
                })

        # Build Clean Markdown Document
        disclaimer_note = (
            "Excluded (Legal disclaimer per Shipbroking_Source_Parsing_Notes.docx)"
            if pages_total > 1 else "N/A (Single page report)"
        )

        md_doc = []
        md_doc.append("---")
        md_doc.append(f'title: "Affinity Tanker Weekly - {pretty_date}"')
        md_doc.append('broker: "Affinity Shipbrokers"')
        md_doc.append('publication: "Affinity Tanker Weekly"')
        md_doc.append(f'issue_date: "{issue_date}"')
        md_doc.append(f"report_week: {report_week}")
        md_doc.append(f"year: {year}")
        md_doc.append(f'source_file: "{source_rel_path}"')
        md_doc.append(f"pages_total: {pages_total}")
        md_doc.append("pages_analyzed: 1")
        md_doc.append(f'page_2_disclaimer: "{disclaimer_note}"')
        md_doc.append("sectors:")
        md_doc.append('  - "Crude Tankers"')
        md_doc.append('  - "Product Tankers"')
        md_doc.append('  - "Demolition / Recycling"')
        md_doc.append("---")
        md_doc.append("")
        md_doc.append(f"# Affinity Tanker Weekly - {pretty_date}")
        md_doc.append("")
        md_doc.append(f"**Publication Date:** {pretty_date} | **Report Week:** Week {report_week:02d}, {year} | **Source:** Affinity Research LLP")
        md_doc.append("")

        # Section: Market Indices
        md_doc.append("## Market Indices")
        md_doc.append("")
        md_doc.append("| Index | Value | Trend (W-o-W) |")
        md_doc.append("|---|---|---|")
        bdti_str = f"{bdti_val:,.0f}" if bdti_val is not None else "-"
        bcti_str = f"{bcti_val:,.0f}" if bcti_val is not None else "-"
        md_doc.append(f"| BDTI | {bdti_str} | {bdti_trend} |")
        md_doc.append(f"| BCTI | {bcti_str} | {bcti_trend} |")
        md_doc.append("")

        # Section: Baltic Demolition Assessment (BDA)
        if bda_rows:
            md_doc.append("## Baltic Demolition Assessment (BDA)")
            md_doc.append("")
            md_doc.append("| Segment | Price ($/LDT) | Change (W-o-W) |")
            md_doc.append("|---|---|---|")
            for b in bda_rows:
                p_str = f"{b['price']:.1f}" if b['price'] is not None else "-"
                c_str = f"{b['change']:+.1f}" if b['change'] is not None else "-"
                md_doc.append(f"| {b['segment']} | {p_str} | {c_str} |")
            md_doc.append("")

        # Section: Baltic TCE Freight Rates
        md_doc.append("## Baltic TCE Freight Rates")
        md_doc.append("")

        # Dirty Table
        if dirty_rows:
            md_doc.append("### Baltic TCE Dirty")
            md_doc.append("")
            md_doc.append("| Route | Description | Quantity (MT) | Rate ($/Day) | Trend (W-o-W) |")
            md_doc.append("|---|---|---|---|---|")
            for r in dirty_rows:
                qty_str = f"{r['quantity']:,}" if r['quantity'] else "-"
                rate_str = format_rate(r['rate'])
                md_doc.append(f"| {r['route']} | {r['description']} | {qty_str} | {rate_str} | {r['trend']} |")
            md_doc.append("")

        # Clean Table
        if clean_rows:
            md_doc.append("### Baltic TCE Clean")
            md_doc.append("")
            md_doc.append("| Route | Description | Quantity (MT) | Rate ($/Day) | Trend (W-o-W) |")
            md_doc.append("|---|---|---|---|---|")
            for r in clean_rows:
                qty_str = f"{r['quantity']:,}" if r['quantity'] else "-"
                rate_str = format_rate(r['rate'])
                md_doc.append(f"| {r['route']} | {r['description']} | {qty_str} | {rate_str} | {r['trend']} |")
            md_doc.append("")

        # Section: Tanker Market Commentary
        if commentary_text:
            md_doc.append("## Tanker Market Commentary")
            md_doc.append("")
            md_doc.append(commentary_text)
            md_doc.append("")

        # Overwrite with clean Markdown
        md_path.write_text("\n".join(md_doc), encoding="utf-8")
        processed += 1

    print(f"Successfully polished {processed} Markdown files with clean two-column commentary.")

    # Write Master Series CSVs
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    # 1. TCE Series
    tce_series.sort(key=lambda x: (x["issue_date"], x["sector"], x["route"] or ""))
    tce_headers = [
        "issue_date", "report_week", "sector", "route", "description",
        "quantity_mt", "tce_usd_per_day", "trend_wow", "source_file"
    ]
    tce_csv_path = OUT_SERIES / "affinity_tce_series.csv"
    with open(tce_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=tce_headers)
        w.writeheader()
        w.writerows(tce_series)
    print(f"Saved {len(tce_series)} rows to {tce_csv_path}")

    # 2. BDA Series
    bda_series.sort(key=lambda x: (x["issue_date"], x["segment"] or ""))
    bda_headers = [
        "issue_date", "report_week", "segment", "price_usd_per_ldt", "change_wow", "source_file"
    ]
    bda_csv_path = OUT_SERIES / "affinity_bda_series.csv"
    with open(bda_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=bda_headers)
        w.writeheader()
        w.writerows(bda_series)
    print(f"Saved {len(bda_series)} rows to {bda_csv_path}")

    # 3. Indices Series
    indices_series.sort(key=lambda x: (x["issue_date"], x["index_name"]))
    indices_headers = [
        "issue_date", "report_week", "index_name", "value", "trend_wow", "source_file"
    ]
    indices_csv_path = OUT_SERIES / "affinity_indices_series.csv"
    with open(indices_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=indices_headers)
        w.writeheader()
        w.writerows(indices_series)
    print(f"Saved {len(indices_series)} rows to {indices_csv_path}")


if __name__ == "__main__":
    run_polish()
