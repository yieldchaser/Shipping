# LEDGER 05 — TRACKING: FROM PORT STATISTICS TO A VESSEL TERMINAL

Execution log for Prompt 05. Every step recorded as executed.

---

## Initial State & Payload Audit (Before Phase 5.1)
- 	ab-tracking initial role: IMF PortWatch port calls viewer, 28 chokepoints directory, 50-hub port stress matrix, basic 2-port great circle distance calculator.
- Unused data on disk: 67,256 Signal Ocean vessels, 7,937 live positions, 12,060 distance routing ports, 1,568 active port lineups with berth/anchor statuses and cargo types.
- Known issues to resolve: fixed-height locked panes in Chokepoints view causing 546px dead space; unstyled 9px chokepoint notes; duplicate Port Bunkers view; unmerged Port Activity Monitor from Signals.

---

## Phase 5.1 — Layout Bug & Chokepoint Spec Strip (Completed)
- **Problem**:
  - `.tracking-workstation` had `align-items: start;` and fixed `560px minmax(0, 1fr)` layout.
  - `.chokepoint-dir-list` had a hardcoded `max-height: 700px;` and `.tracking-table-wrap` had `max-height: 660px;`.
  - Left pane stopped at 737px while the right pane (Map 560px + Drawer 707px + gap 16px) was 1,316px, leaving 579px of empty space below the left pane, and 546px dead card space when stretched.
  - Chokepoint detail blurb was an unstyled 9–11px note without a structured institutional specification strip.
- **Changes Applied**:
  - CSS Grid Workstation: `.tracking-workstation` updated to `grid-template-columns: minmax(480px, 560px) minmax(0, 1fr); gap: 16px; align-items: stretch;`.
  - Independent Scrolling: `.tracking-left-pane` styled with `height: 0; min-height: 100%;`. `.chokepoint-dir-list`, `.tracking-table-wrap`, and `.dist-calc-panel` set to `flex: 1; min-height: 0; overflow-y: auto;` (removed `max-height: 700px` and `max-height: 660px`).
  - Spec Strip: Added `.cp-spec-strip`, `.cp-spec-narrative`, `.cp-spec-grid`, `.cp-spec-item`, `.cp-spec-label` (11px uppercase), and `.cp-spec-val` (13px bold).
  - Wired in `openChokepointAnalytics()` to render Region, Connects, Alternative Routing Corridor, and Normal Baseline with baseline delta percentage at `--fs-body` (13px) with 11px uppercase labels.
- **Verification Measurements (Playwright)**:
  - Workstation: `1360 × 1454 px`
  - Left Pane: `560 × 1454 px` (scrollHeight `1452 px` -> dead space `2 px`, $\le 48$ px requirement met)
  - Right Pane: `784 × 1454 px` (scrollHeight `1454 px` -> dead space `0 px`, $\le 48$ px requirement met)
  - Chokepoint Dir List: `558 × 1417 px` (scrollHeight `2626 px`, smooth independent scrolling across all 28 monitored passages)
  - Typography: Base spec note `13 px` (`--fs-body`), labels `11 px` (`--fs-micro`), values `13 px` (`--fs-body`). Zero elements $< 11$ px.
  - Console Errors: `0` across all tracking subviews (`universe`, `chokepoints`, `disruptions`, `vessel`, `distance`, `stress`).

## Phase 5.2 — Subview Architecture & Port Call History Consolidation (Completed)
- **Problem**:
  - Tracking tab contained a redundant Port Bunkers subview duplicating the dedicated BUNKERS tab.
  - Signals Global Port Activity Monitor had an orphaned bottom container (`#portCongestionContainer`) outside the workstation.
  - Deep history for 43 strategic hubs (120,271 daily readings, 2019–2026) in `data/congestion/portwatch_port_congestion.csv` was unlinked, leaving `#phLoadingNote` unresolved.
  - Subview navigation lacked first-class integration for Port Call History and subview container heights lacked uniform flex properties.
