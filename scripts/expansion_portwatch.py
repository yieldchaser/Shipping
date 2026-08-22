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
from datetime import datetime

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


def query_layer(url, params):
    """Paged ArcGIS query; keys off exceededTransferLimit only."""
    out = []
    offset = 0
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
        if not data or 'features' not in data:
            break
        feats = data.get('features') or []
        out.extend(f['attributes'] for f in feats if isinstance(f, dict) and 'attributes' in f)
        if not data.get('exceededTransferLimit'):
            break
        offset += len(feats)
        if len(feats) == 0:
            break
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

    # 'date' is DateOnly (string): plain string comparison, NOT TIMESTAMP
    where = f"date > '{max_date}'" if max_date else "1=1"
    print(f"chokepoint incremental fetch (max existing: {max_date})...")
    attrs = query_layer(CHOKEPOINT_URL, {
        'where': where,
        'outFields': '*',
        'resultRecordCount': 2000,
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

    if max_date and not full:
        # 'date' is DateOnly (string): plain string comparison, NOT TIMESTAMP
        where = f"date > '{max_date}'"
    else:
        where = " OR ".join([f"UPPER(portname) LIKE '%{n}%'" for n in (
            'SHANGHAI', 'SINGAPORE', 'NINGBO', 'SHENZHEN', 'QINGDAO', 'GUANGZHOU',
            'HONG KONG', 'BUSAN', 'ROTTERDAM', 'ANTWERP', 'LOS ANGELES', 'LONG BEACH',
            'SANTOS', 'JEBEL ALI', 'TANJUNG PELEPAS', 'RIZHAO')])
    print("ports incremental fetch...")
    attrs = query_layer(PORTS_DAILY_URL, {
        'where': where,
        'outFields': '*',
        'resultRecordCount': 2000,
        'orderByFields': 'date',
    })
    rows = attrs_to_rows(attrs)
    print(f"fetched {len(rows)} port-call rows")

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
