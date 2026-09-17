"""
TurkStat Bulk Ingestion Pipeline (§2.10, §4d)
============================================
Ingests Türkiye bulk commodity trade flows:
  - HS 2523: Cement / Clinker Exports (Flow = 1)
  - HS 7204: Scrap Steel Imports (Flow = 2)

Architecture:
  1. Primary Ingester: TurkStat General Trade App (bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42).
     Attempts live connection via Playwright to bi.tuik.gov.tr.
     Fails loudly on HTTP 503 (cloud IP block).
  2. Local Extract Ingestion Policy:
     Strict freshness guard: only ingests local scratch files (scratch/tuik/...)
     if they contain months strictly newer than the latest month already stored.
     Never re-ingests old scratch files.
  3. Secondary Fallback for Scrap:
     SteelOrbis reports quoting TUIK via Google News RSS.
     Derives monthly tonnage = YTD - previous months YTD. Provenance: SteelOrbis/TUIK.
  4. Policy for Cement:
     If TurkStat is blocked and no newer extract exists, the month is intentionally
     left empty to trigger freshness alerts. (Documented in docs/gap_fill/TURKSTAT_SELF_HOSTED.md).
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
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("turkstat_bulk")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = BASE_DIR / "data" / "commodities"
SCRATCH_TUIK_DIR = BASE_DIR / "scratch" / "tuik"
MINOR_BULKS_CSV = COMMODITIES_DIR / "minor_bulks_monthly.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MONTH_NAME_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}


def get_latest_stored_periods() -> dict[str, str]:
    """Get the latest stored period (YYYY-MM) for Cement and Scrap from minor_bulks_monthly.csv."""
    if not MINOR_BULKS_CSV.exists():
        return {"Cement / Clinker": "1900-01", "Scrap Steel": "1900-01"}
    
    df = pd.read_csv(MINOR_BULKS_CSV)
    res = {}
    for comm in ["Cement / Clinker", "Scrap Steel"]:
        sub = df[df["commodity"] == comm]
        if not sub.empty:
            res[comm] = str(sub["date"].max())[:7]
        else:
            res[comm] = "1900-01"
    return res


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
                logger.warning(f"[TurkStat Playwright] bi.tuik.gov.tr returned HTTP {response.status} (Cloud runner IP blocked). See docs/gap_fill/TURKSTAT_SELF_HOSTED.md")
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
# Channel 2: Scratch Ingestion (Fresh Data Only)
# =====================================================================
def inspect_and_ingest_scratch_csv(csv_path: Path, latest_stored: dict[str, str]) -> dict[tuple[str, str], dict]:
    """
    Parse candidate TurkStat CSV, but strictly ONLY return rows that are
    NEWER than latest_stored[commodity].
    Never re-ingests old scratch records.
    """
    if not csv_path.exists():
        return {}

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

            period_str = f"{y:04d}-{m:02d}"
            date_str = f"{period_str}-01"
            period_int = int(f"{y:04d}{m:02d}")

            # Flow 1: Exports -> Cement / Clinker (HS 2523)
            if fl == 1:
                # Check freshness constraint
                if period_str <= latest_stored.get("Cement / Clinker", "1900-01"):
                    continue
                kg_str = row.get("2523_MIKTAR_1")
                usd_str = row.get("2523_DOLAR")
                if kg_str:
                    try:
                        tonnes = round(float(kg_str) / 1000.0, 2)
                        usd = round(float(usd_str), 1) if usd_str else None
                        records[("Cement / Clinker", period_str)] = {
                            "date": date_str,
                            "period": period_int,
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
                # Check freshness constraint
                if period_str <= latest_stored.get("Scrap Steel", "1900-01"):
                    continue
                kg_str = row.get("7204_MIKTAR_1")
                usd_str = row.get("7204_DOLAR")
                if kg_str:
                    try:
                        tonnes = round(float(kg_str) / 1000.0, 2)
                        usd = round(float(usd_str), 1) if usd_str else None
                        records[("Scrap Steel", period_str)] = {
                            "date": date_str,
                            "period": period_int,
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

    if records:
        logger.info(f"Parsed {len(records)} NEW monthly points from {csv_path.name} (strictly newer than stored data)")
    else:
        logger.info(f"Skipping scratch file {csv_path.name}: contains no periods newer than stored data ({latest_stored}). Old files are not re-ingested.")
    return records


# =====================================================================
# Channel 3: SteelOrbis Scrap Steel Fallback (§4d)
# =====================================================================
def fetch_steelorbis_scrap_fallback(latest_stored_month: str) -> dict[tuple[str, str], dict]:
    """
    Search Google News RSS for SteelOrbis reports quoting TUIK scrap imports.
    Follows article links via Playwright and parses monthly or cumulative YTD figures.
    Derives month = YTD - prev YTD when only cumulative data is available.
    Provenance: SteelOrbis/TUIK
    """
    query = "Turkey scrap imports TUIK steelorbis"
    encoded_q = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    logger.info(f"[SteelOrbis Fallback] Querying Google News RSS: {query}")

    req = urllib.request.Request(rss_url, headers=HEADERS)
    rss_items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.fromstring(resp.read())
            for item in tree.findall(".//item")[:8]:
                title = item.find("title").text or ""
                link = item.find("link").text or ""
                pub_date = item.find("pubDate").text or ""
                if "scrap" in title.lower() and "steelorbis" in title.lower():
                    rss_items.append({"title": title, "link": link, "pubDate": pub_date})
    except Exception as e:
        logger.warning(f"[SteelOrbis Fallback] Error querying RSS: {e}")
        return {}

    logger.info(f"[SteelOrbis Fallback] Found {len(rss_items)} candidate SteelOrbis scrap articles.")
    if not rss_items:
        return {}

    # Read existing scrap history to calculate YTD deltas if needed
    existing_scrap = {}
    if MINOR_BULKS_CSV.exists():
        df = pd.read_csv(MINOR_BULKS_CSV)
        sub = df[df["commodity"] == "Scrap Steel"]
        for _, r in sub.iterrows():
            d = str(r["date"])[:7]
            existing_scrap[d] = {
                "tonnes": float(r["metric_tonnes"]) if pd.notna(r["metric_tonnes"]) else 0.0,
                "usd": float(r["value_usd"]) if pd.notna(r["value_usd"]) else 0.0
            }

    parsed_records = {}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[SteelOrbis Fallback] Playwright not installed.")
        return {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for it in rss_items:
            try:
                page = browser.new_page()
                page.goto(it["link"], timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                body = page.locator("body").inner_text()
                page_url = page.url
                page.close()

                # Search body for monthly volume or YTD
                # 1. Direct monthly sentence:
                # "In May this year, Turkey's scrap import volume decreased ... to 1.49 million mt ... The value of these imports totaled $593.95 million"
                m_direct = re.search(
                    r"In\s+([A-Za-z]+)\s+(?:this\s+year|(\d{4})),\s*Turkey(?:'s|’s)\s+scrap\s+import\s+volume.*?to\s+([\d,.]+)\s*(million|mil|thousand|kt|mt|tonnes)?",
                    body, re.IGNORECASE
                )
                m_direct_usd = re.search(
                    r"value\s+of\s+these\s+imports\s+totaled\s+\$([\d,.]+)\s*(billion|million|mil)?",
                    body, re.IGNORECASE
                )

                # 2. Cumulative YTD sentence:
                # "In the January-May period, Turkey's scrap imports amounted to 8.08 million mt ... value ... increased ... to $3.11 billion"
                m_ytd = re.search(
                    r"In\s+the\s+January-([A-Za-z]+)\s+period(?:,\s*|\s+of\s+(\d{4}))?.*?Turkey(?:'s|’s)\s+scrap\s+imports\s+amounted\s+to\s+([\d,.]+)\s*(million|mil|thousand|kt|mt|tonnes)?",
                    body, re.IGNORECASE
                )
                m_ytd_usd = re.search(
                    r"In\s+the\s+January-[A-Za-z]+.*?value\s+of\s+these\s+imports.*?to\s+\$([\d,.]+)\s*(billion|million|mil)?",
                    body, re.IGNORECASE
                )

                target_year = datetime.now().year
                if m_direct:
                    mon_str = m_direct.group(1).lower()
                    m_num = MONTH_NAME_MAP.get(mon_str)
                    if m_direct.group(2):
                        target_year = int(m_direct.group(2))
                    if m_num:
                        period_str = f"{target_year:04d}-{m_num:02d}"
                        if period_str > latest_stored_month:
                            val = float(m_direct.group(3).replace(",", ""))
                            unit = (m_direct.group(4) or "").lower()
                            tonnes = val * 1e6 if ("million" in unit or "mil" in unit or val < 50.0) else val
                            
                            usd = None
                            if m_direct_usd:
                                uval = float(m_direct_usd.group(1).replace(",", ""))
                                uunit = (m_direct_usd.group(2) or "").lower()
                                usd = uval * 1e9 if "billion" in uunit else (uval * 1e6 if ("million" in uunit or "mil" in uunit) else uval)

                            logger.info(f"[SteelOrbis Fallback] Parsed direct monthly scrap for {period_str}: {tonnes:,.0f} t, ${usd:,.0f}")
                            parsed_records[("Scrap Steel", period_str)] = {
                                "date": f"{period_str}-01",
                                "period": int(period_str.replace("-", "")),
                                "commodity": "Scrap Steel",
                                "trade_flow": "Imports",
                                "reporter_country": "Türkiye",
                                "partner_country": "World",
                                "hs_code": 7204,
                                "metric_tonnes": round(tonnes, 2),
                                "value_usd": round(usd, 1) if usd else None,
                                "vessel_demand_impact": "Supramax / Handysize",
                                "source": "SteelOrbis/TUIK",
                                "source_url": page_url
                            }
                            continue

                # If no direct monthly, try YTD delta
                if m_ytd:
                    end_mon_str = m_ytd.group(1).lower()
                    end_m_num = MONTH_NAME_MAP.get(end_mon_str)
                    if m_ytd.group(2):
                        target_year = int(m_ytd.group(2))
                    if end_m_num:
                        period_str = f"{target_year:04d}-{end_m_num:02d}"
                        if period_str > latest_stored_month:
                            val = float(m_ytd.group(3).replace(",", ""))
                            unit = (m_ytd.group(4) or "").lower()
                            ytd_tonnes = val * 1e6 if ("million" in unit or "mil" in unit or val < 50.0) else val

                            ytd_usd = None
                            if m_ytd_usd:
                                uval = float(m_ytd_usd.group(1).replace(",", ""))
                                uunit = (m_ytd_usd.group(2) or "").lower()
                                ytd_usd = uval * 1e9 if "billion" in uunit else (uval * 1e6 if ("million" in uunit or "mil" in uunit) else uval)

                            # Derive month by subtracting months 1 to (end_m_num - 1)
                            prev_tonnes = sum(
                                existing_scrap.get(f"{target_year:04d}-{m:02d}", {}).get("tonnes", 0.0)
                                for m in range(1, end_m_num)
                            )
                            prev_usd = sum(
                                existing_scrap.get(f"{target_year:04d}-{m:02d}", {}).get("usd", 0.0)
                                for m in range(1, end_m_num)
                            )

                            month_tonnes = ytd_tonnes - prev_tonnes
                            month_usd = (ytd_usd - prev_usd) if (ytd_usd and prev_usd) else None

                            if month_tonnes > 100_000:  # Sensible monthly threshold
                                logger.info(f"[SteelOrbis Fallback] Derived monthly scrap for {period_str} from YTD delta: {month_tonnes:,.0f} t (YTD {ytd_tonnes:,.0f} - prev {prev_tonnes:,.0f})")
                                parsed_records[("Scrap Steel", period_str)] = {
                                    "date": f"{period_str}-01",
                                    "period": int(period_str.replace("-", "")),
                                    "commodity": "Scrap Steel",
                                    "trade_flow": "Imports",
                                    "reporter_country": "Türkiye",
                                    "partner_country": "World",
                                    "hs_code": 7204,
                                    "metric_tonnes": round(month_tonnes, 2),
                                    "value_usd": round(month_usd, 1) if month_usd else None,
                                    "vessel_demand_impact": "Supramax / Handysize",
                                    "source": "SteelOrbis/TUIK",
                                    "source_url": page_url
                                }
            except Exception as e:
                logger.warning(f"[SteelOrbis Fallback] Error processing article: {e}")

        browser.close()

    return parsed_records


# =====================================================================
# Merging into CSV
# =====================================================================
def update_minor_bulks_turkstat(records: dict[tuple[str, str], dict]):
    """Merge new TurkStat Cement and Scrap records into minor_bulks_monthly.csv."""
    if not records:
        return

    if not MINOR_BULKS_CSV.exists():
        logger.error(f"{MINOR_BULKS_CSV} does not exist.")
        return

    logger.info(f"Merging {len(records)} new TurkStat records into {MINOR_BULKS_CSV.name}...")
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
            dt = r.get("date", "")[:7]
            key = (comm, dt)
            if key in records:
                rec = records[key]
                r["metric_tonnes"] = rec["metric_tonnes"]
                r["value_usd"] = rec["value_usd"]
                r["source"] = rec["source"]
                r["source_url"] = rec["source_url"]
                del records[key]
            existing_rows.append(r)

    # Append any remaining new records
    for rec in records.values():
        existing_rows.append(rec)

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
    """Run TurkStat ingestion pipeline with Playwright attempt, scratch fresh check, and fallback."""
    logger.info("=== Starting TurkStat Bulk Ingestion Pipeline (§2.10, §4d) ===")

    latest_stored = get_latest_stored_periods()
    logger.info(f"Current latest stored periods in minor_bulks_monthly.csv: {latest_stored}")

    # 1. Attempt Playwright live extraction
    live_rows = attempt_playwright_qlik_pull()
    if live_rows:
        logger.info(f"Processing {len(live_rows)} live rows from bi.tuik.gov.tr...")
        SCRATCH_TUIK_DIR.mkdir(parents=True, exist_ok=True)
        out_csv = SCRATCH_TUIK_DIR / "tuik_by_flow.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["YIL", "AY", "IHRITH_FLAG", "2523_MIKTAR_1", "2523_DOLAR", "7204_MIKTAR_1", "7204_DOLAR"])
            writer.writerows(live_rows)
        records = inspect_and_ingest_scratch_csv(out_csv, latest_stored)
        if records:
            update_minor_bulks_turkstat(records)
        return

    # 2. If live pull failed, never re-ingest old scratch files
    logger.info("[TurkStat Policy] Live pull unavailable; old scratch files are never re-ingested.")
    logger.info("[Cement Policy] TurkStat Qlik connection unavailable. Cement month intentionally left empty to alert.")
        
    # 3. SteelOrbis Scrap Fallback
    logger.info("[Scrap Fallback] Checking SteelOrbis Google News RSS fallback for scrap steel...")
    so_records = fetch_steelorbis_scrap_fallback(latest_stored.get("Scrap Steel", "1900-01"))
    if so_records:
        update_minor_bulks_turkstat(so_records)
    else:
        logger.info("[Scrap Fallback] No newer published scrap reports found via SteelOrbis.")

    logger.info("=== TurkStat pipeline complete ===")


if __name__ == "__main__":
    run_pipeline()
