import os
import csv
import re
import json
import hashlib
from datetime import datetime, timedelta

BDRY_DAILY = 'data/etf/bdry_holdings.csv'
BDRY_HIST = 'data/etf/bdry_holdings_history.csv'

BWET_DAILY = 'data/etf/bwet_holdings.csv'
BWET_HIST = 'data/etf/bwet_holdings_history.csv'

STATE_PATH = 'data/manifests/daily_holdings_hash_state.json'
REAPPEND_WINDOW_DAYS = 10


def load_hash_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def save_hash_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, sort_keys=True)


def snapshot_content_hash(rows):
    """Stable hash over the VALUE columns of a snapshot (date column excluded)."""
    canonical = '\n'.join(
        '|'.join(cell.strip().lower() for cell in row) for row in rows
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def append_daily_to_history(daily_path, hist_path, hash_state):
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
    undated_value_rows = []

    with open(daily_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        daily_header = next(reader, None)
        for row in reader:
            if not row or len(row) < 2:
                continue
            # Handle daily CSV row format with strict ISO date validation
            is_date_col = bool(re.match(r'^\d{4}-\d{2}-\d{2}$', row[0].strip()))
            if is_date_col:
                row_date = row[0].strip()
                contract_name = row[1].strip()
            else:
                row_date = today_str
                contract_name = row[0].strip()
                # Track value payload of undated rows so a stale snapshot can never
                # be re-stamped as fresh "today" history within the guard window.
                undated_value_rows.append(row)

            key = (row_date, contract_name.lower())
            if key not in existing_records:
                formatted_row = [row_date] + (row[1:] if is_date_col else row)
                new_rows.append(formatted_row)
                existing_records.add(key)

    if undated_value_rows and new_rows:
        content_hash = snapshot_content_hash(undated_value_rows)
        fund_state = hash_state.get(os.path.basename(hist_path), {})
        last_seen = fund_state.get(content_hash)
        if last_seen:
            try:
                age_days = (datetime.now() - datetime.strptime(last_seen, '%Y-%m-%d')).days
            except ValueError:
                age_days = None
            if age_days is not None and age_days <= REAPPEND_WINDOW_DAYS:
                print(
                    f"Skipped {hist_path}: identical undated snapshot already stamped "
                    f"{last_seen} ({age_days}d ago); refusing to fabricate duplicate "
                    f"history under {today_str}."
                )
                return 0
        fund_state[content_hash] = today_str
        # Prune hashes older than the guard window
        cutoff = (datetime.now() - timedelta(days=REAPPEND_WINDOW_DAYS)).strftime('%Y-%m-%d')
        hash_state[os.path.basename(hist_path)] = {
            h: d for h, d in fund_state.items() if d >= cutoff
        }
        save_hash_state(hash_state)

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
    state = load_hash_state()
    b1 = append_daily_to_history(BDRY_DAILY, BDRY_HIST, state)
    b2 = append_daily_to_history(BWET_DAILY, BWET_HIST, state)
    print("Holdings History Auto-Sync Completed Successfully!")
