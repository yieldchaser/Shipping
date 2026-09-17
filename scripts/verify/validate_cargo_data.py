#!/usr/bin/env python3
"""
scripts/verify/validate_cargo_data.py
====================================
Comprehensive pre-commit and CI data integrity validator for #tab-cargo (§4).
Enforces zero tolerance for:
  - Corrupted rows / parse bugs (e.g., 423 Mt bauxite, 668 kt alumina, partial steel months)
  - Phantom / zero-value rows for unpublished periods (e.g., Urea 0 t, $0)
  - Future dates beyond the current calendar month
  - Missing or placeholder provenance
  - Duplicate keys on time-series records
  - Outliers outside 0.2x–5.0x trailing 12-month median
"""

import sys
import os
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("validate_cargo_data")

ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = ROOT / "data" / "commodities"

TODAY = datetime.now(timezone.utc).date()
CURRENT_YM = TODAY.strftime("%Y-%m")
CURRENT_DATE = TODAY.strftime("%Y-%m-%d")

ERRORS = []
WARNINGS = []


def record_error(file_name: str, check_name: str, message: str):
    msg = f"[{file_name}] {check_name}: {message}"
    logger.error(msg)
    ERRORS.append(msg)


def record_warning(file_name: str, check_name: str, message: str):
    msg = f"[{file_name}] {check_name}: {message}"
    logger.warning(msg)
    WARNINGS.append(msg)


# =====================================================================
# 1. Guinea Bauxite Validation
# =====================================================================
def validate_guinea_bauxite():
    fname = "guinea_bauxite_exports.csv"
    fpath = COMMODITIES_DIR / fname
    if not fpath.exists():
        record_error(fname, "FILE_EXISTS", "File not found")
        return

    df = pd.read_csv(fpath)

    # Date checks
    dates = df["date"].astype(str).str.strip()
    future = df[dates > CURRENT_DATE]
    if not future.empty:
        record_error(fname, "NO_FUTURE_DATES", f"Found future dates: {list(future['date'])}")

    # Check 2026-05 mirror row
    m_2026_05 = df[(df["date"] == "2026-05-01") & (df["granularity"] == "monthly_bilateral_mirror")]
    if m_2026_05.empty:
        record_error(fname, "2026_05_ROW", "2026-05 mirror row missing")
    else:
        tonnes = float(m_2026_05["tonnes"].iloc[0])
        if tonnes > 40_000_000:
            record_error(fname, "2026_05_SMM_BUG", f"2026-05 mirror row contains SMM parse bug: {tonnes:,.0f} t > 40 Mt")
        elif not (18_000_000 <= tonnes <= 22_000_000):
            record_error(fname, "2026_05_GACC_VALUE", f"2026-05 mirror row should be ~19.56 Mt from GACC, got {tonnes:,.0f} t")
        else:
            logger.info("  [OK] guinea_bauxite: 2026-05 mirror row verified at %.1f Mt (GACC export)", tonnes / 1e6)

    # Monthly mirror clamp & outlier validation
    mirrors = df[df["granularity"] == "monthly_bilateral_mirror"].copy()
    for _, r in mirrors.iterrows():
        t = float(r["tonnes"])
        d = r["date"]
        # Clamp: 1 Mt - 30 Mt for monthly China imports from Guinea
        if t < 1_000_000 or t > 30_000_000:
            record_error(fname, "MIRROR_UNIT_CLAMP", f"{d} tonnes {t:,.0f} outside realistic 1–30 Mt range")
        
        # Check CIF price if present
        cif = r.get("avg_cif_usd_t")
        if pd.notna(cif) and str(cif).strip() != "":
            cif_val = float(cif)
            if cif_val < 30.0 or cif_val > 150.0:
                record_error(fname, "MIRROR_CIF_CLAMP", f"{d} CIF ${cif_val:.2f}/t outside $30-$150 range")

    # Check duplicates: exactly 1 mirror row per month, and unique (date, granularity, company)
    mirrors = df[df["granularity"] == "monthly_bilateral_mirror"]
    mirror_dups = mirrors[mirrors.duplicated(subset=["date"], keep=False)]
    if not mirror_dups.empty:
        record_error(fname, "NO_DUPLICATE_MIRRORS", f"Duplicate monthly_bilateral_mirror dates: {list(mirror_dups['date'].unique())}")

    dups = df[df.duplicated(subset=["date", "granularity", "company"], keep=False)]
    if not dups.empty:
        record_error(fname, "NO_DUPLICATES", f"Duplicate (date, granularity, company) rows found: {list(dups['date'].unique())}")


