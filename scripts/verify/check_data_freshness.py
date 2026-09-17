#!/usr/bin/env python3
"""
check_data_freshness.py — Cargo & Trade Flows Freshness Guard
============================================================
Evaluates every #tab-cargo dataset against the official publication lag schedule
defined in AGENT_HANDOFF.md §1. Computes the expected latest period dynamically
from the current date.

If any dataset is behind schedule:
  - Fails with returncode 1
  - Prints a structured report detailing current period vs expected period
  - Optionally opens or updates a consolidated GitHub issue (--create-issue)
"""

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parents[2]
COMMODITIES_DIR = ROOT / "data" / "commodities"


def get_prev_month(dt: date, n: int = 1) -> str:
    """Return YYYY-MM string for n months before dt."""
    year = dt.year
    month = dt.month - n
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def get_latest_csv_date(csv_path: Path, date_col: str = "date") -> str:
    """Return max date string in a CSV file."""
    if not csv_path.exists():
        return ""
    try:
        df = pd.read_csv(csv_path, usecols=[date_col])
        valid_dates = df[date_col].dropna().astype(str).str.strip()
        if valid_dates.empty:
            return ""
        return valid_dates.max()
    except Exception as e:
        logging.warning("Error reading %s: %s", csv_path.name, e)
        return ""


