"""Audit the route label "garbled" against the page's own positioned words.

Written 2026-09-28 (deep review). Read-only: opens the corpus artefacts under
data/extracted/corpus/ and the PDFs they came from, and prints what it finds. It
writes nothing.

Why this exists: route_page() in extract_all.py calls a page "garbled" when fewer
than 25% of the first 2000 characters of its text layer are alphabetic. A page
holding a table of numbers trips that predicate, so the label described
NUMBER-DENSE pages rather than broken text - and the table gate below it read
`if route in ("text", "image-heavy")`, so those pages were never table-extracted. The
gate now runs on content (see the fix on branch auto/extract-fixes-2026-09-28): a page
is table-extracted unless the mojibake detector flagged it.

Measured on the collected corpus, 2026-09-28 23:10 IST:
  * 1,520 pages routed garbled across 749 documents;
  * 1,517 of them carry no ocr_queue flag and no garbled_blocks (the extractor's
    own mojibake detector never fired on them);
  * 1,360 are table-shaped by the test below; 1,401 hold >=8 numeric tokens.

Table-shaped test, derived from the page rather than hardcoded geometry: cluster
the page's own words into y-bands of 3.5 pt, and count a band with >=2 wholly
numeric tokens as a table row. Prose has larger fonts and few bare numbers, so it
does not produce such rows.

Usage:
  python scripts/extract/audit_garbled_route.py                  # summary
  python scripts/extract/audit_garbled_route.py --list           # one doc per line
  python scripts/extract/audit_garbled_route.py --min-bands 5    # gate to tune
"""
import argparse
import collections
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(REPO, "data", "extracted", "corpus")
BAND_TOL = 3.5
NUM_TOKEN = re.compile(r"^-?[\d.,]+$")


def is_numeric_token(w):
    w = w.strip()
    return bool(NUM_TOKEN.match(w)) and any(c.isdigit() for c in w)


def numeric_bands(words):
    """(rows, rows_with_2plus_numbers, numeric_tokens) from positioned words."""
    bands = []
    for w in sorted(words, key=lambda w: (round(w[1], 1), w[0])):
        y = (w[1] + w[3]) / 2
        for b in bands:
            if abs(b["y"] - y) <= BAND_TOL:
                b["words"].append(w)
                b["n"] += 1
                b["y"] = (b["y"] * (b["n"] - 1) + y) / b["n"]
                break
        else:
            bands.append({"y": y, "words": [w], "n": 1})
    numbands = sum(1 for b in bands
                   if sum(1 for w in b["words"] if is_numeric_token(w[4])) >= 2)
    nnum = sum(1 for w in words if is_numeric_token(w[4]))
    return len(bands), numbands, nnum


def garbled_pages():
    """Every page the extractor routed garbled, from the stored pages.jsonl."""
    for dirpath, _dirnames, filenames in os.walk(CORPUS):
        if "pages.jsonl" not in filenames:
            continue
        doc = os.path.relpath(dirpath, CORPUS).replace(os.sep, "/")
        try:
            with open(os.path.join(dirpath, "pages.jsonl"), encoding="utf-8",
                      errors="replace") as f:
                pages = [json.loads(l) for l in f if l.strip()]
        except Exception as exc:
            print(f"READFAIL {doc}: {exc}", file=sys.stderr)
            continue
        for p in pages:
            if p.get("route") == "garbled":
                yield doc, p


def pdf_index():
    idx = collections.defaultdict(list)
    for dirpath, _dirnames, filenames in os.walk(os.path.join(REPO, "corpus")):
        for f in filenames:
            if f.lower().endswith(".pdf"):
                idx[os.path.splitext(f)[0].lower()].append(
                    os.path.join(dirpath, f))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-bands", type=int, default=5,
                    help="numeric bands needed to call a page table-shaped")
    ap.add_argument("--list", action="store_true",
                    help="print one affected document key per line")
    ap.add_argument("--no-pdf", action="store_true",
                    help="skip re-opening the PDFs (page-record counts only)")
    a = ap.parse_args()
    import pymupdf

    idx = {} if a.no_pdf else pdf_index()
    per_doc = collections.Counter()
    per_src = collections.Counter()
    table_shaped = []
    no_pdf = []
    for doc, p in garbled_pages():
        per_doc[doc] += 1
        per_src[doc.split("/")[0]] += 1
        if a.no_pdf:
            continue
        stem = doc.split("/", 1)[1].split("/", 1)[-1].lower()
        cands = idx.get(stem)
        if not cands:
            no_pdf.append(doc)
            continue
        try:
            d = pymupdf.open(cands[0])
            if p["page"] >= d.page_count:
                d.close()
                continue
            page = d[p["page"]]
            bands, numbands, nnum = numeric_bands(page.get_text("words"))
            d.close()
        except Exception as exc:
            print(f"OPENFAIL {doc} p{p['page']}: {exc}", file=sys.stderr)
            continue
        if numbands >= a.min_bands:
            table_shaped.append((doc, p["page"], bands, numbands, nnum))
    print(f"pages routed garbled : {sum(per_doc.values())}")
    print(f"documents affected   : {len(per_doc)}")
    print(f"by source            : {dict(per_src.most_common())}")
    print(f"no PDF resolved      : {len(set(no_pdf))}")
    print(f"table-shaped (>= {a.min_bands} numeric bands): "
          f"{len(table_shaped)} pages in "
          f"{len({d for d, *_ in table_shaped})} documents")
    if a.list:
        for doc, pg, bands, numbands, nnum in sorted(table_shaped):
            print(f"{doc}\t{pg}\tbands={bands}\tnumbands={numbands}\tnum={nnum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
