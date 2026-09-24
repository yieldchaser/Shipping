"""Lion Shipbrokers - per-source extraction pipeline (source 9).

WHAT THIS SOURCE IS (measured: docs/lion_survey.md, docs/lion_verdict.md):
  * 44 PDFs, 2-4 pages each. One 20-page 2024 digest is NOT a Lion weekly - it is
    a star-asia reprint and is skipped by the report-date gate.
  * TWO deliverables per weekly issue:
      1. LION'S DEMOMETER (USD $/LT) - a real printed table, 4 countries x 3
         vessel types + a trend word -> 12 rows/issue.
      2. REPRESENTATIVE SALES - borderless deal NARRATIVES (prose), one vessel per
         record, split BULKERS / TANKERS / CONTAINER-MPP-TWEEN / DEMOLITION.
  * The Baltic index block on page 0 is a RESTATEMENT of a public index already
    held in data/indices/bdiy_historical.csv -> deliberately NOT extracted.
  * Numbers are ISO (29,580 = 29580); European comma-decimals appear only in rare
    tokens such as '$ 37,25 mill'.

TEXT SOURCE: pymupdf get_text(sort=True) per page, pages joined with
'<<<PAGEBREAK>>>', footer/disclaimer lines dropped, per-line whitespace
collapsed. Verified identical to the original scratch text cache on 43/44 docs
(the exception is the skipped 2024 digest).

Run: python scripts/extract/publishers/run_lion.py [--rebuild-txt]
"""
import argparse
import collections
import glob
import json
import os
import re

import pandas as pd
import pymupdf

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
PDF_DIR = os.path.join(REPO, 'corpus', '01-brokers', 'lion')
TXT = os.path.join(REPO, 'scratch', 'lion', 'txt')
SCR = os.path.join(REPO, 'scratch', 'lion')
OUT = os.path.join(REPO, 'data', 'extracted')
DEM_JSONL = os.path.join(SCR, 'demometer.jsonl')
DEAL_JSONL = os.path.join(SCR, 'deals.jsonl')
LOG = os.path.join(SCR, 'parse_log.txt')

logf = open(LOG, 'w', encoding='utf-8')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    logf.write(s + '\n')
    logf.flush()


# ---------------------------------------------------------------- text loading
FOOTER_PAT = re.compile(
    r'^(LION SHIPBROKERS|WEEKLY REPORT|Quote of the week|Unknown\.|MARKET COMMENTARY|'
    r'Should you have any|'
    r'Dry Cargo Chartering|Container Chartering|Sale & Purchase|Research & Valuations|'
    r'Visit our homepage|Tel:|LION SHIPBROKERS LIMITED|'
    r'LEGAL DISCLAIMER|© Lion Research|This report has been produced|in good faith|'
    r'reliance placed|available.. basis|party for any loss|damage, any loss|in connection with|'
    r'duty or otherwise|recommendations as no market analysis|report is intended solely|'
    r'disclosed to, or used|another person or used|maritime newspapers|maritime websites|'
    r'good faith, without|of information of this report|or/and omissions|express of implied|'
    r'third party for any loss|risk\. The information|disclosed to|for any purpose|'
    r'analysis & commentary|disclaimer|^\W*$)', re.I)

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
}
SUB_LABELS = {'GAS', 'TANKERS', 'CONTAINERS', 'REEFERS', 'RO/PAX', 'ROPAX', 'BULKERS',
              'GENERAL CARGO', 'LPG', 'TWEEN', 'MPP'}

VESSEL_LINE = re.compile(r'^(M/V|M/T|C/V|MTS|MT|M/V\.|LPG/C|LPG|S/C|F/V|M/Vs)\s+\S')
HEADING_LINE = re.compile(r'^[A-Z][A-Z0-9/\.\- ]{2,40}:?$')
COUNTRY_UPPER = ['INDIA', 'PAKISTAN', 'BANGLADESH', 'TURKEY', 'CHINA', 'VIETNAM', 'ALANG']

DEM_COUNTRIES = ['TURKEY', 'PAKISTAN', 'INDIA', 'BANGLADESH']
DEM_TYPES = ['BULKER', 'TANKER', 'CONT/TWEEN']
TREND_WORDS = {'stable', 'positive', 'firm', 'soft', 'steady', 'negative', 'down', 'weak',
               'strong', 'bullish', 'up', 'slow', 'softening', 'cautiously', 'optimistic',
               'flat', 'improving', 'weakening', 'firmish', 'softer', 'firmer', 'slowly'}


def normalize_lines(raw):
    out = []
    for ln in raw.split('\n'):
        if ln.strip() == '<<<PAGEBREAK>>>':
            continue
        s = ' '.join(ln.split())
        if not s:
            continue
        if FOOTER_PAT.match(s):
            continue
        out.append(s)
    return out


def report_date(stem):
    m = re.search(r'(\d{1,2})-([A-Za-z]+)-(\d{4})', stem)
    if not m:
        return None
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
              'September', 'October', 'November', 'December']
    d, mon, y = m.group(1), m.group(2), m.group(3)
    if mon.capitalize() not in months:
        return None
    return '%s-%02d-%02d' % (y, months.index(mon.capitalize()) + 1, int(d))


def week_of(stem):
    m = re.search(r'W(\d{2})', stem)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------- demometer
