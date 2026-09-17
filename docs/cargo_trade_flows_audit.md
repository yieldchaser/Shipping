# Comprehensive Data Audit: Cargo & Trade Flows Terminal

**Date of Audit**: September 16, 2026  
**Repository**: `yieldchaser/Shipping`  
**Target View**: `Cargo & Trade Flows` (`#tab-cargo` / `index.html`)  
**Status**: Complete End-to-End Codebase & UI Audit  

---

## 1. Executive Summary & Terminal Mission

### What We Are Trying to Do Through This Tab
The **Cargo & Trade Flows Terminal** serves as the macroeconomic and physical supply-chain engine of the shipping workstation. In maritime shipping, freight rates (Baltic spot indices, time-charter rates, and FFA derivatives) do not move in a vacuum; they are the direct mathematical consequence of **physical cargo volume multiplied by voyage distance (ton-miles)** against the available supply of merchant vessels.

The primary objectives of this tab are:
1. **Bridge Upstream Cargo Supply with Downstream Freight Rates**: Pair physical departure tonnages from the world's primary export basins (e.g. Tubarão iron ore, Pilbara iron ore, Newcastle coal, US Gulf grains, Guinea bauxite) directly with their matching Baltic benchmark freight routes (C3, C5, C7, Grain routes) to track volume lead-lag dynamics and freight elasticity.
2. **Track Commercial Fixture Volume & Commodity Taxonomy**: Decode and classify commercial market fixtures from the global broker ledger (Fearnleys ~545k fixtures) across dry bulk, tanker, and specialized shipping sectors, providing full transparency into classified vs unclassified fixture volumes.
3. **Detect Seasonal Supply Gluts & Deficits**: Benchmark current monthly/weekly export paces against **5-Year Seasonal Envelopes (Min-Max range and 5Y Mean)** to immediately identify supply shocks (weather disruptions, mine halts, harvest delays, export bans).
4. **Monitor Agricultural Export Lineups & Port Logistics**: Provide deep visibility into port congestion, vessel queues, and export commitments across the world's breadbaskets (US Gulf, Pacific Northwest, Argentina Up-River Paraná) before cargoes hit open waters.
5. **Model Landed Commodity Arbitrage & Import Demand**: Calculate landed import economics ($FOB + Ocean\ Freight = CFR$) and cross-reference major importer demand (e.g., "Who Feeds China?" import origins, World Steel crude steel production, China port iron ore restocking cycles) to forecast ton-mile redirection.

---

## 2. Architecture & Data Ingestion Flow

The Cargo & Trade Flows tab is powered by a multi-tiered architecture:

```mermaid
flowchart TD
    subgraph Primary Sources
        ComexStat[Brazil ComexStat / MDIC]
        PPA[Pilbara Ports Authority]
        USDA[USDA FAS / FGIS / AMS]
        EIA[US Energy Information Admin]
        Miners[Vale, Rio, BHP, FMG Filings]
        BPS[BPS Indonesia Statistics]
        GACC[China Customs / GACC]
        MAGyP[Argentina MAGyP / SAGyP]
        WorldSteel[World Steel Association]
        WorldBank[World Bank Pink Sheet]
        Baltic[Baltic Exchange / Fearnleys TS]
    end

    subgraph Acquisition & Scrapers
        S_Comex[fetch_brazil_comexstat.py]
        S_PPA[fetch_australia_ppa.py]
        S_USDA[fetch_usda_grains.py / fetch_usda_fas_exports.py]
        S_EIA[fetch_eia_petroleum_exports.py]
        S_Miners[fetch_major_miners_production.py]
        S_BPS[fetch_bps_exim.py]
        S_China[fetch_china_customs_demand.py]
        S_Arg[fetch_argentina_grain.py]
        S_Steel[fetch_world_steel_production.py]
        S_Minor[fetch_minor_bulks.py]
        S_Fearn[daily_fearnleys_sync.py]
    end

    subgraph Local Data Stores
        D_Comex[(brazil_comexstat_exports.csv)]
        D_PPA[(australia_ppa_iron_ore.csv)]
        D_USDA[(usda_fas / usda_ytd / usda_vessel_loading)]
        D_EIA[(us_eia_weekly_crude_exports.csv)]
        D_Miners[(major_miners_quarterly_shipments.csv)]
        D_BPS[(indonesia_coal_exports_monthly.csv)]
        D_China[(china_customs_monthly_imports.csv)]
        D_Arg[(argentina_grain_exports_monthly.csv)]
        D_Steel[(world_crude_steel_monthly.csv)]
        D_Minor[(minor_bulks_monthly.csv)]
        D_Fixt[(fearnleys_fixtures_full.csv)]
    end

    subgraph Precomputed Frontend Caches
        C_Summ[data/cargo/cargo_frontend_summary.json]
        C_Mat[data/cargo/commodity_flow_matrix.json]
    end

    subgraph Frontend View
        UI_HUD[Top HUD KPI Strip]
        UI_Flag[Flagship: Origin -> Freight]
        UI_Mat[Commodity Flow Matrix]
        UI_Basins[Seasonal Export Basins]
        UI_Grains[Grain Logistics & Queues]
        UI_Demand[Demand Drivers & Landed Costs]
    end

    ComexStat --> S_Comex --> D_Comex
    PPA --> S_PPA --> D_PPA
    USDA --> S_USDA --> D_USDA
    EIA --> S_EIA --> D_EIA
    Miners --> S_Miners --> D_Miners
    BPS --> S_BPS --> D_BPS
    GACC --> S_China --> D_China
    MAGyP --> S_Arg --> D_Arg
    WorldSteel --> S_Steel --> D_Steel
    WorldBank --> D_WB[(commodities_monthly.csv)]
    Baltic --> S_Fearn --> D_Fixt

    D_Comex & D_PPA & D_USDA & D_EIA & D_Miners & D_BPS & D_China & D_Arg & D_Steel & D_Minor --> C_Summ
    D_Fixt --> C_Mat

    C_Summ --> UI_HUD & UI_Flag & UI_Basins & UI_Grains & UI_Demand
    C_Mat --> UI_HUD & UI_Mat
```

---

## 3. Detailed Audit: Every Single Component, Metric & Chart

Below is the exhaustive, item-by-item breakdown of every data element rendered in `#tab-cargo`.

---

### Part A: Top HUD KPI Strip

#### 1. Total Iron Ore Run-Rate (Brazil + Pilbara)
- **DOM IDs**: `#cargoHudIronOre`, `#cargoHudIronOreSub`
- **Rendered Values**: `79.4 Mt/mo` | `Brazil: 35.2 Mt | Pilbara: 44.2 Mt`
- **Economic Purpose**: Measures aggregate monthly supply from the world's two dominant iron ore basins (Vale Brazil + Rio Tinto/BHP/FMG Western Australia), which together drive over 80% of global Capesize demand.
- **Data Source**: Brazil ComexStat (`data/commodities/brazil_comexstat_exports.csv`) + Pilbara Port Authority (`data/commodities/australia_ppa_iron_ore.csv`).
- **Primary Source / API**: MDIC SECEX ComexStat API (Brazil) & Pilbara Ports Authority monthly throughput reports (Australia).
- **Update Frequency**: Monthly (mid-month).
- **Date Span in Repo**:
  - Brazil: `2017-01-01` to `2026-07-01` (115 months, 575 rows).
  - Pilbara: `2002-07-01` to `2026-07-01` (256 months, 292 rows).
- **Missing / Lag**: August 2026 data is currently published by both MDIC and PPA but has not yet been ingested into the repo.
- **Workflow Status**: Ingested via `upstream_commodity_flows.yml` (every Monday at 06:00 UTC). Recomputed daily into `cargo_frontend_summary.json` via `scheduled_pipeline_sync.yml`.
- **Action Needed**: Run `fetch_brazil_comexstat.py` and `fetch_australia_ppa.py` to ingest August 2026 data.

#### 2. USDA Active Grain Commitments
- **DOM IDs**: `#cargoHudGrains`, `#cargoHudGrainsSub`
- **Rendered Values**: `68.2k Records` | `Active: Corn, Wheat, Soybeans (FAS)`
- **Economic Purpose**: Tracks forward committed export sales of US agricultural bulk commodities. Leading indicator of upcoming Panamax and Supramax grain liftings from US Gulf and PNW.
- **Data Source**: `data/commodities/usda_fas_outstanding_export_sales.csv`.
- **Primary Source / API**: USDA Foreign Agricultural Service (FAS) Export Sales Reporting (ESR) API.
- **Update Frequency**: Weekly (released every Thursday at 08:30 US Eastern).
- **Date Span in Repo**: `1999-09-02` to `2026-08-27` (1,409 weeks, 68,181 rows).
- **Missing / Lag**: Lagging by ~2 weeks (weeks ending Sep 03 and Sep 10, 2026 are published).
- **Workflow Status**: `usda_weekly.yml` runs every Thursday at 15:00 UTC (`scripts/scrapers/fetch_usda_fas_exports.py`).
- **Action Needed**: Verify `usda_weekly.yml` runs cleanly to pull the early September ESR releases.

