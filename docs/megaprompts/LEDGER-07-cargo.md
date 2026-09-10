# Phase 7 Ledger: Cargo & Trade Flows Tab (#tab-cargo)

**Prompt**: `docs/megaprompts/07-cargo-trade-flows.md`  
**Status**: COMPLETE  
**Execution Date**: 2026-09-10  
**Tab Position**: Top navigation bar, positioned between **TRACKING** (`#tab-tracking`) and **BUNKERS** (`#tab-bunkers`).  
**Core Workstation Question**: *"What cargo is physically moving, from which origin, in what volume, and is that normal for the time of year?"*

---

## 1. Complete Tab Series Inventory

Every series surfaced on the Cargo & Trade Flows tab is strictly grounded in primary observed data or explicit honest disclosures:

| Series Name | Module | Status | Primary Source | Extraction Method | Span | Unit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Brazil Seaborne Iron Ore** | Flagship & Basins | `LIVE` | MDIC ComexStat (Brazil) | Official REST API | 2024–2026 | Mt/mo |
| **Baltic Capesize C3 Rate** | Flagship Origin $\to$ Freight | `LIVE` | Fearnleys / Baltic Exchange | Continuous Market Benchmark (tsid 10001) | 2024–2026 | USD/MT |
| **Port Hedland Iron Ore** | Flagship & Basins | `LIVE` | Pilbara Ports Authority (WA) | Harbor Master Statistics | 2024–2026 | Mt/mo |
| **Baltic Capesize C5 Rate** | Flagship Origin $\to$ Freight | `LIVE` | Fearnleys / Baltic Exchange | Continuous Market Benchmark (tsid 10002) | 2024–2026 | USD/MT |
| **Newcastle Seaborne Coal** | Flagship & Basins | `LIVE` | Port of Newcastle Operations | Harbor Terminal Tonnage Log | 2018–2026 | Mt/mo |
| **Newcastle/Qingdao Freight Rate** | Flagship Origin $\to$ Freight | `LIVE` | Fearnleys Dry Bulk Desk | Benchmark Market Fixture Rate (tsid 10003) | 2024–2026 | USD/MT |
| **US Gulf Grain Inspections** | Flagship & Logistics | `LIVE` | USDA Agricultural Marketing Service | AMS FGIS Grain Inspection Database | 2025–2026 | MT/wk |
| **Panamax USG-Japan Route Rate** | Flagship Origin $\to$ Freight | `LIVE` | Fearnleys Continuous Rates | Continuous Route tsid 120129 | 2024–2026 | USD/MT |
| **Guinea Bauxite Seaborne Volume** | Flagship & Demand | `LIVE_MIRROR` | China Customs (GACC) via UN Comtrade | Mirror trade statistics (HS 260600) | 2023–2025 | Mt/mo |
| **Conakry Ministry of Mines Direct Series** | Flagship & Demand | `UNAVAILABLE` | Ministry of Mines & Geology, Guinea | Direct customs clearing feed | Offline | N/A |
| **Atlantic Capesize Benchmark Rate** | Flagship Origin $\to$ Freight | `LIVE` | Fearnleys Capesize Desk | Tubarão / Atlantic proxy benchmark (tsid 10001) | 2024–2026 | USD/MT |
| **Fearnleys Fixture Matrix (Classified)**| Commodity Flow Matrix | `LIVE` | Fearnleys Commercial Ledger | 252,889 mapped broker fixtures | 1974–2026 | Fixtures & Mt |
| **Fearnleys Fixture Matrix (Unclassified)**| Commodity Flow Matrix | `EST.` (Audit) | Fearnleys Commercial Ledger | 287,751 unclassified fixtures (53.2% explicit bucket) | 1974–2026 | Fixtures & Mt |
| **Major Miners Quarterly Guidance** | Seasonal Basins | `LIVE` | Vale, Rio Tinto, BHP, FMG Filings | Official corporate financial guidance | 2024–2026 | Mt/quarter |
| **US Crude Seaborne Exports** | Seasonal Basins | `LIVE` | US Energy Information Administration | Weekly Petroleum Status Report (WPSR) | 2020–2026 | kbpd |
| **USDA Outstanding Export Sales** | Grain Logistics | `LIVE` | USDA FAS Export Sales Reporting | 68,181 historical weekly rows (sorted on read) | 1999–2026 | MT |
| **USDA 31-Year Loading Queue History** | Grain Logistics | `LIVE` | USDA AMS Transportation & Marketing | Weekly Grain Transportation Report (GTR) | 1995–2026 | Vessel Count |
| **Australia REQ Export Volume & Forecasts**| Demand & Landed Costs | `LIVE` | Australian Dept of Industry (DISR) | Resources and Energy Quarterly (REQ) | 1990–2026 | Mt/quarter |
| **China Bauxite Landed CIF Unit Cost** | Demand & Landed Costs | `LIVE_MIRROR` | China Customs (GACC) via UN Comtrade | Import value divided by import net weight | 2023–2025 | USD/tonne |

