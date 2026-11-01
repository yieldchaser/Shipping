#!/usr/bin/env python3
"""
scripts/audit/detect_sec_stacked_tables.py

Lists the SEC filing Markdowns (corpus/10-companies) whose financial-statement rows are stacked into
one table cell. The old converter folded neighbouring columns together (sec2md output went through
standardize_sec_markdown.repair_table_block, whose sub-item merge treated "(814)" as an "(a)" marker),
which leaves cells like

    | Net operating revenue Cost of goods sold ... | Notes 3(b) 4(a) | 2026 2025 54,462 56,701 (40,798) ... |
    | Gross profit |  | 13,664 20,624 | 46,100 51,610 |

Two kinds are reported:

  stacked_cells   a table cell holding >= MIN_FIN financial tokens (thousands comma, decimals, brackets, $, %;
                  years excluded), two of them adjacent: the values of several rows or columns in one cell
  pdf_text_line   a non-table line of >= PDF_LINE_CHARS characters that holds >= PDF_LINE_NUMBERS numeric
                  tokens and is >= PDF_LINE_DENSITY numbers (or >= PDF_LINE_HUGE numbers): a PDF-origin exhibit
                  that came out as one text line instead of a table

Usage:
    python scripts/audit/detect_sec_stacked_tables.py                      # whole corpus, prints the summary
    python scripts/audit/detect_sec_stacked_tables.py --out list.json      # also writes the list (json)
    python scripts/audit/detect_sec_stacked_tables.py --paths a.md b.md    # only these files
    python scripts/audit/detect_sec_stacked_tables.py --list               # one path per line
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_DIR = REPO_ROOT / "corpus" / "10-companies"

MIN_FIN = 3
MIN_RUN = 4
PDF_LINE_CHARS = 1500
PDF_LINE_NUMBERS = 100
PDF_LINE_DENSITY = 0.3
PDF_LINE_HUGE = 500

# A numeric token: 1,234 / 12.5 / (814) / $1,234 / 12% ; trailing-comma list items such as "14," do not match.
NUM_TOKEN = re.compile(
    r"^\(?\x5c?\$?\(?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?%?\)?$|^\(?\d+(?:\.\d+)?\)?%$"
)
# A financial token carries a statement-number marker: thousands comma, decimals, brackets, $ or %.
# Plain integers (phone numbers, ABNs, years, note refs) never count on their own.
FIN_TOKEN = re.compile(
    r"^\(?\x5c?\$?\(?(?:\d{1,3}(?:,\d{3})+|\d+\.\d+)\)?%?\)?$|^\(\d{3,}\)$|^\(?\x5c?\$\d+\)?$|^\(?\d+(?:\.\d+)?\)?%$"
)
FOOTNOTE_TOKEN = re.compile(r"^\(\d{1,2}\)$")
YEAR_TOKEN = re.compile(r"^\(?(?:19|20)\d\d\)?$")


def is_number(token: str) -> bool:
    return bool(NUM_TOKEN.match(token)) and not YEAR_TOKEN.match(token)


def is_financial(token: str) -> bool:
    return bool(FIN_TOKEN.match(token)) and not YEAR_TOKEN.match(token)


def stacked_cell(cell: str) -> bool:
    """
    A cell holding the values of several rows/columns: >= MIN_FIN financial tokens with two adjacent, or a run of
    >= MIN_RUN adjacent financial / footnote-bracket tokens ("(1) (5) (1) (7)").
    """
    toks = cell.split()
    fin = [is_financial(t) for t in toks]
    if sum(fin) >= MIN_FIN and any(a and b for a, b in zip(fin, fin[1:])):
        return True
    run = 0
    for t, f in zip(toks, fin):
        run = run + 1 if (f or FOOTNOTE_TOKEN.match(t)) else 0
        if run >= MIN_RUN:
            return True
    return False


def analyse(text: str) -> dict:
    """Return {'stacked_cells': n, 'pdf_text_line': n, 'example': str} for one document."""
    lines = text.replace("\r\n", "\n").split("\n")
    stacked = 0
    pdf_lines = 0
    example = ""
    for i, line in enumerate(lines):
        if line.startswith("|"):
            for cell in line.split("|")[1:-1]:
                if stacked_cell(cell):
                    stacked += 1
                    if not example:
                        example = line[:240]
        elif len(line) >= PDF_LINE_CHARS:
            toks = line.split()
            nums = sum(is_number(t) for t in toks)
            if nums >= PDF_LINE_NUMBERS and (nums / len(toks) >= PDF_LINE_DENSITY or nums >= PDF_LINE_HUGE):
                pdf_lines += 1
                if not example:
                    example = line[:240]
    return {"stacked_cells": stacked, "pdf_text_line": pdf_lines, "example": example}


def iter_files(paths):
    if paths:
        return [Path(p) for p in paths]
    return sorted(CORPUS_DIR.glob("*/*/*.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", nargs="*", help="Markdown files (default: all of corpus/10-companies)")
    ap.add_argument("--out", help="write the full list as json")
    ap.add_argument("--list", action="store_true", help="print one repo-relative path per line")
    args = ap.parse_args()

    files = iter_files(args.paths)
    hits = {}
    for path in files:
        res = analyse(path.read_text(encoding="utf-8", errors="replace"))
        if res["stacked_cells"] or res["pdf_text_line"]:
            try:
                key = path.resolve().relative_to(REPO_ROOT).as_posix()
            except ValueError:
                key = path.as_posix()
            hits[key] = res

    if args.out:
        Path(args.out).write_text(json.dumps(hits, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.list:
        for key in sorted(hits):
            print(key)
    else:
        by_ticker = {}
        for key in hits:
            ticker = key.split("/")[2] if key.startswith("corpus/") else "?"
            by_ticker[ticker] = by_ticker.get(ticker, 0) + 1
        pdf = sum(1 for r in hits.values() if r["pdf_text_line"])
        print(f"scanned {len(files)} files: {len(hits)} with stacked cells or pdf text lines "
              f"({pdf} pdf_text_line)")
        print("by ticker: " + ", ".join(f"{k} {v}" for k, v in sorted(by_ticker.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
