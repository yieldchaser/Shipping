#!/usr/bin/env python3
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = REPO_ROOT / "data" / "commodities" / "brazil_comexstat_exports.csv"

# NCM definitions
COMMODITY_NCMS = {
    "Iron Ore": ["26011100"],
    "Crude Oil": ["27090010"],
    "Soybeans": ["12011000", "12019000"],
    "Raw Sugar": ["17011300", "17011400"],
    "Corn": ["10059010"],
}

# Sane $/t bands historically
SANE_USD_PER_TONNE = {
    "Iron Ore": (20.0, 250.0),       # ~$40-$200/t typical
    "Crude Oil": (150.0, 1100.0),    # ~$25-$140/bbl (~$180-$1000/t)
    "Soybeans": (200.0, 800.0),      # ~$300-$650/t typical
    "Raw Sugar": (150.0, 750.0),     # ~$250-$600/t typical
    "Corn": (80.0, 450.0),           # ~$130-$350/t typical
}

df = pd.read_csv(CSV_PATH)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['commodity', 'date']).reset_index(drop=True)

# 1. Inspect rows with netWgt null in method
print("=== ROWS WITH 'null' IN METHOD ===")
netwgt_null = df[df['method'].astype(str).str.contains('null', case=False)]
print(f"Total: {len(netwgt_null)}")
for idx, r in netwgt_null.iterrows():
    usd_t = r['fob_usd'] / r['metric_tonnes'] if r['metric_tonnes'] > 0 else 0
    cmd = r['commodity']
    sane_min, sane_max = SANE_USD_PER_TONNE.get(cmd, (0, 99999))
    flag = "OUT_OF_BAND" if (usd_t < sane_min or usd_t > sane_max) else "OK"
    print(f"{r['date'].strftime('%Y-%m')} | {cmd:<10} | {r['metric_tonnes']:>12,.1f} t | FOB: ${r['fob_usd']:>12,.0f} | ${usd_t:>6.1f}/t | {flag} | {r['method'][:60]}")

# 2. Check for implied $/t out of sane band across the whole dataset
print("\n=== ALL ROWS WITH IMPLIED $/T OUT OF SANE BAND ===")
out_of_band = []
for idx, r in df.iterrows():
    cmd = r['commodity']
    sane_min, sane_max = SANE_USD_PER_TONNE.get(cmd, (0, 99999))
    usd_t = r['fob_usd'] / r['metric_tonnes'] if r['metric_tonnes'] > 0 else 0
    if usd_t < sane_min or usd_t > sane_max:
        out_of_band.append(r)
        print(f"{r['date'].strftime('%Y-%m')} | {cmd:<10} | {r['metric_tonnes']:>12,.1f} t | FOB: ${r['fob_usd']:>12,.0f} | ${usd_t:>6.1f}/t (Sane: {sane_min}-{sane_max}) | {r['method']}")
print(f"Total out-of-band: {len(out_of_band)}")

# 3. Check for monthly volume < 20% of trailing 12-month median
print("\n=== ROWS < 20% OF TRAILING 12-MONTH MEDIAN ===")
t12_outliers = []
for cmd in df['commodity'].unique():
    cmd_df = df[df['commodity'] == cmd].copy().sort_values('date').reset_index(drop=True)
    # Seasonal note: Sugar and Corn have seasonality, but let's check < 20% of t12 median
    for i in range(12, len(cmd_df)):
        t12 = cmd_df.loc[i-12:i-1, 'metric_tonnes'].median()
        val = cmd_df.loc[i, 'metric_tonnes']
        if t12 > 0 and val < 0.20 * t12:
            row = cmd_df.loc[i]
            t12_outliers.append(row)
            print(f"{row['date'].strftime('%Y-%m')} | {cmd:<10} | val: {val:>12,.1f} t | T12 median: {t12:>12,.1f} t ({val/t12*100:.1f}%) | {row['method']}")
print(f"Total < 20% of T12 median: {len(t12_outliers)}")
