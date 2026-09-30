# Intermodal TC rates - 800 cells in `intermodal_tc_rates_v2.csv` read a HISTORICAL column

Found 2026-09-24 ~13:00 by the hourly supervisor, during independent verification of
`docs/intermodal_verdict.md` (which declared the source COMPLETE at "252 documents,
0 failures, 100% control agreement"). The completion claim is true. The values are not.

## What is wrong

On the 2021 and 2022 reports the Tanker TC table carries SIX columns:

    $/day | 02-Jul-21 | 25-Jun-21 | +/-% | Diff | 2020 | 2019

The CSV reports the LAST column's value as the current assessment. Measured, verbatim
from `intermodal_2021_W26` page 2 (pymupdf text order):

    300k 1yr TC   26,000  26,000  0.0%  0  42,038  37,462
                  ^current-week        ^2020  ^2019   <- CSV vlcc_1y_tc = 37,462

`allied_2022_W04` page 2 the same way:

    300k 1yr TC   27,000  27,000  0.0%  0  25,684  42,038   <- CSV vlcc_1y_tc = 42,038

For 2023-2026 the table has only two date columns, so the same code lands on the
current week and the control test (which only overlaps 2025-03 -> 2026-09) sees nothing.

## Blast radius (all 252 documents re-read)

| era | docs | docs wrong | cells wrong |
|---|---|---|---|
| 2021 | 25 | **25** | 300/300 tanker |
| 2022 | 49 | **41** | 492/588 tanker |
| 2023-2026 (+1 odd filename) | 178 | 0 | 0 |
| **total** | 252 | **66** | **800** (792 tanker + 8 bulk) |

The 8 bulk cells are `intermodal_2021_W30_Intermodal-Report-Week-30-2021-2.pdf`
(all 8 dry-bulk fields = its 2019 column; e.g. capesize_1y 17,397 vs page's 29,500).
Affected fields: all 12 tanker fields in all 66 docs; the bulk fields in 1 doc.

## How it was measured (two independent methods, no shared code with the extractor)

1. `scratch/supervisor/intermodal_fullcheck.py` - text-order method: rebuild each
   `<NN>k <n>yr TC` row from the page's line order and record which token index the
   CSV value occupies. 0 = current week, >=2 = historical. Result: 792 tanker cells at
   index >= 2, all in 2021-2022; 0 in 2023-2026.
2. `scratch/supervisor/intermodal_colfix.py` - geometry method: take the x0 of the
   FIRST date token in the table's header row as the current-week column, then read the
   row's numeric span aligned to that x0. **Control: it reproduces v2 EXACTLY on 186 of
   252 docs and differs on exactly the same 66 docs** - the method and the defect are
   each confirmed by the other.

## Corrected candidate (not shipped, not committed)

* `data/extracted/intermodal_tc_rates_v3.csv` - v2 with the 800 cells replaced; every
  other cell byte-identical (verified: 252 rows x 26 cols, 800 cells differ, all other
  columns identical).
* `data/extracted/intermodal_tc_column_patch.json` - per-cell old/new + evidence
  (page, current-week header string, how it was picked).
* Re-verified by the independent text-order method over the 66 docs: 1,320/1,320 cells
  now sit in the current-week position, 0 still wrong.

## What the source owner should do

Do NOT ship v3 blind and do NOT just hand-edit: make `intermodal_v2.py` column-aware -
select the value by the x0 of the table's current-week header, not by row proximity or
token order. Also note the extractor's date-header regex fails on `7/30/2021`
(single-digit month), and where it fails the value taken is the row's LAST number -
so any page whose date header does not match is silently a historical column. Re-run
the control test over 2021-2022 as well as 2025-2026.
