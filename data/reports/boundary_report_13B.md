# BOUNDARY REPORT — PROMPT 13B (CORRECTIONS AUDIT C1–C10)
**Generated Verbatim by `scripts/verify/generate_boundary_report.py`**
**Execution Timestamp:** 2026-09-11T08:55:38Z

---

## 1. Global Machine Gates

| Gate | Target / Check | Expected | Actual Result | Status |
|---|---|---|---|---|
| **Gate 1** | `scripts/verify/check_no_fabrication.py` | 0 violations, exits 0 | 0 violations found | **PASS** |
| **Gate 2** | `scripts/verify/check_source_citations.py` | 100% 200 OK, verbatim quotes & numbers match | 13 live citations verified authentic | **PASS** |
| **Gate 3** | Pytest suites (`test_taxonomy_mutation`, `test_comtrade_selection`, `test_detector_mutation`, `test_fearnleys_labels_and_ranges`) | All tests pass, 0 failures | 19 passed (4.55s) | **PASS** |

---

## 2. Corrections Summary (C1 through C10)

| Correction | Target Series / Subsystem | Before Audit | After Correction | Validation / Proof |
|---|---|---|---|---|
| **C1 — Pilbara Purge** | Australia Pilbara Ports | 92 rows in Hedland (30 fabricated), 3 Dampier | **15 Hedland rows** (2020-10-01 -> 2024-05-01); **251 Dampier rows** (2002-07-01 -> 2026-06-01) | Purged 30 fake rows; Dampier sourced from authentic June 2026 PPA PDF (`dampier_cargo_statistics_june_2026.pdf`) |
| **C2 & C10.3 — Guinea Bauxite** | Guinea Bauxite Exports | 120 rows (18 fake `data-hub`, 6 fake trade-press, wrong `_mt` unit) | **107 authentic rows**: 11 company_monthly (GMI #82 verbatim quotes) + 96 bilateral mirror; Unit: `tonnes (import_volume_t)` | Purged 24 unverified rows; verified quotes match live page text; unit changed to tonnes |
| **C3 — Fleet Supply** | Fleet Orderbook & Age Profile | Capesize: 2,256 hulls (included 543 scrapped), avg age 17.4y; UNCTAD literals in script | **Capesize active fleet: 1,702 hulls, avg age 12.4 y**; Orderbook: 208 hulls; Unresolved: 86 hulls; Scrapped excluded: 543 | Classifies exclusively by `orderBookStatusID` (7=active, 1/2=orderbook, 8=scrapped, 4/5/6=unresolved); 0 UNCTAD literals |
| **C4 — Comtrade Selection** | Minor Bulks Monthly | First-row selection bug corrupted Turkey scrap (6.9k vs 1.84M t), ferts (2.4 vs 447k t), cement (0.01 vs 1.89M t) | Shared client `select_total` enforcing `motCode==0 and customsCode=='C00' and partner2Code==0`. Total **321 rows** across 7 commodities | `tests/test_comtrade_selection.py` passed; volume range: 11,471.9 t to 8,451,820.0 t |
| **C5 — Brazil Splicing** | Brazil ComexStat Exports | Spliced 4-digit HS onto 8-digit NCM without matching codes; no `source`/`method` columns | **557 rows** (2017-01-01 -> 2026-07-01) with exact HS 6-digit backfill; `source` and `method` populated on 100% of rows | Seam test deviation at 2024-01: Iron ore 0.00070%, max commodity diff 0.054% (<= 0.5% tolerance) |
| **C6 — Indonesia Coal** | Indonesia Coal Exports | 72 rows carried fabricated `"India (~25-28%)"`; May/July 2026 cited generic index with English quote | **74 rows** (2020-01-01 -> 2026-04-01); 0 rows with `~` in destinations; Jan 2022 ban row (10.92 Mt) preserved & annotated | Katadata releases cited with authentic verbatim Indonesian quotes verified HTTP 200 |
| **C7 — Taxonomy Coherence** | Fearnleys tsId Continuous Rates | Generic coherence check had no teeth (passed 5 wrong planted codes) | **34 registered tsIds** in `fearnleys_tsid_registry.json`; continuous CSV has 34 headers (14263 rows, 1985-01-04 -> 2026-09-10) | `tests/test_taxonomy_mutation.py` passed (5/5 planted mutations caught and rejected) |
| **C8 — Detector Hardening** | Verification System | Detector exempted 33 entire scripts via bare paths; missed list-of-dicts and constant fills | Allowlist converted to **55 exact `path:line:rule` entries** (0 bare paths); F1b & F3b rules added | `tests/test_detector_mutation.py` passed (4/4 mutations caught: Pilbara list-of-dicts, Indonesia annotation, bare path, F3b) |
| **C9 — Report Generator** | Boundary Reporting | Previous boundary report tsId table was invented and contradicted ledger | Boundary report produced 100% dynamically by `scripts/verify/generate_boundary_report.py` | This document is the verbatim output of the script |
| **C10 — Small Fixes** | worldsteel, USDA, Guinea units | worldsteel benchmark circular prompt ref; USDA missing loading/waiting queues; Guinea volume unit wrong | **worldsteel June 2026 benchmark (155.7 Mt global, 83.7 Mt China)** dynamically derived; USDA queues (3304 rows) include `loading` and `waiting_to_load`; Guinea unit is tonnes | `data/commodities/world_crude_steel_metadata.json` updated; `usda_grain_vessel_loading_queues.csv` updated |

---

## 3. Fearnleys tsId Continuous Rates Registry & Taxonomy Alignment (34 Series)

| tsId | Route Code | Fearnpulse Name | Taxonomy Description | Confidence | CSV Date Span |
|---|---|---|---|---|---|
| 1 | `TD3/TD3C` | MEG/Japan (transitioned to China) | Middle East Gulf to China (TD3C) / Middle East Gulf to Japan (historical TD3) | verified | 1985-01-04 -> 2026-09-10 |
| 2 | `TD2` | MEG/Singapore | Middle East Gulf to Singapore | verified | 1985-01-04 -> 2026-09-10 |
| 3 | `TD15` | WAF/FEAST | West Africa to China | verified | 1985-01-04 -> 2026-09-10 |
| 4 | `TD20` | WAF/UKC | West Africa to UK-Continent | verified | 1985-01-04 -> 2026-09-10 |
| 5 | `N/A` | Market Brief (Dirty Tanker) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 6 | `TD19` | Cross Med | Cross Mediterranean | verified | 1985-01-04 -> 2026-09-10 |
| 7 | `N/A` | 1 Year TC - VLCC | None | unverified | 1985-01-04 -> 2026-09-10 |
| 8 | `N/A` | 1 Year TC - Suezmax | None | unverified | 1985-01-04 -> 2026-09-10 |
| 9 | `N/A` | 1 Year TC - Aframax | None | unverified | 1985-01-04 -> 2026-09-10 |
| 11 | `N/A` | Specialized High-Spec TC | None | unverified | 1985-01-04 -> 2026-09-10 |
| 13 | `N/A` | Specialized Asset Rate | None | unverified | 1985-01-04 -> 2026-09-10 |
| 303 | `N/A` | 380 CST Bunker Price (Singapore) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 304 | `N/A` | MGO Bunker Price (Singapore) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 306 | `N/A` | 380 CST Bunker Price (Rotterdam) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 307 | `N/A` | MGO Bunker Price (Rotterdam) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 316 | `N/A` | Commodity Prices (Brent Crude) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 5001 | `N/A` | USD/KRW | None | unverified | 1985-01-04 -> 2026-09-10 |
| 5002 | `N/A` | USD/NOK | None | unverified | 1985-01-04 -> 2026-09-10 |
| 5003 | `N/A` | EUR/USD | None | unverified | 1985-01-04 -> 2026-09-10 |
| 10001 | `C3` | Capesize Tubarao/Qingdao | Tubarao to Qingdao | verified | 1985-01-04 -> 2026-09-10 |
| 10002 | `C5` | Capesize Australia/China | West Australia to Qingdao | verified | 1985-01-04 -> 2026-09-10 |
| 10003 | `N/A` | Capesize Newcastle/Qingdao Coal | None | unverified | 1985-01-04 -> 2026-09-10 |
| 10010 | `P1A_82` | Panamax Transatlantic RV | Skaw-Gib transatlantic round voyage | verified | 1985-01-04 -> 2026-09-10 |
| 10011 | `P2A_82` | Panamax TCE Cont/Far East | Skaw-Gib trip HK-S Korea incl Taiwan | verified | 1985-01-04 -> 2026-09-10 |
| 10012 | `P3A_82` | Panamax TCE Far East RV | Hong Kong-South Korea transpacific round voyage | verified | 1985-01-04 -> 2026-09-10 |
| 10013 | `P4_82` | Panamax TCE Far East/Cont | Hong Kong-South Korea trip to Skaw-Passero | verified | 1985-01-04 -> 2026-09-10 |
| 11323 | `BDI` | Baltic Dry Index | Baltic Dry Index composite freight benchmark | verified | 1985-01-04 -> 2026-09-10 |
| 12100 | `N/A` | Interest Rates (SOFR/LIBOR) | None | unverified | 1985-01-04 -> 2026-09-10 |
| 120129 | `S1C` | Supramax US Gulf - China/South Japan | US Gulf trip to China-south Japan | verified | 1985-01-04 -> 2026-09-10 |
| 120132 | `S4B` | Supramax Transatlantic RV (raw A) | Skaw-Passero trip to US Gulf | verified | 1985-01-04 -> 2026-09-10 |
| 120133 | `S4A` | Supramax Transatlantic RV (raw B) | US Gulf trip to Skaw-Passero | verified | 1985-01-04 -> 2026-09-10 |
| 120137 | `S10` | Supramax South China - Indonesia RV | South China trip via Indonesia to south China | verified | 1985-01-04 -> 2026-09-10 |
| 120654 | `C10_182` | Capesize Pacific RV | China-Japan transpacific round voyage | verified | 1985-01-04 -> 2026-09-10 |
| 120655 | `C9_182` | Capesize TCE Cont/Far East | Continent/Mediterranean trip China-Japan | verified | 1985-01-04 -> 2026-09-10 |

---

## 4. Provenance Manifest & Series Inventory (Touched Data Series)

| Series ID | Display Name | Status | Rows | Date Span | Unit | Last Fetched (UTC) |
|---|---|---|---|---|---|---|
| `clarksons_fearnleys_benchmark_rates_continuous` | Clarksons — Fearnleys Benchmark Rates Continuous | **LIVE** | 14263 | 1985-01-04 -> 2026-09-10 | USD/day / WS | 2026-09-10T18:23:53 |
| `commodities_australia_ppa_iron_ore` | Australia Pilbara Ports (Port Hedland Iron Ore) | **LIVE** | 15 | 2020-10-01 -> 2024-05-01 | Mt/mo | 2026-09-11T08:51:20 |
| `commodities_brazil_comexstat_exports` | Brazil Bulk Commodity Exports (Monthly) | **LIVE** | 557 | 2017-01-01 -> 2026-07-01 | Metric Tonnes / USD FOB | 2026-09-11T08:51:20 |
| `commodities_usda_grain_vessel_loading_queues` | USDA AMS Grain Vessel Loading Queues (Gulf & PNW) | **LIVE** | 3304 | 1995-01-04 -> 2026-09-03 | Vessels | 2026-09-11T08:33:06 |
| `commodities_guinea_bauxite_exports` | Guinea Bauxite Exports (Monthly) | **LIVE** | 107 | 2017-01-01 -> 2026-01-01 | tonnes (import_volume_t) | 2026-09-11T08:51:20 |
| `commodities_australia_ppa_dampier_throughput` | Australia Pilbara Ports (Port of Dampier Throughput) | **LIVE** | 251 | 2002-07-01 -> 2026-06-01 | Mt/mo | 2026-09-11T08:51:20 |
| `commodities_usda_grain_vessel_loading` | USDA AMS Grain Vessel Loading Activity (31-Year History) | **LIVE** | 3304 | 1995-01-04 -> 2026-09-03 | Vessels | 2026-09-11T08:33:06 |
| `commodities_indonesia_coal_exports` | Indonesia Coal Exports (Monthly) | **LIVE** | 74 | 2020-01-01 -> 2026-04-01 | Mt | 2026-09-11T08:51:20 |
| `commodities_minor_bulks_monthly` | Minor Bulks Monthly (Scrap, Fertilizer, Cement, Nickel Ore, Sugar, Alumina) | **LIVE** | 321 | 202201 -> 202607 | Metric Tonnes / USD | 2026-09-11T08:51:20 |
| `commodities_world_crude_steel_monthly` | World Crude Steel Monthly Production | **LIVE** | 31 | 2024-01-01 -> 2026-07-01 | Million Tonnes (Mt) | 2026-09-11T08:51:20 |
| `supply_fleet_orderbook_and_age_profile` | Commercial Fleet Orderbook and Age Profile | **LIVE** | 11 | 2026-09-10 -> 2026-09-10 | Vessels / Mdwt | 2026-09-11T08:51:20 |

---

## 5. Hard Stop Conditions & Absence Declarations

1. **GMI Data Hub Purge (Guinea Bauxite)**:
   `https://www.guineamininginsights.com/data-hub` was confirmed to be a high-level portal landing page containing no historical data tables or company-level monthly exports. The 18 hardcoded rows from Prompt 13 citing this URL have been completely **purged**. Data from 2017 to 2024 is legitimately sourced from UN Comtrade bilateral import mirror flows (96 rows), and January 2026 is sourced from authentic GMI Article #82 (11 rows). Gaps between 2025-01 and 2025-12 are left **absent** as unavailable.
2. **May / July 2026 Indonesian Coal Exports**:
   BPS generic publication index did not contain verified monthly tables for May and July 2026. Rather than fabricating or approximating values, those two rows were **purged**. January 2026 and April 2026 Katadata releases with verbatim quotes and numeric matching were retained.
3. **UNCTAD Merchant Fleet Literals**:
   Static UNCTAD fleet figures (`116,000 vessels`, `2.50 billion DWT`, etc.) in `fetch_fleet_supply.py` were purged because the target URLs served single-page app shells lacking those figures. Fleet figures are computed solely from authentic Signal Ocean records filtered by `orderBookStatusID == 7`.
4. **USDA Vancouver Queues**:
   Vancouver grain queue data was recorded as `n/a` in the source USDA report and is left absent rather than estimated.

---

## 6. Touched Files Inventory

The following files were created or modified as part of Corrections C1 through C10:
- `data/reference/signal_orderbook_status_map.json` (NEW)
- `data/reference/fearnleys_tsid_registry.json` (NEW)
- `data/reference/baltic_route_taxonomy.json` (MODIFIED: BDI, TD3/TD3C)
- `data/raw/dampier_cargo_statistics_june_2026.pdf` (NEW: authentic source PDF)
- `scripts/acquire/fetch_pilbara_ports.py` (MODIFIED: C1)
- `data/commodities/australia_ppa_iron_ore.csv` (MODIFIED: C1)
- `scripts/acquire/fetch_guinea_bauxite.py` (MODIFIED: C2, C10.3)
- `data/commodities/guinea_bauxite_exports.csv` (MODIFIED: C2, C10.3)
- `scripts/acquire/fetch_fleet_supply.py` (MODIFIED: C3)
- `data/supply/fleet_orderbook_and_age_profile.csv` (MODIFIED: C3)
- `data/supply/merchant_fleet_summary.json` (MODIFIED: C3)
- `scripts/acquire/comtrade_client.py` (NEW: C4)
- `tests/test_comtrade_selection.py` (NEW: C4)
- `scripts/acquire/fetch_minor_bulks.py` (MODIFIED: C4)
- `data/commodities/minor_bulks_monthly.csv` (MODIFIED: C4)
- `scripts/acquire/fetch_brazil_comexstat_full.py` (MODIFIED: C5)
- `data/commodities/brazil_comexstat_exports.csv` (MODIFIED: C5)
- `scripts/acquire/fetch_indonesia_coal.py` (MODIFIED: C6)
- `data/commodities/indonesia_coal_exports_monthly.csv` (MODIFIED: C6)
- `tests/test_fearnleys_labels_and_ranges.py` (MODIFIED: C7)
- `tests/test_taxonomy_mutation.py` (NEW: C7)
- `scripts/verify/fabrication_allowlist.txt` (MODIFIED: C8, converted to path:line:rule)
- `scripts/verify/check_no_fabrication.py` (MODIFIED: C8, hardened rules F1b/F1/F3b)
- `scripts/verify/check_source_citations.py` (NEW: C8)
- `tests/test_detector_mutation.py` (NEW: C8)
- `scripts/verify/generate_boundary_report.py` (NEW: C9)
- `scripts/acquire/fetch_world_steel_production.py` (MODIFIED: C10.1)
- `data/commodities/world_crude_steel_metadata.json` (MODIFIED: C10.1)
- `scripts/acquire/fetch_usda_grain_queues.py` (MODIFIED: C10.2)
- `data/commodities/usda_grain_vessel_loading.csv` (MODIFIED: C10.2)
- `data/commodities/usda_grain_vessel_loading_queues.csv` (MODIFIED: C10.2)
- `data/provenance/manifest.json` (MODIFIED: C1-C10)
- `docs/megaprompts/LEDGER-13B-corrections.md` (NEW: step-by-step audit record)

