"""Read the printed tables of an MMi Daily Iron Ore Report from the PDF text layer.

Every number here is printed in the PDF as text, so it is copied, not estimated:

  read_dashboard(doc)        page 1 cards: label, value, change, change %, date line
  read_port_inventories(doc) "Iron Ore Port Inventories" table: week ending + one row per port
  read_futures(doc)          "Iron Ore Futures Contracts" table: DCE and SGX columns, 5 metrics

Cells are located by position (a row label, then the spans on its line to the right), so a
table is read only when its labels are found; a missing table returns None.
"""
from __future__ import annotations

import re
from datetime import datetime

import pymupdf

NUM = re.compile(r"^-?\d[\d,]*(\.\d+)?%?$")
DATE = re.compile(r"^(?:(Week|Month) Ending\s+)?([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})$")


def iso_date(text):
    """'Jan 3rd, 2024' -> '2024-01-03'; 'Week Ending Dec 29th, 2023' -> 'Week ending 2023-12-29'
    (also 'Month Ending Sep 30th,2021', printed on holiday issues)."""
    m = DATE.match((text or "").strip())
    if not m:
        return None
    d = datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%b %d %Y").date().isoformat()
    return f"{m.group(1)} ending {d}" if m.group(1) else d


def _spans(page, clip=None):
    out = []
    for b in page.get_text("dict", clip=clip)["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if t:
                    out.append({"text": t, "rect": pymupdf.Rect(s["bbox"]), "size": s["size"]})
    return out


def _row(spans, label_rect, x_max=None, tol=3.0):
    """Spans on the label's line, right of it, sorted by x."""
    cy = (label_rect.y0 + label_rect.y1) / 2
    return sorted((s for s in spans if abs((s["rect"].y0 + s["rect"].y1) / 2 - cy) <= tol
                   and s["rect"].x0 > label_rect.x1 - 1 and (x_max is None or s["rect"].x1 <= x_max)),
                  key=lambda s: s["rect"].x0)


# ----------------------------------------------------------------------------------------- dashboard

def read_dashboard(doc):
    """[{label, sub, value, change, change_pct, date, session}] in page order, or None.

    Page 1 is a grid of cards (three columns). Each card prints a big value; its two label lines sit
    just above it, its change and change % just below, and its date line (with an optional session
    such as "(3pm close)") below those. Some 2025 issues print the page 1.185x larger (705.8 pt wide):
    the card fonts and spacing scale with it, the 10 pt section headings do not, so card sizes and
    distances are scaled by the page width. A percentage the print shows as "######" (a too-narrow
    spreadsheet cell) is returned as None."""
    page = doc[0]
    spans = _spans(page)
    k = max(1.0, page.rect.width / 595.5)
    values = [s for s in spans if s["size"] >= 15 * k and NUM.match(s["text"])]
    if len(values) < 6:
        return None
    w = page.rect.width
    col = lambda r: min(2, int(((r.x0 + r.x1) / 2) / (w / 3)))  # noqa: E731
    cards = []
    for v in sorted(values, key=lambda s: (round(s["rect"].y0), s["rect"].x0)):
        c, vr = col(v["rect"]), v["rect"]
        same = [s for s in spans if s is not v and col(s["rect"]) == c]
        # label lines are small (8-9 pt); section headings above the cards are 10 pt
        labels = sorted((s for s in same if s["size"] < 9.6 * k and vr.y0 - 45 * k < s["rect"].y1 <= vr.y0 + 12 * k
                         and not iso_date(s["text"]) and s["text"] != "HOLIDAY"), key=lambda s: s["rect"].y0)
        # a market holiday is stamped "HOLIDAY" on the card (the value is the last one assessed)
        holiday = any(s["text"] == "HOLIDAY" and vr.y0 - 45 * k < s["rect"].y0 < vr.y1 + 30 * k for s in same)
        below = sorted((s for s in same if 10 * k <= s["size"] < 15 * k and vr.y1 < s["rect"].y0 < vr.y1 + 25 * k
                        and (NUM.match(s["text"]) or set(s["text"]) == {"#"})), key=lambda s: s["rect"].x0)
        dates = sorted((s for s in same if s["size"] < 10 * k and vr.y1 < s["rect"].y0 < vr.y1 + 70 * k
                        and iso_date(s["text"])), key=lambda s: s["rect"].y0)
        if not labels or len(below) != 2 or not dates or not NUM.match(below[0]["text"]):
            return None
        d = dates[0]
        session = [s["text"] for s in same if s["size"] < 10 * k and abs(s["rect"].y0 - d["rect"].y0) < 3 * k
                   and s["rect"].x0 > d["rect"].x1 and s["text"].startswith("(")]
        lab = [s["text"] for s in labels]
        cards.append({"label": " | ".join(lab), "lines": lab, "value": v["text"], "change": below[0]["text"],
                      "change_pct": below[1]["text"] if NUM.match(below[1]["text"]) else None, "date": iso_date(d["text"]),
                      "session": session[0].strip("()") if session else "", "holiday": holiday})
    return cards


# ----------------------------------------------------------------------------------- port inventories

PORTS = ["Jingtang", "Qingdao", "Caofeidian", "Tianjin", "Rizhao", "Total (35 Ports)"]


def _find_page(doc, *needles):
    for page in doc:
        if all(page.search_for(n) for n in needles):
            return page
    return None


def read_port_inventories(doc):
    """{"week_ending": iso, "rows": [{terminal, inventory_mt, change_pct, low_12m, high_12m}]} or None."""
    page = _find_page(doc, "Province", "This week", "Total (35 Ports)")
    if page is None:
        return None
    spans = _spans(page)
    head = next((s for s in spans if s["text"] == "Province"), None)
    if head is None:
        return None
    fut = next((s for s in spans if s["text"].startswith("Closing Date") and s["rect"].x0 > head["rect"].x1), None)
    x_max = fut["rect"].x0 - 1 if fut else None
    rows = []
    for name in PORTS:
        lab = next((s for s in spans if s["text"] == name and s["rect"].y0 > head["rect"].y0
                    and abs(s["rect"].x0 - head["rect"].x0) < 40), None)
        if lab is None:
            continue
        cells = [s["text"] for s in _row(spans, lab["rect"], x_max)]
        if len(cells) != 4 or not all(NUM.match(c) for c in cells):
            return None
        rows.append({"terminal": name, "inventory_mt": cells[0], "change_pct": cells[1],
                     "low_12m": cells[2], "high_12m": cells[3]})
    if not rows or rows[-1]["terminal"] != PORTS[-1]:
        return None
    wk = [s for s in spans if s["rect"].y1 <= head["rect"].y0 + 1 and head["rect"].y0 - 30 < s["rect"].y0
          and iso_date(s["text"]) and (x_max is None or s["rect"].x1 <= x_max)]
    return {"week_ending": iso_date(wk[0]["text"]) if wk else None, "rows": rows}


# -------------------------------------------------------------------------------------------- futures

FUT_ROWS = ["Closing Price", "Vol traded ('000 lots)", "Open positions ('000 lots)", "Day Low", "Day High"]


def read_futures(doc):
    """{"columns": [{"exchange", "unit", "closing_date", "contract"}] x2,
        "rows": [{"metric", "cells": [v, chg, pct, v, chg, pct]}]} or None (a change or % the print
        leaves blank is None)."""
    page = _find_page(doc, "Closing Date", "Closing Price")
    if page is None:
        return None
    spans = _spans(page)
    lab = {s["text"]: s for s in spans if s["text"] in FUT_ROWS + ["Closing Date", "Contract"]}
    if any(k not in lab for k in FUT_ROWS + ["Closing Date", "Contract"]):
        return None
    dates = [s["text"] for s in _row(spans, lab["Closing Date"]["rect"])]
    head_row = _row(spans, lab["Contract"]["rect"])
    contract = [s["text"] for s in head_row]
    if len(dates) != 2 or len(contract) != 6 or contract[1] != "Change" or contract[4] != "Change":
        return None
    heads = []
    for ex in ("DCE", "SGX"):
        h = next((s["text"] for s in spans if s["text"].startswith(ex + " (")), None)
        m = re.match(r"^(DCE|SGX)\s*\(([^)]+)\)$", h or "")
        if not m:
            return None
        heads.append((m.group(1), m.group(2)))
    columns = [{"exchange": heads[i][0], "unit": heads[i][1], "closing_date": dates[i], "contract": contract[3 * i]}
               for i in range(2)]
    rows = []
    for metric in FUT_ROWS:
        row = _row(spans, lab[metric]["rect"])
        for h in (s for s in row if s["text"] == "HOLIDAY"):      # stamped across a closed exchange's column
            nums_left = sum(1 for s in row if s["text"] != "HOLIDAY" and s["rect"].x0 < h["rect"].x0)
            columns[0 if nums_left < 3 else 1]["holiday"] = True
        nums = [s for s in row if s["text"] != "HOLIDAY"]
        cells = [s["text"] for s in nums]
        if len(cells) != 6:
            # a cell the print leaves blank (2023-04-27: DCE volume change %): place each number under
            # the nearest header column (right-aligned, so compare right edges); blank columns -> None
            slots = [None] * 6
            for s in nums:
                i = min(range(6), key=lambda j: abs(head_row[j]["rect"].x1 - s["rect"].x1))
                if slots[i] is not None or abs(head_row[i]["rect"].x1 - s["rect"].x1) > 15:
                    return None
                slots[i] = s["text"]
            cells = slots
        if not all(c is None or NUM.match(c) for c in cells) or cells[0] is None or cells[3] is None:
            return None
        rows.append({"metric": metric, "cells": cells})
    return {"columns": columns, "rows": rows}


def signed(change, pct=None):
    """The print omits '+' and, on some cards, the sign of the change itself. Add '+' only when
    neither the change nor its percentage carries a minus sign; otherwise keep the printed text."""
    if change.startswith("-") or (pct is not None and pct.startswith("-")):
        return change
    return "+" + change