def evaluate_freshness(today: date | None = None) -> list[dict]:
    """
    Evaluate all 16 cargo datasets against AGENT_HANDOFF.md §1 lag rules.
    Returns list of check result dictionaries.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    results = []

    # 1. Brazil ComexStat (M-1 expected after the 7th working day, ~8th of month)
    # --------------------------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 8 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "brazil_comexstat_exports.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Brazil ComexStat Exports (HS 26011100)",
        "file": "brazil_comexstat_exports.csv",
        "category": "Monthly",
        "rule": "M-1 after ~7th working day",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 2. Pilbara Ports Authority (M-1 expected after ~20th of M+1)
    # ------------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 21 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "australia_ppa_iron_ore.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Pilbara Ports Authority (Port Hedland / Dampier)",
        "file": "australia_ppa_iron_ore.csv",
        "category": "Monthly",
        "rule": "M-1 after ~20th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 3. US EIA Weekly Crude Exports (within 10 days of today)
    # -------------------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "us_eia_weekly_crude_exports.csv")[:10]
    days_lag = None
    if latest_val:
        try:
            ld = datetime.strptime(latest_val, "%Y-%m-%d").date()
            days_lag = (today - ld).days
            is_fresh = days_lag <= 10
        except ValueError:
            is_fresh = False
    else:
        is_fresh = False
    results.append({
        "name": "US EIA Weekly Crude Exports",
        "file": "us_eia_weekly_crude_exports.csv",
        "category": "Weekly",
        "rule": "Within 10 days of today",
        "latest_stored": latest_val,
        "expected": f"<= 10 days lag (current lag: {days_lag}d)",
        "is_fresh": is_fresh,
        "detail": f"Latest week: {latest_val} ({days_lag} days ago)"
    })

    # 4. Newcastle Coal (TfNSW CKAN) (M-1 expected after ~20th of M+1)
    # ----------------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 21 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "newcastle_coal_exports.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Newcastle Coal Exports (TfNSW)",
        "file": "newcastle_coal_exports.csv",
        "category": "Monthly",
        "rule": "M-1 after ~20th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 5. Indonesia Coal (BPS) (M-1 expected after ~20th of M+1)
    # ---------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 21 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "indonesia_coal_exports_monthly.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Indonesia Coal Exports (BPS)",
        "file": "indonesia_coal_exports_monthly.csv",
        "category": "Monthly",
        "rule": "M-1 after ~20th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 6. Guinea Bauxite Mirror (chinadata / GACC) (M-1 after ~25th of M+1)
    # --------------------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 26 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "china_customs_guinea_bauxite_partner_usd.csv", date_col="period")
    if not latest_val:
        latest_val = get_latest_csv_date(COMMODITIES_DIR / "guinea_bauxite_exports.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Guinea Bauxite Mirror (GACC / chinadata)",
        "file": "china_customs_guinea_bauxite_partner_usd.csv",
        "category": "Monthly",
        "rule": "M-1 after ~25th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 7. Minor Bulks (TurkStat Cement/Scrap, TradeStat Urea, PSA Nickel, Sugar, NPK)
    # ------------------------------------------------------------------------------
    mb_csv = COMMODITIES_DIR / "minor_bulks_monthly.csv"
    mb_latest = {}
    if mb_csv.exists():
        df_mb = pd.read_csv(mb_csv)
        for cmd in df_mb["commodity"].unique():
            sub = df_mb[df_mb["commodity"] == cmd]
            mb_latest[cmd] = sub["date"].max()[:7]

    # 7a. TurkStat Cement (published at end of M+1, so available in M+2)
    # E.g. July (M) is published at end of August (M+1); August is published at end of September.
    # Therefore, during September (M+1 for August), expected latest is July (2026-07).
    exp_turk = get_prev_month(today, 2)
    cement_latest = mb_latest.get("Cement / Clinker", "")
    is_fresh = cement_latest >= exp_turk if cement_latest else False
    results.append({
        "name": "Minor Bulks: Cement Exports (Türkiye / TurkStat)",
        "file": "minor_bulks_monthly.csv",
        "category": "Monthly",
        "rule": "End of M+1 (~last day of M+1)",
        "latest_stored": cement_latest,
        "expected": exp_turk,
        "is_fresh": is_fresh,
        "detail": f"Latest: {cement_latest} | Expected: {exp_turk}"
    })

    # 7b. TurkStat Scrap Steel (published at end of M+1, so available in M+2)
    scrap_latest = mb_latest.get("Scrap Steel", "")
    is_fresh = scrap_latest >= exp_turk if scrap_latest else False
    results.append({
        "name": "Minor Bulks: Scrap Steel Imports (Türkiye / TurkStat)",
        "file": "minor_bulks_monthly.csv",
        "category": "Monthly",
        "rule": "End of M+1 (~last day of M+1)",
        "latest_stored": scrap_latest,
        "expected": exp_turk,
        "is_fresh": is_fresh,
        "detail": f"Latest: {scrap_latest} | Expected: {exp_turk}"
    })

    # 7c. India Urea (DGCI&S TradeStat ~M+1.5)
    exp_urea = get_prev_month(today, 2) if today.day < 20 else get_prev_month(today, 1)
    urea_latest = mb_latest.get("Urea / Fertiliser", "")
    is_fresh = urea_latest >= exp_urea if urea_latest else False
    results.append({
        "name": "Minor Bulks: Urea Imports (India / TradeStat)",
        "file": "minor_bulks_monthly.csv",
        "category": "Monthly",
        "rule": "~M+1.5 lag",
        "latest_stored": urea_latest,
        "expected": exp_urea,
        "is_fresh": is_fresh,
        "detail": f"Latest: {urea_latest} | Expected: {exp_urea}"
    })

    # 7d. Philippines Nickel Ore (PSA OpenSTAT ~M+1.5)
    exp_nickel = get_prev_month(today, 2) if today.day < 20 else get_prev_month(today, 1)
    nickel_latest = mb_latest.get("Nickel Ore", "")
    is_fresh = nickel_latest >= exp_nickel if nickel_latest else False
    results.append({
        "name": "Minor Bulks: Nickel Ore Exports (Philippines / PSA)",
        "file": "minor_bulks_monthly.csv",
        "category": "Monthly",
        "rule": "~M+1.5 lag",
        "latest_stored": nickel_latest,
        "expected": exp_nickel,
        "is_fresh": is_fresh,
        "detail": f"Latest: {nickel_latest} | Expected: {exp_nickel}"
    })

    # 8. Australia REQ (Quarterly: June edition covers Q1/Mar; Sep edition due late Sep covers Q2/Jun)
    # ---------------------------------------------------------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "australia_req_commodity_exports.csv")
    req_fresh = bool(latest_val and latest_val >= "2026-03")
    results.append({
        "name": "Australia REQ Historical Volumes (DISR)",
        "file": "australia_req_commodity_exports.csv",
        "category": "Quarterly",
        "rule": "Latest published edition (~1 quarter lag)",
        "latest_stored": latest_val[:7] if latest_val else "",
        "expected": ">= 2026-03",
        "is_fresh": req_fresh,
        "detail": f"Latest quarter: {latest_val}"
    })

    # 9. Argentina Grain (MAGyP) (~25th of M+1)
    # -----------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 26 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "argentina_grain_exports_monthly.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "Argentina Grain Seaborne Loadings (MAGyP)",
        "file": "argentina_grain_exports_monthly.csv",
        "category": "Monthly",
        "rule": "M-1 after ~25th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 10. USDA FAS Export Sales (within 14 days of today)
    # --------------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "usda_fas_outstanding_export_sales.csv")[:10]
    days_lag = None
    if latest_val:
        try:
            ld = datetime.strptime(latest_val, "%Y-%m-%d").date()
            days_lag = (today - ld).days
            is_fresh = days_lag <= 14
        except ValueError:
            is_fresh = False
    else:
        is_fresh = False
    results.append({
        "name": "USDA FAS Weekly Export Sales (885i-uek7)",
        "file": "usda_fas_outstanding_export_sales.csv",
        "category": "Weekly",
        "rule": "Within 14 days of today",
        "latest_stored": latest_val,
        "expected": f"<= 14 days lag (current lag: {days_lag}d)",
        "is_fresh": is_fresh,
        "detail": f"Latest week: {latest_val} ({days_lag} days ago)"
    })

    # 11. USDA FGIS Grain Inspections (within 10 days of today)
    # ---------------------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "usda_ytd_grain_inspections_top20.csv")[:10]
    days_lag = None
    if latest_val:
        try:
            ld = datetime.strptime(latest_val, "%Y-%m-%d").date()
            days_lag = (today - ld).days
            is_fresh = days_lag <= 10
        except ValueError:
            is_fresh = False
    else:
        is_fresh = False
    results.append({
        "name": "USDA FGIS Grain Inspections (CY2026/5sxb-qe7q)",
        "file": "usda_ytd_grain_inspections_top20.csv",
        "category": "Weekly",
        "rule": "Within 10 days of today",
        "latest_stored": latest_val,
        "expected": f"<= 10 days lag (current lag: {days_lag}d)",
        "is_fresh": is_fresh,
        "detail": f"Latest cert date: {latest_val} ({days_lag} days ago)"
    })

    # 12. USDA Vessel Queues (within 14 days of today)
    # -----------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "usda_grain_vessel_loading_queues.csv")[:10]
    days_lag = None
    if latest_val:
        try:
            ld = datetime.strptime(latest_val, "%Y-%m-%d").date()
            days_lag = (today - ld).days
            is_fresh = days_lag <= 14
        except ValueError:
            is_fresh = False
    else:
        is_fresh = False
    results.append({
        "name": "USDA Vessel Queues (GTR Table 19)",
        "file": "usda_grain_vessel_loading_queues.csv",
        "category": "Weekly",
        "rule": "Within 14 days of today",
        "latest_stored": latest_val,
        "expected": f"<= 14 days lag (current lag: {days_lag}d)",
        "is_fresh": is_fresh,
        "detail": f"Latest GTR date: {latest_val} ({days_lag} days ago)"
    })

    # 13. World Crude Steel (worldsteel) (~25th of M+1)
    # -------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 26 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "world_crude_steel_monthly.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "World Crude Steel Production (worldsteel)",
        "file": "world_crude_steel_monthly.csv",
        "category": "Monthly",
        "rule": "M-1 after ~25th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 14. China Customs Monthly Imports (HS 72 / chinadata) (~25th of M+1)
    # --------------------------------------------------------------------
    exp_month = get_prev_month(today, 1) if today.day >= 26 else get_prev_month(today, 2)
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "china_customs_monthly_imports.csv")[:7]
    is_fresh = latest_val >= exp_month if latest_val else False
    results.append({
        "name": "China Customs Monthly Imports (HS 72 / chinadata)",
        "file": "china_customs_monthly_imports.csv",
        "category": "Monthly",
        "rule": "M-1 after ~25th of month",
        "latest_stored": latest_val,
        "expected": exp_month,
        "is_fresh": is_fresh,
        "detail": f"Latest: {latest_val} | Expected: {exp_month}"
    })

    # 15. Major Iron Ore Miners (Quarterly: ~40 days lag after Q end)
    # ---------------------------------------------------------------
    latest_val = get_latest_csv_date(COMMODITIES_DIR / "major_miners_quarterly_shipments.csv", date_col="quarter")
    norm_val = latest_val.replace(" ", "-") if latest_val else ""
    miners_fresh = bool(norm_val and (norm_val >= "2026-Q2" or norm_val >= "2026Q2"))
    results.append({
        "name": "Major Iron Ore Miners Shipments (EDGAR / ASX)",
        "file": "major_miners_quarterly_shipments.csv",
        "category": "Quarterly",
        "rule": "Latest completed quarter (~35 days lag)",
        "latest_stored": latest_val,
        "expected": ">= 2026-Q2",
        "is_fresh": miners_fresh,
        "detail": f"Latest quarter: {latest_val}"
    })

    return results


def sync_github_issue(stale_items: list[dict]):
    """Open or update a single consolidated GitHub issue listing stale datasets."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        logging.warning("No GH_TOKEN available; skipping GitHub issue management.")
        return

    title = "Cargo & Trade Flows Freshness Alert: Stale Upstream Datasets"
    body_lines = [
        "## Automated Cargo Data Freshness Guard",
        f"**Run Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "The following cargo and commodity flow datasets are behind their scheduled publication lag window:",
        "",
        "| Dataset | File | Category | Latest Stored | Expected | Rule |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for item in stale_items:
        body_lines.append(f"| {item['name']} | `{item['file']}` | {item['category']} | **{item['latest_stored']}** | **{item['expected']}** | {item['rule']} |")

    body_lines.extend([
        "",
        "### Recommended Actions",
        "1. Check upstream authority endpoint availability and anti-bot challenge status.",
        "2. If an endpoint is rate-limited (e.g. ComexStat 429) or IP-blocked (e.g. TurkStat 503), inspect runner logs.",
        "3. For TurkStat Cement on cloud runners, trigger the self-hosted runner workflow per `docs/gap_fill/TURKSTAT_SELF_HOSTED.md`.",
        "",
        "_This issue was automatically generated by `scripts/verify/check_data_freshness.py`._"
    ])
    body = "\n".join(body_lines)

    try:
        # Search for existing open issue with this title
        proc = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search", title, "--json", "number"],
            capture_output=True, text=True, check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            issues = json.loads(proc.stdout)
            if issues:
                issue_num = str(issues[0]["number"])
                logging.info("Updating existing freshness issue #%s...", issue_num)
                subprocess.run(["gh", "issue", "edit", issue_num, "--body", body], check=False)
                return

        # Otherwise create a new issue
        logging.info("Creating new freshness alert issue...")
        subprocess.run(["gh", "issue", "create", "--title", title, "--body", body, "--label", "bug"], check=False)
    except Exception as e:
        logging.warning("Failed to manage GitHub issue: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Check freshness of all cargo datasets against lag table")
    parser.add_argument("--create-issue", action="store_true", help="Open or update GitHub issue if any dataset is stale")
    parser.add_argument("--as-of", type=str, default=None, help="Evaluation date (YYYY-MM-DD), default is today")
    args = parser.parse_args()

    eval_date = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else datetime.now(timezone.utc).date()
    logging.info("Evaluating cargo data freshness as of %s...", eval_date)

    results = evaluate_freshness(eval_date)
    stale_items = [r for r in results if not r["is_fresh"]]

    print("\n" + "=" * 90)
    print(f"CARGO DATA FRESHNESS AUDIT (As of {eval_date})")
    print("=" * 90)
    print(f"{'Dataset':<42} | {'Latest':<10} | {'Expected':<12} | {'Status':<6}")
    print("-" * 90)
    for r in results:
        status = "FRESH" if r["is_fresh"] else "STALE"
        print(f"{r['name'][:42]:<42} | {str(r['latest_stored'])[:10]:<10} | {str(r['expected'])[:12]:<12} | {status:<6}")
    print("=" * 90)
    print(f"SUMMARY: {len(results) - len(stale_items)}/{len(results)} FRESH, {len(stale_items)} STALE\n")

    if stale_items:
        logging.error("Freshness guard detected %d stale dataset(s):", len(stale_items))
        for item in stale_items:
            logging.error("  - %s: latest stored '%s' < expected '%s' (%s)", item["name"], item["latest_stored"], item["expected"], item["rule"])

        if args.create_issue:
            sync_github_issue(stale_items)

        sys.exit(1)
    else:
        logging.info("All %d cargo datasets are completely fresh against the publication schedule!", len(results))
        sys.exit(0)


if __name__ == "__main__":
    main()
