import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

root = Path('data/extracted/md/poten')
llama_files = []
for p in root.glob('*/*.md'):
    txt = p.read_text(encoding='utf-8', errors='ignore')
    if 'parser: "LlamaParse' in txt:
        llama_files.append(p)

print(f"Total files parsed with LlamaParse in data/extracted/md/poten: {len(llama_files)}")
for p in llama_files[:15]:
    print(" ", p.parent.name + "/" + p.name)
