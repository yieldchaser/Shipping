"""ISM (Metal Expert, ismreport.com) - per-source extraction pipeline.

WHY THIS SOURCE NEEDS ITS OWN PIPELINE (measured, docs/ism_survey.md):
  * ism holds NO tables. 266 pages / 112 docs carry ZERO numeric row bands that
    are tables - the only multi-number rows are CHART x-axis tick labels
    (weeks 22,25,28,...). The deliverable is chart series, not table cells.
  * Every chart is VECTOR: axis ticks are short drawn line marks (exact
    geometry) and each series is one coloured polyline. Nothing needs vision.
  * One page holds up to 3 charts, some DUAL-AXIS (left $/t or $/day, right %).
    Tick counts per axis measured at 6, 8, 9, 11, 12 across years and the plot
    area moves (y 560-703 in 2023 vs y 93-178 in 2025): no fixed geometry.

METHOD (every threshold derived from the page):
  1. tick marks = chains of >=3 short collinear line items, width<=0.8.
     horizontal chain -> a Y axis; vertical chain -> the X axis.
  2. y values = the numeric labels on the FAR side of the axis from the plot.
     Side is DETECTED, never assumed: a dual-axis chart's right axis is
     labelled to the RIGHT. Matching both sides to the left labels turned a
     0-20% axis into 0-1000 (a 50x error, caught on 2023 W32).
  3. scale = least squares value = a*y + b over (tick mark y, label value).
     Emitted only if max residual < 0.5% of the axis span, else UNVERIFIED.
  4. series = drawings with >=10 line segments and width >= 0.9 inside the
     plot. N segments = N+1 POINTS (segments share endpoints). Reading only
     segment starts loses the last week and shifts every series one week back.
  5. x values = point i sits on x-tick i (measured offset 0.03 tick, gap 1.00
     tick over 52 points). Tick i's week number is read from the positioned
     labels (every 3rd tick labelled; numbering WRAPS: 22,25,...,52,3,...,21).
  6. labels = legend swatches are short coloured marks below the plot; legend
     text is the span to the right on the same baseline. A series is labelled
     ONLY when its stroke colour matches a swatch exactly; a series with no
     swatch stays UNLABELLED (2025 W21 TCE chart: 7 polylines, 6 swatches).
  7. axis choice = a series whose legend text contains '%' uses the axis whose
     tick labels carry '%'; all others use the primary (left) axis.

Numbers are ISO in this source. '%' labels are stripped to their value and the
unit is carried in the axis record.
"""
import pymupdf, re, json, argparse, sys, traceback, collections
from pathlib import Path

NUM = re.compile(r'^[-+]?\d[\d,\.]*\s*%?$')
ROOT = Path('corpus/01-brokers/ism')
OUT = Path('data/extracted/md/ism')
STATE = OUT / '_run_state.json'


def spans(pg):
    out = []
    for b in pg.get_text('dict')['blocks']:
        if b.get('type') != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                t = s['text'].strip()
                if not t:
                    continue
                x0, y0, x1, y1 = s['bbox']
                out.append(dict(t=t, size=round(s['size'], 2), x0=x0, y0=y0, x1=x1, y1=y1,
                                cx=(x0 + x1) / 2, cy=(y0 + y1) / 2, ox=s['origin'][0], oy=s['origin'][1]))
    return out


def tick_chains(pg):
    """chains of short collinear line marks -> horizontal (Y axes) / vertical (X axis)"""
    H, V = [], []
    for x in pg.get_drawings():
        its = x['items']
        # Cap is only a guard against mistaking a dense gridline drawing for a
        # tick chain; series polylines are already excluded by stroke width.
        # 90 was too low: the 6-page holiday special draws a 156-tick x axis and
        # the whole page silently produced zero charts.
        if len(its) < 3 or len(its) > 400:
            continue
        if not all(i[0] == 'l' for i in its):
            continue
        if (x.get('width') or 0) > 0.8:
            continue
        pts = [(i[1].x, i[1].y, i[2].x, i[2].y) for i in its]
        if all(abs(p[1] - p[3]) < 0.2 and abs(p[2] - p[0]) < 6 for p in pts):
            H.append((x['rect'], sorted(set(round(p[1], 2) for p in pts))))
        elif all(abs(p[0] - p[2]) < 0.2 and abs(p[3] - p[1]) < 6 for p in pts):
            V.append((x['rect'], sorted(set(round(p[0], 2) for p in pts))))
    return H, V


