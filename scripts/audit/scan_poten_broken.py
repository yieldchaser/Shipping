import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
from pathlib import Path
import pymupdf

root = Path('data/extracted/md/poten')
md_files = sorted(root.glob('*/*.md'))

tick_pat = re.compile(r'^(?:#+\s*)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-‐\'\s]?\d{2,4}$', re.M | re.I)
dollar_pat = re.compile(r'^(?:#+\s*)?[-‐]?\$\d+', re.M)

broken = []
total_pages = 0

for p in md_files:
    txt = p.read_text(encoding='utf-8')
    t_matches = tick_pat.findall(txt)
    d_matches = dollar_pat.findall(txt)
    is_llama = 'LlamaParse' in txt
    if (len(t_matches) >= 3 or len(d_matches) >= 3) and not is_llama:
        m_src = re.search(r'source_file:\s*"([^"]+)"', txt)
        pdf_path = Path(m_src.group(1)) if m_src else None
        pages = 0
        if pdf_path and pdf_path.exists():
            doc = pymupdf.open(pdf_path)
            pages = len(doc)
            doc.close()
        total_pages += pages
        broken.append((p, pdf_path, pages, len(t_matches), len(d_matches)))

print(f"Total Poten MD files: {len(md_files)}")
print(f"Broken files with chart tick spam: {len(broken)}")
print(f"Total pages across broken files: {total_pages}")
by_year = {}
for p, pdf, pages, tc, dc in broken:
    y = p.parent.name
    by_year[y] = by_year.get(y, 0) + 1
print("Broken by year:", dict(sorted(by_year.items())))
