#!/usr/bin/env python3
"""
Unit and Integration Tests for Cargo & Trade Flows frontend cache and data integrity.
Prompt 07 Verification.
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

def test_commodity_normalisation_reference():
    """Verify data/reference/commodity_normalisation.json schema and taxonomy."""
    norm_path = ROOT / "data" / "reference" / "commodity_normalisation.json"
    assert norm_path.exists(), f"Missing {norm_path}"
    with open(norm_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "version" in data
    assert "commodity_mappings" in data
    assert "region_mappings" in data

    mappings = data["commodity_mappings"]
    assert "grain" in mappings
    assert mappings["grain"]["group"] == "Agricultural Products"
    assert "iron ore" in mappings
    assert mappings["iron ore"]["group"] == "Ores and Rocks"
    assert "bauxite" in mappings
    assert mappings["bauxite"]["group"] == "Ores and Rocks"
    assert "thermal coal" in mappings
    assert mappings["thermal coal"]["group"] == "Energy"
    assert "crude oil" in mappings
    assert mappings["crude oil"]["group"] == "Tankers & Gas"

    regions = data["region_mappings"]
    assert "BRAZIL" in regions
    assert "AUSTRALIA" in regions
    assert "USG" in regions


def test_commodity_flow_matrix_structure_and_unclassified_bucket():
    """Verify commodity_flow_matrix.json contains explicit ~53% unclassified bucket."""
    matrix_path = ROOT / "data" / "cargo" / "commodity_flow_matrix.json"
    assert matrix_path.exists(), f"Missing {matrix_path}"
    with open(matrix_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "metadata" in data
    meta = data["metadata"]
    assert meta["total_fixtures"] == 540640
    assert meta["unclassified_fixtures"] > 250000
    # Must be between 50% and 55%
    assert 50.0 <= meta["unclassified_pct"] <= 55.0

    # Ensure unclassified group exists in groups
    groups = data["groups"]
    assert "Unclassified" in groups
    unclass = groups["Unclassified"]
    assert unclass["fixture_count"] == meta["unclassified_fixtures"]

    # Check top corridors and coverage catalog
    assert "top_corridors" in data
    assert len(data["top_corridors"]) > 0
    assert "coverage_catalog" in data
    assert len(data["coverage_catalog"]) >= 10


def test_cargo_frontend_summary_datasets():
    """Verify cargo_frontend_summary.json has all required primary datasets wired."""
    summary_path = ROOT / "data" / "cargo" / "cargo_frontend_summary.json"
    assert summary_path.exists(), f"Missing {summary_path}"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Flagship origin freight pairs
    assert "flagship_pairs" in data
    pairs = data["flagship_pairs"]
    for expected_key in ["brazil_c3", "pilbara_c5", "newcastle_coal", "usg_grain", "guinea_cape"]:
        assert expected_key in pairs, f"Missing pair: {expected_key}"
        pair = pairs[expected_key]
        assert "volume_data" in pair
        assert "freight_data" in pair
        assert "provenance" in pair
        assert len(pair["volume_data"]) > 0
        assert len(pair["freight_data"]) > 0

    # 2. Brazil exports
    assert "brazil_exports" in data
    assert "Iron Ore" in data["brazil_exports"]["envelopes"]

    # 3. Pilbara iron ore
    assert "pilbara_iron_ore" in data
    assert "hedland_envelope" in data["pilbara_iron_ore"]
    assert len(data["pilbara_iron_ore"]["miners_quarterly"]) > 0

    # 4. Newcastle coal
    assert "newcastle_coal" in data
    assert "envelope" in data["newcastle_coal"]

    # 5. US Crude exports
    assert "us_crude_exports" in data
    assert "envelope" in data["us_crude_exports"]

    # 6. USDA export commitments (68k rows sorted on read)
    assert "usda_export_commitments" in data
    assert data["usda_export_commitments"]["total_rows"] >= 65000
    assert len(data["usda_export_commitments"]["envelopes"]) > 0

    # 7. USDA grain inspections
    assert "usda_grain_inspections" in data
    assert "region_envelopes" in data["usda_grain_inspections"]

    # 8. USDA vessel loading queues
    assert "usda_loading_queues" in data
    assert "in_port_envelope" in data["usda_loading_queues"]

    # 9. Australia REQ quarterly forecasts
    assert "australia_req" in data
    assert len(data["australia_req"]["commodities"]) > 0

    # 10. Guinea bauxite mirror statistics
    assert "guinea_bauxite" in data
    guinea_prov = data["guinea_bauxite"]["provenance"]
    assert guinea_prov["status"] == "LIVE_MIRROR"
    assert guinea_prov["direct_source_status"] == "UNAVAILABLE"
    assert "Ministry of Mines" in guinea_prov["direct_source_attempted"]
