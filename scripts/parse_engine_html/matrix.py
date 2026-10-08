"""OCR + grid reconstruction for the "VV Mini Matrix - Weekly Change" image.

Layout (all observed years): 6 age rows (0,5,10,15,20,25), 13 columns
  Tankers [VLCC Suez Afra LR1 MR] | Bulkers [Cape Pmax Supra Handy] | Containers [Post Pmax, Pmax, Handy, Fmax]
and every cell is two text lines: a coloured % change (green positive, red negative, black zero / N/A) and a grey
italic benchmark size underneath (320k, 7000, N/A).

Pipeline (free, local; RapidOCR = PP-OCR on ONNX runtime; no paid API is ever called)
  1. Text *detection* gives word boxes; reconstruct_grid() derives the 13 column centres and the 6 value/benchmark
     line pairs purely from box geometry (+ a "has coloured ink" flag). It is a pure function, unit-tested on
     synthetic boxes, and refuses (GridError) rather than guessing when the layout is not 13 x 6.
  2. Every cell is re-read from pixels: the value band and the benchmark band are cropped, contrast-enhanced and
     recognised in several render variants; a reading is accepted only when independent variants agree. The sign
     is taken from the text colour (green +, red -) because OCR engines routinely mis-read the tiny sign glyph.
  3. Each cell must match ^[+-]?\\d+(\\.\\d+)?%$ or N/A (benchmark ^\\d{2,4}k?$ or N/A); otherwise the image is
     reported as failed with the offending cells listed. No value is ever repaired or guessed.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from statistics import median

MATRIX_VERSION = "2.0.0"
GROUPS = ("Tankers", "Bulkers", "Containers")
COLUMNS: tuple[tuple[str, str], ...] = (
    ("Tankers", "VLCC"), ("Tankers", "Suez"), ("Tankers", "Afra"), ("Tankers", "LR1"), ("Tankers", "MR"),
    ("Bulkers", "Cape"), ("Bulkers", "Pmax"), ("Bulkers", "Supra"), ("Bulkers", "Handy"),
    ("Containers", "Post Pmax"), ("Containers", "Pmax"), ("Containers", "Handy"), ("Containers", "Fmax"),
)
AGES = (0, 5, 10, 15, 20, 25)
PCT_CELL_RE = re.compile(r"^[+-]?\d+(\.\d+)?%$|^N/A$")
REF_CELL_RE = re.compile(r"^(?:\d{2,3}k|\d{4}|N/A)$")
_IMG_DATE_RE = re.compile(r"(\d{1,2})\s*([A-Za-z]{3,9})\.?\s*(\d{4})")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


class GridError(Exception):
    """The word boxes do not form the expected matrix grid."""


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str = ""
    coloured: bool = False       # contains red/green ink (a percentage cell, never a header/benchmark)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@dataclass
class Grid:
    col_x: list[float]
    val_y: list[float]
    ref_y: list[float]
    col_pitch: float
    header_y: float | None = None
    title_boxes: list[Box] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.val_y)

    @property
    def n_cols(self) -> int:
        return len(self.col_x)


# ---------------------------------------------------------------------------------------------------
# geometry (pure)
# ---------------------------------------------------------------------------------------------------
def cluster_positions(values: list[float], n_groups: int | None = None) -> list[list[float]]:
    """1-D clustering: split where the gap between neighbours jumps (jitter inside a column is a few px, the
    spacing between columns is ~40+ px). If n_groups is given, GridError unless exactly that many come out."""
    vals = sorted(values)
    if len(vals) < 2:
        raise GridError("too few boxes to cluster")
    gaps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    order = sorted(gaps)
    best, thr = 0.0, None
    for lo, hi in zip(order, order[1:]):
        ratio = (hi + 1.0) / (lo + 1.0)
        if ratio > best and hi > 12:
            best, thr = ratio, (lo + hi) / 2
    if thr is None or best < 2.0:
        raise GridError("no clear column separation among word boxes")
    out: list[list[float]] = [[vals[0]]]
    for g, v in zip(gaps, vals[1:]):
        if g > thr:
            out.append([v])
        else:
            out[-1].append(v)
    if n_groups is not None and len(out) != n_groups:
        raise GridError(f"found {len(out)} column clusters, expected {n_groups}")
    return out


def reconstruct_grid(boxes: list[Box], n_cols: int = len(COLUMNS), n_rows: int = len(AGES)) -> Grid:
    """Derive column centres and the value/benchmark line of every row from word boxes (pure function)."""
    usable = [b for b in boxes if b.w >= 4 and b.h >= 3]
    if len(usable) < n_cols * 2:
        raise GridError(f"only {len(usable)} word boxes")
    med_h = median(b.h for b in usable)
    tol = max(2.5, 0.3 * med_h)

    ys = sorted(usable, key=lambda b: b.cy)
    lines: list[list[Box]] = [[ys[0]]]
    for b in ys[1:]:
        if b.cy - median(x.cy for x in lines[-1]) > tol:
            lines.append([b])
        else:
            lines[-1].append(b)
    min_members = max(4, n_cols // 2)
    data_lines = [ln for ln in lines if len(ln) >= min_members]
    if not data_lines:
        raise GridError("no text line with enough boxes")
    # merged boxes (two cells glued by the detector) distort column centres: drop them from the geometry
    wid = median(b.w for ln in data_lines for b in ln)
    data_lines = [[b for b in ln if b.w <= 1.7 * wid] for ln in data_lines]

    header_y = None
    if len(data_lines) == 2 * n_rows + 1:
        if any(b.coloured for b in data_lines[0]):
            raise GridError("first text line carries coloured ink but should be the header")
        header_y = median(b.cy for b in data_lines[0])
        body = data_lines[1:]
    elif len(data_lines) == 2 * n_rows:
        body = data_lines
    else:
        raise GridError(f"{len(data_lines)} text lines with >= {min_members} boxes, expected {2 * n_rows} (+1 header)")
    val_lines, ref_lines = body[0::2], body[1::2]
    for k, (v, r) in enumerate(zip(val_lines, ref_lines)):
        if any(b.coloured for b in r):
            raise GridError(f"benchmark line {k} contains coloured ink: line pairing is off")
    if not any(b.coloured for b in val_lines[0]):
        raise GridError("first percentage line has no coloured ink: line pairing is off")
    if sum(any(b.coloured for b in v) for v in val_lines) < n_rows - 1:
        raise GridError("percentage lines without coloured ink: line pairing is off")

    cxs = [b.cx for ln in body for b in ln]
    clusters = [c for c in cluster_positions(cxs) if len(c) >= max(4, len(body) // 2)]
    if len(clusters) != n_cols:
        raise GridError(f"found {len(clusters)} populated columns, expected {n_cols}")
    col_x = [sum(c) / len(c) for c in clusters]
    col_pitch = median(b - a for a, b in zip(col_x, col_x[1:]))
    val_y = [median(b.cy for b in ln) for ln in val_lines]
    ref_y = [median(b.cy for b in ln) for ln in ref_lines]
    if not all(v < r for v, r in zip(val_y, ref_y)):
        raise GridError("benchmark lines are not below their percentage lines")
    top = header_y if header_y is not None else val_y[0]
    title = [b for b in boxes if b.cy < top - 6]
    return Grid(col_x=col_x, val_y=val_y, ref_y=ref_y, col_pitch=col_pitch, header_y=header_y, title_boxes=title)


def parse_image_date(text: str) -> date | None:
    """'07 March 2023' -> date (the small label in the top-left corner)."""
    m = _IMG_DATE_RE.search(text)
    if m and m.group(2)[:3].lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------------------------------
# cell value normalisation (pure)
# ---------------------------------------------------------------------------------------------------
def normalise_pct(text: str, colour_sign: str, wide: bool = False) -> tuple[str | None, str]:
    """Recogniser text + sign colour -> ('+0.5%' | '-1.4%' | '0.0%' | 'N/A', note).

    The sign comes from the colour (green +, red -); a sign character in the text is only a cross-check. Nothing is
    repaired: a leading digit in front of a one-digit integer part ('11.3', '10.4') could be a mis-read '+' glyph,
    so it is accepted only when the ink is as wide as a genuine two-digit value (`wide`, measured from pixels) and
    rejected otherwise. A zero keeps its minus only when the recognised text carries one ('-0.0%' is printed in some
    images); the colour of a zero is neutral, so there is no colour to take it from.
    """
    t = text.replace(" ", "").replace(",", ".").upper()
    if t in ("N/A", "NA", "N/", "/A", "NVA", "N|A", "NIA"):
        return "N/A", ""
    m = re.fullmatch(r"([+\-−–*:$~])?(\d{1,2})\.(\d)%?", t)
    if not m:
        return None, f"unparseable {text!r}"
    glyph = m.group(1) or ""
    text_sign = {"+": "+", "-": "-", "−": "-", "–": "-"}.get(glyph, "")
    if text_sign and colour_sign and text_sign != colour_sign:
        return None, f"sign text {text_sign!r} vs colour {colour_sign!r}"
    integer = m.group(2)
    if len(integer) == 2 and not glyph and colour_sign and integer[0] in "147" and not wide:
        return None, "ambiguous leading digit (possible mis-read sign glyph)"
    if float(f"{integer}.{m.group(3)}") == 0.0:
        return ("-0.0%" if text_sign == "-" else "0.0%"), ""
    sign = colour_sign or text_sign
    return f"{sign}{integer}.{m.group(3)}%", ""


def normalise_ref(text: str) -> str | None:
    t = text.replace(" ", "").replace(",", "")
    if t.upper() in ("N/A", "NA", "NVA", "N|A"):
        return "N/A"
    m = re.fullmatch(r"(\d{2,3})[kK]|(\d{4})", t)
    if not m:
        return None
    return f"{m.group(1)}k" if m.group(1) else m.group(2)


def ref_value(ref_text: str) -> int | None:
    if ref_text == "N/A":
        return None
    return int(ref_text[:-1]) * 1000 if ref_text.endswith("k") else int(ref_text)


# Plausible benchmark-size range per column (a range check only: a reading outside it is dropped, never repaired).
REF_RANGES: dict[tuple[str, str], tuple[int, int]] = {
    ("Tankers", "VLCC"): (280_000, 330_000), ("Tankers", "Suez"): (140_000, 170_000),
    ("Tankers", "Afra"): (95_000, 125_000), ("Tankers", "LR1"): (60_000, 85_000),
    ("Tankers", "MR"): (40_000, 55_000),
    ("Bulkers", "Cape"): (150_000, 190_000), ("Bulkers", "Pmax"): (70_000, 90_000),
    ("Bulkers", "Supra"): (45_000, 70_000), ("Bulkers", "Handy"): (25_000, 42_000),
    ("Containers", "Post Pmax"): (4_500, 10_000), ("Containers", "Pmax"): (3_000, 5_500),
    ("Containers", "Handy"): (1_400, 2_200), ("Containers", "Fmax"): (800, 1_300),
}


def ref_in_range(group: str, column: str, ref_text: str) -> bool:
    if ref_text == "N/A":
        return True
    lo, hi = REF_RANGES[(group, column)]
    return lo <= (ref_value(ref_text) or 0) <= hi


def vote(candidates: list[str]) -> tuple[str | None, str]:
    """Accept the most common valid reading only if it has >= 2 votes and is at least 2 votes ahead of the runner-up.
    The reason never contains the rejected readings (they go to the sidecar only)."""
    if not candidates:
        return None, "no valid reading"
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top, n = ranked[0]
    if n < 2:
        return None, "no agreement between renders"
    if len(ranked) > 1 and n - ranked[1][1] < 2:
        return None, "readings disagree (winner not 2 votes ahead)"
    return top, ""


@dataclass
class BandRead:
    """Raw recogniser output for one text band (value or benchmark line of one cell); decisions are re-derivable."""
    age: int
    group: str
    column: str
    kind: str                       # val | ref
    sign: str = ""                  # colour sign of the value band
    wide: bool = False              # ink as wide as a two-digit value
    reads: list[list] = field(default_factory=list)      # [variant, scale, text]


@dataclass
class Cell:
    age: int
    group: str
    column: str
    pct_text: str = ""
    pct: float | None = None
    ref_text: str = ""
    ref_size: int | None = None
    raw_val: list[str] = field(default_factory=list)     # raw OCR reads: sidecar only, never in the MD
    raw_ref: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)    # value problems: make the image fail
    notes: list[str] = field(default_factory=list)       # benchmark problems: reported, benchmark left blank


@dataclass
class MatrixResult:
    status: str                    # ok | failed
    image: str
    image_sha256: str
    image_date: str | None = None
    n_rows: int = 0
    n_cols: int = 0
    cells: list[Cell] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bands: list[BandRead] = field(default_factory=list)
    date_reads: list[str] = field(default_factory=list)
    date_v: int = 0                 # version of the date-label reader that produced date_reads

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "MatrixResult":
        return MatrixResult(**{**d, "cells": [Cell(**c) for c in d.get("cells", [])],
                               "bands": [BandRead(**b) for b in d.get("bands", [])]})


# ---------------------------------------------------------------------------------------------------
# OCR engine + pixel reading (heavy imports are lazy so the pure functions stay importable without them)
# ---------------------------------------------------------------------------------------------------
_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        import os
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(var, "1")        # several worker processes: avoid thread oversubscription
        import cv2
        cv2.setNumThreads(1)
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    return _ENGINE


def _ink_mask(win):
    """Ink = noticeably darker than the (white / pale grey) background, or strongly coloured."""
    w = win.astype(int)
    return (w.min(axis=2) < 190) | ((w.max(axis=2) - w.min(axis=2)) > 70)


def _colour_sign(win, ink) -> str:
    """'+' green, '-' red, '' neutral (black / grey)."""
    w = win.astype(int)
    r, g, b = w[..., 0], w[..., 1], w[..., 2]
    nr = int((ink & (r > g + 60) & (r > b + 60)).sum())
    ng = int((ink & (g > r + 40) & (g > b + 25)).sum())
    if max(nr, ng) < 3:
        return ""
    return "-" if nr > ng else "+"


def detect_boxes(rgb) -> list[Box]:
    """Text detection only (about 2 s per image); each box is tagged with whether it holds coloured ink."""
    res, _ = get_engine()(rgb, use_det=True, use_cls=False, use_rec=False)
    out: list[Box] = []
    H, W = rgb.shape[:2]
    for pts in res or []:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        b = Box(min(xs), min(ys), max(xs), max(ys))
        ya, yb = max(int(b.y0), 0), min(int(b.y1) + 1, H)
        xa, xb = max(int(b.x0), 0), min(int(b.x1) + 1, W)
        win = rgb[ya:yb, xa:xb]
        if win.size:
            w = win.astype(int)
            r, g, bl = w[..., 0], w[..., 1], w[..., 2]
            n = int(((r > g + 60) & (r > bl + 60)).sum() + ((g > r + 40) & (g > bl + 25)).sum())
            b.coloured = n >= 3
        out.append(b)
    return out


def _render(band, variant: str, scale: int):
    """White-background 3-channel crop of the ink inside a band, upscaled for the recogniser."""
    import numpy as np
    from PIL import Image, ImageFilter
    ink = _ink_mask(band)
    ys, xs = np.where(ink)
    if len(xs) == 0:
        return None
    x0, x1 = max(xs.min() - 2, 0), min(xs.max() + 3, band.shape[1])
    y0, y1 = max(ys.min() - 2, 0), min(ys.max() + 3, band.shape[0])
    g = band.min(axis=2).astype("float")[y0:y1, x0:x1]
    if variant != "raw":
        lo = float(g.min())
        g = np.clip((g - lo) / max(200.0 - lo, 1.0), 0, 1) * 255
    else:
        g = np.where(g > 215, 255, g)
    im = Image.fromarray(g.astype("uint8")).resize((g.shape[1] * scale, g.shape[0] * scale), Image.LANCZOS)
    if variant == "thick":
        im = im.filter(ImageFilter.MinFilter(3))
    elif variant == "soft":
        im = im.filter(ImageFilter.GaussianBlur(1.0))
    pad = Image.new("L", (im.width + 16, im.height + 16), 255)
    pad.paste(im, (8, 8))
    return np.stack([np.asarray(pad)] * 3, axis=-1)


# (variant, scale): the first pair always runs, the rest only for cells whose first readings fail or disagree
def _np():
    import numpy
    return numpy


PASS1_VAL = (("raw", 5), ("stretch", 5))                 # a value needs two agreeing renders
PASS1_REF = (("raw", 5), ("raw", 4))                   # so does a benchmark size (more renders only on disagreement)
PASS2 = (("raw", 4), ("stretch", 6), ("raw", 3))
PASS3 = (("stretch", 4), ("thick", 4), ("soft", 3), ("raw", 7), ("stretch", 6))
DATE_PLAN = (("raw", 3), ("raw", 4), ("raw", 5), ("raw", 6), ("stretch", 3), ("stretch", 4), ("stretch", 5),
             ("stretch", 6), ("thick", 4), ("thick", 5), ("soft", 4), ("soft", 5))
DATE_V = 2
RAW_SCHEMA = "raw2"          # cache key: the stored raw recogniser output; policy changes never need a re-OCR


def _rec(images) -> list[str]:
    if not images:
        return []
    res, _ = get_engine().text_rec(images)
    return [str(t) for t, _c in res]


def decide_band(br: BandRead) -> tuple[str | None, str]:
    """Policy: >= 2 agreeing renders (strictly the most common) and, for sizes, inside the column's plausible range."""
    texts = [r[2] for r in br.reads]
    if br.kind == "val":
        cands = [v for v, _n in (normalise_pct(t, br.sign, br.wide) for t in texts) if v]
        top, why = vote([("0.0%" if v == "-0.0%" else v) for v in cands])
        if top is not None and top != "N/A" and top[0] not in "+-" and float(top[:-1]) != 0.0:
            return None, "non-zero value with neutral colour (sign unresolved)"
        if top in ("0.0%", "-0.0%"):
            # a dropped minus glyph is far likelier than an invented one: keep it when >= 2 renders show it
            zeros = [v for v in cands if v in ("0.0%", "-0.0%")]
            neg = sum(1 for v in zeros if v == "-0.0%")
            top = "-0.0%" if neg >= 2 and neg * 2 > len(zeros) else "0.0%"
        return top, why
    cands = [v for v in (normalise_ref(t) for t in texts) if v]
    top, why = vote(cands)
    if top is not None and not ref_in_range(br.group, br.column, top):
        return None, "agreed reading is outside the plausible range"
    return top, why


