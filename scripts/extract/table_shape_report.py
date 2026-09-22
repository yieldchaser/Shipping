#!/usr/bin/env python
"""Count what the table extractors actually produced: grids vs extraction noise.

WHY
---
`tables` in the checkpoint counts every record in tables.jsonl, including two
classes that are not tables:

  * skeleton  - a detected grid region with <=1 non-empty cell (camelot returns
                the row/column boundaries but no text). Measured 2026-09-22: a
                xclusiv weekly page yields a 68x7 and a 40x16 all-empty grid
                next to the real tables on the same page.
  * blob      - a single column whose cells hold the whole page (the text layer
                re-emitted as a 1-column "table"); in xclusiv page 5 that blob is
                the entire commodities page in one cell.

Both are harmless in themselves - the values they cover also exist in text.jsonl
- but they inflate the table count and they land in the derived catalogue, so a
"tables extracted" number read from the checkpoint overstates real schema
coverage. classify() labels each record so the count can be stated honestly.

Read-only. Never writes to the corpus.

usage:
    python scripts/extract/table_shape_report.py
    python scripts/extract/table_shape_report.py --json
    python scripts/extract/table_shape_report.py --source carriers
"""
import argparse
import collections
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CORPUS = os.path.join(REPO, 'data', 'extracted', 'corpus')

BLOB_CHARS = 300


def classify(t):
    rows = t.get('rows') or []
    if not rows:
        return 'empty'
    cells = [str(c) for r in rows for c in r if str(c).strip()]
    if not cells:
        return 'empty'
    if len(cells) <= 1:
        return 'single_cell'
    n_cols = max(len(r) for r in rows)
    if n_cols == 1:
        return 'blob' if max(len(c) for c in cells) > BLOB_CHARS else 'onecol'
    return 'grid'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', default=DEFAULT_CORPUS)
    ap.add_argument('--source', default=None)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    per_source = collections.defaultdict(collections.Counter)
    docs_per_source = collections.Counter()
    for tpath in glob.glob(os.path.join(args.corpus, '*', '*', 'tables.jsonl')):
        src = os.path.basename(os.path.dirname(os.path.dirname(tpath)))
        if args.source and src != args.source:
            continue
        docs_per_source[src] += 1
        try:
            with open(tpath, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        t = json.loads(line)
                    except ValueError:
                        per_source[src]['unparseable'] += 1
                        continue
                    per_source[src][classify(t)] += 1
        except OSError:
            per_source[src]['unreadable'] += 1

    total = collections.Counter()
    for c in per_source.values():
        total.update(c)
    n = sum(total.values())
    noise = total['empty'] + total['single_cell'] + total['blob']
    report = {
        'corpus': args.corpus,
        'table_records': n,
        'totals': dict(total),
        'noise_records': noise,
        'noise_share': round(noise / max(1, n), 4),
        'real_grid_records': n - noise,
        'per_source': {s: dict(c) for s, c in sorted(per_source.items())},
        'docs_per_source': dict(docs_per_source),
    }
    if args.json:
        print(json.dumps(report, indent=1))
        return 0
    print('table records: %d   real grids: %d   extraction noise: %d (%.1f%%)'
          % (n, n - noise, noise, 100.0 * noise / max(1, n)))
    print('  ' + '  '.join('%s=%d' % (k, v) for k, v in sorted(total.items())))
    print('%-22s %6s %7s %7s %6s %6s' % ('source', 'docs', 'grid', 'blob', 'skel', 'empty'))
    for s, c in sorted(per_source.items(), key=lambda kv: -sum(kv[1].values())):
        skel = c['single_cell']
        print('%-22s %6d %7d %7d %6d %6d'
              % (s[:22], docs_per_source[s], c['grid'], c['blob'], skel, c['empty']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
