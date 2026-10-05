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

    stop_markers = ("snp@starasiasg.com", "Member of BIMCO", "Page ", "Vessel Values", "Baltic ")
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


def build_star_asia_clean_page(page: pymupdf.Page, lp_md: str = "") -> str:
    """Reconstructs clean markdown for tabular pages with proper headers and complete columns."""
    text = page.get_text("text").replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")

    # 1 & 2. PAGES: Dry Bulk & Tankers (Indices, Vessel Values, and/or Sale & Purchase, even when split across pages)
    has_dry_idx = "Baltic Dry Indices" in text
    has_tkr_idx = "Baltic Tanker Indices" in text
    has_vv = ("Vessel Values" in text) and ("CONTAINERS" not in text)
    has_sp = ("Sale & Purchase" in text) and ("CONTAINERS" not in text) and ("SHIP RECYCLING" not in text)

    if has_dry_idx or has_tkr_idx or has_vv or has_sp:
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
                sp_rows = _parse_sp_fixtures_block(text[sp_start:], all_sp_types)
                if sp_rows:
                    out_lines.append("### Sale & Purchase - Reported Fixtures\n")
                    out_lines.append("| VESSEL | TYPE | DWT | YEAR / BUILT | PRICE (USD M) | BUYER |")
                    out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
                    out_lines.extend(sp_rows)

        if out_lines:
            return "\n".join(out_lines)

    # 3. PAGE: Containers
    elif "CONTAINERS" in text and "Vessel Values" in text:
        out_lines = ["# CONTAINERS\n"]
        m_comm = re.search(r"CONTAINERS\s*\n\s*(.*?)\s*\n\s*Vessel Values", text, re.DOTALL)
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
        out_lines.append("| DESTINATION | TANKERS | BULKERS | GENERAL CARGO | CONTAINERS | OUTLOOK / SENTIMENTS |")
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

        if "Reported Sales" in text or "SHIPS SOLD FOR RECYCLING" in text:
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
            else:
                out_lines.append("| NIL | NIL | NIL | NIL | NIL | No reported sales this week |")

        return "\n".join(out_lines)

    # 5. PAGE: Segment Annual Averages (Dry Bulk, Tankers, Containers)
    elif "SEGMENT (AVG)" in text:
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

        out = [title + "\n"]
        out.append("| " + " | ".join(headers) + " |")
        out.append("| :--- | " + " | ".join([":---:"] * (len(headers) - 1)) + " |")
        for seg, vals in rows:
            val_str = " | ".join(vals)
            out.append(f"| {seg} | {val_str} |")
        return "\n".join(out)

    # 6. PAGE: Commodities & Exchange Rates (Iron Ore, Metals, Oil/Gas, Currencies)
    elif any(k in text for k in ["Copper (Comex)", "Industrial Metal Rates", "Commodity Prices", "Crude Oil & Natural Gas"]):
        out_sections = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

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
        if "Copper (Comex)" in text:
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
                out_sections.append("### Industrial Metal Rates\n")
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

        # 6d. Exchange Rates
        if "Exchange Rates" in text or "USD / CNY" in text:
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
                out_sections.append("### Exchange Rates\n")
                out_sections.append(f"| CURRENCY PAIR | {col1} | {col2} | {col3} |")
                out_sections.append("| :--- | :---: | :---: | :---: |")
                for r in rows:
                    out_sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
                out_sections.append("")

        if out_sections:
            return "\n".join(out_sections)

    # 7. PAGE: Bunker Prices & Disclaimer
    elif "Bunker Prices" in text:
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

    # 8. PAGE: Market Insights & Anchorage / Beaching Positions (Pages 12 & 13)
    elif "Anchorage & Beaching Position" in text and lp_md:
        augmented_md = lp_md
        demo_types_set = {
            "BULKER", "TANKER", "CONTAINER", "GENERAL CARGO", "GC", "GEN CARGO",
            "MPP", "ROPAX", "RORO", "LNG", "LPG", "REEFER", "FERRY", "OFFSHORE",
            "TUG", "BARGE", "DRILLSHIP", "FPSO", "FSO", "VLOC", "PCC", "PCTC", "CHEM"
        }
        for port_lbl, next_anchor in [
            ("Alang", "**Chattogram"),
            ("Chattogram", "**Gaddani"),
            ("Gaddani", "**Aliaga"),
        ]:
            m_ab = re.search(rf"({port_lbl}\s+Anchorage\s*&\s*Beaching\s+Position[^\n]*)\n(.*?)(?=(?:Chattogram,\s*Bangladesh:|Gaddani,\s*Pakistan:|Aliaga,\s*Turkey:|SUB-CONTINENT|TIDE DATES|\Z))", text, re.DOTALL)
            if m_ab and f"{port_lbl} Anchorage" not in augmented_md:
                hdr_title = m_ab.group(1).strip()
                ab_body = m_ab.group(2).strip()
                ab_lines = [l.strip() for l in ab_body.splitlines() if l.strip()]
                # Advance past BEACHING header
                k = 0
                while k < len(ab_lines) and ab_lines[k].upper() != "BEACHING":
                    k += 1
                k += 1
                rem = ab_lines[k:]
                tbl_md_lines = [
                    f"\n### {hdr_title}\n",
                    "| VESSEL | TYPE | LDT | ARRIVAL | BEACHING |",
                    "| :--- | :---: | :---: | :---: | :---: |",
                ]
                if not rem or all(x == "-" for x in rem):
                    tbl_md_lines.append("| NIL | NIL | NIL | NIL | No vessels reported |")
                else:
                    r_idx = 0
                    while r_idx < len(rem):
                        v_p = [rem[r_idx]]
                        r_idx += 1
                        while r_idx < len(rem) and rem[r_idx].upper() not in demo_types_set:
                            v_p.append(rem[r_idx])
                            r_idx += 1
                        v_n = " ".join(v_p).strip()
                        v_t = rem[r_idx].upper() if r_idx < len(rem) else "-"
                        r_idx += 1
                        v_l = rem[r_idx] if (r_idx < len(rem) and re.match(r"^[\d,]+$", rem[r_idx])) else "-"
                        if v_l != "-":
                            r_idx += 1
                        v_arr = rem[r_idx] if (r_idx < len(rem) and re.match(r"^\d{2}\.\d{2}\.\d{4}$", rem[r_idx])) else "-"
                        if v_arr != "-":
                            r_idx += 1
                        v_bch = "AWAITING"
                        if r_idx < len(rem) and (re.match(r"^\d{2}\.\d{2}\.\d{4}$", rem[r_idx]) or rem[r_idx].upper() in ["AWAITING", "BEACHED", "DELIVERED", "-"]):
                            v_bch = rem[r_idx]
                            r_idx += 1
                        if v_n:
                            tbl_md_lines.append(f"| {v_n} | {v_t} | {v_l} | {v_arr} | {v_bch} |")
                tbl_block = "\n".join(tbl_md_lines) + "\n\n"
                ins_pos = augmented_md.find(next_anchor)
                if ins_pos != -1:
                    augmented_md = augmented_md[:ins_pos] + tbl_block + augmented_md[ins_pos:]
                else:
                    augmented_md = augmented_md + "\n" + tbl_block
        return augmented_md

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
                lines.append(lp_page_md)
    raw_md = "\n".join(lines)
    cleaned_md, _ = cabf.clean_star_asia(raw_md)

    # Append vector chart links if chart PNGs exist in data/extracted/charts/star_asia/<year>/
    charts_dir = ROOT / "data" / "extracted" / "charts" / "star_asia" / year_str
    if charts_dir.exists():
        chart_pngs = sorted(charts_dir.glob(f"{pdf.stem}_scrap_trends_*.png"))
        if chart_pngs and "## Market Charts & Quantitative Vectors" not in cleaned_md:
            chart_lines = ["", "## Market Charts & Quantitative Vectors", ""]
            for cp in chart_pngs:
                m_pg = re.search(r"_p(\d+)\.png$", cp.name)
                pg_lbl = f" (Page {int(m_pg.group(1))})" if m_pg else ""
                rel_cp = f"../../../charts/star_asia/{year_str}/{cp.name}"
                chart_lines.extend([
                    f"### Star Asia Demolition Price Trends{pg_lbl}",
                    "",
                    f"![Star Asia Demolition Price Trends]({rel_cp})",
                    "",
                    "*Extracted to time series: `star_asia_scrap_price_trends_series.csv`*",
                    ""
                ])
            cleaned_md = cleaned_md.rstrip() + "\n" + "\n".join(chart_lines)

    return cleaned_md


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
