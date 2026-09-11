#!/usr/bin/env python3
"""
fetch_bps_exim.py — Badan Pusat Statistik (BPS) Indonesia Export API Fetcher
Fetches official monthly Indonesian coal and lignite seaborne exports
using the verified BPS dataexim endpoint with 8-digit HS codes:
  - 27011100: Anthracite
  - 27011210: Bituminous, coking coal
  - 27011290: Bituminous, other coal
  - 27011900: Other coal (thermal)
  - 27012000: Briquettes, ovoids and similar solid fuels manufactured from coal
  - 27021000: Lignite, not agglomerated
  - 27022000: Lignite, agglomerated

API Endpoint:
  GET https://webapi.bps.go.id/v1/api/dataexim/?sumber=1&periode=1&jenishs=2&tahun={YYYY}&kodehs=27011100;27011210;27011290;27011900;27012000;27021000;27022000&key={BPS_API_KEY}

Output:
  data/commodities/indonesia_coal_exports_monthly.csv
  data/commodities/indonesia_coal_ports_destinations.json
"""

import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = ROOT / "data" / "commodities"
MANIFEST_PATH = ROOT / "data" / "provenance" / "manifest.json"
CACHE_DIR = COMMODITIES_DIR / ".cache_bps_raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BPS_URL = "https://webapi.bps.go.id/v1/api/dataexim/"
COAL_HS_CODES = "27011100;27011210;27011290;27011900;27012000;27021000;27022000"

MONTH_MAP = {
    "01": "01", "02": "02", "03": "03", "04": "04", "05": "05", "06": "06",
    "07": "07", "08": "08", "09": "09", "10": "10", "11": "11", "12": "12",
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12"
}


def get_bps_api_key():
    api_key = os.environ.get("BPS_API_KEY", "").strip()
    if not api_key and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                api_key, _ = winreg.QueryValueEx(k, "BPS_API_KEY")
                api_key = api_key.strip()
        except Exception:
            pass
    return api_key


def parse_month_str(bulan_str):
    """Parse BPS month string e.g. '[07] Juli' or 'Juli' into '07'."""
    m = re.search(r"\[(\d{2})\]", bulan_str)
    if m:
        return m.group(1)
    clean = bulan_str.lower().strip()
    return MONTH_MAP.get(clean, "01")


