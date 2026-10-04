"""Lion Shipbrokers - High-Fidelity Extraction Pipeline (LiteParse-style layout).

Features:
1. Strips all emails, telephone lines, repetitive broker boilerplates, running headers/footers,
   and legal disclaimers.
2. Extracts Quote / Joke of the Week with verified author attributions.
3. Partitions Market Commentary cleanly into Tankers, Bulkers, Demolition, and Baltic Dry Indices.
4. Parses Lion's Demometer (USD $/LT) table across Turkey, Pakistan, India, Bangladesh.
5. Structures Representative Sales (Bulkers, Tankers, Cont/Tween/MPP, Gas) into clean GitHub markdown tables.
6. Structures Demolition Sales into clean tables with LDT, DWT, $/LT price, and destination.
7. Retains complete deal narratives and commercial terms.
8. Writes structured .tables.json sidecars with ISO issue_date stamped on every record.
9. Updates master CSV series in data/extracted/series/.
10. Updates the digests in corpus/01-brokers/_digests/lion/2026/ to match the pristine layout.
"""

import os
import re
import glob
import json
import hashlib
import pandas as pd
import pymupdf

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PDF_DIR = os.path.join(REPO, 'corpus', '01-brokers', 'lion')
DIGEST_DIR = os.path.join(REPO, 'corpus', '01-brokers', '_digests', 'lion', '2026')
OUT_MD = os.path.join(REPO, 'data', 'extracted', 'md', 'lion')
OUT_SERIES = os.path.join(REPO, 'data', 'extracted', 'series')

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December']

DEM_COUNTRIES = ['Turkey', 'Pakistan', 'India', 'Bangladesh']
DEM_TYPES = ['BULKER', 'TANKER', 'CONT/TWEEN']
TREND_WORDS = {'stable', 'positive', 'firm', 'soft', 'steady', 'negative', 'down', 'weak',
               'strong', 'flat', 'bullish', 'up', 'slow', 'improving', 'weakening'}

SECTION_TOP = {
    'BULKERS': 'BULKERS',
    'TANKERS': 'TANKERS',
    'CONTAINER/MPP/TWEEN': 'CONTAINER-MPP-TWEEN',
    'CONT/TWEEN/MPP': 'CONTAINER-MPP-TWEEN',
    'CONTAINER/MPP': 'CONTAINER-MPP-TWEEN',
    'CONT/MPP/TWEEN': 'CONTAINER-MPP-TWEEN',
    'CONTAINERS': 'CONTAINER-MPP-TWEEN',
    'CONTAINER': 'CONTAINER-MPP-TWEEN',
    'GENERAL CARGO': 'CONTAINER-MPP-TWEEN',
    'DEMOLITION': 'DEMOLITION',
    'GAS': 'GAS',
}
SUB_LABELS = {'GAS', 'TANKERS', 'CONTAINERS', 'REEFERS', 'RO/PAX', 'ROPAX', 'BULKERS',
              'GENERAL CARGO', 'LPG', 'TWEEN', 'MPP'}

VESSEL_LINE = re.compile(r'^(M/V|M/T|C/V|MTS|MT|M/V\.|LPG/C|LPG|S/C|F/V|M/Vs)\s+\S')
COUNTRY_UPPER = ['INDIA', 'PAKISTAN', 'BANGLADESH', 'TURKEY', 'CHINA', 'VIETNAM', 'ALANG',
                 'OMAN', 'KOREA', 'SOUTH KOREA', 'LEBANON', 'EGYPT']
CLASS_WORDS = ['RINA', 'ABS', 'AB', 'NK', 'NKK', 'LR', 'NV', 'BV', 'RI', 'KR', 'DNV', 'CCS',
               'IR', 'RS', 'GL', 'PRS', 'CC', 'IRS', 'BKI', 'ClassNK']

BUYER_WORDS = re.compile(r'buyer|interest|client|charterer|undisclosed|customer|operator|owner|trader|fund', re.I)
BUYER_PAT = re.compile(r'\bto\s+([^,.;]{2,90}?)(?=\s*[-–]\s|\s+(?:for|basis|including|note|and|with|after|attached|@)\b|[,;.]|$)', re.I)


def clean_text(s):
    if not s:
        return ''
    s = s.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u2013', '-').replace('\u2014', '-').replace('\ufffd', '"')
    return s


def parse_date_str(s):
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', s)
    if not m:
        return None
    d, mon, y = int(m.group(1)), m.group(2).capitalize(), int(m.group(3))
    if mon in MONTHS:
        return f"{y:04d}-{MONTHS.index(mon)+1:02d}-{d:02d}"
    return None


def money(s):
    s = s.strip()
    if re.match(r'^\d{1,3},\d{1,2}$', s):
        return float(s.replace(',', '.'))
    return float(s.replace(',', ''))


