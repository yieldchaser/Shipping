#!/usr/bin/env python3
"""
Target 10 / Prompt 13B C4 — Minor Bulks Seaborne Trade Flow Harvester
====================================================================
Synthesizes monthly trade flows across the 6 major minor bulk commodities
using the strict UN Comtrade client (motCode==0, customsCode=='C00', partner2Code==0):
1. Sugar: Brazil exports (HS 1701 / ComexStat NCM 1701) — world's #1 exporter, Supramax/Handy driver
2. Urea / Fertiliser: India & Brazil imports (HS 3102 / 3105) — key agricultural input trade
3. Alumina: China imports (HS 2818) — bauxite downstream value chain, Handymax/Supramax
4. Nickel Ore: Philippines exports (HS 2604) to China — Supramax round-voyage driver
5. Scrap Steel: Türkiye imports (HS 7204) — world's #1 seaborne scrap buyer, Supramax/Handy
6. Cement & Clinker: Türkiye/Vietnam exports (HS 2523) — Handysize shortsea & deepsea trade

Outputs:
- data/commodities/minor_bulks_monthly.csv
- data/commodities/minor_bulks_metadata.json
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.acquire.comtrade_client import fetch_comtrade_monthly, select_total

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = COMMODITIES_DIR / "minor_bulks_monthly.csv"
OUT_JSON = COMMODITIES_DIR / "minor_bulks_metadata.json"
MANIFEST_FILE = REPO_ROOT / "data" / "provenance" / "manifest.json"

TARGET_FLOWS = [
    {
        "commodity": "Sugar",
        "hs_code": "1701",
        "reporter_code": "76",
        "reporter_name": "Brazil",
        "flow_code": "X",  # Exports
        "partner_code": "0",  # World
        "vessel_class": "Supramax / Handysize",
        "description": "Raw and refined cane sugar seaborne exports from Brazil (Santos / Paranaguá)",
        "unit": "tonnes",
    },
    {
        "commodity": "Urea / Fertiliser",
        "hs_code": "3102",
        "reporter_code": "699",  # India
        "reporter_name": "India",
        "flow_code": "M",  # Imports
        "partner_code": "0",
        "vessel_class": "Handysize / Supramax",
        "description": "Mineral or chemical nitrogenous fertilisers / urea imports into India",
        "unit": "tonnes",
    },
    {
        "commodity": "Fertiliser (NPK/DAP)",
        "hs_code": "3105",
        "reporter_code": "76",  # Brazil
        "reporter_name": "Brazil",
        "flow_code": "M",  # Imports
        "partner_code": "0",
        "vessel_class": "Supramax / Handysize",
        "description": "Mineral or chemical fertilisers containing two or three fertilising elements into Brazil",
        "unit": "tonnes",
    },
    {
        "commodity": "Alumina",
        "hs_code": "2818",
        "reporter_code": "156",  # China
        "reporter_name": "China",
        "flow_code": "M",  # Imports
        "partner_code": "0",
        "vessel_class": "Handymax / Supramax",
        "description": "Aluminium oxide (alumina) and aluminium hydroxide imports into China",
        "unit": "tonnes",
    },
    {
        "commodity": "Nickel Ore",
        "hs_code": "2604",
        "reporter_code": "608",  # Philippines
        "reporter_name": "Philippines",
        "flow_code": "X",  # Exports
        "partner_code": "0",
        "vessel_class": "Supramax",
        "description": "Nickel ores and concentrates exports from the Philippines (primarily to China)",
        "unit": "tonnes",
    },
    {
        "commodity": "Scrap Steel",
        "hs_code": "7204",
        "reporter_code": "792",  # Türkiye
        "reporter_name": "Türkiye",
        "flow_code": "M",  # Imports
        "partner_code": "0",
        "vessel_class": "Supramax / Handysize",
        "description": "Ferrous waste and scrap imports into Türkiye (global scrap benchmark)",
        "unit": "tonnes",
    },
    {
        "commodity": "Cement / Clinker",
        "hs_code": "2523",
        "reporter_code": "792",  # Türkiye
        "reporter_name": "Türkiye",
        "flow_code": "X",  # Exports
        "partner_code": "0",
        "vessel_class": "Handysize",
        "description": "Portland cement, aluminous cement, slag cement and hydraulic cements exports from Türkiye",
        "unit": "tonnes",
    },
]


def run_minor_bulks_harvest():
    records = []

    # Generate monthly periods: 2022-01 to 2026-07
    periods = []
    for y in range(2022, 2027):
        max_m = 12
        if y == 2026:
            max_m = 7
        for m in range(1, max_m + 1):
            periods.append(f"{y}{m:02d}")

    logging.info("Starting minor bulks harvest with strict Comtrade total selector across %d flows and %d periods...",
                 len(TARGET_FLOWS), len(periods))

    # Also load Brazil ComexStat local CSV if available for Sugar
    comex_sugar = {}
    brazil_csv = COMMODITIES_DIR / "brazil_comexstat_exports.csv"
    if brazil_csv.exists():
        try:
            df_b = pd.read_csv(brazil_csv)
            sugar_df = df_b[df_b["commodity"].str.contains("Sugar", case=False, na=False)]
            for _, r in sugar_df.iterrows():
                p = f"{r['year']}{int(r['month']):02d}"
                comex_sugar[p] = {
                    "metric_tonnes": float(r["metric_tonnes"]),
                    "value_usd": float(r["fob_usd"]),
                    "source": "Brazil MDIC ComexStat (NCM 1701)",
                }
            logging.info("Loaded %d historical sugar observations from Brazil ComexStat", len(comex_sugar))
        except Exception as e:
            logging.warning("Failed loading ComexStat sugar: %s", e)

    total_fetched = 0
    sub_1000_reports = []

    for flow in TARGET_FLOWS:
        c_name = flow["commodity"]
        logging.info("Processing commodity flow: %s (%s - %s)", c_name, flow["reporter_name"], flow["hs_code"])

        for p in periods:
            dt_str = f"{p[:4]}-{p[4:6]}-01"

            # Check local Brazil ComexStat for sugar first if available
            if c_name == "Sugar" and p in comex_sugar:
                rec_val = comex_sugar[p]
                records.append({
                    "date": dt_str,
                    "period": p,
                    "commodity": c_name,
                    "trade_flow": "Exports" if flow["flow_code"] == "X" else "Imports",
                    "reporter_country": flow["reporter_name"],
                    "partner_country": "World",
                    "hs_code": flow["hs_code"],
                    "metric_tonnes": rec_val["metric_tonnes"],
                    "value_usd": rec_val["value_usd"],
                    "vessel_demand_impact": flow["vessel_class"],
                    "source": rec_val["source"],
                    "source_url": "https://api-comexstat.mdic.gov.br/general",
                })
                continue

            res = fetch_comtrade_monthly(
                reporter_code=flow["reporter_code"],
                partner_code=flow["partner_code"],
                cmd_code=flow["hs_code"],
                flow_code=flow["flow_code"],
                period=p,
            )

            if res and res.get("metric_tonnes", 0) > 0:
                mt = res["metric_tonnes"]
                val = res["value_usd"]
                total_fetched += 1

                # Plausibility floor audit per C4
                if mt < 1000.0:
                    sub_1000_reports.append({
                        "commodity": c_name,
                        "period": p,
                        "metric_tonnes": mt,
                        "value_usd": val,
                        "url": res["source_url"],
                    })

                records.append({
                    "date": dt_str,
                    "period": p,
                    "commodity": c_name,
                    "trade_flow": "Exports" if flow["flow_code"] == "X" else "Imports",
                    "reporter_country": flow["reporter_name"],
                    "partner_country": "World",
                    "hs_code": flow["hs_code"],
                    "metric_tonnes": mt,
                    "value_usd": val,
                    "vessel_demand_impact": flow["vessel_class"],
                    "source": f"UN Comtrade (Reporter {flow['reporter_name']}, HS {flow['hs_code']})",
                    "source_url": res["source_url"],
                })

    if sub_1000_reports:
        logging.info("Reporting %d rows below 1,000 t plausibility floor (retained as authentic select_total returns):", len(sub_1000_reports))
        for item in sub_1000_reports[:5]:
            logging.info("  %s (%s): %.2f tonnes, $%.2f", item["commodity"], item["period"], item["metric_tonnes"], item["value_usd"])

    df = pd.DataFrame(records)
    if df.empty:
        logging.error("No records harvested for minor bulks!")
        return

    df.sort_values(by=["date", "commodity"], inplace=True)
    df.to_csv(OUT_CSV, index=False)
    logging.info("Saved %d verified minor bulks records to %s", len(df), OUT_CSV)

    summary_by_commodity = {}
    for c_name, group in df.groupby("commodity"):
        summary_by_commodity[c_name] = {
            "total_records": int(len(group)),
            "min_date": str(group["date"].min()),
            "max_date": str(group["date"].max()),
            "mean_monthly_tonnes": round(float(group["metric_tonnes"].mean()), 1),
            "max_monthly_tonnes": round(float(group["metric_tonnes"].max()), 1),
            "total_volume_tonnes": round(float(group["metric_tonnes"].sum()), 1),
            "total_fob_usd": round(float(group["value_usd"].sum()), 1),
            "vessel_class": group["vessel_demand_impact"].iloc[0],
            "reporter": group["reporter_country"].iloc[0],
            "flow": group["trade_flow"].iloc[0],
        }

    meta = {
        "dataset_name": "Seaborne Minor Bulks Monthly Trade Flows",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(df),
        "date_span": f"{df['date'].min()} to {df['date'].max()}",
        "commodities_covered": list(summary_by_commodity.keys()),
        "commodity_summaries": summary_by_commodity,
        "sub_1000_tonnes_audited_count": len(sub_1000_reports),
        "shipping_impact_thesis": {
            "Sugar": "Brazil export peaks (May-Nov) trigger intensive Supramax/Handysize chartering from Santos/Paranagua.",
            "Urea / Fertiliser": "Indian kharif/rabi agricultural import seasons drive major Supramax tonnage inbound from Baltic/Black Sea/Persian Gulf.",
            "Fertiliser (NPK/DAP)": "Brazil soybean/corn soil preparation drives massive fertiliser imports into Paranagua/Santos.",
            "Alumina": "China imports from Australia and Guinea/Indonesia sustain continuous Handymax industrial supply lines.",
            "Nickel Ore": "Philippines monsoon seasonality (April-Oct dry season peak) governs Surigao-to-China Supramax loading runs.",
            "Scrap Steel": "Türkiye electric-arc-furnace steel mills import 1.5-2.0 Mt/mo, establishing deepsea Supramax benchmark rates from US/Europe.",
            "Cement / Clinker": "Türkiye and Vietnam regional export surpluses drive Handysize coastal and deepsea distribution across Mediterranean and West Africa."
        }
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logging.info("Saved minor bulks metadata to %s", OUT_JSON)

    update_manifest(len(df), df["date"].min(), df["date"].max())


def update_manifest(row_count, min_date, max_date):
    if not MANIFEST_FILE.exists():
        return
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    series_list = manifest.get("datasets", [])
    series_id = "commodities_minor_bulks_monthly"
    entry_data = {
        "series_id": series_id,
        "display_name": "Commodities — Seaborne Minor Bulks Monthly Trade Flows",
        "status": "LIVE",
        "source_name": "UN Comtrade (select_total verified) & Brazil MDIC ComexStat",
        "source_url": "https://comtradeapi.un.org",
        "fetch_method": "Strict Comtrade API & ComexStat Harvester",
        "fetch_script": "scripts/acquire/fetch_minor_bulks.py",
        "output_file": "data/commodities/minor_bulks_monthly.csv",
        "row_count": row_count,
        "date_span": [min_date, max_date],
        "last_fetched_utc": datetime.now(timezone.utc).isoformat(),
        "unit": "Tonnes / USD FOB/CIF",
        "is_derived": False,
        "derivation": None,
        "notes": (
            f"Monthly seaborne trade volume and value across 6 vital minor bulks using strict UN Comtrade total selection "
            f"(motCode=0, customsCode=C00, partner2Code=0). Sugar, Urea/Fertiliser, NPK/DAP, Alumina, Nickel Ore, Scrap Steel, "
            f"and Cement/Clinker. Spans {min_date} to {max_date} with {row_count} monthly observations."
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
    logging.info("Updated manifest.json with series %s (%d rows)", series_id, row_count)


if __name__ == "__main__":
    run_minor_bulks_harvest()
