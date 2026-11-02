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


def restore_match(block, rows, used_rows):
    """Source rows for a stacked block that LOST values in the old conversion (EDRY 20-F 2026-04-28: five line
    items stacked, the values of "Non-vested on January 1, 2024" missing). The run must start at the block's first
    line item and end at its last one, and hold every number of the block; the extra numbers are the lost ones,
    read from the SEC source. Returns (start, end, restored Counter) or None."""
    bag = number_bag(block)
    labels = [norm_label(ln.split("|")[1]) for ln in block if not SEPARATOR.match(ln) and ln.split("|")[1].strip()]
    if not labels or not bag:
        return None
    head, last = labels[0], labels[-1]
    for i, (_ln, label, _b) in enumerate(rows):
        if i in used_rows or not label or not head.startswith(label):
            continue
        acc = Counter()
        for j in range(i, len(rows)):
            if j in used_rows or not rows[j][0]:
                break
            acc += rows[j][2]
            if rows[j][1] == last and j > i:
                if not bag - acc:
                    return i, j + 1, acc - bag
                break
    return None


def fresh_markdown(meta: dict) -> tuple[str, list[str]]:
    """Convert the filing again the way fetch_sec_filings.process_filing does (no frontmatter).
    Also returns the source HTML documents (main document, then the EX-99 exhibits)."""
    from edgar import find, set_identity
    import fetch_sec_filings as fsf
    import sec_exhibits
    from repair_sec_markdown_tables import repair_markdown

    set_identity(fsf.SEC_IDENTITY)
    accession = meta["accession_number"]
    form = meta["form"]
    filing = find(accession)
    body, _method = fsf.convert_filing_to_markdown(filing)
    parts, htmls = [body], [filing.html() or ""]
    if form.split("-A")[0] in sec_exhibits.FORMS_WITH_EXHIBITS and meta.get("cik"):
        def convert(html: str) -> str:
            htmls.append(html)
            return fsf.convert_exhibit_html(html)
        sections = sec_exhibits.build_exhibit_sections(fsf.get_sec_client(), meta["cik"], accession, converter=convert)
        parts += [s for _, s in sections]
    text, _ = repair_markdown("\n\n".join(parts))
    return text, htmls


