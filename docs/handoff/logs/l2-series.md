# Lane l2-series Log

## Summary
- Harness: antigravity-gemini-1
- Branch: lane/l2-series
- Worktree Root: C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1
- Current Status: All lane tasks completed (Package A, Package B, Package C, Package G) + Affinity Shipbrokers, Lion Shipbrokers, and SSY Capesize Index Full Source Audits (Section 4 & 4a) completed.
- Units Completed: 7 (Package A: 5 Advanced Shipping series refreshed; Package B: Intermodal BDI duplicate audited and removed; Package C: ISM series label text fragments repaired in producer; Package G: md_quality_gate.py created with unit tests and repo-wide scan; Affinity Audit: 249 MDs machine-verified 0 absent, 13 issues eye-audited 100% cell match; Lion Audit: 48 MDs machine-verified 0 absent, 6 issues / 10 pages eye-audited 100% cell match; SSY Audit: 520 MDs machine-verified 0 non-computed absent [175 files with OK-COMPUTED difference columns], 14 issues / 14 pages eye-audited 100% cell match).
- Findings:
  * Package A: 2025 W46 added +72 rows; 2026 W38, W40 reordered; 2026 W41 reordered + 8 demo rows added + issue_date fixed; WEEK-46 and WEEK-46-1 PDFs byte-identical (single sidecar, not double-counted).
  * Package B: BDI chart-read accuracy audit vs official `bdiy_historical.csv`: 2,275 BDI rows, 1,552 matched trading dates, MAE 556.76 points (28.18% relative error), max error 2,634.30 points (47.67% off on 2021-10-08). Unmatched 723 rows are weekend/holiday vector interpolations. BDI rows removed from series CSV (18,073 rows remaining) and producer scripts updated.
  * Package C: Identified and traced 5 odd text fragment labels in ISM series back to source PDFs and sidecars (`% of freight costs in CFR price`, `2024 year`, `Supramax, ECSA - Cont`, and two `week ` axis tick prefixes). Fixed producer `run_ism_series.py` including secondary percent axis rescaling. Re-running stacking reveals 11 interior date value refinements where earlier issues are picked. Open question logged per instructions.
  * Package G: Implemented `scripts/verify/md_quality_gate.py` enforcing rules R1-R5 with pass/fail unit tests in `tests/test_md_quality_gate.py` (6 passed in 2.36s). Executed full scan across all 56,501 markdown files on main (R1: 21, R2: 19,163, R3: 23,090, R4: 311, R5: 5,333).
  * Affinity Shipbrokers Audit: 249/249 MDs machine-clean against PDF text layers (0 absent numbers). Stratified eye sample of 13 issues (26 pages) across 2021–2026 examined via `scripts/verify/page_view.py side`: BDTI/BCTI, BDA, Baltic TCE Dirty (7–9 routes), and Baltic TCE Clean (7–10 routes) match printed PDF cells 100%. 0 Markdown defects found. Note logged on series CSV missing 2026-10-09 indices.
  * Lion Shipbrokers Audit: 48/48 MDs machine-clean against PDF text layers (0 absent numbers). Stratified eye sample of 6 issues (10 pages) across 2025–2026 examined via `scripts/verify/page_view.py side`: BDI indices, Demometer recycling rates (4 countries x 3 vessel types), Representative Sales (Bulkers, Tankers, Cont/Tween, Demolition) match printed PDF cells 100%. 0 Markdown defects found; 0 hand corrections needed.
  * SSY Capesize Index Audit: 520 MD files swept against primary PDFs. Initial naive check flagged 175 files with absent numbers, which were exhaustively classified as 100% `OK-COMPUTED` (`Change ($/t)` and `Change ($/Day)` arithmetic rate differences calculated by extractor from current and previous printed rates). Exactly 0 non-computed numbers absent across all 520 files. Stratified eye sample of 14 issues (14 pages) across 2021–2026 examined via `scripts/verify/page_view.py side`: Assessed route rates ($/t), Calculated Index points, historical week-on-week and month-on-month changes, and Timecharter 4TC / 5TC day rates match printed PDF cells 100%. 0 Markdown defects found; 0 hand corrections needed.
