"""Row-level table repair for Carriers S&P weekly markdown (data/extracted/md/carriers).

The Carriers prose and every other table are owner-audited and hand-perfected; this tool
rebuilds ONLY three table blocks from the PDF ruling geometry (row = band between horizontal
rules, cell = column band of the header cell, wrapped lines joined with a space):

    ## Second-hand Market Reported Sold      (Bulk / Tankers / Container sub-tables, one MD table)
    ## Demolition Market
    ## Newbuilding Market

Every other byte of the MD (including line endings) is preserved. Nothing is re-parsed from
scratch: the old MD rows are mapped, in order, onto the PDF rows and only proven differences are
written. Change classes (all carry the PDF page and bbox as evidence):

* row_added          - a PDF row the MD lacks (inserted at its PDF position).
* cell_filled        - blank MD cell, the PDF prints text (wrapped/merged cell text lost).
* cell_extended      - the old text is a prefix / word-substring of the PDF text (wrapped text lost).
* demolition_realign - Demolition rows whose cells were shifted/merged across cells or rows. Accepted
                       only when every word of the old table is still present in the rebuilt table
                       (words may be added from the PDF, never lost or invented).
* shift_realign      - the same repair for Second-hand and Newbuilding rows (same word-preservation guard).
* label_fix          - the ONE edit outside the three blocks: in "Dry BC Baltic Time Charter Weighted
                       Average routes" the row label cell only, set to the label the PDF prints on the
                       column whose three numbers equal the MD row's (proves it is the same row).
* en_bloc            - a price cell merged over >1 ruled row gets "<value> (en bloc)" on every spanned
                       row, unless the printed text already says each / en bloc.

Safety, per table (otherwise the table is left unchanged and reported as unresolved):
every old row maps to exactly one PDF row (by name; Newbuilding by type/units/size), in order; every
non-empty old cell equals, or is a strict prefix/word-substring of, the rebuilt cell. Any other
difference refuses the table (Demolition: unless the word-preservation rule above holds).

Conventions kept from the existing MDs: DWT/LDT without thousands separators, every other cell as
printed, merged (spanning) cells repeated on every spanned row, "NONE REPORTED" rows never written.

Source markdown is never modified: fixed copies go to .reparse_staging/carriers_rows/.

Usage:
    python -m scripts.md_cleanup.carriers_rows_fix [--detect-only] [--limit N] [--years 2025,2026]
    python -m scripts.md_cleanup.carriers_rows_fix --promote            # dry-run list (default)
    python -m scripts.md_cleanup.carriers_rows_fix --promote --apply    # copy changed files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scripts.md_cleanup.intermodal_fix import (CRLF, LF, clean_cell, compact, group_lines, join_row, md_tables,
                                               page_rules, rule_covers, split_row, squash)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")
MD_ROOT_REL = Path("data/extracted/md/carriers")
STAGING_REL = Path(".reparse_staging/carriers_rows")
PDF_ROOT_REL = Path("corpus/01-brokers/carriers")

EN_BLOC = "(en bloc)"
SHIFT_KINDS = ("sales", "demolition", "newbuilding")      # tables where words shifted across cells/rows are repaired
HEADINGS = {"## Second-hand Market Reported Sold": "sales", "## Demolition Market": "demolition",
            "## Newbuilding Market": "newbuilding"}
PDF_HEADERS = {
    "sales": ["NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS"],
    "demolition": ["NAME", "TYPE", "DWT", "LDT", "BUILT", "YARD", "PRICE/LDT", "BUYERS"],
    "newbuilding": ["TYPE", "NO", "SIZE", "YARD", "DEL", "MIL$", "OWNERS"],
}
PDF_KEY = {"NAME": "name", "TYPE": "type", "DWT": "dwt", "LDT": "ldt", "BUILT": "built", "YARD": "yard",
           "PRICE": "price", "PRICE/LDT": "price", "BUYERS": "buyers", "COMMENTS": "comments", "NO": "units",
           "SIZE": "size", "DEL": "delivery", "MIL$": "price", "OWNERS": "owners"}
MD_KEY = {"name": "name", "type": "type", "dwt": "dwt", "ldt": "ldt", "built": "built", "yard": "yard",
          "price": "price", "buyers": "buyers", "comments": "comments", "units": "units", "size": "size",
          "delivery": "delivery", "owners": "owners"}
KEY_COLS = {"sales": ["name"], "demolition": ["name"], "newbuilding": ["type", "units", "size"]}
NUMERIC_KEYS = ("dwt", "ldt")
STOP_WORDS = ("bspa", "saleandpurchase", "recyclingindex", "newbuildingindex", "balticdry", "balticindices", "balticstock", "drybc", "tankerrates",
              "carrierscharteringcorp", "marketbaltic", "bda")
HDR_BOTTOM_GAP = 1.5        # a rule this close under the header fill is the header's own border
MIN_FILL_H, MAX_FILL_H = 6.0, 40.0


class FixError(Exception):
    pass


# ---------------------------------------------------------------- text helpers
def norm_cell(text: str, key: str | None = None) -> str:
    """A PDF/MD cell in the convention of the MDs: squashed; DWT/LDT without thousands separators."""
    t = squash(text)
    if key in NUMERIC_KEYS and re.fullmatch(r"\d{1,3}(,\d{3})+", t):
        t = t.replace(",", "")
    return t


def tokens(text: str) -> list[str]:
    """Words, thousands separators removed, case-insensitive (for part-of / multiset comparison)."""
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", squash(text)).lower()
    return t.split()


def strict_part(old: str, new: str) -> bool:
    """`old` is a strict prefix or a contiguous word-substring of `new` (wrapped text lost)."""
    o, n = squash(old).lower(), squash(new).lower()
    if not o or o == n:
        return False
    if n.startswith(o) and not re.fullmatch(r"[\d.,]+", o):     # numbers: whole tokens only (79.52 is not 79.520)
        return True
    ot, nt = tokens(old), tokens(new)
    return bool(ot) and any(nt[i:i + len(ot)] == ot for i in range(len(nt) - len(ot) + 1)) and ot != nt


def loose_part(old: str, new: str) -> bool:
    """Row-key compatibility (name / type / units / size): equal, prefix or word-substring, punctuation-free."""
    co, cn = compact(old), compact(new)
    if not co:
        return False
    if co == cn or cn.startswith(co):
        return True
    ot, nt = [compact(t) for t in tokens(old)], [compact(t) for t in tokens(new)]
    return any(nt[i:i + len(ot)] == ot for i in range(len(nt) - len(ot) + 1))


def has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


# ---------------------------------------------------------------- PDF model
class Pdf:
    """Lazy per-page cache over a pymupdf document: words, ruling lines, header cell fills."""

    def __init__(self, doc):
        self.doc = doc
        self._words: dict[int, list[dict]] = {}
        self._rules: dict[int, list[dict]] = {}
        self._fills: dict[int, list[dict]] = {}

    def __len__(self):
        return len(self.doc)

    def words(self, i: int) -> list[dict]:
        if i not in self._words:
            out = []
            for x0, y0, x1, y1, text, *_ in self.doc[i].get_text("words"):
                if text.strip():
                    out.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "xc": (x0 + x1) / 2,
                                "yc": (y0 + y1) / 2, "text": text})
            self._words[i] = out
        return self._words[i]

    def rules(self, i: int) -> list[dict]:
        if i not in self._rules:
            self._rules[i] = page_rules(self.doc[i])
        return self._rules[i]

    def fills(self, i: int) -> list[dict]:
        if i not in self._fills:
            out = []
            for d in self.doc[i].get_drawings():
                col = d.get("fill")
                if col is None or all(c >= 0.95 for c in col):
                    continue
                for it in d["items"]:
                    if it[0] == "re" and MIN_FILL_H <= it[1].height <= MAX_FILL_H and it[1].width >= 12:
                        r = it[1]
                        out.append({"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1})
            self._fills[i] = out
        return self._fills[i]

    def height(self, i: int) -> float:
        return float(self.doc[i].rect.height)


def header_geometry(pdf: Pdf, page_i: int, line: list[dict]) -> tuple[list[tuple[float, float]], float]:
    """Column x-bands (from the header cell fills; midpoints between header words as fallback) and the
    y of the header's bottom edge."""
    line = sorted(line, key=lambda w: w["x0"])
    bands, bottoms = [], []
    for w in line:
        cand = [f for f in pdf.fills(page_i) if f["x0"] - 0.5 <= w["xc"] <= f["x1"] + 0.5
                and f["y0"] - 1 <= w["yc"] <= f["y1"] + 1]
        if not cand:
            break
        f = max(cand, key=lambda f: f["x1"] - f["x0"])
        bands.append((f["x0"], f["x1"]))
        bottoms.append(f["y1"])
    if len(bands) == len(line) and all(bands[i][1] <= bands[i + 1][0] + 1 for i in range(len(bands) - 1)):
        return bands, max(bottoms)
    cs = [w["xc"] for w in line]
    cuts = [(cs[i] + cs[i + 1]) / 2 for i in range(len(cs) - 1)]
    edges = [line[0]["x0"] - 40] + cuts + [line[-1]["x1"] + 40]
    return [(edges[i], edges[i + 1]) for i in range(len(cs))], max(w["y1"] for w in line) + 3.0


