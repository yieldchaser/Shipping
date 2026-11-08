"""Put a numbered item's number back on its label where the conversion split them onto separate lines:

    1.                              1. Strategic Asset Management
    Strategic Asset Management  ->  2. Financial Management
    2.
    Financial Management

GitHub renders the left side as empty list items with the labels between them. Only proven runs are joined:
at least two consecutive items numbered N, N+1, ... each written as a bare "N." line followed directly (or after
one blank line) by a one-line label that is not itself a number, heading, table row or list item. A bare number
anywhere else (a year or page that wrapped to its own line, "1972.") is left alone. Text is unchanged apart from
the line breaks / blank lines between a number and its label (checked).

    python scripts/md_cleanup/join_lone_list_numbers.py corpus/books [--apply]
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

NUM = re.compile(r"^\s*(\d{1,2})\.\s*$")
NOT_LABEL = re.compile(r"^\s*(?:#|\||>|[-*+]\s|\d+[.)](?:\s|$)|<!--|```)")


def _label_at(lines: list[str], i: int) -> int | None:
    """Index of the label belonging to the bare number at line i, or None."""
    j = i + 1
    if j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines) and lines[j].strip() and not NOT_LABEL.match(lines[j]):
        nxt = lines[j + 1] if j + 1 < len(lines) else ""
        # a one-line label: the next line is blank or the next bare number
        if not nxt.strip() or NUM.match(nxt):
            return j
    return None


def join_numbers(text: str) -> tuple[str, int]:
    crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")
    items: dict[int, tuple[int, int]] = {}            # number line -> (number, label line)
    for i, l in enumerate(lines):
        m = NUM.match(l)
        if m:
            j = _label_at(lines, i)
            if j is not None:
                items[i] = (int(m.group(1)), j)
    # keep items that belong to a run N, N+1 (the next item starts right after this one's label)
    keep: set[int] = set()
    for i, (n, j) in items.items():
        nxt = next((k for k in range(j + 1, min(j + 3, len(lines))) if lines[k].strip()), None)
        if nxt in items and items[nxt][0] == n + 1:
            keep.update((i, nxt))
    out, skip, joins = [], set(), 0
    for i, l in enumerate(lines):
        if i in skip:
            continue
        if i in keep:
            n, j = items[i]
            out.append(f"{n}. {lines[j].strip()}")
            skip.update(range(i + 1, j + 1))
            joins += 1
            continue
        out.append(l)
    new = "\n".join(out)
    assert Counter(re.sub(r"\s+", "", new)) == Counter(re.sub(r"\s+", "", "\n".join(lines))), "text changed"
    return (new.replace("\n", "\r\n") if crlf else new), joins


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    total = files = 0
    for root in [a for a in argv if not a.startswith("--")]:
        for p in ([Path(root)] if Path(root).is_file() else sorted(Path(root).rglob("*.md"))):
            raw = p.read_bytes().decode("utf-8")
            new, n = join_numbers(raw)
            if n:
                files += 1; total += n
                print(f"  {p.as_posix()}: {n}")
                if apply:
                    p.write_bytes(new.encode("utf-8"))
    print(f"{'applied' if apply else 'dry run'}: {total} items in {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
