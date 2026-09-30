"""Update data/derived/iron_ore_restocking.csv with verified MMi Iron Ore LlamaParse series.

Replaces missing or frozen OCR values in iron_ore_restocking.csv with 100% verified
daily index assessments from Metals Market Index (MMi) published in Hellenic Shipping News.
Preserves existing macroeconomic columns (inventories_mt, steel_production_mt, steel_inventories_mt).
"""

import shutil
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TARGET_CSV = ROOT / "data" / "derived" / "iron_ore_restocking.csv"
BACKUP_CSV = ROOT / "data" / "derived" / "iron_ore_restocking.csv.bak"
SERIES_CSV = ROOT / "data" / "extracted" / "series" / "hellenic_iron_ore_table_series.csv"

def main():
    if not SERIES_CSV.exists():
        print(f"Series file {SERIES_CSV} not found. Run extraction first.")
        return

    print(f"Loading existing {TARGET_CSV}...")
    target_df = pd.read_csv(TARGET_CSV)
    original_len = len(target_df)
    original_cols = list(target_df.columns)

    if not BACKUP_CSV.exists():
        shutil.copy2(TARGET_CSV, BACKUP_CSV)
        print(f"Created backup at {BACKUP_CSV}")

    series_df = pd.read_csv(SERIES_CSV)
    print(f"Loaded {len(series_df)} rows from verified series.")

    # Pivot series into date -> {cfr_62, cfr_65, port_stock_62, port_stock_65}
    verified_by_date = {}

    for _, r in series_df.iterrows():
        dt = r["issue_date"]
        icode = str(r["index_code"]).upper()
        if dt not in verified_by_date:
            verified_by_date[dt] = {}

        # CFR 62
        if icode == "IOSI62" and pd.notnull(r["cfr_usd_dmt"]):
            verified_by_date[dt]["cfr_62"] = float(r["cfr_usd_dmt"])
        elif icode == "IOPI62" and pd.notnull(r["cfr_usd_dmt"]) and "cfr_62" not in verified_by_date[dt]:
            verified_by_date[dt]["cfr_62"] = float(r["cfr_usd_dmt"])

        # CFR 65
        if icode == "IOSI65" and pd.notnull(r["cfr_usd_dmt"]):
            verified_by_date[dt]["cfr_65"] = float(r["cfr_usd_dmt"])
        elif icode == "IOPI65" and pd.notnull(r["cfr_usd_dmt"]) and "cfr_65" not in verified_by_date[dt]:
            verified_by_date[dt]["cfr_65"] = float(r["cfr_usd_dmt"])

        # Port Stock 62 (FOT RMB/wmt)
        if icode == "IOPI62" and pd.notnull(r["fot_rmb_wmt"]):
            verified_by_date[dt]["port_stock_62"] = float(r["fot_rmb_wmt"])

        # Port Stock 65 (FOT RMB/wmt)
        if icode == "IOPI65" and pd.notnull(r["fot_rmb_wmt"]):
            verified_by_date[dt]["port_stock_65"] = float(r["fot_rmb_wmt"])

    # Update target_df rows
    target_dict_by_date = {r["date"]: r.to_dict() for _, r in target_df.iterrows()}

    updated_count = 0
    added_count = 0

    for dt, vals in sorted(verified_by_date.items()):
        if dt in target_dict_by_date:
            row = target_dict_by_date[dt]
            for col, v in vals.items():
                row[col] = v
            target_dict_by_date[dt] = row
            updated_count += 1
        else:
            row = {c: np.nan for c in original_cols}
            row["date"] = dt
            for col, v in vals.items():
                row[col] = v
            target_dict_by_date[dt] = row
            added_count += 1

    updated_df = pd.DataFrame(list(target_dict_by_date.values()))
    updated_df = updated_df.sort_values("date").reset_index(drop=True)
    updated_df = updated_df[original_cols]

    updated_df.to_csv(TARGET_CSV, index=False)
    print(f"Successfully updated {TARGET_CSV}:")
    print(f"  Total rows: {len(updated_df)} (original: {original_len})")
    print(f"  Updated existing dates: {updated_count}")
    print(f"  Added new dates: {added_count}")

if __name__ == "__main__":
    main()
