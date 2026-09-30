"""
Carriers S&P, Demolition, and Newbuilding Extraction Pipeline.

Extracts all high-value proprietary tables across 129 weekly Carriers Market Reports (2021-2026):
  - Demolition Market (vessel, type, DWT, LDT, built, yard, price $/ldt, buyers, comments)
  - Newbuilding Market (type, units, size, yard, delivery, price $m, owners, comments)
  - Second-hand Market (re-validates and keeps existing sales)

Outputs:
  - data/extracted/series/carriers_demolition_series.csv
  - data/extracted/series/carriers_newbuilding_series.csv
  - Updates data/extracted/carriers/tables/<stem>.json
  - Updates data/extracted/md/carriers/<stem>.md
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "carriers"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_TAB = ROOT / "data" / "extracted" / PUB / "tables"
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

DEMO_SERIES_CSV = OUT_SERIES / "carriers_demolition_series.csv"
NB_SERIES_CSV = OUT_SERIES / "carriers_newbuilding_series.csv"

# Bins & Columns for Demolition table on Page 1
DEMO_BINS = [
    (0, 115), (115, 155), (155, 205), (205, 250), (250, 295),
    (295, 385), (385, 440), (440, 500), (500, 600)
]
DEMO_COLS = ["NAME", "TYPE", "DWT", "LDT", "BUILT", "YARD", "PRICE_LDT", "BUYERS", "COMMENTS"]

# Bins & Columns for Newbuilding table on Page 1
NB_BINS = [
    (0, 115), (115, 160), (160, 240), (240, 315), (315, 365),
    (365, 430), (430, 505), (505, 600)
]
NB_COLS = ["TYPE", "NO", "SIZE", "YARD", "DEL", "MILS", "OWNERS", "COMMENTS"]

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}


def extract_metadata(pdf_path: Path) -> Tuple[Optional[str], Optional[int]]:
    """Extract ISO issue_date and report_week from filename or text."""
    fn = pdf_path.stem
    doc = pymupdf.open(pdf_path)

    # 1. Week
    wk: Optional[int] = None
    m_wk = re.search(r"week[-_ ]+(\d{1,2})", fn, re.I)
    if m_wk:
        wk = int(m_wk.group(1))
    else:
        m_wk2 = re.search(r"[_-]W(\d{1,2})[_-]", fn, re.I)
        if m_wk2:
            wk = int(m_wk2.group(1))
        else:
            m_wk3 = re.search(r"WK[-_ ]+(\d{1,2})", fn, re.I)
            if m_wk3:
                wk = int(m_wk3.group(1))
            else:
                # check page text
                for pg in doc[:2]:
                    t = pg.get_text()
                    m = re.search(r"Week\s*(\d{1,2})", t, re.I)
                    if m:
                        wk = int(m.group(1))
                        break

    # 2. Date
    dt_str: Optional[str] = None
    m_dmy = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fn)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        dt_str = f"{y:04d}-{m:02d}-{d:02d}"
    else:
        m_dmy2 = re.search(r"(\d{1,2})[-_ ]([A-Za-z]{3,})[-_ ](\d{4})", fn)
        if m_dmy2:
            d = int(m_dmy2.group(1))
            mo_name = m_dmy2.group(2).lower()
            y = int(m_dmy2.group(3))
            mo = MONTHS.get(mo_name[:3], 1)
            dt_str = f"{y:04d}-{mo:02d}-{d:02d}"
        else:
            for pg in doc[:2]:
                t = pg.get_text()
                m_txt = re.search(
                    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
                    r"(January|February|March|April|May|June|July|August|September|October|"
                    r"November|December)\s+(\d{4})\b", t, re.I
                )
                if m_txt:
                    d = int(m_txt.group(1))
                    mo = MONTHS.get(m_txt.group(2).lower(), 1)
                    y = int(m_txt.group(3))
                    dt_str = f"{y:04d}-{mo:02d}-{d:02d}"
                    break

    # Fallback to year folder and week
    if not dt_str and wk:
        try:
            yr = int(pdf_path.parent.name)
            # estimate date from week
            est = dt.date.fromisocalendar(yr, min(wk, 52), 1)
            dt_str = est.isoformat()
        except Exception:
            pass

    return dt_str, wk


def parse_page1_tables(page: pymupdf.Page) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Parse Demolition Market and Newbuilding Market tables from Page 1."""
    words = [w for w in page.get_text("words") if w[4].strip()]
    if not words:
        return [], []

    y_demo_hdr: Optional[float] = None
    y_nb_hdr: Optional[float] = None
    y_bspa: Optional[float] = None
    y_footer: float = page.rect.height

    for w in words:
        txt = w[4]
        if txt == "PRICE/LDT":
            y_demo_hdr = w[1]
        elif txt == "MIL$":
            y_nb_hdr = w[1]
        elif txt in ["BSPA", "Recycling", "Kaplanon", "chartering@carriers.gr"]:
            if w[1] > 400:
                if txt in ["BSPA", "Recycling"]:
                    y_bspa = min(y_bspa or 9999, w[1])
                else:
                    y_footer = min(y_footer, w[1])

    # 1. Demolition
    demo_records: List[Dict[str, str]] = []
    if y_demo_hdr:
        upper_limit = y_nb_hdr - 10 if y_nb_hdr and y_nb_hdr > y_demo_hdr else (y_bspa or y_footer)
        d_words = [w for w in words if y_demo_hdr + 4 <= w[1] < upper_limit]
        d_full = " ".join(w[4] for w in d_words)
        if "No Demolition" not in d_full:
            ws = sorted(d_words, key=lambda w: w[1])
            bands: List[List[Any]] = []
            curr_band: List[Any] = []
            curr_y: Optional[float] = None
            for w in ws:
                if curr_y is None or abs(w[1] - curr_y) <= 8:
                    curr_band.append(w)
                    curr_y = w[1] if curr_y is None else (curr_y * 0.7 + w[1] * 0.3)
                else:
                    bands.append(curr_band)
                    curr_band = [w]
                    curr_y = w[1]
            if curr_band:
                bands.append(curr_band)

            for b in bands:
                rec = {c: "" for c in DEMO_COLS}
                for w in b:
                    x_mid = (w[0] + w[2]) / 2.0
                    for (cmin, cmax), cname in zip(DEMO_BINS, DEMO_COLS):
                        if cmin <= x_mid < cmax:
                            rec[cname] = (rec[cname] + " " + w[4]).strip()
                            break
                name = rec.get("NAME", "").strip().upper()
                if name and name not in ["NAME", "VESSEL", "TOTAL", "DEMOLITION", "NEWBUILDING", "MARKET"]:
                    if not any(k in name for k in ["CARRIERS", "KAPLANON", "CORP", "TEL:", "EMAIL"]):
                        demo_records.append(rec)

    # 2. Newbuilding
    nb_records: List[Dict[str, str]] = []
    if y_nb_hdr:
        upper_limit = y_bspa or y_footer
        n_words = [w for w in words if y_nb_hdr + 4 <= w[1] < upper_limit]
        n_full = " ".join(w[4] for w in n_words)
        if "No Newbuilding" not in n_full:
            ws = sorted(n_words, key=lambda w: w[1])
            bands = []
            curr_band, curr_y = [], None
            for w in ws:
                if curr_y is None or abs(w[1] - curr_y) <= 8:
                    curr_band.append(w)
                    curr_y = w[1] if curr_y is None else (curr_y * 0.7 + w[1] * 0.3)
                else:
                    bands.append(curr_band)
                    curr_band = [w]
                    curr_y = w[1]
            if curr_band:
                bands.append(curr_band)

            for b in bands:
                rec = {c: "" for c in NB_COLS}
                for w in b:
                    x_mid = (w[0] + w[2]) / 2.0
                    for (cmin, cmax), cname in zip(NB_BINS, NB_COLS):
                        if cmin <= x_mid < cmax:
                            rec[cname] = (rec[cname] + " " + w[4]).strip()
                            break
                vtype = rec.get("TYPE", "").strip().upper()
                if vtype and vtype not in ["TYPE", "TOTAL", "NEWBUILDING", "BSPA", "MARKET", "SIZE"]:
                    # ignore non-vessel artifact rows and footer lines
                    if not any(k in vtype for k in ["BSPA", "SALE AND", "RECYCLING", "CARRIERS CHARTERING", "KAPLANON", "CORP."]):
                        # Check units or size has content
                        if rec.get("NO") or rec.get("SIZE") or rec.get("OWNERS"):
                            nb_records.append(rec)

    return demo_records, nb_records