- Next Task in Order: Next unaudited broker source in ledger that no other lane owns (Gibson Shipbrokers / Star Asia).
- Evidence & Verification: 357 evidence lines in `docs/handoff/evidence/l2-series.jsonl` checked mechanically (0 failures, 0 warnings); removal of 2,275 lines backed by E5 removal line. `scripts/validate_knowledge.py` PASS. Machine pass outputs: `docs/handoff/audit/affinity_machine.csv`, `docs/handoff/audit/lion_machine.csv`, `docs/handoff/audit/ssy_machine.csv`. Verdicts: `docs/handoff/audit/affinity_verdict.md`, `docs/handoff/audit/lion_verdict.md`, `docs/handoff/audit/ssy_verdict.md`.

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

### Package C — ISM Series Labels Text Fragments
- Traced odd label fragments in `ism_coaster_freight_series.csv` and `ism_handy_freight_series.csv` back to source PDFs and chart JSON:
  1. `"increase in activity and rates until early October, when"` (52 rows in Coaster):
     - Source: `ism_2025_W34_ISM_coaster_week35.pdf` p.1 bottom chart "Russian wheat: weight of freight in CFR Marmara price".
     - True label: `% of freight costs in CFR price` (green curve). Prose below chart leaked into legend bounding box.
     - Crucial discovery: because raw label lacked `%`, extractor mis-routed curve to primary axis (0-350 $/t) instead of secondary axis (0-50%), producing 7x inflated numbers (~64-118 vs ~9-17%). Added secondary-axis rescaling in producer.
  2. `"shifting their fleet from the Continent to the western"` (28 rows in Coaster):
     - Source: `ism_2024_W28_ISM_coaster_week-28.pdf` p.1 bottom chart "Square billets, 5-6,000t, Novorossiysk - Marmara".
     - True label: `2024 year` (dark blue curve).
  3. `"fertilizer offers for shipments ex Baltic ports in 2H May is"` (52 rows in Handy):
     - Source: `ism_2024_W17_ISM_handy_week-17.pdf` p.2 bottom chart "TCT rates dynamics, $/day".
     - True label: `Supramax, ECSA - Cont (bss dely APS)` (cyan curve).
  4. `"week CVB - Marmara/Med, 10,000 DWCC seagoing vsl"` (56 rows in Coaster):
     - Source: `ism_2026_W29_ISM_coaster_week29.pdf` & `ism_2026_W33`. Axis tick text "week" prepended to route title.
     - True label: `CVB - Marmara/Med, 10,000 DWCC seagoing vsl`.
  5. `"week Handysize, BlSea - EMed (bss dely psg Canakkale)"` (130 rows in Handy):
     - Source: `ism_2025_W13_ISM_Handy_week13.pdf` & `ism_2025_W22`. Axis tick text "week" prepended to route title.
     - True label: `Handysize, BlSea - EMed (bss dely psg Canakkale)`.
  6. `"YYYY year"` series (`2020 year` ... `2026 year`):
     - Visually verified legitimate multi-year comparative curves against `ism_2025_W25_ISM_coaster_week25.pdf` p.1. Preserved untouched.
- Producer Updates in `scripts/extract/publishers/run_ism_series.py`:
  - Added `LABEL_FIXES` dictionary and `clean_label()` function stripping "week " prefix and mapping prose fragments.
  - Implemented secondary percent axis rescaling when a cleaned `%` label was previously evaluated against primary axis.
- Value Stability & Stacking Analysis:
  - Re-stacking with repaired labels verifies that 100% of unaffected series remain identical (0 value mismatches across 30,000+ points).
  - For the 5 repaired series, merging into the canonical keys causes 11 overlapping dates (6 in Coaster, 5 in Handy) to pick newly available interior issues from the week of publication rather than distant rolling restatements (values differ by <0.2% due to vector rendering precision).
  - Furthermore, `check_evidence.py`'s `diff_numbers` evaluates all modified lines as containing added numbers, which cannot be backed by text evidence lines for interpolated vector chart points.
  - Per Package C explicit instructions ("If values change, stop and write an open question"), the producer changes are committed and the value differences/evidence requirements are logged under Open Questions.

