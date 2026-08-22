"""
True Sourced ETF NAV Accounting Waterfall & Chronological Evaluation Engine
===========================================================================
Implements fund-level Net Asset Value (NAV) accounting from sourced regulatory
disclosures. Enforces zero synthetic defaults, zero look-ahead initialization,
and strict decoupling of market close from NAV accounting.

CANONICAL ACCEPTANCE CRITERION:
"Partial accounting decomposition; not a validated NAV reconstruction; not trade-ready."
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional
from etf_provenance_registry import get_observation_provenance
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

def load_canonical_holdings(etf_key: str) -> pd.DataFrame:
    fpath = f"data/etf/{etf_key.lower()}_holdings_history.csv"
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"Missing required holdings file: {fpath}")
    return pd.read_csv(fpath)

def load_official_flows(etf_key: str) -> pd.DataFrame:
    fpath = f"data/etf/{etf_key.upper()}_flows.csv"
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"Missing required flows file: {fpath}")
    df = pd.read_csv(fpath)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.set_index('date')

def load_market_liquidity(etf_key: str) -> pd.DataFrame:
    fpath = f"data/etf/{etf_key.lower()}_liquidity.csv"
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"Missing required liquidity file: {fpath}")
    df = pd.read_csv(fpath)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.set_index('date')

def get_exact_official_nav(date_str: str, df_flows: pd.DataFrame) -> float:
    """
    Looks up exact official NAV for date_str.
    STRICT DIRECTIVE: Zero look-ahead and zero backward search. Returns NaN if absent.
    """
    if date_str in df_flows.index:
        val = df_flows.loc[date_str, 'nav']
        if pd.notna(val):
            return float(val)
    return np.nan

def get_exact_official_perf(date_str: str, df_flows: pd.DataFrame) -> float:
    """
    Looks up exact official daily performance for date_str. Returns NaN if absent.
    """
    if date_str in df_flows.index:
        val = df_flows.loc[date_str, 'perf_pct']
        if pd.notna(val):
            return float(val)
    return np.nan

def get_exact_usd_flow(date_str: str, df_flows: pd.DataFrame) -> float:
    """
    Looks up exact official USD flow for date_str. Returns 0.0 if absent.
    """
    if date_str in df_flows.index:
        val = df_flows.loc[date_str, 'usd_flow']
        if pd.notna(val):
            return float(val)
    return 0.0

def run_fund_level_nav_reconstruction(etf_key: str) -> Dict[str, Any]:
    df_raw = load_canonical_holdings(etf_key)
    df_flows = load_official_flows(etf_key)
    df_liq = load_market_liquidity(etf_key)
    
    dates = sorted(df_raw['date'].unique())
    is_bdry = (etf_key.lower() == 'bdry')
    multiplier = 1.0 if is_bdry else 1000.0
    
    # Organize holdings by date
    days_data = []
    for d in dates:
        sub = df_raw[df_raw['date'] == d]
        fut_mask = ~sub.apply(lambda r: is_cash_side_holding(r['Name'], r.get('Ticker', ''), r.get('CUSIP', '')), axis=1)
        fut_rows = sub[fut_mask]
        col_rows = sub[sub['Name'].str.contains('Invesco|AGPXX', case=False, na=False)]
        csh_rows = sub[sub.apply(lambda r: is_cash_side_holding(r['Name'], r.get('Ticker', ''), r.get('CUSIP', '')), axis=1) & ~sub['Name'].str.contains('Invesco|AGPXX', case=False, na=False)]
        
        fut_notional = (fut_rows['Lots'] * fut_rows['Price'] * multiplier).sum()
        col_val = col_rows['Market_Value'].sum()
        csh_val = csh_rows['Market_Value'].sum()
        
        contracts = {}
        for _, r in fut_rows.iterrows():
            cid = str(r['CUSIP']).strip() if pd.notna(r['CUSIP']) and str(r['CUSIP']).strip() != '' and str(r['CUSIP']).strip() != 'nan' else str(r['Name']).strip()
            contracts[cid] = {
                'name': str(r['Name']).strip(),
                'lots': float(r['Lots']),
                'price': float(r['Price']),
                'multiplier': multiplier,
                'notional': float(r['Lots']) * float(r['Price']) * multiplier
            }
            
        days_data.append({
            'date': d,
            'fut_notional': fut_notional,
            'col_val': col_val,
            'csh_val': csh_val,
            'contracts': contracts
        })
        
    timeline = []
    prev_contracts = days_data[0]['contracts']
    prev_date = dates[0]
    
    fully_reconciled_count = 0
    partial_unreconciled_count = 0
    missing_input_count = 0
    
    for t in range(len(days_data)):
        cur = days_data[t]
        d_str = cur['date']
        
        # 1. Exact Sourced NAV (Zero look-ahead)
        off_nav = get_exact_official_nav(d_str, df_flows)
        off_perf = get_exact_official_perf(d_str, df_flows)
        usd_flow = get_exact_usd_flow(d_str, df_flows)
        
        # 2. Decoupled Secondary Market Close Layer
        mkt_row = df_liq.loc[d_str] if d_str in df_liq.index else None
        mkt_close = float(mkt_row['close']) if mkt_row is not None and pd.notna(mkt_row['close']) else np.nan
        market_status = 'AVAILABLE' if not np.isnan(mkt_close) else 'MARKET_CLOSED'
        mkt_spread_bps = ((mkt_close - off_nav) / off_nav * 10000.0) if (not np.isnan(mkt_close) and not np.isnan(off_nav) and off_nav > 0) else np.nan
        
        # 3. Sourced Waterfall Components
        held_vm_dollars = 0.0
        realized_pnl_dollars = np.nan # Unobserved intraday trade fill log
        collateral_interest_dollars = np.nan # Unobserved daily custody bank voucher
        accrued_expenses_dollars = np.nan # Unobserved daily custodian billing voucher
        
        retained_count = 0
        new_count = 0
        exited_count = 0
        missing_notes = []
        
        # NAV Accounting Status (Decoupled from Market Close)
        if np.isnan(off_nav):
            reconciliation_status = 'MISSING_INPUT'
            missing_input_count += 1
            missing_notes.append("Official NAV not disclosed on this date")
        else:
            # STRICT ZERO-FABRICATION RULE: Without daily bank interest and custodian vouchers,
            # active sessions are strictly PARTIAL_DISCLOSURE_UNRECONCILED.
            reconciliation_status = 'PARTIAL_DISCLOSURE_UNRECONCILED'
            partial_unreconciled_count += 1
            missing_notes.append("Unobserved daily bank interest voucher & custodian billing voucher")
            
        if t > 0:
            prev_d = days_data[t - 1]
            prev_fut_notional = prev_d['fut_notional']
            cur_contracts = cur['contracts']
            
            p_ids = set(prev_contracts.keys())
            c_ids = set(cur_contracts.keys())
            
            retained = p_ids.intersection(c_ids)
            new_c = c_ids - p_ids
            exited = p_ids - c_ids
            
            retained_count = len(retained)
            new_count = len(new_c)
            exited_count = len(exited)
            
            # Sourced Retained Futures Variation Margin ($)
            for cid in retained:
                p_c = prev_contracts[cid]
                c_c = cur_contracts[cid]
                dp = c_c['price'] - p_c['price']
                held_vm_dollars += p_c['lots'] * multiplier * dp
                
            freight_vm_ret = (held_vm_dollars / prev_fut_notional) if prev_fut_notional > 0 else 0.0
            
            if len(exited) > 0 or len(new_c) > 0:
                missing_notes.append(f"Unobserved intraday roll/expiry execution fills ({len(exited)} exits, {len(new_c)} additions)")
                
            if usd_flow != 0:
                missing_notes.append(f"AP capital flow of ${usd_flow:,.0f} (unobserved share transfer timing)")
                
            prev_contracts = cur_contracts
            prev_date = d_str
        else:
            freight_vm_ret = 0.0
            
        prov_tag = get_observation_provenance(d_str, etf_key)
        
        timeline.append({
            'session': t,
            'date': d_str,
            'official_nav': off_nav,
            'official_perf_pct': off_perf,
            'reconstructed_nav': np.nan, # Explicitly unmodeled without shares ledger & vouchers
            'shares_outstanding': np.nan, # No fabricated share defaults
            'total_nav_dollars': np.nan, # No fabricated fund-level dollar totals
            'market_close': mkt_close,
            'market_status': market_status,
            'market_spread_bps': mkt_spread_bps,
            'held_vm_dollars': held_vm_dollars,
            'freight_vm_return': freight_vm_ret,
            'realized_pnl_dollars': realized_pnl_dollars,
            'collateral_interest_dollars': collateral_interest_dollars,
            'accrued_expenses_dollars': accrued_expenses_dollars,
            'usd_flow': usd_flow,
            'retained_contracts': retained_count,
            'new_contracts': new_count,
            'exited_contracts': exited_count,
            'reconciliation_status': reconciliation_status,
            'missing_notes': "; ".join(missing_notes),
            'provenance': prov_tag
        })
        
    df_tl = pd.DataFrame(timeline)
    
    # Chronological Split: Training Period (0 to 22) vs Evaluation Period (23 to 38)
    split_idx = 23
    df_train = df_tl.iloc[:split_idx]
    df_eval = df_tl.iloc[split_idx:]
    
    def compute_split_metrics(df_sub: pd.DataFrame) -> Dict[str, Any]:
        valid = df_sub.dropna(subset=['official_nav', 'official_perf_pct'])
        if len(valid) < 2:
            return {}
            
        # Compare Observed Retained Futures Return to Official Total Fund Performance
        ret_diffs = []
        for i in range(1, len(valid)):
            r_vm = valid.iloc[i]['freight_vm_return']
            r_off = valid.iloc[i]['official_perf_pct']
            ret_diffs.append(r_vm - r_off)
            
        ret_mae = np.mean(np.abs(ret_diffs)) * 100.0 if ret_diffs else 0.0
        ret_rmse = np.sqrt(np.mean(np.array(ret_diffs)**2)) * 100.0 if ret_diffs else 0.0
        
        fully_rec = (df_sub['reconciliation_status'] == 'FULLY_RECONCILED').sum()
        part_rec = (df_sub['reconciliation_status'] == 'PARTIAL_DISCLOSURE_UNRECONCILED').sum()
        miss_in = (df_sub['reconciliation_status'] == 'MISSING_INPUT').sum()
        
        return {
            'sessions_count': len(df_sub),
            'observed_sessions_count': len(valid),
            'vm_vs_official_perf_mae_pct': ret_mae,
            'vm_vs_official_perf_rmse_pct': ret_rmse,
            'fully_reconciled_count': fully_rec,
            'partial_unreconciled_count': part_rec,
            'missing_input_count': miss_in
        }
        
    train_metrics = compute_split_metrics(df_train)
    eval_metrics = compute_split_metrics(df_eval)
    full_metrics = compute_split_metrics(df_tl)
    
    return {
        'etf': etf_key.upper(),
        'timeline': df_tl,
        'train_metrics': train_metrics,
        'eval_metrics': eval_metrics,
        'full_metrics': full_metrics,
        'counts': {
            'fully_reconciled': fully_reconciled_count,
            'partial_unreconciled': partial_unreconciled_count,
            'missing_input': missing_input_count,
            'total_sessions': len(df_tl)
        },
        'train_dates': f"{df_train.iloc[0]['date']} to {df_train.iloc[-1]['date']}",
        'eval_dates': f"{df_eval.iloc[0]['date']} to {df_eval.iloc[-1]['date']}"
    }

if __name__ == '__main__':
    print("==========================================================================================")
    print("   STRICT ETF ACCOUNTING WATERFALL & CHRONOLOGICAL EVALUATION REPORT                       ")
    print("==========================================================================================")
    for k in ['bdry', 'bwet']:
        res = run_fund_level_nav_reconstruction(k)
        c = res['counts']
        print(f"\n==========================================")
        print(f"FUND: {res['etf']}")
        print(f"==========================================")
        print(f"Total Sessions                  : {c['total_sessions']}")
        print(f"  [FULLY_RECONCILED]             : {c['fully_reconciled']} (0.0% - zero false reconciliation claims)")
        print(f"  [PARTIAL_DISCLOSURE_UNRECONCILED]: {c['partial_unreconciled']}")
        print(f"  [MISSING_INPUT]                : {c['missing_input']}")
        
        print(f"\nChronological Split: Training Period ({res['train_dates']}):")
        tm = res['train_metrics']
        print(f"  Total Sessions                : {tm.get('sessions_count')}")
        print(f"  Observed Sessions Evaluated   : {tm.get('observed_sessions_count')}")
        print(f"  Observed Futures VM vs Off Perf MAE: {tm.get('vm_vs_official_perf_mae_pct', 0):.2f}%")
        print(f"  Observed Futures VM vs Off Perf RMSE: {tm.get('vm_vs_official_perf_rmse_pct', 0):.2f}%")
        
        print(f"\nChronological Split: Evaluation Period ({res['eval_dates']}):")
        em = res['eval_metrics']
        print(f"  Total Sessions                : {em.get('sessions_count')}")
        print(f"  Observed Sessions Evaluated   : {em.get('observed_sessions_count')}")
        print(f"  Observed Futures VM vs Off Perf MAE: {em.get('vm_vs_official_perf_mae_pct', 0):.2f}%")
        print(f"  Observed Futures VM vs Off Perf RMSE: {em.get('vm_vs_official_perf_rmse_pct', 0):.2f}%")
        
        print("\nDate-by-Date Sourced Waterfall Matrix (First 5 and Last 5 Sessions):")
        sample_df = pd.concat([res['timeline'].head(5), res['timeline'].tail(5)])
        for _, r in sample_df.iterrows():
            off_s = f"${r['official_nav']:.2f}" if not np.isnan(r['official_nav']) else "MISSING"
            mkt_s = f"${r['market_close']:.2f}" if not np.isnan(r['market_close']) else "MKT CLOSED"
            vm_s = f"${r['held_vm_dollars']:+,.0f}" if r['held_vm_dollars'] != 0 else "$0"
            print(f"  {r['date']} | Off NAV: {off_s:<8} | Mkt: {mkt_s:<10} | Retained VM: {vm_s:<12} | Status: {r['reconciliation_status']}")
            print(f"     -> Unreconciled Detail: {r['missing_notes']}")
            
    print("\n==========================================================================================")
    print("CANONICAL ACCEPTANCE CRITERION:")
    print("Partial accounting decomposition; not a validated NAV reconstruction; not trade-ready.")
    print("==========================================================================================")
