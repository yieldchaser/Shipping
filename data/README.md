# Shipping Domain Data Architecture (`data/`)

This directory houses the structured shipping domain datasets, market telemetry, derived economic models, and front-facing view endpoints that power the application and dashboard.

---

## 1. Directory Structure & Domain Architecture

All data files in `data/` are organized into 28 domain directories with zero loose files at the root:

```
data/
├── views/           # Front-facing JSON endpoints consumed directly by index.html (59 files)
├── derived/         # Synthesized analytical matrices, time-charter models, and forward curves (94 files)
├── commodities/     # Global bulk commodity trade flows, port throughput, and queues (1,240 files)
├── indices/         # Benchmark shipping freight indices (BDI, Cape, Panamax, Tankers, WCI) (23 files)
├── etf/             # BDRY & BWET telemetry, daily holdings, liquidity, NAV, return backtests (174 files)
├── futures/         # SGX freight forward agreements, iron ore futures, forward curves (16 files)
├── flows/           # Capital flows series (all_flows_summary.json, BDRY_flows.json, BWET_flows.json) (3 files)
├── geospatial/      # AIS telemetry, Signal Ocean active hull positions, PortWatch port nodes (108 files)
├── bunkers/         # Global bunker prices, BIX index history, macro benchmarks (12 files)
├── congestion/      # Chokepoints (Suez, Panama, Bab el-Mandeb, Malacca) waiting queues (19 files)
├── supply/          # Global merchant fleet summary, fleet orderbook & age profile (2 files)
├── cargo/           # Cargo frontend summaries, trade flow matrices (3 files)
├── equities/        # Maritime public equity financials and valuation metrics (13 files)
├── cftc_statements/ # Historical CFTC Commitments of Traders statements (146 files)
├── clarksons/       # Clarksons intelligence reports and weekly market digests (65 files)
├── extracted/       # Canonical extracted markdown, 165 time-series CSVs, and DuckDB database (201,122 files)
├── ffa_live/        # Live FFA intraday ticks and recorder states (3 files)
├── macro/           # Macroeconomic commodity indicators (commodities_monthly.csv) (1 file)
├── manifests/       # Data acquisition and raw source manifests (3 files)
├── provenance/      # Audit provenance manifests and fabrication sweep logs (4 files)
├── raw/             # Raw source extracts (38 files)
├── reference/       # Baltic taxonomies, benchmark core fleet definitions (11 files)
├── reports/         # Boundary reports, bunker index articles (9 files)
├── rulebooks/       # NYMEX TD3C/TD20 and SGX freight contract specifications (3 files)
├── _quarantine/     # Quarantined envelope series (3 files)
├── audit/           # WCI real vs synthetic audit data (2 files)
├── cache/           # Historical Excel cache (1 file)
└── demolition/      # Ship & bunker demolition fixtures (1 file)
```

---

## 2. Frontend Linkages (`index.html`)

The web frontend (`index.html`) fetches data exclusively from the following domain subdirectories:

1. **`data/views/`**: Master dashboard JSON endpoints (`dashboard_master.json`, `etf_summary.json`, `port_calls_summary.json`, `vessel_valuations.json`, `signal/live_fleet_positions.json`).
2. **`data/derived/`**: Time-charter rates (`time_charter_rates.csv`, `intermodal_tc_rates.csv`, `time_charter_rates_fearnleys.csv`, `alibra_tce_matrix.json`, `tanker_forward_curves.csv`, `vessel_valuations.csv`, `iron_ore_restocking.csv`).
3. **`data/commodities/`**: Physical trade flows (`australia_ppa_iron_ore.csv`, `sgx_iron_ore_forward_curve.csv`, `usda_grain_vessel_loading_queues.csv`).
4. **`data/indices/`**: Freight benchmarks (`bdiy_historical.csv`, `cape_historical.csv`, `drewry_wci_historical.csv`, `fbx_historical.csv`).
5. **`data/etf/`**: ETF performance telemetry (`BDRY_Daily.csv`, `BWET_Daily.csv`, `live_quotes.json`, `bdry_holdings.csv`).
6. **`data/bunkers/`**: Bunker fuel pricing (`bix_history.csv`, `bunker_master_historical.csv`).
7. **`data/congestion/`**: Chokepoint transit delays and canal queues (`chokepoint_transits_daily.csv`).

---

## 3. Automated Ingestion & Live Synchronization

Key pipelines continuously update these datasets:
- **Daily Master Sync** (`.github/workflows/daily_update.yml`): Updates `indices/`, `futures/`, `flows/`, `derived/`, `bunkers/`, and calls `scripts/build_views.py` to regenerate `views/`.
- **Alibra Poller** (`.github/workflows/alibra_poller.yml`): Updates `derived/time_charter_rates.csv`, `derived/tanker_forward_curves.csv`, and `derived/alibra_tce_matrix.json`.
- **Scheduled Fleet Telemetry** (`\ShippingFleetSync` local task): Ingests 9,000+ active hull AIS coordinates into `views/signal/live_fleet_positions.json` daily at 10:00 AM IST.
- **Weekly Broker Ingest** (`.github/workflows/broker_reports_weekly.yml`): Updates `derived/intermodal_tc_rates.csv`, `clarksons/`, and `derived/scrappage_prices.csv`.
- **Upstream Commodity Flows** (`.github/workflows/upstream_commodity_flows.yml`): Updates `commodities/`, `congestion/`, `derived/`, `cargo/`, and `provenance/`.
