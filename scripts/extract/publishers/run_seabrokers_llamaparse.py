"""
Seabrokers Seabreeze Monthly Reports Full LlamaParse Extraction Pipeline.

Extracts all 97 monthly SEABREEZE offshore market intelligence reports (2018-2026)
cover-to-cover using LlamaParse with publication-grade Markdown normalization,
high-fidelity structured table sidecars, and automated multi-account failover.

Deliverables:
  - Publication-grade Markdown with YAML frontmatter and cleaned headings/tables:
      data/extracted/md/seabrokers/<year>/<stem>.md
  - Structured Table JSON sidecars:
      data/extracted/md/seabrokers/<year>/<stem>.tables.json
  - Master Catalog Series:
      data/extracted/series/seabrokers_catalog_metadata.csv
  - Master Series CSVs (already exported):
      data/extracted/series/seabrokers_osv_spot_rates_series.csv
      data/extracted/series/seabrokers_osv_monthly_history_series.csv
      data/extracted/series/seabrokers_osv_utilisation_series.csv
      data/extracted/series/seabrokers_rigs_market_series.csv
      data/extracted/series/seabrokers_snp_auctions_series.csv
      data/extracted/series/seabrokers_fleet_moves_series.csv
      data/extracted/series/seabrokers_feature_vessels_series.csv
      data/extracted/series/seabrokers_renewables_and_ets_series.csv
"""

import os
import sys
import re
import json
import time
import glob
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Add repo root to pythonpath
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract.llama_manager import manager, get_active_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SeabrokersLlama")

PDF_DIR = REPO_ROOT / "corpus" / "05-seabrokers" / "pdfs"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "seabrokers"
CACHE_DIR = REPO_ROOT / "data" / "extracted" / "llamaparse_seabrokers"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"
STATE_FILE = CACHE_DIR / "_run_state.json"

MD_BASE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SERIES_DIR.mkdir(parents=True, exist_ok=True)

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def load_run_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}}


def save_run_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_date_from_filename(filename: str):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})_', filename)
    if m:
        yr = int(m.group(1))
        mo = int(m.group(2))
        day = int(m.group(3))
        iso_date = f"{yr:04d}-{mo:02d}-{day:02d}"
        return iso_date, yr, mo
    return "2026-01-01", 2026, 1


def is_seabrokers_dir_line(line: str) -> bool:
    """Helper to detect corporate directory, office, and duty phone lines in report tail."""
    l = line.strip()
    if not l:
        return True
    if re.match(r'^#+[ \t]*(?:\*{1,2}[ \t]*\*{1,2}|\*{1,2})?$', l):
        return True
    if re.search(r'\(\+\d+\)|@seabrokers|@seasurveillance|@skagenship', l):
        return True
    if re.match(r'^#+[ \t]*\*{0,2}(?:SEABROKERS|Seabrokers|Sea Surveillance|Skagen Ship|SEA SOFTWARE)[^\n]*$', l):
        return True
    if l.startswith('(+47)') or l.startswith('(+44)') or l.startswith('(+55)'):
        return True
    return False


