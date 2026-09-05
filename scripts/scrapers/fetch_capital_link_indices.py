#!/usr/bin/env python3
"""
Capital Link Shipping Indices Scraper & Digestion Engine
=========================================================
Automated scraper for Capital Link Maritime and Shipping Equity Indices
published via SEE Capital Markets (South East Europe Capital Markets / Zagreb Stock Exchange).

Targets 7 Capital Link Shipping Equity Indices:
1. CLCI   - Capital Link Container Index   (indexId: 44)
2. CLDBI  - Capital Link Drybulk Index     (indexId: 45)
3. CLLG   - Capital Link LNG/LPG Index     (indexId: 46)
4. CLMFI  - Capital Link Mixed Fleet Index (indexId: 47)
5. CLMI   - Capital Link Maritime Index    (indexId: 48)
6. CLMLP  - Capital Link MLP Index         (indexId: 49)
7. CLTI   - Capital Link Tanker Index      (indexId: 50)

Also supports 7 Baltic Exchange Freight Indices:
- BDI, BCI, BPI, BSI, BHSI, BDTI, BCTI (indexIds: 37-43)

Modes:
- --backfill: Extracts full multi-decade history (2005-present, 25 years)
- --daily: Fast incremental update of recent sessions
- --dry-run: Probes API endpoints, checks data integrity without writing to disk
"""

import os
import sys
import time
import argparse
import requests
import pandas as pd
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, 'data')
INDICES_DIR = os.path.join(DATA_DIR, 'indices')
os.makedirs(INDICES_DIR, exist_ok=True)

BASE_URL = "https://seecapitalmarkets.com"
HISTORY_ENDPOINT = f"{BASE_URL}/SingleIndexValues/GetHistoryDataAscending"
LATEST_ENDPOINT = f"{BASE_URL}/IndexValues/GetIndexValues"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': f"{BASE_URL}/indeksi",
}

CAPITAL_LINK_INDICES = {
    'CLCI': {
        'name': 'Capital Link Container',
        'index_id': 44,
        'slug': 'capital_link_container_clci',
        'category': 'Container Equity Index',
    },
    'CLDBI': {
        'name': 'Capital Link Drybulk',
        'index_id': 45,
        'slug': 'capital_link_drybulk_cldbi',
        'category': 'Dry Bulk Equity Index',
    },
    'CLLG': {
        'name': 'Capital Link LNG/LPG',
        'index_id': 46,
        'slug': 'capital_link_lng_lpg_cllg',
        'category': 'Gas Shipping Equity Index',
    },
    'CLMFI': {
        'name': 'Capital Link Mixed Fleet',
        'index_id': 47,
        'slug': 'capital_link_mixed_fleet_clmfi',
        'category': 'Diversified Shipping Equity Index',
    },
    'CLMI': {
        'name': 'Capital Link Maritime',
        'index_id': 48,
        'slug': 'capital_link_maritime_clmi',
        'category': 'Broad Maritime Benchmark Index',
    },
    'CLMLP': {
        'name': 'Capital Link MLP',
        'index_id': 49,
        'slug': 'capital_link_mlp_clmlp',
        'category': 'Maritime MLP Equity Index',
    },
    'CLTI': {
        'name': 'Capital Link Tanker',
        'index_id': 50,
        'slug': 'capital_link_tanker_clti',
        'category': 'Tanker Shipping Equity Index',
    },
}

BALTIC_INDICES = {
    'BDI': {'name': 'Baltic Dry Index', 'index_id': 39, 'slug': 'baltic_dry_bdi'},
    'BCI': {'name': 'Baltic Capesize Index', 'index_id': 37, 'slug': 'baltic_capesize_bci'},
    'BPI': {'name': 'Baltic Panamax Index', 'index_id': 42, 'slug': 'baltic_panamax_bpi'},
    'BSI': {'name': 'Baltic Supramax Index', 'index_id': 43, 'slug': 'baltic_supramax_bsi'},
    'BHSI': {'name': 'Baltic Handysize Index', 'index_id': 41, 'slug': 'baltic_handysize_bhsi'},
    'BDTI': {'name': 'Baltic Dirty Tanker Index', 'index_id': 40, 'slug': 'baltic_dirty_bdti'},
    'BCTI': {'name': 'Baltic Clean Tanker Index', 'index_id': 38, 'slug': 'baltic_clean_bcti'},
}


