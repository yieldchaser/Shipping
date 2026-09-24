"""
Source 7: AGORA "SNAPSHOT OF COMMERCIAL INDICATORS" - dedicated pipeline.

Measured facts (docs/agora_survey.md):
  * 213 PDFs, 2021:25 2022:37 2023:50 2024:38 2025:35 2026:28.
  * 5 pages (6 in 8 docs). Page order is NOT stable: the 6-page documents
    insert the introductory note as its own page, so page index 1 is prose in
    them. Pages are therefore routed by CONTENT.
  * page 0 cover / page 3 Notes / page 4 Contact = no data. Two data pages:
    COMMODITY FUTURES + USD LIBOR + EXCHANGE RATE (page A) and STOCK MARKETS +
    10-YEAR BOND + BUNKERS + BALTIC EXCHANGE (page B).
  * NO CHARTS: every drawing is a zero-width fill (row shading) plus one stroked
    rule per page. .charts.json is emitted empty with that reason recorded.
  * THE HAZARD: the number convention switches mid-2022. US ($78.96, 4.40%) for
    2021 W25-2022 W26; EU (92,85 / 4.492,82) for 2022 W43-2026. Reading either
    with the other's rule is a silent 100x/1000x error in the plausible
    direction. The convention is therefore derived PER DOCUMENT from the page
    (anchor rows Crude Oil/Brent/Gas Oil/Gold/Copper, whose 'Actual last' is
    USD/barrel with 2 decimals), never from a year table.

Design: columns are never typed as coordinates. Every column anchor is read off
the page from its own header words ('Actual last' = the word 'last' preceded by
'Actual'; '% weekly'; '4-weekly'; bunkers 'IFO380'/'VLSFO'/'MGO'), and a value
word is assigned to the column whose header RIGHT EDGE is nearest - values in
this report are right-aligned to their header, so the rule is immune to how wide
a particular number is (measured: header right edges 554.8/629.0/702.6 vs value
right edges 555/624/699 on 2021 W25; 571.9/629.6/703.2 vs 572/627/700 on 2026).

Values are read at WORD level, because a span can carry two values ('$1.183
$1.584' in one span on the 2026 Fujairah row). Labels are matched by vocabulary
and never fed to the value parser ('BCI T/C - 182.000 dwt' carries a value-shaped
182.000 = 182,000 dwt).
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "agora"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

TITLE_TERMS = ["COMMODITY FUTURES", "USD LIBOR", "EXCHANGE RATE",
               "STOCK MARKETS", "10-YEAR BOND", "BUNKERS", "BALTIC EXCHANGE"]
ANCHOR_LABEL = re.compile(r"^(Crude Oil|Brent|Gas Oil|Gold|Copper)\s*\d*$")
VALUE_RE = re.compile(r"^\$?-?[\d][\d.,]*%?$|^\$?-?[\d][\d.,]*$")
BUNKER_COLS = ("IFO380", "VLSFO", "MGO")
PROSE_PAGES = ("Notes :", "CONTACT DETAILS", "Introductory Note:")


def words_of(page):
    """Word-level boxes, then merge fragments separated by < 2.5pt so a number
    and its own '%' or '$' stay one token ('-2,07' + '%')."""
    ws = [{"t": w[4], "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3]}
          for w in page.get_text("words") if w[4].strip()]
    ws.sort(key=lambda w: (round(w["y0"], 1), w["x0"]))
    out = []
    for w in ws:
        if (out and abs(w["y0"] - out[-1]["y0"]) < 2.5
                and -0.5 <= w["x0"] - out[-1]["x1"] < 2.5):
            out[-1]["t"] += w["t"]
            out[-1]["x1"] = max(out[-1]["x1"], w["x1"])
            out[-1]["y1"] = max(out[-1]["y1"], w["y1"])
        else:
            out.append(dict(w))
    return out


def find_titles(ws):
    """Locate the section titles as consecutive same-line words."""
    titles = []
    for i, w in enumerate(ws):
        for term in TITLE_TERMS:
            parts = term.split()
            got, x1, y = [], w["x1"], w["y0"]
            ok = True
            idx = i
            for k, p in enumerate(parts):
                if idx >= len(ws):
                    ok = False
                    break
                c = ws[idx]
                if c["t"] != p or abs(c["y0"] - y) > 2.5 or c["x0"] - x1 > 8:
                    ok = False
                    break
                got.append(c)
                x1 = c["x1"]
                idx += 1
            if ok:
                titles.append({"name": term, "x0": got[0]["x0"], "y0": got[0]["y0"],
                               "x1": got[-1]["x1"], "y1": max(g["y1"] for g in got)})
                break
    # dedupe: a term may be matched at several offsets
    uniq = {}
    for t in titles:
        uniq.setdefault((t["name"], round(t["y0"], 1)), t)
    return sorted(uniq.values(), key=lambda t: (t["y0"], t["x0"]))


def header_groups(ws):
    """Column anchors read off the page: 'Actual last', '% weekly', '% 4-weekly'
    and the bunker grades. Grouped into rows by y, then split by x gaps."""
    anchors = []
    for i, w in enumerate(ws):
        t = w["t"]
        if t == "last" and i and ws[i - 1]["t"] == "Actual" and ws[i - 1]["x0"] < w["x0"]:
            anchors.append(("Actual last", w["x1"], w["y0"], ws[i - 1]["x0"]))
        elif t == "weekly" and i and ws[i - 1]["t"] == "%":
            anchors.append(("% weekly", w["x1"], w["y0"], ws[i - 1]["x0"]))
        elif t == "4-weekly" and i and ws[i - 1]["t"] == "%":
            anchors.append(("% 4-weekly", w["x1"], w["y0"], ws[i - 1]["x0"]))
        elif t in BUNKER_COLS:
            anchors.append((t, w["x1"], w["y0"], w["x0"]))
    rows = []
    for name, xr, y, xl in sorted(anchors, key=lambda a: (a[2], a[1])):
        if rows and abs(y - rows[-1]["y"]) <= 3.5:
            rows[-1]["cols"].append({"name": name, "right": xr, "left": xl})
        else:
            rows.append({"y": y, "cols": [{"name": name, "right": xr, "left": xl}]})
    groups = []
    for r in rows:
        cur = []
        for c in sorted(r["cols"], key=lambda c: c["right"]):
            if cur and c["right"] - cur[-1]["right"] > 100:
                groups.append({"y": r["y"], "cols": cur})
                cur = []
            cur.append(c)
        if cur:
            groups.append({"y": r["y"], "cols": cur})
    return [g for g in groups if len(g["cols"]) >= 2]


def bind_sections(titles, groups):
    """Map each header group to the section title that owns it.

    Score = x-gap between the title and the group's column interval, plus 3x the
    y-gap to the header. x alone mis-binds (on 2021 W33 the STOCK MARKETS header
    at y=174.8 sat nearer the USD LIBOR title in x, so every stock row was filed
    under USD LIBOR); y alone mis-binds the two tables that share a header line
    (STOCK MARKETS and 10-YEAR BOND both at y=174.8).
    """
    for g in groups:
        cols = g["cols"]
        x0 = min(col_left(c) for c in cols)
        x1 = max(c["right"] for c in cols)
        y = g["y"]

        def score(t):
            dx = 0.0 if (t["x1"] >= x0 and t["x0"] <= x1) else (
                x0 - t["x1"] if t["x1"] < x0 else t["x0"] - x1)
            return dx + 3.0 * abs(t["y0"] - y)

        # a title to the RIGHT of the group's last column belongs to another
        # table (10-YEAR BOND's title sits 59pt right of STOCK MARKETS' columns
        # and used to win the score, filing 8 stock rows under the bond table)
        cand = [t for t in titles if y - 60 <= t["y0"] <= y + 20
                and t["x0"] <= x1]
        g["section"] = min(cand, key=score)["name"] if cand else None
    return groups



def clusters(ws, ytol=6.0):
    """Group words into visual rows by y."""
    out = []
    for w in sorted(ws, key=lambda w: (w["y0"], w["x0"])):
        if out and abs(w["y0"] - out[-1]["y"]) <= ytol:
            out[-1]["words"].append(w)
        else:
            out.append({"y": w["y0"], "words": [w]})
    return out


def col_left(col):
    return col["left"]


def assign_value(w, groups, y, tol=30.0):
    """Nearest column by RIGHT-EDGE distance, but only inside the group's OWN
    y-region and x-range. Without the region check a column of one sub-table
    steals a neighbouring sub-table's value (measured: 10-YEAR BOND % weekly at
    right 717.5 is 1.4pt from BUNKERS IFO380 at 711, so '0,29%' landed in the
    bunker table; and the '500' of 'S&P 500' landed in BALTIC's column 1)."""
    best = None
    for g in groups:
        if not (g["y"] - 2 <= y < g["y_end"]):
            continue
        if not (g["x0"] - 1 <= w["x0"] and w["x1"] <= g["x1"] + 1):
            continue
        for c in g["cols"]:
            d = abs(w["x1"] - c["right"])
            if best is None or d < best[0]:
                best = (d, g, c)
    if best and best[0] <= tol:
        return best[1], best[2]
    return None, None


