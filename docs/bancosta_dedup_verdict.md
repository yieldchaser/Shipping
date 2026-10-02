# bancosta - duplicate-key dedup VERDICT (2026-10-03)

**Status: EXECUTED and PROVEN, LOSSLESS (44 rows).** Clears the census's bancosta item.

## Cause - one byte-identical W39 pair

All 44 duplicate rows come from a single byte-identical PDF pair (md5 `2914f821b746cf4360bf77b70c05c0b4`):

    corpus/01-brokers/banchero_costa/2026/banchero_costa_2026_W39_Bancosta-Weekly-2026-39.pdf
    corpus/01-brokers/banchero_costa/2026/bancosta_30_09_2026_banchero_costa_weekly_market_report_week_39_2026.pdf

Both were parsed, so each W39 row is written twice: **sales 24, newbuilding 14, demolition 6 = 44**.

## Fix - controlled row-filter (lossless)

A re-run is NOT available here: banchero's table text layer is glyph-ciphered and is recovered by
LlamaParse (paid, credits exhausted per the state file), so the delivered CSVs are the artefact of
record and a controlled row-filter is the correct instrument. Key = every column except `source_file`;
one row kept per key (lexicographically-first `source_file`, matching the shared `doc_dedup` convention).

    bancosta_sales_series.csv         3,244 -> 3,220   (-24)
    bancosta_newbuilding_series.csv   2,391 -> 2,377   (-14)
    bancosta_demolition_series.csv      965 ->   959   (-6)

## Control

* Full-column key: `PRE minus POST` = removed (24 / 14 / 6), `POST minus PRE` = **0 added**.
* Entity sets identical pre/post with 0 PRE-only and 0 POST-only:
  sales (issue_date, vessel_name, imo) 3,219; newbuilding (issue_date, record_type, vessel_type,
  sector) 2,039; demolition (issue_date, record_type, segment_location, vessel_name) 959.
* Post dup keys: **0** on all three.

## Flag: the register's Banchero Costa block is broadly stale (NOT re-measured here)

`docs/EXTRACTION_REGISTER.md` line 22 lists counts from a different era than the delivered files -
measured today: `bancosta_freight_rates` 20,321 (register 25,715), `bancosta_ffa` 7,618 (7,659),
`bancosta_vhss` 469 (3,413), `bancosta_commodities` 8,447 (2,319), `bancosta_fx` 244 (941),
`bancosta_container_fixtures` 267 (922), `bancosta_secondhand_matrix` 1,891 (1,911). The series were
written by several writers at different times (mtimes 09-29 / 09-30 / today). I updated only the three
series this change touched; the rest of the bancosta block needs its own re-measure pass.

## Notes

* `data/extracted/**` is gitignored - the deduped CSVs are working-tree artefacts, NOT committed.
* Pre-fix copies `scratch/bancosta_dedup/PRE_bancosta_*.csv`; filter `scratch/bancosta_dedup/filter.py`.
