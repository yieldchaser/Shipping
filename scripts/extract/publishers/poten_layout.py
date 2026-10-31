"""poten_layout.py - layout-aware Markdown renderer for Poten & Partners "Tanker Opinion" PDFs.

Local only (PyMuPDF), no network, no paid APIs. Replaces the body of the MDs written by run_poten.py:

  - chart text (axis ticks, legends, region codes, data labels) is never prose and never a heading; each chart
    becomes one caption line `*Chart: <printed title>*`, a table of its printed data labels ONLY when they pair
    unambiguously with printed category labels, and the printed `Source:` line;
  - printed tables (word-aligned grids, >= 3 rows sharing >= 3 columns) become GitHub tables with the printed
    (multi-line, merged per column) header;
  - headings are bold / larger lines outside charts and tables that are followed by body text;
  - running headers / footers / disclaimers are dropped;
  - 2-column pages are read column by column.

Chart regions come from embedded images and from clusters of vector drawings (page.get_drawings), plus text-only
evidence (arithmetic runs of tick labels, month-year tick rows). Values are never estimated from geometry.

    python scripts/extract/publishers/poten_layout.py --out <dir> [--year 2007] [--limit N] [--workers 4]

Writes <dir>/<year>/<same stem>.md: the existing MD's frontmatter block byte-identical, then the re-rendered body.
"""
from __future__ import annotations

import argparse
import collections
import re
import statistics
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
MAIN_ROOT = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT
MD_ROOT = ROOT / "data" / "extracted" / "md" / "poten"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MON3 = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
HYPHENS = "-‐‑"
SENT_END = (".", "!", "?", ":", '"', "”", "'", "’", ")", "%")

RUNNING = [
    re.compile(r"poten\s*&\s*partners.{0,12}(?:athens|london|new york)", re.I),
    re.compile(r"new york.{0,6}london.{0,6}(?:perth|athens|singapore)", re.I),
    re.compile(r"^houston\s*/\s*new york", re.I),
    re.compile(r"^www\.poten\.com$", re.I),
    re.compile(r"^email:\s*tankerresearch@", re.I),
    re.compile(r"^(?:email:\s*)?tankerresearch@poten\.com$", re.I),
    re.compile(r"^page\s+\d+(?:\s+of\s+\d+)?$", re.I),
    re.compile(r"^\d{1,2}\s+May\s+2013$"),
    re.compile(r"^wafwofleet", re.I),
    re.compile(r"^bi or no de\??$", re.I),
]
DISCLAIMER = re.compile(
    r"(?:tanker\s+(?:market\s+)?opinions?\s+(?:are|is)\s+published|"
    r"to\s+receive\s+this\s+(?:via\s+)?email|research\s+products|contact\s+our\s+tanker\s+brokers|"
    r"tankerresearch@poten\.com|please\s+visit\s+our\s+website)", re.I)
DATE_LINE = re.compile(rf"^(?:{MONTHS})\d{{1,2}}(?:,?\d{{4}})?$|^\d{{1,2}}(?:{MONTHS})\d{{4}}$|^(?:{MON3})\.?\d{{1,2}},?\d{{4}}$",
                       re.I)
BRAND = "potentankeropinion"
TICK = re.compile(
    rf"^(?:[$€£]?\(?-?[\d.,]+\)?\s?(?:%|[kKmMbB]n?)?|(?:{MON3})[a-z]*[\-‐‑–' ]?\d{{2,4}}|"
    rf"\d{{1,2}}[\-/]\d{{1,2}}[\-/]\d{{2,4}}|[1-4]Q\s?'?\d{{2,4}}|Q[1-4]\s?'?\d{{2,4}}|\d{{4}}[eEfF]?|\d{{1,2}}/\d{{1,2}})$")
VALUE = re.compile(r"^[$€£]?-?\d[\d,]*(?:\.\d+)?\s?(?:%|[kKmMbB]n?)?$")
FIG_LINE = re.compile(r"^(?:Fig\.?|Figure|Chart|Exhibit|Graph)\s*\d+\b", re.I)
SRC_LINE = re.compile(r"^(?:sources?|notes?)\s*[:\-]", re.I)
BULLET = re.compile(r"^[•·●▪■‣◦]\s*")


# ----------------------------------------------------------------------------------------------------------------
# text lines
# ----------------------------------------------------------------------------------------------------------------
class Line:
    __slots__ = ("text", "x0", "y0", "x1", "y1", "size", "bold", "italic", "font", "rot", "cells", "block",
                 "drop", "claim", "used")

    def __init__(self):
        self.drop = None      # reason when dropped (running / disclaimer / title / date)
        self.claim = None     # chart region index when the line is chart text
        self.used = False     # consumed by a table

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0


def _clean_char(c: str) -> str:
    if c in "       ":
        return " "
    if c in ("­", "​", "‌", "‍", "﻿", "�"):
        return ""
    if c == "" or c == "" or c == "":
        return "•"
    if c == "ﬁ":
        return "fi"
    if c == "ﬂ":
        return "fl"
    cat = unicodedata.category(c)
    if cat in ("Cc", "Cs", "Co"):
        return " " if c in "\t\n\r" else ""
    return c


