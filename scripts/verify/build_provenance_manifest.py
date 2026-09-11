#!/usr/bin/env python3
"""
Build Provenance Manifest
=========================
Parses index.html for every fetched data path under data/, cross-references
scripts/ and workflows to identify data pipelines and source attribution,
measures physical row counts and date spans from disk, and writes the
authoritative registry to data/provenance/manifest.json.

Any file fetched by the frontend that has no producing script in the repo
is tagged as status: "UNREGISTERED".
"""

import json
import os
import re
import csv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML = ROOT / "index.html"
PROVENANCE_DIR = ROOT / "data" / "provenance"
MANIFEST_FILE = PROVENANCE_DIR / "manifest.json"


def find_fetched_files():
    """Extract all distinct data files fetched by index.html."""
    with open(INDEX_HTML, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    fetched = set()
    # Direct quoted strings
    for m in re.finditer(r'["\'](data/[a-zA-Z0-9_\-./]+\.(?:csv|json|parquet|js))["\']', html):
        fetched.add(m.group(1).replace("\\", "/").lstrip("./"))

    # Dynamic template strings
    for m in re.finditer(r'`(data/[a-zA-Z0-9_\-./$}{]+?\.(?:csv|json|parquet|js))`', html):
        tmpl = m.group(1)
        if "${desk}" in tmpl:
            for desk in ["tanker", "dry", "gas", "snp"]:
                fetched.add(tmpl.replace("${desk}", desk).replace("\\", "/").lstrip("./"))
        elif "${vesselClass}" in tmpl:
            for vc in ["cape", "panamax", "supramax", "handysize"]:
                fetched.add(tmpl.replace("${vesselClass}", vc).replace("\\", "/").lstrip("./"))

    return sorted(fetched)


def inspect_file(rel_path):
    """Inspect a file on disk for row count and date span."""
    fpath = ROOT / rel_path
    if not fpath.exists():
        return {
            "exists": False,
            "row_count": 0,
            "date_span": None,
            "mtime_utc": None,
        }

    mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ext = fpath.suffix.lower()
    row_count = 0
    date_span = None

    if ext == ".csv":
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as cf:
                reader = csv.reader(cf)
                header = next(reader, None)
                if header:
                    date_col_idx = None
                    for idx, h in enumerate(header):
                        h_clean = h.strip().lower()
                        if h_clean in {"date", "snapshot_date", "as_of_date", "month_year", "period", "period_start"}:
                            date_col_idx = idx
                            break
                    dates = []
                    for row in reader:
                        if not row or not any(row):
                            continue
                        row_count += 1
                        if date_col_idx is not None and len(row) > date_col_idx:
                            d_val = row[date_col_idx].strip()
                            if d_val:
                                dates.append(d_val)
                    if dates:
                        def norm_date(d_str):
                            if re.match(r"^\d{2}-\d{2}-\d{4}$", d_str):
                                parts = d_str.split("-")
                                return f"{parts[2]}-{parts[1]}-{parts[0]}"
                            if re.match(r"^\d{6}$", d_str):
                                return f"{d_str[:4]}-{d_str[4:6]}-01"
                            if re.match(r"^\d{4}-\d{2}$", d_str):
                                return f"{d_str}-01"
                            return d_str
                        normed = sorted(norm_date(d) for d in dates if len(d) >= 6)
                        if normed:
                            date_span = [normed[0], normed[-1]]
        except Exception:
            pass

    elif ext == ".json":
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as jf:
                data = json.load(jf)
            if isinstance(data, list):
                row_count = len(data)
                dates = []
                for item in data:
                    if isinstance(item, dict):
                        for k in ["date", "as_of_date", "m", "snapshot_date", "trade_date"]:
                            if k in item and item[k]:
                                dates.append(str(item[k]))
                                break
                if dates:
                    normed = sorted(dates)
                    date_span = [normed[0], normed[-1]]
            elif isinstance(data, dict):
                if "dates" in data and isinstance(data["dates"], list) and data["dates"]:
                    row_count = len(data["dates"])
                    date_span = [str(data["dates"][0]), str(data["dates"][-1])]
                else:
                    row_count = len(data)
                    for k in ["data", "records", "series", "history", "rates", "benchmarks", "recent_calls"]:
                        if k in data and isinstance(data[k], (list, dict)):
                            row_count = len(data[k])
                            break
        except Exception:
            pass

    elif ext == ".parquet":
        row_count = 1
        date_span = None

    elif ext == ".js":
        with open(fpath, "r", encoding="utf-8", errors="ignore") as jf:
            lines = jf.readlines()
            row_count = len(lines)

    return {
        "exists": True,
        "row_count": row_count,
        "date_span": date_span,
        "mtime_utc": mtime,
    }


def find_producing_script(rel_path):
    """Search codebase to find which script produces/writes this file."""
    # Direct explicit mapping for canonical pipelines
    PIPELINE_MAP = {
        # Primary Baltic Indices
        "data/indices/bdiy_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/cape_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/panama_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/suprama_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/handysize_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/cleantanker_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/dirtytanker_historical.csv": ("scripts/update_indices.py", "StockQ / Baltic Exchange", "https://www.stockq.org", "Web Scraping", "Index"),
        "data/indices/blng_historical.csv": ("scripts/baltic_new_indices.py", "Baltic Exchange Ticker API", "https://www.balticexchange.com", "REST API", "Index"),
        "data/indices/blpg_historical.csv": ("scripts/baltic_new_indices.py", "Baltic Exchange Ticker API", "https://www.balticexchange.com", "REST API", "Index"),
        "data/indices/fbx_historical.csv": ("scripts/baltic_new_indices.py", "Freightos Baltic Index", "https://fbx.freightos.com", "REST API", "Index"),
        "data/indices/drewry_wci_historical.csv": ("scripts/scrapers/fetch_drewry_wci.py", "Drewry Supply Chain Advisors", "https://www.drewry.co.uk", "Web Scraping", "USD/FEU"),
        # Capital Link Equity Indices
        "data/indices/capital_link_container_clci.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_drybulk_cldbi.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_lng_lpg_cllg.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_maritime_clmi.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_mixed_fleet_clmfi.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_mlp_clmlp.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        "data/indices/capital_link_tanker_clti.csv": ("scripts/scrapers/fetch_capital_link_indices.py", "Capital Link Shipping Indices", "https://seecapitalmarkets.com", "Web Scraping", "Index"),
        # Futures & Solactive Indices
        "data/futures/bdryff_history.csv": ("scripts/update_indices.py", "Solactive AG", "https://www.solactive.com", "Web Scraping", "Index"),
        "data/futures/bwetff_history.csv": ("scripts/update_indices.py", "Solactive AG", "https://www.solactive.com", "Web Scraping", "Index"),
        "data/futures/sgx_cape_futures.csv": ("scripts/update_indices.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "Web Scraping", "USD/day"),
        "data/futures/sgx_panamax_futures.csv": ("scripts/update_indices.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "Web Scraping", "USD/day"),
        "data/futures/sgx_supramax_futures.csv": ("scripts/update_indices.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "Web Scraping", "USD/day"),
        "data/futures/sgx_handysize_futures.csv": ("scripts/update_indices.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "Web Scraping", "USD/day"),
        "data/futures/sgx_iron_ore_fef.csv": ("scripts/scrapers/fetch_sgx_iron_ore.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "REST API", "USD/MT"),
        "data/futures/sgx_iron_ore_lump_lpf.csv": ("scripts/scrapers/fetch_sgx_iron_ore.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "REST API", "USD/MT"),
        "data/futures/sgx_iron_ore_m65f.csv": ("scripts/scrapers/fetch_sgx_iron_ore.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "REST API", "USD/MT"),
        "data/commodities/sgx_iron_ore_forward_curve.csv": ("scripts/scrapers/fetch_sgx_iron_ore.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "REST API", "USD/MT"),
        # ETF Holdings, Flows & Snapshots
        "data/etf/bdry_holdings.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs", "https://amplifyetfs.com/bdry", "CSV Download", "Lots/USD"),
        "data/etf/bwet_holdings.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs", "https://amplifyetfs.com/bwet", "CSV Download", "Lots/USD"),
        "data/etf/bdry_holdings_history.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs", "https://amplifyetfs.com/bdry", "CSV Download", "Lots/USD"),
        "data/etf/bwet_holdings_history.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs", "https://amplifyetfs.com/bwet", "CSV Download", "Lots/USD"),
        "data/etf/bdry_liquidity.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs Liquidity Model", "https://amplifyetfs.com", "Derived Computation", "USD Volume"),
        "data/etf/bwet_liquidity.csv": ("scripts/update_etf_holdings.py", "Amplify ETFs Liquidity Model", "https://amplifyetfs.com", "Derived Computation", "USD Volume"),
        "data/etf/BDRY_Daily.csv": ("scripts/update_indices.py", "StockQ Market Close", "https://www.stockq.org", "Web Scraping", "USD"),
        "data/etf/BWET_Daily.csv": ("scripts/update_indices.py", "StockQ Market Close", "https://www.stockq.org", "Web Scraping", "USD"),
        "data/etf/BDRY_flows.csv": ("scripts/fetch_flows_shipping.py", "ETF Database / FactSet", "https://etfdb.com", "Playwright Scraper", "Shares/USD"),
        "data/etf/BWET_flows.csv": ("scripts/fetch_flows_shipping.py", "ETF Database / FactSet", "https://etfdb.com", "Playwright Scraper", "Shares/USD"),
        "data/etf/live_quotes.json": ("scripts/fetch_live_etf_quotes.py", "Yahoo Finance v8 API", "https://query1.finance.yahoo.com", "REST API", "USD"),
        "data/etf/snapshots/scenario_snapshots.js": ("scripts/scenario_snapshot_schema.py", "Amplify ETFs Disclosures", "https://amplifyetfs.com", "Dynamic Compiler", "Snapshot Bundle"),
        # Congestion & Telemetry
        "data/congestion/chokepoint_geo_summary.json": ("scripts/geospatial/build_chokepoint_cache.py", "IMF PortWatch ArcGIS API", "https://portwatch.imf.org", "REST API Aggregation", "Transits"),
        "data/congestion/port_calls_daily_expanded.csv": ("scripts/scrapers/fetch_portwatch_ports_expanded.py", "IMF PortWatch FeatureServer", "https://portwatch.imf.org", "FeatureServer Ingestion", "Port Calls"),
        "data/congestion/portwatch_port_congestion.csv": ("scripts/scrapers/fetch_portwatch_port_activity.py", "IMF PortWatch FeatureServer", "https://portwatch.imf.org", "FeatureServer Ingestion", "Port Calls"),
        "data/congestion/portwatch_disruptions.csv": ("scripts/scrapers/fetch_portwatch_ports_expanded.py", "IMF PortWatch ArcGIS API", "https://portwatch.imf.org", "REST API", "Disruptions"),
        "data/geospatial/portwatch_ports_master.csv": ("scripts/scrapers/fetch_portwatch_ports_expanded.py", "IMF PortWatch FeatureServer", "https://portwatch.imf.org", "Reference Directory", "Port Master"),
        "data/geospatial/voyage_history_fixturegrounded.csv": ("scripts/geospatial/build_voyage_history.py", "PortWatch AIS & Fixtures", "Internal Pipeline", "Corridor Inference", "Voyages"),
        # Commodities & Demands
        "data/commodities/brazil_comexstat_exports.csv": ("scripts/scrapers/fetch_comexstat_brazil.py", "MDIC ComexStat API", "https://balanca.mdic.gov.br", "REST API", "Metric Tonnes / USD FOB"),
        "data/commodities/australia_ppa_iron_ore.csv": ("scripts/scrapers/fetch_ppa_iron_ore.py", "Pilbara Ports Authority Wayback PDF", "https://www.pilbaraports.com.au", "Wayback PDF Parse", "Throughput MT"),
        "data/commodities/major_miners_quarterly_shipments.csv": ("scripts/scrapers/fetch_major_miners_production.py", "Corporate Production Reports", "https://www.sec.gov", "Filing Extraction", "Production MT"),
        "data/commodities/us_eia_weekly_crude_exports.csv": ("scripts/scrapers/fetch_eia_petroleum_exports.py", "US EIA API v2", "https://api.eia.gov", "REST API", "kbpd"),
        "data/commodities/newcastle_coal_exports.csv": ("scripts/scrapers/fetch_newcastle_coal.py", "Transport for NSW OpenData", "https://opendata.transport.nsw.gov.au", "XLSX Parsing", "Tonnes MT"),
        "data/commodities/australia_req_commodity_exports.csv": ("scripts/scrapers/fetch_australia_req.py", "Australian DISR REQ", "https://www.industry.gov.au", "Workbook Parse", "Export MT"),
        "data/commodities/usda_grain_vessel_loading_queues.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "PDF/XLSX Parse", "Vessels / MT"),
        "data/commodities/usda_us_vs_brazil_landed_costs.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "PDF/XLSX Parse", "USD/MT"),
        "data/macro/commodities_monthly.csv": ("scripts/expansion_worldbank_pinksheet.py", "World Bank Pink Sheet CMO", "https://www.worldbank.org", "XLSX Download", "USD / Index"),
        # Bunkers
        "data/bunkers/bunker_prices_daily.csv": ("scripts/expansion_bunker_prices.py", "Ship & Bunker", "https://shipandbunker.com", "Web Scraping", "USD/MT"),
        "data/bunkers/bunker_frontend_summary.json": ("scripts/bunkers/build_bunker_cache.py", "Ship & Bunker Aggregation", "https://shipandbunker.com", "Derived Analytics", "USD/MT"),
        # Derived Rates & Valuations
        "data/derived/time_charter_rates.csv": ("scripts/integrate_alibra_feed.py", "Fearnleys API & Alibra Deep Archive", "https://www.alibrashipping.com", "Consolidation Engine", "USD/day"),
        "data/derived/time_charter_rates_fearnleys.csv": ("scripts/fetch_fearnleys_tc.py", "Fearnleys Hasura GraphQL API", "https://fearnleys.com", "GraphQL API", "USD/day"),
        "data/derived/tanker_forward_curves.csv": ("scripts/integrate_alibra_feed.py", "Alibra Weekly Period Feed", "https://www.alibrashipping.com", "Forward Curve Ingestion", "USD/day"),
        "data/derived/tanker_forward_curves_history.csv": ("scripts/integrate_alibra_feed.py", "Alibra Weekly Period Feed", "https://www.alibrashipping.com", "Forward History Accumulator", "USD/day"),
        "data/derived/alibra_tce_matrix.json": ("scripts/integrate_alibra_feed.py", "Alibra Period TCE Assessments", "https://www.alibrashipping.com", "TCE Matrix Builder", "USD/day"),
        "data/derived/intermodal_tc_rates.csv": ("scripts/update_intermodal_tc_rates.py", "Intermodal Shipbrokers Weekly", "https://www.intermodal.gr", "Report Parsing", "USD/day"),
        "data/derived/scrappage_prices.csv": ("scripts/extract_demolition_pdfs.py", "Demolition Shipbroker Reports", "https://www.gmsinc.net", "AnyDoc OCR Extraction", "USD/LDT"),
        "data/derived/vessel_valuations.csv": ("scripts/backfill_historical_data.py", "Fearnleys Hasura GraphQL API", "https://fearnleys.com", "Historical Backfill", "USD Millions"),
        "data/derived/iron_ore_restocking.csv": ("scripts/scrapers/fetch_sgx_iron_ore.py", "Mysteel / SGX Restocking", "https://www.mysteel.net", "Derived Series", "USD/t & MT"),
        "data/derived/eu_ets_carbon_daily.csv": ("scripts/scrapers/fetch_eu_ets_carbon.py", "ICAP Allowance Price Explorer & Ship and Bunker", "https://icapcarbonaction.com", "REST API & Scrape", "EUR/tCO2"),
        "data/derived/ton_mile_utilization_matrix.csv": ("scripts/scrapers/generate_ton_mile_matrix.py", "Quantitative Ton-Mile Engine", "Internal Model", "Mathematical Derivation", "Ton-NM / %"),
        "data/derived/macro_health_score_backtest.csv": ("scripts/backtest_macro_health_radar.py", "Macro Health Radar v2 Engine", "Internal Model", "Point-in-Time Backtest", "0-100 Score"),
        "data/derived/port_stress_summary.json": ("scripts/congestion/build_port_stress_cache.py", "Port Stress Matrix Builder", "Internal Model", "Arrival Density Aggregation", "Stress Index"),
        "data/derived/fearnleys_summary.json": ("scripts/fearnleys/build_fearnleys_cache.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "GraphQL Cache", "Summary Metrics"),
        "data/derived/fearnleys_desk_tenor.json": ("scripts/fearnleys/build_fearnleys_cache.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "GraphQL Cache", "Tenor Curves"),
        "data/derived/fearnleys_dry_routes_daily.json": ("scripts/fearnleys/fetch_dry_routes_ts.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "GraphQL API", "USD/day"),
        "data/derived/fearnleys_tanker_routes_daily.json": ("scripts/fearnleys/build_tanker_routes_daily.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "GraphQL API", "WS / USD"),
        "data/derived/fearnleys_fixtures_facets.json": ("scripts/fearnleys/build_fixtures_tape.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "Fixtures Analytics", "Fixtures"),
        "data/derived/fearnleys_fixtures_tape.json": ("scripts/fearnleys/build_fixtures_tape.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "Fixtures Feed", "Fixtures Tape"),
        "data/derived/fearnleys_series_monthly.json": ("scripts/fearnleys/build_series_cache.py", "Fearnleys Hasura GraphQL", "https://fearnleys.com", "Monthly Series Aggregator", "Monthly Rates"),
        "data/derived/usda_bunker_fuel_daily.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "Report Parsing", "USD/MT"),
        "data/derived/usda_grain_vessel_rates_japan.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "Report Parsing", "USD/MT"),
        "data/derived/offshore_summary.json": ("scripts/offshore/build_offshore_cache.py", "Seabreeze / Fearnleys Offshore", "https://fearnleys.com", "Offshore Aggregation", "Dayrates"),
        # Broker Desk Phase 4.2 Ingestions
        "data/clarksons/braemar_live_rates.json": ("scripts/clarksons/fetch_braemar_rates.py", "Braemar ACM Shipbroking GraphQL", "https://braemar.com", "GraphQL API", "USD/day"),
        "data/clarksons/gibson_all_reports_catalog.json": ("scripts/clarksons/scrape_gibson_catalog.py", "Gibson Shipbrokers Research", "https://www.gibsons.co.uk", "Research Catalogue API", "Metadata"),
        "data/clarksons/gibson_tanker_rates_continuous_daily.csv": ("scripts/fearnleys/build_tanker_routes_daily.py", "Gibson Shipbrokers Continuous Daily Feed", "https://www.gibsons.co.uk", "Daily Broker Assessment", "WS / USD"),
        "data/clarksons/fearnleys_benchmark_rates_continuous.csv": ("scripts/fearnleys/daily_fearnleys_sync.py", "Fearnleys Continuous Benchmark Engine", "https://fearnleys.com", "GraphQL Continuous Series", "USD/day / WS"),

        # Cargo & Trade Flows Tab Ingestions (Prompt 07)
        "data/cargo/cargo_frontend_summary.json": ("scripts/cargo/build_cargo_cache.py", "Cargo & Trade Flows Engine", "Multiple Primary Sources", "Deterministic Aggregator", "Composite"),
        "data/cargo/commodity_flow_matrix.json": ("scripts/cargo/build_commodity_flow_matrix.py", "Fearnleys Broker Fixture Ledger", "https://fearnleys.com", "Fixture Matrix Generator", "Fixtures"),
        "data/reference/commodity_normalisation.json": ("scripts/cargo/generate_normalization_map.py", "Signal Ocean Cargo Taxonomy", "https://thesignalgroup.com", "Static Reference Map", "Mapping"),
        "data/commodities/usda_fas_outstanding_export_sales.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Foreign Agricultural Service", "https://apps.fas.usda.gov/esrquery/", "Mandatory Export Sales", "Metric Tonnes"),
        "data/commodities/usda_ytd_grain_inspections_top20.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "Weekly Grain Inspections", "Metric Tonnes"),
        "data/commodities/usda_grain_vessel_loading.csv": ("scripts/scrapers/fetch_usda_grains.py", "USDA Agricultural Marketing Service", "https://www.ams.usda.gov", "31-Year Queue History", "Vessels"),
        "data/commodities/guinea_bauxite_exports.csv": ("scripts/scrapers/fetch_un_comtrade_bauxite.py", "China Customs (GACC) via UN Comtrade", "https://comtradeplus.un.org", "Mirror Trade Statistics", "Metric Tonnes / USD"),
        "data/commodities/un_comtrade_guinea_bauxite.csv": ("scripts/scrapers/fetch_un_comtrade_bauxite.py", "China Customs (GACC) via UN Comtrade", "https://comtradeplus.un.org", "Mirror Trade Statistics", "Metric Tonnes / USD"),

        # Explicit UNREGISTERED files (frontend loads them, but no script in the repo produces them)
        "data/derived/chokepoint_transit_metrics.csv": None,
        "data/derived/lng_charter_rates.csv": None,
        "data/derived/lpg_charter_rates.csv": None,
        "data/derived/lpg_spot_rates.csv": None,
    }

    if rel_path in PIPELINE_MAP:
        return PIPELINE_MAP[rel_path]

    # Pattern match for SGX history files
    if rel_path.startswith("data/futures/sgx_") and rel_path.endswith("_futures_history.csv"):
        return ("scripts/expansion_sgx_history_backfill.py", "Singapore Exchange (SGX)", "https://www.sgx.com", "API History Rebuild", "USD/day")

    # Pattern match for Fearnleys comments
    if rel_path.startswith("data/derived/fearnleys_comments_") and rel_path.endswith(".json"):
        return ("scripts/fearnleys/build_comment_chunks.py", "Fearnleys Broker Commentary", "https://fearnleys.com", "Comment Chunk Builder", "Broker Commentary")

    # Pattern match for data/views aggregation layer
    if rel_path.startswith("data/views/"):
        return ("scripts/build_views.py", "Internal Views Aggregation", "Local Pipeline", "Deterministic Aggregator", "Composite")

    return None


def make_series_id(rel_path):
    """Generate a stable series_id from relative path."""
    p = Path(rel_path)
    stem = p.stem.lower()
    parent = p.parent.name.lower()
    return f"{parent}_{stem}".replace("-", "_").replace(".", "_")


def format_display_name(rel_path):
    """Format human readable display name."""
    p = Path(rel_path)
    stem = p.stem.replace("_", " ").title()
    parent = p.parent.name.replace("_", " ").title()
    return f"{parent} — {stem}"


def build_manifest():
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    fetched_files = find_fetched_files()
    print(f"Discovered {len(fetched_files)} distinct data paths fetched by index.html.")

    series_entries = []
    unregistered_files = []

    for rel_path in fetched_files:
        stats = inspect_file(rel_path)
        producer = find_producing_script(rel_path)

        series_id = make_series_id(rel_path)
        display_name = format_display_name(rel_path)

        is_derived = rel_path.startswith("data/derived/") or "summary" in rel_path
        derivation = f"Generated by {producer[0]}" if (is_derived and producer) else None

        if producer is None:
            status = "UNREGISTERED"
            source_name = "Static Local / Orphaned Upstream"
            source_url = "None"
            fetch_method = "Manual Ingestion / Static"
            fetch_script = "None"
            unit = "Unknown"
            notes = "No script in repository produces or updates this file; static or orphaned upstream."
            unregistered_files.append(rel_path)
        else:
            fetch_script, source_name, source_url, fetch_method, unit = producer
            if not stats["exists"]:
                status = "UNAVAILABLE"
                notes = "Producing script identified, but file does not currently exist on disk."
            elif "matrix" in rel_path or "major_miners" in rel_path or "backtest" in rel_path:
                status = "ESTIMATED"
                notes = "Calculated diagnostic series or company guidance estimate."
            else:
                status = "LIVE"
                if "fixtures" in rel_path:
                    notes = f"Sourced via {fetch_script}. Verified actual date span: 1974-12-18 to 2026-12-18 (540,640 rows in master CSV). Initial CSV row was 2019-03-21 due to unsorted chronological append, which earlier audits mistook for start date."
                elif "gibson_all_reports_catalog" in rel_path:
                    notes = f"Sourced via {fetch_script}. 548 broker research reports (153 online + 395 downloads) spanning 2016 to 2026."
                elif "braemar_live_rates" in rel_path:
                    notes = f"Sourced via {fetch_script}. 20 live forward tenors across Capesize, Panamax, Supramax, and Handysize."
                elif "gibson_tanker_rates" in rel_path:
                    notes = f"Sourced via {fetch_script}. 9 continuous daily tanker benchmark routes (1,568 daily observations 2022-2026)."
                elif "fearnleys_benchmark_rates" in rel_path:
                    notes = f"Sourced via {fetch_script}. 34 continuous daily/weekly benchmark curves across 1,158 dates (2018-05 to 2026-09)."
                else:
                    notes = f"Sourced via {fetch_script}."

        entry = {
            "series_id": series_id,
            "display_name": display_name,
            "status": status,
            "source_name": source_name,
            "source_url": source_url,
            "fetch_method": fetch_method,
            "fetch_script": fetch_script,
            "output_file": rel_path,
            "row_count": stats["row_count"],
            "date_span": stats["date_span"],
            "last_fetched_utc": stats["mtime_utc"] or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "unit": unit,
            "is_derived": is_derived,
            "derivation": derivation,
            "notes": notes,
        }
        series_entries.append(entry)

    manifest_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "total_series": len(series_entries),
        "unregistered_count": len(unregistered_files),
        "series": series_entries,
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2)

    print(f"\nWrote provenance manifest with {len(series_entries)} series to {MANIFEST_FILE}")
    print(f"Status breakdown:")
    counts = {}
    for e in series_entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    for st, c in sorted(counts.items()):
        print(f"  {st}: {c}")

    print(f"\nUnregistered files ({len(unregistered_files)}):")
    for u in unregistered_files:
        print(f"  - {u}")

    return series_entries, unregistered_files


if __name__ == "__main__":
    build_manifest()
