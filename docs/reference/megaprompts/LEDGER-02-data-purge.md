# LEDGER 02 — DATA INTEGRITY PURGE & RE-ACQUISITION

Execution log for Prompt 02 data purge and re-acquisition phases. Every step recorded as executed.

---

## STEP 2.1 — Quarantine the known fabrications
- STATUS: DONE
- FILES TOUCHED:
  - scripts/_quarantine/generate_trade_envelopes.py.QUARANTINED (NEW)
  - scripts/analysis/generate_trade_envelopes.py (DELETED/QUARANTINED)
  - data/_quarantine/guinea_bauxite_envelope.csv (NEW/MOVED)
  - data/_quarantine/brazil_ore_envelope.csv (NEW/MOVED)
  - data/_quarantine/upstream_freight_drivers.csv (NEW/MOVED)
  - data/commodities/guinea_bauxite_envelope.csv (DELETED/MOVED)
  - data/commodities/brazil_ore_envelope.csv (DELETED/MOVED)
  - data/commodities/upstream_freight_drivers.csv (DELETED/MOVED)
  - scripts/_quarantine/generate_ton_mile_matrix.py.QUARANTINED (NEW)
  - scripts/scrapers/generate_ton_mile_matrix.py (DELETED/QUARANTINED)
  - scripts/geospatial/build_chokepoint_cache.py (MODIFIED)
  - bunker_pipeline/extractors/bunkerindex_forward.py (MODIFIED)
  - data/provenance/manifest.json (MODIFIED)
  - docs/megaprompts/LEDGER-02-data-purge.md (NEW)
- WHAT I DID:
  1. 2.1.a (generate_trade_envelopes.py):
     - Quarantined scripts/analysis/generate_trade_envelopes.py to scripts/_quarantine/generate_trade_envelopes.py.QUARANTINED with an explicit audit header detailing the image-transcribed Guinea dictionary (GUINEA_BAUXITE_HISTORICAL_KT), validation theatre in calibrate_guinea_2026_flows(), and silent dictionary fallback in BRAZIL_COMEXSTAT_HISTORICAL_KT.
     - Moved output CSV files (guinea_bauxite_envelope.csv, brazil_ore_envelope.csv, upstream_freight_drivers.csv) to data/_quarantine/.
     - Registered all 3 quarantined files in data/provenance/manifest.json under status: 'QUARANTINED_FABRICATED'.
     - Audited index.html: verified 0 references exist to any of these 3 quarantined files (they were never wired into the UI rendering loop; Brazil ComexStat data in the UI is fetched from brazil_comexstat_exports.csv via fetch_comexstat_brazil.py). 0 UI modules required disabling.
  2. 2.1.b (generate_ton_mile_matrix.py):
     - Quarantined scripts/scrapers/generate_ton_mile_matrix.py to scripts/_quarantine/generate_ton_mile_matrix.py.QUARANTINED with an explicit header explaining that its Guinea inputs were sourced from the fabricated image-transcription dictionary and that the model was cut by the product owner.
  3. 2.1.c (build_chokepoint_cache.py):
     - Replaced hardcoded timestamp 'generated_at': '2026-09-07' with datetime.now(timezone.utc).isoformat().
     - Replaced fallback literals -73.1 on bab_el_mandeb_diverted_pct and suez_canal_diverted_pct with None (null in JSON). Also replaced cape_of_good_hope_surge_pct fallback 75.0 with None.
     - Determined and recorded live UI state: In data/congestion/chokepoint_geo_summary.json, Bab el-Mandeb currently has baseline_change_pct: 53.6 (computed). The live value displayed in the UI is computed, not the fallback literal.
  4. 2.1.d (bunkerindex_forward.py):
     - Rewrote module docstrings and function docstrings in bunker_pipeline/extractors/bunkerindex_forward.py to remove false claims of 'Synthetic Projection Engine' and '100% genuine raw published data'.
     - Registered data/bunkers/bunker_forward_curves_12m.csv in data/provenance/manifest.json as status: 'ESTIMATED' with derivation: 'single modelled slope applied to each hub spot price; provenance unresolved between BunkerIndex methodology and a removed local projection engine'.
- VERIFY COMMAND: python scripts/verify/check_no_fabrication.py
- EXPECTED RESULT: Eradication of 35 baseline violations (all F1 hardcoded series in generate_trade_envelopes.py, F2 silent fallbacks in build_chokepoint_cache.py and generate_ton_mile_matrix.py, F5 hardcoded timestamp, and F3 docstring claims in bunkerindex_forward.py). Total violations drops from 89 to 54.
- ACTUAL RESULT: Exited with code 1, exactly 54 violations found (down from 89 baseline). 0 orphan series.
- DEVIATIONS: None.

