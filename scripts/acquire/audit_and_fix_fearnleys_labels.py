#!/usr/bin/env python3
"""
scripts/acquire/audit_and_fix_fearnleys_labels.py

Target 1A: Re-derive the tsId -> label -> class -> unit mapping for all 34 continuous Fearnleys series.
Fixes live data-integrity bug where Capesize, Panamax, and Supramax series were swapped in column headers.
Adds explicit units: usd/day, usd/tonne, worldscale, usd_million, index, fx, percent, usd/bbl.
Rebuilds data/clarksons/fearnleys_benchmark_rates_continuous.csv and .json.
"""

import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.csv"
JSON_PATH = ROOT / "data" / "clarksons" / "fearnleys_benchmark_rates_continuous.json"

# Complete authoritative tsId -> (canonical_label, vessel_class, unit, notes)
# Derived from scripts/fearnleys/fetch_dry_routes_ts.py, Fearnleys Weekly Report, and market rate realities.
CANONICAL_MAP = {
    1: {
        "label": "MEG/Japan-China VLCC (TD3/TD3C transition)",
        "class": "VLCC",
        "route_code": "TD3/TD3C",
        "unit": "worldscale",
        "header": "MEG/Japan-China VLCC (TD3/TD3C transition) [worldscale] (tsid_1)",
        "notes": "Historical benchmark MEG/Japan (TD3) transitioned to MEG/China (TD3C) around 2019-2020. Quoted in Worldscale points (15-140 WS), straddling both definitions (discontinued 2023-05)."
    },
    2: {
        "label": "MEG/Singapore VLCC (TD2)",
        "class": "VLCC",
        "route_code": "TD2",
        "unit": "worldscale",
        "header": "MEG/Singapore VLCC (TD2) [worldscale] (tsid_2)",
        "notes": "TD2 crude benchmark (Middle East Gulf to Singapore), quoted in Worldscale points (discontinued 2023-05)."
    },
    3: {
        "label": "WAF/China VLCC (TD15)",
        "class": "VLCC",
        "route_code": "TD15",
        "unit": "worldscale",
        "header": "WAF/China VLCC (TD15) [worldscale] (tsid_3)",
        "notes": "TD15 crude benchmark (West Africa to China), quoted in Worldscale points (discontinued 2023-05)."
    },
    4: {
        "label": "WAF/UKC Suezmax (TD20)",
        "class": "Suezmax",
        "route_code": "TD20",
        "unit": "worldscale",
        "header": "WAF/UKC Suezmax (TD20) [worldscale] (tsid_4)",
        "notes": "TD20 crude benchmark (West Africa to UK-Continent), quoted in Worldscale points."
    },
    5: {
        "label": "Market Brief (Dirty Tanker)",
        "class": "Dirty Tanker",
        "route_code": None,
        "unit": "worldscale",
        "header": "Market Brief (Dirty Tanker) [worldscale] (tsid_5)",
        "notes": "Fearnleys BITR market brief composite, quoted in Worldscale points (discontinued 2023-05)."
    },
    6: {
        "label": "Cross Med Aframax (TD19)",
        "class": "Aframax",
        "route_code": "TD19",
        "unit": "worldscale",
        "header": "Cross Med Aframax (TD19) [worldscale] (tsid_6)",
        "notes": "TD19 crude benchmark (Cross Mediterranean), quoted in Worldscale points (discontinued 2023-05)."
    },
    7: {
        "label": "Unverified Spot Route (mislabelled 1 Year TC - VLCC)",
        "class": "VLCC",
        "route_code": None,
        "unit": "worldscale",
        "header": "Unverified Spot Route (mislabelled 1 Year TC - VLCC) [worldscale] (tsid_7)",
        "notes": "Quoted in Worldscale points (55-430), identical span/format to spot routes 1-6. Time charters are never quoted in Worldscale; series was mislabelled 1 Year TC by publisher (discontinued 2023-05)."
    },
    8: {
        "label": "Unverified Spot Route (mislabelled 1 Year TC - Suezmax)",
        "class": "Suezmax",
        "route_code": None,
        "unit": "worldscale",
        "header": "Unverified Spot Route (mislabelled 1 Year TC - Suezmax) [worldscale] (tsid_8)",
        "notes": "Quoted in Worldscale points (62.5-330), identical span/format to spot routes 1-6. Time charters are never quoted in Worldscale; series was mislabelled 1 Year TC by publisher (discontinued 2023-05)."
    },
    9: {
        "label": "Unverified Spot Route (mislabelled 1 Year TC - Aframax)",
        "class": "Aframax",
        "route_code": None,
        "unit": "worldscale",
        "header": "Unverified Spot Route (mislabelled 1 Year TC - Aframax) [worldscale] (tsid_9)",
        "notes": "Quoted in Worldscale points (10-575), identical span/format to spot routes 1-6. Time charters are never quoted in Worldscale; series was mislabelled 1 Year TC by publisher (discontinued 2023-05)."
    },
    11: {
        "label": "Specialized High-Spec TC (mislabelled LR1 TC)",
        "class": "Specialized Asset",
        "route_code": None,
        "unit": "usd/day",
        "header": "Specialized High-Spec TC (mislabelled LR1 TC) [usd/day] (tsid_11)",
        "notes": "Rates $23k-$145k/day. Far exceeds standard LR1 1Y TC ($30-35k/day); represents high-spec asset or LNGC."
    },
    13: {
        "label": "Specialized Asset Rate (mislabelled Handy TC)",
        "class": "Specialized Asset",
        "route_code": None,
        "unit": "usd/day",
        "header": "Specialized Asset Rate (mislabelled Handy TC) [usd/day] (tsid_13)",
        "notes": "Rates $15k-$110k/day. Far exceeds standard Handy 1Y TC ($14.5k/day); represents high-spec asset or VLGC."
    },
    303: {
        "label": "380 CST Bunker Price (Rotterdam)",
        "class": "Bunkers",
        "route_code": None,
        "unit": "usd/tonne",
        "header": "380 CST Bunker Price (Rotterdam) [usd/tonne] (tsid_303)",
        "notes": "Rotterdam HSFO 380 CST spot price in USD/MT."
    },
    304: {
        "label": "MGO Bunker Price (Rotterdam)",
        "class": "Bunkers",
        "route_code": None,
        "unit": "usd/tonne",
        "header": "MGO Bunker Price (Rotterdam) [usd/tonne] (tsid_304)",
        "notes": "Rotterdam Marine Gas Oil spot price in USD/MT."
    },
    306: {
        "label": "380 CST Bunker Price (Singapore)",
        "class": "Bunkers",
        "route_code": None,
        "unit": "usd/tonne",
        "header": "380 CST Bunker Price (Singapore) [usd/tonne] (tsid_306)",
        "notes": "Singapore HSFO 380 CST spot price in USD/MT."
    },
    307: {
        "label": "MGO Bunker Price (Singapore)",
        "class": "Bunkers",
        "route_code": None,
        "unit": "usd/tonne",
        "header": "MGO Bunker Price (Singapore) [usd/tonne] (tsid_307)",
        "notes": "Singapore Marine Gas Oil spot price in USD/MT."
    },
    316: {
        "label": "Commodity Prices (Brent Crude)",
        "class": "Commodities",
        "route_code": None,
        "unit": "usd/bbl",
        "header": "Commodity Prices (Brent Crude) [usd/bbl] (tsid_316)",
        "notes": "Brent crude front-month price ($59-$114/bbl)."
    },
    5001: {
        "label": "USD/KRW",
        "class": "FX",
        "route_code": None,
        "unit": "krw_per_usd",
        "header": "USD/KRW [fx] (tsid_5001)",
        "notes": "Korean Won foreign exchange rate."
    },
    5002: {
        "label": "USD/NOK",
        "class": "FX",
        "route_code": None,
        "unit": "nok_per_usd",
        "header": "USD/NOK [fx] (tsid_5002)",
        "notes": "Norwegian Krone foreign exchange rate."
    },
    5003: {
        "label": "EUR/USD",
        "class": "FX",
        "route_code": None,
        "unit": "usd_per_eur",
        "header": "EUR/USD [fx] (tsid_5003)",
        "notes": "Euro foreign exchange rate."
    },
    10001: {
        "label": "Capesize Tubarao/Qingdao (C3)",
        "class": "Capesize",
        "route_code": "C3",
        "unit": "usd/tonne",
        "header": "Capesize Tubarao/Qingdao (C3) [usd/tonne] (tsid_10001)",
        "notes": "Baltic C3 Capesize iron ore freight benchmark from Tubarao to Qingdao in USD/tonne."
    },
    10002: {
        "label": "Capesize Australia/China (C5)",
        "class": "Capesize",
        "route_code": "C5",
        "unit": "usd/tonne",
        "header": "Capesize Australia/China (C5) [usd/tonne] (tsid_10002)",
        "notes": "Baltic C5 Capesize iron ore freight benchmark from Dampier to Qingdao in USD/tonne."
    },
    10003: {
        "label": "Capesize Newcastle/Qingdao Coal",
        "class": "Capesize",
        "route_code": None,
        "unit": "usd/tonne",
        "header": "Capesize Newcastle/Qingdao Coal [usd/tonne] (tsid_10003)",
        "notes": "Baltic Capesize coal freight benchmark from Newcastle to Qingdao in USD/tonne."
    },
    10010: {
        "label": "Panamax Transatlantic RV (P1A_82)",
        "class": "Panamax",
        "route_code": "P1A_82",
        "unit": "usd/day",
        "header": "Panamax Transatlantic RV (P1A_82) [usd/day] (tsid_10010)",
        "notes": "Baltic P1A_82 Skaw-Gib transatlantic RV. Rate range $11.7k-$24.3k/day (median $17.4k). Corrected from mislabelled Capesize."
    },
    10011: {
        "label": "Panamax TCE Cont/Far East (P2A_82)",
        "class": "Panamax",
        "route_code": "P2A_82",
        "unit": "usd/day",
        "header": "Panamax TCE Cont/Far East (P2A_82) [usd/day] (tsid_10011)",
        "notes": "Baltic P2A_82 Skaw-Gib trip HK-S.Korea. Rate range $17.5k-$33.0k/day (median $24.9k). Corrected from mislabelled Capesize."
    },
    10012: {
        "label": "Panamax TCE Far East RV (P3A_82)",
        "class": "Panamax",
        "route_code": "P3A_82",
        "unit": "usd/day",
        "header": "Panamax TCE Far East RV (P3A_82) [usd/day] (tsid_10012)",
        "notes": "Baltic P3A_82 HK-S.Korea transpacific RV. Rate range $9.2k-$24.1k/day (median $16.8k). Corrected from mislabelled Capesize."
    },
    10013: {
        "label": "Panamax TCE Far East/Cont (P4_82)",
        "class": "Panamax",
        "route_code": "P4_82",
        "unit": "usd/day",
        "header": "Panamax TCE Far East/Cont (P4_82) [usd/day] (tsid_10013)",
        "notes": "Baltic P4_82 HK-S.Korea to Skaw-Passero backhaul. Rate range $7.3k-$16.5k/day (median $10.8k). Corrected from mislabelled Capesize."
    },
    11323: {
        "label": "Baltic Dry Index (BDI)",
        "class": "Dry Bulk Composite",
        "route_code": "BDI",
        "unit": "index",
        "header": "Baltic Dry Index (BDI) [index] (tsid_11323)",
        "notes": "Composite dry bulk shipping index (1,532 - 3,628 points)."
    },
    12100: {
        "label": "Interest Rates (SOFR/LIBOR)",
        "class": "Macro",
        "route_code": None,
        "unit": "percent",
        "header": "Interest Rates (SOFR/LIBOR) [percent] (tsid_12100)",
        "notes": "Benchmark interest rates in percent (3.6% - 4.5%)."
    },
    120129: {
        "label": "Supramax US Gulf - China/South Japan (S1C)",
        "class": "Supramax",
        "route_code": "S1C",
        "unit": "usd/day",
        "header": "Supramax US Gulf - China/South Japan (S1C) [usd/day] (tsid_120129)",
        "notes": "Baltic S1C US Gulf to China-Japan. Rate range $18.8k-$33.8k/day (median $28.4k). Corrected from mislabelled Panamax."
    },
    120132: {
        "label": "Supramax Transatlantic RV Delivery USG (S4A)",
        "class": "Supramax",
        "route_code": "S4A",
        "unit": "usd/day",
        "header": "Supramax Transatlantic RV Delivery USG (S4A) [usd/day] (tsid_120132)",
        "notes": "Baltic S4A US Gulf trip to Skaw-Passero (delivery USG). Peaked over 40kpd late 2023 (max 41,214), 34,757 on 2025-10-01."
    },
    120133: {
        "label": "Supramax Transatlantic RV Delivery Cont (S4B)",
        "class": "Supramax",
        "route_code": "S4B",
        "unit": "usd/day",
        "header": "Supramax Transatlantic RV Delivery Cont (S4B) [usd/day] (tsid_120133)",
        "notes": "Baltic S4B Skaw-Passero trip to US Gulf (delivery Continent). Max 20,675, 15,132 on 2025-10-01."
    },
    120137: {
        "label": "Supramax South China - Indonesia RV (S10)",
        "class": "Supramax",
        "route_code": "S10",
        "unit": "usd/day",
        "header": "Supramax South China - Indonesia RV (S10) [usd/day] (tsid_120137)",
        "notes": "Baltic S10 South China trip via Indonesia to South China nickel/coal RV in USD/day. Rate range $7.5k-$17.9k/day."
    },
    120654: {
        "label": "Capesize Pacific RV (C10_182)",
        "class": "Capesize",
        "route_code": "C10_182",
        "unit": "usd/day",
        "header": "Capesize Pacific RV (C10_182) [usd/day] (tsid_120654)",
        "notes": "Baltic C10_182 China-Japan transpacific RV. Rate range $16.4k-$63.2k/day (median $31.4k). Corrected from mislabelled Supramax."
    },
    120655: {
        "label": "Capesize TCE Cont/Far East (C9_182)",
        "class": "Capesize",
        "route_code": "C9_182",
        "unit": "usd/day",
        "header": "Capesize TCE Cont/Far East (C9_182) [usd/day] (tsid_120655)",
        "notes": "Baltic C9_182 Continent/Med trip China-Japan fronthaul. Rate range $41.1k-$93.1k/day (median $55.6k). Corrected from mislabelled Supramax."
    }
}

