"""Triage the 69 flagged (potentially glyph-ciphered) pages across sources.

The paid-surface scan flagged a handful of pages outside banchero. Before spending a
single credit on them, LOOK at them: the scan's detector is calibrated against known
cases, but a calibrated detector can still be wrong on an unusual page, and the whole
lesson of tonight is that a plausible machine reading is not proof.

This script, for every flagged page:
  * renders it to PNG,
  * reports the spans that tripped the detector,
  * prints the page's own text layer so the two can be compared at a glance.

Output: scratch/bench/png/flagged/<source>/<doc>_pNN.png plus a manifest. A human (or
vision) then decides per page whether the cloud is warranted. Nothing is sent anywhere.
"""
import glob
import importlib.util
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "bench" / "png" / "flagged"
MANIFEST = ROOT / "data" / "derived" / "flagged_pages_manifest.json"

_spec = importlib.util.spec_from_file_location(
    "mps", ROOT / "scripts" / "tools" / "measure_paid_surface.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

# the calibrated detector's triggers, so the manifest can show what fired
STRONG = M.STRONG_MARKERS


def tripping_spans(page):
    """The actual spans the detector matched, for inspection."""
    hits = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if M.span_is_ciphered(t):
                    hits.append({"text": t, "size": round(sp["size"], 1),
                                 "x": round(sp["bbox"][0]), "y": round(sp["bbox"][1])})
    return hits


def main():
    import pymupdf
    surface = json.loads((ROOT / "data/derived/paid_surface_by_source.json").read_text())
    targets = {k: v for k, v in surface.items()
               if isinstance(v, dict) and v.get("flagged_pages")
               and k != "banchero_costa"}          # banchero is already done via cloud
    manifest = {}
    total = 0
    for source, info in targets.items():
        pdfs = sorted(glob.glob(str(ROOT / f"corpus/01-brokers/{source}/*/*.pdf")))
        outdir = OUT / source
        outdir.mkdir(parents=True, exist_ok=True)
        found = []
        for p in pdfs:
            try:
                with pymupdf.open(p) as d:
                    for pno in range(d.page_count):
                        page = d[pno]
                        hits = tripping_spans(page)
                        if not hits:
                            continue
                        stem = os.path.basename(p)[:-4]
                        png = outdir / f"{stem}_p{pno+1}.png"
                        page.get_pixmap(dpi=150).save(png)
                        txt = page.get_text()[:900]
                        found.append({
                            "doc": stem, "page": pno + 1,
                            "png": str(png.relative_to(ROOT)),
                            "tripping_spans": hits[:6],
                            "tripping_count": len(hits),
                            "text_sample": txt,
                        })
            except Exception as e:
                print(f"  {source}: {os.path.basename(p)} error {str(e)[:80]}")
        manifest[source] = found
        total += len(found)
        print(f"{source:<20} flagged pages re-checked: {len(found)}")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print()
    print(f"total flagged pages outside banchero: {total}")
    print(f"rendered to {OUT}")
    print(f"manifest -> {MANIFEST}")
    print()
    print("Next: read the tripping spans. If a page's text layer shows real words and")
    print("numbers where the detector fired, the page is CLEAN and needs no credits.")


if __name__ == "__main__":
    main()
