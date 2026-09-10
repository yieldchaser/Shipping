# LEDGER-13: Scraper Targets & Data Integrity Overhaul

**Prompt:** Prompt 13 — Live-Verified Scraper Targets  
**Date:** 2026-09-10  
**Status:** IN PROGRESS  

---

## TARGET 1A — Fearnpulse Label Audit, Baltic Route Codes & Unit Correction (Data Integrity Bug)

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_baltic_route_taxonomy.py` (created)
  - `data/reference/baltic_route_taxonomy.json` (created - 109 routes, 7 index formulas, 4 vessel specs)
  - `scripts/acquire/audit_and_fix_fearnleys_labels.py` (updated with Baltic route codes and TC resolution)
  - `data/clarksons/fearnleys_benchmark_rates_continuous.csv` (rebuilt with corrected headers carrying route codes)
  - `data/clarksons/fearnleys_benchmark_rates_continuous.json` (rebuilt catalog metadata with route codes)
  - `scripts/cargo/build_cargo_cache.py` (updated freight lookups, Baltic route codes S1C and P1A_82)
  - `data/cargo/cargo_frontend_summary.json` (regenerated cache)
  - `tests/test_fearnleys_labels_and_ranges.py` (regression test suite covering 5 tests)
  - `data/provenance/manifest.json` (registered `reference_baltic_route_taxonomy`)
- **NETWORK CALLS & ESCALATION LADDER AUDIT (§0.66):**
  - **Baltic Exchange Route Taxonomy:**
    - `[Rung 1] GET https://www.balticexchange.com/en/data-services/market-information0/indices.html` with full browser headers (`User-Agent`, `Accept`, `Accept-Language`, `Referer: https://www.balticexchange.com/`). Response: HTTP 200, 1,932 bytes, `<title>Challenge Validation</title>` (Imperva Crypto WAF challenge iframe).
    - `[Rung 4] Headless Playwright Chromium` with `--disable-blink-features=AutomationControlled`. Result: Imperva Challenge Validation remained active on headless runner.
    - `[Rung 7] GET https://web.archive.org/cdx/search/cdx?url=balticexchange.com/en/data-services/market-information0/indices.html*&output=json&limit=10&sort=reverse`. Result: Identified valid 200 snapshot `20260420064708`.
    - `[Rung 7] GET https://web.archive.org/web/20260420064708id_/https://www.balticexchange.com/en/data-services/market-information0/indices.html`. Response: HTTP 200, 105,142 bytes. Parsed 10 HTML tables (109 routes), 7 index construction formulas (BCI, BPI, BSI, BHSI, BCTI, BDTI, BLPG), 4 standard vessel specs (Capesize 182k, Panamax 82.5k, Supramax 63.5k, Handysize 38.2k), and 9 basket definitions.
  - **Fearnpulse Probe Calls:**
    - `GET https://fearnpulse.com/api/marketapi/TS?id=11&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[11,145000,1788912000000,23],[11,130000,1788307200000,23],[11,120000,1787702400000,23]]}`. Observation: Rates $23k-$145k/day. Far exceeds standard LR1 1Y TC ($30-35k/day); represents high-spec asset or LNGC.
    - `GET https://fearnpulse.com/api/marketapi/TS?id=13&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[13,110000,1788912000000,23],[13,82500,1788307200000,23],[13,77500,1787702400000,23]]}`. Observation: Rates $15k-$110k/day. Far exceeds standard Handy 1Y TC ($14.5k/day); represents high-spec asset or VLGC.
    - `GET https://fearnpulse.com/api/marketapi/TS?id=1&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[1,30,1684713600000,1],...]}`. TD3C WS points (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=2&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[2,40,1684713600000,1],...]}`. TD2 WS points (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=3&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[3,40,1684713600000,1],...]}`. TD15 WS points (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=4&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[4,275,1788912000000,23],...]}`. Live Suezmax WAF/UKC TD20 (WS points).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=5&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[5,107.5,1684713600000,1],...]}`. WS points (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=6&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[6,115,1684713600000,1],...]}`. TD19 WS points (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=7&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[7,162.5,1684713600000,1],...]}`. WS points 55-430 (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=8&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[8,130,1684713600000,1],...]}`. WS points 62.5-330 (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/api/marketapi/TS?id=9&last=3` -> Status 200, response: `{"columns":["tsid","value","date","jobid"],"index":[0,1,2],"data":[[9,200,1684713600000,1],...]}`. WS points 10-575 (discontinued 2023-05-22).
    - `GET https://fearnpulse.com/fearnleys-weekly-report` -> Status 200, Next.js SPA HTML structure.
