#!/usr/bin/env python3
"""
Master Orchestrator & CLI for Global Marine Fuel & Bunker Ingestion Pipeline
Executes:
1. Ship & Bunker Historical Spot Engine (221 ports & benchmarks)
2. HTML Matrix Sliding-Window Scraper
3. Bunker Index 12-Month Forward Curves
4. Bunker Index Physical Sales Volume Indicators
5. BIX Macro Benchmark Suites
6. Persistent Incremental Master Store Management
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime

from bunker_pipeline.extractors.shipandbunker_spot import fetch_market
from bunker_pipeline.extractors.bunker_scraper import scrape_all_popular_ports, scrape_port_page, POPULAR_PORT_URLS
from bunker_pipeline.extractors.bunkerindex_forward import fetch_all_forward_curves
from bunker_pipeline.extractors.bunkerindex_volumes import fetch_all_volume_indicators
from bunker_pipeline.extractors.bunkerindex_bix import fetch_all_bix_benchmarks
from bunker_pipeline.storage.incremental_store import STORE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BunkerPipeline")

CONFIG_MARKETS_PATH = "bunker_pipeline/config/valid_markets.json"
STORAGE_DIR = "data/bunkers"

def load_valid_markets() -> list:
    """Loads configured 221 markets."""
    if not os.path.exists(CONFIG_MARKETS_PATH):
        logger.error(f"Missing configuration file at {CONFIG_MARKETS_PATH}")
        return []
    with open(CONFIG_MARKETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_spot_extraction(markets: list, limit: int = None):
    """Harvests historical spot series across target markets."""
    targets = markets[:limit] if limit else markets
    logger.info(f"Starting spot price extraction across {len(targets)} markets...")
    
    total_extracted = 0
    all_records = []
    
    for i, m in enumerate(targets):
        code = m.get("code")
        name = m.get("name")
        logger.info(f"[{i+1}/{len(targets)}] Fetching spot history for {code} ({name})...")
        records = fetch_market(code, name)
        if records:
            all_records.extend(records)
            total_extracted += len(records)
            
        # Ingest in batches of 10 markets or at the end
        if (i + 1) % 10 == 0 or (i + 1) == len(targets):
            if all_records:
                STORE.ingest_records(all_records)
                all_records = []
                
    logger.info(f"Finished spot extraction. Harvested {total_extracted} total price points.")

def run_html_matrix_extraction():
    """Extracts rolling sliding-window matrices from popular port pages."""
    logger.info("Starting HTML matrix sliding-window extraction...")
    records = scrape_all_popular_ports()
    if records:
        stats = STORE.ingest_records(records)
        logger.info(f"HTML matrix ingestion stats: {stats}")
    return records

def run_forward_curves_extraction():
    """Extracts 12-month forward curves across 6 hubs."""
    logger.info("Starting Bunker Index 12-month forward curve extraction...")
    df = fetch_all_forward_curves()
    if not df.empty:
        out_csv = os.path.join(STORAGE_DIR, "bunker_forward_curves_12m.csv")
        out_json = os.path.join(STORAGE_DIR, "bunker_forward_curves_12m.json")
        df.to_csv(out_csv, index=False)
        df.to_json(out_json, orient="records", indent=2)
        logger.info(f"Saved {len(df)} forward curve points to {out_csv}")
    return df

def run_volume_indicators_extraction():
    """Extracts physical sales volumes for Singapore & Rotterdam."""
    logger.info("Starting physical bunker sales volume extraction...")
    df = fetch_all_volume_indicators()
    if not df.empty:
        out_csv = os.path.join(STORAGE_DIR, "bunker_physical_sales_volumes.csv")
        out_json = os.path.join(STORAGE_DIR, "bunker_physical_sales_volumes.json")
        df.to_csv(out_csv, index=False)
        df.to_json(out_json, orient="records", indent=2)
        logger.info(f"Saved {len(df)} physical volume records to {out_csv}")
    return df

def run_bix_benchmarks_extraction():
    """Extracts BIX global & regional composite benchmarks."""
    logger.info("Starting BIX macro benchmark suites extraction...")
    df = fetch_all_bix_benchmarks()
    if not df.empty:
        out_csv = os.path.join(STORAGE_DIR, "bunker_bix_macro_benchmarks.csv")
        out_json = os.path.join(STORAGE_DIR, "bunker_bix_macro_benchmarks.json")
        df.to_csv(out_csv, index=False)
        df.to_json(out_json, orient="records", indent=2)
        logger.info(f"Saved {len(df)} BIX benchmark records to {out_csv}")
    return df

def run_autonomous_validation():
    """Executes the test harness specified in Section 7 of specification."""
    logger.info("=" * 80)
    logger.info("EXECUTING AUTONOMOUS VALIDATION PROTOCOL")
    logger.info("=" * 80)
    
    # 1. Test Ship & Bunker RPC extraction (Singapore)
    logger.info("Test 1: Ship & Bunker RPC Extraction (Singapore)...")
    sg_records = fetch_market("SG SIN", "Singapore")
    assert len(sg_records) > 500, f"Expected >500 records for Singapore, got {len(sg_records)}"
    logger.info(f"PASS: Extracted {len(sg_records)} daily spot records for Singapore.")
    
    # 2. Test Bunker Index Forward Curve (Month 1)
    logger.info("Test 2: Bunker Index Forward Curve (Month 1)...")
    from bunker_pipeline.extractors.bunkerindex_forward import fetch_forward_month
    fwd_df = fetch_forward_month(1)
    assert not fwd_df.empty, "Forward curve month 1 returned empty DataFrame"
    assert "Rotterdam" in fwd_df["port"].values, "Expected Rotterdam in forward curve hubs"
    assert "Singapore" in fwd_df["port"].values, "Expected Singapore in forward curve hubs"
    logger.info(f"PASS: Extracted Month 1 forward curve with hubs: {list(fwd_df['port'].values)}")
    
    # 3. Test Bunker Index Indicator volume (Singapore Monthly)
    logger.info("Test 3: Bunker Index Volume Indicator (Singapore Monthly ID 2)...")
    from bunker_pipeline.extractors.bunkerindex_volumes import fetch_indicator
    vol_df = fetch_indicator(2)
    assert not vol_df.empty, "Volume indicator 2 returned empty DataFrame"
    assert len(vol_df) >= 12, f"Expected at least 12 months, got {len(vol_df)}"
    logger.info(f"PASS: Extracted {len(vol_df)} months of physical sales volumes for Singapore.")
    
    # 4. Test Incremental Master Store Deduplication
    logger.info("Test 4: Incremental Master Store Deduplication...")
    test_rows = sg_records[:10]
    initial_master_len = len(STORE.load_master_df())
    stats1 = STORE.ingest_records(test_rows)
    stats2 = STORE.ingest_records(test_rows) # Re-ingest exact same rows
    assert stats2["added"] == 0, f"Expected 0 added on duplicate ingestion, got {stats2['added']}"
    logger.info("PASS: Duplicate records cleanly rejected by composite primary key.")
    
    logger.info("=" * 80)
    logger.info("ALL VALIDATION PROTOCOL TESTS PASSED WITH 100% SUCCESS.")
    logger.info("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Global Marine Fuel & Bunker Ingestion Pipeline")
    parser.add_argument("--mode", choices=["full", "incremental", "spot", "forward", "volumes", "bix", "test"], default="incremental")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of markets for spot extraction")
    args = parser.parse_args()

    markets = load_valid_markets()
    logger.info(f"Loaded {len(markets)} valid markets from configuration.")

    start_time = time.time()

    if args.mode == "test":
        run_autonomous_validation()
    elif args.mode == "spot":
        run_spot_extraction(markets, limit=args.limit)
    elif args.mode == "forward":
        run_forward_curves_extraction()
    elif args.mode == "volumes":
        run_volume_indicators_extraction()
    elif args.mode == "bix":
        run_bix_benchmarks_extraction()
    elif args.mode == "incremental":
        logger.info("Running daily incremental sync...")
        run_html_matrix_extraction()
        run_forward_curves_extraction()
        run_volume_indicators_extraction()
        run_bix_benchmarks_extraction()
        # Also refresh top 10 global bunker hubs spot
        top_hubs = [m for m in markets if m.get("code") in [
            "SG SIN", "NL RTM", "US HOU", "AE FJR", "CN HOK", "KR PUS", "GI GIB", "PA PAC", "CN ZOS", "JP TYO"
        ]]
        run_spot_extraction(top_hubs)
    elif args.mode == "full":
        logger.info("Running full master corpus ingestion...")
        run_html_matrix_extraction()
        run_forward_curves_extraction()
        run_volume_indicators_extraction()
        run_bix_benchmarks_extraction()
        run_spot_extraction(markets, limit=args.limit)

    elapsed = time.time() - start_time
    logger.info(f"Pipeline run ({args.mode}) finished in {elapsed:.2f} seconds.")

if __name__ == "__main__":
    main()
