"""Deterministic geometric table extractor (engine `pymupdf_table`).

Tables are declared in the profile by anchor + header labels. Column x-boundaries come from
vertical rulings in the header row when their count matches (headers + 1), otherwise from the
midpoints between header-label centres. Rows come from horizontal rulings covering the key
column (falling back to key-column text clustering when a table has no rulings). Cell text is
the PDF text layer verbatim (only broken glyphs are repaired, see `repair_word`).

Prose comes from LiteParse markdown with the regions covered by extracted tables removed and
the geometric tables inserted at the reading-order position of the first removed block.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pymupdf

ROW_TOL = 3.0          # y tolerance (pt) when ordering text inside a cell
PHRASE_GAP = 6.0       # max gap (pt) between words belonging to one phrase
RULE_MIN_LEN = 3.0
EMPTY_CELL_RE = re.compile(r"^[-\u2013\u2014]*$")      # blank or a dash placeholder ("-", "--", en/em dashes)
NO_SALES = "No reported sales"


# --------------------------------------------------------------------------- text repair
def repair_word(text: str) -> str:
    """Map U+FFFD from a broken font encoding to the glyph it replaces in context."""
    if "\ufffd" not in text:
        return text
    if text == "\ufffd":
        return "\u2013"
    if text.startswith("\ufffd") and len(text) > 1 and text[1].isalnum():
        text = "\u201c" + text[1:]
    if text.endswith("\ufffd") and len(text) > 1 and text[-2].isalnum():
        text = text[:-1] + "\u201d"
    return re.sub(r"(?<=\w)\ufffd(?=\w)", "\u2019", text)


def repair_text(text: str) -> str:
    return " ".join(repair_word(t) for t in text.split(" "))


# --------------------------------------------------------------------------- data classes
@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int = 0
    line: int = 0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Segment:
    pos: float   # y for horizontal, x for vertical
    a: float     # start along the axis
    b: float     # end


@dataclass
class TableResult:
    name: str
    title: str
    page: int
    bbox: tuple[float, float, float, float]
    columns: list[str]
    rows: list[list[str]]
    en_bloc_rows: list[int] = field(default_factory=list)
    empty: bool = False
    boundary_source: str = "rulings"
    row_source: str = "rulings"
    unassigned_words: int = 0
    shared_cell_count_mismatch: int = 0       # shared cells whose block count differs from the vessel count (kept whole)
    title_size: float | None = None           # font size of the printed title line (heading level ranking)
    level: int | None = None                  # markdown heading level chosen by the engine
    row_meta: list[list[float]] = field(default_factory=list)   # per row: [page, band top, band bottom, interval]
    column_bounds: list[float] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)    # header labels before the Built split
    hidden: bool = False                      # stub that only marks a continuation region (excluded from prose)
    extra_regions: list[dict[str, Any]] = field(default_factory=list)   # continuation rows on following pages

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name, "title": self.title, "page": self.page,
            "bbox": [round(v, 2) for v in self.bbox], "columns": self.columns, "rows": self.rows,
            "en_bloc_rows": self.en_bloc_rows, "empty": self.empty,
            "boundary_source": self.boundary_source, "row_source": self.row_source,
            "unassigned_words": self.unassigned_words,
            **({"extra_regions": self.extra_regions} if self.extra_regions else {}),
            **({"shared_cell_count_mismatch": self.shared_cell_count_mismatch} if self.shared_cell_count_mismatch else {}),
            "row_meta": self.row_meta, "column_bounds": [round(b, 1) for b in self.column_bounds],
            "source_columns": self.source_columns,
        }

    def to_markdown(self, heading_level: int = 3) -> str:
        heading_level = self.level or heading_level
        return render_gfm(self.columns, self.rows, heading=self.title, level=heading_level)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_gfm(columns: list[str], rows: list[list[str]], heading: str | None = None, level: int = 3) -> str:
    out = []
    if heading:
        out.append("#" * level + " " + heading + "\n")
    out.append("| " + " | ".join(_cell(c) for c in columns) + " |")
    out.append("|" + "|".join("---" for _ in columns) + "|")
    for r in rows:
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    return "\n".join(out)


# --------------------------------------------------------------------------- page primitives
def page_words(page: pymupdf.Page) -> list[Word]:
    out = []
    for x0, y0, x1, y1, t, b, l, _ in page.get_text("words"):
        out.append(Word(x0, y0, x1, y1, repair_word(t), b, l))
    return out


def page_lines(words: list[Word]) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Text lines (by PyMuPDF block/line ids) with bbox, in reading order."""
    groups: dict[tuple[int, int], list[Word]] = {}
    for w in words:
        groups.setdefault((w.block, w.line), []).append(w)
    lines = []
    for ws in groups.values():
        ws.sort(key=lambda w: w.x0)
        lines.append((" ".join(w.text for w in ws),
                      (min(w.x0 for w in ws), min(w.y0 for w in ws), max(w.x1 for w in ws), max(w.y1 for w in ws))))
    lines.sort(key=lambda t: (round(t[1][1]), t[1][0]))
    return lines


def _near_white(col) -> bool:
    return bool(col) and all(c > 0.97 for c in col)


def page_rulings(page: pymupdf.Page) -> tuple[list[Segment], list[Segment]]:
    """Return (horizontal, vertical) ruling segments from vector drawings, merged along their axis."""
    raw_h: list[Segment] = []
    raw_v: list[Segment] = []
    for dr in page.get_drawings():
        if _near_white(dr.get("fill")) and not dr.get("color"):
            continue
        if _near_white(dr.get("color")) and not dr.get("fill"):
            continue
        for it in dr["items"]:
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.y - q.y) < 0.8 and abs(p.x - q.x) >= RULE_MIN_LEN:
                    raw_h.append(Segment((p.y + q.y) / 2, min(p.x, q.x), max(p.x, q.x)))
                elif abs(p.x - q.x) < 0.8 and abs(p.y - q.y) >= RULE_MIN_LEN:
                    raw_v.append(Segment((p.x + q.x) / 2, min(p.y, q.y), max(p.y, q.y)))
            elif it[0] == "re" and dr.get("fill") and not dr.get("color"):
                r = it[1]
                if r.height <= 1.5 and r.width >= RULE_MIN_LEN:
                    raw_h.append(Segment((r.y0 + r.y1) / 2, r.x0, r.x1))
                elif r.width <= 1.5 and r.height >= RULE_MIN_LEN:
                    raw_v.append(Segment((r.x0 + r.x1) / 2, r.y0, r.y1))
    return _merge(raw_h), _merge(raw_v)


