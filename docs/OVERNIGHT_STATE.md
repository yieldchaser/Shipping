**THIS RUN (2026-10-03 10:2x-10:4x, source-by-source) - intermodal macro: a SECOND recall defect found by page reconciliation and FIXED (+15 rows), plus the register residual CLOSED. Evidence `docs/intermodal_macro_kerning_verdict.md`.**

**DEFECT FOUND: the macro parser matched indicator labels by EXACT string equality.** Intermodal's own text layer kernels one label apart in one era - 2023 W21-W36 print `Dow J ones ` (split + trailing space) instead of `Dow Jones`, so `IND_CAT.get(lab)` dropped the row. Same class as the currency-allowlist bug. Measured: `intermodal_macro_series.csv` held **239** Dow Jones rows against **254** documents; the **15** missing are exactly `intermodal_2023_W21..W36`.
**Fix:** label keys are now whitespace-insensitive (`re.sub(r'\s+','',s).lower()`) and the row is stored under the CANONICAL label. Re-ran `run_intermodal_finance.py` over 255 canonical reports (2 `_broker_s_insi` byte-dupes skipped, data held via `intermodal_2026_W38/W39`). **macro 4,803 -> 4,818 (+15)**; stocks 3,152 and bunkers 2,287 UNCHANGED.
**CONTROL:** maritime_stocks md5 `4bdc56ea...` and bunkers md5 `b048156b...` byte-identical pre/post; set-diff `(source_file,indicator,issue_date,report_week)` = **added 15, removed 0**, all Dow Jones, **common-key row diffs 0**. **CONTENT VERIFY:** all 15 added rows re-read against their source PDF page (label + printed 5-value series + W-O-W %): **15/15 = 100% verbatim** on latest+prior+pct.
**REGISTER residual CLOSED:** re-ran `scripts/sync_extraction_register.py` after the intermodal thread landed. **170 CSVs, 593,879 logical data rows** (+305 XLSX = 594,184 total); `verify_registers.py` = **0 mismatches**. Line 19 (Intermodal publisher row) hand-updated macro 4,803 -> 4,818, 62,510 -> 62,525.
**STILL OPEN (unchanged, one at a time):** hellenic VV 214 dup rows (the ONE human decision); the other intermodal series have not had this per-page label reconciliation (macro was the only one with a hardcoded allowlist; a full row-count audit per series is still owed). No vision tool in this session - substituted same-document text reconciliation, and said so.

**THIS RUN (2026-10-03 09:0x, source-by-source) - INTERMODAL depth: a NEW recall defect found by rendering the page and FIXED (+1,016 rows), plus a silent no-op sidecar path. Evidence `docs/intermodal_macro_verdict.md` (ADDENDUM 2026-10-03).**

**The prompt's "xclusiv IN PROGRESS" is STALE** - xclusiv is DONE (271 md files on disk; `docs/xclusiv_verdict.md`, 266/266, 3 passes). All 01-brokers sources are built. Both ledger items the state called "open" (4.3 macro, ism tail) are ALSO already CLOSED. So this run did source-by-source DEPTH instead, on intermodal.

**DEFECT FOUND (new): the finance page prints 7 currencies, the CSV held 3.** `intermodal_macro_series.csv` was 3,787 rows (16 indicators). The page's currency block is `€ / $ | £ / $ | $ / ¥ | $ / NoK | Yuan / $ | Won / $ | $ INDEX`; the runner's hardcoded `INDICATORS` allowlist matched ONLY the 3 ASCII-named ones, so **€/$, £/$, $/¥, $/NoK were dropped on all 254 issues**. Checked "already held?": `intermodal_currencies_series.csv` is a DIFFERENT table (USD/BDT/INR/PKR/TRY); `index.html` does not consume the macro series. **Fix:** 4 labels added to `INDICATORS` (exact bytes: `€ / $`, `£ / $`, `$ / ¥`, `$ / NoK`); `run_intermodal_finance.py` re-run over 255 reports (no API spend). **macro 3,787 -> 4,803** (+1,016 = 4x254); 20 indicators; dup keys 0.
**VERIFIED (content, not count):** every one of the 1,016 new rows re-read against its source PDF page - label followed by exactly the two values and the printed change the CSV carries: **1,016/1,016 = 100.0% verbatim, 0 mismatches** (a first pass showed 90 false "mismatches" = float formatting `1.40` vs `1.4`; numeric compare cleared them). **CONTROL:** `intermodal_maritime_stocks_series.csv` and `intermodal_bunkers_series.csv` **byte-identical** (md5 unchanged).

**SECOND FINDING - a silent no-op path (a verdict claim was false).** The old `intermodal_macro_verdict.md` claimed it had "re-written the sidecar `macro_indicators` for all 252 documents". Measured: **0 of 256 sidecars contained the key** - the runner wrote to a FLAT path (`md/intermodal/<stem>.tables.json`) while `run_intermodal_full.py` writes them **year-partitioned** (`.../<year>/...`), so `sidecar_path.exists()` was always False. **Fixed** (year-partitioned path); **255 sidecars now carry `macro_indicators`** (was 0), spot-checked `2021_W26` `€ / $ 1.19 / 1.18 / -0.6%` matches the page. CSVs byte-identical across the change. **Disclosed residual:** `run_intermodal_full.py` rebuilds its sidecar as a fresh dict, so a future full pass would clobber the key; no script reads it today.

**REGISTER:** the Intermodal row (line 19) was stale across ALL 16 counts (macro 3,739 vs delivered 4,803, etc). Re-measured and corrected: **16 counts, total 62,510 rows** (was 61,694); Section-2 macro line 3,787 -> 4,803.

**NEXT:** mid-tier brokers are all verified; remaining depth work is finding recall gaps the same way - render the page, compare printed rows to the series. intermodal's other 15 series have not had this per-page row-count audit.

**THIS RUN (2026-10-03 02:5x-03:0x, HOURLY SUPERVISOR) - the 8 small census items are RESOLVED: 2 CLOSED (cross-source, lossless, 7 rows), 6 DIAGNOSED as faithful in-document repeats and LEFT AS-IS (28 rows). Evidence `docs/small_dedup_verdict.md`.**

**SUPERVISOR STATUS:** no extraction job running. Prior dedup thread idle since 02:34; a SEPARATE SEC-filings thread committed at 02:52 (`a6bcdd0b6`, 26 issuers) on branch `auto/extract-fixes-2026-10-03-carriers`. Expected phase outputs (text_audit/table_audit/gap_verify/vision_candidates/qaudit_*/sweep_v2) all exist, latest 2026-09-23 - superseded by the dedup/verification campaign, not dead.

**CLOSED (2 files, cross-source, 7 rows):** `star_asia_demolition_series.csv` 3,120 -> **3,116** (-4, the misfiled 2023 W41/W42 pair, valuation_matrix class); `hellenic_iron_ore_commentary_series.csv` 1,182 -> **1,179** (-3, Wayback captures of one MMI page, baltic_ncfi class). CONTROL both: key = all cols except source_file, removed 4/3, **0 added**, keys_pre_only 0, keys_post_only 0, post dup keys 0.
**LEFT AS-IS (6 files, 28 rows, SAME-SOURCE faithful):** clarksons_desk_talk 17, xclusiv_sales 5, poten_top_charterers 2, star_asia_deals 2, hellenic_gms_port_positions 1, star_asia_ferrous_scrap 1. Each is an in-document repeat the publisher actually prints, proven by counting the distinguishing field in the source PDF text (occurrences >= row count; e.g. clarksons "commentary" = a running page header appearing 2-4x per doc, xclusiv JINGJIANG NANYANG 4/4, poten Mexico 5/2). Same class as the carriers_sales LAMBADA double-print - **do NOT re-flag**.
**REVERTED:** a first pass dropped all 35 rows by exact full-row key; that is wrong for the 28 same-source rows (it deletes a printed value). Reverted from `scratch/small_dedup/PRE_*`; only the 2 cross-source fixes stand. **Lesson: split same-source from cross-source BEFORE writing an exact-duplicate filter.**
**POST-FIX CENSUS (all 170 series):** the only remaining duplicate rows are hellenic VV **214** cross-source (matrix 132 / sales 60 / benchmark 22) - the ONE documented HUMAN DECISION - plus the 15 hellenic_vv_matrix same-source rows inside it, plus 1 documented carriers_sales double-print. Everything else is 0.

**BANCHERO / LlamaParse - BLOCKED on credits, but the data is already on disk.** `data/extracted/md/banchero_costa/2026/` holds **BOTH 2026 W39 files** (.md + .tables.json, written 2026-10-02 15:00), so the delivered `bancosta_*` series carry W39; the run's `to do: 2` are byte-identical W39 copies whose re-fetch fails with **HTTP 402 (credits exhausted, ~2,814 spent of the plan)**. Last watchdog decision **2026-09-28 13:10 BLOCKED - not restarting**; it heartbeats every ~30 min. **INTEGRITY FLAG: `watchdog.log` interleaves TWO different states (done=223/failed=0/credits=0 AND done=166/failed=31/credits=2814) and `run.log` was appended at 02:49:57 with no matching restart line - two writers appear to touch the same `_run_state.json`/`run.log`.** Re-enabling needs a fresh key: `python3 scripts/tools/set_llama_key.py --key llx-...`.

**MEASURED CENSUS AT END OF THIS RUN (all 168 `data/extracted/series/*.csv`, key = every column except `source_file`): 265 duplicate-key rows remain, and 229 of them are the ONE known human decision - `hellenic_vv_matrix` 147, `hellenic_vv_sales` 60, `hellenic_vv_benchmark_sales` 22.** The rest are small and NEWLY measured here (not previously named): `clarksons_desk_talk` 17, `xclusiv_sales` 5, `star_asia_demolition` 4, `hellenic_iron_ore_commentary` 3, `poten_top_charterers` 2, `star_asia_deals` 2, `hellenic_gms_port_positions` 1, `star_asia_ferrous_scrap` 1, and `carriers_sales` 1 (the documented publisher-side LAMBADA double print - do NOT re-flag). NEXT RUN: diagnose the small ones (each is a fresh item; note `star_asia_deals` 2 / `star_asia_demolition` 4 are NEW since the star_asia dedup and are a different class from the byte-pair filter).

**LESSON (2026-10-03, lion):** `run_lion_tables.py` has a CORPUS write path - it re-renders and OVERWRITES `corpus/01-brokers/_digests/lion/2026/*week_NN_*.md` for every PDF (lines 769-776). The lion re-run modified **8 corpus digest files**; restored with `git checkout -- corpus/01-brokers/_digests/lion/2026/` (series CSVs are independent, dedup stands). **Before re-running ANY publisher's runner, check whether its write path includes CORPUS, not just data/extracted/.**

**THIS RUN (CONTINUED 4) - the CENSUS TAIL closed: star_asia valuation_matrix (-13) and hellenic_iron_ore_table (-10), both lossless. Evidence `docs/census_tail_dedup_verdict.md`.**

**star_asia_valuation_matrix 3,245 -> 3,232 (-13):** all from the 2023 W41/W42 PDF pair - NOT byte-identical (md5 eca6dc09 vs f18a3945) but **BOTH covers read "WEEK 41 - October 14, 2023"** (the W42-named file is a misfiled Week-41 report, the agora W34/W35 convention). Both give issue_date 2023-10-14 / week 41 and the same matrix -> every row twice.
**hellenic_iron_ore_table 5,624 -> 5,614 (-10):** multiple Wayback captures of the SAME MMI daily page (2026-03-19 x3, 2026-06-08 x4, 2024-06-27 x2) - the baltic_ncfi class.
**CONTROL both:** full-column key removed 13/10, **0 added**; entity sets (issue_date+sector+type+size / +index_family+code+fe_grade) **identical pre/post, 0 PRE-only, 0 POST-only**; post dup keys 0.
**WRITERS NOT PATCHED here** (`run_star_asia_world_class.py`, `run_hellenic_iron_ore_images.py`, and `stack_unstacked_tables.py` for both) - a future re-run would reintroduce them; the delivered CSVs are the artefact of record.
**CENSUS - ALL clear except ONE:** advanced_shipping 148, ssy 132, fearnleys 121, agora 94, star_asia 25 (+ valuation 13), affinity 48, intermodal 36, carriers 253, lion 170, baltic_ncfi 148, bancosta 44, hellenic_iron_ore_table 10. **Only open: hellenic VV 214 - a genuine HUMAN DECISION** (issue_date taken from the download-date filename, 78/261 files differ, + 3x/5x over-copied issues 2026-02-19 & 2026-04-01; date change and dedup are entangled and re-date ~30% of three series).

**THIS RUN (CONTINUED 3) - bancosta CLOSED (44 rows, one byte-identical W39 pair); a NEW flag: the register's whole banchero-costa block is stale. Evidence `docs/bancosta_dedup_verdict.md`.**