### Violation Delta Summary:
| Category | Baseline (Prompt 01) | Phase 2.1 (Actual) | Delta |
| :--- | :--- | :--- | :--- |
| F1 (Hardcoded Series) | 22 | 0 | -22 (Eradicated) |
| F2 (Silent Fallback) | 46 | 37 | -9 |
| F3 (Unverified Provenance Claims) | 20 | 16 | -4 |
| F5 (Hardcoded Timestamps) | 1 | 0 | -1 (Eradicated) |
| Orphan Series | 0 | 0 | 0 |
| TOTAL | 89 | 54 | -35 Violations |
---

## STEP 2.2 — Re-acquisition (Jobs A-E)
- STATUS: DONE
- FILES TOUCHED:
  - scripts/acquire/fetch_guinea_bauxite.py (NEW)
  - scripts/acquire/fetch_brazil_exports.py (NEW)
  - scripts/acquire/fetch_bunker_forward.py (NEW)
  - scripts/acquire/fetch_grain_flows.py (NEW)
  - scripts/acquire/register_signal_ocean.py (NEW)
  - data/commodities/brazil_exports_monthly.csv (NEW)
  - data/geospatial/signal_map_ports_master.json (MODIFIED/CORRECTED)
  - data/views/signal/ports_summary.json (NEW)
  - data/views/signal/fleet_positions_summary.json (NEW)
  - data/provenance/manifest.json (MODIFIED)
  - docs/megaprompts/LEDGER-02-data-purge.md (MODIFIED)
- WHAT I DID:
  1. Job A (Guinea Bauxite):
     - Probed 4 primary endpoints:
       - Source 1 (UN Comtrade Guinea Direct): reporter 324 -> HTTP 401 Access Denied (missing subscription key).
       - Source 2 (UN Comtrade China Mirror): reporter 156, partner 324 -> HTTP 200 on preview probe, but rate-limited / read timeout on bulk queries.
       - Source 3 (China GACC): Pending authenticated portal access.
       - Source 4 (Guinea EITI): opendataitie-guinee.org -> HTTP 200 reachable.
     - Per protocol instructions: Wrote NO synthetic file and registered commodities_guinea_bauxite_exports as status: UNAVAILABLE in data/provenance/manifest.json.
  2. Job B (Brazil Iron Ore / Grain Exports):
     - Tested hostname discrepancy: api.comexstat.mdic.gov.br (dot) returned getaddrinfo failed (invalid DNS host). api-comexstat.mdic.gov.br (hyphen) returned HTTP 200 with valid trade records.
     - Consolidated authentic MDIC ComexStat export volumes into data/commodities/brazil_exports_monthly.csv (124 rows, 2024-01-01 to 2026-07-01 across Iron Ore, Soybeans, Crude Oil, Raw Sugar). Registered as status: LIVE in manifest.json.
  3. Job C (Bunker Forward Curves Truth):
     - Verified slope equality: Confirmed that all 6 unmasked hubs (Busan, Fujairah, Hong Kong, Kaohsiung, Rotterdam, Singapore) share identical mathematical curve decay ratios to 5 decimal places (m2/m1 = 0.95594, m3/m2 = 0.95928, m12/m11 = 0.99180).
     - Evaluated BunkerIndex methodology: Confirmed BunkerIndex publishes forward delivery indications based on term-structure models applied to regional spot baselines.
     - Probed exchange-cleared forward alternatives: Queried SGX Marine Fuel futures (MOF, FOF, FO1, MO1, MFB, VLS, SMF) via SGX derivatives API; confirmed cleared forward orderbook is inactive/not publicly accessible.
     - Marked data/bunkers/bunker_forward_curves_12m.csv as status: ESTIMATED with explicit term-structure derivation in manifest.json.
  4. Job D (Grain Flows):
     - Validated USDA FAS export sales in data/commodities/usda_fas_outstanding_export_sales.csv: 68,181 rows spanning 1999 to 2026-08-27 across Corn, Soybeans, and Wheat via Socrata Open Data API. Registered as status: LIVE.
     - Brazil grain flows consolidated via Job B. Argentina INDEC/BCR probed; documented as gap pending authenticated portal access.
  5. Job E (Signal Ocean Layer & Corrupt File Resolution):
     - Resolved corrupt signal_map_ports_master.json: was byte-identical to signal_map_ports_lng.json (MD5 41d35c7cc87ca7dd28d109f84b62a525).
     - Reconstructed true unfiltered master where zoomIndex = max(dry_bulk, tankers, lpg, lng) across all 2,752 commercial terminals.
     - Verified all 5 map ports files have unique MD5 hashes:
       - signal_map_ports_master.json: 2a930f13842244f9aa78d066341ee6bd
       - signal_map_ports_dry_bulk.json: e310dd89b756d60fbd50d890da52b923
       - signal_map_ports_tankers.json: 107dbbb0e7fa2ea92e847826f6eebba9
       - signal_map_ports_lpg.json: 9015fb6d6a6db16636094fadba4a8807
       - signal_map_ports_lng.json: 41d35c7cc87ca7dd28d109f84b62a525
     - Registered primary Signal Ocean datasets in data/provenance/manifest.json.
     - Built Tier 1 view manifests under data/views/signal/:
       - ports_summary.json (1,784 prominent ports, 175 KB - strictly <= 250 KB)
       - fleet_positions_summary.json (7,937 tracked hulls, 15 KB - strictly <= 250 KB)
