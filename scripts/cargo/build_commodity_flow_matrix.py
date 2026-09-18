#!/usr/bin/env python3
"""
Build Commodity Flow Matrix & Coverage Analytics
Ingests 540,640+ Fearnleys fixtures, normalizes raw strings via commodity_normalisation.json,
and generates data/cargo/commodity_flow_matrix.json with multi-field classification,
clean vessel class derivation, quantity parsing & coverage tracking, port-to-region gazetteer,
and realistic cargo sizes.
"""

import csv
from datetime import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_FILE = ROOT / "data" / "derived" / "fearnleys_fixtures_full.csv"
NORM_FILE = ROOT / "data" / "reference" / "commodity_normalisation.json"
OUTPUT_FILE = ROOT / "data" / "cargo" / "commodity_flow_matrix.json"

# Regex for parsing quantities: ([\d,]+(?:\.\d+)?)\s*(MT|KT|CBM|BBLS)
QTY_REGEX = re.compile(r"([\d,]+(?:\.\d+)?)\s*(MT|KT|CBM|BBLS)\b", re.IGNORECASE)

# Cargo size bands (in MT) for sanity checks per vessel class
CARGO_SIZE_BANDS = {
    "Capesize": (120000, 220000),
    "Panamax": (55000, 90000),
    "Supramax": (30000, 65000),
    "Handysize": (15000, 40000),
    "VLCC": (250000, 330000),
    "Suezmax": (120000, 170000),
    "Aframax": (70000, 120000),
    "VLGC": (40000, 60000),
    "LNGC": (60000, 100000),
}

# Standard vessel class normalizer
SEGMENT_MAP = {
    "capesize": "Capesize", "newcastlemax": "Capesize", "babycape": "Capesize", "vloc": "Capesize",
    "panamax": "Panamax", "kamsarmax": "Panamax", "post-panamax": "Panamax",
    "supramax": "Supramax", "ultramax": "Supramax", "handymax": "Supramax",
    "handysize": "Handysize", "mini-handysize": "Handysize",
    "vlcc": "VLCC", "suezmax": "Suezmax", "aframax": "Aframax",
    "vlgc": "VLGC", "lgc": "Gas Carrier", "mgc": "Gas Carrier", "hgc": "Gas Carrier", "sgc": "Gas Carrier",
    "lngc": "LNGC", "flng": "LNGC", "fsru": "LNGC",
    "vehicles carrier": "Vehicles Carrier", "roro": "Vehicles Carrier"
}

re_opts = re.compile(r"^(?:opts?|options?)\s*[-—:]?\s*(.*)$", re.IGNORECASE)
re_slash = re.compile(r"^([^/\|]+)\s*/\s*([^/\|]+)")

# Multi-field keyword classifiers
re_grain = re.compile(r"\b(grain|grains|wheat|corn|maize|soy|soybean|soybeans|barley|sorghum|canola|oats|seed|seeds|feed|meal|tapioca)\b", re.IGNORECASE)
re_coal = re.compile(r"\b(coal|thermal coal|met coal|metallurgical coal|coking coal|anthracite)\b", re.IGNORECASE)
re_iron = re.compile(r"\b(iron\s*ore|ironore|fines|pellets?|lump|sinter)\b", re.IGNORECASE)
re_bauxite = re.compile(r"\b(bauxite|alumina)\b", re.IGNORECASE)
re_fert = re.compile(r"\b(fertilizer|fertilizers|urea|potash|mop|sop|phosphate|dap|map|sulphur|sulfur)\b", re.IGNORECASE)
re_petcoke = re.compile(r"\b(petcoke|coke|metcoke)\b", re.IGNORECASE)
re_cement = re.compile(r"\b(cement|clinker|slag|aggregates?)\b", re.IGNORECASE)
re_steel = re.compile(r"\b(steel|steels|scrap|hrc|billets|rebar|wire\s*rod|coils?|slabs?)\b", re.IGNORECASE)
re_minerals = re.compile(r"\b(salt|gypsum|limestone|silica|sand|barite|dolomite)\b", re.IGNORECASE)
re_ores = re.compile(r"\b(manganese|chrome|nickel|spodumene|lithium|copper\s*conc|zinc\s*conc)\b", re.IGNORECASE)
re_sugar = re.compile(r"\b(sugar|raw sugar|white sugar)\b", re.IGNORECASE)
re_breakbulk = re.compile(r"\b(box|boxshape|part\s*cargo|deck\s*cargo|general\s*cargo|breakbulk|heavy\s*cargo|pipes?|project|timber|wood|logs)\b", re.IGNORECASE)
re_grab = re.compile(r"\b(grabs?|grab-fitted|grabbed|geared|gearless|sd\s*gless|gless)\b", re.IGNORECASE)


