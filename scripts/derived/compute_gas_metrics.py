#!/usr/bin/env python3
"""
Cryogenic Gas Sector Matrix Interceptor
======================================
Processes live AIS fleet telemetry (Signal Ocean backdoor layer) to extract
cryogenic LNG and LPG vessels, computing real-time port presence via Haversine
intersection against the 2,065 IMF PortWatch master ports.

Syncs active arrival counts into data/derived/port_stress_summary.json, enabling
dynamic surge and collapse alerting for the Gas sector in Subview 7.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
FLEET_POSITIONS_FILE = DATA_DIR / "views" / "signal" / "live_fleet_positions.json"
PORTS_MASTER_FILE = DATA_DIR / "geospatial" / "portwatch_ports_master.csv"
PORT_STRESS_SUMMARY_FILE = DATA_DIR / "derived" / "port_stress_summary.json"
OUTPUT_GAS_FILE = DATA_DIR / "derived" / "gas_port_arrivals.json"

# Proximity threshold: vessel within 30 km (~16.2 NM) of port centroid
PORT_RADIUS_KM = 30.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def load_ports_master() -> list[dict]:
    """Load port catalog from PortWatch master CSV."""
    if not PORTS_MASTER_FILE.exists():
        logging.error("Ports master file %s missing!", PORTS_MASTER_FILE)
        return []

    ports = []
    with open(PORTS_MASTER_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                lat = float(r.get("lat") or 0)
                lon = float(r.get("lon") or 0)
                locode = (r.get("LOCODE") or "").replace(" ", "").upper()
                ports.append({
                    "portid": r.get("portid", ""),
                    "portname": r.get("portname", ""),
                    "country": r.get("country", ""),
                    "locode": locode,
                    "lat": lat,
                    "lon": lon
                })
            except Exception:
                continue
    logging.info("Loaded %d ports from master catalog.", len(ports))
    return ports


def load_gas_fleet_positions() -> list[dict]:
    """Load and extract live LNG and LPG carrier positions."""
    if not FLEET_POSITIONS_FILE.exists():
        logging.error("Fleet positions file %s missing!", FLEET_POSITIONS_FILE)
        return []

    with open(FLEET_POSITIONS_FILE, "r", encoding="utf-8") as f:
        fleet_data = json.load(f)

    cols = fleet_data.get("cols", [])
    rows = fleet_data.get("rows", [])
    try:
        imo_i = cols.index("imo")
        name_i = cols.index("name")
        class_i = cols.index("class")
        seg_i = cols.index("seg")
        lat_i = cols.index("lat")
        lon_i = cols.index("lon")
        spd_i = cols.index("spd")
        stat_i = cols.index("stat")
        op_i = cols.index("op")
        laden_i = cols.index("laden")
    except ValueError as e:
        logging.error("Missing expected columns in fleet positions: %s", e)
        return []

    gas_hulls = []
    for r in rows:
        seg = str(r[seg_i]).lower()
        cls_name = str(r[class_i]).lower()
        if "lng" in seg or "lng" in cls_name:
            gas_type = "LNG"
        elif "lpg" in seg or "lpg" in cls_name:
            gas_type = "LPG"
        else:
            continue

        lat = r[lat_i]
        lon = r[lon_i]
        spd = r[spd_i]
        if lat is None or lon is None:
            continue

        gas_hulls.append({
            "imo": r[imo_i],
            "name": r[name_i],
            "gas_type": gas_type,
            "lat": float(lat),
            "lon": float(lon),
            "speed": float(spd) if spd is not None else 0.0,
            "status": str(r[stat_i] or ""),
            "operator": str(r[op_i] or ""),
            "laden": int(r[laden_i]) if r[laden_i] is not None else 0
        })

    logging.info("Extracted %d live gas carriers (LNG/LPG).", len(gas_hulls))
    return gas_hulls


def compute_gas_port_intersections(gas_hulls: list[dict], ports: list[dict]) -> tuple[dict, list[dict]]:
    """Intersect stationary gas vessels with ports within PORT_RADIUS_KM."""
    # Stationary filter: speed <= 1.0 kts or status indicative of port dwell
    stationary_hulls = [
        v for v in gas_hulls
        if v["speed"] <= 1.0 or any(s in v["status"].lower() for s in ["anchor", "moored", "waiting", "berth"])
    ]
    logging.info("Filtering for stationary/berthing vessels: %d of %d active.", len(stationary_hulls), len(gas_hulls))

    port_arrivals_map = {}  # key: (locode, gas_type)
    matched_events = []

    for v in stationary_hulls:
        v_lat, v_lon = v["lat"], v["lon"]
        # Find closest port within radius
        best_port = None
        min_dist = float("inf")
        for p in ports:
            # Quick bounding box filter ±0.5° before haversine
            if abs(v_lat - p["lat"]) > 0.5 or abs(v_lon - p["lon"]) > 0.5:
                continue
            d = haversine_km(v_lat, v_lon, p["lat"], p["lon"])
            if d <= PORT_RADIUS_KM and d < min_dist:
                min_dist = d
                best_port = p

        if best_port:
            locode = best_port["locode"]
            gt = v["gas_type"]
            pair_key = (locode, gt)
            if pair_key not in port_arrivals_map:
                port_arrivals_map[pair_key] = {
                    "locode": locode,
                    "portname": best_port["portname"],
                    "country": best_port["country"],
                    "portid": best_port["portid"],
                    "asset_class": gt,
                    "vessels": [],
                    "count": 0
                }
            port_arrivals_map[pair_key]["count"] += 1
            port_arrivals_map[pair_key]["vessels"].append({
                "imo": v["imo"],
                "name": v["name"],
                "speed": v["speed"],
                "status": v["status"],
                "operator": v["operator"],
                "distance_km": round(min_dist, 1)
            })
            matched_events.append({
                "locode": locode,
                "portname": best_port["portname"],
                "asset_class": gt,
                "vessel_name": v["name"],
                "imo": v["imo"],
                "distance_km": round(min_dist, 1),
                "speed": v["speed"]
            })

    logging.info("Identified %d (port, gas_type) active terminal clusters.", len(port_arrivals_map))
    return port_arrivals_map, matched_events


def sync_gas_metrics_into_port_stress(port_arrivals_map: dict) -> dict:
    """Sync dynamic gas arrival counts into data/derived/port_stress_summary.json."""
    if not PORT_STRESS_SUMMARY_FILE.exists():
        logging.error("Target port stress summary %s missing!", PORT_STRESS_SUMMARY_FILE)
        return {}

    with open(PORT_STRESS_SUMMARY_FILE, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    hubs = summary_data.get("hubs", [])
    ports_series = summary_data.get("ports_series", {})
    now_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    updated_gas_count = 0
    for h in hubs:
        ac = h.get("asset_class")
        if ac not in ["LNG", "LPG"]:
            continue

        locode = h.get("locode", "").replace(" ", "").upper()
        pair_key = (locode, ac)
        matched_arrival = port_arrivals_map.get(pair_key)

        live_calls = float(matched_arrival["count"]) if matched_arrival else 0.0

        hist_mean = float(h.get("hist_mean") or 1.0)
        hist_std = float(h.get("hist_std") or 1.0)
        if hist_std <= 0:
            hist_std = 1.0

        prev_calls = float(h.get("weekly_calls") or 0.0)
        wow_change = round(live_calls - prev_calls, 1)
        zscore = round((live_calls - hist_mean) / hist_std, 2)

        if zscore >= 1.5:
            stress_flag = "SURGE"
            interpretation = f"Severe {ac} carrier berthing congestion; active terminal dwell elevation."
        elif zscore <= -1.5:
            stress_flag = "COLLAPSE"
            interpretation = f"Depressed {ac} carrier arrivals; terminal export maintenance or demand lull."
        else:
            stress_flag = "NORMAL"
            interpretation = f"Normal {ac} terminal operating envelope."

        h["weekly_calls"] = live_calls
        h["prev_calls"] = prev_calls
        h["wow_change"] = wow_change
        h["zscore"] = zscore
        h["stress_flag"] = stress_flag
        h["interpretation"] = interpretation
        h["latest_date"] = now_date_str

        # Update matching ports_series entry if present
        key = h.get("key")
        if key and key in ports_series:
            series_entry = ports_series[key]
            series_entry["metadata"] = h
            series_list = series_entry.get("series", [])
            if series_list:
                # Update or append latest point
                last_pt = series_list[-1]
                if last_pt.get("d") == now_date_str:
                    last_pt["c"] = live_calls
                    last_pt["z"] = zscore
                    last_pt["flag"] = stress_flag
                else:
                    series_list.append({
                        "d": now_date_str,
                        "c": live_calls,
                        "mean": round(hist_mean, 1),
                        "min": round(float(h.get("hist_min") or 0), 1),
                        "max": round(float(h.get("hist_max") or 0), 1),
                        "z": zscore,
                        "flag": stress_flag
                    })
            h["series_count"] = len(series_list)

        updated_gas_count += 1

    # Recalculate summary totals
    surge_count = sum(1 for h in hubs if h["stress_flag"] == "SURGE")
    collapse_count = sum(1 for h in hubs if h["stress_flag"] == "COLLAPSE")
    normal_count = sum(1 for h in hubs if h["stress_flag"] == "NORMAL")

    summary_data["summary"]["surge_alerts"] = surge_count
    summary_data["summary"]["collapse_alerts"] = collapse_count
    summary_data["summary"]["normal_hubs"] = normal_count
    summary_data["metadata"]["updated"] = now_date_str

    # Re-sort hubs by severity
    def sort_severity(h):
        flag = h["stress_flag"]
        z = h["zscore"]
        if flag == "SURGE":
            return (0, -z)
        elif flag == "COLLAPSE":
            return (1, z)
        return (2, -z)

    hubs.sort(key=sort_severity)

    with open(PORT_STRESS_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, separators=(",", ":"))

    logging.info("Successfully updated %d Gas hubs in %s (Surge: %d, Collapse: %d, Normal: %d).",
                 updated_gas_count, PORT_STRESS_SUMMARY_FILE, surge_count, collapse_count, normal_count)
    return summary_data


def main():
    parser = argparse.ArgumentParser(description="Cryogenic Gas Sector Matrix Interceptor")
    parser.parse_args()

    ports = load_ports_master()
    gas_hulls = load_gas_fleet_positions()
    if not ports or not gas_hulls:
        logging.error("Aborting gas metrics computation due to missing inputs.")
        sys.exit(1)

    port_arrivals_map, matched_events = compute_gas_port_intersections(gas_hulls, ports)

    # Save detailed gas port arrivals file
    OUTPUT_GAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    serializable_map = [
        {
            "locode": v["locode"],
            "portname": v["portname"],
            "country": v["country"],
            "asset_class": v["asset_class"],
            "count": v["count"],
            "vessels": v["vessels"]
        }
        for v in sorted(port_arrivals_map.values(), key=lambda x: x["count"], reverse=True)
    ]
    with open(OUTPUT_GAS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_gas_arrivals": len(matched_events),
            "ports_count": len(serializable_map),
            "ports": serializable_map
        }, f, indent=2)
    logging.info("Saved gas port arrivals breakdown to %s.", OUTPUT_GAS_FILE)

    # Sync into port_stress_summary.json
    sync_gas_metrics_into_port_stress(port_arrivals_map)


if __name__ == "__main__":
    main()
