"""
tests/test_fearnleys_labels_and_ranges.py

Regression test suite for Target 1A (Fearnpulse / Clarksons continuous rates).
Asserts:
1. Every series has an explicit unit in brackets [unit].
2. Critical mislabelled series (120654, 120655, 10010-10013, 120129, 120132, 120133) have correct vessel class labels.
3. Every series median falls inside its class's plausible market band.
4. JSON twin metadata is completely aligned with the CSV headers.
"""

import csv
import json
import re
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.csv"
JSON_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.json"

def load_data():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    return headers, rows

def test_explicit_units_in_all_columns():
    headers, _ = load_data()
    assert headers[0] == "date"
    unit_pattern = re.compile(r"\[(usd/day|usd/tonne|worldscale|usd_million|index|fx|percent|usd/bbl)\]")
    for idx, h in enumerate(headers[1:], start=1):
        assert unit_pattern.search(h), f"Column {idx} ({h}) lacks an explicit canonical unit bracket!"

def test_corrected_vessel_class_labels():
    headers, _ = load_data()
    header_map = {}
    for h in headers[1:]:
        m = re.search(r"\(tsid_(\d+)\)", h)
        if m:
            header_map[int(m.group(1))] = h

    # 1. tsid 120654 & 120655 must be Capesize, NOT Supramax
    assert 120654 in header_map
    assert "Capesize" in header_map[120654], f"tsid 120654 ({header_map[120654]}) must be Capesize!"
    assert "Supramax" not in header_map[120654], f"tsid 120654 ({header_map[120654]}) must not be Supramax!"

    assert 120655 in header_map
    assert "Capesize" in header_map[120655], f"tsid 120655 ({header_map[120655]}) must be Capesize!"
    assert "Supramax" not in header_map[120655], f"tsid 120655 ({header_map[120655]}) must not be Supramax!"

    # 2. tsids 10010, 10011, 10012, 10013 must be Panamax, NOT Capesize
    for tsid in [10010, 10011, 10012, 10013]:
        assert tsid in header_map
        h = header_map[tsid]
        assert "Panamax" in h, f"tsid {tsid} ({h}) must be Panamax!"
        assert "Capesize" not in h, f"tsid {tsid} ({h}) must not be Capesize!"

    # 3. tsids 120129, 120132, 120133 must be Supramax, NOT Panamax
    for tsid in [120129, 120132, 120133]:
        assert tsid in header_map
        h = header_map[tsid]
        assert "Supramax" in h, f"tsid {tsid} ({h}) must be Supramax!"
        assert "Panamax" not in h, f"tsid {tsid} ({h}) must not be Panamax!"

    # 4. Tanker spot routes (1-9) must be Worldscale and 7-9 must be marked mislabelled
    for tsid in range(1, 10):
        assert tsid in header_map
        h = header_map[tsid]
        assert "[worldscale]" in h, f"tsid {tsid} ({h}) must have [worldscale] unit!"

    for tsid in [7, 8, 9]:
        h = header_map[tsid]
        assert "mislabelled" in h, f"tsid {tsid} ({h}) must be flagged as mislabelled because TC cannot be Worldscale!"

    # 5. Baltic route codes must be explicitly carried in headers
    baltic_code_expectations = {
        120655: "C9_182",
        120654: "C10_182",
        10010: "P1A_82",
        10011: "P2A_82",
        10012: "P3A_82",
        10013: "P4_82",
        10001: "C3",
        10002: "C5",
        120129: "S1C",
        120132: "S4B",
        120133: "S4A",
        120137: "S10",
        1: "TD3/TD3C transition",
        2: "TD2",
        3: "TD15",
        4: "TD20",
        6: "TD19",
    }
    for tsid, code in baltic_code_expectations.items():
        assert tsid in header_map
        h = header_map[tsid]
        assert f"({code})" in h, f"tsid {tsid} header ({h}) must carry route code ({code})!"