def footer_cutoff(ws, page_height):
    """Data stops where the disclaimer/letterhead starts - read off the page."""
    marks = ("Disclaimer", "Whilst", "AGORA", "www.agoraships.com")
    ys = [w["y0"] for w in ws if any(m in w["t"] for m in marks)]
    return (min(ys) - 2) if ys else page_height - 40


def group_regions(groups, cutoff):
    """Each header group gets a y-region: from its header down to the next group
    below it that overlaps in x (or to the footer)."""
    for g in groups:
        cols = g["cols"]
        g["x0"] = min(col_left(c) for c in cols) - 20
        g["x1"] = max(c["right"] for c in cols) + 20
    for g in groups:
        ends = [h["y"] for h in groups
                if h is not g and h["y"] > g["y"] + 3
                and not (h["x1"] < g["x0"] or h["x0"] > g["x1"])]
        g["y_end"] = min(ends) if ends else cutoff
    for g in groups:
        lefts = [max(c["right"] for c in h["cols"]) + 5 for h in groups
                 if h is not g and h["x1"] < g["x0"]
                 and h["y"] < g["y_end"] and g["y"] < h["y_end"]]
        g["lab_min"] = max(lefts) if lefts else 0.0
    return groups


def detect_convention(doc):
    """US or EU, derived from THIS document's page (see module docstring)."""
    votes = {"EU": 0, "US": 0}
    anchors = []
    for pno in range(doc.page_count):
        ws = words_of(doc[pno])
        if not any(t["name"] == "COMMODITY FUTURES" for t in find_titles(ws)):
            continue
        groups = bind_sections(find_titles(ws), header_groups(ws))
        for cl in clusters(ws):
            lab = " ".join(w["t"] for w in cl["words"]
                           if not VALUE_RE.match(w["t"]) and w["x1"] < 300)
            lab = re.sub(r"\s+", " ", lab).strip()
            if not ANCHOR_LABEL.match(lab):
                continue
            for w in cl["words"]:
                if not VALUE_RE.match(w["t"]) or w["x1"] < 500:
                    continue
                anchors.append((lab, w["t"]))
                if "," in w["t"] and "." in w["t"]:
                    votes["EU" if w["t"].rindex(",") > w["t"].rindex(".") else "US"] += 2
                elif "," in w["t"]:
                    votes["EU"] += 1
                elif "." in w["t"]:
                    votes["US"] += 1
        break
    if votes["EU"] == votes["US"]:
        # fallback: count comma-decimals vs dot-decimals in the whole document
        c = {"EU": 0, "US": 0}
        for pno in range(doc.page_count):
            for w in words_of(doc[pno]):
                t = w["t"]
                if re.fullmatch(r"\$?-?\d+,\d{2,4}%?", t):
                    c["EU"] += 1
                elif re.fullmatch(r"\$?-?\d+\.\d{2,4}%?", t):
                    c["US"] += 1
        votes = c
        src = "token-shape fallback"
    else:
        src = "anchor rows"
    conv = "EU" if votes["EU"] > votes["US"] else "US"
    return conv, {"source": src, "eu": votes["EU"], "us": votes["US"],
                  "anchors": anchors[:6]}


