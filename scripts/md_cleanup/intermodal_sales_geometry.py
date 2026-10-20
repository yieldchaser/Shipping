"""Intermodal secondhand-sales tables rebuilt from PDF word geometry.

The parse (LlamaParse) shifts cells between columns and rows of the sales tables (merged price cells, two-line yard
names, "(en bloc)" spread over rows). The PDF text layer has every cell; this rebuilds the tables from it.

Header line = words Size/Name/Dwt/Built/... ; rows are anchored on the 4-digit year in the Built column; each word goes
to the column whose span (midpoints between header centres) holds its centre and to the row band (ruled lines, else
midpoints between anchors) holding its middle.

rebuild(text, pdf_path) swaps, per page chunk of the markdown, the span from the first sales-table line (or its
section headings) to the last sales-table line for the rebuilt tables of the matching PDF page. Guards (else the text
is returned unchanged with the reason):
  * the number of chunks holding sales tables equals the number of PDF pages with sales tables;
  * the text layer is clean (no row name that the markdown has whole is split by stray spaces; no empty name or
    short row);
  * no vessel named in the old tables is lost (exact, or a close spelling fix).

Used by run_intermodal_full.process_single_pdf (weekly CI ingest) before the tables are parsed into the sidecar and
series. The stored MDs were rebuilt with the same code on 2026-10-19.

    python scripts/md_cleanup/intermodal_sales_geometry.py PDF PAGE     prints the tables of one page
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path
from typing import List, Tuple

import pymupdf

SECTIONS = ("Tankers", "Bulk Carriers", "Gas Carriers", "Gas", "Containers", "Container", "General Cargo", "Reefers",
            "Car Carriers", "Multi-Purpose", "MPP")
SEC_HEAD = re.compile(r"^#{1,3} (Tankers|Bulk Carriers|Gas.*|Containers?|Secondhand Sales|General Cargo|Reefers|Car Carriers)\s*$")
# obvious publisher slips written as the plain word (the stored MDs carry the plain word)
PLAIN = {"Philipines": "Philippines", "unitl": "until", "undislosed": "undisclosed", "Vietnemese": "Vietnamese"}
# page separators: '---' in the stored MDs, '--- PAGE BREAK ---' in the raw parse
PAGE_SEP = re.compile(r"(\n---(?: PAGE BREAK ---)?\n)")


def _lines_of(words, tol=2.5):
    rows = []
    for w in sorted(words, key=lambda w: (round(w[1]), w[0])):
        for r in rows:
            if abs(r[0] - w[1]) < tol:
                r[1].append(w)
                break
        else:
            rows.append([w[1], [w]])
    return [(y, sorted(ws, key=lambda w: w[0])) for y, ws in sorted(rows)]


def _hlines(page):
    out = []
    for dr in page.get_drawings():
        for it in dr["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.6:
                out.append((it[1].y, min(it[1].x, it[2].x), max(it[1].x, it[2].x)))
            elif it[0] == "re" and it[1].height <= 1.5 and it[1].width > 10:
                out.append(((it[1].y0 + it[1].y1) / 2, it[1].x0, it[1].x1))
    return out


def _headers(page):
    W = page.get_text("words")
    out = []
    for y, ws in _lines_of(W):
        names = [w[4] for w in ws]
        if "Name" in names and "Built" in names and ("Dwt" in names or "Teu" in names or "Cbm" in names):
            cols = []
            for w in ws:
                if w[4] == "due" and cols and cols[-1][0] == "SS":
                    cols[-1] = ["SS due", cols[-1][1], w[2], y]
                    continue
                cols.append([w[4], w[0], w[2], y])
            out.append(cols)
    return out, W


def tables(page) -> List[dict]:
    hs, W = _headers(page)
    res = []
    foot = min([w[1] for w in W if w[4].startswith("©") or w[4] == "Intermodal" and w[1] > page.rect.height * 0.9]
               or [page.rect.height])
    for i, cols in enumerate(hs):
        hy = cols[0][3]
        nxt = hs[i + 1][0][3] - 14 if i + 1 < len(hs) else foot
        # section title: nearest line above the header naming a section
        title = ""
        for y, ws in reversed(_lines_of([w for w in W if hy - 90 < w[1] < hy - 2])):
            t = " ".join(w[4] for w in ws)
            if any(t.startswith(s) for s in SECTIONS):
                title = t
                break
        cen = [(c[1] + c[2]) / 2 for c in cols]
        bounds = [-1e9] + [(cen[j] + cen[j + 1]) / 2 for j in range(len(cen) - 1)] + [1e9]
        bi = [c[0] for c in cols].index("Built")
        body = [w for w in W if hy + 4 < w[1] < nxt and not w[4].startswith("©")]
        anchors = sorted({round((w[1] + w[3]) / 2, 1) for w in body
                          if re.fullmatch(r"(19|20)\d\d", w[4]) and bounds[bi] <= (w[0] + w[2]) / 2 < bounds[bi + 1]})
        if not anchors:
            continue
        gaps = [b - a for a, b in zip(anchors, anchors[1:])] or [20]
        g = sorted(gaps)[len(gaps) // 2]
        edges = [hy + 6] + [(a + b) / 2 for a, b in zip(anchors, anchors[1:])] + [min(nxt, anchors[-1] + max(g, 14) * 0.75)]
        hl = _hlines(page)
        # phrases: words on one line closer than 3.5pt belong together and go to one column by their centre
        chunks = []
        for y, ws in _lines_of(body):
            cur = [ws[0]]
            for w in ws[1:]:
                if w[0] - cur[-1][2] < 3.5:
                    cur.append(w)
                else:
                    chunks.append(cur)
                    cur = [w]
            chunks.append(cur)
        top, bot = hy + 6, edges[-1]
        rows = [["" for _ in cols] for _ in anchors]
        for j in range(len(cols)):
            ys = sorted({y for y, x0, x1 in hl if x0 - 1 <= cen[j] <= x1 + 1 and top - 8 < y < bot + 8})
            colchunks = [c for c in chunks if bounds[j] <= (c[0][0] + c[-1][2]) / 2 < bounds[j + 1]]
            for k, ay in enumerate(anchors):
                above = [y for y in ys if y < ay]
                below = [y for y in ys if y > ay]
                lo = max(above[-1] if above else edges[k], edges[0])
                hi = min(below[0] if below else edges[k + 1], bot)
                if not above or not below:
                    lo, hi = edges[k], edges[k + 1]
                ws = [w for c in colchunks if lo <= (c[0][1] + c[0][3]) / 2 < hi for w in c]
                rows[k][j] = " ".join(x[4] for x in sorted(ws, key=lambda w: (round(w[1]), w[0])))
        res.append({"title": title, "header": [c[0] for c in cols], "rows": rows})
    return res


def _plain(c: str) -> str:
    for k, v in PLAIN.items():
        c = re.sub(r"\b" + k + r"\b", v, c)
    return c


def render(tabs) -> str:
    out = []
    for t in tabs:
        if t["title"]:
            out += [f"## {t['title']}", ""]
        out.append("| " + " | ".join(t["header"]) + " |")
        out.append("| " + " | ".join("---" for _ in t["header"]) + " |")
        for r in t["rows"]:
            out.append("| " + " | ".join(_plain(c).replace("|", "\\|") for c in r) + " |")
        out.append("")
    return "\n".join(out)


def _is_sales_hdr(cells):
    flat = " ".join(cells)
    return "Name" in flat and re.search(r"\b(Dwt|Teu|Cbm)\b", flat) is not None and "Ldt" not in flat


def _sales_span(lines):
    """first/last index of the sales-table region in a chunk, or None"""
    idx = []
    on = False
    for i, ln in enumerate(lines):
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if _is_sales_hdr(cells):
                on = True
            if on:
                idx.append(i)
        elif ln.strip() and not SEC_HEAD.match(ln):
            on = False
    if not idx:
        return None
    a, b = idx[0], idx[-1]
    while a > 0 and (SEC_HEAD.match(lines[a - 1]) or not lines[a - 1].strip()):
        a -= 1
    while a < len(lines) and not lines[a].strip():
        a += 1
    return a, b


def _table_names(text):
    out, ni = [], None
    for ln in text.split("\n"):
        if not ln.startswith("|"):
            ni = None
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if _is_sales_hdr(cells):
            ni = next((i for i, c in enumerate(cells) if c.endswith("Name")), None)
            continue
        if ni is not None and ni < len(cells) and cells[ni] and not set(cells[ni]) <= set("-: "):
            out.append(re.sub(r"[\s\\]", "", cells[ni]).upper())
    return out


def rebuild(text: str, pdf_path) -> Tuple[str, str]:
    """(text with the sales tables rebuilt, status). On any failed guard the text comes back unchanged."""
    eol = "\r\n" if "\r\n" in text else "\n"
    t = text.replace("\r\n", "\n")
    d = pymupdf.open(str(pdf_path))
    pages = [(i + 1, tables(pg)) for i, pg in enumerate(d)]
    pages = [(i, tb) for i, tb in pages if tb]
    parts = PAGE_SEP.split(t)              # chunk, sep, chunk, sep, ...
    chunks = parts[0::2]
    spans = [(ci, _sales_span(c.split("\n"))) for ci, c in enumerate(chunks)]
    spans = [(ci, s) for ci, s in spans if s]
    if not pages:
        return text, "no sales tables in the PDF"
    if len(spans) != len(pages):
        return text, f"skipped: chunks={len(spans)} pdf_pages={len(pages)}"
    flat_md = re.sub(r"[\s\\]", "", "\n".join(l for l in t.split("\n") if l.startswith("|"))).upper()
    bad = []
    for _, tbs in pages:
        for tb in tbs:
            ni = tb["header"].index("Name")
            for r in tb["rows"]:
                n = r[ni]
                if re.search(r"\b[A-Z] [A-Z]{2,}|[A-Z]{2,} [A-Z]\b(?! )", n) and "|" + re.sub(r"\s", "", n) + "|" in flat_md \
                        and "| " + n + " |" not in t:
                    bad.append(n)
                if not n or len(r) != len(tb["header"]):
                    bad.append(f"empty:{n}")
    if bad:
        return text, f"skipped: text layer {bad[:4]}"
    for (ci, (a, bb)), (pno, tbs) in zip(spans, pages):
        lines = chunks[ci].split("\n")
        rest = lines[bb + 1:]
        gap = [""] if rest and rest[0].strip() else []
        chunks[ci] = "\n".join(lines[:a] + render(tbs).rstrip("\n").split("\n") + gap + rest)
    parts[0::2] = chunks
    nt = "".join(parts)
    newn = set(_table_names(nt))
    lost = [n for n in _table_names(t) if n not in newn and not difflib.get_close_matches(n, newn, 1, 0.8)]
    if lost:
        return text, f"skipped: would lose {lost[:5]}"
    return nt.replace("\n", eol), f"rebuilt pages {[p for p, _ in pages]}"


if __name__ == "__main__":
    doc = pymupdf.open(sys.argv[1])
    print(render(tables(doc[int(sys.argv[2]) - 1])))
