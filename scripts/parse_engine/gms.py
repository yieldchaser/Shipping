"""GMS Weekly "Ship Recycling Market Insight" (digital Word PDF, 8 pages, 2022 - 2026).

  p1      cover: date / week / volume+issue, quote of the week, highlights (left margin), commentary headline and text,
          the market-rankings table (2022-24; from 2025 it is on the Turkey page)
  p2-p5   Bangladesh, India, Pakistan, Turkey: headline, margin notes (italic or bold side captions), commentary,
          "MARKET SALES REPORTED" table or the "NO MARKET SALES REPORTED" statement
  p6      "Miscellaneous"/trivia (dropped: not market content) and IMPORTANT DATES (bank holidays, beaching tides)
  p7      port positions (Alang, Chattogram, Gadani) with total tonnage
  p8      steel plate price table (text) and four line charts (image only: noted, never transcribed), contacts (dropped)

Everything comes from the text layer. Tables are rebuilt from word geometry (columns follow the printed header or the
data cells), never estimated. Chart numbers that exist only as pixels are not transcribed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pymupdf

from scripts.parse_engine.xclusiv import fix_glyphs, render_table

PUA = re.compile("[-]")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Sept|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
MONTH_NO = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}
DATE_RE = re.compile(rf"^({MONTHS})\.?\s+(\d{{1,2}})\s*(?:[a-z]{{0,4}})\s*,?\s*(\d{{4}})", re.I)
WEEK_RE = re.compile(r"^Week\s+(\d{1,2})\b", re.I)
VOL_RE = re.compile(r"Volume\s+(\d+)\s*,?\s*Issue\s+(\d+)", re.I)
COUNTRIES = {"BANGLADESH": "Bangladesh", "INDIA": "India", "PAKISTAN": "Pakistan", "TURKEY": "Turkey",
             "TÜRKIYE": "Türkiye", "TURKIYE": "Türkiye", "CHINA": "China"}
BANNER_RE = re.compile(r"^(Page\s+\d+\s+of\s+\d+|GMS Weekly|GMS Port Reports?|Steel Plate Prices|Miscellaneous|Sustainability)\s*$", re.I)
CONTACT_RE = re.compile(r"(?i)(\bTel:|gmsinc\.net|snp@|\+\d[\d. ]{8,}|scan to download|recycling app|view the (gms )?weekly|"
                        r"summary podcast|ctrl)")
DISCLAIMER_RE = re.compile(r"(?i)^(prices indicated above|while extreme care|good faith and without|any loss incurred|"
                           r"subjective and arbitrary|material\. any review|privileged material|is prohibited|prohibited\.)")
SECTION_NAMES = {"BANK HOLIDAYS", "IMPORTANT BANK HOLIDAYS", "INDIA", "BANGLADESH", "PAKISTAN", "TURKEY", "CHINA"}
HEAD_MIN = 13.5
NUM_CELL = re.compile(r"^[\d,]+(?:\.\d+)?$")


@dataclass
class Ln:
    t: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    ital: bool
    font: str
    used: bool = False

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", fix_glyphs(PUA.sub("", t)).replace("\xa0", " ")).strip()


def collect(page: pymupdf.Page) -> list[Ln]:
    out: list[Ln] = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            ink = [s for s in l["spans"] if clean(s["text"])]
            if not ink:
                continue
            size = max((s["size"] for s in ink if re.search(r"[A-Za-z0-9]", s["text"])), default=max(s["size"] for s in ink))
            if size < 4:                                    # 1 pt stray glyphs
                continue
            text = clean("".join(s["text"] for s in l["spans"]))
            if len(text) <= 1 and not text.isdigit():                 # stray one-letter glyphs
                continue
            nb = sum(len(clean(s["text"])) for s in ink if bool(s["flags"] & 16) or "bold" in s["font"].lower())
            bold = nb >= 0.7 * sum(len(clean(s["text"])) for s in ink)          # one accented glyph may sit in a roman font
            ital = any(bool(s["flags"] & 2) or "italic" in s["font"].lower() for s in ink)
            out.append(Ln(text, *l["bbox"], round(size, 1), bold, ital, ink[0]["font"]))
    return out


def cwords(page: pymupdf.Page, clip: tuple | None = None) -> list[tuple]:
    out = []
    for w in page.get_text("words"):
        t = clean(w[4])
        if not t or (w[3] - w[1]) < 3:
            continue
        if clip and not (clip[0] <= (w[0] + w[2]) / 2 <= clip[2] and clip[1] <= (w[1] + w[3]) / 2 <= clip[3]):
            continue
        out.append((w[0], w[1], w[2], w[3], t))
    return out


def rows_of(words: list[tuple], tol: float = 3.5) -> list[list[tuple]]:
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if rows and abs(cy - sum((x[1] + x[3]) / 2 for x in rows[-1]) / len(rows[-1])) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w[0]) for r in rows]


def cells_of(row: list[tuple], gap: float = 9.0) -> list[tuple[float, float, str]]:
    out: list[list[Any]] = []
    for w in sorted(row, key=lambda w: w[0]):
        if out and w[0] - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], w[2])
            out[-1][2] += " " + w[4]
        else:
            out.append([w[0], w[2], w[4]])
    return [(a, b, t) for a, b, t in out]


def _dist(cx: float, iv: tuple[float, float]) -> float:
    return 0.0 if iv[0] <= cx <= iv[1] else min(abs(cx - iv[0]), abs(cx - iv[1]))


def assign(words: list[tuple], intervals: list[tuple[float, float]]) -> list[str]:
    cols: list[list[tuple]] = [[] for _ in intervals]
    for w in words:
        cx = (w[0] + w[2]) / 2
        k = min(range(len(intervals)), key=lambda i: (_dist(cx, intervals[i]), abs(cx - sum(intervals[i]) / 2)))
        cols[k].append(w)
    return [" ".join(w[4] for w in sorted(c, key=lambda w: (round(((w[1] + w[3]) / 2) / 4), w[0]))) for c in cols]


def data_intervals(rows: list[list[tuple]], gap: float = 9.0) -> list[tuple[float, float]] | None:
    """Column extents from the data rows (the cells of the rows that have the most common cell count)."""
    from collections import Counter
    cs = [cells_of(r, gap) for r in rows]
    if not cs:
        return None
    n = Counter(len(c) for c in cs).most_common(1)[0][0]
    base = [c for c in cs if len(c) == n]
    return [(min(c[i][0] for c in base) - 1, max(c[i][1] for c in base) + 1) for i in range(n)]


def nice_header(h: str) -> str:
    h = re.sub(r"\bV ESSEL\b", "VESSEL", h)
    if h.isupper() and len(h) > 3:
        return " ".join(w if w in ("LDT", "USD", "USD/T", "USD/LDT", "II") else w.capitalize() for w in h.split())
    return h


def join_lines(lines: list[str]) -> str:
    """Printed lines to one paragraph. The PDFs are not auto-hyphenated: a line-end hyphen after a letter is a compound
    hyphen (wait-/and-watch), so it stays and no space is added."""
    out = lines[0]
    for t in lines[1:]:
        out = out + t if re.search(r"[A-Za-z0-9]-$", out) and t[:1].isalnum() else out + " " + t
    return out


# ------------------------------------------------------------------------------------------ tables
def rank_table(page: pymupdf.Page) -> dict[str, Any] | None:
    words = cwords(page)
    rank = next((w for w in words if w[4] == "Rank"), None)
    if rank is None or not any(w[4] == "Location" and abs(w[1] - rank[1]) < 20 for w in words):
        return None
    rws = rows_of([w for w in words if w[1] > rank[1] - 4])
    data = []
    first_i = None
    for i, r in enumerate(rws):
        cs = cells_of(r)
        if len(cs) >= 3 and cs[0][2].isdigit() and int(cs[0][2]) <= 12 and any("LDT" in c[2] or NUM_CELL.match(c[2]) for c in cs[2:]):
            if first_i is None:
                first_i = i
            if data and r[0][1] - data[-1][0][0][1] > 25:
                break
            data.append((r, cs))
        elif first_i is not None:
            break
    if not data:
        return None
    data_y = data[0][0][0][1]
    x0 = min(w[0] for r, _ in data for w in r) - 8
    x1 = max(w[2] for r, _ in data for w in r) + 8
    vocab = {"Rank", "Demo", "Location", "Sentiment", "Dry", "Bulk", "Tankers", "Containers"}
    zone = [w for w in words if data_y - 70 <= w[1] < data_y - 1 and x0 - 10 <= w[0] and w[2] <= x1 + 10]
    top = min((w[1] for w in zone if w[4] in vocab), default=rank[1])
    head_words = [w for w in zone if w[1] >= top - 1]
    ncols = max(len(cs) for _, cs in data)
    base = [cs for _, cs in data if len(cs) == ncols]
    intervals = [(min(cs[i][0] for cs in base), max(cs[i][1] for cs in base)) for i in range(ncols)]
    heads = [clean(h) for h in assign(head_words, intervals)]
    rows = [assign(r, intervals) for r, _ in data]
    bottom = max(w[3] for r, _ in data for w in r)
    foot = [w for w in words if bottom < w[1] < bottom + 24 and w[4].startswith("*")]
    foot_lines = [" ".join(w[4] for w in r) for r in rows_of(
        [w for w in words if bottom < w[1] < bottom + 24 and x0 <= w[0] <= x1 + 60])] if foot else []
    box = (x0, top - 2, x1 + 60, bottom + (24 if foot else 2))
    return {"title": "GMS Market Rankings", "columns": heads, "rows": rows, "bbox": box, "footnotes": foot_lines,
            "name": "gms_rankings", "row_source": "gms_words"}


SALES_RE = re.compile(r"^(NO\s+)?MARKET SALES? REPORTED$", re.I)


def sales_block(page: pymupdf.Page, lines: list[Ln], problems: list[str]) -> dict[str, Any] | None:
    heads = [l for l in lines if SALES_RE.match(l.t) and l.size >= 10.4]
    stmts = [h for h in heads if h.t.upper().startswith("NO ")]
    theads = [h for h in heads if not h.t.upper().startswith("NO ")]
    vhdr = next((l for l in lines if l.t.upper().replace(" ", "") == "VESSELNAME"
                 and any("PRICE" in m.t.upper() and abs(m.y0 - l.y0) < 4 for m in lines)), None)
    for h in heads:
        h.used = True
    stmt = {"text": stmts[-1].t.upper(), "y": stmts[-1].y0} if stmts else None
    anchor = theads[0] if theads else vhdr
    if anchor is None:
        return ({"kind": "none", "y": stmt["y"], "text": stmt["text"]} if stmt else None)
    top = anchor.y1 - 1 if theads else anchor.y0 - 6
    y = anchor.y0 if theads else anchor.y0 - 2
    H, W = page.rect.height, page.rect.width
    clip = pymupdf.Rect(15, top, W - 15, H - 10)
    tabs = [t for t in page.find_tables(clip=clip).tables if "VESSEL" in " ".join((c or "") for c in t.extract()[0]).upper().replace(" ", "")]
    words = cwords(page)
    if tabs and (tabs[0].bbox[3] - tabs[0].bbox[1] > 170 or tabs[0].rows[0].bbox[3] - tabs[0].rows[0].bbox[1] > 22):      # not a sales table: text of the page ruled as one cell
        tabs = []
    if tabs:
        hw0 = [w for w in words if tabs[0].rows[0].bbox[1] - 1 <= (w[1] + w[3]) / 2 <= tabs[0].rows[0].bbox[3] + 1]
        if not {"TYPE", "LDT"} <= {w[4].upper() for w in hw0}:
            tabs = []
    if not tabs:
        fb = sales_fallback(words, top, y, stmts)
        if fb is None:
            if stmt:
                return {"kind": "none", "y": stmt["y"], "text": stmt["text"]}
            problems.append("info_sales_heading_without_table")       # printed heading, nothing under it in the PDF
            return {"kind": "heading_only", "y": y, "text": theads[0].t.upper() if theads else "MARKET SALES REPORTED"}
        problems.append("info_sales_table_from_words")
        fb["stmt"] = stmt
        return fb
    t = tabs[0]
    hy0, hy1 = t.rows[0].bbox[1], t.rows[0].bbox[3]
    hw = [w for w in words if hy0 - 1 <= (w[1] + w[3]) / 2 <= hy1 + 1 and t.bbox[0] - 2 <= w[0] <= t.bbox[2] + 2]
    labels = [(a, b, clean(x)) for a, b, x in cells_of(sorted(hw, key=lambda w: w[0]), gap=14)]
    ruled = []
    for c in t.rows[0].cells:                       # the ruled header cells give the true column extents
        if c is None:
            continue
        lab = [w for w in hw if c[0] - 1 <= (w[0] + w[2]) / 2 <= c[2] + 1]
        if lab:
            ruled.append((c[0], c[2], clean(" ".join(w[4] for w in sorted(lab, key=lambda w: (w[1], w[0]))))))
    if len(ruled) >= 2:
        labels = ruled
    intervals = [(a, b) for a, b, _ in labels]
    columns = [nice_header(x) for _, _, x in labels]
    rows = []
    for r in t.rows[1:]:
        bw = [w for w in words if r.bbox[1] - 1 <= (w[1] + w[3]) / 2 <= r.bbox[3] + 1 and t.bbox[0] - 2 <= w[0] <= t.bbox[2] + 2]
        if bw:
            rows.append(assign(bw, intervals))
    return {"kind": "table", "y": y, "title": "Market Sales Reported", "columns": columns, "rows": rows, "stmt": stmt,
            "bbox": tuple(t.bbox), "name": "market_sales_reported", "row_source": "gms_ruled"}


def sales_fallback(words: list[tuple], top: float, y: float, stmts: list[Ln] | None = None) -> dict[str, Any] | None:
    """Sales table without ruling (find_tables finds nothing): rows are the lines that carry an LDT figure; the other
    lines of the table (second line of a wrapped price, which is vertically centred in its cell) join the nearest one."""
    tokens = {"NO", "MARKET", "SALES", "SALE", "REPORTED"}

    def in_stmt(w: tuple) -> bool:      # the printed "NO MARKET SALES REPORTED" statement is not part of the table
        return w[4].upper() in tokens and any(l.x0 - 2 <= (w[0] + w[2]) / 2 <= l.x1 + 2 and l.y0 - 2 <= (w[1] + w[3]) / 2 <= l.y1 + 2
                                              for l in stmts or [])
    seg = [w for w in words if w[1] >= top and not in_stmt(w)]
    rws = rows_of(seg)
    hi = next((k for k, r in enumerate(rws) if any(w[4].upper().startswith("VESSEL") or w[4] == "ESSEL" for w in r)), None)
    if hi is None:
        return None
    labels = cells_of(rws[hi], gap=14)
    columns = [nice_header(clean(x)) for _, _, x in labels]
    ldt_c = next((k for k, c in enumerate(columns) if c.upper() == "LDT"), None)
    if ldt_c is None:
        return None
    body = rws[hi + 1:]
    anchors = [r for r in body if any(NUM_CELL.match(w[4]) and abs((w[0] + w[2]) / 2 - sum(labels[ldt_c][:2]) / 2) < 60 for w in r)]
    if not anchors:
        return None
    ac = [cells_of(r, gap=14) for r in anchors]
    ok = [c for c in ac if len(c) == len(labels)]
    intervals = ([(min(c[i][0] for c in ok) - 1, max(c[i][1] for c in ok) + 1) for i in range(len(labels))]
                 if ok else [(a, b) for a, b, _ in labels])
    groups: list[list[tuple]] = [[] for _ in anchors]
    ay = [sum((w[1] + w[3]) / 2 for w in r) / len(r) for r in anchors]
    for r in body:
        cy = sum((w[1] + w[3]) / 2 for w in r) / len(r)
        k = min(range(len(anchors)), key=lambda i: abs(ay[i] - cy))
        groups[k].extend(r)
    rows = [assign(g, intervals) for g in groups]
    allw = [w for g in groups for w in g] + rws[hi]
    return {"kind": "table", "y": y, "title": "Market Sales Reported", "columns": columns, "rows": rows,
            "bbox": (min(w[0] for w in allw) - 2, rws[hi][0][1] - 2, max(w[2] for w in allw) + 2, max(w[3] for w in allw) + 2),
            "name": "market_sales_reported", "row_source": "gms_words"}


PORT_TITLE_RE = re.compile(r"^(.+?)\s+-\s+Port Position as of\s+(.+)$", re.I)


def port_tables(page: pymupdf.Page, lines: list[Ln], problems: list[str]) -> list[dict[str, Any]]:
    titles = sorted((l for l in lines if PORT_TITLE_RE.match(l.t)), key=lambda l: l.y0)
    words = cwords(page)
    out = []
    for i, tl in enumerate(titles):
        tl.used = True
        end = titles[i + 1].y0 - 1 if i + 1 < len(titles) else page.rect.height
        seg = [w for w in words if tl.y1 <= w[1] < end and w[3] <= end and clean(w[4]) not in ("",)]
        rws = [r for r in rows_of(seg)]
        hi = next((k for k, r in enumerate(rws) if any(w[4] == "No." for w in r)), None)
        if hi is None:
            problems.append(f"port_header_missing:{tl.t[:20]}")
            continue
        labels = cells_of(rws[hi], gap=12)
        vrows = [r for r in rws[hi + 1:] if r[0][4].isdigit()]
        intervals = data_intervals(vrows) or [(a_, b_) for a_, b_, _ in labels]
        if len(intervals) == len(labels):
            columns = [nice_header(x) for _, _, x in labels]
        else:
            columns = [nice_header(clean(h)) for h in assign(rws[hi], intervals)]
        ldt_c = next((k for k, c in enumerate(columns) if c.upper() == "LDT"), 2)
        rows, note, total = [], None, None
        for r in rws[hi + 1:]:
            text = " ".join(w[4] for w in r)
            if re.search(r"(?i)whatsoever|liability|extreme care|relying on|information contained", text) or (
                    text.isupper() and len(text) > 35 and not r[0][4].isdigit()):
                continue
            if r[0][4].isdigit():
                rows.append(assign(r, intervals))
            elif re.match(r"(?i)^no\b.*\b(vessels?|arrivals?)\b", text):
                note = text
            elif (re.match(r"(?i)^total", text) or all(NUM_CELL.match(w[4]) or re.fullmatch(r"-+", w[4]) for w in r)
                  or (len(cells_of(r)) <= 2 and (NUM_CELL.match(r[-1][4]) or re.fullmatch(r"-+", r[-1][4])))):
                if not re.match(r"(?i)^total", text) and re.match(r"[A-Za-z]", text):
                    problems.append(f"info_port_total_label_printed_as:{text.split()[0]}")
                val = next((w[4] for w in reversed(r) if NUM_CELL.match(w[4]) or re.fullmatch(r"-+", w[4])), "")
                total = [""] * len(columns)
                total[1 if len(columns) > 1 else 0] = "Total Tonnage"
                total[ldt_c] = val
            else:
                problems.append(f"port_row_unplaced:{text[:40]}")
        ldt_i = ldt_c
        if total and re.fullmatch(r"[\d,]+(?:\.\d+)?", total[ldt_i]):
            tv = float(total[ldt_i].replace(",", ""))
            name = tl.t.split(" - ")[0]
            vals = [r[ldt_i].replace(",", "") for r in rows]
            if any(not re.fullmatch(r"\d+(?:\.\d+)?", v) for v in vals):
                problems.append(f"info_port_ldt_not_numeric:{name}")          # e.g. "TBD": the total cannot be re-added
            else:
                sm = sum(float(v) for v in vals)
                if abs(sm - tv) > 3:        # printed totals sometimes carry stale tonnage: kept as printed, listed for review
                    problems.append(f"info_port_total_differs_from_rows:{name}:{sm:g} vs printed {tv:g}")
                elif sm != tv:
                    problems.append(f"info_port_total_rounding:{name}:{sm:g} vs printed {tv:g}")
        m = PORT_TITLE_RE.match(tl.t)
        out.append({"title": f"{m.group(1).title()} - Port Position as of {m.group(2)}", "columns": columns, "rows": rows, "note": note,
                    "total": total, "ldt_i": ldt_i, "y": tl.y0,
                    "bbox": (min(w[0] for w in seg), tl.y0, max(w[2] for w in seg), max(w[3] for w in seg)),
                    "name": "port_" + m.group(1).lower().replace(" ", "_"), "row_source": "gms_words"})
    return out


STEEL_ROW_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def steel_table(page: pymupdf.Page) -> dict[str, Any] | None:
    words = cwords(page)
    rws = rows_of(words)
    data = [r for r in rws if STEEL_ROW_RE.match(r[0][4]) and len(r) >= 3]
    if not data:
        return None
    ncols = max(len(r) for r in data)
    base = [r for r in data if len(r) == ncols]
    intervals = [(min(r[i][0] for r in base) - 2, max(r[i][2] for r in base) + 2) for i in range(ncols)]
    y0 = data[0][0][1]
    x0, x1 = intervals[0][0] - 10, intervals[-1][1] + 10
    head = [w for w in words if y0 - 38 <= w[1] < y0 - 1 and x0 <= w[0] and w[2] <= x1]
    columns = [nice_header(clean(h)) for h in assign(head, intervals)]
    rows = [assign(r, intervals) for r in data]
    return {"title": "Steel Plate Prices", "columns": columns, "rows": rows, "name": "steel_plate_prices",
            "bbox": (x0, y0 - 40, x1, max(w[3] for r in data for w in r)), "row_source": "gms_words"}


def dates_blocks(page: pymupdf.Page, lines: list[Ln], problems: list[str]) -> tuple[list[dict[str, Any]], float | None, str | None]:
    """IMPORTANT DATES: returns tables, the heading's y (lines above it on this page are the trivia section), trivia title."""
    head = next((l for l in lines if re.match(r"(?i)^IMPORTANT DATES$", l.t)), None)
    if head is None:
        return [], None, None
    head.used = True
    words = [w for w in cwords(page) if w[1] > head.y1 - 1]
    sec = sorted((l for l in lines if l.y0 > head.y1 and l.bold and l.size >= 11.5 and l.t.upper() in SECTION_NAMES), key=lambda l: l.y0)
    tables = []
    for i, s in enumerate(sec):
        s.used = True
        end = sec[i + 1].y0 - 1 if i + 1 < len(sec) else page.rect.height
        seg = [w for w in words if s.y1 <= w[1] < end and not DISCLAIMER_RE.match(w[4])]
        seg = [w for w in seg if (w[3] - w[1]) > 3 and not (w[3] - w[1] < 9.5 and w[1] > page.rect.height * 0.75 and False)]
        rws = rows_of(seg)
        if not rws:
            problems.append(f"dates_empty:{s.t}")
            continue
        hrow = rws[0]
        labels = cells_of(hrow, gap=14)
        intervals = [(a, b) for a, b, _ in labels]
        columns = [nice_header(clean(x)) for _, _, x in labels]
        body = [w for r in rws[1:] for w in r if w[3] < page.rect.height * 0.86 or w[0] > 0]
        body = [w for w in body if not (w[1] > page.rect.height * 0.86)]
        cols = []
        for ci in range(len(intervals)):
            ws = [w for w in body if min(range(len(intervals)), key=lambda k: (_dist((w[0] + w[2]) / 2, intervals[k]),
                                                                            abs((w[0] + w[2]) / 2 - sum(intervals[k]) / 2))) == ci]
            cols.append("; ".join(" ".join(w[4] for w in r) for r in rows_of(ws)))
        tables.append({"title": s.t.title() if s.t.upper() != "INDIA" else "India", "columns": columns, "rows": [cols],
                       "y": s.y0, "bbox": (min(w[0] for w in seg), s.y0, max(w[2] for w in seg), max(w[3] for w in seg)),
                       "name": "dates_" + s.t.lower().replace(" ", "_"), "row_source": "gms_words"})
    if not tables:
        problems.append("dates_tables_missing")
    return tables, head.y0, None


