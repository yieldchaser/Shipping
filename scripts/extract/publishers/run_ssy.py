"""
Source 3: SSY - dedicated pipeline.

SSY's own structure, measured (scratch/ssy_*.py), NOT a general template:

  * 1 page per document (all years). ~2500 chars of text.
  * TWO-COLUMN page whose columns OVERLAP in x:
        prose : x 17-211, font size 10.0pt
        table : x 208-590, font size  9.0pt, rows on a ~15pt pitch
  * Because they overlap, left-to-right readers fuse them. liteparse produced
        | $5,000/day and $4,750/day in the round | NARVIK/ROTTERDAM | 150,000/10% ...
    i.e. the prose column landing in the table's first cell.
  * pdf-inspector, our source-1 engine, returns 0 usable tables here: the raw
    text HAS the values, and 66 horizontal rules are drawn, but the engine does
    not assemble them. PyMuPDF find_tables() finds a 16x3 grid and leaves the
    cells empty.
  * Numbers are ISO/US.

So SSY is assembled from SPANS, keyed on the two discriminators that actually
separate the columns:
        x >= 205   (the table column's left edge)
        size < 9.5 (table spans are 9pt, prose spans are 10pt)
Both are used: x alone would be brittle against a few points of layout drift;
size alone would catch stray small print elsewhere on the page.

Rows are then reassembled by clustering spans within 8pt of each other in y,
which is under the observed 15pt row pitch.

MEASURED on 2021 A20210705 against the rendered page: 12/12 values recovered,
zero prose bleed-through.
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "ssy"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

XCUT = 205.0          # fallback table left edge, for pages with no rows
NL = chr(10)
BS = chr(92)
SIZE_MAX = 9.5        # table spans are 9pt; prose is 10pt
ROW_TOL = 8.0         # cluster tolerance; observed row pitch is ~15pt

STRUCT = ("CALCULATED INDEX", "Change on Previous Index", "Change on Four Weeks",
          "Change on Previous Year", "Change on Two Years", "Trade")


def parse_iso(tok):
    """SSY is ISO/US: 29,580 -> 29580 ; 34.5 -> 34.5 (not the European rule)."""
    if tok is None:
        return None
    s = str(tok).strip().replace("%", "").replace("$", "").strip()
    if not s or not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    s = s.replace(",", "")
    if s.count(".") > 1:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def spans_of(pg):
    out = []
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = sp["text"].strip()
                if t:
                    out.append((sp["bbox"], t, round(sp["size"], 1)))
    return out


NUMERIC = re.compile(r"^[\d][\d,.]*%?$|^[+-][\d][\d,.]*$|^[\d][\d,.]*/\d+%?$")
PROSEY = re.compile(r"[a-z]{3,}\s+[a-z]{3,}")


def is_numeric_cell(t: str) -> bool:
    s = t.strip().replace("%", "").strip()
    if not s or not re.search(r"\d", s) or len(s) > 14:
        return False
    return bool(re.fullmatch(r"[\d.,]+( DWT)?", s)
                or re.fullmatch(r"[\d.,]+/[\d.]+", s)
                or re.fullmatch(r"[+-]?[\d.,]+", s))


def detect_table_size(spans) -> float:
    """The modal font size among numeric cells = THIS page's table size.

    Needed because SSY's table is 9.0pt in 2021/2023 but 8.7pt in 2026, and a
    fixed threshold silently drops the whole table on the newer layout.
    """
    sizes = Counter(sz for bb, t, sz in spans if is_numeric_cell(t))
    return sizes.most_common(1)[0][0] if sizes else 9.0


def _assemble(rows_y, merged, tsz, tol, xmin=None):
    out = []
    for grp in merged:
        ylo, yhi = min(grp), max(grp) + 3
        cells = []
        for y, items in rows_y.items():
            if not (ylo <= y < yhi):
                continue
            for bb, t, sz in items:
                if abs(sz - tsz) > tol:
                    continue
                if len(t) > 44 or (PROSEY.search(t) and len(t) > 24):
                    continue
                if xmin is not None and bb[0] < xmin:
                    continue
                cells.append((round(bb[0]), round(bb[1]), round(bb[2]), t))
        if not cells:
            continue
        cells.sort()
        seen, row = set(), []
        for x0, y, x1, t in cells:
            if (x0, y, t) in seen:
                continue
            seen.add((x0, y, t))
            row.append((x0, x1, t))
        # A data row must carry a LABEL. Without this the chart's own
        # x-axis year labels (2019 2020 2021, side by side in one y-band)
        # are >=2 numeric cells and become a fake data row - measured
        # 2026-09-24: 181 such rows in 181 of 519 documents, in the old
        # output too. A row of pure numbers names no entity and is not
        # keyable as a series, so it is not a table row.
        if (sum(1 for c in row if is_numeric_cell(c[2])) >= 2
                and any(not is_numeric_cell(c[2]) for c in row)):
            out.append({"y": min(grp), "cells": row})
    return out


def page_rows(pg):
    """Self-calibrating SSY row extraction -> (rows, meta).

    2021/2023 put the table in the RIGHT column (routes at x~208) while 2026
    puts route names in the LEFT column at x~12, so a fixed x-cut deletes them.
    This anchors on y-rows that hold >=2 numeric cells and then takes every span
    on that row at the page's own table size.

    The page's own table LEFT EDGE (`tx`) is derived in a first pass as the MODAL
    x0 of each row's leftmost cell, so prose that shares a row's y-band cannot
    move it. Rows are then re-assembled excluding spans left of `tx` - measured
    2026-09-24: in the 2023/2024 era the prose is 8.8pt, the SAME size as the
    table, so the old size-only test let one prose line into the
    QUEENSLAND/JAPAN row of ssy_2023_20231103-Pacific-Capesize-Report and shifted
    every value one column left in the typed record (10.0 -> 9.00 instead of
    9.00 -> 9.20).

    `meta["headers"]` carries the page's own header bands (the two column DATES
    and the units), which the .md previously dropped entirely.
    """
    spans = spans_of(pg)
    tsz = detect_table_size(spans)
    tol = 0.65

    rows_y = {}
    for bb, t, sz in spans:
        key = round(bb[1] / 3.0) * 3.0
        rows_y.setdefault(key, []).append((bb, t, sz))

    bands = [y for y, items in sorted(rows_y.items())
             if sum(1 for bb, t, sz in items
                    if is_numeric_cell(t) and abs(sz - tsz) <= tol) >= 2]

    merged = []
    for y in bands:
        if merged and abs(y - merged[-1][-1]) <= 6:
            merged[-1].append(y)
        else:
            merged.append([y])

    first = _assemble(rows_y, merged, tsz, tol)
    tx = (Counter(r["cells"][0][0] for r in first).most_common(1)[0][0]
          if first else XCUT)
    rows = _assemble(rows_y, merged, tsz, tol, xmin=tx - 2.0)

    # header bands: same size as the table, inside its x-range, no numeric cell,
    # and not inside a data row's y-band
    taken = set()
    for grp in merged:
        ylo, yhi = min(grp), max(grp) + 3
        for y in rows_y:
            if ylo <= y < yhi:
                taken.add(y)
    hb = {}
    for y, items in rows_y.items():
        if y in taken:
            continue
        for bb, t, sz in items:
            if abs(sz - tsz) > tol or is_numeric_cell(t) or bb[0] < tx - 2.0:
                continue
            hb.setdefault(y, []).append((round(bb[0]), round(bb[2]), t))
    headers = [{"y": y, "cells": sorted(v)} for y, v in sorted(hb.items())]

    ys = [r["y"] for r in rows]
    gaps = [b - a for a, b in zip(ys, ys[1:]) if 0 < b - a < 40]
    pitch = sorted(gaps)[len(gaps) // 2] if gaps else 12.5
    return rows, {"tsz": tsz, "tx": tx, "pitch": pitch, "headers": headers}


def prose(pg, tx, tsz):
    """The prose column - text that sits entirely LEFT of the table's own left
    edge, kept separately so the .md holds it as text, not as a mangled cell.

    Measured 2026-09-24: a fixed `sz >= 9.5` floor is wrong for the 2023/2024
    era, where the prose is set at 8.8pt - the SAME size as the table. That
    floor dropped the whole commentary paragraph from 14 documents. The floor is
    now the page's own table size: prose is never smaller than the table text
    (in 2021 that excludes the 8.0pt address block, which the old floor also
    excluded).
    """
    body = [(bb, t) for bb, t, sz in spans_of(pg)
            if sz >= tsz - 0.65
            and (bb[0] < tx - 2.0
                 or (bb[0] < XCUT and sz > tsz + 1.5))]
    body.sort(key=lambda s: (s[0][1], s[0][0]))
    lines, cur, cy = [], [], None
    for bb, t in body:
        if cy is None or abs(bb[1] - cy) <= 3:
            cur.append(t)
            if cy is None:
                cy = bb[1]
        else:
            lines.append(" ".join(cur))
            cur, cy = [t], bb[1]
    if cur:
        lines.append(" ".join(cur))
    return [l for l in lines if l.strip()]


def _header_cells(bands, rows):
    """Place the header spans into the data columns by maximum x-overlap."""
    widest = max(rows, key=lambda r: len(r["cells"]))
    cols = [(c[0], c[1]) for c in widest["cells"]]
    out = [""] * len(cols)
    for b in bands:
        for x0, x1, t in b["cells"]:
            best, bi = 0.0, -1
            for i, (a, z) in enumerate(cols):
                ov = min(x1, z) - max(x0, a)
                if ov > best:
                    best, bi = ov, i
            if bi >= 0 and best > 0:
                out[bi] = f"{out[bi]} {t}".strip()
    return out


def md_blocks(rows, meta):
    """Group the page's data rows into blocks, each with its own column header.

    The header text is ON the page (2021-2024 stack two header rows: the two
    column DATES, then the units) but was never carried into the .md - measured
    2026-09-24: 0 of 519 SSY .md files contained a dd/mm/yyyy column date, so
    nothing in the output said which weeks the two $/t columns are. A block
    starts at a data row that has its own header band immediately above it,
    which is also what separates the bottom $/Day block from the $/t block.
    """
    adj = 1.5 * meta["pitch"]
    blocks, prev_y = [], None
    for r in rows:
        sel = sorted((h for h in meta["headers"]
                      if (prev_y is None or h["y"] > prev_y) and h["y"] < r["y"]),
                     key=lambda h: -h["y"])
        keep, lim = [], r["y"]
        for h in sel:
            if lim - h["y"] <= adj:
                keep.append(h)
                lim = h["y"]
            else:
                break
        if keep or not blocks:
            blocks.append({"headers": list(reversed(keep)), "rows": [r]})
        else:
            blocks[-1]["rows"].append(r)
        prev_y = r["y"]
    for b in blocks:
        b["header_cells"] = _header_cells(b["headers"], b["rows"])
    return blocks


def build_md(pdf: Path, rows=None, meta=None):
    """Markdown from the page's own text layer, with the table rendered as a
    proper pipe table (its own column headers included) and the prose as prose
    - rather than hoping a converter guesses the column boundary."""
    try:
        ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        ref = pdf.as_posix()
    out = [f"# {pdf.stem}", "", f"source: `{ref}`", ""]
    with pymupdf.open(pdf) as d:
        for i, pg in enumerate(d, start=1):
            out.append(NL + "## Page " + str(i) + NL)
            rws, mt = (rows, meta) if (i == 1 and rows is not None) else page_rows(pg)
            pr = prose(pg, mt["tx"], mt["tsz"])
            if pr:
                out.append("### Commentary" + NL)
                out.extend(f"- {l}" for l in pr)
                out.append("")
            if rws:
                out.append("### Data" + NL)
                blocks = md_blocks(rws, mt)
                w = max(len(r["cells"]) for blk in blocks for r in blk["rows"])
                w = max(w, max(len(blk["header_cells"]) for blk in blocks))
                for b in blocks:
                    hdr = b["header_cells"] + [""] * (w - len(b["header_cells"]))
                    out.append("| " + " | ".join(hdr) + " |")
                    out.append("|" + "---|" * w)
                    for r in b["rows"]:
                        cells = [c[2].replace("|", BS + "|") for c in r["cells"]]
                        cells += [""] * (w - len(cells))
                        out.append("| " + " | ".join(cells) + " |")
                    out.append("")
    return NL.join(out)


PERCENT = re.compile(r"^\d+(?:[.,]\d+)?\s*%$")


def typed_table(rows):
    """Rows -> typed records where the shape is known, otherwise the raw grid.

    The page holds TWO blocks that share row labels but not units: the freight
    block ($/t) and, at the bottom, a $/Day timecharter block under its own
    $/Day header. Measured 2026-09-24: keying on the label alone put the $/Day
    value in weight_pct and the previous day-rate in rate_prev, with rate_curr
    NULL, on 707 of 5,920 rows across all 519 documents - one route label
    carrying a $/t and a $/day value in the same list, which any series keyed on
    (route, field) would fuse. The weight cell is always a percentage, so its
    SHAPE separates the two blocks.
    """
    rec = {"trade_rates": [], "timecharter_day_rates": [], "index": {},
           "raw_rows": rows}
    for r in rows:
        if not r:
            continue
        head = r[0]
        if ("/" in head or head.startswith("T/C")) and len(r) >= 4:
            weight = (r[2] or "").strip() if len(r) > 2 else ""
            if PERCENT.match(weight):
                rec["trade_rates"].append({
                    "route": head,
                    "cargo_size": r[1] if len(r) > 1 else None,
                    "weight_pct": weight,
                    "rate_prev": parse_iso(r[3]) if len(r) > 3 else None,
                    "rate_curr": parse_iso(r[4]) if len(r) > 4 else None,
                })
            else:
                rec["timecharter_day_rates"].append({
                    "route": head,
                    "cargo_size": r[1] if len(r) > 1 else None,
                    "day_rate_prev": parse_iso(r[2]) if len(r) > 2 else None,
                    "day_rate_curr": parse_iso(r[3]) if len(r) > 3 else None,
                })
        elif head.strip().lower() == "calculated index":
            rec["index"]["value_prev"] = parse_iso(r[1]) if len(r) > 1 else None
            rec["index"]["value_curr"] = parse_iso(r[2]) if len(r) > 2 else None
        elif head.strip().lower().startswith("change on"):
            key = (head.strip().replace("Change on ", "").replace("change on ", "")
                       .lower().replace(" ", "_"))
            rec["index"][key] = {
                "prev": parse_iso(r[1]) if len(r) > 1 else None,
                "curr": parse_iso(r[2]) if len(r) > 2 else None,
            }
    return rec


def process(pdf: Path, out=None):
    out_dir = Path(out) if out else OUT
    with pymupdf.open(pdf) as d:
        npages = d.page_count
        rows, meta = page_rows(d[0])
    md = build_md(pdf, rows, meta)
    typed = typed_table([[c[2] for c in r["cells"]] for r in rows])
    stem = pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    (out_dir / f"{stem}.tables.json").write_text(
        json.dumps({"convention": "iso", "n_rows": len(rows), "typed": typed},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "rows": len(rows),
            "routes": len(typed["trade_rates"]),
            "day_rates": len(typed["timecharter_day_rates"]),
            "index_keys": len(typed["index"]),
            "md_bytes": len(md)}


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    st = {"done": {}, "failed": {}}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    todo = [p for p in pdfs if p.stem not in st["done"]]
    print(f"[{PUB}] total={len(pdfs)} done={len(st['done'])} todo={len(todo)}", flush=True)
    t0 = time.time()
    for n, p in enumerate(todo, start=1):
        try:
            r = process(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:52]:<52} rows={r['rows']:>2} "
                  f"routes={r['routes']:>2} idx={r['index_keys']:>2} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:52]:<52} FAILED {type(e).__name__}",
                  flush=True)
            traceback.print_exc(limit=2)
        if n % 10 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(pdfs)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s", flush=True)
    if st["failed"]:
        print(json.dumps(st["failed"], indent=2)[:1200])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            print(json.dumps(process(Path(a)), indent=2, default=str))
    else:
        main()
