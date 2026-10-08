"""Best Oasis weekly ship-recycling report (digital PDF, three templates).

  A  2021 - early 2022: portrait, 7 pages. Cover + highlights, one page per recycling country (commentary and two
     bar charts), bunker chart + "List of vessels sold" table, contacts.
  B  2022 - 2025: landscape slides, 9 pages. Cover, summary, one page per country (commentary left, two bar charts
     right), bunker chart + Brent/WTI, vessel table, contacts.
  C  2025 - 2026: portrait, 4 pages. Cover, market summary (bullets per country), tide/other countries, and one page
     of tables (HMS/shredded prices, indicative prices, vessels sold) with the disclaimer.

The bar charts print their data labels as text, one label per bar above it and the category names below. They are
rebuilt as tables only when the geometry is unambiguous: every category cell holds exactly two labels (previous
week on the left, this week on the right, as the legend says). Otherwise the chart is reported as a `> Figure:` note
and no number is written. Tables are the ruled tables of the page (PyMuPDF find_tables). Nothing is estimated.
"""
from __future__ import annotations

import re
from typing import Any

import pymupdf

from scripts.parse_engine import prose
from scripts.parse_engine.xclusiv import fix_glyphs, render_table

CHART_TITLE_RE = re.compile(r"^(Price (?:for|of)\b|Bunker Prices\b)", re.I)
CAT_WORDS = {"container", "tanker", "bulker", "shredded", "houston", "rotterdam", "gibraltar", "malta",
             "fujairah", "singapore"}
VALUE_RE = re.compile(r"^\d{1,4}(?:\.\d+)?$")
NUMERIC_CELL_RE = re.compile(r"^(?:[\d,]+(?:\.\d+)?|\(\s*[+-]?\s*[\d.]+\s*\))$")
VESSEL_TITLE = "List of Vessels Sold This Week"
Y_TOL = 4.0


SECTION_RE = re.compile(r"(?i)^(india|bangladesh|pakistan|turkey|t.rkiye|turkiye|china|highlights|market summary|"
                        r"exchange rates|list of vessels|bunker prices|ship recycling|price of hms)")
RANGE_LINE_RE = re.compile(r"(?i)^\d{1,2}\s*(?:st|nd|rd|th)?\s+[a-z]+(?:\s+\d{4})?\s+to\s+\d")


def merge_split_sentences(paras: list[Any]) -> list[Any]:
    """Large-type announcement text is set with line gaps wider than the paragraph gap, so one sentence arrives as
    several paragraphs. A paragraph that stops without terminal punctuation and is continued, in the same type size
    and close below, by a paragraph starting in lower case (or after a line that runs to the margin) is joined to it."""
    out: list[Any] = []
    right = max((p.bbox[2] for p in paras), default=0.0)
    for q in sorted(paras, key=lambda p: (p.bbox[1], p.bbox[0])):
        p = out[-1] if out else None
        if p is not None:
            size_p, size_q = max(ln.size for ln in p.lines), max(ln.size for ln in q.lines)
            gap = q.bbox[1] - p.bbox[3]
            first = q.lines[0].plain.lstrip()
            full_line = p.lines[-1].bbox[2] >= 0.88 * right            # the line runs to the margin: the sentence goes on
            if (abs(size_p - size_q) <= 0.6 and p.lines[-1].plain.rstrip()[-1:] not in prose.TERMINAL
                    and ((first[:1].islower() and 0 <= gap < 2.2 * size_p)
                         or (full_line and abs(p.bbox[0] - q.bbox[0]) < 30 and 0 <= gap < 1.0 * size_p))):
                p.lines = p.lines + q.lines
                p.bbox = (min(p.bbox[0], q.bbox[0]), p.bbox[1], max(p.bbox[2], q.bbox[2]), q.bbox[3])
                p.heading = 0
                continue
        out.append(q)
    return out


