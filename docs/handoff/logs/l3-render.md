# Lane l3-render Log

## Summary
- Harness: antigravity-gemini-1
- Branch: lane/l3-render
- Worktree Root: C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1
- Current Status: Package D (Render checks) COMPLETE; Gibson full-sample audit COMPLETE; Package E (Fearnleys orphans inventory) COMPLETE; Package F (Duplicate voice records and stale _digests inventory) COMPLETE; Fearnleys weekly full-sample audit COMPLETE
- Units Completed: Package D (31 tables/MD checks) + Gibson (262 MDs machine-checked, 12 issues eye-checked) + Package E (4,950 orphan MDs indexed and matched) + Package F (634 duplicate voice groups / 1,268 files audited; 207 digest files audited) + Fearnleys Weekly (261 MDs machine-checked, 13 stratified issues eye-checked)
- Findings: Seabrokers (PASS), Intermodal W08/W09 (PASS), Fearnleys 2018 W29 (PASS), Banchero Costa (17 PASS, 3 REBUILD NEEDED), Gibson (262/262 clean, 0 defects, 100% PASS), Fearnleys orphans (190 exact name, 4,743 same date+title, 17 none), Voice Duplicates (634 groups, 0 full-file byte-identical due to distinct UUIDs, 632 body-prose-identical), Stale Digests (200 differs/matched, 7 no canonical found), Fearnleys Weekly (260/261 clean, 1 OK-IMAGE verified in Package D, 13 stratified eye checks, 0 defects, 100% PASS)
- Next Task in Order: All sources owned by lane l3-render in lanes.json and packages D, E, F are completely audited and verified. Awaiting upstream lane merges or next assignments.
- Evidence & Verification: All visual crops saved in docs/handoff/evidence/l3-render/; check_evidence.py & validate_knowledge.py verified

## Environment & Location
- `git rev-parse --show-toplevel`: `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1`
- `git branch --show-current`: `lane/l3-render`

## Log Entries
- Initialized worktree at `C:/Users/Dell/Github/Shipping-wt-antigravity-gemini-1` from `origin/main`.
- Claimed `l3-render` by writing `docs/handoff/claims/l3-render.json` and pushing to `origin lane/l3-render`.
- Executed visual audit for **Package D** target 1: Seabrokers 2019-05 Seabay Spotlist table on Page 8. Rendered 300 DPI crop (`docs/handoff/evidence/l3-render/seabrokers_2019_05_p8_spotlist.png`), inspected all 14 rows / 10 columns (140 cells). 100% exact match.
- Executed visual audit for **Package D** target 2: Intermodal 2026 W08 and W09 raster S&P, demolition, and currency tables (Pages 4 and 6). Verified 404 cells across 8 tables. 100% exact match.
- Executed visual audit for **Package D** target 3: Fearnleys 2018 W29 (Page 3). Verified Newbuilding Contracts (8 rows, 64 cells) and S&P (20 rows, 140 cells) against scan. 100% exact match.
- Executed visual audit for **Package D** target 4: Banchero Costa 20 random MDs with IMO tables. Rendered page images, inspected rows. Discovered structural transition: 2025/2026 reports include printed `IMO No.` column and all 17 sample MDs match the PDF image. In 2023/2024 reports, the original PDF had no IMO column; an injected header shifted columns to the left (>20% defect). Per protocol, logged as "REBUILD NEEDED".
- Authored comprehensive verdict report in `docs/handoff/logs/render-checks.md`.
- Executed **Gibson Full-Sample Audit**:
  - Machine pass over all 262 Gibson MDs (109 PDF-era 2021-2023, 153 HTML-era 2023-2026). Output generated at `docs/handoff/audit/gibson_machine.csv`.
  - Machine result: 262 clean / 0 absent / 0 missing source. 100% clean.
  - Stratified eye pass on 12 issues (first and last of each year 2021-2026, plus PDF-to-HTML transition points). Rendered PDF pages side-by-side using `scripts/verify/page_view.py side` and verified HTML tables against source DOMs and Chart.js payloads.
  - Verified 1,348 table cells across all sampled issues. 0 defects found.
  - Authored comprehensive verdict at `docs/handoff/audit/gibson_verdict.md`.
