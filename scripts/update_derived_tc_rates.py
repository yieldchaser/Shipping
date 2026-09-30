"""Update data/derived/time_charter_rates.csv with verified LlamaParse Alibra series.

Replaces flawed legacy Tesseract OCR rows (2021-07-07 to 2026-09-16) with 100% verified
LlamaParse extraction results from Hellenic Shipping News image assets.
Maintains exact 66-column schema for full backward compatibility with frontend charts.
"""

import csv
import shutil
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TC_CSV = ROOT / "data" / "derived" / "time_charter_rates.csv"
TC_BAK = ROOT / "data" / "derived" / "time_charter_rates.csv.bak"

DRY_SERIES = ROOT / "data" / "extracted" / "series" / "hellenic_alibra_dry_tc_series.csv"
WET_SERIES = ROOT / "data" / "extracted" / "series" / "hellenic_alibra_tanker_tc_series.csv"

def norm_dry_class(c):
    c = str(c).upper()
    if 'CAPE' in c: return 'capesize'
    if 'PANA' in c: return 'panamax'
    if 'SUPRA' in c or 'ULTRA' in c or 'SMAX' in c or 'S MAX' in c: return 'supramax'
    if 'HANDY' in c: return 'handysize'
    return 'unknown'

def norm_dry_tenor(t):
    t = str(t).upper()
    if '6' in t or '4' in t: return '4_6m'
    if '1' in t: return '1y'
    if '2' in t: return '2y'
    return 'unknown'

def norm_dry_basin(b):
    b = str(b).upper()
    if 'ATL' in b: return 'atl'
    if 'PAC' in b: return 'pac'
    return 'unknown'

def norm_wet_class(c):
    c = str(c).upper()
    if 'VLCC' in c: return 'vlcc'
    if 'SUEZ' in c: return 'suezmax'
    if 'AFRA' in c: return 'aframax'
    if 'MR' in c: return 'mr'
    if 'LR1' in c: return 'lr1'
    if 'LR2' in c: return 'lr2'
    if 'HANDY' in c: return 'handytanker'
    return 'unknown'

def norm_wet_tenor(t):
    t = str(t).upper()
    if '1' in t: return '1y'
    if '2' in t: return '2y'
    if '3' in t: return '3y'
    if '5' in t: return '5y'
    return 'unknown'

def main():
    print(f"Loading existing {TC_CSV}...")
    tc_df = pd.read_csv(TC_CSV)
    original_len = len(tc_df)
    original_cols = list(tc_df.columns)

    # Backup original file
    if not TC_BAK.exists():
        shutil.copy2(TC_CSV, TC_BAK)
        print(f"Created backup at {TC_BAK}")

    # Load verified extracted series
    dry_df = pd.read_csv(DRY_SERIES)
    wet_df = pd.read_csv(WET_SERIES)

    dry_df['norm_class'] = dry_df['vessel_class'].apply(norm_dry_class)
    dry_df['norm_tenor'] = dry_df['tenor'].apply(norm_dry_tenor)
    dry_df['norm_basin'] = dry_df['basin'].apply(norm_dry_basin)

    wet_df['norm_class'] = wet_df['vessel_class'].apply(norm_wet_class)
    wet_df['norm_tenor'] = wet_df['tenor'].apply(norm_wet_tenor)

    # Build dictionary of date -> column -> value
    new_data = {}

    for _, r in dry_df.iterrows():
        dt = r['issue_date']
        col_name = f"{r['norm_class']}_{r['norm_tenor']}_{r['norm_basin']}"
        if dt not in new_data:
            new_data[dt] = {}
        new_data[dt][col_name] = r['rate_usd_pdpr']

    # Compute dry averages (atl + pac) / 2
    for dt, cols in new_data.items():
        for seg in ['capesize', 'panamax', 'supramax', 'handysize']:
            for tenor in ['4_6m', '1y', '2y']:
                atl_val = cols.get(f"{seg}_{tenor}_atl")
                pac_val = cols.get(f"{seg}_{tenor}_pac")
                avg_col = f"{seg}_{tenor}_avg"
                if atl_val is not None and pac_val is not None:
                    cols[avg_col] = (atl_val + pac_val) / 2.0
                elif atl_val is not None:
                    cols[avg_col] = atl_val
                elif pac_val is not None:
                    cols[avg_col] = pac_val

    # Tanker rates
    for _, r in wet_df.iterrows():
        dt = r['issue_date']
        col_name = f"{r['norm_class']}_{r['norm_tenor']}"
        if dt not in new_data:
            new_data[dt] = {}
        new_data[dt][col_name] = r['rate_usd_pdpr']

    print(f"Prepared verified data across {len(new_data)} distinct weekly dates.")

    # Update tc_df rows where date is in new_data
    updated_dates = 0
    added_dates = 0

    tc_dict_by_date = {r['date']: r.to_dict() for _, r in tc_df.iterrows()}

    for dt, cols in sorted(new_data.items()):
        if dt in tc_dict_by_date:
            row = tc_dict_by_date[dt]
            row['source'] = 'alibra_ocr'
            for col_name, val in cols.items():
                if col_name in original_cols:
                    row[col_name] = val
            tc_dict_by_date[dt] = row
            updated_dates += 1
        else:
            # Create new row
            row = {c: np.nan for c in original_cols}
            row['date'] = dt
            row['source'] = 'alibra_ocr'
            for col_name, val in cols.items():
                if col_name in original_cols:
                    row[col_name] = val
            tc_dict_by_date[dt] = row
            added_dates += 1

    updated_df = pd.DataFrame(list(tc_dict_by_date.values()))
    updated_df = updated_df.sort_values('date').reset_index(drop=True)

    # Reorder columns exactly
    updated_df = updated_df[original_cols]

    # Write back to CSV
    updated_df.to_csv(TC_CSV, index=False)
    print(f"Successfully updated {TC_CSV}:")
    print(f"  Total rows: {len(updated_df)} (original: {original_len})")
    print(f"  Updated existing dates: {updated_dates}")
    print(f"  Added new dates: {added_dates}")

if __name__ == "__main__":
    main()
