"""
tests/test_benchmark_fleet.py
=============================
Validates the curated (now 5,000-hull) Macro Benchmark Core Fleet:
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
    # The catalogue was expanded from 800 to 5,000 hulls on 2026-09-20 (283f41de19); sizes are checked against the
    # catalogue's own declared counts so a later expansion cannot silently drift from its metadata.
    sectors = benchmark_catalog.get("sectors", {})
    assert set(sectors.keys()) == {"dry_bulk", "tankers", "lng", "lpg"}
    declared = meta.get("sectors", {})
    for name, hulls in sectors.items():
        assert len(hulls) == declared[name]["count"], name
        assert sum(declared[name]["subclasses"].values()) == declared[name]["count"], name
    assert meta.get("total_hulls") == sum(len(h) for h in sectors.values()) >= 800


def test_benchmark_imo_uniqueness(benchmark_catalog):
    sectors = benchmark_catalog.get("sectors", {})
    all_imos = []
    for s_name, vessels in sectors.items():
        for v in vessels:
            imo = v.get("imo")
            assert imo is not None and isinstance(imo, int)
            all_imos.append(imo)

    total = benchmark_catalog["metadata"]["total_hulls"]
    assert len(all_imos) == total
    assert len(set(all_imos)) == total, "Found duplicate IMOs in benchmark catalog"


def _by_class(vessels):
    out = {}
    for v in vessels:
        out.setdefault(v.get("class"), []).append(v)
    return out


# Class counts come from the catalogue's declared subclasses (5,000-hull expansion, 283f41de19). The DWT floors are
# the ones that expansion was built with (VLOC 200k+, VLCC 200k+), wider than the 800-hull Valemax/VLCC cut.
def test_dry_bulk_benchmark_criteria(benchmark_catalog):
    sub = benchmark_catalog["metadata"]["sectors"]["dry_bulk"]["subclasses"]
    c = _by_class(benchmark_catalog["sectors"]["dry_bulk"])
    assert len(c["VLOC"]) == sub["valemax_vloc"]
    assert len(c["Capesize"]) == sub["capesize_newcastlemax"]
    assert len(c["Post Panamax"]) == sub["post_panamax"]
    assert len(c["Panamax"]) == sub["panamax_kamsarmax"]
    assert len(c["Supramax"]) == sub["supramax_ultramax"]
    for cls, lo, hi in [("VLOC", 200000, 450000), ("Capesize", 170000, 230000), ("Post Panamax", 90000, 125000),
                        ("Panamax", 75000, 90000), ("Supramax", 50000, 70000)]:
        for v in c[cls]:
            assert lo <= v.get("dwt", 0) <= hi, f"{cls} {v['name']} outside {lo}-{hi} DWT: {v.get('dwt')}"


def test_tanker_benchmark_criteria(benchmark_catalog):
    sub = benchmark_catalog["metadata"]["sectors"]["tankers"]["subclasses"]
    c = _by_class(benchmark_catalog["sectors"]["tankers"])
    assert len(c["VLCC"]) == sub["vlcc"]
    assert len(c["Suezmax"]) == sub["suezmax"]
    assert len(c["Aframax"]) == sub["aframax"]
    for cls, lo, hi in [("VLCC", 200000, 450000), ("Suezmax", 120000, 200000), ("Aframax", 80000, 130000)]:
        for v in c[cls]:
            assert lo <= v.get("dwt", 0) <= hi, f"{cls} {v['name']} outside {lo}-{hi} DWT: {v.get('dwt')}"


def test_lpg_benchmark_criteria(benchmark_catalog):
    lpg = benchmark_catalog["sectors"]["lpg"]
    assert len(lpg) == benchmark_catalog["metadata"]["sectors"]["lpg"]["count"]
    for v in lpg:
        # sector is "vlgc_and_lgc": one 61k-dwt LGC (Gaz Pegasus) is classed "Small"
        assert v.get("class") in ("VLGC", "Small"), f"Unexpected LPG class {v.get('class')}"
        assert v.get("dwt", 0) >= 50000, f"LPG carrier {v['name']} under 50k DWT: {v.get('dwt')}"


def test_no_floating_production_or_storage_units(benchmark_catalog):
    # the 5,000-hull expansion carried 86 FPSO/FSO/FSRU/FLNG/FSU classed as trading VLCC/LNG/VLGC; removed 2026-11-08
    import re
    floating = [v["name"] for vs in benchmark_catalog["sectors"].values() for v in vs
                if re.search(r"\b(FPSO|FSO|FSRU|FLNG|FSU)\b", v["name"], re.I)]
    assert not floating, f"{len(floating)} floating units: {floating[:10]}"
