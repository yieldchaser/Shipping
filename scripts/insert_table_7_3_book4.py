#!/usr/bin/env python3
"""
Insert Table 7.3 (Marine Money List of Public Shipping Companies 2005-2012)
into Book 4: Maritime Economics - A Macroeconomic Approach.
Maintains 100% byte-for-byte mirroring between corpus/ and knowledge/.
"""
import re
from pathlib import Path
import pymupdf

PDF_PATH = Path("corpus/books/maritime_economics_macro_karakitsos_varnavides.pdf")
CORPUS_MD = Path("corpus/books/maritime_economics_macro_karakitsos_varnavides.md")
KNOWLEDGE_MD = Path("knowledge/docs/books/maritime_economics_macro_karakitsos_varnavides.md")

def parse_table_7_3():
    doc = pymupdf.open(PDF_PATH)
    rows = []
    for p in range(270, 276):
        lines = [l.strip() for l in doc[p].get_text().splitlines() if l.strip()]
        clean = []
        for l in lines:
            if 'KARAKITSOS AND VARNAVIDES' in l or 'THE MARKET STRUCTURE' in l or '(continued)' in l or 'Table 7.3' in l:
                continue
            if l in ['2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012']:
                continue
            clean.append(l)
        
        i = 0
        while i < len(clean):
            name = clean[i]
            vals = []
            j = i + 1
            while j < len(clean) and len(vals) < 8:
                val_str = clean[j]
                if re.match(r'^-?[\d\.]+$', val_str) or val_str.lower() == 'na':
                    vals.append(val_str)
                    j += 1
                else:
                    break
            if len(vals) == 8:
                rows.append((name, vals))
                i = j
            else:
                i += 1
    doc.close()
    return rows

def format_table_md(rows):
    lines = [
        "",
        "### Table 7.3 Marine Money List of Public Shipping Companies (Market Values, USD Millions, 2005–2012)",
        "",
        "| Company Name | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, vals in rows:
        formatted_vals = " | ".join(vals)
        lines.append(f"| {name} | {formatted_vals} |")
    lines.append("")
    return "\n".join(lines)

def main():
    rows = parse_table_7_3()
    table_md = format_table_md(rows)
    
    text = CORPUS_MD.read_text(encoding='utf-8')
    target = "Table 7.3 provided by Marine Money Magazine, lists nearly 150 public\nshipping companies which they track."
    
    if target not in text:
        # try without newline
        target = "Table 7.3 provided by Marine Money Magazine, lists nearly 150 public shipping companies which they track."
        
    if target not in text:
        # search regex
        m = re.search(r"Table 7\.3 provided by Marine Money Magazine.*?\.", text, re.DOTALL)
        if m:
            target = m.group(0)
            
    print(f"Target found: {target[:50]}...")
    
    # We insert the table after the discussion of Table 7.3
    insertion_anchor = "By 2012 many companies were trading\nat just 50 per cent of NAV."
    if insertion_anchor not in text:
        insertion_anchor = "By 2012 many companies were trading at just 50 per cent of NAV."
        
    if insertion_anchor in text:
        new_text = text.replace(insertion_anchor, insertion_anchor + "\n\n" + table_md)
    else:
        # insert after target
        new_text = text.replace(target, target + "\n\n" + table_md)
        
    CORPUS_MD.write_text(new_text, encoding='utf-8')
    KNOWLEDGE_MD.write_text(new_text, encoding='utf-8')
    print("Table 7.3 successfully inserted into Book 4!")
    print(f"Corpus size: {CORPUS_MD.stat().st_size:,} bytes")
    print(f"Knowledge size: {KNOWLEDGE_MD.stat().st_size:,} bytes")
    print(f"Parity: {CORPUS_MD.stat().st_size == KNOWLEDGE_MD.stat().st_size}")

if __name__ == "__main__":
    main()
