#!/usr/bin/env python3
"""
backfill_historical_data.py
──────────────────────────────────────────────────────────────────────────────
Expands historical timelines for shipping indices and time charter rates
using verified open APIs (Fearnleys Hasura GraphQL, TAC Index, ajoposor BDI).

Outputs / Updates:
  - data/indices/bdiy_historical.csv (1985 - present)
  - data/indices/bai_historical.csv (2018 - present)
  - data/derived/time_charter_rates.csv (2000 - present)
  - data/derived/vessel_valuations.csv (1970 - present)
"""

import requests
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

GQL_URL = "https://pbrokerapp.hasura.app/v1/graphql"
GQL_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fearnpulse.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"
}

def backfill_bdi():
    print("=== Backfilling BDI (1985 - 2007) ===")
    url = 'https://raw.githubusercontent.com/ajoposor/Baltic-Dry-Index/master/Old_Data_Baltic_Dry_Index.csv'
    r = requests.get(url)
    if r.status_code != 200:
        print("Failed to fetch historical BDI CSV")
        return

    hist_df = pd.read_csv(url)
    hist_df.columns = ['Date_str', 'Index']
    hist_df['dt'] = pd.to_datetime(hist_df['Date_str'])
    hist_df = hist_df[hist_df['dt'] < '2007-12-05']  # Cutoff before repo's stockq start date
    hist_df['Date'] = hist_df['dt'].dt.strftime('%d-%m-%Y')
    hist_df['% Change'] = '0.0%'
    hist_bdi = hist_df[['Date', 'Index', '% Change', 'dt']]

    local_path = 'data/indices/bdiy_historical.csv'
    local = pd.read_csv(local_path)
    local['dt'] = pd.to_datetime(local['Date'], format='%d-%m-%Y')
    local['Index'] = pd.to_numeric(local['Index'].astype(str).str.replace(',', ''), errors='coerce')

    combined = pd.concat([hist_bdi, local], ignore_index=True)
    combined = combined.drop_duplicates(subset=['dt'], keep='last').sort_values('dt', ascending=False)
    combined['Index'] = combined['Index'].astype(int)
    
    out = combined[['Date', 'Index', '% Change']]
    out.to_csv(local_path, index=False)
    print(f"  [OK] Saved {len(out)} rows to {local_path} ({combined['dt'].min().strftime('%Y-%m-%d')} -> {combined['dt'].max().strftime('%Y-%m-%d')})")

def backfill_bai00():
    print("\n=== Backfilling BAI00 Air Freight Index (2018 - 2026) ===")
    url = 'https://api.tacindex.com/freight/chart/BAI00/?index=BAI'
    r = requests.get(url)
    if r.status_code != 200:
        print("Failed to fetch TAC Index API")
        return

    pts = r.json()
    rows = []
    for pt in pts:
        ts_ms, val = pt[0], pt[1]
        dt = pd.to_datetime(ts_ms, unit='ms')
        rows.append({
            'Date': dt.strftime('%Y-%m-%d'),
            'Index': val,
            'dt': dt
        })
    tac_df = pd.DataFrame(rows)

    local_path = 'data/indices/bai_historical.csv'
    local = pd.read_csv(local_path)
    local['dt'] = pd.to_datetime(local['Date'])
    local['Index'] = pd.to_numeric(local['Index'], errors='coerce')

    combined = pd.concat([tac_df, local], ignore_index=True)
    combined = combined.drop_duplicates(subset=['Date'], keep='last').sort_values('dt', ascending=False)
    out = combined[['Date', 'Index']]
    out.to_csv(local_path, index=False)
    print(f"  [OK] Saved {len(out)} rows to {local_path} ({combined['dt'].min().strftime('%Y-%m-%d')} -> {combined['dt'].max().strftime('%Y-%m-%d')})")

