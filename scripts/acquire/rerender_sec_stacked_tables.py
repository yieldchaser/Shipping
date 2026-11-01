#!/usr/bin/env python3
"""
scripts/acquire/rerender_sec_stacked_tables.py

Re-renders the stacked statement tables of SEC filing Markdowns (corpus/10-companies) with the fixed
converter (standardize_sec_markdown.repair_table_block no longer treats "(814)" as a sub-item marker).

For each file given (the list from scripts/audit/detect_sec_stacked_tables.py):
  1. the filing is converted again exactly as fetch_sec_filings.py does (sec2md on filing.html(), plus the
     EX-99 exhibits of 6-K/8-K), giving a set of fresh Markdown tables
  2. every table block of the existing file that has a stacked cell is replaced by the fresh table that holds
     exactly the same numbers (same multiset of number tokens, brackets and % kept) and has no stacked cell
  3. the whole file is then checked: the number multiset of the file must be identical before and after,
     otherwise nothing is written

Every other byte of the file (prose, frontmatter, other tables, line endings) is untouched. Blocks without
an exactly matching fresh table (PDF-origin text, tables edited since) are left as they are and reported.

    python scripts/acquire/rerender_sec_stacked_tables.py --list damaged.txt [--dry-run] [-j 3]
    python scripts/acquire/rerender_sec_stacked_tables.py corpus/10-companies/VALE/6-K/X.md [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "scripts" / "acquire", REPO_ROOT / "scripts" / "audit"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

NUM_TOKEN = re.compile(r"\(?\d[\d,]*(?:\.\d+)?\)?%?")
PLACEHOLDER = re.compile(r"Col \d+")  # header names the standardizer invents for empty header cells


def number_bag(lines) -> Counter:
    """Multiset of number tokens (with brackets and %), thousands commas kept, trailing commas dropped."""
    bag = Counter()
    for line in lines:
        for tok in NUM_TOKEN.findall(PLACEHOLDER.sub("", line)):
            bag[tok.replace(",)", ")").rstrip(",")] += 1
    return bag


def table_blocks(lines):
    """[(start, end_exclusive)] of every run of lines starting with '|'."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def block_is_stacked(block_lines, stacked_cell) -> bool:
    return any(stacked_cell(c) for ln in block_lines for c in ln.split("|")[1:-1])


def fresh_markdown(meta: dict) -> str:
    """Convert the filing again the way fetch_sec_filings.process_filing does (no frontmatter)."""
    from edgar import find, set_identity
    import fetch_sec_filings as fsf
    import sec_exhibits
    from repair_sec_markdown_tables import repair_markdown

    set_identity(fsf.SEC_IDENTITY)
    accession = meta["accession_number"]
    form = meta["form"]
    filing = find(accession)
    body, _method = fsf.convert_filing_to_markdown(filing)
    parts = [body]
    if form.split("-A")[0] in sec_exhibits.FORMS_WITH_EXHIBITS and meta.get("cik"):
        sections = sec_exhibits.build_exhibit_sections(
            fsf.get_sec_client(), meta["cik"], accession, converter=fsf.convert_exhibit_html
        )
        parts += [s for _, s in sections]
    text, _ = repair_markdown("\n\n".join(parts))
    return text


def read_meta(text: str) -> dict:
    meta = {}
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    for line in (m.group(1) if m else "").split("\n"):
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip("'\"")
    return meta


def rerender(path_str: str, dry_run: bool = False) -> dict:
    from detect_sec_stacked_tables import stacked_cell

    path = Path(path_str)
    if not path.is_absolute():
        path = REPO_ROOT / path
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    st = {"file": path.name, "status": "", "blocks_stacked": 0, "replaced": 0, "unmatched": 0}
    lines = text.split("\n")
    stacked_blocks = [(s, e) for s, e in table_blocks(lines) if block_is_stacked(lines[s:e], stacked_cell)]
    st["blocks_stacked"] = len(stacked_blocks)
    if not stacked_blocks:
        st["status"] = "no_stacked_table_blocks"
        return st

    meta = read_meta(text)
    new_lines = fresh_markdown(meta).split("\n")
    candidates = []  # fresh, non-stacked blocks: (start, end, bag)
    for s, e in table_blocks(new_lines):
        blk = new_lines[s:e]
        if not block_is_stacked(blk, stacked_cell):
            candidates.append((s, e, number_bag(blk)))
    used = set()
    replace = {}
    for s, e in stacked_blocks:
        bag = number_bag(lines[s:e])
        hit = next((k for k, (_s, _e, b) in enumerate(candidates) if k not in used and b == bag), None)
        if hit is None:
            st["unmatched"] += 1
            continue
        used.add(hit)
        cs, ce, _ = candidates[hit]
        replace[s] = (e, new_lines[cs:ce])
    st["replaced"] = len(replace)

    if not replace:
        st["status"] = "no_match"
        return st

    out, i = [], 0
    while i < len(lines):
        if i in replace:
            e, blk = replace[i]
            out.extend(blk)
            i = e
        else:
            out.append(lines[i])
            i += 1
    after = "\n".join(out)

    if number_bag(text.split("\n")) != number_bag(out):
        lost = number_bag(text.split("\n")) - number_bag(out)
        added = number_bag(out) - number_bag(text.split("\n"))
        st["status"] = "FAILED_number_check"
        st["lost"] = dict(list(lost.items())[:10])
        st["added"] = dict(list(added.items())[:10])
        return st

    if not dry_run:
        path.write_bytes((after.replace("\n", "\r\n") if crlf else after).encode("utf-8"))
    st["status"] = "dry_run_ok" if dry_run else "written"
    return st


def _run(args):
    path, dry = args
    try:
        return rerender(path, dry)
    except Exception as e:  # noqa: BLE001
        return {"file": Path(path).name, "status": "ERROR", "error": repr(e)[:300]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--list", help="text file with one corpus path per line")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-j", type=int, default=1)
    a = ap.parse_args()
    paths = list(a.paths)
    if a.list:
        paths += [p.strip() for p in Path(a.list).read_text(encoding="utf-8").splitlines() if p.strip()]
    jobs = [(p, a.dry_run) for p in paths]
    if a.j > 1:
        with ProcessPoolExecutor(max_workers=a.j) as ex:
            for res in ex.map(_run, jobs):
                print(json.dumps(res, ensure_ascii=False), flush=True)
    else:
        for job in jobs:
            print(json.dumps(_run(job), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