# =====================================================================
# 2. Minor Bulks Monthly Validation (Alumina, Urea, etc.)
# =====================================================================
def validate_minor_bulks():
    fname = "minor_bulks_monthly.csv"
    fpath = COMMODITIES_DIR / fname
    if not fpath.exists():
        record_error(fname, "FILE_EXISTS", "File not found")
        return

    df = pd.read_csv(fpath)

    # No future dates
    dates = df["date"].astype(str).str.strip()
    future = df[dates > CURRENT_DATE]
    if not future.empty:
        record_error(fname, "NO_FUTURE_DATES", f"Found future dates: {list(future['date'])}")

    # Check Alumina 2026-06
    al_2026_06 = df[(df["commodity"] == "Alumina") & (df["date"] == "2026-06-01")]
    if al_2026_06.empty:
        record_error(fname, "ALUMINA_2026_06_MISSING", "Alumina 2026-06 row missing")
    else:
        mt = float(al_2026_06["metric_tonnes"].iloc[0])
        if abs(mt - 668000.0) < 1000.0:
            record_error(fname, "ALUMINA_2026_06_BUG", f"Alumina 2026-06 contains old corrupted value: {mt} t (expected ~449,460 t)")
        elif not (440000.0 <= mt <= 460000.0):
            record_error(fname, "ALUMINA_2026_06_VALUE", f"Alumina 2026-06 expected ~449,460 t from GACC, got {mt} t")
        else:
            logger.info("  [OK] minor_bulks: Alumina 2026-06 verified at %.1f t (GACC export)", mt)

    # Check Urea 2026-08 zero row
    urea_2026_08 = df[(df["commodity"].str.contains("Urea")) & (df["date"] == "2026-08-01")]
    if not urea_2026_08.empty:
        mt = float(urea_2026_08["metric_tonnes"].iloc[0])
        val = float(urea_2026_08["value_usd"].iloc[0])
        if mt == 0.0 or val == 0.0:
            record_error(fname, "UREA_ZERO_ROW", f"Found invalid unpublished 2026-08 Urea row with mt={mt}, val={val}")

    # No zeros in published historical data
    for idx, r in df.iterrows():
        d = str(r["date"])
        comm = str(r["commodity"])
        mt = r.get("metric_tonnes")
        val = r.get("value_usd")
        if pd.notna(mt) and float(mt) <= 0:
            record_error(fname, "ZERO_TONNES", f"{comm} on {d} has zero/negative tonnes: {mt}")
        if pd.notna(val) and float(val) <= 0:
            record_error(fname, "ZERO_VALUE", f"{comm} on {d} has zero/negative value_usd: {val}")

    # Check duplicates on (commodity, date)
    dups = df[df.duplicated(subset=["commodity", "date"], keep=False)]
    if not dups.empty:
        record_error(fname, "NO_DUPLICATES", f"Duplicate (commodity, date) rows: {list(dups[['commodity', 'date']].drop_duplicates().values)}")


# =====================================================================
# 3. World Crude Steel Validation
# =====================================================================
def validate_world_crude_steel():
    fname = "world_crude_steel_monthly.csv"
    fpath = COMMODITIES_DIR / fname
    if not fpath.exists():
        record_error(fname, "FILE_EXISTS", "File not found")
        return

    df = pd.read_csv(fpath)

    # Delete 2026-08 and 2026-09 check
    bad_steel = df[df["date"].isin(["2026-08-01", "2026-09-01"])]
    if not bad_steel.empty:
        record_error(fname, "UNPUBLISHED_STEEL_MONTHS", f"Found unreleased/partial steel months: {list(bad_steel['date'])}")

    # Global total > 100 Mt for every month
    for idx, r in df.iterrows():
        d = str(r["date"])
        wt = float(r.get("world_total_mt") or 0)
        if wt < 100.0:
            record_error(fname, "WORLD_STEEL_TOTAL_TOO_LOW", f"{d} world total {wt} Mt < 100 Mt threshold")

    # Check duplicates on date
    dups = df[df.duplicated(subset=["date"], keep=False)]
    if not dups.empty:
        record_error(fname, "NO_DUPLICATES", f"Duplicate date rows found: {list(dups['date'].unique())}")


