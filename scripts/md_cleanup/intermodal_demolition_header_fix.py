"""Realign the header of Intermodal "Indicative Demolition Prices" tables (2021-2023).

The original parse wrote "| Markets | Markets | <date> | <date> | ±% | <y1> | <y2> |" over rows of
"| Bangladesh | 600 | 600 | 0.0% | 348 | 410 | 442 |": the label spans one column, not two, and the page prints
THREE yearly averages ("2020 2019 2018"), so every value sat one column to the left of its label. The fixed header is
"| Markets | <date> | <date> | ±% | <y1> | <y2> | <y2 - 1> |". A table is changed only when every data row has the
header's width, its second cell is a number, and the PDF prints the three years in a row. Only the header line changes.

    python scripts/md_cleanup/intermodal_demolition_header_fix.py [--apply]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intermodal_table_rebuild as R  # noqa: E402

MD_ROOT = R.ROOT / "data" / "extracted" / "md" / "intermodal"


def main() -> int:
    apply = "--apply" in sys.argv
    n_files = n_tables = skipped = 0
    for md in sorted(MD_ROOT.rglob("*.md")):
        raw = md.read_bytes().decode("utf-8")
        lines = raw.splitlines(keepends=True)
        bare = [l.rstrip("\r\n") for l in lines]
        hits = []
        for a, b in R.tables(bare):
            h = R.split_row(bare[a])
            if len(h) != 7 or h[:2] != ["Markets", "Markets"]:
                continue
            data = [R.split_row(l) for l in bare[a + 2:b]]
            data = [r for r in data if any(r[1:])]
            ys = [int(x) for x in h[5:] if re.fullmatch(r"\d{4}", x)]
            pdf = R.source_pdf(raw)
            text = " ".join(p.get_text() for p in pymupdf.open(pdf)) if pdf else ""
            ok = (data and all(len(r) == 7 and re.fullmatch(r"[\d,.]+", r[1]) for r in data) and len(ys) == 2
                  and re.search(rf"{ys[0]}\s+{ys[1]}\s+{ys[1] - 1}", text))
            if not ok:
                skipped += 1
                print(f"skip  {md.name} line {a + 1}")
                continue
            hits.append((a, ["Markets"] + h[2:] + [str(ys[1] - 1)]))
        if not hits:
            continue
        for a, hdr in hits:
            nl = "\r\n" if lines[a].endswith("\r\n") else "\n"
            lines[a] = "| " + " | ".join(hdr) + " |" + nl
        n_files += 1
        n_tables += len(hits)
        print(f"{len(hits)}  {md.relative_to(R.ROOT).as_posix()}")
        if apply:
            md.write_bytes("".join(lines).encode("utf-8"))
    print(f"{n_tables} headers in {n_files} files {'fixed' if apply else '(dry run)'}; {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