def group_beaching(paras: list[Any]) -> list[Any]:
    """The 'Beaching Dates' label and the short lines printed under it (date ranges, 'Throughout the month') become one
    paragraph, so the label is not a repeated one-line block that the generic page-furniture cleaner would drop."""
    out: list[Any] = []
    ordered = sorted(paras, key=lambda p: (p.bbox[1], p.bbox[0]))
    i = 0
    while i < len(ordered):
        p = ordered[i]
        if re.match(r"(?i)beaching dates", p.lines[0].plain) and len(p.lines) == 1:
            items, last, j = [], p, i + 1
            while (j < len(ordered) and not ordered[j].heading and len(ordered[j].lines) <= 2
                   and ordered[j].bbox[1] - last.bbox[3] < 30 and len(" ".join(ln.plain for ln in ordered[j].lines)) < 60
                   and abs(ordered[j].bbox[0] - p.bbox[0]) < 40):
                items.append(" ".join(fix_text(ln.plain) for ln in ordered[j].lines))
                last, j = ordered[j], j + 1
            if items:
                p.lines = p.lines + [ln for k in range(i + 1, j) for ln in ordered[k].lines]
                p.bbox = (p.bbox[0], p.bbox[1], max(o.bbox[2] for o in ordered[i:j]), last.bbox[3])
                p.heading = 0
                p.text = "**Beaching Dates:**\n" + "\n".join("- " + t for t in items)
                p.pre_text = True                         # text is final, do not rebuild it from the lines
                out.append(p)
                i = j
                continue
        out.append(p)
        i += 1
    return out


def _beaching_text(p: Any) -> str:
    """'Beaching Dates:' and its date-range lines are kept as a bold label and one bullet per range."""
    lines = [fix_text(ln.plain) for ln in p.lines]
    if re.match(r"(?i)beaching dates", lines[0]):
        rest = [re.sub(r"\s+", " ", ln) for ln in lines[1:] if ln.strip()]
        if len(lines[0]) <= 16 and rest and all(RANGE_LINE_RE.match(r) for r in rest):
            return "**Beaching Dates:**\n" + "\n".join("- " + r for r in rest)
    elif len(lines) > 1 and all(RANGE_LINE_RE.match(ln) for ln in lines):
        return "\n".join("- " + ln for ln in lines)
    return fix_text(prose._join_lines(p.lines))


def fix_text(text: str) -> str:
    """U+FFFD stands for the lost u-umlaut of Turkiye and for curly quotes; both are restored deterministically."""
    return fix_glyphs(re.sub(r"T�rkiye", "Türkiye", text))


def _clean(cell: Any) -> str:
    return re.sub(r"\s+", " ", fix_text(cell or "")).strip()


# ------------------------------------------------------------------------------------------ charts
def _lines(words: list[tuple]) -> list[list[tuple]]:
    """Words grouped into visual lines (same y within tolerance, left to right)."""
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if rows and abs(cy - sum((x[1] + x[3]) / 2 for x in rows[-1]) / len(rows[-1])) <= Y_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w[0]) for r in rows]


def _bbox(ws: list[tuple]) -> tuple[float, float, float, float]:
    return (min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws))


def _cx(w: tuple) -> float:
    return (w[0] + w[2]) / 2


def _axis_words(nums: list[tuple]) -> set[int]:
    """Value-axis tick labels: three or more numbers sharing one right edge."""
    out: set[int] = set()
    for i, w in enumerate(nums):
        same = [j for j, o in enumerate(nums) if abs(o[2] - w[2]) <= 2.0]
        if len(same) >= 3:
            out.update(same)
    return out


def _category_row(span_words: list[tuple]) -> tuple[list[dict[str, Any]], float, float] | None:
    """The row of category labels: the visual line with the most known category words. Returns the categories
    (label, centre, bbox) left to right and the row's y range."""
    best: tuple[int, list[tuple]] | None = None
    for ln in _lines(span_words):
        known = [w for w in ln if w[4].lower() in CAT_WORDS]
        if known and (best is None or len(known) > best[0]):
            best = (len(known), ln)
    if best is None:
        return None
    ln = best[1]
    cats: list[dict[str, Any]] = []
    i = 0
    while i < len(ln):
        w = ln[i]
        if w[4].lower() == "hms":                    # "HMS 1&2 (80:20)" / "HMS 80:20": every word up to Shredded
            j = i + 1
            while j < len(ln) and ln[j][4].lower() not in CAT_WORDS:
                j += 1
            grp = ln[i:j]
            cats.append({"label": " ".join(g[4] for g in grp), "cx": (min(g[0] for g in grp) + max(g[2] for g in grp)) / 2,
                         "bbox": _bbox(grp)})
            i = j
        elif w[4].lower() in CAT_WORDS:
            cats.append({"label": w[4], "cx": _cx(w), "bbox": _bbox([w])})
            i += 1
        else:
            i += 1
    y0 = min(c["bbox"][1] for c in cats)
    y1 = max(c["bbox"][3] for c in cats)
    return cats, y0, y1


