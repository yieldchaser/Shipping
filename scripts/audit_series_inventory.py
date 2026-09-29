"""Audit the entire series inventory in data/extracted/series/ and compare with docs/EXTRACTION_REGISTER.md."""
import os
import re
from pathlib import Path

SERIES_DIR = Path("data/extracted/series")
REGISTER_PATH = Path("docs/EXTRACTION_REGISTER.md")

def count_rows(file_path):
    count = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for _ in f:
            count += 1
    return max(0, count - 1)  # subtract header

def main():
    if not SERIES_DIR.exists():
        print(f"Error: {SERIES_DIR} does not exist.")
        return

    csv_files = sorted(list(SERIES_DIR.glob("*.csv")))
    xlsx_files = sorted(list(SERIES_DIR.glob("*.xlsx")))
    
    total_csv_rows = 0
    disk_series = {}
    for p in csv_files:
        rows = count_rows(p)
        disk_series[p.name] = rows
        total_csv_rows += rows

    print(f"Found {len(csv_files)} CSV series and {len(xlsx_files)} XLSX series on disk.")
    print(f"Total CSV data rows on disk: {total_csv_rows:,}")

    # Read EXTRACTION_REGISTER.md
    if REGISTER_PATH.exists():
        text = REGISTER_PATH.read_text(encoding="utf-8", errors="replace")
        table_matches = re.findall(r"\|\s*\[([^\]]+\.csv)\]\([^\)]+\)\s*\|\s*([^\|]+)\s*\|\s*([0-9,]+)\s*\|\s*([^\|]+)\s*\|", text)
        register_series = {}
        for m in table_matches:
            fname = m[0].strip()
            desc = m[1].strip()
            rows_str = m[2].strip().replace(",", "")
            rows = int(rows_str) if rows_str.isdigit() else 0
            status = m[3].strip()
            register_series[fname] = (desc, rows, status)

        print(f"Register table lists {len(register_series)} CSV series.")
        
        # Missing from register:
        missing_from_register = set(disk_series.keys()) - set(register_series.keys())
        if missing_from_register:
            print(f"\n--- {len(missing_from_register)} Series on disk MISSING from register table ---")
            for f in sorted(missing_from_register):
                print(f"  + {f} ({disk_series[f]:,} rows)")
                
        # In register but not on disk:
        missing_from_disk = set(register_series.keys()) - set(disk_series.keys())
        if missing_from_disk:
            print(f"\n--- {len(missing_from_disk)} Series in register MISSING from disk ---")
            for f in sorted(missing_from_disk):
                print(f"  - {f}")

        # Outdated row counts:
        outdated = []
        for f, rows_disk in disk_series.items():
            if f in register_series:
                desc, rows_reg, status = register_series[f]
                if rows_disk != rows_reg:
                    outdated.append((f, rows_reg, rows_disk))
                    
        if outdated:
            print(f"\n--- {len(outdated)} Series with OUTDATED row counts in register ---")
            for f, r_reg, r_disk in sorted(outdated, key=lambda x: x[0]):
                print(f"  * {f}: register has {r_reg:,}, disk has {r_disk:,} (diff: {r_disk - r_reg:+d})")

if __name__ == "__main__":
    main()
