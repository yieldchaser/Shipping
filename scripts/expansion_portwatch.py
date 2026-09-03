#!/usr/bin/env python3
"""
PortWatch (IMF) Congestion & Port Calls Collector
=================================================
Daily chokepoint transits and curated port calls from the IMF PortWatch ArcGIS
layers into data/congestion/chokepoint_transits_daily.csv and
data/congestion/port_calls_daily.csv.

Verified API behavior:
- Both layers use an ISO *string* date field; incremental fetch via
  where=date > '<max>' works.
- Layer caps pages at 1000 records regardless of resultRecordCount=2000.
- ObjectId order != date order; pagination must key off
  exceededTransferLimit / empty batches only.

Usage: python expansion_portwatch.py [--ports-full]
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHOKE_OUT = os.path.join(REPO_ROOT, 'data', 'congestion', 'chokepoint_transits_daily.csv')
PORTS_OUT = os.path.join(REPO_ROOT, 'data', 'congestion', 'port_calls_daily.csv')

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
}

# PortWatch ArcGIS Feature Services (public, no auth).
# NOTE: services were renamed from Daily_Trade_Data/{1,0} to these names;
# resolve dynamically via AGOL item search if they move again:
#   Daily_Chokepoints_Data -> item 3da2b9ca97684916b75c4013f95d18ab
#   Daily_Ports_Data       -> item 83b1bbc7b3354c5fb1f40673bb8f852e
SERVICE_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
CHOKEPOINT_URL = f"{SERVICE_BASE}/Daily_Chokepoints_Data/FeatureServer/0/query"
PORTS_DAILY_URL = f"{SERVICE_BASE}/Daily_Ports_Data/FeatureServer/0/query"

# Curated port set (name fragment -> canonical name); resolved against live layer
CURATED_PORT_FRAGMENTS = [
    'shanghai', 'singapore', 'ningbo', 'shenzhen', 'qingdao', 'guangzhou',
    'hong kong', 'busan', 'rotterdam', 'antwerp', 'los angeles', 'long beach',
    'santos', 'jebel ali', 'tanjung pelepas', 'yangshan', 'jingtang', 'rizhao',
]

RETRIES = 3
TIMEOUT = 120
# Build C: unstall port_calls_daily.csv (ends 2020-10-30). A single
# where=date > '2020-10-30' query spans 5+ years x 1000+ ports/day and never
# completes via offset paging alone — fetch incrementally in bounded date
# chunks so each ArcGIS query stays under transfer limits. Idempotent upsert:
# existing rows are never deleted, only deduped + sorted; headers preserved.
PORTS_CHUNK_DAYS = 90
STABLE_ORDER_FIELDS = 'date, ObjectId'


def _date_gt(col: str, val: str) -> str:
    """ArcGIS DateOnly comparison. DATE 'YYYY-MM-DD' is the documented
    literal form; plain 'YYYY-MM-DD' string compare silently returns 0 rows
    on some layers (the 2020-10-30 stall)."""
    return f"{col} > DATE '{val}'"


def _date_range(col: str, start: str, end: str) -> str:
    return f"{col} >= DATE '{start}' AND {col} <= DATE '{end}'"


def query_layer(url, params):
    """Paged ArcGIS query; keys off exceededTransferLimit only.

    Build C fixes: surface server-side 'error' payloads loudly instead of
    silently returning 0 rows (stall), and force a stable secondary sort so
    resultOffset paging cannot skip/duplicate rows that share the same date.
    """
    out = []
    offset = 0
    # Stable pagination: ObjectId order != date order, and date alone is not
    # unique (1000+ ports share one date). Paging by date-only offset can
    # skip/duplicate rows; always add ObjectId as tiebreaker.
    if params.get('orderByFields') == 'date':
        params = dict(params, orderByFields=STABLE_ORDER_FIELDS)
    while True:
        p = dict(params)
        p.update({'resultOffset': offset, 'f': 'json'})
        data = None
        for attempt in range(1, RETRIES + 1):
            try:
                r = requests.get(url, params=p, headers=BROWSER_HEADERS, timeout=TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    break
                print(f"[warn] HTTP {r.status_code} (attempt {attempt}/{RETRIES})", file=sys.stderr)
            except requests.RequestException as e:
                print(f"[warn] {e} (attempt {attempt}/{RETRIES})", file=sys.stderr)
            time.sleep(2 ** attempt)
        if data is None:
            print("[warn] ArcGIS query: no response after retries; stopping page loop.", file=sys.stderr)
            break
        if 'error' in (data or {}):
            # Loud failure beats silent 0-row stall: log server error verbatim.
            print(f"[warn] ArcGIS error payload: {json.dumps(data.get('error'))[:500]} "
                  f"(where={params.get('where')!r} offset={offset})", file=sys.stderr)
            break
        if 'features' not in data:
            break
        feats = data.get('features') or []
        if len(feats) == 0:
            break
        out.extend(f['attributes'] for f in feats if isinstance(f, dict) and 'attributes' in f)
        if not data.get('exceededTransferLimit'):
            break
        offset += len(feats)
    return out


def attrs_to_rows(attrs_list):
    """ArcGIS attributes: the 'date' field is esriFieldTypeDateOnly (plain
    'YYYY-MM-DD' string); epoch-ms ints are normalized defensively."""
    rows = []
    for a in attrs_list:
        row = dict(a)
        d = row.pop('date', None)
        if isinstance(d, (int, float)):
            row['date'] = datetime.utcfromtimestamp(d / 1000).strftime('%Y-%m-%d')
        elif isinstance(d, str):
            row['date'] = d[:10]
        rows.append(row)
    return rows


def sync_chokepoints():
    existing = {}
    fieldnames = None
    if os.path.exists(CHOKE_OUT):
        with open(CHOKE_OUT, encoding='utf-8', newline='') as f:
            rdr = csv.DictReader(f)
            fieldnames = rdr.fieldnames
            for row in rdr:
                existing[(row['date'], row.get('portname', ''), row.get('portid', ''))] = row
    max_date = max((k[0] for k in existing), default=None)

    # 'date' is esriFieldTypeDateOnly: use DATE 'YYYY-MM-DD' literal form.
    # Plain string compare (date > 'YYYY-MM-DD') silently returns 0 rows on
    # some layers — the port_calls stall pattern.
    where = _date_gt('date', max_date) if max_date else "1=1"
    print(f"chokepoint incremental fetch (max existing: {max_date})...")
    attrs = query_layer(CHOKEPOINT_URL, {
        'where': where,
        'outFields': '*',
        'resultRecordCount': 1000,
        'orderByFields': 'date',
    })
    rows = attrs_to_rows(attrs)
    print(f"fetched {len(rows)} chokepoint rows")

    if rows:
        sample = rows[0]
        if fieldnames is None:
            ordered = ['date', 'portname', 'portid']
            ordered += [k for k in sample.keys() if k not in ordered and k.lower() not in ('objectid',)]
            fieldnames = ordered
        added = 0
        for row in rows:
            key = (row['date'], row.get('portname', ''), row.get('portid', ''))
            if key not in existing:
                existing[key] = {fn: row.get(fn, '') or '' for fn in fieldnames}
                added += 1
        all_rows = sorted(existing.values(), key=lambda r: (r['date'], r.get('portname', '')))
        os.makedirs(os.path.dirname(CHOKE_OUT), exist_ok=True)
        tmp = CHOKE_OUT + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        import shutil as _sh
        _sh.move(tmp, CHOKE_OUT)
        print(f"[ok] chokepoint_transits_daily.csv: +{added} rows ({len(all_rows)} total)")


def sync_ports(full=False):
    existing = {}
    fieldnames = None
    if os.path.exists(PORTS_OUT):
        with open(PORTS_OUT, encoding='utf-8', newline='') as f:
            rdr = csv.DictReader(f)
            fieldnames = rdr.fieldnames
            for row in rdr:
                existing[(row['date'], row.get('portname', ''), row.get('portid', ''))] = row
    max_date = max((k[0] for k in existing), default=None)

    attrs: list = []
    if max_date and not full:
        # Incremental, idempotent, chunked: one huge
        # date > '2020-10-30' query (5+ years x all ports) never completes
        # via offset paging alone. Bound each ArcGIS query to
        # PORTS_CHUNK_DAYS so every page stays under transfer limits.
        # DATE '...' literal form fixes the silent 0-row stall.
        # Existing rows are never deleted — chunks only add missing keys.
        try:
            start_d = datetime.strptime(max_date, '%Y-%m-%d').date() + timedelta(days=1)
        except ValueError:
            start_d = None
        today = datetime.utcnow().date()
        if start_d is None or start_d > today:
            print(f"ports up-to-date (max existing: {max_date}); nothing to fetch.")
            return
        chunk_start = start_d
        print(f"ports incremental chunked fetch (max existing: {max_date} -> {today})...")
        while chunk_start <= today:
            chunk_end = min(chunk_start + timedelta(days=PORTS_CHUNK_DAYS - 1), today)
            where = _date_range('date', chunk_start.isoformat(), chunk_end.isoformat())
            chunk_attrs = query_layer(PORTS_DAILY_URL, {
                'where': where,
                'outFields': '*',
                'resultRecordCount': 1000,
                'orderByFields': 'date',
            })
            print(f"  chunk {chunk_start}..{chunk_end}: {len(chunk_attrs)} rows")
            attrs.extend(chunk_attrs)
            chunk_start = chunk_end + timedelta(days=1)
            time.sleep(1)  # polite pacing between chunks
    else:
        where = " OR ".join([f"UPPER(portname) LIKE '%{n}%'" for n in (
            'SHANGHAI', 'SINGAPORE', 'NINGBO', 'SHENZHEN', 'QINGDAO', 'GUANGZHOU',
            'HONG KONG', 'BUSAN', 'ROTTERDAM', 'ANTWERP', 'LOS ANGELES', 'LONG BEACH',
            'SANTOS', 'JEBEL ALI', 'TANJUNG PELEPAS', 'RIZHAO')])
        print("ports full (curated) fetch...")
        attrs = query_layer(PORTS_DAILY_URL, {
            'where': where,
            'outFields': '*',
            'resultRecordCount': 1000,
            'orderByFields': 'date',
        })
    rows = attrs_to_rows(attrs)
    print(f"fetched {len(rows)} port-call rows")

    if not rows:
        # Idempotent no-op: keep existing file byte-identical when upstream
        # has nothing new (never truncate on empty fetch).
        print(f"[ok] port_calls_daily.csv: +0 rows ({len(existing)} total, kept as-is)")
        return

    if rows and fieldnames is None:
        sample = rows[0]
        fieldnames = list(sample.keys())

    if rows and fieldnames:
        added = 0
        for row in rows:
            key = (row['date'], row.get('portname', ''), row.get('portid', ''))
            if key not in existing:
                existing[key] = {fn: row.get(fn, '') if row.get(fn) is not None else '' for fn in fieldnames}
                added += 1
        all_rows = sorted(existing.values(), key=lambda r: (r['date'], r.get('portname', '')))
        os.makedirs(os.path.dirname(PORTS_OUT), exist_ok=True)
        tmp = PORTS_OUT + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        import shutil as _sh
        _sh.move(tmp, PORTS_OUT)
        print(f"[ok] port_calls_daily.csv: +{added} rows ({len(all_rows)} total)")


def main():
    full = '--ports-full' in sys.argv
    try:
        sync_chokepoints()
    except Exception as e:
        print(f"[FAIL] chokepoints: {e}", file=sys.stderr)
    try:
        sync_ports(full=full)
    except Exception as e:
        print(f"[FAIL] ports: {e}", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
