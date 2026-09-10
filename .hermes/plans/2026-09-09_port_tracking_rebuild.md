# Port Tracking Rebuild — Data Source Map (verified by probes, 2026-09-09)

## Standing rules (verbatim)
- "no hardcoded values, no data fabrication" / "don't break anything" / "Spin up the browser, use it to view that what you have done is actually good or not".
- Display only what we have or can accurately construct; label honestly (user rule).

## THE VERDICT ON THE OLD LINEUPS (must die)
`scripts/geospatial/build_geospatial_tracker.py` (462 lines) synthesizes:
- `port_lineups_active.csv` — "Waiting at anchor"/"Operating at berth" statuses are NOT measured;
  arrival = fixture date, departure = fixture date +3 days (hardcoded), days_waiting = date diff,
  IMO = crc32 hash (9000000+n) when missing, DWT = class-standard constants (every VLCC 305000).
- `vessel_voyage_tracks_master` + `ui_voyage_vectors.csv` — polyline "trajectories" = straight
  lines between the 40 hardcoded hub coordinates with pseudo-sequences.
Fixture-grounded voyage history is REAL (reported fixture legs) but ship-position/lineup fields are
fabricated. PortWatch scraper header itself documents this family was already caught once
(2026-08-25: seeded random-walk waiting-times removed).

## FREE DATA WE ALREADY HOLD (real)
- `data/congestion/portwatch_port_congestion.csv` == `port_calls_daily_v2.csv` (BYTE-IDENTICAL
  DUPLICATE — drop one): 43 ports × 2019-01-01→2026-08-28, daily calls by class
  (total/dry_bulk/tanker/container) + import/export kt for dry_bulk & tanker. Producer:
  scripts/scrapers/fetch_portwatch_port_activity.py (real-only since 2026-08-25 audit).
- `chokepoint_transits_daily.csv` 28 chokepoints 2019→2026-08-30 (+ geo summary json).
- `port_arrival_envelope_matrix` (per-port arrival envelopes), 8 MB port_calls_daily.csv (v1).
- Fixture-grounded: fearnleys_fixtures_full.csv → real voyage legs (load/discharge ports, dates).

## FREE SOURCES VERIFIED LIVE (expand into)
ArcGIS root: https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services (no auth;
1000-record page cap; ObjectId order != date order — paginate by exceededTransferLimit).
- `Daily_Ports_Data` (FeatureServer/0): ≥1000 ports (exceededTransferLimit), 2019-01-01→2026-08-28,
  calls by class incl. container + kt by class. We currently keep only 43 ports → 16–30× expansion
  available FREE. This is the reference site's "different ports per sector" answer.