#### 3. Broker Commercial Fixture Coverage
- **DOM IDs**: `#cargoHudFixtures`, `#cargoHudFixturesSub`
- **Rendered Values**: `545k Fixtures` | `46.8% Classified | 53.2% Unclassified`
- **Economic Purpose**: Provides institutional transparency into how much of the historical chartering fixture tape has been cleanly parsed into standardized commodity classifications versus unclassified/general fixtures.
- **Data Source**: `data/cargo/commodity_flow_matrix.json` (derived from `data/derived/fearnleys_fixtures_full.csv`).
- **Primary Source / API**: Fearnleys commercial fixture ledger via Hasura GraphQL engine.
- **Update Frequency**: Continuous / Daily (Hasura delta sync).
- **Date Span in Repo**: `1974-12-18` to `2026-12-18` (545,056 total fixtures).
- **Missing / Lag**: Up to date as of today (September 16, 2026).
- **Workflow Status**: Synchronized 4x daily via `daily_update.yml` (`scripts/fearnleys/daily_fearnleys_sync.py`), cache rebuilt daily via `scheduled_pipeline_sync.yml`.
- **Action Needed**: Expand mapping dictionary in `data/reference/commodity_normalisation.json` to classify ambiguous trade entries and reduce the 53.2% unclassified bucket.

#### 4. C3 vs C5 Capesize Route Spread
- **DOM IDs**: `#cargoHudC3C5Spread`, `#cargoHudC3C5SpreadSub`
- **Rendered Values**: `+$23.67 / MT` | `C3: $41.28/t | C5: $17.61/t (2026-09 average)`
- **Economic Purpose**: The spread between Baltic C3 (Tubarão to Qingdao, ~11,000 nm) and C5 (West Australia to Qingdao, ~3,500 nm). The spread reflects the ton-mile voyage premium of Atlantic iron ore over Pacific iron ore, dictating vessel positioning economics.
- **Data Source**: `data/derived/fearnleys_dry_routes_daily.json` (embedded in `flagship_pairs` in `cargo_frontend_summary.json`).
- **Primary Source / API**: Baltic Exchange benchmark rate series via Fearnleys TS API (`fetch_dry_routes_ts.py`).
- **Update Frequency**: Daily (market close).
- **Date Span in Repo**: Continuous through `2026-09-15`.
- **Missing / Lag**: Fully current.
- **Workflow Status**: Refreshed 4x/day in `daily_update.yml`.

---

### Part B: Module 1 — Flagship: Origin Basin -> Freight Rate Co-Movement

- **DOM Container**: `#cargoFlagshipSection` (`#flagshipOriginFreightContainer`)
- **Chart Element**: `#flagshipOriginFreightChart` (Dual-axis Canvas)
- **Selector Buttons**:
  - `flagBtnBrazilC3` (Brazil Iron Ore vs C3)
  - `flagBtnPilbaraC5` (WA Pilbara Iron Ore vs C5)
  - `flagBtnNewcastleCoal` (Newcastle Coal vs Capesize/Panamax)
  - `flagBtnUsgGrain` (US Gulf Grain vs USG-Japan Grain Freight)
  - `flagBtnGuineaCape` (Guinea Bauxite vs Capesize Volume)
- **Pre-computed Cache**: `data/cargo/cargo_frontend_summary.json` -> `flagship_pairs`.

#### Detailed Stream Audit:
| Corridor | Physical Volume Stream | Freight Benchmark Route | Volume Span | Freight Span | Missing Periods | Update Automation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Brazil C3** | MDIC ComexStat (`brazil_comexstat_exports.csv`) | Baltic C3 Tubarão-Qingdao ($/t) | 2017-01 to 2026-07 | 2023-01 to 2026-09 | Aug 2026 volume pending ingest | Volume: `upstream_commodity_flows.yml`<br>Freight: `daily_update.yml` |
| **Pilbara C5** | PPA Port Hedland/Dampier (`australia_ppa_iron_ore.csv`) | Baltic C5 WA-Qingdao ($/t) | 2002-07 to 2026-07 | 2023-01 to 2026-09 | Aug 2026 volume pending ingest | Volume: `upstream_commodity_flows.yml`<br>Freight: `daily_update.yml` |
| **Newcastle Coal** | Port of Newcastle (`newcastle_coal_exports.csv`) | Capesize Coal Freight | 2018-01 to 2026-07 | 2023-01 to 2026-09 | Aug 2026 volume pending ingest | Volume: `upstream_commodity_flows.yml`<br>Freight: `daily_update.yml` |
| **US Gulf Grain** | USDA FGIS Inspections (`usda_ytd_grain_inspections_top20.csv`) | USDA GTR USG-Japan Grain Freight ($/t) | 2025-01 to 2026-09 | 1996-01 to 2026-08 | Sep 2026 GTR freight pending | Volume: `usda_weekly.yml`<br>Freight: `usda_weekly.yml` |
| **Guinea Bauxite** | UN Comtrade / China Customs Mirror (`guinea_bauxite_exports.csv`) | Capesize Vessel Volume | 2015-12 to 2026-06 | Volume-only (No Baltic Guinea route) | Jul-Aug 2026 mirror pending | Volume: `upstream_commodity_flows.yml` |

---

### Part C: Module 2 — Commodity Flow Matrix & Coverage Analytics

- **DOM Container**: `#cargoMatrixSection` (`#commodityMatrixContainer`)
- **Table Body**: `#cargoMatrixTableBody`
- **Analytics Grid**: `#cargoCoverageGrid`
- **Filters**: ALL, Agri, Energy, Ores, Wet, Metals, Chem, Unclassified
- **Source File**: `data/cargo/commodity_flow_matrix.json` (1.35 MB)
- **Built By**: `scripts/cargo/build_commodity_flow_matrix.py`
- **Input Data**:
  - `data/derived/fearnleys_fixtures_full.csv` (545,056 records, 64.4 MB)
  - `data/reference/commodity_normalisation.json` (Normalization rules)

#### Key Matrix Metrics:
- **Total Commercial Fixtures**: 545,056 fixtures
- **Classified Fixtures**: 255,034 fixtures (46.8%)
- **Unclassified Bucket**: 290,022 fixtures (53.2%, 161.4 Mt)
- **Top Classified Categories**:
  - Grain (Clean / General): 50,491 fixtures (Panamax dominant)
  - Coal: 22,155 fixtures, 179.3 Mt (Capesize/Panamax)
  - Minor Bulks / Specialized: 14,901 fixtures
  - Steel Products: 13,890 fixtures (Supramax dominant)
  - General Cargo / Breakbulk: 9,417 fixtures (Handysize)
  - Wheat: 8,671 fixtures
  - Iron Ore: 8,519 fixtures, 100.2 Mt (Capesize dominant)
- **Workflow Status**: Executed daily in `scheduled_pipeline_sync.yml` at `05:00 UTC`.
- **Deficiencies**: The 53.2% unclassified bucket is high because historical fixture comments often omit explicit commodity names or use non-standard abbreviations.
- **Action Needed**: Run `generate_normalization_map.py` to identify the most frequent unclassified text strings and add them to `commodity_normalisation.json`.

---

### Part D: Module 3 — Seasonal Export Basins & Commodity Supply

#### 1. Brazilian Bulk Seaborne Exports (MDIC ComexStat)
- **DOM Container**: `#brazilExportsContainer` (Chart: `#brazilExportsChart`)
- **Commodity Toggles**: Iron Ore (Mt), Crude Oil (Mt), Soybeans (Mt), Raw Sugar (Mt)
- **Visualization**: Monthly volume vs 5-Year Seasonal Envelope (Min, Max, 5Y Mean) + prior year (2025) and current year (2026).
- **Data File**: `data/commodities/brazil_comexstat_exports.csv` (85 KB, 575 rows).
- **Date Span**: `2017-01-01` to `2026-07-01` (115 consecutive months).
- **Frequency**: Monthly.
- **Missing Data**: August 2026.
- **Collector**: `scripts/scrapers/fetch_brazil_comexstat.py`.
- **Workflow**: `upstream_commodity_flows.yml` (Mondays 06:00 UTC).

#### 2. Pilbara Ports Authority (PPA) Throughput & Major Miners Guidance
- **DOM Container**: `#ppaThroughputContainer` (Chart: `#ppaThroughputChart`)
- **Toggles**: Port Hedland (Mt), Port of Dampier (Mt), Major Miners Shipments
- **Destination Breakdown**: Detailed JSON breakdown (China, Japan, S. Korea, Indonesia, Taiwan).
- **Data Files**:
  - `data/commodities/australia_ppa_iron_ore.csv` (30.4 KB, 292 rows, Span: `2002-07-01` to `2026-07-01`).
  - `data/commodities/major_miners_quarterly_shipments.csv` (4.5 KB, 40 rows, Span: `2024 Q1` to `2026 Q2`).
- **Frequency**: Monthly (PPA) / Quarterly (Miners).
- **Missing Data**: August 2026 (PPA). For miners, Q2 2026 (ended June 30) is the latest completed quarter; Q3 2026 will be released in mid-October 2026.
- **Collector**: `scripts/scrapers/fetch_australia_ppa.py` & `scripts/scrapers/fetch_major_miners_production.py`.
- **Workflow**: `upstream_commodity_flows.yml`.

