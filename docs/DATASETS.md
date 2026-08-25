# Shipping Repository Dataset Inventory & Data Health Documentation

This document outlines the complete dataset inventory, publishing frequencies, primary data sources, and data health status for all **42 CSV datasets** tracked in the repository as of **August 2026**.

---

## 1. Freight & Shipping Indices (`data/indices/`)

| File Name | Commodity / Vessel Class | Start Date | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`bdiy_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/bdiy_historical.csv) | Baltic Dry Index (BDI) | Jan 1985 | Daily | Baltic Exchange | Active |
| [`cape_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/cape_historical.csv) | Baltic Capesize Index | Oct 2008 | Daily | Baltic Exchange | Active |
| [`panama_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/panama_historical.csv) | Baltic Panamax Index | Oct 2008 | Daily | Baltic Exchange | Active |
| [`suprama_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/suprama_historical.csv) | Baltic Supramax Index | Oct 2008 | Daily | Baltic Exchange | Active |
| [`handysize_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/handysize_historical.csv) | Baltic Handysize Index | Oct 2008 | Daily | Baltic Exchange | Active |
| [`dirtytanker_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/dirtytanker_historical.csv) | Baltic Dirty Tanker Index (BDTI) | Dec 2007 | Daily | Baltic Exchange | Active |
| [`cleantanker_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/cleantanker_historical.csv) | Baltic Clean Tanker Index (BCTI) | Jan 2008 | Daily | Baltic Exchange | Active |
| [`blng_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blng_historical.csv) | Baltic LNG Freight Index | Jan 2019 | Daily | Baltic Exchange | Active |
| [`blpg_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blpg_historical.csv) | Baltic LPG Freight Index | Jan 2019 | Daily | Baltic Exchange | Active |
| [`fbx_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/fbx_historical.csv) | Freightos Baltic Container Index | Jan 2019 | Daily | Freightos / Baltic | Active |
| [`bai_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/bai_historical.csv) | Baltic Air Freight Index | Jan 2018 | Weekly | TAC Index / Baltic | Lagged (Weekly) |
| [`blpg_fearnleys_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blpg_fearnleys_historical.csv) | Legacy Fearnleys BLPG Index | Jan 2019 | Discontinued | Fearnleys | Legacy (Superseded by `blpg_historical.csv`) |

---

## 2. Derived Intelligence & Sector Benchmarks (`data/derived/`)

