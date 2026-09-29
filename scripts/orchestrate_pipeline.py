#!/usr/bin/env python3
"""
scripts/orchestrate_pipeline.py
=============================================================================
Unified Shipping Intelligence Pipeline Orchestrator
=============================================================================

Automates end-to-end processing across all market intelligence sources:
1. HARVEST:
   - Hellenic WordPress REST API (shipbrokers, demolition, iron ore, TC, VV)
   - Fearnleys Hasura GraphQL delta sync (fixtures, rates, custom publications)
   - Baltic Dry / Tanker Exchange indices and SGX FFA derivatives
   - Breakwave Advisors biweekly market reports and insights
2. EXTRACT:
   - Cover-to-cover extraction of all publication PDFs and HTML articles
   - Conversion to clean GitHub-Flavored Markdown (.md)
   - Structured JSON sidecars (.tables.json) with explicit ISO issue_dates
   - Master stacked historical time series CSVs (data/extracted/series/)
3. VIEWS:
   - Pre-aggregated frontend JSON caches and view manifests
   - Dashboard master view (data/views/dashboard_master.json)
   - Daily tanker & dry bulk routes daily matrices
4. VERIFY:
   - Automated test suite execution
   - Master Extraction Register (docs/EXTRACTION_REGISTER.md) synchronization

Usage:
    python scripts/orchestrate_pipeline.py [--all]
    python scripts/orchestrate_pipeline.py --stage harvest
    python scripts/orchestrate_pipeline.py --stage extract
    python scripts/orchestrate_pipeline.py --stage views
    python scripts/orchestrate_pipeline.py --stage verify
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Ensure UTF-8 console output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_step(name: str, cmd: List[str], cwd: Path = ROOT) -> bool:
    """Execute a single pipeline sub-step, tracking duration and return code."""
    print(f"\n[RUNNING] {name}...")
    cmd_str = " ".join(cmd)
    print(f"  Command: {cmd_str}")
    t0 = time.time()
    
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=False, text=True)
        elapsed = time.time() - t0
        if res.returncode == 0:
            print(f"[SUCCESS] {name} completed in {elapsed:.1f}s.")
            return True
        else:
            print(f"[ERROR] {name} failed with return code {res.returncode} in {elapsed:.1f}s.")
            return False
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[EXCEPTION] {name} raised error: {e} in {elapsed:.1f}s.")
        return False

def stage_harvest() -> bool:
    print("\n" + "=" * 80)
    print("STAGE 1: HARVEST (Live Ingestion & Data Fetching)")
    print("=" * 80)
    
    success = True
    steps = [
        ("Hellenic REST API Live Sync", [sys.executable, "scripts/acquire/sync_hellenic_live.py"]),
        ("Fearnleys Delta Sync", [sys.executable, "scripts/fearnleys/daily_fearnleys_sync.py"]),
        ("Baltic & SGX FFA Indices Update", [sys.executable, "scripts/update_indices.py"]),
        ("Breakwave Advisors Report Scraper", [sys.executable, "scripts/breakwave_scraper.py", "--category", "both"]),
    ]
    
    for name, cmd in steps:
        ok = run_step(name, cmd)
        if not ok:
            success = False
            
    return success

def stage_extract() -> bool:
    print("\n" + "=" * 80)
    print("STAGE 2: EXTRACT (Cover-to-Cover Parsing & Series Stacking)")
    print("=" * 80)
    
    success = True
    steps = [
        ("Carriers Chartering Complete Extraction", [sys.executable, "scripts/extract/publishers/run_carriers_complete.py"]),
        ("Clarksons S&P & Demolition Extraction", [sys.executable, "scripts/extract/publishers/run_clarksons.py"]),
        ("Lion Shipbrokers Table & Sentiment Extraction", [sys.executable, "scripts/extract/publishers/run_lion_tables.py"]),
        ("Affinity Tanker Extraction", [sys.executable, "scripts/extract/publishers/run_affinity.py"]),
        ("Affinity Table Sidecars & Series Stacking", [sys.executable, "scripts/extract/publishers/run_affinity_tables.py"]),
        ("ISM Coaster & Handy Vector Extraction", [sys.executable, "scripts/extract/publishers/run_ism.py"]),
        ("ISM Series Stacking", [sys.executable, "scripts/extract/publishers/run_ism_series.py"]),
        ("Best Oasis Ship Recycling Extraction", [sys.executable, "scripts/extract/publishers/run_best_oasis_demolition.py"]),
        ("Athenian Demolition Quick Updates", [sys.executable, "scripts/extract/publishers/run_athenian_demolition.py"]),
        ("GMS Leadership Demolition Extraction", [sys.executable, "scripts/extract/publishers/run_gms_demolition.py"]),
        ("VesselsValue HTML & Valuation Extraction", [sys.executable, "scripts/extract/publishers/run_hellenic_vessel_valuations.py"]),
        ("SSY Capesize Index & Routes Extraction", [sys.executable, "scripts/extract/publishers/run_ssy_complete.py"]),
        ("Breakwave Clean LiteParse Extraction", [sys.executable, "scripts/extract/publishers/run_breakwave_clean_liteparse.py", "--batch"]),
        ("Xclusiv Cover-to-Cover Extraction", [sys.executable, "scripts/extract/publishers/run_xclusiv_full_cover_to_cover.py"]),
        ("Star Asia Table Extraction", [sys.executable, "scripts/extract/publishers/run_star_asia_tables.py"]),
    ]
    
    for name, cmd in steps:
        ok = run_step(name, cmd)
        if not ok:
            success = False
            
    return success

def stage_views() -> bool:
    print("\n" + "=" * 80)
    print("STAGE 3: VIEWS (Manifest Rebuilding & Frontend Cache Aggregation)")
    print("=" * 80)
    
    success = True
    steps = [
        ("Fearnleys Daily Tanker Routes", [sys.executable, "scripts/fearnleys/build_tanker_routes_daily.py", "--build"]),
        ("Fearnleys Dry Routes Time Series", [sys.executable, "scripts/fearnleys/fetch_dry_routes_ts.py", "--refresh"]),
        ("Fearnleys Pre-Aggregated Summary Cache", [sys.executable, "scripts/fearnleys/build_fearnleys_cache.py"]),
        ("Dashboard Master Views Generator", [sys.executable, "scripts/build_views.py"]),
    ]
    
    for name, cmd in steps:
        ok = run_step(name, cmd)
        if not ok:
            success = False
            
    return success

def stage_verify() -> bool:
    print("\n" + "=" * 80)
    print("STAGE 4: VERIFY (Unit Tests & Register Audit Synchronization)")
    print("=" * 80)
    
    success = True
    steps = [
        ("Master Extraction Register Sync", [sys.executable, "scripts/sync_extraction_register.py"]),
        ("Hellenic Extraction Pytest Suite", [sys.executable, "-m", "pytest", "tests/test_hellenic_extraction.py", "-v"]),
    ]
    
    for name, cmd in steps:
        ok = run_step(name, cmd)
        if not ok:
            success = False
            
    return success

def main():
    parser = argparse.ArgumentParser(description="Unified Shipping Intelligence Pipeline Orchestrator")
    parser.add_argument(
        "--stage",
        choices=["harvest", "extract", "views", "verify", "all"],
        default="all",
        help="Pipeline stage to execute (default: all)",
    )
    args = parser.parse_args()
    
    t_start = time.time()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("*" * 80)
    print(f"SHIPPING PIPELINE ORCHESTRATOR - STARTING EXECUTION AT {now_str}")
    print(f"Target Stage: {args.stage.upper()}")
    print("*" * 80)
    
    results = {}
    
    if args.stage in ("harvest", "all"):
        results["harvest"] = stage_harvest()
        
    if args.stage in ("extract", "all"):
        results["extract"] = stage_extract()
        
    if args.stage in ("views", "all"):
        results["views"] = stage_views()
        
    if args.stage in ("verify", "all"):
        results["verify"] = stage_verify()
        
    total_elapsed = time.time() - t_start
    print("\n" + "*" * 80)
    print(f"PIPELINE EXECUTION SUMMARY (Elapsed: {total_elapsed:.1f}s)")
    print("*" * 80)
    for stg, passed in results.items():
        status_tag = "[PASS]" if passed else "[FAIL]"
        print(f"  {stg.upper():<12} : {status_tag}")
        
    all_passed = all(results.values())
    if all_passed:
        print("\nALL SELECTED STAGES COMPLETED SUCCESSFULLY.")
        sys.exit(0)
    else:
        print("\nONE OR MORE STAGES REPORTED ERRORS. INSPECT LOGS ABOVE.")
        sys.exit(1)

if __name__ == "__main__":
    main()
