import re
from pathlib import Path
from collections import Counter

ROOT = Path(r"c:\Users\Dell\Github\Shipping")
MD_DIR = ROOT / "corpus" / "01-brokers" / "fearnleys-md"

files = list(MD_DIR.rglob("*.md"))
print(f"Total markdown files in {MD_DIR}: {len(files)}")

by_year = Counter([f.parent.name for f in files])
print("Distribution by folder:")
for y, c in sorted(by_year.items()):
    print(f"  {y}: {c} files")

all_img_urls = set()
files_with_imgs = 0
for f in files:
    txt = f.read_text(encoding="utf-8", errors="ignore")
    urls = re.findall(r"https://pbrkapp\.blob\.core\.windows\.net[^\)\s\"]+", txt)
    if urls:
        files_with_imgs += 1
        all_img_urls.update(urls)

print(f"\nFiles with image links: {files_with_imgs} / {len(files)}")
print(f"Total unique Azure Blob image URLs: {len(all_img_urls)}")

print("\nSample URLs (first 5):")
for u in sorted(list(all_img_urls))[:5]:
    print(f"  {u}")
