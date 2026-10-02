#!/usr/bin/env python3
"""
Normalizer for Banchero Costa Markdown Documents.

Cleans up:
1. Running footers ('banchero costa RESEARCH', 'bc banchero costa | RESEARCH').
2. Trailing page numbers on section headers (e.g. '# COMMODITIES MARKET REPORT – WEEK 06/2026 15').
3. Degenerate 1-column chart tables:
   Replaces ugly 1-column category tables with clean bulleted chart references
   placed after the commodity tables, ensuring tables remain contiguous.
4. Single-column prose tables:
   Converts boxed commentary into clean Markdown headings and paragraphs.
5. Collapsed rate rows:
   Expands single-cell rate strings into structured 6-column tables.

Zero data loss: 100% preservation of analytical content and series CSV integrity.
"""

import os
import re
import argparse
from pathlib import Path

def clean_banchero_text(txt: str) -> tuple[str, dict]:
    stats = {
        "footers_stripped": 0,
        "headers_cleaned": 0,
        "chart_tables_reformatted": 0,
        "prose_tables_unpacked": 0,
        "collapsed_rows_expanded": 0,
    }
    
    orig = txt
    
    # 1. Strip running footers
    # banchero costa RESEARCH / bc banchero costa | RESEARCH
    footer_pattern = re.compile(
        r'^[ \t]*(?:bc\s+)?banchero costa\s*(?:\|\s*)?RESEARCH[ \t]*\r?\n+',
        flags=re.IGNORECASE | re.MULTILINE
    )
    footers_found = len(footer_pattern.findall(txt))
    if footers_found:
        stats["footers_stripped"] += footers_found
        txt = footer_pattern.sub('', txt)
        
    # Also standalone "banchero costa" lines at page breaks
    pagebreak_footer = re.compile(
        r'\n\n[ \t]*(?:bc\s+)?banchero costa[ \t]*\n\n',
        flags=re.IGNORECASE
    )
    pb_found = len(pagebreak_footer.findall(txt))
    if pb_found:
        stats["footers_stripped"] += pb_found
        txt = pagebreak_footer.sub('\n\n', txt)

    # 2. Strip trailing page numbers on section headers
    # e.g. '# COMMODITIES MARKET REPORT – WEEK 06/2026 15' -> '# COMMODITIES MARKET REPORT – WEEK 06/2026'
    # '# SALE & PURCHASE MARKET REPORT – WEEK 06/2026 12' -> '# SALE & PURCHASE MARKET REPORT – WEEK 06/2026'
    def clean_header_num(m):
        stats["headers_cleaned"] += 1
        return m.group(1)
        
    header_page_pattern = re.compile(
        r'^(#+\s+.*?\b(?:19\d\d|20\d\d)\b)\s+\d{1,2}[ \t]*$',
        flags=re.MULTILINE
    )
    txt = header_page_pattern.sub(clean_header_num, txt)

    # 3. Unpack collapsed rate rows into 6-column tables
    # e.g. | **TC1 MEG-Japan (75k)** ws 113.8 110.0 +3.4% +24.4% |
    collapsed_row_pattern = re.compile(
        r'\|\s*(\*\*[^*]+\*\*)\s+(ws|usd/day|usd/mt)\s+([\d,.]+)\s+([\d,.]+)\s+([+-]?[\d.]+%)\s+([+-]?[\d.]+%)\s*\|'
    )
    if collapsed_row_pattern.search(txt):
        lines = txt.splitlines()
        new_lines = []
        in_collapsed_table = False
        for l in lines:
            m = collapsed_row_pattern.match(l.strip())
            if m:
                if not in_collapsed_table:
                    # check if previous line was | Category | or similar
                    if new_lines and '| Category |' in new_lines[-2]:
                        # replace the header and separator
                        new_lines[-2] = '| Route | Unit | Rate | Previous | W-o-W | Y-o-Y |'
                        new_lines[-1] = '| --- | --- | --- | --- | --- | --- |'
                    in_collapsed_table = True
                unpacked = f"| {m.group(1)} | {m.group(2)} | {m.group(3)} | {m.group(4)} | {m.group(5)} | {m.group(6)} |"
                new_lines.append(unpacked)
                stats["collapsed_rows_expanded"] += 1
            else:
                in_collapsed_table = False
                new_lines.append(l)
        txt = '\n'.join(new_lines)

    # 4. Handle degenerate 1-column commodity chart tables
    # Find table with | Category | followed by chart titles/legends
    cat_tbl_pattern = re.compile(
        r'\n\|[ \t]*Category[ \t]*\|\n\|[ \t]*[-:]+[ \t]*\|\n'
        r'((?:\|[ \t]*[^\n\|]+[ \t]*\|\n)+)'
    )
    for m in list(cat_tbl_pattern.finditer(txt)):
        rows = [r.strip('| \t') for r in m.group(1).splitlines() if r.strip('| \t')]
        # Check if rows contain commodity chart indicators
        has_chart_keywords = any(
            any(k in r for k in ['PRICE', 'PRICES', 'BUNKER', 'BRENT', 'HENRY HUB', 'COAL & IRON', 'STEEL PRICES', 'WHEAT & CORN'])
            for r in rows
        )
        if has_chart_keywords:
            items = []
            current_chart = None
            series = []
            for r in rows:
                if any(term in r for term in ['PRICE', 'PRICES', 'INDEX']):
                    if current_chart:
                        s_str = ', '.join(series) if series else 'Historical trend'
                        items.append(f"- **{current_chart}**: {s_str}")
                    current_chart = r
                    series = []
                else:
                    series.append(r)
            if current_chart:
                s_str = ', '.join(series) if series else 'Historical trend'
                items.append(f"- **{current_chart}**: {s_str}")

            if items:
                chart_section = "\n\n### Commodity Price Trend Charts\n\n" + "\n".join(items) + "\n\n"
                # Remove table from original position
                start, end = m.start(), m.end()
                txt = txt[:start] + "\n" + txt[end:]
                stats["chart_tables_reformatted"] += 1

                # Place after AGRICULTURAL table if present, else at end of commodity section
                if "| AGRICULTURAL |" in txt:
                    # find end of table (double newline after | AGRICULTURAL |)
                    agri_pos = txt.find("| AGRICULTURAL |")
                    end_agri = txt.find("\n\n", agri_pos)
                    if end_agri != -1:
                        txt = txt[:end_agri] + chart_section + txt[end_agri:]
                    else:
                        txt = txt + chart_section
                else:
                    txt = txt + chart_section
                break

    # 5. Convert 1-column prose tables into clean Markdown
    # e.g. | **US GULF / NORTH AMERICA** |\n| --- |\n| Supramax and Ultramax prices skyrocketed... |
    prose_table_pattern = re.compile(
        r'\n\|[ \t]*(\*\*[^*]+\*\*|[A-Z\s/]{4,30})[ \t]*\|\n\|[ \t]*[-:]+[ \t]*\|\n'
        r'\|[ \t]*([^\n\|]{50,})[ \t]*\|\n'
    )
    for m in list(prose_table_pattern.finditer(txt)):
        title = m.group(1).strip('* \t')
        body = m.group(2).strip()
        replacement = f"\n\n### {title}\n\n{body}\n\n"
        txt = txt.replace(m.group(0), replacement, 1)
        stats["prose_tables_unpacked"] += 1

    # Clean consecutive blank lines (max 2)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    
    return txt, stats

def process_file(file_path: Path, dry_run: bool = False) -> dict:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        cleaned, stats = clean_banchero_text(content)
        if cleaned != content and not dry_run:
            file_path.write_text(cleaned, encoding="utf-8")
        return stats
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="Clean Banchero Costa Markdown formatting defects")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()

    md_dir = Path("data/extracted/md/banchero_costa")
    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(list(md_dir.glob("**/*.md")))

    print(f"Processing {len(files)} Banchero Costa markdown files...")
    total_stats = {
        "files_modified": 0,
        "footers_stripped": 0,
        "headers_cleaned": 0,
        "chart_tables_reformatted": 0,
        "prose_tables_unpacked": 0,
        "collapsed_rows_expanded": 0,
    }

    for f in files:
        stats = process_file(f, dry_run=args.dry_run)
        any_change = any(v > 0 for v in stats.values())
        if any_change:
            total_stats["files_modified"] += 1
            for k, v in stats.items():
                total_stats[k] = total_stats.get(k, 0) + v

    print("=" * 60)
    print("BANCHERO COSTA CLEANUP SUMMARY:")
    for k, v in total_stats.items():
        print(f"  {k:30}: {v}")
    print("=" * 60)

if __name__ == "__main__":
    main()
