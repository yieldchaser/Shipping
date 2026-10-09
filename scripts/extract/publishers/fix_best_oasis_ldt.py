#!/usr/bin/env python3
"""Best Oasis deals series - LDT separator fix (per-source, idempotent).

The publisher prints the LDT column with MIXED separators: most rows ISO
thousands ("8,015") but some EU period-thousands ("1.995" = 1,995 LDT).
run_best_oasis_demolition.py used to keep the dot as a decimal, so EL YOUSSEF
(2024-03-01) shipped ldt=1.995 instead of 1995. Code is fixed; this repairs the
delivered CSVs. Ground truth (two independent publishers): best_oasis
2024-03-01 page 7 prints "1.995" beside "8,015"/"23,038"; intermodal 2024 W09
lists the same vessel as ldt 1995.

Rule: within this file's `ldt` column, a token that is all-in-threes around
dots ("1.995", "23.038") is a thousands separator (LDT is integer tonnes), so
strip the dots. Idempotent: a second run finds nothing to change.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FILES = [
    REPO / "data/extracted/series/best_oasis_deals_series.csv",
    REPO / "data/extracted/series/hellenic_best_oasis_deals_series.csv",
]
SHAPE = re.compile(r'^\d{1,3}(?:\.\d{3})+$')

def main(apply: bool) -> int:
    total = 0
    for p in FILES:
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        eol = "\r\n" if "\r\n" in text else "\n"
        bom = "\ufeff" if text.startswith("\ufeff") else ""
        lines = text.split(eol)
        header = lines[0].lstrip("\ufeff").split(",")
        li = header.index("ldt")
        # match the column's OWN form: this tier stores LDT as "<int>.0" floats
        dot0 = sum(1 for ln in lines[1:] if ln and
                   len(ln.split(",")) > li and re.match(r'^\d+\.0$', ln.split(",")[li]))
        as_float = dot0 > sum(1 for ln in lines[1:] if ln) * 0.5
        changed = 0
        out = [lines[0]]
        for line in lines[1:]:
            if not line:
                out.append(line)
                continue
            cells = line.split(",")
            if li < len(cells) and SHAPE.match(cells[li]):
                ov = cells[li]
                iv = int(ov.replace(".", ""))
                cells[li] = f"{iv}.0" if as_float else str(iv)
                changed += 1
                if changed <= 3:
                    print(f"  {p.name}: ldt {ov} -> {cells[li]}  ({cells[0]} {cells[1]})")
                line = ",".join(cells)
            out.append(line)
        if changed == 0:
            print(f"{p.name}: idempotent - nothing stale, no write")
            continue
        new_text = bom + eol.join(out)
        assert new_text.count(eol) == text.count(eol), "line count changed"
        if apply:
            p.write_bytes(new_text.encode("utf-8"))
            print(f"{p.name}: wrote {changed} cell(s)")
        else:
            print(f"{p.name}: DRY-RUN would change {changed} cell(s)")
        total += changed
    print(f"total cells changed: {total}")
    return 0

if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
