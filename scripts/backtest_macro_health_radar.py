#!/usr/bin/env python3
"""
Macro Heat Score Engine - Historical Backtest & Calibration (v2, evidence-based)

Point-in-time 5-pillar composite (0-100). v2 replaces cliff-step scoring with
graded transforms and self-calibrating percentiles, and re-labels regimes to
match realized forward returns (freight is strongly mean-reverting):

  Pillar 1: Freight Momentum      - graded MA-gap + ROC blend            [0-20]
  Pillar 2: Term Structure Slope  - continuous spread map (-15%..+15%)   [0-20]
  Pillar 3: Futures Basis Arb     - continuous basis map (-15%..+10%)    [0-20]
  Pillar 4: Port Restocking       - inverted expanding percentile        [0-20]
  Pillar 5: Asset Cycle Heat      - S&P-vs-scrap margin percentile tent  [0-20]

Regimes (labels reflect forward-return evidence, 2018-2026 backtest):
  - >= 75 : Overheated - Reversal Risk   (fwd 3M BDI strongly negative)
  - 60-74 : Late-Cycle Strength          (fwd 3M mildly negative)
  - 45-59 : Mid-Cycle Equilibrium        (fwd 3M modestly positive)
  - < 45  : Trough - Accumulation Zone   (fwd 3M strongly positive)

Percentile windows are strictly point-in-time (only observations dated before
the current one; capped at 1260 obs, minimum 126 before activating).

Saves backtest dataset to data/derived/macro_heat_score_backtest.csv
(legacy macro_health_score_backtest.csv name kept for compatibility below).
"""

import os
import numpy as np
import pandas as pd

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, 'data')
DERIVED_DIR = os.path.join(DATA_DIR, 'derived')
os.makedirs(DERIVED_DIR, exist_ok=True)

STALENESS_WARN_TRADING_DAYS = 15

# Percentile window parameters (shared with index.html implementation)
PCTL_MIN_OBS = 126
PCTL_MAX_OBS = 1260


def lin_map(x, anchors):
    """Piecewise-linear interpolation through (x, score) anchors, clipped to ends."""
    xs = [a[0] for a in anchors]
    ys = [a[1] for a in anchors]
    return float(np.interp(x, xs, ys))


def expanding_percentile(window: np.ndarray, value: float) -> float | None:
    """Percentile rank of `value` within the trailing observation window."""
    w = np.asarray(window, dtype=float)
    if len(w) < PCTL_MIN_OBS:
        return None
    if len(w) > PCTL_MAX_OBS:
        w = w[-PCTL_MAX_OBS:]
    return float(np.mean(w <= value))


