# poten survey - measured 2026-09-29 (cron, unattended)

**Verdict so far: poten is PROSE-FIRST and already essentially covered. The apparent
"fixtures stop in 2014" gap is the publisher retiring the table, not a missing extraction.**

## What we have

| measured | value |
|---|---|
| PDFs | **1,087** (`corpus/04-poten/pdfs/<year>/`, 2004-2026, weekly) |
| metadata | `data/extracted/series/poten_opinions_metadata.csv` **1,087 rows = 100% of the corpus** (issue_date, title, author, pages, tables_count, word_count) |
| knowledge tier | `knowledge/chunks/poten_tankers_<year>.jsonl` for **every year 2004-2026** (23 files) |
| tables | `poten_top_charterers_series.csv` 755 rows (2004-2026) · `poten_fixtures_series.csv` 100 rows (2004-2014) |
| runners | `run_poten.py`, `run_poten_clean.py`, `run_poten_full_cover_to_cover.py`, `run_poten_llamaparse.py`, `sync_poten_corpus.py` |
| app display | **RAG only** - `index.html` consumes `knowledge/chunks/poten_tankers*.jsonl`. The two series CSVs are NOT displayed. |

## The content type is PROSE, not tables

A recent report is **one page, ~3,400 chars, ~800 words**, with no table at all
(`Weekly Opinion - January 9 2026 - Show Me The Barrels.pdf`, `Weekly Opinion - July 10
2026 - Tanker Midterms - 2026 Edition.pdf`): "fixtures" appears only inside sentences.
Across the whole corpus **only 49 of 1,087 reports contain any table**.

## The tabular content is captured - no gap

Checked every one of the 49 tabular reports against both series:

* **49 / 49 have charterer rows** (0 missing) in `poten_top_charterers_series.csv`.
* 36 of them carry exactly ONE table and no fixture rows - i.e. the charterers table only.
  The fixtures table simply is not in those documents.
* `poten_fixtures_series.csv` therefore covers exactly the reports that printed a fixtures
  table, and its last date is **2014-03-14** - the publisher retired the feature.

The charterers table is a **sporadic** feature, not monthly: 2 reports/year in 2024, 2025 and
2026 (`2024-01-05`+`2024-06-28`, `2025-01-03`+`2025-02-07`, `2026-01-09`+`2026-07-10`).
A text scan of all **285** reports from 2020-2026 for a charterer/fixture table phrase found
only 2, consistent with a rare feature rather than an under-detecting parser.

## Three-baseline test (is it already ours?)

1. **Feeds** (`data/**/*.csv`): no poten fixture/charterer feed found.
2. **Our own extraction**: the three poten CSVs above.
3. **App display**: only the RAG knowledge chunks; the tables are not rendered anywhere.

A table would only be GENUINELY_MISSING if absent from all three. Nothing measured here is.

## Open for the next run (not chased - would need a look, and this session has no vision tool)

* `tables_count` in the metadata comes from the metadata extractor, so it could undercount.
  The phrase scan above is a weak proxy (a table can have a header that does not match the
  regex) and it found 2 reports where the metadata says 2 per year - suggestive, not proof.
  To close it: read a run of consecutive 2024 reports cover to cover and count the tables by
  eye.
* Nothing here justifies an extraction run. **Do not build a from-zero poten runner.**
