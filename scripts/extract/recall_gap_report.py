#!/usr/bin/env python
"""Measure table RECALL loss: values that are in the page text but in no grid cell.

WHY
---
The pipeline reconciles cells -> text (`text_verified` per table, so a cell that
is not in the text layer is flagged). The reverse direction is recorded but never
surfaced: `pages.jsonl` keeps `values_only_in_text`, and nobody aggregates it, so
a document can report text_verified 1.0 while whole table rows are missing from
the grids.

Reproduced instance (2026-09-22, carriers_2026_W26_WK-26-26-CARRIERS_SP-MARKET-
REPORT, page 0): the PDF has two sale tables. "Bulk Carriers Reported Sold" was
captured (9 rows). "Tankers / LPG Vessels Reported Sold" (ECLAT / TANKER /
299,031 / 2004 / Universal Shbldg - Ariake / 50.00 / UNDISCLOSED and HANSA OSLO /
51,215 / 2007 / STX Shipbuilding - Jinhae / 20.00, plus XING TONG 799) and the
Container section row (NJORD / CV / 9,543 / 2007 / Sainty Shipbuilding / 7.50)
are in no table cell. Re-running `camelot.read_pdf(page='1', flavor='stream')`
directly on the source PDF also returns no cell containing ECLAT, so this is an
engine coverage limit, not a routing bug in run_batch.

MEASURED 2026-09-22 on the committed corpus (extraction in progress):
  carriers         125 docs: 544 DWT-like values in text but in no cell, 513 of
                   them (94%) inside vessel-sale record blocks, spread over 98
                   docs (78%)
  allied           204 docs: 366 such values, 111 in record blocks (index rows)
  banchero_costa   237 docs:  17 such values (7 docs)
  advanced_shipping 44 docs: 308 such values but 302 are prose/axis labels, i.e.
                   NOT data loss - which is why this report classifies rather
                   than counting raw orphans.
  agora            211 docs:   0

This script only READS the corpus. It never writes to it.

usage:
    python scripts/extract/recall_gap_report.py --source carriers
    python scripts/extract/recall_gap_report.py --source carriers --json
"""
import argparse
import collections
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CORPUS = os.path.join(REPO, 'data', 'extracted', 'corpus')
DEFAULT_CKPT = os.path.join(REPO, 'data', 'extracted', 'corpus_checkpoint.jsonl')

DWT = re.compile(r'^\d{1,3},\d{3}$')
PROSE = re.compile(r'\b(the|was|were|sold|and|but|of|for|with|from|reported|at|to|its|'
                   r'than|which|while|after|before|would|could)\b', re.IGNORECASE)


def source_of(path):
    parts = path.replace(chr(92), '/').split('/')
    if parts[0] == 'reports' and len(parts) > 2:
        return parts[2]
    return parts[0]


def doc_dir(corpus, stem):
    cand = os.path.join(corpus, stem)
    if os.path.isdir(cand):
        return cand
    for src in os.listdir(corpus):
        cand = os.path.join(corpus, src, stem)
        if os.path.isdir(cand):
            return cand
    return None


def load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def classify(doc_path, stem):
    """Return (record_orphans, prose_orphans, examples) for one document."""
    pages = load_jsonl(os.path.join(doc_path, 'pages.jsonl'))
    text = load_jsonl(os.path.join(doc_path, 'text.jsonl'))
    if not pages:
        return 0, 0, []
    rec = prose = 0
    examples = []
    for page in pages:
        for value in page.get('values_only_in_text') or []:
            if not DWT.match(str(value)):
                continue
            hits = [b for b in text
                    if b.get('page') == page.get('page') and value in b.get('text', '')]
            if not hits:
                continue
            block = min(hits, key=lambda b: len(b['text']))
            if PROSE.search(block['text']):
                prose += 1
            else:
                rec += 1
                if len(examples) < 3:
                    examples.append(' '.join(block['text'].split())[:110])
    return rec, prose, examples


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', default=DEFAULT_CORPUS)
    ap.add_argument('--checkpoint', default=DEFAULT_CKPT)
    ap.add_argument('--source', default=None, help='e.g. carriers; default = all sources')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    rows = load_jsonl(args.checkpoint)
    ok = [r for r in rows if r.get('status') == 'ok']
    by_src = collections.defaultdict(list)
    for r in ok:
        by_src[source_of(r['path'])].append(r)
    sources = [args.source] if args.source else sorted(by_src)

    report = {}
    for src in sources:
        tally = collections.Counter()
        worst = []
        for r in by_src.get(src, []):
            stem = r['path'].replace(chr(92), '/').split('/')[-1].rsplit('.pdf', 1)[0]
            d = doc_dir(args.corpus, stem)
            if not d or not os.path.exists(os.path.join(d, 'pages.jsonl')):
                tally['docs_missing'] += 1
                continue
            tally['docs'] += 1
            rec, prose, examples = classify(d, stem)
            if rec:
                tally['docs_with_record_orphans'] += 1
                worst.append((rec, stem, examples))
        worst.sort(reverse=True, key=lambda t: t[0])
        tally['record_orphans'] = sum(w[0] for w in worst)
        report[src] = {'summary': dict(tally), 'worst': [
            {'doc': w[1], 'record_orphans': w[0], 'examples': w[2]} for w in worst[:5]]}
        if not args.json:
            n = max(1, tally['docs'])
            print('== %s: %d docs; vessel-sale-grade record values absent from every '
                  'table cell: %d; docs affected: %d (%.0f%%)'
                  % (src, tally['docs'], tally['record_orphans'],
                     tally['docs_with_record_orphans'],
                     100.0 * tally['docs_with_record_orphans'] / n))
            for w in worst[:3]:
                print('   %4d  %s' % (w[0], w[1][:66]))
                for ex in w[2][:1]:
                    print('         e.g. %s' % ex)
    if args.json:
        print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
