"""
Inventory and audit all stacked time-series CSVs in data/extracted/series/.
Prints exact row counts, schema, and broker attribution.
"""

from pathlib import Path
import csv
import sys

def main():
    series_dir = Path("data/extracted/series")
    csvs = sorted(series_dir.glob("*.csv"))
    print(f"Total series CSV files: {len(csvs)}\n", flush=True)

    total_rows = 0
    sources = {}

    for p in csvs:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fp:
                reader = csv.reader(fp)
                header = next(reader, [])
                count = sum(1 for _ in reader)
            total_rows += count
            prefix = p.stem.split("_")[0]
            sources.setdefault(prefix, []).append((p.name, count, len(header)))
        except Exception as e:
            print(f"Error reading {p.name}: {e}", flush=True)

    print(f"{'Series Filename':<48} | {'Rows':>8} | {'Cols':>4}", flush=True)
    print("-" * 66, flush=True)
    for p in csvs:
        prefix = p.stem.split("_")[0]
        for name, count, ncols in sources.get(prefix, []):
            if name == p.name:
                print(f"{name:<48} | {count:>8,} | {ncols:>4}", flush=True)

    print("-" * 66, flush=True)
    print(f"{'TOTAL ACROSS ALL SERIES':<48} | {total_rows:>8,} |", flush=True)
    print("\nBreakdown by Broker House / Prefix:", flush=True)
    for s, files in sorted(sources.items()):
        s_rows = sum(r for _, r, _ in files)
        print(f"  {s:<15} : {len(files):>2} CSVs, {s_rows:>8,} rows", flush=True)

if __name__ == "__main__":
    main()
