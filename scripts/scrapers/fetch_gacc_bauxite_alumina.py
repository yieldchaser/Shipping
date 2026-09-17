"""
GACC / China Customs Bauxite & Alumina Ingestion Pipeline (§2.6)
==============================================================
Implements the 4-channel zero-touch architecture defined in AGENT_HANDOFF.md §2.6:
  - Channel A: chinadata.live 8-digit USD totals and partner breakdown (HS 26060000, HS 28182000).
               Stores monthly Guinea USD to data/commodities/china_customs_guinea_bauxite_partner_usd.csv.
  - Channel B: GACC Table (14) via Playwright headless Chromium for official total bauxite tonnes.
  - Channel C: SMM (Shanghai Metals Market) reports via Google News RSS for partner tonnes.
               Handles month names without year (infers from article pubDate).
               Strictly rejects cumulative / YTD sentences.
  - Channel D: Calibrated value-share fallback for Guinea bauxite tonnes:
               guinea_t = china_total_t * (guinea_usd / china_total_usd) * 0.982
               labeled method = derived_value_share. (Never applied to alumina).

Sanity Check & Precedence:
  1. GACC official export / UN Comtrade (provenance = GACC)
  2. SMM quote (provenance = SMM/GACC), sanity-checked against Channel D:
     if SMM diverges by >10% from derived Channel D, log warning and prefer derived.
  3. Derived value share (provenance = derived_value_share, bauxite only).
  4. Alumina: null tonnes if SMM has no quantity; never derived from USD.
"""

import sys
import os
import re
import csv
import json
import gzip
import logging
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gacc_bauxite_alumina")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = BASE_DIR / "data" / "commodities"

GUINEA_CSV = COMMODITIES_DIR / "guinea_bauxite_exports.csv"
MINOR_BULKS_CSV = COMMODITIES_DIR / "minor_bulks_monthly.csv"
PARTNER_USD_CSV = COMMODITIES_DIR / "china_customs_guinea_bauxite_partner_usd.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}


