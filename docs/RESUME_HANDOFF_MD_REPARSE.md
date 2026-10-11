# Resume Handoff — Markdown Re-parse & Ingest Automation

Last updated: 2026-10-11 night IST. Worktree: `.claude/worktrees/maritime-audit-docs-review-a8b612`,
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

## STATUS 2026-10-11 (late night) — PARSING NOTES, INTERMODAL TABLE REBUILD

- **Read `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` before judging any "missing" numbers.** It lists the useful
  pages per source (Advanced: drop the last 3 pages; Affinity: page 1; Agora: ignore; Banchero: skip first and last; Carriers
  and Clarksons: drop the last page; Intermodal: drop the last 2 pages from 2024, the last 1 before; Xclusiv: drop the last 2;
  Fearnleys-md: skip first and last). Most Nace "missing" cells were on those excluded pages (Xclusiv 979, Carriers ~1,050,
  Intermodal 534). Re-ranking the defects with only useful pages (scratch script logic: page filter per source) leaves real
  gaps in Star Asia (107), ISM (75 missing / 376 misplaced), Advanced (70) and Clarksons (58), plus chart reads (Drewry AIS, iron ore).
- **Intermodal** (`intermodal_table_rebuild.py`): 77 tables were a header row only — numbers crammed into the header (44) or
  no body at all (33). Each is re-read from its PDF page with LlamaParse (cache `.reparse_staging/intermodal_tables/`):
  - Guards: every body number is printed on the page; the old crammed values printed on the page must survive.
  - Rowspan sector bands come from a majority over intact tables and must match LlamaParse's own label sequence (checked
    by eye: "75k MEG-JAPAN" sits in the Aframax band). A merged $ price over several ships becomes "<price> (en bloc)".
  - A trailing year header that spans two columns has its span moved to the leading label cell, and columns empty in every body row are dropped.
  - 54 rebuilt in 47 files (33 crammed, 21 empty); no header/row column-count mismatch; only table lines changed.
  - Left as is: 11 stray header rows with no table on the page, 2 Secondhand tables (2022 W15, 2023 W02 p6), 1 Period Charters
    table (2021 W31). Not handled yet: a 2022 W42 Demolition table with a missing year column (values shifted).
- `intermodal_chart_guess_note.py`: 8 header-only "tables" in 7 files were LLM reads of the Baltic indices chart; replaced by a
  one-line chart note (public data, not estimated). Both scripts run in `broker_reports_weekly.yml` for new MDs only.

## STATUS 2026-10-11 (night) — TWINS, LINKS, BREAKWAVE/SIGNAL FIDELITY, POTEN CHARTS, IRON ORE CHARTS

All tools are in `scripts/md_cleanup/`. Nothing was deleted: archived MDs are kept under `data/archive/twins/`.

- **Twins** (`resolve_twins.py`, registry `data/derived/twin_documents.json`, 64 entries): same issue extracted twice,
  63 of them byte-identical PDFs (HSN collection-route re-posts) plus misfiles.
  - The twin MD is archived; its series rows are folded into the canonical issue (rows the canonical already had are dropped,
    rows only the twin had are renamed to the canonical with the canonical date). Rows of misfiled twins are dropped.
  - 5 Xclusiv entries are `promote`: the re-post read about twice as many PDF numbers, so it replaced the canonical, renamed.
  - CI: `twin_guard.py --apply` in `report_ingest.yml` checks each NEW MD's PDF md5 against `data/derived/pdf_md5_index.json`
    (rebuild with `--build-index` on a machine holding the corpus). The newcomer is always the twin; a tracked MD is never
    archived in CI, because `protect_accepted_md.py` would restore it.
- **Asset links** (`relative_asset_links.py`, `--list-missing` prints dead targets): every `file:///` link in Breakwave,
  Signal and Poten is now relative, and every local link resolves except one Signal image.
  - Breakwave: the 64 dead links were ANZ Research (63) and Baker Institute (1) PDFs linked from Breakwave insights. They
    sit behind a login wall / 403 (the scraper had rightly rejected the 5 KB login pages), so the links now point to the
    original URLs taken from the live Breakwave pages.
  - Signal: 6 missing chart images downloaded from Signal's CDN (owner OK'd) into `corpus/07-signal/images/`. Three names
    contain `)`, which had truncated the MD links; fixed with `%29`. `7df2b330-…` is broken on Signal's own page.