---

## 2. Core Architecture & Components Delivered

### 2.1 SeasonalEnvelope Component
- Standalone reusable visualization grammar built on standard Chart.js v4.
- Features:
  - Shaded 5-year min/max historical envelope band (`rgba(88,166,255,0.12)`).
  - Dashed 5-year historical mean line (`#7a8494`).
  - Bold current year actual line (`#58a6ff` / `#3fb950`).
  - Secondary prior year comparison line (`#8b949e`).
  - Multi-year toggle bar (`2026`, `2025`, `2024`, `5Y Range`, `5Y Mean`).
  - Unit switcher (`Mt` vs `Kt`).
  - Native CSV exporter (`exportSeasonalCSV(chartId)`).
  - Provenance footer indicating primary source, method, update timestamp, and status badge.

### 2.2 Rebuilt 9 Upstream Modules
Relocated from Signals into `#tab-cargo`:
1. **Brazil ComexStat Iron Ore Monthly**: SeasonalEnvelope with MDIC ComexStat API data.
2. **Pilbara Ports Authority Iron Ore**: SeasonalEnvelope with Port Hedland harbor throughput and miners quarterly guidance overlay (Vale, Rio Tinto, BHP, FMG).
3. **Newcastle Seaborne Coal**: SeasonalEnvelope with Port of Newcastle terminal tonnages and vessels loaded counter.
4. **US EIA Crude Seaborne Exports**: Weekly seasonal envelope with WPSR series.
5. **USDA FAS Export Commitments**: Weekly outstanding export sales for 4 grain commodities across global destinations from 68k rows.
6. **USDA Grain Inspections**: Gulf vs Pacific Northwest vs Interior inspection seasonal envelopes.
7. **USDA 31-Year Loading Queues**: Gulf in-port and 10-day due vessel count queues (1995–2026).
8. **Australia REQ Commodity Export Forecasts**: Official quarterly volumes and forecasts across Iron Ore, Metallurgical Coal, Thermal Coal, Bauxite, and Alumina.
9. **China Bauxite Landed CIF Unit Cost**: Mirror price and tonnage history ($/tonne) with UN Comtrade HS 260600.

### 2.3 Flagship Origin $\to$ Freight Pairing Module
- Pairs physical cargo volume directly with its corresponding Baltic spot freight rate on a dual-axis canvas:
  - **Brazil Iron Ore vs Capesize C3** (Tubarão–Qingdao).
  - **Pilbara Iron Ore vs Capesize C5** (Dampier–Qingdao).
  - **Newcastle Coal vs Newcastle/Qingdao** (tsid 10003).
  - **US Gulf Grain vs Panamax USG–Japan** (tsid 120129).
  - **Guinea Bauxite vs Atlantic Capesize Mirror**.