def parse_demometer_value(raw):
    s = raw.strip().rstrip('.').strip()
    if s in ('-', '--', '–', ''):
        return None, None, None, 'dash'
    m = re.match(r'^(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)$', s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return lo, hi, round((lo + hi) / 2, 3), 'range'
    m = re.match(r'^(\d+(?:\.\d+)?)$', s)
    if m:
        v = float(m.group(1))
        return v, v, v, 'single'
    return None, None, None, 'unparsed:' + s


def parse_demometer(raw, stem, rdate):
    header = None
    for pat in (r'DEMOMETER\s*\(USD\s*\$?\s*/\s*(?:LT|LDT)', r'DEMOMETER'):
        m = re.search(pat, raw, re.I)
        if m:
            header = m
            break
    if not header:
        return [], 'no DEMOMETER header'
    start = header.start()
    j = raw.upper().find('REPRESENTATIVE', header.end())
    end = j if j > 0 else min(len(raw), start + 700)
    block = ' '.join(raw[start:end].split())
    block = re.sub(r'COUNTRY\s+BULKER\s+TANKER\s+CONT\s*/?\s*TWEEN\s+TREND', ' ', block, flags=re.I)
    cut = len(block)
    for term in (r'\(Please note', r'REPRESENTATIVE', r'LEGAL DISCLAIMER', r'Should you have',
                 r'\bTel:', r'\bM/V\s', r'\bM/T\s', r'\bC/V\s'):
        mt = re.search(term, block)
        if mt:
            cut = min(cut, mt.start())
    block = block[:cut]
    pat = re.compile(r'(' + '|'.join(DEM_COUNTRIES) + r')\s+(.{2,60}?)(?=\s(?:' + '|'.join(DEM_COUNTRIES) +
                     r')\b|\sShould you have|\sLEGAL DISCLAIMER|\sTel:|$)')
    rows = []
    seen = set()
    for m in pat.finditer(block):
        country = m.group(1).upper()
        rest = m.group(2).strip()
        rest = re.sub(r'(\d)\s*[-–~]\s*(\d)', r'\1-\2', rest)
        toks = rest.split()
        vals, k = [], 0
        while k < len(toks) and len(vals) < 3 and re.match(r'^[\d.]+(?:-[\d.]+)?$|^-$', toks[k]):
            vals.append(toks[k])
            k += 1
        trend = None
        if k < len(toks) and toks[k].lower().strip('.,/-') in TREND_WORDS:
            tw = [toks[k]]
            if k + 1 < len(toks) and toks[k + 1].lower().strip('.,/-') in TREND_WORDS:
                tw.append(toks[k + 1])
            trend = ' '.join(tw).strip(' .,/-')
        leftovers = toks[k + (len(trend.split()) if trend else 0):]
        if leftovers:
            log('  WARN demometer trailing text', stem[:40], country, leftovers[:6])
        key = (country,)
        if key in seen:
            continue
        seen.add(key)
        row = {'report_date': rdate, 'week': week_of(stem), 'issue': stem,
               'country': country, 'trend': trend,
               'trend_raw': m.group(2)[:60] if trend else None}
        if len(vals) < 3:
            log('  WARN demometer short row', stem[:40], country, vals, '|', rest[:60])
        for idx in range(3):
            lo = hi = pt = None
            kind = 'missing'
            if idx < len(vals):
                lo, hi, pt, kind = parse_demometer_value(vals[idx])
            row.update({'vessel_type': DEM_TYPES[idx], 'price_low': lo, 'price_high': hi,
                        'price_point': pt, 'value_kind': kind})
            rows.append(dict(row))
    if len(rows) != 12:
        log('  WARN demometer rows =', len(rows), 'for', stem[:50])
    return rows, (None if rows else 'block yielded 0 rows')


# ----------------------------------------------------------------------- deals
PRICE_START = re.compile(r'[-–]\s*\$|^\$|\bSold\b|\bDemo\b|\bCommitted\b|\bRumoured\b|\bRumored\b|\bUnderstand\b', re.I)
MONEY_ANY = re.compile(r'\$\s*[\d,]')
PER_LT_R = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:[-–~]\s*|\s+to\s+)\$?\s*([\d,]+(?:\.\d+)?)\s*per\s*(?:LT|L\.?T\.?|LDT)\b', re.I)
PER_LT_1 = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*per\s*(?:LT|L\.?T\.?|LDT)\b', re.I)
MILL_R = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:[-–~]\s*(?:or\s*)?\$?\s*|to\s*\$?\s*)([\d,]+(?:\.\d+)?)\s*mill', re.I)
MILL_OR = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*mill\s*(?:-?or-?|/)\s*\$?\s*([\d,]+(?:\.\d+)?)', re.I)
MILL_1 = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*mill', re.I)
# price without a '$' sign: 'Sold en bloc for 35 mill each', 'for region 530 mill'
ND_MILL_R = re.compile(r'\bfor\s+(?:region\s+)?(?:of\s+excess\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:[-–~]\s*|\s+to\s+)\$?\s*([\d,]+(?:\.\d+)?)\s*mill', re.I)
ND_MILL_1 = re.compile(r'\bfor\s+(?:region\s+)?(?:of\s+excess\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*mill', re.I)
QUALIFIER = re.compile(r'\b(region\s+(?:high|low)|of\s+excess|excess|high|low|either)\b[^$]{0,14}?\$', re.I)
NOTE_PAT = re.compile(r'\bnote:s?\s*(.+)', re.I | re.S)
BUYER_PAT = re.compile(r'\bto\s+([^,.;]{2,90}?)(?=\s*[-–]\s|\s+(?:for|basis|including|note|and|with|after|attached|@)\b|[,;.]|$)', re.I)
BUYER_WORDS = re.compile(r'buyer|interest|client|charterer|undisclosed|customer|operator|owner|trader|fund', re.I)
DEMO_VERB = re.compile(r'\bDemo\b|sold for demo|\bdemo\b', re.I)
SOLD_VERB = re.compile(r'\bSold\b|\bCommitted\b|\bRumoured\b|\bRumored\b|\bUnderstand\b|\bReported\b', re.I)


def money(s):
    """Parse a price token. European comma-decimal ('72,40 mill') is not a thousands
    separator: only treat ',' as thousands when it groups 3 digits after it."""
    s = s.strip()
    if re.match(r'^\d{1,3},\d{1,2}$', s):
        return float(s.replace(',', '.'))
    return float(s.replace(',', ''))


