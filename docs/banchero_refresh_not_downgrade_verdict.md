# Banchero series refresh: measured TO BE A SCHEMA DOWNGRADE, not applied (2026-10-05 15:1x, hourly supervisor)

## What this run verified independently
1. Chunk tier (audit #1 open item) is HEALED - re-measured from knowledge/manifests/documents.jsonl
   vs knowledge/chunks/*.jsonl: declared 106,174 chunks across 93 files; on-disk 106,503 across
   those same 93 files; **SHORT files 0**. (6 additional zero-byte files exist under knowledge/chunks
   that are NOT declared in the manifest - parent/placeholder shards, not a shortfall.)
2. corpus.duckdb (read-only) unchanged vs last reported: cells 6,726,703; catalogue 189,481;
   series 5,743; series_points 1,193,579. Reconciles.

## The carried NEXT-RUN target (14:2x entry) and why it must NOT be run blind
The 14:2x entry said: refresh the 7 reproducible series via build_banchero_series.py + filter.py
"(this WOULD add W36/W37/W39)". Measured this run against the script's own output already sitting in
scratch/banchero_gap/series_after_build/ (built 14:40, restored from afterwards):

| series | current (delivered) | build_banchero_series output | delta |
|---|---|---|---|
| bancosta_sales_series | 3,220 rows / 173 distinct source_file / 17 cols (vessel_name, buyers, price_raw, ss...) | 4,796 rows / 247 distinct source_file / 16 cols (vessel, buyer, seller...) | SCHEMA CHANGE |
| bancosta_newbuilding_series | 2,377 | 1,960 | -417 |
| bancosta_demolition_series | 974 | 1,294 | +320 |
| bancosta_secondhand_matrix_series | 1,891 | 1,891 | 0 |
| bancosta_container_fixtures_series | 267 | 267 | 0 |
| bancosta_vhss_series | 469 | 469 | 0 |
| bancosta_fx_series | 244 | 244 | 0 |
| bancosta_freight_rates_series | 20,321 | 20,321 | 0 (script does NOT emit freight) |

**Conclusion:** running build_banchero_series.py is NOT a safe drop-in. It emits a DIFFERENT (thinner)
sales schema than the delivered file (no vessel_name/buyers/price_raw/ss; uses vessel/buyer/seller),
which is the same class of downgrade as the lion md case. It also does NOT emit freight/ffa/commodities,
so it cannot close the W36/W37/W39 freight gap at all - the "would add W36/W37/W39" claim is unverified
and my measurement contradicts it for the freight series.

## State of the gap (unchanged, owner decision)
- bancosta_freight_rates_series.csv still ends at W35 then W38; W36/W37/W39 have no freight rows.
- No current script emits those 3 big series (freight/ffa/commodities). Closing the gap needs a NEW
  bespoke banchero freight consumer (parse the md freight tables), not a re-run of an existing script.
- Three-baseline test still LOW priority: the freight benchmarks already exist in the feeds
  (clarksons fearnleys_benchmark_rates_continuous / gibson_tanker_rates_continuous_daily) and
  index.html references 0 bancosta_* series. Not user-visible.

## Not done / deliberately not changed
- Did NOT run build_banchero_series.py against data/extracted/series (schema downgrade; not displayed).
- Did NOT run stack_banchero_series.py (still guarded, still broken for current layout).
- No data mutated this run; corpus.duckdb opened read-only.