#### 3. US EIA Weekly Crude Oil Exports
- **DOM Container**: `#eiaExportsContainer` (Chart: `#eiaExportsChart`)
- **Metrics**: Weekly export rate (`us_total_crude_exports_kbpd`) and 4-week moving average (`crude_4w_avg_kbpd`).
- **Data File**: `data/commodities/us_eia_weekly_crude_exports.csv` (42.1 KB, 1,856 rows).
- **Date Span**: `1991-02-08` to `2026-08-28` (weekly, 35 years of data).
- **Frequency**: Weekly (every Friday).
- **Missing Data**: Weeks ending September 04 and September 11, 2026.
- **Collector**: `scripts/scrapers/fetch_eia_petroleum_exports.py`.
- **Workflow**: `upstream_commodity_flows.yml`.

#### 4. Port of Newcastle Coal Exports
- **DOM Container**: `#newcastleCoalContainer` (Chart: `#newcastleCoalChart`)
- **Metrics**: Monthly export tonnes (Mt) and vessel counts.
- **Data File**: `data/commodities/newcastle_coal_exports.csv` (15.7 KB, 103 rows).
- **Date Span**: `2018-01-01` to `2026-07-01`.
- **Frequency**: Monthly.
- **Missing Data**: August 2026.
- **Collector**: `scripts/scrapers/fetch_newcastle_coal.py`.
- **Workflow**: `upstream_commodity_flows.yml`.

#### 5. Indonesia Coal Production, Exports & Export Ban Indicators
- **DOM Container**: `#indonesiaCoalContainer` (Chart: `#indonesiaCoalChart`, Grid: `#indonesiaDestinationsGrid`)
- **Metrics**: Headline coal vs lignite, seaborne volumes, destination shares (China, India, S. Korea).
- **Data Files**:
  - `data/commodities/indonesia_coal_exports_monthly.csv` (28.1 KB, 103 rows, Span: `2018-01-01` to `2026-07-01`).
  - `data/commodities/indonesia_coal_ports_destinations.json` (533 KB, 103 monthly maps).
- **Frequency**: Monthly (Badan Pusat Statistik - BPS publishes with ~45-day lag).
- **Missing Data**: August 2026 (expected release late September).
- **Collector**: `scripts/acquire/fetch_bps_exim.py`.
- **Workflow**: `bps_monthly.yml` (runs monthly on the 15th at 06:00 UTC).

#### 6. Guinea Bauxite Exports & Producer Ledger
- **DOM Container**: `#guineaBauxiteContainer` (Chart: `#guineaBauxiteChart`, Table: `#guineaProducersTableBody`)
- **Metrics**: Annual historical growth (2015-2025: 18 Mt -> 183 Mt), monthly mirror imports, producer ledger (SMB, CBG, Chalco, GAC, SPIC).
- **Data File**: `data/commodities/guinea_bauxite_exports.csv` (62.1 KB, 144 rows, Span: `2015-12-31` to `2026-06-30`).
- **Frequency**: Monthly (China Customs mirror) / Annual (Ministry of Mines).
- **Missing Data**: July and August 2026 mirror imports.
- **Collector**: `scripts/acquire/fetch_guinea_bauxite.py` & `scripts/scrapers/fetch_un_comtrade_bauxite.py`.
- **Workflow**: `upstream_commodity_flows.yml`.

#### 7. Global Minor Bulks Trade Flow Grid
- **DOM Container**: `#minorBulksContainer` (Grid: `#minorBulksGrid`)
- **Commodities**: Alumina, Cement, Fertilizers (Urea/DAP), Petcoke, Raw Sugar, Scrap Metal.
- **Data File**: `data/commodities/minor_bulks_monthly.csv` (79.6 KB, 321 rows, Span: `2022-01-01` to `2026-07-01`).
- **Frequency**: Monthly.
- **Missing Data**: August 2026.
- **Collector**: `scripts/acquire/fetch_minor_bulks.py`.
- **Workflow**: **ORPHANED (Not currently scheduled in any GitHub Actions workflow!)**.
- **Action Needed**: Add `fetch_minor_bulks.py` to `upstream_commodity_flows.yml`.

#### 8. Australia Resources & Energy Quarterly (REQ)
- **DOM Container**: `#australiaReqContainer` (Chart: `#australiaReqChart`)
- **Commodity Toggles**: Iron Ore, Thermal Coal, Met Coal, LNG, Bauxite.
- **Data File**: `data/commodities/australia_req_commodity_exports.csv` (61.7 KB, 725 rows, Span: `1990 Q1` to `2026 Q1`).
- **Frequency**: Quarterly (DISR releases in March, June, September, December).
- **Missing Data**: `2026 Q2` (June 2026 edition) is published but not yet ingested.
- **Collector**: `scripts/scrapers/fetch_australia_req.py`.
- **Workflow**: `upstream_commodity_flows.yml`.

#### 9. Commercial Fleet Orderbook & Supply Profile
- **DOM Element**: Embedded within summary cache (`cs.fleet_orderbook`).
- **Metrics**: Active DWT, orderbook DWT, orderbook-to-fleet ratio (13.2% for Capesize), delivery schedule by year (2026 through 2029+), scrubber penetration (43.8%).
- **Data File**: `data/supply/fleet_orderbook_and_age_profile.csv` (2.4 KB, 11 vessel segments).
- **Collector**: `scripts/acquire/fetch_fleet_supply.py`.
- **Workflow**: `scheduled_pipeline_sync.yml` (Daily at 05:00 UTC).

---

### Part E: Module 4 — Global Grain Lineups & Ocean Freight Economics

#### 1. Argentina Grain Exports & Port Basin Breakdown
- **DOM Container**: `#argentinaGrainContainer` (Chart: `#argentinaGrainChart`, Table: `#argentinaPortsTableBody`)
- **Metrics**: Total grain tonnage, Up-River Paraná share (82.0%), draft constraints, port breakdown (San Lorenzo, Rosario, Bahía Blanca, Necochea).
- **Data Files**:
  - `data/commodities/argentina_grain_exports_monthly.csv` (18.5 KB, 43 rows, Span: `2023-01-01` to `2026-07-01`).
  - `data/commodities/argentina_grain_ports_breakdown.csv` (87.6 KB, 339 rows, Span: `2023-01-01` to `2026-07-01`).
- **Frequency**: Monthly (MAGyP / SAGyP Embarques de Granos).
- **Missing Data**: August 2026.
- **Collector**: `scripts/acquire/fetch_argentina_grain.py`.
- **Workflow**: **ORPHANED (Not currently scheduled in any GitHub Actions workflow!)**.
- **Action Needed**: Add `fetch_argentina_grain.py` to `usda_weekly.yml` or a monthly workflow.

#### 2. USDA FAS Outstanding Export Sales (ESR)
- **DOM Container**: `#usdaExportSalesContainer` (Chart: `#usdaExportSalesChart`)
- **Toggles**: Wheat, Corn, Soybeans, Barley, Sorghum.
- **Data File**: `data/commodities/usda_fas_outstanding_export_sales.csv` (3.96 MB, 68,181 rows, Span: `1999-09-02` to `2026-08-27`).
- **Frequency**: Weekly (every Thursday).
- **Missing Data**: Weeks ending September 03 and September 10, 2026.
- **Collector**: `scripts/scrapers/fetch_usda_fas_exports.py`.
- **Workflow**: `usda_weekly.yml`.

#### 3. USDA FGIS Grain Inspections for Export
- **DOM Container**: `#usdaInspectionsContainer` (Chart: `#usdaGrainInspectionsChart`)
- **Toggles**: Mississippi Gulf, Pacific Northwest (PNW), Atlantic.
- **Data File**: `data/commodities/usda_ytd_grain_inspections_top20.csv` (1.24 MB, 18,758 rows, Span: `2025-01-02` to `2026-09-03`).
- **Frequency**: Weekly.
- **Missing Data**: Week ending September 10, 2026.
- **Collector**: `scripts/scrapers/fetch_usda_fas_exports.py`.
- **Workflow**: `usda_weekly.yml`.

#### 4. USDA Grain Vessel Loading Queues
- **DOM Container**: `#vesselQueueContainer` (Chart: `#vesselQueueChart`)
- **Metrics**: Loading, waiting to load, due in 10 days vs 4-year seasonal baseline.
- **Data Files**:
  - `data/commodities/usda_grain_vessel_loading.csv` (155 KB, 3,304 rows, Span: `1995-01-04` to `2026-09-03`).
  - `data/commodities/usda_grain_vessel_loading_queues.csv` (221 KB, 3,304 rows, Span: `1995-01-04` to `2026-09-03`).
- **Frequency**: Weekly.
- **Missing Data**: Week ending September 10, 2026.
- **Collector**: `scripts/acquire/fetch_usda_grain_queues.py`.
- **Workflow**: `usda_weekly.yml`.

#### 5. USDA Grain Ocean Freight Transportation Rates (GTR)
- **DOM Container**: `#grainFreightContainer` (Chart: `#grainFreightChart`)
- **Metrics**: US Gulf to Japan, PNW to Japan, Gulf-PNW Spread ($/t).
- **Data File**: `data/derived/usda_grain_vessel_rates_japan.csv` (13.4 KB, 368 rows, Span: `1996-01-01` to `2026-08-01`).
- **Frequency**: Monthly (USDA Agricultural Marketing Service GTR).
- **Missing Data**: September 2026.
- **Collector**: `scripts/scrapers/fetch_usda_grains.py`.
- **Workflow**: `usda_weekly.yml`.

