# Cargo & Trade Flows Tab Audit — Final Verification & Walkthrough

This document records the completion, integration, and verification of the comprehensive work order defined in `docs/CARGO_TAB_AUDIT_2026-09-17.md` across all 40 audit items.

---

## 1. Executive Summary & Quality Guarantees

All 40 audit items spanning P0 (Critical/Data Correctness), P1 (High/Display Integrity), P2 (Presentation & Formatting), and Structural Work have been remediated, verified against physical benchmarks, and tested through automated regression suites.

### Core Guarantees Enforced:
1. **Zero Fabrications or Silent Fallbacks**: Every displayed metric traces directly to an official source ledger (`comexstat_brazil`, `ppa_pilbara`, `usda_fas`, `fgis_inspections`, `worldsteel`, `eia`). Tabs with missing series (e.g. USDA Barley & Sorghum FAS commitments) display an explicit empty state (`.cargo-empty-state`) rather than leaving previous datasets on screen.
2. **Official ComexStat API Ground Truth (580-Row Full Series Harvest)**:
   - Scanned all 580 monthly rows (2017-01 to 2026-08 across Corn, Crude Oil, Iron Ore, Raw Sugar, Soybeans) against the live MDIC ComexStat REST API (`api-comexstat.mdic.gov.br/general`).
   - Exact source values verified and locked:
     - **Crude Oil 2022-02** (NCM 27090010): **6,474,032.61 t** (FOB $3,938,875,347.00).
     - **Raw Sugar 2023-02** (NCM 17011300+17011400): **885,612.72 t** (FOB $385,784,771.00).
     - **Iron Ore 2017-03** (NCM 26011100): **33,177,280.55 t** (FOB $2,051,418,773.00).
     - **Corn 2017-09** (NCM 10059010): **5,913,703.18 t** (FOB $915,336,070.00).
   - In-row method stores exact monthly request payload and response timestamp (`response_date=2026-09-18`).
   - Trailing 12-month median outlier validation: 30 seasonal drops (safrinha corn and entre-safra soybeans) justified; 0 unjustified breaches.
   - Reconciled provenance: CSV and UI cards match on `MDIC SECEX ComexStat Official API`.
3. **Strict Physical Unit Conversions**: Removed all heuristics (`val > 50_000`, `> 1000`, `> 10000`). All builders convert raw kilograms strictly via `kg / 1000.0`. Brazil January soybean envelope maximum is corrected from **49.5 Mt down to 2.85 Mt**.
4. **Deterministic Locale Formatting**: Zero bare `.toLocaleString()` calls exist in `index.html`. All 27 formatting calls now use explicit `'en-US'` locale, guaranteeing standard Western groupings (`18,749,824`) and eliminating Indian numbering system formatting (`1,87,49,824`).
5. **Authentic Vessel & Corridor Matrix with Partial Sample Labeling**:
   - Total fixtures in universe: **547,044** (reconciled data resync from cron ingestion of Fearnleys fixture ledger).
   - Free-text charter cargo quantities parsed with explicit units (`MT`, `KT`, `CBM`, `BBLS`) across **27,305 fixtures** (**4.99% ~ 5.0% partial sample coverage**).
   - The matrix table header explicitly marks the column as `Reported Volume (Mt, ~5.0% Sample)`, and every volume row displays its exact commodity-level parsed sample share (e.g. `17.6% sample`). Fixtures lacking explicit tonnage are never assumed to be zero and do not contribute to volume totals.
   - Built a 624-port gazetteer in `data/reference/commodity_normalisation.json`; corridor mapped share reached **67.98%** (exceeding >60% target).
   - Multi-field classification reduced unclassified fixtures to **24.61%** (achieving <25% target) with an explicit unclassified bucket.
   - Vessel classes derived directly from ledger `segment` and DWT with realistic physical cargo bands (Capesize 120–220 kt, Panamax 55–90 kt).
