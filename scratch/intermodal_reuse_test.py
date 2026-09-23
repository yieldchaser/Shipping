"""
Intermodal: can the EXISTING tested parser be reused over the PDF corpus?

The situation (measured):
  * 252 PDFs, 2021-2026, newest W38.
  * data/derived/intermodal_tc_rates.csv has only 49 rows: 2025-03-07 -> 2026-09-11.
  * scripts/update_intermodal_tc_rates.py parses *.md* from
    reports/broker_reports/2026 - a directory DELETED in the corpus migration,
    so the script cannot update. 22 scripts reference that dead path.
  * 47 intermodal .md files survive only inside an old agent worktree.

So the rates are ingested for ~18 months and dead thereafter, while the PDFs hold
5+ years. The right move is to reuse the tested regex set, not to write a
parallel parser - the fields and their patterns are already validated.

This tests whether those regexes fire on PyMuPDF text taken straight from the
PDFs (no .md step), across several years.
"""
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "scripts")
from update_intermodal_tc_rates import RATE_FIELDS  # noqa: E402

DOCS = {
    "2021": "corpus/01-brokers/intermodal/2021",
    "2023": "corpus/01-brokers/intermodal/2023",
    "2024": "corpus/01-brokers/intermodal/2024",
    "2026": "corpus/01-brokers/intermodal/2026",
}

print("=" * 92)
print("DOES THE EXISTING PARSER FIRE ON PDF TEXT? (reuse beats rewrite)")
print("=" * 92)
print(f"{'yr':<6}{'file':<44}{'fields hit':>11}{'of':>4}   missing")
print("-" * 92)

grand = {}
for yr, d in DOCS.items():
    pdfs = sorted(Path(d).glob("*.pdf"))
    if not pdfs:
        continue
    p = pdfs[len(pdfs) // 2]
    with pymupdf.open(p) as doc:
        txt = "".join(pg.get_text() for pg in doc)
    hits = []
    for name, pat in RATE_FIELDS:
        if re.search(pat, txt, re.I):
            hits.append(name)
    miss = [n for n, _ in RATE_FIELDS if n not in hits]
    grand[yr] = (len(hits), p.name)
    print(f"{yr:<6}{p.name[:42]:<44}{len(hits):>11}{len(RATE_FIELDS):>4}   "
          f"{','.join(m.split('_')[0] for m in miss[:6])}")

print()
print("=" * 92)
print("IF IT FIRES: show the values from one doc so they can be judged by eye")
print("=" * 92)
p = sorted(Path(DOCS['2026']).glob("*.pdf"))[len(sorted(Path(DOCS['2026']).glob('*.pdf'))) // 2]
with pymupdf.open(p) as doc:
    txt = "".join(pg.get_text() for pg in doc)
print(f"  doc: {p.name[:70]}")
for name, pat in RATE_FIELDS[:10]:
    m = re.search(pat, txt, re.I)
    print(f"    {name:<20} {'= ' + m.group(1) if m else 'MISS'}")
