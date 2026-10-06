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

MATRIX_VERSION = "1.4.0"
GROUPS = ("Tankers", "Bulkers", "Containers")
COLUMNS: tuple[tuple[str, str], ...] = (
    ("Tankers", "VLCC"), ("Tankers", "Suez"), ("Tankers", "Afra"), ("Tankers", "LR1"), ("Tankers", "MR"),
    ("Bulkers", "Cape"), ("Bulkers", "Pmax"), ("Bulkers", "Supra"), ("Bulkers", "Handy"),
    ("Containers", "Post Pmax"), ("Containers", "Pmax"), ("Containers", "Handy"), ("Containers", "Fmax"),
)
AGES = (0, 5, 10, 15, 20, 25)
PCT_CELL_RE = re.compile(r"^[+-]?\d+(\.\d+)?%$|^N/A$")
REF_CELL_RE = re.compile(r"^(?:\d{2,4}k?|N/A)$")
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

    The sign comes from the colour (green +, red -). A sign character in the text is only a cross-check; a
    leading digit in front of a one-digit integer part ('11.3') is a mis-read '+' glyph unless the ink is as wide
    as a genuine two-digit value (`wide`, measured from pixels); the sign glyph is then dropped and the cell is
    reported with note 'sign_glyph_read_as_digit'.
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
    note = ""
    if len(integer) == 2 and not glyph and colour_sign and integer[0] in "147" and not wide:
        integer, note = integer[1], "sign_glyph_read_as_digit"
    sign = colour_sign or text_sign
    return f"{sign}{integer}.{m.group(3)}%", note


def normalise_ref(text: str) -> str | None:
    t = text.replace(" ", "").replace(",", "")
    if t.upper() in ("N/A", "NA", "NVA", "N|A"):
        return "N/A"
    m = re.fullmatch(r"(\d{2,4})([kK]?)", t)
    if not m:
        return None
    return m.group(1) + ("k" if m.group(2) else "")


def ref_value(ref_text: str) -> int | None:
    if ref_text == "N/A":
        return None
    return int(ref_text[:-1]) * 1000 if ref_text.endswith("k") else int(ref_text)


def vote(candidates: list[str]) -> tuple[str | None, str]:
    """Accept the most common valid reading only if it has >= 2 votes and strictly beats every other reading."""
    if not candidates:
        return None, "no valid reading"
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top, n = ranked[0]
    if n < 2:
        return None, f"no agreement between renders: {sorted(counts)}"
    if len(ranked) > 1 and ranked[1][1] == n:
        return None, f"tied readings: {sorted(counts)}"
    return top, ""


@dataclass
class Cell:
    age: int
    group: str
    column: str
    pct_text: str = ""
    pct: float | None = None
    ref_text: str = ""
    ref_size: int | None = None
    ref_reads: list[str] = field(default_factory=list)   # every valid benchmark reading (for lexicon decoding)
    problems: list[str] = field(default_factory=list)    # value problems: make the image fail
    notes: list[str] = field(default_factory=list)       # benchmark problems / repairs: reported, image stays ok


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

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "MatrixResult":
        return MatrixResult(**{**d, "cells": [Cell(**c) for c in d.get("cells", [])]})


# ---------------------------------------------------------------------------------------------------
# OCR engine + pixel reading (heavy imports are lazy so the pure functions stay importable without them)
# ---------------------------------------------------------------------------------------------------
_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
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
PASS1_VAL = (("raw", 5), ("stretch", 5))      # a value needs two agreeing renders
PASS1_REF = (("raw", 5),)                     # a benchmark is checked later against the lexicon
PASS2 = (("raw", 4), ("stretch", 5), ("raw", 3))
PASS3 = (("stretch", 4), ("thick", 4), ("soft", 3), ("raw", 7), ("stretch", 6))


def _np():
    import numpy
    return numpy


def _rec(images) -> list[str]:
    if not images:
        return []
    res, _ = get_engine().text_rec(images)
    return [str(t) for t, _c in res]


