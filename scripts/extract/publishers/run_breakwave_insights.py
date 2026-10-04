"""
Breakwave Insights HTML-to-Markdown Full Corpus Pipeline (Publication-Grade)
Processes all 3,194 Breakwave market insight articles across 2020-2026:
- Extracts frontmatter (title, ISO date, display date, canonical URL, tags, year, image count, word count)
- Renders images using relative paths for inline Markdown Preview and file:/// URIs for [Local Asset] direct opening
- Formats figures with academic blockquotes, descriptive titles, captions, and interactive platform links
- Consumes caption and tracking link paragraphs to eliminate duplicate prose leaks
- Cleans naked tracking URLs (e.g. Signal Ocean, Bloomberg, Reuters) into named markdown links
- Normalizes bold paragraphs and HTML headings into semantic markdown headings (## / ###) with Title Casing
- Dual-writes to both data/extracted/md/breakwave/insights/<year>/ and corpus/03-breakwave/insights/<year>/
- Stacks master metadata index: data/extracted/series/breakwave_insights_metadata.csv
"""

import os
import sys
import re
import glob
import time
import csv
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup, NavigableString, Tag

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ACRONYMS = {
    'vlcc': 'VLCC', 'suezmax': 'Suezmax', 'aframax': 'Aframax', 'capesize': 'Capesize',
    'panamax': 'Panamax', 'supramax': 'Supramax', 'handysize': 'Handysize', 'handymax': 'Handymax',
    'lr1': 'LR1', 'lr2': 'LR2', 'mr1': 'MR1', 'mr2': 'MR2', 'mr': 'MR', 'tce': 'TCE',
    'bdi': 'BDI', 'bci': 'BCI', 'bpi': 'BPI', 'bsi': 'BSI', 'bhsi': 'BHSI', 'ws': 'WS',
    'dwt': 'DWT', 'ldt': 'LDT', 'nopac': 'NOPAC', 'usg': 'USG', 'meg': 'MEG', 'ag': 'AG',
    'eia': 'EIA', 'iea': 'IEA', 'opec': 'OPEC', 'vlsfo': 'VLSFO', 'hsfo': 'HSFO', 'mgo': 'MGO',
    'lng': 'LNG', 'lpg': 'LPG', 'toncharts': 'TonCharts', 'tondays': 'TonDays', 'covid': 'COVID'
}