def _is_table_heading(page: pymupdf.Page, tbox: tuple) -> bool:
    return any(tbox[3] - 2 <= t.bbox[1] <= tbox[3] + 60 for t in page.find_tables().tables)


def id_(w: tuple) -> tuple:
    return (round(w[0], 1), round(w[1], 1), w[4])


def _series_colours(page: pymupdf.Page, prev: list[tuple], this: list[tuple], vals: list[tuple]) -> tuple[dict[tuple, str], str]:
    """Series of each data label from the vector drawing: the legend marker's fill colour is the series colour and
    the bar under a label has the same fill. Returns (label -> series, status). Status is "unavailable" when the chart
    is a picture (no marker rectangles), "ok" when every marker and every labelled bar matched exactly one fill, and
    "ambiguous" when a marker or a bar has several candidate fills or both series share a colour (never guessed)."""
    fills = [(pymupdf.Rect(d["rect"]), tuple(round(c, 2) for c in d["fill"])) for d in page.get_drawings()
             if d.get("fill") and d["rect"].width > 0 and d["rect"].height > 0]
    marker: dict[tuple, str] = {}
    seen = 0
    for name, ws in (("previous", prev), ("this", this)):
        for w in ws:
            near = {f for r, f in fills if r.width <= 24 and r.height <= 24 and w[0] - 30 <= r.x1 <= w[0] + 4
                    and abs((r.y0 + r.y1) / 2 - (w[1] + w[3]) / 2) <= 12}
            if not near:
                continue
            seen += 1
            if len(near) > 1 or (next(iter(near)) in marker and marker[next(iter(near))] != name):
                return {}, "ambiguous"
            marker[next(iter(near))] = name
    if not seen:
        return {}, "unavailable"
    if len(set(marker.values())) != 2:
        return {}, "ambiguous"
    out: dict[tuple, str] = {}
    for w in vals:
        bars = {f for r, f in fills if r.height > 25 and r.x0 - 2 <= _cx(w) <= r.x1 + 2 and -4 <= r.y0 - w[3] <= 16}
        if len(bars) != 1 or next(iter(bars)) not in marker:
            return {}, "ambiguous"
        out[id_(w)] = marker[next(iter(bars))]
    return out, "ok"


def _remove_words(page: pymupdf.Page, rects: list[list[float]]) -> None:
    """Delete the chart's own words (title, ticks, labels, categories, legend) from the in-memory page. Cutting whole
    text lines by box would also cut commentary that shares a baseline with a chart label (the last wrapped line of a
    bullet), so the prose is read from a page that no longer holds the chart text. Drawings and images are untouched."""
    for r in rects:
        page.add_redact_annot(pymupdf.Rect(r[0] + 0.6, r[1] + 0.6, r[2] - 0.6, r[3] - 0.6))
    if rects:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)


def _note(out: dict[str, Any], why: str, kind: str = "info") -> dict[str, Any]:
    out["note"] = why + ", so the labels cannot be assigned to previous and this week"
    out["note_kind"] = kind
    return out