def resolve_axis(sp, tick_ys, rect, prefer='left'):
    """(pairs, side, raw, monotonic) for the axis whose tick marks are at tick_ys.
    Labels are looked for on BOTH sides; the side with more consistent labels wins."""
    best = None
    for side in ((prefer, 'right' if prefer == 'left' else 'left')):
        pairs, raw = [], []
        for y in tick_ys:
            if side == 'left':
                cand = [s for s in sp if abs(s['cy'] - y) < 3.6 and s['x1'] <= rect.x0 + 2.5 and NUM.match(s['t'])]
                cand.sort(key=lambda z: -z['x1'])
            else:
                cand = [s for s in sp if abs(s['cy'] - y) < 3.6 and s['x0'] >= rect.x1 - 2.5 and NUM.match(s['t'])]
                cand.sort(key=lambda z: z['x0'])
            if cand:
                s = cand[0]
                pairs.append((y, float(s['t'].replace(',', '').replace('%', '').strip())))
                raw.append(s['t'])
        if len(pairs) >= 3:
            mono = all(pairs[i][1] >= pairs[i + 1][1] for i in range(len(pairs) - 1))
            if best is None or len(pairs) > len(best[0]):
                best = (pairs, side, raw, mono)
    return best


def fit(pairs):
    n = len(pairs)
    if n < 3:
        return None
    sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs); sxy = sum(p[0] * p[1] for p in pairs)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return None
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    res = [abs(a * p[0] + b - p[1]) for p in pairs]
    return dict(a=a, b=b, maxres=max(res), n=n)


def series_drawings(pg, plot):
    """polylines and bar groups whose geometry lies inside the plot rect"""
    polys, bars = [], []
    for k, x in enumerate(pg.get_drawings()):
        its = x['items']
        r = x['rect']
        # PDF y grows downward: plot.y0 is the TOP edge, plot.y1 the BOTTOM
        if r.x0 < plot.x0 - 4 or r.x1 > plot.x1 + 4 or r.y0 < plot.y0 - 4 or r.y1 > plot.y1 + 4:
            continue
        kinds = collections.Counter(i[0] for i in its)
        if kinds['l'] >= 10 and len(its) == kinds['l'] and (x.get('width') or 0) >= 0.9:
            pts = []
            for i in its:
                for q in (i[1], i[2]):
                    if not pts or abs(q.x - pts[-1][0]) > 1e-6 or abs(q.y - pts[-1][1]) > 1e-6:
                        pts.append((q.x, q.y))
            polys.append(dict(idx=k, color=x.get('color'), pts=pts))
        elif kinds['re'] >= 10:
            # 2023 draws its bars with a FILL and no stroke: x['color'] is None
            col = x.get('color') or x.get('fill')
            if col is None or tuple(col) == (0.0, 0.0, 0.0):
                continue
            rects = sorted({(round(i[1].x0, 2), round(i[1].y0, 2), round(i[1].x1, 2), round(i[1].y1, 2))
                            for i in its if i[0] == 're'})
            bars.append(dict(idx=k, color=col, rects=rects))
    return polys, bars


