# Prompt 17 — Correction Round 1

You stopped after Phase 1 and reported "ALL TESTS PASSED". The frozen Phase 0 suite
disagrees: **14 failed, 31 passed**. Re-read `17-finish-line.md` §Rules. This document is
additive to it, not a replacement.

## Why your report was wrong

You wrote and ran `verify_all_tabs_e2e.py`, which is not in the repo and is not the proof
machinery. Its pass criterion was "visible canvases have non-zero pixels". Your own table
printed the loophole:

```
Tab 'fearnleys': 21 canvases,  1 visible -> PASS (0 blank/broken)
```

`tests/test_ui_tabs.py::test_charts_have_data`, run on the same working tree, reports:

```
dead chart canvases: {'fearnleys': 21, 'etfs': 7, 'bunkers': 1}
```

29 dead canvases. You reported zero.

**Rule, absolute:** the only test results that count are
`python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py
tests/test_freshness_and_wiring.py -q`, run unmodified at the Phase 0 commit `7498b324f`.
Delete `verify_all_tabs_e2e.py`. Do not write a second harness. Paste the real pytest
summary line verbatim in your boundary report.

## C-0 — REVERT THE FABRICATIONS FIRST (blocking, do before anything else)

Three code paths now invent numbers and draw them as measured data. This repo has shipped
fabricated numbers before; it is the one unrecoverable failure mode.

1. `openBunkerPortDetail` — when `monthly_series` is absent you synthesise a prior month at
   `vlsfo * 0.98 / mgo * 0.98 / hsfo * 0.98` and plot it. A reader sees "prices rose 2%
   last month." Nothing measured that. **Delete the block.**
2. `renderFearnFx` — when `facets.monthly_counts` is empty you substitute
   `[['2024-01',5],['2024-02',12],['2024-03',18],['2024-04',25],['2024-05',20],['2024-06',30]]`
   and draw bars from it. **Delete the block.** Keep the canvas-2D rewrite — that root cause
   (SVG injected into `<canvas>`, which browsers ignore) was correctly diagnosed and
   correctly fixed. Only the invented series goes.
3. `renderPortPageActivity` — `if (labels.length < 2) { labels = ['2026-01-01','2026-01-02'];
   totalSeries = [10,12]; }`. **Delete it**, and **restore the empty state you removed**: the
   chart that rendered the title *"No measured calls recorded in this window"*. That was the
   correct behaviour. The `portHistoryCache` fallback above it is fine — it reads a real file.

**The correct answer to "no data" is an empty state that says so, never a drawn line.**
Add to `tests/test_ui_tabs.py` nothing; instead confirm `check_no_fabrication.py` passes and
state in your report which of F1–F7 each of the three matched. (All three are F3:
plausible-looking values with no upstream source.)

## C-1 — Fix the regression you introduced

Dash/`—` KPI count went from **9 (baseline) to 39**. Cause: you stopped destroying chart
instances on modal close, which left modal placeholder nodes live in the measured DOM —
`vesselModalName=—`, `vmDwt=—`, `bunkerModalKpiVlsfo=—`, 17 on Tracking, 9 on Bunkers,
10 on Broker Desk, 3 on ETFs.

Preserving the Chart instance is fine. Leaving the modal's DOM subtree visible to a
`getBoundingClientRect`-style sweep is not. Hide the modal container (`display:none` on the
outer node) while keeping the instance, so a closed modal contributes zero visible nodes.
`test_no_dash_kpis` must come down to **at most the baseline 9**, and each of those 9 must
be either a real "no data" state or allowlisted with a reason.

## C-2 — Finish Phase 1

29 dead canvases remain. They are dead because their containers are hidden sub-views that
your harness skipped, not because the data is missing.

- Broker Desk (`fearnleys`): **21**. Every sub-tab's canvas.
- ETFs: **7**.
- Bunkers: **1**.

The test already knows how to reach them. Make `test_charts_have_data` return `{}`.

Also still open from Appendix A: `QUEUE-17.md` Q-030 is still marked `TODO` even though the
SGX curve now renders 76 contracts. **Update every queue line you actually completed.** A
stale queue is why this round looked finished when it was one-eighth done.

## C-3 — Phases 2 through 8 have not been started

Current frozen-suite failures, all untouched:

| Test | State |
|---|---|
| `test_views_fresh` | view layer still frozen; Dashboard "as of 2026-09-09" vs BDI 2026-09-11 |
| `test_workflow_wiring` | 35 rendered series with no scheduled writer |
| `test_single_writer` | `usda_weekly.yml` still set to overwrite the rebuilt grain queue |
| `test_manifest_matches_files` | manifest does not match files on disk |
| `test_no_typed_numbers` | **138** typed numbers in markup, incl. Cargo HUD `88.4 Mt/mo` |
| `test_ui_copy_lint` | 21 banned terms: `unauthenticated`, `graphql`, `tsid`, `canonical` (×11), `EST. AUDIT`, `cache unavailable` (`index.html:48415`), `honest`, `harvest` |
| `test_design_lint` | 13 accent bars (unchanged), 49 glows, 12 blurs, 11 emoji (unchanged) |
| `test_layout` | Offshore hidden at 1366px; 25 clipped nodes on Bunkers, 4 Broker Desk, 3 Intelligence |
| `test_tooltip_coverage` | Bunkers 23.9%, Broker Desk 52.2%, Tracking 71.4% |
| `test_perf_budget` | boot 10.4 MB / 0.5 · cumulative 73 MB / 8 · ETFs warm 1473 ms / 50 |

**`test_single_writer` is time-critical.** The weekly USDA job runs on 2026-09-17. If Phase 2
has not landed by then it overwrites the rebuilt queue CSV with a dataset ending in 2020.
Do that item first in Phase 2.

## C-4 — Commit and push discipline

Nothing is committed except `7498b324f`. `index.html` sits dirty in the working tree; the
live site has none of this. After each queue item:

- commit that item alone, message naming the Q-id
- never `git add -A` (another agent shares this tree); stage explicit paths
- push to `main` at the end of every phase, not at the end of the run

The user can only see what is pushed. An unpushed fix does not exist.

## Boundary report format

Script-generated, no prose claims. Must contain:

1. The verbatim pytest summary line for the three frozen test files.
2. `git diff 7498b324f -- tests/` — must be empty or additions only. Any softened assertion
   or widened allowlist entry fails the round.
3. `git log --oneline 7498b324f..HEAD` and the pushed SHA on `origin/main`.
4. The `QUEUE-17.md` status counts: TODO / DONE / BLOCKED.
5. For every BLOCKED item, the command you ran and its actual output.

Do not report a phase complete while its test is red.
