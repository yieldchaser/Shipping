#!/usr/bin/env python3
"""
tests/test_loader_contracts.py
==============================
Static proof test for data loader contracts in index.html (Appendix A).

Validates:
1. SGX futures group (7 files): index.html checks row.settlement != null, but
   the files have no 'settlement' column (real header has 'price', 'expiry_date', etc.)
   and downstream parseSGXRows() requires raw row fields.
2. Table A1 (27 loaders): verifies every loader in index.html reads only columns
   that actually exist in the CSV file's header on disk.

Expected to FAIL on baseline code (27 broken loaders + SGX group).
"""

import csv
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"

SGX_FILES = [
    "data/futures/sgx_cape_futures.csv",
    "data/futures/sgx_panamax_futures.csv",
    "data/futures/sgx_supramax_futures.csv",
    "data/futures/sgx_handysize_futures.csv",
    "data/futures/sgx_iron_ore_fef.csv",
    "data/futures/sgx_iron_ore_m65f.csv",
    "data/futures/sgx_iron_ore_lump_lpf.csv",
]

# Appendix A Table A1: (relative_file_path, list_of_fields_read_that_are_missing)
TABLE_A1_LOADERS = [
    ("data/derived/time_charter_rates.csv", ["capesize", "handysize", "panamax", "supramax"]),
    ("data/derived/iron_ore_restocking.csv", ["days_of_use", "implied_burn_rate_mt", "inventory_mt", "mill_utilization_pct", "regime"]),
    ("data/derived/vessel_valuations.csv", ["age", "annual_earnings_m", "asset_value_m", "five_year_avg_pe", "pe_ratio", "sector"]),
    ("data/derived/scrappage_prices.csv", ["demo_volume_dwt", "price_per_ldt", "region", "subcontinent_avg"]),
    ("data/derived/time_charter_rates_fearnleys.csv", ["rate", "sector", "segment", "tenor"]),
    ("data/derived/intermodal_tc_rates.csv", ["rate", "sector", "segment", "tenor"]),
    ("data/derived/lpg_spot_rates.csv", ["rate", "route", "segment", "unit"]),
    ("data/derived/lpg_charter_rates.csv", ["rate", "segment", "tenor", "unit"]),
    ("data/derived/tanker_forward_curves.csv", ["change", "change_pct", "contract", "period_label", "rate", "route", "unit", "vessel_class"]),
    ("data/derived/tanker_forward_curves_history.csv", ["contract", "rate", "vessel_class"]),
    ("data/derived/lng_charter_rates.csv", ["nb_price_m_usd", "series_type", "tc_10y_usd_day", "tc_7y_usd_day"]),
    ("data/commodities/sgx_iron_ore_forward_curve.csv", ["change", "contract", "month_order", "open_interest", "settlement", "volume"]),
    ("data/indices/drewry_wci_historical.csv", ["los_angeles_shanghai", "new_york_rotterdam", "rotterdam_new_york", "shanghai_los_angeles", "shanghai_new_york"]),
    ("data/indices/fbx_historical.csv", ["fbx_global"]),
    ("data/derived/usda_grain_vessel_rates_japan.csv", ["rate_pnw", "rate_us_gulf", "spread_gulf_pnw"]),
    ("data/commodities/usda_us_vs_brazil_landed_costs.csv", ["brazil_paranagua_landed", "farmValue", "farm_value", "landedCost", "landed_cost", "landed_spread_us_minus_brazil", "totalCost", "total_cost", "us_gulf_landed"]),
    ("data/commodities/usda_grain_vessel_loading_queues.csv", ["total_vessels", "vessels_in_queue", "vessels_loading"]),
    ("data/derived/usda_bunker_fuel_daily.csv", ["vlsfo_houston", "vlsfo_new_orleans"]),
    ("data/commodities/brazil_comexstat_exports.csv", ["crude_oil_kt", "iron_ore_kt", "soybeans_kt"]),
    ("data/commodities/australia_ppa_iron_ore.csv", ["dampier_throughput_mt", "port_hedland_throughput_mt", "total_iron_ore_throughput_mt"]),
    ("data/commodities/major_miners_quarterly_shipments.csv", ["bhp_mt", "fmg_mt", "rio_tinto_mt", "total_major_miners_mt", "vale_mt"]),
    ("data/commodities/us_eia_weekly_crude_exports.csv", ["crude_exports_kbpd"]),
    ("data/derived/eu_ets_carbon_daily.csv", ["carbon_cost_per_ton_fuel_usd", "carbon_price_eur", "vlsfo_with_carbon_usd"]),
    ("data/derived/ton_mile_utilization_matrix.csv", ["cape_ton_miles_billion", "fleet_capacity_dwt_million", "fleet_utilization_pct", "ton_mile_demand_index"]),
    ("data/commodities/newcastle_coal_exports.csv", ["coal_exports_mt"]),
    ("data/commodities/australia_req_commodity_exports.csv", ["export_volume", "unit"]),
    ("data/congestion/portwatch_port_congestion.csv", ["daily_port_calls", "port_code", "port_name", "sector"])
]