def parse_demometer_block(text, issue_date, week):
    m = re.search(r'LION[\'’]S DEMOMETER\s*\((?:USD\s*\$?\s*/\s*(?:LT|LDT))\)', text, re.I)
    if not m:
        m = re.search(r'DEMOMETER', text, re.I)
        if not m:
            return [], []
    start = m.start()
    end_candidates = []
    for term in [r'REPRESENTATIVE SALES', r'LEGAL DISCLAIMER', r'Should you have', r'M/V\s', r'M/T\s', r'© Lion Research']:
        mt = re.search(term, text[start:], re.I)
        if mt:
            end_candidates.append(start + mt.start())
    end = min(end_candidates) if end_candidates else start + 800
    block = text[start:end]

    table_rows = []
    series_rows = []
    for c in DEM_COUNTRIES:
        pat = rf'\b{c.upper()}\b\s*[:\s]?\s*(.*?)(?=\b(?:TURKEY|PAKISTAN|INDIA|BANGLADESH)\b|\n\s*\n|©|REPRESENTATIVE|$)'
        mc = re.search(pat, block, re.S | re.I)
        if mc:
            raw_vals = mc.group(1).strip()
            raw_vals = re.sub(r'(\d+)\s*[-–~]\s*(\d+)', r'\1-\2', raw_vals)
            toks = [t.strip() for t in raw_vals.split() if t.strip()]
            trend = ''
            val_toks = []
            for t in toks:
                if t.lower().strip('.,/-') in TREND_WORDS:
                    trend = (trend + ' ' + t.lower().strip('.,/-')).strip()
                elif re.match(r'^[\d.\-–~]+$', t) or t in ('-', '--'):
                    val_toks.append(t)

            b_val = val_toks[0] if len(val_toks) > 0 else '-'
            t_val = val_toks[1] if len(val_toks) > 1 else '-'
            c_val = val_toks[2] if len(val_toks) > 2 else '-'
            trend_str = trend.capitalize() if trend else 'Steady'

            table_rows.append({
                'country': c,
                'bulker': b_val,
                'tanker': t_val,
                'cont_tween': c_val,
                'trend': trend_str
            })

            # Series records
            for seg, v_str in [('BULKER', b_val), ('TANKER', t_val), ('CONT/TWEEN', c_val)]:
                lo, hi, pt = None, None, None
                if v_str not in ('-', '--', ''):
                    rm = re.match(r'^(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)$', v_str)
                    if rm:
                        lo, hi = float(rm.group(1)), float(rm.group(2))
                        pt = round((lo + hi) / 2.0, 2)
                    else:
                        sm = re.match(r'^(\d+(?:\.\d+)?)$', v_str)
                        if sm:
                            lo = hi = pt = float(sm.group(1))
                series_rows.append({
                    'issue_date': issue_date,
                    'report_week': week,
                    'country': c,
                    'vessel_type': seg,
                    'price_low': lo,
                    'price_high': hi,
                    'price_point': pt,
                    'trend': trend_str,
                    'unit': 'USD_per_LDT'
                })
    return table_rows, series_rows


def parse_specs(specs):
    f = {'dwt': None, 'ldt': None, 'built_year': None, 'yard': None,
         'country': None, 'class': None, 'ss_due': None, 'dd_due': None}
    if not specs:
        return f
    s = ' '.join(specs.split())
    # LDT
    m = re.search(r'\bLDT\s*[:]?\s*([\d,]+)', s, re.I)
    if m:
        c_ldt = m.group(1).replace(',', '').strip()
        if c_ldt.isdigit():
            f['ldt'] = int(c_ldt)
    s_no_ldt = re.sub(r'\bLDT\s*[:]?\s*[\d,]+', ' ', s, flags=re.I)
    m = re.search(r'(?:ABT\s+)?([\d][\d,]{3,})\s*dwt', s_no_ldt, re.I)
    if m:
        c_dwt = m.group(1).replace(',', '').strip()
        if c_dwt.isdigit():
            f['dwt'] = int(c_dwt)
    m = re.search(r'\bblt\.?\s*(\d{4})', s, re.I)
    if m:
        f['built_year'] = int(m.group(1))
        base_end = m.end()
    else:
        m = re.search(r'\bbuilt\s*(?:in\s*)?(\d{4})', s, re.I)
        if m:
            f['built_year'] = int(m.group(1))
            base_end = m.end()
        else:
            base_end = None
    if base_end:
        tail = s[base_end:base_end + 70].strip(' ,')
        for ch in tail.split(','):
            ch = ch.strip(' .)')
            if not ch:
                continue
            mm = re.match(r'^([A-Za-z0-9\.\&\'\- ]{2,45}?)\s*/\s*([A-Za-z\. ]{2,25})$', ch)
            if mm:
                f['yard'] = mm.group(1).strip()
                f['country'] = mm.group(2).strip()
            break
    for w in CLASS_WORDS:
        if re.search(r'(?:^|[,\s(])' + re.escape(w) + r'(?=[\s,/)]|$)', s):
            f['class'] = 'ABS' if w == 'AB' else w
            break
    m = re.search(r'\bss\s*/?\s*dd\s*(?:due|passed|freshly passed)\s*(?:SS\s*)?(\d{2}/\d{2,4})', s, re.I)
    if m:
        f['ss_due'] = f['dd_due'] = m.group(1)
    else:
        m = re.search(r'\bss\s*(?:due|passed|freshly passed)\s*(\d{2}/\d{2,4})', s, re.I)
        if m:
            f['ss_due'] = m.group(1)
        m = re.search(r'\bdd\s*(?:due|passed|freshly passed)\s*(\d{2}/\d{2,4})', s, re.I)
        if m:
            f['dd_due'] = m.group(1)
    return f


