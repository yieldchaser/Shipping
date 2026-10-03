# Derived table DB rebuild - verdict (2026-10-03)

Runner: `scripts/extract/build_table_db.py --rebuild --out data/extracted/corpus`
(run as a background process, ~25 min, offline CPU, no API spend).
Gate: `scripts/extract/check_measured_rules.py` -> **all 11 measured rules present**, exit 0.

## Premise corrected before acting

The prior run's NEXT-RUN TARGET said the DB "still excludes freshly extracted
documents" and to confirm signal/agora/clarksons/intermodal/xclusiv additions
become visible. **Measured false as stated:** a full walk of `data/extracted/corpus`
found **0 of 16,803 `tables.jsonl` newer than the 2026-09-23 DB build** (and 0 newer
than 2026-09-28). The recent work for those publishers is the **md tier**
(`data/extracted/md/<pub>/<year>/*.tables.json`) and the series CSVs - neither is
consumed by this builder, which reads only `corpus/<group>/<stem>/tables.jsonl`.
signal's and breakwave's `tables.jsonl` are **empty (0 records)** - HTML sources with
no tables - which is why they show few catalogue docs, not a build gap.

So the rebuild had nothing new to *add*; its real effect is to apply the parser and
dedup fixes committed since the DB was last built (2026-09-23 13:26 IST).

## Measured delta (old DB vs rebuilt DB, same inputs)

| metric | before | after |
|---|---|---|
| docs | 8,144 | 8,144 |
| tables (catalogue) | 192,535 | **189,481** (-3,054) |
| cells | 6,946,400 | **6,726,703** (-219,697) |
| is_numeric cells | 2,757,974 | 2,648,633 |

**Control 1 - the dedup is content-preserving, no value lost.** The 243,247 cells
absent from the rebuilt DB were checked one-by-one: **243,247 / 243,247 have a cell
with identical (doc, page, engine, row_idx, col_idx, value) still present; 0 have no
twin.** This is the `table_content_sig` dedup added 2026-09-28 (camelot-stream
returns the same region twice on some pages); by construction every dropped value is
kept by its identical twin. The dropped tables are real duplicates, e.g.
banchero_costa weeklies hold four byte-identical `COMMODITY PRICES / BUNKERS`
camelot tables on one page.

**Control 2 - the parser corrections are real (join on value+position, 7,252,807
matched cells).**
- **40,598 cells had a WRONG `num_value`, all off by exactly 1000x** (ratio test:
  0 non-1000x changes). Source: shipbrokers 40,586, hellenic 12. Examples:
  `3.370` 3.37 -> **3370.0** (BDI), `52.315` 52.315 -> **52315.0** ($/day T/C),
  `5.768` -> 5768.0. This is the period-thousands convention for
  advanced_shipping/star_asia/agora that the delivered DB predated.
- **1,768 cells became numeric** that were previously non-numeric, incl. the
  **429 multi-period** cells (`153.800.000` -> 153,800,000) and `$ -space` currency
  cells. (`is_numeric` on 2+ period groups: 0/429 before -> 429/429 after.)

Net: the delivered derived DB had 40,598 broker cells reading 1000x too small and
1,768 resolvable cells invisible. The rebuild fixes both with **zero content loss**.

## What was deliberately NOT shipped

The DB's derived series layer (`series` 5,280 / `series_points` 1,212,902 /
`series_daily` 941,115 / `doc_dates` 5,216) is a **snapshot built from the OLD cells**.
Regenerating it is unsafe right now, measured:
- `scripts/extract/build_series_sql.py --write` produces 143,783 series and **fails
  its own integrity gate**: `orphans=267`, `duplicate(series,date)=172,339`.
- `scripts/extract/build_series.py --write` writes a different schema (no
  `series_daily`), so it cannot refresh the layer alone.
The pre-existing snapshot was therefore **restored** (from
`scratch/db_rebuild_20261003/corpus.duckdb`) rather than replaced. The layer needs
ONE settled producer before it is refreshed from the rebuilt cells.

## Artefacts

Parquet/DuckDB under `data/extracted/corpus/db/` are git-ignored (derived). Backup of
the pre-rebuild DB + diff/control scripts: `scratch/db_rebuild_20261003/`. No register
change (the register tracks the series CSVs, which were not touched).

## Next target

Refresh `series`/`series_points`/`series_daily` from the rebuilt cells, after
settling a single producer and making `build_series_sql.py` pass its integrity gate
(orphans / duplicate (series,date)). Until then the rebuilt `cells` are correct but
the derived series layer still reflects the pre-fix parsing.
