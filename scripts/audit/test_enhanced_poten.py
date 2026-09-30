import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import run_poten

orig_is_chart_chunk = run_poten.is_chart_chunk

DATE_TICK_PAT = re.compile(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-‐–—\s\'/]*\d{2,4}$', re.I)
NUM_TICK_PAT = re.compile(r'^[-\$‐–—]?\s*\$?\s*\d+(?:\.\d+)?%?$', re.I)
CHART_UNITS = {
    '$/ton', 'rebar', '$/ldt', 'ws', 'rate', 'rates', '000', 'tons', '$/bbl',
    'kbd', 'bpd', 'mm', 'bbls', 'blls', 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
    'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'tce'
}

def is_chart_chunk_enhanced(chunk: str, pno: int) -> bool:
    c = chunk.strip()
    if not c:
        return True
    c_lower = c.lower()
    lines = [l.strip() for l in c.splitlines() if l.strip()]
    if not lines:
        return True
    words = re.findall(r"\b[A-Za-z0-9'$/%-]+\b", c)
    num_words = len(words)

    # Captions, legends, sources
    if re.match(r'^(?:fig|figure|chart|graph|source|table)\s*[:\.\d]', c_lower):
        return True
    if any(h in c_lower for h in ['poten & partners', 'www.poten.com', 'tankerresearch@', 'research@poten.com', 'eia/poten', '/eia', 'source:']):
        if num_words <= 8:
            return True

    # Currency ticks or number ticks
    if all(NUM_TICK_PAT.match(l) for l in lines):
        return True

    # Date ticks
    if all(DATE_TICK_PAT.match(l) or l.isdigit() for l in lines):
        return True

    # Multi-tick string on a single line
    tokens = c.split()
    if len(tokens) >= 2 and all(
        NUM_TICK_PAT.match(t) or DATE_TICK_PAT.match(t) or t.lower() in CHART_UNITS
        for t in tokens
    ):
        return True

    # Axis units / single units e.g. $/ldt, WS Rates
    if num_words <= 4 and set(w.lower() for w in words).issubset(CHART_UNITS):
        return True

    return orig_is_chart_chunk(chunk, pno)

run_poten.is_chart_chunk = is_chart_chunk_enhanced

from collections import defaultdict
pdf_path = ROOT / "corpus" / "04-poten" / "pdfs" / "2004" / "Tanker_Opinion_20040305.pdf"
meta, full_md, tables_data, ch_rows, md_rel, tbl_rel = run_poten.process_pdf(pdf_path, defaultdict(int))

print("=== FULL EXTRACTED MARKDOWN (Tanker_Opinion_20040305.pdf) ===")
print(full_md)
print("=== END MARKDOWN ===")