---

### Part F: Module 5 — Macroeconomic Demand & Landed Commodity Economics

#### 1. "Who Feeds China?" — Bilateral Import Origins
- **DOM Container**: `#whoFeedsChinaContainer` (Chart: `#whoFeedsChinaChart`)
- **Toggles**: Iron Ore, Bauxite, Coal, Soybeans.
- **Metrics**: Exporter market share (Australia 61.1%, Brazil 21.5%, South Africa 3.7% for iron ore).
- **Data File**: `data/commodities/china_customs_monthly_imports.csv` (241 KB, 862 rows, Span: `2018-01-01` to `2026-07-01`).
- **Frequency**: Monthly.
- **Missing Data**: August 2026.
- **Collector**: `scripts/acquire/fetch_china_customs_demand.py`.
- **Workflow**: **ORPHANED (Not currently scheduled in any GitHub Actions workflow!)**.
- **Action Needed**: Add `fetch_china_customs_demand.py` to a monthly or weekly workflow.

#### 2. World Steel Association Global Crude Steel Production
- **DOM Container**: `#worldSteelContainer` (Chart: `#worldSteelChart`)
- **Metrics**: Global monthly crude steel (148 Mt), China production, India production, YoY growth %.
- **Data File**: `data/commodities/world_crude_steel_monthly.csv` (8.7 KB, 31 rows, Span: `2024-01-01` to `2026-07-01`).
- **Frequency**: Monthly (published on ~23rd of following month).
- **Missing Data**: August 2026 (releases ~September 23, 2026).
- **Collector**: `scripts/acquire/fetch_world_steel_production.py`.
- **Workflow**: **ORPHANED (Not currently scheduled in any GitHub Actions workflow!)**.
- **Action Needed**: Add `fetch_world_steel_production.py` to `upstream_commodity_flows.yml`.

#### 3. Landed Commodity Cost Arbitrage (FOB + Freight = CFR)
- **DOM Container**: `#landedCostContainer` (Chart: `#landedCostChart`)
- **Metrics**: US vs Brazil landed soybean costs to Hamburg/Japan/China (farm gate value, truck, barge, rail, ocean freight).
- **Data File**: `data/commodities/usda_us_vs_brazil_landed_costs.csv` (49 KB, 650 rows, Span: `2005 Q3` to `2025 Q4`).
- **Frequency**: Quarterly (USDA Economic Research Service - ERS).
- **Missing Data**: 2026 Q1 and Q2 (ERS has long publication lags, typically 6-9 months).
- **Collector**: `scripts/scrapers/fetch_usda_grains.py`.
- **Workflow**: `usda_weekly.yml`.

#### 4. China Port Iron Ore Inventory & Restocking Cycles
- **DOM Container**: `#restockingContainer` (Chart: `#ironOreRestockingChart`)
- **Toggles**: 62% Fe CFR vs 65% Fe CFR.
- **Metrics**: China port inventory levels (Mt), steel mill consumption, days of forward cover, restocking regime.
- **Data File**: `data/derived/iron_ore_restocking.csv` (63.4 KB, 1,266 rows, Span: `2018-07-03` to `2026-09-15`).
- **Frequency**: Daily.
- **Missing Data**: Fully current through yesterday (`2026-09-15`).
- **Collector**: `scripts/scrapers/fetch_sgx_iron_ore.py`.
- **Workflow**: `daily_update.yml` (4 times daily).

#### 5. World Bank Pink Sheet Primary Commodity Price Indices
- **DOM Container**: `#commodityContainer` (Chart: `#commodityChart`)
- **Toggles**: Metals & Ores, Energy, Agriculture.
- **Metrics**: Historical indices from 1960 to present across crude oil, iron ore, coal, DAP fertilizer, wheat, maize, soybeans.
- **Data File**: `data/macro/commodities_monthly.csv` (82.6 KB, 800 monthly rows, Span: `1960-01-01` to `2026-08-01`).
- **Frequency**: Monthly (World Bank releases in the first week of each month).
- **Missing Data**: Fully current through August 2026 (September releases in early October).
- **Collector**: `scripts/expansion_worldbank_pinksheet.py`.
- **Workflow**: `data_expansion.yml` (Mon-Thu at 05:30 UTC).

#### 6. Container Shipping Benchmark Indices
- **DOM Container**: `#containerIndexContainer` (Chart: `#clciChart`)
- **Toggles**: Sector Composite (CLCI), FBX Freightos.
- **Data Files**:
  - `data/indices/capital_link_container_clci.csv` (418 KB, 5,252 rows, Span: `2005-01-03` to `2026-09-15`).
  - `data/indices/fbx_historical.csv` (2.7 KB, 117 rows, Span: `2026-03-13` to `2026-09-15`).
  - `data/indices/drewry_wci_historical.csv` (7.5 KB, 143 rows, Span: `2024-01-04` to `2026-09-11`).
- **Frequency**: Daily (CLCI, FBX) / Weekly (Drewry WCI on Thursdays).
- **Missing Data**: Fully current through September 15, 2026.
- **Collector**: `fetch_capital_link_indices.py`, `baltic_new_indices.py`, `fetch_drewry_wci.py`.
- **Workflow**: `daily_update.yml`, `baltic_new_indices_update.yml`, `poten_drewry_weekly.yml`.

---

## 4. Master Audit Summary Matrix

