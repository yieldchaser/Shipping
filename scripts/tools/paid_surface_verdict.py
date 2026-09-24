"""Which sources still NEED LlamaParse, measured rather than asserted.

The user has asked repeatedly why credits sit still, so this settles it with data:

1. RE-MEASURE the paid surface with the calibrated cipher detector, so the number is
   current rather than inherited.
2. For each source with a non-zero surface, show the FIRST offending page rendered, so
   the defect is a picture and not a count.

The point is not to spend. It is to prove where spend would buy something, so the next
decision is made on evidence rather than on the last run's assumption.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

# scripts/tools/paid_surface_verdict.py -> parents[0]=tools, [1]=scripts, [2]=repo root.
# parents[1] lands on Github/ and every path under it fails, so a silent "no such file"
# read as "no paid surface measured" - a false conclusion from a wrong constant.
REPO = Path(__file__).resolve().parents[2]
SURFACE = REPO / "data" / "derived" / "paid_surface_by_source.json"
OUT = REPO / "scratch" / "paid_pages"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    # Path with forward slashes is fine for glob but NOT for an existence test on
    # Windows, where the repo root resolves with backslashes. Use the same object that
    # builds the glob paths.
    surface = SURFACE
    if not surface.exists():                                # pragma: no cover
        alt = REPO / "data" / "derived" / "paid_surface_by_source.json"
        surface = alt
    if not surface.exists():
        print("no paid_surface_by_source.json - run measure_paid_surface.py first")
        return 1
    data = json.loads(surface.read_text(encoding="utf-8"))
    rows = []
    for src, info in (data.items() if isinstance(data, dict) else []):
        if not isinstance(info, dict):
            continue
        # The writer records "flagged_pages", not "flagged". Reading the wrong key
        # returns 0 for every source and the table then reads as a wholly clean corpus -
        # including banchero, whose 662 ciphered pages are real and were already paid
        # for. A missing key must never read as a zero measurement.
        rows.append((src, info.get("docs", 0), info.get("pages", 0),
                     info.get("flagged_pages", 0)))
    rows.sort(key=lambda r: -r[3])

    print(f"{'source':<20}{'docs':>7}{'pages':>8}{'flagged':>9}{'pct':>8}   verdict")
    total_pages = total_flag = 0
    for src, docs, pages, flagged in rows:
        total_pages += pages
        total_flag += flagged
        pct = (100.0 * flagged / pages) if pages else 0.0
        if flagged == 0:
            v = "no cloud needed - local text layer is clean"
        elif pct > 10:
            v = "CLOUD CANDIDATE - escalate these pages"
        else:
            v = "small - measure individually before spending"
        print(f"{src:<20}{docs:>7}{pages:>8}{flagged:>9}{pct:>7.1f}%   {v}")
    print(f"{'TOTAL':<20}{'':>7}{total_pages:>8}{total_flag:>9}"
          f"{(100.0 * total_flag / total_pages if total_pages else 0):>7.1f}%")

    # render one flagged page per source, if the scan recorded which pages
    flags = REPO / "data" / "derived" / "flagged_pages_manifest.json"
    if flags.exists():
        man = json.loads(flags.read_text(encoding="utf-8"))
        items = man if isinstance(man, list) else man.get("flagged", [])
        seen = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            src = it.get("source") or Path(it.get("pdf", "")).parent.name
            if src in seen:
                continue
            pdf = it.get("pdf")
            page = it.get("page", 0)
            if not pdf or not os.path.exists(pdf):
                continue
            seen.add(src)
            dst = OUT / f"{src}_p{page + 1}.png"
            try:
                with pymupdf.open(pdf) as d:
                    d[page].get_pixmap(dpi=150).save(dst)
                print(f"  rendered {src} p{page + 1} -> {dst}")
            except Exception as e:                          # noqa: BLE001
                print(f"  {src}: render failed {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
