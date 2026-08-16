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
| [`blng_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blng_historical.csv) | Baltic LNG Freight Index | Mar 2026 | Daily | Baltic Exchange | Active |
| [`blpg_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blpg_historical.csv) | Baltic LPG Freight Index | Mar 2026 | Daily | Baltic Exchange | Active |
| [`fbx_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/fbx_historical.csv) | Freightos Baltic Container Index | Mar 2026 | Daily | Freightos / Baltic | Active |
| [`bai_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/bai_historical.csv) | Baltic Air Freight Index | Jan 2018 | Weekly | TAC Index / Baltic | Lagged (Weekly) |
| [`blpg_fearnleys_historical.csv`](file:///c:/Users/Dell/Github/Shipping/data/indices/blpg_fearnleys_historical.csv) | Legacy Fearnleys BLPG Index | Jan 2019 | Discontinued | Fearnleys | Legacy (Superseded by `blpg_historical.csv`) |

---

## 2. Derived Intelligence & Sector Benchmarks (`data/derived/`)

| File Name | Content Description | Start Date | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`time_charter_rates.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/time_charter_rates.csv) | Merged Alibra/Fearnleys 1Y & 2Y TC Rates | Jan 2000 | Weekly | Alibra & Fearnleys | Active |
| [`time_charter_rates_fearnleys.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/time_charter_rates_fearnleys.csv) | Pure Fearnleys Hasura GraphQL TC Rates | Jan 2000 | Weekly | Fearnleys Hasura API | Active |
| [`vessel_valuations.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/vessel_valuations.csv) | 10Y Asset Values & Demolition Prices | Dec 1970 | Weekly | Clarksons / Fearnleys | Active |
| [`scrappage_prices.csv`](file:///c:/Users/Dell/Github/Shipping/data/derived/scrappage_prices.csv) | Demolition / Scrap Prices ($/LDT) | Sep 2022 | Weekly | GMS / Intermodal | Active |
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

---

## 🛠️ Automated Health Check Command

To verify dataset freshness and staleness across all 42 files at any time:
```bash
python scripts/check_data_health.py
```
