"""Stage 1+2: route pages, extract text blocks + tables + harvest chart images.

Per input PDF writes:
  <out>/<source>/<stem>/text.jsonl    per-page ordered blocks w/ bbox+style
  <out>/<source>/<stem>/tables.jsonl  union tables (camelot-stream + pdfplumber)
  <out>/<source>/<stem>/charts/       embedded images + meta.jsonl (dhash series)
  <out>/<source>/<stem>/pages.jsonl   route label per page

Routes: text | garbled | scanned | image-heavy (image-heavy also gets text try).
Quarantine (no text trust): garbled, scanned -> flagged, text kept but marked.

Usage:
  python scripts/extract/extract_all.py <pdf> --out data/extracted/v0 [--no-tables]
  python scripts/extract/extract_all.py --inventory data/extracted/inventory.jsonl --limit 30
"""
import argparse
import hashlib
import io
import json
import multiprocessing as mp
import re
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def img_dhash(pil_img, size=8):
    try:
        g = pil_img.convert("L").resize((size + 1, size))
        px = list(g.get_flattened_data() if hasattr(g, "get_flattened_data") else g.getdata())
        bits = 0
        for r in range(size):
            for c in range(size):
                bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
        return format(bits, "016x")
    except Exception:
        return None


def route_page(page, char_count, n_images):
    if char_count < 50 and n_images >= 1:
        return "scanned"
    if char_count < 50:
        return "empty"
    txt = (page.get_text() or "")[:2000]
    alpha = sum(c.isalpha() for c in txt)
    ratio = alpha / max(1, len(txt))
    if ratio < 0.25:
        return "garbled"
    if n_images > 2:
        return "image-heavy"
    return "text"


def extract_text_blocks(page):
    blocks = []
    try:
        data = page.get_text("dict").get("blocks", [])
    except Exception:
        return blocks
    for b in data:
        if b.get("type", 0) != 0:
            continue
        lines = []
        sizes = []
        for line in b.get("lines", []):
            parts = []
            for span in line.get("spans", []):
                parts.append(span.get("text", ""))
                sizes.append(span.get("size", 0))
            lines.append("".join(parts))
        text = "\n".join(lines).strip()
        if text:
            blocks.append({"bbox": [round(v, 1) for v in b.get("bbox", [])],
                           "text": text,
                           "max_font": round(max(sizes) if sizes else 0, 1)})
    return blocks


def needs_layout(pdf_path, pno, camelot_tables):
    """Gate: run the expensive layout model only where it changes the outcome.

    Measured 2026-09-21: layout = 2.28s/page vs all other stages combined
    0.15s/page (91% of runtime). Firing on "many tables" was wrong: on
    banchero_costa (chart-heavy, genuinely many small tables) it cost 54s for
    16 extra fragments. Fire only where a table is MISSED or STUBBY.
    """
    if not camelot_tables:
        return True  # possibly borderless/missed
    for t in camelot_tables:
        rows = t.get("rows") or []
        if len(rows) <= 3:
            return True  # stub fragment: layout gives real bounds
    return False


def extract_tables_union(pdf_path, pno, skip_tables=False):
    tables = []
    if skip_tables:
        return tables
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import camelot
            tabs = camelot.read_pdf(pdf_path, pages=str(pno + 1), flavor="stream")
        for i in range(tabs.n):
            df = tabs[i].df
            tables.append({"engine": "camelot-stream",
                           "acc": round(tabs[i].parsing_report.get("accuracy", 0), 1),
                           "rows": df.values.tolist()})
    except Exception as exc:
        tables.append({"engine": "camelot-stream", "error": str(exc)[:120]})
    try:
        import pdfplumber
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pdfplumber.open(pdf_path) as pdf:
                for t in pdf.pages[pno].find_tables():
                    tables.append({"engine": "pdfplumber",
                                   "rows": [[("" if c is None else str(c)) for c in row]
                                            for row in t.extract()]})
    except Exception as exc:
        tables.append({"engine": "pdfplumber", "error": str(exc)[:120]})
    return tables