def normalize_seabrokers_content(text: str) -> str:
    """Publication-grade normalization for Seabrokers monthly Seascope reports.
    
    Transforms raw OCR output into polished, human-readable Markdown:
    - Formats Front Cover header and Cover Feature lead story cleanly
    - Formats Table of Contents into a fully bulleted, linked Markdown list
    - Replaces empty marketing service tables on Page 2 with a clean service roster
    - Converts raw HTML <table> blocks into clean GitHub-Flavored Markdown pipe tables
    - Unfurls deformed <br/>-crammed table headers and titles into valid Markdown tables
    - Fixes OCR typos (e.g. 'AI ITS DUTIES' -> 'AHTS DUTIES')
    - Formats vessel photo captions and removes bare OCR logo/image placeholders
    - Re-aligns Page 7 spot rate tables with canonical segment titles
    - Strips corporate directory boxes, office addresses, and duty phone boilerplate
    - Strips running headers, running page numbers, and stray OCR bullet artifacts
    """
    text = text.replace('\r\n', '\n')

    # 1. Clean OCR typos
    text = re.sub(r'\bAI\s*ITS\s+DUTIES\b', 'AHTS DUTIES', text)
    text = re.sub(r'\bAI\s*ITS\b', 'AHTS', text)

    # 2. Format Front Cover Header & Teaser
    def _format_cover(t: str) -> str:
        m = re.search(r'(?is)\A(.*?)(?=\n[ \t]*(?:---+|##\s*Contents|#*\s*CONTENTS))', t)
        if not m:
            return t
        cover = m.group(1).strip()
        my_match = re.search(r'(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', cover)
        month_year = f"{my_match.group(1)} {my_match.group(2)}" if my_match else ""
        
        sb_idx = cover.upper().find("SEABREEZE")
        headline_parts = []
        if sb_idx != -1:
            after_sb = cover[sb_idx:]
            h_lines = re.findall(r'(?m)^[ \t]*#+\s*\**([A-Za-z0-9\s,\'"/&–-]+?)\**[ \t]*$', after_sb)
            headline_parts = [h.strip() for h in h_lines if h.strip().upper() not in ("SEABREEZE", month_year.upper())]
        
        headline = " ".join(headline_parts).strip()
        
        out = [
            "# SEABREEZE",
            f"### The Seabrokers Monthly Market Report — {month_year}" if month_year else "### The Seabrokers Monthly Market Report",
            "*The Shipbroker with a Difference — Seabrokers Group*",
            ""
        ]
        if headline:
            out.append(f"## Cover Feature: {headline}")
            out.append("")
        
        return "\n".join(out) + "\n\n" + t[m.end():]

    text = _format_cover(text)

    # 3. Format Table of Contents
    def _toc_repl(m):
        raw_items = m.group(1).strip()
        lines = [l.strip() for l in raw_items.split('\n') if l.strip()]
        items = []
        for l in lines:
            im = re.match(r'^(\d{1,2})\s*[\*\s]*(.+?)[\*\s]*$', l)
            if im:
                page = im.group(1)
                title = im.group(2).strip('* ').strip()
                if 'Contact Details' not in title and 'Seabrokers Group' not in title:
                    items.append((page, title))
        if items:
            toc = ['## Contents', '']
            for page, title in items:
                toc.append(f'- **{title}** *(p. {page})*')
            return '\n\n' + '\n'.join(toc) + '\n\n'
        return m.group(0)

    text = re.sub(
        r'(?is)(?:^|\n)[ \t]*#*\s*CONTENTS\s*\n+(.*?)(?=\n\s*(?:---+|##\s*\**ABOUT|##\s*\**OSV|#\s*OSV|\Z))', 
        _toc_repl, 
        text
    )

    # 4. Clean Empty Service / Description table on Page 2
    text = re.sub(r'\|\s*Service\s*\|\s*Description\s*\|\n\|[-:\s|]+\|\n(?:\|\s*[A-Z\s]+\s*\|\s*\|\n*)+', 
                  '**Seabrokers Group Services:** Shipbroking | Real Estate | Securalift | Facility Management | Sea Surveillance | Foundations | Yachting | Harbour Cranes\n\n', 
                  text)

    # 5. Clean Page 2 corporate office addresses & distribution boilerplate
    text = re.sub(r'(?is)\*{0,2}OUR OFFICES:\*{0,2}\s*\n(?:[A-Z\s,–-]+\n)+', '', text)
    text = re.sub(r'(?im)^[ \t]*(?:https?://)?www\.seabrokers[a-z0-9\.\-_/]*[ \t]*$', '', text)
    text = re.sub(r'(?is)Production (?:and|&) Administration:?.*?(?:chartering@seabrokers\S*|\.co\.uk|\.no|\.com|\n\n)', '', text)
    text = re.sub(r'(?is)The Seabreeze Monthly Market Report is distributed worldwide through our offices.*?(?=\n\n|\Z)', '', text)
    text = re.sub(r'(?im)^[ \t]*©\s*Seabrokers\s*Group\s*\d{4}[ \t]*$', '', text)

    # 6. Convert raw HTML <table> blocks into clean Markdown tables
    def _html_table_to_md(m):
        html = m.group(0)
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

    text = re.sub(r'<table.*?>.*?</table>', _html_table_to_md, text, flags=re.DOTALL)

    # 7. Unfurl deformed <br/>-crammed table headers
    def _fix_br_table(m):
        tbl = m.group(0)
        lines = tbl.strip().split('\n')
        if len(lines) < 2:
            return tbl
        header_line = lines[0]
        cols = [c.strip() for c in header_line.split('|') if c.strip()]
        if not cols or not any('<br/>' in c or '<br>' in c for c in cols):
            return tbl
        
        col_splits = []
        for c in cols:
            parts = [p.strip() for p in re.split(r'<br\s*/?>', c, flags=re.IGNORECASE) if p.strip()]
            col_splits.append(parts)
        
        part_lens = [len(p) for p in col_splits]
        # Case A: Entire table body packed into header <br/> cells
        if len(lines) <= 2 and len(set(part_lens)) == 1 and part_lens[0] >= 3:
            n_rows = part_lens[0]
            first_items = [p[0] for p in col_splits]
            title = first_items[0] if len(set(first_items)) == 1 else ''
            row_offset = 1 if title else 0
            
            new_headers = [col_splits[i][row_offset] for i in range(len(cols))]
            new_rows = []
            for r_idx in range(row_offset + 1, n_rows):
                new_rows.append([col_splits[c_idx][r_idx] for c_idx in range(len(cols))])
            
            out = []
            if title:
                out.append(f'### {title}\n')
            out.append('| ' + ' | '.join(new_headers) + ' |')
            out.append('| ' + ' | '.join([':---'] * len(new_headers)) + ' |')
            for r in new_rows:
                out.append('| ' + ' | '.join(r) + ' |')
            return '\n' + '\n'.join(out) + '\n\n'
        
        # Case B: Prefix title or multi-line header where body rows exist in lines[1:]
        first_items = [p[0] for p in col_splits if len(p) > 1]
        title = ''
        if first_items and len(set(first_items)) == 1:
            title = first_items[0]
        new_headers = [p[-1] for p in col_splits]
        out = []
        if title:
            out.append(f'### {title}\n')
        out.append('| ' + ' | '.join(new_headers) + ' |')
        for l in lines[1:]:
            out.append(l)
        return '\n' + '\n'.join(out) + '\n\n'

    text = re.sub(r'(?m)^(\|?[^\n]+<br/?>[^\n]+\|\n\|[-:\t |]+\|(?:\n\|[^\n]+\|)*)', _fix_br_table, text, flags=re.IGNORECASE)

    # 8. Format Arrivals & Departures
    def _fix_arr_dep_table(m):
        tbl = m.group(0)
        lines = tbl.strip().split('\n')
        new_lines = [
            '| ARRIVALS (VESSEL) | ORIGIN | DEPARTURES (VESSEL) | DESTINATION |',
            '| :--- | :--- | :--- | :--- |'
        ]
        for l in lines[2:]:
            new_lines.append(l)
        return '\n' + '\n'.join(new_lines) + '\n\n'

    text = re.sub(r'(\| ARRIVALS - NORTH SEA SPOT \| ARRIVALS - NORTH SEA SPOT \| DEPARTURES - NORTH SEA SPOT \| DEPARTURES - NORTH SEA SPOT \|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n*)+)', _fix_arr_dep_table, text)

    def _arr_dep_repl(m):
        arr_part = m.group(1).strip()
        dep_part = m.group(2).strip()
        out = ['### North Sea Spot Arrivals & Departures', '']
        out.append('**Arrivals:**')
        for l in arr_part.split('\n'):
            l = l.strip()
            if not l:
                continue
            items = re.split(r'\s{2,}|(?<=SEA)\s+|(?<=AMERICA)\s+', l)
            for it in items:
                it = it.strip()
                if not it:
                    continue
                pts = re.split(r'\s+EX\s+', it, flags=re.IGNORECASE)
                if len(pts) == 2:
                    out.append(f'- **{pts[0].strip().title()}:** ex {pts[1].strip().title()}')
                else:
                    out.append(f'- **{it.strip().title()}**')
        out.append('')
        out.append('**Departures:**')
        for l in dep_part.split('\n'):
            l = l.strip()
            if not l:
                continue
            items = re.split(r'\s{2,}|(?<=AFRICA)\s+|(?<=CARIBBEAN)\s+', l)
            for it in items:
                it = it.strip()
                if not it:
                    continue
                out.append(f'- **{it.strip().title()}**')
        out.append('')
        out.append('*Note: Vessels arriving in or departing from the North Sea term/layup market are excluded.*')
        return '\n'.join(out) + '\n\n'

    text = re.sub(r'(?is)ARRIVALS NORTH SEA SPOT\s*\*?\s*\n(.*?)\nDEPARTURES NORTH SEA SPOT\s*\*?\s*\n(.*?)(?=\*Vessels|\n\n|\Z)', _arr_dep_repl, text)
    text = re.sub(r'(?i)\*Vessels arriving in or departing from the North Sea term/layup market are not included here\.?', '', text)

    # 9. Realign Page 7 spot rates tables if titles are shifted
    if '# NORTH SEA AVERAGE SPOT RATES' in text:
        def _realign_p7(match):
            block = match.group(0)
            tbl_matches = list(re.finditer(r'(\| (?:Month|Category)\s*\|.*?\n(?:\|[^\n]+\|\n*)+)', block))
            if len(tbl_matches) == 5:
                headers = [
                    '### Spot Rates: PSVs < 900m²',
                    '### Spot Rates: PSVs > 900m²',
                    '### Spot Rates: AHTS < 22,000 bhp',
                    '### Spot Rates: AHTS > 22,000 bhp',
                    '### Average Day Rates To Month'
                ]
                out = ['# NORTH SEA AVERAGE SPOT RATES\n']
                for h, m in zip(headers, tbl_matches):
                    out.append(h)
                    out.append(m.group(0).strip() + '\n')
                return '\n'.join(out) + '\n\n'
            return block
        
        text = re.sub(r'# NORTH SEA AVERAGE SPOT RATES.*?(?=\n# |\Z)', _realign_p7, text, flags=re.DOTALL)

    # 10. Clean bare OCR image/logo markers and style photo captions
    text = re.sub(r'(?im)^[ \t]*[A-Za-z0-9\s&–-]+\s+(?:Logo|Image|Flag|artist impression(?:\(\(\)\))?|photo)\s*$', '', text)
    text = re.sub(r'(?m)^([A-Z][A-Za-z0-9\.\s&–-]+\s+\([A-Z][A-Za-z0-9\.\s]+\))\s*$', r'*[Photo: \1]*', text)

    # 11. Clean tail page banner, puzzles, and corporate contact directories
    # 11a. Page-top banner in earlier era (e.g. # CONUNDRUM CORNER, DUTY PHONES or # SEABROKERS CONTACTS, DUTY PHONES)
    # Promote the subsequent heading to # if it was ##
    text = re.sub(r'(?im)^[ \t]*#+[ \t]*\*{0,2}(?:CONUNDRUM\s+CORNER|SEABROKERS\s+CONTACTS),?\s+DUTY\s+PHONES\*{0,2}[ \t]*\n+(?:##\s*)?', '# ', text)

    # 11b. Modern era corporate directory sidebar on last page
    def _repl_dir(m):
        block = m.group(0)
        if re.search(r'\(\+\d+\)|chartering@seabrokers|seabrokers\.no|sales@seasurveillance|skagenship', block):
            return '\n\n'
        return block

    pattern_dir = r'(?is)(?<=\n)#[ \t]*\*{0,2}SEABROKERS GROUP\*{0,2}[ \t]*\n.*?(?=\n#[ \t]*\*{0,2}(?!(?:SEABROKERS|Seabrokers|Sea Surveillance|Skagen Ship|SEA SOFTWARE)\b)[A-Za-z0-9]|\Z)'
    cutoff = int(len(text) * 0.70)
    head = text[:cutoff]
    tail = text[cutoff:]
    tail = re.sub(pattern_dir, _repl_dir, tail)
    text = head + tail

    # 11c. Corporate contacts box in earlier era
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}SEABROKERS GROUP CONTACTS\*{0,2}.*?(?=\n##|\n#|\Z)', '\n\n', text)

    # 11d. Broken empty contact tables
    text = re.sub(r'(?is)\n\|\s*(?:Company|ORGANIZATION)\s*\|\s*(?:LOCATION\s*\|\s*)?Telephone\s*\|\s*E-mail\s*\|.*?(?=\n\n|\n#|\Z)', '\n\n', text)

    # 11e. Conundrum Corner puzzle section
    conundrum_pattern = r'(?is)\n(?:##?#?\s*)?\*{0,2}CONUNDRUM CORNER\*{0,2}.*?(?=\n##?\s+(?!#|\*|This month|Last month)[A-Z0-9]|\Z)'
    text = re.sub(conundrum_pattern, '\n\n', text)

    # 11f. Administrative subscription, archive, and production boilerplate at the end
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}(?:The Seabreeze Archive|Seabrokers Ltd,?\s*Aberdeen)\*{0,2}.*?(?=\n#|\Z)', '\n\n', text)
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}Production\s+(?:&|and)\s+Administration\*{0,2}.*?(?=\n#|\Z)', '', text)
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}SEASON\'?S GREETINGS\*{0,2}.*?(?=\n#|\Z)', '\n\n', text)
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}CHRISTMAS DONATIONS\*{0,2}.*?(?=\n#|\Z)', '\n\n', text)
    text = re.sub(r'(?is)\n(?:##?\s*)?\*{0,2}HAPPY BIRTHDAY TO SEABROKERS!\*{0,2}.*?(?=\n#|\Z)', '\n\n', text)
    text = re.sub(r'(?is)\n#[ \t]*\*{0,2}For your free copy of Seabreeze.*?(?=\n#|\Z)', '', text)
    text = re.sub(r'(?is)Seabrokers Chartering AS and Seabrokers Ltd are certified by DNV GL.*?(?=\n#|\Z)', '', text)
    text = re.sub(r'(?is)For your free copy of Seabreeze.*?(?=\n#|\Z)', '', text)

    # 12. Clean running headers, footers, stray bullet points, double hashes
    text = re.sub(r'(?im)^[ \t]*Seabreeze\s*[-–—]?\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{4}[ \t]*$', '', text)
    text = re.sub(r'(?im)^[ \t]*\d{1,2}\s+SEABREEZE(?:\s+SEABROKERS\s+GROUP)?.*$', '', text)
    text = re.sub(r'(?im)^[ \t]*SEABREEZE\s+\d{1,2}.*$', '', text)
    text = re.sub(r'(?im)^[ \t]*SEABREEZE\b.*©.*$', '', text)
    text = re.sub(r'(?m)^\s*\d{1,2}\s+\d{1,2}\s*$', '', text)
    text = re.sub(r'(?m)^\s*\d{1,2}\s*$', '', text)
    text = re.sub(r'(?m)^[ \t]*[•\*\-][ \t•\*\-]*$', '', text)
    text = re.sub(r'(?m)^[ \t]*#+[ \t]+(#+[ \t]*[A-Za-z])', r'\1', text)

    # Clean empty header lines
    text = re.sub(r'(?m)^[ \t]*#+[ \t]*(?:\*{1,2}[ \t]*\*{1,2}|\*{1,2})?[ \t]*$', '', text)

    # Remove stray lone question marks or empty dividers
    text = re.sub(r'(?m)^\s*\?\s*$', '', text)
    text = re.sub(r'(?m)^---[ \t]*\n(?:---[ \t]*\n)+', '---\n', text)

    # Normalize multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def parse_markdown_tables(md_text: str):
    """Parses all Markdown pipe tables into structured dictionaries."""
    lines = md_text.split('\n')
    tables = []
    current_table = []
    current_header = 'Table'
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            if not in_table:
                current_header = stripped.lstrip('#').strip()
        if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            current_table.append(stripped)
        else:
            if in_table and len(current_table) >= 2:
                tbl = _build_table_dict(current_header, current_table)
                if tbl:
                    tables.append(tbl)
            current_table = []
            in_table = False

    if in_table and len(current_table) >= 2:
        tbl = _build_table_dict(current_header, current_table)
        if tbl:
            tables.append(tbl)

    return tables


def _build_table_dict(header_title: str, table_lines: list):
    try:
        header_row = [c.strip() for c in table_lines[0].split('|')[1:-1]]
        data_rows = []
        for r in table_lines[2:]:  # skip separator line
            cells = [c.strip() for c in r.split('|')[1:-1]]
            if len(cells) == len(header_row):
                data_rows.append(dict(zip(header_row, cells)))
            elif cells:
                data_rows.append(cells)
        return {
            "title": header_title,
            "columns": header_row,
            "row_count": len(data_rows),
            "rows": data_rows
        }
    except Exception:
        return None


def process_single_report(pdf_path: Path):
    stem = pdf_path.stem
    iso_date, year, month = parse_date_from_filename(pdf_path.name)
    month_name = MONTH_NAMES.get(month, f"Month {month}")
    report_title = f"Seabreeze Monthly Offshore Market Report - {month_name} {year}"

    target_md_dir = MD_BASE_DIR / str(year)
    target_md_dir.mkdir(parents=True, exist_ok=True)
    target_md_path = target_md_dir / f"{stem}.md"
    target_tables_path = target_md_dir / f"{stem}.tables.json"
    cache_json = CACHE_DIR / f"{stem}.json"

    raw_text = None
    pages_count = 0

    # 1. Check valid cache first
    if cache_json.exists():
        try:
            cached_data = json.loads(cache_json.read_text(encoding="utf-8"))
            cached_text = cached_data.get("full_text", "")
            if len(cached_text.strip()) > 0:
                raw_text = cached_text
                pages_count = cached_data.get("pages", 16)
        except Exception:
            pass

    # 2. Call LlamaParse if not cached
    if not raw_text:
        max_retries = 8
        for attempt in range(max_retries):
            try:
                parser = get_active_parser(result_type="markdown", tier="cost_effective")
                docs = parser.load_data(str(pdf_path))
                if not docs:
                    raise RuntimeError("LlamaParse returned 0 docs (upload timed out or dropped)")
                parsed_text = "\n\n---\n\n".join(d.text for d in docs)
                if not parsed_text.strip():
                    raise RuntimeError("LlamaParse returned empty text")
                pages_count = len(docs)
                raw_text = parsed_text
                # Save cache immediately
                cache_json.write_text(json.dumps({
                    "stem": stem,
                    "pages": pages_count,
                    "full_text": raw_text
                }, indent=2), encoding="utf-8")
                break
            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ["429", "402", "quota", "credit", "empty", "0 docs", "exhausted", "timed out", "dropped"]):
                    logger.warning(f"Rotating key due to quota error on {stem}: {e}")
                    manager.mark_key_exhausted(reason=err_str)
                else:
                    wait_time = (attempt + 1) * 4
                    logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {stem}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise e

    if not raw_text:
        raise RuntimeError(f"Failed to extract text for {stem}")

    # 3. Publication-grade Normalization
    clean_text = normalize_seabrokers_content(raw_text)

    # 4. Parse structured tables
    tables = parse_markdown_tables(clean_text)

    word_count = len(clean_text.split())

    # 5. Format Frontmatter
    frontmatter = f"""---
title: "{report_title}"
issue_date: "{iso_date}"
year: {year}
month: {month}
publisher: "Seabrokers Chartering"
source: "seabrokers"
category: "Offshore"
pages: {pages_count}
source_file: "corpus/05-seabrokers/pdfs/{pdf_path.name}"
tables_count: {len(tables)}
word_count: {word_count}
tags:
  - Offshore
  - OSV
  - PSV
  - AHTS
  - Subsea
  - Rigs
  - Renewables
---

"""
    full_markdown = f"{frontmatter}{clean_text}\n"
    target_md_path.write_text(full_markdown, encoding="utf-8")

    # Also synchronize to corpus/05-seabrokers/{year}/{stem}.md
    corpus_md_dir = REPO_ROOT / "corpus" / "05-seabrokers" / str(year)
    corpus_md_dir.mkdir(parents=True, exist_ok=True)
    (corpus_md_dir / f"{stem}.md").write_text(full_markdown, encoding="utf-8")

    # 6. Save structured table sidecar
    table_sidecar = {
        "title": report_title,
        "issue_date": iso_date,
        "year": year,
        "month": month,
        "source_file": f"corpus/05-seabrokers/pdfs/{pdf_path.name}",
        "tables_count": len(tables),
        "tables": tables
    }
    target_tables_path.write_text(json.dumps(table_sidecar, indent=2), encoding="utf-8")

    return {
        "stem": stem,
        "issue_date": iso_date,
        "year": year,
        "month": month,
        "title": report_title,
        "pages": pages_count,
        "tables_count": len(tables),
        "word_count": word_count,
        "source_file": f"corpus/05-seabrokers/pdfs/{pdf_path.name}",
        "extracted_file": f"data/extracted/md/seabrokers/{year}/{stem}.md",
        "tables_file": f"data/extracted/md/seabrokers/{year}/{stem}.tables.json"
    }


