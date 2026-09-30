"""
Export Seabrokers Extended Parquet Dataset into Standard Master Series CSVs.

Unpacks data/extracted/seabrokers_extended.parquet (16,125 rows) into standard
transparent CSV time series in data/extracted/series/:
  1. seabrokers_osv_spot_rates_series.csv
  2. seabrokers_osv_monthly_history_series.csv
  3. seabrokers_osv_utilisation_series.csv
  4. seabrokers_rigs_market_series.csv
  5. seabrokers_snp_auctions_series.csv
  6. seabrokers_fleet_moves_series.csv
  7. seabrokers_feature_vessels_series.csv
  8. seabrokers_renewables_and_ets_series.csv
"""

import os
import sys
import pandas as pd
from datetime import datetime

REPO_ROOT = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
PARQUET_PATH = os.path.join(REPO_ROOT, "data", "extracted", "seabrokers_extended.parquet")
SERIES_DIR = os.path.join(REPO_ROOT, "data", "extracted", "series")
os.makedirs(SERIES_DIR, exist_ok=True)


def export_series():
    print(f"Reading {PARQUET_PATH}...")
    df = pd.read_parquet(PARQUET_PATH)
    print(f"Loaded {len(df):,} rows from parquet.")

    df["report_date"] = pd.to_datetime(df["report_date"]).dt.strftime("%Y-%m-%d")
    df["year"] = pd.to_datetime(df["report_date"]).dt.year
    df["month"] = pd.to_datetime(df["report_date"]).dt.month

    # 1. OSV Spot Rates
    df_spot = df[df["section"] == "osv_spot_rates"].copy()
    csv_spot = os.path.join(SERIES_DIR, "seabrokers_osv_spot_rates_series.csv")
    df_spot = df_spot.sort_values(["report_date", "vessel_class", "metric"])
    df_spot.to_csv(csv_spot, index=False, columns=[
        "report_date", "year", "month", "vessel_class", "metric", "value", "unit", "source", "source_page"
    ])
    print(f"[+] Exported OSV Spot Rates: {csv_spot} ({len(df_spot):,} rows)")

    # 2. OSV Monthly History Curves (6,280 continuous monthly points)
    df_hist = df[df["section"] == "osv_spot_rate_history_monthly"].copy()
    csv_hist = os.path.join(SERIES_DIR, "seabrokers_osv_monthly_history_series.csv")
    df_hist = df_hist.sort_values(["report_date", "vessel_class", "period"])
    df_hist.to_csv(csv_hist, index=False, columns=[
        "report_date", "year", "month", "period", "vessel_class", "metric", "value", "unit", "source", "source_page"
    ])
    print(f"[+] Exported OSV Monthly Rate History: {csv_hist} ({len(df_hist):,} rows)")

    # 3. OSV Utilisation Curves (2,304 utilisation points)
    df_util = df[df["section"] == "osv_utilisation"].copy()
    csv_util = os.path.join(SERIES_DIR, "seabrokers_osv_utilisation_series.csv")
    df_util = df_util.sort_values(["report_date", "vessel_class", "period"])
    df_util.to_csv(csv_util, index=False, columns=[
        "report_date", "year", "month", "period", "vessel_class", "metric", "value", "unit", "source", "source_page"
    ])
    print(f"[+] Exported OSV Utilisation: {csv_util} ({len(df_util):,} rows)")

    # 4. Rigs Market (4,467 rows combining rig_day_rates, rig_utilisation, rigs_inactive)
    df_rigs = df[df["section"].isin(["rig_day_rates", "rig_utilisation", "rigs_inactive"])].copy()
    csv_rigs = os.path.join(SERIES_DIR, "seabrokers_rigs_market_series.csv")
    df_rigs = df_rigs.sort_values(["report_date", "section"])
    df_rigs.to_csv(csv_rigs, index=False, columns=[
        "report_date", "year", "month", "section", "region", "vessel_class", "metric", "value", "value_text", "unit", "period", "note", "source", "source_page"
    ])
    print(f"[+] Exported Rigs Market: {csv_rigs} ({len(df_rigs):,} rows)")

    # 5. Offshore S&P Auctions (Bourbon auctions, MPSV, CSV, PSV, AHTS sales)
    df_snp = df[df["section"] == "offshore_snp_auction"].copy()
    csv_snp = os.path.join(SERIES_DIR, "seabrokers_snp_auctions_series.csv")
    df_snp = df_snp.sort_values(["report_date", "vessel_class"])
    df_snp.to_csv(csv_snp, index=False, columns=[
        "report_date", "year", "month", "vessel_class", "metric", "value", "unit", "note", "source", "source_page"
    ])
    print(f"[+] Exported Offshore S&P Auctions: {csv_snp} ({len(df_snp):,} rows)")

    # 6. OSV Fleet Moves (Arrivals & Departures ex-Med, ex-South America, etc.)
    df_moves = df[df["section"] == "osv_fleet_moves"].copy()
    csv_moves = os.path.join(SERIES_DIR, "seabrokers_fleet_moves_series.csv")
    df_moves = df_moves.sort_values(["report_date", "vessel_class"])
    df_moves.to_csv(csv_moves, index=False, columns=[
        "report_date", "year", "month", "vessel_class", "metric", "value_text", "note", "source", "source_page"
    ])
    print(f"[+] Exported OSV Fleet Moves: {csv_moves} ({len(df_moves):,} rows)")

    # 7. Feature Vessels
    df_fv = df[df["section"] == "feature_vessel"].copy()
    csv_fv = os.path.join(SERIES_DIR, "seabrokers_feature_vessels_series.csv")
    df_fv = df_fv.sort_values(["report_date", "vessel_class"])
    df_fv.to_csv(csv_fv, index=False, columns=[
        "report_date", "year", "month", "vessel_class", "metric", "value", "value_text", "unit", "note", "source", "source_page"
    ])
    print(f"[+] Exported Feature Vessels: {csv_fv} ({len(df_fv):,} rows)")

    # 8. Renewables & ETS Carbon
    df_ren = df[df["section"].isin(["offshore_renewables_auction", "carbon_ets"])].copy()
    csv_ren = os.path.join(SERIES_DIR, "seabrokers_renewables_and_ets_series.csv")
    df_ren = df_ren.sort_values(["report_date", "section"])
    df_ren.to_csv(csv_ren, index=False, columns=[
        "report_date", "year", "month", "section", "metric", "value", "unit", "period", "note", "source", "source_page"
    ])
    print(f"[+] Exported Renewables & ETS: {csv_ren} ({len(df_ren):,} rows)")

    total_exported = len(df_spot) + len(df_hist) + len(df_util) + len(df_rigs) + len(df_snp) + len(df_moves) + len(df_fv) + len(df_ren)
    print(f"\n[+] Total rows exported across 8 series: {total_exported:,} (100% of parquet dataset)")


if __name__ == "__main__":
    export_series()
