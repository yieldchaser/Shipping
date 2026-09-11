#!/usr/bin/env python3
"""
tests/test_bps_selection.py
===========================
Verifies that official Indonesian monthly coal export figures in
data/commodities/indonesia_coal_exports_monthly.csv match exactly when
re-derived from the raw Badan Pusat Statistik (BPS) API JSON responses
cached under data/commodities/.cache_bps_raw/.
"""

import csv
import json
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
CACHE_DIR = COMMODITIES_DIR / ".cache_bps_raw"
CSV_PATH = COMMODITIES_DIR / "indonesia_coal_exports_monthly.csv"

MONTH_MAP = {
    "01": "01", "02": "02", "03": "03", "04": "04", "05": "05", "06": "06",
    "07": "07", "08": "08", "09": "09", "10": "10", "11": "11", "12": "12",
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12"
}


def parse_month_str(bulan_str):
    m = re.search(r"\[(\d{2})\]", bulan_str)
    if m:
        return m.group(1)
    clean = bulan_str.lower().strip()
    return MONTH_MAP.get(clean, "01")


def test_bps_raw_cache_derivation_consistency():
    """Verify each monthly row in the CSV matches the aggregation of raw BPS records."""
    if not CACHE_DIR.exists():
        pytest.skip("BPS raw cache directory does not exist")

    cache_files = list(CACHE_DIR.glob("bps_coal_*.json"))
    if not cache_files:
        pytest.skip("No cached raw BPS responses found in .cache_bps_raw")

    assert CSV_PATH.exists(), f"{CSV_PATH} must exist"

    csv_rows = {}
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            csv_rows[r["date"]] = r

    rederived_months = 0

    for cfile in sorted(cache_files):
        with open(cfile, "r", encoding="utf-8") as f:
            payload = json.load(f)

        records = payload.get("data", [])
        if not records:
            continue

        monthly_totals = {}
        for r in records:
            tahun = str(r.get("tahun", "")).strip()
            bulan_raw = str(r.get("bulan", "")).strip()
            month = parse_month_str(bulan_raw)
            date_str = f"{tahun}-{month}-01"

            kodehs = str(r.get("kodehs", "")).strip()
            try:
                netweight = float(r.get("netweight", 0.0) or 0.0)
            except (ValueError, TypeError):
                continue

            if date_str not in monthly_totals:
                monthly_totals[date_str] = {
                    "bituminous_kg": 0.0,
                    "other_coal_kg": 0.0,
                    "lignite_kg": 0.0,
                }

            if "270112" in kodehs:
                monthly_totals[date_str]["bituminous_kg"] += netweight
            elif "2702" in kodehs:
                monthly_totals[date_str]["lignite_kg"] += netweight
            else:
                monthly_totals[date_str]["other_coal_kg"] += netweight

        for date_str, m in monthly_totals.items():
            if date_str not in csv_rows:
                continue

            expected_bitum_mt = round(m["bituminous_kg"] / 1e9, 2)
            expected_other_mt = round(m["other_coal_kg"] / 1e9, 2)
            expected_lignite_mt = round(m["lignite_kg"] / 1e9, 2)
            expected_headline_mt = round((m["bituminous_kg"] + m["other_coal_kg"]) / 1e9, 2)
            expected_seaborne_mt = round((m["bituminous_kg"] + m["other_coal_kg"] + m["lignite_kg"]) / 1e9, 2)

            actual = csv_rows[date_str]
            assert float(actual["bituminous_mt"]) == pytest.approx(expected_bitum_mt, abs=0.01)
            assert float(actual["other_coal_mt"]) == pytest.approx(expected_other_mt, abs=0.01)
            assert float(actual["lignite_mt"]) == pytest.approx(expected_lignite_mt, abs=0.01)
            assert float(actual["headline_coal_mt"]) == pytest.approx(expected_headline_mt, abs=0.01)
            assert float(actual["total_coal_and_lignite_mt"]) == pytest.approx(expected_seaborne_mt, abs=0.01)

            # Assert source_quote is clean (not invented text)
            assert actual.get("source_quote", "") == "", f"Row {date_str} source_quote must be empty"

            rederived_months += 1

    assert rederived_months > 0, f"Successfully re-derived and verified {rederived_months} monthly rows against raw BPS cache"
