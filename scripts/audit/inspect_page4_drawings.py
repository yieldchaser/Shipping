import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)
page4 = doc[3] # 0-indexed page 4

drawings = page4.get_drawings()
print(f"Page 4 total drawings: {len(drawings)}")

for idx, d in enumerate(drawings):
    rect = d.get("rect")
    color = d.get("color")
    fill = d.get("fill")
    items = d.get("items", [])
    if len(items) > 10:
        print(f"Drawing {idx}: color={color}, fill={fill}, count={len(items)}, rect={rect}")

doc.close()
