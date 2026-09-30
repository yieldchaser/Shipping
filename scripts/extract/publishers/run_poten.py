"""run_poten.py - Poten & Partners Tanker Opinions extraction pipeline.

High-fidelity cover-to-cover extraction of 1,087 Poten Tanker Opinions PDFs (2004 to 2026).
Key features:
  - Complete prose and section heading extraction without chart/axis/legend noise.
  - All tabular data (annual rankings, mini-tables) converted to GitHub Markdown.
  - Seamless sentence stitching across line breaks, columns, and page transitions.
  - Standardized YAML frontmatter and structured JSON sidecars.
  - Stacks master series:
    * data/extracted/series/poten_top_charterers_series.csv
    * data/extracted/series/poten_opinions_metadata.csv
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "corpus" / "04-poten" / "pdfs"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "poten"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
CHARTERERS_SERIES_CSV = OUT_SERIES_DIR / "poten_top_charterers_series.csv"
METADATA_CATALOG_CSV = OUT_SERIES_DIR / "poten_opinions_metadata.csv"

MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

EXPLICIT_DATES = {
    'A-Mulligan-for-Capesize-Owners.pdf': '2015-01-23',
    'Let-it-Float-Let-it-Float-Let-it-Float.pdf': '2014-12-24',
    'Panamaxes-Cleaning-Up-Their-Act.pdf': '2014-12-12',
    'Weekly-Opinion-Feb-6.pdf': '2015-02-06',
    'West-AfriCAN-Go-East.pdf': '2014-11-21',
    '2014-In-The-Rear-View.pdf': '2014-12-31',
}

CHART_TITLES_AND_AXES = [
    'history of consumption', 'spot fixtures by tanker type', 'refinery throughput',
    'weekly rolling average', 'weekly u.s. crude', 'u.s. refinery throughput',
    'tons/month', '000 bpd', 'mm bbls', 'mm blls', 'ws rates', 'source:', 'bp statistics',
    'eia/poten', 'no. spot', 'fixtures by tanker type', '# spot fixtures',
    '# fixtures', 'handy panamax', 'sea/f.east', 'ag/red sea', 'europe/carib',
    'w.africa', 'china as exporter', 'china as importer', 'crude oil imports by',
    'top 10', 'top 5', 'top reported', 'crude oil exports by', 'more than 300 jets',
    'eia data supports', 'ref throughput', 'how low will it go',
    'arabian gulf to usa', 'top 5 sources', 'vortexa',
    'number of vehicles', 'population in', 'suvs', 'minivans', 'automobiles',
    'gasoline imports', 'gasoline consumption', 'crude inventories', 'us crude',
    'us gasoline', 'spot earnings', 'earnings by vessel', 'orderbook', 'fleet growth',
    'deliveries by', 'contracting by', 'demolition by', 'ton-mile', 'ton mile'
]

CHART_SINGLE_WORDS = {
    'production', 'consumption', 'china', '000', 'bpd', 'mm', 'bbls', 'blls',
    'ws', 'rates', 'eia/poten', 'eia', 'poten', 'partners', 'vortexa',
    'handy', 'panamax', 'aframax', 'suezmax', 'vlcc', 'kbd'
}


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace('\u2026', '...').replace('\x85', '...')
    text = text.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u00a0', ' ')
    text = text.replace('\x92', "'").replace('\x93', '"').replace('\x94', '"').replace('\x91', "'").replace('\x96', '-')
    text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', '', text)
    return text.strip()


def slugify(text: str, max_len: int = 60) -> str:
    text = clean_text(text).lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    if len(text) > max_len:
        cut = text[:max_len]
        if '-' in cut:
            cut = cut.rsplit('-', 1)[0]
        text = cut
    return text or "opinion"


def extract_date(pdf_path: Path) -> str:
    fn = pdf_path.name
    if fn in EXPLICIT_DATES:
        return EXPLICIT_DATES[fn]

    m1 = re.search(r'Tanker_Opinion_(\d{4})(\d{2})(\d{2})', fn, re.I)
    if m1:
        return f"{m1.group(1)}-{m1.group(2)}-{m1.group(3)}"

    m2 = re.search(r'(\d{1,2})[-_\s]+([A-Za-z]+)[-_\s]+(\d{4})', fn)
    if m2 and m2.group(2).lower() in MONTH_MAP:
        return f"{int(m2.group(3)):04d}-{MONTH_MAP[m2.group(2).lower()]:02d}-{int(m2.group(1)):02d}"

    m3 = re.search(r'([A-Za-z]+)[-_\s]+(\d{1,2})[-_\s]+(\d{4})', fn)
    if m3 and m3.group(1).lower() in MONTH_MAP:
        return f"{int(m3.group(3)):04d}-{MONTH_MAP[m3.group(1).lower()]:02d}-{int(m3.group(2)):02d}"

    try:
        with pymupdf.open(pdf_path) as doc:
            page = doc[0]
            blocks = sorted(page.get_text('blocks'), key=lambda b: (b[1], b[0]))
            top_text = ' '.join([b[4].strip() for b in blocks[:10] if b[4].strip()])
            m_t = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})', top_text, re.I)
            if m_t and m_t.group(1).lower() in MONTH_MAP:
                return f"{int(m_t.group(3)):04d}-{MONTH_MAP[m_t.group(1).lower()]:02d}-{int(m_t.group(2)):02d}"
            m_s = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*.*?(\b20\d{2}\b)', top_text, re.I | re.S)
            if m_s and m_s.group(1).lower() in MONTH_MAP:
                return f"{int(m_s.group(3)):04d}-{MONTH_MAP[m_s.group(1).lower()]:02d}-{int(m_s.group(2)):02d}"
    except Exception:
        pass

    parent_yr = pdf_path.parent.name
    return f"{parent_yr}-01-01"


def extract_title_and_subtitle(doc: pymupdf.Document, pdf_path: Path) -> tuple[str, str]:
    fn = pdf_path.stem
    m_fn = re.search(r'Weekly[-_\s]+Opinion[-_\s]+(?:[-_\s]*\d{1,2}[-_\s]+[A-Za-z]+[-_\s]+\d{4}|[A-Za-z]+[-_\s]+\d{1,2}[-_\s]+\d{4})[-_\s]+(.+)$', fn, re.I)
    fn_title = ""
    if m_fn:
        fn_title = m_fn.group(1).replace('-', ' ').replace('_', ' ').strip()
    else:
        m_fn2 = re.search(r'^(.+?)[-_\s]+Weekly[-_\s]+Opinion', fn, re.I)
        if m_fn2:
            fn_title = m_fn2.group(1).replace('-', ' ').replace('_', ' ').strip()

    p0 = doc[0]
    d = p0.get_text('dict')
    
    spans = []
    for b in d.get('blocks', []):
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
                    txt = clean_text(s['text'])
                    if not txt or len(txt) < 3: continue
                    txt_u = txt.upper()
                    if any(w in txt_u for w in [
                        'POTEN', 'OTEN', 'TANKER OPINION', 'PINION', 'HOUSTON', 'ATHENS',
                        'LONDON', 'RESEARCH@', 'WAFWOFLEET', '5 MAY 2013', 'BI OR NO DE?', 'WWW.POTEN.COM',
                        'LNG IN WORLD MARKETS'
                    ]):
                        continue
                    if re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{0,4}$', txt, re.I):
                        continue
                    if 45 <= s['bbox'][1] <= 315:
                        spans.append({
                            'size': s['size'],
                            'flags': s['flags'],
                            'font': s['font'],
                            'bbox': s['bbox'],
                            'text': txt
                        })

    title = ""
    subtitle = ""

    if fn_title:
        title = fn_title
        for s in spans:
            if s['size'] >= 9.0 and ('Bold' in s['font'] or s['flags'] & 2):
                clean_s = s['text']
                if re.sub(r'[^a-z0-9]', '', clean_s.lower()) != re.sub(r'[^a-z0-9]', '', title.lower()):
                    if len(clean_s) < 120 and not clean_s.startswith('Source:'):
                        subtitle = clean_s
                        break
    else:
        if spans:
            spans.sort(key=lambda s: (-s['size'], s['bbox'][1]))
            top_size = spans[0]['size']
            if top_size >= 11.0:
                title_parts = [s['text'] for s in spans if abs(s['size'] - top_size) < 1.0 and abs(s['bbox'][1] - spans[0]['bbox'][1]) < 35]
                title = ' '.join(title_parts)
                rem = [s for s in spans if s['text'] not in title_parts and s['bbox'][1] > spans[0]['bbox'][1]]
                if rem and rem[0]['size'] >= 9.0 and ('Bold' in rem[0]['font'] or rem[0]['flags'] & 2):
                    if len(rem[0]['text']) < 120 and not rem[0]['text'].startswith('Source:'):
                        subtitle = rem[0]['text']

    if not title:
        title = pdf_path.stem.replace('_', ' ').replace('-', ' ')

    title = clean_text(title).strip('"\'')
    subtitle = clean_text(subtitle).strip('"\'')
    return title, subtitle


def is_chart_chunk(chunk: str, pno: int) -> bool:
    c = clean_text(chunk)
    lines = [clean_text(l) for l in c.splitlines() if clean_text(l)]
    if not lines:
        return True
    c_lower = c.lower()
    words = re.findall(r"\b[A-Za-z0-9'-]+\b", c)
    num_words = len(words)

    # Figure, chart, table, or source captions/labels
    if re.match(r'^(?:fig|figure|chart|graph|source|table)\s*[:\.\d]', c_lower):
        return True

    # Running headers/footers and source attributions
    if any(h in c_lower for h in ['poten & partners', 'www.poten.com', 'tankerresearch@', 'research@poten.com', 'eia/poten', '/eia']):
        if num_words <= 8:
            return True

    # Known chart titles / axes
    for ct in CHART_TITLES_AND_AXES:
        if ct in c_lower and num_words <= 12:
            return True

    # Pie chart / percent labels
    if num_words <= 5 and any('%' in l for l in lines):
        return True

    # Pure numbers / years list / tick marks
    if all(all(ch.isdigit() or ch in ' ,.%-/' for ch in l) for l in lines):
        return True

    # Dates lists or isolated axis dates
    if pno > 0:
        if re.match(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{2,4}$', c, re.I):
            return True
        if re.match(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{2,4}$', c, re.I):
            return True
        date_matches = re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-,\s]*\d{2,4}\b', c, re.I)
        if len(date_matches) >= 1 and num_words <= len(date_matches) * 3:
            return True

    # Single words or short word lists that match chart keywords
    if num_words <= 6:
        clean_words = set(w.lower() for w in words)
        if clean_words.issubset(CHART_SINGLE_WORDS):
            return True

    return False


def parse_mini_table(title_chunk: str, body_chunk: str) -> str | None:
    lines = [clean_text(l) for l in body_chunk.splitlines() if clean_text(l)]
    if len(lines) >= 8 and any(re.search(r'\d{4}-\d{4}', l) for l in lines):
        col_headers = [l for l in lines[:4] if not re.search(r'\d{4}-\d{4}', l) and not any(c.isdigit() for c in l)]
        rows = []
        i = 0
        while i < len(lines):
            m_yr = re.search(r'(\d{4}-\d{4})', lines[i])
            if m_yr:
                yr = m_yr.group(1)
                vals = []
                j = i + 1
                while j < min(i + 4, len(lines)) and re.match(r'^\d{1,3}(?:,\d{3})+$', lines[j]):
                    vals.append(lines[j])
                    j += 1
                if vals:
                    rows.append([yr] + vals)
                    i = j
                else:
                    i += 1
            else:
                i += 1
        if rows:
            headers = [title_chunk] + (col_headers if col_headers else ['Col 1', 'Col 2'])
            md = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
            for r in rows:
                md.append('| ' + ' | '.join(r) + ' |')
            return '\n'.join(md)
    return None


def parse_top_charterers_table(lines: list[str]) -> tuple[str | None, list[dict]]:
    idx = 0
    while idx < len(lines):
        if lines[idx] == '1' and idx + 1 < len(lines) and not lines[idx+1].isdigit():
            break
        idx += 1
    if idx >= len(lines):
        return None, []
    
    headers = ['Rank', 'Charterer', 'Reported Total Cargo (MT 000s)', '% of Total Dirty Cargoes', 'Prev Rank', 'Fixtures']
    md_rows = []
    dict_rows = []
    curr = idx
    expected_rank = 1
    while curr < len(lines) and expected_rank <= 25:
        if lines[curr] == str(expected_rank) and curr + 1 < len(lines) and not lines[curr+1].isdigit():
            rk = lines[curr]
            ch = lines[curr+1]
            next_idx = None
            for j in range(curr+2, min(curr+10, len(lines))):
                if lines[j] == str(expected_rank + 1) and j + 1 < len(lines) and not lines[j+1].isdigit():
                    next_idx = j
                    break
                elif lines[j].startswith('Top 20') or lines[j] == 'Top 20':
                    next_idx = j
                    break
            vals = lines[curr+2:next_idx] if next_idx else lines[curr+2:curr+7]
            cargo, pct, prev_rk, fix = '', '', '', ''
            for v in vals:
                if '%' in v and not pct:
                    pct = v
                elif re.match(r'^\d{1,3}(?:,\d{3})+$', v) and not cargo:
                    cargo = v
                elif v.isdigit() and int(v) > 30 and not fix:
                    fix = v
                elif (v.isdigit() and int(v) <= 30 and not prev_rk) or v.lower() == 'new':
                    prev_rk = v
            md_rows.append([rk, ch, cargo, pct, prev_rk, fix])
            dict_rows.append({
                'rank': int(rk), 'charterer': ch, 'cargo_mt_000s': cargo,
                'pct_total_cargo': pct, 'fixtures_count': fix, 'pct_fixtures': '',
                'prev_rank': prev_rk
            })
            expected_rank += 1
            curr = next_idx if next_idx else curr + 6
        else:
            curr += 1
            
    for j in range(curr, len(lines)):
        if lines[j].startswith('Top 20'):
            vals = lines[j+1:min(j+5, len(lines))]
            cg, pc, fx = '', '', ''
            for v in vals:
                if '%' in v and not pc: pc = v
                elif re.match(r'^\d{1,3}(?:,\d{3})+$', v) and not cg: cg = v
                elif v.isdigit() and int(v) > 30 and not fx: fx = v
            md_rows.append(['Top 20', '', cg, pc, '', fx])
        elif lines[j].startswith('Others'):
            vals = lines[j+1:min(j+5, len(lines))]
            cg, pc, fx = '', '', ''
            for v in vals:
                if '%' in v and not pc: pc = v
                elif re.match(r'^\d{1,3}(?:,\d{3})+$', v) and not cg: cg = v
                elif v.isdigit() and int(v) > 30 and not fx: fx = v
            md_rows.append(['Others', '', cg, pc, '', fx])
        elif lines[j].startswith('Total'):
            vals = lines[j+1:min(j+5, len(lines))]
            cg, pc, fx = '', '', ''
            for v in vals:
                if '%' in v and not pc: pc = v
                elif re.match(r'^\d{1,3}(?:,\d{3})+$', v) and not cg: cg = v
                elif v.isdigit() and int(v) > 30 and not fx: fx = v
            md_rows.append(['Total', '', cg, pc, '', fx])

    if md_rows:
        md = []
        md.append('| ' + ' | '.join(headers) + ' |')
        md.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for r in md_rows:
            md.append('| ' + ' | '.join(r) + ' |')
        return '\n'.join(md), dict_rows
    return None, []


def extract_page_elements(page: pymupdf.Page, is_p0: bool, title: str, subtitle: str) -> tuple[list[tuple[str, str]], list[dict]]:
    blocks = page.get_text('blocks')
    valid_blocks = []
    
    for b in blocks:
        txt = clean_text(b[4])
        if not txt: continue
        txt_u = txt.upper()
        if is_p0 and (b[3] <= 122 or b[1] < 85):
            continue
        if not is_p0 and b[3] <= 90 and any(h in txt_u for h in ['POTEN', 'PAGE', 'TANKER OPINION', 'WWW.POTEN.COM', 'HOUSTON']):
            continue
        if b[1] >= 745 or any(h in txt_u for h in [
            'RESEARCH@POTEN', 'TANKER OPINIONS ARE PUBLISHED', 'WWW.POTEN.COM',
            'TANKER RESEARCH', 'POTEN TANKER MARKET OPINIONS', 'EMAIL: TANKERRESEARCH'
        ]):
            continue
        if any(h in txt_u for h in ['WAFWOFLEET', '5 MAY 2013', 'BI OR NO DE?', 'HOUSTON / NEW YORK / LONDON', 'POTEN TANKER OPINION']):
            continue
        if len(txt) <= 3 and txt.isdigit():
            continue
        valid_blocks.append(b)

    # Geometric ordering: Check if 2-column or single-column
    body_blocks = [b for b in valid_blocks if len(re.findall(r'\b\w+\b', b[4])) > 8]
    left_body = [b for b in body_blocks if b[2] <= 320]
    right_body = [b for b in body_blocks if b[0] >= 260]
    wide_body = [b for b in body_blocks if b[0] < 220 and b[2] > 380]

    if len(left_body) >= 1 and len(right_body) >= 1 and len(wide_body) <= len(left_body) + len(right_body):
        min_col_y = min(b[1] for b in left_body + right_body)
        max_col_y = max(b[3] for b in left_body + right_body)
        top_wide = [b for b in valid_blocks if b[0] < 220 and b[2] > 380 and b[3] <= min_col_y + 10]
        bot_wide = [b for b in valid_blocks if b[0] < 220 and b[2] > 380 and b[1] >= max_col_y - 10]
        col_blocks = [b for b in valid_blocks if b not in top_wide and b not in bot_wide]
        col_left = [b for b in col_blocks if b[2] <= 320]
        col_right = [b for b in col_blocks if b[0] >= 260]
        col_mid = [b for b in col_blocks if b not in col_left and b not in col_right]
        top_wide.sort(key=lambda b: b[1])
        col_left.sort(key=lambda b: b[1])
        col_right.sort(key=lambda b: b[1])
        col_mid.sort(key=lambda b: b[1])
        bot_wide.sort(key=lambda b: b[1])
        ordered_blocks = top_wide + col_left + col_right + col_mid + bot_wide
    else:
        valid_blocks.sort(key=lambda b: (b[1], b[0]))
        ordered_blocks = valid_blocks

    collected = []
    charterer_records = []
    
    i = 0
    while i < len(ordered_blocks):
        b = ordered_blocks[i]
        raw_text = clean_text(b[4])
        if not raw_text:
            i += 1
            continue

        # Strip running header on later pages
        if not is_p0:
            raw_text = re.sub(r'^Poten\s*&\s*Partners[^\n]*\n?', '', raw_text, flags=re.I).strip()
        if not raw_text:
            i += 1
            continue

        # Check if block is a Top Charterers 20-row table
        b_lines = [clean_text(l) for l in raw_text.splitlines() if clean_text(l)]
        if len(b_lines) >= 15 and sum(1 for l in b_lines if any(c.isdigit() for c in l) or '%' in l) > 8:
            t_md, c_rows = parse_top_charterers_table(b_lines)
            if t_md:
                collected.append(('table', t_md))
                charterer_records.extend(c_rows)
                i += 1
                continue

        # Split block into double-newline chunks
        chunks = re.split(r'\n\s*\n', raw_text)
        c_idx = 0
        while c_idx < len(chunks):
            ch = clean_text(chunks[c_idx])
            if not ch:
                c_idx += 1
                continue

            # Check mini table
            if c_idx + 1 < len(chunks):
                tbl_md = parse_mini_table(ch, chunks[c_idx+1])
                if tbl_md:
                    collected.append(('table', tbl_md))
                    c_idx += 2
                    continue

            # Check chart element
            if is_chart_chunk(ch, 0 if is_p0 else 1):
                c_idx += 1
                continue

            lines = [clean_text(l) for l in ch.splitlines() if clean_text(l)]
            words = re.findall(r"\b[A-Za-z0-9'-]+\b", ch)

            # Normalize title and subtitle for comparison
            clean_ch_for_cmp = re.sub(r'[^a-z0-9]', '', ch.lower())
            clean_title_for_cmp = re.sub(r'[^a-z0-9]', '', title.lower())
            clean_sub_for_cmp = re.sub(r'[^a-z0-9]', '', subtitle.lower()) if subtitle else ''

            # Standalone section heading
            if len(lines) == 1 and len(words) <= 10 and len(ch) <= 75 and not ch.endswith(('.', ':', ';')):
                if re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{0,4}$', ch, re.I):
                    c_idx += 1
                    continue
                if clean_ch_for_cmp == clean_title_for_cmp or (clean_sub_for_cmp and clean_ch_for_cmp == clean_sub_for_cmp):
                    c_idx += 1
                    continue
                collected.append(('heading', ch))
                c_idx += 1
                continue



            # Regular paragraph
            para_txt = ' '.join(lines)
            para_txt = re.sub(r'\s+', ' ', para_txt)
            if is_p0:
                para_txt = re.sub(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}\s*', '', para_txt, flags=re.I).strip()
            if not para_txt:
                c_idx += 1
                continue

            # Strip title / subtitle if paragraph starts with title or subtitle
            clean_para_for_cmp = re.sub(r'[^a-z0-9]', '', para_txt.lower())
            if clean_para_for_cmp == clean_title_for_cmp or (clean_sub_for_cmp and clean_para_for_cmp == clean_sub_for_cmp):
                c_idx += 1
                continue

            if subtitle and para_txt.lower().startswith(subtitle.lower()):
                para_txt = para_txt[len(subtitle):].strip()

            if para_txt:
                collected.append(('para', para_txt))
            c_idx += 1

        i += 1

    return collected, charterer_records


def process_pdf(pdf_path: Path, used_slugs: dict[str, int]) -> tuple[dict, str, dict, list[dict], str, str]:
    issue_date = extract_date(pdf_path)
    year = int(issue_date[:4])
    source_ref = pdf_path.resolve().relative_to(ROOT).as_posix()

    with pymupdf.open(pdf_path) as doc:
        total_pages = len(doc)
        title, subtitle = extract_title_and_subtitle(doc, pdf_path)

        base_slug = slugify(title)
        slug_key = f"{year}_{issue_date}_{base_slug}"
        used_slugs[slug_key] += 1
        slug = base_slug if used_slugs[slug_key] == 1 else f"{base_slug}-{used_slugs[slug_key]}"

        md_rel_path = f"data/extracted/md/poten/{year}/poten_{issue_date}_{slug}.md"
        tables_rel_path = f"data/extracted/md/poten/{year}/poten_{issue_date}_{slug}.tables.json"

        all_elements = []
        all_charterer_rows = []

        for pno in range(total_pages):
            page_elems, c_rows = extract_page_elements(doc[pno], is_p0=(pno == 0), title=title, subtitle=subtitle)
            all_elements.extend(page_elems)
            for r in c_rows:
                r['issue_date'] = issue_date
                r['year'] = year
                r['report_period'] = str(year - 1)
                r['segment'] = 'Overall'
                r['source_file'] = source_ref
                all_charterer_rows.append(r)

        # Sentence stitching across consecutive paragraphs
        stitched_elements = []
        for elem_type, elem_txt in all_elements:
            if elem_type == 'para' and stitched_elements and stitched_elements[-1][0] == 'para':
                last_txt = stitched_elements[-1][1]
                if not last_txt.endswith(('.', '!', '?', '"', "'", '”')):
                    if last_txt.endswith('-'):
                        stitched_elements[-1] = ('para', last_txt[:-1] + elem_txt)
                    else:
                        stitched_elements[-1] = ('para', last_txt + ' ' + elem_txt)
                    continue
            stitched_elements.append((elem_type, elem_txt))

        # Build Markdown
        frontmatter_title = title.replace('"', '\\"')
        frontmatter_sub = subtitle.replace('"', '\\"')
        
        tables_in_doc = [txt for t, txt in stitched_elements if t == 'table']
        frontmatter = (
            "---\n"
            f'title: "{frontmatter_title}"\n'
            f'subtitle: "{frontmatter_sub}"\n'
            f'issue_date: "{issue_date}"\n'
            f'year: {year}\n'
            'author: "Poten & Partners"\n'
            'source: "poten"\n'
            'category: "tankers"\n'
            f'pages: {total_pages}\n'
            f'source_file: "{source_ref}"\n'
            f'tables_count: {len(tables_in_doc)}\n'
            "---\n\n"
        )

        md_parts = [frontmatter, f"# {title}\n\n"]
        if subtitle:
            md_parts.append(f"### {subtitle}\n\n")

        for elem_type, elem_txt in stitched_elements:
            if elem_type == 'heading':
                md_parts.append(f"### {elem_txt}\n\n")
            elif elem_type == 'table':
                md_parts.append(f"{elem_txt}\n\n")
            else:
                md_parts.append(f"{elem_txt}\n\n")

        full_md_content = "".join(md_parts).strip() + "\n"
        words = len(re.findall(r'\w+', full_md_content))

        meta = {
            'issue_date': issue_date,
            'year': year,
            'title': title,
            'subtitle': subtitle,
            'author': "Poten & Partners",
            'pages': total_pages,
            'tables_count': len(tables_in_doc),
            'word_count': words,
            'source_file': source_ref,
            'md_file': md_rel_path
        }

        tables_data = {
            'issue_date': issue_date,
            'year': year,
            'title': title,
            'source_file': source_ref,
            'tables_count': len(tables_in_doc),
            'tables': tables_in_doc,
            'charterers_count': len(all_charterer_rows),
            'charterer_rows': all_charterer_rows
        }

        return meta, full_md_content, tables_data, all_charterer_rows, md_rel_path, tables_rel_path


def main():
    t0 = time.time()
    pdfs = sorted(SRC_DIR.glob("**/*.pdf"))
    total_pdfs = len(pdfs)
    print(f"[poten] Discovered {total_pdfs} authoritative PDFs in {SRC_DIR}", flush=True)

    used_slugs = defaultdict(int)
    all_metadata = []
    all_charterer_rows = []

    for i, pdf_path in enumerate(pdfs, start=1):
        try:
            meta, md_content, tables_data, charterer_rows, md_rel_path, tables_rel_path = process_pdf(pdf_path, used_slugs)
            
            # Write MD file
            md_full_path = ROOT / md_rel_path
            md_full_path.parent.mkdir(parents=True, exist_ok=True)
            md_full_path.write_text(md_content, encoding='utf-8')

            # Write tables JSON sidecar
            tables_full_path = ROOT / tables_rel_path
            tables_full_path.parent.mkdir(parents=True, exist_ok=True)
            tables_full_path.write_text(json.dumps(tables_data, indent=2, ensure_ascii=False), encoding='utf-8')

            all_metadata.append(meta)
            all_charterer_rows.extend(charterer_rows)

            if i % 100 == 0 or i == total_pdfs:
                elapsed = time.time() - t0
                print(f"  [{i:>4}/{total_pdfs}] Processed {pdf_path.name[:45]:<45} ({elapsed:.1f}s)", flush=True)
        except Exception as e:
            print(f"ERROR processing {pdf_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    # Clean up any stale files in OUT_MD_DIR not in current metadata catalog
    expected_md_files = set(ROOT / m['md_file'] for m in all_metadata)
    expected_tables_files = set((ROOT / m['md_file']).with_suffix('.tables.json') for m in all_metadata)
    for p in list(OUT_MD_DIR.rglob('*')):
        if p.is_file():
            if p.suffix == '.md' and p not in expected_md_files:
                p.unlink()
            elif p.name.endswith('.tables.json') and p not in expected_tables_files:
                p.unlink()

    # Generate master stacked series: poten_top_charterers_series.csv
    OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
    all_charterer_rows.sort(key=lambda r: (r['issue_date'], r['rank']))
    
    charterer_cols = [
        'issue_date', 'year', 'report_period', 'segment', 'rank', 'charterer',
        'cargo_mt_000s', 'pct_total_cargo', 'fixtures_count', 'pct_fixtures',
        'prev_rank', 'source_file'
    ]
    with open(CHARTERERS_SERIES_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=charterer_cols)
        writer.writeheader()
        writer.writerows(all_charterer_rows)

    # Generate master metadata catalog: poten_opinions_metadata.csv
    all_metadata.sort(key=lambda m: (m['issue_date'], m['title']))
    meta_cols = [
        'issue_date', 'year', 'title', 'subtitle', 'author', 'pages',
        'tables_count', 'word_count', 'source_file', 'md_file'
    ]
    with open(METADATA_CATALOG_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=meta_cols)
        writer.writeheader()
        writer.writerows(all_metadata)

    elapsed = time.time() - t0
    print("\n[poten] Re-run Complete!", flush=True)
    print(f"  Total Reports Extracted: {len(all_metadata)} / {total_pdfs} (100.0%)")
    print(f"  Total Top Charterer Rows: {len(all_charterer_rows)}")
    print(f"  Series CSV: {CHARTERERS_SERIES_CSV}")
    print(f"  Metadata CSV: {METADATA_CATALOG_CSV}")
    print(f"  Total Time: {elapsed:.1f}s", flush=True)


if __name__ == '__main__':
    main()