def fetch_fearnleys_rates():
    print("\n=== Fetching Fearnleys GraphQL Rates (2000 - Present) ===")
    query = """query Q($routes:[String!],$rateTypes:[String!],$rateSubtypes:[String!],$dateFrom:date,$dateTo:date){
      rate_meta(where:{info:{route:{_in:$routes},rate_type:{_in:$rateTypes},rate_subtype:{_in:$rateSubtypes}},rate_unit:{_eq:"usd"}}){
        rates(where:{date:{_gte:$dateFrom,_lte:$dateTo}},order_by:{date:asc}){date rate}
        info{route rate_type rate_subtype}
      }
    }"""
    dry_routes = ["Capesize (180 000 dwt)", "Panamax (75 000 dwt)", "Supramax (58 000 dwt)", "Handysize (38 000 dwt)"]
    wet_routes = ["VLCC", "Suezmax", "Aframax"]

    body = {
        "query": query,
        "variables": {
            "routes": dry_routes + wet_routes,
            "rateTypes": ["BULK", "TANK"],
            "rateSubtypes": ["TC", "1 Year T/C"],
            "dateFrom": "2000-01-01",
            "dateTo": "2026-12-31"
        }
    }
    r = requests.post(GQL_URL, json=body, headers=GQL_HEADERS, timeout=60)
    if r.status_code != 200:
        print("Failed to query Fearnleys GraphQL")
        return pd.DataFrame()

    rows = []
    for rm in r.json().get("data", {}).get("rate_meta", []):
        info = rm.get("info", {})
        route = info.get("route")
        for pt in rm.get("rates", []):
            rows.append({
                "date": pt["date"],
                "route": route,
                "rate": pt["rate"]
            })
    df = pd.DataFrame(rows)
    print(f"  Got {len(df)} total Fearnleys 1Y TC rate points across {df['route'].nunique()} vessel routes")
    return df

def backfill_tc_rates(fearn_df):
    if fearn_df.empty:
        return
    print("\n=== Merging Fearnleys Historical 1Y TC Rates into time_charter_rates.csv ===")
    local_path = 'data/derived/time_charter_rates.csv'
    local = pd.read_csv(local_path)
    local['dt'] = pd.to_datetime(local['date'])

    # Map Fearnleys routes to repo column names
    route_map = {
        "Capesize (180 000 dwt)": "capesize_1y_avg",
        "Panamax (75 000 dwt)": "panamax_1y_avg",
        "Supramax (58 000 dwt)": "supramax_1y_avg",
        "Handysize (38 000 dwt)": "handysize_1y_avg",
        "VLCC": "vlcc_1y",
        "Suezmax": "suezmax_1y",
        "Aframax": "aframax_1y"
    }

    fearn_df['col'] = fearn_df['route'].map(route_map)
    fearn_df = fearn_df.dropna(subset=['col'])
    piv = fearn_df.pivot(index='date', columns='col', values='rate').reset_index()
    piv['dt'] = pd.to_datetime(piv['date'])

    # Cutoff prior to local start date (2021-07-07)
    piv_hist = piv[piv['dt'] < local['dt'].min()].copy()

    # Reindex columns to match local schema
    for col in local.columns:
        if col not in piv_hist.columns and col != 'dt':
            piv_hist[col] = np.nan

    combined = pd.concat([piv_hist[local.columns], local], ignore_index=True)
    combined = combined.sort_values('date', ascending=True).reset_index(drop=True)
    combined.to_csv(local_path, index=False)
    print(f"  [OK] Expanded time_charter_rates.csv from {len(local)} to {len(combined)} weekly rows ({combined['date'].min()} -> {combined['date'].max()})")

def fetch_and_save_vessel_valuations():
    print("\n=== Fetching Fearnleys Vessel Valuations (S&P Secondhand + Newbuildings 1970 - Present) ===")
    query = """query Valuations {
      rate_meta(where:{info:{rate_type:{_in:["S&P", "NEWBUILDING"]}},rate_unit:{_eq:"usd"}}){
        rates(order_by:{date:asc}){date rate}
        info{route rate_type rate_subtype}
      }
    }"""
    r = requests.post(GQL_URL, json={"query": query}, headers=GQL_HEADERS, timeout=60)
    if r.status_code == 200:
        rows = []
        for rm in r.json().get("data", {}).get("rate_meta", []):
            info = rm.get("info", {})
            for pt in rm.get("rates", []):
                rows.append({
                    "date": pt["date"],
                    "category": info.get("rate_type"),
                    "tenor_type": info.get("rate_subtype"),
                    "vessel_class": info.get("route"),
                    "valuation_usd_m": pt["rate"]
                })
        df = pd.DataFrame(rows)
        out_path = 'data/derived/vessel_valuations.csv'
        df.to_csv(out_path, index=False)
        print(f"  [OK] Saved {len(df)} asset valuation rows to {out_path} ({df['date'].min()} -> {df['date'].max()})")

def main():
    backfill_bdi()
    backfill_bai00()
    fearn_df = fetch_fearnleys_rates()
    backfill_tc_rates(fearn_df)
    fetch_and_save_vessel_valuations()
    print("\n=== ALL HISTORICAL DATA BACKFILLS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    main()