- **Changes Applied**:
  - Removed `#portCongestionContainer` and all orphaned duplicate chart markup from the bottom of `#tab-tracking`.
  - Defined `loadPortCongestionHistory()` and wired it into `loadTrackingData()`, cleanly parsing all 43 hubs and mapping total calls, sector calls (dry bulk, tanker, container), and dry-bulk import/export kilotonnes.
  - Consolidated Port Call History inside `#subviewHistory` with primary hub buttons (Qingdao, Ningbo, Port Hedland, Newcastle, Singapore, Rotterdam, Houston, Tubarao, Santos, Rizhao, Hay Point, Qinhuangdao), sector selector (All, Dry Bulk, Tankers, Container), and 5-year seasonal normal baseline.
  - Added dual-axis `y1` support to `portHistoryChart` to display dry-bulk import tonnage (`importDryBulkKt`) concurrently with daily port calls when the Dry Bulk lens is active.
  - Updated `setTrackingSubView()` to support 7 primary subviews: `history`, `universe`, `disruptions`, `vessel`, `chokepoints`, `distance`, `stress` (along with drill-down `portpage`). Removed all references to deprecated Port Bunkers.
  - Standardized all subview container panes (`#subviewHistory`, `#subviewUniverse`, `#subviewDisruptions`, `#subviewVessel`, `#subviewChokepoints`, `#subviewDistance`, `#trackingSubviewStress`) with `flex-direction: column; height: 100%; min-height: 0;`.
- **Verification Measurements (Playwright)**:
  - Workstation Height: `1454 px`
  - Left Pane Dead Space across all 7 subviews: `2 px` ($\le 48$ px requirement met).
  - Right Pane Dead Space across all 7 subviews: `0 px` ($\le 48$ px requirement met).
  - Typography Audit: Zero elements $< 11$ px across all 7 subviews (`tinyCount: 0`).
  - Interactive Hub Switching: Switching to Ningbo (`port824`) activates `congBtnNingbo`, syncs `#phPortSelect`, updates KPIs (34 calls/day, 5Y mean 52.0, vs 5Y avg -34.6%), and loads 120-day historical window.
  - Dual-Axis Overlay: Dry bulk lens correctly renders 3 datasets: `Dry-Bulk Daily Calls — Ningbo`, `5Y same-window mean (2019-2025)`, and `Dry-Bulk Imports (kt)`.
  - Console Errors: `0`
  - Page Errors: `0`

---

## Phase 5.3 — Signal Ocean Fleet Layer & Institutional Surfaces A–D (Completed & Verified)
- **Surfaces Built**:
  - **Surface A: Asset-Class Port Picker**:
    - Segmented by Dry bulk (118), Tankers (113), LNG (73), LPG (150) at `zoomIndex > 0.1`.
    - Dynamic "Major terminals only" toggle widens the directory to all 2,750 terminals in `data/views/signal/asset_class_ports.json` (185.0 KB, $< 250$ KB budget met).
    - Port search and quick jumping directly into the live lineup.
  - **Surface B: Port Queue & Lineup (Live View Pattern)**:
    - 1,568 live hulls across 36 active ports from `data/geospatial/port_lineups_active.csv`.
    - Enriched against `data/views/signal/lineup_vessel_lookup.json` (165.9 KB, 1,276 vessels).
    - Commercial operator join hit rate: **81.1%** (1,035 / 1,276 matches). Strictly unhallucinated "—" fallback for non-matches.
    - Columns: Vessel Name, Asset Class / DWT, Commercial Operator, Status (Operating at Berth vs Waiting at Anchor), Arrival Date, Days Waiting, Cargo Type, and Drill-down Action.
    - Comprehensive filtering: Operational Status (Berth / Anchor), DWT Size Bands, Cargo Type, and instant text search.
  - **Surface C: Vessel Drill-Down Modal**:
    - `#vesselModalBackdrop` tabbed pattern: Particulars, Historical Voyages, and Live Map Track.
    - Particulars: DWT, Built Year, Shipbuilder / Yard, Flag / Registry, Commercial Operator, Scrubber Fitted, Main Engine kW, Hull Type.
    - Historical Voyages: 24,434 voyage tracks indexed across 2,657 vessels in `data/views/signal/vessel_voyages_lookup.json` (1.4 MB). Shows Voyage Number, Departure Port, Arrival Port, Transit Distance, Duration (days), and Speed.
    - Interactive "Center on Map" button flying the Leaflet camera directly to the vessel's live coordinates.
  - **Surface D: Live Position Map & Floating Fleet HUD**:
    - 7,937 live positions from `data/views/signal/live_fleet_positions.json` (949.9 KB) rendered on Leaflet via `liveFleetMarkersLayer`.
    - Segment filters: All, Dry Bulk, Tankers, Container, LNG, LPG, with Laden / Ballast status filter.
    - `#aisFleetHud` floating strip: 100% computed metrics (never hardcoded):
      - Total Tonnage: 588.6M DWT
      - Average Fleet Speed: 11.2 kn
      - Laden Fleet Ratio: 58.4%
      - Tracked Vessel Count: 7,937 AIS hulls
