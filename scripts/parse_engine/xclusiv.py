"""Xclusiv Shipbrokers weekly report, 2021-2023 template (digital PDF, landscape slides).

Page layout (all useful pages are the first five):
  p1  left column: "Market Commentary"; right panel: Baltic indices, newbuilding prices, demolition prices
  p2  left column: dry freight commentary;  right panel: dry secondhand prices;  charts below
  p3  left column: tanker (wet) freight commentary;  right panel: wet secondhand prices;  charts below
  p4  "Sale and Purchase" commentary (dry paragraph(s), then tanker paragraph(s)) + bulk carrier sales table
  p5  tanker sales + container / gas / general cargo / OBO sales tables

Panel tables are read from word rows (label + numeric cells). The sales tables are read from the vector
cell borders drawn on the page (column rules, row rules, vertical merges), so a buyer or price printed once
over several vessels is carried to every vessel it spans. Charts carry no printed values and produce no
table. Nothing is estimated or derived: every cell is text printed in the PDF.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf

from scripts.parse_engine import prose

NUM_RE = re.compile(r"^[-\u2212\u2013+]?\d[\d,]*(?:\.\d+)?%?$")
CELL_RE = re.compile(r"^(?:[-\u2212\u2013+]?\d[\d,]*(?:\.\d+)?%?|\(\d[\d,]*(?:\.\d+)?\)|[-\u2013\u2014])$")
MONTH_LABEL_RE = re.compile(r"[A-Z][a-z]{2}(?:/\d{2}| \d{4})")
MONTH_RE = re.compile(r"^[A-Z][a-z]{2}/\d{2}$")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
WEEK_RE = re.compile(r"Week\s*(\d+)")
Y_TOL = 3.0

PANEL_TITLES = [
    ("ind_dry", re.compile(r"BALTIC DRY INDICES")),
    ("ind_wet", re.compile(r"BALTIC TANKER INDICES")),
    ("nb_dry", re.compile(r"DRY NEWBUILDING PRICES")),
    ("nb_wet", re.compile(r"WET NEWBUILDING PRICES")),
    ("demo", re.compile(r"DEMOLITION PRICES")),
    ("sh_dry", re.compile(r"DRY SECONDHAND PRICES")),
    ("sh_wet", re.compile(r"WET SECONDHAND PRICES")),
]
SALES_TITLE_RE = re.compile(r"^(?:[A-Z/&]+\s+)+SALES\b")
TENOR = {"resale": "Resale", "5y": "5 Year", "10y": "10 Year", "15y": "15 Year"}
SALES_HEADERS = ["NAME", None, "YEAR", "COUNTRY", "YARD", "BUYERS", "PRICE", "NOTES"]
# Name, DWT/size, Year, Country and Yard are printed per vessel; only Buyers, Price and Comments are ever one cell over several vessels
MERGEABLE_FROM = 5
CONTACT_LINE_RE = re.compile(r"(?i)^(xclusiv shipbrokers( inc\.?| weekly)?|kifissias|15451 psychico|tel:|research & valuations)")


# ------------------------------------------------------------------------------------------ text helpers
def fix_glyphs(text: str) -> str:
    """The text layer loses curly quotes and apostrophes (U+FFFD). Between two letters it is an apostrophe;
    elsewhere a quote that opens when it follows a space/bracket and closes otherwise."""
    if "\ufffd" not in text:
        return text
    out = []
    for i, ch in enumerate(text):
        if ch != "\ufffd":
            out.append(ch)
            continue
        prev = text[i - 1] if i else " "
        nxt = text[i + 1] if i + 1 < len(text) else " "
        if prev.isalnum() and nxt.isalpha():
            out.append("\u2019")
        elif prev in " ([-/\u2013" or i == 0:
            out.append("\u201c")
        else:
            out.append("\u201d")
    return "".join(out)


def _plain(text: str) -> str:
    text = re.sub(r"\s+", " ", fix_glyphs(text.replace("**", ""))).strip()
    return re.sub(r"(USD|US\$|\$) -\s+(?=\d)", r"\1 -", text)     # a negative figure wrapped after its sign


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip() or "-"


def render_table(columns: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    out += ["| " + " | ".join(_md_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _is_num(tok: str) -> bool:
    return bool(NUM_RE.match(tok))


# ------------------------------------------------------------------------------------------ geometry
def panel_x0(page: pymupdf.Page) -> float | None:
    xs = [d["rect"].x0 for d in page.get_drawings()
          if d["rect"].x0 > 380 and d["rect"].width > 200 and d["rect"].height > 8 and d["rect"].y0 < 130]
    return min(xs) if xs else None


def _overlap(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / max(min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])), 1e-6)


def _words(page: pymupdf.Page) -> list[tuple]:
    """Words of the text layer. One issue prints some text twice at (almost) the same position (overprint):
    a repeat of the same word within 2 pt is dropped, and where a different word is printed over an earlier
    one only the later (visible, top-most) word is kept."""
    out: list[tuple] = []
    by_text: dict[str, list[tuple]] = {}
    for w in page.get_text("words"):
        if any(abs(o[0] - w[0]) <= 2 and abs(o[1] - w[1]) <= 2 for o in by_text.get(w[4], [])):
            continue
        by_text.setdefault(w[4], []).append(w)
        out.append(w)
    rows: dict[int, list[int]] = {}
    for k, w in enumerate(out):
        rows.setdefault(int(w[1] // 4), []).append(k)
    hidden: set[int] = set()
    for k, w in enumerate(out):
        near = [m for b in (int(w[1] // 4) - 1, int(w[1] // 4), int(w[1] // 4) + 1) for m in rows.get(b, [])]
        if any(m > k and _overlap(w, out[m]) >= 0.5 for m in near):
            hidden.add(k)
    return [w for k, w in enumerate(out) if k not in hidden]


def _rows_by_y(words: list[tuple]) -> list[tuple[float, list[tuple]]]:
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if rows and abs(cy - (rows[-1][0][1] + rows[-1][0][3]) / 2) <= Y_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [(sum((w[1] + w[3]) / 2 for w in r) / len(r), sorted(r, key=lambda w: w[0])) for r in rows]


def _bbox(words: list[tuple]) -> list[float]:
    return [min(w[0] for w in words), min(w[1] for w in words), max(w[2] for w in words), max(w[3] for w in words)]


def _table(name: str, title: str, page: int, columns: list[str], rows: list[list[str]], words: list[tuple],
           unassigned: int = 0, en_bloc_rows: list[int] | None = None) -> dict[str, Any]:
    return {"name": name, "title": title, "page": page, "bbox": [round(v, 2) for v in _bbox(words)],
            "columns": columns, "rows": rows, "en_bloc_rows": en_bloc_rows or [], "empty": not rows,
            "boundary_source": "xclusiv_rows", "row_source": "xclusiv", "unassigned_words": unassigned,
            "row_meta": [], "column_bounds": [], "source_columns": columns}


# ------------------------------------------------------------------------------------------ panel tables
def _split_label(row: list[tuple]) -> tuple[str, list[str]]:
    """Leading words are the label; after it come the numeric cells ("$" signs printed as their own word are
    skipped; a lone dash or a bracketed figure such as "(5.0)" is a cell too)."""
    label: list[str] = []
    nums: list[str] = []
    for w in row:
        tok = w[4]
        if tok == "$":
            continue
        if (label or nums) and CELL_RE.match(tok):
            nums.append(tok)
        elif not nums:
            label.append(tok)
        else:
            nums.append(tok)          # a non-numeric token inside the numeric run is kept and counted as a mismatch
    return " ".join(label), nums


def _avg_text(years: list[str], vals: list[str]) -> str:
    return " / ".join(f"{y}: {v}" for y, v in zip(years, vals))


def panel_tables(page: pymupdf.Page, pno: int, x0: float, y_max: float) -> tuple[list[dict[str, Any]], list[str]]:
    """Tables of the right-hand panel. Returns (tables, problems)."""
    words = [w for w in _words(page) if (w[0] + w[2]) / 2 >= x0 and w[3] <= y_max]
    state: str | None = None
    blocks: dict[str, list[tuple[float, list[tuple]]]] = {}
    order: list[str] = []
    for y, row in _rows_by_y(words):
        text = " ".join(w[4] for w in row)
        for key, rx in PANEL_TITLES:
            if rx.search(text):
                state = key
                order.append(key)
                blocks[key] = [(y, row)]
                break
        else:
            if state:
                blocks[state].append((y, row))
    tables: list[dict[str, Any]] = []
    problems: list[str] = []
    for key in order:
        rows = blocks[key]
        flat = [w for _, r in rows for w in r]
        header_text = " ".join(" ".join(w[4] for w in r) for _, r in rows[:6])
        months = MONTH_LABEL_RE.findall(header_text)
        years = next(([w[4] for w in r] for _, r in rows[:7] if len(r) == 3 and all(YEAR_RE.match(w[4]) for w in r)), [])
        data = []
        for _, r in rows[1:]:
            label, nums = _split_label(r)
            if (re.search(r"[A-Za-z]", label) and nums and not MONTH_RE.match(label)
                    and not re.search(r"\bWeek\b|\bSegment\b|Demo Country|\bAverage\b|^Page\b|\bINC\b|^Size\b", label)):
                data.append((label, nums, r))
        if not data:
            problems.append(f"panel_{key}_no_rows")
            continue
        bad = 0
        out: list[list[str]] = []
        if key in ("ind_dry", "ind_wet"):
            weeks = [m for m in WEEK_RE.findall(header_text)]
            for label, nums, _ in data:
                if len(nums) != 6:
                    bad += 1
                    continue
                out.append([label, nums[0], nums[1], nums[2], _avg_text(years, nums[3:6])])
            tables.append(_table(f"Baltic {'Dry' if key == 'ind_dry' else 'Tanker'} Indices", "", pno,
                                 ["Index", "Current", "Previous", "Change (%)", "3Y Trend / Historical Averages"],
                                 out, flat, bad))
            tables[-1]["weeks"] = weeks[:2]
        elif key in ("nb_dry", "nb_wet"):
            sector = "Dry" if key == "nb_dry" else "Tanker"
            for label, nums, _ in data:
                if len(nums) != 6:
                    bad += 1
                    continue
                out.append([sector, label, f"${nums[0]}M", f"${nums[1]}M", nums[2], _avg_text(years, nums[3:6])])
            prev = months[1] if len(months) > 1 else "Previous"
            tables.append(_table(f"{sector} Newbuilding Prices", "", pno,
                                 ["Sector", "Vessel Type", "Price ($M)", f"{prev} Price ($M)", "Change (%)",
                                  "3Y Average Prices ($M)"], out, flat, bad))
            tables[-1]["period"] = months[:2]
        elif key == "demo":
            weeks = WEEK_RE.findall(header_text)
            for label, nums, _ in data:
                if len(nums) != 6:
                    bad += 1
                    continue
                out.append(["Bulkers", label.title(), f"${nums[0]}", f"${nums[1]}", nums[2]])
                out.append(["Tankers", label.title(), f"${nums[3]}", f"${nums[4]}", nums[5]])
            out.sort(key=lambda r: (r[0] != "Bulkers",))
            wk_prev = f"Week {weeks[1]}" if len(weeks) > 1 else "Previous Week"
            tables.append(_table("Demolition Prices", "", pno,
                                 ["Segment", "Country", "Price ($/LDT)", f"{wk_prev} ($/LDT)", "Change"], out, flat, bad))
            tables[-1]["weeks"] = weeks[:2]
        else:
            dry = key == "sh_dry"
            for label, nums, _ in data:
                if len(nums) != 7:
                    bad += 1
                    continue
                parts = label.rsplit(" ", 1)
                tenor = TENOR.get(parts[-1].lower())
                vtype = parts[0] if tenor and len(parts) > 1 else label
                out.append([vtype, tenor or "-", f"${nums[0]}M", f"${nums[1]}M", nums[2], nums[3],
                            _avg_text(years, nums[4:7])])
            prev = months[1] if len(months) > 1 else "Previous"
            tables.append(_table(f"{'Dry' if dry else 'Tanker'} Secondhand Prices", "", pno,
                                 ["Vessel Type", "Tenor", "Price ($M)", f"{prev} Price ($M)", "12m Change (%)",
                                  "12m Diff ($M)", "3Y Average Prices ($M)"], out, flat, bad))
            tables[-1]["period"] = months[:2]
        if bad:
            problems.append(f"panel_{key}_rows_with_unexpected_cells={bad}")
    return tables, problems


# ------------------------------------------------------------------------------------------ sales tables
def _cluster(vals: list[float], tol: float) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _rules(page: pymupdf.Page) -> tuple[list[tuple], list[tuple]]:
    """(vertical, horizontal) stroke segments as (x0, y0, x1, y1). Table borders are drawn as thin strokes
    or hairline rectangles."""
    vert, horiz = [], []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width < 1.6 and r.height > 3:
            vert.append((r.x0, r.y0, r.x1, r.y1))
        elif r.height < 1.6 and r.width > 5:
            horiz.append((r.x0, r.y0, r.x1, r.y1))
    return vert, horiz


def _covered(horiz: list[tuple], y: float, x0: float, x1: float) -> bool:
    need = 0.5 * (x1 - x0)
    got = 0.0
    for hx0, hy0, hx1, hy1 in horiz:
        if abs((hy0 + hy1) / 2 - y) <= 1.8:
            got += max(0.0, min(hx1, x1) - max(hx0, x0))
    return got >= need


def _vertical_continues(vert: list[tuple], x: float, y: float) -> bool:
    return any(abs((v[0] + v[2]) / 2 - x) <= 2.5 and v[1] < y - 0.8 and v[3] > y + 0.8 for v in vert)


def _fills(page: pymupdf.Page) -> list[tuple]:
    """Filled cell rectangles (the zebra shading drawn behind each table cell, merged cells included)."""
    return [(d["rect"].x0, d["rect"].y0, d["rect"].x1, d["rect"].y1) for d in page.get_drawings()
            if d.get("fill") is not None and d["rect"].width > 8 and d["rect"].height > 6]


def _cell_boundary(horiz: list[tuple], vert: list[tuple], fills: list[tuple], y: float, x0: float, x1: float) -> bool:
    """A row boundary exists in a column when a cell ends there, a rule is drawn across it, or the rules on both
    sides of the cell are broken there. A cell merged over several rows has none of these (some PDFs omit the
    horizontal rule in a merged cell, others draw the side rules per cell, some draw only the cell shading, so
    all three are checked; the shading decides when the page has it)."""
    cx = (x0 + x1) / 2
    in_col = [f for f in fills if f[0] - 3 <= x0 and f[2] >= x1 - 3 and f[0] <= cx <= f[2] and f[2] - f[0] <= (x1 - x0) + 12]
    if any(f[1] + 1.5 < y < f[3] - 1.5 for f in in_col):
        return False                                      # one shaded cell runs across this line
    if any(abs(f[3] - y) <= 1.5 or abs(f[1] - y) <= 1.5 for f in in_col):
        return True
    if _covered(horiz, y, x0, x1):
        return True
    return not (_vertical_continues(vert, x0 - 1, y) and _vertical_continues(vert, x1 + 1, y))


def sales_tables(page: pymupdf.Page, pno: int, last_title: str | None) -> tuple[list[dict[str, Any]], list[str], str | None]:
    words = _words(page)
    vert, horiz = _rules(page)
    fills = _fills(page)
    problems: list[str] = []
    headers = []
    for w in words:
        if w[4] == "NAME" and w[0] < 140:
            line = {x[4] for x in words if abs((x[1] + x[3]) / 2 - (w[1] + w[3]) / 2) <= Y_TOL}
            if {"YEAR", "COUNTRY"} <= line:
                headers.append(w)
    headers.sort(key=lambda w: w[1])
    tops: list[tuple[float, str | None]] = []
    for h in headers:
        title = None
        title_y = h[1] - 2
        for y, row in _rows_by_y([w for w in words if h[1] - 24 < w[1] < h[1] - 3]):
            text = " ".join(w[4] for w in row)
            if SALES_TITLE_RE.match(text):
                title, title_y = text, min(w[1] for w in row) - 2
        tops.append((title_y, title))
    tables: list[dict[str, Any]] = []
    for i, (h, (top, title)) in enumerate(zip(headers, tops)):
        bottom = tops[i + 1][0] - 8 if i + 1 < len(tops) else min(float(page.rect.height) - 40, 497.0)
        if title:
            last_title = title
        elif last_title:
            title = last_title
        section_title = title or ""
        # rows: the horizontal rules under the NAME column form a chain ~12 pt apart (wrapped rows 24-36 pt);
        # the chain ends at the first large gap
        name_x = h[0] + 1
        hy = _cluster([(s[1] + s[3]) / 2 for s in horiz
                       if s[0] <= name_x + 1 and s[2] >= name_x and top - 14 <= (s[1] + s[3]) / 2 <= bottom], 1.8)
        # the table starts at the rule just above its title (or header) text
        above = [y for y in hy if y <= top + 3]
        hy = hy[hy.index(above[-1]):] if above else hy
        ys = [hy[0]] if hy else []
        for y in hy[1:]:
            if y - ys[-1] > 70:
                break
            ys.append(y)
        if len(ys) < 3:
            problems.append("sales_table_no_rows")
            continue
        tv = [s for s in vert if s[3] > ys[0] + 2 and s[1] < ys[-1] - 2]
        span = ys[-1] - ys[0]
        xs = []
        for cx in _cluster([(s[0] + s[2]) / 2 for s in tv], 2.5):
            # a rule that runs on into the next table counts only as far as this table goes
            cover = sum(min(s[3], ys[-1]) - max(s[1], ys[0]) for s in tv if abs((s[0] + s[2]) / 2 - cx) <= 2.5)
            if cover >= 0.4 * span:
                xs.append(cx)
        xs = _cluster(xs, 2.5)
        if len(xs) != 9:
            problems.append(f"sales_table_columns={len(xs) - 1}")
            continue
        # data rows drawn without rules: the shaded first-column cells give the row edges
        edges = _cluster([f[3] for f in fills if abs(f[0] - xs[0]) <= 3 and abs(f[2] - xs[1]) <= 3
                          and f[1] >= ys[-1] - 1.5 and f[3] <= bottom + 1], 1.8)
        ys += [y for y in edges if y > ys[-1] + 3]
        hdr_row = max(r for r in range(len(ys) - 1) if ys[r] <= h[1] + 1)
        head_bottom = max(w[3] for w in words if abs(w[1] - h[1]) <= Y_TOL and xs[0] < w[0] < xs[-1])
        if hdr_row + 1 < len(ys) and ys[hdr_row + 1] - head_bottom > 6:
            ys.insert(hdr_row + 1, head_bottom + 1.0)      # no rule is drawn under the header: first vessel row follows it
        cols = len(xs) - 1
        cells: list[list[str]] = []
        used: set[int] = set()
        n_rows = len(ys) - 1
        nr = range(hdr_row + 1, n_rows)
        groups: dict[tuple[int, int], tuple[int, int]] = {}
        for c in range(cols):
            r = hdr_row + 1
            while r < n_rows:
                end = r
                while c >= MERGEABLE_FROM and end + 1 < n_rows and not _cell_boundary(horiz, vert, fills, ys[end + 1], xs[c] + 1, xs[c + 1] - 1):
                    end += 1
                for k in range(r, end + 1):
                    groups[(k, c)] = (r, end)
                r = end + 1
        text_cache: dict[tuple[int, int, int], str] = {}
        for k in nr:
            row = []
            for c in range(cols):
                r0, r1 = groups[(k, c)]
                key = (r0, r1, c)
                if key not in text_cache:
                    sel = [w for w in words if xs[c] < (w[0] + w[2]) / 2 < xs[c + 1] and ys[r0] < (w[1] + w[3]) / 2 < ys[r1 + 1]]
                    used.update(id(w) for w in sel)
                    text_cache[key] = " ".join(" ".join(x[4] for x in rr) for _, rr in _rows_by_y(sel))
                row.append(text_cache[key].strip())
            cells.append(row)
        head_words = [w for w in words if xs[0] < w[0] < xs[-1] and abs(w[1] - h[1]) <= Y_TOL]
        head = [" ".join(w[4] for w in sorted([x for x in head_words if xs[c] < (x[0] + x[2]) / 2 < xs[c + 1]], key=lambda x: x[0]))
                for c in range(cols)]
        for c, want in enumerate(SALES_HEADERS):
            if want and not head[c].upper().startswith(want):
                problems.append(f"sales_header_mismatch:{head[c]}")
        unit = head[1].upper() or "DWT"
        body = [w for w in words if xs[0] < (w[0] + w[2]) / 2 < xs[-1] and ys[hdr_row + 1] < (w[1] + w[3]) / 2 < ys[-1]]
        unassigned = sum(1 for w in body if id(w) not in used)
        rows = [r for r in cells if any(r)]
        empty_name = sum(1 for r in rows if not r[0])
        if empty_name:
            problems.append(f"sales_rows_without_name={empty_name}")
        rows = [r for r in rows if r[0]]
        odd = sum(1 for r in rows if not re.fullmatch(r"(?:19|20)\d{2}", r[2]) or not re.fullmatch(r"[0-9.,]+", r[1]))
        if odd:
            problems.append(f"sales_rows_with_unexpected_year_or_size={odd}")
        region = [w for w in words if xs[0] - 1 <= w[0] and w[2] <= xs[-1] + 1 and ys[0] - 1 <= w[1] and w[3] <= ys[-1] + 1]
        t = _table(section_title.title(), section_title, pno, ["Name", unit] + [c.title() for c in head[2:]], rows,
                   region or [h], unassigned)
        t["unit"] = unit
        t["sales_title"] = section_title
        tables.append(t)
    return tables, problems, last_title


# ------------------------------------------------------------------------------------------ sections
def section_label(title: str) -> str:
    t = re.sub(r"(?i)\s+SALES\b.*$", "", title).strip().title()
    return {"Bulk Carrier": "Bulk Carriers", "Tanker": "Tankers", "Container": "Containers",
            "General Cargo": "General Cargo", "Gas": "Gas", "Obo": "OBO"}.get(t, t)


def sales_rows_md(t: dict[str, Any], dry_tanker: bool) -> tuple[list[str], list[list[str]]]:
    label = section_label(t["sales_title"])
    if dry_tanker:
        cols = ["Section", "Name", "DWT", "Year", "Country", "Yard", "Buyers", "Price ($M)", "Comments"]
        rows = [[label] + r for r in t["rows"]]
    else:
        cols = ["Section", "Name", "Size", "Size Unit", "Year", "Country", "Yard", "Buyers", "Price ($M)", "Comments"]
        rows = [[label, r[0], r[1], t["unit"]] + r[2:] for r in t["rows"]]
    return cols, rows


WET_RE = re.compile(r"(?i)\b(?:tankers?|VLCCs?|Suezmax(?:es)?|Aframax(?:es)?|LR[12]|MR[12]?|dirty|clean|LPG|LNG|crude|chemicals?|wet|BDTI|BCTI)\b")
DRY_RE = re.compile(r"(?i)\b(?:dry|Capesize|Newcastlemax|Kamsarmax|Panamax|Ultramax|Supramax|Handysize|Handymax|bulkers?|bulk)\b")


def is_wet_paragraph(text: str) -> bool:
    """A paragraph is about the wet market when its opening sentence names a tanker/gas/wet term before any dry
    term ("The dry S&P market had more activity than wet" is dry; "Following the previous week's VLCC deals, ..."
    is wet)."""
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0][:250]
    wet, dry = WET_RE.search(first), DRY_RE.search(first)
    if wet and (dry is None or wet.start() < dry.start()):
        return True
    return len(WET_RE.findall(text)) > len(DRY_RE.findall(text))     # "Similarly to the dry market, the tanker ..."


def split_sp_commentary(paras: list[str]) -> tuple[list[str], list[str]]:
    """Dry paragraphs come first; the first paragraph that is about the wet market starts the tanker part."""
    for i, p in enumerate(paras):
        if is_wet_paragraph(p):
            return paras[:i], paras[i:]
    return paras, []


# ------------------------------------------------------------------------------------------ driver
def embedded_tables(page: pymupdf.Page, pno: int, limit_x: float) -> list[dict[str, Any]]:
    """Small untitled tables set into the left text column (header cell "PERIOD"): label + k numeric cells."""
    words = [w for w in _words(page) if (w[0] + w[2]) / 2 < limit_x]
    out: list[dict[str, Any]] = []
    for a in [w for w in words if w[4] == "PERIOD"]:
        rows = _rows_by_y([w for w in words if w[1] >= a[1] - 2 and w[0] >= a[0] - 25])
        if not rows:
            continue
        head = rows[0][1]
        body: list[list[tuple]] = []
        k = None
        prev_y = rows[0][0]
        for y, r in rows[1:]:
            label, nums = _split_label(r)
            if y - prev_y > 16 or len(nums) < 2 or not label or len(label.split()) > 2 or (k is not None and len(nums) != k):
                break
            k = len(nums)
            body.append(r)
            prev_y = y
        if not body or k is None:
            continue
        cells = [w for w in head if w is not a]
        gaps = sorted(range(1, len(cells)), key=lambda i: cells[i][0] - cells[i - 1][2], reverse=True)[: k - 1]
        cuts = sorted(gaps)
        starts = [i for i, w in enumerate(cells) if w[4] == cells[0][4]]
        if len(starts) == k:                      # every header cell opens with the same word ("Supramax ...")
            cuts = starts[1:]
        groups, start = [], 0
        for c in cuts + [len(cells)]:
            groups.append(" ".join(w[4] for w in cells[start:c]))
            start = c
        if len(groups) != k:
            continue
        rows_out = []
        for r in body:
            label, nums = _split_label(r)
            rows_out.append([label] + nums)
        used = head + [w for r in body for w in r]
        out.append(_table("Commentary Table - " + groups[0], "", pno, ["Period"] + groups, rows_out, used))
    return out


def chart_top(page: pymupdf.Page) -> float | None:
    """Top of the chart block: charts are placed images (or titled vector charts) in the lower half."""
    tops = [r[1] for r in (i["bbox"] for i in page.get_image_info()) if r[2] - r[0] > 150 and r[3] - r[1] > 100]
    return min(tops) if tops else None


def image_cluster_box(page: pymupdf.Page) -> tuple[float, float, float, float] | None:
    """Bounding box of a chart assembled from many small images (bars), set into the text column. Its label
    text is chart debris, not commentary."""
    boxes = [i["bbox"] for i in page.get_image_info()
             if i["bbox"][3] < page.rect.height - 60 and i["bbox"][1] > 60 and (i["bbox"][2] - i["bbox"][0]) < 120]
    if len(boxes) < 8:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


_VOCAB: set[str] | None = None
_VOCAB_DIR: Path | None = None
WORD_ONLY_RE = re.compile(r"[A-Za-z]{3,}")


def set_vocabulary(words: set[str] | None) -> None:
    global _VOCAB
    _VOCAB = words


def vocabulary() -> set[str]:
    """Lower-case words printed in one piece anywhere in the source's PDFs (no hyphen, so never a line-end split)."""
    global _VOCAB
    if _VOCAB is None:
        words: set[str] = set()
        for pdf in sorted(_VOCAB_DIR.rglob("*.pdf")) if _VOCAB_DIR else []:
            doc = pymupdf.open(pdf)
            for pno in range(min(5, len(doc))):
                words.update(w[4].lower() for w in doc[pno].get_text("words") if WORD_ONLY_RE.fullmatch(w[4]))
        _VOCAB = words
    return _VOCAB


