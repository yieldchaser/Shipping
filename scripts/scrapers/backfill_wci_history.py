"""Backfill REAL Drewry WCI history from the Wayback Machine.

Why this exists: data/indices/drewry_wci_historical.csv held 138 of 145 rows
that were FABRICATED by generate_canonical_wci_history() (see
docs/drewry_wci_fabrication_verdict.md). They were purged 2026-09-29. This
script repopulates the series from the publisher's own archived pages, one
print per week, using fetch_drewry_wci.extract_assessments().

Design:
  * ONE snapshot per ISO week (the earliest capture in that week) - the page
    prints the current week's assessment, so one capture per week is the print.
  * one subprocess-free HTTP fetch at a time, 1s apart, hard timeout;
  * append-only JSONL checkpoint -> --fetch is resumable, never restarts;
  * a torn last line is treated as normal and skipped;
  * NO row is written unless all five core values were parsed from the page.

Usage:
  python3 scripts/scrapers/backfill_wci_history.py --fetch
  python3 scripts/scrapers/backfill_wci_history.py --stack
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time

import requests

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts', 'scrapers'))
from fetch_drewry_wci import extract_assessments  # noqa: E402

CDX = os.path.join(REPO, 'scratch', 'wci_cdx.json')
STATE_DIR = os.path.join(REPO, 'data', 'extracted', 'wci_backfill')
CKPT = os.path.join(STATE_DIR, 'checkpoint.jsonl')
STAGE = os.path.join(REPO, 'data', 'audit', 'drewry_wci_real_rows_from_wayback.csv')
KEYS = ('composite_index', 'shanghai_rotterdam', 'shanghai_genoa', 'shanghai_la', 'shanghai_ny')
COLS = ['date'] + list(KEYS) + ['rotterdam_shanghai', 'source_snapshot']
HDR = {'User-Agent': 'Mozilla/5.0'}


def load_cdx():
    if os.path.exists(CDX):
        with io.open(CDX, encoding='utf-8') as fh:
            return json.load(fh)
    rows = []
    for y in ('2021', '2022', '2023', '2024', '2025', '2026'):
        p = {'url': 'drewry.co.uk/supply-chain-advisors/supply-chain-expertise/'
                    'world-container-index-assessed-by-drewry*',
             'from': y, 'to': y, 'output': 'json',
             'filter': ['statuscode:200', 'mimetype:text/html'],
             'fl': 'timestamp,original', 'collapse': 'digest', 'limit': '500'}
        try:
            r = requests.get('https://web.archive.org/cdx/search/cdx', params=p, timeout=90)
            d = json.loads(r.text)
            rows += (d[1:] if d else [])
        except Exception as exc:
            print('CDX', y, 'failed:', exc)
        time.sleep(1)
    os.makedirs(os.path.dirname(CDX), exist_ok=True)
    with io.open(CDX, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(rows))
    return rows


def one_per_week(rows):
    """Earliest capture in each ISO (year, week)."""
    best = {}
    for ts, orig in rows:
        d = dt.datetime.strptime(ts[:8], '%Y%m%d').date()
        key = d.isocalendar()[:2]
        if key not in best or ts < best[key][0]:
            best[key] = (ts, orig)
    return sorted(best.values())


def load_done():
    done = set()
    if not os.path.exists(CKPT):
        return done
    with io.open(CKPT, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue          # torn last line from a crash - normal
            if rec.get('ts'):
                done.add(rec['ts'])
    return done


def do_fetch(sleep_s=1.0):
    os.makedirs(STATE_DIR, exist_ok=True)
    snaps = one_per_week(load_cdx())
    done = load_done()
    todo = [s for s in snaps if s[0] not in done]
    print('[+] snapshots: %d total, %d already done, %d to fetch'
          % (len(snaps), len(done), len(todo)))
    ok = 0
    with io.open(CKPT, 'a', encoding='utf-8', newline='') as out:
        for i, (ts, orig) in enumerate(todo, 1):
            url = 'https://web.archive.org/web/%sid_/%s' % (ts, orig)
            rec = {'ts': ts}
            try:
                r = requests.get(url, headers=HDR, timeout=90)
                if r.status_code != 200:
                    rec['error'] = 'HTTP %d' % r.status_code
                else:
                    v, pdate, _ = extract_assessments(r.text)
                    rec['page_date'] = pdate
                    rec['values'] = {k: v.get(k) for k in KEYS + ('rotterdam_shanghai',)}
                    have = all(rec['values'].get(k) for k in KEYS)
                    rec['complete'] = bool(have)
                    ok += 1 if have else 0
            except Exception as exc:
                rec['error'] = '%s: %s' % (type(exc).__name__, exc)
            out.write(json.dumps(rec) + '\n')
            out.flush()
            if i % 10 == 0 or i == len(todo):
                print('    %d/%d  complete=%d  last=%s' % (i, len(todo), ok, ts), flush=True)
            time.sleep(sleep_s)
    print('[OK] fetch pass done: %d complete rows in checkpoint' % ok)


def do_stack():
    rows = {}
    withheld = 0
    with io.open(CKPT, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not rec.get('complete') or not rec.get('page_date'):
                continue
            # GATES. (1) era: prose shapes before 2023 were NOT trialed - the
            # 2021 captures parse to garbage (a route value of 78) and are
            # withheld rather than guessed. (2) numeric: the four Shanghai
            # routes are one trade family, so their spread is bounded, and the
            # composite is a weighted average of them.
            if rec['page_date'] < '2023-01-01':
                continue
            core = [rec['values'].get(k) for k in KEYS[1:]]
            if any((c is None or c <= 0) for c in core):
                continue
            if max(core) / min(core) > 5.0:
                continue
            comp = rec['values'].get('composite_index')
            if not comp or not (0.35 * min(core) <= comp <= 2.5 * max(core)):
                continue
            # (3) contamination tells measured on the staged set: a value with two
            # decimals is a methodology number, not a printed level, and a route
            # value equal to the composite means the parser grabbed the headline.
            # Both are 0 on the 7 known-real rows and 0 on the 138 synthetic ones.
            raws = [rec['values'].get(k) for k in KEYS] + [rec['values'].get('rotterdam_shanghai')]
            if any((str(x).rstrip('0').rstrip('.').split('.')[-1] != '0' and '.' in str(x)
                    and len(str(x).split('.')[1]) > 1) for x in raws if x is not None):
                continue
            if any(abs(comp - c) < 0.01 for c in core):
                continue
            # (4) ERA GATE: 2023-2025 rows still mis-assign a route on some 2024
            # prose shapes (2024-04-18 gives Genoa 2291 where the page prints
            # 3577), so they are counted but WITHHELD from the displayed file
            # until that shape is fixed. 2026 rows are md-verified 3/3.
            rec['_ship'] = rec['page_date'] >= '2026-01-01'
            v = rec['values']
            d = rec['page_date']
            if not rec.get('_ship'):
                withheld += 1
                continue
            if d not in rows or rec['ts'] < rows[d]['source_snapshot']:
                rows[d] = {'date': d}
                rows[d].update({k: v.get(k) for k in KEYS + ('rotterdam_shanghai',)})
                rows[d]['source_snapshot'] = rec['ts']
    os.makedirs(os.path.dirname(STAGE), exist_ok=True)
    with io.open(STAGE, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator='\n')
        w.writeheader()
        for d in sorted(rows):
            w.writerow(rows[d])
    print('[OK] staged %d SHIPPABLE real prints -> %s (%d withheld as unverified era)'
          % (len(rows), STAGE, withheld))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--stack', action='store_true')
    ap.add_argument('--sleep', type=float, default=1.0)
    a = ap.parse_args()
    if a.fetch:
        do_fetch(a.sleep)
    if a.stack:
        do_stack()
    if not a.fetch and not a.stack:
        ap.print_help()
