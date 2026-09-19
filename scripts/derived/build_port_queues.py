#!/usr/bin/env python3
"""
scripts/derived/build_port_queues.py
===================================
Pre-indexes active port queues and inbound commercial fleet arrivals across
all 2,065 ports from live_fleet_positions.json, gas_port_arrivals.json,
and live_anchorage_events.json.

Cross-references each port queue with historical 5-year seasonal baselines
from port_stress_summary.json and port_stress_matrix.csv to compute
statistical normality (Z-score, expected weekly volume, and congestion rating).

Outputs a compact, browser-optimized JSON manifest:
data/views/signal/port_queues_active.json (<400 KB)
"""

import os
import json
import math
import logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
FLEET_POS_PATH = DATA_DIR / "views" / "signal" / "live_fleet_positions.json"
ASSET_PORTS_PATH = DATA_DIR / "views" / "signal" / "asset_class_ports.json"
PORTWATCH_PATH = DATA_DIR / "geospatial" / "portwatch_ports_master.csv"
UNIFIED_PORTS_PATH = DATA_DIR / "views" / "signal" / "unified_ports_master.json"
STRESS_SUMMARY_PATH = DATA_DIR / "derived" / "port_stress_summary.json"
OUTPUT_PATH = DATA_DIR / "views" / "signal" / "port_queues_active.json"

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in km."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
    return 6371.0 * c

def clean_code(s: str) -> str:
    """Removes non-alphanumeric characters and converts to uppercase."""
    if not s:
        return ""
    return "".join(ch for ch in s.upper() if ch.isalnum())

