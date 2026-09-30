"""Audit pipeline scripts for hardcoded year strings."""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

SCRIPTS = [
    ROOT / "scripts/extract/orchestrate_incremental_ingest.py",
    ROOT / "scripts/scrapers/fetch_hsn_shipbrokers.py",
    ROOT / "scripts/extract/publishers/extract_week39_supplements.py",
    ROOT / "scripts/extract/build_banchero_series.py",
    ROOT / "scripts/extract/publishers/run_intermodal_full.py",
    ROOT / "scripts/extract/publishers/run_singletons.py",
    ROOT / "scripts/extract/publishers/run_carriers_complete.py",
]

# Match literal hardcoded year strings like "2026" or '2026' or / "2026" as path segment
HARDCODED_RX = re.compile(r'["\'/]202[0-9]["\'/]|= *"202[0-9]"|= *\'202[0-9]\'|/ "202[0-9]"')
# Legit dynamic patterns to ignore
SKIP_RX = re.compile(
    r'issue_date|YYYY|year_match|datetime\.now|\.year\b|range\(|sample|example|note:|#|'
    r'verified|assert|str\(year|f\"|csv\.writer|\.strftime|print\(|re\.compile|regex|'
    r'\"20\d{2}-\d{2}-\d{2}\"'
)

print("=" * 70)
print("HARDCODED YEAR AUDIT")
print("=" * 70)

total_issues = 0
for script in SCRIPTS:
    if not script.exists():
        print(f"  SKIP (not found): {script.name}")
        continue
    hits = []
    for i, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
        if HARDCODED_RX.search(line) and not SKIP_RX.search(line):
            hits.append((i, line.strip()))
    if hits:
        print(f"\n{script.name} -- {len(hits)} suspect line(s):")
        for n, l in hits:
            print(f"  [{n:4d}]: {l[:100]}")
        total_issues += len(hits)
    else:
        print(f"  {script.name}: OK")

print()
print(f"Total suspect hardcoded years: {total_issues}")
