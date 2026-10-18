"""Tables whose numbers the source does not print: chart readings that a parser turned into a table.

For each MD table, the share of its numbers (2+ significant digits) found neither on the PDF text layer nor in
the cached Nace second read (.reparse_staging/nace_second_read/, written by nace_second_read.py). A table at or
above --min (default 0.5) is listed with the heading above it. --apply replaces each listed table with the note
"> **Chart (not transcribed).** The report prints no values for it." (the Banchero note), prose untouched.

Look at the page before --apply: an image table Nace has not read yet also scores high.

    python scripts/qa/unprinted_tables.py --source intermodal [--min 0.5] [--only LIST] [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
from nace_second_read import CACHE, MD_ROOT, NUM, ROOT, norm, pool, source_pdf  # noqa: E402

NOTE = "> **Chart (not transcribed).** The report prints no values for it."
SEP = re.compile(r"^\|[\s:|-]+\|?\s*$")


def tables(lines: list[str]):
    """(start, end) line spans of pipe tables."""
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            if j - i >= 3 and SEP.match(lines[i + 1].strip()):
                yield i, j
            i = j
        else:
            i += 1


def heading(lines: list[str], i: int) -> str:
    for k in range(i - 1, max(-1, i - 8), -1):
        s = lines[k].strip()
        if s and not s.startswith("|"):
            return s[:90]
    return ""


def scan(md: Path, min_share: float) -> list[tuple[int, int, float, int, str]]:
    text = md.read_text(encoding="utf-8")
    pdf = source_pdf(text)
    if not pdf:
        return []
    with pymupdf.open(pdf) as doc:
        known = set().union(*(pool(p.get_text()) for p in doc))
    cp = CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}.json"
    if cp.exists():
        known |= pool(json.loads(cp.read_text(encoding="utf-8"))["markdown"])
    lines = text.split("\n")
    out = []
    for a, b in tables(lines):
        nums = [n for ln in lines[a + 2:b] for n in NUM.findall(ln) if len(re.sub(r"[.,]", "", n).strip("0")) >= 2]
        if len(nums) < 4:
            continue
        share = sum(not (norm(n) & known) for n in nums) / len(nums)
        if share >= min_share:
            out.append((a, b, share, len(nums), heading(lines, a)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--min", type=float, default=0.5)
    ap.add_argument("--only", help="file listing MD names to scan")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    mds = sorted((MD_ROOT / a.source).rglob("*.md"))
    if a.only:
        keep = {Path(x.strip()).name for x in Path(a.only).read_text(encoding="utf-8").splitlines() if x.strip()}
        mds = [m for m in mds if m.name in keep]
    n_tab = n_md = 0
    for md in mds:
        hits = scan(md, a.min)
        if not hits:
            continue
        n_md += 1
        n_tab += len(hits)
        for s, e, share, n, h in hits:
            print(f"{share:4.0%} {n:4d} {md.relative_to(ROOT).as_posix()}:{s + 1} | {h}")
        if a.apply:
            lines = md.read_text(encoding="utf-8").split("\n")
            for s, e, *_ in reversed(hits):
                lines[s:e] = [NOTE]
            md.write_text("\n".join(lines), encoding="utf-8", newline="")
    print(f"{n_tab} tables in {n_md} MDs ({'applied' if a.apply else 'listed'})")


if __name__ == "__main__":
    main()
