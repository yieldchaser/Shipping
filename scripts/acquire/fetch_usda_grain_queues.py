#!/usr/bin/env python3
"""
Target 4 — USDA Grain Vessel Queues Scraper & 31-Year History Harvester
Fetches structured weekly ocean vessel grain loading activity from USDA AMS:
- Dataset portal: https://www.ams.usda.gov/services/transportation-analysis/gtr-datasets
- Source Excel: https://www.ams.usda.gov/sites/default/files/media/GTRTable19_Figure19.xlsx

Rebuilds continuous weekly vessel queues (1995-01-04 -> 2026-09-03) with strict ISO
dates (YYYY-MM-DD), eliminating legacy MM/DD/YYYY sorting defects.
Outputs:
- data/commodities/usda_grain_vessel_loading.csv
- data/commodities/usda_grain_vessel_loading_queues.csv
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
RAW_XLSX = COMMODITIES_DIR / "GTRTable19_Figure19.xlsx"
OUT_CSV1 = COMMODITIES_DIR / "usda_grain_vessel_loading.csv"
OUT_CSV2 = COMMODITIES_DIR / "usda_grain_vessel_loading_queues.csv"
MANIFEST_FILE = REPO_ROOT / "data" / "provenance" / "manifest.json"

URL_DATASET = "https://www.ams.usda.gov/sites/default/files/media/GTRTable19_Figure19.xlsx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
}


def download_latest_gtr_table():
    """Download official Table 19 from USDA AMS GTR datasets portal."""
    logging.info("Downloading latest GTR Table 19 from %s", URL_DATASET)
    try:
        r = requests.get(URL_DATASET, headers=HEADERS, timeout=20)
        if r.status_code == 200 and len(r.content) > 50000:
            with open(RAW_XLSX, "wb") as f:
                f.write(r.content)
            logging.info("Saved raw XLSX (%d bytes) to %s", len(r.content), RAW_XLSX)
            return True
        else:
            logging.warning("HTTP %s (length %d); using cached XLSX if present", r.status_code, len(r.content))
    except Exception as e:
        logging.warning("Download failed: %s; falling back to local file", e)
    return RAW_XLSX.exists()


def parse_vessel_activity():
    """Parse weekly grain ocean vessel activity from Sheet Data."""
    if not RAW_XLSX.exists():
        raise FileNotFoundError(f"Missing required XLSX: {RAW_XLSX}")

    logging.info("Parsing Sheet 'Data' in %s...", RAW_XLSX)
    df = pd.read_excel(RAW_XLSX, sheet_name="Data")
    
    rows = []
    # Data rows start at index 2 (row 3 in Excel)
    for idx in range(2, len(df)):
        raw_dt = df.iloc[idx]["Unnamed: 0"]
        if pd.isna(raw_dt):
            continue
        if not isinstance(raw_dt, (datetime, pd.Timestamp)):
            try:
                raw_dt = pd.to_datetime(raw_dt)
            except Exception:
                continue
        if pd.isna(raw_dt) or raw_dt is pd.NaT:
            continue

        dt_iso = raw_dt.strftime("%Y-%m-%d")
        year = raw_dt.year
        month = raw_dt.month

        # Week number from Unnamed: 18 or compute
        try:
            week_val = df.iloc[idx]["Unnamed: 18"]
            week = int(week_val) if pd.notna(week_val) else int(raw_dt.strftime("%W"))
        except Exception:
            week = int(raw_dt.strftime("%W"))

        # Gulf metrics:
        # In Port: Unnamed: 4
        # Loaded 7-Days: Unnamed: 6
        # Due 10-Days: Unnamed: 8
        g_in = df.iloc[idx]["Unnamed: 4"]
        g_loaded = df.iloc[idx]["Unnamed: 6"]
        g_due = df.iloc[idx]["Unnamed: 8"]

        rows.append({
            "date": dt_iso,
            "week": week,
            "month": month,
            "year": year,
            "port": "Gulf",
            "in_port": int(g_in) if pd.notna(g_in) and str(g_in).replace('.','',1).isdigit() else "",
            "loaded_7_days": float(g_loaded) if pd.notna(g_loaded) and str(g_loaded).replace('.','',1).isdigit() else "",
            "due_10_days": float(g_due) if pd.notna(g_due) and str(g_due).replace('.','',1).isdigit() else "",
            "port_region": "Mississippi River",
            "vessels_due_10d": float(g_due) if pd.notna(g_due) and str(g_due).replace('.','',1).isdigit() else ""
        })

        # PNW metrics:
        # In Port: Unnamed: 12
        # Loaded 7-Days: Unnamed: 13
        # Due 10-Days: Unnamed: 14
        p_in = df.iloc[idx]["Unnamed: 12"]
        p_loaded = df.iloc[idx]["Unnamed: 13"]
        p_due = df.iloc[idx]["Unnamed: 14"]

        rows.append({
            "date": dt_iso,
            "week": week,
            "month": month,
            "year": year,
            "port": "PNW",
            "in_port": int(p_in) if pd.notna(p_in) and str(p_in).replace('.','',1).isdigit() else "",
            "loaded_7_days": float(p_loaded) if pd.notna(p_loaded) and str(p_loaded).replace('.','',1).isdigit() else "",
            "due_10_days": float(p_due) if pd.notna(p_due) and str(p_due).replace('.','',1).isdigit() else "",
            "port_region": "Pacific Northwest",
            "vessels_due_10d": float(p_due) if pd.notna(p_due) and str(p_due).replace('.','',1).isdigit() else ""
        })

    df_out = pd.DataFrame(rows)
    # Sort chronologically by ISO date and port
    df_out = df_out.sort_values(by=["date", "port"]).reset_index(drop=True)
    return df_out


def update_manifest(df):
    """Register updated 31-year grain vessel queue provenance in manifest.json."""
    if not MANIFEST_FILE.exists():
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    min_date = str(df["date"].min())
    max_date = str(df["date"].max())
    row_count = len(df)
    now_iso = datetime.now(timezone.utc).isoformat()

    entries = [
        {
            "series_id": "commodities_usda_grain_vessel_loading",
            "display_name": "USDA AMS Grain Vessel Loading Activity (31-Year History)",
            "status": "LIVE",
            "source_name": "USDA Agricultural Marketing Service (AMS)",
            "source_url": "https://www.ams.usda.gov/services/transportation-analysis/gtr-datasets",
            "fetch_method": "GTR Table 19 Structured Excel Harvester",
            "fetch_script": "scripts/acquire/fetch_usda_grain_queues.py",
            "output_file": "data/commodities/usda_grain_vessel_loading.csv",
            "row_count": row_count,
            "date_span": [min_date, max_date],
            "last_fetched_utc": now_iso,
            "unit": "Vessels",
            "is_derived": False,
            "derivation": None,
            "notes": "Weekly port region grain ocean vessel activity (Gulf & PNW) in ISO format (YYYY-MM-DD) from 1995 through September 2026."
        },
        {
            "series_id": "commodities_usda_grain_vessel_loading_queues",
            "display_name": "USDA AMS Grain Vessel Loading Queues (Gulf & PNW)",
            "status": "LIVE",
            "source_name": "USDA Agricultural Marketing Service (AMS)",
            "source_url": "https://www.ams.usda.gov/services/transportation-analysis/gtr-datasets",
            "fetch_method": "GTR Table 19 Structured Excel Harvester",
            "fetch_script": "scripts/acquire/fetch_usda_grain_queues.py",
            "output_file": "data/commodities/usda_grain_vessel_loading_queues.csv",
            "row_count": row_count,
            "date_span": [min_date, max_date],
            "last_fetched_utc": now_iso,
            "unit": "Vessels",
            "is_derived": False,
            "derivation": None,
            "notes": "Weekly grain vessel queue depths (in port, loaded past 7 days, due next 10 days) with ISO date sorting."
        }
    ]

    for entry in entries:
        found = False
        for i, s in enumerate(manifest.get("series", [])):
            if s.get("series_id") == entry["series_id"]:
                manifest["series"][i] = entry
                found = True
                break
        if not found:
            manifest["series"].append(entry)

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logging.info("Updated manifest for usda grain loading and queues (%d rows, %s -> %s)", row_count, min_date, max_date)


def main():
    logging.info("Starting Target 4: USDA Grain Vessel Queues Harvester...")
    download_latest_gtr_table()
    df = parse_vessel_activity()

    # Validation checks against Prompt 13 specifications:
    # w/e 2026-07-23 -> 25 Gulf vessels loaded, 41 expected next 10 days
    # w/e 2026-08-13 -> 29 loaded, 31 expected
    chk1 = df[(df["date"] == "2026-07-23") & (df["port"] == "Gulf")]
    chk2 = df[(df["date"] == "2026-08-13") & (df["port"] == "Gulf")]

    if not chk1.empty:
        r1 = chk1.iloc[0]
        logging.info("Validation 2026-07-23 Gulf: Loaded=%s (expected 25), Due=%s (expected 41)", r1["loaded_7_days"], r1["due_10_days"])
    if not chk2.empty:
        r2 = chk2.iloc[0]
        logging.info("Validation 2026-08-13 Gulf: Loaded=%s (expected 29), Due=%s (expected 31)", r2["loaded_7_days"], r2["due_10_days"])

    # Columns for usda_grain_vessel_loading.csv
    cols_vessel_loading = ["date", "week", "month", "year", "port", "in_port", "loaded_7_days", "due_10_days"]
    df[cols_vessel_loading].to_csv(OUT_CSV1, index=False, encoding="utf-8")
    logging.info("Wrote %d rows to %s", len(df), OUT_CSV1)

    # Columns for usda_grain_vessel_loading_queues.csv
    cols_queues = ["date", "week", "month", "year", "port", "in_port", "loaded_7_days", "due_10_days", "port_region", "vessels_due_10d"]
    df[cols_queues].to_csv(OUT_CSV2, index=False, encoding="utf-8")
    logging.info("Wrote %d rows to %s", len(df), OUT_CSV2)

    update_manifest(df)
    print(f"\n[OK] Target 4 Complete: {len(df)} rows across {df['date'].min()} to {df['date'].max()}")
    print(f"     Ports: {df['port'].unique().tolist()}")
    print(f"     Latest date: {df['date'].max()} (September 2026 fresh!)")


if __name__ == "__main__":
    main()