- Zero ton-mile sliders or synthetic distance multipliers: strictly observed volume vs observed freight rates.
- Real-time HUD strip displaying Trade Corridor, Latest Basin Volume, Baltic Spot Rate, and TSID identifier.

### 2.4 Commodity Flow Matrix & 53.2% Unclassified Bucket
- Built by `scripts/cargo/build_commodity_flow_matrix.py` processing all 540,640 Fearnleys fixtures.
- Canonical normalization via `data/reference/commodity_normalisation.json` mapping 74 broker strings and 60 trade regions to Signal Ocean taxonomy.
- **53.2% Unclassified Bucket**:
  - 287,751 fixtures lack a specific commodity descriptor.
  - Rendered as an explicit, high-visibility audit disclosure bucket in both the Hero HUD and the Matrix Table. Never discarded, synthetic, or hidden.
- Signal Ocean Taxonomy Audit Catalog covering 14 nodes across National Customs Series, Mirror Trade Flows, and Data Gaps.

### 2.5 Strict Provenance Discipline & Honest Empty States
- **Guinea Direct Customs Series**: Rendered as an explicit `UNAVAILABLE` empty state card detailing that the Ministry of Mines & Geology / BCRG central bank feeds are offline.
- **UN Comtrade Mirror**: Rendered with an explicit `LIVE_MIRROR` badge disclosing that China Customs import filings are standing in for Conakry exports.
- Zero orphan series: all 99 data paths fetched by `index.html` registered in `data/provenance/manifest.json`.

---

## 3. Verification & Test Results

### 3.1 Playwright End-to-End Suite (`tests/test_cargo_playwright.py`)
- **Tab Activation**: Verified `#tab-cargo` activates and renders without layout thrash.
- **Hero HUD**:
  - Iron Ore: 88.4 Mt/mo (Brazil + Pilbara)
  - USDA Grains: 24.6 Mt
  - Fixture Coverage: 46.8% Classified (252k classified / 287k unclassified bucket)
  - C3-C5 Spread: +$14.20/MT
- **Flagship Route Switching**: Verified all 5 routes switch interactively, updating dual-axis canvas, HUD corridor text, and Guinea empty-state card visibility.
- **Matrix Filtering**: Tested group switching (`All Groups`, `Ores & Minerals`, `Unclassified Bucket`).
- **Subview Workstation Toolbar**: Tested all 6 subview modes (`flagship`, `matrix`, `basins`, `grains`, `demand`, `all`).
- **Visual & Layout Compliance**:
  - **Dead Space**: `0.0px` (strict limit $\le 48$px).
  - **Font Size Audit**: `tinyCount === 0` (zero elements $< 11$px across all rendered DOM nodes).
  - **Console Errors**: `0` (zero browser console errors or uncaught exceptions).
- **Screenshots Generated**:
  - `docs/screenshots/cargo_tab_full.png`
  - `docs/screenshots/cargo_flagship.png`
  - `docs/screenshots/cargo_matrix.png`
  - `docs/screenshots/cargo_basins.png`
  - `docs/screenshots/cargo_grains.png`

### 3.2 Unit & Cache Tests (`tests/test_cargo_frontend.py`)
- `test_commodity_normalisation_reference`: PASSED (schema, taxonomy groups, aliases, region mappings).
- `test_commodity_flow_matrix_structure_and_unclassified_bucket`: PASSED (540,640 fixtures, 53.22% unclassified bucket, coverage catalog).
- `test_cargo_frontend_summary_datasets`: PASSED (all 5 flagship pairs, Brazil, Pilbara, Newcastle, US crude, USDA sales, inspections, queues, REQ, Guinea mirror).

### 3.3 Fabrication & Provenance Check
- `scripts/verify/check_no_fabrication.py`: Zero violations in `scripts/cargo/` (total project violations reduced from 66 to 55).
- `scripts/verify/build_provenance_manifest.py`: Generated `manifest.json` with all cargo endpoints registered (0 orphan series).
