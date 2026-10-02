# intermodal finance writer - dedup + STALE re-run: 144 rows added, 36 dup-stem rows dropped, control exact

**Date:** 2026-10-03 01:2x IST  ·  **Source:** `corpus/01-brokers/intermodal` (257 PDFs, 2021-2026)
**Runner:** `scripts/extract/publishers/run_intermodal_finance.py` (writer for macro / maritime_stocks / bunkers)
**Files:** `data/extracted/series/intermodal_{macro,maritime_stocks,bunkers}_series.csv`
**Trigger:** the pending dedup census item for this writer ("36 rows from the dropped W38 copy, and STALE
since the parser was fixed twice"). Both halves proved real; the re-run also closed a FRESHNESS gap the
census did not name.

## What the run did

`run_all()` rebuilds each of the three CSVs from scratch (`open(...,"w")`), so a controlled re-run is a
full rebuild. Enumerated **257 corpus PDFs -> 255 canonical** (`[dedup] skipped 2 byte-identical
duplicate document(s)`; the two skipped stems are
`intermodal_23_09_2026_..._week_38_2026...` and `intermodal_30_09_2026_..._week_39_2026...`).
255/255 parsed, no failures, ~4 min.

| series | PRE rows | POST rows | removed | added |
|---|---|---|---|---|
| `intermodal_macro_series.csv` | 3,739 | **3,787** | 16 | 64 |
| `intermodal_maritime_stocks_series.csv` | 3,119 | **3,152** | 11 | 44 |
| `intermodal_bunkers_series.csv` | 2,260 | **2,287** | 9 | 36 |

## The dedup half - and the STALENESS that hid behind it

**Removed (the census's 36):** exactly the rows stamped with the dropped W38 byte-dup stem
(`intermodal_23_09_2026_...`): macro 16, stocks 11, bunkers 9. POST holds **0** rows with a skipped stem.
The keeper `intermodal_2026_W38_...` is byte-identical (`md5 5bfbdb3b4bd5fda35f71520270ab5891`) and now
supplies those rows.

**Added (the part the census missed):** the delivered finance CSVs were built 2026-09-28 22:28, and
**four 2026 documents collected after that date were never written into them** - the second collection
route's `_2026_WNN_` copies arrived 2026-09-29 21:58 (W36, W37, W38) and 2026-10-01 15:18 (W39). The
newest issue in the corpus (week 39) was therefore MISSING from all three finance series. All four are now
present. Added by source, each 16 / 11 / 9 rows: `..._2026_W36_...`, `..._2026_W37_...`,
`..._2026_W38_...` (the keeper, replacing the removed copy), `..._2026_W39_...`.
Net new weeks: **W36, W37, W39** (+48 / +33 / +27 rows); W38 is a same-value rename.

## Control - nothing else moved

`PRE minus rows whose source_file stem is in the run's skip set` compared to `POST` as an **exact multiset
on every column**:

| series | control base | POST | added | removed |
|---|---|---|---|---|
| macro | 3,723 | 3,787 | 64 | **0** |
| maritime_stocks | 3,108 | 3,152 | 44 | **0** |
| bunkers | 2,251 | 2,287 | 36 | **0** |

Zero rows removed beyond the skip set, and every addition belongs to one of the four genuinely-new
documents. The skip set was frozen from the SAME `byte_duplicate_stems()` call the run consumed (the
state file's keeper-instability trap: recomputing it after the run mis-attributes rows).

## Verification against the document, not the metric

No vision tool is available in this session (stated, not substituted silently). Method used: reconcile
every numeric cell of the new rows against **that document's own PDF text layer** (separators normalised,
trailing-zero-insensitive float compare).

| document | macro | stocks | bunkers | issue_date (cover line) |
|---|---|---|---|---|
| 2026 W36 | 48/48 | 33/33 | 27/27 | 2026-09-08 |
| 2026 W37 | 48/48 | 33/33 | 27/27 | 2026-09-15 |
| 2026 W38 | 48/48 | 33/33 | 27/27 | 2026-09-22 |
| 2026 W39 | 48/48 | 33/33 | 27/27 | 2026-09-29 |

**100.0% (540/540) of the new numeric cells are present verbatim in the source PDF.** Issue dates equal
the publisher's own cover line on all four. (An earlier pass read 44/48 etc. - every "miss" was my
normaliser: the page prints `7,718.60` and the cell is `7718.6`.)

## Residual - disclosed, not fixed

**2026 W08 is a degraded capture.** Its finance page (p6) has 1,106 text chars and **2** vector drawings
where the neighbouring W07 has 2,869 chars and **200** drawings on the same page index; p3 has 68 chars vs
1,600. The Commodities & Ship Finance tables are image-only in this copy, so the runner correctly extracts
**0** rows from it. It is a raster page, not a parse bug; recovering it needs OCR, which this box does not
have. One document, one week (2026-02-24). Not worth a bespoke OCR path unless the user asks.

Evidence / scripts: `scratch/finance_rerun/{measure_pre,check_stems,gap,compare,compare2,verify2,miss}.py`,
PRE copies `scratch/finance_rerun/PRE/`, skip set `scratch/finance_rerun/skipset.json`, run log
`scratch/finance_rerun/run.log`. `data/extracted/` is gitignored - the corrected CSVs are on disk only.
