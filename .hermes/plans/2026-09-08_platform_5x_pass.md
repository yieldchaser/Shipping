# Platform 5x Pass — 2026-09-08 (evening wave)

Standing rules: python3.12 (`C:/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe`); CRLF preserve (python line-surgery, not text-mode rewrites); zero-emoji; no AI-slop stripes; split code/data commits; rebase-before-push; full tests + headless + vision gates each phase; never fabricate — missing data is disclosed, not invented.

## User decisions (locked)
- Fearnleys tab -> **BROKER DESK** (visible label; ids/paths stay `fearn*`; Fearnleys attribution lives in tooltips/meta/source lines).
- TC Rates: **source toggle, one source at a time** — default `Baltic Weekly (2000+)`, second option `Fearnleys Monthly (1977+)`. REMOVE the stitched archive dataset entirely (user: "no stitching; half green half purple looks weird"). Tests referencing the old archive marker must be updated to the toggle world.

## Phase A (parallel-safe, two agents)
- **A1 (index.html only)** — rename tab to BROKER DESK everywhere visible; Overview tile order: (1) TC rates by class Capesize->Panamax->Supramax->Handysize, then Tanker VLCC->Suezmax->Aframax->MR->Product, (2) Newbuilding in family order, (3) S&P/Resale in order; TC source toggle (removes archive ds + purple meta); dynamic tooltips on every element touched (data-tt-* bus: rt-title + labeled rows, all values from caches, honest omission).
- **AD (data/pipeline only, NO index.html, NO push)** — BIX archive: new `scripts/bunkers/build_bix_history.py` appending daily BIX snapshots into `data/bunkers/bix_history.csv` (long obs), integrated into bunker_frontend_summary.json (bix_history key); seeds from current 150 rows; tests for the builder. UI consumption lands in Phase B.

## Phase B — Bunkers tab (after A1+AD land)
Remove PROVENANCE debug bar; BIX full-history chart from bix_history.csv + region/grade selectors ("archive begins 2026-08-24" honest note until harvest grows); fix lower-left dead space (layout); purge code-speak ("(--)" chips, provenance/source-col names in UI); detailed dynamic tooltips on ALL buttons/selectors/KPIs/rows/map pins.

## Phase C — Tracking tab (after B)
Chokepoint selector across all 28 straits/canals (transits_daily.csv has per-sector counts 2019->2026-08-30); sector highlight map (Dry Bulk / Tanker / Container / ...) from port_lineups_active.csv (asset_class, cargo_type, days_waiting per vessel; click-through; honest note: no voyage-track data in sources); port activity history panel (calls vs 5Y avg from portwatch_port_congestion.csv); "Global port activity monitor" placement analysis (Signals -> Tracking?); fill empty lower-left; tooltips everywhere.

## Phase D — Global audit pass (after C)
Tooltip coverage audit EVERY tab (dynamic data-tt-* on each button/selector/chart/KPI/row — Intelligence-tab standard); hardcoded-value hunt (grep + runtime sweep: literals that should come from caches; "(--)" chips; kpis{}-speak); improvement/teardown list; purge leftovers.

## Final bug audits (parent)
Full pytest suite; headless sweep every tab/section (0 errors, all charts have data); vision screenshots; hardcoded sweep; emoji + stripe gates; push watched CI; live hash verify (CRLF-normalized).
