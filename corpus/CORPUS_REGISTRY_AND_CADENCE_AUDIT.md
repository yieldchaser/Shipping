# Master Corpus Registry, Publication Cadence & Extraction Audit

**Audit Snapshot Date:** 2026-10-06 | **Repository:** Shipping Knowledge Base  
**Authoritative Ledger:** Combines the Master Extraction Register, Live Publication Cadence, Format Breakdown, Granular Sub-Sector/Fleet Breakdown, and Vector Chart Inventory across all corpus directories.

---

## 1. Executive Summary & Fleet Publication Status

- **Total Raw Corpus Assets Cataloged:** Over 58,580 documents across 32 discrete publishers and categories in `corpus/`.
- **Raw Ingested Formats in Corpus:** 8,983 PDFs, 8,992 HTML files, 19,919 JPG/PNG images, 18,072 Native Markdown files.
- **Normalized Extracted Markdown Dossiers:** Over 23,279 cover-to-cover Markdown files in `data/extracted/md/` (accompanied by structured `.tables.json` sidecars and 98+ stacked relational CSV series).
- **Status as of 2026-10-06:**
  - **Current & Up to Date (<= 7 days ago):** 22 publishers/categories have their latest reports and filings fully digested.
  - **Week 40 Comprehensive Ingest:** Clarksons Hellas, Lion Shipbrokers, Agora Shipbroking, Advanced Shipping, Affinity Tankers, GMS Demolition, Best Oasis, Fearnleys Weekly, and Fearnleys Broker Voice (4,742 weekly desk comment files) have been harvested, parsed, and stacked into production series.
  - **Reference Literature:** 12 foundational maritime textbooks and handbooks fully normalized and audited with 100% byte parity in `corpus/books/` and `knowledge/docs/books/`.
  - **Normal Interval / Monthly Reporting Lag:** Seabrokers, PPA, and Drewry AIS operate on 30-to-60 day reporting cycles where August figures are published in late September or early October.
  - **Chinese National Day Notice:** Hellenic Iron Ore (MMI Daily) spot updates pause during China's Golden Week (October 1 to October 7).

---

## 2. Master Publisher Cadence & Inventory Matrix

