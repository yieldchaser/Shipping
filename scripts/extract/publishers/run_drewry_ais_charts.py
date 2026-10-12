"""
Drewry AIS Analytics: exact weekly series from the vector charts.

The Drewry AIS PDFs are Power BI exports. Every chart line is a vector path whose points are the data
points, so values are read from geometry, not estimated:
  - a chart is found by its title (bold 12 pt, white on the title bar) and spans the area up to
    the next title to the right and below;
  - the y scale is fitted to the chart's own printed tick labels (the centre of their digits);
  - the x scale is fitted to the chart's own axis labels: "Week 10..50" (seasonal charts, one line per
    year), year labels on Jan 1 ticks, or "Jul 2024" month labels;
  - each line is named by the legend swatch of the same colour ("2025", "% laden 2026", "Laden");
    single-line charts take the chart title. Lines on a right axis ("Spot rate (right axis)", "TD8 (right
    axis)", "Bunker price (right axis)") are Baltic routes and bunker prices we hold elsewhere: skipped.
Every point must land on an axis position or it is dropped and logged: a seasonal point within 0.2 of a
whole week; a dated point between Thursday and Sunday of one ISO week, keyed by that ISO year and week.
The year labels fix a dated axis only to about two days, so weekly rows carry no day (date is empty).
Flat reference lines ("High", "Low" on the 2024 fleet pages) are logged, not stored. The lines are smoothed Bezier paths: the data
points are the segment end points; the control points between them are drawing aids, not data (the
previous version of this script read a control point as the value and numbered points by position, so
its series were wrong and were deleted). A chart whose scales cannot be fitted is skipped and logged,
never guessed. The bar chart "Change in trading status"
is a month-on-month derivative of the fleet-performance lines and is not read.

Each report carries the full history of its charts, so the newest report per vessel class wins for any
week it covers; older reports only add weeks the newer ones no longer show.

Output: data/extracted/series/drewry_ais_chart_series.csv
  vessel_class, sector, page, chart, series, unit, axis, year, week, value, source_file
  axis "weekly": a dated line; year/week = the ISO week of the point;
  axis "seasonal": one line per year against the chart's own week number (1-53; year from the legend).
  A line of a single point (week 1 of a new year) is not drawn as a path and cannot be read.
"""

import csv
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

import pymupdf

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
AIS_CORPUS_DIR = os.path.join(REPO_ROOT, "corpus", "06-drewry", "ais")
OUT_CSV = os.path.join(REPO_ROOT, "data", "extracted", "series", "drewry_ais_chart_series.csv")
FIELDS = ["vessel_class", "sector", "page", "chart", "series", "unit", "axis", "year", "week", "value", "source_file"]
KEY = ["vessel_class", "chart", "series", "axis", "year", "week"]

VESSEL_CLASSES = {
    "Drybulk_Capesize": ("Dry Bulk", "Capesize"),
    "Drybulk_Panamax": ("Dry Bulk", "Panamax"),
    "Drybulk_Supramax": ("Dry Bulk", "Supramax"),
    "Drybulk_Handysize": ("Dry Bulk", "Handysize"),
    "Crude_VLCC": ("Crude Tankers", "VLCC"),
    "Crude_Suezmax": ("Crude Tankers", "Suezmax"),
    "Crude_Aframax": ("Crude Tankers", "Aframax"),
    "Product_LR1": ("Product Tankers", "LR1"),
    "Product_LR2": ("Product Tankers", "LR2"),
    "LPG_FR": ("Gas Shipping", "LPG FR"),
}
FILE_RE = re.compile(r"Drewry_AIS_(?:PDF_)?(" + "|".join(VESSEL_CLASSES) + r")_Week(\d+)_(\d{4})", re.I)
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                                      "Dec"], 1)}
SKIP_CHARTS = ("change in trading status",)
WEEK_TOL = 0.2       # weeks: a seasonal point must sit this close to a whole week
WEEK_FROM_DAY = 3    # weekday (Thursday): a dated point must sit from here to the end of its ISO week
TICK_TOL = 0.01      # share of the tick step: largest misfit allowed between the ticks and the y fit
DIGIT_MID = 0.358   # em: half the height of Arial figures above the baseline
LINE_W = 2.25        # stroke width of Power BI data lines in these exports


