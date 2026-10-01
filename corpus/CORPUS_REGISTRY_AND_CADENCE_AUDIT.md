# Master Corpus Registry, Publication Cadence & Extraction Audit

**Audit Snapshot Date:** 2026-10-01 | **Repository:** Shipping Knowledge Base  
**Authoritative Ledger:** Combines the Master Extraction Register, Live Publication Cadence, Format Breakdown, and Vector Chart Inventory across all corpus directories.

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
| **Hellenic: Dry Bulk Charter (Alibra)** | Weekly (Wednesday) | `2026-09-23` | 8d | **NORMAL INTERVAL (Week 39 expected today/tomorrow)** | 0 PDF, 278 HTML, 759 IMG | [`data/extracted/md/hellenic/dry_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/dry_charter) | Yes (Alibra rate fixture comparison graphics) | `hellenic_alibra_dry_tc_series.csv (6` |
| **Hellenic: Iron Ore (MMI Daily HTML & PDF)** | Daily (Mon-Fri) | `2026-09-28` | 3d | **CURRENT (National Day holiday in China Oct 1-7)** | 4518 PDF, 1200 HTML, 3335 IMG | [`data/extracted/md/hellenic/iron_ore`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore) | Yes (Port inventory curves, Chinese mill profit margin models) | `hellenic_iron_ore_pdf_brands_series.csv (31` |
| **Hellenic: Shipbuilding & Contracting** | Weekly (Friday) | `2026-09-29` | 2d | **CURRENT** | 1352 PDF, 379 HTML, 180 IMG | [`data/extracted/md/hellenic/shipbuilding`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/shipbuilding) | No (Shipyard contracting and orderbook tables) | `clarksons_sales_series.csv (merged)` |
| **Hellenic: Tanker Time Charter (Alibra)** | Weekly (Wednesday) | `2026-09-23` | 8d | **NORMAL INTERVAL (Week 39 expected today/tomorrow)** | 0 PDF, 277 HTML, 757 IMG | [`data/extracted/md/hellenic/tanker_charter`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/tanker_charter) | Yes (Crude & clean period earnings comparison graphics) | `hellenic_alibra_tanker_tc_series.csv (7` |
| **Hellenic: VesselsValue Valuations** | Weekly (Tuesday) | `2026-09-23` | 8d | **NORMAL INTERVAL** | 0 PDF, 273 HTML, 726 IMG | [`data/extracted/md/hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/vessel_valuations) | Yes (VesselsValue fleet valuation index graphs) | `hellenic_vv_matrix_series.csv (12` |
| **Breakwave Advisors** | Weekly (Tuesday) & Daily Insights | `2026-09-29` | 2d | **CURRENT** | 304 PDF, 3236 HTML, 15072 IMG | [`data/extracted/md/breakwave`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/breakwave) | Yes (Dry bulk freight fundamentals & ETF price trajectories) | `breakwave_fundamentals_series.csv (2` |
| **Poten & Partners (Tanker Opinions)** | Weekly (Friday) | `2026-09-18` | 13d | **NORMAL INTERVAL (Week 39 due)** | 1087 PDF, 0 HTML, 0 IMG | [`data/extracted/md/poten`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/poten) | Yes (Top Charterers annual/biannual volume rankings) | `poten_opinions_metadata.csv (1` |
| **Seabrokers (Seabreeze Monthly Offshore)** | Monthly (1st of Month) | `2026-08-01` | 61d | **NORMAL INTERVAL (Published with 3-4 week lag, Sep edition covers Aug)** | 97 PDF, 0 HTML, 0 IMG | [`data/extracted/md/seabrokers`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/seabrokers) | Yes (OSV utilisation curves, rig dayrates, offshore wind) | `seabrokers_osv_monthly_history_series.csv (6` |
| **Drewry Maritime AIS Fleet Performance** | Weekly (Tuesday) | `2026-08-18` | 44d | **NORMAL INTERVAL (Publisher batch releases monthly)** | 276 PDF, 0 HTML, 0 IMG | [`data/extracted/md/drewry/ais`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/ais) | Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds) | `drewry_ais_fleet_performance_series.csv (14` |
| **Drewry Opinions & World Container Index (WCI)** | Weekly (Thursday) | `2026-09-24` | 7d | **CURRENT (Assessed Thursdays)** | 0 PDF, 0 HTML, 0 IMG | [`data/extracted/md/drewry/opinions`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/drewry/opinions) | Yes (Global container freight rate time series) | `drewry_wci_historical.csv (122 weekly rows` |
| **Signal Ocean (Fleet Telemetry & Monitors)** | Weekly (Friday) & Live Telemetry | `2026-09-24` | 7d | **CURRENT** | 10 PDF, 514 HTML, 1885 IMG | [`data/extracted/md/signal`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/signal) | Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps) | `signal_reports_metadata.csv (442 rows)` |
| **Baltic Exchange Weekly** | Weekly (Friday) | `2026-09-25` | 6d | **CURRENT** | 0 PDF, 3043 HTML, 0 IMG | [`data/extracted/md/baltic`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/baltic) | No (Detailed fixture narratives and route earnings) | `baltic_reports_metadata.csv (2` |
| **Pilbara Ports Authority (PPA)** | Monthly (20th of Month) | `2026-07-28` | 65d | **NORMAL INTERVAL (August throughput figures published late Sep/early Oct)** | 493 PDF, 0 HTML, 0 IMG | [`data/commodities`](file:///C:/Users/Dell/Github/Shipping/data/commodities) | No (Port Hedland & Dampier iron ore export tonnage tables) | `australia_ppa_iron_ore.csv (424 rows` |

---

## 3. Comprehensive Image & Graphic Extraction Audit

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

## 4. Detailed Sector Dossiers & Verification Links

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
- **Notes & Rules Applied:** 100% cover-to-cover extraction (all 8 pages). Editorial essay, Tanker spot, Dry bulk TC, S&P, NB, Demo.

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
- **Notes & Rules Applied:** Gaddani / Turkey cell boundary merge defect resolved. Explicit ISO issue dates stamped.

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
- **Notes & Rules Applied:** 100% cover-to-cover across all 9 pages. Full narrative commentary and S&P tables extracted.

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
- **Coverage Span:** `2014-03-28` to `2026-09-23`
- **Latest Ingested Document:** `alibra_dry_2026-09-16.html` (Status: **NORMAL INTERVAL (Week 39 expected today/tomorrow)**)
- **Inventory by Format:** 0 PDFs, 278 HTML files, 759 Images, 264 Markdown files
- **Chart Extraction:** Yes (Alibra rate fixture comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_dry_tc_series.csv (6,467 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Dry Bulk period TC assessments across Capesize, Panamax, Supramax, Handy.

### Hellenic: Iron Ore (MMI Daily HTML & PDF)
- **Corpus Directory:** [`corpus/02-hellenic/iron_ore`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/iron_ore)
- **Markdown Output:** [`data/extracted/md/hellenic/iron_ore`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore)
- **Publication Cadence:** Daily (Mon-Fri) (Expected day: Daily)
- **Coverage Span:** `2014-03-28` to `2026-09-28`
- **Latest Ingested Document:** `2026-09-28_mmi-daily-iron-ore-index-report-september-28-2026_mmi-daily-iron-ore-report-for-28th-s_2c174eb1762c.pdf` (Status: **CURRENT (National Day holiday in China Oct 1-7)**)
- **Inventory by Format:** 4518 PDFs, 1200 HTML files, 3335 Images, 3537 Markdown files
- **Chart Extraction:** Yes (Port inventory curves, Chinese mill profit margin models)
- **Chart Engine / Technique:** PyMuPDF 2D spatial coordinate parser + HTML index parser
- **Stacked Series CSVs:** hellenic_iron_ore_pdf_brands_series.csv (31,272 rows), hellenic_iron_ore_daily_series.csv (1,171 rows), hellenic_capesize_c3_c5_series.csv (1,164 rows)
- **Extraction Script:** [`run_hellenic_iron_ore_pdf.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_iron_ore_pdf.py)
- **Notes & Rules Applied:** Covers 31,000+ brand assessment rows across PB fines, Newman, Carajas, lump, and pellet premiums.

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
- **Coverage Span:** `2014-03-28` to `2026-09-23`
- **Latest Ingested Document:** `alibra_wet_2026-09-16.html` (Status: **NORMAL INTERVAL (Week 39 expected today/tomorrow)**)
- **Inventory by Format:** 0 PDFs, 277 HTML files, 757 Images, 263 Markdown files
- **Chart Extraction:** Yes (Crude & clean period earnings comparison graphics)
- **Chart Engine / Technique:** HTML table & image graphic OCR parsing
- **Stacked Series CSVs:** hellenic_alibra_tanker_tc_series.csv (7,191 rows)
- **Extraction Script:** [`run_hellenic_alibra_tc.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_hellenic_alibra_tc.py)
- **Notes & Rules Applied:** Extracts 1Y, 2Y, 3Y, 5Y Tanker period TC assessments across VLCC, Suezmax, Aframax, LR2, LR1, MR.

### Hellenic: VesselsValue Valuations
- **Corpus Directory:** [`corpus/02-hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/corpus/02-hellenic/vessel_valuations)
- **Markdown Output:** [`data/extracted/md/hellenic/vessel_valuations`](file:///C:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/vessel_valuations)
- **Publication Cadence:** Weekly (Tuesday) (Expected day: Tuesday)
- **Coverage Span:** `2014-03-28` to `2026-09-23`
- **Latest Ingested Document:** `vv_2026-09-23.html` (Status: **NORMAL INTERVAL**)
- **Inventory by Format:** 0 PDFs, 273 HTML files, 726 Images, 254 Markdown files
- **Chart Extraction:** Yes (VesselsValue fleet valuation index graphs)
- **Chart Engine / Technique:** HTML table parser + VV valuation matrix calculator
- **Stacked Series CSVs:** hellenic_vv_matrix_series.csv (12,340 rows), hellenic_vv_sales_series.csv (2,114 rows)
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
- **Coverage Span:** `2024-01-02` to `2026-08-18`
- **Latest Ingested Document:** `Drewry_AIS_Product_LR2_Week33_2026.pdf` (Status: **NORMAL INTERVAL (Publisher batch releases monthly)**)
- **Inventory by Format:** 276 PDFs, 0 HTML files, 0 Images, 276 Markdown files
- **Chart Extraction:** Yes (Fleet utilisation, tonne-mile index, bunker fuel price, ballast speeds)
- **Chart Engine / Technique:** Specialized Drewry AIS parser with Executive KPI table (run_drewry_ais.py)
- **Stacked Series CSVs:** drewry_ais_fleet_performance_series.csv (14,450 rows), drewry_ais_regional_congestion_series.csv (6,540 rows), drewry_ais_deployment_speed_series.csv (2,448 rows), drewry_ais_utilisation_curves_series.csv (957 rows)
- **Extraction Script:** [`run_drewry_ais.py`](file:///C:/Users/Dell/Github/Shipping/scripts/extract/publishers/run_drewry_ais.py)
- **Notes & Rules Applied:** Overhauled to eliminate OCR noise and page break delimiters. 10 vessel classes tracked.

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
- **Inventory by Format:** 10 PDFs, 514 HTML files, 1885 Images, 456 Markdown files
- **Chart Extraction:** Yes (Bauxite/Coal/Crude flow monitors, trade flow heatmaps)
- **Chart Engine / Technique:** Playwright session scraper + static monitor markdown builder
- **Stacked Series CSVs:** signal_reports_metadata.csv (442 rows), data/views/signal/live_fleet_positions.json
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
