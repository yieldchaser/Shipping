"""
Source 6: AFFINITY TANKER WEEKLY - dedicated pipeline.

Affinity is a TABLE-STRUCTURED source, unlike xclusiv (prose payload) or
advanced_shipping (vector charts). Facts measured in docs/affinity_survey.md:

  * 250 PDFs, 2021:26 2022:47 2023:50 2024:50 2025:42 2026:35.
  * page 0 is the data page; pages >= 1 are the legal disclaimer only. Page
    count varies WITHIN a year (166 one-page, 84 two-page), so page 0 is
    identified by content, not by count.
  * two regions: prose at x 16.7-589.9 (TWO columns, col A x~17 col B x~307)
    and a grey card panel at x 596.8-832.0 holding four data cards.
  * the panel rect measured IDENTICAL (596.8, 94.6, 832.0, 561.4) in 250/250
    documents - it is read off the page, never typed, and it is the ONLY
    reliable prose/card separator because in 2021 prose and card data are BOTH
    9.0pt (the modal card size drifts 8.0/8.3/8.6/9.0/9.7 across documents).
  * card titles are NOT always bold: 4/250 docs render them in plain Calibri.
    So cards are found by EXACT VOCABULARY (present in 250/250), never by
    boldness or size.
  * no charts at all: the 14-20 vector drawings per page are single horizontal
    rules spanning the panel (card separators). .charts.json is emitted empty.
  * numbers are ISO/US (280,000 = 280 thousand). Never reuse the
    advanced_shipping European parser here.

Hazards handled, each measured on a real page:
  * a card header date wraps across spans AND rows: '18/09/202' then '6'.
  * a data row can be MISSING its route name (2026 TD19, TD27). The name is
    left missing - it is never filled from row order (a wrong label is worse
    than a missing one).
  * a value and its arrow can share one span: 'WS 130.63 ^Firmer'.
  * the first header cell is literally '#####' (Excel column-too-narrow).
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "affinity"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

# exact vocabulary, verified present in the panel of 250/250 documents
CARD_TITLES = ["BALTIC TCE DIRTY", "BALTIC TCE CLEAN", "BDA", "BDTI", "BCTI"]
HDR_TERMS = {"Route", "Qty", "Qnt", "$/Day", "$ / Day", "$ / WS", "W-O-W",
             "(USD/LDT)", "TKR/LRG", "TKR/MED", "TKR/SML", "This week",
             "\u0394 W-O-W", "#####"}
CODE_RE = re.compile(r"^T[DC]\d{1,2}[A-Z]?$")
ARROW_RE = re.compile(r"[\u2191\u2193]|Firm|Softer|Steady|Flat|unchanged", re.I)
VAL_RE = re.compile(r"^-?[\d][\d,\.]*$")
BDA_METRIC_RE = re.compile(r"TKR/[A-Z]+")


def panel_rect(page):
    """The grey card panel, read off the page (largest fill on the right)."""
    best = None
    for g in page.get_drawings():
        if g["type"] != "f":
            continue
        for it in g["items"]:
            if it[0] != "re":
                continue
            r = it[1]
            if r.x0 > 400 and r.width > 150 and r.height > 300:
                if best is None or r.get_area() > best.get_area():
                    best = r
    return best


def spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for s in ln["spans"]:
                if not s["text"].strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                out.append({"t": s["text"], "x0": x0, "y0": y0, "x1": x1,
                            "y1": y1, "sz": round(s["size"], 1),
                            "bold": (s["flags"] // 16) % 2 == 1})
    return out


def merge_row(cells, gap=2.0):
    """Merge same-row fragments separated by less than `gap` pt.

    An HTML print or a scaled render splits words; joining only sub-2pt gaps
    keeps 'WS 130.63' apart from a following arrow 13pt away.
    """
    out = []
    for c in sorted(cells, key=lambda c: c["x0"]):
        if out and c["x0"] - out[-1]["x1"] < gap:
            out[-1]["t"] += c["t"]
            out[-1]["x1"] = max(out[-1]["x1"], c["x1"])
        else:
            out.append(dict(c))
    for c in out:
        c["t"] = c["t"].strip()
    return [c for c in out if c["t"]]


def rows_of(cells, ytol=2.5):
    """Group cells into rows by y; a row is a y-band, never a row number."""
    out = []
    for c in sorted(cells, key=lambda c: (c["y0"], c["x0"])):
        if out and abs(c["y0"] - out[-1]["_y"]) <= ytol:
            out[-1]["cells"].append(c)
        else:
            out.append({"_y": c["y0"], "cells": [c]})
    for r in out:
        r["cells"] = merge_row(r["cells"])
    return out


def isnum(t):
    return bool(VAL_RE.match(t.strip()))


def to_float(t):
    try:
        return float(t.strip().replace(",", ""))
    except ValueError:
        return None


def split_arrow(c):
    """A cell can carry a value AND its arrow: 'WS 130.63 ^Firmer'."""
    t = c["t"]
    m = re.search(r"[\u2191\u2193]", t)
    if m and m.start() > 0:
        a = dict(c)
        a["t"] = t[:m.start()].strip()
        b = dict(c)
        b["t"] = t[m.start():].strip()
        span = c["x1"] - c["x0"]
        b["x0"] = c["x0"] + span * (m.start() / max(1, len(t)))
        return [a, b]
    return [c]


def card_slices(psp, panel):
    """Split panel spans into cards by EXACT TITLE VOCABULARY (not boldness).

    BDTI and BCTI sit on one row and form a single card.
    """
    anchors = sorted((s["y0"], s["t"].strip()) for s in psp
                     if s["t"].strip() in CARD_TITLES)
    groups = []
    for y, t in anchors:
        if groups and abs(y - groups[-1][0]) <= 3:
            groups[-1][1].append(t)
        else:
            groups.append([y, [t]])
    out = []
    for i, (y, names) in enumerate(groups):
        lo = y - 4.5
        hi = (groups[i + 1][0] - 4.5) if i + 1 < len(groups) else panel.y1 + 6
        name = " / ".join(sorted(set(names)))
        body = [s for s in psp if lo <= s["y0"] < hi
                and s["t"].strip() not in CARD_TITLES]
        out.append({"name": name, "y": y, "body": body})
    return out


DATE_PART = re.compile(r"^\d{2}/\d{2}/\d{0,3}$")
FULLDATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def join_wrapped_dates(rows):
    """A card header date wraps: '15/12/202' then '3'.

    Measured in 2023, 2025 and 2026. The continuation is a 1-2 digit cell
    sitting under the LEFT edge of a cell that already looks like a truncated
    d/m/Y. It is NOT always on the immediately following row - in
    2023-12-15 the '(USD/LDT)' header row is interleaved between them - so the
    search is by x-column within 16pt of y, not by adjacency. The fragment must
    be the ONLY cell on its row, so no real data row can be swallowed.
    """
    dates = [(ri, c) for ri, r in enumerate(rows) for c in r["cells"]
             if DATE_PART.match(c["t"].strip())]
    drop = set()
    for ri, dc in dates:
        best = None
        for rj, r in enumerate(rows):
            if rj == ri or len(r["cells"]) != 1:
                continue
            c = r["cells"][0]
            t = c["t"].strip()
            dy = abs(c["y0"] - dc["y0"])
            # the fragment sits somewhere WITHIN the truncated date's width, not
            # necessarily under its left edge (2026 DIRTY: date x0=601, frag x=618)
            if (re.fullmatch(r"\d{1,4}", t)
                    and dc["x0"] - 6 <= c["x0"] <= dc["x1"] + 6
                    and 0 < dy < 16 and (best is None or dy < best[0])):
                best = (dy, rj, t)
        if best:
            dc["t"] = dc["t"].strip() + best[2]
            drop.add(best[1])
    return [r for i, r in enumerate(rows) if i not in drop]


def header_anchors(rows):
    a = {}
    for r in rows:
        for c in r["cells"]:
            t = c["t"].strip()
            if t in HDR_TERMS and t not in a:
                a[t] = c["x0"]
    return a


def nearest_role(x, cols):
    return min(cols, key=lambda kv: abs(x - kv[1]))[0]


def parse_route_card(name, rows):
    """BALTIC TCE DIRTY / CLEAN: code, description, qty, value, direction.

    A cell can WRAP VERTICALLY AROUND its own data row - the narrow columns
    split a long value over the line above and the line below. Three shapes
    were measured, all on real pages:
        description  'ME Gulf / US' (y-5.4) | TD1 row | 'Gulf' (y+5.4)
        value        'WS' (y-5.4)           | TC6 row | '221.88' (y+5.4)
        date         '01/04/' + '2022' across the header row
    So fragments are NOT read row-by-row: every cell that is not a header, not
    a route code and not a date is attached to the NEAREST data row within 8pt
    of y (the row pitch is 16.5pt, so the window is unambiguous), and the
    fragments of each column are then joined in y order.
    """
    hdr = header_anchors(rows)
    codes = [c for r in rows for c in r["cells"] if CODE_RE.match(c["t"].strip())]
    if not codes:
        return {"name": name, "columns": [], "rows": [], "typed": [],
                "error": "no route-code column found"}
    code_x = sorted(c["x0"] for c in codes)[len(codes) // 2]
    cols = [("Route", code_x)]
    if "Route" in hdr:
        cols.append(("Description", hdr["Route"]))
    for k in ("Qnt", "Qty"):
        if k in hdr:
            cols.append(("Qty", hdr[k]))
    units = [k for k in ("$ / Day", "$ / WS") if k in hdr]
    for k in units:
        cols.append(("Value", hdr[k]))
    if "W-O-W" in hdr:
        cols.append(("W-O-W", hdr["W-O-W"]))

    drows = []
    for r in rows:
        cells = [x for c in r["cells"] for x in split_arrow(c)]
        code = next((c["t"].strip() for c in cells
                     if CODE_RE.match(c["t"].strip())), None)
        if code:
            drows.append({"y": r["_y"], "code": code, "cells": cells,
                          "extra": []})
    if not drows:
        return {"name": name, "columns": [], "rows": [], "typed": [],
                "error": "no route rows found"}

    unassigned = []
    for r in rows:
        if any(CODE_RE.match(c["t"].strip()) for c in r["cells"]):
            continue                      # a data row owns its own cells
        for c in r["cells"]:
            t = c["t"].strip()
            if t in HDR_TERMS or FULLDATE.match(t):
                continue
            best = None
            for dr in drows:
                dy = abs(c["y0"] - dr["y"])
                if dy <= 8.0 and (best is None or dy < best[0]):
                    best = (dy, dr)
            if best:
                best[1]["extra"].append(c)
            else:
                unassigned.append(t)

    def join_role(role, key):
        cs = sorted(role.get(key, []), key=lambda c: (c["y0"], c["x0"]))
        s = ""
        for c in cs:
            t = c["t"].strip()
            if not t:
                continue
            if s and s.endswith("-"):
                s += t
            else:
                s = (s + " " + t) if s else t
        return s or None

    out_rows, typed = [], []
    for dr in drows:
        role = {}
        for c in dr["cells"] + dr["extra"]:
            role.setdefault(nearest_role(c["x0"], cols), []).append(c)
        desc = join_role(role, "Description")
        qty_raw = join_role(role, "Qty")
        val_raw = join_role(role, "Value")
        wow = join_role(role, "W-O-W")
        unit_hdr = units[0] if units else None
        val, unit = None, unit_hdr
        if val_raw:
            m = re.match(r"^WS\s*([\d,\.]+)$", val_raw)
            if m:
                val, unit = to_float(m.group(1)), "WS"
            elif isnum(val_raw):
                val = to_float(val_raw)
                unit = "USD/day" if unit_hdr == "$ / Day" else (
                    "WS" if unit_hdr == "$ / WS" else unit_hdr)
        typed.append({"card": name, "route": dr["code"], "description": desc,
                      "qty_dwt": to_float(qty_raw)
                      if qty_raw and isnum(qty_raw) else None,
                      "value": val, "value_raw": val_raw, "unit": unit,
                      "wow": wow})
        out_rows.append([dr["code"], desc or "", qty_raw or "", val_raw or "",
                         wow or ""])
    return {"name": name, "columns": ["Route", "Description", "Qty", "Value",
                                      "W-O-W"], "rows": out_rows,
            "typed": typed, "unit_header": units[0] if units else None,
            "unassigned": unassigned, "error": None}


def parse_bda(name, rows):
    hdr = None
    for r in rows:
        if any(BDA_METRIC_RE.search(c["t"]) or c["t"].strip() == "(USD/LDT)"
               for c in r["cells"]):
            hdr = r
            break
    metrics = []
    if hdr:
        for c in hdr["cells"]:
            for m in BDA_METRIC_RE.finditer(c["t"]):
                metrics.append(m.group(0))
    if not metrics:
        metrics = ["TKR/LRG", "TKR/MED", "TKR/SML"]
    value_row = delta_row = None
    after = False
    for r in rows:
        if r is hdr:
            after = True
            continue
        nums = [c for c in r["cells"] if isnum(c["t"])]
        if len(nums) >= 3 and value_row is None and after:
            value_row = r
        elif any("\u0394" in c["t"] for c in r["cells"]) and len(nums) >= 3:
            delta_row = r
    def three(row):
        if not row:
            return [None, None, None]
        nums = sorted((c for c in row["cells"] if isnum(c["t"])),
                      key=lambda c: c["x0"])
        return [to_float(c["t"]) for c in nums[:3]] + [None] * (3 - len(nums))
    return {"name": name, "columns": ["metric", "value", "delta"],
            "rows": [[m, v, d] for m, v, d in
                     zip(metrics, three(value_row), three(delta_row))],
            "typed": {"metrics": metrics, "values": three(value_row),
                      "deltas": three(delta_row)}, "error": None}


def parse_bdti(name, rows):
    """BDTI / BCTI share one row: date, BDTI, BCTI, then a delta row of arrows.

    The card title is already excluded from `rows` (card_slices drops it), so
    there is NO title row to skip here - skipping the first row cost the two
    index levels on every document (caught by the reconcile: 626/496 missing).
    """
    value_row = delta_row = None
    for r in rows:
        nums = [c for c in r["cells"] if isnum(c["t"])]
        if len(nums) >= 2 and value_row is None:
            value_row = r
        elif any("\u0394" in c["t"] for c in r["cells"]):
            delta_row = r
    def pair(row):
        if not row:
            return [None, None]
        nums = sorted((c for c in row["cells"] if isnum(c["t"])), key=lambda c: c["x0"])
        return [to_float(c["t"]) for c in nums[:2]]
    date = None
    if value_row:
        txt = [c for c in value_row["cells"] if not isnum(c["t"])]
        date = txt[0]["t"].strip() if txt else None
    arrows = []
    if delta_row:
        arrows = [c["t"].strip() for c in delta_row["cells"]
                  if ARROW_RE.search(c["t"])]
    return {"name": name, "columns": ["metric", "value", "delta"],
            "rows": [["BDTI", pair(value_row)[0], arrows[0] if arrows else None],
                     ["BCTI", pair(value_row)[1], arrows[1] if len(arrows) > 1 else None]],
            "typed": {"date": date, "bdti": pair(value_row)[0],
                      "bcti": pair(value_row)[1], "arrows": arrows},
            "error": None}


def prose_lines(psp):
    """Prose region -> [(lines, pitch)] per column, column-ordered."""
    if not psp:
        return []
    xs = sorted({round(s["x0"]) for s in psp})
    cols = []
    for x in xs:
        if cols and x - cols[-1][-1] <= 20:
            cols[-1].append(x)
        else:
            cols.append([x])
    edges = [(c[0] - 12, c[-1] + 12) for c in cols]
    blocks = []
    for lo, hi in edges:
        sub = [s for s in psp if lo <= s["x0"] <= hi]
        if not sub:
            continue
        lines = []
        for r in rows_of(sub):
            txt = " ".join(c["t"] for c in r["cells"]).strip()
            if not txt:
                continue
            head = any(c["bold"] for c in r["cells"])
            lines.append((r["_y"], txt, head))
        lines.sort()
        ys = [y for y, _, _ in lines]
        deltas = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > 0.5)
        pitch = deltas[len(deltas) // 2] if deltas else 10.0
        blocks.append((lines, pitch))
    return blocks


def render_prose(blocks):
    md = []
    for lines, pitch in blocks:
        prev = None
        for y, txt, head in lines:
            if head:
                md += ["", f"### {txt}", ""]
                prev = y
                continue
            if prev is not None and (y - prev) > 1.5 * pitch:
                md.append("")
            md.append(txt)
            prev = y
        md.append("")
    return md


def norm(tok):
    return tok.strip().replace(",", "").rstrip(".")


def build(pdf: Path):
    with pymupdf.open(pdf) as d:
        npages = d.page_count
        p0 = d[0]
        panel = panel_rect(p0)
        if panel is None:
            raise RuntimeError("no card panel found on page 0")
        sp = spans(p0)
        psp = [s for s in sp if s["x0"] >= panel.x0
               and panel.y0 - 30 <= s["y0"] <= panel.y1 + 2]
        prose = [s for s in sp if s["x0"] < panel.x0
                 and panel.y0 - 30 <= s["y0"] <= panel.y1 + 2]
        cards = []
        date_cells = []
        for cs in card_slices(psp, panel):
            rows = join_wrapped_dates(rows_of(cs["body"]))
            for r in rows:
                for c in r["cells"]:
                    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c["t"].strip()):
                        date_cells.append(c)
            if cs["name"].startswith("BALTIC TCE"):
                cards.append(parse_route_card(cs["name"], rows))
            elif cs["name"] == "BDA":
                cards.append(parse_bda(cs["name"], rows))
            else:
                cards.append(parse_bdti(cs["name"], rows))
        junk = []
        for i in range(1, npages):
            t = d[i].get_text()
            if not any(k in t for k in ("BALTIC TCE", "BDTI", "TKR/")):
                junk.append(i)
        nvec = sum(1 for g in p0.get_drawings() for it in g["items"]
                   if it[0] == "l")
        ptext = p0.get_text()
        pwords = [w for w in p0.get_text("words")
                  if w[0] >= panel.x0 and panel.y0 <= w[1] <= panel.y1]

    # Compare numerically as well as textually: a cell holding the float 626.0
    # stringifies to '626.0' while the page word is '626'. Comparing strings
    # alone reported two false misses per document on a correct extraction.
    toks, ftoks = set(), set()
    for c in cards:
        for row in c["rows"]:
            for cell in row:
                for w in str(cell).split():
                    toks.add(norm(w))
                    f = to_float(w)
                    if f is not None:
                        ftoks.add(f)
    pnums = [w[4] for w in pwords if isnum(w[4])]
    missing, datefrag = [], []
    for w in pwords:
        n = w[4]
        if not isnum(n):
            continue
        if norm(n) in toks:
            continue
        f = to_float(n)
        if f is not None and f in ftoks:
            continue
        # A wrapped card date leaves a bare '3' / '6' as its own page word.
        # It IS captured - joined into the d/m/Y cell - so counting it as a
        # dropped value would understate recall on a correct extraction.
        if (re.fullmatch(r"\d{1,4}", n)
                and any(c["x0"] - 6 <= w[0] <= c["x1"] + 6
                        and 0 < abs(c["y0"] - w[1]) < 16
                        for c in date_cells)):
            datefrag.append(n)
            continue
        missing.append(n)
    denom = len(pnums) - len(datefrag)
    verified = 1.0 - (len(missing) / denom) if denom else 1.0

    try:
        ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        ref = pdf.as_posix()

    md = [f"# {pdf.stem}", "",
          f"source: `{ref}`  |  pages: {npages}  |  card panel: "
          f"{panel.x0:.1f},{panel.y0:.1f}-{panel.x1:.1f},{panel.y1:.1f}", ""]
    if junk:
        md += [f"pages {', '.join(str(j + 1) for j in junk)}: "
               f"disclaimer/junk (routed, no data)", ""]
    md += ["## Cards", ""]
    for c in cards:
        md += [f"### {c['name']}", ""]
        if c.get("error"):
            md += [f"_parse note: {c['error']}_", ""]
        md += ["| " + " | ".join(c["columns"]) + " |",
               "|" + "---|" * len(c["columns"])]
        for row in c["rows"]:
            md.append("| " + " | ".join(str(x) for x in row) + " |")
        md.append("")
    md += ["## Commentary", ""]
    md += render_prose(prose_lines(prose))
    md += ["## Verbatim page 0 text", "", ptext.strip(), ""]
    return (md, cards, junk, nvec, verified, pnums, missing, npages, ref,
            panel, datefrag)


def emit(pdf: Path, md, cards, junk, nvec, verified, pnums, missing,
         npages, ref, datefrag):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{pdf.stem}.md").write_text("\n".join(md), encoding="utf-8")
    typed = {c["name"]: c.get("typed") for c in cards}
    (OUT / f"{pdf.stem}.tables.json").write_text(json.dumps(
        {"convention": "iso", "pages": npages, "junk_pages": junk,
         "typed_confidence": "best-effort: card rows are exact geometry; "
                             "see docs/affinity_survey.md",
         "cards": [{"name": c["name"], "columns": c["columns"],
                    "rows": c["rows"], "error": c.get("error")} for c in cards],
         "typed": typed,
         "text_verified": round(verified, 4),
         "panel_values": len(pnums),
         "date_fragments_merged": datefrag,
         "missing_values": missing[:40]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{pdf.stem}.charts.json").write_text(json.dumps(
        {"charts": [], "vector_drawings": nvec,
         "note": "Affinity has NO charts: the page's vector drawings are "
                 "single horizontal rules spanning the card panel (card "
                 "separators) plus two section-title underlines. Verified by "
                 "dumping every drawing's geometry - docs/affinity_survey.md."},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "cards": len(cards),
            "card_rows": sum(len(c["rows"]) for c in cards),
            "panel_values": len(pnums), "missing": len(missing),
            "text_verified": round(verified, 4), "junk_pages": len(junk)}


def run_one(pdf: Path):
    (md, cards, junk, nvec, verified, pnums, missing, npages, ref, _,
     datefrag) = build(pdf)
    return emit(pdf, md, cards, junk, nvec, verified, pnums, missing,
                npages, ref, datefrag)


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
            r = run_one(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:48]:<48} cards={r['cards']} "
                  f"rows={r['card_rows']:>3} vals={r['panel_values']:>2} "
                  f"miss={r['missing']} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:48]:<48} FAILED "
                  f"{type(e).__name__}", flush=True)
            traceback.print_exc(limit=2)
        if n % 10 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(pdfs)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s",
          flush=True)
    if st["failed"]:
        print(json.dumps(st["failed"], indent=2)[:1200])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            print(json.dumps(run_one(Path(a)), indent=2, default=str))
    else:
        main()
