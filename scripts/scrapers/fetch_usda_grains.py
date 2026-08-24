"""
Production USDA Agricultural Transportation & Maritime Freight Data Engine.
Directly downloads clean CSV tabular datasets from USDA AgTransport:
1. Daily Bunker Fuel Prices (4v3x-mj86) -> VLSFO, MGO, IFO 380
2. Grain Vessel Rates & US Gulf vs PNW Spreads (ehs5-yac3) -> Gulf_To_Japan, PNW_To_Japan, Gulf_PNW_Spread
3. US vs Brazil Landed Soybean Transportation Costs to China (g9w7-d2kh)
4. Grain Vessel Loading Queues in US Gulf and PNW (uiht-9xts)
5. US vs Brazil Transportation Cost Spreads to China (3j5w-mz4e)
6. Global Bulk Vessel Fleet Size and Capacity Over Time (2bqa-utsv)
"""

import os
import io
import urllib.request
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126",
    "Accept": "text/csv,application/csv",
}

DATASETS = {
    "usda_bunker_fuel_daily.csv": {
        "id": "4v3x-mj86",
        "name": "Daily Bunker Fuel Prices (VLSFO, MGO, IFO 380)",
        "dir": DERIVED_DIR,
    },
    "usda_grain_vessel_rates_japan.csv": {
        "id": "ehs5-yac3",
        "name": "Grain Vessel Rates (Gulf & PNW to Japan & Spreads)",
        "dir": DERIVED_DIR,
    },
    "usda_us_vs_brazil_landed_costs.csv": {
        "id": "g9w7-d2kh",
        "name": "US vs Brazil Soybean Landed Costs to China",
        "dir": COMMODITIES_DIR,
    },
    "usda_grain_vessel_loading_queues.csv": {
        "id": "uiht-9xts",
        "name": "Grain Vessel Loading Queues (Gulf & PNW In-Port & Due)",
        "dir": COMMODITIES_DIR,
    },
    "usda_us_vs_brazil_cost_spreads.csv": {
        "id": "3j5w-mz4e",
        "name": "US vs Brazil Transportation Cost Spreads to China",
        "dir": DERIVED_DIR,
    },
    "usda_bulk_vessel_fleet_history.csv": {
        "id": "2bqa-utsv",
        "name": "Global Bulk Vessel Fleet Capacity Over Time",
        "dir": DERIVED_DIR,
    },
}

def fetch_dataset(filename, info):
    dataset_id = info["id"]
    name = info["name"]
    target_dir = info["dir"]
    url = f"https://agtransport.usda.gov/api/views/{dataset_id}/rows.csv?accessType=DOWNLOAD"
    
    print(f"[+] Fetching {name} ({dataset_id})...")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as resp:
        content = resp.read()
        df = pd.read_csv(io.BytesIO(content))
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / filename
        df.to_csv(out_path, index=False)
        print(f"    [OK] Saved {len(df):,} rows and {len(df.columns)} columns to {out_path.name}")
        return len(df)

def main():
    print("=" * 80)
    print("  USDA AGTRANSPORT PRODUCTION MARITIME INGESTION ENGINE")
    print("=" * 80)
    
    results = {}
    for filename, info in DATASETS.items():
        try:
            count = fetch_dataset(filename, info)
            results[info["name"]] = count
        except Exception as e:
            print(f"    [!] Error fetching {info['name']}: {e}")
            results[info["name"]] = False
            
    print("\n" + "=" * 80)
    print("  PRODUCTION INGESTION RESULTS:")
    for name, count in results.items():
        status = f"{count:,} rows" if count else "FAILED"
        print(f"  • {name:55s} -> {status}")
    print("=" * 80)

if __name__ == "__main__":
    main()
