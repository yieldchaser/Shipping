# LEDGER 01 — FOUNDATION: INTEGRITY SYSTEM, VIEW BUILD, DESIGN SYSTEM

Execution log for Prompt 01 rebuild phases. Every step recorded as executed.

---

## STEP 1.1 — Fabrication detector
- STATUS: DONE
- FILES TOUCHED:
  - scripts/verify/check_no_fabrication.py (NEW)
  - scripts/verify/fabrication_allowlist.txt (NEW)
  - docs/megaprompts/LEDGER-01-foundation.md (NEW)
- WHAT I DID: Built the anti-fabrication scanner enforcing rules F1-F6 and orphan series detection. Scans scripts/ and bunker_pipeline/ via AST and regex to catch hardcoded series dicts (F1), silent fallback literals and assignments (F2), unverified provenance claims without network activity (F3), hardcoded timestamps (F5), and unmanifested data files fetched by index.html (Orphan series).
- VERIFY COMMAND: python scripts/verify/check_no_fabrication.py
- EXPECTED RESULT: Exits non-zero; outputs VIOLATION | FILE | LINE | SNIPPET table; confirms violations in scripts/analysis/generate_trade_envelopes.py, scripts/geospatial/build_chokepoint_cache.py, scripts/scrapers/generate_ton_mile_matrix.py, and bunker_pipeline/extractors/bunkerindex_forward.py.
- ACTUAL RESULT: Exit code 1. 171 total baseline violations detected (F1: 22, F2: 46, F3: 20, F5: 1, Orphan series: 82). Confirmed hits in all 4 required files.
- DEVIATIONS: None. All 4 required files flagged along with wider baseline catalog.

### Baseline Violation Breakdown by Category:
- F1 (Hardcoded Series): 22 violations in scripts/analysis/generate_trade_envelopes.py
- F2 (Silent Fallback Literal & Assignment): 46 violations across scripts/geospatial/build_chokepoint_cache.py, scripts/scrapers/generate_ton_mile_matrix.py, scripts/bunkers/build_bunker_cache.py, etc.
- F3 (Unverified Provenance Claims): 20 violations across bunker_pipeline/extractors/bunkerindex_forward.py, bunker_pipeline/run_pipeline.py, scripts/contract_spec_registry.py, etc.
- F5 (Hardcoded Timestamps): 1 violation in scripts/geospatial/build_chokepoint_cache.py ('generated_at': '2026-09-07')
- Orphan Series (Unregistered in manifest.json): 82 files fetched by index.html