def collect_reads(rgb, grid: Grid) -> list[BandRead]:
    """OCR every value band and benchmark band of the grid, escalating to more render variants only for bands the
    policy cannot decide yet."""
    H, W = rgb.shape[:2]
    half = grid.col_pitch / 2 - 2
    gap = grid.ref_y[0] - grid.val_y[0]
    pix: list = []
    bands: list[BandRead] = []
    widths: dict[int, int] = {}
    for r, age in enumerate(AGES[:grid.n_rows]):
        for c, (grp, col) in enumerate(COLUMNS[:grid.n_cols]):
            xa, xb = int(max(grid.col_x[c] - half, 0)), int(min(grid.col_x[c] + half, W))
            for kind, yc in (("val", grid.val_y[r]), ("ref", grid.ref_y[r])):
                ya, yb = int(max(yc - gap * 0.5, 0)), int(min(yc + gap * 0.5, H))
                band = rgb[ya:yb, xa:xb]
                ink = _ink_mask(band)
                sign = _colour_sign(band, ink) if kind == "val" else ""
                br = BandRead(age, grp, col, kind, sign)
                bands.append(br)
                pix.append(band)
                if kind == "val" and sign:
                    xs = _np().where(ink.any(axis=0))[0]
                    if len(xs):
                        widths[len(bands) - 1] = int(xs.max() - xs.min() + 1)
    med_w = median(widths.values()) if widths else 0
    for bi, w in widths.items():
        bands[bi].wide = w >= 1.09 * med_w

    def read(todo: list[int], plan) -> None:
        jobs = []
        for bi in todo:
            for variant, scale in plan:
                img = _render(pix[bi], variant, scale)
                if img is not None:
                    jobs.append((bi, variant, scale, img))
        for (bi, variant, scale, _img), text in zip(jobs, _rec([j[3] for j in jobs])):
            bands[bi].reads.append([variant, scale, text])

    read([i for i, b in enumerate(bands) if b.kind == "val"], PASS1_VAL)
    read([i for i, b in enumerate(bands) if b.kind == "ref"], PASS1_REF)
    for plan in (PASS2, PASS3):
        redo = [i for i, b in enumerate(bands) if decide_band(b)[0] is None]
        if not redo:
            break
        read(redo, plan)
    return bands


