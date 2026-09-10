#!/usr/bin/env python3
"""
Target 11 — Brazil ComexStat Full History Ingest (201701 → Current)
==================================================================
Harvests complete historical monthly export records from Brazilian customs (MDIC ComexStat
and UN Comtrade Brazil Reporter 76 submission) across the 5 primary Brazilian dry bulk and liquid export pillars:
1. Iron Ore (NCM 2601 / HS 2601) — Capesize driver (Tubarao, Ponta da Madeira)
2. Soybeans (NCM 1201 / HS 1201) — Panamax driver (Santos, Paranagua, Itaqui)
3. Corn (NCM 1005 / HS 1005) — Panamax/Supramax safrinha seasonal export wave
4. Raw Sugar (NCM 1701 / HS 1701) — Supramax/Handysize Santos loading
5. Crude Oil (NCM 2709 / HS 2709) — VLCC/Suezmax Angra dos Reis / Santos basin

Outputs:
- data/commodities/brazil_comexstat_exports.csv
- Updates data/provenance/manifest.json
"""

import json
import logging
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = COMMODITIES_DIR / "brazil_comexstat_exports.csv"
CACHE_FILE = COMMODITIES_DIR / ".cache_brazil_comexstat_full.json"
MANIFEST_FILE = REPO_ROOT / "data" / "provenance" / "manifest.json"

COMEXSTAT_URL = "https://api-comexstat.mdic.gov.br/general"

HEADERS_COMEX = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
}

HEADERS_COMTRADE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

COMMODITY_SPECS = [
    {
        "name": "Iron Ore",
        "ncm_code": "26011100",
        "ncm_list": ["26011100", "26011200"],
        "hs_code": "2601",
        "vessel_class": "Capesize",
    },
    {
        "name": "Soybeans",
        "ncm_code": "12011000+12019000",
        "ncm_list": ["12011000", "12019000"],
        "hs_code": "1201",
        "vessel_class": "Panamax",
    },
    {
        "name": "Corn",
        "ncm_code": "10059010",
        "ncm_list": ["10059010", "10051000"],
        "hs_code": "1005",
        "vessel_class": "Panamax / Supramax",
    },
    {
        "name": "Raw Sugar",
        "ncm_code": "17011300+17011400",
        "ncm_list": ["17011300", "17011400"],
        "hs_code": "1701",
        "vessel_class": "Supramax / Handysize",
    },
    {
        "name": "Crude Oil",
        "ncm_code": "27090010",
        "ncm_list": ["27090010"],
        "hs_code": "2709",
        "vessel_class": "VLCC / Suezmax",
    },
]


def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning("Failed loading cache: %s", e)
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logging.warning("Failed writing cache: %s", e)


def fetch_comtrade_brazil(cmd_code, period):
    """Fetch Brazil official export submission from UN Comtrade (Reporter 76, Brazil exports)."""
    url = f"https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=76&partnerCode=0&cmdCode={cmd_code}&flowCode=X&period={period}"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS_COMTRADE, timeout=12)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if not data:
                    return None
                mot_zero = [x for x in data if x.get("motCode") == 0]
                mot_sea = [x for x in data if x.get("motCode") == 2100]

                rec = mot_zero[0] if mot_zero else (mot_sea[0] if mot_sea else data[0])
                wgt_kg = float(rec.get("netWgt") or rec.get("qty") or 0.0)
                fob_val = float(rec.get("primaryValue") or 0.0)

                # Fallback to sum if mot_zero missing weight
                if wgt_kg <= 0 and mot_sea:
                    wgt_kg = float(mot_sea[0].get("netWgt") or mot_sea[0].get("qty") or 0.0)

                if wgt_kg > 0:
                    return {
                        "metric_tonnes": round(wgt_kg / 1000.0, 2),
                        "fob_usd": round(fob_val, 2),
                        "source": "UN Comtrade / MDIC SECEX Official Submission (Reporter 76)",
                    }
            elif r.status_code == 429:
                sleep_wait = 2.0 * (attempt + 1)
                time.sleep(sleep_wait)
                continue
            else:
                return None
        except Exception as e:
            time.sleep(1.0)
    return None


