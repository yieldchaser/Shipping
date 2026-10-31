"""
Intermodal "Commodities & Ship Finance" page -> Markdown section.

The weekly report's last text page prints a daily macro grid, a bunker table, a
maritime-stock table and a news / macro-headlines article. Most intermodal MDs lack that
page (only the 2021 W35-era extraction carried it). This renders it from the PDF text
layer, straight from word geometry (rows by y, cells by x), so every number is the
string the publisher printed ("4,352.34", "609.0", "-6.8%"), never a re-formatted float.

Usage:
  render_intermodal_finance_md.py --out DIR      write DIR/<year>/<stem>.section.md for review
  render_intermodal_finance_md.py --apply        append the section to MDs that lack it
Optional: --files STEM_OR_PATH ... restricts either mode to those MDs.

The tables are text only; a PDF whose table values are not in the text layer (image
tables) is skipped, never guessed. The same values are parsed into series by
run_intermodal_finance.py; use that module as the cross-check.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "intermodal"
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB

DATE_RX = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2}$")
NUM_RX = re.compile(r"^[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)%?$")
CURR_RX = re.compile(r"^[A-Z]{3}$")
GRADE_PORT_ROW_TOL = 3.5

# Indicators the publisher prints, used only to pick the printed category label of a row.
CURRENCY_LABEL_RX = re.compile(r"/|INDEX", re.I)
COMMODITY_LABELS = {"brent", "wti", "gold", "oil"}

# The 2023 W22-W36 text layer kerns some labels apart ("Dow J ones", "G LOBUS", "S tock").
# A label whose whitespace-free form is a known printed label is written as that label.
CATEGORIES = ["Stock Exchange Data", "Currencies", "Commodities"]
INDICATORS = [
    "10year US Bond", "S&P 500", "Nasdaq", "Dow Jones", "FTSE 100", "FTSE All-Share UK", "CAC40",
    "Xetra Dax", "Nikkei", "Hang Seng", "DJ US Maritime", "€ / $", "£ / $", "$ / ¥",
    "$ / NoK", "Yuan / $", "Won / $", "$ / Yuan", "$ / Won", "$ INDEX", "Brent", "WTI",
]
COMPANIES = [
    "CAPITAL PRODUCT PARTNERS LP", "COSTAMARE INC", "DANAOS CORPORATION", "DIANA SHIPPING",
    "EAGLE BULK SHIPPING", "EUROSEAS LTD.", "GLOBUS MARITIME LIMITED", "NAVIOS MARITIME ACQUISITIONS",
    "NAVIOS MARITIME HOLDINGS", "NAVIOS MARITIME PARTNERS LP", "SAFE BULKERS INC",
    "SEANERGY MARITIME HOLDINGS", "SEANERGY MARITIME HOLDINGS CORP", "STAR BULK CARRIERS CORP",
    "STEALTHGAS INC", "TOP SHIPS INC", "TSAKOS ENERGY NAVIGATION",
]


def _nkey(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


_CANON = {_nkey(t): t for t in CATEGORIES + INDICATORS + COMPANIES}


def canon(text: str) -> str:
    return _CANON.get(_nkey(text), text)


MARKERS = ("Commodities & Ship Finance", "Maritime Stock Data")

# Real hyphenated compounds the publisher's line break can split ("US-" / "listed"). Any
# other "xxx-" at a line end is a hyphenation break and is joined ("Gri-" + "maud").
# Measured over all 258 finance pages: these are every real compound that wrapped.
REAL_COMPOUNDS = {
    "us-listed", "uk-headquartered", "buy-back", "five-year", "month-on-month", "near-term",
    "over-allotment", "short-term", "spin-off", "sustainability-linked", "balloon-payment",
    "dry-cargo", "energy-cost", "high-profile", "investment-grade", "multi-currency",
    "non-compliance", "three-month", "ultra-low",
}


class Wd:
    """One text-layer word with geometry."""

    __slots__ = ("x0", "y0", "x1", "y1", "t")

    def __init__(self, x0, y0, x1, y1, t):
        self.x0, self.y0, self.x1, self.y1, self.t = x0, y0, x1, y1, t

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


class RenderError(Exception):
    pass


# ----------------------------------------------------------------------------------------
# page location and word plumbing
# ----------------------------------------------------------------------------------------

def find_page(doc: pymupdf.Document) -> Optional[int]:
    """Page whose text layer carries the stock table, the bunker/oil block and the macro grid."""
    for pno, pg in enumerate(doc):
        toks = {w[4] for w in pg.get_text("words")}
        if "Company" in toks and "Rotterdam" in toks and ("INDEX" in toks or "Bond" in toks):
            return pno
    return None


def page_words(page: pymupdf.Page) -> Tuple[List[Wd], List[Tuple[str, Tuple[float, float, float, float]]]]:
    """Horizontal words, plus the rotated category labels (text, bbox) printed along the grid."""
    rotated: List[Tuple[str, Tuple[float, float, float, float]]] = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            dx, dy = ln["dir"]
            if abs(dy) > 0.5:
                txt = " ".join("".join(s["text"] for s in ln["spans"]).split())
                if txt:
                    rotated.append((txt, tuple(ln["bbox"])))
    words = []
    for w in page.get_text("words"):
        wd = Wd(w[0], w[1], w[2], w[3], w[4])
        if any(bb[0] - 1 <= wd.xc <= bb[2] + 1 and bb[1] - 1 <= wd.yc <= bb[3] + 1 for _, bb in rotated):
            continue
        words.append(wd)
    return words, rotated


def merge_dates(words: List[Wd]) -> List[Wd]:
    """Re-join a date the text layer kerned apart ("2-J" "un-23") into the printed token."""
    out: List[Wd] = []
    ordered = sorted(words, key=lambda w: (round(w.yc), w.x0))
    i = 0
    while i < len(ordered):
        w = ordered[i]
        merged = False
        if not DATE_RX.match(w.t) and re.match(r"^\d{1,2}-", w.t):
            for span in (2, 3):
                grp = ordered[i:i + span]
                if len(grp) == span and all(abs(g.yc - w.yc) < 2 for g in grp):
                    joined = "".join(g.t for g in grp)
                    if DATE_RX.match(joined):
                        out.append(Wd(grp[0].x0, min(g.y0 for g in grp), grp[-1].x1, max(g.y1 for g in grp), joined))
                        i += span
                        merged = True
                        break
        if not merged:
            out.append(w)
            i += 1
    return out


def cluster_rows(words: List[Wd], tol: float = GRADE_PORT_ROW_TOL) -> List[List[Wd]]:
    rows: List[List[Wd]] = []
    for w in sorted(words, key=lambda w: w.yc):
        if rows and abs(w.yc - statistics.mean(x.yc for x in rows[-1])) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    for r in rows:
        r.sort(key=lambda w: w.x0)
    return rows


def is_value_text(t: str) -> bool:
    return bool(NUM_RX.match(t))


def assign_columns(cells: List[Wd], centers: List[float], limit: float) -> List[Optional[str]]:
    """Bucket words into the nearest column centre; words farther than `limit` are dropped."""
    buckets: List[List[Wd]] = [[] for _ in centers]
    for w in cells:
        k = min(range(len(centers)), key=lambda i: abs(centers[i] - w.xc))
        if abs(centers[k] - w.xc) <= limit:
            buckets[k].append(w)
    for k, b in enumerate(buckets):  # a chart legend word ("oil") next to a value is not part of the cell
        if any(is_value_text(w.t) for w in b):
            buckets[k] = [w for w in b if is_value_text(w.t)]
    cells = [" ".join(w.t for w in sorted(b, key=lambda w: w.x0)) if b else None for b in buckets]
    # an obvious printed slip ("2..756") is written as the plain value
    return [re.sub(r"(?<=\d)\.{2,}(?=\d)", ".", c) if c else c for c in cells]


def pct_center(words: List[Wd], after_x: float, before_x: float) -> Optional[float]:
    xs = [w.xc for w in words if w.t.endswith("%") and is_value_text(w.t) and after_x < w.x0 < before_x]
    return statistics.median(xs) if xs else None


# ----------------------------------------------------------------------------------------
# table parsers
# ----------------------------------------------------------------------------------------

def parse_macro(words: List[Wd], rotated, date_row: List[Wd], y_top: float, y_bottom: float):
    """Macro grid. The W-O-W percent column normally follows the day columns; some issues
    (2025 W07) print one more date column AFTER it, so columns are ordered by x."""
    dcent = [w.xc for w in date_row]
    last = date_row[-1]
    pitch = dcent[1] - dcent[0] if len(dcent) > 1 else 46
    region = [w for w in words if y_top < w.yc < y_bottom and w.x0 < last.xc + 110]
    pc = pct_center(region, date_row[0].xc + 15, last.xc + 110)
    if pc is None:
        raise RenderError("macro: no W-O-W percent column")
    cols = sorted(dcent + [pc])
    header = [next(w.t for w in date_row if w.xc == c) if c != pc else "W-O-W Change %" for c in cols]
    rows = []
    for row in cluster_rows(region):
        label_words = [w for w in row if w.xc < dcent[0] - pitch * 0.6]
        cell_words = [w for w in row if w.xc >= dcent[0] - pitch * 0.6]
        cells = assign_columns(cell_words, cols, pitch * 0.6)
        n_num = sum(1 for h, c in zip(header, cells) if h != "W-O-W Change %" and c and is_value_text(c))
        if not label_words or n_num < 1:
            continue
        rows.append(([w.t for w in label_words], cells))
    if not rows:
        raise RenderError("macro: no rows")
    dates = header
    x_max = dcent[0] - pitch * 0.6
    grid_labels = [r for r in rotated if (r[1][0] + r[1][2]) / 2 < x_max and y_top < (r[1][1] + r[1][3]) / 2 < y_bottom]
    return dates, [(canon(" ".join(l)), c) for l, c in rows], rows_categories(grid_labels, rows, region)


def rows_categories(rotated, rows, region) -> List[str]:
    """Printed rotated category label per row ("Stock Exchange Data", "Currencies", ...)."""
    def klass(label: str) -> str:
        low = label.lower()
        if low in COMMODITY_LABELS:
            return "com"
        if CURRENCY_LABEL_RX.search(label):
            return "cur"
        return "idx"

    classes = [klass(" ".join(l)) for l, _ in rows]
    runs = []
    for k in classes:
        if not runs or runs[-1] != k:
            runs.append(k)
    labels = [canon(t) for t, _ in sorted(rotated, key=lambda r: (r[1][1] + r[1][3]) / 2)]
    if len(labels) != len(runs):
        raise RenderError(f"macro: {len(labels)} printed category labels for {len(runs)} row groups {runs}")
    by_run = {}
    seq = 0
    cats = []
    prev = None
    for k in classes:
        if k != prev:
            seq += 1
            prev = k
        cats.append(labels[seq - 1])
    return cats


def parse_bunker(words: List[Wd], rotated, date_row: List[Wd], y_top: float, y_bottom: float):
    dates = [w.t for w in date_row]
    dcent = [w.xc for w in date_row]
    pitch = dcent[1] - dcent[0] if len(dcent) > 1 else 46
    x_min = date_row[0].x0 - 85
    region = [w for w in words if y_top < w.yc < y_bottom and w.x0 >= x_min]
    pc = pct_center(region, dcent[-1] + 15, dcent[-1] + 110)
    if pc is None:
        raise RenderError("bunker: no change percent column")
    cols = dcent + [pc]
    numeric_rows = []
    for row in cluster_rows(region):
        label_words = [w for w in row if w.xc < dcent[0] - pitch * 0.6]
        cell_words = [w for w in row if w.xc >= dcent[0] - pitch * 0.6]
        cells = assign_columns(cell_words, cols, pitch * 0.6)
        if label_words and all(c and is_value_text(c) for c in cells[:-1]):
            numeric_rows.append((label_words, cells))
    if not numeric_rows:
        raise RenderError("bunker: no rows")
    rows = [(statistics.mean(w.yc for w in lw), lw[-1].t, cells) for lw, cells in numeric_rows]
    y_lo = min(r[0] for r in rows) - 10
    y_hi = max(r[0] for r in rows) + 10
    grades = sorted(((bb[1] + bb[3]) / 2, t) for t, bb in rotated
                    if (bb[0] + bb[2]) / 2 >= x_min and y_lo <= (bb[1] + bb[3]) / 2 <= y_hi)
    # chunk the rows: a new group starts when a port name repeats, or when the row kind
    # changes between a port of the first group and a non-port label (Brent / WTI).
    first_ports: List[str] = []
    for r in rows:
        if r[1] in first_ports:
            break
        first_ports.append(r[1])
    chunks: List[List[tuple]] = []
    for r in rows:
        if chunks:
            cur = chunks[-1]
            if r[1] not in [x[1] for x in cur] and (r[1] in first_ports) == (cur[-1][1] in first_ports):
                cur.append(r)
                continue
        chunks.append([r])
    if len(grades) != len(chunks):
        raise RenderError(f"bunker: {len(grades)} grade labels for {len(chunks)} row groups")
    out = []
    for (_, grade), chunk in zip(grades, chunks):
        for _, port, cells in chunk:
            out.append((grade, port, cells))
    return dates, out


def parse_stocks(words: List[Wd], company: Wd, y_bottom: float):
    hdr_row = [w for w in words if abs(w.yc - company.yc) < 6]
    dates_w = sorted([w for w in hdr_row if DATE_RX.match(w.t)], key=lambda w: w.x0)
    curr_h = [w for w in hdr_row if w.t.startswith("Curr")]
    if not dates_w or not curr_h:
        raise RenderError("stocks: header not found")
    dates = [w.t for w in dates_w]
    dcent = [w.xc for w in dates_w]
    curr_x = curr_h[0].xc
    seeds = [w for w in words if w.yc > company.y1 + 6 and w.yc < y_bottom and CURR_RX.match(w.t)
             and abs(w.xc - curr_x) < 16]
    seeds.sort(key=lambda w: w.yc)
    chain = seeds[:1]
    for sd in seeds[1:]:  # the table is one unbroken run of rows; later "CNY" / "PMI" words are prose
        if sd.yc - chain[-1].yc > 25:
            break
        chain.append(sd)
    seeds = chain
    if not seeds:
        raise RenderError("stocks: no rows")
    right = dcent[-1] + 110
    pool = [w for w in words if w.yc > company.y1 + 6 and w.x0 < right]
    pc_words = [w for w in pool if w.t.endswith("%") and is_value_text(w.t) and w.x0 > dcent[-1] + 10]
    pc = statistics.median(w.xc for w in pc_words) if pc_words else None
    if pc is None:
        raise RenderError("stocks: no change percent column")
    cols = dcent + [pc]
    rows = []
    bottom = 0.0
    for s in seeds:
        near = [w for w in pool if abs(w.yc - s.yc) <= 4
                and min(seeds, key=lambda q: abs(q.yc - w.yc)) is s]
        near.sort(key=lambda w: w.x0)
        left = [w for w in near if w.x1 <= s.x0 + 0.5 and w is not s]
        if len(left) < 2:
            raise RenderError("stocks: short row at y=%.0f" % s.yc)
        exch = left[-1]
        comp = left[:-1]
        cells = assign_columns([w for w in near if w.x0 >= s.x1 - 0.5 and w is not s], cols, 24)
        if not any(c and is_value_text(c) for c in cells[:-1]):
            continue  # a 3-capital-letter word in prose (PMI, GDP), not a stock row
        rows.append((canon(" ".join(w.t for w in comp)), exch.t, s.t, cells))
        bottom = max(bottom, s.yc)
    return dates, rows, pc, bottom


# ----------------------------------------------------------------------------------------
# news column
# ----------------------------------------------------------------------------------------

def dehyphenate(lines: List[str]) -> str:
    """Join lines into one paragraph; resolve "Gri-" + "maud" but keep real "inter-company"."""
    inline = {m.group(0).lower() for ln in lines for m in re.finditer(r"[A-Za-z]+(?:-[A-Za-z]+)+", ln)}
    text = lines[0]
    for nxt in lines[1:]:
        if text.endswith("-") and nxt and nxt[0].islower() and re.search(r"[A-Za-z]-$", text):
            stem_w = re.search(r"([A-Za-z]+(?:-[A-Za-z]+)*)-$", text).group(1)
            nxt_w = re.match(r"[A-Za-z]+", nxt)
            nxt_w = nxt_w.group(0) if nxt_w else ""
            joined_w = f"{stem_w}-{nxt_w}".lower()
            real = (joined_w in REAL_COMPOUNDS or joined_w in inline
                    or re.fullmatch(r"[a-z](-[a-z])*", stem_w.lower()) is not None)
            text = text + nxt if real else text[:-1] + nxt
        elif re.match(r"-[A-Za-z]", nxt) and re.search(r"[A-Za-z]$", text):
            text = text + nxt  # "m-o" / "-m": the break fell before the second hyphen
        else:
            text = text + " " + nxt
    return text


def join_line(row: List[Wd]) -> str:
    """Words of one printed line; a stray "." / ")" word and a "-m" fragment attach to the neighbour."""
    txt = " ".join(w.t for w in row)
    txt = re.sub(r" ([.,;:!?)]+)(?= |$)", r"\1", txt)
    return re.sub(r"(?<=[A-Za-z]) -(?=[A-Za-z])", "-", txt)


def build_paragraphs(col_words: List[Wd]) -> List[str]:
    rows = cluster_rows(col_words)
    if not rows:
        return []
    ys = [statistics.mean(w.yc for w in r) for r in rows]
    gaps = [b - a for a, b in zip(ys, ys[1:]) if b - a > 5]
    pitch = min(gaps) if gaps else 12
    paras: List[List[str]] = [[]]
    for i, r in enumerate(rows):
        if i and ys[i] - ys[i - 1] > pitch * 1.25 + 1:
            paras.append([])
        paras[-1].append(join_line(r))
    return [dehyphenate(p) for p in paras if p]


def split_columns(words: List[Wd]) -> List[List[Wd]]:
    """Two-column prose: split at the widest empty vertical band inside the text block."""
    if len(words) < 20:
        return [words]
    cover = sorted((w.x0, w.x1) for w in words)
    gap, mid = 0.0, None
    reach = cover[0][1]
    for x0, x1 in cover[1:]:
        # the first empty band right of the left column's longest line is the gutter (a bullet
        # glyph of the right column sits just across it, so the widest band is the wrong one)
        if x0 - reach >= 6 and reach > 150 and mid is None:
            gap, mid = x0 - reach, (reach + x0) / 2
        reach = max(reach, x1)
    if mid is None:
        return [words]
    left = [w for w in words if w.xc < mid]
    right = [w for w in words if w.xc >= mid]
    if len(left) < 8 or len(right) < 8:
        return [words]
    return [left, right]


def parse_news(words: List[Wd], rows_bottom: float, stock_pct_c: float, company: Wd):
    """Heading + paragraphs. Right-column layout (2021-23: "Market News" beside the stock table)
    or full-width two-column "Macro-economic headlines" below the tables."""
    page_h = max(w.y1 for w in words)
    cut = page_h + 1
    texts = [w.t for w in words]
    for i, w in enumerate(words):
        nxt = words[i + 1].t if i + 1 < len(words) else ""
        if w.t == "The" and nxt == "information" and i + 2 < len(words) and words[i + 2].t == "contained":
            cut = min(cut, w.y0 - 1)
        if w.t == "Written" and nxt == "by":
            cut = min(cut, w.y0 - 1)
        if w.t.startswith("www.intermodal.gr"):
            cut = min(cut, w.y0 - 1)
        if w.t == "Intermodal" and nxt == "Shipbrokers" and i + 3 < len(words) and words[i + 3].t == "established":
            cut = min(cut, w.y0 - 1)
    head_news = None
    for w in words:
        if w.t == "News" and w.x0 > 300 and w.yc < company.yc and any(
                m.t == "Market" and abs(m.yc - w.yc) < 3 and 0 <= w.x0 - m.x1 < 10 for m in words):
            head_news = w
    if head_news is not None:
        hdr = [w for w in words if abs(w.yc - head_news.yc) < 3 and w.x0 > 300]
        title_y1 = max(w.y1 for w in hdr)
        left = stock_pct_c + 20
        prose = [w for w in words if w.y0 >= title_y1 - 0.5 and w.y1 < cut + 0.5 and w.x0 >= left]
        title = "Market News"
        cols = [prose]
    else:
        below = [w for w in words if w.y0 > rows_bottom + 4 and w.y1 < cut + 0.5 and w.x0 < 100]
        if not below:
            raise RenderError("news: no heading below the stock table")
        first = cluster_rows(below)[0]
        hdr_y = statistics.mean(w.yc for w in first)
        hdr = [w for w in words if abs(w.yc - hdr_y) < 3]
        title_y1 = max(w.y1 for w in hdr)
        compact = "".join(w.t for w in hdr).lower()
        title = "Market News" if "news" in compact else "Macro-economic headlines"
        prose = [w for w in words if w.y0 >= title_y1 - 0.5 and w.y1 < cut + 0.5]
        cols = split_columns(prose)
    paras: List[str] = []
    for c in cols:
        cp = build_paragraphs(c)
        if paras and cp and cp[0][:1].islower():  # a sentence that runs from the left column into the right
            first = dehyphenate([paras[-1], cp[0]]) if paras[-1].endswith("-") else paras[-1] + " " + cp[0]
            paras[-1] = first
            cp = cp[1:]
        paras.extend(cp)
    if not paras:
        raise RenderError("news: empty")
    return title, paras, prose, cut


# ----------------------------------------------------------------------------------------
# render
# ----------------------------------------------------------------------------------------

def md_row(cells) -> str:
    return "| " + " | ".join("" if c is None else str(c) for c in cells) + " |"


def parse_page(pdf_path) -> dict:
    doc = pymupdf.open(str(pdf_path))
    pno = find_page(doc)
    if pno is None:
        raise RenderError("finance tables are not in the text layer (no page with Company / Rotterdam / macro grid)")
    page = doc[pno]
    words, rotated = page_words(page)
    words = merge_dates(words)
    companies = [w for w in words if w.t == "Company"]
    if not companies:
        raise RenderError("no Company header")
    company = companies[0]

    date_words = [w for w in words if DATE_RX.match(w.t)]
    groups: List[List[Wd]] = []
    for row in cluster_rows(date_words, tol=2):
        grp = [row[0]]
        for w in row[1:]:
            if w.x0 - grp[-1].x1 > 100:
                groups.append(grp)
                grp = []
            grp.append(w)
        groups.append(grp)
    macro_group = max(groups, key=len)
    if len(macro_group) < 3:
        raise RenderError("macro date header not found")
    stock_y = company.yc
    bunker_group = [g for g in groups if g is not macro_group and abs(g[0].yc - stock_y) > 8]
    if not bunker_group:
        raise RenderError("bunker date header not found")
    bunker_group = max(bunker_group, key=len)

    m_dates, m_rows, m_cats = parse_macro(words, rotated, macro_group, macro_group[0].yc + 6, company.yc - 12)
    b_dates, b_rows = parse_bunker(words, rotated, bunker_group, bunker_group[0].yc + 6, company.yc - 12)
    s_dates, s_rows, s_pc, rows_bottom = parse_stocks(words, company, page.rect.height)
    title, paras, prose_words, cut = parse_news(words, rows_bottom, s_pc, company)
    return {
        "page": pno, "words": words, "company": company, "cut": cut,
        "macro": (m_dates, m_rows, m_cats), "bunker": (b_dates, b_rows),
        "stocks": (s_dates, s_rows), "news": (title, paras), "prose_words": prose_words,
        "stock_pct_c": s_pc,
    }


def render(pdf_path) -> str:
    p = parse_page(pdf_path)
    m_dates, m_rows, m_cats = p["macro"]
    b_dates, b_rows = p["bunker"]
    s_dates, s_rows = p["stocks"]
    title, paras = p["news"]

    out = ["---", "", "# Commodities & Ship Finance", "", "## Market Data", ""]
    out.append(md_row(["Category", "Indicator"] + m_dates))
    out.append(md_row(["---"] * (len(m_dates) + 2)))
    for (label, cells), cat in zip(m_rows, m_cats):
        out.append(md_row([cat, label] + cells))

    bunker = [r for r in b_rows if r[0].upper() != "OIL"]
    oil = [r for r in b_rows if r[0].upper() == "OIL"]
    out += ["", "## Bunker Prices", ""]
    out.append(md_row(["Grade", "Port"] + b_dates + ["Change %"]))
    out.append(md_row(["---"] * (len(b_dates) + 3)))
    for grade, port, cells in bunker:
        out.append(md_row([grade, port] + cells))
    if oil:
        out += ["", "## Oil Prices", ""]
        out.append(md_row(["Category", "Indicator"] + b_dates + ["Change %"]))
        out.append(md_row(["---"] * (len(b_dates) + 3)))
        for grade, port, cells in oil:
            out.append(md_row([grade, port] + cells))

    out += ["", "## Maritime Stock Data", ""]
    out.append(md_row(["Company", "Stock Exchange", "Curr."] + s_dates + ["W-O-W Change %"]))
    out.append(md_row(["---"] * (len(s_dates) + 4)))
    for comp, exch, curr, cells in s_rows:
        out.append(md_row([comp, exch, curr] + cells))

    out += ["", f"## {title}", ""]
    for para in paras:
        out += [para, ""]
    return "\n".join(out).rstrip("\n") + "\n"


# ----------------------------------------------------------------------------------------
# MD targets
# ----------------------------------------------------------------------------------------

def resolve_pdf(source_file: str) -> Optional[Path]:
    """source_file is relative to the repo root; a worktree may lack corpus/, so try its parents."""
    for base in [ROOT] + list(ROOT.parents):
        cand = base / source_file
        if cand.exists():
            return cand
    return None


def md_source_file(text: str) -> Optional[str]:
    m = re.search(r'^source_file:\s*"(.*)"', text, re.M)
    return m.group(1) if m else None


def targets(selected: Optional[List[str]] = None):
    for md in sorted(OUT_MD.glob("*/*.md")):
        if selected and not any(s == md.stem or s == md.name or Path(s) == md for s in selected):
            continue
        text = md.read_bytes().decode("utf-8")
        sf = md_source_file(text)
        yield md, sf, any(k in text for k in MARKERS), text


def append_section(md: Path, section: str) -> None:
    raw = md.read_bytes()
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    body = section.replace("\n", eol.decode())
    if raw.endswith(eol):
        add = eol + body.encode("utf-8")
    else:
        add = eol + eol + body.encode("utf-8")
    with open(md, "ab") as fh:
        fh.write(add)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", help="write DIR/<year>/<stem>.section.md for review")
    ap.add_argument("--apply", action="store_true", help="append the section to MDs that lack it")
    ap.add_argument("--files", nargs="*", help="only these MD stems / paths")
    a = ap.parse_args()
    if not a.out and not a.apply:
        ap.error("give --out DIR and/or --apply")
    done = skipped = failed = 0
    for md, sf, has, _ in targets(a.files):
        if a.apply and has:
            skipped += 1
            continue
        pdf = resolve_pdf(sf) if sf else None
        if pdf is None:
            print(f"[no-pdf] {md.name}")
            failed += 1
            continue
        try:
            section = render(pdf)
        except RenderError as e:
            print(f"[skip] {md.name}: {e}")
            failed += 1
            continue
        if a.out:
            dest = Path(a.out) / md.parent.name / f"{md.stem}.section.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(section.encode("utf-8"))
        if a.apply:
            append_section(md, section)
        done += 1
    print(f"rendered {done}, already had section {skipped}, failed {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
