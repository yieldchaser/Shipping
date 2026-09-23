"""
Advanced Shipping - full-corpus runner (all tools, maximum accuracy).

Tool roles, each chosen because it measured best for that job:
  pdf-inspector  -> table cells (returned every table liteparse broke)
  liteparse      -> markdown for the KB + typed blocks + chart geometry
  pymupdf        -> per-line coordinates (liteparse gives no per-line bbox)

Publisher hazards encoded (all measured on this corpus, not assumed):
  * EUROPEAN NUMBERS: 60.000 = 60000 (period=thousands), 34,5 = 34.5
    (comma=decimal). Getting this wrong is a silent 1000x error.
  * charts on pp.1/2/5/8 are VECTOR -> exact values via axis calibration
  * p.7 bar values are printed as TEXT on a raster graphic -> no vision needed
  * page order shifted in 2026 (one page dropped) -> never hardcode pages

Resumable: every document is written as its own three files and recorded in
_run_state.json, so a crash or sleep costs only the document in flight.
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
import advanced_shipping as A  # noqa: E402

PUB = "advanced_shipping"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"


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


def extract_tables_filtered(pdf: Path):
    """pdf-inspector rules, with the degenerate/misgrouped tables dropped."""
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
    # drop tables with no numeric content (usually prose captured as a grid)
    keep = []
    for t in tables:
        flat = " ".join(c for r in t["rows"] for c in r)
        if len(re.findall(r"\d", flat)) >= 4:
            keep.append(t)
    return keep, md


BALTIC_LABELS = ["BDI", "BCI", "BPI", "BSI", "BHSI"]
TC_LABELS = ["Capesize", "Kamsarmax", "Ultramax", "Handysize"]


def _page_label_lines(pg):
    """Text lines on the page that are exactly a known label (with y order)."""
    import pymupdf  # noqa: F401
    out = []
    for blk in pg.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t in BALTIC_LABELS or t in TC_LABELS:
                y0, y1 = ln["bbox"][1], ln["bbox"][3]
                out.append(((y0 + y1) / 2, t))
    out.sort()
    return [t for _y, t in out]


def attach_known_labels(tables, pdf: Path):
    """Restore row labels ONLY where the label set is known and verifiable.

    MEASURED: the Baltic Indices panel loses its labels in ~176/249 docs
    (rows read ['3.370','','3.507','-3,91%'] - values right, identity gone).
    The labels exist on the page as positioned text, so attach them by ORDER,
    but only when the page yields EXACTLY the expected vocabulary in the
    expected order. That check is what makes this safe: if the labels are not
    the known set, nothing is attached and the rows are left as extracted.

    Deliberately NOT done: matching arbitrary text lines by position, which
    would attach whatever happens to sit near a row.
    """
    import pymupdf
    NUM = re.compile(r"^[\d.,%$+\-\s]+$")
    try:
        doc = pymupdf.open(pdf)
    except Exception:
        return tables

    def find_label_seq(want):
        for pg in doc:
            seq = [t for t in _page_label_lines(pg) if t in want]
            if seq == want:
                return seq
        return None

    baltic = find_label_seq(BALTIC_LABELS)
    tc = find_label_seq(TC_LABELS)
    try:
        for t in tables:
            rows = t["rows"]
            if len(rows) < 4:
                continue
            # Guard, corrected: the first pass counted non-numeric first cells,
            # but the Baltic panel LEADS with a legend row ('B.C.I') and a date
            # row ('12-Dec'), so that test skipped the exact table it was meant
            # to fix. Test for the real signature instead:
            #   (a) a block of numeric rows carrying a % column, and
            #   (b) no known label already present
            if any(r and r[0] in (BALTIC_LABELS + TC_LABELS) for r in rows):
                continue                      # already labelled
            numeric = [r for r in rows
                       if r and r[0] and NUM.match(r[0])
                       and any("%" in c for c in r)]
            if len(numeric) < 4:
                continue
            # Attach the first N labels to the first N numeric rows. Requiring
            # exact equality silently did nothing: this panel carries 7 numeric
            # rows (5 Baltic indices + the Daily T/C block) against 5 labels.
            # Only the leading block is labelled, and only when the page yields
            # the expected vocabulary - otherwise nothing is attached.
            for want in (baltic, tc):
                if want and len(numeric) >= len(want):
                    for r, lbl in zip(numeric[:len(want)], want):
                        r.insert(0, lbl)
                    break
    finally:
        doc.close()
    return tables


def clean_charts(charts: dict) -> dict:
    """Drop degenerate 'series' that do not vary - misgrouped gridlines."""
    out = {}
    for pno, lst in charts.items():
        good = []
        for ch in lst:
            ser = {}
            for col, pts in ch.get("series", {}).items():
                if len(pts) < 8:
                    continue
                ys = [y for _x, y in pts]
                if max(ys) - min(ys) < 0.5:      # flat line -> gridline, not data
                    continue
                ser[col] = pts
            if ser:
                ch = dict(ch)
                ch["series"] = ser
                good.append(ch)
        if good:
            out[pno] = good
    return out


def process(pdf: Path):
    import liteparse
    tables, md = extract_tables_filtered(pdf)
    tables = attach_known_labels(tables, pdf)
    # MEASURED: extract_blocks=True costs ~4s/PAGE (40s for a 10-page file),
    # against liteparse's own ~2-5ms/page claim - a 1000x gap. Block analysis
    # was only needed to compare table structure, and pdf-inspector won that
    # comparison and runs above in 2.9s. Markdown alone is ~0.3s, so the blocks
    # pass is pure duplicated cost on the hot path.
    # ocr_enabled defaults to ON in liteparse. Leaving it unset cost ~25s per
    # document here (the OCR attempt runs over every page). Measured on this
    # corpus: 0 of 312 pages across 7 sources genuinely needed OCR, so it is
    # off on the hot path and can be re-enabled per page from the router.
    lp = liteparse.LiteParse(ocr_enabled=False, quiet=True,
                             output_format="markdown", keep_headers_footers=True)
    res = lp.parse(str(pdf))
    pages_md = []
    for i in range(1, res.num_pages + 1):
        pages_md.append(f"\n## Page {i}\n")
        pages_md.append((res.get_page(i).markdown or "").strip())
    try:
        src_ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        src_ref = pdf.as_posix()
    doc_md = "\n".join([f"# {pdf.stem}", "",
                        f"source: `{src_ref}`  |  pages: {res.num_pages}", ""] + pages_md)
    charts = {}
    for pno in range(1, res.num_pages + 1):
        try:
            c = A.extract_chart_series(pdf, pno)
        except Exception:
            continue
        good = [x for x in c.get("charts", []) if x.get("series")]
        if good:
            charts[str(pno)] = good
    charts = clean_charts(charts)
    stem = pdf.stem
    (OUT / f"{stem}.md").write_text(doc_md, encoding="utf-8")
    (OUT / f"{stem}.tables.json").write_text(
        json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{stem}.charts.json").write_text(
        json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": res.num_pages, "tables": len(tables),
            "chart_pages": sorted(charts, key=int), "md_bytes": len(doc_md)}


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
            el = time.time() - t0
            print(f"  [{n}/{len(todo)}] {p.stem[:58]:<58} "
                  f"pages={r['pages']:>2} tables={r['tables']:>2} "
                  f"charts={r['chart_pages']} ({el:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:180]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:58]:<58} FAILED {type(e).__name__}",
                  flush=True)
            traceback.print_exc(limit=2)
        if n % 5 == 0:
            save_state(st)
    save_state(st)
    ok = len(st["done"])
    print(f"\n[{PUB}] COMPLETE  ok={ok}/{len(pdfs)}  failed={len(st['failed'])}  "
          f"elapsed={time.time()-t0:.0f}s", flush=True)
    if st["failed"]:
        print("failures:", json.dumps(st["failed"], indent=2)[:2000])


if __name__ == "__main__":
    main()