def _merge(segs: list[Segment], pos_tol: float = 0.9, gap: float = 3.0) -> list[Segment]:
    segs = sorted(segs, key=lambda s: (round(s.pos / pos_tol), s.a))
    out: list[Segment] = []
    for s in sorted(segs, key=lambda s: (s.pos, s.a)):
        for o in out:
            if abs(o.pos - s.pos) <= pos_tol and s.a <= o.b + gap and s.b >= o.a - gap:
                o.a, o.b = min(o.a, s.a), max(o.b, s.b)
                break
        else:
            out.append(Segment(s.pos, s.a, s.b))
    return out


def _dedupe(values: list[float], tol: float = 1.5) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


# --------------------------------------------------------------------------- header location
def _find_label(label: str, band: list[Word], used: set[int]) -> list[Word] | None:
    tokens = label.split()
    first = [w for w in band if id(w) not in used and w.text.lower() == tokens[0].lower()]
    if not first:
        return None
    first.sort(key=lambda w: (w.y0, w.x0))
    w0 = first[0]
    found = [w0]
    for tok in tokens[1:]:
        cands = [w for w in band if id(w) not in used and w not in found and w.text.lower() == tok.lower()
                 and abs(w.cx - found[-1].cx) <= 90]
        if not cands:
            return None
        found.append(min(cands, key=lambda w: abs(w.cx - found[-1].cx) + abs(w.y0 - found[-1].y0)))
    return found


def locate_headers(labels: list[str], words: list[Word], y_top: float, y_bottom: float
                   ) -> list[tuple[float, float, float, float]] | None:
    """Bounding box of every header label inside the band, or None if any is missing."""
    band = [w for w in words if y_top <= w.y0 <= y_bottom]
    used: set[int] = set()
    boxes = []
    for label in labels:
        ws = None
        for alt in label.split("|"):          # "Built|BLT": alternative spellings across layouts
            ws = _find_label(alt, band, used)
            if ws is not None:
                break
        if ws is None:
            return None
        used.update(id(w) for w in ws)
        boxes.append((min(w.x0 for w in ws), min(w.y0 for w in ws), max(w.x1 for w in ws), max(w.y1 for w in ws)))
    return boxes


def _covers(seg: Segment, x: float) -> bool:
    return seg.a - 0.5 <= x <= seg.b + 0.5


# --------------------------------------------------------------------------- phrases / assignment
def _phrases(words: list[Word], bounds: list[float] | None = None) -> list[tuple[float, float, float, list[Word]]]:
    """Group same-line words with small gaps. Returns (cx, y0, y1, words).

    With column `bounds`, a phrase is also cut where its next word lies in another column ("DD 08/21" next to
    "(BWTS on order included)" are two cells, not one phrase), except for phrases that start in the first
    column: those can be one printed description spanning several columns."""
    ws = sorted(words, key=lambda w: (round(w.cy / ROW_TOL), w.x0))
    out: list[list[Word]] = []
    for w in ws:
        if out and abs(out[-1][-1].cy - w.cy) <= ROW_TOL and 0 <= w.x0 - out[-1][-1].x1 <= PHRASE_GAP and not (
                bounds and len(bounds) > 3 and out[-1][0].x0 >= bounds[1]
                and _column_of(out[-1][-1].cx, bounds) != _column_of(w.cx, bounds)):
            out[-1].append(w)
        else:
            out.append([w])
    res = []
    for ph in out:
        res.append(((min(w.x0 for w in ph) + max(w.x1 for w in ph)) / 2,
                    min(w.y0 for w in ph), max(w.y1 for w in ph), ph))
    return res


def _column_of(cx: float, bounds: list[float]) -> int:
    for i in range(len(bounds) - 1):
        if cx < bounds[i + 1]:
            return i
    return len(bounds) - 2


def _join_cell(words: list[Word]) -> str:
    if not words:
        return ""
    ws = sorted(words, key=lambda w: w.y0)
    clusters: list[list[Word]] = []
    for w in ws:
        if clusters and abs(w.y0 - clusters[-1][0].y0) <= ROW_TOL:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    text = ""
    for c in clusters:
        line = " ".join(w.text for w in sorted(c, key=lambda w: w.x0))
        # a hyphen at a line end followed by an alphanumeric start is a wrapped token (e.g. 7S50MC-/C7.1)
        text = text + line if text.endswith("-") and line[:1].isalnum() else (text + " " + line).strip()
    return text


