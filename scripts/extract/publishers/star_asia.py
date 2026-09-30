"""
Star Asia - publisher-specific helpers.

MEASURED facts. Every one was read off real documents; none is assumed from
Advanced Shipping, whose conventions differ in two ways that matter:

  * CHARTS ARE RASTER, NOT VECTOR. Star Asia's chart pages carry an embedded
    image covering 20-38% of the page (p4 dry-bulk values, p7 tanker values,
    p9 container values, p10/11 recycling price trend, p17 commodities) and
    those pages yield 0 line items and 0 curve items. Advanced Shipping's
    axis-tick chart calibration is therefore NOT reusable: there is no vector
    geometry to read. In 2021-2025 the chart pixels carry no printed values.
  * A COMPANION TABLE EXISTS ONLY IN 2026. 'SEGMENT (AVG) | 2022 | 2023 | 2024 |
    2025 | 2026 YTD' appears on pages 4/7/9 in 16 of 32 sampled 2026 documents
    and in 0 of the 161 documents from 2021-2025. It carries ANNUAL AVERAGES
    per segment, not the chart's weekly series, so it supplements the chart
    rather than replacing it.
  * BOTH SEPARATORS MEAN THOUSANDS, AND BOTH MEAN DECIMALS. Measured in the
    BDI row of 2024 W02: CURRENT='1.460', LAST WEEK='2,086', LAST YEAR='763',
    W-O-W CHANGE='-30.01%'; and (1460-2086)/2086 = -30.01% exactly, so '1.460'
    is 1460 and '2,086' is 2086 IN THE SAME ROW. Shape decides, never
    assumption:
        comma,  3 trailing digits  -> thousands  ('2,086' -> 2086)
        period, exactly 3 trailing-> thousands  ('1.460' -> 1460)
        comma,  1-2 trailing      -> decimal    ('82,93' -> 82.93, '-8,84%')
        period, 1-2 trailing      -> decimal    ('83.01' -> 83.01)
        Indian grouping           -> ('7,97,000' -> 797000)
    Reading '1.460' as 1.46 is the same silent 1000x error Advanced Shipping
    taught us about, in the opposite direction.
  * pdf-inspector reconstructs Star Asia's grids AND their headers in ~0.17s
    per document. liteparse's block mode costs ~30s per document here and
    returns EMPTY headers, so the two-engine merge Advanced Shipping needed is
    neither needed nor wanted for this publisher.
  * DEFECT to repair: pdf-inspector splits one physical table when a rule
    interrupts it, and the continuation's HEADER slot is filled with its first
    DATA row (measured: 2024 W02 table 13 keeps ['VESSEL NAME','TYPE','LDT',
    'ARRIVAL','BEACHING'] while table 14's header is the data row ['ZE LENG',
    'REEFER','7,007','09.01.2024','12.01.2024']). Repaired below by inheriting
    the previous header, flagged `header_inherited` so it can never be mistaken
    for a real header.
"""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf

PUB = "star_asia"
SRC = Path("corpus/01-brokers/star_asia")


# ---------------------------------------------------------------- numbers

