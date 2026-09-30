"""
stack_banchero_series.py

Aggregates structured data from all data/extracted/md/banchero_costa/*.tables.json files
into master stacked time-series CSV files in data/extracted/series/:
1. bancosta_sales_series.csv (S&P reported sales with 7-digit IMO numbers)
2. bancosta_freight_rates_series.csv (Capesize, Panamax, Supramax, Handysize, Crude/Dirty Tankers, Clean Tankers)
3. bancosta_ffa_series.csv (Dry bulk FFA forward curve assessments)
4. bancosta_newbuilding_series.csv (Indicative newbuilding prices $/m)
5. bancosta_demolition_series.csv (Ship recycling assessments $/ldt)
6. bancosta_secondhand_matrix_series.csv (Baltic secondhand assessments $/m)
7. bancosta_container_fixtures_series.csv (Containership fixtures)
8. bancosta_vhss_series.csv (VHSS ConTex indices)
9. bancosta_fx_series.csv (Exchange rates)
10. bancosta_commodities_series.csv (Commodity price benchmarks)
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"
SERIES_DIR = ROOT / "data" / "extracted" / "series"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stack_banchero")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {len(rows):,} rows to {path.name}")


def stack_all():
    json_files = sorted(MD_DIR.glob("*.tables.json"))
    logger.info(f"Found {len(json_files)} .tables.json files in {MD_DIR}")

    sales_rows = []
    freight_rows = []
    ffa_rows = []
    nb_rows = []
    demo_rows = []
    sh_rows = []
    container_rows = []
    vhss_rows = []
    fx_rows = []
    commodity_rows = []

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error reading {jf.name}: {e}")
            continue

        meta = data.get("metadata", {})
        issue_date = meta.get("issue_date", "")
        report_week = meta.get("report_week", 1)
        source_file = meta.get("source_file", jf.name)

        # 1. Reported Sales
        for r in data.get("reported_sales", []):
            sales_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "vessel_type": r.get("vessel_type", ""),
                "vessel": r.get("vessel", ""),
                "imo": r.get("imo", ""),
                "dwt": r.get("dwt", ""),
                "built": r.get("built", ""),
                "yard": r.get("yard", ""),
                "buyer": r.get("buyer", ""),
                "seller": r.get("seller", ""),
                "price_usd_m": r.get("price_usd_m", ""),
                "ss_due": r.get("ss_due", ""),
                "dd_due": r.get("dd_due", ""),
                "delivery": r.get("delivery", ""),
                "comments": r.get("comments", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 2. Freight Benchmarks
        for r in data.get("freight_benchmarks", []):
            freight_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "sector": r.get("sector", ""),
                "route_or_benchmark": r.get("route_or_benchmark", ""),
                "unit": r.get("unit", ""),
                "rate_current": r.get("rate_current", ""),
                "rate_previous": r.get("rate_previous", ""),
                "change_wow": r.get("change_wow", ""),
                "change_yoy": r.get("change_yoy", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 3. FFA Assessments
        for r in data.get("ffa_assessments", []):
            ffa_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "vessel_class": r.get("vessel_class", ""),
                "tenor": r.get("tenor", ""),
                "unit": r.get("unit", ""),
                "rate_current": r.get("rate_current", ""),
                "rate_previous": r.get("rate_previous", ""),
                "change_wow": r.get("change_wow", ""),
                "premium": r.get("premium", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 4. Newbuilding Prices
        for r in data.get("newbuilding_prices", []):
            nb_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "vessel_type": r.get("vessel_type", ""),
                "price_usd_m": r.get("price_usd_m", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 5. Demolition Assessments
        for r in data.get("demolition_assessments", []):
            country_seg = r.get("segment_country", r.get("country", ""))
            demo_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "segment_country": country_seg,
                "price_usd_per_ldt": r.get("price_usd_per_ldt", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 6. Secondhand Assessments
        for r in data.get("secondhand_assessments", []):
            sh_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "vessel_type": r.get("vessel_type", ""),
                "price_usd_m": r.get("price_usd_m", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 7. Container Fixtures
        for r in data.get("container_fixtures", []):
            container_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "vessel_name": r.get("vessel_name", ""),
                "built": r.get("built", ""),
                "teu": r.get("teu", ""),
                "teu_14": r.get("teu_14", ""),
                "gear": r.get("gear", ""),
                "account": r.get("account", ""),
                "period_mos": r.get("period_mos", ""),
                "rate_usd_day": r.get("rate_usd_day", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 8. VHSS ConTex
        for r in data.get("vhss_contex", []):
            vhss_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "segment": r.get("segment", ""),
                "unit": r.get("unit", ""),
                "value_current": r.get("value_current", ""),
                "value_previous": r.get("value_previous", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 9. Currencies / FX
        for r in data.get("currencies", []):
            fx_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "currency_pair": r.get("currency_pair", ""),
                "rate_current": r.get("rate_current", ""),
                "rate_previous": r.get("rate_previous", ""),
                "source_file": r.get("source_file", source_file),
            })

        # 10. Commodity Prices
        for r in data.get("commodity_prices", []):
            commodity_rows.append({
                "issue_date": r.get("issue_date", issue_date),
                "report_week": r.get("report_week", report_week),
                "category": r.get("category", ""),
                "item": r.get("item", ""),
                "unit": r.get("unit", ""),
                "price_current": r.get("price_current", ""),
                "price_previous": r.get("price_previous", ""),
                "source_file": r.get("source_file", source_file),
            })

    # Sort each series by issue_date
    sales_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["vessel_type"], x["vessel"]))
    freight_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["sector"], x["route_or_benchmark"]))
    ffa_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["vessel_class"], x["tenor"]))
    nb_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["vessel_type"]))
    demo_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["segment_country"]))
    sh_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["vessel_type"]))
    container_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["vessel_name"]))
    vhss_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["segment"]))
    fx_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["currency_pair"]))
    commodity_rows.sort(key=lambda x: (x["issue_date"], x["report_week"], x["category"], x["item"]))

    # Write CSVs
    write_csv(
        SERIES_DIR / "bancosta_sales_series.csv",
        sales_rows,
        ["issue_date", "report_week", "vessel_type", "vessel", "imo", "dwt", "built", "yard", "buyer", "seller", "price_usd_m", "ss_due", "dd_due", "delivery", "comments", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_freight_rates_series.csv",
        freight_rows,
        ["issue_date", "report_week", "sector", "route_or_benchmark", "unit", "rate_current", "rate_previous", "change_wow", "change_yoy", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_ffa_series.csv",
        ffa_rows,
        ["issue_date", "report_week", "vessel_class", "tenor", "unit", "rate_current", "rate_previous", "change_wow", "premium", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_newbuilding_series.csv",
        nb_rows,
        ["issue_date", "report_week", "vessel_type", "price_usd_m", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_demolition_series.csv",
        demo_rows,
        ["issue_date", "report_week", "segment_country", "price_usd_per_ldt", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_secondhand_matrix_series.csv",
        sh_rows,
        ["issue_date", "report_week", "vessel_type", "price_usd_m", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_container_fixtures_series.csv",
        container_rows,
        ["issue_date", "report_week", "vessel_name", "built", "teu", "teu_14", "gear", "account", "period_mos", "rate_usd_day", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_vhss_series.csv",
        vhss_rows,
        ["issue_date", "report_week", "segment", "unit", "value_current", "value_previous", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_fx_series.csv",
        fx_rows,
        ["issue_date", "report_week", "currency_pair", "rate_current", "rate_previous", "source_file"]
    )
    write_csv(
        SERIES_DIR / "bancosta_commodities_series.csv",
        commodity_rows,
        ["issue_date", "report_week", "category", "item", "unit", "price_current", "price_previous", "source_file"]
    )


if __name__ == "__main__":
    stack_all()
