"""
CFTC Rule 4.22(h) Monthly Statement Parser & Structured Ledger Builder
======================================================================
Parses official monthly Commodity Pool Operator (CPO) account statements
for Breakwave Dry Bulk Shipping ETF (BDRY) and Breakwave Tanker Shipping ETF (BWET).

Extracts and mathematically validates:
- Opening Net Asset Value (NAV)
- Share sales / additions ($)
- Share redemptions / subtractions ($)
- Net share capital flow ($)
- Gross Interest Income ($)
- Itemized operating expenses & brokerage commissions ($)
- Fee waivers & sponsor absorbed expenses ($)
- Net Expenses & Net Investment Income / (Loss) ($)
- Realized Gain / (Loss) on Futures ($)
- Change in Unrealized Appreciation / Depreciation on Futures ($)
- Total Net Realized & Unrealized P&L ($)
- Net Income / (Loss) ($)
- Ending Net Asset Value ($)
- Month-End Shares Outstanding
- Month-End NAV per Share ($/share)

Primary Sources:
- Amplify BDRY Fund Documents: https://amplifyetfs.com/bdry-fund-documents/
- Amplify BWET Fund Documents: https://amplifyetfs.com/bwet-fund-documents/
"""

import os
import re
import json
import hashlib
import anydoc
import pypdf
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

RAW_PDF_DIR_BDRY = 'data/cftc_statements/raw_pdf/BDRY'
RAW_PDF_DIR_BWET = 'data/cftc_statements/raw_pdf/BWET'
PARSED_DIR = 'data/cftc_statements/parsed'

os.makedirs(PARSED_DIR, exist_ok=True)

def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def clean_num(val_str: Optional[str]) -> Optional[float]:
    if val_str is None:
        return None
    s = val_str.replace('$', '').replace(',', '').strip()
    if s in ['-', '—', '', '–']:
        return 0.0
    if s.startswith('(') and s.endswith(')'):
        return -float(s[1:-1])
    try:
        return float(s)
    except ValueError:
        return None

