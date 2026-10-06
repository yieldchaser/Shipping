# Extraction Runbook — how to start, supervise, resume

Operational companion to `docs/EXTRACTION_STRATEGY.md`. Any agent (or human)
picking this up mid-run should be able to act from this file alone.

## The one important constraint

**Never run two batches at once.** Two concurrent batches double-process the
corpus and interleave rows into the same checkpoint. This actually happened
(152 checkpoint rows for 91 unique docs) and inflated the throughput numbers.
`run_batch.py` now takes a lockfile (`data/extracted/.batch.lock`); it refuses
to start if the recorded pid is alive. Do not bypass it with `--no-lock`.

## Commands

```bash
# dry batch (303 docs, stratified) - already validated
python scripts/extract/run_batch.py --limit 300 --workers 2 --timeout 420 \
    --resume --out data/extracted/dryrun

# FULL PASS (7,816 unique docs) - the real run
python scripts/extract/run_batch.py --all --workers 2 --timeout 900 \
    --resume --out data/extracted/full

# resume after any interruption (safe to repeat; skips completed docs)
python scripts/extract/run_batch.py --all --workers 2 --timeout 900 \
    --resume --out data/extracted/full

# rebuild the SQL database from whatever has been extracted so far
python scripts/extract/build_table_db.py --out data/extracted/full

# HTML article pass (Hellenic, Signal, Breakwave insights, Baltic)
python scripts/extract/run_html_pass.py --all --out data/extracted/html

# health check - run every few hours; non-zero exit means act
python scripts/extract/verify_extraction.py --out data/extracted/full
```

## Launching on Windows/MSYS

- Launch long jobs through the **tool's background session** (the command runs
  in the foreground of that session). Do **not** use `nohup cmd &` in a shell
  that then exits - the child gets orphaned and the job dies mid-run.
- MSYS `ps aux | grep` does **not** show these children. Check liveness with:
  ```bash
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*run_batch*' -or \$_.CommandLine -like '*batch_worker*' } | Select-Object ProcessId"
  ```
- Judge progress from the checkpoint line count and `data/extracted/batch_state.json`,
  never from a process listing.

### Launch durably (added 2026-09-22)

Prefer the detached launcher over the tool background session:

```bash
python scripts/extract/launch_detached.py            # prescribed command, detached
python scripts/extract/launch_detached.py --dry-run  # print what it would run
```

It spawns `run_batch` with `CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS` and
appends the driver stdout+stderr to `data/extracted/batch_run.log`. Measured
2026-09-22 05:48 IST: a batch started through the tool background session was
terminated ~20 s after the agent run that started it finished (Hermes puts itself
in a `KILL_ON_JOB_CLOSE` job object, so unbroken-away children die with it; there
was no crash record in the Windows Application log, which is how termination was
told apart from a fault). Judge progress from `data/extracted/batch_run.log` and
from the checkpoint line count - never from `ps`, which cannot see these children.

## Signals to watch

| Signal | Meaning | Action |
|---|---|---|
| `verify_extraction.py` exits 1 with `state file is N min old` | batch died | rerun with `--resume` |
| `duplicate checkpoint rows` | two batches ran concurrently | kill strays, dedupe happens automatically on load |
| `timeout` status accumulating | per-doc ceiling too low for large PDFs | raise `--timeout` |
| `not-a-pdf (bad header)` | corrupt/HTML-served-as-PDF | expected; quarantine is correct |
| `GOLDEN REGRESSION` | extractor behaviour changed | stop and investigate before continuing |
| `inventory_drift` in the JSON (informational, never an action) | The queue and `remaining_work()` come from `data/extracted/inventory.jsonl`, a FROZEN file; this many PDFs on disk are absent from it by filename | None by itself - the bespoke runners read the corpus directly. Re-run `build_inventory.py` (then `run_batch --resume`) only if the `extract_all` tree is wanted current. Measured 2026-10-01: 338 such PDFs, 274 with unseen content |
| failure rate > 10% | systemic problem | stop, inspect the failure kinds |

## State the successor agent needs

- `data/extracted/batch_checkpoint.jsonl` — append-only, one JSON record per
  finished document (status, secs, pages, tables, images, ocr_queue_pages,
  orphan_values). Last record per path wins.
- `data/extracted/batch_state.json` — live progress: done/planned, status
  counts, secs per doc, ETA. Written every 10 documents.
- `data/extracted/<run>/<source>/<stem>/` — per-document artefacts:
  `text.jsonl`, `tables.jsonl`, `pages.jsonl`, `charts/` + `charts/meta.jsonl`.
