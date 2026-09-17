#!/usr/bin/env python3
"""
India monthly imports by HS code from Dept of Commerce TradeStat portal (DGCI&S data).
Replaces UN Comtrade for the 'Urea / Fertiliser (India, HS 3102)' series: Comtrade has
value-only months; TradeStat has quantity (kg) and USD value for all of them.

Endpoint: https://tradestat.commerce.gov.in/meidb/commoditywise_import
Form quirks: in 'specific' mode the HS code field is `comval` and the commodity-level
select must NOT be sent (it is disabled). Quantity table has a UNIT column, the USD table
does not, so the current-month column is index 5 (qty) vs 4 (USD mn).
Latest month is flagged (F) = provisional.
"""
import html
import http.cookiejar
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "commodities" / "minor_bulks_monthly.csv"
URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"


def _opener():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")]
    return op


def query(op, month, year, report_val, hs):
    try:
        page = op.open(URL, timeout=60).read().decode()
        token = re.search(r'name="_token" value="([^"]+)"', page)[1]
        data = dict(_token=token, imddMonth=str(month), imddYear=str(year), comlev="specific",
                    comval=hs, imddReportVal=str(report_val), imddReportYear="2")
        body = op.open(urllib.request.Request(URL, data=urllib.parse.urlencode(data).encode(),
                                              headers={"Referer": URL}), timeout=120).read().decode()
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) > 5 and cells[1] == hs:
                return cells
    except Exception as e:
        logging.warning("TradeStat query failed for %04d-%02d (report_val=%s): %s", year, month, report_val, e)
    return None


def fetch_month_row(year, month, hs="3102"):
    op = _opener()
    q = query(op, month, year, 2, hs)
    time.sleep(1)
    v = query(op, month, year, 1, hs)
    if not q or not v:
        return None
    try:
        kg = float(q[5].replace(",", ""))
        usd = float(v[4].replace(",", "")) * 1e6
        # Zero means month is not yet published -> write nothing
        if kg <= 0 or usd <= 0:
            logging.info("TradeStat %04d-%02d returned zero (kg=%.1f, usd=%.1f) -> not yet published; writing nothing.", year, month, kg, usd)
            return None
        return dict(date=f"{year}-{month:02d}-01",
                    period=f"{year}{month:02d}",
                    commodity="Urea / Fertiliser",
                    trade_flow="Imports",
                    reporter_country="India",
                    partner_country="World",
                    hs_code=int(hs),
                    metric_tonnes=round(kg / 1000, 2),
                    value_usd=round(usd),
                    vessel_demand_impact="Handysize / Supramax",
                    source="Ministry of Commerce & Industry TradeStat (DGCI&S)",
                    source_url=URL)
    except Exception as e:
        logging.error("TradeStat cell parse error for %04d-%02d: %s", year, month, e)
        return None


def upsert_to_minor_bulks(rows: list[dict]):
    if not rows or not OUT.exists():
        return
    df_old = pd.read_csv(OUT)
    df_new = pd.DataFrame(rows)
    key = ["date", "commodity"]
    merged = pd.concat([df_old[~df_old.set_index(key).index.isin(df_new.set_index(key).index)], df_new])
    merged = merged.sort_values(["commodity", "date"]).reset_index(drop=True)
    merged.to_csv(OUT, index=False, lineterminator="\n")
    logging.info("Upserted %d TradeStat rows into %s (total: %d rows)", len(df_new), OUT, len(merged))


def main():
    if len(sys.argv) >= 3:
        y, m = int(sys.argv[1]), int(sys.argv[2])
        targets = [(y, m)]
    else:
        now = datetime.now(timezone.utc)
        targets = []
        for offset in range(1, 4):
            m = now.month - offset
            y = now.year
            if m <= 0:
                m += 12
                y -= 1
            targets.append((y, m))

    results = []
    for y, m in targets:
        logging.info("Checking India TradeStat for %04d-%02d...", y, m)
        row = fetch_month_row(y, m)
        if row:
            logging.info("  Found: %.1f tonnes, $%.0f", row["metric_tonnes"], row["value_usd"])
            results.append(row)
        else:
            logging.info("  No data or query error for %04d-%02d", y, m)
        time.sleep(2)

    if results:
        upsert_to_minor_bulks(results)


if __name__ == "__main__":
    main()