def to_float(tok, conv):
    t = tok.strip().lstrip("$").rstrip("%").strip()
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if not t:
        return None
    if conv == "EU":
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def split_label(text):
    """Pull the parenthesised month annotation out of a commodity label."""
    m = re.search(r"\((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                  r"\s*\d{2}\)", text)
    if m:
        # keep what follows the annotation too: dropping it silently removed the
        # unit column ('Crude Oil1 (Jun 21) NYMEX - (USD/Barrel)' -> 'Crude Oil1')
        name = (text[:m.start()] + " " + text[m.end():]).strip()
        return re.sub(r"\s+", " ", name), m.group(0)
    return text, None


def prose_of(ws):
    """Line-level text for the non-data pages (cover, notes, contacts)."""
    out, cur, y = [], [], None
    for w in sorted(ws, key=lambda w: (w["y0"], w["x0"])):
        if y is None or abs(w["y0"] - y) <= 2.0:
            cur.append(w["t"])
            y = w["y0"] if y is None else y
        else:
            out.append(" ".join(cur))
            cur, y = [w["t"]], w["y0"]
    if cur:
        out.append(" ".join(cur))
    return chr(10).join(out)


def parse_page(page, pno, conv, carry=None):
    """Return (sections, unexplained, words, carry) for one data page.

    `carry` is the previous page's column layout, used only for rows ABOVE this
    page's first header: 12 of the 213 documents overflow a table onto the next
    page with no header repeated (measured: 2021 W33 puts the USD/TRY row of
    EXCHANGE RATE at the top of page 2 with the header left on page 1), and
    without the carry those rows were lost entirely.

    Rows are built PER COLUMN GROUP, not globally. Page 2 of the 2026 report
    puts a bunker row at y=350.6 and the BCI row at y=352.7-357.4, so a global
    y-cluster anchored on the bunker row leaves the BCI LABEL 6.8pt outside it
    and every Baltic label was lost. Clustering inside the group's own x-range
    cannot collide with a neighbouring sub-table, and the label is attached from
    the group's own label zone within 8pt of the row.
    """
    ws = words_of(page)
    own = bind_sections(find_titles(ws), header_groups(ws))
    cutoff = footer_cutoff(ws, page.rect.height)
    if not own:
        # a prose page (cover / notes / contacts): no rows here, and its numbers
        # are note markers and contract sizes, not data. Carry the layout past it.
        return {}, [], ws, carry
    groups = group_regions(own, cutoff)
    top = min([g["y"] for g in groups], default=cutoff)
    if carry and top > 0:
        cg = []
        for g in carry:
            h = dict(g)
            h["y"], h["y_end"] = -1.0, top
            cg.append(h)
        groups = cg + groups
        for g in groups:                     # lab_min recomputed over the set
            lefts = [max(c["right"] for c in h["cols"]) + 5 for h in groups
                     if h is not g and h["x1"] < g["x0"]
                     and h["y"] < g["y_end"] and g["y"] < h["y_end"]]
            g["lab_min"] = max(lefts) if lefts else 0.0
    if not groups:
        return {}, [], ws, own
    groups = sorted(groups, key=lambda g: (g["y"], g["x0"]))
    sections, unexplained = {}, []
    assigned = {}          # word index -> (group, col)
    for i, w in enumerate(ws):
        if not VALUE_RE.match(w["t"]):
            continue
        g, c = assign_value(w, groups, w["y0"])
        if g is not None:
            assigned[i] = (g, c)
    used_labels = set()
    seen = set()
    for g in groups:
        hits = [(i, w, c) for i, w in enumerate(ws)
                for gg, c in [assigned.get(i, (None, None))] if gg is g]
        if not hits:
            continue
        seen.add(id(g))
        # cluster this group's own value words into rows
        rows = []
        for i, w, c in sorted(hits, key=lambda h: h[1]["y0"]):
            if rows and abs(w["y0"] - rows[-1]["y"]) <= 6.0:
                rows[-1]["words"].append((i, w, c))
            else:
                rows.append({"y": w["y0"], "words": [(i, w, c)]})
        for r in rows:
            first_left = min(col_left(c) for _, _, c in r["words"])
            ymid = sum(w["y0"] for _, w, _ in r["words"]) / len(r["words"])
            cand = [i for i, w in enumerate(ws)
                    if i not in assigned and i not in used_labels
                    and w["x1"] < first_left - 2 and w["x1"] >= g["lab_min"]
                    and g["y"] + 3 <= w["y0"] <= min(g["y_end"], cutoff)
                    and abs(w["y0"] - ymid) <= 8.0]
            cand.sort(key=lambda i: (abs(ws[i]["y0"] - ymid), ws[i]["x0"]))
            lab_idx, span = [], None
            for i in cand:                       # take the contiguous block
                if span is None or abs(ws[i]["y0"] - ymid) <= 6.0:
                    lab_idx.append(i)
                    span = ws[i]["y0"] if span is None else span
            lab_idx.sort(key=lambda i: ws[i]["x0"])
            label = re.sub(r"\s+", " ",
                           " ".join(ws[i]["t"] for i in lab_idx)).strip()
            used_labels.update(lab_idx)
            vals, raws = {}, {}
            for _, w, c in r["words"]:
                name = c["name"]
                while name in vals:
                    name += "#2"
                vals[name] = to_float(w["t"], conv)
                raws[name] = w["t"]
            name, period = split_label(label)
            sect = g["section"] or "UNBOUND"
            if "T/C" in label and sect.startswith("BALTIC"):
                sect += " - T/C"
            sections.setdefault(sect, {"columns": [c["name"] for c in g["cols"]],
                                       "rows": []})
            sections[sect]["rows"].append({"label": label, "name": name,
                                           "period": period, "values": vals,
                                           "raw": raws, "page": pno, "y": r["y"]})
    for g in own:
        # a table the publisher printed with no numbers at all (2021 W52 shows
        # dashes in every BALTIC cell) must still appear in the .md, not vanish
        if id(g) not in seen:
            sections.setdefault(g["section"] or "UNBOUND",
                                {"columns": [c["name"] for c in g["cols"]],
                                 "rows": [], "empty": True})
    for i, w in enumerate(ws):
        if i not in assigned and i not in used_labels and VALUE_RE.match(w["t"]):
            if w["y0"] > cutoff:
                continue
            unexplained.append({"page": pno, "y": round(w["y0"], 1),
                                "x0": round(w["x0"], 1), "text": w["t"]})
    # only the BOTTOM band of a page can overflow onto the next one
    ymax = max(g["y"] for g in own)
    nxt = [dict(g) for g in own if g["y"] >= ymax - 20]
    return sections, unexplained, ws, nxt


