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
4. **`scripts/md_cleanup/chart_tables.py`** — removes LLM-guessed chart tables (values not printed in source text layer), replaces with `> Figure: … not transcribed` note. Guarded mode default; ISM (vector-engine charts) and any "Vector" section excluded. Dry-run results in `.reparse_staging/chart_cleanup/guard_published/` (8,890 tables). Was about to APPLY in place — check `git diff --stat data/extracted/md` before committing.

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
