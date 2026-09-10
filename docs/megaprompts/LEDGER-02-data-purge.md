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
