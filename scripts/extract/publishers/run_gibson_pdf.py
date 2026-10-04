"""
Gibson Shipbrokers Weekly Tanker Market Report Extraction Pipeline (2021-2023 PDFs).

Processes all historical Gibson weekly PDF reports:
1. Discards back cover page (Paratus advert) and charts (Crude/Clean/Dirty spot graphs and page 1 graphics).
2. Extracts complete narrative commentary structured cleanly by section and sub-heading:
   - Market Editorial (Lead story)
   - Crude Oil: Middle East, Mediterranean, West Africa, US Gulf/Latin America, North Sea
   - Clean Products: East, Mediterranean, UK Continent
   - Dirty Products: Handy, MR, Panamax
3. Extracts tabular market assessments from penultimate page:
   - Dirty Tanker Spot Worldscale & $/day TCE (TD3C, TD20, TD7)
   - Clean Tanker Spot Worldscale & $/day TCE (TC1, TC2, TC5, TC7)
   - ClearView Bunker Prices (Rotterdam VLSFO, Fujairah VLSFO, Singapore VLSFO, Rotterdam LSMGO)
4. Emits:
   - data/extracted/md/gibson/<year>/<stem>.md
   - data/extracted/md/gibson/<year>/<stem>.tables.json
   - data/extracted/series/gibson_tanker_spot_series.csv
   - data/extracted/series/gibson_bunker_prices_series.csv
   - data/extracted/series/gibson_master_tanker_series.xlsx
"""

import os
import re
import csv
import json
from pathlib import Path
from datetime import datetime
import pymupdf
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CORPUS_DIR = REPO_ROOT / "corpus" / "01-brokers" / "gibson"
OUTPUT_MD_DIR = REPO_ROOT / "data" / "extracted" / "md" / "gibson"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"

SPOT_CSV_PATH = SERIES_DIR / "gibson_tanker_spot_series.csv"
BUNKER_CSV_PATH = SERIES_DIR / "gibson_bunker_prices_series.csv"
EXCEL_PATH = SERIES_DIR / "gibson_master_tanker_series.xlsx"

MONTH_MAP = {
    'january': '01', 'jan': '01',
    'february': '02', 'feb': '02',
    'march': '03', 'mar': '03',
    'april': '04', 'apr': '04',
    'may': '05',
    'june': '06', 'jun': '06',
    'july': '07', 'jul': '07',
    'august': '08', 'aug': '08',
    'september': '09', 'sep': '09', 'sept': '09',
    'october': '10', 'oct': '10',
    'november': '11', 'nov': '11',
    'december': '12', 'dec': '12'
}

def clean_text_encoding(text: str) -> str:
    """Normalize UTF-8 characters, smart quotes, and dashes."""
    if not text:
        return ""
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    text = text.replace('\xa0', ' ').replace('\ufffd', "'")
    text = re.sub(r'[\x80-\x9f]', '', text)
    return text.strip()

def parse_date_and_week(doc, filename: str):
    """Derive ISO issue_date and report_week from PDF text or filename."""
    p1_text = clean_text_encoding(doc[0].get_text())
    
    m_week = re.search(r'Week\s+(\d+)\s*\|\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d\d)', p1_text, re.IGNORECASE)
    week_no = None
    iso_date = None
    
    if m_week:
        week_no = int(m_week.group(1))
        day = int(m_week.group(2))
        month_name = m_week.group(3).lower()
        year = int(m_week.group(4))
        month_num = MONTH_MAP.get(month_name[:3], '01')
        iso_date = f"{year:04d}-{month_num}-{day:02d}"
        
    if not iso_date:
        m_file = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
        if m_file:
            iso_date = f"{m_file.group(1)}-{m_file.group(2)}-{m_file.group(3)}"
            try:
                dt = datetime.strptime(iso_date, "%Y-%m-%d")
                week_no = dt.isocalendar()[1]
            except Exception:
                week_no = None

    if not iso_date:
        iso_date = "2021-01-01"
    if not week_no:
        try:
            dt = datetime.strptime(iso_date, "%Y-%m-%d")
            week_no = dt.isocalendar()[1]
        except Exception:
            week_no = 1

    return iso_date, week_no

