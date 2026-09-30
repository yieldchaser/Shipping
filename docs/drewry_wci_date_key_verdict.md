# Drewry WCI displayed index: the date key was the COLLECTION date (2026-09-30)

`data/indices/drewry_wci_historical.csv` is rendered by `index.html`. It was
repaired in two earlier sessions for VALUES. This one found the remaining defect:
the DATE KEY on the newest rows.

## The defect (measured, not inferred)

The publisher assesses the WCI on a **Thursday** and prints that date on its own
page (`assessment for Thursday, 06 Aug 2026`, `World Container Index - 06 Aug`).
`fetch_drewry_wci.py` fell back to the **run date** when it could not find that
phrase, so a live run on a Friday or Sunday stamped that day as the row's date.

Measured on the file as found (109 rows):

* **7 rows were not Thursdays** - and they were EXACTLY the 7 mis-dated rows:
  2026-08-25 (Tue), 09-04 (Fri), 09-06 (Sun), 09-07 (Mon), 09-11 (Fri),
  09-18 (Fri), 09-20 (Sun).
* the same weekly print therefore appeared 2-4 times: the **3 Sep print 4x**
  (09-03/04/06/07), the **10 Sep print 2x** (09-10/11), the **17 Sep print 2x**
  (09-18/20) with **no row dated 17 Sep at all**. 3 duplicate value-groups,
  5 surplus rows - the app drew observations on days the publisher made no
  assessment, and the 17 Sep print was filed 1-3 days late.

The values were NOT wrong: every one of the 5 surplus rows carried its print's
values byte-identically. Only the date key and the row count were wrong, which
is why a value-only recall check could not see it (the project's most expensive
lesson, again).

## Why the live code no longer produces them (measured)

Re-parsed all **230** cached snapshot pages in `scratch/wci/raw/` with the current
`extract_assessments()`:

| measurement | value |
|---|---|
| pages needing the "today" fallback (no page date found) | **0 / 230** |
| pages whose derived date is not a Thursday | **0 / 230** |
| e.g. the 2026-08-20 and 2026-08-24 captures | both -> page date **2026-08-20** |
| the 2026-09-06 capture | page date **2026-09-03** |

So the surplus rows are stale artefacts of the pre-2026-09-29 parser; the current
parser dates every page it has ever fetched correctly.

## The fix

`scripts/scrapers/repair_wci_collection_dates.py` (new, committed). For every row
whose date is not a Thursday it reads the print's own date off the publisher's
page and relabels the row; a row that duplicates a print already held is dropped
**only after checking its five values are identical to the kept row's**. Any row
it cannot derive is left alone and reported. Derivation is content-anchored (the
page phrase, never a hard-coded map); the derived date must be a Thursday, 0-10
days before the row's own date, and the page must print exactly one such phrase.

Applied: **109 -> 104 rows** (5 surplus rows dropped, 2 relabelled).

| action | rows |
|---|---|
| relabelled to the print's own date | 2026-08-25 -> **2026-08-20**, 2026-09-18 -> **2026-09-17** |
| dropped (duplicate of the 2026-09-03 print) | 09-04, 09-06, 09-07 |
| dropped (duplicate of the 2026-09-10 print) | 09-11 |
| dropped (duplicate of the 2026-09-17 print) | 09-20 |

Re-running the display merge then added **one genuine print the file had been
missing**: **2026-08-06** (4297 / 4653 / 5506 / 5894 / 7893), whose own page says
`assessment for Thursday, 06 Aug 2026`. Displayed total **105 rows**.

## Controls (all measured after the change)

* non-Thursday dates **7 -> 0**; duplicate value-groups **3 -> 0**; blank cells **0**.
* `git diff` is exactly 9 lines: 5 removed, 2 dates changed, 1 added. No value on
  any pre-existing row was touched (`VALUE CONTROL: rows whose five values differ
  from their input: 0`).
* dates unique and strictly increasing; range 2021-05-20 .. 2026-09-24.
* **idempotent**: a second run reports `109 -> 109`-equivalent no-ops (0 changes),
  and the repair script re-run on the repaired file changes 0 rows.
* **pipeline idempotence**: `backfill_wci_history.py --stack --era-from 2021-01-01`
  (103 prints, unchanged, gate census identical) followed by the display merge
  reports `105 existing + 0 backfilled = 105` and reproduces the file **byte-for-byte**
  (sha256 `5f623dd14038dcd6cab4ddcf6782d995e7c7e0b54ec89112556a97f93010855f`).
  The repaired file is a fixed point of the pipeline.
* **content grounding of the 6 newest rows** (2026-08-06 .. 09-24): all 30 values
  appear verbatim in that print's own page text - the cached snapshot for
  08-06/08-20/09-03/09-10/09-24, and the publisher's page text in
  `corpus/06-drewry/opinions/2026/2026-09-18_drewry_wci.md` (+ `_09-20_`) for the
  17 Sep print (4500 / 3626 / 4016 / 7712 / 10394, 5/5 in both).

**No vision tool in this session**, so the render-and-look step is substituted by
the same-document reconciliation above plus the page's own printed date phrase.
No network fetch was made: the box gets HTTP 429 from the live Drewry page and the
repair works entirely from page text already held in the repo.

## Open, named (not fixed here)

1. **The 9 corpus md files for 2026 carry the PRE-FIX fused table**:
   `shanghai_rotterdam == shanghai_genoa` and `shanghai_la == shanghai_ny` in all
   9 (`2026-08-24 .. 2026-09-25`, e.g. 09-04 reads 4465 / 4368 / 4368 / 7185 / 7185
   where the page's own prose says $4,092 Rotterdam and $9,587 New York). The CSV
   is repaired; the **md tier** (which feeds the knowledge chunks) is not. Each
   file's true values are in its own commentary prose, so this is fixable offline.
2. `upsert_wci_rows()` still dedupes by date only; with correct page dates that is
   sufficient, but a Thursday assertion on the stored date would make the class of
   defect impossible to reintroduce silently.
3. The standing ledger items are unchanged: 107 snapshots incomplete +
   4 numeric-gated + 1 fetch failure (all pre-2023, all named in the stack's gate
   census), and the 2021-07-01 "k labels, 2k numbers" lane shape.

## FOLLOW-UP 2026-09-30 15:4x - open item 1 is FIXED

The md tier was repaired by `scripts/scrapers/repair_wci_md_tier.py`:
**9 files -> 5 files, one per print, 0 fused lanes, 0 duplicate prints**.
The paths named above are now keyed by the print's own date (`2026-09-18` ->
`2026-09-17_drewry_wci.md`; `2026-09-20`/`2026-09-06`/`2026-09-07`/`2026-08-25`
removed as bodies identical to their kept print). Evidence and controls:
`docs/drewry_wci_md_tier_verdict.md`.
