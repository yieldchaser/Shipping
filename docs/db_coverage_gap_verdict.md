# DB coverage gap: `corpus.duckdb` is a frozen 2026-10-03 snapshot whose CONTENT stops at 2026-09-19

Measured 2026-10-07 ~22:2x IST, read-only (`duckdb.connect(..., read_only=True)`),
unattended source-by-source cron run. Quantifies open item (c) "inventory/DB rebuild".

## Why this exists

`docs/OVERNIGHT_STATE.md` carried item (c) as a bare pointer ("inventory/DB rebuild",
the user's call). This run measured it so the decision is made from numbers, and so a
future audit cannot mistake the DB's ceiling for a missing-extraction defect (the exact
trap in the extraction skill: "cells=0 for a freshly extracted document is the tell").

## Measured

* File `data/extracted/corpus/db/corpus.duckdb`, 125,317,120 bytes, mtime 2026-10-04 17:34.
* **Every** `catalogue` row has the same `extraction_ts` = **2026-10-03T12:36:57Z** (one build;
  no later writes).
* Tables: `catalogue` 189,481 tables; `cells` 6,726,703; `series` 5,743;
  `series_points` 1,193,579; `label_series` 1,619,891; `series_daily` 970,291; `doc_dates` 5,216.
* `cells` by engine: camelot-stream 5,386,900; pdfplumber 1,323,087; html-table 16,716.
* Docs (distinct `doc_stem`) per source: shipbrokers 3,428; hellenic 2,057; poten 1,084;
  baltic 544; drewry_ais_pdfs 276; drybulk 210; ppa_pdf 181; seabrokers 96; tankers 78;
  cftc_statements 30; signal 14; breakwave 9; research 2; plus one-off book/PPA PDFs.

## The gap (content ceiling)

Max document date per source, from `doc_dates`:
shipbrokers **2026-09-19**, baltic 2026-09-18, hellenic 2026-09-18, drybulk 2026-09-15,
tankers 2026-09-08, drewry_ais_pdfs 2026-08-24, seabrokers 2026-08-01, breakwave 2024-05-21.

So the DB reaches content only to **2026-09-19**. Confirmed absent (0 stems matching):
`%2026_09_29%`, `%2026_09_23%`, `%_29_09_2026%`. Present on disk as `.md` but not in the DB:
xclusiv 2026-09-29, intermodal 2026-09-30, agora 2026-09-30, carriers 2026-09-28,
banchero_costa 2026-09-23. The DB therefore lags the delivered md tier by ~10 days
(newest `.md` 2026-09-30) and the newest corpus content (2026-10-06) by ~17 days, and it
predates **every** 2026-10-07 correction (allied en-bloc 6 rows; xclusiv_sales 2026-08-03;
the carriers_* regeneration; carriers_newbuilding).

Per-publisher DB-vs-disk `doc_stem` counts (substring match): xclusiv 261/271, star 191/200,
ssy 509/530, advanced 248/255, affinity 245/249, agora 211/219, ism 113/115, lion 45/48,
intermodal 251/257, banchero 243/249, carriers 131/137, gibson 109/265, clarkson 171/188,
allied 204/203.

## Blast radius

* **Not app-displayed.** `index.html` has 0 `duckdb` references; the app reads
  `data/**/*.csv` plus the knowledge chunks, and a browser cannot fetch a `.duckdb` file.
* Consumers are **scripts only** (`build_series*.py`, `classify_series.py`,
  `column_shift_audit.py`, `verify_extraction.py`, `coverage_audit.py`,
  `generate_cadence_audit.py`, ...) - an analysis/verification layer, not a delivery path.
* **Warning for any future audit:** querying this DB for a document extracted after
  2026-09-19 returns `cells=0`, which reads exactly like "the extraction dropped this
  document". State the DB's ceiling before drawing such a conclusion.

## Builder / how a refresh would run

* `scripts/extract/build_table_db.py`; its own usage: `python scripts/extract/build_table_db.py`
  = **incremental (new docs)**, `--rebuild` = reparse everything.
* Inputs = `data/extracted/corpus/<doc>/<doc>/tables.jsonl` (the corpus-pipeline store,
  distinct from the per-publisher `md/` tiers). Incremental mode reads `catalogue.parquet`'s
  seen `doc` set and appends unseen docs only.
* **Not run this pass.** It rewrites the 125 MB DB, and the parallel Claude vv-OCR job
  (`parse_engine_html vv --workers 6`, PID 11392, its own worktree) holds the CPU -
  no-two-heavy-jobs rule. A full `--rebuild` remains the user's call.

## Liveness at measurement

No `run_*` of ours in flight. The only extraction process is the parallel agent's
`parse_engine_html vv --workers 6` (PID 11392 + 6 spawn workers), confined to its own
worktree. `corpus/` is git-tracked (51,826 files under it) and `git status corpus` =
0 changes -> no new arrivals (newest content 2026-10-06). Register gate
`scripts/extract/verify_registers.py` = ALL PASSED, 180 CSVs / 640,870 logical rows.

---

## UPDATE 2026-10-07 23:4x IST — a rebuild is a measured NO-OP; the gap is UPSTREAM ingestion, not the DB

Measured this run (read-only), to answer the question the 22:2x note left open
("refresh = `build_table_db.py`"): **would a refresh actually close the gap?**

**No.** The store the DB is built from is itself frozen.

* Producer chain (read from source): `corpus.duckdb` <- `scripts/extract/build_table_db.py`
  <- `data/extracted/corpus/<source>/<stem>/tables.jsonl` <- `scripts/extract/extract_all.py`
  driven off `data/extracted/inventory.jsonl`.
* **0 of 17,654** doc dirs (2 levels under `data/extracted/corpus`) have an mtime newer
  than the 2026-10-03 build epoch. `data/extracted/inventory.jsonl` mtime is
  **2026-09-21 15:29**. Newest store content = shipbrokers **2026-09-19**; every store dir
  is <= 2026-09-22.
* Therefore `build_table_db.py` (incremental) prints `no new tables found; nothing to write`
  — it would add **0** documents. `--rebuild` would only reconstruct the identical content
  from the identical (frozen) inputs. **A DB refresh cannot reach xclusiv 2026-09-29,
  intermodal/agora 2026-09-30, carriers 2026-09-28, banchero 2026-09-23, or any newer md**,
  because those were never routed into the `corpus/` store — they exist ONLY as the
  per-publisher `md/` tiers.
* Consequence for the earlier note: the DB lag is NOT a "rebuild was not run" condition.
  It is upstream. The remedy is a USER decision: re-run the store pipeline
  (`inventory.jsonl` rebuild -> `extract_all.py --inventory ... --out data/extracted/corpus`)
  over the current corpus, THEN `build_table_db.py`. Blast radius unchanged: scripts-only,
  not app-displayed (`index.html` 0 `duckdb` refs).

Evidence: `os.scandir` of 17,654 store doc dirs vs the 2026-10-03 build epoch (0 newer);
the mtimes above. This run did NOT run the rebuild (it would be a 125 MB rewrite for zero
new content).