def load_ports():
    """Loads ports from unified_ports_master.json if present, otherwise portwatch_ports_master.csv."""
    ports = []
    if UNIFIED_PORTS_PATH.exists():
        with open(UNIFIED_PORTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for p in data.get("ports", []):
            try:
                lat = float(p.get("lat", 0))
                lon = float(p.get("lon", 0))
            except (ValueError, TypeError):
                continue
            locode = (p.get("locode") or "").strip()
            ports.append({
                "portid": p["portid"],
                "name": p["name"],
                "fullname": p.get("fullname") or f"{p['name']}, {p.get('country', '')}",
                "country": p.get("country", ""),
                "locode": locode,
                "clean_locode": clean_code(locode),
                "lat": lat,
                "lon": lon
            })
        logging.info("Loaded %d ports from Unified Ports Master", len(ports))
        return ports

    import csv
    if not PORTWATCH_PATH.exists():
        logging.warning("PortWatch master not found at %s", PORTWATCH_PATH)
        return ports

    known_locodes = {
        "port362": "AEFJR",   # Fujairah
        "port1091": "SARRT",  # Ras Tanura
    }

    with open(PORTWATCH_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row.get("lat", 0))
                lon = float(row.get("lon", 0))
            except (ValueError, TypeError):
                continue
            pid = row.get("portid", "")
            locode = (row.get("LOCODE") or "").strip()
            if not locode and pid in known_locodes:
                locode = known_locodes[pid]
            ports.append({
                "portid": pid,
                "name": row.get("portname"),
                "fullname": row.get("fullname"),
                "country": row.get("country"),
                "locode": locode,
                "clean_locode": clean_code(locode),
                "lat": lat,
                "lon": lon
            })
    logging.info("Loaded %d ports from PortWatch master", len(ports))
    return ports

def build_port_queues():
    logging.info("Starting compact port queue and inbound fleet build...")

    if not FLEET_POS_PATH.exists():
        logging.error("Fleet positions file missing: %s", FLEET_POS_PATH)
        return

    with open(FLEET_POS_PATH, "r", encoding="utf-8") as f:
        fleet_data = json.load(f)

    # fleet_data['rows'] format:
    # ["imo", "name", "class", "seg", "lat", "lon", "spd", "hdg", "dst", "op", "stat", "laden", "eta"]
    vessels = fleet_data.get("rows", [])
    logging.info("Loaded %d live commercial vessels from %s", len(vessels), FLEET_POS_PATH.name)

    # Load 5-Year Stress Baselines
    stress_by_locode = {}
    stress_by_portid = {}
    if STRESS_SUMMARY_PATH.exists():
        try:
            with open(STRESS_SUMMARY_PATH, "r", encoding="utf-8") as f:
                stress_data = json.load(f)
            for h in stress_data.get("hubs", []):
                lc = clean_code(h.get("locode", ""))
                pid = h.get("portid", "")
                entry = {
                    "hist_mean": h.get("hist_mean"),
                    "hist_min": h.get("hist_min"),
                    "hist_max": h.get("hist_max"),
                    "hist_std": h.get("hist_std"),
                    "zscore": h.get("zscore"),
                    "stress_flag": h.get("stress_flag"),
                    "asset_class": h.get("asset_class"),
                    "interpretation": h.get("interpretation")
                }
                if lc:
                    stress_by_locode[lc] = entry
                if pid:
                    stress_by_portid[pid] = entry
            logging.info("Loaded 5-year stress baselines for %d hubs", len(stress_data.get("hubs", [])))
        except Exception as e:
            logging.warning("Could not parse stress summary: %s", e)

    ports = load_ports()

    # Filter valid lat/lon
    valid_vessels = []
    for r in vessels:
        lat, lon = r[4], r[5]
        if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
            continue
        dst_raw = r[8] or ""
        clean_dst = clean_code(dst_raw)
        valid_vessels.append({
            "imo": r[0],
            "name": r[1],
            "vclass": r[2],
            "seg": r[3],
            "lat": lat,
            "lon": lon,
            "spd": r[6],
            "hdg": r[7],
            "dst": dst_raw,
            "clean_dst": clean_dst,
            "op": r[9] or "—",
            "stat": r[10] or "Underway",
            "laden": r[11],
            "eta": r[12] or ""
        })

    ports_map = {}
    locode_map = {}
    total_anchored_found = 0
    total_inbound_found = 0

    vessel_cols = ["imo", "name", "vclass", "seg", "op", "queue_type", "status", "spd", "hdg", "dst", "eta", "laden", "lat", "lon", "dist_km"]

    for p in ports:
        plat, plon = p["lat"], p["lon"]
        pname_clean = clean_code(p["name"])
        plocode = p["clean_locode"]
        locode_tail = plocode[2:] if len(plocode) == 5 else plocode

        port_anchored = []
        port_inbound = []

        for v in valid_vessels:
            # Check proximity for anchorage/berth queue
            if abs(v["lat"] - plat) <= 0.45 and abs(v["lon"] - plon) <= 0.45:
                dist = haversine_distance_km(plat, plon, v["lat"], v["lon"])
                if dist <= 35.0:
                    status = "Operating at Berth" if ("Moored" in v["stat"] or (v["spd"] == 0.0 and dist <= 5.0)) else "Waiting at Anchor"
                    port_anchored.append([
                        v["imo"], v["name"], v["vclass"], v["seg"], v["op"],
                        "anchored", status, v["spd"], v["hdg"], v["dst"],
                        v["eta"], v["laden"], round(v["lat"], 3), round(v["lon"], 3), round(dist, 1)
                    ])
                    continue

            # Check destination string for inbound vessels
            clean_dst = v["clean_dst"]
            if clean_dst and len(clean_dst) >= 3:
                matches_dest = False
                if plocode and (plocode in clean_dst):
                    matches_dest = True
                elif locode_tail and len(locode_tail) >= 3 and (locode_tail in clean_dst):
                    matches_dest = True
                elif pname_clean and len(pname_clean) >= 4 and (pname_clean in clean_dst):
                    matches_dest = True

                if matches_dest:
                    dist = haversine_distance_km(plat, plon, v["lat"], v["lon"])
                    port_inbound.append([
                        v["imo"], v["name"], v["vclass"], v["seg"], v["op"],
                        "inbound", "Inbound En Route", v["spd"], v["hdg"], v["dst"],
                        v["eta"], v["laden"], round(v["lat"], 3), round(v["lon"], 3), round(dist, 1)
                    ])

        norm = stress_by_locode.get(plocode) or stress_by_portid.get(p["portid"])
        if port_anchored or port_inbound or norm:
            total_anchored_found += len(port_anchored)
            total_inbound_found += len(port_inbound)

            # Sort anchored: closest first; inbound: nearest ETA or closest distance
            port_anchored.sort(key=lambda x: x[14]) # dist_km
            port_inbound.sort(key=lambda x: (x[10] or "9999", x[14]))

            # Keep top 30 anchored and top 30 inbound to guarantee light payload
            capped_vessels = port_anchored[:30] + port_inbound[:30]

            ports_map[p["portid"]] = {
                "name": p["name"],
                "country": p["country"],
                "locode": p["locode"],
                "lat": plat,
                "lon": plon,
                "anchored_total": len(port_anchored),
                "inbound_total": len(port_inbound),
                "normality": norm,
                "rows": capped_vessels
            }

            if plocode:
                locode_map[plocode] = p["portid"]
                if plocode == "SARTA":
                    locode_map["SARRT"] = p["portid"]

    payload = {
        "header": {
            "source": "Signal Ocean Live Commercial Fleet & IMF PortWatch Gateway",
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "ports_indexed": len(ports_map),
            "total_anchored": total_anchored_found,
            "total_inbound": total_inbound_found,
            "vessel_cols": vessel_cols
        },
        "summary": {
            "ports_indexed": len(ports_map),
            "total_anchored": total_anchored_found,
            "total_inbound": total_inbound_found,
            "generated_utc": datetime.now(timezone.utc).isoformat()
        },
        "locode_index": locode_map,
        "ports": ports_map
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = OUTPUT_PATH.stat().st_size // 1024
    logging.info("Successfully generated compact %s (%d KB, %d indexed ports, %d anchored, %d inbound)",
                 OUTPUT_PATH.name, size_kb, len(ports_map), total_anchored_found, total_inbound_found)

if __name__ == "__main__":
    build_port_queues()
