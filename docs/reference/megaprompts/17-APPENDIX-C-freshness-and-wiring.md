# 17 — APPENDIX C: freshness and automation baseline (measured 2026-09-11/12)

Everything here was verified by reading the repo, the workflows and the GitHub run history.

## C1 — The view layer is frozen

`scripts/build_views.py` (and `scripts/acquire/build_signals_views.py`) build **28 files under
`data/views/`**. Every one was last written by the Round 1 commit `d21185f31` (2026-09-10) and
**no workflow runs either script**.

| Evidence | Value |
|---|---|
| `data/views/dashboard_master.json` header | `"as_of": "2026-09-09"`, last date in `dates`: `2026-09-09` |
| `data/indices/bdiy_historical.csv` (its source, updated daily) | last row `2026-09-11,3507.0` |
| Header shown to the user | "Data as of 2026-09-09" |

So the Dashboard, all 17 index views, the ETF summary, the port-call summary and the Signal Ocean
views drift further from the daily data every day. `pages.yml` only uploads the repo — it has no
build step.

**Required fix:** build views as part of deployment. Add a build step to `pages.yml` (before
`upload-pages-artifact`) that runs every view/cache builder, so what is published is always built
from the newest data:
`scripts/build_views.py`, `scripts/acquire/build_signals_views.py`, `scripts/cargo/build_cargo_cache.py`,
`scripts/cargo/build_commodity_flow_matrix.py`, `scripts/bunkers/build_bunker_cache.py`,
`scripts/fearnleys/build_fearnleys_cache.py`, `scripts/offshore/build_offshore_cache.py`,
`scripts/verify/build_provenance_manifest.py` (plus any builder you find that writes into
`data/views/`, `data/cargo/`, `data/bunkers/`, `data/derived/*summary*`).
Run the same set in the nightly data workflows so the committed files don't rot either.

## C2 — 35 rendered series have no scheduled writer

Cross-referencing `data/provenance/manifest.json` (`fetch_script`) against
`.github/workflows/*.yml`, **35 series that `index.html` actually loads are produced by a script no
workflow calls**, including:

`scripts/cargo/build_cargo_cache.py` (the whole Cargo tab) · `scripts/cargo/build_commodity_flow_matrix.py` ·
`scripts/build_views.py` (Dashboard, indices, ETF, port calls, 5 Signal views) ·
`scripts/acquire/fetch_pilbara_ports.py` · `scripts/acquire/fetch_brazil_comexstat_full.py` ·
`scripts/acquire/fetch_usda_grain_queues.py` · `scripts/clarksons/fetch_braemar_rates.py` ·
`scripts/clarksons/scrape_gibson_catalog.py` · `scripts/fearnleys/build_fixtures_tape.py` ·
`scripts/fearnleys/build_fearnleys_cache.py` · `scripts/offshore/build_offshore_cache.py` ·
`scripts/integrate_alibra_feed.py` (TC rates, tanker forward curves) ·
`scripts/backfill_historical_data.py` (vessel valuations) · `scripts/extract_demolition_pdfs.py` (scrap prices) ·
`scripts/backtest_macro_health_radar.py` · `scripts/scenario_snapshot_schema.py`.

⚠ The manifest's `fetch_script` may be wrong for some entries (e.g. the Alibra poller workflow may
write the tanker curves under a different script name). **Verify the real writer** — grep `scripts/`
for the output filename — before concluding a file is unscheduled.

Five rendered series have `fetch_script: None`: `derived_chokepoint_transit_metrics`,
`congestion_chokepoint_annotations`, `derived_lng_charter_rates`, `derived_lpg_charter_rates`,
`derived_lpg_spot_rates`.

## C3 — Sources that are stale or static but presented as live

| What the UI says | Reality |
|---|---|
| Tracking: "LIVE FLEET AIS" | `data/views/signal/live_fleet_positions.json` and the Signal Ocean vessel files were written once (2026-09-10) and nothing refreshes them |
| Broker Desk: "Live GraphQL Feed" | `data/clarksons/braemar_live_rates.json` committed once (2026-09-10 18:51). The endpoint updates daily: Cape Sep was **$53,250** in our file and **$51,250** when polled on 2026-09-11 18:20 UTC |
| Tracking port calls "latest 2026-08-28" | `data/congestion/portwatch_port_congestion.csv` last committed 2026-09-07; PortWatch itself lags ~2 weeks — check which script writes it (`scripts/scrapers/fetch_portwatch_port_activity.py`) and whether any workflow calls it |
| Bunkers "obs 2026-09-04" | BIX observation 5+ days old at audit time |