def locate_tables(pdf: Pdf) -> dict[str, list[dict]]:
    """Header lines of the three table kinds, in reading order. Each region runs from its header down to
    the next header line on the page (or the page end)."""
    found: dict[str, list[dict]] = {k: [] for k in PDF_HEADERS}
    for pi in range(len(pdf)):
        heads = []
        for ln in group_lines(pdf.words(pi), 3.0):
            ln = sorted(ln, key=lambda w: w["x0"])
            toks = [w["text"].upper() for w in ln]
            for kind, seq in PDF_HEADERS.items():
                if toks == seq or toks == seq + ["COMMENTS"]:
                    cols, bottom = header_geometry(pdf, pi, ln)
                    heads.append({"kind": kind, "page": pi, "keys": [PDF_KEY[t] for t in toks], "cols": cols,
                                  "hdr_bottom": bottom, "top": min(w["y0"] for w in ln)})
        heads.sort(key=lambda h: h["top"])
        for i, h in enumerate(heads):
            h["bottom"] = heads[i + 1]["top"] if i + 1 < len(heads) else pdf.height(pi)
            found[h["kind"]].append(h)
    return found


NONE_RE = re.compile(r"^(none|no)[a-z]*reported[a-z]*$")  # "NONE REPORTED", "No Sales Reported", "NONE REPORTED SOLD", "no reported sales"
ANCHOR_KEY = {"sales": "dwt", "demolition": "dwt", "newbuilding": "units"}
ANCHOR_RE = re.compile(r"^[\d.,]+$")


