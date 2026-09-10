# Tracking / Bunkers / Fearnleys rebuild plan

> For Hermes: implement via subagents, one worktree per builder. No fabricated data. Verify in CI before done.

**Goal:** Rebuild tracking + bunkers into differentiated, fully-utilized terminals; surface Fearnleys Hasura breadth (11/356 ids live, ~97% uncharted) via new desk; merge seasonality tabs.

**Architecture:** Keep single-file `index.html` (40861L/2.3M) + `build_*_cache.py → *_summary.json → render*` pattern (offshore reference). No backend, no bundle split.

---

## Recon facts (verified, no fab)

- Tracking shell `#tab-tracking` L13580-13966; dispatch L20273; state L35492-35546; render fns L35548-40861. Loads: port_lineups_active.csv (1568 rows, 36 locodes, Tank 1217/LPG 185/LNG 103/Dry 63, DWT 3 distinct values — flag), vessel_trajectories_active.json (1568 keys), chokepoint_geo_summary.json (28 cps, 2019-01→2026-08-30), chokepoint_transit_metrics.csv (10 rows static), bunker_prices_daily.csv (420 rows, 17d), port_stress_summary.json (50 hubs). NEVER fetched: chokepoint_transits_daily (78372×20), port_calls_daily (150596×30, 1457 ports), port_arrival_envelope (20000×7), voyage_tracks_master (24424×12). Workflow data_expansion.yml Mon-Thu 05:00 never rebuilds lineup/stress → stale. Bugs: HUD static 740/306/434 vs CSV 1568; parser L15766-68 reads anchorage/wait cols absent → null; 41/50 hub mismatch; distance tool great-circle×fudge + fixed canal NM.
- Bunkers: renderBunkersTab L39446-39482, state L39429-43, 18 fns L39484-40120 + legacy renderBunkersSubView L35940 (duplicate surface). Master 482024 rows / 221 ports / 2018-02→2026-09; daily 420 rows; fwd 72 rows (6 hubs); volumes 106 rows (SG+RTM only); bix 150 rows (5 idx). build_bunker_cache.py 471L → bunker_frontend_summary.json 1.48M (meta 2026-09-07, 482778 recs). Copy proven 8 blocks: guards, Esri tiles, state names, pagination-50, subview toggle, flyTo+highlight, empty-state nouns, data-tt bus. Dead: `.bunkers-port-row.selected` no CSS; KPI subs hardcoded L13994-14019; change_7d always 0.0; benchmarks_bix 0 grep hits; LNG/MEOH/EUA parsed never rendered; daily series 35/221 silent monthly fallback.
- Signals/Fearnleys: time_charter_rates 2084×66; _fearnleys 1599×8; catalog 356 (TANK 165/LNG 71/S&P 67/LPG 27/NB 17/BULK 8); fearnpulse_full 305199×7; fixtures 538164×16 (1974-2026); snp 2601; comments 11714; valuations 20499; lpg 359+1152; lng 513; scrappage 379; restocking 1260; backtest 1984×24 NEVER fetched. Scripts: build_fearnleys_cache 450L + daily_sync 444L (Hasura pbrokerapp), fetch_* under scripts/ root, fearnleys_weekly Wed/Thu. Signals renders 5 Fearnleys blocks; ~3% catalog surfaced; broker_sentiment 0 render fns.
- Offshore ref: renderOffshoreTab L40122-40555, state L40112, CSS L5262-5462. Chain: fetch_seabrokers_reports 543L → build_offshore_cache 238L → offshore_summary 313KB + catalog 97 reports + dayrates 42KB. Patterns: summary.json cache, dual-write reports/+data, regex-first PDF, cat_map, KPI-as-filter, envelope avg+min/max fill-1 + util y1, data-tt bus, ledger search 25/pg, report cards w/ PDF links, non-blocking bootstrap.
- UX audit: integrity 0 critical / 14 warnings; headless 0 pageerrors 0 console errors, all charts have points; lazy stress chart OK after subview switch. Real fails: DATA.usdaBunkers len 0 (date parse `2019-January-01/29/2019`), DATA.usdaCostSpreads dead key, renderQDDataGrid double-call L17638-39. KPIs consistent; tooltips 137/137 branched; loader dynamic total OK. Merge quarterly+monthly+heatmaps: merge-safe → one Seasonality tab; distinct canvas ids; unify win-rate matrix dup; batch-3 render cost.

## Build phases (code vs data commits split; branch, push-no-merge)

1. **Pipeline truth** — add build_geospatial_tracker + compute_port_stress_matrix + build_port_stress_cache to data_expansion.yml; fix parser cols or drop dead parse; compute change_7d in builder; reconcile 41/50 hubs + HUD fallbacks. Tests: integrity gate 0 critical; pytest.
2. **Tracking rebuild** — arrival_timestamp first-class (queue build/clear); tonnage lens (capacity_* + import/export kt); sector toggles incl Container/GenCargo/RoRo; dry-bulk coverage or disclosed bias; chokepoint-aware Suez-vs-Cape deltas (rerouting_days + bunker feed); voyage-leg econ in popup. Offshore patterns: KPI-as-filter, envelope idiom, data-tt tooltips, ledger search.
3. **Bunkers differentiation** — kill/sync legacy Tracking mini-view; BIX benchmark strip; LNG/MEOH/EUA alt-fuel cols; live KPI deltas; change/high-low sparklines; fix selected-row CSS; honest volumes label (2 ports); daily-fallback notice + expand benchmark list.
4. **Fearnleys desk (new tab)** — 10 views: TC browser (356 picker + pct bands); term spreads; percentile atlas; tanker WS wall; LNG desk; LPG desk; NB/parity; fixture tape (538k search + league); S&P + broker voice (11.7k stream); backtest lab. Wire macro_health backtest fetch.
5. **Seasonality merge** — quarterly+monthly+heatmaps → one tab; dedupe win-rate matrix; fix QDDataGrid double-call; keep heatmap %/abs state.
6. **Verify** — http.server 127.0.0.1 + headless tab-click + select sweep 0 errors; labeled screenshots desktop+mobile; integrity 0 critical; `gh workflow run` + watch green + `gh run list` clean. Raw pytest/ruff outputs pasted.

## Risks
- Parallel builders on one clone → HEAD race; use one worktree per builder.
- 146M bunker_master.json payload drift → never fetch master direct; summary.json only.
- DWT 3-value + future arrival_timestamp → disclose diagnostic, never smooth over.
- Scope creep → tracking/bunkers/fearnleys first; seasonality last.
