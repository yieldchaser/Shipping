#!/usr/bin/env python3
"""
scripts/acquire/backfill_fearnleys_depth.py

Target 1B: Fearnpulse Historical Depth Backfill.
Fetches full series history for all 34 benchmark series from fearnpulse.com/api/marketapi/TS?id={tsId}.
- Omits 'last' parameter to retrieve full 28-year depth (up to 7,085 rows per route).
- Filters sentinel and corrupt pre-1980 dates.
- Marks discontinued routes (last date <= 2023) as DORMANT.
- Rebuilds data/clarksons/fearnleys_benchmark_rates_continuous.csv and .json.
- Explicitly protects data/indices/bdiy_historical.csv from overwrites.
"""

import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.csv"
JSON_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.json"
BDIY_PATH = ROOT / "data" / "indices" / "bdiy_historical.csv"

# Import CANONICAL_MAP from Target 1A audit
sys.path.insert(0, str(ROOT / "scripts" / "acquire"))
from audit_and_fix_fearnleys_labels import CANONICAL_MAP

TS_URL = "https://fearnpulse.com/api/marketapi/TS"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fearnpulse.com/fearnleys-weekly-report",
    "Origin": "https://fearnpulse.com"
}

CUTOFF_TIMESTAMP_MS = 315532800000  # 1980-01-01 00:00:00 UTC

def fetch_ts_depth(tsid, max_retries=3):
    url = f"{TS_URL}?id={tsid}"
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data", [])
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error fetching tsid {tsid}: {e}")
                return []
            time.sleep(1.5 * (attempt + 1))
    return []

def main():
    # Pre-condition check: verify BDIY path is untouched
    bdiy_size_before = BDIY_PATH.stat().st_size if BDIY_PATH.exists() else 0

    print("=" * 80)
    print("TARGET 1B: Fearnpulse Historical Depth Backfill (All 34 Series)")
    print("=" * 80)

    # Dictionary mapping tsid -> dict of date_str -> value
    all_series_data = {}
    audit_report = []

    sorted_tsids = sorted(CANONICAL_MAP.keys())

    for idx, tsid in enumerate(sorted_tsids, 1):
        meta = CANONICAL_MAP[tsid]
        print(f"[{idx:2d}/34] Probing tsId {tsid:6d} ({meta['label']})...", end="", flush=True)
        raw_rows = fetch_ts_depth(tsid)

        # Normalize ordering: ensure oldest-first
        if raw_rows and len(raw_rows) > 1 and raw_rows[0][2] > raw_rows[-1][2]:
            raw_rows = list(reversed(raw_rows))

        valid_points = {}
        corrupt_count = 0

        for r in raw_rows:
            # r format: [tsid, value, epoch_ms, jobid]
            if len(r) < 3:
                continue
            val = r[1]
            epoch_ms = r[2]

            # Reject pre-1980 corrupt/sentinel rows
            if epoch_ms < CUTOFF_TIMESTAMP_MS:
                corrupt_count += 1
                continue

            # Convert to YYYY-MM-DD
            d_str = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            valid_points[d_str] = val  # Latest row on duplicate dates

        all_series_data[tsid] = valid_points

        dates = sorted(valid_points.keys())
        first_d = dates[0] if dates else "N/A"
        last_d = dates[-1] if dates else "N/A"
        status = "DORMANT" if last_d < "2024-01-01" else "LIVE"

        audit_report.append({
            "tsid": tsid,
            "label": meta["label"],
            "route_code": meta.get("route_code"),
            "class": meta["class"],
            "unit": meta["unit"],
            "raw_count": len(raw_rows),
            "valid_count": len(valid_points),
            "corrupt_dropped": corrupt_count,
            "first_date": first_d,
            "last_date": last_d,
            "status": status
        })

        print(f" {len(valid_points):5d} rows ({first_d} -> {last_d}) [{status}]")
        time.sleep(0.3)  # Polite pacing

    # Print summary table
    print("\n" + "=" * 105)
    print(f"{'tsId':<7} | {'Route Code':<10} | {'Vessel Class':<12} | {'Rows':<6} | {'Span':<23} | {'Status':<8} | {'Header Label'}")
    print("=" * 105)
    for rep in audit_report:
        rc = rep["route_code"] or "-"
        span = f"{rep['first_date']} -> {rep['last_date']}"
        print(f"{rep['tsid']:<7} | {rc:<10} | {rep['class']:<12} | {rep['valid_count']:<6} | {span:<23} | {rep['status']:<8} | {rep['label']}")
    print("=" * 105)

    # Unified chronological date index
    all_unique_dates = sorted(list(set(d for s in all_series_data.values() for d in s.keys())))
    print(f"\nUnified chronological date index: {len(all_unique_dates)} dates ({all_unique_dates[0]} -> {all_unique_dates[-1]})")

    # Rebuild CSV with canonical headers
    csv_headers = ["date"] + [CANONICAL_MAP[tsid]["header"] for tsid in sorted_tsids]
    print(f"Writing {CSV_PATH} with {len(csv_headers)} columns across {len(all_unique_dates)} dates...")

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for d in all_unique_dates:
            row = [d]
            for tsid in sorted_tsids:
                v = all_series_data[tsid].get(d)
                row.append("" if v is None else str(v))
            writer.writerow(row)

    print(f"Successfully rebuilt {CSV_PATH}.")

    # Rebuild JSON twin metadata
    print(f"Updating {JSON_PATH}...")
    catalog = {}
    for rep in audit_report:
        tsid = rep["tsid"]
        meta = CANONICAL_MAP[tsid]
        catalog[str(tsid)] = {
            "tsid": tsid,
            "route_name": meta["label"],
            "vessel_class": meta["class"],
            "route_code": meta.get("route_code"),
            "unit": meta["unit"],
            "status": rep["status"],
            "first_date": rep["first_date"],
            "last_date": rep["last_date"],
            "row_count": rep["valid_count"],
            "notes": meta["notes"]
        }

    json_doc = {
        "metadata": {
            "source_authority": "Fearnleys Weekly Report (fearnpulse.com/api/marketapi/TS)",
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "date_span": [all_unique_dates[0], all_unique_dates[-1]],
            "total_dates": len(all_unique_dates),
            "total_series": len(sorted_tsids),
            "description": "Authoritative continuous dry bulk and tanker benchmark rates at full historical depth."
        },
        "series_catalog": catalog
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_doc, f, indent=2)
    print(f"Successfully updated {JSON_PATH}.")

    # Safety assertion: verify BDIY path was NOT modified
    bdiy_size_after = BDIY_PATH.stat().st_size if BDIY_PATH.exists() else 0
    assert bdiy_size_before == bdiy_size_after, "FATAL: data/indices/bdiy_historical.csv was modified!"
    print("Guardrail verified: data/indices/bdiy_historical.csv preserved untouched.")

if __name__ == "__main__":
    main()
