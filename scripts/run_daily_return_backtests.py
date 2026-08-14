"""
Daily Dollar-P&L Decomposition & Governance Ledger
==================================================
Performs strict accounting decomposition of daily ETF holdings:

1. Variation Margin on Retained Contracts:
   futures_vm(t) = sum_{i in retained} (prior_lots_{i, t-1} * authoritative_multiplier_i * (P_{i, t} - P_{i, t-1}))

2. Simulated Fund Return on Total Net Assets:
   simulated_fund_return(t) = futures_vm(t) / prior_total_fund_NAV(t-1)

3. Strict Governance Labeling Standards:
   - RECONCILED: Permitted ONLY when:
       * 100% mark and contract coverage is verified.
       * Zero unresolved opened/closed contracts or roll residual.
       * Complete daily custody cash, fee, interest, and creation/redemption inputs are observed.
   - PARTIAL_SCALING_ONLY: Assigned when dated total fund NAV is observed, but cash/fee vouchers or roll fills remain unobserved.
   - DESCRIPTIVE_UNRECONCILED: Assigned to all interim daily sessions lacking total fund NAV.
   - Replay status remains strictly UNRECONCILED.
"""

import os
import hashlib
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from contract_spec_registry import resolve_contract_spec, get_authoritative_multiplier, UnknownContractSpecError