def parse_price_segment(seg):
    out = {'price_usd_m': None, 'price_usd_m_low': None, 'price_usd_m_high': None,
           'price_per_lt': None, 'price_per_lt_low': None, 'price_per_lt_high': None,
           'price_unit': None, 'price_qualifier': None, 'price_raw': None}
    mq = QUALIFIER.search(seg)
    if mq:
        out['price_qualifier'] = ' '.join(mq.group(1).lower().split())
    m = PER_LT_R.search(seg)
    if m:
        lo, hi = money(m.group(1)), money(m.group(2))
        out.update(price_per_lt_low=lo, price_per_lt_high=hi,
                   price_unit='USD_per_LDT', price_raw=m.group(0).strip())
        return out
    m = PER_LT_1.search(seg)
    if m:
        v = money(m.group(1))
        out.update(price_per_lt=v, price_per_lt_low=v, price_per_lt_high=v,
                   price_unit='USD_per_LDT', price_raw=m.group(0).strip())
        return out
    m = MILL_OR.search(seg)
    if m:
        lo, hi = money(m.group(1)), money(m.group(2))
        out.update(price_usd_m_low=lo, price_usd_m_high=hi,
                   price_unit='USD_million', price_raw=m.group(0).strip())
        return out
    m = MILL_R.search(seg)
    if m:
        lo, hi = money(m.group(1)), money(m.group(2))
        out.update(price_usd_m_low=lo, price_usd_m_high=hi,
                   price_unit='USD_million', price_raw=m.group(0).strip())
        return out
    m = MILL_1.search(seg)
    if m:
        v = money(m.group(1))
        out.update(price_usd_m=v, price_usd_m_low=v, price_usd_m_high=v,
                   price_unit='USD_million', price_raw=m.group(0).strip())
        return out
    m = ND_MILL_R.search(seg)
    if m:
        lo, hi = money(m.group(1)), money(m.group(2))
        out.update(price_usd_m_low=lo, price_usd_m_high=hi,
                   price_unit='USD_million', price_raw=m.group(0).strip())
        return out
    m = ND_MILL_1.search(seg)
    if m:
        v = money(m.group(1))
        out.update(price_usd_m=v, price_usd_m_low=v, price_usd_m_high=v,
                   price_unit='USD_million', price_raw=m.group(0).strip())
    return out


def parse_buyer_dest(seg):
    buyer = None
    for m in BUYER_PAT.finditer(seg):
        cand = m.group(1).strip()
        if not BUYER_WORDS.search(cand):
            continue
        tail = seg[m.end():]
        pm = re.match(r'\s*(\([^)]*\))', tail)
        if pm:
            cand = cand + ' ' + pm.group(1).strip()
        buyer = ' '.join(cand.split()).strip(' .')
        break
    dest = None
    for c in COUNTRY_UPPER:
        if re.search(r'\bto\s+' + c + r'\b', seg):
            dest = c
            break
    return buyer, dest


def parse_header(rec_text):
    m = re.match(r'^(M/V|M/T|C/V|MTS|MT|M/V\.|LPG/C|LPG|S/C|F/V)\s+(.+)', rec_text, re.S)
    if not m:
        return None, None, None
    tag, rest = m.group(1), m.group(2).strip()
    ipar = rest.find('(')
    mdal = re.search(r'\s[-–]\s', rest)
    use_paren = ipar >= 0 and (not mdal or ipar < mdal.start())
    if use_paren:
        name = rest[:ipar]
        mc = re.match(r'\(([^()]*)\)', rest[ipar:], re.S)
        specs = mc.group(1) if mc else rest[ipar + 1:]
    else:
        md = re.match(r'^(.{2,60}?)\s+[-–]\s+(.*)$', rest, re.S)
        if md:
            name, specs = md.group(1), md.group(2)
        else:
            mk = re.search(r'\s(?:ABT\s+)?[\d][\d,]{3,}\s*dwt|\sLDT\s|,\s*blt\s|\bbuilt\s|\bdely\s|\bdelivery\b', rest)
            if mk:
                name, specs = rest[:mk.start()], rest[mk.start():]
            else:
                name, specs = rest, ''
    # guard: if the candidate name looks like it swallowed spec text, cut at the first spec keyword
    if re.search(r'\bdwt\b|\bblt\b|\bLDT\b|\bbuilt\b|\bteu\b', name, re.I) or re.search(r'\d{1,3},\d{3}', name):
        mk = re.search(r'\s(?:ABT\s+)?[\d][\d,]{3,}\s*dwt|\sLDT\s|,\s*blt\s|\bbuilt\s|\bdely\s|\bdelivery\b', rest)
        if mk:
            name, specs = rest[:mk.start()], rest[mk.start():]
    name = name.strip().strip('"\u201c\u201d').strip(' -–')
    return tag, name, specs


CLASS_WORDS = ['RINA', 'ABS', 'AB', 'NK', 'NKK', 'LR', 'NV', 'BV', 'RI', 'KR', 'DNV', 'CCS',
               'IR', 'RS', 'GL', 'PRS', 'CC', 'IRS', 'BKI', 'ClassNK']