def test_sgx_futures_loader_contracts():
    """Verify SGX futures CSV loaders in index.html match real file schema."""
    html_text = HTML_PATH.read_text(encoding="utf-8")
    
    # Check if index.html filters on settlement (which does not exist in the files)
    assert "row.settlement != null" not in html_text, (
        "SGX futures loader in index.html filters on row.settlement != null, "
        "but SGX CSV files have no 'settlement' column (real column is 'price')."
    )

    # Check each SGX file header
    for rel_path in SGX_FILES:
        csv_path = REPO_ROOT / rel_path
        assert csv_path.exists(), f"SGX file {rel_path} must exist"
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader, [])]
            assert "settlement" in header or "price" in header, f"{rel_path} missing price/settlement"


@pytest.mark.parametrize("file_path,missing_fields", TABLE_A1_LOADERS)
def test_table_a1_loader_contract(file_path, missing_fields):
    """Verify that each loader in Table A1 does not read fields missing from the CSV header."""
    csv_path = REPO_ROOT / file_path
    assert csv_path.exists(), f"File {file_path} must exist"

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader, [])]

    # Find which expected missing fields are absent from the real file header
    absent = [f for f in missing_fields if f not in header]
    
    # We inspect index.html to ensure it does not attempt to read these absent fields
    html_text = HTML_PATH.read_text(encoding="utf-8")
    
    # Locate the loader block for this file
    file_idx = html_text.find(file_path)
    assert file_idx != -1, f"Loader for {file_path} not found in index.html"
    loader_chunk = html_text[file_idx:file_idx + 1200]

    read_absent = []
    for fld in absent:
        if f"row.{fld}" in loader_chunk or f"row['{fld}']" in loader_chunk or f'row["{fld}"]' in loader_chunk:
            read_absent.append(fld)

    assert not read_absent, (
        f"Loader for {file_path} reads fields {read_absent} which do not exist in the file header: {header}"
    )


def test_loader_contracts_summary():
    """Summary test reporting total broken loader contracts against Appendix A."""
    html_text = HTML_PATH.read_text(encoding="utf-8")
    broken_loaders = []
    
    # Check SGX
    if "row.settlement != null" in html_text:
        broken_loaders.append("SGX group (7 files lack 'settlement')")

    # Check 27 loaders
    for file_path, missing_fields in TABLE_A1_LOADERS:
        csv_path = REPO_ROOT / file_path
        if not csv_path.exists():
            broken_loaders.append(file_path)
            continue
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            header = [h.strip() for h in next(csv.reader(f), [])]
        
        file_idx = html_text.find(file_path)
        if file_idx == -1:
            broken_loaders.append(file_path)
            continue
        chunk = html_text[file_idx:file_idx + 1200]
        absent_read = [f for f in missing_fields if f not in header and (f"row.{f}" in chunk or f"row['{f}']" in chunk or f'row["{f}"]' in chunk)]
        if absent_read:
            broken_loaders.append(f"{file_path}: reads missing {absent_read}")

    count_a1 = sum(1 for b in broken_loaders if not b.startswith("SGX"))
    sgx_broken = any(b.startswith("SGX") for b in broken_loaders)
    
    assert not broken_loaders, (
        f"Found {count_a1} broken Table A1 loaders + SGX group: {broken_loaders}"
    )
