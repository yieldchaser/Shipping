#!/usr/bin/env python3
"""
fetch_flows_shipping.py
──────────────────────────────────────────────────────────────────────────────
Fetches ETF fund flows, NAV, performance, and derived market signals for
BDRY and BWET from Trackinsight via Playwright browser session. Also fetches
Henry Hub Natural Gas Futures (NG=F) price history overlay from Yahoo Finance.

Outputs:
  - data/flows/BDRY_flows.json
  - data/flows/BWET_flows.json
  - data/flows/all_flows_summary.json
  - docs/data/flows/all_flows_summary.json
  - data/etf/BDRY_flows.csv
  - data/etf/BWET_flows.csv
"""

import argparse
import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import ssl

import pandas as pd
import numpy as np
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_flows")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FLOWS_DIR = DATA_DIR / "flows"
ETF_DIR = DATA_DIR / "etf"
DOCS_FLOWS_DIR = PROJECT_ROOT / "docs" / "data" / "flows"

ENDPOINT = "https://www.trackinsight.com/search-api/snapshot/get_snapshots"
TICKERS = ["BDRY", "BWET"]

# Yahoo Finance v8 chart API for NG=F history
YAHOO_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
NG_TICKER = "NG=F"


def parse_snapshots(data: list | dict, ticker: str) -> pd.DataFrame:
    if isinstance(data, list):
        if not data:
            return pd.DataFrame()
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        return pd.DataFrame()

    def unpack(field_data: dict) -> list[float]:
        if not isinstance(field_data, dict):
            return []
        scale = field_data.get("scale", 1)
        raw = field_data.get("data", [])
        return [v / scale if v is not None else None for v in raw]

    stamp_field = item.get("stamp", {})
    day_numbers = stamp_field.get("data", [])
    dates = []
    for d in day_numbers:
        try:
            dates.append(datetime.fromtimestamp(int(d) * 86400, tz=timezone.utc).strftime("%Y-%m-%d"))
        except Exception:
            dates.append(None)

    flow_vals = unpack(item.get("USD:flow", {}))
    nav_vals = unpack(item.get("nav", {}))
    perf_vals = unpack(item.get("perf", {}))

    n = len(dates)

    def pad(lst):
        return lst + [None] * (n - len(lst))

    df = pd.DataFrame({
        "date": dates,
        "usd_flow": pad(flow_vals),
        "nav": pad(nav_vals),
        "perf_pct": pad(perf_vals)
    })
    df = df.dropna(subset=["date"])
    df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)

    df["cumulative_flow"] = df["usd_flow"].cumsum()
    df["daily_inflow"] = df["usd_flow"].clip(lower=0)
    df["daily_outflow"] = df["usd_flow"].clip(upper=0)

    if not df.empty and pd.notna(df["nav"].iloc[-1]):
        latest_nav = df["nav"].iloc[-1]
        if not (0.01 <= latest_nav <= 50000.0):
            raise ValueError(f"Latest NAV {latest_nav} out of reasonable bounds for {ticker}")

    return df


# JS run inside the real browser page — same-origin fetch carrying active WAF cookies/headers
_FETCH_JS = """
async (payload) => {
    try {
        const resp = await fetch('%s', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            return {__error: true, status: resp.status, statusText: resp.statusText};
        }
        return await resp.json();
    } catch (e) {
        return {__error: true, status: 0, statusText: String(e)};
    }
}
""" % ENDPOINT


