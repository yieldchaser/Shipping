"""Agora - repair the misfiled 2021 W52 issue's issue_date (PER-SOURCE, idempotent).

DEFECT (measured 2026-10-08): `corpus/01-brokers/agora/2022/
agora_2022_W52_AGORA.-Week-52.-2021.-Snapshot-of-Commercial-Indicators.pdf` is the
publisher's **Week 52 / 2021** report (cover: "Week 52 / 2021", "(27-31 December)"),
but it was collected under a 2022_ W52 filename and the original stacker dated it from
the filename -> 2022-12-30. Its 38 rows therefore sat on the wrong YEAR.

Ground truth (three independent signals agree it is the 2021 report):
  * cover line   : "Week 52 / 2021" / "(27-31 December)"  -> Friday of ISO wk52 2021
  * content      : Rotterdam bunkers IFO380/VLSFO/MGO = 447/571/682 (Dec-2021 level,
                   one week on from 2021-12-24's 432/549/656); utterly unlike the
                   2022 W52 doc's 400/559/886 (Dec-2022 levels)
  * series shape : the 2021 series steps W44..W51 (last 2021-12-24) then jumps to
                   2022-01-07 - W52/2021 is the single missing week.

Fix = set those 38 rows' issue_date to 2021-12-31 (Friday of ISO wk52 2021). report_week
stays 52. No other column, no other row, no EOL/BOM changes.

  python scripts/extract/publishers/fix_agora_w52_2021.py --dry-run
  python scripts/extract/publishers/fix_agora_w52_2021.py
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
CSV = ROOT / "data" / "extracted" / "series" / "agora_indicators_series.csv"
PDF = ROOT / "corpus" / "01-brokers" / "agora" / "2022" / (
    "agora_2022_W52_AGORA.-Week-52.-2021.-Snapshot-of-Commercial-Indicators.pdf")
DOC_SUBSTR = "agora_2022_W52_AGORA.-Week-52.-2021.-Snapshot-of-Commercial-Indicators.pdf"
OLD_DATE = "2022-12-30"
NEW_DATE = "2021-12-31"
EXPECT_ROWS = 38


def cover_friday(path: Path) -> tuple[str, int]:
    doc = pymupdf.open(path)
    txt = " ".join(doc[0].get_text().split())
    doc.close()
    assert "Week 52 / 2021" in txt, f"cover no longer prints 'Week 52 / 2021': {txt[:200]!r}"
    fri = dt.date.fromisocalendar(2021, 52, 5)  # Friday of ISO week 52 2021
    return fri.isoformat(), 52


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    fri, wk = cover_friday(PDF)
    assert fri == NEW_DATE and wk == 52, (fri, wk)
    print(f"cover ground truth: Week 52 / 2021 -> issue_date {fri} (report_week 52)")

    raw = CSV.read_bytes()
    crlf, lf, bom = raw.count(b"\r\n"), raw.count(b"\n"), raw[:3] == b"\xef\xbb\xbf"
    lines = raw.split(b"\n")

    old_prefix = f"{OLD_DATE},{wk},".encode()
    new_prefix = f"{NEW_DATE},{wk},".encode()
    sel = [i for i, ln in enumerate(lines) if DOC_SUBSTR.encode() in ln]
    stale = [i for i in sel if lines[i].startswith(old_prefix)]
    print(f"rows sourced from the misfiled doc: {len(sel)} (expected {EXPECT_ROWS})")
    print(f"  of those still on {OLD_DATE}: {len(stale)}")
    assert len(sel) == EXPECT_ROWS, "row count from this doc changed - re-measure"
    if not stale:
        print("idempotent: nothing stale, no write.")
        return 0
    assert len(stale) == EXPECT_ROWS, "only some rows carry the old date - refuse"

    before_total = len([ln for ln in lines if ln.strip()])
    newraw = raw
    for i in stale:
        newraw = newraw.replace(lines[i].rstrip(b"\r"), lines[i].rstrip(b"\r").replace(old_prefix, new_prefix, 1), 1)
    print(f"replacements: {len(stale)} rows {OLD_DATE} -> {NEW_DATE}")

    changed = sum(1 for x, y in zip(lines, newraw.split(b"\n")) if x != y)
    assert changed == EXPECT_ROWS, f"unexpected changed-line count {changed}"
    assert newraw.count(b"\r\n") == crlf and newraw.count(b"\n") == lf
    assert (newraw[:3] == b"\xef\xbb\xbf") == bom
    assert len([ln for ln in newraw.split(b"\n") if ln.strip()]) == before_total

    if a.dry_run:
        print("dry-run: no write.")
        return 0
    CSV.write_bytes(newraw)
    after = CSV.read_bytes()
    assert after.count(b"\r\n") == crlf and after.count(b"\n") == lf and (after[:3] == b"\xef\xbb\xbf") == bom
    assert after.count(new_prefix) >= EXPECT_ROWS and after.count(old_prefix) == 85 - EXPECT_ROWS
    print("written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