def parse_specs(specs):
    f = {'dwt': None, 'ldt': None, 'ldt_high': None, 'built_year': None, 'yard': None,
         'country': None, 'class': None, 'ss_due': None, 'dd_due': None, 'dely_date': None}
    if not specs:
        return f
    s = ' '.join(specs.split())
    # LDT (may itself be a range: 'LDT 2,351 - 2,854')
    m = re.search(r'\bLDT\s*[:]?\s*([\d,]+)(?:\s*[-–]\s*([\d,]+))?', s, re.I)
    if m:
        f['ldt'] = int(m.group(1).replace(',', ''))
        if m.group(2):
            f['ldt_high'] = int(m.group(2).replace(',', ''))
    s_no_ldt = re.sub(r'\bLDT\s*[:]?\s*[\d,]+\s*(?:[-–]\s*[\d,]+)?', ' ', s, flags=re.I)
    m = re.search(r'(?:ABT\s+)?([\d][\d,]{3,})\s*dwt', s_no_ldt, re.I)
    if m:
        f['dwt'] = int(m.group(1).replace(',', ''))
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
            m = re.search(r'\bdely\s*([A-Z][a-z]+ \d{4})', s, re.I)
            base_end = m.end() if m else None
            if m:
                f['dely_date'] = m.group(1)
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
    if f['built_year'] is None:
        # year present without a 'blt'/'built' label, e.g. '(LDT 2557, 7902 dwt, 1992 Higaki/Jpn)'
        s2 = re.sub(r'\d{2}/\d{2,4}', ' ', s)
        m = re.search(r'(?:^|[(,\s])((?:19|20)\d{2})(?=[,)\s]|$)', s2)
        if m:
            f['built_year'] = int(m.group(1))
            if base_end is None:
                tail = s2[m.end():m.end() + 60].strip(' ,')
                for ch in tail.split(','):
                    ch = ch.strip(' .)')
                    mm = re.match(r'^([A-Za-z0-9\.\&\'\- ]{2,45}?)\s*/\s*([A-Za-z\. ]{2,25})$', ch)
                    if mm:
                        f['yard'] = mm.group(1).strip()
                        f['country'] = mm.group(2).strip()
                    break
    return f


def deal_record(stem, rdate, section, sub, rec_text, seq):
    tag, name, specs = parse_header(rec_text)
    if not name or not re.match(r'^[A-Za-z0-9]', name):
        return None
    mp = PRICE_START.search(rec_text, 1)
    head_part = rec_text[:mp.start()] if mp else rec_text
    seg = rec_text[mp.start():] if mp else ''
    tag, name, specs = parse_header(head_part)
    if not name or not re.match(r'^[A-Za-z0-9]', name):
        tag, name, specs = parse_header(rec_text)
    if not name or not re.match(r'^[A-Za-z0-9]', name):
        return None
    f = parse_specs(specs)
    p = parse_price_segment(seg) if seg else parse_price_segment(rec_text)
    if not p['price_raw'] and MONEY_ANY.search(seg or rec_text):
        p['price_raw'] = 'non-per-LT/mill amount (not a vessel price): ' + \
            ' '.join(MONEY_ANY.search(seg or rec_text).string[max(0, MONEY_ANY.search(seg or rec_text).start() - 20):][:60].split())
    buyer, dest = parse_buyer_dest(seg or rec_text)
    note = None
    mn = NOTE_PAT.search(seg or rec_text)
    if mn:
        note = ' '.join(mn.group(1).split()).strip()
    is_demo = bool(DEMO_VERB.search(seg)) or bool(re.search(r'\bdemo\b', rec_text, re.I))
    if not is_demo and section == 'DEMOLITION' and p['price_unit'] == 'USD_per_LDT':
        is_demo = True
    if is_demo:
        kind = 'demo'
    elif SOLD_VERB.search(seg):
        kind = 'sold'
    elif re.search(r'\bnegos?\b|under negotiation', rec_text, re.I):
        kind = 'nego'
    elif p['price_raw']:
        kind = 'price_only'
    else:
        kind = 'no_price'
    row = {'report_date': rdate, 'week': week_of(stem), 'issue': stem, 'seq': seq,
           'section': section, 'sub_section': sub, 'tag': tag, 'vessel': name,
           'dwt': f['dwt'], 'ldt': f['ldt'], 'ldt_high': f['ldt_high'],
           'built_year': f['built_year'], 'dely_date': f['dely_date'], 'yard': f['yard'],
           'country': f['country'], 'class': f['class'],
           'ss_due': f['ss_due'], 'dd_due': f['dd_due'],
           'deal_kind': kind, 'is_demolition': bool(is_demo),
           'buyer': buyer, 'dest_country': dest, 'notes': note,
           'en_bloc': bool(re.search(r'en\s+bloc', rec_text, re.I)),
           'specs_raw': ' '.join(specs.split()) or None,
           'price_raw': p['price_raw'],
           'tail_raw': ' '.join((seg or rec_text).split())[:600]}
    row.update({k: p[k] for k in ('price_usd_m', 'price_usd_m_low', 'price_usd_m_high',
                                  'price_per_lt', 'price_per_lt_low', 'price_per_lt_high',
                                  'price_unit', 'price_qualifier')})
    row['en_bloc_group_price_usd_m'] = None
    row['en_bloc_group_size'] = None
    row['price_backfill'] = None
    row['buyer_backfill'] = None
    return row


def has_price(r):
    return any(r[k] is not None for k in ('price_usd_m', 'price_per_lt'))


