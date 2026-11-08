"""Re-convert SEC filing Markdowns whose tables hold two printed values in one cell.

Before the 2026-11-02 converter fix, sec2md merged neighbouring value columns of some statements into one cell:

    | Selling and administrative | 4(b) | (437) (362) | (842) (775) |

rerender_sec_stacked_tables.py replaced the rows with three or more values in a cell, but rows with two values per
cell stayed (409 filings on 2026-11-08; VALE 6-K 2026-07-31 alone had 156 such rows). The current converter writes
these tables correctly, so this pass converts the filing again exactly as fetch_sec_filings.process_filing does
(main document, EX-99 exhibits, table repair, paragraph rejoin), takes the table headers from the filing
HTML (sec_tables_from_html.rebuild, as the stored files had them) and keeps the stored frontmatter.

A file is rewritten only when the new conversion passes every gate:
  * it has fewer cells holding two values than the stored file;
  * every number of the stored file is still there (as a multiset; the new one may hold more: values the old
    conversion dropped);
  * at most 0.5% of the stored file's words are missing from it.
Otherwise the file is left as is and the reason is printed. The mirror under data/extracted/md/companies is
written too where it exists.

    python scripts/acquire/reconvert_sec_merged_cells.py --scan                 # list affected files
    python scripts/acquire/reconvert_sec_merged_cells.py --all [--dry-run] [-j 3]
    python scripts/acquire/reconvert_sec_merged_cells.py corpus/10-companies/VALE/6-K/X.md [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "scripts" / "acquire"), str(REPO_ROOT / "scripts" / "audit"), str(REPO_ROOT / "scripts")]

NUM = r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?%?"
TWO = re.compile(rf"^\s*{NUM}\s+{NUM}\s*$")
YEARS = re.compile(r"^\s*(?:19|20)\d\d\s+(?:19|20)\d\d\s*$")
SEPARATOR = re.compile(r"^\|\s*:?-")


def two_value_cells(text: str) -> int:
    n = 0
    for line in text.split("\n"):
        if line.startswith("|") and not SEPARATOR.match(line):
            n += sum(1 for c in line.split("|")[2:-1] if TWO.match(c) and not YEARS.match(c))
    return n


FOLIO = re.compile(r"^\s*(?:[-–—]\s*)?(?:Page\s+)?(?:[A-Z]{1,2}-)?\d{1,4}(?:\s*[-–—])?\s*$", re.I)


def numbers(text: str, data_only: bool = False) -> Counter:
    """Numbers of the text, page folios (lines holding only a page number) left out: conversions place them
    differently and they are not data. data_only also leaves out table header rows (the row above a "| :---"
    separator): their dates and years are written once per column or once per span depending on the converter."""
    lines = text.split("\n")
    keep = [l for k, l in enumerate(lines) if not FOLIO.match(l)
            and not (data_only and l.startswith("|") and k + 1 < len(lines) and SEPARATOR.match(lines[k + 1]))]
    body = "\n".join(keep)
    body = re.sub(r"\bCol \d+\b", "", body)  # "Col 2" / "Col 7": placeholder headers the old standardizer wrote
    return Counter(re.sub(r"[,$()%]", "", t) for t in re.findall(r"\d[\d,]*(?:\.\d+)?", body))


def words(text: str) -> Counter:
    return Counter(w.lower() for w in re.findall(r"[A-Za-z]{2,}", text))


def split_frontmatter(text: str) -> tuple[str, str]:
    m = re.match(r"---\n.*?\n---\n", text, re.S)
    return (text[: m.end()], text[m.end():]) if m else ("", text)


def reconvert(path_str: str, dry_run: bool) -> dict:
    from rerender_sec_stacked_tables import fresh_markdown, read_meta
    from md_cleanup.join_wrapped_paragraphs import join_wrapped
    from sec_tables_from_html import rebuild

    path = Path(path_str)
    if not path.is_absolute():
        path = REPO_ROOT / path
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    st = {"file": path.name, "stored_cells": two_value_cells(text)}
    if not st["stored_cells"]:
        st["status"] = "clean"
        return st
    head, body = split_frontmatter(text)
    meta = read_meta(text)
    cache = Path(os.environ["SEC_FRESH_CACHE"]) / f"{meta.get('accession_number')}.md" if os.environ.get("SEC_FRESH_CACHE") else None
    try:
        if cache and cache.exists():
            fresh = cache.read_text(encoding="utf-8")
        else:
            fresh, _ = fresh_markdown(meta)
            if cache:
                cache.write_text(fresh, encoding="utf-8")
    except Exception as e:  # network / EDGAR errors: leave the file, report
        st["status"] = f"error: {type(e).__name__}: {e}"[:200]
        return st
    new = head + "\n" + fresh.strip("\n") + "\n"
    new, _ = join_wrapped(new)
    # table headers from the filing HTML (sec2md writes "Line Item" / "Col 3" or folds header rows together)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / path.name
        tmp.write_bytes(new.encode("utf-8"))
        st["headers"] = {k: v for k, v in rebuild(tmp, check=False).items() if k not in ("md", "tables")}
        new = tmp.read_bytes().decode("utf-8")
    st["fresh_cells"] = two_value_cells(new)
    lost_nums = numbers(body, data_only=True) - numbers(new)
    w_old, w_new = words(body), words(new)
    lost_words = sum((w_old - w_new).values())
    st["lost_numbers"] = sum(lost_nums.values())
    st["lost_word_share"] = round(lost_words / max(1, sum(w_old.values())), 4)
    if "​" in new:  # zero-width spacer cells: the table rebuild went wrong, keep the stored file
        st["status"] = "skip: zero-width spacer cells"
    elif st["fresh_cells"] >= st["stored_cells"]:
        st["status"] = "skip: not better"
    elif lost_nums:
        st["status"] = "skip: numbers lost"
        st["examples"] = [k for k, _ in lost_nums.most_common(8)]
    elif st["lost_word_share"] > 0.005:
        st["status"] = "skip: words lost"
        st["examples"] = [k for k, _ in (w_old - w_new).most_common(8)]
    else:
        st["status"] = "would rewrite" if dry_run else "rewritten"
        if not dry_run:
            out = (new.replace("\n", "\r\n") if crlf else new).encode("utf-8")
            path.write_bytes(out)
            rel = path.relative_to(REPO_ROOT / "corpus" / "10-companies")
            mirror = REPO_ROOT / "data" / "extracted" / "md" / "companies" / rel
            if mirror.exists():
                mirror.write_bytes(new.encode("utf-8"))
    return st


def scan() -> list[str]:
    out = []
    for p in sorted((REPO_ROOT / "corpus" / "10-companies").rglob("*.md")):
        if two_value_cells(p.read_text(encoding="utf-8").replace("\r\n", "\n")):
            out.append(str(p.relative_to(REPO_ROOT)).replace("\\", "/"))
    return out


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    jobs = int(argv[argv.index("-j") + 1]) if "-j" in argv else 1
    if "--scan" in argv:
        files = scan()
        print("\n".join(files))
        print(f"{len(files)} files with two-value cells", file=sys.stderr)
        return 0
    files = scan() if "--all" in argv else [a for a in argv if a.endswith(".md")]
    tally: Counter = Counter()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for st in ex.map(lambda f: reconvert(f, dry), files):
            tally[st["status"].split(":")[0] if st["status"].startswith("error") else st["status"]] += 1
            print(json.dumps(st, ensure_ascii=False), flush=True)
    print(dict(tally), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