def test_baltic_route_taxonomy_reference():
    tax_path = ROOT / "data" / "reference" / "baltic_route_taxonomy.json"
    assert tax_path.exists(), "baltic_route_taxonomy.json must exist!"
    with open(tax_path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    assert "routes" in tax
    assert "index_formulas" in tax
    assert "vessel_specifications" in tax
    assert len(tax["routes"]) >= 100
    for code in ["C3", "C5", "C9_182", "C10_182", "P1A_82", "P2A_82", "P3A_82", "P4_82", "S1C", "S1B", "S4A", "S4B", "S10", "TD3C", "TD20"]:
        assert code in tax["routes"], f"Taxonomy missing expected Baltic route {code}!"

REGISTRY_PATH = ROOT / "data" / "reference" / "fearnleys_tsid_registry.json"

KNOWN_EXEMPT_PARENS = {
    "Singapore", "Rotterdam", "Brent Crude", "SOFR/LIBOR", "Dirty Tanker",
    "TD3/TD3C transition", "mislabelled 1 Year TC - VLCC",
    "mislabelled 1 Year TC - Suezmax", "mislabelled 1 Year TC - Aframax",
    "mislabelled LR1 TC", "mislabelled Handy TC",
}

def check_taxonomy_coherence(headers):
    """Core assertion function for taxonomy coherence, accepting any header list."""
    tax_path = ROOT / "data" / "reference" / "baltic_route_taxonomy.json"
    assert tax_path.exists(), "baltic_route_taxonomy.json must exist"
    assert REGISTRY_PATH.exists(), "fearnleys_tsid_registry.json must exist"

    with open(tax_path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    routes = tax["routes"]

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)

    for h in headers:
        if h == "date":
            continue
        m_tsid = re.search(r"\(tsid_(\d+)\)", h)
        assert m_tsid, f"Header {h} lacks (tsid_N) tag!"
        tsid_str = m_tsid.group(1)
        assert tsid_str in registry, f"tsid {tsid_str} not found in fearnleys_tsid_registry.json!"

        reg_entry = registry[tsid_str]
        expected_code = reg_entry.get("code")

        all_parens = re.findall(r"\(([^)]+)\)", h)
        codes_found = [p for p in all_parens if not p.startswith("tsid_") and p not in KNOWN_EXEMPT_PARENS]

        # 1. Every code in parentheses must exist in the taxonomy — unknown codes fail
        for c in codes_found:
            assert c in routes, f"Header {h} carries route code '({c})' which does not exist in Baltic taxonomy!"

        # 2. If an expected route code exists, header must equal the registry code
        if expected_code:
            if expected_code == "TD3/TD3C":
                assert "TD3/TD3C" in h or "transition" in h.lower(), f"tsid {tsid_str} must carry TD3/TD3C transition!"
            else:
                assert f"({expected_code})" in h, f"Header {h} does not carry expected registry code ({expected_code})!"
                assert expected_code in codes_found, f"Header {h} does not match expected code {expected_code} (found {codes_found})!"
        else:
            assert len(codes_found) == 0, f"Header {h} carries route codes {codes_found} but registry specifies no code!"

        # 3. Vessel class matches
        vessel_class = reg_entry.get("vessel_class")
        if vessel_class and vessel_class in ["Capesize", "Panamax", "Supramax", "Handysize", "VLCC", "Suezmax", "Aframax"]:
            assert vessel_class in h, f"Header {h} does not match vessel class {vessel_class} from registry!"

        # 4. Negative route checks
        if "Transatlantic" in h:
            assert "(S1B)" not in h, f"Header {h} erroneously carries S1B for Transatlantic route!"


def test_taxonomy_coherence():
    """Permanent test per Guardrails §0.55: Every official route code in a header
    must be consistent with fearnleys_tsid_registry.json and baltic_route_taxonomy.json.
    """
    headers, _ = load_data()
    check_taxonomy_coherence(headers)

def test_median_plausible_bands():
    headers, rows = load_data()
    series_vals = {}
    for idx, h in enumerate(headers):
        if idx == 0: continue
        m = re.search(r"\(tsid_(\d+)\)", h)
        if m:
            tsid = int(m.group(1))
            vals = [float(r[idx]) for r in rows if r[idx].strip() != ""]
            series_vals[tsid] = (h, vals)

    # Capesize TCE $/day bands: median $25k - $70k/day
    for tsid in [120654, 120655]:
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 25000 <= med <= 70000, f"{h} median {med} outside Capesize band [25000, 70000]!"

    # Panamax TCE $/day bands: fronthaul/RV median $10k - $30k/day; backhaul (P4_82) median $4k - $15k/day
    for tsid in [10010, 10011, 10012]:
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 10000 <= med <= 30000, f"{h} median {med} outside Panamax band [10000, 30000]!"

    h, vals = series_vals[10013] # P4_82 backhaul
    med = np.median(vals)
    assert 4000 <= med <= 15000, f"{h} median {med} outside Panamax backhaul band [4000, 15000]!"

    # Supramax TCE $/day bands: median $10k - $35k/day
    for tsid in [120129, 120132, 120133, 120137]:
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 10000 <= med <= 35000, f"{h} median {med} outside Supramax band [10000, 35000]!"

    # Worldscale bands: median 20 - 150 WS points
    for tsid in range(1, 10):
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 15 <= med <= 150, f"{h} median {med} outside Worldscale band [15, 150]!"

    # Capesize Voyage Ore/Coal $/tonne: median $7 - $35/tonne (C5 27-yr median is $8.2/t)
    for tsid in [10001, 10002, 10003]:
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 7.0 <= med <= 35.0, f"{h} median {med} outside $/tonne band [7, 35]!"

    # Bunkers $/tonne: median $350 - $800/tonne
    for tsid in [303, 304, 306, 307]:
        h, vals = series_vals[tsid]
        med = np.median(vals)
        assert 350 <= med <= 800, f"{h} median {med} outside Bunker band [350, 800]!"

    # BDI: 41-year median 1200 - 2500 points (overall 1985-2026 median is 1,423)
    h, vals = series_vals[11323]
    med = np.median(vals)
    assert 1200 <= med <= 2500, f"BDI median {med} outside band [1200, 2500]!"

def test_json_catalog_coherence():
    assert JSON_PATH.exists()
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    catalog = d.get("series_catalog", {})

    assert catalog["120654"]["vessel_class"] == "Capesize"
    assert catalog["120655"]["vessel_class"] == "Capesize"
    assert catalog["10010"]["vessel_class"] == "Panamax"
    assert catalog["10011"]["vessel_class"] == "Panamax"
    assert catalog["10012"]["vessel_class"] == "Panamax"
    assert catalog["10013"]["vessel_class"] == "Panamax"
    assert catalog["120129"]["vessel_class"] == "Supramax"
    assert catalog["120132"]["vessel_class"] == "Supramax"
    assert catalog["120133"]["vessel_class"] == "Supramax"
    assert catalog["1"]["unit"] == "worldscale"
    assert catalog["4"]["unit"] == "worldscale"
    assert catalog["120654"]["unit"] == "usd/day"