class LayoutWorker:
    """Layout model in a subprocess: a segfault on a malformed-font PDF kills
    only the worker, never the multi-hour extraction run.

    Found 2026-09-21: pymupdf-layout raises an unrecoverable access violation
    inside create_stext_page on some real corpus PDFs. In-process that aborts
    the whole run; isolated, the page is simply marked layout-failed.
    """

    def __init__(self, timeout=180):
        self.timeout = timeout
        self.proc = None
        self.req = None
        self.resp = None
        self.crashes = 0

    def _spawn(self):
        self.req = mp.Queue()
        self.resp = mp.Queue()
        self.proc = mp.Process(target=_layout_child, args=(self.req, self.resp),
                               daemon=True)
        self.proc.start()

    def regions(self, pdf_path, pno):
        if self.proc is None:
            self._spawn()
        elif not self.proc.is_alive():
            # died since last request: a segfault on the previous page
            self.crashes += 1
            self._spawn()
        try:
            self.req.put((pdf_path, pno))
            if self.resp.poll(self.timeout):
                kind, val = self.resp.get()
                if kind == "ok":
                    return val
                return None
        except Exception:
            return None
        # timeout: kill and respawn
        self.kill()
        return None

    def kill(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(5)
        if self.proc is not None and self.proc.exitcode not in (0, None):
            self.crashes += 1
        self.proc = None

    def close(self):
        if self.proc is not None:
            try:
                self.req.put(None)
                self.proc.join(5)
            except Exception:
                pass
            self.kill()


def _layout_child(req, resp):
    """Child worker: own the layout model, answer region requests."""
    import pymupdf
    from pymupdf.layout import DocumentLayoutAnalyzer
    model = DocumentLayoutAnalyzer.get_model()
    while True:
        item = req.get()
        if item is None:
            return
        pdf_path, pno = item
        try:
            doc = pymupdf.open(pdf_path)
            H = doc[pno].rect.height
            regions = model.predict(doc[pno]) or []
            doc.close()
            resp.put(("ok", [r for r in regions]))
        except BaseException as exc:  # noqa: BLE001
            resp.put(("err", f"{type(exc).__name__}: {exc}"[:150]))


_LAYOUT_WORKER = None


def verify_tables_against_text(tables, page_text, pno):
    """Cell-level reconciliation of extractor output vs the page text layer.

    Measured 2026-09-21 (golden matrix, 5 sources): plain TEXT extraction hit
    100% of cells on star_asia / ssy / breakwave and 28/28 of the demolition
    circle+bar values, while the best table extractor reached 83-100%. The text
    layer is therefore the primary RECALL source; the table grid is the primary
    SCHEMA source. This records, per table, how many cells the text layer can
    confirm, so downstream merging knows where the grid dropped values.
    """
    norm_text = re.sub(r"\s+", " ", page_text or "").casefold()
    out = []
    for t in tables:
        rows = t.get("rows") or []
        cells = [str(c).strip() for row in rows for c in row if str(c).strip()]
        checkable = [c for c in cells if re.search(r"\d", c)]
        if not checkable:
            t["text_verified"] = None
            out.append(t)
            continue
        found = sum(1 for c in checkable
                    if re.sub(r"\s+", " ", c).casefold() in norm_text)
        t["text_verified"] = round(found / len(checkable), 3)
        t["text_verified_cells"] = f"{found}/{len(checkable)}"
        out.append(t)
    return out


def text_values_not_in_tables(page_text, tables):
    """Numeric tokens present in the page text but absent from every table.

    These are the values the grid dropped, plus chart axis labels. Returned as
    a list (not just a count) so a downstream merge can actually RECOVER them:
    measured 2026-09-21, text extraction hit 100% of cells on three golden
    pages where the best table extractor reached 83-100%, and swept 28/28
    demolition circle/bar values that the grid captured only 15 of.
    """
    nums = re.findall(r"\b\d[\d,]*\.?\d*\b", page_text or "")
    if not nums:
        return []
    blob = " ".join(str(c) for t in tables for row in (t.get("rows") or [])
                    for c in row).casefold()
    seen, out = set(), []
    for n in nums:
        if n.casefold() not in blob and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def image_only_table_suspect(page, n_tables, n_images, text_chars):
    """Flag pages whose table is likely an IMAGE, needing OCR.

    Derived from the Seabrokers finding (2026-09-21): six engines including
    plain text all scored 0/20 on a rates table that was rendered as a picture.
    Signal: no table recovered, but the page carries images and some text.
    """
    if n_tables or not n_images or text_chars < 50:
        return False
    return True


def layout_tables(page, pdf_path, pno):
    """Layout-constrained camelot: the 15/15 golden path, crash-isolated.

    The layout model runs in a subprocess (see LayoutWorker) because it
    segfaults on malformed-font PDFs.
    """
    global _LAYOUT_WORKER
    if _LAYOUT_WORKER is None:
        _LAYOUT_WORKER = LayoutWorker()
    try:
        H = page.rect.height
    except Exception:
        return []
    regions = _LAYOUT_WORKER.regions(pdf_path, pno)
    if not regions:
        return []
    areas = [f"{x0},{H - y1},{x1},{H - y0}"
             for x0, y0, x1, y1, lbl in regions if lbl == "table"]
    if not areas:
        return []
    out = []
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import camelot
            tabs = camelot.read_pdf(pdf_path, pages=str(pno + 1), flavor="stream",
                                    table_areas=areas)
        for i in range(tabs.n):
            out.append({"engine": "camelot-stream+layout-areas",
                        "acc": round(tabs[i].parsing_report.get("accuracy", 0), 1),
                        "rows": tabs[i].df.values.tolist()})
    except Exception as exc:
        out.append({"engine": "camelot-stream+layout-areas", "error": str(exc)[:120]})
    return out


def harvest_images(page, pageno, chart_dir, meta_rows, doc_key):
    n = 0
    try:
        from PIL import Image
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = page.parent.extract_image(xref)
                raw = pix["image"]
                pil = Image.open(io.BytesIO(raw))
                h = img_dhash(pil)
                fn = f"p{pageno:02d}_{xref}_{(h or 'nohash')[:8]}.{pix['ext']}"
                with open(os.path.join(chart_dir, fn), "wb") as f:
                    f.write(raw)
                rects = page.get_image_bbox(img) if hasattr(page, "get_image_bbox") else None
                meta_rows.append({"doc": doc_key, "page": pageno, "file": fn,
                                  "w": pil.width, "h": pil.height, "dhash": h,
                                  "bbox": [round(v, 1) for v in rects] if rects else None})
                n += 1
            except Exception:
                continue
    except Exception:
        pass
    return n


def derive_source(rel_path):
    """Source label from a repo-relative path.

    Skips structural noise (data/, reports/, pdfs/) so that
    data/reports/seabrokers/pdfs/x.pdf -> "seabrokers" rather than "reports".
    Fixed 2026-09-21: the naive parts[1] made data/reports/* all collapse to
    "reports", which silently merged distinct sources in per-source reports.
    """
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    if not parts:
        return "root"
    skip = {"data", "reports", "docs", "scripts", "pdfs"}
    for p in parts[1:]:
        if p.lower() not in skip:
            return p
    return parts[0]


def is_real_pdf(pdf_path):
    """Cheap header sanity check (skips HTML-dump and truncated .pdf files).

    Note: this does NOT prevent layout-model crashes. Measured 2026-09-21: a
    file with a valid %PDF- header still segfaulted pymupdf-layout, so the
    subprocess isolation in LayoutWorker is the real defense; this is just a
    fast pre-filter that avoids pointless work.
    """
    try:
        with open(pdf_path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def process_one(pdf_path, out_root, skip_tables=False, gated_layout=False):
    """Extract one PDF.

    gated_layout defaults OFF. Measured 2026-09-21 on a stratified sample:
    of 100 text-dense pages, the Camelot+pdfplumber union found zero tables on
    0 of them, so the layout gate fired 0% of the time and contributed nothing
    while costing subprocess complexity and a segfault vector. It remains
    available via --layout for sources where the union comes up empty.
    """
    import pymupdf
    if not is_real_pdf(pdf_path):
        rel = os.path.relpath(pdf_path, REPO)
        return {"doc": rel, "error": "not-a-pdf (quarantined: bad header)",
                "pages": 0, "blocks": 0, "tables": 0, "images": 0, "routes": {}}
    rel = os.path.relpath(pdf_path, REPO)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    source = derive_source(rel)
    dkey = f"{source}/{stem}"
    ddir = os.path.join(out_root, source, stem)
    cdir = os.path.join(ddir, "charts")
    os.makedirs(cdir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    t_rows, tab_rows, p_rows, c_meta = [], [], [], []
    for pno, page in enumerate(doc):
        try:
            page_text = page.get_text() or ""
        except Exception:
            page_text = ""
        pix_chars = len(page_text)
        try:
            n_img = len(page.get_images(full=True))
        except Exception:
            n_img = 0
        route = route_page(page, pix_chars, n_img)
        p_rows.append({"page": pno, "route": route, "chars": pix_chars, "images": n_img})
        if route in ("text", "image-heavy", "garbled"):
            for b in extract_text_blocks(page):
                b.update({"page": pno, "route": route})
                t_rows.append(b)
        if route in ("text", "image-heavy"):
            page_tables = extract_tables_union(pdf_path, pno, skip_tables)
            if gated_layout and (not page_tables or needs_layout(pdf_path, pno, page_tables)):
                page_tables.extend(layout_tables(page, pdf_path, pno))
            # recall reconciliation: the text layer is the primary value source,
            # the table grid the primary schema source. Record both the
            # per-table confidence and the exact values the grid dropped.
            page_tables = verify_tables_against_text(page_tables, page_text, pno)
            orphan = text_values_not_in_tables(page_text, page_tables)
            if orphan:
                p_rows[-1]["values_only_in_text"] = orphan
            if image_only_table_suspect(page, len(page_tables), n_img, pix_chars):
                p_rows[-1]["ocr_queue"] = "no table recovered, page has images"
            # sharper signal: a grid WAS returned but none of its values exist in
            # the text layer -> the table is a picture (Seabrokers case)
            scored = [t.get("text_verified") for t in page_tables
                      if t.get("text_verified") is not None]
            if scored and all(s == 0 for s in scored):
                p_rows[-1]["ocr_queue"] = "table values not in text layer (image table)"
            for t in page_tables:
                t.update({"page": pno})
                tab_rows.append(t)
        harvest_images(page, pno, cdir, c_meta, dkey)
    doc.close()
    with open(os.path.join(ddir, "text.jsonl"), "w", encoding="utf-8") as f:
        for r in t_rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(ddir, "tables.jsonl"), "w", encoding="utf-8") as f:
        for r in tab_rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(ddir, "pages.jsonl"), "w", encoding="utf-8") as f:
        for r in p_rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(cdir, "meta.jsonl"), "w", encoding="utf-8") as f:
        for r in c_meta:
            f.write(json.dumps(r) + "\n")
    return {"doc": dkey, "pages": len(p_rows),
            "routes": {r: sum(1 for p in p_rows if p["route"] == r) for r in
                       set(p["route"] for p in p_rows)},
            "blocks": len(t_rows), "tables": len(tab_rows), "images": len(c_meta),
            "ocr_queue_pages": sum(1 for p in p_rows if p.get("ocr_queue")),
            "orphan_values": sum(len(p.get("values_only_in_text") or []) for p in p_rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?", default="")
    ap.add_argument("--inventory", default="")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted", "v0"))
    ap.add_argument("--no-tables", action="store_true")
    ap.add_argument("--layout", action="store_true",
                    help="enable the gated pymupdf-layout fallback (off by default; "
                         "measured to add nothing on the current corpus but costs "
                         "subprocess overhead and carries a segfault risk)")
    a = ap.parse_args()
    targets = []
    if a.pdf:
        targets = [a.pdf if os.path.isabs(a.pdf) else os.path.join(REPO, a.pdf)]
    else:
        inv = [json.loads(l) for l in open(a.inventory, encoding="utf-8")]
        targets = [os.path.join(REPO, r["path"]) for r in inv[:a.limit]]
    summary = []
    for t in targets:
        try:
            rec = process_one(t, a.out, a.no_tables, gated_layout=a.layout)
        except Exception as exc:
            rec = {"doc": t, "error": f"{type(exc).__name__}: {exc}"}
        summary.append(rec)
        print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
