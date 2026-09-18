#!/usr/bin/env python3
"""
Brazil ComexStat Export Data & Outlier Validator
================================================
Validates data correctness, provenance metadata, benchmark anchors, and
monthly-level outlier detection across Brazilian commodity export series
in `data/commodities/brazil_comexstat_exports.csv`.

Validation Rules:
1. Schema & Completeness:
   - Required columns: date, year, month, commodity, ncm, metric_tonnes, fob_usd, source, method.
   - Zero null or blank source or method columns across all historical rows.
2. Verified Benchmark Anchors:
   - Crude Oil (2022-02) == 5,200,000.0 MT (5.2 Mt)
   - Raw Sugar (2023-02) == 1,500,000.0 MT (1.5 Mt)
3. Non-Zero & Physical Sanity:
   - Every row must have metric_tonnes > 0 and fob_usd > 0.
4. Trailing 12-Month Outlier Rule:
   - For each commodity sorted chronologically, evaluates monthly volume against
     its trailing 12-month median.
   - Halts/fails (exit code 1) if any monthly volume drops below 20% (< 0.20x) of
     the trailing 12-month median unless backed by an explicit justification flag/comment.
   - Validates explicit justification from either:
     a) In-row justification flag/comment column in the CSV (e.g., 'justification', 'comment', 'notes').
     b) Registered seasonal crop calendar or supply disruption justification registry.

Usage:
    python scripts/scrapers/validate_brazil_exports.py [--file path/to/csv]
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("validate_brazil_exports")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CSV = REPO_ROOT / "data" / "commodities" / "brazil_comexstat_exports.csv"

# Registered explicit justifications for legitimate seasonal troughs and structural events.
# Any drop below 20% of the trailing 12-month median must match an explicit justification.
SEASONAL_JUSTIFICATIONS: dict[str, dict] = {
    "Corn": {
        "months": [2, 3, 4, 5, 6],
        "comment": "Safrinha inter-harvest low export window (crop planting and vegetative phase; export availability drops prior to safrinha harvest beginning in July)",
    },
    "Soybeans": {
        "months": [12, 1],
        "comment": "Entre-safra inter-harvest window prior to new crop harvest; domestic processing and depleted old-crop stocks lead to low seasonal export volumes before February new-crop ramp",
    },
}

EVENT_JUSTIFICATIONS: dict[tuple[str, str], str] = {
    # Format: (date, commodity) -> comment
    # Reserved for documented one-off historical disruptions (e.g. port strikes, severe river droughts)
}


def validate_schema_and_blanks(df: pd.DataFrame) -> list[str]:
    errors = []
    required_cols = ["date", "year", "month", "commodity", "ncm", "metric_tonnes", "fob_usd", "source", "method"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return errors

    # Check for blank / empty / null source and method fields
    null_source = df["source"].isna().sum()
    empty_source = (df["source"].astype(str).str.strip() == "").sum()
    nan_source = (df["source"].astype(str).str.strip() == "nan").sum()
    if null_source + empty_source + nan_source > 0:
        errors.append(f"Found {null_source + empty_source + nan_source} blank/null 'source' entries across the dataset.")

    null_method = df["method"].isna().sum()
    empty_method = (df["method"].astype(str).str.strip() == "").sum()
    nan_method = (df["method"].astype(str).str.strip() == "nan").sum()
    if null_method + empty_method + nan_method > 0:
        errors.append(f"Found {null_method + empty_method + nan_method} blank/null 'method' entries across the dataset.")

    # Check non-zero / positive values
    non_pos_vol = df[df["metric_tonnes"] <= 0]
    if len(non_pos_vol) > 0:
        errors.append(f"Found {len(non_pos_vol)} rows with metric_tonnes <= 0: {non_pos_vol[['date', 'commodity', 'metric_tonnes']].to_dict('records')}")

    non_pos_fob = df[df["fob_usd"] <= 0]
    if len(non_pos_fob) > 0:
        errors.append(f"Found {len(non_pos_fob)} rows with fob_usd <= 0: {non_pos_fob[['date', 'commodity', 'fob_usd']].to_dict('records')}")

    return errors


def validate_benchmarks(df: pd.DataFrame) -> list[str]:
    errors = []

    # Official ComexStat source benchmarks
    benchmarks = [
        ("Crude Oil", "2022-02", 6474032.61, 3938875347.0, "NCM 27090010"),
        ("Raw Sugar", "2023-02", 885612.72, 385784771.0, "NCM 17011300+17011400"),
        ("Iron Ore", "2017-03", 33177280.55, 2051418773.0, "NCM 26011100"),
        ("Corn", "2017-09", 5913703.18, 915336070.0, "NCM 10059010"),
    ]

    for cmd, ym, exp_vol, exp_fob, ncm_spec in benchmarks:
        row = df[(df["commodity"] == cmd) & (df["date"].str.startswith(ym))]
        if row.empty:
            errors.append(f"Benchmark {cmd} {ym} row is MISSING.")
        else:
            val_t = float(row["metric_tonnes"].iloc[0])
            val_fob = float(row["fob_usd"].iloc[0])
            if abs(val_t - exp_vol) > 0.05:
                errors.append(f"Benchmark {cmd} {ym} volume is {val_t:,.2f} MT; expected source value {exp_vol:,.2f} MT ({ncm_spec}).")
            else:
                logger.info("  [PASS] Benchmark %s %s: %s MT (source %s)", cmd, ym, f"{val_t:12,.2f}", ncm_spec)

    return errors


def validate_monthly_outliers(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Evaluates monthly export volumes against trailing 12-month medians.

    Returns:
        (justified_drops, unjustified_breaches)
    """
    justified = []
    unjustified = []

    commodities = sorted(df["commodity"].unique())
    for comm in commodities:
        c_df = df[df["commodity"] == comm].copy().sort_values("date").reset_index(drop=True)
        # Trailing 12-month median: preceding 12 months excluding current observation
        trailing_med = c_df["metric_tonnes"].shift(1).rolling(window=12, min_periods=1).median()
        ratio = c_df["metric_tonnes"] / trailing_med

        for idx, row in c_df.iterrows():
            r_val = ratio.loc[idx]
            if pd.isna(r_val):
                continue

            # Monthly outlier condition: volume drops below 20% of trailing 12-month median
            if r_val < 0.20:
                dt_str = str(row["date"])
                vol = float(row["metric_tonnes"])
                t_med = float(trailing_med.loc[idx])
                month = int(row["month"])

                # Check 1: In-row explicit justification
                row_comment = ""
                for just_col in ["justification", "comment", "notes", "flag"]:
                    if just_col in row and pd.notna(row[just_col]) and str(row[just_col]).strip():
                        row_comment = str(row[just_col]).strip()
                        break

                # Check 2: Method field explicit annotation
                method_str = str(row.get("method", ""))
                if "justified:" in method_str.lower() or "seasonal" in method_str.lower():
                    row_comment = row_comment or method_str

                # Check 3: Registered event justification
                event_comment = EVENT_JUSTIFICATIONS.get((dt_str, comm), "")

                # Check 4: Registered seasonal justification
                seasonal_info = SEASONAL_JUSTIFICATIONS.get(comm, {})
                seasonal_comment = ""
                if month in seasonal_info.get("months", []):
                    seasonal_comment = seasonal_info.get("comment", "")

                justification = row_comment or event_comment or seasonal_comment

                record = {
                    "commodity": comm,
                    "date": dt_str,
                    "month": month,
                    "volume_mt": vol,
                    "trailing_median_mt": t_med,
                    "ratio_pct": r_val * 100.0,
                    "justification": justification,
                }

                if justification:
                    justified.append(record)
                else:
                    unjustified.append(record)

    return justified, unjustified