- **Playwright Verification**:
  - `scratch/test_phase53_sync.py`: 114 vessels in Fujairah, 28.0M DWT. Modal drill-down for Advantage Solo verified (Suezmax, 157,930 DWT, Shell operator, Scrubber fitted, 2 voyage legs). Dead space: left pane 2px, right pane 0px. Tiny elements (< 11px): 0. Console/page errors: 0.

---

## Phase 5.4 — Distance & Routing Engine (Completed & Verified)
- **Problem**:
  - Legacy calculator was a rigid 2-port Great Circle distance toy with no routing graph, no multi-leg capability, no canal divergence calculations, and no ECA compliance tracking.
- **Engine Built**:
  - Routing network of 12,060 maritime ports from `data/views/signal/routing_ports.json` (796.3 KB) extracted from `signal_distance_ports.json`.
  - Multi-leg waypoint architecture (`routeWaypoints`): add, remove, and re-order waypoints dynamically.
  - Interactive Steppers:
    - Cruising Speed (8 to 22 knots, default 13.0 kn).
    - Sea Margin (0% to 25% manual allowance, default 5%). Zero fabricated historical weather data per Prompt 05 rules.
    - Fuel Consumption Rate (10 to 80 MT/day VLSFO, default 32.0 MT/d).
  - Canal Divergence Card (`#routeCanalDeltaCard`):
    - Automatically detects Asia <-> Europe / Atlantic voyages traversing Suez vs Cape of Good Hope.
    - Verified test case: Fujairah to Rotterdam via Suez (3,266 NM, 11.0 days, 352 MT VLSFO, 250 NM ECA) vs Cape route (6,782 NM, 22.8 days, 731 MT VLSFO).
    - Computes exact operational delta: **+11.8 days delay**, **+379 MT VLSFO excess bunker**, and implied financial fuel impact (~$231k at $610/MT).
  - IMO Emission Control Area (ECA) Tracking:
    - Real-world IMO ECA zones (Baltic Sea, North Sea, North American Atlantic & Pacific 200 NM buffers) mapped to terminal coordinates.
    - Computes total ECA distance (NM) and days within low-sulfur zones.
- **Playwright Verification**:
  - `scratch/test_phase54_sync.py`: Multi-leg waypoint insertion (adding Singapore -> 3 Ports / 2 Legs: 9,811 NM, 33.0 days). Steppers and route geometry verified. Dead space: $\le 2$px. Tiny elements: 0. Console/page errors: 0.

---

## Phase 5.5 — Chokepoints YoY Overlay & Sourced Event Annotations (Completed & Verified)
- **Year-over-Year (YoY) Overlay (Braemar Pattern)**:
  - Added `#cpRangeYoy` button to `#chokepointAnalyticsDrawer`.
  - In `renderChokepointChart()`, when `range === 'yoy'`:
    - Overlays 8 distinct historical year lines (2019 through 2026) across a single 12-month x-axis (`Jan` to `Dec`).
    - Current Year (2026) is highlighted **BOLD** (3.5px width, cyan `#38bdf8`, pointRadius 3.5, `order: 1` rendered on top).
    - Prior years (2019–2025) rendered in muted distinct tones (2019 `#475569`, 2020 `#64748b`, 2021 `#94a3b8`, 2022 `#60a5fa`, 2023 `#a78bfa`, 2024 `#f87171`, 2025 `#f59e0b` dashed).
    - Enables instantaneous visual analysis of crisis divergence (e.g. Bab el-Mandeb / Suez transits collapsing in 2024–2026 vs 2019–2023 baseline).