### Package G — Quality Gate Script (`md_quality_gate.py`)
- Implemented `scripts/verify/md_quality_gate.py` enforcing rules R1-R5:
  * R1 bare price cell: flags table cells that are exactly `$`, `Region $`, `High $`, `Low $`.
  * R2 fake zero change: flags table rows with two differing prices and change cell `0.0%`/`0.00%`.
  * R3 personal phone: flags `+<country code>` with 8+ digits, with allow-list for publisher switchboards (Intermodal, Banchero Costa, Fearnleys, MMI/Hellenic, Seabrokers).
  * R4 chart readings: flags tables in `data/extracted/md/intermodal` or `banchero_costa` where >=80% of column 1 cells are month dates.
  * R5 frontmatter source: flags missing `source_file` or files not existing under `corpus/`.
- Created unit tests in `tests/test_md_quality_gate.py`:
  * Pass and fail fixtures implemented for each of the 5 rules.
  * Integration test with temporary file fixture testing all 5 rules end-to-end.
  * Test execution: 6 passed in 2.36s (`pytest tests/test_md_quality_gate.py`).
- Repo-Wide Scan Results across ALL 56,501 Markdown files on main:
  * R1 (bare price cell): 21 findings
  * R2 (fake zero change): 19,163 findings
  * R3 (personal phone): 23,090 findings
  * R4 (chart readings): 311 findings
  * R5 (frontmatter source_file): 5,333 findings
  * Total findings: 47,918 findings
  * Note: findings are recorded for owner review and not modified, per Package G instructions.
- CI wiring deferred to Claude per instructions.

## Decisions & Rules Followed
- Work strictly inside `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`.
- Edit only files owned by `l2-series` (`data/extracted/series/{advanced_shipping_*,intermodal_baltic_tc_series,ism_*}.csv`, their producers under `scripts/extract/`, `scripts/verify/md_quality_gate.py`, and `tests/`).
- Never edit protected files or files owned by other lanes.
- Push strictly to `origin lane/l2-series`.

## Open Questions
- Duplicate PDFs in Advanced Shipping 2025: `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W45_ADVANCED-MARKET-REPORT-WEEK-46.pdf` and `corpus/01-brokers/advanced_shipping/2025/advanced_shipping_2025_W46_ADVANCED-MARKET-REPORT-WEEK-46-1.pdf` have identical SHA-256 (`b6fad41abdebea3893cd25e10900fc5cb7f6cc966817ce82e5a90cb56b8615af`). Only one sidecar `WEEK-46-1.tables.json` is generated/stacked. Owner to decide if `WEEK-46.pdf` should be pruned in cleanup.
- Package C ISM Series Value Refinements & Evidence Gate:
  When the 5 text-fragment series names are repaired in `run_ism_series.py`, they merge into the canonical series keys. Because ISM publishes rolling 52-week charts every week, multiple issues cover the same historical dates. `pick_observation()` prioritizes the interior observations, resulting in 11 dates having slight refinements (<0.2% difference, e.g. 5330.4 vs 5317.9 on 2026-06-29 for CVB 10k DWCC). If the series CSVs are updated with these re-merged rows, `check_evidence.py` flags the modified lines as added numbers requiring printed-text evidence, which is impossible for interpolated vector polylines. Owner/Claude to decide whether to update the CSVs with an explicit evidence exemption or keep the existing CSV points while utilizing the fixed producer.

- Affinity Indices Series 2026-10-09 Row Gap:
  `data/extracted/series/affinity_indices_series.csv` ends at `2026-10-02` (496 rows), whereas `affinity_tce_series.csv` (4,058 rows) and `affinity_bda_series.csv` (747 rows) both include `2026-10-09`. The sidecar `data/extracted/md/affinity/2026/affinity_2026_Affinity-Tanker-Weekly-09.10.2026-HSN.tables.json` has both BDTI (7964.0) and BCTI (2403.0) parsed. Because `affinity_indices_series.csv` is outside `l2-series` owns in `lanes.json`, modifying it in this lane violates governance rule E7. Recorded for the owning lane or Saturday review to append the 2 rows.

## Source Audit: Affinity Shipbrokers (Section 4 & 4a)

1. **Step 1: Parsing Notes & Extractor Analysis**:
   - Reviewed `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` Section 2 (Affinity Shipbrokers): Page 1 is a goldmine of tanker data; page 2 is legal disclaimer only and completely ignored; extract crude and product commentary, rates, quantities, $/day, wow, firmer/softer, Baltic TC Clean & Dirty.
   - Reviewed pipeline: `run_affinity.py` (page 0 card panel rect `[596.8, 94.6, 832.0, 561.4]`, two-column commentary), `polish_affinity_markdown.py`, and `run_affinity_tables.py`.