def read_region(pdf: Pdf, reg: dict) -> list[dict]:
    """Rows of one PDF table: {cells: {key: text}, page, bbox, spans: {key: n_rows_spanned}}.
    Ruled tables: a row is the band between row rules (rules covering at least half the columns) and a cell
    is the column's block between its own rules, so a merged cell spans several rows. Tables printed
    without row rules (some 2023 issues): the numeric anchor cell (DWT / NO) of each row is single-line and
    vertically centred, every text line belongs to the nearest anchor."""
    pi, cols, keys = reg["page"], reg["cols"], reg["keys"]
    n = len(cols)
    words = [w for w in pdf.words(pi) if reg["hdr_bottom"] < w["yc"] < reg["bottom"]
             and cols[0][0] - 2 <= w["xc"] <= cols[-1][1] + 2]
    strips = []
    for a, b in cols:
        pad = max(3.0, min(12.0, (b - a) / 2 - 2))
        strips.append(((a + b) / 2 - pad, (a + b) / 2 + pad))
    rules = [r for r in pdf.rules(pi) if reg["hdr_bottom"] + HDR_BOTTOM_GAP < r["y"] < reg["bottom"]]
    cover = [[rule_covers(r, *strips[c]) for c in range(n)] for r in rules]
    row_rules = [(r["y"], cv) for r, cv in zip(rules, cover) if sum(cv) >= (n + 1) // 2]
    seps = [reg["hdr_bottom"]] + [y for y, _ in row_rules]
    bounds = [[True] * n] + [cv for _, cv in row_rules]           # which columns each separator closes
    ac = keys.index(ANCHOR_KEY[reg["kind"]]) if ANCHOR_KEY[reg["kind"]] in keys else None
    if ac is None:
        raise FixError(f"PDF table has no {ANCHOR_KEY[reg['kind']]} column")
    anchors = [ln for ln in group_lines([w for w in words if cols[ac][0] <= w["xc"] <= cols[ac][1]], 3.0)
               if all(ANCHOR_RE.match(w["text"]) for w in ln)]
    anchor_y = sorted(statistics.mean(w["yc"] for w in ln) for ln in anchors)
    # which bands are rows: stop at the first blank band or the first non-table heading
    bands = []
    for i in range(len(seps) - 1):
        bw = [w for w in words if seps[i] < w["yc"] < seps[i + 1]]
        if not bw:
            if bands:
                break
            continue
        if NONE_RE.match(compact(" ".join(w["text"] for w in bw))):
            continue
        first = sorted(bw, key=lambda w: (round(w["yc"] / 3), w["x0"]))[:6]
        if any(compact(" ".join(w["text"] for w in first)).startswith(s) for s in STOP_WORDS):
            break
        bands.append(i)
    multi = [i for i in bands if sum(1 for y in anchor_y if seps[i] < y < seps[i + 1]) >= 2]
    if multi and (len(bands) == 1 or 2 * len(multi) >= len(bands)):
        return read_anchored(pdf, reg, words, anchor_y, row_rules)
    if multi:
        raise FixError(f"ruled PDF band at y={seps[multi[0]]:.0f} (page {pi + 1}) holds several data rows "
                       "(merged cells without a rule between them)")
    if not bands:
        return []
    last = bands[-1] + 1
    cache: dict[tuple[int, int, int], str] = {}

    def block(c: int, a: int, b: int) -> str:
        if (c, a, b) not in cache:
            cw = [w for w in words if cols[c][0] <= w["xc"] <= cols[c][1] and seps[a] < w["yc"] < seps[b]]
            cache[(c, a, b)] = lines_text(cw)
        return cache[(c, a, b)]

    rows = []
    for i in bands:
        cells, spans = {}, {}
        for c, key in enumerate(keys):
            a = i
            while a > 0 and not bounds[a][c]:
                a -= 1
            b = i + 1
            while b < last and not bounds[b][c]:
                b += 1
            cells[key] = norm_cell(block(c, a, b), key)
            spans[key] = b - a
        add_row(rows, cells, spans, reg, seps[i], seps[i + 1])
    return rows


EN_BLOC_LABEL = re.compile(r"^en[\s-]?bloc$", re.I)


def label_en_bloc(rows: list[dict]) -> None:
    """2025/26 issues print the price on the first row of an en-bloc group and only the label "EN BLOC" in the price
    cell of the following row(s) (separate ruled cells). Every row of the group carries "<price> EN BLOC", the
    wording printed; such cells are marked synthetic so a change to them is classed en_bloc."""
    for j, r in enumerate(rows):
        if "price" not in r["cells"] or not EN_BLOC_LABEL.match(r["cells"]["price"]):
            continue
        k = j - 1
        while k >= 0 and rows[k]["page"] == r["page"] and "synth_price" in rows[k]:
            k -= 1
        if k < 0 or rows[k]["page"] != r["page"]:
            continue
        head = rows[k]["cells"]["price"]
        if not has_digit(head) or re.search(r"each|en[\s-]?bloc", head, re.I):
            continue
        for m in range(k, j + 1):
            rows[m]["cells"]["price"] = f"{head} {r['cells']['price']}"
            rows[m]["synth_price"] = True


def lines_text(cell_words: list[dict]) -> str:
    lines = [" ".join(w["text"] for w in sorted(ln, key=lambda w: w["x0"])) for ln in group_lines(cell_words, 3.0)]
    return squash(" ".join(lines))


def add_row(rows: list[dict], cells: dict, spans: dict, reg: dict, top: float, bottom: float) -> None:
    key_text = cells[reg["keys"][0]]
    if NONE_RE.match(compact(key_text)):
        return
    if "report" in compact(key_text).lower() and not any(v for k, v in cells.items() if k != reg["keys"][0]):
        return          # a placeholder sentence alone in the name cell is not a vessel
    if not key_text:
        raise FixError(f"PDF row band at y={top:.0f} (page {reg['page'] + 1}) has text but no {reg['keys'][0]} cell")
    rows.append({"cells": cells, "spans": spans, "page": reg["page"], "keys": reg["keys"],
                 "bbox": [round(reg["cols"][0][0], 1), round(top, 1), round(reg["cols"][-1][1], 1), round(bottom, 1)]})


def read_anchored(pdf: Pdf, reg: dict, words: list[dict], anchor_y: list[float], row_rules: list) -> list[dict]:
    cols, keys = reg["cols"], reg["keys"]
    if not anchor_y:
        return []
    ends = [y for y, _ in row_rules if y > anchor_y[-1] + 4]
    if not ends:
        raise FixError("table printed without row rules and without a closing rule")
    y_end = min(ends)
    tops = [reg["hdr_bottom"]] + [(anchor_y[i] + anchor_y[i + 1]) / 2 for i in range(len(anchor_y) - 1)]
    bottoms = tops[1:] + [y_end]
    per: list[dict] = [{k: [] for k in keys} for _ in anchor_y]
    for c, key in enumerate(keys):
        cw = [w for w in words if cols[c][0] <= w["xc"] <= cols[c][1] and w["yc"] < y_end]
        for ln in group_lines(cw, 3.0):
            y = statistics.mean(w["yc"] for w in ln)
            r = min(range(len(anchor_y)), key=lambda r: abs(anchor_y[r] - y))
            per[r][key].append(ln)
    rows: list[dict] = []
    for r, cells_by_key in enumerate(per):
        cells = {k: norm_cell(lines_text([w for ln in v for w in ln]), k) for k, v in cells_by_key.items()}
        add_row(rows, cells, {k: 1 for k in keys}, reg, tops[r], bottoms[r])
    return rows


# ---------------------------------------------------------------- markdown side
def md_key(header_cell: str) -> str | None:
    c = re.sub(r"[^a-z]", "", clean_cell(header_cell).split("(")[0].lower())
    return MD_KEY.get(c)


def tables_by_kind(lines: list[str]) -> dict[str, dict]:
    """kind -> {"title", "heading", "table" (md table or None)} for the three headings."""
    heads = [(i, ln.strip()) for i, ln in enumerate(lines) if ln.startswith("## ")]
    tabs = md_tables(lines)
    out = {}
    for n, (i, ln) in enumerate(heads):
        if ln not in HEADINGS:
            continue
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        t = next((t for t in tabs if i < t["head"] < end), None)
        out[HEADINGS[ln]] = {"title": ln[3:], "heading": i, "table": t}
    return out


PRICE_LIKE = re.compile(r"^(?:[A-Za-z]{2,6}\.? )?\$?\s?[\d.,]+(?:\s?-\s?[\d.,]+)?$")      # "52.50", "Low 11.00", "82-83"


def price_en_bloc(text: str) -> bool:
    """A short price cell merged over several rows that does not already say each / en bloc."""
    return bool(PRICE_LIKE.match(text)) and not re.search(r"\beach\b|en[\s-]?bloc", text, re.I)


def row_values(kind: str, row: dict, md_keys: list[str]) -> list[str | None]:
    """The rebuilt MD cells of one PDF row, in the MD column order (None = the PDF has no such column)."""
    out = []
    for k in md_keys:
        if k not in row["cells"]:
            out.append(None)
            continue
        v = row["cells"][k]
        if k == "price" and row["spans"].get(k, 1) > 1 and price_en_bloc(v):
            v = f"{v} {EN_BLOC}"
        out.append(v)
    return out


def demolition_compat(old: list[str], new: dict) -> bool:
    """A (possibly shifted / word-lossy) old Demolition row belongs to a PDF row when its name words (the type may
    be glued to the name) are an ordered subsequence of the PDF name and every number it carries is on that PDF row."""
    if not old:
        return False
    ot = [compact(t) for t in tokens(clean_cell(old[0])) if compact(t)]
    tt = [compact(t) for t in tokens(new["cells"].get("type", "")) if compact(t)]
    for k in range(len(tt), 0, -1):        # the old name may end with the (first words of the) type
        if len(ot) > k and ot[-k:] == tt[:k]:
            ot = ot[:-k]
            break
    nt = iter(compact(t) for t in tokens(new["cells"].get("name", "")))
    if not ot or not all(any(t == u for u in nt) for t in ot):
        return False
    nums = {tok for c in old for tok in tokens(clean_cell(c)) if tok.isdigit()}
    return nums <= {tok for v in new["cells"].values() for tok in tokens(v)}


def key_compat(kind: str, old: list[str], new: dict, md_keys: list[str]) -> bool:
    if kind == "demolition":
        return demolition_compat(old, new)
    for k in KEY_COLS[kind]:
        i = md_keys.index(k) if k in md_keys else None
        if i is None or i >= len(old):
            continue
        o = clean_cell(old[i])
        if kind == "newbuilding" and not o:
            continue
        if not loose_part(o, new["cells"].get(k, "")):
            return False
    return True


def classify(old: str, new: str, key: str, synth: bool = False) -> str | None:
    """Change class of one differing cell, or None if the cell is already right. Raises FixError on conflict.
    `synth`: the PDF value was assembled across rows as an en-bloc price."""
    o = clean_cell(old)
    if o == new:
        return None
    if not o:
        return "en_bloc" if synth or new.endswith(EN_BLOC) else "cell_filled"
    if strict_part(o, new):
        suffix = new.endswith(EN_BLOC) and squash(new[:-len(EN_BLOC)]) == o
        return "en_bloc" if synth or suffix else "cell_extended"
    raise FixError(f"{key}: old '{o}' conflicts with PDF '{new}'")


def fix_table(kind: str, title: str, t: dict, rows: list[dict], lines: list[str], changes: list[dict]) -> list[str] | None:
    """Returns the new body lines of table `t`, or None when nothing changes. Raises FixError to refuse."""
    hdr = [clean_cell(h) for h in t["hdr"]]
    md_keys = [md_key(h) for h in hdr]
    if any(k is None for k in md_keys) or len(set(md_keys)) != len(md_keys):
        raise FixError(f"MD header {hdr} has unknown or duplicate columns")
    pdf_keys = {k for r in rows for k in r["cells"]}
    if not pdf_keys <= set(md_keys):
        raise FixError(f"PDF columns {sorted(pdf_keys - set(md_keys))} are not in the MD header")
    for r in rows:
        if not set(md_keys) - {"comments"} <= set(r["cells"]):
            raise FixError(f"MD columns {sorted(set(md_keys) - set(r['cells']))} are not printed in the PDF table")
    if not rows:
        raise FixError("PDF has no rows for this table but the MD has")
    old = t["rows"]
    mapping, ptr = [], 0
    for idx, cells in old:
        j = next((j for j in range(ptr, len(rows)) if key_compat(kind, cells, rows[j], md_keys)), None)
        if j is None:
            raise FixError(f"MD row (line {idx + 1}) '{clean_cell(cells[0]) if cells else ''}' "
                           "does not map to a PDF row, in order")
        mapping.append(j)
        ptr = j + 1
    new_vals = [row_values(kind, r, md_keys) for r in rows]
    plan: list[tuple] = []          # ("keep", idx) / ("edit", idx, cells) / ("add", cells, row)
    row_changes: list[dict] = []
    conflicts: dict[int, str] = {}
    for (idx, cells), j in zip(old, mapping):
        nv = new_vals[j]
        if len(cells) != len(md_keys):
            conflicts[idx] = f"row has {len(cells)} cells, header {len(md_keys)}"
            continue
        out, cell_changes = list(cells), []
        try:
            for c, key in enumerate(md_keys):
                if nv[c] is None:
                    continue
                cls = classify(cells[c], nv[c], key, key == "price" and "synth_price" in rows[j])
                if cls:
                    cell_changes.append({"column": t["hdr"][c], "old": cells[c], "new": nv[c], "class": cls})
                    out[c] = nv[c]
        except FixError as exc:
            conflicts[idx] = str(exc)
            continue
        plan.append(("edit" if cell_changes else "keep", idx, out, j))
        row_changes += [{"line": idx + 1, "table": title, "pdf_evidence": ev(rows[j]), **ch} for ch in cell_changes]
    if conflicts:
        lost = lost_words(old, rows)
        if kind not in SHIFT_KINDS:
            first = next(iter(conflicts.items()))
            raise FixError(f"line {first[0] + 1}: {first[1]} [{len(conflicts)} conflicting row(s); "
                           + ("every old word is present in the PDF rows (word-preserving shift)" if not lost
                              else "old words absent from the PDF rows: " + ", ".join(sorted(lost))) + "]")
        if lost:
            raise FixError(f"{kind} rows are not a pure shift of the PDF text; words absent from the PDF: "
                           + ", ".join(sorted(lost)))
        by_idx = {p[1]: p for p in plan}
        for (idx, cells), j in zip(old, mapping):
            if idx not in conflicts:
                continue
            full = [v if v is not None else "" for v in new_vals[j]]
            by_idx[idx] = ("edit", idx, full, j)
            row_changes.append({"line": idx + 1, "table": title, "class": "demolition_realign" if kind == "demolition" else "shift_realign", "old": cells,
                                "new": full, "pdf_evidence": ev(rows[j])})
        plan = [by_idx[idx] for idx, _ in old]
    # assemble body: unmapped PDF rows are inserted at their PDF position
    mapped_to_old = {j: n for n, j in enumerate(mapping)}
    body: list[str] = []
    changed = bool(row_changes)
    adds = []
    for j, r in enumerate(rows):
        if j in mapped_to_old:
            n = mapped_to_old[j]
            p = plan[n]
            body.append(lines[p[1]] if p[0] == "keep" else join_row(p[2]))
            if p[0] == "edit" and join_row(split_row(lines[p[1]])) != lines[p[1]] and p[1] not in conflicts:
                raise FixError(f"line {p[1] + 1} is not in canonical `| a | b |` form")
        else:
            vals = [v if v is not None else "" for v in new_vals[j]]
            if any("|" in v for v in vals):
                raise FixError("a PDF cell contains '|'")
            body.append(join_row(vals))
            prev = next((mapping[k] for k in range(len(mapping) - 1, -1, -1) if mapping[k] < j), None)
            line_no = (old[mapped_to_old[prev]][0] + 2) if prev is not None else t["head"] + 3
            adds.append({"line": line_no, "table": title, "class": "row_added", "old": None, "new": vals,
                         "pdf_evidence": ev(r)})
            changed = True
    if not changed:
        return None
    changes.extend(row_changes + adds)
    return body


def lost_words(old: list, rows: list[dict]) -> Counter:
    """Words of the old table that the PDF rows do not (sufficiently often) contain."""
    old_tok = Counter(tok for _, cells in old for c in cells for tok in map(compact, tokens(clean_cell(c))) if tok)
    new_tok = Counter(tok for r in rows for v in r["cells"].values() for tok in map(compact, tokens(v)) if tok)
    return old_tok - new_tok


def ev(row: dict) -> dict:
    return {"page": row["page"] + 1, "bbox": row["bbox"]}



# ---------------------------------------------------------------- label_fix (outside the three blocks)
LABEL_HEADING = "## Dry BC Baltic Time Charter Weighted Average routes"
LABEL_WORD = re.compile(r"^[A-Za-z]+$")
SIZE_WORD = re.compile(r"^\d+K$", re.I)
NUMBER = re.compile(r"^-?[\d,]+(\.\d+)?$")


def num(text: str) -> float | None:
    t = squash(text).replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def printed_columns(pdf: Pdf) -> tuple[int, list[dict]] | None:
    """The column-oriented weighted-average table: [{label, this, change, prev, bbox}] per printed size label."""
    for pi in range(len(pdf)):
        ws = pdf.words(pi)
        head = next((w for w in ws if w["text"] == "Weighted" and any(
            v["text"] == "Average" and abs(v["yc"] - w["yc"]) < 3 for v in ws)), None)
        if head is None:
            continue
        end = next((w["y0"] for w in ws if w["text"] == "Period" and w["y0"] > head["y1"]), pdf.height(pi))
        reg = [w for w in ws if head["y1"] < w["y0"] < end]
        rows = {}
        for key, first in (("this", "This"), ("change", "Week"), ("prev", "Prev,")):
            w = next((w for w in reg if w["text"] == first), None)
            if w is None:
                return None
            rows[key] = w["yc"]
        cols = []
        for w in reg:
            nxt = [v for v in reg if SIZE_WORD.match(v["text"]) and 0 <= v["x0"] - w["x1"] < 5 and abs(v["yc"] - w["yc"]) < 3]
            if w["yc"] >= rows["this"] - 3 or not LABEL_WORD.match(w["text"]) or not nxt:
                continue
            size = nxt[0]
            xc = (w["x0"] + size["x1"]) / 2
            vals, boxes = {}, []
            for key, y in rows.items():
                hit = [v for v in reg if abs(v["yc"] - y) < 4 and NUMBER.match(v["text"]) and abs(v["xc"] - xc) < 22]
                if len(hit) == 1:
                    vals[key] = num(hit[0]["text"])
                    boxes.append(hit[0])
            cols.append({"label": f"{w['text']} {size['text']}", "vals": [vals.get(k) for k in ("this", "change", "prev")],
                         "bbox": [round(w["x0"], 1), round(min(w["y0"], size["y0"]), 1), round(size["x1"], 1),
                                  round(max(w["y1"], size["y1"]), 1)]})
        return pi, cols
    return None


def fix_labels(lines: list[str], pdf: Pdf, changes: list[dict], unresolved: list[dict]) -> None:
    heads = [i for i, ln in enumerate(lines) if ln.strip() == LABEL_HEADING]
    if not heads:
        return
    t = next((t for t in md_tables(lines) if t["head"] > heads[0]), None)
    if t is None or not t["hdr"] or compact(t["hdr"][0]) != "routeclass":
        return
    got = printed_columns(pdf)
    if got is None:
        unresolved.append({"line": heads[0] + 1, "class": "label", "reason": "weighted-average table not located in the PDF"})
        return
    pi, cols = got
    for idx, cells in t["rows"]:
        if len(cells) != len(t["hdr"]) or len(cells) < 4:
            continue
        old = clean_cell(cells[0])
        vals = [num(c) for c in cells[1:4]]
        if any(v is None for v in vals):
            if old not in {c["label"] for c in cols}:
                unresolved.append({"line": idx + 1, "class": "label", "row": old,
                                   "reason": "MD row has blank values and the PDF prints no such label (placeholder row, left)"})
            continue
        hit = [c for c in cols if None not in c["vals"] and all(abs(a - b) < 1e-9 for a, b in zip(c["vals"], vals))]
        if len(hit) != 1:
            continue
        new = hit[0]["label"]
        if new == old:
            continue
        if (old, new) != ("SUPRA 63K", "TESS 58K"):     # the only label drift the PDFs show; anything else is reported
            unresolved.append({"line": idx + 1, "class": "label", "row": old,
                               "reason": f"values match PDF column '{new}' but only SUPRA 63K -> TESS 58K is allowed"})
            continue
        if join_row(split_row(lines[idx])) != lines[idx]:
            unresolved.append({"line": idx + 1, "class": "label", "reason": "row is not in canonical form"})
            continue
        lines[idx] = join_row([new] + cells[1:])
        changes.append({"line": idx + 1, "class": "label_fix", "table": LABEL_HEADING[3:], "column": t["hdr"][0],
                        "old": cells[0], "new": new,
                        "pdf_evidence": {"page": pi + 1, "bbox": hit[0]["bbox"], "values": hit[0]["vals"]}})


# ---------------------------------------------------------------- per-document fix
def fix_document(text: str, doc) -> tuple[str, list[dict], list[dict]]:
    pdf = doc if hasattr(doc, "words") else Pdf(doc)
    lines = text.split(LF)
    changes: list[dict] = []
    unresolved: list[dict] = []
    fix_labels(lines, pdf, changes, unresolved)
    found = tables_by_kind(lines)
    if not found:
        unresolved.append({"line": 1, "class": "layout", "reason": "MD has none of the three table headings"})
        return LF.join(lines), changes, unresolved
    located = locate_tables(pdf)
    replace: dict[int, tuple[int, list[str]]] = {}
    for kind, info in found.items():
        t, title = info["table"], info["title"]
        pdf_rows: list[dict] = []
        try:
            if not located[kind]:
                if t is not None:
                    raise FixError("table header not found in the PDF (different publisher layout)")
                continue
            for reg in located[kind]:
                got = read_region(pdf, reg)
                if kind == "sales":
                    label_en_bloc(got)
                pdf_rows += got
            if t is None:
                if pdf_rows:
                    raise FixError(f"MD block has no table but the PDF prints {len(pdf_rows)} row(s)")
                continue
            table_changes: list[dict] = []
            body = fix_table(kind, title, t, pdf_rows, lines, table_changes)
        except FixError as exc:
            unresolved.append({"line": info["heading"] + 1, "class": kind, "table": title, "reason": str(exc)})
            continue
        if body is not None:
            changes.extend(table_changes)
            replace[t["head"] + 2] = (t["end"], body)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i in replace:
            end, body = replace[i]
            out.extend(body)
            i = end
        else:
            out.append(lines[i])
            i += 1
    changes.sort(key=lambda c: (c["line"], c["class"] != "row_added"))
    return LF.join(out), changes, unresolved


# ---------------------------------------------------------------- driver
def resolve_pdf(md_path: Path) -> Path | None:
    rel = PDF_ROOT_REL / md_path.parent.name / (md_path.stem + ".pdf")
    for root in (REPO_ROOT, MAIN_CHECKOUT):
        if (root / rel).exists():
            return root / rel
    return None


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
                    help="copy staged files into data/extracted/md/carriers (default is a dry-run list)")
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