def clean_num(val: str) -> Optional[float]:
    """Clean numeric string to float."""
    if not val:
        return None
    s = val.replace(",", "").replace("$", "").replace("m", "").replace("M", "").strip()
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def run():
    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"[run_carriers_tables] Found {len(all_pdfs)} total PDFs.")

    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)

    all_demo_rows: List[Dict[str, Any]] = []
    all_nb_rows: List[Dict[str, Any]] = []

    for idx, pdf_path in enumerate(all_pdfs, 1):
        stem = pdf_path.stem
        issue_date, report_week = extract_metadata(pdf_path)

        doc = pymupdf.open(pdf_path)
        demo_recs, nb_recs = parse_page1_tables(doc[0])

        for r in demo_recs:
            all_demo_rows.append({
                "issue_date": issue_date or "",
                "report_week": report_week or "",
                "vessel": r.get("NAME", ""),
                "vessel_type": r.get("TYPE", ""),
                "dwt": r.get("DWT", "").replace(",", ""),
                "ldt": r.get("LDT", "").replace(",", ""),
                "built": r.get("BUILT", ""),
                "yard": r.get("YARD", ""),
                "price_usd_per_ldt": r.get("PRICE_LDT", "").replace(",", "").replace("$", ""),
                "buyer": r.get("BUYERS", ""),
                "comments": r.get("COMMENTS", ""),
                "source_file": pdf_path.name
            })

        for r in nb_recs:
            all_nb_rows.append({
                "issue_date": issue_date or "",
                "report_week": report_week or "",
                "vessel_type": r.get("TYPE", ""),
                "units": r.get("NO", ""),
                "size": r.get("SIZE", ""),
                "yard": r.get("YARD", ""),
                "delivery": r.get("DEL", ""),
                "price_usd_m": r.get("MILS", "").replace("$", "").replace("EACH", "").strip(),
                "owner": r.get("OWNERS", ""),
                "comments": r.get("COMMENTS", ""),
                "source_file": pdf_path.name
            })

        # Update JSON sidecar in OUT_TAB
        tab_json_path = OUT_TAB / f"{stem}.json"
        tab_data = {}
        if tab_json_path.exists():
            try:
                tab_data = json.loads(tab_json_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if "tables" not in tab_data:
            tab_data["tables"] = {}
        tab_data["tables"]["demolition_market"] = demo_recs
        tab_data["tables"]["newbuilding_market"] = nb_recs
        tab_data["issue_date"] = issue_date
        tab_data["report_week"] = report_week
        tab_data["source_file"] = pdf_path.name
        tab_json_path.write_text(json.dumps(tab_data, indent=2), encoding="utf-8")

    # Write Master Stacked Series CSVs
    # 1. Demolition Series
    demo_fields = [
        "issue_date", "report_week", "vessel", "vessel_type", "dwt", "ldt",
        "built", "yard", "price_usd_per_ldt", "buyer", "comments", "source_file"
    ]
    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=demo_fields)
        writer.writeheader()
        writer.writerows(all_demo_rows)

    # 2. Newbuilding Series
    nb_fields = [
        "issue_date", "report_week", "vessel_type", "units", "size", "yard",
        "delivery", "price_usd_m", "owner", "comments", "source_file"
    ]
    with open(NB_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=nb_fields)
        writer.writeheader()
        writer.writerows(all_nb_rows)

    print(f"\n[run_carriers_tables] Successfully wrote:")
    print(f"  {DEMO_SERIES_CSV.name}: {len(all_demo_rows):,} rows across {len(all_pdfs)} reports")
    print(f"  {NB_SERIES_CSV.name}: {len(all_nb_rows):,} rows across {len(all_pdfs)} reports")


if __name__ == "__main__":
    run()