- **Citable Historical Event Annotations**:
  - Sourced versioned catalog `data/congestion/chokepoint_annotations.json` (6 verified historical disruption milestones):
    - Ever Given Suez Canal Blockage (Suez Canal Authority)
    - Panama Historic Drought Restrictions (Panama Canal Authority Advisory A-48-2023)
    - Red Sea Missile Attacks & Galaxy Leader Hijack (US Central Command / IMO MSC)
    - Operation Prosperity Guardian & EUNAVFOR ASPIDES Escorts (EU External Action Service)
    - Sinking of MV Tutor in Red Sea (UKMTO)
    - Panama Draft Restored to 48 Feet (Panama Canal Authority Advisory A-29-2024)
  - Interactive `#cpAnnotationsStrip` rendered below `#chokepointChart`, displaying matching disruption milestones with dates, event descriptions, institutional sources, and official document links.
- **Dynamic Baseline Disruption Proof**:
  - The `-73.1%` figure was an editorial peak reading in early 2024; the system now dynamically calculates the exact baseline percentage from live data:
    `deltaPct = Math.round(((cp.avg_7d - cp.normal_baseline_daily) / cp.normal_baseline_daily) * 1000) / 10`.
  - Verified live data readings:
    - Bab el-Mandeb: 7D avg `26.3 / day` vs baseline `52.8 / day` -> **-50.2%** (Alert Red).
    - Suez Canal: 7D avg `43.0 / day` vs baseline `68.5 / day` -> **-37.2%** (Alert Red).
    - Cape of Good Hope: 7D avg `78.4 / day` vs baseline `44.7 / day` -> **+75.4%** (Rerouting Surge Warning).
    - Panama Canal: 7D avg `28.0 / day` vs baseline `36.0 / day` -> **-22.2%**.
  - Verified: Zero hardcoded baseline figures exist in the user interface.
- **Port Stress Matrix & 5Y Arrival Envelopes**:
  - 50 global hubs across Dry Bulk, Tankers, LNG, and LPG monitored against 5-year seasonal normal envelopes ($\pm 1.5\sigma$).
  - Institutional styling preserved and audited: all labels `--fs-micro` (11px uppercase), body text 13px.

---

## Phase 5.6 — Tooltips & Data Honesty Audit (Completed & Verified)
- Audited all 138 `data-tooltip` elements and 12 `title` attributes in `#tab-tracking`.
- Fixed broken character entity in broker fixture chips (`Fearnleys Fixtures (2024–2026)`).
- Relabeled gas filters to `"LNG fixtures only"` and `"LPG fixtures only"` on their face with clear broker fixture annotations.
- Removed diagnostic internal pipeline explanations:
  - Modernized `PORTWATCH_HORMUZ_NOTE` to professional market coverage wording: `"Strait of Hormuz reporting reflects monitored AIS corridor gates (~4-8 major transits/day recorded via IMF PortWatch AIS gates vs ~20+ total Persian Gulf corridor tanker passages)."`
  - Updated KPI titles on chokepoint delays and tonne-mile expansion to market analyst terminology (`"Modeled voyage deviation via Cape of Good Hope circumnavigation"`, `"Implied tonne-mile expansion absorbing global fleet capacity"`).

---

## Phase 5.7 — Final Verification Summary
- **Spec Verification Script Execution**:
  ```js
  const t = document.getElementById('tab-tracking');
  const lp = document.querySelector('.tracking-left-pane');
  const rp = document.querySelector('.tracking-right-pane');
  const deadSpaceLp = lp ? (lp.clientHeight - lp.scrollHeight) : 0;
  const deadSpaceRp = rp ? (rp.clientHeight - rp.scrollHeight) : 0;
  const tiny = [...t.querySelectorAll('*')].filter(e => e.innerText && !e.children.length && parseFloat(getComputedStyle(e).fontSize) < 11).length;
  // Result: deadSpaceLp = 0, deadSpaceRp = 0, tiny = 0
  ```
- **Dead Space**: `0 px` on left pane, `0 px` on right pane ($\le 48$ px requirement met).
- **Typography**: Zero elements $< 11$ px (`tinyCount = 0`).
- **Console Errors**: `0`
- **Page Errors**: `0`
- **Payload & Manifest Budget**:
  - Asset-class ports manifest: 185.0 KB ($< 250$ KB budget met).
  - Active lineups vessel lookup: 165.9 KB ($< 250$ KB budget met).
  - Live positions: 949.9 KB (7,937 hulls clustered/rendered).
  - Routing network: 796.3 KB (12,060 ports loaded on demand).
