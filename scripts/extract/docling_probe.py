"""Docling smoke test: does it actually run here, and what does it cost per page?

Docling was benched as a gatekeeper (~1,900 s/doc on CPU) but never verified
working on this box, and it produced 0 cells in the corpus - so its claimed
recall was never exercised against the real data. Before spending hours on a
sample cross-check, confirm it runs and measure its true cost on ONE document.

Usage:
    python scripts/extract/docling_probe.py <pdf_path> [max_pages]
"""
from __future__ import annotations

import os
import sys
import time


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: docling_probe.py <pdf_path> [max_pages]")
        return 2
    pdf = sys.argv[1]
    maxp = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if not os.path.exists(pdf):
        print(f"not found: {pdf}")
        return 1

    print(f"pdf: {pdf}")
    print(f"size: {os.path.getsize(pdf)/1e6:.2f} MB   pages capped at {maxp}")

    t0 = time.time()
    try:
        from docling.document_converter import DocumentConverter
        print(f"import ok ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"IMPORT FAILED: {type(e).__name__}: {str(e)[:200]}")
        return 1

    t0 = time.time()
    try:
        conv = DocumentConverter()
        print(f"converter built ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"CONVERTER FAILED: {type(e).__name__}: {str(e)[:200]}")
        return 1

    t0 = time.time()
    try:
        res = conv.convert(pdf, page_range=(1, maxp))
        dt = time.time() - t0
        doc = res.document
        per_page = dt / max(maxp, 1)
        print(f"\nCONVERTED in {dt:.1f}s  ({per_page:.0f}s/page for {maxp} pages)")
        try:
            md = doc.export_to_markdown()
        except Exception:
            md = ""
        print(f"  markdown chars : {len(md):,}")
        try:
            n_tables = len(doc.tables)
        except Exception:
            n_tables = "n/a"
        print(f"  tables detected: {n_tables}")
        print(f"\n  first 400 chars:\n    {md[:400]!r}")
        print(f"\nEXTRAPOLATED full-corpus cost at this rate: "
              f"{per_page * 100000 / 3600:.0f} CPU-hours for 100k pages")
    except Exception as e:
        print(f"CONVERT FAILED after {time.time()-t0:.1f}s: "
              f"{type(e).__name__}: {str(e)[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
