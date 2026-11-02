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


def stacked_cell_any(cells, stacked_cell) -> bool:
    return any(stacked_cell(c) for c in cells)


def block_is_stacked(block_lines, stacked_cell) -> bool:
    return any(stacked_cell(c) for ln in block_lines for c in ln.split("|")[1:-1])


SEPARATOR = re.compile(r"^\|\s*:?-{3,}")


def norm_label(cell: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", cell.replace("\\", "").lower()).strip()


def row_match(block, fresh_rows, used_rows):
    """Fresh rows that hold exactly this stacked block's values.

    Fresh tables do not always break where the stored ones do (2025 SBLK cash flow: one fresh table, three stored
    blocks), so whole-block matching misses them. Anchor on the block's first line item: the fresh row whose label
    starts the block's first cell, then take consecutive fresh rows while their numbers stay inside the block's
    multiset; accept only when the two multisets are equal. Returns (start, end) in fresh_rows or None."""
    bag = number_bag(block)
    first = next((ln.split("|")[1] for ln in block if not SEPARATOR.match(ln)), "")
    head = norm_label(first)
    if not head:
        return None
    for i, (_ln, label, _b) in enumerate(fresh_rows):
        if i in used_rows or not label or not head.startswith(label):
            continue
        acc = Counter()
        for j in range(i, len(fresh_rows)):
            if j in used_rows:
                break
            acc += fresh_rows[j][2]
            if acc - bag:  # a value the block does not hold
                break
            if acc == bag:
                return i, j + 1
    return None


VALUE = re.compile(r"^(?:\\?\$?\(?\d[\d,]*(?:\.\d+)?\)?%?|—|-|–)$")


def split_short_row(row: str, ncol: int) -> str:
    """A value cell that holds the values of the cells after it, e.g. "| Offering expenses paid | (96) — |  |" in a
    3-column table (the converter put both years in one cell and left the next empty): the values are spread over
    that cell and the empty or missing cells to its right. Applied only when the counts are exact."""
    cells = row.split("|")[1:-1]
    cells += [" "] * max(0, ncol - len(cells))
    for k in range(1, len(cells)):
        toks = cells[k].split()
        rest = cells[k + 1:]
        if len(toks) > 1 and all(VALUE.match(t) for t in toks) and len(rest) >= len(toks) - 1                 and all(not c.strip() for c in rest[:len(toks) - 1])                 and all(not c.strip() for c in cells[1:k]):
            new = cells[:k] + [f" {t} " for t in toks] + rest[len(toks) - 1:]
            return "|" + "|".join(new) + "|"
    return row


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
    # fresh data rows (no separators, no repeated "Line Item" header rows) for row-level matching
    fresh_rows = []
    for s, e in table_blocks(new_lines):
        for ln in new_lines[s:e]:
            cells = ln.split("|")[1:-1]
            if SEPARATOR.match(ln) or not cells or cells[0].strip() == "Line Item" or stacked_cell_any(cells, stacked_cell):
                continue
            fresh_rows.append((ln, norm_label(cells[0]), number_bag([ln])))
    used, used_rows = set(), set()
    replace = {}
    for s, e in stacked_blocks:
        bag = number_bag(lines[s:e])
        hit = next((k for k, (_s, _e, b) in enumerate(candidates) if k not in used and b == bag), None)
        if hit is not None:
            used.add(hit)
            cs, ce, _ = candidates[hit]
            replace[s] = (e, new_lines[cs:ce])
            continue
        rows = row_match(lines[s:e], fresh_rows, used_rows)
        if rows is None or not bag:
            st["unmatched"] += 1
            continue
        r0, r1 = rows
        # label-only rows (section headings such as "Changes in operating assets and liabilities:") that the
        # stored block carries right after its values belong to it as well
        block_text = norm_label(" ".join(lines[s:e]))
        while (r1 < len(fresh_rows) and r1 not in used_rows and not fresh_rows[r1][2]
               and fresh_rows[r1][1] and fresh_rows[r1][1] in block_text):
            r1 += 1
        used_rows.update(range(r0, r1))
        body = [fresh_rows[k][0] for k in range(r0, r1)]
        ncol = max(len(b.split("|")) - 2 for b in body)
        body = [split_short_row(b, ncol) for b in body]
        header = "| Line Item | " + " | ".join(f"Col {c}" for c in range(2, ncol + 1)) + " |"
        sep = "| :--- | " + " | ".join("---:" for _ in range(2, ncol + 1)) + " |"
        replace[s] = (e, [header, sep] + body)
        st["row_matched"] = st.get("row_matched", 0) + 1
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
