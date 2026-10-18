#!/usr/bin/env python3
"""CI gate for NEW Markdown (untracked under data/extracted/md/): tables of numbers the source does not print.

Run after the extractors and protect_accepted_md.py, before `git add`. Accepted MDs are never touched.

For every new MD with a PDF source_file, each table is scored by scripts/qa/unprinted_tables.py (share of its
numbers that are not on the PDF text layer). Tables under an "> **Estimate.**" note (vector-geometry charts)
are skipped.
  * Every number unprinted AND the PDF holds no images at all: the numbers cannot be printed anywhere, so the
    table is a parser's chart reading. It is replaced with the "Chart (not transcribed)" note (owner rule:
    wrong data is deleted, not kept).
  * Otherwise, when the share is >= 0.5: the table may be an image table, so it is left as is and listed in
    data/extracted/md/_FIDELITY_REVIEW.json for a second read (scripts/qa/nace_second_read.py, then a look).

Flags: --dry-run (report only). Exit 0 unless git fails.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "qa"))
from nace_second_read import source_pdf  # noqa: E402
from unprinted_tables import NOTE, scan  # noqa: E402

QUEUE = ROOT / "data" / "extracted" / "md" / "_FIDELITY_REVIEW.json"  # "_": protect_accepted_md leaves it writable


def new_mds() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "data/extracted/md"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.splitlines() if p.endswith(".md")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {}
    noted = queued = 0
    for md in new_mds():
        text = md.read_text(encoding="utf-8", errors="replace")
        pdf = source_pdf(text)
        if not pdf:
            continue
        with pymupdf.open(pdf) as doc:
            has_images = any(p.get_images() for p in doc)
        lines = text.split("\n")
        drop, review = [], []
        for s, e, share, n, head in scan(md, 0.5):
            if any("**Estimate.**" in lines[k] for k in range(max(0, s - 4), s)):
                continue
            if share >= 1.0 and not has_images:
                drop.append((s, e))
            else:
                review.append({"line": s + 1, "share": round(share, 2), "numbers": n, "heading": head})
        rel = md.relative_to(ROOT).as_posix()
        for s, e in reversed(drop):
            print(f"  chart reading, no image in PDF: {rel}:{s + 1}")
            lines[s:e] = [NOTE]
        if drop and not a.dry_run:
            md.write_text("\n".join(lines), encoding="utf-8", newline="")
        if review:
            queue[rel] = review
            print(f"  review: {rel} {len(review)} table(s)")
        noted += len(drop)
        queued += len(review)
    if queued and not a.dry_run:
        QUEUE.write_text(json.dumps(queue, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"fidelity gate: {noted} chart-reading tables noted, {queued} tables queued for review"
          f"{' (dry run)' if a.dry_run else ''}")


if __name__ == "__main__":
    main()
