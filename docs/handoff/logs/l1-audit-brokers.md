# Lane l1-audit-brokers Log

## Summary
- Harness: antigravity-gemini-1
- Branch: lane/l1-audit-brokers
- Worktree Root: C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1
- Current Status: Clarksons, Carriers, Xclusiv, and Agora completed (100% PASS); starting Fearnleys-md audit
- Units Completed: 4 (Clarksons, Carriers, Xclusiv, Agora)
- Findings:
  - Clarksons: 180/180 clean; 0 absent numbers (5,814 numbers audited); 12 stratified eye checks (648 cells) 0 defects.
  - Carriers: 135/135 clean; 0 absent numbers (19,489 numbers audited); 13 stratified eye checks (2,682 cells) 0 defects.
  - Xclusiv: 267/267 clean; 0 absent numbers (214,835 numbers audited); 12 stratified eye checks (1,026 cells) 0 defects.
  - Agora: 216/216 clean; 0 absent numbers (60,740 numbers audited); 12 stratified eye checks (1,092 cells) 0 defects.
- Next Task in Order: Fearnleys-md full-sample audit
- Evidence & Verification: check_evidence.py & validate_knowledge.py clean

## Environment & Location
- `git rev-parse --show-toplevel`: `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`
- `git branch --show-current`: `lane/l1-audit-brokers`

## Log Entries
- Initialized lane `l1-audit-brokers` from `origin/main` in worktree `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`.
- Claimed `l1-audit-brokers` by writing `docs/handoff/claims/l1-audit-brokers.json` and pushing to `origin lane/l1-audit-brokers`.
- Commencing work list in order: Clarksons -> Carriers -> Xclusiv -> Agora -> Fearnleys-md.
- **Clarksons Full-Sample Audit**:
  - Machine sweep: 180 MD files swept against primary PDFs (`corpus/02-hellenic/shipbuilding/pdfs/<year>/` and `corpus/01-brokers/clarksons/2026/`).
  - 5,814 numbers extracted and checked against PDF text layers: 0 absent.
  - Resolved `clarksons_2026_Weekly-Sales-9th-October-2026.md` against worktree PDF (`clarksons_2026_Weekly-Sales-9th-October-2026.pdf`), matching all 48 numbers.
  - Verified edge cases: `3,6000` printed verbatim in PDF text layer; `2021` conjoined with `NEW` in text layer.
  - Generated full machine audit log: `docs/handoff/audit/clarksons_machine.csv` (180/180 clean).
  - Stratified visual eye pass (manual 4a): 12 issues rendered side-by-side with `scripts/verify/page_view.py side`:
    1. 2021 first (`2021-07-02`): 9 rows, 72 cells. 0 defects.
    2. 2021 last (`2021-12-24`): 6 rows, 48 cells. 0 defects.
    3. 2022 first (`2022-01-07`): 5 rows, 40 cells. 0 defects.
    4. 2022 last (`2022-12-23`): 5 rows, 40 cells. 0 defects.
    5. 2023 first (`2023-01-09`): 6 rows, 48 cells. 0 defects.
    6. 2023 last (`2023-12-22`): 1 row, 8 cells. 0 defects.
    7. 2024 first (`2024-01-05`): 8 rows, 64 cells. 0 defects.
    8. 2024 last (`2024-02-23`): 11 rows, 88 cells. 0 defects.
    9. 2025 first (`2025-10-24`): 11 rows, 88 cells. 0 defects.
    10. 2025 last (`2025-12-19`): 4 rows, 32 cells. 0 defects.
    11. 2026 first (`2026-01-09`): 5 rows, 40 cells. 0 defects.
    12. 2026 last (`2026-10-09`): 10 rows, 80 cells. 0 defects.
    - Total eye-checked: 648 cells, 0 defects.
  - Author and committed final verdict: `docs/handoff/audit/clarksons_verdict.md`.
- **Carriers Full-Sample Audit**:
  - Machine sweep: 135 MD files swept against primary PDFs (`corpus/01-brokers/carriers/<year>/`).
  - 19,489 numbers extracted and checked against PDF text layers: 0 absent (100.0% clean).
  - Generated full machine audit log: `docs/handoff/audit/carriers_machine.csv` (135/135 clean).
  - Stratified visual eye pass (manual 4a): 13 issues rendered side-by-side with `scripts/verify/page_view.py side`:
    1. 2021 only (`carriers_2021_19-Nov-2021.md`): 13 rows, 130 cells. 0 defects.
    2. 2023 first (`carriers_2023_W46_WK-46-23-CARRIERS_SP-MARKET-REPORT.md`): 37 rows, 296 cells. 0 defects.
    3. 2023 mid (`carriers_2023_W48_WK-48-23-CARRIERS_SP-MARKET-REPORT.md`): 28 rows, 224 cells. 0 defects.
    4. 2023 last (`carriers_2023_W51_WK-51-23-CARRIERS_SP-MARKET-REPORT.md`): 26 rows, 208 cells. 0 defects.
    5. 2024 first (`carriers_2024_W01_WK-12-24-CARRIERS_SP-MARKET-REPORT.md`): 29 rows, 232 cells. 0 defects.
    6. 2024 mid (`carriers_2024_W28_WK-28-24-CARRIERS_SP-MARKET-REPORT.md`): 33 rows, 264 cells. 0 defects.
    7. 2024 last (`carriers_2024_W52_WK-52-24-CARRIERS_SP-MARKET-REPORT.md`): 17 rows, 136 cells. 0 defects.
    8. 2025 first (`carriers_2025_W01_WK-0102-25-CARRIERS_SP-MARKET-REPORT.md`): 24 rows, 192 cells. 0 defects.
    9. 2025 mid (`carriers_2025_W24_WK-24-25-CARRIERS_SP-MARKET-REPORT.md`): 24 rows, 192 cells. 0 defects.
    10. 2025 last (`carriers_2025_W51_WK-51-25-CARRIERS_SP-MARKET-REPORT.md`): 19 rows, 152 cells. 0 defects.
    11. 2026 first (`carriers_12_10_2026_carriers_sales_purchase_market_report_week_41.md`): 20 rows, 160 cells. 0 defects.
    12. 2026 mid (`carriers_2026_W20_WK-20-26-CARRIERS_SP-MARKET-REPORT.md`): 33 rows, 264 cells. 0 defects.
    13. 2026 last (`general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.md`): 28 rows, 224 cells. 0 defects.
    - Total eye-checked: 2,682 cells, 0 defects.
  - Author final verdict: `docs/handoff/audit/carriers_verdict.md`.
