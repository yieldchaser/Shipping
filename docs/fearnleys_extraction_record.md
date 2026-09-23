# Fearnleys extraction - RECORD of a run that was already in flight

**Read `docs/fearnleys_verdict.md` first: the source is SKIPPED.** At 03:05:53,
while this extraction was already running, the user committed that decision -
the publisher is already ingested structurally from its own Hasura backend
(11,732 commentary notes, a 62MB fixtures CSV, tanker/dry route dailies, T/C
rates, S and P deals), so the PDFs are a strictly worse copy. I re-verified that
independently: `data/derived/fearnleys_*` holds all of it.

This file is the measured record of the work that was in flight, kept because
the LAYOUT findings and the seven defects below transfer to the sources that
are not yet ingested. It does not dispute the SKIP decision.

**Run: 257/257 documents, 0 failures, 267s.** Output
`data/extracted/md/fearnleys/` (git-ignored): 257 `.md` + 257 `.tables.json` +
257 `.charts.json`, 11 MB, 16,326 typed rows.
Pipeline `scripts/extract/publishers/run_fearnleys.py`.

| era | docs | rows | what it is |
|---|---|---|---|
| A-cards | 150 | 9,378 | HTML page printed to PDF, 19-20pp, median 71 rows/doc |
| B-rows | 83 | 6,948 | 2021-2022 poster + the 7pp 'printer version', exactly 84 rows/doc |
| D-image | 23 | 0 | QUARANTINED: content is a raster, text layer = browser chrome |
| C-garbled | 1 | 0 | QUARANTINED: 2018 W29, font encoding to control characters |

## How it was verified

1. **Faithfulness** - every extracted value must appear verbatim in the SAME
   document's text layer. Measured **NOT-IN-TEXT = 0** on a seeded random sample
   across all four eras.
2. **Reconciliation** - every value-shaped line in a document is accounted for:
   extracted row / change-column cell / chart axis tick / chapter marker.
3. **Printing check** - each value's bbox tested against the RENDERED page:
   **199 of 233 documents with rows had every sampled value printed** where the
   text layer says it is (see the disclosure below for the other 34).

**Vision was NOT available to this run's model** (no image tool in the session),
so this is reading the positioned text layer plus a pixel test of the rendering,
not a glance at a PNG. Pages are rendered to `scratch/fearnleys/renders/`.

## Seven defects, every one found by a check and none by a row count

1. **A size anchor is not portable.** `fearnleys_2023_W39` is the same card
   layout rendered at ~10% scale (fonts 1.5/1.8/1.3pt where 2026 W18 has
   15/18/13.5pt, IDENTICAL positions). An 18pt value threshold returned **0
   rows** on it while returning 71 on the normal file.
2. **'k'-suffixed chart axis labels** ('25k','150k') have the same shape as a
   value: 19 phantom cards (90 rows where the page holds 71).
3. **Cross-page label carry-over** attached 'Spread MGO/380 CST' to a chart tick
   '2500' - a phantom row in an otherwise clean file.
4. **Prose sits at the same x as headings**, so a "has something above it" test
   dropped the real heading 'Rates' and shifted every later section label.
5. **Chapter markers** ('01'..'06', bare numbers at the margin) were read as card
   values: 2026 W17's last row was 'Prices | 05'.
6. **Every change value was dropped** on the printer-era files: the change cell's
   text is `$1.2` + newline + a PRIVATE-USE-AREA arrow glyph, and a plain
   `strip()` leaves it, so the cell failed the value test. Found by reconciling
   lines - the row count was already correct at 84.
7. The modal-x guard crashed with an empty `max()` on the poster files. Caught
   by the trial, before the bulk run.

Fixes 1-7 took the row total from 16,360 to 16,326: **34 phantom rows removed,
no real row lost** (v2 is row-for-row identical to v1 on every normal file).

## Correction to the first survey

The 02:52 survey said "Era B (2021-2022) is 1-page posters, PROSE only, no
table". **Wrong** - the probe printed the first 22 lines and stopped, and the
rate table sits ~1,500pt below. Those files carry a full 84-row table with the
same routes and vessel sizes as the 2026 cards. The limitation was the probe.

## Disclosed, not hidden

* **34 documents (13%)**: on ONE page each the value text renders faint or blank
  in the raster while the label beside it renders dark - the card bands are
  embedded images painting over the value. Value bbox min luminance 227 against
  a page mean of 251, while the label in the same band reads 80. The text layer
  is colour-coded and complete (values blue #2655a2, negative changes red
  #dc2626). `scratch/fearnleys/visibility.json` lists all 34.
* **23 raster-only documents** quarantined with no typed rows (six are 441-page
  files). OCR is not installed on this box.
* **1 garbled document** (2018 W29), 31% printable characters.
* Charts are RASTER in every era: no chart series taken.
* Numbers are ISO/US in every era (`$67,028`, `$13.24`, `WS 21.0`, `4.14%`).
