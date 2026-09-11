#!/usr/bin/env python3
"""
Target 9 — Fleet Supply Side Ingestion & Orderbook Analytics Engine
==================================================================
Synthesizes the global commercial shipping supply side across:
1. Signal Ocean Commercial Fleet Records (57,256 commercial hulls on disk):
   - Classified by orderBookStatusID (status 7 = active fleet; 1, 2 = orderbook; 8 = scrapped; 4, 5, 6 = unresolved)
   - Derives age profile (0–4y, 5–9y, 10–14y, 15–19y, 20+y overage demolition pool)
   - Derives orderbook-to-fleet capacity ratios (% of fleet on order)
   - Computes delivery schedules by year (2026, 2027, 2028, 2029+)
   - Measures scrubber adoption rate across Capesize, Panamax, VLCC, and gas carriers
   - Orderbook is reported as recorded by Signal Ocean (coverage of unbuilt hulls is partial/indicative)

Outputs:
- data/supply/fleet_orderbook_and_age_profile.csv
- data/supply/merchant_fleet_summary.json
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GEOSPATIAL_DIR = REPO_ROOT / "data" / "geospatial"
SUPPLY_DIR = REPO_ROOT / "data" / "supply"
SUPPLY_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = SUPPLY_DIR / "fleet_orderbook_and_age_profile.csv"
OUT_JSON = SUPPLY_DIR / "merchant_fleet_summary.json"
MANIFEST_FILE = REPO_ROOT / "data" / "provenance" / "manifest.json"

CURRENT_YEAR = 2026

ASSET_CLASS_SPECS = [
    # Dry Bulk
    {"file": "signal_vessels_dry_bulk.json", "class_name": "Capesize", "filter_fn": lambda v: v.get("vesselClass") == "Capesize", "sector": "Dry Bulk"},
    {"file": "signal_vessels_dry_bulk.json", "class_name": "Panamax / Kamsarmax", "filter_fn": lambda v: v.get("vesselClass") == "Panamax", "sector": "Dry Bulk"},
    {"file": "signal_vessels_dry_bulk.json", "class_name": "Supramax / Ultramax", "filter_fn": lambda v: v.get("vesselClass") == "Supramax", "sector": "Dry Bulk"},
    {"file": "signal_vessels_dry_bulk.json", "class_name": "Handysize", "filter_fn": lambda v: v.get("vesselClass") == "Handysize", "sector": "Dry Bulk"},
    # Tankers
    {"file": "signal_vessels_tankers.json", "class_name": "VLCC", "filter_fn": lambda v: v.get("vesselClass") == "VLCC", "sector": "Crude Tanker"},
    {"file": "signal_vessels_tankers.json", "class_name": "Suezmax", "filter_fn": lambda v: v.get("vesselClass") == "Suezmax", "sector": "Crude Tanker"},
    {"file": "signal_vessels_tankers.json", "class_name": "Aframax / LR2", "filter_fn": lambda v: v.get("vesselClass") == "Aframax", "sector": "Crude / Product Tanker"},
    {"file": "signal_vessels_tankers.json", "class_name": "Panamax / LR1", "filter_fn": lambda v: v.get("vesselClass") == "Panamax", "sector": "Product Tanker"},
    {"file": "signal_vessels_tankers.json", "class_name": "MR2 Product Tanker", "filter_fn": lambda v: v.get("vesselClass") == "MR2", "sector": "Clean Product Tanker"},
    # Gas
    {"file": "signal_vessels_lng.json", "class_name": "LNG Carrier", "filter_fn": lambda v: True, "sector": "LNG Gas Carrier"},
    {"file": "signal_vessels_lpg.json", "class_name": "VLGC (Very Large Gas Carrier)", "filter_fn": lambda v: v.get("vesselClass") == "VLGC", "sector": "LPG Gas Carrier"},
]


def process_fleet_data():
    """Process micro fleet records across all vessel categories."""
    # Load datasets into memory
    loaded_files = {}
    for spec in ASSET_CLASS_SPECS:
        fname = spec["file"]
        if fname not in loaded_files:
            fpath = GEOSPATIAL_DIR / fname
            if not fpath.exists():
                logging.error("Source file missing: %s", fpath)
                sys.exit(1)
            with open(fpath, "r", encoding="utf-8") as f:
                loaded_files[fname] = json.load(f)
            logging.info("Loaded %d vessels from %s", len(loaded_files[fname]), fname)

    rows = []
    total_active_hulls = 0
    total_orderbook_hulls = 0
    total_fleet_dwt = 0.0
    total_orderbook_dwt = 0.0
    total_unresolved_hulls = 0
    total_scrapped_hulls = 0

    for spec in ASSET_CLASS_SPECS:
        c_name = spec["class_name"]
        sector = spec["sector"]
        all_vessels = loaded_files[spec["file"]]
        matched = [v for v in all_vessels if spec["filter_fn"](v)]

        if not matched:
            continue

        # Classify by orderBookStatusID per data/reference/signal_orderbook_status_map.json:
        # 7 -> active fleet
        # 1, 2 -> orderbook (orderbook as recorded by Signal Ocean)
        # 8 -> scrapped / dead (strictly excluded)
        # 4, 5, 6 -> unresolved (reported separately, excluded from active and orderbook)
        active = [v for v in matched if v.get("orderBookStatusID") == 7]
        orderbook = [v for v in matched if v.get("orderBookStatusID") in (1, 2)]
        unresolved = [v for v in matched if v.get("orderBookStatusID") in (4, 5, 6)]
        scrapped = [v for v in matched if v.get("orderBookStatusID") == 8]

        active_count = len(active)
        active_dwt = sum(float(v.get("deadweight") or 0.0) for v in active)
        total_active_hulls += active_count
        total_fleet_dwt += active_dwt

        # Age profiling for active fleet
        ages = [CURRENT_YEAR - v["yearBuilt"] for v in active if v.get("yearBuilt")]
        avg_age = round(sum(ages) / len(ages), 1) if ages else 0.0

        age_0_4 = sum(float(v.get("deadweight") or 0) for v in active if CURRENT_YEAR - (v.get("yearBuilt") or 0) < 5)
        age_5_9 = sum(float(v.get("deadweight") or 0) for v in active if 5 <= CURRENT_YEAR - (v.get("yearBuilt") or 0) < 10)
        age_10_14 = sum(float(v.get("deadweight") or 0) for v in active if 10 <= CURRENT_YEAR - (v.get("yearBuilt") or 0) < 15)
        age_15_19 = sum(float(v.get("deadweight") or 0) for v in active if 15 <= CURRENT_YEAR - (v.get("yearBuilt") or 0) < 20)
        age_20_plus = sum(float(v.get("deadweight") or 0) for v in active if CURRENT_YEAR - (v.get("yearBuilt") or 0) >= 20)

        # Orderbook metrics
        ob_count = len(orderbook)
        ob_dwt = sum(float(v.get("deadweight") or 0.0) for v in orderbook)
        total_orderbook_hulls += ob_count
        total_orderbook_dwt += ob_dwt

        total_unresolved_hulls += len(unresolved)
        total_scrapped_hulls += len(scrapped)

        ob_to_fleet_pct = round((ob_dwt / active_dwt) * 100, 1) if active_dwt > 0 else 0.0

        # Scheduled delivery profile
        deliv_2026 = sum(1 for v in orderbook if v.get("yearBuilt") == 2026)
        deliv_2027 = sum(1 for v in orderbook if v.get("yearBuilt") == 2027)
        deliv_2028 = sum(1 for v in orderbook if v.get("yearBuilt") == 2028)
        deliv_2029_plus = sum(1 for v in orderbook if (v.get("yearBuilt") or 0) >= 2029)

        # Scrubber penetration
        scrubbers_count = sum(1 for v in active if v.get("scrubbers") is True or v.get("scrubbers") == 1)
        scrubber_pct = round((scrubbers_count / active_count) * 100, 1) if active_count > 0 else 0.0

        rows.append({
            "vessel_segment": c_name,
            "sector": sector,
            "active_vessel_count": active_count,
            "active_dwt_million": round(active_dwt / 1e6, 2),
            "average_age_years": avg_age,
            "age_0_to_4_years_dwt_m": round(age_0_4 / 1e6, 2),
            "age_5_to_9_years_dwt_m": round(age_5_9 / 1e6, 2),
            "age_10_to_14_years_dwt_m": round(age_10_14 / 1e6, 2),
            "age_15_to_19_years_dwt_m": round(age_15_19 / 1e6, 2),
            "age_20_plus_years_dwt_m": round(age_20_plus / 1e6, 2),
            "orderbook_vessel_count": ob_count,
            "orderbook_dwt_million": round(ob_dwt / 1e6, 2),
            "orderbook_to_fleet_pct": ob_to_fleet_pct,
            "deliveries_2026_count": deliv_2026,
            "deliveries_2027_count": deliv_2027,
            "deliveries_2028_count": deliv_2028,
            "deliveries_2029_plus_count": deliv_2029_plus,
            "scrubber_fitted_pct": scrubber_pct,
            "status_unresolved_vessel_count": len(unresolved),
            "scrapped_excluded_vessel_count": len(scrapped),
            "source": "Signal Ocean Commercial Fleet (orderbook as recorded by Signal Ocean)",
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    logging.info("Saved %d asset classes to %s", len(df), OUT_CSV)

    # Master summary JSON
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status_mapping_reference": "data/reference/signal_orderbook_status_map.json",
        "signal_ocean_computed_fleet_metrics": {
            "total_commercial_tracked_hulls": sum(len(f) for f in loaded_files.values()),
            "primary_cargo_active_hulls": total_active_hulls,
            "primary_cargo_active_dwt_million": round(total_fleet_dwt / 1e6, 1),
            "total_orderbook_hulls_as_recorded": total_orderbook_hulls,
            "total_orderbook_dwt_million": round(total_orderbook_dwt / 1e6, 1),
            "aggregate_orderbook_to_fleet_pct": round((total_orderbook_dwt / total_fleet_dwt) * 100, 1) if total_fleet_dwt > 0 else 0.0,
            "total_unresolved_hulls": total_unresolved_hulls,
            "total_scrapped_hulls_excluded": total_scrapped_hulls,
        },
        "asset_classes": rows,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logging.info("Saved supply summary JSON to %s", OUT_JSON)

    # Update manifest
    update_manifest(df)


def update_manifest(df):
    """Update data/provenance/manifest.json."""
    if not MANIFEST_FILE.exists():
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    series_list = manifest.get("datasets", [])
    series_id = "supply_fleet_orderbook_and_age_profile"

    entry_data = {
        "series_id": series_id,
        "display_name": "Supply — Global Commercial Fleet Orderbook & Age Profile",
        "status": "LIVE",
        "source_name": "Signal Ocean Commercial Fleet",
        "source_url": "https://www.thesignalgroupp.com/",
        "fetch_method": "Signal Ocean Micro Commercial Fleet Analysis",
        "fetch_script": "scripts/acquire/fetch_fleet_supply.py",
        "output_file": "data/supply/fleet_orderbook_and_age_profile.csv",
        "row_count": len(df),
        "date_span": ["2026-01-01", "2032-12-31"],
        "last_fetched_utc": datetime.now(timezone.utc).isoformat(),
        "unit": "Hulls / Million DWT / Percent",
        "is_derived": False,
        "derivation": None,
        "notes": (
            f"Commercial fleet supply profile across {len(df)} primary asset classes. Synthesizes commercial hulls "
            f"classified by Signal Ocean orderBookStatusID (status 7 active fleet; status 1 & 2 orderbook as recorded "
            f"by Signal Ocean; status 8 scrapped ships excluded; status 4, 5, 6 unresolved). Tracking active deadweight, "
            f"age distribution (including >20y overage demolition pool), scheduled deliveries, and scrubber penetration."
        ),
    }

    existing = next((e for e in series_list if e.get("series_id") == series_id), None)
    if existing:
        existing.update(entry_data)
    else:
        series_list.append(entry_data)

    manifest["datasets"] = series_list
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logging.info("Updated manifest.json with series %s (%d rows)", series_id, len(df))


if __name__ == "__main__":
    process_fleet_data()
