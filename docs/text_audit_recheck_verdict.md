# TEXT-AUDIT REFRESH against the current corpus + knowledge tier (2026-10-04, overnight)

Context: audit job #1 (`data/extracted/text_audit.json`) was generated 2026-09-23. The
other three audit outputs were refreshed on 2026-10-04 (`table_audit.json`,
`gap_verify_recheck.json`), so this run refreshed the text audit and re-measured the
knowledge chunk tier. Artefact: `data/extracted/text_audit_recheck.json`.

## 1. Corpus text storage - COMPLETE, unchanged

- `text.jsonl` on disk = **16,803**; **124** are zero-byte (image-only / scanned) - the
  same population the 2026-09-23 audit classified as vision candidates, not failures.
- No new 0-byte or missing text has appeared. The text layer is stable.

## 2. Knowledge chunk tier - OPEN, measured shortfall

- Manifest declares **106,489** chunks across **93** shard files.
- On disk: **89,151** chunks across **104** shard files. Shortfall = **17,338 (16.3 pct)**.
- **11 shards declared >0 chunks but are 0 bytes / empty on disk**, holding **2,456**
  declared chunks, ALL hellenic:
  `hellenic_shipbuilding_2014/2021/2022/2023/2024` and
  `hellenic_vessel_valuations_2014/2021/2022/2023/2024/2025`.
- **6 shards are partial** (on-disk < declared): `hellenic_iron_ore_2021` (9,302/9,539),
  `hellenic_iron_ore_2022` (6,544/17,380), `hellenic_iron_ore_2026` (1,752/4,908),
  `hellenic_shipbuilding_2025` (12/351), `hellenic_shipbuilding_2026` (89/307),
  `hellenic_vessel_valuations_2026` (47/155).

### App impact (user-visible, silent)
All 11 empty shards are referenced by `index.html` `QA_CHUNK_FILES` for the hellenic,
ironOre and shipbuilding tabs (historical and deep_historical tiers). A 0-byte shard
loads 0 rows, so the app Q&A over those tiers returns nothing for the years concerned.
No error is raised - it is silent coverage loss.

## 3. Why the 2026-09-23 remediation no longer applies

The 2026-09-23 audit named the fix as "re-run the chunk compiler for the 11 hellenic
chunk files". That is **wrong as literally written** against the current repo:

- The `reports/hellenic -> corpus/02-hellenic` migration left `documents.jsonl`
  `source_path` stale. Measured now: of **3,214** hellenic manifest rows, **2,702**
  point at a `reports/hellenic/...` path that no longer exists, and for **all 2,702**
  the alternate `corpus/02-hellenic/...` path DOES exist.
- `process_knowledge.py --source hellenic` resolves each source through that stale
  `source_path`; the existing repair template (`scripts/repair_iron_ore_shards.py`)
  does the same and would **SKIP every one** of these documents (`[SKIP] missing source`).
- The prune effect of the stale paths was already measured in a prior overnight run
  (8,999/10,202 rows would drop) and established as **not reproducible / does not fire**
  on the nightly `knowledge:update`. Recorded here as context, not a new hazard.

Correct remediation: give the repair a `corpus/02-hellenic` source override (resolve the
alt path instead of `row["source_path"]`), keep the LLM OFF (reuse stored metadata as
`repair_iron_ore_shards.py` does), re-ingest the affected docs, then compact the touched
shards. Sources are verified present: `corpus/02-hellenic/shipbuilding` = 379 html,
`corpus/02-hellenic/vessel_valuations` = 274 html (matching the manifest counts).

### Caution before running any re-ingest
`process_file` regenerates the knowledge doc md and tree. On at least one other source
(lion) a re-run would have DOWNGRADED the richer md now on disk. Before healing, confirm
the re-generated md is not a downgrade of the existing `knowledge/docs/hellenic/...` md.

## Verdict
- Corpus TEXT storage: complete, unchanged.
- Knowledge chunk tier: open defect, quantified (17,338-chunk shortfall; 11 empty + 6
  partial hellenic shards; all app-referenced). Nothing was mutated this run.
