"""Intermodal: replace chart tables read by eye with a one-line note.

The Intermodal PDFs draw their trend charts (Baltic indices, average T/C rates, WS rates, demolition and
newbuilding price histories) as graphics; the report prints no values for them. The older LlamaParse runs
transcribed each chart into a table by eye: the values are axis ticks or guesses (e.g. 2/Jul/20 BCI 4100,
BDI 4100), and only 62% of their numbers exist anywhere in the PDF against 99.2% for the printed tables.

A chart table is recognised by its first column: dates (2/Jul/20, Jul-20) in at least 80% of its rows, or
by sitting under a "(N-Year Trend)" heading. A heading that only carries the chart table is folded into the
note; prose under the heading is kept. Printed tables (first column = vessel, route, country, ...) and the
text around them stay byte-identical.

    python scripts/md_cleanup/intermodal_chart_note.py [--apply] [files...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "intermodal"
NOTE = "> **Chart (not transcribed):** {title}. The report prints no values for it."
DATE = re.compile(r"^\s*(?:\d{1,2}[/ -])?[A-Za-z]{3}[/ -]?'?\d{2,4}\s*$")
TREND = re.compile(r"\(\d+-Year Trend\)", re.I)
BLOCK = re.compile(r"(?:^\|[^\n]*\n?)+", re.M)
HEAD = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)


def is_chart(table: str, heading: str, directly_under: bool) -> bool:
    rows = [r for r in table.strip().splitlines()[2:] if r.strip()]
    if len(rows) < 2:
        return False
    first = [r.strip().strip("|").split("|")[0] for r in rows]
    if sum(bool(DATE.match(c)) for c in first) >= 0.8 * len(rows):
        return True
    # A "(N-Year Trend)" heading names the chart right below it. A later table under the same heading
    # (e.g. the printed TC Rates table that has no heading of its own) is not that chart.
    # A printed week-on-week table (e.g. Baltic Indices: '01/07/2022 Index | 24/06/2022 Index') carries exactly
    # two distinct dates in its header; a transposed chart carries one per month.
    header_dates = set(re.findall(r"\d{1,2}[/-][A-Za-z0-9]{2,3}[/-]\d{2,4}", table.splitlines()[0]))
    return bool(TREND.search(heading)) and directly_under and len(header_dates) != 2


def process(text: str) -> tuple[str, list[str]]:
    nl = "\r\n" if "\r\n" in text else "\n"
    t = text.replace("\r\n", "\n")
    out, pos, notes = [], 0, []
    for m in BLOCK.finditer(t):
        heads = list(HEAD.finditer(t, 0, m.start()))
        h = heads[-1] if heads else None
        title = h.group(2).strip().strip("*").strip() if h else ""
        between = t[h.end():m.start()] if h else None
        if not is_chart(m.group(0), title, bool(h) and between.strip() == ""):
            continue
        note = NOTE.format(title=title or "untitled chart")
        if h and between.strip() == "" and h.start() >= pos:   # heading carries only this table: fold it
            start = h.start()
        else:
            start = m.start()
        out.append(t[pos:start])
        pos = m.end()
        out.append(note + "\n" + ("" if t[pos:pos + 1] in ("\n", "") else "\n"))
        notes.append(title)
    out.append(t[pos:])
    new = "".join(out)
    return (new.replace("\n", nl) if notes else text), notes


def main() -> int:
    apply = "--apply" in sys.argv
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or sorted(MD_ROOT.rglob("*.md"))
    n_files = n_notes = 0
    for p in files:
        raw = p.read_bytes().decode("utf-8")
        fm = re.match(r"---\r?\n.*?\r?\n---\r?\n", raw, re.S)
        head, body = (raw[:fm.end()], raw[fm.end():]) if fm else ("", raw)
        new_body, notes = process(body)
        if not notes:
            continue
        n_files += 1
        n_notes += len(notes)
        if apply:
            p.write_bytes((head + new_body).encode("utf-8"))
    print(f"{n_files} MDs, {n_notes} chart tables -> notes{'' if apply else ' (dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