def _chart(page: pymupdf.Page, pno: int, title: str, tbox: tuple, y_end: float, words: list[tuple]) -> dict[str, Any]:
    """Rebuild one bar chart whose title line is `tbox`; its area ends at `y_end` (next chart title / page end).

    `note_kind` is "info" when the chart legitimately yields no table (it prints no labels, or its legend names only
    one series) and "flag" when the labels do not pair up and a human must look."""
    span = [w for w in words if tbox[1] - 1 <= w[1] and w[3] <= y_end]
    below = [w for w in span if w[1] >= tbox[3] - 1]            # the title line itself names HMS / Shredded
    title_words = [w for w in words if tbox[0] - 1 <= w[0] and w[2] <= tbox[2] + 1 and tbox[1] - 1 <= w[1] and w[3] <= tbox[3] + 1]
    out: dict[str, Any] = {"title": title, "page": pno, "boxes": [list(tbox)], "columns": [], "rows": [], "note": None,
                           "note_kind": None, "bbox": list(tbox), "printed": ""}
    row = _category_row(below)
    if row is None:
        out["note"] = "category labels not found in the text layer"
        out["is_chart"] = False
        return out
    cats, cy0, cy1 = row
    spacing = min((b["cx"] - a["cx"] for a, b in zip(cats, cats[1:])), default=200.0)
    legend = []                       # legend entries only: "Previous"/"This" + "Week", standing apart from running text
    for ln in _lines(span):
        for k, (w, nx) in enumerate(zip(ln, ln[1:])):
            after = ln[k + 2] if k + 2 < len(ln) else None
            before = ln[k - 1] if k else None
            apart = ((after is None or after[0] - nx[2] >= 14 or after[4].lower() in ("this", "previous"))
                     and (before is None or w[0] - before[2] >= 14 or before[4].lower() == "week" or before[4] in ("-", "–")))
            in_chart = cats[0]["cx"] - spacing <= _cx(w) <= cats[-1]["cx"] + spacing
            if (w[4].lower() in ("previous", "this") and nx[4].lower() == "week" and nx[0] - w[2] < 12 and apart and in_chart
                    and not (after is not None and after[4].startswith(":"))):    # "This Week : 84.36" is a value line
                legend += [w, nx]
    if not legend and _is_table_heading(page, tbox):
        out["note"] = "no chart legend (a table heading, not a chart)"
        out["is_chart"] = False                       # C template: the HMS/Shredded heading sits above a ruled table
        return out
    nums = [w for w in span if VALUE_RE.match(w[4]) and w[3] <= cy0 + 1 and w[1] >= tbox[1]
            and cats[0]["cx"] - spacing <= _cx(w) <= cats[-1]["cx"] + spacing]     # numbers in the commentary are not ticks
    axis = _axis_words(nums)
    xs0, xs1 = cats[0]["cx"] - spacing / 2, cats[-1]["cx"] + spacing / 2
    vals = [w for i, w in enumerate(nums) if i not in axis and xs0 <= _cx(w) <= xs1]
    axis_ws = [nums[i] for i in axis]
    left = max([w[2] for w in axis_ws if w[2] < cats[0]["cx"]], default=None)
    per_cat: list[list[tuple]] = [[] for _ in cats]
    for w in vals:
        k = min(range(len(cats)), key=lambda i: abs(cats[i]["cx"] - _cx(w)))
        per_cat[k].append(w)
    prev = [w for w in legend if w[4].lower() == "previous"]
    this = [w for w in legend if w[4].lower() == "this"]
    legend_ok = bool(prev and this)
    first_series = ("previous" if min(w[0] for w in prev) < min(w[0] for w in this) else "this") if legend_ok else None
    # only the chart's own apparatus (title, axis ticks, labels, categories, legend) is cut from the prose, line by line,
    # so a footnote printed inside the chart area ("*The market remains closed") stays in the text
    apparatus = title_words + axis_ws + vals + legend + [w for w in below if w[1] >= cy0 - 2 and w[3] <= cy1 + 2
                                                         and any(c["bbox"][0] - 1 <= w[0] and w[2] <= c["bbox"][2] + 1 for c in cats)]
    out["boxes"] = [[min(w[0] for w in ln) - 2, min(w[1] for w in ln) - 2, max(w[2] for w in ln) + 2, max(w[3] for w in ln) + 2]
                    for ln in _lines(apparatus)]
    out["apparatus"] = [[w[0], w[1], w[2], w[3]] for w in apparatus]
    ys = [w[1] for w in vals] or [cy0]
    lx0 = (left + 2.0) if left is not None else min(c["bbox"][0] for c in cats) - 4.0
    lx1 = max(max(c["bbox"][2] for c in cats), max((w[2] for w in vals), default=0.0)) + 4.0
    out["bbox"] = [lx0, min(ys) - 2.0, lx1, cy1 + 1.0]
    out["printed"] = "; ".join(f"{c['label']}: {', '.join(w[4] for w in sorted(v, key=lambda w: w[0]))}"
                               for c, v in zip(cats, per_cat) if v)
    if not vals:
        out["note"], out["note_kind"] = "the chart prints no data labels", "info"
        return out
    # a category whose bars carry no label (no price that week) stays empty; one label alone is ambiguous
    paired = all(len(v) in (0, 2) for v in per_cat) and any(len(v) == 2 for v in per_cat)
    if not legend_ok or not paired:
        out["note"] = ("the legend names only one series" if legend and not legend_ok else
                       "the legend is not printed as text" if not legend_ok else
                       "the data labels do not pair up (" + ", ".join(f"{c['label']}:{len(v)}" for c, v in zip(cats, per_cat)) + ")")
        out["note"] += ", so the labels cannot be assigned to previous and this week"
        out["note_kind"] = "info"                     # nothing is guessed: the printed labels stay in the note
        return out
    out["columns"] = ["Category", "Previous Week", "This Week"]
    if all(not v or v[0][4] == v[1][4] for v in per_cat):
        # both bars of every category print the same figure: the table is the same whichever bar is which series
        out["series_basis"] = "series_equal"
        out["rows"] = [[fix_text(c["label"]), *([v[0][4], v[1][4]] if v else ["", ""])] for c, v in zip(cats, per_cat)]
        return out
    colours, status = _series_colours(page, prev, this, vals)
    stacked = abs(min(w[0] for w in prev) - min(w[0] for w in this)) < 5     # legend entries one above the other
    rows = []
    if status == "unavailable":
        if stacked:
            return _note(out, "the legend entries are stacked, so the bar order does not say which series is which")
        out["series_basis"] = "legend_order"          # picture chart: only legend order (left to right) assigns the series
    elif status != "ok":
        return _note(out, "the legend markers or bar colours are ambiguous", "flag")
    else:
        out["series_basis"] = "colour"
    for c, v in zip(cats, per_cat):
        if not v:
            rows.append([fix_text(c["label"]), "", ""])
            continue
        v = sorted(v, key=lambda w: w[0])
        by_order = (v[0], v[1]) if first_series == "previous" else (v[1], v[0])      # (previous, this) by legend order
        if status == "ok":
            ser = [colours[id_(w)] for w in v]
            if sorted(ser) != ["previous", "this"]:
                return _note(out, "both bars of " + c["label"] + " have the same colour", "flag")
            pv = v[ser.index("previous")]
            tv = v[ser.index("this")]
            if not stacked and (pv, tv) != by_order:
                return _note(out, "bar colours and legend order disagree for " + c["label"], "flag")
        else:
            pv, tv = by_order
        rows.append([fix_text(c["label"]), pv[4], tv[4]])
    out["rows"] = rows
    return out


