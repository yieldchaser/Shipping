# Prompt 18 — Finish

Self-contained. You do not need to read any other document. Baseline: `17779dea8` on `main`.

## The only definition of done

```bash
python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py tests/test_freshness_and_wiring.py -q
```

**`0 failed`.** Nothing else counts as finished. Right now it is **8 failed / 37 passed**.

Run that exact command. Do not write your own test harness — a previous round wrote
`verify_all_tabs_e2e.py`, scored "visible canvases have non-zero pixels", and reported ALL TESTS
PASSED while 27 canvases were dead. **A metric you choose is a metric you can satisfy.**

Work continuously. Do not stop to ask. Commit after each item, push at the end of each section.

## Seven rules that override any instinct to make a test go quiet

1. **Never invent a number.** No synthetic series, no `x * 0.98` for last month, no hardcoded
   sample arrays, no zero-filling. Past rounds shipped all three.
2. **The correct answer to "no data" is an empty state that says so.** Never a drawn line, never
   `+$0.00`, never a placeholder. A dash a reader understands beats a number that is false.
3. **Never weaken a test.** Strengthening is welcome. If a test asserts the wrong thing, say so in
   your report with the reason and fix it to assert the right thing — do not relax it quietly.
   Every change under `tests/` must appear in your report with a justification.
4. **Never branch on the environment.** No `hostname === 'localhost'`, no test-only code paths.
   Behaviour that differs under test is behaviour the test cannot check.
5. **No test-driven UI hacks.** Do not open a modal, mount a hidden chart, or render something
   off-screen to make a canvas count. One round called `openContractPriceInspector()` from a render
   path to force a canvas to mount; it popped a modal over the ETFs tab on every render.
6. **Check what was already green.** Report before/after for every metric, including ones you did
   not touch. Past rounds fixed one number and regressed three others.
7. **Never `git add -A`.** Another agent shares this tree. Stage explicit paths.

## Already fixed — do not redo, do not undo

`test_views_fresh` · `test_single_writer` · `test_charts_have_data` · `test_no_console_errors` ·
`test_no_dash_kpis` · `test_no_empty_states` · `test_ui_sweep` · `test_no_failed_requests` ·
`test_loader_contracts` 29/29.

- The ETF contract modal is hidden and its auto-open is gone.
- `fetchLiveETFQuote` is cache-only; `data/etf/live_quotes.json` is the source of truth.
- `build_views.py` stamps `as_of` on every view from that view's own newest non-future date, and
  `pages.yml` rebuilds views at deploy. **Never hand-edit anything under `data/views/`.**
- `fetch_usda_grain_queues.py` is the sole writer of `usda_grain_vessel_loading_queues.csv`.
- Chart.js is vendored at `vendor/chart.umd.min.js`. Do not point it back at a CDN.

## Known flake — read this before you panic

Two runs out of roughly ten reported a wall of failures (11 tabs with console errors, ~50 dead
canvases, `Chart is not defined`) that did not reproduce on the next run with identical code. The
audit harness races page load. **If a run looks catastrophically worse than the last one, re-run
before changing anything.** Two consecutive agreeing runs, or it did not happen. Making the harness
deterministic (waiting for a settled signal rather than a fixed timeout) is a legitimate
strengthening and would help everyone — but never paper over it by loosening an assertion.

---

# The eight

## Section A — automation (do this first; without it the dashboard cannot update itself)

### A1 · `test_workflow_wiring` — 27 rendered series with no scheduled writer

```
cargo_cargo_frontend_summary · cargo_commodity_flow_matrix · clarksons_braemar_live_rates
clarksons_gibson_all_reports_catalog · commodities_australia_ppa_iron_ore
commodities_australia_ppa_dampier_throughput · commodities_brazil_comexstat_exports
congestion_chokepoint_annotations · derived_alibra_tce_matrix · derived_chokepoint_transit_metrics
derived_fearnleys_fixtures_facets · derived_fearnleys_fixtures_tape · derived_fearnleys_summary
derived_lng_charter_rates · derived_lpg_charter_rates · derived_lpg_spot_rates
derived_macro_health_score_backtest · derived_offshore_summary · derived_scrappage_prices
derived_tanker_forward_curves · derived_tanker_forward_curves_history · derived_time_charter_rates
derived_vessel_valuations · snapshots_scenario_snapshots · provenance_manifest
reports_fearnleys_reports_catalog · reports_seabrokers_catalog
```

