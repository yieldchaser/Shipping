# Resume Handoff — Markdown Re-parse & Ingest Automation

Last updated: 2026-10-06 ~23:30 IST. Worktree: `.claude/worktrees/maritime-audit-docs-review-a8b612`,
branch `claude/restore-damaged-md` (WIP pushed to origin). Goal: every `data/extracted/md` file correct
and well-formatted for the DeepSeek GraphRAG build, plus end-to-end ingest automation.

## Done and live on `main`
| Commit | What |
|---|---|
| `be887bcbb` | Restored 411 historical MDs that CI bots damaged on 2026-10-06 (intermodal 251, star_asia 157, banchero 1, seabrokers 2) from baseline `6f07f5e76`; removed 150 case-duplicate Best Oasis MDs. |
| (before `6f35adc5d`) | Write-once guard `scripts/ci/protect_accepted_md.py` in 6 data workflows; removed `clean_all_brokers_formatting.py` from broker workflow; `run_hellenic_demolition.py` can no longer create case-variant duplicates. |
| `478d8a47a` | 12 books renamed to short slugs (no z-lib), proper titles; legacy knowledge validator passes. Main checkout needs `git pull`. |

## Uncommitted-to-main work (on branch, staged outputs in `.reparse_staging/`, gitignored)
1. **`scripts/parse_engine/`** — reproducible engine. Free path: `pymupdf_table` (geometric tables anchored on headers) + `pymupdf_prose`. Paid fallback: LlamaParse v2 `agentic`, version pinned `2026-01-16`, cache in `.parse_cache/<sha256>/` (gitignored). Profiles in `scripts/parse_engine/profiles/*.yaml`. CLI: `python -m scripts.parse_engine run|promote|series ...`.
2. **Clarksons**: 179 unique PDFs (396 files, dupes by sha256) parsed free; promotion plan in `.reparse_staging/clarksons/promotion_plan.csv`. **Verifier said NO-GO** until: B1 retire `scripts/extract/publishers/run_clarksons.py` from `scripts/orchestrate_pipeline.py:102` (it would overwrite) + tables.json schema compat; B2 case-insensitive drop_regions (market box leaks in 55 files); B3 case-insensitive filename date patterns (2026 dates 1 day late); promote source guard; cache config hash; en-bloc grouping; per-vessel Details in merged cells. A coder was fixing these when the session paused — re-check state, re-run batch (free), re-verify, then `promote --apply`, then series.
3. **`scripts/parse_engine_html/`** — VesselsValue HTML deals + VV Mini Matrix image OCR (in progress). Output to `.reparse_staging/vessel_valuations/`.
4. **SHELVED — see HARD RULE.** `scripts/md_cleanup/chart_tables.py` — removes LLM-guessed chart tables (values not printed in source text layer), replaces with `> Figure: … not transcribed` note. Guarded mode default; ISM (vector-engine charts) and any "Vector" section excluded. Dry-run results in `.reparse_staging/chart_cleanup/guard_published/` (8,890 tables). Was about to APPLY in place — check `git diff --stat data/extracted/md` before committing.

## STATUS 2026-10-10 (later) — Intermodal tables LIVE ON MAIN (2a0621f4fa, merged ae04de5d84)
scripts/md_cleanup/intermodal_fix.py (35 tests): 245 files — fill_down 1432 merged cells (+ "(en bloc)" on multi-ship $ prices),
nb_prices 217 tables rebuilt to one schema (values dropped by old MD added from PDF with bbox), demolition_ldt 76 "$ NNN.0m"→"$ NNN/Ldt".
40 unresolved left as-is (26 NB: value lost mid-row; 14 fill: page-spanning/split rows) — list in .reparse_staging/intermodal_fix/_summary.json.
Publisher error kept as printed: 2023 W20–W29 Kamsarmax averages = Newcastlemax's (66/59/51). Owner: Star Asia stays without arrows.
Chart-derived monthly tables (NB prices m$, demolition Date|Bangladesh…) untouched — chart cleanup still SHELVED.
NEXT: Carriers row-level re-parse → VV leftovers → metadata → self-hosted runner. Keys rotation at very end (owner).

## STATUS 2026-10-10 — Star Asia LIVE ON MAIN (f5c1c07e16, merged f00f033710)
197 files: snapshot tables rebuilt from PDF spans, 2932 page-footer lines removed, 4 orphan blocks (2023 W24/W26/W28/W30).
Orphan blocker fixed: unit_key now strips escaped `\*` so escaped cells match; commentary test added (22 tests pass). Validator OK.
Owner decision still pending: Star Asia trend arrows (images) — currently "IMPROVING /" without arrow.
NEXT: Intermodal tables (NB Orders column shift; demolition "$ 540.0m" should be $540/ldt) → Carriers row-level re-parse →
VV leftovers → metadata → self-hosted runner. Keys rotation at very end (owner).