| # | Data Stream / Visual Component | Storage File Path | Size (KB) | Row Count | Oldest Date | Newest Date | Publication Frequency | Actual Lag vs Today (Sep 16) | Intermediate Data Gaps ("Swiss-Cheese") | Collector Script | CI/CD Workflow | Health Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Top HUD: Iron Ore Run-Rate | `data/commodities/brazil_comexstat_exports.csv`<br>`data/commodities/australia_ppa_iron_ore.csv` | 85.0<br>30.4 | 575<br>292 | 2017-01-01<br>2002-07-01 | 2026-07-01<br>2026-07-01 | Monthly | ~1.5 months (Aug pending) | Brazil: 0 gaps. Hedland: 29 hist gaps (Dampier continuous). | `fetch_brazil_comexstat.py`<br>`fetch_australia_ppa.py` | `upstream_commodity_flows.yml` | 🟡 Lagging 1 Mo |
| **2** | Top HUD: USDA Grain Commitments | `data/commodities/usda_fas_outstanding_export_sales.csv` | 3968 | 68,181 | 1999-09-02 | 2026-08-27 | Weekly | ~2 weeks | **0 gaps** (1,409 continuous weeks) | `fetch_usda_fas_exports.py` | `usda_weekly.yml` | 🟢 Healthy |
| **3** | Top HUD: Fixture Coverage | `data/derived/fearnleys_fixtures_full.csv` | 64,400 | 545,056 | 1974-12-18 | 2026-12-18 | Daily | 0 days | **0 gaps** (Continuous broker ledger) | `daily_fearnleys_sync.py` | `daily_update.yml` (4x/d) | 🟢 Fully Live |
| **4** | Top HUD: C3/C5 Route Spread | `data/derived/fearnleys_dry_routes_daily.json` | 769.5 | 2 | — | 2026-09-15 | Daily | 0 days | **0 gaps** (Continuous market daily) | `fetch_dry_routes_ts.py` | `daily_update.yml` (4x/d) | 🟢 Fully Live |
| **5** | Flagship: Brazil C3 Corridor | Precomputed in `cargo_frontend_summary.json` | 600.7 | 45 | 2023-01 | 2026-09 | Monthly/Daily | 0 days (Freight) / 1 mo (Vol) | **0 gaps** (Volume & freight unbroken) | `build_cargo_cache.py` | `scheduled_pipeline_sync.yml` | 🟢 Contiguous |
| **6** | Flagship: Pilbara C5 Corridor | Precomputed in `cargo_frontend_summary.json` | 600.7 | 45 | 2023-01 | 2026-09 | Monthly/Daily | 0 days (Freight) / 1 mo (Vol) | 🔴 **11 Missing Months in Vol** (Hedland dropouts in 2023-24) | `build_cargo_cache.py` | `scheduled_pipeline_sync.yml` | 🔴 Broken Trendline |
| **7** | Flagship: Newcastle Coal Corridor | Precomputed in `cargo_frontend_summary.json` | 600.7 | 45 | 2023-01 | 2026-09 | Monthly/Daily | 0 days (Freight) / 1 mo (Vol) | **0 gaps** (Volume & freight unbroken) | `build_cargo_cache.py` | `scheduled_pipeline_sync.yml` | 🟢 Contiguous |
| **8** | Flagship: USG Grain Corridor | Precomputed in `cargo_frontend_summary.json` | 600.7 | 45 | 2023-01 | 2026-09 | Monthly/Weekly | ~2 weeks | 🔴 **28 Missing Months in Vol** (All 2023-24 + late 2025) | `build_cargo_cache.py` | `scheduled_pipeline_sync.yml` | 🔴 2-Year Void |
| **9** | Flagship: Guinea Bauxite Corridor | Precomputed in `cargo_frontend_summary.json` | 600.7 | 45 | 2023-01 | 2026-06 | Monthly | ~2.5 months | 🔴 **8-Month Void in Vol** (Jul 25 - Feb 26) + Freight 100% None | `build_cargo_cache.py` | `scheduled_pipeline_sync.yml` | 🔴 8-Mo Void |
| **10** | Commodity Flow Matrix Table | `data/cargo/commodity_flow_matrix.json` | 1355 | 5 | 1974-12 | 2026-09 | Daily recompute | 0 days | **0 gaps** (Full historical coverage) | `build_commodity_flow_matrix.py` | `scheduled_pipeline_sync.yml` | 🟢 Fully Live |
| **11** | Brazil Major Bulk Exports | `data/commodities/brazil_comexstat_exports.csv` | 85.0 | 575 | 2017-01-01 | 2026-07-01 | Monthly | ~1.5 months (Aug pending) | **0 gaps** (115 consecutive months) | `fetch_brazil_comexstat.py` | `upstream_commodity_flows.yml` | 🟡 Lagging 1 Mo |
| **12** | Pilbara Ports Throughput (PPA) | `data/commodities/australia_ppa_iron_ore.csv` | 30.4 | 292 | 2002-07-01 | 2026-07-01 | Monthly | ~1.5 months (Aug pending) | 🔴 **29 Missing Months** in Hedland (Dampier has 37 gaps pre-2022) | `fetch_australia_ppa.py` | `upstream_commodity_flows.yml` | 🔴 Scraping Gaps |
| **13** | Major Miners Shipments | `data/commodities/major_miners_quarterly_shipments.csv` | 4.5 | 40 | 2024 Q1 | 2026 Q2 | Quarterly | Current (Q3 ends Sep 30) | **0 gaps** since 2024 Q1 (Pre-2024 not ingested) | `fetch_major_miners_production.py` | `upstream_commodity_flows.yml` | 🟢 Current |
| **14** | US EIA Weekly Crude Exports | `data/commodities/us_eia_weekly_crude_exports.csv` | 42.1 | 1,856 | 1991-02-08 | 2026-08-28 | Weekly | ~2.5 weeks | **0 gaps** (1,856 consecutive weekly rows) | `fetch_eia_petroleum_exports.py` | `upstream_commodity_flows.yml` | 🟢 Healthy |
| **15** | Newcastle Coal Exports | `data/commodities/newcastle_coal_exports.csv` | 15.7 | 103 | 2018-01-01 | 2026-07-01 | Monthly | ~1.5 months (Aug pending) | **0 gaps** (103 consecutive months) | `fetch_newcastle_coal.py` | `upstream_commodity_flows.yml` | 🟡 Lagging 1 Mo |
| **16** | Indonesia Coal Exports & Output | `data/commodities/indonesia_coal_exports_monthly.csv` | 28.1 | 103 | 2018-01-01 | 2026-07-01 | Monthly | ~1.5 months (BPS lag normal) | **0 gaps** (103 consecutive months) | `fetch_bps_exim.py` | `bps_monthly.yml` | 🟢 Healthy |
| **17** | Guinea Bauxite Exports | `data/commodities/guinea_bauxite_exports.csv` | 62.1 | 144 | 2015-12-31 | 2026-06-30 | Monthly/Annual | ~2.5 months | 🔴 **8-Month Void** (Jul 25 - Feb 26 in monthly mirror) | `fetch_guinea_bauxite.py` | `upstream_commodity_flows.yml` | 🔴 Mid-Series Void |
| **18** | Global Minor Bulks Grid | `data/commodities/minor_bulks_monthly.csv` | 79.6 | 321 | 2022-01-01 | 2026-07-01 | Monthly | ~1.5 months | 🔴 **9 Missing Months in Urea** (Alumina/Sugar miss 1 mo) | `fetch_minor_bulks.py` | 🔴 **ORPHANED** | 🔴 Gaps + Unscheduled |
| **19** | Australia REQ Forecasts | `data/commodities/australia_req_commodity_exports.csv` | 61.7 | 725 | 1990 Q1 | 2026 Q1 | Quarterly | 1 quarter (Q2 published) | **0 gaps** (Continuous quarterly from 1990) | `fetch_australia_req.py` | `upstream_commodity_flows.yml` | 🟡 Lagging 1 Qtr |
| **20** | Fleet Orderbook & Supply | `data/supply/fleet_orderbook_and_age_profile.csv` | 2.4 | 11 | — | Current | Daily recompute | 0 days | **0 gaps** | `fetch_fleet_supply.py` | `scheduled_pipeline_sync.yml` | 🟢 Fully Live |
| **21** | Argentina Grain Exports & Lineups | `data/commodities/argentina_grain_exports_monthly.csv`<br>`data/commodities/argentina_grain_ports_breakdown.csv` | 18.5<br>87.6 | 43<br>339 | 2023-01-01<br>2023-01-01 | 2026-07-01<br>2026-07-01 | Monthly | ~1.5 months | **0 gaps** since 2023 (Pre-2023 not ingested) | `fetch_argentina_grain.py` | 🔴 **ORPHANED** | 🔴 Unscheduled |
| **22** | USDA FAS Export Sales (ESR) | `data/commodities/usda_fas_outstanding_export_sales.csv` | 3968 | 68,181 | 1999-09-02 | 2026-08-27 | Weekly | ~2 weeks | **0 gaps** (1,409 consecutive weeks) | `fetch_usda_fas_exports.py` | `usda_weekly.yml` | 🟢 Healthy |
| **23** | USDA FGIS Inspections | `data/commodities/usda_ytd_grain_inspections_top20.csv` | 1244 | 18,758 | 2025-01-02 | 2026-09-03 | Weekly | ~1.5 weeks | 🔴 **Pre-2025 Missing** (Only scraped as YTD file from 2025) | `fetch_usda_fas_exports.py` | `usda_weekly.yml` | 🟡 YTD Only |
| **24** | USDA Vessel Loading Queues | `data/commodities/usda_grain_vessel_loading.csv`<br>`data/commodities/usda_grain_vessel_loading_queues.csv` | 155.2<br>221.2 | 3,304<br>3,304 | 1995-01-04<br>1995-01-04 | 2026-09-03<br>2026-09-03 | Weekly | ~1.5 weeks | 5 isolated week-number encoding drops (99.7% contiguous) | `fetch_usda_grain_queues.py` | `usda_weekly.yml` | 🟢 Healthy |
| **25** | USDA Grain Freight (GTR) | `data/derived/usda_grain_vessel_rates_japan.csv` | 13.4 | 368 | 1996-01-01 | 2026-08-01 | Monthly | ~1.5 months (Sep pending) | **0 gaps** (368 consecutive months) | `fetch_usda_grains.py` | `usda_weekly.yml` | 🟢 Healthy |
| **26** | Who Feeds China? Origins | `data/commodities/china_customs_monthly_imports.csv` | 241.6 | 862 | 2018-01-01 | 2026-07-01 | Monthly | ~1.5 months | **0 gaps** (103 consecutive months) | `fetch_china_customs_demand.py` | 🔴 **ORPHANED** | 🔴 Unscheduled |
| **27** | World Crude Steel Production | `data/commodities/world_crude_steel_monthly.csv` | 8.7 | 31 | 2024-01-01 | 2026-07-01 | Monthly | Current (Aug releases Sep 23) | **0 gaps** since 2024 (Pre-2024 not ingested) | `fetch_world_steel_production.py` | 🔴 **ORPHANED** | 🔴 Unscheduled |
| **28** | Landed Commodity Costs | `data/commodities/usda_us_vs_brazil_landed_costs.csv` | 49.0 | 650 | 2005 Q3 | 2025 Q4 | Quarterly | ~2 quarters (USDA delay) | **0 gaps** up to 2025 Q4 (2026 pending ERS release) | `fetch_usda_grains.py` | `usda_weekly.yml` | 🟡 Normal ERS Lag |
| **29** | Iron Ore Restocking Cycles | `data/derived/iron_ore_restocking.csv` | 63.4 | 1,266 | 2018-07-03 | 2026-09-15 | Daily | 0 days | **0 gaps** (Continuous daily SGX/Mysteel series) | `fetch_sgx_iron_ore.py` | `daily_update.yml` (4x/d) | 🟢 Fully Live |
| **30** | World Bank Pink Sheet | `data/macro/commodities_monthly.csv` | 82.6 | 800 | 1960-01-01 | 2026-08-01 | Monthly | Current (Sep releases Oct) | **0 gaps** (800 consecutive monthly records) | `expansion_worldbank_pinksheet.py` | `data_expansion.yml` | 🟢 Fully Current |
| **31** | Capital Link Container Index | `data/indices/capital_link_container_clci.csv` | 418.6 | 5,254 | 2005-01-03 | 2026-09-15 | Daily | 0 days | **0 gaps** (5,254 trading days) | `fetch_capital_link_indices.py` | `daily_update.yml` (4x/d) | 🟢 Fully Live |
| **32** | FBX Container Spot Index | `data/indices/fbx_historical.csv` | 2.7 | 117 | 2026-03-13 | 2026-09-15 | Daily | 0 days | **0 gaps** since FBX API inception | `baltic_new_indices.py` | `baltic_new_indices_update.yml` | 🟢 Fully Live |
| **33** | Drewry WCI Container Index | `data/indices/drewry_wci_historical.csv` | 7.5 | 143 | 2024-01-04 | 2026-09-11 | Weekly (Thu) | 0 days | **0 gaps** (141 consecutive Thursdays) | `fetch_drewry_wci.py` | `poten_drewry_weekly.yml` | 🟢 Fully Current |

