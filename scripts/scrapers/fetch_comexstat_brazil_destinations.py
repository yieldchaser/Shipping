#!/usr/bin/env python3
"""
Brazil ComexStat (MDIC) monthly exports BY DESTINATION COUNTRY - official, free, no key.

Where Brazil's iron ore, soybeans, crude oil and sugar go each month, in tonnes and FOB USD. The China column is
the exporter-side view of the Capesize C3 (Tubarao-Qingdao) iron ore trade and of Brazil-China soybean and crude
flows; China customs' own by-partner tables are not reachable by script (see docs/PRE_GRAPHRAG_OPEN_ITEMS.md).

API (checked 2026-11-01): POST https://api-comexstat.mdic.gov.br/general
  {"flow":"export","monthDetail":true,"period":{"from":"YYYY-MM","to":"YYYY-MM"},
   "filters":[{"filter":"heading","values":["2601"]}],"details":["country","heading"],
   "metrics":["metricKG","metricFOB"]}
  -> data.list[]: year, monthNumber, country (Portuguese name), headingCode, metricKG, metricFOB

Output: data/commodities/brazil_exports_by_destination.csv
  date, commodity, hs_heading, country, metric_tonnes, fob_usd, source, source_url
Rows are written exactly as served (kg / 1000). Months already stored are re-fetched only for the last 3 months
(ComexStat revises the latest months); older history is kept. A commodity whose query fails keeps its stored rows.
"""
import json
import logging
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
OUT_FILE = ROOT / "data" / "commodities" / "brazil_exports_by_destination.csv"
URL = "https://api-comexstat.mdic.gov.br/general"
FIRST_YEAR = 2018
GAP_S = 20             # free-tier pacing between queries
MAX_RETRIES = 5

# commodity -> HS heading (4-digit): the whole heading, so the totals are Brazil's full exports of the product
COMMODITIES = {
    "Iron Ore": "2601",
    "Soybeans": "1201",
    "Crude Oil": "2709",
    "Sugar": "1701",
}
# ComexStat serves Portuguese country names; the dashboard shows English ones for the main destinations
COUNTRY_EN = {
    "China": "China", "Hong Kong": "Hong Kong", "Japão": "Japan", "Coreia do Sul": "South Korea",
    "Malásia": "Malaysia", "Países Baixos (Holanda)": "Netherlands", "Omã": "Oman", "Bahrein": "Bahrain",
    "Estados Unidos": "United States", "Espanha": "Spain", "Índia": "India", "Singapura": "Singapore",
    "Tailândia": "Thailand", "Irã": "Iran", "Turquia": "Turkey", "Egito": "Egypt", "Argélia": "Algeria",
    "Arábia Saudita": "Saudi Arabia", "Emirados Árabes Unidos": "United Arab Emirates", "Bangladesh": "Bangladesh",
    "Indonésia": "Indonesia", "Vietnã": "Vietnam", "Taiwan (Formosa)": "Taiwan", "Alemanha": "Germany",
    "França": "France", "Itália": "Italy", "Reino Unido": "United Kingdom", "Chile": "Chile", "Argentina": "Argentina",
    "Filipinas": "Philippines", "Paquistão": "Pakistan", "Marrocos": "Morocco", "Nigéria": "Nigeria",
    "Canadá": "Canada", "Portugal": "Portugal", "Rússia": "Russia", "Trinidad e Tobago": "Trinidad and Tobago",
    "Panamá": "Panama", "Peru": "Peru", "Uruguai": "Uruguay", "México": "Mexico", "Catar": "Qatar",
    "Kuwait": "Kuwait", "Iraque": "Iraq", "Jordânia": "Jordan", "Iêmen": "Yemen", "Sudão": "Sudan",
    "Bélgica": "Belgium", "Noruega": "Norway", "Polônia": "Poland", "Grécia": "Greece", "Romênia": "Romania",
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False      # same as fetch_comexstat_brazil.py: the MDIC chain fails on some runners
_CTX.verify_mode = ssl.CERT_NONE


def _post(payload: dict) -> dict:
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "Accept": "application/json",
                                                  "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if not d.get("success", True) or "data" not in d:
                raise RuntimeError(f"API answered without data: {str(d)[:200]}")
            return d
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 30 * (attempt + 1)
            logging.warning("ComexStat attempt %d failed (%s); retry in %ds", attempt + 1, e, wait)
            time.sleep(wait)
    raise RuntimeError(f"ComexStat failed after {MAX_RETRIES} attempts: {last}")


def fetch(commodity: str, heading: str, start: str, end: str) -> list[dict]:
    d = _post({"flow": "export", "monthDetail": True, "period": {"from": start, "to": end},
               "filters": [{"filter": "heading", "values": [heading]}], "details": ["country", "heading"],
               "metrics": ["metricKG", "metricFOB"]})
    rows = []
    for r in d["data"]["list"]:
        if r.get("headingCode") != heading:
            continue
        country = r["country"]
        rows.append({"date": f"{r['year']}-{int(r['monthNumber']):02d}-01", "commodity": commodity,
                     "hs_heading": heading, "country": COUNTRY_EN.get(country, country),
                     "metric_tonnes": round(float(r["metricKG"]) / 1000.0, 3), "fob_usd": float(r["metricFOB"]),
                     "source": "Brazil MDIC SECEX ComexStat API (exports by destination)", "source_url": URL})
    return rows


def main() -> int:
    now = datetime.now(timezone.utc)
    end = now.strftime("%Y-%m")
    old = pd.read_csv(OUT_FILE, dtype={"hs_heading": str}) if OUT_FILE.exists() else pd.DataFrame()
    keep, fresh, failed = [], [], []
    for i, (commodity, heading) in enumerate(COMMODITIES.items()):
        have = old[old["commodity"] == commodity] if len(old) else old
        if len(have):
            # history kept; the last 3 stored months are re-fetched (ComexStat revises them)
            last = pd.Period(have["date"].max()[:7], "M")
            start = str(last - 2)
            windows = [(start, end)]
            keep.append(have[have["date"] < f"{start}-01"])
        else:
            windows = [(f"{y}-01", f"{y}-12" if y < now.year else end) for y in range(FIRST_YEAR, now.year + 1)]
        try:
            got = []
            for a, b in windows:
                got += fetch(commodity, heading, a, b)
                time.sleep(GAP_S)
            if not got:
                raise RuntimeError("no rows returned")
            fresh += got
            logging.info("%s (HS %s): %d rows, %s..%s", commodity, heading, len(got),
                         min(r["date"] for r in got), max(r["date"] for r in got))
        except Exception as e:  # noqa: BLE001
            logging.error("%s failed (%s); stored rows kept", commodity, e)
            failed.append(commodity)
            if len(have):
                keep[-1] = have
        if i < len(COMMODITIES) - 1:
            time.sleep(GAP_S)

    out = pd.concat([*keep, pd.DataFrame(fresh)], ignore_index=True)
    if out.empty:
        logging.error("nothing fetched and nothing stored")
        return 1
    out = (out.drop_duplicates(subset=["date", "commodity", "country"], keep="last")
              .sort_values(["commodity", "date", "metric_tonnes"], ascending=[True, True, False]))
    out.to_csv(OUT_FILE, index=False, lineterminator="\n")
    logging.info("Wrote %d rows -> %s (latest %s)", len(out), OUT_FILE.name, out["date"].max())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
