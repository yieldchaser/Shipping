"""
Explicit Historical ETF Holdings Migration Command
==================================================
ONE-TIME EXPLICIT MIGRATION TOOL:
Iterates through cumulative holdings history files (data/etf/*_holdings_history.csv),
creates immutable raw archives under data/etf/raw_holdings/<FUND>/<DATE>.csv for every historical
as-of date, computes exact SHA-256 hashes, and populates the append-only provenance manifest.

Crucial Governance Rule:
Historical migration marks reconstructed holdings as 'BACKFILLED_LOCAL_DERIVED' (not official verified response archives).
"""

import os
import sys
import pandas as pd
from typing import Dict, Any, List, Optional

# Add scripts directory to path
SCRIPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from provenance_manifest_manager import (
    save_immutable_raw_archive,
    register_provenance_record,
    load_manifest,
    save_manifest,
    calculate_sha256,
    get_base_data_dir,
    OFFICIAL_SOURCE_URLS
)

def get_historical_files() -> Dict[str, str]:
    base = get_base_data_dir()
    return {
        'BDRY': os.path.join(base, 'bdry_holdings_history.csv'),
        'BWET': os.path.join(base, 'bwet_holdings_history.csv')
    }

def migrate_historical_archives_for_fund(fund: str, history_file: str) -> List[Dict[str, Any]]:
    """
    Reads historical history CSV, extracts each unique date, saves immutable raw archives,
    and registers them in provenance manifest as BACKFILLED_LOCAL_DERIVED.
    """
    f_upper = fund.upper()
    if not os.path.exists(history_file):
        print(f"ERROR: History file not found: {history_file}")
        return []
        
    df = pd.read_csv(history_file)
    if df.empty or 'date' not in df.columns:
        print(f"ERROR: History file {history_file} is empty or missing 'date' column.")
        return []
        
    df['date_str'] = df['date'].astype(str).str.strip()
    unique_dates = sorted(df['date_str'].unique())
    print(f"Found {len(unique_dates)} distinct historical dates for {f_upper}.")
    
    migrated_records = []
    for d_str in unique_dates:
        day_df = df[df['date_str'] == d_str].copy()
        day_df = day_df.drop(columns=['date', 'date_str'], errors='ignore')
        
        # Save derived immutable archive
        rel_path, comp_sha = save_immutable_raw_archive(f_upper, d_str, day_df)
        
        # Register in provenance manifest with BACKFILLED_LOCAL_DERIVED status
        rec = register_provenance_record(
            fund=f_upper,
            as_of_date=d_str,
            immutable_archive_path=rel_path,
            archive_sha256=comp_sha,
            official_source_url=OFFICIAL_SOURCE_URLS.get(f_upper),
            raw_source_path=rel_path,
            raw_source_sha256=comp_sha,
            is_official_as_of_date=False,
            date_sourcing="BACKFILLED_LOCAL_DERIVED",
            provenance_status="BACKFILLED_LOCAL_DERIVED"
        )
        migrated_records.append(rec)
        
    print(f"[OK] Successfully migrated {len(migrated_records)} archives and manifest records for {f_upper}.")
    return migrated_records

def main():
    print("=" * 80)
    print("      EXPLICIT ONE-TIME HISTORICAL ETF HOLDINGS ARCHIVE MIGRATION      ")
    print("=" * 80)
    
    total_migrated = 0
    hist_files = get_historical_files()
    for fund, hist_file in hist_files.items():
        records = migrate_historical_archives_for_fund(fund, hist_file)
        total_migrated += len(records)
        
    print("\n" + "=" * 80)
    print(f"MIGRATION COMPLETE: {total_migrated} total historical records registered in manifest.")
    print("=" * 80)

if __name__ == '__main__':
    main()
