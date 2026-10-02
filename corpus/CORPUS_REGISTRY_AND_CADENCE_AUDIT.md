# Master Corpus Registry, Publication Cadence & Extraction Audit

**Audit Snapshot Date:** 2026-10-01 | **Repository:** Shipping Knowledge Base  
**Authoritative Ledger:** Combines the Master Extraction Register, Live Publication Cadence, Format Breakdown, Granular Sub-Sector/Fleet Breakdown, and Vector Chart Inventory across all corpus directories.

---

## 1. Executive Summary & Fleet Publication Status

- **Total Corpus Assets Cataloged:** Over 54,000 documents across 29 discrete publishers and categories.
- **Active Document Formats:** 6,639 PDFs, 9,678 HTML files, 26,451 JPG/PNG images, 18,290 Markdown files.
- **Status as of October 1, 2026:**
  - **Current & Up to Date (<= 7 days ago):** 24 publishers have their latest Week 39 / Week 40 reports fully digested.
  - **Just Ingested Live Today:** Fearnleys Week 40 (published 01/10/2026) and Agora Week 39 (published 30/09/2026) were crawled live and ingested into clean Markdown.
  - **Normal Interval / Monthly Reporting Lag:** Seabrokers, PPA, and Drewry AIS operate on 30-to-60 day reporting cycles where August figures are published in late September or early October.
  - **Chinese National Day Notice:** Hellenic Iron Ore (MMI Daily) spot updates pause during China's Golden Week (October 1 to October 7).

---

## 2. Master Publisher Cadence & Inventory Matrix

