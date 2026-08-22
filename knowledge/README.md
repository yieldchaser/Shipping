# Shipping Knowledge System Runbook

This document is the operational README for the repo-native knowledge pipeline:

- source scraping into `reports/`
- knowledge compilation into `knowledge/`
- validation and health checks
- online workflow execution and verification

As of `2026-04-11`, the pipeline has been dry-run and validated with:

- `process_knowledge.py --no-llm` -> `processed=0 skipped=7535 errors=0`
- `validate_knowledge.py` -> `Validation status: PASS`


## 1) What Is In Scope

The knowledge system ingests and normalizes:

- Breakwave PDF reports (`drybulk`, `tankers`)
- Baltic HTML reports (`dry`, `tanker`, `gas`, `container`, `ningbo`)
- Breakwave Insights HTML archives (`insights`)
- Hellenic HTML archives (`dry_charter`, `tanker_charter`, `iron_ore`, `vessel_valuations`, `demolition`, `shipbuilding`)
- books (`reports/*.pdf`)

Outputs are written under:

- `knowledge/docs/` (normalized markdown + frontmatter)
- `knowledge/trees/` (section trees)
- `knowledge/chunks/` (retrieval JSONL chunks)
- `knowledge/manifests/` (documents/sources/errors + lint/coverage)
- `knowledge/derived/` (signals/themes/section_index/topic_evidence/timelines)
- `knowledge/wiki/` (topic pages)
- `knowledge/reports/` (health summary)


## 2) Scrapers And Automation

### `report_ingest.yml`

- schedule:
  - `0 8,12,16 * * 1-5` (core windows)
  - `30 9 * * 1-5` (extended window)
- scripts:
  - `scripts/breakwave_scraper.py`
  - `scripts/baltic_scraper.py`
  - `scripts/breakwave_insights_scraper.py`
  - `scripts/hellenic_scraper.py`

### `process_knowledge.yml`

- triggers:
  - on `reports/**` push
  - manual dispatch (`source`, `rebuild`)
- runs:
  - `python scripts/process_knowledge.py ...`
  - `python scripts/validate_knowledge.py`

### `daily_knowledge_update.yml`

- schedule:
  - `30 15 * * *` (daily)
- only processes when `reports/` has files newer than `knowledge/manifests/documents.jsonl`


## 3) Ingestion Coverage Matrix

This is what the compiler currently handles in `scripts/process_knowledge.py`.

### Native report body content

- HTML headings/paragraphs/lists/blockquote: extracted
- HTML tables: extracted via `table_to_text(...)`
- inline `<img>` references: captured as image references
- PDF text pages: extracted with `pdfplumber`

### Linked assets in Hellenic archives

The compiler follows both:

- `<a href="...">`
- `<img src="...">`

Then resolves local assets and ingests:

- `.pdf` -> text extraction (page-limited, truncated safely)
- `.html/.htm` -> section text extraction
- `.txt/.md` -> plain text extraction
- `.csv/.tsv` -> tabular extraction
- `.json` -> parsed/pretty JSON extraction
- `.xls/.xlsx/.xlsm` -> sheet/tabular extraction (`pandas` + `openpyxl`)
- images (`.png/.jpg/.jpeg/.gif/.webp/.svg`) -> image asset section with metadata, SVG text when present, optional OCR notice

Important caveats:

- Remote links are not fetched over network during compile. The compiler resolves assets that exist inside the repo archive.
- If a page links to an external URL, the scraper should mirror that file into `reports/...` for full ingestion.
- OCR for raster images is best-effort. If OCR dependencies are missing, the image is still ingested as a linked image section with metadata/reference.


## 4) LLM Provider Behavior And 429 Protection

LLM calls are controlled in `scripts/process_knowledge.py` with provider chaining:

- `Gemini -> Ollama -> heuristic extraction`

Gemini controls:

- request pacing (`GEMINI_MIN_INTERVAL_SEC`)
- retry/backoff/jitter (`GEMINI_MAX_RETRIES`, `GEMINI_BACKOFF_BASE_SEC`, `GEMINI_MAX_BACKOFF_SEC`)
- retry-after parsing for rate-limit responses
- model override via `GEMINI_MODEL` (default `gemini-2.5-flash`)

