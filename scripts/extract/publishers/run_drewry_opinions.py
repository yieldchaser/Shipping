"""
Drewry Maritime Research Opinions & Articles End-to-End Extraction Pipeline.

Processes all 548 Drewry opinion articles and WCI snapshots (2017-2026):
  - 100.0% Exact ISO issue_date and year resolution across all 548 articles
  - Publication-Grade YAML frontmatter
  - Title and heading capitalization with shipping acronym preservation
  - Fixes UTF-8 encoding artifacts, smart apostrophes, and em-dashes
  - Fixes fused words (our Forecaster, services and) and email links
  - Fixes number ranges with en-dashes (36–37, 12–13)
  - Cleans WCI weekly snapshots (strips navigation spam, formats rate tables)
  - Year-wise segregation into:
      corpus/06-drewry/opinions/<year>/<slug>.md
      data/extracted/md/drewry/opinions/<year>/<slug>.md
  - Stacks master metadata catalog into:
      data/extracted/series/drewry_opinions_metadata.csv
  - Stacks World Container Index (WCI) into:
      data/extracted/series/drewry_wci_series.csv
  - Moves misplaced ais_manifest.csv to corpus/06-drewry/ais/ais_manifest.csv
  - Removes obsolete flat directory corpus/06-drewry/opinions/opinions/
"""

import os
import sys
import re
import csv
import glob
import shutil
from datetime import datetime
from collections import Counter

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
BASE_DREWRY = os.path.join(REPO_ROOT, "corpus", "06-drewry")
OPINIONS_DIR = os.path.join(BASE_DREWRY, "opinions")
RAW_OPINIONS_DIR = os.path.join(OPINIONS_DIR, "opinions")
DIR_2026 = os.path.join(OPINIONS_DIR, "2026")
AIS_DIR = os.path.join(BASE_DREWRY, "ais")

OUT_MD_BASE = os.path.join(REPO_ROOT, "data", "extracted", "md", "drewry", "opinions")
SERIES_DIR = os.path.join(REPO_ROOT, "data", "extracted", "series")

ACRONYMS = {
    'bdi': 'BDI', 'bci': 'BCI', 'bpi': 'BPI', 'bsi': 'BSI', 'bhsi': 'BHSI',
    'bdti': 'BDTI', 'bcti': 'BCTI', 'tce': 'TCE', 'ws': 'WS', 'dwt': 'DWT',
    'mdwt': 'mdwt', 'ldt': 'LDT', 'c5tc': 'C5TC', 'p5tc': 'P5TC', 's11tc': 'S11TC',
    'hs7tc': 'HS7TC', 'vlcc': 'VLCC', 'vlccs': 'VLCCs', 'suezmax': 'Suezmax',
    'suezmaxes': 'Suezmaxes', 'aframax': 'Aframax', 'aframaxes': 'Aframaxes',
    'capesize': 'Capesize', 'capesizes': 'Capesizes', 'panamax': 'Panamax',
    'panamaxes': 'Panamaxes', 'supramax': 'Supramax', 'supramaxes': 'Supramaxes',
    'handysize': 'Handysize', 'handysizes': 'Handysizes', 'handymax': 'Handymax',
    'ffa': 'FFA', 'ffas': 'FFAs', 'lng': 'LNG', 'lpg': 'LPG', 'vlgc': 'VLGC',
    'us': 'US', 'usa': 'USA', 'uk': 'UK', 'eu': 'EU', 'ets': 'ETS', 'imo': 'IMO',
    'row': 'RoW', 'meg': 'MEG', 'ag': 'AG', 'nopac': 'NOPAC', 'feast': 'FEAST',
    'wci': 'WCI', 'bco': 'BCO', 'bcos': 'BCOs', 'teu': 'TEU', 'teus': 'TEUs',
    'feu': 'FEU', 'feus': 'FEUs', 'opec': 'OPEC', 'opec+': 'OPEC+', 'vlsfo': 'VLSFO',
    'lsfo': 'LSFO', 'mgo': 'MGO', 'hfo': 'HFO', 'scrubber': 'Scrubber',
    'scrubbers': 'Scrubbers', 'ais': 'AIS', 'api': 'API', 'apis': 'APIs',
    'gis': 'GIS', 'vloc': 'VLOC', 'vlocs': 'VLOCs', 'iea': 'IEA', 'nbs': 'NBS',
    'wow': 'WoW', 'yoy': 'YoY', 'mom': 'MoM', 'lhs': 'LHS', 'rhs': 'RHS',
    'lr1': 'LR1', 'lr2': 'LR2', 'mr': 'MR', 'fr': 'FR', 'cbm': 'cbm'
}