def legend_map(pg, plot, sp):
    """swatch colour -> legend text for THIS panel.

    A legend entry wraps onto 2-3 lines and its text is split across spans, so
    the entry's text is everything in the band from this swatch down to the next
    one. Joining only same-baseline spans truncated
    'Gulf of Finland (St-Pb) - ARA RV, 3,000 DWCC coaster' to
    'Gulf of Finland (St-Pb)', which made two different routes look identical."""
    sw = []
    for x in pg.get_drawings():
        its = x['items']
        if len(its) != 1:
            continue
        r = x['rect']
        if not (r.x0 > plot.x0 - 6 and r.x1 <= plot.x1 + 70):
            continue
        if not (plot.y0 - 40 <= r.y0 <= plot.y1 + 90):
            continue
        w = max(r.x1 - r.x0, r.y1 - r.y0)
        if not (4 <= w <= 22):
            continue
        col = x.get('color') or x.get('fill')
        if col is None:
            continue
        sw.append(((r.y0 + r.y1) / 2, tuple(round(c, 3) for c in col), r))
    sw.sort(key=lambda t: t[0])
    out = {}
    for i, (cy, col, r) in enumerate(sw):
        # Bound the band in BOTH axes: unbounded, the last swatch swallowed the
        # prose below it (one chart got a whole sentence as its legend label) and
        # a right-hand column's text, which smuggled a stray '%' into a $/day
        # label and routed that series onto the percent axis.
        nxt = min([c for c, _, _ in sw if c > cy + 2], default=cy + 18)
        band_hi = min(nxt - 4.0, cy + 18)
        # A legend is not always a vertical column: the year-comparison charts
        # (280 of 444 here) put their swatches in a ROW, so without a right-hand
        # bound the first swatch swallowed all three labels and every series was
        # named '2023 year 2024 year 2025 year'.
        right = min([r2.x0 for cy2, _, r2 in sw
                     if abs(cy2 - cy) < 4.0 and r2.x0 > r.x0 + 2], default=r.x1 + 220)
        cand = [s for s in sp if cy - 4.0 < s['cy'] < band_hi
                and r.x1 - 1 <= s['x0'] < right - 2 and not NUM.match(s['t'])]
        if not cand:
            continue
        # a legend entry is set in ONE size; prose that leaks into the band is a
        # different size. Anchoring on the first line's size recovers the wrapped
        # lines without dragging a sentence in as the label.
        s0 = min(cand, key=lambda z: abs(z['cy'] - cy))
        cand = [z for z in cand if abs(z['size'] - s0['size']) <= 0.35]
        cand.sort(key=lambda z: (round(z['cy'], 1), z['x0']))
        text = ' '.join(z['t'] for z in cand)
        # final guards: a legend entry here is a short route name. Anything that
        # reads as a sentence, or that duplicates a name already claimed by
        # another colour, is a mis-join -> leave the series UNLABELLED rather
        # than ship a wrong name (user's rule: a wrong label is worse than none).
        # NB do NOT test for '. ' + capital: real route names abbreviate
        # ('Rus steel billets, calc. CFR Marmara, $/t') and the test threw 92
        # good labels away.
        if len(text) > 70 or '»' in text or '«' in text:
            continue
        if any(e['text'] == text for c3, v3 in out.items() if c3 != col for e in v3):
            continue
        out.setdefault(col, []).append(dict(text=text, y=round(cy, 1)))
    return out


def chart_title(sp, plot):
    """The title is the LARGEST text immediately above the plot. Prose body text
    is smaller, so size separates them; a hard coordinate cut cannot (2023's TCE
    title is 18pt against 11pt prose, but the title line runs 230pt wide and a
    narrow x window truncated it to its second half)."""
    cand = [s for s in sp if s['y1'] <= plot.y0 + 2 and plot.y0 - s['y1'] <= 45
            and s['x1'] > plot.x0 - 12 and s['x0'] < plot.x1 + 12]
    if not cand:
        return ''
    top = max(s['size'] for s in cand)
    big = [s for s in cand if s['size'] >= top - 0.6]
    ybot = max(s['y0'] for s in big)
    keep = [s for s in big if ybot - s['y0'] < 30]
    keep.sort(key=lambda z: (z['y0'], z['x0']))
    return ' '.join(s['t'] for s in keep)


def x_label_spans(sp, vr):
    """numeric labels in the band just under the x tick marks (not y labels:
    those sit left of vr.x0, nor legend text: that is prose)."""
    out = [s for s in sp if s['y0'] >= vr.y1 - 1.5 and s['y1'] <= vr.y1 + 18
           and vr.x0 - 6 <= s['cx'] <= vr.x1 + 6 and NUM.match(s['t'])]
    out.sort(key=lambda z: z['cx'])
    return out


def week_scale(labels):
    """Fit week = c*x + d on the publisher's OWN tick labels, unwrapping past 52.

    Why not map series point i to tick i: the two charts on one page disagree.
    The TCE chart has 52 ticks and its points sit ON them; the billets chart has
    53 ticks (week BOUNDARIES) and its points sit on the week CENTRES between
    them. Anchoring on the labels the publisher printed works for both, and the
    fit residual says whether the axis is even linear in week."""
    if len(labels) < 3:
        return None
    ws, prev_raw, off = [], None, 0
    for s in labels:
        w = int(round(float(s['t'].replace(',', '').strip())))
        # compare RAW weeks: comparing against the unwrapped value re-adds 52
        # on every subsequent label (measured: 7 spurious wraps, 120-week residual)
        if prev_raw is not None and w < prev_raw:
            off += 52
        ws.append(w + off)
        prev_raw = w
    xs = [s['cx'] for s in labels]
    n = len(xs)
    sx = sum(xs); sy = sum(ws); sxx = sum(x * x for x in xs); sxy = sum(x * w for x, w in zip(xs, ws))
    den = n * sxx - sx * sx
    if abs(den) < 1e-9:
        return None
    c = (n * sxy - sx * sy) / den
    d = (sy - c * sx) / n
    res = [abs(c * x + d - w) for x, w in zip(xs, ws)]
    return dict(c=c, d=d, maxres=max(res), n=n, first=ws[0], last=ws[-1],
                labels=[(round(s['cx'], 1), s['t']) for s in labels])