def extract_lines(page) -> list[Line]:
    out: list[Line] = []
    d = page.get_text("rawdict")
    for bi, b in enumerate(d["blocks"]):
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            chars = []
            for s in l["spans"]:
                fn = s["font"]
                low = fn.lower()
                bold = any(k in low for k in ("bold", "heavy", "black", "semibold", "demi")) or bool(s["flags"] & 16)
                ital = any(k in low for k in ("italic", "oblique")) or bool(s["flags"] & 2)
                for ch in s["chars"]:
                    c = _clean_char(ch["c"])
                    if c == "":
                        continue
                    for cc in c:
                        chars.append((cc, ch["bbox"], s["size"], bold, ital, fn))
            if not chars or not any(c[0] != " " for c in chars):
                continue
            ln = Line()
            ln.block = bi
            dx, dy = l["dir"]
            ln.rot = abs(dx) < 0.99
            vis = [c for c in chars if c[0] != " "]
            if ln.rot:
                ln.x0, ln.y0, ln.x1, ln.y1 = l["bbox"]
            else:
                ln.x0 = min(c[1][0] for c in vis)
                ln.y0 = min(c[1][1] for c in vis)
                ln.x1 = max(c[1][2] for c in vis)
                ln.y1 = max(c[1][3] for c in vis)
            ln.size = sum(c[2] for c in vis) / len(vis)
            ln.bold = sum(1 for c in vis if c[3]) / len(vis) >= 0.8
            ln.italic = sum(1 for c in vis if c[4]) / len(vis) >= 0.8
            ln.font = collections.Counter(c[5] for c in vis).most_common(1)[0][0]
            # text and cells (a gap wider than 1.5 em between two printed characters starts a new cell)
            text = []
            cells = []
            cur = []
            prev_x1 = None
            thr = 1.5 * ln.size
            for c in chars:
                if c[0] == " ":
                    if cur:
                        cur.append(" ")
                    text.append(" ")
                    continue
                if prev_x1 is not None and not ln.rot and c[1][0] - prev_x1 > thr and cur:
                    cells.append(["".join(cur).strip(), cur_x0, prev_x1])
                    cur = []
                if not cur:
                    cur_x0 = c[1][0]
                cur.append(c[0])
                prev_x1 = c[1][2]
                text.append(c[0])
            if cur:
                cells.append(["".join(cur).strip(), cur_x0, prev_x1])
            ln.text = re.sub(r"\s+", " ", "".join(text)).strip()
            ln.cells = [(re.sub(r"\s+", " ", t).strip(), a, bb) for t, a, bb in cells if t.strip()]
            if ln.text:
                out.append(ln)
    return out


