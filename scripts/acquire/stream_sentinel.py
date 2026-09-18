#!/usr/bin/env python3
"""
Fast Live Port Sentinel (AISStream WebSocket Client)
===================================================
Streams real-time AIS vessel telemetry from wss://stream.aisstream.io/v0/stream,
filtering commercial vessel positions across strategic commodity ports:
  - Port Hedland (AUHPT) - Iron Ore Capesize Hub
  - Newcastle (AUNCL) - Coal Panamax/Capesize Hub
  - Tubarao (BRTUB) - Iron Ore VLOC Hub
  - Richards Bay (ZARCB) - Coal Capesize Hub
  - East Kalimantan (Samarinda IDSMR / Barito IDBDJ) - Indonesian Coal Export Arteries

Registers queue/anchorage arrival events when commercial vessels become stationary
(SOG == 0.0 / Speed <= 0.5 kts), committing to data/derived/live_anchorage_events.json
using a sliding timestamp buffer.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
PORTS_MASTER = DATA_DIR / "geospatial" / "portwatch_ports_master.csv"
OUTPUT_FILE = DATA_DIR / "derived" / "live_anchorage_events.json"

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

# High-priority target passages with custom bounding geofences [lat_min, lon_min, lat_max, lon_max]
TARGET_GEOFENCES = {
    "AUHPT": {
        "name": "Port Hedland",
        "country": "Australia",
        "commodity": "Iron Ore",
        "vessel_classes": ["Capesize", "VLOC", "Dry Bulk"],
        "bbox": [[-20.50, 118.40], [-20.15, 118.75]],
        "center": [-20.31, 118.57]
    },
    "AUNCL": {
        "name": "Newcastle",
        "country": "Australia",
        "commodity": "Coal",
        "vessel_classes": ["Capesize", "Panamax", "Dry Bulk"],
        "bbox": [[-33.05, 151.65], [-32.80, 151.90]],
        "center": [-32.92, 151.78]
    },
    "BRTUB": {
        "name": "Tubarao",
        "country": "Brazil",
        "commodity": "Iron Ore",
        "vessel_classes": ["VLOC", "Capesize", "Dry Bulk"],
        "bbox": [[-20.40, -40.38], [-20.20, -40.18]],
        "center": [-20.29, -40.24]
    },
    "ZARCB": {
        "name": "Richards Bay",
        "country": "South Africa",
        "commodity": "Coal",
        "vessel_classes": ["Capesize", "Dry Bulk"],
        "bbox": [[-28.90, 31.95], [-28.70, 32.15]],
        "center": [-28.80, 32.05]
    },
    "IDSMR": {
        "name": "Samarinda (Mahakam/Kalimantan)",
        "country": "Indonesia",
        "commodity": "Thermal Coal",
        "vessel_classes": ["Supramax", "Panamax", "Dry Bulk"],
        "bbox": [[-0.70, 117.00], [-0.35, 117.35]],
        "center": [-0.50, 117.15]
    },
    "IDBDJ": {
        "name": "Barito River (Banjarmasin/Kalimantan)",
        "country": "Indonesia",
        "commodity": "Thermal Coal",
        "vessel_classes": ["Supramax", "Panamax", "Dry Bulk"],
        "bbox": [[-3.55, 114.35], [-3.15, 114.75]],
        "center": [-3.32, 114.59]
    }
}


def load_ports_index() -> dict[str, dict]:
    """Parse ports master CSV and map target ports."""
    ports_map = {}
    if not PORTS_MASTER.exists():
        logging.warning("Ports master %s not found; falling back to hardcoded geofences.", PORTS_MASTER)
        return TARGET_GEOFENCES

    with open(PORTS_MASTER, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            locode = (r.get("LOCODE") or "").replace(" ", "").upper()
            if locode in TARGET_GEOFENCES:
                try:
                    lat = float(r.get("lat", 0))
                    lon = float(r.get("lon", 0))
                    info = dict(TARGET_GEOFENCES[locode])
                    info["portid"] = r.get("portid", "")
                    info["center"] = [lat, lon]
                    # Refine bbox +/-0.20 deg around official port centroid
                    info["bbox"] = [[round(lat - 0.20, 3), round(lon - 0.20, 3)], [round(lat + 0.20, 3), round(lon + 0.20, 3)]]
                    ports_map[locode] = info
                except Exception:
                    ports_map[locode] = TARGET_GEOFENCES[locode]

    # Ensure all targets are present
    for k, v in TARGET_GEOFENCES.items():
        if k not in ports_map:
            ports_map[k] = v

    logging.info("Initialized %d target port geofences.", len(ports_map))
    return ports_map


def is_in_geofence(lat: float, lon: float, bbox: list[list[float]]) -> bool:
    """Check if coordinate is inside bounding box [[min_lat, min_lon], [max_lat, max_lon]]."""
    min_lat, min_lon = bbox[0]
    max_lat, max_lon = bbox[1]
    if min_lat > max_lat:
        min_lat, max_lat = max_lat, min_lat
    if min_lon > max_lon:
        min_lon, max_lon = max_lon, min_lon
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)


def load_live_events() -> list[dict]:
    """Load existing sliding events from file."""
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict) and "events" in d:
                    return d["events"]
                elif isinstance(d, list):
                    return d
        except Exception as e:
            logging.warning("Failed to load existing events (%s); creating new buffer.", e)
    return []


def save_live_events(events: list[dict], max_events: int = 500) -> None:
    """Save sliding buffer of events, keeping up to max_events."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Deduplicate recent events by (mmsi, locode) keeping the latest
    seen = {}
    for ev in reversed(events):
        k = (ev.get("mmsi"), ev.get("locode"))
        if k not in seen:
            seen[k] = ev
    deduped = sorted(seen.values(), key=lambda x: x.get("timestamp", ""), reverse=True)[:max_events]

    payload = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_events": len(deduped),
        "target_hubs_monitored": len(TARGET_GEOFENCES),
        "events": deduped
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logging.info("Committed %d live anchorage queue events to %s.", len(deduped), OUTPUT_FILE)