def parse_deal_line(section, sub_section, text):
    text = clean_text(text).strip()
    m = re.match(r'^(M/V|M/T|C/V|MTS|MT|M/V\.|LPG/C|LPG|S/C|F/V)\s+(.+)', text, re.S)
    if not m:
        return None
    tag, rest = m.group(1), m.group(2).strip()
    ipar = rest.find('(')
    if ipar >= 0:
        name = rest[:ipar].strip(' -–"')
        mc = re.match(r'\(([^()]*)\)', rest[ipar:], re.S)
        specs = mc.group(1) if mc else ''
        tail = rest[ipar + len(specs) + 2:].strip()
    else:
        md = re.match(r'^(.{2,60}?)\s+[-–]\s+(.*)$', rest, re.S)
        if md:
            name, tail = md.group(1).strip(), md.group(2).strip()
            specs = ''
        else:
            name, specs, tail = rest, '', ''

    f = parse_specs(specs)

    price_usd_m = None
    price_per_lt = None
    price_raw = None
    en_bloc = bool(re.search(r'\ben\s+bloc\b', tail, re.I))

    pm = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*mill', tail, re.I)
    if pm:
        price_usd_m = money(pm.group(1))
        price_raw = pm.group(0)
    else:
        pm_nd = re.search(r'(?:Sold|Committed|region|excess)\s*(?:for\s+)?(?:region\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*mill', tail, re.I)
        if pm_nd:
            price_usd_m = money(pm_nd.group(1))
            price_raw = f"${price_usd_m}M"
        else:
            p_lt = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:per\s*(?:LT|L\.?T\.?|LDT)|as-is)', tail, re.I)
            if p_lt:
                price_per_lt = money(p_lt.group(1))
                price_raw = p_lt.group(0)

    # Buyer & Dest
    buyer = None
    dest_country = None
    for bm in BUYER_PAT.finditer(tail):
        cand = bm.group(1).strip()
        if BUYER_WORDS.search(cand):
            tail_b = tail[bm.end():]
            pm_b = re.match(r'\s*(\([^)]*\))', tail_b)
            if pm_b:
                cand = cand + ' ' + pm_b.group(1).strip()
            buyer = ' '.join(cand.split()).strip(' .')
            break

    for c in COUNTRY_UPPER:
        if re.search(r'\b(?:to|as-is|destination)\s+' + re.escape(c) + r'\b', tail, re.I):
            dest_country = c.capitalize()
            break

    deal_kind = 'demo' if (section == 'DEMOLITION' or price_per_lt is not None) else 'sold'

    nm = re.search(r'note:\s*(.+)', tail, re.I)
    clean_notes = nm.group(1).strip() if nm else tail.strip('- ')

    return {
        'section': section,
        'sub_section': sub_section,
        'tag': tag,
        'vessel': name,
        'dwt': f['dwt'],
        'ldt': f['ldt'],
        'built_year': f['built_year'],
        'yard': f['yard'],
        'country': f['country'],
        'class': f['class'],
        'ss_due': f['ss_due'],
        'dd_due': f['dd_due'],
        'price_usd_m': price_usd_m,
        'price_per_lt': price_per_lt,
        'price_raw': price_raw,
        'en_bloc': en_bloc,
        'buyer': buyer,
        'dest_country': dest_country,
        'deal_kind': deal_kind,
        'specs_raw': specs,
        'tail_raw': tail,
        'comments': clean_notes
    }