# --------------------------------------------------------------------------- extraction
def extract_table(cfg: dict[str, Any], page: pymupdf.Page, page_no: int, words: list[Word],
                  hsegs: list[Segment], vsegs: list[Segment], anchor_bbox: tuple[float, float, float, float],
                  title: str, limit_y: float, memory: dict[Any, Any] | None = None,
                  continuation: bool = False) -> TableResult | None:
    labels: list[str] = cfg["headers"]
    n = len(labels)
    ax0, ay0, ax1, ay1 = anchor_bbox
    header_lines = int(cfg.get("header_lines", 1))
    mem_key = tuple(labels)
    hdr_boxes = locate_headers(labels, words, ay1 - 1, ay1 + 14 + 14 * header_lines + 20)
    headerless = False
    if hdr_boxes is None:
        # a continued table can start on a new page without its header row: reuse the column geometry
        # of the same layout seen earlier in the document
        geo = (memory or {}).get(mem_key) if cfg.get("headerless_ok") else None
        if geo is None:
            return None
        headerless = True
        hy0 = hy1 = ay1 + 2
        hx0, hx1, centers = geo["hx0"], geo["hx1"], list(geo["centers"])
    else:
        hy0 = min(b[1] for b in hdr_boxes)
        hy1 = max(b[3] for b in hdr_boxes)
        hx0 = min(b[0] for b in hdr_boxes)
        hx1 = max(b[2] for b in hdr_boxes)
        centers = [(b[0] + b[2]) / 2 for b in hdr_boxes]
        if centers != sorted(centers):
            return None

    # horizontal rulings that span the header width (>= 50 %)
    def spans_table(s: Segment) -> bool:
        ov = min(s.b, hx1 + 40) - max(s.a, hx0 - 40)
        return ov >= 0.5 * (hx1 - hx0)

    cand_h = [s for s in hsegs if spans_table(s)]
    above = [s.pos for s in cand_h if s.pos <= hy0 + 1 and s.pos >= ay1 - 2]
    below = [s.pos for s in cand_h if s.pos >= hy1 - 1 and s.pos <= limit_y + 0.5]
    hdr_top = max(above) if above else hy0 - 2
    body_rules = _dedupe([p for p in below])
    has_rulings = len(body_rules) >= 1
    hdr_bottom = hy1 if continuation else (body_rules[0] if has_rulings else hy1 + 2)

    # column boundaries
    def _vlines(y: float) -> list[float]:
        return _dedupe([v.pos for v in vsegs if v.a <= y <= v.b and hx0 - 60 <= v.pos <= hx1 + 60], tol=4.5)

    v_in_header = _vlines((hdr_top + hdr_bottom) / 2)
    if len(v_in_header) != n + 1:
        # some layouts (2021) rule only the body rows: use the verticals that cross the first body row
        v_in_header = _vlines(hdr_bottom + 8)
    if headerless:
        bounds, boundary_source = list(geo["bounds"]), geo["boundary_source"]
    elif len(v_in_header) == n + 1 and all(v_in_header[i] <= centers[i] <= v_in_header[i + 1] for i in range(n)):
        bounds = v_in_header
        boundary_source = "rulings"
    else:
        mids = [(centers[i] + centers[i + 1]) / 2 for i in range(n - 1)]
        bounds = [0.0, *mids, page.rect.width]
        boundary_source = "header-midpoints"
    key_col = int(cfg.get("key_column", 0))
    key_cx = (bounds[key_col] + bounds[key_col + 1]) / 2 if boundary_source == "rulings" else centers[key_col]

    body_words = [w for w in words if w.cy >= hdr_bottom and w.y1 <= limit_y + 1
                  and bounds[0] - 1 <= w.cx <= bounds[-1] + 1]

    # row intervals
    # every ruling that crosses the key column separates two rows, even a partial one (SFL SPEY / MEDWAY have a
    # rule only under name, DWT, SS/DD and Price): not just rules that span half the table
    # (a ruled table frame can start further left than the header text: SFL bulletins start at x=14, header at 57)
    rule_lo = min(hx0 - 40, bounds[0] - 3) if boundary_source == "rulings" else hx0 - 40
    rule_hi = max(hx1 + 60, bounds[-1] + 3) if boundary_source == "rulings" else hx1 + 60
    key_rules = [s for s in hsegs if _covers(s, key_cx) and s.pos > hdr_bottom + 0.5 and s.pos <= limit_y + 0.5
                 and s.a >= rule_lo and s.b <= rule_hi]
    row_edges: list[float]
    if has_rulings and key_rules:
        row_edges = [hdr_bottom, *_dedupe([s.pos for s in key_rules])]
        tail = [w for w in body_words if row_edges[-1] < w.cy <= row_edges[-1] + 30]
        if tail and not _has_key_phrase(tail, bounds, key_col, cfg.get("row_start_pattern")):
            tail = []
        if tail:
            row_edges.append(max(w.y1 for w in tail) + 1)
        row_source = "rulings"
        intervals = list(zip(row_edges[:-1], row_edges[1:]))
        bottom = row_edges[-1]
    else:
        row_source = "key-column"
        intervals = _cluster_rows(body_words, bounds, key_col, cfg.get("row_start_pattern"))
        bottom = max([w.y1 for w in body_words] + [hdr_bottom])

    ncols = n
    # text sitting between the header row and the first body rule would be silently lost: surface it
    skipped = [w for w in words if hy1 + 1 < w.cy < hdr_bottom - 0.5 and bounds[0] - 1 <= w.cx <= bounds[-1] + 1
               and w.y1 <= limit_y + 1]
    cells: list[list[list[Word]]] = [[[] for _ in range(ncols)] for _ in intervals]
    unassigned = len(skipped)
    phrases = _phrases(body_words, bounds if boundary_source == "rulings" else None)
    # a phrase that starts in the first column and runs across 2+ further columns is one merged cell
    # (e.g. a printed deal description in place of a vessel name): keep it in the first column, together
    # with the later lines of that cell (they may start further right, e.g. a short last line)
    span: dict[int, tuple[float, float]] = {}     # row index -> (first spanning y0, right edge)
    if len(bounds) > 3:
        for cx, y0, y1, ph in phrases:
            idx = next((i for i, (a, b) in enumerate(intervals) if a <= (y0 + y1) / 2 < b), None)
            if idx is not None and len(ph) > 3 and min(w.x0 for w in ph) < bounds[1]                     and max(w.x1 for w in ph) > bounds[3]:
                top, right = span.get(idx, (y0, 0.0))
                span[idx] = (min(top, y0), max(right, max(w.x1 for w in ph)))
    for cx, y0, y1, ph in phrases:
        cy = (y0 + y1) / 2
        idx = next((i for i, (a, b) in enumerate(intervals) if a <= cy < b), None)
        if idx is None:
            unassigned += len(ph)
            continue
        col = _column_of(cx, bounds)
        if idx in span:
            top, right = span[idx]
            if y0 >= top - 1 and max(w.x1 for w in ph) <= right + 1:      # inside the description's extent
                col = 0
        cells[idx][col].extend(ph)

    # merged (spanning) cells: a column boundary is open when no ruling covers that column there
    per_vessel = {i for i, l in enumerate(labels) if l.split("|")[0] in (cfg.get("per_vessel_columns") or [])}
    shared = {i for i, l in enumerate(labels) if l.split("|")[0] in (cfg.get("span_columns") or [])}
    merged, flagged = _merged_rows(cells, intervals, hsegs, bounds, key_col, ncols, row_source, per_vessel, shared)
    if row_source == "key-column" and intervals:
        key_ys = []
        for (ya, yb), row in zip(intervals, cells):
            kw = row[key_col]
            key_ys.append(sum(w.cy for w in kw) / len(kw) if kw else (ya + yb) / 2)
        for ci, lab in enumerate(labels):
            if lab.split("|")[0] in (cfg.get("span_columns") or []):
                col_text, col_flags = _infer_spans(cells, key_ys, ci)
                for r, t in enumerate(col_text):
                    merged[r][ci] = t
                flagged |= col_flags
    rows_text: list[list[str]] = []
    kept_flags: list[int] = []
    expand = row_source == "rulings"
    part_patterns = {i: re.compile(cfg["split_part_patterns"][l.split("|")[0]]) for i, l in enumerate(labels)
                     if l.split("|")[0] in (cfg.get("split_part_patterns") or {})}
    count_hint = None
    if cfg.get("vessel_count_column") in [l.split("|")[0] for l in labels]:
        hint_ci = [l.split("|")[0] for l in labels].index(cfg["vessel_count_column"])
        count_hint = (hint_ci, re.compile(cfg.get("vessel_count_pattern", r"\bSS\b")))
    names0 = [l.split("|")[0] for l in labels]
    group_markers = {names0.index(k): re.compile(v, re.I) for k, v in (cfg.get("group_markers") or {}).items() if k in names0}
    amount_cols = {i for i, l in enumerate(names0) if l in (cfg.get("amount_split_columns") or [])}
    centered_cols = {i for i, l in enumerate(names0) if l in (cfg.get("centered_split_columns") or [])}
    mismatch: list[int] = []
    row_meta: list[list[float]] = []
    for i, row in enumerate(merged):
        if not any(x.strip() for x in row):
            continue
        expanded = _expand_deal(cells[i], row, key_col, shared, cfg.get("row_start_pattern"),
                                int(cfg.get("name_column", 0)), count_hint, per_vessel,
                                _name_rules(hsegs, bounds, int(cfg.get("name_column", 0)), intervals[i]),
                                {c: _name_rules(hsegs, bounds, c, intervals[i]) for c in range(ncols)},
                                part_patterns, group_markers, amount_cols, centered_cols, mismatch) if expand else None
        if expanded:
            subs, key_ys_i = expanded
            a_i, b_i = intervals[i]
            for j, sub in enumerate(subs):
                kept_flags.append(len(rows_text))
                rows_text.append(sub)
                sub_top = a_i if j == 0 else (key_ys_i[j - 1] + key_ys_i[j]) / 2
                sub_bottom = b_i if j == len(subs) - 1 else (key_ys_i[j] + key_ys_i[j + 1]) / 2
                row_meta.append([page_no, round(sub_top, 1), round(sub_bottom, 1), i])
            continue
        if i in flagged:
            kept_flags.append(len(rows_text))
        rows_text.append(row)
        row_meta.append([page_no, round(intervals[i][0], 1), round(intervals[i][1], 1), i])

    if memory is not None and not headerless:
        memory[mem_key] = {"hx0": hx0, "hx1": hx1, "centers": centers, "bounds": bounds,
                           "boundary_source": boundary_source}
    columns = [l.split("|")[0] for l in labels]
    empty = all(all(EMPTY_CELL_RE.match(x.strip()) for x in r) for r in rows_text)
    if empty:
        rows_text = [[NO_SALES] + [""] * (ncols - 1)]
        kept_flags = []
        rows_text, columns, kept_flags = _apply_splits(cfg.get("split_columns") or [], columns, rows_text, kept_flags)
    else:
        marker_col = next((i for i, l in enumerate(columns) if l.lower() == "price"), ncols - 1)
        for ri in kept_flags:
            if "en bloc" not in rows_text[ri][marker_col].lower():
                rows_text[ri][marker_col] = (rows_text[ri][marker_col] + " (en bloc)").strip()
        rows_text, columns, kept_flags = _apply_splits(cfg.get("split_columns") or [], columns, rows_text, kept_flags)

    return TableResult(
        name=cfg["name"], title=title, page=page_no,
        bbox=(min(ax0, bounds[0] if boundary_source == "rulings" else hx0), ay0,
              max(ax1, bounds[-1] if boundary_source == "rulings" else hx1), bottom),
        columns=columns, rows=rows_text, en_bloc_rows=kept_flags, empty=empty,
        boundary_source=boundary_source, row_source=row_source, unassigned_words=unassigned,
        shared_cell_count_mismatch=len(mismatch),
        row_meta=[] if empty else row_meta, column_bounds=list(bounds), source_columns=list(names0))


