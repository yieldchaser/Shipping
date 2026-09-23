# Intermodal T/C backfill - FAILED VERIFICATION, do not use

## Status: the backfill output is NOT trustworthy. Do not merge it.

`data/extracted/intermodal_tc_rates_backfill.csv` (252 rows, 2021-07-06 to
2026-09-18, all 20 fields populated) LOOKS complete. It is not CORRECT.

## UPDATE - the column-aware fix verified on ONE page but does NOT generalise

`scripts/extract/publishers/intermodal_columnaware.py` reproduces the rendered
page EXACTLY on 2025 W10 (12/12 values), fixing the wrong-column defect. But its
FULL run over 252 docs shows it does not generalise:

    files=252   all-20-fields=0   failed=0
    2022 W26: 0/20    2023 W27: 14/20    2024 W29: 14/20
    2025 W31: 14/20   2026 W34:  0/20    2026-09:  0/20

Two structural reasons, both worth understanding before trying again:

1. THE 20-FIELD SET SPANS MORE THAN ONE TABLE. Page 2's TC Rates table carries
   only 12 rows - VLCC/Suezmax/Aframax/Panamax/MR/Handy, each at 1yr and 3yr.
   The remaining fields (capesize, supramax, handysize, handy_tanker variants)
   are DRY BULK and live in a different table, probably on another page. So 12/20
   is the ceiling from page 2 alone, and the docs showing 14/20 carry extras
   elsewhere. The inherited 20 RATE_FIELDS were written against flattened .md
   text where the source table was not visible, so nothing in them records WHICH
   table each field came from.

2. THE NEWEST LAYOUT DOES NOT MATCH AT ALL - 2026 returns 0/20, and so does
   2022 W26. Either the labels changed (as Panamax already did: the page says
   '75k', the inherited pattern said '76k') or the table moved off page 2. This
   must be established by RENDERING a 2026 document and reading it, not guessed.

## What the next attempt must do
- Render a 2026 document and a 2022 document and read the actual tables.
- Map EACH of the 20 fields to the table and page it comes from, per era.
- Then re-run the control test: agreement with the 49 known-good rows must reach
  ~100% on the overlap before ANY of the 2021-2024 history is trusted.
- Do not report a field count as success. 14/20 with 6 fields silently absent is
  indistinguishable from 0/20 in a summary - only the control test distinguishes
  a partial extraction from a correct one.

---

## What the control test found
The backfill overlaps the pre-existing `data/derived/intermodal_tc_rates.csv`
(49 rows) over 2025-03-07 to 2026-09-11. Both were produced by the same 20
RATE_FIELDS patterns, but from different inputs (the old one from .md files, the
new one from PDF text). Where they overlap they must agree. They do not:

    980 comparable values   818 agree   162 differ   = 83.5% agreement

## Root cause, established by RENDERING PAGE 2 AND READING IT
The TC Rates table on page 2 carries SEVERAL value columns per row:

    $/day                 07/03/25   28/02/25    +/-%   Diff    2024    2023
    VLCC   300k 1yr TC     44,500     44,750    -0.6%   -250   50,365  48,601
           300k 3yr TC     45,000     43,500     3.4%   1500   47,339  42,291
    Suezmax 150k 1yr TC    35,000     35,000     0.0%      0   45,394  46,154

The patterns are `300[Kk]\s+1yr\s+TC\s+([\d,]+)` - a label followed by a number.
With four numeric columns there is no way for that pattern to know WHICH column
it caught. Measured example: the backfill returned 44,750 for 2025-03-07, which
is the PREVIOUS-WEEK column; the value the page shows for that date is 44,500,
which is what the existing CSV has. So the OLD data was right and the NEW
backfill is wrong.

Contributing factor: the backfill regexed the CONCATENATED text of all pages.
Page 1 has no T/C table at all, so a label and an unrelated number could be
paired across a page boundary. Search must be per-page and, more importantly,
per-COLUMN.

## The real fix (not yet implemented)
Column positions must come from geometry, not from match order:
  * locate the header row (07/03/25, 28/02/25, ...) and take their x-ranges;
  * for each labelled row, take the cell whose x-range falls under the CURRENT
    week header;
  * validate by re-running the control test - agreement with the 49 known-good
    rows must reach ~100% before the 2021-2024 history is trusted at all.

## What remains valid
- The PDF corpus (252 docs, 2021-2026) and the finding that 20 rate fields EXIST
  in every year: field hit rate 20/20 across 2021/2023/2024/2026.
- The date extraction worked: 246 of 246 full ISO dates, range 2021-07-06 ..
  2026-09-18.
- The pre-existing 49-row CSV is the more accurate of the two - it came from .md
  where column order survived. It remains the reference until the backfill beats
  it on the control test.

## The lesson this establishes (the strongest one of the night)
A 252-row, 0-failure, fully-populated output was 16.5% WRONG, and nothing but a
CONTROL TEST against an independent extraction revealed it. Row counts, field
counts and clean exit codes were all green. Percent-complete metrics prove
nothing about correctness - only agreement with an independent source does.