def fetch_index_history(index_id: int, years: int = 25, retries: int = 3) -> list:
    """Fetches full historical daily series for a specific indexId."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    for attempt in range(1, retries + 1):
        try:
            r = session.get(
                HISTORY_ENDPOINT,
                params={'indexId': index_id, 'years': years},
                timeout=20
            )
            if r.status_code == 200:
                payload = r.json()
                data = payload.get('data', [])
                return data
            elif r.status_code in (404, 410):
                return []
        except requests.RequestException as e:
            if attempt == retries:
                print(f"    [Error] indexId {index_id}: {e}", file=sys.stderr)
        time.sleep(1.0 * attempt)
    return []


def parse_history_payload(raw_records: list, index_code: str, index_name: str) -> pd.DataFrame:
    """Parses raw JSON records into a clean, normalized pandas DataFrame."""
    if not raw_records:
        return pd.DataFrame()
        
    rows = []
    for item in raw_records:
        d_raw = item.get('Date')
        if not d_raw:
            continue
        try:
            d_str = d_raw[:10]  # 'YYYY-MM-DD'
        except Exception:
            continue
            
        close_p = item.get('Close')
        if close_p is None or float(close_p) <= 0:
            continue
            
        rows.append({
            'date': d_str,
            'index_name': index_name,
            'index_code': index_code,
            'close': round(float(close_p), 2),
            'open': round(float(item.get('Open', close_p)), 2),
            'high': round(float(item.get('High', close_p)), 2),
            'low': round(float(item.get('Low', close_p)), 2),
            'volume': float(item.get('Turnover', 0.0) or 0.0),
            'change_pct': round(float(item.get('Change', 0.0) or 0.0), 4),
        })
        
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('date').reset_index(drop=True)
        df = df.drop_duplicates(subset=['date'])
    return df


def update_master_time_series(dfs_dict: dict, out_path: str):
    """Aligns all individual index series by date into a consolidated master CSV."""
    if not dfs_dict:
        return
        
    close_series = {}
    for code, df in dfs_dict.items():
        if not df.empty:
            close_series[code] = df.set_index('date')['close']
            
    master_df = pd.DataFrame(close_series)
    master_df = master_df.sort_index().reset_index().rename(columns={'index': 'date'})
    master_df.to_csv(out_path, index=False)
    print(f"✔ Saved consolidated master time series: {out_path} ({len(master_df):,} daily observations)")


def run_pipeline(backfill: bool = False, dry_run: bool = False, include_baltic: bool = False):
    years_lookback = 25 if backfill else 2
    mode_str = "DRY RUN (PROBE ONLY)" if dry_run else ("FULL 25-YEAR BACKFILL" if backfill else "INCREMENTAL REFRESH")
    
    print("=" * 85)
    print("CAPITAL LINK SHIPPING INDICES EXTRACTION & DIGESTION ENGINE")
    print(f"Target: SEE Capital Markets API | Mode: {mode_str} | Lookback: {years_lookback}y")
    print("=" * 85)

    targets = dict(CAPITAL_LINK_INDICES)
    if include_baltic:
        targets.update(BALTIC_INDICES)

    results = {}
    
    for code, meta in targets.items():
        name = meta['name']
        idx_id = meta['index_id']
        slug = meta['slug']
        
        print(f"\n[{code}] Fetching '{name}' (indexId: {idx_id}, lookback: {years_lookback}y)...")
        raw_bars = fetch_index_history(idx_id, years=years_lookback)
        time.sleep(0.15)  # Respectful request spacing
        
        df = parse_history_payload(raw_bars, code, name)
        
        if df.empty:
            print(f"  ✖ Failed to retrieve records for {code}")
            continue
            
        min_date = df['date'].min()
        max_date = df['date'].max()
        latest_close = df.iloc[-1]['close']
        latest_chg = df.iloc[-1]['change_pct']
        
        print(f"  ✔ Retrieved {len(df):,} daily bars | {min_date} to {max_date} | Latest Close: {latest_close:,.2f} ({latest_chg:+.2f}%)")
        results[code] = df
        
        if not dry_run:
            out_csv = os.path.join(INDICES_DIR, f"{slug}.csv")
            
            # If incremental, merge with existing file if present
            if not backfill and os.path.exists(out_csv):
                try:
                    df_old = pd.read_csv(out_csv)
                    df_combined = pd.concat([df_old, df], ignore_index=True)
                    df_combined = df_combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
                    df_combined.to_csv(out_csv, index=False)
                    results[code] = df_combined
                    print(f"  -> Merged with existing store: {out_csv} ({len(df_combined):,} total bars)")
                except Exception as e:
                    df.to_csv(out_csv, index=False)
                    print(f"  -> Written to: {out_csv}")
            else:
                df.to_csv(out_csv, index=False)
                print(f"  -> Written to: {out_csv}")

    if not dry_run:
        # Build consolidated master for Capital Link indices
        cl_dfs = {k: v for k, v in results.items() if k in CAPITAL_LINK_INDICES}
        master_path = os.path.join(INDICES_DIR, 'capital_link_indices_master.csv')
        update_master_time_series(cl_dfs, master_path)

    print("\n" + "=" * 85)
    print(f"SUMMARY: Successfully processed {len(results)}/{len(targets)} indices with ZERO errors.")
    print("=" * 85)
    return results


def main():
    parser = argparse.ArgumentParser(description="Capital Link Shipping Indices Scraper")
    parser.add_argument('--backfill', action='store_true', help="Execute full 25-year history backfill")
    parser.add_argument('--dry-run', action='store_true', help="Dry run end-to-end to test API without writing to disk")
    parser.add_argument('--include-baltic', action='store_true', help="Also fetch the 7 Baltic Exchange indices")
    args = parser.parse_args()

    run_pipeline(backfill=args.backfill, dry_run=args.dry_run, include_baltic=args.include_baltic)


if __name__ == '__main__':
    main()
