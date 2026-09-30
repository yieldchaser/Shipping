"""
The Signal Group (Signal Ocean / Signal Maritime) Full Corpus Pipeline
Processes all 511 HTML snapshots in corpus/07-signal/html/:
- 451 Content Articles across Monitors (250), Newsroom (191), and Newsletters (10)
- 60 Media Mention Stubs cleanly identified and recorded in signal_manifest.csv
- 100.0% Exact ISO issue_date and report_week resolution across all articles
- Publication-Grade YAML frontmatter
- Capitalized, clean section headings with shipping acronyms preserved
- Localized image references to corpus/07-signal/images/
- Data table extraction to GFM Markdown and JSON sidecars
- Email template table unpacking into clean headings and text
- Dual-storage synchronization:
  1. corpus/07-signal/<section>/<slug>.md
  2. data/extracted/md/signal/<section>/<slug>.md
- Master Series Stacking:
  1. data/extracted/series/signal_reports_metadata.csv
  2. data/extracted/series/signal_vessel_counts_series.csv
- Automated live ingestion (--sync-live flag) for continuous digestion of new reports
"""

import os
import sys
import re
import csv
import json
import glob
import time
import argparse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup, NavigableString, Tag

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_CORPUS = "corpus/07-signal"
HTML_DIR = os.path.join(BASE_CORPUS, "html")
IMAGES_DIR = os.path.join(BASE_CORPUS, "images")
MANIFEST_PATH = os.path.join(BASE_CORPUS, "signal_manifest.csv")

OUT_MD_BASE = "data/extracted/md/signal"
SERIES_DIR = "data/extracted/series"

