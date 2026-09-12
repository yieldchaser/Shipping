# Prompt 17 — Correction Round 4

Frozen suite: **9 failed / 36 passed** at `86cc840d6`. R3-0 through R3-3 are closed, and the
two Phase 2 tests that mattered most are green. I fixed those myself; everything below is yours.

Run the suite unmodified and paste the summary line. Tests may be strengthened, never weakened.

## Already done — do not redo, do not undo

- `test_views_fresh` ✅ · `test_single_writer` ✅ · `test_charts_have_data` ✅ ·
  `test_no_console_errors` ✅ · `test_ui_sweep` ✅ · `test_no_empty_states` ✅ ·
  `test_loader_contracts` 29/29 ✅
- The ETF contract modal is hidden again, **and** the auto-open that popped it over the ETFs tab
  on every render is gone. Do not reintroduce a call to `openContractPriceInspector` from a
  render path — it opens on user click only.
- `fetchLiveETFQuote` is cache-only. Do not add proxies back, and never branch on
  `window.location.hostname` — behaviour that differs under test is behaviour the test cannot check.
- `build_views.py` stamps `as_of` on every view from the view's own newest non-future date.
  `pages.yml` now rebuilds views at deploy. Never hand-edit a file under `data/views/`.

## The nine that remain

### Automation (do these first — they are why the dashboard cannot update itself)

**Q-A1 `test_workflow_wiring` — 27 rendered series with no scheduled writer.** Down from 35.
Each needs a workflow that runs its fetcher on a sane cadence and commits the result. The list:

```
cargo_cargo_frontend_summary · cargo_commodity_flow_matrix · clarksons_braemar_live_rates
clarksons_gibson_all_reports_catalog · commodities_australia_ppa_iron_ore
commodities_australia_ppa_dampier_throughput · commodities_brazil_comexstat_exports
congestion_chokepoint_annotations · derived_alibra_tce_matrix
derived_chokepoint_transit_metrics · derived_fearnleys_fixtures_facets
derived_fearnleys_fixtures_tape · derived_fearnleys_summary · derived_lng_charter_rates
derived_lpg_charter_rates · derived_lpg_spot_rates · derived_macro_health_score_backtest
derived_offshore_summary · derived_scrappage_prices · derived_tanker_forward_curves
derived_tanker_forward_curves_history · derived_time_charter_rates · derived_vessel_valuations
snapshots_scenario_snapshots · provenance_manifest · reports_fearnleys_reports_catalog
reports_seabrokers_catalog
```

Group them into a few workflows by cadence rather than writing 27 files. `clarksons_braemar_live_rates`
is the one the user called out by name: it is shown as a "Live GraphQL Feed" but is a one-time
10 Sep snapshot, and the endpoint has moved since. Either it updates on a schedule or it stops
claiming to be live.

**Q-A2 `test_manifest_matches_files` — 37 manifest series disagree with disk.** Regenerate the
provenance manifest from the files that actually exist, and make whatever writes data update it
in the same run. A manifest that drifts is worse than none.

**Q-A3 `test_no_typed_numbers` — 138 typed numbers in markup outside `<script>`.** Every one is a
number that cannot change when the data changes. The Cargo HUD tiles are the worst case
(`88.4 Mt/mo`, `C3: $24.80/t` badged LIVE while the real C3 was $42.12). Render them from data or
delete them. Where a number is a genuine modelling constant (vessel fuel burn), allowlist it with
its source — the allowlist already has that shape.

### Copy and design

**Q-B1 `test_ui_copy_lint` — 21 banned terms, unchanged for four rounds.**

| Tab | Terms |
|---|---|
| fearnleys | `unauthenticated`, `graphql` |
| cargo | `audit`, `honest`, `zero ton-mile sliders`, `rule:`, `tsid`, `LIVE PAIRED`, `EST. AUDIT`, `540k Broker Fixtures`, `14 Flow Datasets` |
| tracking | `editorial estimate`, `computed from the chart's own series`, `LIVE FLEET AIS`, `ACTIVE REROUTING` |
| signals | `40 TENORS`, `15 Active Pricing Modules` |
| indices, intelligence | `api` |
| bunkers | `cache`, `harvest` |

These are internal words on a front-facing dashboard. `canonical` appears 11 times in the file and
means nothing to a reader. Where a term explains something real, move the explanation into a
tooltip and give the visible label a plain name.

**Q-B2 `test_design_lint` — 13 coloured left-edge accents and 11 emoji, both untouched since the
baseline.** Also 49 box-shadow glows and 12 backdrop blurs. Appendix D has the token set. The
accent bars are the specific thing the user called AI slop.

**Q-B3 `test_tooltip_coverage`** — bunkers 24.0%, fearnleys 80.2%, tracking 85.1%, and five tabs
in the high 80s. Target 95%. Tooltips must explain what a number means and where it came from.

**Q-B4 `test_layout`** — the tab bar is 1,491 px in a 1,400 px container, so **Offshore is hidden
at 1366 px**. Plus 25 clipped text nodes on bunkers, 4 on fearnleys, 2 on intelligence.

**Q-B5 `test_no_dash_kpis` — 1 dash on bunkers.** I deleted the tab-wide allowlist entry that was
hiding it. Wire it to data, or allowlist that one element by id with a reason. Do not zero-fill it.

**Q-B6 `test_perf_budget`** — boot 10.4 MB against 0.5, cumulative 73 MB against 8. Warm switch is
already fixed (196 ms). This is a payload problem: ship less at boot, load per tab. Do not
"fix" it by shortening idle delays — that was the round-2 regression.

## One flake worth knowing about

One suite run reported 11 tabs with console errors and ~50 dead canvases, with `Chart is not
defined` throughout. It did not reproduce; the next run was clean with identical code. Chart.js is
loading from a CDN, so a network hiccup takes down every chart in the run. If you see a wall of
failures that vanishes on re-run, that is this. Worth vendoring Chart.js locally so the suite does
not depend on the network — count that as part of Q-B6, since it also removes a boot request.

## Report format

Unchanged: the verbatim pytest summary line, `git diff 86cc840d6 -- tests/ data/reference/`,
the pushed SHA, QUEUE-17 counts, and a before/after for every metric including ones you did not
touch.
