import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf
import re

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)
page3 = doc[2] # 0-indexed page 3

# On page 3, top chart: "Scrap Prices Vs WS Rates"
# Let's inspect the exact line points in Path 200 (Red: $/Ldt) and Path 199/198 (WS Rates)
drawings = page3.get_drawings()

# Chart 1 boundaries:
# X spans: 157.5 to 460.5 pt
# Y spans: 69.75 ($400 / 200 WS) to 271.5 ($0 / 0 WS)
y_bottom = 271.5
y_top = 69.75
h = y_bottom - y_top # 201.75 pt

# Left scale: 0 to 400 $/Ldt
scale_ldt = 400.0 / h

# Right scale: 0 to 200 WS Rate
scale_ws = 200.0 / h

# X-axis ticks:
# Path 157: 157.5 (Jan-85)
# Path 158: 189.0 (Jan-87) -> step = 31.5 pt for 24 months = 1.3125 pt/month
# Path 159: 220.5 (Jan-89)
# Path 160: 252.0 (Jan-91)
# Path 161: 283.5 (Jan-93)
# Path 162: 315.0 (Jan-95)
# Path 163: 347.25 (Jan-97)
# Path 164: 378.75 (Jan-99)
# Path 165: 410.25 (Jan-01)
# Path 166: 441.75 (Jan-03)

# Path 200: Red line ($/Ldt)
p200 = drawings[200]
print(f"Red curve items: {len(p200['items'])}")

# Path 199: WS Rate curve line
p199 = drawings[199]
print(f"WS Rate curve items: {len(p199['items'])}")

# Let's sample every year or every 6 months along the path
print("\n--- EXACT VECTOR SAMPLES FOR 'Scrap Prices Vs WS Rates' ---")
# Let's check points at x = 157.5 (Jan-85), 189.0 (Jan-87), 220.5 (Jan-89), etc.
target_x = [
    (157.5, "Jan-85"),
    (189.0, "Jan-87"),
    (220.5, "Jan-89"),
    (252.0, "Jan-91"),
    (283.5, "Jan-93"),
    (315.0, "Jan-95"),
    (346.5, "Jan-97"),
    (378.0, "Jan-99"),
    (409.5, "Jan-01"),
    (441.0, "Jan-03"),
    (456.75, "Jan-04")
]

for x_val, label in target_x:
    # Find nearest point in Red line
    ldt_pts = [it[1] for it in p200['items'] if abs(it[1].x - x_val) < 2.0]
    ws_pts = [it[1] for it in p199['items'] if abs(it[1].x - x_val) < 2.0]
    
    ldt_val = round((y_bottom - ldt_pts[0].y) * scale_ldt, 1) if ldt_pts else None
    ws_val = round((y_bottom - ws_pts[0].y) * scale_ws, 1) if ws_pts else None
    
    print(f"{label} (x={x_val}): $/Ldt = {ldt_val}, WS Rate = {ws_val}")

doc.close()
