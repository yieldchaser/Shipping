# baltic_ncfi - duplicate-key dedup VERDICT (2026-10-03)

**Status: EXECUTED and PROVEN, LOSSLESS - the largest remaining un-diagnosed census item (148 rows).**
This is an HTML source (`corpus/08-baltic/ningbo/`), not a PDF one, which is why it was still open.

## Cause - two Wayback captures of the SAME Ningbo page

`baltic_ncfi_series.csv` held **148 duplicate rows across 144 keys** (140 pairs + 4 triples). Every
one is the same weekly index table captured under two different Wayback filenames, e.g.:

    2020-06-05  Ningbo - Europe  640.68 / prev 649.39 / -1.34
      from  2020-05-29_Ningbo-Containerised-Freight-Index31_ningbo.html
      and   2020-06-05_Ningbo-Containerised-Freight-Index3_ningbo.html

The two HTML files are NOT byte-identical (md5 287fde89 vs 36344e93) but display the **same table**:
the 29-May-named capture's body reads `Date: 29 May 2020` yet its table columns are
`2020-06-05 | 2020-05-29` with the identical values. The extractor stamps `issue_date` from the
table's current-week column, so both captures produce the same 2020-06-05 rows.

## Fix - controlled row-filter (lossless)

Key = every column except `source_file`. One row kept per key, preferring the capture whose *filename*
date equals `issue_date` (better provenance), else lexicographically first. Applied to the delivered
CSV AND wired into `run_baltic.py` (at the NCFI stacking step, `[dedup] dropped N ...`) so a future
re-run cannot reintroduce them.

    2,180 -> 2,032 rows   (148 dropped)

## Control

* Key multiset: `PRE minus POST` = **148 removed, 0 added** on the full-column key.
* Distinct `(issue_date, route)` pairs: **2,024 before AND after, 0 PRE-only, 0 POST-only** - no
  index observation lost.
* `baltic_reports_metadata.csv` (2,218 rows) untouched.
* Idempotence: re-applying the runner's dedup to the fixed file drops **0**.

## Notes

* `data/extracted/**` is gitignored - the deduped CSV is a working-tree artefact, NOT committed.
* Pre-fix copy `scratch/baltic_ncfi/PRE_baltic_ncfi_series.csv`; filter `scratch/baltic_ncfi/filter.py`.
