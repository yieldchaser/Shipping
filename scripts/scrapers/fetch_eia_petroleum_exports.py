#!/usr/bin/env python3
"""
US Energy Information Administration (EIA) Seaborne Petroleum Export Scraper
Fetches weekly total US crude oil exports (EIA series WCREXUS2) in kbpd.

EIA publishes weekly crude exports for the US as a whole only. Earlier versions of
this script wrote a 'PADD 3 Gulf Coast' column as US total x 0.92 and a 'total
petroleum' column as US total x 2.45. Neither is an EIA series; both were removed
(2026-09-13) and must not come back.
Direct Portal: https://www.eia.gov/petroleum/supply/weekly/

Build C policy (no fake data):
  - With EIA_API_KEY, WCREXUS2 is paginated back to 1991-01-01 via the v2 API (offset/length loop).
  - Without a key, the same series is read from EIA's own history workbook
    (https://www.eia.gov/dnav/pet/hist_xls/WCREXUS2w.xls, no key needed). The CI secret was never set,
    so the file had stopped at 2026-09-11.
  - Either way the rows are upserted onto the existing ones (dedup + sort only, never delete); on any
    failure the existing file is kept as-is (never synthetic data).
"""

import io
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
HIST_XLS = "https://www.eia.gov/dnav/pet/hist_xls/WCREXUS2w.xls"
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


def _fetch_wcrexus2_xls() -> list[dict]:
    """WCREXUS2 from EIA's history workbook: sheet 'Data 1', week-ending date and kbpd."""
    resp = requests.get(HIST_XLS, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Data 1", skiprows=2)
    df = df.iloc[:, :2].dropna()
    df.columns = ["period", "value"]
    return [{"period": pd.Timestamp(d).strftime("%Y-%m-%d"), "value": v} for d, v in zip(df["period"], df["value"])]


def fetch_eia_weekly():
    logging.info("Compiling US EIA weekly seaborne crude and refined petroleum export series...")
    api_key = os.environ.get("EIA_API_KEY", "").strip()

    all_rows: list[dict] = []
    if not api_key:
        logging.info("EIA_API_KEY not set: reading %s from the EIA history workbook %s", SERIES, HIST_XLS)
        try:
            all_rows = _fetch_wcrexus2_xls()
        except Exception as e:  # noqa: BLE001
            logging.error("EIA history workbook failed (%s); keeping existing file as-is.", e)
            existing = _read_existing()
            if existing is not None:
                return existing
            raise

    if api_key:
        logging.info("EIA_API_KEY detected. Paginating %s back to %s via official EIA v2 API...",
                 SERIES, SERIES_START)
    offset = 0
    for _page in range(MAX_PAGES if api_key else 0):
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
        records.append({
            "date": dt_str,
            "us_total_crude_exports_kbpd": val,
        })
    if not records:
        logging.error("EIA API returned no usable %s rows back to %s; keeping existing file as-is.",
                      SERIES, SERIES_START)
        existing = _read_existing()
        if existing is not None:
            return existing
        raise SystemExit(f"EIA API returned no usable {SERIES} rows — wrote nothing (no fake data).")

    df = pd.DataFrame(records).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    # Never delete rows: upsert onto existing real rows, dedup + sort only.
    existing = _read_existing()
    if existing is not None:
        try:
            df = (pd.concat([existing[["date", "us_total_crude_exports_kbpd"]], df], ignore_index=True)
                  .drop_duplicates(subset=["date"], keep="last")
                  .sort_values("date").reset_index(drop=True))
        except Exception as exc:  # noqa: BLE001
            logging.warning("Could not merge with existing %s (%s); writing fresh API fetch.",
                            OUT_FILE.name, exc)
    df["crude_4w_avg_kbpd"] = df["us_total_crude_exports_kbpd"].rolling(4, min_periods=1).mean().round(1)
    df = df[["date", "us_total_crude_exports_kbpd", "crude_4w_avg_kbpd"]]
    df.to_csv(OUT_FILE, index=False, lineterminator="\n")
    logging.info("Successfully fetched %d %s rows (merged total %d) via %s.",
                 len(records), SERIES, len(df), "EIA API v2" if api_key else "the EIA history workbook")
    return df

if __name__ == "__main__":
    fetch_eia_weekly()
