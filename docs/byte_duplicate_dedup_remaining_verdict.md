# CLOSED 2026-10-01 (night run) - advanced_shipping byte-duplicate double-count FIXED and PROVEN

Continues the byte-duplicate defect recorded in `docs/decimal_comma_regeneration_verdict.md`
section 7 (xclusiv + intermodal fixed there, the rest "measured, NOT yet fixed").

## 1. Re-measured the census from the DELIVERED CSVs (not from the earlier doc)

Method: for each publisher, hash every `corpus/01-brokers/<pub>/**/*.pdf` with md5, take the
groups with >1 copy, then count how many DELIVERED series rows carry a dropped copy's
`source_file`. `source_file` comes in three shapes (bare stem / stem.pdf / full corpus path),
so it is normalised to basename-minus-extension first - the earlier pass missed the path-shaped
ones and under-counted star_asia.

| publisher | dup groups | rows double-counted in delivered series | status |
|---|---|---|---|
| advanced_shipping | 3 | **148** (sales 44, secondhand 64, newbuilding 21, demolition 16, demo_sales 3) | **FIXED this run** |
| ssy | 14 | 132 (route_rates 120, capesize_index_time 12) | open |
| fearnleys | 3 | 121 (rates 121) | open |
| agora | 4 | 94 (indicators 94) | open |
| star_asia | 2 | 58 (7 series) | open |
| affinity | 7 | 48 (tce 38, bda 6, indices 4) | open |
| carriers | 4 | 327 | other agent's - untouched |
| intermodal | 2 | **36 STILL PRESENT** in 3 series (macro 16, maritime_stocks 11, bunkers 9) | open |
| ism | 3 | 0 | nothing to do |

## 2. NEW FINDING - the earlier "intermodal 36 -> 0" claim does not hold

The state file says "intermodal likewise 36 -> 0". The delivered files say otherwise:
`run_intermodal_finance.py` (a SEPARATE writer for macro / maritime_stocks / bunkers) was never
patched, and those three series still carry 36 rows from the dropped W38 copy. Verified by
counting `source_file` against the duplicate group. Same class of error the skill warns about:
read the artefact, not the report.

## 3. The keeper rule had to be measured, not guessed

`scripts/extract/publishers/doc_dedup.py` (new, shared plumbing; each publisher still owns its
own pipeline) picks ONE copy per md5 group. The keeper is the copy with the RICHEST extraction,
ties broken lexicographically.

Two traps found by measuring:

* **A file-size "richness" rule is wrong.** The sidecar stamps its own filename into every row,
  so the DD_MM_YYYY collection-route name makes a byte-identical extraction look larger and
  wins the tie-break on the WRONG copy. Measured: it flipped the advanced_shipping keeper and
  produced a 28-row POST_not_in_PRE delta that was pure filename provenance. Fixed by counting
  table ROWS (list-valued keys) instead.
* **Lexicographic-first can keep a STUB.** Measured: star_asia 2026 W38 has a 1,182-byte dict on
  one copy and a 29,127-byte list on the other; agora W38 88 bytes vs 13,524; ssy 2025-09-28
  345 bytes vs 2,746. Row-count richness keeps the real extraction in every one of those.

Also measured: for every duplicate pair checked, the two sidecars differ ONLY in
`stem`/`source_file`/filename-derived `issue_date` (e.g. fearnleys 2026-09-10 vs 2026-09-09,
xclusiv 2026-09-15 vs 2026-09-14) - the extracted VALUES are identical, so keeping either copy
loses no data.

## 4. advanced_shipping - the fix and the proof

`run_advanced_shipping_tables.py` (the only writer of all 5 of its series) gained:
* `duplicate_stems()` - the shared filter, applied to its own `CORPUS_DIR.rglob("*.pdf")`;
* `--stack-only` - rebuilds the 5 series CSVs from the sidecars already on disk, never
  re-parsing a PDF. This is deliberate: the sidecar holds the exact row lists
  `process_document()` produced, so the rebuild cannot silently re-extract anything.

Run: `python3 scripts/extract/publishers/run_advanced_shipping_tables.py --stack-only`
(2.9 s; 250 of 253 sidecars kept, dedup skipped 3).

CONTROL (the strong one): pre-fix CSVs kept in `scratch/dedup_20261001/`. For each series,
`pre_rows minus (rows whose source_file is a dropped copy)` was compared as a multiset against
the post-fix file:

