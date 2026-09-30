"""
Source 6: AFFINITY TANKER WEEKLY - Table Sidecar Stamping & Series Stacking Pipeline.

Handles:
1. Inspecting all 250 table sidecars in data/extracted/md/affinity/*.tables.json
2. Stamping explicit ISO issue_date (YYYY-MM-DD) and report_week (ISO calendar week integer 1..53)
   across top-level metadata, cards, and typed record objects.
3. Stacking series datasets into:
   - data/extracted/series/affinity_tce_series.csv
     schema: issue_date,report_week,sector,route,description,quantity_mt,tce_usd_per_day,trend_wow,source_file
   - data/extracted/series/affinity_bda_series.csv
     schema: issue_date,report_week,segment,price_usd_per_ldt,change_wow,source_file
4. Verifying negative TCE values (e.g. TC2 -$4,273 parsed as -4273.0).
5. Cross-checking sample extractions against rendered PDF pages across 2021, 2024, 2026.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
PUB = "affinity"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

TCE_SERIES_CSV = OUT_SERIES / "affinity_tce_series.csv"
BDA_SERIES_CSV = OUT_SERIES / "affinity_bda_series.csv"

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_doc_date_from_md(md_path: Path) -> Optional[Tuple[str, int]]:
    """Extract printed report date and ISO week from markdown text."""
    if not md_path.exists():
        return None
    txt = md_path.read_text(encoding="utf-8")
    
    # 1. Look for explicit header date: AFFINITY TANKER WEEKLY\n<DD> <MONTH> <YYYY>
    m = re.search(r"AFFINITY TANKER WEEKLY\s+(\d{1,2})\s+([A-Za-z]+)\s+(202\d)", txt, re.I)
    if m:
        mo = MONTH_MAP.get(m.group(2).lower())
        if mo:
            day = int(m.group(1))
            year = int(m.group(3))
            d = dt.date(year, mo, day)
            return d.isoformat(), d.isocalendar()[1]
            
    # 2. Look for date in verbatim text
    m2 = re.search(r"## Verbatim page 0 text.*?(?:AFFINITY TANKER WEEKLY)?\s+(\d{1,2})\s+([A-Za-z]+)\s+(202\d)", txt, re.S | re.I)
    if m2:
        mo = MONTH_MAP.get(m2.group(2).lower())
        if mo:
            day = int(m2.group(1))
            year = int(m2.group(3))
            d = dt.date(year, mo, day)
            return d.isoformat(), d.isocalendar()[1]
            
    return None


def parse_date_from_filename(stem_or_name: str) -> Optional[Tuple[str, int]]:
    """Fallback extraction of date from filename."""
    # Pattern: Affinity-Tanker-Weekly-DD.MM.YYYY
    m = re.search(r"Affinity-Tanker-Weekly-(\d{2})\.(\d{2})\.(\d{4})", stem_or_name, re.I)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d = dt.date(year, month, day)
        return d.isoformat(), d.isocalendar()[1]

    # Pattern: affinity_tanker_weekly_DD_month_YYYY
    m2 = re.search(r"affinity_tanker_weekly_(\d{1,2})_([a-z]+)_(\d{4})", stem_or_name, re.I)
    if m2:
        day = int(m2.group(1))
        mo = MONTH_MAP.get(m2.group(2).lower())
        year = int(m2.group(3))
        if mo:
            d = dt.date(year, mo, day)
            return d.isoformat(), d.isocalendar()[1]

    # Pattern: DD_MM_YYYY
    m3 = re.search(r"(\d{2})_(\d{2})_(\d{4})", stem_or_name)
    if m3:
        day, month, year = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
        d = dt.date(year, month, day)
        return d.isoformat(), d.isocalendar()[1]

    return None


def resolve_metadata(stem: str) -> Tuple[str, int, str]:
    """Resolve ISO issue_date, report_week, and source_file for a given stem."""
    md_path = OUT_MD / f"{stem}.md"
    date_info = parse_doc_date_from_md(md_path)
    if not date_info:
        date_info = parse_date_from_filename(stem)
    if not date_info:
        raise ValueError(f"Unable to resolve date/week for stem: {stem}")
    
    issue_date, report_week = date_info
    source_file = f"{stem}.pdf"
    return issue_date, report_week, source_file


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

    # Strip WS prefix if present
    if s.upper().startswith("WS"):
        s = s[2:].strip()

    s = s.replace(",", "")
    try:
        f = float(s)
        return -f if is_neg else f
    except ValueError:
        return None


def parse_quantity_mt(val: Any) -> Optional[float]:
    """Parse cargo quantity in metric tonnes."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def stamp_and_stack() -> Dict[str, Any]:
    """Update all 250 tables.json sidecars and stack series CSVs."""
    sidecar_files = sorted(OUT_MD.rglob("*.tables.json"))
    if not sidecar_files:
        raise FileNotFoundError(f"No .tables.json files found in {OUT_MD}")

    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    tce_records: List[Dict[str, Any]] = []
    bda_records: List[Dict[str, Any]] = []

    stamped_count = 0
    tce_rows_count = 0
    bda_rows_count = 0
    negative_tce_count = 0

    for sidecar_path in sidecar_files:
        stem = sidecar_path.name.replace(".tables.json", "")
        issue_date, report_week, source_file = resolve_metadata(stem)

        data = json.load(open(sidecar_path, encoding="utf-8"))

        # 1. Stamp top-level metadata
        data["stem"] = stem
        data["source_file"] = source_file
        data["issue_date"] = issue_date
        data["report_week"] = report_week

        # 2. Stamp cards
        for card in data.get("cards", []):
            card["issue_date"] = issue_date
            card["report_week"] = report_week
            card["source_file"] = source_file

        typed = data.get("typed", {})

        # 3. Process BALTIC TCE DIRTY
        dirty_records = typed.get("BALTIC TCE DIRTY", [])
        if isinstance(dirty_records, list):
            for r in dirty_records:
                r["issue_date"] = issue_date
                r["report_week"] = report_week
                r["source_file"] = source_file

                route = r.get("route")
                desc = r.get("description")
                qty = parse_quantity_mt(r.get("qty_dwt"))
                
                # Check negative value parsing
                raw_val = r.get("value_raw")
                val = parse_clean_float(r.get("value")) if r.get("value") is not None else parse_clean_float(raw_val)
                if val is not None and val < 0:
                    negative_tce_count += 1

                trend = r.get("wow")

                tce_records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Dirty",
                    "route": route,
                    "description": desc,
                    "quantity_mt": qty,
                    "tce_usd_per_day": val,
                    "trend_wow": trend,
                    "source_file": source_file,
                })
                tce_rows_count += 1

        # 4. Process BALTIC TCE CLEAN
        clean_records = typed.get("BALTIC TCE CLEAN", [])
        if isinstance(clean_records, list):
            for r in clean_records:
                r["issue_date"] = issue_date
                r["report_week"] = report_week
                r["source_file"] = source_file

                route = r.get("route")
                desc = r.get("description")
                qty = parse_quantity_mt(r.get("qty_dwt"))

                raw_val = r.get("value_raw")
                val = parse_clean_float(r.get("value")) if r.get("value") is not None else parse_clean_float(raw_val)
                if val is not None and val < 0:
                    negative_tce_count += 1

                trend = r.get("wow")

                tce_records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": "Clean",
                    "route": route,
                    "description": desc,
                    "quantity_mt": qty,
                    "tce_usd_per_day": val,
                    "trend_wow": trend,
                    "source_file": source_file,
                })
                tce_rows_count += 1

        # 5. Process BDA
        bda = typed.get("BDA", {})
        if isinstance(bda, dict):
            bda["issue_date"] = issue_date
            bda["report_week"] = report_week
            bda["source_file"] = source_file

            metrics = bda.get("metrics", [])
            values = bda.get("values", [])
            deltas = bda.get("deltas", [])

            bda_list = []
            for seg, p_ldt, chg in zip(metrics, values, deltas):
                price_f = parse_clean_float(p_ldt)
                change_f = parse_clean_float(chg)
                row_dict = {
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "segment": seg,
                    "price_usd_per_ldt": price_f,
                    "change_wow": change_f,
                    "source_file": source_file,
                }
                bda_records.append(row_dict)
                bda_list.append(row_dict)
                bda_rows_count += 1
            bda["records"] = bda_list

        # 6. Process BDTI / BCTI
        indices = typed.get("BCTI / BDTI", {})
        if isinstance(indices, dict):
            indices["issue_date"] = issue_date
            indices["report_week"] = report_week
            indices["source_file"] = source_file

        # Write updated sidecar JSON
        sidecar_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        stamped_count += 1

    # Deterministic sorting
    tce_records.sort(key=lambda x: (x["issue_date"], x["sector"], x["route"] or ""))
    bda_records.sort(key=lambda x: (x["issue_date"], x["segment"] or ""))

    # Write affinity_tce_series.csv
    tce_headers = [
        "issue_date", "report_week", "sector", "route", "description",
        "quantity_mt", "tce_usd_per_day", "trend_wow", "source_file"
    ]
    with open(TCE_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=tce_headers)
        writer.writeheader()
        writer.writerows(tce_records)

    # Write affinity_bda_series.csv
    bda_headers = [
        "issue_date", "report_week", "segment", "price_usd_per_ldt", "change_wow", "source_file"
    ]
    with open(BDA_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bda_headers)
        writer.writeheader()
        writer.writerows(bda_records)

    summary = {
        "sidecars_stamped": stamped_count,
        "tce_series_rows": len(tce_records),
        "bda_series_rows": len(bda_records),
        "negative_tce_count": negative_tce_count,
        "tce_csv": str(TCE_SERIES_CSV),
        "bda_csv": str(BDA_SERIES_CSV),
    }

    return summary