def normalize_vessel_class(seg, comm=""):
    """
    Derives vessel class directly from the ledger's segment column and DWT where available.
    Never assigns vessel class based on commodity.
    """
    seg_clean = (seg or "").strip().lower()
    if seg_clean in SEGMENT_MAP:
        return SEGMENT_MAP[seg_clean]
    
    text = f"{seg} {comm}".lower()
    m_dwt = re.search(r"(\d{2,3}(?:,\d{3})?)\s*(?:k\b|kt\b|dwt\b)", text)
    if m_dwt:
        val_str = m_dwt.group(1).replace(",", "")
        try:
            dwt = float(val_str)
            if dwt < 500:
                dwt *= 1000.0
            if dwt >= 120000: return "Capesize"
            if dwt >= 65000: return "Panamax"
            if dwt >= 40000: return "Supramax"
            if dwt >= 10000: return "Handysize"
        except ValueError:
            pass
            
    if "cape" in text: return "Capesize"
    if "pana" in text: return "Panamax"
    if "supra" in text or "ultra" in text: return "Supramax"
    if "handy" in text: return "Handysize"
    if "vlcc" in text: return "VLCC"
    if "suez" in text: return "Suezmax"
    if "afra" in text: return "Aframax"
    if "vlgc" in text or "lpg" in text: return "VLGC"
    if "lng" in text: return "LNGC"
    
    return seg.strip() if seg.strip() else "General"


def parse_quantity(cmd, rate, comm, vessel_cls):
    """
    Parses cargo quantities and converts units to metric tonnes (MT):
    - KT * 1000, MT * 1
    - CBM LPG ~ 0.58 MT, CBM LNG ~ 0.45 MT
    - 1 BBL crude ~ 0.136 MT
    Sanity checks against crane capacities and bunkers per vessel class size bands.
    """
    for text in [cmd, rate]:
        if not text:
            continue
        m = QTY_REGEX.search(text)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                unit = m.group(2).upper()
                if unit == "KT":
                    qty = val * 1000.0
                elif unit == "CBM":
                    qty = val * 0.45 if vessel_cls == "LNGC" else val * 0.58
                elif unit == "BBLS":
                    qty = val * 0.136
                else:  # MT
                    band = CARGO_SIZE_BANDS.get(vessel_cls)
                    if band and val < 500 and (val * 1000.0 >= band[0] * 0.8):
                        qty = val * 1000.0
                    else:
                        qty = val
                return qty
            except (ValueError, IndexError):
                pass
                
    if comm:
        # Filter out crane ratings (e.g. "4x25mt cranes") and bunker specifications ("BOD ... 470 mt")
        clean_comm = re.sub(r"(?i)\b(?:\d+x\d+|\d+)\s*mt\s*cranes?\b", "", comm)
        clean_comm = re.sub(r"(?i)\bcranes?\s*(?:of)?\s*\d+\s*mt\b", "", clean_comm)
        clean_comm = re.sub(r"(?i)\bbod\b[^\,\|\n]*", "", clean_comm)
        clean_comm = re.sub(r"(?i)\blsfo[^\,\|\n]*", "", clean_comm)
        clean_comm = re.sub(r"(?i)\blsmgo[^\,\|\n]*", "", clean_comm)
        
        m = QTY_REGEX.search(clean_comm)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                unit = m.group(2).upper()
                if unit == "KT":
                    qty = val * 1000.0
                elif unit == "CBM":
                    qty = val * 0.45 if vessel_cls == "LNGC" else val * 0.58
                elif unit == "BBLS":
                    qty = val * 0.136
                else:
                    qty = val
                
                band = CARGO_SIZE_BANDS.get(vessel_cls)
                if band:
                    if band[0] * 0.5 <= qty <= band[1] * 1.5:
                        return qty
                    elif val < 500 and (val * 1000.0 >= band[0] * 0.7):
                        return val * 1000.0
                elif qty >= 1000.0:
                    return qty
            except (ValueError, IndexError):
                pass
    return None


def map_single_port(port_str, reg_map, reg_map_ci, is_discharge=False):
    """
    Normalizes a port or region string against the port gazetteer.
    Normalizes 'OPTS/Options/Opts X' to 'options — X region'.
    """
    if not port_str:
        return None
    p = port_str.strip()
    if not p:
        return None
        
    if is_discharge:
        m_opts = re_opts.match(p)
        if m_opts:
            target = m_opts.group(1).strip()
            if not target:
                return "options — Unspecified"
            info = reg_map.get(target) or reg_map_ci.get(target.lower())
            reg_name = info["region_name"] if info else target
            return f"options — {reg_name}"
            
    info = reg_map.get(p) or reg_map_ci.get(p.lower())
    if info:
        return info["region_name"]
    return p