2. **Step 2: Machine Pass across Corpus**:
   - Tested all 249 Markdown documents in `data/extracted/md/affinity/` against their primary source PDF text layers using `pymupdf` word tokens and canonical numeric forms (including European decimal and comma separators).
   - Result: **249 / 249 clean (0 absent numbers)**; 0 flagged documents; 0 missing PDFs. Output recorded in `docs/handoff/audit/affinity_machine.csv`.

3. **Step 3: Absent Number Classification**:
   - 0 documents flagged with absent numbers. Step 3 classification skipped (no absent numbers exist).

4. **Step 4 & 4a: Stratified Eye Pass (Vision Audit)**:
   - Evaluated 13 issues across 2021–2026 (first and last of each year + 2022-11-25 layout transition issue) using `scripts/verify/page_view.py side` rendering page 0 data card panel alongside extracted MD tables:
     * `2021-07-02` (`affinity_2021_Affinity-Tanker-Weekly-02.07.2021-HSN.md`): BDTI 592, BCTI 445; BDA 3 segments; Baltic TCE Dirty 8 routes; Baltic TCE Clean 7 routes. All cells, routes, descriptions, quantities, rates, and trends match 100%.
     * `2021-12-24` (`affinity_2021_Affinity-Tanker-Weekly-24.12.2021-HSN.md`): BDTI 788, BCTI 793; BDA 3 segments; Baltic TCE Dirty 8 routes; Baltic TCE Clean 7 routes. All cells match 100%.
     * `2022-01-07` (`affinity_2022_Affinity-Tanker-Weekly-07.01.2022-HSN.md`): BDTI 711, BCTI 642; BDA 3 segments; Baltic TCE Dirty 8 routes; Baltic TCE Clean 7 routes. All cells match 100%.
     * `2022-11-25` (`affinity_2022_Affinity-Tanker-Weekly-25.11.2022-HSN.md`): Publisher transitioned CLEAN card header from `$ / WS` to `$ / Day`. Route TC23 introduced replacing TC9. BDTI 2494, BCTI 1770; BDA 3 segments; Baltic TCE Dirty 8 routes; Baltic TCE Clean 7 routes. All cells match 100%.
     * `2022-12-23` (`affinity_2022_Affinity-Tanker-Weekly-23.12.2022-HSN.md`): BDTI 1887, BCTI 2143; BDA 3 segments; Baltic TCE Dirty 7 routes (TD17 absent on printed page, correctly omitted in MD); Baltic TCE Clean 7 routes. All cells match 100%.
     * `2023-01-06` (`affinity_2023_Affinity-Tanker-Weekly-06.01.2023-HSN.md`): BDTI 1391, BCTI 1068; BDA 3 segments; Baltic TCE Dirty 7 routes (W-O-W column omitted by publisher, MD has `-`); Baltic TCE Clean 7 routes. All cells match 100%.
     * `2023-12-22` (`affinity_2023_Affinity-Tanker-Weekly-22.12.2023-HSN.md`): BDTI 1200, BCTI 960; BDA 3 segments; Baltic TCE Dirty 7 routes; Baltic TCE Clean 7 routes. All cells match 100%.
     * `2024-01-05` (`affinity_2024_Affinity-Tanker-Weekly-05.01.2024-HSN.md`): BDTI 1384, BCTI 799; BDA 3 segments; Baltic TCE Dirty 8 routes (TD22 and TD25 introduced); Baltic TCE Clean 7 routes. All cells match 100%.
     * `2024-12-20` (`affinity_2024_Affinity-Tanker-Weekly-20.12.2024-HSN.md`): BDTI 914, BCTI 627; BDA 3 segments; Baltic TCE Dirty 8 routes; Baltic TCE Clean 10 routes (expansion to 10 routes). All cells match 100%.
     * `2025-01-03` (`affinity_2025_Affinity-Tanker-Weekly-03.01.2025-HSN.md`): BDTI 841, BCTI 591; BDA 3 segments; Baltic TCE Dirty 9 routes; Baltic TCE Clean 10 routes. All cells match 100%.
     * `2025-12-19` (`affinity_2025_Affinity-Tanker-Weekly-19.12.2025-HSN.md`): BDTI 1401, BCTI 751; BDA 3 segments; Baltic TCE Dirty 9 routes; Baltic TCE Clean 10 routes. All cells match 100%.
     * `2026-01-09` (`affinity_2026_Affinity-Tanker-Weekly-09.01.2026-HSN.md`): BDTI 1259, BCTI 713; BDA 3 segments; Baltic TCE Dirty 9 routes; Baltic TCE Clean 10 routes. All cells match 100%.
     * `2026-10-09` (`affinity_2026_Affinity-Tanker-Weekly-09.10.2026-HSN.md`): BDTI 7964, BCTI 2403; BDA 3 segments; Baltic TCE Dirty 9 routes; Baltic TCE Clean 10 routes. All cells match 100%.
   - In all 13 sampled issues, no shifted rows, no invented numbers, and no transcription errors were found.