def parse_number(raw):
    """Parse a Star Asia numeric cell to a float, or None if it is not one.

    Shape decides the separator; the module docstring records the measurement
    behind each branch. Returns None rather than guessing - a wrong value is
    worse than a missing one.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    s = s.replace("US$", "").replace("USD", "").replace("$", "")
    s = s.replace("%", "").replace(" ", "").strip()
    if not re.fullmatch(r"[+\-]?[\d.,]+", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if "," in s and "." in s:
        # the rightmost separator is the decimal point, the other is grouping
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 3 and all(len(p) <= 3 for p in parts[1:]):
            s = "".join(parts)               # '2,086' -> 2086
        elif len(parts[-1]) <= 2:
            s = s.replace(",", ".")          # '82,93' -> 82.93
        else:
            s = "".join(parts)
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and all(len(p) <= 3 for p in parts[1:]):
            s = "".join(parts)               # '1.460' -> 1460
        # otherwise a lone period is a real decimal point ('83.01')
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


# ---------------------------------------------------------------- page kinds

CHART_MIN_COVER = 0.15      # measured: chart images cover 20-38% of their page
CHART_MIN_PX = 100_000


def page_map(pdf):
    """Per-page anatomy. `raster_cover` is the largest embedded image's share of
    the page area, which is what separates a chart page (20-38%) from a table
    page (~0-2%) on this publisher. `image_only` marks a page whose entire
    content is the raster: those are the pages a vision pass would have to
    handle, and they are listed explicitly rather than silently skipped.
    """
    out = []
    with pymupdf.open(pdf) as d:
        for i, pg in enumerate(d, start=1):
            rect = pg.rect
            area = max(rect.width * rect.height, 1.0)
            kinds = {"re": 0, "l": 0, "c": 0}
            for dr in pg.get_drawings():
                for it in dr["items"]:
                    kinds[it[0]] = kinds.get(it[0], 0) + 1
            cover, px = 0.0, 0
            for im in pg.get_images(full=True):
                px = max(px, int(im[2]) * int(im[3]))
                try:
                    box = pg.get_image_bbox(im)
                except Exception:
                    continue
                cover = max(cover, (box.width * box.height) / area)
            txt = pg.get_text()
            chart = cover >= CHART_MIN_COVER and px >= CHART_MIN_PX
            out.append({
                "page": i,
                "chars": len(txt),
                "raster_cover": round(cover, 4),
                "raster_px": px,
                "rects": kinds["re"],
                "lines": kinds["l"],
                "curves": kinds["c"],
                "chart_image": chart,
                "image_only": bool(chart and len(txt) < 400),
                "vector_chart": (kinds["l"] + kinds["c"]) > 40,
            })
    return out


# ---------------------------------------------------------------- tables

def _md_tables(md):
    tables, cur = [], None
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if cur is None:
                cur = {"header": cells, "rows": []}
            else:
                cur["rows"].append(cells)
        else:
            if cur and cur["rows"]:
                tables.append(cur)
            cur = None
    if cur and cur["rows"]:
        tables.append(cur)
    return tables


_HAS_DIGIT = re.compile(r"\d")
_DATE_CELL = re.compile(
    r"^(?:\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?"
    r"|(?:19|20)\d{2}\s*/\s*[A-Za-z]{3,}"
    r"|(?:19|20)\d{2})$")


_COL_WORDS = {
    "TYPE", "DWT", "VESSEL", "VESSEL NAME", "NAME", "LDT", "LDT / MT", "PRICE",
    "COMMENTS", "COMMENTS / BUYERS", "COMMENT", "BUYER", "BUYERS", "YEAR",
    "YEAR / BUILT", "BUILT", "TEU", "SIZE", "SIZE (TEU)", "GRADE", "INDEX",
    "INDICES", "UNITS", "CHANGE", "% CHANGE", "CONTRACT", "DESTINATION",
    "PORTS", "PORT", "COMMODITY", "COMMODITY (USD/MT)", "SEGMENT", "TANKERS",
    "BULKERS", "CONTAINERS", "MPP/ GENERAL CARGO", "GENERAL. CARGO", "OUTLOOK",
    "OUTLOOK / FUTURE SENTIMENTS", "SENTIMENTS / WEEKLY FUTURE TREND",
    "ARRIVAL", "BEACHING", "GEARED / GEARLESS", "GEARED", "GEARLESS", "NB",
    "NB CONTRACT", "NB PROMPT", "NB PROMPT DELIVERY", "DELIVERY", "YEARS",
    "YRS", "5 YEARS", "10 YEARS", "15 YEARS", "20 YEARS", "5 YRS", "10 YRS",
    "15 YRS", "CURRENCY", "CURRENCY PAIR", "PAIR", "CURRENT", "LAST WEEK",
    "LAST YEAR", "THIS WEEK", "W-O-W", "W-O-W CHANGE", "W-O-W CHANGE %",
    "Y-O-Y", "Y-O-Y CHANGE", "Y-O-Y CHANGE %", "WOW", "YOY", "WOW %",
    "CHANGE W-O-W", "CHANGE Y-O-Y", "PRICE (USD M)", "PRICE (MILLION) USD",
    "PRICE (US$/LDT)", "PRICE (US/LDT )", "SEGMENT (AVG)", "SEGMENT (AVG) (US$)",
    "CATEGORY", "ITEM", "DESCRIPTION", "REGION", "ROUTE", "SUPPLIERS",
}
_YEARISH = re.compile(r"^(19|20)\d{2}$")
_MEASURE = re.compile(r"[%$]|\d{1,3},\d{3}|\d{4,}|\.\d")
_INDEX_LABELS = {"BDI", "BCI", "BPI", "BSI", "BHSI", "BDTI", "BCTI",
                 "BHSI", "BSDI", "BDTI ", "BCTI "}


def _is_header_row(row):
    """Is this row a table's header, rather than data or a title?

    Requires every measurement-shaped cell to be absent and a strong majority of
    cells to be column vocabulary, a bare year, or empty. Measured against the
    2022 layout, where pdf-inspector emits the title line as the header and the
    real header as row 0 or row 1 of the rows.
    """
    cells = [c.strip() for c in row]
    if len(cells) < 2:
        return False
    known = 0
    for c in cells:
        if not c:
            known += 1
            continue
        u = c.upper()
        if u in _COL_WORDS or _YEARISH.match(u) or not any(ch.isdigit() for ch in u):
            known += 1
    meas = sum(1 for c in cells
               if c and parse_number(c) is not None and _MEASURE.search(c))
    return meas == 0 and known >= max(2, (len(cells) * 6) // 10)


def _header_is_data(header):
    """Is this "header" really a promoted DATA row from a split table?

    This must be STRICT. A first pass used "any cell that parses as a number",
    which wrongly demoted two legitimate headers and would have attached the
    wrong column names to real data - the exact mislabelling that is worse than
    leaving rows unlabelled. Measured false positives it produced:
        ['PORT','VLSFO (0.5%)','HSFO (3.5%)','MGO (0.1%)']          bunkers
        ['SEGMENT (AVG)','2022','2023','2024','2025','2026 YTD']     year matrix
    Both are real headers. The true positive it must keep catching is a row like
        ['ZE LENG','REEFER','7,007','09.01.2024','12.01.2024']
    so the rule requires a NAME in the first cell plus a date-shaped cell, and
    explicitly refuses year-matrix headers.
    """
    cells = [c.strip() for c in header if c.strip()]
    if len(cells) < 2:
        return False
    if not re.search(r"[A-Za-z]", cells[0]):
        return False                     # a data row starts with a name
    yearish = sum(1 for c in cells
                  if re.fullmatch(r"(19|20)\d{2}(\s*YTD)?", c, re.I))
    if yearish >= 3:
        return False                     # a year-matrix header, not a data row
    if any(_DATE_CELL.match(c) for c in cells):
        return True
    bare = sum(1 for c in cells
               if parse_number(c) is not None and not re.search(r"[A-Za-z()%]", c))
    return bare >= max(3, len(cells) - 1)


def recover_header(t):
    """Promote a real header row out of the rows, keeping what it displaced.

    MEASURED 2022 layout: pdf-inspector puts the panel TITLE in the header slot
    and the real header in row 0 or row 1, e.g.
        header ['BULKER 12 MONTHS T/C RATES AVERAGE (IN USD/DAY)']
        row 0  ['DWT','CURRENT','LAST WEEK','LAST YEAR','W-O-W CHANGE %',...]
    Nothing is discarded: a title-shaped old header moves to `title`, and a
    DATA-shaped old header is kept as the first row so no vessel is lost.
    """
    rows = t.get("rows") or []
    if len(rows) < 2:
        return False
    idx = next((i for i in range(min(3, len(rows))) if _is_header_row(rows[i])), None)
    if idx is None:
        return False
    old = list(t["header"])
    if _is_header_row(old):
        return False                     # already a real header
    if len(rows[idx]) < len(old):
        return False
    is_data = _header_is_data(old)
    pre = [old] if is_data else []
    dropped = [r for r in rows[:idx] if any(c.strip() for c in r)]
    # a DATA-shaped old header is preserved as a row, so it must not also be
    # copied into the title - that duplicated a vessel row into the metadata.
    title = "" if is_data else " ".join(c for c in old if c.strip())
    for r in dropped:
        title = (title + " " + " ".join(c for c in r if c.strip())).strip()
    t["title"] = title
    t["header"] = list(rows[idx])
    t["rows"] = pre + rows[idx + 1:]
    t["header_recovered"] = True
    return True


def fix_short_header(t):
    """The 2022 layout drops the LABEL column from the header row.

    MEASURED: header ['CURRENT','LAST WEEK','LAST YEAR','W-O-W CHANGE %',
    'Y-O-Y CHANGE %'] against rows ['BDI','2,146','2,150','3,199','-0.19',
    '-32.92'] - the header is short by exactly one cell, so CURRENT reads as the
    row label and every series would be keyed one column to the left. The label
    column is restored as an explicit name when the row labels prove what it is,
    otherwise as an empty string with `header_short` flagged - never guessed.
    """
    rows = t.get("rows") or []
    if not rows:
        return False
    widths = [len(r) for r in rows]
    modal = max(set(widths), key=widths.count)
    hdr = list(t["header"])
    if len(hdr) != modal - 1:
        return False
    if not hdr or not all(_is_header_row([c]) or c.upper() in _COL_WORDS or
                          not any(ch.isdigit() for ch in c) for c in hdr):
        return False
    labels = {r[0].strip().upper() for r in rows if r and r[0].strip()}
    name = "INDICES" if labels and labels <= _INDEX_LABELS else ""
    t["header"] = [name] + hdr
    t["header_short"] = True
    return True


def extract_tables(pdf):
    """pdf-inspector tables with the continuation-header defect repaired."""
    import pdf_inspector as pi
    out = pi.process_pdf(str(pdf))
    md = out if isinstance(out, str) else getattr(out, "markdown", None) or str(out)
    keep = []
    for t in _md_tables(md):
        flat = " ".join(c for r in t["rows"] for c in r)
        if len(_HAS_DIGIT.findall(flat)) >= 4:
            keep.append(t)
    for t in keep:
        recover_header(t)
    for t in keep:
        fix_short_header(t)
    for i, t in enumerate(keep):
        if i and _header_is_data(t["header"]):
            prev = keep[i - 1]
            # require the same column count: a continuation of the same physical
            # table cannot change shape, and this blocks cross-table accidents
            if (prev["header"] and not _header_is_data(prev["header"])
                    and len(prev["header"]) == len(t["header"])):
                t["rows"] = [t["header"]] + t["rows"]
                t["header"] = list(prev["header"])
                t["header_inherited"] = True
    return keep, md


# ---------------------------------------------------------------- verification

# Two verifier families, both using the document's OWN arithmetic so no external
# ground truth is needed. Measured need: the 2026 layout dropped the
# CURRENT/LAST WEEK panel and replaced it with THIS WEEK/LAST WEEK/WoW and a
# CURRENCY PAIR / <date> / <date> / WoW % table, so a verifier that only knows
# the 2021-2025 vocabulary reported 0/0 checked on 2026 documents.
_LEVEL_PAIRS = [
    ("CURRENT", "LAST WEEK", "W-O-W CHANGE"),
    ("CURRENT", "LAST YEAR", "Y-O-Y CHANGE"),
    ("THIS WEEK", "LAST WEEK", "WOW"),
    ("THIS WEEK", "LAST YEAR", "YOY"),
]


def _tolerance(printed_raw):
    """Tolerance from the PRINTED precision, because the publisher truncates.

    Measured: Iron Ore Lumps printed '+16.6%' where the arithmetic gives 16.67 -
    a fixed 0.05 tolerance called that a failure. One unit of the last printed
    digit is the honest bound, and it still catches a 1000x convention error by
    a factor of thousands.
    """
    s = str(printed_raw or "").strip().rstrip("%")
    if "." in s:
        dp = len(s.split(".")[-1])
        return 10.0 ** (-dp) + 1e-9
    return 1.0


def verify_change_arithmetic(tables):
    """Check printed %change cells against the values printed beside them.

    Family A: (base - compare) / compare * 100 vs a printed relative %change.
    Family B: a currency-pair row whose last column is a relative %change of the
              two preceding level columns. The publisher states it against the
              LATER date (USD/CNY: 6.80 vs 6.83 printed '+0.44%'), so both
              directions are tried and the one that holds is recorded as a
              convention rather than reported as a defect.

    A wrong number convention fails this, and so does a dropped or misaligned
    column - which is what makes it worth running on every document.
    """
    checked = passed = 0
    sign_flipped = 0
    fails = []
    for t in tables:
        hdr = [h.upper().strip() for h in t["header"]]

        def col(name):
            return hdr.index(name) if name in hdr else None

        pairs = [(col(a), col(b), col(c), "A") for a, b, c in _LEVEL_PAIRS]
        pairs = [p for p in pairs if p[0] is not None and p[1] is not None
                 and p[2] is not None]
        if not pairs and len(hdr) >= 3 and hdr[-1].endswith("%"):
            if hdr[0] in ("CURRENCY PAIR", "CURRENCY", "PAIR"):
                pairs = [(1, 2, len(hdr) - 1, "B")]
        if not pairs:
            continue
        for r in t["rows"]:
            label = (r[0][:24] if r else "")
            for bi, ci_, pi, fam in pairs:
                if max(bi, ci_, pi) >= len(r):
                    continue
                base = parse_number(r[bi])
                comp = parse_number(r[ci_])
                printed = parse_number(r[pi])
                if base is None or comp in (None, 0) or printed is None:
                    continue
                checked += 1
                tol = _tolerance(r[pi])
                fwd = (base - comp) / comp * 100.0
                rev = (comp - base) / base * 100.0
                if abs(fwd - printed) <= tol:
                    passed += 1
                elif fam == "B" and abs(rev - printed) <= tol:
                    passed += 1
                    sign_flipped += 1
                else:
                    fails.append({"row": label, "base": r[bi], "vs": r[ci_],
                                  "printed": r[pi], "computed": round(fwd, 3)})
    return {"checked": checked, "passed": passed, "sign_flipped": sign_flipped,
            "fails": fails[:12]}
