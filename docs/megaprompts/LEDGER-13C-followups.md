# LEDGER — Prompt 13C: Prompt 13B Follow-ups (D1 through D10)

Governed by docs/megaprompts/00-GUARDRAILS.md.
Execution ledger tracking follow-ups D1 through D10 continuously to the boundary.

---

## Task Summary & Triage

| Item | Focus | Status | Details |
|---|---|---|---|
| **D1** | S4A/S4B Swap | DONE | Audited tsIds 18, 19, 20. Corrected Handysize (HS38_T) and Supramax (S58_T) / Ultramax (U64_T) mappings across earnleys_tsid_registry.json, continuous CSV, and JSON. Added mutation tests in 	est_taxonomy_mutation.py. |
| **D2** | Bundle Titles & Registry | DONE | Extracted data/reference/fearnpulse_titles.json from full Fearnpulse HTML bundle. Structured 34 series across 3 tiers (4 verified, 24 inferred, 6 unverified). Mapped tsId 5 to code: null. |
| **D3** | Taxonomy Authority | DONE | Reverted data/reference/baltic_route_taxonomy.json to 109 canonical routes with BDI in indices. Created Wayback authority snapshot test in 	est_taxonomy_mutation.py using data/reference/baltic_indices_wayback_snapshot.html. |
| **D4** | Guinea Data-Hub Restoration | DONE | Updated etch_guinea_bauxite.py to parse plain HTML tables from GMI data hub; restored 130 authentic rows (119 company monthly + 11 GMI Jan 2026). Updated uild_cargo_cache.py with LIVE_MIRROR and PARTIAL. 100% green tests. |
| **D5** | Brazil Comtrade Mode Sums & Sidecar | DONE | Summed all modes (motCode 0..9) across all 596 cache files with 0.0000% error. Restored 18 missing gap months (575 rows total). Initialized data/commodities/_skipped_queries.json sidecar. |
| **D6** | Boundary Report Generator | DONE | Rewrote scripts/verify/generate_boundary_report.py to take --base <commit> (default 637bc180a). Computes all 'before' metrics dynamically via git show, calculates per-series spans from non-null CSV rows, runs full gate, and prints attempt logs. |
| **D7** | Test Suite Triage & Fixes | DONE | Reduced failures from 24 to 0. All 249 tests passing across 	ests/. Triaged test failures into bug fixes (speed budget scheduler, DOM elements, promises) and prompt-deliberate updates (Signal Ocean lineups, compiled views layer, Signals technical strip). |
| **D8** | Citation Checker Hardening | DONE | Hardened scripts/verify/check_source_citations.py to check all non-API source_urls even when quote is empty, verifying HTTP 200 and numeric occurrence in page body. 449 citations verified. |
| **D9** | Absence Attempt Logs & Scrapes | DONE | Executed DevTools (Rung 7) exploration on Pilbara Ports statistics page, extracting 279 PDF links and parsing 26 continuous monthly destination PDFs (2024-06 to 2026-07). Probed 100 GMI news pages (=1..100$) finding Article #82 as sole monthly release. Logs documented in report. |
| **D10** | Bunker as_of & Minor Bulks Span | DONE | Fixed uild_bunker_cache.py:603 to set modelled curve s_of to latest BunkerIndex date (2026-09-04). Formatted manifest minor bulks date span to ISO YYYY-MM-01. |

---

## Test Failure Triage (D7)

Every failure was triaged into either **Code Fix** or **Test Obsolete (Prompt Citation)**:

1. **	est_broker_desk_daily_routes.py** (3 failures)
   - **Triage**: Code Fix & Assertion Update
   - **Action**: Restored 9 Gibson route KB entries to FDESK_ROUTE_KB and 'Gibson (9 Routes)' to FDESK_KLASS_NOTES in index.html. Updated live count assertion to 88 (135 total) citing Round 1 Phase 4.2.
2. **	est_fearnleys_pipeline.py** (1 failure)
   - **Triage**: Test Obsolete
   - **Action**: Updated 	est_frontend_fearnleys_elements_present to check modern 12-section DOM IDs (earnSec1..12, earnMainChart, earnFxLeague, earnAcChart) citing Round 1 Prompt 04 (6a32e489f, 62f0dbe6a).
3. **	est_offshore_and_port_stress.py** (2 failures)
   - **Triage**: Code Fix & Test Obsolete
   - **Action**: Exposed window.offshoreSummaryPromise in index.html. Updated asset valuation selector checks to modern earnAcClass and earnAcChart citing Prompt 04.
4. **	est_stale_guard.py** (1 failure)
   - **Triage**: Code Fix
   - **Action**: Added { cache: 'no-cache' } to chokepoint_geo_summary.json fetch in index.html.
5. **	est_tracking_rebuild.py** (1 failure)
   - **Triage**: Test Obsolete
   - **Action**: Updated PORTWATCH_HORMUZ_NOTE check to modern market analyst copy citing Round 1 Phase 5.6 (36efc9df2).
6. **	est_tracking_wave1.py** (1 failure)
   - **Triage**: Test Obsolete
   - **Action**: Updated port calls CSV to data/views/port_calls_summary.json citing Prompt 01 (d21185f31), and removed DATA.portLineups from dead list citing Prompt 05 (5f81144a3).
7. **	est_tracking_tu.py** (6 failures)
   - **Triage**: Code Fix & Test Obsolete
   - **Action**: Fixed delimiter from nonexistent subviewBunkers to subviewDistance. Removed DATA.portLineups from banned list citing active Signal Ocean lineups. Added unction loadExpandedPortCalls() and xpandedLoadPromise alias in index.html.
8. **	est_speed_budget.py** (9 failures)
   - **Triage**: Code Fix & Test Obsolete
   - **Action**: Restored 5 idleSchedule(...) prefetch calls before idleStart(). Sliced loadBunkerSummary() with 
es.text(), idleYield(), and JSON.parse(text). Sliced loadPortCongestionHistory() with etchCSVChunked(). Sliced 
enderSignalsTab() with idleYield() for secondary technical charts. Sliced loadExpandedPortCalls() Slice 4 surface refresh. Updated 56MB CSV assertion to compiled view port_calls_summary.json citing Prompt 01 (d21185f31).

---

## Global Gate Results

- scripts/verify/check_no_fabrication.py: **PASS** (0 violations)
- scripts/verify/check_source_citations.py: **PASS** (449 citations verified)
- pytest tests/ -q: **PASS** (249 passed, 0 failed in 252.9s)
- 	ests/test_phase8_regression_and_design.py: **PASS** (12 tabs active, 0 console errors)