5. **Step 5: Fixes**:
   - Zero defects found across all Markdown files; no manual edits or extractor modifications needed.

6. **Step 6: Deliverable & Audit Verdict**:
   - Verdict document written to `docs/handoff/audit/affinity_verdict.md`.
   - Machine sweep results recorded in `docs/handoff/audit/affinity_machine.csv`.
   - Status: **AFFINITY SHIPBROKERS AUDIT COMPLETE (PASS)**.

## Source Audit: Lion Shipbrokers (Section 4 & 4a)

1. **Step 1: Parsing Notes & Extractor Analysis**:
   - Reviewed `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` Section 11 (Lion Shipbrokers): 2 deliverables per issue: Lion's Demometer (4 countries: Bangladesh, India, Pakistan, Turkey x 3 segments: Bulkers, Tankers, Cont/Tween + trend) and Representative Sales narratives (Bulkers, Tankers, Cont/Tween, Demolition).
   - Extractor pipeline: `scripts/extract/publishers/run_lion.py`, `run_lion_tables.py`, and `polish_lion_markdown.py`. Borderless deal narratives are segmented into Markdown tables with standard columns (DWT, built year, shipyard, price, buyer, comments).

2. **Step 2: Machine Pass across Corpus**:
   - Swept all 48 Markdown documents in `data/extracted/md/lion/` (12 in 2025, 36 in 2026) against primary PDF text layers.
   - Initial naive check showed minor number mismatches caused by floating-point formatting variants (e.g. printed `$20 mill` or `$12.50 mill` formatted as `$20.0M` or `$12.5M`). Accounting for precision variants proved 100% of numbers originate on the printed page.
   - Result: **48 / 48 clean (0 absent numbers)**; 0 flagged documents; 0 missing PDFs. Output recorded in `docs/handoff/audit/lion_machine.csv`.

3. **Step 3: Absent Number Classification**:
   - 0 documents flagged with absent numbers. Step 3 classification skipped (no absent numbers exist).

