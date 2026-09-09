#!/usr/bin/env python3
"""
Test Baltic Indices Data Integrity and Deobfuscation Scraper
"""

import os
import sys
import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts'))
from update_indices import decode_stockq, scrape_index, INDEXES


def test_stockq_deobfuscator_vectors():
    assert decode_stockq('MjA3Mjc1NzU5N3wxMy4wfDgxN3wwfDgxOXw2Mw==') == '6313.00'
    assert decode_stockq('MjA3Mjc2MTY4Mnw0OTZ8LnwwfDkxN3w0Mw==') == '0.43'
    assert decode_stockq('NDU4MTU5NzQ5fDQ2M3wzNDh8NTAwfDEufDAw') == '5001.00'


def test_baltic_index_files_updated():
    files = {
        'Capesize': 'data/indices/cape_historical.csv',
        'BDI': 'data/indices/bdiy_historical.csv',
        'Panamax': 'data/indices/panama_historical.csv',
        'Supramax': 'data/indices/suprama_historical.csv',
        'Handysize': 'data/indices/handysize_historical.csv',
        'Dirty Tanker': 'data/indices/dirtytanker_historical.csv',
        'Clean Tanker': 'data/indices/cleantanker_historical.csv',
    }

    for name, rel_path in files.items():
        full_path = os.path.join(REPO_ROOT, rel_path)
        assert os.path.exists(full_path), f'Missing {name} index file: {rel_path}'
        df = pd.read_csv(full_path)
        assert len(df) > 4000, f'{name} file too small: {len(df)} rows'
        latest = df.iloc[-1]
        assert latest['Date'] >= '2026-09-08', f'{name} data is outdated: latest date is {latest["Date"]}'
        price = float(str(latest['Index']).replace(',', ''))
        assert price > 0, f'{name} price must be positive, got {price}'

    cape_df = pd.read_csv(os.path.join(REPO_ROOT, 'data/indices/cape_historical.csv'))
    latest_cape = cape_df.iloc[-1]
    cape_price = float(str(latest_cape['Index']).replace(',', ''))
    assert cape_price > 6000, f'Capesize price should be >6000 on 2026-09-08, got {cape_price}'
    assert cape_price != 5105.0, 'Capesize price is still stuck at old 5,105 value!'


def test_scrape_index_bci_returns_valid_data():
    df = scrape_index('BCI')
    assert not df.empty, 'scrape_index(BCI) returned empty DataFrame'
    assert 'Date' in df.columns
    assert 'Index' in df.columns
    assert '% Change' in df.columns
    assert len(df) >= 20
    latest_row = df.iloc[-1]
    assert latest_row['Date'] >= '2026-09-08'
    assert float(latest_row['Index']) > 6000
