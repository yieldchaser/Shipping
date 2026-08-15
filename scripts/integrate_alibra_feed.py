"""
Alibra Data Integration Engine
------------------------------
Integrates Alibra historical archives (2008-2026), live snapshot tables,
and tanker forward curves into data/derived/ time series datasets.

Usage:
    python scripts/integrate_alibra_feed.py
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIBRA_DATA_DIR = REPO_ROOT / "docs" / "alibra_data"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

TC_COLS = [
    "date",
    "source",
    "capesize_4_6m_atl", "capesize_4_6m_pac", "capesize_4_6m_avg",
    "capesize_1y_atl", "capesize_1y_pac", "capesize_1y_avg",
    "capesize_2y_atl", "capesize_2y_pac", "capesize_2y_avg",
    "panamax_4_6m_atl", "panamax_4_6m_pac", "panamax_4_6m_avg",
    "panamax_1y_atl", "panamax_1y_pac", "panamax_1y_avg",
    "panamax_2y_atl", "panamax_2y_pac", "panamax_2y_avg",
    "supramax_4_6m_atl", "supramax_4_6m_pac", "supramax_4_6m_avg",
    "supramax_1y_atl", "supramax_1y_pac", "supramax_1y_avg",
    "supramax_2y_atl", "supramax_2y_pac", "supramax_2y_avg",
    "handysize_4_6m_atl", "handysize_4_6m_pac", "handysize_4_6m_avg",
    "handysize_1y_atl", "handysize_1y_pac", "handysize_1y_avg",
    "handysize_2y_atl", "handysize_2y_pac", "handysize_2y_avg",
    "vlcc_1y", "vlcc_2y", "vlcc_3y", "vlcc_5y",
    "suezmax_1y", "suezmax_2y", "suezmax_3y", "suezmax_5y",
    "aframax_1y", "aframax_2y", "aframax_3y", "aframax_5y",
    "mr_1y", "mr_2y", "mr_3y", "mr_5y",
    "lr1_1y", "lr1_2y", "lr1_3y", "lr1_5y",
    "lr2_1y", "lr2_2y", "lr2_3y", "lr2_5y",
    "handytanker_1y", "handytanker_2y", "handytanker_3y", "handytanker_5y"
]

def clean_num(val):
    """Clean string number with commas or symbols to float, or None."""
    if val is None:
        return None
    val_str = str(val).strip().replace(",", "").replace("$", "").replace('"', "")
    if not val_str or val_str.upper() in ["#N/A", "N/A", "NAN", "-", "NULL"]:
        return None
    try:
        return float(val_str)
    except ValueError:
        return None

def parse_iso_date(tag_str, fallback_date_str=""):
    """Extract YYYY-MM-DD from ISO tag (e.g. 'Week 1|2008-01-01') or parse date string."""
    if tag_str:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(tag_str))
        if m:
            return m.group(1)
    if fallback_date_str:
        cleaned = str(fallback_date_str).strip()
        for fmt in ["%d %b %Y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

def parse_archive_file(filepath):
    """Parses an Alibra dry bulk archive CSV into {date: {handysize, supramax, panamax, capesize}}."""
    records = {}
    if not filepath.exists():
        return records
    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 6:
                continue
            date_col = row[1] if len(row) > 1 else ""
            tag_col = row[6] if len(row) > 6 else (row[5] if len(row) > 5 else "")
            iso_date = parse_iso_date(tag_col, date_col)
            if not iso_date or iso_date < "2008-01-01":
                continue
            handy = clean_num(row[2])
            supra = clean_num(row[3])
            pana = clean_num(row[4])
            cape = clean_num(row[5])
            records[iso_date] = {
                "handysize": handy,
                "supramax": supra,
                "panamax": pana,
                "capesize": cape
            }
    return records

def integrate_historical_time_charter():
    """Integrates Alibra Atlantic (2015-2026) and Pacific (2008-2026) archives into time_charter_rates.csv."""
    tc_file = DERIVED_DIR / "time_charter_rates.csv"
    existing_rows = {}
    
    if tc_file.exists():
        with open(tc_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row.get("date", "").strip()
                if d:
                    existing_rows[d] = row

    atl_files = sorted(list((ALIBRA_DATA_DIR / "dry_bulk_archive_atl").glob("*.csv")))
    pac_files = sorted(list((ALIBRA_DATA_DIR / "dry_bulk_archive_pac").glob("*.csv")))

    atl_records = {}
    if atl_files:
        atl_records = parse_archive_file(atl_files[-1])
        print(f"Loaded {len(atl_records)} Atlantic archive rows ({min(atl_records.keys())} -> {max(atl_records.keys())})")

    pac_records = {}
    if pac_files:
        pac_records = parse_archive_file(pac_files[-1])
        print(f"Loaded {len(pac_records)} Pacific archive rows ({min(pac_records.keys())} -> {max(pac_records.keys())})")

    all_dates = set(existing_rows.keys()) | set(atl_records.keys()) | set(pac_records.keys())
    merged_rows = []

    for d in sorted(all_dates):
        row = existing_rows.get(d, {})
        if d < "2008-01-01" and row.get("source") == "alibra_archive":
            continue
        row_dict = {"date": d}
        for col in TC_COLS[1:]:
            row_dict[col] = row.get(col, "")

        # Set source provenance
        if not row_dict.get("source"):
            if d < "2021-07-07":
                row_dict["source"] = "alibra_archive" if (d in atl_records or d in pac_records) else "fearnleys"
            else:
                row_dict["source"] = "alibra_ocr"

        # Enrich Atlantic rates
        if d in atl_records:
            a = atl_records[d]
            if a["capesize"] is not None:
                row_dict["capesize_1y_atl"] = a["capesize"]
            if a["panamax"] is not None:
                row_dict["panamax_1y_atl"] = a["panamax"]
            if a["supramax"] is not None:
                row_dict["supramax_1y_atl"] = a["supramax"]
            if a["handysize"] is not None:
                row_dict["handysize_1y_atl"] = a["handysize"]

        # Enrich Pacific rates
        if d in pac_records:
            p = pac_records[d]
            if p["capesize"] is not None:
                row_dict["capesize_1y_pac"] = p["capesize"]
            if p["panamax"] is not None:
                row_dict["panamax_1y_pac"] = p["panamax"]
            if p["supramax"] is not None:
                row_dict["supramax_1y_pac"] = p["supramax"]
            if p["handysize"] is not None:
                row_dict["handysize_1y_pac"] = p["handysize"]

        # Compute averages if both atl and pac are present
        for seg in ["capesize", "panamax", "supramax", "handysize"]:
            atl_val = clean_num(row_dict.get(f"{seg}_1y_atl"))
            pac_val = clean_num(row_dict.get(f"{seg}_1y_pac"))
            current_avg = clean_num(row_dict.get(f"{seg}_1y_avg"))

            if atl_val is not None and pac_val is not None:
                row_dict[f"{seg}_1y_avg"] = (atl_val + pac_val) / 2.0
            elif current_avg is None:
                if pac_val is not None:
                    row_dict[f"{seg}_1y_avg"] = pac_val
                elif atl_val is not None:
                    row_dict[f"{seg}_1y_avg"] = atl_val

        merged_rows.append(row_dict)

    merged_rows.sort(key=lambda r: r["date"])

    with open(tc_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TC_COLS, extrasaction="ignore")
        writer.writeheader()
        for r in merged_rows:
            writer.writerow(r)

    print(f"Successfully integrated Alibra historical archives into {tc_file} ({len(merged_rows)} total rows)!")

def integrate_tanker_forward_curves():
    """Parses latest forward_curves CSV and saves formatted snapshot and historical archive."""
    fc_dir = ALIBRA_DATA_DIR / "forward_curves"
    fc_files = sorted(list(fc_dir.glob("*.csv")))
    if not fc_files:
        print("No forward curve files found.")
        return

    latest_file = fc_files[-1]
    snapshot_date = latest_file.stem  # e.g. 2026-08-15

    # Check if last_updated_stamp is available
    stamp_dir = ALIBRA_DATA_DIR / "last_updated_stamp"
    stamp_files = sorted(list(stamp_dir.glob("*.csv")))
    if stamp_files:
        with open(stamp_files[-1], encoding="utf-8") as f:
            stamp_text = f.read().strip()
            parsed_stamp = parse_iso_date("", stamp_text)
            if parsed_stamp:
                snapshot_date = parsed_stamp

    forward_rows = []
    with open(latest_file, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 13:
                continue
            month_str = row[0].strip()
            if not month_str:
                continue

            # Format forward contract month (e.g. 1-Aug-26 -> 2026-08-01)
            fwd_iso = parse_iso_date("", month_str)
            if not fwd_iso:
                # parse 1-Aug-26
                try:
                    dt = datetime.strptime(month_str, "%d-%b-%y")
                    fwd_iso = dt.strftime("%Y-%m-%d")
                except ValueError:
                    fwd_iso = month_str

            forward_rows.append({
                "snapshot_date": snapshot_date,
                "forward_month": fwd_iso,
                "contract_label": month_str,
                "vlcc_td3c": clean_num(row[1]),
                "vlcc_eco_td3c": clean_num(row[2]),
                "suezmax_td20": clean_num(row[3]),
                "aframax_td25": clean_num(row[4]),
                "lr1_tc5": clean_num(row[5]),
                "lr1_eco_tc5": clean_num(row[6]),
                "mr_tc2": clean_num(row[7]),
                "mr_eco_tc2": clean_num(row[8]),
                "mr_tc14": clean_num(row[9]),
                "mr_eco_tc14": clean_num(row[10]),
                "mr_tc6": clean_num(row[11]),
                "mr_triangulation": clean_num(row[12]),
            })

    if not forward_rows:
        return

    # 1. Write current snapshot CSV
    out_snapshot = DERIVED_DIR / "tanker_forward_curves.csv"
    fc_fieldnames = list(forward_rows[0].keys())
    with open(out_snapshot, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames)
        writer.writeheader()
        for r in forward_rows:
            writer.writerow(r)

    # 2. Append to historical forward curves archive
    out_history = DERIVED_DIR / "tanker_forward_curves_history.csv"
    existing_keys = set()
    if out_history.exists():
        with open(out_history, encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                existing_keys.add((r.get("snapshot_date"), r.get("forward_month")))

    write_history_header = not out_history.exists()
    with open(out_history, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames)
        if write_history_header:
            writer.writeheader()
        for r in forward_rows:
            k = (r["snapshot_date"], r["forward_month"])
            if k not in existing_keys:
                writer.writerow(r)
                existing_keys.add(k)

    print(f"Successfully generated {out_snapshot} and updated {out_history} ({len(forward_rows)} contracts for {snapshot_date})!")

def main():
    print("=== RUNNING ALIBRA FEED INTEGRATION ===")
    integrate_historical_time_charter()
    integrate_tanker_forward_curves()
    print("=== INTEGRATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
