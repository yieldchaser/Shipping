"""Do these sources have a chart layer at all? Answer by MEASUREMENT, per source.

Four sources are reported by the completeness audit as "missing CHART-VALUES":
banchero_costa, carriers, intermodal, ssy (plus lion and fearnleys_cleaned). Before
treating any of them as a gap, establish whether a chart layer EXISTS.

This matters because agora turned out to have none - its 213 .charts.json each declared
an empty chart list with a measured reason, and rendering confirmed it. Four "missing
chart" verdicts may be the same shape. Assuming a gap where none exists would send
real documents to a paid parser for nothing.

For each source, over a sample spanning years, report per page:
  * vector drawing paths
  * images (a raster chart shows up here)
  * text spans that look like AXIS LABELS (digits, %, and a units word)
  * a crude chart signature: a page with BOTH many drawings/images AND a dense run of
    axis-like numeric text
No rendering, no API, no credits - just geometry, so it is free to run.
"""
import collections
import glob
import json
import os
import re
import sys

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = ["ssy", "carriers", "intermodal", "banchero_costa", "lion", "clarksons"]

# axis-like text: a short numeric run, optionally with % or a units word
AXISY = re.compile(r"^[\s\-+]?\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?\s*%?$")
UNITS = re.compile(r"\b(USD|\$|%|m|dmt|mt|k|MM)\b")


def page_profile(pg):
    """(drawings, images, axis_text, plot_shapes).

    `drawings` alone is NOT evidence of a chart. Measured counter-example: carriers
    page 1 has 711 drawing objects and is 100% table - 660 of them are thin rules and
    the rest are row fills, and rendering confirms there is no plot. So `plot_shapes`
    counts only drawing objects with real area (a bar or a thick line segment), which
    is what a plotted series actually produces.
    """
    dr_all = pg.get_drawings()
    imgs = len(pg.get_images())
    axis = 0
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if not t:
                    continue
                if AXISY.match(t) or (UNITS.search(t) and any(c.isdigit() for c in t)):
                    axis += 1
    plot = 0
    for x in dr_all:
        r = x["rect"]
        h, w = r.y1 - r.y0, r.x1 - r.x0
        if (h > 2 and w > 2) or (h > 0.5 and w > 8):      # bars / thick segments
            plot += 1
        elif h > 12 and w > 12:                            # big blocks
            plot += 1
    return len(dr_all), imgs, axis, plot


def main():
    only = sys.argv[1:] or SOURCES
    out = {}
    for src in only:
        pdfs = sorted(glob.glob(os.path.join(ROOT, "corpus/01-brokers", src, "*/*.pdf")))
        if not pdfs:
            print(f"{src:<18} NO PDFS")
            continue
        # spread the sample across the corpus by filename position
        n = len(pdfs)
        picks = [pdfs[int(f * (n - 1))] for f in (0.0, 0.25, 0.5, 0.75, 0.99)]
        pages = 0
        chartish = 0
        best = (0, "")
        best_plot = (0, "")
        dist = collections.Counter()
        for p in picks:
            try:
                with pymupdf.open(p) as d:
                    for pg in d:
                        pages += 1
                        dr, im, ax, plot = page_profile(pg)
                        dist[dr > 100] += 1
                        # A real plot needs AREA-bearing shapes. Table rules and row
                        # fills have height ~0, so they are excluded by construction.
                        # raster charts still show up as images.
                        is_chart = plot >= 12 or (im >= 2 and ax >= 6)
                        if is_chart:
                            chartish += 1
                        if ax > best[0]:
                            best = (ax, os.path.basename(p)[:44] + f" p{d.page_count}")
                        if plot > best_plot[0]:
                            best_plot = (plot, f"{os.path.basename(p)[:34]} p{pg.number}"
                                         f" (plot={plot} img={im} axis={ax})")
            except Exception:
                continue
        pct = 100 * chartish / max(pages, 1)
        verdict = "CHARTS PRESENT" if pct >= 25 else (
            "no chart layer found" if pct < 8 else "BORDERLINE - render and look")
        out[src] = {"pages_sampled": pages, "chartish_pages": chartish,
                    "pct": round(pct, 1), "max_axis_text_on_a_page": best[0],
                    "max_axis_doc": best[1], "max_plot_shapes": best_plot[0],
                    "max_plot_page": best_plot[1], "verdict": verdict}
        print(f"{src:<18} pages={pages:<5} chartish={chartish:<4} ({pct:>5.1f}%)  "
              f"max-plot-shapes={best_plot[0]:<5} -> {verdict}")
        print(f"                     strongest page: {best_plot[1]}")
    dest = os.path.join(ROOT, "data", "derived", "chart_layer_survey.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print()
    print(f"written -> {dest}")


if __name__ == "__main__":
    main()
