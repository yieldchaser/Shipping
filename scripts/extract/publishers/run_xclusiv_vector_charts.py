"""
Xclusiv Shipbrokers Vector Chart Extraction Pipeline.

Extracts:
  1) 4 Bulk Carrier chart categories on Page 2:
     - Capesize 5TC (Spot $/day)
     - Kamsarmax 5TC (Spot $/day)
     - Ultramax 11TC (Spot $/day)
     - Handysize 7TC (Spot $/day)
  2) Demolition Price curves (Page 7 in 9pp reports, Page 5 in 7pp reports):
     - Dry Demolition Prices ($/LDT)
     - Tanker Demolition Prices ($/LDT)

Outputs:
  - data/extracted/series/xclusiv_bulk_carrier_charts_series.csv
  - data/extracted/series/xclusiv_demolition_charts_series.csv
"""

import csv
import datetime
import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

ROOT = Path(__file__).resolve().parents[3]
XCLUSIV_DIR = ROOT / "corpus" / "01-brokers" / "xclusiv"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)


def _byte_duplicate_stems(root: Path) -> set:
    """Stems of corpus PDFs that are BYTE-IDENTICAL to another corpus PDF.

    A second collection route re-drops the same weekly issue under a different
    filename (measured 2026-10-01: xclusiv has 271 PDFs but only 264 unique,
    7 md5-duplicate groups). Both copies were parsed and stacked, so every
    duplicate issue double-counted. Keep the lexicographically-first stem.
    """
    import hashlib
    by_hash: Dict[str, List[Path]] = {}
    for pdf in sorted(root.glob("**/*.pdf")):
        try:
            h = hashlib.md5(pdf.read_bytes()).hexdigest()
        except OSError:
            continue
        by_hash.setdefault(h, []).append(pdf)
    skip: set = set()
    for group in by_hash.values():
        if len(group) > 1:
            skip.update(p.stem for p in group[1:])
    return skip


BC_SERIES_CSV = OUT_SERIES_DIR / "xclusiv_bulk_carrier_charts_series.csv"
DEMO_SERIES_CSV = OUT_SERIES_DIR / "xclusiv_demolition_charts_series.csv"


def derive_report_week(iso_date: str) -> int:
    """The week number a report COVERS, derived from its issue date.

    Verified 2026-09-28 against the tables-tier control (run_xclusiv_tables.py):
    for the 261 issue dates the control also dates, this derivation agrees on
    257 (98.5%); the 4 disagreements are implausible control values (week 6 for
    2021-11-29, week 1 for 2022-03-28, week 2 for 2022-07-11).  ISO week of
    (issue_date - 7 days), so a report published Tue 15 Sep 2026 covering week
    37 is labelled 37 and year boundaries fall out correctly.

    Used ONLY when the filename carries no week number; the chart CSVs shipped
    report_week = 0 on all 498 rows because this was never derived.
    """
    try:
        dt = datetime.date.fromisoformat(iso_date) - datetime.timedelta(days=7)
    except ValueError:
        return 0
    return dt.isocalendar()[1]


