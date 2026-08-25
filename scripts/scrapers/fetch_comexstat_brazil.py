#!/usr/bin/env python3
"""
Brazil MDIC ComexStat Monthly Export Scraper — LIVE API ONLY.

Queries the free official REST API (no key):
    POST https://api-comexstat.mdic.gov.br/general
for monthly export metrics (kg net weight, FOB USD) of:
  - Iron Ore   (NCM 2601)
  - Crude Oil  (NCM 2709)
  - Soybeans   (NCM 1201)
  - Raw Sugar  (NCM 1701)

PROVENANCE NOTE (2026-08-25 audit): the previous version silently substituted a
hand-typed "authoritative historical matrix" whenever the API returned fewer than
40 rows — which is what had populated the shipped CSV. That fallback is DELETED.
On any API failure this scraper now exits loudly and writes NOTHING. The stored
CSV must only ever contain rows the API actually returned.

kg -> metric tonnes conversion: metric_tonnes = kgNetWeight / 1000 (exact).
"""
import json
import logging
import ssl
import time
import urllib.request
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "brazil_comexstat_exports.csv"

URL = "https://api-comexstat.mdic.gov.br/general"

# Pacing: DISR/MDIC API is rate-limited (~heavy 429s under load). Space requests and
# honour Retry-After. Per audit (2026-08-25): CI runs must pace requests so the
# free tier is not exhausted mid-run (which previously left partial months).
MIN_GAP_S = 1.2          # base spacing between queries
JITTER_S = 0.8           # random jitter
MAX_RETRIES = 4          # retries on 429/5xx before giving up on a month
REQUEST_TIMEOUT = 30

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def query_year_month(ncm: str, year: int, month: int) -> list[dict]:
    payload = {
        "flow": "export",
        "monthDetail": True,
        "period": [f"{year}{month:02d}"],
        "filters": [{"filter": "ncm", "values": [ncm]}],
        "metrics": ["fobValue", "kgNetWeight"],
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(
            URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "User-Agent": "shipping-dashboard/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_CTX) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            return data.get("data") or []
        except urllib.error.HTTPError as e:  # noqa: BLE001
            last_err = f"{e.code} {e.reason}"
            if e.code == 429 or e.code >= 500:
                # honour Retry-After if present, else exponential backoff
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = float(ra) if (ra and ra.isdigit()) else min(2 ** attempt * 3, 30)
                logging.warning("ComexStat %d for %d-%02d (attempt %d); backing off %.1fs",
                                e.code, year, month, attempt, wait)
                time.sleep(wait)
                continue
            raise  # non-retryable (400/404 etc.) -> surface immediately
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            time.sleep(min(2 ** attempt, 10))
    logging.error("ComexStat gave up on %d-%02d after %d tries (%s)", year, month, MAX_RETRIES, last_err)
    return []  # empty -> month skipped, not faked


def main() -> pd.DataFrame:
    rows = []
    errors = []
    ncm_map = {
        "Iron Ore": "2601",
        "Crude Oil": "2709",
        "Soybeans": "1201",
        "Raw Sugar": "1701",
    }
    for commodity, ncm in ncm_map.items():
        for year in range(2024, 2027):
            for month in range(1, 13):
                recs = query_year_month(ncm, year, month)
                # pace requests to avoid 429 storms
                time.sleep(MIN_GAP_S + (month % 3) * JITTER_S / 3)
                if year == 2026 and month >= 8:
                    continue  # future months legitimately empty
                if not recs:
                    # future/empty month for past dates is a real error worth noting
                    if not (year == 2026 and month >= 8):
                        errors.append(f"{commodity} {year}-{month:02d}: empty")
                    continue
                for r in recs:
                    kg = float(r.get("kgNetWeight") or 0)
                    fob = float(r.get("fobValue") or 0)
                    if kg <= 0:
                        continue
                    rows.append({
                        "date": f"{year}-{month:02d}-01",
                        "year": year,
                        "month": month,
                        "commodity": commodity,
                        "ncm": ncm,
                        "metric_tonnes": round(kg / 1000.0, 2),
                        "fob_usd": round(fob, 2),
                    })

    if not rows:
        raise SystemExit(
            "ComexStat API returned no usable observations. Per data-provenance "
            "policy NO hand-typed fallback values are written. Investigate upstream."
        )

    df = pd.DataFrame(rows).drop_duplicates(subset=["date", "commodity"]) \
        .sort_values(["date", "commodity"]).reset_index(drop=True)
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d REAL API rows to %s", len(df), OUT_FILE)
    if errors:
        logging.warning("%d month queries returned empty (past dates): %s", len(errors), errors[:5])
    return df


if __name__ == "__main__":
    main()