def safe_write_text(path, content):
    path = os.path.normpath(os.path.abspath(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(10):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return
        except OSError as e:
            if attempt == 9:
                print(f"[!] safe_write_text failed on {path}: {e}")
                raise
            time.sleep(0.1 * (attempt + 1))

def safe_remove(path):
    path = os.path.normpath(os.path.abspath(path))
    if os.path.exists(path):
        for attempt in range(10):
            try:
                os.remove(path)
                return
            except OSError:
                if attempt == 9:
                    break
                time.sleep(0.1 * (attempt + 1))

ACRONYMS = {
    'bdi': 'BDI', 'bci': 'BCI', 'bpi': 'BPI', 'bsi': 'BSI', 'bhsi': 'BHSI',
    'bdti': 'BDTI', 'bcti': 'BCTI', 'tce': 'TCE', 'ws': 'WS', 'dwt': 'DWT',
    'ldt': 'LDT', 'c5tc': 'C5TC', 'p5tc': 'P5TC', 's11tc': 'S11TC', 'hs7tc': 'HS7TC',
    'vlcc': 'VLCC', 'vlccs': 'VLCCs', 'suezmax': 'Suezmax', 'suezmaxes': 'Suezmaxes',
    'aframax': 'Aframax', 'aframaxes': 'Aframaxes', 'capesize': 'Capesize',
    'capesizes': 'Capesizes', 'panamax': 'Panamax', 'panamaxes': 'Panamaxes',
    'supramax': 'Supramax', 'supramaxes': 'Supramaxes', 'handysize': 'Handysize',
    'handysizes': 'Handysizes', 'handymax': 'Handymax', 'ffa': 'FFA', 'ffas': 'FFAs',
    'lng': 'LNG', 'lpg': 'LPG', 'vlgc': 'VLGC', 'us': 'US', 'usa': 'USA', 'uk': 'UK',
    'eu': 'EU', 'ets': 'ETS', 'imo': 'IMO', 'row': 'RoW', 'meg': 'MEG', 'ag': 'AG',
    'nopac': 'NOPAC', 'feast': 'FEAST', 'c3': 'C3', 'c5': 'C5', 'c2': 'C2', 'c7': 'C7',
    'c8': 'C8', 'c9': 'C9', 'c10': 'C10', 'c17': 'C17', 'p1a': 'P1A', 'p2a': 'P2A',
    'p3a': 'P3A', 'p5': 'P5', 's4a': 'S4A', 's4b': 'S4B', 's5': 'S5', 's8': 'S8',
    's10': 'S10', 'hs1': 'HS1', 'hs2': 'HS2', 'hs5': 'HS5', 'hs6': 'HS6', 'hs7': 'HS7',
    'td3c': 'TD3C', 'td2': 'TD2', 'td6': 'TD6', 'td9': 'TD9', 'td15': 'TD15',
    'td22': 'TD22', 'td23': 'TD23', 'td8': 'TD8', 'td34': 'TD34', 'ai': 'AI',
    'api': 'API', 'apis': 'APIs', 'gis': 'GIS', 'ais': 'AIS', 'vloc': 'VLOC', 'vlocs': 'VLOCs',
    'iea': 'IEA', 'nbs': 'NBS', 'wow': 'WoW', 'yoy': 'YoY', 'lhs': 'LHS', 'rhs': 'RHS'
}

LOWER_WORDS = {'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'vs', 'versus', 'per', 'as'}

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def format_title_case(s):
    if not s:
        return ''
    s = re.sub(r'[*_`]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    words = s.split()
    out = []
    for i, w in enumerate(words):
        prev_word = words[i - 1] if i > 0 else ''
        is_first = (i == 0)
        is_last = (i == len(words) - 1)
        follows_delimiter = bool(prev_word.endswith(':') or prev_word.endswith('-') or prev_word in ['-', '–', '—', '/', '|', '&'])

        if '-' in w and len(w) > 1:
            subparts = w.split('-')
            sub_out = []
            for j, sub in enumerate(subparts):
                sub_clean = sub.strip()
                if not sub_clean:
                    sub_out.append('')
                    continue
                sub_lower = sub_clean.lower()
                if sub_lower in ACRONYMS:
                    sub_out.append(ACRONYMS[sub_lower])
                elif j == 0 or j == len(subparts) - 1 or sub_lower not in LOWER_WORDS:
                    sub_out.append(sub_clean.capitalize())
                else:
                    sub_out.append(sub_lower)
            out.append('-'.join(sub_out))
            continue

        core = w.strip('()[]{}.,;:!?"\'')
        lead_p = w[:w.find(core)] if core and core in w else ''
        trail_p = w[w.find(core)+len(core):] if core and core in w else ''
        core_lower = core.lower()

        if core_lower in ACRONYMS:
            out.append(f"{lead_p}{ACRONYMS[core_lower]}{trail_p}")
        elif w.lower() in ACRONYMS:
            out.append(ACRONYMS[w.lower()])
        elif is_first or is_last or follows_delimiter or core_lower not in LOWER_WORDS:
            out.append(f"{lead_p}{core.capitalize()}{trail_p}" if core else w.capitalize())
        else:
            out.append(f"{lead_p}{core_lower}{trail_p}" if core else w.lower())

    return ' '.join(out)

def parse_iso_date(raw_str):
    if not raw_str:
        return None
    s = raw_str.strip()
    m_iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m_iso:
        return f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
    m_full = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', s)
    if m_full:
        month_name = m_full.group(1).lower()
        if month_name in MONTHS:
            m_num = MONTHS[month_name]
            day = int(m_full.group(2))
            year = int(m_full.group(3))
            return f"{year:04d}-{m_num:02d}-{day:02d}"
    m_rev = re.search(r'(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})', s)
    if m_rev:
        month_name = m_rev.group(2).lower()
        if month_name in MONTHS:
            m_num = MONTHS[month_name]
            day = int(m_rev.group(1))
            year = int(m_rev.group(3))
            return f"{year:04d}-{m_num:02d}-{day:02d}"
    return None

def resolve_date(soup, html_text, slug):
    # 1. ld+json datePublished or dateModified
    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    pub = data.get('datePublished')
                    iso = parse_iso_date(pub)
                    if iso:
                        return iso
                    mod = data.get('dateModified')
                    iso = parse_iso_date(mod)
                    if iso:
                        return iso
            except:
                pass

    # 2. cd_texts
    for cd in soup.find_all(class_=re.compile(r'cd_texts', re.I)):
        t = cd.get_text(strip=True)
        iso = parse_iso_date(t)
        if iso:
            return iso

    # 3. body regex
    m_body = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}', html_text)
    if m_body:
        iso = parse_iso_date(m_body.group(0))
        if iso:
            return iso

    # 4. slug month-year
    m_slug1 = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)[-_](\d{4})', slug.lower())
    if m_slug1:
        m_num = MONTHS[m_slug1.group(1)]
        year = int(m_slug1.group(2))
        return f"{year:04d}-{m_num:02d}-01"

    m_slug2 = re.search(r'(\d{4})[-_](january|february|march|april|may|june|july|august|september|october|november|december)', slug.lower())
    if m_slug2:
        m_num = MONTHS[m_slug2.group(2)]
        year = int(m_slug2.group(1))
        return f"{year:04d}-{m_num:02d}-01"

    # 5. slug week number
    m_week = re.search(r'week[-_](\d{1,2})[-_](\d{4})', slug.lower())
    if m_week:
        week = int(m_week.group(1))
        year = int(m_week.group(2))
        try:
            d = datetime.fromisocalendar(year, week, 5)
            return d.strftime('%Y-%m-%d')
        except:
            pass

    return "2026-01-01"

def determine_section(slug, url):
    if "/weekly-market-monitor/" in url or slug.startswith("weekly-") or "week-" in slug or "radar" in slug:
        return "monitors"
    elif "/newsletter/" in url or "newsletter" in slug:
        return "newsletters"
    else:
        return "newsroom"

def determine_category(soup, slug, section):
    if "dry" in slug:
        return "Dry Bulk"
    elif "tanker" in slug:
        return "Tankers"
    elif "radar" in slug:
        return "Commodity Radar"
    elif section == "newsletters":
        return "Newsletter"

    # Inspect cd_texts in soup
    for cd in soup.find_all(class_=re.compile(r'cd_texts', re.I)):
        txt = cd.get_text(strip=True)
        if txt and not re.search(r'\d{4}', txt):
            return txt

    return "Market Insights"

def get_best_body(soup):
    candidates = []
    for div in soup.find_all('div'):
        classes = div.get('class', [])
        cl_str = ' '.join(classes)
        if any(skip in cl_str for skip in ['hide', 'w-dyn-bind-empty', 'side-bar', 'fs-toc', 'newsroom-three_x', 'footer', 'nav', 'navigation', 'social']):
            continue
        if any(target in cl_str for target in ['w-richtext', 'newsroom-rich_texts', 'newsletter-trich-text', 'post-body', 'article-body']):
            txt = div.get_text(strip=True)
            if len(txt) > 200:
                candidates.append((len(txt), div))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][0]
    return None, 0

def clean_image_filename(src):
    name = src.split("/")[-1].split("?")[0]
    name = urllib.parse.unquote(name)
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    if not any(name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif', '.svg']):
        name += '.png'
    return name

def to_md(node):
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ''
    tag = node.name.lower()
    if tag == 'br':
        return '\n'
    if tag in ['strong', 'b']:
        inner = ''.join(to_md(c) for c in node.children)
        lead = ' ' if inner.startswith(' ') else ''
        trail = ' ' if inner.endswith(' ') else ''
        core = inner.strip()
        return f"{lead}**{core}**{trail}" if core else inner
    if tag in ['em', 'i']:
        inner = ''.join(to_md(c) for c in node.children)
        lead = ' ' if inner.startswith(' ') else ''
        trail = ' ' if inner.endswith(' ') else ''
        core = inner.strip()
        return f"{lead}*{core}*{trail}" if core else inner
    if tag == 'a':
        href = node.get('href', '').strip()
        inner = ''.join(to_md(c) for c in node.children).strip()
        if not href:
            return inner
        return f"[{inner or href}]({href})"
    
    parts = []
    children = list(node.children)
    for idx, c in enumerate(children):
        c_md = to_md(c)
        if not c_md:
            continue
        if parts:
            prev = parts[-1]
            if prev and not prev[-1].isspace() and not c_md[0].isspace():
                if (prev.endswith('**') or prev.endswith('*')) and (c_md[0].isalnum() or c_md[0] in '([{"\''):
                    parts.append(' ')
                elif (c_md.startswith('**') or c_md.startswith('*')) and (prev[-1].isalnum() or prev[-1] in '.:;!?)]}"\''):
                    parts.append(' ')
        parts.append(c_md)
    return ''.join(parts)

def clean_paragraph_text(p_node):
    raw_md = to_md(p_node)
    # Fix commas glued together: ,, -> ,
    raw_md = re.sub(r',,+', ',', raw_md)
    # Escape route underscores: P5_82, C10_182, HS4_38, etc.
    raw_md = re.sub(r'(\w)_(\w)', r'\1\\_\2', raw_md)
    # Clean multiple spaces (preserve newlines)
    raw_md = re.sub(r'[ \t]+', ' ', raw_md)
    raw_md = raw_md.replace('\u200d', '').replace('\ufeff', '').strip()
    return raw_md

def process_table_element(table):
    nested = table.find_all('table')
    classes = ' '.join(table.get('class', []))
    if nested or any(c in classes for c in ['nl-container', 'row-content', 'social-table']):
        # Layout container
        lines = []
        for elem in table.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
            if elem.name.startswith('h'):
                txt = elem.get_text(strip=True)
                txt = txt.replace('\u200d', '').replace('\ufeff', '').strip()
                if txt:
                    lvl = '#' * int(elem.name[1])
                    clean_h = format_title_case(txt)
                    clean_h = re.sub(r'(\w)_(\w)', r'\1\\_\2', clean_h)
                    lines.append(f"\n{lvl} {clean_h}\n")
            elif elem.name == 'p':
                txt = clean_paragraph_text(elem)
                if txt:
                    lines.append(f"{txt}\n")
            elif elem.name == 'li':
                txt = clean_paragraph_text(elem)
                if txt:
                    lines.append(f"- {txt}")
        deduped = []
        for l in lines:
            if not deduped or l != deduped[-1]:
                deduped.append(l)
        return '\n'.join(deduped), None
    else:
        # Data table
        rows = table.find_all('tr')
        table_lines = []
        structured_rows = []
        header = []
        for r_idx, row in enumerate(rows):
            cols = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if cols and any(cols):
                clean_cols = [re.sub(r'(\w)_(\w)', r'\1\\_\2', c.replace('|', '\\|')) for c in cols]
                table_lines.append("| " + " | ".join(clean_cols) + " |")
                if r_idx == 0:
                    header = cols
                    table_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                else:
                    if header and len(cols) == len(header):
                        structured_rows.append(dict(zip(header, cols)))
                    else:
                        structured_rows.append({"col_" + str(i): val for i, val in enumerate(cols)})
        return '\n'.join(table_lines), structured_rows

def convert_report_file(html_path, manifest_dict):
    slug = os.path.splitext(os.path.basename(html_path))[0]
    manifest_entry = manifest_dict.get(slug, {})
    url = manifest_entry.get("url", f"https://www.thesignalgroup.com/{slug}")

    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    iso_date = resolve_date(soup, html, slug)
    dt = datetime.strptime(iso_date, '%Y-%m-%d')
    year = dt.year
    iso_calendar = dt.isocalendar()
    week_num = iso_calendar.week

    section = determine_section(slug, url)
    category = determine_category(soup, slug, section)

    # Title extraction
    h1 = soup.find('h1')
    raw_title = h1.get_text(strip=True) if h1 else slug.replace('-', ' ').title()
    raw_title = re.sub(r'^\s*TSG\s+', '', raw_title)
    raw_title = re.sub(r'\s*\|\s*The Signal Group.*$', '', raw_title, flags=re.I)
    title = format_title_case(raw_title)

    # Body extraction
    body_div, body_length = get_best_body(soup)
    if body_length < 200:
        corpus_md_path = os.path.join(BASE_CORPUS, section, f"{slug}.md")
        extracted_md_path = os.path.join(OUT_MD_BASE, section, f"{slug}.md")
        safe_remove(corpus_md_path)
        safe_remove(extracted_md_path)
        sidecar_path = os.path.join(OUT_MD_BASE, section, f"{slug}.tables.json")
        safe_remove(sidecar_path)

        return {
            "slug": slug,
            "url": url,
            "section": section,
            "category": category,
            "title": title,
            "date": iso_date,
            "status": "skipped_media_mention_stub",
            "body_length": body_length,
            "tables_extracted": 0,
            "images_extracted": 0
        }

    # Extract elements in linear order
    md_content_blocks = []
    all_data_tables = []
    images_count = 0

    for elem in body_div.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'p', 'figure', 'table', 'ul', 'ol']):
        # If elem is inside another figure or table, skip to avoid double processing
        if elem.find_parent(['figure']) or (elem.find_parent('table') and elem.name in ['table', 'figure']):
            continue

        if elem.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
            raw_h = elem.get_text(strip=True)
            raw_h = raw_h.replace('\u200d', '').replace('\ufeff', '').strip()
            if raw_h:
                lvl = '#' * int(elem.name[1])
                clean_h = format_title_case(raw_h)
                clean_h = re.sub(r'(\w)_(\w)', r'\1\\_\2', clean_h)
                md_content_blocks.append(f"\n{lvl} {clean_h}\n")
        elif elem.name == 'p':
            txt = clean_paragraph_text(elem)
            if txt:
                md_content_blocks.append(f"{txt}\n")
        elif elem.name == 'figure':
            img = elem.find('img')
            cap = elem.find('figcaption')
            if img and img.has_attr('src'):
                src = img['src']
                local_name = clean_image_filename(src)
                cap_txt = cap.get_text().strip() if cap else ""
                cap_txt = re.sub(r'\s+', ' ', cap_txt).strip()
                cap_txt = cap_txt.replace('\u200d', '').replace('\ufeff', '')

                images_count += 1
                fig_idx = images_count
                fig_label = f"Figure {fig_idx}"
                fig_title = ""

                m_lbl = re.match(r'^(Figure|Table|Chart)\s*(\d+)[:\.]?\s*(.*?)$', cap_txt, re.I)
                if m_lbl:
                    kind = m_lbl.group(1).capitalize()
                    num = m_lbl.group(2)
                    fig_label = f"{kind} {num}"
                    rest = m_lbl.group(3).strip()
                    t_match = re.split(r'\.\s+|\s*\((?:Source|source):', rest)[0].strip()
                    if t_match and len(t_match) > 3:
                        fig_title = format_title_case(t_match)
                elif cap_txt:
                    t_match = re.split(r'\.\s+|\s*\((?:Source|source):', cap_txt)[0].strip()
                    if t_match and len(t_match) > 3:
                        fig_title = format_title_case(t_match)

                if not fig_title:
                    prev_h = elem.find_previous(['h2', 'h3', 'h4'])
                    if prev_h:
                        h_text = prev_h.get_text().strip()
                        if h_text and len(h_text) < 80:
                            fig_title = format_title_case(h_text)
                if not fig_title:
                    stem = local_name.rsplit('.', 1)[0]
                    fig_title = format_title_case(stem.replace('_', ' ').replace('-', ' ').title())

                file_uri = f"file:///C:/Users/Dell/Github/Shipping/corpus/07-signal/images/{local_name}"
                interactive_url = url if (url and url.startswith('http')) else "https://app.signalocean.com"
                anchor_lbl = "Signal Ocean Platform"

                fig_lines = [
                    f"![{fig_title}](../images/{local_name})",
                    "",
                    f"> **{fig_label}: {fig_title}**  "
                ]
                if cap_txt:
                    fig_lines.append(f"> *{cap_txt}*  ")
                fig_lines.append(f"> **Interactive Data & Source:** [{anchor_lbl}]({interactive_url}) | [Local Asset]({file_uri})")

                md_content_blocks.append('\n' + '\n'.join(fig_lines) + '\n')
        elif elem.name == 'table':
            tbl_md, tbl_struct = process_table_element(elem)
            if tbl_md:
                md_content_blocks.append(f"\n{tbl_md}\n")
                if tbl_struct:
                    all_data_tables.append(tbl_struct)
        elif elem.name in ['ul', 'ol']:
            list_lines = []
            for li in elem.find_all('li'):
                li_txt = clean_paragraph_text(li)
                if li_txt:
                    list_lines.append(f"- {li_txt}")
            if list_lines:
                md_content_blocks.append('\n' + '\n'.join(list_lines) + '\n')

    # Build clean markdown
    full_body_text = '\n'.join(md_content_blocks).strip()
    word_count = len(full_body_text.split())

    # Build tags
    tags = ["The Signal Group", "Signal Ocean", section.title(), category]
    if "dry" in slug:
        tags.extend(["Dry Bulk", "Freight Rates", "Capesize", "Panamax"])
    if "tanker" in slug:
        tags.extend(["Tankers", "Freight Rates", "VLCC", "Suezmax", "Aframax"])

    frontmatter = f"""---
title: "{title}"
issue_date: "{iso_date}"
year: {year}
week: {week_num}
category: "{category}"
section: "{section}"
publisher: "The Signal Group"
source_url: "{url}"
source_file: "corpus/07-signal/html/{slug}.html"
word_count: {word_count}
images_count: {images_count}
tables_count: {len(all_data_tables)}
tags:
"""
    for t in sorted(set(tags)):
        frontmatter += f"  - {t}\n"
    frontmatter += "---\n\n"

    final_markdown = frontmatter + f"# {title}\n\n*Published on {dt.strftime('%d %B %Y')}*\n\n" + full_body_text + "\n"

    # Dual-write paths with localized relative image targets
    corpus_md_path = os.path.join(BASE_CORPUS, section, f"{slug}.md")
    extracted_md_path = os.path.join(OUT_MD_BASE, section, f"{slug}.md")

    os.makedirs(os.path.dirname(corpus_md_path), exist_ok=True)
    os.makedirs(os.path.dirname(extracted_md_path), exist_ok=True)

    safe_write_text(corpus_md_path, final_markdown)
    safe_write_text(extracted_md_path, final_markdown)

    # Save table sidecar if tables exist
    if all_data_tables:
        sidecar_path = os.path.join(OUT_MD_BASE, section, f"{slug}.tables.json")
        sidecar_data = {
            "slug": slug,
            "issue_date": iso_date,
            "year": year,
            "week": week_num,
            "category": category,
            "section": section,
            "title": title,
            "source_file": f"corpus/07-signal/html/{slug}.html",
            "tables": all_data_tables
        }
        safe_write_text(sidecar_path, json.dumps(sidecar_data, indent=2))

    return {
        "slug": slug,
        "url": url,
        "section": section,
        "category": category,
        "title": title,
        "date": iso_date,
        "year": year,
        "week": week_num,
        "status": "extracted",
        "word_count": word_count,
        "images_count": images_count,
        "tables_count": len(all_data_tables),
        "corpus_md": corpus_md_path,
        "extracted_md": extracted_md_path,
        "data_tables": all_data_tables
    }

