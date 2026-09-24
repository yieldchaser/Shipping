"""Settle the intermodal final-segment disagreement, per pixel.

The open question: on 2025 W49 the BDI vector stroke's last vertices are
(571.6, 190.28) (572.0, 191.16) (572.5, 192.47) - a rise then a fall, ending at 2,465 -
while a 500-dpi render appears to show the line still rising to about 2,750 at the right
edge, matching the page's printed table value of 2,727.

Those cannot both be right. This measures the RENDERED line directly: it renders the plot
at high dpi, finds the darkest pixels in the right-hand 5% of the plot, and reports the
y of the line there. It then converts that y with the printed ladder and compares.

The rendered line is what a reader sees, so if it disagrees with the vector path, the
vector path is missing or duplicating something - and that is the finding.

Run:  python3 -B scratch/settle_intermodal_tail.py
"""
from __future__ import annotations

import glob
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ic", REPO / "scripts" / "extract" / "publishers" / "run_intermodal_charts.py")
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)

DPI = 600
SCALE = DPI / 72.0


def pixmap_rgb(page, clip):
    """(width, height, rgb bytes) for a clip, at DPI, via pymupdf's own raster."""
    pm = page.get_pixmap(dpi=DPI, clip=clip)
    return pm.width, pm.height, pm.samples, pm.n


def line_y_in_band(w, h, rgb, n, x0, x1, y0, y1, colour=None, tol=90):
    """For each pixel column in [x0, x1), the y of the pixel nearest `colour`.

    Nearest-to-target, NOT darkest. Measured 2025 W49, a darkest-pixel scan of the
    right-hand band returned y ~207-209 (~1,620) where the BDI vector vertex is at
    y=192.47 (~2,465) - a difference of 15pt, or three whole gridlines. The scan was
    picking a different series: the plot carries five lines and the darkest at any given
    column is whichever happens to be lowest, not the one asked for. BDI is drawn in
    near-black (0.2, 0.192, 0.196) and is unambiguous, so matching on colour is the
    correct discriminator and the darkest-pixel rule was simply the wrong test.
    """
    tr, tg, tb = colour or (0, 0, 0)
    out = {}
    for x in range(x0, x1):
        best_y, best_d = None, None
        for y in range(y0, y1):
            i = (y * w + x) * n
            r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
            d = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
            if best_d is None or d < best_d:
                best_d, best_y = d, y
        if best_y is not None and best_d is not None and best_d ** 0.5 <= tol:
            out[x] = best_y
    return out


def main():
    pdf = glob.glob(str(REPO / "corpus" / "01-brokers" / "intermodal" / "2025" / "*W49*.pdf"))[0]
    import pymupdf
    doc = pymupdf.open(pdf)
    try:
        page = doc[2]
        chart_frame, chart = None, None
        d2 = ic.extract(pdf)
        chart = next(c for c in d2["charts"] if c["ticks"] and c["ticks"][0]["v"] < 20000)
        frame = chart["frame"]
        ticks = sorted(((t["v"], t["y"]) for t in chart["ticks"]), key=lambda z: z[1])
        print(f"file          : {Path(pdf).name}")
        print(f"plot frame    : x {frame[0]:.1f}..{frame[2]:.1f}   y {frame[1]:.1f}..{frame[3]:.1f}")
        print("printed ladder: " + ", ".join(f"{int(v)}@{y:.1f}" for v, y in ticks))
        bdi = next(s for s in chart["series"] if s["name"] == "BDI")
        last = max(bdi["points"], key=lambda q: q["x"])
        print(f"BDI last VECTOR vertex: x={last['x']:.1f} y={last['y']:.2f} -> {last['value']}")
        print("printed table value   : 2727")
        print()

        clip = pymupdf.Rect(frame[0], frame[1], frame[2] + 1, frame[3] + 1)
        # the pixmap MUST be taken while the document is still open: rendering a page
        # after its document is closed raises 'invalid null reference'
        w, h, rgb, n = pixmap_rgb(page, clip)
    finally:
        doc.close()
    print(f"raster: {w} x {h} px at {DPI} dpi")

    # the right-hand 6% of the plot, in raster columns
    rx0 = int(w * 0.94)
    ry0, ry1 = 0, h
    bdi_rgb = bdi.get("colour") or [0.2, 0.192, 0.196]
    target = tuple(int(round(c * 255)) for c in bdi_rgb)
    print(f"matching pixels to BDI's stroke colour {bdi_rgb} -> RGB {target}")
    cols = line_y_in_band(w, h, rgb, n, rx0, w, ry0, ry1, colour=target)
    if not cols:
        print("no dark pixels found in the right-hand band - try a wider y range")
        return 1
    xs = sorted(cols)
    print(f"dark columns found: {len(cols)}  (from raster x {xs[0]} to {xs[-1]})")

    def val_at(raster_y):
        py = clip.y0 + raster_y / SCALE
        for i in range(len(ticks) - 1):
            (v0, y0), (v1, y1) = ticks[i], ticks[i + 1]
            if y0 <= py <= y1:
                return v0 + (py - y0) * (v1 - v0) / (y1 - y0)
        # outside the ladder: extend with the end interval
        if py < ticks[0][1]:
            (v0, y0), (v1, y1) = ticks[0], ticks[1]
        else:
            (v0, y0), (v1, y1) = ticks[-2], ticks[-1]
        return v0 + (py - y0) * (v1 - v0) / (y1 - y0)

    print()
    print("rendered line, right-hand columns (raster x -> page y -> value):")
    for x in xs[::max(1, len(xs) // 14)]:
        py = clip.y0 + cols[x] / SCALE
        px = clip.x0 + x / SCALE
        print(f"   page x={px:7.1f}  y={py:7.2f}  value={val_at(cols[x]):8.1f}")
    far = xs[-1]
    print()
    print(f"AT THE FAR RIGHT EDGE (page x={clip.x0 + far / SCALE:.1f}):")
    print(f"   rendered y={clip.y0 + cols[far] / SCALE:.2f}  value={val_at(cols[far]):.1f}")
    print(f"   vector   y={last['y']:.2f}  value={last['value']}")
    print(f"   printed        value=2727")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