# =====================================================================
# Channel A: chinadata.live USD API
# =====================================================================
def fetch_chinadata_hs(hs_code: str, flow: str = "import", period: str = "all") -> dict:
    """Fetch trade data from chinadata.live for an 8-digit or 4-digit HS code."""
    url = f"https://chinadata.live/api/v2/trade/hs/{hs_code}?flow={flow}&period={period}"
    logger.info(f"[Channel A] Fetching chinadata.live HS {hs_code} (flow={flow}, period={period})")
    req = urllib.request.Request(url, headers={"User-Agent": "ShippingIntel/1.0 (partner-harvest)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sync_partner_usd_history(bauxite_data: dict) -> dict:
    """Ensure data/commodities/china_customs_guinea_bauxite_partner_usd.csv is up-to-date."""
    PARTNER_USD_CSV.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if PARTNER_USD_CSV.exists():
        with open(PARTNER_USD_CSV, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[r["period"]] = r

    # Seed from existing guinea_bauxite_exports.csv if partner file is empty
    if not existing and GUINEA_CSV.exists():
        logger.info("Seeding partner USD history from guinea_bauxite_exports.csv mirror rows...")
        with open(GUINEA_CSV, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("granularity") == "monthly_bilateral_mirror":
                    d = str(r.get("date", ""))[:7]
                    quote = str(r.get("source_quote", ""))
                    m_usd = re.search(r"US\$\s*([\d,]+)", quote)
                    g_usd = None
                    if m_usd:
                        g_usd = float(m_usd.group(1).replace(",", ""))
                    elif r.get("tonnes") and r.get("avg_cif_usd_t"):
                        try:
                            g_usd = float(r["tonnes"]) * float(r["avg_cif_usd_t"])
                        except ValueError:
                            pass
                    if d and g_usd:
                        existing[d] = {
                            "period": d,
                            "date": f"{d}-01",
                            "guinea_usd": g_usd,
                            "china_total_usd": "",
                            "guinea_value_share": "",
                            "source": r.get("publisher", "GACC")
                        }

    # Match with chinadata.live monthly totals
    monthly_totals = {m["month"]: m["value_usd"] for m in bauxite_data.get("monthly", [])}
    for m_str, tot in monthly_totals.items():
        if m_str in existing:
            existing[m_str]["china_total_usd"] = tot
            g_usd = existing[m_str].get("guinea_usd")
            if g_usd:
                try:
                    existing[m_str]["guinea_value_share"] = round(float(g_usd) / float(tot), 6)
                except (ValueError, ZeroDivisionError):
                    pass

    # Check latest_partners from chinadata
    latest_partners = bauxite_data.get("latest_partners", [])
    for p in latest_partners:
        if str(p.get("partner_code")) == "221" or "Guinea" in str(p.get("partner_name", "")):
            latest_m = str(p.get("latest_month", ""))
            if len(latest_m) == 6:
                m_str = f"{latest_m[:4]}-{latest_m[4:6]}"
            else:
                m_str = bauxite_data.get("monthly", [{}])[-1].get("month")

            tot_usd = monthly_totals.get(m_str, "")
            g_usd = p.get("value_usd")
            share = p.get("share")
            logger.info(f"[Channel A] Found Guinea partner USD for {m_str}: ${g_usd:,.0f} (share: {share:.2%})")
            existing[m_str] = {
                "period": m_str,
                "date": f"{m_str}-01",
                "guinea_usd": g_usd,
                "china_total_usd": tot_usd,
                "guinea_value_share": round(float(share), 6) if share else "",
                "source": "chinadata.live (partner_code 221)"
            }

    # Write sorted CSV
    sorted_periods = sorted(existing.keys())
    with open(PARTNER_USD_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["period", "date", "guinea_usd", "china_total_usd", "guinea_value_share", "source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in sorted_periods:
            writer.writerow(existing[p])

    logger.info(f"Updated {PARTNER_USD_CSV} ({len(sorted_periods)} months recorded)")
    return existing


# =====================================================================
# Channel B: GACC Table 14 via Playwright Headless Chromium
# =====================================================================
def fetch_gacc_table14_playwright(year: int, month: int) -> float | None:
    """
    Attempt to scrape official total bauxite import tonnes from GACC Table 14.
    Link text: （14）{year}年{month}月进口主要商品量值表（美元值）
    Row: 铝矿砂及其精矿 (万吨 -> tonnes = 万吨 * 10,000)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[Channel B] Playwright not installed. Skipping Table 14 scrape.")
        return None

    logger.info(f"[Channel B] Attempting Playwright navigation for GACC Table 14 ({year}-{month:02d})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            init_url = "http://www.customs.gov.cn/customs/302249/zfxxgk/2799825/302274/index.html"
            try:
                page.goto(init_url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(6000)
            except Exception as e:
                logger.warning(f"[Channel B] Initial handshake challenge timeout/error: {e}")

            target_idx_url = f"http://www.customs.gov.cn/customs/302249/zfxxgk/fdzdgknr/302274/302277/{year}/index.html"
            page.goto(target_idx_url, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            target_pattern = f"14.*{month}月进口主要商品量值表"
            links = page.query_selector_all("a")
            table_url = None
            for l in links:
                txt = (l.inner_text() or "").strip()
                if re.search(target_pattern, txt):
                    href = l.get_attribute("href")
                    if href:
                        table_url = urllib.parse.urljoin(page.url, href)
                        logger.info(f"[Channel B] Found Table 14 link: {txt} -> {table_url}")
                        break

            if not table_url:
                logger.warning(f"[Channel B] Table 14 link for {year}-{month:02d} not found on index page.")
                return None

            page.goto(table_url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            content = page.content()
            m = re.search(r"铝矿砂及其精矿\s*</td>\s*<td[^>]*>\s*万吨\s*</td>\s*<td[^>]*>\s*([\d,]+(?:\.\d+)?)", content)
            if m:
                wan_tonnes = float(m.group(1).replace(",", ""))
                total_tonnes = wan_tonnes * 10000.0
                logger.info(f"[Channel B] Successfully parsed bauxite total from Table 14: {wan_tonnes} 万吨 ({total_tonnes:,.0f} t)")
                return total_tonnes
            else:
                logger.warning("[Channel B] Row '铝矿砂及其精矿' not found in Table 14 content.")
                return None
        except Exception as e:
            logger.warning(f"[Channel B] Failed to scrape Table 14 via Playwright: {e}")
            return None
        finally:
            browser.close()


# =====================================================================
# Channel C: SMM (Shanghai Metals Market) via Google News RSS
# =====================================================================
def fetch_smm_news_rss(query: str, max_items: int = 15) -> list[dict]:
    """Search Google News RSS for SMM articles and return title, link, pubDate."""
    encoded_q = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    logger.info(f"[Channel C] Querying Google News RSS: {query}")

    req = urllib.request.Request(rss_url, headers=HEADERS)
    items = []
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            tree = ET.fromstring(resp.read())
            for item in tree.findall(".//item")[:max_items]:
                title = item.find("title").text or ""
                link = item.find("link").text or ""
                pub_date = item.find("pubDate").text or ""
                items.append({"title": title, "link": link, "pubDate": pub_date})
    except Exception as e:
        logger.warning(f"[Channel C] Error querying Google News RSS: {e}")
    return items


def fetch_article_text(url: str) -> str:
    """Fetch article body handling gzip and redirects."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            page = b.new_page()
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            text = page.locator("body").inner_text()
            b.close()
            return text
    except Exception:
        # Fallback to urllib
        req = urllib.request.Request(url, headers={**HEADERS, "Accept-Encoding": "gzip, deflate"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)
                return content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"[Channel C] Failed to fetch article {url}: {e}")
            return ""


def extract_period_from_smm(title: str, body: str, pub_date: str = "") -> str | None:
    """
    Extract YYYY-MM period from SMM article.
    Handles month names without year by inferring year from pubDate or current year.
    """
    # 1. Check title and body for Month + 4-digit year
    m = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", f"{title}\n{body}", re.IGNORECASE)
    if m:
        mon = m.group(1).lower()
        yr = int(m.group(2))
        return f"{yr:04d}-{MONTH_MAP[mon]:02d}"

    # 2. Check for month name alone, inferring year from pubDate
    m_mon = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", f"{title}\n{body[:200]}", re.IGNORECASE)
    if m_mon:
        mon = m_mon.group(1).lower()
        yr = None
        if pub_date:
            try:
                parsed_dt = email.utils.parsedate_to_datetime(pub_date)
                yr = parsed_dt.year
            except Exception:
                m_yr = re.search(r"\b(20\d\d)\b", pub_date)
                if m_yr:
                    yr = int(m_yr.group(1))
        if not yr:
            yr = datetime.now().year
        return f"{yr:04d}-{MONTH_MAP[mon]:02d}"

    return None


def parse_smm_bauxite_article(title: str, body: str, pub_date: str = "") -> dict | None:
    """
    Parse Guinea bauxite tonnes from an SMM article.
    Strictly rejects cumulative / YTD sentences and extracts pure monthly volumes.
    """
    period_str = extract_period_from_smm(title, body, pub_date)
    if not period_str:
        return None

    full_text = f"{title}\n{body}"
    sentences = [s.strip() for s in re.split(r"[.\n]+", full_text) if s.strip()]

    # Patterns for monthly Guinea bauxite
    patterns = [
        r"(?:imported|imports\s+from\s+Guinea\s+(?:reached|were|totaled)?)\s+([\d,]+(?:\.\d+)?)\s*(?:million|mil)?\s*(?:mt|tonnes|t)\s+(?:of\s+bauxite\s+)?from\s+Guinea",
        r"Guinea\s*[^.]*?([\d,]+(?:\.\d+)?)\s*(?:million|mil)\s*(?:mt|tonnes|t)",
        r"([\d,]+(?:\.\d+)?)\s*(?:million|mil)\s*(?:mt|tonnes|t)\s+(?:of\s+bauxite\s+)?from\s+Guinea",
    ]

    for s in sentences:
        # Strictly reject cumulative / YTD sentences
        if re.search(r"january[-–\s]+[a-z]+|first\s+\d+\s+months|cumulative|ytd|in the first \w+ months", s, re.IGNORECASE):
            continue

        for pat in patterns:
            m = re.search(pat, s, re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(",", "")
                val = float(val_str)
                if "million" in m.group(0).lower() or "mil" in m.group(0).lower() or val < 100.0:
                    tonnes = val * 1e6
                else:
                    tonnes = val

                return {
                    "period": period_str,
                    "date": f"{period_str}-01",
                    "tonnes": tonnes,
                    "quote": m.group(0).strip(),
                    "title": title
                }
    return None


def parse_smm_alumina_article(title: str, body: str, pub_date: str = "") -> dict | None:
    """
    Parse Alumina import tonnes from an SMM article.
    Strictly rejects cumulative / YTD sentences.
    """
    period_str = extract_period_from_smm(title, body, pub_date)
    if not period_str:
        return None

    full_text = f"{title}\n{body}"
    sentences = [s.strip() for s in re.split(r"[.\n]+", full_text) if s.strip()]

    patterns = [
        r"alumina\s+(?:net\s+)?imports\s+(?:reached|totaled|were)?\s*([\d,]+(?:\.\d+)?)\s*(?:mt|tonnes|t)",
        r"imported\s+([\d,]+(?:\.\d+)?)\s*(?:mt|tonnes|t)\s+(?:of\s+alumina)",
        r"([\d,]+(?:\.\d+)?)\s*(?:million|mil)\s*(?:mt|tonnes|t)\s+(?:of\s+alumina)",
    ]

    for s in sentences:
        if re.search(r"january[-–\s]+[a-z]+|first\s+\d+\s+months|cumulative|ytd|in the first \w+ months", s, re.IGNORECASE):
            continue

        for pat in patterns:
            m = re.search(pat, s, re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(",", "")
                val = float(val_str)
                if "million" in m.group(0).lower() or "mil" in m.group(0).lower() or val < 50.0:
                    tonnes = val * 1e6
                else:
                    tonnes = val
                return {
                    "period": period_str,
                    "date": f"{period_str}-01",
                    "metric_tonnes": tonnes,
                    "quote": m.group(0).strip(),
                    "title": title
                }
    return None


# =====================================================================
# Updating CSV Datasets
# =====================================================================
def update_guinea_bauxite_mirror(period: str, tonnes: float, method: str, publisher: str,
                                 source_url: str, quote: str, avg_cif: float | None = None) -> bool:
    """
    Insert or overwrite a mirror row in guinea_bauxite_exports.csv.
    Enforces precedence: GACC > SMM/GACC > derived_value_share.
    """
    if not GUINEA_CSV.exists():
        logger.error(f"{GUINEA_CSV} does not exist.")
        return False

    date_str = f"{period}-01"
    rows = []
    updated = False
    priority = {"GACC": 3, "SMM/GACC": 2, "derived_value_share": 1}

    with open(GUINEA_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or [
            "date", "tonnes", "vessels", "company", "source_url", "publisher",
            "source_quote", "method", "import_volume_t", "avg_cif_usd_t", "granularity"
        ]
        for r in reader:
            if r.get("date") == date_str and r.get("granularity") == "monthly_bilateral_mirror":
                curr_method = r.get("method", "")
                curr_prio = priority.get("GACC" if "GACC query" in curr_method else ("SMM/GACC" if "SMM" in curr_method else "derived_value_share"), 1)
                new_prio = priority.get(method, 1)

                if new_prio >= curr_prio:
                    logger.info(f"Updating {period} mirror row: {curr_method} ({r.get('tonnes')}) -> {method} ({tonnes:.1f})")
                    r["tonnes"] = f"{tonnes:.1f}"
                    r["import_volume_t"] = f"{tonnes:.1f}"
                    r["method"] = method
                    r["publisher"] = publisher
                    r["source_url"] = source_url
                    r["source_quote"] = quote
                    if avg_cif:
                        r["avg_cif_usd_t"] = f"{avg_cif:.2f}"
                    updated = True
                else:
                    logger.info(f"Retaining higher precedence {curr_method} over candidate {method} for {period}")
            rows.append(r)

    if not updated:
        exists = any(r.get("date") == date_str and r.get("granularity") == "monthly_bilateral_mirror" for r in rows)
        if not exists:
            logger.info(f"Appending new mirror row for {period}: {tonnes:,.0f} t via {method}")
            rows.append({
                "date": date_str,
                "tonnes": f"{tonnes:.1f}",
                "vessels": "",
                "company": "Bilateral Mirror (China Imports from Guinea)",
                "source_url": source_url,
                "publisher": publisher,
                "source_quote": quote,
                "method": method,
                "import_volume_t": f"{tonnes:.1f}",
                "avg_cif_usd_t": f"{avg_cif:.2f}" if avg_cif else "",
                "granularity": "monthly_bilateral_mirror"
            })
            updated = True

    rows.sort(key=lambda x: x.get("date", ""))
    with open(GUINEA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return updated


def update_minor_bulks_alumina(period: str, metric_tonnes: float | None, value_usd: float | None,
                               source_str: str, source_url: str) -> bool:
    """
    Insert or update China Alumina row in minor_bulks_monthly.csv.
    Tonnes can be None if SMM did not report it; value_usd is exact from chinadata.
    NEVER derives tonnes from USD value.
    """
    if not MINOR_BULKS_CSV.exists():
        logger.error(f"{MINOR_BULKS_CSV} does not exist.")
        return False

    date_str = f"{period}-01"
    period_int = int(period.replace("-", ""))
    rows = []
    found = False

    with open(MINOR_BULKS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or [
            "date", "period", "commodity", "trade_flow", "reporter_country",
            "partner_country", "hs_code", "metric_tonnes", "value_usd",
            "vessel_demand_impact", "source", "source_url"
        ]
        for r in reader:
            if (r.get("commodity") == "Alumina" and
                r.get("reporter_country") == "China" and
                r.get("date") == date_str):
                found = True
                if metric_tonnes is not None:
                    r["metric_tonnes"] = f"{metric_tonnes:.2f}"
                if value_usd is not None:
                    r["value_usd"] = f"{value_usd:.1f}"
                r["source"] = source_str
                r["source_url"] = source_url
            rows.append(r)

    if not found:
        logger.info(f"Appending new Alumina row for {period}: tonnes={metric_tonnes}, value_usd={value_usd}")
        rows.append({
            "date": date_str,
            "period": period_int,
            "commodity": "Alumina",
            "trade_flow": "Imports",
            "reporter_country": "China",
            "partner_country": "World",
            "hs_code": "2818",
            "metric_tonnes": f"{metric_tonnes:.2f}" if metric_tonnes is not None else "",
            "value_usd": f"{value_usd:.1f}" if value_usd is not None else "",
            "vessel_demand_impact": "Handymax / Supramax",
            "source": source_str,
            "source_url": source_url
        })

    rows.sort(key=lambda x: (x.get("commodity", ""), x.get("date", "")))
    with open(MINOR_BULKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


# =====================================================================
# Main Orchestrator
# =====================================================================
def run_pipeline(target_period: str | None = None):
    """
    Run bauxite and alumina ingestion pipeline across all channels.
    Re-evaluates the last 3 periods to capture late publications and revisions.
    """
    logger.info("=== Starting GACC Bauxite & Alumina Ingestion Pipeline (§2.6) ===")

    # Channel A: Fetch chinadata.live 8-digit USD
    bauxite_data = fetch_chinadata_hs("26060000", flow="import", period="all")
    alumina_data = fetch_chinadata_hs("28182000", flow="import", period="all")

    # Sync partner USD table
    partner_history = sync_partner_usd_history(bauxite_data)

    all_bauxite_months = [m["month"] for m in bauxite_data.get("monthly", []) if "month" in m]
    all_alumina_months = [m["month"] for m in alumina_data.get("monthly", []) if "month" in m]

    if target_period:
        eval_bauxite_months = [target_period]
        eval_alumina_months = [target_period]
    else:
        # Re-evaluate last 3 months
        eval_bauxite_months = all_bauxite_months[-3:] if len(all_bauxite_months) >= 3 else all_bauxite_months
        eval_alumina_months = all_alumina_months[-3:] if len(all_alumina_months) >= 3 else all_alumina_months

    logger.info(f"Evaluating bauxite months: {eval_bauxite_months}")
    logger.info(f"Evaluating alumina months: {eval_alumina_months}")

    # Process Alumina for evaluation months
    alumina_totals = {m["month"]: m["value_usd"] for m in alumina_data.get("monthly", [])}
    for m_str in eval_alumina_months:
        val_usd = alumina_totals.get(m_str)
        if val_usd:
            logger.info(f"Processing Alumina {m_str}: chinadata.live USD = ${val_usd:,.0f}")
            smm_alumina = None
            rss_items = fetch_smm_news_rss(f"China alumina imports {m_str[:4]} site:news.metal.com")
            for it in rss_items:
                body = fetch_article_text(it["link"])
                parsed = parse_smm_alumina_article(it["title"], body, it.get("pubDate", ""))
                if parsed and parsed["period"] == m_str:
                    smm_alumina = parsed
                    smm_alumina["link"] = it["link"]
                    break

            tonnes = smm_alumina["metric_tonnes"] if smm_alumina else None
            src_str = "China GACC via chinadata.live (HS 28182000)" + (f"; tonnes via SMM ({smm_alumina['title'][:50]}...)" if smm_alumina else "")
            src_url = smm_alumina["link"] if smm_alumina else "https://chinadata.live/api/v2/trade/hs/28182000"
            update_minor_bulks_alumina(m_str, tonnes, val_usd, src_str, src_url)

    # Process Guinea Bauxite for evaluation months
    for m_str in eval_bauxite_months:
        dt = datetime.strptime(f"{m_str}-01", "%Y-%m-%d")
        partner_info = partner_history.get(m_str, {})
        guinea_usd = partner_info.get("guinea_usd")
        china_tot_usd = partner_info.get("china_total_usd")

        # 1. Try SMM Quote (Channel C)
        smm_bauxite = None
        rss_items = fetch_smm_news_rss(f"China bauxite imports Guinea {m_str[:4]} site:news.metal.com")
        for it in rss_items:
            body = fetch_article_text(it["link"])
            parsed = parse_smm_bauxite_article(it["title"], body, it.get("pubDate", ""))
            if parsed and parsed["period"] == m_str:
                smm_bauxite = parsed
                smm_bauxite["link"] = it["link"]
                break

        # 2. Try Table 14 via Playwright (Channel B) + Calibrated Value-Share (Channel D)
        derived_tonnes = None
        china_tot_tonnes = fetch_gacc_table14_playwright(dt.year, dt.month)
        if china_tot_tonnes and guinea_usd and china_tot_usd:
            derived_tonnes = china_tot_tonnes * (float(guinea_usd) / float(china_tot_usd)) * 0.982
            logger.info(f"[Channel D] Calibrated derived Guinea bauxite tonnes for {m_str}: {derived_tonnes:,.0f} t (factor 0.982)")

        # 3. Sanity check SMM vs Channel D (if >10% diff, log and prefer derived)
        if smm_bauxite and derived_tonnes:
            diff_pct = abs(smm_bauxite["tonnes"] - derived_tonnes) / derived_tonnes
            if diff_pct > 0.10:
                logger.warning(
                    f"[Sanity Check] SMM tonnes ({smm_bauxite['tonnes']:,.0f}) diverges by {diff_pct:.1%} (>10%) "
                    f"from derived Channel D ({derived_tonnes:,.0f}). Preferring derived Channel D."
                )
                cif = float(guinea_usd) / derived_tonnes if guinea_usd else None
                update_guinea_bauxite_mirror(
                    period=m_str,
                    tonnes=derived_tonnes,
                    method="derived_value_share",
                    publisher="chinadata.live + GACC Table 14 (derived)",
                    source_url="http://www.customs.gov.cn",
                    quote=f"Derived after SMM divergence: {china_tot_tonnes:,.0f} total tonnes * ({guinea_usd}/{china_tot_usd}) * 0.982",
                    avg_cif=cif
                )
                continue
            else:
                logger.info(f"[Sanity Check] SMM tonnes and Channel D agree within {diff_pct:.1%}.")

        if smm_bauxite:
            logger.info(f"[Channel C] Found SMM Guinea bauxite tonnes for {m_str}: {smm_bauxite['tonnes']:,.0f} t")
            cif = (float(guinea_usd) / smm_bauxite["tonnes"]) if guinea_usd else None
            update_guinea_bauxite_mirror(
                period=m_str,
                tonnes=smm_bauxite["tonnes"],
                method="SMM/GACC",
                publisher="Shanghai Metals Market (SMM) / GACC",
                source_url=smm_bauxite.get("link", "https://news.metal.com"),
                quote=f"SMM quote: {smm_bauxite['quote']}",
                avg_cif=cif
            )
            continue

        if derived_tonnes:
            cif = float(guinea_usd) / derived_tonnes if guinea_usd else None
            update_guinea_bauxite_mirror(
                period=m_str,
                tonnes=derived_tonnes,
                method="derived_value_share",
                publisher="chinadata.live + GACC Table 14 (derived)",
                source_url="http://www.customs.gov.cn",
                quote=f"Derived: {china_tot_tonnes:,.0f} total tonnes * ({guinea_usd}/{china_tot_usd}) * 0.982",
                avg_cif=cif
            )
            continue

        logger.info(f"No new volume data for Guinea bauxite {m_str}; retained existing data.")

    logger.info("=== GACC Pipeline run complete ===")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(target)
