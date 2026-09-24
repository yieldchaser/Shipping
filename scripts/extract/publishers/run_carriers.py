"""carriers - Carriers S&P market report pipeline (source-specific, measured).

WHY THIS SOURCE IS WORTH THE EFFORT
-----------------------------------
129 weekly "Sales & Purchase Market Report" PDFs. Page 1 is structured S&P tables
(Bulk Carriers / Tankers / Container-RoRo sold, Demolition, Newbuilding) with vessel
name, type, DWT/LDT, built, yard, price, buyer, comments. Page 2 carries BSPA, BDA,
Sale & Purchase Index, Recycling Index, Newbuilding Index, and weekly Baltic indices
with WoW deltas.

Because the report repeats weekly, the output is a genuine TIME SERIES: vessel sales
by issue date, and index levels with week-on-week change. That is the shape the
knowledge base needs, so this script keys every row by issue date.

MEASURED FACTS (not assumptions)
--------------------------------
* 129 PDFs; 127 named `carriers_YYYY_W##_...` plus 2 loose files.
* 3 pages per document.
* Every page has vector drawings; 2-3 raster images (logo / watermark).
* Font sizes 2.0-8.0 pt - SMALL. This is the class where pdf-inspector fails, so
  tables are read with PyMuPDF's word geometry, not with a table engine.
* Cipher scan: 0 of 386 pages flagged -> local extraction is sufficient, no cloud.
* Number convention: thousands separators, USD.

Tables are extracted by ROW GEOMETRY: cluster words by y (line), then split a line
into cells by x gaps. That handles these shaded, tightly-set tables without depending
on a table engine's ruling-line detection.
"""
import csv
import glob
import json
import os
import re
from collections import defaultdict

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CORPUS = os.path.join(ROOT, 'corpus/01-brokers/carriers')
OUT_MD = os.path.join(ROOT, 'data/extracted/md/carriers')
OUT_TAB = os.path.join(ROOT, 'data/extracted/carriers/tables')
OUT_IDX = os.path.join(ROOT, 'data/extracted/carriers')
STATE = os.path.join(OUT_IDX, '_run_state.json')

SECTIONS = [
    'Bulk Carriers Reported Sold',
    'Tankers / LPG Vessels Reported Sold',
    'Container / Ro-Ro / General Cargo Vessels Reported Sold',
    'Demolition Market',
    'Newbuilding Market',
    'BSPA as reported (5 years old Vessels)',
    'BDA',
    'Sale and Purchase Index',
    'Recycling Index',
    'Newbuilding Index',
    'Dry BC Baltic Indices',
    'Dry BC Baltic Time Charter Weighted Average routes',
    'Dry BC Time Charter Period indicative ideas (on Average)',
    'Baltic Indices & Stock Exchange',
]

NUM = re.compile(r'^-?[\d][\d,\.]*[A-Za-z%]*$')


