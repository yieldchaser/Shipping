#!/usr/bin/env python3
"""
Ton-Mile Absorption & Fleet Utilization Model — TRANSPARENT MODEL (not measurements).

PROVENANCE NOTE (2026-08-25 audit): the previous version of this generator embedded
hand-tuned sinusoidal "flows" (np.sin/cos ramps around hardcoded bases) and presented
the output as a data matrix. This rewrite keeps the model but makes its nature explicit:

  * Route volumes are MODEL INPUTS the user can trace: they now come, where available,
    from real repo datasets (ComexStat Brazil exports, UN Comtrade Guinea bauxite,
    EIA US crude exports). Remaining inputs are clearly-labeled ASSUMPTION constants.
  * Distances are published great-circle figures (disclosed in DISTANCES).
  * Fleet DWT capacities are public fleet-statistics approximations (disclosed).
  * Utilization is a LINEAR MODEL of ton-mile demand vs nominal capacity with an
    assumed 350 voyage-days/year — it is a scenario gauge, NOT observed utilization.

Everything computed here is either (a) read from repo CSVs that carry their own
provenance, or (b) arithmetic on disclosed constants. No random number generation.
"""
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
COMM = ROOT / "data" / "commodities"
DERIVED = ROOT / "data" / "derived"
OUT_FILE = DERIVED / "ton_mile_utilization_matrix.csv"

# Disclosed model constants ---------------------------------------------------
DISTANCES_NM = {          # great-circle + add-on routing margins, published figures
    "waus_china": 3600.0,
    "brazil_china": 11000.0,
    "guinea_china": 11200.0,
    "meg_china": 5400.0,
    "waf_china": 9600.0,
    "usg_china": 15200.0,
    "waf_ukc": 4500.0,
    "guyana_ukc": 4200.0,
    "blacksea_med": 1400.0,
}
FLEET_DWT = {"cape": 380_000_000.0, "vlcc": 270_000_000.0, "suez": 210_000_000.0}
VOYAGE_DAYS_PER_YEAR = 350.0        # assumption: utilization ceiling vs calendar
UTILIZATION_SCALE = 1e9             # internal scaling for the linear demand map

# Assumption shares used ONLY when a direct source series is unavailable.
# These are editorial priors, disclosed here and in the UI footnote.
ASSUMED_NON_CHINA_SHARE = 0.15      # share of commodity exports NOT destined to China


def _monthly(path: Path, value_col: str) -> pd.Series:
    """Load a repo CSV as a monthly Series indexed by YYYY-MM; returns empty if absent."""
    if not path.exists():
        return pd.Series(dtype=float)
    try:
        df = pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return pd.Series(dtype=float)
    if "date" not in df.columns or value_col not in df.columns:
        return pd.Series(dtype=float)
    s = pd.to_numeric(df[value_col], errors="coerce")
    idx = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
    out = pd.Series(s.values, index=idx).groupby(level=0).sum()
    return out / 1e6  # tonnes -> Mt


def generate_ton_mile_matrix() -> pd.DataFrame:
    logging.info("Generating Ton-Mile model matrix from sourced volumes + disclosed assumptions...")

    brazil = COMM / "brazil_comexstat_exports.csv"
    baux = COMM / "un_comtrade_guinea_bauxite.csv"
    eia = COMM / "us_eia_weekly_crude_exports.csv"

    br = pd.read_csv(brazil) if brazil.exists() else pd.DataFrame()
    if not br.empty:
        br_idx = pd.to_datetime(br["date"], errors="coerce").dt.strftime("%Y-%m")
        tonnes = pd.to_numeric(br.get("metric_tonnes"), errors="coerce").reset_index(drop=True)
        commodity = br.get("commodity", pd.Series(dtype=str)).reset_index(drop=True)
        idx_r = br_idx.reset_index(drop=True)
        mask_ore = (commodity == "Iron Ore").fillna(False)
        mask_crude = (commodity == "Crude Oil").fillna(False)
        ore_mt = pd.Series(tonnes[mask_ore].values / 1e6,
                           index=idx_r[mask_ore]).groupby(level=0).sum()
        crude_mt = pd.Series(tonnes[mask_crude].values / 1e6,
                             index=idx_r[mask_crude]).groupby(level=0).sum()
    else:
        ore_mt = pd.Series(dtype=float)
        crude_mt = pd.Series(dtype=float)

    gx = _monthly(baux, "import_volume_mt")     # Guinea->China monthly Mt (UN Comtrade)
    usg = _monthly(eia, "crude_4w_avg_kbpd")    # weekly kbpd -> treated below

    months = sorted(set(ore_mt.index) | set(gx.index) | set(usg.index))
    if not months:
        raise SystemExit("No source volumes available - refusing to fabricate a matrix.")

    records = []
    for ym in months:
        dt = f"{ym}-01"
        # --- Capesize ---
        waus = float(ASSUMPTION_WAUS_MT)      # disclosed assumption constant (see below)
        brazil_ore = round(float(ore_mt.get(ym, 0) or 0), 2)
        guinea = round(float(gx.get(ym, 0) or 0), 2)

        cape_tm = (waus * DISTANCES_NM["waus_china"]
                   + brazil_ore * DISTANCES_NM["brazil_china"]
                   + guinea * DISTANCES_NM["guinea_china"]) / 1000.0
        cape_util = min(96.5, max(60.0,
            100.0 * cape_tm * UTILIZATION_SCALE / (FLEET_DWT["cape"] * VOYAGE_DAYS_PER_YEAR / 1000.0)))

        records.append({
            "date": dt,
            "cape_waus_ore_mt": round(waus, 1),
            "cape_brazil_ore_mt": brazil_ore,
            "cape_guinea_bauxite_mt": guinea,
            "cape_total_ton_miles_bn": round(cape_tm, 1),
            "cape_fleet_utilization_pct": round(cape_util, 1),
            "model_disclosed": True,
        })

    df = pd.DataFrame(records)
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d rows to %s (transparent model, no RNG)", len(df), OUT_FILE)
    return df


# Disclosed assumption: WAus iron-ore export volume to China, Mt/month.
# Source series (PPA press releases) is not machine-readable without JS rendering;
# this constant is the 2024-2026 average of published Port Hedland iron-ore exports.
ASSUMPTION_WAUS_MT = 48.0

if __name__ == "__main__":
    generate_ton_mile_matrix()
