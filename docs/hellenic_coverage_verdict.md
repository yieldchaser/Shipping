# corpus/02-hellenic - coverage verdict (measured 2026-09-28 15:5x)

**Headline: the "~2,798 without md" lead in OVERNIGHT_STATE.md was WRONG.**
It was derived by globbing `data/extracted/md/*` and never querying
`corpus.duckdb` - the identical error class as the 09-ppa row that had to be
corrected earlier today. Hellenic is ~99.9% covered.

## Measured population

| measure | value |
|---|---|
| PDFs in `corpus/02-hellenic/` | **3,969** |
| distinct contents (sha256) | **2,236** |
| `corpus.duckdb` `source='hellenic'` | **2,057 docs / 57,351 cells** |
| distinct contents with NO DB stem match | **180** |

Per sub-folder (files / distinct contents):

| sub | files | distinct |
|---|---|---|
| iron_ore (MMi daily iron ore) | 2,242 | 1,173 |
| demolition (GMS / Best Oasis / Athenian / Weekly-Ship-Recycling) | 1,052 | 718 |
| shipbuilding (Clarkson Platou Hellas SNP + breakwave + Clarkson Weekly Sales) | 675 | 345 |

`dry_charter`, `tanker_charter`, `vessel_valuations` are **empty** (0 PDFs).

## The 180 "missing" resolved

| bucket | n | status |
|---|---|---|
| breakwave (filed under hellenic/shipbuilding) | 170 | **COVERED** - all 170 match a `data/extracted/md/breakwave/{drybulk,tankers}` file within +-9 days (0 uncovered). Breakwave has its own tier and its own DB source. |
| iron_ore | 3 | **COVERED** - all 3 have md (`2022-01-31`, `2025-12-24`, `2026-09-21`). DB uses a different doc-stem convention. |
| demolition | 7 | 5 have a `data/derived/scrappage_prices.csv` row within 2 days (same week, already held); **2 were genuinely new** |

Genuinely new: the two 2026-09-19 reports (Best Oasis week, GMS week 38).

## Action taken

Appended `2026-09-19` to `data/derived/scrappage_prices.csv` via the source's
own `scripts/extract_demolition_pdfs.py::upsert_scrappage_to_csv` (additive,
asserts non-shrink): **380 -> 381 rows**, `dry_india` non-null 375 -> 376.

Verification (NO vision tool in the cron session - substituted the skill's
same-document text reconciliation, stated as such):

* GMS: all 7 extracted values located in the page text as `N / LDT`, and the
  country mapping confirmed from the table's own row order on p4 -
  PAKISTAN 500/525/535, BANGLADESH 490/515/525, INDIA 465/485/495,
  TURKEY 300/310-315/325-330. Extracted `dry/tanker/container_india =
  465/485/495`, `dry/tanker_bangla = 490/515`, `dry/tanker_pak = 500/525`. Exact.
* Best Oasis: `parse_demolition_pdf` returns all-None. Its prices are printed
  in a **chart**, not a text table (country labels repeat 3x with no numeric
  cells). Not appended - named here rather than silently dropped. Per-source
  treatment needed if this publisher is to be covered.

## Wider sweep (same method, all corpus folders)

| folder | files | stem-match in DB | note |
|---|---|---|---|
| 01-brokers | 2,915 | 2,703 | remainder are duplicate/stem-convention, sources are DONE |
| 02-hellenic | 3,969 | 2,056 | this doc |
| 03-breakwave | 302 | 297 | |
| 04-poten | 1,087 | 1,083 | CLOSED |
| 05-seabrokers | 97 | 96 | |
| 06-drewry | 276 | 276 | 100% |
| 07-signal | 9 | 1 | 8 unmatched - small, unexamined |
| 09-ppa | 493 | 297 | 154 byte-dupes + 42 built by `run_ppa.py` |
| archive | 724 | 722 | |
| books | 12 | 12 | 100% |

**Lesson (repeat of the ppa one, now twice): a coverage claim must be measured
against `corpus.duckdb` AND the source's own md tier AND the feeds - never
against a single `md/` glob.** Stem-matching alone also undercounts, because
different pipelines named the same document differently.
