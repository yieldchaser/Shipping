#!/usr/bin/env python3
"""
SGX FFA Full-History Backfill Collector
========================================
Backfills complete contract lives for SGX dry-bulk FFA futures (Cape/Panamax/
Supramax/Handysize) into data/futures/sgx_{class}_futures_history.csv.

Schema matches the live files written by update_indices.py:
    contract,expiry_month,expiry_year,date,price,volume,expiry_date
Dates DD-MM-YYYY, expiry_month as 'Mar 2026', missing price = empty string
(never 0), volumes kept as floats. Idempotent: existing (contract, date) keys
are skipped; output sorted chronologically.

API notes (verified):
- No real pagination: meta.totalPages is always 0; the endpoint returns the
  contract's entire life in one response. Defensive offset paging keyed off
  meta.totalPages > 1 is coded anyway but never triggers in practice.
- days=N means 'last N rows', anchored at expiry (expired) or today (live).
  days=2200d captures full contract lives.
"""

import csv
import os
import sys
import time
from datetime import datetime, date

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SGX_PRODUCTS = {
    'CWF': os.path.join(REPO_ROOT, 'data', 'futures', 'sgx_cape_futures_history.csv'),
    'PWF': os.path.join(REPO_ROOT, 'data', 'futures', 'sgx_panamax_futures_history.csv'),
    'SWF': os.path.join(REPO_ROOT, 'data', 'futures', 'sgx_supramax_futures_history.csv'),
    'HWF': os.path.join(REPO_ROOT, 'data', 'futures', 'sgx_handysize_futures_history.csv'),
}

CME_MONTHS = {
    'F': (1,  'Jan'), 'G': (2,  'Feb'), 'H': (3,  'Mar'),
    'J': (4,  'Apr'), 'K': (5,  'May'), 'M': (6,  'Jun'),
    'N': (7,  'Jul'), 'Q': (8,  'Aug'), 'U': (9,  'Sep'),
    'V': (10, 'Oct'), 'X': (11, 'Nov'), 'Z': (12, 'Dec'),
}

SGX_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Referer': 'https://www.sgx.com/',
    'Origin': 'https://www.sgx.com',
    'Accept': 'application/json',
}

FIELDNAMES = ['contract', 'expiry_month', 'expiry_year', 'date', 'price', 'volume', 'open_interest', 'expiry_date']

SESSION = requests.Session()
RETRIES = 3
TIMEOUT = 30


def get_expiry(month_num, year):
    """Last calendar day of the contract month, walked back to a weekday."""
    from calendar import monthrange
    d = date(year, month_num, monthrange(year, month_num)[1])
    while d.weekday() >= 5:
        d = date.fromordinal(d.toordinal() - 1)
    return d


def generate_all_tickers(product_code, start_year=2017):
    """All month tickers from start_year through next year (expired included)."""
    now = datetime.now()
    tickers = []
    for year in range(start_year, now.year + 2):
        year2 = str(year)[-2:]
        for code, (month_num, month_name) in CME_MONTHS.items():
            expiry = get_expiry(month_num, year)
            tickers.append((f"{product_code}{code}{year2}", month_num, year, month_name,
                            expiry.strftime('%d-%m-%Y'), expiry))
    return tickers