Each needs a scheduled workflow that runs its fetcher and commits the result. **Group by cadence
into a handful of workflows** — daily, weekly, monthly — rather than writing 27 separate files.
Follow the shape of the existing workflows in `.github/workflows/`.

`clarksons_braemar_live_rates` is the one the user named: it is labelled "Live GraphQL Feed" on
screen but is a one-time 10 Sep snapshot, and the endpoint has moved since. Either it refreshes on
a schedule or it stops calling itself live. Both is not an option.

If a source genuinely cannot be automated (needs a key you do not have, or a real browser session),
**say so explicitly with the command you ran and its output**, and leave the series labelled with
its real as-of date. A documented gap is acceptable; a silent one is not.

### A2 · `test_manifest_matches_files` — 37 manifest series disagree with disk

Regenerate the provenance manifest from the files that actually exist, and make each writer update
it in the same run so it cannot drift again. A manifest that lies is worse than no manifest.

### A3 · `test_no_typed_numbers` — 138 typed numbers in markup outside `<script>`

Every one is a number that cannot change when the data changes. The worst case is the Cargo HUD,
which types `88.4 Mt/mo` and `C3: $24.80/t` into the markup and badges them **LIVE** — the real C3
was $42.12 at the time. Render each from data, or delete it.

Where a number is a genuine modelling constant (vessel fuel burn per day), add it to
`data/reference/ui_test_allowlist.json` with its source. Follow the existing entries' shape. The
allowlist is for constants with provenance, not for numbers you would rather not fix.

## Section B — what the user sees

### B1 · `test_ui_copy_lint` — 21 internal terms on a front-facing dashboard

| Tab | Terms |
|---|---|
| fearnleys | `unauthenticated`, `graphql` |
| cargo | `audit`, `honest`, `zero ton-mile sliders`, `rule:`, `tsid`, `LIVE PAIRED`, `EST. AUDIT`, `540k Broker Fixtures`, `14 Flow Datasets` |
| tracking | `editorial estimate`, `computed from the chart series`, `LIVE FLEET AIS`, `ACTIVE REROUTING` |
| signals | `40 TENORS`, `15 Active Pricing Modules` |
| indices, intelligence | `api` |
| bunkers | `cache`, `harvest` |

`canonical` also appears 11 times in the file and means nothing to a reader. Give each control a
plain English label. Where the internal term explains something real, move the explanation into a
tooltip rather than deleting the meaning.

### B2 · `test_design_lint`

13 coloured left-edge accent bars · 49 box-shadow glows · 12 backdrop-filter blurs · 11 emoji.
The accent bars and the emoji have not moved in four rounds, and the user called them AI slop by
name. Dark theme, flat surfaces, one accent colour used sparingly, no decorative glow, no emoji in
UI chrome.

### B3 · `test_tooltip_coverage` — target 95%

bunkers 24.0% · fearnleys 80.2% · tracking 85.1% · cargo 88.7% · dashboard 89.4% · signals 89.7% ·
intelligence 82.5% · etfs 93.3%.

A tooltip says what the number means and where it came from. Baltic route codes (C3, C5, S4A, TD3,
TC20) must carry a plain-language gloss of the actual route.

### B4 · `test_layout`

The tab bar is 1,491 px inside a 1,400 px container, so **Offshore is off-screen at 1366 px**. Also
25 clipped text nodes on bunkers, 4 on fearnleys, 2 on intelligence. Must be clean at both 1366 and
1920.

### B5 · `test_perf_budget`

Boot transfer **10.4 MB** against a 0.5 MB budget. Cumulative **73 MB** against 8 MB. The warm tab
switch is already fixed at ~196 ms — do not touch the idle scheduler to chase the others.
Shortening those delays was a previous round's regression, because renders then fire before their
data lands.

This is a payload problem, not a scheduling one. Ship a small boot bundle and load each tab's data
when that tab opens. Tracking pulls an 18.7 MB CSV and the bunker summary is 4.4 MB at boot; those
are the two targets.

---

## Your report

Script-generated. Prose claims are not evidence. It must contain:

1. The verbatim pytest summary line from the command at the top of this document.
2. `git diff 17779dea8 -- tests/ data/reference/ui_test_allowlist.json` pasted in full, with every
   change justified.
3. The pushed SHA on `origin/main`.
4. A before/after line for all eight items above, including any you did not work on.
5. For anything you could not do: the command you ran and its actual output.

Do not report an item complete while its test is red.
