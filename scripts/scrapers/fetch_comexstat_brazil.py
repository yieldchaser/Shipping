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
# Build C: maximize historical depth. ComexStat monthly series is available back
# to 1997-01 (NCM-based). Fetch year-by-year so a single huge window cannot
# time out / 429 the free tier, and so one bad year never wipes good history.
# Set COMEXSTAT_FULL_HISTORY=0 to fetch only the recent window (2024+).
PERIOD_FROM = "1997-01"
RECENT_FROM = "2024-01"
PERIOD_TO = datetime.now(timezone.utc).strftime("%Y-%m")  # rolling window; future months return empty

GAP_S = 45              # spacing between commodity queries (free-tier pacing)
YEAR_GAP_S = 5          # spacing between year-slice queries for the same commodity
MAX_RETRIES = 5         # 429/5xx backoff attempts per commodity-year slice
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
    """Fetch one commodity year-by-year from PERIOD_FROM..PERIOD_TO.

    Year slicing keeps each POST small (free-tier 429 avoidance) and isolates
    failures: one bad year logs loudly but does not discard other years.
    Honors Retry-After on 429 with exponential backoff per year slice.
    """
    import os as _os

    full_history = _os.environ.get("COMEXSTAT_FULL_HISTORY", "1").strip() not in ("0", "false", "False", "")
    start_year = int((PERIOD_FROM if full_history else RECENT_FROM).split("-")[0])
    end_year = int(PERIOD_TO.split("-")[0])
    all_recs: list[dict] = []
    for year in range(start_year, end_year + 1):
        period_from = f"{year}-01"
        period_to = PERIOD_TO if year == end_year else f"{year}-12"
        payload = {
            "flow": "export",
            "monthDetail": True,
            "period": {"from": period_from, "to": period_to},
            "filters": [{"filter": "ncm", "values": ncms}],
            "metrics": ["metricFOB", "metricKG"],
        }
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                d = _post(payload)
                recs = (d.get("data") or {}).get("list") or []
                all_recs.extend(recs)
                break
            except urllib.error.HTTPError as e:  # noqa: PERF203
                last_err = f"HTTP {e.code}"
                if e.code == 429 or e.code >= 500:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    wait = float(ra) if (ra and str(ra).isdigit()) else min(2 ** attempt * 15, 90)
                    logging.warning("%s [%s] -> %s (attempt %d/%d); backing off %.0fs",
                                    ",".join(ncms), period_from, last_err, attempt, MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                raise  # 4xx is a payload bug — surface it, don't mask it
            except Exception as e:  # noqa: BLE001, PERF203
                last_err = str(e)
                time.sleep(min(2 ** attempt * 10, 60))
        else:
            logging.warning("ComexStat gave up on %s year %d after %d tries (%s); "
                            "keeping other years.",
                            ",".join(ncms), year, MAX_RETRIES, last_err)
            continue
        time.sleep(YEAR_GAP_S)
    if not all_recs:
        raise RuntimeError(f"ComexStat gave up on {ncms} for {start_year}..{end_year}")
    return all_recs


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
        # No-break rule: keep the existing 2024+ file untouched on total failure.
        if OUT_FILE.exists():
            logging.error("ComexStat returned NO usable observations for any commodity "
                          "(all queries failed). Keeping existing file untouched — "
                          "investigate upstream.")
            return pd.read_csv(OUT_FILE)
        raise SystemExit("ComexStat returned NO usable observations for any commodity "
                         "(all queries failed). Nothing written — investigate upstream.")

    df = (pd.concat(frames, ignore_index=True)
          .sort_values(["date", "commodity"]).reset_index(drop=True))
    # Never truncate history: upsert new API rows onto existing 2024+ rows,
    # dedup on (date, commodity), sort only. Header order unchanged.
    if OUT_FILE.exists():
        try:
            df_old = pd.read_csv(OUT_FILE)
            df = (pd.concat([df_old, df], ignore_index=True)
                  .drop_duplicates(subset=["date", "commodity"], keep="last")
                  .sort_values(["date", "commodity"]).reset_index(drop=True))
            # Preserve existing column order (never change CSV headers).
            df = df[[c for c in df_old.columns if c in df.columns]
                    + [c for c in df.columns if c not in df_old.columns]]
        except Exception as exc:  # noqa: BLE001
            logging.warning("Could not merge with existing %s (%s); writing fresh fetch.",
                            OUT_FILE.name, exc)
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d REAL API rows -> %s", len(df), OUT_FILE.name)
    if failures:
        logging.warning("%d commodities FAILED this run (absent from CSV): %s",
                        len(failures), "; ".join(failures))
    return df


if __name__ == "__main__":
    main()
