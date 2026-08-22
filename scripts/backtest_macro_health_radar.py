#!/usr/bin/env python3
"""
Macro Health Radar Engine - 4-Regime Historical Backtest & Calibration
Computes point-in-time 5-pillar scores (0-100) across daily freight history:
  Pillar 1: Freight Momentum (BDI vs 90D MA & 30D ROC) [0-20]
  Pillar 2: Term Structure Slope (Capesize 4-6M vs 2Y TC rate spread) [0-20]
  Pillar 3: Futures Basis Arbitrage (Spot BDI vs BDRYFF Futures) [0-20]
  Pillar 4: Port Restocking Dynamics (China Port Inventories Mt) [0-20]
  Pillar 5: Asset Cycle Safety (Capesize 10Y S&P vs Scrap Margin) [0-20]

Calibrated 4 Regimes:
  - Bullish Expansion (>= 75 pts)
  - Constructive Expansion (60-74 pts)
  - Balanced Mid-Cycle (45-59 pts)
  - Contraction / Trough (< 45 pts)

Saves backtest dataset to data/derived/macro_health_score_backtest.csv
"""

import os
import json
import pandas as pd
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, 'data')
DERIVED_DIR = os.path.join(DATA_DIR, 'derived')
os.makedirs(DERIVED_DIR, exist_ok=True)

# Trading-day staleness above which an input is flagged (any_input_stale).
STALENESS_WARN_TRADING_DAYS = 15

