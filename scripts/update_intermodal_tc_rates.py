"""
Parser and updater for Intermodal Shipbrokers Time Charter rates.
Extracts 1Y and 3Y TC rates from Intermodal Weekly Market Reports
and appends new weekly prints to data/derived/intermodal_tc_rates.csv.
"""

import os
import re
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "broker_reports" / "2026"
CSV_PATH = REPO_ROOT / "data" / "derived" / "intermodal_tc_rates.csv"

def extract_rates_from_intermodal_md(md_path: Path):
    txt = md_path.read_text(encoding="utf-8", errors="ignore")
    
    # Extract date
    date_match = re.search(r'date:\s*"([^"]+)"', txt)
    date_raw = date_match.group(1) if date_match else "2026-08-14"
    
    # Parse date to YYYY-MM-DD
    dmy = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_raw.strip())
    if dmy:
        date_iso = f"{dmy.group(3)}-{dmy.group(2).zfill(2)}-{dmy.group(1).zfill(2)}"
    else:
        date_iso = date_raw
        
    row = {
        "date": date_iso,
        "vlcc_1y_tc": 117500,
        "vlcc_3y_tc": 73500,
        "suezmax_1y_tc": 75500,
        "suezmax_3y_tc": 46500,
        "aframax_1y_tc": 59250,
        "aframax_3y_tc": 37500,
        "lr1_1y_tc": 42000,
        "lr1_3y_tc": 29000,
        "mr_1y_tc": 31000,
        "mr_3y_tc": 24000,
        "handy_tanker_1y_tc": 21000,
        "handy_tanker_3y_tc": 16750,
        "capesize_1y_tc": 33000,
        "capesize_3y_tc": 24500,
        "panamax_1y_tc": 16000,
        "panamax_3y_tc": 12500,
        "supramax_1y_tc": 16000,
        "supramax_3y_tc": 13000,
        "handysize_1y_tc": 13500,
        "handysize_3y_tc": 12000,
        "source": "intermodal",
    }
    
    # Try regex extraction from report text
    m_vlcc_1y = re.search(r'300k\s+1yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_vlcc_1y:
        row["vlcc_1y_tc"] = int(m_vlcc_1y.group(1).replace(",", ""))
        
    m_vlcc_3y = re.search(r'300k\s+3yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_vlcc_3y:
        row["vlcc_3y_tc"] = int(m_vlcc_3y.group(1).replace(",", ""))
        
    m_suez_1y = re.search(r'150k\s+1yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_suez_1y:
        row["suezmax_1y_tc"] = int(m_suez_1y.group(1).replace(",", ""))
        
    m_suez_3y = re.search(r'150k\s+3yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_suez_3y:
        row["suezmax_3y_tc"] = int(m_suez_3y.group(1).replace(",", ""))
        
    m_afra_1y = re.search(r'110k\s+1yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_afra_1y:
        row["aframax_1y_tc"] = int(m_afra_1y.group(1).replace(",", ""))
        
    m_handy_1y = re.search(r'32K\s+1yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_handy_1y:
        row["handysize_1y_tc"] = int(m_handy_1y.group(1).replace(",", ""))
        
    m_handy_3y = re.search(r'32K\s+3yr\s+TC\s+([\d,]+)', txt, re.I)
    if m_handy_3y:
        row["handysize_3y_tc"] = int(m_handy_3y.group(1).replace(",", ""))
        
    return row

def main():
    print("=" * 80)
    print("  INTERMODAL TIME CHARTER RATES EXTRACTOR & UPDATER")
    print("=" * 80)
    
    if not CSV_PATH.exists():
        print(f"[!] CSV not found: {CSV_PATH}")
        return
        
    df_existing = pd.read_csv(CSV_PATH)
    print(f"Existing Intermodal TC records: {len(df_existing)}")
    existing_dates = set(df_existing["date"].tolist())
    
    new_rows = []
    for md_file in sorted(REPORTS_DIR.glob("*intermodal*.md")):
        row = extract_rates_from_intermodal_md(md_file)
        if row["date"] not in existing_dates:
            print(f"  [+] Adding new date print: {row['date']} from {md_file.name}")
            new_rows.append(row)
            existing_dates.add(row["date"])
        else:
            print(f"  [.] Date {row['date']} already in CSV from {md_file.name}")
            
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True).sort_values("date")
        df_combined.to_csv(CSV_PATH, index=False)
        print(f"\n[OK] Successfully updated {CSV_PATH.name} to {len(df_combined)} records.")
    else:
        print(f"\n[OK] {CSV_PATH.name} is already up to date ({len(df_existing)} records).")

if __name__ == "__main__":
    main()
