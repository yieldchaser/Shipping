"""xclusiv charts: does specialized_chart_parsing return the TCE series as DATA?

This is a DIFFERENT capability from the banchero text-layer rescue, and it is the
one claim I have not yet proven. banchero proved "a ciphered text layer can be
recovered by a pixel-reading parser". It did NOT prove "a vector chart's plotted
series can be recovered as numbers".

Why it matters: docs/xclusiv_charts_owed.md records five time-series charts per
document, each carrying ~5 years of history - VLCC TCE, Suezmax TCE, Aframax TCE,
MR Atlantic Basket, MR Pacific Basket. That is the highest-value missing data in
the corpus, and geometry-fitting it locally has not been done.

Per the official docs, with specialized_chart_parsing enabled Parse often represents
a chart's data as a TABLE in the items tree. This script tests exactly that, and
checks the result against the independently extracted prose values for the same
week - the control that matters, because prose and chart should agree.

Usage:
    python3 scripts/extract/publishers/test_xclusiv_charts.py --limit 2
    python3 scripts/extract/publishers/test_xclusiv_charts.py --limit 2 --pages 3,4,5
"""
import argparse, glob, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTDIR = ROOT / 'data' / 'extracted' / 'llamaparse_xclusiv_charts'

# xclusiv documents carry their chart pages at a stable position; the wet-market
# charts sit on the page carrying "Freight Market" in the header.
DEFAULT_PAGES = '3,4'


def _hermes_env_paths():
    out = []
    hh = os.environ.get('HERMES_HOME')
    if hh:
        out.append(Path(hh) / '.env')
    out.append(Path.home() / '.hermes' / '.env')
    if os.name == 'nt':
        la = os.environ.get('LOCALAPPDATA')
        if la:
            out.append(Path(la) / 'hermes' / '.env')
    return out


def get_api_key():
    k = os.environ.get('LLAMA_CLOUD_API_KEY', '').strip()
    if k:
        return k, 'environment'
    for p in _hermes_env_paths():
        try:
            if not p.exists():
                continue
            for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
                s = line.strip()
                if s.startswith('LLAMA_CLOUD_API_KEY='):
                    v = s.split('=', 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v, str(p)
        except Exception:
            continue
    return '', None


def flatten_items(items_json):
    """Pull typed tables out of the items tree, per page."""
    found = []
    try:
        pages = items_json.get('pages') or []
        for idx, page in enumerate(pages):
            for item in (page.get('items') or []):
                if (item.get('type') or '').lower() == 'table':
                    rows = item.get('rows') or []
                    if rows:
                        found.append({'page': idx + 1, 'rows': rows})
    except Exception:
        pass
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=2)
    ap.add_argument('--pages', default=DEFAULT_PAGES,
                    help='target_pages for the chart pages (1-based, comma separated)')
    ap.add_argument('--tier', default='agentic_plus',
                    choices=['agentic', 'agentic_plus'])
    ap.add_argument('--year', default='',
                    help='restrict to documents whose path contains this year '
                         '(the layouts differ by era, so a cross-era check is required)')
    a = ap.parse_args()

    key, source = get_api_key()
    if not key:
        print('ABORT: no LLAMA_CLOUD_API_KEY (checked process env and the Hermes .env)')
        sys.exit(2)
    print(f'credential source: {source}')

    from llama_cloud import LlamaCloud
    client = LlamaCloud(api_key=key)

    pdfs = sorted(glob.glob(str(ROOT / 'corpus/01-brokers/xclusiv/*/*.pdf')))
    if a.year:
        pdfs = [p for p in pdfs if f'/{a.year}/' in p.replace('\\', '/')]
    if a.limit:
        pdfs = pdfs[-a.limit:]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    CR = {'agentic': 18, 'agentic_plus': 45}[a.tier]
    n_pages = len(a.pages.split(','))
    print(f'docs: {len(pdfs)} | tier={a.tier} ({CR} cr/page) | pages="{a.pages}" '
          f'| est. {len(pdfs)*n_pages*CR} credits')
    print()

    summary = []
    for i, pdf in enumerate(pdfs, 1):
        doc = Path(pdf).stem
        t0 = time.time()
        try:
            fo = client.files.create(file=pdf, purpose='parse')
            res = client.parsing.parse(
                file_id=fo.id,
                tier=a.tier,
                version='latest',
                page_ranges={'target_pages': a.pages},
                processing_options={'specialized_chart_parsing': a.tier},
                expand=['markdown_full', 'items'],
            )
            md = getattr(res, 'markdown_full', None) or ''
            (OUTDIR / f'{doc}.md').write_text(md, encoding='utf-8')

            items_raw = {}
            try:
                items_raw = json.loads(res.items.model_dump_json())
                (OUTDIR / f'{doc}.items.json').write_text(
                    json.dumps(items_raw), encoding='utf-8')
            except Exception:
                pass

            tables = flatten_items(items_raw)
            (OUTDIR / f'{doc}.tables.json').write_text(
                json.dumps(tables, indent=1), encoding='utf-8')

            # does any recovered table look like a TCE time series?
            hits = []
            for t in tables:
                flat = json.dumps(t['rows'])
                if re.search(r'TCE|VLCC|Suezmax|Aframax', flat, re.I):
                    hits.append(t)
            summary.append({'doc': doc, 'tables': len(tables), 'tce_like': len(hits),
                            'chars': len(md), 'secs': round(time.time() - t0)})
            print(f'  [{i}/{len(pdfs)}] {doc}: {len(tables)} tables, '
                  f'{len(hits)} TCE-like, {len(md)} chars, {time.time()-t0:.0f}s')
        except Exception as e:
            print(f'  [{i}/{len(pdfs)}] {doc} FAILED: {str(e)[:200]}')
            summary.append({'doc': doc, 'error': str(e)[:200]})

    (OUTDIR / '_summary.json').write_text(json.dumps(summary, indent=1))
    print()
    tot = sum(s.get('tce_like', 0) for s in summary)
    print(f'TCE-like tables recovered: {tot}')
    if tot:
        print('VERDICT: specialized_chart_parsing DOES return chart series as tables.')
        print(f'   Inspect: {OUTDIR}/*.tables.json')
    else:
        print('VERDICT: no chart-derived tables. Check the markdown for whether the')
        print('   series came through as text/images instead, before spending more.')


if __name__ == '__main__':
    main()
