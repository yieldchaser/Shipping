"""Prose extraction from the PDF text layer (engine `pymupdf_prose`).

PyMuPDF `get_text("dict")` blocks -> lines -> spans. Lines are grouped into paragraphs by vertical
gaps; inline bold stays inline (`**bold**`) and never starts a new line. Headings are single short
lines that are larger than the body text or entirely bold. Multi-column pages are read column by
column. Table bboxes, dropped regions and repeated header/footer bands are excluded.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pymupdf

BAND_FRACTION = 0.06
HEADING_MAX_WORDS = 8
HEADING_SIZE_DELTA = 1.5
GAP_FACTOR = 0.45          # vertical gap (x font size) that separates paragraphs
TERMINAL = ".!?:)\"'’”"


@dataclass
class Line:
    text: str            # markdown text of the line (inline bold already applied)
    plain: str
    bbox: tuple[float, float, float, float]
    size: float
    all_bold: bool
    any_bold: bool
    tail_normal: bool    # bold text followed on the same line by normal text


@dataclass
class Para:
    lines: list[Line]
    page: int
    heading: int = 0     # 0 = paragraph, else markdown level
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    text: str = ""
    column: int = -1     # -1 = full width / single column
    full_width: bool = False

    @property
    def y0(self) -> float:
        return self.bbox[1]


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _line_from_dict(line: dict) -> Line | None:
    spans = [s for s in line["spans"] if s["text"] != ""]
    plain = "".join(s["text"] for s in spans)
    if not plain.strip():
        return None
    ink = [s for s in spans if s["text"].strip()]
    bold_flags = [_is_bold(s) for s in ink]
    all_bold, any_bold = all(bold_flags), any(bold_flags)
    # markdown with inline bold; whitespace is kept outside the markers
    parts: list[str] = []
    cur_bold, buf = False, ""

    def flush():
        nonlocal buf
        if buf:
            if cur_bold:
                core = buf.strip()
                lead = buf[: len(buf) - len(buf.lstrip())]
                trail = buf[len(buf.rstrip()):]
                parts.append(f"{lead}**{core}**{trail}" if core else buf)
            else:
                parts.append(buf)
            buf = ""

    for s in spans:
        b = _is_bold(s) if s["text"].strip() else cur_bold
        if b != cur_bold:
            flush()
            cur_bold = b
        buf += s["text"]
    flush()
    md = "".join(parts).replace(" ", " ")
    md = re.sub(r"\*\*\s*\*\*", " ", md)
    sizes = [round(s["size"], 1) for s in ink]
    tail_normal = False
    seen_bold = False
    for s, b in zip(ink, bold_flags):
        if b:
            seen_bold = True
        elif seen_bold:
            tail_normal = True
    x0, y0, x1, y1 = line["bbox"]
    return Line(re.sub(r"\s+", " ", md).strip(), re.sub(r"\s+", " ", plain).strip(), (x0, y0, x1, y1),
                max(sizes), all_bold, any_bold, tail_normal)


def _norm_band(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip().lower()))


def repeated_band_texts(doc: pymupdf.Document) -> set[str]:
    """Normalised texts occurring in the top/bottom band on at least two pages."""
    counts: Counter = Counter()
    for page in doc:
        h = page.rect.height
        seen = set()
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for ln in b["lines"]:
                y0, y1 = ln["bbox"][1], ln["bbox"][3]
                if y1 < BAND_FRACTION * h or y0 > (1 - BAND_FRACTION) * h:
                    t = _norm_band("".join(s["text"] for s in ln["spans"]))
                    if t:
                        seen.add(t)
        counts.update(seen)
    return {t for t, n in counts.items() if n >= 2}


def body_font_size(doc: pymupdf.Document, pages: list[int]) -> float:
    c: Counter = Counter()
    for p in pages:
        for b in doc[p - 1].get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for ln in b["lines"]:
                for s in ln["spans"]:
                    if s["text"].strip():
                        c[round(s["size"], 1)] += len(s["text"].strip())
    return c.most_common(1)[0][0] if c else 10.0


BLOCK_END_MAX_GAP = 8.0


def _anchor_rects(page: pymupdf.Page, rule: dict[str, Any]) -> list[pymupdf.Rect]:
    """Rects of the anchors. With `line_start: true` an anchor only counts when a text line begins with
    it (case-sensitive, and at most `max_line_chars` long when given), so prose that merely mentions
    "exchange rate" or "disclaimer" never starts a dropped region."""
    anchors = rule.get("anchor_any", [])
    if not rule.get("line_start"):
        return [r for a in anchors for r in page.search_for(a)]
    max_chars = rule.get("max_line_chars")
    lines: dict[tuple[int, int], list[tuple]] = {}
    for w in page.get_text("words"):
        lines.setdefault((w[5], w[6]), []).append(w)
    rects = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in ws)
        if max_chars and len(text) > max_chars:
            continue
        if any(text.startswith(a) for a in anchors):
            rects.append(pymupdf.Rect(min(w[0] for w in ws), min(w[1] for w in ws),
                                      max(w[2] for w in ws), max(w[3] for w in ws)))
    return rects


def drop_region_boxes(page: pymupdf.Page, rules: list[dict[str, Any]] | None) -> list[tuple[float, float, float, float]]:
    """`drop_regions: [{anchor_any: [...], until: page_end | block_end}]` -> full-width boxes.

    The box starts at the top of the first anchor found. `page_end` runs to the bottom of the page;
    `block_end` runs through the contiguous run of text lines below the anchor (vertical gap <= 8 pt),
    which cuts a contacts/disclaimer block that sits mid-page without eating the text after it."""
    boxes = []
    words = None
    for rule in rules or []:
        rects = _anchor_rects(page, rule)
        if not rects:
            continue
        top = min(r.y0 for r in rects) - 2
        bottom = float(page.rect.height)
        if rule.get("until") == "block_end":
            if words is None:
                words = sorted((w[1], w[3]) for w in page.get_text("words"))
            # anchors within 30 pt of the first one belong to the same block (heading + first text line)
            bottom = max(r.y1 for r in rects if r.y0 < top + 32)
            for y0, y1 in words:
                if y1 < top:
                    continue
                if y0 - bottom > BLOCK_END_MAX_GAP:
                    break
                bottom = max(bottom, y1)
            bottom += 1
        boxes.append((0.0, top, float(page.rect.width), bottom))
    return boxes


def _inside(bbox, box, frac: float = 0.5) -> bool:
    x0, y0, x1, y1 = bbox
    bx0, by0, bx1, by1 = box
    ix = max(0.0, min(x1, bx1) - max(x0, bx0))
    iy = max(0.0, min(y1, by1) - max(y0, by0))
    area = max((x1 - x0) * (y1 - y0), 1e-6)
    return ix * iy / area >= frac


def _raw_paragraphs(page: pymupdf.Page, page_no: int, exclude: list[tuple[float, float, float, float]],
                    repeated: set[str], body: float) -> list[Para]:
    h = page.rect.height
    lines: list[tuple[int, Line]] = []
    for bi, b in enumerate(page.get_text("dict")["blocks"]):
        if b["type"] != 0:
            continue
        for ln in b["lines"]:
            line = _line_from_dict(ln)
            if line is None:
                continue
            if any(_inside(line.bbox, box) for box in exclude):
                continue
            in_band = line.bbox[3] < BAND_FRACTION * h or line.bbox[1] > (1 - BAND_FRACTION) * h
            if in_band and (_norm_band(line.plain) in repeated or re.fullmatch(r"(page\s+)?\d{1,3}", line.plain.lower())):
                continue
            lines.append((bi, line))
    # same-row fragments (e.g. a bold lead-in and its text in separate lines/blocks) are merged
    lines.sort(key=lambda t: (round(t[1].bbox[1] / 2), t[1].bbox[0]))
    paras: list[Para] = []
    cur: list[Line] = []

    def close():
        nonlocal cur
        if cur:
            x0 = min(l.bbox[0] for l in cur)
            y0 = min(l.bbox[1] for l in cur)
            x1 = max(l.bbox[2] for l in cur)
            y1 = max(l.bbox[3] for l in cur)
            paras.append(Para(cur, page_no, bbox=(x0, y0, x1, y1)))
            cur = []

    # columns interleave in y order, so group by block first (blocks are column-local in these PDFs)
    by_block: dict[int, list[Line]] = {}
    for bi, ln in lines:
        by_block.setdefault(bi, []).append(ln)
    for bi in sorted(by_block, key=lambda k: (min(l.bbox[1] for l in by_block[k]), min(l.bbox[0] for l in by_block[k]))):
        prev: Line | None = None
        for ln in sorted(by_block[bi], key=lambda l: (l.bbox[1], l.bbox[0])):
            if prev is not None:
                same_row = abs(ln.bbox[1] - prev.bbox[1]) < 2 and ln.bbox[0] > prev.bbox[2] - 1
                gap = ln.bbox[1] - prev.bbox[3]
                size_break = (ln.size >= body + HEADING_SIZE_DELTA) != (prev.size >= body + HEADING_SIZE_DELTA)
                if not same_row and (gap > GAP_FACTOR * max(ln.size, prev.size) or size_break):
                    close()
            cur.append(ln)
            prev = ln
        close()
    return paras


def _glue(out: str, nxt: str) -> str:
    """Join two consecutive text pieces; a line-end hyphen is removed only when the joined word is
    alphabetic and the continuation starts in lower case (scrub-/ber -> scrubber)."""
    if out.endswith("-") and nxt[:1].isalpha():
        prev_tok = re.split(r"\s+", out)[-1]
        next_tok = nxt.split(" ")[0]
        if re.fullmatch(r"[A-Za-z]+-", prev_tok) and next_tok[:1].islower()                 and re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*[,.;:]?", next_tok):
            return out[:-1] + nxt          # soft hyphen
        return out + nxt                    # 7S50MC-/C7.1 or Sub-/Continent: hyphen stays, no space
    return out + " " + nxt


def _join_lines(lines: list[Line]) -> str:
    out = lines[0].text
    for ln in lines[1:]:
        out = _glue(out, ln.text)
    return re.sub(r"\*\*\s*\*\*", " ", re.sub(r"\s+", " ", out)).strip()


def _classify(paras: list[Para], body: float) -> None:
    for p in paras:
        p.text = _join_lines(p.lines)
        if len(p.lines) == 1:
            ln = p.lines[0]
            words = len(ln.plain.split())
            big = ln.size >= body + HEADING_SIZE_DELTA
            bold_only = ln.all_bold and not ln.tail_normal
            if words <= HEADING_MAX_WORDS and (big or bold_only):
                p.heading = 1  # level assigned later from relative size
                p.text = ln.plain


def _detect_columns(paras: list[Para], page_width: float) -> None:
    """x-cluster the left edges of narrow paragraphs; mark column index / full-width paragraphs."""
    if not paras:
        return
    narrow = [p for p in paras if (p.bbox[2] - p.bbox[0]) < 0.62 * page_width]
    lefts = sorted({round(p.bbox[0]) for p in narrow})
    if len(narrow) < 4 or len(lefts) < 2:
        return
    clusters: list[list[float]] = [[lefts[0]]]
    for x in lefts[1:]:
        if x - clusters[-1][-1] > 0.2 * page_width:
            clusters.append([x])
        else:
            clusters[-1].append(x)
    clusters = [c for c in clusters if sum(1 for p in narrow if min(c) - 8 <= p.bbox[0] <= max(c) + 8) >= 2]
    if len(clusters) < 2:
        return
    starts = [min(c) for c in clusters]
    for p in paras:
        if (p.bbox[2] - p.bbox[0]) >= 0.62 * page_width:
            p.full_width = True
            continue
        p.column = max(i for i, s in enumerate(starts) if p.bbox[0] >= s - 8) if p.bbox[0] >= starts[0] - 8 else 0


def page_prose(page: pymupdf.Page, page_no: int, exclude: list[tuple[float, float, float, float]],
               repeated: set[str], body: float) -> list[Para]:
    paras = _raw_paragraphs(page, page_no, exclude, repeated, body)
    _classify(paras, body)
    _detect_columns(paras, page.rect.width)
    return paras


def assign_heading_levels(paras: list[Para], body: float) -> None:
    sizes = sorted({max(l.size for l in p.lines) for p in paras if p.heading and max(l.size for l in p.lines) >= body + HEADING_SIZE_DELTA},
                   reverse=True)
    top = sizes[0] if sizes else None
    for p in paras:
        if p.heading:
            size = max(l.size for l in p.lines)
            p.heading = 1 if top is not None and size >= top - 0.2 and size >= body + HEADING_SIZE_DELTA else 2


def order_items(paras: list[Para], tables: list[Any]) -> list[tuple[str, Any]]:
    """Reading order of paragraphs and tables on one page. Tables (and full-width paragraphs, when the
    page has columns) are separators; narrow paragraphs between separators are read column by column."""
    seps: list[tuple[float, str, Any]] = [(t.bbox[1], "table", t) for t in tables]
    columned = any(p.column >= 0 for p in paras)
    singles: list[Para] = []
    for p in paras:
        if columned and p.full_width:
            seps.append((p.y0, "para", p))
        elif columned:
            singles.append(p)
        else:
            seps.append((p.y0, "para", p))
    seps.sort(key=lambda s: s[0])
    out: list[tuple[str, Any]] = []
    bands: dict[int, list[Para]] = {}
    for p in singles:
        k = sum(1 for s in seps if s[0] <= p.y0 + 1)
        bands.setdefault(k, []).append(p)

    def flush(k: int) -> None:
        for p in sorted(bands.pop(k, []), key=lambda p: (p.column, p.y0)):
            out.append(("para", p))

    flush(0)
    for i, (_, kind, obj) in enumerate(seps):
        out.append((kind, obj))
        flush(i + 1)
    for k in sorted(bands):
        flush(k)
    return out


def render(items: list[tuple[str, Any]], table_heading_level: int = 2) -> str:
    """Paragraphs/tables -> markdown. A paragraph that stops without terminal punctuation and is
    continued by a lower-case paragraph (column or page flow) is joined to it."""
    blocks: list[tuple[str, str]] = []   # (kind, text)
    for kind, obj in items:
        if kind == "table":
            blocks.append(("table", obj.to_markdown(table_heading_level)))
        elif obj.heading:
            blocks.append(("heading", "#" * obj.heading + " " + obj.text))
        else:
            if blocks and blocks[-1][0] == "para" and _continues(blocks[-1][1], obj.text):
                blocks[-1] = ("para", _glue(blocks[-1][1], obj.text))
            else:
                blocks.append(("para", obj.text))
    return "\n\n".join(t for _, t in blocks)


def _continues(prev: str, nxt: str) -> bool:
    core = prev.rstrip("*_ ")
    first = re.sub(r"^[*_\s]+", "", nxt)
    return bool(core) and core[-1] not in TERMINAL and bool(first) and first[0].islower()
