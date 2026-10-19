"""Row integrity of MD tables against the PDF text layer (word coordinates).

A number-recall check (every MD number occurs somewhere in the PDF text) cannot see a table whose row labels
are shifted against their values: Nace returned Intermodal W41 2026 with every label one row below its numbers,
and all the numbers still occur in the PDF. Here each MD table row with a text label and 2+ numbers is located
on the page: some printed occurrence of the label must have the row's numbers, left to right, on the same
horizontal band (the label's line, widened for labels that wrap). A row whose label is printed but whose numbers
never sit beside it is flagged.

Rows whose label is not on the text layer are skipped (image tables, labels the parser rewrote), so a clean
result on an image page means "not checked", not "correct".

    python scripts/qa/table_row_check.py MD PDF            # print flagged rows
    from table_row_check import bad_rows                    # [(table_index, row_cells), ...]
"""
from __future__ import annotations

import re
import sys
from typing import List, Tuple

NUM = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def _n(s: str) -> str:
    return s.replace(",", "").replace("$", "").replace("%", "").lstrip("+")


def md_table_rows(md: str) -> List[Tuple[int, List[str]]]:
    rows, t, prev = [], -1, False
    for line in md.splitlines():
        s = line.strip()
        is_row = s.startswith("|") and s.endswith("|")
        if is_row and not prev:
            t += 1
        prev = is_row
        if is_row and not re.fullmatch(r"\|[\s:|-]+\|", s):
            rows.append((t, [c.strip() for c in s.strip("|").split("|")]))
    return rows


def page_words(doc) -> List[Tuple[int, float, float, float, float, str]]:
    out = []
    for pno, page in enumerate(doc):
        for x0, y0, x1, y1, w, *_ in page.get_text("words"):
            out.append((pno, x0, y0, x1, y1, w))
    return out


def _row_ok(words, label_toks: List[str], vals: List[str]) -> Tuple[bool, bool]:
    """(label_found, values_beside_label)"""
    first = label_toks[0]
    found = False
    for i, (pno, x0, y0, x1, y1, w) in enumerate(words):
        if w.lower() != first:
            continue
        # rest of the label on the same line, in order
        j, k, ok = i + 1, 1, True
        while k < len(label_toks):
            if j >= len(words) or words[j][0] != pno or abs(words[j][2] - y0) > 3 or words[j][5].lower() != label_toks[k]:
                ok = False
                break
            j, k = j + 1, k + 1
        if not ok:
            continue
        found = True
        h = max(y1 - y0, 6)
        for tol in (0.6 * h, 2.2 * h):   # same line, then a band for labels that wrap onto two lines
            yc = (y0 + y1) / 2
            band = sorted((wx0, _n(ww)) for (wp, wx0, wy0, wx1, wy1, ww) in words
                          if wp == pno and wx0 > x0 and abs((wy0 + wy1) / 2 - yc) <= tol and NUM.fullmatch(ww))
            seq, m = [v for _, v in band], 0
            for v in seq:
                if m < len(vals) and v == vals[m]:
                    m += 1
            if m == len(vals):
                return True, True
    return found, False


def bad_rows(md: str, doc) -> List[Tuple[int, List[str]]]:
    words = page_words(doc)
    out = []
    for ti, cells in md_table_rows(md):
        # anchor: the last text cell before the row's first run of 2+ number cells (the route "MEG-SPORE", not
        # the group label "VLCC" printed once across several rows); check only that run
        isnum = [bool(c) and bool(NUM.fullmatch(c.replace(" ", ""))) for c in cells]
        label, vals = "", []
        for i, c in enumerate(cells):
            if isnum[i] or not re.search(r"[A-Za-z]{2}", c):
                continue
            run = []
            for j in range(i + 1, len(cells)):
                if not isnum[j]:
                    break
                run.append(_n(cells[j].replace(" ", "")))
            if len(run) >= 2:
                label, vals = c, run
                break
        toks = [t.lower() for t in label.split()]
        if len(vals) < 2 or not toks:
            continue
        found, ok = _row_ok(words, toks, vals)
        if found and not ok:
            out.append((ti, cells))
    return out


if __name__ == "__main__":
    import pymupdf
    md = open(sys.argv[1], encoding="utf-8").read()
    bad = bad_rows(md, pymupdf.open(sys.argv[2]))
    for ti, cells in bad:
        print(f"table {ti}: {' | '.join(cells)[:150]}")
    print(f"{len(bad)} flagged rows")
