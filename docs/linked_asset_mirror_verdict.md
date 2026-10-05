# Linked-asset mirror blocker (CI step 11 "Validate updated knowledge") - root-caused and measured

Run: 2026-10-06 ~01:0x IST, unattended 30m job. Branch `main` (HEAD 7d55cb08b; origin==local).
Nothing of ours extracting (all broker sources closed - re-measured this run).

## What the prior run asked for (NEXT RUN items)

1. Did a `Process Knowledge Base` run for `1c942986f`? -> **NO.** Newest P-KB run is
   `37349481980` (17:34Z, headSha 636eca503, conclusion **failure**). `1c942986f` is
   00:36 IST = **19:06Z**, *after* that run, and no P-KB run has been dispatched for it.
   So the carried fixes were exercised by 37349481980 only; the 1c942986f commit has NOT
   been through CI.
2. Measure the 1393 linked-asset targets. -> **DONE BELOW.**
3. Merge/re-apply the books fix. -> `3fbc82f99` is **NOT on main**; it lives only on
   `auto/extract-fixes-2026-10-06-books-section-count` (local + origin). main HEAD is
   7d55cb08b (a fleet-sync commit on top of 1c942986f). Per "never touch main", not merged.

## Method (exact, reproducible)

I imported the validator's **own** function on the local manifest, so the number is not a
re-implementation:
```
python - <<: sys.path.insert(0,"scripts"); import validate_knowledge as vk
rows = json.load ... knowledge/manifests/documents.jsonl  (10,202 rows, Oct 5 14:50)
vk.validate_linked_asset_coverage(rows)
```
Result **reproduces the CI number exactly**: `unresolved_required_local = 1393`.

Totals on 8,644 linked-asset html rows / 5,686 enforced (mirrored>0):
discovered 22,294 / mirrored 13,837 / ingested 13,712 / skipped 8,491 / failed 91;
schema_issues 0, consistency_issues 0.

## Composition of the 1393 (by YEAR/category segment)

| segment | count |
|---|---|
| hellenic `demolition` | 671 |
| hellenic `iron_ore` | 650 |
| breakwave `2024` | 35 |
| breakwave `2023` | 17 |
| breakwave `2025` | 10 |
| breakwave `2021` | 3 |
| breakwave `2022` | 2 |
| breakwave `2020` | 5 |
| **total** | **1393** (1,387 distinct basenames) |

**Correction to the prior entry's characterisation:** the class is NOT breakwave-dominated.
It is **95% hellenic** (demolition+iron_ore = 1,321). The prior "72 breakwave refs" figure is
only the small part. Every one of the 1393 is a row whose `source_path` starts with `reports/`.

## Root cause = the skill's "moved-path reference" class

Every unresolved entry is an html whose `<a href>` contains `../pdfs/<name>.pdf`, e.g.
```
reports/hellenic/demolition/2021/2021-07-03_...html
   -> ../pdfs/2021-07-03_..._weekly-ship-recycling-report_137b264ac3ac.pdf
   => reports/hellenic/demolition/pdfs/<that>.pdf   <-- does not exist (moved)
```
The PDF **does** exist, one tree over:
`corpus/02-hellenic/demolition/pdfs/2021-07-03_..._137b264ac3ac.pdf` (verified isfile=True).

A migration moved the archived linked PDFs out of `reports/<src>/<cat>/pdfs/` into
`corpus/<NN-src>/<cat>/pdfs/`, but the html `../pdfs/` refs still point at the old location.
`reports/hellenic/<cat>/pdfs/` retains only the **recent** assets (365 tracked, e.g. 2025-11
onward); everything older moved.
`git ls-files reports/breakwave/pdfs` = **0** -> the breakwave assets were never tracked on
main at all (they exist only inside the `.claude` / `.kilo` worktree checkouts).

**None are genuinely absent from the repo**: 0 of the 1,387 basenames are missing repo-wide
(excl `.git`); 1,386 sit in the worktree checkouts, 2,629 hits under `corpus/02-hellenic`,
13 under `corpus/03-breakwave/insights/pdfs`.

## The decisive experiment (proves the fix direction)

Remap ONLY the `source_path` of the linked-asset html rows to where the assets now live
(`reports/hellenic/...` -> `corpus/02-hellenic/...`; `reports/breakwave/<y>/...` ->
`corpus/03-breakwave/insights/<y>/...`), re-run the validator's own function:

| variant | unresolved |
|---|---|
| as-is | 1393 |
| hellenic rows remapped to corpus | **72** |
| hellenic + breakwave rows remapped to corpus | **65** |

Repointing resolves **1,328 / 1,393 (95.3%)**. The residual 65 are breakwave commodity-call
PDFs that were never mirrored into `corpus/03-breakwave/insights/pdfs/` (only 13 there;
the rest live only in the worktree checkouts).

Precondition verified: the mirror-image html exists under `corpus/`, and from THAT path the
`../pdfs/<name>.pdf` ref resolves (isfile True) - corpus html and corpus pdfs are siblings.

## Why `prune_superseded_mirror_rows` does not already fix it

`iter_source_files()` discovers hellenic/breakwave html from **REPORTS_ROOT (`reports/`)**
(line 1411+). So the *discovered* path is `reports/...`; `prune_superseded_mirror_rows`
drops the **corpus** rows as "superseded" and KEEPS the reports rows whose refs no longer
resolve. The dedupe keeps the wrong side for the asset check. That is why CI still shows
1393 after the prune fix landed.

## Fix options (both data-level; do NOT re-derive by eye)

A. **Repoint the html refs** (`../pdfs/` -> the corpus sibling location). 1,328/1,393 clean
   immediately; matches the skill's "explicit path field -> repoint" remedy. Touches served
   html content, so needs a before/after validator control.
B. **Mirror the moved assets back** to `reports/<src>/<cat>/pdfs/`. Consistent with the 365
   recent files already there, but adds ~1,387 PDFs to a tracked tree (size bloat) and 65
   breakwave assets are not in the main tree to copy.
C. **Re-point discovery / `make_archive_doc_id` side**: make the corpus html the discovered
   path for linked-asset sources. Highest leverage but tightly coupled to the parallel
   automation's de-mirroring work on `main`.

## Honest limits

- Measurement is on the LOCAL manifest (Oct 5 14:50); CI's composition matches (1393) but the
  local validator prints a different metric set than the CI runner - the remap experiment is
  an offline proof of the mechanism, not a CI-verified fix.
- Nothing was mutated this run (read-only + one new doc). No fix applied: the change touches
  served html and is co-owned with the parallel automation's de-mirroring. Recommend the
  owner/daily automation pick A or C with a validator control before/after.
- The books fix (`3fbc82f99`) still needs merging to `main` to reach CI.
