# LEDGER-13: Scraper Targets & Data Integrity Overhaul

**Prompt:** Prompt 13 — Live-Verified Scraper Targets  
**Date:** 2026-09-10  
**Status:** IN PROGRESS  

---

## TARGET 1A — Fearnpulse Label Audit & Unit Correction (Data Integrity Bug)

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/audit_and_fix_fearnleys_labels.py` (created)
  - `data/clarksons/fearnleys_benchmark_rates_continuous.csv` (rebuilt with corrected headers)
  - `data/clarksons/fearnleys_benchmark_rates_continuous.json` (rebuilt catalog metadata)
  - `scripts/cargo/build_cargo_cache.py` (updated freight lookups, route codes, and units)
  - `data/cargo/cargo_frontend_summary.json` (regenerated cache)
  - `tests/test_fearnleys_labels_and_ranges.py` (created regression test suite)
- **NETWORK CALLS & ENDPOINT AUDIT:**
  - `GET https://fearnpulse.com/api/marketapi/TS?id=11&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[11,145000,1788912000000,23],[11,130000,1788307200000,23],[11,120000,1787702400000,23]]}`. Observation: Rates $23k-$145k/day. Far exceeds standard LR1 1Y TC ($30-35k/day); represents high-spec asset or LNGC.
  - `GET https://fearnpulse.com/api/marketapi/TS?id=13&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[13,110000,1788912000000,23],[13,82500,1788307200000,23],[13,77500,1787702400000,23]]}`. Observation: Rates $15k-$110k/day. Far exceeds standard Handy 1Y TC ($14.5k/day); represents high-spec asset or VLGC.
  - `GET https://fearnpulse.com/api/marketapi/TS?id=1&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[1,30,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=2&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[2,40,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=3&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[3,40,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=4&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[4,275,1788912000000,23],...]}`. Live Suezmax WAF/UKC (WS points).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=5&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[5,107.5,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=6&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[6,115,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=7&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[7,162.5,1684713600000,1],...]}`. WS/index points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=8&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[8,130,1684713600000,1],...]}`. WS/index points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/api/marketapi/TS?id=9&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[9,200,1684713600000,1],...]}`. WS/index points (discontinued 2023-05-22).
  - `GET https://fearnpulse.com/fearnleys-weekly-report` -> Status 200, Next.js SPA HTML structure.
- **WHAT I DID:**
  1. Re-derived the complete tsId -> label -> class -> unit mapping across all 34 continuous series using `scripts/fearnleys/fetch_dry_routes_ts.py`, live API probing, and physical class rate ranges.
  2. Fixed the critical live data-integrity bugs where vessel classes were inverted:
     - `tsid 120654`: Corrected from `Pacific RV (Supramax)` to `Pacific RV (Capesize) [usd/day]`. Rates are $16.4k–$63.2k/day (latest $62.4k/day, median $31.4k/day).
     - `tsid 120655`: Corrected from `TCE Cont/Far East (Supramax)` to `TCE Cont/Far East (Capesize) [usd/day]`. Rates are $41.1k–$93.1k/day (latest $91.2k/day, median $55.6k/day).
     - `tsid 10010`: Corrected from `Transatlantic RV (Capesize)` to `Transatlantic RV (Panamax) [usd/day]`. Rates are $11.7k–$24.3k/day (median $17.4k/day).
     - `tsid 10011`: Corrected from `TCE Cont/Far East (Capesize)` to `TCE Cont/Far East (Panamax) [usd/day]`. Rates are $17.5k–$33.0k/day (median $24.9k/day).
     - `tsid 10012`: Corrected from `TCE Far East RV (Capesize)` to `TCE Far East RV (Panamax) [usd/day]`. Rates are $9.2k–$24.1k/day (median $16.8k/day).
     - `tsid 10013`: Corrected from `TCE Far East/Cont (Capesize)` to `TCE Far East/Cont (Panamax) [usd/day]`. Rates are $7.3k–$16.5k/day (median $10.8k/day).
     - `tsid 120129`: Corrected from `US Gulf - China/South Japan (Panamax)` to `US Gulf - China/South Japan (Supramax) [usd/day]`.
     - `tsid 120132`: Corrected from `Transatlantic RV (Panamax)` to `Transatlantic RV Delivery Cont (Supramax) [usd/day]`.
     - `tsid 120133`: Corrected from `Transatlantic RV Round 2 (Panamax)` to `Transatlantic RV Delivery USG (Supramax) [usd/day]`.
  3. Added explicit units to all series headers: `[worldscale]`, `[usd/day]`, `[usd/tonne]`, `[usd/bbl]`, `[fx]`, `[percent]`, `[index]`.
  4. Updated `scripts/cargo/build_cargo_cache.py` to reference corrected headers by tsId, relabel `route_code` for `Supramax USG-China/Japan (tsid 120129)` and `Panamax Transatlantic RV (tsid 10010)`, and rebuilt `data/cargo/cargo_frontend_summary.json`.
  5. Built regression test suite `tests/test_fearnleys_labels_and_ranges.py` validating all 34 column units, vessel class fixes, median plausibility bands, and JSON catalog coherence.
- **VERIFY COMMAND:**
  ```bash
  pytest tests/test_fearnleys_labels_and_ranges.py -v
  ```
- **EXPECTED RESULT:** 4 passed
- **ACTUAL RESULT:** 4 passed in 2.24s
- **DEVIATIONS:** None.