- Executed **Fearnleys Orphans Inventory (Package E)**:
  - Audited all 4,950 unresolvable MDs (184 in `data/extracted/md/fearnleys-md/`, 4,766 in `data/extracted/md/fearnleys/voice/`).
  - Indexed 8,245 Fearnleys source files in corpus (including 4,747 corpus voice records and bespoke PDFs).
  - Categorized into 3 match classes:
    - `exact name`: 190 (3.84%)
    - `same date+title`: 4,743 (95.82%)
    - `none`: 17 (0.34%)
  - Generated full CSV inventory at `docs/handoff/logs/fearnleys-orphans.csv`.
  - Authored comprehensive Markdown summary with yearly breakdown and 10 examples of each class at `docs/handoff/logs/fearnleys-orphans.md`.
- Executed **Duplicate Voice Records and Stale `_digests` Inventory (Package F)**:
  - Audited all 4,748 files under `corpus/01-brokers/fearnleys/voice/` and 4,766 files under `data/extracted/md/fearnleys/voice/`.
  - Identified 634 duplicate `(date, desk)` groups (1,268 files total) created during dual Hasura export runs (un-suffixed vs hex GUID-suffixed).
  - Verified content identity: 0 full files byte-identical due to distinct database UUIDs in frontmatter; 632 of 634 groups (99.7%) have 100% byte-identical Market Commentary body text.
  - Generated `docs/handoff/logs/dup-voice-groups.csv`.
  - Audited all 207 files under `corpus/01-brokers/_digests/` against canonical extractions in `data/extracted/md/`.
  - Mapped 200 files (96.6%) to canonical MDs (`differs`, reflecting web synopsis scrape vs full table extraction from PDF) including cross-syndicated Gibson and Clarksons reports.
  - Classified remaining 7 files as `no canonical found` (all general maritime blog articles in `carriers/` with empty `pdf_url:` and no publisher PDF report).
  - Generated `docs/handoff/logs/digests-inventory.csv`.
  - Authored comprehensive report at `docs/handoff/logs/dup-inventory.md`.
- Executed **Fearnleys Weekly Full-Sample Audit**:
  - Swept all 261 Fearnleys weekly reports (2018, 2021–2026) against source PDFs in corpus (`docs/handoff/audit/fearnleys_machine.csv`).
  - Machine sweep: 3,389 numbers checked; 260/261 MDs 100% clean with 0 absent numbers.
  - The 1 non-clean file (`fearnleys_2018_W29_fw_week_29_2018b.md`) is a physical bitmap scan whose tables (204 cells) were confirmed 100% accurate in Package D target 3 (classified as `OK-IMAGE`).
  - Conducted stratified visual eye audit across 13 issues (2018 W29, 2021 first/last, 2022 first/last, 2023 first/last, 2024 first/last, 2025 first/last, 2026 first/last). All text and rate assessments match PDF source layers 100%. 0 defects found.
  - Authored comprehensive verdict at `docs/handoff/audit/fearnleys_verdict.md`.

## Decisions & Rules Followed
- In Banchero Costa 2025 W03, the printed IMO for `Prabhu Yuvika` on page 11 is verbatim `92291781` (an 8-digit printed typo by the broker). Verified by eye against image. Kept as printed without guessing.
- In Banchero Costa 2023 W44, 2024 W08, 2024 W44, column shift exceeds 20% threshold. Marked as REBUILD NEEDED without modifying MDs.
- In Gibson audit, verified that tracked origin/main source HTML files under `corpus/01-brokers/gibson/html/` (such as `2024-09-20_losing-relevance.html`) contain full articles and match MD text layers 100%.

## Open Questions
- None.