def _has_key_phrase(words: list[Word], bounds: list[float], key_col: int, pattern: str | None) -> bool:
    rx = re.compile(pattern) if pattern else None
    for w in words:
        if _column_of(w.cx, bounds) == key_col and (rx is None or rx.search(w.text)):
            return True
    return False


def _line_groups(words: list[Word]) -> list[list[Word]]:
    ws = sorted(words, key=lambda w: w.y0)
    groups: list[list[Word]] = []
    for w in ws:
        if groups and abs(w.y0 - groups[-1][0].y0) <= ROW_TOL:
            groups[-1].append(w)
        else:
            groups.append([w])
    return [sorted(g, key=lambda w: w.x0) for g in groups]


def _mean_cy(words: list[Word]) -> float:
    return sum(w.cy for w in words) / len(words)


def _split_column(words: list[Word], key_ys: list[float], tol: float = 6.5, centered: float = 0.0) -> list[str] | None:
    """Split a cell shared by m vessels into m texts, or None when the cell is one shared value.

    Every text line goes to the vessel whose key line is nearest (so a wrapped name stays with its
    vessel). The split is accepted only if every vessel receives text and each vessel's first line
    starts within `tol` of its key line; a value centred between two vessels is therefore shared.

    `centered` > 0 is the mode for multi-line comment cells (Details): each vessel's block is centred on its
    key line rather than starting on it, so the block's mean line position must lie within `centered` of the
    key line and the gap between neighbouring blocks must be bigger than the line pitch inside them."""
    m = len(key_ys)
    lines = _line_groups(words)
    if not lines:
        return None
    groups: list[list[Word]] = [[] for _ in range(m)]
    first_y: list[float | None] = [None] * m
    for ln in lines:
        cy = _mean_cy(ln)
        j = min(range(m), key=lambda k: abs(key_ys[k] - cy))
        groups[j].extend(ln)
        if first_y[j] is None:
            first_y[j] = cy
    if any(not g for g in groups):
        return None
    if centered:
        if any(abs(sum(_mean_cy(ln) for ln in _line_groups(g)) / len(_line_groups(g)) - key_ys[j]) > centered
               for j, g in enumerate(groups)):
            return None
    elif any(abs(first_y[j] - key_ys[j]) > tol for j in range(m)):
        return None
    if tol < 1e8 or centered:
        # one block of evenly spaced lines cut into unequal parts is a shared cell, not per-vessel text:
        # a real boundary shows a bigger gap than the line pitch inside the groups
        counts = [len(_line_groups(g)) for g in groups]
        inner, bounds_gap = [], []
        for j, g in enumerate(groups):
            ys = [_mean_cy(ln) for ln in _line_groups(g)]
            inner += [b - a for a, b in zip(ys, ys[1:])]
            if j + 1 < m:
                nxt = [_mean_cy(ln) for ln in _line_groups(groups[j + 1])]
                bounds_gap.append(nxt[0] - ys[-1])
        pitch = sum(inner) / len(inner) if inner else 10.0
        if min(bounds_gap) <= 1.35 * pitch:
            return None
    return [_join_cell(g) for g in groups]