def resolve_en_bloc(rows):
    """Vessels grouped under one 'en bloc' price line directly below their spec headers.

    'en bloc for <amount> each'   -> price is per vessel: copy to every member.
    'en bloc for <total> ($<x> mill each)' -> <x> is per vessel, the leading amount
                                   is the group total (v3).
    'en bloc for $A mill & $B mill respectively' -> the amounts are per-vessel but
                                   the vessel<->price mapping is not resolvable from
                                   the text -> both stay NULL, both amounts recorded
                                   in the note (a wrong price is worse than a missing one).
    per-LT rates                  -> inherently per vessel: copy to every member.
    'en bloc for <total>'         -> group total: members AND the carrier keep the
                                   per-vessel price NULL and carry
                                   en_bloc_group_price_usd_m / en_bloc_group_size.
    'en bloc' with no amount      -> members inherit the verb/buyer, price stays NULL.

    v3 fixes, each measured on the 44-issue corpus (docs/lion_verdict.md):
      A) the carrier used to keep the group total as if it were its own price
         (32 rows; e.g. NORDIC LUNA 50.0 where the pair total was $50 mill and the
         publisher's own commentary says '$25 mill each').
      B) the 'respectively' form lost one of its two prices entirely
         (OOCL DURBAN/BRAZIL: $79.3 mill silently dropped).
      C) 'en bloc for region $52.5 mill ($17.5 mill each)' copied the TOTAL to
         every member, a 3x overstatement (AFRICAN MERLIN trio, MINERVA pair).
    """
    PRICE_FIELDS = ('price_usd_m', 'price_usd_m_low', 'price_usd_m_high', 'price_per_lt',
                    'price_per_lt_low', 'price_per_lt_high', 'price_unit', 'price_raw',
                    'price_qualifier')
    RESPECTIVELY_R = re.compile(
        r'en\s+bloc\s+for\s+(?:region\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*mill\s*'
        r'(?:&|and)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*mill\s+respectively', re.I)
    PAREN_EACH_R = re.compile(
        r'\(\s*\$?\s*([\d,]+(?:\.\d+)?)\s*mill\s+(?:each|apiece|a\s+piece)\s*\)', re.I)
    n = len(rows)
    for i, r in enumerate(rows):
        if not r['en_bloc']:
            continue
        if not (has_price(r) or r['deal_kind'] in ('sold', 'demo')):
            continue
        tail = r['tail_raw'] or ''
        if not re.search(r'\ben\s+bloc\b', tail, re.I):
            continue
        j = i - 1
        group = [i]
        while j >= 0:
            p = rows[j]
            if p['section'] != r['section'] or has_price(p) or p['deal_kind'] in ('sold', 'demo', 'nego'):
                break
            group.insert(0, j)
            j -= 1
        kind = r['deal_kind'] if r['deal_kind'] in ('sold', 'demo') else 'sold'
        ei = tail.lower().find('en bloc')
        price_from_sentence = False
        if r['price_raw']:
            pi = tail.find(r['price_raw'])
            if pi < 0:
                mm = re.search(r'[\d][\d,\.]*', r['price_raw'])
                pi = tail.find(mm.group(0)) if mm else -1
            price_from_sentence = (pi >= 0 and ei >= 0 and pi > ei)

        mr = RESPECTIVELY_R.search(tail)
        if mr and len(group) >= 2:
            a, b = money(mr.group(1)), money(mr.group(2))
            for k in group:
                rows[k]['deal_kind'] = kind
                rows[k]['is_demolition'] = r['is_demolition']
                rows[k]['buyer'] = rows[k]['buyer'] or r['buyer']
                rows[k]['dest_country'] = rows[k]['dest_country'] or r['dest_country']
                rows[k]['en_bloc'] = True
                rows[k]['en_bloc_group_size'] = len(group)
                rows[k]['en_bloc_group_price_usd_m'] = None
                for fld in PRICE_FIELDS:
                    rows[k][fld] = None
                rows[k]['notes'] = ((rows[k]['notes'] or '') +
                                    ' [en bloc, respectively: $%g mill / $%g mill for %d vessels'
                                    ' - per-vessel mapping not resolvable, price left null]'
                                    % (a, b, len(group))).strip()
            continue

        each = bool(re.search(r'\beach\b|\ba\s+piece\b|\bapiece\b', tail, re.I))
        if r['price_unit'] == 'USD_per_LDT':
            each = True

        me = PAREN_EACH_R.search(tail)
        if me and len(group) >= 2:
            per_v = money(me.group(1))
            gtot = r['price_usd_m']
            for k in group:
                rows[k]['deal_kind'] = kind
                rows[k]['is_demolition'] = r['is_demolition']
                rows[k]['buyer'] = rows[k]['buyer'] or r['buyer']
                rows[k]['dest_country'] = rows[k]['dest_country'] or r['dest_country']
                rows[k]['en_bloc'] = True
                rows[k]['en_bloc_group_size'] = len(group)
                rows[k]['en_bloc_group_price_usd_m'] = gtot
                rows[k]['price_usd_m'] = per_v
                rows[k]['price_usd_m_low'] = per_v
                rows[k]['price_usd_m_high'] = per_v
                rows[k]['price_unit'] = 'USD_million'
                rows[k]['price_qualifier'] = None
                rows[k]['price_raw'] = '$%g mill each' % per_v
                rows[k]['price_backfill'] = 'en_bloc:' + r['vessel']
                rows[k]['notes'] = ((rows[k]['notes'] or '') +
                                    ' [en bloc group: $%g mill total for %d vessels, $%g mill each]'
                                    % (gtot, len(group), per_v)).strip()
            continue

        if has_price(r) and not each:
            gtot = r['price_usd_m']
            for k in group:
                rows[k]['en_bloc_group_price_usd_m'] = gtot
                rows[k]['en_bloc_group_size'] = len(group)
                rows[k]['deal_kind'] = kind
                rows[k]['is_demolition'] = r['is_demolition']
                rows[k]['buyer'] = rows[k]['buyer'] or r['buyer']
                rows[k]['dest_country'] = rows[k]['dest_country'] or r['dest_country']
                if k != i or (price_from_sentence and len(group) > 1):
                    for fld in PRICE_FIELDS:
                        rows[k][fld] = None
                rows[k]['notes'] = ((rows[k]['notes'] or '') +
                                    ' [en bloc group: $ %s mill total for %d vessels, per-vessel price not disclosed]'
                                    % (gtot, len(group))).strip()
            continue
        for k in group:
            if k == i:
                continue
            for fld in PRICE_FIELDS:
                rows[k][fld] = r[fld]
            rows[k]['deal_kind'] = kind
            rows[k]['is_demolition'] = r['is_demolition']
            rows[k]['dest_country'] = rows[k]['dest_country'] or r['dest_country']
            rows[k]['buyer'] = rows[k]['buyer'] or r['buyer']
            rows[k]['en_bloc_group_size'] = len(group)
            rows[k]['price_backfill'] = 'en_bloc:' + r['vessel']
            rows[k]['notes'] = ((rows[k]['notes'] or '') +
                                ' [en bloc %s with %s]' % (kind, r['vessel'])).strip()
    for i, r in enumerate(rows):
        if r['buyer'] and r['en_bloc'] and re.search(r'\ben\s+bloc\b', r['tail_raw'] or '', re.I):
            j = i - 1
            while j >= 0:
                p = rows[j]
                if p['section'] != r['section'] or p['buyer'] or not has_price(p):
                    break
                if re.search(r'en\s+bloc\s+for', p['tail_raw'] or '', re.I):
                    break
                p['buyer'] = r['buyer']
                p['buyer_backfill'] = r['vessel']
                j -= 1
    return rows


