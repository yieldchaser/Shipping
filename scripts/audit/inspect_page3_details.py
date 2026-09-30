import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf

pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)

page3 = doc[2] # 0-indexed page 3
drawings = page3.get_drawings()
print(f"Page 3 total drawings: {len(drawings)}")

for idx, d in enumerate(drawings[:30]):
    color = d.get("color")
    fill = d.get("fill")
    items = d.get("items", [])
    rect = d.get("rect")
    print(f"Path {idx}: color={color}, fill={fill}, items_count={len(items)}, rect={rect}")

# Let's also check text on page 3
text_instances = page3.get_text("blocks")
print("\n--- Text blocks on page 3 ---")
for b in text_instances:
    print(f"Bbox: {b[:4]} -> {b[4][:60].strip()}")

doc.close()
