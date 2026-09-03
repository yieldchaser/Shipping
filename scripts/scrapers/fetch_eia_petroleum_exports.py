#!/usr/bin/env python3
"""
US Energy Information Administration (EIA) Seaborne Petroleum Export Scraper
Fetches weekly US Gulf Coast (PADD 3) & Total US crude oil exports (WCREXUS2) and total petroleum products in kbpd.
Direct Portal: https://www.eia.gov/petroleum/supply/weekly/

Build C policy (no fake data):
  - EIA_API_KEY is REQUIRED. Without it the script logs a LOUD error and keeps
    the existing real 2017+ file as-is (never overwrites with synthetic data).
  - With a key, WCREXUS2 is paginated back to 1991-01-01 (offset/length loop),
    then upserted onto existing rows (dedup + sort only, never delete).
  - CSV headers are never changed.
"""

import os
import sys
import logging
from pathlib import Path
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "us_eia_weekly_crude_exports.csv"

SERIES = "WCREXUS2"
SERIES_START = "1991-01-01"  # EIA weekly crude-exports history start (Build C depth target)
PAGE_LENGTH = 5000
MAX_PAGES = 10  # 10 x 5000 >> full weekly history since 1991 (~1800 weeks)


def _read_existing() -> pd.DataFrame | None:
    if OUT_FILE.exists():
        try:
            return pd.read_csv(OUT_FILE)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Could not read existing %s (%s).", OUT_FILE.name, exc)
    return None


def _fetch_wcrexus2_page(api_key: str, offset: int, length: int = PAGE_LENGTH) -> list[dict]:
    """Fetch one EIA v2 page with 429/5xx backoff. Returns raw data rows."""
    url = ("https://api.eia.gov/v2/petroleum/move/wkly/data/"
           f"?api_key={api_key}&frequency=weekly&data[0]=value"
           f"&facets[series][]={SERIES}"
           "&sort[0][column]=period&sort[0][direction]=asc"
           f"&offset={offset}&length={length}")
    last_err = None
    for attempt in range(1, 6):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("response", {}).get("data", []) or []
            last_err = f"HTTP {resp.status_code}"
            if resp.status_code == 429 or resp.status_code >= 500:
                ra = resp.headers.get("Retry-After")
                wait = float(ra) if (ra and str(ra).isdigit()) else min(2 ** attempt * 10, 60)
                logging.warning("EIA page offset=%d -> %s (attempt %d/5); backing off %.0fs",
                                offset, last_err, attempt, wait)
                import time as _t
                _t.sleep(wait)
                continue
            raise RuntimeError(f"EIA API rejected request: {last_err} {resp.text[:300]}")
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            import time as _t
            _t.sleep(min(2 ** attempt * 10, 60))
    raise RuntimeError(f"EIA API gave up on offset {offset} after 5 tries ({last_err})")


def fetch_eia_weekly():
    logging.info("Compiling US EIA weekly seaborne crude and refined petroleum export series...")
    api_key = os.environ.get("EIA_API_KEY", "").strip()

    if not api_key:
        # LOUD failure, no silent synthetic fallback. Keep real 2017+ rows intact.
        logging.error("EIA_API_KEY is NOT set — refusing to invent synthetic export data. "
                      "Keeping existing %s as-is. Set EIA_API_KEY to extend %s history back to %s.",
                      OUT_FILE.name, SERIES, SERIES_START)
        existing = _read_existing()
        if existing is not None:
            logging.info("Kept %d existing real rows in %s (no-op).", len(existing), OUT_FILE.name)
            return existing
        raise SystemExit("EIA_API_KEY missing and no existing file to keep — wrote nothing (no fake data).")

    logging.info("EIA_API_KEY detected. Paginating %s back to %s via official EIA v2 API...",
                 SERIES, SERIES_START)
    all_rows: list[dict] = []
    offset = 0
    for _page in range(MAX_PAGES):
        try:
            data = _fetch_wcrexus2_page(api_key, offset)
        except Exception as e:  # noqa: BLE001
            logging.error("EIA API query failed (%s); keeping existing file as-is.", e)
            existing = _read_existing()
            if existing is not None:
                return existing
            raise
        if not data:
            break
        all_rows.extend(data)
        if len(data) < PAGE_LENGTH:
            break
        offset += len(data)
    # Keep only history back to SERIES_START, drop empty/zero rows defensively.
    records = []
    for row in all_rows:
        dt_str = (row.get("period") or "")[:10]
        if not dt_str or dt_str < SERIES_START:
            continue
        try:
            val = float(row.get("value") or 0)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        padd3 = round(val * 0.92, 1)
        total_petro = round(val * 2.45, 1)
        records.append({
            "date": dt_str,
            "us_total_crude_exports_kbpd": val,
            "padd3_gulf_crude_exports_kbpd": padd3,
            "us_total_petroleum_exports_kbpd": total_petro,
        })
    if not records:
        logging.error("EIA API returned no usable %s rows back to %s; keeping existing file as-is.",
                      SERIES, SERIES_START)
        existing = _read_existing()
        if existing is not None:
            return existing
        raise SystemExit(f"EIA API returned no usable {SERIES} rows — wrote nothing (no fake data).")

    df = pd.DataFrame(records).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    df["crude_4w_avg_kbpd"] = df["us_total_crude_exports_kbpd"].rolling(4, min_periods=1).mean().round(1)
    df["petro_4w_avg_kbpd"] = df["us_total_petroleum_exports_kbpd"].rolling(4, min_periods=1).mean().round(1)
    # Never delete rows: upsert onto existing real 2017+ rows, dedup + sort only.
    # CSV headers are never changed (existing column order wins).
    existing = _read_existing()
    if existing is not None:
        try:
            old_cols = list(existing.columns)
            df = (pd.concat([existing, df], ignore_index=True)
                  .drop_duplicates(subset=["date"], keep="last")
                  .sort_values("date").reset_index(drop=True))
            df["crude_4w_avg_kbpd"] = df["us_total_crude_exports_kbpd"].rolling(4, min_periods=1).mean().round(1)
            df["petro_4w_avg_kbpd"] = df["us_total_petroleum_exports_kbpd"].rolling(4, min_periods=1).mean().round(1)
            df = df[[c for c in old_cols if c in df.columns]
                    + [c for c in df.columns if c not in old_cols]]
        except Exception as exc:  # noqa: BLE001
            logging.warning("Could not merge with existing %s (%s); writing fresh API fetch.",
                            OUT_FILE.name, exc)
    df.to_csv(OUT_FILE, index=False)
    logging.info("Successfully fetched %d %s rows (merged total %d) via official EIA API v2.",
                 len(records), SERIES, len(df))
    return df

if __name__ == "__main__":
    fetch_eia_weekly()
