import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import json

txt = Path('data/extracted/test_w13_llamaparse.md').read_text(encoding='utf-8')
lines = txt.splitlines()

current_h1 = ''
current_h2 = ''
current_h3 = ''

tables = []
for i, line in enumerate(lines):
    if line.startswith('# '):
        current_h1 = line[2:].strip()
        current_h2 = ''
        current_h3 = ''
    elif line.startswith('## '):
        current_h2 = line[3:].strip()
        current_h3 = ''
    elif line.startswith('### '):
        current_h3 = line[4:].strip()
    
    if '|' in line and i + 1 < len(lines) and any(s in lines[i+1] for s in ['| ---', '|:---', '|---']):
        headers = [c.strip().strip('*') for c in line.split('|')[1:-1]]
        rows = []
        j = i + 2
        while j < len(lines) and '|' in lines[j]:
            cells = [c.strip().strip('*').replace('~~', '') for c in lines[j].split('|')[1:-1]]
            if any(cells):
                rows.append(cells)
            j += 1
        tables.append({
            'h1': current_h1,
            'h2': current_h2,
            'h3': current_h3,
            'headers': headers,
            'num_rows': len(rows),
            'first_row': rows[0] if rows else []
        })

print(f'Total tables found: {len(tables)}')
for idx, t in enumerate(tables):
    ctx = f"{t['h1']} / {t['h2']} / {t['h3']}".strip(' /')
    print(f"{idx+1:02d}: [{ctx[:40]:40s}] H={t['headers'][:3]} | R={t['num_rows']} | {t['first_row'][:2]}")
