"""Normalise star_asia_deals_series.csv's arrival/beaching dates to ISO.

The stored values are faithful to the publisher's page (proven against the PDF
text layer), so this reformats ONLY the two date columns, keeps the page's own
string in ``*_raw``, and adds a status/note column pair.  Every other column is
left byte-identical -- asserted by scripts/extract/verify_star_asia_deals_dates.py.

Run:  python3 scripts/extract/apply_star_asia_deals_dates.py [--apply]
Without --apply it reports only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "extracted" / "series" / "star_asia_deals_series.csv"
BACKUP = ROOT / "scratch" / "sup" / "star_asia_deals_series.pre_dates_backup.csv"
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
from star_asia_dates import normalise_deal_dates  # noqa: E402

BASE_FIELDS = [
    "issue_date", "report_week", "deal_type", "vessel_name", "vessel_type",
    "ldt", "price_usd_per_ldt", "destination_yard",
    "year_built", "built_country", "arrival_date", "beaching_date",
    "terms_comments", "source_file",
]
AUDIT_FIELDS = [
    "arrival_date_raw", "arrival_date_status", "arrival_date_note",
    "beaching_date_raw", "beaching_date_status", "beaching_date_note",
]
FIELDS = BASE_FIELDS + AUDIT_FIELDS


def load() -> list[dict]:
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = load()
    before = {i: (r.get("arrival_date", "").strip(), r.get("beaching_date", "").strip())
              for i, r in enumerate(rows)}

    out = []
    for i, row in enumerate(rows):
        rec = {k: row.get(k, "") for k in BASE_FIELDS}
        normalise_deal_dates(rec)
        out.append({**{k: rec.get(k, "") for k in FIELDS}, "_lineno": i + 2})

    date_notes = collections.Counter()
    quarantined = []
    for rec in out:
        for col in ("arrival_date", "beaching_date"):
            raw = rec[f"{col}_raw"]
            if not raw:
                continue
            date_notes[rec[f"{col}_note"]] += 1
            if rec[f"{col}_note"] == "UNPARSED":
                quarantined.append({"lineno": rec["_lineno"], "column": col, "value": raw,
                                    "vessel": rec["vessel_name"], "source_file": rec["source_file"]})
    iso = sum(1 for r in out if r["arrival_date"]) + sum(1 for r in out if r["beaching_date"])
    print(f"rows                        : {len(out)}")
    print(f"non-empty date cells        : {sum(1 for r in out for c in ('arrival_date','beaching_date') if r[c+'_raw'])}")
    print(f"cells now ISO               : {iso}")
    for k, n in date_notes.most_common():
        print(f"   {k:24s} {n}")
    print(f"quarantined (UNPARSED)      : {len(quarantined)}")

    if not args.apply:
        print("dry run - nothing written")
        return 0

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CSV_PATH, BACKUP)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in out)
    print(f"wrote {CSV_PATH} (backup: {BACKUP})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