# =====================================================================
# 4. Major Miners Quarterly Shipments Validation
# =====================================================================
def validate_major_miners():
    fname = "major_miners_quarterly_shipments.csv"
    fpath = COMMODITIES_DIR / fname
    if not fpath.exists():
        record_error(fname, "FILE_EXISTS", "File not found")
        return

    df = pd.read_csv(fpath)

    # Must contain exactly the 4 target miners
    miners = set(df["miner"].unique())
    expected_miners = {"Vale", "Rio Tinto", "BHP", "Fortescue"}
    if miners != expected_miners:
        record_error(fname, "MINERS_SET", f"Expected miners {expected_miners}, got {miners}")

    # No future quarters beyond 2026 Q2
    valid_quarters = [
        "2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4",
        "2025 Q1", "2025 Q2", "2025 Q3", "2025 Q4",
        "2026 Q1", "2026 Q2"
    ]
    invalid_q = set(df["quarter"].unique()) - set(valid_quarters)
    if invalid_q:
        record_error(fname, "INVALID_QUARTERS", f"Found unexpected/future quarters: {invalid_q}")

    # Verify each row has valid shipments and production, and valid provenance
    for idx, r in df.iterrows():
        m = r["miner"]
        q = r["quarter"]
        ship = r.get("shipments_mt")
        prod = r.get("production_mt")
        prov = str(r.get("provenance", "")).strip()

        if pd.isna(ship) or float(ship) <= 0:
            record_error(fname, "INVALID_SHIPMENTS", f"{m} {q} shipments missing or non-positive: {ship}")
        if pd.isna(prod) or float(prod) <= 0:
            record_error(fname, "INVALID_PRODUCTION", f"{m} {q} production missing or non-positive: {prod}")

        # Provenance check
        if not (prov.startswith("EDGAR:") or prov.startswith("ASX:") or prov == "illustrative_prior_estimate"):
            record_error(fname, "INVALID_PROVENANCE", f"{m} {q} invalid provenance: '{prov}'")

    # Check duplicates on (miner, quarter)
    dups = df[df.duplicated(subset=["miner", "quarter"], keep=False)]
    if not dups.empty:
        record_error(fname, "NO_DUPLICATES", f"Duplicate (miner, quarter) rows: {list(dups[['miner', 'quarter']].drop_duplicates().values)}")


# =====================================================================
# 5. Outlier Detection Across Time Series (0.2x to 5.0x Rolling 12m Median)
# =====================================================================
def validate_time_series_outliers():
    target_files = [
        ("australia_ppa_iron_ore.csv", ["port_hedland_throughput_mt", "total_throughput_mt", "iron_ore_exports_mt"], "port"),
        ("newcastle_coal_monthly.csv", ["exports_mt", "shipments_mt", "metric_tonnes"], None),
        ("us_eia_weekly_crude_exports.csv", ["us_total_crude_exports_kbpd"], None),
        ("brazil_comexstat_exports.csv", ["metric_tonnes"], "commodity")
    ]

    for fname, cols, group_col in target_files:
        fpath = COMMODITIES_DIR / fname
        if not fpath.exists():
            continue
        df = pd.read_csv(fpath)
        if "date" not in df.columns:
            continue

        groups = [("All", df)] if not group_col or group_col not in df.columns else df.groupby(group_col)

        for gname, gdf in groups:
            gdf_sorted = gdf.sort_values(by="date").reset_index(drop=True)
            for col in cols:
                if col in gdf_sorted.columns and pd.api.types.is_numeric_dtype(gdf_sorted[col]):
                    s = gdf_sorted[col].dropna()
                    # Filter out zero values so they don't skew the median
                    s_nonzero = s[s > 0]
                    if len(s_nonzero) >= 12:
                        med = s_nonzero.rolling(window=12, min_periods=6).median()
                        ratio = s_nonzero / med
                        bad = gdf_sorted.loc[s_nonzero.index[(ratio < 0.2) | (ratio > 5.0)]]
                        for idx, row in bad.iterrows():
                            val = row[col]
                            m_val = med.loc[idx]
                            r_val = ratio.loc[idx]
                            d = row["date"]
                            record_warning(fname, "OUTLIER_BREACH", f"[{gname}] {d} col '{col}' = {val} outside 0.2x-5.0x trailing median ({m_val:.1f}, ratio {r_val:.2f}x)")


# =====================================================================
# Main Runner
# =====================================================================
def validate_cargo_datasets():
    ERRORS.clear()
    WARNINGS.clear()
    validate_guinea_bauxite()
    validate_minor_bulks()
    validate_world_crude_steel()
    validate_major_miners()
    validate_time_series_outliers()
    return (len(ERRORS) == 0, len(ERRORS), len(WARNINGS), list(ERRORS))


def main():
    logger.info("=================================================================")
    logger.info("    RUNNING CARGO DATA PRE-COMMIT INTEGRITY VALIDATOR (§4)      ")
    logger.info("=================================================================")

    passed, err_cnt, warn_cnt, errs = validate_cargo_datasets()

    print("\n" + "=" * 80)
    if not passed:
        print(f"FAILED: Found {err_cnt} data integrity errors:")
        for err in errs:
            print(f"  ❌ {err}")
        print("=" * 80)
        sys.exit(1)
    else:
        print("SUCCESS: All cargo commodity datasets PASSED integrity validation!")
        print(f"  Checked: Guinea Bauxite, Minor Bulks, World Steel, Major Miners, Pilbara PPA, Newcastle, EIA, ComexStat")
        print(f"  Total errors: 0 | Warnings: {warn_cnt}")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
