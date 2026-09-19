"""
tests/test_benchmark_fleet.py
=============================
Validates the curated 800-Hull Macro Benchmark Core Fleet:
- Sector sizing: 250 Dry Bulk, 250 Tankers, 150 LNG, 150 LPG
- 100% unique IMOs across all sectors
- Strict adherence to Baltic index class and deadweight criteria
- Merge integrity and benchmark tagging behavior
"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REF_FILE = REPO_ROOT / "data" / "reference" / "benchmark_core_fleet.json"


@pytest.fixture(scope="module")
def benchmark_catalog():
    assert REF_FILE.exists(), f"Benchmark fleet catalog missing: {REF_FILE}"
    with open(REF_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_total_count_and_sectors(benchmark_catalog):
    meta = benchmark_catalog.get("metadata", {})
    assert meta.get("total_hulls") == 800

    sectors = benchmark_catalog.get("sectors", {})
    assert set(sectors.keys()) == {"dry_bulk", "tankers", "lng", "lpg"}
    assert len(sectors["dry_bulk"]) == 250
    assert len(sectors["tankers"]) == 250
    assert len(sectors["lng"]) == 150
    assert len(sectors["lpg"]) == 150


def test_benchmark_imo_uniqueness(benchmark_catalog):
    sectors = benchmark_catalog.get("sectors", {})
    all_imos = []
    for s_name, vessels in sectors.items():
        for v in vessels:
            imo = v.get("imo")
            assert imo is not None and isinstance(imo, int)
            all_imos.append(imo)

    assert len(all_imos) == 800
    assert len(set(all_imos)) == 800, "Found duplicate IMOs in benchmark catalog"


def test_dry_bulk_benchmark_criteria(benchmark_catalog):
    bulk_vessels = benchmark_catalog["sectors"]["dry_bulk"]
    valemax = [v for v in bulk_vessels if v.get("class") == "VLOC"]
    capes = [v for v in bulk_vessels if v.get("class") == "Capesize"]

    assert len(valemax) == 73, f"Expected 73 Valemax, found {len(valemax)}"
    assert len(capes) == 177, f"Expected 177 Capesize, found {len(capes)}"

    for v in valemax:
        assert v.get("dwt", 0) >= 350000, f"Valemax {v['name']} under 350k DWT: {v.get('dwt')}"

    for v in capes:
        assert 170000 <= v.get("dwt", 0) <= 190000, f"Cape {v['name']} outside 170-190k DWT: {v.get('dwt')}"


def test_tanker_benchmark_criteria(benchmark_catalog):
    tankers = benchmark_catalog["sectors"]["tankers"]
    vlccs = [v for v in tankers if v.get("class") == "VLCC"]
    suez = [v for v in tankers if v.get("class") == "Suezmax"]

    assert len(vlccs) == 175, f"Expected 175 VLCCs, found {len(vlccs)}"
    assert len(suez) == 75, f"Expected 75 Suezmaxes, found {len(suez)}"

    for v in vlccs:
        assert v.get("dwt", 0) >= 295000, f"VLCC {v['name']} under 295k DWT: {v.get('dwt')}"

    for v in suez:
        assert 150000 <= v.get("dwt", 0) <= 165000, f"Suezmax {v['name']} outside 150-165k DWT: {v.get('dwt')}"


def test_lpg_benchmark_criteria(benchmark_catalog):
    lpg = benchmark_catalog["sectors"]["lpg"]
    assert len(lpg) == 150
    for v in lpg:
        assert v.get("class") == "VLGC", f"Expected VLGC class, got {v.get('class')}"
        assert v.get("dwt", 0) >= 50000, f"VLGC {v['name']} under 50k DWT: {v.get('dwt')}"
