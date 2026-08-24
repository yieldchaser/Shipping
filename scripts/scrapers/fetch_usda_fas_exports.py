"""
USDA Foreign Agricultural Service (FAS) Export Sales Reporting Scraper.
Fetches weekly export sales, outstanding commitments, and accumulated exports
for major bulk dry commodities (Corn, Soybeans, Wheat) to key maritime destinations
(China, Japan, Mexico, EU, Egypt) via USDA AgTransport Socrata Open API.
"""

import os
import io
import json
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

# 885i-uek7: Total Outstanding Export Sales by Week, Commodity, and Country
# pamd-wd5x: Year-to-Date Grain and Soybean Inspections by Top 20 Destinations
DATASETS = {
    "usda_fas_outstanding_export_sales.csv": {
        "id": "885i-uek7",
        "name": "USDA FAS Weekly Outstanding Export Sales by Commodity & Country",
        "dir": COMMODITIES_DIR,
        "limit": 10000,
    },
    "usda_ytd_grain_inspections_top20.csv": {
        "id": "pamd-wd5x",
        "name": "USDA Grain & Soybean Inspections by Top 20 Destinations",
        "dir": COMMODITIES_DIR,
        "limit": 5000,
    },
}

def fetch_fas_dataset(filename, info):
    dataset_id = info["id"]
    name = info["name"]
    target_dir = info["dir"]
    limit = info.get("limit", 5000)
    
    url = f"https://agtransport.usda.gov/resource/{dataset_id}.csv?$limit={limit}&$order=:id"
    print(f"[+] Fetching {name} ({dataset_id})...")
    
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        content = resp.read()
        df = pd.read_csv(io.BytesIO(content))
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / filename
        df.to_csv(out_path, index=False)
        print(f"    [OK] Saved {len(df):,} rows and {len(df.columns)} columns to {out_path.name}")
        return len(df)

def main():
    print("=" * 80)
    print("  USDA FAS AGRICULTURAL EXPORT SALES INGESTION ENGINE")
    print("=" * 80)
    
    results = {}
    for filename, info in DATASETS.items():
        try:
            count = fetch_fas_dataset(filename, info)
            results[info["name"]] = count
        except Exception as e:
            print(f"    [!] Error fetching {info['name']}: {e}")
            results[info["name"]] = False
            
    print("\n" + "=" * 80)
    print("  FAS INGESTION RESULTS:")
    for name, count in results.items():
        status = f"{count:,} rows" if count else "FAILED"
        print(f"  • {name:60s} -> {status}")
    print("=" * 80)

if __name__ == "__main__":
    main()
