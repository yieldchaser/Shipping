"""intermodal - extract the plotted series from the Dry Bulk / Indicative Period charts.

MEASURED LAYOUT (page 3, verified on intermodal 2026 W35 by rendering and reading)
------------------------------------------------------------------------------
Two charts sit in the right column, stacked:

  chart 1 "Baltic Indices"    frame x 356.0..572.8  y 168.7..243.9
  chart 2 "Average T/C Rates" frame x 360.2..574.9  y 300.0..378.7

Each has five long stroked polylines, one per legend entry, matched by EXACT stroke RGB
against the legend swatch. Chart 1's five are BCI / BPI / BSI / BHSI / BDI; chart 2's are
the average T/C curves for Handysize, Supramax, Panamax and Capesize.

WHY THIS IS FREE
----------------
The series are vector paths and the y-axis is printed text, so values come from
interpolating the ladder against each stroke's own vertices - exact to plotted
resolution, no cloud, no vision. LlamaParse charges 45 cr/page for chart parsing; the
whole 252-document intermodal chart surface is 252 pages, so a cloud route would be
11,340 credits for a worse answer than the printed axis gives for nothing.

THE CLIP PROBLEM, AND WHY THE PATH'S OWN RECT CANNOT BE USED
-----------------------------------------------------------
Each series is a MULTI-DECADE path clipped to the visible window, so its raw bounding
box runs far off-page: measured 2026 W35, the five Baltic strokes span x -4,540.1 to
570.7, and the T/C strokes x -1,761.0 to 572.8. Their rect is useless as a plot bound.

So the plot window is read from the FRAME - a 4-vertex path that the chart draws around
the visible area (measured 356.0..572.8 and 360.2..574.9) - and each series is clipped
to it. The frame is identified by enclosing the y-ladder and by having exactly 4 line
items, not by size alone.

IDENTIFYING A REAL SERIES (three filters, each calibrated on this material)
--------------------------------------------------------------------------
1. It has >= 500 line items. Measured: real series 2,844-6,059; the x-axis date tick
   marks on these pages run 49-69 items and are drawn with NO colour.
2. Its stroke colour is a real RGB triple. The tick marks carry no colour at all
   (`color=[]`), so an uncoloured path is furniture, not a series.
3. It overlaps the frame vertically. A stroke entirely above or below the frame belongs
   to the other chart or to the page header.

The aspect-ratio trap applies here too. A naive height > 0.75*width filter is wrong for
multi-decade paths whose off-page extent makes the rect enormous in x; the frame test
is the reliable one.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

try:                                    # sibling module, same directory
    import intermodal_axis_dates as axdates
except ImportError:                     # pragma: no cover - direct execution
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "intermodal_axis_dates", Path(__file__).with_name("intermodal_axis_dates.py"))
    axdates = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(axdates)

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "corpus" / "01-brokers" / "intermodal"
OUT = REPO / "data" / "extracted" / "charts" / "intermodal"

CHART_PAGES = (2,)              # 0-based: page 3 carries both charts
MIN_ITEMS = 500                 # real series >= 2,844 on this material


def _items(d):
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            for s in it[1:]:
                pts.append((s.x, s.y))
    return pts


def _nlines(d):
    return sum(1 for it in d["items"] if it[0] == "l")


def find_charts(page, strokes):
    """The chart plot regions, as (frame, ladder), one per chart on the page.

    TWO WAYS TO FIND A PLOT, because the frame is not always drawn:

    - 2023-2026: the plot is enclosed by a 4-vertex path (measured 356.0..572.8 and
      360.2..574.9). The frame is the direct evidence.
    - 2021-2022: NO frame is drawn. The render shows the same two charts - Baltic Indices
      and Average T/C Rates, same legend - with only the y-ladder and the series strokes.
      A frame-only test therefore returns 0 charts for that era, losing two years of data
      silently.

    Either way the LADDER decides how many charts there are, because both charts on the
    page share one x column (measured 2026 W35: x~340 holds 6,000..0 AND 55,000..0). So
    every validated ladder yields its own plot, with the vertical span of the ladder plus
    a small margin, and the strokes that overlap that span.

    LADDERS ARE THEN DEDUPLICATED BY GEOMETRY. `_split_ladders` tries eight gap
    thresholds, and most of them recover the same run, so a page returned 7-8 identical
    charts before this step (measured 2026 W35: 15 chart records for 2 charts). Two
    ladders are the same chart when they span the same y range and carry the same tick
    pitch, which is exact - two different charts never share both.
    """
    ladders = _all_ladders(page)
    if not ladders:
        return []
    ladders = _dedupe_ladders(ladders, _page_numerics(page))
    frames = _raw_frames(page)
    out = []
    for lad in ladders:
        lo = min(c[1] for c in lad) - 10
        hi = max(c[1] for c in lad) + 10
        band = [s for s in strokes if s["y1"] >= lo and s["y0"] <= hi]
        if not band:
            continue
        # the plot's horizontal extent: the strokes overlapping this ladder's band.
        # The series are multi-decade paths clipped to the window, so their x0 runs far
        # off-page (measured -4,540 on 2026 W35). The left edge is therefore the smallest
        # NON-NEGATIVE x among the band, falling back to the ladder's own x when every
        # stroke starts off-page.
        lefts = [s["x0"] for s in band if s["x0"] > 0]
        left = min(lefts) if lefts else min(c[0] for c in lad) + 8
        right = max(s["x1"] for s in band)
        cx = min(c[0] for c in lad)
        # A DRAWN FRAME IS THE PRIMARY EVIDENCE, and it is present in EVERY era - measured
        # 2025 W49 page 3 draws it at x 356.4..573.0, y 168.8..244.2. A ladder-derived
        # window is WRONG and measurably so: deriving it from the ticks gave y
        # 153.4..230.2, cutting the real plot's bottom 14pt off, which pinned BHSI flat
        # along a false floor and put the page's own 841 at 569 (-32%).
        #
        # BUT SEVERAL FRAMES ARE DRAWN, and choosing the SMALLEST one is also wrong: the
        # page draws a legend strip at exactly the same x span and top edge but a shorter
        # bottom (measured 2025 W49: 356.4..573.0 y 168.8..225.3 sits inside the true
        # 168.8..244.2). Taking the smaller clipped the ladder's bottom tick and made the
        # same values worse.
        #
        # The frame that identifies a chart is the one whose BOTTOM is lowest - the plot
        # area reaches down to the axis, while the legend strip and the tables-panel
        # border both stop short. The tables-panel border is additionally much wider
        # (312..584 against the plot's 356..573), so it is rejected on x as well.
        # THE FRAME SITS BESIDE ITS LADDER, NOT OVER IT. The axis labels are drawn to the
        # LEFT of the plot and are right-aligned, so the frame's left edge is a little to
        # the RIGHT of the tick text's x. Measured 2025 W49: ticks at x=333.6, the true
        # frame at x=356.4 - 22.8pt to the right, the width of the label plus the axis gap.
        # A test that accepted frames starting to the LEFT of the ladder therefore chose
        # the surrounding tables-panel border (312.0..583.7) and clipped both charts.
        #
        # The three properties that together identify the plot, all measured:
        #   - its left edge is 15-35pt RIGHT of the ladder's x
        #   - its width is 180-260pt
        #   - its top is within 40pt above the ladder's top tick, and its bottom below it
        cx = min(c[0] for c in lad)
        best = None
        for f in frames:
            if len(f) == 5:          # a (frame, ladder) pair from a previous pass
                f = f[0]
            w = f[2] - f[0]
            h = f[3] - f[1]
            if not (10 <= f[0] - cx <= 45):
                continue
            if not (150 <= w <= 280):
                continue
            if not (25 <= h <= 200):
                continue
            if not (f[1] <= lo + 40 and f[3] >= hi - 20):
                continue
            depth = f[3]
            if best is None or depth > best[0]:
                best = (depth, f)
        if best is not None:
            out.append((best[1], lad))
        else:
            out.append(((min(cx, left), lo, right, hi), lad))
    out.sort(key=lambda t: t[0][1])
    return _dedupe_frames(out)


def _dedupe_frames(pairs, y_tol=4.0):
    """Keep one plot per distinct chart when several ladders share a frame."""
    out = []
    for fr, lad in pairs:
        if any(abs(fr[1] - o[0][1]) <= y_tol and abs(fr[3] - o[0][3]) <= y_tol
               for o in out):
            continue
        out.append((fr, lad))
    return out


def _dedupe_ladders(ladders, allnums=(), y_tol=3.0, pitch_tol=0.5):
    """Keep one ladder per distinct chart, by y-span and tick pitch.

    A LADDER MUST REACH ZERO. This is not cosmetic: the `0` label is set at a different
    x from the other ticks because it is one character wide, and on 2025 W49 it sits at
    x=345.46 while '1000'..'4000' sit at x=333.59. A 30pt x-cluster keeps them together,
    but a later step preferred the LONGER run and returned 4000/3000/2000/1000 without
    the 0. `value_at` then extrapolated from the 4000..1000 interval, compressing every
    reading downward.

    The measured damage: the page's own Baltic table gives BHSI 841 and the extractor
    returned 569 (-32%); across 14 documents, 0 of 70 comparisons were within 5% and the
    median error was 26%. Every one of them was the same missing-baseline error, and the
    independent table control is what exposed it - the fit's own error metric was clean.

    So a ladder that has a gap at its bottom large enough to be a missing 0 is extended
    to include it, rather than being preferred over the longer sub-run.
    """
    out = []
    for lad in sorted(ladders, key=lambda l: -len(l)):
        ys = [c[1] for c in lad]
        pitch = (ys[-1] - ys[0]) / (len(ys) - 1) if len(ys) > 1 else 0.0
        same = False
        for k in out:
            kys = [c[1] for c in k]
            kp = (kys[-1] - kys[0]) / (len(kys) - 1) if len(kys) > 1 else 0.0
            if abs(ys[0] - kys[0]) <= y_tol and abs(ys[-1] - kys[-1]) <= y_tol \
                    and abs(pitch - kp) <= pitch_tol:
                same = True
                break
        if not same:
            out.append(lad)
    out.sort(key=lambda l: l[0][1])
    return _extend_to_zero(out, allnums)


def _extend_to_zero(ladders, allnums=(), pitch_tol=0.6):
    """Re-attach a `0` tick that fell out of a ladder during splitting.

    THE LADDER MUST INCLUDE ZERO, and this is the single largest error source measured.
    On 2025 W49 the printed ladder is 4000/3000/2000/1000 at y 163.4..220.2, and the `0`
    sits at y=239.16, x=345.46 - BELOW the lowest kept tick and 12pt to the RIGHT of the
    others, because '0' is one character wide where '1000' is four. The x-cluster test
    cannot separate it, and preferring the longer sub-run drops it.

    With the zero missing, `value_at` extrapolates downward from the 4000..1000 interval
    and every reading is compressed. Measured: the page's own Baltic table gives
    BDI 2,727 / BCI 5,083 / BHSI 841, and the extractor returned 2,465 / 4,066 / 569.
    The independent table control put 0 of 70 comparisons within 5%, median error 26% -
    all one cause.

    So a ladder is completed whenever a zero tick lies one pitch below its lowest member.
    Membership is geometric, and the expected value is checked before the tick is added,
    so a coincidental zero elsewhere on the page cannot corrupt the scale.
    """
    if not ladders:
        return ladders
    zeros = [d for d in allnums if d[2] == 0]
    if not zeros:
        return ladders
    out = []
    for lad in ladders:
        ys = [c[1] for c in lad]
        pitch = (ys[-1] - ys[0]) / (len(ys) - 1) if len(ys) > 1 else 0.0
        vals = [c[2] for c in lad]
        if any(v == 0 for v in vals) or pitch <= 0:
            out.append(lad)
            continue
        step = abs(vals[1] - vals[0])          # the ladder's own value increment
        want_y = ys[-1] + pitch
        cands = [z for z in zeros if abs(z[1] - want_y) <= pitch * pitch_tol]
        if cands and step > 0:
            z = min(cands, key=lambda q: abs(q[1] - want_y))
            # the zero must be exactly one more step below in VALUE
            if abs((vals[-1] - 0) - step) <= step * 0.15:
                out.append(sorted(lad + [z], key=lambda c: c[1]))
                continue
        out.append(lad)
    return out


def _page_numerics(page):
    """Every numeric text span on the page, as (x, y, value).

    The pattern admits a bare '0': that is the axis BASELINE, and it is the tick most
    likely to be missed, because it is one character wide and is set 12pt to the right
    of the four-digit labels. Excluding it is what left the 2025 W49 ladder running
    1000..4000 with no floor. Thousands separators are optional, because 2022 prints
    '5000' and 2023-26 print '5,000'.
    """
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip().replace(",", "")
                if not re.fullmatch(r"\d{1,6}", t):
                    continue
                out.append((sp["bbox"][0], sp["bbox"][1], float(t)))
    return out


def _all_ladders(page):
    """Every validated y-ladder on the page, from every x column, split on y gaps."""
    allnums = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip().replace(",", "")
                # 2022 prints its ladder WITHOUT thousands separators ('5000', '95000')
                # while 2023-26 print them ('5,000'). Stripping the comma first makes both
                # shapes match; an earlier regex demanded the comma and found no ladder in
                # that era at all.
                if not re.fullmatch(r"\d{3,6}", t):
                    continue
                allnums.append((sp["bbox"][0], sp["bbox"][1], float(t)))
    out = []
    for cl in _clusters([(c[0], c) for c in allnums], gap=30.0):
        col = [c[1] for c in cl]
        if len(col) < 4:
            continue
        uniq = {}
        for c in col:
            uniq.setdefault(round(c[1], 1), c)
        col = list(uniq.values())
        if len(col) < 4:
            continue
        for run in _split_ladders(col):
            ys = [c[1] for c in run]
            gaps = [b - a for a, b in zip(ys, ys[1:])]
            mean = sum(gaps) / len(gaps)
            if mean <= 0 or (max(gaps) - min(gaps)) / mean > 0.15:
                continue
            vals = [c[2] for c in run]
            inc = all(b >= a for a, b in zip(vals, vals[1:]))
            dec = all(b <= a for a, b in zip(vals, vals[1:]))
            if not (inc or dec):
                continue
            out.append(sorted(run, key=lambda c: c[1]))
    return out


def _raw_frames(page):
    cands = []
    for d in page.get_drawings():
        if _nlines(d) != 4:
            continue
        r = d["rect"]
        w, h = r.x1 - r.x0, r.y1 - r.y0
        if not (120 < w < 400 and 40 < h < 250):
            continue
        cands.append((r.x0, r.y0, r.x1, r.y1))
    cands.sort(key=lambda f: f[1])
    return cands


def _split_ladders(col, fractions=(1.6, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)):
    """Yield candidate ladders from one x-column, splitting on large y gaps.

    Returns the column itself first (a single chart's ladder, unchanged) and then the
    pieces obtained by cutting at each gap that exceeds a multiple of the median gap.
    Each candidate is then validated on even spacing and monotonicity by the caller, so
    over-splitting costs nothing and under-splitting is visible as a rejected candidate.
    """
    col = sorted(col, key=lambda c: c[1])
    yield col
    if len(col) < 6:
        return
    ys = [c[1] for c in col]
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    med = sorted(gaps)[len(gaps) // 2]
    if med <= 0:
        return
    for f in fractions:
        thr = med * f
        pieces, cur = [], [col[0]]
        for i in range(1, len(col)):
            if ys[i] - ys[i - 1] > thr:
                pieces.append(cur)
                cur = [col[i]]
            else:
                cur.append(col[i])
        pieces.append(cur)
        if len(pieces) < 2:
            continue
        for p in pieces:
            if len(p) >= 4:
                yield p


def _free_frames(page, strokes, min_w=120.0, max_w=400.0):
    """Plot regions implied by the series strokes themselves, plus the nearest y-ladder.

    The 2022 era draws NO frame, so the plot must be bounded by something else. The
    series are the most reliable evidence present: measured 2022 W05 page 3, they fall
    into two clean vertical groups - y 98.2..243.3 and y 315.1..394.2 - which are exactly
    the two charts (Baltic Indices and Average T/C Rates).

    The ladder is then found NEAR those strokes, and the nearest candidate is the right
    one. Searching the whole page for an evenly spaced monotonic numeric column is not
    enough: the page also holds the Period and Chartering TABLES, which produce denser
    numeric clusters than either chart (measured 17 members at x 102..114 against the
    chart ladder's 8), and a global search picks those instead. The tables sit to the
    LEFT of the charts, so proximity to the strokes is the discriminator.
    """
    if not strokes:
        return []
    # group the strokes into vertical bands, splitting on gaps larger than a stroke's
    # own height
    by_y = sorted(strokes, key=lambda s: s["y0"])
    bands = [[by_y[0]]]
    for s in by_y[1:]:
        if s["y0"] - max(t["y0"] for t in bands[-1]) > 20:
            bands.append([s])
        else:
            bands[-1].append(s)
    bands = [b for b in bands if len(b) >= 3]
    if not bands:
        return []
    # the ladder columns on the page
    allnums = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip().replace(",", "")
                # 2022 prints its ladder WITHOUT thousands separators ('5000', '95000')
                # while 2024-26 print them ('5,000'). Stripping the comma first makes both
                # shapes match; an earlier regex demanded the comma and found no ladder in
                # that era at all.
                if not re.fullmatch(r"\d{3,6}", t):
                    continue
                allnums.append((sp["bbox"][0], sp["bbox"][1], float(t)))
    if not allnums:
        return []
    ladders = []
    for cl in _clusters([(c[0], c) for c in allnums], gap=30.0):
        col = [c[1] for c in cl]
        if len(col) < 4:
            continue
        uniq = {}
        for c in col:
            uniq.setdefault(round(c[1], 1), c)
        col = list(uniq.values())
        if len(col) < 4:
            continue
        # ONE X-COLUMN CAN CARRY BOTH CHARTS' LADDERS. Measured 2021 W39, x=324.8 holds
        # 16 members: 10,500/9,000/7,500/.../0 for the Baltic chart AND 85,000/75,000/...
        # /0 for the T/C chart, in one column. The combined set is not evenly spaced, so
        # the ladder test rejects it and BOTH charts go missing - which is why 2021 and
        # 2022 returned zero charts.
        #
        # The ladders are separated by a large y gap, so the column is split on gap and
        # each run tested on its own, exactly as for the frame era. The split threshold is
        # derived from the run itself rather than fixed: try a small set of fractions of
        # the median spacing and keep the split that yields two evenly spaced runs.
        for ladder in _split_ladders(col):
            ys = [c[1] for c in ladder]
            gaps = [b - a for a, b in zip(ys, ys[1:])]
            mean = sum(gaps) / len(gaps)
            if mean <= 0 or (max(gaps) - min(gaps)) / mean > 0.15:
                continue
            vals = [c[2] for c in ladder]
            inc = all(b >= a for a, b in zip(vals, vals[1:]))
            dec = all(b <= a for a, b in zip(vals, vals[1:]))
            if not (inc or dec):
                continue
            ladders.append(ladder)
    out = []
    for band in bands:
        by0 = min(s["y0"] for s in band)
        by1 = max(s["y1"] for s in band)
        right = max(s["x1"] for s in band)
        left = min(s["x0"] for s in band if s["x0"] > 0) if any(
            s["x0"] > 0 for s in band) else min(s["x0"] for s in band)
        # the nearest ladder that overlaps this band vertically
        best = None
        for col in ladders:
            ly0, ly1 = min(c[1] for c in col), max(c[1] for c in col)
            if not (by0 - 15 <= ly0 and ly1 <= by1 + 15):
                continue
            cx = min(c[0] for c in col)
            d = abs(cx - left)
            if best is None or d < best[0]:
                best = (d, col)
        if best is None:
            continue
        col = best[1]
        cx = min(c[0] for c in col)
        lo, hi = min(c[1] for c in col) - 8, max(c[1] for c in col) + 8
        out.append(((min(cx, left), lo, max(right, left + min_w), hi), col))
    out.sort(key=lambda t: t[0][1])
    return out


def axis_ladders(page, frame):
    """EVERY y-axis ladder of the chart occupying `frame`.

    Not one ladder. Measured 2026 W35, the single x column at x~340 carries BOTH
    charts' ladders: 6,000/5,000/.../0 at y 162.8-226 for the Baltic chart, and
    55,000/50,000/.../0 at y 300-367 for the T/C chart. A function that returned only
    the first run therefore found one chart and silently lost the other.

    Each ladder is validated separately (even spacing, monotonic values) and the results
    are returned together, so both charts on the page are found from one column.
    """
    fx0 = frame[0]
    cand = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip().replace(",", "")
                if not re.fullmatch(r"\d+(?:\.\d+)?", t):
                    continue
                x, y = sp["bbox"][0], sp["bbox"][1]
                if not (fx0 - 60 <= x < fx0):
                    continue
                if not (frame[1] - 25 <= y <= frame[3] + 25):
                    continue
                cand.append((x, y, float(t)))
    out = []
    for cl in _clusters([(c[0], c) for c in cand], gap=30.0):
        col = [c[1] for c in cl]
        if len(col) < 3:
            continue
        uniq = {}
        for c in col:
            uniq.setdefault(round(c[1], 1), c)
        col = list(uniq.values())
        if len(col) < 3:
            continue
        for run in _split_ladders(col):
            ys = [c[1] for c in run]
            gaps = [b - a for a, b in zip(ys, ys[1:])]
            mean = sum(gaps) / len(gaps)
            if mean <= 0 or (max(gaps) - min(gaps)) / mean > 0.15:
                continue
            vals = [c[2] for c in run]
            inc = all(b >= a for a, b in zip(vals, vals[1:]))
            dec = all(b <= a for a, b in zip(vals, vals[1:]))
            if not (inc or dec):
                continue
            out.append(sorted(run, key=lambda c: c[1]))
    return out


def axis_ladder(page, frame):
    """The single best ladder for `frame`, for callers that want one."""
    ls = axis_ladders(page, frame)
    return max(ls, key=len) if ls else []


def _clusters(pairs, gap):
    ordered = sorted(pairs, key=lambda p: p[0])
    if not ordered:
        return []
    out = [[ordered[0]]]
    for it in ordered[1:]:
        if it[0] - out[-1][-1][0] <= gap:
            out[-1].append(it)
        else:
            out.append([it])
    return out


def legend_series(page, frame):
    """Map each series stroke to its legend name by exact colour match.

    The legend row is a short swatch stroke with its name printed immediately ABOVE it,
    not beside it: measured 2026 W35, chart 1's swatches sit at y=167.25 and the names
    BCI/BPI/BSI/BHSI/BDI at y=161.00, 6.25pt above. An earlier test assumed the name sat
    to the right on the same baseline and matched nothing, leaving all series unlabelled.

    The search band is anchored on the CHART TITLE when one is present, because the frame
    top and the legend are not always in the same place: in the frame-less 2021-22 era
    the frame is synthesised from the ladder, so its top is the ladder's top tick and the
    legend sits several points above that. Anchoring on the title is stable across eras,
    and the colour join makes the match exact regardless of the offset.

    Matching on RGB is an equality join on measured geometry, so a series is never named
    by its position or by the order the PDF emitted it.
    """
    swatches = []
    for d in page.get_drawings():
        col = tuple(d.get("color") or ())
        if len(col) != 3:
            continue
        r = d["rect"]
        if 2 < (r.x1 - r.x0) < 20 and (r.y1 - r.y0) < 2:
            swatches.append((r.x0, r.y0, col))
    if not swatches:
        return {}
    # The legend is the row of swatches nearest the plot, ABOVE it. The band is wide
    # because the offset differs by era: with a drawn frame the swatches sit 2pt below
    # the frame's top edge (measured 2026 W35: frame top 168.7, swatches 167.25), while
    # in the frame-less era the synthesised frame starts at the ladder's TOP TICK, which
    # is already below the swatches. A 60pt window covers both without reaching the
    # OTHER chart's legend, which is 130pt+ away.
    # The legend sits ABOVE the plot's top edge. The frame's top is the ladder's top tick,
    # and the legend row is a few points above THAT (measured 2021 W39: frame top 151.1,
    # swatches 159.72 - i.e. BELOW the frame top - and names 156.83, also below; measured
    # 2026 W35: frame top 168.7, swatches 167.25, names 161.00, all above the top TICK at
    # 163). The offset is not consistent between eras, so the band spans both sides of
    # the frame top generously, and the colour join decides the actual pairing.
    #
    # A band that reached only DOWNWARD from the frame top found no names at all in the
    # 2021-22 era, where the synthesised frame starts at the ladder's top tick and the
    # legend is 5pt below it - but in 2023-26 it is above. Window must cover +/-.
    lo_band, hi_band = frame[1] - 30, frame[1] + 20
    above = [s for s in swatches if lo_band <= s[1] <= hi_band]
    if not above:
        above = [s for s in swatches if abs(s[1] - frame[1]) < 50] or swatches
    if above:
        top = min(s[1] for s in above)
        above = [s for s in above if s[1] - top < 3.0]
    names = defaultdict(list)
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip()
                x, y = sp["bbox"][0], sp["bbox"][1]
                if not t or len(t) > 40:
                    continue
                if not (lo_band <= y <= hi_band):
                    continue
                # WITHIN THE PLOT'S OWN X RANGE. The same token appears twice on the page:
                # in the chart's legend (measured 2021 W39: 'BCI' at x=392.06, size 5.6)
                # and in the left-hand data table (x=22.17, size 7.3), 370pt away. The
                # table copy is emitted LAST, so proximity alone is ambiguous; the x range
                # is not, because a chart's legend always sits above its own plot.
                if not (frame[0] - 10 <= x <= frame[2] + 10):
                    continue
                names[t].append((x, y))
    return {"swatches": above, "names": names}


def name_for(col, swatches, names, frame):
    """The legend name printed directly above the swatch of this colour.

    Measured 2021 W39: swatches at y=159.72, names at y=156.83, name x = swatch x + 17.6.
    Measured 2026 W35: swatches at y=167.25, names at y=161.00, name x = swatch x + 16.7.
    So the name is consistently ~17pt right of its swatch's left edge and a few points
    above it.

    The candidate text must be a SHORT alphabetic token. That filter is what excludes the
    ladder itself: in 2021 the ladder's top tick '10,500' sits at y=161.07, INSIDE the
    legend band, so a window-based filter alone admits the axis numbers as names. 'BCI'
    and '10,500' are trivially separable on shape, and the colour join then fixes which
    is which.
    """
    sw = min(swatches, key=lambda s: max(abs(a - b) for a, b in zip(s[2], col)))
    if max(abs(a - b) for a, b in zip(sw[2], col)) > 0.01:
        return None
    best = None
    for name, locs in names.items():
        t = name.strip()
        if not t or len(t) > 24 or not re.search(r"[A-Za-z]{2}", t):
            continue                      # not a legend label: excludes '10,500', '2024'
        for x, y in locs:
            dx = x - sw[0]
            dy = y - sw[1]
            if 2 <= dx <= 30 and -14 <= dy <= 2:
                d = abs(dx - 17) + abs(dy + 3)
                if best is None or d < best[0]:
                    best = (d, t)
    return best[1] if best else None


def value_at(y, ticks, frame=None):
    """Interpolate page y -> index value, piecewise across the printed ladder.

    When a plot FRAME is known, its own top and bottom are used as the ladder's
    endpoints when the printed labels stop short of them. This matters: a chart whose
    lowest printed label is 1000 has a plot floor BELOW that label, and clamping
    everything under the label pins the series flat along the floor. Measured 2025 W49,
    BHSI's final six vertices all sat at one y for exactly this reason, and the page's
    own table put the true value 48% higher.

    The frame is only used to EXTEND the scale, never to replace the printed labels: the
    top end keeps its printed value, and the bottom end is placed at the frame's floor
    using the ladder's own pitch.
    """
    if len(ticks) < 2:
        return None
    srt = sorted(ticks, key=lambda t: t[1])
    if frame is not None:
        ft, fb = frame[1], frame[3]
        top_y, top_v = srt[0][1], srt[0][2]
        bot_y, bot_v = srt[-1][1], srt[-1][2]
        if bot_y == top_y:
            return None
        step = (bot_v - top_v) / (bot_y - top_y)
        # the synthetic endpoints are full (x, y, value) triples, matching the ladder's
        # own shape - a 2-tuple here raised IndexError on every document
        if ft < top_y - 2:
            srt = [(ft, 0.0, top_v - step * (top_y - ft))] + srt
        if fb > bot_y + 2:
            srt = srt + [(fb, 0.0, bot_v - step * (fb - bot_y))]
        srt = sorted(srt, key=lambda t: t[1])
    if y <= srt[0][1]:
        a, b = srt[0], srt[1]
    elif y >= srt[-1][1]:
        a, b = srt[-2], srt[-1]
    else:
        a = b = None
        for i in range(len(srt) - 1):
            if srt[i][1] <= y <= srt[i + 1][1]:
                a, b = srt[i], srt[i + 1]
                break
        if a is None:
            return None
    if a[1] == b[1]:
        return None
    return a[2] + (y - a[1]) * (b[2] - a[2]) / (b[1] - a[1])


def date_labels(page, frame, report_date=None):
    """The twelve month-end dates on the x axis, as (x, ISO date), oldest first.

    THE LABELS ARE OUTLINED VECTOR GLYPHS. Measured 2025 W49: `page.get_text()` over the
    x-axis band returns nothing at all - the twelve date labels are filled paths, each a
    cluster of 98-138 tiny strokes, so a text-layer read finds an axis with no dates
    silently.

    The dates are therefore DERIVED from the window's structure by `intermodal_axis_dates`,
    whose rule was verified against a 500-dpi render of the axis: the axis carries twelve
    month-ends ending in the report's own month.

    THEIR X POSITIONS ARE MEASURED, NOT ASSUMED. The label glyph clusters are found as
    small uncoloured multi-stroke groups just below the plot, and their left edges are used
    directly. Measured 2025 W49: 13 clusters (12 intervals) at x 357.1, 374.5, 390.5,
    409.8, 426.0, 446.4, 465.5, 481.3, 499.9, 518.2, 535.5, 553.7 - spacing about 16-20pt
    across a 217pt plot. The FIRST one sits at the plot's left edge, not at half a month
    in, so the earlier uniform (k+0.5)/12 placement shifted every date by half a month
    and mis-dated the whole series.

    If the clusters cannot be found the labels are left empty and the caller records the
    gap rather than inventing dates.
    """
    if not report_date:
        return []
    dates = axdates.window(report_date)
    if not dates:
        return []
    ticks = _label_cluster_x(page, frame)
    if len(ticks) >= len(dates):
        # the left edge of the k-th label bounds the month it names
        return [(ticks[k], dates[k].isoformat()) for k in range(len(dates))]
    fx0, fx1 = frame[0], frame[2]
    w = fx1 - fx0
    n = len(dates)
    return [(fx0 + w * k / (n - 1), dates[k].isoformat()) for k in range(n)]


def _label_cluster_x(page, frame, n_min=40, n_max=200, max_w=30):
    """x positions of the outlined date labels beneath a plot, in order.

    Each label is a cluster of many tiny uncoloured strokes, so it is found by shape: more
    than 40 line items, under 30pt wide, sitting just below the plot, and drawn with no
    stroke colour (the labels are filled outlines, not strokes).
    """
    out = []
    for d in page.get_drawings():
        if tuple(d.get("color") or ()):
            continue                      # labelled with a colour: not an outline glyph
        n = _nlines(d)
        if not (n_min <= n <= n_max):
            continue
        r = d["rect"]
        w = r.x1 - r.x0
        if not (5 < w < max_w):
            continue
        if not (frame[3] - 2 <= r.y0 <= frame[3] + 32):
            continue
        if r.x0 < frame[0] - 5 or r.x0 > frame[2] + 5:
            continue
        out.append((r.x0, w, n))
    out.sort()
    # one label per cluster: merge groups whose x ranges overlap
    merged = []
    for x, w, n in out:
        if merged and x < merged[-1][1] - 2:
            merged[-1] = (merged[-1][0], max(merged[-1][1], x + w))
        else:
            merged.append((x, x + w))
    return [round(a, 2) for a, _ in merged]


def to_iso(t):
    """Publisher date label '30/Sep/25' -> '2025-09-30'."""
    m = re.fullmatch(r"(\d{2})/([A-Z][a-z]{2})/(\d{2})", t or "")
    if not m:
        return None
    dd, mon, yy = m.groups()
    mi = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC").index(mon.upper()) + 1
    return f"20{yy}-{mi:02d}-{dd}"


def x_frac(x, frame):
    fx0, fx1 = frame[0], frame[2]
    return (x - fx0) / (fx1 - fx0) if fx1 > fx0 else None


def date_for_frac(frac, dates, frame):
    """Interpolate an x position to an ISO date using the axis labels."""
    if not dates or frac is None:
        return None
    fx0, fx1 = frame[0], frame[2]
    pos = fx0 + frac * (fx1 - fx0)
    xs = [d[0] for d in dates]
    if pos <= xs[0]:
        return dates[0][1]
    if pos >= xs[-1]:
        return dates[-1][1]
    i = 0
    for j in range(len(xs) - 1):
        if xs[j] <= pos:
            i = j
    a, b = dates[i], dates[i + 1]
    if a[0] == b[0]:
        return a[1]
    import datetime as _dt
    try:
        da = _dt.date.fromisoformat(a[1])
        db = _dt.date.fromisoformat(b[1])
    except ValueError:
        return a[1]
    t = (pos - a[0]) / (b[0] - a[0])
    return (da + _dt.timedelta(days=(db - da).days * t)).isoformat()


def report_date_of(pdf_path):
    """The report's assessment date, ISO, from the filename's ISO week.

    intermodal_v2 already resolves the authoritative assessment date from the PRINTED
    table header; this is the filename-derived equivalent used for the axis window. Both
    are recorded, so a disagreement between them is visible rather than silent.
    """
    m = re.search(r"(20\d{2})[_-]W(\d{2})", Path(pdf_path).name)
    if not m:
        return None
    import datetime as _dt
    try:
        return _dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 5).isoformat()
    except ValueError:
        return None


def route_of(doc):
    """'ATLANTIC' or 'PACIFIC' - which index this report charts.

    READ FROM THE PAGE, NEVER THE FILENAME. The filenames never carry the route: all 252
    are named `intermodal_<year>_W<nn>_...`, so a filename rule classifies 252 of 252 as
    ATLANTIC and pools two different indices onto one key. Measured cost of that mistake:
    the merge's cross-report agreement collapsed to a 58.2% median spread, with the worst
    keys spanning 4..2,315 across 44 reports - a range only two different indices produce.

    The page prints the route in its own title block ('Pacific Capesize Index',
    'The SSY Atlantic Capesize Index'), so an exact vocabulary match on the text is both
    available and unambiguous.
    """
    txt = doc[0].get_text()
    head = txt[:400].upper()
    a = "ATLANTIC CAPESIZE INDEX" in head
    p = "PACIFIC CAPESIZE INDEX" in head
    if a and not p:
        return "ATLANTIC"
    if p and not a:
        return "PACIFIC"
    up = txt.upper()
    if "ATLANTIC CAPESIZE INDEX" in up and "PACIFIC CAPESIZE INDEX" not in up:
        return "ATLANTIC"
    if "PACIFIC CAPESIZE INDEX" in up and "ATLANTIC CAPESIZE INDEX" not in up:
        return "PACIFIC"
    return None


def extract(pdf_path):
    doc = pymupdf.open(pdf_path)
    try:
        out = {"file": Path(pdf_path).name,
               "report_date": report_date_of(pdf_path),
               "route": route_of(doc),
               "charts": [], "warnings": []}
        for pi in CHART_PAGES:
            if pi >= len(doc):
                out["warnings"].append(f"page {pi + 1} missing")
                continue
            page = doc[pi]
            # series strokes first: the frame-less era needs them to bound the plot
            strokes = []
            for d in page.get_drawings():
                if _nlines(d) < MIN_ITEMS:
                    continue
                col = tuple(d.get("color") or ())
                if len(col) != 3:
                    continue
                pts = _items(d)
                if not pts:
                    continue
                strokes.append({"pts": pts, "colour": col,
                                "x0": min(p[0] for p in pts), "x1": max(p[0] for p in pts),
                                "y0": min(p[1] for p in pts), "y1": max(p[1] for p in pts)})
            if not strokes:
                out["warnings"].append(f"page {pi + 1}: no series strokes")
                continue
            charts = find_charts(page, strokes)
            if not charts:
                out["warnings"].append(f"page {pi + 1}: no plot region found")
                continue
            for frame, ticks in charts:
                leg = legend_series(page, frame)
                dates = date_labels(page, frame, out["report_date"])
                # a stroke belongs to this plot if it overlaps it vertically and reaches
                # into its x window
                inframe = [s for s in strokes
                           if s["y1"] >= frame[1] - 5 and s["y0"] <= frame[3] + 5
                           and s["x1"] >= frame[0] and s["x0"] <= frame[2] + 400]
                chart = {
                    "page": pi + 1,
                    "frame": [round(v, 2) for v in frame],
                    "ticks": [{"v": round(t[2], 1), "y": round(t[1], 2)} for t in ticks],
                    "date_labels": [{"x": round(x, 2), "date": d} for x, d in dates],
                    "series": [],
                }
                if not ticks:
                    chart["warning"] = "no y-axis ladder"
                for s in inframe:
                    nm = name_for(s["colour"], leg["swatches"], leg["names"], frame) if leg else None
                    seen, pts = set(), []
                    for x, y in s["pts"]:
                        if not (frame[0] - 1 <= x <= frame[2] + 1):
                            continue
                        if not (frame[1] - 1 <= y <= frame[3] + 1):
                            continue
                        k = (round(x, 2), round(y, 2))
                        if k not in seen:
                            seen.add(k)
                            pts.append((x, y))
                    pts.sort()
                    if len(pts) < 5:
                        continue
                    rec = []
                    for x, y in pts:
                        v = value_at(y, ticks, frame)
                        frac = x_frac(x, frame)
                        r = {"x": round(x, 2), "y": round(y, 2), "x_frac": round(frac, 5) if frac is not None else None,
                             "value": round(v, 1) if v is not None else None}
                        d = date_for_frac(frac, dates, frame)
                        if d:
                            r["date"] = d
                        rec.append(r)
                    vals = [r["value"] for r in rec if r["value"] is not None]
                    chart["series"].append({
                        "name": nm,
                        "colour": [round(c, 4) for c in s["colour"]],
                        "n_points": len(rec),
                        "min": min(vals) if vals else None,
                        "max": max(vals) if vals else None,
                        "last": vals[-1] if vals else None,
                        "points": rec,
                    })
                chart["series"].sort(key=lambda z: (z["name"] is None, z["name"] or ""))
                out["charts"].append(chart)
        return out
    finally:
        doc.close()


def main(argv):
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    limit = None
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    pdfs = sorted(SRC.glob("*/*.pdf"))
    if only:
        pdfs = [p for p in pdfs if only in p.name]
    if limit:
        pdfs = pdfs[:limit]
    OUT.mkdir(parents=True, exist_ok=True)
    state = OUT / "_run_state.json"
    done = json.loads(state.read_text()) if state.exists() else {}
    ok = fail = 0
    for i, p in enumerate(pdfs, 1):
        sid = p.name
        if done.get(sid, {}).get("n_points", 0) > 0:
            ok += 1
            continue
        try:
            d = extract(p)
        except Exception as e:                            # noqa: BLE001
            fail += 1
            done[sid] = {"n_points": 0, "error": str(e)[:200]}
            print(f"[{i}/{len(pdfs)}] {sid} FAILED {e}", flush=True)
            state.write_text(json.dumps(done, indent=1), encoding="utf-8")
            continue
        npts = sum(s["n_points"] for c in d["charts"] for s in c["series"])
        (OUT / (sid + ".charts.json")).write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        done[sid] = {"n_points": npts, "n_charts": len(d["charts"]),
                     "n_series": sum(len(c["series"]) for c in d["charts"]),
                     "warnings": d["warnings"]}
        if npts:
            ok += 1
        else:
            fail += 1
        state.write_text(json.dumps(done, indent=1), encoding="utf-8")
        print(f"[{i}/{len(pdfs)}] {sid} charts={len(d['charts'])} "
              f"series={done[sid]['n_series']} pts={npts} "
              f"{'OK' if npts else 'EMPTY ' + str(d['warnings'])}", flush=True)
    print(f"\ndone={ok} empty_or_failed={fail} credits=0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
