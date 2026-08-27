#!/usr/bin/env python3
"""
fetch_live_etf_quotes.py
========================
Fetches latest market quotes for freight ETFs (BDRY, BWET) and writes
an authoritative JSON cache to `data/etf/live_quotes.json`.

This provides:
1. Instant, zero-CORS baseline live pricing for the browser terminal.
2. 15-to-30 minute fresh snapshot fallback when client-side CORS proxies are unavailable.
3. Multi-source fallback (Yahoo Finance -> CNBC -> Stooq).
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "etf", "live_quotes.json")
TICKERS = ["BDRY", "BWET"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def fetch_yahoo_quote(ticker: str) -> dict:
    """Fetch quote from Yahoo Finance API."""
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    res = payload.get("chart", {}).get("result", [{}])[0]
                    meta = res.get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    if price is not None and not isinstance(price, (int, float)):
                        price = float(price)
                    if prev_close is not None and not isinstance(prev_close, (int, float)):
                        prev_close = float(prev_close)

                    if price is not None and price > 0:
                        chg = (price - prev_close) if prev_close else 0.0
                        chg_pct = (chg / prev_close * 100) if prev_close and prev_close > 0 else 0.0
                        market_time = meta.get("regularMarketTime")
                        mkt_iso = datetime.fromtimestamp(market_time, tz=timezone.utc).isoformat() if market_time else None
                        
                        return {
                            "symbol": ticker,
                            "price": round(price, 4),
                            "previous_close": round(prev_close, 4) if prev_close else None,
                            "change": round(chg, 4),
                            "change_percent": round(chg_pct, 4),
                            "regular_market_day_high": meta.get("regularMarketDayHigh"),
                            "regular_market_day_low": meta.get("regularMarketDayLow"),
                            "regular_market_volume": meta.get("regularMarketVolume"),
                            "market_time_utc": mkt_iso,
                            "currency": meta.get("currency", "USD"),
                            "exchange": meta.get("exchangeName", "NYSEArca"),
                            "source": "yahoo_finance",
                        }
        except Exception as e:
            continue
    return None


def fetch_cnbc_quote(ticker: str) -> dict:
    """Fallback: fetch quote from CNBC webservice."""
    url = (
        f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?"
        f"symbols={ticker}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json"
    )
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                fq = payload.get("FormattedQuoteResult", {}).get("FormattedQuote", [{}])[0]
                last = fq.get("last")
                if last:
                    price = float(str(last).replace(",", ""))
                    prev_close_str = fq.get("previous_day_closing")
                    prev_close = float(str(prev_close_str).replace(",", "")) if prev_close_str else None
                    chg_pct_str = fq.get("change_pct")
                    chg_pct = float(str(chg_pct_str).replace("%", "").replace(",", "")) if chg_pct_str else 0.0
                    chg_str = fq.get("change")
                    chg = float(str(chg_str).replace(",", "")) if chg_str else 0.0

                    return {
                        "symbol": ticker,
                        "price": round(price, 4),
                        "previous_close": round(prev_close, 4) if prev_close else None,
                        "change": round(chg, 4),
                        "change_percent": round(chg_pct, 4),
                        "regular_market_day_high": float(fq.get("high", 0)) if fq.get("high") else None,
                        "regular_market_day_low": float(fq.get("low", 0)) if fq.get("low") else None,
                        "regular_market_volume": int(fq.get("volume", 0)) if fq.get("volume") else None,
                        "market_time_utc": fq.get("last_time"),
                        "currency": "USD",
                        "exchange": "NYSEArca",
                        "source": "cnbc",
                    }
    except Exception:
        pass
    return None


def fetch_quote_with_fallback(ticker: str) -> dict:
    """Attempt primary Yahoo fetch, then fallback to CNBC."""
    q = fetch_yahoo_quote(ticker)
    if q:
        return q
    q = fetch_cnbc_quote(ticker)
    if q:
        return q
    return None


def run_pipeline(dry_run: bool = False) -> dict:
    """Execute live quote retrieval and write bundle."""
    now_iso = datetime.now(timezone.utc).isoformat()
    bundle = {
        "schema_version": "1.0",
        "updated_at_utc": now_iso,
        "quotes": {}
    }

    print(f"[{now_iso}] Fetching ETF quotes for {TICKERS}...")
    success_count = 0

    for ticker in TICKERS:
        q = fetch_quote_with_fallback(ticker)
        if q:
            bundle["quotes"][ticker] = q
            success_count += 1
            print(f"  [OK] {ticker}: ${q['price']:.2f} ({q['change_percent']:+.2f}%) via {q['source']}")
        else:
            print(f"  [WARN] Failed to fetch live quote for {ticker}")

    if not dry_run and success_count > 0:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
        print(f"[OK] Wrote {OUTPUT_PATH} ({success_count}/{len(TICKERS)} quotes)")
    elif dry_run:
        print("[DRY-RUN] Output not written to disk.")

    return bundle


def main():
    parser = argparse.ArgumentParser(description="Fetch live quotes for BDRY and BWET ETFs.")
    parser.add_argument("--dry-run", action="store_true", help="Execute without writing to disk.")
    args = parser.parse_args()

    bundle = run_pipeline(dry_run=args.dry_run)
    if len(bundle["quotes"]) == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
