"""Gibson: embedded chart tables must not hold data from after the issue.

The weekly pages were archived years after publication, and some of their Chart.js tables are live
(shared across reports and refreshed on the site): the 2023-10-06 "US Dollar Strength" table holds only
2026 values. For each "Chart data as embedded in the report" table with a date first column:

  - no row dated on or before the issue date  -> the table is replaced by a note (not this issue's chart);
  - the same chart (identical header) also appears in another Gibson MD -> a shared live chart: rows dated
    after the issue are dropped;
  - otherwise (an article's own chart, e.g. a production outlook running to December) -> kept as is.

Date labels are dd/mm/yyyy or mm/dd/yyyy as the page embedded them; the reading that makes the column
ascend is used. Rows, cells and surrounding text are otherwise untouched.

    python scripts/md_cleanup/gibson_live_chart_trim.py [--apply] [files...]
"""
from __future__ import annotations

import collections
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "gibson"
LEAD = "Chart data as embedded in the report:"
NOTE = ("> **Chart (not transcribed):** the chart data in the archived page postdates this issue "
        "(a live chart refreshed after publication).")
TABLE = re.compile(r"(?:^\|[^\n]*\n)+", re.M)
DMY = re.compile(r"^\| (\d{1,2})/(\d{1,2})/(\d{4}) \|")


def dates(rows: list[str]) -> list[date | None] | None:
    raw = [DMY.match(r) for r in rows]
    if not raw or not all(raw):
        return None
    for day, month in ((1, 2), (2, 1)):     # group numbers: dd/mm first, then mm/dd
        try:
            ds = [date(int(m.group(3)), int(m.group(month)), int(m.group(day))) for m in raw]
        except ValueError:
            continue
        if all(a <= b for a, b in zip(ds, ds[1:])):
            return ds
    return None


def charts(text: str):
    """(start, end, header, rows) of each embedded chart table."""
    for m in TABLE.finditer(text):
        if text[:m.start()].rstrip().endswith(LEAD):
            lines = m.group(0).rstrip("\n").split("\n")
            yield m.start(), m.end(), lines[0], lines


def process(text: str, issue: date, shared: set[str]) -> tuple[str, list[str]]:
    out, pos, log = [], 0, []
    for s, e, head, lines in charts(text):
        ds = dates(lines[2:])
        if ds is None:
            # labels that do not ascend in either reading (e.g. 718 rows all '21/01/2026'): broken axis labels.
            # If every label lies after the issue, the table is not this issue's chart.
            ms = [DMY.match(r) for r in lines[2:]]
            if ms and all(ms) and all(int(m.group(3)) > issue.year for m in ms):
                ds = [date(int(m.group(3)), 1, 1) for m in ms]
            else:
                continue
        if ds[-1] <= issue:
            continue
        keep = [r for r, d in zip(lines[2:], ds) if d <= issue]
        if not keep:
            lead = text.rfind(LEAD, 0, s)
            out.append(text[pos:lead])
            out.append(NOTE + "\n")
            log.append(f"NOTE  {head[:60]} ({len(ds)} rows, {ds[0]}..{ds[-1]})")
        elif head in shared:
            out.append(text[pos:s])
            out.append("\n".join(lines[:2] + keep) + "\n")
            log.append(f"TRIM  {head[:60]} -{len(ds) - len(keep)} rows after {issue}")
        else:
            continue
        pos = e
    out.append(text[pos:])
    return "".join(out), log


def main() -> int:
    apply = "--apply" in sys.argv
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or sorted(MD_ROOT.rglob("*.md"))
    every = sorted(MD_ROOT.rglob("*.md"))
    seen = collections.Counter()
    for p in every:
        t = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        seen.update({h for _, _, h, _ in charts(t)})
    shared = {h for h, n in seen.items() if n > 1}
    n = 0
    for p in files:
        raw = p.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        t = raw.replace("\r\n", "\n")
        m = re.search(r"""^issue_date:\s*["']?(\d{4})-(\d\d)-(\d\d)""", t, re.M)
        if not m:
            continue
        new, log = process(t, date(*map(int, m.groups())), shared)
        if not log:
            continue
        n += 1
        print(p.name)
        for l in log:
            print("   ", l)
        if apply:
            p.write_bytes(new.replace("\n", nl).encode("utf-8"))
    print(f"{n} MDs{'' if apply else ' (dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
