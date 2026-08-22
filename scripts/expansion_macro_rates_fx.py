#!/usr/bin/env python3
"""
Macro Rates & FX Collector
==========================
Daily USD-base FX (ECB reference rates, inverted from EUR base) and US rates
(FRED: SOFR, DGS2, DGS5, DGS10) into data/macro/rates_fx.csv.

Schema:
    date,usd_cny,usd_jpy,usd_inr,usd_krw,usd_try,eur_usd,sofr,dgs2,dgs5,dgs10

Conventions: ISO dates; missing = empty string (never 0); merge-fill of empty
fields only on re-run (non-empty values never rewritten); retry x3 backoff;
graceful per-source failure. NOTE: FRED returns 520 to browser-like
User-Agents from some hosts but 200 to the default python-requests UA — no
custom UA is sent for FRED.
"""

import csv
import io
import os
import sys
import time
from datetime import datetime

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO_ROOT, 'data', 'macro', 'rates_fx.csv')

FIELDNAMES = ['date', 'usd_cny', 'usd_jpy', 'usd_inr', 'usd_krw', 'usd_try', 'eur_usd',
              'sofr', 'dgs2', 'dgs5', 'dgs10']

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
}

FRED_SERIES = ['SOFR', 'DGS2', 'DGS5', 'DGS10']

RETRIES = 3
TIMEOUT = 30


def fetch_with_retry(url, headers=None):
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            print(f"[warn] HTTP {r.status_code} for {url[:80]} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        except requests.RequestException as e:
            print(f"[warn] {e} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def fetch_ecb_fx():
    """ECB daily reference rates (EUR base). Returns {iso_date: {slug: value}} in USD base."""
    url = ("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip")
    import zipfile
    resp = fetch_with_retry(url, headers=BROWSER_HEADERS)
    if resp is None:
        return {}
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    name = z.namelist()[0]
    text = z.read(name).decode('utf-8')
    reader = csv.DictReader(text.splitlines())

    # ECB columns: Date, USD, CNY, JPY, INR, KRW, TRY, ... (EUR base: 1 EUR = X)
    wanted = {'CNY': 'usd_cny', 'JPY': 'usd_jpy', 'INR': 'usd_inr',
              'KRW': 'usd_krw', 'TRY': 'usd_try', 'USD': 'eur_usd'}
    out = {}
    for row in reader:
        raw_date = (row.get('Date') or '').strip()
        if not raw_date:
            continue
        try:
            iso = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            continue
        rec = {}
        usd_per_eur = None
        try:
            v = (row.get('USD') or '').strip()
            if v and v != 'N/A':
                usd_per_eur = float(v)
        except ValueError:
            pass
        for cur, slug in wanted.items():
            try:
                val = (row.get(cur) or '').strip()
                if not val or val == 'N/A':
                    continue
                fval = float(val)
                if fval <= 0:
                    continue
                if cur == 'USD':
                    # eur_usd column stores the EUR/USD quote directly
                    rec[slug] = round(fval, 6)
                elif usd_per_eur:
                    # invert to USD base: 1 USD = cur / usd_per_eur
                    rec[slug] = round(fval / usd_per_eur, 6)
            except (ValueError, ZeroDivisionError):
                continue
        if rec:
            out[iso] = rec
    return out


def fetch_fred_series(series_id):
    """FRED CSV: header observation_date,<SERIES>; '.' = missing."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    # Deliberately default UA: Cloudflare 520s browser UAs from some hosts.
    resp = fetch_with_retry(url, headers=None)
    if resp is None:
        return {}
    out = {}
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        ds = (row.get('observation_date') or '').strip()
        raw = (row.get(series_id) or '').strip()
        if not ds or not raw or raw == '.':
            continue
        try:
            out[ds] = round(float(raw), 6)
        except ValueError:
            continue
    return out


def main():
    existing = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                existing[row['date']] = row
    before = len(existing)

    fx = fetch_ecb_fx()
    print(f"ECB FX dates fetched: {len(fx)}")

    fred = {}
    for series in FRED_SERIES:
        got = fetch_fred_series(series)
        slug = series.lower().replace('dgs', 'dgs')
        fred[slug] = got
        print(f"FRED {series}: {len(got)} observations")

    all_dates = sorted(set(existing.keys()) | set(fx.keys()) | set(k for m in fred.values() for k in m))
    merged = 0
    for d in all_dates:
        row = existing.get(d, {'date': d})
        changed = False
        src_fx = fx.get(d, {})
        for slug, val in src_fx.items():
            if not row.get(slug):
                row[slug] = val
                changed = True
        for slug, series_map in fred.items():
            val = series_map.get(d)
            if val is not None and not row.get(slug):
                row[slug] = val
                changed = True
        if changed or d not in existing:
            existing[d] = row
            merged += 1

    rows = []
    for d in sorted(existing.keys()):
        row = existing[d]
        rows.append({k: row.get(k, '') or '' for k in FIELDNAMES})

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    import shutil as _sh
    _sh.move(tmp, OUT_PATH)
    print(f"[ok] rates_fx.csv: {before} -> {len(rows)} date keys (+{merged} new/updated)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
