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


def build_star_asia_clean_page(page: pymupdf.Page) -> str:
    """Reconstructs clean markdown for tabular pages with proper headers and complete columns."""
    text = page.get_text("text").replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")

    # 1. PAGE: Dry Bulk
    if "Baltic Dry Indices" in text:
        out_lines = ["### Baltic Dry Index (BDI)\n"]
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

        # Vessel Values
        out_lines.append("### Vessel Values (USD Million)\n")
        out_lines.append("| TYPE | DWT | NB CONTRACT | NB PROMPT | 5 YRS | 10 YRS | 15 YRS |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for v_type in ["CAPESIZE", "KAMSARMAX", "ULTRAMAX", "HANDY"]:
            m_vv = re.search(rf"{v_type}\s*\n\s*([\d,]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)", text)
            if m_vv:
                dwt, nb_c, nb_p, y5, y10, y15 = [x.strip() for x in m_vv.groups()]
                out_lines.append(f"| {v_type} | {dwt} | {nb_c} | {nb_p} | {y5} | {y10} | {y15} |")
        out_lines.append("")

        # S&P Fixtures
        out_lines.append("### Sale & Purchase - Reported Fixtures\n")
        out_lines.append("| VESSEL | TYPE | DWT | YEAR / BUILT | PRICE (USD M) | BUYER |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
        sp_start = text.find("Sale & Purchase")
        if sp_start != -1:
            sp_lines = [l.strip() for l in text[sp_start:].splitlines() if l.strip()]
            i = 0
            while i < len(sp_lines) and not sp_lines[i].startswith("BUYER"):
                i += 1
            i += 1
            while i < len(sp_lines):
                if "snp@starasiasg.com" in sp_lines[i] or "Member of BIMCO" in sp_lines[i] or "Page" in sp_lines[i]:
                    break
                v_parts = [sp_lines[i]]
                i += 1
                while i < len(sp_lines) and sp_lines[i] not in ["CAPE", "POST", "PMAX", "KMAX", "UMAX", "SMAX", "HANDY", "POST PMAX"]:
                    if sp_lines[i].isdigit() or "CHINA" in sp_lines[i] or "JAPAN" in sp_lines[i] or "snp@" in sp_lines[i]:
                        break
                    v_parts.append(sp_lines[i])
                    i += 1
                v_name = " ".join(v_parts).strip()
                v_name = re.sub(r"^BUYER\s+", "", v_name)
                v_type = ""
                if i < len(sp_lines) and sp_lines[i] in ["CAPE", "POST", "PMAX", "KMAX", "UMAX", "SMAX", "HANDY"]:
                    v_type = sp_lines[i]; i += 1
                    if v_type == "POST" and i < len(sp_lines) and sp_lines[i] == "PMAX":
                        v_type = "POST PMAX"; i += 1
                v_dwt = ""
                if i < len(sp_lines) and re.match(r"^[\d,]+$", sp_lines[i]):
                    v_dwt = sp_lines[i]; i += 1
                    if i < len(sp_lines) and re.match(r"^[\d,]+$", sp_lines[i]):
                        v_dwt = f"{v_dwt} / {sp_lines[i]}"; i += 1
                v_built = ""
                if i < len(sp_lines) and re.search(r"\b(19\d\d|20\d\d)\b", sp_lines[i]):
                    v_built = sp_lines[i]; i += 1
                v_price = ""
                if i < len(sp_lines) and (re.search(r"\d", sp_lines[i]) or sp_lines[i] == "-"):
                    v_price = sp_lines[i]; i += 1
                v_buyer = ""
                if i < len(sp_lines) and any(w in sp_lines[i].upper() for w in ["BUYER", "UNDISCLOSED", "GREEK", "CHINESE", "EUROPEAN", "TURKISH", "MIDDLE EAST", "FAR EAST"]):
                    b_parts = [sp_lines[i]]; i += 1
                    if i < len(sp_lines) and sp_lines[i] == "BUYER":
                        b_parts.append(sp_lines[i]); i += 1
                    v_buyer = " ".join(b_parts)
                if v_name and v_type:
                    out_lines.append(f"| {v_name} | {v_type} | {v_dwt} | {v_built} | {v_price} | {v_buyer} |")

        return "\n".join(out_lines)

    # 2. PAGE: Tankers
    elif "Baltic Tanker Indices" in text:
        out_lines = ["### Baltic Tanker Indices\n"]
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

        # Vessel Values
        out_lines.append("### Vessel Values (USD Million)\n")
        out_lines.append("| TYPE | DWT | NB CONTRACT | NB PROMPT | 5 YRS | 10 YRS | 15 YRS |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for v_type in ["VLCC", "SUEZMAX", "AFRAMAX", "LR1", "MR"]:
            m_vv = re.search(rf"{v_type}\s*\n\s*([\d,]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)\s*\n\s*(\$?[^\n]+)", text)
            if m_vv:
                dwt, nb_c, nb_p, y5, y10, y15 = [x.strip() for x in m_vv.groups()]
                out_lines.append(f"| {v_type} | {dwt} | {nb_c} | {nb_p} | {y5} | {y10} | {y15} |")
        out_lines.append("")

        # S&P Fixtures
        out_lines.append("### Sale & Purchase - Reported Fixtures\n")
        out_lines.append("| VESSEL | TYPE | DWT | YEAR / BUILT | PRICE (USD M) | BUYER |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
        sp_start = text.find("Sale & Purchase")
        if sp_start != -1:
            sp_lines = [l.strip() for l in text[sp_start:].splitlines() if l.strip()]
            i = 0
            while i < len(sp_lines) and not (sp_lines[i].startswith("BUYER") or sp_lines[i].startswith("PRICE")):
                i += 1
            i += 1
            while i < len(sp_lines):
                if "snp@starasiasg.com" in sp_lines[i] or "Member of BIMCO" in sp_lines[i] or "Page" in sp_lines[i]:
                    break
                v_parts = [sp_lines[i]]
                i += 1
                while i < len(sp_lines) and sp_lines[i] not in ["VLCC", "SUEZ", "AFRA", "LR2", "LR1", "MR", "SMALL"]:
                    if sp_lines[i].isdigit() or "CHINA" in sp_lines[i] or "JAPAN" in sp_lines[i] or "snp@" in sp_lines[i]:
                        break
                    v_parts.append(sp_lines[i])
                    i += 1
                v_name = " ".join(v_parts).strip()
                v_name = re.sub(r"^BUYER\s+", "", v_name)
                v_type = ""
                if i < len(sp_lines) and sp_lines[i] in ["VLCC", "SUEZ", "AFRA", "LR2", "LR1", "MR", "SMALL"]:
                    v_type = sp_lines[i]; i += 1
                v_dwt = ""
                if i < len(sp_lines) and re.match(r"^[\d,]+$", sp_lines[i]):
                    v_dwt = sp_lines[i]; i += 1
                v_built = ""
                if i < len(sp_lines) and re.search(r"\b(19\d\d|20\d\d)\b", sp_lines[i]):
                    v_built = sp_lines[i]; i += 1
                v_price = ""
                if i < len(sp_lines) and (re.search(r"\d", sp_lines[i]) or sp_lines[i] == "-"):
                    v_price = sp_lines[i]; i += 1
                v_buyer = ""
                if i < len(sp_lines) and any(w in sp_lines[i].upper() for w in ["BUYER", "UNDISCLOSED", "GREEK", "CHINESE", "EUROPEAN", "TURKISH", "MIDDLE EAST", "FAR EAST"]):
                    b_parts = [sp_lines[i]]; i += 1
                    if i < len(sp_lines) and sp_lines[i] == "BUYER":
                        b_parts.append(sp_lines[i]); i += 1
                    v_buyer = " ".join(b_parts)
                if v_name and v_type:
                    out_lines.append(f"| {v_name} | {v_type} | {v_dwt} | {v_built} | {v_price} | {v_buyer} |")

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

        out_lines.append("### Sale & Purchase - Reported Fixtures\n")
        out_lines.append("| VESSEL | TYPE | TEU | YEAR / BUILT | PRICE (USD M) | BUYER |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
        sp_start = text.find("Sale & Purchase")
        if sp_start != -1:
            sp_lines = [l.strip() for l in text[sp_start:].splitlines() if l.strip()]
            i = 0
            while i < len(sp_lines) and not sp_lines[i].startswith("BUYER"):
                i += 1
            i += 1
            while i < len(sp_lines):
                if "snp@starasiasg.com" in sp_lines[i] or "Member of BIMCO" in sp_lines[i] or "Page" in sp_lines[i]:
                    break
                v_name = sp_lines[i]; i += 1
                v_type = sp_lines[i] if i < len(sp_lines) else ""; i += 1
                v_teu = sp_lines[i] if i < len(sp_lines) else ""; i += 1
                v_built = sp_lines[i] if i < len(sp_lines) else ""; i += 1
                v_price = sp_lines[i] if i < len(sp_lines) else ""; i += 1
                v_buyer = sp_lines[i] if i < len(sp_lines) else ""; i += 1
                if v_name and v_type:
                    out_lines.append(f"| {v_name} | {v_type} | {v_teu} | {v_built} | {v_price} | {v_buyer} |")

        return "\n".join(out_lines)

    # 4. PAGE: Ship Recycling
    elif "SHIP RECYCLING" in text and "Current Market Snapshot" in text:
        out_lines = ["### Ship Recycling - Current Market Snapshot (USD / LDT)\n"]
        out_lines.append("| DESTINATION | TANKERS | BULKERS | GENERAL CARGO | CONTAINERS | OUTLOOK / SENTIMENTS |")
        out_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for dest in ["ALANG, INDIA", "CHATTOGRAM, BANGLADESH", "GADDANI, PAKISTAN", "ALIAGA, TURKEY"]:
            dest_pat = dest.split(",")[0]
            m = re.search(rf"{dest_pat}[^\n]*\n\s*(\$[\d\s-]+)\s*\n\s*(\$[\d\s-]+)\s*\n\s*(\$[\d\s-]+)\s*\n\s*(\$[\d\s-]+)\s*\n\s*([A-Z\s/]+)", text)
            if m:
                t, b, g, c, s = [x.strip() for x in m.groups()]
                out_lines.append(f"| {dest} | {t} | {b} | {g} | {c} | {s} |")
        out_lines.append("")

        if "Reported Sales" in text or "SHIPS SOLD FOR RECYCLING" in text:
            out_lines.append("### Demolition - Reported Sales\n")
            out_lines.append("| VESSEL | TYPE | LDT | BUILT | PRICE ($/LDT) | DELIVERY / TERMS |")
            out_lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |")
            out_lines.append("| - | - | - | - | - | No reported sales this week |")

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
        m_disc = re.search(r"(This report is performed to the best of our knowledge.*)", text, re.DOTALL)
        if m_disc:
            disc_clean = re.sub(r"\s+", " ", m_disc.group(1)).strip()
            disc_clean = re.sub(r"snp@starasiasg\.com.*", "", disc_clean).strip()
            out.append("### Disclaimer\n")
            out.append(f"*{disc_clean}*\n")
        return "\n".join(out)

    return ""


def build_md(pdf: Path):
    import liteparse
    import clean_all_brokers_formatting as cabf
    import run_star_asia_tables as sa
    lp = liteparse.LiteParse(ocr_enabled=False, quiet=True,
                             output_format="markdown", keep_headers_footers=True)
    res = lp.parse(str(pdf))
    try:
        src_ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        src_ref = pdf.as_posix()

    try:
        with pymupdf.open(pdf) as d:
            report_week, issue_date = sa.extract_meta(d, pdf)
    except Exception:
        report_week, issue_date = 0, "2026-01-01"
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
        f'pages: {res.num_pages}',
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
        for i in range(1, res.num_pages + 1):
            lines.append(f"\n## Page {i}\n")
            clean_tbl = build_star_asia_clean_page(doc[i - 1])
            if clean_tbl:
                lines.append(clean_tbl)
            else:
                lines.append((res.get_page(i).markdown or "").strip())
    raw_md = "\n".join(lines)
    cleaned_md, _ = cabf.clean_star_asia(raw_md)
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
    sidecar = OUT / f"{stem}.tables.json"
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
    
    # Save to root md directory
    (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
    chart_file = OUT / f"{stem}.charts.json"
    if not chart_file.exists():
        chart_file.write_text(
            json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
            
    # Also synchronize to year subdirectory if present
    year_dir = pdf.parent.name
    if year_dir.isdigit() and len(year_dir) == 4:
        yd = OUT / year_dir
        yd.mkdir(parents=True, exist_ok=True)
        (yd / f"{stem}.md").write_text(md, encoding="utf-8")
        yd_sidecar = yd / f"{stem}.tables.json"
        if not yd_sidecar.exists():
            yd_sidecar.write_text(
                json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")
        yd_chart = yd / f"{stem}.charts.json"
        if not yd_chart.exists():
            yd_chart.write_text(
                json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")

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
