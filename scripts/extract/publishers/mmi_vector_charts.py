"""Read MMi Daily Iron Ore Report charts from their vector geometry.

The MMi PDFs draw every chart as vector paths: the series are polylines (lines) or filled
rectangles (bars), the y axis carries numeric tick labels in the text layer and gridlines in
the drawing layer, and the x axis carries tick marks plus date labels that are either text or
glyph outlines. Values are computed, not eyeballed:

  y   linear fit of tick-label value against the exact gridline y it labels
  x   the tick marks (line charts) or the bar centres (bar charts)
  t   the date label at each tick: text when present, else OCR of that label's glyph path drawn
      alone, then forced onto an even month sequence (one misread cannot shift a row)

Each chart is self-checked (calibration residual, tick/label count, date sequence); a chart that
fails a check returns None and the caller writes no table, so no value is ever guessed. The
values remain readings of a chart, so callers must label them as estimates.

OCR results are cached by glyph shape in mmi_label_glyphs.json, so CI (no Tesseract) reuses them.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pymupdf

GLYPH_CACHE = Path(__file__).with_name("mmi_label_glyphs.json")
GRID = (0.85, 0.85, 0.85)
FRAME = (0.75, 0.0, 0.0)
NUM = re.compile(r"^-?[\d,]+(\.\d+)?%?$")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

_cache: dict | None = None
_cache_dirty = False


def _close(c, ref, tol=0.03):
    return c is not None and len(c) >= 3 and all(abs(a - b) < tol for a, b in zip(c, ref))


def _load_cache():
    global _cache
    if _cache is None:
        _cache = json.loads(GLYPH_CACHE.read_text(encoding="utf-8")) if GLYPH_CACHE.exists() else {}
    return _cache


def save_glyph_cache():
    global _cache_dirty
    if _cache is not None and _cache_dirty:
        GLYPH_CACHE.write_text(json.dumps(_cache, indent=0, sort_keys=True), encoding="utf-8")
        _cache_dirty = False


_DRAW = {"doc": None, "pages": {}}


def _drawings(page):
    """page.get_drawings() is the dominant cost; every chart on a page reuses one read."""
    if _DRAW["doc"] is not page.parent:
        _DRAW["doc"], _DRAW["pages"] = page.parent, {}
    if page.number not in _DRAW["pages"]:
        _DRAW["pages"][page.number] = page.get_drawings()
    return _DRAW["pages"][page.number]


def _frames(page):
    return [d["rect"] for d in _drawings(page)
            if d["type"] == "s" and _close(d.get("color"), FRAME) and d["rect"].height > 60]


def _panel(page, title, legend=None, bars=False):
    """Chart frame under its title. 2021-22 PDFs draw titles as glyphs: then the frame that
    holds the legend text, or (bar charts) the frame that holds a multi-bar fill."""
    hits = page.search_for(title)
    if not hits:
        frames = _frames(page)
        if legend:
            for lr in page.search_for(legend):
                inside = [f for f in frames if f.contains(lr)]
                if inside:
                    return min(inside, key=lambda f: f.width * f.height)
        if bars:
            cands = [f for f in frames if any(
                d["type"] == "f" and len(d["items"]) >= 10 and all(it[0] == "re" for it in d["items"])
                and not _close(d.get("fill"), (1.0, 1.0, 1.0)) and f.x0 < d["rect"].x1 <= f.x1 + 2  # clipped on the left only
                and f.y0 - 2 <= d["rect"].y0 and d["rect"].y1 <= f.y1 + 2 for d in _drawings(page))]
            if len(cands) == 1:
                return cands[0]
        return None
    t = hits[0]
    cx = (t.x0 + t.x1) / 2
    best = None
    for d in _drawings(page):
        r = d["rect"]
        if d["type"] == "s" and _close(d.get("color"), FRAME) and r.x0 - 2 <= cx <= r.x1 + 2 \
                and t.y1 - 4 <= r.y0 <= t.y1 + 10 and r.height > 60:
            if best is None or r.y0 < best.y0:
                best = r
    return best


def _text_lines(page, clip):
    out = []
    for b in page.get_text("dict", clip=clip)["blocks"]:
        for l in b.get("lines", []):
            s = "".join(sp["text"] for sp in l["spans"]).strip()
            if s:
                out.append((pymupdf.Rect(l["bbox"]), (round(l["dir"][0], 2), round(l["dir"][1], 2)), s))
    return out


def _y_calibration(lines, plot_x0, grid_ys):
    ticks = []
    for r, dr, s in lines:
        if dr == (1.0, 0.0) and r.x1 <= plot_x0 + 3 and NUM.match(s.replace(" ", "")):
            yc = (r.y0 + r.y1) / 2
            near = [g for g in grid_ys if abs(g - yc) < 3]
            if near:  # gridlines are exact; label boxes carry font-metric offsets
                yc = min(near, key=lambda g: abs(g - yc))
            ticks.append((yc, float(s.replace(",", "").rstrip("%"))))
    if len(ticks) < 3:
        return None
    n = len(ticks)
    my = sum(t[0] for t in ticks) / n
    mv = sum(t[1] for t in ticks) / n
    den = sum((t[0] - my) ** 2 for t in ticks)
    if den == 0:
        return None
    a = sum((t[0] - my) * (t[1] - mv) for t in ticks) / den
    b = mv - a * my
    span = max(t[1] for t in ticks) - min(t[1] for t in ticks)
    if span <= 0 or max(abs(a * y + b - v) for y, v in ticks) > 0.005 * span:
        return None
    return a, b, span


def _glyph_key(d):
    r = d["rect"]
    parts = []
    for it in d["items"]:
        for p in it[1:]:
            if isinstance(p, pymupdf.Point):
                parts.append(f"{p.x - r.x0:.1f},{p.y - r.y0:.1f}")
            elif isinstance(p, pymupdf.Rect):
                parts.append(f"{p.x0 - r.x0:.1f},{p.y0 - r.y0:.1f},{p.x1 - r.x0:.1f},{p.y1 - r.y0:.1f}")
        parts.append(it[0])
    return hashlib.sha1(";".join(parts).encode()).hexdigest()[:20]


def _ocr_glyph(d, angle):
    global _cache_dirty
    cache = _load_cache()
    key = f"{_glyph_key(d)}@{angle}"
    if key in cache:
        return cache[key]
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    tess = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tess.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tess)
    r = d["rect"]
    doc = pymupdf.open()
    pg = doc.new_page(width=r.width + 4, height=r.height + 4)
    sh = pg.new_shape()
    off = pymupdf.Point(r.x0 - 2, r.y0 - 2)
    for it in d["items"]:
        if it[0] == "l":
            sh.draw_line(it[1] - off, it[2] - off)
        elif it[0] == "c":
            sh.draw_bezier(it[1] - off, it[2] - off, it[3] - off, it[4] - off)
        elif it[0] == "re":
            sh.draw_rect(it[1] - (off.x, off.y, off.x, off.y))
    sh.finish(fill=(0, 0, 0), color=None, even_odd=d.get("even_odd", True), closePath=False)
    sh.commit()
    im = Image.open(io.BytesIO(pg.get_pixmap(dpi=1200).tobytes("png"))).convert("L")
    im = im.rotate(-angle, expand=True, fillcolor=255, resample=Image.BICUBIC)
    try:
        txt = pytesseract.image_to_string(im, config="--psm 7").strip().replace(" ", "")
    except Exception:
        return None
    cache[key] = txt
    _cache_dirty = True
    return txt


def parse_label(s):
    s = (s or "").replace(" ", "").strip(".,")
    for fmt in ("%d-%b-%y", "%b-%y", "%Y/%m/%d", "%Y/%m", "%d-%b-%Y", "%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _months(d):
    return d.year * 12 + d.month - 1


def _add_months(d, k, day):
    return _month_date(_months(d) + k, day)


def _eom(d):
    return (d + timedelta(days=1)).day == 1


def _month_date(m, day):
    """Date in month index m; day 0 = the last day of the month (month-end axis labels)."""
    first = date(m // 12, m % 12 + 1, 1)
    last = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
    return first.replace(day=last if day == 0 else day)


def _label_day(ds):
    """Common day of the labels: 0 when every label is a month end (31-Jan, 28-Feb, 31-Mar ...)."""
    ds = list(ds)
    if ds and all(_eom(d) for d in ds) and max(d.day for d in ds) >= 30:
        return 0
    return Counter(d.day for d in ds).most_common(1)[0][0]


def _regularise(raw, fmt_day):
    """raw: parsed dates or None per label. Force an even month step; None if inconsistent."""
    idx = [(i, d) for i, d in enumerate(raw) if d]
    if len(idx) < max(2, int(0.6 * len(raw))):
        return None
    steps = Counter()
    for (i, a), (j, b) in zip(idx, idx[1:]):
        diff = _months(b) - _months(a)
        if diff % (j - i) == 0:
            steps[diff // (j - i)] += 1
    if not steps:
        return None
    step = steps.most_common(1)[0][0]
    if step <= 0:
        return None
    anchors = Counter()
    for i, d in idx:
        anchors[_months(d) - i * step] += 1
    base, votes = anchors.most_common(1)[0]
    if votes < 0.6 * len(raw):
        return None
    day = _label_day(d for _, d in idx) if fmt_day else 1
    return [_month_date(base + i * step, day) for i in range(len(raw))]


def _fmt(d, with_day):
    return f"{d.day}-{MONTHS[d.month - 1]}-{d.strftime('%y')}" if with_day else f"{MONTHS[d.month - 1]}-{d.strftime('%y')}"


def _x_labels(page, draws, lines, plot, angle_hint):
    labs = [(r, s) for r, dr, s in lines if r.y0 >= plot.y1 - 2 and parse_label(s)]
    if labs:
        return sorted(((r.x0 + r.x1) / 2, r, s) for r, s in labs), "text"
    # glyph outlines are curves, or (some 2021-26 PDFs) many short straight segments
    glyphs = [d for d in draws if d["type"] == "f" and d["items"]
              and (d["items"][0][0] == "c" or (d["items"][0][0] == "l" and len(d["items"]) >= 20))
              and d["rect"].y0 >= plot.y1 - 2 and d["rect"].height > 5]
    glyphs.sort(key=lambda g: g["rect"].x0)
    n = len(glyphs)
    # Glyph labels rarely repeat byte-for-byte, so OCR is the cost. Labels are evenly spaced dates:
    # read from both ends inward and stop once >=4 readings, covering both ends, fit one start + step.
    order = list(dict.fromkeys([0, 1, n - 1, n - 2, 2, n - 3] + list(range(3, n - 3))))
    order = [i for i in order if 0 <= i < n]
    texts, parsed, fit = {}, {}, None
    for i in order:
        s = None
        for ang in angle_hint:
            s = _ocr_glyph(glyphs[i], ang)
            if parse_label(s):
                break
        texts[i] = s or ""
        if parse_label(s):
            parsed[i] = parse_label(s)
        fit = _lazy_fit(parsed, n)
        if fit:
            break
    if fit:
        base, step, day = fit
        with_day = any(re.match(r"^[0-9]", texts[i]) for i in parsed)
        for i in range(n):
            if i not in texts:
                m = base + i * step
                texts[i] = _fmt(_month_date(m, day), with_day)
    out = [((g["rect"].x0 + g["rect"].x1) / 2, g["rect"], texts.get(i, "")) for i, g in enumerate(glyphs)]
    return out, "glyph"


def _lazy_fit(parsed, n):
    """(base_month, step, day) when >=4 parsed labels incl. both ends agree; else None."""
    if len(parsed) < 4 or not (set(parsed) & {0, 1}) or not (set(parsed) & {n - 1, n - 2}):
        return None
    idx = sorted(parsed.items())
    (i0, d0), (i1, d1) = idx[0], idx[-1]
    diff = _months(d1) - _months(d0)
    if i1 == i0 or diff % (i1 - i0):
        return None
    step = diff // (i1 - i0)
    base = _months(d0) - i0 * step
    if step <= 0 or any(_months(d) != base + i * step for i, d in idx):
        return None
    day = _label_day(d for _, d in idx)
    if any(_month_date(_months(d), day) != d for _, d in idx):
        return None
    return base, step, day


def _polyline(d):
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            if not pts or abs(pts[-1][0] - it[1].x) > 1e-6 or abs(pts[-1][1] - it[1].y) > 1e-6:
                pts.append((it[1].x, it[1].y))
            pts.append((it[2].x, it[2].y))
    return pts


def _y_at(pts, x):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if min(x0, x1) - 1e-6 <= x <= max(x0, x1) + 1e-6:
            return y1 if abs(x1 - x0) < 1e-9 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def _legend(draws, lines, plot):
    legend = {}
    for d in draws:
        r = d["rect"]
        if r.y0 <= plot.y1 or r.height > 6 or r.width > 30:
            continue
        col = d.get("color") if d["type"] == "s" else d.get("fill")
        if col is None:
            continue
        cand = [(l[0].x0 - r.x1, l[2]) for l in lines
                if l[1] == (1.0, 0.0) and abs((l[0].y0 + l[0].y1) / 2 - (r.y0 + r.y1) / 2) < 5 and -1 <= l[0].x0 - r.x1 < 15]
        if cand:
            legend[tuple(round(c, 2) for c in col)] = min(cand)[1]
    return legend


def read_line_chart(page, title, legend=None):
    """-> {"cols": [...], "rows": [(label, date, [values])], "last": [values]} or None."""
    panel = _panel(page, title, legend=legend)
    if panel is None:
        return None
    alld = _drawings(page)
    draws = [d for d in alld if panel.contains(d["rect"])]
    # Older layouts draw each series from before the axis minimum and clip it, so the path
    # box can stick out of the panel on the left: select by vertical extent instead.
    series = [d for d in alld if d["type"] == "s" and len(d["items"]) > 40 and not _close(d.get("color"), GRID)
              and d["rect"].y0 >= panel.y0 - 2 and d["rect"].y1 <= panel.y1 + 2
              and panel.x0 < d["rect"].x1 <= panel.x1 + 2]
    grid = [d for d in draws if d["type"] == "s" and _close(d.get("color"), GRID)]
    if not series or not grid:
        return None
    plot = pymupdf.Rect(min(d["rect"].x0 for d in grid), min(d["rect"].y0 for d in series),
                        max(d["rect"].x1 for d in grid), max(d["rect"].y1 for d in series + grid))
    hgrid = {round(it[1].y, 2) for d in grid for it in d["items"]
             if it[0] == "l" and abs(it[1].y - it[2].y) < 0.05 and abs(it[1].x - it[2].x) > 20}
    plot.y1 = max(hgrid) if hgrid else plot.y1
    lines = _text_lines(page, panel)
    cal = _y_calibration(lines, plot.x0, sorted(hgrid))
    if not cal:
        return None
    a, b, _ = cal
    ticks = sorted({round(it[1].x, 2) for d in grid for it in d["items"]
                    if it[0] == "l" and abs(it[1].x - it[2].x) < 0.05 and 0.5 < abs(it[1].y - it[2].y) < 6
                    and min(it[1].y, it[2].y) >= plot.y1 - 0.5})
    labels, kind = _x_labels(page, draws, lines, plot, (45, 90, -45))
    if ticks and labels and len(ticks) != len(labels) and kind == "glyph":
        # A tick with no label (the axis end): a rotated label ends at its tick, so pair each label
        # with that tick and drop the unlabelled one. Every label must claim its own tick.
        pick = [min(ticks, key=lambda t: abs(t - r.x1)) for _, r, _ in labels]
        if len(set(pick)) != len(pick) or any(abs(t - r.x1) > 3 for t, (_, r, _) in zip(pick, labels)):
            return None
        ticks = pick
    if ticks and labels and len(labels) < len(ticks):
        # Ticks with no readable label (axis ends, or labels broken up in the text layer): a label sits
        # a small fixed offset from its own tick (the axis is day-scaled, months differ in width), so
        # exactly one offset under half a tick pitch must put every label on its own tick. Unlabelled
        # ticks keep a None label and take their date from the month sequence.
        pitch = sorted(b - a for a, b in zip(ticks, ticks[1:]))[(len(ticks) - 1) // 2]
        fits = []
        for o in sorted({round(labels[0][0] - t, 2) for t in ticks}):
            if abs(o) >= pitch / 2:
                continue
            at = [min(range(len(ticks)), key=lambda i: abs(x - o - ticks[i])) for x, _, _ in labels]
            offs = [x - ticks[i] for (x, _, _), i in zip(labels, at)]
            if len(set(at)) == len(at) and max(offs) - min(offs) < 1.0 and at not in fits:
                fits.append(at)
        if len(fits) == 1:
            slot = dict(zip(fits[0], labels))
            labels = [slot.get(i, (t, None, None)) for i, t in enumerate(ticks)]
    if not ticks or len(ticks) != len(labels):
        return None
    raw = [parse_label(s) for _, _, s in labels]
    with_day = sum(1 for _, _, s in labels if re.match(r"^\d", s or "")) > sum(1 for _, _, s in labels if s) / 2
    dates = _regularise(raw, with_day)
    if dates is None:
        return None
    # The axis is day-scaled, so a printed label (28-Feb, then 31-Mar) is the tick's own date: keep it
    # where it agrees with the month sequence.
    dates = [r if r and _months(r) == _months(d) else d for r, d in zip(raw, dates)]
    legend = _legend(draws, lines, plot)
    cols, polys = [], []
    # Long series are drawn as several paths of the same colour (e.g. 200 nodes each): join the pieces
    # left to right, only where each piece starts exactly where the previous one ended.
    by_colour = {}
    for d in sorted(series, key=lambda d: d["rect"].x0):
        by_colour.setdefault(tuple(round(c, 2) for c in d["color"]), []).append(_polyline(d))
    for key, pieces in by_colour.items():
        if key not in legend:
            return None
        pts = pieces[0]
        for nxt in pieces[1:]:
            if not nxt or abs(nxt[0][0] - pts[-1][0]) > 0.5 or abs(nxt[0][1] - pts[-1][1]) > 0.5:
                return None
            pts = pts + nxt[1:]
        cols.append(legend[key])
        polys.append(pts)
    if len(set(cols)) != len(cols):
        return None
    rows = []
    for x, dt in zip(ticks, dates):
        vals = []
        for pts in polys:
            y = _y_at(pts, x)
            vals.append(None if y is None else round(a * y + b, 2))
        rows.append((_fmt(dt, with_day), dt, vals))
    last = [round(a * max((p for p in pts if p[0] <= plot.x1 + 1), key=lambda p: p[0])[1] + b, 2) for pts in polys]
    return {"cols": cols, "rows": rows, "last": last}


def _rects(d):
    """Filled rectangles of a fill path: "re" items and/or closed 4-line axis-aligned quads (some PDFs
    draw the bars as line paths, or mix both). None when the path holds anything else."""
    its, out, k = d["items"], [], 0
    while k < len(its):
        if its[k][0] == "re":
            out.append(its[k][1])
            k += 1
            continue
        quad = its[k:k + 4]
        if len(quad) < 4 or any(it[0] != "l" for it in quad):
            return None
        pts = [it[1] for it in quad] + [quad[3][2]]
        if abs(pts[4].x - pts[0].x) > 0.05 or abs(pts[4].y - pts[0].y) > 0.05:
            return None
        xs, ys = {round(p.x, 1) for p in pts}, {round(p.y, 1) for p in pts}
        if len(xs) != 2 or len(ys) != 2:
            return None
        out.append(pymupdf.Rect(min(xs), min(ys), max(xs), max(ys)))
        k += 4
    return out or None


def read_bar_chart(page, title):
    """Single-series monthly bar chart -> {"rows": [(label, date, value)], "baseline_value": v} or None."""
    panel = _panel(page, title, bars=True)
    if panel is None:
        return None
    alld = _drawings(page)
    draws = [d for d in alld if panel.contains(d["rect"])]
    grid = [d for d in draws if d["type"] == "s" and _close(d.get("color"), GRID)]
    if not grid:
        return None
    gx0, gx1 = min(d["rect"].x0 for d in grid), max(d["rect"].x1 for d in grid)
    bars = []
    by_fill = {}  # one series may be split over several paths of the same fill
    for d in alld:  # older layouts draw bars from before the axis start and clip them
        rects = _rects(d) if d["type"] == "f" else None
        if rects and d["rect"].intersects(panel) and not _close(d.get("fill"), (1.0, 1.0, 1.0)):
            inside = [r for r in rects if gx0 <= (r.x0 + r.x1) / 2 <= gx1]
            by_fill.setdefault(tuple(round(c, 2) for c in d["fill"]), []).extend(inside)
    for rs in by_fill.values():
        if len(rs) > len(bars):
            bars = rs
    if len(bars) < 3:
        return None
    bars.sort(key=lambda r: r.x0)
    hgrid = sorted({round(it[1].y, 2) for d in grid for it in d["items"]
                    if it[0] == "l" and abs(it[1].y - it[2].y) < 0.05 and abs(it[1].x - it[2].x) > 20})
    base = Counter(round(r.y1, 1) for r in bars).most_common(1)[0][0]
    plot = pymupdf.Rect(gx0, panel.y0, gx1, base)
    lines = _text_lines(page, panel)
    cal = _y_calibration(lines, gx0, hgrid)
    if not cal:
        return None
    a, b, _ = cal
    labels, kind = _x_labels(page, draws, lines, plot, (45, 90, -45))
    if not labels:
        return None
    cxs = [(r.x0 + r.x1) / 2 for r in bars]
    # Bars sit on an even monthly grid; a month can have no bar (nothing drawn), so place each bar on
    # its slot of the grid instead of counting bars.
    # Count slots gap by gap (bar spacing alternates by a fraction of a point), then fit the pitch
    # over the whole axis.
    step = sorted(q - p for p, q in zip(cxs, cxs[1:]))[(len(cxs) - 2) // 2]
    slot = [0]
    for p, q in zip(cxs, cxs[1:]):
        slot.append(slot[-1] + round((q - p) / step))
    if slot[-1] == 0:
        return None
    pitch = (cxs[-1] - cxs[0]) / slot[-1]
    if len(set(slot)) != len(slot) or any(abs((cx - cxs[0]) / pitch - k) > 0.15 for cx, k in zip(cxs, slot)):
        return None
    marks = []  # (slot, parsed date)
    for cx, r, s in labels:
        anchor = r.x1 - 1 if kind == "glyph" else cx  # 45-degree glyph labels end at their bar
        k = round((anchor - cxs[0]) / pitch)
        if abs(cxs[0] + k * pitch - anchor) > pitch / 2:
            return None
        marks.append((k, parse_label(s)))
    if len({k for k, _ in marks}) != len(marks):
        return None
    with_day = sum(1 for _, _, s in labels if re.match(r"^\d", s or "")) > len(labels) / 2
    # Each readable label votes for the month of slot 0; a misread label is outvoted, not trusted.
    parsed = [(k, d) for k, d in marks if d]
    if len(parsed) < max(2, 0.6 * len(marks)):
        return None
    m0, votes = Counter(_months(d) - k for k, d in parsed).most_common(1)[0]
    if votes < 0.6 * len(marks):
        return None
    good = [d for k, d in parsed if _months(d) - k == m0]
    day = (_label_day(good) if with_day else 1)
    rows = []
    for k, r in zip(slot, bars):
        dt = _month_date(m0 + k, day)
        top = r.y0 if abs(r.y1 - base) < 1 else r.y1  # negative bars hang below the base
        rows.append((_fmt(dt, with_day), dt, round(a * top + b, 2)))
    return {"rows": rows, "baseline_value": round(a * base + b, 2)}


CHARTS = {
    # key: (title, legend text that identifies the frame when the title is a glyph, kind)
    "freight": ("DRY BULK FREIGHT RATES", "C5 - W. Australia - Qingdao", "line"),
    "comparisons": ("IRON ORE INDEX COMPARISONS", "IOPI62 (equivalent)", "line"),
    "imports": ("TOTAL CHINA IRON ORE IMPORT", None, "bar"),
}


def read_mmi_charts(doc):
    """{"freight": res|None, "comparisons": res|None, "imports": res|None} for one MMi PDF."""
    out = {}
    for key, (title, legend, kind) in CHARTS.items():
        res = None
        for page in doc:
            has_title = bool(page.search_for(title))
            try:  # an inconsistent date axis fails this chart only, not the other charts of the PDF
                if kind == "line" and (has_title or (legend and page.search_for(legend))):
                    res = read_line_chart(page, title, legend=legend)
                elif kind == "bar" and (has_title or page.search_for(CHARTS["freight"][1])):
                    res = read_bar_chart(page, title)
            except ValueError:
                res = None
            if res:
                break
        out[key] = res
    return out


ESTIMATE_NOTES = {
    "vector": "> **Estimate.** The report prints no numbers for this chart. Values are computed from the chart's "
              "vector geometry at each x-axis date label (calibrated on the printed axis ticks; typically within "
              "1% of the axis range).",
    "visual": "> **Approximate.** The report prints no numbers for this chart. Values were read visually from the "
              "chart image by the parser and are rough estimates.",
}


def apply_vector_charts(pdf_path, issue_date, year, comparisons_chart, freight_chart, imports_chart):
    """Replace the parser's chart rows (lists, in place) with vector readings where the chart reads
    cleanly. Returns {"comparisons"|"freight"|"imports": "vector"|"visual"} for the rows that remain."""
    src = {}
    try:
        doc = pymupdf.open(pdf_path)
        res = read_mmi_charts(doc)
    except Exception:
        res = {}
    name = Path(pdf_path).name
    r = res.get("freight")
    if r:
        c5 = next((i for i, c in enumerate(r["cols"]) if c.startswith("C5")), None)
        c3 = next((i for i, c in enumerate(r["cols"]) if c.startswith("C3")), None)
        if c5 is not None and c3 is not None:
            freight_chart[:] = [{"date": issue_date, "chart_date": lab, "c5_waust_usd_t": v[c5], "c3_tubarao_usd_t": v[c3],
                                 "year": year, "source_file": name, "value_source": "vector"} for lab, _, v in r["rows"]]
    r = res.get("comparisons")
    if r:
        idx = {c.split(" ")[0].upper(): i for i, c in enumerate(r["cols"])}
        if all(k in idx for k in ("IOSI62", "IOPI62", "IOSI65", "IOPI65")):
            comparisons_chart[:] = [{"date": issue_date, "chart_date": lab, "iosi62_usd_dmt": v[idx["IOSI62"]],
                                     "iopi62_eq_usd_dmt": v[idx["IOPI62"]], "iosi65_usd_dmt": v[idx["IOSI65"]],
                                     "iopi65_eq_usd_dmt": v[idx["IOPI65"]], "year": year, "source_file": name,
                                     "value_source": "vector"} for lab, _, v in r["rows"]]
    r = res.get("imports")
    if r:
        imports_chart[:] = [{"date": issue_date, "period": lab, "volume_mt": v, "year": year, "source_file": name,
                             "value_source": "vector"} for lab, _, v in r["rows"]]
    for key, rows in (("comparisons", comparisons_chart), ("freight", freight_chart), ("imports", imports_chart)):
        if rows:
            src[key] = "vector" if all(x.get("value_source") == "vector" for x in rows) else "visual"
    save_glyph_cache()
    return src