def extract_editorial(doc, crude_start_pno: int, title: str):
    """Extract lead market editorial from page 0 up to crude_start_pno."""
    editorial_lines = []
    
    for pno in range(0, crude_start_pno):
        pd = doc[pno].get_text('dict')
        for b in pd['blocks']:
            if 'lines' not in b:
                continue
            bbox = b['bbox']
            # Header / footer margin filter
            if bbox[1] < 75 or bbox[3] > 780:
                continue
            # Filter page 1 embedded charts (e.g. Argentina Monthly Crude Exports chart)
            # Typically centered/left between y=230 and y=530 with small ticks
            b_full_text = clean_text_encoding(' '.join(s['text'].strip() for l in b['lines'] for s in l['spans']))
            if 'Source:' in b_full_text or b_full_text in ['Suezmax', 'Aframax']:
                continue
                
            for l in b['lines']:
                spans = l['spans']
                if any(s['size'] >= 13 for s in spans):
                    continue # title / subtitle
                line_str = clean_text_encoding(' '.join(s['text'].strip() for s in spans))
                if not line_str or line_str.startswith('Source:') or line_str.startswith('Page '):
                    continue
                if line_str in ['Weekly Tanker Market Report', 'Weekly Tanker Report'] or title in line_str:
                    continue
                # Discard numeric axis ticks
                words = line_str.split()
                if len(words) <= 5 and all(w.isdigit() or w in ['-', '+', '%'] or re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}$', w) for w in words):
                    continue
                if line_str in ['Suezmax', 'Aframax']:
                    continue
                editorial_lines.append(line_str)
                
    full_text = " ".join(editorial_lines)
    full_text = re.sub(r'\s+', ' ', full_text)
    words = full_text.split()
    paras = []
    curr_para = []
    for w in words:
        curr_para.append(w)
        if len(curr_para) >= 60 and w.endswith(('.', '!', '?')):
            paras.append(" ".join(curr_para))
            curr_para = []
    if curr_para:
        paras.append(" ".join(curr_para))
    return paras

