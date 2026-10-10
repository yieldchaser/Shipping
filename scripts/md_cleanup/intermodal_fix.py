"""Targeted cell-level fixer for Intermodal weekly markdown (data/extracted/md/intermodal).

The Intermodal MD prose is owner-audited and hand-perfected; chart-derived tables are left
byte-identical. This tool repairs ONLY three table defect classes; every other byte
(including line endings) is preserved. Nothing is re-parsed from scratch.

* fill_down      - "Newbuilding Orders" and "Secondhand Sales" tables: a PDF cell that vertically
                   spans several rows was written in one MD row only. A blank MD cell is filled
                   ONLY when the PDF geometry proves it: the row separators (horizontal ruling
                   lines) of that column bound a block of >= 2 rows with no rule inside, the
                   printed text block of that column lies inside the block, is vertically centred
                   in it, and equals the MD anchor cell. The text is copied from the MD anchor
                   cell (PDF text has kerning gaps), never from the PDF. A $-price spanning more
                   than one row is written "<value> (en bloc)" in every spanned row including the
                   anchor row; "undisclosed" is filled plain. A non-empty cell is never changed
                   (except for that en-bloc suffix).
* nb_prices      - "Indicative Newbuilding Prices" table: mislabelled heading, many schema
                   variants, gas rows shifted one column left. Rebuilt to one schema
                   `Sector | Vessel | Size | <header cells printed in the PDF>`. Guards: the
                   multiset of digit-bearing tokens of the rebuilt table must equal that of the
                   old table (header rows ignored) AND every row's size/values must be located,
                   in order, on the matching PDF row; otherwise the table is left unchanged and
                   reported as unresolved.
* demolition_ldt - demolition sales `$/Ldt` cell printed by the publisher as "$ 580.0m":
                   rewritten "$ 580/Ldt" (owner decision) when 100 <= value <= 1500 and the
                   token is located in the PDF text layer.

Source markdown is never modified: fixed copies go to .reparse_staging/intermodal_fix/.

Usage:
    python -m scripts.md_cleanup.intermodal_fix [--detect-only] [--limit N] [--years 2025,2026]
    python -m scripts.md_cleanup.intermodal_fix --promote            # dry-run list (default)
    python -m scripts.md_cleanup.intermodal_fix --promote --apply    # copy changed files
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")
MD_ROOT_REL = Path("data/extracted/md/intermodal")
STAGING_REL = Path(".reparse_staging/intermodal_fix")
PDF_ROOT_REL = Path("corpus/01-brokers/intermodal")

CRLF = chr(13) + chr(10)
LF = chr(10)
PLUS_MINUS = "\u00b1"
NB_HEADING = "## Indicative Newbuilding Prices ($ Million)"
EN_BLOC = "(en bloc)"
SECTORS = {"bulkers": "Bulkers", "tankers": "Tankers", "gas": "Gas"}
GAS_PREFIX = ("lng", "lgc", "mgc", "sgc", "vlgc")
STRIP_PAD = 12.0            # half width of the column centre strip a rule must cover
TEXT_SIM = 0.85             # anchor vs printed text: tolerates one-character typos in the PDF text layer
CENTRE_TOL = 0.25           # text centre may differ from block centre by this many row pitches
                            # (printed merged cells sit within ~0.05; 0.5 would accept text centred on one row)


class FixError(Exception):
    pass


# ---------------------------------------------------------------- text helpers
def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compact(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def split_row(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [c.strip() for c in body.split("|")]


def join_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def is_sep(line: str) -> bool:
    return bool(re.match(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$", line.strip()))


def clean_cell(text: str) -> str:
    """A table cell as printed: HTML entities, markdown escapes and bold/italic markup removed."""
    t = html.unescape(text).replace(chr(92), "")
    return squash(t.replace("*", ""))


def has_digit(token: str) -> bool:
    return any(ch.isdigit() for ch in token)


def digit_tokens(cells: list[str]) -> Counter:
    return Counter(tok for c in cells for tok in c.split() if has_digit(tok))


# ---------------------------------------------------------------- PDF model
def page_spans(page) -> list[dict]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            rot = abs(ln["dir"][0]) < 0.9
            for s in ln["spans"]:
                if s["text"].strip():
                    x0, y0, x1, y1 = s["bbox"]
                    out.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "xc": (x0 + x1) / 2,
                                "yc": (y0 + y1) / 2, "text": s["text"], "size": s["size"], "rot": rot})
    return out


def join_spans(spans: list[dict]) -> str:
    """Spans of one printed line, left to right; a space only where the PDF has a gap."""
    out = ""
    prev = None
    for s in sorted(spans, key=lambda s: s["x0"]):
        if prev is not None and s["x0"] - prev["x1"] >= 1.5 \
                and not out.endswith(" ") and not s["text"].startswith(" "):
            out += " "
        out += s["text"]
        prev = s
    return squash(out)


def group_lines(spans: list[dict], tol: float = 3.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for s in sorted(spans, key=lambda s: (s["yc"], s["x0"])):
        if lines and abs(statistics.mean(x["yc"] for x in lines[-1]) - s["yc"]) <= tol:
            lines[-1].append(s)
        else:
            lines.append([s])
    return lines


def _white(color) -> bool:
    return color is None or all(c >= 0.95 for c in color)


def page_rules(page) -> list[dict]:
    """Horizontal rules: [{y, ivs:[(x0, x1)]}], strokes and thin non-white filled rectangles,
    same-y segments merged into intervals."""
    segs = []
    for d in page.get_drawings():
        color = d.get("color") if "s" in d["type"] else d.get("fill")
        if _white(color):
            continue
        for it in d["items"]:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) <= 0.6 and abs(p1.x - p2.x) >= 3:
                    segs.append(((p1.y + p2.y) / 2, min(p1.x, p2.x), max(p1.x, p2.x)))
            elif it[0] == "re":
                r = it[1]
                if r.height <= 1.6 and r.width >= 3:
                    segs.append(((r.y0 + r.y1) / 2, r.x0, r.x1))
    segs.sort()
    rules: list[dict] = []
    for y, x0, x1 in segs:
        if rules and abs(rules[-1]["y"] - y) <= 0.8:
            rules[-1]["raw"].append((x0, x1))
        else:
            rules.append({"y": y, "raw": [(x0, x1)]})
    for r in rules:
        ivs: list[list[float]] = []
        for x0, x1 in sorted(r.pop("raw")):
            if ivs and x0 <= ivs[-1][1] + 3:
                ivs[-1][1] = max(ivs[-1][1], x1)
            else:
                ivs.append([x0, x1])
        r["ivs"] = [(a, b) for a, b in ivs]
    return rules


def rule_covers(rule: dict, lo: float, hi: float) -> bool:
    return any(a <= lo + 1 and b >= hi - 1 for a, b in rule["ivs"])


class Pdf:
    """Lazy per-page cache over a pymupdf document."""

    def __init__(self, doc):
        self.doc = doc
        self._spans: dict[int, list[dict]] = {}
        self._rules: dict[int, list[dict]] = {}

    def __len__(self):
        return len(self.doc)

    def spans(self, i: int) -> list[dict]:
        if i not in self._spans:
            self._spans[i] = page_spans(self.doc[i])
        return self._spans[i]

    def rules(self, i: int) -> list[dict]:
        if i not in self._rules:
            self._rules[i] = page_rules(self.doc[i])
        return self._rules[i]


# ---------------------------------------------------------------- markdown tables
def md_tables(lines: list[str]) -> list[dict]:
    out, i = [], 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and is_sep(lines[i + 1]):
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append((j, split_row(lines[j])))
                j += 1
            out.append({"head": i, "hdr": split_row(lines[i]), "rows": rows, "end": j})
            i = j
        else:
            i += 1
    return out


COL_KEYS = sorted(["size", "name", "dwt", "teu", "built", "yard", "me", "ssdue", "gear", "hull", "price",
                   "buyers", "buyer", "comments", "type", "cbm", "units", "delivery", "ss"],
                  key=len, reverse=True)


def col_key(header_cell: str) -> str | None:
    """Canonical column of a header cell; a section prefix ("Bulk Carriers Size") is ignored."""
    c = compact(clean_cell(header_cell))
    for k in COL_KEYS:
        if c == k or (c.endswith(k) and k not in ("ss",)):
            return k
    return "ss" if c == "ss" else None


def table_kind(t: dict) -> tuple[str, list[str]] | None:
    keys = [col_key(h) for h in t["hdr"]]
    if any(k is None for k in keys):
        return None
    if keys in (["units", "type", "size", "yard", "delivery", "buyer", "price"],
                ["units", "type", "size", "yard", "delivery", "buyer", "price", "comments"]):
        return "nb_orders", keys
    if {"name", "yard", "price"} <= set(keys) and len(set(keys)) == len(keys):
        return "sh_sales", keys
    return None


def edit_cell(lines: list[str], idx: int, col: int, new: str) -> str | None:
    """Set one cell of a table row in place; the row must be in canonical `| a | b |` form so every
    other byte is preserved. Returns the old cell text, or None if the row cannot be edited."""
    cells = split_row(lines[idx])
    if join_row(cells) != lines[idx] or col >= len(cells):
        return None
    old = cells[col]
    cells[col] = new
    lines[idx] = join_row(cells)
    return old


def is_label_row(cells: list[str]) -> bool:
    return bool(clean_cell(cells[0])) and not any(clean_cell(c) for c in cells[1:])


# ---------------------------------------------------------------- class 1: fill-down
def header_candidates(spans: list[dict], keys: list[str]) -> list[list[dict]]:
    out = []
    for ln in group_lines([s for s in spans if not s["rot"]], 3.0):
        ln = sorted(ln, key=lambda s: s["x0"])
        names = [compact(s["text"]) for s in ln]
        if len(ln) >= len(keys) and names[:len(keys)] == keys and set(names[len(keys):]) <= {"comments"}:
            out.append(ln)       # the MD may lack the trailing Comments column the PDF prints
    return out


def map_rows(spans: list[dict], hdr: list[dict], texts: list[str], key_cols: list[int], rules: list[dict]):
    """Locate every MD row on the PDF page. Returns (key_col, [(first_yc, last_yc)]), the string
    "unruled" when the rows were found but the key column has no ruling line between two of them
    (then they are not provably separate table rows, e.g. one vessel name wrapped over two lines
    split into two MD rows), or None. Rows are located by consuming the printed lines of one key
    column in order until their kerning-insensitive text equals the MD cell."""
    unruled = False
    hcx = [s["xc"] for s in hdr]
    hdr_bottom = max(s["y1"] for s in hdr)
    below = [s for s in spans if not s["rot"] and s["y0"] > hdr_bottom - 0.5 and s not in hdr]
    for kc in key_cols:
        col = [s for s in below if min(range(len(hcx)), key=lambda i: abs(hcx[i] - s["xc"])) == kc]
        plines = [(statistics.mean(s["yc"] for s in ln), compact(join_spans(ln)))
                  for ln in group_lines(col, 3.0)]
        pos, rows, ok = 0, [], True
        for target in texts[kc]:
            acc, first, last = "", None, None
            while pos < len(plines) and acc != target and target.startswith(acc):
                first = plines[pos][0] if first is None else first
                last = plines[pos][0]
                acc += plines[pos][1]
                pos += 1
            if acc != target or first is None:
                ok = False
                break
            rows.append((first, last))
        if ok and all(rows[i][1] < rows[i + 1][0] for i in range(len(rows) - 1)):
            ruled = [r["y"] for r in rules if rule_covers(r, hcx[kc] - STRIP_PAD, hcx[kc] + STRIP_PAD)]
            if all(any(rows[i][1] < y < rows[i + 1][0] for y in ruled) for i in range(len(rows) - 1)):
                return kc, rows
            unruled = True
    return "unruled" if unruled else None


def analyse_fill(pdf: Pdf, page_i: int, hdr: list[dict], rows_y, kc: int, cells_by_row: list[list[str]],
                 raw_by_row: list[list[str]], keys: list[str]) -> tuple[list[dict], list[dict]]:
    """Blocks of >= 2 rows in each non-key column; returns (fills, unresolved)."""
    spans = [s for s in pdf.spans(page_i) if not s["rot"]]
    rules = pdf.rules(page_i)
    hcx = [s["xc"] for s in hdr]
    hdr_bottom = max(s["y1"] for s in hdr)
    nrows = len(rows_y)
    fills, unres = [], []
    for c in range(len(keys)):
        if c == kc:
            continue
        lo_x, hi_x = hcx[c] - STRIP_PAD, hcx[c] + STRIP_PAD
        crules = [r["y"] for r in rules if rule_covers(r, lo_x, hi_x)]

        def gap_rule(r):
            lo, hi = rows_y[r][1], rows_y[r + 1][0]
            mid = (lo + hi) / 2
            cand = [y for y in crules if lo < y < hi]
            return min(cand, key=lambda y: abs(y - mid)) if cand else None

        seps = [gap_rule(r) for r in range(nrows - 1)]
        a = 0
        while a < nrows:
            b = a
            while b + 1 < nrows and seps[b] is None:
                b += 1
            if b > a:
                top = hdr_bottom if a == 0 else seps[a - 1]
                if b + 1 < nrows:
                    bottom = seps[b]
                else:
                    below_last = [y for y in crules if rows_y[b][1] < y < rows_y[b][1] + 80]
                    bottom = min(below_last) if below_last else None
                res = _block(spans, hcx, c, a, b, top, bottom, cells_by_row, raw_by_row, keys)
                if res:
                    (fills if res.get("fill") else unres).append(res)
            a = b + 1
    return fills, unres


def _block(spans, hcx, c, a, b, top, bottom, cells_by_row, raw_by_row, keys):
    texts = [clean_cell(cells_by_row[r][c]) for r in range(a, b + 1)]
    blanks = [a + i for i, t in enumerate(texts) if not t]
    if not blanks:
        return None
    anchors = {t for t in texts if t}
    if len(anchors) > 1:
        return None
    if bottom is None:
        return {"col": c, "rows": [a, b], "reason": "no rule below the block: extent not provable"}
    col = [s for s in spans if min(range(len(hcx)), key=lambda i: abs(hcx[i] - s["xc"])) == c
           and top < s["yc"] < bottom]
    if not anchors:
        if col:
            return {"col": c, "rows": [a, b], "reason": "PDF text in merged block but no MD anchor cell"}
        return None
    if not col:
        return {"col": c, "rows": [a, b], "reason": "MD anchor cell has no printed text in the merged block"}
    anchor = anchors.pop()
    if any(s["y0"] < top - 1 or s["y1"] > bottom + 1 for s in col):
        return {"col": c, "rows": [a, b], "reason": "printed text crosses the block boundary"}
    pdf_text = compact(" ".join(join_spans(ln) for ln in group_lines(col, 3.0)))
    similarity = SequenceMatcher(None, pdf_text, compact(anchor)).ratio()
    if similarity < TEXT_SIM:
        return {"col": c, "rows": [a, b],
                "reason": f"anchor '{anchor}' differs from printed block text '{join_spans(col)[:60]}'"}
    ymin, ymax = min(s["y0"] for s in col), max(s["y1"] for s in col)
    pitch = (bottom - top) / (b - a + 1)
    if abs((ymin + ymax) / 2 - (top + bottom) / 2) > CENTRE_TOL * pitch:
        return {"col": c, "rows": [a, b], "reason": "printed text is not centred in the block"}
    anchor_raw = next(raw_by_row[r][c] for r in range(a, b + 1) if clean_cell(raw_by_row[r][c]))
    new = anchor_raw      # the anchor cell exactly as the MD writes it (entities, markup)
    en_bloc = (keys[c] == "price" and "$" in anchor and has_digit(anchor)
               and not re.search(r"\beach\b", anchor, re.I))     # "$ 14.5m each" is already a per-ship price
    if en_bloc and not re.search(r"en[\s-]?bloc", anchor, re.I):     # "$ 42.0m enbloc" is already labelled
        new = f"{anchor_raw} {EN_BLOC}"
    return {"fill": True, "col": c, "rows": [a, b], "blanks": blanks, "anchor": anchor, "new": new,
            "en_bloc": en_bloc and new != anchor_raw, "similarity": round(similarity, 3),
            "bbox": [round(min(s["x0"] for s in col), 1), round(ymin, 1),
                     round(max(s["x1"] for s in col), 1), round(ymax, 1)],
            "rule_above": round(top, 1), "rule_below": round(bottom, 1)}


def fix_fill_table(lines: list[str], pdf: Pdf, t: dict, kind: str, keys: list[str],
                   changes: list[dict], unresolved: list[dict]) -> None:
    n = len(keys)
    data = [(idx, cells) for idx, cells in t["rows"] if not is_label_row(cells)]
    if len(data) < 2:
        return
    if any(len(cells) != n for _, cells in data):
        unresolved.append({"line": t["head"] + 1, "class": "fill_down", "reason": "row cell count differs from header"})
        return
    cleaned = [[clean_cell(c) for c in cells] for _, cells in data]
    if not any(not v for row in cleaned for v in row):
        return
    key_cols = [i for i in sorted(range(n), key=lambda i: ({"name": 0, "type": 1, "units": 2, "size": 3}.get(keys[i], 9), i))
                if all(row[i] for row in cleaned)]
    texts = [[compact(row[i]) for row in cleaned] for i in range(n)]
    found, unruled = None, False
    for page_i in range(len(pdf)):
        for hdr in header_candidates(pdf.spans(page_i), keys):
            m = map_rows(pdf.spans(page_i), hdr, texts, key_cols, pdf.rules(page_i))
            if m == "unruled":
                unruled = True
            elif m:
                found = (page_i, hdr, m)
                break
        if found:
            break
    if not found:
        unresolved.append({"line": t["head"] + 1, "class": "fill_down", "reason": (
            "MD rows are not separated by ruling lines in the PDF key column (a PDF row is split over several MD rows)"
            if unruled else "table not located on a single PDF page (header/rows do not match)")})
        return
    page_i, hdr, (kc, rows_y) = found
    fills, unres = analyse_fill(pdf, page_i, hdr, rows_y, kc, cleaned, [cells for _, cells in data], keys)
    for u in unres:
        unresolved.append({"line": data[u["rows"][0]][0] + 1, "class": "fill_down",
                           "reason": u["reason"], "column": t["hdr"][u["col"]]})
    for f in fills:
        c = f["col"]
        touched = f["blanks"] + ([r for r in range(f["rows"][0], f["rows"][1] + 1)
                                  if f["en_bloc"] and r not in f["blanks"]])
        for r in sorted(touched):
            idx = data[r][0]
            old = edit_cell(lines, idx, c, f["new"])
            if old is None:
                unresolved.append({"line": idx + 1, "class": "fill_down", "reason": "row is not in canonical form"})
                continue
            changes.append({"line": idx + 1, "class": "fill_down", "column": t["hdr"][c], "old": old,
                            "new": f["new"], "pdf_evidence": {
                                "page": page_i + 1, "bbox": f["bbox"], "rule_above_y": f["rule_above"],
                                "rule_below_y": f["rule_below"],
                                "rows_spanned": [data[x][0] + 1 for x in range(f["rows"][0], f["rows"][1] + 1)],
                                "text_similarity": f["similarity"],
                                "en_bloc_anchor": bool(f["en_bloc"] and r not in f["blanks"])}})


# ---------------------------------------------------------------- class 3: demolition $/Ldt
LDT_CELL = re.compile(r"^(?P<pre>(?:[A-Za-z/\-]+ )*)\$ ?(?P<int>\d+)\.0+m$")


def locate_token(pdf: Pdf, needle: str) -> tuple[int, list[float]] | None:
    """Page and bbox of `needle` printed under a `$/ldt` column header (not inside a longer
    number such as 1580.0m, and not in another table's price column)."""
    pat = re.compile(r"(?<![\d.,])\$?" + re.escape(needle) + r"(?![\d])")
    for i in range(len(pdf)):
        spans = [s for s in pdf.spans(i) if not s["rot"]]
        heads = [s for s in spans if "/ldt" in s["text"].replace(" ", "").lower()]
        if not heads:
            continue
        for ln in group_lines(spans, 3.0):
            for s in ln:
                if not pat.search(s["text"].replace(" ", "")):
                    continue
                xc = (s["x0"] + s["x1"]) / 2
                if any(h["y1"] <= s["y0"] and h["x0"] - 25 <= xc <= h["x1"] + 25 for h in heads):
                    return i, [round(s["x0"], 1), round(s["y0"], 1), round(s["x1"], 1), round(s["y1"], 1)]
    return None


def fix_demolition(lines: list[str], pdf: Pdf, t: dict, changes: list[dict], unresolved: list[dict]) -> None:
    cols = [i for i, h in enumerate(t["hdr"]) if "$/ldt" in h.lower()]
    if not cols:
        return
    for idx, cells in t["rows"]:
        for c in cols:
            if c >= len(cells):
                continue
            m = LDT_CELL.match(cells[c])
            if not m or not 100 <= int(m["int"]) <= 1500:
                continue
            loc = locate_token(pdf, f"{m['int']}.0m")
            if loc is None:
                unresolved.append({"line": idx + 1, "class": "demolition_ldt",
                                   "reason": f"'{cells[c]}' not found in the PDF text layer"})
                continue
            new = f"{m['pre']}$ {m['int']}/Ldt"
            if edit_cell(lines, idx, c, new) is None:
                unresolved.append({"line": idx + 1, "class": "demolition_ldt", "reason": "row is not in canonical form"})
                continue
            changes.append({"line": idx + 1, "class": "demolition_ldt", "column": t["hdr"][c], "old": cells[c],
                            "new": new, "pdf_evidence": {
                                "page": loc[0] + 1, "bbox": loc[1],
                                "note": f"PDF prints '$ {m['int']}.0m' in $/Ldt column; normalised per owner decision"}})


# ---------------------------------------------------------------- class 2: NB prices
DATE_RE = re.compile(r"^\d{1,2}[/-](?:\d{1,2}|[A-Za-z]{3})[/-]\d{2,4}$")
ADD_RE = re.compile(r"^-?\d+(\.\d+)?%?$")      # a value cell that may be added from the PDF
ADD_X_SPREAD = 14.0         # added cells of one column may differ in centre x by this much (points)
SIZE_RE = re.compile(r"^\d+(?:\.\d+)?k$", re.I)


def norm_pm(token: str) -> str:
    """The PDF prints the plus/minus sign with a glyph that extracts as a replacement char."""
    return PLUS_MINUS + "%" if re.fullmatch(r"[^\w\s%.]%", token) else token


def is_header_row(cc: list[str]) -> bool:
    return any(DATE_RE.match(c) for c in cc[1:]) or compact(cc[0]) in ("vessel", "sector", "tenor", "size")


def parse_nb_old(t: dict) -> list[dict]:
    """Logical rows of the old table: {sector_md, vessel, size, values, cells}."""
    rows, cur = [], None
    for idx, cells in t["rows"]:
        cc = [clean_cell(c) for c in cells]
        nonempty = [c for c in cc if c]
        if not nonempty or is_header_row(cc):
            continue
        if len(nonempty) == 1 and compact(nonempty[0]) in SECTORS:
            cur = SECTORS[compact(nonempty[0])]
            continue
        if compact(cc[0]) in SECTORS:
            cur, rest = SECTORS[compact(cc[0])], cc[1:]
        elif cc[0] == "":
            rest = cc[1:]
        else:
            rest = cc
        while rest and not rest[0]:
            rest = rest[1:]
        if not rest:
            continue
        vessel, rest = rest[0], rest[1:]
        if rest and SIZE_RE.match(rest[0]):
            size, vals = rest[0], [v for v in rest[1:] if v]
        else:
            size, vals = "", [v for v in rest if v]
        rows.append({"line": idx, "sector_md": cur, "vessel": vessel, "size": size, "values": vals, "cells": cc})
    return rows


def nb_table_candidate(t: dict) -> bool:
    flat = [clean_cell(c) for _, cells in t["rows"] for c in cells]
    hdr = [compact(clean_cell(h)) for h in t["hdr"]]
    return ("units" not in hdr and any("cbm" in c.lower() for c in flat)
            and any(compact(c) in ("capesize", "vlcc", "newcastlemax") for c in flat))


def nb_pdf_check(pdf: Pdf, rows: list[dict]):
    """Locate the table on the PDF and every row, in order. The old values of a row must be the
    leading value cells of the PDF row (same row, same column position); further numeric cells printed
    on that PDF row are "added" values (the old MD dropped trailing columns). The printed title is
    optional (some PDFs draw it without a text layer). Returns
    (page_i, title_line_or_None, row_info, header_spans, labels, n_vals) or raises FixError."""
    last_err = "no PDF page carries the table rows"
    for pi in range(len(pdf)):
        spans = [s for s in pdf.spans(pi) if not s["rot"]]
        plines = group_lines(spans, 3.0)
        title = next((ln for ln in plines if "indicativenewbuildingprices" in compact(join_spans(ln))), None)
        info, prev_y = [], (statistics.mean(s["yc"] for s in title) if title else -1e9)
        try:
            for r in rows:
                old, hit, near = r["values"], None, None
                for ln in plines:
                    y = statistics.mean(s["yc"] for s in ln)
                    if y <= prev_y + 0.5:
                        continue
                    toks = [(tok, s) for s in sorted(ln, key=lambda s: s["x0"]) for tok in s["text"].split()]
                    tt = [norm_pm(t) for t, _ in toks]
                    for j in range(len(tt)):
                        if not compact("".join(tt[:j])).endswith(compact(r["vessel"])) or not tt[:j]:
                            continue
                        k = j + (1 if r["size"] else 0)
                        if r["size"] and tt[j] != r["size"]:
                            continue
                        if tt[k:k + len(old)] != old:
                            near = f"row '{r['vessel']}': old values are not the leading cells of the PDF row "                                    "(a value is missing or in another column)"
                            continue
                        extra = []
                        for tok in tt[k + len(old):]:
                            if not ADD_RE.match(tok):
                                break
                            extra.append(tok)
                        n_all = len(old) + len(extra)
                        hit = (y, [s for _, s in toks[k:k + n_all]], [s for _, s in toks[:j]], tt[k:k + n_all])
                        break
                    if hit:
                        break
                if hit is None:
                    raise FixError(near or f"row '{r['vessel']}': size/values not found in order on a PDF row")
                prev_y = hit[0]
                info.append({"y": hit[0], "val_spans": hit[1], "name_spans": hit[2], "values": hit[3],
                             "n_old": len(old)})
        except FixError as exc:
            if info or "leading cells" in str(exc) or last_err.startswith("no PDF page"):
                last_err = str(exc)      # an error from a page that holds some rows beats "not found"
            continue
        # Prose printed beside the table can start with a number and look like one more value cell, but only
        # on some rows: the table's width is the narrowest numeric run, never wider than what every row prints.
        n_vals = min(len(i["values"]) for i in info)
        if n_vals < max(i["n_old"] for i in info):
            last_err = ("PDF rows print differing numbers of value cells "
                        f"{sorted(Counter(len(i['values']) for i in info).items())}")
            continue
        for i in info:
            i["values"], i["val_spans"] = i["values"][:n_vals], i["val_spans"][:n_vals]
        added_cols = {c for i in info for c in range(i["n_old"], n_vals)}
        if any(max(i["val_spans"][c]["xc"] for i in info if c >= i["n_old"])
               - min(i["val_spans"][c]["xc"] for i in info if c >= i["n_old"]) > ADD_X_SPREAD for c in added_cols):
            last_err = "added value cells are not aligned in one PDF column"
            continue
        left = min(min(s["x0"] for s in i["name_spans"] or i["val_spans"]) for i in info) - 40
        right = max(max(s["x1"] for s in i["val_spans"]) for i in info) + 4
        top = title[0]["y1"] - 0.5 if title else info[0]["y"] - 50
        hdr = [s for s in spans if top <= s["y0"] and s["yc"] < info[0]["y"] - 3
               and s["x0"] >= left and s["x1"] <= right + 4 and not (title and s in title)]
        labels = [s for s in pdf.spans(pi) if s["rot"] and compact(s["text"]) in SECTORS
                  and info[0]["y"] - 25 <= s["yc"] <= info[-1]["y"] + 25]
        return pi, title, info, hdr, labels, n_vals
    raise FixError(last_err)


def _merge_words(words: list[dict]) -> list[dict]:
    """Glue header spans of one printed word that the PDF split (kerning gaps: "28-J ul-23")."""
    out: list[dict] = []
    for w in sorted(words, key=lambda w: (round(w["yc"]), w["x0"])):
        if out and abs(out[-1]["yc"] - w["yc"]) <= 1.5 and w["x0"] - out[-1]["x1"] <= 3:
            prev = out[-1]
            prev.update({"text": prev["text"].rstrip() + w["text"].lstrip(), "x1": w["x1"]})
            prev["xc"] = (prev["x0"] + prev["x1"]) / 2
        else:
            out.append(dict(w))
    return out


def header_text(text: str) -> str:
    t = norm_pm(squash(text))
    return t.replace(" ", "") if DATE_RE.match(t.replace(" ", "")) else t


def nb_header(hdr_words: list[dict], info: list[dict], old_hdr: list[str], n_vals: int) -> list[str]:
    """Value-column header cells as printed. The lowest header line holds the leaf cells; a word
    printed above and overlapping leaf cells is a group header (YTD, 5-year, Average) and prefixes
    them (`Average 2023`, so annual averages are not read as point values). A word with no
    leaf below it is the header of the column it is centred on (dates, plus/minus)."""
    vcx = [statistics.median(i["val_spans"][j]["xc"] for i in info) for j in range(n_vals)]
    step = (vcx[1] - vcx[0]) if n_vals > 1 else 40.0
    words = _merge_words([w for w in hdr_words if w["xc"] >= vcx[0] - 0.8 * step])

    def nearest(w):
        return min(range(n_vals), key=lambda j: abs(vcx[j] - w["xc"]))
    if words:
        leaf_y = max(w["yc"] for w in words)
        leaves = [w for w in words if w["yc"] >= leaf_y - 3]
        upper = [w for w in words if w["yc"] < leaf_y - 3]
        ok = True
        leaf_col = {}
        for w in leaves:
            j = nearest(w)
            ok = ok and j not in leaf_col
            leaf_col[j] = w
        prefix: dict[int, list[str]] = defaultdict(list)
        own: dict[int, list[str]] = defaultdict(list)
        for w in sorted(upper, key=lambda w: w["yc"]):
            under = [j for j, lw in leaf_col.items() if lw["x0"] < w["x1"] and lw["x1"] > w["x0"]]
            if under and leaf_y - w["yc"] > 3:
                for j in under:
                    prefix[j].append(header_text(w["text"]))
            else:
                own[nearest(w)].append(header_text(w["text"]))
        # a group word centred over one year (Average) covers every plain-year column
        years = [j for j, lw in leaf_col.items() if re.fullmatch(r"\d{4}", header_text(lw["text"]))]
        year_groups = {tuple(prefix[j]) for j in years if prefix[j]}
        if len(year_groups) == 1:
            for j in years:
                prefix[j] = list(next(iter(year_groups)))
        out = []
        for j in range(n_vals):
            if j in leaf_col:
                leaf = header_text(leaf_col[j]["text"])
                out.append(" ".join(prefix[j] + [leaf]))
                ok = ok and j not in own
            else:
                ok = ok and len(own[j]) == 1
                out.append(own[j][0] if own[j] else "")
        if ok and all(out):
            return out
    old_vals = [clean_cell(h) for h in old_hdr[3:]]
    pdf_tokens = Counter(header_text(w["text"]) for w in hdr_words) + Counter(
        tok for w in hdr_words for tok in header_text(w["text"]).split())
    if len(old_vals) == n_vals and all(old_vals) and all(all(tok in pdf_tokens for tok in v.split()) for v in old_vals):
        return old_vals
    raise FixError("value-column header cannot be proven from the PDF header")


def nb_sectors(rows: list[dict], info: list[dict], labels: list[dict]) -> list[str]:
    if not labels:
        raise FixError("no rotated sector labels on the PDF")
    labs = sorted({(round(s["yc"], 1), SECTORS[compact(s["text"])]) for s in labels})
    out = []
    for r, i in zip(rows, info):
        sec = min(labs, key=lambda lab: abs(lab[0] - i["y"]))[1]
        if r["sector_md"] and r["sector_md"] != sec:
            raise FixError(f"sector of '{r['vessel']}': PDF label {sec} vs MD {r['sector_md']}")
        out.append(sec)
    if [s for k, s in enumerate(out) if k == 0 or s != out[k - 1]] != [lab[1] for lab in labs]:
        raise FixError("PDF sector labels do not form contiguous row groups")
    return out


def fix_nb_table(lines: list[str], pdf: Pdf, t: dict, changes: list[dict], unresolved: list[dict]) -> dict | None:
    """Returns {start, end, new} (a line-range replacement) or None."""
    def fail(reason: str):
        unresolved.append({"line": t["head"] + 1, "class": "nb_prices", "reason": reason})
        return None
    rows = parse_nb_old(t)
    if len(rows) < 4:
        return fail("old table has no recognisable vessel rows")
    try:
        pi, title, info, hdr_words, labels, n_vals = nb_pdf_check(pdf, rows)
        header = nb_header(hdr_words, info, t["hdr"], n_vals)
        sectors = nb_sectors(rows, info, labels)
    except FixError as exc:
        return fail(str(exc))
    new_rows = [[sec, r["vessel"], r["size"], *i["values"]] for sec, r, i in zip(sectors, rows, info)]
    added = [{"row": r["vessel"], "col": header[c], "col_index": c, "value": i["values"][c],
              "bbox": [round(i["val_spans"][c]["x0"], 1), round(i["val_spans"][c]["y0"], 1),
                       round(i["val_spans"][c]["x1"], 1), round(i["val_spans"][c]["y1"], 1)]}
             for r, i in zip(rows, info) for c in range(i["n_old"], n_vals)]
    old_tok = digit_tokens([c for r in rows for c in r["cells"]])
    new_tok = digit_tokens([c for r in new_rows for c in r])
    if old_tok - new_tok or new_tok - old_tok != digit_tokens([a["value"] for a in added]):
        return fail("numeric tokens of the old table are not all kept in the rebuilt table")
    new_table = [join_row(["Sector", "Vessel", "Size", *header]), join_row(["---"] * (3 + n_vals))]
    new_table += [join_row(r) for r in new_rows]
    start = t["head"]
    j = start - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    head_line = lines[j] if j >= 0 else ""
    if head_line.startswith("## ") or (head_line.startswith("#") and "indicativenewbuildingprices" in compact(head_line)):
        block_start, prefix = j, [NB_HEADING] + lines[j + 1:start]
    else:
        block_start, prefix = start, [NB_HEADING, ""]
    new = prefix + new_table
    old = lines[block_start:t["end"]]
    if new == old:
        return None
    changes.append({"line": block_start + 1, "class": "nb_prices", "old": old, "new": new, "pdf_evidence": {
        "page": pi + 1, "title_bbox": ([round(min(s["x0"] for s in title), 1), round(min(s["y0"] for s in title), 1),
                                        round(max(s["x1"] for s in title), 1), round(max(s["y1"] for s in title), 1)]
                                       if title else None),
        "header": header, "sectors": dict(Counter(sectors)), "added_from_pdf": added,
        "rows": [{"vessel": r["vessel"], "y": round(i["y"], 1),
                  "value_bbox": [round(min(s["x0"] for s in i["val_spans"]), 1), round(min(s["y0"] for s in i["val_spans"]), 1),
                                 round(max(s["x1"] for s in i["val_spans"]), 1), round(max(s["y1"] for s in i["val_spans"]), 1)]}
                 for r, i in zip(rows, info)]}})
    return {"start": block_start, "end": t["end"], "new": new}


# ---------------------------------------------------------------- per-document fix
def fix_document(text: str, doc) -> tuple[str, list[dict], list[dict]]:
    pdf = doc if hasattr(doc, "spans") else Pdf(doc)
    lines = text.split(LF)
    changes: list[dict] = []
    unresolved: list[dict] = []
    replace: list[dict] = []
    for t in md_tables(lines):
        kind = table_kind(t)
        if kind:
            fix_fill_table(lines, pdf, t, kind[0], kind[1], changes, unresolved)
        if any("$/ldt" in h.lower() for h in t["hdr"]):
            fix_demolition(lines, pdf, t, changes, unresolved)
        if nb_table_candidate(t):
            r = fix_nb_table(lines, pdf, t, changes, unresolved)
            if r:
                replace.append(r)
    out: list[str] = []
    i = 0
    by_start = {r["start"]: r for r in replace}
    while i < len(lines):
        if i in by_start:
            out.extend(by_start[i]["new"])
            i = by_start[i]["end"]
        else:
            out.append(lines[i])
            i += 1
    changes.sort(key=lambda c: c["line"])
    return LF.join(out), changes, unresolved


# ---------------------------------------------------------------- driver
def resolve_pdf(md_path: Path) -> Path | None:
    rel = PDF_ROOT_REL / md_path.parent.name / (md_path.stem + ".pdf")
    for root in (REPO_ROOT, MAIN_CHECKOUT):
        if (root / rel).exists():
            return root / rel
    return None


def change_lines(c: dict) -> int:
    return len(c["old"]) if isinstance(c["old"], list) else 1


def run(years: list[str] | None, limit: int | None, detect_only: bool, out_root: Path,
        md_root: Path | None = None) -> dict:
    import pymupdf
    md_root = md_root or (REPO_ROOT / MD_ROOT_REL)
    summary = {"files": 0, "files_changed": 0, "changes": 0, "no_pdf": [], "by_class": {}, "by_year_class": {},
               "unresolved_by_class": {}, "unresolved": [], "per_file_changes": {}}
    byyc: dict = defaultdict(Counter)
    byc: Counter = Counter()
    unc: Counter = Counter()
    paths = sorted(md_root.glob("*/*.md"))
    if years:
        paths = [p for p in paths if p.parent.name in years]
    if limit:
        paths = paths[:limit]
    for p in paths:
        if not detect_only:     # never leave a previous run's output for a file that no longer changes
            for stale in (out_root / p.parent.name / p.name, out_root / p.parent.name / (p.stem + ".changelog.json")):
                stale.unlink(missing_ok=True)
        raw = p.read_bytes().decode("utf-8")
        eol = CRLF if CRLF in raw else LF
        txt = raw.replace(CRLF, LF)
        yr = p.parent.name
        summary["files"] += 1
        if txt.replace(LF, eol) != raw:
            summary["no_pdf"].append(p.name + " (mixed line endings, skipped)")
            continue
        pdf_path = resolve_pdf(p)
        if pdf_path is None:
            summary["no_pdf"].append(p.name)
            continue
        with pymupdf.open(pdf_path) as doc:
            new, ch, un = fix_document(txt, Pdf(doc))
        for c in ch:
            byyc[yr][c["class"]] += 1
            byc[c["class"]] += 1
        for u in un:
            unc[u["class"]] += 1
            summary["unresolved"].append({"file": p.name, "year": yr, **u})
        if ch:
            summary["files_changed"] += 1
            summary["changes"] += len(ch)
            summary["per_file_changes"][p.name] = {"year": yr, "changes": len(ch)}
            if not detect_only:
                d = out_root / yr
                d.mkdir(parents=True, exist_ok=True)
                staged_bytes = new.replace(LF, eol).encode("utf-8")
                (d / p.name).write_bytes(staged_bytes)
                (d / (p.stem + ".changelog.json")).write_text(
                    json.dumps({"md": str(MD_ROOT_REL / yr / p.name), "pdf": pdf_path.name,
                                "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                "staged_sha256": hashlib.sha256(staged_bytes).hexdigest(),
                                "changes": ch, "unresolved": un}, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    summary["by_class"] = dict(byc)
    summary["by_year_class"] = {y: dict(c) for y, c in sorted(byyc.items())}
    summary["unresolved_by_class"] = dict(unc)
    return summary


def apply_staged(staging: Path, do_apply: bool, repo_root: Path | None = None) -> dict:
    """Copy staged MDs over the real MDs, only for files that have a changelog and whose
    source is byte-identical to what the fixer read. Dry-run unless do_apply."""
    repo_root = repo_root or REPO_ROOT
    res = {"applied": [], "refused": [], "dry_run": not do_apply}
    for log in sorted(staging.glob("*/*.changelog.json")):
        meta = json.loads(log.read_text(encoding="utf-8"))
        staged = log.with_name(log.name[: -len(".changelog.json")] + ".md")
        target = repo_root / meta["md"]
        if not meta.get("changes") or not staged.exists() or not target.exists():
            res["refused"].append({"file": log.name, "reason": "no changes / missing staged or target"})
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != meta.get("source_sha256"):
            res["refused"].append({"file": log.name, "reason": "target changed since staging"})
            continue
        if hashlib.sha256(staged.read_bytes()).hexdigest() != meta.get("staged_sha256"):
            res["refused"].append({"file": log.name, "reason": "staged file differs from what the fixer wrote"})
            continue
        if do_apply:
            target.write_bytes(staged.read_bytes())
        res["applied"].append(str(target.relative_to(repo_root)))
    return res


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--years")
    ap.add_argument("--promote", action="store_true", help="list/apply staged files, do not re-run the fixer")
    ap.add_argument("--apply", action="store_true",
                    help="copy staged files into data/extracted/md/intermodal (default is a dry-run list)")
    a = ap.parse_args()
    if a.apply and not a.promote:
        ap.error("--apply requires --promote")
    if a.promote:
        r = apply_staged(REPO_ROOT / STAGING_REL, a.apply)
        print(json.dumps({"dry_run": r["dry_run"], "applied": len(r["applied"]), "refused": r["refused"]}, indent=1))
        return
    out = REPO_ROOT / STAGING_REL
    s = run(a.years.split(",") if a.years else None, a.limit, a.detect_only, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "_summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k not in ("per_file_changes", "unresolved")},
                     indent=1, ensure_ascii=False))
    print("unresolved:", len(s["unresolved"]))


if __name__ == "__main__":
    main()
