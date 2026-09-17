#!/usr/bin/env python3
"""
apply_gap_fill.py
Applies all gap-fill patches from docs/gap_fill/patches/ to data/commodities/
following the exact specifications in docs/gap_fill/AGENT_HANDOFF.md §0.
"""

import shutil
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "docs" / "gap_fill" / "patches"
COMMODITIES = ROOT / "data" / "commodities"


def apply_ppa():
    print("1. Patching Australia PPA Iron Ore (Full Replacement)...")
    target = COMMODITIES / "australia_ppa_iron_ore.csv"
    patch = PATCHES / "australia_ppa_iron_ore__FULL_REPLACEMENT.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    shutil.copy2(patch, target)
    df = pd.read_csv(target)
    print(f"   -> Replaced with {len(df)} rows. Hedland: {len(df[df['port']=='Port Hedland'])}, Dampier: {len(df[df['port']=='Port of Dampier'])}")


def apply_minor_bulks():
    print("2. Patching Minor Bulks Monthly (Append 64 rows)...")
    target = COMMODITIES / "minor_bulks_monthly.csv"
    patch = PATCHES / "minor_bulks_monthly__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target)
    df_p = pd.read_csv(patch)
    combined = pd.concat([df_t, df_p], ignore_index=True)
    combined.drop_duplicates(subset=["date", "commodity", "trade_flow", "reporter_country", "partner_country"], keep="last", inplace=True)
    combined.sort_values(by=["commodity", "date"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Combined from {len(df_t)} to {len(combined)} rows.")


def apply_guinea():
    print("3. Patching Guinea Bauxite Exports (Replace 2017 & Append)...")
    target = COMMODITIES / "guinea_bauxite_exports.csv"
    patch_2017 = PATCHES / "guinea_bauxite_exports__REPLACE_2017_ROWS.csv"
    patch_add = PATCHES / "guinea_bauxite_exports__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target)
    # Remove old 2017 monthly mirror rows
    mask_2017_old = (df_t["date"].astype(str).str.startswith("2017")) & (df_t["granularity"] == "monthly_bilateral_mirror")
    removed = len(df_t[mask_2017_old])
    df_filtered = df_t[~mask_2017_old]
    df_rep = pd.read_csv(patch_2017)
    df_add = pd.read_csv(patch_add)
    combined = pd.concat([df_filtered, df_rep, df_add], ignore_index=True)
    combined.drop_duplicates(subset=["date", "company", "granularity"], keep="last", inplace=True)
    combined.sort_values(by=["date"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Removed {removed} old 2017 rows, added {len(df_rep)} 2017 replacements + {len(df_add)} new mirror rows. Total: {len(combined)} rows.")


def apply_brazil():
    print("4. Patching Brazil ComexStat Exports (Revisions + Aug 2026)...")
    target = COMMODITIES / "brazil_comexstat_exports.csv"
    patch_rev = PATCHES / "brazil_comexstat_exports__JUL26_REVISIONS.csv"
    patch_add = PATCHES / "brazil_comexstat_exports__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target)
    df_rev = pd.read_csv(patch_rev)
    # Apply July revisions
    for _, r in df_rev.iterrows():
        mask = (df_t["date"] == "2026-07-01") & (df_t["commodity"] == r["commodity"])
        if mask.any():
            df_t.loc[mask, "metric_tonnes"] = round(float(r["current_mdic_tonnes"]), 2)
            df_t.loc[mask, "fob_usd"] = float(r["current_mdic_fob"])
    df_add = pd.read_csv(patch_add)
    combined = pd.concat([df_t, df_add], ignore_index=True)
    combined.drop_duplicates(subset=["date", "commodity"], keep="last", inplace=True)
    combined.sort_values(by=["date", "commodity"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Applied revisions to Jul-2026 and added Aug-2026. Total: {len(combined)} rows.")


def apply_eia():
    print("5. Patching US EIA Weekly Crude Exports...")
    target = COMMODITIES / "us_eia_weekly_crude_exports.csv"
    patch_add = PATCHES / "us_eia_weekly_crude_exports__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target)
    df_add = pd.read_csv(patch_add)
    combined = pd.concat([df_t, df_add], ignore_index=True)
    combined.drop_duplicates(subset=["date"], keep="last", inplace=True)
    combined.sort_values(by=["date"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Appended {len(df_add)} weeks. Total: {len(combined)} rows.")


def apply_usda_inspections():
    print("6. Patching USDA Grain Inspections (58,937 FGIS certificate rows)...")
    target = COMMODITIES / "usda_ytd_grain_inspections_top20.csv"
    patch_add = PATCHES / "usda_ytd_grain_inspections_top20__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target, low_memory=False)
    df_add = pd.read_csv(patch_add, low_memory=False)
    combined = pd.concat([df_t, df_add], ignore_index=True)
    combined.drop_duplicates(keep="last", inplace=True)
    combined.sort_values(by=["date", "ams_reg", "grain"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Combined from {len(df_t)} to {len(combined)} rows.")


def apply_usda_sales():
    print("7. Patching USDA FAS Outstanding Export Sales...")
    target = COMMODITIES / "usda_fas_outstanding_export_sales.csv"
    patch_add = PATCHES / "usda_fas_outstanding_export_sales__ADD_ROWS.csv"
    shutil.copy2(target, target.with_suffix(".csv.bak"))
    df_t = pd.read_csv(target, low_memory=False)
    df_add = pd.read_csv(patch_add, low_memory=False)
    combined = pd.concat([df_t, df_add], ignore_index=True)
    combined.drop_duplicates(keep="last", inplace=True)
    combined.sort_values(by=["date", "commodity"], inplace=True)
    combined.to_csv(target, index=False)
    print(f"   -> Appended {len(df_add)} rows. Total: {len(combined)} rows.")


def main():
    print("=== Applying Gap-Fill Patches (AGENT_HANDOFF §0) ===")
    apply_ppa()
    apply_minor_bulks()
    apply_guinea()
    apply_brazil()
    apply_eia()
    apply_usda_inspections()
    apply_usda_sales()
    print("=== All Patches Successfully Applied! ===")


if __name__ == "__main__":
    main()
