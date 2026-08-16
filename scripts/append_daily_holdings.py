import os
import csv
import re
from datetime import datetime

BDRY_DAILY = 'data/etf/bdry_holdings.csv'
BDRY_HIST = 'data/etf/bdry_holdings_history.csv'

BWET_DAILY = 'data/etf/bwet_holdings.csv'
BWET_HIST = 'data/etf/bwet_holdings_history.csv'

def append_daily_to_history(daily_path, hist_path):
    if not os.path.exists(daily_path) or not os.path.exists(hist_path):
        print(f"Skipping {daily_path} / {hist_path}: File not found.")
        return 0

    # Load existing history dates & rows to prevent duplicates
    existing_records = set()
    with open(hist_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2:
                # Key: (date, contract_name)
                existing_records.add((row[0].strip(), row[1].strip().lower()))

    # Read current daily snapshot
    today_str = datetime.now().strftime('%Y-%m-%d')
    new_rows = []

    with open(daily_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        daily_header = next(reader, None)
        for row in reader:
            if not row or len(row) < 2:
                continue
            # Handle daily CSV row format with strict ISO date validation
            is_date_col = bool(re.match(r'^\d{4}-\d{2}-\d{2}$', row[0].strip()))
            row_date = row[0].strip() if is_date_col else today_str
            contract_name = row[1].strip() if is_date_col else row[0].strip()

            key = (row_date, contract_name.lower())
            if key not in existing_records:
                formatted_row = [row_date] + (row[1:] if is_date_col else row)
                new_rows.append(formatted_row)
                existing_records.add(key)

    if new_rows:
        with open(hist_path, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)
        print(f"Appended {len(new_rows)} new historical records to {hist_path}")
    else:
        print(f"No new records to append for {hist_path} (Already up to date).")

    return len(new_rows)

if __name__ == '__main__':
    print("=== AUTOMATED DAILY HOLDINGS HISTORY APPEND & AUDIT ===")
    b1 = append_daily_to_history(BDRY_DAILY, BDRY_HIST)
    b2 = append_daily_to_history(BWET_DAILY, BWET_HIST)
    print("Holdings History Auto-Sync Completed Successfully!")