def render_section(sect):
    if not sect["rows"]:
        return ["| Item | " + " | ".join(sect["columns"]) + " |",
                "|---" * (len(sect["columns"]) + 1) + "|",
                "| _(this table carried no numeric cells on the page)_ |" +
                "  |" * len(sect["columns"])]
    cols = sect["columns"]
    order = [c for c in ("Actual last", "% weekly", "% 4-weekly") if c in cols]
    order += [c for c in cols if c not in order]
    has_period = any(r.get("period") for r in sect["rows"])
    head = "| Item | " + " | ".join(order) + " |"
    lines = [head, "|---" * (len(order) + 1) + "|"]
    for r in sect["rows"]:
        cells = [r["label"] or r["name"] or "?"]
        cells += [r["raw"].get(c, "") for c in order]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    if has_period:
        p = ["| Item | Period | " + " | ".join(order) + " |",
             "|---" * (len(order) + 2) + "|"]
        for r in sect["rows"]:
            cells = [r["name"] or r["label"] or "?", r["period"] or ""]
            cells += [r["raw"].get(c, "") for c in order]
            p.append("| " + " | ".join(str(c) for c in cells) + " |")
        lines = p
    return lines


def build(pdf):
    doc = pymupdf.open(pdf)
    conv, conv_info = detect_convention(doc)
    pages, unexplained, n_values = [], [], 0
    carry = []
    for pno in range(doc.page_count):
        page = doc[pno]
        sections, unexp, ws, carry = parse_page(page, pno, conv, carry)
        unexplained += unexp
        n_values += sum(1 for w in ws if VALUE_RE.match(w["t"]))
        prose = None
        if not sections:
            prose = "\n".join(w["t"] for w in ws)
        pages.append({"pno": pno, "sections": sections, "prose": prose,
                      "nwords": len(ws)})
    doc.close()
    return conv, conv_info, pages, unexplained, n_values


