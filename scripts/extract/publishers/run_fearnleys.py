"""Source 5: FEARNLEYS - dedicated pipeline. THREE payload shapes + junk.

257 PDFs: 2018:1 2021:26 2022:49 2023:49 2024:48 2025:48 2026:36
Measured fingerprint of all 257 (scratch/fearnleys/fingerprint.jsonl):
    A-cards   130   HTML page printed to PDF, 19-20pp, fearnpulse.com
    B-rows     57   2021-2022, ONE landscape poster page
    printer    46   'fearnpulse.com/print' A4 portrait, 7pp (2021-2023) or 19-20pp
    image-only 23   content is a RASTER; text layer holds only header/footer
    garbled     1   2018 W29, custom font encoding -> control characters

*** THE LESSON THIS SOURCE TAUGHT: GEOMETRY IS NOT STABLE, AND NEITHER IS SIZE.
A fixed 18pt "value" threshold (correct on 2026 W18) silently returned ZERO rows
on 2023 W39, where the same HTML was rendered at ~10% scale so the card fonts
are 1.5pt labels / 1.8pt values / 1.3pt sizes instead of 15 / 18 / 13.5. The
POSITIONS are identical (label x=58.3, size x~512, same 105pt card pitch); only
the font sizes shrank. The same document also splits words into fragments
('W' + 'AF/FEAST', '$37' + ',000', '1 Y' + 'ear T' + '/C'), which a size or
exact-text rule reads as garbage.

So this pipeline anchors on POSITION + CONTENT, never on font size:
  * fragments on one baseline are merged (|dy|<1.5, x-gap<2.0)
  * chrome (header/footer) is excluded by its y band (y<30 or y>805), not by
    its 8.0pt size, which is the one size that does NOT scale
  * a value is a cell whose text IS a number / $number / WS number
  * a card label is the nearest preceding TEXT cell in the same column, within
    40pt above; the card's vessel-size cell is the right-column cell ABOVE the
    value, the change cell the right-column cell AT/BELOW it
  * rows (poster + printer eras) are y-groups of >=2 cells where the value is
    the first value-shaped cell and the label the text cell to its LEFT
Cards straddle page breaks (2026 W18: 'VLCC' label p3 y=767, value p4 y=29).

Numbers are ISO/US in every era ('$67,028', '$13.24', '$27000.0', 'WS 21.0').
The advanced_shipping European parser must NOT be reused.
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "fearnleys"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

# No 'k' suffix: chart AXIS labels ('25k','150k') are the same shape as a
# value and, once the 18pt size anchor was removed, they produced 19 phantom
# cards on 2026 W18 (90 rows where the page holds 71). Real fearnleys table
# values never carry a 'k' - prose does ('USD 32k/day') and prose is not parsed.
VAL_RE = re.compile(r"^(?:WS\s*[\d.]+|[-+]?\$?\d[\d,]*(?:\.\d+)?%?)$")
NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")

# Browser chrome, filtered BY CONTENT: the 2021-2022 poster page is ~7700pt
# tall and the 7pp 'printer version' is 1192pt, so a fixed y band silently
# deleted every row of both (it kept only the 19-20pp A4 documents).
CHROME = re.compile(r"(fearnpulse\.com|\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}"
                    r"|^\d+/\d+$|Fearnleys Weekly Report \| Fearnpulse)")


def clean(t: str) -> str:
    """Strip the up/down arrow printed beside every change value.

    Measured: a change cell's text is '$1.2' + newline + chr(0xF062) - a
    PRIVATE-USE-AREA glyph. A plain strip() left it in place, so is_value()
    rejected it and EVERY change in the printer-era files was silently
    dropped. Found by reconciling every value-shaped line, not by a row
    count, which looked healthy.
    """
    t = "".join(ch for ch in t if not (0xF000 <= ord(ch) <= 0xF8FF))
    t = t.replace(chr(0x25B2), " ").replace(chr(0x25BC), " ")
    t = t.replace(chr(10), " ")
    return " ".join(t.split())

def is_value(t: str) -> bool:
    t = clean(t)
    return bool(t) and bool(VAL_RE.match(t))


def to_num(t: str):
    t = clean(t)
    m = NUM.search(t)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def read_lines(doc):
    """Merge same-baseline fragments, then drop header/footer chrome by y band."""
    raw = []
    for pno, pg in enumerate(doc):
        for b in pg.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                t = " ".join("".join(s["text"] for s in l["spans"]).split())
                if not t:
                    continue
                x0, y0, x1, y1 = l["bbox"]
                raw.append(dict(p=pno, t=t, x=round(x0, 1), y=round(y0, 1),
                                x1=round(x1, 1),
                                sz=round(l["spans"][0]["size"], 1)))
    raw.sort(key=lambda l: (l["p"], l["y"], l["x"]))
    merged = []
    for l in raw:
        if (merged and merged[-1]["p"] == l["p"]
                and abs(merged[-1]["y"] - l["y"]) < 1.5
                and -1.0 <= l["x"] - merged[-1]["x1"] < 2.5):
            merged[-1]["t"] += l["t"]
            merged[-1]["x1"] = max(merged[-1]["x1"], l["x1"])
            continue
        merged.append(dict(l))
    body = [l for l in merged if not CHROME.search(l["t"])]
    chrome = [l for l in merged if CHROME.search(l["t"])]
    return body, chrome


def _label(prev, v, xmax=200, same=True, top=True):
    """Nearest preceding TEXT cell in the SAME COLUMN as the value."""
    for c in reversed(prev):
        if c["x"] >= xmax or abs(c["x"] - v["x"]) > 8:
            continue
        if not re.search(r"[A-Za-z]", c["t"]) or is_value(c["t"]):
            continue
        if same and c["p"] == v["p"] and 8 <= v["y"] - c["y"] <= 45:
            return c
        if not same:
            if c["p"] == v["p"] - 1 and c["y"] > 600 and top:
                return c
    return None


def tick_columns(unlabelled):
    """A chart's y-axis tick labels are a chain of plain numbers in one narrow
    column - measured on 2026 W18 p19: 2500/2000/1500/1000/500 at x~64-70 with
    a 45pt pitch. Card values ALSO form a regular column (105pt pitch, spread
    0.00), so pitch alone cannot separate them: only values that found NO label
    on their own page are tick candidates. That is the check that catches the
    phantom row the cross-page carry-over produced ('Spread MGO/380 CST' ->
    tick '2500')."""
    byx = {}
    for l in unlabelled:
        byx.setdefault((l["p"], round(l["x"] / 15.0)), []).append(l)
    bad = set()
    for k, g in byx.items():
        if len(g) < 4:
            continue
        g.sort(key=lambda l: l["y"])
        d = [b["y"] - a["y"] for a, b in zip(g, g[1:])]
        med = sorted(d)[len(d) // 2]
        if med > 5 and (max(d) - min(d)) / med < 0.35:
            bad.update(id(x) for x in g)
    return bad


def cards(ls):
    """Card = label/value in the left column, size/change in the right one."""
    left = [l for l in ls if l["x"] < 200]
    tops = {}
    for l in ls:
        tops[l["p"]] = min(tops.get(l["p"], 10 ** 9), l["y"])
    vals = [l for l in left if is_value(l["t"])]
    # The CARD column is derived from the document: it is the modal x of the
    # value-shaped lines in the left half. The chapter markers ('01'..'06', at
    # the margin, x~39.8) are also bare numbers, and one of them was read as a
    # card value with the heading 'Prices' as its label (2026 W17, row 10/10).
    if not vals:
        return []          # poster/printer eras have no left-column values
    cx = {}
    for v in vals:
        cx[round(v["x"])] = cx.get(round(v["x"]), 0) + 1
    card_x = max(cx, key=cx.get)
    vals = [v for v in vals if abs(v["x"] - card_x) <= 6]
    unlabelled, lab_of = [], {}
    for v in vals:
        lab = _label(left[:left.index(v)], v)
        if lab is not None:
            lab_of[id(v)] = lab
        else:
            unlabelled.append(v)
    bad = tick_columns(unlabelled)
    rows = []
    for v in vals:
        if id(v) in bad:
            continue
        lab = lab_of.get(id(v))
        if lab is None:
            top = v["y"] <= tops.get(v["p"], 0) + 0.5
            lab = _label(left[:left.index(v)], v, same=False, top=top)
        if lab is None:
            continue
        right = [l for l in ls if l["p"] == v["p"] and l["x"] > 400
                 and v["y"] - 45 <= l["y"] <= v["y"] + 45]
        above = sorted([l for l in right if l["y"] < v["y"]],
                       key=lambda l: -l["y"])
        below = sorted([l for l in right if l["y"] >= v["y"]],
                       key=lambda l: l["y"])
        rows.append(dict(page=v["p"] + 1, label=clean(lab["t"]), value_raw=clean(v["t"]),
                         value=to_num(v["t"]), _lx=lab["x"], _y=v["y"], _era="A-cards",
                         vessel_size=clean(above[0]["t"]) if above else "",
                         change_raw=clean(below[0]["t"]) if below else "",
                         change=to_num(below[0]["t"]) if below else None))
    return rows


def table_rows(ls):
    """Poster + printer eras: label | value | change all share one y."""
    groups = {}
    for l in ls:
        groups.setdefault((l["p"], round(l["y"] / 3.0)), []).append(l)
    rows = []
    for k in sorted(groups):
        g = sorted(groups[k], key=lambda l: l["x"])
        if len(g) < 2:
            continue
        vi = next((i for i, c in enumerate(g) if is_value(c["t"])), None)
        if vi is None:
            continue
        v = g[vi]
        lab = next((c for c in reversed(g[:vi]) if re.search(r"[A-Za-z]", c["t"])),
                   None)
        if lab is None:
            continue
        chg = next((c for c in reversed(g[vi + 1:]) if is_value(c["t"])), None)
        rows.append(dict(page=v["p"] + 1, label=clean(lab["t"]), value_raw=clean(v["t"]),
                         value=to_num(v["t"]), _lx=lab["x"], _y=v["y"], vessel_size="",
                         change_raw=clean(chg["t"]) if chg else "",
                         change=to_num(chg["t"]) if chg else None))
    return rows


def is_card_label(ls, i, l):
    """A card label has a VALUE 8-45pt BELOW it in the same column. Prose lines
    sit at the same x as headings and fooled a 'has something above it' test,
    which silently dropped the real section heading 'Rates' (2026 W18 p6)."""
    for c in ls[i + 1:]:
        if c["p"] != l["p"]:
            break
        if c["y"] - l["y"] > 45:
            break
        if abs(c["x"] - l["x"]) <= 8 and 8 <= c["y"] - l["y"] <= 45                 and is_value(c["t"]):
            return True
    return False


def has_subtitle(ls, l):
    """In the A-cards era every real section heading is followed by a smaller
    '(USD/Day, Weekly Change)'-style unit line. Chart furniture in the same
    margin ('Click rate to view graph', 'USD per Day') is not, and that is what
    separates them without hardcoding those strings."""
    for c in ls:
        if c["p"] == l["p"] and 0 < c["y"] - l["y"] <= 22 and c["sz"] < l["sz"]                 and c["t"].startswith("("):
            return True
    return False


def headings(ls, label_x, strict=False):
    """Heading = short line in the LEFT MARGIN, on no table row, not ending in a
    period, and with no value under it in the same column.

    The margin is derived from the rows themselves (heading_x < label_x - 3):
    in the A-cards era headings sit at x=39.8 while card labels sit at 57.8, so
    'Modern' (x=493), a chart legend (x=370) and a chart tick (x=64) are all
    excluded by position rather than by a hardcoded coordinate."""
    rowcells = set()
    groups = {}
    for l in ls:
        groups.setdefault((l["p"], round(l["y"] / 3.0)), []).append(l)
    for k, g in groups.items():
        if any(is_value(c["t"]) for c in g):
            rowcells.update(id(c) for c in g)
    hs = []
    for i, l in enumerate(ls):
        if (id(l) in rowcells or not (label_x - 25 <= l["x"] < label_x - 3)
                or not re.search(r"[A-Za-z]", l["t"]) or len(l["t"]) > 60
                or l["t"].endswith(".") or l["t"][:1].islower()):
            continue
        if is_card_label(ls, i, l):
            continue                     # it is a card label, not a heading
        if strict and not (has_subtitle(ls, l) or l["sz"] >= 20):
            continue
        hs.append(l)
    hs.sort(key=lambda l: (l["p"], l["y"]))
    return hs


def attach_sections(rows, ls):
    """Nearest preceding heading, tiered by the doc's OWN heading sizes.
    Best-effort CONTEXT: a heading may be carried across a page boundary."""
    if not rows:
        return
    xs = {}
    for r in rows:
        xs[r["_lx"]] = xs.get(r["_lx"], 0) + 1
    label_x = max(xs, key=xs.get)
    hs = headings(ls, label_x, strict=(rows[0].get('_era') == 'A-cards'))
    if not hs:
        return
    base = min(l["sz"] for l in hs)
    for r in rows:
        y = r.pop("_y", None)
        p0 = r["page"] - 1
        sec = cls = ""
        for h in reversed(hs):
            # on the row's own page the heading must sit ABOVE the row; a heading
            # on an earlier page is preceding by reading order (sections and
            # chapters run across page breaks in this publication).
            if h["p"] > p0 or (h["p"] == p0 and y is not None and h["y"] >= y):
                continue
            if h["p"] < p0 - 1:
                break                    # do not carry context two pages back
            s_ = h["sz"]
            if s_ <= base * 1.15 and not sec:
                sec = h["t"]
            elif s_ > base * 1.15 and not cls:
                cls = h["t"]
            if sec and cls:
                break
        r["section"], r["klass"] = sec, cls


def route(npages, body, text):
    pr = (sum(1 for c in text if c.isprintable()) / max(1, len(text))) if text else 1.0
    cpp = len(text) / max(1, npages)
    if pr < 0.8:
        return "C-garbled", [], []
    if cpp < 300:
        return "D-image", [], []
    cr = cards(body)
    tr = table_rows(body)
    if len(cr) >= 5 and len(cr) >= len(tr):
        return "A-cards", cr, []
    if len(tr) >= 5:
        return "B-rows", tr, []
    return "empty", cr or tr, []


def process(pdf: Path):
    with pymupdf.open(pdf) as d:
        npages = d.page_count
        nimg = sum(len(pg.get_images()) for pg in d)
        gfx = {}
        for i, pg in enumerate(d, start=1):
            segs = sum(1 for dr in pg.get_drawings() for it in dr["items"]
                       if it[0] == "l")
            if segs > 200:
                gfx[str(i)] = {"vector_segments": segs}
        body, chrome = read_lines(d)
        text = "".join(pg.get_text() for pg in d)
        pages = [pg.get_text().strip() for pg in d]

    era, rows, _ = route(npages, body, text)
    if era in ("A-cards", "B-rows"):
        attach_sections(rows, body)
    try:
        ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        ref = pdf.as_posix()

    typed = [r for r in rows if r["value"] is not None]
    head = [f"# {pdf.stem}", "",
            f"source: `{ref}`  |  pages: {npages}  |  era: {era}", ""]
    if era == "D-image":
        head += [f"> QUARANTINED: content is a raster image ({nimg} embedded "
                 f"images); the text layer holds only the browser header/footer "
                 f"({len(text)} chars over {npages} pages). No typed rows are "
                 f"asserted. OCR is not installed on this box.", ""]
    if era == "C-garbled":
        head += ["> QUARANTINED: custom font encoding, text layer maps to "
                 "control characters.", ""]
    md = head + [f"## Typed rows (era {era}) - {len(typed)}", "",
                 "| page | chapter | section | label | value | size | change |",
                 "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['page']} | {r.get('klass', '')} | {r.get('section', '')} | "
                  f"{r['label'].replace('|', '/')} | {r['value_raw']} | "
                  f"{r['vessel_size']} | {r['change_raw']} |")
    md += ["", "## Full page text", ""]
    for i, t in enumerate(pages, start=1):
        md += [f"\n### Page {i}\n", t, ""]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{pdf.stem}.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / f"{pdf.stem}.tables.json").write_text(json.dumps(
        {"convention": "iso", "era": era, "n_rows": len(rows),
         "n_typed": len(typed), "rows": rows}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    (OUT / f"{pdf.stem}.charts.json").write_text(
        json.dumps(gfx, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "era": era, "rows": len(rows),
            "typed": len(typed), "chars": len(text), "images": nimg,
            "md_bytes": len("\n".join(md))}


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    st = {"done": {}, "failed": {}}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    todo = [p for p in pdfs if p.stem not in st["done"]]
    print(f"[{PUB}] total={len(pdfs)} done={len(st['done'])} todo={len(todo)}",
          flush=True)
    t0 = time.time()
    for n, p in enumerate(todo, start=1):
        try:
            r = process(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:44]:<44} {r['era']:<9} "
                  f"rows={r['rows']:>3} typed={r['typed']:>3} ({time.time()-t0:.0f}s)",
                  flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:44]:<44} FAILED "
                  f"{type(e).__name__}: {str(e)[:70]}", flush=True)
            traceback.print_exc(limit=2)
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
