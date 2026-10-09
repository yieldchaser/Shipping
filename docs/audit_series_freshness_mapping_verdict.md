# `audit_series_freshness.py` - FOUND + FIXED two lying-instrument bugs (2026-10-09 19:xx)

Run: scheduled source-by-source job. Nothing left to EXTRACT (re-verified: all 18 publishers
CLOSED, corpus 0 changes, newest broker content still W40, W41 not arrived). This run instead
fixed the project's own durable freshness instrument, which was reporting false zeros.

Register gate re-run before and after: `verify_registers.py` = ALL PASSED (180 CSVs /
**639,756** logical rows == JSON == MD, 0 mismatches). No data file changed by this fix.

## Defect 1 - series keyed by `split('_')[0]`, so multi-word publishers fell into non-existent buckets

`scripts/extract/audit_series_freshness.py` mapped each `*_series.csv` to a source with
`b.split('_')[0]` (with a lone `intermodal_` special-case). A multi-word publisher therefore
keyed to a bucket that is not an md dir:

| series prefix | old key | md dir it belongs to | files |
|---|---|---|---|
| `advanced_shipping_*` | `advanced` | advanced_shipping | 5 |
| `star_asia_*` | `star` | star_asia | 10 |
| `bancosta_*` | `bancosta` | banchero_costa | 10 |
| `golden_destiny_*` | `golden` | golden_destiny | 1 |
| `best_oasis_*`, `athenian_*`, `gms_*` | `best`/`athenian`/`gms` | hellenic (their md tier) | 12 |
| `singletons_*` | `singletons` | (no md dir; never printed) | 1 |

The report loops `sorted(md_dirs)`, so a bucket with no md dir is dropped twice over: its md dir
prints **0 CSVs / 0 rows**, and the files themselves never appear. Measured before: **4 md dirs
read 0** (`advanced_shipping`, `banchero_costa`, `star_asia`, `golden_destiny`), **39 of 174**
series files invisible or mis-attributed - a false "these sources have no series" reading,
exactly the class of error the project's own doctrine warns about ("state the population a query
covered; if the query cannot see a source type, say so").

### Fix
Resolve each series file against the REAL md sources: longest whole-token prefix match, an alias
table for the publisher name variants (`bancosta -> banchero_costa`; `athenian`/`gms`/`best_oasis`
-> `hellenic`), else keep the file's own bucket. The report now iterates
`set(md_dirs) | set(series_by_src)` so nothing is invisible.

## Defect 2 - 13 series files (19,077 rows) counted as 0 for lack of a recognized date column

`max_date_in_csv()` returned early (`None,None,0`) when no fieldname was in `DATE_COLS`, so a
file with rows but an unrecognized date column contributed **0** to the row total:

- `drewry_ais_*` (10 files) use **`published_date`** - a real date column, simply absent from
  `DATE_COLS`.
- `hellenic_iron_ore_commentary_series.csv` (1,179 rows) carried a **BOM-prefixed
  `issue_date`** (`\ufeffissue_date`), so `c.lower() in DATE_COLS` failed on the BOM.
- `ssy_capesize{,_index}_series.csv` (17,610 rows) hold `route/base/year` - genuinely no date
  column; these are counted as rows now but still contribute no date (correct).

### Fix
Add `published_date` to `DATE_COLS`, strip a leading BOM (`c.lstrip('\ufeff')`) before matching,
and count every row regardless of whether a date column was found.

## Measured before / after (same tree, same run)

```
BEFORE: sum #csv = 135   sum rows =  509,867   (4 md dirs read 0; 39 files dropped)
AFTER : sum #csv = 174   sum rows =  632,134   (all *_series.csv present)
```

**Control (independent instrument):** an independent `csv.reader` count of every
`data/extracted/series/*_series.csv` = **174 files / 632,134 rows** - the fixed audit now
matches it exactly. (`632,134 + 7,622 metadata rows = 639,756` = the register; the audit's glob
is `*_series.csv`, so the 6 `*_metadata.csv` files, 7,622 rows, are outside its stated scope.)

Per-source deltas that were false zeros:
`advanced_shipping` 0->5 csv / 0->18,687 rows; `banchero_costa` 0->10 / 0->46,480;
`star_asia` 0->10 / 0->17,015; `golden_destiny` 0->1 / 0->5,320; `hellenic` 32->44 / 259,010->275,831
(+athenian/gms/best_oasis 12 files, +commentary BOM 1,179); `drewry` 25,000->25,288;
`ssy` 5,676->23,286; new bucket `singletons` 1 / 46 rows.

## Scope / NOT changed
- No data file, series CSV, md, or register touched. Register gate re-run GREEN both sides.
- The audit still reads only `*_series.csv` (not `*_metadata.csv`); that scope is now explicit.
- Pre-existing file-wide style (E701/E702 semicolons/colons, unused `json`) left as-is - it
  predates this run and there is no repo ruff config enforcing it.