def cells_from_bands(bands: list[BandRead]) -> list[Cell]:
    by = {(b.age, b.group, b.column, b.kind): b for b in bands}
    cells: list[Cell] = []
    for age in sorted({b.age for b in bands}):
        for grp, col in COLUMNS:
            vb, rb = by.get((age, grp, col, "val")), by.get((age, grp, col, "ref"))
            if vb is None or rb is None:
                continue
            cell = Cell(age=age, group=grp, column=col)
            if not vb.reads:
                cell.problems.append("no value glyphs")
            else:
                top, why = decide_band(vb)
                if top is None:
                    cell.problems.append(f"value not read: {why}")
                    cell.raw_val = [r[2] for r in vb.reads]
                else:
                    cell.pct_text = top
                    cell.pct = None if top == "N/A" else float(top[:-1]) + 0.0
            if not rb.reads:
                cell.notes.append("no benchmark glyphs")
            else:
                top, why = decide_band(rb)
                if top is None:
                    cell.notes.append(f"benchmark left blank: {why}")
                    cell.raw_ref = [r[2] for r in rb.reads]
                else:
                    cell.ref_text = top
                    cell.ref_size = ref_value(top)
            cells.append(cell)
    return cells


def read_date_reads(rgb, grid: Grid) -> list[str]:
    """OCR the small date label above the table ('07 March 2023'): the small boxes at the top-left, many renders."""
    cands = [b for b in grid.title_boxes if b.w < 0.25 * rgb.shape[1] and b.h < 30 and b.x0 < 0.3 * rgb.shape[1]]
    texts: list[str] = []
    for b in sorted(cands, key=lambda b: (b.y0, b.x0))[:4]:
        crop = rgb[int(max(b.y0 - 2, 0)):int(b.y1 + 3), int(max(b.x0 - 2, 0)):int(b.x1 + 3)]
        imgs = [i for i in (_render(crop, v, s) for v, s in DATE_PLAN) if i is not None]
        texts += _rec(imgs)
    return texts


