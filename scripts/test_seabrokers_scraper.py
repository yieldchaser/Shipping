#!/usr/bin/env python3
"""
Unit and Integration Tests for Seabrokers Seabreeze Scraper & Digestion Pipeline
"""

import os
import sys
import json
import pytest
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.scrapers.fetch_seabrokers_reports import (
    parse_month_year,
    extract_osv_rates_from_text,
    CATALOG_PATH_REPORTS,
    CATALOG_PATH_DATA,
    RATES_CSV_PATH,
    SEABROKERS_REPORTS_DIR,
)


def test_month_year_parser():
    """Verify multilingual English and Norwegian date parsing."""
    test_cases = [
        ("Market Report August 2026", "market-report-august-2026", "2026-08-01", 2026, 8),
        ("Markedsrapport juli 2026", "markedsrapport-juli-2026", "2026-07-01", 2026, 7),
        ("Market Report May 2026", "market-report-may-2025-2", "2026-05-01", 2026, 5),
        ("Market Report October 2018", "markedsrapport-oktober-2018", "2018-10-01", 2018, 10),
        ("Markedsrapport mai 2018", "markedsrapport-mai-2018", "2018-05-01", 2018, 5),
        ("Markedsrapport desember 2024", "markedsrapport-desember-2024", "2024-12-01", 2024, 12),
    ]
    for title, slug, expected_date, exp_year, exp_month in test_cases:
        d, y, m = parse_month_year(title, slug)
        assert d == expected_date, f"Failed for {title}: got {d}, expected {expected_date}"
        assert y == exp_year
        assert m == exp_month


def test_extract_osv_rates():
    """Verify regex extraction of spot dayrates and utilization."""
    sample_text = """
    NORTH SEA SPOT AVERAGE UTILISATION AUG 2026
    TYPE AUG 2026 JUL 2026 JUN 2026 MAY 2026 APR 2026 MAR 2026
    MED PSV (<900m2) 82% 61% 50% 54% 85% 69%
    LARGE PSV (>900m2) 79% 62% 65% 68% 89% 67%
    MED AHTS (<22,000 bhp) 46% 41% 51% 33% 56% 29%
    LARGE AHTS (>22,000 bhp) 73% 55% 80% 53% 63% 37%

    NORTH SEA AVERAGE RATES AUGUST 2026
    CATEGORY AVERAGE RATE AUG 2026 AVERAGE RATE AUG 2025 % CHANGE MINIMUM MAXIMUM
    SUPPLY DUTIES PSVS < 900M2 £18,000 £4,737 +279.99% £15,000 £20,000
    SUPPLY DUTIES PSVS > 900M2 £21,445 £5,925 +261.94% £9,000 £31,000
    AHTS DUTIES AHTS < 22,000 BHP £62,332 £15,899 +292.05% £38,517 £117,359
    AHTS DUTIES AHTS > 22,000 BHP £96,015 £16,024 +499.19% £34,237 £195,598
    """
    rows = extract_osv_rates_from_text(sample_text, "2026-08-01", "Market Report August 2026")
    assert len(rows) == 4
    categories = [r["category"] for r in rows]
    assert "SUPPLY DUTIES PSVS < 900M2" in categories
    assert "AHTS DUTIES AHTS > 22,000 BHP" in categories

    cape_row = next(r for r in rows if r["category"] == "AHTS DUTIES AHTS > 22,000 BHP")
    assert cape_row["avg_dayrate_gbp"] == 96015
    assert cape_row["prev_year_dayrate_gbp"] == 16024
    assert cape_row["min_dayrate_gbp"] == 34237
    assert cape_row["max_dayrate_gbp"] == 195598
    assert cape_row["large_ahts_util"] == "73%"


def test_catalog_manifest():
    """Verify the generated catalog manifest has 97 verified reports."""
    assert os.path.exists(CATALOG_PATH_REPORTS), "Missing reports/seabrokers_catalog.json"
    with open(CATALOG_PATH_REPORTS, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert len(catalog) == 97, f"Expected 97 catalog entries, found {len(catalog)}"
    assert catalog[0]["date"] >= catalog[-1]["date"], "Catalog should be sorted descending by date"

    # Check that all entries have resolved PDF URLs and 200 status code
    resolved_entries = [e for e in catalog if e.get("pdf_url") and e.get("status_code") == 200]
    assert len(resolved_entries) == 97, f"Expected 97 resolved URLs, found {len(resolved_entries)}"

    # Check date range
    assert catalog[0]["date"].startswith("2026"), f"Latest date should be 2026, got {catalog[0]['date']}"
    assert catalog[-1]["date"].startswith("2018"), f"Earliest date should be 2018, got {catalog[-1]['date']}"


def test_markdown_digested_reports():
    """Verify that digested Markdown reports contain expected sections."""
    md_files = [f for f in os.listdir(SEABROKERS_REPORTS_DIR) if f.endswith(".md")]
    assert len(md_files) >= 6, f"Expected at least 6 digested markdown reports, found {len(md_files)}"

    sample_md = os.path.join(SEABROKERS_REPORTS_DIR, "2026-08-01_market-report-august-2026.md")
    assert os.path.exists(sample_md)
    with open(sample_md, "r", encoding="utf-8") as f:
        content = f.read()

    assert "# Market Report August 2026" in content
    assert "Seabrokers Chartering" in content
    assert "North Sea OSV Spot Rates & Fleet Utilisation" in content
    assert "Offshore Fleet S&P Transactions & Auctions" in content


def test_osv_dayrates_csv():
    """Verify extracted CSV data integrity."""
    assert os.path.exists(RATES_CSV_PATH), "Missing data/derived/seabrokers_osv_dayrates.csv"
    df = pd.read_csv(RATES_CSV_PATH)
    assert len(df) >= 24, f"Expected at least 24 rate records, found {len(df)}"

    required_cols = [
        "date", "report_month", "category", "avg_dayrate_gbp",
        "prev_year_dayrate_gbp", "yoy_change_pct", "min_dayrate_gbp", "max_dayrate_gbp"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing column {col} in CSV"

    assert df["avg_dayrate_gbp"].notnull().all()
    assert (df["avg_dayrate_gbp"] > 0).all()