def run_backtest():
    # 1. Load BDI
    bdi_df = pd.read_csv(os.path.join(DATA_DIR, 'indices', 'bdiy_historical.csv'))
    bdi_df['date'] = pd.to_datetime(bdi_df['Date'], errors='coerce')
    bdi_df['bdiy'] = pd.to_numeric(bdi_df['Index'].astype(str).str.replace(',', ''), errors='coerce')
    bdi_df = bdi_df.dropna(subset=['date', 'bdiy']).sort_values('date').reset_index(drop=True)

    # 2. Load BDRY ETF
    bdry_df = pd.read_csv(os.path.join(DATA_DIR, 'etf', 'bdry_liquidity.csv'))
    bdry_df['date'] = pd.to_datetime(bdry_df['date'])
    bdry_df['bdry'] = pd.to_numeric(bdry_df['close'], errors='coerce')
    bdry_df = bdry_df.dropna(subset=['date', 'bdry']).sort_values('date').reset_index(drop=True)

    # 3. Load Futures BDRYFF
    bdryff_df = pd.read_csv(os.path.join(DATA_DIR, 'futures', 'bdryff_history.csv'))
    bdryff_df['date'] = pd.to_datetime(bdryff_df['date'])
    bdryff_df['bdryff'] = pd.to_numeric(bdryff_df['value'], errors='coerce')
    bdryff_df = bdryff_df.dropna(subset=['date', 'bdryff']).sort_values('date').reset_index(drop=True)

    # 4. Load Time Charter Rates
    tc_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'time_charter_rates.csv'))
    tc_df['date'] = pd.to_datetime(tc_df['date'])
    tc_df = tc_df.sort_values('date').reset_index(drop=True)

    # 5. Load Port Inventory
    io_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'iron_ore_restocking.csv'))
    io_df['date'] = pd.to_datetime(io_df['date'])
    io_df = io_df[io_df['inventories_mt'].notna()].sort_values('date').reset_index(drop=True)

    # 6. Load Valuations & Scrappage
    val_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'vessel_valuations.csv'))
    val_df['date'] = pd.to_datetime(val_df['date'])
    val_cape = val_df[(val_df['category'] == 'S&P') & (val_df['tenor_type'] == 'DRY-10') &
                      (val_df['vessel_class'] == 'Capesize')].dropna(subset=['valuation_usd_m'])
    val_cape = val_cape.sort_values('date').reset_index(drop=True)

    scrap_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'scrappage_prices.csv'))
    scrap_df['date'] = pd.to_datetime(scrap_df['date'])
    scrap_df = scrap_df[scrap_df['dry_india'].notna()].sort_values('date').reset_index(drop=True)

    # Precompute paired Cape S&P-vs-scrap margin history (point-in-time pairing:
    # each valuation matched to the latest scrap print on/before its own date).
    margin_pts = []  # list of (date, margin_pct)
    sc_dates = scrap_df['date'].values
    sc_vals = scrap_df['dry_india'].values.astype(float)
    ptr = 0
    last_scrap = None
    for _, vrow in val_cape.iterrows():
        while ptr < len(sc_dates) and sc_dates[ptr] <= vrow['date']:
            last_scrap = float(sc_vals[ptr])
            ptr += 1
        if last_scrap is not None and last_scrap > 0:
            sp = float(vrow['valuation_usd_m'])
            if sp > 0:
                margin_pts.append((vrow['date'], ((sp - last_scrap * 24000 / 1e6) / sp) * 100))
    margin_dates = np.array([m[0] for m in margin_pts])
    margin_vals = np.array([m[1] for m in margin_pts])

    master = pd.merge(bdi_df[['date', 'bdiy']], bdry_df[['date', 'bdry']], on='date', how='inner')
    master = master.sort_values('date').reset_index(drop=True)

    dates = master['date'].tolist()
    master_dates_np = master['date'].values

    def trading_day_staleness(idx, last_obs_date):
        if last_obs_date is None or pd.isna(last_obs_date):
            return idx + 1
        pos = np.searchsorted(master_dates_np, np.datetime64(last_obs_date), side='right') - 1
        if pos < 0:
            return idx + 1
        return int(idx - pos)

    def last_asof(df, d):
        sub = df[df['date'] <= d]
        return sub.iloc[-1] if len(sub) else None

    records = []
    for idx, d in enumerate(dates):
        cur_bdi = master.loc[idx, 'bdiy']

        # ── Pillar 1: Freight Momentum (graded blend of MA-gap and 30D ROC) ──
        past_bdi = bdi_df[bdi_df['date'] <= d]['bdiy'].values
        p1 = 10.0
        if len(past_bdi) >= 90:
            ma90 = float(np.mean(past_bdi[-90:]))
            v30 = past_bdi[-31] if len(past_bdi) >= 31 else past_bdi[0]
            roc30 = ((cur_bdi - v30) / v30) * 100 if v30 > 0 else 0.0
            ma_gap = ((cur_bdi - ma90) / ma90) * 100 if ma90 > 0 else 0.0
            f = lin_map(ma_gap, [(-20, -4), (-5, -2), (0, 0), (2.5, 1.5), (10, 3), (30, 5)])
            g = lin_map(roc30, [(-20, -6), (-5, -3), (0, -1.5), (2.5, 0.5), (5, 2), (20, 3.5), (40, 5)])
            p1 = round(float(np.clip(10 + f + g, 0, 20)), 1)

        # ── Pillar 2: Term Structure Slope (continuous spread map) ───────────
        tcr = last_asof(tc_df, d)
        staleness_p2 = trading_day_staleness(idx, tcr['date'] if tcr is not None else None)
        p2 = 10.0
        spread_pct = None
        if tcr is not None:
            nt, lt = tcr.get('capesize_4_6m_avg'), tcr.get('capesize_2y_avg')
            if pd.notna(nt) and pd.notna(lt) and lt > 0:
                spread_pct = ((nt - lt) / lt) * 100
                p2 = round(lin_map(spread_pct, [(-15, 2), (-5, 7), (0, 11), (5, 15.5), (15, 20)]), 1)

        # ── Pillar 3: Futures Basis Arb (continuous basis map) ───────────────
        ff_row = last_asof(bdryff_df, d)
        staleness_p3 = trading_day_staleness(idx, ff_row['date'] if ff_row is not None else None)
        p3 = 10.0
        basis_pct = None
        if ff_row is not None:
            ff_val = ff_row['bdryff']
            if pd.notna(ff_val) and cur_bdi > 0:
                basis_pct = ((ff_val - cur_bdi) / cur_bdi) * 100
                p3 = round(lin_map(basis_pct, [(-10, 20), (-4, 15), (0, 11), (5, 4.5), (15, 0)]), 1)

        # ── Pillar 4: Port Restocking (inverted expanding percentile) ────────
        io_row = last_asof(io_df, d)
        staleness_p4 = trading_day_staleness(idx, io_row['date'] if io_row is not None else None)
        p4 = 10.0
        inv_pctl = None
        if io_row is not None:
            inv = float(io_row['inventories_mt'])
            prior = io_df[io_df['date'] < io_row['date']]['inventories_mt'].values
            pr = expanding_percentile(prior[-PCTL_MAX_OBS:], inv)
            if pr is None:
                # warm-up fallback: legacy absolute steps
                p4 = 20.0 if inv < 110 else 17.0 if inv < 125 else 13.0 if inv < 140 else \
                     8.0 if inv < 155 else 4.0 if inv < 170 else 1.0
            else:
                inv_pctl = pr
                p4 = round(lin_map(pr, [(0.0, 20), (0.25, 16), (0.5, 12), (0.75, 7), (1.0, 0)]), 1)

        # ── Pillar 5: Asset Cycle Heat (margin percentile tent) ──────────────
        vr = last_asof(val_cape, d)
        scr = last_asof(scrap_df, d)
        cand = [x['date'] for x in (vr, scr) if x is not None]
        staleness_p5 = trading_day_staleness(idx, max(cand) if cand else None)
        p5 = 10.0
        margin_pctl = None
        if vr is not None and scr is not None:
            sp_val = float(vr['valuation_usd_m'])
            scrap_m = float(scr['dry_india']) * 24000 / 1e6
            if sp_val > 0 and scrap_m > 0:
                margin_now = ((sp_val - scrap_m) / sp_val) * 100
                prior_m = margin_vals[margin_dates < vr['date']]
                pr = expanding_percentile(prior_m, margin_now)
                if pr is None:
                    # warm-up fallback: legacy sweet-spot steps
                    m = margin_now
                    p5 = 20.0 if 25 <= m <= 40 else 15.0 if 40 < m <= 55 else 10.0 if m > 55 else \
                         12.0 if m >= 15 else 6.0 if m >= 5 else 2.0
                else:
                    margin_pctl = pr
                    if pr <= 0.5:
                        p5 = round(lin_map(pr, [(0.05, 6), (0.5, 20)]), 1)
                    else:
                        p5 = round(lin_map(pr, [(0.5, 20), (0.95, 5)]), 1)

        total = round(p1 + p2 + p3 + p4 + p5, 1)
        if total >= 75:
            regime = 'Overheated - Reversal Risk'
        elif total >= 60:
            regime = 'Late-Cycle Strength'
        elif total >= 45:
            regime = 'Mid-Cycle Equilibrium'
        else:
            regime = 'Trough - Accumulation Zone'

        def fwd(lag):
            return ((master.loc[idx + lag, 'bdiy'] - cur_bdi) / cur_bdi) * 100 if idx + lag < len(master) else np.nan

        def fwd_bdry(lag):
            cb = master.loc[idx, 'bdry']
            return ((master.loc[idx + lag, 'bdry'] - cb) / cb) * 100 if idx + lag < len(master) else np.nan

        records.append({
            'date': d.strftime('%Y-%m-%d'),
            'bdi': cur_bdi,
            'bdry': master.loc[idx, 'bdry'],
            'p1_momentum': p1,
            'p2_term_structure': p2,
            'p3_futures_basis': p3,
            'p4_port_restock': p4,
            'p4_inv_pctl': round(inv_pctl, 3) if inv_pctl is not None else np.nan,
            'p5_asset_safety': p5,
            'p5_margin_pctl': round(margin_pctl, 3) if margin_pctl is not None else np.nan,
            'total_score': total,
            'regime': regime,
            'input_staleness_p1': 0,
            'input_staleness_p2': staleness_p2,
            'input_staleness_p3': staleness_p3,
            'input_staleness_p4': staleness_p4,
            'input_staleness_p5': staleness_p5,
            'any_input_stale': bool(max(staleness_p2, staleness_p3, staleness_p4, staleness_p5) > STALENESS_WARN_TRADING_DAYS),
            'bdi_fwd_1W': fwd(5),
            'bdry_fwd_1W': fwd_bdry(5),
            'bdi_fwd_1M': fwd(21),
            'bdry_fwd_1M': fwd_bdry(21),
            'bdi_fwd_3M': fwd(63),
            'bdry_fwd_3M': fwd_bdry(63),
            'bdi_fwd_6M': fwd(126),
            'bdry_fwd_6M': fwd_bdry(126),
        })

    out_df = pd.DataFrame(records)
    out_csv = os.path.join(DERIVED_DIR, 'macro_health_score_backtest.csv')
    out_df.to_csv(out_csv, index=False)
    print(f"Generated Macro Heat Score Backtest dataset with {len(out_df)} rows at {out_csv}")
    return out_df


if __name__ == '__main__':
    run_backtest()