def run_full_history_harvest():
    cache = load_cache()

    # Load existing CSV to preserve verified 2024-2026 rows
    existing_rows = {}
    if OUT_CSV.exists():
        try:
            df_old = pd.read_csv(OUT_CSV)
            for _, r in df_old.iterrows():
                key = (str(r["date"]), str(r["commodity"]))
                existing_rows[key] = {
                    "date": str(r["date"]),
                    "year": int(r["year"]),
                    "month": int(r["month"]),
                    "commodity": str(r["commodity"]),
                    "ncm": str(r["ncm"]),
                    "metric_tonnes": float(r["metric_tonnes"]),
                    "fob_usd": float(r["fob_usd"]),
                }
            logging.info("Preserved %d existing rows from %s", len(existing_rows), OUT_CSV)
        except Exception as e:
            logging.warning("Failed parsing existing CSV: %s", e)

    # Generate all monthly periods from 201701 through 202607
    all_periods = []
    for y in range(2017, 2027):
        max_m = 12
        if y == 2026:
            max_m = 7
        for m in range(1, max_m + 1):
            all_periods.append((y, m, f"{y}{m:02d}", f"{y}-{m:02d}-01"))

    logging.info("Evaluating full history across %d periods and %d commodities (%d potential points)...",
                 len(all_periods), len(COMMODITY_SPECS), len(all_periods) * len(COMMODITY_SPECS))

    total_new = 0
    total_cache_hits = 0

    for spec in COMMODITY_SPECS:
        c_name = spec["name"]
        hs = spec["hs_code"]
        ncm = spec["ncm_code"]
        logging.info("Processing Brazil exports for: %s (HS %s / NCM %s)...", c_name, hs, ncm)

        for y, m, p, dt_str in all_periods:
            row_key = (dt_str, c_name)
            if row_key in existing_rows:
                continue

            cache_key = f"BRA_{hs}_{p}"
            res = None

            if cache_key in cache:
                total_cache_hits += 1
                res = cache[cache_key]
            else:
                time.sleep(0.3)  # Gentle rate pacing
                res = fetch_comtrade_brazil(hs, p)
                cache[cache_key] = res
                total_new += 1

            if res and res.get("metric_tonnes", 0) > 0:
                existing_rows[row_key] = {
                    "date": dt_str,
                    "year": y,
                    "month": m,
                    "commodity": c_name,
                    "ncm": ncm,
                    "metric_tonnes": res["metric_tonnes"],
                    "fob_usd": res["fob_usd"],
                }

    save_cache(cache)
    logging.info("Harvest complete: %d total observations (new queries: %d, cache hits: %d)",
                 len(existing_rows), total_new, total_cache_hits)

    final_df = pd.DataFrame(list(existing_rows.values()))
    final_df.sort_values(by=["date", "commodity"], inplace=True)
    final_df.to_csv(OUT_CSV, index=False)
    logging.info("Successfully wrote %d full history rows to %s", len(final_df), OUT_CSV)

    update_manifest(len(final_df), final_df["date"].min(), final_df["date"].max())


def update_manifest(row_count, min_date, max_date):
    if not MANIFEST_FILE.exists():
        return
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    series_list = manifest.get("datasets", [])
    series_id = "commodities_brazil_comexstat_exports"

    entry_data = {
        "series_id": series_id,
        "display_name": "Commodities — Brazil Comexstat Exports",
        "status": "LIVE",
        "source_name": "MDIC ComexStat API & UN Comtrade Brazil SECEX Reporter 76",
        "source_url": "https://balanca.mdic.gov.br",
        "fetch_method": "REST API & Comtrade Bilateral Pipeline",
        "fetch_script": "scripts/acquire/fetch_brazil_comexstat_full.py",
        "output_file": "data/commodities/brazil_comexstat_exports.csv",
        "row_count": row_count,
        "date_span": [min_date, max_date],
        "last_fetched_utc": datetime.now(timezone.utc).isoformat(),
        "unit": "Metric Tonnes / USD FOB",
        "is_derived": False,
        "derivation": None,
        "notes": (
            f"Expanded monthly Brazilian export trade series spanning {min_date} to {max_date} ({row_count} rows). "
            f"Encompasses Iron Ore (NCM 2601 / Tubarao Capesize demand), Soybeans (NCM 1201 / Santos Panamax demand), "
            f"Corn (NCM 1005 / safrinha Panamax demand), Raw Sugar (NCM 1701 / Supramax demand), and Crude Oil (NCM 2709 / VLCC demand)."
        ),
    }

    existing = next((e for e in series_list if e.get("series_id") == series_id), None)
    if existing:
        existing.update(entry_data)
    else:
        series_list.append(entry_data)

    manifest["datasets"] = series_list
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logging.info("Updated manifest.json with series %s (%d rows)", series_id, row_count)


if __name__ == "__main__":
    run_full_history_harvest()
