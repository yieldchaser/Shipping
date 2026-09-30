import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf
import re

ROOT = Path("corpus/04-poten/pdfs")
pdfs = sorted(ROOT.glob("*/*.pdf"))

print(f"Total Poten PDFs: {len(pdfs)}")

vector_chart_pdfs = []
raster_chart_pdfs = []
text_table_pdfs = []

for p in pdfs:
    try:
        doc = pymupdf.open(p)
        has_drawings = any(len(page.get_drawings()) > 30 for page in doc)
        txt = " ".join(page.get_text() for page in doc).lower()
        has_table_words = any(k in txt for k in ["top dirty charterers", "top clean charterers", "spot fixtures by tanker type", "reported spot dirty fixtures"])
        
        if has_drawings:
            vector_chart_pdfs.append(p)
        if has_table_words:
            text_table_pdfs.append(p)
        doc.close()
    except Exception:
        pass

print(f"PDFs with vector drawings (>30 paths): {len(vector_chart_pdfs)}")
print(f"PDFs with real table text (Charterer rankings/fixtures): {len(text_table_pdfs)}")
