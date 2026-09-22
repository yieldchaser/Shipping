"""Prototype: split a two-up page at its word-density valley, then extract each
half as its own table. Measures throughput so the full sweep can be sized.

Design notes
------------
A strict "empty vertical band" detector was too brittle (it found page 0's
gutter and nothing on pages 1-5, where a single long word crosses the gap). This
scores valleys by density instead and requires both sides to be substantial, so
it cannot split off a thin margin or a page-number column.

Both halves are then given to Camelot via `table_areas`, which is the engine
already benched as primary - so this adds a region hint rather than a new
extractor.
"""
from __future__ import annotations

import glob
import os
import sys
import time

import pymupdf


def find_valley(page, min_side_frac: float = 0.15) -> tuple[float | None, dict]:
    """Return x of the sub-table boundary, or None if the page is single-table."""
    words = page.get_text("words")
    if not words:
        return None, {}
    W = page.rect.width
    step = 5.0
    nb = int(W / step) + 1
    hit = [0] * nb
    for w in words:
        for i in range(max(0, int(w[0] / step)), min(nb - 1, int(w[2] / step)) + 1):
            hit[i] += 1

    xs = [w[0] for w in words] + [w[2] for w in words]
    lo, hi = min(xs), max(xs)
    span = hi - lo
    if span < 50:
        return None, {}

    # interior candidates only, and each side must carry real content
    cands = []
    for i in range(nb):
        x = i * step
        if not (lo + span * min_side_frac < x < hi - span * min_side_frac):
            continue
        cands.append((hit[i], x))
    if not cands:
        return None, {}
    cands.sort()

    dens, x = cands[0]
    L = [w for w in words if w[2] <= x]
    R = [w for w in words if w[0] >= x]
    S = [w for w in words if w[0] < x < w[2]]
    peak = max(hit) or 1
    info = {"density": dens, "peak": peak, "left": len(L), "right": len(R),
            "straddling": len(S), "x": x}
    # reject if the valley is not actually quieter than its surroundings
    if dens > peak * 0.5:
        return None, info
    return x, info


def split_page(page, x: float) -> tuple[list, list]:
    words = page.get_text("words")
    L = [w for w in words if w[2] <= x]
    R = [w for w in words if w[0] >= x]
    # a word crossing the boundary goes to whichever side holds more of it
    for w in words:
        if w[0] < x < w[2]:
            (L if (x - w[0]) > (w[2] - x) else R).append(w)
    return L, R


def main() -> int:
    stem = sys.argv[1] if len(sys.argv) > 1 else ""
    which = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    matches = [p for p in glob.glob("reports/**/*.pdf", recursive=True)
               if stem[:40] in os.path.basename(p)]
    if not matches:
        sys.exit("no pdf")
    doc = pymupdf.open(matches[0])
    page = doc[which]

    t0 = time.time()
    x, info = find_valley(page)
    t_valley = time.time() - t0
    print(f"valley scan: {t_valley*1000:.0f} ms   ->  {info}")
    if x is None:
        print("page judged single-table; no split")
        return 0

    L, R = split_page(page, x)
    print(f"split at x={x:.0f}: left {len(L)} words, right {len(R)} words")
    print(f"  left : {[w[4] for w in L[:10]]}")
    print(f"  right: {[w[4] for w in R[:10]]}")

    # time camelot on the two halves via table_areas
    import camelot
    W = page.rect.width
    H = page.rect.height
    for name, x0, x1 in (("LEFT", 0, x), ("RIGHT", x, W)):
        t1 = time.time()
        area = f"{x0},{H},{x1},0"
        try:
            tl = camelot.read_pdf(matches[0], pages=str(which + 1),
                                  flavor="stream", table_areas=[area])
            dt = time.time() - t1
            print(f"  camelot {name}: {len(tl)} table(s) in {dt:.2f}s", end="")
            if len(tl):
                df = tl[0].df
                print(f"  shape={df.shape}")
                print("     header:", list(df.iloc[0])[:6])
                print("     row1  :", list(df.iloc[1])[:6] if len(df) > 1 else "")
            else:
                print()
        except Exception as e:
            print(f"  camelot {name}: FAILED {str(e)[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