def extract_sections(doc, crude_start_pno: int, table_pno: int):
    """Extract Crude Oil, Clean Products, and Dirty Products commentary."""
    sections = {
        'Crude Oil': {
            'Middle East': [],
            'Mediterranean': [],
            'West Africa': [],
            'US Gulf/Latin America': [],
            'North Sea': []
        },
        'Clean Products': {
            'East': [],
            'Mediterranean': [],
            'UK Continent': []
        },
        'Dirty Products': {
            'Handy': [],
            'MR': [],
            'Panamax': []
        }
    }
    
    sub_map = {
        'middle east': 'Middle East',
        'west africa': 'West Africa',
        'mediterranean': 'Mediterranean',
        'us gulf/latin america': 'US Gulf/Latin America',
        'us gulf / latin america': 'US Gulf/Latin America',
        'north sea': 'North Sea',
        'east': 'East',
        'uk continent': 'UK Continent',
        'handy': 'Handy',
        'mr': 'MR',
        'panamax': 'Panamax'
    }
    
    curr_major = None
    curr_sub = None
    
    for pno in range(crude_start_pno, table_pno):
        page = doc[pno]
        pd = page.get_text('dict')
        page_raw = page.get_text()
        
        # Determine chart coordinates on this page
        has_crude_chart = 'Crude Tanker Spot Rates' in page_raw
        has_clean_chart = 'Clean Product Tanker Spot Rates' in page_raw
        has_dirty_chart = 'Dirty Product Tanker Spot Rates' in page_raw
        
        blocks = []
        for b in pd['blocks']:
            if 'lines' in b:
                bbox = b['bbox']
                if bbox[1] < 75 or bbox[3] > 780:
                    continue
                    
                # Chart elimination based on geometry:
                # 1. Crude chart on right column: x0 >= 300
                if has_crude_chart and bbox[0] >= 300:
                    continue
                # 2. Clean chart on right column bottom: x0 >= 300 and y0 >= 370
                if has_clean_chart and bbox[0] >= 300 and bbox[1] >= 370:
                    continue
                # 3. Dirty chart on right column bottom: x0 >= 300 and y0 >= 530
                if has_dirty_chart and bbox[0] >= 300 and bbox[1] >= 530:
                    continue
                    
                col = 0 if bbox[0] < 300 else 1
                blocks.append((col, bbox[1], b))
                
        blocks.sort(key=lambda x: (x[0], x[1]))
        
        for col, y_top, b in blocks:
            for l in b['lines']:
                line_spans = l['spans']
                line_txt = clean_text_encoding(' '.join(s['text'].strip() for s in line_spans))
                if not line_txt:
                    continue
                    
                # Major headers (size >= 20)
                if any(s['size'] >= 20 for s in line_spans):
                    for s in line_spans:
                        st = clean_text_encoding(s['text'].strip())
                        if st in ['Crude Oil', 'Clean Products', 'Dirty Products']:
                            curr_major = st
                            curr_sub = None
                    continue
                    
                # Subheadings (size >= 12)
                is_sub = False
                for s in line_spans:
                    st = clean_text_encoding(s['text'].strip()).lower()
                    if st in sub_map and s['size'] >= 12:
                        curr_sub = sub_map[st]
                        is_sub = True
                        break
                if is_sub:
                    continue
                    
                # Discard chart graphics / legend text / tick artifacts
                if 'Spot Rates' in line_txt or line_txt.startswith('*All rates') or 'terms of WS100' in line_txt:
                    continue
                if line_txt.lower() in ['time', 'ws']:
                    continue
                words = line_txt.split()
                if len(words) <= 4 and all(w.isdigit() or w in ['-', '+', 'WS'] or re.match(r'^(Aug|Sep|Oct|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul)\s+\d{2}$', w) for w in words):
                    continue
                if any(w in line_txt for w in ['Mid East/China 270kt', 'WA/UKC 130kt', 'UKC/UKC 80kt', 'UKC/USAC 37kt', 'Singapore/Australia 30kt', 'Mid East/Japan 55kt', 'Mid East/Japan 75kt', 'ARA/USG 55kt', 'Black Sea/Med 30kt', 'Baltic Sea/UKC 30kt']):
                    continue
                    
                if curr_major and curr_sub and curr_major in sections and curr_sub in sections[curr_major]:
                    sections[curr_major][curr_sub].append(line_txt)
                    
    cleaned_sections = {}
    for maj, subs in sections.items():
        cleaned_sections[maj] = {}
        for sub, lines in subs.items():
            joined = clean_text_encoding(" ".join(lines))
            joined = re.sub(r'\s+', ' ', joined)
            # Remove any trailing 'time Aug 21 Sep 21' leftovers
            joined = re.sub(r'\s*(?:time\s*)?(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}\s*)+(?:time)?\s*$', '', joined, flags=re.IGNORECASE)
            joined = re.sub(r'\s*time\s*$', '', joined, flags=re.IGNORECASE)
            cleaned_sections[maj][sub] = joined.strip()
            
    return cleaned_sections

def parse_trailing_numbers(line: str):
    """Split line into textual route prefix and numerical assessment values."""
    tokens = line.split()
    num_tokens = []
    i = len(tokens) - 1
    while i >= 0:
        t = tokens[i]
        clean_t = t.replace(',', '').replace('+', '')
        try:
            float(clean_t)
            num_tokens.append(t)
            i -= 1
        except ValueError:
            break
    num_tokens.reverse()
    text_part = " ".join(tokens[:i+1])
    return text_part, num_tokens