def verify_samples():
    """Verify samples against PDF text across 2021, 2024, 2026."""
    import pymupdf

    samples = [
        ("2021", CORPUS_DIR / "2021" / "affinity_2021_Affinity-Tanker-Weekly-01.10.2021-HSN.pdf"),
        ("2024", CORPUS_DIR / "2024" / "affinity_2024_Affinity-Tanker-Weekly-25.10.2024-HSN.pdf"),
        ("2026", CORPUS_DIR / "2026" / "affinity_19_09_2026_affinity_tanker_weekly_18_september_2026.pdf"),
    ]

    results = []
    for yr, p in samples:
        stem = p.stem
        tbl_path = OUT_MD / f"{stem}.tables.json"
        data = json.load(open(tbl_path, encoding="utf-8"))

        doc = pymupdf.open(p)
        txt = doc[0].get_text()
        doc.close()

        m = re.search(r"AFFINITY TANKER WEEKLY\s+(\d{1,2}\s+[A-Za-z]+\s+202\d)", txt, re.I)
        printed_date = m.group(1) if m else "N/A"

        dirty = data.get("typed", {}).get("BALTIC TCE DIRTY", [])
        clean = data.get("typed", {}).get("BALTIC TCE CLEAN", [])
        bda = data.get("typed", {}).get("BDA", {})

        results.append({
            "year": yr,
            "pdf_name": p.name,
            "printed_date": printed_date,
            "stamped_issue_date": data.get("issue_date"),
            "stamped_report_week": data.get("report_week"),
            "sample_dirty": dirty[:3],
            "sample_clean": clean[:3],
            "bda": bda.get("records", []),
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Stamp Affinity table sidecars and stack series.")
    parser.add_argument("--verify", action="store_true", help="Run sample verification across 2021, 2024, 2026")
    args = parser.parse_args()

    print("=" * 60)
    print("AFFINITY TANKER SERIES EXTRACTION & STAMPING")
    print("=" * 60)

    summary = stamp_and_stack()
    for k, v in summary.items():
        print(f"  {k:<25}: {v}")

    if args.verify:
        print("\n" + "=" * 60)
        print("SAMPLE VERIFICATION ACROSS 2021, 2024, 2026")
        print("=" * 60)
        samples = verify_samples()
        for s in samples:
            print(f"\n[{s['year']}] {s['pdf_name']}")
            print(f"  Printed: {s['printed_date']} | Stamped ISO: {s['stamped_issue_date']} | Week: {s['stamped_report_week']}")
            print("  Dirty Sample:")
            for r in s["sample_dirty"]:
                print(f"    {r.get('route'):<6} {r.get('description'):<20} {r.get('qty_dwt')} MT -> {r.get('value')} USD/day ({r.get('wow')})")
            print("  Clean Sample:")
            for r in s["sample_clean"]:
                print(f"    {r.get('route'):<6} {r.get('description'):<20} {r.get('qty_dwt')} MT -> {r.get('value')} USD/day ({r.get('wow')})")
            print("  BDA:")
            for r in s["bda"]:
                print(f"    {r.get('segment'):<8} ${r.get('price_usd_per_ldt')}/LDT (Δ {r.get('change_wow')})")


if __name__ == "__main__":
    main()
