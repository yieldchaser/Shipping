"""Replace Intermodal "tables" that are a visual guess of the Baltic indices chart with a one-line chart note.

They are header-only tables (no body rows) whose header cells are a run of chart dates with round numbers glued on
("23/May/22 ... | BCI 3000 2800 3100 1000 ..."): an earlier LLM pass read the 1-year Baltic indices chart by eye.
The Baltic indices are public data, kept elsewhere in this repo, so the chart is not estimated (owner rule,
2026-10-11). Only these two lines change; everything else in the file is byte-identical.

    python scripts/md_cleanup/intermodal_chart_guess_note.py [--apply]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "intermodal"
SEP = re.compile(r"^\|\s*:?-{3}")
DATE = re.compile(r"\b\d{1,2}/(?:[A-Z][a-z]{2}|\d{2})/\d{2}\b")
NOTE = ("> **Chart (not transcribed):** Baltic indices, 1-year trend. The report prints no numbers for it; the "
        "index values are public Baltic Exchange data.")


def main() -> int:
    apply = "--apply" in sys.argv
    n_files = n_tables = 0
    for md in sorted(MD_ROOT.rglob("*.md")):
        raw = md.read_bytes().decode("utf-8")
        lines = raw.splitlines(keepends=True)
        out, i, hit = [], 0, 0
        while i < len(lines):
            a = lines[i]
            b = lines[i + 1] if i + 1 < len(lines) else ""
            c = lines[i + 2] if i + 2 < len(lines) else ""
            prev = out[-1] if out else ""
            if (a.startswith("|") and SEP.match(b) and not c.startswith("|") and not prev.startswith("|")
                    and len(DATE.findall(a)) >= 6 and re.search(r"\b(BCI|BPI|BSI|BHSI|BDI|BCCI)\b|\|\s*\d{1,2}/", a)):
                nl = "\r\n" if a.endswith("\r\n") else "\n"
                out.append(NOTE + nl)
                i += 2
                hit += 1
                continue
            out.append(a)
            i += 1
        if hit:
            n_files += 1
            n_tables += hit
            print(f"{hit}  {md.relative_to(ROOT).as_posix()}")
            if apply:
                md.write_bytes("".join(out).encode("utf-8"))
    print(f"{n_tables} chart-guess tables in {n_files} files {'replaced' if apply else '(dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