6. **Hero HUD Like-for-Like Rebuild**:
   - **Pilbara Iron Ore Run-Rate**: 59.4 Mt/mo (Hedland iron ore 46.6 Mt + Dampier iron ore 12.8 Mt, eliminating the previous conflation of total Dampier throughput).
   - **USDA Grain Commitments**: 37.2 Mt outstanding commitments (volume in Mt instead of row counts).
   - **Fixture Coverage**: 412k classified fixtures (75.4% classified), 547k fixtures total.
   - **Freight Spread**: C3-C5 spread +$24.10/MT.

---

## 2. Fixture Count Lineage & Confirmation (546,131 -> 547,044)

The fixture count change from **546,131** to **547,044** is an **authentic data resync**, not an anomaly or calculation error.

### Evidence & Provenance:
1. `data/derived/fearnleys_fixtures_full.csv` is maintained and updated by automated scheduled cron jobs.
2. Commits on `main`:
   - `c3a132024` (2026-09-17 20:26 UTC): `data(broker-voice): sync Fearnleys comments/reports`
   - `cd224362e` (2026-09-18 00:01 UTC): `Update indices, flows, and bunkers`
3. Ingestion added 913 new commercial fixtures dated up through `2026-09-17`.
4. Row count in `fearnleys_fixtures_full.csv` grew from 546,132 lines (546,131 data rows) to 547,045 lines (547,044 data rows).
5. All downstream matrix aggregations (`scripts/cargo/build_commodity_flow_matrix.py`) and UI badges in `index.html` were recomputed and aligned with this updated authoritative dataset.

---

## 3. Automated Test Verification Results

### Pytest Full Suite (36 / 36 PASSED - 100%)
Ran `pytest tests/test_cargo_audit_fixes.py tests/test_cargo_frontend.py tests/test_cargo_truth.py -v`:
- `tests/test_cargo_audit_fixes.py`: **29/29 PASSED**
  - January Soybean envelope max <= 5.0 Mt (actual: 2.85 Mt).
  - Crude Oil 2022-02 = 6,474,032.61 MT, Raw Sugar 2023-02 = 885,612.72 MT (ComexStat source ground truth).
  - Envelope `min <= mean <= max` ordering.
  - Zero unit guess heuristics in builders (`val > 50_000`).
  - Zero blank `source` or `method` in `brazil_comexstat_exports.csv`.
  - Monthly trailing 12-month median outlier validator passed with exit code 0.
  - Fixture quantity regex parsing, coverage thresholds, segment-derived vessel classes, and cargo size sanity bands.
  - Mapped corridor coverage > 60% (actual: 67.98%).
  - Unclassified fixtures < 25% (actual: 24.61%).
  - Zero bare `.toLocaleString()` in `index.html`.
  - Dynamic provenance registry across 17 datasets in `cargo_cache.json`.
  - Extended historical series verified (Hedland 2015+, Dampier 2002+, Guinea 2017+, China 2018+, EIA 1991+).
  - Empty states, toggle isolation, spread fallbacks, and HUD calculations.
- `tests/test_cargo_frontend.py`: **3/3 PASSED**
- `tests/test_cargo_truth.py`: **4/4 PASSED**

### Playwright End-to-End Test (100% PASSED)
Ran `python tests/test_cargo_playwright.py`:
- **DOM Typography Font Floor (>= 11px)**: `tinyCount === 0`.
- **Trailing Dead Space**: `0.0px` (strict limit: <= 48px).
- **Browser Console Errors**: `0`.
- **Page Uncaught Exceptions**: `0`.
- **Flagship Route Switching**: 5 routes toggled smoothly with correct status badges (including Guinea `MIRROR STATISTIC`).
- **Workstation Subviews**: All 6 views (`#cargoSubFlagshipBtn`, `#cargoSubMatrixBtn`, `#cargoSubBasinsBtn`, `#cargoSubGrainsBtn`, `#cargoSubDemandBtn`, `#cargoSubAllBtn`) verified.