def _block_count(words: list[Word]) -> int:
    """Number of separate text blocks in a cell: line groups apart by more than the line pitch start a new block."""
    ys = [_mean_cy(ln) for ln in _line_groups(words)]
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    if not gaps:
        return 1 if ys else 0
    pitch = min(gaps)
    return 1 + sum(1 for g in gaps if g > 1.35 * pitch)


def _name_rules(hsegs: list[Segment], bounds: list[float], name_col: int, interval: tuple[float, float]) -> list[float]:
    """Horizontal rulings strictly inside a row interval that cover the name column but not the whole row."""
    a, b = interval
    cx = (bounds[name_col] + bounds[name_col + 1]) / 2
    return sorted(s.pos for s in hsegs if a + 3 < s.pos < b - 3 and _covers(s, cx))


AMOUNT_TOKEN_RE = re.compile(
    r"(?:(?:RGN|REGION|LOW|MID|HIGH|XS)(?:\s*[/\-]\s*(?:LOW|MID|HIGH|XS|RGN))?\s+)*(?:USD|US\$|\$)\s*\d[\d.,]*\s*(?:M|B|BN)?\b",
    re.I)


def _split_by_amounts(text: str, m: int) -> list[str] | None:
    """Cut a shared price text into m pieces when it holds exactly m amounts ("USD 14.6 M USD 14.8 M (en bloc)")."""
    hits = list(AMOUNT_TOKEN_RE.finditer(text))
    if len(hits) != m:
        return None
    starts = [0] + [h.start() for h in hits[1:]]
    ends = starts[1:] + [len(text)]
    return [text[a:b].strip() for a, b in zip(starts, ends)]


def _split_by_marker(words: list[Word], marker: re.Pattern, m: int, match: bool = False) -> list[str] | None:
    """Split a cell into m texts, one starting at each line that contains the marker (e.g. one "SS" block
    per vessel). Used when the marker occurs on exactly m lines; lines before the first marker join part 1."""
    lines = _line_groups(words)
    test = marker.match if match else marker.search
    starts = [i for i, ln in enumerate(lines) if test(" ".join(w.text for w in ln))]
    if len(starts) != m:
        return None
    starts[0] = 0
    bounds = starts + [len(lines)]
    return [_join_cell([w for ln in lines[a:b] for w in ln]) for a, b in zip(bounds, bounds[1:])]


