#!/usr/bin/env python3
"""
Philippines nickel ore exports (HS 2604) from PSA OpenSTAT PXWeb API – no API key needed.
Replaces UN Comtrade for this series (Comtrade stops Sep-2025 and has value-only months).
Validated 2026-09-17: identical to repo rows Jul/Aug/Nov/Dec-25, Jan–May-26.
Quantity tables are kg; FOB tables are USD. Sum all PSCC codes starting 2604 across countries.
Table IDs per year: QPE=quantity, FOB=value (…XQD5 = 2026, …XQD4 = 2025, …XQD1 = 2022).
"""
import io
import json
import logging
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "commodities" / "minor_bulks_monthly.csv"

B = "https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/"
TABLES = {  # year: (quantity table, fob table)
    2022: ("2L/IMT/QPE/0052L4DXQD1.px", "2L/IMT/FOB/0052L4DXVD1.px"),
    2023: ("2L/IMT/QPE/0042L4DXQD2.px", "2L/IMT/FOB/0042L4DXVD2.px"),
    2024: ("2L/IMT/QPE/0032L4DXQD3.px", "2L/IMT/FOB/0032L4DXVD3.px"),
    2025: ("2L/IMT/QPE/0022L4DXQD4.px", "2L/IMT/FOB/0022L4DXVD4.px"),
    2026: ("2L/IMT/QPE/0012L4DXQD5.px", "2L/IMT/FOB/0012L4DXVD5.px"),
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def post(table, body):
    req = urllib.request.Request(B + table, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "curl/8.5.0"})
    return urllib.request.urlopen(req, timeout=240).read().decode("latin1")


def codes(table, prefix):
    body = {
        "query": [
            {"code": "Commodity Code", "selection": {"filter": "all", "values": ["*"]}},
            {"code": "Country", "selection": {"filter": "item", "values": ["164"]}},
            {"code": "Period", "selection": {"filter": "item", "values": ["0"]}},
        ],
        "response": {"format": "json-stat2"},
    }
    lab = json.loads(post(table, body))["dimension"]["Commodity Code"]["category"]["label"]
    return [k for k, v in lab.items() if v.startswith(prefix)]


def monthly(table, prefix="2604"):
    body = {
        "query": [{"code": "Commodity Code", "selection": {"filter": "item", "values": codes(table, prefix)}}],
        "response": {"format": "csv"},
    }
    d = pd.read_csv(io.StringIO(post(table, body)), na_values=["..", ".", "-"])
    cols = [c for c in d.columns if c[:4].isdigit()]
    return d[cols].sum(min_count=1)


def fetch_psa_data(years=(2025, 2026)):
    rows = []
    for y in years:
        if y not in TABLES:
            continue
        qt, vt = TABLES[y]
        logging.info("Querying PSA OpenSTAT for CY%d (%s)...", y, qt)
        try:
            q, v = monthly(qt), monthly(vt)
            for col in q.index:
                mname = col.split(" ", 1)[1].rstrip("P")
                if mname not in MONTHS:
                    continue
                m = MONTHS.index(mname) + 1
                if pd.isna(q[col]) or q[col] == 0:
                    continue
                rows.append(dict(
                    date=f"{y}-{m:02d}-01",
                    period=f"{y}{m:02d}",
                    commodity="Nickel Ore",
                    trade_flow="Exports",
                    reporter_country="Philippines",
                    partner_country="World",
                    hs_code=2604,
                    metric_tonnes=round(q[col] / 1000, 2),
                    value_usd=float(v.get(col, 0.0)),
                    vessel_demand_impact="Supramax",
                    source="Philippine Statistics Authority OpenSTAT" + (" (preliminary)" if col.endswith("P") else ""),
                    source_url=B + qt,
                ))
        except Exception as e:
            logging.error("Failed fetching CY%d from PSA OpenSTAT: %s", y, e)
        time.sleep(2)
    return pd.DataFrame(rows)


def upsert_to_minor_bulks(df_new: pd.DataFrame):
    if df_new.empty or not OUT.exists():
        return
    df_old = pd.read_csv(OUT)
    key = ["date", "commodity"]
    merged = pd.concat([df_old[~df_old.set_index(key).index.isin(df_new.set_index(key).index)], df_new])
    merged = merged.sort_values(["commodity", "date"]).reset_index(drop=True)
    merged.to_csv(OUT, index=False, lineterminator="\n")
    logging.info("Upserted %d PSA Nickel rows into %s (total: %d rows)", len(df_new), OUT, len(merged))


def main():
    years = [int(a) for a in sys.argv[1:] if a.isdigit()] or [2025, 2026]
    df_new = fetch_psa_data(years)
    if not df_new.empty:
        logging.info("Harvested %d Nickel Ore rows from PSA OpenSTAT:\n%s", len(df_new), df_new[["date", "metric_tonnes", "value_usd"]])
        upsert_to_minor_bulks(df_new)


if __name__ == "__main__":
    main()