def run_daily_dollar_decomposition(fund: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    h_file = f'data/etf/{fund.lower()}_holdings_history.csv'
    f_file = f'data/etf/{fund.upper()}_flows.csv'
    l_file = f'data/etf/{fund.lower()}_liquidity.csv'
    cftc_file = f'data/cftc_statements/parsed/{fund.lower()}_monthly_cftc_ledger.csv'
    
    df_h = pd.read_csv(h_file)
    df_f = pd.read_csv(f_file)
    df_l = pd.read_csv(l_file)
    df_cftc = pd.read_csv(cftc_file) if os.path.exists(cftc_file) else pd.DataFrame()
    
    # Dates
    df_h['date'] = pd.to_datetime(df_h['date']).dt.strftime('%Y-%m-%d')
    df_f['date'] = pd.to_datetime(df_f['date']).dt.strftime('%Y-%m-%d')
    df_l['date'] = pd.to_datetime(df_l['date']).dt.strftime('%Y-%m-%d')
    
    # Numeric cleaning
    df_h['Lots'] = pd.to_numeric(df_h['Lots'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)
    df_h['Price'] = pd.to_numeric(df_h['Price'].astype(str).str.replace('$', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)
    
    if fund.upper() == 'BDRY':
        df_h_fut = df_h[df_h['Name'].str.contains('Capesize|Panamax|Supramax', case=False, na=False)].copy()
    else:
        df_h_fut = df_h[df_h['Name'].str.contains('VLCC|Suezmax|TD3C|TD20', case=False, na=False)].copy()
        
    h_dates = sorted(df_h_fut['date'].unique())
    
    nav_sh_map = dict(zip(df_f['date'], df_f['nav']))
    mkt_map = dict(zip(df_l['date'], df_l['close']))
    
    cftc_nav_map = {}
    cftc_shares_map = {}
    if not df_cftc.empty:
        for _, r in df_cftc.iterrows():
            p_dt = pd.to_datetime(r['period_ended'], errors='coerce', format='mixed')
            if pd.notna(p_dt):
                d_str = p_dt.strftime('%Y-%m-%d')
                if pd.notna(r['closing_nav_dollars']):
                    cftc_nav_map[d_str] = float(r['closing_nav_dollars'])
                if pd.notna(r['shares_outstanding']):
                    cftc_shares_map[d_str] = int(r['shares_outstanding'])
                    
    # Form 10-Q March 31, 2026 fixture
    if fund.upper() == 'BDRY':
        cftc_nav_map['2026-03-31'] = 43139969.00
        cftc_shares_map['2026-03-31'] = 4275040
    else:
        cftc_nav_map['2026-03-31'] = 56888799.00
        cftc_shares_map['2026-03-31'] = 475100
        
    records = []
    
    for idx in range(1, len(h_dates)):
        prev_date = h_dates[idx - 1]
        curr_date = h_dates[idx]
        
        # 1. Official per-share NAV return
        nav_sh_prev = nav_sh_map.get(prev_date, np.nan)
        nav_sh_curr = nav_sh_map.get(curr_date, np.nan)
        
        if pd.notna(nav_sh_prev) and pd.notna(nav_sh_curr) and nav_sh_prev > 0:
            r_official_pct = ((nav_sh_curr - nav_sh_prev) / nav_sh_prev) * 100.0
        else:
            r_official_pct = np.nan
            
        # 2. Prior total fund NAV ($)
        prior_total_fund_nav = cftc_nav_map.get(prev_date, np.nan)
        if np.isnan(prior_total_fund_nav) and prev_date in cftc_shares_map and pd.notna(nav_sh_prev):
            prior_total_fund_nav = nav_sh_prev * cftc_shares_map[prev_date]
            
        # 3. Explicit Roll Decomposition
        h_prev = df_h_fut[df_h_fut['date'] == prev_date].copy()
        h_curr = df_h_fut[df_h_fut['date'] == curr_date].copy()
        
        prev_names = set(h_prev['Name'])
        curr_names = set(h_curr['Name'])
        
        retained_names = prev_names.intersection(curr_names)
        closed_names = prev_names.difference(curr_names)
        opened_names = curr_names.difference(prev_names)
        
        futures_vm_dollars = 0.0
        retained_base_notional = 0.0
        
        for r_name in retained_names:
            row_p = h_prev[h_prev['Name'] == r_name].iloc[0]
            row_c = h_curr[h_curr['Name'] == r_name].iloc[0]
            
            p_prev = float(row_p['Price'])
            p_curr = float(row_c['Price'])
            q_prev = float(row_p['Lots'])
            
            mult = get_authoritative_multiplier(
                identifier=r_name,
                ticker=str(row_p.get('Ticker', '')),
                cusip=str(row_p.get('CUSIP', '')),
                fund=fund
            )
            
            contract_vm = q_prev * mult * (p_curr - p_prev)
            contract_base_notional = q_prev * mult * p_prev
            
            futures_vm_dollars += contract_vm
            retained_base_notional += contract_base_notional
            
        # 4. Strict Status Determination
        # A session is RECONCILED iff:
        # - 100% mark coverage
        # - 0 opened/closed contracts (no roll residual)
        # - observed daily cash vouchers, fees, interest, and AP flows (unobserved at daily level)
        daily_cash_vouchers_observed = False  # Blocked
        has_roll_transition = (len(closed_names) > 0 or len(opened_names) > 0)
        
        if pd.notna(prior_total_fund_nav) and prior_total_fund_nav > 0:
            simulated_fund_ret_pct = (futures_vm_dollars / prior_total_fund_nav) * 100.0
            if daily_cash_vouchers_observed and not has_roll_transition:
                reconciliation_status = 'RECONCILED'
            else:
                reconciliation_status = 'PARTIAL_SCALING_ONLY'
        else:
            simulated_fund_ret_pct = np.nan
            reconciliation_status = 'DESCRIPTIVE_UNRECONCILED'
            
        notional_proxy_ret_pct = (futures_vm_dollars / retained_base_notional * 100.0) if retained_base_notional > 0 else np.nan
        notional_proxy_diff_pct = (notional_proxy_ret_pct - r_official_pct) if (pd.notna(notional_proxy_ret_pct) and pd.notna(r_official_pct)) else np.nan
        
        records.append({
            'fund': fund,
            'prev_date': prev_date,
            'date': curr_date,
            'reconciliation_status': reconciliation_status,
            'nav_sh_prev': nav_sh_prev,
            'nav_sh_curr': nav_sh_curr,
            'r_official_pct': r_official_pct,
            'prior_total_fund_nav_dollars': prior_total_fund_nav,
            'futures_vm_retained_dollars': futures_vm_dollars,
            'simulated_fund_ret_pct': simulated_fund_ret_pct,
            'notional_proxy_ret_pct': notional_proxy_ret_pct,
            'notional_proxy_diff_pct': notional_proxy_diff_pct,
            'retained_contracts_count': len(retained_names),
            'closed_contracts_count': len(closed_names),
            'opened_contracts_count': len(opened_names)
        })
        
    df_res = pd.DataFrame(records)
    
    total_sessions = len(df_res)
    reconciled_count = len(df_res[df_res['reconciliation_status'] == 'RECONCILED'])
    partial_scaling_count = len(df_res[df_res['reconciliation_status'] == 'PARTIAL_SCALING_ONLY'])
    unreconciled_count = len(df_res[df_res['reconciliation_status'] == 'DESCRIPTIVE_UNRECONCILED'])
    
    valid_diffs = df_res['notional_proxy_diff_pct'].dropna()
    descriptive_proxy_mae = float(np.mean(np.abs(valid_diffs))) if not valid_diffs.empty else None
    
    summary_report = {
        'fund': fund,
        'total_disclosure_sessions': total_sessions,
        'genuinely_reconciled_sessions_count': reconciled_count,
        'partial_scaling_sessions_count': partial_scaling_count,
        'unreconciled_interim_sessions_count': unreconciled_count,
        'descriptive_unreconciled_notional_proxy_mae_pct': round(descriptive_proxy_mae, 3) if descriptive_proxy_mae else None,
        'tracking_accuracy_verdict': "NO_ACCURACY_VERDICT_ISSUED (Daily cash/shares unobserved; daily replay status strictly UNRECONCILED)"
    }
    
    return df_res, summary_report

def run_all():
    print("==========================================================================")
    print("     DAILY DOLLAR-P&L DECOMPOSITION & GOVERNANCE ACCOUNTING REPORT        ")
    print("==========================================================================")
    
    for fund in ['BDRY', 'BWET']:
        df_res, rep = run_daily_dollar_decomposition(fund)
        print(f"--- FUND: {fund} Accounting Status ---")
        print(f"  Total Disclosure Sessions     : {rep['total_disclosure_sessions']}")
        print(f"  Genuinely Reconciled Sessions : {rep['genuinely_reconciled_sessions_count']} (0 due to unobserved daily vouchers/roll fills)")
        print(f"  Partial Scaling Sessions      : {rep['partial_scaling_sessions_count']} (Dated total NAV observed; unobserved cash vouchers)")
        print(f"  Unreconciled Interim Sessions : {rep['unreconciled_interim_sessions_count']} (Daily cash/shares unobserved)")
        print(f"  Descriptive Notional Proxy MAE: {rep['descriptive_unreconciled_notional_proxy_mae_pct']}%/day (Informational only)")
        print(f"  Tracking Accuracy Verdict     : {rep['tracking_accuracy_verdict']}\n")

if __name__ == '__main__':
    run_all()
