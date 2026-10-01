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
RAW_DIR = os.path.join(REPO, 'scratch', 'wci', 'raw')  # local HTML cache (gitignored)
PARSER_VERSION = 17  # 17=TWO PARALLEL `respectively` LISTS in ONE sentence are split AT THEIR OWN MARKER: each list part maps its labels to its values positionally, so a part holding two tracked lanes no longer hands both of them that list's FIRST value (2024-12-19: "rates from Shanghai to Genoa and Rotterdam to Shanghai decreased 2% to $5,424 per feu and $508 per feu, respectively, and those from New York to Rotterdam and Shanghai to Rotterdam shrank 1% to $824 per feu and $4,819 per feu, respectively" -> rotterdam_shanghai 5424 -> 508, shanghai_rotterdam 824 -> 4819). Fires ONLY when the pool logic found nothing, fills EMPTY columns only, and bails unless every list part has as many labels (tracked or not) as values. MEASURED over all 231 cached captures: 231 parsed, 0 parser errors, exactly 4 values moved, all on the 2 snapshots of that one print; 227 pages byte-identical; 16=a LEVEL printed with NO dollar sign ("...rates from Shanghai to Los Angeles fell 3% or $224 to 7,288 per 40ft box.", 2024-07-18) is now a candidate, admitted ONLY when the level introducer ends immediately before it, a price unit follows, and it carries a thousands comma or >=4 digits. MEASURED over all 230 cached captures: 229 unchanged, exactly 1 page moved, 1 value, shanghai_la 224 -> 7288 (the level the page prints); 0 parser errors; 15=an ORIGIN printed in the sentence's OPENING lane ("Spot rates from Shanghai to major US destinations declined slightly ... with spot rates to Los Angeles and New York falling 1% to $2,214 and $2,800 per 40ft container, respectively.", 2026-02-12) now seeds the elided-origin destination list; ADDITIVE and MONOTONE, fills EMPTY lanes only, and it runs only when the sentence names no route AND ROUTE_PATTERNS matches nothing in it. MEASURED over all 230 cached captures: exactly 1 page moved, 2 values, both None -> the level printed on that page (shanghai_la 2214, shanghai_ny 2800; 230/230 pages parsed, 0 parser errors); 14=the elided-origin mention is also written as "those to <port>" (2026-03-26: "rates from Shanghai to New York jumped 3% to $3,393 ... while those to Los Angeles increased 4% to $2,686"); 13=an ELIDED-ORIGIN re-statement ("...rates from Shanghai to New York falling 6% to $2,735 ... and rates to Los Angeles reducing 4% to $2,089", 2025-11-27) fills a lane left EMPTY after the sentence's own logic - a monotone fallback that can never move or overwrite an assignment; 12=a lane list whose SECOND destination is a bare port after a conjunction ("from Shanghai to New York and Los Angeles ... $9,507 and $6,802 respectively") now ordinals BOTH lanes and derives the second lane's column from ROUTE_PATTERNS by reconstructing "<origin> to <dest>": 10 cached captures recovered a lane, 0 values changed, 220/230 pages byte-identical; 11=the LEVEL introducer also accepts a PHRASE (to touch / a new high of): 2021-05-20 now returns $9,865/$5,605, not the $889/$350 CHANGES; 10=to_rx accepts reached/reaches; 1=per-line, 2=per-sentence, 3=ordinal over untracked lanes, 4=clause scope + or/at/reach introducers, 5=dash lane lists + level in next clause, 6=composite anchored on the week headline level not the YTD average (2026-09-30), 7=re-parse of every cached snapshot under 6, 8=label_rx accepts the plain HYPHEN so 2021-era "Shanghai-New York" lanes are ordinalised, 9=leading prose word trimmed off a label + to-anchored suffix pool for changes-first lane lists (2021-07-01, 2023-02-23, 2023-09-21), 10=to_rx also accepts reached/reaches (2023-09-28, 2021-07-22)
# The oldest print this parser's prose shapes have been TRIAL-VERIFIED against.
# Moved 2023-01-01 -> 2021-01-01 on 2026-09-30 (docs/drewry_wci_era2021_verdict.md):
# every gate-passing 2021-2022 print was read lane-by-lane against its own cached
# page. Captures older than this stay counted-but-withheld, never guessed.
TRIALED_FROM = '2021-01-01'
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


