"""Throughput probe: time the v1 extractor on a representative doc sample.

Answers "how long for 7,816 docs?" with measured numbers, split by stage
(route / layout / tables / charts) so the bottleneck is visible.

Usage: python scripts/extract/timing_probe.py --n 12 [--layout]
"""
import argparse
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "extract"))


def timed_docs(sample, out, use_layout):
    import pymupdf
    results = []
    layout_model = None
    if use_layout:
        from pymupdf.layout import DocumentLayoutAnalyzer
        t0 = time.time()
        layout_model = DocumentLayoutAnalyzer.get_model()
        load_s = time.time() - t0
        print(f"layout model load: {load_s:.1f}s")
    for path in sample:
        t_start = time.time()
        doc = pymupdf.open(path)
        t_open = time.time() - t_start
        pages = len(doc)
        # route stage
        t0 = time.time()
        for pg in doc:
            _ = len(pg.get_text() or "")
            _ = len(pg.get_images(full=True))
        t_route = time.time() - t0
        # layout stage (page regions)
        t_layout = 0.0
        if layout_model is not None:
            t0 = time.time()
            for pg in doc:
                layout_model.predict(pg)
            t_layout = time.time() - t0
        # table stage (camelot + pdfplumber) on first 3 pages only: cost driver
        t_tables = 0.0
        if pages:
            import camelot
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t0 = time.time()
                try:
                    camelot.read_pdf(path, pages="1-3", flavor="stream")
                except Exception:
                    pass
                t_tables = time.time() - t0
        doc.close()
        rec = {"doc": os.path.relpath(path, REPO), "pages": pages,
               "open_s": round(t_open, 2), "route_s": round(t_route, 2),
               "layout_s": round(t_layout, 2), "tables3pg_s": round(t_tables, 2),
               "total_s": round(time.time() - t_start, 2)}
        results.append(rec)
        print(json.dumps(rec), flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    inv = [json.loads(l) for l in
           open(os.path.join(REPO, "data", "extracted", "inventory.jsonl"), encoding="utf-8")]
    uniq = [r for r in inv if not r.get("dup_of_content")]
    random.Random(a.seed).shuffle(uniq)
    # spread across roots
    by_root, sample = {}, []
    for r in uniq:
        k = r["root"]
        if by_root.get(k, 0) < 2:
            by_root[k] = by_root.get(k, 0) + 1
            sample.append(os.path.join(REPO, r["path"]))
        if len(sample) >= a.n:
            break
    print(f"probing {len(sample)} docs, layout={a.layout}")
    res = timed_docs(sample, "", a.layout)
    tot = sum(r["total_s"] for r in res)
    pages = sum(r["pages"] for r in res)
    print(f"\nTOTAL {tot:.1f}s for {pages} pages "
          f"({tot / max(1, pages):.2f}s/page)")
    for f in ("open_s", "route_s", "layout_s", "tables3pg_s"):
        s = sum(r[f] for r in res)
        print(f"  {f}: {s:.1f}s")
    print(f"\nProjection for 7,816 docs (6.79GB, ~55k pages):")
    print(f"  single worker: {tot / len(res) * 7816 / 3600:.1f} hours")
    print(f"  2 workers:     {tot / len(res) * 7816 / 2 / 3600:.1f} hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
