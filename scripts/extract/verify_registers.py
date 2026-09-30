import os
import glob
import csv
import json
import re

def verify():
    # 1. Check disk CSVs vs EXTRACTION_REGISTER.json
    with open('data/extracted/EXTRACTION_REGISTER.json', 'r', encoding='utf-8') as f:
        reg_json = json.load(f)

    json_inventory = {item['file']: item['rows'] for item in reg_json['master_series_inventory']}

    series_dir = 'data/extracted/series'
    csv_files = sorted(glob.glob(os.path.join(series_dir, '*.csv')))

    mismatches = []
    disk_total = 0
    for p in csv_files:
        fname = os.path.basename(p)
        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            try:
                next(reader)
            except StopIteration:
                pass
            rows = sum(1 for _ in reader)
        disk_total += rows
        if fname not in json_inventory:
            mismatches.append(f"Missing in JSON: {fname}")
        elif json_inventory[fname] != rows:
            mismatches.append(f"Row mismatch in JSON for {fname}: disk={rows} vs json={json_inventory[fname]}")

    print(f"Disk CSV count: {len(csv_files)}, Disk logical rows: {disk_total:,}")
    print(f"JSON total_master_stacked_rows: {reg_json['total_master_stacked_rows']:,}")
    print(f"JSON total_series_csvs: {reg_json['total_series_csvs']}")
    print(f"JSON master_series_inventory items: {len(reg_json['master_series_inventory'])}")

    # 2. Check disk CSVs vs docs/EXTRACTION_REGISTER.md
    with open('docs/EXTRACTION_REGISTER.md', 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Check for control characters
    ctrl_chars = [c for c in md_text if ord(c) < 32 and c not in '\n\r\t']
    print(f"Control characters in MD: {len(ctrl_chars)}")

    # Check emojis in MD and JSON
    def has_emoji(text):
        return bool(re.search(r'[\U00010000-\U0010ffff]', text))

    print(f"Emojis in MD: {has_emoji(md_text)}")
    print(f"Emojis in JSON: {has_emoji(json.dumps(reg_json))}")

    # Check Section 2 rows in MD
    sec2_rows = {}
    for line in md_text.splitlines():
        if line.startswith('| [') and '.csv' in line:
            parts = [p.strip() for p in line.split('|')]
            fname = re.search(r'\[([^\]]+)\]', parts[1]).group(1)
            row_str = parts[3].replace(',', '')
            sec2_rows[fname] = int(row_str)

    md_mismatches = []
    for fname, rows in json_inventory.items():
        if fname.endswith('.csv'):
            if fname not in sec2_rows:
                md_mismatches.append(f"Missing in MD: {fname}")
            elif sec2_rows[fname] != rows:
                md_mismatches.append(f"Row mismatch in MD for {fname}: json={rows} vs md={sec2_rows[fname]}")

    print(f"MD Section 2 CSV count: {len(sec2_rows)}")
    print(f"Mismatches with JSON: {len(mismatches)}")
    print(f"Mismatches with MD: {len(md_mismatches)}")

    if not mismatches and not md_mismatches and not ctrl_chars and not has_emoji(md_text):
        print("ALL VERIFICATION CHECKS PASSED PERFECTLY (100.0% MATCH)!")
    else:
        print("ISSUES FOUND:")
        for m in mismatches + md_mismatches:
            print(" ", m)

if __name__ == '__main__':
    verify()
