import csv
import json
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIBRA_DIR = REPO_ROOT / "docs" / "alibra_data"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

def generate_tce_matrix_json():
    dry_files = sorted(list((ALIBRA_DIR / "dry_bulk_tce_table").glob("*.csv")))
    tanker_files = sorted(list((ALIBRA_DIR / "tanker_tce_table").glob("*.csv")))
    stamp_files = sorted(list((ALIBRA_DIR / "last_updated_stamp").glob("*.csv")))
    dry_atl_trend = sorted(list((ALIBRA_DIR / "dry_bulk_trend_atl").glob("*.csv")))
    dry_pac_trend = sorted(list((ALIBRA_DIR / "dry_bulk_trend_pac").glob("*.csv")))
    tank_1y_trend = sorted(list((ALIBRA_DIR / "tanker_trend_1yr").glob("*.csv")))
    tank_3y_trend = sorted(list((ALIBRA_DIR / "tanker_trend_3yr").glob("*.csv")))

    # Load 10Y TC historical data for percentiles
    tc_file = DERIVED_DIR / "time_charter_rates.csv"
    df_10y = None
    if tc_file.exists():
        df_tc = pd.read_csv(tc_file)
        if 'date' in df_tc.columns:
            df_tc['date'] = pd.to_datetime(df_tc['date'])
            df_10y = df_tc[df_tc['date'] >= '2016-01-01']

    report_date = "2026-08-12"
    if stamp_files:
        with open(stamp_files[-1], encoding="utf-8") as f:
            txt = f.read().strip()
            if txt:
                report_date = txt.splitlines()[0].strip()

    # Load Trends
    df_d_atl = pd.read_csv(dry_atl_trend[-1]) if dry_atl_trend else None
    df_d_pac = pd.read_csv(dry_pac_trend[-1]) if dry_pac_trend else None
    df_t_1y = pd.read_csv(tank_1y_trend[-1]) if tank_1y_trend else None
    df_t_3y = pd.read_csv(tank_3y_trend[-1]) if tank_3y_trend else None

    eco_spreads = {
        'VLCC': 4350,
        'LR1': 5270,
        'MR IMO3': 3820,
        'MR': 3820,
        'LR2': 6200,
        'Aframax': 5100,
        'Suezmax': 5400,
        'Handymax': 2900
    }

    matrix = {
        "report_date": report_date,
        "dry_bulk": [],
        "tankers": []
    }

    dry_map = {
        'Handysize (38dwt)': {'col_atl': 'HANDYSIZE (38dwt)', 'col_pac': 'HANDYSIZE', 'tc_col': 'handysize_1y_avg'},
        'Supramax / Ultramax': {'col_atl': 'SMAX/ULTRA', 'col_pac': 'SMAX/ULTRA', 'tc_col': 'supramax_1y_avg'},
        'Panamax / Kamsarmax': {'col_atl': 'PANAMAX', 'col_pac': 'PANAMAX', 'tc_col': 'panamax_1y_avg'},
        'Capesize': {'col_atl': 'CAPESIZE', 'col_pac': 'CAPESIZE', 'tc_col': 'capesize_1y_avg'}
    }

    if dry_files:
        with open(dry_files[-1], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not r or not r.get("Size"):
                    continue
                sz = r.get("Size", "").strip()
                r_6m_atl = float(r.get("6MonthsATL", 0) or 0)
                chg_6m_atl = float(r.get("6MchangeATL", 0) or 0)
                r_1y_atl = float(r.get("1YearATL", 0) or 0)
                chg_1y_atl = float(r.get("1YRchangeATL", 0) or 0)
                r_2y_atl = float(r.get("2YearATL", 0) or 0)
                chg_2y_atl = float(r.get("2YRchangeATL", 0) or 0)

                r_6m_pac = float(r.get("6MonthsPAC", 0) or 0)
                chg_6m_pac = float(r.get("6MchangePAC", 0) or 0)
                r_1y_pac = float(r.get("1YearPAC", 0) or 0)
                chg_1y_pac = float(r.get("1YRchangePAC", 0) or 0)
                r_2y_pac = float(r.get("2YearPAC", 0) or 0)
                chg_2y_pac = float(r.get("2YRchangePAC", 0) or 0)

                spread_6m = r_6m_atl - r_6m_pac
                spread_1y = r_1y_atl - r_1y_pac
                spread_2y = r_2y_atl - r_2y_pac

                sparkline = []
                mom_1m = 0.0
                mom_1y = 0.0
                high_52w = max(r_1y_atl, r_1y_pac)
                low_52w = min(r_1y_atl, r_1y_pac)

                meta_entry = dry_map.get(sz, {})
                col_a = meta_entry.get('col_atl')
                if df_d_atl is not None and col_a in df_d_atl.columns:
                    s_vals = df_d_atl[col_a].dropna().tolist()
                    sparkline = [float(v) for v in s_vals[-52:]]
                    if len(sparkline) >= 5 and sparkline[-5] > 0:
                        mom_1m = round(((sparkline[-1] - sparkline[-5]) / sparkline[-5]) * 100.0, 1)
                    if len(sparkline) >= 20 and sparkline[0] > 0:
                        mom_1y = round(((sparkline[-1] - sparkline[0]) / sparkline[0]) * 100.0, 1)
                    if sparkline:
                        high_52w = max(sparkline)
                        low_52w = min(sparkline)

                tc_c = meta_entry.get('tc_col')
                pct_10y = 50.0
                med_10y = 15000.0
                if df_10y is not None and tc_c and tc_c in df_10y.columns:
                    hist = df_10y[tc_c].dropna()
                    avg_cur = (r_1y_atl + r_1y_pac) / 2.0
                    pct_10y = round((hist < avg_cur).mean() * 100.0, 1)
                    med_10y = round(hist.median())

                if pct_10y >= 90:
                    cycle_label = "Super Bullish (Top 10%)"
                    cycle_badge = "bull-top"
                elif pct_10y >= 75:
                    cycle_label = "Bullish (Upper Quartile)"
                    cycle_badge = "bull"
                elif pct_10y >= 40:
                    cycle_label = "Mid-Cycle Neutral"
                    cycle_badge = "neutral"
                else:
                    cycle_label = "Subdued / Soft"
                    cycle_badge = "bear"

                matrix["dry_bulk"].append({
                    "size": sz,
                    "rate_6m_atl": r_6m_atl, "chg_6m_atl": chg_6m_atl,
                    "rate_1y_atl": r_1y_atl, "chg_1y_atl": chg_1y_atl,
                    "rate_2y_atl": r_2y_atl, "chg_2y_atl": chg_2y_atl,
                    "rate_6m_pac": r_6m_pac, "chg_6m_pac": chg_6m_pac,
                    "rate_1y_pac": r_1y_pac, "chg_1y_pac": chg_1y_pac,
                    "rate_2y_pac": r_2y_pac, "chg_2y_pac": chg_2y_pac,
                    "basin_spread_1y": spread_1y,
                    "basin_spread_pct_1y": round((spread_1y / r_1y_pac * 100.0) if r_1y_pac > 0 else 0.0, 1),
                    "basin_spread_6m": spread_6m,
                    "basin_spread_2y": spread_2y,
                    "sparkline_52w": sparkline,
                    "mom_1w": chg_1y_atl,
                    "mom_1m": mom_1m,
                    "mom_1y": mom_1y,
                    "high_52w": high_52w,
                    "low_52w": low_52w,
                    "pctile_10y": pct_10y,
                    "median_10y": med_10y,
                    "cycle_label": cycle_label,
                    "cycle_badge": cycle_badge
                })

    tanker_map = {
        'Handymax': {'col': 'HANDY', 'tc_col': 'handytanker_1y'},
        'MR IMO3': {'col': 'MR', 'tc_col': 'mr_1y'},
        'LR1': {'col': 'LR1', 'tc_col': 'lr1_1y'},
        'LR2': {'col': 'LR2', 'tc_col': 'lr2_1y'},
        'Aframax': {'col': 'AFRA', 'tc_col': 'aframax_1y'},
        'Suezmax': {'col': 'SUEZ', 'tc_col': 'suezmax_1y'},
        'VLCC': {'col': 'VLCC', 'tc_col': 'vlcc_1y'}
    }

    if tanker_files:
        with open(tanker_files[-1], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not r or not r.get("Size"):
                    continue
                sz = r.get("Size", "").strip()
                r_1y = float(r.get("1Year", 0) or 0)
                chg_1y = float(r.get("1Yrchange", 0) or 0)
                r_2y = float(r.get("2Years", 0) or 0)
                chg_2y = float(r.get("2Yrchange", 0) or 0)
                r_3y = float(r.get("3Years", 0) or 0)
                chg_3y = float(r.get("3Yrchange", 0) or 0)
                r_5y = float(r.get("5 Years", 0) or 0)
                chg_5y = float(r.get("5Yrchange", 0) or 0)

                curve_spread_3y = r_1y - r_3y
                if curve_spread_3y > 2000:
                    slope_state = "Backwardation (Prompt Premium)"
                    slope_badge = "backwardation"
                elif curve_spread_3y < -2000:
                    slope_state = "Contango (Forward Premium)"
                    slope_badge = "contango"
                else:
                    slope_state = "Flat Curve"
                    slope_badge = "flat"

                sparkline = []
                mom_1m = 0.0
                mom_1y = 0.0
                high_52w = r_1y
                low_52w = r_1y

                meta_entry = tanker_map.get(sz, {})
                col_t = meta_entry.get('col')
                if df_t_1y is not None and col_t in df_t_1y.columns:
                    s_vals = df_t_1y[col_t].dropna().tolist()
                    sparkline = [float(v) for v in s_vals[-52:]]
                    if len(sparkline) >= 5 and sparkline[-5] > 0:
                        mom_1m = round(((sparkline[-1] - sparkline[-5]) / sparkline[-5]) * 100.0, 1)
                    if len(sparkline) >= 20 and sparkline[0] > 0:
                        mom_1y = round(((sparkline[-1] - sparkline[0]) / sparkline[0]) * 100.0, 1)
                    if sparkline:
                        high_52w = max(sparkline)
                        low_52w = min(sparkline)

                tc_c = meta_entry.get('tc_col')
                pct_10y = 50.0
                med_10y = 25000.0
                if df_10y is not None and tc_c and tc_c in df_10y.columns:
                    hist = df_10y[tc_c].dropna()
                    pct_10y = round((hist < r_1y).mean() * 100.0, 1)
                    med_10y = round(hist.median())

                if pct_10y >= 90:
                    cycle_label = "Super Bullish (Top 10%)"
                    cycle_badge = "bull-top"
                elif pct_10y >= 75:
                    cycle_label = "Bullish (Upper Quartile)"
                    cycle_badge = "bull"
                elif pct_10y >= 40:
                    cycle_label = "Mid-Cycle Neutral"
                    cycle_badge = "neutral"
                else:
                    cycle_label = "Subdued / Soft"
                    cycle_badge = "bear"

                eco_val = eco_spreads.get(sz, 4000)

                matrix["tankers"].append({
                    "size": sz,
                    "rate_1y": r_1y, "chg_1y": chg_1y,
                    "rate_2y": r_2y, "chg_2y": chg_2y,
                    "rate_3y": r_3y, "chg_3y": chg_3y,
                    "rate_5y": r_5y, "chg_5y": chg_5y,
                    "curve_slope_3y": curve_spread_3y,
                    "curve_slope_state": slope_state,
                    "curve_slope_badge": slope_badge,
                    "eco_premium_day": eco_val,
                    "sparkline_52w": sparkline,
                    "mom_1w": chg_1y,
                    "mom_1m": mom_1m,
                    "mom_1y": mom_1y,
                    "high_52w": high_52w,
                    "low_52w": low_52w,
                    "pctile_10y": pct_10y,
                    "median_10y": med_10y,
                    "cycle_label": cycle_label,
                    "cycle_badge": cycle_badge
                })

    out_file = DERIVED_DIR / "alibra_tce_matrix.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2)

    print(f"Generated {out_file} with {len(matrix['dry_bulk'])} dry bulk and {len(matrix['tankers'])} tanker classes!")
    return matrix

if __name__ == "__main__":
    generate_tce_matrix_json()