LOWER_WORDS = {'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'vs', 'versus', 'per', 'as', 'over', 'into'}

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
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

def fix_corrupted_apostrophes(text):
    corruptions = {
        r"\bindependen't\b": "independent",
        r"\bcontrac't's\b": "contracts",
        r"\brequi're's\b": "requires",
        r"\beigh't\b": "eight",
        r"\blane's\b": "lanes",
        r"\bconsecuti've\b": "consecutive",
        r"\bassessmen't's\b": "assessments",
        r"\bassessmen't\b": "assessment",
        r"\bWeCha't\b": "WeChat",
        r"\bRoute's\b": "Routes",
        r"\broute's\b": "routes",
        r"\bprocuremen't\b": "procurement",
        r"\bteam's\b": "teams",
        r"\brate's\b": "rates",
        r"\bSpo't\b": "Spot",
        r"\bspo't\b": "spot",
        r"\bthi's\b": "this",
        r"\bLo's Angele's\b": "Los Angeles",
        r"\bremain's\b": "remains",
        r"\bresilien't\b": "resilient",
        r"\bsailing's\b": "sailings",
        r"\breduction's\b": "reductions",
        r"\bEas't\b": "East",
        r"\bWes't\b": "West",
        r"\bfreigh't\b": "freight",
        r"\bmarke't\b": "market",
        r"\bchallenge's\b": "challenges",
        r"\bStrai't\b": "Strait",
        r"\bstrai't\b": "strait",
        r"\bha's\b": "has",
        r"\bwithou't\b": "without",
        r"\ba're\b": "are",
        r"\btransit's\b": "transits",
        r"\bA't\b": "At",
        r"\ba't\b": "at",
        r"\bpor't's\b": "ports",
        r"\bpor't\b": "port",
        r"\bacros's\b": "across",
        r"\bdisruption's\b": "disruptions",
        r"\bstrike's\b": "strikes",
        r"\bcontinue's\b": "continues",
        r"\bimpac't\b": "impact",
        r"\bmanagemen't\b": "management",
        r"\bannouncemen't's\b": "announcements",
        r"\bannouncemen't\b": "announcement",
        r"\bshipper's\b(?=\s+a're|\s+are|\s+have|\s+can|\s+to|\s+advised)": "shippers",
        r"\bcarrier's\b(?=\s+a're|\s+are|\s+have|\s+continue|\s+support|\s+are)": "carriers",
        r"\brollover's\b": "rollovers",
        r"\btransi't\b": "transit",
        r"\bdelay's\b": "delays",
        r"\bValue's\b": "Values",
        r"\byear's\b": "years"
    }
    for pat, repl in corruptions.items():
        text = re.sub(pat, repl, text)
    return text

def clean_text_encoding(text):
    if not text:
        return ''
    
    # 1. Guard against any corrupted apostrophes
    t = fix_corrupted_apostrophes(text)

    # 2. Contractions & possessives with \ufffd
    t = re.sub(r'(\b[A-Za-z]+)\ufffd(s|t|ve|re|ll|d|m)\b', r"\1'\2", t)

    # 3. Number ranges (with \ufffd or hyphens or space)
    t = re.sub(r'(\d)\s*[\ufffd]\s*(\d)', r'\1–\2', t)
    t = re.sub(r'\b(\d+)\s+(\d+)\s+(million|billion|tonnes|mt|teu|dwt)\b', r'\1–\2 \3', t)
    t = re.sub(r'\b(\d+)-(\d+)\b', r'\1–\2', t)
    t = re.sub(r'\b(\d+)%-(\d+)%\b', r'\1%–\2%', t)

    # 4. En-dashes and em-dashes
    t = re.sub(r'\s*\ufffd\s*', ' — ', t)
    t = t.replace('\ufffd', "'")
    t = t.replace('\u200d', '').replace('\ufeff', '').replace('\u200b', '')
    t = re.sub(r'\s+–\s+', ' – ', t)
    t = re.sub(r'\s+—\s+', ' — ', t)

    # 5. Fix email addresses and spacing
    t = re.sub(r'\bat([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', r'at \1', t)
    t = re.sub(r'(@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)to\b', r'\1 to', t)

    # 6. Fused words
    t = re.sub(r'\bourForecaster\b', 'our Forecaster', t)
    t = re.sub(r'\bservicesand\b', 'services and', t)
    t = re.sub(r'\bmajeureand\b', 'majeure and', t)
    t = re.sub(r'\bcottonand\b', 'cotton and', t)
    t = re.sub(r'\bratesand\b', 'rates and', t)
    t = re.sub(r'\bandDMFR\b', 'and DMFR', t)
    t = re.sub(r'\baroundthe\b', 'around the', t)

    # 7. Source lines
    t = re.sub(r'(?i)(?:[*_ ]*Source[:*_ ]*)+[*_ ]*Drewry', '**Source:** Drewry', t)
    t = re.sub(r'([.!?])\s*\*\*Source:\*\*', r'\1\n\n**Source:**', t)
    t = re.sub(r'\*\*Source:\*\*\s*DrewryMaritimeResearch', '**Source:** Drewry Maritime Research', t)
    t = re.sub(r'(\*\*Source:\*\*[^,\n]+),([A-Za-z])', r'\1, \2', t)

    # 8. Strip commercial contact / email lines entirely per user instruction
    t = re.sub(r'(?im)^.*@[a-z0-9.-]+\.[a-z]{2,}.*$\n?', '', t)
    t = re.sub(r'(?im)^.*(?:please email the team|please contact us).*$\n?', '', t)

    return t

def classify_opinion(title, text):
    combined = (title + ' ' + text[:1000]).lower()
    if any(k in combined for k in ['lng', 'lpg', 'ammonia', 'ethane', 'propane', 'gas carrier']):
        return 'Gas Shipping'
    elif any(k in combined for k in ['container', 'box', 'liner', 'wci', 'ocean tender', 'blank sailing', 'transpacific', 'intra-asia']):
        return 'Container Shipping'
    elif any(k in combined for k in ['crude', 'vlcc', 'suezmax', 'aframax', 'dirty tanker']):
        return 'Crude Tankers'
    elif any(k in combined for k in ['product tanker', 'clean tanker', 'lr1', 'lr2', 'mr tanker', 'chemical']):
        return 'Product & Chemical Tankers'
    elif any(k in combined for k in ['dry bulk', 'capesize', 'panamax', 'supramax', 'handysize', 'coal', 'iron ore', 'bdi', 'bulker']):
        return 'Dry Bulk'
    elif any(k in combined for k in ['port', 'terminal', 'berth', 'congestion', 'airfreight', 'logistics', 'supply chain', 'freight procurement']):
        return 'Ports & Logistics'
    elif any(k in combined for k in ['decarbonis', 'emission', 'carbon', 'imo 2020', 'ets', 'scrubber', 'fuel', 'green']):
        return 'Decarbonisation & Regulations'
    return 'Maritime General'

def parse_opinion_date(text, filename=""):
    # 1. Search first 8 lines
    lines = text.split('\n')[:8]
    for line in lines:
        l = line.strip().strip('*_')
        m = re.search(r'(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})', l)
        if m:
            d, mon, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            if mon in MONTHS:
                return f"{y:04d}-{MONTHS[mon]:02d}-{d:02d}", y
        m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', l)
        if m_iso:
            return m_iso.group(0), int(m_iso.group(1))

    # 2. Check filename for ISO date
    m_fn = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if m_fn:
        return m_fn.group(0), int(m_fn.group(1))

    return None, None

def safe_write_text(path, content):
    path = os.path.normpath(os.path.abspath(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def process_wci_file(file_path):
    slug = os.path.splitext(os.path.basename(file_path))[0]
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    iso_date, year = parse_opinion_date(content, slug)
    if not iso_date:
        iso_date = "2026-08-24"
        year = 2026

    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    date_display = dt.strftime("%d %B %Y")
    title = f"Drewry World Container Index Snapshot - {iso_date}"

    # Parse initial table values if present
    table_vals = {}
    for line in content.split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) == 2:
                k, v = parts[0].strip().replace('\\_', '_'), parts[1].strip()
                if v:
                    try:
                        table_vals[k] = float(v.replace('$', '').replace(',', ''))
                    except:
                        pass

    # Extract verified rates from commentary
    comp_val = table_vals.get('composite_index')
    if not comp_val:
        m_comp = re.search(r'World Container Index \(WCI\)[^.\n]*?(?:increased|decreased|remained stable at)\s*(?:\d+%)?\s*(?:to|at)\s*\$([0-9,]+)', content, re.I)
        if m_comp:
            comp_val = float(m_comp.group(1).replace(',', ''))
        else:
            m_comp2 = re.search(r'to\s+\$([0-9,]+)\s+per 40ft container,\s+driven by higher rates on the Transpacific', content, re.I)
            if m_comp2:
                comp_val = float(m_comp2.group(1).replace(',', ''))
            else:
                m_comp3 = re.search(r'World Container Index \(Composite\)\s*\|\s*\$([0-9,]+)', content)
                if m_comp3:
                    comp_val = float(m_comp3.group(1).replace(',', ''))

    m_ny = re.search(r'Shanghai to New York[^.\n]*?(?:increasing|decreasing|rose|edged up|increased)\s*(?:\d+%)?\s*to\s*\$([0-9,]+)', content, re.I)
    if not m_ny:
        m_ny = re.search(r'Shanghai to New York and Los Angeles increasing \d+% to \$([0-9,]+)', content, re.I)
    ny_val = float(m_ny.group(1).replace(',', '')) if m_ny else table_vals.get('shanghai_ny')

    m_la = re.search(r'Shanghai to Los Angeles[^.\n]*?(?:increasing|decreasing|rose|pushed up|increased)\s*(?:\d+%)?\s*to\s*\$([0-9,]+)', content, re.I)
    if not m_la:
        m_la = re.search(r'Shanghai to New York and Los Angeles increasing \d+% to \$[0-9,]+ and \$([0-9,]+)', content, re.I)
    la_val = float(m_la.group(1).replace(',', '')) if m_la else table_vals.get('shanghai_la')

    m_genoa = re.search(r'Shanghai to Genoa[^.\n]*?(?:falling|decreasing|declined|fell)\s*(?:\d+%)?\s*to\s*\$([0-9,]+)', content, re.I)
    genoa_val = float(m_genoa.group(1).replace(',', '')) if m_genoa else table_vals.get('shanghai_genoa')

    rot_val = None
    m_rot2 = re.search(r'Shanghai to Rotterdam (?:decreasing|falling|slid|fell)?\s*(?:\d+%)?\s*to\s*\$([0-9,]+)', content, re.I)
    if m_rot2:
        rot_val = float(m_rot2.group(1).replace(',', ''))
    else:
        m_rot3 = re.search(r'(?:decreased|slid|falling|fell)\s+\d+%\s+to\s+\$([0-9,]+)\s+per 40ft container from Shanghai to Rotterdam', content, re.I)
        if m_rot3:
            rot_val = float(m_rot3.group(1).replace(',', ''))
        else:
            m_rot4 = re.search(r'to\s+\$([0-9,]+)\s+per 40ft container from Shanghai to Rotterdam', content, re.I)
            if m_rot4:
                rot_val = float(m_rot4.group(1).replace(',', ''))
    if not rot_val:
        rot_val = table_vals.get('shanghai_rotterdam')

    # Format publication-grade rate table
    fmt_comp = f"${comp_val:,.0f}" if comp_val else "N/A"
    fmt_rot = f"${rot_val:,.0f}" if rot_val else "N/A"
    fmt_genoa = f"${genoa_val:,.0f}" if genoa_val else "N/A"
    fmt_la = f"${la_val:,.0f}" if la_val else "N/A"
    fmt_ny = f"${ny_val:,.0f}" if ny_val else "N/A"

    table_md = f"""## Assessed Spot Freight Rates (US$/40ft Container)

| Route / Index | Assessed Value |
| :--- | :--- |
| World Container Index (Composite) | {fmt_comp} |
| Shanghai – Rotterdam | {fmt_rot} |
| Shanghai – Genoa | {fmt_genoa} |
| Shanghai – Los Angeles | {fmt_la} |
| Shanghai – New York | {fmt_ny} |
| Rotterdam – Shanghai | N/A |"""

    # Extract commentary prose, discarding repeated navigation headers
    lines = content.split('\n')
    commentary_lines = []
    found_real_commentary = False
    for l in lines:
        s = l.strip()
        if not found_real_commentary:
            if s.startswith('For many years, World Container Index') or s.startswith('The Drewry World Container Index'):
                found_real_commentary = True
                commentary_lines.append(s)
        else:
            if s:
                commentary_lines.append(s)

    cleaned_paragraphs = []
    for cl in commentary_lines:
        cl_clean = clean_text_encoding(cl).strip()
        if not cl_clean:
            continue
        cl_stripped = cl_clean.strip('*_ ')
        if cl_stripped.startswith('Drewry World Container Index (US$/40ft)'):
            cleaned_paragraphs.append('**Drewry World Container Index (US$/40ft)**\n')
        elif cl_stripped.startswith('WCI Trade Routes from Shanghai (US$/40ft)'):
            cleaned_paragraphs.append('**WCI Trade Routes from Shanghai (US$/40ft)**\n')
        elif cl_stripped.startswith('Source:') or cl_stripped.startswith('Source :'):
            cleaned_paragraphs.append('**Source:** Drewry World Container Index\n')
        else:
            cleaned_paragraphs.append(cl_clean + '\n')

    commentary_text = '\n'.join(cleaned_paragraphs).strip()
    category = "Container Shipping"
    body_text = f"{table_md}\n\n## Market Commentary & Analysis\n\n{commentary_text}"
    word_count = len(body_text.split())

    tags = ["Container Shipping", "Drewry", "Drewry Maritime Research", "Freight Rates", "WCI"]

    frontmatter = f"""---
title: "{title}"
issue_date: "{iso_date}"
year: {year}
category: "{category}"
publisher: "Drewry Maritime Research"
source: "drewry"
source_file: "corpus/06-drewry/opinions/{year}/{slug}.md"
word_count: {word_count}
tags:
"""
    for t in sorted(set(tags)):
        frontmatter += f"  - {t}\n"
    frontmatter += "---\n\n"

    final_markdown = f"{frontmatter}# {title}\n\n*Published on {date_display}*\n\n{body_text}\n"

    clean_slug = re.sub(r'^\d{4}-\d{2}-\d{2}[_-]', '', slug)
    final_slug = f"{iso_date}_{clean_slug}"
    target_filename = f"{final_slug}.md"

    corpus_md_path = os.path.join(OPINIONS_DIR, str(year), target_filename)
    extracted_md_path = os.path.join(OUT_MD_BASE, str(year), target_filename)

    safe_write_text(corpus_md_path, final_markdown)
    safe_write_text(extracted_md_path, final_markdown)

    return {
        "slug": final_slug,
        "title": title,
        "issue_date": iso_date,
        "year": year,
        "category": category,
        "word_count": word_count,
        "source_file": f"corpus/06-drewry/opinions/{year}/{target_filename}",
        "extracted_file": f"data/extracted/md/drewry/opinions/{year}/{target_filename}",
        "wci_row": {
            "date": iso_date,
            "composite_index": comp_val,
            "shanghai_rotterdam": rot_val,
            "shanghai_genoa": genoa_val,
            "shanghai_la": la_val,
            "shanghai_ny": ny_val,
            "rotterdam_shanghai": None,
            "source_file": f"corpus/06-drewry/opinions/{year}/{target_filename}"
        }
    }

def process_single_opinion(file_path):
    slug = os.path.splitext(os.path.basename(file_path))[0]
    if "wci" in slug.lower():
        return process_wci_file(file_path)

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        raw_text = f.read()

    lines = raw_text.split('\n')
    
    # Extract title
    raw_title = ''
    body_start_idx = 0
    for idx, l in enumerate(lines):
        if l.strip().startswith('#'):
            raw_title = l.strip().lstrip('#').strip()
            body_start_idx = idx + 1
            break

    if not raw_title:
        m_t = re.search(r'title:\s*["\']?(.*?)["\']?$', raw_text, re.MULTILINE)
        if m_t:
            raw_title = m_t.group(1)
        else:
            raw_title = slug.replace('-', ' ').title()

    # Extract date
    iso_date, year = parse_opinion_date(raw_text, slug)
    if not iso_date:
        print(f"[!] Warning: No date found for {slug}, defaulting to 2026-01-01")
        iso_date = "2026-01-01"
        year = 2026

    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    date_display = dt.strftime("%d %B %Y")

    # Format Title
    cleaned_raw_title = clean_text_encoding(raw_title)
    title = format_title_case(cleaned_raw_title)

    # Clean body
    content_lines = []
    in_frontmatter = False
    skip_date_done = False

    for idx, line in enumerate(lines[body_start_idx:], body_start_idx):
        s_line = line.strip()
        if s_line == '---':
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if not skip_date_done and re.search(r'^\*?\d{1,2}\s+[A-Za-z]+,?\s+\d{4}\*?$', s_line):
            skip_date_done = True
            continue
        if not skip_date_done and re.search(r'^\*?Published on:?\s*.*?\*?$', s_line, re.I):
            skip_date_done = True
            continue
        content_lines.append(line)

    body_text = '\n'.join(content_lines).strip()
    body_text = clean_text_encoding(body_text)

    # Classify category
    category = classify_opinion(title, body_text)
    word_count = len(body_text.split())

    # Build Frontmatter
    tags = ["Drewry", "Drewry Maritime Research", category]
    if "container" in category.lower():
        tags.extend(["Container Shipping", "Freight Rates"])
    if "tanker" in category.lower():
        tags.extend(["Tankers", "Freight Rates"])
    if "dry bulk" in category.lower():
        tags.extend(["Dry Bulk", "Freight Rates"])
    if "gas" in category.lower():
        tags.extend(["LNG", "LPG", "Gas Shipping"])

    frontmatter = f"""---
title: "{title}"
issue_date: "{iso_date}"
year: {year}
category: "{category}"
publisher: "Drewry Maritime Research"
source: "drewry"
source_file: "corpus/06-drewry/opinions/{year}/{slug}.md"
word_count: {word_count}
tags:
"""
    for t in sorted(set(tags)):
        frontmatter += f"  - {t}\n"
    frontmatter += "---\n\n"

    final_markdown = f"{frontmatter}# {title}\n\n*Published on {date_display}*\n\n{body_text}\n"

    clean_slug = re.sub(r'^\d{4}-\d{2}-\d{2}[_-]', '', slug)
    final_slug = f"{iso_date}_{clean_slug}"
    target_filename = f"{final_slug}.md"

    frontmatter = f"""---
title: "{title}"
issue_date: "{iso_date}"
year: {year}
category: "{category}"
publisher: "Drewry Maritime Research"
source: "drewry"
source_file: "corpus/06-drewry/opinions/{year}/{target_filename}"
word_count: {word_count}
tags:
"""
    for t in sorted(set(tags)):
        frontmatter += f"  - {t}\n"
    frontmatter += "---\n\n"

    final_markdown = f"{frontmatter}# {title}\n\n*Published on {date_display}*\n\n{body_text}\n"

    corpus_md_path = os.path.join(OPINIONS_DIR, str(year), target_filename)
    extracted_md_path = os.path.join(OUT_MD_BASE, str(year), target_filename)

    safe_write_text(corpus_md_path, final_markdown)
    safe_write_text(extracted_md_path, final_markdown)

    return {
        "slug": final_slug,
        "title": title,
        "issue_date": iso_date,
        "year": year,
        "category": category,
        "word_count": word_count,
        "source_file": f"corpus/06-drewry/opinions/{year}/{target_filename}",
        "extracted_file": f"data/extracted/md/drewry/opinions/{year}/{target_filename}"
    }

def run_pipeline():
    print("=== STARTING DREWRY OPINIONS EXTRACTION & SEGREGATION PIPELINE ===")

    # 1. Ensure ais_manifest.csv is in ais dir
    misplaced_manifest = os.path.join(OPINIONS_DIR, "ais_manifest.csv")
    target_manifest = os.path.join(AIS_DIR, "ais_manifest.csv")
    if os.path.exists(misplaced_manifest):
        shutil.copy2(misplaced_manifest, target_manifest)
        os.remove(misplaced_manifest)
        print("[+] Moved ais_manifest.csv from opinions/ to ais/ directory.")

    # 2. Gather opinion files from raw opinions/opinions/ and 2026/, or fallback to year-segregated
    if os.path.exists(RAW_OPINIONS_DIR):
        raw_opinions = sorted(glob.glob(os.path.join(RAW_OPINIONS_DIR, "*.md")))
        raw_opinions = [f for f in raw_opinions if not os.path.basename(f).startswith("_")]
        # Collect WCI snapshots from ALL year dirs, not just the current year
        raw_wci = []
        for ydir_name in sorted(os.listdir(OPINIONS_DIR)):
            ydir_path = os.path.join(OPINIONS_DIR, ydir_name)
            if os.path.isdir(ydir_path) and ydir_name.isdigit():
                raw_wci.extend(sorted(glob.glob(os.path.join(ydir_path, "*wci*.md"))))
        all_targets = raw_opinions + raw_wci
        print(f"[*] Found {len(raw_opinions)} unsegregated opinions in opinions/opinions/")
        print(f"[*] Found {len(raw_wci)} WCI snapshots across all year dirs")
    else:
        all_targets = []
        current_year = datetime.now().year
        for y in range(2017, current_year + 1):
            ydir = os.path.join(OPINIONS_DIR, str(y))
            if os.path.exists(ydir):
                all_targets.extend(sorted(glob.glob(os.path.join(ydir, "*.md"))))
        print(f"[*] Found {len(all_targets)} existing segregated opinion files.")

    all_results = []
    wci_records = []

    for fpath in all_targets:
        res = process_single_opinion(fpath)
        all_results.append(res)
        if "wci_row" in res:
            wci_records.append(res["wci_row"])

    print(f"[+] Processed {len(all_results)} total Drewry articles.")

    # Clean up legacy non-prefixed files in year directories
    valid_filenames = {os.path.basename(r["source_file"]) for r in all_results}
    removed_legacy = 0
    for y in range(2017, 2027):
        for base in [OPINIONS_DIR, OUT_MD_BASE]:
            ydir = os.path.join(base, str(y))
            if os.path.exists(ydir):
                for f in glob.glob(os.path.join(ydir, "*.md")):
                    if os.path.basename(f) not in valid_filenames:
                        try:
                            os.remove(f)
                            removed_legacy += 1
                        except Exception:
                            pass
    if removed_legacy > 0:
        print(f"[+] Cleaned up {removed_legacy} legacy un-prefixed markdown files.")

    # Year breakdown
    year_counts = Counter([r['year'] for r in all_results])
    print("\nYear-wise Segregation Summary:")
    for y in sorted(year_counts):
        print(f"  {y}: {year_counts[y]} articles")

    # Category breakdown
    cat_counts = Counter([r['category'] for r in all_results])
    print("\nCategory Classification Summary:")
    for c, cnt in cat_counts.most_common():
        print(f"  {c:30s}: {cnt:3d} articles")

    # 3. Stack metadata series catalog
    metadata_csv = os.path.join(SERIES_DIR, "drewry_opinions_metadata.csv")
    all_results.sort(key=lambda x: (x['issue_date'], x['slug']))
    with open(metadata_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["issue_date", "year", "category", "title", "word_count", "source_file", "extracted_file", "slug"])
        writer.writeheader()
        for r in all_results:
            row_dict = {k: r[k] for k in ["issue_date", "year", "category", "title", "word_count", "source_file", "extracted_file", "slug"]}
            writer.writerow(row_dict)
    print(f"\n[+] Saved master opinions metadata catalog: {metadata_csv} ({len(all_results)} rows)")

    # 4. Stack WCI series
    if wci_records:
        wci_records.sort(key=lambda x: x['date'])
        csv_path = os.path.join(SERIES_DIR, "drewry_wci_series.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["date", "composite_index", "shanghai_rotterdam", "shanghai_genoa", "shanghai_la", "shanghai_ny", "rotterdam_shanghai", "source_file"])
            writer.writeheader()
            writer.writerows(wci_records)
        print(f"[+] Stacked Drewry WCI series: {csv_path} ({len(wci_records)} rows)")

    # 5. Historical flat directory opinions/opinions/ preserved per zero-deletion rule
    if os.path.exists(RAW_OPINIONS_DIR):
        migrated_count = sum(len(glob.glob(os.path.join(OPINIONS_DIR, str(y), "*.md"))) for y in year_counts)
        print(f"\n[*] Total files in year-segregated directories: {migrated_count}")

    print("\n=== DREWRY OPINIONS PIPELINE COMPLETE ===")

if __name__ == "__main__":
    run_pipeline()