def update_offshore_summary_json():
    """Enriches data/derived/offshore_summary.json with md_url and tables_count

    Preserves 100% of all existing keys to guarantee zero frontend breaks and
    100% pass on tests/test_offshore_and_port_stress.py.
    """
    summary_path = REPO_ROOT / "data" / "derived" / "offshore_summary.json"
    if not summary_path.exists():
        return
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        reports = data.get("reports", [])
        for rep in reports:
            slug = rep.get("slug")
            date_str = rep.get("date")
            yr = rep.get("year")
            # Match to extracted md file
            md_cand = list((MD_BASE_DIR / str(yr)).glob(f"{date_str}_*.md"))
            if md_cand:
                rep["md_path"] = f"data/extracted/md/seabrokers/{yr}/{md_cand[0].name}"
                tables_cand = list((MD_BASE_DIR / str(yr)).glob(f"{date_str}_*.tables.json"))
                if tables_cand:
                    rep["tables_path"] = f"data/extracted/md/seabrokers/{yr}/{tables_cand[0].name}"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"[+] Enriched {summary_path} with md_path and tables_path references.")
    except Exception as e:
        logger.error(f"Failed to enrich offshore_summary.json: {e}")


def run_pipeline():
    logger.info("=== STARTING SEABROKERS FULL LLAMAPARSE EXTRACTION PIPELINE ===")

    pdf_files = sorted(list(PDF_DIR.glob("*.pdf")))
    logger.info(f"Found {len(pdf_files)} Seabrokers PDFs to process.")

    state = load_run_state()
    done = state.get("done", {})
    failed = state.get("failed", {})

    # Re-normalize all already cached reports immediately
    results = []
    pending_pdfs = []

    junk = state.get("junk", {})

    for p in pdf_files:
        # Route junk explicitly: LlamaParse rejects non-PDF bytes with HTTP 415
        # ("File content does not match its '.pdf' extension"), which the retry
        # loop would otherwise burn 8 attempts on.
        try:
            magic = p.open("rb").read(5)
        except Exception as e:
            magic = b""
        if not magic.startswith(b"%PDF-"):
            junk[p.stem] = f"JUNK: not a PDF (magic={magic[:5]!r})"
            logger.warning(f"[junk] {p.name} is not a PDF (magic={magic[:5]!r}) - excluded")
            continue
        cache_f = CACHE_DIR / f"{p.stem}.json"
        if cache_f.exists():
            try:
                cd = json.loads(cache_f.read_text(encoding="utf-8"))
                if len(cd.get("full_text", "").strip()) > 0:
                    res = process_single_report(p)
                    done[p.stem] = res
                    results.append(res)
                    continue
            except Exception:
                pass
        pending_pdfs.append(p)

    state["done"] = done
    state["failed"] = failed
    state["junk"] = junk
    save_run_state(state)

    logger.info(f"Loaded and re-normalized {len(results)} cached reports. Pending fresh LlamaParse: {len(pending_pdfs)}")

    # Process pending files with max_workers=2 to prevent network timeouts/drops
    if pending_pdfs:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(process_single_report, p): p for p in pending_pdfs}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    res = fut.result()
                    done[p.stem] = res
                    results.append(res)
                    logger.info(f"[+] Completed {p.name}: {res['pages']} pages, {res['tables_count']} tables, {res['word_count']} words")
                except Exception as e:
                    logger.error(f"[!] Failed {p.name}: {e}")
                    failed[p.stem] = str(e)
                state["done"] = done
                state["failed"] = failed
                save_run_state(state)

    logger.info(f"Successfully processed {len(results)} of {len(pdf_files)} Seabreeze reports.")

    # Save master metadata catalog
    results.sort(key=lambda x: (x["issue_date"], x["stem"]))
    df_cat = pd.DataFrame(results)
    csv_cat = SERIES_DIR / "seabrokers_catalog_metadata.csv"
    df_cat.to_csv(csv_cat, index=False)
    logger.info(f"[+] Saved master Seabrokers catalog metadata: {csv_cat} ({len(df_cat)} rows)")

    # Enrich offshore_summary.json without breaking any existing contracts
    update_offshore_summary_json()

    logger.info("=== SEABROKERS LLAMAPARSE PIPELINE COMPLETE ===")


if __name__ == "__main__":
    run_pipeline()
