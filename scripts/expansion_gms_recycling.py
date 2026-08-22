#!/usr/bin/env python3
"""
GMS Ship Recycling Weekly Collector
===================================
Weekly $/LDT demolition rates by country (dry/tanker/container) from GMS
(gmsinc.net) into data/recycling/gms_recycling_weekly.csv.

Schema:
    week_date,dry_india,dry_pak,dry_bangla,dry_turkey,
    tanker_india,tanker_pak,tanker_bangla,
    ldt_delivered_total,vessels_sold_count,notes

Discovers the latest ~12 weekly market pages from the listing page, parses the
rate grids, upserts by week_date (existing keys never rewritten), missing =
empty string.
"""

import csv
import os
import re
import sys
import time
from datetime import datetime

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO_ROOT, 'data', 'recycling', 'gms_recycling_weekly.csv')

FIELDNAMES = ['week_date', 'dry_india', 'dry_pak', 'dry_bangla', 'dry_turkey',
              'tanker_india', 'tanker_pak', 'tanker_bangla',
              'ldt_delivered_total', 'vessels_sold_count', 'notes']

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# NOTE (2026-08): GMS moved weekly market reports behind the authenticated
# Ship Recycling Portal (/ship-recycling-portal); the old /weekly-market-report/
# listing 404s. We still probe the legacy path plus /news each run so public
# availability is detected automatically when/if it returns.
LISTING_URLS = [
    "https://www.gmsinc.net/weekly-market-report/",
    "https://www.gmsinc.net/news",
]
MAX_PAGES = 12

RETRIES = 3
TIMEOUT = 30


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


def discover_weekly_urls():
    urls = []
    seen = set()
    for listing in LISTING_URLS:
        resp = fetch_with_retry(listing)
        if resp is None:
            continue
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'lxml')
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(' ', strip=True).lower()
            if ('weekly' in href.lower() or 'market-report' in href.lower() or 'weekly' in text) \
                    and href not in seen and href.rstrip('/') != listing.rstrip('/'):
                if href.startswith('/'):
                    href = 'https://www.gmsinc.net' + href
                if href.startswith('http'):
                    seen.add(href)
                    urls.append((href, text))
        if urls:
            break
    if not urls:
        print("[BLOCKED/FAIL] no public weekly listing found (reports moved behind "
              "the GMS Ship Recycling Portal login); human follow-up needed", file=sys.stderr)
    return urls[:MAX_PAGES]


def parse_week_date(text, soup=None):
    """Extract the report week date from page text/title."""
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})', text or '')
    if m:
        for fmt in ('%d %B %Y', '%d %b %Y'):
            try:
                return datetime.strptime(' '.join(m.groups()), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    if soup:
        title = soup.title.get_text() if soup.title else ''
        m2 = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})', title)
        if m2:
            for fmt in ('%d %B %Y', '%d %b %Y'):
                try:
                    return datetime.strptime(' '.join(m2.groups()), fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
    return None


def parse_rates(soup):
    """Parse the rate grid: country rows x dry/tanker/container columns ($/LDT)."""
    rates = {}
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cells = [td.get_text(' ', strip=True) for td in tr.find_all(['td', 'th'])]
            if not cells:
                continue
            joined = ' | '.join(cells).lower()
            nums = []
            for c in cells[1:]:
                m = re.search(r'(\d{3,4})(?:\.\d+)?', c.replace(',', ''))
                if m:
                    nums.append(float(m.group(1)))
            if not nums:
                continue
            if 'india' in joined and 'container' not in joined:
                if 'tanker' in joined and 'dry' not in joined:
                    rates.setdefault('tanker_india', nums[0])
                elif 'dry' in joined or 'container' not in joined:
                    rates.setdefault('dry_india', nums[0])
            if 'pakistan' in joined:
                if 'tanker' in joined:
                    rates.setdefault('tanker_pak', nums[0])
                else:
                    rates.setdefault('dry_pak', nums[0])
            if 'bangladesh' in joined:
                if 'tanker' in joined:
                    rates.setdefault('tanker_bangla', nums[0])
                else:
                    rates.setdefault('dry_bangla', nums[0])
            if 'turkey' in joined:
                rates.setdefault('dry_turkey', nums[0])
    return rates


def parse_ldt_and_sales(soup):
    ldt_total = None
    vessels = None
    text = soup.get_text(' ', strip=True)
    m = re.search(r'([\d,]+)\s*(?:LDT|ldt)\s*(?:delivered|sold)', text)
    if m:
        try:
            ldt_total = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    m2 = re.search(r'(\d{1,3})\s+vessels?\s+(?:sold|reported)', text, re.I)
    if m2:
        vessels = float(m2.group(1))
    return ldt_total, vessels


def main():
    existing = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                existing[row['week_date']] = row
    before = len(existing)

    urls = discover_weekly_urls()
    print(f"discovered {len(urls)} weekly pages")
    added = 0
    for url, link_text in urls:
        resp = fetch_with_retry(url)
        if resp is None:
            continue
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'lxml')
        week = parse_week_date(link_text + ' ' + (soup.get_text(' ', strip=True)[:400] or ''), soup)
        if not week:
            continue
        if week in existing:
            continue
        rates = parse_rates(soup)
        ldt, vessels = parse_ldt_and_sales(soup)
        if not rates:
            continue
        row = {'week_date': week}
        for k in FIELDNAMES[1:]:
            row[k] = ''
        for k, v in rates.items():
            if k in row:
                row[k] = v
        row['ldt_delivered_total'] = ldt if ldt is not None else ''
        row['vessels_sold_count'] = vessels if vessels is not None else ''
        row['notes'] = ''
        existing[week] = row
        added += 1

    rows = [existing[d] for d in sorted(existing)]
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    import shutil as _sh
    _sh.move(tmp, OUT_PATH)
    print(f"[ok] gms_recycling_weekly.csv: {before} -> {len(rows)} weeks (+{added})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
