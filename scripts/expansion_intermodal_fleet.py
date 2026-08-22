#!/usr/bin/env python3
"""
Intermodal (intermodal.gr) Monthly Fleet & Orderbook Collector
==============================================================
Extracts dry-bulk and tanker fleet/orderbook tables from Intermodal's monthly
research PDFs into data/fleet/intermodal_fleet_monthly.csv.

Schema:
    report_month,segment,size_band,fleet_units,orderbook_units,orderbook_pct,
    deliveries_next_year,value_5y_musd,value_10y_musd,nb_price_musd

URL discovery: research/reports pages are scraped for PDFs, with direct
wp-content/uploads/YYYY/MM/ patterns probed as fallback. Last 6 editions per
segment attempted; graceful 404 skip. Requires pypdf (pip install --user pypdf).
"""

import csv
import io
import os
import re
import sys
import time
from datetime import datetime

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO_ROOT, 'data', 'fleet', 'intermodal_fleet_monthly.csv')

FIELDNAMES = ['report_month', 'segment', 'size_band', 'fleet_units', 'orderbook_units',
              'orderbook_pct', 'deliveries_next_year', 'value_5y_musd', 'value_10y_musd',
              'nb_price_musd']

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
}

RESEARCH_PAGES = [
    # NOTE (2026-08): /monthlyreport/ no longer links public PDFs directly
    # (form-gated); probed each run so collection resumes automatically when
    # the reports become publicly reachable again.
    "https://www.intermodal.gr/monthlyreport/",
    "https://www.intermodal.gr/market-insight-week-33/",
]
MAX_EDITIONS_PER_SEGMENT = 6
RETRIES = 3
TIMEOUT = 30


def fetch_with_retry(url):
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
            print(f"[warn] HTTP {r.status_code} for {url[:90]} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        except requests.RequestException as e:
            print(f"[warn] {e} (attempt {attempt}/{RETRIES})", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def discover_pdfs():
    urls = set()
    for page in RESEARCH_PAGES:
        resp = fetch_with_retry(page)
        if resp is None:
            continue
        for m in re.finditer(r'href="([^"]+\.pdf)"', resp.text, re.I):
            u = m.group(1)
            if u.startswith('/'):
                u = 'https://www.intermodal.gr' + u
            if 'intermodal' in u.lower() and ('dry' in u.lower() or 'bulk' in u.lower() or 'tanker' in u.lower()):
                urls.add(u)
    # Direct pattern probe for recent months
    now = datetime.now()
    for back in range(0, MAX_EDITIONS_PER_SEGMENT + 1):
        ym = datetime(now.year, now.month, 1)
        mm = ym.month - back
        yy = ym.year
        while mm <= 0:
            mm += 12
            yy -= 1
        mon = datetime(yy, mm, 1).strftime('%b').lower()
        yr = str(yy)[-2:] if int(str(yy)[-2:]) > 9 else '0' + str(yy)[-1:]
        for seg in ('dry-bulk', 'tanker'):
            urls.add(f"https://www.intermodal.gr/wp-content/uploads/{yy}/{mm:02d}/intermodal-monthly-{seg}-{mon}-{yr}.pdf")
            urls.add(f"https://www.intermodal.gr/wp-content/uploads/{yy}/{mm:02d}/intermodal-monthly-{seg}-{mon}-{yy}.pdf")
    return sorted(urls)


def parse_pdf_tables(content, url):
    """Best-effort extraction of fleet/orderbook rows from the PDF text layer."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("[warn] pypdf not installed - skipping PDF parse (pip install --user pypdf)", file=sys.stderr)
        return []
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or '') for page in reader.pages[:40])
    except Exception as e:
        print(f"[warn] pdf parse failed ({url[:80]}): {e}", file=sys.stderr)
        return []

    segment = 'dry_bulk' if ('dry' in url.lower() or 'bulk' in url.lower()) else 'tankers'
    m = re.search(r'(20\d{2})[-_ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', url.lower())
    report_month = None
    if m:
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        mi = months.index(m.group(2)) + 1
        report_month = f"{m.group(1)}-{mi:02d}-01"

    SIZE_BANDS = {
        'cape': 'Capesize', 'panamax': 'Panamax', 'supramax': 'Supramax',
        'handymax': 'Handymax', 'handysize': 'Handysize', 'ultramax': 'Ultramax',
        'vlcc': 'VLCC', 'suezmax': 'Suezmax', 'aframax': 'Aframax', 'lr2': 'LR2',
        'lr1': 'LR1', 'mr': 'MR', 'handy': 'Handy',
    }
    rows = []
    seen_bands = set()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        low = line.lower()
        for frag, band in SIZE_BANDS.items():
            if frag in low and band not in seen_bands:
                nums = re.findall(r'\d[\d,]*(?:\.\d+)?', line)
                vals = [float(n.replace(',', '')) for n in nums]
                if len(vals) >= 2:
                    row = {k: '' for k in FIELDNAMES}
                    row['report_month'] = report_month or ''
                    row['segment'] = segment
                    row['size_band'] = band
                    row['fleet_units'] = vals[0]
                    row['orderbook_units'] = vals[1] if len(vals) > 1 else ''
                    row['orderbook_pct'] = vals[2] if len(vals) > 2 else ''
                    if len(vals) > 3:
                        row['deliveries_next_year'] = vals[3]
                    if len(vals) > 4:
                        row['value_5y_musd'] = vals[4]
                    if len(vals) > 5:
                        row['value_10y_musd'] = vals[5]
                    if len(vals) > 6:
                        row['nb_price_musd'] = vals[6]
                    rows.append(row)
                    seen_bands.add(band)
                break
        if len(seen_bands) >= len(SIZE_BANDS):
            break
    return rows


def main():
    existing = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                existing[(row['report_month'], row['segment'], row['size_band'])] = row
    before = len(existing)

    urls = discover_pdfs()
    print(f"discovered/probing {len(urls)} candidate PDFs")
    added = 0
    ok = blocked = 0
    per_segment_editions = {}
    for url in urls:
        seg = 'dry_bulk' if ('dry' in url.lower() or 'bulk' in url.lower()) else 'tankers'
        if per_segment_editions.get(seg, 0) >= MAX_EDITIONS_PER_SEGMENT:
            continue
        resp = fetch_with_retry(url)
        if resp is None:
            continue
        parsed = parse_pdf_tables(resp.content, url)
        if not parsed:
            blocked += 1
            continue
        ok += 1
        per_segment_editions[seg] = per_segment_editions.get(seg, 0) + 1
        for row in parsed:
            key = (row['report_month'], row['segment'], row['size_band'])
            if key[0] and key not in existing:
                existing[key] = row
                added += 1

    if ok == 0:
        print(f"[BLOCKED/FORMAT-CHANGED] no PDFs parsed ({blocked} failures); human follow-up needed", file=sys.stderr)

    rows = sorted(existing.values(), key=lambda r: (r['report_month'], r['segment'], r['size_band']))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    import shutil as _sh
    _sh.move(tmp, OUT_PATH)
    print(f"[ok] intermodal_fleet_monthly.csv: +{added} rows ({len(rows)} total)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