- **Xclusiv Full-Sample Audit**:
  - Machine sweep: 267 MD files swept against primary PDFs (`corpus/01-brokers/xclusiv/<year>/`).
  - 214,835 numbers extracted and checked against PDF text layers: 0 absent (100.0% clean).
  - Generated full machine audit log: `docs/handoff/audit/xclusiv_machine.csv` (267/267 clean).
  - Stratified visual eye pass (manual 4a): 12 issues rendered side-by-side with `scripts/verify/page_view.py side`:
    1. 2021 first (`xclusiv_2021_xclusiv_weekly_2021_07_26.md`): 24 rows, 129 cells. 0 defects.
    2. 2021 last (`xclusiv_2021_xclusiv_weekly_2021_12_6-.md`): 24 rows, 129 cells. 0 defects.
    3. 2022 first (`xclusiv_2022_xclusiv_weekly_2022_01_10-1.md`): 24 rows, 129 cells. 0 defects.
    4. 2022 last (`xclusiv_2022_xclusiv_weekly_2022_12_27.md`): 24 rows, 129 cells. 0 defects.
    5. 2023 first (`xclusiv_2023_xclusiv_weekly_2023_01_09.md`): 24 rows, 129 cells. 0 defects.
    6. 2023 last (`xclusiv_2023_xclusiv_weekly_2023_12_27.md`): 24 rows, 129 cells. 0 defects.
    7. 2024 first (`xclusiv_2024_xclusiv-2024_01_08.md`): 7 rows, 42 cells. 0 defects.
    8. 2024 last (`xclusiv_2024_xclusiv-2024_12_23.md`): 7 rows, 42 cells. 0 defects.
    9. 2025 first (`xclusiv_2025_xclusiv-2025_01_07.md`): 7 rows, 42 cells. 0 defects.
    10. 2025 last (`xclusiv_2025_xclusiv-2025_12_22.md`): 7 rows, 42 cells. 0 defects.
    11. 2026 first (`xclusiv_06_10_2026_xclusiv_shipbrokers_weekly_05th_october_2026.md`): 7 rows, 42 cells. 0 defects.
    12. 2026 last (`xclusiv_2026_xclusiv-2026_09_28.md`): 7 rows, 42 cells. 0 defects.
    - Total eye-checked: 1,026 cells, 0 defects.
  - Author final verdict: `docs/handoff/audit/xclusiv_verdict.md`.
- **Agora Full-Sample Audit**:
  - Machine sweep: 216 MD files swept against primary PDFs (`corpus/01-brokers/agora/<year>/`).
  - 60,740 numbers extracted and checked against PDF text layers: 0 absent (100.0% clean).
  - Generated full machine audit log: `docs/handoff/audit/agora_machine.csv` (216/216 clean).
  - Stratified visual eye pass (manual 4a): 12 issues rendered side-by-side with `scripts/verify/page_view.py side`:
    1. 2021 first (`agora_2021_W25_...md`): 19 rows, 91 cells. 0 defects.
    2. 2021 last (`agora_2021_W51_...md`): 19 rows, 91 cells. 0 defects.
    3. 2022 first (`agora_2022_W01_...md`): 19 rows, 91 cells. 0 defects.
    4. 2022 last (`agora_2022_W52_...md`): 19 rows, 91 cells. 0 defects.
    5. 2023 first (`agora_2023_W01_...md`): 19 rows, 91 cells. 0 defects.
    6. 2023 last (`agora_2023_W52_...md`): 19 rows, 91 cells. 0 defects.
    7. 2024 first (`agora_2024_W01_...md`): 19 rows, 91 cells. 0 defects.
    8. 2024 last (`agora_2024_W52_...md`): 19 rows, 91 cells. 0 defects.
    9. 2025 first (`agora_2025_W02_...md`): 19 rows, 91 cells. 0 defects.
    10. 2025 last (`agora_2025_W51_...md`): 19 rows, 91 cells. 0 defects.
    11. 2026 first (`agora_09_10_2026_...md`): 19 rows, 91 cells. 0 defects.
    12. 2026 last (`agora_2026_W41_...md`): 19 rows, 91 cells. 0 defects.
    - Total eye-checked: 1,092 cells, 0 defects.
  - Author final verdict: `docs/handoff/audit/agora_verdict.md`.

## Decisions & Rules Followed
- Work strictly inside `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`.
- Edit only files owned by `l1-audit-brokers` (`data/extracted/md/{clarksons,fearnleys-md,carriers,xclusiv,agora}/**` and their scripts/series).
- Never edit protected files or files owned by other lanes.
- Push strictly to `origin lane/l1-audit-brokers`.

## Open Questions
- None.
