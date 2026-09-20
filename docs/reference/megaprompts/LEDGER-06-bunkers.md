# LEDGER 06 — BUNKERS: FROM STATIC TABLE TO MARINE FUEL WORKSTATION

Execution log for Prompt 06 (docs/megaprompts/06-bunkers.md). Every step recorded as executed and verified.

---

## Initial State & Payload Audit (Before Phase 6.1)
- **Previous Role of #tab-bunkers**:
  - Static 221-row table displaying unstyled twin panes, arbitrary max-height: 660px, and align-items: start.
  - Right pane sat unaligned with 396px of dead card space.
  - Orphaned #carbonEtsContainer and #scrubberCalcWrap sat at the bottom of the workstation grid, breaking grid alignment.
  - 8 non-ports (Brent, EUA, APAC Average, EMEA Average, Americas Average, Global 4 Ports Average, Global 20 Ports Average, Global Average Bunker Price) were mixed into the physical ports table as fake supply ports.
  - Forward curves were displayed as a 12-row numeric table without term structure visualization, M0 spot anchor, or provenance disclosure.
  - Duplicate CSV/JSON files mirrored to repository root on every pipeline run.

---

## Phase 6.1 — Layout & Data Foundation (Completed & Verified)
- **Root Cleanup & Pipeline Fix**:
  - Purged 6 duplicate CSV/JSON files sitting in repository root (bunker_bix_macro_benchmarks.csv/.json, bunker_forward_curves_12m.csv/.json, bunker_physical_sales_volumes.csv/.json).
  - Updated bunker_pipeline/run_pipeline.py to write exclusively to data/bunkers/ and stop mirroring writes to root.
- **Port vs Non-Port Separation**:
  - Analyzed data/bunkers/bunker_master_historical.csv (482,024 authentic rows).
  - Extracted 6 regional/global composite averages into DATA.bunkerSummary.composites:
    - Americas Average, APAC Average, EMEA Average, Global 4 Ports Average, Global 20 Ports Average, Global Average Bunker Price.
  - Extracted 2 macro commodity benchmarks into DATA.bunkerSummary.macro_benchmarks:
    - Brent, EUA.
  - Filtered DATA.bunkerSummary.ports to true physical bunker supply ports: **213 physical ports**.
- **Statistical 3σ Outlier Guard**:
  - Implemented 3σ outlier detection per fuel grade cluster across ports:
    - Civitavecchia (VLSFO .00, z = -4.66; MGO .00, z = -3.34)
    - Maputo (VLSFO ,270.00, z = +3.20)
    - Sekondi (MGO ,995.00, z = +4.70)
    - Skagen (VLSFO .00, z = -3.04)
    - Takoradi (MGO ,995.00, z = +4.70)
    - Tema (MGO ,440.00, z = +3.03)
    - Vancouver (IFO380 .00, z = -3.37)
  - Data preserved honestly; in the UI, outliers are flagged with warning pill and z-score tooltip without suppressing the authentic data.
- **Workstation CSS Grid & Zero Dead Space**:
  - .bunkers-workstation updated to grid-template-columns: minmax(480px, 560px) minmax(0, 1fr); gap: 16px; align-items: stretch;.
  - .bunkers-left-pane set to height: 0; min-height: 100%;.
  - .bunkers-right-pane set to min-height: 0;.
  - .bunkers-table-wrap set to flex: 1; min-height: 0; overflow-y: auto; (removed max-height: 660px;).
  - Moved #carbonEtsContainer and #scrubberCalcWrap inside #bunkersSubviewScrubber.
  - Measured dead space: **0.0px** (<= 48px requirement met).

---

## Phase 6.2 — Forward Curve, Resolved (Completed & Verified)
- **Single-Slope Term Structure Line Chart**:
  - Resolved per Prompt 02 Job C and Prompt 06 §6.2 Branch 2: BunkerIndex models one slope per hub from spot baselines across 12 delivery months.
  - Replaced numeric table with interactive multi-series Chart.js line chart #bunkerForwardChart.
  - Series plotted:
    - VLSFO (0.5% S): #3fb950
    - MGO (0.1% S): #e3b341
    - HSFO (IFO380): #4d9aff
    - Hi-5 Spread: #a371f7 (right axis)
  - **M0 Spot Anchor**: Anchored to contemporaneous physical spot price indication at offset 0 (M0 (Spot)).
  - **Term Structure Badge**: #bunkerFwdStructureBadge displays BACKWARDATION (-22.7%) or CONTANGO (+slope%).
  - **Series Museum Badge**: Explicit provenance labeling: MODELLED · BunkerIndex Single-Slope · As-of 2026-09-05.
  - 13-row contract table below chart detailing M0 through M12 maturities.

