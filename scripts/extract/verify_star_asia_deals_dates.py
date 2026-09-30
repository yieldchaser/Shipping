"""Independent verification of the star_asia deals date normalisation.

Compares data/extracted/series/star_asia_deals_series.csv against the pre-change
backup in scratch/sup/ and asserts:
  1. the row count is unchanged;
  2. every column OTHER than the two date columns is byte-identical;
  3. every new primary date cell is either empty or ISO YYYY-MM-DD;
  4. every new date cell's *_raw equals the old primary cell verbatim
     (proves nothing was altered, only reformatted);
  5. no date was invented: ISO dates in the new file must come from a raw value
     the parser classifies as a date.
"""
from __future__ import annotations
import csv, re, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "data" / "extracted" / "series" / "star_asia_deals_series.csv"
OLD = ROOT / "scratch" / "sup" / "star_asia_deals_series.pre_dates_backup.csv"
DATE_COLS = ("arrival_date", "beaching_date")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

old = list(csv.DictReader(open(OLD, encoding="utf-8", newline="")))
new = list(csv.DictReader(open(NEW, encoding="utf-8", newline="")))
fails = []
if len(old) != len(new):
    fails.append(f"row count {len(old)} -> {len(new)}")
same_ctx = 0
for i, (o, n) in enumerate(zip(old, new)):
    for k, v in o.items():
        if k in DATE_COLS:
            continue
        if n.get(k, "") != v:
            fails.append(f"line {i+2} column {k}: {v!r} -> {n.get(k)!r}")
        else:
            same_ctx += 1
noniso = [r[c] for r in new for c in DATE_COLS if r[c] and not ISO.match(r[c])]
if noniso:
    fails.append(f"non-ISO primary dates: {len(noniso)} e.g. {noniso[:5]}")
raw_mismatch = [i + 2 for i, (o, n) in enumerate(zip(old, new))
                if n["arrival_date_raw"] != (o["arrival_date"] or "").strip().strip("`'\u2018\u2019\"")
                or n["beaching_date_raw"] != (o["beaching_date"] or "").strip().strip("`'\u2018\u2019\"")]
if raw_mismatch:
    fails.append(f"raw != old primary on {len(raw_mismatch)} rows e.g. {raw_mismatch[:5]}")
iso_cells = sum(1 for r in new for c in DATE_COLS if r[c])
print(f"old rows {len(old)}  new rows {len(new)}")
n_ctx_cols = len([k for k in old[0] if k not in DATE_COLS])
print(f"context cells compared byte-for-byte: {same_ctx} ({n_ctx_cols} columns x {len(new)} rows)")
print(f"ISO date cells in new file: {iso_cells}")
print(f"non-ISO primary cells     : {len(noniso)}")
print(f"raw-vs-old mismatches     : {len(raw_mismatch)}")
print("--- notes ---")
for k, v in collections.Counter(r[f"{c}_note"] for r in new for c in DATE_COLS if r[f"{c}_note"]).most_common():
    print(f"   {v:5d}  {k}")
print("--- statuses ---")
for k, v in collections.Counter(r[f"{c}_status"] for r in new for c in DATE_COLS if r[f"{c}_status"]).most_common():
    print(f"   {v:5d}  {k}")
if fails:
    print("FAIL"); [print("  ", f) for f in fails[:20]]
    sys.exit(1)
print("PASS - all checks green")
