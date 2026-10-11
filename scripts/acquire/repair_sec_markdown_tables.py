#!/usr/bin/env python3
"""
scripts/acquire/repair_sec_markdown_tables.py

Deterministic (no LLM) post-processor for the SEC filings corpus in
corpus/10-companies/. It fixes two converter defects and leaves every other
byte of the file untouched:

1. Broken table rows. A row that starts with "|" but whose cell text contained a
   newline is continued on the following line(s), e.g.

       | Common Shares,
       par value $0.01 per share | SBLK | Nasdaq
       Global Select Market |

   The continuation lines are joined onto the row with a single space.

2. Bullet lists rendered as two-column tables ("| . | text |"). A table block in
   which every row is a bullet marker cell plus one text cell is turned back into
   "- text" list items. Mixed blocks (a real header row, data rows, bullet matrices
   such as "| bullet | bullet |") are never touched.

Safety: every repaired file is checked with assert_text_preserved(): apart from
the joined newlines, the table pipes and the bullet markers, the sequence of
non-whitespace characters is identical before and after.

Usage:
    python scripts/acquire/repair_sec_markdown_tables.py --dry-run
    python scripts/acquire/repair_sec_markdown_tables.py                 # all corpus files
    python scripts/acquire/repair_sec_markdown_tables.py path/to/a.md ...  # specific files
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_DIR = REPO_ROOT / "corpus" / "10-companies"

# Maximum number of physical lines a single table row may span.
MAX_ROW_SPAN = 60

BULLET_CHARS = "·•●▪◦"  # middle dot, bullet, black circle, small square, white bullet
BULLET_ROW_RE = re.compile(r"^\|\s*[" + BULLET_CHARS + r"]\s*\|(?P<rest>.*\|)\s*$")
SEPARATOR_ROW_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")
WORD_CHAR_RE = re.compile(r"\w")


def _is_open_row(line: str) -> bool:
    """A table row that starts a cell run but does not close with a trailing pipe."""
    stripped = line.rstrip()
    return stripped.startswith("|") and not stripped.endswith("|")


def join_continuation_rows(lines: List[str]) -> Tuple[List[str], int]:
    """
    Join rows that were split by a newline inside a cell.
    Returns (new_lines, number_of_rows_joined).
    A row is only joined when a closing line (ending in "|") is found within
    MAX_ROW_SPAN lines without meeting another table row first; otherwise the
    lines are left exactly as they were.
    """
    out: List[str] = []
    joined = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not _is_open_row(line):
            out.append(line)
            i += 1
            continue

        parts = [line.rstrip()]
        closed_at: Optional[int] = None
        j = i + 1
        while j < n and j - i <= MAX_ROW_SPAN:
            nxt = lines[j]
            if not nxt.strip():
                j += 1
                continue
            if nxt.startswith("|"):
                break
            parts.append(nxt.strip())
            if nxt.rstrip().endswith("|"):
                closed_at = j
                break
            j += 1

        if closed_at is None:
            out.append(line)
            i += 1
            continue

        out.append(" ".join(parts))
        joined += 1
        i = closed_at + 1
    return out, joined


def _bullet_text(line: str) -> Optional[str]:
    """
    Return the text of a "| bullet | text |" row (trailing empty cells allowed),
    or None if the row is not one.
    """
    m = BULLET_ROW_RE.match(line)
    if not m:
        return None
    cells = UNESCAPED_PIPE_RE.split(m.group("rest").rstrip()[:-1])
    text = cells[0].strip()
    if not WORD_CHAR_RE.search(text):
        return None  # e.g. "| bullet | bullet |" matrix cells
    if any(c.strip() for c in cells[1:]):
        return None  # a real multi-column row
    return text


def convert_bullet_tables(lines: List[str], marker: str = "- ") -> Tuple[List[str], int]:
    """
    Convert "| bullet | text |" rows into list items. Returns (new_lines, rows_converted).

    A block of consecutive table lines that contains a separator row is a real
    Markdown table, so it is only converted when every row in it is a bullet row.
    A block without a separator row never renders as a table; there the bullet
    rows are converted one by one and any other row is left as it was.
    """
    out: List[str] = []
    converted = 0
    i = 0
    n = len(lines)
    while i < n:
        if not lines[i].startswith("|"):
            out.append(lines[i])
            i += 1
            continue
        j = i
        while j < n and lines[j].startswith("|"):
            j += 1
        block = lines[i:j]
        texts = [_bullet_text(b) for b in block]
        has_separator = any(SEPARATOR_ROW_RE.match(b) for b in block)
        if has_separator and not all(t is not None for t in texts):
            out.extend(block)
        else:
            for original, text in zip(block, texts):
                if text is None:
                    out.append(original)
                else:
                    out.append(marker + text)
                    converted += 1
        i = j
    return out, converted


def repair_markdown(text: str, marker: str = "- ") -> Tuple[str, Dict[str, int]]:
    """Repair broken table rows and bullet tables. Everything else is byte-identical."""
    lines = text.split("\n")
    lines, joined = join_continuation_rows(lines)
    lines, bullets = convert_bullet_tables(lines, marker)
    return "\n".join(lines), {"rows_joined": joined, "bullets_converted": bullets}


def _nonws_stream(text: str) -> str:
    """Non-whitespace characters with table pipes and bullet markers removed."""
    text = text.replace("|", "")
    for ch in BULLET_CHARS:
        text = text.replace(ch, "")
    return "".join(text.split())


def assert_text_preserved(before: str, after: str, bullets_converted: int) -> None:
    """
    Raise AssertionError unless `after` differs from `before` only by joined
    newlines, removed table pipes/bullet markers and the added "- " list markers.
    """
    before_stream = _nonws_stream(before)
    after_stream = _nonws_stream(after)
    # 1. Same text in the same order once the list markers are left out.
    marker_free, _ = repair_markdown(before, marker="")
    assert _nonws_stream(marker_free) == before_stream, "non-whitespace text changed by repair"
    # 2. The output carries exactly one extra "-" per converted bullet row, and nothing is lost.
    lost = Counter(before_stream) - Counter(after_stream)
    added = Counter(after_stream) - Counter(before_stream)
    assert not lost, f"characters lost by repair: {dict(lost)}"
    expected_added = Counter({"-": bullets_converted}) if bullets_converted else Counter()
    assert added == expected_added, f"unexpected characters added by repair: {dict(added)}"


def repair_file(path: Path, dry_run: bool = False) -> Dict[str, int]:
    """Repair one file in place (unless dry_run). Returns the repair stats."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        before = f.read()
    # Working-tree files are CRLF on Windows (autocrlf) and LF on Linux: repair on LF, restore the style.
    crlf = "\r\n" in before
    work = before.replace("\r\n", "\n") if crlf else before
    after, stats = repair_markdown(work)
    if after == work:
        return stats
    assert_text_preserved(work, after, stats["bullets_converted"])
    # Idempotency: a second pass must be a no-op.
    again, _ = repair_markdown(after)
    assert again == after, f"repair is not idempotent for {path}"
    if not dry_run:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(after.replace("\n", "\r\n") if crlf else after)
    return stats


def iter_corpus_files(root: Path = CORPUS_DIR) -> Iterable[Path]:
    return sorted(root.glob("*/*/*.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair broken tables / bullet tables in SEC corpus Markdown.")
    ap.add_argument("paths", nargs="*", help="Markdown files (default: the whole corpus/10-companies tree)")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = ap.parse_args()

    files = [Path(p) for p in args.paths] if args.paths else list(iter_corpus_files())
    changed = 0
    totals = Counter()
    for path in files:
        stats = repair_file(path, dry_run=args.dry_run)
        if stats["rows_joined"] or stats["bullets_converted"]:
            changed += 1
            totals.update(stats)
    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {changed} of {len(files)} files: "
          f"{totals['rows_joined']} rows joined, {totals['bullets_converted']} bullet rows converted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
