# agora - dedup: 94 rows removed, and the census's skip set would have removed the WRONG copy

**Date:** 2026-10-03 01:3x IST  ·  **Source:** `corpus/01-brokers/agora` (217 PDFs / **213 unique**, 4 md5 groups)
**File:** `data/extracted/series/agora_indicators_series.csv`  ·  **Writer:** none exists in the repo
(`run_agora.py` writes md sidecars only; see the residual below)
**File rows:** 10,002 -> **9,908** (-94)

## Why a row-filter and not a re-run

`run_agora.py` writes the `.md` + `.tables.json` sidecars and a run-state; **no script in the repo writes
`agora_indicators_series.csv`** (checked `scripts/` and `scratch/`). So there is nothing to re-run: the only
options are a rebuilt stacker or a deliberate, controlled row-filter. A row-filter was chosen and applied
here, with the control below.

## What was removed, and the trap in the census's skip set

The census said "94 rows from a dropped stem". That is right as a count - but the stem it names is wrong
for one of the two groups:

| group | copies (md5-identical) | rows in CSV | correct action |
|---|---|---|---|
| 2024 W52 | `..._W52_...-1` / `..._W52_...` | 47 + 47 | drop the `-1` twin (keeper present) |
| 2026 | `agora_2026_W34_...Week-35-2026...` / `agora_2026_W35_...Week-35-2026...` | 47 + 47 | drop the **W34-named** copy |

`doc_dedup.byte_duplicate_stems()` keeps the lexicographically-first stem, which for the 2026 pair is the
**misfiled** one - `agora_2026_W34_...` sorts before `agora_2026_W35_...`. **Dropping its skip stem
(`agora_2026_W35_...`) would have deleted the correctly-labelled week-35 rows and kept the misdated
week-34 ones** - a straight inversion, caught by the control.

Evidence the W34-named copy is the misfiled one:
- both files' own cover line reads **`Week 35 / 2026`** (`pymupdf` page-0 text);
- **no** agora 2026 PDF carries `Week 34 / 2026` (all 2026 covers regexed); 2026 week 34 does not exist in
  the corpus at all;
- the CSV's `2026-08-21 / week 34` rows come **only** from the W34-named file - they are week-35 values
  stamped with a filename-derived week 34.

## Control

Every dropped row's **data columns** (`section,label,name,period,val_*`) are matched by an identical row in
the kept set: **0 data rows lost** (`lost_data_rows=0`). The only thing removed is the divergent
filename-derived `issue_date`/`report_week` pair on the misfiled copy. The two 0-row skip stems
(`agora_2026_W38_...`, `agora_30_09_2026_...`) contribute nothing.

POST: 9,908 rows, 211 distinct source files; the spurious 2026 week-34 datapoint is gone and week 35
(2026-08-28) remains. Pre-fix copy `scratch/agora_dedup/PRE_agora_indicators_series.csv`, script
`scratch/agora_dedup/filter.py`. `data/extracted/` is gitignored - the corrected CSV is on disk only.

## Residual - disclosed, not fixed (the real cause of the stale series)

agora's newest issues have **no table sidecars**, so the series cannot reach them:
- `agora_2026_W37_...tables.json` and `agora_2026_W38_...tables.json` are **174-byte STUBS**
  (`{"stem":..., "charts": []}` - no tables);
- `agora_2026_W39_...` and `agora_30_09_2026_...` have an `.md` but **no `.tables.json` at all**.

The series therefore ends at the 2026-09-18 issue. Extending it needs (a) a rebuilt stacker, which does
not exist in the repo, and (b) a reparse of those issues so their sidecars are real. Not attempted this
run - it is a separate, larger item and must be measured on its own.
