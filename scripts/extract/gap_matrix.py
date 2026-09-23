"""GAP MATRIX: for every recurring series the publisher reports carry, is it already
published by a live feed?

Buckets
-------
ALREADY_IN_FEED    a feed file publishes the same quantity at equal-or-finer grain.
                   Every such row MUST cite the feed file that justifies it.
PARTIALLY_COVERED  a feed touches the concept but scope/grain/history differs.
                   partial_kind records WHICH way it differs:
                     feed_has_aggregate_only   report is finer (per-brand, per-port, per-route)
                     feed_narrower_coverage    feed has a subset of the report's rows/columns
                     feed_snapshot_only        feed is a single snapshot, report is a history
                     feed_raw_only             feed carries raw material, not the derived series
GENUINELY_MISSING  no feed file carries the quantity.
UNSURE             cannot be decided from the artefacts; stated, not guessed.

Citations are validated against the enumerated feed set - a row claiming
ALREADY_IN_FEED with a filename that is not one of the 120 feeds is an error and
the script fails loudly rather than emitting an unverifiable claim.

usage: python scripts/extract/gap_matrix.py [--json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

FEED_JSON = "scratch/gap_feeds.json"
OUT = "data/extracted/gap_matrix.json"
CORPUS = "data/extracted/corpus/db/corpus.duckdb"

# ---------------------------------------------------------------------------
# concept register: derived from the recurring report tables these publishers
# carry (series_priorities worklist + the extracted `series` entity inventory +
# heading census of the breakwave HTML insights and the seabrokers .md months).
# ---------------------------------------------------------------------------
M = [
    # ---------------- DRY BULK FREIGHT ----------------
    dict(id="dry_index_levels", concept="Baltic dry indices: BDI / BCI / BPI / BSI / BHSI",
         publishers=["shipbrokers (weekly market reviews)", "baltic (weekly dry)",
                     "hellenic (weekly dry charter)", "drybulk (monthly)",
                     "poten (weekly)"],
         publisher_grain="weekly/daily index level + % change",
         bucket="ALREADY_IN_FEED",
         evidence=["data/indices/bdiy_historical.csv", "data/indices/cape_historical.csv",
                   "data/indices/panama_historical.csv", "data/indices/suprama_historical.csv",
                   "data/indices/handysize_historical.csv"],
         note="BDI 10,521 rows back to 1985-01-04; BCI/BPI/BSI/BHSI 4,319-4,341 rows each from 2008-10-06 to 2026-09-21 - daily, longer history than any report."),
    dict(id="dry_route_subindices", concept="Baltic dry route sub-indices (C2,C3,C5,C7,C8,C10,C14, P1A-P4, S1C-S10, HS1-HS3)",
         publishers=["shipbrokers (weekly)", "baltic (weekly dry)", "hellenic (weekly dry charter)"],
         publisher_grain="weekly route rate/TCE per route",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/clarksons/fearnleys_benchmark_rates_continuous.csv"],
         note="Feed carries C3, C5, C9_182, C10_182, P1A_82, P2A_82, P3A_82, P4_82, S1C, S4A, S4B, S10 (1985-01-04..2026-09-10). Reports tabulate ~30 routes incl. C2/C7/C8/C14/P5/P6 and the HS series, which the feed does not hold."),
    dict(id="dry_segment_tc", concept="Dry bulk TC average by design size (180k/176k cape, 82k kamsarmax, 75k panamax, 58k supramax, 64k ultramax, 38k handy)",
         publishers=["shipbrokers (weekly)", "baltic (weekly dry)", "hellenic (weekly dry charter)"],
         publisher_grain="weekly TC average per size, this wk / previous",
         bucket="ALREADY_IN_FEED",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="BULK_TC_CAPESIZE_180_000_DWT 2,216 rows, BULK_TC_PANAMAX_75_000_DWT 2,298, BULK_TC_KAMSARMAX_82_000_DWT 327, BULK_TC_SUPRAMAX_58_000_DWT 1,150, BULK_TC_ULTRAMAX_64_000_DWT 325, BULK_TC_HANDYSIZE_38_000_DWT 142 - back to 1977 in the monthly cache."),
    dict(id="dry_tc_vintage_buckets", concept="Broker-specific TC buckets not published by Baltic (capesize 176k, handysize 32k/37k/40k, supramax 56k, ultramax 63k)",
         publishers=["shipbrokers (weekly)"],
         publisher_grain="weekly TC per broker size label",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="Feed publishes the segment/dwt set above; the 176k/32k/37k/40k/56k/63k labels are broker-specific bucketings of the same market (corpus holds them as shipbrokers|capesize 180k etc.)."),
    dict(id="dry_period_tc", concept="Dry period TC (4-6 months, 1 year, 2 years; Atlantic/Pacific/average)",
         publishers=["shipbrokers (weekly)", "baltic (weekly dry)"],
         publisher_grain="weekly 1-yr/2-yr TC per segment and basin",
         bucket="PARTIALLY_COVERED", partial_kind="feed_snapshot_only",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="Feed gives spot/period TC averages per segment (BULK_TC_*), not the 4-6m/1y/2y x Atlantic/Pacific grid. A derived artefact exists at data/derived/time_charter_rates.csv (source column 'fearnleys') but it is not one of the 120 feeds."),
    dict(id="ffa_settlements", concept="FFA / freight futures settlements by contract month and tenor",
         publishers=["shipbrokers (weekly)", "breakwave (daily insights)", "baltic (weekly)"],
         publisher_grain="daily/weekly settle per contract and tenor",
         bucket="ALREADY_IN_FEED",
         evidence=["data/futures/sgx_cape_futures_history.csv", "data/futures/sgx_panamax_futures_history.csv",
                   "data/futures/sgx_supramax_futures_history.csv", "data/futures/sgx_handysize_futures_history.csv",
                   "data/futures/bdryff_history.csv", "data/ffa_live/daily.csv"],
         note="183,569 / 66,245 / 188,674 / 82,340 rows of every SGX contract with price, volume, OI; data/ffa_live/daily.csv carries the live curve (120 rows, 2026-09-14..2026-09-21)."),
    # ---------------- IRON ORE / STEEL ----------------
    dict(id="sgx_iron_ore", concept="SGX iron ore futures: 62% Fe, 65% (M65F), lump (LPF) + forward curve",
         publishers=["hellenic (daily iron ore)", "baltic (weekly dry)", "drybulk (monthly)", "shipbrokers"],
         publisher_grain="daily/weekly contract price + curve",
         bucket="ALREADY_IN_FEED",
         evidence=["data/futures/sgx_iron_ore_fef_history.csv", "data/futures/sgx_iron_ore_m65f_history.csv",
                   "data/futures/sgx_iron_ore_lump_lpf_history.csv", "data/commodities/sgx_iron_ore_continuous_daily.csv",
                   "data/commodities/sgx_iron_ore_forward_curve.csv"],
         note="95,894 / 61,832 / 41,636 rows of every contract; continuous daily 2,237 rows 2018-01-19..2026-09-18; forward curve snapshot."),
    dict(id="iron_ore_spot_indices", concept="Iron ore spot price indices: IOPI 58/62/65, IOPLI 62, IOSI 62/65 (+ MTD/YTD averages)",
         publishers=["hellenic (daily iron ore)"],
         publisher_grain="daily index level, MTD and YTD averages",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/futures/sgx_iron_ore_fef_history.csv", "data/macro/commodities_monthly.csv"],
         note="Feed holds the 62/65/lump swap complex and a monthly iron_ore price series (1960-01-01..2026-08-01), but no 58% index, no IOPLI, no MTD/YTD framing. Corpus holds 915 docs of iopi58|iopi62|iopi65|iopli62|iosi62|iosi65."),
    dict(id="iron_ore_brands", concept="Iron ore physical brand prices (~40 brands: PB fines, Newman, MAC, Carajas, RTX, Yandi, SSF, West Pilbara fines...)",
         publishers=["hellenic (daily iron ore)"],
         publisher_grain="daily brand-level price/assessment",
         bucket="GENUINELY_MISSING",
         evidence=[],
         note="Verified: no feed filename or header contains 'brand' or 'fines' (0/120). Largest recurring report table in the corpus (1,165 docs)."),
    dict(id="iron_ore_quality", concept="Iron ore quality specs (Fe %, alumina %, silica %, phosphorus %, sulphur %, moisture %)",
         publishers=["hellenic (daily iron ore)"],
         publisher_grain="per brand, weekly",
         bucket="GENUINELY_MISSING", evidence=[],
         note="No feed file carries assay/spec data; 1,160 docs in corpus."),
    dict(id="china_port_stocks", concept="Chinese iron ore port stocks: total (35 ports) and by port (Caofeidian, Jingtang, Qingdao, Rizhao, Tianjin, Beilun, Bayuquan, Dalian) / province (Hebei, Liaoning, Shandong)",
         publishers=["hellenic (daily iron ore)", "drybulk (monthly)"],
         publisher_grain="weekly stocks by port and province + total",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feeds match 'stocks' or 'inventor'. A derived artefact exists (data/derived/iron_ore_restocking.csv) but it is report-derived, not a feed. 1,040 + 1,037 docs in corpus."),
    dict(id="steel_prices", concept="Chinese steel prices by product (HRC, CRC SPCC/ST12, GI, rebar HRB400, wire rod, medium & heavy plate)",
         publishers=["hellenic (weekly shipbuilding/steel)", "shipbrokers"],
         publisher_grain="weekly RMB/tonne price per product spec",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: no feed carries steel prices ('steel' matches only data/commodities/world_crude_steel_monthly.csv, which is production). 1,157 + 735 docs in corpus."),
    dict(id="steel_production", concept="Steel production (world / China, monthly)",
         publishers=["drybulk (monthly)", "tankers (monthly)"],
         publisher_grain="monthly Mt, YoY",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/world_crude_steel_monthly.csv"],
         note="World Steel Association monthly press releases, 70 reporting countries, 2024-01-01..2026-07-01 (31 rows) incl. china_mt, yoy_change_pct."),
    dict(id="steel_inventories", concept="China steel inventories",
         publishers=["drybulk (monthly)"],
         publisher_grain="monthly Mt",
         bucket="GENUINELY_MISSING", evidence=[],
         note="No feed carries steel stocks; only the report-derived data/derived/iron_ore_restocking.csv has steel_inventories_mt."),
    # ---------------- TRADE FLOWS / COMMODITIES ----------------
    dict(id="iron_ore_exports", concept="Australia + Brazil iron ore exports (Port Hedland/PPA, REQ, Comexstat)",
         publishers=["drybulk (monthly)", "hellenic (daily iron ore)"],
         publisher_grain="monthly Mt by port and destination",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/australia_ppa_iron_ore.csv", "data/commodities/australia_req_commodity_exports.csv",
                   "data/commodities/brazil_comexstat_exports.csv", "data/commodities/brazil_exports_monthly.csv"],
         note="PPA Port Hedland iron_ore_exports_mt with a destinations_t breakdown, 423 rows 2002-07-01..2026-08-01; REQ 725 rows from 1990-03-01; Comexstat 580 rows from 2017-01-01."),
    dict(id="china_imports", concept="China commodity imports (iron ore, coal, crude oil, soybeans, bauxite, alumina, LNG/LPG, steel products, fertiliser)",
         publishers=["drybulk (monthly)", "tankers (monthly)", "hellenic (iron ore)"],
         publisher_grain="monthly volume/value by HS code with top partners",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/china_customs_monthly_imports.csv"],
         note="GACC/chinadata.live: 957 rows 2018-01-01..2026-08-01 covering exactly Alumina, Bauxite, Coal, Crude oil, Fertilisers, Iron ore, LNG/LPG, Soybeans, Steel products."),
    dict(id="coal_exports", concept="Coal exports: Indonesia monthly, Newcastle (port + monthly), Australian coal price",
         publishers=["drybulk (monthly)"],
         publisher_grain="monthly Mt by grade and destination",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/indonesia_coal_exports_monthly.csv", "data/commodities/newcastle_coal_exports.csv",
                   "data/commodities/newcastle_coal_monthly.csv", "data/macro/commodities_monthly.csv"],
         note="Indonesia split into bituminous/other/lignite (103 rows from 2018-01-01); Newcastle with vessels_loaded_count and primary_destinations."),
    dict(id="grain_flows", concept="Grain and oilseed trade flows + vessel loading/queues (USDA, Argentina, Brazil)",
         publishers=["drybulk (monthly)", "shipbrokers (weekly)"],
         publisher_grain="monthly/quarterly Mt; weekly vessel loading queues",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/usda_grain_vessel_loading.csv", "data/commodities/usda_grain_vessel_loading_queues.csv",
                   "data/commodities/usda_ytd_grain_inspections_top20.csv", "data/commodities/usda_fas_outstanding_export_sales.csv",
                   "data/commodities/argentina_grain_exports_monthly.csv", "data/commodities/argentina_grain_ports_breakdown.csv"],
         note="Vessel loading (3,306 rows from 1995-01-04), inspections top-20 (50,127 rows), outstanding sales (68,350 rows), Argentina port breakdown (394 rows)."),
    dict(id="bauxite_flows", concept="Bauxite/Guinea exports and China bauxite imports",
         publishers=["drybulk (monthly)"],
         publisher_grain="monthly Mt + partner USD",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/guinea_bauxite_exports.csv", "data/commodities/china_customs_guinea_bauxite_partner_usd.csv",
                   "data/commodities/un_comtrade_guinea_bauxite.csv"],
         note="155 rows from 2015-12-31; China customs partner breakdown 107 rows; Comtrade 24 rows."),
    dict(id="minor_bulks", concept="Minor bulks monthly (fertiliser, alumina, other dry)",
         publishers=["drybulk (monthly)"],
         publisher_grain="monthly Mt",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/minor_bulks_monthly.csv"],
         note="662 rows 2013-01-01..2026-08-01."),
    dict(id="commodity_prices", concept="Commodity price board (Brent, WTI, gasoil, natural gas, LME 3mo alu/copper/tin/zinc, COMEX copper, gold, silver, corn, rice, soybean, lithium)",
         publishers=["shipbrokers (weekly)", "breakwave (daily)", "baltic (weekly)", "tankers (monthly)"],
         publisher_grain="weekly/daily futures and spot prints",
         bucket="PARTIALLY_COVERED", partial_kind="feed_has_aggregate_only",
         evidence=["data/macro/commodities_monthly.csv", "data/clarksons/fearnleys_benchmark_rates_continuous.csv"],
         note="Feed is the World Bank monthly pink sheet (iron ore, Australian coal, Brent, EU natgas, Japan LNG, DAP, maize, wheat, Thai rice, soybeans, copper, aluminium, nickel, precious metals; 800 rows from 1960-01-01) plus a daily Brent series inside the Fearnleys feed. No LME 3-month, no tin, no RBOB, no lithium."),
    dict(id="fx_pairs", concept="FX pairs quoted in the weekly tables (EUR/USD, USD/JPY, USD/KRW, USD/NOK, GBP/USD, USD/CNY, USD/INR, USD/TRY, USD/PKR, USD/BDT)",
         publishers=["shipbrokers (weekly)"],
         publisher_grain="weekly spot per pair",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/clarksons/fearnleys_benchmark_rates_continuous.csv"],
         note="Feed carries EUR/USD, USD/KRW and USD/NOK only (1985-01-04..2026-09-10). The other pairs (USD/JPY, USD/TRY, USD/INR, USD/CNY, USD/PKR, USD/BDT, GBP/USD) appear in no feed file."),
    dict(id="equity_prices", concept="Listed shipping equity prices (DSX, EGLE, ESEA, GOGL, NAT, ADM, BHP, RIO, DAC, GASS, TOPS...) and broad indices (Dow, FTSE, Nikkei, Hang Seng, Nasdaq, CAC40, DJ US Maritime)",
         publishers=["shipbrokers (weekly)"],
         publisher_grain="weekly price/index level",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/equities/foreign_maritime_metrics.csv", "data/equities/foreign_maritime_financials.csv",
                   "data/equities/maritime_universe_catalog.csv", "data/equities/sec_xbrl_financials.csv"],
         note="Feed has the maritime universe catalog (175 rows), valuation metrics and SEC XBRL financials (10,462 rows) - no share-price history and no broad index levels (verified: 'cac40'/'nikkei' appear only in corpus labels, never in a feed header)."),
    dict(id="rates_macro", concept="Interest rates (SOFR/LIBOR) quoted in the report tables",
         publishers=["shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="weekly rate",
         bucket="ALREADY_IN_FEED",
         evidence=["data/clarksons/fearnleys_benchmark_rates_continuous.csv"],
         note="tsid_12100 'Interest Rates (SOFR/LIBOR) [percent]' inside the continuous benchmark feed."),
    dict(id="carbon_ets", concept="Carbon / EU ETS allowance price (decarbonisation sections)",
         publishers=["hellenic (weekly)", "seabrokers (monthly)"],
         publisher_grain="weekly price",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: no feed filename or header matches 'carbon' or 'eua'; only a report-derived data/derived/eu_ets_carbon_daily.csv."),
    # ---------------- WET FREIGHT / OIL ----------------
    dict(id="tanker_index_levels", concept="Baltic tanker indices BDTI / BCTI",
         publishers=["shipbrokers (weekly)", "baltic (weekly tanker)", "poten (weekly)", "tankers (monthly)"],
         publisher_grain="daily/weekly index level",
         bucket="ALREADY_IN_FEED",
         evidence=["data/indices/dirtytanker_historical.csv", "data/indices/cleantanker_historical.csv"],
         note="4,528 rows from 2007-12-05 and 4,513 rows from 2008-01-02, both to 2026-09-21."),
    dict(id="tanker_routes", concept="Tanker route rates: VLCC MEG-Asia, TD3C/TD15, TD2, TD20, TD19, Aframax/Suezmax/LR/MR route TCEs and WS",
         publishers=["shipbrokers (weekly)", "baltic (weekly tanker)", "poten (weekly)", "tankers (monthly)",
                     "breakwave (daily insights)", "drewry (monthly)"],
         publisher_grain="daily/weekly WS or $/day per route",
         bucket="ALREADY_IN_FEED",
         evidence=["data/reference/fearnpulse_rates_full.csv", "data/clarksons/fearnleys_benchmark_rates_continuous.csv"],
         note="fearnpulse holds 224,971 tanker observations across ~180 route labels (TANK_VLCC_MEG_FEAST 3,546 rows, TANK_AFRAMAX_CBS_USG 3,544, TANK_SUEZMAX_* ...) incl. TANK_BALTIC_INDEX_TD3C_TCE/TD1/TD6/TD7/TD17/TD19/TD20 and demurrage; the Fearnleys feed adds TD3/TD3C, TD2, TD15, TD20, TD19 at worldscale."),
    dict(id="tanker_period_tc", concept="Tanker period TC (1-year / 3-year) by class",
         publishers=["shipbrokers (weekly)", "poten (weekly)", "tankers (monthly)"],
         publisher_grain="weekly 1yr/3yr TC per class",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="Feed has a handful of period labels (TANK_SUEZMAX_MEG_EAST_15_YR, TANK_SUEZMAX_MEG_EAST_MODERN) rather than a 1yr/3yr x class grid; data/derived/intermodal_tc_rates.csv (source 'intermodal') is a report-derived artefact, not a feed."),
    dict(id="tanker_ffa_curve", concept="Tanker FFAs / forward curves (TD3C etc.)",
         publishers=["breakwave (daily insights)", "shipbrokers (weekly)"],
         publisher_grain="daily settle per contract month",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/futures/bwetff_history.csv", "data/etf/bwet_holdings_history.csv"],
         note="Feed holds the Breakwave tanker FFA index history (2,467 rows) and the ETF's contract-level FFA prices (728 rows); no full tanker forward curve (data/derived/tanker_forward_curves.csv is report-derived)."),
    dict(id="oil_fundamentals", concept="Oil fundamentals: China oil imports, US crude exports, OECD crude stocks, OPEC/non-OPEC supply, world oil demand, crude on water / floating storage",
         publishers=["tankers (monthly)", "breakwave (daily)", "poten (weekly)"],
         publisher_grain="monthly volume/stock; weekly exports",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/commodities/china_customs_monthly_imports.csv", "data/commodities/us_eia_weekly_crude_exports.csv"],
         note="China crude imports (103 rows) and US weekly crude exports (1,858 rows from 1991-02-08) are covered; OECD stocks, OPEC/non-OPEC supply, world demand and floating storage are in no feed."),
    dict(id="tonne_days", concept="Tanker/bulker tonne-day demand and loaded volumes by route (breakwave SECTION 3 - DEMAND, 'In Ton Days')",
         publishers=["breakwave (daily insights)"],
         publisher_grain="daily tonne-days / loaded mbbl per route",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feeds match 'tonne-day' or 'tonneday'. The closest raw material is AIS-derived (data/geospatial/vessel_voyage_tracks_master.csv, voyage_history_fixturegrounded.csv) but no tonne-day series is published."),
    dict(id="ballasters", concept="Vessel supply positioning: ballasters (# vessels) by region/segment (breakwave SECTION 2 - SUPPLY)",
         publishers=["breakwave (daily insights)", "drewry (monthly AIS)"],
         publisher_grain="daily vessel counts of ballast tonnage",
         bucket="PARTIALLY_COVERED", partial_kind="feed_raw_only",
         evidence=["data/geospatial/vessel_voyage_tracks_master.csv", "data/geospatial/voyage_history_fixturegrounded.csv",
                   "data/congestion/port_calls_daily.csv"],
         note="Feed carries AIS voyage tracks (24,485 rows) / fixture-grounded voyage history (358,690 rows) and daily port calls (179,506 rows); the derived ballast-count series itself is not published anywhere in the feed set."),
    # ---------------- CONTAINER / GAS / AIR ----------------
    dict(id="container_indices", concept="Container indices: Drewry WCI, FBX, Capital Link CLCI, Drewry intra-Asia (IACI)",
         publishers=["shipbrokers (weekly container section)", "drewry (monthly)"],
         publisher_grain="weekly index per trade lane",
         bucket="ALREADY_IN_FEED",
         evidence=["data/indices/drewry_wci_historical.csv", "data/indices/fbx_historical.csv",
                   "data/indices/capital_link_container_clci.csv", "data/clarksons/drewry_intra_asia_container_index.csv"],
         note="WCI composite + 5 lanes (145 rows), FBX (121 rows), CLCI daily back to 2005-01-03 (5,610 rows), IACI composite + 8 lanes."),
    dict(id="ningbo_container", concept="Ningbo container route rates (Ningbo-Europe, Ningbo-Middle East, Ningbo-East/West Med)",
         publishers=["baltic (weekly ningbo)"],
         publisher_grain="weekly rate per route",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feed files match 'ningbo'. Corpus holds 4 baltic series x ~510 weekly points 2017-01-06..2026-09-18."),
    dict(id="container_tc", concept="Container time-charter rates by TEU size (1100 TEU 1y geared ... 4250 TEU)",
         publishers=["shipbrokers (weekly container section)", "baltic (weekly container)"],
         publisher_grain="weekly TC per size band",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="Feed holds container NEWBUILDING prices by TEU band (NEWBUILDING_PRICES_1_900_TEU .. 21_000_TEU_LNG_DF) but no charter market; data/derived/time_charter_rates.csv is report-derived."),
    dict(id="container_fleet", concept="Container fleet / orderbook by TEU class and container vessel values",
         publishers=["shipbrokers (weekly container section)", "baltic (weekly container)"],
         publisher_grain="monthly fleet and orderbook, weekly values",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/supply/fleet_orderbook_and_age_profile.csv", "data/reference/fearnpulse_rates_full.csv"],
         note="The fleet feed's 11 segments cover dry bulk, crude/product tankers, LNG and LPG only - no container, car carrier, reefer, ro-ro, cruise or general cargo. Fleet containers/orderbook is therefore absent; only container newbuild prices exist (fearnpulse)."),
    dict(id="gas_indices", concept="Gas indices BLNG / BLPG and LNG/LPG spot & charter rates",
         publishers=["baltic (weekly gas)", "shipbrokers (weekly)"],
         publisher_grain="weekly index and $/day",
         bucket="ALREADY_IN_FEED",
         evidence=["data/indices/blng_historical.csv", "data/indices/blpg_historical.csv",
                   "data/indices/blpg_fearnleys_historical.csv",
                   "data/indices/capital_link_lng_lpg_cllg.csv",
                   "data/reference/fearnpulse_rates_full.csv"],
         note="BLNG 121 rows and BLPG 121 rows (both only 2026-03-13..2026-09-21), but the Capital Link LNG/LPG index goes back to 2005-01-03 (5,610 rows) and fearnpulse holds 30,578 LNG and 21,888 LPG observations (spot, 1/3/5-yr TC, FOB butane/propane, NB prices)."),
    dict(id="air_freight", concept="Air freight price index",
         publishers=["drewry (monthly) - carried as a feed, no extracted corpus series"],
         publisher_grain="monthly index",
         bucket="ALREADY_IN_FEED",
         evidence=["data/indices/bai_historical.csv", "data/clarksons/drewry_airfreight_price_index.csv"],
         note="BAI 460 rows; Drewry air freight index 24 rows 2024-09-01..2026-08-01."),
    # ---------------- DEMOLITION / S&P / VALUATIONS ----------------
    dict(id="newbuild_prices", concept="Newbuilding prices by class (VLCC, Suezmax, Aframax, Product, Kamsarmax, Ultramax, Newcastlemax, LNG/LPG, container TEU)",
         publishers=["hellenic (weekly vessel valuations)", "shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="weekly $m per class",
         bucket="ALREADY_IN_FEED",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="NEWBUILDING_PRICES_VLCC 1,138 rows, _SUEZMAX 743, _AFRAMAX 748, _PRODUCT 749, _KAMSARMAX 557, _ULTRAMAX 557, _NEWCASTLEMAX 1,139, container TEU bands 41-43 rows each, LNG/LPG NB prices."),
    dict(id="secondhand_values", concept="Secondhand (S&P) benchmark values: 5 / 10 / 15-year-old and resale, dry + wet, incl. Chinese- and Japanese-built",
         publishers=["hellenic (weekly vessel valuations)", "shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="weekly $m per class and age",
         bucket="ALREADY_IN_FEED",
         evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="S_P_DRY_5_CAPESIZE 860 rows, S_P_DRY_10_KAMSARMAX 512, S_P_DRY_RESALE_ULTRAMAX 279, S_P_WET_5_VLCC 759, plus _CN_*_CHINESE and _JP_*_JAPANESE breakdowns."),
    dict(id="snp_transactions", concept="Sale-and-purchase transactions (individual sales: vessel, built, dwt, price, buyer/seller)",
         publishers=["shipbrokers (weekly S&P)", "hellenic (weekly)", "baltic (weekly)"],
         publisher_grain="per-transaction weekly lists",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feeds match 'buyer'; fearnpulse carries benchmark values, not transactions. A report-derived tape exists at data/derived/fearnleys_snp_transactions.csv."),
    dict(id="demolition_volume", concept="Demolition volume and fixture tape: tonnage by destination country (Bangladesh, India, Pakistan, Turkey) and by vessel type, vessel-level fixture list",
         publishers=["hellenic (daily demolition)", "shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="weekly tonnage per destination + per-vessel fixtures",
         bucket="PARTIALLY_COVERED", partial_kind="feed_narrower_coverage",
         evidence=["data/demolition/shipandbunker_demolition_fixtures.csv"],
         note="Feed is a 254-row per-vessel fixture list (year, week, sale_date, vessel_name, vessel_type, build_date, seller) with NO destination and NO price column, so neither the report's by-destination aggregation nor its scrap prices can be reproduced from it."),
    dict(id="scrap_prices", concept="Scrappage/demolition prices by destination and ship type (dry India/Bangla/Pak/ Turkey; tanker; container)",
         publishers=["hellenic (daily demolition)"],
         publisher_grain="weekly $/ldt per destination and type",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: no feed carries demolition prices; only the report-derived data/derived/scrappage_prices.csv."),
    dict(id="fleet_orderbook", concept="Fleet size, age profile, orderbook and delivery schedule by segment",
         publishers=["hellenic (weekly shipbuilding)", "shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="monthly fleet/orderbook by type; weekly changes",
         bucket="PARTIALLY_COVERED", partial_kind="feed_snapshot_only",
         evidence=["data/supply/fleet_orderbook_and_age_profile.csv"],
         note="Feed is one snapshot: 11 rows x (active count, dwt, avg age, 5 age bands, orderbook, deliveries 2026-29+, scrubber %, source Signal Ocean). The reports carry a monthly history of the same quantities, which the feed cannot supply."),
    dict(id="fleet_by_country", concept="Fleet and demolition tonnage by owning/flag country (China, Greece, Japan, Russia, India, Brazil, USA, S.Africa)",
         publishers=["shipbrokers (weekly)", "hellenic (weekly)"],
         publisher_grain="monthly dwt by country",
         bucket="GENUINELY_MISSING", evidence=[],
         note="The supply feed carries no country dimension (columns are vessel_segment/sector only); the geospatial port master carries country per port, not ownership."),
    dict(id="fleet_by_type_full", concept="Fleet by type incl. car carrier, reefer, ro-ro, passenger/cruise, general cargo, combined, special projects",
         publishers=["shipbrokers (weekly)", "baltic (weekly)"],
         publisher_grain="monthly count/dwt by type",
         bucket="GENUINELY_MISSING", evidence=[],
         note="data/supply/fleet_orderbook_and_age_profile.csv holds only 11 dry/tanker/gas segments; the other eight reported types appear in no feed file."),
    # ---------------- BUNKERS ----------------
    dict(id="bunker_prices", concept="Bunker prices by port and grade (VLSFO, MGO, IFO380, HSFO) - Singapore, Rotterdam, Fujairah, Houston, Hong Kong",
         publishers=["shipbrokers (weekly)", "hellenic (weekly)", "baltic (weekly)", "breakwave (daily)"],
         publisher_grain="daily/weekly $/mt per port and grade",
         bucket="ALREADY_IN_FEED",
         evidence=["data/bunkers/bunker_master_historical.csv", "data/bunkers/bunker_prices_daily.csv",
                   "data/bunkers/bix_history.csv", "data/bunkers/bunker_bix_macro_benchmarks.csv"],
         note="master_historical 488,107 rows keyed on (observation_date, port_code, port_name, grade, delivery_term) 2018-02-12..2026-09-21; BIX index 3,975 rows."),
    dict(id="bunker_forwards", concept="Bunker forward curves",
         publishers=["shipbrokers (weekly bunker section) - feed-side concept, no forward-curve series in the corpus"],
         publisher_grain="12-month curve per port",
         bucket="ALREADY_IN_FEED",
         evidence=["data/bunkers/bunker_forward_curves_12m.csv"],
         note="72 rows, snapshot 2026-09-21."),
    dict(id="bunker_sales_volumes", concept="Bunker physical sales volumes by port",
         publishers=["shipbrokers (weekly)", "hellenic (weekly)"],
         publisher_grain="monthly sales volume per port",
         bucket="ALREADY_IN_FEED",
         evidence=["data/bunkers/bunker_physical_sales_volumes.csv"],
         note="106 rows."),
    dict(id="bunker_commentary", concept="Weekly bunker market commentary / sentiment",
         publishers=["shipbrokers (weekly bunker section)", "breakwave (daily)"],
         publisher_grain="narrative",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Narrative, not a numeric series; no feed equivalent by nature. Folded with narrative_commentary in the bucket tally."),
    # ---------------- CONGESTION / AIS / PORTS ----------------
    dict(id="port_congestion", concept="Port congestion and port calls (vessel counts, waiting, imports/exports kt)",
         publishers=["breakwave (daily SECTION 4 - CHINESE PORT CONGESTIONS)", "drewry (monthly AIS)",
                     "baltic (weekly)", "tankers (monthly)"],
         publisher_grain="daily vessel counts by port and type",
         bucket="PARTIALLY_COVERED", partial_kind="feed_has_aggregate_only",
         evidence=["data/congestion/portwatch_port_congestion.csv", "data/congestion/port_calls_daily.csv",
                   "data/congestion/port_calls_daily_expanded.csv", "data/congestion/port_arrival_envelope_matrix.csv"],
         note="Feed has daily port calls total/per-type and kt handled per port (120,453 / 179,506 / 524,510 / 20,100 rows) but not the report's per-port 'number of vessels waiting / congestion index' framing."),
    dict(id="chokepoints", concept="Chokepoint transits (Suez, Panama, Bab el-Mandeb, Turkish straits) with capacity",
         publishers=["shipbrokers (weekly)", "baltic (weekly)", "drewry (monthly)"],
         publisher_grain="daily transits and capacity by vessel type",
         bucket="ALREADY_IN_FEED",
         evidence=["data/congestion/chokepoint_transits_daily.csv"],
         note="78,764 rows 2019-01-01..2026-09-13 with n_<type> and capacity_<type> per chokepoint."),
    dict(id="panama_canal", concept="Panama Canal draft, transit slots and Gatun lake water level",
         publishers=["shipbrokers (weekly)", "baltic (weekly)", "drybulk (monthly)"],
         publisher_grain="weekly/daily draft, slots, water level",
         bucket="ALREADY_IN_FEED",
         evidence=["data/commodities/panama_canal_draft_and_slots.csv",
                   "data/clarksons/panama_gatun_lake_water_level_history.csv",
                   "data/clarksons/panama_gatun_water_level_projection.csv"],
         note="Gatun history 22,531 rows from 1965-01-01; draft and slots 16 rows 2022-01-15..2026-08-20; 63-row projection."),
    dict(id="ais_behaviour", concept="AIS-derived voyage behaviour: % laden/ballast, speed by basin, miles index, MoM change by vessel class",
         publishers=["drewry (monthly AIS PDFs)"],
         publisher_grain="monthly index per vessel class",
         bucket="PARTIALLY_COVERED", partial_kind="feed_raw_only",
         evidence=["data/geospatial/vessel_voyage_tracks_master.csv", "data/geospatial/voyage_history_fixturegrounded.csv",
                   "data/geospatial/ui_voyage_vectors.csv"],
         note="Feeds hold voyage tracks (24,485 rows), fixture-grounded voyage history (358,690 rows) and voyage vectors (2,657 rows); the derived speed/ballast/miles indices in the Drewry tables are not published as series anywhere in the feed set (verified: 0/120 match 'tonne-day')."),
    dict(id="port_master", concept="Port reference/master data (country, coordinates, vessel mix, industry mix)",
         publishers=["breakwave (daily)", "drewry (monthly)"],
         publisher_grain="static reference",
         bucket="ALREADY_IN_FEED",
         evidence=["data/geospatial/portwatch_ports_master.csv", "data/congestion/chokepoints_master.csv"],
         note="2,065 ports with lat/lon, flagship vessel mix and industry top-3; 28 chokepoints."),
    # ---------------- OFFSHORE (SEABROKERS) ----------------
    dict(id="osv_spot_rates", concept="OSV spot rates by category (PSV <900m2 / >900m2, AHTS <22,000bhp / >22,000bhp), North Sea",
         publishers=["seabrokers (monthly market report)"],
         publisher_grain="monthly average/min/max GBP per category",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feed files match 'osv', 'offshore' or 'dayrate'. Only report-derived data/derived/seabrokers_osv_dayrates.csv exists."),
    dict(id="osv_utilisation", concept="OSV fleet utilisation by category and region (Med PSV, Large PSV, Med AHTS, Large AHTS)",
         publishers=["seabrokers (monthly)"],
         publisher_grain="monthly utilisation %",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feeds match 'utilisation' or 'utilis'."),
    dict(id="rig_rates", concept="Rig rates and utilisation (jackups, semisubs, drillships by region: UK/Norway harsh, ultra-deepwater)",
         publishers=["seabrokers (monthly)"],
         publisher_grain="monthly $/day and utilisation %",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Verified: 0/120 feeds match 'rig', 'jackup' or 'drill' (the one 'rig' hit is 'freight' inside an unrelated grain-cost header)."),
    dict(id="offshore_snp_newbuild", concept="Offshore newbuilds / conversions / S&P and renewables (CSOV, SOV) activity",
         publishers=["seabrokers (monthly)"],
         publisher_grain="monthly transaction lists",
         bucket="GENUINELY_MISSING", evidence=[],
         note="No feed carries offshore transactions; the wider S&P gap (snp_transactions) applies a fortiori."),
    # ---------------- ETF / FILINGS ----------------
    dict(id="etf_fund_data", concept="Breakwave ETF data: BDRY/BWET NAV, premium/discount, flows, holdings, liquidity",
         publishers=["breakwave (daily insights)", "shipbrokers"],
         publisher_grain="daily NAV/flows/holdings",
         bucket="ALREADY_IN_FEED",
         evidence=["data/etf/BDRY_Daily.csv", "data/etf/BDRY_flows.csv", "data/etf/BWET_Daily.csv",
                   "data/etf/BWET_flows.csv", "data/etf/bdry_holdings_history.csv",
                   "data/etf/bwet_holdings_history.csv", "data/etf/bdry_liquidity.csv",
                   "data/etf/bwet_liquidity.csv"],
         note="BDRY daily 2,136 rows from 2018-03-21, flows 2,126, holdings history 1,023, liquidity 2,135; BWET equivalents from 2023-01-05."),
    dict(id="sec_filings", concept="SEC filings and XBRL financials for listed maritime companies",
         publishers=["shipbrokers (weekly equity sections)"],
         publisher_grain="per-filing",
         bucket="ALREADY_IN_FEED",
         evidence=["data/equities/sec_master_filing_catalog.csv", "data/equities/sec_xbrl_financials.csv",
                   "data/equities/sec_form4_insider_trades.csv", "data/equities/sec_exhibit99_announcements.csv"],
         note="92,200-row filing catalog with document URLs, 10,462 XBRL rows, 741 Form-4 rows, 688 8-K announcement rows."),
    dict(id="drewry_port_throughput", concept="Port throughput / breakbulk transport indices",
         publishers=["drewry (monthly)"],
         publisher_grain="monthly index",
         bucket="ALREADY_IN_FEED",
         evidence=["data/clarksons/drewry_port_throughput_indices.csv",
                   "data/clarksons/drewry_breakbulk_transport_indices.csv"],
         note="25 and 49 rows respectively, to 2026-08-01."),
    dict(id="container_values_teu", concept="Container vessel values by TEU class (900~1,200 / 1,600~1,850 / 2,700~2,900 etc.)",
         publishers=["shipbrokers (weekly)"],
         publisher_grain="weekly value per TEU band",
         bucket="UNSURE", evidence=["data/reference/fearnpulse_rates_full.csv"],
         note="Feed has container NEWBUILDING prices for 1,900/3,100/4,500/7,000/9,000/16,000/21,000 TEU; the report's narrow bands overlap but the feed headers do not state whether the quantities are the same (newbuild vs secondhand basis). Not guessed either way."),
    dict(id="scrap_vs_secondhand_map", concept="Per-vessel demolition destination (Alang / Aliaga / Chattogram / Gaddani) attached to fixture rows",
         publishers=["hellenic (daily demolition)"],
         publisher_grain="per-fixture destination",
         bucket="UNSURE", evidence=["data/demolition/shipandbunker_demolition_fixtures.csv"],
         note="Fixture feed has no destination column; whether the seller/source fields can be mapped to destination cannot be established from the file alone."),
    dict(id="narrative_commentary", concept="Broker market commentary / weekend reads / geopolitics / decarbonisation narrative",
         publishers=["breakwave (daily insights)", "shipbrokers (weekly, ~25 broker houses)", "baltic (weekly)", "drewry (opinions)", "signal"],
         publisher_grain="narrative text",
         bucket="GENUINELY_MISSING", evidence=[],
         note="Text, not a series. 97+ 'Market Commentary' headings, 74 'Macro/Geopolitics', 22 'Shipping Decarbonization Weekly Insights' in the breakwave HTML corpus alone."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    inv = json.load(open(FEED_JSON, encoding="utf-8"))
    feeds = inv["feeds"]
    feed_names = {os.path.basename(f["path"]): f for f in feeds}
    meta = {os.path.basename(f["path"]): f for f in feeds}

    # ---- validate every citation is a real feed file
    bad = []
    for row in M:
        for e in row["evidence"]:
            if os.path.basename(e) not in feed_names:
                bad.append((row["id"], e))
    if bad:
        print("ERROR - citations that are not canonical feeds:")
        for b in bad:
            print("   ", b)
        return 2

    # ---- enrichment: attach rows/date range to each cited feed
    for row in M:
        row["feed_evidence"] = [
            {"file": os.path.basename(e), "rows": meta[os.path.basename(e)]["rows"],
             "first": meta[os.path.basename(e)]["first"], "last": meta[os.path.basename(e)]["last"],
             "freq": meta[os.path.basename(e)]["freq"]}
            for e in row["evidence"]]

    # ---- verification sweep backing every GENUINELY_MISSING claim
    MISS_KW = {
        "iron_ore_brands": ["brand", "fines", "newman", "carajas", "pilbara", "yandi", "rtx"],
        "iron_ore_quality": ["alumina", "silica", "phosphorus", "moisture", "sulphur", "fe %"],
        "china_port_stocks": ["stock", "inventor", "caofeidian", "jingtang", "qingdao", "rizhao",
                              "beilun", "bayuquan", "dalian"],
        "steel_prices": ["hrc", "rebar", "wire rod", "plate", "crc", "coated", "billet"],
        "steel_inventories": ["steel inventor", "steel stock"],
        "ningbo_container": ["ningbo"],
        "snp_transactions": ["buyer", "sale_date", "seller", "vessel_name"],
        "scrap_prices": ["scrap", "ldt", "aliaga", "alang", "gaddani", "chattogram"],
        "fleet_by_country": ["flag", "beneficial owner", "ownership", "shipowner"],
        "fleet_by_type_full": ["car carrier", "reefer", "ro-ro", "roro", "cruise", "general cargo",
                               "combined carrier"],
        "osv_spot_rates": ["osv", "psv", "ahts", "offshore", "dayrate", "supply vessel"],
        "osv_utilisation": ["utilisation", "utilization"],
        "rig_rates": ["jackup", "drillship", "semisub", "rig rate", "rig count"],
        "offshore_snp_newbuild": ["csov", "sov", "subsea", "conversion"],
        "tonne_days": ["tonne-day", "tonneday", "tonne day", "ton-mile", "ton miles"],
        "carbon_ets": ["carbon", "eua", "allowance", "ets price"],
        "bunker_commentary": [],
        "narrative_commentary": [],
    }
    label_vocab = []
    for lf, col in (("data/reference/fearnpulse_rates_full.csv", "label"),
                    ("data/etf/bdry_holdings_history.csv", "Name"),
                    ("data/etf/bwet_holdings_history.csv", "Name")):
        try:
            import csv as _csv
            with open(lf, encoding="utf-8", errors="replace") as fh:
                label_vocab += [r.get(col, "") or "" for r in _csv.DictReader(fh)]
        except Exception:
            pass
    label_blob = " ".join(label_vocab).lower()

    MISS_INTERP = {
        "iron_ore_brands": "'pilbara' matches data/commodities/major_miners_quarterly_shipments.csv, which is quarterly "
                           "shipments per major miner (40 rows) - a different quantity from per-brand physical prices.",
        "snp_transactions": "'sale_date'/'seller'/'vessel_name' match only data/demolition/shipandbunker_demolition_fixtures.csv, "
                            "i.e. the demolition tape, not a secondhand sale-and-purchase tape; no 'buyer' column exists in any feed.",
        "fleet_by_type_full": "'roro' matches the port-call and chokepoint transit feeds, which count RoRo vessel calls at "
                              "ports - not a fleet size/orderbook by ship type.",
    }

    for row in M:
        if row["bucket"] != "GENUINELY_MISSING":
            continue
        kws = MISS_KW.get(row["id"], [])
        hits = []
        for kw in kws:
            where = []
            for f in feeds:
                if kw in os.path.basename(f["path"]).lower() or kw in f["header"].lower():
                    where.append(os.path.basename(f["path"]))
            if kw in label_blob:
                where.append("fearnpulse/holdings label vocab")
            if where:
                hits.append({"keyword": kw, "hit_in": sorted(set(where))[:5]})
        row["verification"] = {
            "keywords_swept": kws,
            "feeds_swept": len(feeds),
            "label_rows_swept": len(label_vocab),
            "hits": hits,
            "verdict": "no feed match" if not hits else "some keyword matches - inspect",
        }
        if row["id"] in MISS_INTERP:
            row["verification"]["interpretation"] = MISS_INTERP[row["id"]]
            row["verification"]["verdict"] = "no feed match (adjacent keyword only)"

    # ---- corpus side
    corpus = {}
    try:
        import duckdb
        con = duckdb.connect(CORPUS, read_only=True)
        corpus = {
            "series": con.execute("select count(*) from series").fetchone()[0],
            "observations": con.execute("select count(*) from series_points").fetchone()[0],
            "series_daily_rows": con.execute("select count(*) from series_daily").fetchone()[0],
            "by_source": [{"source": s, "series": n, "observations": int(p),
                           "first": str(f), "last": str(l)}
                          for s, n, p, f, l in con.execute(
                              "select source, count(*), sum(points), min(first_date), max(last_date) "
                              "from series group by 1 order by 3 desc").fetchall()],
        }
        ex = conn_rows = con.execute(
            "select entity_key, count(*), sum(points) from series group by 1 "
            "order by 3 desc limit 30").fetchall()
        corpus["top_entities"] = [{"entity": e, "series": n, "points": int(p)} for e, n, p in ex]
    except Exception as e:  # noqa: BLE001
        corpus = {"error": str(e)[:200]}

    buckets = {}
    for row in M:
        buckets.setdefault(row["bucket"], []).append(row["id"])
    largest = max(buckets.items(), key=lambda kv: (len(kv[1]), kv[0]))[0]

    out = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "method": {
            "feeds": "non-recursive top-level CSV in the 16 FEED_DIRS used by scripts/extract/coverage_audit.py",
            "publisher_side": "recurring report tables (series_priorities worklist), the `series` entity inventory, "
                              "and a heading census of the breakwave HTML insights (3,194 docs) and seabrokers .md months (97 docs); "
                              "`cells`/`label_series` were NOT used to judge coverage because they only see PDF tables",
            "buckets": {
                "ALREADY_IN_FEED": "feed publishes the same quantity at equal-or-finer grain; feed file cited",
                "PARTIALLY_COVERED": "feed touches the concept but scope/grain/history differs (partial_kind says how)",
                "GENUINELY_MISSING": "no feed file carries the quantity (stated on a verified keyword sweep of all 120 feeds)",
                "UNSURE": "cannot be decided from the artefacts; deliberately not guessed",
            },
            "citation_check": "every cited filename must be one of the enumerated feeds - the build fails otherwise",
            "missing_check": "GENUINELY_MISSING rows are backed by a keyword sweep of all 120 feeds: filename + header "
                             "for every feed, plus the label vocabulary of the two label-driven feeds "
                             "(fearnpulse_rates_full.csv label column, BDRY/BWET holdings Name column). "
                             "A header/label-level sweep, not an exhaustive row scan - hits are reported, not hidden.",
        },
        "inventory": {
            "csv_total_under_data": inv["csv_total"],
            "feed_files": inv["feed_count"], "feed_rows": inv["feed_rows"],
            "aux_files": inv["aux_count"], "aux_rows": inv["aux_rows"],
            "total_csv_rows": inv["feed_rows"] + inv["aux_rows"],
            "feeds": [{"file": os.path.basename(f["path"]), "dir": f["dir"], "rows": f["rows"],
                       "first": f["first"], "last": f["last"], "freq": f["freq"],
                       "header": f["header"][:150], "sample": f["sample"]} for f in feeds],
            "aux": [{"file": a["path"], "dir": a["dir"], "rows": a["rows"],
                     "first": a["first"], "last": a["last"], "freq": a["freq"],
                     "header": a["header"][:150]} for a in inv["aux"]],
            "aux_by_dir": sorted(
                [{"dir": d, "files": sum(1 for x in inv["aux"] if x["dir"] == d),
                  "rows": sum(x["rows"] for x in inv["aux"] if x["dir"] == d)}
                 for d in {x["dir"] for x in inv["aux"]}],
                key=lambda r: -r["rows"]),
        },
        "corpus": corpus,
        "matrix": M,
        "buckets": {k: {"count": len(v), "concepts": v} for k, v in
                    sorted(buckets.items(), key=lambda kv: -len(kv[1]))},
        "largest_bucket": largest,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"wrote {OUT}")

    # ---- print
    print("\n" + "=" * 108)
    print("INVENTORY")
    print("=" * 108)
    print(f"  CSVs under data/ (recursive) : {inv['csv_total']}")
    print(f"  canonical feed CSVs          : {inv['feed_count']:>4}   rows {inv['feed_rows']:>10,}")
    print(f"  auxiliary CSVs (non-feed)    : {inv['aux_count']:>4}   rows {inv['aux_rows']:>10,}")
    print(f"  TOTAL CSV rows               : {inv['feed_rows'] + inv['aux_rows']:>10,}")
    print(f"  corpus series / observations : {corpus.get('series'):,} / {corpus.get('observations'):,}")
    print("\n  feeds per directory:")
    agg = {}
    for f in feeds:
        k = f["dir"]
        agg.setdefault(k, [0, 0])
        agg[k][0] += 1
        agg[k][1] += f["rows"]
    for k, (n, r) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print(f"    {n:>3} files {r:>10,} rows   {k}")
    print("\n  corpus series by source:")
    for s in corpus.get("by_source", []):
        print(f"    {s['source']:<16}{s['series']:>6} series {s['observations']:>10,} obs  {s['first']}..{s['last']}")

    print("\n" + "=" * 108)
    print("GAP MATRIX  (bucket | concept | cited feed)")
    print("=" * 108)
    order = {"ALREADY_IN_FEED": 0, "PARTIALLY_COVERED": 1, "GENUINELY_MISSING": 2, "UNSURE": 3}
    for row in sorted(M, key=lambda r: (order[r["bucket"]], r["id"])):
        cite = ", ".join(e["file"] for e in row["feed_evidence"]) or "-"
        pk = f" [{row['partial_kind']}]" if row.get("partial_kind") else ""
        print(f"\n  {row['bucket']}{pk}")
        print(f"    concept : {row['concept']}")
        print(f"    reports : {', '.join(row['publishers'])}")
        print(f"    feed    : {cite}")
        print(f"    why     : {row['note']}")

    print("\n" + "=" * 108)
    print("BUCKET TOTALS")
    print("=" * 108)
    for b, v in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        print(f"  {b:<20}{len(v):>3}   {'<-- LARGEST' if b == largest else ''}")
    print(f"\n  largest bucket: {largest} ({len(buckets[largest])} of {len(M)} concepts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
