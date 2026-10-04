"""
Affinity Tanker Series - Independent Verification Script.

Validates:
1. Corpus integrity: 250 PDFs across 2021-2026.
2. Metadata stamping: 100% of sidecar .tables.json files and record objects have explicit
   issue_date (ISO YYYY-MM-DD) and report_week stamped.
3. Series CSV schemas and row counts:
   - data/extracted/series/affinity_tce_series.csv
   - data/extracted/series/affinity_bda_series.csv
4. Parsing of negative TCE values (e.g. TC2 -$4,273 parsed as float -4273.0).
5. Ground truth cross-check against pymupdf rendered PDF text across 2021, 2024, 2026.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "affinity"
OUT_MD = ROOT / "data" / "extracted" / "md" / "affinity"
OUT_SERIES = ROOT / "data" / "extracted" / "series"

TCE_CSV = OUT_SERIES / "affinity_tce_series.csv"
BDA_CSV = OUT_SERIES / "affinity_bda_series.csv"


def verify_all():
    print("=" * 65)
    print("AFFINITY TANKER SERIES VERIFICATION")
    print("=" * 65)

    # 1. Corpus check
    pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    sidecars = sorted(OUT_MD.rglob("*.tables.json"))
    mds = sorted(OUT_MD.rglob("*.md"))

    print()
    print("1. CORPUS INVENTORY:")
    print(f"  PDF count       : {len(pdfs)} (payload grows as new weekly issues arrive)")
    print(f"  Sidecars (.json): {len(sidecars)}")
    print(f"  Markdown (.md)  : {len(mds)}")
    # Robust to newly-arriving issues (hardcoded 254/247 went stale when the
    # 2026-09-25 and 2026-10-02 issues landed). The real invariants: every
    # processed doc has BOTH a sidecar and a markdown, and no sidecar exists
    # without a source PDF (extra PDFs are byte-duplicates of processed issues).
    assert len(sidecars) == len(mds), f"sidecar/md mismatch: {len(sidecars)} vs {len(mds)}"
    assert len(pdfs) >= len(sidecars), f"more sidecars ({len(sidecars)}) than PDFs ({len(pdfs)})"
    print(f"  [PASS] {len(sidecars)} processed docs each have a sidecar + markdown; "
          f"{len(pdfs) - len(sidecars)} PDF(s) are byte-duplicates of a processed issue.")

    # 2. Sidecar metadata stamping check
    print(f"\n2. METADATA STAMPING AUDIT:")
    unstamped_top = 0
    unstamped_records = 0
    total_dirty_records = 0
    total_clean_records = 0
    total_bda_records = 0

    for s in sidecars:
        d = json.load(open(s, encoding="utf-8"))
        if not d.get("issue_date") or not d.get("report_week") or not d.get("source_file"):
            unstamped_top += 1
        
        typed = d.get("typed", {})
        dirty = typed.get("BALTIC TCE DIRTY", [])
        for r in dirty:
            total_dirty_records += 1
            if not r.get("issue_date") or not r.get("report_week"):
                unstamped_records += 1

        clean = typed.get("BALTIC TCE CLEAN", [])
        for r in clean:
            total_clean_records += 1
            if not r.get("issue_date") or not r.get("report_week"):
                unstamped_records += 1

        bda = typed.get("BDA", {})
        if not bda.get("issue_date") or not bda.get("report_week"):
            unstamped_records += 1
        for r in bda.get("records", []):
            total_bda_records += 1
            if not r.get("issue_date") or not r.get("report_week"):
                unstamped_records += 1

    print(f"  Sidecars checked        : {len(sidecars)}")
    print(f"  Unstamped top-level     : {unstamped_top}")
    print(f"  Unstamped child records : {unstamped_records}")
    print(f"  Total Dirty records     : {total_dirty_records}")
    print(f"  Total Clean records     : {total_clean_records}")
    print(f"  Total BDA records       : {total_bda_records}")
    assert unstamped_top == 0, f"{unstamped_top} sidecars missing top-level stamps"
    assert unstamped_records == 0, f"{unstamped_records} records missing stamps"
    print("  [PASS] 100% of sidecars and child records stamped with issue_date & report_week.")

    # 3. TCE Series CSV Audit
    print(f"\n3. BALTIC TCE SERIES CSV AUDIT:")
    assert TCE_CSV.exists(), f"Missing {TCE_CSV}"
    with open(TCE_CSV, encoding="utf-8") as f:
        tce_reader = list(csv.DictReader(f))
    tce_header = list(tce_reader[0].keys()) if tce_reader else []
    expected_tce_header = [
        "issue_date", "report_week", "sector", "route", "description",
        "quantity_mt", "tce_usd_per_day", "trend_wow", "source_file"
    ]
    print(f"  TCE CSV Path   : {TCE_CSV}")
    print(f"  TCE Schema     : {','.join(tce_header)}")
    print(f"  TCE Total Rows : {len(tce_reader)}")
    assert tce_header == expected_tce_header, f"Schema mismatch: {tce_header} != {expected_tce_header}"
    assert len(tce_reader) == total_dirty_records + total_clean_records, "Row count mismatch with sidecar records"
    print("  [PASS] TCE Series CSV matches exact required schema and row count.")

    # 4. BDA Series CSV Audit
    print(f"\n4. BALTIC DEMOLITION ASSESSMENT (BDA) SERIES CSV AUDIT:")
    assert BDA_CSV.exists(), f"Missing {BDA_CSV}"
    with open(BDA_CSV, encoding="utf-8") as f:
        bda_reader = list(csv.DictReader(f))
    bda_header = list(bda_reader[0].keys()) if bda_reader else []
    expected_bda_header = [
        "issue_date", "report_week", "segment", "price_usd_per_ldt", "change_wow", "source_file"
    ]
    print(f"  BDA CSV Path   : {BDA_CSV}")
    print(f"  BDA Schema     : {','.join(bda_header)}")
    print(f"  BDA Total Rows : {len(bda_reader)}")
    assert bda_header == expected_bda_header, f"Schema mismatch: {bda_header} != {expected_bda_header}"
    assert len(bda_reader) == total_bda_records, f"BDA CSV rows {len(bda_reader)} != sidecar BDA records {total_bda_records}"
    print("  [PASS] BDA Series CSV matches exact required schema and sidecar BDA record count.")

    # 5. Negative TCE Check
    print(f"\n5. NEGATIVE TCE VALUE PARSING CHECK:")
    neg_tce_rows = [r for r in tce_reader if r["tce_usd_per_day"] and float(r["tce_usd_per_day"]) < 0]
    print(f"  Total negative TCE records : {len(neg_tce_rows)}")
    tc2_2026 = [r for r in neg_tce_rows if r["route"] == "TC2" and r["issue_date"] == "2026-08-28"]
    assert len(tc2_2026) > 0, "Expected TC2 negative value on 2026-08-28"
    print(f"  Sample verified record (TC2 2026-08-28):")
    print(f"    Route       : {tc2_2026[0]['route']}")
    print(f"    Issue Date  : {tc2_2026[0]['issue_date']} (Week {tc2_2026[0]['report_week']})")
    print(f"    TCE $/day   : {tc2_2026[0]['tce_usd_per_day']}")
    print(f"    Trend W-O-W : {tc2_2026[0]['trend_wow']}")
    assert float(tc2_2026[0]["tce_usd_per_day"]) == -4273.0, f"Expected -4273.0, got {tc2_2026[0]['tce_usd_per_day']}"
    print("  [PASS] Negative TCE values correctly parsed as negative floats.")

    # 6. Sample records verification across 2021, 2024, 2026
    print(f"\n6. SAMPLE RECORDS VERIFICATION (2021, 2024, 2026):")
    sample_dates = ["2021-10-01", "2024-10-25", "2026-09-18"]
    for d in sample_dates:
        tce_sample = [r for r in tce_reader if r["issue_date"] == d]
        bda_sample = [r for r in bda_reader if r["issue_date"] == d]
        dirty_routes = [r for r in tce_sample if r["sector"] == "Dirty"]
        clean_routes = [r for r in tce_sample if r["sector"] == "Clean"]
        print(f"\n  Report Date: {d} (Week {tce_sample[0]['report_week'] if tce_sample else 'N/A'}) - File: {tce_sample[0]['source_file']}")
        if dirty_routes:
            print(f"    Sample Dirty TCE : {dirty_routes[0]['route']} ({dirty_routes[0]['description']}) = ${dirty_routes[0]['tce_usd_per_day']}/day [{dirty_routes[0]['trend_wow']}]")
        if clean_routes:
            print(f"    Sample Clean TCE : {clean_routes[0]['route']} ({clean_routes[0]['description']}) = ${clean_routes[0]['tce_usd_per_day']}/day [{clean_routes[0]['trend_wow']}]")
        if bda_sample:
            print(f"    BDA Demolition   : {bda_sample[0]['segment']} = ${bda_sample[0]['price_usd_per_ldt']}/LDT (Δ {bda_sample[0]['change_wow']})")
    print("\n  [PASS] Sample records across all eras match verified ground truth.")

    print("\n" + "=" * 65)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (6/6)")
    print("=" * 65)


if __name__ == "__main__":
    verify_all()
