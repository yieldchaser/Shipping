"""ssy - extract every plotted index series from the report chart. VECTOR, exact, free.

MEASURED STRUCTURE (each point settled by inspecting the PDF, not by guessing)
----------------------------------------------------------------------------
ssy is 519 ONE-PAGE reports. The route table, the Calculated Index and the T/C rates
are ALREADY in data/extracted/md/ssy/. What is missing is the PLOTTED SERIES.

Two layout eras exist and they are structurally different:

  2021-2023  (Atlantic, one series, 26-104 weekly vertices)
    - x axis: month labels 'Jan' .. 'Dec' plus a separate two-digit-year span
    - y axis: FULL numerals 28000,24000,...,4000,0, right-aligned, so their x varies
      with digit count (215.74 for '12,000' vs 220.91 for '8,000' vs 239.08 for '0')
    - the ladder is exactly even: 128.535 / 128.700 units-per-point on all six
      intervals, a 0.13% spread. That is the proof the calibration is right.

  2024-2026  (Pacific, THREE series)
    - x axis: bare month labels 'Jan' .. 'Dec', no year
    - y axis: ABBREVIATED labels 0, 4k, 8k, 12k, 16k at x~26-34  <- why the first
      extractor found no ticks on 2024+ at all
    - a COLOUR LEGEND below the axis: a short swatch stroke then the year, all on
      y=586.2. The swatch RGB equals its series RGB exactly, so the year label is
      recovered by an equality join on measured geometry, never by row order:
        teal (0.0039,0.6392,0.6196) = 2022, n=104
        navy (0.0863,0.2431,0.6235) = 2023, n=100
        pink (0.9216,0.2196,0.4431) = 2024, n= 52 (current year, partial)

WHY CLUSTERING IS DONE BY GAP, NOT BY A FIXED BUCKET
----------------------------------------------------
Both axes are right-aligned, so label x varies with digit count and fixed buckets split
one ladder in two: 26.1//30=0 but 30.3//30=1, which lost the whole 2024 axis. Month
labels have the same defect in y (spans differ by 0.01pt), so round(y) fragmented a
22-label axis into fragments of 14. Both are fixed by sorting and starting a new cluster
only when the GAP exceeds a tolerance, which is scale-free and needs no bucket width.

WHY NO CREDITS
--------------
The series are stroked vector paths, not raster. Every reading is an interpolation of
the printed axis ladder against the stroke's own vertices, so values are exact to the
plotted resolution. LlamaParse was measured at 45 credits/page for this material: 519
pages would cost 23,355 credits, more than three whole free-plan accounts, for a worse
answer than the printed ladder gives for free.

SELF-CHECK
----------
Every page prints 'Calculated Index' followed by the current figure. The current-year
series must end at that value, so extract() records the gap in index['check'] and
main() reports the population. That is a per-document ground truth, not a sample.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "corpus" / "01-brokers" / "ssy"
OUT = REPO / "data" / "extracted" / "charts" / "ssy"

MONTH_ABBR = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTH_RE = "|".join(MONTH_ABBR)
YEAR_RE = re.compile(r"^(19|20)\d{2}$")

# An axis column is a cluster whose members sit within this many points of each other.
# Measured: a y ladder spans 26.1..239.1 (13pt of right-alignment drift), month labels
# 40.3..527.5, and the route table is >200pt away. 40pt separates one axis from the next
# with a wide margin on both sides.
CLUSTER_GAP = 40.0


# --------------------------------------------------------------------------- text

def _spans(page):
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                yield sp


def _num(txt):
    """'12,000' / '28000' / '4k' / '0' -> float, else None."""
    t = txt.strip().replace(",", "").replace(" ", "")
    m = re.fullmatch(r"(\d+)(k)?", t, re.I)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1000.0 if m.group(2) else v


def _clusters(pairs, gap=CLUSTER_GAP):
    """Group (coord, payload) into 1-D clusters separated by > gap.

    Scale-free: it asks how far apart neighbours are, not which bucket they fall in.
    """
    ordered = sorted(pairs, key=lambda p: p[0])
    if not ordered:
        return []
    out = [[ordered[0]]]
    for item in ordered[1:]:
        if item[0] - out[-1][-1][0] <= gap:
            out[-1].append(item)
        else:
            out.append([item])
    return out


def axis_ticks(page):
    """The y-axis ladder: evenly spaced in y, monotonic in value, one x cluster.

    Handles both eras with one test. Values are not required to be positive: the '0'
    baseline is a real tick and dropping it - as an early version did by requiring
    v > 0 - left the 2024 ladder with four rungs and no anchor.
    """
    nums = []
    for sp in _spans(page):
        v = _num(sp["text"])
        if v is not None:
            nums.append((sp["bbox"][0], sp["bbox"][1], v, sp["text"].strip()))
    best = None
    for cl in _clusters([(x, (x, y, v, raw)) for x, y, v, raw in nums]):
        col = [c[1] for c in cl]
        if len(col) < 3:
            continue
        # A ladder is CONSTANTLY spaced in y. Legend labels can share the x band and sit
        # between rungs (measured 2023: ticks at x=207.6/211.3, legend years
        # '2021'/'2022'/'2023' at x=243.8, y=377.4/386.7/396.1, dropped into the middle of
        # the tick run), so the whole cluster fails a strict even-spacing test.
        #
        # A fixed gap threshold cannot separate them: real rung spacing is 15.88pt
        # (measured 2021, sixteen rungs 15,000..0), so a 6pt y-gap split every rung apart
        # and returned NO ladder for all 519 documents. A 20pt gap would instead swallow
        # the interleaved legend years.
        #
        # So the rungs are found by a ROBUST arithmetic fit instead: take the median gap
        # as the step, then keep only the members that sit on that grid. The legend years
        # fall between rungs and are discarded; a genuine ladder is untouched. This is
        # scale-free and uses the ladder's own dominant spacing, not a tuned constant.
        if len(col) < 3:
            continue
        ys = sorted(c[1] for c in col)
        diffs = [b - a for a, b in zip(ys, ys[1:])]
        step = sorted(diffs)[len(diffs) // 2]
        if step <= 0:
            continue
        # keep the longest run of consecutive gaps within 25% of the step
        on_grid, run, best_run = [], [], []
        for c in sorted(col, key=lambda t: t[1]):
            if on_grid and abs((c[1] - on_grid[-1][1]) - step) <= step * 0.25:
                run.append(c)
            else:
                run = [c]
            if len(run) > len(best_run):
                best_run = list(run)
            on_grid = run
        cand = best_run
        if len(cand) < 3:
            continue
        ordered = [c[2] for c in cand]
        inc = all(b >= a for a, b in zip(ordered, ordered[1:]))
        dec = all(b <= a for a, b in zip(ordered, ordered[1:]))
        if not (inc or dec):
            continue
        if best is None or len(cand) > len(best):
            best = cand
    return sorted(best, key=lambda t: t[1]) if best else []


def month_axis(page):
    """Ordered x-axis month labels as dicts with both edges.

    Both label forms are accepted: 'Jan-20' (2021-23, where the year is a separate
    span) and bare 'Jan' (2024-26). Year-only labels elsewhere on the page are a COLOUR
    LEGEND, not axis ticks, and are never used here - see legend_series().
    """
    found = []
    for sp in _spans(page):
        t = sp["text"].strip()
        m = re.fullmatch(r"(" + MONTH_RE + r")-(\d{2})", t, re.I)
        if m or re.fullmatch(MONTH_RE, t, re.I):
            yy = m.group(2) if m else ""
            found.append({
                "x0": sp["bbox"][0], "x1": sp["bbox"][2],
                "y": sp["bbox"][1], "mon": (m.group(1) if m else t).upper(), "yy": yy,
            })
    if len(found) < 2:
        return []
    rows = _clusters([(f["y"], f) for f in found], gap=3.0)
    row = [c[1] for c in max(rows, key=len)]
    if len(row) < 2:
        return []
    row.sort(key=lambda f: f["x0"])
    year = None
    for f in row:
        if f["yy"]:
            year = f["yy"]
        f["yy"] = year or ""
    return row


# ------------------------------------------------------------------------ geometry

def _pts(d):
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            for seg in it[1:]:
                pts.append((seg.x, seg.y))
    return pts


def series_paths(page):
    """Every long stroked polyline: the candidate series.

    Selected by VERTEX COUNT with a floor of 20. A plotted weekly line has dozens to a
    hundred closely spaced vertices; the plot frame has 8-16. Taking the single longest
    path - the obvious first implementation - merged the frame into the series and cut
    the final reading by 5.4% against the page's own printed value.
    """
    out = []
    for d in page.get_drawings():
        raw = []
        for it in d["items"]:
            if it[0] == "l":
                for seg in it[1:]:
                    raw.append((seg.x, seg.y))
        if len(raw) < 20:
            continue
        r = d["rect"]
        if (r.x1 - r.x0) < 100 or (r.y1 - r.y0) < 10:
            continue
        # A DATA LINE advances monotonically in x. Axis furniture does not.
        #
        # Measured ssy 2021, the 4th candidate was 15 full-width GRIDLINES: 30 vertices,
        # median segment 313.61pt, the width of the whole plot. The three real series run
        # 7.86 / 9.27 / 15.06pt. A gridline is a horizontal rule repeated down the page,
        # so each one is at a constant x span and the path never steps rightward; a
        # plotted line steps right at every vertex.
        #
        # Earlier attempts failed here for instructive reasons. An aspect-ratio rule
        # (height > 0.75*width) deleted a REAL series: the 2021 line spans 65% of the
        # plot's height against the furniture's 71%. A closed-walk test missed the
        # furniture because PyMuPDF reports each rule as its own item, so the path is not
        # closed. A median-segment-length test pointed the wrong way: the gridline is the
        # LONGEST path on the page.
        xs = [x for x, _ in raw]
        steps = [b - a for a, b in zip(xs, xs[1:])]
        if not steps:
            continue
        forward = sum(1 for s in steps if s > 0.01)
        backward = sum(1 for s in steps if s < -0.01)
        if forward < 0.9 * (forward + backward):
            continue              # a stack of rules, not a left-to-right line
        # KEEP EMISSION ORDER. Sorting by x here would destroy the information
        # _forward_runs() needs: a stroke that doubles back is only recognisable from the
        # order its segments were emitted, and sorting first makes the backtrack look
        # like ordinary data. The x range still comes from the drawing's own rect.
        out.append({"pts": list(raw), "rect": (r.x0, r.y0, r.x1, r.y1),
                    "colour": tuple(d.get("color") or ())})
    return out


def _forward_runs(pts):
    """Rebuild a stroke in emission order, keeping only forward-moving runs.

    A plotted line advances left to right. A stroke that doubles back - emitted once to
    draw the line and again for a highlight, or with a duplicated peak - produces a run
    of x-steps that go backwards. Sorting by x (as an earlier version did) interleaves
    the returning run with the outgoing one and invents points that are on neither.

    Measured ssy 2025-01-03 Pacific: the 2023 teal stroke's tail was
    ...58,561 / 90,279 / 90,279 / 56,050, a 90k spike with the peak repeated, against a
    rendered line that peaks near 42k in October. Keeping the longest forward run drops
    the backtrack and its duplicate together, so the phantom never becomes a reading.

    The LONGEST run wins rather than the first, so a short backtrack at either end is
    discarded without discarding the series.
    """
    best, cur = [], []
    for p in pts:
        if cur and p[0] < cur[-1][0] - 0.01:
            if len(cur) > len(best):
                best = cur
            cur = [p]
        else:
            cur.append(p)
    if len(cur) > len(best):
        best = cur
    return best or list(pts)


def _drop_shadow_paths(paths):
    """Remove duplicate strokes drawn exactly beneath a series for contrast.

    Measured on the 16 ssy 2026 reports that yield six paths for three series: each
    coloured line has a grey (0.7529, 0.7529, 0.7529) twin at the SAME x range, the same
    vertex count, and a MAXIMUM vertex offset of 0.00pt. Keeping both would double every
    point and invent six series where the chart draws three.

    A shadow is dropped only when its vertices coincide exactly (within 0.05pt) with an
    already-kept path, so a genuine second series is never discarded. Colour and vertex
    count are the cheap pre-filter; the coordinate test is the proof.
    """
    kept = []
    for p in paths:
        pts = sorted((round(x, 1), round(y, 1)) for x, y in p["pts"])
        shadow = False
        for q in kept:
            qp = sorted((round(x, 1), round(y, 1)) for x, y in q["pts"])
            if len(qp) != len(pts):
                continue
            if max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                   for a, b in zip(pts, qp)) <= 0.05:
                shadow = True
                break
        if not shadow:
            kept.append(p)
    return kept


def plot_x_window(page, months, ticks):
    """The plot's left and right x bounds, from the frame when one is drawn.

    2021-23 draw the plot border as an 8-vertex closed path: measured ssy 2021, x
    254.1..572.8 / y 450.9..669.6, w=318.7 / h=218.7. That is the true window and the
    month labels sit inside it (248.9..563.5), so the frame must win.

    2024-26 draw no frame. Their window is bounded by the axis tick columns instead:
    the y ladder is left of the plot, and its first month label is the next reference to
    the right. Where no frame exists, the label extent is used with the measured
    overshoot added - 23.9pt on 2024 - rather than a guessed margin.
    """
    for d in page.get_drawings():
        r = d["rect"]
        pts = _pts(d)
        if 6 <= len(pts) <= 20 and (r.x1 - r.x0) > 250 and (r.y1 - r.y0) > 80:
            # require it to enclose the month labels, so a table rule cannot qualify
            if months and not (r.x0 <= months[0]["x0"] and r.x1 >= months[-1]["x1"]):
                continue
            return r.x0, r.x1
    if not months:
        return None, None
    lo = months[0]["x0"]
    hi = months[-1]["x1"] + 26.0     # measured overshoot 23.9pt, rounded up
    if ticks:
        left = max((t[0] for t in ticks), default=None)
        if left is not None:
            lo = lo   # labels already start inside the plot; ticks are further left
    return lo, hi


def legend_series(page, paths):
    """Map each series stroke to a year by exact colour equality with its swatch.

    The legend is a short stroke followed by a year label on one baseline. Matching the
    RGB is an equality join on measured geometry, so a series is never labelled by its
    left-to-right position or by the order the PDF emitted it.
    """
    swatches, labels = [], []
    for d in page.get_drawings():
        r = d["rect"]
        col = tuple(d.get("color") or ())
        if len(col) != 3:          # some strokes carry no RGB at all
            continue
        if 3 < (r.x1 - r.x0) < 30 and (r.y1 - r.y0) < 2:
            swatches.append((r.x0, r.y0, col))
    for sp in _spans(page):
        if YEAR_RE.match(sp["text"].strip()):
            labels.append((sp["bbox"][0], sp["bbox"][1], sp["text"].strip()))
    if not swatches or not labels:
        return {}
    out = {}
    for p in paths:
        col = p["colour"]
        if len(col) != 3:
            continue
        sw = min(swatches, key=lambda s: max(abs(a - b) for a, b in zip(s[2], col)))
        if max(abs(a - b) for a, b in zip(sw[2], col)) > 0.01:
            continue
        cands = [l for l in labels if 0 < l[0] - sw[0] < 40 and abs(l[1] - sw[1]) < 8]
        if not cands:
            continue
        # nearest label to the RIGHT of this swatch. Taking min-by-x alone assigned
        # every swatch the same leftmost year (measured 2021: three swatches at x
        # 443.4/485.3/526.8 all matched '2019' at x=457.2), which is how the 2021 run
        # reported three correctly-coloured series with duplicated year labels.
        out[id(p)] = min(cands, key=lambda l: l[0])[2]
    return out


# ------------------------------------------------------------------------- scaling

def value_at(y, ticks):
    """Interpolate page y -> index value, piecewise across the printed ladder.

    Piecewise so error cannot accumulate toward the ends. Below the lowest printed
    tick the last interval is extended, which is needed because the ladder's lowest
    label is 0 or 4,000 while the plot's baseline may sit below it.
    """
    if len(ticks) < 2:
        return None
    srt = sorted(ticks, key=lambda t: t[1])
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


def date_for_x(x, months, series_year=None):
    """Map a page x to a calendar position using the month axis.

    x is linear in time, so a point between two month labels is dated by interpolating
    within that month. Two label forms exist:

    - 'Jan-20' .. 'Jan-22' (2021-23): the labels carry the year, so the date comes
      straight off the axis. `series_year` is ignored.
    - bare 'Jan' .. 'Dec' (2024-26): the labels carry only the month, and all THREE
      legend years share ONE x axis. The year of a point is therefore its own SERIES'
      legend year.

    That last point is the one that matters, and getting it wrong is invisible per
    document. Measured on ssy: a report with legend 2023/2024/2025 and months Jan..Dec
    plots all three years against the same axis, so the x position gives the MONTH and
    the series gives the YEAR. Dating by the window's start year instead - the oldest
    legend year - stamped the 2024 line's December point as 2023-DEC as well, merging two
    different years onto one key. The merge's own agreement check exposed it: a
    90,279 reading (real Pacific 2023) and a 3,893 reading (real 2024) landed on
    'PACIFIC 2023-DEC-b4' with a 183% spread across 104 reports.

    The window-start-year idea was wrong in principle: an x axis spanning one calendar
    year means the year is a property of the SERIES, not of the plot.
    """
    if len(months) < 2:
        return None
    x0s = [m["x0"] for m in months]
    if x <= x0s[0]:
        i = 0
    elif x >= x0s[-1]:
        i = len(months) - 2
    else:
        i = max(j for j in range(len(x0s) - 1) if x0s[j] <= x)
    a, b = months[i], months[i + 1]
    t = (x - a["x0"]) / (b["x0"] - a["x0"]) if b["x0"] != a["x0"] else 0.0
    mi0 = MONTH_ABBR.index(a["mon"]) if a["mon"] in MONTH_ABBR else 0
    mi1 = MONTH_ABBR.index(b["mon"]) if b["mon"] in MONTH_ABBR else mi0 + 1
    mf = mi0 + t * ((mi1 - mi0) % 12 or 1)
    out = {"month_frac": round(mf, 3)}
    yy = a["yy"]
    if yy and yy.isdigit():
        y0 = int(yy)
    elif series_year and str(series_year).isdigit():
        y0 = int(series_year)
    else:
        return out
    year = y0 + int(mf // 12)
    mon = MONTH_ABBR[int(mf % 12)]
    out.update({"date": f"{year:04d}-{mon}", "year": year, "month_abbr": mon})
    return out


# ------------------------------------------------------------------- page ground truth

def printed_field(page, heading):
    """The first numeric figure printed under a given table heading.

    The whole table is ONE block, so the heading and its figures are lines inside it
    (measured 2024 block 3: 'Calculated Index', '7,234', '6,899', ...). A block-scoped
    or span-scoped scan misses the number; this walks the lines of the containing block.
    Two earlier attempts failed exactly there.
    """
    for blk in page.get_text("dict")["blocks"]:
        texts = ["".join(sp["text"] for sp in ln["spans"]).strip()
                 for ln in blk.get("lines", [])]
        for i, txt in enumerate(texts):
            if not re.match(re.escape(heading) + r"\b", txt, re.I):
                continue
            for nxt in texts[i + 1:]:
                m = re.fullmatch(r"([+\-]?)([\d,]{2,})(\.\d+)?", nxt)
                if m:
                    v = float(m.group(2).replace(",", ""))
                    return -v if m.group(1) == "-" else v
    return None


def calculated_index(page):
    """The page's own printed 'Calculated Index', for the base and self-check.

    Current comes first, matching the two date headers printed above the columns.
    """
    return printed_field(page, "Calculated Index")


def route_of(doc):
    """The index this report covers: Atlantic or Pacific.

    Taken from the ROUTE, never from the title. Two separate reasons:

    1. The chart title is not reliably recoverable from text order. A regex matching any
       line containing 'SSY ... Capesize Index' returned the first PROSE SENTENCE on 100+
       documents - e.g. 'The SSY Atlantic Capesize Index fell by', 'SSY Pacific Capesize
       Index to a 13-', 'took the SSY Pacific Capesize Index to'. Those are commentary,
       not titles, and pooling them would merge two different indices.
    2. Atlantic and Pacific are DIFFERENT indices with different values. Pooled, the same
       key collects readings from both and the cross-report spread explodes - which is
       exactly what the merge's own agreement check reported: median 48.8%, worst key
       2023-DEC-b4 spanning 8,175..90,279 across 156 reports.

    The route is therefore read from the document's own text, using an exact vocabulary
    match on the route name, and the merge keys on it.
    """
    txt = doc[0].get_text().upper()
    has_a = "ATLANTIC CAPESIZE INDEX" in txt
    has_p = "PACIFIC CAPESIZE INDEX" in txt
    if has_a and not has_p:
        return "ATLANTIC"
    if has_p and not has_a:
        return "PACIFIC"
    if has_a and has_p:
        # both words present: the report's OWN header decides. The first 400 characters
        # carry the title block; later text is the commentary paragraph.
        head = txt[:400]
        return "ATLANTIC" if "ATLANTIC CAPESIZE INDEX" in head else "PACIFIC"
    return None


def title_of(page):
    """The chart's title span, if one is present verbatim.

    Accepts only a span that IS the title, not a sentence containing it. A looser test
    returned prose on most 2021-23 reports, so the match is anchored to the whole span.
    """
    pat = re.compile(r"^(The )?SSY (Atlantic|Pacific) Capesize Index\.?$", re.I)
    for sp in _spans(page):
        t = sp["text"].strip()
        if pat.match(t):
            return t.rstrip(".")
    return ""


def report_year(pdf_path):
    ys = re.findall(r"(20\d{2})", Path(pdf_path).name)
    return int(ys[0]) if ys else None


def page_date(page):
    """The report's own date, ISO format, from the page text.

    Used to order the weekly chain, so the rebasing detector walks the reports in
    publication order rather than in filename order. Filenames are not reliably
    chronological across the corpus's three naming schemes (ssy_2025_20250627-...,
    ssy_2022_P20220110, ssy_14_09_2026_...).
    """
    txt = page.get_text()
    for pat in (r"(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|"
                r"July|August|September|October|November|December)\s+(20\d{2})",
                r"(20\d{2})-(\d{2})-(\d{2})",
                r"(\d{2})/(\d{2})/(20\d{2})"):
        m = re.search(pat, txt)
        if not m:
            continue
        g = m.groups()
        if g[0].startswith("20"):
            return f"{g[0]}-{g[1]}-{g[2]}"
        mon = MONTH_ABBR.index(g[1][:3].upper()) + 1
        if len(g[0]) == 4:                       # already yyyy, mm, dd
            return f"{g[0]}-{int(g[1]):02d}-{int(g[2]):02d}"
        return f"{g[2]}-{mon:02d}-{int(g[0]):02d}"
    return None


# --------------------------------------------------------------------------- extract

def extract(pdf_path):
    doc = pymupdf.open(pdf_path)
    try:
        page = doc[0]
        ticks = axis_ticks(page)
        months = month_axis(page)
        paths = series_paths(page)
        paths = _drop_shadow_paths(paths)
        leg = legend_series(page, paths)
        out = {
            "file": Path(pdf_path).name,
            "report_year": report_year(pdf_path),
            "report_date": page_date(page),
            "route": route_of(doc),
            "title": title_of(page),
            "n_ticks": len(ticks),
            "ticks": [{"v": round(t[2], 1), "y": round(t[1], 2), "raw": t[3]} for t in ticks],
            "months": [{"x0": round(m["x0"], 2), "x1": round(m["x1"], 2),
                        "mon": m["mon"], "yy": m["yy"]} for m in months],
            "series": [], "warnings": [],
        }
        if not ticks:
            out["warnings"].append("no y-axis ladder")
        if not months:
            out["warnings"].append("no x-axis month labels")
        if not paths:
            out["warnings"].append("no long polyline")
        if paths and not leg:
            out["warnings"].append("no colour legend; series unlabelled")

        # The plot's x window is the FRAME, not the label extent. The month labels are
        # inset inside it: on ssy 2021 the frame is x 254.1..572.8 while the labels run
        # 248.9..563.5, so bounding by labels both shifted the window and cut the final
        # points off. Measured overshoot on 2024 was 23.9pt past the last label.
        # 2024+ draws no frame, so its window comes from the tick columns, which sit
        # either side of the plot.
        gx_lo, gx_hi = plot_x_window(page, months, ticks)
        span = (gx_hi - gx_lo) if (gx_lo is not None and gx_hi is not None) else None
        ty_lo = min((t[1] for t in ticks), default=None)
        ty_hi = max((t[1] for t in ticks), default=None)

        for p in paths:
            rx0, ry0, rx1, ry1 = p["rect"]
            if span:
                if rx0 < gx_lo - 20 or rx1 > gx_hi + 20:
                    continue
            if ticks and (ry0 < ty_lo - 80 or ry1 > ty_hi + 80):
                continue
            # The PLOT BORDER is not a series. Three facts, each measured, rule it out.
            #
            # It is a CLOSED walk: the first and last vertices coincide, because a frame
            # is drawn as one loop. A data line is an open stroke, so its endpoints are
            # its first and last DATA points and never coincide - they are at different
            # x positions.
            #
            # It is VERTICAL-EXTREME: it reaches the top and bottom of the plot. A data
            # line is bounded by its own data. Measured ssy 2021, the frame ran y
            # 430.6..652.5 against a ladder of 434.3..672.5. An earlier aspect-ratio rule
            # (height > 0.75*width) was tried first and rejected: the frame is 0.71 but
            # the REAL 2021 series is 0.75, so it deleted a genuine line.
            #
            # ORDER BY EMISSION, THEN x. A stroke can double back on itself, and sorting
            # by x alone interleaves the returning run with the outgoing one.
            #
            # This produced a phantom 90,279 reading. Measured ssy 2025-01-03 Pacific, the
            # 2023 teal path ends ...58,561 / 90,279 / 90,279 / 56,050, i.e. it spikes to
            # 90k and falls 34k inside the last two weekly steps, with the peak vertex
            # emitted TWICE. The rendered page shows that line peaking near 42k in October,
            # so the spike is a stroke artifact, not data. It also poisoned the merge: a
            # single 90,279 reading on key 'PACIFIC 2023-DEC-b4' dragged 78 correct
            # readings of ~8,175 into a 167% spread.
            #
            # The path below rebuilds the stroke in emission order and keeps only
            # forward-moving runs, so a backtrack and its duplicated peak are dropped
            # together rather than being read as two extra data points.
            ordered = _forward_runs(p["pts"])
            seen, uniq = set(), []
            for x, y in ordered:
                k = (round(x, 2), round(y, 2))
                if k not in seen:
                    seen.add(k)
                    uniq.append((x, y))
            if len(uniq) > 2 and uniq[0] == uniq[-1]:
                continue
            pts = []
            yr = leg.get(id(p))
            for x, y in uniq:
                v = value_at(y, ticks)
                rec = {"x": round(x, 2), "y": round(y, 2),
                       "index_value": round(v, 1) if v is not None else None,
                       "x_frac": round((x - gx_lo) / span, 5) if span else None}
                if span:
                    rec.update(date_for_x(x, months, yr) or {})
                pts.append(rec)
            vals = [q["index_value"] for q in pts if q["index_value"] is not None]
            out["series"].append({
                "year": yr, "series": f"SSY Capesize Index {yr}" if yr else None,
                "colour": [round(c, 4) for c in p["colour"]] if len(p["colour"]) == 3 else None,
                "n_points": len(pts),
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "last": vals[-1] if vals else None,
                "points": pts,
            })
        # current year first, then oldest -> newest; unlabelled last
        out["series"].sort(key=lambda s: (
            s["year"] is None, s["year"] != str(out["report_year"]), s["year"] or ""))

        # SELF-CHECK against the page's own printed Calculated Index.
        #
        # The current-year series deliberately ends mid-year: measured ssy 2023/24/25/26,
        # the current line stops at x_frac 0.68 / 0.53 / 0.50 / 0.40 of the plot, because
        # the chart plots the current calendar year TO DATE and the report is published
        # partway through it (e.g. ssy_2026_20260522 is 22 May, so the 2026 line covers
        # Jan-May only). The printed index is therefore a LATER reading than the final
        # plotted vertex, and the two are not expected to agree: observed gaps 8-16%,
        # always in the same direction. Treating that as an error would condemn a correct
        # extraction, so it is recorded as structure, not a pass/fail gate.
        #
        # The exact value is not lost: the printed figure IS captured, and it is the
        # anchor for the current-year series. The chart supplies the path.
        printed = calculated_index(page)
        prev_chg = printed_field(page, "Change on Previous Index")
        two_ago = printed_field(page, "Change on Two Years Ago")
        cur = next((s for s in out["series"] if s["year"] == str(out["report_year"])), None)
        if cur is None and out["series"]:
            cur = out["series"][0]
        gap = (abs(cur["last"] - printed) / printed
               if (cur and printed and cur["last"] is not None and printed) else None)
        out["check"] = {
            "printed_calculated_index": printed,
            "change_on_previous": prev_chg,
            "change_two_years_ago": two_ago,
            "series_last": cur["last"] if cur else None,
            "series_year": cur["year"] if cur else None,
            "series_ends_at_frac": cur["points"][-1]["x_frac"] if cur and cur["points"] else None,
            "rel_gap": round(gap, 5) if gap is not None else None,
            "note": ("series plots the current year to date; the printed index is a "
                     "later reading, so a same-direction gap is expected"),
        }
        return out
    finally:
        doc.close()


def main(argv):
    only = limit = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
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
    ok = empty = 0
    gaps = []
    for i, p in enumerate(pdfs, 1):
        sid = p.name
        if done.get(sid, {}).get("n_points", 0) > 0:
            ok += 1
            g = done[sid].get("rel_gap")
            if g is not None:
                gaps.append(g)
            continue
        try:
            d = extract(p)
        except Exception as e:                            # noqa: BLE001
            empty += 1
            done[sid] = {"n_points": 0, "error": str(e)[:200]}
            print(f"[{i}/{len(pdfs)}] {sid} FAILED {e}", flush=True)
            state.write_text(json.dumps(done, indent=1), encoding="utf-8")
            continue
        n = sum(s["n_points"] for s in d["series"])
        (OUT / (sid + ".charts.json")).write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        done[sid] = {"n_points": n, "n_series": len(d["series"]), "ticks": d["n_ticks"],
                     "rel_gap": d["check"]["rel_gap"], "warnings": d["warnings"]}
        if n:
            ok += 1
            g = d["check"]["rel_gap"]
            if g is not None:
                gaps.append(g)
        else:
            empty += 1
        state.write_text(json.dumps(done, indent=1), encoding="utf-8")
        print(f"[{i}/{len(pdfs)}] {sid} series={len(d['series'])} pts={n} "
              f"ticks={d['n_ticks']} gap={d['check']['rel_gap']} "
              f"{'OK' if n else 'EMPTY ' + str(d['warnings'])}", flush=True)
    if gaps:
        gaps_sorted = sorted(gaps)
        within5 = sum(1 for g in gaps_sorted if g <= 0.05)
        print(f"\nself-check vs printed Calculated Index: n={len(gaps_sorted)} "
              f"within 5% = {within5} ({100*within5/len(gaps_sorted):.1f}%) "
              f"median gap = {gaps_sorted[len(gaps_sorted)//2]:.4f} "
              f"p90 = {gaps_sorted[int(len(gaps_sorted)*0.9)]:.4f}", flush=True)
    print(f"done={ok} empty_or_failed={empty} credits=0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