def find_charts(page: pymupdf.Page, pno: int) -> list[dict[str, Any]]:
    words = page.get_text("words")
    titles = []
    for ln in _lines(words):
        segs, seg = [], [ln[0]]
        for w in ln[1:]:                                   # a title can share a baseline with commentary on its left
            if w[0] - seg[-1][2] > 40:
                segs.append(seg)
                seg = []
            seg.append(w)
        segs.append(seg)
        for sg in segs:
            text = " ".join(w[4] for w in sg)
            if CHART_TITLE_RE.match(text) and len(text) < 70:
                titles.append((text, _bbox(sg)))
    titles.sort(key=lambda t: t[1][1])
    out = []
    for i, (text, tb) in enumerate(titles):
        y_end = titles[i + 1][1][1] - 1 if i + 1 < len(titles) else float(page.rect.height)
        c = _chart(page, pno, fix_text(text), tb, y_end, words)
        if c.get("is_chart", True):                     # a banner heading ("BUNKER PRICES AT PORT") has no categories
            out.append(c)
    return out


# ------------------------------------------------------------------------------------------ label : value blocks
KV_LINE_RE = re.compile(r"^(This Week|Previous Week|Gained|Gain|Lost|Loss|Movement)\s*:\s*(\S.*)$", re.I)
CRUDE_LINE_RE = re.compile(r"^(BRENT CRUDE|WTI CRUDE)\s*:\s*(\(.*?\))\s*(\S.*)?$", re.I)


def _kv_label_at(ln: list[tuple], k: int) -> bool:
    t = ln[k][4].lower()
    if t in ("this", "previous"):
        return k + 1 < len(ln) and ln[k + 1][4].lower() == "week"
    return t in ("gained", "gain", "lost", "loss", "movement")


