# ssy byte-duplicate dedup - VERIFIED, 2026-10-01 23:0x

Continues the corpus-wide double-count fix (`docs/decimal_comma_regeneration_verdict.md`
section 7). ssy's runner had the shared `byte_duplicate_stems()` filter wired but had
never been re-run, so the delivered series still carried the duplicate rows.

## Measured before

| item | value |
|---|---|
| corpus PDFs under `corpus/01-brokers/ssy` | **530** |
| md5 duplicate groups | **14** (pairs, 14 duplicate documents) |
| rows in the delivered `ssy_route_rates_series.csv` | 5,280 |
| ...of which attributable to a skipped (duplicate) stem | **120** |
| rows in `ssy_capesize_index_time_series.csv` | 528 |
| ...of which attributable to a skipped stem | **12** |
| total double-counted rows | **132** (matches the census in the state file) |

The 14 groups are the two known collection routes: `ssy_YYYY_YYYYMMDD-{Atlantic,Pacific}-...`
vs `ssy_2026_nan_YYYYMMDD-...` and vs the `ssy_DD_MM_YYYY_...` route names. All pairs are
byte-identical PDFs (md5-equal); richness (sidecar row count) was equal on 13 of 14 groups,
and only the W39 Atlantic pair differed (12 rows vs a 1-row stub sidecar) - the row-count
rule kept the real extraction, which is exactly why the keeper is chosen on content.

## The run

`python3 scripts/extract/publishers/run_ssy_complete.py` (per-source runner, unchanged
strategy; the filter is wired at its own enumeration point). Full re-parse from the PDFs,
not a sidecar re-stack, because this runner builds its series in the same pass.

```
[dedup] skipped 14 byte-identical duplicate document(s)
[ssy] Starting complete overhaul across all 516 reports...
[SSY COMPLETE] All 516 reports successfully processed!
  -> Generated 5160 route rate observations
  -> Generated 516 index time series records
  -> Total execution time: 82.8s
```

## The control (the point of this run)

Pre-fix file minus the rows whose `source_file` is a skipped stem must equal the post-fix
file as an exact multiset, on every column and both series:

```
ssy_route_rates_series.csv:
  pre=5280  dropped(dup stems)=120  expected_post=5160  actual_post=5160
  rows ADDED vs control: 0   rows REMOVED vs control: 0
  CONTROL: PASS (exact multiset)
ssy_capesize_index_time_series.csv:
  pre=528  dropped(dup stems)=12  expected_post=516  actual_post=516
  rows ADDED vs control: 0   rows REMOVED vs control: 0
  CONTROL: PASS (exact multiset)
OVERALL: PASS
```

So the dedup removed exactly the duplicate rows and moved **nothing else** - no value was
re-parsed differently.

## md tier

The dropped stems' md/sidecar/chart artefacts were still on disk and would have let the
same issue be ingested twice. **41 files quarantined** to `scratch/dedup_ssy/quarantine/`
(kept, not deleted). Post: `data/extracted/md/ssy/` 516 `.md` + 516 `.tables.json`,
`charts/ssy/` 510 `.charts.json`, 0 files for a skipped stem.

NOTE (pre-existing, not introduced here, not fixed here): the ssy md tier writes every
document to BOTH the flat dir and a `<year>/` subdir - 516 flat + 516 mirrored = 1,032 md
for 516 documents. Same flat+year mirror already recorded for ism and poten in the state
file. It doubles the md tier but not the series.

## Status

ssy: 516/516 documents, 5,160 route rows, 516 index rows, 0 duplicate rows. CLOSED.
Pre-fix copies: `scratch/dedup_ssy/PRE_*.csv`. `data/extracted/` is gitignored, so the
corrected CSVs are disk-only; the code fix (`a7618c051`) and this record are the commit.