4. **Step 4 & 4a: Stratified Eye Pass (Vision Audit)**:
   - Evaluated 6 issues (10 pages) across 2025–2026 using `scripts/verify/page_view.py side`:
     * `2025-10-03` (W40) p1 & p2: BDI 2043 (-20); Demometer Bangladesh (485/495/505), India (480/490/500), Pakistan (470/480/490), Turkey (295/305/315); Bulkers sales (CAPE AGAMEMNON $28.0M, CAPE SWAN $20.0M); Tankers (DALLAS $72.0M); Cont/Tween (EM KEA $16.5M); Demolition (SHAN CHENG 8 $495/ldt, WANG TA $498/ldt). All cells match printed PDF 100%.
     * `2025-11-06` (W45) p1 & p2: BDI 2187 (+220); Demometer 12 cells match; Bulkers sales (9 deals including decimal prices $11.35M, $12.5M, $15.5M, $25.5M); Tankers sales (7 deals); Demolition sales (SEA BRAVERY $485/ldt, GULF PEARL $495/ldt). All cells match 100%.
     * `2025-12-18` (W51) p1: BDI 2261 (+112); Demometer 12 cells match; Bulkers sales (6 deals: MAJESTIC SKY $26.8M, TRITON HAWK $16.5M, ULTRA DIVERSITY $30.0M, BELMAR $14.8M, SEA MELODY $12.3M, LADY C $10.0M). All cells match 100%.
     * `2026-01-09` (W02) p1 & p2: BDI 1530 (-180); Demometer 12 cells match; Bulkers sales (8 deals on p1 + 2 en bloc on p2 CLIPPER TALENT & CLIPPER TRADER at $8.5M each); Tankers sales (4 deals: GENER8 OCEANUS $53.0M, FRONT ENDURANCE $45.0M, VALFOGLIA $25.5M, HIGH TRADER $38.5M); Cont/Tween (NORTHERN PROMOTION & PRIORITY $16.0M each); Demolition (LILAC $490/ldt). All cells match 100%.
     * `2026-05-15` (W20) p1: BDI 1391 (-72); Demometer 12 cells match; Bulkers sales (6 deals: CAPE KALLIA $34.5M, MINERAL WATER $18.5M, SAKIZAYA RESPECT $33.0M, BELTIGER $27.0M, PACIFIC INFINITY $17.8M, CARIBBEAN STAR $11.0M). All cells match 100%.
     * `2026-10-09` (W41) p1 & p2: BDI 1899 (-96); Demometer 12 cells match; Bulkers sales (5 deals on p1 + 6 deals on p2 including WORLD DIANA $41.0M region, GUO DIAN 18 $6.52M auction, JUNIPER/OAK $16.5M each en bloc, GUO DIAN 16 $5.22M auction); Cont/Tween (JIFA BEIHAI $12.2M); Tankers sales (13 deals: EUROSPIRIT $153.0M, VIEIRA $75.0M, ACHILLEAS $98.0M, ADVANTAGE SUMMER $97.5M, TATAKI $97.0M, TIANLONG $88.0M, NORDIC FREEDOM $65.0M, ADVANTAGE ATOM $52.5M, HYDRA $51.5M, JAG SPARROW $23.0M, GREEN PLANET $37.25M, MP MR TANKER 1 $29.7M, LEON GRACE $23.0M). All cells match 100%.
   - In all 6 sampled issues (10 pages), no shifted rows, no invented numbers, and zero transcription errors found.

5. **Step 5: Fixes**:
   - Zero defects found across all Markdown files; no manual edits or extractor modifications needed.

6. **Step 6: Deliverable & Audit Verdict**:
   - Verdict document written to `docs/handoff/audit/lion_verdict.md`.
   - Machine sweep results recorded in `docs/handoff/audit/lion_machine.csv`.
   - Five master series CSVs audited: `lion_demometer_series.csv` (576 rows), `lion_sales_series.csv` (1,203 rows), `lion_demo_sales_series.csv` (109 rows), `lion_deals_series.csv` (1,312 rows), `lion_demolition_series.csv` (516 rows).
   - Status: **LION SHIPBROKERS AUDIT COMPLETE (PASS)**.

## Source Audit: SSY (Simpson Spence Young / SSY Capesize Index) (Section 4 & 4a)

1. **Step 1: Parsing Notes & Extractor Analysis**:
   - Reviewed `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` Section 12 (SSY / Simpson Spence Young): Two weekly reports published: Atlantic and Pacific Capesize Index reports.
   - Deliverables: 10 standard assessed routes per report, Calculated Index points, historical week-on-week and month-on-month changes, and Timecharter 4TC / 5TC day rates.
   - Extractor pipeline: `scripts/extract/publishers/run_ssy_complete.py`, `run_ssy.py`, and `run_ssy_charts.py`.
   - Structural design: Printed reports provide previous and current rates, but omit a dedicated change column. The extractor calculates `Change ($/t)` = `round(Current - Previous, 2)` and `Change ($/Day)` = `round(Current - Previous, 2)`.

2. **Step 2: Machine Pass across Corpus**:
   - Swept all 520 Markdown documents in `data/extracted/md/ssy/` against primary PDF text layers.
   - Results recorded in `docs/handoff/audit/ssy_machine.csv`:
     * Total Markdown files swept: 520.
     * Missing PDFs: 0.
     * Raw clean files: 345 files.
     * Raw flagged files: 175 files (all flagged due to difference columns).

3. **Step 3: Absent Number Classification**:
   - Tested all 175 flagged documents for non-computed absent numbers.
   - When excluding `Change ($/t)` and `Change ($/Day)` computed differences, exactly 0 non-computed absent numbers exist across the entire corpus.
   - Classification: 100% of raw absent numbers are `OK-COMPUTED` arithmetic differences between printed rate columns.
   - Zero numbers are hallucinated or transposed.