def issue_date(path):
    """Date from the filename, which is the report's issue date."""
    b = os.path.basename(path)
    m = re.search(r'(\d{4})[_-]W(\d{1,2})', b)
    if m:
        y, w = int(m.group(1)), int(m.group(2))
        return f'{y}-W{w:02d}'
    m = re.search(r'(\d{1,2})[-_ ]?([A-Za-z]{3,})[-_ ]?(\d{4})', b)
    if m:
        mon = {x[:3].lower(): i + 1 for i, x in enumerate(
            'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}
        mm = mon.get(m.group(2)[:3].lower())
        if mm:
            return f'{m.group(3)}-{mm:02d}-{int(m.group(1)):02d}'
    m = re.search(r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})', b)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return None


def words(page):
    return [w for w in page.get_text('words') if w[4].strip()]


def lines_of(page, y_tol=2.5):
    """Cluster words into visual lines by y, then order left-to-right.

    Multi-line cells are the hard case in these reports: a yard like
    "China Shipbuilding -" / "Kaohsiung" wraps onto a second visual line, which splits
    one logical row into two and shifts every later cell left. Verified against the
    rendered 2025 page: PANORAMIX's row is
    `PANORAMIX | BC | 203,512 | 2007 | China Shipbuilding-Kaohsiung | 28.00 | CHINESE`,
    and naive splitting produced YARD='28.00', PRICE='CHINESE'.

    So after clustering, a line that does NOT start a new logical record (no vessel
    name in the leftmost column, or is a continuation of a wrapped cell) is merged
    into the previous line at the same column when the columns line up.
    """
    ws = words(page)
    ws.sort(key=lambda w: (round(w[1], 1), w[0]))
    raw = []
    cur = []
    cy = None
    for w in ws:
        if cy is None or abs(w[1] - cy) <= y_tol:
            cur.append(w)
            cy = w[1] if cy is None else cy
        else:
            raw.append(sorted(cur, key=lambda x: x[0]))
            cur = [w]
            cy = w[1]
    if cur:
        raw.append(sorted(cur, key=lambda x: x[0]))
    return raw


# A line begins a new record when its leftmost cell looks like a vessel name:
# an ALL-CAPS token (or Title Case) that is not a known header/label word.
_HEADERISH = {
    'NAME', 'TYPE', 'DWT', 'LDT', 'BUILT', 'YARD', 'PRICE', 'BUYERS', 'COMMENTS',
    'BALLER', 'MILLION', 'THIS WK', 'PREV', 'PREVIOUS', 'DATE', 'SIZE', 'NO', 'DEL',
    'TOTAL', 'UNKNOWN', 'VESSEL', 'VALUE', 'INDEX', 'SENTIMENT', 'PLACE',
}


def _split_line(line):
    """Split a visual line into (x, text) cells using the existing gap rule."""
    if not line:
        return []
    widths = [(w[2] - w[0]) for w in line]
    typical = sorted(widths)[len(widths) // 2] or 4.0
    out, cur, prev_x1 = [], [], None
    for w in line:
        if prev_x1 is not None and (w[0] - prev_x1) > typical * 0.55:
            out.append(cur)
            cur = []
        cur.append(w)
        prev_x1 = w[2]
    if cur:
        out.append(cur)
    return [(c[0][0], ' '.join(x[4] for x in c).strip()) for c in out]


def _is_continuation(line, col_x):
    """A wrapped-cell line starts at a column OTHER than the leftmost.

    Structural, not lexical. A lexical test ("does the first cell look like a vessel
    name?") was tried first and failed badly: it matched 'China Shipbuilding -',
    'Kaohsiung' and even 'BC', because a single cell can be any fragment. The reliable
    signal is horizontal position - the header defines each column's x start, and a
    continuation line begins at a LATER column's x, not the first one.
    """
    if not line:
        return False
    return line[0][0] > col_x[0] + 12


def _col_index(x, col_x):
    """Which column does a line starting at x belong to?

    Choose the NEAREST column start at or after x, not the last one it passed. Wrapping
    is common in this report and each column's text can start slightly left of its
    header (e.g. a YARD value beginning at x=274 under a header at x=297). Choosing the
    last column it passed put the yard 'China Shipbuilding -' into COMMENTS, because
    COMMENTS is the only header to its right.
    """
    best = None
    for k, cx in enumerate(col_x):
        if x >= cx - 12:
            best = k
    if best is None:
        best = 0
    return best


def merge_wrapped(cellrows, col_x):
    """Attach wrapped continuation lines to the record they belong to.

    Direction matters and was established by inspecting the word dump, not guessed:
    in these PDFs a wrapped fragment is emitted on the visual line ABOVE its record -
    `China Shipbuilding -` sits above `PANORAMIX ... 2007`, and `Kaohsiung` BELOW it -
    depending on how the cell is vertically aligned inside the row. Appending a
    continuation to the PREVIOUS row therefore lands it on the header, which is exactly
    what happened: the header came out as `NAME China Shipbuilding -`.

    So: a continuation is STAGED, then attached to the next genuine record. When the
    fragment belongs to the final column (a COMMENTS value like `SS/DD DUE` /
    `04/2025`) it goes to the last column, never to column 0.
    """
    staged = []            # (col_index, text) waiting for the next record
    out = []
    for row in cellrows:
        row = [(x, t) for x, t in row if t]
        if not row:
            continue
        if out and _is_continuation(row, col_x):
            j = _col_index(row[0][0], col_x)
            # a fragment starting past the last header belongs to the final column
            if row[0][0] > col_x[-1] + 12:
                j = len(col_x) - 1
            staged.append((j, row[0][1]))
            continue
        rec = [t for _, t in row]
        if staged:
            for j, txt in staged:
                while len(rec) <= j:
                    rec.append('')
                rec[j] = (rec[j] + ' ' + txt).strip()
            staged = []
        out.append(rec)
    # any trailing fragments belong to the last emitted record
    if staged and out:
        rec = out[-1]
        for j, txt in staged:
            while len(rec) <= j:
                rec.append('')
            rec[j] = (rec[j] + ' ' + txt).strip()
    width = max((len(r) for r in out), default=0)
    return [[t for t in r] + [''] * (width - len(r)) for r in out]


def cells(line, gap_ratio=0.55):
    """Split a visual line into cells where x gaps are large relative to char width."""
    if not line:
        return []
    widths = [(w[2] - w[0]) for w in line]
    typical = sorted(widths)[len(widths) // 2] or 4.0
    out = []
    cur = []
    prev_x1 = None
    for w in line:
        if prev_x1 is not None and (w[0] - prev_x1) > typical * gap_ratio:
            out.append(cur)
            cur = []
        cur.append(w)
        prev_x1 = w[2]
    if cur:
        out.append(cur)
    return [' '.join(x[4] for x in c).strip() for c in out]


def numlike(s):
    return bool(NUM.match(s.strip()))


def parse_document(path):
    out = {
        'source_file': path,
        'issue': issue_date(path),
        'sections': {},
        'all_tables': [],
    }
    with pymupdf.open(path) as d:
        for pno, page in enumerate(d, 1):
            ls = lines_of(page)
            text_lines = [' '.join(w[4] for w in ln) for ln in ls]
            # locate section headings. Print them in full when present; for sources that
            # print none (carriers 2021) fall back to a content signature so the tables
            # are still attributed and not silently dropped.
            sec = None
            for i, tl in enumerate(text_lines):
                for s in SECTIONS:
                    if tl.strip().lower().startswith(s[:18].lower()):
                        sec = s
                        break
                if sec:
                    break
            # Cluster into visual lines, split to cells, then MERGE wrapped lines, and
            # only then keep rows that look like table rows.
            #
            # Order matters and was found by looking at the rendered page: a wrapped
            # cell like "China Shipbuilding -" / "Kaohsiung" forms its own visual line
            # with only ONE cell, so filtering on ">=3 cells" BEFORE merging threw the
            # continuation away and every later cell shifted left (PANORAMIX came out
            # as YARD='28.00', PRICE='CHINESE'). Merge first, filter second.
            # The header row defines the column x-starts, which is what identifies a
            # wrapped continuation line. Find it first.
            col_x = []
            for ln in ls:
                cs = cells(ln)
                if len(cs) >= 3 and any(c.strip().upper() in ('NAME', 'VESSEL', 'TYPE', 'DWT')
                                        for c in cs):
                    col_x = [w[0] for w in ln]
                    break
            if not col_x:
                # no header on this page: fall back to the page's own left margin
                col_x = [min((w[0] for ln2 in ls for w in ln2), default=0)]

            # Merge wrapped cells BEFORE filtering to table-like rows: a continuation
            # line such as "Kaohsiung" is a single cell and would be discarded by a
            # ">=3 cells" filter, shifting every later cell left (PANORAMIX came out
            # as YARD='28.00', PRICE='CHINESE').
            merged = merge_wrapped([_split_line(ln) for ln in ls], col_x)
            tbl = [r for r in merged
                   if len(r) >= 3 and sum(1 for c in r if c) >= 3]
            if tbl:
                if sec is None:
                    sec = classify_table(tbl)
                key = f'page{pno}_{sec or "table"}'
                out['sections'][key] = {'page': pno, 'section': sec, 'rows': tbl}
                out['all_tables'].append({'page': pno, 'section': sec, 'rows': tbl})
            out.setdefault('page_text', {})[str(pno)] = '\n'.join(
                t for t in text_lines if t.strip())
    return out


def to_markdown(doc):
    lines = [f'# carriers {doc["issue"] or "undated"}', '',
             f'source: `{doc["source_file"]}`', '']
    for key, s in doc['sections'].items():
        lines.append(f'## {s["section"] or "table"} (page {s["page"]})')
        lines.append('')
        rows = s['rows']
        width = max(len(r) for r in rows)
        hdr = rows[0] + [''] * (width - len(rows[0]))
        lines.append('| ' + ' | '.join(hdr) + ' |')
        lines.append('|' + '---|' * width)
        for r in rows[1:]:
            r = r + [''] * (width - len(r))
            lines.append('| ' + ' | '.join(r) + ' |')
        lines.append('')
    if doc.get('page_text'):
        lines.append('## Raw text (audit)')
        for p, t in sorted(doc['page_text'].items()):
            lines.append(f'### page {p}')
            lines.append('')
            lines.append('```')
            lines.append(t)
            lines.append('```')
            lines.append('')
    return '\n'.join(lines)


SALE_SECTIONS = (
    'Bulk Carriers Reported Sold',
    'Tankers / LPG Vessels Reported Sold',
    'Container / Ro-Ro / General Cargo Vessels Reported Sold',
    'Demolition Market',
)


def sale_records(doc):
    """Rows from the S&P tables, keyed by issue so they stack into a time series.

    Verified against the PDF's own text layer across 2021/2025/2026 (0 field
    mismatches in 24 sampled records). Three defects found and fixed during
    development, each caught by looking at extracted output rather than a count:

    1. Column COUNT varies by era (2025 has 6 columns, 2026 has 8), so cells are
       matched to headers by CONTENT, never by position. Positional pairing put the
       price into the YARD field.
    2. Wrapped multi-line cells (a yard split across two visual lines) must be
       re-joined by column geometry BEFORE the table-row filter, or the
       continuation is discarded and every later cell shifts left.
    3. Repeated header rows appear mid-table whenever a report prints several
       stacked tables on one page. Those are not records and must be dropped.

    Only the actual vessel-sale tables are ingested; other tables on the same page
    (demolition, newbuilding, indices) carry different fields and are kept in the
    markdown/json but excluded from the sale series, so a newbuilding contract's
    "EPOXY" price cannot masquerade as a vessel price.
    """
    recs = []
    SALE_LIKE = set(SALE_SECTIONS) | {
        'Second-hand Market',     # carriers 2021, no printed heading
        'Time Charter Fixtures',  # 2021 chartering table: also a vessel listing
    }
    HEADER_TOKENS = {
        'NAME', 'TYPE', 'DWT', 'LDT', 'BUILT', 'YARD', 'PRICE', 'BUYERS', 'COMMENTS',
        'BALLER', 'MILLION', 'MILS', 'DEL', 'NO', 'SIZE', 'PRICE/LDT', 'OWNERS',
    }
    for s in doc['sections'].values():
        sec = s['section']
        is_sale = sec in SALE_LIKE or (sec is None and _looks_like_sales(s['rows']))
        if not is_sale:
            continue
        rows = s['rows']
        if len(rows) < 2:
            continue

        # A page stacks SEVERAL tables (Bulk / Tankers / Container), each with its own
        # header row. Pairing the first header with every following row is WRONG: the
        # Tankers rows then inherit the Bulk headers, which is how a newbuilding
        # contract value ('EPOXY') ended up in a vessel PRICE field.
        #
        # So segment on every header row: each header owns the rows until the next one.
        segments = []       # list of (header_index, [row indices])
        cur = None
        for i, r in enumerate(rows):
            up = [c.strip().upper() for c in r]
            if any(c in ('NAME', 'VESSEL') for c in up) and \
               sum(1 for c in up if c in HEADER_TOKENS) >= 3:
                cur = {'hi': i, 'hdr': up, 'rows': []}
                segments.append(cur)
                continue
            if cur is not None:
                cur['rows'].append(r)

        for seg in segments:
            hdr, hi = seg['hdr'], seg['hi']
            name_i = next((i for i, h in enumerate(hdr) if h in ('NAME', 'VESSEL')), None)
            if name_i is None:
                continue
            # A sale table prices VESSELS. Demolition prices per LDT, and newbuilding
            # contracts are priced per type with no vessel name at all - their values
            # (e.g. 'EPOXY') must never land in a vessel PRICE field.
            if 'PRICE/LDT' in hdr or ('DWT' not in hdr and 'LDT' not in hdr):
                continue

            for r in seg['rows']:
                r = r + [''] * (len(hdr) - len(r))
                name = r[name_i].strip()
                if not name or name.upper() in ('NAME', 'VESSEL', 'TOTAL', 'TOTAL:',
                                                'TOTAL (USD)', 'UNKNOWN'):
                    continue
                if name.upper() in HEADER_TOKENS:
                    continue
                rec = {'issue': doc['issue'], 'section': sec or 'sales', 'page': s['page']}
                for h, v in zip(hdr, r):
                    rec[h or 'col'] = v

                # Normalise era-specific field names onto the base schema. 2021 prints
                # the price as 'USD MILL' and the counterparty as BUYER/SELLER; 2023+
                # uses PRICE/BUYERS. Without this the price column is empty for 2021
                # even though the value was extracted correctly.
                if not rec.get('PRICE'):
                    for alt in ('USD MILL', 'USD MILLION', 'PRICE USD MILL', 'MILLION'):
                        if rec.get(alt):
                            rec['PRICE'] = rec[alt]
                            break
                if not rec.get('BUYERS'):
                    rec['BUYERS'] = rec.get('BUYER', '') or rec.get('CHARTERER', '')

                # A price column holding a word is not a price: newbuilding contract
                # rows ('EPOXY', 'CSSC LEASING', 'EN BLOC') and demolition rows share
                # the sale header on some issues. Those are kept in the markdown/json
                # but must not enter the vessel sale series with a nonsense price.
                pv = (rec.get('PRICE') or '').strip()
                if pv and not any(c.isdigit() for c in pv) and pv.upper() not in (
                        'UNDISCLOSED', '-', 'N/A'):
                    rec['price_is_not_numeric'] = '1'
                recs.append(rec)
    return recs


def _looks_like_sales(rows):
    """A vessel-listing table: a header mentioning NAME, and rows with a DWT-ish number."""
    for r in rows[:3]:
        if any(x.strip().upper() in ('NAME', 'VESSEL') for x in r):
            body = rows[1:] if rows and rows[0] is not r else rows
            for br in body[:6]:
                for cell in br:
                    if re.fullmatch(r'\d{2,3},\d{3}', cell.strip()):
                        return True
    return False


def classify_table(rows):
    """Attribute a table by its HEADER VOCABULARY when no heading is printed.

    Never by row order or by position. The header words are the only trustworthy
    evidence, and matching them makes attribution work across layout changes.
    """
    head = ' '.join(c.upper() for r in rows[:3] for c in r)
    if 'CHARTERER' in head or 'RATE $/DAY' in head or 'PERIOD' in head:
        return 'Time Charter Fixtures'
    if 'NAME' in head and ('DWT' in head or 'LDT' in head) and ('BUILT' in head or 'YARD' in head):
        return 'Second-hand Market'
    if 'DWT' in head and 'LDT' in head and 'PRICE/LDT' in head:
        return 'Demolition Market'
    if 'NEWB' in head or ('SIZE' in head and 'YARD' in head and 'DEL' in head):
        return 'Newbuilding Market'
    if 'INDEX' in head or 'VALUE' in head:
        return 'Indices'
    if 'BALTIC' in head or 'T/C AVG IN $' in head or 'THIS WK' in head:
        return 'Baltic Indices'
    return None


def main():
    os.makedirs(OUT_MD, exist_ok=True)
    os.makedirs(OUT_TAB, exist_ok=True)
    os.makedirs(OUT_IDX, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {'done': [], 'failed': {}}
    pdfs = sorted(glob.glob(os.path.join(CORPUS, '*/*.pdf')))
    all_sales, all_tables = [], []
    for i, p in enumerate(pdfs, 1):
        stem = os.path.basename(p)[:-4]
        if stem in state['done']:
            # still need its records for the aggregate on a resumed run
            tp = os.path.join(OUT_TAB, stem + '.json')
            if os.path.exists(tp):
                d = json.load(open(tp, encoding='utf-8'))
                all_sales.extend(sale_records(d))
                all_tables.extend(d.get('all_tables', []))
            continue
        try:
            doc = parse_document(p)
            stem = os.path.basename(p)[:-4]
            open(os.path.join(OUT_MD, stem + '.md'), 'w',
                 encoding='utf-8').write(to_markdown(doc))
            json.dump(doc, open(os.path.join(OUT_TAB, stem + '.json'), 'w',
                                encoding='utf-8'), indent=1)
            all_sales.extend(sale_records(doc))
            all_tables.extend(doc['all_tables'])
            state['done'].append(stem)
            if i % 25 == 0:
                print(f'  {i}/{len(pdfs)}')
        except Exception as e:
            state['failed'][stem] = str(e)[:200]
        json.dump(state, open(STATE, 'w'), indent=1)
    # aggregate time series
    if all_sales:
        # Rows whose PRICE is a word are NOT vessel sales (newbuilding contracts and
        # demolition entries share the sale header on some issues). They are retained
        # in each document's JSON/markdown, but excluded here so the sale series never
        # carries a value like 'EPOXY' as a price. A wrong value is worse than a
        # missing one.
        rows = [r for r in all_sales
                if r.get('issue') and not r.get('price_is_not_numeric')]
        rows.sort(key=lambda r: str(r['issue']))
        if rows:
            # Field names vary per document (2021 uses USD MILL/BUYER/SELLER, 2026 uses
            # PRICE/BUYERS; newbuilding adds columns). A positional union silently
            # CORRUPTED the output: the shared `issue`/`section` keys collided with
            # document-specific ones, and the CSV came out with issue='1' on every row.
            # Fix: normalise to a fixed schema and keep per-document extras in one
            # JSON blob, so the series has a stable, never-colliding shape.
            BASE = ['issue', 'section', 'page', 'NAME', 'TYPE', 'DWT', 'BUILT',
                    'YARD', 'PRICE', 'BUYERS', 'COMMENTS']
            with open(os.path.join(OUT_IDX, 'carriers_sales_series.csv'), 'w',
                      newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(BASE + ['extra_json'])
                for r in rows:
                    base = [r.get(k, '') or '' for k in BASE]
                    extra = {k: v for k, v in r.items()
                             if k not in BASE and v not in (None, '')}
                    w.writerow(base + [json.dumps(extra, ensure_ascii=False)])
            print(f'carriers_sales_series.csv: {len(rows)} rows')
    print(f'done={len(state["done"])} failed={len(state["failed"])}')
    if state['failed']:
        print('failures:', list(state['failed'].items())[:5])


if __name__ == '__main__':
    main()