# ------------------------------------------------------------------- per issue
def split_records(lines):
    records = []
    section = None
    sub = None
    cur = None
    blocker = False
    for ln in lines:
        s = ln.strip()
        up = s.rstrip(':').strip().upper()
        is_head = bool(HEADING_LINE.match(s)) and (up in SECTION_TOP or up in SUB_LABELS)
        if VESSEL_LINE.match(s):
            if cur:
                records.append(cur)
            cur = {'section': section, 'sub': sub, 'lines': [s]}
            blocker = False
            continue
        if blocker:
            if is_head:
                blocker = False
            else:
                continue
        if is_head:
            if cur:
                records.append(cur)
                cur = None
            if section == 'DEMOLITION' and up in SUB_LABELS:
                sub = up
                continue
            if up in SECTION_TOP:
                section = SECTION_TOP[up]
                sub = None
                continue
            if up in SUB_LABELS:
                sub = up
            continue
        if re.match(r'^(Should you have any comments|LEGAL DISCLAIMER)|^Tel:', s):
            blocker = True
            if cur:
                records.append(cur)
                cur = None
            continue
        if cur:
            cur['lines'].append(s)
    if cur:
        records.append(cur)
    return records


def parse_issue(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    raw = open(path, encoding='utf-8').read()
    rdate = report_date(stem)
    if rdate is None:
        return [], [], 'no parseable report date in filename (not a Lion weekly issue)'
    dem, err = parse_demometer(raw, stem, rdate)
    records = split_records(normalize_lines(raw))
    rows = []
    for i, rec in enumerate(records):
        txt = ' '.join(rec['lines'])
        row = deal_record(stem, rdate, rec['section'], rec['sub'], txt, i)
        if row is None:
            log('  WARN unparsed record', stem[:40], '|', txt[:120])
            continue
        rows.append(row)
    rows = resolve_en_bloc(rows)
    # records seen before any section heading are MARKET COMMENTARY gossip, not the
    # REPRESENTATIVE SALES table -> excluded
    comm = [r for r in rows if r['section'] is None]
    rows = [r for r in rows if r['section'] is not None]
    for r in comm:
        log('  SKIP commentary record (no section heading):', stem[:35], '|', r['vessel'])
    kept = [r for r in rows if has_price(r) or r['deal_kind'] in ('sold', 'demo', 'nego')
            or r['en_bloc_group_price_usd_m'] is not None]
    dropped = [r for r in rows if r not in kept]
    for r in dropped:
        log('  DROP record (no price, no verb):', stem[:35], '|', r['vessel'])
    return dem, kept, (err if not dem else None)


def fmt_dem(v_low, v_high):
    if v_low is None or v_high is None:
        return '-'
    if v_low == v_high:
        return '%g' % v_low
    return '%g-%g' % (v_low, v_high)


def find_pdf(stem):
    hits = glob.glob(os.path.join(PDF_DIR, '*', stem + '.pdf'))
    if not hits:
        return 'corpus/01-brokers/lion/<year>/' + stem + '.pdf'
    return os.path.relpath(hits[0], REPO).replace(os.sep, '/')


def write_md(dem_rows, deal_rows):
    """One markdown file per issue: the demometer table + the deal records."""
    outdir = os.path.join(OUT, 'md', 'lion')
    os.makedirs(outdir, exist_ok=True)
    dem_by = collections.defaultdict(list)
    for r in dem_rows:
        dem_by[r['issue']].append(r)
    deal_by = collections.defaultdict(list)
    for r in deal_rows:
        deal_by[r['issue']].append(r)
    written = 0
    for stem in sorted(set(dem_by) | set(deal_by)):
        L = ['# ' + stem, '', 'source: `%s`' % find_pdf(stem), '']
        L += ["## Lion's demometer (USD $/LT)", '']
        L += ['| country | bulker | tanker | cont/tween | trend |', '|---|---|---|---|---|']
        rows = dem_by.get(stem, [])
        for c in DEM_COUNTRIES:
            cells = {}
            trend = ''
            for r in rows:
                if r['country'] == c:
                    cells[r['vessel_type']] = fmt_dem(r['price_low'], r['price_high'])
                    trend = r.get('trend') or trend
            if cells:
                L.append('| %s | %s | %s | %s | %s |' % (
                    c, cells.get('BULKER', '-'), cells.get('TANKER', '-'),
                    cells.get('CONT/TWEEN', '-'), trend))
        L.append('')
        L += ['## Representative sales', '',
              '| section | vessel | dwt | built | yard | price | buyer | kind |',
              '|---|---|---|---|---|---|---|---|']
        for r in deal_by.get(stem, []):
            if r.get('price_usd_m') is not None:
                price = '$%g mill' % r['price_usd_m']
            elif r.get('price_usd_m_low') is not None:
                price = '$%g-%g mill' % (r['price_usd_m_low'], r['price_usd_m_high'])
            elif r.get('price_per_lt') is not None:
                price = '$%g/lt' % r['price_per_lt']
            elif r.get('price_per_lt_low') is not None:
                price = '$%g-%g/lt' % (r['price_per_lt_low'], r['price_per_lt_high'])
            elif r.get('en_bloc_group_price_usd_m') is not None:
                price = 'en bloc $%g mill total / %d ships' % (
                    r['en_bloc_group_price_usd_m'], int(r.get('en_bloc_group_size') or 0))
            else:
                price = '-'
            L.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
                r.get('section') or '-', r.get('vessel') or '-',
                ('%g' % r['dwt']) if r.get('dwt') else '-',
                ('%g' % r['built_year']) if r.get('built_year') else '-',
                r.get('yard') or '-', price, r.get('buyer') or '-',
                r.get('deal_kind') or '-'))
        L.append('')
        L += ['## Narratives', '']
        for r in deal_by.get(stem, []):
            L.append('- **%s** %s' % (r.get('vessel'), (r.get('tail_raw') or '').strip()))
        with open(os.path.join(outdir, stem + '.md'), 'w', encoding='utf-8') as fh:
            fh.write(chr(10).join(L) + chr(10))
        written += 1
    log('markdown: %d issue file(s) -> data/extracted/md/lion/' % written)