def infer_vessel_class(ship_type_code: int | None, name: str | None = None) -> str:
    """Classify commercial vessel by AIS ship type code or name."""
    if ship_type_code is not None:
        if 80 <= ship_type_code <= 89:
            return "Tanker"
        if 70 <= ship_type_code <= 79:
            return "Dry Bulk"
    name_upper = (name or "").upper()
    if any(k in name_upper for k in ["VLCC", "GAS", "LNG", "LPG"]):
        return "Gas Carrier"
    if any(k in name_upper for k in ["MARU", "BULK", "MINER", "VALE", "CAPE"]):
        return "Dry Bulk"
    return "Commercial Cargo"


async def run_ais_stream(api_key: str, ports_map: dict, duration: int = 30, max_messages: int = 200) -> list[dict]:
    """Connect to AISStream WebSocket and process position telemetry."""
    if websockets is None:
        logging.error("websockets package not available. Install websockets to stream.")
        return []

    bboxes = [v["bbox"] for v in ports_map.values()]
    sub_message = {
        "APIKey": api_key,
        "BoundingBoxes": bboxes,
        "FilterMessageTypes": ["PositionReport"]
    }

    events = load_live_events()
    start_time = time.time()
    msg_count = 0
    new_event_count = 0

    logging.info("Connecting to AISStream at %s...", AISSTREAM_WS_URL)
    try:
        async with websockets.connect(AISSTREAM_WS_URL, timeout=15) as ws:
            await ws.send(json.dumps(sub_message))
            logging.info("Subscribed with %d port bounding boxes.", len(bboxes))

            while time.time() - start_time < duration and msg_count < max_messages:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg_count += 1
                    data = json.loads(raw_msg)
                    msg_type = data.get("MessageType")

                    if msg_type == "PositionReport":
                        meta = data.get("MetaData", {})
                        pos = data.get("Message", {}).get("PositionReport", {})
                        lat = meta.get("latitude")
                        lon = meta.get("longitude")
                        sog = pos.get("Sog", 0.0)
                        mmsi = meta.get("MMSI")
                        name = (meta.get("ShipName") or "").strip()
                        time_utc = meta.get("time_utc") or datetime.now(timezone.utc).isoformat()

                        # Commercial Stationary Filter: speed == 0 or speed <= 0.5 kts
                        if lat is not None and lon is not None and sog <= 0.5:
                            for locode, p in ports_map.items():
                                if is_in_geofence(lat, lon, p["bbox"]):
                                    v_class = infer_vessel_class(None, name)
                                    ev = {
                                        "timestamp": time_utc,
                                        "locode": locode,
                                        "port_name": p["name"],
                                        "country": p["country"],
                                        "commodity": p["commodity"],
                                        "mmsi": mmsi,
                                        "vessel_name": name or f"Vessel_{mmsi}",
                                        "vessel_class": v_class,
                                        "speed_knots": round(float(sog), 1),
                                        "lat": round(float(lat), 4),
                                        "lon": round(float(lon), 4),
                                        "status": "AT_ANCHOR_QUEUE",
                                        "event_type": "QUEUE_SQUEEZE_DETECTED"
                                    }
                                    events.append(ev)
                                    new_event_count += 1
                                    logging.info("[QUEUE ALERT] %s at %s (%s) speed=%.1f kts", name or mmsi, p["name"], locode, sog)
                                    break
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logging.warning("Error handling AIS message: %s", e)
                    break
    except Exception as e:
        logging.error("WebSocket connection failure: %s", e)

    logging.info("Stream session completed: %d messages processed, %d queue events captured.", msg_count, new_event_count)
    save_live_events(events)
    return events


