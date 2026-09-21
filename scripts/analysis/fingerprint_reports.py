"""Layout fingerprinting for report continuity mapping.

For each PDF: per-page char/word counts, table count (pdfplumber),
image count + sizes + dhash (pypdf + PIL), page count, title/first-line.
For each Markdown: heading skeleton, table count, image count, word count.
For each HTML: heading tags, table count, img count, text length.

Sampler: seeded random N files per directory (default: per year-subdir),
always includes newest. Output: JSON lines, one record per file.

Usage:
    python scripts/analysis/fingerprint_reports.py <dir> [--per-year 3] [--seed 42]
        [--out fingerprints.jsonl] [--md] [--html]
    Without --md/--html, scans *.pdf recursively.
"""
import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys


def dhash(pixels, w, h, size=8):
    try:
        from PIL import Image
    except ImportError:
        return None
    img = Image.frombytes("RGB", (w, h), pixels) if isinstance(pixels, bytes) else pixels
    img = img.convert("L").resize((size + 1, size), Image.BILINEAR)
    px = list(img.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return format(bits, "016x")


def fingerprint_pdf(path, skip_tables=False):
    rec = {"file": path, "kind": "pdf", "error": None}
    try:
        from pypdf import PdfReader
    except ImportError:
        rec["error"] = "no pypdf"
        return rec
    try:
        rdr = PdfReader(path)
        rec["pages"] = len(rdr.pages)
        rec["meta_title"] = (rdr.metadata.title if rdr.metadata else None) or ""
        page_chars, page_words, nimgs, imghashes = [], [], 0, []
        for i, pg in enumerate(rdr.pages):
            try:
                txt = pg.extract_text() or ""
            except Exception:
                txt = ""
            page_chars.append(len(txt))
            page_words.append(len(txt.split()))
            try:
                for img in pg.images:
                    nimgs += 1
                    try:
                        h = dhash(img.image, img.image.width, img.image.height)
                    except Exception:
                        h = None
                    imghashes.append({"name": img.name, "hash": h})
            except Exception:
                pass
        rec["page_chars"] = page_chars
        rec["page_words"] = page_words
        rec["n_images"] = nimgs
        rec["image_hashes"] = imghashes
        if skip_tables:
            rec["n_tables_plumber"] = "skipped"
        else:
            try:
                import pdfplumber
                ntables = 0
                with pdfplumber.open(path) as pdf:
                    for pg in pdf.pages:
                        try:
                            ntables += len(pg.find_tables())
                        except Exception:
                            pass
                rec["n_tables_plumber"] = ntables
            except ImportError:
                rec["n_tables_plumber"] = None
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def fingerprint_md(path):
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception as exc:
        return {"file": path, "kind": "md", "error": str(exc)}
    heads = re.findall(r"^(#{1,4}\s+.+)$", txt, re.M)
    return {
        "file": path, "kind": "md", "error": None,
        "words": len(txt.split()),
        "headings": [h.strip()[:100] for h in heads],
        "n_tables": txt.count("\n|"),
        "n_images": len(re.findall(r"!\[", txt)),
    }


def fingerprint_html(path):
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception as exc:
        return {"file": path, "kind": "html", "error": str(exc)}
    return {
        "file": path, "kind": "html", "error": None,
        "chars": len(txt),
        "words": len(re.sub(r"<[^>]+>", " ", txt).split()),
        "headings": re.findall(r"<h[1-3][^>]*>(.{1,100}?)</h[1-3]>", txt)[:20],
        "n_tables": len(re.findall(r"<table", txt, re.I)),
        "n_images": len(re.findall(r"<img", txt, re.I)),
    }


def sample_files(root, exts, per_year, seed, newest_first=True):
    rng = random.Random(seed)
    # group by immediate subdir (usually year) else root
    groups = {}
    for ext in exts:
        for fp in glob.glob(os.path.join(root, "**", f"*{ext}"), recursive=True):
            rel = os.path.relpath(fp, root)
            parts = rel.split(os.sep)
            key = parts[0] if len(parts) > 1 else "_root"
            groups.setdefault(key, []).append(fp)
    picked = []
    for key in sorted(groups):
        files = sorted(groups[key])
        if not files:
            continue
        newest = max(files, key=lambda f: os.path.getmtime(f))
        pool = [f for f in files if f != newest]
        n = min(per_year, len(pool))
        samp = rng.sample(pool, n) if n else []
        picked.append((key, newest, samp, len(files)))
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--per-year", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--no-tables", action="store_true",
                    help="skip pdfplumber table scan (fast path for chart-heavy PDFs)")
    a = ap.parse_args()
    exts = ([".md"] if a.md else [".html"] if a.html else [".pdf"])
    fn = fingerprint_md if a.md else fingerprint_html if a.html else \
        (lambda fp: fingerprint_pdf(fp, skip_tables=a.no_tables))
    out = open(a.out, "w", encoding="utf-8", newline="\n") if a.out else None
    total = 0
    for key, newest, samp, pop in sample_files(a.dir, exts, a.per_year, a.seed):
        for fp in [newest] + samp:
            rec = fn(fp)
            rec["group"] = key
            rec["group_pop"] = pop
            rec["sampled_as"] = "newest" if fp == newest else "random"
            line = json.dumps(rec)
            print(line, flush=True)
            if out:
                out.write(line + "\n")
            total += 1
    print(f"[*] {total} files fingerprinted", file=sys.stderr)
    if out:
        out.close()


if __name__ == "__main__":
    main()