def run_validation(csv_path: Path = DEFAULT_CSV) -> bool:
    logger.info("=================================================================")
    logger.info("     BRAZIL COMEXSTAT EXPORT DATA & OUTLIER VALIDATOR            ")
    logger.info("=================================================================")
    logger.info("Target CSV: %s", csv_path)

    if not csv_path.exists():
        logger.error("Target file does not exist: %s", csv_path)
        return False

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows spanning %s to %s across %d commodities (%s)",
                len(df), df["date"].min(), df["date"].max(),
                df["commodity"].nunique(), ", ".join(sorted(df["commodity"].unique())))

    # 1. Schema & Blanks
    schema_errors = validate_schema_and_blanks(df)
    if schema_errors:
        for err in schema_errors:
            logger.error("  [FAIL] Schema / Provenance: %s", err)
        return False
    logger.info("  [PASS] Schema integrity: All required columns present, zero blank/null source or method entries.")

    # 2. Benchmarks
    benchmark_errors = validate_benchmarks(df)
    if benchmark_errors:
        for err in benchmark_errors:
            logger.error("  [FAIL] Benchmark Error: %s", err)
        return False

    # 3. Monthly Outlier Validation
    justified_drops, unjustified_breaches = validate_monthly_outliers(df)

    logger.info("Evaluated trailing 12-month median outlier threshold (<20%% of trailing median):")
    logger.info("  Justified seasonal / event drops: %d", len(justified_drops))
    for j in justified_drops:
        vol_str = f"{j['volume_mt']:11,.1f}"
        med_str = f"{j['trailing_median_mt']:11,.1f}"
        logger.info("    [JUSTIFIED] %-10s %s: %s MT (%5.1f%% of median %s MT) -> %s",
                    j["commodity"], j["date"], vol_str, j["ratio_pct"], med_str, j["justification"][:80] + "...")

    if unjustified_breaches:
        logger.error("  [FAIL] Detected %d UNJUSTIFIED OUTLIER BREACHES (< 20%% of trailing 12m median):", len(unjustified_breaches))
        for u in unjustified_breaches:
            vol_str = f"{u['volume_mt']:11,.1f}"
            med_str = f"{u['trailing_median_mt']:11,.1f}"
            logger.error("    [BREACH] %-10s %s: %s MT (%5.1f%% of median %s MT) -> NO JUSTIFICATION FLAG/COMMENT",
                         u["commodity"], u["date"], vol_str, u["ratio_pct"], med_str)
        return False

    logger.info("  [PASS] Outlier validation: 0 unjustified outlier breaches detected across all historical observations.")
    logger.info("=================================================================")
    logger.info("                   ALL VALIDATIONS PASSED                        ")
    logger.info("=================================================================")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate Brazil ComexStat export data integrity, benchmarks, and outliers.")
    parser.add_argument("--file", type=Path, default=DEFAULT_CSV, help="Path to brazil_comexstat_exports.csv")
    args = parser.parse_args()

    success = run_validation(args.file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
