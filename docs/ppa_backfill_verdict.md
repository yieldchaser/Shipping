# PPA 2013-2014 backfill verdict — source 09-ppa (2026-10-04)

Runner: `scripts/extract/publishers/run_ppa.py` (per-source, resumable, JSONL checkpoint).
Exporter: `scripts/extract/export_ppa_csv.py` (new — the deliverable CSVs previously had no
committed builder). Corpus: `corpus/09-ppa`.

## What was wrong: the runner could not see 110 corpus files

Measured this run: `corpus/09-ppa` now holds **603 PDFs / 358 distinct contents**, but
`run_ppa.py` discovered files with

```python
files = sorted(CORPUS.glob("_root_pdfs/*.pdf")) + sorted(CORPUS.glob("ppa_pdf/*.pdf"))
```

= **493 files / 339 distinct** — i.e. the 110 PDFs that a corpus reorg moved to the corpus
**root** were invisible to the extractor. 85 of them are byte-duplicates of files still in the
two subdirs; **19 are distinct contents seen by no runner at all** (md5 sweep, `scratch/ppa_gap/hash.py`).

All 19 are **2013-2014 Port Hedland** documents, in two report flavours:
* **10 "summary"** — `Cargo Stats by Destination` country x commodity grid (family-A shape);
* **9 "detailed"** — `Cargo Stats by Destination - Detailed`, a per-vessel listing (no grid).

## Fix (measured)

1. File discovery now also globs the corpus root, **appended last** so the existing JSONL/CSV
   row order is preserved: `... + sorted(CORPUS.glob("*.pdf"))`.
2. `parse_hedland` now returns `None, "no-cargo-grid"` when a document parses to **0 tables**,
   so the per-vessel "detailed" files are recorded as skipped (not as "done / 0 rows").

## Result — family A (Port Hedland)

| measured | value |
|---|---|
| paths processed (new pass) | 348, **0 failed**, 78.5 s |
| new rows added | **+816** (diff vs installed CSV = 816 added, **0 removed**) |
| months added | **10** — 2013-03…2013-08, 2014-03…2014-07 |
| series span | **2013-03-01 .. 2026-08-01** (was 2015-01) |
| rows | 4,591 -> **5,407** |
| arithmetic checks on the 10 new docs | **265 / 265 pass, 0 bad** |

Family B (Dampier), same glob fix: 520 paths processed, 0 failed; the 2 extra parsed docs were
byte-duplicates and dedup removed them, so `ppa_dampier_fy_series.csv` is **byte-identical** (control).

## Controls

* **Exporter reproduces the committed baseline byte-for-byte.** `export_ppa_csv.py --family
  hedland` run against the **pre-change** `hedland_rows.jsonl` produced a file identical to the
  installed `ppa_hedland_trade_series.csv` (578,160 bytes, `cmp` clean). So the CSV build is
  faithful and the only change to the deliverable is the 816 appended rows.
* **Dedup is on the value key** `(date,port,direction,commodity,country,tonnes)`, first
  occurrence wins — this is what drops the corpus's byte-duplicate documents.
* **Ground truth (rendered page text, not another extractor).**
  `corpus/09-ppa/ppa_cargo_stats_by_destination_summary_june_2013_pdf.pdf` p1 prints
  `22,947,021.00` -> CSV row `2013-06-01,Port Hedland,LOAD,Iron Ore,China,22947021.0`. Match.

## Not done / carried

* The **9 "detailed" 2013-2014 per-vessel files** are skipped (`no-cargo-grid`): they are a
  per-vessel listing, not a country x commodity grid, and are not the family-C report either
  (`Cargo, GRT and DWT Statistics by Commodity Group`). If their data is wanted it needs its own
  parser — a separate scope.
* The CSV's `source_file` column still carries legacy `corpus/09-ppa/_root_pdfs/...` paths for
  pre-2013 rows (a migration artifact). Left untouched: rewriting it would rewrite the whole
  deliverable's path column and is a display/consistency call, not an accuracy one.
* `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` still says PPA "493 PDFs" (now 603). That line is
  generator-owned (`scripts/audit/generate_cadence_audit.py`); update the generator, not the md
  (see the 2026-10-04 cadence-audit drift lesson).
