import pymupdf
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
pdf_path = ROOT / "corpus/01-brokers/agora/2026/agora_2026_W34_AGORA.-Week-35-2026.-Snapshot-of-Commercial-Indicators.pdf"
doc = pymupdf.open(pdf_path)


def format_notes_page(page):
    text = page.get_text("text")
    lines = ["### Contract Specifications & Commodity Notes\n"]
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or "AGORA" in ln or "Office:" in ln or "Disclaimer:" in ln or "Notes" in ln or "www." in ln:
            continue
        m = re.match(r"^(\d+\.\s*)([^-–:]+)([-–:].*)$", ln)
        if m:
            lines.append(f"{m.group(1)}**{m.group(2).strip()}** - {m.group(3).lstrip('-–: ')}")
        elif re.match(r"^\d+\.", ln):
            lines.append(ln)
    lines.append("")
    return "\n".join(lines)


print(format_notes_page(doc[3]))
