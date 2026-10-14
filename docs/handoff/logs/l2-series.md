# Lane l2-series Log

## Summary
- Harness: antigravity-gemini-1
- Branch: lane/l2-series
- Worktree Root: C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1
- Current Status: Package A completed; progressing to Package B (Intermodal BDI duplicate removal)
- Units Completed: 1 (Package A: 5 series CSVs refreshed, 252 sidecars stacked)
- Findings: 2025 W46 added +72 rows; 2026 W38, W40 reordered; 2026 W41 reordered + 8 demo rows added + issue_date fixed; WEEK-46 and WEEK-46-1 PDFs byte-identical (single sidecar, not double-counted).
- Next Task in Order: Package B (Intermodal BDI duplicate audit and removal)
- Evidence & Verification: 356 evidence lines in `docs/handoff/evidence/l2-series.jsonl` checked mechanically (0 failures, 0 warnings); 15 random rows verified against PDF text layers.

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
- Evidence generated:
  - Created `docs/handoff/evidence/l2-series.jsonl` with 356 evidence lines covering all numeric changes in the 5 CSVs.
  - Verified with `check_evidence.py` against base `origin/main` (0 failures, 0 warnings).

## Decisions & Rules Followed
- Work strictly inside `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`.
- Edit only files owned by `l2-series` (`data/extracted/series/{advanced_shipping_*,intermodal_baltic_tc_series,ism_*}.csv`, their producers under `scripts/extract/`, `scripts/verify/md_quality_gate.py`, and `tests/`).
- Never edit protected files or files owned by other lanes.
- Push strictly to `origin lane/l2-series`.

## Open Questions
- Duplicate PDFs in Advanced Shipping 2025: `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W45_ADVANCED-MARKET-REPORT-WEEK-46.pdf` and `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W46_ADVANCED-MARKET-REPORT-WEEK-46-1.pdf` have identical SHA-256 (`b6fad41abdebea3893cd25e10900fc5cb7f6cc966817ce82e5a90cb56b8615af`). Only one sidecar `WEEK-46-1.tables.json` is generated/stacked. Owner to decide if `WEEK-46.pdf` should be pruned in cleanup.