def split_report_deals(text):
    text = clean_text(text)
    m_sales = re.search(r'REPRESENTATIVE SALES', text, re.I)
    if not m_sales:
        return []
    body = text[m_sales.end():]
    m_disc = re.search(r'LEGAL DISCLAIMER', body, re.I)
    if m_disc:
        body = body[:m_disc.start()]

    lines = [l.strip() for l in body.split('\n') if l.strip()]
    records = []
    section = 'BULKERS'
    sub_section = None
    cur_lines = []

    for ln in lines:
        up = ln.rstrip(':').strip().upper()
        if section == 'DEMOLITION' and up in SUB_LABELS:
            if cur_lines:
                records.append((section, sub_section, ' '.join(cur_lines)))
                cur_lines = []
            sub_section = up
            continue
        if up in SECTION_TOP:
            if cur_lines:
                records.append((section, sub_section, ' '.join(cur_lines)))
                cur_lines = []
            section = SECTION_TOP[up]
            sub_section = None
            continue

        m_inline = re.match(r'^([A-Za-z/ ]+):\s*((?:M/V|M/T|C/V|MTS|MT|LPG/C|LPG|S/C|F/V)\s+.+)', ln, re.I)
        if m_inline and m_inline.group(1).strip().upper() in SUB_LABELS:
            if section == 'DEMOLITION':
                sub_section = m_inline.group(1).strip().upper()
            ln = m_inline.group(2)

        if VESSEL_LINE.match(ln):
            if cur_lines:
                records.append((section, sub_section, ' '.join(cur_lines)))
                cur_lines = []
            cur_lines.append(ln)
        else:
            if cur_lines:
                if re.match(r'^\d{1,2}$', ln):
                    continue
                if re.match(r'^(?:TURKEY|PAKISTAN|INDIA|BANGLADESH)\s+[\d\-]', ln, re.I):
                    continue
                if re.search(r'© Lion Research|www\.lionshipbrokers|Should you have|Tel:|DEMOMETER|COUNTRY\s+BULKER|LEGAL DISCLAIMER|This report has been produced', ln, re.I):
                    continue
                cur_lines.append(ln)

    if cur_lines:
        records.append((section, sub_section, ' '.join(cur_lines)))

    parsed_deals = []
    for sec, sub, raw_d in records:
        d = parse_deal_line(sec, sub, raw_d)
        if d:
            parsed_deals.append(d)

    # resolve en bloc
    for i in range(len(parsed_deals) - 1, -1, -1):
        cur = parsed_deals[i]
        if cur['en_bloc'] and (cur['price_usd_m'] or cur['price_per_lt']):
            j = i - 1
            while j >= 0 and parsed_deals[j]['section'] == cur['section']:
                prev = parsed_deals[j]
                if prev['price_usd_m'] is None and prev['price_per_lt'] is None:
                    prev['price_usd_m'] = cur['price_usd_m']
                    prev['price_per_lt'] = cur['price_per_lt']
                    prev['price_raw'] = cur['price_raw']
                    prev['buyer'] = prev['buyer'] or cur['buyer']
                    prev['dest_country'] = prev['dest_country'] or cur['dest_country']
                    prev['en_bloc'] = True
                    j -= 1
                else:
                    break

    return parsed_deals