| series | pre | removed | post | verdict |
|---|---|---|---|---|
| advanced_shipping_demo_sales_series.csv | 604 | 3 | 601 | EXACT MATCH |
| advanced_shipping_demolition_series.csv | 2,016 | 16 | 2,000 | EXACT MATCH |
| advanced_shipping_newbuilding_series.csv | 1,909 | 21 | 1,888 | EXACT MATCH |
| advanced_shipping_sales_series.csv | 6,105 | 44 | 6,061 | EXACT MATCH |
| advanced_shipping_secondhand_matrix_series.csv | 8,110 | 64 | 8,046 | EXACT MATCH |

**148 rows removed, and every surviving row is byte-identical to what was shipped.** The rebuild
changed nothing else - no value moved, no row lost.

## 4b. INCIDENT - a concurrent process truncated the delivered series mid-run

At 22:19:16, while this run was working, a SECOND python process started
(`run_advanced_shipping_tables.py --sample`, PID 18956) and at 22:20:10 wrote a 3-document
sample over all five delivered advanced_shipping CSVs - sales went 6,061 -> **74 rows**. The
corrected files were restored by re-running `--stack-only` (601/2,000/1,888/6,061/8,046) and
verified byte-identical to the post-fix hashes. Separately, a `git` process held
`.git/index.lock` and had to be waited out, and a third process was seen reading
advanced_shipping_sales_series.csv with pandas - the user runs several agents on this repo at
once, so re-check the artefact after any concurrent activity.

GUARD ADDED: `--sample` no longer writes the series CSVs (it parses 3 documents and would
replace the delivered output). Control: re-ran `--sample`; all five CSVs unchanged (md5 OK) and
a re-run of `--stack-only` afterwards reproduces the same files, so the sample did not change
any extracted content either.

## 4c. Runners patched now (filter executes; full re-run still pending)

The shared filter is wired into each publisher's OWN enumeration/stack point and each patched
runner was executed to prove the filter path works (skipped counts measured 2026-10-01 22:2x):

| runner | skipped stems | expected |
|---|---|---|
| run_advanced_shipping_tables.py | 3 | 3 (RAN + VERIFIED) |
| run_ssy_complete.py | 14 | 14 |
| run_fearnleys_normalized.py | 3 | 3 |
| run_agora.py | 4 | 4 |
| run_star_asia_tables.py | 2 | 2 |
| run_affinity_tables.py | 7 | 7 |
| run_intermodal_finance.py | 2 | 2 |

Those six have NOT yet had their full re-run, so their delivered CSVs still carry the
double-counted rows (132/121/94/58/48/36). ALSO NOT YET PATCHED: star_asia's other four writers
(`run_star_asia_charts.py`, `run_star_asia_ferrous_scrap.py`, `run_star_asia_price_trends.py`,
`stack_unstacked_tables.stack_star_asia`) and affinity's second writer
(`polish_affinity_markdown.py`, which also writes indices and re-reads the PDFs).

## 5. Still open, in the order to work them

Each needs its own runner patched at BOTH points (enumeration AND stack) - affinity/agora keep a
resumable `_run_state.json`, so a re-run alone changes nothing:

1. ssy - `run_ssy_complete.py` builds its series from PDFs in the same pass (`SRC.rglob` +
   series write inside one run), so it needs a full re-run (~516 docs, 1 page each).
2. fearnleys - `run_fearnleys_normalized.py`, same shape (PDF-driven, 260 docs).
3. agora - `run_agora.py` (213 docs); no separate stacker in the repo.
4. star_asia - FIVE writers: `run_star_asia_tables.py` (deals/demolition/snp),
   `run_star_asia_charts.py`, `run_star_asia_ferrous_scrap.py`, `run_star_asia_price_trends.py`
   and `stack_unstacked_tables.py` (valuation_matrix).
5. affinity - TWO writers for tce/bda: `run_affinity_tables.py` (sidecar-only stack, cheap) and
   `polish_affinity_markdown.py` (writes all three incl. indices, re-reads PDFs).
6. intermodal - `run_intermodal_finance.py`, the 3 residual series, sidecar-based.
7. carriers - 327 rows, but owned by a PARALLEL agent; do not touch without checking.

NOTE: `data/extracted/` is gitignored, so the corrected CSVs are on DISK, not in git. The
register's per-file counts remain pre-dedup inflated.
