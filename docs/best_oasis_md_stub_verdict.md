# Best Oasis md tier: empty price tables in the committed ingest, restored in the working tree (independently verified)

Run 2026-10-06 ~13:3x, branch `auto/extract-fixes-2026-10-06-deepreview`. Cron job, unattended.
Nothing else was extracting. **The best_oasis md fix is the PARALLEL AUTOMATION's live work-in-progress
(file mtimes advanced 13:27 -> 13:42 DURING this session, alongside `docs/EXTRACTION_REGISTER.md` and
`docs/CORPUS_CADENCE_AND_AUDIT.md` at 13:42). I did not commit it. This doc records only my independent
verification of it.**

## The defect (measured)

The automation's ingest commit `b0fa2b3be` ("reports: ingest latest market reports and update cadence
audit 2026-10-06", 13:21 IST) **created** the best_oasis md tier at the canonical path
`data/extracted/md/hellenic/demolition/best_oasis/<year>/` with **empty indicative-price tables** -
header rows only, no data rows. Example (HEAD): `best_oasis_2022-02-19_..._18_Feb.md` and
`best_oasis_2025-01-04_..._compressed.md` both carry `| Location | ... |` then `|:---|` and nothing.

Measured over the 150 best_oasis md that the working tree rewrites:

| | count |
|---|---|
| best_oasis md modified in the working tree | 150 |
| ... of those, HEAD version has NO price data row (`^\| India \|`) | **134** |
| working-tree version HAS the price data row | **150** |

So 134 md files lost their price table in the committed tier; the working tree restores all of them.
The same defect class was committed-fixed for GMS/Alibra in `1eb52d5c3` (13:32); best_oasis is its
uncommitted analogue.

## Does the restoration point at real data? (verified against the source PDFs, not file counts)

The working-tree md is the output of the source's own runner `scripts/extract/publishers/run_best_oasis_demolition.py`
(its header - `title: "Best Oasis Weekly Ship Recycling Report - {date}"`, `source: "best_oasis"`,
`pages:`, `tables_count:` - matches the runner's md writer exactly).

I checked every `$`-value in every price-table row of the 150 rewritten md against the text layer of its
own `source_file` PDF (`pymupdf`, `page.get_text()`), accepting both plain and comma-grouped forms:

| measured | value |
|---|---|
| price values checked | **1,509** |
| found verbatim in the source PDF text | **1,481 = 98.1%** |
| not found | 28 |
| ... of which in `2022-12-28` (PDF text layer EMPTY, extracted from a cached parse) | 24 (unverifiable, not wrong) |
| ... of which in `2025-11-22` (PDF text layer partial, 4,148 chars) | 3 (unverifiable) |
| genuine single-value candidates | **2 = 0.13%** |

The two candidates: `$654` (HARMONY, `2022-03-05`) and `$334` (SHENG TAI, `2025-03-29`) - the vessel
name IS in the page text but the price is not. Every other value reconciles. (One apparent miss,
`$1275` BOW FLOWER, is CORRECT: the page prints `1,275` with a "high quantity of STST 316" note - my
first checker just failed on the comma form.)

## Path-field check

All **269** working-tree best_oasis md have a `source_file:` that resolves to an existing PDF (0 stale).
An earlier working-tree revision carried a spurious `/2022/` segment in the 2022 files' `source_file`;
that was corrected by the 13:42 regeneration (the PDFs are flat under `best_oasis/`).

## Series layer unchanged

The series CSVs were NOT rewritten by this md fix (mtime 12:55): `best_oasis_deals_series.csv` 892 rows,
`best_oasis_demolition_series.csv` 867, `best_oasis_exchange_rates_series.csv` 167 - matching
`docs/EXTRACTION_REGISTER.md`. The price/deal DATA was never lost at the series layer; only the .md
tier was stubbed.

## Verdict

The automation's best_oasis md restoration is CORRECT and worth committing (134 empty-table files ->
data, 98.1% of values confirmed in the source page text, 0 unresolvable path refs). It is not mine to
commit (live WIP). Residual: look at `$654` / `$334` if the .md tier is treated as ground truth.

## Completeness of the restoration (what is STILL empty)

After the restoration, 269 worktree md remain, 238 carrying a price data row. Of the **31** that still
do not, **30 have a data-bearing sibling md for the SAME issue_date** (the `_<hash>` duplicate filenames) -
i.e. redundant stale copies, not a data gap. Exactly **one** has no data-bearing sibling:

* `best_oasis/2026/2026-06-13_..._best-oasis-weekly-recycling-market-report-05-june-2026_ship-recycling-market-insight-week-2_416dd50ae58c.md`
  - no price data row; its PDF (`corpus/02-hellenic/demolition/pdfs/2026-06-13_..._416dd50ae58c.pdf`, 8 pp)
  holds `India` and 135 three-digit numbers, so the table is plausibly recoverable. NOTE its `source_file`
  is the flat path (not under `best_oasis/`), i.e. a different writer than the runner's canonical set, and
  a 2026-06-06 md already covers the same "05-june-2026" week.

So the practical residual is **1 md file**, not 31 - the other 30 are duplicate filenames.