def extract_full_report(text, source_path, pages_count=1):
    text = clean_text(text)
    stem = os.path.splitext(os.path.basename(source_path))[0]

    m_week = re.search(r'WEEK\s*(\d{1,2}(?:\s*(?:&|-|and)\s*\d{1,2})?)[^\d\n]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.I)
    if m_week:
        week_num_str = m_week.group(1).split('&')[0].split('-')[0].strip()
        week_int = int(week_num_str)
        date_str = parse_date_str(m_week.group(2))
        raw_date_display = m_week.group(2).strip()
    else:
        m_st = re.search(r'W(\d{2})', stem)
        week_int = int(m_st.group(1)) if m_st else 0
        date_str = parse_date_str(stem)
        raw_date_display = date_str

    year = int(date_str.split('-')[0]) if date_str else 2026

    # Quote of the week
    m_quote = re.search(r'(?:Quote|Joke) of the week:\s*\n*(.*?)(?=\n\s*MARKET COMMENTARY|\n\s*Bulkers:|\n\s*Tankers:)', text, re.S | re.I)
    quote_text = ""
    quote_author = ""
    is_joke = bool(re.search(r'Joke of the week', text[:1500], re.I))
    if m_quote:
        q_raw = m_quote.group(1).strip()
        q_lines = [l.strip() for l in q_raw.split('\n') if l.strip() and not re.search(r'chartering@|Tel:|Visit our', l)]
        if len(q_lines) >= 2:
            quote_text = q_lines[0].strip('"\';-– ')
            quote_author = ' '.join(q_lines[1:]).strip('"\';-– ')
        elif len(q_lines) == 1:
            quote_text = q_lines[0].strip('"\';-– ')

    # Market Commentary
    m_comm = re.search(r'MARKET COMMENTARY\s*\n*(.*?)(?=\n\s*LION[\'’]S DEMOMETER|\n\s*REPRESENTATIVE SALES)', text, re.S | re.I)
    comm_raw = m_comm.group(1).strip() if m_comm else ''
    
    comm_clean = re.sub(r'Should you have any comments.*?Visit our homepage.*?\n', '', comm_raw, flags=re.S | re.I)
    comm_clean = re.sub(r'LION SHIPBROKERS LIMITED.*?\n', '', comm_clean, flags=re.I)
    comm_clean = re.sub(r'Dry Cargo Chartering.*?\n', '', comm_clean, flags=re.I)
    comm_clean = re.sub(r'Container Chartering.*?\n', '', comm_clean, flags=re.I)
    comm_clean = re.sub(r'Sale & Purchase/Demolition.*?\n', '', comm_clean, flags=re.I)
    comm_clean = re.sub(r'Research & Valuations.*?\n', '', comm_clean, flags=re.I)

    comm_sections = {}
    pats = [
        ('bulkers', r'(?:^|\n)\s*(?:Bulkers|Dry\s*bulk)\s*:\s*'),
        ('tankers', r'(?:^|\n)\s*(?:Tankers|Wet)\s*:\s*'),
        ('demolition', r'(?:^|\n)\s*(?:Demolition|Recycling)\s*:\s*'),
    ]
    matches = []
    for key, p in pats:
        for m in re.finditer(p, comm_clean, re.I):
            matches.append((m.start(), m.end(), key))
    matches.sort()

    lead_overview = ""
    if matches:
        lead_overview = comm_clean[:matches[0][0]].strip()
    else:
        lead_overview = comm_clean.strip()
    lead_overview = re.sub(r'^(?:Quote|Joke) of the week:.*?\n', '', lead_overview, flags=re.S | re.I).strip()
    comm_sections['overview'] = lead_overview

    for idx, (st_idx, end_idx, key) in enumerate(matches):
        nxt_st = matches[idx + 1][0] if idx + 1 < len(matches) else len(comm_clean)
        comm_sections[key] = comm_clean[end_idx:nxt_st].strip()

    bdi_indices = []
    bdi_matches = re.findall(r'(Baltic\s+[A-Za-z]+\s+Index)\s+([\d,]+)\s+([+\-–]?\s*[\d,]+)', comm_clean, re.I)
    for b_name, b_val, b_chg in bdi_matches:
        bdi_indices.append({
            'index_name': ' '.join(b_name.split()),
            'value': int(b_val.replace(',', '')),
            'change': b_chg.strip()
        })

    dem_table, dem_series = parse_demometer_block(text, date_str, week_int)
    deals = split_report_deals(text)

    secondhand_deals = [d for d in deals if d['deal_kind'] == 'sold']
    demo_deals = [d for d in deals if d['deal_kind'] == 'demo']

    return {
        'stem': stem,
        'source_path': source_path,
        'pages_count': pages_count,
        'issue_date': date_str,
        'raw_date_display': raw_date_display,
        'report_week': week_int,
        'year': year,
        'is_joke': is_joke,
        'quote_text': quote_text,
        'quote_author': quote_author,
        'commentary': comm_sections,
        'baltic_indices': bdi_indices,
        'demometer_table': dem_table,
        'demometer_series': dem_series,
        'secondhand_deals': secondhand_deals,
        'demo_deals': demo_deals,
        'all_deals': deals
    }


def render_markdown(doc_data):
    w = doc_data['report_week']
    d_str = doc_data['issue_date']
    yr = doc_data['year']
    raw_date = doc_data['raw_date_display']
    deals_count = len(doc_data['all_deals'])
    source_rel = os.path.relpath(doc_data['source_path'], REPO).replace(os.sep, '/')

    quote_type = "Joke of the Week" if doc_data['is_joke'] else "Quote of the Week"

    md = []
    md.append("---")
    md.append(f'title: "Lion Shipbrokers Weekly Market Report - Week {w:02d}, {yr}"')
    md.append(f'issue_date: "{d_str}"')
    md.append(f'report_week: {w}')
    md.append(f'year: {yr}')
    md.append('broker: "Lion Shipbrokers"')
    md.append('source: "lion"')
    if doc_data['quote_text']:
        q_esc = doc_data['quote_text'].replace('"', '\\"')
        md.append(f'quote_of_the_week: "{q_esc}"')
    if doc_data['quote_author']:
        a_esc = doc_data['quote_author'].replace('"', '\\"')
        md.append(f'quote_author: "{a_esc}"')
    md.append(f'source_file: "{source_rel}"')
    md.append(f'pages: {doc_data["pages_count"]}')
    md.append(f'deals_count: {deals_count}')
    md.append(f'demometer_rows: {len(doc_data["demometer_table"])}')
    md.append("---\n")

    md.append(f"# Lion Shipbrokers Weekly Market Report — Week {w:02d} ({raw_date})\n")
    md.append(f"**Broker**: Lion Shipbrokers Limited (Athens, Greece)  ")
    md.append(f"**Issue Date**: {d_str} | **Report Week**: Week {w:02d}, {yr}  \n")

    # Quote of the week
    if doc_data['quote_text']:
        md.append(f"## {quote_type}\n")
        md.append(f"> \"{doc_data['quote_text']}\"")
        if doc_data['quote_author']:
            md.append(f">\n> — **{doc_data['quote_author']}**\n")
        else:
            md.append("\n")

    # Market Commentary
    md.append("## Market Commentary\n")
    comm = doc_data['commentary']

    if 'overview' in comm and comm['overview']:
        md.append(f"{comm['overview']}\n\n")

    for key, title in [('tankers', 'Tankers'), ('bulkers', 'Bulkers'), ('demolition', 'Demolition')]:
        if key in comm and comm[key]:
            md.append(f"### {title}\n")
            body_text = comm[key]
            if key == 'bulkers' and doc_data['baltic_indices']:
                body_text = re.sub(r'Baltic\s+[A-Za-z]+\s+Index\s+[\d,]+\s+[+\-–]?\s*[\d,]+', '', body_text)
                body_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', body_text).strip()
            md.append(f"{body_text}\n")
            if key == 'bulkers' and doc_data['baltic_indices']:
                md.append("#### Baltic Dry Indices\n")
                md.append("| Index | Current Value | Change |")
                md.append("|:---|:---:|:---:|")
                for bi in doc_data['baltic_indices']:
                    md.append(f"| {bi['index_name']} | {bi['value']:,} | {bi['change']} |")
                md.append("\n")

    # Demometer Table
    md.append("## Lion's Demometer (USD $ / LT)\n")
    if doc_data['demometer_table']:
        md.append("| Country | Bulker ($/LT) | Tanker ($/LT) | Cont / Tween ($/LT) | Trend |")
        md.append("|:---|:---:|:---:|:---:|:---:|")
        for dr in doc_data['demometer_table']:
            md.append(f"| **{dr['country']}** | {dr['bulker']} | {dr['tanker']} | {dr['cont_tween']} | {dr['trend']} |")
        md.append("\n")
    else:
        md.append("*No Demometer table published for this issue.*\n")

    # Representative Sales Tables
    md.append("## Representative Sales\n")
    sh_deals = doc_data['secondhand_deals']
    if sh_deals:
        by_sec = {}
        for d in sh_deals:
            sec = d['section']
            if sec not in by_sec:
                by_sec[sec] = []
            by_sec[sec].append(d)

        sec_order = ['BULKERS', 'TANKERS', 'CONTAINER-MPP-TWEEN', 'GAS']
        for sec in sec_order:
            if sec in by_sec:
                sec_title = 'Container / MPP / Tween' if sec == 'CONTAINER-MPP-TWEEN' else sec.capitalize()
                md.append(f"### {sec_title}\n")
                md.append("| Vessel | DWT | Built | Yard | Price | Buyer | Comments & Details |")
                md.append("|:---|---:|:---:|:---|:---|:---|:---|")
                for d in by_sec[sec]:
                    v_name = f"{d['tag']} {d['vessel']}".strip()
                    dwt_str = f"{d['dwt']:,}" if d['dwt'] else "-"
                    blt_str = f"{d['built_year']}" if d['built_year'] else "-"
                    yard_str = f"{d['yard']} / {d['country']}" if (d['yard'] and d['country']) else (d['yard'] or d['country'] or "-")
                    price_str = f"${d['price_usd_m']}M" if d['price_usd_m'] else "-"
                    buyer_str = d['buyer'] or "Undisclosed"
                    comm_str = d['comments'].replace('|', '/') if d['comments'] else "-"
                    md.append(f"| **{v_name}** | {dwt_str} | {blt_str} | {yard_str} | {price_str} | {buyer_str} | {comm_str} |")
                md.append("\n")
    else:
        md.append("*No secondhand sales reported this week.*\n")

    # Demolition Sales Table
    md.append("## Demolition Sales\n")
    dm_deals = doc_data['demo_deals']
    if dm_deals:
        md.append("| Vessel | Type | DWT | LDT | Built | Yard | Price ($/LT) | Destination | Comments / Terms |")
        md.append("|:---|:---|---:|---:|:---:|:---|:---|:---|:---|")
        for d in dm_deals:
            v_name = f"{d['tag']} {d['vessel']}".strip()
            v_type = d['sub_section'].capitalize() if d['sub_section'] else "Vessel"
            dwt_str = f"{d['dwt']:,}" if d['dwt'] else "-"
            ldt_str = f"{d['ldt']:,}" if d['ldt'] else "-"
            blt_str = f"{d['built_year']}" if d['built_year'] else "-"
            yard_str = f"{d['yard']} / {d['country']}" if (d['yard'] and d['country']) else (d['yard'] or d['country'] or "-")
            price_str = f"${d['price_per_lt']:.0f}/lt" if d['price_per_lt'] else "-"
            dest_str = d['dest_country'].capitalize() if d['dest_country'] else "Subcontinent"
            comm_str = d['comments'].replace('|', '/') if d['comments'] else "-"
            md.append(f"| **{v_name}** | {v_type} | {dwt_str} | {ldt_str} | {blt_str} | {yard_str} | {price_str} | {dest_str} | {comm_str} |")
        md.append("\n")
    else:
        md.append("*No demolition sales reported this week.*\n")

    # Full Narratives
    md.append("## Deal Narratives & Commercial Details\n")
    if doc_data['all_deals']:
        cur_sec = None
        for d in doc_data['all_deals']:
            sec_name = d['section']
            if sec_name != cur_sec:
                cur_sec = sec_name
                sec_disp = 'Container / MPP / Tween' if cur_sec == 'CONTAINER-MPP-TWEEN' else cur_sec.capitalize()
                md.append(f"### {sec_disp}\n")
            full_line = f"{d['tag']} {d['vessel']}"
            if d['specs_raw']:
                full_line += f" ({d['specs_raw']})"
            if d['tail_raw']:
                full_line += f" {d['tail_raw']}"
            md.append(f"- **{d['tag']} {d['vessel']}**: {full_line.strip()}\n")
    md.append("\n")

    return '\n'.join(md)


def build_sidecar_json(doc_data):
    sh_sidecar = []
    for d in doc_data['secondhand_deals']:
        sh_sidecar.append({
            'issue_date': doc_data['issue_date'],
            'report_week': doc_data['report_week'],
            'section': d['section'],
            'tag': d['tag'],
            'vessel': d['vessel'],
            'dwt': d['dwt'],
            'built_year': d['built_year'],
            'yard': d['yard'],
            'country_built': d['country'],
            'class': d['class'],
            'ss_due': d['ss_due'],
            'dd_due': d['dd_due'],
            'price_usd_m': d['price_usd_m'],
            'price_raw': d['price_raw'],
            'en_bloc': d['en_bloc'],
            'buyer': d['buyer'],
            'comments': d['comments']
        })

    demo_sidecar = []
    for d in doc_data['demo_deals']:
        demo_sidecar.append({
            'issue_date': doc_data['issue_date'],
            'report_week': doc_data['report_week'],
            'section': d['section'],
            'sub_section': d['sub_section'],
            'tag': d['tag'],
            'vessel': d['vessel'],
            'dwt': d['dwt'],
            'ldt': d['ldt'],
            'built_year': d['built_year'],
            'yard': d['yard'],
            'country_built': d['country'],
            'price_usd_per_lt': d['price_per_lt'],
            'price_raw': d['price_raw'],
            'destination': d['dest_country'],
            'comments': d['comments']
        })

    return {
        'issue_date': doc_data['issue_date'],
        'report_week': doc_data['report_week'],
        'year': doc_data['year'],
        'quote_of_the_week': {
            'type': "Joke of the Week" if doc_data['is_joke'] else "Quote of the Week",
            'quote': doc_data['quote_text'],
            'author': doc_data['quote_author']
        },
        'market_commentary': doc_data['commentary'],
        'baltic_indices': doc_data['baltic_indices'],
        'tables': {
            'demometer': doc_data['demometer_series'],
            'secondhand_sales': sh_sidecar,
            'demolition_sales': demo_sidecar
        }
    }


def main():
    os.makedirs(OUT_MD, exist_ok=True)
    os.makedirs(OUT_SERIES, exist_ok=True)

    # 1. Gather all 43 PDFs
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, '*', '*.pdf')))
    # Dedup byte-identical PDFs: the same issue is sometimes collected under two
    # filename conventions (e.g. lion_2026_W40_... and lion_02_10_2026_...), which
    # otherwise double-parse every row of that issue.
    _seen_hash = {}
    _uniq = []
    for _p in pdfs:
        with open(_p, 'rb') as _f:
            _h = hashlib.sha256(_f.read()).hexdigest()
        if _h in _seen_hash:
            print(f"  [dup-input] skipping byte-identical copy: {os.path.basename(_p)} == {os.path.basename(_seen_hash[_h])}")
            continue
        _seen_hash[_h] = _p
        _uniq.append(_p)
    pdfs = _uniq
    # 2. Gather W37 and W38 digests
    digest_w37 = os.path.join(DIGEST_DIR, 'lion_12_09_2026_lion_weekly_market_report_week_37_2026.md')
    digest_w38 = os.path.join(DIGEST_DIR, 'lion_18_09_2026_lion_weekly_market_report_week_38_2026.md')

    all_jobs = [(p, 'pdf') for p in pdfs]
    if os.path.exists(digest_w37):
        all_jobs.append((digest_w37, 'digest_w37'))
    if os.path.exists(digest_w38):
        all_jobs.append((digest_w38, 'digest_w38'))

    print(f"Executing Lion extraction across {len(all_jobs)} total issues...")

    all_demometer_series = []
    all_secondhand_series = []
    all_demo_series = []
    all_deals_series = []

    for src_path, kind in all_jobs:
        if kind == 'pdf':
            doc = pymupdf.open(src_path)
            text = '\n'.join(p.get_text() for p in doc)
            pages_count = len(doc)
            stem = os.path.splitext(os.path.basename(src_path))[0]
        elif kind == 'digest_w37':
            raw_path = os.path.join(REPO, 'scratch', 'lion', 'raw', 'w37_raw.md')
            read_path = raw_path if os.path.exists(raw_path) else src_path
            with open(read_path, encoding='utf-8') as f:
                text = f.read()
            pages_count = 3
            stem = 'lion_2026_W37_Lion-Weekly-Report-11-September-2026-W37'
        elif kind == 'digest_w38':
            raw_path = os.path.join(REPO, 'scratch', 'lion', 'raw', 'w38_raw.md')
            read_path = raw_path if os.path.exists(raw_path) else src_path
            with open(read_path, encoding='utf-8') as f:
                text = f.read()
            pages_count = 3
            stem = 'lion_2026_W38_Lion-Weekly-Report-18-September-2026-W38'

        doc_data = extract_full_report(text, src_path, pages_count)
        doc_data['stem'] = stem
        rendered_md = render_markdown(doc_data)
        sidecar_json = build_sidecar_json(doc_data)

        # Write to data/extracted/md/lion/
        md_out_path = os.path.join(OUT_MD, f"{stem}.md")
        json_out_path = os.path.join(OUT_MD, f"{stem}.tables.json")

        with open(md_out_path, 'w', encoding='utf-8') as f:
            f.write(rendered_md)

        with open(json_out_path, 'w', encoding='utf-8') as f:
            json.dump(sidecar_json, f, indent=2)

        # Also update the digest file in corpus/01-brokers/_digests/lion/2026/ for W37 / W38
        if kind in ('digest_w37', 'digest_w38'):
            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(rendered_md)
        else:
            w_match = re.search(r'W(\d{2})', stem)
            if w_match:
                w_str = w_match.group(1)
                matching_digests = glob.glob(os.path.join(DIGEST_DIR, f'*week_{w_str}_*.md'))
                for md_f in matching_digests:
                    with open(md_f, 'w', encoding='utf-8') as f:
                        f.write(rendered_md)

        # Collect rows for series CSVs
        all_demometer_series.extend(doc_data['demometer_series'])

        for d in doc_data['secondhand_deals']:
            all_secondhand_series.append({
                'issue_date': doc_data['issue_date'],
                'report_week': doc_data['report_week'],
                'section': d['section'],
                'tag': d['tag'],
                'vessel': d['vessel'],
                'dwt': d['dwt'],
                'built_year': d['built_year'],
                'yard': d['yard'],
                'country_built': d['country'],
                'class': d['class'],
                'ss_due': d['ss_due'],
                'dd_due': d['dd_due'],
                'price_usd_m': d['price_usd_m'],
                'price_raw': d['price_raw'],
                'en_bloc': d['en_bloc'],
                'buyer': d['buyer'],
                'comments': d['comments'],
                'source_file': os.path.relpath(src_path, REPO).replace(os.sep, '/')
            })

        for d in doc_data['demo_deals']:
            all_demo_series.append({
                'issue_date': doc_data['issue_date'],
                'report_week': doc_data['report_week'],
                'section': d['section'],
                'sub_section': d['sub_section'],
                'tag': d['tag'],
                'vessel': d['vessel'],
                'dwt': d['dwt'],
                'ldt': d['ldt'],
                'built_year': d['built_year'],
                'yard': d['yard'],
                'country_built': d['country'],
                'price_usd_per_lt': d['price_per_lt'],
                'price_raw': d['price_raw'],
                'destination': d['dest_country'],
                'comments': d['comments'],
                'source_file': os.path.relpath(src_path, REPO).replace(os.sep, '/')
            })

        for d in doc_data['all_deals']:
            all_deals_series.append({
                'issue_date': doc_data['issue_date'],
                'report_week': doc_data['report_week'],
                'section': d['section'],
                'sub_section': d['sub_section'],
                'deal_kind': d['deal_kind'],
                'tag': d['tag'],
                'vessel': d['vessel'],
                'dwt': d['dwt'],
                'ldt': d['ldt'],
                'built_year': d['built_year'],
                'yard': d['yard'],
                'country_built': d['country'],
                'class': d['class'],
                'price_usd_m': d['price_usd_m'],
                'price_per_lt': d['price_per_lt'],
                'price_raw': d['price_raw'],
                'en_bloc': d['en_bloc'],
                'buyer': d['buyer'],
                'destination': d['dest_country'],
                'comments': d['comments'],
                'source_file': os.path.relpath(src_path, REPO).replace(os.sep, '/')
            })

        print(f"Processed {stem}: dem={len(doc_data['demometer_table'])} rows, sales={len(doc_data['secondhand_deals'])}, demo={len(doc_data['demo_deals'])}")

    # Remove obsolete / reprint file if exists
    bad_md = os.path.join(OUT_MD, 'lion_2024_W31_Market-report-Week-31.md')
    bad_json = os.path.join(OUT_MD, 'lion_2024_W31_Market-report-Week-31.tables.json')
    if os.path.exists(bad_md):
        os.remove(bad_md)
    if os.path.exists(bad_json):
        os.remove(bad_json)

    # Save series CSVs
    df_dem = pd.DataFrame(all_demometer_series).sort_values(['issue_date', 'country', 'vessel_type']).reset_index(drop=True)
    df_sh = pd.DataFrame(all_secondhand_series).sort_values(['issue_date', 'section', 'vessel']).reset_index(drop=True)
    df_dm = pd.DataFrame(all_demo_series).sort_values(['issue_date', 'vessel']).reset_index(drop=True)
    df_deals = pd.DataFrame(all_deals_series).sort_values(['issue_date', 'section', 'vessel']).reset_index(drop=True)

    df_dem.to_csv(os.path.join(OUT_SERIES, 'lion_demometer_series.csv'), index=False)
    df_sh.to_csv(os.path.join(OUT_SERIES, 'lion_sales_series.csv'), index=False)
    df_dm.to_csv(os.path.join(OUT_SERIES, 'lion_demo_sales_series.csv'), index=False)
    df_deals.to_csv(os.path.join(OUT_SERIES, 'lion_deals_series.csv'), index=False)

    print("\n--- Summary of Extraction ---")
    print(f"Total reports processed: {len(all_jobs)}")
    print(f"lion_demometer_series.csv: {len(df_dem)} rows")
    print(f"lion_sales_series.csv: {len(df_sh)} rows")
    print(f"lion_demo_sales_series.csv: {len(df_dm)} rows")
    print(f"lion_deals_series.csv: {len(df_deals)} rows")
    print(f"MD files written to: {OUT_MD}")
    print(f"JSON sidecars written to: {OUT_MD}")


if __name__ == '__main__':
    main()
