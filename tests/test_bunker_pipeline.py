#!/usr/bin/env python3
"""
Unit and Integration Tests for Global Marine Fuel & Bunker Ingestion Pipeline
"""

import os
import json
import pytest
import pandas as pd
from datetime import date

from bunker_pipeline.utils.normalizer import (
    normalize_grade,
    normalize_timestamp_ms,
    normalize_date_str,
    validate_price,
)
from bunker_pipeline.storage.incremental_store import IncrementalBunkerStore, MASTER_COLUMNS
from bunker_pipeline.extractors.bunkerindex_forward import get_contract_month_label, fetch_forward_month
from bunker_pipeline.extractors.bunkerindex_volumes import fetch_indicator
from bunker_pipeline.extractors.bunkerindex_bix import fetch_bix_suite, BIX_ENDPOINTS
from bunker_pipeline.extractors.shipandbunker_spot import fetch_market

def test_normalizer_grades():
    assert normalize_grade("VLSFO") == "VLSFO"
    assert normalize_grade("0.5%") == "VLSFO"
    assert normalize_grade("IFO 380") == "IFO380"
    assert normalize_grade("380 CST") == "IFO380"
    assert normalize_grade("HSFO") == "IFO380"
    assert normalize_grade("MGO (0.1%)") == "MGO"
    assert normalize_grade("LSMGO") == "LSMGO"
    assert normalize_grade("B24") == "BIO"

def test_normalizer_dates():
    assert normalize_date_str("2026-09-04") == "2026-09-04"
    assert normalize_date_str("20260904") == "2026-09-04"
    assert normalize_date_str("04 Sep", default_year=2026) == "2026-09-04"
    assert normalize_date_str("FSep 4", default_year=2026) == "2026-09-04"
    # ms timestamp 1709683200000 -> 2024-03-06
    assert normalize_timestamp_ms(1709683200000) == "2024-03-06"

def test_price_validation():
    assert validate_price(650.0) is True
    assert validate_price(1500.5) is True
    assert validate_price(0.0) is False
    assert validate_price(-10.0) is False
    assert validate_price(10000.0) is False
    assert validate_price(None) is False

def test_contract_month_label():
    d = date(2026, 9, 1)
    assert get_contract_month_label(1, d) == "2026-10"
    assert get_contract_month_label(4, d) == "2027-01"
    assert get_contract_month_label(12, d) == "2027-09"

def test_valid_markets_config():
    cfg_path = "bunker_pipeline/config/valid_markets.json"
    assert os.path.exists(cfg_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        markets = json.load(f)
    assert len(markets) == 221
    codes = set(m["code"] for m in markets)
    assert len(codes) == 221
    assert "SG SIN" in codes
    assert "NL RTM" in codes
    assert "US HOU" in codes
    assert "AE FJR" in codes
    assert "AU NTL" in codes

def test_indicator_catalog_config():
    cfg_path = "bunker_pipeline/config/indicator_catalog.json"
    assert os.path.exists(cfg_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    assert len(catalog) == 7
    ids = set(c["id"] for c in catalog)
    assert 2 in ids # Singapore monthly
    assert 3 in ids # Rotterdam quarterly

def test_incremental_store_deduplication(tmp_path):
    test_csv = str(tmp_path / "test_master.csv")
    test_json = str(tmp_path / "test_master.json")
    store = IncrementalBunkerStore(csv_path=test_csv, json_path=test_json)

    batch_1 = [
        {
            "observation_date": "2026-09-04",
            "port_code": "SG SIN",
            "port_name": "Singapore",
            "grade": "VLSFO",
            "delivery_term": "Prompt",
            "price_usd": 848.00,
            "change_usd": -12.50,
            "high_usd": 864.00,
            "low_usd": 825.00,
            "spread_usd": 39.00,
            "unit": "USD/MT",
            "source": "ShipAndBunker_HTML"
        },
        {
            "observation_date": "2026-09-04",
            "port_code": "NL RTM",
            "port_name": "Rotterdam",
            "grade": "VLSFO",
            "delivery_term": "Prompt",
            "price_usd": 681.50,
            "change_usd": 3.00,
            "high_usd": 690.00,
            "low_usd": 675.00,
            "spread_usd": 15.00,
            "unit": "USD/MT",
            "source": "ShipAndBunker_HTML"
        }
    ]

    stats_1 = store.ingest_records(batch_1)
    assert stats_1["added"] == 2
    assert stats_1["total_master"] == 2

    # Re-ingest exact same batch
    stats_2 = store.ingest_records(batch_1)
    assert stats_2["added"] == 0
    assert stats_2["total_master"] == 2

    # Ingest 1 updated record and 1 new record
    batch_2 = [
        {
            "observation_date": "2026-09-04",
            "port_code": "SG SIN",
            "port_name": "Singapore",
            "grade": "VLSFO",
            "delivery_term": "Prompt",
            "price_usd": 849.00, # Updated price
            "change_usd": -11.50,
            "high_usd": 864.00,
            "low_usd": 825.00,
            "spread_usd": 39.00,
            "unit": "USD/MT",
            "source": "ShipAndBunker_HTML"
        },
        {
            "observation_date": "2026-09-04",
            "port_code": "US HOU",
            "port_name": "Houston",
            "grade": "VLSFO",
            "delivery_term": "Prompt",
            "price_usd": 718.50,
            "change_usd": 4.00,
            "high_usd": 725.00,
            "low_usd": 710.00,
            "spread_usd": 15.00,
            "unit": "USD/MT",
            "source": "ShipAndBunker_HTML"
        }
    ]

    stats_3 = store.ingest_records(batch_2)
    assert stats_3["added"] == 1
    assert stats_3["total_master"] == 3

    df = store.load_master_df()
    assert len(df) == 3
    # Check that SG SIN was updated with latest price
    sg_row = df[(df["port_code"] == "SG SIN") & (df["grade"] == "VLSFO")].iloc[0]
    assert float(sg_row["price_usd"]) == 849.00

def test_live_forward_curve_month_1():
    df = fetch_forward_month(1)
    assert not df.empty
    assert "port" in df.columns
    assert "vlsfo_usd" in df.columns
    assert "Singapore" in df["port"].values
    assert "Rotterdam" in df["port"].values
    assert len(df) >= 5

def test_live_physical_volume_singapore():
    df = fetch_indicator(2)
    assert not df.empty
    assert "volume_mt" in df.columns
    assert len(df) >= 12
    # Verify realistic volume bounds (3.5M to 6.0M MT/month for Singapore)
    recent_vol = df["volume_mt"].iloc[-1]
    assert 3000000 <= recent_vol <= 6500000

def test_live_bix_world():
    df = fetch_bix_suite("BIX_World", BIX_ENDPOINTS["BIX_World"])
    assert not df.empty
    assert "price_usd" in df.columns
    assert "grade" in df.columns
    grades = set(df["grade"].unique())
    assert "VLSFO" in grades
    assert "IFO380" in grades
    assert "MGO" in grades