def analyse_page(pg):
    sp = spans(pg)
    H, V = tick_chains(pg)
    panels = []
    for vr, xs in V:
        if len(xs) < 10:
            continue
        hs = [h for h in H if abs(h[0].y1 - vr.y0) < 3.5
              and h[0].x0 >= vr.x0 - 25 and h[0].x1 <= vr.x1 + 25]
        if not hs:
            continue
        hs.sort(key=lambda h: h[0].x0)
        left, right = hs[0], (hs[-1] if len(hs) > 1 else None)
        plot = pymupdf.Rect(min(left[0].x0, vr.x0), min(left[0].y0, vr.y0),
                            max(vr.x1, (right[0].x1 if right else vr.x1)), vr.y0)
        panels.append(dict(vr=vr, xs=xs, left=left, right=right, plot=plot))
    out = []
    for p in panels:
        plot = p['plot']
        rec = dict(title=chart_title(sp, plot), plot=[round(v, 1) for v in plot],
                   n_xticks=len(p['xs']), axes={}, series=[], warnings=[])
        # a left-edge axis is labelled to its LEFT, a right-edge axis to its RIGHT:
        # preferring the far side is what keeps a 0-40% axis from being read off
        # the 0-400 $/t labels (a 10x error caught on 2025 W21)
        la = resolve_axis(sp, p['left'][1], p['left'][0], prefer='left')
        ra = resolve_axis(sp, p['right'][1], p['right'][0], prefer='right') if p['right'] else None
        if not la:
            rec['warnings'].append('no primary axis labels')
            out.append(rec)
            continue
        fl = fit(la[0])
        spanl = max(v for _, v in la[0]) - min(v for _, v in la[0])
        rec['axes']['primary'] = dict(side=la[1], raw=la[2], a=round(fl['a'], 5), b=round(fl['b'], 3),
                                      maxres=round(fl['maxres'], 3),
                                      maxres_pct=round(100 * fl['maxres'] / max(spanl, 1e-9), 3),
                                      verified=bool(fl['maxres'] < 0.005 * max(spanl, 1e-9)), n=fl['n'])
        fr = None
        if ra:
            fr = fit(ra[0])
            spanr = max(v for _, v in ra[0]) - min(v for _, v in ra[0])
            rec['axes']['secondary'] = dict(side=ra[1], raw=ra[2], a=round(fr['a'], 5), b=round(fr['b'], 3),
                                            maxres=round(fr['maxres'], 3),
                                            maxres_pct=round(100 * fr['maxres'] / max(spanr, 1e-9), 3),
                                            verified=bool(fr['maxres'] < 0.005 * max(spanr, 1e-9)),
                                            n=fr['n'], is_percent=any('%' in t for t in ra[2]))
        polys, bars = series_drawings(pg, plot)
        # publishers draw one bar group as fill + outline + shadow copies: three
        # drawings, identical bar tops. Keep one, else the same series ships 2-3x.
        # key on the resulting VALUE SEQUENCE, not on geometry: the copies differ
        # by a 1pt border offset, so a geometry key let duplicates through and
        # the same bar series shipped twice under one legend label.
        uniq = []
        for b in bars:
            tops = [r[1] for r in b['rects']]
            dup = False
            for k in uniq:
                kt = [r[1] for r in k['rects']]
                if len(kt) == len(tops) and max(abs(a - c) for a, c in zip(tops, kt)) < 0.5:
                    dup = True
                    break
            if not dup:
                uniq.append(b)
        bars = uniq
        lm = legend_map(pg, plot, sp)
        ticks = p['xs']
        labels = x_label_spans(sp, p['vr'])
        wk = week_scale(labels)
        if wk:
            rec['x_scale'] = dict(c=round(wk['c'], 6), d=round(wk['d'], 3), n=wk['n'],
                                  maxres_weeks=round(wk['maxres'], 4),
                                  first_label=wk['first'], last_label=wk['last'],
                                  linear=bool(wk['maxres'] < 0.5))
            if wk['maxres'] >= 0.5:
                rec['warnings'].append(f'x axis not linear in week (fit residual {wk["maxres"]:.2f} wk)')
        else:
            rec['warnings'].append('fewer than 3 readable x labels')
        rec['x_labels'] = [t for _, t in wk['labels']] if wk else []
        rec['n_xticks'] = len(ticks)

        def weeks_of(xs):
            """x -> week number. Round to the integer week FIRST, then wrap: a raw
            week of 52.9999 rounds to 53 and ((53-1)%52)+1 = 1, but wrapping the
            float first gave 52.9999 -> 53, a week number that does not exist."""
            if not wk:
                return [None] * len(xs)
            out = []
            for x in xs:
                wi = int(round(wk['c'] * x + wk['d']))
                out.append(((wi - 1) % 52) + 1)
            return out

        def align(xs):
            """how far the data grid sits from whole weeks (0 = perfectly aligned)"""
            if not wk or not xs:
                return None
            return max(abs(wk['c'] * x + wk['d'] - round(wk['c'] * x + wk['d'])) for x in xs)

        def name_for(col):
            if col is None:
                return None
            for c, entries in lm.items():
                if all(abs(c[i] - col[i]) < 0.02 for i in range(3)):
                    return entries[0]['text']
            return None

        for s in polys:
            col = tuple(round(c, 3) for c in s['color']) if s['color'] else None
            name = name_for(col)
            use_sec = bool(name and '%' in name and fr
                           and rec['axes']['secondary'].get('is_percent'))
            a, b = (fr['a'], fr['b']) if use_sec else (fl['a'], fl['b'])
            rec['series'].append(dict(kind='line', color=col, label=name,
                                      axis='secondary' if use_sec else 'primary',
                                      n_points=len(s['pts']),
                                      values=[round(a * y + b, 1) for _, y in s['pts']],
                                      weeks=weeks_of([x for x, _ in s['pts']]),
                                      week_align=round(align([x for x, _ in s['pts']]) or 0, 3)))
        for s in bars:
            col = tuple(round(c, 3) for c in s['color'])
            name = name_for(col)
            use_sec = bool(name and '%' in name and fr
                           and rec['axes']['secondary'].get('is_percent'))
            a, b = (fr['a'], fr['b']) if use_sec else (fl['a'], fl['b'])
            rec['series'].append(dict(kind='bar', color=col, label=name,
                                      axis='secondary' if use_sec else 'primary',
                                      n_points=len(s['rects']),
                                      values=[round(a * r[1] + b, 1) for r in s['rects']],
                                      weeks=weeks_of([(r[0] + r[2]) / 2 for r in s['rects']]),
                                      week_align=round(align([(r[0] + r[2]) / 2 for r in s['rects']]) or 0, 3)))
        if not any(s['label'] for s in rec['series']) and rec['series']:
            rec['warnings'].append('no series matched a legend swatch')
        out.append(rec)
    return out


