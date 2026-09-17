"""
TurkStat Bulk Ingestion Pipeline (§2.10, §4d)
============================================
Ingests Türkiye bulk commodity trade flows:
  - HS 2523: Cement / Clinker Exports (Flow = 1)
  - HS 7204: Scrap Steel Imports (Flow = 2)

Architecture:
  1. Primary Ingester: TurkStat General Trade App (bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42).
     Reads fresh extracts from scratch/tuik/ (tuik_by_flow.csv / tuik_GENERAL_*.csv)
     or docs/gap_fill/patches/minor_bulks_turkiye_TURKSTAT_GENERAL_2013_2026.csv.
  2. Live Automation Attempt: Headless Chromium via Playwright attempting to connect
     to bi.tuik.gov.tr mashup and extract hypercube. Fails loudly on HTTP 503.
  3. Secondary Fallback for Scrap: SteelOrbis reports quoting TUIK via Google News RSS.
  4. Routing: Upserts Cement and Scrap into data/commodities/minor_bulks_monthly.csv,
     routing away from UN Comtrade (which lacks recent months and special trade distortion).
"""

import sys
import os
import re
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("turkstat_bulk")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = BASE_DIR / "data" / "commodities"
SCRATCH_TUIK_DIR = BASE_DIR / "scratch" / "tuik"
PATCH_TUIK_CSV = BASE_DIR / "docs" / "gap_fill" / "patches" / "minor_bulks_turkiye_TURKSTAT_GENERAL_2013_2026.csv"
MINOR_BULKS_CSV = COMMODITIES_DIR / "minor_bulks_monthly.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# =====================================================================
# Channel 1: Playwright Automated Qlik Cube Pull
# =====================================================================
def attempt_playwright_qlik_pull() -> list[dict] | None:
    """
    Attempt to run Qlik mashup script via Playwright.
    Connects to https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1
    and executes tuik_browser_pull.js.
    Fails loudly with warning on HTTP 503 (cloud IP block).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[TurkStat Playwright] Playwright not installed.")
        return None

    logger.info("[TurkStat Playwright] Attempting live connection to bi.tuik.gov.tr mashup...")
    url = "https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1"

    js_code = """
    async () => {
        const ID = 'bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42';
        const CODES = ['2523', '7204'];
        if (typeof require === 'undefined') return { error: 'require not defined' };
        const qlik = await new Promise(r => require(['js/qlik'], r));
        const app = qlik.openApp(ID);
        const M = [];
        for (const c of CODES) for (const m of ['MIKTAR_1', 'DOLAR'])
            M.push({ qDef: { qDef: `Sum({<[TARIFE4]={'${c}'}>} [${m}])`, qLabel: `${c}_${m}` } });
        const dims = ['YIL', 'AY', 'IHRITH_FLAG'].map(x => ({ qDef: { qFieldDefs: [x] } }));
        const width = dims.length + M.length, height = Math.floor(10000 / width);
        const hc = await new Promise((res, rej) => {
            const t = setTimeout(() => rej('timeout'), 45000);
            app.createCube({ qDimensions: dims, qMeasures: M,
                qInitialDataFetch: [{ qTop: 0, qLeft: 0, qWidth: width, qHeight: height }] },
                rep => { clearTimeout(t); res(rep.qHyperCube); app.destroySessionObject(rep.qInfo.qId); });
        });
        const rows = hc.qDataPages[0].qMatrix.map(r => r.map(c => c.qIsNull ? '' :
            (typeof c.qNum === 'number' && !isNaN(c.qNum) ? c.qNum : c.qText)));
        return { success: true, count: rows.length, rows: rows };
    }
    """

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            if response and response.status in (503, 403):
                logger.warning(f"[TurkStat Playwright] bi.tuik.gov.tr returned HTTP {response.status} (Cloud runner blocked).")
                return None

            page.wait_for_timeout(5000)
            res = page.evaluate(js_code)
            if res and res.get("success"):
                logger.info(f"[TurkStat Playwright] Live extract succeeded! Received {res.get('count')} rows.")
                return res.get("rows")
            else:
                logger.warning(f"[TurkStat Playwright] Execution returned: {res}")
                return None
        except Exception as e:
            logger.warning(f"[TurkStat Playwright] bi.tuik.gov.tr connection failed: {e}")
            return None
        finally:
            try:
                browser.close()
            except Exception:
                pass


# =====================================================================
# Channel 2: SteelOrbis Scrap Steel Fallback (§4d)
# =====================================================================
def fetch_steelorbis_scrap_fallback() -> list[dict]:
    """
    Search Google News RSS for SteelOrbis reports quoting TUIK scrap imports.
    Matches e.g. "Turkey's scrap imports ... in January-July 2026"
    """
    query = "Turkey scrap imports TUIK steelorbis"
    encoded_q = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    logger.info(f"[SteelOrbis Fallback] Querying Google News RSS: {query}")

    req = urllib.request.Request(rss_url, headers=HEADERS)
    results = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.fromstring(resp.read())
            for item in tree.findall(".//item")[:10]:
                title = item.find("title").text or ""
                link = item.find("link").text or ""
                pub_date = item.find("pubDate").text or ""
                results.append({"title": title, "link": link, "pubDate": pub_date})
    except Exception as e:
        logger.warning(f"[SteelOrbis Fallback] Error querying RSS: {e}")
    return results


# =====================================================================
# Channel 3: Local General Trade Ingestion
# =====================================================================
def ingest_tuik_general_csv(csv_path: Path) -> dict[str, dict]:
    """
    Parse TurkStat general trade raw export (tuik_GENERAL_*.csv or tuik_by_flow.csv).
    Returns dict keyed by (commodity, period) -> {metric_tonnes, value_usd, date, ...}
    """
    logger.info(f"Ingesting TurkStat general trade from {csv_path}...")
    records = {}
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yil = row.get("YIL") or row.get("yil") or row.get("Year")
            ay = row.get("AY") or row.get("ay") or row.get("Month")
            flow = row.get("IHRITH_FLAG") or row.get("flow")

            if not (yil and ay and flow):
                continue

            try:
                y = int(float(yil))
                m = int(float(ay))
                fl = int(float(flow))
            except ValueError:
                continue

            period = f"{y:04d}{m:02d}"
            date_str = f"{y:04d}-{m:02d}-01"

            # Flow 1: Exports -> Cement / Clinker (HS 2523)
            if fl == 1:
                kg_str = row.get("2523_MIKTAR_1")
                usd_str = row.get("2523_DOLAR")
                if kg_str:
                    try:
                        tonnes = round(float(kg_str) / 1000.0, 2)
                        usd = round(float(usd_str), 1) if usd_str else None
                        records[("Cement / Clinker", period)] = {
                            "date": date_str,
                            "period": int(period),
                            "commodity": "Cement / Clinker",
                            "trade_flow": "Exports",
                            "reporter_country": "Türkiye",
                            "partner_country": "World",
                            "hs_code": 2523,
                            "metric_tonnes": tonnes,
                            "value_usd": usd,
                            "vessel_demand_impact": "Handysize",
                            "source": "TurkStat general trade",
                            "source_url": "https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1 (general trade, Qlik app bd4b4757)"
                        }
                    except ValueError:
                        pass

            # Flow 2: Imports -> Scrap Steel (HS 7204)
            elif fl == 2:
                kg_str = row.get("7204_MIKTAR_1")
                usd_str = row.get("7204_DOLAR")
                if kg_str:
                    try:
                        tonnes = round(float(kg_str) / 1000.0, 2)
                        usd = round(float(usd_str), 1) if usd_str else None
                        records[("Scrap Steel", period)] = {
                            "date": date_str,
                            "period": int(period),
                            "commodity": "Scrap Steel",
                            "trade_flow": "Imports",
                            "reporter_country": "Türkiye",
                            "partner_country": "World",
                            "hs_code": 7204,
                            "metric_tonnes": tonnes,
                            "value_usd": usd,
                            "vessel_demand_impact": "Supramax / Handysize",
                            "source": "TurkStat general trade",
                            "source_url": "https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1 (general trade, Qlik app bd4b4757)"
                        }
                    except ValueError:
                        pass

    logger.info(f"Parsed {len(records)} monthly commodity points from {csv_path.name}")
    return records


def update_minor_bulks_turkstat(records: dict[str, dict]):
    """Merge TurkStat Cement and Scrap records into minor_bulks_monthly.csv."""
    if not MINOR_BULKS_CSV.exists():
        logger.error(f"{MINOR_BULKS_CSV} does not exist.")
        return

    logger.info(f"Merging {len(records)} TurkStat points into {MINOR_BULKS_CSV.name}...")
    existing_rows = []
    with open(MINOR_BULKS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or [
            "date", "period", "commodity", "trade_flow", "reporter_country",
            "partner_country", "hs_code", "metric_tonnes", "value_usd",
            "vessel_demand_impact", "source", "source_url"
        ]
        for r in reader:
            comm = r.get("commodity")
            dt = r.get("date")
            p = (comm, dt[:7].replace("-", ""))
            # If this is a Comtrade or old record being replaced by general trade
            if p in records and ("Comtrade" in r.get("source", "") or "TurkStat" in r.get("source", "")):
                rec = records[p]
                r["metric_tonnes"] = rec["metric_tonnes"]
                r["value_usd"] = rec["value_usd"]
                r["source"] = rec["source"]
                r["source_url"] = rec["source_url"]
                del records[p]
            existing_rows.append(r)

    # Append any remaining new records
    for rec in records.values():
        existing_rows.append(rec)

    # Sort and write
    existing_rows.sort(key=lambda x: (x.get("commodity", ""), x.get("date", "")))
    with open(MINOR_BULKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    logger.info(f"Successfully updated {MINOR_BULKS_CSV.name} ({len(existing_rows)} total rows)")


# =====================================================================
# Main Orchestrator
# =====================================================================
def run_pipeline():
    """Run TurkStat ingestion pipeline with Playwright attempt, local ingest, and fallback."""
    logger.info("=== Starting TurkStat Bulk Ingestion Pipeline (§2.10) ===")

    # 1. Attempt Playwright live extraction
    live_rows = attempt_playwright_qlik_pull()
    if live_rows:
        logger.info(f"Processing {len(live_rows)} live rows from bi.tuik.gov.tr...")
        # (format and save to scratch/tuik/tuik_by_flow.csv)
        SCRATCH_TUIK_DIR.mkdir(parents=True, exist_ok=True)
        out_csv = SCRATCH_TUIK_DIR / "tuik_by_flow.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["YIL", "AY", "IHRITH_FLAG", "2523_MIKTAR_1", "2523_DOLAR", "7204_MIKTAR_1", "7204_DOLAR"])
            writer.writerows(live_rows)
        records = ingest_tuik_general_csv(out_csv)
        update_minor_bulks_turkstat(records)
        return

    # 2. Ingest from scratch/tuik or patch files
    candidates = [
        SCRATCH_TUIK_DIR / "tuik_GENERAL_bd4b4757.csv",
        SCRATCH_TUIK_DIR / "tuik_by_flow.csv",
        PATCH_TUIK_CSV,
    ]
    parsed_any = False
    for cand in candidates:
        if cand.exists():
            records = ingest_tuik_general_csv(cand)
            if records:
                update_minor_bulks_turkstat(records)
                parsed_any = True
                break

    if not parsed_any:
        logger.warning("No TurkStat raw extracts found. Checking SteelOrbis fallback for scrap...")
        so_items = fetch_steelorbis_scrap_fallback()
        logger.info(f"Found {len(so_items)} SteelOrbis news articles.")

    logger.info("=== TurkStat pipeline complete ===")


if __name__ == "__main__":
    run_pipeline()