- `PortWatch_ports_database` (2065 rows): portid/portname/country/ISO3/continent/lat/lon/LOCODE +
  vessel_count_* by type + industry_top1..3 + share_country_maritime_import/export
  = INFRASTRUCTURE TAB (reference site's "infrastructure") — measured.
- `PortWatch_chokepoints_database` (28 rows): same schema for chokepoints.
- `portwatch_disruptions_database` (132 events, live): eventid/eventtype(EQ,TC,WF,OT…)/eventname/
  alertlevel(RED)/country/fromdate/todate(epoch ms)/severitytext/affectedports/n_affectedports/
  affectedpopulation. Example live: TC BAVI-26 RED 37 ports affected; HORMUZ-26 RED ongoing.
  = DISRUPTIONS/EVENTS FEED (free, measured) — replaces nothing, adds real event context.
- NOT vessel-level: PortWatch has NO per-vessel AIS/lineup dataset (the reference site's lineups
  run on licensed AIS we cannot get free). "95K ships tracked" = their AIS backbone, aggregated.

## NOT FREE / SHELVED (documented, no fabrication)
- Live per-vessel AIS (MarineTraffic/VesselFinder/Spire/VT Explorer): paid or signup-keyed.
- aisstream.io free websocket: requires account key — user asleep, no credentials; do NOT sign up.
- UN Global Platform / VizaFact AIS-derived weekly port calls: portal registration required.
- Global Fishing Watch API: free tier exists but fishing-focused; not for freight lineups.

## SECTORS WE CAN MEASURE
Tanker + Dry Bulk + Container (+ LNG/LPG via fixture segments only — PortWatch has no LNG/LPG
class in Daily_Ports_Data; LNG/LPG port activity comes from our fixture-grounded data, labeled).

## PHASE TD (data, agent-safe now — no index.html touched)
1. `scripts/scrapers/fetch_portwatch_ports_expanded.py`:
   - Full port universe from `PortWatch_ports_database` (all 2065) → data/geospatial/portwatch_ports_master.csv
     (infrastructure facts verbatim: lat/lon, vessel_count_*, industry_top1..3, shares, LOCODE).
   - Chokepoints database → data/congestion/chokepoints_master.csv.
   - Daily_Ports_Data for the EXPANDED port set: priority tiers —
     tier1: all ports with ANY daily row 2025→ (full backfill to 2019-01-01),
     tier2: rest of 2065 universe (their full history is same endpoint; ingest if payload allows,
     else keep tier1 in daily table + universe facts for the rest — decide by measured bytes).
     Target file data/congestion/port_calls_daily_expanded.csv (+ parquet); gzip if >25 MB,
     but the UI bundle stays PRUNED (bundle-size rule).
   - Disruptions database full pull → data/congestion/portwatch_disruptions.csv (132+ events,
     epoch→ISO, affectedports list split).
   - INCREMENTAL MODE --refresh (date > max) wired into .github/workflows/data_expansion.yml
     as its own step (do not touch bunker/fearnleys steps).
   - NO synthetic statuses, NO synthetic IMOs, NO +3-day departures anywhere.
2. Kill the duplicate: retire port_calls_daily_v2.csv (byte-dup of portwatch_port_congestion.csv);
   keep the canonical name; update consumers (grep first).
3. Fixture-grounded history: `scripts/geospatial/build_voyage_history.py` REWRITE of the tracker
   WITHOUT fabrication: keep real fields (vessel, IMO-as-reported, class, load/discharge, dates,
   leg sequence, computed great-circle distance between REPORTED ports) →
   data/geospatial/voyage_history_fixturegrounded.{csv,parquet}. Drop lat/lon polylines, drop
   status/days_waiting, drop generated IMOs and DWT constants. UI labels it
   "reported fixture voyages — not AIS positions" (phase UI).
4. Tests: tests/test_portwatch_expanded.py — real-JSON fixtures; assert no synthetic columns
   (status/days_waiting absent), counts ≥ measured floors (ports ≥1000 universe rows, disruptions
   ≥100 events), date monotonic, duplicate file gone, workflow wiring present.
5. Commits split code/data; push rebase-first; dispatch data_expansion.yml once + watch green;
   verify origin via git show origin/main:<path>. Report JSON: files, rows/ports/events counts,
   byte sizes, tests, commits, workflow_run, origin_verification, notes (payload decisions).
   DO NOT touch index.html (audit agent owns it), bunker/, fearnleys steps.

## PHASE TU (UI — later, blocked on audit agent releasing index.html)
Rebuild Tracking tab: sector modes (Tanker/Dry Bulk/Container from PortWatch classes; LNG/LPG
from fixture-grounded), port universe 2065 with facts + search, per-port daily charts, chokepoints,
disruption events with alert badges, arrival envelopes; fixture voyage history labeled honestly;
Intelligence-style dynamic tooltips everywhere; no code-speak; browser-verified via preview + headless.

### REFERENCE FULLY DECODED (all 11 shots) → TU feature map
Shots: (1) port Live View w/ filters+map legend+multi-port tab strip; (2) Bunkers tab
(AREA/PORT/GRADE/PRICE/7-DAY AVG/UPDATED, VLSFO $933 Richards Bay); (3-4) per-vessel
Live/Voyages/Particulars/Valuation + voyage timeline legs/durations/STS; (5-6) same port in
Tanker vs Dry sector modes w/ different lineup columns; (7) full dry columns
Status/ETD/Terminal/Previous Port/Cargo Type/Quantity; (8) LNG mode honest EMPTY state
("No Rows To Show" — reference itself does not fabricate); (9-10) LNG Ras Laffan lineups
(RasGas/Qatargas, ETA, quantity in m³); (11) global Ports landing: search + world map pins.
TU BUILD ORDER (honest analogs, all from TD output + our caches):
1. PORTS LANDING (analog of shot 11): search box over ports_master (~2,065, real lat/lon) +
   Leaflet world map with port pins (class-colored by vessel_count mix) + disruption event pins
   (separate legend chip); KPI strip = global yesterday calls, 7d avg, active disruptions.
2. PORT PAGE: sector mode tabs Tanker/Dry Bulk/Container (PortWatch classes) + LNG/LPG
   (fixture-grounded, badged); "Activity" panel = daily calls chart by class + import/export kt;
   "Recent reported fixtures" table (vessel/class/charterer/commodity/laycan/rate from fixtures
   tape filtered by resolved port aliases) = honest analog of lineup rows; Bunkers tab from OUR
   180-port archive (grade rows, price, computed 7-day avg, updated date — REAL); Port Expenses
   tab OMITTED (no free source — no fake); honest empty state per sector×port mirrors shot 8.
3. MULTI-PORT TAB STRIP: pin any port into tabs (client-side session state), default = our hubs.
4. PER-VESSEL VIEW (from fixture tape): voyage timeline (dated legs, load→discharge, computed GC
   distance where resolved), labeled "reported fixture voyages — not AIS"; no STS/valuation
   (not in data). Vessel search across fixtures tape vessels.
5. CHOKEPOINTS panel (28, real) + DISRUPTIONS feed (132 events, alert badges, ongoing flag).
6. Legacy synthetic surfaces (lineups KPI strip, pin sizing by waiting count, voyage polylines)
   REMOVED — replaced by the above; before/after screenshots in scratch/port_tracking/.
PRIORITY 0 — SYNTHETIC SURFACES MUST NOT SURVIVE: remove every UI embed/renderer built on
port_lineups_active (operational_status/days_waiting are fabricated), ui_voyage_vectors.csv and
vessel_voyage_tracks_master (pseudo-polyline "trajectories", generated IMOs). Replace with the
honest layers below; if a replacement isn't ready at ship time, the surface is omitted, not faked.
MEASURED REFS in index.html (2026-09-09): port_lineups_active x4 (incl. a rt-note tooltip
"waiting-vessel count per port (port_lineups_active.csv snapshot…)" — that map pin sizing itself
is fabricated-data-driven), vessel_voyage_tracks_master x1, portwatch_port_congestion x3,
ui_voyage_vectors x0, port_arrival_envelope x0. The TD agent retires port_calls_daily_v2.csv
(byte-dup); grep index.html for it at UI time too.
BONUS (data already in hand): the reference site's per-port BUNKER tab maps 1:1 to OUR bunker
archive — 180 daily bunker ports (e.g. Valletta 265 obs days) in data/bunkers/ master + BUX/BIX
history. Port page gets a real bunker price panel from our own archive, clearly sourced.
Reference capabilities to be inspired-by (not copied): multi-port lineup tabs (any port, not a
fixed list), full lineup columns (ETA/ETD, Vessel, Class, Operator, Purpose, Status, Terminal,
Previous Port, Cargo Type, Quantity), per-vessel voyage timeline (legs, STS history), per-port
bunker tab, sector modes (Tanker/Dry/LNG/LPG), map with legend chips + coordinate readout.
OUR HONEST VERSION (only measured data — UI must say what each layer IS):
- Port universe: search across ALL ingested ports (TD output, ~1000-2000+); each port page =
  daily calls chart (by class), import/export kt, facts card (vessel_count by type, industry_top1..3,
  country import/export share) from ports_master — all real PortWatch fields.
- Sector modes: Tanker / Dry Bulk / Container (PortWatch classes); LNG & LPG modes = fixture-grounded
  (badge: "reported fixtures, not AIS"); do NOT fake LNG/LPG port calls.
- Live "lineup" equivalent: we CANNOT show today's anchored ships honestly — instead show
  "Port activity: calls + tonnage, daily" and disruption events affecting the port. Any surface that
  would need live AIS is explicitly omitted, not faked.
- Disruptions feed: event cards (type EQ/TC/WF, alert level badge, severity text, affected ports
  count, from/to dates, ongoing flag) — map pins where lat/long present.
- Chokepoints: keep existing 28-chokepoint charts; add chokepoints_master facts.
- Voyage history: per-vessel fixture leg timeline (real legs + computed GC distance where resolved),
  labeled "reported fixture voyages — not AIS positions".
- Tooltips: Intelligence-grade dynamic (rt-title + labeled rows from live caches) on every port card,
  chart, event, filter; honest omissions when a field doesn't exist.
- Design: Blue Margin tokens (#0d1117/#161b22/#30363d, #388bfd accent), dense tables, sticky headers,
  zebra rows, hover accent; no left-edge accent stripes; no emoji; no code-speak.
- Payload: UI embeds PRUNED slices only (per-port daily aggregates + selected ports' series);
  full CSVs stay in repo; watch the ~60MB deployed payload budget.

### PHASE 2 EXECUTION BRIEF (Broker Desk rewiring — runs when index.html frees)
Verified 2026-09-09: both daily caches LIVE on production (Pages data fetch, no embed):
- https://yieldchaser.github.io/Shipping/data/derived/fearnleys_tanker_routes_daily.json
  3,769,569 B · 126 series / 191,421 pts · date_to 2026-09-08 (sha 9aecd435faaa)
- .../fearnleys_dry_routes_daily.json 456,986 B · 12 series (sha c9cf564a5776)
index.html working tree: 0 refs to either cache (S3 still renders the 22MB monthly CSV;
fearnpulse_rates_full x3 refs). WIRING = fetch() the JSON from data/ path (same pattern as
existing caches) — no inline embed, size-safe.
S3 rewrite: per-klass tab group (VLCC/Suezmax/Aframax/Dirty/1Y TC/Fuel Oil/Weekly) with
per-route tiles (label, unit, last value, day delta, first/last meta, live vs frozen badge —
frozen = last < 2026-08, reason: source 2023-05 taxonomy switch ended tce twins), click-through
daily chart, Intelligence tooltips from cache meta. Dry-route benchmark grid: 12 series
(Capesize/Panamax/Supramax RV+TCE+usd/tonne) with per-series first dates in meta.
Do NOT unilaterally add World 3 / BIX regions; keep bunker tab data as-is.
Quality gates unchanged: full pytest, headless sweep 0 console errors, screenshots,
push rebase-first, Pages deploy watch, live hash verify.


### PHASE 3 CHECK ITEMS (parent-measured, post-wave)
- MEASURED 126-series split (probe of fearnleys_tanker_routes_daily.json): 79 LIVE (last>=2026-08),
  8 FROZEN-REAL (real values, ended 2023-04-25 tce twins), 39 ALL-ZERO never-published branches
  (n=1351-1353 or 505-844, every value 0). Phase 2b (deleg_6da10fcb) excludes the 39 from tiles
  with an honest footer; badge semantics split LIVE vs FROZEN-REAL. Fresh audit verifies: no
  all-zero tile anywhere, footer present, FROZEN badge count == 8, klass tab counts match shown series.
1. S1 Overview tiles still read fearnleys_series_monthly (monthly means of fearnpulse_rates_full).
   MUST measure the source cadence of the BULK class TC series per subtype (first probe confounded:
   6,818 TC rows / 56.7 yrs across segments). If a series is daily/weekly-native, monthly display
   violates the standing rule — rewire to daily cache or disclose why monthly matches the source's
   own publication granularity. S3/S4 fixed daily-native (commit 5b9623d59, deploy 34289601562).
2. TU: after TD lands, grep index.html for legacy synthetic refs (port_lineups_active x3,
   vessel_voyage_tracks_master x1) — all must be gone after the Tracking rebuild.
3. Fresh-audit wave watch list: live/frozen badge honesty, tooltip coverage on new P2/TU elements,
   bundle size delta after both phases (stay well under payload budget).

### PHASE 2E BRIEF (queued behind 2c tooltip agent releasing index.html)
USER DIRECTIVE (verbatim intent): the Indices tab has a range slider that 'works perfectly':
52-week high-low, 52-week position %, YTD %, from-last-drop %. Port that pattern to the charts
in Broker Desk: Tanker Routes (tile charts), Dry Routes, TC Rates, LNG Desk, LPG Desk, wherever
applicable. 'Think about this very properly and also do this... any other scope of improvement
along this line of thinking, then do it. No breaking anything, no introducing bugs.'
DESIGN (parent pre-analysis, agent verifies against the actual Indices implementation):
- Reuse the Indices tab's existing stats/slider components if extractable; otherwise replicate
  its exact pattern (it is the approved model).
- Per-chart stat strip (52W high / 52W low / current position in 52W range % / YTD % / drawdown
  from last peak) computed FROM THE CHART'S OWN loaded points at render time (cache-derived,
  never hardcoded); annotate the plotted 52W high/low as dashed reference lines + labels.
- Apply to: S3 tanker tile charts, S4 dry charts, TC Rates charts, LNG/LPG desk charts,
  Overview tile sparklines optional (only if it stays clean at that size).
- Range slider: mirror Indices' interaction (zoom window select) on the big route charts.
- Also add the 2D-derived TCE series tiles once they land (klass grids + 'derived' badge +
  fit disclosure tooltip from the derivation_notes), and fix any LIVE-series-zero tiles the
  2D census surfaces (e.g. NOVO/USG WS: badge or exclude per finding).
GATES (lessons learned): per-panel div-balance check excluding script content; 9-tab leak sweep;
headless render of every touched section with 0 console errors; annotateCoverageGaps stays 0
missing; full pytest; node --check; before/after screenshots; production verify (hash + spot
markers) before reporting done. NO em dashes in any new tooltip/note text.

### 2E AMENDMENT (user, 2026-09-09)
- Frozen-tile tooltips: state only the user-facing fact - the source stopped publishing this TCE series (last date shown); the Worldscale twin carries the market now. NO 'inference tested/failed' narration, no QC speak.

### PHASE SPEED BRIEF (measured baseline 2026-09-09, parent probes)
PRODUCTION: initial load 9.1s networkidle / 71 data fetches / 18.8 MB data on landing
(top offenders: portwatch_port_congestion.csv 7.97 MB eager, vessel_valuations 0.84 MB,
fearnleys_series_monthly 0.66 MB, sgx futures ~0.55 MB each, chokepoint_geo_summary 0.58 MB).
Tab first paints (incl 2.5s settle in measurement): Yearly 5.9s, Signals 4.7s, ETFs 3.9s,
Indices 3.1s, Seasonality 2.9s, Tracking 2.9s, Bunkers 3.0s, Offshore 2.9s, Intelligence 2.8s,
Broker Desk 2.7s. Warm switches: Broker Desk 5.4s (!), Tracking 2.6s, Bunkers 3.3s.
THE 80/20: (1) Broker Desk warm switch re-renders everything each visit (5.4s warm = render-bound,
not network) - memoize rendered sections (render-once + dirty flags; 2c/2E sections already
render-once), (2) portwatch_port_congestion.csv 7.97 MB eager on landing - defer to Tracking
tab first-open (same lazy pattern TU used for the expanded file), (3) Yearly/Signals first paint
- find the per-tab eager heavy work (backtest? matrix builds) and lazy-build on first visit.
GATES: same as always (190+ suite, node blocks, token scan, leak sweep, per-tab screenshots,
production hash). No visual changes beyond latency. Measure again post-change with the same probe
(saved scratch/audit/speed_probe1.py) and report before/after per tab.