- **WHAT I DID:**
  1. Built and executed `scripts/acquire/fetch_baltic_route_taxonomy.py` climbing the Guardrail §0.66 escalation ladder to harvest the full Baltic Exchange Route Taxonomy (109 routes, 7 index formulas, 4 vessel specs, 9 baskets) into `data/reference/baltic_route_taxonomy.json`.
  2. Resolved the self-contradiction on tsIds 7, 8, 9 (`1 Year TC - VLCC/Suezmax/Aframax [worldscale]`): Time charter contracts are never quoted in Worldscale; series values (55–430, 62.5–330, 10–575), date span, and row counts are identical to dirty spot routes 1–6. Relabelled all three as `Unverified Spot Route (mislabelled 1 Year TC - VLCC/Suezmax/Aframax) [worldscale]`.
  3. Carried exact Baltic route codes alongside vessel classes in continuous CSV headers:
     - `tsid 120655`: `Capesize TCE Cont/Far East (C9_182) [usd/day] (tsid_120655)`
     - `tsid 120654`: `Capesize Pacific RV (C10_182) [usd/day] (tsid_120654)`
     - `tsid 10010`: `Panamax Transatlantic RV (P1A_82) [usd/day] (tsid_10010)`
     - `tsid 10011`: `Panamax TCE Cont/Far East (P2A_82) [usd/day] (tsid_10011)`
     - `tsid 10012`: `Panamax TCE Far East RV (P3A_82) [usd/day] (tsid_10012)`
     - `tsid 10013`: `Panamax TCE Far East/Cont (P4_82) [usd/day] (tsid_10013)`
     - `tsid 10001`: `Capesize Tubarao/Qingdao (C3) [usd/tonne] (tsid_10001)`
     - `tsid 10002`: `Capesize Australia/China (C5) [usd/tonne] (tsid_10002)`
     - `tsid 120129`: `Supramax US Gulf - China/South Japan (S1C) [usd/day] (tsid_120129)`
     - `tsid 120132`: `Supramax Transatlantic RV Delivery Cont (S1B) [usd/day] (tsid_120132)`
     - `tsid 120133`: `Supramax Transatlantic RV Delivery USG (S4B) [usd/day] (tsid_120133)`
     - `tsid 120137`: `Supramax South China - Indonesia RV (S10) [usd/day] (tsid_120137)`
     - `tsid 1`: `MEG/Japan VLCC (TD3C) [worldscale] (tsid_1)`
     - `tsid 2`: `MEG/Singapore VLCC (TD2) [worldscale] (tsid_2)`
     - `tsid 3`: `WAF/China VLCC (TD15) [worldscale] (tsid_3)`
     - `tsid 4`: `WAF/UKC Suezmax (TD20) [worldscale] (tsid_4)`
     - `tsid 6`: `Cross Med Aframax (TD19) [worldscale] (tsid_6)`
  4. Added explicit canonical units to all series headers: `[worldscale]`, `[usd/day]`, `[usd/tonne]`, `[usd/bbl]`, `[fx]`, `[percent]`, `[index]`.
  5. Rebuilt `data/clarksons/fearnleys_benchmark_rates_continuous.csv` and `data/clarksons/fearnleys_benchmark_rates_continuous.json`.
  6. Updated `scripts/cargo/build_cargo_cache.py` to carry route codes `S1C` and `P1A_82` and rebuilt `data/cargo/cargo_frontend_summary.json`.
  7. Expanded `tests/test_fearnleys_labels_and_ranges.py` asserting unit brackets, class labels, Baltic route codes, TC worldscale contradiction resolution, median plausibility bands, and JSON catalog coherence.
  8. Registered `reference_baltic_route_taxonomy` in `data/provenance/manifest.json`.
- **VERIFY COMMAND:**
  ```bash
  pytest tests/test_fearnleys_labels_and_ranges.py -v
  ```
- **EXPECTED RESULT:** 5 passed
- **ACTUAL RESULT:** 5 passed in 0.81s
- **DEVIATIONS:** None.

