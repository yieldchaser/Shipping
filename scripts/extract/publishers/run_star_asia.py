"""
Source #2: STAR ASIA pipeline.

Built from MEASURED facts (docs/star_asia_survey.md), not copied from
advanced_shipping - two publishers with opposite conventions:

  star_asia                        advanced_shipping
  ---------                        -----------------
  16-21 pages                      9-12 pages
  charts RASTER (no vector pages)  charts VECTOR (exact geometry)
  ISO numbers 29,580 = 29580       European 60.000 = 60000
  charts restate the text tables   charts carry unique weekly series

Reused deliberately: the resumable state checkpoint, per-document output of
.md/.tables.json/.charts.json, the pdf-inspector + liteparse value-anchored
table merge, ocr_enabled=False.

NOT reused: the European number parser and the vector chart calibration, which
would both be WRONG here.
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))

import pymupdf  # noqa: E402

PUB = "star_asia"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

# pdf-inspector gives better table cells; liteparse blocks carry labels it drops.
# Same two-engine merge as source 1, which is the general part.
NUM = re.compile(r"^[\d.,%$+\-\s]+$")
PROSE = re.compile(r"[a-z]{4,}\s+[a-z]{4,}\s+[a-z]{4,}")


def parse_number(tok):
    """Star Asia = ISO/US: '29,580' is 29580, '34.5' is 34.5.

    NOTE: this is NOT the European rule used for advanced_shipping, where
    '60.000' means 60000. Comma here groups THOUSANDS.
    """
    if tok is None:
        return None
    s = str(tok).strip().replace("%", "").replace("$", "").strip()
    if not s:
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    # ISO/US: comma = thousands separator, period = decimal point
    s = s.replace(",", "")
    if s.count(".") > 1:                 # 1.234.567 is not ISO; leave malformed
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}}


def save_state(st):
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def tables_from_pdfinspector(pdf: Path):
    try:
        import pdf_inspector as pi
        out = pi.process_pdf(str(pdf))
        md = out if isinstance(out, str) else getattr(out, "markdown", None) or str(out)
    except (ImportError, Exception):
        sidecar = OUT / f"{pdf.stem}.tables.json"
        if sidecar.exists():
            try:
                loaded = json.loads(sidecar.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    return loaded, ""
            except Exception:
                pass
        return [], ""
    tables, cur = [], None
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if cur is None:
                cur = {"header": cells, "rows": []}
            else:
                cur["rows"].append(cells)
        else:
            if cur and cur["rows"]:
                tables.append(cur)
            cur = None
    if cur and cur["rows"]:
        tables.append(cur)
    # keep tables with real numeric content
    keep = []
    for t in tables:
        flat = " ".join(c for r in t["rows"] for c in r)
        if len(re.findall(r"\d", flat)) >= 4:
            keep.append(t)
    return keep, md



def merge_missing_labels(tables, pdf: Path):
    """Adopt liteparse block rows where pdf-inspector lost or mangled labels.

    Value-anchored: a block is adopted only when it shares >=2 non-trivial
    values with the row group. An earlier positional version attached labels to
    the wrong rows - a wrong label is worse than a missing one.
    """
    import liteparse
    need = False
    for t in tables:
        for r in t["rows"]:
            if r and r[0] and NUM.match(r[0]) and len(r) >= 3:
                need = True
                break
        if need:
            break
    if not need:
        return tables
    try:
        lp = liteparse.LiteParse(extract_blocks=True, ocr_enabled=False,
                                 quiet=True, output_format="markdown")
        res = lp.parse(str(pdf))
    except Exception:
        return tables
    cands = []
    for i in range(1, res.num_pages + 1):
        for b in (res.get_page(i).blocks or []):
            if not b.rows:
                continue
            rows = [[c.text.strip() for c in row] for row in b.rows]
            if any(len(c) > 100 for r in rows for c in r):
                continue
            hdr = [c.text.strip() for c in b.header] if b.header else []
            vals = {c for r in rows for c in r if c and NUM.match(c) and len(c) >= 3}
            if vals:
                cands.append((hdr, rows, vals))

    def nums(rows):
        return {c for r in rows for c in r if c and NUM.match(c) and len(c) >= 3}

    for t in tables:
        rows = t["rows"]
        if len(rows) < 3:
            continue
        out, i = [], 0
        while i < len(rows):
            r = rows[i]
            if not (r and r[0] and NUM.match(r[0]) and len(r) >= 3):
                out.append(r)
                i += 1
                continue
            j = i
            while j < len(rows) and rows[j] and rows[j][0] and NUM.match(rows[j][0]):
                j += 1
            group = rows[i:j]
            gv = nums(group)
            replaced = False
            if len(group) >= 2:
                for hdr, lrows, lv in cands:
                    if len(gv & lv) >= 2:
                        out.extend(lrows)
                        replaced = True
                        break
            if not replaced:
                out.extend(group)
            i = j
        t["rows"] = out
    return tables


def drop_prose_rows(tables):
    """Remove rows that are narrative, not data.

    Star Asia's charts are raster and restate the text tables, so unlike source
    1 there is no clean block to substitute. Removing the narrative rows is the
    honest action: it leaves the real data and discards text that is prose, not
    values. Rows are dropped only when a cell is BOTH long and sentence-like.
    """
    for t in tables:
        kept = []
        for r in t["rows"]:
            if any(len(c) > 100 and PROSE.search(c) for c in r):
                continue
            kept.append(r)
        t["rows"] = kept
    return [t for t in tables if t["rows"]]


def _parse_sp_fixtures_block(sp_text: str, valid_types: list[str]) -> list[str]:
    """Parse Sale & Purchase reported fixtures table rows cleanly, handling multi-line vessel & buyer names."""
    sp_lines = [l.strip() for l in sp_text.splitlines() if l.strip()]
    i = 0
    while i < len(sp_lines) and not (sp_lines[i].startswith("BUYER") or sp_lines[i].startswith("PRICE")):
        i += 1
    if i < len(sp_lines) and sp_lines[i].startswith("PRICE"):
        i += 1
        if i < len(sp_lines) and sp_lines[i].startswith("BUYER"):
            i += 1
    else:
        i += 1

    stop_markers = ("snp@starasiasg.com", "Member of BIMCO", "Page ", "Vessel Value", "Baltic ")
    rows_out: list[str] = []

    def _is_type_token(idx: int) -> tuple[str, int]:
        if idx >= len(sp_lines):
            return "", 0
        tok = sp_lines[idx].upper()
        if tok == "POST" and idx + 1 < len(sp_lines) and sp_lines[idx + 1].upper() == "PMAX":
            return "POST PMAX", 2
        if tok in valid_types:
            return tok, 1
        return "", 0

    while i < len(sp_lines):
        if any(m in sp_lines[i] for m in stop_markers):
            break
        v_parts = [sp_lines[i]]
        i += 1
        while i < len(sp_lines):
            if any(m in sp_lines[i] for m in stop_markers):
                break
            t_match, _ = _is_type_token(i)
            if t_match:
                break
            v_parts.append(sp_lines[i])
            i += 1
        v_name = " ".join(v_parts).strip()
        v_name = re.sub(r"^BUYER\s+", "", v_name)
        v_type, consumed = _is_type_token(i)
        if not v_type:
            break
        i += consumed

        v_dwt = ""
        if i < len(sp_lines) and re.match(r"^[\d,]+(?:\s*/\s*[\d,]+)?$", sp_lines[i]):
            v_dwt = sp_lines[i]
            i += 1
            if i < len(sp_lines) and re.match(r"^[\d,]+$", sp_lines[i]):
                v_dwt = f"{v_dwt} / {sp_lines[i]}"
                i += 1

        v_built = ""
        if i < len(sp_lines) and re.search(r"\b(19\d\d|20\d\d)\b", sp_lines[i]):
            v_built = sp_lines[i]
            i += 1
            if i < len(sp_lines) and re.match(r"^/\s*[A-Z]+$", sp_lines[i]):
                v_built = f"{v_built} {sp_lines[i]}"
                i += 1

        v_price = ""
        if i < len(sp_lines) and (re.search(r"\d", sp_lines[i]) or sp_lines[i] in ["-", "N/A", "UNDISCLOSED"]):
            v_price = sp_lines[i]
            i += 1

        # Buyer: consume lines until the next vessel row (which is followed within 1-2 lines by a valid_type + DWT)
        buyer_suffixes = {
            "BUYER", "BUYERS", "CLIENTS", "HOLDINGS", "HOLDING", "LIMITED", "LTD", "LTD.",
            "INC", "INC.", "CORP", "CORP.", "CORPORATION", "SHIPPING", "LINES", "LINE",
            "NAVIGATION", "MARITIME", "GROUP", "COMPANY", "CO", "CO.", "CONTAINER",
            "LOGISTICS", "INVEST", "INVESTMENT", "INVESTMENTS", "TRANSPORT", "TRADING", "SA", "S.A.", "LLC"
        }
        b_parts: list[str] = []
        while i < len(sp_lines):
            if any(m in sp_lines[i] for m in stop_markers):
                break
            tok_up = sp_lines[i].upper().rstrip(",.")
            t1, c1 = _is_type_token(i + 1)
            t2, c2 = _is_type_token(i + 2)
            # If sp_lines[i+1] is a valid vessel type AND followed by a DWT number, sp_lines[i] is the next vessel
            if t1 and (i + 1 + c1 < len(sp_lines)) and re.match(r"^[\d,]+", sp_lines[i + 1 + c1]):
                break
            if not b_parts:
                b_parts.append(sp_lines[i])
                i += 1
            elif tok_up in buyer_suffixes:
                b_parts.append(sp_lines[i])
                i += 1
                if t1 and (i + c1 < len(sp_lines)) and re.match(r"^[\d,]+", sp_lines[i + c1]):
                    break
            elif t2 and (i + 2 + c2 < len(sp_lines)) and re.match(r"^[\d,]+", sp_lines[i + 2 + c2]):
                break
            else:
                if t2:
                    break
                b_parts.append(sp_lines[i])
                i += 1

        v_buyer = " ".join(b_parts).strip()
        if v_name and v_type and (v_dwt or v_built):
            rows_out.append(f"| {v_name} | {v_type} | {v_dwt} | {v_built} | {v_price} | {v_buyer} |")

    return rows_out


# ---------------------------------------------------------------------------
# Text-layer + word-geometry builders (2026-10 audit). The LiteParse route lost the Alang section, emptied the
# VESSEL/TYPE header cells (so clean_star_asia dropped those columns), merged Reported Sales rows, cut paragraphs
# and wrote "AWAITING" into blank BEACHING cells. These builders read only what the page prints.
# ---------------------------------------------------------------------------
_TYPO = {"–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "�": "-"}
_RUNNING = re.compile(r"^(STAR ASIA\s*\||Week \d+\s*\||snp@|Page \d+$|Member of BIMCO|\(A Member of BIMCO|Singapore \| London"
                      r"|Tel:|For Privacy Policy|This report is performed|and we emphasise|have obtained from|upon this report"
                      r"|action or failure to act)")
_LDT = re.compile(r"^\d{1,3}(,\d{3})*$")
_LABEL = re.compile(r"^((?:Alang|Chattogram|Gaddani|Gadani|Aliaga), (?:India|Bangladesh|Pakistan|Turkey|Türkiye|Turkiye)"
                    r"|India|Pakistan|Bangladesh|Turkiye|Türkiye|Turkey|China):\s")


def _typo(s: str) -> str:
    for a, b in _TYPO.items():
        s = s.replace(a, b)
    return s


def _word_lines(words, tol=3.0):
    out = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        if out and abs(out[-1][0] - cy) <= tol:
            out[-1][1].append(w)
        else:
            out.append([cy, [w]])
    return [(cy, sorted(ws, key=lambda w: w[0])) for cy, ws in out]


def _body_words(page: pymupdf.Page):
    """Page words without the running header/footer bands (a table's last row must not absorb the footer)."""
    h = page.rect.height
    top, bot = 0.0, h
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            s = "".join(sp["text"] for sp in ln["spans"]).strip()
            if not s or not _RUNNING.match(s):
                continue
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            if y1 < h * 0.15:
                top = max(top, y1)
            elif y0 > h * 0.85:
                bot = min(bot, y0)
    return [w for w in page.get_text("words") if w[1] >= top - 0.5 and w[3] <= bot + 0.5]


def vessel_tables(page: pymupdf.Page):
    """Tables whose header line holds VESSEL, TYPE and LDT (Reported Sales, <Port> Anchorage & Beaching Position).
    Columns = header word clusters; rows anchored on the LDT number; other words join the nearest anchor row
    (multi-line cells such as 'GENERAL / CARGO'). Returns [(title, header, rows, y_top, y_bottom)]; an empty
    printed table ('-' cells) gives rows == []."""
    L = _word_lines(_body_words(page))
    res = []
    for k, (cy, ws) in enumerate(L):
        hw = {w[4] for w in ws}
        anchor_name = next((a for a in ("LDT", "DWT", "TEU") if a in hw), None)
        if not ({"VESSEL", "TYPE"} <= hw and anchor_name):
            continue
        cols = []
        for w in ws:
            if cols and w[0] - cols[-1][2] < 12:
                cols[-1][2] = w[2]; cols[-1][3] += " " + w[4]
            else:
                cols.append([w[0], cy, w[2], w[4]])
        ldt = next(i for i, c in enumerate(cols) if c[3] == anchor_name)
        tx0, tx1 = cols[0][0] - 5, max(c[2] for c in cols) + 40
        body, last = [], cy
        for cy2, ws2 in L[k + 1:]:
            wide = (ws2[-1][2] - ws2[0][0]) > 0.7 * (tx1 - tx0)
            # prose flows word to word; a table line (even the top half of a stacked row) has column gaps
            col_gaps = sum(1 for a, b2 in zip(ws2, ws2[1:]) if b2[0] - a[2] > 12)
            if cy2 - last > 28 or (len(ws2) > 9 and wide and col_gaps < 2 and not any(_LDT.match(w[4]) for w in ws2)):
                break
            if any(w[4] in ("VESSEL", "Vessel") for w in ws2) and cy2 - cy > 5:
                break
            body.append((cy2, ws2)); last = cy2

        def col_of(w):
            mx = (w[0] + w[2]) / 2
            c = [i for i in range(len(cols)) if mx >= cols[i][0] - 6]
            return c[-1] if c else 0
        anchors = []
        for cy2, ws2 in body:
            cell = "".join(w[4] for w in ws2 if col_of(w) == ldt)
            if re.fullmatch(r"\d{1,3}([,.]\d{3})*(\.\d{1,2})?(/\d{1,3}(,\d{3})*)?", cell):
                anchors.append(cy2)
        rows = [[[] for _ in cols] for _ in anchors]
        if anchors:
            for cy2, ws2 in body:
                for w in ws2:
                    r = min(range(len(anchors)), key=lambda i: abs(anchors[i] - cy2))
                    rows[r][col_of(w)].append((cy2, w[0], w[4]))
        # one row listing several vessels ('38.8 EACH', '60.0 ENBLOC'): each printed name line is its own vessel
        multi = [any(re.search(r"\b(EACH|ENBLOC|EN BLOC)\b", " ".join(x[2] for x in c)) for c in r) for r in rows]

        def _vessel_cell(c):
            lines = []
            for y, x, t in sorted(c):
                if lines and abs(lines[-1][0] - y) <= 3:
                    lines[-1][1].append(t)
                else:
                    lines.append([y, [t]])
            names = [" ".join(ts) for _, ts in lines]
            if len(names) > 1 and not any("/" in n for n in names):   # printed slashes already split the names
                return " / ".join(names)
            return " ".join(names)
        def _plain_cell(c):
            parts = [t for _, _, t in sorted(c)]
            # one number per stacked vessel line (prices 70.0 over 73.0): keep them apart
            if len(parts) > 1 and len({round(y) for y, _, _ in c}) == len(parts) and all(re.fullmatch(r"[\d,.]+", p) for p in parts):
                return " / ".join(parts)
            return " ".join(parts)
        rows = [[_typo(_vessel_cell(c) if i == 0 and multi[k] else _plain_cell(c))
                 for i, c in enumerate(r)] for k, r in enumerate(rows)]
        rows = [[re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", c) if i == ldt else c for i, c in enumerate(r)] for r in rows]
        # printed slips: dd.mmyyyy (01.102026) -> dd.mm.yyyy; AWAIITNG -> AWAITING
        rows = [[re.sub(r"^(\d\d)\.(\d\d)(\d{4})$", r"\1.\2.\3", c).replace("AWAIITNG", "AWAITING")
                 .replace("�WAITING", "AWAITING").replace("ÀWAITING", "AWAITING") for c in r] for r in rows]
        # stacked two-vessel rows ('LUCTOR /' over 'TURMOIL', DWT stacked): the row without a TYPE joins its partner
        hdr_names = [c[3] for c in cols]
        ti = hdr_names.index("TYPE") if "TYPE" in hdr_names else None
        if ti is not None and len(rows) > 1:
            merged = []
            for r in rows:
                if merged and not r[ti] and merged[-1][0].rstrip().endswith("/"):
                    prev = merged[-1]
                    merged[-1] = [prev[0] + " " + r[0]] + [_stack(prev[i], r[i], i == ldt) for i in range(1, len(r))]
                else:
                    merged.append(r)
            out2 = []
            i = 0
            while i < len(merged):
                r = merged[i]
                bare = all(not r[k] for k in range(1, len(r)) if k != ldt)
                if not r[ti] and (r[0].rstrip().endswith("/") or bare) and i + 1 < len(merged):
                    nx = merged[i + 1]
                    out2.append([r[0] + (" " if r[0].rstrip().endswith("/") else " / ") + nx[0]] + [
                        _stack(r[k], nx[k], k == ldt) for k in range(1, len(r))])
                    i += 2
                    continue
                out2.append(r)
                i += 1
            rows = out2
        title = _typo(" ".join(w[4] for w in L[k - 1][1])) if k else ""
        res.append((title, [c[3] for c in cols], rows, L[k - 1][0] - 4 if k else cy - 4, last + 4))
    return res


def _stack(a, b, anchor):
    """Cell of two stacked lines: anchors (DWT/LDT) as 'a / b'; other text continues ('EUROPEAN' + 'BUYERS')."""
    if a and b and a != b:
        both_num = all(re.fullmatch(r"[\d,.]+", x) for x in (a, b))   # per-vessel prices 70.0 / 73.0
        return a + (" / " if anchor or both_num else " ") + b
    return a or b


def _table_md(header, rows, align=None):
    out = ["| " + " | ".join(header) + " |", align or "|" + "---|" * len(header)]
    out += ["| " + " | ".join(c if c else " " for c in r) + " |" for r in rows]
    return "\n".join(out)


def _paragraphs(lines):
    """Text-layer lines -> paragraphs: blank line / large gap / label start opens a new one; a line ending in '-'
    joins the next without a space (dollar-/priced, near-/term)."""
    paras, cur, last_y = [], "", None
    for y, txt in lines:
        txt = _typo(txt.strip())
        if not txt:
            continue
        new = cur and (last_y is not None and y - last_y > 16 or _LABEL.match(txt))
        if new:
            paras.append(cur); cur = ""
        cur = cur + txt if cur.endswith("-") or not cur else cur + " " + txt
        last_y = y
    if cur:
        paras.append(cur)
    out = []
    for p in paras:
        m = _LABEL.match(p)
        out.append(f"**{m.group(1)}:** {p[m.end():]}" if m else p)
    return out


def _page_text_lines(page, exclude=()):
    """(y, text) per text-layer line, running header/footer removed, lines inside `exclude` y-bands dropped."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            y = (ln["bbox"][1] + ln["bbox"][3]) / 2
            if not t or _RUNNING.match(t) or any(a <= y <= z for a, z in exclude):
                continue
            out.append((y, ln["bbox"][0], t))
    out.sort()
    merged = []
    for y, x, t in out:      # same visual line split into spans -> one line
        if merged and abs(merged[-1][0] - y) < 2.5:
            merged[-1] = (merged[-1][0], merged[-1][1] + " " + t)
        else:
            merged.append((y, t))
    return merged


_HEADINGS = {
    "Market Insights": "## Market Insights",
    "SUB-CONTINENT & TURKEY SCRAP MARKETS": "# SUB-CONTINENT & TURKEY SCRAP MARKETS",
    "COMMODITIES, BUNKERS & RATES": "# COMMODITIES, BUNKERS & RATES",
    "Commodities Focus": "## Commodities Focus",
}


def anchorage_page_md(page: pymupdf.Page) -> str:
    """Market Insights / Anchorage & Beaching pages, in print order: port commentary (bold port labels), each
    '<Port> Anchorage & Beaching Position' table from word geometry, TIDE DATES, scrap-market commentary."""
    tabs = vessel_tables(page)
    events = [(y0, "T", (title, hdr, rows)) for title, hdr, rows, y0, y1 in tabs]
    lines = _page_text_lines(page, exclude=[(y0, y1) for *_, y0, y1 in tabs])
    out, buf = [], []

    def flush():
        if buf:
            out.extend(p + "\n" for p in _paragraphs(buf)); buf.clear()
    seq = sorted([(y, "L", t) for y, t in lines] + events, key=lambda e: e[0])
    for y, kind, v in seq:
        if kind == "T":
            flush()
            title, hdr, rows = v
            if title:
                out.append(f"## {title}\n")
            out.append((_table_md(hdr, rows) if rows else _table_md(hdr, [["-"] * len(hdr)])) + "\n")
            continue
        t = _typo(v).strip()
        if t in _HEADINGS:
            flush(); out.append(_HEADINGS[t] + "\n")
        elif t.startswith("TIDE DATES"):
            flush()
            if out and out[-1].startswith("## TIDE DATES"):
                out[-1] = out[-1].rstrip("\n") + " " + t + "\n"
            else:
                out.append(f"## {t}\n")
        elif re.match(r"^(Alang|Chattogram):\s", t) and out and out[-1].startswith("## TIDE DATES") and not buf:
            out[-1] = out[-1].rstrip("\n") + " " + t + "\n"
        else:
            buf.append((y, t))
    flush()
    return "\n".join(out).strip()


def prose_before(page: pymupdf.Page, stop_titles) -> str:
    """Prose and section headings above the first table title on a page (e.g. Commodities Focus above Iron Ore)."""
    lines = _page_text_lines(page)
    stop = next((y for y, t in lines if t.strip() in stop_titles
                 or t.strip().startswith(("INDEX UNITS", "COMMODITY (USD", "CURRENCY PAIR"))), None)
    out, buf = [], []
    for y, t in lines:
        if stop is not None and y >= stop:
            break
        t = _typo(t).strip()
        if t in _HEADINGS:
            if buf:
                out.extend(_paragraphs(buf)); buf = []
            out.append(_HEADINGS[t])
        else:
            buf.append((y, t))
    if buf:
        out.extend(_paragraphs(buf))
    return "\n\n".join(out)


def note_lines(page: pymupdf.Page, start: str, stop_prefixes) -> list:
    """Footnote block starting with `start` (e.g. '* Turkey prices'), up to a line starting with a stop prefix."""
    lines = _page_text_lines(page)
    i = next((k for k, (_, t) in enumerate(lines) if t.strip().startswith(start)), None)
    if i is None:
        return []
    out = []
    for _, t in lines[i:]:
        t = _typo(t).strip()
        if any(t.startswith(s) for s in stop_prefixes):
            break
        if t in ("", "•", "-") or len(t) <= 1:
            out.append("")
            continue
        out.append(t)
    blocks, cur = [], ""
    for t in out:
        if not t:
            if cur:
                blocks.append(cur); cur = ""
            continue
        cur = cur + t if cur.endswith("-") or not cur else cur + " " + t
    if cur:
        blocks.append(cur)
    return blocks


def _segment_md(page: pymupdf.Page, text: str, with_sp: bool = True) -> str:
    """'SEGMENT (AVG)' annual-average table (USD / Day); with_sp also emits a S&P table spilling onto the page."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    try:
        idx = lines.index("SEGMENT (AVG)")
    except ValueError:
        return ""
    headers = ["SEGMENT (AVG)"]
    j = idx + 1
    while j < len(lines) and (re.match(r"^(?:19\d\d|20\d\d)(?:\s*YTD)?$", lines[j]) or lines[j].isdigit()):
        headers.append(lines[j])
        j += 1
    num_cols = len(headers)
    if num_cols < 2:
        return ""

    known_segments = [
        "CAPESIZE", "PANAMAX", "SUPRAMAX", "HANDY", "HANDYSIZE",
        "VLCC", "SUEZMAX", "AFRAMAX", "MR", "LR1", "LR2",
        "1000 TEU", "1,700 TEU", "2,750 TEU", "9,000 TEU"
    ]
    rows = []
    cur_seg = None
    cur_vals = []
    while j < len(lines):
        line = lines[j]
        if any(line.upper().startswith(s) for s in known_segments):
            if cur_seg and cur_vals:
                rows.append((cur_seg, cur_vals))
            cur_seg = line
            cur_vals = []
        elif cur_seg and (line.startswith("$") or re.match(r"^[\d,]+$", line)):
            cur_vals.append(line)
        elif line.startswith("snp@") or "Member of BIMCO" in line or "Page " in line:
            break
        j += 1
    if cur_seg and cur_vals:
        rows.append((cur_seg, cur_vals))

    if not rows:
        return ""

    title = "### Segment Annual Averages (USD / Day)"
    if any(r[0] in ["CAPESIZE", "PANAMAX", "SUPRAMAX", "HANDY"] for r in rows):
        title = "### Dry Bulk Annual Averages (USD / Day)"
    elif any(r[0] in ["VLCC", "SUEZMAX", "AFRAMAX", "MR"] for r in rows):
        title = "### Tanker Annual Averages (USD / Day)"
    elif any("TEU" in r[0] for r in rows):
        title = "### Container Annual Averages (USD / Day)"

    out = []
    # a Sale & Purchase table spilling over from the previous page sits above the averages
    for _, g_hdr, g_rows, *_ in (vessel_tables(page) if with_sp else []):
        if g_rows and ("DWT" in g_hdr or "TEU" in g_hdr):
            out.append("### Sale & Purchase - Reported Fixtures (continued)\n")
            out.append(_table_md(g_hdr, [[c or "-" for c in r] for r in g_rows]) + "\n")
    out.append(title + "\n")
    out.append("| " + " | ".join(headers) + " |")
    out.append("| :--- | " + " | ".join([":---:"] * (len(headers) - 1)) + " |")
    for seg, vals in rows:
        val_str = " | ".join(vals)
        out.append(f"| {seg} | {val_str} |")
    return "\n".join(out)


def build_star_asia_clean_page(page: pymupdf.Page, lp_md: str = "") -> str:
    """Reconstructs clean markdown for tabular pages with proper headers and complete columns."""
    text = page.get_text("text").replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")

    # 1 & 2. PAGES: Dry Bulk & Tankers (Indices, Vessel Values, and/or Sale & Purchase, even when split across pages)
    has_dry_idx = bool(re.search(r"\bBDI\s*\n\s*[\d,]+\s*\n\s*WoW:", text))
    has_tkr_idx = bool(re.search(r"\bBDTI\s*\n\s*[\d,]+\s*\n\s*WoW:", text))
    has_vv = bool(re.search(r"Vessel Values?\b", text)) and ("CONTAINERS" not in text)
    has_sp = ("Sale & Purchase" in text) and ("CONTAINERS" not in text) and ("SHIP RECYCLING" not in text)

    if has_dry_idx or has_tkr_idx or has_vv or has_sp or "Baltic Dry Indices" in text or "Baltic Tanker Indices" in text:
        out_lines: list[str] = []

        # Preserve narrative commentary if the page has prose above the tables (e.g. Tankers Page 5)
        if lp_md:
            cut_markers = [
                "Baltic Dry Indices", "Baltic Tanker Indices", "### Baltic", "## Baltic",
                "Vessel Values", "## Vessel Values", "\n| BDTI", "\n| BDI", "\n| TYPE | DWT"
            ]
            prose_part = lp_md
            for cm in cut_markers:
                pos = prose_part.find(cm)
                if pos != -1:
                    prose_part = prose_part[:pos]
            # Strip trailing standalone index names or table remnants at the bottom of prose_part
            prose_part = re.sub(r"(?m)^#*\s*(?:BDTI|BCTI|BDI|BCI|BPI|BSI|BHSI|Sale & Purchase.*)\s*$", "", prose_part).strip()
            prose_part = re.sub(r"(?s)\n+#*\s*(?:BDTI|BCTI|BDI)\b.*$", "", prose_part).strip()
            prose_part = re.sub(r"(?m)^#+\s*$", "", prose_part).strip()
            prose_part = re.sub(r"(\d) \.(\d)", r"\1.\2", prose_part)   # LiteParse splits '1.27' as '1 .27'
            if len(prose_part) > 120:
                out_lines.append(prose_part + "\n")

        if has_dry_idx:
            out_lines.append("### Baltic Dry Index (BDI)\n")
            m_bdi = re.search(r"BDI\s*\n\s*([\d,]+)\s*\n\s*WoW:\s*([^\n]+)\s*\n\s*YoY:\s*([^\n]+)", text)
            if m_bdi:
                bdi_val, bdi_wow, bdi_yoy = m_bdi.groups()
                out_lines.append(f"**BDI: {bdi_val}** (WoW: {bdi_wow.strip()} | YoY: {bdi_yoy.strip()})\n")

            sub_hdrs = ["BCI", "BPI", "BSI", "BHSI"]
            vals, wows, yoys = [], [], []
            for h in sub_hdrs:
                m = re.search(rf"{h}\s*\n\s*([\d,]+)\s*\n\s*WoW:\s*([^\n]+)\s*\n\s*YoY:\s*([^\n]+)", text)
                if m:
                    v, w, y = m.groups()
                    vals.append(v)
                    wows.append(w.strip())
                    yoys.append(y.strip())
                else:
                    vals.append("-"); wows.append("-"); yoys.append("-")
            out_lines.append("| " + " | ".join(sub_hdrs) + " |")
            out_lines.append("| " + " | ".join([":---:"] * 4) + " |")
            out_lines.append("| " + " | ".join(vals) + " |")
            out_lines.append("| " + " | ".join(f"WoW: {w}" for w in wows) + " |")
            out_lines.append("| " + " | ".join(f"YoY: {y}" for y in yoys) + " |\n")

        if has_tkr_idx:
            out_lines.append("### Baltic Tanker Indices\n")
            sub_hdrs = ["BDTI", "BCTI"]
            vals, wows, yoys = [], [], []
            for h in sub_hdrs:
                m = re.search(rf"{h}\s*\n\s*([\d,]+)\s*\n\s*WoW:\s*([^\n]+)\s*\n\s*YoY:\s*([^\n]+)", text)
                if m:
                    v, w, y = m.groups()
                    vals.append(v)
                    wows.append(w.strip())
                    yoys.append(y.strip())
                else:
                    vals.append("-"); wows.append("-"); yoys.append("-")
            out_lines.append("| " + " | ".join(sub_hdrs) + " |")
            out_lines.append("| " + " | ".join([":---:"] * 2) + " |")
            out_lines.append("| " + " | ".join(vals) + " |")
            out_lines.append("| " + " | ".join(f"WoW: {w}" for w in wows) + " |")
            out_lines.append("| " + " | ".join(f"YoY: {y}" for y in yoys) + " |\n")

        if has_vv:
            vv_search_text = text[:text.find("Sale & Purchase")] if "Sale & Purchase" in text else text
            vv_search_text = re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", vv_search_text)
            vv_rows: list[str] = []
            for v_type in ["CAPESIZE", "KAMSARMAX", "ULTRAMAX", "HANDY", "VLCC", "SUEZMAX", "AFRAMAX", "LR1", "MR"]:
                m_vv = re.search(rf"{v_type}\s*\n\s*([\d,]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)", vv_search_text)
                if m_vv:
                    dwt, nb_c, nb_p, y5, y10, y15 = [x.strip() for x in m_vv.groups()]
                    vv_rows.append(f"| {v_type} | {dwt} | {nb_c} | {nb_p} | {y5} | {y10} | {y15} |")
            if vv_rows:
                out_lines.append("### Vessel Values (USD Million)\n")
                out_lines.append("| TYPE | DWT | NB CONTRACT | NB PROMPT | 5 YRS | 10 YRS | 15 YRS |")
                out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
                out_lines.extend(vv_rows)
                out_lines.append("")

        if has_sp:
            sp_start = text.find("Sale & Purchase")
            if sp_start != -1:
                all_sp_types = [
                    "CAPE", "POST", "PMAX", "KMAX", "UMAX", "SMAX", "HANDY", "POST PMAX",
                    "VLCC", "SUEZ", "AFRA", "LR2", "LR1", "MR", "SMALL", "CHEM", "PROD"
                ]
                geo_sp = [v for v in vessel_tables(page) if v[1] and ("DWT" in v[1] or "TEU" in v[1])]
                if geo_sp and geo_sp[0][2]:
                    sp_rows = ["| " + " | ".join(c or "-" for c in (r + [""] * 6)[:6]) + " |" for r in geo_sp[0][2]]
                else:
                    sp_rows = _parse_sp_fixtures_block(text[sp_start:], all_sp_types)
                if sp_rows:
                    out_lines.append("### Sale & Purchase - Reported Fixtures\n")
                    out_lines.append("| VESSEL | TYPE | DWT | YEAR / BUILT | PRICE (USD M) | BUYER |")
                    out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
                    out_lines.extend(sp_rows)

        if out_lines:
            if "SEGMENT (AVG)" in text:
                seg = _segment_md(page, text, with_sp=False)
                if seg:
                    out_lines.append("\n" + seg)
            return "\n".join(out_lines)

    # 3. PAGE: Containers
    elif "CONTAINERS" in text and "Vessel Values" in text:
        out_lines = ["# CONTAINERS\n"]
        m_comm = re.search(r"CONTAINERS\s*\n\s*(.*?)\s*\n\s*(?:Vessel Values|Sale & Purchase)", text, re.DOTALL)
        if m_comm:
            para = re.sub(r"\s+", " ", m_comm.group(1)).strip()
            out_lines.append(f"{para}\n")

        out_lines.append("### Vessel Values (USD Million)\n")
        out_lines.append("| SIZE (TEU) | TYPE | NB CONTRACT | NB PROMPT | 5 YRS | 10 YRS | 15 YRS |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        vv_part = text[text.find("Vessel Values"):]
        m_rows = re.findall(r"([\d,]+\s*[-–—]\s*[\d,]+)\s*\n\s*(Geared|Gearless)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)", vv_part)
        for r in m_rows:
            sz, tp, nb_c, nb_p, y5, y10, y15 = [x.strip() for x in r]
            out_lines.append(f"| {sz} | {tp} | {nb_c} | {nb_p} | {y5} | {y10} | {y15} |")
        out_lines.append("")

        sp_start = text.find("Sale & Purchase")
        if sp_start != -1:
            geo_sp = [v for v in vessel_tables(page) if v[1] and ("DWT" in v[1] or "TEU" in v[1])]
            if geo_sp and geo_sp[0][2]:
                sp_rows = ["| " + " | ".join(c or "-" for c in (r + [""] * 6)[:6]) + " |" for r in geo_sp[0][2]]
            else:
                sp_rows = _parse_sp_fixtures_block(text[sp_start:], ["FEEDER", "CONTAINER", "SUB-PMAX", "PMAX", "POST PMAX", "NEOPANAMAX"])
            if sp_rows:
                out_lines.append("### Sale & Purchase - Reported Fixtures\n")
                out_lines.append("| VESSEL | TYPE | TEU | YEAR / BUILT | PRICE (USD M) | BUYER |")
                out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
                out_lines.extend(sp_rows)

        return "\n".join(out_lines)

    # 4. PAGE: Ship Recycling
    elif "SHIP RECYCLING" in text and "Current Market Snapshot" in text:
        out_lines = ["### Ship Recycling - Current Market Snapshot (USD / LDT)\n"]
        snap_hdr = ["DESTINATION", "TANKERS", "BULKERS", "GENERAL CARGO", "CONTAINERS", "OUTLOOK / SENTIMENTS"]
        m_sh = re.search(r"Current Market Snapshot[^\n]*\n(.*?)\n\s*ALANG", text, re.S)
        if m_sh:
            cells = [" ".join(c.split()) for c in m_sh.group(1).split("\n") if c.strip()]
            joined = []
            for c in cells:
                if joined and joined[-1] == "GENERAL" and c == "CARGO":
                    joined[-1] = "GENERAL CARGO"
                else:
                    joined.append(c)
            if len(joined) == 6 and joined[0] == "DESTINATION":
                snap_hdr = joined
        out_lines.append("| " + " | ".join(snap_hdr) + " |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        dest_defs = [
            ("ALANG, INDIA", r"ALANG\s*,\s*INDIA\*?"),
            ("CHATTOGRAM, BANGLADESH", r"CHATTOGRAM\s*,\s*BANGLADESH\*?"),
            ("GADDANI, PAKISTAN", r"GADDANI\s*,\s*PAKISTAN\*?"),
            ("ALIAGA, TURKEY", r"ALIAGA\s*,\s*T[UÜ]RK(?:EY|[Iİ]YE)\*?"),
        ]
        # Split text at '5-Year Historical' if present so Current Snapshot and 5-Year Average don't collide
        snap_text = text
        hist_text = ""
        m_hist_hdr = re.search(r"5-Year Historical Average[^\n]*", text, re.IGNORECASE)
        if m_hist_hdr:
            snap_text = text[:m_hist_hdr.start()]
            rs_cut = text.find("Reported Sales", m_hist_hdr.start())
            hist_text = text[m_hist_hdr.start():rs_cut] if rs_cut != -1 else text[m_hist_hdr.start():]

        for dest, dest_pat in dest_defs:
            m = re.search(
                rf"{dest_pat}\s*\n\s*(\$[\d\s\-]+)\s*\n\s*(\$[\d\s\-]+)\s*\n\s*(\$[\d\s\-]+)\s*\n\s*(\$[\d\s\-]+)\s*\n\s*([A-Z /]+(?:\n\s*(?:FIRM|SOFT|WEAK|STEADY|STABLE|MIXED|QUIET|POSITIVE|NEGATIVE|CAUTIOUS|UNCHANGED))?)",
                snap_text
            )
            if m:
                t, b, g, c, s = [x.strip() for x in m.groups()]
                s_clean = " ".join(s.split()).rstrip("/").strip()
                out_lines.append(f"| {dest} | {t} | {b} | {g} | {c} | {s_clean} |")
        out_lines.append("")
        notes = note_lines(page, "* ", ("5-Year Historical", "Reported Sales", "SHIPS SOLD"))
        if notes:
            first = notes[0].lstrip("* ")
            if " less. " in first:
                first, rest = first.split(" less. ", 1)
                out_lines.append(f"*{first} less.*\n")
                out_lines.append(rest + "\n")
                out_lines.extend(f"- {n}" for n in notes[1:])
            else:
                out_lines.append(f"*{first}*\n")
                out_lines.extend(n + "\n" for n in notes[1:])
            out_lines.append("")

        if hist_text:
            # Extract the 5 historical year column headers (e.g. 2021, 2022, 2023, 2024, 2025)
            yr_hdrs = re.findall(r"\b(20\d{2})\b", hist_text[:250])
            if len(yr_hdrs) >= 4:
                n_yrs = min(len(yr_hdrs), 5)
                yr_hdrs = yr_hdrs[:n_yrs]
                val_pat = r"\s*\n\s*".join([r"(\$?[\d \-,]+)"] * n_yrs)
                hist_rows: list[str] = []
                for dest, dest_pat in dest_defs:
                    mh = re.search(rf"{dest_pat}\s*\n\s*{val_pat}", hist_text)
                    if mh:
                        hvals = [x.strip() for x in mh.groups()]
                        hist_rows.append(f"| {dest} | " + " | ".join(hvals) + " |")
                if hist_rows:
                    out_lines.append("### 5-Year Historical Average Prices (USD / LDT)\n")
                    out_lines.append("| DESTINATION | " + " | ".join(yr_hdrs) + " |")
                    out_lines.append("| :--- | " + " | ".join([":---:"] * len(yr_hdrs)) + " |")
                    out_lines.extend(hist_rows)
                    out_lines.append("")

        geo_sales = [v for v in vessel_tables(page) if v[1] and v[1][0].startswith("VESSEL") and "ARRIVAL" not in v[1]]
        if geo_sales:
            out_lines.append("### Demolition - Reported Sales\n")
            hdr = (geo_sales[0][1] + [""] * 6)[:6]
            out_lines.append("| " + " | ".join(hdr) + " |")
            out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
            rows = geo_sales[0][2]
            for r in rows:
                r = (r + [""] * 6)[:6]
                out_lines.append("| " + " | ".join(c or "-" for c in r) + " |")
            if not rows:
                out_lines.append("| - | - | - | - | - | - |")
        elif "Reported Sales" in text or "SHIPS SOLD FOR RECYCLING" in text:
            out_lines.append("### Demolition - Reported Sales\n")
            out_lines.append("| VESSEL | TYPE | LDT | BUILT | PRICE ($/LDT) | DELIVERY / TERMS |")
            out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
            rs_pos = text.find("Reported Sales")
            if rs_pos == -1:
                rs_pos = text.find("SHIPS SOLD FOR RECYCLING")
            rs_sub = text[rs_pos:] if rs_pos != -1 else ""
            rs_lines = [l.strip() for l in rs_sub.splitlines() if l.strip()]
            idx_r = 0
            while idx_r < len(rs_lines) and not any(rs_lines[idx_r].startswith(h) for h in ["DELIVERY", "TERMS", "REMARKS", "COMMENTS"]):
                idx_r += 1
            idx_r += 1

            demo_rows: list[str] = []
            stop_demo = ("snp@starasiasg.com", "Member of BIMCO", "Page ", "5-Year Historical", "Price Trends", "*Above tables")
            demo_types = {
                "BULKER", "TANKER", "CONTAINER", "GENERAL CARGO", "GC", "GEN CARGO",
                "MPP", "ROPAX", "RORO", "LNG", "LPG", "REEFER", "FERRY", "OFFSHORE",
                "TUG", "BARGE", "DRILLSHIP", "FPSO", "FSO", "VLOC", "PCC", "PCTC", "CHEM"
            }
            while idx_r < len(rs_lines):
                line_cur = rs_lines[idx_r]
                if any(m in line_cur for m in stop_demo):
                    break
                if "NO REPORTED SALES" in line_cur.upper() or line_cur.upper() == "NIL":
                    break
                # Vessel name until we hit a known demo type or LDT
                v_parts = [line_cur]
                idx_r += 1
                while idx_r < len(rs_lines) and rs_lines[idx_r].upper() not in demo_types and not re.match(r"^[\d,]+$", rs_lines[idx_r]):
                    if any(m in rs_lines[idx_r] for m in stop_demo):
                        break
                    v_parts.append(rs_lines[idx_r])
                    idx_r += 1
                v_name = " ".join(v_parts).strip()
                v_type = ""
                if idx_r < len(rs_lines) and rs_lines[idx_r].upper() in demo_types:
                    v_type = rs_lines[idx_r].upper()
                    idx_r += 1
                v_ldt = ""
                if idx_r < len(rs_lines) and re.match(r"^[\d,]+$", rs_lines[idx_r]):
                    v_ldt = rs_lines[idx_r]
                    idx_r += 1
                v_built = ""
                if idx_r < len(rs_lines) and re.search(r"\b(19\d\d|20\d\d)\b", rs_lines[idx_r]):
                    v_built = rs_lines[idx_r]
                    idx_r += 1
                    if idx_r < len(rs_lines) and re.match(r"^/\s*[A-Z]+$", rs_lines[idx_r]):
                        v_built = f"{v_built} {rs_lines[idx_r]}"
                        idx_r += 1
                v_price = ""
                if idx_r < len(rs_lines) and (re.match(r"^\$?[\d,\.]+$", rs_lines[idx_r]) or rs_lines[idx_r].upper() in ["UNDISCLOSED", "PRIVATE", "-"]):
                    v_price = rs_lines[idx_r]
                    idx_r += 1
                deliv_parts: list[str] = []
                while idx_r < len(rs_lines):
                    if any(m in rs_lines[idx_r] for m in stop_demo):
                        break
                    # Check if rs_lines[idx_r] is the next vessel (followed by a demo_type in 1-2 lines)
                    if idx_r + 1 < len(rs_lines) and rs_lines[idx_r + 1].upper() in demo_types:
                        break
                    if idx_r + 2 < len(rs_lines) and rs_lines[idx_r + 2].upper() in demo_types:
                        break
                    deliv_parts.append(rs_lines[idx_r])
                    idx_r += 1
                v_deliv = " ".join(deliv_parts).strip()
                if v_name and (v_type or v_ldt):
                    demo_rows.append(f"| {v_name} | {v_type or '-'} | {v_ldt or '-'} | {v_built or '-'} | {v_price or '-'} | {v_deliv or '-'} |")

            if demo_rows:
                out_lines.extend(demo_rows)
            elif re.search(r"\bNIL\b", text[text.find("Reported Sales"):] if "Reported Sales" in text else text):
                out_lines.append("| NIL | NIL | NIL | NIL | NIL | NIL |")
            else:
                out_lines.append("| - | - | - | - | - | - |")

        return "\n".join(out_lines)

    # 5. PAGE: Segment Annual Averages (Dry Bulk, Tankers, Containers)
    elif "SEGMENT (AVG)" in text:
        return _segment_md(page, text)

    # 6. PAGE: Commodities & Exchange Rates (Iron Ore, Metals, Oil/Gas, Currencies)
    elif any(k in text for k in ["Copper (Comex)", "Industrial Metal Rates", "Commodity Prices", "Crude Oil & Natural Gas",
                                 "Iron Ore Lumps", "Iron Ore Fines"]) or re.search(r"(?m)^3Mo \w+ \(LME\)", text):
        out_sections = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        prose = prose_before(page, {"Iron Ore", "Industrial Metal Rates", "Crude Oil & Natural Gas", "Exchange Rates", "Commodity Prices"})
        if prose:
            out_sections.append(prose + "\n")

        # 6a. Iron Ore
        if any(k in text for k in ["Iron Ore Lumps", "Iron Ore Fines"]):
            rows = []
            j = 0
            while j < len(lines):
                l = lines[j]
                if any(l.startswith(k) for k in ["Iron Ore Lumps", "Iron Ore Fines"]):
                    comm_parts = [l]
                    j += 1
                    while j < len(lines) and not re.search(r"Fe\s*\d", lines[j]):
                        comm_parts.append(lines[j])
                        j += 1
                    comm_name = " ".join(comm_parts).replace(" ,", ",").strip()
                    grade_parts = []
                    while j < len(lines) and not (lines[j].startswith("$") or lines[j].startswith("US$")):
                        grade_parts.append(lines[j])
                        j += 1
                    grade_name = " ".join(grade_parts).strip()
                    this_wk = lines[j] if j < len(lines) else ""
                    j += 1
                    vals = []
                    while j < len(lines) and len(vals) < 4:
                        if lines[j].startswith("Copper (Comex)") or lines[j] == "INDEX" or any(lines[j].startswith(k) for k in ["Iron Ore Lumps", "Iron Ore Fines"]):
                            break
                        vals.append(lines[j])
                        j += 1
                    rows.append((comm_name, grade_name, this_wk, vals))
                else:
                    j += 1
            if rows:
                out_sections.append("### Iron Ore\n")
                out_sections.append("| COMMODITY (USD/MT) | GRADE | THIS WEEK | LAST WEEK | LAST YEAR | WoW | YoY |")
                out_sections.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
                for c_name, g_name, tw, rest in rows:
                    if len(rest) == 4:
                        if "%" in rest[0]: # 2022 format: WoW, YoY, LAST WEEK, LAST YEAR
                            wow, yoy, lw, ly = rest
                        else:
                            lw, ly, wow, yoy = rest
                        out_sections.append(f"| {c_name} | {g_name} | {tw} | {lw} | {ly} | {wow} | {yoy} |")
                    else:
                        out_sections.append(f"| {c_name} | {g_name} | {tw} | " + " | ".join(rest) + " |")
                out_sections.append("")

        # 6b. Industrial Metal Rates
        if re.search(r"(?m)^(Copper \(Comex\)|3Mo \w+ \(LME\))", text):
            metals_pat = re.compile(r"^(Copper \(Comex\)|3Mo Copper|3Mo Aluminium|3Mo Aluminum|3Mo Zinc|3Mo Tin)", re.IGNORECASE)
            rows = []
            j = 0
            while j < len(lines):
                l = lines[j]
                if metals_pat.match(l):
                    name = l
                    units = lines[j+1] if j+1 < len(lines) else ""
                    price = lines[j+2] if j+2 < len(lines) else ""
                    chg = lines[j+3] if j+3 < len(lines) else ""
                    pct = lines[j+4] if j+4 < len(lines) else ""
                    contract = lines[j+5] if j+5 < len(lines) else ""
                    rows.append((name, units, price, chg, pct, contract))
                    j += 6
                else:
                    j += 1
            if rows:
                out_sections.append("### Industrial Metal Rates\n" if "Industrial Metal Rates" in text
                                    else "### Industrial Metal Rates (continued)\n")
                out_sections.append("| INDEX | UNITS | PRICE | CHANGE | % CHANGE | CONTRACT |")
                out_sections.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
                for r in rows:
                    out_sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
                out_sections.append("")

        # 6c. Crude Oil & Natural Gas
        if any(k in text for k in ["WTI Crude Oil", "Brent Crude"]):
            energy_pat = re.compile(r"^(WTI Crude Oil|Brent Crude|Crude Oil \(Tokyo\)|Natural Gas)", re.IGNORECASE)
            rows = []
            j = 0
            while j < len(lines):
                l = lines[j]
                if energy_pat.match(l):
                    name = l
                    units = lines[j+1] if j+1 < len(lines) else ""
                    price = lines[j+2] if j+2 < len(lines) else ""
                    chg = lines[j+3] if j+3 < len(lines) else ""
                    pct = lines[j+4] if j+4 < len(lines) else ""
                    contract = lines[j+5] if j+5 < len(lines) else ""
                    rows.append((name, units, price, chg, pct, contract))
                    j += 6
                else:
                    j += 1
            if rows:
                out_sections.append("### Crude Oil & Natural Gas\n")
                out_sections.append("| INDEX | UNITS | PRICE | CHANGE | % CHANGE | CONTRACT |")
                out_sections.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
                for r in rows:
                    out_sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
                out_sections.append("")
                cob = next((l for l in lines if l.startswith("* All rates")), "")
                if cob:
                    out_sections.append(f"*{_typo(cob.lstrip('* '))}*\n")

        # 6d. Exchange Rates
        fx = _fx_md(text)
        if fx:
            out_sections.append(fx)

        if "Bunker Prices" in text:
            bunker = _bunker_md(text)
            if bunker:
                out_sections.append(bunker)
        if out_sections:
            return "\n".join(out_sections)

    # 7. PAGE: Bunker Prices & Disclaimer
    elif "Bunker Prices" in text:
        parts = [x for x in (_fx_md(text), _bunker_md(text)) if x]
        return "\n\n".join(parts)

    # 8. PAGE: Market Insights & Anchorage / Beaching Positions (pages 12-14): text layer + word geometry
    elif "Anchorage & Beaching Position" in text:
        return anchorage_page_md(page)

    # 9. PAGE: commodities commentary without tables (continues the scrap-market prose)
    elif "Commodities Focus" in text:
        return prose_before(page, ())

    return ""


def _fx_md(text: str) -> str:
    """Exchange Rates table (CURRENCY PAIR | <this week> | <last week> | WoW %) from the text layer."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    if "Exchange Rates" in text or "USD / CNY" in text or "CURRENCY PAIR" in text:
        cur_pat = re.compile(r"^USD\s*/\s*(CNY|BDT|INR|PKR|TRY)", re.IGNORECASE)
        rows = []
        j = 0
        col1, col2, col3 = "CURRENT", "LAST WEEK", "WoW %"
        while j < len(lines) and not cur_pat.match(lines[j]):
            if j + 2 < len(lines) and "%" in lines[j+2] and not lines[j].startswith("*") and not lines[j].startswith("Note"):
                col1, col2, col3 = lines[j], lines[j+1], lines[j+2]
            j += 1
        while j < len(lines):
            l = lines[j]
            if cur_pat.match(l):
                c_name = l
                c1 = lines[j+1] if j+1 < len(lines) else ""
                c2 = lines[j+2] if j+2 < len(lines) else ""
                c3 = lines[j+3] if j+3 < len(lines) else ""
                rows.append((c_name, c1, c2, c3))
                j += 4
            else:
                j += 1
        if rows:
            out.append("### Exchange Rates\n" if "Exchange Rates" in text else "### Exchange Rates (continued)\n")
            out.append(f"| CURRENCY PAIR | {col1} | {col2} | {col3} |")
            out.append("| :--- | :---: | :---: | :---: |")
            for r in rows:
                out.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
            out.append("")
    return "\n".join(out)


def _bunker_md(text: str) -> str:
    if True:
        ports = ["SINGAPORE", "HONG KONG", "FUJAIRAH", "ROTTERDAM", "HOUSTON", "GIBRALTAR", "PANAMA"]
        headers = ["PORT", "VLSFO (0.5%)", "HSFO (3.5%)", "MGO (0.1%)"]
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        try:
            b_idx = [i for i, l in enumerate(lines) if "Bunker Prices" in l][0]
            j = b_idx + 1
        except IndexError:
            j = 0
        rows = []
        while j < len(lines):
            line = lines[j]
            if line in ports:
                p_name = line
                vlsfo = lines[j+1] if j+1 < len(lines) else ""
                hsfo = lines[j+2] if j+2 < len(lines) else ""
                mgo = lines[j+3] if j+3 < len(lines) else ""
                rows.append((p_name, vlsfo, hsfo, mgo))
                j += 4
            elif "Singapore | London" in line or (j > b_idx + 5 and "snp@" in line):
                break
            else:
                j += 1
        out = []
        if rows:
            out.append("### Bunker Prices (USD / ton)\n")
            out.append("| " + " | ".join(headers) + " |")
            out.append("| :--- | :---: | :---: | :---: |")
            for r in rows:
                out.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
            out.append("")
        return "\n".join(out)

    return ""


def build_md(pdf: Path):
    import clean_all_brokers_formatting as cabf
    import run_star_asia_tables as sa
    res = None
    try:
        import liteparse
        lp = liteparse.LiteParse(ocr_enabled=False, quiet=True,
                                 output_format="markdown", keep_headers_footers=True)
        res = lp.parse(str(pdf))
    except Exception:
        res = None
    try:
        src_ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        src_ref = pdf.as_posix()

    try:
        with pymupdf.open(pdf) as d:
            report_week, issue_date = sa.extract_meta(d, pdf)
            num_pages = len(d)
    except Exception:
        report_week, issue_date, num_pages = 0, "2026-01-01", (res.num_pages if res else 1)
    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"

    lines = [
        "---",
        f'title: "Star Asia Shipbroking Weekly Demolition Report - Week {report_week}, {year_str}"',
        f'issue_date: "{issue_date}"',
        f'year: "{year_str}"',
        f'report_week: {report_week}',
        'broker: "Star Asia Shipbroking"',
        'category: "demolition_report"',
        f'source_file: "{src_ref}"',
        f'pages: {num_pages}',
        "---",
        "",
        f"# Star Asia Weekly Demolition Report - Week {report_week}, {year_str}",
        "",
        f"**Issue Date:** {issue_date} | **Report Week:** {report_week} | **Publisher:** Star Asia Shipbroking  ",
        f"**Source Document:** `{src_ref}`  ",
        "",
        "---",
        ""
    ]
    with pymupdf.open(pdf) as doc:
        for i in range(1, len(doc) + 1):
            lines.append(f"\n## Page {i}\n")
            if res is not None and i <= res.num_pages:
                lp_page_md = (res.get_page(i).markdown or "").strip()
            else:
                lp_page_md = doc[i - 1].get_text("text").strip()
            clean_tbl = build_star_asia_clean_page(doc[i - 1], lp_page_md)
            if clean_tbl:
                lines.append(clean_tbl)
            else:
                lines.append(re.sub(r"(\d) \.(\d)", r"\1.\2", lp_page_md))   # LiteParse '1 .27' -> '1.27'
    raw_md = "\n".join(lines)
    cleaned_md, _ = cabf.clean_star_asia(raw_md)

    return cleaned_md



# ---------------------------------------------------------------------------
# Series rows from the built MD (2026-10 audit). The old route (run_star_asia_tables.extract_*) labelled every
# anchorage row Chattogram, stripped spaces from vessel names and read the 5-year averages as current prices.
# The MD tables are built from print geometry, so the series are derived from them.
# ---------------------------------------------------------------------------
PORTS = {"ALANG": ("Alang, India", "India"), "CHATTOGRAM": ("Chattogram, Bangladesh", "Bangladesh"),
         "GADDANI": ("Gaddani, Pakistan", "Pakistan"), "GADANI": ("Gaddani, Pakistan", "Pakistan"),
         "ALIAGA": ("Aliaga, Turkey", "Turkey")}
DEALS_COLS = ["issue_date", "report_week", "deal_type", "vessel_name", "vessel_type", "ldt", "price_usd_per_ldt",
              "destination_yard", "year_built", "built_country", "arrival_date", "beaching_date", "terms_comments",
              "source_file", "arrival_date_raw", "arrival_date_status", "arrival_date_note", "beaching_date_raw",
              "beaching_date_status", "beaching_date_note", "built", "country_destination", "buyer_comments", "terms"]
DEMO_COLS = ["issue_date", "report_week", "destination", "country", "segment", "price_low", "price_high",
             "price_usd_per_ldt", "sentiment", "source_file"]
IRON_COLS = ["issue_date", "report_week", "commodity", "grade_origin", "price_usd_mt", "change_wow_pct",
             "change_yoy_pct", "last_week_usd_mt", "last_year_usd_mt", "source_file"]


SNP_COLS = ["issue_date", "report_week", "section", "vessel_name", "vessel_type", "dwt", "year_built", "built_country",
            "price_usd_mill", "buyers_comments", "source_file"]


def sidecar_rows(rows, cols):
    """Series rows in the sidecar's typed form: every column present, numbers as float/None, year_built int."""
    out = []
    for r in rows:
        d = {}
        for k in cols:
            v = r.get(k, "")
            if k == "report_week":
                v = int(v)
            elif k in ("ldt", "price_low", "price_high", "price_usd_per_ldt"):
                v = float(v) if v not in ("", None) else None
            elif k == "year_built":
                v = int(v) if str(v).isdigit() else (v or "")
            d[k] = v
        out.append(d)
    return out


SIDECAR_DEALS_COLS = DEALS_COLS[:20]


def _md_tables_all(t, head):
    """Every pipe table under a heading starting with `head` (S&P tables recur per sector and as continuations)."""
    out = []
    for m in re.finditer(rf"^#+ {re.escape(head)}[^\n]*", t, re.M):
        i = t.find("\n|", m.end())
        nxt = re.search(r"^#", t[m.end():], re.M)
        if i < 0 or (nxt and m.end() + nxt.start() < i):
            continue
        j = t.find("\n\n", i + 1)
        ls = [l for l in t[i + 1:j if j > 0 else None].split("\n") if l.startswith("|")]
        out.append(([c.strip() for c in ls[0].strip().strip("|").split("|")],
                    [[c.strip() for c in l.strip().strip("|").split("|")] for l in ls[2:]]))
    return out


VAL_COLS = ["issue_date", "report_week", "sector", "vessel_type", "size_dwt_teu", "nb_contract_usd_m", "nb_prompt_usd_m",
            "five_year_usd_m", "ten_year_usd_m", "older_year_usd_m", "source_file"]
METALS_COLS = ["issue_date", "report_week", "category", "index_name", "units", "price", "change", "pct_change", "contract",
               "source_file"]
HIST_COLS = ["issue_date", "report_week", "destination", "year_2021", "year_2022", "year_2023", "year_2024", "year_2025",
             "source_file"]
_TANKER_TYPES = {"VLCC", "SUEZMAX", "AFRAMAX", "LR1", "LR2", "MR", "HANDY TANKER"}


def _usd_m(s):
    """'$130M' / '$92M (E)' -> 130.0 / 92.0; '-' or blank -> ''."""
    m = re.match(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*M?\b", (s or "").strip())
    return float(m.group(1).replace(",", "")) if m else ""


def _val_rows(t, base, pdf_rel):
    out = []
    for hdr, rows in _md_tables_all(t, "Vessel Values"):
        h = [x.upper() for x in hdr]
        if "NB CONTRACT" not in h:
            continue
        teu = "SIZE (TEU)" in h
        ti, si = h.index("TYPE"), (h.index("SIZE (TEU)") if teu else h.index("DWT") if "DWT" in h else None)
        cols = [h.index(k) if k in h else None for k in ("NB CONTRACT", "NB PROMPT", "5 YRS", "10 YRS", "15 YRS")]
        for r in rows:
            r = (r + [""] * len(h))[:len(h)]
            vt = r[ti]
            sector = "Containers" if teu else ("Tankers" if vt.upper() in _TANKER_TYPES else "Dry Bulk")
            v = [_usd_m(r[c]) if c is not None else "" for c in cols]
            out.append(dict(base, sector=sector, vessel_type=vt, size_dwt_teu=r[si] if si is not None else "",
                            nb_contract_usd_m=v[0], nb_prompt_usd_m=v[1], five_year_usd_m=v[2], ten_year_usd_m=v[3],
                            older_year_usd_m=v[4], source_file=pdf_rel))
    return out


def _metals_rows(t, base, pdf_rel):
    out = []
    for head, cat in (("Industrial Metal Rates", "Industrial Metals"), ("Crude Oil & Natural Gas", "Energy")):
        for hdr, rows in _md_tables_all(t, head):
            h = [x.upper() for x in hdr]
            if "INDEX" not in h:
                continue
            for r in rows:
                r = (r + [""] * len(h))[:len(h)]
                g = lambda k: r[h.index(k)] if k in h else ""
                out.append(dict(base, category=cat, index_name=g("INDEX"), units=g("UNITS"), price=g("PRICE"),
                                change=g("CHANGE"), pct_change=g("% CHANGE"), contract=g("CONTRACT"), source_file=pdf_rel))
    return out


def _hist_rows(t, base, pdf_rel):
    out = []
    for hdr, rows in _md_tables_all(t, "5-Year Historical Average"):
        years = [x if re.fullmatch(r"20\d\d", x) else None for x in hdr]
        for r in rows:
            d = dict(base, destination=r[0], source_file=pdf_rel)
            for y, v in zip(years, r):
                if y and f"year_{y}" in HIST_COLS:
                    d[f"year_{y}"] = v
            out.append(d)
    return out


def _snp_rows(t, base, pdf_name):
    """Sale & Purchase rows. Price keeps its number; a printed qualifier (EACH, ENBLOC, (STST)) goes to
    buyers_comments in parentheses, as in the historical series."""
    out = []
    for hdr, rows in _md_tables_all(t, "Sale & Purchase"):
        h = [x.upper() for x in hdr]
        if "VESSEL" not in h or not ({"DWT", "TEU"} & set(h)):
            continue
        ix = {k: h.index(k) for k in h}
        size = ix.get("DWT", ix.get("TEU"))
        for r in rows:
            r = (r + [""] * len(h))[:len(h)]
            v = r[ix["VESSEL"]]
            if not v or v == "-":
                continue
            built = r[ix["YEAR / BUILT"]] if "YEAR / BUILT" in ix else ""
            y, c = (built.split(" / ") + [""])[:2]
            price = r[ix["PRICE (USD M)"]] if "PRICE (USD M)" in ix else ""
            m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", price)
            pnum, qual = (float(m.group(1)), m.group(2).strip()) if m else ("", "")
            if re.fullmatch(r"[\d.]+( / [\d.]+)+", price):   # one price per vessel: no single deal price
                pnum, qual = "", price
            buyer = r[ix["BUYER"]] if "BUYER" in ix else ""
            if qual:
                q = qual if qual.startswith("(") else f"({qual})"
                buyer = f"{buyer} {q}".strip()
            elif not m and price and price not in ("-", "N/A", "UNDISCLOSED"):
                buyer = f"{buyer} ({price})".strip()
            out.append(dict(base, section="Secondhand Sales", vessel_name=v, vessel_type=r[ix.get("TYPE", 1)],
                            dwt=_num(r[size].split(" / ")[0]), year_built=y.strip(), built_country=c.strip(),
                            price_usd_mill=pnum, buyers_comments=buyer, source_file=pdf_name))
    return out


def _md_table(t, head):
    m = re.search(rf"^#+ {re.escape(head)}", t, re.M)
    if not m:
        return None
    i = t.find("\n|", m.end())
    if i < 0:
        return None
    j = t.find("\n\n", i + 1)
    ls = [l for l in t[i + 1:j if j > 0 else None].split("\n") if l.startswith("|")]
    return [[c.strip() for c in l.strip().strip("|").split("|")] for l in ls[2:]]


def _num(s):
    s = s.replace(",", "").replace("$", "")
    return float(s) if re.fullmatch(r"\d+(\.\d+)?", s) else ""


def _iso(s):
    m = re.fullmatch(r"(\d\d)\.(\d\d)\.(\d{4})", s)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def series_rows(md_text: str, pdf_name: str, pdf_rel: str) -> dict:
    t = md_text.replace("\r\n", "\n")
    date = re.search(r'^issue_date:\s*"?([\d-]+)', t, re.M).group(1)
    week = re.search(r"^report_week:\s*(\d+)", t, re.M).group(1)
    base = dict(issue_date=date, report_week=int(week))
    deals, demo, iron = [], [], []
    for r in _md_table(t, "Demolition - Reported Sales") or []:
        if len(r) < 6 or r[0] in ("NIL", "-", ""):
            continue
        v, ty, ldt, built, price, com = r[:6]
        dest = next((PORTS[k][0] for k in PORTS if k in com.upper() and "DELIVERED" in com.upper()), "")
        y, c = (built.split(" / ") + [""])[:2]
        deals.append(dict(base, deal_type="Reported Sale", vessel_name=v, vessel_type=ty, ldt=_num(ldt),
                          price_usd_per_ldt=_num(price), destination_yard=dest, year_built=y, built_country=c,
                          terms_comments="" if com == "-" else com, source_file=pdf_name))
    for port in ("Alang", "Chattogram", "Gaddani"):
        for r in _md_table(t, f"{port} Anchorage & Beaching Position") or []:
            if len(r) < 5 or not _LDT.match(r[2]):
                continue
            v, ty, ldt, arr, bea = (c.strip() for c in r[:5])
            row = dict(base, deal_type="Beaching / Arrival", vessel_name=v, vessel_type=ty, ldt=_num(ldt),
                       destination_yard=PORTS[port.upper()][0], arrival_date=_iso(arr), beaching_date=_iso(bea),
                       arrival_date_raw=arr, beaching_date_raw=bea, source_file=pdf_name)
            for k, raw in (("arrival", arr), ("beaching", bea)):
                if not raw:
                    continue
                if _iso(raw):
                    row[f"{k}_date_note"] = "EU_DDMMYYYY"
                else:
                    row[f"{k}_date_status"] = raw; row[f"{k}_date_note"] = "STATUS"
            deals.append(row)
    segs = ["Tankers", "Bulkers", "General Cargo", "Containers"]
    for r in _md_table(t, "Ship Recycling - Current Market Snapshot") or []:
        key = next((k for k in PORTS if r[0].upper().startswith(k)), None)
        if not key or len(r) < 6:
            continue
        dname, country = PORTS[key]
        for s, cell in zip(segs, r[1:5]):
            nums = [float(x) for x in re.findall(r"\d+", cell.replace(",", ""))]
            if not nums:
                continue
            lo, hi = nums[0], nums[-1]
            demo.append(dict(base, destination=dname, country=country, segment=s, price_low=lo, price_high=hi,
                             price_usd_per_ldt=(lo + hi) / 2, sentiment=r[5], source_file=pdf_name))
    for r in _md_table(t, "Iron Ore") or []:
        if len(r) == 7:
            c, g, tw, lw, ly, w, y = r
            iron.append(dict(base, commodity=c, grade_origin=g, price_usd_mt=tw.lstrip("$"), change_wow_pct=w,
                             change_yoy_pct=y, last_week_usd_mt=lw.lstrip("$"), last_year_usd_mt=ly.lstrip("$"),
                             source_file=pdf_rel))
    return {"deals": deals, "demolition": demo, "iron_ore": iron, "snp": _snp_rows(t, base, pdf_name),
            "valuation": _val_rows(t, base, pdf_rel), "metals_energy": _metals_rows(t, base, pdf_rel),
            "history_5y": _hist_rows(t, base, pdf_rel)}

def chart_pages(pdf: Path):
    """Star Asia charts are RASTER, so record WHICH pages carry graphics rather
    than trying to calibrate them. The survey showed the charts restate the text
    tables, so no series are derived here."""
    out = {}
    try:
        with pymupdf.open(pdf) as d:
            for i, pg in enumerate(d, start=1):
                big = 0
                for im in pg.get_images(full=True):
                    try:
                        info = d.extract_image(im[0])
                        big = max(big, info["width"] * info["height"])
                    except Exception:
                        pass
                if big > 400_000:
                    out[str(i)] = {"image_px": big,
                                   "note": "raster graphic; values, if any, are "
                                           "within the image"}
    except Exception:
        pass
    return out


def process(pdf: Path):
    stem = pdf.stem
    year_dir = pdf.parent.name
    target_dir = (OUT / year_dir) if (year_dir.isdigit() and len(year_dir) == 4) else OUT
    target_dir.mkdir(parents=True, exist_ok=True)

    sidecar = target_dir / f"{stem}.tables.json"
    tables = []
    if sidecar.exists():
        try:
            loaded = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                tables = loaded
        except Exception:
            pass
    if not tables:
        tables, _md = tables_from_pdfinspector(pdf)
        if tables:
            tables = merge_missing_labels(tables, pdf)
            tables = drop_prose_rows(tables)
        sidecar.write_text(
            json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")

    md = build_md(pdf)
    charts = chart_pages(pdf)
    with pymupdf.open(pdf) as d:
        npages = d.page_count

    (target_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    chart_file = target_dir / f"{stem}.charts.json"
    if not chart_file.exists():
        chart_file.write_text(
            json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")

    # Remove any legacy flat duplicate in OUT root if target_dir is a year subdirectory
    if target_dir != OUT:
        for ext in (".md", ".tables.json", ".charts.json"):
            flat_f = OUT / f"{stem}{ext}"
            if flat_f.exists():
                flat_f.unlink()

    return {"pages": npages, "tables": len(tables),
            "graphic_pages": sorted(charts, key=int), "md_bytes": len(md)}



def main():
    import sys as _s
    pdfs = sorted(SRC.rglob("*.pdf"))
    st = load_state()
    force = "--all" in _s.argv or "--force" in _s.argv
    todo = pdfs if force else [p for p in pdfs if p.stem not in st["done"]]
    print(f"[{PUB}] total={len(pdfs)}  done={len(st['done'])}  todo={len(todo)} (force={force})", flush=True)
    t0 = time.time()
    for n, p in enumerate(todo, start=1):
        try:
            r = process(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            if n % 10 == 0 or n == len(todo):
                print(f"  [{n}/{len(todo)}] {p.stem[:56]:<56} pages={r['pages']:>2} "
                      f"tables={r['tables']:>2} graphics={r['graphic_pages']} "
                      f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:180]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:56]:<56} FAILED {type(e).__name__}",
                  flush=True)
            traceback.print_exc(limit=2)
        if n % 10 == 0:
            save_state(st)
    save_state(st)
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(pdfs)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s", flush=True)
    if st["failed"]:
        print("failures:", json.dumps(st["failed"], indent=2)[:1500])


if __name__ == "__main__":
    import sys as _s
    files = [a for a in _s.argv[1:] if not a.startswith("-")]
    if files:
        for a in files:
            print(json.dumps(process(Path(a)), indent=2, default=str))
    else:
        main()
