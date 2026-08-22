#!/usr/bin/env python3
"""
Ship & Bunker Fuel Price Collector
==================================
Daily global-average and key-port bunker prices (VLSFO, MGO, IFS380) from
shipandbunker.com into data/bunkers/bunker_prices_daily.csv.

Schema:
    date,port,fuel_grade,price_usd_mt

Forward-accumulating daily snapshots: appends today's snapshot when a new date
key appears. Idempotent (existing date+port+grade keys never rewritten).
Graceful failure on layout changes / blocks with a stderr summary.
"""

import csv
import os
import re
import sys
import time
from datetime import datetime

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bunker_prices_daily.csv')

FIELDNAMES = ['date', 'port', 'fuel_grade', 'price_usd_mt']

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# The global prices page embeds all 14 tracked ports/regions x 3 grades in
# tabbed tables; hub pages 404 under the current URL scheme and are redundant.
PAGES = [
    ('global_average', 'https://shipandbunker.com/prices'),
]

RETRIES = 3
TIMEOUT = 30


GRADE_TOKENS = ('VLSFO', 'MGO', 'IFO380')


def fetch_with_retry(url):
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            print(f"[warn] HTTP {r.status_code} for {url[:80]} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        except requests.RequestException as e:
            print(f"[warn] {e} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def parse_price_cell(cell_text):
    m = re.search(r'([\d,]+(?:\.\d+)?)', cell_text or '')
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _grade_for_table(table):
    """Fuel grade from the nearest preceding heading (verified layout:
    every table shares the generic header 'Port | Price $/mt | Change | ...';
    the grade lives in the section heading above each table)."""
    prev = table
    for _ in range(12):
        prev = prev.find_previous(['h1', 'h2', 'h3', 'h4'])
        if prev is None:
            return None
        txt = (prev.get_text(' ', strip=True) or '').upper()
        for g in GRADE_TOKENS:
            if g in txt:
                return g
    return None


def parse_page(html, port):
    """Verified layout (shipandbunker.com/prices): grades are jQuery-UI tabs —
    <div id="overview-tabs"><ul class="products"> with anchors #_VLSFO/#_MGO/
    #_IFO380, each panel div id="_GRADE" containing one prices table
    ('Port | Price $/mt | Change | High | Low | Spread')."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    out = []
    today = datetime.utcnow().strftime('%Y-%m-%d')

    panels = []
    for g in GRADE_TOKENS:
        panel = soup.find('div', id=f'_{g}')
        if panel is not None:
            panels.append((g, panel))

    for grade, panel in panels:
        for table in panel.find_all('table'):
            headers = [th.get_text(' ', strip=True) for th in table.find_all('th')]
            if not headers or 'port' not in headers[0].lower():
                continue
            try:
                price_j = next(i for i, h in enumerate(headers) if 'price' in h.lower())
            except StopIteration:
                continue
            for tr in table.find_all('tr'):
                # Port label is a <th>, prices are <td>s in one combined grid
                all_cells = tr.find_all(['th', 'td'])
                if len(all_cells) <= price_j:
                    continue
                name = all_cells[0].get_text(' ', strip=True)
                if not name or name.lower() == 'port':
                    continue
                px = parse_price_cell(all_cells[price_j].get_text(' ', strip=True))
                if px is None or not (10 < px < 2000):
                    continue
                row_port = name.lower().replace(' ', '_') if port == 'global_average' else port
                if not row_port:
                    continue
                out.append({'date': today, 'port': row_port, 'fuel_grade': grade,
                            'price_usd_mt': px})
    return out


def main():
    existing = set()
    rows_existing = []
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                rows_existing.append(row)
                existing.add((row['date'], row['port'], row['fuel_grade']))
    before = len(rows_existing)

    added = 0
    for port, url in PAGES:
        resp = fetch_with_retry(url)
        if resp is None:
            print(f"[BLOCKED/FAIL] {port}: unreachable", file=sys.stderr)
            continue
        parsed = parse_page(resp.text, port)
        if not parsed:
            print(f"[FORMAT-CHANGED] {port}: no price rows recognized", file=sys.stderr)
            continue
        for row in parsed:
            key = (row['date'], row['port'], row['fuel_grade'])
            if key not in existing:
                rows_existing.append(row)
                existing.add(key)
                added += 1
        print(f"[ok] {port}: {len(parsed)} price cells parsed")

    rows_existing.sort(key=lambda r: (r['date'], r['port'], r['fuel_grade']))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_existing)
    import shutil as _sh
    _sh.move(tmp, OUT_PATH)
    print(f"[ok] bunker_prices_daily.csv: {before} -> {len(rows_existing)} rows (+{added})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