def glue(out: str, nxt: str) -> str:
    """Join two text pieces across a line break. A line-end hyphen is a soft hyphen (dropped) only when the joined
    word is printed in one piece elsewhere in the corpus ("scrub-" + "ber"); otherwise the hyphen is part of the
    word and stays ("pre-" + "pandemic" -> "pre-pandemic", "de-" + "escalate")."""
    if out.endswith("-") and nxt[:1].isalpha():
        prev_tok = re.split(r"\s+", out)[-1]
        next_tok = nxt.split(" ")[0]
        if re.fullmatch(r"[A-Za-z]+-", prev_tok) and next_tok[:1].islower()                 and re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*[,.;:]?", next_tok):
            joined = (prev_tok[:-1] + re.match(r"[A-Za-z]+", next_tok).group(0)).lower()
            vocab = vocabulary()
            if not vocab or joined in vocab:
                return out[:-1] + nxt
        return out + nxt
    return out + " " + nxt


def join_lines(lines: list[Any]) -> str:
    out = lines[0].text
    for ln in lines[1:]:
        out = glue(out, ln.text)
    return re.sub(r"\*\*\s*\*\*", " ", re.sub(r"\s+", " ", out)).strip()


def join_paragraphs(paras: list[str]) -> list[str]:
    """A paragraph interrupted by a table or chart continues in the next one when it stops without terminal
    punctuation and the next starts in lower case (same rule as prose.render)."""
    out: list[str] = []
    for text in paras:
        if out and not out[-1].startswith("|") and not text.startswith("|") and prose._continues(out[-1], text):
            out[-1] = glue(out[-1], text)
        else:
            out.append(text)
    return out