# ------------------------------------------------------------------------------------------ prose
def body_size(lines: list[Ln]) -> float:
    from collections import Counter
    c = Counter(l.size for l in lines if len(l.t) > 55)
    return c.most_common(1)[0][0] if c else 10.0


def paragraphs(lines: list[Ln], bsize: float) -> list[tuple[float, str]]:
    """Body-size lines in y order grouped by the line pitch: a gap above 1.45 x the page's typical pitch starts a paragraph."""
    ls = sorted(lines, key=lambda l: (l.y0, l.x0))
    if not ls:
        return []
    dys = sorted(b.y0 - a.y0 for a, b in zip(ls, ls[1:]) if 8 < b.y0 - a.y0 < 22)
    pitch = dys[len(dys) // 2] if dys else 13.4
    out: list[tuple[float, list[str]]] = []
    prev = None
    for l in ls:
        if prev is None or l.y0 - prev.y0 > 1.45 * pitch or abs(l.x0 - prev.x0) > 60 and l.y0 - prev.y0 > 1.1 * pitch:
            out.append((l.y0, [l.t]))
        else:
            out[-1][1].append(l.t)
        prev = l
    return [(y, join_lines(ts)) for y, ts in out]


def junk(l: Ln, pno: int, height: float, banners: list[str]) -> bool:
    if l.y0 < 80 and BANNER_RE.match(l.t):
        if not re.match(r"(?i)^page\b", l.t):
            banners.append(l.t)
        return True
    if CONTACT_RE.search(l.t) or DISCLAIMER_RE.match(l.t):
        return True
    if l.size <= 8.2 and l.y0 > 0.7 * height and not l.t.startswith("*") and "alibri" not in l.font:
        return True
    if pno == 1 and l.y0 < 110:
        return True
    return False


@dataclass
class PageOut:
    blocks: list[tuple[float, str]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    trivia_title: str | None = None
    figures: list[str] = field(default_factory=list)


def md_table(title: str, level: int, columns: list[str], rows: list[list[str]], foot: list[str] | None = None) -> str:
    out = f"{'#' * level} {title}\n\n{render_table(columns, rows)}"
    for f in foot or []:
        out += f"\n\n{f}"
    return out


def parse_cover(page: pymupdf.Page, lines: list[Ln], po: PageOut) -> None:
    for l in lines:
        m = DATE_RE.match(l.t)
        if m and "date_text" not in po.meta and l.x0 < 120:
            mo = next((v for k, v in MONTH_NO.items() if k.startswith(m.group(1).lower()[:3])), None)
            try:
                po.meta["issue_date"] = date(int(m.group(3)), mo, int(m.group(2))).isoformat()
            except (ValueError, TypeError):
                po.problems.append("cover_date_invalid:" + l.t[:30])
            po.meta["date_text"] = l.t
            l.used = True
        elif WEEK_RE.match(l.t) and "report_week" not in po.meta and l.x0 < 120:
            po.meta["report_week"] = int(WEEK_RE.match(l.t).group(1))
            l.used = True
        elif VOL_RE.search(l.t) and "volume" not in po.meta and l.x0 < 120:
            v = VOL_RE.search(l.t)
            po.meta["volume"], po.meta["issue"] = int(v.group(1)), int(v.group(2))
            l.used = True
    for k in ("issue_date", "report_week", "volume"):
        if k not in po.meta:
            po.problems.append(f"cover_{k}_missing")
    mc = next((l for l in lines if re.match(r"(?i)^-*\s*market commentary\s*-*$", l.t)), None)
    mc_y = mc.y0 if mc else 190
    if mc:
        mc.used = True
    # quote of the week: lines right of the date block, above the commentary label
    ql = sorted((l for l in lines if not l.used and l.x0 > 190 and l.y0 < mc_y - 2 and l.size < 14), key=lambda l: (l.y0, l.x0))
    attr = None
    if ql and re.match(r"^[–—\-~]\s*\S", ql[-1].t) and not ql[-1].t.startswith(("“", '"')):
        attr = re.sub(r"^[–—\-~]\s*", "", ql[-1].t)
        ql = ql[:-1]
    if ql:
        q = join_lines([l.t for l in ql]).strip()
        q = re.sub(r"^[“\"]\s*|\s*[”\"]$", "", q)
        po.meta["quote_text"] = q
        po.meta["quote_author"] = attr
        po.meta["quote_of_the_week"] = f"{q} — {attr}" if attr else q
        for l in ql:
            l.used = True
    else:
        po.problems.append("cover_quote_missing")
    if attr:
        for l in lines:
            if l.t.endswith(attr) and not l.used and l.x0 > 190 and l.y0 < mc_y:
                l.used = True
    # highlights: left margin below the "Highlights:" label
    hl = next((l for l in lines if re.match(r"(?i)^highlights\s*:?$", l.t)), None)
    if hl:
        hl.used = True
        side = sorted((l for l in lines if not l.used and l.x1 < 215 and l.x0 < 160 and l.y0 > hl.y1), key=lambda l: l.y0)
        items: list[list[Ln]] = []
        for l in side:
            if items and l.y0 - items[-1][-1].y1 < 12:
                items[-1].append(l)
            else:
                items.append([l])
        hs = [re.sub(r"[`\s]+$", "", re.sub(r"^[^A-Za-z0-9]+", "", join_lines([x.t for x in it]))) for it in items]
        hs = [h for h in hs if h]
        for it in items:
            for x in it:
                x.used = True
        po.meta["highlights"] = hs
    else:
        po.problems.append("cover_highlights_missing")
    # headline(s): bold large lines
    hd = sorted((l for l in lines if not l.used and l.bold and l.size >= HEAD_MIN and l.x0 > 150), key=lambda l: l.y0)
    if hd:
        po.meta["headline"] = join_lines([l.t for l in hd])
        for l in hd:
            l.used = True
    else:
        po.problems.append("cover_headline_missing")


def run_page(page: pymupdf.Page, pno: int, level_shift: int = 0) -> PageOut:
    po = PageOut()
    H = page.rect.height
    banners: list[str] = []
    all_lines = collect(page)
    scan = next((l for l in all_lines if pno == 1 and re.match(r"(?i)^[^A-Za-z]*scan to download", l.t)), None)
    if scan is not None:                            # the app promo block closes the left margin of the cover
        for l in all_lines:
            if l.x1 < 215 and l.y0 >= scan.y0 - 1:
                l.used = True
    lines = [l for l in all_lines if not l.used and not junk(l, pno, H, banners)]
    po.meta["banners"] = banners
    consumed: list[tuple] = []

    # dates / trivia first (page 6)
    dt, dates_y, _ = dates_blocks(page, lines, po.problems)
    if dates_y is not None:
        big = [l for l in lines if 80 < l.y0 < dates_y - 2 and l.size >= 17]
        po.trivia_title = join_lines([l.t for l in sorted(big, key=lambda l: l.y0)]) if big else None
        for l in lines:
            if 80 < l.y0 < dates_y - 2:
                l.used = True
        po.meta["trivia_box"] = (0.0, 80.0, float(page.rect.width), dates_y - 2)
        po.blocks.append((dates_y, "# Important Dates"))
        for t in dt:
            po.blocks.append((t["y"], md_table(t["title"], 2, t["columns"], t["rows"])))
            consumed.append(t["bbox"])
        po.tables.extend(dt)
        for l in lines:
            if l.y0 > dates_y:
                l.used = True
    # ports
    pt = port_tables(page, lines, po.problems)
    if pt:
        po.blocks.append((min(t["y"] for t in pt) - 1, "# Port Reports"))
    for t in pt:
        if t["rows"]:
            rows = t["rows"] + ([t["total"]] if t["total"] else [])
            po.blocks.append((t["y"], md_table(t["title"], 2, t["columns"], rows)))
        else:
            tot = f"\n\nTotal Tonnage: {t['total'][t['ldt_i']]}" if t["total"] else ""
            po.blocks.append((t["y"], f"## {t['title']}\n\n{t['note'] or 'No vessels listed in the printed table.'}{tot}"))
            if not t["note"]:
                po.problems.append("info_port_empty_table_printed:" + t["title"][:20])
        consumed.append(t["bbox"])
    po.tables.extend(t for t in pt if t["rows"])
    if pt:
        for l in lines:
            if any(b[0] - 5 <= l.cx <= b[2] + 5 and b[1] - 5 <= l.cy <= b[3] + 5 for b in consumed):
                l.used = True
    # steel table + charts
    st = steel_table(page)
    if st:
        banner = next((b for b in banners if re.match(r"(?i)steel plate prices", b)), "Steel Plate Prices")
        po.blocks.append((st["bbox"][1] - 1, f"# {banner}"))
        po.blocks.append((st["bbox"][1], render_table(st["columns"], st["rows"])))
        po.tables.append(st)
        consumed.append(st["bbox"])
        imgs = [b for b in page.get_text("dict")["blocks"] if b["type"] == 1 and (b["bbox"][2] - b["bbox"][0]) > 150 and (b["bbox"][3] - b["bbox"][1]) > 80]
        if imgs:
            ymax = max(b["bbox"][3] for b in imgs)
            po.blocks.append((st["bbox"][3] + 1, f"> Figure: {len(imgs)} line chart image(s) of steel plate prices below the table; "
                                                  "their values exist only as pixels and are not transcribed."))
            po.figures.append(f"p{pno}:steel_charts:{len(imgs)}")
            consumed.append((0, st["bbox"][3], page.rect.width, ymax))
        for l in lines:
            if any(b[0] - 5 <= l.cx <= b[2] + 5 and b[1] - 5 <= l.cy <= b[3] + 5 for b in consumed):
                l.used = True
    # rankings (cover or Turkey page)
    rk = rank_table(page)
    if rk:
        consumed.append(rk["bbox"])
        for l in lines:
            if rk["bbox"][0] <= l.cx <= rk["bbox"][2] and rk["bbox"][1] - 2 <= l.cy <= rk["bbox"][3]:
                l.used = True
        po.tables.append(rk)
    # sales
    sb = sales_block(page, lines, po.problems)
    if sb and sb["kind"] == "table":
        po.tables.append(sb)
        consumed.append(sb["bbox"])
        for l in lines:
            if sb["bbox"][1] - 2 <= l.cy <= sb["bbox"][3] + 2 and sb["bbox"][0] - 5 <= l.cx <= sb["bbox"][2] + 5:
                l.used = True
    if pno == 1:
        parse_cover(page, lines, po)

    rest = [l for l in lines if not l.used]
    bs = body_size([l for l in rest]) if rest else 10.0
    countries = [l for l in rest if l.bold and l.size >= HEAD_MIN and l.t.upper() in COUNTRIES]
    for l in countries:
        l.used = True
        po.meta["country"] = COUNTRIES[l.t.upper()]
        po.blocks.append((l.y0 - 2, f"# {COUNTRIES[l.t.upper()]}"))
    rest = [l for l in rest if not l.used]
    body = [l for l in rest if abs(l.size - bs) <= 0.6 and len(l.t) > 0]
    long_ = [l for l in body if (l.x1 - l.x0) > 200]
    bx0 = sorted(l.x0 for l in long_)[len(long_) // 2] if long_ else 0.0
    bx1 = sorted(l.x1 for l in long_)[len(long_) // 2] if long_ else page.rect.width
    bx0 = min((l.x0 for l in long_), default=bx0)
    heads = sorted((l for l in rest if l.bold and l.size >= HEAD_MIN), key=lambda l: l.y0)
    notes = [l for l in rest if 10.6 <= l.size <= 12.4 and not l.used and (l.x1 <= bx0 + 4 or l.x0 >= bx1 - 6) and len(l.t) < 90]
    for l in notes:
        l.used = True
    cover_body_threshold = 150 if pno == 1 else 0
    body = [l for l in rest if abs(l.size - bs) <= 1.6 and not l.used and l.x0 >= cover_body_threshold - 5]
    for l in body:
        l.used = True
    # headline(s) of country / section
    hblocks: list[tuple[float, str]] = []
    cur: list[Ln] = []
    for l in heads:
        if cur and l.y0 - cur[-1].y1 < 8 and abs(l.size - cur[-1].size) < 0.6:
            cur.append(l)
        else:
            if cur:
                hblocks.append((cur[0].y0, join_lines([x.t for x in cur]), cur[0].size))
            cur = [l]
        l.used = True
    if cur:
        hblocks.append((cur[0].y0, join_lines([x.t for x in cur]), cur[0].size))
    if pno == 1 and po.meta.get("headline"):
        pass
    else:
        for y, t, sz in hblocks:
            po.blocks.append((y, f"## {t}" if sz >= 19 else f"## {t}"))
    # notes in one italic block right after the section headline
    ordered_notes = []
    grp: list[Ln] = []
    for l in sorted(notes, key=lambda l: (l.x0 > bx1 - 6, l.y0)):
        if grp and (l.y0 - grp[-1].y1 < 6) and abs(l.x0 - grp[-1].x0) < 25:
            grp.append(l)
        else:
            if grp:
                ordered_notes.append(join_lines([x.t for x in grp]))
            grp = [l]
    if grp:
        ordered_notes.append(join_lines([x.t for x in grp]))
    notes_sorted = []
    for text in ordered_notes:
        notes_sorted.append(text)
    if notes_sorted:
        ny = min(b[0] for b in po.blocks if b[1].startswith("## ")) + 0.5 if any(b[1].startswith("## ") for b in po.blocks) else 0.1
        po.blocks.append((ny, "*Margin notes: " + " | ".join(notes_sorted) + "*"))
        po.meta["margin_notes"] = notes_sorted
    for y, t in paragraphs(body, bs):
        po.blocks.append((y, t))
    if rk:
        printed = any(re.search(r"(?i)market rankings", t) for _, t, _ in hblocks)
        foot = "".join("\n\n" + f for f in rk["footnotes"])
        tbl = (render_table(rk["columns"], rk["rows"]) + foot) if printed else md_table(rk["title"], 3, rk["columns"], rk["rows"], rk["footnotes"])
        po.blocks.append((rk["bbox"][1], tbl))
    if sb:
        if sb["kind"] == "table":
            po.blocks.append((sb["y"], md_table(sb["title"], 3, sb["columns"], sb["rows"])))
            if sb.get("stmt"):
                po.blocks.append((sb["stmt"]["y"], f"**{sb['stmt']['text']}**"))
                po.problems.append("info_sales_table_and_no_sales_statement_both_printed")
        elif sb["kind"] == "heading_only":
            po.blocks.append((sb["y"], f"**{sb['text']}** (printed as a heading with no table beneath it in the source PDF)"))
        else:
            po.blocks.append((sb["y"], f"**{sb['text']}**"))
    leftover = [l for l in lines if not l.used]
    for l in leftover:
        po.problems.append(f"p{pno}_unplaced:{l.t[:50]}")
    po.blocks.sort(key=lambda b: b[0])
    return po


# ------------------------------------------------------------------------------------------ document
def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[‘’'`]", "", text.lower())).strip("-")
    return s[:60].strip("-")


def run(plan: Any, doc: pymupdf.Document, profile: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    md: list[str] = []
    tables: list[dict[str, Any]] = []
    cover = None
    trivia_boxes: list[dict[str, Any]] = []
    trivia_titles: list[str] = []
    figures: list[str] = []
    for pno in plan.pages:
        po = run_page(doc[pno - 1], pno)
        problems.extend(po.problems)
        figures.extend(po.figures)
        for t in po.tables:
            t["page"] = pno
            t.setdefault("title", t.get("name"))
            t.update({"empty": not t["rows"], "unassigned_words": 0, "row_meta": [], "column_bounds": [],
                      "source_columns": t["columns"], "en_bloc_rows": [], "bbox": [round(float(v), 2) for v in t["bbox"]]})
            t.pop("footnotes", None)
            t.pop("y", None)
            t.pop("note", None)
            t.pop("total", None)
            t.pop("ldt_i", None)
        tables.extend(po.tables)
        if po.trivia_title is not None:
            trivia_titles.append(po.trivia_title)
        if "trivia_box" in po.meta:
            trivia_boxes.append({"page": pno, "bbox": po.meta["trivia_box"]})
        if pno == 1:
            cover = po
            m = po.meta
            head = m.get("headline", "")
            hl = m.get("highlights") or []
            intro = ("GMS Weekly - Ship Recycling Market Insight - Week {w}, Volume {v}, Issue {i} - {d}".format(
                w=m.get("report_week", "?"), v=m.get("volume", "?"), i=m.get("issue", "?"), d=m.get("date_text", "?")))
            md.append(intro)
            if m.get("quote_of_the_week"):
                md.append(f"**Quote of the week:** “{m['quote_text']}”" + (f" — {m['quote_author']}" if m.get("quote_author") else ""))
            if hl:
                md.append("# Highlights\n\n" + "\n".join(f"- {h}" for h in hl))
            md.append("# Market Commentary" + (f"\n\n## {head}" if head else ""))
        md.append("\n\n".join(t for _, t in po.blocks))
    if cover is None:
        problems.append("cover_not_parsed")
        cover = PageOut()
    m = cover.meta
    iso = m.get("issue_date")
    headline = m.get("headline") or ""
    week = m.get("report_week")
    title = f"GMS Week {week} – {headline}" if week and headline else (f"GMS Week {week}" if week else "GMS Weekly")
    stem = None
    if iso:
        stem = f"gms_{iso}_week-{int(week):02d}_{slug(headline)}" if week and headline else f"gms_{iso}"
        stem = stem.rstrip("_-")
    if iso and plan.issue_date and iso != plan.issue_date:
        problems.append(f"printed_date_differs_from_plan:{iso}!={plan.issue_date}")
    if iso:
        try:
            delta = (date.fromisoformat(plan.pdf.name[:10]) - date.fromisoformat(iso)).days
            if not 0 <= delta <= 6:
                problems.append(f"printed_date_vs_file_date:{iso} vs {plan.pdf.name[:10]}")
        except ValueError:
            pass
    return {
        "markdown": "\n\n".join(x for x in md if x.strip()), "tables": tables, "parser": "pymupdf_words + gms_template",
        "api": "local", "tier": None, "credits_used": 0, "parsed_at": None, "problems": problems,
        "stem": stem,
        "meta": {k: v for k, v in {"title": title, "publisher": profile.get("publisher"), "issue_date": iso,
                                    "report_week": week, "volume": m.get("volume"), "issue": m.get("issue"),
                                    "quote_of_the_week": m.get("quote_of_the_week"),
                                    "year": int(iso[:4]) if iso else None}.items() if v is not None},
        "trivia": trivia_titles, "trivia_boxes": trivia_boxes, "figures": figures,
    }


def trivia_boxes_for(page: pymupdf.Page) -> list[tuple[float, float, float, float]]:
    """The miscellany block above IMPORTANT DATES (dropped from the output, so excluded from text recall)."""
    lines = collect(page)
    head = next((l for l in lines if re.match(r"(?i)^IMPORTANT DATES$", l.t)), None)
    if head is None:
        return []
    return [(0.0, 80.0, float(page.rect.width), head.y0 - 2)]


# ------------------------------------------------------------------------------------------ 2021 HSN article HTML
HTML_TITLE_RE = re.compile(r"^GMS\s+Week\s+(\d{1,2})\s*\W\s*(.+)$", re.I)


def html_issue(path: Any) -> dict[str, Any]:
    """The Hellenic Shipping News article of a 2021 GMS issue: commentary paragraphs only. The rankings table is a linked
    image; nothing is read from it. The issue date is the article's publication date (the GMS cover date is not in the
    article), which is also the Monday date the legacy extractions used."""
    from html import unescape
    from pathlib import Path as _P

    text = _P(path).read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    title = clean(unescape(m.group(1))) if m else ""
    d = re.search(r'name="archive-date"\s+content="(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"', text)
    iso = None
    if d:
        mo = next((v for k, v in MONTH_NO.items() if k.startswith(d.group(2).lower()[:3])), None)
        try:
            iso = date(int(d.group(3)), mo, int(d.group(1))).isoformat()
        except (ValueError, TypeError):
            iso = None
    body = text[text.index("<body>"):] if "<body>" in text else text
    section = re.search(r"<section>(.*?)</section>", body, re.S)
    paras = []
    for pm in re.finditer(r"<p>(.*?)</p>", section.group(1) if section else "", re.S):
        raw = pm.group(1)
        if "Linked asset" in raw or re.match(r"^\s*Source:", re.sub(r"<[^>]+>", "", raw)):
            continue
        t = clean(unescape(re.sub(r"<[^>]+>", " ", raw)))
        if t:
            paras.append(t)
    assets = re.findall(r'<a href="(assets/[^"]+\.(?:jpg|jpeg|png))"', section.group(1) if section else "", re.I)
    tm = HTML_TITLE_RE.match(title)
    return {"title_raw": title, "week": int(tm.group(1)) if tm else None, "headline": tm.group(2).strip() if tm else None,
            "issue_date": iso, "paras": paras, "assets": assets}


def run_html(path: Any, profile: dict[str, Any]) -> dict[str, Any]:
    h = html_issue(path)
    problems: list[str] = []
    for k in ("issue_date", "week", "headline"):
        if not h[k]:
            problems.append(f"html_{k}_missing")
    if not h["paras"]:
        problems.append("html_no_paragraphs")
    md = [f"GMS Weekly - Ship Recycling Market Insight - Week {h['week']} - {h['issue_date']} "
          "(Hellenic Shipping News article of the GMS weekly)"]
    md.append("# Market Commentary" + (f"\n\n## {h['headline']}" if h["headline"] else ""))
    md.append("\n\n".join(h["paras"]))
    if h["assets"]:
        md.append("> Figure: the GMS market rankings / pricing table of this issue is published only as an image "
                  "(linked asset in the article); its numbers are not in a text layer and are not transcribed.")
    iso = h["issue_date"]
    stem = f"gms_{iso}_week-{h['week']:02d}_{slug(h['headline'])}" if iso and h["week"] and h["headline"] else None
    title = f"GMS Week {h['week']} – {h['headline']}" if h["week"] and h["headline"] else None
    return {"markdown": "\n\n".join(x for x in md if x.strip()), "stem": stem, "problems": problems,
            "meta": {k: v for k, v in {"title": title, "publisher": profile.get("publisher"), "issue_date": iso,
                                        "report_week": h["week"], "year": int(iso[:4]) if iso else None,
                                        "issue_date_source": "hsn_article_publication_date"}.items() if v is not None},
            "paras": h["paras"], "figures": h["assets"]}
