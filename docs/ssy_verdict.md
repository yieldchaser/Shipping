# SSY (source 3) - COMPLETE and VERIFIED

data/extracted/md/ssy/ : 519 .md + 519 .tables.json
  519/519 documents, 0 failures, 121 seconds.

## Verified numbers
  route rows extracted : 5,920
  index entries        : 3,114
  docs with ZERO routes: 0
  md size              : 1,161-1,897 bytes each, 727 KB total, none undersized
  page count           : 1 page per document, every year

## Structure is CONSISTENT across years (the audit question)
  2021 rows=16 routes=10 index_keys=6
  2023 rows=17 routes=12 index_keys=6
  2024 rows=17 routes=12 index_keys=6
  2026 rows=17 routes=12 index_keys=6
Same 10 route lanes + 2 T/C rows, same 5 index rows (Calculated Index + 4
Changes), plus a $/Day block on the newer layout.

## Why this needed its own pipeline (three failures before the working method)
1. liteparse fuses the prose column into the table, because the page's columns
   OVERLAP in x (prose to 211, table from 208):
     | $5,000/day and $4,750/day in the round | NARVIK/ROTTERDAM | 150,000/10% ...
2. Clipping by horizontal-rule position picked the CHART's gridlines - evenly
   spaced rule chains exist in both the table and the chart, so geometry alone
   cannot tell them apart.
3. A fixed x-cut at 205 worked for 2021/2023 and SILENTLY DELETED every route
   name in 2026, where routes sit at x~12 instead of x~208. A fixed size
   threshold fails too: the table is 9.0pt in 2021 but 8.7pt in 2026.
pdf-inspector - the source-1 engine - returns 0 usable tables here at all, and
PyMuPDF find_tables() finds a 16x3 grid with empty cells.

## The method that survives (self-calibrating, no fixed geometry)
  * the page's table size = the MODAL font size among its numeric cells
  * a table row = a y-band holding >=2 numeric cells (anchor on numbers, so the
    route column is found wherever it sits)
  * on that row take every span at the table size; prose is always larger, so it
    is excluded by size rather than by coordinate
  * index rows matched case-insensitively (2021 'CALCULATED INDEX' vs later
    'Calculated Index')

## OPEN BUG (acquisition layer, not extraction)
8 PDFs in 2026 are named with 'nan' in a date field, e.g.
  ssy_2026_nan_20260807-Atlantic-Capesize-Report.pdf
The real date IS in the name as 20260807; one field upstream got nan. Extraction
is unaffected (all 8 yield 17 rows / 12 routes / 6 index keys). Fix in the SSY
scraper's filename construction, not here.

## Status
Source 1 advanced_shipping complete. Source 2 star_asia complete.
Source 3 ssy complete. Next: pick source 4 and repeat the method.