def fetch_live_data(ticker: str, start_date: str, end_date: str, page) -> pd.DataFrame:
    payload = {
        "requests": [{
            "fund": ticker,
            "startDate": start_date,
            "endDate": end_date,
            "columns": ["stamp", "USD:flow", "nav", "perf"]
        }]
    }

    def _do_request(pl):
        for attempt, wait in enumerate([0, 15, 30, 60]):
            if wait:
                logger.info(f"Rate limited for {ticker}, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
            try:
                result = page.evaluate(_FETCH_JS, pl)
                if isinstance(result, dict) and result.get("__error"):
                    logger.warning(f"Request error for {ticker}: {result['status']} {result['statusText']}")
                    continue
                return result
            except Exception as e:
                logger.warning(f"Request error for {ticker}: {e}")
        return None

    raw_data = _do_request(payload)
    if raw_data is not None:
        return parse_snapshots(raw_data, ticker)

    # Retry without endDate
    payload["requests"][0].pop("endDate", None)
    raw_data = _do_request(payload)
    if raw_data is not None:
        return parse_snapshots(raw_data, ticker)

    return pd.DataFrame()


def apply_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df["cumulative_flow"] = df["usd_flow"].cumsum()
    df["daily_inflow"] = df["usd_flow"].clip(lower=0)
    df["daily_outflow"] = df["usd_flow"].clip(upper=0)

    # 30-day rolling Z-Score
    window = 30
    df["mean_30d"] = df["usd_flow"].rolling(window, min_periods=5).mean()
    df["std_30d"] = df["usd_flow"].rolling(window, min_periods=5).std()
    df["flow_zscore"] = np.where(df["std_30d"] > 0, (df["usd_flow"] - df["mean_30d"]) / df["std_30d"], 0.0)

    # Momentum
    df["flow_5d"] = df["usd_flow"].rolling(5, min_periods=1).sum()
    df["flow_20d"] = df["usd_flow"].rolling(20, min_periods=1).sum()

    # Flow Regime
    def get_regime(z):
        if pd.isna(z):
            return "BALANCED"
        if z > 1.5:
            return "ACCUMULATION"
        if z < -1.5:
            return "DISTRIBUTION"
        return "BALANCED"

    df["regime"] = df["flow_zscore"].apply(get_regime)

    # Streak
    sign = np.sign(df["usd_flow"])
    streak = sign.groupby((sign != sign.shift()).cumsum()).cumsum()

    # Pressure calculation
    def compute_pressure(row, s):
        if pd.isna(row["flow_zscore"]):
            return 0.0
        mom_factor = 10 if row["flow_5d"] > 0 else (-10 if row["flow_5d"] < 0 else 0)
        streak_bonus = min(abs(s) * 2, 20) * (1 if s > 0 else -1)
        raw = (row["flow_zscore"] * 25) + mom_factor + streak_bonus
        return max(-100.0, min(100.0, raw))

    pressures = []
    for idx, row in df.iterrows():
        pressures.append(compute_pressure(row, streak.loc[idx]))
    df["pressure"] = pressures

    df = df.drop(columns=["mean_30d", "std_30d"])

    for col in ["flow_zscore", "flow_5d", "flow_20d", "pressure"]:
        df[col] = df[col].fillna(0.0)

    return df


RAW_COLS = ["date", "usd_flow", "nav", "perf_pct"]


def load_existing(json_path: Path) -> pd.DataFrame:
    try:
        with open(json_path) as f:
            existing = json.load(f)
        df = pd.DataFrame(existing["data"])
        return df[[c for c in RAW_COLS if c in df.columns]]
    except Exception:
        return pd.DataFrame()


def fetch_ng_history():
    """Fetch NG=F (Henry Hub Natural Gas Futures) daily closes from Yahoo Finance v8."""
    logger.info("Fetching NG=F history for flow-price overlay...")

    period1 = int(datetime(2007, 1, 1).timestamp())
    period2 = int(datetime.now().timestamp())
    url = (
        f"{YAHOO_BASE_URL}{urllib.request.quote(NG_TICKER)}"
        f"?period1={period1}&period2={period2}&interval=1d&includePrePost=false"
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            resp = urllib.request.urlopen(req, context=ctx, timeout=30)
            raw = json.loads(resp.read())

            result = raw["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]

            history = []
            for i in range(len(timestamps)):
                close = quote["close"][i]
                if close is None:
                    continue
                date_str = datetime.fromtimestamp(timestamps[i], tz=timezone.utc).strftime("%Y-%m-%d")
                history.append({"date": date_str, "close": round(close, 4)})

            seen = set()
            deduped = []
            for h in reversed(history):
                if h["date"] not in seen:
                    seen.add(h["date"])
                    deduped.append(h)
            deduped.reverse()

            logger.info(f"NG=F: fetched {len(deduped)} daily closes")
            return deduped

        except Exception as e:
            logger.warning(f"NG=F fetch attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(5 * attempt)

    logger.error("All NG=F fetch attempts failed")
    return []


def main():
    parser = argparse.ArgumentParser(description="Shipping ETF Fund Flow Scraper (Trackinsight Playwright Engine)")
    parser.add_argument("--seed", action="store_true", help="Seed from local CSVs")
    parser.add_argument("--full", action="store_true", help="Force full re-fetch from 2010-01-01")
    args = parser.parse_args()

    FLOWS_DIR.mkdir(parents=True, exist_ok=True)
    ETF_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_FLOWS_DIR.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    summary_data = {
        "updated": today_str,
        "tickers": {},
        "cross_etf": {}
    }

    latest_dates = []

    flow_30d_bdry = 0.0
    flow_30d_bwet = 0.0

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox"
        ]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    logger.info("Warming up browser session on trackinsight.com...")
    page.goto("https://www.trackinsight.com/en/fund/BDRY/flows", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    for ticker in TICKERS:
        logger.info(f"Processing {ticker}...")
        time.sleep(1)
        df = pd.DataFrame()
        json_out = FLOWS_DIR / f"{ticker}_flows.json"

        if args.seed:
            csv_files = list(DATA_DIR.glob(f"{ticker}_flows_*.csv"))
            if csv_files:
                csv_file = sorted(csv_files)[-1]
                logger.info(f"Seeding from {csv_file}")
                df = pd.read_csv(csv_file)
            else:
                logger.warning(f"No CSV found for {ticker}")
                continue
        elif args.full or not json_out.exists():
            df = fetch_live_data(ticker, "2010-01-01", today_str, page)
            if df.empty:
                logger.warning(f"Extended history unavailable for {ticker}, falling back to 2021-01-01")
                df = fetch_live_data(ticker, "2021-01-01", today_str, page)
        else:
            existing_df = load_existing(json_out)
            if existing_df.empty:
                start_date = "2010-01-01"
            else:
                last_date = existing_df["date"].max()
                start_date = last_date
                logger.info(f"{ticker}: have data through {last_date}, fetching from {start_date}")

            new_df = fetch_live_data(ticker, start_date, today_str, page)

            if new_df.empty and existing_df.empty:
                logger.error(f"No data for {ticker}. Skipping.")
                continue
            elif new_df.empty:
                logger.warning(f"No new data for {ticker}, keeping existing.")
                df = existing_df
            elif existing_df.empty:
                df = new_df
            else:
                new_raw = new_df[[c for c in RAW_COLS if c in new_df.columns]]
                df = pd.concat([existing_df, new_raw], ignore_index=True)
                df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
                logger.info(f"{ticker}: merged {len(existing_df)} existing + {len(new_raw)} new = {len(df)} rows")

        if df.empty:
            logger.error(f"No data for {ticker}. Skipping.")
            continue

        df = apply_derived_metrics(df)

        # 1) Save JSON Output
        for col in ["usd_flow", "daily_inflow", "daily_outflow", "cumulative_flow", "nav", "perf_pct", "flow_zscore", "flow_5d", "flow_20d", "pressure"]:
            if col in df.columns:
                df[col] = df[col].round(4)

        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.fillna(0, inplace=True)

        json_dict = {
            "ticker": ticker,
            "updated": today_str,
            "data": df.to_dict(orient="records")
        }

        with open(json_out, "w") as f:
            json.dump(json_dict, f, indent=2)

        logger.info(f"Saved {len(df)} rows to {json_out}")

        # 2) Save CSV Output (for data/etf/{ticker}_flows.csv compatibility)
        csv_out = ETF_DIR / f"{ticker}_flows.csv"
        csv_cols = ["date", "usd_flow", "nav", "perf_pct", "cumulative_flow", "daily_inflow", "daily_outflow"]
        df_csv = df[[c for c in csv_cols if c in df.columns]]
        df_csv.to_csv(csv_out, index=False)
        logger.info(f"Saved {len(df_csv)} rows to {csv_out}")

        # Populate summary statistics
        last_row = df.iloc[-1]
        last_30d_net = df.tail(30)["usd_flow"].sum()

        actual_latest = df["date"].max()
        if actual_latest:
            latest_dates.append(actual_latest)

        summary_data["tickers"][ticker] = {
            "last_30d_net": round(last_30d_net, 2),
            "zscore": round(last_row["flow_zscore"], 2),
            "regime": last_row["regime"],
            "pressure": round(last_row["pressure"], 0),
            "latest_nav": round(last_row["nav"], 2),
            "flow_5d": round(last_row["flow_5d"], 2),
            "flow_20d": round(last_row["flow_20d"], 2),
            "latest_date": actual_latest
        }

        if ticker == "BDRY":
            flow_30d_bdry += last_30d_net
        elif ticker == "BWET":
            flow_30d_bwet += last_30d_net

    browser.close()
    pw.stop()

    if latest_dates:
        actual_data_date = min(latest_dates)
        summary_data["updated"] = actual_data_date
        logger.info(f"Actual data date: {actual_data_date} (range: {min(latest_dates)} – {max(latest_dates)})")

    summary_data["cross_etf"] = {
        "bdry_flow_30d": round(flow_30d_bdry, 2),
        "bwet_flow_30d": round(flow_30d_bwet, 2),
        "combined_flow_30d": round(flow_30d_bdry + flow_30d_bwet, 2)
    }

    combined = flow_30d_bdry + flow_30d_bwet
    sentiment = "NEUTRAL"
    if combined > 10000:
        sentiment = "BULLISH"
    elif combined < -10000:
        sentiment = "BEARISH"

    summary_data["cross_etf"]["sentiment"] = sentiment

    ng_history = fetch_ng_history()
    if ng_history:
        summary_data["ng_history"] = ng_history
        logger.info(f"Added {len(ng_history)} NG=F daily closes to summary")

    summary_out = FLOWS_DIR / "all_flows_summary.json"
    with open(summary_out, "w") as f:
        json.dump(summary_data, f, indent=2)
    logger.info(f"Saved summary to {summary_out}")

    docs_summary = DOCS_FLOWS_DIR / "all_flows_summary.json"
    with open(docs_summary, "w") as f:
        json.dump(summary_data, f, indent=2)
    logger.info(f"Copied summary to {docs_summary}")


if __name__ == "__main__":
    main()
