# Daily Knowledge Update: step-10 fixed, step-11 is the new blocker

Run: 2026-10-05 ~15:05 UTC (workflow_dispatch of run 37329812815, branch main, HEAD 9fb0aaafd).

## What was verified
The Breakwave freshness guardrail fix (in `scripts/check_breakwave_freshness.py`,
committed in 9fb0aaafd) WORKS in CI. Step 10 "Guardrail - verify Breakwave
signals freshness" is now **success** - it was the failing step on all 6 runs
2026-09-29..10-04. Local control: `--check signals_vs_reports` -> EXIT=0
(drybulk 09-29==09-29, tankers 09-22==09-22).

## The new blocker (measured, from the CI log)
The run now fails at step 11, **"Validate updated knowledge"** (`scripts/validate_knowledge.py`),
exit code 1. Because that step fails, "Commit if changes" is SKIPPED, so the QA /
knowledge tier still does not advance.

Validator failure counts on the CI runner (after `process_knowledge` regenerated
knowledge/):

| check | value |
|---|---|
| Duplicate doc ids | **1290** |
| Chunks with invalid section refs | **28731** |
| Duplicate tree node ids | **3337** |
| Duplicate section index node ids | 2047 |
| Unresolved required local linked assets | 1393 |
| Frontmatter section-count mismatches | 7 |
| Coverage: TOTAL files=8962 processed=**10147** (missing=-1185) | |

Validator exit is non-zero if the summed `failures` list is non-zero; the
coverage term alone counts `total_missing` (15 locally / -1185 on CI), so this
needs to be driven to 0, not merely reduced.

## Root cause 1 - broker digests are MIRRORED into two dirs (PROVEN)
`reports/broker_reports/<year>/` holds each digest under BOTH a publisher dir
(`advanced_shipping/`, `gibson/`, ...) AND the mirror dirs `carriers/` and
`general_broker/`. The digests ending `general_broker_*` exist under BOTH
`carriers/` and `general_broker/`.

- `reports/broker_reports/**/*.md` = 277 files, 172 distinct basenames -> **105 duplicate basenames**.
- Content-hash grouping: **102 groups of byte-identical duplicate files** (102 surplus files).
- `carriers/` mirror added by `9fb0aaafd` ("mirror drewry opinions and broker digests");
  `general_broker/` by `0924975de` ("restore 1:1 file mirror in reports/").

`make_archive_doc_id()` = `{source}_{category}_{date}_{slug(stem)}` - it does NOT
include the directory, so two paths holding the same stem produce the SAME doc_id.
`process_knowledge.py:1380-1382` globs `REPORTS_ROOT/broker_reports/**/*.md`
(recursive) -> both copies are ingested -> duplicate doc ids. The duplicate doc
ids printed by the validator all have the `broker_reports_broker_report_...` form.

## Root cause 2 - hellenic double-counting (measured, path not yet pinned)
On the CI runner three hellenic categories are processed more times than they
have files: iron_ore 1203->1736 (+533), shipbuilding 379->758 (+379, exactly 2x),
vessel_valuations 274->547 (+273, ~2x). Those three are exactly +1185, the whole
`missing=-1185`. `corpus/02-hellenic/<cat>` mirrors `reports/hellenic/<cat>`
(html counts match 1:1), so a discovery path that scans BOTH roots would double
them - but `dry_charter`/`tanker_charter`/`demolition` (also mirrored) are NOT
doubled, so the trigger is category-scoped, not root-scoped. Needs the manifest
write/merge path in `process_knowledge.py` read before fixing.

## Suggested fix (NOT applied this run - owned by the parallel automation)
1. Do not keep two copies of the same digest under `reports/broker_reports/`:
   drop the `carriers/` + `general_broker/` mirrors, OR make `process_knowledge`
   dedupe discovered paths by doc_id (first-wins) so a mirror cannot double-ingest.
2. Then re-check `processed <= files` per hellenic category and the 3.3k duplicate
   tree node ids / 28.7k invalid section refs (a duplicate doc id also duplicates
   its tree nodes, which makes its chunks' section refs invalid - the three counts
   are likely one defect).

Changes this run: none to the repo tree (diagnosis only). CI run 37329812815 is
left failed; the nightly 15:30 UTC run will re-fail at step 11 until this is fixed.