def _expand_deal(cells_row: list[list[Word]], merged_row: list[str], key_col: int, shared: set[int],
                 pattern: str | None, name_col: int = 0, count_hint: tuple[int, re.Pattern] | None = None,
                 per_vessel: set[int] | None = None, name_rules: list[float] | None = None,
                 col_rules: dict[int, list[float]] | None = None,
                 part_patterns: dict[int, re.Pattern] | None = None,
                 group_markers: dict[int, re.Pattern] | None = None, amount_cols: set[int] | None = None,
                 centered_cols: set[int] | None = None, mismatch: list[int] | None = None) -> tuple[list[list[str]], list[float]] | None:
    """One ruled row can hold several vessels (en bloc / sister ships). Return one row per vessel,
    repeating shared cells (price, buyer, and any cell that cannot be split per vessel).

    Vessels are counted from the key column (DWT) and from the name column; names on separate
    lines far enough apart (> 12 pt) are separate vessels even when DWT is one merged cell."""
    rx = re.compile(pattern) if pattern else None
    key_ys = []
    for cx, y0, y1, ph in _phrases(cells_row[key_col]):
        if rx is None or rx.search(" ".join(w.text for w in ph)):
            cy = (y0 + y1) / 2
            if not key_ys or cy - key_ys[-1] > ROW_TOL:
                key_ys.append(cy)
    name_ys: list[float] = []
    name_line_ys: list[float] = []
    for cx, y0, y1, ph in _phrases(cells_row[name_col]):
        cy = (y0 + y1) / 2
        name_line_ys.append(cy)
        if not name_ys or cy - name_ys[-1] > 12.0:
            name_ys.append(cy)
    if name_rules:
        # a ruling that only crosses the name column separates two vessels inside one merged row
        edges = [-1e9, *sorted(name_rules), 1e9]
        parts = [[y for y in name_line_ys if edges[k] < y < edges[k + 1]] for k in range(len(edges) - 1)]
        if all(parts):
            key_ys = [sum(p) / len(p) for p in parts]
            name_ys = key_ys
    if len(name_ys) > len(key_ys) and count_hint is not None:
        # sister vessels sharing one DWT cell: trust the name lines only when another column agrees
        # on the vessel count (e.g. one "SS" block per vessel); a wrapped name never passes this
        hint_col, hint_rx = count_hint
        if len(hint_rx.findall(merged_row[hint_col])) == len(name_ys):
            key_ys = name_ys
    if len(key_ys) < 2:
        return None
    m = len(key_ys)
    out = [[""] * len(merged_row) for _ in range(m)]
    for c, words in enumerate(cells_row):
        # one amount per vessel in a shared price cell ("USD 14.6 M USD 14.8 M"): assign them in reading order;
        # a different number of amounts stays one raw shared text (the series then leaves the price blank)
        if c in (amount_cols or set()) and m > 1:
            pieces = _split_by_amounts(merged_row[c], m)
            if pieces is not None:
                for j in range(m):
                    out[j][c] = pieces[j]
                continue
        # a column with its own rulings between the vessels has one cell per vessel: take the lines of each
        # cell (a column without such rulings is either one shared cell or split by alignment below)
        cuts = (col_rules or {}).get(c)
        if c not in shared and cuts and len(cuts) == m - 1:
            edges = [-1e9, *cuts, 1e9]
            groups = [[w for w in words if edges[k] < w.cy < edges[k + 1]] for k in range(m)]
            if all(groups):
                for j in range(m):
                    out[j][c] = _join_cell(groups[j])
                continue
        # fewer rulings than vessels - 1: each ruled cell spans the vessels whose key line lies inside it
        # (DONG-A OKNOS / ASTREA share "2010 HHI", EOS has "2009 HHI"), so the cell text goes to each of them
        if c not in shared and c not in (per_vessel or set()) and cuts and 0 < len(cuts) < m - 1:
            edges = [-1e9, *sorted(cuts), 1e9]
            seg_of = [next(k for k in range(len(edges) - 1) if edges[k] < y <= edges[k + 1]) for y in key_ys]
            segs = [[w for w in words if edges[k] < w.cy < edges[k + 1]] for k in range(len(edges) - 1)]
            if all(segs) and set(seg_of) == set(range(len(segs))):
                for j in range(m):
                    out[j][c] = _join_cell(segs[seg_of[j]])
                continue
        if count_hint is not None and c == count_hint[0] and c not in shared:
            marked = _split_by_marker(words, count_hint[1], m)
            if marked is not None:
                for j in range(m):
                    out[j][c] = marked[j]
                continue
        # a column whose cell holds one block per vessel (engine makers, SS lines, years) is cut at the markers
        # when the marker count equals the vessel count; one marker means one shared block (copied whole);
        # any other count is left as the raw shared text rather than guessed
        mk = (group_markers or {}).get(c)
        if mk is not None and c not in (per_vessel or set()):
            lines = _line_groups(words)
            n_mark = sum(1 for ln in lines if mk.match(" ".join(w.text for w in ln)))
            if n_mark == m:
                for j, txt in enumerate(_split_by_marker(words, mk, m, match=True) or []):
                    out[j][c] = txt
                continue
            if n_mark >= 1:
                for j in range(m):
                    out[j][c] = merged_row[c]
                continue
        # columns that always hold one value per vessel (name, DWT) are split by nearest line without
        # the alignment tolerance used for cells that may be one value shared by all vessels
        parts = None if c in shared else _split_column(words, key_ys, 1e9 if c in (per_vessel or set()) else 6.5)
        if parts is None and c in (centered_cols or set()):
            parts = _split_column(words, key_ys, 6.5, centered=9.0)
            # blocks that cannot be matched one-to-one with the vessels are kept whole (never guessed) and flagged
            if parts is None and mismatch is not None and _block_count(words) not in (0, 1, m):
                mismatch.append(c)
        # a split is only believed when every part looks like a standalone value of that column (a Built part
        # must start with a year): "2012 HHIC-PHILIPPINES" / "(SUBIC SHIPYARD)" is one shared cell, not two
        pat = (part_patterns or {}).get(c)
        if parts is not None and pat is not None and not all(pat.match(x) for x in parts):
            parts = None
        for j in range(m):
            out[j][c] = parts[j] if parts is not None else merged_row[c]
    return out, key_ys


def _merged_rows(cells, intervals, hsegs, bounds, key_col, ncols, row_source, skip_cols: set[int] | None = None,
                 flag_cols: set[int] | None = None) -> tuple[list[list[str]], set[int]]:
    """Join cell text per row; cells without a ruling between rows span them (replicated, flagged)."""
    rows = [[_join_cell(c) for c in row] for row in cells]
    flagged: set[int] = set()
    if row_source != "rulings":
        return rows, flagged
    for c in range(ncols):
        if c == key_col or c in (skip_cols or set()):     # per-vessel columns are never one shared value
            continue
        ccx = (bounds[c] + bounds[c + 1]) / 2
        i = 0
        while i < len(intervals):
            j = i
            while j + 1 < len(intervals) and not any(
                    abs(s.pos - intervals[j][1]) <= 1.5 and _covers(s, ccx) for s in hsegs):
                j += 1
            if j > i:
                text = _join_cell([w for k in range(i, j + 1) for w in cells[k][c]])
                for k in range(i, j + 1):
                    rows[k][c] = text
                    if flag_cols is None or c in flag_cols:
                        flagged.add(k)
            i = j + 1
    return rows, flagged


def _cluster_rows(words: list[Word], bounds: list[float], key_col: int, pattern: str | None
                  ) -> list[tuple[float, float]]:
    """Fallback row detection: a new row starts at each key-column phrase (optionally matching a regex).
    Between two key lines the cut goes through the widest vertical whitespace, because cells are
    often vertically centred so details lines can sit above or below their key line."""
    rx = re.compile(pattern) if pattern else None
    key_words = [w for w in words if _column_of(w.cx, bounds) == key_col]
    starts: list[float] = []
    for cx, y0, y1, ph in _phrases(key_words):
        text = " ".join(w.text for w in ph)
        if rx is None or rx.search(text):
            cy = (y0 + y1) / 2
            if not starts or cy - starts[-1] > ROW_TOL:
                starts.append(cy)
    if not starts:
        return []
    top = min(w.y0 for w in words)
    bottom = max(w.y1 for w in words) + 1
    cuts = []
    for i in range(len(starts) - 1):
        lo, hi = starts[i], starts[i + 1]
        lines = sorted({(round(w.y0, 1), round(w.y1, 1)) for w in words if lo - 2 <= w.cy <= hi + 2})
        best_gap, best_cut = -1.0, (lo + hi) / 2
        for (a0, a1), (b0, b1) in zip(lines, lines[1:]):
            if a0 + ROW_TOL > hi or b1 < lo:
                continue
            gap = b0 - a1
            if gap > best_gap and lo <= (a1 + b0) / 2 <= hi:
                best_gap, best_cut = gap, (a1 + b0) / 2
        cuts.append(best_cut)
    edges = [top - 0.5, *cuts, bottom]
    return list(zip(edges[:-1], edges[1:]))


