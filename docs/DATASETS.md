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
| [`sgx_cape_futures_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_cape_futures_history.csv) | SGX Capesize FFA **Full Contract Lives** (real settlements for contracts expiring Jan 2024 onward; SGX serves zero-filled rows for older lives and the collector auto-skips them) | Jan 2024 expiries | Daily (backfill + Mon–Thu CI refresh) | Singapore Exchange (SGX) via `expansion_sgx_history_backfill.py` | Active (~119k rows; consumed by the frontend **Contract Archive** selector — lazy per-vessel-class load, session-cached) |
| [`sgx_panamax_futures_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_panamax_futures_history.csv) | SGX Panamax FFA Full Contract Lives | Jan 2024 expiries | Daily (backfill + Mon–Thu CI refresh) | Singapore Exchange (SGX) via `expansion_sgx_history_backfill.py` | Active (~37k rows) |
| [`sgx_supramax_futures_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_supramax_futures_history.csv) | SGX Supramax FFA Full Contract Lives | Jan 2024 expiries | Daily (backfill + Mon–Thu CI refresh) | Singapore Exchange (SGX) via `expansion_sgx_history_backfill.py` | Active (~122k rows) |
| [`sgx_handysize_futures_history.csv`](file:///c:/Users/Dell/Github/Shipping/data/futures/sgx_handysize_futures_history.csv) | SGX Handysize FFA Full Contract Lives | Jan 2024 expiries | Daily (backfill + Mon–Thu CI refresh) | Singapore Exchange (SGX) via `expansion_sgx_history_backfill.py` | Active (~46k rows) |

---

## 5. Expansion Collectors (`data/congestion/`, `data/macro/`, `data/bunkers/`)

Mon–Thu 05:00 UTC via `.github/workflows/data_expansion.yml`. All collectors are
idempotent upserts, retry x3 with backoff, and fail gracefully without corrupting
existing data.

| File Name | Content Description | Coverage | Frequency | Data Source | Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`data/congestion/chokepoint_transits_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/congestion/chokepoint_transits_daily.csv) | Daily transit counts across 28 maritime chokepoints (Suez, Panama, Bosporus, Malacca, ...) by vessel class | 2019-01-01 → live | Daily (incremental) | IMF PortWatch ArcGIS (`Daily_Chokepoints_Data`) via `expansion_portwatch.py` | Active (~78k rows; upstream lags ~5 days) |
| [`data/congestion/port_calls_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/congestion/port_calls_daily.csv) | Daily port call volumes for curated major ports by segment | 2026-08 window → live | Daily (incremental) | IMF PortWatch ArcGIS (`Daily_Ports_Data`) via `expansion_portwatch.py` | Active (curated set) |
| [`data/macro/commodities_monthly.csv`](file:///c:/Users/Dell/Github/Shipping/data/macro/commodities_monthly.csv) | World Bank Pink Sheet monthly commodity prices — iron ore, coal, crude, natgas, LNG, grains, metals + CMO indices. Core cargo-demand inputs for dry bulk & tanker analysis; rendered on the Signals tab as **Cargo Demand Drivers**. Series the Pink Sheet no longer publishes (all-empty columns, e.g. `coal_newcastle` after the 2026 WB series restructure) are auto-dropped from the schema on each refresh | Jan 1960 → live (monthly) | Monthly (~4th of month, prior-month data) | World Bank CMO xlsx via `expansion_worldbank_pinksheet.py` | Active (current through Jul 2026) |
| [`data/bunkers/bunker_prices_daily.csv`](file:///c:/Users/Dell/Github/Shipping/data/bunkers/bunker_prices_daily.csv) | Bunker fuel prices ($/mt): VLSFO / MGO / IFO380 across global average, regional averages and 8 major hubs (Singapore, Rotterdam, Fujairah, Houston, ...) | Live snapshots accumulate | Daily (snapshot append) | Ship & Bunker tabbed price tables via `expansion_bunker_prices.py` | Active |

> [!NOTE]
> **Retired expansion targets** (removed 2026-08-22 after source access was lost):
> OPEC MOMR appendix (Cloudflare IP-block on all opec.org routes), GMS weekly
> demolition rates (moved behind the Ship Recycling Portal login — the dashboard's
> $/LDT needs are served by `data/derived/scrappage_prices.csv` from Hellenic OCR),
> Intermodal fleet/orderbook PDFs (form-gated), and macro rates/FX (`rates_fx.csv`
> had no consumer in this shipping-focused repo).

### 5.1 Knowledge Pipeline Artifacts Consumed by the Frontend

| File | Producer | Consumer | Notes |
|:---|:---|:---|:---|
| `knowledge/chunks/index.json` | `process_knowledge.py::write_chunk_index()` (emitted after every derived rebuild) | Q&A panel shard discovery + `generate_brief.py` | Small stat-only manifest (`file/stem/year/bytes` per `.jsonl` shard). Fixes the Jan-1 year-rollover bug where hardcoded shard lists silently missed the new year's files. Frontend falls back to its static list when the manifest is absent (e.g. stale local checkout). |
| `knowledge/chunks/search/index.json` + `search/{stem}.idx.json` | `scripts/search_index_build.py` via `build_derived()` post-pass | Q&A fast-path retrieval (B1) | BM25-ready per-shard posting indexes: vocab + per-doc top-40 terms, `38.6 MB` total across 77 shards vs ~141 MB raw text. Browser ranks candidates from these first and downloads only hit shards; falls back to legacy full scan if unavailable. `i` = ordinal among parsed lines (aligned with the frontend's parsed-row arrays); per-candidate `chunk_id` verification guards against staleness. |
| `knowledge/chunks/*.jsonl` | `process_knowledge.py` | Q&A BM25 retrieval | New/reprocessed documents get sentence-aware chunk boundaries and full Breakwave bullet sentences; existing corpus is untouched until a natural re-process (no `COMPILER_VERSION` bump, avoiding a mass re-OCR run). Chunks now carry `source_url` provenance. Archived bot-challenge pages are labelled `is_error_page` and excluded from signals/derived data. Image-asset chunks may carry a `[structured table]` markdown block (B2 geometry-based table recovery) above the raw OCR text. |
| `knowledge/derived/breakwave_signals.json` | `build_derived()` | Signals tab fast path | Kept in the Pages deploy (62 KB) so production uses the relative-path load instead of the 88 MB `signals.jsonl` raw.githubusercontent fallback. |
| `knowledge/manifests/derived_cache.json`, `knowledge/derived/.wiki_*_cache.json` | `build_derived()` / `build_wiki.py` (B4) | none (local speed caches) | Content-addressed incremental-build caches, **gitignored/local-only** (~305 MB). Cold run = full rebuild (CI behavior unchanged); warm run measured 3.75× faster with byte-identical outputs. `KNOWLEDGE_FULL_DERIVED=1` bypasses. |

---

## 🛠️ Automated Health Check Command

To verify dataset freshness and staleness across all 42 files at any time:
```bash
python scripts/check_data_health.py
```
