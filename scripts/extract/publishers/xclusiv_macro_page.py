"""Xclusiv weekly macro page: Commodities & Currencies table, Bunker Prices table, markets commentary.

Read from PDF word geometry. Guards: the table is bounded by its own header row; every row is a label plus
exactly the header's column count of numbers; the commentary is the page's own text blocks right of the
table, split on its bullet glyphs. A page that fails a guard yields nothing (the MD then has no macro
section rather than a wrong one).

Used by run_xclusiv_tables.process_pdf (weekly CI ingest). The 264 stored MDs were rebuilt with the same
code on 2026-10-19.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

NUM = re.compile(r"^[-+]?\$?[\d,]*\.?\d+%?$")
SECT = {"Energy", "Metals", "Industrial", "Currencies", "Agriculture", "Indices", "Equities", "Softs"}
BULLET = "•�"
BUNKER_TITLE = "Bunker Prices (in USD)"
BUNKER_COLUMNS = ["issue_date", "report_week", "port", "vlsfo_usd_mt", "ifo380_usd_mt", "mgo_usd_mt",
                  "spread_vlsfo_ifo380", "source_file"]


def _lines(ws, tol=3.0):
    out = []
    for w in sorted(ws, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if out and abs(out[-1][0] - cy) < tol:
            out[-1][1].append(w)
        else:
            out.append([cy, [w]])
    return [(cy, sorted(l, key=lambda w: w[0])) for cy, l in out]


def macro_page(doc) -> Optional[int]:
    for i, pg in enumerate(doc):
        t = pg.get_text()
        if "COMMODITIES AND CURRENCIES" in t.upper() or ("Uranium" in t and "EUR/USD" in t):
            return i
    return None


def _same_line(W, ref, tol=3):
    c = (ref[1] + ref[3]) / 2
    return sorted((w for w in W if abs((w[1] + w[3]) / 2 - c) < tol), key=lambda w: w[0])


def _parse(pg):
    W = [w for w in pg.get_text("words") if w[4].strip(BULLET)]
    H = pg.rect.height * 0.9
    price = next((w for w in W if w[4] == "Price" and any(x[4] in ("+/_", "+/-", "Energy") for x in _same_line(W, w))), None)
    eur = next((w for w in W if w[4] == "EUR/USD" and any(NUM.match(x[4]) and 0 < x[0] - w[2] < 80 for x in _same_line(W, w))), None)
    if not price or not eur:
        return "NOHDR", None
    hdr = [w for w in _same_line(W, price) if w[0] >= price[0]]
    # header = the run of known column labels; the first other word belongs to something else
    VOC = {"Price", "+/_", "+/-", "Day", "Daily", "Weekly", "Monthly", "YTD", "YoY", "WoW", "MoM"}
    end = 0
    for i in range(1, len(hdr)):
        if hdr[i][4] not in VOC or hdr[i][0] - hdr[i - 1][2] > 40:
            break
        end = i
    nxt = hdr[end + 1] if end + 1 < len(hdr) else None
    hdr = hdr[:end + 1]
    x0, x1 = eur[0] - 8, min(hdr[-1][2] + 25, (nxt[0] - 4) if nxt else 1e9)
    title = next((w for w in W if w[4].upper() == "COMMODITIES" and w[0] < x1), None)
    y0 = (title[1] - 2) if title else price[1] - 15
    T = [w for w in W if x0 <= w[0] and w[2] <= x1 and w[1] >= y0 and w[3] < H]
    cols = [w[4] for w in hdr]
    bp = next((w for w in W if w[4] == "Bunker" and any(x[4] == "Prices" and (0 < x[0] - w[2] < 15 and abs(x[1] - w[1]) < 3
                                                                              or abs(x[0] - w[0]) < 15 and 0 < x[1] - w[1] < 20) for x in W)), None)
    blocks, cur = [], None
    for cy, l in _lines(T):
        toks = [w[4] for w in l]
        s = " ".join(toks)
        if bp and bp[0] < x1 and cy > bp[1] - 14:
            break                      # bunker table handled below
        if s.upper().startswith("COMMODITIES AND CURRENCIES"):
            continue
        if toks[0] in SECT:
            cur = [toks[0], cols, []]
            blocks.append(cur)
            continue
        k = next((i for i, t in enumerate(toks) if NUM.match(t)), None)
        if k is None:
            continue
        if k == 0 or cur is None or not all(NUM.match(v) for v in toks[k:]):
            return "BADROW", s
        cur[2].append((" ".join(toks[:k]), toks[k:]))
    if bp:
        if bp[0] < x1:     # bunker box under the commodity table, same columns band
            bx0, bx1 = x0, x1 + 10
        else:              # separate box to the right: bounded by its own header line
            hl = sorted((w for w in W if abs(w[1] - bp[1]) < 16 and w[0] >= bp[0] - 15), key=lambda w: w[0])
            bx1 = hl[0][2]
            for w in hl[1:]:
                if w[0] - bx1 > 60:
                    break
                bx1 = max(bx1, w[2])
            bx0, bx1 = bp[0] - 15, bx1 + 10
        BT = [w for w in W if bx0 <= w[0] and w[2] <= bx1 and bp[1] - 14 < w[1] and w[3] < H]
        rows = []
        for cy, l in _lines(BT):
            toks = [w[4] for w in l]
            k = next((i for i, t in enumerate(toks) if NUM.match(t)), None)
            if not k:
                continue
            vals = toks[k:]
            e = next((i for i, v in enumerate(vals) if not NUM.match(v)), len(vals))
            if any(NUM.match(v) for v in vals[e:]) or e < 3:
                continue           # commentary line, not a port row
            if rows and (cy - rows[-1][0] > 30 or e != len(rows[0][3])):
                break              # end of the box
            rows.append((cy, l[:k + e], " ".join(toks[:k]), vals[:e]))
        if not rows:
            return "NOBUNKROW", None
        ry = rows[0][1][0][1]
        hw = [w for w in BT if w[1] < ry - 2 and w[0] > bp[0] + 40
              and not w[4].startswith(("Bunker", "Prices", "(in", "USD)", "$)")) and not NUM.match(w[4])]
        # column header = header words clustered by the x-centre of the first data row's value cells
        vc = [((w[0] + w[2]) / 2) for w in rows[0][1] if NUM.match(w[4])]
        bcols = [[] for _ in vc]
        for w in sorted(hw, key=lambda w: (round(w[1]), w[0])):
            c = (w[0] + w[2]) / 2
            j = min(range(len(vc)), key=lambda j: abs(vc[j] - c))
            if abs(vc[j] - c) < 30:
                bcols[j].append(w[4])
        blocks.append([BUNKER_TITLE, [" ".join(c) for c in bcols], [(lab, v) for _, _, lab, v in rows]])
    return blocks, x1


def _commentary(pg, x_table) -> List[str]:
    out = []
    H = pg.rect.height * 0.9
    for b in pg.get_text("blocks"):
        if b[0] < x_table - 15 or b[6] != 0 or b[1] > H:
            continue
        t = re.sub(r"\s*\n\s*", " ", re.sub(r"(?<=[a-z])-[ \t]*\n\s*(?=[a-z])", "-", b[4])).strip()
        toks = t.split()
        if len(t) < 80 or t.startswith("www.xclusiv") or sum(bool(NUM.match(x)) for x in toks) > 0.4 * len(toks):
            continue   # footers, chart labels, and table boxes that sit right of the commodity table
        out.append(t)
    # one bullet per paragraph: split on bullet glyphs, keep the printed order
    paras = []
    for t in out:
        for p in re.split("[" + BULLET + "]", t):
            p = p.strip()
            if p:
                paras.append(p)
    return paras


def extract(doc) -> Tuple[Optional[List[str]], Optional[list], str]:
    """(markdown lines, blocks, status). Lines and blocks are None when the page is absent or fails a guard."""
    pi = macro_page(doc)
    if pi is None:
        return None, None, "no macro page"
    res, x1 = _parse(doc[pi])
    if isinstance(res, str):
        return None, None, f"{res} {x1 or ''}".strip()
    blocks = res
    badw = [(bl[0], lab) for bl in blocks for lab, v in bl[2] if len(v) != len(bl[1])]
    secs = [bl[0] for bl in blocks]
    if badw or "Currencies" not in secs or "Energy" not in secs or not all(bl[2] for bl in blocks):
        return None, None, f"guard failed {badw[:3]} {secs}"
    paras = _commentary(doc[pi], x1)
    out = ["", "## Commodities and Currencies", ""]
    if paras:
        out += ["### Markets Commentary", ""] + [f"- {p}" for p in paras] + [""]
    for name, cols, rows in blocks:
        out += [f"### {name}", "",
                "| " + " | ".join([name.split(" (")[0] if name.startswith("Bunker") else name] + cols) + " |",
                "| " + " | ".join(["---"] * (len(cols) + 1)) + " |"]
        out += ["| " + " | ".join([lab] + v) + " |" for lab, v in rows] + [""]
    return out, blocks, "ok"


def bunker_rows(blocks, issue_date: str, source_stem: str, report_week=None) -> List[Dict[str, Any]]:
    """Series rows of xclusiv_macro_bunkers_series.csv. report_week is the week the report prints, as in the other
    Xclusiv series (the ISO week of the Monday issue date runs one ahead)."""
    if not blocks or not issue_date:
        return []
    num = lambda s: float(s.strip().replace(",", "").replace("$", ""))
    wk = report_week if report_week else datetime.date.fromisoformat(issue_date[:10]).isocalendar()[1]
    out = []
    for name, cols, rows in blocks:
        if name != BUNKER_TITLE:
            continue
        for lab, v in rows:
            if len(v) < 4:
                continue
            out.append(dict(issue_date=issue_date[:10], report_week=str(wk), port=lab,
                            vlsfo_usd_mt=num(v[0]), ifo380_usd_mt=num(v[1]), mgo_usd_mt=num(v[2]),
                            spread_vlsfo_ifo380=num(v[3]), source_file=source_stem))
    return out
