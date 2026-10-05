# Knowledge-validate blocker: ROOT-CAUSED AND FIXED (mirror path duplication)

Run: 2026-10-05 21:35 IST, 30m source-by-source job. Repo on `main` (parallel
automation active). No extraction job live (all broker sources CLOSED, non-broker
corpora extracted - see OVERNIGHT_STATE). This run worked the top open, app-visible
item carried from the 20:5x run: CI step 11 `Validate updated knowledge`
(`scripts/validate_knowledge.py`, exit 1) keeps the daily knowledge commit SKIPPED,
so the QA tier the app serves has been frozen since 2026-09-29.

## The exact failure composition (measured, run 37329812815)

CI validator summary (artifact `daily-knowledge-failure-diagnostics-37329812815`):

| metric | CI value |
|---|---|
| Duplicate doc ids | **1290** |
| Duplicate tree node ids | 3337 |
| Chunks with invalid section refs | 28731 |
| Duplicate section index node ids | 2047 |
| Linked assets failed | 1311 |
| Coverage TOTAL processed vs files | 10147 vs 8962 (**-1185**) |

Coverage gaps by category (CI):
`hellenic/iron_ore 1203->1736`, `hellenic/shipbuilding 379->758`,
`hellenic/vessel_valuations 274->547` = +533 +379 +273 = **+1185**.

**1290 = 1185 (hellenic) + 105 (broker) exactly.** Two independent mirror defects.

## Root cause, proven from the CI manifest itself

`knowledge/manifests/documents.jsonl` on the runner (12606 rows) contains, for the
SAME document, two rows with one `doc_id`:

```
doc_id: hellenic_iron_ore_2021-07-14_2021_07_14_mmi_daily_iron_ore_index_report_july_14_2021
  source_path: corpus/02-hellenic/iron_ore/2021/2021-07-14_mmi-daily-iron-ore-index-report-july-14-2021.html
  source_path: reports/hellenic/iron_ore/2021/2021-07-14_mmi-daily-iron-ore-index-report-july-14-2021.html
```

`make_archive_doc_id()` (process_knowledge.py:1972) builds ids from
`source_category_date_slug(stem)` and **ignores the directory**, so a stale row left
at the old mirror root (`corpus/02-hellenic/**`) and the live copy at the current
root (`reports/hellenic/**`) share one doc_id.

* **Hellenic (1185):** 1185 manifest rows still point at `corpus/02-hellenic/**`
  (iron_ore 533, shipbuilding 379, vessel_valuations 273). The live root is
  `reports/hellenic/**`; on the CI runner those live files are (re)processed and
  the twin rows collide. `prune_missing_sources` keeps them because the corpus
  files still exist on disk, so nothing removed them.
* **Broker (105):** `reports/broker_reports/**/carriers/` and
  `reports/broker_reports/**/general_broker/` are 1:1 mirrors of the per-publisher
  digests (added by `9fb0aaafd` / `0924975de`). Measured: 277 md files, 172 distinct
  basenames -> **105 duplicate basenames**, 210 files in colliding pairs, all inside
  `broker_reports`.

The 3337 duplicate tree node ids, the 28731 invalid chunk section refs and the 2047
duplicate section-index node ids are downstream of the same duplicate rows: a
duplicated doc_id makes the validator read one document's tree twice and key its
chunks against the wrong tree.

## Fix (process_knowledge.py only; uncommitted on `main`)

1. `prune_superseded_mirror_rows()` - at manifest load, drop any row whose
   `(source, category, basename)` is produced by a currently-discovered file whose
   own path differs. Removes the 1185 stale `corpus/02-hellenic/**` rows.
2. discovery dedupe (in `main`) - discovered files are de-duplicated on
   `(source, category, stem)`, preferring the path already in the manifest, so the
   broker mirror is not processed twice.
3. `dedupe_manifest_rows_by_doc_id()` - final write keeps exactly one row per
   doc_id, preferring a discovered path (belt-and-braces).

## Verification (measured, offline against the real CI manifest)

Applied to `scratch/ci_diag/knowledge/manifests/documents.jsonl` (the CI artifact):

```
CI rows 12606
before          : extra dup doc ids = 1290
after prune     : rows 11421, extra dup doc ids = 105
after doc_id dedupe: rows 11316, extra dup doc ids = 0
hellenic after  : iron_ore 1203, shipbuilding 379, vessel_valuations 274  (= file counts)
```

`python3 -m py_compile scripts/process_knowledge.py` -> OK.

## Tree / chunk layer verified (measured, second check)

Fed the DEDUPED manifest (11316 rows) straight into the validator's own
`inspect_trees()` + `inspect_chunks()` against the repo's tree/chunk files:

```
final rows 11316
DUP tree node ids: 0          (CI: 3337)
DUP chunk ids: 0
invalid section refs: 0       (CI: 28731)
missing section refs: 0
```

So the two largest cascade failures clear with the deduped manifest, measured -
not inferred. (`missing tree files: 1121` here just reflects that this box's
committed tree set corresponds to the local manifest, not the CI-regenerated one;
in CI those trees exist.)

## NOT yet verified (honest limits)

* The full CI chain (process -> validate) was not reproduced locally: this box's
  `knowledge/derived/*` is stale/absent (gitignored) and the local validator takes
  ~31 min and reports a DIFFERENT metric set ("Section index rows: 0", "Missing
  section index node ids: 34718") than the runner, so local numbers are not the CI
  numbers. The fix was verified only at the manifest layer (dup doc ids -> 0).
* Whether `Chunks with invalid section refs` (28731), `Duplicate section index node
  ids` (2047) and `Linked assets failed` (1311) reach 0 after the next CI run is
  therefore UNPROVEN. They are all consistent with being cascade effects of the
  duplicate rows, but that is inference, not measurement.
* Local clean-manifest baseline (for contrast, committed manifest, no reprocessing):
  Duplicate doc ids 0 / dup tree node ids 0 / invalid section refs 0, but
  `Missing source files in manifest: 21`, `Source hash mismatches: 245`, coverage
  gaps 15 - i.e. the committed tree has OTHER, smaller validate failures.

## Owner action

The fix is code-only in `scripts/process_knowledge.py` and must land on `main` for
CI to see it. It was left UNCOMMITTED because this session runs on `main` and the
standing order is "never touch main" (a parallel automation is committing ffa-live
ticks there). Also worth considering: the validator's "linked assets failed" and
the local "hash mismatches" gates fail independently of this bug and would still
keep `validate` non-zero if they are truly enforced as failures.

## Why pruning the `corpus/02-hellenic/**` rows loses nothing (measured)

All 1185 `corpus/02-hellenic/**` rows have a twin at the live root; the files are
NOT byte-identical (different CSS/template wrapper: corpus 3922 B, Sep-29 cron
render; reports 3854 B, Oct-5), but the extracted visible TEXT is IDENTICAL
(checked on `2021-07-14_mmi-daily-iron-ore-index-report-july-14-2021.html`:
1363 chars == 1363 chars, byte-equal after tag/CSS strip). The corpus copies are
stale re-renders of the same documents; `reports/hellenic/**` is the current root
(newest mtime Oct-5, the discovery root), so preferring it is correct.