def fix_csv():
    print(f"Reading {CSV_PATH}...")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        old_headers = next(reader)
        rows = list(reader)

    new_headers = [old_headers[0]] # 'date'
    for h in old_headers[1:]:
        m = re.search(r"\(tsid_(\d+)\)", h)
        if m:
            tsid = int(m.group(1))
            if tsid in CANONICAL_MAP:
                new_headers.append(CANONICAL_MAP[tsid]["header"])
            else:
                new_headers.append(h)
        else:
            new_headers.append(h)

    print(f"Rewriting {CSV_PATH} with {len(new_headers)} corrected headers...")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(new_headers)
        writer.writerows(rows)
    print("Successfully rebuilt CSV.")

def fix_json():
    if not JSON_PATH.exists():
        print(f"{JSON_PATH} does not exist, skipping.")
        return

    print(f"Reading {JSON_PATH}...")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    catalog = data.get("series_catalog", {})
    for tsid_str, meta in catalog.items():
        try:
            tsid = int(tsid_str)
        except ValueError:
            continue
        if tsid in CANONICAL_MAP:
            mapping = CANONICAL_MAP[tsid]
            meta["route_name"] = mapping["label"]
            meta["vessel_class"] = mapping["class"]
            meta["route_code"] = mapping.get("route_code")
            meta["unit"] = mapping["unit"]
            meta["notes"] = mapping["notes"]

    print(f"Rewriting {JSON_PATH} with updated catalog metadata...")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Successfully updated JSON catalog.")

if __name__ == "__main__":
    fix_csv()
    fix_json()