**bancosta DEDUP DONE.** All 44 duplicate rows come from ONE byte-identical W39 pair (md5 `2914f821b746cf4360bf77b70c05c0b4`): `banchero_costa_2026_W39_Bancosta-Weekly-2026-39.pdf` vs `bancosta_30_09_2026_banchero_costa_weekly_market_report_week_39_2026.pdf`. sales 3,244 -> **3,220** (-24), newbuilding 2,391 -> **2,377** (-14), demolition 965 -> **959** (-6). A re-run is NOT available (banchero's table layer is glyph-ciphered -> LlamaParse, credits exhausted), so the delivered CSVs are the artefact of record and a controlled row-filter is the instrument. **CONTROL:** full-column key removed 24/14/6, **0 added**; entity sets (issue_date+name+imo / +type+sector) **identical pre/post, 0 PRE-only, 0 POST-only**; post dup keys 0.
**FLAG - the register's Banchero Costa row (line 22) is from a different era than the delivered files.** Measured today vs register: freight_rates 20,321 (reg 25,715), ffa 7,618 (7,659), vhss 469 (3,413), commodities 8,447 (2,319), fx 244 (941), container_fixtures 267 (922), secondhand_matrix 1,891 (1,911). The bancosta series were written by SEVERAL writers at different mtimes (09-29, 09-30, today). Updated only the 3 series this run touched; the rest of the bancosta block needs its own re-measure pass. `run_banchero_costa_tables.py`, `build_banchero_series.py`, `process_banchero_2026_w36_w38.py`, `stack_banchero_series.py`, `run_singletons.py` and `extract_week39_supplements.py` ALL write bancosta_* - a fix must cover every writer.
**CENSUS:** cleared advanced_shipping 148, ssy 132, fearnleys 121, agora 94, star_asia 25, affinity 48, intermodal 36, carriers 253, lion 170, baltic_ncfi 148, bancosta 44. **Still open:** hellenic VV 214 (human decision), star_asia_valuation_matrix 13, hellenic_iron_ore_table 13.

**THIS RUN (CONTINUED 2) - baltic_ncfi CLOSED (the largest un-diagnosed census item, 148 rows); it is an HTML source, not a PDF one. Evidence `docs/baltic_ncfi_dedup_verdict.md`.**

**baltic_ncfi DEDUP DONE.** `baltic_ncfi_series.csv` **2,180 -> 2,032** (148 dropped), dup keys 0. Cause: two Wayback captures of the SAME Ningbo page (140 pairs + 4 triples) - e.g. `2020-05-29_...Index31` and `2020-06-05_...Index3` both display the `2020-06-05 | 2020-05-29` table with identical values; the extractor stamps `issue_date` from the table's current-week column, so both yield the same rows. The two HTML files are NOT byte-identical (md5 287fde89 vs 36344e93) - content-identical only.
**CONTROL:** full-column key `PRE minus POST` = **148 removed, 0 added**; distinct `(issue_date, route)` pairs **2,024 before AND after, 0 PRE-only / 0 POST-only**; metadata CSV (2,218) untouched; re-applying the dedup to the fixed file drops **0** (idempotent).
**Fixed TWO ways:** the delivered CSV was row-filtered AND `run_baltic.py` now dedups at the NCFI stacking step (`[dedup] dropped N ...`), so a re-run cannot reintroduce them. `run_baltic.py` compiles.
**CENSUS NOW (measured this run):** cleared - advanced_shipping 148, ssy 132, fearnleys 121, agora 94, star_asia 25, affinity 48, intermodal 36, carriers 253, lion 170, baltic_ncfi 148. **Still open:** hellenic VV 214 (human decision - download-date-as-issue_date + 3x/5x copies, entangled), bancosta 44, star_asia 17 (valuation_matrix 13), hellenic_iron_ore_table 13 - measured, not yet diagnosed.

**THIS RUN (CONTINUED) - the earlier run's "human decision #2" TAKEN: lion DELIVERED SERIES REGENERATED, LOSSLESS. Branch `auto/extract-fixes-2026-10-03-carriers`; `main` NOT touched. Evidence `docs/lion_dedup_verdict.md`.**

**lion DUP-KEY REGENERATION DONE.** `run_lion_tables.py` (current code) re-run over 46 PDFs -> 46 reports. `data/extracted/series/lion_*`: deals 1,314 -> **1,241**, sales 1,200 -> **1,136**, demometer 576 -> **552**, demo_sales 114 -> **105**; **170 rows removed**, dup keys **0** on all four. `lion_demolition_series.csv` (516) is a DIFFERENT writer, untouched, already 0.
**CONTROL - PROVABLY LOSSLESS:** `POST minus PRE` = **0 added** on every series; entity check (issue_date+vessel, and issue_date+country+vessel_type+price_point for the demometer) gives **identical entity sets pre/post** (sales 1136, deals 1241, demo_sales 105, demometer 552; 0 PRE-only, 0 POST-only on all four). No value changed on any kept row.
**CAUSE:** W37 (2026-09-11) and W38 (2026-09-18) each parsed TWICE - PDF + the `_digests/lion/2026/` markdown (deals 31+31 / 33+33, sales 26+26 / 29+29). The current code looks for digest names (`lion_12_09_2026_lion_weekly_market_report_week_37_2026.md`) that do NOT exist on disk (files are `lion_shipbrokers_12_09_2026_...`), and the W37/W38 PDFs now exist carrying the same data - so the digest jobs are redundant and the re-run is a pure dedup. 18 of the removed keys were whitespace variants (digest "27 th August" vs PDF "27th August"); the entity survived in every case. Same 46 issue dates before and after.
**Register updated** (`docs/EXTRACTION_REGISTER.md` lion rows -> 46 docs / 1,241 / 1,136 / 552 / 516 / 105, 3,550 rows).

**THIS RUN (2026-10-03 02:1x-02:2x) - carriers DUP-KEY REGENERATION EXECUTED and PROVEN (the earlier run's "human decision #1" taken), and that run's "0 duplicate keys" claim is WRONG - 1 publisher-side duplicate survives. Branch `auto/extract-fixes-2026-10-03-carriers`; `main` NOT touched. Evidence `docs/carriers_dedup_verdict.md`.**

**carriers DELIVERED SERIES REGENERATED.** `run_carriers_complete.py` (guard `57d064c09`) re-run over 136 corpus PDFs: 133 processed, **3 SKIP lines**, rebuilds all nine series with `open(...,"w")` so the fix lands in one pass. `data/extracted/series/carriers_*`: sales 3,130 -> **3,061**, dry_tc_period 3,216 -> **3,144**, indices 1,876 -> **1,834**, tanker_tce 804 -> **786**, bspa 749 -> **731**, dry_weighted_routes 670 -> **655**, bda 375 -> **366**, newbuilding 312 -> **306**, demolition 178 -> **174**. **253 removed in total.**
**CONTROL exact:** key = all columns except `source_file`; `PRE minus POST` = **253 removed, 0 added**, and per-series removed == per-series delta. Nothing else moved.
**THE EARLIER SANDBOX'S "-> 0 duplicate keys" WAS WRONG.** `carriers_sales_series.csv` retains exactly **1** duplicate key: **2024 W40 TANKER LAMBADA (104,866 / 2006 / Samsung Heavy Inds - Geoje / 30.00)** from the SAME document (`carriers_2024_W40_WK-40-24-...`), page 1. The **PUBLISHER prints the vessel twice** in the "Tankers / LPG Vessels Reported Sold" table - positioned-text bboxes at y=303.5 AND y=337.7 (34.2 pt = 3 row pitches, x0=52.2 both), with ELIJAH (314.9) and ES SPIRIT (326.3) between them. Faithful extraction, NOT a parser defect; the byte-pair guard cannot see it (one doc, not a copy). **Left AS-IS and recorded**, so the next census does not re-flag it.
**`data/extracted/**` IS GITIGNORED (`.gitignore:73`)** - the delivered CSVs are working-tree artefacts and are NOT committed; only docs/scripts are versioned. md tier: 133 flat `.md` + 133 `.tables.json`; the 3 skipped stems had **no md on disk**, so no orphan to quarantine.
**REMAINING HUMAN DECISIONS (from `docs/EXTRACTION_OVERNIGHT_LOG.md`):** (2) lion - delivered `lion_demometer_series.csv` stale by 24 rows + `lion_deals`/`sales` dup keys 119; a re-run would change VALUES (its runner changed after the delivered files were built, Sep 30 vs Sep 29) so it needs page verification, or a lossless controlled row-filter. (3) hellenic VV - download-date-as-issue_date + 3x/5x copies (214 dup rows), date and dedup entangled, genuine human call. (4) Athenian demolition regeneration + derived-DB rebuild. Un-diagnosed census rows: baltic_ncfi 148, bancosta 44, star_asia 17, hellenic_iron_ore 13.

**THIS RUN (same run, SECOND SOURCE) - agora dedup CLOSED via a controlled row-filter, and the census's skip set was INVERTED for one group. Evidence `docs/agora_dedup_verdict.md`.**

**agora DEDUP DONE. Measured: 217 corpus PDFs / 213 unique / 4 md5 groups.** `agora_indicators_series.csv` 10,002 -> **9,908** (-94). No writer exists (`run_agora.py` writes sidecars only), so this was a deliberate row-filter, not a re-run.
**THE CENSUS'S SKIP STEM IS WRONG FOR THE 2026 WEEK-34/35 PAIR.** `byte_duplicate_stems()` keeps the lexicographically-first stem; for `{agora_2026_W34_...Week-35-2026..., agora_2026_W35_...Week-35-2026...}` that is the **MISFILED** `W34`-named copy (byte-identical to the W35 one, cover line `Week 35 / 2026`). Dropping the skip stem it returns (`..._W35_...`) would have DELETED the correctly-labelled week-35 rows and KEPT the misdated week-34 ones. Proof: both covers read `Week 35 / 2026`; **no** agora 2026 PDF reads `Week 34 / 2026`; the CSV's `2026-08-21/week 34` rows come only from the W34-named file.
Dropped instead: the `W52_...-1` 2024 twin (47) + the `W34`-named misfiled copy (47). **CONTROL: every dropped row's data columns (`section,label,name,period,val_*`) match a kept row -> 0 data rows lost** (only the divergent filename-derived date/week goes). POST 9,908 rows / 211 source files.
**RESIDUAL (the real reason agora is stale to ~2026-09-18):** `agora_2026_W37/W38_...tables.json` are **174-byte STUBS** (`charts: []`, no tables) and `agora_2026_W39_...` / `agora_30_09_2026_...` have **no `.tables.json` at all**. Extending the series needs a rebuilt stacker (none in the repo) AND a reparse of those issues. Not attempted.

**THIS RUN (2026-10-03 01:2x-01:4x) - CORPUS-WIDE DEDUP RE-RUNS, source #5: intermodal FINANCE writer CLOSED and PROVEN - and the re-run also closed a FRESHNESS gap the census did not name. Branch `auto/extract-fixes-2026-10-03-intermodal-finance` (HEAD was `main`; `main` NOT touched). Evidence `docs/intermodal_finance_dedup_verdict.md`.**

**intermodal finance (writer `run_intermodal_finance.py`: macro / maritime_stocks / bunkers) DEDUP + STALE RE-RUN DONE.** 257 corpus PDFs -> **255 canonical** (`[dedup] skipped 2`). Delivered: macro 3,739 -> **3,787**, maritime_stocks 3,119 -> **3,152**, bunkers 2,260 -> **2,287**. **Removed** the 36 dup-stem rows (macro 16/stocks 11/bunkers 9, all stamped `intermodal_23_09_2026_...week_38...`); POST holds 0 rows with a skipped stem. **Added 144** = 4 documents x (16/11/9): `..._2026_W36/37/38/39_...`.
**THE STALENESS WAS A REAL FRESHNESS GAP.** The CSVs were built 2026-09-28 22:28; the second collection route's `_2026_WNN_` copies (W36/W37/W38 collected 09-29 21:58, W39 10-01 15:18) were NEVER written in - so the newest issue (week 39) was missing from all three finance series. Now present. Net new weeks W36/W37/W39; W38 is a same-value rename onto the keeper.
**CONTROL exact:** `PRE minus skipped-stem rows` == `POST` multiset on every column -> removed **0** on all three; all additions belong to the four new docs. Skip set frozen from the SAME `byte_duplicate_stems()` call the run consumed (keeper-instability trap).
**VERIFIED against the document's own text layer** (no vision tool in session - stated, not silently substituted): **540/540 = 100.0%** of the new numeric cells are present verbatim in their source PDF across all 4 docs (macro 48/48, stocks 33/33, bunkers 27/27 each); issue_date == cover line (2026-09-08/15/22/29).
**RESIDUAL (disclosed, not fixed): 2026 W08 is a degraded capture** - finance page p6 has 1,106 chars / 2 drawings vs W07's 2,869 / 200 on the same page index; p3 68 chars vs 1,600. Image-only page -> runner correctly extracts 0 rows. Needs OCR (not on this box). One doc, one week.

**THIS RUN (2026-10-02 00:4x-01:0x) - CORPUS-WIDE DEDUP RE-RUNS, source #4: star_asia CLOSED and PROVEN - 25 duplicate rows dropped, control exact. Branch `auto/extract-fixes-2026-10-02-dedup-fearnleys` (two commits; `main` NOT touched). Evidence `docs/star_asia_dedup_verdict.md`.**

**star_asia DEDUP DONE. Measured: 199 corpus PDFs / 2 md5 duplicate groups -> 197 canonical.** deals **3,358 -> 3,349** (-9), demolition **3,136 -> 3,120** (-16) = **25**; CONTROL exact multiset, 0 added / 0 removed on both. `run_star_asia_tables.py` REBUILDS with `open(...,"w")`, so the enumeration filter alone is enough here (no merge-map trap like fearnleys). Run: `[dedup] skipped 2 ... 197 PDFs`, 197/197, 195 indicative tables repaired, 0 failures.
**THE CENSUS'S 58 IS STALE - re-measured 25.** A scan of ALL TEN `star_asia_*` series found dup-stem rows ONLY in deals 9 + demolition 16; 5y_history / ferrous_scrap / iron_ore / ldt_comparison / metals_energy / scrap_price_trends / valuation_matrix are all **0**, because those writers rebuild with `"w"` and were rebuilt since the census. The same "re-measure before re-running" rule that saved the intermodal 36 -> 0 claim.
4 md/sidecar files for the 2 excluded copies QUARANTINED to `scratch/dedup_census/quarantine_star_asia/` (residual 0). Pre-fix CSVs `scratch/dedup_census/PRE_star_asia_*.csv`.

**NEW FINDING - THE DEDUP KEEPER IS NOT STABLE ACROSS A RUN OF THIS SOURCE'S OWN RUNNER.** `doc_dedup._richness()` ranks sidecars by shape, and `run_star_asia_tables.py` REWRITES every sidecar it processes, so the skip set changes as a side effect: BEFORE the run it was {W38, `star_asia_28_09_2026_...week_39`}, AFTER it is {W38, `star_asia_2026_W39_Market-Report-Week-39-1`}. Both are byte-identical (`md5 41955f76f905095ccaaa5abc41df8e49`). Cause: both sidecars were `{..., charts:[4]}` (richness 4) -> lexicographic tie-break kept `..._2026_W39_...`; the run wrapped that sidecar into a 2-element LIST ([old dict, clean indicative table]) so its measured richness fell 4 -> 2 and the OTHER copy became the keeper on the next computation. **No data lost** (the charts dict survives as element 0), values unaffected - only `source_file`/`issue_date` can switch copy between runs.
**CONSEQUENCE FOR VERIFICATION, cost one wrong control:** recomputing the skip set AFTER the run mis-attributed the W39-1 rows and reported a phantom "55 added" / "14 added". A control must use the skip set the RUN used. PROPOSED FIX, NOT SHIPPED (it changes keeper choice for EVERY publisher, so it needs its own measured run): make `_richness()` recursive (a list contributes its items PLUS each dict element's richness) so a container-rewrap cannot change the ranking; verify by computing every publisher's skip set before/after.

**REMAINING PENDING RE-RUNS (re-measured 2026-10-02):** agora **94** (`agora_indicators_series.csv`) - still NO stacker anywhere in the repo, a re-run changes nothing; needs a rebuilt stacker or a deliberate controlled row-filter. intermodal **16** (`intermodal_macro_series.csv`; plus bunkers/stocks) - `run_intermodal_finance.py` patched but STALE, a re-run changes VALUES and must be page-verified. carriers **327** - a PARALLEL agent's, untouched.

**THIS RUN (2026-10-02 00:0x-00:3x) - CORPUS-WIDE DEDUP RE-RUNS, source #3: fearnleys CLOSED and PROVEN - 121 duplicate rows dropped, control exact once the day's new issue is accounted for. Branch `auto/extract-fixes-2026-10-02-dedup-fearnleys` (HEAD was `main`; `main` NOT touched). Evidence `docs/fearnleys_dedup_verdict.md`.**

**fearnleys DEDUP DONE. Measured: 263 corpus PDFs / 3 md5 duplicate groups -> 260 canonical.** Delivered `fearnleys_rates_series.csv` 17,142 -> **17,076**. Removed exactly **121** duplicate rows (58 from `fearnleys_2026_W37_...` issue_date 2026-09-09, 63 from `fearnleys_24_09_2026_fearnleys_week_39_2026` issue_date 2026-09-24); the third skip stem (W40 Fearnpulse) contributed **0** rows because its composite pkey had already collapsed onto the keeper's. 0 of the 121 shared a pkey with a kept copy.

**THE TRAP HERE WAS THE MERGE MAP - this source's runner is not a rebuild.** `run_fearnleys_normalized.py` seeds `existing_map` from the PREVIOUS series CSV (pkey `issue_date|chapter|section|label`) and writes `existing_map | this-run`. The dedup filter was already wired at the enumeration (3 docs skipped) but that alone changes NOTHING in the delivered file - the skipped copy's 121 rows are re-loaded from disk every run. PATCHED at the load loop (skips rows whose `source_file` stem is in the skip set + reports the count). Run: `[dedup] skipped 3 ... [dedup] dropped 121 stale row(s) ... Successfully normalized 260 Fearnleys files`, 260/260, 0 failures, 10,710 rows generated in-pass, ~11 min.

**CONTROL:** PRE minus skipped-stem rows == POST as an exact multiset on every column -> **0 removed, 55 added**, and all 55 additions are ONE document: `fearnleys_01_10_2026_fearnleys_week_40_2026.pdf` (issue_date 2026-10-01, week 40, corpus mtime 2026-10-01 14:31 - collected AFTER the previous series build, PRE held 0 rows for it). Excluding that newly-arrived document: **added 0, removed 0 -> PASS**. Nothing else moved.
**12 orphan md/sidecar files quarantined** to `scratch/dedup_census/quarantine_fearnleys/` (flat + `2026/` mirror for the 3 skipped stems); re-scan: 0 orphans. md tier 260 `.md` + 520 `.tables.json`. Pre-fix copy `scratch/dedup_census/PRE_fearnleys_rates_series.csv`; scripts `scratch/dedup_census/{scan,verify_fearnleys,verify2,find_orphans,quarantine_fearnleys,patch_fearnleys}.py`. NOTE fearnleys is RECORD-ONLY (already ingested structurally) - this is hygiene on a record tier, not new data; do not treat it as a data gain.

**REMAINING PENDING RE-RUNS (re-measured on disk this run):** agora **94** (`agora_indicators_series.csv`) - STILL no stacker anywhere in the repo, so a re-run changes nothing; needs a rebuilt stacker or a deliberate controlled row-filter. star_asia **25** measurable (deals 9 + demolition 16; census 58 across 7 series) - 4 writers still unpatched (`run_star_asia_charts.py`, `run_star_asia_ferrous_scrap.py`, `run_star_asia_price_trends.py`, `stack_unstacked_tables.stack_star_asia`). intermodal **16** (`intermodal_macro_series.csv`; plus bunkers/stocks) - `run_intermodal_finance.py` is patched but STALE, a re-run changes VALUES and must be page-verified. carriers **327** - a PARALLEL agent's, untouched.

**SAME RUN, SECOND SOURCE: affinity CLOSED and PROVEN - 48 duplicate rows dropped, control exact on all three series. Evidence `docs/affinity_dedup_verdict.md`.**

**affinity DEDUP DONE. Measured: 254 corpus PDFs / 7 md5 duplicate groups / 247 unique.** tce **4,058 -> 4,020** (-38), bda **747 -> 741** (-6), indices **498 -> 494** (-4) = **48**, exactly the census. CONTROL: pre minus the dropped-stem rows == post as an exact multiset on every column of all three series - **0 added, 0 removed** beyond the 48.

**THE TRAP HERE WAS TWO WRITERS.** `run_affinity_tables.py` (patched last run) writes only tce + bda; the file that writes **all three** series AND rewrites the md is `polish_affinity_markdown.py`, which had NO filter - running the patched runner alone would have been silently undone. Patched it (shared `byte_duplicate_stems`, applied at its sidecar enumeration), then ran it: `[dedup] skipped 3 ... Processing 247 canonical`, 247 md polished. Its own pre-existing `*_nan_*` cleanup already removes the flat-dir twins, which is why only 3 of 7 groups needed the md5 filter. Pre-patch code kept at `scratch/dedup_ssy/polish_affinity_markdown.py.bak`.
**13 orphan md/sidecar/chart files quarantined** to `scratch/dedup_ssy/quarantine_affinity/`; md tier is now **247 `.md` + 247 `.tables.json`**, exactly one set per canonical report. affinity has NO flat+year md mirror (unlike ssy/ism). Adjacent finding, not fixed: that script's `_nan_` cleanup is `OUT_MD.glob("*_nan_*")` - **flat dir only** - so `_nan_` twins under `<year>/` survive every run; 5 were sitting there.
**DETECTION GOTCHA, cost a wasted pass:** my orphan-file matcher used `f.name.split(".")[0]` as the stem - that is WRONG for affinity because its filenames contain dots (`...-Weekly-18.09.2026-HSN.tables.json` truncates to `...-Weekly-18`). Strip the known suffixes (`.tables.json` / `.charts.json` / `.md`) instead. It matched 0 files on the first attempt and 13 on the second.

**REMAINING PENDING RE-RUNS (re-measured this run per delivered CSV):** fearnleys **121** (`fearnleys_rates_series.csv`, RECORD-ONLY source - lowest value), agora **94** (`agora_indicators_series.csv`), intermodal **36** (bunkers 9 + macro 16 + stocks 11, all from `run_intermodal_finance.py` - not just double-counted but STALE with its parser fixed twice since, so a re-run changes VALUES and must be page-verified), star_asia **25 measured** (deals 9 + demolition 16; the census's 58 counts more series than carry a `source_file` column - the other four star_asia writers are still unpatched), carriers **327** (parallel agent's - untouched).
**agora HAS NO STACKER ANYWHERE IN THE REPO** - `run_agora.py` writes only sidecars + `_run_state.json`; nothing in `scripts/` or `scratch/` writes `agora_indicators_series.csv` (grep: only audits and the register mention it). So agora cannot be deduped by re-running: it needs either a row-filter on the delivered CSV or a rebuilt stacker from its 213 `_run_state.json` entries. Decide deliberately, do not hand-edit a delivered CSV by reflex.
**xclusiv and ism still show duplicate STEMS in their corpus (7 and 3 groups)** but their delivered series carry **0** rows from a skipped stem - already clean. Do not re-open.

**THIS RUN (2026-10-01 22:5x-23:1x) - THE CORPUS-WIDE DEDUP RE-RUNS STARTED: source #1 of the pending list, ssy, is CLOSED and PROVEN. Branch `auto/extract-fixes-2026-10-01-dedup-rerun` (HEAD was `main`; `main` NOT touched this run). Evidence `docs/ssy_dedup_verdict.md`.**

**WHICH BRANCH - READ THIS.** The previous run's two commits (`a7618c051`, `ade7d059a`) and the merge of `auto/extract-fixes-2026-10-01-decimal-comma` landed **on `main`** (reflog: `checkout: moving from auto/extract-fixes-2026-10-01-decimal-comma to main` at 22:22:59, then two commits on main) - so the "main NOT touched" claim in the block below is **wrong**, however conventional `auto/extract-fixes-*` branches may be. This run stayed OFF main: `auto/extract-fixes-2026-10-01-dedup-rerun`.

**ssy DEDUP DONE. Measured: 530 corpus PDFs / 14 md5 duplicate groups -> 516 unique documents.** Delivered series carried **120** duplicate route rows + **12** duplicate index rows = **132**, exactly the census. Re-ran `run_ssy_complete.py` (own per-source runner; full re-parse from the PDFs, not a sidecar re-stack): 516/516 reports, 0 failures, **82.8 s**, route 5,280 -> **5,160**, index 528 -> **516**.
CONTROL, exact: `PRE minus rows whose source_file is a skipped stem` == the post file as an exact multiset on every column and both series - **0 rows added, 0 removed** beyond the 132 dropped. So the filter moved nothing else. Pre-fix copies `scratch/dedup_ssy/PRE_*.csv`; probe/verify scripts `scratch/dedup_ssy/{probe,verify}.py`.
Also **41 orphan md/sidecar/chart files for the 14 dropped stems quarantined** to `scratch/dedup_ssy/quarantine/` (they would have let the same issue be ingested twice). Post md tier: 516 `.md` + 516 `.tables.json`, charts 510.

**KEEPER-CHOICE CONFIRMED ON ssy:** rich-ness (sidecar ROW count, never file size) is what saved the W39 Atlantic pair - the `ssy_2026_20260925-Atlantic` copy has a 12-row sidecar and its `ssy_28_09_2026_...` twin a 1-row STUB, so a blind lexicographic rule would have kept the stub. 13 of the 14 groups were row-count ties.

**REMAINING PENDING RE-RUNS (the rest of the census, unchanged):** fearnleys 121 rows, agora 94, star_asia 58, affinity 48, intermodal_finance 36. fearnleys is RECORD-ONLY (already ingested structurally) - lowest value. star_asia has FOUR more writers unpatched (`run_star_asia_charts.py`, `run_star_asia_ferrous_scrap.py`, `run_star_asia_price_trends.py`, `stack_unstacked_tables.stack_star_asia`) and affinity a second writer (`polish_affinity_markdown.py`, also writes `affinity_index_series.csv`) - patch BOTH enumeration AND stack before re-running those, or the filter changes nothing. carriers 327 is a parallel agent's - untouched. intermodal_finance is not just double-counted but STALE (last written 2026-09-28) with its parser fixed twice since, so re-running it changes VALUES, not just row count - verify against the pages.

**THIS RUN (2026-10-01 22:1x-22:3x) - ONE ITEM CLOSED AND PROVEN: the corpus-wide byte-duplicate double-count, source #1 advanced_shipping. Committed `527e6888a`, `543e91a05`, `a7618c051` on the current branch (`main` NOT touched). Evidence `docs/byte_duplicate_dedup_remaining_verdict.md`.**

**advanced_shipping FIXED: 148 duplicate rows removed (sales 44, secondhand 64, newbuilding 21, demolition 16, demo_sales 3), and the CONTROL PROVES nothing else moved** - `pre_rows minus rows of a dropped copy` is an EXACT multiset match against the post-fix file on all five series. Rebuilt with a new `--stack-only` mode (`run_advanced_shipping_tables.py`) that re-stacks the sidecars already on disk and never re-parses a PDF (2.9 s, 250 of 253 sidecars). Post counts: 6,061 / 8,046 / 1,888 / 2,000 / 601.

**NEW SHARED HELPER `scripts/extract/publishers/doc_dedup.py`** (plumbing only - each publisher still owns its pipeline). Two traps, both measured, both would have shipped wrong:
- The keeper must be chosen on CONTENT, not file size. The sidecar stamps its own filename into every row, so the `DD_MM_YYYY` collection-route name makes a byte-identical extraction look bigger and wins the tie-break on the WRONG copy - measured, it flipped the advanced_shipping keeper and produced a phantom 28-row delta.
- Lexicographic-first can keep a STUB sidecar: star_asia 2026 W38 is a 1,182-byte dict on one copy and a 29,127-byte list on the other; agora W38 88 bytes vs 13,524; ssy 2025-09-28 345 vs 2,746. Row-count richness keeps the real extraction in all three.
- For every duplicate pair checked the two sidecars differ ONLY in `stem`/`source_file`/filename-derived `issue_date` (fearnleys 09-10 vs 09-09, xclusiv 09-15 vs 09-14) - the VALUES are identical, so keeping either copy loses nothing.

**FALSIFIED THIS RUN - the state file's "intermodal likewise 36 -> 0" is WRONG.** `run_intermodal_finance.py` is a SEPARATE writer (macro / maritime_stocks / bunkers) that was never patched; those three series still carry **36** rows from the dropped W38 copy (macro 16, stocks 11, bunkers 9). Measured off the delivered CSVs. That file was last written 2026-09-28 22:28 and its parser has since been FIXED twice (ledger 4.3 macro signs, 4.4 issue_date), so it is BOTH double-counted and stale - re-running it will change values, not just drop rows, and must be verified against the pages.

**FILTER WIRED INTO SIX MORE RUNNERS, full re-run still pending** (each patched runner WAS executed and the filter path measured - 14/3/4/2/7/2 stems skipped): `run_ssy_complete.py` (132 rows), `run_fearnleys_normalized.py` (121), `run_agora.py` (94), `run_star_asia_tables.py` (58), `run_affinity_tables.py` (48), `run_intermodal_finance.py` (36). ssy/fearnleys/agora/star_asia build their series from PDFs in the SAME pass, so each needs a full re-run (~200-520 docs) - do ONE at a time.

**NOT YET PATCHED:** star_asia's other four writers (`run_star_asia_charts.py`, `run_star_asia_ferrous_scrap.py`, `run_star_asia_price_trends.py`, `stack_unstacked_tables.stack_star_asia`) and affinity's second writer (`polish_affinity_markdown.py`, which also writes `affinity_indices_series.csv`). `carriers` (327 rows) is a PARALLEL agent's - untouched.

**INCIDENT - CONCURRENT AGENTS, read before starting a heavy run.** At 22:19:16 a SECOND python process (`run_advanced_shipping_tables.py --sample`, PID 18956) wrote a 3-document sample over all five delivered advanced_shipping CSVs: sales **6,061 -> 74 rows**. Restored via `--stack-only` and verified byte-identical. A git process also held `.git/index.lock` (waited out; it merged origin/main), and a third process was reading the sales CSV with pandas. GUARD ADDED: `--sample` no longer writes series CSVs (control: re-ran `--sample`, all five md5-unchanged). IF YOU ARE THE OTHER AGENT: never run a publisher runner with `--sample`/`--file` against the delivered series directory.

**advshipping verification note:** `data/extracted/` is gitignored - the corrected CSVs are on DISK only; pre-fix copies in `scratch/dedup_20261001/`.

**THIS RUN (2026-10-01 20:3x-21:0x) - TWO ITEMS CLOSED. (1) HUMAN DECISION #1 executed: the decimal-comma fixes are now APPLIED to the delivered CSVs (191 rows corrected). (2) A bigger defect surfaced doing it - EVERY publisher was DOUBLE-COUNTING byte-duplicate documents. Committed on the current branch (`main` NOT touched). Evidence `docs/decimal_comma_regeneration_verdict.md`.**

**REGENERATED (offline, no API spend, no credits):** xclusiv `run_xclusiv_tables.py --all` (264 docs), clarksons
`run_clarksons_hellas_world_class.py` (165), intermodal `run_intermodal_full.py --reparse-only --year all` (255).
Measured corrections: **xclusiv sales 1 cell** (TANAIS FLYER 48.0 -> 4.8, page prints `4,8`); **clarksons snp_sales
7 cells** (EMILIA 139.0->13.9 `USD 13,9 M`, NORD POTOMAC 279->27.9, BULK SAO PAULO 7225->72.25, SEACON AFRICA
227->22.7, ILMA+INGRID 982->98.2, UOG OSLO 235->23.5); **intermodal**: `m_e` 2,755 rows (the engine column held
COMMENT text: `BWTS fitted`/`Eco`/`Scrubber fitted` -> `MAN-B&W`/`MAN B&W`/`Wartsila`), `comments` 1,723 rows
(it was EMPTY on all 3,358), `price_usd_m` 184 rows, `dwt` 89 rows (gas sub-table shift).

**VERIFIED AGAINST THE PAGES, NOT COUNTS.** Ground truth read by hand: intermodal 2021 W26 p3 prints
`DOUBLE PROVIDENCE | 95,720 | 2012 | IMABARI, Japan | MAN-B&W | Jan-22 | $ 21.3m | Greek | BWTS on order` - the old
CSV had `m_e="BWTS on order"`, the new has `m_e=MAN-B&W` + `comments=BWTS on order`. Reverse control: 1,723/1,733
(99.4%) of the moved `m_e` texts now sit in `comments`/`m_e`. Sample: 88/88 changed rows carry the new `m_e`
verbatim in their own PDF. Whole-series reconciliation (120 rows x every numeric column vs its own PDF text,
separators normalised): 14 of 16 intermodal series 120/120 (sales 118/120, currencies 118/120 - a re-draw found
no failing row, so the misses are my normaliser). tc_rates 150/150 on both rate columns. xclusiv_sales 120/120
vessel names verbatim. Idempotent: a second reparse+stack gives 0 md5 diffs.

**NEW DEFECT, FIXED - byte-duplicate documents were double-counted.** Accounting for a +10 row delta in
intermodal sales exposed it: a SECOND COLLECTION ROUTE re-drops the same weekly report under a different
filename. md5-measured: intermodal 257 PDFs / **255 unique** (2 dup groups), xclusiv 271 / **264 unique**
(7 groups), clarksons 9 / 8 (ALREADY dedupes by SHA256), banchero_costa 248 / 247. E.g.
`intermodal_2026_W39_*.pdf` == `intermodal_30_09_2026_*week_39*.pdf`, and
`xclusiv_2026_xclusiv-2026_09_14.pdf` == `xclusiv_15_09_2026_*14th_september_2026.pdf`. Both copies were parsed
and stacked; the existing row dedup keys on ALL columns INCLUDING `source_file`, so the copies never collapsed.
Impact: xclusiv_sales carried **113** duplicate rows; intermodal W38 AND W39 each double-counted (the register's
own `intermodal_sales 3,358` already included the pre-existing W38 duplicate).
FIX (per-source in each publisher's own runner): `byte_duplicate_stems()` keeps the lexicographically-first stem
of each md5 group and skips the rest - with `run_intermodal_full.py` filtering BOTH the reparse enumeration AND
the sidecar stack (else the skipped copy's stale sidecar re-adds its rows). Result: intermodal 257 -> **255 docs,
61,386 rows** (register 61,694 was inflated), 0 exact duplicates; xclusiv 271 -> **264 docs**, xclusiv_sales
5,815 -> **5,702**.

**XCLUSIV IS NOW FULLY CLEAN, not just the tables tier.** xclusiv has THREE more writers, all patched and
re-run this run: `run_xclusiv_vector_charts.py` (bulk_carrier_charts 216->208, demolition_charts 282->278),
`run_xclusiv_full_cover_to_cover.py` (macro_bunkers 667->643), `stack_unstacked_tables.py` (newbuilding_orders
1329->1313, newbuilding_prices 1397->1379). Rows attributable to duplicate stems across all 10 xclusiv series:
**127 -> 0**. intermodal likewise 36 -> 0.

**CORPUS-WIDE CENSUS - the same defect is in every broker publisher except lion: carriers 327 dup rows,
advanced_shipping 148, ssy 132, fearnleys 121, agora 94, star_asia 58, affinity 48, ism 0 (per-file detail in
`docs/decimal_comma_regeneration_verdict.md` section 7).** `run_advanced_shipping / run_star_asia /
run_affinity / run_agora / run_ism / run_fearnleys / run_ssy / run_carriers` enumerate with
`rglob("*.pdf")` and NONE dedupe; note affinity/agora are resumable (`_run_state.json`), so the filter must
be applied to BOTH the enumeration AND the stack or it changes nothing. carriers is a PARALLEL agent's - do
not touch without checking. THIS IS THE NEXT WORK ITEM.

**NOTE FOR THE NEXT RUN:** the series CSVs live under `data/extracted/` which is GITIGNORED - the corrected rows
are on DISK, not in git. `docs/EXTRACTION_REGISTER.md` per-file counts are now stale (and were themselves
pre-dedup inflated); regenerating that tracked doc is a whole-file rewrite and was deliberately NOT done.
`banchero_costa` has 1 duplicate pair but is blocked on LlamaParse credits (HTTP 402).

**THIS RUN (2026-10-01 19:0x-19:5x) - ONE ITEM CLOSED: the frontend data-integrity scanner's ONLY CRITICAL was the scanner's own instrument bug. Committed `7912be029` on the current branch (`main` NOT touched). Evidence `docs/frontend_integrity_scanner_verdict.md`.**

`scripts/check_frontend_data_integrity.py` ("exits non-zero if any CRITICAL finding exists. Designed for CI") regexes EVERY `safeFetch('data/... | knowledge/...')` target in index.html - 39 of them - and handed each one to `pd.read_csv`. Exactly ONE is not a CSV: `data/views/signals/cape_ffa_distribution.json` (fetched at `index.html:18683`, a real displayed view). Reading it as CSV gives `shape (0, 158)` - 0 rows, 158 pseudo-columns - which the tool reported as `DUPLICATE COLUMNS ['max:7634','min:-243']` + `ZERO DATA ROWS`. **The JSON is fine** (`json.load`: 6 top-level keys, all 12 months `count=18`). A red CI gate with no data behind it.

**FIX, two instrument bugs, one file.** (1) dispatch by suffix: `scan_csv` for `.csv`, new `scan_json` for `.json` (exists / non-empty / parses / payload non-empty). (2) `scan_csv` required a column named exactly `date`, so **3 of its own targets** were reported "no date column" and then skipped entirely - they spell it `Date` (measured on those 3: 0 unparseable dates, monotonic).

**MEASURED BEFORE -> AFTER:** 27 OK / 11 warnings / **2 critical** -> 31 OK / 8 warnings / **0 critical**, exit **1 -> 0**; targets validated 27 -> 31 (30 csv + 1 json).

**CONTROLS (scratch/ctl_scanner.py, 7 fixtures in a temp root):** duplicate columns, header-only, missing file, malformed JSON and empty `{}` JSON ALL still produce CRITICAL and exit 1; a good CSV and a good JSON pass. The fix masks nothing.

**ALSO MEASURED, no action taken (each recorded so the next run does not re-derive it):**
- `scripts/verify/audit_manifest_staleness.py`: **111 of 112 manifest entries agree**; the single stale one is `bunkers_bunker_prices_daily` (registry 1218 rows / end 2026-09-30 vs disk **1260 / 2026-10-01**). Regenerable via `scripts/verify/build_provenance_manifest.py`; NOT run (it rewrites the whole registry) and NOT hand-edited.
- `data/derived/held_data_catalog.json` (mtime 2026-09-30) is still stale (`rows 145 / end 2026-09-20` vs the file's **135 / 2026-09-24**) and has **NO builder anywhere in the repo** (only a prose mention in `scripts/extract/update_extraction_register.py`) and **no reader** (`index.html` does not reference it). Left alone.
- **THE STATE FILE'S OWN `run_ism.py` NOTE IS WRONG - do not "fix" it.** It said `main()` "defaults its doc list to `ROOT.rglob('*.pdf')` (every PDF in the repo)"; `run_ism.py:42` is `ROOT = Path('corpus/01-brokers/ism')`, scoped to the ism corpus folder, and it is the ONLY `ROOT.rglob` in the whole publishers directory. No code change made. (Falsified before acting - the same discipline that saved the poten "937 duplicate stub" hypothesis.)
- **13 of 18 cargo datasets are STALE by CONTENT, not by expectation** (`scripts/verify/check_data_freshness.py`, not wired into any workflow): `us_eia_weekly_crude_exports.csv` ends **2026-09-11** (a WEEKLY series, 20d lag), `newcastle_coal_exports.csv` ends **2026-07-01**. Last data commit from the Monday `upstream_commodity_flows.yml` chain is **2026-09-17** (`us_eia`) / 2026-08-25 (`newcastle`). NOT refreshed here: the EIA fetcher REQUIRES `EIA_API_KEY`, which is absent from this box's env and `.env` (CI secret). **CI run status is not visible from this box - recorded as a measured content lag, not as a confirmed workflow failure.**
- `data/views/signals/cape_ffa_distribution.json` (`generated_at 2026-09-10`, built by `scripts/acquire/build_signals_views.py`, **no workflow runs it**) is a 12-month percentile view over 2008-2026 spot history; its `as_of` lag is reported, not treated as a defect.

**THIS RUN (2026-10-01 18:2x-18:4x) - ONE ITEM CLOSED AND IT WAS LIVE: the ism chart tier was re-extracted TODAY at 13:06 (by commit c3e7f3337, the run_ism.py rewrite) and the shipped ism series no longer matched it. 837 published series points had silently changed value. Fixed, and the two series regenerated. Branch `auto/extract-fixes-2026-10-01-ism-tier-drift` (HEAD was `main`; `main` NOT touched). Evidence `docs/ism_tier_drift_verdict.md`.**

**THE DEFECT, measured.** The rewrite changed `resolve_ism_meta()` so the sidecar `date` became a `YYYY-01-01` PLACEHOLDER for the majority filename style (`ism_YYYY_Wnn_...`): **226 of 230** sidecars, shipped verbatim into the `.md` frontmatter as `issue_date: "2023-01-01"`. The stacker's `parse_doc_meta()` then failed its `date` regex and fell to the filename regex, which latches onto the TRAILING `weekNN` token and mis-derives the week for names where `Wnn != weekNN` (`ism_2025_W34_..._week35`). That moved each report's ISO date and hence which issue `pick_observation()` calls "nearest".

**IMPACT of running the shipped stacker against the re-extracted tier, unfixed:** handy 17,968 -> 18,016 rows and coaster 12,319 -> 12,529, with **633 handy + 204 coaster series points whose VALUE changed** - purely from metadata, no chart re-read differently.

**THE FIX (both parts):** `resolve_ism_meta()` now derives the ISO Monday from the known week (`date.fromisocalendar`); re-extracted **115/115** ism docs ($0, 0 failures), wrong `issue_date`s **226 -> 4** (the 4 are week-less holiday specials x2). `run_ism_series.parse_doc_meta()` now prefers the sidecar's own `year`/`week`; the chart glob dedupes by content (the extractor writes each sidecar to BOTH the flat dir and the year subdir - 230 files for 115 reports - which had doubled `n_reports`).

**VERIFIED: handy 17,968 rows, 0 keys added/removed and 0 VALUE changed vs the committed file** (only 611 `n_reports` corrected); **coaster 12,462 rows, +143 added, 0 removed, 0 value changed**. The +143 are the new **2026 W39** issue's `Wheat, 25-30,000 t, Constanta - EgyptMed` multi-year chart (values 11.2-23.0 inside its printed `10..30` axis, `verified=True`). Agreement gate: handy within-2% **74.1% -> 74.9%**, p90 11.76 -> 11.35; coaster unchanged. New shas: handy `c764bb00d778...`, coaster `07d32cd48132...`. NOTE: `data/extracted/` is gitignored, so the CSVs are disk-only; the pre-fix copies are kept at `scratch/ism_pretest/` and the pre-fix code at `scratch/ism_dup/*.bak`.

**THE LEDGER'S LAST OPEN ITEM IS RESOLVED:** the ism agreement tail is the PUBLISHER'S own axis-label shift between issues (already read and measured 2026-09-30); the only lever that is ours (choose the reading nearest the cluster median) was deliberately NOT applied, because `pick_observation()` prefers the week's own issue over older restatements and the median would report a value the publisher never printed that week.

**ADJACENT, not acted on:** `run_ism.py main()` defaults its doc list to `ROOT.rglob('*.pdf')` (every PDF in the repo) when `--docs` is omitted - a hazard for a manual run, does not affect the orchestrator which passes explicit paths.

**THIS RUN (2026-10-01 15:5x-16:5x) - ONE ITEM CLOSED, AND IT REOPENS POTEN: the poten knowledge tier has NO source root. `reports/poten` was deleted by the 2026-09-23 corpus migration (`b20829464`) and `process_knowledge.py` never adopted the canonical `GROUP_ROOTS["poten"] = corpus/04-poten`, so `iter_source_files('poten')` returns **0** files. Read-only; no data changed. Branch `auto/extract-fixes-2026-10-01-poten-kb-source` (HEAD was `main`; `main` NOT touched). Evidence `docs/poten_knowledge_source_stale_verdict.md`.**

**THE MEASUREMENT (module imported, control included):** `REPORTS_ROOT/poten` does not exist; `iter_source_files('poten')` -> **0**; `iter_source_files('baltic')` -> **187** (control - the function works); `GROUP_ROOTS['poten']` already -> `corpus/04-poten`. `git ls-files reports/poten` = **0**. The path is read in three places (registry count ~L1312, `paths` payload ~L1344, `iter_source_files` ~L1377).
**CONSEQUENCE:** a newly collected poten issue can be fetched and extracted and will STILL never enter `knowledge/`. The poten `SyntaxError` repair (main `48b45e9f6`) is necessary but not sufficient.
**WHAT THE FROZEN TIER HOLDS:** `documents.jsonl` 10,202 rows, **1,096 poten rows, all 1,096 `source_path`s under the deleted `reports/poten/`** - 937 thin metadata md (`date: unknown-01-01`), 159 dated, 545 rows `date: null`. `sources.json` still claims poten 1096 at `reports/poten`. User-visible symptom already on record: `knowledge/chunks/poten_tankers_2030.jsonl` (the 2030 mis-dated stub).

**FALSIFIED BEFORE ACTING - the corpus is NOT duplicated, the mirror is by design.** Census (`data/extracted/audit/poten_corpus_md_census.json`): corpus/04-poten md **2,183** = **1,096** metadata md (frontmatter has `pdf_file:`; 937 stub-shaped + 159 dated) + **1,087** md **byte-identical** to `data/extracted/md/poten/` (0 unexplained). `2,183 - 1,087 = 1,096` = the migration's own md count. The 1,087 copies are written deliberately: `run_poten_clean.py` syncs every extracted opinion to BOTH `data/extracted/md/poten/<year>/` and `corpus/04-poten/<year>/`. **Nothing to delete** (a 937-file "duplicate stub" hypothesis was killed here, at zero cost).

**PRUNING - measured, NOT reproducible, do not act.** Simulating `prune_missing_sources()` over the current manifest removes **8,999 / 10,202 rows** (incl. all 1,096 poten), because their `source_path` is gone. But 8 days of nightly `knowledge: update` since the migration removed **none** of them (2026-09-29 commit: documents.jsonl **+4 / -0**; `HEAD` == working tree). The path that should have pruned did not fire; cause NOT established. Reported as *not reproducible*, not as a live hazard.

**THE FIX IS APPLIED ON THE BRANCH (both parts, controlled):** `is_poten_metadata_md()` added; the three poten reads now use `GROUP_ROOTS["poten"]` and select the metadata generation. CONTROL (pre-patch copy kept): `iter_source_files('poten')` **0 -> 1,096**, every other source UNCHANGED (baltic 187, breakwave_insights 505, hellenic 514, broker_reports 180); py_compile OK on 3.11 AND 3.14; the 1,096 basenames yielded are an EXACT match for the 1,096 poten `source_path` basenames already in `documents.jsonl` (0 added, 0 lost, 0 of the 1,087 mirrored md yielded). Tier NOT rebuilt - no data changed. ORIGINAL FRAMING BELOW: (1) repoint the three poten reads to `GROUP_ROOTS["poten"]`; (2) the read must select ONE md generation, because `corpus/04-poten` holds BOTH sets - reading the whole dir would inject 1,087 duplicate documents into the RAG. Adjacent, out of scope: `iter_source_files('baltic')` yields **187** while the tier holds 2,036 baltic rows, so tier and source roots have drifted generally.

**SAME RUN, SECOND ITEM: the freshly published `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` (14:46) does not reproduce.** Evidence `docs/corpus_registry_audit_verification.md`. Read-only; enumerate the filesystem, never re-read the doc's numbers.
- COVERAGE VERIFIED: no corpus group has zero md output (md counts per publisher recorded in the doc).
- HEADLINE FORMAT INVENTORY FAILS: doc says **6,639 PDFs**; measured **13,989** in `corpus/` (**2.1x LOW**). Doc says 9,678 HTML; measured 10,007 (close). Doc says 26,451 JPG/PNG; measured 26,274 (close). Doc says 18,290 md; measured **9,599** in `corpus/`, **17,723** under `data/extracted/md` - matches neither. Doc says "over 54,000 documents"; measured **60,351** files in `corpus/`. No obvious sub-population lands on 6,639 (excl. 02-hellenic = 5,985; excl. 02-hellenic+archive = 5,261). A content-dedupe hypothesis was **NOT** tested (would need 14k hashes) - reported as *not reproducible*, not as *wrong by X*.
- CLARKSONS ROW IS WRONG ON LOCATION: the row quotes "180 PDF" against `corpus/01-brokers/clarksons`, which holds **9 PDFs** (all 2026/). 180 is the md count in `data/extracted/md/clarksons`. The history is filed elsewhere: **345 clarkson-named PDFs corpus-wide, 168 under `corpus/02-hellenic/shipbuilding/pdfs/`**. Its latest-issue date **2026-09-25 IS correct** (`clarksons_2026_Weekly-Sales-25th-Sept-2026.pdf` on disk).
- TRAP HIT, REPORT IT: a filename-only latest-date sweep under-reports any source whose filename uses an ORDINAL MONTH (`25th-Sept-2026` matched nothing), and it flagged clarksons/lion/star_asia/fearnleys-md as behind. Those are MY parser, not the sources - do not act on them.

**THIS RUN (2026-10-01 15:0x) - ONE ITEM CLOSED: the drewry WCI "two wildcard URL patterns were never checked" item. They hold NOTHING recoverable; the era gap is now measured off the ARCHIVE'S OWN capture list, not inferred. Read-only run - no fetch, no data change; displayed series stays 135 rows.** Evidence `docs/drewry_wci_wildcard_gap_verdict.md`.

**CDX IS STILL OFFLINE.** `web.archive.org/cdx/search/cdx` returns the `Internet Archive: Temporarily Offline` HTML body, while `/wayback/available`, a snapshot fetch and `/web/timemap/json/<exact url>` all return 200. So the patterns cannot be enumerated as patterns; they were closed by enumerating every plausible EXACT url with the timemap and comparing capture sets.

**THE CANDIDATES (timemap, status-200 only).** `http://` / no-`www` / trailing-slash forms of the WCI url each return the IDENTICAL **1,053-capture / 252-week** set (scheme/host normalisation) - zero new content. The one genuinely different path, `.../supply-chain-expertise/world-container-index` (the shortest form `*world-container-index*` would also match), holds **4 captures in ONE ISO week and ZERO in any week we lack**. `.../container-index` and `/world-container-index-assessed-by-drewry` do not exist in the archive. **Verdict: nothing to fetch from either wildcard pattern.**

**THE ERA GAP, re-measured on the archive's own list** (1,053 timemap rows, 1,033 status-200, 2017-06-16..2026-09-27). For each of the **280 era Thursdays** (2021-05-20..2026-09-24), is there a capture AFTER that day's print (window `(Thu 12:00, +7d]` - a Mon-Wed capture holds the PREVIOUS week's assessment)? **224 have one; 56 do not**; 53 of the 56 have no capture anywhere. **5 Thursdays have a post-publication capture but no print in the checkpoint, and all 5 are HOLIDAY WEEKS where the archived page ITSELF still prints the PRIOR Thursday:** 2021-12-30 (captures print "*Thursday, 23 December 2021*"), 2023-12-28 ("*21 December 2023*"), 2024-12-26 ("*19 December 2024*"), 2025-12-18 and 2026-01-01 (both print "*Thursday, 25 Dec 2025*" - the NEXT print, not the week's). So there is no print to recover; nothing was dropped by the parser or the gate.

**REMAINING, archive-side and unfixable for this URL:** 56 era Thursdays with no post-publication capture (53 with no capture at all). `corpus/06-drewry/opinions/` holds only 5 WCI `.md` files (2026-08-20..2026-09-24), so there is no corpus-side path either. Reproduce: `scratch/wci/{wildcard_probe,era_gap_measure,five_gap}.py`.

**VERIFIED this run (unchanged):** `data/indices/drewry_wci_historical.csv` = **135 rows**, 2021-05-20..2026-09-24, **all Thursdays**, 0 duplicate dates, **0 blank cells in the five core lanes**, 63 blank `rotterdam_shanghai` (the publisher's own blanks); `manifest.json` `indices_drewry_wci_historical.row_count` = **135**.

**THIS RUN (2026-10-01 13:1x-14:0x) - ONE ITEM CLOSED AND IT WAS BIG: the drewry WCI backfill was NEVER TAKING THE WEEK'S OWN PRINT. Displayed series 121 -> 135 rows (14 added, 0 cell corrections). Branch `auto/extract-fixes-2026-10-01-wci-postthu`. Evidence `docs/drewry_wci_postthursday_verdict.md`.**

**THE DEFECT, SEEN BY EYE (not by a metric).** `one_per_week()` in `backfill_wci_history.py` keeps the EARLIEST capture of each ISO week. The WCI print is published ON Thursday, so a Mon-Wed capture prints the PREVIOUS week's assessment and the week's OWN print - which the archive holds - was never fetched. Control, 2022-W02: `20220112103127` (the capture that WAS taken) prints "assessment for Thursday, 6 January 2022"; `20220114134343` (never fetched) prints "Thursday, 13 January 2022". This is also the real explanation of the earlier "90 incomplete captures".

**THE PREVIOUS RUN'S START-HERE ITEM IS CLOSED: CDX IS OFFLINE, THE TIMEMAP IS NOT.** `web.archive.org/cdx/search/cdx` returns **HTTP 503 "Internet Archive: Temporarily Offline"** for every pattern, while `/wayback/available`, a snapshot fetch, `archive.org/` and **`/web/timemap/json/<exact url>`** all return 200. The timemap gives the DEFINITIVE capture list for the exact URL: **1,053 rows, 1,033 status-200, 252 ISO weeks, 2017-06-16..2026-09-27**. Against the checkpoint: **23 timemap weeks are absent and ALL are 2017-2020 - ZERO in the displayed era**; of the era's 280 Thursdays, 187 had a page_date, 93 did not, and **60 of those 93 sit in an ISO week the archive DOES hold**.

**SHIPPED (measured).** (1) `candidates()` - the earliest capture of each week PLUS the earliest capture in `(that week's Thursday 12:00, +7d]`, the one that carries the week's own print: **231 -> 384 snapshots**. (2) **pv18 STABILITY GUARD** in `fetch_drewry_wci.extract_assessments()` - a lane the page prints as "remained stable" (no level, no `$`) is no longer handed ANOTHER lane's level; fires only when EVERY mention of that lane is a stability mention with no `$` in its clause, so "remained stable at $6,818" is untouched. CONTROL over all **274** cached pages, old vs new module: **0 errors, exactly 2 values moved** - `2024-12-05 shanghai_ny 2649 -> None` (`2,649` is printed ONCE on that page and belongs to Rotterdam-New York; the page prints NO level for Shanghai-New York) and `2025-03-06 shanghai_genoa 845 -> None` (the known "845 is NY-Rotterdam's level" case). `--fetch --refresh`: **384 snapshots, 226 complete prints, 15 fetch failures (WinError 10061, resumable), 0 parser errors**. `--stack --era-from 2021-01-01`: staged **120 -> 135**, census `{"snapshots":384,"fetch_failed":15,"incomplete":143,"numeric":1}` (the single `numeric` rejection is the 2024-12-05 print, now correctly 4-of-5 instead of 5-of-5 with one WRONG lane).
**VERIFIED:** the 15 new rows' every value appears **inside its own lane's clause** on its own archived page (15 clean, 0 misassigned, 0 without page text; 12 also read by eye; all 15 composites printed verbatim). `merge_display.py --apply`: **0 CELL CORRECTIONS, 14 ROWS ADDED**, md-tier untouched, `2026-08-27` skipped as same-week as an md print; display diff = **exactly 14 added lines, 0 removed**; **135 rows, dates unique/strictly increasing/all Thursdays, 0 blank core cells, 63 blank `rotterdam_shanghai`**; `pytest tests/test_drewry_wci_contract.py tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **38 passed**; `manifest.json` regenerated AFTER pytest, `row_count` **121 -> 135**.

**STILL OPEN (measured):** 15 snapshots failed to fetch (WinError 10061) - a later `--refresh` retries them; **33 era Thursdays have NO archived capture in their week and 17 more only pre-Thursday captures** (archive-side, unfixable by any parser change for this URL); the two wildcard URL patterns remain unchecked because CDX is offline and the timemap only enumerates an exact URL.
**NOTE, measured:** the repo's OWN automation committed the two patched scrapers to **main** as `f6a980a71` (`git add -A` + commit + `pull --rebase origin main`) before this run could branch; the DATA changes are on the side branch. Nothing pushed, no merge.

---

**THIS RUN (2026-10-01 12:3x) - ONE ITEM CLOSED: the drewry WCI "90 incomplete captures" are the PUBLISHER'S OWN BLANKS, verified by reading all 90 pages. No data was rewritten; one guard shipped.** Branch `auto/extract-fixes-2026-10-01-wci-incomplete` (HEAD was `main`; `main` NOT touched).

**THE ITEM.** The ledger carried "90 incomplete captures by year 2021:30 2022:19 2023:21 2024:11 2025:9" as the suspicion that the parser drops lane levels the publisher printed. IT DOES NOT. Every one of the **203 missing lane-slots** across the 90 captures was read against that capture's OWN page (all 231 bodies are cached locally in `scratch/wci/raw/`, 18 MB - the audit was offline and read-only; nothing re-fetched).
CLASSIFICATION: **138 STABLE_BLANK** (the sentence says `remain(ed) stable` / `hovered around previous weeks level` / `declined 1% each` - no level), **14 NAMED_NO_VALUE** (the lane is named with a % but no `$` in its sentence), **51 UNNAMED** (the lane is not named in the assessment paragraph), **0 HAS_VALUE**.
WHOLE-PAGE CONTROL (not just the paragraph): a `$` within 140 chars after a lane mention anywhere on the page gave **4 hits, all FALSE POSITIVES** - in each the `$` belongs to a following clause naming a DIFFERENT lane: `2021-09-09 shanghai_ny` ("...grew 1% each ... **However, rates from Rotterdam to Shanghai dropped 1% or $21 to $1,626**"), `2021-10-14 shanghai_genoa/rotterdam_shanghai` ("**...nudged up by 3% or $38**").
**8 captures record no lane level at all**: 4 are PARTIAL Wayback bodies (only the headline + the composite `$`, no narrative: 2021-01-21, 2021-02-11, 2021-03-18, 2021-04-15); the other 4 ARE full prints that state no level (`2022-05-19`: "...Shanghai - Rotterdam, Rotterdam - Shanghai, ... hovered around previous weeks level").

**(B) THE 59 BLANK `rotterdam_shanghai` CELLS IN THE SHIPPED CSV ARE ALSO FAITHFUL.** `data/indices/drewry_wci_historical.csv` (121 rows) is blank on that lane for 59 rows, 2021-06-24..2026-09-24: **20 named with no level, 38 not named, 1 capture date not cached, 0 with a printed level**. The five OTHER lanes are blank on **0** rows. That is why the new contract test exempts this lane from the no-blank rule.

**(C) CONTINUITY OF THE ERA, measured against the population it covers** (280 Thursdays, 2021-05-20..2026-09-24): **121 displayed** + **67 a capture IS held for but the print is withheld** (2021:20 2022:16 2023:15 2024:9 2025:7) + **92 no Wayback capture at all** (2021:7 2022:16 2023:18 2024:15 2025:21 2026:15). The 92 are an ARCHIVE-side gap: no parser change can fill them, and `corpus/06-drewry/opinions/` holds only 5 WCI `.md` files (2026-08-20..2026-09-24), so there is no corpus-side backfill path either.

**(D) SHIPPED (code + test only).** `scripts/scrapers/fetch_drewry_wci.py` `upsert_wci_rows()` deduped by DATE alone (last row wins), so a misparsed date could overwrite a real print with no trace. It now REPORTS every merge: rows in/out, how many the date dedupe discarded, which dates had a **stored value replaced** (with before -> after), and any date that is **not a Thursday** (the index is assessed on Thursdays). Printed as `[wci-upsert]` lines and kept in module-level `UPSERT_REPORT`.
CONTROLS (temp copy; the real CSV sha256 `de1aeea74e5503a5...` was IDENTICAL before and after): re-upsert of the file's own 121 rows = 242 in -> 121 out, 121 discarded, **0 shadowed, 0 non-Thursday, output byte-identical**; a mutated stored value (`2026-09-24 shanghai_la 7838 -> 7949`) = reported with both values; a non-Thursday date (`2021-05-21`) = reported.
NEW TEST `tests/test_drewry_wci_contract.py` (4 tests: canonical header, every date a Thursday, dates unique + strictly increasing, the five core lanes never blank). `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py tests/test_drewry_wci_contract.py` = **38 passed** (Python 3.12).
Evidence **`docs/drewry_wci_incomplete_verdict.md`**. Reproduce: `scratch/wci/{read_incomplete,classify3,incomplete_verdict,rs_blank,continuity,ctl_upsert}.py`.

**ONE BOUNDED ARCHIVE-SIDE CHECK LEFT (start here next run).** A year-scoped CDX query on the tool's own pattern (`...world-container-index-assessed-by-drewry*`, 2021) returns **125 snapshots over 36 ISO weeks** and the checkpoint holds **the same 36 weeks - 0 archived weeks missing**; the 89 extra timestamps are duplicate captures inside weeks we already have (`one_per_week()` keeps the earliest). The OTHER two patterns (`*world-container-index*`, `*container-index*`) were never checked - every attempt returned **HTTP 503** (archive.org throttles wide queries today; year-scoped ones work). If they hold captures in the 92 never-archived weeks, `scripts/scrapers/backfill_wci_history.py --fetch` (resumable, caches to `scratch/wci/raw/`) already knows how to take them.

**STALE POINTERS, do not act on them:** the cron prompt still says xclusiv is IN PROGRESS and lists the fearnleys/intermodal/affinity/banchero/agora/carriers/ism/lion ladder - xclusiv is **266/266 DONE** and every broker source is CLOSED (`docs/EXTRACTION_REGISTER.md`). The prompt's "commit on benchmark/extraction-comparison" is also stale: HEAD was `main` and `main` was not committed to.


**THIS RUN (2026-10-01 11:3x-12:1x) - ONE ITEM CLOSED: the drewry WCI TWO-PARALLEL-`respectively`-LISTS shape is recovered and SHIPPED, displayed 120 -> 121 rows; and a measured trap about the provenance manifest is recorded. Branch `auto/extract-fixes-2026-10-01-wci-pv17` (HEAD was `main` and `main` was NOT committed to).**

**(A) pv17 - the double-`respectively` sentence.** `2024-12-19`: *"rates from Shanghai to Genoa and Rotterdam to Shanghai decreased 2% to $5,424 per feu and $508 per feu, respectively, and those from New York to Rotterdam and Shanghai to Rotterdam shrank 1% to $824 per feu and $4,819 per feu, respectively, whereas those from Los Angeles to Shanghai remained stable."* The parser handed each lane its own list's FIRST value - `rotterdam_shanghai 5424` (should be **508**), `shanghai_rotterdam 824` (should be **4,819**) - so the four tracked lanes read `5424/5424/4499/824`, the numeric spread gate (max/min>5) correctly rejected the print, and it never reached the display. THE RULE: each `respectively` CLOSES a list, so the ordinal mapping is scoped to the part BEFORE that marker; the part after the LAST marker is a tail and is ignored; a part maps its labels (tracked OR untracked - dropping an untracked lane shifts every ordinal) to its own values positionally, and it fires ONLY when the pool logic found nothing (`vals is None`), filling EMPTY columns only. `PARSER_VERSION` 16 -> 17.
CONTROLS: read-only trial over all 231 cached captures = **231 parsed, 0 parser errors, exactly 4 values moved**, all on the 2 snapshots of that one print (`shanghai_rotterdam 824 -> 4819`, `rotterdam_shanghai 5424 -> 508`), **227 pages byte-identical**; re-run against the module now on disk vs the pre-patch backup = identical result. Re-parse `--fetch --refresh`: 231 snapshots re-parsed **from the local cache**, 141 complete, 0 network fetches, 29 s. `--stack --era-from 2021-01-01`: staged **119 -> 120** prints, census `numeric 3 -> 1` (the remaining one is 2025-03-06, the publisher's own blank), stage diff = **exactly 1 added line**. `merge_display.py --apply`: displayed **120 -> 121**, **CELL CORRECTIONS 0**, ROWS ADDED 1, md-tier untouched, file diff = **exactly 1 added line**, and only `rotterdam_shanghai` body changed relative to the pre-fix parse of that same print. VERIFIED: 121 rows, dates unique/strictly increasing/**all Thursdays** (2021-05-20 .. 2026-09-24), **0 blank cells in the five core lanes**, 0 duplicate value-groups; `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** (Python312). Evidence `docs/drewry_wci_pv17_verdict.md`.

**(B) MEASURED TRAP - the repo's `conftest` RESTORES `data/provenance/manifest.json` FROM GIT at the end of a test run** (`[conftest] restored 1 data file(s) and removed 0 created by tests`). A manifest regeneration done BEFORE pytest is silently discarded, and `git diff` then shows nothing while the builder reported success - a run can believe it regenerated the manifest and ship a stale one. Fix the ORDER: regenerate AFTER the tests and verify `row_count` on disk. Done here: `indices_drewry_wci_historical` `row_count` **120 -> 121** (5 lines changed in the whole manifest, 3 of them unrelated disk measurements: `generated_at`, an `ffa_live` tick).
**STALE POINTER, do not act on it:** the cron prompt still describes xclusiv as IN PROGRESS and lists the fearnleys/intermodal/affinity/banchero/agora/carriers/ism/lion ladder - xclusiv is **266/266 DONE** and every broker source is CLOSED (`docs/EXTRACTION_REGISTER.md`); a fresh count here is `find data/extracted/md/xclusiv -name '*.md' | wc -l` = **271** (266 docs + 5 control/duplicate-named files laid out by year, 2021:23 2022:51 2023:50 2024:51 2025:51 2026:45).

**(C) REPO-WIDE 3.11 SWEEP FOUND A SYNTAX-BROKEN PUBLISHER RUNNER ON HEAD, AND IT IS FIXED.** A compile sweep over every tracked `scripts/**/*.py` with the Actions runner interpreter (Python 3.11 - the PEP-701 class that killed poten for three weeks) reported **1 of 359 failed**: `scripts/extract/publishers/run_hellenic_iron_ore_pdf.py` - `IndentationError: expected an indented block after 'if' statement on line 2232`, on **3.11 AND 3.14 alike**, so the module could not be imported or run at all. Cause: commit `6c01a5ce7` (smm-iron-ore, today 11:15) inserted its new single-page early-branch into `process_single_mmi_sync()` at the WRONG INDENTATION, on top of the `if ( ... ):` body, deleting both the body and its `try/except` - the `if` was left with no statement. FIX = the 4 clobbered lines restored (`return {"status": "skipped", ...}` + `except Exception:` + `pass`) with the new SMM early-branch kept where the commit wanted it: `git diff` = **4 added lines, 0 removed**. CONTROLS: py_compile 3.11 OK / 3.14 OK; repo-wide sweeps now **359 compiled / 0 failed on BOTH 3.11 and 3.14** (was 358/1); the only importers are two gitignored `scratch/test_*.py`, so this broke the runner itself, not a scheduled job. Evidence `docs/hellenic_runner_syntax_verdict.md`.
NOTE ON BRANCHES, measured: this repo's own automation committed the pv17 code/data to **main** itself (as `843865c11`) and switched the working tree back to `main` mid-run; a side branch `auto/extract-fixes-2026-10-01-wci-pv17` holds an earlier copy of the same two commits. Nothing was pushed and no merge was performed.

**STILL OPEN (drewry WCI), measured from the checkpoint:** (1) **1 numeric-gated print** - **2025-03-06** is a genuine publisher-blank (*"rates from Shanghai to Genoa and Los Angeles to Shanghai remained stable"*), correctly withheld; (2) **90 incomplete captures** by year `2021:30 2022:19 2023:21 2024:11 2025:9` (2026 has none left); (3) `upsert_wci_rows()` still dedupes by date only (a Thursday assertion there would stop a dropped print from reappearing silently).

**THIS RUN (2026-10-01 10:2x-11:0x) - ONE ITEM CLOSED, ONE FETCH RECOVERED: drewry WCI pv16, displayed 118 -> 120. Branch `auto/extract-fixes-2026-09-30-wci-pv15`, `main` NOT touched (it was at `origin/main` when this run started - the prompt's "commit on benchmark/extraction-comparison" is stale).**

**THE DEFECT: a LEVEL printed with NO dollar sign.** `20240722012524.html` (2024-07-18) prints *"...rates from Shanghai to Los Angeles fell 3% or $224 to **7,288** per 40ft box."* `value_rx` requires a `$`, so 7,288 was never a candidate and the lane took the **$224 CHANGE** - the numeric gate then correctly rejected the print, so it never reached the display. THE RULE (pv16, additive): a bare number joins the candidates only when the level introducer (`to|at|reach|touch|a new high|low of`) ends immediately before it, a price unit follows, and it has a thousands comma or >=4 digits. `PARSER_VERSION` 15 -> 16.
**TRAP HIT WHILE BUILDING IT, REPORT IT:** the first trial measured **0 differences**. Cause: `\b` written in a NON-raw outer string became a literal **0x08 BACKSPACE** in the generated module, so the unit guard matched nothing - the SAME trap `COMPOSITE_AVG_RX` already carries a comment about in this file. Fix: boundaries inside an r-string + an `assert '\x08' not in src` in the patch. A no-op detector reads exactly like a publisher-side gap.
CONTROLS: read-only trial, all 230 cached captures in process, nothing written - **230 parsed, 0 parser errors, exactly 1 value moved** (`2024-07-18 shanghai_la 224.0 -> 7288.0`), 229/230 unchanged; the value read verbatim off its own page. Then `--fetch --refresh` (231 snaps, 230 from the local cache) -> `--stack --era-from 2021-01-01`: staged **118 -> 119**, census `numeric 4 -> 3`, stage diff = exactly 2 added lines. `merge_display.py --apply`: displayed **118 -> 120**, **CELL CORRECTIONS 0**, ROWS ADDED 2, md-tier untouched, file diff = **exactly 2 added lines**. VERIFIED: 120 rows, dates unique/strictly increasing/**all Thursdays**, 2021-05-20 .. 2026-09-24, **0 blank core cells, 0 duplicate value-groups**; `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** (Python312). Evidence `docs/drewry_wci_pv16_verdict.md`, commits `82f65ee48` (code) + `22c6da39a` (data).

**THE `fetch_failed: 1` IS NOW 0 - the capture `20251006233302` FETCHED.** It had 404d on every previous run; this run it returned 115,772 bytes of valid HTML and parsed a complete print for **2025-10-02**, whose five values are printed verbatim on that page ("...assessment for Thursday, 02 Oct 2025. The WCI fell 5% to $1,669 ... Shanghai to Los Angeles decreased 5% to $2,196 ... Shanghai to New York decreased 2% to $3,200 ... declined 7% ($1,613) on Shanghai-Rotterdam and 9% ($1,804) on Shanghai-Genoa"). It sits between the shipped 2025-09-25 and 2025-10-23.

**`data/provenance/manifest.json` REGENERATED** with the repo builder (never hand-edited): `indices_drewry_wci_historical` `row_count` **117 -> 120**. The regeneration also picked up **32 further measured fields** from OTHER pipelines whose files advanced since the last regen (lpg charter/spot, tanker forward curves, time charter rates, ffa_live, ...) - disk measurements, not hand edits.

**STILL OPEN (drewry WCI), measured from the checkpoint:** (1) **3 numeric-gated prints**, all with the level ON the page - **2024-12-19** (two snapshots) is the TWO-PARALLEL-`respectively`-LISTS shape (*"...Shanghai to Genoa and Rotterdam to Shanghai decreased 2% to $5,424 ... and $508 ..., respectively, and those from New York to Rotterdam and Shanghai to Rotterdam shrank 1% to $824 ... and $4,819 ..., respectively"* -> parser gave rotterdam_shanghai 5,424 (should be 508) and shanghai_rotterdam 824 (should be 4,819): each lane got its own list's FIRST value); **2025-03-06** is a genuine publisher-blank (genoa *"remained stable"*) correctly withheld - the parser's 845 is New York->Rotterdam's level. (2) **90 incomplete captures** by year `2021:30 2022:19 2023:21 2024:11 2025:9`. (3) `upsert_wci_rows()` still dedupes by date only.

**STALE POINTERS, do not act on them:** every broker source is CLOSED (`docs/EXTRACTION_REGISTER.md`); xclusiv is 266/266 DONE; the cron prompt's "next source" ladder (fearnleys/intermodal/affinity/banchero/agora/carriers/ism/lion) is built.

**THIS RUN (2026-09-30 21:2x) - TWO ITEMS CLOSED. (A) drewry WCI pv15: the LAST named lane shape is recovered and SHIPPED, displayed 117 -> 118 rows; (B) the poten step's `|| true` is replaced by a real assertion so a zero can never pass silently again. Branch `auto/extract-fixes-2026-09-30-wci-pv15`, 4 commits; `main` was NOT touched (the tree was clean and at `origin/main` when this run started, so the prompt's "commit on benchmark/extraction-comparison" no longer matches the repo).**

**(A) pv15 - the ORIGIN-INFERENCE lane recovery (`2026-02-12`).** The page prints *"Spot rates from Shanghai to major US destinations declined slightly due to low cargo volume, with spot rates to Los Angeles and New York falling 1% to $2,214 and $2,800 per 40ft container, respectively."* - exactly the sentence that made this an open item. MEASURED on it: `ROUTE_PATTERNS` matches NOTHING (its opening "destination" is the lowercase group phrase "major US destinations", not a capitalised port pair) and `label_rx` matches NOTHING either, so the sentence never entered the lane logic, BOTH printed levels were dropped while composite 1,933 / Rotterdam 2,127 / Genoa 2,965 parsed fine, and the print failed the `complete` gate - sitting among the 91 withheld captures. THE RULE: an origin printed in the sentence's OPENING lane (the module's own `elided_rx`, "rates **from Shanghai**") now seeds the destination list. It runs only when the sentence says "respectively", names no route and matches no ROUTE_PATTERN, and it fills EMPTY columns only - it cannot move or overwrite an assignment. `PARSER_VERSION` 14 -> 15.
CONTROLS, each measured separately: read-only trial over all 230 cached captures = **230 parsed, 0 parser errors, 2 value differences, both `None -> value` on that one page**; then through the real checkpoint, 230 snapshots present under both pv14 and pv15 with **exactly 1 moved**, the moved record `(1933, 2127, 2965, None, None, None) -> (1933, 2127, 2965, 2214, 2800, None)` - no value changed, no page_date changed; stage **116 -> 117 prints, incomplete 91 -> 90**; display merge **0 cell corrections, 1 row added**, md-tier (>= 2026-08-01) untouched, diff = exactly one added line; displayed file dates unique, strictly increasing, **all Thursdays** (2021-05-20 .. 2026-09-24), 0 blank core cells, 0 duplicate value-groups; all five values of the new row verbatim as `$X,XXX` on its own page (which prints "Thursday, 12 Feb 2026" and headline `$1,933`); `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** (use Python312 - Python314 has no pytest). Evidence **`docs/drewry_wci_pv15_verdict.md`**.
DISPLAY PATH PROBED headlessly (http.server + Playwright/Chromium on the app's own index.html?test=1, driving its own window.loadSignalsData): the app fetches the CSV **HTTP 200** and DATA.drewry_wci holds **118** rows, the recovered row exactly as printed. FINDING, measured: nothing in index.html READS DATA.drewry_wci - window.renderDrewryChart is an alias of the CLCI/FBX chart - so this series reaches the user through **scripts/generate_brief.py** section 10a (it reads the file's LAST row), not through a chart. Adding a row is correct but is not pixel-visible in the current UI.
FRESH CENSUS: incomplete **90**, by print year `2021:30 2022:19 2023:21 2024:11 2025:9` - **2026 now has none left**; missing-lane histogram in the verdict. NOTE: the previous verdict's histogram summed to 97 against its own census of 91; the numbers now printed are recomputed from `checkpoint.jsonl`.

**(B) poten - the silent-zero class is closed at the workflow.** `python scripts/scrapers/fetch_poten_direct.py || true` is gone: the step now captures the exit code and the whole crawl log, and a new final step (`if: always()`) FAILS the job unless `Found [1-9][0-9]* articles on page 1` appears and `Total in catalog: 0` does not - so the three measured failure modes that all looked like success (poten.com HTTP 403, an empty listing parse, and the 3.11 SyntaxError that killed the module before it ran, 2026-08-29..2026-09-30) are now loud. The assertion is placed AFTER the commit step on purpose, so a poten outage cannot block the drewry commits. VERIFIED: YAML parses (8 steps); the discriminating grep was executed against synthetic logs for all four cases (healthy PASS; 0-articles FAIL; 403 FAIL; SyntaxError FAIL) and the empty-catalog gate fires on its own.

**STALE POINTERS, do not act on them:** the cron prompt still describes xclusiv as IN PROGRESS and lists a "next source" ladder (fearnleys/intermodal/affinity/banchero/agora/carriers/ism/lion) - xclusiv is **266/266 DONE** and every broker source is CLOSED (`docs/EXTRACTION_REGISTER.md`); `data/provenance/manifest.json` was regenerated on 2026-09-30 (commit `53c03d335`) and is no longer stale.
**STILL OPEN (drewry WCI):** the 4 numeric-gated prints, the 1 never-fetched capture (`20251006233302`, HTTP 404), the 2021-07-01 "k labels, 2k numbers" print, and `upsert_wci_rows()`'s date-only dedupe (a Thursday assertion there would stop a dropped print from reappearing silently). The 90 incomplete captures are mostly the publisher printing no number (`2025-06-12` was READ: it prints no LA level).

**THIS RUN (2026-09-30 15:3x - 17:4x) - TWO CLOSED ITEMS. (A) the drewry WCI MD TIER is repaired; (B) the ELIDED-SECOND-LANE parser shapes are recovered and SHIPPED: displayed WCI rows 105 -> 117, 0 previously displayed rows changed.**

**(B) is the bigger one. Three lane-list shapes were invisible to `extract_assessments`, so the second lane's level was silently DROPPED while every recall check passed (the value IS on the page). PARSER_VERSION 11 -> 14, each step on its own control:**
* **pv12** - a BARE PORT after a conjunction: "rates from Shanghai to New York **and Los Angeles** increasing 9% to $9,507 and $6,802 respectively" (2026-08-20). The continuation is taken only IMMEDIATELY after a label and never when the captured words are a new pair's origin ("...and Shanghai to Rotterdam" keeps its own label); the second lane's column is DERIVED from ROUTE_PATTERNS by reconstructing "<origin> to <dest>". CONTROL: 230 cached pages re-parsed - 220 unchanged, **10 moved, all 10 `None -> value`** (no value changed, none lost).
* **pv13** - the origin elided as "**rates to <port>**" (2025-11-27). Implemented as a MONOTONE fallback that runs after the sentence's own logic and fills only a lane still EMPTY, so it can never move an assignment. CONTROL: 226 unchanged, **4 moved, all `None -> value`**.
* **pv14** - the elided mention written as "**those to <port>**" (2026-03-26). One measured word added to the same fallback. CONTROL: 224 unchanged, **6 moved, all `None -> value`**.
All 20 recoveries were read back against THEIR OWN page sentence (each names both lanes and prints "$X and $Y ... respectively"): e.g. 2025-11-13 LA $2,328, 2025-10-23 NY $3,420, 2026-03-26 LA $2,686 / Rotterdam $2,552. **SHIPPED: stage 103 -> 116 shippable prints, displayed 105 -> 117 rows, 0 lost, 0 previously displayed rows changed, 0 cell corrections, 0 blank cells, 0 duplicate value-groups, dates unique/increasing/all Thursdays (2021-05-20 .. 2026-09-24); every added row's 5 values verbatim on its own page (12/12 rows, 60/60 values).** Gate census now `{snapshots 231, fetch_failed 1, incomplete 91, numeric 4}` - the ledger's "107 incomplete" is now 91. `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed**. Evidence `docs/drewry_wci_lane_recovery_verdict.md`.

**(A) the WCI md tier**: `corpus/06-drewry/opinions/2026/*_drewry_wci.md` carried the pre-fix parser output - 9/9 named with the RUN date, 9/9 `shanghai_rotterdam == shanghai_genoa`, 7/9 `shanghai_la == shanghai_ny`, 2/9 a lane blank, i.e. **5 prints in 9 files, each holding its neighbour lane's level**. IT MATTERED because `scratch/wci/merge_display.py` gives that tier AUTHORITY for dates >= 2026-08-01. FIX: new `scripts/scrapers/repair_wci_md_tier.py` (print date from the page's own phrase, values from the repaired CSV row, rename to the print's date; same-print files collapsed only after their bodies are proven identical): **9 files -> 5 files, 25 lines changed, 4 duplicates removed**. CONTROLS: every value verbatim in the file's OWN commentary (5/5 files, 5/5 values); git HEAD as before-witness (exactly 5 lines differ per file, commentary byte-identical 5/5); table == CSV 5/5; idempotent. Evidence `docs/drewry_wci_md_tier_verdict.md`.

**STILL OPEN, named and measured:** (1) **2026-02-12** - "spot rates **to Los Angeles and New York** falling 1% to $2,214 and $2,800 ... respectively": NO origin anywhere in the sentence, so the elided fallback cannot fire; needs an origin INFERENCE rule, trialed before it ships (values ARE printed). (2) 91 captures still incomplete (histogram in the verdict; `shanghai_ny` alone 20, 2026 only 2 left) - **2025-06-12 was READ and the publisher prints NO LA level** ("increased 1% in the past week and 89% in the past four weeks"), so that one is theirs, not ours. (3) **`data/provenance/manifest.json` is STALE for this series** (`row_count 108`, date_span starts 2021-06-24; the file is 117 rows from 2021-05-20) - regenerate with `python3 scripts/verify/build_provenance_manifest.py`, never hand-edit; NOT run here because it rewrites the whole registry. (4) the 2021-07-01 "k labels, 2k numbers" print; (5) `upsert_wci_rows()` dedupes by date only - a Thursday assertion would make this class unable to reappear silently; (6) poten runner-side HTTP 403 + replace `|| true` with a non-empty-catalog assertion.

**THIS RUN (2026-09-30 12:3x) - FOUND AND REPAIRED A SOURCE THAT HAD BEEN COLLECTING NOTHING FOR WEEKS WHILE ITS PIPELINE REPORTED SUCCESS. Found by auditing collection liveness (nothing named it); main was NOT touched.**

**THE FINDING: poten's live collection is dead on the Actions runner, and it is invisible from this box.**
`scripts/scrapers/fetch_poten_direct.py` line 488 puts a backslash inside an f-string expression
(`title.replace('\"', '')`), which is legal only from Python 3.12 (PEP 701). The runner is **3.11**,
so the module is a SyntaxError before it runs - while the local box (3.14) executes the same file
fine. Every poten run since 2026-09-11 died that way; every run since 2026-08-29 before it ended
`Total in catalog: 0`. **All of them concluded `success`**, because the step is
`python scripts/scrapers/fetch_poten_direct.py || true`. Reproduced read-only with
`Python311/python.exe -m py_compile`. MEASURED EFFECT: `corpus/04-poten` and `data/extracted/md/poten`
both end at **2026-09-18** while the publisher's own feed lists **2026-09-26** ("Do We Need To Plan For
A Diesel Export Ban?") - one weekly issue missing from corpus, md tier and RAG chunks.
**FIXED (branch only):** quote-stripping hoisted out of the f-string; controls: `build_markdown()`
HEAD-vs-fixed **5/5 byte-identical** (a first edit silently dropped the `Poten Tanker Opinion: `
prefix - the control caught it, restored, re-verified). Repo-wide 3.11 sweep: **444 compiled / 3 failed
-> 446 compiled / 0 failed** (same defect in `fetch_poten_archive_backfill.py:265`; a nested-quote
f-string in `current_book_scenario_ui.py:39`). **`origin/main` STILL CARRIES THE BUG** (verified after
`git fetch`), so Friday 2026-10-02 17:00 UTC will crash identically - merging is the user's call.
**NOT fixed by this:** the missing issue itself - poten.com returns **HTTP 403** to this box on both
listing URLs (the repo's own fetcher reproduces it), so only the runner's egress can fetch it; and the
step's `|| true` should be replaced by an assertion that the catalog is non-empty.
Evidence **`docs/poten_collection_outage_verdict.md`**.
**SAME RUN, SECOND POTEN DEFECT (verified while verifying the first):** `extract_year()` in
`fetch_poten_archive_backfill.py` could not see the archive's compact `Tanker_Opinion_YYYYMMDD.pdf`
form, so it took the year from the ARTICLE TITLE - **564 of 1,087 poten PDFs (52%)** returned
`unknown` under the old code, and *"The Outlook for Energy: A View to 2030"* (PDF dated 20071109) was
written as `poten_2030-01-01_...md` and now sits in the app's knowledge tier as
`knowledge/chunks/poten_tankers_2030.jsonl` (exactly 2 future-dated records exist in
`knowledge/chunks/**/*.jsonl`, both this file). FIXED on the branch (compact date read first; control
over all 1,087 filenames: only the 564 `unknown -> correct year` change). The duplicate corpus file
and the chunk rebuild are left to the corpus/knowledge owners - commands are in the verdict doc.

**ALSO THIS RUN: `docs/source_freshness_audit.md` - every source's collection freshness measured from
FILENAMES (never mtime), with the population stated.** 16 of 17 broker sources are current and their
extraction lag is **0 days**; the archive publishers are measured dead (allied 961 d, golden_destiny
674 d, gibson 1,097 d, other 1,087 d, anchor 1,374 d) so BACKFILL_ONLY stands on measurement, not on a
note. Three `DUE` readings were FALSE ALARMS and one was a bug in my own script: clarksons looked 12 days
stale because the parser did not strip the ordinal in `25th-Sept-2026` (**the fourth confidently wrong
detector in this project**); agora's missing W39 **404s on HSN** (site search's newest is week 38);
seabrokers' own site lists nothing newer than `markedsrapport-juli-2026`. `DUE` is a pointer to look, not
a finding.
**STALE POINTER RETIRED (do not act on it):** the 11:4x entry's "trial a median-preferring pick" for ism.
Measured (`scratch/ism_edge_baseline.py`, `scratch/ism_edge_attrib.py`): the edge fraction is 71.3%
(handy, baseline 44.7%) and 65.6% (coaster, baseline 52.4%) - real, but it is the documented
nearest-issue/first-print policy (`pick_observation`) plus the trivial n=2 case (**100% of "own week" rows
are edges by construction**), not a defect in choosing among restatements. All 29,948 values are verbatim
from the named issue; re-picking them optimises the very gate you would measure. Filter on `value_sd`
downstream instead.
**NEXT:** (1) the poten issue (runner-side only; a 403 diagnosis on the runner and an assertion instead of
`|| true`); (2) a merge of the branch fix to main when the user allows it; (3) the drewry WCI ledger items
unchanged (107 snapshots incomplete + 4 numeric-gated + 1 fetch failure, all pre-2023).

**THIS RUN (2026-09-30 11:4x) - the last open ledger item (the ism agreement tail) is CLOSED as MEASURED, and it is the PUBLISHER'S AXIS, not our parse. Plus a latent breakage fixed that would have silently emptied both ism series.**

The previous run's instruction was "name the failing REPORTS and read them". Done. Two documents were read against
their own pages, and in BOTH the extractor is exact:
* `ism_2024_W42` Izmail/Odesa-Bari/Ortona: recomputing by hand from the page's own printed y labels (100@292.9 ...
  20@432.9, 17.5pt/10 units, axis line 437.1) and the drawn grey `2022 year` path gives week 1 = **45.0** and
  week 10 = **37.0**, exactly the CSV. The CSV's 21-week "hole" is the publisher's own line break (one path, two subpaths).
* `ism_2026_W19` vs `ism_2026_W23` Corn/soybeans POC-Alexandria/Beirut: the page prints y labels **45..10** in W19 and
  **50..15** in W23 at essentially the same pixels (top label y 673.7 vs 675.7), and the extractor records each page's
  own labels exactly. An independent calibration fitted only from the printed labels + the drawn path reproduces the
  CSV on both pages (W19 2025 line 18.6/18.0/18.0/18.8; W23 2024 36.5/29.5/23.5/22.0, 2025 23.0/22.5/22.0/23.0).
  So the ~4-5 unit disagreement between issues is a publisher-side one-tick label shift; no re-extraction can remove it.
CENSUS (calendar-year overlays only, `scratch/ism_tail_census2.py`): 4,489 comparable keys, **1,231 rows = 8.5%** off the
cross-report median, **65 of 84** contributing reports never an outlier; concentrate in `ism_2026_W19` 121/122 (99%),
`ism_2023_W27` 120/125, `ism_2023_W36` and `ism_2023_W38` 127/140 each, `ism_2024_W41` 139/286, `ism_2025_W41` 111/265,
`ism_2025_W44` 114/268, `ism_2026_W06` 81/199, `ism_2024_W48` 53/110, `ism_2024_W50` 55/266, `ism_2023_W50` 48/204,
`ism_2024_W01` 48/154.
**THE ONE LEVER THAT IS OURS, measured and NOT applied:** the pooled `value` sits at the cluster EDGE (`min`/`max`) on
**1,139/1,598 (71%)** of the >2%-spread multi-report rows in handy and **635/969 (66%)** in coaster (n>=3 subset: 925/1,384
and 363/697). Next run: trial a median-preferring pick, re-measure the gate before/after; never hand-edit the CSV.
**FIXED + PROVEN THIS RUN:** a parallel process re-organised `data/extracted/md/ism/` into `2023/..2026/` subdirs at 11:35
today; `run_ism_series.py` globbed `*.charts.json` NON-recursively and would have found **0** charts and rewritten both
CSVs empty. Now `rglob`; re-run finds all **114** and reproduces both files **byte-identically** (sha256 `021d2a5f7498...`
coaster, `85bf1052b538...` handy). Same latent breakage (top-level `*.md` = 0, recursive = 271 / 247) fixed in the working
tree for `normalize_xclusiv_md.py` and `build_banchero_series.py` - both are UNTRACKED files belonging to another agent,
so the fix is left uncommitted beside them rather than landing their unpublished file.
Commit `248ae3174` (docs + runner). Evidence: `docs/ism_agreement_tail.md` section 3.
**NOTE: this dir tree is shared - 114 files moved while this run was measuring them. Always glob recursively.**

**THIS RUN (2026-09-30 10:2x) - THE LAST NAMED NUMERIC-GATE REJECT IS SHIPPED: WCI displayed 108 -> 109 rows, 569/569 = 100.00% page-reconciled. Plus one latent parser bug found while checking.**

The 2021-05-20 page introduces its levels with a PHRASE, not with the bare `to|at|reach` the parser knew:
*"soared 10% or $889 and **reached a new high of** $9,865"* and *"an increase of $350 **to touch** $5,605"* -
so the parser returned the **CHANGES** (889 / 350) for levels of 9,865 / 5,605. Both wrong numbers are ON the
page, so every recall control passed: the same change-vs-level family as pv10.
**FIX:** `to_rx` also accepts `to touch` and `a new low|high of`; the look-back window is `INTRO_WIN = 32`
(*"a new high of "* is 13 chars, so the old 8-char window could not hold it), anchored at the window END so a
`to` earlier in the sentence still cannot leak in. **ALSO REPAIRED: `COMPOSITE_AVG_RX` carried two literal
0x08 BACKSPACE bytes where `\b` was intended, so its `\bytd\b` alternative never matched** (the transport
trap this file already warned about). `PARSER_VERSION` 10 -> 11.
**CONTROLS, measured separately on all 230 cached pages re-parsed in process, nothing written:** the backspace
repair alone moves **0/230**; the phrase introducer moves **exactly 1/230 - 2021-05-20** (Rotterdam 889 -> 9865,
Los Angeles 350 -> 5605, both read against the page). Shipped: stage 102 -> 103 prints, numeric-gate rejects
**5 -> 4**, merge 0 corrections / 1 row added, md-tier untouched; displayed file 0 rows lost, **0 of the 108
previously displayed rows changed**, dates unique/increasing, **569/569 = 100.00%** verbatim on their own page,
0 fused, 0 composite == a route, pre-2023 **26/26 Thursdays with cover line 26/26**, md-tier byte-identical.
Evidence `docs/drewry_wci_era2021_verdict.md` (pv11 section). Commits `2ce8d7294` (code) + `897a81e79` (data).
**RESOLVED, do not re-list:** `data/derived/held_data_catalog.json` (still says `rows: 145`) is an **ORPHAN** -
`index.html`/`methodology.html` do not mention it, there is no builder for it in `scripts/`, nothing reads it.
**STILL OPEN:** 107 snapshots incomplete + 4 numeric-gated + 1 fetch failure (pre-existing, all pre-2023 - each
means the publisher printed no number or the row is a genuine reject, named in the gate census).

**SAME RUN, CONTINUED (11:0x) - LEDGER AUDIT: the two items the previous run left as "pick one" were ALREADY CLOSED. Verified today by measurement, and the "open" pointer was stale.**

* **4.5 `star_asia_deals_series.csv` - closed 2026-09-28. MEASURED today:** 3,358 rows; `arrival_date` ISO **2,708**, old European `DD.MM.YYYY` shape **0**; `beaching_date` ISO **1,747**, old shape **0**, the status text now in `beaching_date_status` (AWAITING 958 / ARRESTED 24 / blank 2,374). 63 publisher-corrupt years (`29.02.2022`) stay blank and are inventoried with page evidence. Do not re-chase.
* **4.3 `intermodal_macro_series.csv` - closed 2026-09-28, and the ledger's premise is WRONG BY DESIGN.** `prior_value` is the page's SECOND SESSION column (1-Jul-21) while the publisher's `W-O-W Change %` is week-over-week, so nothing about it should be expected to reproduce. MEASURED today: 2,833/3,739 (75.8%) do not reproduce from latest/prior, **0** blanks; but the printed % DOES reproduce from the same indicator's latest in the PREVIOUS REPORT on **3,266/3,723 = 87.7%** (exact 7-day gaps: **3,149/3,383 = 93.1%**), and fails only where the gap is 14/21 days - the true base is a report we do not hold. My probe on the page's own five value columns reproduces it on **1/795**. **Do NOT rewrite latest/prior to force reproduction.**
* **Section 2 of the ledger is stale; re-measured with its own instrument today:** ism_handy p90 20.59 -> **11.76%** (within 2% 69.1 -> **74.1%**), ism_coaster p90 43.34 -> **5.67%** (74.3 -> **83.7%**), ssy reference 87.1%, intermodal_baltic unchanged at 3.2% (held-data verdict stands).
**THE ONLY OPEN ITEM LEFT in the ledger is the ism residual tail** (within-2% 74.1% / 83.7%): name the failing REPORTS and read them, do not re-run the gate.

**SAME RUN, pv10 - the `reached` introducer: displayed 107 -> 108 rows (80 -> 108 for the run).**

`to_rx` accepted `to|at|reach` but not the PAST TENSE, so a level introduced by *"and reached"* lost to
the nearby CHANGE. MEASURED over all 230 cached pages re-parsed in process: **228/230 unchanged,
exactly 2 moved, both read against their pages, both improvements** - 2021-07-22 `shanghai_la`
**220 -> 9953** (*"increased 2% or $220 and **reached** $9,953"*) and 2023-09-28 `shanghai_rotterdam`
**120 -> 1052** (*"nosedived 10% or $120 for two consecutive weeks, and **reached** $1,052"*). The
2023-09-28 print now SHIPS (the numeric gate had been reading its $120 change; the spread tell caught
it, so nothing wrong was ever displayed); 2021-07-22 stays withheld as INCOMPLETE - New York is printed
as *"remain stable at previous weeks level"* with no number.
**CONTROLS, final for this run:** 108 rows (80 at the start), 0 of those 80 changed, **563/563 =
100.00%** of displayed values verbatim on their own page, 0 lost, dates unique/increasing/Thursdays
with cover lines 25/25 pre-2023, 0 fused, 0 `composite == a route`, 0 repeated value in a row,
numeric rejects 6 -> 5, `fused` 3 -> 0, md-tier (>= 2026-08-01) untouched.
**STILL OPEN (unchanged from the pv9 note):** 2021-05-20 (page introduces its levels with *"new high
of"* / *"an increase of"*, so the parser returns the **$889/$350 changes**); the stale derived
metadata (`data/provenance/manifest.json`, `data/derived/held_data_catalog.json` still say
`row_count 145`); 107 snapshots incomplete + 5 numeric-gated + 1 fetch failure, all pre-existing.

**SAME RUN, CONTINUED (pv9) - THE OPEN FUSED-LANE SHAPE IS FIXED, not just withheld: displayed 104 -> 107 rows, 558/558 page-reconciled, `fused` census 3 -> 0.**

The item this run left as "NEXT (precise)" is done. The 2021-07-01 print AND the two the previous run
had gated out (2023-02-23, 2023-09-21) were ONE shape with TWO distinct causes, both measured on pages:
(1) **a leading prose word absorbed into the lane label** - *"**On** Shanghai - New York and Shanghai -
Rotterdam, rates fell by 4% to ..."* matched group1 as "On Shanghai", which `is_route_mention` then threw
away, so the sentence counted ONE lane instead of two and `respectively` could never fire; fix = trim
leading non-port words off the match. (2) **the pools could not separate a dollar CHANGE from a dollar
LEVEL** - *"grew $617 and $539 to $9,165 and $11,719"*, *"dropped 10% or $167 and $127 to $1,531 and
$1,172"*: with k=2 and 4 dollar values none of the three pools held exactly k (the `or` filter strips
only the FIRST change), so the row fell through to proximity and lane 2 got lane 1's level - the very
thing the `fused` gate was catching; fix = **(d) TO-ANCHORED SUFFIX** (the levels are the run starting
at the value introduced by to|at|reach), used ONLY as a last resort after the three existing pools.
**CONTROL:** all 230 cached pages re-parsed in process (nothing written): **225/230 unchanged**; the 5
that moved were each read against their pages and **all 5 are improvements** - 2021-07-01 NY 9165->11719,
2021-07-22 G 13066->12773, 2023-02-23 R 2881->1633, 2023-09-21 R 1531->1172, 2024-02-15 NY 709->6170 and
RS 4288->958. Two of those pages still do not ship and BOTH are correctly withheld as **incomplete, not
wrong** (2021-07-22 prints New York as "remain stable at previous weeks level"; 2024-02-15 prints
Shanghai-Los Angeles as "remained stable") - the publisher printed no number.
**FINAL CONTROLS on the 107 rows:** 0 of the 104 previously displayed rows changed; **558/558 = 100.00%**
of displayed values verbatim on their own page; change arithmetic pre-2023 $ **45/45** and % **43/45**,
2023+ $ **56/56** and % **49/56**; composite == page headline level **30/30**; new dates are Thursdays
carrying the cover line **25/25**; 0 fused / 0 `composite == a route` / 0 repeated value in a row.
Evidence `docs/drewry_wci_era2021_verdict.md` (both sections).
**NEXT (precise, in order):** (1) `to_rx` matches `to|at|reach` but NOT **reached/reaches** -
*"increased 2% or $220 and reached $9,953"* (2021-07-22) returns the CHANGE; needs its own corpus
control (it would not ship that row - New York is unprinted that week). (2) 2021-05-20 numeric-gate
reject: the page introduces the levels with *"new high of"* / *"an increase of"*, so the parser returns
the **$889/$350 changes** - do NOT add `of` blindly, it introduces real changes too. (3) the stale
derived metadata (`data/provenance/manifest.json` and `data/derived/held_data_catalog.json` still say
`row_count 145` for `data/indices/drewry_wci_historical.csv`) - regenerate, never hand-edit.
**LESSON (repeat of the project's most expensive one):** the previous run's fused-gate reject, the
`fused` pair, and two of these five wrong cells were all "well-formed and plausible" - only reading
the sentence against the parsed lanes found them. A recall check cannot see a swap and a gate cannot
see a value that is merely the CHANGE instead of the LEVEL.

**THIS RUN (2026-09-30 09:0x) - THE 2021-2022 ERA IS SHIPPED: WCI displayed series 80 -> 104 rows, 542/542 values page-reconciled. The "NEXT (precise)" item of the previous run is DONE.**

The hard `page_date < '2023-01-01'` cut was moved to `TRIALED_FROM = '2021-01-01'` - and only after
the era was trial-verified print by print against its own cached pages.
**THE TRIAL FOUND ONE REAL DEFECT (the reason the cut existed is not the reason it was fixed):**
**2021-06-24 had New York and Los Angeles SWAPPED.** Page: *"rates on Shanghai-New York and Shanghai-Los
Angeles soared 39% and 34% to $11,180 and $8,548 per feu, respectively"* -> NY 11,180 / LA 8,548; the
parser returned LA 11,180 / NY 8,548 - **two plausible numbers handed to the wrong lanes**, so every
recall control passed (both values ARE on the page).
**ROOT CAUSE (reproduced):** `label_rx` separated a lane with `to` or an EN/EM DASH - **the plain
hyphen was NOT in the class**, so the publisher's 2021 spelling `Shanghai-New York` was never a label,
the ordinal/`respectively` rule could never fire and proximity gave Los Angeles the first `$`.
MEASURED: 30 hyphenated lane tokens on the 2021 pages; the non-lane ones (East-West, Intra-Asia,
Ro-Ro, Y-o-Y, Hapag-Lloyd) are rejected by `is_route_mention`'s port vocabulary.
**FIX:** separator class + `-`; `PARSER_VERSION` 7 -> 8.
**CONTROL ON THE FIX:** all 230 cached snapshots re-parsed offline (no network, no spend) and
diffed pv7 vs pv8: **exactly 2 snapshots moved corpus-wide - both captures of that same 2021-06-24
print, both the swap - and 0 post-2023 snapshots moved.**
**SHIPPED CONTROLS:** 80 -> 104 rows (0 lost, dates unique, strictly increasing); **542/542 = 100.00%
of displayed values appear verbatim on their own page**; parsed composite == the page's **own
headline level 30/30** (independent regex, parser not reused); printed **$ change 45/45** and **%
43/45** on pre-2023 consecutive weeks (2023+ unchanged at 56/56 and 49/56); **post-2023 stage
byte-identical**; **0 previously displayed rows changed** (additions only); new dates are Thursdays
**24/24** and carry the page's own cover line **24/24**; 0 fused, 0 `composite == a route`, 0 rows
with a repeated value; md-tier (>= 2026-08-01) untouched. Evidence `docs/drewry_wci_era2021_verdict.md`.
**WITHHELD, named:** of 79 pre-2023 snapshots, 49 lack all five values, **2021-05-20** fails the
numeric gate (the parser returns the printed **$889/$350 CHANGES**; the level there is introduced by
*"new high of"*/*"an increase of"*, not by to|at|reach) and **2021-07-01** fails the fused gate
(*"grew $617 and $539 to $9,165 and $11,719 ... respectively"* -> both lanes got $9,165).
**NEXT (precise):** that last one is the still-open **"k labels, 2k numbers, changes first"** lane
shape - the SAME family as the two post-2023 rejects 2023-02-23 and 2023-09-21. Fixing it would
recover 3 named prints (1 pre-2023 + 2 post-2023) and would let the `fused` gate stop rejecting
them. Start by reading those three sentences off their cached pages, then trial the rule on them.
**ALSO OPEN:** `data/provenance/manifest.json` and `data/derived/held_data_catalog.json` still say
`row_count 145` for `data/indices/drewry_wci_historical.csv` (stale since the 138-row fabrication
purge, NOT introduced by this run; neither file is rendered). Regenerate, do not hand-edit.
NOTE: `git checkout` of this worktree had been moved to `main` by the fleet-sync automation at
08:59; it was restored to `benchmark/extraction-comparison` before any commit.

**THIS RUN (2026-09-30 07:4x) - A DISPLAYED DEFECT FIXED: the Drewry WCI composite was the publisher's YEAR-TO-DATE AVERAGE on 6 displayed rows (worst +21.0%). 75 -> 80 rows, 408/408 = 100.00% page-reconciled.**

`data/indices/drewry_wci_historical.csv` is fetched by `index.html`. Six of its 75 rows carried a
wrong composite in the PLAUSIBLE direction, so no count-based check could see it: 2023-06-22 showed
1822.0 where the page prints 1,535.75 (+18.6%), 2023-06-29 1809.0 vs 1,494.46 (+21.0%), 2023-08-03
1770.0 vs 1,761.33, 2023-09-07 1769.0 vs 1,680.73 (+5.3%), 2023-09-14 1763.0 vs 1,561.30 (+12.9%),
2023-01-05 2135.0 vs 2,135.16. Every one is the publisher's own *year-to-date average*, printed two
sentences after the week's level.
**ROOT CAUSE (reproduced):** `COMPOSITE_PAT` bounded its gap with a period-free character class, so
any page whose change has a decimal ("increased 4.7% or $255 to $5,726.99 per 40ft container") failed
the headline and fell through to the YTD-average sentence. MEASURED on all 228 cached pages: 49 took
the average; 6 of those were displayed.
**FIX:** the gap now allows periods, and the first match whose preceding 90 chars hold no
`average|year-to-date|ytd` wins.
**INDEPENDENT CONTROL (page text only):** the later week's page prints its own % and $ change, so
level_new = level_old*(1+pct) and level_new-level_old = printed $. Same 57-58 consecutive pairs:
BEFORE % 12/57, $ 51/57 - AFTER % 43/58, **$ 58/58** (the 15 residual % misses are the control's own
extractor grabbing the "remains 224% higher than a year ago" percent).
**TWO MORE DEFECTS THE FIX EXPOSED:** (1) the contamination gate's 2-decimal tell was applied to the
composite - the publisher prints every ROUTE as a whole dollar but the composite to 2 dp, so the tell
was silently dropping **12 real prints, all 12 with the 2 dp in the composite alone**; re-scoped to
routes. (2) the checkpoint's `rotterdam_shanghai` was STALE on 2 displayed rows (5.0 and 16.0 = the
printed CHANGE); the current parser already returns the page's 575 and 500, so a re-parse fixed them.
**NEW GATE:** `fused` - reject a print where two tracked lanes carry an equal level. MEASURED: exactly
2 of the 76 staged prints carry an equal pair and BOTH are the parser handing one lane the other's
level (2023-02-23 Rotterdam got NY's 2,881; 2023-09-21 Rotterdam got Genoa's 1,531). The lane rule for
that shape ("k labels, 2k numbers, changes first") is STILL OPEN - named pages in the verdict.
**SHIPPED:** 8 cells corrected + 5 rows added (2023-01-12/02-16/03-02/03-30, 2025-07-03); stage 68 ->
74 gate-passing prints; 0 dup dates, 0 fused, 0 composite==route; **408/408 = 100.00% of displayed
values appear verbatim on their own page**; md-tier authority kept for >= 2026-08-01 (09-03, 09-10,
09-24 untouched); the staged 2026-08-06 print skipped as the same week as the displayed 2026-07-30.
Evidence **`docs/drewry_wci_composite_verdict.md`**.
**NEXT (precise):** the 2021-2022 era is blocked by a HARD `page_date < '2023-01-01'` cut ABOVE the
era gate - MEASURED: `--era-from 2021-01-01` still yields 2023-01-05..2026-09-24 and a byte-identical
stage. Trial the 30 complete 2021-2022 records against their pages, then remove that cut. They now
look parseable: their pages carry the full route prose (4/4 correct on two pages read by eye) and
their composite was the same YTD-average defect, now fixed.
**PRE-TRIAL ALREADY MEASURED (after the fix, nothing shipped):** on the 68 cached pre-2023 prints,
45 consecutive-week pairs reproduce the printed $ change **45/45** and the printed % **43/45**, and
every value of the first 40 pre-2023 prints appears verbatim on its own page (0 missing)
(`scratch/wci/era2021_ctl.py`). The 30 gate-passing records still need their lane values read
against the pages. Then: the open lane-fusion shape.

# OVERNIGHT STATE - read this FIRST, then resume

**THIS RUN (2026-09-29 17:xx) - WCI BACKFILL SHIPPED: the parser was fixed on measured page evidence and the displayed series went 17 -> 75 rows. The previous run's recorded diagnosis was WRONG.**

The state file said a route was "assigned to the first line that mentions it" and prescribed
"make the assignment global across lines". FALSE: the 2024-04-18 assessment is **ONE text line**,
so no line-scoping change could matter. The real bug was the `respectively` rule pairing the k-th
label with the k-th `$` across a **multi-sentence paragraph** (Genoa got the $2,291 of
Rotterdam-New York). Five shapes were found and fixed, each on a real archived page: (1) sentence
scope; (2) ordinal over EVERY lane named, not just tracked ones (2024-04-25: LA took 2214/3,395);
(3) clause-local pairing (2026-03-05 LA/NY swapped, 2026-07-30 R/G swapped); (4) ordinal pool must
prefer "to|at|reach"-introduced LEVELS, never the "or $X" change (2025-01-30); (5) a clause holding
only a change takes its level from the next lane-less clause ("diminished 3% or $16 **and stood at
$500**"), and en-dash lane lists must be enumerated too (2023-09-07/14).
**MEASURED:** 231 snapshots re-parsed from a LOCAL CACHE (`scratch/wci/raw/`, no re-fetch needed),
121 with all five values, 68 gate-passers. Controls: **publisher markdown 40/40** (8 WCI md files,
unchanged before AND after every fix), **7/7 page trials exact**, and an independent **% control
(127/128 = 99.22%, was 87.5%)** that reproduces the % the PUBLISHER prints for each lane from two
different weeks' documents. `data/indices/drewry_wci_historical.csv`: **17 -> 75 rows**, 2023-01-05
.. 2026-09-24, 0 dupes / 0 fused / 0 composite-equals-route; exactly **1 correction** (2026-07-30
R/G unswapped); the 8 md-tier rows >= 2026-08-01 byte-identical; the 10 previously committed rows
byte-identical. Evidence **`docs/drewry_wci_backfill_verdict.md`**.
**WITHHELD, stated not implied:** 2021-2022 (30 records) stays behind the hard pre-2023 gate - that
era's prose is untrialed and parses to garbage; 1 fetch failure; 109 captures without all five
values. The 5 gaps > 45 days are the ARCHIVE's coverage (~38 captures/year), not the parser's.
**NEXT (small, precise):** (a) the 2021-2022 era could now be trialed the same way - the cache is
local and free, so trial one 2021 page against its printed sentence before touching the gate;
(b) the live site is still HTTP 429 from this box, so any further history is a Wayback collection
job; (c) 2026-08-24 exists as an md-tier print and is still NOT displayed (it duplicates 08-25).
NOTE for whoever edits the parser next: build replacement text with `chr(92)` - a `\b` written
through the tool transport arrived as a literal BACKSPACE byte and silently disabled `label_rx`;
and keep heredocs under ~5 KB or the shell eats them.

**THIS RUN (2026-09-29 15:2x) - WCI backfill FINISHED; displayed file now holds only REAL rows.**

`backfill_wci_history.py --fetch` ran to completion: **231 archived weekly captures** (2021-2026,
Wayback, one per ISO week), **81 with all five values parsed**, **30 passing the numeric +
contamination gates**. `--stack` then applied an era gate and
**`data/indices/drewry_wci_historical.csv` is now 17 rows, ALL 2026** - the 7
publisher-markdown-verified prints + 10 backfilled. Controls on the merged file: 0 fused
`rotterdam == genoa`, 0 rows where composite == a route value, 0 two-decimal values.
**2026 IS TRIALED** (4 captures re-parsed and read against their own printed sentences, all
matching, plus a **3/3 all-five-values match with the publisher markdown**: the 2026-09-03 capture
reproduces the md's 4,465/4,092/4,368/7,185/9,587 exactly).
**2021-2025 IS NOT - 71 complete captures are WITHHELD, measured not assumed:** 2024-04-18 prints
*"rates on Shanghai to Rotterdam and Shanghai to Genoa declined 2% to $2,989 and $3,577 per feu
respectively"* and the parser gives Genoa **2,291** instead of 3,577 (2024-02-29 and 2025-01-23
sample correctly). Cause: `assign_route_values()` assigns each route to the **FIRST line that
mentions it**, so a stray earlier mention blocks the correct later assignment.
**NEXT ACTION (precise):** make the assignment global - score every line's candidate for a route,
then pick the best across lines - re-run `--stack`, re-trial 2024-04-18 + two more 2024/2025
captures against their printed sentences, and only then widen the era gate in `do_stack()`
(`rec['_ship'] = rec['page_date'] >= '2026-01-01'`). Checkpoint:
`data/extracted/wci_backfill/checkpoint.jsonl` (231 records, resumable). Staging:
`data/audit/drewry_wci_real_rows_from_wayback.csv`. Evidence:
`docs/drewry_wci_fabrication_verdict.md`.
NOTE: the live Drewry site returns **HTTP 429** from this box - the scraper is Wayback-only
until that clears.

**THIS RUN (2026-09-29 14:5x) - BIGGER FINDING, FOUND WHILE FIXING THE ABOVE: 138 of the 145
DISPLAYED Drewry-WCI rows were FABRICATED. PURGED. Real history backfilling now.**

`data/indices/drewry_wci_historical.csv` is fetched by `index.html`. Commit `22c0a870a` ADDED
`generate_canonical_wci_history()` inside `scripts/scrapers/fetch_drewry_wci.py` and wired it into
the failure path (`if not primary: csv_path = update_csv()`), so whenever the live page was
unparseable the scraper WROTE INVENTED DATA - a sine/cosine trend starting at 2,100 with a fake
`2800 * exp(-((i-28)**2)/60)` "Red Sea crisis spike". A later commit reduced it to a stub whose
comment says *"no values synthesized"* - **but nothing removed the 138 rows it had already
written.**
**PROOF 1 (formula):** reproduced the removed generator verbatim (grid 2024-01-04..2026-08-20,
freq 7D, n=138): **138 of 138 rows on that grid reproduce it exactly** on all six columns
(tol 0.051 = the publisher's 1 dp). That is 138 of the file's 145 rows.
**PROOF 2 (the publisher, decisive):** parsed the publisher's own archived pages with the fixed
parser - 2024-07-04 prints composite **5,868** (CSV said **4,893.0**), 2025-07-10 prints **2,672**
(CSV **3,167.0**), 2026-03-05 prints **1,958** (CSV **3,761.6**) - and in every case the CSV's
number is EXACTLY the formula's output.
**ACTION:** the 138 rows are MOVED (not deleted) to
**`data/audit/drewry_wci_synthetic_quarantine.csv`** (committed evidence); the displayed CSV now
holds **7 rows**, the only ones ever really scraped, each verified against the publisher's own
markdown. No fabricated value remains in a displayed artefact. Evidence
**`docs/drewry_wci_fabrication_verdict.md`**.

**THE PARSER NEEDED TWO MORE ERA FIXES BEFORE ANY BACKFILL** (the trial is what caught them - the
7 repaired rows only exercised the 2026 prose):
(1) **change before level** - 2021-2024 pages print *"rates from Shanghai to New York increased 17%
or $1,331 to $9,158 per 40ft container"*, so "nearest number to the label" returned the CHANGE:
Shanghai-Rotterdam came out **734** instead of **8,056** (a 10x-class error in the plausible
direction). Fix: a value introduced by `to` outranks a nearer value that is not.
(2) **positional "respectively" list** - *"rates on Shanghai to Los Angeles, Rotterdam to Shanghai
and Los Angeles to Shanghai increased by 6% to $2,100, 3% to $466 and 1% to $774 per feu
respectively"* - labels and values cluster in the same order, so proximity gave Los Angeles the
$466 that belongs to Rotterdam-Shanghai. Fix: k-th label -> k-th value.
TRIALED against the sentence printed on each page: **2023-12-21** R1667/G1956/LA2100/NY3074/comp1661,
**2024-07-04** R8056/G7573/LA7472/NY9158/comp5868, **2025-01-10** R4375/G5210/LA5476/NY7085/comp3986,
**2026-09-12** R3997/G4216/LA7352/NY9726/comp4476 - all four match the page. The 2026 one is the
control: it reproduces the same four values as the markdown the 7 surviving rows came from.
WATCH OUT: my own first patch wrote a literal **backspace byte** for `\b` (a non-raw string in the
patch script) and doubled `\s`, which silently disabled the new date anchor; caught only by the
trial. **Build replacement text with `chr(92)`, never with backslashes inside a heredoc.**

**NEXT / IN FLIGHT:** `scripts/scrapers/backfill_wci_history.py` (new, committed) rebuilds REAL
history from the publisher's archived pages - one capture per ISO week, append-only JSONL
checkpoint (`--resume`), no row written unless all five core values parsed. Launched as a
background job; **231 weekly snapshots to fetch**. `--stack` emits
`data/audit/drewry_wci_real_rows_from_wayback.csv`. Judge it by the advancing checkpoint
(`wc -l data/extracted/wci_backfill/checkpoint.jsonl`), never by `ps`. When it is done, stack it
into the displayed CSV and re-verify a sample against the page prose.

**STILL OPEN (measured, not fixed):** the 7 `data/indices/capital_link_*.csv` files carry
`open == high == low == close` on 100% of 5,525-5,612 rows and `volume = 0.0` on 100% (42
column-pairs); the publisher's own master has ONLY a close, so those columns are placeholders.
MEASURED severity: not user-visible (`index.html` reads only `r.close` + `change_pct` for
`capital_link: true` products). Left unchanged deliberately. Detector `scratch/sweep_fused_cols.py`.

**THIS RUN (2026-09-29 14:0x): NO source is unbuilt - so I audited what the APP SHOWS and found a
REAL, user-visible defect in a displayed index. FIXED + verified.**

xclusiv is 266/266 and every broker source is CLOSED (`EXTRACTION_REGISTER.md`: all 27 rows). The
ledger's last item (ism tail) closed at 12:3x. The prompt's "next source" list is stale, and poten
is closed. So this run went after an artefact that is actually **rendered**: `index.html` fetches
`data/indices/drewry_wci_historical.csv`.

**DEFECT: Drewry WCI route columns were FUSED on the 7 newest rows (14 cells).**
`shanghai_rotterdam == shanghai_genoa` and `shanghai_ny == shanghai_la` - so the app drew
Rotterdam/Genoa as ONE line and LA/New York as ONE line. 2026-09-18 printed 4016/4016/7712/7712
where the publisher's own page says **3626 / 4016 / 7712 / 10394**.
**ROOT CAUSE (reproduced, not guessed):** the page carries **no `<table>` at all** - the
assessments are PROSE with **TWO routes in one sentence** ("...Shanghai to Genoa fell 3% to $4,216
... while they decreased 2% to $3,997 ... from Shanghai to Rotterdam"). The scraper's free-text
fallback took the **FIRST `$` on the line for EVERY route named on it**, so the second route got the
first route's value. Reproduced against Wayback snapshot `20260912113125` (the LIVE site returns
**HTTP 429** from this box).
**FIX:** `assign_route_values()` in `scripts/scrapers/fetch_drewry_wci.py` - every `$N` on the line
is a candidate, a route claims the **nearest** one (<=120 chars), assigned greedily so a number is
used at most once. Content-anchored, no geometry. Also fixed the date parser: `%B` rejected `Sep`,
so the page's own `assessment for Thursday, 10 Sep 2026` never matched and the regex fell through
to an UNRELATED date elsewhere on the page (`2026-09-29` on the 09-12 snapshot).
**VERIFIED:** parser now returns 3997/4216/7352/9726 on the 09-12 snapshot (all distinct, matching
the prose sentence it had read); all 14 corrected cells are **verbatim in the publisher's own**
`corpus/06-drewry/opinions/2026/*wci*.md` (14/14); 145 rows unchanged; **0** fused rows remain;
CSV diff is exactly 14 lines; the repair is **idempotent** (2nd run changes 0 cells).
Evidence **`docs/drewry_wci_display_verdict.md`**.
STILL OPEN there (stated, not implied): the file is **one week stale** (newest 2026-09-20; the
verified 2026-09-27 snapshot exists but was NOT added - that is a collection job with its own date
convention). The 138 rows older than 2026-08-25 have no ground truth in this repo; they are clean
of THIS defect by construction (the bug always yields `rotterdam == genoa`).

**GENERALISED THE FINDING - swept all 22 `data/indices/*.csv` for the fused-column signature.**
One class flagged: the 7 `capital_link_*` files carry `open == high == low == close` on
**100%** of 5,525-5,612 rows and `volume = 0.0` on 100% (42 column-pairs). The publisher's own
`capital_link_indices_master.csv` has **only a close** (0 rows with 4 distinct OHLC), so the extra
columns are **fabricated placeholders**. MEASURED severity: **NOT user-visible** - `index.html`
reads only `r.close` + `change_pct` for `capital_link: true` products (the only `volume` read,
line 18709, is the SGX futures block). Left UNCHANGED on purpose: blanking columns could break
`build_views.py` / `build_provenance_manifest.py`, and nothing renders them.
No other index file has the signature. Detector: `scratch/sweep_fused_cols.py`.

LESSON: a **scraper** writing prose-derived numbers needs the same discipline as a PDF extractor -
anchor on content (the value NEAREST its label), never on position (the first number on the line).
And when an artefact is DISPLAYED, a plausible wrong number is invisible to every count-based
check: 145 well-formed rows and a valid CSV both look perfectly healthy.

**THIS RUN (2026-09-29 12:3x): ism residual tail CLOSED - 2 REAL DEFECTS FIXED, spread is the PUBLISHER's.**
Ledger's last open item. Rebuilt from the CACHED `.charts.json` - **no API spend**. Row counts
unchanged (handy 17,629 / coaster 12,319 / 29,948), so `EXTRACTION_REGISTER.md` stays valid.
(1) **`unit` was wrong on 16,985 of 29,948 rows (57%)** - `build_rows()` read a variable named
`title` that is NOT a parameter; it is `main()`'s chart-loop variable, resolved at call time, so
every row got the unit of whichever chart was processed LAST. `$/t` never appeared at all before,
though 16,985 rows carry a title AND a label ending in `$/t`. FIX = `unit_for(title,[label])`,
page-derived (label suffix first - a CFR chart carries a `%` line AND a `$/t` line, so the unit is
per-SERIES). MEASURED: handy `%`1,058/`$/day`16,571 -> `%`1,058/`$/t`14,668/`$/day`1,903; coaster
`%`1,130/`$/day`11,189 -> `%`1,130/`$/t`7,637/`$/day`3,296/`EUR/t`256. CONTROL 24,409 rows checked
against their own printed unit suffix: **0 real mismatches**.
(2) **`value` was a MEDIAN across restatements that contradict each other** - a number no page ever
printed. ism redraws each chart weekly over a rolling 52-week window; of 1,495 restated TCT points
**24.6% differ >2%** between the week's own issue and the latest, **14.6% by >10%**; and BOTH window
edges are unreliable (the week's own issue prints a PROVISIONAL newest point: `ism_2024_W21` prints
17,035 for a week every later issue prints as 19,546; the oldest point of a later issue is expiring).
FIX = `pick_observation()`: drop points drawn outside their own chart's printed axis (14 corpus-wide,
all negative freight rates), prefer a NON-edge point, then the issue nearest the observation date.
MEASURED CONTROL: **29,948/29,948 = 100.00% of emitted values are verbatim in the issue named by the
new `value_report` column**; 0 negative `value`, 0 negative `min_value`. Change is surgical: p50
0.0000, p90 0.0016/0.0033, only **736 rows** move >5% (465 handy + 271 coaster). New columns
`value_edge` (0/1) and `value_report`; `min_value`/`max_value`/`value_sd`/`n_reports` still carry
the restatement band.
**THE SPREAD IS THE PUBLISHER's, read off the PAGES (not geometry):** (a) the publisher RELABELS its
own year-comparison lines - chart `Fertilizers, 4,000t, Klaipeda - N.Spain (2500x/2500x), $/t` prints
legend `2020/2021/2022 year` in `ism_2023_W50` and `2022/2023/2024 year` in `ism_2024_W01`, and the
line W50 calls `2021 year` carries EXACTLY the values W01 calls `2022 year` (labels are matched by
stroke COLOUR, so this is not an order mis-join); (b) ONE TCT line changes level mid-2025 while its
five siblings stay identical to the digit (at 2025-03-31: W18 14,246.6 vs W22 7,999.5 vs W26 7,999.4
for `Supramax, ECSA - Cont (bss dely APS)`, all five others within 0.2 units across the three
issues). Residual >10% spread flags: **665 handy / 453 coaster** - a record of the publisher's own
restatement band. Evidence **`docs/ism_series_value_provenance_verdict.md`**; the earlier
`docs/ism_residual_verdict.md` is annotated (its median RECOMMENDATION was measured wrong and not
followed).
**NEXT TARGET SCOPED AND CLOSED THIS RUN - poten (`corpus/04-poten`, 1,087 PDFs, 2004-2026).**
Three-baseline test done, so the next run does NOT re-derive it: poten is PROSE-FIRST (a report is
ONE page, ~3,400 chars; only **49 of 1,087** reports contain any table at all). Coverage is
already complete - metadata **1,087 rows = 100%** of the corpus; `knowledge/chunks/poten_tankers_<year>.jsonl`
for EVERY year 2004-2026; the app consumes ONLY those RAG chunks (the two series CSVs are not
displayed). **Every one of the 49 tabular reports has charterer rows (49/49, 0 missing)**; 36 of them
carry exactly ONE table (charterers only) so they legitimately have no fixture rows, and
`poten_fixtures_series.csv` covers exactly the reports that printed a fixtures table - its last date
**2014-03-14 is the publisher retiring the feature, NOT a missing extraction**. The charterers table
is sporadic, not monthly: 2 reports/year in 2024/2025/2026. **Do NOT build a from-zero poten runner.**
Only open thread: `tables_count` comes from the metadata extractor so it could undercount (a text
scan of all 285 reports 2020-2026 found 2 table-phrase hits, matching the metadata - suggestive, not
proof). Evidence **`docs/poten_survey.md`**. Remaining unbuilt non-broker corpora after poten:
`corpus/06-drewry` 276 (has an existing fetcher), `corpus/02-hellenic` 3,969 (OWNED BY ANOTHER LIVE
SESSION - do not collide), `corpus/03-breakwave` 302 / `corpus/08-baltic` 3,038 / `corpus/07-signal`
(existing fetchers, signal CLOSED).

**NOTE:** xclusiv is 266/266 and every broker source is CLOSED - the prompt's "next source" list is
stale. banchero_costa now has **245** `.md` on disk (was 243). HELLENIC is owned by a separate live
session - do not collide.

**THIS RUN (2026-09-29 11:5x): BOTH bancosta residues CLOSED (the state file's two NEXT TARGETS).**
(1) freight_rates SECOND residue - the "125 rows / 52 docs whose `unit` is not a unit" split into 68 leaked
sub-header rows, 21 empty rows and 33 SHIFTED rows, all in branch 11. Root cause = a FIXED column index in a
table that redesigns across years: 2021-2022 publish a 7-col `| Category | Name | Unit | <d> | <d> | W-o-W |
Y-o-Y |` grid and `DELAYS AT TURKISH STRAITS` an 8-col one, so the Name landed in `unit`, the unit in
`rate_current`, and W-o-W/Y-o-Y were DROPPED. FIX = content anchor (`FREIGHT_UNIT_TOKENS`); a row with no
unit token is a header/banner/empty row; join `<code>`+`<name>` hyphenating a leading `TCE` (the page prints
`TC1-TCE`). MEASURED: freight_rates 20,249 -> **20,321**; non-unit rows 125 -> **0**; distinct units 44 -> **6**.
(2) branches 7/8 (VHSS ConTex + Freightos) - the SAME defect: heading-only gate + fixed index, so the
container CHARTS under the same heading (`| Date | 4250 | 3500 | 2700 |` / `| Jul-20 | 8000 | 8000 | 8000 |`)
were published as container indices, and the Freightos banners (`Services:`) as routes. FIX = require a real
unit token (`_INDEX_UNITS`); a chart table then falls through to branch 12 (chart_series). MEASURED:
vhss_contex 3,427 -> **1,714**; freightos_index 2,271 -> **1,769**; non-unit rows 2,215 -> **0**;
chart_series 39,425 -> **42,403** (0 removed, +2,970 added). NOTE `chart_series` is a SIDECAR-only artefact
(not one of the 10 stacked series CSVs).
CONTROLS (both): (a) a cache-only rebuild reproduces all 10 series CSVs byte-exact BEFORE either patch;
(b) after, **8 of 10 byte-identical** - only freight_rates and vhss differ; (c) EVERY added row verified
verbatim - 196/196 (freight), 1,714/1,714 (vhss) + 1,769/1,769 (freightos) + 2,970/2,970 (chart), all
reconciled against the publisher's own PDF text layer or the LlamaParse pixel-read; (d) every removed row
CLASSIFIED, **0 removed rows carried a unit token / 0 real route codes lost**; (e) ground truth read from
the rendered page text of 2021_W46 page 6 and 2021_W26 container page. Rebuilt from the CACHED markdown -
**no API spend**. Evidence **`docs/bancosta_freight_rates_residue2_verdict.md`**,
**`docs/bancosta_container_index_chart_verdict.md`**.
METHOD NOTE: this run had NO vision tool (no image tool in the cron session) - substituted same-document
text reconciliation against BOTH the PDF text layer and the LlamaParse markdown, and read the rendered page
TEXT. Both bancosta residues are now closed; the only bancosta blocker left is the LlamaParse credit wall
(HTTP 402) for the final 1 doc of 244 - only the user can rotate the key.
NEXT TARGET RE-MEASURED (2026-09-29 12:0x, so the next run does not re-derive it): the residual ism
agreement tail is SMALLER than `docs/ism_agreement_tail.md` records (it says 2,269 rows / 17.5%; the file is
STALE - the 2026-09-28 re-key already took it to 1,178). Measured NOW on the two merged files:
ism_handy 6,116 multi-report rows / **723 >10% spread (11.8%)**; ism_coaster 5,876 / **485 (8.3%)** = 1,208
total. The top offenders are NO LONGER `% of freight costs in CFR price` (which the entity re-key fixed);
they are (a) `'TCT rates dynamics, $/day' / 'Supramax, ECSA - Cont (bss dely APS)'` 84 rows and
`'Handysize, BlSea - EMed ...'` 73 - the entity sits in `series_name` and the spread may be genuine
publisher restatement; and (b) `'<route> ... $/t' / '2021 year'|'2025 year'|'2024 year'` (52/41/41) - the
multi-year chart axis, i.e. the year series plotted against a date axis. VERIFY each against the ism page
BEFORE fixing (three previous "defects" looked real and were faithful). ism route rates are NOT held data,
so this fix is worth doing. ism runners: `scripts/extract/publishers/run_ism.py` + `run_ism_series.py`.
HELLENIC is owned by a separate live session - do not collide.

**THIS RUN (2026-09-29 02:3x): bancosta_freight_rates DRY_BULK residue CLOSED - 80 rows routed, 0 left.**
The 80 misrouted rows re-measured EXACTLY as briefed (FX 8/2, chart 25/5, commodity-with-unit 13/2,
container TC 24/2, banners 10/3). Root cause = branch 11 gates on the HEADER STRING alone and sectors
from ctx alone, while the specific branches' gates were CTX-ONLY (VHSS sits under CONTAINERSHIP MARKET;
the FREIGHTOS table has no heading; the 2021 FX heading is INTEREST RATES / CURRENCIES, not EXCHANGE
RATES). FIX = content anchors only: (1) branch 9 requires a real XXX/YYY row + accepts CURRENC in ctx;
(2) branch 7 row anchor ^(ConTex|NNNN teu); (3) branch 8 accepts freightos in the table's own header;
(4) branch 10 also fires when the unit sits INSIDE each row (the 2023/24 "| Benchmark | <d> | <d> | W-o-W
| Y-o-Y |" era); (5) new branch 10c sends the commodity CHART tables to chart_series and DROPS all-empty
banner rows. Rebuilt from the CACHED markdown - **no API spend**. MEASURED: freight_rates 20,329 ->
**20,249** (-80); sector DRY_BULK 80 -> **0** (the file now has NO DRY_BULK at all - it was only ever the
misroute fallback); fx 968 -> 976; vhss 3,413 -> 3,427; commodities 8,435 -> 8,447; sidecar freightos_index
2,261 -> 2,271; chart_series 38,204 -> 39,425. CONTROLS: function-level diff (HEAD parser vs fixed, all 244
docs) shows the ONLY key that loses rows anywhere is freight_benchmarks, on EXACTLY the 10 named docs,
-80 total - nothing else lost a single row; series md5 **4 of 10 changed** (freight_rates/fx/vhss/
commodities), **6 byte-identical**. Every routed value reconciled cell-by-cell against the document's own
cached page text (no vision tool in this session): 2021_W46 FX, 2022_W43 VHSS+FREIGHTOS, 2026_W38 VHSS,
2024_W24 commodity - all exact. The +1,221 chart_series rows are a SECOND measured fix, not noise: making
branch 9 content-anchored stopped it claiming the FX heading's own chart table, which it read and silently
DISCARDED (194 docs recover rows, e.g. 2026_W24 JPY/USD EXCHANGE RATE). Evidence
**`docs/bancosta_freight_rates_residue_verdict.md`**. NOTE: the BC_DUMP_B11 env dump was added to branch 11
(same pattern as BC_DUMP_FFA).
NEXT TARGETS, both measured this run and NOT fixed:
(1) chart tables published as container indices (same root cause in branches 7/8): `freightos_index`
502 of 2,271 rows / 145 docs and `vhss_contex` 1,713 of 3,427 rows / 218 docs have a unit cell that is
neither a unit token nor a period label (e.g. segment Jul-20, unit 8000);
(2) a SECOND residue in freight_rates itself: **125 rows / 52 docs** whose `unit` is not a unit - a leaked
sub-header row ("AFRAMAX | Unit | 3-Jul | 26-Jun | W-o-W | Y-o-Y" published as data; the `category unit`
header shape, 25 firings corpus-wide), the 2021 era's 7-column `Category | Name | Unit | ...` table where
the label spans two cells (28 rows on 2021_W46 alone), and empty rows. **These PRE-DATE the fix** (the
function-level control proves this run removed exactly 80 rows and added none).
HELLENIC is owned by a separate live session - do not collide.

**THIS RUN (2026-09-29 01:2x): bancosta FFA/FX tier - 5 mis-parse defects FOUND, FIXED and VERIFIED.**
The previous run's leftovers ("93 FFA rows whose tenor is a currency pair; 60 FFA rows with a %
in rate_previous") re-measured to 5 distinct causes in the FFA branch, all from one root: the branch
keyed on `ctx` alone, and the heading tracker keeps h1='DRY BULK FFA ASSESSMENTS' while h2/h3 move on.
Measured 1,881 FFA-branch firings / 244 docs. (1) 7 EXCHANGE RATES tables (28 rows) were filed as FFA
with a one-column shift AND those 7 docs were entirely MISSING from bancosta_fx_series.csv (236 md docs
carry a CURRENCIES table; exactly 7 were absent). (2) 16 chart tables (curve titles / date matrices)
were published as assessments - 9 junk tenor rows. (3) 4 all-empty section rows ('Capesize | | | ...').
(4) 2026_W19's FFA table has NO tenor column in the page read (LlamaParse), so every value sat one
column left. (5) a transposed chart table under EXCHANGE RATES published currency_pair='110'.
FIX = content anchors (uppercase XXX/YYY row test, 'premium' column required for an assessment, unit
cell when the tenor column is absent), never ctx or geometry alone. Rebuilt from the CACHED markdown -
**no API spend**. MEASURED: ffa 7,659 -> **7,618** rows (currency-pair tenors 28->0, curve-title tenors
9->0, blank-unit rows 4->0, W19 32 rows corrected verbatim 32/32); fx 941 -> **968** rows; docs missing
from the FX tier 7 -> 0. CONTROL: 19 of 245 sidecars changed and the diff is confined to 3 keys
(ffa_assessments/currencies/chart_series); **8 of 10 series CSVs byte-identical** - only ffa and fx
differ. Left VERBATIM (not repaired): 2025_W30's 32 garbled tenor labels (ul-25/lug-25/iep-25/...),
which are in LlamaParse's own raw read, so they come from the page - mapping them would be a guess.
Evidence **`docs/bancosta_ffa_verdict.md`**.
STILL OPEN in bancosta: the LlamaParse credit block (HTTP 402 - only the user can rotate the key).
NEXT TARGET, measured this run (do NOT delete these rows - they are NOT duplicates): the
`bancosta_freight_rates_series.csv` DRY_BULK residue is **80 rows / 10 docs**, all misrouted by branch 11
(the same ctx-only gating root cause), in FIVE classes: FX rows (currency pair) 8 rows/2 docs
(2021_W46/W47 - and they are shifted one column: `unit` holds the rate); chart rows whose `unit` is a
NUMBER 25/5 docs; **commodity table rows with a real unit 13/2 docs (2023_W39, 2024_W24 - REAL commodity
data that is MISSING from the commodity tier: those tables' header is `| Benchmark | <d> | <d> | W-o-W |
Y-o-Y |` with no `Unit` column, so the commodity branch's `"unit" in header_str` gate fails and branch 11
grabs them)**; container TC / index rows 24/2 docs (2022_W43, 2026_W38 - REAL container TC data missing
from the container tier); table/heading rows with no unit 10/3 docs. Measured with
`scratch/bancosta_fb_classes.py`. The chart-class rows carry DIFFERENT numbers from the printed
commodity table (chart Brent 70 vs printed 93.00), so they are chart points, not duplicates.
HELLENIC is owned by a separate live session - do not collide.

**THIS RUN (2026-09-28 22:1x): ledger 4.3 CLOSED - intermodal_macro_series.csv had a REAL defect.**
It was recorded as "stated change not reproducible on 1,290 of 3,739 rows, blank on 2,075".
The blank column was real and 5x the story: **EVERY positive change was silently dropped** -
2,075 blanks, and of the 1,664 survivors **0 were positive**, while the publisher prints a
change on essentially every row. Root cause = the macro regex's greedy middle group
`(?:[\s
]+[0-9.,]+)*` swallowed a bare positive number (`1.7%`), leaving `%` with no
preceding whitespace so the trailing `([-+]?[0-9.]+%)` group never matched; a negative change
survives only because `[0-9.,]+` cannot start with `-`. Second fault: a value cell can be TEXT
(`mrkt closed` 23x, `market closed` 3x, `mrkt close` 1x) which stopped the number-only scan
mid-row. Fix = content-anchored row parse in `run_intermodal_finance.py`; NONNUM derived from
the corpus, not guessed. **Measured: blanks 2,075 -> 0; positive changes 0 -> 2,061; rows
3,739 unchanged; latest_value 0 changed; prior_value 6 changed (all '' -> a value the page
prints); change strings verbatim in the source page text 1,664/3,739 -> 3,739/3,739.**
Control: 125 of 126 series CSVs byte-identical (md5) - only macro differs, and stocks/bunkers
are byte-identical, proving the other branches were untouched. The (issue_date, indicator) key
diffs vs a pre-run snapshot are the earlier 4.4 date fix, not this change.
Cross-document control: the printed W-O-W reconciles with the previous report's own Friday
close on **3,160/3,447 = 91.7%** (95-100% for 12 of 16 indicators). **Nikkei 52% and Xetra Dax
57% fit NO reference hypothesis** - values and changes are verbatim on the page, so it is a
publisher-side inconsistency, left as printed. Evidence: `docs/intermodal_macro_verdict.md`.
**NEXT: the only defect left in `docs/series_verification_ledger.md` is the residual ism
agreement tail** (1,178 rows, outlier reports drawn on a different axis). banchero is still
BLOCKED on LlamaParse credits (243/244, HTTP 402) - only the user can rotate the key.
**THIS RUN (2026-09-29 00:2x): ledger section 3 CLOSED - bancosta_commodities_series.csv was
BADLY mis-parsed (55% of rows) and is now FIXED; bancosta_ffa was verified FAITHFUL and left alone.**
The ledger flagged these two only for a low cross-issue continuity score. Reading the pages:
FFA's low score is the PUBLISHER's (it restates the prior week's FFA point by 17% between issues;
both sidecars are verbatim; column swap ruled out 7,475/7,500). Commodities was a REAL defect:
the parser assumed every row has a leading category cell, true for BUNKERS and false for
OIL & GAS / AGRICULTURAL / COAL / IRON ORE & STEEL, so those rows shifted one column right and
lost the item label; the gate also matched the word "category", which is the header of the
commodity CHARTS, so chart points were parsed as prices (1,297 junk rows); and the eras whose
price header is `| BUNKERS | Unit | ... |` fell through to freight_benchmarks as sector=DRY_BULK.
Fix = unit-cell anchor + gate on unit+w-o-w + block name from header/heading/real Category column
+ numeric-current + per-document dedupe, in `run_banchero_world_class_llama.py`. Rebuilt from the
CACHED markdown - no API spend. Measured: commodities 2,319 -> **8,435** rows; numeric unit
1,285 -> 0; % in previous 611 -> 0; empty current 273 -> 0; chart junk 984 -> 0; duplicates
106 -> 0; GENERAL 1,297 -> 33; freight_rates 25,715 -> **20,329**. Controls: 2022_W02 page-12
values 4/4 exact; unmodified parser reproduces the sidecars byte-exact; **2 of 132 series CSVs
changed, 130 byte-identical**; every genuine freight sector count unchanged; 2023/2024 docs went
from 0 to 35 commodity rows. Evidence **`docs/bancosta_commodities_verdict.md`**.
NOTE: `data/extracted/` is gitignored, so the rebuilt sidecars/CSVs are on disk only - the parser
is the committed artefact. NOTE: `run_banchero_world_class_llama.py` was UNTRACKED (34 sibling
runners are tracked); it is now committed.
STILL OPEN in bancosta (measured): 93 FFA rows whose tenor is a currency pair; 60 FFA rows with a
% in rate_previous (32 from 2026_W19); 33 numeric units + 80 DRY_BULK rows in freight_rates.
banchero LlamaParse is STILL credit-blocked (watchdog 23:29 alive=0 credits=0) - only the user can
rotate the key. HELLENIC is being worked by a separate live session (scratch/sup_alibra, runners
started 23:29) - do not collide with it.

**Purpose:** if the machine sleeps, a session dies, or a new context starts with no
memory of this project, this file is the single source of truth. Read it, check the
live state it tells you to check, then continue. Do not restart finished work.

**THIS RUN (2026-09-28 21:31, supervisor 345bc8db9233): ledger 4.5 CLOSED - star_asia_deals
date columns normalised.** `arrival_date` / `beaching_date` held the publisher's European
`DD.MM.YYYY` plus STATUS words (`AWAITING`, `ARRESTED`), so no ISO date join could see them.
Measured, not assumed: 77/77 of the non-canonical values are VERBATIM in the source PDF text
layer, and for the 63 that are not real dates a same-page glyph-advance control (ratio
0.93-1.05 vs clean dates in the same font) proves no glyph was dropped - **the publisher's own
page prints `05.02.206`**. Nothing was guessed. 4,417 date cells are now ISO; 966 typed STATUS;
63 quarantined with the printed value kept; 6 empty. Fix is one call to the new
`scripts/extract/publishers/star_asia_dates.py` at the single choke point in
`run_star_asia_tables.py`, so future full runs are correct too. Verifier
`scripts/extract/verify_star_asia_deals_dates.py` = PASS (3,327 rows unchanged, 39,924 context
cells byte-identical, 0 raw-vs-old mismatches). Evidence: `docs/star_asia_deals_dates_verdict.md`.
**ALSO THIS RUN: ledger 4.4 CLOSED - and its headline number does NOT reproduce.**
Measured across 119 series CSVs / 334,358 date-shaped cells, only **12** calendar-invalid date
cells ever existed (`2026-00-00` x12 in the two Xclusiv CHART files); the 218 rows the entry
blamed on intermodal_macro / maritime_stocks / bunkers are not in those files at all (100%
well-formed ISO; the read-only corpus DB has none either). Fixed 12 fake + **4 wrong** dates (a
plausible `2025-12-10` on `xclusiv-2026_04_20.pdf`), plus `report_week`, which was `0` on all
498 chart rows and is now derived from the issue date (agrees with the tables-tier control on
257/261 = 98.5% of shared documents). Root cause worth remembering: `run_xclusiv_vector_charts.py`
was ALREADY patched at 20:47 but **the patch had never been run** - a fixed parser with stale
output looks exactly like an unfixed defect. Evidence `docs/xclusiv_charts_dates_verdict.md`,
verifier `scratch/sup/verify_xclusiv_charts.py` = PASS. Note: 0 invalid date cells remain
corpus-wide, so any future "fake date" claim needs a stated population.

**Still open and next: 4.3 `intermodal_macro_series.csv` - 1,290 of 3,739 rows whose stated
change is not reproducible from `latest_value`/`prior_value`, blank on 2,075. NOT yet verified
against the page: verify BEFORE fixing (the last three "defects" looked real and were
faithful).**

**CURRENT STATE - 2026-09-28 17:1x. Both old leads are now CLOSED - do NOT reopen them.**

* `corpus/07-signal` is **DONE**: 442 market articles extracted (253 monitors / 179
  newsroom / 10 newsletters) into `data/extracted/md/signal/`, register row `CLOSED`.
  The 9 PDFs the earlier note called "unmatched" are 3 one-off reference PDFs (IMO GHG
  study, GreenVoyage efficiency guide, a 175p Indonesian ministerial report) plus 6
  files that are **HTML served with a .pdf name** (923-byte `	<head>` bodies) or EU
  webpage printouts. Excluded per user prompt. **No runner to build.**
* `corpus/01-brokers`'s 212 unmatched are **resolved** in
  `docs/hellenic_coverage_verdict.md` (176 = the fearnleys-md duplicate folder, the rest
  stem-convention/_nan_ dupes). No gap. **Do not re-audit.**

**THIS RUN (2026-09-28 18:4x): intermodal NEWBUILDING-PRICES defect FIXED and verified.**
The ledger recorded it as "893 rows with price_previous = 0.0"; that diagnosis was wrong
and 5x too small. Every row of `intermodal_newbuilding_prices_series.csv` was shifted one
column LEFT - vessel_type held the vessel SIZE, size held the current price, current held
the previous, previous held the printed +/-%, pct held the 2020 average. Rebuilt from the
**cached** LlamaParse markdown (no API spend; 252/252, 0 failures, 72 s).
3,194 -> **3,134** rows; vessel_type-as-a-size 1,408 -> **0**; blank previous 60 -> **0**;
(cur,prev,pct) self-consistent 1,603 -> **3,112**. Verification: the (current, previous)
pair is a consecutive numeric run in the source PDF's OWN text layer in **3,132/3,134 =
99.94%** (252 docs). Control: all 10 other intermodal series CSVs byte-identical. Also
fixed: a malformed `<td` repair that was losing 2021_W38's whole table, and 40 mislabelled
sector rows. Full evidence: **`docs/intermodal_newbuilding_verdict.md`**.

Run it with Python312 - `llama_parse` is NOT importable from Python314:
`/c/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe scripts/extract/publishers/run_intermodal_full.py --year all --reparse-only`

NOTE FOR THE NEXT RUN: xclusiv is 266/266 DONE (`docs/xclusiv_verdict.md`, 2026-09-26) and
ALL broker sources are CLOSED in the register. The prompt's "next source" list (fearnleys,
affinity, agora, ism, lion, banchero...) is stale - every one of those is built. Work the
open ledger defects below, one at a time.
`docs/series_verification_ledger.md` 7.1 (a one-column shift that published the vessel
SIZE as the price on 537 rows) and 4.3 (75 exact duplicate rows) are closed. Fix is in
`scripts/extract/publishers/run_intermodal_full.py`, rebuilt from the **cached** LlamaParse
markdown - no API spend, 252 docs, 0 failures, 35.5 s. 2,409 -> 2,333 rows; inconsistency
23.0% -> 0.43%; 14 prev-month values recovered from the PDF text layer; the other 6
intermodal series CSVs are byte-identical (control). Full evidence:
**`docs/intermodal_indicative_verdict.md`**.

**NEXT TARGET - pick ONE from the still-open ledger defects** (all measured, none fixed):
1. ~~`carriers_tanker_tce_series.csv`~~ - **CLOSED 2026-09-28 19:0x as FAITHFUL, not a
   defect.** The source page prints `VLCC TCE in $ 25.290 / Week Ch. -4098 / Previous
   29.388` verbatim; the unit switch is the publisher's own. Do not spend time here.
2. ~~`intermodal_newbuilding_prices_series.csv`~~ - **FIXED 2026-09-28 18:4x**: it was a
   one-column shift on every row, not a zero. `docs/intermodal_newbuilding_verdict.md`.
3. `intermodal_macro_series.csv` - 1,290 of 3,739 rows whose stated change is not
   reproducible from `latest_value`/`prior_value`, and blank on 2,075.
4. `star_asia_deals_series.csv` - `arrival_date` is European `DD.MM.YYYY` on **2,680 of
   2,727** non-empty values (a date-join silently drops them) and `beaching_date` holds STATUS
   text (AWAITING 901, ARRESTED 24, the source's own typo AWATIING 17, plus real dates).
   CONFIRMED REAL 2026-09-28.
5. Fake dates `2026-00-00` - **230** rows (re-measured; the original sweep missed
   xclusiv_demolition_charts): intermodal_macro 92, maritime_stocks 72, bunkers 54,
   xclusiv_bulk_carrier_charts 8, xclusiv_demolition_charts 4.
Check each against the source's own PDF page text BEFORE fixing, as this run did.


**PPA IS 87.6 PCT ALREADY EXTRACTED - 2026-09-28 14:33 (supervisor 345bc8db9233).** Do NOT build a from-zero
493-document PPA runner. Measured read-only: corpus/09-ppa holds 493 files but only
**339 distinct contents** (154 are byte-duplicates); the DB already holds **297** of them
(**228,280 cells, 1,335 tables**), i.e. **87.6 pct**. Only **42** distinct documents are
missing - the Port of Dampier FY cargo-statistics one-pagers FY2015-16..FY2025-26. The md
tier IS genuinely 0 pct (no data/extracted/md/ppa*). PPA is already DISPLAYED via
`data/commodities/australia_ppa_iron_ore.csv` (423 rows to 2026-08-01). Full evidence:
`docs/PPA_ALREADY_EXTRACTED_FINDING.md`, `data/extracted/supervisor_verify_20260928_1420.json`,
file list `scratch/supervisor_verify/ppa_42_files.json`. Scope the PPA work to 42 docs.

Last updated: 2026-09-28 18:50 IST (intermodal NEWBUILDING PRICES fixed - one-column shift on all 3,194 rows, 99.94% text-verified; ppa COMPLETE - families A+B+C, 0 failures; family C cross-checked against family A exact to the tonne on 128/132 months) (banchero BLOCKED - LlamaParse credits exhausted, see
ACTIVE JOB below; ism merged-series defect FIXED - see `docs/ism_series_fix_verdict.md`)

**2026-09-28 12:50 note for the next run - READ BEFORE TOUCHING banchero:**
The banchero LlamaParse escalation is **243/244 done and BLOCKED**, not running and not
dead-by-crash. The last document (`banchero_costa_2026_W38_Bancosta-Weekly-2026-38`, 2
ciphered pages, ~6 credits) returns **HTTP 402: "You've exceeded the maximum number of
credits for your plan"** - the free-tier account in the Hermes .env is spent. Only the
user can supply a fresh key (`python3 scripts/tools/set_llama_key.py --key llx-...`).
Do NOT keep restarting it. The ground-truth gate still passes 13/13 on 2026_W03, so the
tier is fine - this is purely a billing wall.
The routing map was rebuilt this run and now covers **244** docs (was 243 - W38 was
missing from it, which is why the runner would have skipped it).
Also: `scripts/tools/watch_banchero_run.sh` restarts with a bare `python3`, which in the
cron environment resolves to the Hermes venv whose `pydantic_core` is a cp311 `.pyd` -
it crashes on import every 30 min. Use the explicit Python 3.14 interpreter instead.
Earlier line follows:

Last updated: 2026-09-28 11:40 IST (intermodal Baltic chart series VERDICT: superseded - see
`docs/intermodal_baltic_series_verdict.md`; all broker sources built per `docs/EXTRACTION_REGISTER.md`)

**2026-09-28 note for the next run:** the live status ledger is now
`docs/EXTRACTION_REGISTER.md` (last written 2026-09-28 02:23, all 18 publishers marked
CLOSED). Its row counts match the artefacts exactly (273,254 rows / 98 CSVs, verified
2026-09-28). Two of its claims do NOT hold under measurement:
1. intermodal's chart-derived `intermodal_baltic_tc_series.csv` (20,348 rows) is held data,
   25-53% off the feed, stale to 2026-08-30 and fails the agreement gate at 59.3% - it is
   not a deliverable (`docs/intermodal_baltic_series_verdict.md`). The table layer IS exact.
2. ism's merged series pass the agreement gate at the median (0.22-0.34%) but have a bad
   tail (p90 20-43%, only 69-74% within 2%) - a subset of its series are mis-keyed.
   NOT yet investigated. That is the next verification target.
Also open: 10 series CSVs carry exact duplicate rows (bancosta_commodities 106/2,319 worst).

**2026-09-28 12:15 - verification ledger written: `docs/series_verification_ledger.md`.**
Register row counts MATCH the artefacts (273,254 rows / 98 CSVs). Four real defects, all
measured, none fixed yet - next run picks one:
1. `intermodal_indicative_values_series.csv` - one-column shift on 295 rows (the vessel SIZE
   `180k` was read as the price in $M). Proven against the printed page. Fix = realign the
   `Vessel 5 yrs old` table where sector and size share a cell.
2. `carriers_tanker_tce_series.csv` - 510/768 rows where `week_change` != current-prev; the
   TCE family is in thousands while the change is in units (1000x-class mix).
3. `intermodal_newbuilding_prices/series` - 893 rows with `price_previous = 0.0` (missing
   written as zero).
4. `intermodal_macro_series.csv` - 1,290 rows whose stated change is not reproducible from
   latest/prior; change blank on 2,075.
5. `ism` merged series - key omits the panel entity (`docs/ism_agreement_tail.md`); this one
   is worth fixing because ism's route rates are NOT held data.
DO NOT chase `intermodal_tanker_spot_series.csv` - its 3.8% score was my checker pairing the
change with the WS column instead of TCE. The file is correct.
There is NO vision tool in the cron session - substitute the same-document text
reconciliation (section 5 of the intermodal verdict) and say so.

---

## READ THIS FIRST

**`docs/MASTER_EXTRACTION_PLAN.md` is the master resumable plan** - source
inventory, proven capabilities, cost routing policy, skip decisions, exact
commands. This file (OVERNIGHT_STATE) covers only what is in flight right now.

---

## ACTIVE JOB RIGHT NOW - do NOT duplicate

**LlamaParse escalation run for banchero_costa is STOPPED - BLOCKED ON CREDITS.**

State: **243 .md files on disk** (measured 2026-09-28 14:4x: `ls *.md | wc -l` = 243).
NOTE: `_run_state.json` now reads "166 done / 29 failed" because a LATER restart over a
78-doc subset overwrote the done list - the 243 `.md` files are the truth, not that counter.
The remaining doc needs ~6 credits and the account is out of them (HTTP 402, all 29 recent
attempts failed on the same 402). Nothing to do until the user rotates the key. The log
mtime was 13:08 when checked at 13:48 (stale) - the run is stopped, not crashed.

- Process: `run_banchero_llamaparse.py --tier cost_effective` (resumable, 243 docs)
- State:   `data/extracted/llamaparse_banchero/_run_state.json`
- Log:     `data/extracted/llamaparse_banchero/run.log`
- Output:  `data/extracted/llamaparse_banchero/*.md`
- Watchdog: `scripts/tools/watch_banchero_run.sh` restarts it if it dies.

WHY: banchero's table text layer is glyph-ciphered (see
`docs/banchero_cipher_forensics.md`). Local decode is impossible - the subset fonts
are stripped and the ToUnicode CMaps are inconsistent with the drawn glyphs. Only a
pixel-reading parser recovers it. LlamaParse does, verified 13/13 against ground
truth at the cheapest tier.

HOW TO CHECK (do this before assuming it is dead):
```
tail -5 data/extracted/llamaparse_banchero/run.log
python3 -c "import json;st=json.load(open('data/extracted/llamaparse_banchero/_run_state.json'));print(len(st['done']),'done /',len(st['failed']),'failed')"
```
It is ALIVE if the log mtime is recent or a python process matches
`run_banchero_llamaparse`. Do NOT start a second one - two concurrent runs
double-spend credits on the same documents.

IF IT IS DEAD: `bash scripts/tools/watch_banchero_run.sh` (it resumes, never restarts
from zero). Credential lives in the Hermes .env, read directly - see
`scripts/tools/set_llama_key.py`.

MEANWHILE: work on OTHER sources only. Do not touch banchero output while the run is
live - it writes those files.

---

## THE RULE (user's explicit instruction, do not violate)

**SOURCE BY SOURCE ONLY.** Each publisher gets its own measured pipeline with its
own treatment. A generic one-size runner across publishers was built and DELETED
on the user's order - a previous mass-extraction attempt "resulted in garbage or
complete fucking crap". Measurement scripts may be shared; the EXTRACTION
strategy must be per-source.

Method for every source, in order:
1. Count PDFs, year spread.
2. RENDER pages from several years and LOOK at them.
3. Write `docs/<source>_survey.md` with the measured facts.
4. Build `scripts/extract/publishers/run_<source>.py` for THAT source.
5. TRIAL on 2+ documents from DIFFERENT years; compare against what you SEE.
   Do not bulk-run until the trial matches.
6. Bulk-run as a BACKGROUND process with `notify=true` (never nohup).
7. Verify by CONTENT (doc counts, row counts, spot-check values against the
   source), then write `docs/<source>_verdict.md`.
8. Commit each step. Branch only, never main.

---

## STATUS

### DONE and verified - do NOT redo
| source | docs | output | notes |
|---|---|---|---|
| advanced_shipping | 249/249 | `data/extracted/md/advanced_shipping/` | VECTOR charts, EUROPEAN numbers (60.000=60000). `docs/prose_merge_verdict.md` records why a prose-fused table defect was ABANDONED. Do not reopen. |
| star_asia | 193/193 | `data/extracted/md/star_asia/` | 3,640 tables. Charts RASTER. ISO numbers. |
| ssy | 519/519 | `data/extracted/md/ssy/` | 5,920 route rows. 1 page/doc. |
| xclusiv | 266/266 | `data/extracted/md/xclusiv/` | 3 passes; prose-anchored rates, 69% labelled, 0 duplicates/stray. `docs/xclusiv_verdict.md`. |
| affinity | 250/250 | `data/extracted/md/affinity/` | 4 cards (BDTI/BCTI, BDA, TCE DIRTY, TCE CLEAN), 0 charts, ISO numbers. Independent verify: 250/250 docs, 0 unaccounted panel values, panel rect constant in 250/250. `docs/affinity_verdict.md`. |
| agora | 213/213 | `data/extracted/md/agora/` | 10,002 rows, 42,013 value words, 3 unaccounted in the whole corpus, 53s, 0 failures. Independent verify: 0 failures, 426/426 semantic crude/Brent gates, 212/212 BDI. US/EU convention switch mid-2022 - derived PER DOCUMENT. `docs/agora_verdict.md`. |
| ism | 112/112 | `data/extracted/md/ism/` | **charts only, NO tables** (measured). SERIES RE-KEYED 2026-09-28: entity key + multi-year axis fix, 32,114 -> 29,948 rows, rows >10% spread 2,269 -> 1,178. `docs/ism_series_fix_verdict.md`. 444 charts, 1,678 series, 84,035 weekly points, 0 failures, ~35 s. 96.8% labelled, 0 mislabelled, 0 unverified axes, 443/444 linear x. `docs/ism_verdict.md` (12 defects found+fixed), `docs/ism_survey.md`. |
| lion | 43/44 (1 skipped) | `data/extracted/md/lion/` + `data/extracted/lion_deals.parquet` + `lion_demometer.parquet` | 1,145 deal rows, 516 demometer rows, runner `scripts/extract/publishers/run_lion.py`. The 44th file is a star-asia reprint (RESTATEMENT, skipped). Verification found and fixed **3 en-bloc pricing defects in 38 of 1,145 rows**; demometer recall 736/736 printed numbers, 0 mismatches. `docs/lion_verdict.md`. |
| ppa family C (per-vessel) | 151/152 (1 skipped, named in the verdict) | `data/extracted/ppa/ppa_hedland_vessel_calls.csv` (38,097 rows, 4,253 vessels, 138 months 2015-01..2026-08) | Runner `scripts/extract/publishers/run_ppa_vessels.py`, 0 failures, 104.6 s. Cross-family control: per-vessel Iron Ore export summed per month reproduces family A's country-matrix total **exactly on 128/132 months**; the 4 others are corpus restatements (two different documents, each internally consistent). 5 defects found by the trial and fixed. |
| ppa (families A+B) | 255 + 83 | `data/extracted/ppa/ppa_hedland_trade_series.csv` (4,591 rows, 133 months 2015-01..2026-08) + `ppa_dampier_fy_series.csv` (4,344 rows, 290 months, FY2002-03..FY2026-27) | Runner `scripts/extract/publishers/run_ppa.py`. 0 failures; arithmetic self-check 6,210/6,210 + 873/873 (100%). Independent control vs the pre-existing `australia_ppa_iron_ore.csv`: Hedland 126/126 months, Dampier 289/290 (the 1 = a documented 2016-10 restatement between two Wayback snapshots). Family C (152 per-vessel PDFs) NOT built. `docs/ppa_verdict.md`, `docs/ppa_survey.md`. |
| fearnleys | SKIPPED | `data/extracted/md/fearnleys/` (record only) | **User decision 03:05: the publisher is already ingested structurally** (Hasura: 11,732 comments, 62MB fixtures, route dailies, T/C, S and P) - the PDFs are a worse copy. An extraction was already in flight and completed anyway: 257/257, 16,326 rows, 267s, 0 failures. Kept as `docs/fearnleys_extraction_record.md` (7 transferable defects). Do NOT re-extract and do NOT treat it as new data. |

### DONE: lion (source 9) - completed, verified and committed 2026-09-24

`docs/lion_verdict.md`. Runner `scripts/extract/publishers/run_lion.py`
(self-contained: PDF -> text -> parse -> parquet + summary + markdown;
`--rebuild-txt` re-renders text from the PDFs).

| measured | value |
|---|---|
| issues | **43/44** (the 44th is a star-asia reprint filed under lion -> RESTATEMENT, skipped) |
| demometer | `data/extracted/lion_demometer.parquet` 516 rows, 43 weeks 2025-10-03 -> 2026-09-04 |
| deals | `data/extracted/lion_deals.parquet` 1,145 rows, 1,117 vessels |
| markdown | `data/extracted/md/lion/` **43 files** (master-plan action 6 for lion: done) |
| recall | demometer **736/736 printed numbers, 0 mismatches**; 1,023 price values, 0 untraceable |
| fixed | **3 en-bloc pricing defects, 38 of 1,145 rows** (see below) |

**ALL BROKER SOURCES ARE NOW BUILT.** Nothing in `corpus/01-brokers/` is unbuilt.

#### Next: non-broker corpora (measured counts, 2026-09-24)

| corpus | PDFs | notes |
|---|---|---|
| `corpus/04-poten` | **1,087** | biggest; poten has feed-side fetchers (`data/derived/poten_*`) - run the three-baseline test FIRST |
| `corpus/09-ppa` | **493** | no runner found |
| `corpus/02-hellenic` | 3,969 | includes the demolition PDFs already consumed by `scripts/extract_demolition_pdfs.py` |
| `corpus/03-breakwave` | 302 | existing fetcher |
| `corpus/06-drewry` | 276 | existing fetcher |
| `corpus/05-seabrokers` | 97 | small |
| `corpus/07-signal` | 9 | tiny |

#### The lion lesson that generalises (it cost 38 wrong rows)

**A group price is the easiest thing in a broker narrative to get wrong, and it
looks perfectly plausible.** Four forms appear in ONE source:
`for $X mill each` (per vessel - fine), `for $X mill` (a GROUP TOTAL - belongs to
no single ship), `for $X mill ($Y mill each)` (Y is per vessel, X the total), and
`for $A mill & $B mill respectively` (two per-vessel prices, mapping by listing
order). Rules that held:
- never let a group total sit in a per-vessel price column - **for the carrier row
  as well as the members** (the bug was exactly that the carrier was exempted);
- a price printed BEFORE the "en bloc" phrase in the same row is that ship's own
  price and must be kept (VS SPIRIT: "- $ 14 mill. Sold en bloc for $ 25 mill",
  where 11 + 14 = 25 - the sentence restates the pair's sum);
- when the mapping is not resolvable, leave it NULL and record the amounts in the
  note. A wrong value is worse than a missing one;
- the tell that catches all of them: **the corpus max price**. It was 831.5 (a
  group total for 8 VLCCs) and fell to 170.0 once fixed.

#### Verifier traps hit this run (do not re-chase)

* A price/buyer check reading only a row's OWN text flags every en-bloc member
  whose buyer sits in the group line. Re-check against the FULL issue text:
  41 flagged, 41 grounded, 0 real defects.
* A checker comparing `str(value)` to the PDF text flags every European
  comma-decimal ("$ 6,75 mill" = 6.75). Include the comma form: 12 flagged,
  12 false positives, 0 real defects.
* Bound a "numbers printed in this block" window at the block's own end, or the
  last row swallows the following prose and reports hundreds of phantom misses.

---

### NEXT: lion (44 PDFs) - source 9, the last unbuilt broker source (historical fingerprint notes, superseded)

**ism is DONE and verified** (`docs/ism_verdict.md`): 112/112, 444 charts,
1,678 series, 84,035 weekly points, 0 failures. It is a CHARTS-ONLY source - a
numeric-row detector fires on 149/266 pages but every hit is a chart's x-axis
tick labels, there is no table anywhere. `scripts/extract/publishers/run_ism.py`
is the model to copy for a vector-chart source: derive the axis from the drawn
tick MARKS, anchor weeks on the publisher's printed labels, label series by
stroke colour only, and leave a series unlabelled when no swatch matches.

LION fingerprint (measured 2026-09-24, start here):

| fact | measured |
|---|---|
| documents | **44** (`corpus/01-brokers/lion/`) |
| years | **2024:1  2025:12  2026:31** - a recent, live publication |
| pages/doc | 2 (4), 3 (36), 4 (3), **20 (1)** |
| text layer | median **10,225 chars/doc**, min 7,658 - the richest text of any source so far |
| drawings | 148 of ~150 pages carry vector content |
| filenames | `lion_<year>_W<nn>_...pdf` |

10k chars/doc is roughly double ism's, so this source is likely to hold REAL
TABLES as well as charts - do not assume the ism approach transfers. Count +
fingerprint first, render pages from 2025 and 2026 and LOOK, then decide.

Remaining sources with NO existing fetcher after lion: **none in 01-brokers**.

Already covered / hands off - do NOT build extractors for these:
* `banchero_costa` 243 - has `scripts/extract/banchero_deals.py` + parquet
  (3,120 deals; 61/243 reports are garbled-text-layer and need OCR this box has not).
* `intermodal` / `carriers` - PARALLEL agents own them.
* `drewry`, `breakwave`, `poten` - existing fetchers; `fearnleys` - skipped as
  already ingested.
* non-broker `corpus/04-poten` 1087, `corpus/09-ppa` 493, `corpus/06-drewry` 276.

---|---|
| page size | portrait A4 595 pt |
| pages/doc | 2 in 2023-2024, 3 in 2025-2026, 6 for the holiday special |
| layout | page 0 = prose commentary + chart, page 1 = more prose (+ chart in 2023), last page = contacts/disclaimer |
| images | 1-2 per doc (logo), so not a raster source |
| drawings | 26-36 per page -> **VECTOR content** |

**2023 W32 page 1 carries a real VECTOR CHART**: title `Average round voyage TCE
(given backhaul leg in ballast), $/day`, y-axis tick labels printed as POSITIONED
TEXT at 5.9 pt (`0, 1500, 3000 ... 16500`, y 697.7 down to 560.3) and week numbers
on x (`33 36 39 42 ...`). Legend labels are also positioned text
(`BlSea - Med RV, 10,000 DWCC minibulker`, `BlSea - Marmara RV, ...`). So the
chart values are exact path data + readable ticks - do NOT reach for vision:
probe `page.get_drawings()`, cluster ticks per chart, fit `value = a*y + b`,
identify series by `drawing["color"]`, and validate the fit against a tick the fit
never saw (the method in the skill). The axis label pitch here is ~12.6 pt per
1500 units, which sets the scale.

Method as always: count + fingerprint several YEARS and LOOK, write
`docs/<source>_survey.md`, build `scripts/extract/publishers/run_<source>.py`,
TRIAL on 2+ docs from different years against what the page says, then bulk-run
as a BACKGROUND process. Verify by content, then write `docs/<source>_verdict.md`.

---

## HOW TO CHECK LIVE STATE (do this before assuming anything)

```bash
cd C:/Users/Dell/Github/Shipping
export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"

# what is running right now
tasklist | grep -i python | head

# progress of the current source (resumable state file)
python3 -c "
import json
st=json.load(open('data/extracted/md/intermodal/_run_state.json'))
print('done',len(st['done']),'failed',len(st['failed']))
"

# file counts per source
for s in advanced_shipping star_asia ssy xclusiv fearnleys; do
  echo "$s: $(ls data/extracted/md/$s/*.md 2>/dev/null | wc -l) docs"
done
```

---

## HARD-WON LESSONS (each cost hours - do not relearn)

- **RENDER A PAGE AND LOOK AT IT.** Every real bug in this project was found by a
  check or by eye, never by a metric. **If the session has no image/vision tool,
  say so and substitute a real check**: reconcile EVERY value-shaped text line in
  the document against the extracted rows, and pixel-test the rendering (render
  the page, confirm the value's bbox contains ink relative to the page's own
  brightness). Do not report a metric as if it were a look.
- **CHECK FOR AN EXISTING FETCHER FIRST.** The user's rule, learned twice: grep
  `scripts/` and `data/derived/` for the publisher before building an extractor.
  fearnleys and (partly) intermodal were already ingested from the publisher's
  own API. Building an extractor for an already-ingested source is pure waste.
- **A SIZE ANCHOR IS NOT PORTABLE.** fearnleys 2023 W39 is the same HTML print
  rendered at ~10% scale: fonts 1.5/1.8/1.3pt where 2026 W18 has 15/18/13.5pt,
  with IDENTICAL positions. An 18pt threshold returned 0 rows on it while
  returning 71 on the normal file. Derive the column from the page (modal x of
  value-shaped cells), never a fixed size or coordinate.
- **MERGE FRAGMENTS ON A BASELINE.** The scaled file splits words: 'W'+'AF/FEAST',
  '$37'+',000', '1 Y'+'ear T'+'/C'. Merge same-y lines with an x-gap under 2pt
  before parsing anything.
- **ARROW GLYPHS ARE PRIVATE-USE CHARACTERS.** A change cell's text is
  `$1.2` + newline + chr(0xF062). A plain `strip()` leaves it, `is_value()` then
  rejects the cell, and EVERY change is silently dropped. Strip U+F000-U+F8FF.
- **A PROBE THAT STOPS EARLY LIES.** The first fearnleys survey declared the
  2021-2022 posters "prose only, no table" because it printed the first 22 lines.
  The table was 1,500pt further down. Read the WHOLE page before concluding.
- **VERIFY WITH A CONTROL that points at the SAME document you measured.**
- **Never assign labels by row order or position.** Match by VALUE, bbox, or exact
  vocabulary; otherwise leave unlabelled. A wrong label is worse than a missing one.
- **Evenly spaced rule chains appear in BOTH tables and charts** - anchor on
  CONTENT (numeric cells per row), not on geometry. A chart's y-axis tick labels
  are plain numbers; they look exactly like a card column (card pitch 105pt,
  tick pitch 45pt - pitch alone cannot separate them, so only values that found
  NO label on their own page are tick candidates).
- **liteparse `ocr_enabled` defaults to ON** and costs ~43 of every 45 seconds.
  Always pass `ocr_enabled=False`.
- **Numbers are PER SOURCE.** advanced_shipping European (60.000=60000);
  star_asia/ssy/xclusiv/fearnleys ISO (29,580=29580).
- **Verify completeness by CONTENT, not file count.** 193 files existing is not
  193 files being correct.
- **Check the data is not already held** before treating a defect as worth fixing:
  look in `data/**/*.csv`, the corpus, and `index.html`.
- **Report MEASURED numbers, never estimates.** Estimates were wrong three times
  in one night in the safe direction.

---

## ENVIRONMENT

- Repo `C:/Users/Dell/Github/Shipping`. Commit on **`benchmark/extraction-comparison`**.
  **NEVER touch `main`.** `scratch/` is gitignored.
- Shell is **MSYS/git-bash**, not PowerShell. Native tools need `C:/...` paths.
- **Long commands get truncated by the tool**: a heredoc over ~5KB silently breaks
  the shell. Write big scripts in 2-3 chunks (`cat >` then `cat >>`).
- CPU-only, ~8 GB RAM: **no two heavy jobs at once.**
- Python: `export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"`
- Installed extractors: `liteparse 2.14.7`, `pdf_inspector`, `pymupdf4llm`, `pymupdf`.
  `opendataloader_pdf` performs badly here (0/35 numbers) - do not use.
  No tesseract / no OCR. LLaMA Parse (paid) is NOT installed.
- User has ~1,155 uncommitted files in the working tree - **do not disturb them**
  and do not `git checkout`/`git stash` broadly.

---

**THIS RUN (2026-09-28 21:2x): ledger 4.4 CLOSED - and it was BIGGER than the ledger said.**
The `2026-00-00` fake dates (230 rows) were the visible tip; the same builders had also written a
WRONG date on 251 further rows, because they searched the report's BODY PROSE instead of its
cover line. `intermodal_2022_W06` was shipped as **2021-10-07** (cover: 15 February 2022);
`intermodal_2023_W08` as **2025-03-31** (cover: 28 February 2023). Three builders, one bug each:
`run_intermodal_full.py`, `run_intermodal_finance.py`, `run_xclusiv_vector_charts.py` (the last
accepted only a `YYYY_MM_DD` filename; xclusiv uses `DD_MM_YYYY`).
Fix = parse the publisher's own cover line first (present and unique on page 0 of **252/252**
intermodal reports), then the filename, then loose text; an unknown date is written BLANK, never a
zero month. Three ORPHAN series (`intermodal_demo_sales`, `intermodal_demolition_prices`,
`intermodal_newbuilding_orders` - no current writer, stale to 2026-09-27) now come off the same
code path. No API spend (cached markdown; `--reparse-only` / `--stack-only`).
Verified: **40,636 / 40,636 intermodal rows across 16 series have `issue_date` == the document's
own cover line (0 wrong, 0 fake)**; `report_week` == the cover week on 252/252; control = 110 of
119 series CSVs byte-identical. Row counts otherwise unchanged.
One count moved and is explained: `intermodal_newbuilding_orders_series.csv` 1,786 -> 1,833 (all
1,833 rows are in the union file, which the old split file was 47 rows short of).
Evidence: **`docs/intermodal_issue_date_verdict.md`**. NOTE: the intermodal stack rebuild hangs on
non-daemon threads AFTER writing its files - judge completion by the file mtimes, not by exit.

**STILL OPEN (pick one): 4.3 `intermodal_macro_series.csv`** (1,290 of 3,739 rows with a
non-reproducible stated change, blank on 2,075 - VERIFY against the page before fixing), and the
residual ism agreement tail (1,178 rows, outlier reports drawn on a different axis).
