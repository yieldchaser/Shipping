#!/usr/bin/env python3
"""
scripts/append_book9_index.py
Recovers the complete 172-page Index (PDF pages 976-1148) for Book 9:
The Sea and Civilization: A Maritime History of the World by Lincoln Paine.
Eliminates dangling ebook links and ensures 100% byte parity.
"""
import sys
import re
from pathlib import Path
import pymupdf

CORPUS_PDF = Path("corpus/books/sea_and_civilization_paine.pdf")
TARGET_MD = Path("corpus/books/sea_and_civilization_paine.md")
KNOWLEDGE_MD = Path("knowledge/docs/books/sea_and_civilization_paine.md")

def clean_inline_text(text: str) -> str:
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    text = text.replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    return text

def extract_index_from_pdf():
    doc = pymupdf.open(CORPUS_PDF)
    print(f"Extracting index from pages 976 to {len(doc)}...")
    index_lines = []
    
    # PDF pages 976 to len(doc) (0-indexed: 975 to len(doc))
    for p_num in range(975, len(doc)):
        page = doc[p_num]
        p_text = page.get_text()
        lines = p_text.splitlines()
        for l in lines:
            s = l.strip()
            if not s:
                continue
            if s.isdigit():
                continue
            if s == "Index":
                continue
            if s == "Click here to return to the text.":
                continue
            s_clean = clean_inline_text(s)
            index_lines.append(s_clean)
            
    doc.close()
    return index_lines

def main():
    if not TARGET_MD.exists():
        print(f"Error: {TARGET_MD} not found")
        sys.exit(1)
        
    raw_md = TARGET_MD.read_text(encoding='utf-8')
    
    # Strip trailing "Click here to return to the text." artifacts if any
    clean_md = re.sub(r'(\n\s*Click here to return to the text\.\s*)+', '\n', raw_md)
    clean_md = clean_md.rstrip() + "\n\n"
    
    # Check if actual index entries already present
    if "Abadan, 10.1" in clean_md:
        print("Index already present in markdown file.")
    else:
        index_lines = extract_index_from_pdf()
        print(f"Extracted {len(index_lines)} index lines.")
        
        index_block = [
            "---\n",
            "# Index\n\n",
            "*Page numbers in italics refer to illustration captions.*\n\n"
        ]
        
        # Format index lines into clean markdown list
        for l in index_lines:
            if l.startswith("*Page numbers"):
                continue
            # Single letter headings like A, B, C...
            if re.match(r'^[A-Z]$', l):
                index_block.append(f"\n## {l}\n\n")
            else:
                index_block.append(f"{l}  \n")
                
        index_str = "".join(index_block)
        clean_md += index_str
        
    print(f"Writing updated markdown to {TARGET_MD} ({len(clean_md)} chars)...")
    TARGET_MD.write_text(clean_md, encoding='utf-8')
    
    print(f"Writing to {KNOWLEDGE_MD}...")
    KNOWLEDGE_MD.write_text(clean_md, encoding='utf-8')
    
    print("Done. 100% byte parity enforced.")

if __name__ == '__main__':
    main()
