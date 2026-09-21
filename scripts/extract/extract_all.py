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
    0.15s/page (91% of runtime). Skip it unless the page looks like a
    missed or fragmented table.
    """
    if not camelot_tables:
        # no tables found -> maybe borderless/missed; only worth layout on
        # text-dense pages, not figure-only pages
        return True
    if len(camelot_tables) > 5:
        # likely one table fragmented by wrapped rows -> layout merges it
        return True
    for t in camelot_tables:
        rows = t.get("rows") or []
        if rows and len(rows) <= 3:
            return True  # stub fragments: layout gives real bounds
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


def layout_tables(pdf_path, pno):
    """Layout-constrained camelot: the 15/15 golden path."""
    import pymupdf
    from pymupdf.layout import DocumentLayoutAnalyzer
    global _LAYOUT_MODEL
    try:
        _LAYOUT_MODEL
    except NameError:
        _LAYOUT_MODEL = DocumentLayoutAnalyzer.get_model()
    doc = pymupdf.open(pdf_path)
    pg = doc[pno]
    H = pg.rect.height
    regions = _LAYOUT_MODEL.predict(pg)
    doc.close()
    areas = [f"{x0},{H - y1},{x1},{H - y0}" for x0, y0, x1, y1, lbl in regions if lbl == "table"]
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


def process_one(pdf_path, out_root, skip_tables=False, gated_layout=True):
    import pymupdf
    rel = os.path.relpath(pdf_path, REPO)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    source = rel.split(os.sep)[1] if len(rel.split(os.sep)) > 2 else "root"
    dkey = f"{source}/{stem}"
    ddir = os.path.join(out_root, source, stem)
    cdir = os.path.join(ddir, "charts")
    os.makedirs(cdir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    t_rows, tab_rows, p_rows, c_meta = [], [], [], []
    for pno, page in enumerate(doc):
        pix_chars = len(page.get_text() or "")
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
            if gated_layout and page_tables and needs_layout(pdf_path, pno, page_tables):
                page_tables.extend(layout_tables(pdf_path, pno))
            elif gated_layout and not page_tables:
                page_tables.extend(layout_tables(pdf_path, pno))
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
            "blocks": len(t_rows), "tables": len(tab_rows), "images": len(c_meta)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?", default="")
    ap.add_argument("--inventory", default="")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted", "v0"))
    ap.add_argument("--no-tables", action="store_true")
    ap.add_argument("--no-layout", action="store_true",
                    help="disable the gated layout pass (fast, lower table recall)")
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
            rec = process_one(t, a.out, a.no_tables, gated_layout=not a.no_layout)
        except Exception as exc:
            rec = {"doc": t, "error": f"{type(exc).__name__}: {exc}"}
        summary.append(rec)
        print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