SHORT_LINE = 30.0      # a line this much shorter than the column ends its paragraph when it ends a sentence


def split_paragraph(p: Any) -> list[tuple[float, str]]:
    """Some issues print consecutive paragraphs without a gap or indent (the tanker paragraph of the S&P
    commentary follows the dry one on the next line). A sentence-final line that stops well short of the column
    edge, followed by a line starting in capitals, is a paragraph end."""
    lines = p.lines
    if p.heading or len(lines) < 2:
        return [(p.bbox[1], p.text)]
    right = max(ln.bbox[2] for ln in lines)
    pieces: list[list[Any]] = [[lines[0]]]
    for prev, ln in zip(lines, lines[1:]):
        if prev.bbox[2] < right - SHORT_LINE and prev.plain.rstrip()[-1:] in ".!?" and ln.plain[:1].isupper():
            pieces.append([ln])
        else:
            pieces[-1].append(ln)
    return [(c[0].bbox[1], join_lines(c)) for c in pieces]


def _prose_paras(page: pymupdf.Page, pno: int, exclude: list[tuple], body: float, strip: list[re.Pattern]
                 ) -> list[tuple[float, str]]:
    out = []
    chart = image_cluster_box(page)
    for p in prose.page_prose(page, pno, exclude, set(), body):
        for y0, raw in split_paragraph(p):
            text = _plain(raw)
            if not text or CONTACT_LINE_RE.match(text) or any(r.search(text) for r in strip):
                continue
            if p.bbox[0] > 0.7 * page.rect.width and p.bbox[3] < 70:      # "Research & Valuations" under the logo
                continue
            if (chart and len(text) < 250 and chart[1] - 30 <= (p.bbox[1] + p.bbox[3]) / 2 <= chart[3] + 40
                    and chart[0] - 30 <= (p.bbox[0] + p.bbox[2]) / 2 <= chart[2] + 30):
                continue                                                  # label text of the bar chart
            out.append((y0, text))
    return out