def kv_tables(page: pymupdf.Page, pno: int) -> list[dict[str, Any]]:
    """Blocks of 'This Week : v / Previous Week : v / Gained|Lost|Movement : v' lines printed under a column title
    (exchange rates 'USD / INR', 'Brent Crude' / 'WTI Crude'). Blocks side by side on one row form one table; each
    block is read from its own x range, so titles and values cannot be paired across columns."""
    lines = _lines(page.get_text("words"))
    kv = []
    for i, ln in enumerate(lines):
        starts = [k for k, w in enumerate(ln) if _kv_label_at(ln, k)]
        for a, b in zip(starts, [*starts[1:], len(ln)]):          # columns share a visual line: cut at each label
            seg = ln[a:b]
            m = KV_LINE_RE.match(" ".join(w[4] for w in seg))
            if m:
                kv.append((i, seg, m.group(1), m.group(2)))
    blocks: list[dict[str, Any]] = []
    for i, ln, label, value in kv:
        x0, y0, x1, y1 = _bbox(ln)
        for b in blocks:
            if abs(b["x0"] - x0) <= 12 and 0 <= y0 - b["y1"] < 40:
                b["rows"].append((label, value))
                b["y1"], b["x1"] = y1, max(b["x1"], x1)
                break
        else:
            blocks.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "rows": [(label, value)]})
    out = []
    for b in blocks:
        if len(b["rows"]) < 2:
            continue
        above = [ln for ln in lines if ln[0][1] < b["y0"] - 1 and b["y0"] - ln[0][3] < 70
                 and not any(_kv_label_at(ln, k) for k in range(len(ln)))
                 and any(b["x0"] - 40 <= _cx(w) <= b["x1"] + 40 for w in ln)]
        if not above:
            continue
        head = max(above, key=lambda ln: ln[0][1])
        hw = [w for w in head if b["x0"] - 40 <= _cx(w) <= b["x1"] + 40]
        d = {lab.title(): val for lab, val in b["rows"]}
        change = next((k for k in ("Gained", "Gain", "Lost", "Loss", "Movement") if k in d), None)
        out.append({"title": fix_text(" ".join(w[4] for w in hw)), "this": d.get("This Week", ""),
                    "prev": d.get("Previous Week", ""),
                    "change": ("" if change is None else d[change] if change == "Movement" else f"{change} {d[change]}"),
                    "bbox": [min(w[0] for w in hw), min(w[1] for w in hw), b["x1"], b["y1"]]})
    if len(out) < 2:
        return []
    out.sort(key=lambda r: r["bbox"][0])
    return [{"page": pno, "columns": ["Item", "This Week", "Previous Week", "Change"],
             "rows": [[r["title"], r["this"], r["prev"], r["change"]] for r in out],
             "bbox": [round(min(r["bbox"][0] for r in out), 2), round(min(r["bbox"][1] for r in out), 2),
                      round(max(r["bbox"][2] for r in out), 2), round(max(r["bbox"][3] for r in out), 2)]}]


def crude_table(page: pymupdf.Page, pno: int) -> list[dict[str, Any]]:
    """'BRENT CRUDE: (104.86 103.16) - 1.7' lines (C template): the two figures and the change as printed; the
    arrow between the figures is a picture, so the values are not labelled previous/this here."""
    rows, boxes = [], []
    for ln in _lines(page.get_text("words")):
        m = CRUDE_LINE_RE.match(" ".join(w[4] for w in ln))
        if m:
            rows.append([m.group(1).upper(), m.group(2), (m.group(3) or "").strip()])
            boxes.append(_bbox(ln))
    if not rows:
        return []
    bb = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return [{"page": pno, "columns": ["Item", "Values as printed", "Change"], "rows": rows, "bbox": [round(v, 2) for v in bb]}]


# ------------------------------------------------------------------------------------------ ruled tables
def _is_data_cell(cell: str) -> bool:
    return bool(NUMERIC_CELL_RE.match(cell))


def normalise_table(raw: list[list[str]]) -> tuple[list[str], list[list[str]]] | None:
    """Header rows are the rows above the first row with a numeric cell. A header printed over merged cells
    (A-template 'Year of Build' sits two columns right of its data) is moved onto the data column."""
    start = next((i for i, r in enumerate(raw) if any(_is_data_cell(c) for c in r)), None)
    if start is None or start == 0:
        return None
    head_rows, body = raw[:start], [r for r in raw[start:] if any(r)]
    n = max(len(r) for r in raw)
    head = [" ".join(h for h in (r[i] if i < len(r) else "" for r in head_rows) if h) for i in range(n)]
    has_data = [any(i < len(r) and r[i] for r in body) for i in range(n)]
    for i in range(n):
        if has_data[i] and not head[i]:
            j = next((k for k in range(i + 1, n) if head[k] and not has_data[k]), None)
            if j is not None:
                head[i], head[j] = head[j], ""
    keep = [i for i in range(n) if has_data[i] or head[i]]
    keep = [i for i in keep if has_data[i]]
    return [head[i] for i in keep], [[(r[i] if i < len(r) else "") for i in keep] for r in body]


