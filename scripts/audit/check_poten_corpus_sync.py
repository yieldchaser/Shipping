import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
from pathlib import Path

extracted = list(Path('data/extracted/md/poten').glob('*/*.md'))
corpus = list(Path('corpus/04-poten').glob('[0-9]*/*.md'))

corpus_by_pdf = {}
for cf in corpus:
    txt = cf.read_text(encoding='utf-8', errors='ignore')
    m = re.search(r'pdf_file:\s*"([^"\r\n]+)"', txt)
    if not m:
        m = re.search(r'pdf_file:\s*([^\r\n]+)', txt)
    if m:
        p_name = Path(m.group(1).strip().strip('"').strip("'")).name
        corpus_by_pdf[p_name] = cf

matched = 0
for ex in extracted:
    txt = ex.read_text(encoding='utf-8')
    m_src = re.search(r'source_file:\s*"([^"]+)"', txt)
    if m_src:
        pdf_name = Path(m_src.group(1)).name
        if pdf_name in corpus_by_pdf:
            matched += 1

print(f"Total extracted: {len(extracted)}")
print(f"Total corpus: {len(corpus)}")
print(f"Extracted matching corpus by pdf_file: {matched}")
