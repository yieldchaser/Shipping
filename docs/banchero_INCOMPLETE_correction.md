# Banchero Costa - my "243/243 complete" was OVERSTATED. Tables and charts were missed.

## The user's challenge, and it stands
The user rendered banchero pages 9, 10, 13 and 14 and pointed out what they contain:
dense structured tables - VLCC/Suezmax/Aframax freight rates (TD3C, TD15, TD6, TD7,
TD19, TC1-TC11) with WS and $/day columns, a REPORTED SALES table (vessel, IMO, DWT,
built, yard, buyers, price), BALTIC SECONDHAND ASSESSMENTS, and DRY BULK FFA
ASSESSMENTS with forward curves, plus charts throughout.

My banchero deliverable captured THE PROSE ONLY. No tables. No chart series. So
"243/243, 0 failures" was a completeness claim the work did not support.

## Root cause of the missing tables - found, not guessed
The table text on those pages is GLYPH-MOJIBAKED in the PDF text layer. Measured on
2026 W03 page 9:

    find_tables() returns: ['', '!"#$ %FG()" *G(', '']
    the rendered page shows:  Unit | 16-Jan | 9-Jan | W-o-W | Y-o-Y

while the PROSE on the SAME PAGE extracts perfectly:
    'CRUDE TANKER MARKET'
    'VLCC rates reached WS 130 for 270,000 mt AG/China ...'

The discriminator is the FONT SUBSET, by size:

    Calibri     8.5pt  n=104  '!"#$"'                    GARBLED (table cells)
    Calibri-Bold 8.5pt n=41   '!"#$'                     GARBLED (table headers)
    Calibri     11.0pt n=36   'The market is hotter...'  CLEAN  (prose)
    ArialMT     6.9pt  n=26   '!"'                       GARBLED
    Calibri     7.5-7.7pt n=48 '!'                       GARBLED

The embedded subsets (AAABNJ+ArialMT, BKSOEQ+Calibri) have broken encodings at the
small sizes and correct ones at 11pt. A PDF viewer renders both fine, which is why
the user sees clean tables while extraction gets punctuation soup. This is the same
Banchero glyph issue noted earlier as "decode_mojibake.py structurally inapplicable
(0 Latin-Extended glyphs)" - it is NOT inapplicable, it just needed a different
mapping than the Latin-Extended one.

## Scale
12 of 41 sampled documents (~29%) carry garbled small-font text, i.e. roughly 70 of
the 243 banchero documents. Affected pages cluster on the data pages (5,6,8,9,10,11).

## The existing tables.jsonl I reused is ALSO defective
I converted only text.jsonl, so this was not used - but it should be recorded that
data/extracted/corpus/shipbrokers/banchero_costa_*/tables.jsonl is NOT a usable
table source either. On 2026 W03 it holds 78 rows and MISSES every real table:
    TD3C              NOT FOUND
    REPORTED SALES    NOT FOUND
    FFA Jan-26        NOT FOUND
What it did capture is the 3-column PROSE misread as a table, e.g.
    ['', 'COMMODITY NEWS -', '']
    ["China's 2025 oil", "China's fuel oil", 'American country']
And charts/ holds small image fragments (155x46, 400x866), not usable chart series.

## The fix - started, not finished
The cipher is a simple character substitution and is solvable from known plaintext.
Established from the header row alone:
    !->U  "->n  #->i  $->t  %->1  F->6  G->-  (->J  )->a
giving '!"#$ %FG()" *G(' -> 'Unit 16-Jan 9-Jan'.
More known plaintext is available and abundant: ship names, IMO numbers and DWT
values from banchero_deals.parquet (3,120 rows) constrain the same tables, so the
mapping can be derived rather than guessed.

Two viable routes, in order of promise:
  1. Derive the substitution mapping per font subset and apply it, then extract the
     tables normally. Repeatable and cheap at scale.
  2. Render the table region and OCR it. Robust and font-independent, slower.

## What must NOT have happened but did
I declared banchero complete on the strength of a file count and a clean exit. The
same failure mode as the intermodal backfill (252/252 while 16.5% wrong) and the
xclusiv labels (85% labelled while wrong). Three times in one night a completeness
metric substituted for verifying that the CONTENT was present.

## Status
Banchero is NOT complete. Its prose is extracted and verified. Its tables require the
glyph fix above, and its charts are not extracted at all. The verdict file
docs/banchero_verdict.md should be read with that qualification.

## Also to check
Whether other sources in this project have the same small-font glyph corruption. The
'garbled' route flag exists in banchero's own pages.jsonl; equivalent flags or font
subsets should be checked for advanced_shipping, star_asia, ssy, xclusiv, fearnleys
and intermodal rather than assumed clean.
