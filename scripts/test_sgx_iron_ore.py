#!/usr/bin/env python3
"""
Unit and Integration Tests for SGX Iron Ore Derivatives Ingestion Pipeline
"""

import os
import pytest
import pandas as pd
from datetime import datetime

import sys
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DATA_DIR = os.path.join(REPO_ROOT, 'data')
COMMODITIES_DIR = os.path.join(DATA_DIR, 'commodities')
FUTURES_DIR = os.path.join(DATA_DIR, 'futures')
DERIVED_DIR = os.path.join(DATA_DIR, 'derived')

from scripts.scrapers.fetch_sgx_iron_ore import (
    generate_contract_tickers,
    get_contract_expiry,
    CME_MONTHS,
)


def test_contract_expiry_calculation():
    """Verify that contract expiry dates always resolve to weekdays."""
    for y in range(2020, 2030):
        for m in range(1, 13):
            exp = get_contract_expiry(m, y)
            assert exp.weekday() < 5, f"Expiry {exp} falls on a weekend!"
            assert exp.month == m, f"Expiry {exp} month mismatch for {m}/{y}"
            assert exp.year == y, f"Expiry {exp} year mismatch for {y}"


def test_ticker_generation():
    """Verify ticker generation logic across all CME month codes."""
    tickers = generate_contract_tickers('FEF', start_year=2024, end_year=2025)
    assert len(tickers) == 24
    assert tickers[0]['ticker'] == 'FEFF24'
    assert tickers[0]['month_name'] == 'Jan'
    assert tickers[11]['ticker'] == 'FEFZ24'
    assert tickers[11]['month_name'] == 'Dec'
    assert tickers[12]['ticker'] == 'FEFF25'


def test_forward_curve_file_integrity():
    """Verify that sgx_iron_ore_forward_curve.csv is well-formed with valid metrics."""
    curve_path = os.path.join(COMMODITIES_DIR, 'sgx_iron_ore_forward_curve.csv')
    assert os.path.exists(curve_path), f"Forward curve CSV not found: {curve_path}"
    
    df = pd.read_csv(curve_path)
    assert not df.empty, "Forward curve CSV is empty!"
    assert len(df) >= 12, f"Expected at least 12 forward tenors, got {len(df)}"
    
    required_cols = [
        'date', 'tenor', 'delivery_month', 'delivery_year',
        'fef_ticker', 'fef_settle', 'fef_oi', 'fef_volume',
        'm65f_ticker', 'm65f_settle', 'm65f_oi', 'm65f_volume',
        'fe65_fe62_premium_spread', 'lpf_ticker', 'lpf_settle',
        'fef_term_structure_slope', 'fef_slope_pct', 'fef_curve_regime'
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column in forward curve: {col}"
        
    # Check price bounds for prompt & forward (standard range: $50 to $200/dmt)
    prompt_fef = df.iloc[0]['fef_settle']
    assert 60.0 <= prompt_fef <= 180.0, f"FEF prompt settle ${prompt_fef} outside realistic bounds"
    
    prompt_m65f = df.iloc[0]['m65f_settle']
    if pd.notna(prompt_m65f):
        assert prompt_m65f > prompt_fef, "65% Fe price should exceed 62% Fe price!"
        spread = df.iloc[0]['fe65_fe62_premium_spread']
        assert 5.0 <= spread <= 40.0, f"High-grade spread ${spread} outside realistic bounds"
        
    # Open interest should be positive for active curve
    assert df['fef_oi'].sum() > 100000, "Expected >100,000 lots total open interest across active curve"


def test_continuous_series_integrity():
    """Verify that sgx_iron_ore_continuous_daily.csv is monotonic and complete."""
    cont_path = os.path.join(COMMODITIES_DIR, 'sgx_iron_ore_continuous_daily.csv')
    assert os.path.exists(cont_path), f"Continuous daily CSV not found: {cont_path}"
    
    df = pd.read_csv(cont_path)
    assert not df.empty, "Continuous daily CSV is empty!"
    
    # Verify date format and sorting
    dates = pd.to_datetime(df['date'], format='%Y-%m-%d')
    assert dates.is_monotonic_increasing, "Continuous daily series dates are not monotonically increasing!"
    
    # Check price integrity
    assert df['fef_m1_price'].notna().all(), "Found null values in fef_m1_price!"
    assert (df['fef_m1_price'] > 40.0).all(), "Found prices below $40/dmt in FEF front month"
    assert (df['fef_m1_price'] < 260.0).all(), "Found prices above $260/dmt in FEF front month"
    
    # Check term structure spread
    assert 'm1_m2_term_structure_spread' in df.columns
    assert 'high_grade_spread_65_62' in df.columns


def test_historical_contract_stores():
    """Verify that full historical stores exist and have expected columns."""
    for fn in ['sgx_iron_ore_62_fef_historical.csv', 'sgx_iron_ore_65_m65f_historical.csv', 'sgx_iron_ore_lump_lpf_historical.csv']:
        p = os.path.join(COMMODITIES_DIR, fn)
        assert os.path.exists(p), f"Missing historical file: {p}"
        df = pd.read_csv(p)
        assert not df.empty, f"Historical file is empty: {p}"
        for col in ['contract', 'expiry_month', 'expiry_year', 'date', 'price', 'volume', 'open_interest', 'expiry_date']:
            assert col in df.columns, f"Missing column {col} in {p}"


def test_derived_iron_ore_restocking_sync():
    """Verify that iron_ore_restocking.csv has valid non-empty CFR prices."""
    restock_path = os.path.join(DERIVED_DIR, 'iron_ore_restocking.csv')
    assert os.path.exists(restock_path)
    df = pd.read_csv(restock_path)
    
    # Check that latest rows have populated CFR 62%
    latest_rows = df.tail(10)
    assert latest_rows['cfr_62'].notna().sum() >= 8, "Too many missing CFR 62 values in recent rows"
