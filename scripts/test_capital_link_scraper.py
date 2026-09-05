#!/usr/bin/env python3
"""
Unit and Integration Tests for Capital Link Indices Scraper & Data Stores
"""

import os
import sys
import pytest
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DATA_DIR = os.path.join(REPO_ROOT, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw', 'capital_link_excel')
INDICES_DIR = os.path.join(DATA_DIR, 'indices')

from scripts.scrapers.fetch_capital_link_indices import (
    CAPITAL_LINK_INDICES,
    parse_history_payload,
)


def test_indices_metadata():
    """Verify metadata definitions for all 7 Capital Link indices."""
    assert len(CAPITAL_LINK_INDICES) == 7
    expected_ids = {44, 45, 46, 47, 48, 49, 50}
    actual_ids = {v['index_id'] for v in CAPITAL_LINK_INDICES.values()}
    assert actual_ids == expected_ids, f"Mismatch in indexIds: {actual_ids}"


def test_payload_parser():
    """Verify parsing of API response dictionaries into DataFrames."""
    sample_payload = [
        {
            'Date': '2026-09-03T00:00:00',
            'Close': 5082.88,
            'Open': 5082.88,
            'High': 5082.88,
            'Low': 5082.88,
            'Turnover': 0.0,
            'Change': 0.1869,
        },
        {
            'Date': '2026-09-02T00:00:00',
            'Close': 5073.40,
            'Open': 5073.40,
            'High': 5073.40,
            'Low': 5073.40,
            'Turnover': 0.0,
            'Change': 1.95,
        }
    ]
    df = parse_history_payload(sample_payload, 'CLTI', 'Capital Link Tanker')
    assert len(df) == 2
    assert df.iloc[0]['date'] == '2026-09-02'  # sorted ascending
    assert df.iloc[1]['date'] == '2026-09-03'
    assert df.iloc[1]['close'] == 5082.88


def test_raw_excel_preservation():
    """Verify that all 7 original Excel files are safely stored in data/raw/capital_link_excel/."""
    assert os.path.exists(RAW_DIR), f"Raw storage directory missing: {RAW_DIR}"
    for meta in CAPITAL_LINK_INDICES.values():
        slug = meta['slug']
        raw_file = os.path.join(RAW_DIR, f"{slug}_raw.xlsx")
        assert os.path.exists(raw_file), f"Missing raw Excel archive: {raw_file}"
        assert os.path.getsize(raw_file) > 100000, f"Raw Excel file too small: {raw_file}"


def test_individual_indices_csv_integrity():
    """Verify that normalized CSVs exist in data/indices/ with 20+ years of history."""
    for code, meta in CAPITAL_LINK_INDICES.items():
        slug = meta['slug']
        csv_path = os.path.join(INDICES_DIR, f"{slug}.csv")
        assert os.path.exists(csv_path), f"Missing index CSV: {csv_path}"
        
        df = pd.read_csv(csv_path)
        assert not df.empty, f"Index CSV is empty: {csv_path}"
        assert len(df) >= 5000, f"Expected >= 5,000 rows for {code}, got {len(df)}"
        
        # Check required columns
        for col in ['date', 'index_name', 'index_code', 'close', 'open', 'high', 'low', 'volume', 'change_pct']:
            assert col in df.columns, f"Missing column {col} in {csv_path}"
            
        # Verify date monotonicity
        dates = pd.to_datetime(df['date'], format='%Y-%m-%d')
        assert dates.is_monotonic_increasing, f"Dates not monotonic in {csv_path}"
        
        # Check price reasonableness
        assert (df['close'] > 0).all(), f"Found non-positive close in {csv_path}"
        assert df['date'].min() <= '2005-06-01', f"History does not start in 2005 for {code}"
        assert df['date'].max() >= '2026-09-01', f"History is not up to date for {code}"


def test_consolidated_master_csv():
    """Verify that capital_link_indices_master.csv exists and has all 7 index series."""
    master_path = os.path.join(INDICES_DIR, 'capital_link_indices_master.csv')
    assert os.path.exists(master_path), f"Missing master CSV: {master_path}"
    
    df = pd.read_csv(master_path)
    assert not df.empty, "Master CSV is empty!"
    assert len(df) >= 5000, f"Expected >= 5,000 rows in master, got {len(df)}"
    assert 'date' in df.columns
    
    for code in CAPITAL_LINK_INDICES.keys():
        assert code in df.columns, f"Missing column {code} in master CSV"
        assert df[code].notna().sum() >= 5000, f"Too many missing values for {code} in master CSV"
