#!/usr/bin/env python3
"""Apply the Fearnleys Dry-Bulk 1-Year T/C corrections to the delivered series CSV.

WHY (measured 2026-10-09): the committed fixes in
`run_fearnleys_normalized.py` (commits 861054ddc "anchor Dry 1Y TC rows to the
1 Year T/C block" and 8872218c4 "recover the Dry Bulk 1Y TC first page on the
2024/2025 Fearnpulse layout") changed the CODE but the delivered
`data/extracted/series/fearnleys_rates_series.csv` was never regenerated, so it
still carries the pre-fix values:
  * 183 rows in `02 Dry Bulk / Dry 1Y TC` whose `value` was the vessel SIZE
    (e.g. 2021-07-28 Capesize value 180.0 -> 27,500.0) and/or whose `size`/`change`
    were shifted (a later row's size overwrote the current row's; unsigned positive
    changes fell to 0.0);
  * 7 missing rows (the whole first page of the 2024/2025 Fearnpulse 1Y T/C block,
    e.g. 2026-10-01 Newcastlemax/Kamsarmax/Ultramax/Capesize/Panamax/Supramax).

SCOPE: this tool touches ONLY `section == "Dry 1Y TC"` rows. It is a MERGE onto
the delivered file (add new keys, overwrite matching keys whose cells differ) - it
never deletes a row and never touches any other section, so the file's multi-era
accumulated rows (sections no longer produced by the current code, e.g.
`Capesize Spot`) are preserved untouched. Idempotent: a second run reports
nothing stale and writes nothing.

The fresh extraction is obtained by running the publisher's own runner with its
output redirected to a temp dir (the runner writes a *pure* current-code CSV with
no merge); pass an existing fresh CSV with --fresh-csv to skip that step.

Usage:
  python3 scripts/extract/publishers/apply_fearnleys_1y_tc_fix.py --fresh-csv scratch/fl_base/out_series.csv
  python3 scripts/extract/publishers/apply_fearnleys_1y_tc_fix.py            # re-runs the runner into a temp dir
  python3 scripts/extract/publishers/apply_fearnleys_1y_tc_fix.py --check    # report only, no write
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"c:\Users\Dell\Github\Shipping")
SERIES_CSV = ROOT / "data" / "extracted" / "series" / "fearnleys_rates_series.csv"
SECTION = "Dry 1Y TC"
KEYCOLS = ("issue_date", "chapter", "section", "label")
FIELDS = ["issue_date", "report_week", "page", "chapter", "section",
          "label", "value", "size", "change", "source_file"]


def sort_key(r):
    return (r.get("issue_date", ""), str(r.get("chapter", "")), str(r.get("section", "")))


def load(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fresh_extraction():
    """Run the publisher runner with outputs redirected to a temp dir."""
    sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
    import run_fearnleys_normalized as R  # type: ignore
    tmp = Path(tempfile.mkdtemp(prefix="fearnleys_fresh_"))
    R.MD_DIR = tmp / "md"
    R.SERIES_CSV = tmp / "fresh_series.csv"
    (tmp / "md").mkdir(parents=True, exist_ok=True)
    R.normalize_fearnleys()
    return R.SERIES_CSV


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh-csv", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    fresh_path = Path(args.fresh_csv) if args.fresh_csv else fresh_extraction()
    if not fresh_path.exists():
        sys.exit(f"fresh CSV not found: {fresh_path}")

    delivered = load(SERIES_CSV)
    fresh = load(fresh_path)
    before = len(delivered)

    idx = {}
    for i, r in enumerate(delivered):
        idx[tuple(r[c] for c in KEYCOLS)] = i

    added = 0
    changed = 0
    changed_cells = 0
    changed_sections = {}
    out = list(delivered)
    new_rows = []
    for r in fresh:
        if r.get("section") != SECTION:
            continue
        k = tuple(r[c] for c in KEYCOLS)
        if k in idx:
            cur = out[idx[k]]
            diff = [c for c in FIELDS if cur.get(c) != r.get(c)]
            if diff:
                changed += 1
                changed_cells += len(diff)
                changed_sections[r["section"]] = changed_sections.get(r["section"], 0) + 1
                for c in FIELDS:
                    cur[c] = r.get(c, "")
        else:
            added += 1
            new_rows.append({c: r.get(c, "") for c in FIELDS})

    if new_rows:
        out = out + new_rows
        out.sort(key=sort_key)

    print(f"delivered rows: {before} -> {len(out)} (added {added}, changed {changed} rows / {changed_cells} cells)")
    print(f"changed sections: {changed_sections}")

    if args.check:
        print("--check: no write")
        return
    if added == 0 and changed == 0:
        print("idempotent: nothing stale, no write")
        return

    tmp = SERIES_CSV.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in out:
            w.writerow(r)
    tmp.replace(SERIES_CSV)
    print(f"wrote {SERIES_CSV}")


if __name__ == "__main__":
    main()
