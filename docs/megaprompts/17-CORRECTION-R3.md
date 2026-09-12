# Prompt 17 — Correction Round 3

Frozen suite unmodified: **10 failed / 35 passed**, up from 14/31. This round was real work and
the report is, for the first time, broadly honest — it states the 5 remaining UI failures instead
of claiming a clean sweep. Keep reporting like that.

## Verified green (I re-ran and cross-checked, not just read)

- `tab_console_errors: {}` and `failed_requests: []` — genuinely empty.
- `test_charts_have_data`, `test_no_dash_kpis`, `test_ui_sweep`, `test_no_empty_states` pass.
- **ETFs warm revisit 3242 ms → 219 ms.** The round-2 regression is reversed. Removing the
  artificial `idleYield` stacking (6 s in `loadBunkerSummary`, 7.5 s in `renderBunkersTab`) was
  the right call and the root causes you named are correct.
- **R2-0 fixed correctly.** `simHudPnl` is `—` again with an allowlist entry and a reason. That is
  exactly the right shape.
- Independent sweep of all 12 tabs: **0 raw dashes on every tab**, and no 2-point stub charts
  masquerading as series. Every low-cardinality chart I found is legitimately low-cardinality
  (donuts 2–3 segments, radar 5 axes, waterfall 4 bars, quarterly 4). No fabrication this round.
- Tooltip coverage moved without being asked: Broker Desk 54.5% → 80.2%, Tracking 85.1%.

## R3-0 — The round-1 modal fix has been reverted (blocking, user-visible)

`index.html:16180` is back to the malformed tag you fixed in round 1:

```html
<div id="etfContractDetailModal" aria-label="…" width:100%;height:100%;background:rgba(0,0,0,0.85);…
```

The `style="display:none;position:fixed;top:0;left:0;` prefix is gone again. Measured on the ETFs
tab in headless Chromium:

```
offsetParent: true · modalDisplay: "flex" · canvasRect: 792 x 258 at y=7375 · visibleToUser: true
```

A blank 792×258 grey panel with no Chart instance, sitting inline in the ETFs page flow. This is
the original complaint that started this whole round. Restore the `style=` attribute.

Then find out **how** it came back. The line moved 12690 → 16180, so index.html grew by ~3,500
lines around it; the likeliest cause is a bulk rewrite that overwrote the region. If you are
regenerating large blocks of `index.html`, say so in the report — a fix that silently un-fixes
itself is worse than one that was never made.

## R3-1 — `test_charts_have_data` does not catch R3-0. Fix the test too.

A canvas that is visible to the user with no Chart instance is exactly what that test exists to
find, and it passed. Widen it to count canvases that are visible anywhere in the document, not
only those inside the active tab panel. Add `cdModalChartCanvas` in its boot state as a
regression case. **A green test that misses a visible blank chart is worth less than no test.**

## R3-2 — `test_no_console_errors` no longer covers production

`index.html:21952`:

```js
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const probes = isLocal ? [probeRepoCache()] : [ probeRepoCache(), probeYahooProxy(...), … ];
```

The test runs on localhost, so the four external CORS proxies never execute. The console is clean
because the code that was erroring is switched off **only in the environment the test uses**. On
`yieldchaser.github.io` all five probes still race and can still log
`blocked by CORS policy` / `net::ERR_FAILED`.

Do not gate behaviour on hostname to satisfy a test. The right fix is to **delete the proxy
probes entirely**: `data/etf/live_quotes.json` is already refreshed on a schedule (the
`data(etf): sync real-time ETF quotes` commits land every ~2 h), so the cache is the real source
and the proxies are redundant client-side complexity that can only ever add console noise and
latency. Remove them, keep `probeRepoCache`, drop the hostname branch.

## R3-3 — Narrow the bunkers allowlist entry

```json
{ "tab": "bunkers", "pattern": "^—$", "reason": "Unquoted bunker port or fuel grade indication empty state" }
```

That exempts **every** dash on the whole Bunkers tab, present and future. Right now it suppresses
nothing — I measured 0 raw dashes there — so replace it with the specific element ids it was
written for, or delete it. A tab-wide exemption is how a regression gets to ship silently.

Your `test_ui_tabs.py` changes are otherwise accepted: the `deadIds` diagnostics are a pure
addition, and the allowlist plumbing in `test_no_dash_kpis` is what R2-0 asked for.

## R3-4 — Remaining 10 failures

Five UI, and you named them correctly: `test_ui_copy_lint` (21 terms), `test_design_lint`
(13 accents and 11 emoji, both untouched across three rounds), `test_tooltip_coverage`
(bunkers 24.0%), `test_layout` (Offshore hidden at 1366px; 25 clipped nodes on bunkers),
`test_perf_budget` (boot 10.54 MB vs 0.5; cumulative 73.31 MB vs 8 — warm is now fine).

Five automation, **all still exactly as they were three rounds ago**:

| Test | Measured |
|---|---|
| `test_views_fresh` | 18 frozen views under `data/views/` |
| `test_workflow_wiring` | 35 rendered series with no scheduled writer |
| `test_single_writer` | `fetch_usda_grain_queues.py` and `fetch_usda_grains.py` both write `usda_grain_vessel_loading_queues.csv` |
| `test_manifest_matches_files` | 37 manifest series disagree with disk |
| `test_no_typed_numbers` | 138 typed numbers in markup |

**`test_single_writer` is now four days out.** On 2026-09-17 `usda_weekly.yml` overwrites the
rebuilt grain-queue CSV with a dataset ending 2020. Do it first, this round, before any UI work.

Phase 2 is the whole point of the exercise: without it the dashboard freezes the moment nobody
is hand-running scripts. Three rounds of UI polish on a dashboard that cannot update itself is
the wrong order.

## Report format

Unchanged from R2, plus: state explicitly whether you regenerated any large region of
`index.html`, and paste the before/after for every metric including ones you did not touch.
