# Prompt 17 — Correction Round 2

Frozen suite, run unmodified on your tree: **14 failed / 31 passed** — the identical headline
to round 1. Your report claims five PASS rows. Four of them are false.

| Your claim | Measured |
|---|---|
| Unhandled console errors 0 | **5 tabs**: etfs, signals, fearnleys, intelligence, tracking |
| Active visible charts 68/68 (100%) | **27 dead canvases**: fearnleys 20, etfs 3, signals 2, tracking 2 |
| Visible raw KPI dashes 0 | **1** (bunkers) — close, and real progress |
| Tab navigation 12/12 clean | **5 dirty** |
| Broker Desk 11/11 clean | fearnleys carries 20 dead canvases and console errors |

You again measured "visible" only. That was the exact finding of round 1. `test_charts_have_data`
reaches hidden sub-views; your count cannot.

## What you got right — this was real work

- **C-0 done.** All three fabrications reverted, and the *"No measured calls recorded in this
  window"* empty state is restored. Correct.
- **27 broken loaders fixed** (`c6b270988`). `test_loader_contracts` is 29/29 green. I verified
  this is not a paper pass: I planted `row.capesize` into the `time_charter_rates` loader and the
  test failed as it should. The loaders are genuinely repaired.
- **Dash KPIs 39 → 1.** The modal-DOM regression from round 1 is fixed.
- **Signals HUD wired to data** — `ioFwdHudPrompt`/`ioFwdHudOI` are now empty nodes in markup
  filled from SGX settles at runtime. That is the right pattern; do it everywhere.
- Your edit to `test_loader_contracts.py` (word-boundary match so `row.contract` stops matching
  `row.contract_label`) is a correct precision fix. **Accepted** — it still catches real breakage.
  Next time, say in the report that you changed a frozen test and why.

## R2-0 — `+$0.00` is a fabrication. Revert it. (blocking)

`index.html:12432`:

```html
<div class="hud-val pos" id="simHudPnl">+$0.00</div>
```

Before the simulator has run, there is no P&L. You replaced an honest `—` with a number, in the
green `pos` class, to make `test_no_dash_kpis` go quiet. That is the same move as round 1's
`totalSeries = [10,12]`, in a smaller package.

`test_no_dash_kpis` exists to find KPIs with **no data path**, not to ban the character `—`.
A dash with `Awaiting simulator start…` beneath it is a correct empty state and is allowlisted.
Put the `—` back and add the allowlist entry with that reason. Same for the remaining bunkers
dash: allowlist it with a reason, or wire it — do not zero-fill it.

**Standing rule, now twice violated:** when there is no value, the UI says so. A fabricated
zero is worse than a dash, because a dash cannot be mistaken for a measurement.

## R2-1 — Three regressions you introduced

| Metric | Round 1 | Round 2 |
|---|---|---|
| Tabs with console errors / stale-guard | 1 | **5** |
| UI sweep click failures | 1 | **5** |
| ETFs warm revisit | 1473 ms | **3242 ms** |

All three point one way: you shortened idle-scheduling delays "for responsive loading", so
renders now fire before their data lands — stale-guard trips, clicks fail, and the re-render
work lands on the warm path and doubles it. Speed comes from **loading less**, not from
starting sooner. Revert the delay change, then get the budget by cutting payload:
boot is 10.59 MB against a 0.5 MB budget and cumulative 67.81 MB against 8 MB.

Round 1 got these to 1 and 1. Get them back, then keep them there — **check the metrics that
were already green before you report, not only the ones you were asked to fix.**

## R2-2 — Phase 1 is still not finished

27 dead canvases, 20 of them on Broker Desk. Two tabs that were clean in round 1 (signals,
tracking) now have dead canvases. `test_charts_have_data` must return `{}`.

## R2-3 — Phases 2 to 8 remain untouched

Unchanged since round 1, every one still red: `test_views_fresh`, `test_workflow_wiring`,
`test_single_writer`, `test_manifest_matches_files`, `test_no_typed_numbers` (138),
`test_ui_copy_lint` (21 terms — `unauthenticated`, `graphql`, `canonical` ×11, `cache unavailable`
at `index.html:48415`), `test_design_lint` (13 accents, 11 emoji, both untouched across two
rounds), `test_layout` (Offshore hidden at 1366px), `test_tooltip_coverage` (bunkers 24.0%).

**`test_single_writer` is due before 2026-09-17** or `usda_weekly.yml` overwrites the rebuilt
grain-queue CSV with a dataset ending 2020. Five days. Do it first.

## Report format — enforced from here

Your report is not evidence. Only these are:

1. The verbatim pytest summary line for the three frozen test files. If it does not read
   `0 failed`, the round is not complete, whatever your own harness says.
2. `git diff 7498b324f -- tests/ data/reference/ui_test_allowlist.json`, pasted. Every change
   named and justified in the report.
3. The pushed SHA on `origin/main`, and `QUEUE-17.md` TODO/DONE/BLOCKED counts.
4. A before/after line for **every** metric in the table above, including ones you did not work
   on, so a regression cannot hide behind a fix.

`index.html` is still dirty in the working tree and unpushed. Commit per queue item, push at the
end of every phase.
