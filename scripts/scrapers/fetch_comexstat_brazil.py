#!/usr/bin/env python3
"""
Brazil ComexStat (MDIC) monthly exports — REAL API DATA ONLY, paced for the free tier.

API notes (validated against live MDIC ComexStat, audit 2026-08):
  - Endpoint : POST https://api-comexstat.mdic.gov.br/general
  - Payload  : {"flow":"export","monthDetail":true,
                "period":{"from":"YYYY-MM","to":"YYYY-MM"},
                "filters":[{"filter":"ncm","values":[<8-digit codes>]}],
                "metrics":["metricFOB","metricKG"]}
    -> response {"data":{"list":[{year, monthNumber, metricFOB, metricKG}, ...]}}
  - Rate limiting is aggressive: space commodity queries ~45s apart, honour
    Retry-After on 429, retry with backoff.

Behaviour (data-provenance policy):
  - Every row comes straight from the live API. No hand-typed fallback exists.
  - If every commodity query fails -> exit non-zero, write nothing.
  - If some fail -> commit the successful ones, log the failures loudly.
"""
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "brazil_comexstat_exports.csv"

URL = "https://api-comexstat.mdic.gov.br/general"
PERIOD_FROM = "2024-01"
PERIOD_TO = datetime.now(timezone.utc).strftime("%Y-%m")  # rolling window; future months return empty

GAP_S = 45              # spacing between commodity queries (free-tier pacing)
MAX_RETRIES = 5         # 429/5xx backoff attempts per commodity
REQUEST_TIMEOUT = 120

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# commodity -> canonical NCM-8 export codes
COMMODITIES: dict[str, list[str]] = {
    "Iron Ore": ["26011100"],                      # iron ores & concentrates: fines (<0.3mm... agglomerated parent line kept simple)
    "Crude Oil": ["27090010"],                     # petroleum crude oils
    "Soybeans": ["12011000", "12019000"],          # seed-grade + other soybeans ("grãos")
    "Raw Sugar": ["17011300", "17011400"],         # raw cane sugar, no added flavouring
}


def _post(payload: dict) -> dict:
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_commodity(ncms: list[str]) -> list[dict]:
    payload = {
        "flow": "export",
        "monthDetail": True,
        "period": {"from": PERIOD_FROM, "to": PERIOD_TO},
        "filters": [{"filter": "ncm", "values": ncms}],
        "metrics": ["metricFOB", "metricKG"],
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            d = _post(payload)
            return (d.get("data") or {}).get("list") or []
        except urllib.error.HTTPError as e:  # noqa: PERF203
            last_err = f"HTTP {e.code}"
            if e.code == 429 or e.code >= 500:
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = float(ra) if (ra and str(ra).isdigit()) else min(2 ** attempt * 15, 90)
                logging.warning("%s -> %s (attempt %d/%d); backing off %.0fs",
                                ",".join(ncms), last_err, attempt, MAX_RETRIES, wait)
                time.sleep(wait)
                continue
            raise  # 4xx is a payload bug — surface it, don't mask it
        except Exception as e:  # noqa: BLE001, PERF203
            last_err = str(e)
            time.sleep(min(2 ** attempt * 10, 60))
    raise RuntimeError(f"ComexStat gave up on {ncms} after {MAX_RETRIES} tries ({last_err})")


def main() -> pd.DataFrame:
    frames = []
    failures = []
    for i, (commodity, ncms) in enumerate(COMMODITIES.items()):
        try:
            recs = fetch_commodity(ncms)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{commodity}: {exc}")
            continue
        rows = []
        for rec in recs:
            kg = float(rec.get("metricKG") or 0)
            if kg <= 0:
                continue
            y, m = int(rec["year"]), int(rec["monthNumber"])
            rows.append({
                "date": f"{y}-{m:02d}-01",
                "year": y,
                "month": m,
                "commodity": commodity,
                "ncm": "+".join(ncms),
                "metric_tonnes": round(kg / 1000.0, 2),
                "fob_usd": round(float(rec.get("metricFOB") or 0), 2),
            })
        # multiple NCMs may land in the same month -> aggregate
        df_c = (pd.DataFrame(rows)
                .groupby(["date", "year", "month", "commodity", "ncm"], as_index=False)
                .sum(numeric_only=True))
        frames.append(df_c)
        got_months = len(df_c)
        span = f"{df_c['date'].min()} .. {df_c['date'].max()}" if got_months else "EMPTY"
        logging.info("%-10s %2d months (%s)", commodity, got_months, span)
        if i < len(COMMODITIES) - 1:
            time.sleep(GAP_S)

    if not frames:
        raise SystemExit("ComexStat returned NO usable observations for any commodity "
                         "(all queries failed). Nothing written — investigate upstream.")

    df = (pd.concat(frames, ignore_index=True)
          .sort_values(["date", "commodity"]).reset_index(drop=True))
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d REAL API rows -> %s", len(df), OUT_FILE.name)
    if failures:
        logging.warning("%d commodities FAILED this run (absent from CSV): %s",
                        len(failures), "; ".join(failures))
    return df


if __name__ == "__main__":
    main()