### Full Baseline Violation Table:
`
+------------------------------------+----------------------------------------------------+------+------------------------------------------------------------+
| VIOLATION                          | FILE                                               | LINE | SNIPPET                                                    |
+------------------------------------+----------------------------------------------------+------+------------------------------------------------------------+
| F2 (Silent Fallback Literal)       | scripts/backtest_macro_health_radar.py             | 210  | 12.0 if m >= 15 else 6.0 if m >= 5 else 2.0                |
| F3 (Unverified Provenance: 'ver... | scripts/check_data_spike_health.py                 | 1    | #!/usr/bin/env python3                                     |
| F2 (Silent Fallback Literal)       | scripts/compute_port_stress_matrix.py              | 176  | mean_val = float(weekly["live_calls"].mean()) if not we... |
| F2 (Silent Fallback Literal)       | scripts/compute_port_stress_matrix.py              | 177  | std_val = float(weekly["live_calls"].std()) if len(week... |
| F3 (Unverified Provenance: 'ver... | scripts/contract_spec_registry.py                  | 1    | """                                                        |
| F3 (Unverified Provenance: 'ver... | scripts/contract_spec_registry.py                  | 24   | class UnknownContractSpecError(Exception):                 |
| F3 (Unverified Provenance: 'ver... | scripts/current_book_manual_shock.py               | 1    | """                                                        |
| F3 (Unverified Provenance: 'ver... | scripts/current_book_manual_shock.py               | 254  | def calculate_manual_contract_shock(                       |
| F3 (Unverified Provenance: 'ver... | scripts/current_book_scenario_ui.py                | 1    | """                                                        |
| F3 (Unverified Provenance: 'ver... | scripts/decision_ticket_workflow.py                | 1    | """                                                        |
| F2 (Silent Fallback Literal)       | scripts/etf_official_nav_engine.py                 | 164  | initial_nav = nav_map.get(first_date, mkt_map.get(first... |
| F2 (Silent Fallback Literal)       | scripts/etf_true_waterfall_engine.py               | 99   | multiplier = 1.0 if is_bdry else 1000.0                    |
| F2 (Silent Fallback Literal)       | scripts/extract_demolition_pdfs.py                 | 142  | max_turkey_bound = 460 if any(yr_mo in date_str for yr_... |
| F2 (Silent Fallback Literal)       | scripts/generate_brief.py                          | 1885 | read_timeout = 60 if is_free_model else 180                |
| F3 (Unverified Provenance: 'ver... | scripts/migrate_historical_archives_and_manifes... | 1    | """                                                        |
| F2 (Silent Fallback Literal)       | scripts/parse_star_asia_corpus.py                  | 269  | "cells_coverage_pct": round((c_parsed / c_exp) * 100, 2... |
| F2 (Silent Fallback Assignment)    | scripts/parse_star_asia_corpus.py                  | 82   | if rows == 0: rows = 5                                     |
| F2 (Silent Fallback Assignment)    | scripts/parse_star_asia_corpus.py                  | 86   | if rows == 0: rows = 2                                     |
| F3 (Unverified Provenance: 'ver... | scripts/production_scenario_workflow.py            | 53   | def evaluate_scenario(                                     |
| F3 (Unverified Provenance: 'ver... | scripts/run_daily_return_backtests.py              | 1    | """                                                        |
| F2 (Silent Fallback Literal)       | scripts/scenario_snapshot_schema.py                | 285  | latest_shares = 2200000 if fund == 'BDRY' else 4700000     |
| F3 (Unverified Provenance: 'ver... | scripts/scenario_snapshot_schema.py                | 180  | def generate_scenario_snapshot(                            |
| F3 (Unverified Provenance: 'ver... | scripts/test_daily_return_backtests.py             | 1    | """                                                        |
| F2 (Silent Fallback Literal)       | scripts/test_decision_ticket_workflow.py           | 107  | self._bdry_cape_prompt_price  = float(cape_pos[0]['pric... |
| F2 (Silent Fallback Literal)       | scripts/test_decision_ticket_workflow.py           | 113  | self._bwet_vlcc_prompt_price  = float(vlcc_pos[0]['pric... |
| F2 (Silent Fallback Literal)       | scripts/test_decision_ticket_workflow.py           | 115  | self._bwet_suez_prompt_price  = float(suez_pos[0]['pric... |
| F3 (Unverified Provenance: 'ver... | scripts/test_decision_ticket_workflow.py           | 1    | """                                                        |
| F3 (Unverified Provenance: 'gen... | scripts/test_evidence_and_governance.py            | 1    | """                                                        |
| F2 (Silent Fallback Literal)       | scripts/test_fetch_live_etf_quotes.py              | 32   | "price": 15.25 if ticker == "BDRY" else 410.50,            |
| F2 (Silent Fallback Literal)       | scripts/test_fetch_live_etf_quotes.py              | 33   | "previous_close": 15.00 if ticker == "BDRY" else 400.00,   |
| F2 (Silent Fallback Literal)       | scripts/test_fetch_live_etf_quotes.py              | 34   | "change": 0.25 if ticker == "BDRY" else 10.50,             |
| F2 (Silent Fallback Literal)       | scripts/test_fetch_live_etf_quotes.py              | 35   | "change_percent": 1.6667 if ticker == "BDRY" else 2.625,   |
| F3 (Unverified Provenance: 'ver... | scripts/test_seabrokers_scraper.py                 | 74   | def test_catalog_manifest():                               |
| F2 (Silent Fallback Literal)       | scripts/test_thesis_scenario_builder.py            | 57   | self._cape_prompt_price = float(cape_positions[0]['pric... |
| F2 (Silent Fallback Literal)       | scripts/test_thesis_scenario_builder.py            | 67   | self._vlcc_prompt_price  = float(vlcc_positions[0]['pri... |
| F2 (Silent Fallback Literal)       | scripts/thesis_scenario_builder.py                 | 747  | 'total_nav_dollars': 30000000.0 if fund == 'BDRY' else ... |
| F2 (Silent Fallback Literal)       | scripts/thesis_scenario_builder.py                 | 748  | 'shares_outstanding': 2169200 if fund == 'BDRY' else 44... |
| F2 (Silent Fallback Literal)       | scripts/thesis_scenario_builder.py                 | 749  | 'nav_per_share': 13.83 if fund == 'BDRY' else 339.37,      |
| F2 (Silent Fallback Literal)       | scripts/thesis_scenario_builder.py                 | 750  | 'market_price': 13.79 if fund == 'BDRY' else 357.33,       |
| F2 (Silent Fallback Literal)       | scripts/analysis/cascade_extractor_dry_run.py      | 322  | confidence = 96.0 if is_valid else 70.0                    |
| F2 (Silent Fallback Literal)       | scripts/analysis/cascade_extractor_v2.py           | 219  | annual_targets['Alang']['2024'] / 12.0 if yr == '2024' ... |
| F2 (Silent Fallback Literal)       | scripts/analysis/cascade_extractor_v2.py           | 233  | val = base_monthly * (1.3 if m in [5, 9] else 0.8)         |
| F2 (Silent Fallback Literal)       | scripts/analysis/cascade_extractor_v2.py           | 226  | annual_targets['Chattogram']['2024'] / 12.0 if yr == '2... |
| F2 (Silent Fallback Literal)       | scripts/analysis/cascade_extractor_v2.py           | 232  | annual_targets['Gadani']['2024'] / 12.0 if yr == '2024'... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 53   | BRAZIL_COMEXSTAT_HISTORICAL_KT = {                         |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 141  | GUINEA_BAUXITE_HISTORICAL_KT = {                           |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 55   | 2017: {1: 27435.2, 2: 24250.6, 3: 31210.4, 4: 26890.1, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 57   | 2018: {1: 27950.4, 2: 25110.2, 3: 28940.7, 4: 29120.5, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 59   | 2019: {1: 32410.8, 2: 28940.5, 3: 22180.2, 4: 18340.6, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 61   | 2020: {1: 26710.4, 2: 21540.8, 3: 20950.6, 4: 23980.2, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 63   | 2021: {1: 27710.5, 2: 22410.6, 3: 25780.4, 4: 24920.8, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 65   | 2022: {1: 24120.4, 2: 21540.2, 3: 24510.8, 4: 25620.4, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 67   | 2023: {1: 27010.5, 2: 22410.8, 3: 29120.4, 4: 25610.2, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 69   | 2024: {1: 26908.9, 2: 28514.2, 3: 26210.5, 4: 28710.8, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 71   | 2025: {1: 26210.4, 2: 25410.8, 3: 26510.2, 4: 29810.5, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 73   | 2026: {1: 28310.5, 2: 26710.2, 3: 26810.4, 4: 32950.8, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 143  | 2017: {1: 3850.0, 2: 4120.0, 3: 4560.0, 4: 4320.0, 5: 4... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 145  | 2018: {1: 4950.0, 2: 5120.0, 3: 5670.0, 4: 5340.0, 5: 5... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 147  | 2019: {1: 5890.0, 2: 6120.0, 3: 6780.0, 4: 6450.0, 5: 6... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 149  | 2020: {1: 6780.0, 2: 7010.0, 3: 7890.0, 4: 7450.0, 5: 7... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 151  | 2021: {1: 7500.0, 2: 6200.0, 3: 7000.0, 4: 6800.0, 5: 6... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 153  | 2022: {1: 7000.0, 2: 7400.0, 3: 8600.0, 4: 7200.0, 5: 8... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 155  | 2023: {1: 9800.0, 2: 8800.0, 3: 11000.0, 4: 11600.0, 5:... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 157  | 2024: {1: 9600.0, 2: 10100.0, 3: 13600.0, 4: 10900.0, 5... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 159  | 2025: {1: 14800.0, 2: 14500.0, 3: 15800.0, 4: 16200.0, ... |
| F1 (Hardcoded Series)              | scripts/analysis/generate_trade_envelopes.py       | 161  | 2026: {1: 17300.0, 2: 18700.0, 3: 21600.0, 4: 17800.0, ... |
| F2 (Silent Fallback Literal)       | scripts/analysis/generate_trade_envelopes.py       | 117  | months_in_year = 8 if y == 2026 else 12                    |
| F2 (Silent Fallback Literal)       | scripts/analysis/generate_trade_envelopes.py       | 203  | months_in_year = 8 if y == 2026 else 12                    |
| F2 (Silent Fallback Literal)       | scripts/bunkers/build_bunker_cache.py              | 361  | yoy_pct = round((latest_vol - float(yoy_match.values[0]... |
| F2 (Silent Fallback Literal)       | scripts/experiments/timesfm_probe_backtest.py      | 527  | horizon = kwargs.get("horizon") or (args[1] if len(args... |
| F2 (Silent Fallback Literal)       | scripts/fearnleys/build_fearnleys_cache.py         | 191  | pct_hist = float((rates < curr_val).mean() * 100.0) if ... |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_chokepoint_cache.py       | 446  | 'bab_el_mandeb_diverted_pct': red_sea_bab['baseline_cha... |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_chokepoint_cache.py       | 447  | 'suez_canal_diverted_pct': suez['baseline_change_pct'] ... |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_chokepoint_cache.py       | 448  | 'cape_of_good_hope_surge_pct': round(((cape['avg_2026']... |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_chokepoint_cache.py       | 453  | 'current_daily_avg': panama['avg_2026'] if panama else ... |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_chokepoint_cache.py       | 454  | 'baseline_daily': panama['normal_baseline_daily'] if pa... |
| F5 (Hardcoded Timestamp: 'gener... | scripts/geospatial/build_chokepoint_cache.py       | 442  | 'generated_at': '2026-09-07',                              |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_geospatial_tracker.py     | 377  | radius = 0.08 if status == "Waiting at anchor" else 0.02   |
| F2 (Silent Fallback Literal)       | scripts/geospatial/build_geospatial_tracker.py     | 310  | transit_days = (arr_date - prev_date).days if prev_date... |
| F2 (Silent Fallback Literal)       | scripts/scrapers/fetch_capital_link_indices.py     | 189  | years_lookback = 25 if backfill else 2                     |
| F2 (Silent Fallback Literal)       | scripts/scrapers/fetch_hsn_shipbrokers.py          | 262  | pages = int(sys.argv[1]) if len(sys.argv) > 1 else 3       |
| F2 (Silent Fallback Literal)       | scripts/scrapers/fetch_un_comtrade_bauxite.py      | 74   | max_m = now.month if y == now.year else 12                 |
| F2 (Silent Fallback Assignment)    | scripts/scrapers/generate_ton_mile_matrix.py       | 100  | if brazil_ore <= 0:                                        |
| F2 (Silent Fallback Assignment)    | scripts/scrapers/generate_ton_mile_matrix.py       | 105  | if guinea <= 0:                                            |
| F3 (Unverified Provenance: 'gen... | bunker_pipeline/run_pipeline.py                    | 80   | def run_forward_curves_extraction():                       |
| F3 (Unverified Provenance: 'Ver... | bunker_pipeline/extractors/bunkerindex_bix.py      | 165  | def _extract_chart_grade_blocks(html: str) -> list:        |
| F3 (Unverified Provenance: 'gen... | bunker_pipeline/extractors/bunkerindex_forward.py  | 1    | #!/usr/bin/env python3                                     |
| F3 (Unverified Provenance: 'gen... | bunker_pipeline/extractors/bunkerindex_forward.py  | 33   | def fetch_forward_month(month_offset: int, as_of_date_s... |
| F3 (Unverified Provenance: 'gen... | bunker_pipeline/extractors/bunkerindex_forward.py  | 95   | def fetch_all_forward_curves() -> pd.DataFrame:            |
| Orphan Series (Unregistered in ... | data/bunkers/bunker_frontend_summary.json          | 1    | index.html fetches 'data/bunkers/bunker_frontend_summar... |
| Orphan Series (Unregistered in ... | data/bunkers/bunker_prices_daily.csv               | 1    | index.html fetches 'data/bunkers/bunker_prices_daily.cs... |
| Orphan Series (Unregistered in ... | data/commodities/australia_ppa_iron_ore.csv        | 1    | index.html fetches 'data/commodities/australia_ppa_iron... |
| Orphan Series (Unregistered in ... | data/commodities/australia_req_commodity_export... | 1    | index.html fetches 'data/commodities/australia_req_comm... |
| Orphan Series (Unregistered in ... | data/commodities/brazil_comexstat_exports.csv      | 1    | index.html fetches 'data/commodities/brazil_comexstat_e... |
| Orphan Series (Unregistered in ... | data/commodities/major_miners_quarterly_shipmen... | 1    | index.html fetches 'data/commodities/major_miners_quart... |
| Orphan Series (Unregistered in ... | data/commodities/newcastle_coal_exports.csv        | 1    | index.html fetches 'data/commodities/newcastle_coal_exp... |
| Orphan Series (Unregistered in ... | data/commodities/sgx_iron_ore_forward_curve.csv    | 1    | index.html fetches 'data/commodities/sgx_iron_ore_forwa... |
| Orphan Series (Unregistered in ... | data/commodities/us_eia_weekly_crude_exports.csv   | 1    | index.html fetches 'data/commodities/us_eia_weekly_crud... |
| Orphan Series (Unregistered in ... | data/commodities/usda_grain_vessel_loading_queu... | 1    | index.html fetches 'data/commodities/usda_grain_vessel_... |
| Orphan Series (Unregistered in ... | data/commodities/usda_us_vs_brazil_landed_costs... | 1    | index.html fetches 'data/commodities/usda_us_vs_brazil_... |
| Orphan Series (Unregistered in ... | data/congestion/chokepoint_geo_summary.json        | 1    | index.html fetches 'data/congestion/chokepoint_geo_summ... |
| Orphan Series (Unregistered in ... | data/congestion/port_calls_daily_expanded.csv      | 1    | index.html fetches 'data/congestion/port_calls_daily_ex... |
| Orphan Series (Unregistered in ... | data/congestion/portwatch_disruptions.csv          | 1    | index.html fetches 'data/congestion/portwatch_disruptio... |
| Orphan Series (Unregistered in ... | data/congestion/portwatch_port_congestion.csv      | 1    | index.html fetches 'data/congestion/portwatch_port_cong... |
| Orphan Series (Unregistered in ... | data/derived/alibra_tce_matrix.json                | 1    | index.html fetches 'data/derived/alibra_tce_matrix.json... |
| Orphan Series (Unregistered in ... | data/derived/chokepoint_transit_metrics.csv        | 1    | index.html fetches 'data/derived/chokepoint_transit_met... |
| Orphan Series (Unregistered in ... | data/derived/eu_ets_carbon_daily.csv               | 1    | index.html fetches 'data/derived/eu_ets_carbon_daily.cs... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_dry_routes_daily.json       | 1    | index.html fetches 'data/derived/fearnleys_dry_routes_d... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_fixtures_facets.json        | 1    | index.html fetches 'data/derived/fearnleys_fixtures_fac... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_fixtures_tape.json          | 1    | index.html fetches 'data/derived/fearnleys_fixtures_tap... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_series_monthly.json         | 1    | index.html fetches 'data/derived/fearnleys_series_month... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_summary.json                | 1    | index.html fetches 'data/derived/fearnleys_summary.json... |
| Orphan Series (Unregistered in ... | data/derived/fearnleys_tanker_routes_daily.json    | 1    | index.html fetches 'data/derived/fearnleys_tanker_route... |
| Orphan Series (Unregistered in ... | data/derived/intermodal_tc_rates.csv               | 1    | index.html fetches 'data/derived/intermodal_tc_rates.cs... |
| Orphan Series (Unregistered in ... | data/derived/iron_ore_restocking.csv               | 1    | index.html fetches 'data/derived/iron_ore_restocking.cs... |
| Orphan Series (Unregistered in ... | data/derived/lng_charter_rates.csv                 | 1    | index.html fetches 'data/derived/lng_charter_rates.csv'... |
| Orphan Series (Unregistered in ... | data/derived/lpg_charter_rates.csv                 | 1    | index.html fetches 'data/derived/lpg_charter_rates.csv'... |
| Orphan Series (Unregistered in ... | data/derived/lpg_spot_rates.csv                    | 1    | index.html fetches 'data/derived/lpg_spot_rates.csv' wi... |
| Orphan Series (Unregistered in ... | data/derived/macro_health_score_backtest.csv       | 1    | index.html fetches 'data/derived/macro_health_score_bac... |
| Orphan Series (Unregistered in ... | data/derived/offshore_summary.json                 | 1    | index.html fetches 'data/derived/offshore_summary.json'... |
| Orphan Series (Unregistered in ... | data/derived/port_stress_summary.json              | 1    | index.html fetches 'data/derived/port_stress_summary.js... |
| Orphan Series (Unregistered in ... | data/derived/scrappage_prices.csv                  | 1    | index.html fetches 'data/derived/scrappage_prices.csv' ... |
| Orphan Series (Unregistered in ... | data/derived/tanker_forward_curves.csv             | 1    | index.html fetches 'data/derived/tanker_forward_curves.... |
| Orphan Series (Unregistered in ... | data/derived/tanker_forward_curves_history.csv     | 1    | index.html fetches 'data/derived/tanker_forward_curves_... |
| Orphan Series (Unregistered in ... | data/derived/time_charter_rates.csv                | 1    | index.html fetches 'data/derived/time_charter_rates.csv... |
| Orphan Series (Unregistered in ... | data/derived/time_charter_rates_fearnleys.csv      | 1    | index.html fetches 'data/derived/time_charter_rates_fea... |
| Orphan Series (Unregistered in ... | data/derived/ton_mile_utilization_matrix.csv       | 1    | index.html fetches 'data/derived/ton_mile_utilization_m... |
| Orphan Series (Unregistered in ... | data/derived/usda_bunker_fuel_daily.csv            | 1    | index.html fetches 'data/derived/usda_bunker_fuel_daily... |
| Orphan Series (Unregistered in ... | data/derived/usda_grain_vessel_rates_japan.csv     | 1    | index.html fetches 'data/derived/usda_grain_vessel_rate... |
| Orphan Series (Unregistered in ... | data/derived/vessel_valuations.csv                 | 1    | index.html fetches 'data/derived/vessel_valuations.csv'... |
| Orphan Series (Unregistered in ... | data/etf/BDRY_Daily.csv                            | 1    | index.html fetches 'data/etf/BDRY_Daily.csv' with no re... |
| Orphan Series (Unregistered in ... | data/etf/BDRY_flows.csv                            | 1    | index.html fetches 'data/etf/BDRY_flows.csv' with no re... |
| Orphan Series (Unregistered in ... | data/etf/BWET_Daily.csv                            | 1    | index.html fetches 'data/etf/BWET_Daily.csv' with no re... |
| Orphan Series (Unregistered in ... | data/etf/BWET_flows.csv                            | 1    | index.html fetches 'data/etf/BWET_flows.csv' with no re... |
| Orphan Series (Unregistered in ... | data/etf/bdry_holdings.csv                         | 1    | index.html fetches 'data/etf/bdry_holdings.csv' with no... |
| Orphan Series (Unregistered in ... | data/etf/bdry_holdings_history.csv                 | 1    | index.html fetches 'data/etf/bdry_holdings_history.csv'... |
| Orphan Series (Unregistered in ... | data/etf/bdry_liquidity.csv                        | 1    | index.html fetches 'data/etf/bdry_liquidity.csv' with n... |
| Orphan Series (Unregistered in ... | data/etf/bwet_holdings.csv                         | 1    | index.html fetches 'data/etf/bwet_holdings.csv' with no... |
| Orphan Series (Unregistered in ... | data/etf/bwet_holdings_history.csv                 | 1    | index.html fetches 'data/etf/bwet_holdings_history.csv'... |
| Orphan Series (Unregistered in ... | data/etf/bwet_liquidity.csv                        | 1    | index.html fetches 'data/etf/bwet_liquidity.csv' with n... |
| Orphan Series (Unregistered in ... | data/etf/live_quotes.json                          | 1    | index.html fetches 'data/etf/live_quotes.json' with no ... |
| Orphan Series (Unregistered in ... | data/etf/snapshots/scenario_snapshots.js           | 1    | index.html fetches 'data/etf/snapshots/scenario_snapsho... |
| Orphan Series (Unregistered in ... | data/futures/bdryff_history.csv                    | 1    | index.html fetches 'data/futures/bdryff_history.csv' wi... |
| Orphan Series (Unregistered in ... | data/futures/bwetff_history.csv                    | 1    | index.html fetches 'data/futures/bwetff_history.csv' wi... |
| Orphan Series (Unregistered in ... | data/futures/sgx_cape_futures.csv                  | 1    | index.html fetches 'data/futures/sgx_cape_futures.csv' ... |
| Orphan Series (Unregistered in ... | data/futures/sgx_handysize_futures.csv             | 1    | index.html fetches 'data/futures/sgx_handysize_futures.... |
| Orphan Series (Unregistered in ... | data/futures/sgx_iron_ore_fef.csv                  | 1    | index.html fetches 'data/futures/sgx_iron_ore_fef.csv' ... |
| Orphan Series (Unregistered in ... | data/futures/sgx_iron_ore_lump_lpf.csv             | 1    | index.html fetches 'data/futures/sgx_iron_ore_lump_lpf.... |
| Orphan Series (Unregistered in ... | data/futures/sgx_iron_ore_m65f.csv                 | 1    | index.html fetches 'data/futures/sgx_iron_ore_m65f.csv'... |
| Orphan Series (Unregistered in ... | data/futures/sgx_panamax_futures.csv               | 1    | index.html fetches 'data/futures/sgx_panamax_futures.cs... |
| Orphan Series (Unregistered in ... | data/futures/sgx_supramax_futures.csv              | 1    | index.html fetches 'data/futures/sgx_supramax_futures.c... |
| Orphan Series (Unregistered in ... | data/geospatial/portwatch_ports_master.csv         | 1    | index.html fetches 'data/geospatial/portwatch_ports_mas... |
| Orphan Series (Unregistered in ... | data/geospatial/voyage_history_fixturegrounded.csv | 1    | index.html fetches 'data/geospatial/voyage_history_fixt... |
| Orphan Series (Unregistered in ... | data/indices/bdiy_historical.csv                   | 1    | index.html fetches 'data/indices/bdiy_historical.csv' w... |
| Orphan Series (Unregistered in ... | data/indices/blpg_historical.csv                   | 1    | index.html fetches 'data/indices/blpg_historical.csv' w... |
| Orphan Series (Unregistered in ... | data/indices/cape_historical.csv                   | 1    | index.html fetches 'data/indices/cape_historical.csv' w... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_container_clci.csv       | 1    | index.html fetches 'data/indices/capital_link_container... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_drybulk_cldbi.csv        | 1    | index.html fetches 'data/indices/capital_link_drybulk_c... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_lng_lpg_cllg.csv         | 1    | index.html fetches 'data/indices/capital_link_lng_lpg_c... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_maritime_clmi.csv        | 1    | index.html fetches 'data/indices/capital_link_maritime_... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_mixed_fleet_clmfi.csv    | 1    | index.html fetches 'data/indices/capital_link_mixed_fle... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_mlp_clmlp.csv            | 1    | index.html fetches 'data/indices/capital_link_mlp_clmlp... |
| Orphan Series (Unregistered in ... | data/indices/capital_link_tanker_clti.csv          | 1    | index.html fetches 'data/indices/capital_link_tanker_cl... |
| Orphan Series (Unregistered in ... | data/indices/cleantanker_historical.csv            | 1    | index.html fetches 'data/indices/cleantanker_historical... |
| Orphan Series (Unregistered in ... | data/indices/dirtytanker_historical.csv            | 1    | index.html fetches 'data/indices/dirtytanker_historical... |
| Orphan Series (Unregistered in ... | data/indices/drewry_wci_historical.csv             | 1    | index.html fetches 'data/indices/drewry_wci_historical.... |
| Orphan Series (Unregistered in ... | data/indices/fbx_historical.csv                    | 1    | index.html fetches 'data/indices/fbx_historical.csv' wi... |
| Orphan Series (Unregistered in ... | data/indices/handysize_historical.csv              | 1    | index.html fetches 'data/indices/handysize_historical.c... |
| Orphan Series (Unregistered in ... | data/indices/panama_historical.csv                 | 1    | index.html fetches 'data/indices/panama_historical.csv'... |
| Orphan Series (Unregistered in ... | data/indices/suprama_historical.csv                | 1    | index.html fetches 'data/indices/suprama_historical.csv... |
| Orphan Series (Unregistered in ... | data/macro/commodities_monthly.csv                 | 1    | index.html fetches 'data/macro/commodities_monthly.csv'... |
+------------------------------------+----------------------------------------------------+------+------------------------------------------------------------+

Total violations found: 171
```

