"""Audit ACTUAL extraction completeness per source - content, not file counts.

Files existing is NOT correctness. This checks whether each source's output really
carries (a) non-empty markdown, (b) non-empty table JSON with rows, and (c) chart JSON
with a real series (>=3 points), and reports the shortfall honestly.

A source is only 'END-TO-END COMPLETE' when text AND tables AND chart values are all
present AND non-trivial. Everything else is partial and gets named as such.
"""
import glob, json, os, sys

BASE = 'data/extracted/md'
STATS = {}


def nonempty_json_with_rows(path, need_rows=1):
    """True if the file has at least `need_rows` row-ish entries."""
    try:
        raw = open(path, encoding='utf-8', errors='replace').read()
    except Exception:
        return False, 0
    if len(raw.strip()) < 50:
        return False, 0
    try:
        d = json.loads(raw)
    except Exception:
        # jsonl
        n = sum(1 for line in raw.splitlines() if line.strip())
        return (n >= need_rows), n
    if isinstance(d, list):
        n = len(d)
    elif isinstance(d, dict):
        # charts: count points in any series
        n = 0
        for k in ('series', 'points', 'data', 'rows'):
            if k in d:
                v = d[k]
                n = len(v) if hasattr(v, '__len__') else 1
                break
        else:
            n = len(d)
    else:
        n = 0
    return (n >= need_rows), n


def audit_source(src):
    d = os.path.join(BASE, src)
    if not os.path.isdir(d):
        return None
    mds = glob.glob(os.path.join(d, '*.md'))
    tabs = [p for p in glob.glob(os.path.join(d, '*table*.json'))]
    chs = [p for p in glob.glob(os.path.join(d, '*chart*.json'))]

    # Text threshold must be PER SOURCE, not a fixed byte count. A fixed 2000-byte
    # gate wrongly condemned ssy, which is ONE PAGE per document: 1,306-1,987 bytes
    # is a complete extraction there (10-row table + calculated index + T/C rates),
    # verified by reading the file. Judge each source against its own median so a
    # legitimately short source is not reported as empty.
    sizes = [os.path.getsize(p) for p in mds]
    if sizes:
        srt = sorted(sizes)
        median = srt[len(srt) // 2]
        thresh = max(400, int(median * 0.4))
    else:
        thresh = 400
    md_ok = sum(1 for p in mds if os.path.getsize(p) >= thresh)
    tab_ok = 0
    for p in tabs:
        ok, _ = nonempty_json_with_rows(p, 1)
        if ok:
            tab_ok += 1
    ch_ok = 0
    ch_series = 0
    for p in chs:
        ok, n = nonempty_json_with_rows(p, 3)
        if ok:
            ch_ok += 1
            ch_series += n
    return {
        'md_files': len(mds), 'md_nontrivial': md_ok,
        'table_files': len(tabs), 'table_nontrivial': tab_ok,
        'chart_files': len(chs), 'chart_with_series': ch_ok,
        'chart_points': ch_series,
    }


def main():
    srcs = sorted(os.path.basename(p) for p in glob.glob(f'{BASE}/*') if os.path.isdir(p))
    print(f'{"source":<20} {"md ok/tot":<12} {"tables ok":<12} {"charts w/series":<18} verdict')
    print('-' * 96)
    complete = []
    partial = []
    for s in srcs:
        a = audit_source(s)
        if not a:
            continue
        has_text = a['md_nontrivial'] > 0
        has_tab = a['table_nontrivial'] > 0
        has_chart = a['chart_with_series'] > 0
        if has_text and has_tab and has_chart:
            verdict = 'END-TO-END'
            complete.append(s)
        else:
            missing = []
            if not has_text: missing.append('TEXT')
            if not has_tab: missing.append('TABLES')
            if not has_chart: missing.append('CHART-VALUES')
            verdict = 'PARTIAL: missing ' + ','.join(missing)
            partial.append((s, missing))
        print(f'{s:<20} {a["md_nontrivial"]}/{a["md_files"]:<10} '
              f'{a["table_nontrivial"]}/{a["table_files"]:<10} '
              f'{a["chart_with_series"]}/{a["chart_files"]:<14} {verdict}')
    print()
    print(f'END-TO-END COMPLETE: {len(complete)} -> {complete}')
    print(f'PARTIAL: {len(partial)}')
    for s, m in partial:
        print(f'   {s:<20} missing {m}')
    json.dump({'complete': complete,
               'partial': {s: m for s, m in partial}},
              open('data/derived/extraction_completeness_audit.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