def read_cells(rgb, grid: Grid) -> list[Cell]:
    """Re-read every cell of the reconstructed grid from pixels (value band + benchmark band per cell)."""
    H, W = rgb.shape[:2]
    half = grid.col_pitch / 2 - 2
    gap = grid.ref_y[0] - grid.val_y[0]
    cells: list[Cell] = []
    bands: list[tuple[int, str, object, str]] = []      # (cell index, kind, band pixels, colour sign)
    ink_w: dict[int, int] = {}
    for r, age in enumerate(AGES[:grid.n_rows]):
        for c, (grp, col) in enumerate(COLUMNS[:grid.n_cols]):
            cell = Cell(age=age, group=grp, column=col)
            cells.append(cell)
            xa, xb = int(max(grid.col_x[c] - half, 0)), int(min(grid.col_x[c] + half, W))
            for kind, yc in (("val", grid.val_y[r]), ("ref", grid.ref_y[r])):
                ya, yb = int(max(yc - gap * 0.5, 0)), int(min(yc + gap * 0.5, H))
                band = rgb[ya:yb, xa:xb]
                sign = _colour_sign(band, _ink_mask(band)) if kind == "val" else ""
                bands.append((len(cells) - 1, kind, band, sign))
                if kind == "val" and sign:
                    xs = _np().where(_ink_mask(band).any(axis=0))[0]
                    if len(xs):
                        ink_w[len(bands) - 1] = int(xs.max() - xs.min() + 1)
    med_w = median(ink_w.values()) if ink_w else 0

    def read_all(todo: list[int], plan) -> dict[int, list[str]]:
        jobs = []
        for bi in todo:
            for variant, scale in plan:
                img = _render(bands[bi][2], variant, scale)
                if img is not None:
                    jobs.append((bi, img))
        texts = _rec([j[1] for j in jobs])
        out: dict[int, list[str]] = {bi: [] for bi in todo}
        for (bi, _img), t in zip(jobs, texts):
            out[bi].append(t)
        return out

    def interpret(bi: int, texts: list[str]) -> list[str]:
        _ci, kind, _band, sign = bands[bi]
        if kind == "val":
            wide = bi in ink_w and ink_w[bi] >= 1.09 * med_w
            return [v for v, _n in (normalise_pct(t, sign, wide) for t in texts) if v]
        return [v for v in (normalise_ref(t) for t in texts) if v]

    val_idx = [i for i, b in enumerate(bands) if b[1] == "val"]
    ref_idx = [i for i, b in enumerate(bands) if b[1] == "ref"]
    raw: dict[int, list[str]] = {**read_all(val_idx, PASS1_VAL), **read_all(ref_idx, PASS1_REF)}
    valid: dict[int, list[str]] = {bi: interpret(bi, raw[bi]) for bi in raw}
    for plan in (PASS2, PASS3):
        redo = [bi for bi in valid
                if (bands[bi][1] == "val" and vote(valid[bi])[0] is None)
                or (bands[bi][1] == "ref" and (not valid[bi] or (len(set(valid[bi])) > 1 and vote(valid[bi])[0] is None)))]
        if not redo:
            break
        extra = read_all(redo, plan)
        for bi in redo:
            raw[bi] += extra[bi]
            valid[bi] = interpret(bi, raw[bi])

    for bi, (ci, kind, _band, _sign) in enumerate(bands):
        cell = cells[ci]
        label = "value" if kind == "val" else "benchmark"
        if not raw.get(bi):
            cell.problems.append(f"no {label} glyphs")
            continue
        if kind == "ref":
            cell.ref_reads = list(valid[bi])
        top, why = (valid[bi][0], "") if kind == "ref" and len(valid[bi]) == 1 else vote(valid[bi])
        if top is None:
            (cell.problems if kind == "val" else cell.notes).append(f"{label} not read: {why}; raw={raw[bi]}")
            continue
        if kind == "val":
            if top != "N/A" and top[0] not in "+-" and float(top[:-1]) != 0.0:
                cell.problems.append(f"non-zero value {top} with neutral colour (sign unresolved)")
                continue
            cell.pct_text = top
            cell.pct = None if top == "N/A" else float(top[:-1])
        else:
            cell.ref_text = top
            cell.ref_size = ref_value(top)
    return cells