def fetch_year(year, api_key="", use_cache=True):
    """Fetch all monthly port x destination export records for a given year."""
    cache_file = CACHE_DIR / f"bps_coal_{year}.json"
    if use_cache and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
                return payload.get("data", [])
        except Exception:
            pass

    if not api_key:
        return []

    params = {
        "sumber": 1,      # 1 = exports
        "periode": 1,     # 1 = monthly
        "jenishs": 2,     # 2 = 8-digit HS
        "tahun": year,
        "kodehs": COAL_HS_CODES,
        "key": api_key
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ShippingBPSClient/1.0"
    }
    resp = requests.get(BPS_URL, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "OK":
        print(f"Warning: BPS returned status '{payload.get('status')}' for year {year}")
        return []

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload.get("data", [])


def update_manifest(csv_path, row_count, min_date, max_date):
    """Synchronize manifest row counts for both series and datasets sections."""
    if not MANIFEST_PATH.exists():
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for section in ["series", "datasets"]:
        for item in manifest.get(section, []):
            if "indonesia_coal" in item.get("id", "") or "indonesia_coal" in item.get("file", ""):
                item["rows"] = row_count
                item["row_count"] = row_count
                item["data_through"] = max_date
                item["min_date"] = min_date
                item["max_date"] = max_date
                item["last_verified"] = datetime.utcnow().strftime("%Y-%m-%d")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    api_key = get_bps_api_key()
    has_cache = any(CACHE_DIR.glob("bps_coal_*.json"))
    if not api_key and not has_cache:
        print("INFO: BPS_API_KEY environment variable is not set and no cache found.")
        print("To run locally: set BPS_API_KEY=<key> or setx BPS_API_KEY <key>")
        print("To run in CI: GitHub Actions workflow .github/workflows/bps_monthly.yml runs with secrets.BPS_API_KEY.")
        sys.exit(0)

    current_year = datetime.utcnow().year
    years = list(range(2018, current_year + 1))
    print(f"Fetching BPS Indonesia coal exports for years {years[0]}–{years[-1]}...")

    all_records = []
    for y in years:
        print(f"  Querying year {y}...")
        try:
            records = fetch_year(y, api_key)
            all_records.extend(records)
            print(f"    Got {len(records)} records for {y}")
            time.sleep(0.5)  # Polite pacing
        except Exception as e:
            print(f"    Error fetching {y}: {e}")

    if not all_records:
        print("No records retrieved from BPS API.")
        return

    # Process records by month:
    # Process records by month:
    monthly_data = defaultdict(lambda: {
        "bituminous_kg": 0.0,
        "other_coal_kg": 0.0,
        "lignite_kg": 0.0,
        "value_usd": 0.0,
        "dests": defaultdict(float),
        "ports": defaultdict(float)
    })

    COUNTRY_MAP = {
        "CHINA": "China",
        "INDIA": "India",
        "PHILIPPINES": "Philippines",
        "VIET NAM": "Viet Nam",
        "JAPAN": "Japan",
        "KOREA, REPUBLIC OF": "South Korea",
        "MALAYSIA": "Malaysia",
        "TAIWAN, PROVINCE OF CHINA": "Taiwan",
        "THAILAND": "Thailand",
        "BANGLADESH": "Bangladesh"
    }

    for r in all_records:
        tahun = str(r.get("tahun", "")).strip()
        bulan_raw = str(r.get("bulan", "")).strip()
        month = parse_month_str(bulan_raw)
        date_str = f"{tahun}-{month}-01"

        kodehs = str(r.get("kodehs", "")).strip()
        pod = str(r.get("pod", "")).strip()
        ctr = str(r.get("ctr", "")).strip()
        clean_ctr = COUNTRY_MAP.get(ctr.upper(), ctr.title()) if ctr else ""

        try:
            val_usd = float(r.get("value", 0.0) or 0.0)
            netweight_kg = float(r.get("netweight", 0.0) or 0.0)
        except (ValueError, TypeError):
            continue

        if "270112" in kodehs:
            monthly_data[date_str]["bituminous_kg"] += netweight_kg
        elif "2702" in kodehs:
            monthly_data[date_str]["lignite_kg"] += netweight_kg
        else:
            monthly_data[date_str]["other_coal_kg"] += netweight_kg

        monthly_data[date_str]["value_usd"] += val_usd
        if clean_ctr:
            monthly_data[date_str]["dests"][clean_ctr] += netweight_kg
        if pod:
            monthly_data[date_str]["ports"][pod.title()] += netweight_kg

    # Build rows
    out_rows = []
    ports_dest_detail = {}

    for d in sorted(monthly_data.keys()):
        m = monthly_data[d]
        bitum_mt = round(m["bituminous_kg"] / 1e9, 2)
        other_mt = round(m["other_coal_kg"] / 1e9, 2)
        lignite_mt = round(m["lignite_kg"] / 1e9, 2)
        hs2701_mt = round((m["bituminous_kg"] + m["other_coal_kg"]) / 1e9, 2)
        total_seaborne_mt = round((m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"]) / 1e9, 2)
        val_usd = round(m["value_usd"], 2)

        # Destinations sorted by volume
        sorted_dests = sorted(m["dests"].items(), key=lambda x: x[1], reverse=True)
        dest_items = []
        for c, kg in sorted_dests:
            mt = round(kg / 1e9, 2)
            pct = round((kg / (m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"])) * 100, 1) if (m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"]) > 0 else 0.0
            dest_items.append({"destination": c, "tonnes_mt": mt, "share_pct": pct})

        d1 = f"{dest_items[0]['destination']} {dest_items[0]['tonnes_mt']} Mt ({dest_items[0]['share_pct']}%)" if len(dest_items) > 0 else ""
        d2 = f"{dest_items[1]['destination']} {dest_items[1]['tonnes_mt']} Mt ({dest_items[1]['share_pct']}%)" if len(dest_items) > 1 else ""
        d3 = f"{dest_items[2]['destination']} {dest_items[2]['tonnes_mt']} Mt ({dest_items[2]['share_pct']}%)" if len(dest_items) > 2 else ""

        # Top loading ports
        sorted_ports = sorted(m["ports"].items(), key=lambda x: x[1], reverse=True)
        port_items = []
        for p, kg in sorted_ports:
            mt = round(kg / 1e9, 2)
            pct = round((kg / (m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"])) * 100, 1) if (m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"]) > 0 else 0.0
            port_items.append({"port": p, "tonnes_mt": mt, "share_pct": pct})

        out_rows.append({
            "date": d,
            "volume_mt": total_seaborne_mt,
            "bituminous_mt": bitum_mt,
            "other_coal_mt": other_mt,
            "lignite_mt": lignite_mt,
            "headline_coal_mt": hs2701_mt,
            "total_coal_and_lignite_mt": total_seaborne_mt,
            "value_usd": val_usd,
            "seaborne_mt": total_seaborne_mt,
            "top_destination_1": d1,
            "top_destination_2": d2,
            "top_destination_3": d3,
            "source_url": "https://webapi.bps.go.id/v1/api/dataexim/",
            "publisher": "Badan Pusat Statistik (BPS) Indonesia",
            "source_quote": "",
            "method": "BPS Official Export API v1 (dataexim 8-digit series)"
        })

        ports_dest_detail[d] = {
            "total_seaborne_mt": total_seaborne_mt,
            "headline_coal_mt": hs2701_mt,
            "bituminous_mt": bitum_mt,
            "other_coal_mt": other_mt,
            "lignite_mt": lignite_mt,
            "top_destinations": dest_items,
            "top_ports": port_items
        }

    # Write output CSV
    csv_file = COMMODITIES_DIR / "indonesia_coal_exports_monthly.csv"
    COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date", "volume_mt", "bituminous_mt", "other_coal_mt", "lignite_mt",
        "headline_coal_mt", "total_coal_and_lignite_mt", "value_usd", "seaborne_mt",
        "top_destination_1", "top_destination_2", "top_destination_3",
        "source_url", "publisher", "source_quote", "method"
    ]
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    detail_file = COMMODITIES_DIR / "indonesia_coal_ports_destinations.json"
    with open(detail_file, "w", encoding="utf-8") as f:
        json.dump(ports_dest_detail, f, indent=2)

    min_date = out_rows[0]["date"]
    max_date = out_rows[-1]["date"]
    update_manifest(csv_file, len(out_rows), min_date, max_date)
    print(f"Successfully saved {len(out_rows)} monthly rows ({min_date} to {max_date}) to {csv_file}")


if __name__ == "__main__":
    main()