def extract_date_and_week(doc: pymupdf.Document, pdf_path: Path) -> Tuple[str, int]:
    fn = pdf_path.stem
    m_wk = re.search(r"week[_\-\s]*(\d{1,2})", fn, re.I) or re.search(r"W(\d{1,2})", fn, re.I)
    wk = int(m_wk.group(1)) if m_wk else 0

    # Priority 1: the canonical date in the filename, immune to prose noise.
    # xclusiv names its files two ways; the dominant one is DD_MM_YYYY
    # (xclusiv_15_09_2026_...weekly_14th_september_2026.pdf), which this builder
    # did not handle - it fell back to the fake "2026-00-00" on 2 documents x 2
    # series = 12 rows. run_xclusiv_tables.py already used DD_MM_YYYY and is the
    # control: it gives 2026-09-15 / 2026-09-22 for exactly these two files.
    dt = None
    m_fn = re.search(r"(\d{4})_(\d{2})_(\d{2})", fn)
    if m_fn:
        y, m, d = int(m_fn.group(1)), int(m_fn.group(2)), int(m_fn.group(3))
        dt = f"{y:04d}-{m:02d}-{d:02d}"
    else:
        m_fn2 = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
        if m_fn2:
            d, m, y = int(m_fn2.group(1)), int(m_fn2.group(2)), int(m_fn2.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"

    # Priority 2: a date printed on page 1.
    if not dt:
        p1 = doc[0].get_text()
        m_dt = re.search(r"(\d{2})[/-](\d{2})[/-](202\d)", p1)
        if m_dt:
            d, m, y = int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"

    # An unknown date is written BLANK, never as a fake "2026-00-00": a zero month
    # parses as a real ISO date and sorts as if it were in 2026.
    if wk == 0 and dt:
        wk = derive_report_week(dt)
    return dt or "", wk


def extract_panel_value_from_drawings(drawings: List[Dict[str, Any]], y_min: float, y_max: float, val_top: float, val_bot: float) -> Optional[float]:
    curves = []
    for d in drawings:
        rect = d.get('rect')
        if not rect:
            continue
        if rect.y0 >= y_min - 20 and rect.y1 <= y_max + 20:
            n_lines = sum(1 for it in d['items'] if it[0] == 'l')
            if n_lines > 25 and d.get('color'):
                c = d['color']
                # Check for blue/navy tone
                if len(c) == 3 and (c[0] < 0.35 and c[1] < 0.6 and c[2] > 0.4):
                    curves.append((n_lines, d['items']))

    if not curves:
        return None

    curves.sort(key=lambda x: x[0], reverse=True)
    items = curves[0][1]
    pts = [it[1] for it in items if it[0] == 'l']
    if not pts:
        return None

    max_x = max(p.x for p in pts)
    latest_pts = [p for p in pts if p.x >= max_x - 1.5]
    if not latest_pts:
        return None
    latest_y = sum(p.y for p in latest_pts) / len(latest_pts)
    val = val_bot + (y_max - latest_y) * ((val_top - val_bot) / (y_max - y_min))
    return round(val, 1)


def run_xclusiv_charts_pipeline():
    pdfs = sorted(glob.glob(str(XCLUSIV_DIR / "*/*.pdf")))
    _dup = _byte_duplicate_stems(XCLUSIV_DIR)
    if _dup:
        _b = len(pdfs)
        pdfs = [q for q in pdfs if Path(q).stem not in _dup]
        print(f"[dedup] skipped {_b - len(pdfs)} byte-identical duplicate document(s)")
    print(f"Executing Vector Chart Extraction across {len(pdfs)} Xclusiv weekly reports...", flush=True)

    bc_rows = []
    demo_rows = []

    PANELS_BC = [
        ("Capesize 5TC", 121.0, 206.0, 100000.0, 20000.0),
        ("Kamsarmax 5TC", 291.0, 376.0, 50000.0, 10000.0),
        ("Ultramax 11TC", 475.0, 560.0, 25000.0, 5000.0),
        ("Handysize 7TC", 664.0, 757.0, 40000.0, 5000.0)
    ]

    for idx, pdf_str in enumerate(pdfs):
        pdf_path = Path(pdf_str)
        try:
            doc = pymupdf.open(pdf_path)
        except Exception:
            continue

        issue_date, report_week = extract_date_and_week(doc, pdf_path)

        # 1. Page 2 Bulk Carrier Charts
        if len(doc) >= 2:
            page2 = doc[1]
            drawings_p2 = page2.get_drawings()
            if len(drawings_p2) > 40:
                for panel_name, y_min, y_max, val_top, val_bot in PANELS_BC:
                    val = extract_panel_value_from_drawings(drawings_p2, y_min, y_max, val_top, val_bot)
                    if val is not None:
                        bc_rows.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "vessel_class": panel_name,
                            "rate_usd_per_day": val,
                            "chart_page": 2,
                            "source_file": pdf_path.name
                        })

        # 2. Demolition Price Charts (Targeted Page: 7 for >=9pp, 5 for <=7pp)
        target_demo_pno = 6 if len(doc) >= 8 else (4 if len(doc) >= 5 else None)
        if target_demo_pno is not None and target_demo_pno < len(doc):
            demo_page = doc[target_demo_pno]
            t = demo_page.get_text().upper()
            if "DEMOLITION" in t:
                drawings_demo = demo_page.get_drawings()
                if len(drawings_demo) > 25:
                    dry_val = extract_panel_value_from_drawings(drawings_demo, 135.0, 225.0, 700.0, 200.0)
                    tank_val = extract_panel_value_from_drawings(drawings_demo, 375.0, 465.0, 700.0, 200.0)

                    if dry_val is not None:
                        demo_rows.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "segment": "Dry Demolition Index",
                            "price_usd_per_ldt": dry_val,
                            "chart_page": target_demo_pno + 1,
                            "source_file": pdf_path.name
                        })
                    if tank_val is not None:
                        demo_rows.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "segment": "Tanker Demolition Index",
                            "price_usd_per_ldt": tank_val,
                            "chart_page": target_demo_pno + 1,
                            "source_file": pdf_path.name
                        })

        if (idx + 1) % 50 == 0 or idx == len(pdfs) - 1:
            print(f"[{idx+1}/{len(pdfs)}] Processed {pdf_path.name} (BC rows: {len(bc_rows)}, Demo rows: {len(demo_rows)})", flush=True)

    print(f"Total Xclusiv Bulk Carrier chart rows: {len(bc_rows)}", flush=True)
    print(f"Total Xclusiv Demolition chart rows: {len(demo_rows)}", flush=True)

    if bc_rows:
        fields_bc = ["issue_date", "report_week", "vessel_class", "rate_usd_per_day", "chart_page", "source_file"]
        with open(BC_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields_bc)
            writer.writeheader()
            writer.writerows(bc_rows)
        print(f"Exported {len(bc_rows)} rows to {BC_SERIES_CSV.name}", flush=True)

    if demo_rows:
        fields_demo = ["issue_date", "report_week", "segment", "price_usd_per_ldt", "chart_page", "source_file"]
        with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields_demo)
            writer.writeheader()
            writer.writerows(demo_rows)
        print(f"Exported {len(demo_rows)} rows to {DEMO_SERIES_CSV.name}", flush=True)


if __name__ == "__main__":
    run_xclusiv_charts_pipeline()