def build_outputs():
    """Build the two parquet deliverables + JSON summary from the JSONL ledgers."""
    dem = [json.loads(l) for l in open(os.path.join(SCR, 'demometer.jsonl'), encoding='utf-8')]
    deals = [json.loads(l) for l in open(os.path.join(SCR, 'deals.jsonl'), encoding='utf-8')]

    DEM_COLS = ['report_date', 'week', 'country', 'vessel_type', 'price_low', 'price_high',
                'price_point', 'trend', 'unit', 'value_kind', 'issue']
    for r in dem:
        r['unit'] = 'USD_per_LDT'
    ddf = pd.DataFrame(dem)[DEM_COLS].sort_values(['report_date', 'country', 'vessel_type']).reset_index(drop=True)
    ddf.to_parquet(os.path.join(OUT, 'lion_demometer.parquet'), index=False)

    DEAL_COLS = ['report_date', 'week', 'section', 'sub_section', 'vessel', 'tag', 'dwt', 'ldt',
                 'ldt_high', 'built_year', 'dely_date', 'yard', 'country', 'class', 'ss_due',
                 'dd_due', 'deal_kind', 'is_demolition', 'price_usd_m', 'price_usd_m_low',
                 'price_usd_m_high', 'price_per_lt', 'price_per_lt_low', 'price_per_lt_high',
                 'price_unit', 'price_qualifier', 'en_bloc_group_price_usd_m', 'en_bloc_group_size',
                 'en_bloc', 'price_backfill', 'buyer', 'buyer_backfill', 'dest_country', 'notes',
                 'price_raw', 'specs_raw', 'tail_raw', 'issue']
    for r in deals:
        for c in DEAL_COLS:
            r.setdefault(c, None)
    xdf = pd.DataFrame(deals)[DEAL_COLS].sort_values(['report_date', 'section', 'vessel']).reset_index(drop=True)
    xdf.to_parquet(os.path.join(OUT, 'lion_deals.parquet'), index=False)

    # ---------------------------------------------------------------- summary
    issues_all = sorted({r['issue'] for r in dem} | {r['issue'] for r in deals})


    def pct(series):
        return round(100.0 * series.notna().sum() / len(series), 1)


    dem_useful = ddf[ddf['price_point'].notna()]
    by_ct = (dem_useful.groupby(['country', 'vessel_type'])
             .agg(n=('price_point', 'size'), min_point=('price_point', 'min'),
                  max_point=('price_point', 'max'), min_low=('price_low', 'min'),
                  max_high=('price_high', 'max'))
             .reset_index().to_dict('records'))

    dem_ranges = {}
    for (c, t), g in dem_useful[dem_useful['value_kind'] == 'range'].groupby(['country', 'vessel_type']):
        dem_ranges['%s|%s' % (c, t)] = {'n_ranges': int(len(g)), 'min_low': float(g['price_low'].min()),
                                        'max_high': float(g['price_high'].max())}

    x = xdf
    sold = x[(~x['is_demolition']) & (x['deal_kind'].isin(['sold', 'price_only']))]
    demo = x[x['is_demolition']]

    summary = {
        'source': 'reports/shipbrokers/lion/<year>/*.pdf (Lion Shipbrokers weekly report)',
        'issues_available': 44,
        'issues_yielded_data': len(issues_all),
        'issues_failed': 1,
        'issues_failed_detail': [
            {'issue': 'lion_2024_W31_Market-report-Week-31',
             'reason': 'not a Lion weekly report (a Star Asia market report filed under the Lion dir): '
                       'no DEMOMETER table, no REPRESENTATIVE SALES section; tabular S&P list instead'},
        ],
        'demometer': {
            'rows': int(len(ddf)),
            'weeks_covered': int(ddf['report_date'].nunique()),
            'date_range': [str(ddf['report_date'].min()), str(ddf['report_date'].max())],
            'countries': sorted(ddf['country'].unique().tolist()),
            'n_countries': int(ddf['country'].nunique()),
            'vessel_types': sorted(ddf['vessel_type'].unique().tolist()),
            'unit': 'USD per LDT (light displacement tonne)',
            'value_kind_counts': dict(collections.Counter(ddf['value_kind'])),
            'rows_with_price': int(ddf['price_point'].notna().sum()),
            'price_range_usd_per_ldt': [float(ddf['price_low'].min()), float(ddf['price_high'].max())],
            'per_country_type': by_ct,
            'ranges_both_bounds_kept': dem_ranges,
            'ranges_policy': "ranges keep price_low and price_high; price_point is their midpoint "
                             "(a collapsed single value is never stored without both bounds)",
            'null_handling': "a '-' cell (1 row) yields price_low/high/point = null, value_kind='dash'",
            'trend_vocabulary': sorted(set(v for v in ddf['trend'].dropna().unique())),
            'example_rows': ddf.head(5).to_dict('records'),
        },
        'deals': {
            'rows': int(len(xdf)),
            'issues': len(issues_all),
            'sold_rows': int(len(sold)),
            'demolition_rows': int(len(demo)),
            'deal_kind_counts': dict(collections.Counter(xdf['deal_kind'])),
            'is_demolition_flag_policy': "true when the record carries a 'Demo' verb, or sits in the "
                                         "DEMOLITION section and is priced per LDT (catches "
                                         "'Sold for $ 493 per LT' Ro/Pax scrape sales)",
            'section_counts': dict(collections.Counter(xdf['section'])),
            'sub_section_counts': {k: v for k, v in collections.Counter(
                xdf['sub_section'].dropna()).items()},
            'column_population_pct': {c: pct(xdf[c]) for c in DEAL_COLS if c not in
                                      ('issue', 'tail_raw', 'specs_raw', 'price_raw')},
            'price_usd_m_population_pct': pct(xdf['price_usd_m']),
            'price_per_lt_population_pct': pct(xdf['price_per_lt']),
            'any_vessel_price_population_pct': round(100.0 * (
                (xdf['price_usd_m'].notna()) | (xdf['price_per_lt'].notna())).sum() / len(xdf), 1),
            'buyer_population_pct': pct(xdf['buyer']),
            'buyer_population_pct_sold_only': round(100.0 * sold['buyer'].notna().sum() / max(1, len(sold)), 1),
            'buyer_population_pct_demolition_only': round(100.0 * demo['buyer'].notna().sum() / max(1, len(demo)), 1),
            'named_buyer_population_pct': round(100.0 * x['buyer'].notna().sum() / len(x), 1),
            'undisclosed_buyer_rows': int(x['buyer'].fillna('').str.contains('undisclosed', case=False).sum()),
            'dest_country_population_pct': pct(xdf['dest_country']),
            'dest_country_counts': dict(collections.Counter(xdf['dest_country'].dropna())),
            'distinct_buyer_strings': int(xdf['buyer'].nunique(dropna=True)),
            'unit_policy': "price_usd_m / price_usd_m_low / price_usd_m_high are USD million "
                           "(secondhand sale prices); price_per_lt / _low / _high are USD per light "
                           "tonne (scrap); never mixed in one column",
            'range_policy': "ranges keep both bounds in *_low / *_high; the point column stays null",
            'en_bloc_policy': "'en bloc ... each' and per-LDT group deals propagate the price to every "
                              "member; a group TOTAL ('en bloc for $ 160 mill', 4 ships) is stored only "
                              "in en_bloc_group_price_usd_m and per-vessel price stays null",
            'en_bloc_group_rows': int(xdf['en_bloc_group_price_usd_m'].notna().sum()),
            'en_bloc_propagated_rows': int(xdf['price_backfill'].notna().sum()),
            'price_backfilled_from_sibling_rows': int(xdf['price_backfill'].notna().sum()),
            'example_rows': xdf.head(5).drop(columns=['tail_raw', 'specs_raw']).to_dict('records'),
            'example_demolition_rows': demo.head(5).drop(columns=['tail_raw', 'specs_raw']).to_dict('records'),
        },
        'files': {
            'demometer_parquet': 'data/extracted/lion_demometer.parquet',
            'deals_parquet': 'data/extracted/lion_deals.parquet',
            'summary_json': 'data/extracted/lion_summary.json',
            'raw_ledgers': ['scratch/lion/demometer.jsonl', 'scratch/lion/deals.jsonl'],
            'parse_log': 'scratch/lion/parse_log.txt',
        },
    }
    with open(os.path.join(OUT, 'lion_summary.json'), 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, indent=2, default=str)

    print('demometer rows', len(ddf), '| deals rows', len(xdf))
    print('weeks', summary['demometer']['weeks_covered'], '| countries', summary['demometer']['n_countries'])
    print('sold', len(sold), '| demo', len(demo), '| buyer%', summary['deals']['buyer_population_pct'])
    print('wrote 3 files to data/extracted/')