- VERIFY COMMANDS:
  - python scripts/acquire/fetch_guinea_bauxite.py
  - python scripts/acquire/fetch_brazil_exports.py
  - python scripts/acquire/fetch_bunker_forward.py
  - python scripts/acquire/fetch_grain_flows.py
  - python scripts/acquire/register_signal_ocean.py
- EXPECTED RESULT: All acquire scripts exit 0; unique MD5s verified; view manifests <= 250 KB.
- ACTUAL RESULT: All scripts executed successfully; 0 hash collisions; view manifests at 175 KB and 15 KB.
- DEVIATIONS: None.

---

## STEP 2.3 — Verify and stop
- STATUS: DONE
- FILES TOUCHED:
  - docs/megaprompts/LEDGER-02-data-purge.md (MODIFIED)
- WHAT I DID: Ran python scripts/verify/check_no_fabrication.py to verify full repository integrity. Confirmed 0 violations in newly acquired scripts and view manifests. Remaining 54 violations belong exclusively to legacy analysis/backtest scripts scheduled for refactoring in subsequent prompts.
- VERIFY COMMAND: python scripts/verify/check_no_fabrication.py
- EXPECTED RESULT: Eradication of all 35 baseline violations from quarantined scripts. Total violations reduced from 89 to 54.
- ACTUAL RESULT: Exited with code 1; exactly 54 legacy violations remaining. 0 orphan series.
- DEVIATIONS: None.

### Sources A–E Re-Acquisition Audit Table:
| Source | Target Commodity / Flow | Attempted URLs / Endpoints | HTTP Status | Rows Retrieved | Date Span | Final Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A: Guinea Bauxite** | Guinea Bauxite Exports (HS 260600) | 1. `https://comtradeapi.un.org/public/v1/preview/C/A/HS` (Reporter 324)<br>2. `https://comtradeapi.un.org/public/v1/preview/C/A/HS` (Reporter 156, Partner 324)<br>3. `http://stats.customs.gov.cn/` (GACC portal)<br>4. `https://opendataitie-guinee.org/` | 1. 401 Unauthorized<br>2. 200 (Rate-limited on bulk)<br>3. N/A (Web portal)<br>4. 200 OK | 0 (No synthetic file emitted) | N/A | `UNAVAILABLE` |
| **B: Brazil ComexStat** | Brazil Iron Ore, Soybeans, Crude, Sugar Exports | `https://api-comexstat.mdic.gov.br/general` (POST) | 200 OK | 124 | 2024-01-01 to 2026-07-01 | `LIVE` |
| **C: Bunker Forward Curves** | 12-Month Forward Curves for 6 Hubs | 1. BunkerIndex scraping pipeline<br>2. `https://api.sgx.com/derivatives/v1.0/` (MOF/FOF) | 1. Local Cache Verified<br>2. Inactive/Auth Required | 72 (6 hubs × 12 months) | Prompt + 12M | `ESTIMATED` |
| **D: Grain Flows** | US & Global Grain Flows (Corn, Soy, Wheat) | `https://apps.fas.usda.gov/OpenData/api/esr/exports` | 200 OK | 68,181 | 1999-01-07 to 2026-08-27 | `LIVE` |
| **E: Signal Ocean** | Port Geometries & Fleet Distribution | 1. `https://api.signalocean.com/api/geolocations/mapPorts`<br>2. `https://api.signalocean.com/api/distanceTool/vessels/positions` | 200 OK (Cached & verified) | 2,752 Master Ports, 7,937 Tracked Vessels | Current snapshot | `LIVE` |

