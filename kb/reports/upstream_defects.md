# Upstream defects & known gaps (found during build, NOT fixed here)

Protected inputs (`corpus/`, `data/`, `scripts/`) are frozen by `kb/tripwire.py`.
Everything below is recorded for the upstream owners of the extraction pipeline;
the KB build works around it or leaves the gap explicit (`corpus_known_gaps`, PLAN 4.6).

## P2 (series CSVs, broker tables, SEC XBRL)

### 1. SEC XBRL ingestion skipped — no SEC_USER_AGENT in the environment
- Source: `docs/GRAPHRAG_AGENT_TASK.md` L123 ("If `SEC_USER_AGENT` is unset, SKIP the XBRL
  ingestion and log it here").
- Effect: `series_id = sec:<TICKER>:<concept>` facts are absent; `v_company_fin` holds only
  broker-report/CSV-derived company numbers. PLAN 4.3 `raw_cell_found_all_sec` is satisfied
  vacuously (0 `sec:*` observations). Re-run `kb/p2_xbrl.py` after exporting
  `SEC_USER_AGENT="name email"` to add them (idempotent, `provenance='xbrl'`).

### 2. `seabrokers_fleet_moves_series` CSV has no numeric `value` column
- File: `data/extracted/series/seabrokers_fleet_moves_series.csv` (+ `_binary` variant).
- The file is a categorical / transaction-table dump (fleet-move rows), header contains no
  `value`-like column, so the long/wide loaders emit **0 numeric observations**. Not forced
  through a fabricated value column; the stem is recorded as a defect by `kb/p2_series.py`.
- Upstream fix: re-extract this bulletin with a numeric value column (or as a
  transaction table so it belongs to 4.2/D9 rather than 4.1).

### 3. No sidecar carries charter/fixture rows
- `*.tables.json` sidecars expose `reported_sales`, `sales`, `demolitions` (and non-deal
  blocks `indicative_demolition_prices`, `newbuilding_prices`, `charterer_rows`,
  `orderbook_age_rows`). `charterer_rows` is a Poten charterer-share ranking, NOT fixtures.
- Effect on 4.2: fixtures/TC assessments cannot be sourced from sidecars; `fixture` rows come
  only from the curated CSV specs in `kb/p2_transactions.SPECS`, and `v_fixture` is thinner
  than `v_sale`. Recorded in `corpus_known_gaps`.
- Upstream fix: sidecar extractor should emit a `fixtures` block (vessel, charterer, TC/day,
  period, delivery) for the fixture-bearing bulletins.

### 4. Sidecar `source_file` does not always resolve to a `document`
- `kb/p2_tables.py` offline dry run: `unresolved_doc` high (≈14.8k of 13.6k claims before
  doc-map resolution was exercised against the real DB). Sidecars whose `source_file` names a
  file not present in `data/extracted/md/` cannot be attributed to a `doc_id`.
- Effect: those claims still cluster into `transaction` rows (dedupe key is content-based) but
  their `mention.doc_id` is NULL, so doc-level provenance is missing for them.
