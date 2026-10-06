# Register gate fix - hellenic_vv_sales_series.csv was stale in the register (2026-10-06 15:5x)

## Symptom (measured, not assumed)

`python3 scripts/extract/verify_registers.py` on committed HEAD (`41e877f6c`) was **RED** with a
single mismatch:

```
ISSUES FOUND:
  Row mismatch in JSON for hellenic_vv_sales_series.csv: disk=2062 vs json=2022
```

Every other check passed (175 CSVs / 0 control chars / 0 emojis / MD section-2 in agreement).
This is a **register-consistency** defect, not an extraction defect: the CSV is right, the
register that indexes it is stale by 40 rows.

## Root cause

Commit `9479ec9e4` ("fix(ci): skip already-extracted vessel valuations HTML after parsing internal
issue_date", 13:42) rewrote `data/extracted/series/hellenic_vv_sales_series.csv` and its runner
(`run_hellenic_vessel_valuations.py`) and its `_run_state.json`, but **did not re-run the register
synchroniser** - so `EXTRACTION_REGISTER.json` / `.md` kept the pre-commit count.

Proven with git, not inference:

| ref | csv lines | data rows | JSON rows for this file |
|---|---|---|---|
| `9479ec9e4^` | 2023 | 2022 | 2022 (consistent) |
| `9479ec9e4` | 2063 | **2062** | **2022 (stale)** |

## The +40 rows are legitimate recovered sales, not drift

The 40 new rows were checked, not assumed:

* **0 exact duplicate rows** in the current CSV.
* They land on **31 distinct issue_dates** (1-3 rows each), all real sale records.
* They are dominated by **MR2 tanker** sales plus a few Handy BC / VLCC rows - i.e. the row class
  the old "already-extracted HTML" skip was dropping.
* **Spot-checked against source HTML** (the .html tier is the publisher's own read):
  `corpus/02-hellenic/vessel_valuations/2026/2026-09-09_...september-8-2026.html` prints
  `... sold to Indonesian buyers for USD 27.2 mil, VV Value USD 27.92 mil. MR2 (...)` - exactly
  the recovered row `2026-09-08 | Tanker | MR2 | MR2 | Indonesian buyers | 27.2`.

So the recoveries are genuine; the register simply never recorded them.

## Fix

Re-ran the authoritative synchroniser:

```
python3 scripts/sync_extraction_register.py
```

Minimal, exactly-scoped diff (9 insertions / 9 deletions): the one inventory row
`hellenic_vv_sales_series.csv: 2022 -> 2062`, the `series_inventory` mirror, and the four totals
(`total_master_stacked_rows` / `total_stacked_rows` 630,317 -> **630,357**;
`total_rows_extracted` 630,622 -> **630,662**; `updated_at`).

## Verification (after)

`python3 scripts/extract/verify_registers.py`:

```
Disk CSV count: 175, Disk logical rows: 630,357
JSON total_master_stacked_rows: 630,357
Mismatches with JSON: 0
Mismatches with MD: 0
ALL VERIFICATION CHECKS PASSED PERFECTLY (100.0% MATCH)!
```

Gate is green on the regenerated register.

## Note also - bancosta "Target #1" is CLOSED (re-measured this run)

The two bancosta residue verdicts still carry a "STILL OPEN: chart tables published as container
indices" pointer. Re-measured against the current 243 canonical sidecars: `vhss_contex` **0/1,704**
and `freightos_index` **0/1,759** rows have a `unit` cell that is neither a unit token nor a period
label. Already fixed by commit `d96dd30bd` ("bancosta branches 7/8 - stop publishing container chart
points as indices"). The pointer is stale - **do not reopen**.
