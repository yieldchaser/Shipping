# Gibson HTML series - table-classifier defect FIXED (2026-10-07 run)

Closes the open ledger item ("the 5 gibson empty value-rows are the only clean
removal candidate - confirm against the HTML first", `docs/duplicate_rows_source_verification.md`).
The empty rows were the visible tip: the root cause also published **wrong values**.

## Root cause (measured, one code path)

`scripts/extract/publishers/run_gibson_html.py` decided whether a `<table>` was a
market table by a loose substring test over the WHOLE table text:

    is_spot_table   = any('TD3C' in rtext or 'Suezmax' in rtext ...)
    is_bunker_table = any('VLSFO' in rtext or 'LSMGO' in rtext ...)

That matched tables that are NOT the spot/bunker market grids, and then parsed
their cells 1..5 as change/current/prev/last-month/FFA:

* **Newbuild and Second Hand Benchmark Values** (vessel valuations in **$ million**)
  - contains "Suezmax"/"Aframax" -> every row emitted as "Spot Worldscale".
* **FFA forward-curve matrix** in the `-weekly-projects-report-*` files.
* Review-issue grids ("Rates (TCEs at 'market speed')", "Rates (Eco, Non-Scrubber TCEs)").
* A review table containing "VLSFO" -> emitted as bunker prices.

Also every real spot table's **trailing blank row** (and, in the fake tables, the
header row) was emitted because a >=4-cell empty row passed the guard.

## Fix (per-source, in the runner only)

* A table qualifies as **spot** only if it carries a genuine route row, i.e. a
  first cell matching `^T[DC]\d+[A-Za-z]*\b.*(WS|TCE)` - the publisher's own
  `TD3C VLCC AG-China WS` / `... TCE $/day` labels.
* A table qualifies as **bunker** only if a row's first cell is `<Port> <Grade>`
  (`Rotterdam|Fujairah|Singapore ... VLSFO|LSMGO|MGO|HSFO`).
* Rows with an empty first cell are skipped (blank spacer rows).

No geometry, no hardcoded file list - derived from the page's own labels.

## Measured effect

Scanned all **156** Gibson HTML files (2023-2026):

| | value |
|---|---|
| spot tables matched by the OLD test | 153 |
| tables that are the real market grid | 145 |
| **mis-detected (fake) tables** | **8** |
| fake **bunker** tables | 3 |
| files affected | **8** (the 3 review files also carry a real grid) |

Delivered series:

| series | before | after | change |
|---|---|---|---|
| `gibson_tanker_spot_series.csv` | 3,602 | **3,555** | **42 fake rows removed**, **15 rows corrected** |
| `gibson_bunker_prices_series.csv` | 1,015 | 1,015 | **4 rows corrected** (count unchanged) |

The 15 spot + 4 bunker "corrected" rows are the dangerous kind: the fake row had
won the `drop_duplicates(issue_date,category,market_type,route_code)` slot and was
**publishing a fabricated number** where the page prints the real one. Example
(2023-12-15, `TD3C` Spot Worldscale): old `79.0` (a review-grid value) -> new
`56.0 / 67.0` (the real WS row). Same for TC1 `306 -> 149`, TD25 `305 -> 156`,
all 6 codes on 2023-12-15 / 2024-07-05 / 2024-12-20.

Markdown (primary deliverable): exactly **9 .md + 9 .tables.json** changed; the
other **147 are byte-identical** to HEAD. The only churn I had to undo was a
`source_url` blank (recovered from `gibson_all_reports_catalog.json`).

## Verification (no vision tool in this cron session - stated)

1. **Ground truth = the page's own table text.** Every corrected value is a
   verbatim token in the source HTML (checked: 2023-12-15, 2024-07-05, 2024-12-20
   - all present, 0 missing).
2. **Control.** Every row whose key is common to the old and new CSV is
   byte-identical except exactly the 15 intended corrections; 0 rows added.
3. Old test vs new test differ only on the 8 fake tables; nothing else changed.

Register synced `gibson_tanker_spot_series.csv` 3,602 -> 3,555; `verify_registers.py`
= **ALL PASSED (180 CSVs / 641,130 rows, 0 mismatches)**.

## Note for future runs
The `gibson_*` HTML tier is re-run from the local corpus (no network) - the
runner skips fetching when the `.md` and `.tables.json` exist. Re-running it now
is safe and deterministic.
