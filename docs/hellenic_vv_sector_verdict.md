# hellenic vessel_valuations - the `sector` column was wrong on 3,090 of 12,350 rows

**Date:** 2026-10-08 (cron, source-by-source)
**Source:** `corpus/02-hellenic/vessel_valuations/` (261 HTML report pages -> 255 distinct reports, 2021-07 .. 2026-09)
**File changed:** `data/extracted/series/hellenic_vv_matrix_series.csv` (12,350 rows, values only, row count unchanged)
**Runner fixed:** `scripts/extract/publishers/run_hellenic_vv_matrix.py` (`parse_vv_matrix_markdown`)

## The defect (measured, not inferred)

The series' `sector` column contradicted the row's own `vessel_class` on **2,969 of 12,350 rows (24.0%)** before the
fix, e.g. `sector=Bulkers, vessel_class="Containers Handy"` (855 rows), `Bulkers / Containers Pmax` (868),
`Bulkers / Containers Post Pmax` (657), `Unknown / Tankers LRI` (76).

Two independent causes in `parse_vv_matrix_markdown`:

1. **Keyword scan ordered wrong.** With no `#` section heading the sector was inferred from the class name with the
   BULKER list tested before the CONTAINER list. `"Containers Handy"` contains `handy` and `"Containers Pmax"`
   contains `pmax`, so both matched the bulker branch first and every container column that reuses a bulker word was
   filed as `Bulkers`.
2. **A table TITLE was read as a section heading.** The heading test was `sector_word in line`, so the markdown
   title `# VV Mini Matrix - Weekly Change Bulkers` (8 cached reports) set the section for the whole table.

## Ground truth

The publisher's own header row, from the cached LlamaParse markdown of the matrix graphic that IS the data source
(`data/extracted/cache_hellenic_vv/*.md`) - verbatim, 2026-01-28:

```
| Year | Tankers VLCC | Tankers Suez | Tankers Afra | Tankers LR1 | Tankers MR |
| Bulkers Cape | Bulkers Pmax | Bulkers Supra | Bulkers Handy |
| Post Pmax | Containers Pmax | Containers Handy | Containers Fmax |
```

Each column states its own sector in the cell. The one bare column, `Post Pmax`, is written
`Containers<br/>Post Pmax` in 75 of 261 reports, sits between `Bulkers Handy` and `Containers Pmax` in the fixed
13-column header, and carries benchmark sizes `7000 / 6500 / 5500` (TEU) - never the `<n>k` DWT form every bulker
column uses (`Bulkers Pmax` = 80k/75k/82k). It is the container column.

## The fix (per-source, in the runner)

* `_sector_from_header(vclass)` - the sector PREFIX the header cell states wins (`Containers Handy` -> Containers).
* **Conflict veto:** if the class token is unique to another sector (`Bulkers Fmax`, `Bulkers MR` - OCR garbles of
  container/tanker columns), the prefix is NOT trusted and the keyword-derived sector is kept. A wrong label is
  worse than a missing one.
* Bare `Post Pmax` -> Containers (publisher's dominant form + the TEU benchmark, above).
* A `#` heading now sets a section only when the line **equals** a sector name.
* The original keyword scan is kept as the fallback, so only header-prefixed columns change.

## Regeneration - cache only, no API spend

All **255/255** reports' companion matrix images are in the LlamaParse cache (verified before the run), so
re-running the runner made **0 API calls**: 255 reports -> 12,350 matrix observations, 124 benchmark sales.

## Control (same document set before and after)

| check | result |
|---|---|
| rows | 12,350 -> **12,350** |
| non-`sector` cell multiset | **identical** (no row added, removed or otherwise altered) |
| rows whose `sector` changed | **3,090** (3,080 unique + 10 of the 15 known duplicate rows) |
| transitions | `Bulkers -> Containers` 2,631, `Unknown -> Tankers` 262, `Bulkers -> Tankers` 143, `Unknown -> Bulkers` 54 |
| self-contradictory rows (class states a sector, column disagrees) | **2,969 -> 18** |
| `hellenic_vv_benchmark_sales_series.csv` / `hellenic_vv_sales_series.csv` | content unchanged (LF restored; not in the diff) |
| register gate `verify_registers.py` | **ALL PASSED** - 180 CSVs / **639,749** == JSON == MD, 0 mismatches |
| trial vs the page | 2021-07-06 (header `Age`) and 2026-01-28 (header `Year`) both reproduce their header's 13 columns exactly |

## Carried, NOT fixed (named)

* **15 exact-duplicate rows** in 5 clusters (`2026-01-28` x13 classes, `2026-08-18` x2) - the source image's own
  OCR lists the `10`-year row twice, so this is an artifact of the cached markdown, not of the sector logic. Left.
* **18 rows in 3 OCR-garbled header cells** (`Bulkers MR` 6, `Bulkers Fmax` 6, `Tankers Supra` 6) keep the sector
  their class word states (Tankers / Containers / Bulkers) - the prefix is unreadable, so nothing was invented.
* `Bulkers Post Pmax` appears in 4 reports; those keep the prefix.

## Caveat on the md tier (found the hard way)

`data/extracted/md/hellenic/vessel_valuations/**` is written by **two** runners. The delivered `.md` layout
(`## Sector Market Commentary` + the S&P transaction table) comes from
`scripts/extract/publishers/run_hellenic_vessel_valuations.py`; `run_hellenic_vv_matrix.py` writes an OLDER layout to
the same paths and **overwrites it**. The first regeneration of this run clobbered all 255 `.md` files that way;
they were reverted and are **byte-identical to HEAD**, and the 255 gitignored `.tables.json` sidecars were restored
by re-running the sales runner (whose output is byte-identical for all 255 md files - that is the control that the
delivered layout was reproduced, not approximated). Anyone re-running the matrix runner must revert the md tier.

Also: this series is **not app-displayed** (`index.html` has 0 references to it). The fix is a correctness repair in
a delivered, register-"Verified" series, not a visible change.

## Reproduce

```
python3 scripts/extract/publishers/run_hellenic_vv_matrix.py     # cache-only reparse (py312: llama_parse)
git checkout -- data/extracted/md/hellenic/vessel_valuations     # keep the sales-runner md layout
python3 scripts/extract/verify_registers.py
```
