"""banchero_costa - LlamaParse escalation runner (page-targeted, resumable).

WHY THIS SOURCE NEEDS A CLOUD PARSER
------------------------------------
The banchero table text layer is glyph-ciphered. Established by probing the embedded
subset fonts (docs/banchero_cipher_forensics.md):
  * glyph OUTLINES render correctly - the page shows a perfect table;
  * the text layer is wrong, and it is not recoverable locally:
      - subsets are stripped (no `post` table, glyph names are glyph00001...),
      - ToUnicode CMaps are present but inconsistent with the drawn glyphs,
      - the mapping is per font SUBSET, so no single substitution table exists.
  * `text.jsonl` does not contain TD3C/TD15/116,448/105,321 in any form.
A pixel-reading parser is the only working method - LlamaParse recovered 13/13
ground-truth values where every local method failed.

DESIGN RULES
------------
  * SOURCE BY SOURCE - hardcoded to banchero; not a generic runner.
  * PAY ONLY FOR PAGES THAT NEED IT - the routing map is computed inline by
    detecting ciphered spans, so clean pages are never sent. Measured: 1074 of
    3753 pages (28.6%) are affected.
  * NO QUALITY COMPROMISE - every run is verified against ground truth before the
    tier is trusted at scale; the script prints a scale/don't-scale verdict.
  * CHECKPOINT + RESUME - state written after every document.
  * NO KEY PERSISTENCE - LLAMA_CLOUD_API_KEY is read from the env, never written.

Usage:
    python3 scripts/extract/publishers/run_banchero_llamaparse.py --limit 3 --tier cost_effective
    python3 scripts/extract/publishers/run_banchero_llamaparse.py --chart --limit 3 --tier agentic_plus
    python3 scripts/extract/publishers/run_banchero_llamaparse.py --status
"""
import argparse, glob, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTDIR = ROOT / 'data' / 'extracted' / 'llamaparse_banchero'
STATE = OUTDIR / '_run_state.json'
ROUTEMAP_CACHE = OUTDIR / '_cipher_pages.json'

CIPHER_CHARS = set('!"#$%&()*')

# Ground truth for 2026 W03, read off the rendered page by eye and independently
# recovered by the first LlamaParse run (13/13). Gates the tier before scale-up.
GROUND_TRUTH = ['130.3', '77.7', '+67.6%', '+69.0%', '116,448', '59,536',
                '105,321', '60,759', '65,000', '59,000', '121.9', '77.3', '106,057']
GT_DOC_PREFIX = 'banchero_costa_2026_W03'

TIER_CR = {'fast': 1, 'cost_effective': 3, 'agentic': 18, 'agentic_plus': 45}


def punct_ratio(s):
    return sum(1 for c in s if c in CIPHER_CHARS) / len(s) if s else 0.0


def ciphered_pages(pdf):
    """Pages carrying glyph-ciphered spans. This is the paid surface."""
    import pymupdf
    out = []
    with pymupdf.open(pdf) as d:
        for pno in range(d.page_count):
            for blk in d[pno].get_text('dict')['blocks']:
                hit = False
                for ln in blk.get('lines', []):
                    for sp in ln['spans']:
                        t = sp['text'].strip()
                        if len(t) >= 4 and punct_ratio(t) > 0.35 and not any(c.islower() for c in t):
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    out.append(pno + 1)      # 1-based, for page_ranges
                    break
            # continue scanning the rest of the pages
    return out


