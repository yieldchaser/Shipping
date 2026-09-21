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

## Signals to watch

| Signal | Meaning | Action |
|---|---|---|
| `verify_extraction.py` exits 1 with `state file is N min old` | batch died | rerun with `--resume` |
| `duplicate checkpoint rows` | two batches ran concurrently | kill strays, dedupe happens automatically on load |
| `timeout` status accumulating | per-doc ceiling too low for large PDFs | raise `--timeout` |
| `not-a-pdf (bad header)` | corrupt/HTML-served-as-PDF | expected; quarantine is correct |
| `GOLDEN REGRESSION` | extractor behaviour changed | stop and investigate before continuing |
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

## Known failures and their disposition

| Item | Disposition |
|---|---|
| `docs/research/Subscription Plans - UN Comtrade Help Center.pdf` | layout segfault; quarantined |
| 3 files with bad `%PDF-` headers (breakwave x2, signal fueleu) | quarantined as not-a-pdf |
| `Maritime Economics ... (z-lib.org).pdf` (~400 pp) | needs `--timeout 900`; textbook, not time-series data |
| `bp-stats-review-2020-full-report.pdf` (68 pp) | ~120 s; keep timeout generous |
| Baltic `*/assets/*` | bot-wall placeholders, skipped by the HTML pass |
| Breakwave HTML aggregations (Yahoo/CNN/Blogspot) | filtered by the HTML pass |

## Reporting rule

Report measured throughput and the per-status counts, list the failure kinds
with the exact filenames, and never present an estimate as a measurement.
