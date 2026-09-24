# Intermodal - still NOT correct. Do not use either backfill.

## Status of the two attempts

| attempt | output | control vs the 49 known-good rows |
|---|---|---|
| `intermodal_tc_rates_backfill.csv`   | 252 rows, 20/20 fields | **83.5%** |
| `intermodal_tc_rates_columnaware.csv`| fields 0/20, 12/20...  | not usable |
| `intermodal_tc_rates_v2.csv`         | 252 rows, 180 at 20/20 | **61.9%** |

**The v2 output is the WORST of the three on the only test that matters.** It found
both pages on all 252 documents and populated 20 fields on 180 of them - and it is
still wrong, because it reads the wrong COLUMN.

## What was established by rendering pages (the valuable part)

Page 2 "Tanker Market" carries a TC Rates table, 12 rows:
    300k 1yr/3yr, 150k 1yr/3yr, 110k 1yr/3yr, 75k 1yr/3yr, 52k 1yr/3yr, 36k 1yr/3yr
Page 3 "Dry Bulk Market" carries a SEPARATE TC Rates table, 8 rows:
    180k 1yr/3yr, 76k 1yr/3yr, 58k 1yr/3yr, 32k 1yr/3yr
12 + 8 = the 20 inherited fields. That is why a single-page extractor capped at 12.

Both pages carry a row labelled "Panamax" - tanker 75k and dry bulk 76k - so a
pattern accepting 7[56]k matches both and only page context disambiguates. The
anchors are '300k Nyr TC' (tanker page) and '180k Nyr TC' (dry-bulk page).

The date header format CHANGED between years: 2025 writes 07/03/25 (8 chars),
2026 writes 08/05/2026 (10 chars). A regex demanding dd/mm/yy silently found
nothing in 2026 and returned 0/20 with no error. Page 3 also uses uppercase K
(180K) where page 2 uses lowercase (300k).

## Why v2 still reads the wrong column

The page's text layer RENDERS TWO NUMBERS AT THE SAME x WITHIN ONE ROW'S WINDOW.
Measured on 2025 W10 page 2:

    y 356.3-366.9 | 300k 1yr TC | nums at x108: '44,500' AND '45,000'
    y 367.6-378.3 | 300k 3yr TC | nums at x108: '45,000' AND '35,000'

and the rendered page shows:

    $/day              07/03/25   28/02/25
    VLCC 300k 1yr TC    44,500     44,750
        300k 3yr TC     45,000     43,500

v2 anchored on the label's y-CENTRE and required 6pt proximity, but with two
numbers stacked at the same x the nearest-by-y is not reliably the current row's,
and the result is that it takes the PREVIOUS-WEEK column:
    vlcc_1y  old=44,500 (current)  new=44,750 (previous)
    vlcc_3y  old=45,000 (current)  new=43,500 (previous)

## What the next attempt must do - NOT more regex tuning
The overlapping text layer means GEOMETRY ALONE cannot resolve which number belongs
to which cell. Options, in order of promise:
  1. Use `page.get_text("rawdict")` to get per-SPAN bboxes (spans are not merged like
     lines) and pick the span whose bbox is fully inside both the row band and the
     current-week column band.
  2. Use the word's FULL bbox (x1 as well as x0) so a number cannot be claimed by a
     column it merely starts inside.
  3. Re-derive from the ORIGINAL .md path where column order survived - the 49-row
     CSV proves that path produced correct values; the missing input directory
     `reports/broker_reports/` is the only reason it stopped.
Recovery note: 47 intermodal .md files still exist in the old agent worktree
`.claude/worktrees/maritime-audit-docs-review-a8b612/knowledge/docs/broker_reports/`.

## The rule this source keeps proving
Each of these looked finished and was not: the first backfill (252/252 complete,
16.5% wrong), the column-aware version (12/12 on one page, 0/20 across the corpus),
and v2 (180/252 at 20/20, 61.9% agreement). Only the CONTROL TEST distinguishes a
complete-looking extraction from a correct one, and nothing else does.
