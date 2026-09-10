# Fearnpulse-inspired utilization pass — verified facts & task spec (2026-09-09)

## Standing rules (verbatim user constraints)
- If data is there or can be accurately constructed → keep it; else shelve it. Display only what we have.
- No "not in source feeds" style notes in UI. Never fabricate. Daily data must display daily (never monthly-compressed).
- Tooltips: custom, detailed, dynamic, everywhere (Intelligence-tab style: rt-title + labeled rows, cache-derived only, honest omission).
- index.html single-writer at a time. Push rebase-first. Split code/data commits.

## A. NEW SOURCE (captured & verified by parent)
- Endpoint: `GET https://fearnpulse.com/api/marketapi/TS?last={n}&id={tsId}&date_to={date}` (no auth; omit `last` for FULL history). Response `{columns, index, data:[[tsId, value, epoch_ms, seq],...]}` NEWEST-FIRST; epoch ms UTC midnights.
- Data lands (Phase 1 agent): `data/derived/fearnleys_dry_routes_daily.json` (UI cache, chronological `pts:[[epoch_ms,value],...]`, keys below) + `data/derived/fearnpulse_dry_routes_full.csv` (archive). Producer `scripts/fearnleys/fetch_dry_routes_ts.py` wired into data_expansion.yml daily.
- tsId → series (12 incl. derived):
  - Capesize: 120655 'TCE Cont/Far East' usd/day · 10002 'Australia/China' usd/tonne · 120654 'Pacific RV' usd/day
  - Panamax: 10010 'Transatlantic RV' · 10011 'TCE Cont/Far East' · 10013 'TCE Far East/Cont' · 10012 'TCE Far East RV' (usd/day)
  - Supramax: 120132+120133 raw pair → DERIVED 'Transatlantic RV' (mean-of-pair, published-midpoint formula, disclose in tooltip) · 120129 'US Gulf - China/South Japan' · 120137 'South China - Indonesia RV' (usd/day)
- CORROBORATION PROOF (parent, live): all 9 checkable series EXACTLY match the published Week-36 (2026-09-02) report tiles (21623=21623, 31364=31364, 12860=12860, 20998=20998, 89167=89167, 51036=51036, 16.5=16.5, 31222=31222, 15806=15806) and d-1 deltas are consistent.
- Depth (measured by Phase 1, real launch-date differences — show per-series first date in UI meta, never imply uniform depth):
  - 10002 Capesize Australia/China: 6,875 rows 1999-03-01→ · 120655 Capesize TCE Cont/FE + 120654 Pacific RV: 505 rows 2024-09-02→
  - Panamax 10010/10011/10013/10012: 2,167 rows 2018-01-02→ · Supramax 120132/120133/120129: 840 rows, 120137: 855, 2023-05-02→
- API order QUIRK: no-`last` full-history responses arrive OLDEST-first (the `last=N` form arrives newest-first) — producer normalizes by detection.
- Market Brief tsIds (306/307/303/304 Singapore+Rotterdam bunkers, 5002/5001/5003 FX, 12100 SOFR, 316 Brent) are STALE on source (last obs 2021–mid-2026) → SHELVED per user rule. Do not display.

## B. S3 "Tanker Routes" defect (fix in this pass)
- Current: renders TANK route series from the MONTHLY cache with visible badge "DAILY native · since 2018-05 · cadence gap 1d · plotted monthly (≈27× obs compression)". Violates daily-display rule.
- Fix (Phase 1b + Phase 2): new cache `data/derived/fearnleys_tanker_routes_daily.json` (per-series daily pts, built from fearnpulse_rates_full.csv TANK rows by `scripts/fearnleys/build_tanker_routes_daily.py`, CI-wired, tests with floors) → S3 re-renders DAILY native: KPI cards become daily-aware (latest + Δ vs prior obs + 30d range + percentile), select list shows cadence 'daily', chart plots daily points (decimation only for canvas via pointRadius 0 — data stays daily), tooltip notes cadence + source.
- TANK daily universe (from monthly cache label inventory; daily raw in fearnpulse_rates_full.csv 2018-05→2026-09-08): VLCC 26 routes (12 TCE) · Suezmax 37 (18 TCE) · Aframax 43 (17 TCE) · Dirty 9 WS · 1 Year T/C 3 · Baltic Index 15 (stale 2023-04) · Fuel Oil 5 · Weekly VLCC 2 · VLCC/Suezmax MARKET 9 (stale 2023) · Equinor 1 (stale).

## C. Unrendered-family inventory (parent, measured)
- 294 monthly-cached labels; rendered today: BULK_TC ×8 (S2), NEWBUILDING ×17 (S4), S&P ×67 (S5), LNG/LPG families (S6/S7), TANK 1_YEAR_T_C ×3 (Overview), S3 shows WS routes monthly, Museum (S9) carries stale subtypes (BALTIC INDEX, SUEZMAX-MARKET, VLCC-MARKET, EQUINOR, MARKET, BLPG).
- TRULY unrendered anywhere: TANK_FUEL_OIL_ ×5 (SKAW/SPORE, CBS-USG/SPORE, USG/UKC — live to 2026-09) · TANK_WEEKLY_VLCC ×2 (fixed last week / available MEG 30d — live weekly, on their report) · COUNTS_ ×1 (MEG Fixture Count — live to 2026-09-01).
- Action: surface these in S3 as a "Fuel & Fleet Counters" group (fuel oil series live-daily; VLCC counters weekly — badge the cadence honestly; fixture count weekly). Tooltips: unit, cadence, last-obs date, Δ vs prior, span.

## D. Phase 2 UI spec (single index.html agent; after audit agent lands AND Phase 1+1b data on origin)
1. FDESK_SECTIONS: insert `{ id: 12, name: 'Dry Routes' }` after id 2 (TC Rates). New section: three class groups (Capesize, Panamax, Supramax) × tile grid (value + daily Δ + spark) → click-through full daily chart (range presets 1M/3M/6M/1Y/ALL), every tile + chart + control Intelligence-grade tooltips (incl. Supramax-avg derivation note on the two avg tiles + raw-pair disclosure).
2. S3 daily-native upgrade per §B (select stays; KPIs/charts go daily; remove the monthly-compression badge, replace with honest daily meta).
3. "Fuel & Fleet Counters" group in S3 per §C.
4. Tooltip sweep of everything touched; no code-speak; no new fetch without a consumer.
5. Gates: pytest full suite, headless 0-console-error sweep of sections 1,2,3,12 (+sub-sections), node --check, screenshots, commit, push rebase-first, watch Pages deploy green, live hash + marker check.

## Sequencing
- NOW: Phase 1 (dry-route capture) running; audit agent (index.html owner) running.
- NEXT: Phase 1b (tanker-routes daily cache builder) after Phase 1 returns (shares data_expansion.yml + scripts/fearnleys/).
- THEN: Phase 2 (UI) after audit agent lands + Phase 1b data on origin.
- FINALLY: fresh full audit pass (tooltip + hardcoded + all-tab headless) re-run over the new UI.