def run_backtest():
    # 1. Load BDI
    bdi_df = pd.read_csv(os.path.join(DATA_DIR, 'indices', 'bdiy_historical.csv'))
    bdi_df['date'] = pd.to_datetime(bdi_df['Date'], format='%d-%m-%Y', errors='coerce')
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
    io_df = io_df.sort_values('date').reset_index(drop=True)

    # 6. Load Valuations & Scrappage
    val_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'vessel_valuations.csv'))
    val_df['date'] = pd.to_datetime(val_df['date'])
    val_df = val_df.sort_values('date').reset_index(drop=True)
    val_cape = val_df[(val_df['category'] == 'S&P') & (val_df['tenor_type'] == 'DRY-10') & (val_df['vessel_class'] == 'Capesize')]

    scrap_df = pd.read_csv(os.path.join(DATA_DIR, 'derived', 'scrappage_prices.csv'))
    scrap_df['date'] = pd.to_datetime(scrap_df['date'])
    scrap_df = scrap_df.sort_values('date').reset_index(drop=True)

    # Merge on master trading dates
    master = pd.merge(bdi_df[['date', 'bdiy']], bdry_df[['date', 'close']].rename(columns={'close': 'bdry'}), on='date', how='inner')
    master = master.sort_values('date').reset_index(drop=True)

    records = []
    bdi_vals = bdi_df[['date', 'bdiy']].set_index('date')['bdiy'].to_dict()
    bdryff_vals = bdryff_df[['date', 'bdryff']].dropna().set_index('date')['bdryff'].to_dict()

    dates = master['date'].tolist()
    master_dates_np = master['date'].values

    def trading_day_staleness(idx, last_obs_date):
        """Trading sessions between the evaluation date and the input's last
        observation (position-based, master frame = trading sessions)."""
        if last_obs_date is None or pd.isna(last_obs_date):
            return idx + 1
        pos = np.searchsorted(master_dates_np, np.datetime64(last_obs_date), side='right') - 1
        if pos < 0:
            return idx + 1
        return int(idx - pos)

    for idx, d in enumerate(dates):
        cur_bdi = master.loc[idx, 'bdiy']
        cur_bdry = master.loc[idx, 'bdry']

        # Pillar 1: Freight Momentum (0-20)
        past_bdi = bdi_df[bdi_df['date'] <= d]['bdiy'].values
        p1 = 10
        if len(past_bdi) >= 90:
            ma90 = np.mean(past_bdi[-90:])
            v30 = past_bdi[-31] if len(past_bdi) >= 31 else past_bdi[0]
            roc30 = ((cur_bdi - v30) / v30) * 100 if v30 > 0 else 0
            if cur_bdi > ma90 and roc30 > 5:
                p1 = 20
            elif cur_bdi > ma90 and roc30 > 0:
                p1 = 16
            elif cur_bdi > ma90:
                p1 = 12
            elif roc30 > 20:
                p1 = 12
            elif roc30 > 0:
                p1 = 8
            elif roc30 > -5:
                p1 = 4
            else:
                p1 = 0

        # Pillar 2: Term Structure Slope (0-20)
        past_tc = tc_df[tc_df['date'] <= d]
        p2 = 10
        staleness_p2 = trading_day_staleness(idx, past_tc.iloc[-1]['date'] if len(past_tc) > 0 else None)
        if len(past_tc) > 0:
            last_tc = past_tc.iloc[-1]
            near_term = last_tc.get('capesize_4_6m_avg')
            long_term = last_tc.get('capesize_2y_avg')
            if pd.notnull(near_term) and pd.notnull(long_term) and long_term > 0:
                spread_pct = ((near_term - long_term) / long_term) * 100
                if spread_pct > 15:
                    p2 = 20
                elif spread_pct > 5:
                    p2 = 16
                elif spread_pct > 0:
                    p2 = 12
                elif spread_pct > -10:
                    p2 = 6
                else:
                    p2 = 2

        # Pillar 3: Futures Basis (0-20)
        p3 = 10
        past_ff = bdryff_df[bdryff_df['date'] <= d]
        staleness_p3 = trading_day_staleness(idx, past_ff.iloc[-1]['date'] if len(past_ff) > 0 else None)
        if len(past_ff) > 0:
            ff_val = past_ff.iloc[-1]['bdryff']
            if pd.notnull(ff_val) and ff_val > 0:
                basis_pct = ((cur_bdi - ff_val) / ff_val) * 100
                if basis_pct > 10:
                    p3 = 20
                elif basis_pct > 4:
                    p3 = 16
                elif basis_pct > 0:
                    p3 = 12
                elif basis_pct > -5:
                    p3 = 7
                elif basis_pct > -15:
                    p3 = 3
                else:
                    p3 = 0

        # Pillar 4: Port Restocking (0-20)
        past_io = io_df[(io_df['date'] <= d) & (io_df['inventories_mt'].notnull())]
        p4 = 10
        staleness_p4 = trading_day_staleness(idx, past_io.iloc[-1]['date'] if len(past_io) > 0 else None)
        if len(past_io) > 0:
            inv = past_io.iloc[-1]['inventories_mt']
            if inv < 110:
                p4 = 20
            elif inv < 125:
                p4 = 17
            elif inv < 140:
                p4 = 13
            elif inv < 155:
                p4 = 8
            elif inv < 170:
                p4 = 4
            else:
                p4 = 1

        # Pillar 5: Asset Cycle Safety (0-20)
        past_val = val_cape[val_cape['date'] <= d]
        past_scrap = scrap_df[(scrap_df['date'] <= d) & (scrap_df['dry_india'].notnull())]
        p5 = 10
        p5_last_obs = None
        cand_dates = [df.iloc[-1]['date'] for df in (past_val, past_scrap) if len(df) > 0]
        if cand_dates:
            p5_last_obs = max(cand_dates)
        staleness_p5 = trading_day_staleness(idx, p5_last_obs)
        if len(past_val) > 0 and len(past_scrap) > 0:
            sp_val = past_val.iloc[-1]['valuation_usd_m']
            scrap_val_m = (past_scrap.iloc[-1]['dry_india'] * 17000) / 1e6
            if pd.notnull(sp_val) and sp_val > 0 and scrap_val_m > 0:
                margin_pct = ((sp_val - scrap_val_m) / sp_val) * 100
                if 25 <= margin_pct <= 40:
                    p5 = 20
                elif 40 < margin_pct <= 55:
                    p5 = 15
                elif margin_pct > 55:
                    p5 = 10
                elif margin_pct >= 15:
                    p5 = 12
                elif margin_pct >= 5:
                    p5 = 6
                else:
                    p5 = 2

        total = p1 + p2 + p3 + p4 + p5
        if total >= 75:
            regime = 'Bullish Expansion'
        elif total >= 60:
            regime = 'Constructive Expansion'
        elif total >= 45:
            regime = 'Balanced Mid-Cycle'
        else:
            regime = 'Contraction / Trough'

        # Forward returns
        fwd_1w_bdi = ((master.loc[idx + 5, 'bdiy'] - cur_bdi) / cur_bdi) * 100 if idx + 5 < len(master) else np.nan
        fwd_1w_bdry = ((master.loc[idx + 5, 'bdry'] - cur_bdry) / cur_bdry) * 100 if idx + 5 < len(master) else np.nan

        fwd_1m_bdi = ((master.loc[idx + 21, 'bdiy'] - cur_bdi) / cur_bdi) * 100 if idx + 21 < len(master) else np.nan
        fwd_1m_bdry = ((master.loc[idx + 21, 'bdry'] - cur_bdry) / cur_bdry) * 100 if idx + 21 < len(master) else np.nan

        fwd_3m_bdi = ((master.loc[idx + 63, 'bdiy'] - cur_bdi) / cur_bdi) * 100 if idx + 63 < len(master) else np.nan
        fwd_3m_bdry = ((master.loc[idx + 63, 'bdry'] - cur_bdry) / cur_bdry) * 100 if idx + 63 < len(master) else np.nan

        fwd_6m_bdi = ((master.loc[idx + 126, 'bdiy'] - cur_bdi) / cur_bdi) * 100 if idx + 126 < len(master) else np.nan
        fwd_6m_bdry = ((master.loc[idx + 126, 'bdry'] - cur_bdry) / cur_bdry) * 100 if idx + 126 < len(master) else np.nan

        staleness_p1 = 0  # pillar 1 consumes the current session's BDI directly

        records.append({
            'date': d.strftime('%Y-%m-%d'),
            'bdi': cur_bdi,
            'bdry': cur_bdry,
            'p1_momentum': p1,
            'p2_term_structure': p2,
            'p3_futures_basis': p3,
            'p4_port_restock': p4,
            'p5_asset_safety': p5,
            'total_score': total,
            'regime': regime,
            'input_staleness_p1': staleness_p1,
            'input_staleness_p2': staleness_p2,
            'input_staleness_p3': staleness_p3,
            'input_staleness_p4': staleness_p4,
            'input_staleness_p5': staleness_p5,
            'any_input_stale': bool(max(staleness_p1, staleness_p2, staleness_p3, staleness_p4, staleness_p5) > STALENESS_WARN_TRADING_DAYS),
            'bdi_fwd_1W': fwd_1w_bdi,
            'bdry_fwd_1W': fwd_1w_bdry,
            'bdi_fwd_1M': fwd_1m_bdi,
            'bdry_fwd_1M': fwd_1m_bdry,
            'bdi_fwd_3M': fwd_3m_bdi,
            'bdry_fwd_3M': fwd_3m_bdry,
            'bdi_fwd_6M': fwd_6m_bdi,
            'bdry_fwd_6M': fwd_6m_bdry,
        })

    out_df = pd.DataFrame(records)
    out_csv = os.path.join(DERIVED_DIR, 'macro_health_score_backtest.csv')
    out_df.to_csv(out_csv, index=False)
    print(f"Generated Macro Health Score Backtest dataset with {len(out_df)} rows at {out_csv}")
    return out_df

if __name__ == '__main__':
    run_backtest()