| Publisher / Source | Cadence | Latest Issue Date | Days Elapsed | Status (2026-10-01) | Formats in Corpus | Extracted MD Path | Vector Charts Extracted | Primary Master Series CSV |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- | :--- |
| **Advanced Shipping & Trading** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 253 PDF, 0 HTML, 0 IMG | [`data/extracted/md/advanced_shipping`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/advanced_shipping) | Yes (Secondhand valuation matrices & demo trends) | `advanced_shipping_sales_series.csv (6` |
| **Affinity Shipbrokers** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 254 PDF, 0 HTML, 0 IMG | [`data/extracted/md/affinity`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/affinity) | Yes (Baltic Dirty & Clean TCE trajectory curves) | `affinity_tce_series.csv (4` |
| **Agora Shipbroking** | Weekly (Wednesday/Thursday) | `2026-09-30` | 1d | **CURRENT (Just Ingested W39)** | 216 PDF, 0 HTML, 0 IMG | [`data/extracted/md/agora`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/agora) | No (Dense indicator tables across 5 pages) | `agora_indicators_series.csv (10` |
| **Banchero Costa (Bancosta)** | Weekly (Wednesday) | `2026-09-30` | 1d | **CURRENT** | 247 PDF, 0 HTML, 0 IMG | [`data/extracted/md/banchero_costa`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/banchero_costa) | Yes (Freight rates, FFA forward curves, ConTex index) | `bancosta_freight_rates_series.csv (20` |
| **Carriers Chartering (General Broker)** | Weekly (Monday) | `2026-09-28` | 3d | **CURRENT** | 136 PDF, 0 HTML, 0 IMG | [`data/extracted/md/carriers`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/carriers) | No (Tabular S&P and Baltic BSPA/BDA indices) | `carriers_sales_series.csv (3` |
| **Clarksons / Clarksons Hellas** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 180 PDF, 0 HTML, 0 IMG | [`data/extracted/md/clarksons`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/clarksons) | No (Bulker & Tanker reported sales transaction tables) | `clarksons_sales_series.csv (3` |
| **Fearnleys Weekly** | Weekly (Wednesday/Thursday) | `2026-10-01` | 0d | **CURRENT (Just Ingested W40 Today)** | 262 PDF, 0 HTML, 0 IMG | [`data/extracted/md/fearnleys`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/fearnleys) | Yes (Tanker spot WS, Dry bulk BDI & TC, LPG/LNG) | `fearnleys_rates_series.csv (14` |
| **Fearnleys-MD (Econometric Research)** | Monthly / Bespoke (Bi-weekly) | `2026-09-30` | 1d | **CURRENT** | 176 PDF, 0 HTML, 2786 IMG | [`data/extracted/md/fearnleys-md`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/fearnleys-md) | Yes (Top 52 econometric recurring lead-indicator models) | `fearnleys_md_master_econometric_series.xlsx (6 sheets` |
| **Intermodal Shipbrokers** | Weekly (Tuesday) | `2026-09-29` | 2d | **CURRENT** | 256 PDF, 0 HTML, 0 IMG | [`data/extracted/md/intermodal`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/intermodal) | Yes (Baltic & Time Charter vector curves, Page 3) | `intermodal_baltic_tc_series.csv (20` |
| **ISM Coasters & Mini-Bulkers** | Weekly (Monday) | `2026-09-28` | 3d | **CURRENT** | 115 PDF, 0 HTML, 0 IMG | [`data/extracted/md/ism`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ism) | Yes (4 weekly freight indicator vector charts) | `ism_handy_freight_series.csv (17` |
| **Lion Shipbrokers** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 46 PDF, 0 HTML, 0 IMG | [`data/extracted/md/lion`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/lion) | No (S&P deals, Demometer indicative ranges, Demo fixtures) | `lion_deals_series.csv (1` |
| **SSY (Simpson Spence Young)** | Weekly (Monday) | `2026-09-28` | 3d | **CURRENT** | 530 PDF, 0 HTML, 0 IMG | [`data/extracted/md/ssy`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ssy) | Yes (Atlantic & Pacific Capesize index vector curves) | `ssy_capesize_index_series.csv (8` |
| **Star Asia Demolition** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 199 PDF, 0 HTML, 0 IMG | [`data/extracted/md/star_asia`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/star_asia) | Yes (Subcontinent scrap price trends $/LDT, metals/energy) | `star_asia_snp_sales_series.csv (3` |
| **Xclusiv Shipbrokers** | Weekly (Monday) | `2026-09-28` | 3d | **CURRENT** | 271 PDF, 0 HTML, 0 IMG | [`data/extracted/md/xclusiv`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/xclusiv) | Yes (Pages 2-3 freight curves, Pages 8-9 bunker spreads) | `xclusiv_secondhand_series.csv (8` |
| **Hellenic: Demolition Market** | Weekly (Saturday/Sunday) | `2026-09-26` | 5d | **CURRENT** | 2134 PDF, 807 HTML, 1208 IMG | [`data/extracted/md/hellenic/demolition`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/demolition) | Yes (Port position queue charts, cash buyer price matrices) | `hellenic_athenian_demolition_series.csv (3` |
| **Hellenic: Dry Bulk Charter (Alibra)** | Weekly (Wednesday) | `2026-09-30` | 1d | **CURRENT** | 0 PDF, 279 HTML, 759 IMG | [`data/extracted/md/hellenic/dry_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/dry_charter) | Yes (Alibra rate fixture comparison graphics) | `hellenic_alibra_dry_tc_series.csv (6` |
| **Hellenic: Iron Ore (MMI & SMM Daily)** | Daily (Mon-Fri) | `2026-09-30` | 1d | **CURRENT (Golden Week pause Oct 1-7)** | 4519 PDF, 1200 HTML, 3335 IMG | [`data/extracted/md/hellenic/iron_ore_pdf`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore_pdf) | Yes (4 SMM driver vector charts + MMi inventory/margin curves) | `hellenic_iron_ore_pdf_brands_series.csv (31,470 rows, 21 CSVs)` |
| **Hellenic: Shipbuilding & Contracting** | Weekly (Friday) | `2026-09-29` | 2d | **CURRENT** | 1352 PDF, 379 HTML, 180 IMG | [`data/extracted/md/hellenic/shipbuilding`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/shipbuilding) | No (Shipyard contracting and orderbook tables) | `clarksons_sales_series.csv (merged)` |
| **Hellenic: Tanker Time Charter (Alibra)** | Weekly (Wednesday) | `2026-09-30` | 1d | **CURRENT** | 0 PDF, 278 HTML, 757 IMG | [`data/extracted/md/hellenic/tanker_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/tanker_charter) | Yes (Crude & clean period earnings comparison graphics) | `hellenic_alibra_tanker_tc_series.csv (7` |
| **Hellenic: VesselsValue Valuations** | Weekly (Tuesday) | `2026-09-29` | 2d | **CURRENT** | 0 PDF, 274 HTML, 726 IMG | [`data/extracted/md/hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/vessel_valuations) | Yes (VesselsValue fleet valuation index graphs) | `hellenic_vv_matrix_series.csv (12` |
| **Breakwave Advisors** | Weekly (Tuesday) & Daily Insights | `2026-09-29` | 2d | **CURRENT** | 304 PDF, 3236 HTML, 15072 IMG | [`data/extracted/md/breakwave`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/breakwave) | Yes (Dry bulk freight fundamentals & ETF price trajectories) | `breakwave_fundamentals_series.csv (2` |
| **Poten & Partners (Tanker Opinions)** | Weekly (Friday) | `2026-09-18` | 13d | **NORMAL INTERVAL (Week 39 due)** | 1087 PDF, 0 HTML, 0 IMG | [`data/extracted/md/poten`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/poten) | Yes (Top Charterers annual/biannual volume rankings) | `poten_opinions_metadata.csv (1` |
| **Seabrokers (Seabreeze Monthly Offshore)** | Monthly (1st of Month) | `2026-08-01` | 61d | **NORMAL INTERVAL (Published with 3-4 week lag, Sep edition covers Aug)** | 97 PDF, 0 HTML, 0 IMG | [`data/extracted/md/seabrokers`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/seabrokers) | Yes (OSV utilisation curves, rig dayrates, offshore wind) | `seabrokers_osv_monthly_history_series.csv (6` |
| **Drewry Maritime AIS Fleet Performance** | Weekly (Tuesday) | `2026-09-24` | 7d | **CURRENT (Ingested up to Week 39 across DAM 034)** | 288 PDF, 0 HTML, 0 IMG | [`data/extracted/md/drewry/ais`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais) | Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds) | `drewry_ais_fleet_performance_series.csv (14` |
| **Drewry Opinions & World Container Index (WCI)** | Weekly (Thursday) | `2026-09-24` | 7d | **CURRENT (Assessed Thursdays)** | 0 PDF, 0 HTML, 0 IMG | [`data/extracted/md/drewry/opinions`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/opinions) | Yes (Global container freight rate time series) | `drewry_wci_historical.csv (122 weekly rows` |
| **Signal Ocean (Fleet Telemetry & Monitors)** | Weekly (Friday) & Live Telemetry | `2026-09-24` | 7d | **CURRENT** | 10 PDF, 515 HTML, 1885 IMG | [`data/extracted/md/signal`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/signal) | Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps) | `signal_reports_metadata.csv (446 rows)` |
| **Baltic Exchange Weekly** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 0 PDF, 3043 HTML, 0 IMG | [`data/extracted/md/baltic`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/baltic) | No (Detailed fixture narratives and route earnings) | `baltic_reports_metadata.csv (2` |
| **Pilbara Ports Authority (PPA)** | Monthly (20th of Month) | `2026-07-28` | 65d | **NORMAL INTERVAL (August throughput figures published late Sep/early Oct)** | 493 PDF, 0 HTML, 0 IMG | [`data/commodities`](file:///C:/Users/Dell/Github/Shipping/data/commodities) | No (Port Hedland & Dampier iron ore export tonnage tables) | `australia_ppa_iron_ore.csv (424 rows` |

---

## 3. Granular Sub-Sector, Vessel Class & Fleet Breakdown

This section details document volumes, vessel classes, numerical metric coverage, and extraction scripts across complex composite publishers.

### 3.1 Drewry Maritime AIS Fleet Performance (10 Discrete Vessel Classes)

Drewry AIS reports are published across 10 specialized maritime vessel classes. The pipeline extracts executive KPIs, fleet utilisation curves, bunker consumption indicators, and port congestion indices without OCR noise:

| Vessel Class / Sector | Report Count in Corpus | Typical Deadweight / CBM | Analytical Metrics Extracted | Master Series Target CSV | Extracted Data Volume | Processing Script |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **Capesize (180,000 DWT)** | `27 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Port Hedland/Tubarao delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Panamax / Kamsarmax (82,000 DWT)** | `23 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Santos/Mississippi delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Supramax / Ultramax (64,000 DWT)** | `23 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Indonesian coal delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Handysize (38,000 DWT)** | `25 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, minor bulk port queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **VLCC (300,000 DWT)** | `32 weekly PDFs` | PDF vector | Crude utilisation %, tonne-miles, Ras Tanura/Ningbo congestion, ballast speed | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Suezmax (160,000 DWT)** | `30 weekly PDFs` | PDF vector | Crude utilisation %, tonne-miles, West Africa/Mediterranean queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Aframax (115,000 DWT)** | `31 weekly PDFs` | PDF vector | Dirty utilisation %, tonne-miles, North Sea/Baltic/Caribs queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Product LR2 (115,000 DWT)** | `31 weekly PDFs` | PDF vector | Clean product utilisation %, tonne-miles, MEG-East product flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Product LR1 (75,000 DWT)** | `34 weekly PDFs` | PDF vector | Clean product utilisation %, tonne-miles, regional refinery flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **LPG Carrier (84,000 CBM VLGC)** | `32 weekly PDFs` | PDF vector | LPG carrier utilisation %, tonne-miles, US Gulf/Ras Laffan flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Regional Port Congestion (All Classes)** | `288 reports` | PDF vector curves | Port waiting days & congestion indexes across China, AG, USG, Aus, Bra | `drewry_ais_regional_congestion_series.csv` | **6,792 rows** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Deployment & Ballast Speeds (All Classes)** | `288 reports` | PDF vector curves | Laden vs ballast cruising speed knots by vessel class and region | `drewry_ais_deployment_speed_series.csv` | **2,427 rows** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Capacity Utilisation Curves (All Classes)** | `288 reports` | PDF vector curves | Multi-year historical utilisation curves (2020-2026) | `drewry_ais_utilisation_curves_series.csv` | **1,007 rows** | [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |

### 3.2 Hellenic Shipping News Multi-Category Sub-Sources

| Category / Sub-Source | Sub-Broker / Segment | Report Count | Format | Commercial Intelligence Extracted | Master Series CSV | Total Data Rows | Processing Script |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **Hellenic Demolition** | Athenian Shipbrokers Cash Buyer | `1,272 reports` | HTML / PDF | Scrap indicative prices ($/LDT) for Bangladesh, India, Pakistan, Turkey | `hellenic_athenian_demolition_series.csv` | **3,052 rows** | [`run_athenian_demolition.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_athenian_demolition.py) |
| **Hellenic Demolition** | GMS Weekly Recycler Insights & Deals | `1,272 reports` | HTML / PDF | Cash buyer commentary, scrap sentiment, fixture deals | `hellenic_gms_demolition_series.csv` | **1,092 rows** | [`run_gms_demolition.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_gms_demolition.py) |
| **Hellenic Demolition** | GMS Port Position Queues | `1,272 reports` | HTML tables / Images | Cash buyer port arrivals, beaching positions, tonnage queued | `hellenic_gms_port_positions_series.csv` | **2,905 rows** | [`run_gms_demolition.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_gms_demolition.py) |
| **Hellenic Demolition** | Best Oasis Scrap Assessments & Deals | `1,272 reports` | HTML / PDF | Subcontinent scrap rates and beaching transaction fixtures | `hellenic_best_oasis_deals_series.csv` | **882 rows (deals), 859 rows (rates)** | [`run_best_oasis_demolition.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_best_oasis_demolition.py) |
| **Hellenic Dry Charter** | Alibra Dry Bulk Time Charter Estimates | `266 reports` | HTML / Images | 1Y, 2Y, 3Y, 5Y period TC ($/day) for Capesize, Kamsarmax, Ultramax, Handy | `hellenic_alibra_dry_tc_series.csv` | **6,443 rows** | [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py) |
| **Hellenic Tanker Charter** | Alibra Tanker Time Charter Estimates | `265 reports` | HTML / Images | 1Y, 2Y, 3Y, 5Y period TC ($/day) for VLCC, Suezmax, Aframax, LR2, LR1, MR | `hellenic_alibra_tanker_tc_series.csv` | **7,177 rows** | [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py) |
| **Hellenic Iron Ore** | MMI Daily Brand Price Assessments | `4,519 PDFs` | PDF tabular | 31+ brand prices $/dmtu (PB Fines, Newman, Carajas, Lump/Pellet premiums) | `hellenic_iron_ore_pdf_brands_series.csv` | **31,470 rows** | [`run_hellenic_iron_ore_pdf.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) |
| **Hellenic Iron Ore** | SMM Daily Spot Iron Ore Benchmark & New Layout | `4,519 PDFs` | PDF structured | 62% Fe CFR China benchmark, Key View editorial, futures, and driver charts | `hellenic_iron_ore_daily_series.csv` | **1,175 rows (36 cols)** | [`run_smm_iron_ore_daily.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_smm_iron_ore_daily.py) |
| **Hellenic Iron Ore** | Baltic Capesize C3 / C5 Freight Rates | `4,519 PDFs` | PDF tabular | Tubarao-Qingdao (C3) & Dampier-Qingdao (C5) freight $/ton | `hellenic_iron_ore_pdf_freight_rates_series.csv` | **22,257 rows** | [`run_hellenic_iron_ore_pdf.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) |
| **Hellenic Valuations** | VesselsValue Secondhand Valuation Matrix | `261 reports` | HTML tables / Images | Resale, 5Y, 10Y, 15Y, 20Y values ($M) for Bulkers, Tankers, Containers | `hellenic_vv_matrix_series.csv` | **12,340 rows** | [`run_hellenic_vv_matrix.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_vv_matrix.py) |
| **Hellenic Valuations** | VesselsValue Secondhand Sales Deals | `261 reports` | HTML tables | Reported S&P transactions with vessel name, DWT, built, yard, price $M | `hellenic_vv_sales_series.csv` | **2,122 rows** | [`run_hellenic_vessel_valuations.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_vessel_valuations.py) |

### 3.3 Shipbroker Intelligence Discrete Series & Econometric Models

| Publisher | Intelligence Domain | Document Volume | Format | Core Analytical Payload | Master Series CSV / Destination | Stored Volume | Processing Script |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **SSY Simpson Spence Young** | Atlantic Capesize Index (ACI) & Pacific (PCI) | `530 reports` | PDF tabular | Atlantic & Pacific Capesize voyage rate indices & iron ore haul routes | `data/indices/ (display-linked)` | **Continuous weekly indices** | [`run_ssy_complete.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_ssy_complete.py) |
| **Fearnleys Weekly** | 6-Pillar Weekly Market Intelligence | `526 reports` | PDF structured | Crude/Product tankers, Dry Bulk, Gas, Newbuilding, S&P, Macro | `data/extracted/series/ (normalized rate cards)` | **526 issues cover-to-cover** | [`run_fearnleys_normalized.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_fearnleys_normalized.py) |
| **Fearnleys Econometric** | 26 Lead-Indicator Econometric Models | `26 models` | Vector charts / Excel | Copper vs Supramax, Coal curve vs P5, Iron Ore vs 5TC, S&P vs 1Y TC | `fearnleys_md_master_econometric_series.xlsx` | **26 workbook sheets** | [`export_fearnleys_md_excel.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/export_fearnleys_md_excel.py) |
| **Poten & Partners** | Tanker Opinions & Top Charterers Series | `1,087 reports` | PDF full text | Narrative essays + 2005-2026 Top Dirty Spot Charterer annual volume rankings | `poten_top_charterers_series.csv` | **755 rows (charterers), 1,087 rows (metadata)** | [`run_poten.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_poten.py) |
| **Seabrokers Seascope** | Offshore Support Vessels, Rigs & Subsea | `97 reports` | PDF monthly | North Sea OSV dayrates, rig utilization %, subsea & offshore wind | `seabrokers_osv_monthly_history_series.csv` | **15,430 rows across 9 series** | [`run_seabrokers_llamaparse.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_seabrokers_llamaparse.py) |
| **Signal Ocean** | Weekly Monitors, Research & Live Fleet | `515 reports` | HTML / Telemetry | Dry & tanker weekly monitors, trade flows, live fleet positions & queues | `signal_reports_metadata.csv` | **446 rows + live JSON views** | [`run_signal.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_signal.py) |
| **Xclusiv Shipbrokers** | Comprehensive Tabular Market Intelligence | `271 reports` | PDF tables (9 pages) | S&P sales, scrap deals, secondhand matrix, newbuilding orders | `xclusiv_sales_series.csv` | **17,737 rows across 5 series** | [`run_xclusiv_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_xclusiv_tables.py) |
| **Advanced Shipping** | S&P, Secondhand Matrices, Demo & NB | `253 reports` | PDF tables (10 pages) | S&P sales, demolition rates & deals, secondhand valuation matrix | `advanced_shipping_sales_series.csv` | **18,744 rows across 5 series** | [`run_advanced_shipping_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_advanced_shipping_tables.py) |
| **Banchero Costa** | S&P Deals with IMO Numbers & Newbuilding | `243 reports` | PDF tables / LlamaParse | S&P deals with verified 7-digit IMO numbers, newbuilding orders & prices | `bancosta_sales_series.csv` | **5,043 rows across 3 series** | [`run_banchero_costa_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_banchero_costa_tables.py) |
| **Intermodal** | Secondhand S&P, Newbuilding, Scrap & Baltic | `256 reports` | PDF tables / Vector | Secondhand sales, newbuilding, scrap $/LDT, Page 3 Baltic curves | `intermodal_baltic_tc_series.csv` | **20,348 rows across series** | [`run_intermodal_full.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_intermodal_full.py) |
| **Drewry WCI** | World Container Index (WCI) Freight Benchmarks | `122 weekly rows` | HTML / Wayback CDX | 8 major east-west route benchmarks + composite index $/FEU | `drewry_wci_historical.csv` | **122 weekly rows (display-linked)** | [`fetch_drewry_wci.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/fetch_drewry_wci.py) |
| **Pilbara Ports Authority** | Port Hedland & Dampier Iron Ore Export Throughput | `493 reports` | PDF tables | Monthly export tonnage, destination country breakdowns (China, Japan, Korea) | `australia_ppa_iron_ore.csv` | **424 monthly rows (display-linked)** | [`run_ppa.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_ppa.py) |

---

## 4. Comprehensive Image & Graphic Extraction Audit

This table tracks sectors where the pipeline inspects and extracts numerical data from images, raster graphics, or vector drawings:

| Source Category | Image Count in Corpus | Image Types | Analytical Pipeline Applied | Extracted Data Output |
| :--- | :---: | :--- | :--- | :--- |
| **01-brokers/fearnleys-md** | 2,786 | 200 DPI vector PNG clips, JPG | Dynamic row-wise affine scale regression ($R^2 \ge 0.999$) | 26 econometric lead-indicator sheets in `fearnleys_md_master_econometric_series.xlsx` |
| **01-brokers/ism** | Vector stream | PDF internal vector polylines | Least-squares dual-axis scale calibration & tick filtering | 4 weekly freight rate series (`ism_handy_freight_series.csv`, `ism_coaster_freight_series.csv`) |
| **01-brokers/intermodal** | Vector stream | Page 3 vector drawing paths | Polyline vertex extraction matching Baltic dry & TC curves | `intermodal_baltic_tc_series.csv` (20,348 rows) |
| **01-brokers/star_asia** | Vector stream | Drawing paths & bar charts | Subcontinent scrap price trend calibration ($/LDT) | `star_asia_scrap_price_trends_series.csv` (347 rows) |
| **02-hellenic/iron_ore** | 3,335 | JPG / PNG port inventory graphics | OCR & spatial coordinate table extraction | `hellenic_iron_ore_pdf_brands_series.csv` (31,272 rows) |
| **02-hellenic/demolition** | 1,208 | Cash buyer market insight graphics | HTML table extraction + OCR fallback | `hellenic_gms_port_positions_series.csv` (2,905 rows) |
| **02-hellenic/dry_charter** | 759 | Alibra Dry Bulk TC rate graphics | Graphic OCR & tabular parameter parsing | `hellenic_alibra_dry_tc_series.csv` (6,467 rows) |
| **02-hellenic/tanker_charter** | 757 | Alibra Tanker TC rate graphics | Graphic OCR & tabular parameter parsing | `hellenic_alibra_tanker_tc_series.csv` (7,191 rows) |
| **02-hellenic/vessel_valuations** | 726 | VesselsValue asset price charts | Asset valuation curve digitizer & matrix builder | `hellenic_vv_matrix_series.csv` (12,340 rows) |
| **03-breakwave** | 15,072 | Freight market fundamentals PNGs | BDRY/BWET index trajectory curves & fundamental commentary | `breakwave_fundamentals_series.csv` (2,746 rows) |
| **07-signal** | 1,885 | Flow heatmaps & trade monitors | Live telemetry pipeline & monitor digest parser | `signal_reports_metadata.csv` (442 rows) |

---

## 5. Detailed Sector Dossiers & Verification Links

### Advanced Shipping & Trading
- **Corpus Directory:** [`corpus/01-brokers/advanced_shipping`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/advanced_shipping)
- **Markdown Output:** [`data/extracted/md/advanced_shipping`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/advanced_shipping)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-06-25` to `2026-09-25`
- **Latest Ingested Document:** `advanced_shipping_26_09_2026_advanced_shipping_trading_weekly_shipping_marke.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 253 PDFs, 0 HTML files, 0 Images, 253 Markdown files
- **Chart Extraction:** Yes (Secondhand valuation matrices & demo trends)
- **Chart Engine / Technique:** Native coordinate grid & affine scale parser
- **Stacked Series CSVs:** advanced_shipping_sales_series.csv (6,105 rows), advanced_shipping_demolition_series.csv (2,016 rows), advanced_shipping_secondhand_matrix_series.csv (8,110 rows), advanced_shipping_newbuilding_series.csv (1,909 rows), advanced_shipping_demo_sales_series.csv (604 rows)
- **Extraction Script:** [`run_advanced_shipping_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_advanced_shipping_tables.py)
- **Notes & Rules Applied:** Last 3 pages discarded per parsing rules (currencies/stocks). European comma/dot decimals normalized.

### Affinity Shipbrokers
- **Corpus Directory:** [`corpus/01-brokers/affinity`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/affinity)
- **Markdown Output:** [`data/extracted/md/affinity`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/affinity)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-10-01` to `2026-09-25`
- **Latest Ingested Document:** `affinity_26_09_2026_affinity_tanker_weekly_25_september_2026.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 254 PDFs, 0 HTML files, 0 Images, 254 Markdown files
- **Chart Extraction:** Yes (Baltic Dirty & Clean TCE trajectory curves)
- **Chart Engine / Technique:** Native PyMuPDF card layout geometry
- **Stacked Series CSVs:** affinity_tce_series.csv (4,039 rows), affinity_bda_series.csv (744 rows), affinity_indices_series.csv (490 rows)
- **Extraction Script:** [`run_affinity_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_affinity_tables.py)
- **Notes & Rules Applied:** Handles negative TCE rates (e.g. TC2 -$4,273). Full tanker commentary preserved.

### Agora Shipbroking
- **Corpus Directory:** [`corpus/01-brokers/agora`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/agora)
- **Markdown Output:** [`data/extracted/md/agora`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/agora)
- **Publication Cadence:** Weekly (Wednesday/Thursday) (Expected day: Wednesday)
- **Coverage Span:** `2021-06-25` to `2026-09-30`
- **Latest Ingested Document:** `agora_30_09_2026_agora_shipbroking_corporation_snapshot_of_commercial_indicator.pdf` (Status: **CURRENT (Just Ingested W39)**)
- **Inventory by Format:** 216 PDFs, 0 HTML files, 0 Images, 216 Markdown files
- **Chart Extraction:** No (Dense indicator tables across 5 pages)
- **Chart Engine / Technique:** Native layout block parser
- **Stacked Series CSVs:** agora_indicators_series.csv (10,002 rows)
- **Extraction Script:** [`format_agora_properly.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/format_agora_properly.py)
- **Notes & Rules Applied:** Parsed live right now for Week 39 (24 Sep reference). European decimals normalized.

### Banchero Costa (Bancosta)
- **Corpus Directory:** [`corpus/01-brokers/banchero_costa`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/banchero_costa)
- **Markdown Output:** [`data/extracted/md/banchero_costa`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/banchero_costa)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2021-06-30` to `2026-09-30`
- **Latest Ingested Document:** `bancosta_30_09_2026_banchero_costa_weekly_market_report_week_39_2026.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 247 PDFs, 0 HTML files, 0 Images, 252 Markdown files
- **Chart Extraction:** Yes (Freight rates, FFA forward curves, ConTex index)
- **Chart Engine / Technique:** Native PyMuPDF table parser (Zero LlamaParse cost for ongoing)
- **Stacked Series CSVs:** bancosta_freight_rates_series.csv (20,321 rows), bancosta_ffa_series.csv (7,618 rows), bancosta_sales_series.csv (4,591 rows), bancosta_commodities_series.csv (8,447 rows), bancosta_newbuilding_series.csv (1,952 rows), bancosta_secondhand_matrix_series.csv (1,911 rows), bancosta_demolition_series.csv (1,288 rows)
- **Extraction Script:** [`run_banchero_costa_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_banchero_costa_tables.py)
- **Notes & Rules Applied:** Extracts exact 7-digit IMO numbers on secondhand vessel transactions. Pages 2 to N-1 parsed.

### Carriers Chartering (General Broker)
- **Corpus Directory:** [`corpus/01-brokers/carriers`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/carriers)
- **Markdown Output:** [`data/extracted/md/carriers`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/carriers)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-11-19` to `2026-09-28`
- **Latest Ingested Document:** `general_broker_28_09_2026_carriers_sales_purchase_market_report_week_39.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 136 PDFs, 0 HTML files, 0 Images, 137 Markdown files
- **Chart Extraction:** No (Tabular S&P and Baltic BSPA/BDA indices)
- **Chart Engine / Technique:** Native word geometry and dynamic anchor parser
- **Stacked Series CSVs:** carriers_sales_series.csv (3,004 rows), carriers_dry_tc_period_series.csv (3,072 rows), carriers_indices_series.csv (1,792 rows), carriers_tanker_tce_series.csv (768 rows), carriers_bspa_series.csv (713 rows), carriers_newbuilding_series.csv (301 rows), carriers_demolition_series.csv (171 rows)
- **Extraction Script:** [`run_carriers_complete.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_carriers_complete.py)
- **Notes & Rules Applied:** Greek public equities & daily quote stripped per rules. En bloc sister-ship prices handled.

### Clarksons / Clarksons Hellas
- **Corpus Directory:** [`corpus/01-brokers/clarksons`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/clarksons)
- **Markdown Output:** [`data/extracted/md/clarksons`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/clarksons)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-07-02` to `2026-09-25`
- **Latest Ingested Document:** `clarksons_25_09_2026_clarksons_hellas_snp_weekly.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 180 PDFs, 0 HTML files, 0 Images, 180 Markdown files
- **Chart Extraction:** No (Bulker & Tanker reported sales transaction tables)
- **Chart Engine / Technique:** Native PyMuPDF table coordinate extractor
- **Stacked Series CSVs:** clarksons_sales_series.csv (3,920 rows)
- **Extraction Script:** [`run_clarksons.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_clarksons.py)
- **Notes & Rules Applied:** Deduplicated against duplicate uploads on Hellenic portal.

### Fearnleys Weekly
- **Corpus Directory:** [`corpus/01-brokers/fearnleys`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/fearnleys)
- **Markdown Output:** [`data/extracted/md/fearnleys`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/fearnleys)
- **Publication Cadence:** Weekly (Wednesday/Thursday) (Expected day: Wednesday)
- **Coverage Span:** `2021-07-07` to `2026-10-01`
- **Latest Ingested Document:** `fearnleys_01_10_2026_fearnleys_week_40_2026.pdf` (Status: **CURRENT (Just Ingested W40 Today)**)
- **Inventory by Format:** 262 PDFs, 0 HTML files, 0 Images, 523 Markdown files
- **Chart Extraction:** Yes (Tanker spot WS, Dry bulk BDI & TC, LPG/LNG)
- **Chart Engine / Technique:** Specialized 6-pillar normalized parser (run_fearnleys_normalized.py)
- **Stacked Series CSVs:** fearnleys_rates_series.csv (14,669 rows)
- **Extraction Script:** [`run_fearnleys_normalized.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_fearnleys_normalized.py)
- **Notes & Rules Applied:** Ingested live today for Week 40 (Sep 30 date). Formatted with 6 distinct pillars.

### Fearnleys-MD (Econometric Research)
- **Corpus Directory:** [`corpus/01-brokers/fearnleys-md`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/fearnleys-md)
- **Markdown Output:** [`data/extracted/md/fearnleys-md`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/fearnleys-md)
- **Publication Cadence:** Monthly / Bespoke (Bi-weekly) (Expected day: Ad-hoc)
- **Coverage Span:** `2024-03-25` to `2026-09-30`
- **Latest Ingested Document:** `2026-09-30_fearnleys-dry-bulk-market-outlook-august-2026-6.md` (Status: **CURRENT**)
- **Inventory by Format:** 176 PDFs, 0 HTML files, 2786 Images, 182 Markdown files
- **Chart Extraction:** Yes (Top 52 econometric recurring lead-indicator models)
- **Chart Engine / Technique:** Proprietary Dynamic Affine Calibration Engine (R^2 >= 0.999)
- **Stacked Series CSVs:** fearnleys_md_master_econometric_series.xlsx (6 sheets, 26 lead models), fearnleys_md_vessel_tightness_series.csv (109 rows), fearnleys_md_macro_correlations_series.csv (78 rows), fearnleys_md_coal_futures_spread_series.csv (46 rows)
- **Extraction Script:** [`run_fearnleys_md_full_power.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_fearnleys_md_full_power.py)
- **Notes & Rules Applied:** 2,786 high-res vector charts extracted and calibrated. First/last pages discarded per rule.

### Intermodal Shipbrokers
- **Corpus Directory:** [`corpus/01-brokers/intermodal`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/intermodal)
- **Markdown Output:** [`data/extracted/md/intermodal`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/intermodal)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2021-06-29` to `2026-09-29`
- **Latest Ingested Document:** `intermodal_30_09_2026_intermodal_weekly_market_report_week_39_2026_broker_s_insi.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 256 PDFs, 0 HTML files, 0 Images, 256 Markdown files
- **Chart Extraction:** Yes (Baltic & Time Charter vector curves, Page 3)
- **Chart Engine / Technique:** LlamaParse cover-to-cover + PyMuPDF chart vector curves
- **Stacked Series CSVs:** intermodal_baltic_tc_series.csv (20,348 rows), intermodal_tc_rates_series.csv (5,100 rows), intermodal_newbuilding_series.csv (5,058 rows), intermodal_tanker_spot_series.csv (3,879 rows), intermodal_sales_series.csv (3,358 rows), intermodal_demolition_series.csv (2,629 rows)
- **Extraction Script:** [`run_intermodal_full.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_intermodal_full.py)
- **Notes & Rules Applied:** 100% cover-to-cover extraction (all 8 pages). Editorial essay, Tanker spot, Dry bulk TC, S&P, NB, Demo. Audited and verified TC Rates table multi-row structure and Indicative Market Values column alignment.

### ISM Coasters & Mini-Bulkers
- **Corpus Directory:** [`corpus/01-brokers/ism`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/ism)
- **Markdown Output:** [`data/extracted/md/ism`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ism)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-05` to `2026-09-28`
- **Latest Ingested Document:** `ism_28_09_2026_ism_coasters_and_mini_bulkers_week_39.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 115 PDFs, 0 HTML files, 0 Images, 230 Markdown files
- **Chart Extraction:** Yes (4 weekly freight indicator vector charts)
- **Chart Engine / Technique:** PyMuPDF drawing path & polyline axis scale calibration
- **Stacked Series CSVs:** ism_handy_freight_series.csv (17,629 rows), ism_coaster_freight_series.csv (12,319 rows)
- **Extraction Script:** [`run_ism.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_ism.py)
- **Notes & Rules Applied:** Overhauled to eliminate vertical axis tick number chains. Clean commentary under thematic subheaders.

### Lion Shipbrokers
- **Corpus Directory:** [`corpus/01-brokers/lion`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/lion)
- **Markdown Output:** [`data/extracted/md/lion`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/lion)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-07-09` to `2026-09-25`
- **Latest Ingested Document:** `lion_2026_W39_Lion-Weekly-Report-25-September-2026-W39.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 46 PDFs, 0 HTML files, 0 Images, 47 Markdown files
- **Chart Extraction:** No (S&P deals, Demometer indicative ranges, Demo fixtures)
- **Chart Engine / Technique:** LiteParse in-process layout parser
- **Stacked Series CSVs:** lion_deals_series.csv (1,212 rows), lion_sales_series.csv (1,109 rows), lion_demometer_series.csv (540 rows), lion_demolition_series.csv (516 rows), lion_demo_sales_series.csv (103 rows)
- **Extraction Script:** [`run_lion_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_lion_tables.py)
- **Notes & Rules Applied:** Joke of the week, author commentary preserved. Disclaimers and contact cards stripped.

### SSY (Simpson Spence Young)
- **Corpus Directory:** [`corpus/01-brokers/ssy`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/ssy)
- **Markdown Output:** [`data/extracted/md/ssy`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ssy)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-05` to `2026-09-28`
- **Latest Ingested Document:** `ssy_28_09_2026_ssy_pacific_capesize_index_28_september_2026.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 530 PDFs, 0 HTML files, 0 Images, 531 Markdown files
- **Chart Extraction:** Yes (Atlantic & Pacific Capesize index vector curves)
- **Chart Engine / Technique:** PyMuPDF span geometry + vector chart calibration
- **Stacked Series CSVs:** ssy_capesize_index_series.csv (8,881 rows), ssy_capesize_series.csv (8,881 rows), ssy_route_rates_series.csv (5,190 rows), ssy_capesize_index_time_series.csv (519 rows)
- **Extraction Script:** [`run_ssy_complete.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_ssy_complete.py)
- **Notes & Rules Applied:** Covers both Atlantic Capesize Index (ACI) and Pacific Capesize Index (PCI).

### Star Asia Demolition
- **Corpus Directory:** [`corpus/01-brokers/star_asia`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/star_asia)
- **Markdown Output:** [`data/extracted/md/star_asia`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/star_asia)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2022-07-22` to `2026-09-25`
- **Latest Ingested Document:** `star_asia_28_09_2026_star_asia_shipbroking_weekly_market_report_week_39.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 199 PDFs, 0 HTML files, 0 Images, 200 Markdown files
- **Chart Extraction:** Yes (Subcontinent scrap price trends $/LDT, metals/energy)
- **Chart Engine / Technique:** LlamaParse + World-Class Markdown Normalizer (run_star_asia_tables.py)
- **Stacked Series CSVs:** star_asia_snp_sales_series.csv (3,717 rows), star_asia_deals_series.csv (3,327 rows), star_asia_valuation_matrix_series.csv (3,245 rows), star_asia_demolition_series.csv (3,072 rows), star_asia_metals_energy_series.csv (1,327 rows)
- **Extraction Script:** [`run_star_asia_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_star_asia_tables.py)
- **Notes & Rules Applied:** Gaddani / Turkey cell boundary merge defect resolved. Explicit ISO issue dates stamped. Uniform sector subheader bolding (**Capesize:**, **Panamax/Kamsarmax:**, **Supramax/Ultramax:**, **Handysize:**) verified across all 198 reports.

### Xclusiv Shipbrokers
- **Corpus Directory:** [`corpus/01-brokers/xclusiv`](file:///C:/Users/Dell/Github/Shipping/corpus/01-brokers/xclusiv)
- **Markdown Output:** [`data/extracted/md/xclusiv`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/xclusiv)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-26` to `2026-09-28`
- **Latest Ingested Document:** `xclusiv_29_09_2026_xclusiv_shipbrokers_weekly_28th_september_2026.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 271 PDFs, 0 HTML files, 0 Images, 271 Markdown files
- **Chart Extraction:** Yes (Pages 2-3 freight curves, Pages 8-9 bunker spreads)
- **Chart Engine / Technique:** LiteParse cover-to-cover + vector chart parser
- **Stacked Series CSVs:** xclusiv_secondhand_series.csv (8,593 rows), xclusiv_sales_series.csv (5,713 rows), xclusiv_demolition_series.csv (2,098 rows), xclusiv_newbuilding_prices_series.csv (1,397 rows), xclusiv_newbuilding_orders_series.csv (1,329 rows)
- **Extraction Script:** [`run_xclusiv_tables.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_xclusiv_tables.py)
- **Notes & Rules Applied:** 100% cover-to-cover across all 9 pages. Full narrative commentary (Capesize, Panamax, Supramax, Handysize, VLCC, Suezmax, Aframax, Products) and S&P tables extracted. Left-column commentary boundary calibrated to strip chart axis tick noise.

### Hellenic: Demolition Market
- **Corpus Directory:** [`corpus/02-hellenic/demolition`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/demolition)
- **Markdown Output:** [`data/extracted/md/hellenic/demolition`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/demolition)
- **Publication Cadence:** Weekly (Saturday/Sunday) (Expected day: Saturday)
- **Coverage Span:** `2014-03-28` to `2026-09-26`
- **Latest Ingested Document:** `gms_2026-09-25_2026-09-26_gms-week-39-earnings-roar-supply-retreat_Ship-recycling-market-insight-Week-39-09-25-2026-Rates-Soar-Hulls-Stay.html` (Status: **CURRENT**)
- **Inventory by Format:** 2134 PDFs, 807 HTML files, 1208 Images, 1272 Markdown files
- **Chart Extraction:** Yes (Port position queue charts, cash buyer price matrices)
- **Chart Engine / Technique:** BeautifulSoup HTML + PyMuPDF spatial coordinate table parser
- **Stacked Series CSVs:** hellenic_athenian_demolition_series.csv (3,052 rows), hellenic_gms_port_positions_series.csv (2,905 rows), hellenic_gms_demolition_series.csv (1,092 rows), hellenic_best_oasis_deals_series.csv (882 rows), hellenic_best_oasis_demolition_series.csv (859 rows)
- **Extraction Script:** [`run_hellenic_demolition.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_demolition.py)
- **Notes & Rules Applied:** Distinguishes Athenian, Best Oasis, GMS cash buyer reports and port queue tables.

### Hellenic: Dry Bulk Charter (Alibra)
- **Corpus Directory:** [`corpus/02-hellenic/dry_charter`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/dry_charter)
- **Markdown Output:** [`data/extracted/md/hellenic/dry_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/dry_charter)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2014-03-28` to `2026-09-30`
- **Latest Ingested Document:** `2026-09-30_weekly-dry-time-charter-estimates-september-30-2026.html` (Status: **CURRENT**)
- **Inventory by Format:** 0 PDFs, 279 HTML files, 759 Images, 266 Markdown files
- **Chart Extraction:** Yes (Alibra rate fixture comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_dry_tc_series.csv (6,443 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Dry Bulk period TC assessments across Capesize, Panamax, Supramax, Handy.

### Hellenic: Iron Ore (MMI Daily HTML & PDF)
- **Corpus Directory:** [`corpus/02-hellenic/iron_ore`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/iron_ore) (HTML web previews) & [`corpus/02-hellenic/iron_ore/pdfs`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/iron_ore/pdfs) (Ground truth authoritative PDFs)
- **Markdown Output:** [`data/extracted/md/hellenic/iron_ore_pdf`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore_pdf) (1,188 full-fidelity PDF markdown files with `.tables.json` sidecars) & [`data/extracted/md/hellenic/iron_ore`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore) (HTML web summaries)
- **Publication Cadence:** Daily (Mon-Fri) (Expected day: Daily)
- **Coverage Span:** `2014-03-28` to `2026-09-30` (Unbroken continuous history)
- **Latest Ingested Document:** `2026-09-30_mmi-daily-iron-ore-index-report-septembe_MMi-Daily-Iron-Ore-Report-for-30th-September-2026.pdf` (Status: **CURRENT (Final issue before Golden Week National Day holiday Oct 1-7)**)
- **Inventory by Format:** 4,519 PDFs, 1,200 HTML files, 3,335 Images, 4,725 Markdown files across HTML and PDF tiers
- **Chart Extraction:** Yes (High-resolution 200 DPI vector clips for Ocean Freight, Port Inventories at 10 & 35 ports, Hot Metal BF output, and Global Shipments vs Chinese Port Arrivals)
- **Chart Engine / Technique:** PyMuPDF 2D spatial coordinate parser + SMM vector chart bounding-box clipper (`data/extracted/charts/hellenic_iron_ore/<issue_date>/`)
- **Extraction Scripts (Dual-Pipeline Architecture):**
  - **Pipeline A (Historical 6-Page MMi PDFs):** [`run_hellenic_iron_ore_pdf.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) — Parses all 6 pages cover-to-cover (Dashboard, MMi Benchmark Price Indices, Chinese Domestic Concentrates, 31 Brand Spot Assessments, Port Differentials, Futures, Freight, Port Stocks, Steel Spot Prices, Mill Profitability, and Specifications).
  - **Pipeline B (New 1-Page SMM Daily PDFs, mid-Sept 2026+):** [`run_smm_iron_ore_daily.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_smm_iron_ore_daily.py) — Parses the redesigned Shanghai Metals Market layout (Futures Contracts, Physical & Seaborne Indices, Key View editorial narrative, Today's Highlights, Qingdao Port Spot CNY, Imported Ore USD prices, SMM Stats, 4 Price Driver vector charts, and Market Commentary).
- **Stacked Master Series CSVs (21 CSVs, 200,000+ data rows, 2021-07-14 to 2026-09-30):**
  - `hellenic_iron_ore_pdf_brands_series.csv` (31,470 rows) — 31+ brand spot prices (PB Fines, Newman, Carajas, MAC, SSF, BRBF, Lump/Pellet premiums)
  - `hellenic_iron_ore_pdf_brand_specs_series.csv` (29,506 rows) — Fe %, Alumina %, Silica %, Phosphorus %, and Moisture % by brand
  - `hellenic_iron_ore_pdf_freight_rates_series.csv` (22,257 rows) — C3 (Tubarao-Qingdao) & C5 (W. Australia-Qingdao) Capesize spot freight
  - `hellenic_iron_ore_pdf_steel_production_consumption_series.csv` (19,679 rows) — Chinese rebar & HRC production and consumption indices
  - `hellenic_iron_ore_pdf_import_volumes_series.csv` (17,252 rows) — Total Chinese monthly & weekly iron ore import volumes
  - `hellenic_iron_ore_pdf_port_differentials_series.csv` (14,983 rows) — PB Fines port basis spreads across 12 Chinese port terminals
  - `hellenic_iron_ore_pdf_indices_series.csv` (11,619 rows) — IOPI62, IOPI65, IOPI58, IOSI62, IOSI65, IOPLI62 spot and seaborne benchmarks
  - `hellenic_iron_ore_pdf_averages_series.csv` (11,544 rows) — Multi-period rolling averages (MTD, QTD, YTD, 52-week low/high)
  - `hellenic_iron_ore_pdf_normalisations_series.csv` (10,740 rows) — Differential penalties per 1% Fe, 1% Alumina, 1% Silica, 0.01% Phosphorus
  - `hellenic_iron_ore_pdf_steel_mill_pnl_series.csv` (9,627 rows) — Chinese steel mill profit margin models (BF vs BOF rebar & HRC)
  - `hellenic_iron_ore_pdf_index_comparisons_series.csv` (9,546 rows) — Relative performance spreads between benchmark indices
  - `hellenic_iron_ore_pdf_steel_series.csv` (8,488 rows) — Spot steel market prices (Rebar, Wire rod, HRC, CRC, Medium/Heavy plate)
  - `hellenic_iron_ore_pdf_port_inventories_series.csv` (6,067 rows) — Port stockpiles across Jingtang, Qingdao, Caofeidian, Tianjin, Rizhao
  - `hellenic_iron_ore_table_series.csv` (5,624 rows) — Port stock vs seaborne grade parity tables
  - `hellenic_iron_ore_pdf_domestic_concentrate_series.csv` (5,583 rows) — Domestic concentrate prices (Hanxing, Qian'an, Anshan, Zibo)
  - `hellenic_iron_ore_daily_series.csv` (1,175 rows) — Daily core macro dashboard metrics (36 normalized columns)
  - `hellenic_iron_ore_pdf_spreads_series.csv` (3,240 rows) — High-grade (65%) vs low-grade (58%) Fe price spreads
  - `hellenic_iron_ore_pdf_futures_series.csv` (2,227 rows) — DCE & SGX front-month iron ore and SHFE rebar settlement prices
  - `hellenic_iron_ore_commentary_series.csv` (1,182 rows) — Full daily desk commentary narrative text
  - `hellenic_iron_ore_pdf_dashboard_series.csv` (127 rows) — New SMM dashboard executive indicators
  - `hellenic_smm_market_drivers_series.csv` (10 rows) — SMM weekly operational metrics (hot metal output, blast furnace operating rates, 10-port/35-port inventory, outbound volumes)

### Hellenic: Shipbuilding & Contracting
- **Corpus Directory:** [`corpus/02-hellenic/shipbuilding`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/shipbuilding)
- **Markdown Output:** [`data/extracted/md/hellenic/shipbuilding`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/shipbuilding)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2014-03-28` to `2026-09-29`
- **Latest Ingested Document:** `2026-07-31_clarksons-hellas-snp-weekly-3_weekly-sales-31st-jul-2026_2ee0001b97f9.pdf` (Status: **CURRENT**)
- **Inventory by Format:** 1352 PDFs, 379 HTML files, 180 Images, 165 Markdown files
- **Chart Extraction:** No (Shipyard contracting and orderbook tables)
- **Chart Engine / Technique:** Native PyMuPDF table parser
- **Stacked Series CSVs:** clarksons_sales_series.csv (merged)
- **Extraction Script:** [`run_hellenic_shipbuilding.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_shipbuilding.py)
- **Notes & Rules Applied:** Clarksons Hellas shipyard contracting and orderbook updates.

### Hellenic: Tanker Time Charter (Alibra)
- **Corpus Directory:** [`corpus/02-hellenic/tanker_charter`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/tanker_charter)
- **Markdown Output:** [`data/extracted/md/hellenic/tanker_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/tanker_charter)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2014-03-28` to `2026-09-30`
- **Latest Ingested Document:** `2026-09-30_weekly-tanker-time-charter-estimates-september-30-2026.html` (Status: **CURRENT**)
- **Inventory by Format:** 0 PDFs, 278 HTML files, 757 Images, 265 Markdown files
- **Chart Extraction:** Yes (Crude & clean period earnings comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_tanker_tc_series.csv (7,177 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Tanker period TC assessments across VLCC, Suezmax, Aframax, LR2, LR1, MR.

### Hellenic: VesselsValue Valuations
- **Corpus Directory:** [`corpus/02-hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/vessel_valuations)
- **Markdown Output:** [`data/extracted/md/hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/vessel_valuations)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2014-03-28` to `2026-09-29`
- **Latest Ingested Document:** `2026-09-29_weekly-vessel-valuations-report-september-29-2026.html` (Status: **CURRENT**)
- **Inventory by Format:** 0 PDFs, 274 HTML files, 726 Images, 261 Markdown files
- **Chart Extraction:** Yes (VesselsValue fleet valuation index graphs)
- **Chart Engine / Technique:** HTML table parser + VV valuation matrix calculator
- **Stacked Series CSVs:** hellenic_vv_matrix_series.csv (12,340 rows), hellenic_vv_sales_series.csv (2,122 rows)
- **Extraction Script:** [`run_hellenic_vessel_valuations.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_vessel_valuations.py)
- **Notes & Rules Applied:** Full secondhand valuation matrix across Bulkers, Tankers, Containers for Newbuilding, 5Y, 10Y, 15Y, 20Y.

### Breakwave Advisors
- **Corpus Directory:** [`corpus/03-breakwave`](file:///C:/Users/Dell/Github/Shipping/corpus/03-breakwave)
- **Markdown Output:** [`data/extracted/md/breakwave`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/breakwave)
- **Publication Cadence:** Weekly (Tuesday) & Daily Insights (Expected day: Tuesday)
- **Coverage Span:** `2018-07-03` to `2026-09-29`
- **Latest Ingested Document:** `2026-09-29_Breakwave_Dry_Bulk.html` (Status: **CURRENT**)
- **Inventory by Format:** 304 PDFs, 3236 HTML files, 15072 Images, 3485 Markdown files
- **Chart Extraction:** Yes (Dry bulk freight fundamentals & ETF price trajectories)
- **Chart Engine / Technique:** PyMuPDF LiteParse + chart image extraction
- **Stacked Series CSVs:** breakwave_fundamentals_series.csv (2,746 rows), breakwave_insights_metadata.csv (3,194 rows)
- **Extraction Script:** [`run_breakwave_clean_liteparse.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_breakwave_clean_liteparse.py)
- **Notes & Rules Applied:** 15,072 chart images extracted. BDRY and BWET ETF fundamental commentaries parsed.

### Poten & Partners (Tanker Opinions)
- **Corpus Directory:** [`corpus/04-poten`](file:///C:/Users/Dell/Github/Shipping/corpus/04-poten)
- **Markdown Output:** [`data/extracted/md/poten`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/poten)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2004-01-02` to `2026-09-18`
- **Latest Ingested Document:** `Weekly Opinion - 18 September 2026 - Running Out Of Options.pdf` (Status: **NORMAL INTERVAL (Week 39 due)**)
- **Inventory by Format:** 1087 PDFs, 0 HTML files, 0 Images, 1087 Markdown files
- **Chart Extraction:** Yes (Top Charterers annual/biannual volume rankings)
- **Chart Engine / Technique:** Local PyMuPDF geometry extraction (poten_clean_v2)
- **Stacked Series CSVs:** poten_opinions_metadata.csv (1,087 rows), poten_top_charterers_series.csv (755 rows), poten_fixtures_series.csv (100 rows)
- **Extraction Script:** [`run_poten.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_poten.py)
- **Notes & Rules Applied:** Unbroken 22-year coverage (2004-2026). 1,087 reports cover-to-cover with 0 date exceptions.

### Seabrokers (Seabreeze Monthly Offshore)
- **Corpus Directory:** [`corpus/05-seabrokers`](file:///C:/Users/Dell/Github/Shipping/corpus/05-seabrokers)
- **Markdown Output:** [`data/extracted/md/seabrokers`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/seabrokers)
- **Publication Cadence:** Monthly (1st of Month) (Expected day: 1st of Month)
- **Coverage Span:** `2018-05-01` to `2026-08-01`
- **Latest Ingested Document:** `2026-08-01_market-report-august-2026.pdf` (Status: **NORMAL INTERVAL (Published with 3-4 week lag, Sep edition covers Aug)**)
- **Inventory by Format:** 97 PDFs, 0 HTML files, 0 Images, 97 Markdown files
- **Chart Extraction:** Yes (OSV utilisation curves, rig dayrates, offshore wind)
- **Chart Engine / Technique:** LlamaParse cover-to-cover + export_seabrokers_series.py
- **Stacked Series CSVs:** seabrokers_osv_monthly_history_series.csv (6,280 rows), seabrokers_rigs_market_series.csv (4,467 rows), seabrokers_osv_utilisation_series.csv (2,304 rows), seabrokers_osv_spot_rates_series.csv (1,855 rows)
- **Extraction Script:** [`run_seabrokers_llamaparse.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_seabrokers_llamaparse.py)
- **Notes & Rules Applied:** 9 master series CSVs (15,430 rows total). Unbroken monthly offshore and subsea coverage.

### Drewry Maritime AIS Fleet Performance
- **Corpus Directory:** [`corpus/06-drewry/ais`](file:///C:/Users/Dell/Github/Shipping/corpus/06-drewry/ais)
- **Markdown Output:** [`data/extracted/md/drewry/ais`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2024-01-02` to `2026-09-24`
- **Latest Ingested Document:** `Drewry_AIS_Product_LR2_Week39_2026.pdf` (Status: **CURRENT (Ingested up to Week 39 across DAM 034)**)
- **Inventory by Format:** 288 PDFs, 0 HTML files, 0 Images, 288 Markdown files
- **Chart Extraction:** Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds)
- **Chart Engine / Technique:** Vector PostScript/PDF drawing curve extractor + executive KPI parser (run_drewry_ais_charts.py)
- **Stacked Series CSVs:** drewry_ais_fleet_performance_series.csv (14,768 rows), drewry_ais_regional_congestion_series.csv (6,792 rows), drewry_ais_deployment_speed_series.csv (2,427 rows), drewry_ais_utilisation_curves_series.csv (1,007 rows)
- **Extraction Script:** [`run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py)
- **Notes & Rules Applied:** 24,994 continuous weekly data points across all 10 vessel classes: Product LR1 (34), VLCC (32), LPG Carrier (32), Aframax (31), Product LR2 (31), Suezmax (30), Capesize (27), Handysize (25), Panamax (23), Supramax (23).

#### Discrete Vessel Class Breakdown & Dedicated Folder Inventory

Drewry AIS reports are organized into 10 distinct vessel sectors, each with dedicated Markdown digests and structured table sidecars:

| Vessel Class | Deadweight / CBM | Report Count | Markdown Subfolder | Primary Metrics Tracked |
| :--- | :--- | :---: | :--- | :--- |
| **Product LR1** | 75,000 DWT | 34 reports | [`data/extracted/md/drewry/ais/Product_LR1`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Product_LR1) | Clean product utilisation %, tonne-miles, regional refinery flows |
| **VLCC** | 300,000 DWT | 32 reports | [`data/extracted/md/drewry/ais/Crude_VLCC`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Crude_VLCC) | Crude utilisation %, tonne-miles, Ras Tanura/Ningbo queues, ballast speed |
| **LPG Carrier** | 84,000 CBM | 32 reports | [`data/extracted/md/drewry/ais/LPG_FR`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/LPG_FR) | VLGC fleet utilisation %, tonne-miles, US Gulf/Ras Laffan flows |
| **Aframax** | 115,000 DWT | 31 reports | [`data/extracted/md/drewry/ais/Crude_Aframax`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Crude_Aframax) | Dirty utilisation %, tonne-miles, North Sea/Baltic/Caribs queues |
| **Product LR2** | 115,000 DWT | 31 reports | [`data/extracted/md/drewry/ais/Product_LR2`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Product_LR2) | Clean product utilisation %, tonne-miles, MEG-East product flows |
| **Suezmax** | 160,000 DWT | 30 reports | [`data/extracted/md/drewry/ais/Crude_Suezmax`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Crude_Suezmax) | Crude utilisation %, tonne-miles, West Africa/Mediterranean queues |
| **Capesize** | 180,000 DWT | 27 reports | [`data/extracted/md/drewry/ais/Drybulk_Capesize`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Drybulk_Capesize) | Iron ore utilisation %, tonne-miles, Port Hedland/Tubarao delays |
| **Handysize** | 38,000 DWT | 25 reports | [`data/extracted/md/drewry/ais/Drybulk_Handysize`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Drybulk_Handysize) | Minor bulk utilisation %, tonne-miles, grain/fertilizer port queues |
| **Panamax / Kamsarmax** | 82,000 DWT | 23 reports | [`data/extracted/md/drewry/ais/Drybulk_Panamax`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Drybulk_Panamax) | Grain/coal utilisation %, tonne-miles, Santos/Mississippi delays |
| **Supramax / Ultramax** | 64,000 DWT | 23 reports | [`data/extracted/md/drewry/ais/Drybulk_Supramax`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais/Drybulk_Supramax) | Minor bulk utilisation %, tonne-miles, Indonesian coal delays |

#### Complete Pipeline Scripts & Asset Locations
- **Live Ingestion Scraper:** [`scripts/scrapers/fetch_drewry_ais_weekly.py`](file:///C:/Users/Dell/Github/Shipping/scripts/scrapers/fetch_drewry_ais_weekly.py) — polls Drewry digital asset repository on Tuesdays.
- **Multi-Threaded Sweeper:** [`scripts/scrapers/sweep_drewry_fast.py`](file:///C:/Users/Dell/Github/Shipping/scripts/scrapers/sweep_drewry_fast.py) — 20-worker fast DAM probe across weeks 32-42 for 2026.
- **KPI & Tables Extractor:** [`scripts/extract/publishers/run_drewry_ais.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais.py) — extracts tables and generates Markdown dossiers into per-class subdirectories.
- **Vector Curves Extractor:** [`scripts/extract/publishers/run_drewry_ais_charts.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) — extracts drawing curves and stacks into 4 master series CSVs (24,994 data rows).

### Drewry Opinions & World Container Index (WCI)
- **Corpus Directory:** [`corpus/06-drewry/opinions`](file:///C:/Users/Dell/Github/Shipping/corpus/06-drewry/opinions)
- **Markdown Output:** [`data/extracted/md/drewry/opinions`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/opinions)
- **Publication Cadence:** Weekly (Thursday) (Expected day: Thursday)
- **Coverage Span:** `2017-11-09` to `2026-09-24`
- **Latest Ingested Document:** `2026-09-20_drewry_wci.md` (Status: **CURRENT (Assessed Thursdays)**)
- **Inventory by Format:** 0 PDFs, 0 HTML files, 0 Images, 548 Markdown files
- **Chart Extraction:** Yes (Global container freight rate time series)
- **Chart Engine / Technique:** Wayback CDX & live HTML parser with pv18 stability guard
- **Stacked Series CSVs:** drewry_wci_historical.csv (122 weekly rows, display-linked)
- **Extraction Script:** [`fetch_drewry_wci.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/fetch_drewry_wci.py)
- **Notes & Rules Applied:** Contract test verified (38 passed). Displayed directly on index.html.

### Signal Ocean (Fleet Telemetry & Monitors)
- **Corpus Directory:** [`corpus/07-signal`](file:///C:/Users/Dell/Github/Shipping/corpus/07-signal)
- **Markdown Output:** [`data/extracted/md/signal`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/signal)
- **Publication Cadence:** Weekly (Friday) & Live Telemetry (Expected day: Friday)
- **Coverage Span:** `2021-05-14` to `2026-09-24`
- **Latest Ingested Document:** `weekly-tanker-market-monitor-week-35-2026.md` (Status: **CURRENT**)
- **Inventory by Format:** 10 PDFs, 515 HTML files, 1885 Images, 456 Markdown files
- **Chart Extraction:** Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps)
- **Chart Engine / Technique:** Playwright session scraper + static monitor markdown builder
- **Stacked Series CSVs:** signal_reports_metadata.csv (446 rows), data/views/signal/live_fleet_positions.json
- **Extraction Script:** [`sync_live_fleet_pipeline.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/sync_live_fleet_pipeline.py)
- **Notes & Rules Applied:** Live automated telemetry syncs active tanker queues and fleet AIS positions.

### Baltic Exchange Weekly
- **Corpus Directory:** [`corpus/08-baltic`](file:///C:/Users/Dell/Github/Shipping/corpus/08-baltic)
- **Markdown Output:** [`data/extracted/md/baltic`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/baltic)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2015-01-02` to `2026-09-25`
- **Latest Ingested Document:** `2026_tanker-report-week-9_tanker.md` (Status: **CURRENT**)
- **Inventory by Format:** 0 PDFs, 3043 HTML files, 0 Images, 2218 Markdown files
- **Chart Extraction:** No (Detailed fixture narratives and route earnings)
- **Chart Engine / Technique:** BeautifulSoup HTML layout parser
- **Stacked Series CSVs:** baltic_reports_metadata.csv (2,218 rows), baltic_ncfi_series.csv (2,180 rows)
- **Extraction Script:** [`run_baltic.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_baltic.py)
- **Notes & Rules Applied:** Covers Tanker, Dry Bulk, Container, Gas, and Ningbo Container Freight Index (NCFI).

### Pilbara Ports Authority (PPA)
- **Corpus Directory:** [`corpus/09-ppa`](file:///C:/Users/Dell/Github/Shipping/corpus/09-ppa)
- **Markdown Output:** [`data/commodities`](file:///C:/Users/Dell/Github/Shipping/data/commodities)
- **Publication Cadence:** Monthly (20th of Month) (Expected day: 20th of Month)
- **Coverage Span:** `2016-03-11` to `2026-07-28`
- **Latest Ingested Document:** `PPA Shipping Figures - July 2026.pdf` (Status: **NORMAL INTERVAL (August throughput figures published late Sep/early Oct)**)
- **Inventory by Format:** 493 PDFs, 0 HTML files, 0 Images, 0 Markdown files
- **Chart Extraction:** No (Port Hedland & Dampier iron ore export tonnage tables)
- **Chart Engine / Technique:** PDF tabular throughput parser + DuckDB
- **Stacked Series CSVs:** australia_ppa_iron_ore.csv (424 rows, display-linked)
- **Extraction Script:** [`run_ppa.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_ppa.py)
- **Notes & Rules Applied:** Directly feeds iron ore throughput charts on index.html. Stored in corpus.duckdb.

---

## 5. Quarantined & Stashed Redundant Sources Register

**Quarantine Root Directory:** [`data/stashed_redundant_sources/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources)  
**Total Quarantined Files Preserved:** 10,286 files (Zero data deletion policy applied)  
**Master Quarantine Ledger:** [`data/stashed_redundant_sources/README.md`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/README.md)

To prevent automated scanning tools, agents, and subagents from discovering or highlighting superseded web previews, truncated files, or unpartitioned root duplicates over the authoritative ground truth data, the following redundant sources have been safely quarantined into stashed storage:

| Quarantined / Stashed Category | Stashed Location | Items Preserved | Why Stashed (Root Cause) | Active Authoritative Path (Single Source of Truth) |
| :--- | :--- | :---: | :--- | :--- |
| **Hellenic Iron Ore HTML Web Previews** | [`data/stashed_redundant_sources/hellenic_iron_ore_html_previews/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/hellenic_iron_ore_html_previews) | **4,700 files** (6 year subdirs) | Thin ~20-line HTML web-scraped summaries from the Hellenic news site. Caused agents to report partial summaries rather than the full 400-line cover-to-cover data. | [`data/extracted/md/hellenic/iron_ore_pdf/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore_pdf) (1,188 full-fidelity Markdown reports + `.tables.json` sidecars across 2021-2026, plus 21 stacked series CSVs) |
| **Poten Legacy Scraped Markdown (Corpus)** | [`data/stashed_redundant_sources/poten_legacy_scraped_md/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/poten_legacy_scraped_md) | **2,183 files** (2004-2026) | Truncated web preview text (`... Read More" />`) and `unknown-01-01` dates sitting in the corpus directory, creating confusion with raw PDFs. | **Corpus:** [`corpus/04-poten/pdfs/`](file:///C:/Users/Dell/Github/Shipping/corpus/04-poten/pdfs) (1,087 PDFs)<br>**Extracted MD:** [`data/extracted/md/poten/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/poten) (1,087 full Markdown reports) |
| **Banchero Costa Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/banchero_costa/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/banchero_costa) | **499 files** | Unpartitioned root duplicate `.md` and `.tables.json` files and legacy singleton naming (`bancosta_*.md`) conflicting with year folders. | [`data/extracted/md/banchero_costa/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/banchero_costa) (Clean year-partitioned directories, 100% complete) |
| **Carriers Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/carriers/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/carriers) | **272 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/carriers/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/carriers) |
| **Fearnleys Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/fearnleys/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/fearnleys) | **522 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/fearnleys/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/fearnleys) |
| **ISM Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ism/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ism) | **231 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/ism/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ism) |
| **SSY Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ssy/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ssy) | **1,061 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/ssy/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/ssy) |
| **Xclusiv Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv) | **809 files** | Loose duplicate `.md`, `.tables.json`, and `.charts.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/xclusiv/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/xclusiv) |
| **Other Broker Loose Root Files** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/`](file:///C:/Users/Dell/Github/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates) | **9 files** | Loose state/artifact files across Advanced Shipping, Affinity, Agora, Clarksons, Lion, Star Asia. | [`data/extracted/md/<broker>/<year>/`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md) |