def _num(s):
    s = s.replace(",", "").replace("%", "").replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _fit(pairs):
    """Least-squares a + b*x over (x, y) pairs -> (a, b, largest residual)."""
    xs, ys = zip(*pairs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in pairs) / sxx
    a = my - b * mx
    return a, b, max(abs(a + b * x - y) for x, y in pairs)


def _spans(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for s in ln["spans"]:
                if s["text"].strip():
                    out.append({"text": s["text"].strip(), "bbox": pymupdf.Rect(s["bbox"]), "font": s["font"],
                                "size": s["size"], "color": s["color"], "dir": ln["dir"],
                                "origin": s["origin"]})
    return out


def _panels(page, spans, k):
    titles = [s for s in spans if "Bold" in s["font"] and round(s["size"] / k) == 12
              and s["color"] == 0xFFFFFF]
    panels = []
    for t in titles:
        r = t["bbox"]
        right = min([o["bbox"].x0 for o in titles if o["bbox"].x0 > r.x0 + 20 * k and abs(o["bbox"].y0 - r.y0) < 20 * k]
                    + [page.rect.width])
        below = min([o["bbox"].y0 for o in titles if o["bbox"].y0 > r.y1 + 20 * k and o["bbox"].x0 < right - 20 * k
                     and o["bbox"].x0 > r.x0 - 200 * k] + [page.rect.height])
        panels.append((t["text"], pymupdf.Rect(r.x0 - 20 * k, r.y1, right - 10 * k, below - 5 * k)))
    return panels


def _color(c):
    return tuple(round(v, 2) for v in c) if c else None


def read_chart(page, spans, drawings, title, box, log, k=1.0):
    """k: page scale against the 996 pt wide Power BI page (some 2024 exports are drawn at 2x)."""
    inside = [s for s in spans if box.contains(s["bbox"].tl) and s["text"] != title]
    lines = [d for d in drawings if abs((d.get("width") or 0) / k - LINE_W) < 0.01 and d.get("color")
             and _color(d["color"]) != (1.0, 1.0, 1.0) and box.contains(d["rect"].tl) and len(d["items"]) >= 2]
    if not lines:
        return []
    px0 = min(d["rect"].x0 for d in lines)
    px1 = max(d["rect"].x1 for d in lines)
    py1 = max(d["rect"].y1 for d in lines)

    # legend: filled squares with the entry text right after them
    legend = {}
    for d in drawings:
        r = d["rect"]
        if d.get("fill") and 5 * k < r.width < 10 * k and 5 * k < r.height < 10 * k and box.contains(r.tl) and r.y0 > py1:
            txt = [s for s in inside if 0 <= s["bbox"].x0 - r.x1 < 8 * k
                   and abs((s["bbox"].y0 + s["bbox"].y1) / 2 - (r.y0 + r.y1) / 2) < 4 * k]
            if txt:
                legend[_color(d["fill"])] = txt[0]
    legend_spans = {id(s) for s in legend.values()}

    # y scale: numeric labels left of the plot. Power BI centres each label on its value; the centre of the
    # digits (baseline - 0.358 em, Arial figures are 0.716 em tall) reproduces the report's own figures:
    # tonne-miles index 100.0 in its base week and 90.7 on the KPI tile, bunker $859. The white strokes near
    # the labels are line halos, not gridlines.
    ylabels = [s for s in inside if s["dir"] == (1.0, 0.0) and s["bbox"].x1 <= px0 + 2 * k and _num(s["text"]) is not None]
    # the tick labels are right-aligned in one column; a week label at the plot's corner is not one of them
    edges = Counter(round(s["bbox"].x1 / k) for s in ylabels)
    if edges:
        col = max(edges, key=lambda e: sum(n for x, n in edges.items() if abs(x - e) <= 1))
        ylabels = [s for s in ylabels if abs(s["bbox"].x1 / k - col) <= 1.5]
    ypairs = [(s["origin"][1] - DIGIT_MID * s["size"], _num(s["text"])) for s in ylabels]
    if len(ypairs) < 2 or len({v for _, v in ypairs}) < 2:
        log.append(f"{title}: fewer than 2 y ticks")
        return []
    ya, yb, yres = _fit(ypairs)
    step = min(abs(b - a) for a, b in zip(sorted(v for _, v in ypairs), sorted(v for _, v in ypairs)[1:]) if b != a)
    if yres > TICK_TOL * step:
        log.append(f"{title}: y ticks not linear (misfit {yres:.4f})")
        return []
    decimals = max((len(s["text"].replace("%", "").split(".")[1]) if "." in s["text"] else 0) for s in ylabels) + 2
    unit = "%" if any("%" in s["text"] for s in ylabels) else next(
        (s["text"] for s in inside if s["dir"] != (1.0, 0.0) and s["bbox"].x1 <= px0 and s["text"].isalpha()), "")
    if not unit and "index" in title.lower():
        unit = "index"

    # x scale
    below = [s for s in inside if s["dir"] == (1.0, 0.0) and s["bbox"].y0 >= py1 - 2 * k and id(s) not in legend_spans
             and s["bbox"].x0 >= px0 - 15 * k and s["bbox"].x1 <= px1 + 15 * k]
    # seasonal charts number the weeks 10..50; a dated axis may also carry the axis title "Week"
    xpairs = [((s["bbox"].x0 + s["bbox"].x1) / 2, _num(s["text"])) for s in below
              if re.fullmatch(r"[1-5]0", s["text"])]
    seasonal = len(xpairs) >= 2 and any(s["text"] == "Week" for s in below)
    if not seasonal:
        xpairs = []
        for s in below:
            cx = (s["bbox"].x0 + s["bbox"].x1) / 2
            if re.fullmatch(r"20\d\d", s["text"]):
                xpairs.append((cx, date(int(s["text"]), 1, 1).toordinal()))
            elif re.fullmatch(r"[A-Z][a-z]{2} 20\d\d", s["text"]) and s["text"][:3] in MONTHS:
                xpairs.append((cx, date(int(s["text"][4:]), MONTHS[s["text"][:3]], 1).toordinal()))
    if len(xpairs) < 2:
        log.append(f"{title}: fewer than 2 x labels")
        return []
    xa, xb, xres = _fit(xpairs)
    if xres > (0.25 if seasonal else 1.5):
        log.append(f"{title}: x labels not linear (misfit {xres:.3f})")
        return []

    rows = []
    for d in lines:
        c = _color(d["color"])
        if legend:
            if c not in legend:
                log.append(f"{title}: line colour {c} not in legend")
                continue
            name = legend[c]["text"]
        elif len(lines) == 1:
            name = ""
        else:
            log.append(f"{title}: {len(lines)} lines and no legend")
            return []
        if "right axis" in name.lower():
            continue
        pts = [d["items"][0][1]] + [it[-1] for it in d["items"]]
        if seasonal:
            m = re.search(r"\b(20\d\d)\b", name)
            if not m:
                log.append(f"{title}: seasonal line '{name}' has no year")
                continue
            year, series = int(m.group(1)), re.sub(r"\s*\b20\d\d\b\s*", " ", name).strip()
            seen = set()
            for p in pts:
                w = xa + xb * p.x
                if abs(w - round(w)) > WEEK_TOL or not 1 <= round(w) <= 53 or round(w) in seen:
                    log.append(f"{title} {name}: point at week {w:.2f} dropped")
                    continue
                seen.add(round(w))
                rows.append({"series": series, "axis": "seasonal", "year": year, "week": round(w),
                             "value": ya + yb * p.y})
        else:
            if len(pts) > 2 and max(p.y for p in pts) - min(p.y for p in pts) < 1e-6:
                log.append(f"{title} {name}: flat reference line at {round(ya + yb * pts[0].y, decimals)}, "
                           "not a series")
                continue
            # The year labels fix the date axis only to about two days (0.13 pt per day), so a point's exact
            # day is not readable; its ISO week is: every weekly point falls Thursday to Sunday.
            seen = {}
            for p in pts:
                f = xa + xb * p.x
                day = date.fromordinal(int(f))
                if day.weekday() < WEEK_FROM_DAY:
                    log.append(f"{title} {name}: point at {day} +{f % 1:.2f}d not Thursday-Sunday, dropped")
                    continue
                iso = day.isocalendar()
                if iso[:2] in seen:
                    # some 2024 exports draw each week twice, a day apart, at the same height
                    if abs(seen[iso[:2]] - p.y) > 1e-6:
                        log.append(f"{title} {name}: second point in {iso[0]}-W{iso[1]} at another value, dropped")
                    continue
                seen[iso[:2]] = p.y
                rows.append({"series": name, "axis": "weekly", "year": iso[0], "week": iso[1],
                             "value": ya + yb * p.y})
    for r in rows:
        r.update(chart=title, unit=unit, value=round(r["value"], decimals))
    return rows


def extract_report(path, log):
    doc = pymupdf.open(path)
    rows = []
    for page in doc:
        spans = _spans(page)
        k = max(1, round(page.rect.width / 996))   # some 2024 exports are drawn at exactly 2x on a 1920 pt page
        header = [s["text"] for s in spans if s["color"] == 0xFFFFFF and round(s["size"] / k) == 14]
        page_name = header[-1] if header else f"page {page.number + 1}"
        panels = _panels(page, spans, k)
        if not panels:
            continue
        drawings = page.get_drawings()
        for title, box in panels:
            if title.lower().startswith(SKIP_CHARTS):
                continue
            chart_log = []
            got = read_chart(page, spans, drawings, title, box, chart_log, k)
            log.extend(f"  p{page.number + 1} {m}" for m in chart_log)
            for r in got:
                r["page"] = page_name
            rows.extend(got)
    doc.close()
    return rows


def reports():
    """{class key: [(year, week, path)] oldest first}."""
    out = defaultdict(list)
    if not os.path.isdir(AIS_CORPUS_DIR):    # gitignored: absent on CI until the fetcher downloads a PDF
        return out
    for fn in os.listdir(AIS_CORPUS_DIR):
        m = FILE_RE.search(fn)
        if fn.lower().endswith(".pdf") and m:
            key = next(k for k in VESSEL_CLASSES if k.lower() == m.group(1).lower())
            out[key].append((int(m.group(3)[:4]), int(m.group(2)), os.path.join(AIS_CORPUS_DIR, fn)))
    for v in out.values():
        v.sort()
    return out


def main():
    verbose = "-v" in sys.argv
    table = {}
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                table[tuple(r[k] for k in KEY)] = r
    for key, files in sorted(reports().items()):
        sector, vessel = VESSEL_CLASSES[key]
        for _, _, path in files:
            log = []
            rows = extract_report(path, log)
            fn = os.path.basename(path)
            for r in rows:
                r.update(vessel_class=vessel, sector=sector, source_file=fn)
                r = {k: str(r[k]) for k in FIELDS}
                table[tuple(r[k] for k in KEY)] = r
            print(f"{fn}: {len(rows)} points, {len({(r['chart'], r['series']) for r in rows})} lines, "
                  f"{sum('dropped' in m for m in log)} points dropped, "
                  f"{sum('reference line' in m for m in log)} reference lines, "
                  f"{sum('dropped' not in m and 'reference line' not in m for m in log)} chart problems")
            for m in log:
                if verbose or ("dropped" not in m and "reference line" not in m):
                    print(m)
    out = sorted(table.values(), key=lambda r: (r["sector"], r["vessel_class"], r["page"], r["chart"], r["series"],
                                                r["axis"], int(r["year"]), int(r["week"])))
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} rows -> {os.path.relpath(OUT_CSV, REPO_ROOT)}")


if __name__ == "__main__":
    main()
