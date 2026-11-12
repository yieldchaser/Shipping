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

### 5. Vessel identity material in the corpus is name-heavy (P3 finding, no code change)
Measured on the built corpus (not a parser bug — a property of broker prose; logged because it
caps what identity resolution can prove):
- Printed IMO appears only in AIS/registry sidecars and in a minority of sale/demolition tables;
  1,894 checksum-valid printed IMO tags across all 185,454 tagged chunks. Broker fixture text is
  effectively IMO-free, which is why plan §6.4 requires corroborating DWT/built-year/yard.
- P2 claim-derived provisional vessels: 11,135 entities, of which 2,484 are single-token names
  and 18 are pure generic words (`STAR`, `SEA`, ...). Regex-level plausibility gates in
  `kb/p3_tag.py` reject those at the tagging layer instead of inventing identity:
  `skipped_implausible_vessel=2,527`, `ambiguous_vessel_norms=3,564` (names shared by >3 IMOs),
  `ais_name_alias_skipped=2,333`, `vessel_alias_dropped_ambiguous=2,873`.
- Counterparty columns yield 3,076 `company:int:*` provisional companies, 795 single-token; 1,171
  generic patterns (`ONE`, `GAS`, `SHIPPING`, ...) are refused as text aliases
  (`skipped_generic_company`) because they would tag every sentence.
- Consequence accepted at P3: identity is precision-first. 305 merges PASSED the audit at 0.99
  precision; unresolved provisional names stay provisional and are tagged as such (visible
  ambiguity) rather than guessed. Recall cost is documented in `kb/reports/p3.md`.
