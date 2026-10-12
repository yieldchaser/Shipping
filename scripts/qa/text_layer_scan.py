"""Leads for a text-layer audit: MD tables whose numbers are not printed in the source PDF's text layer.

For every MD under data/extracted/md/<source> that names a source PDF, each markdown table's numbers are
compared with the numbers in the PDF text (all pages). A table is a lead when at least 3 of its numbers
exist and more than 20% of them are not printed. A lead is NOT a verdict: chart reads, OCR'd image pages
(see `image_pages`), computed columns and number formatting all produce leads; each one needs the page
render before anything is changed.

    python scripts/qa/text_layer_scan.py banchero_costa lion ssy affinity fearnleys

Writes .reparse_staging/text_scan/<source>.csv (one row per lead) and prints a summary per source.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "md_cleanup"))
import intermodal_table_rebuild as R  # noqa: E402
from star_asia_page_rebuild import nums  # noqa: E402

TABLE = re.compile(r"^\s*\|")
OUT = ROOT / ".reparse_staging" / "text_scan"


def tables(lines):
    """(start, end, heading) per markdown table; heading = nearest non-empty line above."""
    i = 0
    while i < len(lines):
        if TABLE.match(lines[i]):
            j = i
            while j < len(lines) and TABLE.match(lines[j]):
                j += 1
            k = i - 1
            while k >= 0 and not lines[k].strip():
                k -= 1
            yield i, j, (lines[k].strip() if k >= 0 else "")
            i = j
        else:
            i += 1


def scan(source):
    rows, stat = [], Counter()
    for md in sorted((ROOT / "data" / "extracted" / "md" / source).rglob("*.md")):
        raw = md.read_bytes().decode("utf-8", "ignore")
        pdf = R.source_pdf(raw)
        if pdf is None:
            stat["no pdf"] += 1
            continue
        stat["mds"] += 1
        doc = pymupdf.open(pdf)
        texts = [p.get_text() for p in doc]
        image_pages = sum(1 for t in texts if len(t.strip()) < 50)
        printed = set().union(*(nums(t) for t in texts)) if texts else set()
        lines = raw.splitlines()
        for a, b, head in tables(lines):
            stat["tables"] += 1
            if head.startswith(">"):            # already carries an Estimate / not-transcribed note
                stat["noted tables"] += 1
                continue
            n = nums("\n".join(lines[a + 2:b]))
            miss = sorted(n - printed)
            if len(n) >= 3 and len(miss) / len(n) > 0.2:
                stat["leads"] += 1
                rows.append({"md": md.relative_to(ROOT).as_posix(), "line": a + 1, "heading": head[:80],
                             "header": lines[a][:120], "unprinted": len(miss), "numbers": len(n),
                             "image_pages": image_pages, "pages": len(texts), "sample": " ".join(miss[:12])})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{source}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["md", "line", "heading", "header", "unprinted", "numbers",
                                           "image_pages", "pages", "sample"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(source, dict(stat), flush=True)


if __name__ == "__main__":
    for s in sys.argv[1:]:
        scan(s)