def norm_letters(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ----------------------------------------------------------------------------------------------------------------
# lexicon for de-hyphenation (words that occur un-hyphenated in the already rendered corpus)
# ----------------------------------------------------------------------------------------------------------------
_LEX: set[str] | None = None
LAST_DEBUG: list = []   # per text line of the last render(): (page, text, drop, chart_region, in_table, rotated, size)


def lexicon() -> set[str]:
    global _LEX
    if _LEX is None:
        cnt = collections.Counter()
        for md in MD_ROOT.rglob("*.md"):
            try:
                txt = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            cnt.update(w.lower() for w in re.findall(r"[A-Za-z]{4,}", txt))
        _LEX = {w for w, n in cnt.items() if n >= 2}
    return _LEX


def join_lines(texts: list[str]) -> str:
    """Join the lines of one paragraph: de-hyphenate soft line-end hyphens, keep hard hyphens as printed."""
    acc = texts[0]
    for nxt in texts[1:]:
        if acc and acc[-1] in HYPHENS and len(acc) > 1:
            m = re.match(r"([A-Za-zÀ-ɏ]+)", nxt)
            stem = re.search(r"([A-Za-zÀ-ɏ]+)$", acc[:-1])
            if nxt[:1].islower() and m and stem:
                joined = (stem.group(1) + m.group(1)).lower()
                if joined in lexicon():
                    acc = acc[:-1] + nxt
                else:
                    acc = acc + nxt
                continue
            if acc[-2] == " ":
                acc = acc + " " + nxt
            else:
                acc = acc + nxt
            continue
        acc = acc + " " + nxt
    return re.sub(r" {2,}", " ", acc).strip()


# ----------------------------------------------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------------------------------------------
def inter_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def cluster(rects, gap):
    n = len(rects)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cell = 60.0
    grid = collections.defaultdict(list)
    g = gap / 2
    for i, r in enumerate(rects):
        x0, y0, x1, y1 = r[0] - g, r[1] - g, r[2] + g, r[3] + g
        for ix in range(int(x0 // cell), int(x1 // cell) + 1):
            for iy in range(int(y0 // cell), int(y1 // cell) + 1):
                for j in grid[(ix, iy)]:
                    q = rects[j]
                    if not (x1 < q[0] - g or q[2] + g < x0 or y1 < q[1] - g or q[3] + g < y0):
                        a, b = find(i), find(j)
                        if a != b:
                            parent[a] = b
                grid[(ix, iy)].append(i)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


# ----------------------------------------------------------------------------------------------------------------
# tables
# ----------------------------------------------------------------------------------------------------------------
class Row:
    __slots__ = ("items", "yc", "y0", "y1")

    def __init__(self, it):
        self.items = [it]
        self.yc = it["yc"]
        self.y0 = it["y0"]
        self.y1 = it["y1"]

    def add(self, it):
        self.items.append(it)
        self.yc = sum(i["yc"] for i in self.items) / len(self.items)
        self.y0 = min(self.y0, it["y0"])
        self.y1 = max(self.y1, it["y1"])


def _columns(rows):
    ivs = sorted((it["x0"], it["x1"]) for r in rows for it in r.items)
    cols = []
    for a, b in ivs:
        if cols and a <= cols[-1][1] + 1.0:
            cols[-1][1] = max(cols[-1][1], b)
        else:
            cols.append([a, b])
    return cols


def _col_of(cols, x0, x1):
    best, bo = None, 0.0
    for k, (a, b) in enumerate(cols):
        o = min(b, x1) - max(a, x0)
        if o > bo:
            best, bo = k, o
    if best is None:
        cx = (x0 + x1) / 2
        best = min(range(len(cols)), key=lambda k: abs((cols[k][0] + cols[k][1]) / 2 - cx))
    return best


def find_tables(lines: list[Line], body: float, mc: int = 3, subset=None):
    items = []
    for i, l in enumerate(lines):
        if l.rot or l.drop or l.claim is not None or (subset is not None and i not in subset):
            continue
        for ci, (t, a, b) in enumerate(l.cells):
            if len(t) > 50 or len(t.split()) >= 8 or SRC_LINE.match(t):
                continue   # prose / source lines are not table cells
            items.append({"li": i, "ci": ci, "x0": a, "x1": b, "y0": l.y0, "y1": l.y1, "yc": l.cy,
                          "t": t, "size": l.size, "bold": l.bold, "nc": len(l.cells)})
    items.sort(key=lambda it: (it["yc"], it["x0"]))
    rows: list[Row] = []
    for it in items:
        for r in reversed(rows[-6:]):
            if abs(it["yc"] - r.yc) <= max(2.0, 0.45 * it["size"]) and abs(it["size"] - r.items[0]["size"]) <= 0.6:
                r.add(it)
                break
        else:
            rows.append(Row(it))
    rows.sort(key=lambda r: r.yc)
    for r in rows:
        r.items.sort(key=lambda it: it["x0"])
    tables = []
    i = 0
    n = len(rows)
    while i < n:
        if len(rows[i].items) < mc:
            i += 1
            continue
        size = rows[i].items[0]["size"]
        j = i
        last_good = i
        jm = i      # last row of the run's own type size
        sx0 = min(it["x0"] for it in rows[i].items)
        sx1 = max(it["x1"] for it in rows[i].items)
        while j + 1 < n:
            nxt = rows[j + 1]
            if abs(nxt.items[0]["size"] - size) > 0.6:
                if nxt.yc - rows[jm].yc > 5 * size:
                    break
                j += 1      # a line of another type size (neighbouring column's text) is not part of the table
                continue
            gap = nxt.yc - rows[jm].yc
            if gap > 2.6 * size:
                break
            if len(nxt.items) >= mc:
                last_good = j + 1
            else:
                ok = all(it["x0"] >= sx0 - 15 and it["x1"] <= sx1 + 15 and len(it["t"]) <= 40 for it in nxt.items)
                if not ok:
                    break
            sx0 = min(sx0, min(it["x0"] for it in nxt.items))
            sx1 = max(sx1, max(it["x1"] for it in nxt.items))
            j += 1
            jm = j
        run = [r for r in rows[i:last_good + 1] if abs(r.items[0]["size"] - size) <= 0.6]
        start = i
        i = last_good + 1
        wide = [r for r in run if len(r.items) >= mc]
        if len(wide) < (3 if mc >= 3 else 4):
            continue
        cols = _columns(wide)
        hits = collections.Counter()
        for r in wide:
            for k in {_col_of(cols, it["x0"], it["x1"]) for it in r.items}:
                hits[k] += 1
        good = {k for k, v in hits.items() if v >= 3}
        if len(good) < mc:
            continue
        ok_rows = 0
        for r in wide:
            if len({_col_of(cols, it["x0"], it["x1"]) for it in r.items} & good) >= mc:
                ok_rows += 1
        if ok_rows < (3 if mc >= 3 else 4):
            continue
        # extend upward with header rows that have fewer than 3 cells
        k = start - 1
        while k >= 0:
            prv = rows[k]
            if abs(prv.items[0]["size"] - size) > 0.6:
                break
            gaps = [run[m + 1].yc - run[m].yc for m in range(len(run) - 1)]
            mg = statistics.median(gaps) if gaps else 12
            if run[0].yc - prv.yc <= 1.15 * mg and all(
                    it["x0"] >= cols[0][0] - 15 and it["x1"] <= cols[-1][1] + 15 and len(it["t"]) <= 40
                    for it in prv.items) and prv.items[0]["bold"] == run[0].items[0]["bold"]:
                run.insert(0, prv)
                k -= 1
            else:
                break
        tables.append(_build_table(run, rows, mc))
    return [t for t in tables if t]


def _drop_sparse_edges(run: list[Row], mc: int = 3) -> list[Row]:
    """Drop first / last columns that are filled in almost no row and only by single-cell lines (the text of a
    neighbouring column that happens to share the table's baselines)."""
    for _ in range(2):
        data = [r for r in run if len(r.items) >= mc]
        cols = _columns(data)
        if len(cols) <= mc:
            break
        cnt = collections.Counter()
        for r in run:
            for it in r.items:
                cnt[_col_of(cols, it["x0"], it["x1"])] += 1
        changed = False
        for edge in (0, len(cols) - 1):
            if cnt[edge] <= max(1, 0.12 * len(run)):
                victims = [(r, it) for r in run for it in r.items
                           if _col_of(cols, it["x0"], it["x1"]) == edge and it["nc"] == 1]
                if len(victims) == cnt[edge]:
                    for r, it in victims:
                        r.items.remove(it)
                    run = [r for r in run if r.items]
                    changed = True
                    break
        if not changed:
            break
    return run


def _build_table(run: list[Row], _rows, mc: int = 3):
    run = _drop_sparse_edges(run, mc)
    if len([r for r in run if len(r.items) >= mc]) < (3 if mc >= 3 else 4):
        return None
    data_rows = [r for r in run if len(r.items) >= mc]
    cols = _columns(data_rows)
    # merge columns that are only separated by <= 1pt after the union (already merged) - keep as is
    gaps = [run[m + 1].yc - run[m].yc for m in range(len(run) - 1)]
    mg = statistics.median(gaps) if gaps else 12.0
    # header band
    band = 1
    firstbold = all(it["bold"] for it in run[0].items)

    def isval(t):
        return bool(VALUE.match(t)) and not re.fullmatch(r"(?:19|20)\d\d", t)   # a bare year heads columns

    def numeric_row(r):
        return sum(1 for it in r.items if isval(it["t"])) >= 0.5 * len(r.items)

    def mixed_row(r):
        v = sum(1 for it in r.items if isval(it["t"]))
        return 0 < v < len(r.items)

    nb = 0
    while nb < len(run) and not numeric_row(run[nb]):
        nb += 1
    bb_ = 0
    if firstbold and any(not all(it["bold"] for it in r.items) for r in run[1:]):
        while bb_ < len(run) and all(it["bold"] for it in run[bb_].items):
            bb_ += 1
    if nb == 0 and mixed_row(run[0]) and not firstbold:
        band = 0           # no printed header: the first row is already data (label | value)
    elif 1 <= max(nb, bb_) < len(run) - 1:
        band = max(nb, bb_)     # header = the leading rows that carry no values / are set in bold
    else:
        band = 1
        while band < len(run) and run[band].yc - run[band - 1].yc < 0.8 * mg:
            band += 1
    band = max(0 if band == 0 else 1, min(band, len(run) - 1))
    ncol = len(cols)

    def place(rowlist):
        grid = [[] for _ in range(ncol)]
        for r in rowlist:
            for it in r.items:
                overl = [k for k, (a, b) in enumerate(cols) if min(b, it["x1"]) - max(a, it["x0"]) > 0.3 * (it["x1"] - it["x0"])]
                k = overl[0] if overl else _col_of(cols, it["x0"], it["x1"])
                grid[k].append(it["t"])
        return [" ".join(c) for c in grid]

    header = place(run[:band]) if band else [""] * ncol
    body_rows = [place([r]) for r in run[band:]]
    used = {(it["li"]) for r in run for it in r.items}
    x0 = min(it["x0"] for r in run for it in r.items)
    x1 = max(it["x1"] for r in run for it in r.items)
    y0 = min(r.y0 for r in run)
    y1 = max(r.y1 for r in run)
    esc = lambda s: s.replace("|", "\\|")
    md = ["| " + " | ".join(esc(c) for c in header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for r in body_rows:
        md.append("| " + " | ".join(esc(c) for c in r) + " |")
    return {"bbox": (x0, y0, x1, y1), "md": "\n".join(md), "lines": used, "ncol": ncol, "nrows": len(run)}


# ----------------------------------------------------------------------------------------------------------------
# charts
# ----------------------------------------------------------------------------------------------------------------
def is_tick(t: str) -> bool:
    return bool(TICK.match(t.strip()))


def rule_only(drawings) -> bool:
    """True when the cluster is only axis-aligned rules and rectangles (a table frame, not a plot)."""
    for d in drawings:
        for it in d["items"]:
            if it[0] in ("c", "qu"):
                return False
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.x - q.x) > 1.0 and abs(p.y - q.y) > 1.0:
                    return False
    return True


def find_regions(page, lines, pw, ph, title_top, body=10.0, table_boxes=()):
    """Chart regions as dicts {bbox, img, drawings}. Header / footer images and logos are not charts."""
    hdr = []
    shapes = []
    for info in page.get_image_info():
        x0, y0, x1, y1 = info["bbox"]
        w, h = x1 - x0, y1 - y0
        if w * h >= 0.8 * pw * ph:
            continue
        if y1 <= 132 or y0 >= ph - 70:
            hdr.append((x0, y0, x1, y1))
            continue
        if title_top is not None and y1 <= title_top + 3 and y0 < 220:
            hdr.append((x0, y0, x1, y1))
            continue
        if w < 30 or h < 20:
            continue
        prose = [l for l in lines if not l.rot and not l.drop and len(l.text) >= 45 and l.size >= body - 0.7
                 and x0 - 2 <= l.cx <= x1 + 2 and y0 - 2 <= l.cy <= y1 + 2]
        strip_text = h < 45 and any(not l.rot and not l.drop and x0 - 2 <= l.cx <= x1 + 2 and y0 - 2 <= l.cy <= y1 + 2
                                    for l in lines)
        if len(prose) >= 1 or strip_text:
            continue   # an image behind a block of body text (page assembled from picture tiles), not a chart
        shapes.append({"bbox": (x0, y0, x1, y1), "img": True, "dr": None})
    for d in page.get_drawings():
        r = d["rect"]
        x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
        if (x1 - x0) >= 0.9 * pw and (y1 - y0) >= 0.9 * ph:
            continue
        if (x1 - x0) >= 0.6 * pw and (y1 - y0) <= 1.5:
            continue
        if (x1 - x0) * (y1 - y0) >= 0.12 * pw * ph and not d.get("fill") and len(d["items"]) <= 2:
            continue   # outline of a whole page column / panel, not part of a plot
        fill = d.get("fill")
        if fill and min(fill) >= 0.97 and not d.get("color"):
            continue   # white background panel behind a picture / text block
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(h[0] <= cx <= h[2] and h[1] <= cy <= h[3] for h in hdr):
            continue
        shapes.append({"bbox": (x0, y0, x1, y1), "img": False, "dr": d})
    if not shapes:
        return [], hdr
    # stage 1: vector drawings cluster among themselves; a rule-only cluster on a printed table is the table's frame,
    # a handful of strokes (a box round a heading) is decoration
    imgs = [s for s in shapes if s["img"]]
    dshapes = [s for s in shapes if not s["img"]]
    units = []   # (bbox, img, drawings, strong)
    for s in imgs:
        units.append((s["bbox"], True, [], True))
    if dshapes:
        for g in cluster([s["bbox"] for s in dshapes], 10.0):
            drs = [dshapes[k]["dr"] for k in g]
            bb = dshapes[g[0]]["bbox"]
            for k in g[1:]:
                bb = union(bb, dshapes[k]["bbox"])
            nitems = sum(len(d["items"]) for d in drs)
            strong = bb[2] - bb[0] >= 40 and bb[3] - bb[1] >= 30 and (len(drs) >= 4 or nitems >= 8)
            if strong and rule_only(drs) and any(
                    inter_area(bb, t) >= 0.4 * area(bb) or inter_area(bb, t) >= 0.4 * area(t) for t in table_boxes):
                continue
            units.append((bb, False, drs, strong))
    # stage 2: pictures and the remaining vector clusters merge when they touch
    regions = []
    for g in cluster([u[0] for u in units], 10.0):
        members = [units[k] for k in g]
        if not any(m[3] for m in members):
            continue
        bb = members[0][0]
        for m in members[1:]:
            bb = union(bb, m[0])
        has_img = any(m[1] for m in members)
        drs = [d for m in members for d in m[2]]
        if bb[2] - bb[0] < 40 or bb[3] - bb[1] < 30:
            continue
        regions.append({"bbox": bb, "img": has_img, "dr": drs, "ruleonly": (not has_img) and rule_only(drs)})
    return regions, hdr


def tick_regions(lines, pw, existing, skip=()):
    """Text-only chart evidence: rows / columns of >= 4 tick labels in arithmetic progression or month-year labels."""
    cand = [l for i, l in enumerate(lines) if i not in skip and not l.drop and l.claim is None and not l.rot
            and is_tick(l.text) and len(l.text) <= 9]
    found = []
    # rows
    byrow = collections.defaultdict(list)
    for l in cand:
        byrow[round(l.cy / 3)].append(l)
    for v in byrow.values():
        v.sort(key=lambda l: l.x0)
        if len(v) >= 4 and _progression(v):
            found.append(v)
    bycol = collections.defaultdict(list)
    for l in cand:
        bycol[round(l.x1 / 4)].append(l)
    for v in bycol.values():
        v.sort(key=lambda l: l.y0)
        if len(v) >= 4 and _progression(v):
            found.append(v)
    out = []
    for v in found:
        bb = (min(l.x0 for l in v), min(l.y0 for l in v), max(l.x1 for l in v), max(l.y1 for l in v))
        if any(inter_area(bb, e["bbox"]) > 0 or _near(bb, e["bbox"], 50) for e in existing):
            continue
        out.append(bb)
    merged = []
    for bb in out:
        for k, m in enumerate(merged):
            if _near(bb, m, 60):
                merged[k] = union(bb, m)
                break
        else:
            merged.append(bb)
    return [{"bbox": (b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4), "img": False, "dr": [], "ruleonly": False,
             "text_only": True} for b in merged]


def _near(a, b, d):
    return not (a[2] + d < b[0] or b[2] + d < a[0] or a[3] + d < b[1] or b[3] + d < a[1])


def _num(t):
    s = re.sub(r"[^\d.\-]", "", t.replace(",", ""))
    try:
        return float(s)
    except ValueError:
        return None


def _progression(v):
    nums = [_num(l.text) for l in v]
    if all(n is not None for n in nums):
        d = [round(b - a, 6) for a, b in zip(nums, nums[1:])]
        return len(set(d)) == 1 and d[0] != 0
    # month-year labels
    return sum(1 for l in v if re.match(rf"^(?:{MON3})[a-z]*[\-‐‑–' ]?\d{{2,4}}$", l.text)) >= 4


def claim_chart_text(regions, lines, body, pw, ph):
    for ri, rg in enumerate(regions):
        x0, y0, x1, y1 = rg["bbox"]
        rg["lines"] = []
        for l in lines:
            if l.drop or l.claim is not None:
                continue
            cx, cy = l.cx, l.cy
            inside = x0 <= cx <= x1 and y0 <= cy <= y1
            if inside and len(l.text) >= 45 and l.size >= body - 0.7 and not l.rot:
                continue   # body text is never chart text
            if inside:
                l.claim = ri
                rg["lines"].append(l)
                continue
            margin = (x0 - 55 <= cx <= x1 + 55) and (y0 - 14 <= cy <= y1 + 42)
            if not margin:
                continue
            small = l.size < body - 0.8
            ticky = is_tick(l.text) and len(l.text) <= 12
            if l.rot or small or ticky:
                # a line that is clearly a prose line (long, body sized) is never claimed from the margin
                if len(l.text) > 70 and not l.rot:
                    continue
                l.claim = ri
                rg["lines"].append(l)
    return regions


def region_extent(rg):
    bb = rg["bbox"]
    for l in rg["lines"]:
        bb = union(bb, (l.x0, l.y0, l.x1, l.y1))
    return bb


def pick_title(rg, lines, body):
    """Printed chart title: a bold / larger horizontal line inside the top of the region or directly above it
    (also a 'Figure/Chart/Exhibit ...' line directly below)."""
    x0, y0, x1, y1 = rg["bbox"]
    rcx = (x0 + x1) / 2
    cand = []
    chart_lines = [l for l in rg["lines"] if not l.rot]
    sizes = [l.size for l in chart_lines if not is_tick(l.text)]
    med = statistics.median(sizes) if sizes else body
    for l in chart_lines:
        if FIG_LINE.match(l.text):
            cand.append(l)
            continue
        if is_tick(l.text) or SRC_LINE.match(l.text):
            continue
        if len(l.text) < 8 or len(l.text.split()) > 16:
            continue
        top_third = l.cy <= y0 + 0.30 * (y1 - y0)
        if top_third and (l.bold or l.size > med + 0.4) and abs(l.cx - rcx) <= 0.3 * (x1 - x0):
            cand.append(l)
    for l in lines:
        if l.drop or l.claim is not None or l.rot or l.used:
            continue
        if FIG_LINE.match(l.text) and (-9 <= y0 - l.y1 <= 40 or -9 <= l.y0 - y1 <= 40) and l.x1 > x0 and l.x0 < x1:
            cand.append(l)
            continue
        between = [m for m in lines if m is not l and not m.drop and m.claim is None and not m.rot
                   and m.y0 >= l.y1 - 1 and m.y1 <= y0 + 1 and m.x1 > x0 and m.x0 < x1
                   and not (abs(m.size - l.size) < 0.6 and m.bold == l.bold and m.y0 - l.y1 < 1.4 * l.size)]
        if 0 <= y0 - l.y1 <= 60 and not between and (l.bold or l.size > body + 0.3) and len(l.text) >= 5 and len(l.text.split()) <= 16 \
                and not l.text.endswith(".") and l.x1 > x0 and l.x0 < x1:
            if abs(l.cx - rcx) <= 0.3 * (x1 - x0) or l.x0 >= x0 - 3:
                cand.append(l)
        if 0 <= l.y0 - y1 <= 14 and re.match(r"^(?:Figure|Chart|Exhibit)\b", l.text) and l.x1 > x0 and l.x0 < x1:
            cand.append(l)
    if not cand:
        return None, []
    cand.sort(key=lambda l: l.y0)
    # contiguous stacks of same-style lines; the stack with the biggest type wins, then the top-most
    stacks = [[cand[0]]]
    for l in cand[1:]:
        p = stacks[-1][-1]
        if l.y0 - p.y1 < 1.4 * p.size and abs(l.size - p.size) < 0.6 and l.bold == p.bold:
            stacks[-1].append(l)
        else:
            stacks.append([l])
    best = max(stacks, key=lambda s: (bool(FIG_LINE.match(s[0].text)), round(s[0].size, 1), -s[0].y0))
    title = " ".join(l.text for l in best)
    return re.sub(r"\s+", " ", title).strip(), best


def pair_labels(rg):
    """Pair printed data labels with printed category labels. Only when every non-axis numeric label has exactly one
    category partner; otherwise None. Never uses geometry of bars/lines for values."""
    ls = [l for l in rg["lines"] if not l.rot and not SRC_LINE.match(l.text)]
    if len(ls) < 4:
        return None
    vals = [l for l in ls if VALUE.match(l.text)]
    cats = [l for l in ls if not VALUE.match(l.text) and not is_tick(l.text) and len(l.text.split()) <= 4 and len(l.text) <= 30]
    # axis tick values: arithmetic runs in a column or a row
    ticks = set()
    for key in ("x1", "cy"):
        groups = collections.defaultdict(list)
        for l in vals:
            groups[round((l.x1 if key == "x1" else l.cy) / 4)].append(l)
        for g in groups.values():
            g.sort(key=lambda l: l.y0 if key == "x1" else l.x0)
            if len(g) >= 3 and _progression(g):
                ticks.update(id(l) for l in g)
    data = [l for l in vals if id(l) not in ticks]
    if len(data) < 2:
        return None
    # (a) stacked: category directly above / below its value
    def stacked():
        pairs = []
        for v in data:
            c = [k for k in cats if abs(k.cx - v.cx) <= 10 and (0 <= v.y0 - k.y1 <= 5 or 0 <= k.y0 - v.y1 <= 5)]
            if len(c) != 1:
                return None
            pairs.append((c[0], v))
        if len({id(c) for c, _ in pairs}) != len(pairs):
            return None
        return pairs

    def sidebyside():
        pairs = []
        for v in data:
            c = [k for k in cats if abs(k.cy - v.cy) <= 3 and 0 <= v.x0 - k.x1 <= 40]
            if len(c) != 1:
                return None
            pairs.append((c[0], v))
        if len({id(c) for c, _ in pairs}) != len(pairs):
            return None
        return pairs

    def axis():
        # category row: >= 3 horizontal labels on one baseline, all below the data labels
        rows = collections.defaultdict(list)
        for k in cats + [l for l in ls if is_tick(l.text) and not VALUE.match(l.text)] + \
                [l for l in vals if id(l) in ticks]:
            rows[round(k.cy / 3)].append(k)
        best = None
        for r in rows.values():
            r = sorted(r, key=lambda k: k.x0)
            if len(r) >= 3 and all(min(v.y1 for v in data) < r[0].y0 for _ in [0]):
                if best is None or len(r) > len(best):
                    best = r
        if best is None:
            return None
        sp = statistics.median([b.cx - a.cx for a, b in zip(best, best[1:])])
        pairs = []
        for v in data:
            c = [k for k in best if abs(k.cx - v.cx) <= 0.4 * sp]
            if len(c) != 1:
                return None
            pairs.append((c[0], v))
        if len({id(c) for c, _ in pairs}) != len(pairs):
            return None
        return pairs

    for fn in (stacked, sidebyside, axis):
        pairs = fn()
        if pairs:
            return sorted(pairs, key=lambda p: (p[0].cx, p[0].cy))
    return None


def render_chart(rg, lines, body):
    title, title_lines = pick_title(rg, lines, body)
    for l in title_lines:
        if l.claim is None:
            l.claim = -1
    parts = [f"*Chart: {title}*" if title else "*Chart*"]
    pairs = pair_labels(rg)
    if pairs:
        parts.append("| Label | Value |\n| --- | --- |\n" + "\n".join(f"| {c.text} | {v.text} |" for c, v in pairs))
    srcs = sorted((l for l in rg["lines"] if (SRC_LINE.match(l.text) or l.text.startswith("*")) and not l.rot),
                  key=lambda l: (l.y0, l.x0))
    if srcs:
        parts.append("\n\n".join(("\\" + l.text) if l.text.startswith("*") else f"*{l.text}*" for l in srcs))
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------------------------------------------
# page assembly
# ----------------------------------------------------------------------------------------------------------------
def detect_gutter(items, pw):
    """x of the gutter of a 2-column page, or None. items: elements with x0,x1 (text lines)."""
    narrow = [e for e in items if (e.x1 - e.x0) <= 0.6 * pw]
    if len(narrow) < 8:
        return None
    ivs = sorted((e.x0, e.x1) for e in narrow)
    cov = []
    for a, b in ivs:
        if cov and a <= cov[-1][1] + 0.01:
            cov[-1][1] = max(cov[-1][1], b)
        else:
            cov.append([a, b])
    for (a0, a1), (b0, b1) in zip(cov, cov[1:]):
        if b0 - a1 >= 8 and 0.25 * pw <= (a1 + b0) / 2 <= 0.75 * pw:
            g = (a1 + b0) / 2
            left = [e for e in narrow if e.x1 <= g]
            right = [e for e in narrow if e.x0 >= g]
            if len(left) >= 4 and len(right) >= 3:
                return g
    return None


class El:
    __slots__ = ("kind", "x0", "y0", "x1", "y1", "line", "md", "size", "bold")

    def __init__(self, kind, bb, line=None, md=None):
        self.kind = kind
        self.x0, self.y0, self.x1, self.y1 = bb
        self.line = line
        self.md = md


def order_elements(els, pw):
    g = detect_gutter([e for e in els if e.kind == "line"], pw)
    if g is None:
        return sorted(els, key=lambda e: (round(e.y0), e.x0))
    def straddles(e):
        lp, rp = g - e.x0, e.x1 - g
        return min(lp, rp) >= max(30.0, 0.2 * (e.x1 - e.x0))
    wide = sorted((e for e in els if straddles(e)), key=lambda e: e.y0)
    rest = [e for e in els if e not in wide]
    out = []
    bounds = [-1e9] + [w.y0 for w in wide] + [1e9]
    for k in range(len(bounds) - 1):
        lo, hi = bounds[k], bounds[k + 1]
        band = [e for e in rest if lo <= e.y0 < hi or (k == 0 and e.y0 < hi)]
        band = [e for e in band if (lo <= e.y0 < hi)]
        left = sorted((e for e in band if (e.x0 + e.x1) / 2 < g), key=lambda e: (e.y0, e.x0))
        right = sorted((e for e in band if (e.x0 + e.x1) / 2 >= g), key=lambda e: (e.y0, e.x0))
        out += left + right
        if k < len(wide):
            out.append(wide[k])
    return out


def doc_body_size(all_lines) -> float:
    cnt = collections.Counter()
    for l in all_lines:
        if l.drop or l.rot or len(l.text) < 25:
            continue
        cnt[round(l.size * 2) / 2] += len(l.text)
    return cnt.most_common(1)[0][0] if cnt else 10.0


def mark_running(page_lines, pw, ph, hdr_rects):
    # disclaimer blocks
    bad_blocks = {l.block for l in page_lines if DISCLAIMER.search(l.text)}
    for l in page_lines:
        t = l.text
        flat = re.sub(r"\s", "", t)
        if l.block in bad_blocks and len(t) < 260:
            l.drop = "disclaimer"
        elif any(p.search(t) for p in RUNNING):
            l.drop = "running"
        elif norm_letters(t) == BRAND:
            l.drop = "running"
        elif DATE_LINE.match(flat) and l.y0 < 330:
            l.drop = "date"
        elif re.fullmatch(r"(?:19|20)\d\d", flat) and l.size >= 12 and l.y0 < 200:
            l.drop = "date"
        elif re.fullmatch(r"\d{1,2}", t) and l.y0 >= ph - 62:
            l.drop = "pageno"
    return page_lines


def match_title(lines0, title):
    """Mark the page-0 lines that print the title."""
    if not title:
        return
    tn = norm_letters(title)
    cand = sorted((l for l in lines0 if not l.drop and not l.rot), key=lambda l: (l.y0, l.x0))
    for i in range(len(cand)):
        acc = ""
        for j in range(i, min(i + 4, len(cand))):
            acc += norm_letters(cand[j].text)
            if acc == tn:
                for l in cand[i:j + 1]:
                    l.drop = "title"
                return
            if not tn.startswith(acc):
                break
    # fallback: single lines that are fully contained in the title and big / bold
    for l in cand:
        n = norm_letters(l.text)
        if len(n) >= 6 and n in tn and (l.bold or l.size >= 13) and l.y0 < 330:
            l.drop = "title"


def guess_title(lines0, body):
    cand = sorted((l for l in lines0 if not l.drop and not l.rot and l.y0 < 330 and l.claim is None), key=lambda l: l.y0)
    for i, l in enumerate(cand):
        if (l.bold or l.size >= body + 1.5) and len(l.text) >= 5:
            tl = [l]
            for m in cand[i + 1:]:
                if m.y0 - tl[-1].y1 < 1.4 * tl[-1].size and abs(m.size - l.size) < 0.6 and m.bold == l.bold:
                    tl.append(m)
                else:
                    break
            for m in tl:
                m.drop = "title"
            return " ".join(m.text for m in tl)
    return ""


def render(pdf_path, title: str | None = None) -> str:
    doc = pymupdf.open(str(pdf_path))
    pages = []
    for pno, page in enumerate(doc):
        pages.append((page, extract_lines(page)))
    all_lines = [l for _, ls in pages for l in ls]
    for page, ls in pages:
        mark_running(ls, page.rect.width, page.rect.height, [])
    body = doc_body_size(all_lines)
    if pages:
        lines0 = pages[0][1]
        if title:
            match_title(lines0, title)
            if not any(l.drop == "title" for l in lines0):
                guess_title(lines0, body)   # the MD's H1 (taken from the file name) differs from the printed title
        title_top = min([l.y0 for l in lines0 if l.drop == "title"], default=None)
    else:
        title_top = None
    out_blocks: list[tuple[str, str, bool]] = []   # (kind, text, page-first)
    pitch_all = []
    for pno, (page, ls) in enumerate(pages):
        pw, ph = page.rect.width, page.rect.height
        if pno == 0 and title is None:
            body_tmp = body
            title = guess_title(ls, body_tmp)
            title_top = min([l.y0 for l in ls if l.drop == "title"], default=None)
        # chart regions from drawings / images, then text-only evidence
        tables0 = find_tables(ls, body)
        regions, hdr = find_regions(page, ls, pw, ph, title_top if pno == 0 else None, body,
                                    [t["bbox"] for t in tables0])
        # header/footer lines inside header/footer images that are running text were already dropped; any other
        # lines inside them are kept as text.
        # drop frame-only clusters that coincide with a printed table
        keep = []
        for rg in regions:
            if rg["ruleonly"] and any(inter_area(rg["bbox"], t["bbox"]) >= 0.4 * area(rg["bbox"]) or
                                      inter_area(rg["bbox"], t["bbox"]) >= 0.4 * area(t["bbox"]) for t in tables0):
                continue
            keep.append(rg)
        regions = keep
        # a framed grid of rules and rectangles with a 2-column table inside (label | page, label | value)
        keep = []
        for rg in regions:
            if rg["ruleonly"]:
                bx = rg["bbox"]
                inside = {i for i, l in enumerate(ls) if not l.drop and l.claim is None and not l.rot
                          and bx[0] - 3 <= l.cx <= bx[2] + 3 and bx[1] - 3 <= l.cy <= bx[3] + 3}
                t2 = find_tables(ls, body, mc=2, subset=inside)
                if t2:
                    tables0 += t2
                    continue
            keep.append(rg)
        regions = keep
        # a region with a block of body text inside is a frame / panel round prose, not a chart
        keep = []
        for rg in regions:
            bx = rg["bbox"]
            prose_in = [l for l in ls if not l.drop and not l.rot and len(l.text) >= 45 and l.size >= body - 0.7
                        and bx[0] <= l.cx <= bx[2] and bx[1] <= l.cy <= bx[3]]
            if len(prose_in) < 3:
                keep.append(rg)
        regions = keep
        claim_chart_text(regions, ls, body, pw, ph)
        extra = tick_regions(ls, pw, regions, skip={li for t in tables0 for li in t["lines"]})
        if extra:
            regions += extra
            claim_chart_text(extra, ls, body, pw, ph)
        # a region with neither text nor an image nor a real plot is decoration
        regions = [rg for rg in regions if rg["img"] or rg["lines"] or len(rg["dr"]) >= 10]
        tables = []
        for t in tables0:
            tb = t["bbox"]
            if any(inter_area(tb, region_extent(rg)) >= 0.5 * area(tb) for rg in regions):
                continue
            tables.append(t)
        for t in tables:
            for li in t["lines"]:
                ls[li].used = True
        els: list[El] = []
        for rg in regions:
            ext = region_extent(rg)
            md = render_chart(rg, ls, body)
            e = El("chart", ext, md=md)
            e.y0 = rg["bbox"][1]    # reading order follows the plot, not the small print around it
            els.append(e)
        for t in tables:
            els.append(El("table", t["bbox"], md=t["md"]))
        for l in ls:
            if l.drop or l.claim is not None or l.used or l.rot:
                continue
            els.append(El("line", (l.x0, l.y0, l.x1, l.y1), line=l))
        els = order_elements(els, pw)
        # paragraphs / headings
        left_of = {}
        body_lines = [e.line for e in els if e.kind == "line" and e.line.size >= body - 0.5]
        pitch = []
        for a, b in zip(body_lines, body_lines[1:]):
            dy = b.y0 - a.y0
            if 0 < dy < 2.0 * a.size and abs(a.x0 - b.x0) < 30 or (0 < dy < 2.0 * a.size and abs(a.x0 - b.x0) < 130):
                pitch.append(dy)
        pitch_all += pitch
        elems = []   # (kind, text)
        cur: list[Line] = []
        cur_left = None

        def flush():
            nonlocal cur
            if cur:
                txt = join_lines([c.text for c in cur])
                elems.append(["para", txt, cur[0], cur[-1]])
            cur = []

        norm_pitch = statistics.median(pitch) if pitch else 1.25 * body
        k = 0
        n = len(els)
        while k < n:
            e = els[k]
            if e.kind != "line":
                flush()
                elems.append([e.kind, e.md, None, None])
                k += 1
                continue
            l = e.line
            styled = (l.bold or l.size >= body + 0.7) and len(l.text) <= 120 and len(l.text.split()) <= 16
            if styled and k > 0 and els[k - 1].kind == "line":
                pl = els[k - 1].line
                dy = l.y0 - pl.y0
                if 0 < dy <= 1.3 * norm_pitch and not pl.text.endswith(SENT_END) and abs(pl.size - l.size) < 3:
                    styled = False   # emphasised words inside a paragraph, not a heading
            if styled:
                # gather the heading block: consecutive lines of the same style
                hl = [l]
                m = k + 1
                while m < n and els[m].kind == "line":
                    nx = els[m].line
                    if abs(nx.size - l.size) < 0.6 and nx.bold == l.bold and 0 < nx.y0 - hl[-1].y0 < 1.9 * l.size \
                            and abs(nx.x0 - l.x0) < 40 and len(nx.text) <= 120:
                        hl.append(nx)
                        m += 1
                    else:
                        break
                nxt = els[m] if m < n else None
                htxt = join_lines([x.text for x in hl])
                token = len(htxt) <= 4 or bool(VALUE.match(htxt)) or bool(TICK.match(htxt))
                if nxt is not None and nxt.kind == "line" and not (nxt.line.bold or nxt.line.size >= body + 0.7) \
                        and not htxt.endswith(".") and not token:
                    flush()
                    elems.append(["heading", htxt, hl[0], hl[-1]])
                    k = m
                    continue
                if len(hl) == 1 and (l.bold) and not l.text.endswith(".") and len(l.text) < 80:
                    flush()
                    elems.append(["para", f"**{l.text}**", l, l])
                    k += 1
                    continue
            # ordinary prose line: decide whether it starts a new paragraph
            new = False
            if not cur:
                new = True
            else:
                p = cur[-1]
                dy = l.y0 - p.y0
                if dy < -2 or dy > 1.45 * max(norm_pitch, p.size * 1.15):
                    new = True
                elif BULLET.match(l.text):
                    new = True
                elif p.text.endswith(SENT_END) and (l.x0 - min(c.x0 for c in cur)) >= 7 and l.x0 - p.x0 >= 7:
                    new = True
                elif abs(l.size - p.size) > 1.0:
                    new = True
            if new:
                flush()
            cur.append(l)
            k += 1
        flush()
        for el in elems:
            out_blocks.append((el[0], el[1], pno))
    # stitch paragraphs across page breaks and consecutive fragments
    final: list[tuple[str, str]] = []
    prev_page = None
    for kind, txt, pno in out_blocks:
        if kind == "para" and final and final[-1][0] == "para" and prev_page is not None and pno != prev_page \
                and not final[-1][1].endswith(SENT_END) and txt[:1].islower() and not txt.startswith("**"):
            final[-1] = ("para", join_lines([final[-1][1], txt]))
        else:
            final.append((kind, txt))
        prev_page = pno
    global LAST_DEBUG
    LAST_DEBUG = [(pno, l.text, l.drop, l.claim, l.used, l.rot, l.size)
                  for pno, (_, ls) in enumerate(pages) for l in ls]
    md = []
    if title:
        md.append(f"# {title}")
    for kind, txt in final:
        if kind == "heading":
            md.append(f"### {txt}")
        elif kind == "para":
            b = BULLET.match(txt)
            if b:
                md.append("- " + txt[b.end():])
            elif re.match(r"^(?:\*(?!\*)|[+\-#>]\s|\d+[.)]\s)", txt):
                md.append("\\" + txt)
            else:
                md.append(txt)
        else:
            md.append(txt)
    return "\n\n".join(md) + "\n"


# ----------------------------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------------------------
FM = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)


def pdf_for(md_text: str) -> Path | None:
    m = re.search(r'^source_file:\s*"?([^"\n]+)"?\s*$', md_text[:3000], re.M)
    if not m:
        return None
    rel = m.group(1).strip()
    for r in (MAIN_ROOT, ROOT):
        if (r / rel).is_file():
            return r / rel
    return None


def render_md(md_path: Path) -> tuple[str, str | None]:
    raw = md_path.read_bytes().decode("utf-8")
    fm = FM.match(raw)
    head = fm.group(0) if fm else ""
    rest = raw[len(head):]
    m = re.search(r"^# (.+)$", rest, re.M)
    title = m.group(1).strip() if m else None
    pdf = pdf_for(raw)
    if pdf is None:
        return raw, "pdf_missing"
    body = render(pdf, title)
    return head + "\n" + body, None


def _work(args):
    md_path, out_dir = args
    try:
        text, err = render_md(md_path)
        if err:
            return md_path.name, err
        out = out_dir / md_path.parent.name / md_path.name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(text.encode("utf-8"))
        return md_path.name, None
    except Exception as exc:  # noqa: BLE001
        return md_path.name, f"{type(exc).__name__}: {exc}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--year", action="append")
    ap.add_argument("--stem", action="append", help="only MDs whose name contains this text")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args(argv)
    out_dir = Path(a.out)
    mds = sorted(MD_ROOT.rglob("*.md"))
    if a.year:
        mds = [m for m in mds if m.parent.name in a.year]
    if a.stem:
        mds = [m for m in mds if any(s in m.name for s in a.stem)]
    if a.limit:
        mds = mds[:a.limit]
    lexicon()
    errs = []
    if a.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.workers) as ex:
            for i, (name, err) in enumerate(ex.map(_work, [(m, out_dir) for m in mds], chunksize=8), 1):
                if err:
                    errs.append((name, err))
                if i % 200 == 0:
                    print(f"  {i}/{len(mds)}", flush=True)
    else:
        for i, m in enumerate(mds, 1):
            name, err = _work((m, out_dir))
            if err:
                errs.append((name, err))
            if i % 200 == 0:
                print(f"  {i}/{len(mds)}", flush=True)
    print(f"{len(mds)} MDs rendered to {out_dir}; {len(errs)} errors")
    for name, err in errs[:30]:
        print("  ", name, err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