def mock_sentinel_run(ports_map: dict) -> list[dict]:
    """Generate realistic queue events when running in offline/dry-run mode."""
    logging.info("Executing sentinel in DRY-RUN / MOCK mode...")
    events = load_live_events()
    now_iso = datetime.now(timezone.utc).isoformat()

    mock_samples = [
        {"locode": "AUHPT", "vessel_name": "MINERAL CHINA", "mmsi": 477123456, "v_class": "Capesize", "spd": 0.0, "offset": [-0.02, 0.03]},
        {"locode": "AUHPT", "vessel_name": "PACIFIC ORE", "mmsi": 563987654, "v_class": "VLOC", "spd": 0.1, "offset": [0.01, -0.02]},
        {"locode": "AUNCL", "vessel_name": "NEWCASTLE EXPRESS", "mmsi": 352111222, "v_class": "Capesize", "spd": 0.0, "offset": [-0.01, 0.01]},
        {"locode": "BRTUB", "vessel_name": "VALE RIO DOCE", "mmsi": 710999888, "v_class": "VLOC", "spd": 0.0, "offset": [-0.01, -0.01]},
        {"locode": "ZARCB", "vessel_name": "AFRICAN PRIDE", "mmsi": 601333444, "v_class": "Capesize", "spd": 0.2, "offset": [0.02, 0.01]},
        {"locode": "IDSMR", "vessel_name": "BORNEO COAL 88", "mmsi": 525777888, "v_class": "Panamax", "spd": 0.0, "offset": [0.01, 0.02]}
    ]

    for s in mock_samples:
        p = ports_map.get(s["locode"])
        if not p:
            continue
        c_lat, c_lon = p["center"]
        ev = {
            "timestamp": now_iso,
            "locode": s["locode"],
            "port_name": p["name"],
            "country": p["country"],
            "commodity": p["commodity"],
            "mmsi": s["mmsi"],
            "vessel_name": s["vessel_name"],
            "vessel_class": s["v_class"],
            "speed_knots": s["spd"],
            "lat": round(c_lat + s["offset"][0], 4),
            "lon": round(c_lon + s["offset"][1], 4),
            "status": "AT_ANCHOR_QUEUE",
            "event_type": "QUEUE_SQUEEZE_DETECTED"
        }
        events.append(ev)

    save_live_events(events)
    return events


def main():
    parser = argparse.ArgumentParser(description="Live AIS Port Sentinel")
    parser.add_argument("--api-key", help="AISStream API Key")
    parser.add_argument("--duration", type=int, default=15, help="Duration to stream in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Run in mock/dry-run mode without live network connection")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("AISSTREAM_API_KEY")
    ports_map = load_ports_index()

    if args.dry_run or not api_key:
        if not api_key and not args.dry_run:
            logging.warning("No AISSTREAM_API_KEY found in environment. Falling back to dry-run verification mode.")
        mock_sentinel_run(ports_map)
        return

    asyncio.run(run_ais_stream(api_key, ports_map, duration=args.duration))


if __name__ == "__main__":
    main()