def build_txt(rebuild=False):
    """PDF -> cached text: get_text(sort=True), PAGEBREAK-joined, footer lines dropped."""
    os.makedirs(TXT, exist_ok=True)
    made = 0
    for pdf in sorted(glob.glob(os.path.join(PDF_DIR, '*', '*.pdf'))):
        stem = os.path.splitext(os.path.basename(pdf))[0]
        out = os.path.join(TXT, stem + '.txt')
        if os.path.exists(out) and not rebuild:
            continue
        doc = pymupdf.open(pdf)
        raw = (chr(10) + '<<<PAGEBREAK>>>' + chr(10)).join(
            pg.get_text(sort=True) for pg in doc)
        doc.close()
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(chr(10).join(normalize_lines(raw)) + chr(10))
        made += 1
    log('text cache: %d written, %d total' % (made, len(glob.glob(os.path.join(TXT, '*.txt')))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rebuild-txt', action='store_true',
                    help='re-render the text cache from the PDFs before parsing')
    args = ap.parse_args()
    build_txt(args.rebuild_txt)
    files = sorted(glob.glob(os.path.join(TXT, '*.txt')))
    log('issues found:', len(files))
    open(DEM_JSONL, 'w', encoding='utf-8').close()
    open(DEAL_JSONL, 'w', encoding='utf-8').close()
    ok, failed = [], []
    for f in files:
        dem, rows, err = parse_issue(f)
        if err and not rows:
            failed.append((os.path.basename(f), err))
            log('ISSUE SKIPPED:', os.path.basename(f), '|', err)
            continue
        with open(DEM_JSONL, 'a', encoding='utf-8') as fh:
            for r in dem:
                fh.write(json.dumps(r) + '\n')
        with open(DEAL_JSONL, 'a', encoding='utf-8') as fh:
            for r in rows:
                fh.write(json.dumps(r) + '\n')
        ok.append((os.path.basename(f), len(dem), len(rows)))
        log('OK %-68s dem_rows=%d deals=%d' % (os.path.basename(f)[:66], len(dem), len(rows)))
    log('issues parsed ok:', len(ok), 'skipped:', len(failed))
    log('demometer rows total:', sum(x[1] for x in ok), 'deal rows total:', sum(x[2] for x in ok))
    build_outputs()
    dem_all = [json.loads(l) for l in open(DEM_JSONL, encoding='utf-8') if l.strip()]
    deal_all = [json.loads(l) for l in open(DEAL_JSONL, encoding='utf-8') if l.strip()]
    write_md(dem_all, deal_all)


if __name__ == '__main__':
    main()
    logf.close()