- `data/extracted/<run>/db/` — `tables.parquet` (one row per cell),
  `catalogue.parquet` (one row per table), `corpus.duckdb` with `cells`,
  `catalogue` and `label_series` views.

### The 74 not-a-pdf quarantines are genuine (measured 2026-10-01)

Re-checked by magic bytes, not by assuming the check was right: of the 6 whose source
file still exists, **0 are PDFs** - 5 are HTML (`<!DOCTYPE html>` / `<html>`) and 1 is a
DOCX (`PK`, `word/document.xml`). The other **68 source files no longer exist anywhere in
the repo**: they were breakwave "commodity call" HTML-dumps removed during the corpus
reorganisation into `corpus/<NN-group>/`. So the quarantine cost 0 real documents and the
count is expected, not a regression. A verifier seeing 74 should not "fix" it.

## What the extract_all corpus does and does not feed (measured 2026-10-01)

`extract_all.py` (the bulk pass) writes `data/extracted/<run>/<source>/<stem>/{text,tables,pages}.jsonl`.
**Nothing in the app reads that tree** - `index.html` fetches `data/views/**`, `data/derived/**`,
`data/clarksons/**`, `data/etf/**` only. The publisher series come from the per-publisher runners
under `scripts/extract/publishers/`, which open the SOURCE PDFs directly and write
`data/extracted/md/<pub>/*.tables.json` + `data/extracted/series/*.csv` (or, for PPA,
`data/extracted/ppa/`). `build_table_db.py` is the only consumer of the `extract_all` tree
(`glob <out>/*/*/tables.jsonl` -> `data/extracted/corpus/db/corpus.duckdb`), and **that DB is
not rebuilt** - see the pending human decision in `EXTRACTION_OVERNIGHT_LOG.md`.

Consequence for any "re-extract N documents" proposal: it only buys something for a publisher
that has NO bespoke runner. Coverage measured for the 717 documents carrying a skipped
`garbled` page (the table-shaped pages recorded in `EXTRACTION_OVERNIGHT_LOG.md`):

| Publisher affected | Docs | Bespoke pipeline that bypasses extract_all |
|---|---|---|
| shipbrokers/advanced_shipping | 5 | `run_advanced_shipping_tables.py` -> 5 series CSVs, 18,744 rows |
| shipbrokers/xclusiv | 39 | `run_xclusiv_tables.py` -> 10 CSVs, 21,212 rows |
| shipbrokers/banchero | 59 | `run_banchero_*` -> 10 CSVs, 256 md files |
| shipbrokers/fearnleys | 4 | `run_fearnleys*` -> 7 CSVs |
| hellenic | 181 | `run_hellenic_demolition.py` etc. -> 31 CSVs, 265,104 rows |
| seabrokers | 96 | `run_seabrokers_llamaparse.py` -> 9 CSVs, 16,500 rows |
| ppa_pdf | 126 | `run_ppa.py` -> `data/extracted/ppa/{hedland,dampier}_rows.jsonl` |
| **shipbrokers/allied** | **129** | **none** (and archived) |
| **shipbrokers/golden_destiny** | **78** | **none** (and archived) |

510 of 717 belong to a publisher whose series never read the `extract_all` tables. The only
uncovered 207 are `allied` and `golden_destiny`, both moved to `corpus/archive/` (allied's newest
issue is 2024-W07, golden's 2024-W48 - both >180 days old => BACKFILL_ONLY), with no series CSV
and no mention in `index.html`. Re-extracting them backfills two dead titles; it extends no
current series.

## Known failures and their disposition

| Item | Disposition |
|---|---|
| `docs/research/Subscription Plans - UN Comtrade Help Center.pdf` | layout segfault; quarantined |
| **74** files with bad `%PDF-` headers (full 7,816-doc pass; the earlier "3" was the 303-doc dryrun) | quarantined as not-a-pdf - verified correct 2026-10-01 |
| `maritime_economics_macro_karakitsos_varnavides.pdf` (~400 pp) | needs `--timeout 900`; textbook, not time-series data |
| `bp-stats-review-2020-full-report.pdf` (68 pp) | ~120 s; keep timeout generous |
| Baltic `*/assets/*` | bot-wall placeholders, skipped by the HTML pass |
| Breakwave HTML aggregations (Yahoo/CNN/Blogspot) | filtered by the HTML pass |

## Reporting rule

Report measured throughput and the per-status counts, list the failure kinds
with the exact filenames, and never present an estimate as a measurement.