def parse_table_page(page, iso_date: str, report_week: int, source_file: str):
    """Extract Dirty Spot, Clean Spot, and Bunker Prices tables."""
    words = page.get_text('words')
    sorted_words = sorted(words, key=lambda w: (round(w[1] / 5.0) * 5, w[0]))
    lines_by_y = {}
    for w in sorted_words:
        yk = round(w[1] / 5.0) * 5
        lines_by_y.setdefault(yk, []).append(w)
        
    grouped_lines = []
    for yk in sorted(lines_by_y.keys()):
        lw = sorted(lines_by_y[yk], key=lambda x: x[0])
        txt = clean_text_encoding(" ".join(w[4] for w in lw))
        grouped_lines.append(txt)
        
    ffa_period = "FFA"
    for gl in grouped_lines:
        m_ffa = re.search(r'FFA\s+(Q\d)', gl)
        if m_ffa:
            ffa_period = m_ffa.group(1)
            break
        elif 'Q1' in gl or 'Q2' in gl or 'Q3' in gl or 'Q4' in gl:
            m_q = re.search(r'\b(Q[1-4])\b', gl)
            if m_q:
                ffa_period = m_q.group(1)
                break
                
    spot_rows = []
    bunker_rows = []
    
    current_category = "Dirty Tanker Spot"
    current_type = "Spot Worldscale"
    
    for gl in grouped_lines:
        if 'Dirty Tanker' in gl and 'Worldscale' in gl:
            current_category = "Dirty Tanker Spot"
            current_type = "Spot Worldscale"
            continue
        elif 'Dirty Tanker' in gl and ('tce' in gl.lower() or '$/day' in gl):
            current_category = "Dirty Tanker Spot"
            current_type = "$/day TCE"
            continue
        elif 'Clean Tanker' in gl and 'Worldscale' in gl:
            current_category = "Clean Tanker Spot"
            current_type = "Spot Worldscale"
            continue
        elif 'Clean Tanker' in gl and ('tce' in gl.lower() or '$/day' in gl):
            current_category = "Clean Tanker Spot"
            current_type = "$/day TCE"
            continue
            
        for r_code in ['TD3C', 'TD20', 'TD7', 'TC1', 'TC2', 'TC5', 'TC7']:
            if gl.startswith(r_code):
                txt_part, nums = parse_trailing_numbers(gl)
                vessel_class = ""
                route_desc = ""
                rem = txt_part[len(r_code):].strip()
                
                if r_code == 'TD3C':
                    vessel_class = "VLCC"
                    route_desc = "AG-China"
                elif r_code == 'TD20':
                    vessel_class = "Suezmax"
                    route_desc = "WAF-UKC"
                elif r_code == 'TD7':
                    vessel_class = "Aframax"
                    route_desc = "N.Sea-UKC"
                elif r_code == 'TC1':
                    vessel_class = "LR2"
                    route_desc = "AG-Japan"
                elif r_code == 'TC2':
                    vessel_class = "MR - west"
                    route_desc = "UKC-USAC"
                elif r_code == 'TC5':
                    vessel_class = "LR1"
                    route_desc = "AG-Japan"
                elif r_code == 'TC7':
                    vessel_class = "MR - east"
                    route_desc = "Singapore-EC Aus"
                else:
                    parts = rem.split(None, 1)
                    vessel_class = parts[0] if len(parts) > 0 else ""
                    route_desc = parts[1] if len(parts) > 1 else ""
                    
                chg = nums[0] if len(nums) > 0 else ""
                curr = nums[1] if len(nums) > 1 else ""
                prev = nums[2] if len(nums) > 2 else ""
                mth = nums[3] if len(nums) > 3 else ""
                ffa = nums[4] if len(nums) > 4 else ""
                
                def parse_val(v):
                    if not v:
                        return None
                    clean = v.replace(',', '').replace('+', '').strip()
                    try:
                        return float(clean)
                    except ValueError:
                        return None

                spot_rows.append({
                    'issue_date': iso_date,
                    'report_week': report_week,
                    'category': current_category,
                    'market_type': current_type,
                    'route_code': r_code,
                    'vessel_class': vessel_class,
                    'route_description': route_desc,
                    'change_wow': parse_val(chg),
                    'rate_current': parse_val(curr),
                    'rate_prev': parse_val(prev),
                    'rate_last_month': parse_val(mth),
                    'ffa_value': parse_val(ffa),
                    'ffa_period': ffa_period if parse_val(ffa) is not None else "",
                    'source_file': source_file
                })
                break
                
        if 'ClearView Bunker Price' in gl or ('Bunker Price' in gl and any(p in gl for p in ['Rotterdam', 'Fujairah', 'Singapore'])):
            txt_part, nums = parse_trailing_numbers(gl)
            port = ""
            grade = ""
            if 'Rotterdam VLSFO' in txt_part:
                port, grade = 'Rotterdam', 'VLSFO'
            elif 'Fujairah VLSFO' in txt_part:
                port, grade = 'Fujairah', 'VLSFO'
            elif 'Singapore VLSFO' in txt_part:
                port, grade = 'Singapore', 'VLSFO'
            elif 'Rotterdam LSMGO' in txt_part:
                port, grade = 'Rotterdam', 'LSMGO'
            else:
                port, grade = 'Global', 'Bunkers'
                
            chg = nums[0] if len(nums) > 0 else ""
            curr = nums[1] if len(nums) > 1 else ""
            prev = nums[2] if len(nums) > 2 else ""
            mth = nums[3] if len(nums) > 3 else ""
            
            def parse_val(v):
                if not v:
                    return None
                clean = v.replace(',', '').replace('+', '').strip()
                try:
                    return float(clean)
                except ValueError:
                    return None
                    
            bunker_rows.append({
                'issue_date': iso_date,
                'report_week': report_week,
                'port': port,
                'grade': grade,
                'change_wow': parse_val(chg),
                'price_current': parse_val(curr),
                'price_prev': parse_val(prev),
                'price_last_month': parse_val(mth),
                'source_file': source_file
            })
            
    return spot_rows, bunker_rows, grouped_lines