Ollama controls:

- base URL / key / model (`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `OLLAMA_MODEL`)
- request pacing (`OLLAMA_MIN_INTERVAL_SEC`)
- retry/backoff/jitter (`OLLAMA_MAX_RETRIES`, `OLLAMA_BACKOFF_BASE_SEC`, `OLLAMA_MAX_BACKOFF_SEC`)

Workflow env defaults are set in:

- `.github/workflows/process_knowledge.yml`
- `.github/workflows/daily_knowledge_update.yml`

Why AI Studio may show no new calls:

- run used `--no-llm`
- run skipped all unchanged docs
- `GEMINI_API_KEY` missing in runtime environment
- Gemini failed and fallback provider handled the run


## 5) Online Trigger Runbook

Use this sequence for a clean online run.

1. Trigger `report_ingest.yml` manually:
   - `source=all`
   - `year=auto`
   - Optional historical batch: `start_year=<YYYY>`, `end_year=<YYYY>`
   - Optional remirror: `overwrite=true`
   - `dry_run=false`
2. Wait for reports commit to `main`.
3. Trigger `process_knowledge.yml` manually:
   - `source=all`
   - `rebuild=false` (incremental)
4. Confirm logs include:
   - `[DONE] processed=... skipped=... errors=0`
   - `Validation status: PASS`
5. Confirm workflow pushed updated `knowledge/` artifacts if changes were detected.

Use `rebuild=true` only when intentionally doing a full clean rebuild.
For one-time historical hardening, run scraper backfills first (with `overwrite=true`), then run `process_knowledge.yml` with `rebuild=true`.


## 6) Local Dry-Run Commands

Incremental no-LLM dry run:

```bash
python scripts/process_knowledge.py --no-llm
python scripts/validate_knowledge.py
```

LLM-enabled run:

```bash
python scripts/process_knowledge.py
python scripts/validate_knowledge.py
```

Source-specific runs:

```bash
python scripts/process_knowledge.py --source hellenic --no-llm
python scripts/process_knowledge.py --source breakwave_insights --no-llm
```


## 7) Expected Success Criteria

A healthy run should have:

- `processed + skipped = total source files`
- `errors=0` in processor summary
- validator `PASS`
- `duplicate chunk ids = 0`
- `missing docs/chunks/trees = 0`
- `malformed json/jsonl/tree counts = 0`
- `high-severity health warnings = 0`


## 8) Known Operational Notes

- `knowledge/manifests/errors.jsonl` is an operational log and can contain historical failures even after a clean run.
- Large chunk files can trigger GitHub size warnings (for example large `hellenic_iron_ore.jsonl`).
- Local Windows ACL/file locks can block writes; rerun with proper permissions when needed.


## 9) Pipeline Quality Audit (2026-08-22) & Applied Improvements

A full end-to-end audit of the document pipeline (ingest → extract → chunk →
derive → serve) produced the following changes, all verified with unit tests.
Unless stated otherwise, extraction improvements apply to **newly processed
documents only** — the existing 8,657-doc corpus re-chunks lazily via the
normal content-hash skip logic, and `COMPILER_VERSION` was deliberately NOT
bumped to avoid triggering a mass re-OCR/re-LLM rebuild.

### Applied

1. **Chunk shard manifest (`knowledge/chunks/index.json`)** — emitted by
   `write_chunk_index()` after every derived rebuild (stat-only per shard, no
   full-file scans). The frontend Q&A tier table and `generate_brief.py` now
   discover shards dynamically; hardcoded year lists (which silently broke
   every January 1) are demoted to fallbacks. Deployed to Pages inside
   `knowledge/chunks/`.
2. **Sentence-aware chunk boundaries** — `chunk_text()` snaps cuts backward to
   the nearest `. ! ? \n` within a 120-char window, ending the mid-sentence /
   mid-table-row truncation that hurt BM25 precision. Overlap stepping is
   unchanged, so no token coverage is lost.
3. **Breakwave bullet de-wrapping** — `adapt_breakwave()` now joins wrapped
   PDF lines into their parent `•` bullet instead of emitting each physical
   line as its own fragment (overview chunks were literally clipped
   mid-clause: "- ...characterized by increased").
4. **Bot-challenge page filter** — archived Cloudflare/Incapsula challenge
   pages are labelled `document_type=error_page` + `is_error_page: true`,
   excluded from signals/themes/timelines in `build_derived()`, and their
   lines are rejected by `extract_numeric_observations()` (a Cloudflare Ray ID
   previously entered `signals.jsonl` as numeric "observations").
5. **Chunk provenance** — chunks carry `source_url` (already available on
   trees/docs), enabling clickable citations downstream.
6. **Pages deploy keeps `breakwave_signals.json`** — production Signals tab
   uses the 62 KB relative-path file instead of downloading the 88 MB
   `signals.jsonl` fallback from raw.githubusercontent.

### Known limitations / roadmap

- ~~**B1 — Pre-built browser search index**~~ **APPLIED 2026-08-22**: every
  chunk shard now has a compact BM25-ready companion
  `knowledge/chunks/search/{stem}.idx.json` (vocab + per-doc top-40 posting
  lists; 38.6 MB total across 77 shards vs ~141 MB of raw text) plus a
  `search/index.json` manifest, emitted by `scripts/search_index_build.py`
  after every derived rebuild. The frontend Q&A ranks candidates from these
  tiny indexes first and downloads only the shards containing hits, instead of
  streaming every tier shard and building an inverted index in-browser. Any
  manifest/index failure falls back to the legacy scan transparently;
  per-line `chunk_id` verification guards against stale indexes.
- ~~**B2 — Structured table extraction**~~ **APPLIED 2026-08-22**: new
  `scripts/table_extract.py` recovers market tables from OCR word-box geometry
  (row clustering + column-gap detection, no new dependencies). Image assets
  that yield a numeric grid emit a `[structured table]` markdown block above
  the raw OCR text; the charter rescan prefers those labeled rows over the
  old positional `vals[-6:]` guesswork and clamps implausible rates outside
  300–200,000 $/day with a logged warning. Forward-looking: applies to newly
  processed documents and future chunk rescans.
- ~~**B4 — Incremental derived/wiki builds**~~ **APPLIED 2026-08-22**:
  content-addressed caches make rebuilds skip unchanged work — doc-level
  (`knowledge/manifests/derived_cache.json`, sha256 of file bytes), chunk-file
  rescans keyed by (path,size,mtime), and wiki score/meta caches under
  `knowledge/derived/.wiki_*_cache.json` invalidated by config hash. Measured
  on the full corpus: 1,777s cold → 474s warm (3.75×), all outputs
  byte-identical (timestamp-normalized) between full and incremental runs.
  The caches are **local-only** (gitignored, ~305 MB); ephemeral CI runners
  keep today's full-rebuild cost unless an `actions/cache` layer is added
  later. `KNOWLEDGE_FULL_DERIVED=1` forces a full refresh.
- **B3 — Cross-source dedup** (Breakwave PDF ↔ insights article twins):
  documented, deliberately not implemented (per product decision).
- **B5+ — img2table/Pix2Text upgrade path**: B2's geometry core is the
  dependency-free baseline; swapping in ML-backed table parsers later only
  replaces `words_from_image`/grid construction, not downstream consumers.
- **Q6 — Wiki recency cap**: topic evidence keeps top-250 newest rows, so
  "Historical Patterns" spans ~10 weeks of a 2014–2026 corpus; stratified
  old/new sampling would fix it.
- Legacy undated docs persist as date `0000-00-00`; wrong `archive-date` meta
  is trusted verbatim during Hellenic/Baltic ingest.


## 10) Dependency Baseline

Knowledge pipeline dependencies are in `requirements_knowledge.txt`, including:

- `pdfplumber`, `beautifulsoup4`, `lxml`, `tiktoken`, `python-frontmatter`, `python-dotenv`, `google-generativeai`
- `pandas`, `openpyxl`, `Pillow` for robust linked spreadsheet/image handling