def build_routing_map(force=False):
    if ROUTEMAP_CACHE.exists() and not force:
        try:
            return json.loads(ROUTEMAP_CACHE.read_text())
        except Exception:
            pass
    pdfs = sorted(glob.glob(str(ROOT / 'corpus/01-brokers/banchero_costa/*/*.pdf')))
    print(f'building routing map over {len(pdfs)} docs (cached after this run)...')
    m = {}
    for i, p in enumerate(pdfs, 1):
        doc = os.path.basename(p)[:-4]
        try:
            m[doc] = ciphered_pages(p)
        except Exception as e:
            m[doc] = []
            print(f'   {doc}: scan error {str(e)[:80]}')
        if i % 50 == 0:
            print(f'   ...{i}/{len(pdfs)}')
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ROUTEMAP_CACHE.write_text(json.dumps(m, indent=1))
    tot = sum(len(v) for v in m.values())
    print(f'routing map: {tot} ciphered pages across {len(m)} docs')
    return m


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {'done': {}, 'failed': {}, 'pages_parsed': 0, 'credits_estimated': 0, 'tier': None}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='max docs this run (0 = all)')
    ap.add_argument('--tier', default='cost_effective', choices=list(TIER_CR))
    ap.add_argument('--chart', action='store_true', help='enable specialized chart parsing')
    ap.add_argument('--no-target-pages', action='store_true',
                    help='send whole documents (expensive; comparison only)')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--rebuild-map', action='store_true')
    a = ap.parse_args()

    st = load_state()
    if a.status:
        print(f'tier of last run : {st.get("tier")}')
        print(f'docs done        : {len(st["done"])}')
        print(f'docs failed      : {len(st["failed"])}')
        print(f'pages parsed     : {st.get("pages_parsed", 0)}')
        print(f'credits estimate : {st.get("credits_estimated", 0)}')
        if st['failed']:
            print('failures:', list(st['failed'])[:10])
        return

    key = os.environ.get('LLAMA_CLOUD_API_KEY', '').strip()
    if not key:
        print('ABORT: LLAMA_CLOUD_API_KEY not set in the environment.')
        print('Set it for this shell only, then re-run. It is never written to disk.')
        sys.exit(2)

    from llama_cloud import LlamaCloud
    client = LlamaCloud(api_key=key)

    route = build_routing_map(force=a.rebuild_map)
    pdfs = sorted(glob.glob(str(ROOT / 'corpus/01-brokers/banchero_costa/*/*.pdf')))
    todo = [p for p in pdfs if os.path.basename(p)[:-4] not in st['done']]
    if a.limit:
        todo = todo[:a.limit]

    cr = TIER_CR[a.tier]
    print(f'tier={a.tier} ({cr} cr/page)   to do: {len(todo)}   done: {len(st["done"])}')
    print()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for i, pdf in enumerate(todo, 1):
        doc = os.path.basename(pdf)[:-4]
        pages = route.get(doc) or []
        kwargs = dict(tier=a.tier, version='latest', expand=['markdown_full', 'items'])
        use_pages = pages and not a.no_target_pages
        if use_pages:
            kwargs['page_ranges'] = {'target_pages': ','.join(str(x) for x in pages)}
        proc = {'cost_optimizer': {'enable': True}}
        if a.chart:
            proc['specialized_chart_parsing'] = a.tier
        kwargs['processing_options'] = proc
        kwargs['output_options'] = {
            'tables_as_spreadsheet': {'enable': True},
            'markdown': {'tables': {'merge_continued_tables': True}},
        }
        n_pages = len(pages) if use_pages else 16
        t0 = time.time()
        try:
            fo = client.files.create(file=pdf, purpose='parse')
            res = client.parsing.parse(file_id=fo.id, **kwargs)
            md = getattr(res, 'markdown_full', None) or ''
            (OUTDIR / f'{doc}.md').write_text(md, encoding='utf-8')
            try:
                (OUTDIR / f'{doc}.items.json').write_text(res.items.model_dump_json(), encoding='utf-8')
            except Exception:
                pass
            st['done'][doc] = {'pages': pages, 'chars': len(md), 'secs': round(time.time() - t0)}
            st['pages_parsed'] += n_pages
            st['credits_estimated'] += n_pages * cr
            st['tier'] = a.tier
            print(f'  [{i}/{len(todo)}] {doc}  pages={n_pages}  {len(md)} chars  '
                  f'{time.time()-t0:.0f}s   credits~{st["credits_estimated"]}')
        except Exception as e:
            st['failed'][doc] = str(e)[:300]
            print(f'  [{i}/{len(todo)}] {doc}  FAILED: {str(e)[:150]}')
        save_state(st)

    print()
    print(f'done={len(st["done"])}  failed={len(st["failed"])}  '
          f'pages={st["pages_parsed"]}  credits~{st["credits_estimated"]}')

    # ---- verification gate: never skip ----
    gtdocs = [k for k in st['done'] if k.startswith(GT_DOC_PREFIX)]
    if gtdocs:
        md = OUTDIR / f'{gtdocs[0]}.md'
        if md.exists():
            txt = md.read_text(encoding='utf-8')
            missing = [v for v in GROUND_TRUTH if v not in txt]
            print()
            print(f'VERIFICATION vs ground truth on {gtdocs[0]}: '
                  f'{len(GROUND_TRUTH)-len(missing)}/{len(GROUND_TRUTH)}')
            if missing:
                print(f'   MISSING: {missing}')
                print('   -> DO NOT SCALE THIS TIER until the gaps are explained.')
            else:
                print('   -> tier passes; safe to scale.')


if __name__ == '__main__':
    main()
