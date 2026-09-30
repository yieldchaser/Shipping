"""
run_banchero_sequential.py

Sequentially processes Banchero Costa weekly reports across years 2024 -> 2023 -> 2022 -> 2021
with gentle 2-worker concurrency to prevent local system/memory strain.
After completing all years, automatically stacks all 10 master series CSVs.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Ensure UTF-8
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero_v2"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "banchero_costa"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract.publishers.run_banchero_world_class_llama import process_corpus
from scripts.extract.publishers.stack_banchero_series import stack_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("sequential_banchero")


def wait_for_year_2025_completion():
    """Wait if 2025 is still being processed in another task."""
    year_2025_pdfs = list((CORPUS_DIR / "2025").glob("*.pdf"))
    expected_count = len(year_2025_pdfs)
    logger.info(f"Target 2025 files: {expected_count}")

    while True:
        completed = list(RAW_DIR.glob("*2025*.md"))
        logger.info(f"Checking 2025 progress: {len(completed)} / {expected_count} completed...")
        if len(completed) >= expected_count:
            logger.info("2025 ingestion fully complete!")
            break
        time.sleep(15)


def main():
    logger.info("Starting sequential Banchero Costa ingestion pipeline...")
    
    # 1. Wait for 2025 background task to finish if active
    wait_for_year_2025_completion()

    # 2. Sequentially process remaining years with 2 gentle workers
    years_to_process = [2024, 2023, 2022, 2021]
    for yr in years_to_process:
        logger.info("=" * 60)
        logger.info(f"STARTING YEAR {yr} WITH 2 WORKERS")
        logger.info("=" * 60)
        process_corpus(year=yr, workers=2)
        logger.info(f"YEAR {yr} COMPLETED SUCCESSFULLY!")

    # 3. Stack all master series
    logger.info("=" * 60)
    logger.info("STACKING ALL MASTER TIME SERIES (2021-2026)")
    logger.info("=" * 60)
    stack_all()
    logger.info("ALL MASTER SERIES SUCCESSFULLY STACKED!")


if __name__ == "__main__":
    main()