LOWER_WORDS = {'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'vs', 'versus', 'per'}

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
        follows_delimiter = bool(prev_word.endswith(':') or prev_word.endswith('-') or prev_word in ['-', '–', '—', '/', '|'])

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

        prefix = re.match(r'^[^\w]*', w).group(0)
        suffix = re.search(r'[^\w]*$', w).group(0)
        core = w[len(prefix):len(w)-len(suffix)] if len(suffix) else w[len(prefix):]
        if not core:
            out.append(w)
            continue
        core_lower = core.lower()
        if core_lower in ACRONYMS:
            cased = ACRONYMS[core_lower]
        elif is_first or is_last or follows_delimiter or core_lower not in LOWER_WORDS:
            cased = core.capitalize()
        else:
            cased = core_lower
        out.append(f'{prefix}{cased}{suffix}')
    return ' '.join(out)

def clean_url_anchor(href):
    if not href:
        return ''
    h_lower = href.lower()
    if 'signalocean.com' in h_lower or 'thesignalgroup.com' in h_lower:
        if 'crude-oil-flows' in h_lower:
            return 'Signal Ocean Tanker Dynamic Crude Oil Flows'
        if 'market-prices' in h_lower:
            return 'Signal Ocean Dynamic Market Prices'
        if 'vlcc-insights' in h_lower:
            return 'Signal Ocean VLCC Insights'
        if 'timeseries' in h_lower:
            return 'Signal Ocean Dynamic Timeseries'
        return 'Signal Ocean Platform'
    if 'breakwaveadvisors.com' in h_lower:
        return 'Breakwave Advisors Market Insights'
    if 'bloomberg.com' in h_lower:
        return 'Bloomberg News'
    if 'reuters.com' in h_lower:
        return 'Reuters'
    if 'eia.gov' in h_lower:
        return 'U.S. Energy Information Administration (EIA)'
    if 'iea.org' in h_lower:
        return 'International Energy Agency (IEA)'
    if 'tradewindsnews.com' in h_lower:
        return 'TradeWinds'
    if 'splash247.com' in h_lower:
        return 'Splash247'
    if 'hellenicshippingnews.com' in h_lower:
        return 'Hellenic Shipping News'
    m = re.search(r'https?://([^/]+)', href)
    if m:
        domain = m.group(1).replace('www.', '')
        parts = [p.capitalize() for p in domain.split('.')]
        return ' '.join(parts[:-1]) if len(parts) > 1 else domain.capitalize()
    return 'Interactive Source'

def clean_tanker_title(prev_text):
    if not prev_text or len(prev_text) > 120 or '.' in prev_text:
        return ''
    m = re.search(r'^(?:[#*\s-]*)?(VLCC|Suezmax|Aframax|MR|LR1|LR2|Capesize|Panamax|Supramax|Handysize)\s*([A-Za-z0-9\s\-/]{0,35}?)\s*(Weaker|Firmer|Steady|Soft|Firm|Bullish|Bearish)', prev_text.strip(), re.IGNORECASE)
    if m:
        seg = m.group(1).upper()
        route = m.group(2).strip().replace('-', ' - ')
        route = re.sub(r'\s+', ' ', route)
        sentiment = m.group(3).capitalize()
        if route:
            return f'{seg}: {route} (Sentiment: {sentiment})'
        return f'{seg} (Sentiment: {sentiment})'
    return ''

def title_from_caption(c):
    if not c or len(c) < 8:
        return ''
    m = re.match(r'^(?:Chart|Figure|Table)\s*\d*\s*[:|-]\s*(?:Signal Ocean Data\s*\|\s*)?(.*?)$', c.strip(), re.I)
    raw = m.group(1).strip() if m else c.strip()
    if '|' in raw:
        raw = raw.split('|')[-1].strip()
    c_clean = re.sub(r'^(The|A|An)\s+', '', raw, flags=re.I)
    parts = [p.strip() for p in re.split(r'[,.;—–]', c_clean) if p.strip()]
    if not parts:
        return ''
    candidate = parts[0]
    if len(candidate) < 6 and len(parts) > 1:
        candidate = f'{parts[0]} - {parts[1]}'
    if len(candidate) > 65:
        candidate = candidate[:65].rsplit(' ', 1)[0]
    if len(candidate) > 4:
        return format_title_case(candidate)
    return ''

def clean_stem(src):
    base = os.path.basename(src)
    m = re.search(r'_img_(.+?)_[a-f0-9]{10,}\.[a-z0-9]+$', base, flags=re.IGNORECASE)
    if m:
        raw = m.group(1)
        raw = re.sub(r'28\d+29', '', raw)
        raw = raw.replace('_', ' ').replace('-', ' ').strip()
        if not raw.lower().startswith('unnamed') and not raw.lower().startswith('image'):
            raw = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw)
            return format_title_case(raw)
    return ''

def clean_cell(text):
    text = text.replace('\n', ' ').replace('|', '\\|')
    return re.sub(r'\s+', ' ', text).strip()