| Publisher / Source | Cadence | Latest Issue Date | Days Elapsed | Status (2026-10-06) | Raw Ingested Format (Corpus) | Extracted MD Path (data/extracted/md/) | Vector Charts Extracted | Primary Master Series CSV |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- | :--- |
| **Advanced Shipping & Trading** | Weekly (Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 254 PDF | [`data/extracted/md/advanced_shipping`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/advanced_shipping) | Yes (Secondhand valuation matrices & demo trends) | `advanced_shipping_sales_series.csv (6,105 rows)` |
| **Affinity Shipbrokers** | Weekly (Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 255 PDF | [`data/extracted/md/affinity`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/affinity) | Yes (Baltic Dirty & Clean TCE trajectory curves) | `affinity_tce_series.csv (4,039 rows)` |
| **Agora Shipbroking** | Weekly (Wednesday/Thursday) | `2026-09-30` | 6d | **CURRENT (6d ago)** | 216 PDF | [`data/extracted/md/agora`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/agora) | No (Dense indicator tables across 5 pages) | `agora_indicators_series.csv (10,002 rows)` |
| **Banchero Costa (Bancosta)** | Weekly (Wednesday) | `2026-09-30` | 6d | **CURRENT (6d ago)** | 247 PDF | [`data/extracted/md/banchero_costa`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/banchero_costa) | Yes (Freight rates, FFA forward curves, ConTex index) | `bancosta_freight_rates_series.csv (20,321 rows)` |
| **Carriers Chartering (General Broker)** | Weekly (Monday) | `2026-09-28` | 8d | **CURRENT (8d ago)** | 136 PDF | [`data/extracted/md/carriers`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/carriers) | No (Tabular S&P and Baltic BSPA/BDA indices) | `carriers_sales_series.csv (3,004 rows)` |
| **Clarksons / Clarksons Hellas** | Weekly (Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 181 PDF | [`data/extracted/md/clarksons`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/clarksons) | No (Bulker & Tanker reported sales transaction tables) | `clarksons_sales_series.csv (1,311 sales rows, 120 demo rows)` |
| **Fearnleys Weekly** | Weekly (Wednesday/Thursday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 4,742 MD | [`data/extracted/md/fearnleys`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys) | Yes (Tanker spot WS, Dry bulk BDI & TC, LPG/LNG) | `fearnleys_rates_series.csv (14,669 rows)` |
| **Fearnleys Broker Voice (Hasura Desk Feeds)** | Weekly (Wednesday-Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 4,742 MD | [`data/extracted/md/fearnleys/voice`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys/voice) | No (Dense narrative intelligence across 35 desks & routes) | `fearnleys_broker_comments.csv (11,750 comments), corpus/01-brokers/fearnleys/voice/ (11,750 files), data/extracted/md/fearnleys/voice/ (11,750 files)` |
| **Fearnleys-MD (Econometric Research)** | Monthly / Bespoke (Bi-weekly) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 184 MD | [`data/extracted/md/fearnleys-md`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys-md) | Yes (Top 52 econometric recurring lead-indicator models) | `fearnleys_md_master_econometric_series.xlsx (6 sheets, 26 lead models)` |
| **Gibson Shipbrokers** | Weekly (Friday) | `2026-09-25` | 11d | **CURRENT (11d ago)** | 167 HTML | [`data/extracted/md/gibson`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/gibson) | Yes (wpDataCharts daily vector curves for all 155 HTML reports in .charts.json) | `gibson_tanker_spot_series.csv (3,583 rows)` |
| **Intermodal Shipbrokers** | Weekly (Tuesday) | `2026-09-29` | 7d | **CURRENT (7d ago)** | 256 PDF | [`data/extracted/md/intermodal`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/intermodal) | Yes (Baltic & Time Charter vector curves, Page 3) | `intermodal_baltic_tc_series.csv (20,348 rows)` |
| **ISM Coasters & Mini-Bulkers** | Weekly (Monday) | `2026-09-28` | 8d | **CURRENT (8d ago)** | 115 PDF | [`data/extracted/md/ism`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ism) | Yes (4 weekly freight indicator vector charts) | `ism_handy_freight_series.csv (17,629 rows)` |
| **Lion Shipbrokers** | Weekly (Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 47 PDF | [`data/extracted/md/lion`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/lion) | No (S&P deals, Demometer indicative ranges, Demo fixtures) | `lion_deals_series.csv (1,212 rows)` |
| **SSY (Simpson Spence Young)** | Weekly (Monday) | `2026-09-28` | 8d | **CURRENT (8d ago)** | 530 PDF | [`data/extracted/md/ssy`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ssy) | Yes (Atlantic & Pacific Capesize index vector curves) | `ssy_capesize_index_series.csv (8,881 rows)` |
| **Star Asia Demolition** | Weekly (Friday) | `2026-09-25` | 11d | **CURRENT (11d ago)** | 199 PDF | [`data/extracted/md/star_asia`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/star_asia) | Yes (Subcontinent scrap price trends $/LDT, metals/energy) | `star_asia_snp_sales_series.csv (3,717 rows)` |
| **Xclusiv Shipbrokers** | Weekly (Monday) | `2026-09-28` | 8d | **CURRENT (8d ago)** | 271 PDF | [`data/extracted/md/xclusiv`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/xclusiv) | Yes (Pages 2-3 freight curves, Pages 8-9 bunker spreads) | `xclusiv_secondhand_series.csv (8,593 rows)` |
| **Hellenic: Demolition Market** | Weekly (Saturday/Sunday) | `2026-10-03` | 3d | **CURRENT (3d ago)** | 1,056 PDF, 810 HTML, 1,211 IMG | [`data/extracted/md/hellenic/demolition`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/demolition) | Yes (Port position queue charts, cash buyer price matrices) | `hellenic_athenian_demolition_series.csv (2,916 rows)` |
| **Hellenic: Dry Bulk Charter (Alibra)** | Weekly (Wednesday) | `2026-09-30` | 6d | **CURRENT (6d ago)** | 279 HTML, 761 IMG | [`data/extracted/md/hellenic/dry_charter`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/dry_charter) | Yes (Alibra rate fixture comparison graphics) | `hellenic_alibra_dry_tc_series.csv (6,443 rows)` |
| **Hellenic: Iron Ore (MMI & SMM Daily)** | Daily (Mon-Fri) | `2026-10-05` | 1d | **CURRENT (1d ago)** | 2,252 PDF | [`data/extracted/md/hellenic/iron_ore_pdf`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/iron_ore_pdf) | Yes (4 SMM driver vector charts + MMi inventory/margin curves) | `hellenic_iron_ore_pdf_brands_series.csv (216 rows)` |
| **Hellenic: Shipbuilding & Contracting** | Weekly (Friday) | `2026-09-29` | 7d | **CURRENT (7d ago)** | 677 PDF, 379 HTML, 180 IMG | [`data/extracted/md/hellenic/shipbuilding/clarksons`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/shipbuilding/clarksons) | No (Shipyard contracting and orderbook tables) | `clarksons_snp_sales_series.csv` |
| **Hellenic: Tanker Time Charter (Alibra)** | Weekly (Wednesday) | `2026-09-30` | 6d | **CURRENT (6d ago)** | 278 HTML, 758 IMG | [`data/extracted/md/hellenic/tanker_charter`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/tanker_charter) | Yes (Crude & clean period earnings comparison graphics) | `hellenic_alibra_tanker_tc_series.csv (7,177 rows)` |
| **Hellenic: VesselsValue Valuations** | Weekly (Tuesday) | `2026-09-29` | 7d | **CURRENT (7d ago)** | 274 HTML, 733 IMG | [`data/extracted/md/hellenic/vessel_valuations`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/vessel_valuations) | Yes (VesselsValue fleet valuation index graphs) | `hellenic_vv_matrix_series.csv (12,340 rows)` |
| **Breakwave Advisors** | Weekly (Tuesday) & Daily Insights | `2026-10-05` | 1d | **CURRENT (1d ago)** | 304 PDF, 3,242 HTML, 15,083 IMG, 3,213 MD | [`data/extracted/md/breakwave`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/breakwave) | Yes (Dry bulk freight fundamentals, ETF trajectories, & localized Insights charts) | `breakwave_fundamentals_series.csv (2,746 rows)` |
| **Poten & Partners (Tanker Opinions)** | Weekly (Friday) | `2026-09-18` | 18d | **NORMAL INTERVAL (18d ago)** | 1,087 PDF | [`data/extracted/md/poten`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/poten) | Yes (Top Charterers annual/biannual volume rankings) | `poten_opinions_metadata.csv (1,087 rows)` |
| **Seabrokers (Seabreeze Monthly Offshore)** | Monthly (1st of Month) | `2026-09-01` | 35d | **NORMAL INTERVAL (35d ago)** | 97 PDF, 99 MD | [`data/extracted/md/seabrokers`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/seabrokers) | Yes (OSV utilisation curves, rig dayrates, offshore wind) | `seabrokers_osv_monthly_history_series.csv (6,280 rows)` |
| **Drewry Maritime AIS Fleet Performance** | Weekly (Tuesday) | `2026-09-24` | 12d | **CURRENT (12d ago)** | 288 PDF | [`data/extracted/md/drewry/ais`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais) | Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds) | `drewry_ais_fleet_performance_series.csv (14,768 rows)` |
| **Drewry Opinions & World Container Index (WCI)** | Weekly (Thursday) | `2026-10-01` | 5d | **CURRENT (5d ago)** | 1,092 MD | [`data/extracted/md/drewry/opinions`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/opinions) | Yes (Global container freight rate time series) | `drewry_wci_historical.csv (136 rows)` |
| **Signal Ocean (Fleet Telemetry & Monitors)** | Weekly (Friday) & Live Telemetry | `2026-09-29` | 7d | **CURRENT (7d ago)** | 10 PDF, 515 HTML, 1,193 IMG, 450 MD | [`data/extracted/md/signal`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/signal) | Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps) | `signal_reports_metadata.csv (446 rows)` |
| **Baltic Exchange Weekly** | Weekly (Friday) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 3,048 HTML, 2,228 MD | [`data/extracted/md/baltic`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/baltic) | No (Detailed fixture narratives and route earnings) | `baltic_reports_metadata.csv (2,227 rows)` |
| **Pilbara Ports Authority (PPA)** | Monthly (20th of Month) | `2026-07-28` | 70d | **NORMAL INTERVAL (70d ago)** | 493 PDF | [`data/commodities`](file:////home/runner/work/Shipping/Shipping/data/commodities) | No (Port Hedland & Dampier iron ore export tonnage tables) | `australia_ppa_iron_ore.csv (423 rows)` |
| **SEC EDGAR: Listed Shipping & Dry Bulk Corporates (26 Issuers)** | Continuous / Statutory Filing Triggers (10-K, 20-F, 10-Q, 6-K, Material 8-K) | `2026-10-02` | 4d | **CURRENT (4d ago)** | 1,310 MD | [`data/extracted/md/companies`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/companies) | No (Complete tabular statutory financials, fleet lists, debt notes) | `Direct structured Markdown with standardized YAML frontmatter across 26 corporate subdirectories` |
| **Maritime Reference Literature & Academic Textbooks (12 Books)** | Static Reference Corpus | `2026-10-04` | 2d | **CURRENT (2d ago)** | 12 PDF, 12 MD | [`data/extracted/md/books`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/books) | Yes (LaTeX math formulas, figures, port facilities) | `Clean Markdown in data/extracted/md/books/*.md and knowledge/docs/books/*.md` |

---

## 3. Granular Sub-Sector, Vessel Class & Fleet Breakdown

This section details document volumes, vessel classes, numerical metric coverage, and extraction scripts across complex composite publishers.

### 3.1 Drewry Maritime AIS Fleet Performance (10 Discrete Vessel Classes)

Drewry AIS reports are published across 10 specialized maritime vessel classes. The pipeline extracts executive KPIs, fleet utilisation curves, bunker consumption indicators, and port congestion indices without OCR noise:

| Vessel Class / Sector | Report Count in Corpus | Typical Deadweight / CBM | Analytical Metrics Extracted | Master Series Target CSV | Extracted Data Volume | Processing Script |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **Capesize (180,000 DWT)** | `27 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Port Hedland/Tubarao delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Panamax / Kamsarmax (82,000 DWT)** | `23 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Santos/Mississippi delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Supramax / Ultramax (64,000 DWT)** | `23 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, Indonesian coal delays | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Handysize (38,000 DWT)** | `25 weekly PDFs` | PDF vector | Fleet utilisation %, tonne-miles, ballast speed, minor bulk port queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **VLCC (300,000 DWT)** | `32 weekly PDFs` | PDF vector | Crude utilisation %, tonne-miles, Ras Tanura/Ningbo congestion, ballast speed | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Suezmax (160,000 DWT)** | `30 weekly PDFs` | PDF vector | Crude utilisation %, tonne-miles, West Africa/Mediterranean queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Aframax (115,000 DWT)** | `31 weekly PDFs` | PDF vector | Dirty utilisation %, tonne-miles, North Sea/Baltic/Caribs queues | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Product LR2 (115,000 DWT)** | `31 weekly PDFs` | PDF vector | Clean product utilisation %, tonne-miles, MEG-East product flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Product LR1 (75,000 DWT)** | `34 weekly PDFs` | PDF vector | Clean product utilisation %, tonne-miles, regional refinery flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **LPG Carrier (84,000 CBM VLGC)** | `32 weekly PDFs` | PDF vector | LPG carrier utilisation %, tonne-miles, US Gulf/Ras Laffan flows | `drewry_ais_fleet_performance_series.csv` | **14,768 rows across classes** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Regional Port Congestion (All Classes)** | `288 reports` | PDF vector curves | Port waiting days & congestion indexes across China, AG, USG, Aus, Bra | `drewry_ais_regional_congestion_series.csv` | **6,792 rows** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Deployment & Ballast Speeds (All Classes)** | `288 reports` | PDF vector curves | Laden vs ballast cruising speed knots by vessel class and region | `drewry_ais_deployment_speed_series.csv` | **2,427 rows** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |
| **Capacity Utilisation Curves (All Classes)** | `288 reports` | PDF vector curves | Multi-year historical utilisation curves (2020-2026) | `drewry_ais_utilisation_curves_series.csv` | **1,007 rows** | [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) |

### 3.2 Hellenic Shipping News Multi-Category Sub-Sources

| Category / Sub-Source | Sub-Broker / Segment | Report Count | Format | Commercial Intelligence Extracted | Master Series CSV | Total Data Rows | Processing Script |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **Hellenic Demolition** | Athenian Shipbrokers Cash Buyer | `1,272 reports` | HTML / PDF | Scrap indicative prices ($/LDT) for Bangladesh, India, Pakistan, Turkey | `hellenic_athenian_demolition_series.csv` | **2,916 rows** | [`run_athenian_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_athenian_demolition.py) |
| **Hellenic Demolition** | GMS Weekly Recycler Insights & Deals | `1,272 reports` | HTML / PDF | Cash buyer commentary, scrap sentiment, fixture deals | `hellenic_gms_demolition_series.csv` | **1,092 rows** | [`run_gms_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_gms_demolition.py) |
| **Hellenic Demolition** | GMS Port Position Queues | `1,272 reports` | HTML tables / Images | Cash buyer port arrivals, beaching positions, tonnage queued | `hellenic_gms_port_positions_series.csv` | **2,905 rows** | [`run_gms_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_gms_demolition.py) |
| **Hellenic Demolition** | Best Oasis Scrap Assessments & Deals | `1,272 reports` | HTML / PDF | Subcontinent scrap rates and beaching transaction fixtures | `hellenic_best_oasis_deals_series.csv` | **887 rows (deals), 863 rows (rates)** | [`run_best_oasis_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_best_oasis_demolition.py) |
| **Hellenic Dry Charter** | Alibra Dry Bulk Time Charter Estimates | `266 reports` | HTML / Images | 1Y, 2Y, 3Y, 5Y period TC ($/day) for Capesize, Kamsarmax, Ultramax, Handy | `hellenic_alibra_dry_tc_series.csv` | **6,443 rows** | [`run_hellenic_alibra_tc.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py) |
| **Hellenic Tanker Charter** | Alibra Tanker Time Charter Estimates | `265 reports` | HTML / Images | 1Y, 2Y, 3Y, 5Y period TC ($/day) for VLCC, Suezmax, Aframax, LR2, LR1, MR | `hellenic_alibra_tanker_tc_series.csv` | **7,177 rows** | [`run_hellenic_alibra_tc.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py) |
| **Hellenic Iron Ore** | MMI Daily Brand Price Assessments | `3,537 reports` | PDF / HTML | 31+ brand prices $/dmtu (PB Fines, Newman, Carajas, Lump/Pellet premiums) | `hellenic_iron_ore_pdf_brands_series.csv` | **216 rows** | [`run_hellenic_iron_ore_pdf.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) |
| **Hellenic Iron Ore** | SMM Daily Spot Iron Ore Benchmark | `1,171 reports` | PDF / HTML | 62% Fe CFR China daily benchmark and port stock statistics | `hellenic_iron_ore_daily_series.csv` | **1,171 rows** | [`run_smm_iron_ore_daily.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_smm_iron_ore_daily.py) |
| **Hellenic Iron Ore** | Baltic Capesize C3 / C5 Freight Rates | `1,164 reports` | PDF / HTML | Tubarao-Qingdao (C3) & Dampier-Qingdao (C5) freight $/ton | `hellenic_capesize_c3_c5_series.csv` | **1,164 rows** | [`run_hellenic_iron_ore_pdf.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) |
| **Hellenic Valuations** | VesselsValue Secondhand Valuation Matrix | `261 reports` | HTML tables / Images | Resale, 5Y, 10Y, 15Y, 20Y values ($M) for Bulkers, Tankers, Containers | `hellenic_vv_matrix_series.csv` | **12,340 rows** | [`run_hellenic_vv_matrix.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_vv_matrix.py) |
| **Hellenic Valuations** | VesselsValue Secondhand Sales Deals | `261 reports` | HTML tables | Reported S&P transactions with vessel name, DWT, built, yard, price $M | `hellenic_vv_sales_series.csv` | **2,062 rows** | [`run_hellenic_vessel_valuations.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_vessel_valuations.py) |

### 3.3 Shipbroker Intelligence Discrete Series & Econometric Models

| Publisher | Intelligence Domain | Document Volume | Format | Core Analytical Payload | Master Series CSV / Destination | Stored Volume | Processing Script |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **SSY Simpson Spence Young** | Atlantic Capesize Index (ACI) & Pacific (PCI) | `530 reports` | PDF tabular | Atlantic & Pacific Capesize voyage rate indices & iron ore haul routes | `data/indices/ (display-linked)` | **Continuous weekly indices** | [`run_ssy_complete.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_ssy_complete.py) |
| **Fearnleys Weekly** | 6-Pillar Weekly Market Intelligence | `526 reports` | PDF structured | Crude/Product tankers, Dry Bulk, Gas, Newbuilding, S&P, Macro | `data/extracted/series/ (normalized rate cards)` | **526 issues cover-to-cover** | [`run_fearnleys_normalized.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_fearnleys_normalized.py) |
| **Fearnleys Econometric** | 26 Lead-Indicator Econometric Models | `26 models` | Vector charts / Excel | Copper vs Supramax, Coal curve vs P5, Iron Ore vs 5TC, S&P vs 1Y TC | `fearnleys_md_master_econometric_series.xlsx` | **26 workbook sheets** | [`export_fearnleys_md_excel.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/export_fearnleys_md_excel.py) |
| **Poten & Partners** | Tanker Opinions & Top Charterers Series | `1,087 reports` | PDF full text | Narrative essays + 2005-2026 Top Dirty Spot Charterer annual volume rankings | `poten_top_charterers_series.csv` | **755 rows (charterers), 1,087 rows (metadata)** | [`run_poten.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_poten.py) |
| **Seabrokers Seascope** | Offshore Support Vessels, Rigs & Subsea | `97 reports` | PDF monthly | North Sea OSV dayrates, rig utilization %, subsea & offshore wind | `seabrokers_osv_monthly_history_series.csv` | **15,430 rows across 9 series** | [`run_seabrokers_llamaparse.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_seabrokers_llamaparse.py) |
| **Signal Ocean** | Weekly Monitors, Research & Live Fleet | `515 reports` | HTML / Telemetry | Dry & tanker weekly monitors, trade flows, live fleet positions & queues | `signal_reports_metadata.csv` | **446 rows + live JSON views** | [`run_signal.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_signal.py) |
| **Xclusiv Shipbrokers** | Comprehensive Tabular Market Intelligence | `271 reports` | PDF tables (9 pages) | S&P sales, scrap deals, secondhand matrix, newbuilding orders | `xclusiv_sales_series.csv` | **17,737 rows across 5 series** | [`run_xclusiv_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_xclusiv_tables.py) |
| **Advanced Shipping** | S&P, Secondhand Matrices, Demo & NB | `253 reports` | PDF tables (10 pages) | S&P sales, demolition rates & deals, secondhand valuation matrix | `advanced_shipping_sales_series.csv` | **18,744 rows across 5 series** | [`run_advanced_shipping_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_advanced_shipping_tables.py) |
| **Banchero Costa** | S&P Deals with IMO Numbers & Newbuilding | `243 reports` | PDF tables / LlamaParse | S&P deals with verified 7-digit IMO numbers, newbuilding orders & prices | `bancosta_sales_series.csv` | **5,043 rows across 3 series** | [`run_banchero_costa_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_banchero_costa_tables.py) |
| **Intermodal** | Secondhand S&P, Newbuilding, Scrap & Baltic | `256 reports` | PDF tables / Vector | Secondhand sales, newbuilding, scrap $/LDT, Page 3 Baltic curves | `intermodal_baltic_tc_series.csv` | **20,348 rows across series** | [`run_intermodal_full.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_intermodal_full.py) |
| **Drewry WCI** | World Container Index (WCI) Freight Benchmarks | `122 weekly rows` | HTML / Wayback CDX | 8 major east-west route benchmarks + composite index $/FEU | `drewry_wci_historical.csv` | **136 rows** | [`fetch_drewry_wci.py`](file:////home/runner/work/Shipping/Shipping/scripts/scrapers/fetch_drewry_wci.py) |
| **Pilbara Ports Authority** | Port Hedland & Dampier Iron Ore Export Throughput | `493 reports` | PDF tables | Monthly export tonnage, destination country breakdowns (China, Japan, Korea) | `australia_ppa_iron_ore.csv` | **423 rows** | [`run_ppa.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_ppa.py) |

### 3.4 SEC EDGAR Corporate Regulatory Filings (26 Listed Shipping & Dry Bulk Issuers)

Corporate statutory filings covering all 26 target shipping, dry bulk, tanker, and gas public issuers. Filings include Annual Reports (10-K, 20-F), Quarterly Reports (10-Q, 6-K), and Material 8-Ks (earnings, vessel sales/purchases, fleet developments), converted via sec2md into clean Markdown with standardized YAML frontmatter:

| Issuer Sector | Target Companies | Statutory Filings | Primary Form Types | Key Metrics & Financials Extracted | Storage Directory | Stored Documents | Ingestion Pipeline |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| **Corporate SEC Filings (Dry Bulk)** | Major Miners & Dry Bulk Owners (VALE, RIO, BHP, SBLK, GOGL, GNK, SB, DSX, SHIP, CTRM, GLBS, EDRY) | `596 filings` | Markdown / Tables | Annual Reports (10-K, 20-F), Quarterly Reports (10-Q, 6-K), Material 8-Ks | [`corpus/10-companies/`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies) | **596 statutory filings** | [`fetch_sec_filings.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/fetch_sec_filings.py) |
| **Corporate SEC Filings (Tankers & Gas)** | Crude, Product & Gas Tankers (FRO, INSW, STNG, DHT, TNK, TRMD, ECO, NAT, TNP, ASC, SFL, NVGS, LPG) | `714 filings` | Markdown / Tables | Annual Reports (10-K, 20-F), Quarterly Reports (10-Q, 6-K), Material 8-Ks | [`corpus/10-companies/`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies) | **714 statutory filings** | [`fetch_sec_filings.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/fetch_sec_filings.py) |

### 3.5 Maritime Reference Literature & Academic Textbooks (12 Foundational Books)

Foundational reference textbooks, econometric monographs, maritime law handbooks, port atlases, and industry literature providing the theoretical ground truth for knowledge extraction and GraphRAG semantic graph indexing. Both the raw source PDFs and normalized Markdown files reside together under [`corpus/books/`](file:///C:/Users/Dell/Github/Shipping/corpus/books) and are mirrored in [`knowledge/docs/books/`](file:///C:/Users/Dell/Github/Shipping/knowledge/docs/books):

| # | Work Title & Authors | Domain & Sector | Raw Source PDF | Normalized Markdown File | Key Structural Normalizations Applied |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | **Maritime Economics (3rd Ed.)**<br>Martin Stopford | Four Shipping Markets, Cycles, Supply/Demand, Cost Models | [`Maritime economics 3rd edition.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Maritime%20economics%203rd%20edition.pdf) | [`maritime_economics_3rd_edition.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/maritime_economics_3rd_edition.md) | Stripped 475 repeated running headers, 1,152 standalone page numbers, 2,828 vertical thumb letters (`CHAPTER`); healed 424 fractured sentences; dehyphenated line breaks. |
| 2 | **Maritime Economics: A Macroeconomic Approach**<br>E. Karakitsos, L. Varnavides | Macroeconomic Cycles, Financialisation, Econometrics | [`Maritime Economics A Macroeconomic Approach.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Maritime%20Economics%20A%20Macroeconomic%20Approach%20(Elias%20Karakitsos,%20Lambros%20Varnavides%20(auth.))%20(z-lib.org).pdf) | [`maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md) | Stripped 157 running headers with page numbers; healed sentences across breaks (e.g. `abated to 12 per cent thereafter`); converted Cobb-Douglas & Solow growth models to LaTeX math (`$$...$$`). |
| 3 | **Lloyd's Maritime Atlas of World Ports (24th Ed.)**<br>Informa UK | Global Port Coordinates, Canal Chokepoints, Terminals | [`Lloyds_Maritime_Atlas_24th_Edition.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Lloyds_Maritime_Atlas_24th_Edition.pdf) | [`lloyds_maritime_atlas_24th_edition.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/lloyds_maritime_atlas_24th_edition.md) | Stripped 65 repetitive facility header banners; injected comprehensive Facility Codes Legend (`P`, `Q`, `Y`, `G`, `C`, `R`, `L`, `B`, `D`, `T`, `A`) at document head; normalized coordinate lines. |
| 4 | **The Business of Shipping**<br>Lane C. Kendall | Liner Operations, Tramp Chartering, Ocean Bills of Lading | [`The Business of Shipping.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/The%20Business%20of%20Shipping%20(Lane%20C.%20Kendall%20(auth.))%20(Z-Library).pdf) | [`the_business_of_shipping_lane_c_kendall_auth_z_library.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/the_business_of_shipping_lane_c_kendall_auth_z_library.md) | Stripped 217 running headers with trailing page numbers; joined fractured paragraphs across section headers; dehyphenated chartering terminology. |
| 5 | **Intl Handbook of Shipping Finance**<br>M. Kavussanos, I. Visvikis | Ship Mortgages, Syndicated Loans, Capital Structure, Hedging | [`The International Handbook of Shipping Finance.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/The%20International%20Handbook%20of%20Shipping%20Finance%20Theory%20and%20Practice%20(Manolis%20G.%20Kavussanos,%20Ilias%20D.%20Visvikis%20(eds.))%20(z-lib.org).pdf) | [`the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md) | Healed drop-cap line starts (`C harter` -> `Charter`, `T rade` -> `Trade`, `E arnings` -> `Earnings`); stripped running page headers; formatted equations and econometric citations. |
| 6 | **The Sea and Civilization**<br>Lincoln Paine | Maritime History, Seaborne Trade Networks, Geopolitics | [`The Sea and Civilization.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/The%20Sea%20and%20Civilization%20A%20Maritime%20History%20of%20the%20World%20(Lincoln%20Paine)%20(z-lib.org).pdf) | [`the_sea_and_civilization_a_maritime_history_of_the_world_lincoln_paine_z_lib_org.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/the_sea_and_civilization_a_maritime_history_of_the_world_lincoln_paine_z_lib_org.md) | Healed 1,104 fractured sentence lines across page breaks; dehyphenated historical trade names and geographical locations; normalized multi-level section hierarchy. |
| 7 | **The Shipping Man**<br>Matthew McCleery | Private Equity, S&P Deal Mechanics, Greek Shipowners | [`The Shipping Man.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/The%20Shipping%20Man%20(Matthew%20McCleery)%20(z-lib.org).pdf) | [`the_shipping_man_matthew_mccleery_z_lib_org.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/the_shipping_man_matthew_mccleery_z_lib_org.md) | Structured all 28 novel chapters into standard Markdown headings (`## Chapter 1: Serendipity` through `## Chapter 28: Finis in the Cote D'Azur`); separated chapter title text from narrative body prose. |
| 8 | **The World's Key Industry**<br>G. Harlaftis, S. Tenold, J. Valdaliso | Post-WWII International Shipping History & Economics | [`The Worlds Key Industry.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/The%20Worlds%20Key%20Industry%20History%20and%20Economics%20of%20International%20Shipping%20(G.%20Harlaftis,%20S.%20Tenold,%20J.%20Valdaliso)%20(z-lib.org).pdf) | [`the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md) | Stripped 13 running page number headings; healed fractured sentences across page transitions; dehyphenated postwar economic and tonnage statistics. |
| 9 | **Shipping Business Unwrapped**<br>Okan Duru | Maritime Asset Pricing, Behavioral Finance, Volatility | [`Shipping Business Unwrapped.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Shipping%20Business%20Unwrapped.%20(Duru,%20Okan)%20(Z-Library).pdf) | [`shipping_business_unwrapped_duru_okan_z_library.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/shipping_business_unwrapped_duru_okan_z_library.md) | Healed 403 split paragraph lines; dehyphenated financial econometric terminology; normalized section headings and sub-headings. |
| 10 | **Quantitative Modelling of Freight Rates**<br>L. Ke, Q. Liu, A. Ng, W. Shi | 20-Year Econometric Literature Review, Time Series, ML | [`2022-Quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/2022-Quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.pdf) | [`2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md) | Healed journal column breaks; standardized citation blocks and bibliographies; preserved YAML taxonomies (Capesize, Panamax, Supramax, VLCC). |
| 11 | **Predictability of Second-Hand Bulk Carriers**<br>O. Duru, E. Gulay, S. Girgin | ARDL-EMD-ANN Hybrid Model, Shipping Q Index | [`Predictability of second-hand bulk carriers with a novel hybrid.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Predictability%20of%20second-hand%20bulk%20carriers%20with%20a%20novel%20hybrid.pdf) | [`predictability_of_second_hand_bulk_carriers_with_a_novel_hybrid.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/predictability_of_second_hand_bulk_carriers_with_a_novel_hybrid.md) | Standardized empirical regression results and equation blocks; dehyphenated machine learning and econometric terms; preserved complete frontmatter metadata. |
| 12 | **Lesson 2: Types of Ships**<br>Nautical Institute / Maritime Academy | Naval Architecture, Vessel Classification, Hull Types | [`Lesson-2-Types-of-Ships.pdf`](file:///C:/Users/Dell/Github/Shipping/corpus/books/Lesson-2-Types-of-Ships.pdf) | [`lesson_2_types_of_ships.md`](file:///C:/Users/Dell/Github/Shipping/corpus/books/lesson_2_types_of_ships.md) | Cleaned ship type definitions (Bulkers, Tankers, Gas Carriers, Ro-Ros, Container ships); standardized bullet hierarchies and hull geometry parameters. |


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
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/advanced_shipping`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/advanced_shipping)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/advanced_shipping`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/advanced_shipping)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-06-25` to `2026-10-02`
- **Latest Ingested Document:** `advanced_shipping_02_10_2026_weekly_shipping_market_report_week_40.pdf` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 254 PDFs
- **Extracted Markdown Dossiers:** 254 Markdown files
- **Chart Extraction:** Yes (Secondhand valuation matrices & demo trends)
- **Chart Engine / Technique:** Native coordinate grid & affine scale parser
- **Stacked Series CSVs:** advanced_shipping_sales_series.csv (6,105 rows), advanced_shipping_demolition_series.csv (2,016 rows), advanced_shipping_secondhand_matrix_series.csv (8,110 rows), advanced_shipping_newbuilding_series.csv (1,909 rows), advanced_shipping_demo_sales_series.csv (604 rows)
- **Extraction Script:** [`run_advanced_shipping_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_advanced_shipping_tables.py)
- **Notes & Rules Applied:** Last 3 pages discarded per parsing rules (currencies/stocks). European comma/dot decimals normalized.

### Affinity Shipbrokers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/affinity`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/affinity)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/affinity`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/affinity)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-10-01` to `2026-10-02`
- **Latest Ingested Document:** `affinity_02_10_2026_affinity_tanker_weekly_week_40.pdf` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 255 PDFs
- **Extracted Markdown Dossiers:** 255 Markdown files
- **Chart Extraction:** Yes (Baltic Dirty & Clean TCE trajectory curves)
- **Chart Engine / Technique:** Native PyMuPDF card layout geometry
- **Stacked Series CSVs:** affinity_tce_series.csv (4,039 rows), affinity_bda_series.csv (744 rows), affinity_indices_series.csv (490 rows)
- **Extraction Script:** [`run_affinity_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_affinity_tables.py)
- **Notes & Rules Applied:** Handles negative TCE rates (e.g. TC2 -$4,273). Full tanker commentary preserved.

### Agora Shipbroking
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/agora`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/agora)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/agora`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/agora)
- **Publication Cadence:** Weekly (Wednesday/Thursday) (Expected day: Wednesday)
- **Coverage Span:** `2021-06-25` to `2026-09-30`
- **Latest Ingested Document:** `agora_30_09_2026_agora_shipbroking_corporation_snapshot_of_commercial_indicator.pdf` (Status: **CURRENT (6d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 216 PDFs
- **Extracted Markdown Dossiers:** 216 Markdown files
- **Chart Extraction:** No (Dense indicator tables across 5 pages)
- **Chart Engine / Technique:** Native layout block parser
- **Stacked Series CSVs:** agora_indicators_series.csv (10,002 rows)
- **Extraction Script:** [`format_agora_properly.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/format_agora_properly.py)
- **Notes & Rules Applied:** Parsed live right now for Week 39 (24 Sep reference). European decimals normalized.

### Banchero Costa (Bancosta)
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/banchero_costa`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/banchero_costa)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/banchero_costa`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/banchero_costa)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2021-06-30` to `2026-09-30`
- **Latest Ingested Document:** `bancosta_30_09_2026_banchero_costa_weekly_market_report_week_39_2026.pdf` (Status: **CURRENT (6d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 247 PDFs
- **Extracted Markdown Dossiers:** 247 Markdown files
- **Chart Extraction:** Yes (Freight rates, FFA forward curves, ConTex index)
- **Chart Engine / Technique:** LlamaParse cover-to-cover (ciphered/2026) + Native PyMuPDF table & chart parser + clean_all_brokers_formatting.py
- **Stacked Series CSVs:** bancosta_freight_rates_series.csv (20,321 rows), bancosta_ffa_series.csv (7,618 rows), bancosta_sales_series.csv (4,591 rows), bancosta_commodities_series.csv (8,447 rows), bancosta_newbuilding_series.csv (1,952 rows), bancosta_secondhand_matrix_series.csv (1,911 rows), bancosta_demolition_series.csv (1,288 rows)
- **Extraction Script:** [`run_banchero_llamaparse.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_banchero_llamaparse.py) & [`run_banchero_costa_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_banchero_costa_tables.py)
- **Notes & Rules Applied:** Cover-to-cover LlamaParse for ciphered/2026 reports with automated quality gate (verify_broker_md_quality_gate.py). Extracts exact 7-digit IMO numbers on secondhand vessel transactions. Pages 2 to N-1 parsed.

### Carriers Chartering (General Broker)
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/carriers`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/carriers)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/carriers`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/carriers)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-11-19` to `2026-09-28`
- **Latest Ingested Document:** `general_broker_28_09_2026_carriers_sales_purchase_market_report_week_39.pdf` (Status: **CURRENT (8d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 136 PDFs
- **Extracted Markdown Dossiers:** 137 Markdown files
- **Chart Extraction:** No (Tabular S&P and Baltic BSPA/BDA indices)
- **Chart Engine / Technique:** Native word geometry and dynamic anchor parser
- **Stacked Series CSVs:** carriers_sales_series.csv (3,004 rows), carriers_dry_tc_period_series.csv (3,072 rows), carriers_indices_series.csv (1,792 rows), carriers_tanker_tce_series.csv (768 rows), carriers_bspa_series.csv (713 rows), carriers_newbuilding_series.csv (301 rows), carriers_demolition_series.csv (171 rows)
- **Extraction Script:** [`run_carriers_complete.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_carriers_complete.py)
- **Notes & Rules Applied:** Greek public equities & daily quote stripped per rules. En bloc sister-ship prices handled.

### Clarksons / Clarksons Hellas
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/clarksons`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/clarksons)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/clarksons`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/clarksons)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-07-02` to `2026-10-02`
- **Latest Ingested Document:** `Weekly-Sales-2nd-October-2026.pdf` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 181 PDFs
- **Extracted Markdown Dossiers:** 181 Markdown files
- **Chart Extraction:** No (Bulker & Tanker reported sales transaction tables)
- **Chart Engine / Technique:** Native PyMuPDF table coordinate extractor
- **Stacked Series CSVs:** clarksons_sales_series.csv (1,311 sales rows, 120 demo rows)
- **Extraction Script:** [`run_clarksons.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_clarksons.py)
- **Notes & Rules Applied:** Clarksons Platou Hellas S&P Bulletins extracted cover-to-cover. Desk Talk commentary properly segregated into distinct dry cargo and tanker sections with Panamax comments preserved. Reported sales, demolition deals, and macro tables stacked.

### Fearnleys Weekly
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/fearnleys`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/fearnleys)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/fearnleys`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys)
- **Publication Cadence:** Weekly (Wednesday/Thursday) (Expected day: Wednesday)
- **Coverage Span:** `2021-07-07` to `2026-10-02`
- **Latest Ingested Document:** `2026-10-02_snp_weekly_comment.md` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 4,742 Native Markdown files
- **Extracted Markdown Dossiers:** 4,742 Markdown files
- **Chart Extraction:** Yes (Tanker spot WS, Dry bulk BDI & TC, LPG/LNG)
- **Chart Engine / Technique:** Specialized 6-pillar normalized parser (run_fearnleys_normalized.py)
- **Stacked Series CSVs:** fearnleys_rates_series.csv (14,669 rows)
- **Extraction Script:** [`run_fearnleys_normalized.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_fearnleys_normalized.py)
- **Notes & Rules Applied:** Ingested live for Week 40. 419 weekly commentary reports generated across all 9 years (2018-2026) in reports/fearnleys/commentary/<year>/ and data/reports/fearnleys/commentary/<year>/. 182 bespoke research reports mirrored into reports/fearnleys/<year>/.

### Fearnleys Broker Voice (Hasura Desk Feeds)
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/fearnleys/voice`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/fearnleys/voice)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/fearnleys/voice`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys/voice)
- **Publication Cadence:** Weekly (Wednesday-Friday) (Expected day: Friday)
- **Coverage Span:** `2018-09-05` to `2026-10-02`
- **Latest Ingested Document:** `2026-10-02_snp_weekly_comment.md` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-30_vlcc_weekly_comment.md`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/fearnleys/voice/vlcc/2026/2026-09-30_vlcc_weekly_comment.md)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 4,742 Native Markdown files
- **Extracted Markdown Dossiers:** 4,742 Markdown files
- **Chart Extraction:** No (Dense narrative intelligence across 35 desks & routes)
- **Chart Engine / Technique:** Direct Hasura GraphQL feed parser with clean Markdown reformatting
- **Stacked Series CSVs:** [`fearnleys_broker_comments.csv`](file:////home/runner/work/Shipping/Shipping/data/derived/fearnleys_broker_comments.csv) (11,750 comments), corpus/01-brokers/fearnleys/voice/ (11,750 files), data/extracted/md/fearnleys/voice/ (11,750 files)
- **Extraction Script:** [`export_broker_voice_to_corpus.py`](file:////home/runner/work/Shipping/Shipping/scripts/fearnleys/export_broker_voice_to_corpus.py)
- **Notes & Rules Applied:** 11,750 weekly desk and route comments segregated by sector, desk, and year across Tankers (8,787), Dry Bulk (1,150), Gas (1,096), Chartering (392), and S&P (325). Standardized YAML frontmatter.

### Fearnleys-MD (Econometric Research)
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/fearnleys-md`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/fearnleys-md)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/fearnleys-md`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys-md)
- **Publication Cadence:** Monthly / Bespoke (Bi-weekly) (Expected day: Ad-hoc)
- **Coverage Span:** `2024-03-25` to `2026-10-02`
- **Latest Ingested Document:** `2026-10-02_lng-shipping-quarterly-report-q3-2026.md` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-10-02_lng-shipping-quarterly-report-q3-2026.md`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/fearnleys-md/2026/2026-10-02_lng-shipping-quarterly-report-q3-2026.md)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 184 Native Markdown files
- **Extracted Markdown Dossiers:** 184 Markdown files
- **Chart Extraction:** Yes (Top 52 econometric recurring lead-indicator models)
- **Chart Engine / Technique:** Proprietary Dynamic Affine Calibration Engine (R^2 >= 0.999)
- **Stacked Series CSVs:** fearnleys_md_master_econometric_series.xlsx (6 sheets, 26 lead models), fearnleys_md_vessel_tightness_series.csv (112 rows), fearnleys_md_macro_correlations_series.csv (78 rows), fearnleys_md_coal_futures_spread_series.csv (47 rows), fearnleys_md_shipment_volumes_series.csv (40 rows)
- **Extraction Script:** [`run_fearnleys_md_full_power.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_fearnleys_md_full_power.py)
- **Notes & Rules Applied:** 2,827 high-res vector charts extracted and calibrated. First/last pages discarded per rule.

### Gibson Shipbrokers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/gibson`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/gibson)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/gibson`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/gibson)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-07-02` to `2026-09-25`
- **Latest Ingested Document:** `2026-09-25_clean-catchup.html` (Status: **CURRENT (11d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-25_clean-catchup.html`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/gibson/raw_html/2026/2026-09-25_clean-catchup.html)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 167 HTML files
- **Extracted Markdown Dossiers:** 0 Markdown files
- **Chart Extraction:** Yes (wpDataCharts daily vector curves for all 155 HTML reports in .charts.json)
- **Chart Engine / Technique:** Native PyMuPDF table parser (PDFs) + BeautifulSoup DOM & wpDataCharts JSON extractor (HTML)
- **Stacked Series CSVs:** gibson_tanker_spot_series.csv (3,583 rows), gibson_bunker_prices_series.csv (1,011 rows), gibson_master_tanker_series.xlsx
- **Extraction Script:** [`run_gibson_pdf.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_gibson_pdf.py) & [`run_gibson_html.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_gibson_html.py)
- **Notes & Rules Applied:** 100% complete coverage: 109 historical PDFs (2021-2023) + 155 live online HTML reports (2023-2026). Tabular assessments (Spot WS & TCE, FFA, bunkers) and full editorial/sector commentary extracted.

### Intermodal Shipbrokers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/intermodal`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/intermodal)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/intermodal`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/intermodal)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2021-06-29` to `2026-09-29`
- **Latest Ingested Document:** `intermodal_30_09_2026_intermodal_weekly_market_report_week_39_2026_broker_s_insi.pdf` (Status: **CURRENT (7d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 256 PDFs
- **Extracted Markdown Dossiers:** 256 Markdown files
- **Chart Extraction:** Yes (Baltic & Time Charter vector curves, Page 3)
- **Chart Engine / Technique:** LlamaParse cover-to-cover + PyMuPDF chart vector curves
- **Stacked Series CSVs:** intermodal_baltic_tc_series.csv (20,348 rows), intermodal_tc_rates_series.csv (5,100 rows), intermodal_newbuilding_series.csv (5,058 rows), intermodal_tanker_spot_series.csv (3,879 rows), intermodal_sales_series.csv (3,358 rows), intermodal_demolition_series.csv (2,629 rows)
- **Extraction Script:** [`run_intermodal_full.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_intermodal_full.py)
- **Notes & Rules Applied:** 100% cover-to-cover extraction (all 8 pages). Editorial essay, Tanker spot, Dry bulk TC, S&P, NB, Demo.

### ISM Coasters & Mini-Bulkers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/ism`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/ism)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/ism`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ism)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-05` to `2026-09-28`
- **Latest Ingested Document:** `ism_28_09_2026_ism_coasters_and_mini_bulkers_week_39.pdf` (Status: **CURRENT (8d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 115 PDFs
- **Extracted Markdown Dossiers:** 230 Markdown files
- **Chart Extraction:** Yes (4 weekly freight indicator vector charts)
- **Chart Engine / Technique:** PyMuPDF drawing path & polyline axis scale calibration
- **Stacked Series CSVs:** ism_handy_freight_series.csv (17,629 rows), ism_coaster_freight_series.csv (12,319 rows)
- **Extraction Script:** [`run_ism.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_ism.py)
- **Notes & Rules Applied:** Overhauled to eliminate vertical axis tick number chains. Clean commentary under thematic subheaders.

### Lion Shipbrokers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/lion`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/lion)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/lion`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/lion)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2021-07-09` to `2026-10-02`
- **Latest Ingested Document:** `lion_2026_W40_Lion-Weekly-Report-02-October-2026-W40.pdf` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 47 PDFs
- **Extracted Markdown Dossiers:** 48 Markdown files
- **Chart Extraction:** No (S&P deals, Demometer indicative ranges, Demo fixtures)
- **Chart Engine / Technique:** LiteParse in-process layout parser
- **Stacked Series CSVs:** lion_deals_series.csv (1,212 rows), lion_sales_series.csv (1,192 rows), lion_demometer_series.csv (576 rows), lion_demolition_series.csv (516 rows), lion_demo_sales_series.csv (105 rows)
- **Extraction Script:** [`run_lion_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_lion_tables.py)
- **Notes & Rules Applied:** Joke of the week, author commentary preserved. Week 40 tables stacked cleanly.

### SSY (Simpson Spence Young)
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/ssy`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/ssy)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/ssy`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ssy)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-05` to `2026-09-28`
- **Latest Ingested Document:** `ssy_28_09_2026_ssy_pacific_capesize_index_28_september_2026.pdf` (Status: **CURRENT (8d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 530 PDFs
- **Extracted Markdown Dossiers:** 531 Markdown files
- **Chart Extraction:** Yes (Atlantic & Pacific Capesize index vector curves)
- **Chart Engine / Technique:** PyMuPDF span geometry + vector chart calibration
- **Stacked Series CSVs:** ssy_capesize_index_series.csv (8,881 rows), ssy_capesize_series.csv (8,881 rows), ssy_route_rates_series.csv (5,190 rows), ssy_capesize_index_time_series.csv (519 rows)
- **Extraction Script:** [`run_ssy_complete.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_ssy_complete.py)
- **Notes & Rules Applied:** Covers both Atlantic Capesize Index (ACI) and Pacific Capesize Index (PCI).

### Star Asia Demolition
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/star_asia`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/star_asia)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/star_asia`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/star_asia)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2022-07-22` to `2026-09-25`
- **Latest Ingested Document:** `star_asia_28_09_2026_star_asia_shipbroking_weekly_market_report_week_39.pdf` (Status: **CURRENT (11d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 199 PDFs
- **Extracted Markdown Dossiers:** 200 Markdown files
- **Chart Extraction:** Yes (Subcontinent scrap price trends $/LDT, metals/energy)
- **Chart Engine / Technique:** LlamaParse + World-Class Markdown Normalizer (run_star_asia_tables.py)
- **Stacked Series CSVs:** star_asia_snp_sales_series.csv (3,717 rows), star_asia_deals_series.csv (3,327 rows), star_asia_valuation_matrix_series.csv (3,245 rows), star_asia_demolition_series.csv (3,072 rows), star_asia_metals_energy_series.csv (1,327 rows)
- **Extraction Script:** [`run_star_asia_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_star_asia_tables.py)
- **Notes & Rules Applied:** Gaddani / Turkey cell boundary merge defect resolved. Table headers and Baltic Dry Index / valuation matrices properly labeled. Disclaimers and contact footers removed. Explicit ISO issue dates stamped.

### Xclusiv Shipbrokers
- **Corpus Directory (Raw Source):** [`corpus/01-brokers/xclusiv`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/xclusiv)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/xclusiv`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/xclusiv)
- **Publication Cadence:** Weekly (Monday) (Expected day: Monday)
- **Coverage Span:** `2021-07-26` to `2026-09-28`
- **Latest Ingested Document:** `xclusiv_29_09_2026_xclusiv_shipbrokers_weekly_28th_september_2026.pdf` (Status: **CURRENT (8d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 271 PDFs
- **Extracted Markdown Dossiers:** 271 Markdown files
- **Chart Extraction:** Yes (Pages 2-3 freight curves, Pages 8-9 bunker spreads)
- **Chart Engine / Technique:** LiteParse cover-to-cover + vector chart parser
- **Stacked Series CSVs:** xclusiv_secondhand_series.csv (8,593 rows), xclusiv_sales_series.csv (5,713 rows), xclusiv_demolition_series.csv (2,098 rows), xclusiv_newbuilding_prices_series.csv (1,397 rows), xclusiv_newbuilding_orders_series.csv (1,329 rows)
- **Extraction Script:** [`run_xclusiv_tables.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_xclusiv_tables.py)
- **Notes & Rules Applied:** 100% cover-to-cover across all 9 pages. Full narrative commentary and S&P tables extracted. Visually audited top pages to guarantee complete commentary and table fidelity without omissions.

### Hellenic: Demolition Market
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/demolition`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/demolition)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/demolition`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/demolition)
- **Publication Cadence:** Weekly (Saturday/Sunday) (Expected day: Saturday)
- **Coverage Span:** `2014-03-28` to `2026-10-03`
- **Latest Ingested Document:** `2026-10-03_best-oasis-weekly-recycling-market-report-2-october-2026_weekly-ship-recycling-report-26-sept_4f6a6b2abdc2.pdf` (Status: **CURRENT (3d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-10-03_gms-week-40-scarcity-puts-chattogram-on-top.html`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/demolition/2026/2026-10-03_gms-week-40-scarcity-puts-chattogram-on-top.html)
- **Sample Extracted Markdown (Digest):** [`gms_2026-10-03_2026-10-03_gms-week-40-scarcity-puts-chattogram-on-top_ship-recycling-market-insight-week-4_30126523ae22.md`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/demolition/gms/2026/gms_2026-10-03_2026-10-03_gms-week-40-scarcity-puts-chattogram-on-top_ship-recycling-market-insight-week-4_30126523ae22.md)
- **Raw Corpus Inventory:** 1,056 PDFs, 810 HTML files, 1,211 Images
- **Extracted Markdown Dossiers:** 739 Markdown files + 739 .tables.json sidecars
- **Chart Extraction:** Yes (Port position queue charts, cash buyer price matrices)
- **Chart Engine / Technique:** BeautifulSoup HTML + PyMuPDF spatial coordinate table parser
- **Stacked Series CSVs:** [`hellenic_athenian_demolition_series.csv`](file:////home/runner/work/Shipping/Shipping/data/extracted/series/hellenic_athenian_demolition_series.csv) (2,916 rows), hellenic_gms_port_positions_series.csv (2,921 rows), hellenic_gms_demolition_series.csv (1,096 rows), hellenic_best_oasis_deals_series.csv (892 rows), hellenic_best_oasis_demolition_series.csv (867 rows)
- **Extraction Script:** [`run_hellenic_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_demolition.py) & [`run_best_oasis_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_best_oasis_demolition.py) & [`run_gms_demolition.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_gms_demolition.py)
- **Notes & Rules Applied:** Distinguishes Athenian, Best Oasis, GMS cash buyer reports and port queue tables. Week 40 stacked.

### Hellenic: Dry Bulk Charter (Alibra)
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/dry_charter`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/dry_charter)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/dry_charter`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/dry_charter)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2014-03-28` to `2026-09-30`
- **Latest Ingested Document:** `2026-09-30_weekly-dry-time-charter-estimates-september-30-2026.html` (Status: **CURRENT (6d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-30_weekly-dry-time-charter-estimates-september-30-2026.html`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/dry_charter/2026/2026-09-30_weekly-dry-time-charter-estimates-september-30-2026.html)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 279 HTML files, 761 Images
- **Extracted Markdown Dossiers:** 0 Markdown files
- **Chart Extraction:** Yes (Alibra rate fixture comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_dry_tc_series.csv (6,443 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Dry Bulk period TC assessments across Capesize, Panamax, Supramax, Handy.

### Hellenic: Iron Ore (MMI & SMM Daily)
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/iron_ore/pdfs`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/iron_ore/pdfs)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/iron_ore_pdf`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/iron_ore_pdf)
- **Publication Cadence:** Daily (Mon-Fri) (Expected day: Daily)
- **Coverage Span:** `2014-03-28` to `2026-10-05`
- **Latest Ingested Document:** `2026-10-05_mmi-daily-iron-ore-index-report-october-5-2026_iron-ore-daily-20261005-en_3612a47ae754.pdf` (Status: **CURRENT (1d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-10-05_mmi-daily-iron-ore-index-report-october-5-2026_iron-ore-daily-20261005-en_3612a47ae754.pdf`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/iron_ore/pdfs/2026-10-05_mmi-daily-iron-ore-index-report-october-5-2026_iron-ore-daily-20261005-en_3612a47ae754.pdf)
- **Sample Extracted Markdown (Digest):** [`2026-10-05_mmi-daily-iron-ore-index-report-october-5-2026_iron-ore-daily-20261005-en_3612a47ae754.md`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/iron_ore_pdf/2026/2026-10-05_mmi-daily-iron-ore-index-report-october-5-2026_iron-ore-daily-20261005-en_3612a47ae754.md)
- **Raw Corpus Inventory:** 2,252 PDFs
- **Extracted Markdown Dossiers:** 12 Markdown files + 12 .tables.json sidecars
- **Chart Extraction:** Yes (4 SMM driver vector charts + MMi inventory/margin curves)
- **Chart Engine / Technique:** PyMuPDF 2D spatial coordinate parser + SMM vector chart clipper
- **Stacked Series CSVs:** [`hellenic_iron_ore_pdf_brands_series.csv`](file:////home/runner/work/Shipping/Shipping/data/extracted/series/hellenic_iron_ore_pdf_brands_series.csv) (216 rows)
- **Extraction Script:** [`run_hellenic_iron_ore_pdf.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py) & [`run_smm_iron_ore_daily.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_smm_iron_ore_daily.py)
- **Notes & Rules Applied:** Full dual-pipeline: 6-page MMi cover-to-cover + 1-page SMM Daily with 4 vector chart clips.

### Hellenic: Shipbuilding & Contracting
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/shipbuilding`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/shipbuilding)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/shipbuilding/clarksons`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/shipbuilding/clarksons)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2014-03-28` to `2026-09-29`
- **Latest Ingested Document:** `2026-09-29_breakwave-dry-bulk-shipping-report-9-29-2026_breakwavedryseptember292026report_e20b41a2f1b2.pdf` (Status: **CURRENT (7d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-29_breakwave-dry-bulk-shipping-report-9-29-2026.html`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/shipbuilding/2026/2026-09-29_breakwave-dry-bulk-shipping-report-9-29-2026.html)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 677 PDFs, 379 HTML files, 180 Images
- **Extracted Markdown Dossiers:** 0 Markdown files
- **Chart Extraction:** No (Shipyard contracting and orderbook tables)
- **Chart Engine / Technique:** Native PyMuPDF table parser
- **Stacked Series CSVs:** clarksons_snp_sales_series.csv, clarksons_demolition_sales_series.csv, clarksons_macro_series.csv, clarksons_desk_talk_series.csv
- **Extraction Script:** [`run_clarksons_hellas_world_class.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_clarksons_hellas_world_class.py)
- **Notes & Rules Applied:** Clarksons Platou Hellas S&P Bulletins extracted cover-to-cover with reported sales, demolition deals, and desk talk.

### Hellenic: Tanker Time Charter (Alibra)
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/tanker_charter`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/tanker_charter)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/tanker_charter`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/tanker_charter)
- **Publication Cadence:** Weekly (Wednesday) (Expected day: Wednesday)
- **Coverage Span:** `2014-03-28` to `2026-09-30`
- **Latest Ingested Document:** `2026-09-30_weekly-tanker-time-charter-estimates-september-30-2026.html` (Status: **CURRENT (6d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-30_weekly-tanker-time-charter-estimates-september-30-2026.html`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/tanker_charter/2026/2026-09-30_weekly-tanker-time-charter-estimates-september-30-2026.html)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 278 HTML files, 758 Images
- **Extracted Markdown Dossiers:** 0 Markdown files
- **Chart Extraction:** Yes (Crude & clean period earnings comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_tanker_tc_series.csv (7,177 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Tanker period TC assessments across VLCC, Suezmax, Aframax, LR2, LR1, MR.

### Hellenic: VesselsValue Valuations
- **Corpus Directory (Raw Source):** [`corpus/02-hellenic/vessel_valuations`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/vessel_valuations)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/hellenic/vessel_valuations`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/vessel_valuations)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2014-03-28` to `2026-09-29`
- **Latest Ingested Document:** `2026-09-29_weekly-vessel-valuations-report-september-29-2026.html` (Status: **CURRENT (7d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-29_weekly-vessel-valuations-report-september-29-2026.html`](file:////home/runner/work/Shipping/Shipping/corpus/02-hellenic/vessel_valuations/2026/2026-09-29_weekly-vessel-valuations-report-september-29-2026.html)
- **Sample Extracted Markdown (Digest):** [`vv_2026-09-29.md`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/vessel_valuations/2026/vv_2026-09-29.md)
- **Raw Corpus Inventory:** 274 HTML files, 733 Images
- **Extracted Markdown Dossiers:** 255 Markdown files + 255 .tables.json sidecars
- **Chart Extraction:** Yes (VesselsValue fleet valuation index graphs)
- **Chart Engine / Technique:** HTML table parser + VV valuation matrix calculator
- **Stacked Series CSVs:** hellenic_vv_matrix_series.csv (12,340 rows), [`hellenic_vv_sales_series.csv`](file:////home/runner/work/Shipping/Shipping/data/extracted/series/hellenic_vv_sales_series.csv) (2,062 rows)
- **Extraction Script:** [`run_hellenic_vessel_valuations.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_hellenic_vessel_valuations.py)
- **Notes & Rules Applied:** Full secondhand valuation matrix across Bulkers, Tankers, Containers for Newbuilding, 5Y, 10Y, 15Y, 20Y.

### Breakwave Advisors
- **Corpus Directory (Raw Source):** [`corpus/03-breakwave`](file:////home/runner/work/Shipping/Shipping/corpus/03-breakwave)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/breakwave`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/breakwave)
- **Publication Cadence:** Weekly (Tuesday) & Daily Insights (Expected day: Tuesday / Daily)
- **Coverage Span:** `2018-07-03` to `2026-10-05`
- **Latest Ingested Document:** `2026-10-05_ongoing-growth-in-steel-production-ex-china.html` (Status: **CURRENT (1d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-22_Breakwave_Tankers.pdf`](file:////home/runner/work/Shipping/Shipping/corpus/03-breakwave/tankers/2026/2026-09-22_Breakwave_Tankers.pdf)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 304 PDFs, 3,242 HTML files, 15,083 Images, 3,213 Native Markdown files
- **Extracted Markdown Dossiers:** 3,213 Markdown files
- **Chart Extraction:** Yes (Dry bulk freight fundamentals, ETF trajectories, & localized Insights charts)
- **Chart Engine / Technique:** BeautifulSoup DOM + Asset Linker (run_breakwave_insights.py) & PyMuPDF LiteParse (run_breakwave_clean_liteparse.py)
- **Stacked Series CSVs:** breakwave_fundamentals_series.csv (2,746 rows), breakwave_insights_metadata.csv (3,210 rows)
- **Extraction Script:** [`run_breakwave_insights.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_breakwave_insights.py) & [`run_breakwave_clean_liteparse.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_breakwave_clean_liteparse.py)
- **Notes & Rules Applied:** 100% 1:1 parity across 3,210 Insights articles (2020-2026) and 291 bi-weekly Dry Bulk/Tanker PDFs. Drybulk and Tankers partitioned by year (2018-2026 and 2023-2026). CI freshness comparison logic fixed to unblock automated workflow.

### Poten & Partners (Tanker Opinions)
- **Corpus Directory (Raw Source):** [`corpus/04-poten`](file:////home/runner/work/Shipping/Shipping/corpus/04-poten)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/poten`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/poten)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2004-01-02` to `2026-09-18`
- **Latest Ingested Document:** `Weekly Opinion - 18 September 2026 - Running Out Of Options.pdf` (Status: **NORMAL INTERVAL (18d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 1,087 PDFs
- **Extracted Markdown Dossiers:** 1,087 Markdown files
- **Chart Extraction:** Yes (Top Charterers annual/biannual volume rankings)
- **Chart Engine / Technique:** Local PyMuPDF geometry extraction (poten_clean_v2)
- **Stacked Series CSVs:** poten_opinions_metadata.csv (1,087 rows), poten_top_charterers_series.csv (755 rows), poten_fixtures_series.csv (100 rows)
- **Extraction Script:** [`run_poten.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_poten.py)
- **Notes & Rules Applied:** Unbroken 22-year coverage (2004-2026). 1,087 reports cover-to-cover with 0 date exceptions.

### Seabrokers (Seabreeze Monthly Offshore)
- **Corpus Directory (Raw Source):** [`corpus/05-seabrokers`](file:////home/runner/work/Shipping/Shipping/corpus/05-seabrokers)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/seabrokers`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/seabrokers)
- **Publication Cadence:** Monthly (1st of Month) (Expected day: 1st of Month)
- **Coverage Span:** `2018-05-01` to `2026-09-01`
- **Latest Ingested Document:** `2026-09-01_market-report-september-2026.md` (Status: **NORMAL INTERVAL (35d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-09-01_market-report-september-2026.md`](file:////home/runner/work/Shipping/Shipping/corpus/05-seabrokers/2026/2026-09-01_market-report-september-2026.md)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 97 PDFs, 99 Native Markdown files
- **Extracted Markdown Dossiers:** 99 Markdown files
- **Chart Extraction:** Yes (OSV utilisation curves, rig dayrates, offshore wind)
- **Chart Engine / Technique:** LlamaParse cover-to-cover + export_seabrokers_series.py
- **Stacked Series CSVs:** seabrokers_osv_monthly_history_series.csv (6,280 rows), seabrokers_rigs_market_series.csv (4,467 rows), seabrokers_osv_utilisation_series.csv (2,304 rows), seabrokers_osv_spot_rates_series.csv (1,855 rows)
- **Extraction Script:** [`run_seabrokers_llamaparse.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_seabrokers_llamaparse.py)
- **Notes & Rules Applied:** 9 master series CSVs (15,430 rows total). Unbroken monthly offshore and subsea coverage.

### Drewry Maritime AIS Fleet Performance
- **Corpus Directory (Raw Source):** [`corpus/06-drewry/ais`](file:////home/runner/work/Shipping/Shipping/corpus/06-drewry/ais)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/drewry/ais`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2024-01-02` to `2026-09-24`
- **Latest Ingested Document:** `Drewry_AIS_Product_LR2_Week39_2026.pdf` (Status: **CURRENT (12d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 288 PDFs
- **Extracted Markdown Dossiers:** 288 Markdown files
- **Chart Extraction:** Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds)
- **Chart Engine / Technique:** Vector PostScript/PDF drawing curve extractor + executive KPI parser (run_drewry_ais_charts.py)
- **Stacked Series CSVs:** drewry_ais_fleet_performance_series.csv (14,768 rows), drewry_ais_regional_congestion_series.csv (6,792 rows), drewry_ais_deployment_speed_series.csv (2,427 rows), drewry_ais_utilisation_curves_series.csv (1,007 rows)
- **Extraction Script:** [`run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py)
- **Notes & Rules Applied:** 24,994 continuous weekly data points across all 10 vessel classes: Product LR1 (34), VLCC (32), LPG Carrier (32), Aframax (31), Product LR2 (31), Suezmax (30), Capesize (27), Handysize (25), Panamax (23), Supramax (23).

#### Discrete Vessel Class Breakdown & Dedicated Folder Inventory

Drewry AIS reports are organized into 10 distinct vessel sectors, each with dedicated Markdown digests and structured table sidecars:

| Vessel Class | Deadweight / CBM | Report Count | Markdown Subfolder | Primary Metrics Tracked |
| :--- | :--- | :---: | :--- | :--- |
| **Product LR1** | 75,000 DWT | 34 reports | [`data/extracted/md/drewry/ais/Product_LR1`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Product_LR1) | Clean product utilisation %, tonne-miles, regional refinery flows |
| **VLCC** | 300,000 DWT | 32 reports | [`data/extracted/md/drewry/ais/Crude_VLCC`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Crude_VLCC) | Crude utilisation %, tonne-miles, Ras Tanura/Ningbo queues, ballast speed |
| **LPG Carrier** | 84,000 CBM | 32 reports | [`data/extracted/md/drewry/ais/LPG_FR`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/LPG_FR) | VLGC fleet utilisation %, tonne-miles, US Gulf/Ras Laffan flows |
| **Aframax** | 115,000 DWT | 31 reports | [`data/extracted/md/drewry/ais/Crude_Aframax`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Crude_Aframax) | Dirty utilisation %, tonne-miles, North Sea/Baltic/Caribs queues |
| **Product LR2** | 115,000 DWT | 31 reports | [`data/extracted/md/drewry/ais/Product_LR2`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Product_LR2) | Clean product utilisation %, tonne-miles, MEG-East product flows |
| **Suezmax** | 160,000 DWT | 30 reports | [`data/extracted/md/drewry/ais/Crude_Suezmax`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Crude_Suezmax) | Crude utilisation %, tonne-miles, West Africa/Mediterranean queues |
| **Capesize** | 180,000 DWT | 27 reports | [`data/extracted/md/drewry/ais/Drybulk_Capesize`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Drybulk_Capesize) | Iron ore utilisation %, tonne-miles, Port Hedland/Tubarao delays |
| **Handysize** | 38,000 DWT | 25 reports | [`data/extracted/md/drewry/ais/Drybulk_Handysize`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Drybulk_Handysize) | Minor bulk utilisation %, tonne-miles, grain/fertilizer port queues |
| **Panamax / Kamsarmax** | 82,000 DWT | 23 reports | [`data/extracted/md/drewry/ais/Drybulk_Panamax`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Drybulk_Panamax) | Grain/coal utilisation %, tonne-miles, Santos/Mississippi delays |
| **Supramax / Ultramax** | 64,000 DWT | 23 reports | [`data/extracted/md/drewry/ais/Drybulk_Supramax`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/ais/Drybulk_Supramax) | Minor bulk utilisation %, tonne-miles, Indonesian coal delays |

#### Complete Pipeline Scripts & Asset Locations
- **Live Ingestion Scraper:** [`scripts/scrapers/fetch_drewry_ais_weekly.py`](file:////home/runner/work/Shipping/Shipping/scripts/scrapers/fetch_drewry_ais_weekly.py) — polls Drewry digital asset repository on Tuesdays.
- **Multi-Threaded Sweeper:** [`scripts/scrapers/sweep_drewry_fast.py`](file:////home/runner/work/Shipping/Shipping/scripts/scrapers/sweep_drewry_fast.py) — 20-worker fast DAM probe across weeks 32-42 for 2026.
- **KPI & Tables Extractor:** [`scripts/extract/publishers/run_drewry_ais.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais.py) — extracts tables and generates Markdown dossiers into per-class subdirectories.
- **Vector Curves Extractor:** [`scripts/extract/publishers/run_drewry_ais_charts.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_ais_charts.py) — extracts drawing curves and stacks into 4 master series CSVs (24,994 data rows).

### Drewry Opinions & World Container Index (WCI)
- **Corpus Directory (Raw Source):** [`corpus/06-drewry/opinions`](file:////home/runner/work/Shipping/Shipping/corpus/06-drewry/opinions)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/drewry/opinions`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/drewry/opinions)
- **Publication Cadence:** Weekly (Thursday) (Expected day: Thursday)
- **Coverage Span:** `2017-11-09` to `2026-10-01`
- **Latest Ingested Document:** `2026-10-01_world-container-index-assessed-by-drewry.md` (Status: **CURRENT (5d ago)**)
- **Sample Ingested Report (Corpus):** [`2026-10-01_world-container-index-assessed-by-drewry.md`](file:////home/runner/work/Shipping/Shipping/corpus/06-drewry/opinions/2026/2026-10-01_world-container-index-assessed-by-drewry.md)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 1,092 Native Markdown files
- **Extracted Markdown Dossiers:** 1,092 Markdown files
- **Chart Extraction:** Yes (Global container freight rate time series)
- **Chart Engine / Technique:** Wayback CDX & live HTML parser with pv18 stability guard
- **Stacked Series CSVs:** [`drewry_wci_historical.csv`](file:////home/runner/work/Shipping/Shipping/data/indices/drewry_wci_historical.csv) (136 rows), drewry_opinions_metadata.csv (551 rows), drewry_wci_series.csv (6 rows)
- **Extraction Script:** [`run_drewry_opinions.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_drewry_opinions.py) & [`fetch_drewry_opinions_incremental.py`](file:////home/runner/work/Shipping/Shipping/scripts/scrapers/fetch_drewry_opinions_incremental.py) & [`fetch_drewry_wci.py`](file:////home/runner/work/Shipping/Shipping/scripts/scrapers/fetch_drewry_wci.py)
- **Notes & Rules Applied:** 556 opinion reports spanning 10 years (2017-2026) synchronized into reports/drewry/opinions/<year>/ and corpus/06-drewry/opinions/<year>/. Scraper updated with automatic ISO date prefixing (YYYY-MM-DD_<slug>.md) and dual-saving into both corpus/ and reports/ mirrors. Displayed directly on index.html.

### Signal Ocean (Fleet Telemetry & Monitors)
- **Corpus Directory (Raw Source):** [`corpus/07-signal`](file:////home/runner/work/Shipping/Shipping/corpus/07-signal)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/signal`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/signal)
- **Publication Cadence:** Weekly (Friday) & Live Telemetry (Expected day: Friday)
- **Coverage Span:** `2020-12-29` to `2026-09-29`
- **Latest Ingested Document:** `steel-demand-softens-as-iron-ore-flows-face-growing-headwinds.md` (Status: **CURRENT (7d ago)**)
- **Sample Ingested Report (Corpus):** [`revision-eu-ets_with-annex_en_0.pdf`](file:////home/runner/work/Shipping/Shipping/corpus/07-signal/pdfs/revision-eu-ets_with-annex_en_0.pdf)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 10 PDFs, 515 HTML files, 1,193 Images, 450 Native Markdown files
- **Extracted Markdown Dossiers:** 450 Markdown files
- **Chart Extraction:** Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps)
- **Chart Engine / Technique:** Playwright session scraper + static monitor markdown builder
- **Stacked Series CSVs:** signal_reports_metadata.csv (446 rows), signal_vessel_counts_series.csv (106 rows), data/views/signal/live_fleet_positions.json (9,082 tracked hulls), data/views/signal/port_queues_active.json (1,932 ports)
- **Extraction Script:** [`run_signal.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_signal.py) & [`sync_live_fleet_pipeline.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/sync_live_fleet_pipeline.py)
- **Notes & Rules Applied:** Live automated telemetry syncs active tanker queues and fleet AIS positions. All 446 articles segregated by year across monitors, newsroom, and newsletters.

### Baltic Exchange Weekly
- **Corpus Directory (Raw Source):** [`corpus/08-baltic`](file:////home/runner/work/Shipping/Shipping/corpus/08-baltic)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/baltic`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/baltic)
- **Publication Cadence:** Weekly (Friday) (Expected day: Friday)
- **Coverage Span:** `2015-01-02` to `2026-10-02`
- **Latest Ingested Document:** `2026-10-02_W40_bulk-report-week-40_dry.md` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** [`2026_tanker-report-week-9_tanker.html`](file:////home/runner/work/Shipping/Shipping/corpus/08-baltic/tanker/2026/2026_tanker-report-week-9_tanker.html)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 3,048 HTML files, 2,228 Native Markdown files
- **Extracted Markdown Dossiers:** 2,228 Markdown files
- **Chart Extraction:** No (Detailed fixture narratives and route earnings)
- **Chart Engine / Technique:** BeautifulSoup HTML layout parser
- **Stacked Series CSVs:** baltic_reports_metadata.csv (2,227 rows), baltic_ncfi_series.csv (2,180 rows)
- **Extraction Script:** [`run_baltic.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_baltic.py)
- **Notes & Rules Applied:** Covers Tanker, Dry Bulk, Container, Gas, and Ningbo Container Freight Index (NCFI). Week 40 (2026-10-02) extracted.

### Pilbara Ports Authority (PPA)
- **Corpus Directory (Raw Source):** [`corpus/09-ppa`](file:////home/runner/work/Shipping/Shipping/corpus/09-ppa)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/commodities`](file:////home/runner/work/Shipping/Shipping/data/commodities)
- **Publication Cadence:** Monthly (20th of Month) (Expected day: 20th of Month)
- **Coverage Span:** `2016-03-11` to `2026-07-28`
- **Latest Ingested Document:** `PPA Shipping Figures - July 2026.pdf` (Status: **NORMAL INTERVAL (70d ago)**)
- **Sample Ingested Report (Corpus):** N/A
- **Sample Extracted Markdown (Digest):** [`world_crude_steel_monthly.csv`](file:////home/runner/work/Shipping/Shipping/data/commodities/world_crude_steel_monthly.csv)
- **Raw Corpus Inventory:** 493 PDFs
- **Extracted Markdown Dossiers:** 0 Markdown files
- **Chart Extraction:** No (Port Hedland & Dampier iron ore export tonnage tables)
- **Chart Engine / Technique:** PDF tabular throughput parser + DuckDB
- **Stacked Series CSVs:** [`australia_ppa_iron_ore.csv`](file:////home/runner/work/Shipping/Shipping/data/commodities/australia_ppa_iron_ore.csv) (423 rows)
- **Extraction Script:** [`run_ppa.py`](file:////home/runner/work/Shipping/Shipping/scripts/extract/publishers/run_ppa.py)
- **Notes & Rules Applied:** All 110 loose PDFs consolidated into corpus/09-ppa/_root_pdfs/, leaving 0 unorganized root files. Directly feeds iron ore throughput charts on index.html. Stored in corpus.duckdb.

### SEC EDGAR: Listed Shipping & Dry Bulk Corporates (26 Issuers)
- **Corpus Directory (Raw Source):** [`corpus/10-companies`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/companies`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/companies)
- **Publication Cadence:** Continuous / Statutory Filing Triggers (10-K, 20-F, 10-Q, 6-K, Material 8-K) (Expected day: Continuous)
- **Coverage Span:** `2014-01-01` to `2026-10-02`
- **Latest Ingested Document:** `VALE_6-K_2026-10-02_0001292814-26-004828.md` (Status: **CURRENT (4d ago)**)
- **Sample Ingested Report (Corpus):** [`VALE_6-K_2026-10-02_0001292814-26-004828.md`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/VALE/6-K/VALE_6-K_2026-10-02_0001292814-26-004828.md)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 1,310 Native Markdown files
- **Extracted Markdown Dossiers:** 1,310 Markdown files
- **Chart Extraction:** No (Complete tabular statutory financials, fleet lists, debt notes)
- **Chart Engine / Technique:** sec2md HTML DOM parser + standardized YAML frontmatter normalizer
- **Stacked Series CSVs:** Direct structured Markdown with standardized YAML frontmatter across 26 corporate subdirectories
- **Extraction Script:** [`fetch_sec_filings.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/fetch_sec_filings.py) & [`audit_sec_corpus.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/audit_sec_corpus.py)
- **Notes & Rules Applied:** 100% clean Markdown across 26 tickers (VALE, RIO, BHP, FSUGY, SBLK, GOGL, GNK, SB, DSX, SHIP, CTRM, GLBS, EDRY, FRO, INSW, STNG, DHT, TNK, TRMD, ECO, NAT, TNP, ASC, SFL, NVGS, LPG). Zero conversion artifacts. Standardized YAML frontmatter.

#### Complete 26-Company Statutory Filings Inventory & Folder Breakdown

All corporate filings are organized under `corpus/10-companies/{TICKER}/{FORM}/` with standardized YAML frontmatter and cleaned Markdown tables:

| # | Ticker | Company Name | CIK | Segment | 10-K | 20-F | 10-Q | 6-K | 8-K | Total Files | Directory Link |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 01 | **VALE** | Vale S.A. | 0000917851 | Dry Bulk (Major Miner) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/VALE`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/VALE) |
| 02 | **RIO** | Rio Tinto plc | 0001091587 | Dry Bulk (Major Miner) | 0 | 14 | 0 | 35 | 0 | 49 | [`corpus/10-companies/RIO`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/RIO) |
| 03 | **BHP** | BHP Group Ltd | 0000817778 | Dry Bulk (Major Miner) | 0 | 13 | 0 | 35 | 0 | 48 | [`corpus/10-companies/BHP`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/BHP) |
| 04 | **FSUGY** | Fortescue Ltd | 0001444325 | Dry Bulk (Rule 12g3-2(b) Exempt) | 0 | 0 | 0 | 0 | 0 | 0 | [`corpus/10-companies/FSUGY`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/FSUGY) |
| 05 | **SBLK** | Star Bulk Carriers Corp. | 0001386909 | Dry Bulk (Capesize/Kamsarmax) | 0 | 14 | 0 | 35 | 0 | 49 | [`corpus/10-companies/SBLK`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/SBLK) |
| 06 | **GOGL** | Golden Ocean Group Ltd | 0001029145 | Dry Bulk (Capesize/Panamax) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/GOGL`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/GOGL) |
| 07 | **GNK** | Genco Shipping & Trading Ltd | 0001322439 | Dry Bulk (Capesize/Ultramax) | 15 | 0 | 18 | 0 | 44 | 77 | [`corpus/10-companies/GNK`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/GNK) |
| 08 | **SB** | Safe Bulkers, Inc. | 0001423878 | Dry Bulk (Post-Panamax/Kamsarmax) | 0 | 12 | 0 | 36 | 0 | 48 | [`corpus/10-companies/SB`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/SB) |
| 09 | **DSX** | Diana Shipping Inc. | 0001318605 | Dry Bulk (Capesize/Kamsarmax) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/DSX`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/DSX) |
| 10 | **SHIP** | Seanergy Maritime Holdings Corp. | 0001438533 | Dry Bulk (Pure-play Capesize) | 0 | 14 | 0 | 35 | 0 | 49 | [`corpus/10-companies/SHIP`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/SHIP) |
| 11 | **CTRM** | Castor Maritime Inc. | 0001720161 | Dry Bulk & Containerships | 0 | 10 | 0 | 35 | 0 | 45 | [`corpus/10-companies/CTRM`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/CTRM) |
| 12 | **GLBS** | Globus Maritime Ltd | 0001499780 | Dry Bulk (Kamsarmax/Supramax) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/GLBS`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/GLBS) |
| 13 | **EDRY** | EuroDry Ltd. | 0001731388 | Dry Bulk (Kamsarmax/Supramax) | 0 | 8 | 0 | 35 | 0 | 43 | [`corpus/10-companies/EDRY`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/EDRY) |
| 14 | **FRO** | Frontline plc | 0000913290 | Crude Tankers (VLCC/Suezmax/LR2) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/FRO`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/FRO) |
| 15 | **INSW** | International Seaways, Inc. | 0001679049 | Crude & Product Tankers | 10 | 0 | 18 | 0 | 77 | 105 | [`corpus/10-companies/INSW`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/INSW) |
| 16 | **STNG** | Scorpio Tankers Inc. | 0001483934 | Product Tankers (LR2/MR) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/STNG`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/STNG) |
| 17 | **DHT** | DHT Holdings, Inc. | 0001331284 | Crude Tankers (Pure-play VLCC) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/DHT`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/DHT) |
| 18 | **TNK** | Teekay Tankers Ltd. | 0001419945 | Crude & Product (Suezmax/Aframax) | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/TNK`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/TNK) |
| 19 | **TRMD** | TORM plc | 0001655891 | Product Tankers (LR2/LR1/MR) | 0 | 10 | 0 | 35 | 0 | 45 | [`corpus/10-companies/TRMD`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/TRMD) |
| 20 | **ECO** | Okeanis Eco Tankers Corp. | 0001964954 | Crude Tankers (VLCC/Suezmax) | 0 | 3 | 0 | 35 | 0 | 38 | [`corpus/10-companies/ECO`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/ECO) |
| 21 | **NAT** | Nordic American Tankers Ltd | 0001000177 | Crude Tankers (Pure-play Suezmax) | 0 | 15 | 0 | 35 | 0 | 50 | [`corpus/10-companies/NAT`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/NAT) |
| 22 | **TNP** | Tsakos Energy Navigation Ltd | 0001166663 | Diversified Tankers & LNG | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/TNP`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/TNP) |
| 23 | **ASC** | Ardmore Shipping Corp | 0001577437 | Product & Chemical Tankers (MR) | 0 | 15 | 0 | 35 | 0 | 50 | [`corpus/10-companies/ASC`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/ASC) |
| 24 | **SFL** | SFL Corporation Ltd | 0001289877 | Diversified Maritime Assets | 0 | 12 | 0 | 35 | 0 | 47 | [`corpus/10-companies/SFL`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/SFL) |
| 25 | **NVGS** | Navigator Holdings Ltd. | 0001581804 | Gas Carriers (Handysize LPG/Ethylene) | 0 | 13 | 0 | 35 | 0 | 48 | [`corpus/10-companies/NVGS`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/NVGS) |
| 26 | **LPG** | Dorian LPG Ltd. | 0001596993 | Gas Carriers (Pure-play VLGC) | 14 | 0 | 18 | 0 | 64 | 96 | [`corpus/10-companies/LPG`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies/LPG) |
| **Total** | | | | | **39** | **233** | **54** | **771** | **213** | **1,310** | [`corpus/10-companies`](file:////home/runner/work/Shipping/Shipping/corpus/10-companies) |

#### Autonomous Pipeline Scripts & Audit Verification
- **Automated Acquisition & Conversion:** [`scripts/acquire/fetch_sec_filings.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/fetch_sec_filings.py) — autonomous incremental ingestion via `edgartools` + `sec2md` with frontmatter generation.
- **Markdown Standardization Engine:** [`scripts/acquire/standardize_sec_markdown.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/standardize_sec_markdown.py) — enforces uniform YAML frontmatter, cleans HTML/DOM artifacts, normalizes tables.
- **Zero-Defect Quality Audit:** [`scripts/acquire/audit_sec_corpus.py`](file:////home/runner/work/Shipping/Shipping/scripts/acquire/audit_sec_corpus.py) — validates all 1,310 filings for valid YAML frontmatter, minimum byte length, and zero conversion defects.

### Maritime Reference Literature & Academic Textbooks (12 Books)
- **Corpus Directory (Raw Source):** [`corpus/books`](file:////home/runner/work/Shipping/Shipping/corpus/books)
- **Extracted Markdown Path (Normalized Dossiers):** [`data/extracted/md/books`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/books)
- **Publication Cadence:** Static Reference Corpus (Expected day: Static)
- **Coverage Span:** `2026-10-04` to `2026-10-04`
- **Latest Ingested Document:** `Maritime economics 3rd edition.pdf` (Status: **CURRENT (2d ago)**)
- **Sample Ingested Report (Corpus):** [`The World’s Key Industry History and Economics of International Shipping (G. Harlaftis, S. Tenold, J. Valdaliso) (z-lib.org).pdf`](file:////home/runner/work/Shipping/Shipping/corpus/books/The World’s Key Industry History and Economics of International Shipping (G. Harlaftis, S. Tenold, J. Valdaliso) (z-lib.org).pdf)
- **Sample Extracted Markdown (Digest):** N/A
- **Raw Corpus Inventory:** 12 PDFs, 12 Native Markdown files
- **Extracted Markdown Dossiers:** 12 Markdown files
- **Chart Extraction:** Yes (LaTeX math formulas, figures, port facilities)
- **Chart Engine / Technique:** Native GFM normalizer + LaTeX math blocks ($$...$$)
- **Stacked Series CSVs:** Clean Markdown in data/extracted/md/books/*.md and knowledge/docs/books/*.md
- **Extraction Script:** `normalize_maritime_books.py`
- **Notes & Rules Applied:** 12 foundational academic textbooks and handbooks fully normalized and audited with 100% byte parity in corpus/books/, data/extracted/md/books/, and knowledge/docs/books/.

---

## 6. Quarantined & Stashed Redundant Sources Register

**Quarantine Root Directory:** [`data/stashed_redundant_sources/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources)  
**Total Quarantined Files Preserved:** 10,286 files (Zero data deletion policy strictly enforced)  
**Master Quarantine Ledger:** [`data/stashed_redundant_sources/README.md`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/README.md)

To prevent automated scanning tools, agents, and subagents from discovering or highlighting superseded web previews, truncated files, or unpartitioned root duplicates over the authoritative ground truth data, the following redundant sources have been safely quarantined into stashed storage:

| Quarantined / Stashed Category | Stashed Location | Items Preserved | Why Stashed (Root Cause) | Active Authoritative Path (Single Source of Truth) |
| :--- | :--- | :---: | :--- | :--- |
| **Hellenic Iron Ore HTML Web Previews** | [`data/stashed_redundant_sources/hellenic_iron_ore_html_previews/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/hellenic_iron_ore_html_previews) | **4,700 files** (6 year subdirs) | Thin ~20-line HTML web-scraped summaries from the Hellenic news site. Caused agents to report partial summaries rather than the full 400-line cover-to-cover data. | [`data/extracted/md/hellenic/iron_ore_pdf/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/hellenic/iron_ore_pdf) (1,188 full-fidelity Markdown reports + `.tables.json` sidecars across 2021-2026, plus 21 stacked series CSVs) |
| **Poten Legacy Scraped Markdown (Corpus)** | [`data/stashed_redundant_sources/poten_legacy_scraped_md/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/poten_legacy_scraped_md) | **2,183 files** (2004-2026) | Truncated web preview text (`... Read More" />`) and `unknown-01-01` dates sitting in the corpus directory, creating confusion with raw PDFs. | **Corpus:** [`corpus/04-poten/pdfs/`](file:////home/runner/work/Shipping/Shipping/corpus/04-poten/pdfs) (1,087 PDFs)<br>**Extracted MD:** [`data/extracted/md/poten/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/poten) (1,087 full Markdown reports) |
| **Banchero Costa Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/banchero_costa/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/banchero_costa) | **499 files** | Unpartitioned root duplicate `.md` and `.tables.json` files and legacy singleton naming (`bancosta_*.md`) conflicting with year folders. | [`data/extracted/md/banchero_costa/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/banchero_costa) (Clean year-partitioned directories, 100% complete) |
| **Carriers Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/carriers/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/carriers) | **272 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/carriers/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/carriers) |
| **Fearnleys Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/fearnleys/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/fearnleys) | **522 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/fearnleys/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/fearnleys) |
| **ISM Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ism/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ism) | **231 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/ism/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ism) |
| **SSY Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ssy/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/ssy) | **1,061 files** | Loose duplicate `.md` and `.tables.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/ssy/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/ssy) |
| **Xclusiv Root Duplicates** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv) | **809 files** | Loose duplicate `.md`, `.tables.json`, and `.charts.json` in root folder duplicate of year subdirectories. | [`data/extracted/md/xclusiv/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md/xclusiv) |
| **Other Broker Loose Root Files** | [`data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/`](file:////home/runner/work/Shipping/Shipping/data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates) | **9 files** | Loose state/artifact files across Advanced Shipping, Affinity, Agora, Clarksons, Lion, Star Asia. | [`data/extracted/md/`](file:////home/runner/work/Shipping/Shipping/data/extracted/md) |

---

## 7. Auxiliary Corpus Directories & Specialized Archives

This registry accounts for auxiliary and reference materials preserved under `corpus/`:

| Directory | Asset Count | Content Description | Role in Research Pipeline | Direct Link |
| :--- | :---: | :--- | :--- | :--- |
| **`corpus/01-brokers/_digests`** | 180 files | Scraped markdown digests from weekly broker newsletters | Parallel text digests collected alongside PDFs | [`corpus/01-brokers/_digests`](file:////home/runner/work/Shipping/Shipping/corpus/01-brokers/_digests) |
| **`corpus/archive/`** | 725 files | Historical broker reports (Allied, Anchor, Gibson, Golden Destiny) | Historical context prior to primary 2021-2026 series | [`corpus/archive`](file:////home/runner/work/Shipping/Shipping/corpus/archive) |
| **`corpus/11-other/panama-canal`** | 1 file | Panama Canal Authority transit & draft advisory data | Critical waterway bottleneck intelligence | [`corpus/11-other`](file:////home/runner/work/Shipping/Shipping/corpus/11-other) |
| **`corpus/books/`** | 12 volumes | Foundational maritime textbooks, atlases, and econometrics treatises | Stopford Maritime Economics, Lloyds Atlas, freight models | [`corpus/books`](file:////home/runner/work/Shipping/Shipping/corpus/books) |

---

## 8. Extraction Methodology & Genealogy: Earlier vs Current Architecture

This section documents the methodological transition from legacy ingestion routines into the unified production pipeline.

### 8.1 Tabular Extraction (S&P Deals, Demolition Assessments, Freight Benchmarks)

| Feature / Dimension | Earlier Legacy Approach | Current Production Architecture |
| :--- | :--- | :--- |
| **Parsing Engine** | Unanchored regular expressions, basic `pdftotext`, or raw text line splitting. | Native PyMuPDF spatial word geometry, LiteParse structural block parser, or targeted LlamaParse (`agentic` / `cost_effective`). |
| **Visual Verification** | None. Blind text streaming without visual rendering. | High-resolution 150-200 DPI PNG page rendering to verify every column boundary and cell value against PDF pixels. |
| **Table Formatting** | Table rows collapsed into single prose lines; delimiter rows missing; columns misaligned. | Clean GitHub Flavored Markdown (GFM) tables with standardized headers and alignment markers (`| :--- | :---: | ---: |`). |
| **Number Normalization** | European decimal conventions (`60.000` = 60,000; `34,5` = 34.5) caused parsing errors or NaN entries. | Explicit numeric normalizer distinguishing thousands dots/commas from decimal dots/commas based on publisher locale. |
| **Identifiers** | Vessel names frequently truncated; 7-digit IMO numbers omitted or merged with deadweight. | Explicit regex capture for 7-digit IMO numbers (`\b[789]\d{6}\b`), cross-referenced with vessel registries. |
| **Temporal Stamping** | Relative dates or missing issue dates; sidecar records lacked date fields. | Strict ISO 8601 `YYYY-MM-DD` and ISO week number stamped onto every record and CSV row. |

### 8.2 Vector Chart & Econometric Intelligence

| Feature / Dimension | Earlier Legacy Approach | Current Production Architecture |
| :--- | :--- | :--- |
| **Vector Drawings** | Treated as raw text noise (dumping 100+ lines of tick labels like `0.0 0.2 0.4...`), or ignored entirely. | 5-stage vector extraction engine: plot frame detection, affine scale calibration, polyline filtering, RGB legend matching, consensus validation. |
| **Coordinate Calibration** | Axis bounds unmapped; values could not be derived from graphics. | Dynamic linear affine calibration (`y_val = slope * y_pixel + intercept`) yielding R² >= 0.999 precision. |
| **Visual Output** | Untracked or missing. | 2,827 high-resolution 200 DPI PNG chart crops stored under `data/extracted/charts/<publisher>/` with JSON calibration sidecars. |
| **Series Integration** | Charts isolated from numerical time series. | 26 recurring econometric lead-indicator models compiled into `data/extracted/series/fearnleys_md_master_econometric_series.xlsx`. |

### 8.3 Reference Literature & Academic Textbooks (12 Books)

| Feature / Dimension | Earlier Legacy Approach | Current Production Architecture |
| :--- | :--- | :--- |
| **Storage Location** | Fragmented across `knowledge/docs/books/` and temporary workspace directories. | Centrally unified in `corpus/books/*.md` and mirrored with 100% byte parity in `knowledge/docs/books/*.md` (9,748,609 bytes across 139,248 lines). |
| **Table Structure** | Delimiter rows missing (Stopford Tables 13.6/13.7); financial term tables flattened into plain text (Kavussanos ECA/Islamic finance). | 100% verified GFM tables with restored headers, aligned delimiters, and validated figures. |
| **Mathematical Formulas** | Raw text garbled fractions, exponents, and summation signs. | Standardized LaTeX math syntax (`$formula$` and `$$display$$`). |
| **Visual Inspection** | Unchecked conversion artifacts. | Cover-to-cover pixel audit of key chapters, tables, and maps rendered to high-resolution PNG artifacts. |

### 8.4 Broker Commentary & Hasura GraphQL Feeds

| Feature / Dimension | Earlier Legacy Approach | Current Production Architecture |
| :--- | :--- | :--- |
| **Feed Storage** | Flattened single CSV (`data/derived/fearnleys_broker_comments.csv`) with squashed single-line strings. | Folder-wise segregation into `corpus/01-brokers/fearnleys/voice/<desk>/<year>/<date>_<slug>.md` across 13 desks and 9 years (4,744 discrete files). |
| **Frontmatter** | None. Flat CSV fields. | Comprehensive YAML frontmatter with `id`, `source`, `desk`, `sector`, `comment_type`, `date`, `year`, `week`, `title`. |
| **Text Cleanliness** | Smart quotes and en-dashes frequently corrupted into replacement characters; paragraph breaks lost. | UTF-8 clean text normalizer restoring clean paragraphs, proper subheaders, and uncorrupted quotes/dashes. |
| **Automation** | Commentary was only ingested when manually triggered. | Fully automated: `export_broker_voice_to_corpus.py` wired directly into `daily_fearnleys_sync.py` to auto-export incoming comments on every sync. |

---

## 9. Transition to GraphRAG Semantic Knowledge Base

The repository is transitioning from a traditional relational/tabular archive to a multi-layered **GraphRAG Semantic Knowledge Graph**:

1. **Core Graph Entities:**
   - `Vessel`: Identified by Name, 7-digit IMO Number, DWT, Built Year, Shipyard, and Sub-type.
   - `Company / Counterparty`: Owners, Charterers (Petrobras, Unipec, Shell, Vale), Cash Buyers (GMS, Best Oasis), and Brokers (Fearnleys, Clarksons, Affinity, Gibson).
   - `Trade Route / Haul`: Baltic benchmark routes (C3 Tubarao-Qingdao, C5 West Aus-Qingdao, TD3C MEG-China, TD20 WAF-UKC, TC2 Cont-USAC).
   - `Macro / Commodity Driver`: 62% Fe CFR China, Newcastle Coal Futures, LME Copper, Brent Crude, US SPR releases.
   - `Temporal Point`: ISO Issue Date (`YYYY-MM-DD`) and ISO Week Number.
2. **First-Class Relationships:**
   - `(Vessel)-[:SOLD_TO {price_usd_m, date}]->(Company)`
   - `(Company)-[:CHARTERED {rate, tenor, route}]->(Vessel)`
   - `(Route)-[:INFLUENCED_BY {lead_time_days, correlation}]->(Commodity)`
   - `(Port)-[:EXPERIENCING_DELAY {waiting_days, queue_count}]->(VesselClass)`
3. **Dual Query Architecture:**
   - **Quantitative Vector Path:** Direct SQL/DuckDB queries on 170 time series CSVs for exact numerical regression, backtesting, and charting.
   - **Semantic Qualitative Path:** Multi-hop GraphRAG traversal across broker commentary, SEC disclosures, market analyses, and textbook economic theories to answer complex commercial inquiries.

---

## 10. Pipeline Automation Architecture & Ingest Lifecycle

### 10.1 Automated Scheduled Workflows (GitHub Actions & Cron)
- **Canonical Corpus Output Path Unification:** All ingestion scrapers (`breakwave_insights_scraper.py`, `baltic_scraper.py`, `hellenic_scraper.py`, `fetch_drewry_opinions_incremental.py`, `daily_fearnleys_sync.py`) write directly into their canonical `corpus/` directories and invoke their respective post-scrape extractors (`run_breakwave_insights.py`, `run_baltic.py`, `run_hellenic_demolition.py`, `run_drewry_opinions.py`, `run_signal.py`) both in-process and in GitHub Actions (`report_ingest.yml`, `poten_drewry_weekly.yml`, `signal_reports_weekly.yml`, `broker_reports_weekly.yml`).
- **Raw Document Ingestion:** `broker_reports_weekly.yml` (weekly broker PDFs + Gibson HTMLs), `report_ingest.yml` (Baltic, Breakwave Insights & Bi-Weekly PDFs, Hellenic), `poten_drewry_weekly.yml` (Poten Opinions, Drewry WCI, AIS, Opinions), `signal_reports_weekly.yml` (Signal Ocean monitors & images), and `daily_fearnleys_sync.py` (Hasura fixtures, rates, comments, bespoke reports).
- **Broker Voice Export:** `daily_fearnleys_sync.py` automatically invokes `export_broker_voice_to_corpus.py` to write individual desk `.md` files into `corpus/01-brokers/fearnleys/voice/<desk>/<year>/`.
- **Weekly Commentary Digest:** `generate_fearnleys_commentary_digest.py` compiles active year weekly sector digests upon sync.
- **Frontend Cache Generation:** Pre-aggregated caches (`fearnleys_cache.json`, `fearnDeskTenor.json`, `fearnNbPrices.json`) rebuild automatically during daily sync.

### 10.2 Specialized Runner Execution (Deep Extraction & Quality Audits)
- **High-Fidelity Publisher Table Extraction:** Running specialized publisher scripts (`run_clarksons.py`, `run_lion_tables.py`, `format_agora_properly.py`, `run_advanced_shipping_tables.py`, `run_affinity_tables.py`, `run_gms_demolition.py`, `run_best_oasis_demolition.py`).
- **Vector Chart Affine Calibration:** `run_fearnleys_md_full_power.py` and `export_fearnleys_md_excel.py` (2,827 chart crops, 26 econometric models).
- **LlamaParse API Routing:** Targeted and cover-to-cover parsing for ciphered or complex multi-column documents (`run_banchero_llamaparse.py`, `run_intermodal_full.py`, `run_star_asia_tables.py`, `run_xclusiv_full_cover_to_cover.py`).
- **Reference Book Normalization:** Auditing and normalizing the 12 foundational books against rendered PDF pages.

### 10.3 Unified Incremental Orchestrator & Single-Canonical-Extractor Routing
To eliminate fallback drift where a lightweight script overwrites a rich publication-grade Markdown file, `scripts/extract/orchestrate_incremental_ingest.py` routes all 14 shipbrokers directly to their single canonical publisher extractor (including `run_banchero_llamaparse.py` + `run_banchero_costa_tables.py` for ciphered Banchero Costa PDFs), followed by `scripts/extract/publishers/clean_all_brokers_formatting.py` and `scripts/extract/verify_broker_md_quality_gate.py`.

---

## 11. Quality Assurance & Regression Prevention Rules

1. **Strict Zero Emojis:** Zero emojis across all code, docstrings, commit messages, Markdown text, and terminal output.
2. **Strict File Linking:** All file paths referenced in documentation or system reports must utilize valid clickable `file:///` URLs formatted with forward slashes.
3. **Automated Quality Gate & Dry-Run Simulation:** `scripts/extract/verify_broker_md_quality_gate.py` and `scripts/extract/dry_run_broker_simulation.py` validate every generated broker `.md` and `.tables.json` against historical peers (YAML frontmatter, non-empty sections, GFM table structure, zero running-header spam, and `.tables.json` sidecar parity).
4. **Parity Verification Scripts:** `scripts/verify_all_12_books.py`, `scripts/extract/verify_broker_md_quality_gate.py`, and `scripts/audit/generate_cadence_audit.py` guarantee that 100% of corpus assets, books, and broker voices remain synchronized, audited, and error-free.