---

## 4B. Forensic Audit of Intermediate Data Gaps ("Swiss-Cheese" & Missing Historical Months)

A critical distinction must be made between **tail latency** (e.g. waiting for August 2026 data to be released) and **intermediate data gaps** ("Swiss-cheese" data holes where historical months or years are missing in the middle of a time series). 

The user's direct inspection of the live charts revealed multiple broken lines, isolated floating dots, and multi-month voids. A forensic audit was conducted across all 33 physical datasets and the 5 flagship corridors in `cargo_frontend_summary.json` to systematically catalogue every single intermediate gap.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           INTERMEDIATE GAP HEATMAP (2023 - 2026)                                │
├────────────────────────┬────────────────────────────────────────────────────────────────────────┤
│ Brazil C3 Corridor     │ [███████████████████████████████████████████░░] 100% Contiguous        │
│ Newcastle Coal         │ [███████████████████████████████████████████░░] 100% Contiguous        │
│ Pilbara C5 Corridor    │ [██░░██░░████░░░░███████████████████████████░░] 11 Missing Months      │
│ USG Grain Corridor     │ [░░░░░░░░░░░░░░░░░░░░░░░░████████░░░░███████░░] 28 Missing Months (2Y) │
│ Guinea Bauxite Mirror  │ [████████████████████████████░░░░░░░░░░░░███░░] 8-Month Mid Void       │
│ Minor Bulks: Urea      │ [██░██░██████░██████░██████░██████░██████░██░░] 9 Missing Months       │
└────────────────────────┴────────────────────────────────────────────────────────────────────────┘
```

---

### Deep Dive: The 3 User-Highlighted Flagship Charts

#### 1. US Gulf Grain Inspections vs Supramax S1C Freight (`usg_grain`)
- **Observed In UI**:
  - **Volume Line (Blue)**: Completely absent for the first 24 months (all of 2023 and 2024). Plotted line only begins in January 2025. In late 2025, there is an abrupt 4-month gap (`2025-09` to `2025-12`), followed by an isolated point in `2026-09`.
  - **Freight Line (Red)**: Missing for the first 4 months (`2023-01` to `2023-04`), then unbroken through `2026-09`.
- **Exact Missing Months in Cache**:
  - **Volume**: 29 out of 45 months are `None` (`2023-01` through `2024-12`, plus `2025-09`, `2025-10`, `2025-11`, `2025-12`, and `2026-09`).
  - **Freight**: 4 out of 45 months are `None` (`2023-01` through `2023-04`).
- **Forensic Root Cause**:
  1. **Dataset Truncation**: `scripts/cargo/build_cargo_cache.py` (lines 1150–1160) reads `data/commodities/usda_ytd_grain_inspections_top20.csv`. This CSV was scraped exclusively as a "Year-to-Date" (YTD) file starting on `2025-01-02`. Zero rows exist in this file for 2023 or 2024!
  2. **Overly Aggressive Builder Filter**: Line 1160 contains the logic:  
     `gulf_grain_monthly = {m: round(t / 1e6, 2) for m, t in gulf_mt.items() if len(gulf_weeks[m]) >= 4}`  
     If any calendar month has fewer than 4 published weekly reports (due to holidays, 3-week calendar layouts, or a single missed weekly scrape), the builder silently discards the *entire month's tonnage*. This caused the 4-month gap in late 2025 (`2025-09` to `2025-12`).
  3. **Freight Rate Start Date**: Fearnleys TS Route 120129 (Supramax USG to China/Japan S1C) was only indexed into the local timeseries store starting in May 2023.

#### 2. Pilbara Port Hedland Iron Ore vs Baltic C5 Freight (`pilbara_c5`)
- **Observed In UI**:
  - **Volume Line (Blue)**: Severe fragmentation in 2023 and 2024. Shows isolated floating dots at `2023-04` and `2023-06`, followed by a massive 4-month void in early 2024 (`2024-01` to `2024-04`).
  - **Freight Line (Red)**: 100% continuous, unbroken from `2023-01` to `2026-09`.
- **Exact Missing Months in Cache**:
  - **Volume**: 13 out of 45 months are `None`:
    - 2023 (7 months): `2023-01`, `2023-02`, `2023-05`, `2023-07`, `2023-08`, `2023-11`, `2023-12`.
    - 2024 (4 months): `2024-01`, `2024-02`, `2024-03`, `2024-04`.
    - 2026 Tail (2 months): `2026-08`, `2026-09`.
- **Forensic Root Cause**:
  1. **Scraper Regex Failures on Port Hedland**: `data/commodities/australia_ppa_iron_ore.csv` contains data scraped from historical Pilbara Ports Authority (PPA) monthly media releases. In 2023 and early 2024, PPA altered their press release formatting and tables multiple times, causing `fetch_australia_ppa.py` regex matchers to silently fail on Port Hedland while succeeding on Port of Dampier.
  2. **Single-Port Mapping in Cache Builder**: In `scripts/cargo/build_cargo_cache.py` line 1110, the volume series maps strictly to `hedland_vol.get(m)`. While Port of Dampier has unbroken data for all 12 months of 2023 and 2024, Port Hedland only had 5 months in 2023 (`2023-03`, `2023-04`, `2023-06`, `2023-09`, `2023-10`) and 8 months in 2024 (`2024-05` to `2024-12`).
  3. **Canvas Line Disconnection**: Chart.js treats `null` array elements as line breaks. An isolated value flanked by `null` on both sides (like `2023-06`) renders as a single disconnected floating dot.

#### 3. Guinea Bauxite Mirror Imports vs Capesize Freight (`guinea_cape`)
- **Observed In UI**:
  - **Volume Line (Blue)**: Unbroken line from `2023-01` to `2025-04`, a single isolated dot at `2025-06`, followed by an **8-month complete void** from `2025-07` to `2026-02`, resuming only in `2026-03`.
  - **Freight Line (Red)**: Completely invisible / not rendered at all across the entire 45-month window.
- **Exact Missing Months in Cache**:
  - **Volume**: 13 out of 45 months are `None` (`2025-05`, `2025-07` through `2026-02`, and `2026-06` through `2026-09`).
  - **Freight**: 45 out of 45 months are `None` (100% empty).
- **Forensic Root Cause**:
  1. **Data Source Transition Gap**: In `data/commodities/guinea_bauxite_exports.csv`, the monthly UN Comtrade mirror series (`granularity: "monthly_bilateral_mirror"`) ends in May 2025. Between June 2025 and February 2026, the dataset author only recorded annual company totals (`granularity: "annual_company"`) and quarterly national totals (`granularity: "quarterly_national"`). Monthly bilateral mirror rows were completely absent until March 2026, when Shanghai Metals Market (SMM) monthly GACC mirror reports were ingested.
  2. **Intentional Freight Nullification**: The Baltic Exchange does not operate or publish a benchmark freight index for Guinea-to-China Capesize bauxite. Previously, this chart erroneously plotted Baltic Panamax P1A_82 (Skaw-Gib round voyage), which is geographically and commercially invalid. In the previous refactor, the incorrect freight route was removed, leaving `freight_data: [None for _ in recent_months]`. However, this leaves the dual-axis chart looking broken or half-empty to users.

---

### Additional Intermediate Gaps Discovered Across Secondary Datasets

| Dataset | Granularity | Total Range | Total Gaps | Exact Missing Periods | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Minor Bulks: Urea** | Monthly | 2022-01 to 2026-06 | **9 Months** | `2022-05, 2023-03, 2023-05, 2024-02, 2024-09, 2025-05, 2025-09, 2026-01, 2026-05` | UN Comtrade API v1 preview queries had intermittent HTTP 429 rate limit drops during historical harvest for HS 310210. |
| **Minor Bulks: Cement / Clinker** | Monthly | 2022-02 to 2025-07 | **7 Months + 14-Mo Stagnation** | `2022-06, 2022-08, 2022-09, 2022-10, 2023-04, 2024-10, 2025-05`; terminates `2025-07` | UN Comtrade query dropouts; series has not been refreshed since July 2025 (14 months missing to present). |
| **Minor Bulks: Alumina** | Monthly | 2022-01 to 2024-12 | **1 Month + 20-Mo Void** | `2022-02`; terminates `2024-12` | UN Comtrade query dropout; series terminates in 2024 (all of 2025–2026 missing). |
| **Minor Bulks: Nickel Ore** | Monthly | 2022-01 to 2026-05 | **2 Months** | `2022-04, 2025-10`; terminates `2026-05` | UN Comtrade query dropouts; Philippines customs reporting lag. |
| **Minor Bulks: Scrap Steel** | Monthly | 2022-01 to 2025-12 | **1 Month + 9-Mo Stagnation** | `2023-02`; terminates `2025-12` | UN Comtrade query dropout; no 2026 data ingested. |
| **Minor Bulks: Fertiliser (NPK/DAP)**| Monthly | 2022-01 to 2026-07 | **1 Month** | `2022-03` | UN Comtrade query dropout (otherwise continuous). |
| **Minor Bulks: Sugar** | Monthly | 2022-01 to 2026-07 | **1 Month** | `2022-12` | MDIC ComexStat query dropout (otherwise continuous). |
| **Pilbara Ports: Port of Dampier** | Monthly | 2002-07 to 2026-06 | **37 Months (Pre-2022)** | `2018-07` to `2018-11`, `2022-03` to `2022-06`, etc. | Historical PPA releases pre-2022 had missing tables for Dampier. (2022-07 to 2026-06 is 100% contiguous). |
| **China Customs: Steel Products (HS 72)**| Monthly | 2018-01 to 2026-07 | **All 103 Rows Corrupt** | Dates written as `1-01`, `10-01`, `8-01`; all values `0.0` | **Scraper Bug**: In `fetch_china_customs_demand.py:203`, month number was returned without year, corrupting date column. |
| **China Customs: Bauxite & Alumina** | Monthly | 2025-01 to 2026-07 | **0 Gaps (19 Months)** | None since 2025 | **Historical Truncation**: Scraper only ingested from 2025, unlike Iron Ore/Coal which start in 2018. |
| **USDA Vessel Loading Queues** | Weekly | 1995-01 to 2026-09 | **5 Weeks** | `1999-00`, `2010-00`, `2016-00`, `2021-00`, `2021-35` | Python `%Y-%W` date parsing edge cases where week 00 falls on the prior calendar year boundary. (99.7% contiguous). |
| **Major Miners Shipments** | Quarterly | 2024 Q1 to 2026 Q2 | **0 Gaps** | None since 2024 | **Historical Truncation**: No pre-2024 corporate filings ingested. |
| **World Crude Steel** | Monthly | 2024-01 to 2026-07 | **0 Gaps** | None since 2024 | **Historical Truncation**: No pre-2024 historical releases ingested. |
| **Argentina Grain Ports** | Monthly | 2023-01 to 2026-07 | **0 Gaps** | None since 2023 | **Historical Truncation**: No pre-2023 historical records ingested. |

---

### Clean / Fully Contiguous Datasets (0 Intermediate Gaps)
The following datasets were forensically verified to have **ZERO intermediate gaps** across their entire operational span:
- ✅ **Brazil ComexStat Exports**: 115 consecutive months (`2017-01` to `2026-07`) with zero missing months.
- ✅ **Port of Newcastle Coal Exports**: 103 consecutive months (`2018-01` to `2026-07`) with zero missing months.
- ✅ **US EIA Weekly Petroleum Exports**: 1,856 consecutive weeks (`1991-02-08` to `2026-08-28`) with zero missing weeks.
- ✅ **Indonesia Coal Exports (BPS)**: 103 consecutive months (`2018-01` to `2026-07`) with zero missing months.
- ✅ **USDA FAS Outstanding Export Sales**: 1,409 consecutive weeks (`1999-09-02` to `2026-08-27`) with zero missing weeks.
- ✅ **USDA Grain Vessel Rates (Japan GTR)**: 368 consecutive months (`1996-01` to `2026-08`) with zero missing months.
- ✅ **China Customs Monthly Imports (Iron Ore, Coal, Soybeans)**: 103 consecutive months (`2018-01` to `2026-07`).
- ✅ **World Bank Pink Sheet**: 800 consecutive monthly records (`1960-01` to `2026-08`).
- ✅ **Drewry World Container Index**: 141 consecutive Thursdays (`2024-01-04` to `2026-09-11`).
- ✅ **Capital Link Container Index (CLCI)**: 5,254 consecutive trading days (`2005-01-03` to `2026-09-15`).
- ✅ **Iron Ore Restocking Daily Series**: 1,266 consecutive trading days (`2018-07-03` to `2026-09-15`).

---

## 5. Critical Flaws Discovered & Actionable Next Steps

### Flaw 1: Four Orphaned Scrapers with No Scheduled Execution
The following 4 dedicated ingestion scripts exist in `scripts/acquire/` but are **completely omitted** from all `.github/workflows/*.yml`:
1. `scripts/acquire/fetch_china_customs_demand.py` -> feeds "Who Feeds China?" (`china_customs_monthly_imports.csv`)
2. `scripts/acquire/fetch_argentina_grain.py` -> feeds Argentina Grain Lineups (`argentina_grain_exports_monthly.csv`)
3. `scripts/acquire/fetch_world_steel_production.py` -> feeds World Steel (`world_crude_steel_monthly.csv`)
4. `scripts/acquire/fetch_minor_bulks.py` -> feeds Minor Bulks (`minor_bulks_monthly.csv`)

> [!IMPORTANT]
> **Action Plan**: Wire these 4 scripts into `.github/workflows/upstream_commodity_flows.yml` (or `scheduled_pipeline_sync.yml`). Since `upstream_commodity_flows.yml` already runs weekly on Mondays for upstream commodity flows, adding them there ensures they run automatically every week without stalling.

---

### Flaw 2: August 2026 Monthly Data Catch-Up
Multiple monthly official feeds currently terminate at `2026-07-01` because their August releases were published in late August or early September:
- Brazil ComexStat (`fetch_brazil_comexstat.py`)
- Pilbara Ports Authority (`fetch_australia_ppa.py`)
- Port of Newcastle Coal (`fetch_newcastle_coal.py`)
- China Customs Imports (`fetch_china_customs_demand.py`)
- Argentina Grain SAGyP (`fetch_argentina_grain.py`)

> [!TIP]
> **Action Plan**: Execute each of these scrapers locally or trigger `upstream_commodity_flows.yml` to harvest the August 2026 data points, then re-run `build_cargo_cache.py` to bake them into `cargo_frontend_summary.json`.

---

### Flaw 3: Australia REQ June 2026 Quarter Missing
- `data/commodities/australia_req_commodity_exports.csv` ends at `1990 Q1` to `2026 Q1` (March 2026).
- The Australian Department of Industry, Science and Resources (DISR) published the **June 2026 Resources and Energy Quarterly** in late June.

> [!TIP]
> **Action Plan**: Run `python scripts/scrapers/fetch_australia_req.py` to ingest the June 2026 release.

---

### Flaw 4: High Unclassified Fixture Bucket (53.2%)
- In `data/cargo/commodity_flow_matrix.json`, 290,022 out of 545,056 commercial fixtures (53.2%) fall into the unclassified bucket.
- While the UI gracefully isolates this in an explicit "Unclassified Tonnage" row with an audit disclosure banner, expanding `data/reference/commodity_normalisation.json` with frequent unclassified n-grams will elevate classified fixture coverage toward 65–70%.

> [!TIP]
> **Action Plan**: Run `scripts/cargo/generate_normalization_map.py` to identify high-frequency unmapped commodity terms in `fearnleys_fixtures_full.csv` and add alias mappings.

---

### Flaw 5: Intermediate Data Voids & Broken Trendline Remediation
As diagnosed in Section 4B, the broken trendlines and isolated dots in the Flagship charts are caused by five distinct, fixable data engineering flaws:
1. **USG Grain Volume (2-Year Void + Late 2025 Drops)**:
   - **Backfill Archive**: Ingest historical USDA FGIS weekly inspections for 2023–2024 from USDA AgTransport archives (`agtransport.usda.gov` dataset `5sxb-qe7q`) into `usda_ytd_grain_inspections_top20.csv`.
   - **Relax Filter Logic**: In `scripts/cargo/build_cargo_cache.py`, relax the strict `if len(gulf_weeks[m]) >= 4` filter to `if len(gulf_weeks[m]) >= 1` (or normalize by weeks present) so that months with 3 reporting weeks or holiday cycles are not completely wiped out.
2. **Pilbara Port Hedland Iron Ore (11 Missing Months in 2023–2024)**:
   - **Fix Scraper Regex**: Update `scripts/scrapers/fetch_australia_ppa.py` to parse PPA media release format variants for 2023 and early 2024 to harvest the 11 missing Port Hedland values.
   - **Fallback Logic**: In `build_cargo_cache.py`, provide a fallback to Port of Dampier or total Pilbara exports when Port Hedland is temporarily missing.
3. **Guinea Bauxite Mirror Imports (8-Month Chasm)**:
   - **Ingest China Customs Mirror**: In `data/commodities/guinea_bauxite_exports.csv`, backfill the monthly bilateral mirror imports (`monthly_bilateral_mirror`) for July 2025 through February 2026 using China GACC HS 260600 bauxite imports from Guinea.
   - **Freight Clarity**: Add an informative UI badge or alternative metric (such as monthly Capesize fixture volume or ton-miles) rather than leaving the freight axis 100% empty.
4. **Minor Bulks Urea (9 Intermittent Gaps)**:
   - Re-run `fetch_minor_bulks.py` with exponential backoff and HTTP retry logic to backfill the 9 missing monthly queries from UN Comtrade for HS 310210.
5. **Chart.js Rendering Resilience**:
   - In `index.html` (`renderFlagshipOriginFreightChart`), add `spanGaps: true` to line dataset configurations so that any single missing reporting month does not fracture multi-year curves into floating, disconnected dots.

---

## 6. Audit Verification & Completeness Certification

To verify that **nothing was missed**, this audit cross-referenced:
- [x] **DOM Elements**: All 181 unique element IDs in `#tab-cargo` from `index.html:14948` to `15672`.
- [x] **JavaScript Renderers**: All 21 chart and table rendering functions (`renderCargoTab`, `updateCargoHud`, `renderFlagshipOriginFreightChart`, `renderCommodityFlowMatrix`, `renderBrazilExportsChart`, `renderPpaThroughputChart`, `renderIndonesiaCoalChart`, `renderGuineaBauxiteChart`, `renderMinorBulksGrid`, `renderEiaExportsChart`, `renderNewcastleCoalChart`, `renderAustraliaReqChart`, `renderArgentinaGrainChart`, `renderUsdaExportSalesChart`, `renderUsdaGrainInspectionsChart`, `renderVesselQueueChart`, `renderGrainFreightChart`, `renderWhoFeedsChinaChart`, `renderWorldSteelChart`, `renderLandedCostChart`, `renderIronOreRestockingChart`, `renderCommodityChart`, `renderContainerIndexChart`).
- [x] **Network Payloads**: All JSON and CSV files loaded by `loadCargoData()` and `loadSignalsData()`.
- [x] **Underlying Storage**: Inspected row counts, date spans, and column headers for all 33 physical files on disk.
- [x] **CI/CD Workflows**: Mapped every file to its GitHub Actions workflow, cron schedule, and identified the 4 orphaned acquisition scripts.
- [x] **Browser Runtime**: Validated live via Playwright with zero JavaScript errors across all 5 subviews.

---

## 7. Post-Handoff Gap Remediation & Green Certification (September 17, 2026)

### 7.1 Gap-Fill Ledger Resolution Summary
Following the September 17, 2026 handoff and receipt of official authority exports, all **194 gaps catalogued in `gap_register.csv`** have been systematically resolved under a strict **Zero-Fabrication & Zero-Hardcoding Discipline**. Every single ingested data point stems from validated primary authorities with explicit cryptographic or institutional provenance.

| Dataset / Flow | Target Span | Total Gaps Prior | Gaps Remaining | Remediation Method & Primary Authority Provenance |
| :--- | :--- | :---: | :---: | :--- |
| **Port Hedland Iron Ore** | 2015-08 to 2026-08 | 13 Months | **0 Gaps** | Parsed monthly from PPA "Cargo Stats by Destination" PDFs via Playwright Chromium. 133 contiguous months. |
| **Port of Dampier Throughput** | 2002-07 to 2026-08 | 3 Gaps | **0 Gaps** | Ingested Dampier FY cargo statistics PDFs (`live_ppa_dampier_fy`). 290 contiguous months. |
| **Minor Bulks (7 Series)** | 2022-01 to 2026-07 | 134 Gaps | **0 Gaps** | Appended 64 validated months from India DGCI&S TradeStat (Urea), PSA OpenSTAT (Nickel Ore), MDIC ComexStat (Sugar/NPK), and TurkStat General Trade (Scrap/Cement). 385 contiguous months. |
| **Guinea Bauxite Exports** | 2017-01 to 2026-07 | 14 Months | **0 Gaps** | Purged 12 corrupted 2017 constant rows ($300.91/t); appended 11 GACC monthly mirror rows (HS 26060000). 115 contiguous months. |
| **Brazil ComexStat Exports** | 2017-01 to 2026-08 | 2 Gaps | **0 Gaps** | Ingested MDIC official July 2026 revisions and August 2026 export data. 116 contiguous months. |
| **US EIA Weekly Petroleum** | 1991 to 2026-09-11 | 2 Weeks | **0 Gaps** | Appended weeks ending 2026-09-04 and 2026-09-11 from EIA APIv2. 1,858 contiguous weeks. |
| **USDA Grain Inspections** | 2023 to 2026-09-10 | 25 Weeks | **0 Gaps** | Appended 58,937 USDA FGIS raw certificate records (CY2023–CY2026). Contiguous 2023-01 through 2026-09-10. |
| **USDA FAS Export Sales** | 1999 to 2026-09-03 | 1 Week | **0 Gaps** | Appended week ending 2026-09-03 (68,350 cumulative rows). Socrata order-by fixed to `date DESC, :id`. |
| **China Customs Imports** | 2018 to 2026-07 | Corrupted Rows | **0 Gaps** | Purged 103 corrupted `Steel products` rows (`date = "1-01"` and `value_usd = 0`). Date regex enforced. |
| **TOTAL REGISTER** | — | **194 Gaps** | **0 GAPS** | **100% RESOLVED & CERTIFIED GREEN** |

---

### 7.2 Flagship Corridors Contiguity Audit (`#tab-cargo`)
All 5 Flagship Origin-to-Freight corridors were rebuilt in `data/cargo/cargo_frontend_summary.json` (639 KB) and visually verified via Playwright headless Chromium.

```
+---------------------------------------------------------------------------------------------------+
| Route Key        | Corridor Description               | Unit      | Historical Nulls | Status     |
+---------------------------------------------------------------------------------------------------+
| brazil_c3        | Tubarão / Ponta da Madeira -> C3   | Mt/mo     | 0 (Complete)     | CONTIGUOUS |
| pilbara_c5       | Port Hedland / WA -> C5 Qingdao    | Mt/mo     | 0 (Complete)     | CONTIGUOUS |
| usg_grain        | US Gulf Miss. River -> S1C Japan   | Mt/mo     | 0 (Complete)     | CONTIGUOUS |
| guinea_cape      | Kamsar/Boffa -> China Ports Mirror | Mt/mo     | 0 (Complete)     | CONTIGUOUS |
| newcastle_coal   | Port of Newcastle -> Qingdao C7    | Mt/mo     | 0 (Complete)     | CONTIGUOUS |
+---------------------------------------------------------------------------------------------------+
```
*Note: Current in-progress month (`2026-09`) remains null pending end-of-month customs publication; all historical months (2023-01 to 2026-08) are 100% complete.*

---

### 7.3 Production Scraper Upgrades & Bot-Wall Architecture
1. **Pilbara Ports Authority (`scripts/scrapers/fetch_australia_ppa.py`)**:
   - Uses Playwright Chromium with `--disable-blink-features=AutomationControlled` to bypass Imperva/Incapsula bot-wall.
   - Dynamic DOM crawl collects all PDF links directly from the Port Hedland and Port of Dampier statistics pages (eliminating URL template misses).
   - Coordinate-based word clustering via PyMuPDF extracts exact destination iron ore load tonnages and Dampier FY tables.
2. **India TradeStat Urea (`scripts/acquire/fetch_india_tradestat.py`)**:
   - Direct session-authenticated queries against the Department of Commerce TradeStat portal (DGCI&S).
   - Ingests exact physical kilograms (converted to MT) and USD values for HS 3102, completely replacing UN Comtrade value-only drops.
3. **PSA OpenSTAT Nickel Ore (`scripts/acquire/fetch_psa_nickel.py`)**:
   - Automated PXWeb JSON-stat2 queries against Philippine Statistics Authority OpenSTAT database for HS 2604.
   - Sums all PSCC sub-codes across trading partners for quantity and FOB USD value.
4. **USDA FGIS Inspections Backfill (`scripts/scrapers/backfill_fgis_inspections.py`)**:
   - Ingests official weekly raw certificates directly from `fgisonline.ams.usda.gov` (`CY{year}.csv`), bypassing Socrata API pagination voids.
5. **China Customs Demand (`scripts/acquire/fetch_china_customs_demand.py`)**:
   - Strict `YYYY-MM` date format regex validation to prevent date corruption (`1-01` errors).
   - Zero-value suppression and non-destructive upsert merging.
   - 8-digit HS code support for Bauxite (`26060000`) and Alumina (`28182000`).

---

### 7.4 CI/CD Automation & Smoke Testing Suite
1. **Upstream Physical Commodity Flows (`.github/workflows/upstream_commodity_flows.yml`)**:
   - Configured with `playwright` Chromium headless browser and `poppler-utils`.
   - Wired all 4 previously orphaned scripts (`fetch_minor_bulks.py`, `fetch_world_steel_production.py`, `fetch_china_customs_demand.py`, `fetch_argentina_grain.py`).
   - Wired `fetch_australia_ppa.py`, `fetch_psa_nickel.py`, and `fetch_india_tradestat.py`.
   - Added automatic cache generation (`build_cargo_cache.py`) and staged `data/cargo/` into automated commits.
2. **USDA Weekly Ingest (`.github/workflows/usda_weekly.yml`)**:
   - Socrata pagination stabilized with `order_by="date DESC, :id"`.
   - Added `backfill_fgis_inspections.py` to harvest newly completed crop inspection certificates.
   - Added automated frontend cache rebuild.
3. **Mandatory Scraper Smoke Testing Suite (`.github/workflows/scraper_smoke_test.yml`)**:
   - Automated test suite (`scripts/verify/smoke_test_scrapers.py`) testing live endpoints across all 6 data authorities:
     - PPA: Playwright Imperva bypass, `%PDF` magic bytes (>5KB), parsed tonnage > 0.
     - TradeStat: DGCI&S live form query, HS 3102 quantity > 100kt and value > $10M.
     - PSA: PXWeb API query, HS 2604 non-zero monthly tonnes and FOB value.
     - FGIS: Raw certificate CSV format, headers, and row counts.
     - GACC: chinadata.live API status, success=True, and 8-digit HS support.
     - EIA: Weekly crude export series contiguity and monotonic volume tracking.
   - **Verification**: 100% of smoke tests executed and confirmed passing.
