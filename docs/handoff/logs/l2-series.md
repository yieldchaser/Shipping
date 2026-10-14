# Lane l2-series Log

## Summary
- Harness: antigravity-gemini-1
- Branch: lane/l2-series
- Worktree Root: C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1
- Current Status: Package A & Package B completed; progressing to Package C (ISM series labels)
- Units Completed: 2 (Package A: 5 Advanced Shipping series refreshed; Package B: Intermodal BDI duplicate audited and removed)
- Findings:
  * Package A: 2025 W46 added +72 rows; 2026 W38, W40 reordered; 2026 W41 reordered + 8 demo rows added + issue_date fixed; WEEK-46 and WEEK-46-1 PDFs byte-identical (single sidecar, not double-counted).
  * Package B: BDI chart-read accuracy audit vs official `bdiy_historical.csv`: 2,275 BDI rows, 1,552 matched trading dates, MAE 556.76 points (28.18% relative error), max error 2,634.30 points (47.67% off on 2021-10-08). Unmatched 723 rows are weekend/holiday vector interpolations. BDI rows removed from series CSV (18,073 rows remaining) and producer scripts updated.
- Next Task in Order: Package C (ISM series names text fragment fixes)
- Evidence & Verification: 357 evidence lines in `docs/handoff/evidence/l2-series.jsonl` checked mechanically (0 failures, 0 warnings); removal of 2,275 lines backed by E5 removal line.

## Environment & Location
- `git rev-parse --show-toplevel`: `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`
- `git branch --show-current`: `lane/l2-series`

## Log Entries
- Initialized worktree at `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1` on branch `lane/l2-series` from `origin/main`.
- Claimed `l2-series` by writing `docs/handoff/claims/l2-series.json` and pushed to `origin lane/l2-series` (commit `c538a7cf41`).
- Commencing work in order: Package A -> Package B -> Package C -> Package G.

### Package A — Advanced Shipping Series Drift
- Rebuilt all 5 series CSVs using `python scripts/extract/publishers/run_advanced_shipping_tables.py --stack-only` (processed 252 sidecars from disk without re-parsing PDFs).
- Analyzed diffs vs `origin/main`:
  - Exactly 4 issues affected: `2025 W46`, `2026 W38`, `2026 W40`, `2026 W41`. Zero other issues altered.
  - Rows added / changed per issue:
    * `2025 W46` (`advanced_shipping_2025_W46_ADVANCED-MARKET-REPORT-WEEK-46-1.pdf`): +72 rows added (+17 sales, +8 demo prices, +13 newbuilding, +32 secondhand matrix, +2 demo sales).
    * `2026 W38` (`advanced_shipping_2026_W38_ADVANCED-MARKET-REPORT-WEEK-38.pdf`): 76 rows reordered into chronological position (27 sales, 8 demo prices, 8 newbuilding, 32 secondhand matrix, 1 demo sales).
    * `2026 W40` (`advanced_shipping_2026_W40_ADVANCED-MARKET-REPORT-WEEK-40.pdf`): 83 rows reordered into chronological position (36 sales, 8 demo prices, 7 newbuilding, 32 secondhand matrix).
    * `2026 W41` (`advanced_shipping_2026_W41_ADVANCED-MARKET-REPORT-WEEK-41.pdf`): 17 sales rows reordered and empty `issue_date` populated to `2026-10-09`; +8 demolition rows added; 16 newbuilding and 32 secondhand matrix rows reordered into chronological order.
- Double-count verification (Task 2):
  - Verified SHA-256 for `advanced_shipping_2025_W45_ADVANCED-MARKET-REPORT-WEEK-46.pdf` and `advanced_shipping_2025_W46_ADVANCED-MARKET-REPORT-WEEK-46-1.pdf`.
  - Both hashes are identical (`b6fad41abdebea3893cd25e10900fc5cb7f6cc966817ce82e5a90cb56b8615af`).
  - Only one sidecar exists (`WEEK-46-1.tables.json`). Therefore, 2025 W46 is NOT double-counted in the stacked series.
- 15-Row Random Verification against Primary PDFs (Task 3):
  1. `sales` 2025 W46 p.3: Seacon Africa Newcastlemax 206,291 dwt Imabari 2006, $ 22,7m (matches p.3 table & p.1 text "Seacon Shipping Group have committed the Newcastlemax 'Seacon Africa' at USD 22,7 mill").
  2. `sales` 2025 W46 p.3: Grace Harmony Ultramax 60,259 dwt Onomichi 2015, High $ 24m (matches p.3 table).
  3. `sales` 2025 W46 p.3: STI Battery MR 49,990 dwt Hyundai Mipo 2014, $ 32m (matches p.3 table).
  4. `demolition` 2025 W46 p.5: Bulkers Bangladesh 395 $/ldt (matches p.5 table).
  5. `demolition` 2025 W46 p.5: Tankers Turkey 270 $/ldt (matches p.5 table).
  6. `newbuilding` 2025 W46 p.4: Hanwha Ocean 320,000 dwt VLCC, $ 127m (matches p.4 table).
  7. `newbuilding` 2025 W46 p.4: Navibulgar Yangzijiang 71,000 dwt bulkers (matches p.4 table).
  8. `secondhand_matrix` 2025 W46 p.6: Capesize 180k Resale 77,5 mill (matches p.6 table).
  9. `demo_sales` 2025 W46 p.5: Zenith Tanker 105,161 dwt 17,013 ldt 359 $/ldt India (matches p.5 table).
  10. `sales` 2026 W38 p.3: Bora Kamsarmax 81,682 dwt Sainty 2014, $ 22,5m (matches p.3 table & p.1 text "committed to undisclosed interests at USD 22,5 mill").
  11. `demolition` 2026 W38 p.6: Bulkers India 440 $/ldt (matches p.6 table).
  12. `secondhand_matrix` 2026 W38 p.7: Capesize 180k Resale 84,5 mill (matches p.7 table).
  13. `demo_sales` 2026 W38 p.6: Uniorder Bulker 47,240 dwt 7,060 ldt 450 $/ldt (matches p.6 table).
  14. `sales` 2026 W40 p.3: LC Milady Post Panamax 93,758 dwt Shanhaiguan 2011, Mid $ 14m (matches p.3 table).
  15. `demolition` 2026 W41 p.5: Bulkers Pakistan 485 $/ldt (matches p.5 table).
  All 15 rows verified exact match (15/15 OK).
