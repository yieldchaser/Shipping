#!/usr/bin/env python3
"""
Build Unified Ports Master
==========================
Merges IMF PortWatch (2,065 ports) and Signal Ocean (2,752 commercial terminals)
into a unified, deduplicated canonical global master (~2,800 ports & terminals).
"""

import csv
import json
import math
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"c:\Users\Dell\Github\Shipping")
GEO_DIR = ROOT / "data" / "geospatial"
VIEWS_DIR = ROOT / "data" / "views" / "signal"
VIEWS_DIR.mkdir(parents=True, exist_ok=True)

PW_FILE = GEO_DIR / "portwatch_ports_master.csv"
SIGNAL_MAP_FILE = GEO_DIR / "signal_map_ports_master.json"
SIGNAL_ASSET_FILE = VIEWS_DIR / "asset_class_ports.json"
OUTPUT_FILE = VIEWS_DIR / "unified_ports_master.json"

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r'\b(port of|port|terminal|harbour|harbor|offshore|oil|berth)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def normalize_country(country: str) -> str:
    if not country:
        return ""
    c = country.lower().strip()
    c = re.sub(r'\b(the|republic of|kingdom of|state of)\b', '', c).strip()
    replacements = {
        'united states': 'usa', 'united states of america': 'usa',
        'united kingdom': 'uk', 'great britain': 'uk',
        'netherlands': 'netherlands', 'the netherlands': 'netherlands',
        'korea, republic of': 'south korea', 'korea': 'south korea',
        'uae': 'united arab emirates',
        'russia': 'russian federation'
    }
    return replacements.get(c, c)

CURATED_OVERRIDES = {
    3604: "port743",    # Kuwait (Signal 3604) <-> Mina Al Ahmadi (PortWatch port743)
    12770: "port1328",  # Tubarao (Signal 12770) <-> Tubarao (PortWatch port1328)
    3245: "port1160",   # Santos Brazil (Signal 3245) <-> Santos (PortWatch port1160)
    17690: "port2388",  # Sabine Pass (Signal 17690) <-> Sabine Pass (PortWatch port2388)
    3303: "port1069",   # Qingdao (Signal 3303) <-> Qingdao Port (PortWatch port1069)
    3853: "port481",    # Houston (Signal 3853) <-> Houston (US-TX) (PortWatch port481)
    3689: "port1114",   # Rotterdam (Signal 3689) <-> Rotterdam (PortWatch port1114)
    3754: "port1090",   # Ras Laffan (Signal 3754) <-> Ras Laffan (PortWatch port1090)
    3778: "port1091",   # Ras Tanura (Signal 3778) <-> Ras Tanura (PortWatch port1091)
    3153: "port362",    # Fujairah (Signal 3153) <-> Fujairah (PortWatch port362)
    3210: "port955",    # Port Hedland (Signal 3210) <-> Port Hedland (PortWatch port955)
    3209: "port276",    # Dampier (Signal 3209) <-> Dampier (PortWatch port276)
    3201: "port816",    # Newcastle (Signal 3201) <-> Newcastle (PortWatch port816)
    3204: "port398",    # Gladstone (Signal 3204) <-> Gladstone (PortWatch port398)
    3918: "port1099",   # Richards Bay (Signal 3918) <-> Richards Bay (PortWatch port1099)
    3845: "port264",    # Corpus Christi (Signal 3845) <-> Corpus Christi (PortWatch port264)
    3659: "port149",    # Bintulu (Signal 3659) <-> Bintulu (PortWatch port149)
    3679: "port155",    # Bonny (Signal 3679) <-> Bonny (PortWatch port155)
}

