import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)
page4 = doc[3]

drawings = page4.get_drawings()
# Blue line is drawing 112
d112 = drawings[112]
print(f"Blue line rect: {d112['rect']}")
print("Sample items from 2001-2004 (x > 350):")
for it in d112['items']:
    pt = it[1]
    if pt.x > 350:
        print(f"  x={pt.x:.1f}, y={pt.y:.1f}")

# Y-axis bounds on page 4:
# WS axis: 0 at y=472.5, 200 at y=270.75 (height = 201.75 pt)
y_bottom = 472.5
y_top = 270.75
scale_ws = 200.0 / (y_bottom - y_top)

print("\n--- CALCULATED WS RATES FOR 2001-2004 ---")
for it in d112['items']:
    pt = it[1]
    if pt.x > 350 and pt.x % 10 < 1.5:
        ws = (y_bottom - pt.y) * scale_ws
        print(f"  x={pt.x:.1f}: WS Rate = {ws:.1f}")

doc.close()
