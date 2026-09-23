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
    import pdf_inspector as pi
    out = pi.process_pdf(str(pdf))
    md = out if isinstance(out, str) else getattr(out, "markdown", None) or str(out)
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


def build_md(pdf: Path):
    import liteparse
    lp = liteparse.LiteParse(ocr_enabled=False, quiet=True,
                             output_format="markdown", keep_headers_footers=True)
    res = lp.parse(str(pdf))
    try:
        src_ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        src_ref = pdf.as_posix()
    lines = [f"# {pdf.stem}", "",
             f"source: `{src_ref}`  |  pages: {res.num_pages}", ""]
    for i in range(1, res.num_pages + 1):
        lines.append(f"\n## Page {i}\n")
        lines.append((res.get_page(i).markdown or "").strip())
    return "\n".join(lines)


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
    tables, _md = tables_from_pdfinspector(pdf)
    tables = merge_missing_labels(tables, pdf)
    tables = drop_prose_rows(tables)
    md = build_md(pdf)
    charts = chart_pages(pdf)
    with pymupdf.open(pdf) as d:
        npages = d.page_count
    stem = pdf.stem
    (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
    (OUT / f"{stem}.tables.json").write_text(
        json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{stem}.charts.json").write_text(
        json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "tables": len(tables),
            "graphic_pages": sorted(charts, key=int), "md_bytes": len(md)}


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    st = load_state()
    todo = [p for p in pdfs if p.stem not in st["done"]]
    print(f"[{PUB}] total={len(pdfs)}  done={len(st['done'])}  todo={len(todo)}", flush=True)
    t0 = time.time()
    for n, p in enumerate(todo, start=1):
        try:
            r = process(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:56]:<56} pages={r['pages']:>2} "
                  f"tables={r['tables']:>2} graphics={r['graphic_pages']} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:180]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:56]:<56} FAILED {type(e).__name__}",
                  flush=True)
            traceback.print_exc(limit=2)
        if n % 5 == 0:
            save_state(st)
    save_state(st)
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(pdfs)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s", flush=True)
    if st["failed"]:
        print("failures:", json.dumps(st["failed"], indent=2)[:1500])


if __name__ == "__main__":
    import sys as _s
    if len(_s.argv) > 1:
        for a in _s.argv[1:]:
            print(json.dumps(process(Path(a)), indent=2, default=str))
    else:
        main()
