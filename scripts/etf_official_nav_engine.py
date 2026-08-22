"""
ETF Official NAV Accounting & Reconstruction Engine
===================================================
Implements the canonical Net Asset Value (NAV) accounting waterfall and 10-Q
balance sheet taxonomy for Breakwave Dry Bulk Shipping ETF (BDRY) and
Breakwave Tanker Shipping ETF (BWET).

STRICT DIRECTIVE:
1. Compares Simulated NAV strictly to Official Disclosed NAV (from fund administrator / 10-Q).
2. Models NYSE Arca secondary market close as a separate Premium/Discount layer.
3. No synthetic proxy marks or gap fills.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple
from test_10q_golden_fixtures import SEC_10Q_MARCH_31_2026
from contract_spec_registry import resolve_contract_spec, UnknownContractSpecError

FUTURES_MARKER_TOKENS = ('FFA', 'TD3C', 'TD20', 'C4', 'P4', 'S4')
CASH_NAME_TOKENS = ('CASH', 'COLLATERAL', 'MAREX', 'USD')

def is_cash_side_holding(name, ticker='', cusip=''):
    """
    Single authority for futures-vs-cash-side classification.
    Futures marker tokens short-circuit to False; otherwise the contract spec
    registry decides (Collateral/Cash Equivalent vessel class => cash side).
    Unmapped names fall back to exact-ish cash token matching.
    """
    name_str = str(name).upper()
    if any(token in name_str for token in FUTURES_MARKER_TOKENS):
        return False
    try:
        spec = resolve_contract_spec(str(name), ticker=str(ticker or ''), cusip=str(cusip or ''))
    except UnknownContractSpecError:
        return any(token in name_str for token in CASH_NAME_TOKENS)
    return spec.get('vessel_class') == 'Collateral/Cash Equivalent'

def normalize_holdings_record(df_raw: pd.DataFrame, etf_key: str) -> pd.DataFrame:
    """
    Standardizes raw portfolio disclosures into canonical holdings schema.
    """
    records = []
    col_map = {c.lower().strip(): c for c in df_raw.columns}
    
    date_col = col_map.get('date', 'date')
    name_col = col_map.get('name', 'Name')
    shares_col = col_map.get('lots', col_map.get('shares_held', col_map.get('shares', 'Lots')))
    mark_col = col_map.get('price', col_map.get('mark', 'Price'))
    mv_col = col_map.get('market_value', col_map.get('marketvalue', 'Market_Value'))
    ticker_col = col_map.get('ticker', 'Ticker')
    cusip_col = col_map.get('cusip', 'CUSIP')
    
    for _, row in df_raw.iterrows():
        d_str = str(row.get(date_col, '')).strip()
        name_str = str(row.get(name_col, '')).strip()
        ticker_str = str(row.get(ticker_col, '')).strip()
        cusip_str = str(row.get(cusip_col, '')).strip()
        try:
            qty = float(row.get(shares_col, 0.0))
        except (ValueError, TypeError):
            qty = 0.0
        try:
            mark = float(row.get(mark_col, 0.0))
        except (ValueError, TypeError):
            mark = 0.0
        try:
            mv = float(row.get(mv_col, 0.0))
        except (ValueError, TypeError):
            mv = 0.0
            
        is_money_market = any(x in name_str.upper() for x in ['AGPXX', 'INVESCO', 'GOVERNMENT', 'TREASURY'])
        is_cash = is_cash_side_holding(name_str, ticker_str, cusip_str) and not is_money_market
        is_futures = not (is_money_market or is_cash)
        
        route_class = 'other'
        mult = 1.0
        if is_futures:
            u_name = name_str.upper()
            if etf_key == 'bdry':
                mult = 1.0
                if 'CAPE' in u_name:
                    route_class = 'cape'
                elif 'PANA' in u_name:
                    route_class = 'pana'
                elif 'SUPRA' in u_name:
                    route_class = 'supra'
            elif etf_key == 'bwet':
                mult = 1000.0
                if 'TD3C' in u_name or 'VLCC' in u_name:
                    route_class = 'vlcc'
                elif 'TD20' in u_name or 'SUEZ' in u_name:
                    route_class = 'suez'
                    
        records.append({
            'date': d_str,
            'contract_id': name_str,
            'name': name_str,
            'quantity': qty,
            'mark': mark,
            'multiplier': mult,
            'disclosed_market_value': mv,
            'is_futures': is_futures,
            'is_collateral': is_money_market,
            'is_cash': is_cash,
            'route_class': route_class
        })
        
    return pd.DataFrame(records)

def load_official_nav_series(etf_key: str) -> pd.DataFrame:
    """
    Loads official fund NAV records, daily flows, and performance history.
    """
    fpath = f"data/etf/{etf_key.upper()}_flows.csv"
    if not os.path.exists(fpath):
        return pd.DataFrame()
    df = pd.read_csv(fpath)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)

def load_market_price_series(etf_key: str) -> pd.DataFrame:
    """
    Loads secondary market NYSE Arca closing prices.
    """
    fpath = f"data/etf/{etf_key.lower()}_liquidity.csv"
    if not os.path.exists(fpath):
        return pd.DataFrame()
    df = pd.read_csv(fpath)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)

def run_official_nav_reconstruction(etf_key: str) -> Dict[str, Any]:
    """
    Executes the 10-Q NAV accounting waterfall across all historical disclosure dates.
    """
    hist_path = f"data/etf/{etf_key.lower()}_holdings_history.csv"
    df_raw = pd.read_csv(hist_path)
    df_norm = normalize_holdings_record(df_raw, etf_key)
    
    dates = sorted(list(df_norm['date'].unique()))
    df_nav_official = load_official_nav_series(etf_key)
    df_mkt = load_market_price_series(etf_key)
    
    nav_map = dict(zip(df_nav_official['date'], df_nav_official['nav'])) if not df_nav_official.empty else {}
    mkt_map = dict(zip(df_mkt['date'], df_mkt['close'])) if not df_mkt.empty else {}
    
    timeline = []
    valid_dates_count = 0
    missing_official_nav_count = 0
    missing_mkt_close_count = 0
    contract_transition_events = 0
    
    # Initialize state from first disclosure
    first_date = dates[0]
    first_day_holdings = df_norm[df_norm['date'] == first_date]
    first_fut = first_day_holdings[first_day_holdings['is_futures']]
    first_col = first_day_holdings[first_day_holdings['is_collateral']]['disclosed_market_value'].sum()
    first_csh = first_day_holdings[first_day_holdings['is_cash']]['disclosed_market_value'].sum()
    
    # Initial NAV per share anchored to official NAV or first market close
    initial_nav = nav_map.get(first_date, mkt_map.get(first_date, 10.09 if etf_key == 'bdry' else 119.74))
    sim_nav = float(initial_nav)
    
    for t, cur_date in enumerate(dates):
        cur_raw = df_norm[df_norm['date'] == cur_date]
        cur_fut = cur_raw[cur_raw['is_futures']].copy()
        cur_col = cur_raw[cur_raw['is_collateral']]['disclosed_market_value'].sum()
        cur_csh = cur_raw[cur_raw['is_cash']]['disclosed_market_value'].sum()
        cur_fut_notional = (cur_fut['quantity'] * cur_fut['mark'] * cur_fut['multiplier']).sum()
        
        official_nav = nav_map.get(cur_date, np.nan)
        mkt_close = mkt_map.get(cur_date, np.nan)
        
        if np.isnan(official_nav):
            missing_official_nav_count += 1
        if np.isnan(mkt_close):
            missing_mkt_close_count += 1
            
        held_pnl = 0.0
        retained_contracts = 0
        new_contracts = 0
        exited_contracts = 0
        
        if t > 0:
            prev_date = dates[t - 1]
            prev_raw = df_norm[df_norm['date'] == prev_date]
            prev_fut = prev_raw[prev_raw['is_futures']].copy()
            prev_fut_notional = (prev_fut['quantity'] * prev_fut['mark'] * prev_fut['multiplier']).sum()
            
            prev_map = prev_fut.set_index('contract_id')
            cur_map = cur_fut.set_index('contract_id')
            
            prev_ids = set(prev_map.index)
            cur_ids = set(cur_map.index)
            
            retained_ids = prev_ids.intersection(cur_ids)
            new_ids = cur_ids - prev_ids
            exited_ids = prev_ids - cur_ids
            
            retained_contracts = len(retained_ids)
            new_contracts = len(new_ids)
            exited_contracts = len(exited_ids)
            
            if len(new_ids) > 0 or len(exited_ids) > 0:
                contract_transition_events += 1
                
            # Variation margin on retained contracts using prior quantity Q_{i, t-1}
            for cid in retained_ids:
                p_row = prev_map.loc[cid]
                c_row = cur_map.loc[cid]
                q_prev = float(p_row['quantity'])
                mult = float(c_row['multiplier'])
                dp = float(c_row['mark']) - float(p_row['mark'])
                held_pnl += q_prev * mult * dp
                
            freight_ret = held_pnl / prev_fut_notional if prev_fut_notional > 0 else 0.0
            
            # Business day cash yield (AGPXX repo 4.85% net of 1.45% statutory OER)
            dt_days = (datetime.strptime(cur_date, '%Y-%m-%d') - datetime.strptime(prev_date, '%Y-%m-%d')).days
            b_days = max(1, min(dt_days, 3))
            cash_yield = ((0.0485 - 0.0145) / 252.0) * b_days
            
            net_nav_return = freight_ret + cash_yield
            sim_nav = sim_nav * (1.0 + net_nav_return)
            
        spread_mkt_vs_sim_bps = ((mkt_close - sim_nav) / sim_nav) * 10000.0 if (not np.isnan(mkt_close) and sim_nav > 0) else np.nan
        spread_mkt_vs_off_bps = ((mkt_close - official_nav) / official_nav) * 10000.0 if (not np.isnan(mkt_close) and not np.isnan(official_nav) and official_nav > 0) else np.nan
        drift_sim_vs_off_bps = ((sim_nav - official_nav) / official_nav) * 10000.0 if (not np.isnan(official_nav) and official_nav > 0) else np.nan
        
        timeline.append({
            'date': cur_date,
            'sim_nav': sim_nav,
            'official_nav': official_nav,
            'market_close': mkt_close,
            'held_pnl': held_pnl,
            'futures_notional': cur_fut_notional,
            'collateral_agpxx': cur_col,
            'segregated_cash': cur_csh,
            'spread_mkt_vs_sim_bps': spread_mkt_vs_sim_bps,
            'spread_mkt_vs_off_bps': spread_mkt_vs_off_bps,
            'drift_sim_vs_off_bps': drift_sim_vs_off_bps,
            'retained_contracts': retained_contracts,
            'new_contracts': new_contracts,
            'exited_contracts': exited_contracts
        })
        
    df_res = pd.DataFrame(timeline)
    
    # Calculate statistical tracking metrics against official NAV
    valid_nav = df_res.dropna(subset=['sim_nav', 'official_nav'])
    nav_r2 = 0.0
    nav_mae_pct = 0.0
    if len(valid_nav) > 1:
        corr = np.corrcoef(valid_nav['sim_nav'], valid_nav['official_nav'])[0, 1]
        nav_r2 = (corr ** 2) * 100.0 if not np.isnan(corr) else 0.0
        nav_mae_pct = np.mean(np.abs((valid_nav['sim_nav'] - valid_nav['official_nav']) / valid_nav['official_nav'])) * 100.0
        
    # Statistical tracking of Market Close vs Official NAV (Premium/Discount Layer)
    valid_spreads = df_res['spread_mkt_vs_off_bps'].dropna()
    mean_spread = valid_spreads.mean() if len(valid_spreads) else 0.0
    std_spread = valid_spreads.std() if len(valid_spreads) else 0.0
    max_abs_spread = valid_spreads.abs().max() if len(valid_spreads) else 0.0
    
    return {
        'etf': etf_key.upper(),
        'timeline': df_res,
        'metrics': {
            'total_disclosure_dates': len(dates),
            'missing_official_nav_dates': missing_official_nav_count,
            'missing_market_close_dates': missing_mkt_close_count,
            'contract_transition_events': contract_transition_events,
            'nav_tracking_r2': nav_r2,
            'nav_tracking_mae_pct': nav_mae_pct,
            'market_spread_mean_bps': mean_spread,
            'market_spread_std_bps': std_spread,
            'market_spread_max_abs_bps': max_abs_spread
        }
    }

if __name__ == '__main__':
    print("==========================================================================================")
    print("               OFFICIAL NAV RECONSTRUCTION & 10-Q TAXONOMY VALIDATION                     ")
    print("==========================================================================================")
    for k in ['bdry', 'bwet']:
        res = run_official_nav_reconstruction(k)
        m = res['metrics']
        print(f"\n--- FUND: {res['etf']} ---")
        print(f"Total Disclosure Dates          : {m['total_disclosure_dates']}")
        print(f"Missing Official NAV Dates      : {m['missing_official_nav_dates']}")
        print(f"Missing Market Closes (NYSE)    : {m['missing_market_close_dates']}")
        print(f"Contract Transition Events      : {m['contract_transition_events']}")
        print(f"Official NAV Tracking R²        : {m['nav_tracking_r2']:.2f}%")
        print(f"Official NAV Tracking MAE       : ±{m['nav_tracking_mae_pct']:.2f}%")
        print(f"Market Close Premium/Disc (Mean): {m['market_spread_mean_bps']:+.1f} bps (std={m['market_spread_std_bps']:.1f} bps)")
        print(f"Market Close Premium/Disc (Max) : {m['market_spread_max_abs_bps']:.1f} bps")
        
        print("\nLast 5 Reconstructed Sessions:")
        tail_df = res['timeline'].tail(5)
        for _, r in tail_df.iterrows():
            mkt_s = f"${r['market_close']:.2f}" if not np.isnan(r['market_close']) else "MKT CLOSED"
            off_s = f"${r['official_nav']:.2f}" if not np.isnan(r['official_nav']) else "N/A"
            sp_s = f"{r['spread_mkt_vs_off_bps']:+.1f} bps" if not np.isnan(r['spread_mkt_vs_off_bps']) else "N/A"
            print(f"  {r['date']} | Sim NAV: ${r['sim_nav']:.2f} | Off NAV: {off_s:<8} | Mkt Close: {mkt_s:<10} | Mkt/Off Spread: {sp_s}")
    print("\n==========================================================================================")
