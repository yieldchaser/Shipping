import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)

print(f"Total pages: {len(doc)}")
for i, page in enumerate(doc):
    drawings = page.get_drawings()
    print(f"Page {i+1}: {len(drawings)} drawing paths")

doc.close()