def page_tables(page: pymupdf.Page, pno: int) -> list[dict[str, Any]]:
    out = []
    for t in page.find_tables().tables:
        raw = [[_clean(c) for c in r] for r in t.extract()]
        norm = normalise_table(raw)
        if norm is None:
            continue
        cols, rows = norm
        if not rows or len(cols) < 2:
            continue
        out.append({"page": pno, "columns": cols, "rows": rows, "bbox": [round(v, 2) for v in t.bbox]})
    return out


# ------------------------------------------------------------------------------------------ markdown shims
class _Block:
    """Table or figure note placed among paragraphs by prose.order_items / render."""

    def __init__(self, bbox: list[float], md: str) -> None:
        self.bbox = tuple(bbox)
        self._md = md

    def to_markdown(self, level: int = 3) -> str:
        return self._md.replace("@@", "#" * level, 1)


CHART_MARKER = "<!-- bo-chart {} -->"      # removed by best_oasis_continuity once it has run


def _chart_md(c: dict[str, Any], cid: str) -> str:
    head = CHART_MARKER.format(cid) + f"\n@@ {c['title']}"
    if c["note"]:
        printed = f" Labels as printed, left to right: {c['printed']}." if c["printed"] else ""
        return f"{head}\n\n> Figure: {c['title']} - {c['note']}; no table written.{printed}"
    return head + "\n\n" + render_table(c["columns"], c["rows"])


def _table_md(t: dict[str, Any], title: str | None) -> str:
    body = render_table(t["columns"], t["rows"])
    return f"@@ {title}\n\n{body}" if title else body


def table_title(t: dict[str, Any], page_text: str) -> str | None:
    """The printed section banner of a table: text when the page has it, otherwise the banner image's caption
    (A template), which is the same fixed title."""
    if any(re.search(r"(?i)vessel name", c) for c in t["columns"]) and VESSEL_TITLE.lower() not in page_text.lower():
        return VESSEL_TITLE
    return None


# ------------------------------------------------------------------------------------------ run
def report_period(doc: pymupdf.Document) -> str | None:
    month = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    for ln in doc[0].get_text().split("\n"):
        t = re.sub(r"\s+", " ", re.sub(r"[()]", " ", ln)).strip()
        if re.search(r"(?i)\b" + month + r"\b", t) and re.search(r"\d", t) and len(t) < 60:
            return t
    return None