def _infer_spans(cells: list[list[list[Word]]], key_ys: list[float], col: int) -> tuple[list[str], set[int]]:
    """Without rulings a merged cell shows up as text in one row and blanks in its neighbours.
    Because merged cells are vertically centred, each non-empty cell claims the contiguous blank rows
    that bring the centre of its group closest to the centre of its text."""
    n = len(cells)
    text = [_join_cell(cells[i][col]) for i in range(n)]
    anchors = [i for i in range(n) if text[i].strip()]
    out = list(text)
    flagged: set[int] = set()
    if not anchors:
        return out, flagged
    top = 0
    for k, ai in enumerate(anchors):
        last = k + 1 == len(anchors)
        nxt = n if last else anchors[k + 1]
        yc = sum(w.cy for w in cells[ai][col]) / len(cells[ai][col])
        if last:
            bottom = nxt - 1
        else:
            bottom, best_cost = ai, None
            for b in range(ai, nxt):
                cost = abs((key_ys[top] + key_ys[b]) / 2 - yc)
                if best_cost is None or cost < best_cost - 1e-6:
                    bottom, best_cost = b, cost
        for r in range(top, bottom + 1):
            out[r] = text[ai]
        if bottom > top:
            flagged.update(range(top, bottom + 1))
        top = bottom + 1
    return out, flagged


def _apply_splits(splits: list[dict[str, Any]], columns: list[str], rows: list[list[str]], flags: list[int]
                  ) -> tuple[list[list[str]], list[str], list[int]]:
    for sp in splits:
        if sp["column"] not in columns:
            continue
        ci = columns.index(sp["column"])
        rx = re.compile(sp["pattern"])
        new_cols = list(sp["into"])
        columns = columns[:ci] + new_cols + columns[ci + 1:]
        new_rows = []
        for r in rows:
            m = rx.match(r[ci].strip())
            parts = list(m.groups()) if m else [r[ci]] + [""] * (len(new_cols) - 1)
            parts = [(p or "").strip() for p in parts]
            parts += [""] * (len(new_cols) - len(parts))
            new_rows.append(r[:ci] + parts[:len(new_cols)] + r[ci + 1:])
        rows = new_rows
    return rows, columns, flags


# --------------------------------------------------------------------------- page-level driver
def find_tables(page: pymupdf.Page, page_no: int, table_cfgs: list[dict[str, Any]],
                stop_anchors: list[str] | None = None, footer_margin: float = 45.0,
                memory: dict[Any, Any] | None = None, continuation_ignore: list[str] | None = None) -> list[TableResult]:
    words = page_words(page)
    if not words:
        return []
    lines = page_lines(words)
    hsegs, vsegs = page_rulings(page)
    stops = [re.compile(p) for p in (stop_anchors or [])]
    anchor_res = [(cfg, re.compile(cfg["anchor"])) for cfg in table_cfgs]
    footer_y = page.rect.height - footer_margin
    results: list[TableResult] = []
    consumed: set[int] = set()
    done_cfgs: set[int] = set()
    # all section-start lines: every table anchor plus extra stop anchors
    boundary_ys = sorted(bb[1] for text, bb in lines
                         if any(rx.match(text) for _, rx in anchor_res) or any(s.match(text) for s in stops))
    for ci, (cfg, rx) in enumerate(anchor_res):
        for li, (text, bb) in enumerate(lines):
            if li in consumed or ci in done_cfgs or not rx.match(text):
                continue
            nxt = [y for y in boundary_ys if y > bb[3] + 12]
            limit = min([footer_y] + nxt)
            res = extract_table(cfg, page, page_no, words, hsegs, vsegs, bb, text, limit, memory)
            if res is not None:
                res.title_size = _title_font_size(page, bb)
                results.append(res)
                consumed.add(li)
                done_cfgs.add(ci)
    results.sort(key=lambda t: t.bbox[1])
    if memory is not None:
        stub = _continue_open_table(memory, page, page_no, table_cfgs, words, hsegs, vsegs, boundary_ys, footer_y,
                                    continuation_ignore)
        if stub is not None:
            results.insert(0, stub)
        real = [t for t in results if not t.hidden and not t.empty]
        last = real[-1] if real else None
        # "open" = nothing but the footer follows the table on this page, so its rows may go on overleaf
        trailing = [w for w in words if w.y0 > (last.bbox[3] + 3 if last else 0) and w.y1 < footer_y] if last else []
        memory["_open"] = last if (last is not None and not trailing) else None
        memory["_open_page"] = page_no
    return results


CONTINUATION_TOP = 45.0


def _title_font_size(page: pymupdf.Page, bb: tuple[float, float, float, float]) -> float | None:
    """Font size of the text line at `bb` (the printed table title)."""
    best = None
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            x0, y0, x1, y1 = ln["bbox"]
            if abs(y0 - bb[1]) < 2.5 and x0 <= bb[2] and x1 >= bb[0]:
                sizes = [s["size"] for s in ln["spans"] if s["text"].strip()]
                if sizes:
                    best = max(sizes)
    return best


def _ignored_word_ids(words: list[Word], patterns: list[str] | None) -> set[int]:
    """ids of words on lines (same PyMuPDF block/line) whose text matches one of the ignore patterns,
    e.g. a letterhead line repeated at the top of every page."""
    if not patterns:
        return set()
    rxs = [re.compile(p) for p in patterns]
    groups: dict[tuple[int, int], list[Word]] = {}
    for w in words:
        groups.setdefault((w.block, w.line), []).append(w)
    out: set[int] = set()
    for ws in groups.values():
        text = " ".join(w.text for w in sorted(ws, key=lambda w: w.x0))
        if any(r.match(text) for r in rxs):
            out.update(id(w) for w in ws)
    return out


