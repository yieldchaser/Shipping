"""Extract Banchero Costa REPORTED SALES (sale & purchase) deal tables.

One row per reported deal. Evidence + layout notes: scratch/banchero/NOTES.md.

Why not camelot/pdfplumber tables: the Banchero deal tables are borderless and
pdfplumber returns each row as ONE cell (measured on
2026_W35 page 14 -> a single column of 14 strings), and camelot-stream returns
the whole page as one table because the prose columns trip its separator
heuristic. extract_all.py already establishes the working pattern for this
corpus: the text layer is the primary value source, geometry only supplies the
grid. This script does exactly that, scoped to the deal table.

Pipeline
  1. pymupdf word boxes -> visual lines (group by `top`).
  2. A deal row is a line whose FIRST word is a vessel-type token (Bulk, Tank,
     ...) and which carries >= 4 words. Nothing else in a Banchero weekly
     produces a run of consecutive type-first lines; the longest such run (with
     a year-presence tiebreak, to reject 1-line prose false positives) is the
     deal table.
  3. Column separators = x-ranges covered by NO word in ANY row of the run.
  4. Columns are placed by CONTENT KIND (type / imo / year / numeric / date /
     text) anchored on the vessel-type column, because most Banchero weeklies
     print no header row at all (measured: only 5 of 243 files carry a
     "TYPE VESSEL NAME ..." line).
  5. Anything unverifiable is logged as a failure, never guessed.

Nothing is inferred: absent price -> NULL; 'Undisclosed' -> NULL.

Usage: python3 scripts/extract/banchero_deals.py [--limit N] [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

import pymupdf

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Vessel-type first column. 'dwt' deliberately EXCLUDED: prose lines such as
# "dwt built 2011 Mitsui, sold at $17.95" otherwise give 1-line false runs.
TYPES = {"bulk", "bulker", "tank", "tanker", "container", "lpg", "lng", "gas",
         "car", "carrier", "reefer", "general", "pax", "chemical", "roro",
         "drillship", "barge", "crude", "chem", "product", "pctc", "fso",
         "mpp", "woodchip", "cement", "asphalt", "bitumen", "bunker",
         "dredger", "ferry", "passenger", "fishing", "cargo", "dry", "lnge",
         "prod", "cnt"}
TYPE_CANON = {"bulk": "Bulk", "bulker": "Bulk", "tank": "Tank", "tanker": "Tank",
              "container": "Container", "lpg": "LPG", "lng": "LNG", "gas": "Gas",
              "car": "Car carrier", "carrier": "Carrier", "reefer": "Reefer",
              "general": "General cargo", "pax": "Pax", "chemical": "Chemical",
              "roro": "RoRo", "drillship": "Drillship", "barge": "Barge",
              "crude": "Crude", "chem": "Chemical", "product": "Product",
              "pctc": "PCTC", "fso": "FSO", "mpp": "MPP",
              "woodchip": "Woodchip", "cement": "Cement", "asphalt": "Asphalt",
              "bitumen": "Bitumen", "bunker": "Bunker", "dredger": "Dredger",
              "ferry": "Ferry", "passenger": "Passenger", "fishing": "Fishing",
              "cargo": "Cargo", "dry": "Dry", "prod": "Product",
              "cnt": "Container"}  # noqa: E501

YEAR_RE = re.compile(r"^(19[5-9]\d|20[0-4]\d)$")
IMO_RE = re.compile(r"^\d{7}$")
NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
NUMC_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
MONTHY = re.compile(r"^([A-Za-z]{3,9})[-/ ](\d{2}|\d{4})$")
SLASHMY = re.compile(r"^(\d{1,2})[/-](\d{4})$")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], start=1)}
TYPES_WORD = re.compile(r"\b(bulk|tank(?:er)?|container|lng|lpg|gas|car|"
                        r"reefer|general|chemical|pax)\b", re.I)


def norm_txt(s):
    """NFKC-fold word text: the PDFs contain ligatures ('Thor Inﬁnity') and
    non-breaking spaces that would otherwise enter the dataset verbatim."""
    import unicodedata
    return unicodedata.normalize("NFKC", s).replace("\u00a0", " ")


def group_lines(words, tol=2.2):
    words = sorted(([w[0], w[1], w[2], w[3], norm_txt(w[4]),
                     *w[5:]] for w in words),
                   key=lambda w: (w[1], w[0]))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur_top is None or abs(w[1] - cur_top) <= tol:
            cur.append(w)
            cur_top = w[1] if cur_top is None else cur_top
        else:
            lines.append(cur)
            cur, cur_top = [w], w[1]
    if cur:
        lines.append(cur)
    for ln in lines:
        ln.sort(key=lambda w: w[0])
    return lines


def line_text(ln):
    return " ".join(w[4] for w in ln)


def is_deal_line(ln):
    if len(ln) < 4:
        return False
    return ln[0][4].strip().lower().rstrip(":") in TYPES


TON_RE = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$|^\d{4,6}$")


def is_typeless_deal_line(ln):
    """A deal row in an edition whose table has NO vessel-type column.

    Measured on 2023_W07 page 11: rows read
      'HL Aquamarine 207,999 2021 New Times'
      'Omicron Crest 76,737 2004 Sasebo Indonesian 12 old sale, Bwts fitted'
    i.e. vessel, DWT, BUILT, YARD, BUYERS, PRICE, NOTE - the type column simply
    is not printed. Signature: 1-3 leading name words, then a tonnage figure
    immediately followed by a 4-digit build year.
    """
    if len(ln) < 4:
        return False
    tok = [w[4].strip() for w in ln]
    if tok[0].lower().rstrip(":") in TYPES:
        return False
    if not re.match(r"^[A-Za-z]", tok[0]):
        return False
    for i in range(1, len(tok) - 1):
        if TON_RE.match(tok[i]):
            if YEAR_RE.match(tok[i + 1]) or (i + 2 < len(tok) and YEAR_RE.match(tok[i + 2])):
                return True
    return False


def find_runs(lines, pred=None):
    pred = pred or is_deal_line
    flags = [pred(ln) for ln in lines]
    runs, i = [], 0
    while i < len(flags):
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(flags) and flags[j + 1]:
            j += 1
        runs.append((i, j))
        i = j + 1
    return runs


def _gaps_of_row(row, min_gap):
    """Midpoints of x-gaps inside one row's word intervals."""
    ivs = sorted((w[0], w[2]) for w in row)
    merged = []
    for a, b in ivs:
        if merged and a <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = []
    for k in range(1, len(merged)):
        if merged[k][0] - merged[k - 1][1] >= min_gap:
            out.append((merged[k - 1][1] + merged[k][0]) / 2)
    return out, merged