def html_rows(html: str) -> list[str]:
    """Every <tr> of the source HTML as one Markdown row, read straight from the cells.

    sec2md stacks some statements (VALE 6-K 2026-07-31: three <tr> rows came out as one row whose cells hold
    every value) and a fresh conversion repeats it, so stacked blocks with no clean fresh table are matched
    against the source rows themselves. "$" cells join the value after them, ")" and "%" cells the value before
    them (the usual EDGAR split), and columns empty in every row of a table are dropped. Tables are separated
    by an empty row ("") so a match never runs from one table into the next."""
    from bs4 import BeautifulSoup

    out: list[str] = []
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        if table.find("table"):
            continue  # layout wrapper; its inner tables are visited on their own
        rows = []
        for tr in table.find_all("tr"):
            cells: list[str] = []
            for td in tr.find_all(["td", "th"]):
                t = re.sub(r"\s+", " ", td.get_text(" ")).strip()
                t = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", t))
                try:
                    span = max(1, min(int(td.get("colspan", 1)), 20))
                except ValueError:
                    span = 1
                cells += [t] + [""] * (span - 1)
            if any(cells):
                rows.append(cells)
        if not rows:
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        for r in rows:  # "$" | "(1,234" | ")" -> "" | "$(1,234)" | ""
            for k in range(width):
                if r[k] in ("$", "US$") and k + 1 < width and r[k + 1]:
                    r[k + 1], r[k] = r[k] + r[k + 1], ""
                elif r[k] in (")", "%", ")%", "%)"):
                    prev = next((m for m in range(k - 1, -1, -1) if r[m]), None)
                    if prev is not None:
                        r[prev], r[k] = r[prev] + r[k], ""
        # EDGAR splits one printed column over several cells ("$" | "1,234" | ")" , or a header spanning a
        # value column and its padding): merge neighbouring columns that never both hold text in one row
        cols = [[r[k] for r in rows] for k in range(width) if any(r[k] for r in rows)]
        k = 0
        while k < len(cols) - 1:
            a, b_ = cols[k], cols[k + 1]
            if k > 0 and not any(x and y for x, y in zip(a, b_)):
                cols[k] = [x or y for x, y in zip(a, b_)]
                del cols[k + 1]
            else:
                k += 1
        for n in range(len(rows)):
            cells = [col[n] for col in cols]
            # "$" escaped as the stored corpus writes it (Markdown math delimiter)
            out.append("| " + " | ".join(c.replace("|", "/").replace("$", r"\$") for c in cells) + " |")
        out.append("")
    return out


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
    fresh_text, htmls = fresh_markdown(meta)
    new_lines = fresh_text.split("\n")
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
    source_rows, used_source = None, set()
    restored = Counter()  # values the old conversion lost, put back from the SEC source rows
    replace = {}
    for s, e in stacked_blocks:
        bag = number_bag(lines[s:e])
        hit = next((k for k, (_s, _e, b) in enumerate(candidates) if k not in used and b == bag), None)
        if hit is not None:
            used.add(hit)
            cs, ce, _ = candidates[hit]
            replace[s] = (e, new_lines[cs:ce])
            continue
        # a clean header line above the separator (column years, "Notes") is kept and only the rows under it are
        # matched; its first cell is usually empty, so it cannot anchor a match (VALE 6-K 2026-07-31)
        blk = lines[s:e]
        attempts = [([], blk)]
        if len(blk) > 2 and SEPARATOR.match(blk[1]) and not stacked_cell_any(blk[0].split("|")[1:-1], stacked_cell):
            attempts.append((blk[:1], blk[2:]))
        found = None
        for head, part in attempts:
            if not number_bag(part):
                continue
            for name in ("fresh", "source"):
                if name == "fresh":
                    pool, used_pool = fresh_rows, used_rows
                else:
                    if source_rows is None:
                        # "" separates source tables: it gets a bag no block holds, so a run stops there
                        source_rows = [(ln, norm_label(ln.split("|")[1]), number_bag([ln])) if ln else
                                       ("", "", Counter({"\0": 1})) for h in htmls for ln in html_rows(h)]
                    pool, used_pool = source_rows, used_source
                rows = row_match(part, pool, used_pool)
                if rows is not None:
                    found = (head, part, pool, used_pool, rows, name)
                    break
            if found:
                break
        if found is None and source_rows:
            for head, part in reversed(attempts):  # keep a clean header line when there is one
                hit = restore_match(part, source_rows, used_source)
                if hit:
                    found = (head, part, source_rows, used_source, hit[:2], "restored")
                    restored += hit[2]
                    break
        if found is None:
            st["unmatched"] += 1
            continue
        head, part, pool, used_pool, (r0, r1), name = found
        st[f"{name}_rows_matched"] = st.get(f"{name}_rows_matched", 0) + 1
        # label-only rows (section headings such as "Changes in operating assets and liabilities:") that the
        # stored block carries right after its values belong to it as well
        block_text = norm_label(" ".join(part))
        while (r1 < len(pool) and r1 not in used_pool and not pool[r1][2]
               and pool[r1][1] and pool[r1][1] in block_text):
            r1 += 1
        used_pool.update(range(r0, r1))
        body = [pool[k][0] for k in range(r0, r1)]
        # label-only rows keep the stored line's formatting (bold section headings), padded to the new width
        stored_label_rows = {norm_label(ln.split("|")[1]): ln.split("|")[1] for ln in part
                             if not SEPARATOR.match(ln) and not number_bag([ln]) and ln.split("|")[1].strip()}
        ncol = max(len(b.split("|")) - 2 for b in body)
        for n, row in enumerate(body):
            lab = norm_label(row.split("|")[1])
            if not number_bag([row]) and lab in stored_label_rows and not any(c.strip() for c in row.split("|")[2:-1]):
                body[n] = "|" + stored_label_rows[lab] + "|" + "  |" * (ncol - 1)
        body = [split_short_row(b, ncol) for b in body]
        if head:
            cells = head[0].split("|")[1:-1]
            cells += [" "] * (ncol - len(cells))
            header = "|" + "|".join(cells) + "|"
        else:
            header = "| Line Item | " + " | ".join(f"Col {c}" for c in range(2, ncol + 1)) + " |"
        sep = "| :--- | " + " | ".join("---:" for _ in range(2, ncol + 1)) + " |"
        if block_is_stacked(body, stacked_cell):
            # the source cell itself holds this text (BHP result boxes, TRMD vote tables): nothing to repair
            st["source_faithful"] = st.get("source_faithful", 0) + 1
            used_pool.difference_update(range(r0, r1))
            continue
        replace[s] = (e, [header, sep] + body)
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

    if restored:
        st["restored"] = {k: v for k, v in restored.items()}
    if number_bag(text.split("\n")) + restored != number_bag(out):
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