---

## STEP 1.2 — Provenance registry
- STATUS: DONE
- FILES TOUCHED:
  - scripts/verify/build_provenance_manifest.py (NEW)
  - data/provenance/manifest.json (NEW)
  - docs/megaprompts/LEDGER-01-foundation.md (MODIFIED)
- WHAT I DID: Created `scripts/verify/build_provenance_manifest.py` which extracts all 82 distinct data paths fetched by `index.html`, resolves their upstream data sources, URLs, fetch methods, and producing scripts across `scripts/` and workflows, reads exact row counts and date spans from disk, and writes `data/provenance/manifest.json` following the GUARDRAILS §0.3 schema.
- VERIFY COMMAND: `python scripts/verify/build_provenance_manifest.py`
- EXPECTED RESULT: Generates `data/provenance/manifest.json` registering all fetched series with status, source, span, and row count; flags unregistered files.
- ACTUAL RESULT: Generated `data/provenance/manifest.json` with 82 registered series (74 LIVE, 4 ESTIMATED, 4 UNREGISTERED). Running `python scripts/verify/check_no_fabrication.py` confirms 0 Orphan Series remain (down from 82).
- DEVIATIONS: None.

### Series Status Breakdown in Manifest:
- LIVE: 74 series
- ESTIMATED: 4 series (diagnostic/model series: `ton_mile_utilization_matrix.csv`, `major_miners_quarterly_shipments.csv`, `macro_health_score_backtest.csv`, `port_stress_summary.json`)
- UNREGISTERED: 4 series (see below)

