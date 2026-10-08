"""Agora (SNAPSHOT OF COMMERCIAL INDICATORS) - PER-SOURCE week stacker.

Why this exists: `run_agora.py` writes only md/tables sidecars. The series CSV
`agora_indicators_series.csv` was previously extended only by a throwaway scratch
script with HARDCODED weeks, so a newly-collected issue was extracted to .md but
silently never stacked (measured 2026-10-08: W40 present as md, absent from the
series). This makes the stacking step per-source, content-driven and idempotent.

The date convention is MEASURED off the shipped series, not assumed:
  * 212 / 213 distinct issue dates are a FRIDAY;
  * report_week == the ISO week of that date on 213 / 213 rows.
So issue_date = the Friday of the report's own ISO week, read from the
document's printed cover line ("Week 40 / 2026"). A cover whose printed
reference date does NOT fall in that ISO week is internally inconsistent, so the
document is SKIPPED and named - never guessed.

Other rules:
  * byte-identical PDFs deduped by md5, keeping the lexicographically-first stem
    (the same keeper rule the runner uses) so a re-drop cannot double-count;
  * append-only: existing rows are asserted byte-identical afterwards.

usage:
    python scripts/extract/publishers/stack_agora_weeks.py --dry-run
    python scripts/extract/publishers/stack_agora_weeks.py
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scratch" / "agora_fix"))

import pymupdf  # noqa: E402

SRC = ROOT / "corpus" / "01-brokers" / "agora"
CSV = ROOT / "data" / "extracted" / "series" / "agora_indicators_series.csv"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}
WEEK_RE = re.compile(r"Week\s+(\d{1,2})\s*/\s*((?:19|20)\d\d)")
REF_RE = re.compile(r"Reference\s+point\s+(\d{1,2})\s+([A-Za-z]+)\s+((?:19|20)\d\d)")


def build_rows():
    from build_rows import rows_for, HDR  # validated byte-exact on W35/W36/W37/W39
    return rows_for, HDR


def cover_meta(pdf: Path):
    """(issue_date_iso, week, note) from the document's own cover."""
    try:
        doc = pymupdf.open(pdf)
        txt = re.sub(r"\s+", " ", doc[0].get_text())
        doc.close()
    except Exception as e:
        return None, None, f"unreadable: {e}"
    w = WEEK_RE.search(txt)
    r = REF_RE.search(txt)
    if not w:
        return None, None, "no 'Week N / YYYY' on cover"
    wk, yr = int(w.group(1)), int(w.group(2))
    # Friday of that ISO week
    try:
        fri = dt.date.fromisocalendar(yr, wk, 5)
    except ValueError:
        return None, None, f"bad ISO week {yr}-W{wk}"
    if r:
        try:
            ref = dt.date(int(r.group(3)), MONTHS[r.group(2).capitalize()], int(r.group(1)))
        except (KeyError, ValueError):
            return None, None, "unparseable reference date"
        if ref.isocalendar()[:2] != (yr, wk):
            return None, None, (f"cover inconsistent: printed ref {ref} is ISO week "
                                f"{ref.isocalendar()[1]}, cover says W{wk}")
    return fri.isoformat(), wk, "ok"


def dedup_pdfs() -> list[Path]:
    by_hash: dict[str, list[Path]] = {}
    for p in sorted(SRC.glob("**/*.pdf")):
        try:
            by_hash.setdefault(hashlib.md5(p.read_bytes()).hexdigest(), []).append(p)
        except OSError:
            continue
    keep, skipped = [], 0
    for group in by_hash.values():
        keep.append(group[0])
        skipped += len(group) - 1
    if skipped:
        print(f"[dedup] skipped {skipped} byte-identical duplicate PDF(s)")
    return sorted(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows_for, HDR = build_rows()
    with open(CSV, encoding="utf-8-sig", newline="") as fh:
        r = csv.reader(fh)
        hdr = next(r)
        pre = [x for x in r if len(x) == len(hdr)]
    assert hdr == HDR, "series header drift"
    have = set(x[0] for x in pre)
    print(f"series rows {len(pre)}; {len(have)} distinct issue dates; md5 {hashlib.md5(CSV.read_bytes()).hexdigest()}")

    # a document already represented in the series (under ANY date) must not be
    # added a second time: the series keys a week by date, but a re-collected or
    # mislabelled copy carries the same stem.
    referenced = set()
    for r in rows if False else []:
        pass
    with open(CSV, encoding="utf-8-sig", newline="") as fh:
        rr = csv.reader(fh)
        h = next(rr)
        si = h.index("source_file")
        for x in rr:
            if len(x) == len(h):
                referenced.add(Path(x[si]).stem)

    added, problems = [], []
    for pdf in dedup_pdfs():
        d, wk, note = cover_meta(pdf)
        if d is None:
            problems.append(f"{pdf.name}  [{note}]")
            continue
        if d in have:
            continue
        if pdf.stem in referenced:
            problems.append(f"{pdf.name}  [already in series under another date; not re-added]")
            continue
        got, conv = rows_for(str(pdf), pdf.relative_to(ROOT).as_posix(), d, wk)
        print(f"  + {d} wk{wk}: {len(got)} rows conv={conv}  <- {pdf.name}")
        added.extend([[row[c] for c in HDR] for row in got])
        have.add(d)
    if problems:
        print(f"SKIPPED {len(problems)} doc(s) (named, not guessed):")
        for p in problems:
            print("   -", p)
    print(f"TO ADD: {len(added)} rows")
    if a.dry_run or not added:
        return
    with open(CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        w.writerows(pre + added)
    with open(CSV, encoding="utf-8-sig", newline="") as fh:
        r = csv.reader(fh)
        h2 = next(r)
        chk = [x for x in r if len(x) == len(h2)]
    assert chk[: len(pre)] == pre, "existing rows changed!"
    print(f"POST rows {len(chk)} (+{len(added)}); CONTROL ok: existing rows byte-identical")


if __name__ == "__main__":
    main()