---

## 4. Visual Verification & Screenshots

### A. Five Macro Workstation Captures

#### 1. Full Cargo & Trade Flows Tab
The complete tab layout with Hero HUD, Flagship Corridor, and subview navigation:

![Full Cargo & Trade Flows Tab](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/cargo_tab_full.png)

#### 2. Flagship Route & Quality Strip
Brazil Tubarão → Qingdao C3 corridor with dynamic provenance footer and clamped Capesize spot chart:

![Flagship Corridor View](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/cargo_flagship.png)

#### 3. Commodity Flow Matrix & Classification Bucket
Classified fixtures with parsed quantity coverage badge (`Parsed Qty Coverage: 27,305 fixtures (5.0% sample)`), explicit `Reported Volume (Mt, ~5.0% Sample)` column, and explicit unclassified bucket:

![Commodity Flow Matrix](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/cargo_matrix.png)

#### 4. Basins & Miner Throughput
Port Hedland / Dampier toggle isolation, 24-year historical depth, and global iron ore miners breakdown:

![Basins and Miners](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/cargo_basins.png)

#### 5. Grains & Landed Cost Competitiveness
Argentine port basin breakdown (Up-River Paraná vs Ocean Deepwater), USDA commitments by destination, and landed cost spread:

![Grains and Landed Cost](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/cargo_grains.png)

---

### B. Eight Focused Captures of Remediated Display Defect Cards

#### 1 & 2. USDA Commitments Tab — Barley & Sorghum Empty States
When commodities lack FAS weekly export sales series, the chart safely destroys previous canvases and renders an explicit empty state rather than leaving stale datasets on screen:

````carousel
![USDA Barley Empty State](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_usda_barley_empty.png)
<!-- slide -->
![USDA Sorghum Empty State](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_usda_sorghum_empty.png)
````

#### 3. Port of Dampier Toggle Isolation
Selecting Port of Dampier renders the authentic Dampier historical series without bleeding into Port Hedland badges or envelopes:

![Port of Dampier Toggle](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_dampier_toggle.png)

#### 4. Port Hedland Destination Panel Header
Header and badge dynamically read `August 2026` / `LIVE AUGUST 2026` from `latest_destinations.date`, eliminating hardcoded July 2026 strings:

![Port Hedland Destination Panel Header](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_hedland_destination_header.png)

#### 5. Major Miners Chart
Retitled to `Major Global Iron Ore Miners & Pilbara Ports Throughput` to accurately reflect the inclusion of Vale alongside Rio Tinto, BHP, and FMG, with hatched styling for prior estimates:

![Major Miners Chart](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_major_miners.png)

#### 6. Gulf–PNW Freight Spread Badge & Chart
Calculates spread dynamically (`gulfToJapan - pnwToJapan`), displays active badge (`+$28.25/MT`), renders the yellow spread curve, and avoids `+$0/MT` fallback:

![Gulf-PNW Freight Spread](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_gulf_pnw_spread.png)

#### 7. Minor-Bulk Multiples Grid
Responsive multiples cards displaying authentic 5-year envelopes and seasonality for minor bulk commodities:

![Minor-Bulk Multiples Grid](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_minor_bulks.png)

#### 8. Brazilian Bulk Seaborne Exports (Seasonal Envelopes)
Displays verified ComexStat API primary export data with seasonal envelope corridors across Iron Ore, Crude Oil, Soybeans, and Raw Sugar:

![Brazil Seasonal Exports Card](file:///C:/Users/Dell/.gemini/antigravity/brain/b43c34cd-0857-475d-92ff-5a9e0356f6bc/card_brazil_seasonal.png)

---

## 5. Summary of Commits & File Verification

All files are verified, tested, committed to `main`, and pushed to remote.
- Full automated test suite: **100% PASSED** (Pytest & Playwright).
- Console errors: **0**.
- Visual anomalies / dead space: **0**.