def run(plan: Any, doc: pymupdf.Document, profile: dict[str, Any]) -> dict[str, Any]:
    drops = profile.get("drop_regions")
    strip = [re.compile(p) for p in (*profile.get("strip_line_patterns", []), *profile.get("boilerplate_patterns", []))]
    repeated: set[str] = set()      # footers are stripped by profile patterns; the band filter would eat repeated beaching dates
    body = prose.body_font_size(doc, plan.pages)
    level = int(profile.get("geom", {}).get("table_heading_level", 3))
    all_tables: list[dict[str, Any]] = []
    md: list[str] = []
    problems: list[str] = []
    counts = {"charts": 0, "chart_notes": 0, "tables": 0}
    if any("gmsinc.net" in doc[p - 1].get_text() for p in range(1, len(doc) + 1)):
        problems.append("wrong_publisher_pdf:GMS report filed under a Best Oasis title")
    period = report_period(doc)
    if period:
        md.append(f"Reporting week: {fix_text(period)}")
    for pno in plan.pages:
        page = doc[pno - 1]
        page_text = page.get_text()
        boxes = prose.drop_region_boxes(page, drops)
        charts = find_charts(page, pno)
        tables = page_tables(page, pno) + kv_tables(page, pno) + crude_table(page, pno)
        exclude = list(boxes)
        for t in tables:
            exclude.append((t["bbox"][0] - 2, t["bbox"][1] - 2, t["bbox"][2] + 2, t["bbox"][3] + 2))
        _remove_words(page, [r for c in charts for r in c["apparatus"]])
        paras = prose.page_prose(page, pno, exclude, repeated, body)
        for p in paras:
            p.lines = [ln for ln in p.lines if not any(r.search(ln.plain) for r in strip)]
        paras = [p for p in paras if p.lines]
        paras = merge_split_sentences(paras) if not any(p.column >= 0 for p in paras) else paras
        paras = group_beaching(paras)
        paras = [p for p in paras if not (period and re.sub(r"\s+", " ", re.sub(r"[()]", " ", fix_text(" ".join(ln.plain for ln in p.lines)))).strip() == period)]
        paras = [p for i, p in enumerate(paras) if not (i and p.heading and paras[i - 1].heading
                                                       and p.lines[0].plain == paras[i - 1].lines[0].plain)]
        for p in paras:
            if getattr(p, "pre_text", False):
                continue
            p.text = fix_text(prose._join_lines(p.lines))
            if p.heading:
                p.text = fix_text(p.lines[0].plain)
                if re.match(r"(?i)beaching dates", p.text):
                    p.heading, p.text = 0, "**Beaching Dates:**"
                elif len(re.findall(r"[A-Za-z]", p.text)) < 3:
                    p.heading = 0                              # "- 1.7": a coloured figure, not a heading
                else:
                    p.heading = 1 if SECTION_RE.match(p.text) else 2
            else:
                p.text = _beaching_text(p)
        landscape = page.rect.width > page.rect.height
        blocks: list[_Block] = []
        page_country = next((m.group(1) for c in charts if (m := re.search(r"(?i)ships in (\S+)", c["title"]))), None)
        for ci, c in enumerate(charts):
            cid = f"p{pno}c{ci}"                           # stable chart id: page + chart index on the page
            counts["charts"] += 1
            counts["chart_notes"] += bool(c["note"])
            if c["note"]:
                kind = "figure_note" if c["note_kind"] == "info" else "chart_not_extracted"
                problems.append(f"{kind}_p{pno}:{c['title'][:40]}:{c['note'][:70]}")
            else:
                all_tables.append({"name": c["title"], "title": c["title"], "page": pno, "bbox": [round(v, 2) for v in c["bbox"]],
                                   "columns": c["columns"], "rows": c["rows"], "empty": not c["rows"],
                                   "row_source": "best_oasis_chart", "series_basis": c.get("series_basis"), "chart_id": cid,
                                   "country": page_country, "printed": c["printed"], "unassigned_words": 0, "row_meta": [],
                                   "column_bounds": [], "source_columns": c["columns"], "en_bloc_rows": []})
            bb = [min(b[0] for b in c["boxes"]), min(b[1] for b in c["boxes"]),
                  max(b[2] for b in c["boxes"]), max(b[3] for b in c["boxes"])]
            if landscape and (bb[0] + bb[2]) / 2 > 0.6 * page.rect.width:
                bb[1] += float(page.rect.height)           # right-hand charts follow the commentary
            blocks.append(_Block(bb, _chart_md(c, cid)))
        for t in tables:
            title = table_title(t, page_text)
            counts["tables"] += 1
            entry = {"name": title or "Table", "title": title, "page": pno, "bbox": t["bbox"], "columns": t["columns"],
                     "rows": t["rows"], "empty": False, "row_source": "best_oasis_ruled", "unassigned_words": 0,
                     "row_meta": [], "column_bounds": [], "source_columns": t["columns"], "en_bloc_rows": []}
            all_tables.append(entry)
            blocks.append(_Block(t["bbox"], ""))
            blocks[-1].entry = entry                         # type: ignore[attr-defined]
            blocks[-1].title = title                         # type: ignore[attr-defined]
        for b in blocks:
            e = getattr(b, "entry", None)
            if e is not None:
                b._md = _table_md(e, b.title)                # type: ignore[attr-defined]
        items = prose.order_items(paras, [b for b in blocks])
        md.append(prose.render(items, level))
    text = "\n\n".join(m for m in md if m.strip())
    return {
        "markdown": text, "tables": all_tables, "parser": "pymupdf_table + best_oasis_template",
        "api": "local", "tier": None, "credits_used": 0, "parsed_at": None, "problems": problems, "counts": counts,
    }
