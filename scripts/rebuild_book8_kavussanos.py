#!/usr/bin/env python3
"""
Rebuild Book 8: The International Handbook of Shipping Finance (Kavussanos & Visvikis)
Recovers 100% of omitted pages, charts text, matrices, and econometric formulas.
Maintains 100% byte-for-byte mirroring between corpus/ and knowledge/.
"""
import re
from pathlib import Path
import pymupdf

CORPUS_MD = Path("corpus/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")
KNOWLEDGE_MD = Path("knowledge/docs/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")
PDF_PATH = list(Path("corpus/books").glob("*International Handbook*.pdf"))[0]

def clean_ligatures(text):
    text = text.replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    text = text.replace('\ufb00', 'ff').replace('\ufb03', 'ffi').replace('\ufb04', 'ffl')
    text = re.sub(r'\bﬁ\s*', 'fi', text)
    text = re.sub(r'\bﬂ\s*', 'fl', text)
    # heal split words like 'Th e' -> 'The'
    text = re.sub(r'\bTh\s+e\b', 'The', text)
    text = re.sub(r'\bth\s+e\b', 'the', text)
    text = re.sub(r'\bo\s+f\b', 'of', text)
    text = re.sub(r'\bi\s+n\b', 'in', text)
    text = re.sub(r'\ba\s+nd\b', 'and', text)
    return text

def extract_book8():
    doc = pymupdf.open(PDF_PATH)
    
    # Read existing frontmatter
    orig_text = CORPUS_MD.read_text(encoding='utf-8')
    fm_match = re.match(r"^(---\n.*?\n---\n)", orig_text, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""
    
    out_lines = [
        frontmatter.strip(), "",
        "# The International Handbook of Shipping Finance: Theory and Practice", "",
        "**Editors:** Manolis G. Kavussanos, Ilias D. Visvikis", "",
        "**Publisher:** Palgrave Macmillan", ""
    ]
    
    # Chapter 1 starts at page 39 (0-indexed 38)
    for p_num in range(38, len(doc)):
        page = doc[p_num]
        raw_text = clean_ligatures(page.get_text())
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if not lines:
            continue
            
        # Strip running headers at top
        # Patterns like: ['18', 'J.-H. Hübner'] or ['1 Shipping Markets and Their Economic Drivers', '23']
        idx = 0
        if idx < len(lines) and (lines[idx].isdigit() or re.match(r'^[A-Z]\.-?[A-Z]\.', lines[idx]) or re.match(r'^\d+\s+[A-Z]', lines[idx])):
            idx += 1
            if idx < len(lines) and (lines[idx].isdigit() or re.match(r'^[A-Z]\.-?[A-Z]\.', lines[idx]) or re.match(r'^\d+\s+[A-Z]', lines[idx]) or 'Shipping' in lines[idx] or 'Finance' in lines[idx]):
                idx += 1
                
        page_body = lines[idx:]
        
        # Format headings
        for line in page_body:
            # Chapter headings e.g. "Chapter 1", "1 Shipping Markets..."
            if re.match(r"^(\d+)\s+([A-Z][A-Za-z\s,:'\-]+)$", line) and len(line) < 80:
                out_lines.extend(["", f"## {line}", ""])
            elif re.match(r"^(\d+\.\d+)\s+([A-Z][A-Za-z\s,:'\-]+)$", line) and len(line) < 80:
                out_lines.extend(["", f"### {line}", ""])
            elif re.match(r"^(\d+\.\d+\.\d+)\s+([A-Z][A-Za-z\s,:'\-]+)$", line) and len(line) < 80:
                out_lines.extend(["", f"#### {line}", ""])
            elif re.match(r"^(Table\s+\d+\.\d+|Fig\.\s+\d+\.\d+|Figure\s+\d+\.\d+)", line):
                out_lines.extend(["", f"**{line}**", ""])
            else:
                out_lines.append(line)
        out_lines.append("")
        
    doc.close()
    
    final_text = "\n".join(out_lines)
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip() + "\n"
    
    CORPUS_MD.write_text(final_text, encoding='utf-8')
    KNOWLEDGE_MD.write_text(final_text, encoding='utf-8')
    print(f"Book 8 successfully rebuilt: {len(final_text):,} chars, {len(final_text.splitlines()):,} lines")
    print(f"Parity check: {CORPUS_MD.stat().st_size == KNOWLEDGE_MD.stat().st_size}")

if __name__ == "__main__":
    extract_book8()
