#!/usr/bin/env python3
"""
Helper to render specified pages from book PDFs to PNG for visual inspection.
"""
import sys
from pathlib import Path
import pymupdf

SCRATCH_DIR = Path(r"C:\Users\Dell\.gemini\antigravity\brain\a5d78b66-3c04-43e1-8233-27a1b8e1ae5a\scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

def render_pages(pdf_path: str, page_numbers: list[int], prefix: str, dpi: int = 150):
    """
    Renders 1-indexed page_numbers from pdf_path to PNG.
    """
    p = Path(pdf_path)
    if not p.exists():
        # try glob matching in same parent directory
        parent = p.parent if p.parent != Path(".") else Path("corpus/books")
        matches = list(parent.glob(p.name))
        if not matches:
            matches = [f for f in parent.glob("*.pdf") if p.stem.split()[0].lower() in f.stem.lower()]
        if matches:
            p = matches[0]
            print(f"Matched PDF: {p}")
        else:
            raise FileNotFoundError(f"Cannot resolve PDF: {pdf_path}")
            
    doc = pymupdf.open(p)
    output_files = []
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    
    for p_num in page_numbers:
        if 1 <= p_num <= len(doc):
            page = doc[p_num - 1]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_name = f"{prefix}_page_{p_num:03d}.png"
            out_path = SCRATCH_DIR / out_name
            pix.save(str(out_path))
            print(f"Rendered: {out_path} ({pix.width}x{pix.height})")
            output_files.append(out_path)
        else:
            print(f"Warning: page {p_num} out of bounds (1-{len(doc)})")
    doc.close()
    return output_files

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python render_book_pages.py <pdf_path> <prefix> <page1> [page2 ...]")
        sys.exit(1)
    pdf = sys.argv[1]
    pref = sys.argv[2]
    pages = [int(x) for x in sys.argv[3:]]
    render_pages(pdf, pages, pref)
