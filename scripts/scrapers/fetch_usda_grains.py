"""
Standalone USDA Agricultural Marketing Service (AMS) & AgTransport Fetcher.
Pulls open Socrata datasets for:
1. Daily Bunker Fuel Prices (y4ft-fdwn)
2. Bulk Grain Ocean Freight Rates (ehic-wtxb)
3. Bulk Grain Ocean Freight Rate Spreads (7is6-abe5)
4. Grain Vessel Loading Activity in US Gulf and PNW (uiht-9xts)
5. Brazil to China / Germany Ocean Freight Rates (ahq9-q9dg)
"""

import os
import json
import urllib.request
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126",
    "Accept": "application/json",
}

DATASETS = {
    "bunker_prices": {
        "id": "y4ft-fdwn",
        "name": "Daily Bunker Fuel Prices",
        "output": DERIVED_DIR / "usda_bunker_fuel_daily.csv",
    },
    "bulk_ocean_rates": {
        "id": "ehic-wtxb",
        "name": "Bulk Grain Ocean Freight Rates",
        "output": COMMODITIES_DIR / "usda_bulk_grain_ocean_rates.csv",
    },
    "freight_spreads": {
        "id": "7is6-abe5",
        "name": "Bulk Grain Ocean Freight Rate Spreads",
        "output": DERIVED_DIR / "usda_grain_freight_spreads.csv",
    },
    "vessel_loading": {
        "id": "uiht-9xts",
        "name": "Grain Vessel Loading Activity (US Gulf & PNW)",
        "output": COMMODITIES_DIR / "usda_grain_vessel_loading.csv",
    },
    "brazil_china_rates": {
        "id": "ahq9-q9dg",
        "name": "Brazil Ocean Freight Rates to China & Germany",
        "output": COMMODITIES_DIR / "usda_brazil_ocean_freight.csv",
    },
}

def fetch_socrata_dataset(dataset_id, limit=5000):
    url = f"https://agtransport.usda.gov/resource/{dataset_id}.json?$limit={limit}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 80)
    print("  USDA AGTRANSPORT OPEN MARITIME DATA INGESTION ENGINE")
    print("=" * 80)
    
    COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    for key, info in DATASETS.items():
        print(f"\n[+] Fetching {info['name']} ({info['id']})...")
        try:
            records = fetch_socrata_dataset(info["id"])
            if records:
                df = pd.DataFrame(records)
                df.to_csv(info["output"], index=False)
                print(f"    [OK] Saved {len(df)} rows to {info['output'].name}")
                results[key] = len(df)
            else:
                print(f"    [!] No records returned for {info['id']}")
                results[key] = 0
        except Exception as e:
            print(f"    [!] Error fetching {info['id']}: {e}")
            results[key] = False
            
    print("\n" + "=" * 80)
    print("  INGESTION SUMMARY:")
    for k, count in results.items():
        status = f"{count} records" if count else "FAILED"
        print(f"  • {DATASETS[k]['name']:45s} -> {status}")
    print("=" * 80)

if __name__ == "__main__":
    main()