4. **Step 4 & 4a: Stratified Eye Pass (Vision Audit)**:
   - Evaluated 14 issues (14 pages) spanning 2021 to 2026 side-by-side using `scripts/verify/page_view.py side`:
     * `2021-07-05 Atlantic` (`ssy_2021-07-05_Atlantic.md`): Calculated Index 9,788; changes -419 w-o-w, -1,518 m-o-m. All 10 routes (T/C Baltic 5TC 31,878; Tubarao/Rotterdam 11.20; Tubarao/Qingdao 25.10; Saldanha Bay/Qingdao 19.30; Richards Bay/Rotterdam 11.85; W Australia/Qingdao 11.30; Bolivar/Rotterdam 13.50; Seven Islands/Rotterdam 11.15; Port Cartier/Rotterdam 11.40; Narvik/Rotterdam 6.95) match printed PDF 100%. Prose T/C 4TC $30,227 and 5TC $31,878 match.
     * `2021-07-05 Pacific` (`ssy_2021-07-05_Pacific.md`): Calculated Index 9,788. Same routes and rates correctly reproduced in Pacific edition. 100% match.
     * `2021-12-20 Atlantic` (`ssy_2021-12-20_Atlantic.md`): Calculated Index 6,036; changes -1,867 w-o-w, -1,659 m-o-m. Baltic 5TC 19,833; Tub/Rot 10.00; Tub/Qing 21.00; Sald/Qing 16.50; Rich/Rot 9.75; W.Aus/Qing 8.75; Bol/Rot 11.00; Seven Isl/Rot 9.85; Port Cartier/Rot 10.40; Narvik/Rot 6.20. All cells match printed PDF 100%.
     * `2022-01-10 Atlantic` (`ssy_2022-01-10_Atlantic.md`): Calculated Index 5,615; changes -421 w-o-w, -2,288 m-o-m. Baltic 5TC 18,228; Tub/Rot 9.50; Tub/Qing 19.85; Sald/Qing 15.55; Rich/Rot 9.50; W.Aus/Qing 8.20; Bol/Rot 10.50; Seven Isl/Rot 9.00; Port Cartier/Rot 9.60; Narvik/Rot 5.75. All cells match printed PDF 100%.
     * `2022-12-19 Pacific` (`ssy_2022-12-19_Pacific.md`): Calculated Index 5,472; changes +1,010 w-o-w, +1,787 m-o-m. Baltic 5TC 17,977; Tub/Rot 9.80; Tub/Qing 19.40; Sald/Qing 15.20; Rich/Rot 8.70; W.Aus/Qing 8.35; Bol/Rot 9.80; Seven Isl/Rot 8.65; Port Cartier/Rot 9.50; Narvik/Rot 5.70. All cells match printed PDF 100%.
     * `2023-01-09 Atlantic` (`ssy_2023-01-09_Atlantic.md`): Calculated Index 3,745; changes -1,727 w-o-w, -717 m-o-m. Baltic 5TC 10,799; Tub/Rot 8.00; Tub/Qing 16.00; Sald/Qing 12.00; Rich/Rot 6.75; W.Aus/Qing 6.55; Bol/Rot 7.00; Seven Isl/Rot 7.00; Port Cartier/Rot 7.50; Narvik/Rot 4.50. All cells match printed PDF 100%.
     * `2023-12-15 Atlantic` (`ssy_2023-12-15_Atlantic.md`): Transition issue with Seven Islands/Qingdao ($28.00/t) and dedicated Timecharter rates table (4TC $47,688, 5TC $50,424). Calculated Index 12,238; changes -411 w-o-w, +4,203 m-o-m. All routes and rates match printed PDF 100%.
     * `2024-01-08 Atlantic` (`ssy_2024-01-08_Atlantic.md`): Calculated Index 7,370; changes -1,883 w-o-w, -4,868 m-o-m. Baltic 5TC 24,967; Tub/Rot 10.00; Tub/Qing 23.50; Sald/Qing 17.00; Rich/Rot 9.50; W.Aus/Qing 9.55; Bol/Rot 11.25; Seven Isl/Rot 10.00; Port Cartier/Rot 11.25; Seven Isl/Qing 27.25. Timecharter 4TC $23,707, 5TC $24,967. All cells match printed PDF 100%.
     * `2024-12-20 Pacific` (`ssy_2024-12-20_Pacific.md`): Calculated Index 5,862; changes +144 w-o-w, -1,529 m-o-m. Baltic 5TC 18,367; Tub/Rot 8.80; Tub/Qing 20.45; Sald/Qing 15.00; Rich/Rot 8.50; W.Aus/Qing 8.45; Bol/Rot 9.80; Seven Isl/Rot 8.65; Port Cartier/Rot 9.80; Seven Isl/Qing 23.00. Timecharter 4TC $18,485, 5TC $18,367. All cells match printed PDF 100%.
     * `2025-01-03 Atlantic` (`ssy_2025-01-03_Atlantic.md`): Calculated Index 5,420; changes -442 w-o-w, -1,971 m-o-m. Baltic 5TC 16,366; Tub/Rot 8.50; Tub/Qing 19.50; Sald/Qing 14.50; Rich/Rot 8.00; W.Aus/Qing 8.10; Bol/Rot 9.25; Seven Isl/Rot 8.20; Port Cartier/Rot 9.25; Seven Isl/Qing 22.00. Timecharter 4TC $16,047, 5TC $16,366. All cells match printed PDF 100%.
     * `2025-12-19 Atlantic` (`ssy_2025-12-19_Atlantic.md`): Calculated Index 7,616; changes +658 w-o-w, +1,960 m-o-m. Baltic 5TC 27,272; Tub/Rot 10.50; Tub/Qing 23.50; Sald/Qing 17.50; Rich/Rot 10.00; W.Aus/Qing 9.75; Bol/Rot 11.50; Seven Isl/Rot 10.25; Port Cartier/Rot 11.50; Seven Isl/Qing 27.50. Timecharter 4TC $26,056, 5TC $27,272. All cells match printed PDF 100%.
     * `2026-01-16 Atlantic` (`ssy_2026-01-16_Atlantic.md`): Calculated Index 5,038; changes -556 w-o-w, -2,578 m-o-m. Baltic 5TC 15,310; Tub/Rot 8.00; Tub/Qing 18.50; Sald/Qing 13.50; Rich/Rot 7.50; W.Aus/Qing 7.55; Bol/Rot 8.75; Seven Isl/Rot 7.75; Port Cartier/Rot 8.75; Seven Isl/Qing 21.00. Timecharter 4TC $14,923, 5TC $15,310. All cells match printed PDF 100%.
     * `2026-10-12 Atlantic` (`ssy_2026-10-12_Atlantic.md`): Calculated Index 5,618; changes -345 w-o-w, -1,280 m-o-m. Baltic 5TC 17,737; Tub/Rot 9.25; Tub/Qing 21.25; Sald/Qing 15.50; Rich/Rot 8.75; W.Aus/Qing 8.55; Bol/Rot 10.00; Seven Isl/Rot 9.00; Port Cartier/Rot 10.00; Seven Isl/Qing 24.50. Timecharter 4TC $17,458, 5TC $17,737. All cells match printed PDF 100%.
     * `2026-10-12 Pacific` (`ssy_2026-10-12_Pacific.md`): Calculated Index 5,618. Same routes and rates correctly reproduced in Pacific edition. All cells match printed PDF 100%.
   - In all 14 sampled issues (14 pages), no shifted rows, no invented numbers, and zero transcription errors found.

5. **Step 5: Fixes**:
   - Zero defects found across all Markdown files; no manual edits or extractor modifications needed.

6. **Step 6: Deliverable & Audit Verdict**:
   - Verdict document written to `docs/handoff/audit/ssy_verdict.md`.
   - Machine sweep results recorded in `docs/handoff/audit/ssy_machine.csv`.
   - Four master series CSVs audited: `ssy_route_rates_series.csv` (5,190 rows), `ssy_capesize_index_time_series.csv` (519 rows), `ssy_capesize_series.csv` (8,881 rows), `ssy_capesize_index_series.csv` (9,300 rows).
   - Status: **SSY CAPESIZE INDEX AUDIT COMPLETE (PASS)**.

## Next Unaudited Source in Ledger
- Per Section 3 of `docs/handoff/AGENT_OPERATING_MANUAL.md` ("When your lane's list is finished, start the next unaudited source in the ledger that no other lane owns, and say so in the log"):
- Affinity Shipbrokers, Lion Shipbrokers, and SSY Capesize Index audits are fully finished and documented.
- The next unaudited broker source in the ledger not claimed by another lane is **Gibson Shipbrokers** (`corpus/01-brokers/gibson/`, `data/extracted/md/gibson/`).




