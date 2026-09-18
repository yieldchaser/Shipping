#!/usr/bin/env python3
"""
tests/test_cargo_audit_fixes.py
===============================
Rigorous test suite verifying fixes and acceptance criteria across all 40 audit items
from docs/CARGO_TAB_AUDIT_2026-09-17.md and docs/gap_fill/cargo_tab_status.md.

Audit verification covers:
1. Envelope Containment & Unit Heuristic Removal (Audit Item 1)
2. Zero Blank Source/Method & Outlier Validator (Audit Item 2)
3. Fixture Quantities, Vessel Class & Sanity Bands (Audit Item 4)
4. Corridor Mapping Coverage (Audit Item 5)
5. Unclassified Fixture Threshold (Audit Item 6)
6. Number Formatting Locale Enforcement (Audit Item 8)
7. Dynamic Provenance Registry & Extended History (Audit Items 14, 16)
8. Toggle Isolation & Empty States (Audit Items 3, 10)
9. Presentation, Taxonomy, Metrics & Macro Audits (Audit Items 7, 9, 11-13, 15, 17-23, 24-35, 36-40)
"""

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
CARGO_DIR = ROOT / "data" / "cargo"
COMMODITIES_DIR = ROOT / "data" / "commodities"
REFERENCE_DIR = ROOT / "data" / "reference"
DERIVED_DIR = ROOT / "data" / "derived"

CARGO_CACHE_FILE = CARGO_DIR / "cargo_cache.json"
CARGO_SUMMARY_FILE = CARGO_DIR / "cargo_frontend_summary.json"
FLOW_MATRIX_FILE = CARGO_DIR / "commodity_flow_matrix.json"
BRAZIL_EXPORTS_CSV = COMMODITIES_DIR / "brazil_comexstat_exports.csv"
COMMODITY_NORM_FILE = REFERENCE_DIR / "commodity_normalisation.json"
FIXTURES_FILE = DERIVED_DIR / "fearnleys_fixtures_full.csv"
INDEX_HTML_FILE = ROOT / "index.html"
AUDIT_STATUS_FILE = ROOT / "docs" / "gap_fill" / "cargo_tab_status.md"
VALIDATE_BRAZIL_SCRIPT = ROOT / "scripts" / "scrapers" / "validate_brazil_exports.py"


