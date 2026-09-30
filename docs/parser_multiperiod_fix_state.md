# Parser fix state: multi-period numbers (2026-09-24, supervisor run 11:40)

## What changed (already on disk, syntax-checked OK)
`scripts/extract/build_table_db.py` (mtime 2026-09-24 10:56) gained
`MULTI_THOUSANDS_PERIOD = ^[1-9]\d{0,2}(?:\.\d{3}){2,}$`: a number with TWO OR
MORE period groups cannot be a decimal literal, so it is a thousands separator
for every publisher. Written by the deep-review job `d77cc9df53c4` at 10:38-10:56.

## Why
`golden_destiny` writes its "Invested Capital" column with commas in the
2021/2022 era ("468,300,000") and with periods from 2023 ("149.200.000"). Only
the comma era was being read; the period era was not numeric at all, so those
cells were invisible to series construction.

## Measured scale (independent, read-only query of
## data/extracted/corpus/db/corpus.duckdb, pre-fix state)
    cells matching ^[1-9][0-9]{0,2}(\.[0-9]{3}){2,}$ : 1,768
    distinct documents                                :   101
    sources                                           :     1 (shipbrokers)
    of those cells, is_numeric = true                 :     0
The comment's "1,768 cells in 101 documents" claim is confirmed exactly.

## Pool experiment completed (6 golden_destiny docs, before/after)
Inputs are byte-identical (md5) in `pool_before` and `pool_after`; the only
variable is the parser. Outputs written to
`data/extracted/scratch_review/period_multi/{pool_before,pool_after}/db/`:

    before : cells 8094  numeric 3759  (multi-period-shaped 100, numeric 0)
    after  : cells 8094  numeric 3859  (multi-period-shaped 100, numeric 100)
    cells whose is_numeric changed : exactly 100, all in the intended shape

`211.450.000 -> 211450000.0`, `616.200.000 -> 616200000.0`; the 100 changed
values span 1,329,000 .. 1,237,600,000, plausible invested-capital magnitudes.
No collateral reclassification of any other cell.

## The one remaining step (NOT done - deliberately)
The fix is inert until the derived DB is rebuilt:

    python3 scripts/extract/build_table_db.py --out data/extracted/corpus --rebuild

Expected delta: 1,768 cells flip to numeric (101 shipbrokers documents, all
golden_destiny, no other source). Not run by the supervisor because the
source-by-source agent (12f7fa574166) was mid-trial and running a corpus-wide
scan at 11:48; two heavy jobs on an 8 GB CPU-only box is the one thing the
environment note forbids, and the shared derived DB must have a single writer.
