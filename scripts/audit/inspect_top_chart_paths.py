import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)
page3 = doc[2]

drawings = page3.get_drawings()
for idx, d in enumerate(drawings):
    rect = d.get("rect")
    # Top chart is between y=60 and y=270
    if rect and rect.y0 >= 50 and rect.y1 <= 280:
        color = d.get("color")
        fill = d.get("fill")
        items = d.get("items", [])
        print(f"Path {idx}: color={color}, fill={fill}, items_count={len(items)}, rect={rect}")
        if len(items) > 5:
            # Print first 5 items
            for it in items[:5]:
                print("   ", it)

doc.close()