### Files Tagged as UNREGISTERED:
These are files loaded by `index.html` that have no producing/scraping script in the repository:
1. `data/derived/chokepoint_transit_metrics.csv`
   - Description: Static 11-row summary of maritime chokepoints with pre-disruption baseline counts and diverted percentages.
   - Provenance gap: Loaded in `index.html` (line 20042) and verified by `test_question_routing_and_grounding.py`, but never written by any pipeline in `scripts/`.
2. `data/derived/lng_charter_rates.csv`
   - Description: LNG 7Y/10Y Time Charter rates ($/day) and Newbuilding prices ($M) from 2017-01-05.
   - Provenance gap: Read by `scripts/fearnleys/build_desk_caches.py` and `scripts/generate_brief.py`, but no active pipeline script scrapes or updates it (legacy static backfill).
3. `data/derived/lpg_charter_rates.csv`
   - Description: LPG 1Y TC Rates ($/month) across VLGC 84k, MGC 38k, Handy 22k from 2019-07-01.
   - Provenance gap: Read by `scripts/fearnleys/build_desk_caches.py` and `scripts/generate_brief.py`, but no active pipeline script scrapes or updates it (legacy static backfill).
4. `data/derived/lpg_spot_rates.csv`
   - Description: LPG Spot Rates ($/day) across VLGC spot and MGC spot from 2004-01-07.
   - Provenance gap: Read by `scripts/fearnleys/build_desk_caches.py`, but no active pipeline script scrapes or updates it (legacy static backfill).

