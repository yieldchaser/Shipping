#!/usr/bin/env python3
"""
BIX Full-History Harvester
==========================
The Bunker Index pages publish a FULL year of daily index points on every page
(inline Highcharts `data` arrays) but the in-repo flat harvester
(bunker_pipeline/extractors/bunkerindex_bix.py fetch_bix_suite) only extracts
the trailing 10-day tables. This script re-fetches the 5 BIX pages, parses the
FULL published series per page x grade (IFO380/VLSFO/MGO), and feeds it into
the append/merge accumulator (scripts/bunkers/build_bix_history.py) so
data/bunkers/bix_history.csv extends (dedupe latest-wins) on every run:

    pages (5) x grades (3) x ~256 published days  ->  up to ~3,840 observations

- Never fabricates: only rows present in the fetched page (chart array or
  trailing table) are emitted. change/low/high stay empty for chart-only days.
- Idempotent: re-running rewrites the archive byte-identically when the source
  series is unchanged (the accumulator is deterministic).
- Fails gracefully: a page that 404s/blocks is reported and skipped; the run
  still merges whatever it got (archive never shrinks, never loses old days).

Runs in the scheduled Data Expansion workflow (data_expansion.yml, "Bunker
prices collector & Bunker Cache" step) BEFORE build_bunker_cache.py so the
rebuilt bunker_frontend_summary.json embeds the extended archive. Can also run
standalone:  python scripts/bunkers/bix_history_backfill.py [--dry-run]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, 'scripts', 'bunkers')):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_bix_history as bbh  # scripts/bunkers accumulator
from bunker_pipeline.extractors.bunkerindex_bix import (
    BIX_ENDPOINTS,
    fetch_bix_history,
)

HISTORY_CSV = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bix_history.csv')
SEED_CSV = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bunker_bix_macro_benchmarks.csv')
# Data-driven tests + ops review read the run report from here.
REPORT_PATH = os.path.join(REPO_ROOT, 'data', 'bunkers', 'bix_backfill_report.json')


def write_report(report):
    """Persists the run report atomically (never leaves a half-written file)."""
    d = os.path.dirname(REPORT_PATH)
    os.makedirs(d, exist_ok=True)
    tmp = REPORT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, sort_keys=True)
    os.replace(tmp, REPORT_PATH)


def main(argv=None):
    ap = argparse.ArgumentParser(description='BIX full-history backfill/harvest')
    ap.add_argument('--dry-run', action='store_true',
                    help='Fetch + parse + report only; do not write the archive')
    args = ap.parse_args(argv)

    from bunker_pipeline.utils.http_client import CLIENT
    CLIENT.min_delay = 0.6
    CLIENT.max_delay = 1.2

    rows = []
    pages = []
    for name, url in BIX_ENDPOINTS.items():
        recs = fetch_bix_history(name, url)
        days = sorted({r['observation_date'] for r in recs})
        pages.append({
            'index_code': name,
            'url': url,
            'rows': len(recs),
            'obs_days': len(days),
            'date_min': days[0] if days else None,
            'date_max': days[-1] if days else None,
        })
        rows.extend(recs)

    report = {
        'pages': pages,
        'rows': len(rows),
        'written': False,
    }

    if not rows:
        report['status'] = 'blocked_or_empty'
        write_report(report)
        print('BIX history harvest: blocked or empty; archive untouched.')
        return 0

    # Merge into the archive (latest-wins: prior history < seed < harvest).
    tmp_csv = _temp_csv(rows)
    try:
        archive, stats = bbh.merge_history(
            history_path=HISTORY_CSV, seed_path=SEED_CSV, inputs=[tmp_csv])
    finally:
        try:
            os.remove(tmp_csv)
        except OSError:
            pass
    report['archive'] = {k: stats[k] for k in (
        'prior_history_rows', 'new_keys_added', 'total_rows',
        'distinct_obs_dates', 'date_min', 'date_max')}
    report['status'] = 'ok'

    if not args.dry_run:
        bbh.write_history(archive, HISTORY_CSV)
        report['written'] = True
    write_report(report)
    print('BIX history harvest:', json.dumps(report['archive'], sort_keys=True),
          '| harvest_rows:', report['rows'], '| written:', report['written'])
    return 0


def _temp_csv(rows):
    """Harvest rows -> temp long-schema CSV (the accumulator's merge input).
    Deleted by the caller-context tempfile; merge consumes it immediately."""
    import csv
    import tempfile
    fd, path = tempfile.mkstemp(prefix='bix_harvest_', suffix='.csv')
    with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=bbh.FIELDS, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k, '')) for k in bbh.FIELDS})
    return path


if __name__ == '__main__':
    raise SystemExit(main())