def format_markdown(iso_date: str, report_week: int, title: str, editorial: list, sections: dict, spot_rows: list, bunker_rows: list, total_pages: int, table_page: int, rel_path: str):
    """Format extracted intelligence into publication-grade Markdown."""
    year = int(iso_date.split('-')[0])
    lines = [
        "---",
        f'title: "{title}"',
        'subtitle: "Weekly Tanker Market Report"',
        f'issue_date: "{iso_date}"',
        f'year: {year}',
        f'report_week: {report_week}',
        'broker: "gibson"',
        'category: "tankers"',
        f'pages: {total_pages}',
        f'table_page: {table_page + 1}',
        f'source_file: "{rel_path}"',
        f'tables_count: {len(spot_rows) + len(bunker_rows)}',
        "---",
        "",
        f"# {title}",
        f"**Weekly Tanker Market Report | Week {report_week} ({iso_date})**",
        "",
        "## Market Editorial",
        ""
    ]
    
    for p in editorial:
        lines.append(p)
        lines.append("")
        
    for maj in ['Crude Oil', 'Clean Products', 'Dirty Products']:
        if maj in sections:
            lines.append(f"## {maj}")
            lines.append("")
            for sub, text in sections[maj].items():
                lines.append(f"### {sub}")
                lines.append("")
                if text:
                    lines.append(text)
                else:
                    lines.append("*No specific commentary reported for this sector this week.*")
                lines.append("")
                
    lines.append("## Tanker Market Assessment Tables")
    lines.append("")
    
    d_ws = [r for r in spot_rows if r['category'] == 'Dirty Tanker Spot' and r['market_type'] == 'Spot Worldscale']
    if d_ws:
        lines.append("### Dirty Tanker Spot Market Developments - Spot Worldscale")
        lines.append("")
        lines.append("| Route | Vessel | Description | WoW Change | Current | Previous | Last Month | FFA |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in d_ws:
            lines.append(f"| {r['route_code']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        lines.append("")
        
    d_tce = [r for r in spot_rows if r['category'] == 'Dirty Tanker Spot' and r['market_type'] == '$/day TCE']
    if d_tce:
        lines.append("### Dirty Tanker Spot Market Developments - $/day TCE")
        lines.append("")
        lines.append("| Route | Vessel | Description | WoW Change ($) | Current ($/day) | Previous ($/day) | Last Month ($/day) | FFA ($/day) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in d_tce:
            lines.append(f"| {r['route_code']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        lines.append("")
        
    c_ws = [r for r in spot_rows if r['category'] == 'Clean Tanker Spot' and r['market_type'] == 'Spot Worldscale']
    if c_ws:
        lines.append("### Clean Tanker Spot Market Developments - Spot Worldscale")
        lines.append("")
        lines.append("| Route | Vessel | Description | WoW Change | Current | Previous | Last Month | FFA |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in c_ws:
            lines.append(f"| {r['route_code']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        lines.append("")
        
    c_tce = [r for r in spot_rows if r['category'] == 'Clean Tanker Spot' and r['market_type'] == '$/day TCE']
    if c_tce:
        lines.append("### Clean Tanker Spot Market Developments - $/day TCE")
        lines.append("")
        lines.append("| Route | Vessel | Description | WoW Change ($) | Current ($/day) | Previous ($/day) | Last Month ($/day) | FFA ($/day) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in c_tce:
            lines.append(f"| {r['route_code']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        lines.append("")
        
    if bunker_rows:
        lines.append("### ClearView Bunker Prices ($/tonne)")
        lines.append("")
        lines.append("| Port | Grade | WoW Change ($) | Current ($/t) | Previous ($/t) | Last Month ($/t) |")
        lines.append("|---|---|---|---|---|---|")
        for r in bunker_rows:
            lines.append(f"| {r['port']} | {r['grade']} | {r['change_wow'] or '-'} | {r['price_current'] or '-'} | {r['price_prev'] or '-'} | {r['price_last_month'] or '-'} |")
        lines.append("")
        
    return "\n".join(lines)

def run_gibson_pipeline():
    """Execute complete Gibson extraction across all PDFs."""
    print("Starting Gibson Shipbrokers PDF Extraction Pipeline...")
    OUTPUT_MD_DIR.mkdir(parents=True, exist_ok=True)
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    
    pdfs = sorted(CORPUS_DIR.glob('**/*.pdf'))
    print(f"Found {len(pdfs)} PDF reports in {CORPUS_DIR}")
    
    all_spot_rows = []
    all_bunker_rows = []
    processed_count = 0
    
    for pdf_path in pdfs:
        try:
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            rel_path = str(pdf_path.relative_to(REPO_ROOT)).replace('\\', '/')
            
            # 1. Date & Week
            iso_date, report_week = parse_date_and_week(doc, pdf_path.name)
            year = iso_date.split('-')[0]
            
            # 2. Title
            p1_dict = doc[0].get_text('dict')
            title = None
            for b in p1_dict['blocks']:
                if 'lines' in b:
                    for l in b['lines']:
                        for s in l['spans']:
                            if s['size'] >= 18 and clean_text_encoding(s['text'].strip()) not in ['GIBSON', 'Page 01']:
                                title = clean_text_encoding(s['text'].strip())
                                break
                if title:
                    break
            if not title:
                parts = pdf_path.stem.split('-')
                title = ' '.join(parts[3:]).replace('_', ' ') if len(parts) > 3 else pdf_path.stem
                
            # 3. Locate Crude Oil and Table page
            crude_start_pno = 1
            table_pno = len(doc) - 2
            for i, page in enumerate(doc):
                t = page.get_text()
                if 'Crude Oil' in t and crude_start_pno == 1 and i > 0:
                    crude_start_pno = i
                if 'Dirty Tanker Spot Market Developments' in t or 'Spot Worldscale' in t:
                    table_pno = i
                    
            # 4. Extract content
            editorial = extract_editorial(doc, crude_start_pno, title)
            sections = extract_sections(doc, crude_start_pno, table_pno)
            spot_rows, bunker_rows, grouped_lines = parse_table_page(doc[table_pno], iso_date, report_week, rel_path)
            
            all_spot_rows.extend(spot_rows)
            all_bunker_rows.extend(bunker_rows)
            
            # 5. Format and save Markdown
            md_content = format_markdown(
                iso_date=iso_date,
                report_week=report_week,
                title=title,
                editorial=editorial,
                sections=sections,
                spot_rows=spot_rows,
                bunker_rows=bunker_rows,
                total_pages=total_pages,
                table_page=table_pno,
                rel_path=rel_path
            )
            
            out_year_dir = OUTPUT_MD_DIR / year
            out_year_dir.mkdir(parents=True, exist_ok=True)
            
            stem = pdf_path.stem
            md_path = out_year_dir / f"{stem}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            # 6. Save Table Sidecar JSON
            tables_sidecar = {
                'issue_date': iso_date,
                'report_week': report_week,
                'title': title,
                'source_file': rel_path,
                'spot_rates': spot_rows,
                'bunker_prices': bunker_rows
            }
            json_path = out_year_dir / f"{stem}.tables.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(tables_sidecar, f, indent=2)
                
            doc.close()
            processed_count += 1
            if processed_count % 25 == 0 or processed_count == len(pdfs):
                print(f"Processed {processed_count}/{len(pdfs)} reports...")
                
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")
            
    print(f"\nCompleted extraction of {processed_count} Gibson PDF reports.")
    print(f"Total Tanker Spot records: {len(all_spot_rows)}")
    print(f"Total Bunker Price records: {len(all_bunker_rows)}")
    
    # 7. Write Series CSVs
    if all_spot_rows:
        df_spot = pd.DataFrame(all_spot_rows)
        df_spot = df_spot.drop_duplicates(subset=['issue_date', 'category', 'market_type', 'route_code'])
        df_spot = df_spot.sort_values(by=['issue_date', 'category', 'market_type', 'route_code'])
        df_spot.to_csv(SPOT_CSV_PATH, index=False, encoding='utf-8')
        print(f"Saved: {SPOT_CSV_PATH} ({len(df_spot)} rows)")
        
    if all_bunker_rows:
        df_bunker = pd.DataFrame(all_bunker_rows)
        df_bunker = df_bunker.drop_duplicates(subset=['issue_date', 'port', 'grade'])
        df_bunker = df_bunker.sort_values(by=['issue_date', 'port', 'grade'])
        df_bunker.to_csv(BUNKER_CSV_PATH, index=False, encoding='utf-8')
        print(f"Saved: {BUNKER_CSV_PATH} ({len(df_bunker)} rows)")
        
    # 8. Create Master Multi-Tab Excel Workbook
    if all_spot_rows and all_bunker_rows:
        with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
            df_dirty = df_spot[df_spot['category'] == 'Dirty Tanker Spot']
            df_dirty.to_excel(writer, sheet_name='Dirty Spot WS & TCE', index=False)
            
            df_clean = df_spot[df_spot['category'] == 'Clean Tanker Spot']
            df_clean.to_excel(writer, sheet_name='Clean Spot WS & TCE', index=False)
            
            df_bunker.to_excel(writer, sheet_name='Bunker Prices', index=False)
            
            pivot_rates = df_spot.pivot_table(
                index=['issue_date', 'report_week'],
                columns=['market_type', 'route_code'],
                values='rate_current'
            ).reset_index()
            pivot_rates.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in pivot_rates.columns]
def extract_gibson_single_pdf(pdf_path: Path, dry_run: bool = False):
    """Process a single Gibson PDF report for incremental orchestrator ingestion."""
    pdf_path = Path(pdf_path).resolve()
    stem = pdf_path.stem
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    rel_path = str(pdf_path.relative_to(REPO_ROOT)).replace('\\', '/')
    
    iso_date, report_week = parse_date_and_week(doc, pdf_path.name)
    year = iso_date.split('-')[0]
    
    p1_dict = doc[0].get_text('dict')
    title = None
    for b in p1_dict['blocks']:
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
                    if s['size'] >= 18 and clean_text_encoding(s['text'].strip()) not in ['GIBSON', 'Page 01']:
                        title = clean_text_encoding(s['text'].strip())
                        break
        if title:
            break
    if not title:
        parts = pdf_path.stem.split('-')
        title = ' '.join(parts[3:]).replace('_', ' ') if len(parts) > 3 else pdf_path.stem
        
    crude_start_pno = 1
    table_pno = len(doc) - 2
    for i, page in enumerate(doc):
        t = page.get_text()
        if 'Crude Oil' in t and crude_start_pno == 1 and i > 0:
            crude_start_pno = i
        if 'Dirty Tanker Spot Market Developments' in t or 'Spot Worldscale' in t:
            table_pno = i
            
    editorial = extract_editorial(doc, crude_start_pno, title)
    sections = extract_sections(doc, crude_start_pno, table_pno)
    spot_rows, bunker_rows, grouped_lines = parse_table_page(doc[table_pno], iso_date, report_week, rel_path)
    doc.close()
    
    out_year_dir = OUTPUT_MD_DIR / year
    md_path = out_year_dir / f"{stem}.md"
    json_path = out_year_dir / f"{stem}.tables.json"
    
    if not dry_run:
        out_year_dir.mkdir(parents=True, exist_ok=True)
        md_content = format_markdown(
            iso_date=iso_date,
            report_week=report_week,
            title=title,
            editorial=editorial,
            sections=sections,
            spot_rows=spot_rows,
            bunker_rows=bunker_rows,
            total_pages=total_pages,
            table_page=table_pno,
            rel_path=rel_path
        )
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        tables_sidecar = {
            'issue_date': iso_date,
            'report_week': report_week,
            'title': title,
            'source_file': rel_path,
            'spot_rates': spot_rows,
            'bunker_prices': bunker_rows
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(tables_sidecar, f, indent=2)
            
        # Append to CSVs
        if spot_rows and SPOT_CSV_PATH.exists():
            df_existing = pd.read_csv(SPOT_CSV_PATH)
            df_new = pd.DataFrame(spot_rows)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=['issue_date', 'category', 'market_type', 'route_code'])
            df_combined = df_combined.sort_values(by=['issue_date', 'category', 'market_type', 'route_code'])
            df_combined.to_csv(SPOT_CSV_PATH, index=False, encoding='utf-8')
            
        if bunker_rows and BUNKER_CSV_PATH.exists():
            df_existing = pd.read_csv(BUNKER_CSV_PATH)
            df_new = pd.DataFrame(bunker_rows)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=['issue_date', 'port', 'grade'])
            df_combined = df_combined.sort_values(by=['issue_date', 'port', 'grade'])
            df_combined.to_csv(BUNKER_CSV_PATH, index=False, encoding='utf-8')
            
    return {
        "stem": stem,
        "issue_date": iso_date,
        "report_week": report_week,
        "spot_rows_count": len(spot_rows),
        "bunker_rows_count": len(bunker_rows),
        "target_md": str(md_path)
    }

if __name__ == '__main__':
    run_gibson_pipeline()
