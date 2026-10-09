"""Re-derive star_asia_deals_series.csv's arrival/beaching date columns.

The stored date VALUES are faithful to the publisher's page (proven against the
PDF text layer).  This tool re-derives the two primary ISO columns plus their
status/note columns from the page-raw strings via
``scripts/extract/publishers/star_asia_dates.py``, which also appends the
impossible-date quarantine flags (``|FUTURE_VS_ISSUE`` / ``|ORDER_INVALID``).

History / why this was rewritten (2026-10-09):
  the ORIGINAL version fed the PRIMARY (already-ISO) column back into the
  normaliser, so on the delivered CSV every cell re-parsed as UNPARSED -- running
  it with --apply would have BLANKED all 4,449 ISO dates.  It also wrote a
  hardcoded 20-column FIELDS list (dropping built / country_destination /
  buyer_comments / terms) and CRLF line endings.  This version reads the CSV's
  OWN header and the ``*_raw`` columns, preserves the exact column set and LF
  EOL, and is idempotent.

Run:  python3 scripts/extract/apply_star_asia_deals_dates.py [--apply]
Without --apply it reports only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "extracted" / "series" / "star_asia_deals_series.csv"
BACKUP = ROOT / "scratch" / "sup" / "star_asia_deals_series.pre_dates_backup.csv"
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
from star_asia_dates import normalise_deal_dates  # noqa: E402

RAW_TO_ISO = {"arrival_date_raw": "arrival_date", "beaching_date_raw": "beaching_date"}
AUDIT = ["arrival_date", "arrival_date_status", "arrival_date_note",
         "beaching_date", "beaching_date_status", "beaching_date_note"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    raw = CSV_PATH.read_bytes().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw, newline="")))
    hdr = rows[0]
    if not all(c in hdr for c in list(RAW_TO_ISO) + AUDIT):
        print("ABORT: CSV lacks the expected date/audit columns")
        return 2

    # safety: a no-op csv round-trip must reproduce the bytes exactly
    rt = io.StringIO()
    csv.writer(rt, lineterminator="\n").writerows(rows)
    if rt.getvalue().encode("utf-8") != CSV_PATH.read_bytes():
        print("ABORT: csv round-trip is not byte-identical (quoting/EOL risk)")
        return 2

    i = {c: hdr.index(c) for c in hdr}
    out = [hdr]
    notes = collections.Counter()
    changed = 0
    iso_mismatch = 0
    for r in rows[1:]:
        new = list(r)
        rec = {"issue_date": r[i["issue_date"]]}
        for rawc, isoc in RAW_TO_ISO.items():
            # prefer the page-raw column; fall back to the primary cell
            rec[isoc] = r[i[rawc]] if r[i[rawc]] else r[i[isoc]]
        normalise_deal_dates(rec)
        for rawc, isoc in RAW_TO_ISO.items():
            if rec[isoc] != r[i[isoc]]:
                iso_mismatch += 1
            for sfx in ("", "_status", "_note"):
                col = isoc + sfx
                if rec[col] != r[i[col]]:
                    changed += 1
                    new[i[col]] = rec[col]
                    if sfx == "_note" and rec[col]:
                        notes[rec[col]] += 1
        out.append(new)

    print(f"rows                        : {len(rows)-1}")
    print(f"cells changed               : {changed}")
    print(f"ISO mismatches (control)    : {iso_mismatch}")
    print("--- notes ---")
    for k, n in notes.most_common():
        print(f"   {n:5d}  {k}")
    if iso_mismatch:
        print("ABORT: control failed (raw->ISO disagrees with the delivered value)")
        return 1
    if changed == 0:
        print("idempotent: nothing stale, no write")
        return 0
    if not args.apply:
        print("dry run - nothing written")
        return 0

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CSV_PATH, BACKUP)
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(out)
    CSV_PATH.write_bytes(buf.getvalue().encode("utf-8"))
    print(f"wrote {CSV_PATH} (backup: {BACKUP})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