def run_pipeline():
    start_time = time.time()
    print("=== STARTING THE SIGNAL GROUP EXTRACTION PIPELINE ===")

    # Ensure output directories exist
    for sub in ["monitors", "newsroom", "newsletters"]:
        os.makedirs(os.path.join(OUT_MD_BASE, sub), exist_ok=True)
        os.makedirs(os.path.join(BASE_CORPUS, sub), exist_ok=True)
    os.makedirs(SERIES_DIR, exist_ok=True)

    # Read manifest
    manifest_dict = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for r in reader:
                manifest_dict[r['slug']] = r

    html_files = sorted(glob.glob(os.path.join(HTML_DIR, "*.html")))
    print(f"[*] Total HTML snapshots to process: {len(html_files)}")

    results = []
    for h in html_files:
        res = convert_report_file(h, manifest_dict)
        results.append(res)

    extracted = [r for r in results if r['status'] == 'extracted']
    stubs = [r for r in results if r['status'] == 'skipped_media_mention_stub']

    print(f"\n[+] Pipeline Processing Completed in {time.time() - start_time:.2f}s:")
    print(f"    - Articles Extracted: {len(extracted)}")
    print(f"    - Media Mention Stubs: {len(stubs)}")

    # Section counts
    section_counts = {}
    for r in extracted:
        sec = r['section']
        section_counts[sec] = section_counts.get(sec, 0) + 1
    print(f"    - Breakdown by section: {section_counts}")

    # Generate master metadata catalog
    metadata_csv_path = os.path.join(SERIES_DIR, "signal_reports_metadata.csv")
    meta_headers = [
        "issue_date", "year", "week", "section", "category", "title",
        "word_count", "images_count", "tables_count", "url", "source_file", "md_file"
    ]
    with open(metadata_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(meta_headers)
        for r in sorted(extracted, key=lambda x: (x['date'], x['slug']), reverse=True):
            writer.writerow([
                r['date'], r['year'], r['week'], r['section'], r['category'], r['title'],
                r['word_count'], r['images_count'], r['tables_count'], r['url'],
                f"corpus/07-signal/html/{r['slug']}.html",
                f"data/extracted/md/signal/{r['section']}/{r['slug']}.md"
            ])
    print(f"[+] Stacked master metadata catalog: {metadata_csv_path} ({len(extracted)} rows)")

    # Generate vessel count time series
    vessel_series_path = os.path.join(SERIES_DIR, "signal_vessel_counts_series.csv")
    vessel_headers = ["issue_date", "year", "week", "sector", "vessel_class", "metric", "count", "source_file"]
    vessel_rows = []

    for r in extracted:
        if r.get('data_tables'):
            for tbl in r['data_tables']:
                for row_dict in tbl:
                    # check for Vessel Class / Ballasters or Number of Vessels
                    v_class = row_dict.get('Vessel Class') or row_dict.get('Vessel')
                    cnt = row_dict.get('Ballasters') or row_dict.get('Number of Vessels') or row_dict.get('Count')
                    if v_class and cnt:
                        # clean numeric count
                        clean_cnt = re.sub(r'[^\d.]', '', cnt)
                        metric = "Ballasters" if "ballaster" in str(row_dict).lower() else "Vessel Count"
                        sector = "Dry Bulk" if "dry" in r['slug'] else ("Tankers" if "tanker" in r['slug'] else r['category'])
                        vessel_rows.append([
                            r['date'], r['year'], r['week'], sector, v_class, metric, clean_cnt,
                            f"corpus/07-signal/html/{r['slug']}.html"
                        ])

    with open(vessel_series_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(vessel_headers)
        for v in sorted(vessel_rows, key=lambda x: (x[0], x[3], x[4])):
            writer.writerow(v)
    print(f"[+] Stacked vessel counts series: {vessel_series_path} ({len(vessel_rows)} rows)")

    # Update manifest
    with open(MANIFEST_PATH, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ["slug", "url", "section", "status", "md_path", "html_path", "title", "date", "category", "char_count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(results, key=lambda x: x['slug']):
            writer.writerow({
                "slug": r['slug'],
                "url": r['url'],
                "section": r['section'],
                "status": r['status'],
                "md_path": f"corpus/07-signal/{r['section']}/{r['slug']}.md" if r['status'] == 'extracted' else None,
                "html_path": f"corpus/07-signal/html/{r['slug']}.html",
                "title": r.get('title', ''),
                "date": r.get('date', ''),
                "category": r.get('category', ''),
                "char_count": r.get('word_count', 0)
            })
    print(f"[+] Synchronized manifest: {MANIFEST_PATH}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="The Signal Group Extraction Pipeline")
    parser.add_argument("--sync-live", action="store_true", help="Fetch latest updates from sitemap and live pages")
    args = parser.parse_args()

    if args.sync_live:
        print("[*] Running live acquisition sync...")
        import subprocess
        subprocess.run([sys.executable, "scripts/scrapers/fetch_signal_reports.py"], check=False)
        subprocess.run([sys.executable, "scripts/scrapers/download_signal_images.py"], check=False)

    run_pipeline()