## STATUS 2026-10-08 23:30 IST — PAUSED (weekly limit 98%). Resume Saturday.
LIVE ON MAIN: Clarksons 179 · VV 224/255 · Xclusiv 2021–23 123/124 (18f9a8ae8) · Carriers cell fixes 135 files
(23437f6d4) · Best Oasis 210 issues + 259 dupes removed (4ab1ef138). Knowledge validator passes.
IN PROGRESS — Star Asia (targeted fixer, NOT applied): scripts/md_cleanup/star_asia_fix.py (WIP committed on branch),
staging .reparse_staging/star_asia/ (197 files). Verifier GO on everything except ONE blocker: find_orphans
(~star_asia_fix.py:378-392) is vocabulary-only + unbounded upward walk → must require line == printed PDF table
span/cell concatenation, cap run length; tests: commentary "Alang"/"Prices are about the ships" kept, W28 fragment
removed; rerun must remove exactly 4 blocks (2023 W24/W26/W28/W30). Then verifier → `--promote --apply` → commit → push.
Owner decision pending: trend arrows in Star Asia snapshot are images (↔); currently "IMPROVING /" without arrow.
NEXT after Star Asia: Intermodal tables → Carriers row-level re-parse (154 missing sales rows, demolition column shift
in ~109 files, en-bloc price cells, label drift e.g. SUPRA 63K vs TESS 58K) → VV leftovers (31 blocked issues,
vv_2026-10-06 legacy, VV series regen) → metadata → self-hosted runner. Keys rotation at very end (owner).
Lessons: always verify promote apply by counting files on disk; push loop (fetch+merge+push) races FFA bot.

## STATUS 2026-10-08 midday — CLARKSONS + VV LIVE ON MAIN (c5ee2048f)
- VV: 224/255 issues promoted (51818b6f5). 31 keep old MD (1–2 unparsed deal lines each — next fix).
  Matrix: 160 ok / 94 "not machine-readable" (mostly 2025–26 small images). Benchmark sizes reconciled across
  issues (misreads blanked, 289 cells); label date must equal issue date or ±1–2 weeks. VV series CSVs NOT yet
  regenerated (CI `vv --incremental` will append; full regen pending). Main has vv_2026-10-06.md from legacy runner
  (pre-guard) — re-parse with engine.
- Knowledge validator passes after merge. Pushes to main are slow (repo size) and race the FFA bot: fetch+merge+push loop.
- NEXT: Xclusiv 2021–23 coder running (profile scripts/parse_engine/profiles/xclusiv.yaml, staging .reparse_staging/xclusiv).
  Then Carriers, Best Oasis, Star Asia, Intermodal tables, metadata, self-hosted runner.

## STATUS 2026-10-08 — CLARKSONS DONE (on branch, not yet on main)
- All 179 Clarksons issues promoted from parse engine (commits 9aeb395d1, 056d97c96); 161+20 duplicate/legacy MDs
  removed (hellenic/shipbuilding/clarksons dupes); clarksons_sales_series.csv + demolition series refreshed.
  Verifier GO x2; visual checks vs PDF (SFL 2021-09-17, DONG-A/WUHU/INTERLINK 2022-02-25) match.