| File Name | Content Description | Start Date | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`time_charter_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/time_charter_rates.csv) | Merged Alibra/Fearnleys 1Y & 2Y TC Rates | Jan 2000 | Weekly | Alibra & Fearnleys | Active |
| [`time_charter_rates_fearnleys.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/time_charter_rates_fearnleys.csv) | Pure Fearnleys Hasura GraphQL TC Rates | Jan 2000 | Weekly | Fearnleys Hasura API | Active |
| [`vessel_valuations.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/vessel_valuations.csv) | 10Y Asset Values & Demolition Prices | Dec 1970 | Weekly | Clarksons / Fearnleys | Active |
| [`scrappage_prices.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/scrappage_prices.csv) | Demolition / Scrap Prices ($/LDT) | Jul 2021 | Weekly | GMS / Intermodal / Hellenic | Active |
| [`iron_ore_restocking.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/iron_ore_restocking.csv) | CFR 62% Iron Ore & Qingdao Port Stock | Jul 2018 | Weekly | Mysteel / S&P Global | Active |
| [`lng_charter_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/lng_charter_rates.csv) | LNG Carrier Spot & Time Charter Rates | Jan 2017 | Weekly | Spark Commodities | Active |
| [`lpg_charter_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/lpg_charter_rates.csv) | VLGC LPG Time Charter Rates | Jul 2019 | Weekly | Fearnleys / Clarksons | Active |
| [`lpg_spot_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/lpg_spot_rates.csv) | Ras Tanura to Chiba LPG Freight Rates | Jan 2004 | Weekly | Fearnleys | Active |
| [`tanker_forward_curves.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/tanker_forward_curves.csv) | Tanker FFA 22-Month Forward Term Structure | Aug 2026 | Weekly / Daily | Alibra Poller | Active |
| [`tanker_forward_curves_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/tanker_forward_curves_history.csv) | Persistent Tanker Forward Curve History | Aug 2026 | Weekly / Daily | Alibra Poller | Active |
| [`alibra_tce_matrix.json`](file:///c:/Users/Dell/Github/Shipping/data/derived/alibra_tce_matrix.json) | Live Period TCE Matrix & WoW Deltas | Aug 2026 | Weekly / Daily | Alibra Poller | Active |
| [`fearnleys_catalog.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/fearnleys_catalog.csv) | Hasura GraphQL Route Catalog | N/A | Static | Fearnleys GraphQL Schema | Static Metadata |

---

## 3. ETF Holdings, Flows & Backtests (`data/etf/`)

| File Name | Content Description | Start Date | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`bdry_liquidity.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bdry_liquidity.csv) | BDRY ETF AUM, Shares & Safe Liquidity | Mar 2018 | Daily | Breakwave / Yahoo Finance | Active |
| [`bwet_liquidity.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bwet_liquidity.csv) | BWET ETF AUM, Shares & Safe Liquidity | May 2023 | Daily | Breakwave / Yahoo Finance | Active |
| [`BDRY_flows.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/BDRY_flows.csv) | BDRY Capital Net Flows ($M) | Mar 2018 | Daily | Breakwave Advisors | Active |
| [`BWET_flows.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/BWET_flows.csv) | BWET Capital Net Flows ($M) | May 2023 | Daily | Breakwave Advisors | Active |
| [`bdry_holdings_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bdry_holdings_history.csv) | BDRY Daily Contract Basket History | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`bwet_holdings_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bwet_holdings_history.csv) | BWET Daily Contract Basket History | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`bdry_daily_dollar_decomposition.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bdry_daily_dollar_decomposition.csv) | BDRY Daily Variation Margin & PnL Attribution | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`bwet_daily_dollar_decomposition.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bwet_daily_dollar_decomposition.csv) | BWET Daily Variation Margin & PnL Attribution | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`bdry_daily_return_backtest.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bdry_daily_return_backtest.csv) | BDRY Bottom-Up vs Actual NAV Backtest | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`bwet_daily_return_backtest.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bwet_daily_return_backtest.csv) | BWET Bottom-Up vs Actual NAV Backtest | Jun 2026 | Daily | Breakwave Advisors | Active |
| [`BDRY_Daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/BDRY_Daily.csv) | Legacy BDRY P/D History | Mar 2018 | Daily | Legacy Amplify Feed | Synced from `bdry_liquidity.csv` |
| [`BWET_Daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/BWET_Daily.csv) | Legacy BWET P/D History | May 2023 | Daily | Legacy Amplify Feed | Synced from `bwet_liquidity.csv` |
| [`bdry_holdings.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bdry_holdings.csv) | Current BDRY Portfolio Snapshot | N/A | Daily | Breakwave Advisors | Static Snapshot |
| [`bwet_holdings.csv`](file:///c:/Users/Dell/Github/Shipping/data/etf/bwet_holdings.csv) | Current BWET Portfolio Snapshot | N/A | Daily | Breakwave Advisors | Static Snapshot |

---

## 4. Freight Futures / FFAs (`data/futures/`)

| File Name | Content Description | Start Date | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`bdryff_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/bdryff_history.csv) | BDRYFF Dry Bulk Forward Curve History | Feb 2010 | Daily | Breakwave / SGX | Active |
| [`bwetff_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/bwetff_history.csv) | BWETFF Tanker Forward Curve History | Dec 2016 | Daily | Breakwave / SGX | Active |
| [`sgx_cape_futures.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_cape_futures.csv) | SGX Capesize FFA Forward Curve | Dec 2024 | Daily | Singapore Exchange (SGX) | Active |
| [`sgx_panamax_futures.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_panamax_futures.csv) | SGX Panamax FFA Forward Curve | Dec 2024 | Daily | Singapore Exchange (SGX) | Active |
| [`sgx_supramax_futures.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_supramax_futures.csv) | SGX Supramax FFA Forward Curve | Aug 2024 | Daily | Singapore Exchange (SGX) | Active |
| [`sgx_handysize_futures.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_handysize_futures.csv) | SGX Handysize FFA Forward Curve | Dec 2024 | Daily | Singapore Exchange (SGX) | Active |
| [`sgx_*_futures_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_cape_futures_history.csv) | SGX FFA Full Contract Lives (4 files) | 2018 | Daily (`--rebuild` + Mon–Thu CI refresh) | Singapore Exchange (SGX) via `expansion_sgx_history_backfill.py` | Active (~324k rows) |

---

## 5. Expansion Collectors (`data/congestion/`, `data/macro/`, `data/bunkers/`)

Mon–Thu 05:00 UTC via `.github/workflows/data_expansion.yml`.

| File Name | Content Description | Coverage | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`data/congestion/chokepoint_transits_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/congestion/chokepoint_transits_daily.csv) | Daily transit counts across 28 maritime chokepoints by vessel class | 2019-01-01 → live | Daily (incremental) | IMF PortWatch ArcGIS (`Daily_Chokepoints_Data`) | Active (~78k rows) |
| [`data/congestion/port_calls_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/congestion/port_calls_daily.csv) | Daily port call volumes for curated major ports by segment | 2019 → live | Daily (incremental) | IMF PortWatch ArcGIS (`Daily_Ports_Data`) | Active (~13k rows) |
| [`data/macro/commodities_monthly.csv`](file:///c:/Users/Dell/Github/Shipping/data/macro/commodities_monthly.csv) | World Bank Pink Sheet monthly commodity prices + CMO indices | Jan 1960 → live | Monthly | World Bank CMO xlsx | Active (~800 rows) |
| [`data/bunkers/bunker_prices_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/bunkers/bunker_prices_daily.csv) | Bunker fuel prices ($/mt): VLSFO / MGO / IFO380 across 8 major hubs | Daily | Daily (snapshot append) | Ship & Bunker | Active |

