"""Measure the PAID SURFACE across every broker source - free, local, no API calls.

The banchero work established the method: a page only needs a cloud parser if its
text layer is actually broken. Detecting that is a local PyMuPDF scan, so the whole
corpus can be measured for free BEFORE any credits are committed.

This answers the strategic question the user keeps asking - "what is the total paid
surface?" - per source, so the budget can be planned against evidence instead of
guesswork.

A page is flagged when it carries spans that look glyph-ciphered: punctuation-dense
with no lowercase. Clean prose, clean tables and normal all-caps headings are not
flagged (see banchero_cipher_forensics.md for how the thresholds were derived).

Writes: data/derived/paid_surface_by_source.json
"""
import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def discover_sources():
    """Every broker source dir with PDFs under corpus/01-brokers/."""
    base = ROOT / 'corpus/01-brokers'
    found = {}
    try:
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            n = len(list(d.glob('*/*.pdf')))
            if n == 0:
                n = len(list(d.glob('*.pdf')))
            if n:
                found[d.name] = f'corpus/01-brokers/{d.name}/*/*.pdf'
    except Exception:
        pass
    return found


CIPHER_CHARS = set('!"#$%&()*')


def punct_ratio(s):
    return sum(1 for c in s if c in CIPHER_CHARS) / len(s) if s else 0.0


def page_flagged(pg):
    for blk in pg.get_text('dict')['blocks']:
        for ln in blk.get('lines', []):
            for sp in ln['spans']:
                t = sp['text'].strip()
                if len(t) >= 4 and punct_ratio(t) > 0.35 and not any(c.islower() for c in t):
                    return True
    return False


def main():
    import pymupdf

    only = sys.argv[1] if len(sys.argv) > 1 else ''
    results = {}
    if (ROOT / 'data/derived/paid_surface_by_source.json').exists():
        try:
            results = json.loads((ROOT / 'data/derived/paid_surface_by_source.json').read_text())
        except Exception:
            results = {}

    sources = discover_sources()
    print(f'sources discovered: {len(sources)}')
    for name, pattern in sources.items():
        if only and only != name:
            continue
        pdfs = sorted(glob.glob(str(ROOT / pattern)))
        if not pdfs:
            continue
        docs = pages = flagged = errs = 0
        hist = collections.Counter()
        for i, p in enumerate(pdfs, 1):
            try:
                with pymupdf.open(p) as d:
                    docs += 1
                    for pno in range(d.page_count):
                        pages += 1
                        try:
                            if page_flagged(d[pno]):
                                flagged += 1
                                hist[pno + 1] += 1
                        except Exception:
                            errs += 1
            except Exception:
                errs += 1
                continue
            if i % 100 == 0:
                print(f'  {name}: {i}/{len(pdfs)}  flagged={flagged}')

        results[name] = {
            'docs': docs, 'pages': pages, 'flagged_pages': flagged,
            'pct': round(100 * flagged / max(pages, 1), 1), 'errors': errs,
            'flagged_by_page': {str(k): v for k, v in sorted(hist.items())},
        }
        print(f'{name:<20} docs={docs:<5} pages={pages:<6} flagged={flagged:<6} '
              f'({results[name]["pct"]}%)')

    out = ROOT / 'data/derived/paid_surface_by_source.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1))
    print()
    print(f'written -> {out}')
    tot_p = sum(v['pages'] for v in results.values())
    tot_f = sum(v['flagged_pages'] for v in results.values())
    print(f'TOTAL across measured sources: {tot_f}/{tot_p} pages flagged ({100*tot_f/max(tot_p,1):.1f}%)')


if __name__ == '__main__':
    main()
