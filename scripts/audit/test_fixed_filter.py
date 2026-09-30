import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
from pathlib import Path
import pymupdf

def is_chart_chunk_fixed(chunk: str, pno: int) -> bool:
    c = chunk.strip()
    if not c:
        return True
    c_lower = c.lower()
    lines = [l.strip() for l in c.splitlines() if l.strip()]
    if not lines:
        return True
    words = re.findall(r"\b[A-Za-z0-9'-]+\b", c)
    num_words = len(words)

    # 1. Captions, legends, sources
    if re.match(r'^(?:fig|figure|chart|graph|source|table)\s*[:\.\d]', c_lower):
        return True
    if any(h in c_lower for h in ['poten & partners', 'www.poten.com', 'tankerresearch@', 'research@poten.com', 'eia/poten', '/eia']):
        if num_words <= 8:
            return True

    # 2. Currency ticks e.g. $450, $0, -$6, $180, etc.
    if all(re.match(r'^[-\$‐–—]?\s*\$?\s*\d+(?:\.\d+)?%?$', l) for l in lines):
        return True

    # 3. Date ticks e.g. Feb-07, Jan-85, 2004, Aug-06, etc.
    date_tick_pat = re.compile(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-‐–—\s\'/]*\d{2,4}$', re.I)
    if all(date_tick_pat.match(l) or l.isdigit() for l in lines):
        return True

    # 4. Multi-tick string on a single line (e.g. "$0 $2 $4 $6 $8 $10 $12 $14" or "Feb-07 Feb-06 Feb-08")
    tokens = c.split()
    if len(tokens) >= 2 and all(
        re.match(r'^[-\$‐–—]?\s*\$?\s*\d+(?:\.\d+)?%?$', t) or
        date_tick_pat.match(t) or
        t.lower() in ['ws', 'rate', 'rates', '$/ldt', '$/bbl', 'kbd', '000', 'tons', 'bpd', 'rebar', '$/ton']
        for t in tokens
    ):
        return True

    # 5. Chart axis labels / legends (e.g. "$/Ton Rebar $/Ldt", "$/Ldt WS Rate", "000 Tons")
    chart_units = {
        '$/ton', 'rebar', '$/ldt', 'ws', 'rate', 'rates', '000', 'tons', '$/bbl',
        'kbd', 'bpd', 'mm', 'bbls', 'blls', 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
        'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    }
    if num_words <= 6 and set(w.lower() for w in words).issubset(chart_units):
        return True

    return False

# Test on 20040305 blocks
pdf_path = Path("corpus/04-poten/pdfs/2004/Tanker_Opinion_20040305.pdf")
doc = pymupdf.open(pdf_path)

print("--- TESTING FIXED EXTRACTION ON 20040305 ---")
for pno, page in enumerate(doc):
    blocks = page.get_text("blocks")
    for b in blocks:
        txt = b[4].strip()
        if not txt: continue
        chunks = re.split(r'\n\s*\n', txt)
        for ch in chunks:
            ch_s = ch.strip()
            if not ch_s: continue
            if is_chart_chunk_fixed(ch_s, pno):
                print(f"P{pno+1} [FILTERED CHART NOISE]: {repr(ch_s[:60])}")
            else:
                if len(ch_s) < 80:
                    print(f"P{pno+1} [KEPT PROSE/HEADING]: {repr(ch_s)}")

doc.close()
