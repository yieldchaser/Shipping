# Corpus coverage: what is genuinely unbuilt (measured 2026-09-28, unattended run)

Written after the three-baseline test on `corpus/04-poten`, which was proposed as
the "biggest first" next source. It is **already fully extracted** - the lead was
stale. This file records the measured coverage so the next run does not repeat it.

## The poten test result: ALREADY OURS - do not build an extractor

| baseline | finding |
|---|---|
| our own extraction | **1,087 `.md` + 1,087 `.tables.json`** in `data/extracted/md/poten/`, one per PDF, year counts matching the corpus year by year |
| our own series | `poten_opinions_metadata.csv` **1,087 rows** (= the PDF count), `poten_top_charterers_series.csv` 755, `poten_fixtures_series.csv` 100 |
| the app | `index.html` references `knowledge/chunks/poten_tankers.jsonl` / `poten_tankers_2026.jsonl` |

Content check: 0 zero-byte `.md`, min 811 bytes, max 13,656, 4.7 MB total. The
metadata CSV carries `source_file` (`corpus/04-poten/pdfs/<year>/...`) and
`md_file` fields that point at paths which actually exist - i.e. no stale
path references after the corpus migration.
`docs/EXTRACTION_REGISTER.md` already lists Poten as `CLOSED`.

**Verdict: SKIP.** Building a poten extractor would have duplicated 1,087
documents of existing work.

## Measured coverage of every corpus folder

| corpus | PDFs | extraction output | gap |
|---|---|---|---|
| `01-brokers` | 2,915 | per-publisher dirs under `data/extracted/md/` (see register; all 18 CLOSED) | none known |
| `02-hellenic` | **3,969** | `hellenic` 1,171 md | **~2,798 unextracted - LARGEST GAP** |
| `03-breakwave` | 302 | `breakwave` 3,483 md | md count exceeds PDFs - a different (HTML/API) source type, not a gap |
| `04-poten` | 1,087 | `poten` 1,087 md + 1,087 tables.json | none - CLOSED |
| `05-seabrokers` | 97 | none | 97 (small) |
| `06-drewry` | 276 | `drewry` 276 md | none |
| `07-signal` | 9 | none | 9 (tiny) |
| `08-baltic` | 0 | `baltic` 2,218 md | not a PDF source |
| `09-ppa` | **493** | **none** | **493 - largest fully-unbuilt PDF corpus** |
| `archive` | 724 | none | stopped publications (archive by rule) |
| `books` | 12 | none | 12 |

## Recommended next source, in order

1. **`corpus/09-ppa` (493 PDFs, zero output).** The biggest corpus with no
   extraction at all. No runner exists. Start from zero: count + fingerprint
   several years, render and LOOK, write `docs/ppa_survey.md`, build
   `scripts/extract/publishers/run_ppa.py`, trial on 2+ docs from different
   years, then bulk-run.
2. **`corpus/02-hellenic` (~2,798 without md).** Larger in absolute terms, but
   **check `scripts/extract_demolition_pdfs.py` first** - the state file records
   that part of this corpus is already consumed, and the register claims 992
   hellenic series already exist. Do the three-baseline test per sub-publication
   before treating any of it as missing: this is exactly the trap recorded in
   `docs/` where hellenic was ranked a top CONSTRUCT target while the corpus
   already held 992 of its series.
3. `05-seabrokers` (97) and `07-signal` (9) are small enough to be filler, not a
   priority.

## Caveat on this table

Counts are `glob` counts of `*.pdf` and `*.md` on disk, measured this run. They
are not stem-matched, so "gap" is an upper bound: a corpus whose md filenames are
reformatted (as poten's are - `Tanker_Opinion_20040102.pdf` ->
`poten_2004-01-02_china-syndrome.md`) cannot be matched by stem, which is why
poten's stem-match reads 0 while its per-year coverage is complete. Any corpus
above must be confirmed by per-year counts before a bulk run.