KEY_VALUE_DEFAULT = r"^\d{1,3}(?:[.,]\d{3})+$|^\d{4,6}$"
CONTINUATION_MAX_LINE_WORDS = 18


def _continue_open_table(memory: dict[Any, Any], page: pymupdf.Page, page_no: int, table_cfgs: list[dict[str, Any]],
                         words: list[Word], hsegs: list[Segment], vsegs: list[Segment], boundary_ys: list[float],
                         footer_y: float, ignore: list[str] | None = None) -> TableResult | None:
    """A table that is the last thing on a page goes on at the top of the next one without a title or header.
    Its rows are parsed with the column geometry of the table, appended to it, and the region is returned as a
    hidden stub so the prose engine does not print those rows again. Letterhead lines matching `ignore` are
    skipped. Only attempted when the first remaining line has a DWT-like number in the key column and is
    short; a prose paragraph never qualifies."""
    prev: TableResult | None = memory.get("_open")
    if prev is None or memory.get("_open_page") != page_no - 1:
        return None
    cfg = next((c for c in table_cfgs if c["name"] == prev.name), None)
    if cfg is None or not cfg.get("headerless_ok"):
        return None
    geo = memory.get(tuple(cfg["headers"]))
    if geo is None:
        return None
    skip = _ignored_word_ids(words, ignore)
    nxt = [y for y in boundary_ys if y > CONTINUATION_TOP + 6]
    limit = min([footer_y] + nxt)
    body = [w for w in words if w.y0 >= CONTINUATION_TOP and w.y1 <= limit + 1 and id(w) not in skip]
    if not body:
        return None
    top = max([CONTINUATION_TOP] + [w.y1 + 1 for w in words if id(w) in skip and w.y1 < min(b.y0 for b in body) + 1])
    first_y = min(w.y0 for w in body)
    first_line = [w for w in body if abs(w.y0 - first_y) <= 12]
    key = int(cfg.get("key_column", 0))
    kv = re.compile(cfg.get("key_value_pattern", KEY_VALUE_DEFAULT))
    if len(first_line) > CONTINUATION_MAX_LINE_WORDS or not any(
            geo["bounds"][key] <= w.cx < geo["bounds"][key + 1] and kv.match(w.text) for w in first_line):
        return None
    anchor = (geo["hx0"], top - 12, geo["hx1"], top - 2)
    res = extract_table(cfg, page, page_no, words, hsegs, vsegs, anchor, "", limit, memory, continuation=True)
    if res is None or res.empty or not res.rows:
        return None
    offset = len(prev.rows)
    prev.rows.extend(res.rows)
    prev.en_bloc_rows.extend(i + offset for i in res.en_bloc_rows)
    prev.row_meta.extend(res.row_meta)
    prev.unassigned_words += res.unassigned_words
    prev.shared_cell_count_mismatch += res.shared_cell_count_mismatch
    prev.extra_regions.append({"page": page_no, "bbox": [round(v, 2) for v in res.bbox]})
    res.hidden = True
    return res


# --------------------------------------------------------------------------- prose assembly
def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def region_tokens(words: list[Word], bbox: tuple[float, float, float, float]) -> set[str]:
    x0, y0, x1, y1 = bbox
    return {t for w in words if x0 - 1 <= w.cx <= x1 + 1 and y0 - 1 <= w.cy <= y1 + 1 for t in _tokens(w.text)}


def _block_y(toks: list[str], seq: list[tuple[str, float]]) -> float | None:
    """y of the first place in the PDF word stream where the block's leading tokens occur."""
    n = min(4, len(toks))
    if n == 0:
        return None
    head = toks[:n]
    for i in range(len(seq) - n + 1):
        if all(seq[i + k][0] == head[k] for k in range(n)):
            return seq[i][1]
    return None


def merge_prose_and_tables(md: str, tables: list[TableResult], words: list[Word], heading_level: int = 2) -> str:
    """Remove LiteParse blocks that come from table regions; insert geometric tables in reading order.

    A block is dropped when >= 80 % of its tokens occur inside a table region. A heading block that
    only partly overlaps (LiteParse fuses a section heading with the table title, e.g.
    "Demolition Bulk Carriers - GCs") is replaced by a heading made of its leftover words
    ("Demolition"). Each table is inserted before the first remaining block that starts below the
    table top (blocks keep LiteParse order, so multi-column prose is not reshuffled); tables
    below all prose go last."""
    blocks = [b for b in re.split(r"\n\s*\n", md.strip()) if b.strip()]
    regions = [region_tokens(words, t.bbox) for t in tables]
    seq = [(t, w.y0) for w in words for t in _tokens(w.text)]
    kept: list[tuple[str, float | None]] = []
    for block in blocks:
        toks = _tokens(block)
        if not toks:
            kept.append((block, None))
            continue
        is_heading = block.lstrip().startswith("#")
        best, best_hit = None, 0
        for ti, reg in enumerate(regions):
            hit = sum(1 for t in toks if t in reg)
            if hit > best_hit:
                best, best_hit = ti, hit
        ratio = best_hit / len(toks)
        if best is not None and (ratio >= 0.8 or (is_heading and ratio >= 0.5 and best_hit >= 2)):
            leftover = [w for w in re.findall(r"\S+", re.sub(r"^#+\s*", "", block))
                        if _tokens(w) and not all(t in regions[best] for t in _tokens(w))]
            if is_heading and leftover:
                level = len(block) - len(block.lstrip("#"))
                kept.append(("#" * max(level, 1) + " " + " ".join(leftover), _block_y(_tokens(" ".join(leftover)), seq)))
            continue
        kept.append((block, _block_y(toks, seq)))
    out: list[str] = []
    pending = sorted(range(len(tables)), key=lambda i: tables[i].bbox[1])
    for text, y in kept:
        if y is not None:
            while pending and tables[pending[0]].bbox[1] <= y:
                out.append(tables[pending.pop(0)].to_markdown(heading_level))
        out.append(text)
    out.extend(tables[i].to_markdown(heading_level) for i in pending)
    return "\n\n".join(out)