def render(pdf, conv, conv_info, pages):
    dec = "comma is the decimal point" if conv == "EU" else "period is the decimal point"
    out = [f"# {pdf.stem}", "",
           f"source: `{pdf.relative_to(ROOT).as_posix()}`  |  pages: {len(pages)}  |  "
           f"number convention: **{conv}** ({dec})", "",
           f"convention read off this page: {conv_info['source']} "
           f"(EU votes {conv_info['eu']}, US votes {conv_info['us']})", ""]
    for p in pages:
        out.append(f"## Page {p['pno'] + 1}")
        out.append("")
        if p["prose"] is not None:
            out.append("_no data table on this page_")
            out.append("")
            for ln in p["prose"].splitlines():
                if ln.strip():
                    out.append(ln.strip())
            out.append("")
            continue
        for name in sorted(p["sections"], key=lambda n: (n.endswith("T/C"), n)):
            out.append(f"### {name}")
            out.append("")
            out += render_section(p["sections"][name])
            out.append("")
    return "\n".join(out) + "\n"


def emit(pdf, md, conv, conv_info, pages, unexplained, n_values):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (pdf.stem + ".md")).write_text(md, encoding="utf-8")
    tables = {"source": pdf.relative_to(ROOT).as_posix(), "convention": conv,
              "convention_info": conv_info, "pages": len(pages),
              "typed_confidence": "best-effort typed cells; .md is the primary artefact",
              "sections": {str(p["pno"]): p["sections"] for p in pages}}
    (OUT / (pdf.stem + ".tables.json")).write_text(
        json.dumps(tables, indent=1, ensure_ascii=False), encoding="utf-8")
    charts = {"charts": [],
              "reason": "no chart layer: every drawing on every page is a zero-width "
                        "fill (table row shading) plus one stroked rule per page; "
                        "images are the logo only (measured, docs/agora_survey.md)"}
    (OUT / (pdf.stem + ".charts.json")).write_text(
        json.dumps(charts, indent=1), encoding="utf-8")
    nrows = sum(len(s["rows"]) for p in pages for s in p["sections"].values())
    return {"sections": sum(len(p["sections"]) for p in pages), "rows": nrows,
            "value_words": n_values, "unexplained": len(unexplained),
            "convention": conv, "conv_source": conv_info["source"],
            "unexplained_sample": unexplained[:4]}


def run_one(pdf):
    pdf = Path(pdf).resolve()
    conv, conv_info, pages, unexplained, n_values = build(pdf)
    md = render(pdf, conv, conv_info, pages)
    return emit(pdf, md, conv, conv_info, pages, unexplained, n_values)


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
            r = run_one(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:44]:<44} conv={r['convention']} "
                  f"sect={r['sections']} rows={r['rows']:>3} vals={r['value_words']:>3} "
                  f"unexp={r['unexplained']} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:44]:<44} FAILED {type(e).__name__}",
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
    if len(sys.argv) > 1 and sys.argv[1].endswith(".pdf"):
        for a in sys.argv[1:]:
            print(json.dumps(run_one(Path(a)), indent=2, default=str))
    else:
        main()
