# agora_indicators_series.csv - date-hygiene recovery + W37/W39 recall (+94 rows)

Source-by-source run, 2026-10-03 ~13:3x IST. Branch
`auto/extract-fixes-2026-10-03-clarksons-desktalk` (the branch HEAD was already on).
`main` NOT touched. `data/extracted/` is gitignored, so the delivered CSV is the
artefact of record; only the register + this note are committed.

## What was wrong (measured, not guessed)

A content-completeness sweep of the corpus (`corpus/01-brokers/agora`, 217 PDFs)
against the delivered series found **6 issues effectively invisible to any
date-joined query**:

| defect | issues | rows | why |
|---|---|---|---|
| BLANK `issue_date` AND BLANK `report_week` | 5 (`2024_w32`, `2024_w49`, `2025_w04`, `2025_w27`, `2026_w14`) | 235 | files carry the older lowercase `agora_<YYYY>_w<NN>.pdf` name; whatever built the series could not read a date off them |
| BLANK `report_week` (date present) | 1 (`agora_18_09_2026_...`, the W38 issue) | 47 | date came from the download-date filename; the week was never assigned |
| ABSENT from the series entirely | 2 (`W37` 2026-09-11, `W39` 2026-09-25) | 94 | the stacker that built the CSV never emitted them (the sidecar for W37/W38 is a metadata-only stub; W39 has no sidecar) |

`report_week` was also stored as a float string (`"36.0"`) - every other series
in the corpus stores an int string (`"26"`, `"27"`, `"29"`).

## The convention, derived from the data (not assumed)

`issue_date == the Friday of ISO week report_week`, verified against **9,626
existing dated rows / 0 mismatches**. It is a clean rule, so the missing dates
are computable once the week is known.

The week/year for the 5 undated issues and for W38 were read off each
**document's own cover** (`Week NN / YYYY`), not the filename - agora filenames
have been wrong before (a `W34` file prints "Week 35"). All 6 covers matched
their expected week.

## Fix (all measured, each with a control)

1. **Date the 5 blank issues** from their cover week -> `issue_date = Friday`,
   `report_week` = int. `scratch/agora_fix/fix_dates.py`.
   Control: every non-date column byte-identical row-for-row; 0 blank dates after.
2. **Fill the W38 week** (cover: Week 38 / 2026; date already correct).
3. **Normalise `report_week` to int** across the column to match corpus
   convention. `scratch/agora_fix/normalize_week.py`; control: only
   `report_week` changed (9,626 values).
4. **Recover W37 and W39** by re-running the source's OWN extractor
   (`run_agora.build`) over the two PDFs and emitting rows in the exact series
   schema. `scratch/agora_fix/build_rows.py` + `append.py`.
   **Validation before trusting it:** the builder reproduces the existing W36 and
   W35 rows **byte-for-byte (47/47 each, EXACT MATCH)**. Control on the append:
   append-only, existing rows byte-identical.

W39 is byte-identical to `agora_30_09_2026_...` (md5 `18d36a0c...`), and W38 is
byte-identical to `agora_18_09_2026_...` (md5 `77c63a46...`), so each issue is
represented once - no double-count.

## Result (measured)

| metric | before | after |
|---|---|---|
| rows | 9,908 | **10,002** (+94) |
| blank `issue_date` | 235 | **0** |
| blank `report_week` | 282 | **0** |
| `report_week` float strings | 9,626 | **0** |
| duplicate-key rows (key = all cols except `source_file`) | 0 | **0** |

Content spot-check against the rendered page text (no vision tool in this
session - the same-document text-layer reconciliation is the substitute, stated
plainly): W39 Crude Oil series `94.61 / -8.38 / 13.26` == page `94,61 /
-8,38% / 13,26%`; W37 Crude Oil `102.48` == page `102,48`. 2026 weeks now read
`1,2,6..14,16,19..30,32,33,35,36,37,38,39` (was missing 14, 37, 39 and blank 38).

Register re-synced: `scripts/sync_extraction_register.py` -> agora 9,908 ->
**10,002**; Section-2 total 594,568 -> **594,409** (also picks up the parallel
clarksons_desk_talk 608 -> 355 fix already on this branch).

## Residual (disclosed, not fixed)

* The writer that builds `agora_indicators_series.csv` is **not in `scripts/`**
  (only `run_agora.py`, which writes md/sidecars, and `format_agora_properly.py`,
  which writes the md + a metadata-only stub sidecar). The delivered CSV is
  therefore patched directly; a rebuild from scratch would need that stacker
  reconstructed.
* The stale **flat** `source_file` paths (`corpus/01-brokers/agora/<file>.pdf`
  without the year directory) affect every row - a separate, corpus-wide
  path-reference item, not touched here.
