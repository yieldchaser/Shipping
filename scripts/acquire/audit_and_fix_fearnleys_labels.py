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
        "label": "MEG/Japan (VLCC)",
        "class": "VLCC",
        "unit": "worldscale",
        "header": "MEG/Japan (VLCC) [worldscale] (tsid_1)",
        "notes": "TD3C crude benchmark, quoted in Worldscale points (historical WS 15-140)."
    },
    2: {
        "label": "MEG/Singapore (VLCC)",
        "class": "VLCC",
        "unit": "worldscale",
        "header": "MEG/Singapore (VLCC) [worldscale] (tsid_2)",
        "notes": "Dirty tanker route, quoted in Worldscale points."
    },
    3: {
        "label": "WAF/China (VLCC)",
        "class": "VLCC",
        "unit": "worldscale",
        "header": "WAF/China (VLCC) [worldscale] (tsid_3)",
        "notes": "TD15/TD22 crude benchmark, quoted in Worldscale points."
    },
    4: {
        "label": "WAF/UKC (Suezmax)",
        "class": "Suezmax",
        "unit": "worldscale",
        "header": "WAF/UKC (Suezmax) [worldscale] (tsid_4)",
        "notes": "TD20 crude benchmark, quoted in Worldscale points."
    },
    5: {
        "label": "Market Brief (Dirty Tanker)",
        "class": "Dirty Tanker",
        "unit": "worldscale",
        "header": "Market Brief (Dirty Tanker) [worldscale] (tsid_5)",
        "notes": "Fearnleys BITR market brief composite, quoted in Worldscale points."
    },
    6: {
        "label": "Cross Med (Aframax)",
        "class": "Aframax",
        "unit": "worldscale",
        "header": "Cross Med (Aframax) [worldscale] (tsid_6)",
        "notes": "TD19 crude benchmark, quoted in Worldscale points."
    },
    7: {
        "label": "1 Year TC - VLCC",
        "class": "VLCC",
        "unit": "worldscale",
        "header": "1 Year TC - VLCC [worldscale] (tsid_7)",
        "notes": "1Y TC benchmark index, quoted in Worldscale points (discontinued 2023-05)."
    },
    8: {
        "label": "1 Year TC - Suezmax",
        "class": "Suezmax",
        "unit": "worldscale",
        "header": "1 Year TC - Suezmax [worldscale] (tsid_8)",
        "notes": "1Y TC benchmark index, quoted in Worldscale points (discontinued 2023-05)."
    },
    9: {
        "label": "1 Year TC - Aframax",
        "class": "Aframax",
        "unit": "worldscale",
        "header": "1 Year TC - Aframax [worldscale] (tsid_9)",
        "notes": "1Y TC benchmark index, quoted in Worldscale points (discontinued 2023-05)."
    },
    11: {
        "label": "Specialized High-Spec TC (mislabelled LR1 TC)",
        "class": "Specialized Asset",
        "unit": "usd/day",
        "header": "Specialized High-Spec TC (mislabelled LR1 TC) [usd/day] (tsid_11)",
        "notes": "Rates $23k-$145k/day. Far exceeds standard LR1 1Y TC ($30-35k/day); represents high-spec asset or LNGC."
    },
    13: {
        "label": "Specialized Asset Rate (mislabelled Handy TC)",
        "class": "Specialized Asset",
        "unit": "usd/day",
        "header": "Specialized Asset Rate (mislabelled Handy TC) [usd/day] (tsid_13)",
        "notes": "Rates $15k-$110k/day. Far exceeds standard Handy 1Y TC ($14.5k/day); represents high-spec asset or VLGC."
    },
    303: {
        "label": "380 CST Bunker Price (Singapore)",
        "class": "Bunkers",
        "unit": "usd/tonne",
        "header": "380 CST Bunker Price (Singapore) [usd/tonne] (tsid_303)",
        "notes": "Singapore HSFO 380 CST spot price in USD/MT."
    },
    304: {
        "label": "MGO Bunker Price (Singapore)",
        "class": "Bunkers",
        "unit": "usd/tonne",
        "header": "MGO Bunker Price (Singapore) [usd/tonne] (tsid_304)",
        "notes": "Singapore Marine Gas Oil spot price in USD/MT."
    },
    306: {
        "label": "380 CST Bunker Price (Rotterdam)",
        "class": "Bunkers",
        "unit": "usd/tonne",
        "header": "380 CST Bunker Price (Rotterdam) [usd/tonne] (tsid_306)",
        "notes": "Rotterdam HSFO 380 CST spot price in USD/MT."
    },
    307: {
        "label": "MGO Bunker Price (Rotterdam)",
        "class": "Bunkers",
        "unit": "usd/tonne",
        "header": "MGO Bunker Price (Rotterdam) [usd/tonne] (tsid_307)",
        "notes": "Rotterdam Marine Gas Oil spot price in USD/MT."
    },
    316: {
        "label": "Commodity Prices (Brent Crude)",
        "class": "Commodities",
        "unit": "usd/bbl",
        "header": "Commodity Prices (Brent Crude) [usd/bbl] (tsid_316)",
        "notes": "Brent crude front-month price ($59-$114/bbl)."
    },
    5001: {
        "label": "USD/KRW",
        "class": "FX",
        "unit": "krw_per_usd",
        "header": "USD/KRW [fx] (tsid_5001)",
        "notes": "Korean Won foreign exchange rate."
    },
    5002: {
        "label": "USD/NOK",
        "class": "FX",
        "unit": "nok_per_usd",
        "header": "USD/NOK [fx] (tsid_5002)",
        "notes": "Norwegian Krone foreign exchange rate."
    },
    5003: {
        "label": "EUR/USD",
        "class": "FX",
        "unit": "usd_per_eur",
        "header": "EUR/USD [fx] (tsid_5003)",
        "notes": "Euro foreign exchange rate."
    },
    10001: {
        "label": "Tubarao/Qingdao (Capesize Iron Ore C3)",
        "class": "Capesize",
        "unit": "usd/tonne",
        "header": "Tubarao/Qingdao (Capesize Iron Ore C3) [usd/tonne] (tsid_10001)",
        "notes": "Baltic C3 Capesize iron ore freight benchmark from Tubarao to Qingdao in USD/tonne."
    },
    10002: {
        "label": "Australia/China (Capesize Iron Ore C5)",
        "class": "Capesize",
        "unit": "usd/tonne",
        "header": "Australia/China (Capesize Iron Ore C5) [usd/tonne] (tsid_10002)",
        "notes": "Baltic C5 Capesize iron ore freight benchmark from Dampier to Qingdao in USD/tonne."
    },
    10003: {
        "label": "Newcastle/Qingdao (Capesize Coal)",
        "class": "Capesize",
        "unit": "usd/tonne",
        "header": "Newcastle/Qingdao (Capesize Coal) [usd/tonne] (tsid_10003)",
        "notes": "Baltic Capesize coal freight benchmark from Newcastle to Qingdao in USD/tonne."
    },
    10010: {
        "label": "Panamax Transatlantic RV",
        "class": "Panamax",
        "unit": "usd/day",
        "header": "Transatlantic RV (Panamax) [usd/day] (tsid_10010)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Capesize. Rate range $11.7k-$24.3k/day (median $17.4k). Exact match to fetch_dry_routes_ts.py PANAMAX_TRANSATLANTIC_RV."
    },
    10011: {
        "label": "Panamax TCE Cont/Far East",
        "class": "Panamax",
        "unit": "usd/day",
        "header": "TCE Cont/Far East (Panamax) [usd/day] (tsid_10011)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Capesize. Rate range $17.5k-$33.0k/day (median $24.9k). Exact match to fetch_dry_routes_ts.py PANAMAX_TCE_CONT_FAR_EAST."
    },
    10012: {
        "label": "Panamax TCE Far East RV",
        "class": "Panamax",
        "unit": "usd/day",
        "header": "TCE Far East RV (Panamax) [usd/day] (tsid_10012)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Capesize. Rate range $9.2k-$24.1k/day (median $16.8k). Exact match to fetch_dry_routes_ts.py PANAMAX_TCE_FAR_EAST_RV."
    },
    10013: {
        "label": "Panamax TCE Far East/Cont",
        "class": "Panamax",
        "unit": "usd/day",
        "header": "TCE Far East/Cont (Panamax) [usd/day] (tsid_10013)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Capesize. Rate range $7.3k-$16.5k/day (median $10.8k). Exact match to fetch_dry_routes_ts.py PANAMAX_TCE_FAR_EAST_CONT."
    },
    11323: {
        "label": "Baltic Dry Index (BDI)",
        "class": "Dry Bulk Composite",
        "unit": "index",
        "header": "Baltic Dry Index (BDI) [index] (tsid_11323)",
        "notes": "Composite dry bulk shipping index (1,532 - 3,628 points)."
    },
    12100: {
        "label": "Interest Rates (SOFR/LIBOR)",
        "class": "Macro",
        "unit": "percent",
        "header": "Interest Rates (SOFR/LIBOR) [percent] (tsid_12100)",
        "notes": "Benchmark interest rates in percent (3.6% - 4.5%)."
    },
    120129: {
        "label": "Supramax US Gulf - China/South Japan",
        "class": "Supramax",
        "unit": "usd/day",
        "header": "US Gulf - China/South Japan (Supramax) [usd/day] (tsid_120129)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Panamax. Rate range $18.8k-$33.8k/day (median $28.4k). Exact match to fetch_dry_routes_ts.py SUPRAMAX_US_GULF_CHINA_SJ."
    },
    120132: {
        "label": "Supramax Transatlantic RV (Delivery Cont)",
        "class": "Supramax",
        "unit": "usd/day",
        "header": "Transatlantic RV Delivery Cont (Supramax) [usd/day] (tsid_120132)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Panamax. Raw leg A of Supramax Transatlantic RV (Skaw-Passero delivery). Rate range $17.7k-$34.8k/day."
    },
    120133: {
        "label": "Supramax Transatlantic RV (Delivery USG)",
        "class": "Supramax",
        "unit": "usd/day",
        "header": "Transatlantic RV Delivery USG (Supramax) [usd/day] (tsid_120133)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Panamax. Raw leg B of Supramax Transatlantic RV (US Gulf delivery). Rate range $9.6k-$16.6k/day."
    },
    120137: {
        "label": "Supramax South China - Indonesia RV",
        "class": "Supramax",
        "unit": "usd/day",
        "header": "South China - Indonesia RV (Supramax) [usd/day] (tsid_120137)",
        "notes": "Supramax Southeast Asia nickel/coal RV in USD/day. Rate range $7.5k-$17.9k/day."
    },
    120654: {
        "label": "Capesize Pacific RV",
        "class": "Capesize",
        "unit": "usd/day",
        "header": "Pacific RV (Capesize) [usd/day] (tsid_120654)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Supramax. Rate range $16.4k-$63.2k/day (latest $62.4k). Exact match to fetch_dry_routes_ts.py CAPESIZE_PACIFIC_RV."
    },
    120655: {
        "label": "Capesize TCE Cont/Far East",
        "class": "Capesize",
        "unit": "usd/day",
        "header": "TCE Cont/Far East (Capesize) [usd/day] (tsid_120655)",
        "notes": "CRITICAL FIX: Formerly mislabelled as Supramax. Rate range $41.1k-$93.1k/day (latest $91.2k). Exact match to fetch_dry_routes_ts.py CAPESIZE_TCE_CONT_FAR_EAST."
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
            meta["unit"] = mapping["unit"]
            meta["notes"] = mapping["notes"]

    print(f"Rewriting {JSON_PATH} with updated catalog metadata...")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Successfully updated JSON catalog.")

if __name__ == "__main__":
    fix_csv()
    fix_json()