- Not merged to main yet: branch also holds in-progress VV parser wired into report_ingest.yml. Merge after VV verified.
- Follow-ups (non-blocking): re-run intermodal staging to confirm geom_table changes don't alter it; test for generic
  exception in cli run; compare_vs_*.csv written into data/extracted/series by `series` (delete, don't commit).
- VV coder started 2026-10-08 on fix list below.

## STATUS 2026-10-07 21:30 IST — PAUSED by owner (usage limits). Agents stopped mid-round; WIP committed on branch.
- Owner priority: START THE DEEPSEEK GRAPHRAG BUILD. Recommendation given: build GraphRAG now on the audited-GOOD
  corpus; exclude data/extracted/md/clarksons, hellenic/shipbuilding/clarksons, hellenic/vessel_valuations (and the
  other defective sources) or ingest them as-is flagged low-trust; swap in re-parsed versions later as incremental updates.
- Clarksons: 3 verifier rounds done. Round-3 confirmed all earlier items fixed. OPEN (coder was mid-fix when stopped,
  partial edits possible — run tests first): (1) export_series._iter_issues picks up SSY file
  clarksons/2026/2026-05-18_ssy-pacific-capesize-… → --require-engine-schema aborts; filter by belongs_to_source.
  (2) en-bloc shared cells: Details concatenated into each sister row (2023-09-29 FENGNING group, 2022-04-08 ARDMORE,
  2023-11-10 TORM ESTRID/ISMINI, 2023-11-17); multi-amount Price cell assigns first amount to all (2021-09-17 SFL
  MEDWAY 14.8/KENT 15.2/CLYDE 14.0, 2024-01-05 XING SHOU HAI 28, TORM ISMINI 20.5). Plus minor list (demo price ranges,
  greek homoglyphs in series, new-only per-PDF try/except, pyyaml in workflows, one workflow only for Clarksons steps).
  Owner question pending: keep engine-added "(en bloc)" marker in Price (not printed in PDF)? I recommended keep.
- VV: verifier fix list items 1–12 (see below) partly done when stopped; OCR cache in .reparse_staging/vessel_valuations/_matrix_cache.
- Not started: Xclusiv, Carriers, Best Oasis, Star Asia, Intermodal tables, metadata, self-hosted runner.

## STATUS 2026-10-07 11:20 IST (uncommitted work on disk in this worktree; nothing promoted)
- Clarksons: all first-round NO-GO items fixed by coder (93 tests pass; legacy runners refuse to run; orchestrators skip
  Clarksons; promote needs --apply). Staged 179/179 flag-free. My visual check of 2024-01-12 vs PDF: staged beats both
  old sets (keeps HIGH/RGN/XS qualifiers, demolition table, commentary). REMAINING: en-bloc merged-cell bug
  (CRESTED/STELLAR EAGLE: shared Details split by line, per-vessel SS/DD duplicated) + explain 98 old-only vessels vs
  clarksons_snp_sales_series.csv. Coder was on it. Then: verifier → visual check → `promote --apply` → series → commit.
- VesselsValue: staged MD far better (2023-03-07 matrix 78/78 exact vs image; commentary/comments/class fixed).
  Verifier NO-GO: benchmark sizes misread (~130 rows: 710k/770k for 110k, 100 for 1100) — emit only when ≥2 renders
  agree; Built/Yard swap (≥9), truncated sizes (≥6), buyer typos, en bloc not in MD, -0; undisclosed digit repair;
  ok matrix needs date label; map series to existing vocab; retire run_hellenic_vessel_valuations.py +
  run_hellenic_vv_matrix.py (report_ingest.yml:152, orchestrate_pipeline.py:113 — 13-col DictWriter would crash).
  Keep current matrix rows for failed issues only in years where current ≥98% accurate vs staged (2026 current = garbage).
  2026 matrix images are 600px — unreadable, mark "not machine-readable", never guess. Coder was on it.
- Agents may have died at session limit: resume by re-sending these fix lists to coders (check git diff first).

## HARD RULE (owner, 2026-10-07)
Never run bulk scripts over MDs audited GOOD (list below). Owner hand-perfected them (tables, firmer/softer, arrows).
Chart cleanup (`scripts/md_cleanup/chart_tables.py`) was applied 2026-10-07, verifier NO-GO: it removed ~197 real
Banchero FFA tables (image-only pages, empty text layer) and kept round-number chart guesses. Fully reverted; tool is
SHELVED — do not run it. Only re-parse the defective sources, and replace a file only after rendering the PDF page
and confirming the new MD beats the old one visually.

## Audit verdicts (PDF text recall + visual page checks)
Good: intermodal text, banchero text/tables, advanced, affinity, carriers (except below), ssy, ism, star_asia (except below), poten, seabrokers, gibson, fearnleys, fearnleys-md, drewry ais text, MMI iron ore, breakwave, alibra, baltic, signal.
Defective → to re-parse with engine (in order):
1. Clarksons (page 2 missing, duplicate set `hellenic/shipbuilding/clarksons`) — in progress.
2. VesselsValue (sector commentary, deal comments, class/name split, matrix 5/78) — in progress.
3. Xclusiv 2021–23 (commentary paragraphs missing, wet text under dry heading).
4. Carriers (TCE "38.806" = 38,806 → 1000x error; sentiment arrow colours lost: red/green images).
5. Best Oasis (commentary missing, axis dumps, empty tables).
6. Star Asia (recycling snapshot table broken, "Page N"/footer noise).
7. Intermodal tables (NB Orders column shift; demolition "$ 540.0m" should be $540/ldt).
Then: metadata normalisation (frontmatter/issue_date for advanced, agora, fearnleys, intermodal, hellenic charter/VV, baltic, breakwave, voice), duplicate cleanup (E2E test dupes banchero W39 / star_asia W40, flat `hellenic/demolition/2026/gms_*.md`).

## Facts to remember
- LlamaParse: only keys #11-13 (last three in `scripts/extract/llama_manager.py` pool) have credits this month; #1-10 return 402. Tiers: fast 1, cost_effective 3, agentic 10, agentic_plus 45 credits/page. Re-parse within 48h free (server cache). Keys are hardcoded in a PUBLIC repo — rotate at the very end (owner decision).
- hellenicshippingnews.com returns 403 to GitHub-hosted runners → self-hosted runner on this PC planned (owner approved hosting). Needs: download `actions-runner-win-x64` v2.337.0 from github.com/actions/runner; shell not elevated → start via Startup folder, not service. Owner must set repo Settings → Actions → fork PR approval to "Require approval for all external contributors" (security setting; do not change it for them).
- Raw broker/Poten/PPA PDFs are local-only (`corpus/**/*.pdf` gitignored); ~4,000 Hellenic PDFs + books are tracked.
- Parsing rules per broker: `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` (Agora: owner says keep what exists).
- Owner defaults applied: Clarksons date conflicts resolved (year typo → filename; header confirmed by second filename date → header); hash-duplicate old MDs removed; chart guesses dropped with figure note.