def column_bounds(rows, min_gap=2.5, support=0.3, cluster_pt=6.0, merge_pt=5.0,
                  verbose=False):
    """Column separators from PER-ROW gaps, clustered across rows.

    Not the union of all word intervals: measured on 2022_W12 page 11, rows carry
    merged words ('2013MinaminipponUndisclosed' spanning built+yard+buyers,
    '2400cbm2015' spanning dwt+built) which erase a separator from the union
    layout and collapse four columns into one. Nor a seed comparison: the
    type/vessel gap in 2022_W12 wanders over 31..41 pt across the 18 rows, and
    comparing against a cluster seed split it into five sub-threshold clusters
    and dropped the column entirely. Single-linkage on the sorted gap positions
    handles both.

    Quorum is 0.3 of rows, not 0.4: a separator is only observable in a row that
    has BOTH neighbouring cells filled. In 2026_W35 the SS and NOTE cells are
    both filled in only 5 of 14 rows, so a 0.4 quorum deletes the SS column and
    folds SS dates into the note (measured; the 0.3 quorum keeps `ss_due`).
    """
    pts_by_row = []
    for r in rows:
        g, _ = _gaps_of_row(r, min_gap)
        pts_by_row.append(g)
    pts = sorted(p for g in pts_by_row for p in g)
    clusters = []
    for p in pts:
        if clusters and p - clusters[-1][-1] <= cluster_pt:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    seps = []
    for cl in clusters:
        rows_hit = sum(1 for g in pts_by_row
                       if any(abs(x - cl[len(cl) // 2]) <= cluster_pt for x in g))
        if rows_hit >= max(2, int(round(support * len(rows)))):
            seps.append(cl[len(cl) // 2])
    merged = []
    for s in sorted(seps):
        if merged and s - merged[-1] < merge_pt:
            continue
        merged.append(s)
    x0 = min(w[0] for r in rows for w in r)
    x1 = max(w[2] for r in rows for w in r)
    return [x0] + merged + [x1 + 1]


def rows_valid(grid):
    """Fraction of rows that look like real deal rows.

    Guards against the false positives measured on this corpus:
      2022_W28 / 2023_W07 -> the 'LNG TTF Netherlands usd/mmbtu 46.89 ...' price
      table, whose rows start with 'LNG' and so satisfy the type test;
      2026_W22          -> a multi-column news page whose wrapped lines start
      with 'LNG' / 'BULK'.
    A deal row must carry a 4-digit build year AND a thousands-separated tonnage
    (or a 7-digit IMO).
    """
    if not grid:
        return 0.0
    # A deal row must carry a 4-digit build year AND a tonnage figure. Tonnage
    # spellings measured in this corpus: '156,881' (2026_W35), '92.648'
    # (2026_W28) and bare '177486' (2024_W30 - no separator at all).
    ACCEPT = re.compile(r"\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{5,7}\b|\b\d{7}\b")
    ok = 0
    for r in grid:
        txt = " ".join(r)
        if not re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", txt):
            continue
        if ACCEPT.search(txt):
            ok += 1
    return ok / len(grid)


def split_cols(rows, bounds):
    out = []
    ncols = len(bounds) - 1
    for r in rows:
        cols = [[] for _ in range(ncols)]
        for w in r:
            x = w[0]
            k = ncols - 1
            for c in range(ncols):
                if bounds[c] <= x < bounds[c + 1]:
                    k = c
                    break
            cols[k].append(w[4])
        out.append([" ".join(c).strip() for c in cols])
    return out


def is_priceish(v):
    """A price cell, including Banchero's qualified spellings.

    Measured spellings: '11.9', '107', 'high 21', 'low 15', 'mid/high 22',
    'rgn 28', 'rgn/xs 20', 'w/mid 80', 'xs 30', 'ex 13', 'high 30s', '/'.
    A qualified price states a BAND, not a number, so price_usd_m stays NULL for
    those (the raw text is preserved in comments).
    """
    s = v.strip().lower()
    s = re.sub(r"^(?:mid|high|low|rgn|region|xs|ex|w|about|around|usd|"
               r"\$|/| |-)+", "", s)
    s = s.rstrip("s")
    return bool(re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+|\d+\.\d+|\d{1,3},\d{1,3}"
                             r"|\d+", s))


def col_kind(vals):
    v = [x for x in vals if x]
    if not v:
        return "empty", 0.0
    n = len(v)
    frac = {
        "type": sum(1 for x in v if x.lower() in TYPES) / n,
        "imo": sum(1 for x in v if IMO_RE.match(x) and int(x) >= 1000000) / n,
        "year": sum(1 for x in v if YEAR_RE.match(x)) / n,
        "num": sum(1 for x in v if NUM_RE.match(x.replace(",", ""))) / n,
        "numc": sum(1 for x in v if NUMC_RE.match(x)) / n,
        "date": sum(1 for x in v if MONTHY.match(x) or SLASHMY.match(x)) / n,
        "price": sum(1 for x in v if is_priceish(x)) / n,
    }
    if frac["type"] >= 0.6:
        return "type", frac["type"]
    if frac["imo"] >= 0.6:
        return "imo", frac["imo"]
    if frac["year"] >= 0.6:
        return "year", frac["year"]
    if frac["date"] >= 0.5:
        return "date", frac["date"]
    if max(frac["num"], frac["numc"]) >= 0.6:
        return "num", max(frac["num"], frac["numc"])
    if frac["price"] >= 0.5:
        return "price", frac["price"]
    return "text", 0.0


def nums(vals):
    out = []
    for x in vals:
        s = x.replace(",", "")
        if NUM_RE.match(s):
            try:
                out.append(float(s))
            except ValueError:
                pass
    return out


def parse_dwt(raw):
    """DWT cell -> int tonnes.

    Banchero writes DWT with a comma OR a period as the thousands separator
    depending on the edition: 2026_W28 prints "92.648" (= 92,648 t) while
    2026_W35 prints "156,881". Measured on both files. A bare decimal like
    "19.998" is therefore 19,998 t, not 19.998 t.
    """
    if not raw:
        return None
    s = raw.strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return int(s.replace(",", "").replace(".", ""))
    if re.fullmatch(r"\d+", s):
        return int(s)
    if re.fullmatch(r"\d+\.\d+", s):
        return int(float(s))
    return None


def parse_price(raw):
    """Price cell -> (usd_million, raw_qualifier).

    Banchero writes prices three ways in this corpus and all three were measured:
      '11.9' '107'   plain
      '73,50' '86,75' '25,15'  COMMA AS DECIMAL separator (= 73.50, 86.75, 25.15
                     mln). Verified against prose: table '25,375' for HANTON
                     TRADER I, narrative '$25.375mln each' (2022_W36).
      'high 21' 'rgn 28' 'rgn/xs 20'  a BAND, not a number -> NULL.
    Reading '73,50' as 7,350 mln (thousands) put 8 absurd prices in the ledger
    before this rule.
    """
    if not raw:
        return None, None
    s = raw.strip()
    m = re.fullmatch(r"(\d{1,3}),(\d{1,3})", s)
    if m:
        dec = float(f"{m.group(1)}.{m.group(2)}")
        if 0.1 <= dec <= 2000:  # plausible USD-million band
            return dec, None
    s2 = s.replace(",", "")
    if NUM_RE.match(s2):
        return float(s2), None
    return None, raw


def norm_month_year(raw):
    if not raw:
        return None
    s = raw.strip()
    m = SLASHMY.match(s)
    if m:
        mo, yr = int(m.group(1)), int(m.group(2))
        return f"{yr:04d}-{mo:02d}" if 1 <= mo <= 12 else None
    m = MONTHY.match(s)
    if m:
        name, num = m.group(1).lower(), m.group(2)
        if name[:3] in MONTHS:
            if len(num) == 2:
                iv = int(num)
                yr = 2000 + iv if iv < 70 else 1900 + iv
            else:
                yr = int(num)
            return f"{yr:04d}-{MONTHS[name[:3]]:02d}"
    return None


def report_date_from_stem(stem):
    m = re.search(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])", stem)
    if m:
        y, wk = int(m.group(1)), int(m.group(2))
        if 1 <= wk <= 53:
            try:
                return dt.date.fromisocalendar(y, wk, 1).isoformat()
            except ValueError:
                return None
    m = re.search(r"[Ww]eek[_-]?(\d{1,2})[_-]?((?:19|20)\d\d)", stem)
    if m:
        wk, y = int(m.group(1)), int(m.group(2))
        try:
            return dt.date.fromisocalendar(y, wk, 1).isoformat()
        except ValueError:
            return None
    return None


def place_columns(kinds, typed=True):
    """Kind-driven column placement anchored on the leading type/vessel column.

    Returns (names, ok). names[k] is the output field for grid column k, or
    None when the column is unmapped (then it is folded into comments).
    Observed orders, all head-anchored on the first column:
      10: type vessel imo  dwt built yard buyer price ss  note
       9: type vessel imo  dwt built yard buyer price ss
       9: type vessel      dwt built yard buyer price ss  note   (2024_W30)
       8: type vessel      dwt built yard buyer price note
       7: vessel           dwt built yard buyer price note       (2023_W07, no type col)
    """
    n = len(kinds)
    names = [None] * n
    k = 0
    if typed:
        if kinds[0][0] != "type":
            return names, False
        names[0] = "vessel_type"
        k = 1
    else:
        if kinds[0][0] != "text":
            return names, False

    def skip_empty(j):
        """Advance past grid columns that are blank in EVERY row.

        2022_W40 prints an IMO column that is empty for the whole week; without
        this the 'built' check lands on it and the report fails verification.
        """
        while j < n and kinds[j][0] == "empty":
            j += 1
        return j

    k = skip_empty(k)
    if n < k + 3 or kinds[k][0] != "text":
        return names, False
    names[k] = "vessel"
    k = skip_empty(k + 1)
    if k < n and kinds[k][0] == "imo":
        names[k] = "imo"
        k = skip_empty(k + 1)
    if k < n and kinds[k][0] == "num":
        names[k] = "dwt"
        k = skip_empty(k + 1)
    else:
        return names, False
    if k < n and kinds[k][0] == "year":
        names[k] = "built"
        k = skip_empty(k + 1)
    else:
        return names, False
    if k < n and kinds[k][0] == "text":
        names[k] = "yard"
        k = skip_empty(k + 1)
    if k < n and kinds[k][0] == "text":
        names[k] = "buyer"
        k = skip_empty(k + 1)
    if k < n and kinds[k][0] in ("num", "price"):
        names[k] = "price_usd_m"
        k = skip_empty(k + 1)
    # tail
    if k < n and kinds[k][0] == "date":
        names[k] = "ss_due"
        k = skip_empty(k + 1)
        if k < n and kinds[k][0] == "date":
            names[k] = "dd_due"
            k = skip_empty(k + 1)
    for j in range(k, n):
        names[j] = "comments" if names[j] is None else names[j]
    return names, True


def extend_table(cand, lines_all, max_dy=30.0):
    """Grow a validated candidate run over the rows its predicate missed.

    A run stops at any line that is not a deal row, so one interleaved chart
    block or one row with a missing tonnage splits a table and truncates it
    (measured on 2023_W07: the run detector kept 10 of the 21 rows). Extend by
    row geometry instead: keep neighbouring lines that live inside the table's
    x-span, start in the table's first column, and carry a year + a tonnage.
    Stop when the vertical step to the next line exceeds max_dy so the extension
    cannot jump into the next section of the page.
    """
    typed, gap = cand["typed"], cand["gap"]
    i0, i1 = cand["run"]
    body0 = [lines_all[k] for k in range(i0, i1 + 1)]
    bounds = column_bounds(body0, min_gap=gap)
    if len(bounds) - 1 < 5:
        return None
    x_lo, x_hi = bounds[0] - 3, bounds[-1] - 1
    first_lo, first_hi = bounds[0] - 3, bounds[1]
    YR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
    TON = re.compile(r"\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,7}\b")

    def ok_line(k):
        ln = lines_all[k]
        if not ln or len(ln) < 4:
            return False
        # the line must still LOOK like a deal row, not merely contain a year and
        # a number: without this the extension walks into the narrative prose of
        # the same page (2021_W26: 'dwt built 2001 ... by Hyundai Heavy' landed in
        # the ledger as a deal).
        if not (is_deal_line(ln) or is_typeless_deal_line(ln)):
            return False
        if min(w[0] for w in ln) < x_lo or max(w[2] for w in ln) > x_hi:
            return False
        if not (first_lo <= ln[0][0] < first_hi):
            return False
        txt = line_text(ln)
        return bool(YR.search(txt) and TON.search(txt))

    # walk down then up from the run
    keep_down = []
    prev_top = lines_all[i1][0][1]
    for k in range(i1 + 1, len(lines_all)):
        ln = lines_all[k]
        if not ln:
            continue
        top = ln[0][1]
        if top - prev_top > max_dy:
            break
        prev_top = top
        if ok_line(k):
            keep_down.append(k)
    keep_up = []
    prev_top = lines_all[i0][0][1]
    for k in range(i0 - 1, -1, -1):
        ln = lines_all[k]
        if not ln:
            continue
        top = ln[0][1]
        if prev_top - top > max_dy:
            break
        prev_top = top
        if ok_line(k):
            keep_up.append(k)
    idx = sorted(keep_up + list(range(i0, i1 + 1)) + keep_down)
    body = [lines_all[k] for k in idx]
    bounds = column_bounds(body, min_gap=gap)
    if len(bounds) - 1 < 5:
        return None
    grid = split_cols(body, bounds)
    kinds = [col_kind([r[k] for r in grid]) for k in range(len(grid[0]))]
    names, ok = place_columns(kinds, typed=typed)
    if not ok:
        return None
    if typed:
        ntype = sum(1 for r in grid if r[0].lower().rstrip(":") in TYPES)
        if ntype < max(2, len(grid) * 0.6):
            return None
    v = rows_valid(grid)
    if v < 0.6:
        return None
    return {"page": cand["page"], "run": (idx[0], idx[-1]), "grid": grid,
            "names": names, "kinds": kinds, "gap": gap, "typed": typed,
            "valid": v, "n": len(grid)}


WEIRD_PUNCT = set('!"#$%&*+~^=@[]{}|\\<>\u00b7\u00a8\u00ac')


def page_garbled_share(text):
    """Share of 'weird' punctuation on a page - the glyph-mojibake tell.

    Some weeklies (most of 2025, a few 2026) embed a subset font with no usable
    ToUnicode map, so their table pages decode to ASCII punctuation soup:
        '!!"#$%"&#'!(*#(!+'   '!&,$#'   'I16BB10 3334C 6546'
    while the prose pages of the SAME file decode fine, so this must be measured
    per page. Measured shares: 0.01-0.06 on healthy pages (including chart pages
    of every year) vs 0.10-0.48 on mojibake pages. extract_all.py's Latin-Extended
    predicate does NOT catch this variant (the glyphs map into ASCII punctuation).
    """
    t = text or ""
    if len(t) < 200:
        return None
    return sum(1 for c in t if c in WEIRD_PUNCT) / len(t)


def process_pdf(path):
    rel = os.path.relpath(path, REPO).replace("\\", "/")
    stem = os.path.splitext(os.path.basename(path))[0]
    rdate = report_date_from_stem(stem)
    diag = {"file": rel, "report_date": rdate, "status": "no-table",
            "n_rows": 0, "page": None, "n_cols": None, "names": None,
            "kinds": None, "header": None}
    rows = []
    doc = pymupdf.open(path)
    page_lines = []
    had_marker = False
    garbled_pages = 0
    try:
        for pno in range(doc.page_count):
            txt = doc[pno].get_text() or ""
            if "REPORTED SALES" in txt.upper():
                had_marker = True
            gs = page_garbled_share(txt)
            if gs is not None and gs >= 0.10:
                garbled_pages += 1
            page_lines.append(group_lines(doc[pno].get_text("words")))
    finally:
        doc.close()
    diag["had_reported_sales_marker"] = had_marker
    diag["garbled_pages"] = garbled_pages

    # Build every candidate grid (run x column-gap x layout) and keep only those
    # whose rows pass the deal-row validity gate.
    cands = []
    for pno, lines in enumerate(page_lines):
        for typed, pred, minlen in ((True, is_deal_line, 1),
                                    (False, is_typeless_deal_line, 3)):
            for run in find_runs(lines, pred):
                if run[1] - run[0] + 1 < minlen:
                    continue
                body = [lines[k] for k in range(run[0], run[1] + 1)]
                for gap in (2.5, 2.0, 1.5):
                    bounds = column_bounds(body, min_gap=gap)
                    if len(bounds) - 1 < 5:
                        continue
                    grid = split_cols(body, bounds)
                    kinds = [col_kind([r[k] for r in grid])
                             for k in range(len(grid[0]))]
                    names, ok = place_columns(kinds, typed=typed)
                    if not ok:
                        continue
                    v = rows_valid(grid)
                    if v < 0.6:
                        continue
                    cands.append({"page": pno, "run": run, "grid": grid,
                                  "names": names, "kinds": kinds, "gap": gap,
                                  "typed": typed, "valid": v, "n": len(grid)})
                    break
    if not cands:
        if not had_marker and garbled_pages > 0 and garbled_pages >= 3:
            diag["status"] = "garbled-text-layer"
        elif not had_marker:
            diag["status"] = "no-table"
        else:
            diag["status"] = "marker-but-no-parsable-table"
        return rows, diag
    # Reports can print MORE THAN ONE deal table: 2023_W07 page 11 carries a dry
    # table and a tanker table, and an interleaved chart block splits a single
    # table into several runs. Accept every candidate that validates, extend each
    # over the rows the run predicate missed, then dedupe identical deals.
    cands.sort(key=lambda c: (-c["n"], -c["valid"]))
    tables, seen = [], []
    for c in cands:
        rng = set(range(c["run"][0], c["run"][1] + 1))
        if any(rng <= s for s in seen):
            continue
        t = extend_table(c, page_lines[c["page"]]) or c
        seen.append(set(range(t["run"][0], t["run"][1] + 1)))
        tables.append(t)
    if not tables:
        diag["status"] = "schema-verify-failed"
        return rows, diag
    diag.update({"page": [t["page"] for t in tables],
                 "n_tables": len(tables),
                 "n_cols": [len(t["grid"][0]) for t in tables],
                 "names": tables[0]["names"],
                 "kinds": [k[0] for k in tables[0]["kinds"]],
                 "typed": [t["typed"] for t in tables],
                 "valid_frac": [round(t["valid"], 3) for t in tables]})
    for t in tables:
        lines = page_lines[t["page"]]
        if t["run"][0] - 1 >= 0:
            prev = line_text(lines[t["run"][0] - 1])
            if re.search(r"\b(vessel|type)\b", prev, re.I):
                diag["header"] = prev

    raw_rows = []
    for t in tables:
        names, grid = t["names"], t["grid"]
        for r in grid:
            raw_rows.append(build_row(r, names))
    seen_keys, rows = set(), []
    for rec in raw_rows:
        key = (rec.get("vessel"), rec.get("dwt"), rec.get("built"),
               rec.get("buyer"), rec.get("price_usd_m"), rec.get("comments"),
               rec.get("imo"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rec["source_file"] = rel
        rec["report_date"] = rdate
        rows.append(rec)
    diag["status"] = "ok"
    diag["n_rows"] = len(rows)
    return rows, diag


def build_row(r, names):
    """One grid row -> one deal record (all parsing rules live here)."""
    cells = {}
    for k, nm in enumerate(names):
        if nm is None or nm == "comments":
            continue
        cells[nm] = r[k].strip() or None
    notes = [r[k].strip() for k, nm in enumerate(names)
             if nm == "comments" and r[k].strip()]
    rec = {f: None for f in
           ["vessel_type", "vessel", "imo", "dwt", "built", "buyer", "yard",
            "seller", "price_usd_m", "ss_due", "dd_due", "delivery",
            "comments"]}
    rec.update({k: v for k, v in cells.items() if k in rec})
    # Some 2021-2023 editions print the type and the DWT in one tight cell, so
    # the type arrives as 'Prod 50600' / 'Cnt 66,000'. Split the numeric tail off
    # (and use it as the DWT only when the DWT cell is genuinely empty).
    vt = rec.get("vessel_type")
    if vt:
        m = re.match(r"^([A-Za-z][A-Za-z/.\- ]*?)\s+([\d,.]+)$", vt.strip())
        if m:
            if rec.get("dwt") is None:
                rec["dwt"] = m.group(2)
            vt = m.group(1)
        vt = vt.strip()
        rec["vessel_type"] = TYPE_CANON.get(vt.lower(), vt)
    if rec.get("imo") and not IMO_RE.match(rec["imo"]):
        rec["imo"] = None
    if rec.get("built") and not YEAR_RE.match(rec["built"]):
        rec["built"] = None
    if rec.get("dwt"):
        rec["dwt"] = parse_dwt(rec["dwt"])
    price, raw = parse_price(rec.get("price_usd_m"))
    rec["price_usd_m"] = price
    ss_raw = rec.get("ss_due")
    if ss_raw:
        my = norm_month_year(ss_raw)
        if my:
            rec["ss_due"] = my
        else:
            rec["ss_due"] = None
            notes.append(f"SS: {ss_raw}")
    if rec.get("dd_due"):
        rec["dd_due"] = norm_month_year(rec["dd_due"])
    note = " ".join(notes)
    if not rec.get("ss_due"):
        m = re.search(r"\bSS[/ ]*DD[ :]*(\d{1,2})[/-](\d{4})", note, re.I)
        if m:
            rec["ss_due"] = norm_month_year(f"{m.group(1)}/{m.group(2)}")
    if not rec.get("ss_due"):
        m = re.search(r"\bSS[ :]*\(?(\d{1,2})[/-](\d{4})", note, re.I)
        if m:
            rec["ss_due"] = norm_month_year(f"{m.group(1)}/{m.group(2)}")
    if not rec.get("dd_due"):
        m = re.search(r"\bDD[ :]*\(?(\d{1,2})[/-](\d{4})", note, re.I)
        if m:
            rec["dd_due"] = norm_month_year(f"{m.group(1)}/{m.group(2)}")
    m = re.search(r"(?:dely|delivery)\b[ :]*([A-Za-z0-9/\-]{2,20})", note, re.I)
    if m:
        rec["delivery"] = m.group(1).strip()
    if raw:
        note = (f"PRICE: {raw} | " + note).strip(" |")
    rec["comments"] = note or None
    return rec


def write_outputs(rows, diags, parquet_path, json_path):
    """Materialise the deal ledger + a coverage summary.

    Columns are exactly the requested schema. Every field is left NULL when the
    source does not state it ('Undisclosed' price -> NULL, no seller column in
    Banchero's table -> NULL seller).
    """
    import pandas as pd

    COLS = ["source_file", "report_date", "vessel", "imo", "vessel_type", "dwt",
            "built", "buyer", "seller", "price_usd_m", "ss_due", "dd_due",
            "delivery", "comments", "yard"]
    df = pd.DataFrame([{c: r.get(c) for c in COLS} for r in rows], columns=COLS)
    df = df[["source_file", "report_date", "vessel", "imo", "vessel_type", "dwt",
             "built", "buyer", "seller", "price_usd_m", "ss_due", "dd_due",
             "delivery", "comments", "yard"]]
    for c in ("imo", "dwt", "built"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df["price_usd_m"] = pd.to_numeric(df["price_usd_m"], errors="coerce")
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    for c in ("source_file", "vessel", "vessel_type", "buyer", "seller",
              "ss_due", "dd_due", "delivery", "comments", "yard"):
        df[c] = df[c].astype("string")
    os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
    df.to_parquet(parquet_path, index=False)

    # IMO check digit (IMO numbers carry a mod-10 check on the first six digits).
    # NA-safe: pandas' nullable Int64 yields pd.NA, and int(pd.NA) raises
    # TypeError - that aborted the whole write (twice) before this guard.
    def _num_or_none(v):
        if v is None:
            return None
        try:
            if v != v:  # NaN
                return None
        except Exception:
            pass
        if str(v).strip() in ("", "<NA>", "nan", "NaN", "None", "NaT"):
            return None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    def imo_valid(v):
        n = _num_or_none(v)
        if n is None:
            return None
        s = str(n)
        if len(s) != 7:
            return False
        return sum(int(d) * w for d, w in zip(s[:6], range(7, 1, -1))) % 10 == int(s[6])

    imo_ok = [imo_valid(v) for v in df["imo"].tolist()]
    pop = {c: round(float(df[c].notna().mean()), 4) for c in df.columns}
    from collections import Counter
    statuses = Counter(d["status"] for d in diags)
    summary = {
        "source": "corpus/01-brokers/banchero_costa/**/*.pdf",
        "section": "SALE & PURCHASE -> REPORTED SALES (secondhand deal table)",
        "n_reports_total": len(diags),
        "n_reports_with_deals": int(statuses.get("ok", 0)),
        "n_reports_with_garbled_pages": sum(
            1 for d in diags if d.get("garbled_pages", 0) > 0),
        "n_rows_failed_unparsed": None,
        "report_status_counts": dict(statuses),
        "n_deals": int(len(df)),
        "n_reports_span": {
            "min_report_date": (df["report_date"].min().date().isoformat()
                                if df["report_date"].notna().any() else None),
            "max_report_date": (df["report_date"].max().date().isoformat()
                                if df["report_date"].notna().any() else None),
        },
        "n_distinct_imo": int(df["imo"].nunique()),
        "imo_check_digit_pass": {
            "n_checked": sum(1 for x in imo_ok if x is not None),
            "n_pass": sum(1 for x in imo_ok if x is True),
            "n_fail": sum(1 for x in imo_ok if x is False),
        },
        "pct_populated": pop,
        "dwt_lt_1000_rows": int((df["dwt"].dropna() < 1000).sum()),
        "price_gt_1000_rows": int((df["price_usd_m"].dropna() > 1000).sum()),
        "deals_per_year": {str(k): int(v) for k, v in
                           df["report_date"].dt.year.value_counts().sort_index().items()},
        "vessel_type_counts": {str(k): int(v) for k, v in
                               df["vessel_type"].value_counts().items()},
        "failed_reports": [
            {"file": d["file"], "status": d["status"],
             "had_reported_sales_marker": d.get("had_reported_sales_marker"),
             "garbled_pages": d.get("garbled_pages", 0)}
            for d in diags if d["status"] not in ("ok", "no-table")],
        "notes": [
            "'no-table' = the week's S&P section is prose only (no REPORTED "
            "SALES table printed); verified by reading the page text.",
            "'garbled-text-layer' = the PDF's table pages decode to ASCII "
            "punctuation soup (subset font with no ToUnicode map): the table may "
            "exist but is UNREADABLE without OCR. Confirmed on most of 2025 and "
            "a few 2026 weeklies - this is the reason 2025 holds far fewer deals "
            "than 2021-2024, NOT a change in Banchero's publishing.",
            "price_usd_m is USD million, as printed. A qualifier price "
            "('high 21', 'region 27', 'rgn/xs 20') is NOT a number, so it is "
            "NULL with the raw text preserved in comments as 'PRICE: ...'.",
            "seller is always NULL: Banchero's table has no seller column.",
            "ss_due/dd_due are 'YYYY-MM'. Older layouts print SS/DD inside the "
            "note column ('SS/DD 10/2021'); those are parsed out too.",
            "Price cells with a comma are read with a DECIMAL comma when a "
            "thousands reading would be implausible (table '73,50' -> 73.5 mln; "
            "verified against the narrative '$25.375mln each' for '25,375').",
            "Some editions print DWT truncated to thousands ('Solando 20' for a "
            "20,000 dwt tanker, 'Eships Barracuda 13'); those literal values are "
            "kept as printed rather than scaled by guesswork.",
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    return df, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--out", default=os.path.join(REPO, "scratch", "banchero",
                                                  "deals.jsonl"))
    ap.add_argument("--parquet", default=None,
                    help="also write the final parquet + JSON summary here "
                         "(default data/extracted/banchero_deals.parquet when "
                         "--write-final is given)")
    ap.add_argument("--write-final", action="store_true",
                    help="write data/extracted/banchero_deals.{parquet,json}")
    a = ap.parse_args()
    pat = a.glob or os.path.join(REPO, "corpus", "01-brokers", "banchero_costa",
                                 "**", "*.pdf")
    pdfs = sorted(glob.glob(pat, recursive=True))
    if a.limit:
        pdfs = pdfs[-a.limit:]
    all_rows, diags = [], []
    for p in pdfs:
        try:
            rows, diag = process_pdf(p)
        except Exception as exc:  # noqa: BLE001
            rows = []
            diag = {"file": os.path.relpath(p, REPO).replace("\\", "/"),
                    "status": "crash", "error": f"{type(exc).__name__}: {exc}"[:200]}
        all_rows.extend(rows)
        diags.append(diag)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    dpath = os.path.splitext(a.out)[0] + "_diag.json"
    with open(dpath, "w", encoding="utf-8") as f:
        json.dump(diags, f, indent=1)
    from collections import Counter
    print(json.dumps(Counter(d["status"] for d in diags), indent=1))
    print("rows:", len(all_rows), "files:", len(pdfs))
    for d in diags:
        if d["status"] not in ("ok", "no-table"):
            print("FAIL", d["status"], d["file"].split("/")[-1],
                  d.get("n_cols"), d.get("kinds"), d.get("grid_sample"))
    if a.write_final or a.parquet:
        pq = a.parquet or os.path.join(REPO, "data", "extracted",
                                       "banchero_deals.parquet")
        js = os.path.splitext(pq)[0] + ".json"
        df, summary = write_outputs(all_rows, diags, pq, js)
        print("WROTE", pq, "rows", len(df))
        print(json.dumps({k: v for k, v in summary.items()
                          if k not in ("failed_reports", "pct_populated")},
                         indent=1))
        print("pct_populated:", json.dumps(summary["pct_populated"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
