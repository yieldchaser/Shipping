#!/usr/bin/env python3
"""
scripts/reference/build_benchmark_core_fleet.py
==============================================
Curates the 800-Hull Macro Benchmark Core Fleet from the global commercial registry.
These 800 strategic vessels carry >70% of global seaborne ton-miles across:
- Dry Bulk (250): 73 Valemax/Guaibamax mega-carriers + 177 Baltic 5TC Capesizes
- Tankers (250): 175 Modern VLCCs + 75 Modern Suezmaxes
- LNG (150): Qatar Q-Max/Q-Flex + Modern 174k CBM Two-Stroke export carriers
- LPG (150): Modern Very Large Gas Carriers (VLGCs)

Outputs:
  data/reference/benchmark_core_fleet.json
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GEO_DIR = REPO_ROOT / "data" / "geospatial"
REF_DIR = REPO_ROOT / "data" / "reference"


def load_registry(filename: str) -> List[Dict[str, Any]]:
    path = GEO_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_benchmark_fleet() -> Dict[str, Any]:
    REF_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Dry Bulk (Target: 250)
    dry_reg = load_registry("signal_vessels_dry_bulk.json")
    valemax = [
        v for v in dry_reg 
        if v.get("vesselClass") == "VLOC" and v.get("deadweight", 0) >= 350000 and v.get("imo")
    ]
    # Sort Valemax by DWT desc
    valemax.sort(key=lambda x: (x.get("deadweight", 0), x.get("yearBuilt", 0)), reverse=True)

    needed_capes = 250 - len(valemax)
    capes = [
        v for v in dry_reg
        if v.get("vesselClass") == "Capesize" and 170000 <= v.get("deadweight", 0) <= 190000 and v.get("imo")
    ]
    # Sort Capes by modern year built desc, then DWT desc
    capes.sort(key=lambda x: (x.get("yearBuilt", 0), x.get("deadweight", 0)), reverse=True)
    selected_capes = capes[:needed_capes]

    dry_bulk_fleet = valemax + selected_capes
    assert len(dry_bulk_fleet) == 250, f"Expected 250 Dry Bulk, got {len(dry_bulk_fleet)}"

    # 2. Tankers (Target: 250 -> 175 VLCC + 75 Suezmax)
    tanker_reg = load_registry("signal_vessels_tankers.json")
    vlccs = [
        v for v in tanker_reg
        if v.get("vesselClass") == "VLCC" and v.get("deadweight", 0) >= 295000 and v.get("imo")
    ]
    vlccs.sort(key=lambda x: (x.get("yearBuilt", 0), x.get("deadweight", 0)), reverse=True)
    selected_vlccs = vlccs[:175]

    suez = [
        v for v in tanker_reg
        if v.get("vesselClass") == "Suezmax" and 150000 <= v.get("deadweight", 0) <= 165000 and v.get("imo")
    ]
    suez.sort(key=lambda x: (x.get("yearBuilt", 0), x.get("deadweight", 0)), reverse=True)
    selected_suez = suez[:75]

    tanker_fleet = selected_vlccs + selected_suez
    assert len(tanker_fleet) == 250, f"Expected 250 Tankers, got {len(tanker_fleet)}"

    # 3. LNG (Target: 150)
    lng_reg = load_registry("signal_vessels_lng.json")
    lng_valid = [v for v in lng_reg if v.get("imo")]
    # Prioritize Q-Max/Q-Flex (high DWT) and modern export carriers
    lng_valid.sort(key=lambda x: (x.get("deadweight", 0), x.get("yearBuilt", 0)), reverse=True)
    lng_fleet = lng_valid[:150]
    assert len(lng_fleet) == 150, f"Expected 150 LNG, got {len(lng_fleet)}"

    # 4. LPG (Target: 150 VLGCs)
    lpg_reg = load_registry("signal_vessels_lpg.json")
    vlgcs = [
        v for v in lpg_reg
        if v.get("vesselClass") == "VLGC" and v.get("deadweight", 0) >= 50000 and v.get("imo")
    ]
    vlgcs.sort(key=lambda x: (x.get("yearBuilt", 0), x.get("deadweight", 0)), reverse=True)
    lpg_fleet = vlgcs[:150]
    assert len(lpg_fleet) == 150, f"Expected 150 LPG, got {len(lpg_fleet)}"

    # Build reference document
    fleet_catalog = {
        "metadata": {
            "title": "Macro Benchmark Core Fleet (800 Hulls)",
            "description": "Curated strategic merchant fleet tracking >70% of global seaborne ton-miles.",
            "total_hulls": 800,
            "sectors": {
                "dry_bulk": {
                    "count": len(dry_bulk_fleet),
                    "subclasses": {
                        "valemax_vloc": len(valemax),
                        "baltic_5tc_capesize": len(selected_capes)
                    },
                    "type_header": "3"
                },
                "tankers": {
                    "count": len(tanker_fleet),
                    "subclasses": {
                        "vlcc": len(selected_vlccs),
                        "suezmax": len(selected_suez)
                    },
                    "type_header": "1"
                },
                "lng": {
                    "count": len(lng_fleet),
                    "subclasses": {
                        "qmax_qflex_and_export_megi": len(lng_fleet)
                    },
                    "type_header": "5"
                },
                "lpg": {
                    "count": len(lpg_fleet),
                    "subclasses": {
                        "vlgc": len(lpg_fleet)
                    },
                    "type_header": "6"
                }
            }
        },
        "sectors": {
            "dry_bulk": [
                {
                    "imo": v["imo"],
                    "name": v.get("vesselName"),
                    "class": v.get("vesselClass"),
                    "dwt": v.get("deadweight"),
                    "built": v.get("yearBuilt"),
                    "operator": v.get("companyName") or v.get("synonyms")
                }
                for v in dry_bulk_fleet
            ],
            "tankers": [
                {
                    "imo": v["imo"],
                    "name": v.get("vesselName"),
                    "class": v.get("vesselClass"),
                    "dwt": v.get("deadweight"),
                    "built": v.get("yearBuilt"),
                    "operator": v.get("companyName") or v.get("synonyms")
                }
                for v in tanker_fleet
            ],
            "lng": [
                {
                    "imo": v["imo"],
                    "name": v.get("vesselName"),
                    "class": v.get("vesselClass"),
                    "dwt": v.get("deadweight"),
                    "built": v.get("yearBuilt"),
                    "operator": v.get("companyName") or v.get("synonyms")
                }
                for v in lng_fleet
            ],
            "lpg": [
                {
                    "imo": v["imo"],
                    "name": v.get("vesselName"),
                    "class": v.get("vesselClass"),
                    "dwt": v.get("deadweight"),
                    "built": v.get("yearBuilt"),
                    "operator": v.get("companyName") or v.get("synonyms")
                }
                for v in lpg_fleet
            ]
        }
    }

    # Verify uniqueness of all IMOs
    all_imos = []
    for s_name, s_vessels in fleet_catalog["sectors"].items():
        all_imos.extend([v["imo"] for v in s_vessels])
    assert len(all_imos) == 800, f"Expected 800 IMOs, got {len(all_imos)}"
    assert len(set(all_imos)) == 800, f"Found duplicate IMOs: {len(all_imos) - len(set(all_imos))}"

    out_file = REF_DIR / "benchmark_core_fleet.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(fleet_catalog, f, indent=2)

    logging.info("Saved %s with exactly 800 benchmark vessels (%d KB)", out_file.name, out_file.stat().st_size // 1024)
    return fleet_catalog


if __name__ == "__main__":
    build_benchmark_fleet()