def read_date_label(rgb, grid: Grid) -> str | None:
    """OCR the small date label above the table ('07 March 2023') using the detected boxes left of the title."""
    cands = [b for b in grid.title_boxes if b.w < 0.25 * rgb.shape[1] and b.h < 30 and b.x0 < 0.3 * rgb.shape[1]]
    imgs = []
    for b in sorted(cands, key=lambda b: (b.x0, b.y0))[:4]:
        crop = rgb[int(max(b.y0 - 2, 0)):int(b.y1 + 3), int(max(b.x0 - 2, 0)):int(b.x1 + 3)]
        img = _render(crop, "raw", 5)
        if img is not None:
            imgs.append(img)
    for text in _rec(imgs):
        d = parse_image_date(text)
        if d:
            return d.isoformat()
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


def parse_matrix_image(path: Path, cache_dir: Path | None = None) -> MatrixResult:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    cache_file = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{sha[:24]}_v{MATRIX_VERSION}.json"
        if cache_file.exists():
            res = MatrixResult.from_json(json.loads(cache_file.read_text(encoding="utf-8")))
            res.image = path.name
            return res
    res = MatrixResult(status="failed", image=path.name, image_sha256=sha)
    try:
        import numpy as np
        from PIL import Image
        rgb = np.asarray(Image.open(path).convert("RGB"))
        grid = reconstruct_grid(detect_boxes(rgb))
        res.n_rows, res.n_cols = grid.n_rows, grid.n_cols
        res.image_date = read_date_label(rgb, grid)
        res.cells = read_cells(rgb, grid)
        res.errors = validate_cells(res.cells)
        res.status = "ok" if not res.errors else "failed"
    except GridError as exc:
        res.errors.append(f"grid: {exc}")
    except Exception as exc:  # unreadable image, engine failure ...
        res.errors.append(f"{type(exc).__name__}: {exc}")
    if cache_file is not None:
        cache_file.write_text(json.dumps(res.to_json(), ensure_ascii=False), encoding="utf-8")
    return res


def decode_refs(results: list[MatrixResult], min_count: int = 6) -> dict:
    """Benchmark sizes come from a small closed set per column (320k, 7000, ...). Italic grey digits are the
    weakest OCR target ('1' -> 'J', '7' -> '/'), so unresolved or rare readings are decoded against the lexicon
    of readings that the images themselves confirm with a clear vote: a cell takes a lexicon value only when its
    own render candidates contain exactly one lexicon value; otherwise the benchmark stays empty (never guessed)."""
    lex: dict[str, dict[str, int]] = {}
    for r in results:
        for c in r.cells:
            if c.ref_text:
                d = lex.setdefault(c.column + "|" + c.group, {})
                d[c.ref_text] = d.get(c.ref_text, 0) + 1
    stats = {"voted": 0, "lexicon_resolved": 0, "rare_dropped": 0, "unresolved": 0}
    for r in results:
        for c in r.cells:
            d = lex.get(c.column + "|" + c.group, {})
            common = {v for v, n in d.items() if n >= min_count}
            if c.ref_text and c.ref_text in common:
                stats["voted"] += 1
                continue
            cands = {v for v in c.ref_reads if v in common}
            had = c.ref_text
            c.ref_text, c.ref_size = "", None
            if len(cands) == 1:
                c.ref_text = next(iter(cands))
                c.ref_size = ref_value(c.ref_text)
                c.notes.append("benchmark resolved against lexicon")
                stats["lexicon_resolved"] += 1
            elif had:
                c.notes.append(f"benchmark {had} is rare for this column: dropped")
                stats["rare_dropped"] += 1
            else:
                stats["unresolved"] += 1
    return stats