def parse_single_pdf(filepath: str, fund_name: str, url: str) -> Dict[str, Any]:
    full_text = ""
    try:
        reader = pypdf.PdfReader(filepath)
        full_text = "\n".join([page.extract_text() or "" for page in reader.pages])
    except Exception:
        pass

    if not full_text or len(full_text.strip()) < 50:
        try:
            full_text = anydoc.to_markdown(filepath)
        except Exception:
            full_text = ""
    
    # 1. Period Ended Date
    m_period = re.search(r'For the Month Ended\s*\|?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})', full_text, re.IGNORECASE)
    if not m_period:
        m_period = re.search(r'Month Ended\s*\|?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})', full_text, re.IGNORECASE)
    period_str = m_period.group(1).strip() if m_period else os.path.basename(filepath).replace(f'{fund_name}_', '').replace('.pdf', '')
    
    # 2. Extract Numbers using precise regex with flexible spacing
    def find_amount(pattern: str, text: str, default: Optional[float] = 0.0) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = clean_num(m.group(1))
            return val if val is not None else default
        return default

    # Interest Income
    interest = find_amount(r'Interest[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    
    # Itemized Expenses
    sponsor_fee = find_amount(r'Sponsor Fee[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    cta_fee = find_amount(r'CTA Fee[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    brokerage_comm = find_amount(r'Brokerage Commissions[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    admin_custody_fee = find_amount(r'Admin/Accounting/Custodian/Transfer Agent Fees[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    
    # Total Expenses & Fee Waivers
    tot_exp = find_amount(r'Total Expenses[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    waiver_cta = find_amount(r'Less:\s*Waiver of CTA Fee[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    expenses_absorbed = find_amount(r'Less:\s*Expenses absorbed[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    
    # Net Expenses
    net_exp = find_amount(r'Net Expenses[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=None)
    if net_exp is None and tot_exp is not None:
        net_exp = tot_exp - abs(waiver_cta or 0.0) - abs(expenses_absorbed or 0.0)
        
    # Net Investment Income / (Loss)
    nii = find_amount(r'Net Investment Income\s*\([^\)]+\)[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=None)
    if nii is None and interest is not None and net_exp is not None:
        nii = interest - net_exp
        
    # Realized Gain / Loss on Futures
    realized_futures = find_amount(r'Net Realized Gain\s*\([^\)]+\)\s*on\s*Futures Contracts[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=None)
    if realized_futures is None:
        realized_futures = find_amount(r'Futures Contracts[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
        
    # Unrealized Gain / Loss Delta on Futures
    unrealized_delta = find_amount(r'Change in Net Unrealized Appreciation/Depreciation[^\d\(\)\-]*?([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    
    # Net Realized & Unrealized P&L
    tot_futures_pnl = find_amount(r'Net Realized and Unrealized Gain\s*\([^\)]+\)[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=None)
    if tot_futures_pnl is None and realized_futures is not None and unrealized_delta is not None:
        tot_futures_pnl = realized_futures + unrealized_delta
        
    # Net Income / (Loss)
    net_income = find_amount(r'Net Income\s*\([^\)]+\)[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=None)
    if net_income is None and nii is not None and tot_futures_pnl is not None:
        net_income = nii + tot_futures_pnl
        
    # Opening NAV & Ending NAV
    nav_matches = re.findall(r'Net Asset Value End of Period\s*\|?\s*[\d/]+\s*\|?\s*\$?\s*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\))', full_text, re.IGNORECASE)
    if len(nav_matches) >= 2:
        open_nav = clean_num(nav_matches[0])
        closing_nav = clean_num(nav_matches[1])
    elif len(nav_matches) == 1:
        open_nav = None
        closing_nav = clean_num(nav_matches[0])
    else:
        open_nav = None
        closing_nav = None
        
    # Sales & Redemptions of Shares
    sales = find_amount(r'Sales of Shares[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    redemptions = find_amount(r'Redemption of Shares[^\d\(\)\-\n]*([\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)|-)', full_text, default=0.0)
    net_share_activity = (sales or 0.0) + (redemptions or 0.0)
    
    # Month-End Shares Outstanding
    m_shares = re.search(r'Shares Outstanding[^\d\n]*([\d,]+(?:\.\d+)?)', full_text, re.IGNORECASE)
    shares_out = int(clean_num(m_shares.group(1))) if m_shares and clean_num(m_shares.group(1)) is not None else None
    
    # Month-End NAV per Share
    m_nav_sh = re.search(r'(?:Net Asset )?Value Per Share[^\d\n]*([\d,]+(?:\.\d+)?)', full_text, re.IGNORECASE)
    nav_per_share = clean_num(m_nav_sh.group(1)) if m_nav_sh else None
    
    # Mathematical Balances
    # 1. Total Net Assets Balance: Closing = Opening + Sales + Redemptions + Net Income
    balance_identity_err = None
    balance_identity_valid = False
    if open_nav is not None and closing_nav is not None and net_income is not None:
        reconstructed_ending_nav = open_nav + net_share_activity + net_income
        balance_identity_err = round(reconstructed_ending_nav - closing_nav, 2)
        balance_identity_valid = (abs(balance_identity_err) < 2.0)
        
    # 2. Per-Share NAV Balance: NAV/share = Closing NAV / Shares Outstanding
    share_identity_err = None
    share_identity_valid = False
    if closing_nav is not None and shares_out is not None and shares_out > 0 and nav_per_share is not None:
        calc_nav_sh = closing_nav / shares_out
        share_identity_err = round(calc_nav_sh - nav_per_share, 4)
        share_identity_valid = (abs(share_identity_err) < 0.02)
        
    return {
        'fund': fund_name,
        'period_ended': period_str,
        'source_url': url,
        'local_file_path': filepath,
        'sha256_checksum': calculate_sha256(filepath),
        'file_size_bytes': os.path.getsize(filepath),
        'opening_nav_dollars': open_nav,
        'sales_of_shares_dollars': sales,
        'redemptions_of_shares_dollars': redemptions,
        'net_share_activity_dollars': net_share_activity,
        'interest_income_dollars': interest,
        'sponsor_fee_dollars': sponsor_fee,
        'cta_fee_dollars': cta_fee,
        'brokerage_commissions_dollars': brokerage_comm,
        'admin_custody_fees_dollars': admin_custody_fee,
        'total_expenses_dollars': tot_exp,
        'cta_fee_waiver_dollars': waiver_cta,
        'expenses_absorbed_dollars': expenses_absorbed,
        'net_expenses_dollars': net_exp,
        'net_investment_income_dollars': nii,
        'realized_futures_pnl_dollars': realized_futures,
        'unrealized_futures_pnl_delta_dollars': unrealized_delta,
        'net_futures_pnl_dollars': tot_futures_pnl,
        'net_income_loss_dollars': net_income,
        'closing_nav_dollars': closing_nav,
        'shares_outstanding': shares_out,
        'nav_per_share': nav_per_share,
        'balance_identity_err_dollars': balance_identity_err,
        'balance_identity_valid': balance_identity_valid,
        'share_identity_err_dollars': share_identity_err,
        'share_identity_valid': share_identity_valid
    }

def parse_date_key(period_str: str) -> datetime:
    s = period_str.replace('-', ' ').strip()
    s = re.sub(r'\s+', ' ', s)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%B %Y", "%b %Y", "%Y %m %d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime(1970, 1, 1)

def process_all_statements() -> Dict[str, pd.DataFrame]:
    with open('scratch/statement_urls.json', 'r') as f:
        urls_meta = json.load(f)
        
    url_map = {}
    for f_name in ['BDRY', 'BWET']:
        for item in urls_meta[f_name]:
            fname = os.path.basename(item['url'])
            url_map[fname] = item['url']
            
    results = {}
    
    for fund, dir_path in [('BDRY', RAW_PDF_DIR_BDRY), ('BWET', RAW_PDF_DIR_BWET)]:
        records = []
        files = sorted([f for f in os.listdir(dir_path) if f.endswith('.pdf')])
        print(f"Parsing {len(files)} raw statement PDFs for {fund}...")
        
        for fname in files:
            fp = os.path.join(dir_path, fname)
            u = url_map.get(fname, f"https://amplifyetfs.com/wp-content/uploads/files/{fund}/Account_Statements/{fname}")
            rec = parse_single_pdf(fp, fund, u)
            records.append(rec)
            
        records = sorted(records, key=lambda r: parse_date_key(r['period_ended']))
        df = pd.DataFrame(records)
        csv_path = os.path.join(PARSED_DIR, f"{fund.lower()}_monthly_cftc_ledger.csv")
        json_path = os.path.join(PARSED_DIR, f"{fund.lower()}_monthly_cftc_ledger.json")
        
        df.to_csv(csv_path, index=False)
        with open(json_path, 'w') as jf:
            json.dump(records, jf, indent=2)
            
        results[fund] = df
        print(f"  -> Generated {csv_path} ({len(df)} rows, chronologically sorted)")
        
    return results

if __name__ == '__main__':
    dfs = process_all_statements()
    print("\n==========================================================================")
    print("      CFTC RULE 4.22(h) MONTHLY RECONSTRUCTION AUDIT SUMMARY              ")
    print("==========================================================================")
    for fund, df in dfs.items():
        val_balance = df['balance_identity_valid'].sum()
        val_shares = df['share_identity_valid'].sum()
        tot = len(df)
        print(f"Fund: {fund:<5} | Total Statements: {tot:<3} | Balance Identity Valid: {val_balance}/{tot} ({val_balance/tot*100:.1f}%) | Share Identity Valid: {val_shares}/{tot} ({val_shares/tot*100:.1f}%)")