_DAY_RE = re.compile(r"^\W*(\d{1,2})(?!\d)")
_YEAR_RE = re.compile(r"(20[1-3]\d)(?!\d)")


def _field_winner(votes: list[int]) -> int | None:
    counts: dict[int, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < 2:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 2:
        return None
    return ranked[0][0]


def decide_date(texts: list[str]) -> str | None:
    """Day, month and year are each decided by agreement across the renders (>= 2 votes, >= 2 ahead): the tiny
    label usually loses a different field in each render ('17 June 7075' / '17 2025'). A year outside 2015-2035
    is an OCR error. Nothing is taken from the article date."""
    days, months, years = [], [], []
    for t in texts:
        dm = _DAY_RE.match(t)
        if dm and 1 <= int(dm.group(1)) <= 31:
            days.append(int(dm.group(1)))
        for w in re.findall(r"[A-Za-z]{3,9}", t):
            if w[:3].lower() in _MONTHS:
                months.append(_MONTHS[w[:3].lower()])
                break
        ym = _YEAR_RE.search(t)
        if ym:
            years.append(int(ym.group(1)))
    d, m, y = _field_winner(days), _field_winner(months), _field_winner(years)
    if d is None or m is None or y is None:
        return None
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def validate_cells(cells: list[Cell]) -> list[str]:
    errs: list[str] = []
    for c in cells:
        tag = f"age {c.age} {c.group}/{c.column}"
        errs += [f"{tag}: {p}" for p in c.problems]
        if c.pct_text and not PCT_CELL_RE.match(c.pct_text):
            errs.append(f"{tag}: value {c.pct_text!r} fails pattern")
        if c.ref_text and not REF_CELL_RE.match(c.ref_text):
            errs.append(f"{tag}: benchmark {c.ref_text!r} fails pattern")
        if not c.pct_text and not c.problems:
            errs.append(f"{tag}: empty value")
    return errs


def stale_by_whole_weeks(image_date: str, article_date: str, max_weeks: int = 2) -> bool:
    """A genuinely stale image is the previous weeks' table: its label is the issue date -/+ 7k days. k is limited to 1-2: every
    28-day difference seen in the archive (2023-10-31 / 2026-03-31) was a day-digit misread, none a stale image."""
    delta = abs((date.fromisoformat(image_date) - date.fromisoformat(article_date)).days)
    return delta % 7 == 0 and 1 <= delta // 7 <= max_weeks


def finalize(res: MatrixResult, article_date: str | None = None) -> MatrixResult:
    """Apply the decision policy to the stored raw reads. An image is OK only if every percentage cell is read,
    and (when article_date is given) its date label equals the article date."""
    res.errors = [e for e in res.errors if e.startswith("grid:")]
    res.warnings = [w for w in res.warnings if "date label" not in w]
    if res.errors:
        res.status = "failed"
        return res
    res.image_date = decide_date(res.date_reads)
    res.cells = cells_from_bands(res.bands)
    res.errors = validate_cells(res.cells)
    if len(res.cells) != len(COLUMNS) * len(AGES):
        res.errors.append(f"only {len(res.cells)} of {len(COLUMNS) * len(AGES)} cells present")
    if article_date is not None and res.image_date is None:
        res.errors.append(f"image date label {res.image_date!r} could not be read")
    elif article_date is not None and res.image_date != article_date and not stale_by_whole_weeks(
            res.image_date, article_date):
        # a day/month/year digit misread looks exactly like this: never print such a date
        res.errors.append("date label unreliable: it differs from the issue date by something other than "
                          "1-2 whole weeks")
    elif article_date is not None and res.image_date != article_date:
        res.warnings.append(f"image date label {res.image_date} differs from the issue date {article_date}; "
                            "the table below is that of the image's own date")
    res.status = "ok" if not res.errors else "failed"
    return res


def _redo_date_reads(path: Path, res: MatrixResult) -> bool:
    """Re-read only the date label of a cached result written by an older label reader; True when it ran."""
    try:
        import numpy as np
        from PIL import Image
        rgb = np.asarray(Image.open(path).convert("RGB"))
        grid = reconstruct_grid(detect_boxes(rgb))
        res.date_reads = res.date_reads + read_date_reads(rgb, grid)
        res.date_v = DATE_V
        return True
    except Exception:
        return False


def parse_matrix_image(path: Path, cache_dir: Path | None = None, article_date: str | None = None) -> MatrixResult:
    """A genuine layout failure (GridError) is cached and reported as unreadable. An engine/import/IO failure is
    returned with status 'error', never cached and never rendered as unreadable: the caller shows 'not run' and
    retries on the next run."""
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    cache_file = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{sha[:24]}_{RAW_SCHEMA}.json"
        if cache_file.exists():
            res = MatrixResult.from_json(json.loads(cache_file.read_text(encoding="utf-8")))
            res.image = path.name
            if (res.date_v < DATE_V and not any(e.startswith("grid:") for e in res.errors)
                    and decide_date(res.date_reads) is None):
                if _redo_date_reads(path, res):
                    cache_file.write_text(json.dumps(res.to_json(), ensure_ascii=False), encoding="utf-8")
            return finalize(res, article_date)
    res = MatrixResult(status="failed", image=path.name, image_sha256=sha)
    try:
        import numpy as np
        from PIL import Image
        rgb = np.asarray(Image.open(path).convert("RGB"))
        grid = reconstruct_grid(detect_boxes(rgb))
        res.n_rows, res.n_cols = grid.n_rows, grid.n_cols
        res.date_reads = read_date_reads(rgb, grid)
        res.date_v = DATE_V
        res.bands = collect_reads(rgb, grid)
    except GridError as exc:
        res.errors.append(f"grid: {exc}")
    except Exception as exc:  # missing engine, unreadable file ...: not a verdict on the image
        return MatrixResult(status="error", image=path.name, image_sha256=sha,
                            errors=[f"engine: {type(exc).__name__}: {exc}"])
    if cache_file is not None:
        cache_file.write_text(json.dumps(res.to_json(), ensure_ascii=False), encoding="utf-8")
    return finalize(res, article_date)
