# SSY fix APPLIED and independently verified (hourly supervisor 345bc8db9233)

**When:** 2026-09-24 04:30-04:34 IST. **What:** the parked "needs a human" item 1
from the 3-hourly review (job d77cc9df53c4, commit 5dbe6da77 on
`auto/extract-fixes-2026-09-24`) - re-run SSY to apply the already-measured fix
to the 519 extracted docs.

## What was done
- Parked the resume state (`data/extracted/md/ssy/_run_state.json` ->
  `scratch/ssy_apply/_run_state.preapply.json`) so all 519 docs re-process.
  A plain re-run would have been a NO-OP: main() skips any stem already in
  `_run_state.json['done']` (519 of 519 were done).
- Snapshot of the pre-fix outputs: `scratch/ssy_apply/before_snapshot/` (519 .md).
- Ran `python3 scripts/extract/publishers/run_ssy.py` (working tree already
  carries the fix; `git diff 5dbe6da77 -- run_ssy.py` is empty).
- **Result: ok=519/519, failed=0, elapsed 60 s.** Log `scratch/ssy_apply/run.log`.

## Independent verification (this run, not the other job's numbers)
| measure | before | after | expected by 5dbe6da77 |
|---|---|---|---|
| n_rows total | 8,696 | **8,515** | 8,515 (181 junk chart-axis rows) |
| trade_rates | 5,920 | **5,191** | 5,191 |
| timecharter_day_rates | 0 | **729** | +729 |
| index keys | 3,114 | 3,114 | unchanged |
| docs with a column header | 15 (crude test) | **519 of 519** | 519/519 |
| .md files changed | - | 519 of 519 | - |
| .md files SMALLER than before | - | **0** | 0 |
| total .md bytes | 707,750 | 783,241 | - |

5,191 + 729 = 5,920, i.e. the rate block was relabelled, not lost. Every number
reproduces the fix commit's claim exactly.

## Risk checked before touching it
- No consumer: `grep -rl "extracted/md"` across `scripts/`, `data/`, `index.html`
  finds only extraction/verify scripts - the app does not read `md/ssy`.
  corpus.duckdb is built from `data/extracted/corpus/*/tables.jsonl`, a different
  tree, so the DB and the app are untouched by this re-run.
- No git operation was performed (no pull/commit/push/checkout).

## Still open for the owner (from the same review)
- 8 SSY docs are byte-identical duplicates (`ssy_2026_nan_<date>-{Atlantic,Pacific}`
  vs the same names without `nan`), so 8 docs sit in the output twice.
  Decide: dedup in the runner, or accept.
