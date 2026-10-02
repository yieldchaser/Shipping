#!/usr/bin/env python3
import os
import re
from pathlib import Path

target_companies = [
    'VALE', 'RIO', 'BHP', 'FSUGY', 'SBLK', 'GOGL', 'GNK', 'SB', 'DSX', 'SHIP',
    'CTRM', 'GLBS', 'EDRY', 'FRO', 'INSW', 'STNG', 'DHT', 'TNK', 'TRMD', 'ECO',
    'NAT', 'TNP', 'ASC', 'SFL', 'NVGS', 'LPG'
]

corpus_dir = Path('corpus/10-companies')
forms = ['10-K', '20-F', '10-Q', '6-K', '8-K']

artifact_pat = re.compile(
    r'^\s*(COMMAND=|ZEQ=|Field:\s*|end of user-specified|User-specified TAGGED|PARA=JUSTIFY|TOC_END)',
    re.IGNORECASE
)

summary = []
total_md_files = 0
total_bytes = 0
bad_files = []

for ticker in target_companies:
    t_dir = corpus_dir / ticker
    row = {'ticker': ticker, '10-K': 0, '20-F': 0, '10-Q': 0, '6-K': 0, '8-K': 0, 'total': 0}
    if not t_dir.exists():
        row['status'] = 'MISSING_DIR'
        summary.append(row)
        continue
    
    for f in forms:
        f_dir = t_dir / f
        if f_dir.exists():
            mds = sorted(list(f_dir.glob('*.md')))
            row[f] = len(mds)
            row['total'] += len(mds)
            total_md_files += len(mds)
            for md in mds:
                sz = md.stat().st_size
                total_bytes += sz
                if sz < 300:
                    bad_files.append((str(md), f'Small file: {sz} bytes'))
                text = md.read_text(encoding='utf-8', errors='ignore')
                for line in text.splitlines():
                    if artifact_pat.match(line):
                        bad_files.append((str(md), f'Artifact line: {line[:50]}'))
                        break

    summary.append(row)

header = "| # | Ticker | 10-K | 20-F | 10-Q | 6-K | 8-K | Total Files |"
sep = "|---|--------|------|------|------|-----|-----|-------------|"
print(header)
print(sep)
for idx, r in enumerate(summary, 1):
    t = r['ticker']
    k10 = r['10-K']
    f20 = r['20-F']
    q10 = r['10-Q']
    k6 = r['6-K']
    k8 = r['8-K']
    tot = r['total']
    print(f"| {idx:02d} | {t:<6} | {k10:4d} | {f20:4d} | {q10:4d} | {k6:3d} | {k8:3d} | {tot:11d} |")

print()
print(f"Total Companies Audited: {len(summary)}")
print(f"Total Markdown Files: {total_md_files}")
print(f"Total Corpus Size: {total_bytes / (1024*1024):.2f} MB")
print(f"Defective Files Found: {len(bad_files)}")
if bad_files:
    print("Defective files sample:", bad_files[:5])
