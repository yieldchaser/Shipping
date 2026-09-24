"""Does a source have a chart layer at all? MEASURE, do not infer from file counts.

For each source, find the page with the most vector content and render it, so the
question "are there charts to extract" is answered by looking, not by a heuristic
that has already lied twice in this programme (the cipher detector, the chart survey).

Run:  python3 -B scratch/find_chart_page.py carriers intermodal lion clarksons ism
"""
from __future__ import annotations

import glob
import os
import sys

import pymupdf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart_pages")
os.makedirs(OUT, exist_ok=True)


def profile(pg):
    """(drawings, images, long line paths, longest-path vertices)."""
    long_paths = 0
    max_verts = 0
    for d in pg.get_drawings():
        n = 0
        for it in d["items"]:
            if it[0] == "l":
                n += 1
        if n >= 20:
            long_paths += 1
            max_verts = max(max_verts, n)
    return len(pg.get_drawings()), len(pg.get_images()), long_paths, max_verts


def main(names):
    for src in names:
        pdfs = sorted(glob.glob(f"corpus/01-brokers/{src}/**/*.pdf", recursive=True))
        if not pdfs:
            print(f"{src}: NO PDFs")
            continue
        # SAMPLE across the source's span, never only the first file: layouts change by
        # era, and an era-blind sample is how a whole era gets missed. Profiling every
        # page of ~1,500 PDFs took over 7 minutes and had to be abandoned.
        step = max(1, len(pdfs) // 24)
        picks = pdfs[::step][:24] + pdfs[-2:]
        best = []
        for p in picks:
            try:
                with pymupdf.open(p) as d:
                    for i, pg in enumerate(d):
                        dr, im, lp, mv = profile(pg)
                        best.append((lp, mv, dr, im, p, i))
            except Exception:                                # noqa: BLE001
                continue
        best.sort(reverse=True)
        print(f"\n{src}: {len(pdfs)} PDFs, sampled {len(picks)} docs / "
              f"{len(best)} pages")
        if not best:
            print("   (no readable pages)")
            continue
        for lp, mv, dr, im, p, i in best[:3]:
            print(f"   lp={lp:<3} maxverts={mv:<4} drawings={dr:<5} images={im:<3} "
                  f"p{i + 1} {os.path.basename(p)[:50]}")
        lp, mv, dr, im, p, i = best[0]
        out = os.path.join(OUT, f"{src}_best.png")
        with pymupdf.open(p) as d:
            d[i].get_pixmap(dpi=150).save(out)
        print(f"   -> rendered {out}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["carriers"])
