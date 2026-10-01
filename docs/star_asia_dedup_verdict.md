# star_asia byte-duplicate dedup - VERIFIED, 2026-10-02 00:4x

Continues the corpus-wide double-count fix (`docs/decimal_comma_regeneration_verdict.md`
section 7; ssy / affinity / fearnleys closed in `docs/ssy_dedup_verdict.md` /
`docs/affinity_dedup_verdict.md` / `docs/fearnleys_dedup_verdict.md`).

## Measured before - the census's 58 was already stale

A fresh scan of ALL TEN `star_asia_*` series on disk found **25** duplicate-stem rows,
all in the two series `run_star_asia_tables.py` writes:

| series | rows | dup-stem rows |
|---|---|---|
| star_asia_deals_series.csv | 3,358 | **9** |
| star_asia_demolition_series.csv | 3,136 | **16** |
| 5y_history / ferrous_scrap / iron_ore / ldt_comparison / metals_energy / scrap_price_trends / valuation_matrix | 7,073 | **0** |

The census's 58 (demolition 16, valuation_matrix 10, ferrous_scrap 10, deals 9,
metals_energy 8, 5y_history 4, iron_ore 1) no longer holds: 33 of those rows are gone -
those writers rebuild with `open(..., "w")` and their series were rebuilt since the
census, so only the 25 remain. Corpus: **199 PDFs / 197 unique / 2 duplicate groups**
(`star_asia_2026_W38_Market-Report-Week-38`, `star_asia_28_09_2026_...week_39`).

## The run

`python3 scripts/extract/publishers/run_star_asia_tables.py` (per-source runner; the filter
was wired at its own enumeration in an earlier run, and this runner REBUILDS with
`open(...,"w")`, so the enumeration filter alone is sufficient - no merge-map trap here).

```
[dedup] skipped 2 byte-identical duplicate document(s)
Starting Star Asia extraction across 197 PDFs...
total_documents 197 | sidecars_updated 197 | indicative_tables_repaired 195
indicative_series_rows 3120 | deals_series_rows 3349 | snp_sales_rows 0
```

## The control (the point of this run)

PRE minus the rows of the copies the RUN excluded == POST as an exact multiset:

```
star_asia_deals_series.csv:      PRE 3358 - dropped 9  -> expected 3349 | POST 3349 | added 0 removed 0 => PASS
star_asia_demolition_series.csv: PRE 3136 - dropped 16 -> expected 3120 | POST 3120 | added 0 removed 0 => PASS
```

So 25 duplicate rows removed and **nothing else moved**. (All 25 came from the W38 copy;
the W39 pair's rows had already collapsed onto the keeper.)

## NEW FINDING - the skip set is NOT stable across a run of this source's own runner

`doc_dedup._richness()` measures the shape of the `.tables.json` SIDECAR, and
`run_star_asia_tables.py` REWRITES every sidecar it processes. So the ranking that decides
the keeper changes as a side effect of the run:

| | skip set |
|---|---|
| immediately BEFORE the run | W38 + `star_asia_28_09_2026_...week_39` |
| immediately AFTER | W38 + `star_asia_2026_W39_Market-Report-Week-39-1` |

The W39 pair is byte-identical (`md5 41955f76f905095ccaaa5abc41df8e49` both). Before the
run both sidecars were `{stem, issue_date, year, broker, charts:[4]}` -> richness 4 each ->
tie broken lexicographically -> `..._2026_W39_...` kept, `28_09_2026` skipped. The run then
wrapped the kept copy's sidecar into a 2-element LIST ([old dict, clean indicative table]),
so its measured richness fell 4 -> 2 and `28_09_2026` (still a dict, richness 4) became the
keeper on the NEXT computation. **No data was lost** - the charts dict survives as element 0
of the list - but the ranking metric is not idempotent.

Consequences, measured and bounded:
- Values are unaffected (the PDFs are byte-identical); only filename-derived fields
  (`source_file`, `issue_date`) can switch copy between runs.
- It made a naive post-hoc control WRONG: re-computing the skip set after the run
  mis-attributed the W39-1 rows, reporting a phantom "55 added / 14 added". The control
  above uses the skip set the RUN actually used, which is the correct invariant.

PROPOSED FIX (NOT shipped - it changes keeper choice for EVERY publisher, so it needs its
own measured run): make `_richness()` recursive - a list contributes its own items PLUS the
richness of each dict element - so a container-rewrap cannot change the ranking. Verify by
computing every publisher's skip set before and after the change and confirming which pairs
flip.

## md tier

The 2 copies the run excluded had md + sidecar on disk (they would let the same issue be
ingested twice): **4 files quarantined** to `scratch/dedup_census/quarantine_star_asia/`.
Residual: 0. Post 2026 md tier: 35 `.md`.

## Status

star_asia: 197/197 canonical documents, deals 3,349 + demolition 3,120 rows, **0 duplicate-stem
rows** across all ten series. CLOSED. Pre-fix copies `scratch/dedup_census/PRE_star_asia_*.csv`;
scripts `scratch/dedup_census/{scan_starasia,verify_starasia}.py`. `data/extracted/` is
gitignored - the corrected CSVs are disk-only.

## Remaining in this census (re-measured 2026-10-02 00:0x)

| source | dup rows still delivered | blocker |
|---|---|---|
| agora | **94** (`agora_indicators_series.csv`) | no stacker exists in the repo (`run_agora.py` writes sidecars only) - a re-run changes nothing; needs a rebuilt stacker or a controlled row-filter |
| intermodal | **16** (`intermodal_macro_series.csv`; +bunkers/stocks) | `run_intermodal_finance.py` patched but STALE - a re-run changes VALUES, must be page-verified |
| carriers | **327** | a PARALLEL agent's - untouched |
