#!/usr/bin/env python3
"""
BIX Benchmark History Accumulator
=================================
The flat harvester (bunker_pipeline/extractors/bunkerindex_bix.py
fetch_bix_suite, invoked by bunker_pipeline/run_pipeline.py) OVERWRITES
data/bunkers/bunker_bix_macro_benchmarks.csv on every run and only extracts
the trailing ~10-day tables. The full published series (~256 daily chart
points per index x grade) is harvested by scripts/bunkers/bix_history_backfill.py
and merged through this accumulator (extra --input rows win the dedupe).

This script maintains an append/merge archive instead:

    data/bunkers/bix_history.csv   (same long schema as the source CSV)

- Seeds from data/bunkers/bunker_bix_macro_benchmarks.csv (current 150 rows,
  10 obs days x 5 BIX indices x 3 grades) on first run.
- Merges any prior history file, then any extra --input CSVs (future harvest
  layouts / backfills), deduped on (observation_date, index_code, grade)
  keeping the LATEST source revision (source CSVs win over the archive).
- Idempotent: re-running with unchanged inputs rewrites byte-identical output.
- CRLF-safe: reads utf-8(-sig)/CRLF or LF, writes deterministic LF.
- Never fabricates rows: the archive only ever contains rows that appeared in
  a real source CSV. Coverage grows as the scheduled harvest runs daily.

Wire-in: called by scripts/bunkers/build_bunker_cache.py (which CI runs in
.github/workflows/data_expansion.yml "Bunker prices collector & Bunker Cache"
step) BEFORE the summary build, so the archive grows on every scheduled run.
Can also be run standalone:  python scripts/bunkers/build_bix_history.py
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HISTORY_CSV = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bix_history.csv')
SEED_CSV = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bunker_bix_macro_benchmarks.csv')

# Same long schema + provenance cols as bunker_bix_macro_benchmarks.csv.
FIELDS = [
    'observation_date', 'index_code', 'grade', 'price_usd', 'change_usd',
    'change_pct', 'low_usd', 'high_usd', 'unit', 'source',
]
# Dedupe key: one row per observation date per index per grade.
KEY_FIELDS = ('observation_date', 'index_code', 'grade')
_NUM_FIELDS = ('price_usd', 'change_usd', 'change_pct', 'low_usd', 'high_usd')


def _canon(val, field):
    """Canonical string form so dedupe is stable across runs/machines."""
    if val is None:
        return ''
    s = str(val).replace('\r', ' ').replace('\n', ' ').strip()
    if field in _NUM_FIELDS:
        if s == '':
            return ''
        try:
            # '.10g' keeps 664.31 / -2.38 / 0.89 exact; trims float noise.
            return format(float(s), '.10g')
        except (TypeError, ValueError):
            return ''
    return s


def read_rows(path):
    """Read a long-schema BIX CSV (tolerates BOM/CRLF); returns canonical dicts."""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, 'r', newline='', encoding='utf-8-sig') as f:
        for raw in csv.DictReader(f):
            row = {k: _canon(raw.get(k), k) for k in FIELDS}
            if row['observation_date'] and row['index_code'] and row['grade'] \
                    and row['price_usd'] != '':
                rows.append(row)
    return rows


def merge_history(history_path=HISTORY_CSV, inputs=None, seed_path=SEED_CSV):
    """Merge seed + prior history + extra inputs into the archive dict.

    Priority (later wins): prior history -> seed -> each --input in order,
    i.e. the freshest published revision of the same observation wins.
    Returns (archive dict keyed by KEY_FIELDS, stats dict).
    """
    archive = {}
    source_order = []
    if os.path.exists(history_path):
        for row in read_rows(history_path):
            archive[row['observation_date'], row['index_code'], row['grade']] = row
        source_order.append(('history', len(archive)))
    prior_rows = len(archive)

    seed_rows = []
    if os.path.exists(seed_path):
        seed_rows = read_rows(seed_path)
        source_order.append(('seed', len(seed_rows)))
    new_keys = 0
    for row in seed_rows:
        k = (row['observation_date'], row['index_code'], row['grade'])
        if k not in archive:
            new_keys += 1
        archive[k] = row

    for path in (inputs or []):
        rows = read_rows(path)
        source_order.append((os.path.basename(path), len(rows)))
        for row in rows:
            k = (row['observation_date'], row['index_code'], row['grade'])
            if k not in archive:
                new_keys += 1
            archive[k] = row

    dates = sorted({k[0] for k in archive})
    stats = {
        'sources': source_order,
        'prior_history_rows': prior_rows,
        'new_keys_added': new_keys,
        'total_rows': len(archive),
        'distinct_obs_dates': len(dates),
        'date_min': dates[0] if dates else None,
        'date_max': dates[-1] if dates else None,
    }
    return archive, stats


def write_history(archive, out_path=HISTORY_CSV):
    """Write the archive deterministically (sorted, LF, no BOM). Idempotent."""
    rows = sorted(
        archive.values(),
        key=lambda r: (r['observation_date'], r['index_code'], r['grade']),
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    buf = []
    for row in rows:
        buf.append({k: row.get(k, '') for k in FIELDS})
    tmp = out_path + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(buf)
    os.replace(tmp, out_path)  # atomic swap; never leaves a half-written archive
    return rows


def build_bix_history_payload(history_path=HISTORY_CSV):
    """Compact embed for bunker_frontend_summary.json.

    {index_code: {grade: {dates: [...], prices: [...], change_usd: [...]}}}
    dates ascending (monotonic) — the FULL archive, not a trailing window.
    Returns None when the archive does not exist yet.
    """
    if not os.path.exists(history_path):
        return None
    rows = read_rows(history_path)
    series = {}
    for r in sorted(rows, key=lambda r: (r['observation_date'], r['index_code'], r['grade'])):
        g = series.setdefault(r['index_code'], {}).setdefault(r['grade'], {'dates': [], 'prices': [], 'change_usd': []})
        g['dates'].append(r['observation_date'])
        g['prices'].append(round(float(r['price_usd']), 2))
        g['change_usd'].append(round(float(r['change_usd']), 2) if r['change_usd'] != '' else None)
    return {
        'source': 'BunkerIndex_BIX',
        'unit': 'USD/MT',
        'updated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'rows': len(rows),
        'series': series,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='Accumulate BIX benchmark history archive')
    ap.add_argument('--input', action='append', default=[],
                    help='Extra long-schema BIX CSV to merge (repeatable)')
    ap.add_argument('--history', default=HISTORY_CSV, help='Archive CSV path')
    ap.add_argument('--seed', default=SEED_CSV, help='Seed/source CSV path')
    ap.add_argument('--dry-run', action='store_true', help='Merge + report only')
    args = ap.parse_args(argv)

    archive, stats = merge_history(history_path=args.history, inputs=args.input, seed_path=args.seed)
    if not archive:
        print('ERROR: no BIX rows found (no history, no seed).', file=sys.stderr)
        return 1
    if not args.dry_run:
        write_history(archive, args.history)
    stats['written'] = not args.dry_run
    print(json.dumps(stats))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