- **Breakwave/Signal text** (`restore_html_paragraphs.py`): blocks the HTML-to-MD pass dropped (nested sub-bullets, chart
  captions) were re-inserted, additive only: Breakwave 83 blocks / 43 files, Signal 11 / 9. Coverage vs the source HTML is now
  99.6% (Breakwave) and 99.3%+ (Signal); 67 partial-wording losses are reported, not touched.
  Owner: Breakwave's BDI/BDTI/FFA charts are NOT estimated — those values are public and already in Index.md. Same rule for any
  future chart whose data exists elsewhere.
- **Poten** (`poten_chart_captions.py`): exhibits had the article title as caption, a hard-coded "Poten & Partners" source,
  logo crops (2004-08) and nothing about the chart. A LlamaParse agentic read of each PDF page (cache
  `.reparse_staging/poten_charts/`) gives the printed title, unit, x-axis, series and source; logos (dhash) are dropped, and
  charts that were never cropped are added as captions. Values are NOT estimated (charts are images). CI runs it with
  `--untracked` after `run_poten.py`. Poten's site moved (new article URLs); the last issue is 2026-10-02 and 7 issues were
  backfilled.
  - Applied to all Poten MDs: 1,033 exhibits captioned, 239 logo crops dropped, 499 never-cropped charts added as captions,
    134 exhibits left unmatched (kept with their image), 82 MDs where no chart was read. Only caption/image lines changed
    (checked line by line). Titles drawn inside chart images are not in the PDF text layer; samples were checked visually.
  - The 1,276 chart PNGs the MDs reference (148 MB) are committed (owner OK'd); unreferenced logo crops are not.
- **Iron ore** (MMi PDFs): the three chart tables (freight, China imports, index comparisons) were visual guesses (e.g. negative
  C3 freight, wrong x labels). `iron_ore_vector_charts_patch.py` recomputes them from the chart's vector geometry and labels
  them `> **Estimate.**`; charts that do not read cleanly keep the old values under `> **Approximate.**`.
  `iron_ore_chart_series_rebuild.py` rebuilds the three `hellenic_iron_ore_pdf_*` series with a `value_source` column.
  - Applied to 1,189 MDs: vector reads for comparisons 567, freight 1,069, imports 1,125; kept as Approximate 62 / 95 / 39.
  - Spot check (2021-09-16 vs rendered page 4): x labels 8-Sep (old 9-Sep), C3 ~30 and C5 ~12.5 USD/t, import bars exact.
  - The manual MMi runner (`run_hellenic_iron_ore_pdf.py`) writes `value_source` too. CI only ingests the SMM one-page
    report, which has no charts.

## PAUSED 2026-10-11 ~11:40 IST (session limit 89%)
- The owner approved Nace credits (keys rotate via NACE_API_KEY_n lines in ~/.nace/keys.env), the runner download and all open items.
- **Nace cross-check** (`scripts/qa/nace_crosscheck.py`, uncommitted): a full sweep (6 samples per source, 2 pages each) was left running.
  Results go to `.reparse_staging/qa_nace/crosscheck_summary.csv` and `crosscheck_defects.csv`, with the log in `run_full.log`. Triage
  low ok_rate files by rendering pages. `unprinted` = a Nace chart guess, ignored.
- REAL DEFECT FOUND: the Xclusiv **2024+** MDs (legacy template) keep only the current-week column of the Dry and Tanker secondhand price
  tables, dropping prior-year, +/-% and the 3 annual averages. They also mislabel the Panamax/Supramax 15-year rows as Kamsarmax/Ultramax.
  These need a parse-engine profile for the 2024+ template.
- The chart-engine coder (Intermodal date fix, Xclusiv demolition index + wet TCE) was STOPPED midway. Check `git status` for partial
  edits in scripts/extract/publishers/*intermodal*, *xclusiv*, tests/test_chart_engines_new_only.py and broker_reports_weekly.yml,
  and review or revert them before committing anything.
- Runner: not installed yet. The repo is PUBLIC, so the runner must only serve schedule/dispatch jobs (with fork-PR approval
  required) and gets a dedicated label. Plan: a separate workflow on the residential IP for the HSN fetch, new-only parse,
  and a copy of the new PDFs into the main corpus.
- Still to do: the Athenian historical-prices strip; Nace checks of the Star Asia LDT / Xclusiv annual chart values.

## STATUS 2026-10-11 (evening) — ATHENIAN DUPES + WRONG SERIES FIXED

- **SEC filings (90c98b8a62):** EX-99 exhibits backfilled into 563 6-K/8-K filings, which leaves 73 cover-only 6-Ks (image-only or EX-1..5).
  Broken table rows went from 12,733 to 0, with text preserved in all 736 edited files. `sec_filings_weekly.yml` fetches new filings only.
  Open items:
  - 203 6-Ks have image-only exhibits, and 7 filings have PDF exhibits.
  - About 25 6-Ks have EX-1..5 press releases (EuroDry) that were not fetched.
  - 1,022 table rows have a cell count that differs from their header. They were left alone, because realigning could shift numbers.

- The 295 `athenian_*` MDs written by the legacy `run_hellenic_demolition.py` Athenian branch put prices under the
  wrong country/sector (W36 2026: India Containers $271, but the PDF says $480). They are removed. Every issue has a plain MD from
  `run_athenian_demolition.py`, checked by year+week. 2026 W40 was legacy-only, so a plain MD was generated and checked against the PDF.
  The result is 258 MDs, one per issue.
- `hellenic_athenian_demolition_series.csv` was removed: 2,076 of 2,532 comparable rows were wrong. The canonical series is
  `athenian_indicative_demolition_series.csv`; 36 values sampled from 2021, 2023 and 2025 match the PDFs.
- `run_athenian_demolition.py --new-only` skips PDFs whose stem or issue date already has an MD, and the series CSVs upsert by
  source_file and never truncate. A plain run truncated them to the 12 rows of the one PDF in a CI checkout. CI
  (`report_ingest.yml`) now runs it instead of `run_hellenic_demolition.py`, whose Athenian branch is guarded like GMS/BO.
- The Athenian MDs still omit the printed "Historical demolition prices" strip, as they always did. This gap is known and left alone.
- **Best Oasis 2025-12-30 / 2026-05-05:** page 4 (SHIP RECYCLING price table + vessels sold) had been dropped as
  "trailing boilerplate". On a "no sales" week the page is under 60 words and carries the disclaimer. Fixed with an opt-in
  `last_page_keep_regex` page rule (best_oasis profile only); no 7- or 9-page BO PDF has that phrase on its last page. Both
  MDs were re-parsed and the tables checked against the rendered pages.
- **Chart engines in CI** (`broker_reports_weekly.yml`): SSY (`run_ssy_charts --new-only` + `merge_ssy_charts --new-only`)
  and ISM (`run_ism_series --new-only`) run there now; both append only. The SSY 5 Oct report added 2 keys, and a rerun adds 0.
  Intermodal and Xclusiv got a new-only mode but are NOT in CI:
  - Intermodal overlap diffs are 4-51%, and its x-axis dates sit on the 25th, but the engine assumes month-end.
  - **Xclusiv vector engine is broken** and now refuses to run (`ALLOW_BROKEN_XCLUSIV_VECTOR=1` overrides). It read the
    dashed Max/Average reference lines (Capesize 5TC alternated 86,590.1 / 22,568.3), and the demolition panels used a
    hard-coded 200-700 axis. `xclusiv_bulk_carrier_charts_series.csv` and `xclusiv_demolition_charts_series.csv` were removed.
    The Capesize/Kamsarmax TCs are Baltic data we already scrape; only rebuild the demolition-index panels if wanted.

## STATUS 2026-10-11 (later) — METADATA + GMS + DUPES DONE (7c5ce3b3b9, c1a3164dc8, 0854c1ceb3)
- Frontmatter: `scripts/md_cleanup/frontmatter_fix.py` added headers to 1,440 header-less MDs (body byte-identical),
  then 82 leftovers by hand rules (0854c1ceb3): Fearnleys browser prints take the content-header date; Banchero
  issue_date = end of printed week range; 62 Agora issues print no date -> year/report_week only. Drewry 10 AIS
  series files keep no issue_date (intentional).
- GMS: `scripts/parse_engine/gms.py` + `profiles/gms.yaml`; 272 issues replace 818 legacy/dupe files. 2022 weeks
  1/17/20 have no PDF -> flat `hellenic/demolition/2022/gms_*.md` HTML scrapes kept as only copy. 2022-05-21 cover
  date kept as printed (Week 21; likely publisher typo for 05-27). Accepted flags: low_text_recall (disclaimers,
  trivia dropped by design), low_table_numeric_recall (port date moved into heading). No unit tests for gms.py yet.
- Best Oasis: 214 CI-recreated `best_oasis_*` dupes removed; profile now globs `pdfs/best_oasis/` (+9 issues never
  parsed). 2022-12-28 PDF is image-only -> legacy copy kept.
- Guards: `ALLOW_LEGACY_DEMOLITION_EXTRACT=1` needed for run_hellenic_gms_demolition / run_gms_demolition /
  run_best_oasis_demolition and the BO/GMS branches of run_hellenic_demolition (Athenian still owned there). CI runs
  the engine `--new-only` for best_oasis + gms. Tests in tests/test_parse_engine_legacy_guards.py.
- OPEN for owner: Athenian has the same dup pattern (athenian_* vs plain names, ~552 files); Banchero 2026 W38 has
  two copies (`bancosta_23_09_2026_*` + `*_W38_*`) and W40 exists only as `banchero_costa_07_10_2026_*`;
  GMS/Best Oasis series CSVs are no longer refreshed by the retired runners (engine `series` for them not built).
NEXT: self-hosted runner (owner OK to download). Keys rotation at end (owner).

## STATUS 2026-10-11 — VV COMPLETE ON MAIN (ebd75cf192 MDs, c3347028e9 series)
VV 256/256 on engine: 33 untabulatable deal sentences printed verbatim ("Other reported deals (as printed, not
tabulated)"); vv_2026-10-06 re-parsed. Series regenerated, owner chose "accurate only": sales 2,067 rows/254 issues;
matrix 12,373 rows/160 OCR-validated issues (87 unvalidated legacy issues dropped). NOTE: matrix OCR fails on all
2026-03 onward images (small images) -> matrix series ends 2026-03-03; future improvement = better OCR for small images.
Full tests/ run: 33 non-VV failures (test_ui_tabs, test_wave1_pipeline_truth) — pre-existing? not investigated.
NEXT: metadata normalisation + dupes → self-hosted runner (owner OK to download). Keys rotation at end (owner).

## STATUS 2026-10-10 (evening) — Carriers row-level LIVE ON MAIN (9bec4563cd, merged e61619d05a)
scripts/md_cleanup/carriers_rows_fix.py: 121 files (extended 114, filled 146, demolition_realign 142, shift_realign 193,
row_added 46, en_bloc 2, label_fix 33 SUPRA 63K->TESS 58K). 2024 W06/2025 W25 price/buyer columns swapped back (PDF
prints them inverted; note in MD). 2021-11-19 file is a Seasure "Blue Report" misfiled under carriers — MD rebuilt by
hand from PDF text layer (report_publisher frontmatter key). 18 tables unresolved (staging changelogs).
IN PROGRESS: VV leftovers (coder): 33 unparsed deal sentences -> verbatim "Other reported deals (as printed)" list so
31 blocked issues promote; vv_2026-10-06 legacy re-parse; full VV series regen (staged + compare first).
NEXT: metadata normalisation + dupes → self-hosted runner (needs owner OK to download). Keys rotation at end (owner).

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

## 2026-10-11 ~13:30 IST — Nace triage (UNCOMMITTED, run validator then commit)
- Checker fixed (scripts/qa/nace_crosscheck.py): European decimal comma + full row label. Re-score from cache = no credits.
- Advanced Shipping: crop y 480->500 in run_advanced_shipping_tables.py. 61 MDs patched by ONE row each (Handysize 28k 15yr: 15 missing 2021 W26-40, 46 garbled 2021 W41-2022 W52), sidecars + secondhand series CSV patched surgically (+61/-46). Spot-checked vs PDF text.
- Carriers: BSPA/BDA box untitled in 2024 W07 + 2026 W17-W26 (9 files). Anchor fallback on "price in $m" in run_carriers_complete.py; sections spliced into 9 MDs + sidecars; bspa +54 / bda +27 series rows (0 lost). W21 values match Nace.
- By design (not defects): Carriers Greek equities page, Clarksons Baltic/FX/bunker box (drop_regions).
- TODO: corpus-wide TEXT-twin scan (byte dedup misses them): Advanced 2025 W45/W46-1, 2026 W38/19_09, W39/26_09, W40/03_10; Carriers W39/general_broker_28_09_2026. Nace sweep still running (bzpgmeq0h) — continue triage from run_full.log after clarksons.

## 2026-10-11 afternoon — pushed 5a7553edc4 (Advanced + Carriers); then:
- **Xclusiv secondhand (2024-2026, 133 MDs):** dry + tanker tables restored to all 6 printed columns
  (month, same month last year, ±%, 3 yearly averages) and 15y rows relabelled from the PDF
  (Kamsarmax->Panamax, Ultramax->Supramax). Current values asserted equal to the old MD before writing.
  xclusiv_secondhand_series.csv: 147 15y labels fixed (keyed by original label: 4 files have equal prices).
  Generator run_xclusiv_tables.py: enrich_secondhand_from_text() so CI renders the same 8-col table
  (sandbox output byte-identical to patched MDs; falls back to 3-col when a row lacks 6 printed values).
  NOT done: 2021-2023 (different layout: "12m diff", size-labelled rows), 2024-04-08 / 05-08 (one row prints 5 values),
  2025-02-24 + 2026 Feb/Aug-31 parse fails, 6 files with no 3-col block.
- **Drewry AIS was NOT ingesting in CI since 2026-09-23** (refactor f20e02dc6c): fetcher import path,
  opinions runner crash on missing gitignored corpus/06-drewry/ais, charts runner crash. All three fixed.
  run_drewry_ais upsert no longer falls back to "new rows only" on a read error. Plain-text (no LlamaParse:
  ALL LlamaParse keys out of credit) fallback now reads the KPI cards + commentary; 288 cached reports
  extract identically. W40 (VLCC, Handysize, LR1) ingested; PDFs copied to main corpus/06-drewry/ais.
- **Poten:** tanker-opinions listing 404s since the site redesign; RSS empty. Owner decision (source gone?).
  The workflow's Poten assert fails the job weekly (after the commit step, so data still lands).
- **Twins:** 64 MD pairs from the same PDF text under two names (two ingest routes, mostly 2026:
  ssy 14, iron_ore_pdf 12, xclusiv 7, agora 4, carriers 4, advanced 3 ...). List:
  scratchpad md_twins.json (regenerate: text-hash every corpus PDF). Needs per-publisher series cleanup +
  a text-hash guard at ingest. Not started.
- Intermodal coder WIP parked as .reparse_staging/intermodal_charts_wip.patch (unverified; files restored).
- **Nace sweep triage (by design, not defects):** Intermodal "missing" = final market-data pages (commodities,
  bunkers, stocks) excluded from MDs and extracted by run_intermodal_finance; Clarksons Baltic/FX box; Carriers
  Greek equities; Drewry ais_charts MDs are summaries (data in vector CSVs).
- **OWNER DECISION — iron ore chart reads:** 1,164/1,201 iron_ore_pdf MDs carry "## Dry Bulk Freight Rates
  Historical Line Data" and 629 carry "## Historical Iron Ore Index Comparisons". Values are whole numbers /
  multiples of 5 on chart axis-label dates (e.g. 2023-09-01: 4-Jan-21 15.00/18.00 ...; dates not in the text
  layer or are axis ticks). These are visual chart reads presented as data (anti-fabrication pattern).
  Iron ore is owner hand-perfected -> not touched. Options: drop the two sections (keep a "> Figure:" note),
  or keep with an explicit "approximate chart read" caption. Also omitted printed cells: freight change % /
  52w low-high, futures volume/OI changes.
