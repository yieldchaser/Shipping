# fearnleys byte-duplicate dedup - VERIFIED, 2026-10-02 00:2x

Continues the corpus-wide double-count fix (`docs/decimal_comma_regeneration_verdict.md`
section 7; ssy/affinity closed in `docs/ssy_dedup_verdict.md` / `docs/affinity_dedup_verdict.md`).
fearnleys is a **RECORD-ONLY** source (already ingested structurally per the user's
2026-09-2x decision) - this is a hygiene fix on the delivered series, not new data.

## Measured before

| item | value |
|---|---|
| corpus PDFs under `corpus/01-brokers/fearnleys` | **263** |
| md5 duplicate groups / documents to skip | **3** |
| rows in the delivered `fearnleys_rates_series.csv` | 17,142 |
| ...of which carry `source_file` from a skipped stem | **121** |
| rows whose composite pkey collides with a kept copy | **0** |

Dropped stems (the second collection route, byte-identical PDFs):
`fearnleys_2026_W37_Fearnleys-Weekly-Report-` (58 rows, issue_date derived 2026-09-09),
`fearnleys_24_09_2026_fearnleys_week_39_2026` (63 rows, 2026-09-24),
`fearnleys_2026_W40_Fearnleys-Weekly-Report-_-Fearnpulse` (0 rows - its pkey collapsed
onto the keeper's, which is why the census's per-series count was 121, not 242).
121 = 58 + 63, exactly.

## The trap here was the MERGE MAP (this source only)

`run_fearnleys_normalized.py` does not rebuild its series from scratch: it seeds
`existing_map` from the PREVIOUS `fearnleys_rates_series.csv` (keyed on
`issue_date|chapter|section|label`) and writes `existing_map | this-run's-rows`.
The dedup filter was already wired at the enumeration (3 documents skipped), but that
alone changes **nothing** in the delivered file - the skipped copy's 121 stale rows are
re-loaded from disk on every run. Patched: the load loop now skips any row whose
`source_file` stem is in the skip set and reports the count.

## The run

```
[dedup] skipped 3 byte-identical duplicate document(s)
Total Fearnleys PDFs to normalize: 260
[dedup] dropped 121 stale row(s) carried by a skipped duplicate stem in the existing series CSV
Successfully normalized 260 Fearnleys files.
```

260/260, 0 failures, 10,710 rows generated in-pass, ~11 min wall.

## The control (the point of this run)

PRE minus the rows of a skipped stem must equal POST as an exact multiset on every column:

```
PRE 17142  POST 17076  (expected 17142 - 121 = 17021, plus new documents)
rows ADDED vs control: 55   rows REMOVED vs control: 0
  all 55 additions are ONE document, issue_date 2026-10-01 / report_week 40:
  corpus/01-brokers/fearnleys/2026/fearnleys_01_10_2026_fearnleys_week_40_2026.pdf
  PRE held 0 rows for it; corpus mtime 2026-10-01 14:31 (collected today, after the
  previous series build). Legitimate new issue, not a control break.
CONTROL excluding that newly-arrived document -> added 0, removed 0 => PASS
```

So the dedup removed exactly the 121 duplicate rows and moved **nothing else** - no other
document's values were re-parsed differently.

## md tier

The 3 skipped stems' md/sidecar artefacts existed in BOTH the flat dir and the `2026/`
mirror - **12 files quarantined** to `scratch/dedup_census/quarantine_fearnleys/` (kept,
not deleted), so the double-count cannot be re-ingested. Re-scan for orphans: **0**.
Post md tier: 260 `.md` + 520 `.tables.json` (flat + year mirror, a pre-existing shape).

## Status

fearnleys: 260/260 canonical documents, 17,076 rows, **0 duplicate-stem rows**. CLOSED.
Pre-fix copy `scratch/dedup_census/PRE_fearnleys_rates_series.csv`; probe/verify/patch
scripts in `scratch/dedup_census/`. `data/extracted/` is gitignored, so the corrected CSV
is disk-only; the code fix and this record are the commit.

## Remaining in this census (unchanged, re-measured on disk 2026-10-02 00:0x)

| source | dup rows still delivered | blocker |
|---|---|---|
| agora | **94** (`agora_indicators_series.csv`) | no stacker exists in the repo - `run_agora.py` writes sidecars only, so a re-run changes nothing; needs a rebuilt stacker or a controlled row-filter |
| star_asia | **25** measurable (deals 9 + demolition 16) | 4 writers still unpatched (`charts`, `ferrous_scrap`, `price_trends`, `stack_unstacked_tables`); census says 58 across 7 series |
| intermodal | **16** (`intermodal_macro_series.csv`; +bunkers/stocks) | `run_intermodal_finance.py` patched but STALE (parser fixed twice since) - re-run changes VALUES, must be page-verified |
| carriers | **327** | a PARALLEL agent's - untouched |
