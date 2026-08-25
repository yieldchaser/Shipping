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

RATE_FIELDS = [
    ("vlcc_1y_tc", r"300[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("vlcc_3y_tc", r"300[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("suezmax_1y_tc", r"150[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("suezmax_3y_tc", r"150[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("aframax_1y_tc", r"110[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("aframax_3y_tc", r"110[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("lr1_1y_tc", r"75[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("lr1_3y_tc", r"75[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("mr_1y_tc", r"52[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("mr_3y_tc", r"52[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("handy_tanker_1y_tc", r"36[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("handy_tanker_3y_tc", r"36[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("capesize_1y_tc", r"180[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("capesize_3y_tc", r"180[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("panamax_1y_tc", r"76[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("panamax_3y_tc", r"76[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("supramax_1y_tc", r"58[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("supramax_3y_tc", r"58[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
    ("handysize_1y_tc", r"32[Kk]\s+1(?:yr|y)\s+TC\s+([\d,]+)"),
    ("handysize_3y_tc", r"32[Kk]\s+3(?:yr|y)\s+TC\s+([\d,]+)"),
]

def extract_rates_from_intermodal_md(md_path: Path):
    txt = md_path.read_text(encoding="utf-8", errors="ignore")
    
    # Extract Assessment Date from Tanker Chartering table header if present, else frontmatter
    date_iso = None
    m_tbl_date = re.search(r'Tanker\s+Chartering\s*\n\s*(\d{1,2})/(\d{1,2})/(\d{4})', txt, re.I)
    if m_tbl_date:
        d, m, y = m_tbl_date.group(1), m_tbl_date.group(2), m_tbl_date.group(3)
        date_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    else:
        date_match = re.search(r'date:\s*"([^"]+)"', txt)
        if date_match:
            date_raw = date_match.group(1).strip()
            dmy = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_raw)
            if dmy:
                date_iso = f"{dmy.group(3)}-{dmy.group(2).zfill(2)}-{dmy.group(1).zfill(2)}"
            else:
                date_iso = date_raw
        else:
            date_iso = "2026-08-14"

    row = {"date": date_iso, "source": "intermodal"}
    for field_name, pat in RATE_FIELDS:
        m = re.search(pat, txt, re.I)
        if m:
            row[field_name] = int(m.group(1).replace(",", ""))
        else:
            row[field_name] = None

    return row

def main():
    print("=" * 80)
    print("  INTERMODAL TIME CHARTER RATES EXTRACTOR & UPDATER")
    print("=" * 80)
    
    if not CSV_PATH.exists():
        print(f"[!] CSV not found: {CSV_PATH}")
        return
        
    df_existing = pd.read_csv(CSV_PATH)
    # Remove any invalid duplicate fallback rows inserted with publication dates rather than assessment dates
    df_existing = df_existing[~df_existing["date"].isin(["2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-19"])]
    print(f"Existing Intermodal TC records (cleaned base): {len(df_existing)}")
    
    extracted_rows = []
    for md_file in sorted(REPORTS_DIR.glob("*intermodal*.md")):
        row = extract_rates_from_intermodal_md(md_file)
        if all(v is not None for k, v in row.items() if k != "date"):
            print(f"  [+] Extracted valid rates for date: {row['date']} from {md_file.name}")
            extracted_rows.append(row)
        else:
            missing = [k for k, v in row.items() if v is None]
            print(f"  [!] Missing fields for {md_file.name}: {missing}")
            
    df_new = pd.DataFrame(extracted_rows)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df_combined = df_combined.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    
    df_combined.to_csv(CSV_PATH, index=False)
    print(f"\n[OK] Successfully updated {CSV_PATH.name} to {len(df_combined)} chronologically sorted records.")

if __name__ == "__main__":
    main()