def fetch_with_retry(url):
    for attempt in range(1, RETRIES + 1):
        try:
            r = SESSION.get(url, headers=SGX_HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 410):
                return None
            print(f"    [warn] HTTP {r.status_code} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        except requests.RequestException as e:
            print(f"    [warn] {e} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def fetch_contract_history(ticker):
    """Fetch the contract's entire life. Returns list of row dicts (may be empty).

    Verified 2026-08-22 against the live API: SGX publishes a real
    daily-settlement-price only on sessions where the contract actually
    cleared (7 traded days for CWFZ25's whole life); every other session
    carries price=0 while volume and open-interest remain fully populated,
    including the 2025 lookback window where prices are redacted server-side.
    We therefore store all three series verbatim - the zeros are the truth.
    """
    url = (f"https://api.sgx.com/derivatives/v1.0/history/symbol/{ticker}"
           f"?days=2200d&category=futures"
           f"&params=base-date%2Ctotal-volume%2Cdaily-settlement-price-abs"
           f"%2Copen-interest")
    payload = fetch_with_retry(url)
    if not payload:
        return []
    rows_out = []
    data = payload.get('data') or []
    meta = payload.get('meta') or {}
    # Defensive offset paging (never triggers: meta.totalPages is always 0)
    if meta.get('totalPages', 0) and meta.get('totalPages', 0) > 1:
        print(f"    [info] {ticker}: server reports {meta.get('totalPages')} pages", file=sys.stderr)
    for entry in data:
        base_date = entry.get('base-date')
        if not base_date:
            continue
        try:
            d = datetime.strptime(str(base_date), '%Y%m%d')
        except ValueError:
            continue
        price = entry.get('daily-settlement-price-abs')
        volume = entry.get('total-volume')
        oi = entry.get('open-interest')
        rows_out.append({'_date': d, 'price': price, 'volume': volume, 'open_interest': oi})
    return rows_out


def earliest_data_year(existing):
    """Earliest contract-expiry year holding any nonzero settlement price.

    The SGX history API serves real settlement PRICES only for sessions where
    the contract actually cleared; for contracts expiring before ~Jan 2024
    every price field reads 0 forever (verified across all four products on
    2026-08-22), and even post-2024 expiries carry only ~7 traded-day prices
    per life. Volume and open-interest ARE served full-depth back to 2022
    regardless. The daily refresh uses this floor purely to skip wasted
    probes; --rebuild bypasses it to capture full-depth volume/OI.
    Returns None when unknown (no file / no priced rows yet) -> probe all.
    """
    years = []
    for row in existing.values():
        try:
            if float(row.get('price') or 0) > 0 and row.get('expiry_year'):
                years.append(int(row['expiry_year']))
        except (TypeError, ValueError):
            continue
    return min(years) if years else None


def upsert_product(product_code, out_path, rebuild=False):
    existing = {}
    if os.path.exists(out_path) and not rebuild:
        with open(out_path, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                existing[(row['contract'], row['date'])] = row
    before = len(existing)

    # Daily refreshes skip pre-floor tickers (their PRICES are zero-filled
    # upstream). --rebuild probes everything instead: volume and open-interest
    # ARE served full-depth back to 2022 even where prices are redacted.
    floor_year = None if rebuild else earliest_data_year(existing)
    if floor_year:
        print(f"  [{product_code}] probing contracts expiring {floor_year}+ "
              f"(older tickers have no settlement data upstream)")
    elif rebuild:
        print(f"  [{product_code}] REBUILD: probing all contracts "
              f"(volume/open-interest exist pre-floor even where prices do not)")
    floor_cutoff = date(floor_year, 1, 1) if floor_year else None

    tickers = generate_all_tickers(product_code)
    new_rows = []
    fetched = 0
    skipped = 0
    for ticker, month_num, year, month_name, expiry_str, expiry in tickers:
        if floor_cutoff and expiry < floor_cutoff:
            skipped += 1
            continue
        entries = fetch_contract_history(ticker)
        fetched += 1
        if fetched % 40 == 0:
            print(f"  [{product_code}] {fetched}/{len(tickers)} contracts probed "
                  f"({skipped} skipped pre-floor), {len(new_rows)} new rows")
        for e in entries:
            key = (ticker, e['_date'].strftime('%d-%m-%Y'))
            if key in existing:
                continue
            new_rows.append({
                'contract': ticker,
                'expiry_month': f"{month_name} {year}",
                'expiry_year': str(year),
                'date': key[1],
                'price': '' if e['price'] is None else str(float(e['price'])),
                'volume': '' if e['volume'] is None else str(float(e['volume'])),
                'open_interest': '' if e.get('open_interest') is None else str(float(e['open_interest'])),
                'expiry_date': expiry_str,
                '_dt': e['_date'],
            })

    if not new_rows:
        print(f"[ok] {product_code}: 0 new rows ({before} existing)")
        return 0

    all_rows = []
    for row in existing.values():
        try:
            row['_dt'] = datetime.strptime(row['date'], '%d-%m-%Y')
        except ValueError:
            row['_dt'] = datetime.min
        all_rows.append(row)
    all_rows.extend(new_rows)
    all_rows.sort(key=lambda r: (r['_dt'], r.get('contract', '')))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    os.replace(tmp, out_path)
    print(f"[ok] {product_code}: +{len(new_rows)} rows -> {os.path.relpath(out_path, REPO_ROOT)} ({len(all_rows)} total)")
    return len(new_rows)


def main():
    rebuild = '--rebuild' in sys.argv
    if rebuild:
        print("[rebuild] probing every ticker and regenerating archives "
              "(schema migrations / full-depth volume+OI recovery)")
    total = 0
    for product_code, out_path in SGX_PRODUCTS.items():
        try:
            total += upsert_product(product_code, out_path, rebuild=rebuild)
        except Exception as e:
            print(f"[FAIL] {product_code}: {e}", file=sys.stderr)
    print(f"SGX history backfill complete: +{total} rows")
    return 0


if __name__ == '__main__':
    sys.exit(main())
