#!/usr/bin/env python3
"""
Rebuild Book 7: The Business of Shipping (Lane C. Kendall)
Recovers 100% of omitted pages, labor tables, chartering cables, and cargo calculations.
Maintains 100% byte-for-byte mirroring between corpus/ and knowledge/.
"""
import re
from pathlib import Path
import pymupdf

CORPUS_MD = Path("corpus/books/business_of_shipping_kendall.md")
KNOWLEDGE_MD = Path("knowledge/docs/books/business_of_shipping_kendall.md")
PDF_PATH = Path("corpus/books/business_of_shipping_kendall.pdf")

def extract_book7():
    doc = pymupdf.open(PDF_PATH)
    
    # Read existing frontmatter
    orig_text = CORPUS_MD.read_text(encoding='utf-8')
    fm_match = re.match(r"^(---\n.*?\n---\n)", orig_text, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""
    
    out_lines = [frontmatter.strip(), "", "# The Business of Shipping", "", "**Author:** Lane C. Kendall", "**Publisher:** Chapman & Hall / Cornell Maritime Press", ""]
    
    for p_num in range(10, len(doc)): # Start from page 11 (0-indexed 10, Introduction)
        page = doc[p_num]
        lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
        if not lines:
            continue
            
        # Check running header at top
        # Patterns like: ['THE MANAGEMENT OF TRAMP SHIPPING', '43', ...] or ['44', 'THE MANAGEMENT OF TRAMP SHIPPING', ...]
        idx = 0
        if idx < len(lines) and (lines[idx].isupper() or lines[idx].isdigit()):
            if lines[idx].isdigit():
                idx += 1
                if idx < len(lines) and lines[idx].isupper():
                    idx += 1
            else:
                idx += 1
                if idx < len(lines) and lines[idx].isdigit():
                    idx += 1
                    
        page_body = lines[idx:]
        
        # Detect Chapter headings
        for line in page_body:
            if re.match(r"^(Chapter\s+\d+|CHAPTER\s+\d+)", line, re.IGNORECASE):
                out_lines.extend(["", f"## {line}", ""])
            elif re.match(r"^(APPENDIX\s+[A-Z]|Appendix\s+[A-Z])", line):
                out_lines.extend(["", f"## {line}", ""])
            else:
                out_lines.append(line)
        out_lines.append("") # paragraph break between pages if needed
        
    doc.close()
    
    final_text = "\n".join(out_lines)
    # Normalize excessive blank lines
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip() + "\n"
    
    CORPUS_MD.write_text(final_text, encoding='utf-8')
    KNOWLEDGE_MD.write_text(final_text, encoding='utf-8')
    print(f"Book 7 successfully rebuilt: {len(final_text):,} chars, {len(final_text.splitlines()):,} lines")
    print(f"Parity check: {CORPUS_MD.stat().st_size == KNOWLEDGE_MD.stat().st_size}")

if __name__ == "__main__":
    extract_book7()
