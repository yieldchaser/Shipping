# Derived series-layer refresh — verdict (2026-10-03)

Runner: `scripts/extract/build_series_sql.py --db data/extracted/corpus/db/corpus.duckdb
--write --min-points 20` (offline CPU, ~2m13s, no API spend).

Closes the prior run's NEXT-RUN TARGET: the derived table DB's `cells` were rebuilt
(40,598 cells fixed from 1000x-wrong) but the series layer was still a snapshot built
from the OLD cells. The producer is now SETTLED and SHIPPED.

## Producer settled: `build_series_sql.py` (py producer retired here)

The delivered snapshot was itself produced by the SQL producer at `--min-points 20`
(measured: its `series` table's minimum `points` = 20, schema `series_id/source/
entity_key/measurement_key/block_no/instrument_class/points/distinct_dates/first_date/
last_date/entity/measurement`). So there was no producer to *choose* — only a stale
snapshot of the same producer to refresh at the same threshold. `build_series.py`
(the Python one) is NOT used: it writes a different schema (no `series_daily`) and
collapses per-date points silently (`pts[d]=value`, last-wins).

## Integrity gate now PASSES (it previously failed at orphans=267)

The uncommitted fix in `build_series_sql.py` (this run committed it):
- the series key delimiter changed `|` -> `\x1f`. The entity/header TEXT can itself
  contain `|` (fearnleys "weekly report | fearnpulse"); the old `split_part()`
  recovery mis-read those keys so the representative-spelling join DROPPED their
  series -> 267 orphan points / 162 series_ids.
- `series` is now built from the component columns (GROUP BY source, entity_key,
  header_key, block_no, class_key), never re-parsed from the id string.
- `duplicate(series,date)` is disclosed (BY DESIGN), not part of the fail gate: every
  raw observation is kept in `series_points`; `series_daily` is the one-row-per-
  (series,date) view carrying `min/max/spread/n_observations/n_distinct_values`, so a
  multi-value date is visible, never averaged.

Measured on the shipped layer: **orphans=0, mismatched points=0**, gate exit 0.

## Measured delta (git-ignored DB; backup in scratch/db_series_refresh/)

| table | before (old cells) | after (rebuilt cells) |
|---|---|---|
| cells | 6,726,703 | 6,726,703 (unchanged) |
| series | 5,280 | **5,241** |
| series_points | 1,212,902 | **1,167,616** |
| series_daily | 941,115 | **942,263** |
| doc_dates | 5,216 | 5,216 |
| daily rows with >1 distinct value (disclosed) | — | 72,847 |
| duplicate(series,date) in series_points | — | 149,584 (BY DESIGN) |

Series ids are byte-different from the old snapshot because the delimiter changed
(`|` -> `\x1f`); joined on the COMPONENT key (source, entity_key, measurement_key,
block_no, instrument_class), **5,239 of 5,241** new series match an old one.

## Control — the 1000x cell fix propagates into the series

Joined old vs new on the component key + date: of 2,121,669 matched observations,
**172,075 are exactly `new == old * 1000`** (e.g. `shipbrokers|kamsarmax|dwt`
2022-02-07: 81.666 -> 81666.0). Zero are `old == new*1000` other than trivial 0.0
rows. The residual "changed" pairs are block/row renumbering after the 219,697-cell
dedup (the series key is positional), not value corruption.

## Ground truth (no vision tool this session — substituted positional page text)

`advanced_shipping_2022_W06_ADVANCED-MARKET-REPORT-WEEK-6.pdf` p3: the word
`Kamsarmax` at (x=25.0, y=284.1) sits on the SAME row as `81.666` at (x=142.7,
y=284.1) — directly under the `Dwt` column header (x=145.7). advanced_shipping is the
EUROPEAN-convention source (60.000 = sixty thousand), so 81.666 = **81,666** deadweight
tonnes. The fetched series now reads 81,666.0. The whole family is now physically
plausible where before it was absurd: KAMSARMAX DWT 79,200..85,688, SUPRAMAX
50,029..59,963, VLCC 159,233..441,585, HANDYSIZE 18,901..43,368.

## Consumers / blast radius (measured)

- No app consumer: no `.html`/`.js`/`.json` in the repo reads `series`/`series_points`/
  `series_daily` or `corpus.duckdb`.
- No test/CI consumer: `tests/` and `.github/` reference neither (the one `build_series`
  hit, `tests/test_fearnleys_desk.py`, is `scripts/fearnleys/build_series_cache.py`, a
  different file).
- `check_measured_rules.py` -> all 11 measured rules present, exit 0.
- The register tracks the series CSVs (not this DB layer) and is untouched.

## Residuals (measured, not fixed)

- The `label_series` table in the DB is from an older pipeline and was not refreshed
  (not produced by this script).
- 1,696 of 6,912 doc stems are undated and excluded from series (unchanged behaviour).