---

## 6. Agricultural, Container & Multi-Broker Intelligence (`data/commodities/`, `data/indices/`, `data/derived/`)

| File Name | Content Description | Coverage | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`data/indices/drewry_wci_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/drewry_wci_historical.csv) | Drewry World Container Index (WCI) — Composite & 8 East-West routes ($/FEU) | 2019–live (~400 rows) | Weekly (Thu) | Drewry Supply Chain Advisors via `fetch_drewry_wci.py` | Active |
| [`data/commodities/usda_fas_outstanding_export_sales.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/usda_fas_outstanding_export_sales.csv) | USDA FAS Weekly Export Sales — Outstanding commitments and accumulated exports | 1999–live (10,000 rows) | Weekly (Thu) | USDA Foreign Agricultural Service Open API | Active |
| [`data/commodities/panama_canal_draft_and_slots.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/panama_canal_draft_and_slots.csv) | Panama Canal Authority (ACP) Advisories — Draft limits, Gatun Lake levels | 2022–live | Periodic | Panama Canal Authority (ACP) | Active |
| [`data/commodities/usda_us_vs_brazil_landed_costs.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/usda_us_vs_brazil_landed_costs.csv) | USDA Landed Soybean Transportation Costs ($/MT) to Shanghai (US vs Brazil) | 2005–live (650 rows) | Quarterly | USDA AgTransport Socrata Open API | Active |
| [`data/commodities/usda_grain_vessel_loading_queues.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/usda_grain_vessel_loading_queues.csv) | USDA Grain Vessel Loading Queues — In-Port, Loaded, Due counts at US Gulf & PNW | 1995–live (3,113 rows) | Weekly (Thu) | USDA AgTransport Socrata Open API | Active |
| [`data/derived/usda_grain_vessel_rates_japan.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/usda_grain_vessel_rates_japan.csv) | USDA Bulk Grain Ocean Freight Rates ($/MT) to Japan (Gulf vs PNW) | 1996–live (369 rows) | Monthly / Weekly | USDA AgTransport via `fetch_usda_grains.py` | Active |
| [`data/derived/intermodal_tc_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/intermodal_tc_rates.csv) | Intermodal Shipbrokers Weekly Period TC Rates ($/day) | 2025–live (45 rows) | Weekly (Fri) | Intermodal Research via `update_intermodal_tc_rates.py` | Active |

---

## 7. Upstream Physical Commodity Flows, Logistics & Environmental Regimes (`data/commodities/`, `data/congestion/`, `data/derived/`)

| File Name | Content Description | Coverage | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`data/commodities/brazil_comexstat_exports.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/brazil_comexstat_exports.csv) | Brazilian seaborne exports: Iron Ore, Crude Oil, Soybeans, Raw Sugar | 2018–live (416 rows) | Monthly | Brazilian MDIC / SECEX ComexStat API | Active |
| [`data/commodities/australia_ppa_iron_ore.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/australia_ppa_iron_ore.csv) | Pilbara Ports Authority iron ore throughput: Port Hedland & Dampier | 2018–live (208 rows) | Monthly | Pilbara Ports Authority (PPA) | Active |
| [`data/commodities/major_miners_quarterly_shipments.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/major_miners_quarterly_shipments.csv) | Big 4 Miners: Vale, Rio Tinto, BHP, Fortescue (Production, Shipments, C1 Cost) | 2018–live (136 rows) | Quarterly | Mining Operations Reports | Active |
| [`data/commodities/us_eia_weekly_crude_exports.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/us_eia_weekly_crude_exports.csv) | US Gulf Coast (PADD 3) & Total US weekly crude and petroleum exports | 2018–live (451 rows) | Weekly (Wed) | US Energy Information Administration (EIA) | Active |
| [`data/commodities/un_comtrade_guinea_bauxite.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/un_comtrade_guinea_bauxite.csv) | Bilateral Guinea-to-China bauxite seaborne export volumes | 2018–live (104 rows) | Monthly | UN Comtrade v1 Data API | Active |
| [`data/congestion/portwatch_port_congestion.csv`](file:///c:/Users/Dell/Github/Shipping/data/congestion/portwatch_port_congestion.csv) | 8-hub global congestion & anchorage: Qingdao, Ningbo, Rotterdam, Singapore... | 2019–live (22,344 rows) | Daily | IMF PortWatch ArcGIS Spatial AIS Layer | Active |
| [`data/derived/eu_ets_carbon_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/eu_ets_carbon_daily.csv) | EU ETS EUA spot carbon allowance, Hi-5 bunker fuel spreads, and scrubber savings | 2018–live (2,255 rows) | Daily | European Energy Exchange (EEX) / Ship & Bunker | Active |
| [`data/commodities/newcastle_coal_exports.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/newcastle_coal_exports.csv) | Australian coal shipments: Newcastle, DBCT, Gladstone | 2018–live (312 rows) | Monthly | Port Authorities | Active |
| [`data/commodities/australia_req_commodity_exports.csv`](file:///c:/Users/Dell/Github/Shipping/data/commodities/australia_req_commodity_exports.csv) | Australia DISR Resources and Energy Quarterly: Iron Ore, Coal, LNG | 2018–live (136 rows) | Quarterly | Australian DISR REQ | Active |
| [`data/derived/ton_mile_utilization_matrix.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/ton_mile_utilization_matrix.csv) | Capesize, VLCC, and Suezmax global ton-mile absorption and active fleet utilization | 2018–live (104 rows) | Monthly | Quantitative Ton-Mile Distance & Elasticity Engine | Active |

---

## 🛠️ Automated Health Check Command

To verify dataset freshness and staleness across all datasets at any time:
```bash
python scripts/check_data_health.py
```