---

## Phase 6.3 — Subviews & Port Detail Modal (Completed & Verified)
- **Dedicated Composites Strip (#bunkersCompositesStrip)**:
  - Positioned prominently above the Spot table in #bunkersSubviewSpot.
  - 6 interactive benchmark cards: APAC Avg, Americas Avg, EMEA Avg, Global 20 Ports Avg, Global 4 Ports Avg, Global Avg.
  - Displays VLSFO, MGO, HSFO, and Hi-5 spread. Clicking any card plots its full 3-year historical series in the main chart.
- **Physical Volumes Subview (#bunkersSubviewVolumes)**:
  - Singapore Demand Bellwether Volume Chart (#bunkerVolumesChart):
    - 5-Year Historical Range shaded envelope [Min, Max] MT.
    - 5-Year Historical Average dashed line MT.
    - Latest monthly actuals (2025/2026) prominent line MT.
  - Rotterdam quarterly delivery volume bars via hub selector.
  - 36-period delivery statistics table.
- **Scrubber Economics & EU ETS Terminal (#bunkersSubviewScrubber)**:
  - Top: Scrubber ranking table sorted by Hi-5 spread descending across 110 ports, displaying VLSFO, HSFO, Hi-5, Capesize TCE bonus (+/d), VLCC TCE bonus (+/d), and EU ETS cost.
  - Middle: Merged #carbonEtsContainer with Chart.js line chart for EUA (€/t) vs Singapore Hi-5 spread.
  - Bottom: Interactive Scrubber Payback & Voyage Cost Calculator HUD (#scrubberCalcWrap) with vessel class selectors.
- **Port Detail Modal (#bunkerPortDetailModal)**:
  - Interactive drill-down modal triggered by clicking the info icon on any spot table row or clicking map markers.
  - Header: Port Name, Country, Region, UN/LOCODE, Coordinates, Observation Date.
  - Outlier Warning Banner: Displays exact z-score and deviation when 3σ outlier guard is active.
  - 8 KPI cards: VLSFO, MGO, HSFO, Hi-5 Spread, Spread vs Singapore, Biofuel B24, LNG, MEOH.
  - Multi-Grade Historical Chart: 3-Year Chart.js line chart comparing VLSFO, MGO, HSFO, and Hi-5 spread on dual y-axes.

---

## Phase 6.4 — Tooltips Rewritten to Standard (Completed & Verified)
- Eliminated all pipeline internal code-speak and boilerplate templates.
- Provided institutional domain definitions across all tooltip handlers:
  - **VLSFO**: Very Low Sulphur Fuel Oil (<= 0.50% sulphur cap under IMO 2020 MARPOL Annex VI).
  - **MGO**: Marine Gas Oil (<= 0.10% sulphur distillate required in IMO Emission Control Areas - ECAs).
  - **HSFO**: High Sulphur Fuel Oil (IFO380, <= 3.50% sulphur), permissible only on vessels with exhaust gas cleaning systems (scrubbers).
  - **Hi-5 Spread**: Differential between VLSFO and HSFO ($/MT); primary payback driver for marine scrubber retrofits.
  - **Biofuel (B24)**: Drop-in blend of 24% Used Cooking Oil Methyl Ester (UCOME) biodiesel and 76% VLSFO.
  - **LNG**: Liquefied natural gas cryogenic marine fuel.
  - **MEOH**: Marine methanol fuel.
  - **EUA**: European Union Allowance under EU ETS Maritime (Directive 2023/959).
  - **3σ Outlier Guard**: Transparent explanation of statistical variance against global clusters.
- Every price indication states data source (Ship & Bunker RPC Live Archive / BunkerIndex) and observation window.

---

## Phase 6.5 — Verification & Quality Assurance (Completed)
- **Typography Audit**:
  - tinyCount === 0: Zero elements < 11px across #tab-bunkers (all text >= 11px).
- **Workstation Geometry & Dead Space**:
  - Left Pane: 560 x 846 px
  - Right Pane: 784 x 846 px
  - Dead Space: **0.0px** (<= 48px requirement met).
- **Data Integrity**:
  - Physical ports count: **213 ports** (verified in spot table).
  - Zero non-ports in spot table: confirmed absence of Brent, EUA, and all 6 *Average entries.
- **Automated Tests**:
  - pytest tests/test_bunker_cache_and_frontend.py -v: **10 of 10 tests passed (100%)**.
  - python scratch/test_phase6_playwright.py: **All 11 browser test suites passed**.
  - Console errors: **0**.
  - Page runtime errors: **0**.