def run(plan: Any, doc: pymupdf.Document, profile: dict[str, Any]) -> dict[str, Any]:
    drops = profile.get("drop_regions")
    strip = [re.compile(p) for p in (*profile.get("strip_line_patterns", []), *profile.get("boilerplate_patterns", []))]
    global _VOCAB_DIR
    if _VOCAB_DIR is None:
        _VOCAB_DIR = Path(plan.pdf).parent.parent
    body = prose.body_font_size(doc, plan.pages)
    commentary: list[str] = []
    dry_freight: list[str] = []
    wet_freight: list[str] = []
    sp_paras: list[str] = []
    panel: dict[str, dict[str, Any]] = {}
    sales: list[dict[str, Any]] = []
    all_tables: list[dict[str, Any]] = []
    problems: list[str] = []
    last_title: str | None = None
    for pno in plan.pages:
        page = doc[pno - 1]
        text = page.get_text()
        boxes = prose.drop_region_boxes(page, drops)
        y_max = min([b[1] for b in boxes] + [float(page.rect.height) - 50.0])
        x0 = panel_x0(page)
        exclude = list(boxes)
        ctop = chart_top(page) if "SECONDHAND PRICES" in text else None      # freight pages: charts under the text
        if ctop is not None:
            exclude.append((0.0, ctop - 2.0, float(page.rect.width), float(page.rect.height)))
            y_max = min(y_max, ctop)
        ptables: list[dict[str, Any]] = []
        if x0 is not None:
            ptables, pp = panel_tables(page, pno, x0, y_max)
            problems += pp
            exclude.append((x0 - 1.0, 0.0, float(page.rect.width), float(page.rect.height)))
        stables, sp, last_title = sales_tables(page, pno, last_title)
        problems += sp
        for t in stables:
            exclude.append((t["bbox"][0] - 2, t["bbox"][1] - 4, t["bbox"][2] + 2, t["bbox"][3] + 2))
        for t in ptables:
            panel[t["name"]] = t
        sales += stables
        for title in re.findall(r"(?m)^([A-Z][A-Z/& ]*? SALES(?:/ MPP)?)\s*$", text):
            if not any(t["sales_title"].strip() == title.strip() for t in stables):
                problems.append(f"sales_table_not_extracted:{title.strip()}")
        all_tables += ptables + stables
        etables = embedded_tables(page, pno, x0 if x0 is not None else float(page.rect.width))
        for t in etables:
            exclude.append((t["bbox"][0] - 2, t["bbox"][1] - 2, t["bbox"][2] + 2, t["bbox"][3] + 2))
        all_tables += etables
        items = _prose_paras(page, pno, exclude, body, strip)
        items += [(t["bbox"][1], render_table(t["columns"], t["rows"])) for t in etables]
        paras = join_paragraphs([text for _, text in sorted(items, key=lambda it: it[0])])
        if "DRY SECONDHAND PRICES" in text:
            dry_freight += paras
        elif "WET SECONDHAND PRICES" in text:
            wet_freight += paras
        elif re.search(r"(?m)^Sale and Purchase:", text):
            sp_paras += paras
        elif pno == plan.pages[0]:
            commentary += paras
        elif paras:
            problems.append(f"unplaced_prose_p{pno}:{len(paras)}:{paras[0][:50]}")
    if commentary and re.fullmatch(r"(?i)market commentary:?", commentary[0]):
        commentary = commentary[1:]
    title = "Market Commentary:"
    if commentary:
        m = re.match(r"(?i)(market commentary:?)\s*", commentary[0])
        if m:
            title = m.group(1) if m.group(1).endswith(":") else m.group(1) + ":"
            commentary[0] = commentary[0][m.end():]
    if sp_paras and re.fullmatch(r"(?i)sale and purchase:?", sp_paras[0]):
        sp_paras = sp_paras[1:]
    elif sp_paras:
        sp_paras[0] = re.sub(r"(?i)^sale and purchase:\s*", "", sp_paras[0])
    dry_sp, wet_sp = split_sp_commentary(sp_paras)

    md: list[str] = []

    def heading(level: int, text: str) -> None:
        md.append("#" * level + " " + text)

    heading(2, "Market Overview")
    if commentary:
        heading(3, f"Editorial: {title}")
        md += commentary
    idx = [panel[k] for k in ("Baltic Dry Indices", "Baltic Tanker Indices") if k in panel]
    if idx:
        heading(3, "Baltic Exchange Freight Indices")
        md.append(render_table(idx[0]["columns"], [r for t in idx for r in t["rows"]]))
    heading(2, "Freight Market Analysis")
    if dry_freight:
        heading(3, "Dry Bulk Freight")
        md += dry_freight
    if wet_freight:
        heading(3, "Tanker Freight")
        md += wet_freight
    nb = [panel[k] for k in ("Dry Newbuilding Prices", "Tanker Newbuilding Prices") if k in panel]
    if nb:
        heading(2, "Newbuilding Market")
        heading(3, "Indicative Newbuilding Prices ($ mills)")
        md.append(render_table(nb[0]["columns"], [r for t in nb for r in t["rows"]]))
    heading(2, "Sale & Purchase Market")
    bulk = [t for t in sales if section_label(t["sales_title"]) == "Bulk Carriers"]
    tank = [t for t in sales if section_label(t["sales_title"]) == "Tankers"]
    other = [t for t in sales if t not in bulk and t not in tank]
    if "Dry Secondhand Prices" in panel:
        t = panel["Dry Secondhand Prices"]
        heading(3, "Dry Secondhand Prices ($ mills)")
        md.append(render_table(t["columns"], t["rows"]))
    if dry_sp:
        heading(3, "Dry S&P Activity Commentary")
        md += dry_sp
    if bulk:
        heading(3, "Bulk Carrier Sales")
        md.append(render_table(sales_rows_md(bulk[0], True)[0], [r for t in bulk for r in sales_rows_md(t, True)[1]]))
    if "Tanker Secondhand Prices" in panel:
        t = panel["Tanker Secondhand Prices"]
        heading(3, "Tanker Secondhand Prices ($ mills)")
        md.append(render_table(t["columns"], t["rows"]))
    if wet_sp:
        heading(3, "Tanker S&P Activity Commentary")
        md += wet_sp
    if tank:
        heading(3, "Tanker Sales")
        md.append(render_table(sales_rows_md(tank[0], True)[0], [r for t in tank for r in sales_rows_md(t, True)[1]]))
    if other:
        heading(3, "Other Reported Sales (Gas / Containers)")
        md.append(render_table(sales_rows_md(other[0], False)[0], [r for t in other for r in sales_rows_md(t, False)[1]]))
    if "Demolition Prices" in panel:
        t = panel["Demolition Prices"]
        heading(2, "Demolition Market")
        heading(3, "Indicative Demolition Scrap Prices ($/LDT)")
        md.append(render_table(t["columns"], t["rows"]))

    # the md tables are the emitted tables: sales tables are replaced by their target-layout form
    for t in all_tables:
        if "sales_title" in t:
            t["columns"], t["rows"] = sales_rows_md(t, section_label(t["sales_title"]) in ("Bulk Carriers", "Tankers"))
            t["name"] = {"Bulk Carriers": "Bulk Carrier Sales", "Tankers": "Tanker Sales"}.get(
                section_label(t["sales_title"]), "Other Reported Sales - " + section_label(t["sales_title"]))
        t["empty"] = not t["rows"]
    return {
        "markdown": "\n\n".join(md), "tables": all_tables, "parser": "pymupdf_table + xclusiv_template",
        "api": "local", "tier": None, "credits_used": 0, "parsed_at": None, "problems": problems,
        "counts": {"dry_freight_paras": len(dry_freight), "wet_freight_paras": len(wet_freight),
                   "commentary_paras": len(commentary), "dry_sp_paras": len(dry_sp), "wet_sp_paras": len(wet_sp)},
    }