def latest_by_ts():
    """ts -> the last record written for it (a --refresh appends corrected parses)."""
    out = {}
    if not os.path.exists(CKPT):
        return out
    with io.open(CKPT, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get('ts'):
                out[rec['ts']] = rec
    return out


def fetch_html(ts, orig, sleep_s=1.0, attempts=4):
    """Wayback fetch with a local cache and backoff.

    The cache means a parser change re-parses offline. Wayback intermittently
    refuses connections (WinError 10061) when hit too fast, so retry with
    backoff rather than writing an error over a parse that already worked.
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    cache = os.path.join(RAW_DIR, '%s.html' % ts)
    if os.path.exists(cache) and os.path.getsize(cache) > 1000:
        with io.open(cache, encoding='utf-8', errors='replace') as fh:
            return fh.read(), None
    url = 'https://web.archive.org/web/%sid_/%s' % (ts, orig)
    last = None
    for k in range(attempts):
        try:
            r = requests.get(url, headers=HDR, timeout=90)
            if r.status_code == 200 and len(r.text) > 1000:
                with io.open(cache, 'w', encoding='utf-8') as fh:
                    fh.write(r.text)
                time.sleep(sleep_s)
                return r.text, None
            last = 'HTTP %d' % r.status_code
        except Exception as exc:
            last = '%s: %s' % (type(exc).__name__, exc)
        time.sleep(sleep_s + 3.0 * k)
    return None, last


def do_fetch(sleep_s=1.0, refresh=False, limit=None):
    os.makedirs(STATE_DIR, exist_ok=True)
    snaps = one_per_week(load_cdx())
    done = load_done()
    latest = latest_by_ts()
    if refresh:
        # Re-parse only what has no GOOD record from the CURRENT parser version.
        # A --refresh must not re-buy a page that already parsed, and a failed
        # fetch must never erase the parse it replaced (see do_stack).
        todo = [s for s in snaps
                if not (latest.get(s[0], {}).get('pv') == PARSER_VERSION
                        and not latest[s[0]].get('error'))]
    else:
        todo = [s for s in snaps if s[0] not in done]
    if limit:
        todo = todo[:limit]
    lack = sum(1 for t in snaps
               if not (latest.get(t[0], {}).get('pv') == PARSER_VERSION
                       and not latest[t[0]].get('error')))
    print('[+] snapshots: %d total, %d done, %d lack a good v%d parse, %d to fetch (refresh=%s)'
          % (len(snaps), len(done), lack, PARSER_VERSION, len(todo), refresh), flush=True)
    ok = 0
    with io.open(CKPT, 'a', encoding='utf-8', newline='') as out:
        for i, (ts, orig) in enumerate(todo, 1):
            rec = {'ts': ts, 'pv': PARSER_VERSION}
            try:
                html, err = fetch_html(ts, orig, sleep_s)
                if err:
                    rec['error'] = err
                else:
                    v, pdate, _ = extract_assessments(html)
                    rec['page_date'] = pdate
                    rec['values'] = {k: v.get(k) for k in KEYS + ('rotterdam_shanghai',)}
                    have = all(rec['values'].get(k) for k in KEYS)
                    rec['complete'] = bool(have)
                    ok += 1 if have else 0
            except Exception as exc:
                rec['error'] = '%s: %s' % (type(exc).__name__, exc)
            out.write(json.dumps(rec) + '\n')
            out.flush()
            if i % 25 == 0 or i == len(todo):
                print('    %d/%d  complete=%d  last=%s' % (i, len(todo), ok, ts), flush=True)
    print('[OK] fetch pass done: %d complete rows in this pass' % ok)

def do_stack(era_from='2026-01-01'):
    # Last parse wins per snapshot timestamp (a --refresh appends a corrected
    # record for the same ts), then ONE row per print date from the EARLIEST
    # snapshot of that date.
    by_ts, order = {}, []
    with io.open(CKPT, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue                 # torn last line from a crash - normal
            if rec.get('ts'):
                if rec['ts'] not in by_ts:
                    order.append(rec['ts'])
                    by_ts[rec['ts']] = rec
                elif rec.get('values') or not by_ts[rec['ts']].get('values'):
                    # A re-parse wins; a FAILED fetch (no 'values') never erases
                    # the parse it was meant to replace.
                    by_ts[rec['ts']] = rec
    rows = {}
    n = {'snapshots': len(by_ts), 'fetch_failed': 0, 'incomplete': 0, 'pre_era': 0,
         'numeric': 0, 'composite': 0, 'contam': 0, 'fused': 0, 'withheld': 0}
    for ts in order:
        rec = by_ts[ts]
        if not rec.get('values'):
            n['fetch_failed'] += 1
            continue
        if not rec.get('complete') or not rec.get('page_date'):
            n['incomplete'] += 1
            continue
        # GATES. (1) era: prose shapes before TRIALED_FROM are NOT trialed and are
        # withheld rather than guessed. TRIALED_FROM was 2023-01-01 until
        # 2026-09-30, when the 2021-2022 era was trial-verified: 28 gate-passing
        # prints read lane-by-lane against their own pages, composite 30/30 ==
        # the page's own headline level. (2) numeric: the four Shanghai routes are
        # one trade family, so their spread is bounded and the composite is a
        # weighted average of them.
        if rec['page_date'] < TRIALED_FROM:
            n['pre_era'] += 1
            continue
        core = [rec['values'].get(k) for k in KEYS[1:]]
        if any((c is None or c <= 0) for c in core) or max(core) / min(core) > 5.0:
            n['numeric'] += 1
            continue
        comp = rec['values'].get('composite_index')
        if not comp or not (0.35 * min(core) <= comp <= 2.5 * max(core)):
            n['composite'] += 1
            continue
        # (3) contamination tells measured on the staged set: a value with two
        # decimals is a methodology number, not a printed level, and a route
        # value equal to the composite means the parser grabbed the headline.
        # The 2-decimal tell applies to the ROUTE values only. MEASURED on the
        # archived pages: every route is printed as a whole dollar ("$1,313 per
        # 40ft box") while the composite is printed to 2 dp ("$1,535.75 per 40ft
        # container"). Including the composite dropped 12 real prints - all 12
        # with a 2-dp value in the composite alone (scratch/wci/gate_probe.py).
        raws = [rec['values'].get(k) for k in KEYS[1:]] + [rec['values'].get('rotterdam_shanghai')]
        if any((str(x).rstrip('0').rstrip('.').split('.')[-1] != '0' and '.' in str(x)
                and len(str(x).split('.')[1]) > 1) for x in raws if x is not None):
            n['contam'] += 1
            continue
        # (3b) FUSED PAIR. Two tracked lanes cannot carry the same level on one
        # page unless the publisher prints them equal. MEASURED 2026-09-30 on
        # the 76 staged prints: exactly 2 rows carry an equal tracked pair and
        # BOTH are the parser handing one lane the other lane's level -
        # 2023-02-23 "On Shanghai - New York and Shanghai - Rotterdam, rates fell
        # by 4% to $2,881 and $1,633 per feu, respectively" (Rotterdam got
        # 2,881) and 2023-09-21 "Freight Rates on Shanghai - Genoa and Shanghai -
        # Rotterdam dropped 10% or $167 and $127 to $1,531 and $1,172 per 40ft
        # container" (Rotterdam got 1,531). Reject the row - a wrong value is
        # worse than a missing one. The lane rule for that shape is still open.
        rv = [x for x in raws if x is not None]
        if len(rv) != len(set(rv)):
            n['fused'] += 1
            continue
        if any(abs(comp - c) < 0.01 for c in core):
            n['contam'] += 1
            continue
        # (4) ERA GATE: rows older than `era_from` are counted but WITHHELD from
        # the displayed file until their prose shape has been trialed against the
        # page. Widen only after a trial passes - never by assumption.
        if rec['page_date'] < era_from:
            n['withheld'] += 1
            continue
        d, v = rec['page_date'], rec['values']
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
    print('[OK] staged %d SHIPPABLE real prints -> %s   (era_from=%s)' % (len(rows), STAGE, era_from))
    print('     gate census: %s' % json.dumps(n))
    print('     date range  : %s .. %s' % (min(rows), max(rows)) if rows else '     (empty)')
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--stack', action='store_true')
    ap.add_argument('--refresh', action='store_true',
                    help='re-fetch/re-parse EVERY snapshot, not just the missing ones')
    ap.add_argument('--limit', type=int, default=None, help='cap the fetch pass (trial runs)')
    ap.add_argument('--sleep', type=float, default=1.0)
    ap.add_argument('--era-from', default='2026-01-01',
                    help='rows older than this are counted but withheld from the staged file')
    a = ap.parse_args()
    if a.fetch:
        do_fetch(a.sleep, refresh=a.refresh, limit=a.limit)
    if a.stack:
        do_stack(a.era_from)
    if not a.fetch and not a.stack:
        ap.print_help()