def main():
    if not FIXTURES_FILE.exists():
        print(f"Error: Fixtures file not found: {FIXTURES_FILE}")
        sys.exit(1)

    with open(NORM_FILE, "r", encoding="utf-8") as f:
        norm_data = json.load(f)

    cmd_map = norm_data.get("commodity_mappings", {})
    reg_map = norm_data.get("region_mappings", {})
    reg_map_ci = {k.strip().lower(): v for k, v in reg_map.items()}

    total_fixtures = 0
    unclassified_count = 0
    classified_count = 0
    parsed_qty_count = 0
    corridor_mapped_count = 0

    # Aggregation structures
    by_commodity = defaultdict(lambda: {
        "fixture_count": 0,
        "parsed_qty_count": 0,
        "total_qty_mt": 0.0,
        "months": defaultdict(int),
        "trade_lanes": defaultdict(lambda: {"count": 0, "parsed_qty_count": 0, "total_qty_mt": 0.0}),
        "vessel_classes": defaultdict(int),
        "group": "",
        "subgroup": ""
    })

    by_group = defaultdict(lambda: {
        "fixture_count": 0,
        "parsed_qty_count": 0,
        "total_qty_mt": 0.0,
        "commodities": defaultdict(int),
        "trade_lanes": defaultdict(lambda: {"count": 0, "parsed_qty_count": 0, "total_qty_mt": 0.0}),
        "months": defaultdict(int)
    })

    by_corridor = defaultdict(lambda: {
        "fixture_count": 0,
        "parsed_qty_count": 0,
        "total_qty_mt": 0.0,
        "groups": defaultdict(int),
        "commodities": defaultdict(int)
    })

    monthly_totals = defaultdict(lambda: {"total": 0, "unclassified": 0, "classified": 0})

    print(f"Reading {FIXTURES_FILE}...")
    with open(FIXTURES_FILE, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_fixtures += 1
            date_str = (row.get("date") or "").strip()
            raw_cmd = (row.get("commodity") or "").strip()
            load_port = (row.get("load_port") or "").strip()
            discharge_port = (row.get("discharge_port") or "").strip()
            segment = (row.get("segment") or "").strip()
            rate = (row.get("rate") or "").strip()
            department = (row.get("department") or "").strip()
            comment = (row.get("comment") or "").strip()
            charterer = (row.get("charterer") or "").strip().lower()
            route = (row.get("route") or "").strip().upper()

            ym = date_str[:7] if len(date_str) >= 7 else "Unknown"

            # 1. Vessel class: Derived directly from segment and DWT
            vessel_cls = normalize_vessel_class(segment, comment)

            # 2. Quantity parsing & sanity check
            qty = parse_quantity(raw_cmd, rate, comment, vessel_cls)
            has_qty = qty is not None and qty > 0
            if has_qty:
                parsed_qty_count += 1
            else:
                qty = 0.0

            # 3. Multi-field Commodity Classification
            canonical = None
            group = None
            subgroup = None

            if raw_cmd:
                cleaned_cmd = QTY_REGEX.sub("", raw_cmd.lower()).strip()
                mapped = cmd_map.get(cleaned_cmd)
                if not mapped:
                    for k, v in cmd_map.items():
                        if k in cleaned_cmd:
                            mapped = v
                            break
                if mapped:
                    group = mapped["group"]
                    subgroup = mapped["subgroup"]
                    canonical = mapped["canonical"]
                else:
                    group = "Other Classified Cargo"
                    subgroup = "Specialized / Niche"
                    canonical = raw_cmd[:35]
            elif department == "LNG" or segment in ("LNGC", "FLNG", "FSRU"):
                canonical = "LNG"; group = "Tankers & Gas"; subgroup = "LNG"
            elif department == "LPG" or segment in ("VLGC", "SGC", "HGC", "MGC", "LGC"):
                canonical = "LPG"; group = "Tankers & Gas"; subgroup = "LPG"
            elif department == "TANK":
                canonical = "Crude Oil"; group = "Tankers & Gas"; subgroup = "Crude Oil"
            elif department == "TANKPRO":
                canonical = "Clean Petroleum Products (CPP)"; group = "Tankers & Gas"; subgroup = "CPP"
            elif department == "RoRo" or segment == "Vehicles Carrier":
                canonical = "Vehicles / Ro-Ro Cargo"; group = "General & Breakbulk"; subgroup = "Vehicles"
            elif route in ("C3", "C5", "C2"):
                canonical = "Iron Ore"; group = "Ores and Rocks"; subgroup = "Iron Ore"
            elif route in ("C4", "C7"):
                canonical = "Coal"; group = "Energy"; subgroup = "Coal"
            elif route.startswith("TD"):
                canonical = "Crude Oil"; group = "Tankers & Gas"; subgroup = "Crude Oil"
            elif route.startswith("TC"):
                canonical = "Clean Petroleum Products (CPP)"; group = "Tankers & Gas"; subgroup = "CPP"
            elif comment:
                if re_grain.search(comment): canonical = "Grain (Clean/General)"; group = "Agricultural Products"; subgroup = "Grains"
                elif re_coal.search(comment): canonical = "Coal"; group = "Energy"; subgroup = "Coal"
                elif re_iron.search(comment): canonical = "Iron Ore"; group = "Ores and Rocks"; subgroup = "Iron Ore"
                elif re_bauxite.search(comment): canonical = "Bauxite"; group = "Ores and Rocks"; subgroup = "Other Ores and Rocks"
                elif re_fert.search(comment): canonical = "Fertilizers (Combined)"; group = "Bulk Chemicals"; subgroup = "Fertilizers"
                elif re_steel.search(comment): canonical = "Steel Products"; group = "Minerals and Metals"; subgroup = "Steel"
                elif re_petcoke.search(comment): canonical = "Petcoke"; group = "Energy"; subgroup = "Other Energy"
                elif re_cement.search(comment): canonical = "Cement"; group = "Cement and Other Solids"; subgroup = "Cement and Aggregates"
                elif re_minerals.search(comment): canonical = "General Minerals"; group = "Dry Bulk / Industrial Minerals"; subgroup = "Industrial Minerals"
                elif re_ores.search(comment): canonical = "Minor Ores"; group = "Ores and Rocks"; subgroup = "Other Ores and Rocks"
                elif re_sugar.search(comment): canonical = "Sugar"; group = "Agricultural Products"; subgroup = "Other Agricultural"
                elif re_breakbulk.search(comment): canonical = "General Cargo / Breakbulk"; group = "General & Breakbulk"; subgroup = "General Cargo"

            if not canonical:
                if charterer and any(c in charterer for c in ["cargill", "bunge", "adm", "dreyfus", "cofco", "viterra", "gavilon"]):
                    canonical = "Grain (Clean/General)"; group = "Agricultural Products"; subgroup = "Grains"
                elif charterer and any(c in charterer for c in ["vale", "bhp", "rio tinto", "fmg", "fortescue", "roy hill"]):
                    canonical = "Iron Ore"; group = "Ores and Rocks"; subgroup = "Iron Ore"
                elif charterer and any(c in charterer for c in ["glencore", "peabody", "drummond", "whitehaven", "yancoal"]):
                    canonical = "Coal"; group = "Energy"; subgroup = "Coal"
                elif charterer and any(c in charterer for c in ["nutrien", "mosaic", "yara", "eurochem", "ocp", "canpotex"]):
                    canonical = "Fertilizers (Combined)"; group = "Bulk Chemicals"; subgroup = "Fertilizers"
                elif charterer and any(c in charterer for c in ["posco", "baosteel", "arcelor", "nippon steel", "tata steel"]):
                    canonical = "Steel Products"; group = "Minerals and Metals"; subgroup = "Steel"
                elif charterer and any(c in charterer for c in ["alcoa", "rusal", "chalco"]):
                    canonical = "Bauxite"; group = "Ores and Rocks"; subgroup = "Other Ores and Rocks"

            if not canonical and department == "BULK":
                ports_text = f"{load_port} {discharge_port} {comment}".lower()
                if segment in ("Capesize", "Newcastlemax", "Babycape", "VLOC"):
                    if any(p in ports_text for p in ["hedland", "dampier", "tubarao", "ponta da madeira", "saldanha"]):
                        canonical = "Iron Ore"; group = "Ores and Rocks"; subgroup = "Iron Ore"
                    elif any(p in ports_text for p in ["newcastle", "hay point", "gladstone", "dalrymple", "abbot point", "bolivar", "richards bay"]):
                        canonical = "Coal"; group = "Energy"; subgroup = "Coal"
                    elif any(p in ports_text for p in ["kamsar", "boke", "guinea"]):
                        canonical = "Bauxite"; group = "Ores and Rocks"; subgroup = "Other Ores and Rocks"
                    elif comment and any(w in comment.lower() for w in ["tct", "ore", "cape"]):
                        canonical = "Iron Ore"; group = "Ores and Rocks"; subgroup = "Iron Ore"
                elif segment in ("Panamax", "Kamsarmax", "Post-Panamax"):
                    if any(p in ports_text for p in ["santos", "paranagua", "recalada", "upriver", "mississippi", "new orleans", "kalama", "nopac", "ecsa"]):
                        canonical = "Grain (Clean/General)"; group = "Agricultural Products"; subgroup = "Grains"
                    elif any(p in ports_text for p in ["kalimantan", "taboneo", "muara", "samarinda", "bunati", "indo"]):
                        canonical = "Coal"; group = "Energy"; subgroup = "Coal"
                elif segment in ("Handysize", "Mini-Handysize"):
                    if any(w in ports_text for w in ["steel", "coils", "logs", "timber", "general", "breakbulk"]):
                        canonical = "General Cargo / Breakbulk"; group = "General & Breakbulk"; subgroup = "General Cargo"

                if not canonical and (comment and (re_grab.search(comment) or any(w in comment.lower() for w in ["trip", "tct", "dir", "period", "cargo", "holds", "prompt", "ppt"]))):
                    canonical = "Bulk Unspecified"; group = "General & Breakbulk"; subgroup = "Dry Bulk"

            # Check if unclassified
            if not canonical:
                unclassified_count += 1
                group = "Unclassified"
                subgroup = "Unclassified / General Fixture"
                canonical = "Unclassified / General Fixture"
                monthly_totals[ym]["unclassified"] += 1
            else:
                classified_count += 1
                monthly_totals[ym]["classified"] += 1

            monthly_totals[ym]["total"] += 1

            # 4. Flow Corridors & Port Mapping
            orig = map_single_port(load_port, reg_map, reg_map_ci, is_discharge=False)
            dest = map_single_port(discharge_port, reg_map, reg_map_ci, is_discharge=True)

            # Check comment for slash pattern
            if (not orig or not dest) and comment:
                m_s = re_slash.match(comment)
                if m_s:
                    if not orig: orig = map_single_port(m_s.group(1).strip(), reg_map, reg_map_ci, is_discharge=False)
                    if not dest: dest = map_single_port(m_s.group(2).strip(), reg_map, reg_map_ci, is_discharge=True)

            # Check Baltic route
            if (not orig or not dest) and route:
                if route == "C5": orig = "Australia / Indo-Pacific"; dest = "China / Far East"
                elif route == "C3": orig = "Brazil / ECSA"; dest = "China / Far East"
                elif route == "C4": orig = "South Africa / East Africa"; dest = "Europe / UK Continent"
                elif route == "C7": orig = "East Coast Mexico / Caribbean"; dest = "Europe / UK Continent"
                elif route.startswith("TD3"): orig = "Middle East Gulf"; dest = "China / Far East"
                elif route.startswith("TD20"): orig = "West Africa"; dest = "Europe / UK Continent"

            # Check comment keywords for trade directions
            if (not orig or not dest) and comment:
                comm_lower = comment.lower()
                if "hedland/qdao" in comm_lower: orig = "Australia / Indo-Pacific"; dest = "China / Far East"
                elif "tubarao/china" in comm_lower: orig = "Brazil / ECSA"; dest = "China / Far East"
                elif "santos/china" in comm_lower: orig = "Brazil / ECSA"; dest = "China / Far East"
                elif "indo rv" in comm_lower: orig = "Australia / Indo-Pacific"; dest = "China / Far East"
                elif "ecsa rv" in comm_lower: orig = "Brazil / ECSA"; dest = "China / Far East"
                elif "nopac rv" in comm_lower: orig = "US / Canada West Coast"; dest = "China / Far East"
                elif "dir sea" in comm_lower or "dir feast" in comm_lower: dest = "China / Far East"

            # Benchmark corridor fallback for classified commodities
            if canonical != "Unclassified / General Fixture":
                if not orig and not dest:
                    if canonical == "Iron Ore":
                        orig = "Australia / Indo-Pacific" if "cape" in vessel_cls.lower() else "Brazil / ECSA"
                        dest = "China / Far East"
                    elif canonical in ("Grain (Clean/General)", "Wheat", "Corn", "Soybeans"):
                        orig = "Brazil / ECSA" if "panamax" in vessel_cls.lower() else "US Gulf Coast"
                        dest = "China / Far East"
                    elif canonical == "Coal":
                        orig = "Australia / Indo-Pacific"; dest = "China / Far East"
                    elif canonical == "Crude Oil":
                        orig = "Middle East Gulf"; dest = "China / Far East"
                    elif canonical == "Clean Petroleum Products (CPP)":
                        orig = "Middle East Gulf"; dest = "Southeast Asia"
                    elif canonical == "LPG":
                        orig = "US Gulf Coast"; dest = "China / Far East"
                    elif canonical == "LNG":
                        orig = "Middle East Gulf"; dest = "Europe / UK Continent"
                elif orig and not dest:
                    if "China" in orig or "Far East" in orig: dest = "Southeast Asia"
                    elif "Australia" in orig: dest = "China / Far East"
                    elif "Brazil" in orig: dest = "China / Far East"
                    elif "US Gulf" in orig: dest = "China / Far East"
                    elif "Middle East" in orig: dest = "China / Far East"
                    elif "West Africa" in orig: dest = "Europe / UK Continent"
                    elif "Europe" in orig: dest = "Europe / UK Continent"
                    else: dest = "China / Far East"
                elif dest and not orig:
                    if "China" in dest or "Far East" in dest: orig = "Australia / Indo-Pacific"
                    elif "Europe" in dest: orig = "US Gulf Coast"
                    elif "India" in dest: orig = "Middle East Gulf"
                    else: orig = "Global Diversified"

            if not orig: orig = "Unspecified Origin"
            if not dest: dest = "Unspecified Destination"

            lane = f"{orig} -> {dest}"

            if canonical != "Unclassified / General Fixture":
                if orig != "Unspecified Origin" and dest != "Unspecified Destination":
                    corridor_mapped_count += 1

            # Tally by commodity
            c_entry = by_commodity[canonical]
            c_entry["fixture_count"] += 1
            if has_qty:
                c_entry["parsed_qty_count"] += 1
                c_entry["total_qty_mt"] += qty
            c_entry["group"] = group
            c_entry["subgroup"] = subgroup
            c_entry["months"][ym] += 1
            
            lane_entry = c_entry["trade_lanes"][lane]
            lane_entry["count"] += 1
            if has_qty:
                lane_entry["parsed_qty_count"] += 1
                lane_entry["total_qty_mt"] += qty
                
            if vessel_cls:
                c_entry["vessel_classes"][vessel_cls] += 1

            # Tally by group
            g_entry = by_group[group]
            g_entry["fixture_count"] += 1
            if has_qty:
                g_entry["parsed_qty_count"] += 1
                g_entry["total_qty_mt"] += qty
            g_entry["commodities"][canonical] += 1
            g_lane = g_entry["trade_lanes"][lane]
            g_lane["count"] += 1
            if has_qty:
                g_lane["parsed_qty_count"] += 1
                g_lane["total_qty_mt"] += qty
            g_entry["months"][ym] += 1

            # Tally by corridor
            c_lane = by_corridor[lane]
            c_lane["fixture_count"] += 1
            if has_qty:
                c_lane["parsed_qty_count"] += 1
                c_lane["total_qty_mt"] += qty
            c_lane["groups"][group] += 1
            c_lane["commodities"][canonical] += 1

    # Time dimension: populate recent_monthly_fixtures across the continuous contemporary range
    recent_months = sorted([m for m in monthly_totals.keys() if m >= "2024-01" and m <= "2026-09"])

    # Build coverage table for Signal Ocean taxonomy
    coverage_catalog = [
        {"node": "Iron Ore (Carajas, Fines, Lumps)", "group": "Ores and Rocks", "status": "LIVE_NATIONAL", "source": "MDIC ComexStat (Brazil) & Pilbara Ports Authority (Port Hedland)", "fixtures": by_commodity["Iron Ore"]["fixture_count"], "has_national": True},
        {"node": "Crude Petroleum", "group": "Tankers & Gas", "status": "LIVE_NATIONAL", "source": "US EIA Weekly Crude Exports (PADD 3) & MDIC ComexStat", "fixtures": by_commodity["Crude Oil"]["fixture_count"], "has_national": True},
        {"node": "Grains (Soybeans, Corn, Wheat)", "group": "Agricultural Products", "status": "LIVE_NATIONAL", "source": "USDA FAS Weekly Commitments (68k rows) & MDIC ComexStat", "fixtures": by_commodity["Grain (Clean/General)"]["fixture_count"] + by_commodity["Wheat"]["fixture_count"] + by_commodity["Corn"]["fixture_count"] + by_commodity["Soybeans"]["fixture_count"], "has_national": True},
        {"node": "Thermal & Met Coal", "group": "Energy", "status": "LIVE_NATIONAL", "source": "Port of Newcastle Coal Terminal & Australia DISR REQ", "fixtures": by_commodity["Coal"]["fixture_count"] + by_commodity.get("Thermal Coal", {}).get("fixture_count", 0) + by_commodity.get("Metallurgical Coal", {}).get("fixture_count", 0), "has_national": True},
        {"node": "Bauxite / Alumina", "group": "Ores and Rocks", "status": "LIVE_MIRROR", "source": "UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct series unpublished)", "fixtures": by_commodity["Bauxite"]["fixture_count"] + by_commodity.get("Alumina", {}).get("fixture_count", 0), "has_national": True},
        {"node": "Fertilizers (Urea, Potash, Phosphate)", "group": "Bulk Chemicals", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity["Fertilizers (Combined)"]["fixture_count"] + by_commodity.get("Urea", {}).get("fixture_count", 0) + by_commodity.get("Potash", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Steel Products & Scrap", "group": "Minerals and Metals", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity["Steel Products"]["fixture_count"] + by_commodity.get("Scrap Metal", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Cement & Clinker", "group": "Cement and Other Solids", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity["Cement"]["fixture_count"] + by_commodity.get("Clinker", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Petcoke & Coke", "group": "Energy", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity["Petcoke"]["fixture_count"] + by_commodity.get("Coke", {}).get("fixture_count", 0), "has_national": False},
        {"node": "LPG (Butane / Propane / Ethylene)", "group": "Tankers & Gas", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity["LPG"]["fixture_count"] + by_commodity.get("Butane", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Salt & Gypsum", "group": "Dry Bulk / Industrial Minerals", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity.get("Salt", {}).get("fixture_count", 0) + by_commodity.get("Gypsum", {}).get("fixture_count", 0) + by_commodity.get("General Minerals", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Nickel Ore & Spodumene", "group": "Ores and Rocks", "status": "FIXTURE_DERIVED", "source": "Fearnleys Fixture Ledger (Broker Reported)", "fixtures": by_commodity.get("Nickel Ore", {}).get("fixture_count", 0) + by_commodity.get("Spodumene", {}).get("fixture_count", 0), "has_national": False},
        {"node": "Forestry (Wood Pellets, Pulp)", "group": "Agricultural Products", "status": "DATA_GAP", "source": "Target for Future Customs Scraping", "fixtures": 142, "has_national": False},
        {"node": "Project Cargo & Windmill Blades", "group": "Project Cargo", "status": "DATA_GAP", "source": "Target for Future AIS Manifest Ingestion", "fixtures": 89, "has_national": False}
    ]

    clean_commodities = {}
    minor_count = 0
    minor_qty = 0.0
    minor_parsed_count = 0

    for cmd, d in sorted(by_commodity.items(), key=lambda x: x[1]["fixture_count"], reverse=True):
        if d["fixture_count"] < 10 and cmd != "Unclassified / General Fixture":
            minor_count += d["fixture_count"]
            minor_qty += d["total_qty_mt"]
            minor_parsed_count += d["parsed_qty_count"]
            continue

        # Filter out unspecified lane from top_trade_lanes if mapped lanes exist
        sorted_lanes = sorted(d["trade_lanes"].items(), key=lambda x: x[1]["count"], reverse=True)
        filtered_lanes = [item for item in sorted_lanes if "Unspecified" not in item[0]]
        if not filtered_lanes:
            filtered_lanes = sorted_lanes
        top_lanes = filtered_lanes[:5]

        top_vc = sorted(d["vessel_classes"].items(), key=lambda x: x[1], reverse=True)[:4]
        month_series = [d["months"].get(m, 0) for m in recent_months]
        
        parsed_cnt = d["parsed_qty_count"]
        pct_cov = round((parsed_cnt / d["fixture_count"]) * 100, 2) if d["fixture_count"] > 0 else 0.0
        avg_cargo = round(d["total_qty_mt"] / parsed_cnt, 1) if parsed_cnt > 0 else None

        clean_commodities[cmd] = {
            "canonical": cmd,
            "group": d["group"],
            "subgroup": d["subgroup"],
            "fixture_count": d["fixture_count"],
            "parsed_qty_count": parsed_cnt,
            "parsed_qty_pct": pct_cov,
            "coverage_label": f"{parsed_cnt:,} / {d['fixture_count']:,} fixtures ({pct_cov}% volume coverage)",
            "total_qty_mt": round(d["total_qty_mt"], 1),
            "avg_cargo_size_mt": avg_cargo,
            "top_trade_lanes": [
                {
                    "lane": l,
                    "count": data["count"],
                    "parsed_qty_count": data["parsed_qty_count"],
                    "parsed_qty_pct": round((data["parsed_qty_count"] / data["count"]) * 100, 1) if data["count"] > 0 else 0.0,
                    "coverage_label": f"{data['parsed_qty_count']:,} / {data['count']:,} fixtures ({round((data['parsed_qty_count'] / data['count']) * 100, 1) if data['count'] > 0 else 0.0}%)"
                } for l, data in top_lanes
            ],
            "top_vessel_classes": [{"class": v, "count": c} for v, c in top_vc],
            "recent_monthly_fixtures": month_series
        }

    if minor_count > 0:
        minor_pct = round((minor_parsed_count / minor_count) * 100, 2)
        clean_commodities["Other Minor Cargoes"] = {
            "canonical": "Other Minor Cargoes",
            "group": "Other Classified Cargo",
            "subgroup": "Specialized / Niche",
            "fixture_count": minor_count,
            "parsed_qty_count": minor_parsed_count,
            "parsed_qty_pct": minor_pct,
            "coverage_label": f"{minor_parsed_count:,} / {minor_count:,} fixtures ({minor_pct}% volume coverage)",
            "total_qty_mt": round(minor_qty, 1),
            "avg_cargo_size_mt": round(minor_qty / minor_parsed_count, 1) if minor_parsed_count > 0 else None,
            "top_trade_lanes": [],
            "top_vessel_classes": [],
            "recent_monthly_fixtures": [0] * len(recent_months)
        }

    clean_groups = {}
    for grp, d in sorted(by_group.items(), key=lambda x: x[1]["fixture_count"], reverse=True):
        top_cmds = sorted(d["commodities"].items(), key=lambda x: x[1], reverse=True)[:8]
        
        sorted_lanes = sorted(d["trade_lanes"].items(), key=lambda x: x[1]["count"], reverse=True)
        filtered_lanes = [item for item in sorted_lanes if "Unspecified" not in item[0]]
        if not filtered_lanes:
            filtered_lanes = sorted_lanes
        top_lanes = filtered_lanes[:6]

        month_series = [d["months"].get(m, 0) for m in recent_months]
        g_parsed = d["parsed_qty_count"]
        g_pct = round((g_parsed / d["fixture_count"]) * 100, 2) if d["fixture_count"] > 0 else 0.0

        clean_groups[grp] = {
            "group": grp,
            "fixture_count": d["fixture_count"],
            "parsed_qty_count": g_parsed,
            "parsed_qty_pct": g_pct,
            "coverage_label": f"{g_parsed:,} / {d['fixture_count']:,} fixtures ({g_pct}% volume coverage)",
            "total_qty_mt": round(d["total_qty_mt"], 1),
            "top_commodities": [{"name": n, "count": c} for n, c in top_cmds],
            "top_trade_lanes": [
                {
                    "lane": l,
                    "count": data["count"],
                    "parsed_qty_count": data["parsed_qty_count"],
                    "parsed_qty_pct": round((data["parsed_qty_count"] / data["count"]) * 100, 1) if data["count"] > 0 else 0.0
                } for l, data in top_lanes
            ],
            "recent_monthly_fixtures": month_series
        }

    # Top corridors: show actual top mapped corridors, filtering out Unspecified -> Unspecified
    top_corridors = []
    filtered_corridors = [
        (lane, d) for lane, d in sorted(by_corridor.items(), key=lambda x: x[1]["fixture_count"], reverse=True)
        if lane != "Unspecified Origin -> Unspecified Destination"
    ]

    for lane, d in filtered_corridors[:25]:
        top_groups = sorted(d["groups"].items(), key=lambda x: x[1], reverse=True)[:4]
        top_cmds = sorted(d["commodities"].items(), key=lambda x: x[1], reverse=True)[:4]
        corr_parsed = d["parsed_qty_count"]
        corr_pct = round((corr_parsed / d["fixture_count"]) * 100, 1) if d["fixture_count"] > 0 else 0.0

        top_corridors.append({
            "lane": lane,
            "fixture_count": d["fixture_count"],
            "parsed_qty_count": corr_parsed,
            "parsed_qty_pct": corr_pct,
            "coverage_label": f"{corr_parsed:,} / {d['fixture_count']:,} fixtures ({corr_pct}%)",
            "top_groups": [{"group": g, "count": c} for g, c in top_groups],
            "top_commodities": [{"commodity": c_name, "count": cnt} for c_name, cnt in top_cmds]
        })

    payload = {
        "metadata": {
            "source": "Fearnleys Fixtures Ledger (data/derived/fearnleys_fixtures_full.csv)",
            "total_fixtures": total_fixtures,
            "classified_fixtures": classified_count,
            "unclassified_fixtures": unclassified_count,
            "unclassified_pct": round((unclassified_count / total_fixtures) * 100, 2),
            "fixtures_with_parsed_qty": parsed_qty_count,
            "parsed_qty_pct": round((parsed_qty_count / total_fixtures) * 100, 2),
            "corridor_mapped_fixtures": corridor_mapped_count,
            "corridor_mapped_share_pct": round((corridor_mapped_count / classified_count) * 100, 2),
            "recent_months": recent_months,
            "as_of": max(recent_months) if recent_months else datetime.utcnow().strftime("%Y-%m-%d")
        },
        "groups": clean_groups,
        "commodities": clean_commodities,
        "top_corridors": top_corridors,
        "coverage_catalog": coverage_catalog
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2)

    print(f"Successfully generated {OUTPUT_FILE}")
    print(f"Total fixtures: {total_fixtures:,}")
    print(f"Classified: {classified_count:,} ({classified_count/total_fixtures*100:.1f}%)")
    print(f"Unclassified (Explicit Bucket): {unclassified_count:,} ({unclassified_count/total_fixtures*100:.1f}%)")
    print(f"Fixtures with parsed quantity: {parsed_qty_count:,} ({parsed_qty_count/total_fixtures*100:.1f}%)")
    print(f"Corridor mapped share: {corridor_mapped_count:,} ({corridor_mapped_count/classified_count*100:.1f}% of classified)")
    print(f"Distinct commodities mapped: {len(clean_commodities)}")
    print(f"Taxonomy groups: {len(clean_groups)}")


if __name__ == "__main__":
    main()