def main():
    print("[INFO] Loading source datasets...")
    with open(PW_FILE, "r", encoding="utf-8") as f:
        pw_rows = list(csv.DictReader(f))
    print(f"  - PortWatch ports: {len(pw_rows)}")

    with open(SIGNAL_MAP_FILE, "r", encoding="utf-8") as f:
        signal_ports = json.load(f)
    print(f"  - Signal Ocean map terminals: {len(signal_ports)}")

    ac_map = {}
    if SIGNAL_ASSET_FILE.exists():
        with open(SIGNAL_ASSET_FILE, "r", encoding="utf-8") as f:
            ac_data = json.load(f)
            for ap in ac_data.get("ports", []):
                ac_map[ap[0]] = {
                    "dry_bulk": ap[5],
                    "tankers": ap[6],
                    "lng": ap[7],
                    "lpg": ap[8]
                }
    print(f"  - Signal asset-class readiness profiles: {len(ac_map)}")

    valid_signal_ports = []
    for sp in signal_ports:
        lat = sp.get("latitude")
        lon = sp.get("longitude")
        if lat is None or lon is None:
            continue
        if abs(lat) < 0.001 and abs(lon) < 0.001:
            continue
        valid_signal_ports.append(sp)
    print(f"  - Valid Signal Ocean terminals (non-zero coords): {len(valid_signal_ports)}")

    pw_by_id = {}
    pw_by_norm_name = {}
    for r in pw_rows:
        pid = r["portid"]
        lat = float(r["lat"]) if r.get("lat") else 0.0
        lon = float(r["lon"]) if r.get("lon") else 0.0
        r["_lat"] = lat
        r["_lon"] = lon
        pw_by_id[pid] = r

        nm = normalize_name(r.get("portname", ""))
        ctry = normalize_country(r.get("country", ""))
        if nm and ctry:
            pw_by_norm_name[(nm, ctry)] = pid

    matched_signal_to_pw = {}
    used_pw_ids = set()

    for sp in valid_signal_ports:
        s_id = sp["portID"]
        s_name = normalize_name(sp.get("portName", ""))
        s_ctry = normalize_country(sp.get("countryName", ""))
        s_lat = float(sp.get("latitude", 0.0))
        s_lon = float(sp.get("longitude", 0.0))

        if s_id in CURATED_OVERRIDES:
            target_pw = CURATED_OVERRIDES[s_id]
            if target_pw in pw_by_id:
                matched_signal_to_pw[s_id] = target_pw
                used_pw_ids.add(target_pw)
                continue

        if (s_name, s_ctry) in pw_by_norm_name:
            target_pw = pw_by_norm_name[(s_name, s_ctry)]
            matched_signal_to_pw[s_id] = target_pw
            used_pw_ids.add(target_pw)
            continue

        best_d = 999999.0
        best_pid = None
        for pid, r in pw_by_id.items():
            r_ctry = normalize_country(r.get("country", ""))
            if r_ctry == s_ctry:
                d = haversine(s_lat, s_lon, r["_lat"], r["_lon"])
                if d <= 20.0 and d < best_d:
                    best_d = d
                    best_pid = pid
        if best_pid:
            matched_signal_to_pw[s_id] = best_pid
            used_pw_ids.add(best_pid)

    print(f"[INFO] Cross-matched {len(matched_signal_to_pw)} Signal terminals to PortWatch hubs.")

    pw_to_signal = {}
    for s_id, pw_id in matched_signal_to_pw.items():
        pw_to_signal.setdefault(pw_id, []).append(s_id)

    signal_by_id = {sp["portID"]: sp for sp in valid_signal_ports}

    unified_catalog = []

    for r in pw_rows:
        pid = r["portid"]
        lat = r["_lat"]
        lon = r["_lon"]
        matched_sig_ids = pw_to_signal.get(pid, [])

        sectors = []
        if (int(r.get("vessel_count_dry_bulk", 0) or 0) > 0):
            sectors.append("dry_bulk")
        if (int(r.get("vessel_count_tanker", 0) or 0) > 0):
            sectors.append("tankers")
        if (int(r.get("vessel_count_container", 0) or 0) > 0):
            sectors.append("container")
        if (int(r.get("vessel_count_general_cargo", 0) or 0) > 0):
            sectors.append("general_cargo")
        if (int(r.get("vessel_count_RoRo", 0) or 0) > 0):
            sectors.append("roro")

        zoom_idx = 0.1
        shapes = []
        for s_id in matched_sig_ids:
            ac_info = ac_map.get(s_id, {})
            if ac_info.get("lng", 0) > 0.05 and "lng" not in sectors:
                sectors.append("lng")
            if ac_info.get("lpg", 0) > 0.05 and "lpg" not in sectors:
                sectors.append("lpg")
            if ac_info.get("dry_bulk", 0) > 0.05 and "dry_bulk" not in sectors:
                sectors.append("dry_bulk")
            if ac_info.get("tankers", 0) > 0.05 and "tankers" not in sectors:
                sectors.append("tankers")

            sig_obj = signal_by_id.get(s_id)
            if sig_obj:
                zoom_idx = max(zoom_idx, sig_obj.get("zoomIndex", 0.1))
                if sig_obj.get("shapes"):
                    shapes.extend(sig_obj["shapes"])

        entry = {
            "unified_id": pid,
            "portid": pid,
            "signal_port_ids": matched_sig_ids,
            "name": r.get("portname", ""),
            "fullname": r.get("fullname") or f"{r.get('portname', '')}, {r.get('country', '')}",
            "country": r.get("country", ""),
            "iso3": r.get("ISO3", ""),
            "continent": r.get("continent", ""),
            "locode": (r.get("LOCODE") or "").strip().upper(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "zoom_index": round(zoom_idx, 4),
            "sectors": sectors,
            "capabilities": {
                "has_portwatch_calls": True,
                "has_seasonal_baseline": True,
                "has_signal_polygons": len(shapes) > 0,
                "has_gas_readiness": ("lng" in sectors or "lpg" in sectors)
            },
            "calls_breakdown": {
                "total": int(r.get("vessel_count_total", 0) or 0),
                "dry_bulk": int(r.get("vessel_count_dry_bulk", 0) or 0),
                "tankers": int(r.get("vessel_count_tanker", 0) or 0),
                "container": int(r.get("vessel_count_container", 0) or 0),
                "general_cargo": int(r.get("vessel_count_general_cargo", 0) or 0),
                "roro": int(r.get("vessel_count_RoRo", 0) or 0)
            },
            "shapes": shapes
        }
        unified_catalog.append(entry)

    unmatched_count = 0
    for sp in valid_signal_ports:
        s_id = sp["portID"]
        if s_id in matched_signal_to_pw:
            continue

        unmatched_count += 1
        synthetic_id = f"so_{s_id}"
        s_name = sp.get("portName", "").strip()
        s_ctry = sp.get("countryName", "").strip()
        s_lat = round(float(sp.get("latitude", 0.0)), 5)
        s_lon = round(float(sp.get("longitude", 0.0)), 5)
        s_zoom = round(float(sp.get("zoomIndex", 0.1)), 4)
        shapes = sp.get("shapes", [])

        ac_info = ac_map.get(s_id, {})
        sectors = []
        if ac_info.get("dry_bulk", 0) > 0.05:
            sectors.append("dry_bulk")
        if ac_info.get("tankers", 0) > 0.05:
            sectors.append("tankers")
        if ac_info.get("lng", 0) > 0.05:
            sectors.append("lng")
        if ac_info.get("lpg", 0) > 0.05:
            sectors.append("lpg")
        if not sectors:
            sectors = ["tankers"]

        entry = {
            "unified_id": synthetic_id,
            "portid": synthetic_id,
            "signal_port_ids": [s_id],
            "name": s_name,
            "fullname": f"{s_name}, {s_ctry}",
            "country": s_ctry,
            "iso3": "",
            "continent": "",
            "locode": "",
            "lat": s_lat,
            "lon": s_lon,
            "zoom_index": s_zoom,
            "sectors": sectors,
            "capabilities": {
                "has_portwatch_calls": False,
                "has_seasonal_baseline": False,
                "has_signal_polygons": len(shapes) > 0,
                "has_gas_readiness": ("lng" in sectors or "lpg" in sectors)
            },
            "calls_breakdown": {
                "total": 0, "dry_bulk": 0, "tankers": 0,
                "container": 0, "general_cargo": 0, "roro": 0
            },
            "shapes": shapes
        }
        unified_catalog.append(entry)

    print(f"[INFO] Ingested {unmatched_count} unique Signal Ocean commercial terminals.")
    print(f"[INFO] Total canonical unified ports & terminals: {len(unified_catalog)}")

    unified_catalog.sort(key=lambda x: (x.get("zoom_index", 0), x.get("calls_breakdown", {}).get("total", 0)), reverse=True)

    payload = {
        "header": {
            "series_id": "unified_global_ports_master",
            "source": "IMF PortWatch & Signal Ocean Platform Combined Master",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_hubs": len(unified_catalog),
            "portwatch_coverage": len(pw_rows),
            "signal_coverage": len(valid_signal_ports),
            "signal_only_terminals": unmatched_count
        },
        "ports": unified_catalog
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(',', ':'), ensure_ascii=False)

    print(f"[SUCCESS] Wrote unified master to {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