def doc_date(p):
    m = re.search(r'(20\d\d).*?[Ww](?:eek)?[-_ ]?(\d{1,2})', p.name)
    if m:
        return f'{m.group(1)} W{int(m.group(2)):02d}'
    m = re.search(r'(20\d\d)', p.name)
    return m.group(1) if m else ''


def render_md(p, charts, pages_text, meta):
    L = [f'# ism {meta["date"]} - {p.stem}', '',
         f'source: ismreport.com (Metal Expert) | file: `{p.as_posix()}` | '
         f'pages: {meta["pages"]} | charts: {len(charts)} | extracted: {meta["ts"]}', '']
    if meta.get('warnings'):
        L += ['**WARNINGS**: ' + '; '.join(meta['warnings']), '']
    for i, ch in enumerate(charts, 1):
        L += [f'## Chart {i}: {ch["title"] or "(untitled)"}', '']
        for an, ax in ch.get('axes', {}).items():
            unit = 'percent' if ax.get('is_percent') else 'absolute'
            L.append(f'- axis `{an}` ({unit}, labels on the {ax["side"]}): '
                     f'tick values {ax["raw"]} -> fit value = {ax["a"]}*y + {ax["b"]} '
                     f'({ax["n"]} ticks, max residual {ax["maxres"]} = {ax["maxres_pct"]}% of span, '
                     f'{"VERIFIED" if ax["verified"] else "UNVERIFIED"})')
        xs = ch.get('x_scale')
        if xs:
            L.append(f'- x axis: {ch["n_xticks"]} tick marks, weeks {xs["first_label"]}..{xs["last_label"]} '
                     f'from {xs["n"]} printed labels; week = {xs["c"]:.6f}*x + {xs["d"]:.2f} '
                     f'(max residual {xs["maxres_weeks"]} weeks, '
                     f'{"LINEAR" if xs["linear"] else "NOT LINEAR"})')
        L.append('')
        ser = ch.get('series', [])
        if not ser:
            L += ['(no series found)', '']
            continue
        for s in ser:
            L.append(f'- series {s["label"] or "(UNLABELLED - no legend swatch matched)"} '
                     f'[{s["kind"]}, {s["n_points"]} pts, axis {s["axis"]}, color {s["color"]}]')
        L.append('')
        weeks = [s['weeks'] for s in ser]
        n = max(len(w) for w in weeks)
        hdr = ['week'] + [f'{s["label"] or "unlabelled"}' for s in ser]
        L.append('| ' + ' | '.join(hdr) + ' |')
        L.append('|' + '---|' * len(hdr))
        for j in range(n):
            wv = next((w[j] for w in weeks if j < len(w) and w[j] is not None), None)
            wk = '' if wv is None else str(wv)
            cells = [str(s['values'][j]) if j < len(s['values']) else '' for s in ser]
            L.append('| ' + wk + ' | ' + ' | '.join(cells) + ' |')
        L.append('')
    for pi, t in pages_text:
        L += [f'## Page {pi + 1} text', '', t.strip(), '']
    return '\n'.join(L)


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return dict(done=[], failed={}, started=None)


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--docs', nargs='*')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st = load_state() if a.resume else dict(done=[], failed={}, started=None)
    st['started'] = st.get('started') or __import__('datetime').datetime.now().isoformat(timespec='seconds')
    docs = [Path(d) for d in a.docs] if a.docs else sorted(ROOT.rglob('*.pdf'))
    if a.limit:
        docs = docs[:a.limit]
    done = set(st['done'])
    todo = [p for p in docs if p.as_posix() not in done]
    print(f'ism: {len(docs)} docs total, {len(todo)} to do (resume={a.resume})', flush=True)
    import datetime
    for i, p in enumerate(todo, 1):
        key = p.as_posix()
        try:
            with pymupdf.open(p) as d:
                pages_text = []
                charts = []
                for pi, pg in enumerate(d):
                    charts += [dict(c, page=pi + 1) for c in analyse_page(pg)]
                    pages_text.append((pi, pg.get_text()))
                npages = d.page_count
            meta = dict(date=doc_date(p), pages=npages, ts=datetime.datetime.now().isoformat(timespec='seconds'),
                        warnings=[])
            bad = [c for c in charts if not all(ax.get('verified') for ax in c.get('axes', {}).values())]
            if bad:
                meta['warnings'].append(f'{len(bad)} chart(s) with an UNVERIFIED axis scale')
            unlab = sum(1 for c in charts for s in c.get('series', []) if not s.get('label'))
            if unlab:
                meta['warnings'].append(f'{unlab} series with no legend swatch (left unlabelled)')
            md = render_md(p, charts, pages_text, meta)
            (out / (p.stem + '.md')).write_text(md, encoding='utf-8')
            (out / (p.stem + '.charts.json')).write_text(
                json.dumps(dict(file=key, date=meta['date'], pages=npages, charts=charts,
                                warnings=meta['warnings']), indent=1), encoding='utf-8')
            st['done'].append(key)
            if i % 10 == 0 or i == len(todo):
                save_state(st)
            print(f'  [{i}/{len(todo)}] {p.name} pages={npages} charts={len(charts)} '
                  f'series={sum(len(c.get("series", [])) for c in charts)} warn={meta["warnings"]}', flush=True)
        except Exception as e:
            st['failed'][key] = f'{type(e).__name__}: {e}'
            save_state(st)
            print(f'  [{i}/{len(todo)}] FAIL {p.name}: {type(e).__name__}: {e}', flush=True)
            traceback.print_exc()
    save_state(st)
    print(f'DONE done={len(st["done"])} failed={len(st["failed"])}', flush=True)


if __name__ == '__main__':
    main()