- Committed and pushed to `origin lane/l2-series` (commit `aa9f28d054`).

### Package B — Intermodal BDI Duplicate Audit & Removal
- Accuracy Audit of Chart-Read BDI vs Official `data/indices/bdiy_historical.csv`:
  * Total BDI rows in Intermodal series: 2,275
  * Matched rows on calendar dates with historical BDI: 1,552
  * Unmatched dates: 723 (328 Saturdays, 271 Sundays, and market holidays where Baltic index is closed but chart polylines interpolate across non-trading days)
  * Mean Absolute Error (MAE): 556.7575 points
  * Median Absolute Error: 468.3500 points
  * Max Absolute Error: 2,634.3000 points
  * Mean Relative Error (%): 28.1766%
  * Top 10 worst dates by absolute error:
    1. 2021-10-08: Chart= 2,891.70, Official= 5,526.00, Error= 2,634.30 (47.67%)
    2. 2021-10-07: Chart= 3,018.80, Official= 5,650.00, Error= 2,631.20 (46.57%)
    3. 2021-10-06: Chart= 3,060.90, Official= 5,647.00, Error= 2,586.10 (45.80%)
    4. 2021-10-04: Chart= 2,824.60, Official= 5,267.00, Error= 2,442.40 (46.37%)
    5. 2021-10-01: Chart= 2,849.40, Official= 5,202.00, Error= 2,352.60 (45.22%)
    6. 2021-10-11: Chart= 3,174.90, Official= 5,488.00, Error= 2,313.10 (42.15%)
    7. 2021-10-05: Chart= 3,103.40, Official= 5,409.00, Error= 2,305.60 (42.63%)
    8. 2021-09-29: Chart= 2,891.70, Official= 5,197.00, Error= 2,305.30 (44.36%)
    9. 2021-09-30: Chart= 2,891.70, Official= 5,167.00, Error= 2,275.30 (44.04%)
    10. 2023-12-04: Chart= 1,141.90, Official= 3,346.00, Error= 2,204.10 (65.87%)
- Producer Modifications:
  * Modified `scripts/extract/publishers/merge_intermodal_charts.py`:
    - Added `EXCLUDED_SERIES = {"BDI"}` with explanatory comment referencing the owner rule.
    - Updated `readings_from_files()`, `merge_new_only()`, and `main()` to filter `EXCLUDED_SERIES`.
  * Modified `scripts/extract/orchestrate_incremental_ingest.py`:
    - Updated `SIGNATURE_CATALOG` entry `baltic_tc_curves` title to reflect BDI exclusion per owner rule.
- Series CSV Cleanup:
  * Removed all 2,275 BDI rows from `data/extracted/series/intermodal_baltic_tc_series.csv`.
  * Exactly 18,073 rows remain across the 8 non-duplicate series (`AVR 10TC BSI`, `AVR 5TC BPI`, `AVR 7TC BHSI`, `Average of the 5 T / C`, `BCI`, `BHSI`, `BPI`, `BSI`). Zero other rows altered.
  * Added removal entry in `docs/handoff/evidence/l2-series.jsonl` (2,275 lines, reason recorded).
  * Validated with `check_evidence.py` (0 failures, 0 warnings).

## Decisions & Rules Followed
- Work strictly inside `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`.
- Edit only files owned by `l2-series` (`data/extracted/series/{advanced_shipping_*,intermodal_baltic_tc_series,ism_*}.csv`, their producers under `scripts/extract/`, `scripts/verify/md_quality_gate.py`, and `tests/`).
- Never edit protected files or files owned by other lanes.
- Push strictly to `origin lane/l2-series`.

## Open Questions
- Duplicate PDFs in Advanced Shipping 2025: `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W45_ADVANCED-MARKET-REPORT-WEEK-46.pdf` and `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W46_ADVANCED-MARKET-REPORT-WEEK-46-1.pdf` have identical SHA-256 (`b6fad41abdebea3893cd25e10900fc5cb7f6cc966817ce82e5a90cb56b8615af`). Only one sidecar `WEEK-46-1.tables.json` is generated/stacked. Owner to decide if `WEEK-46.pdf` should be pruned in cleanup.