Braemar after the London close shows `price == prevClose` for every product, so whether it moves
intraday is **unknown** — poll every 30 minutes through one London session (07:00–17:30 UTC) and
record the answer before labelling it.

## C4 — A workflow that will damage data

`usda_weekly.yml` runs `scripts/scrapers/fetch_usda_grains.py`, which downloads Socrata dataset
`uiht-9xts` straight over `data/commodities/usda_grain_vessel_loading_queues.csv`. That dataset
**ends in 2020** and uses `MM/DD/YYYY`, while the file in the repo now holds 1995→2026 with ISO
dates and the loading/waiting-to-load columns. First run after deployment destroys it.
Remove that entry from `fetch_usda_grains.py` and call `scripts/acquire/fetch_usda_grain_queues.py`
from `usda_weekly.yml` instead. Check every other Socrata entry in that script the same way:
**exactly one writer per file.**

## C5 — Hand-typed data files still in the render path

- `data/derived/chokepoint_transit_metrics.csv` — no builder script, unregistered in the manifest,
  and Bab-el-Mandeb and Suez carry identical `avg_rerouting_voyage_days_added = 14.5` and
  `implied_tonne_mile_expansion_pct = 28.4`. These drive Tracking's "CAPE VOYAGE DELAY +14.5 Days"
  and "TONNE-MILE EXPANSION +28.4%" KPIs, and its `daily_transit_count = 14.2` contradicts the
  PortWatch-derived 25.4/day shown beside it.
- `index.html` Cargo HUD tiles are **typed into the markup** and labelled LIVE:
  `88.4 Mt/mo`, `Brazil: 32.1 Mt | Port Hedland: 56.3 Mt`, `24.6 Mt`,
  `Top Destination: Mexico (6.8 Mt) & Japan (4.2 Mt)`, `+$14.20 / MT`,
  `C3: $24.80/t | C5: $10.60/t`. Today's real values from the same repo: C3 **$42.12**, C5
  **$17.85** (Broker Desk dry-route tiles), Port Hedland July 2026 **44.2 Mt**. Either the JS never
  overwrites them or it fails; either way the markup must hold no numbers.
- Other typed numbers found in markup: `32.1 Mt/mo`, `$24.80 / MT`, `Showing 1–50 of 213 ports`,
  `50% EU voyage scope @ €68/t EUA`, `Capesize (45 MT/day)` and three more vessel-consumption
  constants (these last ones are legitimate assumptions — label them as assumptions and allowlist).

## C6 — Data quality problems visible on screen

- **Broker Desk → LNG Desk** opens on "1 Yr TC 120-130k 1ST Gen" showing **$1,000/day** with
  ATL **0** and a flat 500→1,000 line. Pick a defensible default series and add a plausibility
  band per asset class (an LNG carrier 1-year TC is tens of thousands of $/day, never 1,000).
- **Broker Desk → TC Rates**: all five KPIs show `n/a`; the spot-vs-period chart's legend lists
  "1-Year TC" and "Spot/1Y Ratio" but only the spot line is drawn (the `time_charter_rates.csv`
  mapping in Appendix A).
- **Broker Desk → S&P & Assets**: tenor-ladder and 5y/NB charts blank, all four valuation KPIs `—`,
  range slider stuck on "Loading…" (`vessel_valuations.csv` mapping).
- **Cargo → Commodity Flow Matrix**: `total_qty_mt` sums only the fixtures that report a quantity
  (grain: 50,132 fixtures → 2.6 Mt ≈ 52 t per fixture, impossible; "Other Minor Cargoes" shows
  3,269.6 Mt). Report fixtures-with-quantity and median parcel size, and treat parcels outside
  1,000–450,000 t as unparseable.
- **Signals**: eight modules have no chart object at all — FFA term structure (BDRY, BWET),
  BDI daily-change contribution, lead-lag correlation, ETF premium/discount z-score, ETF fund flow
  signals, SGX FFA forward curve, SGX iron-ore term structure.
- **Tracking**: `renderTrackingHUDRefreshNote is not defined` (ReferenceError), "awaiting
  disruptions feed", `hudDisruptionsActive = —`.
- **Bunkers**: 20 change values clipped mid-text ("-4.95 (…").
- Five charts on Signals (basis, spread, Bollinger, historical volatility, seasonal) render only
  **after being scrolled into view** — any UI test must scroll the whole tab before judging.