def process_single_article(html_path):
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    title = ''
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.h1:
        title = soup.h1.get_text().strip()

    date_meta = soup.find('meta', {'name': 'archive-date'})
    display_date = date_meta.get('content').strip() if date_meta else ''

    filename = os.path.basename(html_path)
    date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', filename)
    iso_date = date_match.group(1) if date_match else ''

    url_meta = soup.find('meta', {'name': 'archive-url'})
    url_str = url_meta.get('content').strip() if url_meta else ''

    tags = []
    tag_p = soup.find('p', class_='tags')
    if tag_p:
        raw_tags = tag_p.get_text().replace('Tags:', '').strip()
        tags = [format_title_case(t.strip()) for t in raw_tags.split('|') if t.strip()]

    year_match = re.search(r'[\\/](\d{4})[\\/]', html_path)
    year = int(year_match.group(1)) if year_match else (int(iso_date[:4]) if iso_date else 2020)

    section = soup.find('section')
    if not section:
        section = soup.find('body')

    imgs = section.find_all('img') if section else []
    images_count = len(imgs)

    consumed_elements = set()
    img_blocks = {}

    for idx, img in enumerate(imgs, 1):
        src = img.get('src', '').strip()
        alt = img.get('alt', '').strip()

        # Absolute file path & file URI for one-click opening in editor
        abs_img_path = os.path.abspath(os.path.join(os.path.dirname(html_path), src))
        file_uri = f"file:///{abs_img_path.replace(chr(92), '/')}"

        # Relative path for standard inline markdown rendering
        rel_img_path = src if not src.startswith(('http://', 'https://')) else file_uri

        caption = ''
        source_url = ''

        # Search next elements for caption and source link
        for p in img.find_all_next(['p', 'blockquote']):
            prev_img = p.find_previous('img')
            if prev_img != img:
                break
            txt = p.get_text().strip()
            if not txt:
                continue
            a_in_p = p.find('a')
            if a_in_p and len(txt) == len(a_in_p.get_text().strip()) and a_in_p.get('href', '').startswith('http'):
                if not source_url:
                    source_url = a_in_p.get('href', '').strip()
                    consumed_elements.add(p)
                    continue
            if re.match(r'^(?:Chart|Figure|Table)\s*\d*\s*[:|]', txt, re.I):
                if not caption:
                    caption = txt
                    consumed_elements.add(p)
                    break
            elif (p.find('em') or p.name == 'blockquote') and len(txt) > 15:
                if not caption:
                    caption = txt
                    consumed_elements.add(p)
                    break

        if not source_url:
            a_tag = img.find_next('a')
            if a_tag and a_tag.get('href', '').startswith('http'):
                source_url = a_tag.get('href', '').strip()

        fig_title = ''
        if caption:
            cap_t = title_from_caption(caption)
            if cap_t:
                fig_title = cap_t

        if not fig_title:
            prev_p = img.find_previous(['p', 'h2', 'h3', 'strong'])
            prev_txt = prev_p.get_text().strip() if prev_p else ''
            tanker_title = clean_tanker_title(prev_txt)
            if tanker_title:
                fig_title = tanker_title
                if prev_p and len(prev_txt) < 80:
                    consumed_elements.add(prev_p)

        if not fig_title and alt:
            alt_clean = re.sub(r'\.(?:png|jpe?g|webp)$', '', alt, flags=re.IGNORECASE).strip()
            alt_clean = re.sub(r'28\d+29', '', alt_clean).strip()
            alt_clean = alt_clean.replace('_', ' ').replace('-', ' ')
            alt_clean = re.sub(r'\s+', ' ', alt_clean).strip()
            if not alt_clean.lower().startswith('unnamed') and not alt_clean.lower().startswith('image') and len(alt_clean) > 3:
                fig_title = format_title_case(alt_clean)

        if not fig_title:
            stem_title = clean_stem(src)
            if stem_title:
                fig_title = stem_title

        if not fig_title:
            prev_p = img.find_previous(['p', 'h2', 'h3', 'strong'])
            prev_txt = prev_p.get_text().strip() if prev_p else ''
            if prev_p and prev_p not in consumed_elements:
                ptxt = re.sub(r'\s+', ' ', prev_txt)
                if 3 < len(ptxt) < 70 and not ptxt.endswith('.'):
                    fig_title = format_title_case(ptxt)
                    consumed_elements.add(prev_p)

        if not fig_title:
            fig_title = f'Market Chart {idx}'

        # Build figure markdown block
        lines = []
        lines.append(f'![{fig_title}]({rel_img_path})')
        lines.append('')
        lines.append(f'> **Figure {idx}: {fig_title}**  ')
        if caption:
            lines.append(f'> *{caption}*  ')

        source_line_parts = []
        if source_url:
            anchor_lbl = clean_url_anchor(source_url)
            source_line_parts.append(f'**Interactive Data & Source:** [{anchor_lbl}]({source_url})')
        if file_uri:
            source_line_parts.append(f'[Local Asset]({file_uri})')

        if source_line_parts:
            lines.append(f"> {' | '.join(source_line_parts)}")
        lines.append('')

        img_blocks[id(img)] = '\n'.join(lines)

    def is_consumed(node):
        curr = node
        while curr:
            if curr in consumed_elements:
                return True
            curr = curr.parent
        return False

    def to_md(node):
        if is_consumed(node):
            return ''

        if isinstance(node, NavigableString):
            return str(node)
        if not isinstance(node, Tag):
            return ''

        tag = node.name.lower()

        if tag == 'br':
            return '\n'

        if tag in ['strong', 'b']:
            inner = ''.join(to_md(c) for c in node.children).strip()
            return f'**{inner}**' if inner else ''

        if tag in ['em', 'i']:
            inner = ''.join(to_md(c) for c in node.children).strip()
            return f'*{inner}*' if inner else ''

        if tag == 'a':
            href = node.get('href', '').strip()
            inner = ''.join(to_md(c) for c in node.children).strip()
            if not href:
                return inner
            if not inner or inner == href or re.match(r'^https?://', inner):
                inner = clean_url_anchor(href)
            return f'[{inner}]({href})'

        if tag == 'img':
            if id(node) in img_blocks:
                return '\n\n' + img_blocks[id(node)] + '\n\n'
            return ''

        if tag == 'figure':
            parts = [to_md(c) for c in node.children]
            return '\n\n' + ''.join(parts).strip() + '\n\n'

        if tag == 'blockquote':
            inner = ''.join(to_md(c) for c in node.children).strip()
            bq_lines = [f'> {line}' for line in inner.split('\n') if line.strip()]
            return '\n\n' + '\n>\n'.join(bq_lines) + '\n\n'

        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag[1])
            prefix = '#' * max(2, min(level, 4))
            inner = node.get_text().strip()
            if inner:
                inner_clean = format_title_case(inner)
                return f'\n\n{prefix} {inner_clean}\n\n'
            return ''

        if tag == 'ul':
            items = []
            for c in node.find_all('li', recursive=False):
                it = ''.join(to_md(ch) for ch in c.children).strip()
                if it:
                    items.append(f'- {it}')
            return '\n\n' + '\n'.join(items) + '\n\n'

        if tag == 'ol':
            items = []
            for i, c in enumerate(node.find_all('li', recursive=False), 1):
                it = ''.join(to_md(ch) for ch in c.children).strip()
                if it:
                    items.append(f'{i}. {it}')
            return '\n\n' + '\n'.join(items) + '\n\n'

        if tag == 'table':
            rows = []
            for tr in node.find_all('tr'):
                cells = [clean_cell(''.join(to_md(c) for c in cell.children).strip())
                         for cell in tr.find_all(['th', 'td'])]
                if any(cells):
                    rows.append(cells)
            if not rows:
                return ''
            max_cols = max(len(r) for r in rows)
            norm_rows = [r + [''] * (max_cols - len(r)) for r in rows]
            table_md = ['| ' + ' | '.join(norm_rows[0]) + ' |',
                        '| ' + ' | '.join([':---'] * max_cols) + ' |']
            for r in norm_rows[1:]:
                table_md.append('| ' + ' | '.join(r) + ' |')
            return '\n\n' + '\n'.join(table_md) + '\n\n'

        if tag == 'p':
            if 'tags' in node.get('class', []):
                return ''
            inner = ''.join(to_md(c) for c in node.children).strip()
            if not inner:
                return ''

            m_bold = re.match(r'^\*\*(.+?)\*\*$', inner)
            if m_bold and len(m_bold.group(1)) < 90 and '\n' not in inner and not m_bold.group(1).endswith('.'):
                hdr = format_title_case(m_bold.group(1))
                return f'\n\n### {hdr}\n\n'

            if inner.lower().startswith('takeaway'):
                return f'\n\n## Key Market Takeaways\n\n'

            return f'\n\n{inner}\n\n'

        parts = [to_md(c) for c in node.children]
        return ''.join(parts)

    body_md = to_md(section) if section else ''
    body_md = re.sub(r'\n{3,}', '\n\n', body_md).strip()

    word_count = len(re.findall(r'\b\w+\b', body_md))

    # Assemble document
    md = []
    md.append('---')
    md.append(f'title: "{title}"')
    if iso_date:
        md.append(f'date: "{iso_date}"')
    if display_date:
        md.append(f'display_date: "{display_date}"')
    md.append(f'year: {year}')
    md.append('category: "insights"')
    md.append('source: "Breakwave Advisors"')
    if url_str:
        md.append(f'url: "{url_str}"')
    if tags:
        tag_str = ', '.join(f'"{t}"' for t in tags)
        md.append(f'tags: [{tag_str}]')
    md.append(f'images_count: {images_count}')
    md.append(f'word_count: {word_count}')
    md.append(f'source_file: "{html_path.replace(chr(92), "/")}"')
    md.append('---')
    md.append('')
    md.append(f'# {title}')
    md.append('')
    if display_date:
        md.append(f'**Date:** {display_date}  ')
    elif iso_date:
        md.append(f'**Date:** {iso_date}  ')
    md.append('**Publisher:** Breakwave Advisors | **Category:** Market Insights  ')
    if url_str:
        md.append(f'**Original URL:** [{url_str}]({url_str})  ')
    md.append('')
    md.append('---')
    md.append('')
    md.append(body_md)
    md.append('')
    if tags:
        md.append('---')
        md.append('')
        md.append(f"**Tags:** {', '.join(tags)}  ")
        md.append('')

    full_md = '\n'.join(md)

    metadata_record = {
        'issue_date': iso_date or display_date,
        'year': year,
        'title': title,
        'url': url_str,
        'tags': '; '.join(tags),
        'images_count': images_count,
        'word_count': word_count,
        'source_file': html_path.replace('\\', '/'),
        'md_file': f'data/extracted/md/breakwave/insights/{year}/{os.path.splitext(filename)[0]}.md'
    }

    stem = os.path.splitext(filename)[0]
    out_ext_path = f'data/extracted/md/breakwave/insights/{year}/{stem}.md'
    corpus_md_path = f'corpus/03-breakwave/insights/{year}/{stem}.md'

    os.makedirs(os.path.dirname(out_ext_path), exist_ok=True)
    os.makedirs(os.path.dirname(corpus_md_path), exist_ok=True)

    with open(out_ext_path, 'w', encoding='utf-8') as f:
        f.write(full_md)

    with open(corpus_md_path, 'w', encoding='utf-8') as f:
        f.write(full_md)

    return metadata_record

