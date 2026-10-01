#!/usr/bin/env python3
"""
scripts/tools/normalize_markdown_corpus.py
==========================================
Universal Markdown Corpus Normalizer:
1. Strips phantom empty headers ('## ', '## **') across Seabrokers and all publishers.
2. Normalizes deformed multi-hash headers in Star Asia ('Anchorage & Beaching Position').
3. Converts raw HTML <table> blocks into publication-grade GitHub Flavored Markdown (GFM) pipe tables (Banchero Costa, Intermodal, Hellenic).
4. Corrects spaced hashes ('# # ') into standard hierarchy ('## ').
5. Cleans ambiguous '# of' shorthand in headings to 'Number of'.
6. Collapses excessive trailing empty lines.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md"


def html_table_to_gfm(html: str) -> str:
    """Converts a raw HTML <table> block into a GFM pipe table."""
    rows = re.findall(r'<tr.*?>\s*(.*?)\s*</tr>', html, flags=re.DOTALL)
    if not rows:
        return ''
    md_rows = []
    title = ''
    for r in rows:
        title_m = re.search(r'<th[^>]*colspan[^>]*>(.*?)</th>', r, flags=re.DOTALL)
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            continue
        cells = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', r, flags=re.DOTALL)
        if cells:
            clean_cells = [re.sub(r'<[^>]+>', ' ', c).strip().replace('|', '/') for c in cells]
            clean_cells = [' '.join(c.split()) for c in clean_cells]
            # Replace corrupt encoding artifacts
            clean_cells = [c.replace('%', '+/-%').replace('', '') for c in clean_cells]
            md_rows.append(clean_cells)
    if not md_rows:
        return ''
    header = md_rows[0]
    data = md_rows[1:]
    res = []
    if title:
        res.append(f'### {title}\n')
    res.append('| ' + ' | '.join(header) + ' |')
    res.append('| ' + ' | '.join([':---'] * len(header)) + ' |')
    for d in data:
        while len(d) < len(header):
            d.append('')
        res.append('| ' + ' | '.join(d[:len(header)]) + ' |')
    return '\n' + '\n'.join(res) + '\n\n'


def normalize_content(pub: str, text: str) -> str:
    original = text

    # 1. Convert raw HTML <table> blocks to GFM tables
    if '<table' in text.lower():
        text = re.sub(r'<table.*?>.*?</table>', lambda m: html_table_to_gfm(m.group(0)), text, flags=re.DOTALL)

    # 2. Fix spaced hashes: '# # ' -> '## ', '# ##' -> '## '
    text = re.sub(r'(?m)^[ \t]*#\s+#\s+(.*)$', r'## \1', text)
    text = re.sub(r'(?m)^[ \t]*#\s+##\s+(.*)$', r'## \1', text)

    # 3. Strip phantom empty headers ('## ', '## **', '### **')
    text = re.sub(r'(?m)^[ \t]*#{1,6}\s*(?:\*{1,2})?\s*$', '', text)

    # 4. Normalize Star Asia deformed multi-hash Anchorage & Beaching headers
    if pub == "star_asia" or "star_asia" in pub:
        text = re.sub(r'(?m)^[ \t]*[#\s\*]*\b(Anchorage & Beaching Position.*?)(?:\*{1,2})?\s*$', r'### \1', text)

    # 5. Normalize '# of' shorthand in headers to 'Number of'
    text = re.sub(r'(?m)^([ \t]*#{1,6}\s+)#\s+(of\s+[A-Za-z]+)', r'\1Number \2', text)

    # 6. Normalize double divider lines and blank line runs
    text = re.sub(r'(?m)^---[ \t]*\n(?:---[ \t]*\n)+', '---\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip() + '\n'


def main():
    print("================================================================================")
    print("STARTING CORPUS-WIDE MARKDOWN NORMALIZATION SWEEP")
    print("================================================================================")

    stats = {}
    total_scanned = 0
    total_modified = 0

    for pub_dir in sorted(MD_ROOT.iterdir()):
        if not pub_dir.is_dir():
            continue
        pub_name = pub_dir.name
        pub_files = list(pub_dir.rglob("*.md"))
        modified_in_pub = 0

        for md_file in pub_files:
            total_scanned += 1
            try:
                content = md_file.read_text(encoding="utf-8")
                normalized = normalize_content(pub_name, content)
                if normalized != content:
                    md_file.write_text(normalized, encoding="utf-8")
                    modified_in_pub += 1
                    total_modified += 1
            except Exception as e:
                print(f"[ERROR] Failed {md_file.name}: {e}")

        stats[pub_name] = {"scanned": len(pub_files), "modified": modified_in_pub}
        if modified_in_pub > 0:
            print(f"[{pub_name:<20}] Scanned: {len(pub_files):<5} | Normalized: {modified_in_pub}")

    print("================================================================================")
    print(f"NORMALIZATION COMPLETE: {total_modified} / {total_scanned} files updated across corpus.")
    print("================================================================================")


if __name__ == "__main__":
    main()