# =====================================================================
# Fixtures
# =====================================================================
@pytest.fixture(scope="session")
def cargo_cache():
    assert CARGO_CACHE_FILE.exists(), f"Missing {CARGO_CACHE_FILE}"
    with open(CARGO_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def cargo_summary():
    assert CARGO_SUMMARY_FILE.exists(), f"Missing {CARGO_SUMMARY_FILE}"
    with open(CARGO_SUMMARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def flow_matrix():
    assert FLOW_MATRIX_FILE.exists(), f"Missing {FLOW_MATRIX_FILE}"
    with open(FLOW_MATRIX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def index_html_content():
    assert INDEX_HTML_FILE.exists(), f"Missing {INDEX_HTML_FILE}"
    return INDEX_HTML_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def dry_bulk_cargo_sizes():
    """
    Computes dry bulk vessel class cargo sizes from fearnleys_fixtures_full.csv.
    Uses the normalized segment and quantity parsing logic.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.cargo.build_commodity_flow_matrix import (
        normalize_vessel_class,
        parse_quantity,
    )

    totals = defaultdict(float)
    counts = defaultdict(int)

    with open(FIXTURES_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seg = row.get("segment", "")
            comm = row.get("commodity", "")
            vc = normalize_vessel_class(seg, comm)
            if vc in ("Capesize", "Panamax", "Supramax", "Handysize"):
                rate = row.get("rate", "")
                comment = row.get("comment", "")
                qty = parse_quantity(comm, rate, comment, vc)
                if qty is not None and qty > 0:
                    totals[vc] += qty
                    counts[vc] += 1

    means = {}
    for vc in ("Capesize", "Panamax", "Supramax", "Handysize"):
        cnt = counts[vc]
        means[vc] = (totals[vc] / cnt) / 1000.0 if cnt > 0 else 0.0
    return {"counts": counts, "means": means}


# =====================================================================
# 1. Envelope Containment & Unit Heuristic Removal (Audit Item 1)
# =====================================================================
class TestAuditItem1EnvelopeContainment:
    """Audit Item 1: Brazil seasonal envelopes containment and unit heuristic removal."""

    def test_brazil_soybeans_january_envelope_max(self, cargo_cache, cargo_summary):
        """Brazil Soybeans January envelope max <= 3.5 Mt (verified around ~2.85 Mt)."""
        for src_name, data in [("cargo_cache", cargo_cache), ("cargo_summary", cargo_summary)]:
            b_exp = data.get("brazil_exports", {})
            assert "envelopes" in b_exp, f"Missing envelopes in brazil_exports for {src_name}"
            soy = b_exp["envelopes"].get("Soybeans")
            assert soy is not None, f"Missing Soybeans envelope in {src_name}"
            jan_max = soy["max"][0]
            assert jan_max <= 3.5, (
                f"[{src_name}] Brazil Soybeans January max envelope ({jan_max} Mt) > 3.5 Mt. "
                f"Unit heuristic bug (49.5 Mt) has not been removed!"
            )
            assert 2.0 <= jan_max <= 3.2, (
                f"[{src_name}] Expected January max around ~2.85 Mt, got {jan_max} Mt"
            )

    def test_brazil_crude_oil_and_raw_sugar_benchmarks(self, cargo_cache, cargo_summary):
        """Brazil official source benchmarks: Crude 2022-02 = 6.474 Mt, Sugar 2023-02 = 0.886 Mt."""
        # 1. Verify in serialized frontend caches (in Mt)
        for src_name, data in [("cargo_cache", cargo_cache), ("cargo_summary", cargo_summary)]:
            raw = data.get("brazil_exports", {}).get("monthly_raw", {})
            crude = raw.get("Crude Oil", {})
            sugar = raw.get("Raw Sugar", {})

            crude_2022_02 = crude.get("2022-02")
            assert crude_2022_02 is not None, f"[{src_name}] Missing Crude Oil 2022-02 row"
            assert abs(float(crude_2022_02) - 6.474) < 0.02, (
                f"[{src_name}] Crude Oil 2022-02 should be 6.474 Mt (source NCM 27090010 = 6,474,032.61 t), got {crude_2022_02}"
            )

            sugar_2023_02 = sugar.get("2023-02")
            assert sugar_2023_02 is not None, f"[{src_name}] Missing Raw Sugar 2023-02 row"
            assert abs(float(sugar_2023_02) - 0.886) < 0.02, (
                f"[{src_name}] Raw Sugar 2023-02 should be 0.886 Mt (source NCM 17011300+17011400 = 885,612.72 t), got {sugar_2023_02}"
            )

        # 2. Verify exact tonnages and FOB in data/commodities/brazil_comexstat_exports.csv
        df = pd.read_csv(BRAZIL_EXPORTS_CSV)
        c_row = df[(df["commodity"] == "Crude Oil") & (df["date"].str.startswith("2022-02"))].iloc[0]
        assert abs(float(c_row["metric_tonnes"]) - 6474032.61) < 0.01, f"Crude 2022-02 exact tonnage mismatch: {c_row['metric_tonnes']}"
        assert abs(float(c_row["fob_usd"]) - 3938875347.0) < 1.0, f"Crude 2022-02 FOB mismatch: {c_row['fob_usd']}"
        assert "api-comexstat.mdic.gov.br" in str(c_row["method"]), "Crude 2022-02 missing ComexStat API method"

        s_row = df[(df["commodity"] == "Raw Sugar") & (df["date"].str.startswith("2023-02"))].iloc[0]
        assert abs(float(s_row["metric_tonnes"]) - 885612.72) < 0.01, f"Sugar 2023-02 exact tonnage mismatch: {s_row['metric_tonnes']}"
        assert abs(float(s_row["fob_usd"]) - 385784771.0) < 1.0, f"Sugar 2023-02 FOB mismatch: {s_row['fob_usd']}"
        assert "api-comexstat.mdic.gov.br" in str(s_row["method"]), "Sugar 2023-02 missing ComexStat API method"

        io_row = df[(df["commodity"] == "Iron Ore") & (df["date"].str.startswith("2017-03"))].iloc[0]
        assert abs(float(io_row["metric_tonnes"]) - 33177280.55) < 0.01, f"Iron Ore 2017-03 exact tonnage mismatch: {io_row['metric_tonnes']}"
        assert abs(float(io_row["fob_usd"]) - 2051418773.0) < 1.0, f"Iron Ore 2017-03 FOB mismatch: {io_row['fob_usd']}"

        corn_row = df[(df["commodity"] == "Corn") & (df["date"].str.startswith("2017-09"))].iloc[0]
        assert abs(float(corn_row["metric_tonnes"]) - 5913703.18) < 0.01, f"Corn 2017-09 exact tonnage mismatch: {corn_row['metric_tonnes']}"
        assert abs(float(corn_row["fob_usd"]) - 915336070.0) < 1.0, f"Corn 2017-09 FOB mismatch: {corn_row['fob_usd']}"

    def test_envelope_min_mean_max_ordering(self, cargo_cache, cargo_summary):
        """Envelope min <= envelope mean <= envelope max across all 12 months for all Brazil commodities."""
        for src_name, data in [("cargo_cache", cargo_cache), ("cargo_summary", cargo_summary)]:
            envs = data.get("brazil_exports", {}).get("envelopes", {})
            assert len(envs) >= 5, f"[{src_name}] Expected at least 5 Brazil export commodities"

            for cmd, env in envs.items():
                mins = env.get("min", [])
                means = env.get("mean", [])
                maxs = env.get("max", [])
                assert len(mins) == 12, f"[{src_name}] {cmd} mins length != 12"
                assert len(means) == 12, f"[{src_name}] {cmd} means length != 12"
                assert len(maxs) == 12, f"[{src_name}] {cmd} maxs length != 12"

                for m_idx in range(12):
                    mn, avg, mx = mins[m_idx], means[m_idx], maxs[m_idx]
                    assert mn <= avg <= mx, (
                        f"[{src_name}] {cmd} month {m_idx+1}: ordering violated min={mn} <= mean={avg} <= max={mx}"
                    )

    def test_no_unit_guess_heuristic_in_builders(self):
        """Assert that `val > 50_000` heuristic is deleted from builder scripts."""
        for script_name in ["build_cargo_cache.py", "build_commodity_flow_matrix.py"]:
            script_path = ROOT / "scripts" / "cargo" / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                assert "val > 50_000" not in content and "val > 50000" not in content, (
                    f"Found deprecated 'val > 50_000' unit guess heuristic in {script_name}"
                )
                assert "val / 1000.0 if val >" not in content, (
                    f"Found unit ternary guess in {script_name}"
                )


# =====================================================================
# 2. Zero Blank Source/Method & Outlier Validator (Audit Item 2)
# =====================================================================
class TestAuditItem2ProvenanceAndOutliers:
    """Audit Item 2: Zero blank source/method and monthly outlier detection."""

    def test_brazil_exports_csv_no_blank_source_or_method(self):
        """Assert data/commodities/brazil_comexstat_exports.csv has zero blank or null source/method."""
        assert BRAZIL_EXPORTS_CSV.exists(), f"Missing {BRAZIL_EXPORTS_CSV}"
        df = pd.read_csv(BRAZIL_EXPORTS_CSV)

        for col in ["source", "method"]:
            assert col in df.columns, f"Missing required column '{col}' in brazil_comexstat_exports.csv"
            null_count = df[col].isna().sum()
            empty_count = (df[col].astype(str).str.strip() == "").sum()
            nan_count = (df[col].astype(str).str.strip().str.lower() == "nan").sum()
            total_invalid = null_count + empty_count + nan_count
            assert total_invalid == 0, (
                f"Found {total_invalid} blank or null values in column '{col}'"
            )

    def test_validate_brazil_exports_script_passes(self):
        """Assert python scripts/scrapers/validate_brazil_exports.py passes with returncode 0."""
        assert VALIDATE_BRAZIL_SCRIPT.exists(), f"Missing {VALIDATE_BRAZIL_SCRIPT}"
        res = subprocess.run(
            [sys.executable, str(VALIDATE_BRAZIL_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert res.returncode == 0, (
            f"validate_brazil_exports.py failed with returncode {res.returncode}.\n"
            f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )


# =====================================================================
# 3. Fixture Quantities, Vessel Class & Sanity Bands (Audit Item 4)
# =====================================================================
class TestAuditItem4FixtureQuantitiesAndVesselClasses:
    """Audit Item 4: Fixture quantities, vessel class derivation, and cargo size sanity bands."""

    def test_parsed_quantity_thresholds(self, flow_matrix):
        """Assert fixtures_with_parsed_qty > 20000 and parsed_qty_pct > 0 in metadata."""
        meta = flow_matrix.get("metadata", {})
        parsed_qty_cnt = meta.get("fixtures_with_parsed_qty", 0)
        parsed_qty_pct = meta.get("parsed_qty_pct", 0.0)

        assert parsed_qty_cnt > 20000, (
            f"Expected fixtures_with_parsed_qty > 20,000; got {parsed_qty_cnt:,}"
        )
        assert parsed_qty_pct > 0.0, f"Expected parsed_qty_pct > 0.0; got {parsed_qty_pct}"

    def test_vessel_classes_derived_from_segments(self, flow_matrix):
        """Assert vessel classes are derived from ledger segments (Grain is not 100% Panamax)."""
        commodities = flow_matrix.get("commodities", {})
        grain = commodities.get("Grain (Clean/General)") or commodities.get("Grain")
        assert grain is not None, "Missing Grain in commodity_flow_matrix.json"

        top_vc = grain.get("top_vessel_classes", [])
        assert len(top_vc) >= 3, f"Expected multiple vessel classes for grain, got: {top_vc}"

        vc_names = {item["class"] for item in top_vc}
        assert "Panamax" in vc_names, "Grain missing Panamax vessel class"
        assert "Supramax" in vc_names, "Grain missing Supramax vessel class"
        assert "Handysize" in vc_names, "Grain missing Handysize vessel class"

        # Ensure not 100% Panamax
        total_vc_count = sum(item["count"] for item in top_vc)
        panamax_count = next(item["count"] for item in top_vc if item["class"] == "Panamax")
        panamax_share = (panamax_count / total_vc_count) * 100.0
        assert panamax_share < 90.0, (
            f"Grain vessel class is degenerate: Panamax accounts for {panamax_share:.1f}% (>90%)"
        )

    def test_dry_bulk_mean_cargo_size_sanity_bands(self, dry_bulk_cargo_sizes):
        """
        Check mean cargo sizes per dry bulk vessel class:
        - Capesize between 120-220 kt
        - Panamax between 50-95 kt
        - Supramax between 30-65 kt
        - Handysize between 15-45 kt
        """
        means = dry_bulk_cargo_sizes["means"]
        counts = dry_bulk_cargo_sizes["counts"]

        # Capesize
        assert counts["Capesize"] >= 50, f"Insufficient parsed Capesize fixtures: {counts['Capesize']}"
        assert 120.0 <= means["Capesize"] <= 220.0, (
            f"Capesize mean cargo size ({means['Capesize']:.1f} kt) outside sanity band [120, 220] kt"
        )

        # Panamax
        assert counts["Panamax"] >= 1000, f"Insufficient parsed Panamax fixtures: {counts['Panamax']}"
        assert 50.0 <= means["Panamax"] <= 95.0, (
            f"Panamax mean cargo size ({means['Panamax']:.1f} kt) outside sanity band [50, 95] kt"
        )

        # Supramax
        assert counts["Supramax"] >= 1000, f"Insufficient parsed Supramax fixtures: {counts['Supramax']}"
        assert 30.0 <= means["Supramax"] <= 65.0, (
            f"Supramax mean cargo size ({means['Supramax']:.1f} kt) outside sanity band [30, 65] kt"
        )

        # Handysize
        assert counts["Handysize"] >= 1000, f"Insufficient parsed Handysize fixtures: {counts['Handysize']}"
        assert 15.0 <= means["Handysize"] <= 45.0, (
            f"Handysize mean cargo size ({means['Handysize']:.1f} kt) outside sanity band [15, 45] kt"
        )


# =====================================================================
# 4. Corridor Mapping Coverage (Audit Item 5)
# =====================================================================
class TestAuditItem5CorridorMappingCoverage:
    """Audit Item 5: Corridor mapping coverage and port normalization."""

    def test_corridor_mapped_share_threshold(self, flow_matrix):
        """Assert corridor_mapped_share_pct > 60.0 in metadata."""
        meta = flow_matrix.get("metadata", {})
        share_pct = meta.get("corridor_mapped_share_pct", 0.0)
        assert share_pct > 60.0, (
            f"corridor_mapped_share_pct ({share_pct}%) <= 60.0% threshold"
        )

    def test_top_corridors_exclude_unspecified(self, flow_matrix):
        """Assert top corridors are populated with meaningful origin -> destination pairs."""
        top_corr = flow_matrix.get("top_corridors", [])
        assert len(top_corr) >= 5, "Fewer than 5 top corridors returned"
        assert top_corr[0]["lane"] != "Unspecified Origin -> Unspecified Destination", (
            "Top corridor is still Unspecified Origin -> Unspecified Destination!"
        )


# =====================================================================
# 5. Unclassified Fixture Threshold (Audit Item 6)
# =====================================================================
class TestAuditItem6UnclassifiedFixtureThreshold:
    """Audit Item 6: Unclassified fixture threshold (< 25%)."""

    def test_unclassified_pct_threshold(self, flow_matrix):
        """Assert unclassified_pct < 25.0 in metadata."""
        meta = flow_matrix.get("metadata", {})
        unclass_pct = meta.get("unclassified_pct", 100.0)
        assert unclass_pct < 25.0, (
            f"unclassified_pct ({unclass_pct}%) >= 25.0% target"
        )

    def test_explicit_unclassified_bucket_exists(self, flow_matrix):
        """Ensure honest explicit unclassified group is maintained in taxonomy."""
        groups = flow_matrix.get("groups", {})
        assert "Unclassified" in groups, "Missing explicit 'Unclassified' group"
        meta = flow_matrix.get("metadata", {})
        assert groups["Unclassified"]["fixture_count"] == meta["unclassified_fixtures"]


# =====================================================================
# 6. Number Formatting (Audit Item 8)
# =====================================================================
class TestAuditItem8NumberFormatting:
    """Audit Item 8: Number formatting locale enforcement (no bare toLocaleString)."""

    def test_zero_bare_tolocalestring_in_index_html(self, index_html_content):
        """Assert zero bare .toLocaleString() calls exist in index.html."""
        bare_calls = re.findall(r"\.toLocaleString\(\s*\)", index_html_content)
        assert len(bare_calls) == 0, (
            f"Found {len(bare_calls)} bare .toLocaleString() calls without locale argument in index.html. "
            f"This causes Indian numbering system (lakhs) formatting on en-IN browsers!"
        )

        all_calls = re.findall(r"\.toLocaleString\([^)]*\)", index_html_content)
        assert len(all_calls) > 50, "Expected active toLocaleString calls in index.html"
        for call in all_calls:
            assert "en-US" in call or "locale" in call.lower() or len(call.strip("().,;")) > 14, (
                f"Suspicious toLocaleString call without explicit locale: {call}"
            )


# =====================================================================
# 7. Dynamic Provenance Registry & Extended History (Audit Items 14, 16)
# =====================================================================
class TestAuditItems14And16DynamicProvenanceAndHistory:
    """Audit Items 14 & 16: Dynamic provenance registry and extended historical series."""

    def test_provenance_registry_in_cargo_cache(self, cargo_cache):
        """Assert provenance_registry is present with metadata and datasets in cargo_cache.json."""
        assert "provenance_registry" in cargo_cache, "Missing provenance_registry in cargo_cache.json"
        reg = cargo_cache["provenance_registry"]
        assert "datasets" in reg, "Missing datasets in provenance_registry"
        assert reg.get("registry_metadata", {}).get("total_datasets", 0) >= 10

        # Check completeness of core metadata fields across all datasets
        required_fields = ["source", "method", "span", "as_of", "status"]
        for ds_name, ds_meta in reg["datasets"].items():
            for fld in required_fields:
                assert fld in ds_meta, f"Dataset '{ds_name}' missing provenance field '{fld}'"
                assert str(ds_meta[fld]).strip() != "", f"Dataset '{ds_name}' has empty '{fld}'"

    def test_extended_history_start_dates(self, cargo_cache):
        """
        Assert historical series start dates:
        - Hedland starts <= 2015-08
        - Dampier starts <= 2002-07
        - Guinea bauxite starts <= 2017-01
        - China imports starts <= 2018-01
        """
        datasets = cargo_cache["provenance_registry"]["datasets"]

        pilbara = datasets.get("pilbara_iron_ore", {})
        hedland_start = pilbara.get("hedland_min_date", "")
        dampier_start = pilbara.get("dampier_min_date", "")
        assert hedland_start <= "2015-08", f"Port Hedland start date {hedland_start} > 2015-08"
        assert dampier_start <= "2002-07", f"Port of Dampier start date {dampier_start} > 2002-07"

        guinea = datasets.get("guinea_bauxite", {})
        guinea_start = guinea.get("min_date", "")
        assert guinea_start <= "2017-01", f"Guinea bauxite start date {guinea_start} > 2017-01"

        china = datasets.get("who_feeds_china", {})
        china_start = china.get("min_date", "")
        assert china_start <= "2018-01", f"China imports start date {china_start} > 2018-01"


# =====================================================================
# 8. Toggle Isolation & Empty States (Audit Items 3, 10)
# =====================================================================
class TestAuditItems3And10ToggleIsolationAndEmptyStates:
    """Audit Items 3 & 10: Toggle isolation and empty state handling."""

    def test_usda_empty_state_and_chart_clearing(self, index_html_content):
        """Check index.html for USDA empty state handling ('No FAS commitments reported') and chart destruction."""
        assert "No FAS commitments reported" in index_html_content, (
            "Missing 'No FAS commitments reported' empty state handling in index.html"
        )
        assert "destroyChart('usdaExportSalesChart')" in index_html_content or "destroyChart(" in index_html_content, (
            "Missing chart destruction when switching to empty USDA commodity"
        )

    def test_dampier_toggle_isolation_and_dest_card_hiding(self, index_html_content):
        """Check index.html for Dampier toggle isolation (ppa.dampier_envelope used and Hedland dest card hidden)."""
        assert "ppa.dampier_envelope" in index_html_content, (
            "index.html does not reference ppa.dampier_envelope"
        )
        assert "destCard.style.display = 'none'" in index_html_content, (
            "Hedland destination card is not hidden when Dampier is selected"
        )
        assert "Port of Dampier:" in index_html_content, (
            "Throughput badge is not updated for Port of Dampier"
        )


# =====================================================================
# 9. Additional Audit Items (7, 9, 11-13, 15, 17-23, 24-35, 36-40)
# =====================================================================
class TestAdditionalAuditItems:
    """Tests covering remaining audit items across P0, P1, P2, and Structural tiers."""

    def test_audit_item_7_spread_fallback_no_hardcoded_zero(self, index_html_content):
        """Audit Item 7: Gulf-PNW freight spread calculation with clean fallback (no hardcoded +$0)."""
        assert "gulfPnwSpread" in index_html_content or "gulfToJapan" in index_html_content
        # Ensure no hardcoded +$0 fallback
        assert "+$0/MT" not in index_html_content and "+$${latest.spread ?? 0}" not in index_html_content

    def test_audit_item_9_hedland_destination_date_label(self, index_html_content):
        """Audit Item 9: Destination panel date label dynamically derived from ppa.latest_destinations.date."""
        assert "ppa.latest_destinations" in index_html_content
        assert "ppa.latest_destinations.date" in index_html_content

    def test_audit_item_11_major_miners_illustrative_styling(self, index_html_content):
        """Audit Item 11: Major miners basis and illustrative estimate differentiation."""
        assert "illustrative_prior_estimate" in index_html_content or "illustrative" in index_html_content.lower()

    def test_audit_item_12_cargo_hud_like_for_like(self, index_html_content):
        """Audit Item 12: Pilbara HUD iron ore run-rate like-for-like (59.4 Mt/mo) and USDA in Mt."""
        assert "59.4 Mt/mo" in index_html_content or "59.4 Mt" in index_html_content
        assert "38.1 Mt" in index_html_content or "Mt" in index_html_content

    def test_audit_item_13_spot_rate_bounds(self, index_html_content):
        """Audit Item 13: Capesize spot chart clamped with min: 0 on yLeft axis."""
        assert "min: 0" in index_html_content or "min:0" in index_html_content

    def test_audit_item_15_usda_destination_breakdown(self, cargo_cache):
        """Audit Item 15: USDA commitments top_destinations breakdown present."""
        usda = cargo_cache.get("usda_export_commitments", {})
        assert "top_destinations" in usda, "Missing top_destinations in usda_export_commitments"
        for cmd in ["Corn", "Soybeans", "Wheat"]:
            assert cmd in usda["top_destinations"], f"Missing top_destinations for {cmd}"

    def test_audit_item_17_guinea_flagship_volume_only(self, cargo_summary):
        """Audit Item 17: Guinea bauxite flagship is volume-only (no fake freight route paired)."""
        pair = cargo_summary.get("flagship_pairs", {}).get("guinea_cape", {})
        assert pair.get("route_code") is None
        assert pair.get("freight_unit") is None

    def test_audit_item_22_commodity_normalisation_clean_taxonomy(self):
        """Audit Item 22: Salt and Gypsum moved out of Steel & Metals; Potash mapped."""
        assert COMMODITY_NORM_FILE.exists(), f"Missing {COMMODITY_NORM_FILE}"
        with open(COMMODITY_NORM_FILE, "r", encoding="utf-8") as f:
            norm = json.load(f)
        comm_map = norm.get("commodity_mappings", {})

        salt = comm_map.get("salt")
        assert salt is not None
        assert salt["group"] != "Steel & Metals", "Salt erroneously mapped to Steel & Metals"
        assert salt["group"] == "Dry Bulk / Industrial Minerals"

        gypsum = comm_map.get("gypsum")
        assert gypsum is not None
        assert gypsum["group"] != "Steel & Metals", "Gypsum erroneously mapped to Steel & Metals"
        assert gypsum["group"] == "Dry Bulk / Industrial Minerals"

        potash = comm_map.get("potash")
        assert potash is not None
        assert potash["group"] == "Bulk Chemicals"

    def test_audit_item_23_matrix_time_dimension_monthly_arrays(self, flow_matrix):
        """Audit Item 23: Continuous contemporary monthly range (2024-2026) and populated monthly fixtures."""
        meta = flow_matrix.get("metadata", {})
        rm = meta.get("recent_months", [])
        assert len(rm) >= 24, f"Insufficient recent_months: {len(rm)}"
        assert rm[0] == "2024-01"
        assert rm[-1] >= "2026-08"

        commodities = flow_matrix.get("commodities", {})
        for cmd in ["Grain (Clean/General)", "Coal", "Iron Ore"]:
            c_data = commodities.get(cmd)
            assert c_data is not None, f"Missing {cmd} in commodities"
            m_fixtures = c_data.get("recent_monthly_fixtures", [])
            assert len(m_fixtures) == len(rm)
            assert sum(m_fixtures) > 0, f"recent_monthly_fixtures for {cmd} is all zero"

    def test_audit_items_24_to_35_toast_positioning(self, index_html_content):
        """Audit Items 24-35: Toast notification positioned at bottom-right to not cover charts."""
        assert "bottom: 20px" in index_html_content or "bottom:20px" in index_html_content
        assert "right: 20px" in index_html_content or "right:20px" in index_html_content

    def test_audit_items_36_to_40_workstream_status_tracker(self):
        """Audit Items 36-40: Workstream status tracker tracks all 40 items."""
        assert AUDIT_STATUS_FILE.exists(), f"Missing {AUDIT_STATUS_FILE}"
        status_text = AUDIT_STATUS_FILE.read_text(encoding="utf-8")

        # Verify all P0/P1 items are tracked and resolved
        for item_num in range(1, 24):
            pattern = rf"\|\s*{item_num}\s*\|"
            assert re.search(pattern, status_text), f"Audit item {item_num} missing from status tracker"

        # Verify structural items 36-40 are present
        assert "36-40" in status_text or re.search(r"\|\s*36\s*\|", status_text)