def run_pipeline(target_years=None):
    t_start = time.time()
    if target_years:
        years = target_years
    else:
        insights_dir = Path('corpus/03-breakwave/insights')
        if insights_dir.exists():
            discovered = sorted([p.name for p in insights_dir.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 4])
            years = discovered if discovered else [str(y) for y in range(2020, datetime.now(timezone.utc).year + 2)]
        else:
            years = [str(y) for y in range(2020, datetime.now(timezone.utc).year + 2)]

    os.makedirs('data/extracted/series', exist_ok=True)
    all_files = []
    for y in years:
        y_files = sorted(glob.glob(f'corpus/03-breakwave/insights/{y}/*.html'))
        all_files.extend(y_files)

    print(f'Starting World-Class Breakwave Insights extraction on {len(all_files)} files across years: {", ".join(years)}')

    max_workers = min(os.cpu_count() or 4, 8)
    all_metadata = []
    total_errors = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for idx, meta in enumerate(executor.map(process_single_article, all_files), 1):
            if meta:
                all_metadata.append(meta)
            else:
                total_errors += 1
            if idx % 500 == 0 or idx == len(all_files):
                print(f'Processed {idx}/{len(all_files)} files ({idx/(time.time() - t_start):.1f} files/sec)...')

    # Write Master Metadata Catalog
    meta_path = 'data/extracted/series/breakwave_insights_metadata.csv'
    with open(meta_path, 'w', encoding='utf-8', newline='') as mf:
        fieldnames = ['issue_date', 'year', 'title', 'url', 'tags', 'images_count', 'word_count', 'source_file', 'md_file']
        writer = csv.DictWriter(mf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_metadata)

    t_total = time.time() - t_start
    print(f'\nPipeline Complete!')
    print(f'Total files converted: {len(all_metadata)} (Errors: {total_errors}) in {t_total:.1f}s')
    print(f'Master metadata catalog created: {meta_path} ({len(all_metadata)} rows)')

if __name__ == '__main__':
    target_years = sys.argv[1:] if len(sys.argv) > 1 else None
    run_pipeline(target_years)
