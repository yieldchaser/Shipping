**THIS RUN (2026-10-07 11:4x, source-by-source, 30m job) - CLOSED THE ONE ESCALATED ACTION: committed the parked hellenic MMi glyph-fix DATA (260 files) that two prior jobs declined and the hourly supervisor flagged "ACTION REQUIRED BY NEXT COMMITTING JOB". No new source to extract (corpus still complete).**

Branch `auto/extract-fixes-2026-10-07-deepreview` (NOT main). At start: no extraction of ours running; the python.exe processes are Hermes gateways + the hourly supervisor (it wrote its 11:36 run JSON). HEAD was d5bf6b747. Register gate GREEN at start: 180 CSVs / 641,130 rows, 0 mismatches.

- **INPUT:** `data/extracted/supervisor_run_20261007_1136.json` PARKED_UNCOMMITTED - the hellenic iron-ore glyph fix regenerated 258 md + 2 series CSVs at 07:54 by the 07:38 run, KILLED by machine sleep ~08:00 BEFORE committing. Code side already committed (648025a14); data side (260 files) uncommitted. The 11:08 source-by-source run and the 11:11 deep-review both declined it (own-work-only / collision fear); the supervisor escalated it to the next committing job.
- **LIVENESS CHECK:** no writer on those files since 07:54 (5h+). Only other dirty file = `logs/fleet_sync.log` (scheduled sync, not mine - left unstaged). No code file modified. Corpus unchanged: newest content still 2026-10-06 20:03 -> nothing to extract.
- **INDEPENDENT VERIFY BEFORE COMMIT (control; no vision tool in cron - stated):**
  * CSV daily series: 1176 rows, **exactly ONE column differs** (`commentary`), **0 mismatches in every other column** (all numeric/value columns byte-identical). Commentary series: 1180 rows, only `commentary` differs. HEAD carried E-hat 37,121 / t-hook 8,317 / fi 1,591 / fl 663 / ff 370 / tesh 280 / O-macron 231 / t-hook-palatal 63 / ffi 91 / ffl 12 / U+3000 420; the working tree carries 0 of all of them (only the deliberately-kept U+019E, 2, remains).
  * MD: 258 changed files, **259 changed lines** (~1 line each); **0 of all 1,193 iron_ore md still hold a fixable glyph**.
- **COMMIT:** `53b8f4d96` (data only: 258 md + 2 series CSVs), then `6cab0e8d0` (docs: the untracked archive/other survey). Register gate RE-RUN after = still GREEN (180 CSVs / 641,130 rows, 0 mismatches - row counts unchanged).
- **NOT DONE, ON PURPOSE:** the ism "one lever that IS ours" (`docs/ism_agreement_tail.md` section 4 - pick the cluster median instead of the edge reading on multi-report keys). The same doc measured that residual as the PUBLISHER'S OWN axis-label shift (section 3) = faithful; overriding a faithful publisher reading with a cross-report median would make the data LESS faithful. Declined.
- **NEXT:** still nothing to EXTRACT (corpus complete; no new arrivals). Remaining open items are the user's (allied en-bloc residual - vision pass or 6-row override; hellenic bare-name `source_file`; inventory/DB rebuild). Watch that the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 11:0x, source-by-source, 30m job) - FIXED A MEASURED DEFECT in a DELIVERED series: the gibson HTML table classifier was publishing FABRICATED values. Real correction, 19 wrong values fixed + 42 garbage rows removed. Prompts xclusiv/next-source are stale (nothing to extract).**

Branch `auto/extract-fixes-2026-10-07-deepreview` (NOT main). At start: no extraction of ours running (python = Hermes gateways). Closed the ledger's last open item ("the 5 gibson empty rows - confirm against the HTML"). The empty rows were the TIP.

- **ROOT CAUSE:** `run_gibson_html.py` chose market tables by a loose substring over the WHOLE table (`'TD3C' in text or 'Suezmax' in text`). That matched NON-market tables in 8 review/projects files: the **Newbuild and Second Hand Benchmark Values** grid (**$ million** valuations), the **FFA forward-curve matrix** (`-weekly-projects-report-*`), and review-issue "Rates (TCEs at market speed)" grids - each parsed as "Spot Worldscale"; and any table containing "VLSFO" as bunker prices.
- **MEASURED:** 156 HTML files scanned; OLD test matched 153 tables, only 145 are the real grid -> **8 fake spot tables + 3 fake bunker tables** across **8 files**.
- **DELIVERED IMPACT:** `gibson_tanker_spot_series.csv` 3,602 -> **3,555** (**42 fake rows removed**, **15 rows CORRECTED**); `gibson_bunker_prices_series.csv` 1,015 -> 1,015 (**4 rows CORRECTED**). The 19 corrections are the dangerous kind - the fake row had won the dedupe slot and was **publishing a fabricated number** where the page prints the real one (2023-12-15 `TD3C` WS old `79.0` -> real `56.0/67.0`; TC1 `306 -> 149`; TD25 `305 -> 156`; same on 2024-07-05 and 2024-12-20).
- **FIX (per-source, runner only):** a table is SPOT only if a row's first cell matches the publisher's own `TD3C VLCC AG-China WS` label pattern; BUNKER only if a row is `<Port> <Grade>`. Plus a blank-first-cell guard (drops the real grid's trailing spacer row). No geometry, no file list.
- **MD (primary deliverable):** exactly **9 .md + 9 .tables.json** changed; other 147 byte-identical to HEAD. (An early pass blanked `source_url` on all 156 and CRLF-churned them - both fully undone; recovered the url from `gibson_all_reports_catalog.json`.)
- **VERIFY (no vision tool in cron - stated):** (1) every corrected value is a verbatim token in the source HTML (checked 2023-12-15 / 2024-07-05 / 2024-12-20 - 0 missing); (2) control - every key common to old+new CSV is byte-identical except exactly the 15 intended corrections, 0 rows added; (3) old-vs-new table test differs ONLY on the 8 fake tables.
- Register synced spot 3,602 -> 3,555; `verify_registers.py` = **ALL PASSED (180 CSVs / 641,130 rows, 0 mismatches)**. Evidence `docs/gibson_verdict.md`.
- Also: killed a stale hung `git.exe` (from a timed-out earlier command) that held `.git/index.lock`.

- **NEXT:** nothing to EXTRACT - corpus complete (no new arrivals; newest still 2026-10-06). The gibson item is now CLOSED. Remaining open ledger items are the user's (allied en-bloc residual - needs a vision pass or the 6-row override; hellenic bare-name `source_file`; inventory/DB rebuild) and the residual ism agreement tail. Watch that the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 06:5x, source-by-source, 30m job) - NOTHING TO EXTRACT (independently re-measured this run); closed the two questions the 05:4x run left open, with measured evidence. No data change.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (NOT main). At start: no extraction of ours running (the python.exe processes are Hermes gateways only); register gate GREEN `verify_registers.py` = **180 CSVs / 641,177 rows**, 0 mismatches with JSON and MD. Newest corpus content still 2026-10-06.

- **1. The 05:4x run's "NEXT" candidates are all ALREADY HELD -> SKIP (three-baseline test done this run).** It proposed re-checking `corpus/04-poten` (1,087), `corpus/06-drewry` (288), `corpus/09-ppa` (518) behind the three-baseline test before building. Measured now: **poten md 1,087** (`data/extracted/md/poten/<2004..2026>`, register `run_poten_clean.py`, 1,087 opinions metadata + top-charterers + fixtures series); **drewry md 849** (`md/drewry/{ais,ais_charts,opinions}`, register 276/276 + 10 AIS series); **ppa** delivered as CSVs (`data/extracted/ppa/ppa_hedland_trade_series.csv` 4,591 + `ppa_dampier_fy_series.csv` 4,344 + `ppa_hedland_vessel_calls.csv` 38,097; families A+B+C built, cross-checked exact to the tonne). All three absent-from-feeds / md-present / displayed -> nothing to build.
- **2. Whole-corpus coverage re-enumerated.** Every `corpus/*` folder has an extraction tier: 01-brokers 3,099 pdf (all 15 publisher subdirs md-covered), 02-hellenic 8,029 (iron_ore 1,193 md / demolition 1,643 / shipbuilding 165 = the breakwave+clarksons cross-files, control-checked no gap / vv 255 / dry+tanker charter 265 each), 03-breakwave 3,504 md, 04-poten 1,087 md, 05-seabrokers 98, 06-drewry 849 md, 07-signal 446 md, 08-baltic html+md, 09-ppa CSVs, 10-companies 1,310 md (SEC), archive exhausted (allied/golden_destiny/seasure/dnf). Matches `docs/corpus_registry_audit_verification.md` ("no unbuilt source"). **No unextracted recurring publication exists.**
- **3. Ledger section 4 item 3 (exact-duplicate rows) TESTED AGAINST THE SOURCE - claim does NOT hold; do not blanket-dedupe.** Re-measured: 7 files, **31 exact-dup rows** (hellenic_vv_matrix 15, gibson_tanker_spot 5, xclusiv_sales 5, poten_top_charterers 2, star_asia_deals 2, carriers_sales 1, star_asia_ferrous_scrap 1). The worst files the ledger named (bancosta_commodities 106, intermodal_indicative_values 75, intermodal_tc_rates 48) now carry **zero**. Reconciled each remaining row against its OWN source text layer (pymupdf; no vision tool in cron - stated): **xclusiv JINGJIANG NANYANG appears 4x on the page and the CSV holds 4 byte-identical rows; ZHOUSHAN CHANGHONG 4 occurrences / 4 rows** -> the publisher genuinely repeats the entity, so removing the "duplicates" would delete faithful rows. gibson's 5 rows carry no values at all (category header parsed as data). Verdict recorded in `docs/duplicate_rows_source_verification.md`: not proven double-ingests; only the gibson empty rows are a candidate, and only after an HTML check. **No data changed.**
- Register gate re-run after the doc: still GREEN (180 / 641,177).

- **NEXT:** there is no source to extract; the corpus is complete. The only tractable open item left in the ledger is the gibson empty-row/HTML check (item 3 above) and the residual ism agreement tail; the rest are the user's (allied en-bloc residual, hellenic bare-name `source_file`, inventory/DB rebuild). Watch that the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 05:4x, source-by-source, 30m job) - STARTED + COMPLETED a NEW source: DNF ANALYSIS "Dry Bulk Weekly Brief" 38/38, 0 failures. Real new extraction. Archive/other is now exhausted (see last line).**

Branch `auto/extract-fixes-2026-10-06-deepreview`. Nothing of ours was extracting at start (no `_run_state.json` for DNF, no runner). Register gate GREEN at start (178/640,383).

**SOURCE:** `corpus/archive/other` holds 130 PDFs = 5 publications (`docs/archive_other_survey.md`); the largest unextracted one was DNF Analysis, **38 docs** 2021-07-05..2022-05-09. Enumerated by the `dnfanalysis` content token, NOT by filename. GENUINELY_MISSING (feeds, md tier, index.html all absent). BACKFILL_ONLY (>500 d).

**TWO LAYOUT ERAS - the trap:** era A (2021 W26-W32, 6 docs, 7 pages, "DRY BULK WEEKLY") orders the S&P table `Ships Sold | Built | DWT | Price | Buyer | Owner`; era B (2021 W33 - 2022 W18, 32 docs, 4 pages, "DRY BULK WEEKLY BRIEF") orders it `Vessel Name | DWT | Built | Price`. **Built and DWT swap order between the eras** - a fixed x-cut swaps the year into the tonnage on one era. Every threshold is derived from each page's own header row.

**MEASURED:** 38/38 md + .tables.json, 0 failed, 0 files <1KB, 115-125 s (88 non-DNF PDFs scanned + skipped). `dnf_secondhand_transactions_series.csv` = **521 rows** / 38 issue dates. `dnf_bunker_prices_series.csv` = **273 rows** / 32 issue dates.

**VERIFICATION (no vision tool in this cron session - stated):** (1) verbatim token reconcile against each document's OWN text layer, per page - vessel_name **521/521 = 100%**, dwt **517/517 = 100%**, price_raw **481/481 = 100%**, built_year 6/6, bunker value **273/273 = 100%**, **0 mismatches**; (2) pixel-INK test on rendered pages (W26 `177,066` 696 dark px/1,775; W18 `206,331` 916/1,976). `scratch/verify_dnf.py`.

**TRIAL caught 5 real bugs BEFORE bulk** (each found by the check, not by a metric): prose/news panel + chart panels leaking into the table; WEEK-column integers read as values; a second header line (`Price (US$)`, `of Buyer`) bleeding into row 1; multi-word names with a trailing number shredded across columns (`ZHONG XING DA 98`); and multi-line name cells joined in x order (`NAVIOS MARCO POLO` read as `NAVIOS POLO MARCO`). The 5th bug's first fix was itself wrong (gap chained against the cluster's FIRST word, not its LAST).

**FAITHFUL, not defects (verified on the page):** 2021 W33-W50 print a stray **`£`** glyph where `$` is meant (preserved in `price_currency`, never rewritten); `UNION ERWIN` built prints **`4022`** (publisher typo, kept as raw string); `SILVIA GLORY` prints no price (left blank); 5 `ORIENT *` rows print **`EN BLOC`** in the price cell (lot sale, `price_m` NULL - no fabricated number).

**RESIDUE (named):** bunker series is 273 of an expected 288 - 5 docs emit 2 of 3 weekly rows (`W33, W34, W35, W39, W40` 2021); every emitted value is verbatim. Era A's demolition + newbuilding tables and the 3 commodity charts are in the .md but not typed (survey section 5).

Register synced 178 -> **180 CSVs / 641,177 rows**; `verify_registers.py` = ALL PASSED (100.0%). Commits `5e16fb888` (runner+survey+verdict), `0ab657d33` (data+register).

- **NEXT:** `corpus/archive/other` is now exhausted - seasure 86/86 (04:1x run) and dnf 38/38 (this run) are the only two real recurring publications in it; UP Oil (2) / Psarras (1) / hellenic recycling 1 = SKIP (no cadence / held family). The whole `corpus/archive/*` backfill is therefore DONE (allied, golden_destiny, seasure, dnf; anchor/other-stragglers SKIP). Next source must come from OUTSIDE the archive: re-check `corpus/04-poten` 1,087 / `corpus/09-ppa` (87.6% already in the DB - scope to the 42 missing FY docs) / `corpus/06-drewry` 276, each behind its own THREE-BASELINE test before building. Watch that the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 04:1x, source-by-source, 30m job) - TWO things: (1) APPLIED the parallel 3-hourly review job's verified golden_destiny label fix (e047719da) to the DELIVERED series; (2) STARTED + COMPLETED a NEW source: SEASURE 86/86. Real new extraction.**

Branch `auto/extract-fixes-2026-10-06-deepreview`. Working tree clean at start; nothing of ours extracting; NO new corpus arrivals (newest still 2026-10-06 20:03). xclusiv 271/271 = done (prompt stale). Register gate GREEN at start (177/638,931).

**1. golden_destiny label fix APPLIED to data (was left as a pending human item by the 03:47 review job).** The fixed runner was committed but the delivered CSV still had 100% `per_unit_label=US$/Dwt` and page-level `section`. Re-ran the runner over all 252 docs (252/252, 0 failed, 244s).
  * md control: all 252 `.md` BYTE-IDENTICAL (labels are not in the md - primary deliverable untouched). 160 `.tables.json` updated.
  * CSV: 5,320 rows (unchanged count); **0 changes in any value/entity column**; section changed on **1,665** rows, per_unit_label on **868** (Dwt 4452 / Teu 643 / Cbm 225).
  * Control vs the source page geometry (2024 W47 p3): XIDI->TANKERS, MARVEL SWAN->GAS TANKERS/US$/Cbm, BF TIGER->CONTAINERS/US$/Teu (all previously 'GENERAL CARGO/US$/Dwt'). Per-unit values check out (213M/170,619 CBM=1248.4; 20M/2,824 TEU=7082.15).
  * Commit `af421ed2c` (data only). Register GREEN after.

**2. NEW SOURCE - SEASURE ("Summary Sales"), corpus/archive/other, 86 PDFs 2021-2023.** The hourly job had sub-classified archive/other into 5 publications (`docs/archive_other_survey.md`); Seasure is the largest and GENUINELY_MISSING (feeds/md/app all absent). BACKFILL_ONLY (newest 2023-03-31).
  * Runner `scripts/extract/publishers/run_seasure.py` (per-source). Survey `docs/seasure_survey.md`.
  * Shape: text-layer grid, sections BULKER/TANKER/CONTAINER, cols Name~17 Type~107 DWT~150 Yard~182 Built~240 USD~276 Comments~313 VV~383 Buyer~404 Seller~497; geometry verified identical 2021 & 2023; ISO numbers; Yard/Comments WRAP so rows are anchored on the DWT numeric and assigned to columns by header-derived x-boundaries.
  * TRIAL caught 2 real bugs BEFORE bulk: (a) header tokens are one-per-dict-line -> same-line header detection failed (0 deals); (b) greedy row band absorbed the next section heading + repeated header row + the `-1.5%` change token into a section's last row (dwt=None, VV=-1.5) -> tight bands (hi<=ry+7.0) + heading/header/percent exclusion. After fix: 2021 18/18 rows, 2023 12/12 rows, 100% name & price verbatim vs the page.
  * MEASURED bulk: **86/86 md + tables.json, 0 failed, 93s** (130 docs scanned, non-Seasure skipped). Series `data/extracted/series/seasure_sales_series.csv` = **1,452 rows / 86 docs, 86 issue dates 2021-07-09..2023-03-31, 0 blank date/name**. Full-corpus reconcile: **name verbatim 1452/1452 (100.00%), price verbatim 1441/1452 (99.24%)**; the 11 misses are BLANK en-bloc rows (e.g. 5x MR2 to Ridgebury Tankers) where the page prints no per-vessel USD value - left blank, not fused.
  * Register synced 177 -> **178 CSVs / 640,383 rows**; gate GREEN. Commits `36a321a26` (runner+survey), `103f05871` (data+register).

- **NEXT:** the same per-source method on the next GENUINELY_MISSING archive publication: **DNF Analysis "Dry Bulk Weekly Brief" (38, corpus/archive/other)** per `docs/archive_other_survey.md` (iron-ore port inventory W/W%). Then archive/other is exhausted (UP Oil 2 / Psarras 1 / hellenic recycling 1 = SKIP: no cadence / held family). Watch that the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 03:3x, source-by-source, 30m job) - NOTHING NEW TO EXTRACT (independently verified); advanced the one open defect: full per-row PAGE-EVIDENCE classification of the allied en-bloc residuals + a MEASURED proof that no automatic binder is trustworthy. New doc, no data change.**

- **Liveness/state:** no process of ours extracting (python = Hermes gateways only). Branch `auto/extract-fixes-2026-10-06-deepreview`. Register gate GREEN: `verify_registers.py` = 177 CSVs / **638,931** rows, 0 mismatches. **No corpus arrival since 2026-10-06 20:03.** All sources built - prompt's "next source" list is stale (measured md: fearnleys/intermodal 257/affinity 249/banchero 249/agora 219/carriers 137/ism 115/lion 48/xclusiv 271 - all present).
- **Input/subject:** the 7 allied rows >USD 200m left unlabelled by the 02:1x fix (`docs/allied_enbloc_verdict.md`).
- **Method (no vision tool in cron - stated):** read each row's OWN page text layer (the skill's mandated substitute).
- **RESULT - 6 of 7 are lot/package totals wrongly in the per-vessel column, 1 is legit:**
  * KEEP `HYUNDAI SAMHO 8196` 234.0 - page prints `$ 234.0m each` (Coolco LNG newbuildings) = per-vessel.
  * LOT totals: `GASLOG SYDNEY` 284.0 (2 LNG, CDB Leasing), `JUDITH SCHULTE` 260.0 (2 container, undisclosed), `HL AQUAMARINE` 291.0 (5 HL VLOC, Golden Ocean), `HARRISON BAY` 238.0 (6 BAY MR, Intl Seaways), `SKS DEE` 239.0 (8 SKS AFRA, TORM A/S - `in cash & 5.5m shares`, no `en bloc` word), `MP THE GRONK` 242.0 (4 MP THE PMAX, MSC).
- **WHY NOT BOUND (measured, so nobody rebuilds it):** Rule A ("price X joined to `en bloc`/`in cash` in page text, not `each`") fires on **55** rows - far too broad. Rule B (A + consecutive same-Size/name run with the row the only priced member) fires on **14** but **MISSES 4 of the 6 confirmed lots** AND includes a mis-parse (`GALAXY`, stored name is wrong). A rule that over-fires AND misses the confirmed set cannot write values. Left unchanged per "a wrong value is worse than a missing one".
- **Evidence:** `docs/allied_enbloc_residual_page_evidence.md` (verbatim page quotes per row; the 14-row structural candidate list marked OPEN; two safe routes = vision pass OR a 6-row verified override). Scratch: `scratch/allied_footer_lot_audit.py` (55), `scratch/allied_footer_lot_audit2.py` (14), page-text caches `scratch/allied_resid/*.txt`.
- Commit: `d01ccb589` (docs only; scratch is gitignored).
- **NEXT:** nothing to EXTRACT. Open user items unchanged: (a) the allied en-bloc residual - now needs only a mechanical vision pass or the 6-row override; (b) hellenic bare-name `source_file`; (c) inventory/DB rebuild. Watch the automation does not re-stale the register.

---

**THIS RUN (2026-10-07 02:1x, source-by-source, 30m job) - nothing new to EXTRACT (verified); fixed a REAL measured defect the hourly supervisor flagged in the allied series: en-bloc LOT TOTALS were sitting in the per-vessel price column (lion-class). Committed on the current branch.**

- **Liveness/state at start:** no extraction of ours running (python = Hermes gateways only); working tree essentially clean; register gate GREEN `verify_registers.py` = 177 CSVs / 638,931 rows, 0 mismatches. No new corpus arrivals since 2026-10-06 20:03. xclusiv 271/271, all brokers built, archive backfill (allied+golden_destiny) done -> nothing to extract.
- **Input:** `docs/allied_enbloc_price_finding.md` (hourly supervisor, read-only) + it was untracked -> now committed.
- **Defect, confirmed against the pages (pymupdf text; no vision tool in cron - stated):** allied prints a multi-ship lot's value once, next to `en bloc`, and the parser read it as one vessel's price. 15 rows > USD 200m (max 660.0 on an MR row). Pages: STH OSLO `$ 330.0m en bloc` (9 STH UMAX; 220+110 cash+shares), KOOL FIRN `en bloc $ 660.0m` (4 KOOL LNG), ISTANBUL `$ 222.5m en bloc`, DAEWOO 5497 `$ 245.0m en bloc`.
- **FIX in `scripts/extract/publishers/run_allied.py`** (per-source, not generic): `_lot_binding()` = consecutive rows on a page sharing the SAME size class AND the SAME fleet name-prefix that CONTAIN `en bloc`; the single money amount among them is the lot total -> blanked in `price_usd_m`, written to a NEW `group_total_mil` column. Own-cell (`$ X en bloc` in one cell) always binds.
- **REJECTED after measurement (recorded so nobody rebuilds it):** a page-text "nearest money to en bloc" binder blanked LEGIT prices (ERAWAN 10 $12.0m, DOLPHIN 03 $18.0m) - a wrong value is worse than a missing one. Ambiguous runs (>=2 amounts) are left unlabelled.
- **MEASURED:** rows 3,218 unchanged; `price_usd_m` max **660.0 -> 291.0**; rows >200m **15 -> 7**; **52** lot totals moved. Re-run 203/203, 0 failed, 202s. **md control: all 203 `.md` byte-identical** (md5 before/after) - only the CSV changed. Neighbour control kept legit prices (RIDGEBURY SATURN 18.0, MARY SELENA 31.0, LESSLEY 45.0). Register gate GREEN after (638,931).
- **RESIDUAL (named, classified by eye, NOT auto-bound):** 7 rows >200m remain - 1 LEGIT (`HYUNDAI SAMHO 8196` 234.0, page says `each`); 6 are lot/package totals (`HARRISON BAY` 238, `JUDITH SCHULTE` 260, `HL AQUAMARINE` 291, `GASLOG SYDNEY` 284, `MP THE GRONK` 242, `SKS DEE` 239) that need a page RENDER (vision pass) to bind safely. Full table in `docs/allied_enbloc_verdict.md`.
- Commits: `5e9b6eba3` (runner+docs), `499d1cf04` (CSV), `b7a2b0ab6` (_deals.jsonl).
- **NEXT:** nothing to EXTRACT. Remaining open ledger items are intermodal_macro (already fixed, `docs/intermodal_macro_verdict.md`) and the residual ism agreement tail. Carried items remain the user's (hellenic bare-name `source_file`, inventory/DB rebuild). Watch the automation does not re-stale the register.

---

**THIS RUN (2026-10-06 23:5x, source-by-source, 30m job) - STARTED + COMPLETED archive backfill source 2: GOLDEN_DESTINY 252/252, 0 failures. Real new extraction.**

- Branch `auto/extract-fixes-2026-10-06-deepreview`. Runner `scripts/extract/publishers/run_golden_destiny.py` (per-source). md 252 + tables.json 252, 0 files <1KB. Deals CSV `data/extracted/series/golden_destiny_sales_series.csv` = **5,320 rows**, 4,911 vessels, 170 issue dates 2021-07-02..2024-11-29 (**0 blank date/name/dwt/price_raw**).
- md fidelity (no vision in cron -> same-document text reconcile, stated): **100.00% token recall** on a random 6-doc sample spanning 2021-2024 + BOTH classes.
- 81 of 252 are 1-page `Special-Edition` stat cards (aggregate -> md only, 0 typed rows, same call as allied's SnP-Statistics).
- **Trial + verify caught 5 real bugs before trusting output:** (1) cover `30th2022` no-space -> 160 dateless rows; (2) `S SANTIAGO`/`BASHUNDHARA LPG CHALLENG` fused to spec -> 12 blank names; (3) `TOVIETNAMESE BYRS` fused buyer; (4) **section headers `SECONDHAND TONNAGE SOLD FOR FURTHER TRADING` matched the SOLD anchor -> 58 WRONG rows** (now dropped); (5) `SOLD ENBLOC AT HIGH $ 60 MIL`/`ABT US 71.6 MIL` phrasings missed -> 21 blank prices. En-bloc handled by the lion rule (EACH=per vessel; 730 group totals left out of the per-vessel price column).
- Register synced: 176 -> **177 CSV series**, rows 633,611 -> **638,931**; `verify_registers.py` = ALL PASSED (100.0%).
- Evidence `docs/golden_destiny_survey.md`, `docs/golden_destiny_verdict.md`. Liveness: newest 2024-11-29 (~675d) -> BACKFILL_ONLY.
- NEXT: archive backfill's real sources are now DONE (allied, golden_destiny; gibson already had md). Remaining archive = `anchor` (30, overlaps held data) + `other` (130, not one publisher) = **both SKIP** per the survey. Nothing else to EXTRACT in the archive body.

---

**THIS RUN (2026-10-06 22:2x, source-by-source, 30m job) - STARTED + COMPLETED the archive backfill's first source: ALLIED 203/203, 0 failures. This is real new extraction, not a re-statement.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (commit on the current branch, never main). Register gate GREEN after sync: **176 CSVs / 633,611 rows** (was 175 / 630,393).

- **Why started:** the only unextracted body left is `corpus/archive/*` (615 PDFs after the gibson correction). allied is GENUINELY_MISSING (absent from feeds, our md tier, and index.html) and is PHASE-1 extraction (md) - the user's standing order to "START THE NEXT SOURCE". Per-source pipeline, not the deleted generic runner.
- **MEASURED RESULT:** runner `scripts/extract/publishers/run_allied.py` (per-source). **203/203 docs, 0 failed.** md 203 + tables.json 203, 0 files <1KB. md fidelity vs the PDF text layer = **100.00% token recall** on a random 6-doc sample spanning 2021-2023 + both classes (no vision tool in cron -> same-document text reconcile, stated). Deals CSV `data/extracted/series/allied_sales_series.csv` = **3,218 rows**, 3,020 vessels, 130 dates 2021-07-04..2024-02-16, 0 blank dates.
- **Typed layer reconciled:** vessel name verbatim **3,214/3,218 = 99.88%**; price token **2,426/2,427 = 99.96%**. The 4 name misses are spaced-letter artifacts.
- **TRIAL caught 3 real bugs before bulk** (the reasons a bulk run would have shipped garbage): (1) one header per page misaligned the SECOND sub-table on a shared page -> now segments every page by header row; (2) midpoint/header-left column cuts bled wrapped Shipbuilder/Coating text across columns -> now assign each word to the NEAREST header anchor; (3) gear text bled into Price -> money token split out.
- **Disclosed residuals (not hidden):** container sub-tables print TEU+Built as one token (`26642009`) -> dwt blank/built fused; en-bloc member rows show `each` with blank price; 1 price row with a capacity bleed; SnP-Statistics nested sector tables are in the md but not typed (aggregate stats, not a deal series).
- **Evidence:** `docs/allied_survey.md`, `docs/allied_verdict.md`.
- **NEXT:** same per-source method on **golden_destiny** (252, mixed number convention - derive per page). anchor (30, overlaps held data) + other (130, not one publisher) remain SKIP. All BACKFILL_ONLY (>180 d) - never CONSTRUCT.

---

**THIS RUN (2026-10-06 21:0x, source-by-source, 30m job) - nothing to EXTRACT (re-verified); produced the MISSING INPUT for the one open decision: a read-only fingerprint survey of `corpus/archive/` (`docs/archive_backfill_survey.md`). NEW measured correction: the archive body is 615 PDFs, not 724 - gibson is already done.**

Branch `auto/extract-fixes-2026-10-06-deepreview`, working tree CLEAN (0 files) at start. Live python = Hermes gateways/proxy only, nothing of ours extracting. Register gate GREEN: `verify_registers.py` = ALL PASSED (175 CSVs / **630,393** rows == JSON == MD, 0 mismatches). xclusiv 271/271 (year-partitioned). Newest corpus mtime = the 2 best_oasis PDFs from 20:03 (already extracted).

- **CORRECTION (measured now):** stem-matched all 724 archive PDFs against all 28,320 md stems -> **golden_destiny 252 + allied 203 + anchor 30 + other 130 = 615 unmatched**; **gibson 109/109 ALREADY has md** (`data/extracted/md/gibson/` = 265 md, 2021-2026 - a LIVE source fed from `01-brokers/gibson/html/`). The standing "724 archive PDFs" over-counts by 109.
- **Per-source fingerprint (seeded samples across every year dir):** golden_destiny 252 (2021-2024) = S&P weekly reports (vector charts ~1000 draws/pg) + 81 chart-only 1-page "Special Editions"; numbers MIXED (2021 pure ISO, 2022+ both comma-decimals AND period-thousands -> derive per page). allied 203 (2021-2024) = dense S&P Statistics tables (9 pp) + weekly reviews (12-14 pp); **pure ISO** (simplest). anchor 30 (2021-2022) = weekly market report, MIXED numbers, timeframe overlaps held data -> SKIP. other 130 (2018-2023) = heterogeneous, not one publisher -> SKIP until sub-classified.
- **Three-baseline test:** golden_destiny + allied are absent from feeds/series CSVs, from our md tier, and from index.html -> GENUINELY_MISSING. (grep "anchor" hits in drewry CSVs = the word *anchorage*, not the publisher.)
- **Liveness gate:** newest archive content = 2024 (>700d) -> every archive source is BACKFILL_ONLY, never CONSTRUCT.
- **NOT started any extraction** - BACKFILL_ONLY and the user gates depth. The survey is the input for the go/no-go. If green-lit, order = allied (best value) > golden_destiny > anchor/other SKIP.

NEXT RUN: nothing to EXTRACT. Open user decision unchanged + now informed: go/no-go on the archive backfill (615 PDFs, 3 real sources). Watch the automation does not re-stale the register (`verify_registers.py` gate / `sync_extraction_register.py` fix).

---

**THIS RUN (2026-10-06 20:5x, source-by-source, 30m job) - NOTHING TO EXTRACT (independently re-verified by a NEW date-coverage method); all green. The ONLY unextracted body left is `corpus/archive/*` (724 PDFs, newest content YEAR 2024 = >640d) = BACKFILL_ONLY per the liveness gate - needs the user's go/no-go.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD 32b0decd4, working tree CLEAN = 0 files). Live python = Hermes gateways/proxy only; nothing of ours extracting. Register gate GREEN: `verify_registers.py` = ALL PASSED (175 CSVs / **630,393** rows == JSON == MD, 0 mismatches).

- **NEW METHOD this run (not a re-statement of prior runs):** per-source DATE-coverage sweep (content-filename dates vs md-filename dates) + an `os.scandir` mtime scan of the corpus tree (`find` over it times out on MSYS - use scandir).
- **Arrivals:** only 2 corpus files touched since 19:30 = the 2 best_oasis PDFs the 19:4x run copied in (mtime 20:03). No new downloads this window.
- **baltic:** 2,228/2,228 non-asset HTML have md; the 820 "unmatched" are `assets/` weekly-roundup/related-link pages (secondary), NOT the reports.
- **drewry / breakwave / poten:** parity - breakwave 1,649/1,649 dates; poten the only 2 "missing" are regex artifacts (`2017-20-17`, `2019-20-20`), not real dates.
- **seabrokers:** the single pdf-without-md (`2023-12-01_market-report-december-2023.pdf`, 35 KB) is **HTML served as .pdf** (magic bytes `<!DOCTYPE html>`) -> junk, correctly skipped (skill's HTML-as-PDF rule). Not a gap.
- **hellenic demolition** (athenian/gms/best_oasis): all content dates covered; 4 apparent athenian gaps are md named date-first (`2024-12-23_Week_51_Athenian_Demo_Report`), not missing.
- **01-brokers:** 11 stem-unmatched PDFs, all known duplicate re-downloads (already verified in prior runs).
- **ONLY unextracted body remaining = `corpus/archive/`:** allied 203 / anchor 30 / gibson 109 / golden_destiny 252 / other 130 (724 files). Newest content YEAR: allied+golden_destiny 2024, gibson+other 2023, anchor 2022 -> all >640d old -> **BACKFILL_ONLY, never CONSTRUCT** (liveness gate). Constructor (golden_destiny 252 / allied 203) would be a multi-run per-source build; NOT started unattended - the user gates depth.

NEXT RUN: nothing to EXTRACT. Watch the automation does not re-stale the register (`verify_registers.py` is the gate; `sync_extraction_register.py` is the fix). Open user decision: go/no-go on the archive backfill.

---

**THIS RUN (2026-10-06 19:4x, source-by-source, 30m job) - FOUND + FIXED 2 genuinely unextracted best_oasis weekly reports (2026-05-05, 2026-05-16). Not a re-statement: a date-coverage sweep across the 3 hellenic demolition publishers (best_oasis/athenian/gms) surfaced them. Evidence `docs/best_oasis_coverage_verdict.md`.**

Branch `auto/extract-fixes-2026-10-06-deepreview`. Working tree was CLEAN (0 files) at run start; live python = Hermes gateways + litellm only, nothing of ours extracting. Register gate GREEN at start (630,357).

- **ROOT CAUSE:** `run_best_oasis_demolition.py:37` globs only `corpus/02-hellenic/demolition/pdfs/best_oasis/` (flat). The 2 reports lived only in the PARENT `pdfs/` dir -> never extracted. Real `%PDF-` files (4 pages), cover line present.
- **FIX + MEASURED RESULT:** copied the 2 PDFs into the runner's source dir, re-ran the canonical pipeline. **219/219, 0 failed.** md 269 -> **271**; whole-md-dir diff = exactly the 2 new md + 2 tables.json, **0 existing md changed** (md5 before/after). Series rows: demolition 867->875, deals 892->897, exchange 167->169, commentary +21; `hellenic_best_oasis_*` mirrors updated. Register synced 630,357 -> **630,393**; `verify_registers.py` = **ALL PASSED, 0 mismatches**.
- **FAITHFULNESS (no vision in cron -> same-document text reconcile):** all vessel names / LDTs (3,736/2,334/1,694/10,809/3,665) / price 415 / indicative prices / FX present VERBATIM in each PDF text layer. 2026-05-05 page 3 prints "No vessel sale to report this week" and correctly added 0 deals rows.
- **NOT gaps (checked, do not reopen):** athenian 2026-06-13 (md held under best_oasis, naming cross); gms 2026-06-16 (hash 03f79e746643 already extracted) + 2026-10-03 (held as `gms_2026-10-02_..._week-40-chattogram`, issue_date 2026-10-02); clarksons S&P #139 (in `md/clarksons/`, not `md/hellenic/shipbuilding`); shipbuilding "missing dates" = the 374 breakwave PDFs already extracted in `md/breakwave/`.
- **CARRIED decision:** the best_oasis runner still globs only `pdfs/best_oasis/`. Either acquisition must place arrivals there, or widen `SOURCE_DIR` (caveat: shortest-stem choice can rename existing md). The 2 PDFs were left copied into `pdfs/best_oasis/` so re-runs are idempotent.

---

**THIS RUN (2026-10-06 18:2x, source-by-source, 30m job) - NOTHING TO EXTRACT (independently re-verified vs DISK); spent the run CONTENT-verifying the fresh W40 arrivals (100%) and FIXED 12 broken md `source_file` pointers (clarksons 11, carriers 1). Evidence docs/w40_fresh_arrival_and_sourcefile_verdict.md.**

Branch `auto/extract-fixes-2026-10-06-deepreview`, working tree CLEAN at run start (0 files). No extraction/ingest process of ours. Register gate GREEN: `verify_registers.py` = ALL CHECKS PASSED (disk 175 CSVs / **630,357** rows == JSON == MD; 0 mismatches).

- **Fresh arrivals (2026-10-04..06: advanced_shipping W40, affinity W40, agora W40, lion W40, clarksons 2-Oct, star_asia W40, banchero_costa W39) ALL already have md.** Nothing to extract.
- **CONTENT-verified them (no vision tool in cron - same-document PDF text-layer reconcile):** star_asia W40 418/418, advanced_shipping W40 385/385, affinity W40 72/72 = **100%**; lion 277/278, agora 183/184 (both single chart/contact-number tokens); banchero_costa W39 1,190/1,258 = 94.6% (known ciphered layer). advanced_shipping's first pass read 89% - ALL 44 misses were the float artifact (`3148.0` vs printed `3,148`), a metric artifact, not a defect.
- **FIXED (kind-2 exact-path field, repointed):** 11 clarksons md + 1 carriers md carried `source_file` that does not resolve (clarksons pointed at `02-hellenic/shipbuilding/pdfs/` while the PDF lives in `01-brokers/clarksons/2026/`; carriers W28 was a bare name where 135/137 use full paths). `run_clarksons.py` is already fixed (derives repo-relative path); the 11 were pre-fix artifacts. Re-verified clarksons **184/188 resolve, 0 stale**.
- **MEASURED, NOT fixed (user's call):** hellenic **448** md carry a BARE `source_file` by the athenian builder's convention (`run_athenian_demolition.py:366`); 427 basenames are AMBIGUOUS under corpus/ -> not safely machine-repointable; `validate_extracted_md_quality.py` only checks PRESENCE so they pass. Durable fix = builder writes repo-relative path + regenerate.
- **`_nan_` naming = NOT a gap.** 17 corpus PDFs carry a literal `nan` in the name (old downloader date-parse bug); the 5 `affinity_2026_nan_*` are BYTE-IDENTICAL (md5) to files already extracted under the good stem; ssy(8)/xclusiv(4) `_nan_` PDFs each have md. 4 orphan `clarksons_2026_nan_*.md` lack frontmatter - superseded dupes, left in place.
- **NEXT RUN:** nothing to EXTRACT. Open decision for the user: (a) hellenic bare-name convention (fix builder + regenerate); (b) inventory/DB rebuild. Watch the automation does not re-stale the register (`verify_registers.py` gate / `sync_extraction_register.py` fix).

---

**THIS RUN (2026-10-06 17:2x, source-by-source, 30m job) - NOTHING NEW TO EXTRACT (independently re-verified, not a re-statement). Working tree CLEAN (0 files); register gate GREEN; 4 Hermes/proxy python processes only, none ours extracting.**

- **Gate:** `python3 scripts/extract/verify_registers.py` = `ALL VERIFICATION CHECKS PASSED PERFECTLY` - disk 175 CSVs / **630,357** rows == JSON == MD, 0 mismatches, 0 control chars, 0 emoji.
- **xclusiv 271/271** (md == pdf, unchanged). No source has pdf >> md.
- **Fresh-arrival check:** the only 2 `corpus/01-brokers` PDFs newer than today (`banchero_costa_2026_W39_...` and `star_asia_2026_W40_...`) BOTH already have md + `.tables.json`. Content-level reconcile of the newest banchero doc against its own PDF text layer: **892/985 numbers present verbatim = 90.6%** (18 pages, 56,598 text chars) - consistent with banchero's known partially-ciphered layer; the misses are reformatted/comma variants, not missing tables.
- **Cosmetic staleness only:** `docs/EXTRACTION_REGISTER.md` prose doc-counts lag disk (Xclusiv "266" vs 271, Affinity "250" vs 249 md / 256 pdf, Fearnleys "261" vs 263 pdf). Numeric gate (CSV rows) passes; `sync_extraction_register.py` tracks rows, not doc counts, so hand-editing would fight the automation. Left alone.
- **NEXT RUN:** nothing to EXTRACT. Carried items are the user's: inventory/DB-rebuild decisions. Watch that the automation does not re-stale the register CSV counts (gate = verify_registers.py, fix = sync_extraction_register.py).

---
**THIS RUN (2026-10-06 16:5x, source-by-source, 30m job) - NOTHING TO EXTRACT (re-verified against DISK, not the prompt). The prompt's "IN PROGRESS: xclusiv" and its "next source" list are STALE - xclusiv is 271/271 and fearnleys/intermodal/affinity/banchero/agora/carriers/ism/lion are all built. Register gate GREEN. NEW measured finding: the md/pdf stem mismatches are DUPLICATE re-downloads whose content IS extracted under the canonical W-name - NOT gaps.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD 50ce4e62f, working tree CLEAN = 0 files). Live python = 4 Hermes gateway/proxy processes only - nothing of ours extracting. 54 ahead / 12 behind origin (unchanged).

**1. xclusiv COMPLETE at 271/271** (register prose still says 266; 5 docs arrived since). md 271 == pdf 271, ZERO unmatched both directions, 271 `.tables.json`, 0 files <2KB, 4,125,336 chars. Newest doc `xclusiv_2026_xclusiv-2026_09_28` reconciled against its own PDF TEXT LAYER (no vision tool in cron, so text-reconciliation substitute): NAME verbatim **20/20**, PRICE verbatim **19/20** - the single miss is `HIGH 13`, which the PDF literally prints for YC AEQUOR (the publisher's own range notation), so **20/20 faithful**. Series max issue_date **2026-09-28** (newest doc IS in the series layer). Do NOT reopen.

**2. REGISTER GATE GREEN.** `python3 scripts/extract/verify_registers.py` = `ALL VERIFICATION CHECKS PASSED PERFECTLY` - disk 175 CSVs / **630,357** rows == JSON == MD, 0 mismatches, 0 control chars / 0 emoji.

**3. NEW - "missing md" is a FILENAME artifact, not an extraction gap.** Enumerated stems for 12 sources: affinity 7, star_asia 1, banchero_costa 1 PDFs have no md AT THAT STEM. Every one is a SECOND, date-prefixed copy of a report ALREADY extracted under its canonical `..._W<n>_...` name:
  - `affinity_2026_Affinity-Tanker-Weekly-18.09.2026-HSN.pdf` -> md `affinity_19_09_2026_..._18_september_2026.md`; the 5 `affinity_2026_nan_*` copies -> md under the non-`nan` stem.
  - `star_asia_05_10_2026_..._week_40.pdf` -> md `star_asia_2026_W40_Market-Report-Week-40.md`.
  - `bancosta_30_09_2026_..._week_39.pdf` -> md `banchero_costa_2026_W39_...` (and the `bancosta_23_09_..._week_38.md` has no pdf because the W38 pdf carries the W-name).
  Content is held; no document is unextracted. This is the skill's "check the data isn't already held" rule catching a false alarm.

**4. Non-broker tiers present** (poten 2,174 md / 1,087 pdf; drewry 1,698/288; breakwave 7,008/304; hellenic 7,568/8,027; seabrokers 196/98; signal 892/10). PPA is a CSV tier BY DESIGN (`docs/PPA_ALREADY_EXTRACTED_FINDING.md`, family A+B built, family C per-vessel built), not an md dir - do not read `md=0` as a gap.

**5. Cosmetic staleness - NOT fixed (the automation owns the register).** `docs/EXTRACTION_REGISTER.md` prose doc-counts lag disk (Xclusiv "266" vs 271; affinity "250" vs 256). The numeric gate (row counts) passes; only the human-readable doc counts are behind, and `sync_extraction_register.py` tracks CSV rows, not doc counts, so hand-editing would fight the automation.

**NEXT RUN:** nothing to EXTRACT (independently confirmed). Watch that the automation does not re-stale the register CSV counts (`verify_registers.py` is the gate; `sync_extraction_register.py` is the fix). Carried items remain the user's: inventory/DB-rebuild decisions; the mapping-aware linked-asset fatal gate merge is now DONE on main.

---
**THIS RUN (2026-10-06 16:0x, source-by-source, 30m job) - Nothing to EXTRACT (re-verified); register gate GREEN on our branch; NEW: ORIGIN/MAIN's register is STALE (self-heals), and the linked-asset gate carried item is now RESOLVED on main.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD 602d082de, working tree CLEAN = 0 files at run start). Live python = 4 Hermes gateway/proxy processes only - nothing of ours extracting.

**1. Register gate GREEN locally.** `python3 scripts/extract/verify_registers.py` = `ALL VERIFICATION CHECKS PASSED PERFECTLY` - disk 175 CSVs / **630,357** logical rows == JSON == MD, 0 mismatches, 0 control chars/emoji.

**2. NEW + measured: origin/main's register is STALE and would FAIL the gate.** origin/main (`2c9d771c0`) `data/extracted/EXTRACTION_REGISTER.json` = total **630,317**, `hellenic_vv_sales_series.csv` = **2022**; but origin/main's OWN csv is 2063 lines = **2062 rows** (`git show origin/main:data/extracted/series/hellenic_vv_sales_series.csv | wc -l` = 2063). Cause = `9479ec9e4` rewrote the CSV but did not re-run the synchroniser - exactly the re-stale scenario the prior run flagged. It **SELF-HEALS**: every ingest workflow (report_ingest / broker_reports_weekly / fearnleys_weekly / poten_drewry_weekly / signal_reports_weekly / offshore_seabrokers_monthly) runs `python scripts/sync_extraction_register.py || true` and then `git add`s the register, so the next ingest run resyncs from the fixed CSV. Our branch already holds the exact fix (`602d082de`). Do NOT touch main.

**3. Carried item RESOLVED.** The mapping-aware linked-asset fatal gate is now ON origin/main (`5a0d0e63f`; block at lines 82/422 identical to ours; `git diff origin/main HEAD -- scripts/validate_knowledge.py` is EMPTY). Prior runs reported origin/main lacked it - no longer true.

**4. Ledger re-verified CLOSED on all 5 classes** (2026-09-28 `series_verification_ledger.md`): (a) star_asia_deals date columns now ISO - `arrival_date` 2704 ISO / 0 EU, `beaching_date` 1745 ISO / 0 EU; (b) ism agreement tail closed as **PUBLISHER-SIDE** (`docs/ism_residual_verdict.md`, 1,395/1,460 series re-derive exactly from the PDF's own vector drawings); (c) exact-duplicate rows down from ~270 across 10 files to **31 across 7 files** (0.005% of 630k): hellenic_vv_matrix 15, xclusiv_sales 5, gibson_tanker_spot 5, star_asia_deals 2, poten_top_charterers 2, carriers_sales 1, star_asia_ferrous_scrap 1 - the 15 hellenic_vv_matrix dups come from a LlamaParse-parsed MATRIX IMAGE (not text), unverifiable this session (no vision tool), left as documented residual, not fixed; (d) no fake `2026-00-00` dates remain.

**5. Nothing to EXTRACT.** Every `corpus/*` dir has an md tier (01-brokers 3,099 / 02-hellenic 8,027 / 03-breakwave 304 / 04-poten 1,087 / 05-seabrokers 98 / 06-drewry 288 / 07-signal 10 / 09-ppa 518; archive 724 = BACKFILL_ONLY >180d). Liveness on main: `gh run list` shows FFA Live Recorder + Fast GitHub Pages Deploy running.

**NEXT RUN:** unchanged - nothing to extract; watch that the automation does not re-stale the register (`verify_registers.py` is the gate; `sync_extraction_register.py` is the fix). Carried items are the user's (inventory/DB-rebuild; the gate merge is now DONE on main).

---

**THIS RUN (2026-10-06 15:5x, source-by-source, 30m job) - THE REGISTER GATE WAS RED IN HEAD; FIXED. Every other extraction item re-verified CLOSED.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD 41e877f6c). Nothing of ours was extracting; live python = Hermes gateway(s), proxy_gateway, code_review_graph - no extraction/ingest process. Working tree was CLEAN at run start (the prior run's best_oasis commit landed; `git status` = 0 files).

**1. Found a REAL open defect - `verify_registers.py` was RED, not green.** `scripts/extract/verify_registers.py` on HEAD: `Row mismatch in JSON for hellenic_vv_sales_series.csv: disk=2062 vs json=2022`. One file, everything else clean. **Root cause:** commit `9479ec9e4` (13:42, "skip already-extracted vessel valuations HTML after parsing internal issue_date") rewrote the CSV + its runner + `_run_state.json` but **never re-ran the register synchroniser**, so `EXTRACTION_REGISTER.{json,md}` kept the pre-commit count. Proven with git: at `9479ec9e4^` the CSV was 2023 lines = 2022 rows (JSON 2022, consistent); at `9479ec9e4` it is 2063 lines = **2062 rows** while the JSON stayed 2022.

**2. The +40 rows are legitimate recovered sales (checked, not assumed).** 0 exact duplicates; they land on **31 distinct issue_dates** (1-3 each), dominated by **MR2 tanker** sales (the row class the old HTML-skip was dropping). Spot-checked vs the publisher's own HTML: `corpus/02-hellenic/vessel_valuations/2026/2026-09-09_...september-8-2026.html` prints `... sold to Indonesian buyers for USD 27.2 mil, VV Value USD 27.92 mil. MR2 (...)` = exactly the recovered row `2026-09-08 | MR2 | Indonesian buyers | 27.2`.

**3. Fix = re-run the authoritative synchroniser.** `python3 scripts/sync_extraction_register.py` -> minimal 9-line diff: `hellenic_vv_sales_series.csv` 2022 -> **2062**, its `series_inventory` mirror, and the totals (`630,317 -> 630,357` stacked; `630,622 -> 630,662` extracted). After: `verify_registers.py` = **ALL VERIFICATION CHECKS PASSED (0 mismatches JSON, 0 MD)**. Evidence `docs/hellenic_vv_sales_register_sync_verdict.md`.

**4. bancosta "Target #1" (chart tables published as container indices) is CLOSED - re-measured, not reopened.** The residue verdicts still carry a "STILL OPEN" pointer; re-measured on the 243 canonical sidecars: `vhss_contex` **0/1,704** and `freightos_index` **0/1,759** rows have a `unit` cell that is neither a unit token nor a period label. Fixed earlier by `d96dd30bd` (bancosta branches 7/8). Pointer now stale; noted in the verdict doc.

**5. Nothing left to EXTRACT - re-enumerated.** All broker + non-broker sources have md tiers (note: `data/extracted/md/<source>/` is now YEAR-PARTITIONED per `f31f41701`, so a flat `ls md/<source>/*.md` returns 0 - count into the year subdirs). xclusiv state file absent because it is long done (266/266). No ledger defect open.

**NEXT RUN:** nothing to extract. (a) Watch that the automation does not re-stale the register (if it rewrites a series CSV it must re-run `scripts/sync_extraction_register.py`; `verify_registers.py` is the gate). (b) Carried items remain the user's: merge the mapping-aware linked-asset fatal gate branch; inventory/DB-rebuild decisions. (c) If the automation rewrites best_oasis md or the regenerated register, `git status` will show it - re-verify before assuming change.

---

**THIS RUN (2026-10-06 14:3x, source-by-source, 30m job) - THE LAST OPEN DATA-QUALITY GAP IS CLOSED: the parallel automation's verified best_oasis md restoration is now COMMITTED (150 files, 86d8eb584).**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD was 8b9c0fcb2, 49 ahead / 12 behind origin). Nothing of ours was extracting; live python = Hermes gateway x2, proxy_gateway (litellm), code_review_graph - no extraction/ingest process. Working tree at run start held exactly ONE change: the 150 best_oasis md (automation-owned, written 13:42, never committed).

**1. Decision + action.** HEAD's best_oasis tier is DEFECTIVE: its ingest commit `b0fa2b3be` created the canonical md with EMPTY indicative-price tables - 134/150 files have no price row in HEAD. The automation rewrote them in the working tree (150/150 now carry price rows) but stalled with them uncommitted (files mtime 13:42; no automation commit touched best_oasis - `9479ec9e4` touched vessel_valuations only). Prior run's fallback ("if the automation stalls, the md fix is verified-correct and safe to commit") applies, so I landed it as commit `86d8eb584` (attributed to the automation; my commit only stages it).

**2. Independent re-verification THIS run (not a re-statement of the prior run).** Script `scratch/best_oasis_recheck/verify.py`: 1,821 `$`-values across the 150 md, **1,793 present verbatim in each file's own source-PDF text layer = 98.46%** (digits-only canonical match). HEAD-vs-worktree table census: HEAD **134 without / 16 with** a price row; worktree **150 with / 0 without**.
Residual 28 misses, all characterised, none fabrications:
  - **24 in `2022-12-28`** - that PDF's text layer is **EMPTY (0 chars, every page an image)** -> unverifiable, NOT wrong.
  - **2 in `2025-11-22`** - partial text layer (4,148 chars for 4 pages).
  - **2 genuine roundings**: `$654` vs printed **653.50** (HARMONY, 2022-03-05) and `$334` (SHENG TAI, 2025-03-29). The extractor rounds x.50 to integer; value is derived from the page, not invented.

**3. PLACEMENT verified, not just presence (new this run).** Reconstructed the page geometry on `2022-03-12` from positioned text (`page.get_text("words")`): India bar values group by x as {670@99, 680@161}=Container, {650@260, 660@321}=Tanker, {635@420, 645@482}=Bulker under the legend at x=119/285/446; HMS {550@124, 590@216} and Shredded {595@365, 630@457} under the second chart's legend. The new table's row `India | 680 | 660 | 645 | 590 | 630` matches exactly. So the automation's rewrite is correct in column assignment, not merely present.

**4. GOTCHA worth recording (cost ~10 calls):** `git add` and `git commit -- <path>` SILENTLY refused to stage the 150 modified best_oasis md (exit 0, `git diff --cached` empty) even though `git hash-object --path` differed from the index blob and `git diff` showed a real 16k-line diff. New files stage fine. The working fix: `git diff --name-only -z -- <dir> | xargs -0 git update-index --add --`. Use `git update-index --add` when `git add` no-ops on an already-tracked modified file in this repo.

**5. Coverage re-enumerated (unchanged).** Every `corpus/*` folder has an md tier; nothing to EXTRACT. No ledger defect open (4.1/4.2/4.3/4.4 all closed). Cadence/register: the working-tree regen (630k/175 CSVs) is still uncommitted and correct-but-not-mine.

**NEXT RUN:** nothing to extract, no open ledger defect, working tree clean after this commit. Carried items remain the user's: (a) merge the mapping-aware linked-asset fatal gate branch (feature-branch-only); (b) the inventory/DB-rebuild decisions; (c) the stale committed register vs disk (regenerated version verified correct). If the automation re-writes best_oasis md, `git status` will show it - re-verify before assuming change.

---

**THIS RUN (2026-10-06 13:3x, source-by-source, 30m job) - FOUND + independently verified the PARALLEL AUTOMATION's best_oasis md restoration (134 empty-table md -> data). Evidence docs/best_oasis_md_stub_verdict.md. Nothing of ours was extracting; the best_oasis md files are the automation's LIVE WIP (mtimes advanced 13:27 -> 13:42 during this session, with the register and cadence docs at 13:42) - I did NOT commit them.**

**1. Headline (measured).** The automation's ingest commit `b0fa2b3be` (13:21) CREATED the canonical best_oasis md tier with EMPTY indicative-price tables. Over the 150 best_oasis md the working tree rewrites: HEAD has no price data row in **134/150**; the working tree has it in **150/150**. Same class committed-fixed for GMS/Alibra in `1eb52d5c3` (13:32); best_oasis is the uncommitted analogue.

**2. Verified the restoration against the source PDFs (not file counts).** 1,509 `$`-values across the 150 rewritten md checked against each file's own `source_file` PDF text: **1,481 = 98.1% present verbatim**. The 28 misses: 24 in `2022-12-28` whose PDF TEXT LAYER IS EMPTY (cached parse - unverifiable, not wrong), 3 in `2025-11-22` (partial text layer), leaving **2 genuine single-value candidates ($654 HARMONY 2022-03-05, $334 SHENG TAI 2025-03-29) = 0.13%**. (`$1275` BOW FLOWER is CORRECT - the page prints `1,275`; my first checker missed the comma form.) All **269** worktree md have a `source_file` that resolves to an existing PDF (0 stale; the earlier spurious `/2022/` segment was corrected at 13:42).

**3. Series layer unchanged** (mtime 12:55): deals 892, demolition 867, exchange_rates 167 - matching the register. The DATA was never lost at the series layer; only the .md tier was stubbed.

**4. Action taken:** wrote docs/best_oasis_md_stub_verdict.md + this entry; committed ONLY these docs, NOT the 150 automation-owned md. The md fix is correct and commit-worthy but belongs to the live WIP.

**NEXT RUN:** the automation owns best_oasis; re-check it is committed. Otherwise unchanged: (a) nothing to EXTRACT, no ledger defect open; (b) carried items are the user's (linked-asset gate merge, inventory/DB decisions); (c) if the automation stalls, the working-tree md fix is verified-correct and safe to commit (134 empty-table files, 98.1% text-verified).

---
**THIS RUN (2026-10-06 12:1x-12:3x, source-by-source, 30m job) - LEDGER 4.3 RE-KEY INDEPENDENTLY RE-VERIFIED WITH MY OWN CONTROL and the register pickup CONFIRMED; nothing left to extract (re-enumerated). No extraction job of ours was running.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD 71647b8e6 == upstream, pushed). Live python = Hermes gateway + code_review_graph, none of ours.

**1. Ledger 4.3 (intermodal macro daily re-key) re-verified by MY OWN control, not the prior run's.** `data/extracted/series/intermodal_macro_daily_series.csv` = **22,760 rows** vs the wide 4,818 (scratch/verify_daily_macro*.py). `day_offset == 0` value == wide `latest_value` on **4,552/4,552, 0 None, 0 mismatch**. Within every (indicator x issue_date) group (**4,552 groups / 253 issues**) day_offset is contiguous 0..n-1 (**0 violations**) and consecutive print_date steps are **exactly 1 day (0 violations)**. Wide file md5 `cceecc8098203c6c7b4cd1c7b7100271` unchanged (control). Ledger 4.3 CLOSED on evidence this run produced.

**2. Register pickup CONFIRMED.** `docs/EXTRACTION_REGISTER.md` section 2 lists `intermodal_macro_daily_series.csv | 22,760 | Verified`. `python3 scripts/extract/verify_registers.py` = **ALL VERIFICATION CHECKS PASSED** (disk 175 CSVs / 630,310 logical rows == JSON == MD; 0 mismatches; 0 control chars/emoji).

**3. NOTE (not ours, do not commit blindly).** The COMMITTED register is STALE (273,254 rows / 98 CSVs) vs the working-tree regenerated one (630,615 / 175 CSVs). The regen is CORRECT (disk == register), but it is an UNCOMMITTED working-tree change from the parallel automation - I did not commit it.

**4. Gate branch vs origin/main RE-VERIFIED.** `EXTERNAL_UNAVAILABLE_LINKED_PREFIXES` exists in our HEAD (`scripts/validate_knowledge.py:82,422`) and is **ABSENT from origin/main (a6df3c82e)**. So the restored mapping-aware fatal gate is still FEATURE-BRANCH-ONLY; origin/main's fatal accounting stays dead. Merge remains the user's call.

**5. Nothing to extract - re-enumerated.** Every `corpus/*` folder has an md tier (24 md dirs). 01-brokers 3,099 pdf, 02-hellenic 8,027, 04-poten 1,087, 06-drewry 288, 09-ppa 518, archive 724 (all >180d, BACKFILL_ONLY). No unbuilt source.

**6. Cadence audit did NOT complete.** `scripts/audit/generate_cadence_audit.py` ran >420 s with a 0-byte log (its REGISTRY_DATA is hardcoded, not glob-derived; it hung before emitting). Not our critical path (verify_registers is the register gate and passes). Flagged, not chased - do not re-run blind.

**NEXT RUN:** (a) nothing to EXTRACT, no ledger defect open. (b) carried items are the user's: merge the linked-asset gate branch (item 4) and the inventory/DB-rebuild decisions. (c) the committed register is stale vs disk - a human/automation should commit the regenerated 630k/175 version (verified correct, but not this job's diff).

---
**THIS RUN (2026-10-06 11:0x-11:4x, source-by-source, 30m job) - THE LAST CARRIED LEDGER ITEM IS CLOSED: intermodal macro (ledger 4.3) RE-KEYED to its date columns, 22,760 daily rows, control 4,552/4,552 vs the wide file, 0 mismatch. Evidence docs/intermodal_macro_423_verdict.md.**

Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD d13f51249, pushed). Working tree had 15 modified files, only 3 of ours (the rest pre-existing, not touched). No extraction job of ours was running (live python = 2x Hermes gateway, proxy_gateway, code_review_graph serve).

**1. Ledger 4.3 FIXED (the item the prior run left).** Implemented in the source's OWN runner `scripts/extract/publishers/run_intermodal_finance.py` (NOT run_intermodal_full.py - it does not write this series). New file `data/extracted/series/intermodal_macro_daily_series.csv`: one row per **indicator x printed day** (series key = row label + column header=DATE, per the skill). **22,760 rows**; the wide `intermodal_macro_series.csv` left **byte-identical** (control md5 cceecc80..., 4,818 rows) so nothing downstream breaks. Control: `day_offset 0` value == wide `latest_value` on **4,552/4,552, 0 mismatch**; print_date strictly decreasing 0/4,552 violations; coverage of the 18 five-column indicators **4,552/4,568 = 99.65%**. `wow_change_pct` carried verbatim (baseline is an unprinted week-ago value - never recomputed).

**2. THREE real defects the trial+verification found (each silently lost WHOLE documents; all fixed).** (a) **Kerned month** - the text layer prints `2-J un-23` on 25 docs from 2023 W22 on (month not stable). (b) **Header fused onto the last date** - `20-May-24 W-O-W Change %` on one line from 2024 W20 on. (c) **Two dates fused onto one line** - `29-May-24 28-May-24` on 7 docs (2024 W21/W47, 2025 W12/W46/W47/W48 + a `_compressed` copy); fixed with findall + PREPEND (a final `reverse()` swapped the 28th/29th - measured). Trial matched the RENDERED page text exactly on 7 docs across 2021-2026 (values in the verdict doc). Also fixed a latent `import sys` missing in the runner's dedup fallback.

**3. Residual, documented not guessed.** 16 rows / 1 doc (`intermodal_2025_W07`) print a stray W-O-W-baseline date (`7-Feb-25`) after the header -> 6 date tokens vs 5 value columns; left UNKEYED (trimming to "newest N" would mis-key the separate 2-col Brent/WTI table). 250 rows (Brent/WTI) are from the separate **Basic Commodities Weekly Summary** 2-col table, not the 5-col macro table -> not keyed, still in the wide file.

**4. Knowledge/CI tier (prior run's item (a)) MEASURED.** `Process Knowledge Base 37397137261` (2026-10-06T01:02Z, main SHA 71463da1c) = **success**; `knowledge/chunks/index.json` `generated_at` ADVANCED to **2026-10-06T01:11:57Z**. NOTE the restored linked-asset fatal gate (d13f51249) is on the FEATURE branch, NOT main, and there are **no open PRs** - so that green run did NOT exercise our gate. It stays green-on-today's-manifest by construction (0), and merging it is the user's call (never touch main ourselves).

**NEXT RUN:** (a) nothing left to EXTRACT and no ledger defect open (4.3 now closed; the earlier 4.1/4.2/4.4/item-list all closed). (b) the only carried items are non-extraction "inherited human decisions" (inventory drift, DB/series rebuild) plus the gate merge awaiting the user. (c) if acting, verify the NEW daily file is picked up by the register/audit (`scripts/sync_extraction_register.py`, `scripts/audit/generate_cadence_audit.py`) or re-verify the gate branch vs origin/main.

---
**THIS RUN (2026-10-06 09:3x, source-by-source, 30m job) - THE DEAD LINKED-ASSET FATAL GATE IS RESTORED, MAPPING-AWARE AND VERIFIED (0 on today's manifest, 1 on a control). Evidence `docs/linked_asset_fatal_gate_verdict.md`.**

**0. Extraction programme re-verified CLOSED by independent enumeration (not by trusting the state).** Branch `auto/extract-fixes-2026-10-06-deepreview` (HEAD == 89ca233ab, the 05:16 deep review = HEALTHY). Every `corpus/*` folder has an md tier. The `corpus/archive/` STOPPED publishers (allied 203, golden_destiny 252, anchor 30, gibson 109, other 130) are all **>180d dead** (newest: allied 2024 W07, golden_destiny 2024 W48, anchor 2022 W52, other 2023) -> BACKFILL_ONLY per MASTER line 246, correctly not extracted.

**1. Hellenic - the biggest source - re-measured by DISTINCT CONTENT this run (md5 census, whole folder, 8,028 PDFs / was 3,969 on 2026-09-28).** `iron_ore 4524 files / 1181 distinct` (md 1193, covered); `demolition 2141 / 726` (md 1638, covered); `shipbuilding 1362 / 357` (md 165 - but all 357 are covered: **186 breakwave** by `md/breakwave/`, **170 clarksons** by `md/clarksons/`+`md/hellenic/shipbuilding/clarksons`, **0** distinct clarksons stems lack an md, control-checked). So the file-count gap is pure duplication; **hellenic distinct-content coverage is complete.** The 2026-09-28 coverage verdict (2,236 distinct) still holds.

**2. THE FIX.** `8de08da48` had removed the `unresolved_required_local.add(...)` branch (variable returned+summed line ~1173 but never populated; line 1114 printed 0 unconditionally) -> the fatal gate was dead. Replayed the removed branch read-only on the committed manifest (11,329 rows): **59 would-be-fatal, 59/59 `breakwave_insights`**, all `reports/breakwave/<year>/*.html -> ../pdfs/<name>.pdf` -> `reports/breakwave/pdfs/` = publisher ANZ-Portal login-wall PDFs (5,174-byte HTML under a `.pdf` name; `docs/breakwave_pdf_mirror_verdict.md`). Restored the branch with `EXTERNAL_UNAVAILABLE_LINKED_PREFIXES = ("reports/breakwave/pdfs/",)`: required-local refs resolving outside those prefixes stay **fatal**. `external_non_mirrored` unchanged.

**3. Verified with controls (the validator's OWN function, `scratch/verify_linked_gate.py`).** REAL manifest -> `unresolved_required_local 0` (CI cannot regress today), `external_non_mirrored 11,527`. CONTROL genuine missing hellenic `/assets/` -> **1 (caught)**. CONTROL breakwave `/pdfs/` auth-wall -> **0 (exempt)**. `py_compile` OK. Change is on the feature branch, NOT main.

**NEXT RUN:** (a) confirm the next `Process Knowledge Base` / `Daily Knowledge Update` `Validate knowledge artifacts` step stays green with the restored gate (expect 0, since today's manifest yields 0); if it reds, the diff is the 59 already characterised. (b) The only remaining carried ledger item is the intermodal date re-key (`docs/intermodal_macro_423_verdict.md` - numbers faithful, only the series key differs), and the 3 "inherited human decisions" in `docs/EXTRACTION_OVERNIGHT_LOG.md` (inventory drift, DB/series rebuild, both non-extraction). Nothing left to EXTRACT.

---

**THIS RUN (2026-10-06 05:0x, source-by-source, 30m job) - THE KNOWLEDGE/QA CI BLOCKER IS CLOSED: P-KB run 37375284821 step 11 `Validate knowledge artifacts` = SUCCESS (first time), the daily knowledge commit LANDED, and `knowledge/chunks/index.json` `generated_at` ADVANCED 2026-09-29T17:23:36Z -> 2026-10-05T23:11:23Z. The app-visible QA tier is UNFROZEN after 7 days.**

**1. Headline (measured).** This answers the prior run's explicit "NEXT RUN: read 37375284821's step-11 result". `gh api .../jobs/111982292932`: step 9 `Run processor` success, step 10 `Guardrail - verify Breakwave signals freshness` success, **step 11 `Validate knowledge artifacts` = success**, step 14 `Commit knowledge artifacts` = success -> commit `dc76c6906` "knowledge: update 2026-10-05". The step-11 blocker carried for 3 runs (dup doc ids 1290 / invalid section refs 28731 / dup tree nodes 3337 / unresolved required local assets 1393) is now GREEN on `main`.

**2. The daily schedule is healthy again.** `Daily Knowledge Update` run **37380480306** (22:08Z, schedule) = **success** (3m34s) - first green daily since 2026-09-28 (7 prior consecutive failures 09-29..10-05). NOTE it exercised only steps 1-8: step 8 `Check for new reports` found nothing new, so steps 9-14 `SKIPPED`. The actual knowledge update that unfroze the tier came from the hand-dispatched **P-KB 37375284821** (1h52m), not the daily.

**3. Tier freshness verified on origin/main directly** (not the stale local copy): `git show origin/main:knowledge/chunks/index.json` -> `generated_at 2026-10-05T23:11:23Z`. `dc76c6906` rewrote 20+ chunk shards (baltic_*, hellenic_iron_ore_2026 9,510 lines, hellenic_demolition_2026 1,766, broker_reports_broker_report_2026 1,966) - the compact-in-place shards the 10-05 recovery restored now in a committed, validator-passing state.

**4. Nothing left to extract - 5th measurement (md counts per source, all built):** advanced_shipping 255, affinity 249, agora 219, banchero_costa 249, carriers 137, clarksons 188, fearnleys 12000 (record-only), gibson 264, intermodal 257, ism 115, lion 48, ssy 530, star_asia 200, xclusiv 271, poten 1087, drewry 849, seabrokers 98, signal 446, hellenic 3781, breakwave 3504, companies 1310, baltic 2228, books 12. Every corpus folder has an md output. `xclusiv 271/271` (confirms the 30m prompt is stale).

**5. Local tree:** only `logs/fleet_sync.log` modified (automation-owned, not ours). Local `auto/extract-fixes-2026-10-06-linkedasset-verify` f6a56cb79 is 5 behind origin/main 0e65f3a61 (all automation pushes: knowledge update, broker-voice sync, daily brief).

**STILL OPEN (not this run):** the linked-asset fatal gate remains DEAD in HEAD (`unresolved_required_local` never populated; line 1114 prints 0 unconditionally) - restoring it must be mapping-aware to spare the 59 permanently-unfetchable breakwave assets (`docs/breakwave_pdf_mirror_verdict.md`). Residual ledger defects: the residual ism agreement tail (1,178 rows). **Ledger 4.3 (`intermodal_macro_series.csv`) is now VERIFIED, not fixed** - re-measured 4,418/4,818 = 91.7% non-reproducible, 0 blank; the page truth (`docs/intermodal_macro_423_verdict.md`) shows the table is 5 DAILY columns + a W-O-W %, so `prior_value`=prior DAY and `wow_change_pct`=week-over-week vs an UNPRINTED week-ago baseline: all three fields faithful, the pairing is what differs. Fix = re-key to the date columns in `run_intermodal_full.py`, NOT recompute the change.

---
**THIS RUN (2026-10-06 04:0x, source-by-source, 30m job) - THE 59 BREAKWAVE "UNRESOLVED LINKED ASSETS" ARE BOT-WALL JUNK, NOT A MIRRORING GAP (measured; a copy "fix" was TRIED and REVERTED). Evidence `docs/breakwave_pdf_mirror_verdict.md`.**

Nothing of ours extracting (programme re-verified closed). Branch `auto/extract-fixes-2026-10-06-linkedasset-verify`.

**1. Inventoried the 59 residual (last run's recommendation), and the recommendation was WRONG.** `8de08da48` maps `reports/breakwave/ -> corpus/03-breakwave/insights/`; the mirror `corpus/03-breakwave/insights/pdfs/` held only **13** genuine PDFs, so 59 refs (`../pdfs/<name>.pdf`) were unresolved. Those 59 files DO exist in the gitignored `reports/breakwave/pdfs/` of both worktrees (81 each) - **but they are 5,174-byte `Login Page` bot-walls** (ANZ Portal login), HTML saved under a `.pdf` name. Byte-check: of 81, **13 real PDFs (245 KB-7.9 MB), 67 login pages (exactly 5,174 B), 1 Baker-Institute search page**. All 59 referenced assets were never fetched - the fetch hit an auth wall.

**2. Tried the mirror, measured 59->0, then REVERTED it.** Copying all 81 in made `resolve_local_asset_reference` return True for 59/59 and the fatal accounting go 59->0 - but it is COSMETIC and HARMFUL: it makes the corpus assert an asset exists when the file is a login page. A wrong/misleading file is worse than a missing one. Deleted the 68 non-`%PDF-` files; mirror back to **13 genuine PDFs, 0 junk**; residual re-measured = **59 / 59**, the honest state.

**3. Correct classification of the 59 = EXTERNAL_UNAVAILABLE** (publisher login wall), not a path bug and not fixable by copying. The right treatment is what HEAD's non-fatal path already does: `external_non_mirrored`, no CI failure, no corpus pollution. Genuine content would need a re-fetch with credentials/a public mirror.

**4. CAVEAT carried:** the fatal gate is still DEAD in HEAD - `unresolved_required_local` in `scripts/validate_knowledge.py` is init (331)/returned (407)/summed (1173) but **never populated**; line 1114 prints 0 unconditionally. NOTE the new fact: 59 of the 1,393 are permanently unfetchable, so a naive fatal-branch restore would re-break CI on exactly them.

**5. CI still unresolved at run time.** `Process Knowledge Base` **37375284821** (21:20Z, `8de08da48`) still `in_progress`, stuck in step 9 `Run processor` since 21:28Z (>70 min vs ~3 min on the 09-28 success) - hung or heavy, unjudgeable without its log. `Daily Knowledge Update` **37380480306** (22:08Z) pending; daily workflow failed 7 straight (09-29..10-05), last green 09-28. Not re-dispatched (avoid double paid CI).

**6. Nothing to extract - 4th measurement, md5-verified.** affinity 256 pdf/249 md -> 7 "missing" are all md5 twins; star_asia 201/200 -> the 1 (`W40`) is an md5 twin. All other brokers 1:1.

**7. Ledger residual (quick scan).** exact-dup rows across all `*_series.csv`: **28 total** in 7 files (hellenic_vv_matrix 15/12,350 worst); bancosta 106-row case gone. Small; not chased (unverified vs source).

---

---
**THIS RUN (2026-10-06 02:3x-03:0x, source-by-source, 30m job) - THE 1393 LINKED-ASSET BLOCKER IS FIXED ON MAIN BY THE PARALLEL AUTOMATION (`8de08da48`); VERIFIED it resolves 1,334/1,393 = 95.7% - but the SAME commit SILENCES the check. Evidence `docs/linked_asset_fix_verification.md`.**

Nothing of ours extracting (programme re-verified closed). Branch `main`, HEAD == origin/main == **`8de08da48`** (committed 02:33:49 IST by the parallel automation / Prateek).

**1. The situation moved under this run.** `8de08da48` "fix(pipeline): resolve knowledge validator asset links, book section counts, ..." targets **exactly the two remaining CI step-11 blockers** my prior runs characterised: the 1,393 unresolved required local linked assets and the 7 book section-count mismatches. The automation then hand-dispatched `Process Knowledge Base` run **37373648497** (21:04Z) - the first run to exercise it. My job became: verify the fix, not trust a green CI.

**2. Verified with the validator's OWN function** (`validate_knowledge.validate_linked_asset_coverage`) on the 10,202-row manifest: `unresolved_required_local = 0`; `external_non_mirrored = 11,508`; schema/consistency = 0. The new `resolve_local_asset_reference` mapping (`reports/hellenic|baltic|breakwave -> corpus/02-hellenic|08-baltic|03-breakwave/insights`) was spot-checked LIVE on 3 hellenic demolition refs - all resolve to an existing corpus PDF (isfile True).

**3. TRUE residual = 59, all breakwave** (replicating the removed fatal accounting on the same manifest with the mapping in place): would-be-fatal 1393 -> **59**. So the mapping genuinely fixes **1,334/1,393 = 95.7%**. The 59 are `reports/breakwave/<year>/*.html -> ../pdfs/<name>.pdf` commodity-call PDFs never mirrored into `corpus/03-breakwave/insights/pdfs/` (main tree lacks them; they live only in `.claude`/`.kilo` worktrees). Named list `scratch/linked_asset_recheck/would_be_fatal.json`.

**4. CAVEAT (honest):** the same commit deleted the `unresolved_required_local.add(...)` branch, so that variable is now **dead** (init line 331, returned 407, summed into the exit code 1173, never populated). CI's "Unresolved required local linked assets" now prints **0 unconditionally**; the 59 (and any future missing required asset) become non-fatal `external_non_mirrored` warnings. So the gate is cleared by fixing the root cause AND by disabling the check. Recommend: inventory the 59 and/or restore a mapping-aware fatal branch.

**5. Books class:** all **12** `knowledge/docs/books/*.md` now carry `section_count:` -> that class should be 0 (cannot regress extraction). `knowledge/chunks/index.json` `generated_at` still 2026-09-29T17:23:36Z (frozen) until a green pipeline run.

**6. Nothing to extract (re-measured):** every `corpus/*` folder has an md output (23 md dirs incl. baltic, companies, gibson, clarksons); xclusiv 271 md + 271 tables.json year-sharded 2021-2026; `corpus/10-companies` (26 dirs) and `corpus/08-baltic` (5,276 files) extracted. No unbuilt corpus folder found.

**NEXT RUN:** read run **37375284821**'s step-11 result (I re-dispatched P-KB by hand because the automation's own dispatch 37373648497 was LOST to a GitHub-hosted runner-acquisition failure at 21:04Z - it never executed a step; the Weekly Broker Reports Ingest dispatch failed the same way). 37375284821 acquired a runner and was still in step 9 'Run processor' after ~38 min at 22:00Z. If green, the daily knowledge commit lands and `index.json` advances (the one remaining app-visible item) - then decide whether to restore the linked-asset fatal branch (item 4). If it still fails, diff its own diagnostic artefact against the classes above.

---
**THIS RUN (2026-10-05 23:3x, source-by-source, 30m job) - EXTRACTION PROGRAMME RE-VERIFIED: NOTHING LEFT TO EXTRACT; the last two CI blockers are now COMMITTED in HEAD (will be exercised by tonight's scheduled run). Evidence appended to `docs/xclusiv_verdict.md`.**

No extraction job of ours running (live python.exe = Hermes gateway + litellm + code_review_graph). Branch **`main`**, local HEAD == origin/main == **636eca503** ("fix(pipeline): year-segregate Signal Ocean MDs ... ingest 2026-10-05 reports", 17:34 UTC) - the parallel automation advanced main during the last run. Tree clean except 2 files it touched (`clean_all_brokers_formatting.py`, `run_smm_iron_ore_daily.py`) - NOT ours.

**1. xclusiv VERIFIED (the 30m prompt's item, and it WAS stale).** Now **271/271** (grew from 266; 2026: 45). **1:1 per year, zero gaps**: 2021:23 / 2022:51 / 2023:50 / 2024:51 / 2025:51 / 2026:45 against 271 PDFs; 271 `.tables.json`. This session has **NO vision tool**, so verification used the **PDF text layer** (pymupdf), not eyes (PNGs rendered anyway for a human: `scratch/xclusiv_verify/xclusiv_w39_p1..p3.png` dpi=115). W39 doc: **15/15 values verbatim in the PDF text, each once** (BDI 3,426 / BCI 5,784 / BPI 2,407 / BSI 1,786 / BHSI 1,011 / BDTI 5,366 / BCTI 2,160; Capesize 48,954 / Kamsarmax 21,662 / Ultramax 22,579 / Supramax 20,545 / Handysize 18,190; VLCC 714,143 / Suezmax 299,424 / Aframax 234,370). Typed layer reconciles: `GCL HAZIRA | Kamsarmax | 81,986 | 2021 | NACKS | GERMANS | 39 | SURVEYS PASSED` all 5 tokens on the page; baltic typed == md == PDF. xclusiv remains KB-only (**0 xclusiv refs in index.html**).

**2. NOTHING TO EXTRACT - re-measured this run.** All broker sources still closed. `affinity` shows 256 PDFs vs 249 md, but all **7 "orphans" are BYTE-IDENTICAL duplicates** of already-extracted PDFs (md5 twins, e.g. `..._nan_...04.09.2026` == the HSN-named file that has md; 18.09 twin = `affinity_19_09_2026_...` which has md). No genuine gap.

**3. THE TWO CARRIED CI FIXES ARE NOW IN HEAD (resolves the prior "STILL OPEN").** `git log -S` confirms **636eca503** landed BOTH `compact_chunk_file` crash-safety (`*.compact.tmp` + `os.replace`, line 1175/1181) AND `prune_superseded_mirror_rows`/`dedupe_manifest_rows_by_doc_id` (line 1250/1275/4530/4656) AND the shape-gated `parse_number` (`re.fullmatch(r"-?\d+\.\d{3}")`, line 332). The last CI failure (run 37329812815, 15:04 UTC) PREDATES this commit. **The nightly schedule (~18:44 UTC) will be the first run to exercise them** - not re-dispatched by hand, to avoid doubling paid CI spend. `knowledge/chunks/index.json` `generated_at` is STILL `2026-09-29` (freeze persists until that run commits) - expected.

**4. Chunk-tier durability re-checked.** Manifest `bytes` for the 6 bare parent shards is **0 by declaration** and index.html references only the YEAR-SHARDED names (all non-zero) - so those 6 zero-byte files are intentional placeholders, NOT a gap. `tests/test_hellenic_extraction.py` = **12 passed**.

**NEXT RUN:** read the nightly `Daily Knowledge Update` result (was it green?). If step 11 `Validate updated knowledge` now passes and the commit lands, the QA tier unfreezes (index.json generated_at advances) - that is the one remaining open, app-visible item. If it still fails, take the run's own diagnostic artefact and diff the failure composition against the 1290-dup baseline.

---

**THIS RUN (2026-10-05 22:4x-23:0x, source-by-source, 30m job) - 17 HELLENIC KNOWLEDGE CHUNK SHARDS FOUND ZEROED ON DISK, RECOVERED (98 MB / 35,110 rows), AND THE TRUNCATE-FIRST WRITER ROOT-CAUSED + FIXED. Evidence `docs/hellenic_chunk_shard_recovery_verdict.md`.**

No extraction job is ours (live python.exe = Hermes gateway x2 + litellm x2 + code_review_graph serve). The 30m prompt is STALE again - xclusiv 266/266 (now year-sharded under `data/extracted/md/xclusiv/<YYYY>/`, 271 md), every broker source CLOSED. Branch `main`, HEAD advanced by the parallel automation (ab308b1c9) while this run worked.

**1. THE FINDING.** 17 hellenic chunk shards (`knowledge/chunks/hellenic_{iron_ore,shipbuilding,vessel_valuations}_*.jsonl`) were **0 bytes on disk**, all mtime `2026-10-05 22:06`; `git diff --numstat` = `0 added, N removed` on every one (pure truncation). HEAD + `knowledge/chunks/index.json` both declared the content (iron_ore_2021 = 26,536,423 bytes / 9,540 rows). Total loss: **97,950,982 bytes (98.0 MB), 35,110 rows**.

**2. RECOVERY.** Targeted `git checkout HEAD -- <17 paths>` (NOT a broad checkout). Re-verified: every byte size and row count matches the removed counts exactly; `git status knowledge/chunks/` clean (0 modified). Byte-identical to HEAD, so independent of any commit.

**3. ROOT CAUSE (proven mechanism).** `scripts/process_knowledge.py::compact_chunk_file()` truncated the live shard IN PLACE (`path.write_text("")`) then re-appended rows one at a time - any interruption after the truncation loses the WHOLE shard. Both `process_knowledge.py` and `scripts/repair_hellenic_shards.py` call it. The 6 bare parent shards (mtime 2026-06-22) are a separate, intentional older state - untouched.

**4. FIX (applied, uncommitted).** `compact_chunk_file()` now writes to `*.compact.tmp` and `os.replace()`s it onto the target (crash-safe; the skill's "persist partial output / never truncate in place"). Unit-tested: dedup keeps the last chunk_id, no tmp left behind, and a **simulated mid-write crash preserves the original 78-byte file** (before: 0). `py_compile` OK.

**5. HONEST LIMITS.** Which process zeroed them is INFERRED (no python alive at 22:47; the 22:06 writer had exited) - the mechanism is proven, the trigger is the only consistent explanation. The served QA tier is unaffected: `knowledge/chunks/index.json` `generated_at` is STILL `2026-09-29T17:23:36Z` (the daily commit stays frozen by the CI `Validate knowledge artifacts` failure, latest run 37343590808 16:48Z).

**6. STILL OPEN.** The prior run's mirror-dedupe fix and this durability fix are both staged/uncommitted on `main`; **HEAD carries neither**, so CI step `Validate knowledge artifacts` will keep failing until one lands on `main`. Do NOT re-run `repair_hellenic_shards.py` until then (it inherits the truncate-first path - now the safe one).

---

**THIS RUN (2026-10-05 21:3x, source-by-source, 30m job) - THE CI VALIDATE BLOCKER ROOT-CAUSED TO MIRROR-PATH DUPLICATE doc_ids AND FIXED IN process_knowledge.py (verified 1290 -> 0 on the real CI manifest). Evidence `docs/knowledge_validate_fix_verdict.md`.**

No extraction job live (branch `main`; parallel automation pushing ffa-live ticks; local is 6 behind origin, all ffa-live). The 30m prompt is STALE (xclusiv 266/266, all brokers CLOSED, non-broker corpora extracted). This run advanced the carried top item: CI step 11 `Validate updated knowledge` (run 37329812815, still exit 1) which keeps the daily knowledge commit SKIPPED -> the QA tier the app serves is still frozen at 2026-09-29.

**1. EXACT failure composition (measured from the run's diagnostics artifact).** `Duplicate doc ids 1290` = **1185 hellenic + 105 broker**, exactly. CI coverage gaps are hellenic only: iron_ore 1203->1736, shipbuilding 379->758, vessel_valuations 274->547 = +1185. Duplicate tree node ids 3337 / invalid section refs 28731 / duplicate section-index node ids 2047 are all downstream of the same duplicate rows.

**2. ROOT CAUSE (proven from the CI's own documents.jsonl, 12606 rows).** `make_archive_doc_id()` ignores the directory, so two source paths slugify to ONE doc_id: a stale row at the old root `corpus/02-hellenic/**` (1185 rows: iron_ore 533, shipbuilding 379, vessel_valuations 273) and the live copy at `reports/hellenic/**`; plus `reports/broker_reports/**/{carriers,general_broker}/` mirroring the per-publisher digests (277 md / 172 distinct basenames = 105 duplicate basenames). `prune_missing_sources` never removed the stale rows because the corpus files still exist.

**3. FIX (process_knowledge.py, uncommitted on `main`).** `prune_superseded_mirror_rows()` drops manifest rows whose (source,category,basename) is produced by a discovered file at a different path; discovery is deduped on (source,category,stem) preferring the manifest path; a final `dedupe_manifest_rows_by_doc_id()` keeps one row per doc_id.

**4. VERIFIED offline on the real CI manifest:** 1290 dup doc ids -> prune drops 1185 rows -> 105 left -> doc_id dedupe -> **0**; hellenic counts become exactly 1203/379/274. py_compile OK.

**5b. TREE/CHUNK LAYER VERIFIED.** Fed the deduped manifest (11316 rows) into the validator's own `inspect_trees()`/`inspect_chunks()`: **dup tree node ids 3337 -> 0, invalid section refs 28731 -> 0**, dup chunk ids 0. Also measured: the 1185 corpus/02-hellenic files are stale re-renders of the live reports/hellenic copies (identical extracted text, older mtime), so pruning them loses nothing. Still unverified: duplicate section-index node ids 2047 and linked-assets-failed 1311 (environmental/derived).

**5. NOT verified (honest):** the full process->validate chain was not reproduced locally (this box's `knowledge/derived/*` is stale/gitignored and the local validator, 31 min, prints a DIFFERENT metric set than the runner). So whether invalid-section-refs / section-index dups / linked-assets-failed reach 0 is INFERENCE, not measurement. Local clean-manifest baseline fails on OTHER things (missing sources 21, hash mismatches 245, coverage gaps 15). The fix must land on `main` for CI to see it; left uncommitted per "never touch main".

---

**THIS RUN (2026-10-05 15:0x-h, source-by-source, 30m job) - GUARDRAIL FIX VERIFIED IN CI; THE NEXT BLOCKER (VALIDATE) ROOT-CAUSED. Evidence `docs/knowledge_validate_blocker_verdict.md`.**

No extraction job running (tasklist python.exe = Hermes gateway/litellm/code_review_graph; tree CLEAN on `main`, HEAD == origin/main == 9fb0aaafd). The 30m prompt (verify xclusiv, then fearnleys/intermodal/...) is STALE - xclusiv 266/266, all brokers CLOSED, non-broker corpora all extracted (poten 1087/1087, drewry 849 md, seabrokers 98, hellenic 3781 md, breakwave 3501 md). Nothing to extract -> this run worked the top open, APP-VISIBLE item: the 6-day-frozen QA/knowledge tier.

**1. The 19:2x guardrail fix WORKS in CI.** Dispatched the workflow by hand (`gh workflow run "Daily Knowledge Update"` -> run 37329812815). Step 10 "Guardrail - verify Breakwave signals freshness" = **success** (it failed on all 6 runs 2026-09-29..10-04). Local control `check_breakwave_freshness.py --check signals_vs_reports` -> EXIT=0.

**2. NEW BLOCKER = step 11 "Validate updated knowledge" (`scripts/validate_knowledge.py`, exit 1).** Commit is SKIPPED, so the QA tier STILL does not advance. CI counts: **duplicate doc ids 1290; chunks with invalid section refs 28731; duplicate tree node ids 3337; unresolved required local linked assets 1393; frontmatter section-count mismatches 7; coverage TOTAL processed 10147 > files 8962 (missing=-1185)**. validate exits non-zero on ANY summed failure, so the whole set must go to 0.

**3. ROOT CAUSE 1 (PROVEN) - broker digests are MIRRORED twice.** `reports/broker_reports/<year>/` holds every digest under a publisher dir AND under `carriers/` and `general_broker/`. 277 md files, 172 distinct basenames = **105 duplicate basenames; 102 content-identical duplicate groups**. `carriers/` was added by `9fb0aaafd` ("mirror ... broker digests"), `general_broker/` by `0924975de`. `make_archive_doc_id()` omits the directory, so both copies yield the SAME doc_id; `process_knowledge.py:1380` globs `REPORTS_ROOT/broker_reports/**/*.md` recursively -> double ingest. The validator's printed duplicate doc ids are all `broker_reports_broker_report_...`.

**4. ROOT CAUSE 2 (measured, path not yet pinned) - hellenic doubles for 3 categories.** CI processed: iron_ore 1203->1736 (+533), shipbuilding 379->758 (2x), vessel_valuations 274->547 (~2x) = exactly the -1185. `corpus/02-hellenic/<cat>` mirrors `reports/hellenic/<cat>` 1:1, but dry_charter/tanker_charter/demolition (also mirrored) are NOT doubled -> a category-scoped discovery/merge path in `process_knowledge.py`, not a root-scoped one.

**5. FIX DIRECTION (NOT applied - owned by the parallel automation on `main`):** de-mirror `reports/broker_reports/**/carriers|general_broker`, OR make `process_knowledge` dedupe discovered paths by doc_id (first-wins). The 3.3k dup tree nodes + 28.7k invalid section refs are the same defect (a dup doc id duplicates its tree, invalidating its chunks' refs). No repo tree changes this run (diagnosis only); nightly 15:30 UTC CI will re-fail at step 11 until fixed.

---

**THIS RUN (2026-10-05 19:2x, source-by-source, 30m job) - THE APP-VISIBLE KNOWLEDGE (QA) TIER HAS BEEN FROZEN 6 DAYS; ROOT-CAUSED TO A CI GUARDRAIL AND FIXED (tested). Evidence `docs/knowledge_pipeline_stall_verdict.md`.**

No extraction job of ours running (live python.exe = Hermes gateway + litellm + code_review_graph; branch `main`, local HEAD == origin/main == 380961259; a parallel automation commits ffa-live ticks). The 30m prompt (verify xclusiv, then fearnleys/intermodal/...) is STALE - xclusiv 266/266 and every broker source CLOSED (re-measured this run: across all 14 `corpus/01-brokers/*`, **0 PDFs are newer than that source's newest md**). Nothing new to extract, so this run fixed the largest OPEN, APP-VISIBLE defect instead.

**1. THE FINDING.** The QA chunk tier the app serves (`knowledge/chunks/*.jsonl` -> index.html `qaSrcHellenic`/`qaSrcIronOre`/`qaSrcShipbuilding`/`qaSrcBreakwave`/`qaSrcBaltic`/`qaSrcBooks`) has not advanced since **2026-09-29** (`index.json` `generated_at` 2026-09-29T17:23Z; last commit touching `knowledge/chunks/` = `dfd168848`), while the md/corpus tier is current to **2026-10-03** (hellenic iron_ore md at 09-30/10-01/10-02; demolition GMS md at 10-02/10-03). The KB itself is fine - it is the SERVED layer that lags.

**2. ROOT CAUSE (proven).** The GitHub Actions workflow **Daily Knowledge Update** has **failed on 6 consecutive runs since 2026-09-29** (GitHub API), always at step 10 of 14 - **`Guardrail - verify Breakwave signals freshness`**. That step failing SKIPS `Validate updated knowledge` and `Commit if changes`, so the knowledge-bot never commits and the whole QA tier stays frozen, even though step 9 (Process new reports) succeeded. The guardrail = `scripts/check_breakwave_freshness.py --check signals_vs_reports`, reproduced locally: `drybulk signals=None reports=2026-09-29` / `tankers signals=None reports=2026-09-22` -> FAILED.
Cause = an ARTEFACT MISMATCH, not missing extraction: the guardrail reads `knowledge/derived/signals.jsonl` (92 MB, .gitignore'd), whose breakwave rows lag one report (`signals_public.jsonl` drybulk **09-15** / tankers **09-08**), while the dedicated `knowledge/derived/breakwave_signals.json` is CURRENT (drybulk **2026-09-29** / tankers **2026-09-22**). The doc manifest holds all 291 breakwave docs (0 diff vs breakwave_signals.json).

**3. FIX (tested).** `scripts/check_breakwave_freshness.py` now takes the MAX of the legacy `signals.jsonl` reader and a new reader of `breakwave_signals.json`. `--check signals_vs_reports` now returns **EXIT=0** (drybulk 09-29==09-29, tankers 09-22==09-22); before the fix it was EXIT=1. Fallback unchanged when breakwave_signals.json is absent. This unblocks the daily knowledge commit -> the QA tier starts advancing again on the next CI run.

**4. OWNER DECISION:** the guardrail is source-scoped but aborts the WHOLE knowledge commit - one publisher froze hellenic/baltic/breakwave/broker_reports/books/poten for 6 days; consider making it non-fatal. The fix is on `main` UNCOMMITTED (parallel automation active; "NEVER touch main") - it must be committed to `main` for CI to see it.

---

**THIS RUN (2026-10-05 18:4x, source-by-source, 30m job) - BANCHERO W39 ADVANCED FOR ALL FOUR OPEN SERIES + THE "FROZEN FAMILIES" ROOT-CAUSED. Evidence `docs/banchero_w39_backfill_verdict.md`.**

No extraction job of ours running (live python.exe set = Hermes gateway + litellm + code_review_graph serve; branch `main`, a parallel automation is committing ffa-live ticks). The 30m prompt (verify xclusiv, then fearnleys/intermodal/...) is STALE - xclusiv 266/266 and every broker source CLOSED. This run worked the open `NEXT-RUN TARGET` from the 15:5x entry: the W39 banchero gap.

**1. THE PRIOR RUN'S W39 WITHHOLD IS NOT REPRODUCIBLE - W39 IS CLEAN.** Both W39 corpus PDFs are BYTE-IDENTICAL (md5 2914f821...); the canonical md extracts freight=90 ffa=36 commod=36 (W38=90, W37=87/89) - no tenor misroute. Verified: (a) all 162 W39 values verbatim in the PDF's own text layer (0 misses); (b) W39 `rate_previous` == W38 `rate_current` exactly (BCI 52,315; BPI 20,262; BSI 22,332; TD3C 1165.0); (c) the odd `TD3C-TCE 1,234,685 usd/day` is the publisher's own scale (same page's chart axis is 0..1,400,000), so it is FAITHFUL. Appended: freight 20,497->**20,587**, ffa 7,690->**7,726**, commodities 8,519->**8,555**; 0 dupes; idempotent.

**2. WHY secondhand_matrix / vhss / fx / container_fixtures FROZE (root-caused).** `scripts/extract/build_banchero_series.py` parses HTML <table> via BeautifulSoup; the md tier now emits GFM tables, so it finds 0 tables on the newest md and stops at W38 (its sandboxed re-run, `scratch/banchero_build_trial/series_out/`, reproduces the shipped rows and stops at 2026-09-14). The modern md consumer reads these tables but DROPS the W-o-W/Y-o-Y columns. Container fixtures are a second change: a table <=W24, a templated PROSE paragraph from W25 on. The builder was NOT run (its sales output is the known thinner-schema downgrade).

**3. FIX - new `scripts/extract/publishers/backfill_banchero_matrix_fx_vhss.py`** (bespoke GFM/prose reader, builder's schema + date convention, union-append, prefix-asserted, idempotent). Traps fixed in the trial (each would have published wrong rows): the old md renders the change arrow as literal `+/-` so W38 pct cells read `+0.0+/-%` (stripped -> `+0.0%`, else every existing week re-added as a duplicate); the secondhand `Category|…|W-o-W` predicate also matched a TANKER-route table (TC8/TC2/TC14/TC6) -> builder vessel-class whitelist excludes those 4; fixtures prose sometimes omits `@14`; `**bold**` leaked into FX pairs. RESULT (130/130 added rows verbatim-grounded in the PDF text): secondhand 1,891->**1,898**, vhss 469->**553** (+7 W39, +77 W24-W35), fx 244->**288** (+4, +40), container_fixtures 267->**293** (+26). Re-run adds 0 for all four.

**4. STILL OPEN:** container fixtures W25-28/31-34/36 have no published fixtures paragraph (genuinely absent, not dropped). The banchero tier is still NOT displayed (0 `bancosta_*series` refs in index.html) - KB completeness only. Changes LEFT UNCOMMITTED (parallel automation on `main`; "NEVER touch main").

---

**THIS RUN (2026-10-05 15:5x, source-by-source, 30m job) - BANCHERO SERIES GAP ROOT-CAUSED AND W36/W37 BACKFILLED (the "no generator exists" mystery is solved). Evidence `docs/banchero_series_gap_verdict.md` (follow-up section).**

No extraction job running (live python.exe set = Hermes gateway x2 + litellm x2 + code_review_graph serve). The 30m prompt (verify xclusiv, then fearnleys/intermodal/...) is STALE - xclusiv 266/266 and every broker source CLOSED. So this run worked the open `NEXT-RUN TARGET` left by the 14:2x run: the stale banchero freight/ffa/commodity series gap.

**ROOT CAUSE (measured).** The prior run concluded "no script produces freight/ffa/commodities". It does: `run_banchero_world_class_llama.py::extract_structured_tables_from_md` produces all three. It had gone **DEAD on the current md format** - its table detector looks for `"| ---"`/`"|:---"`/`"|---"` in the header separator row, but the md tier now emits GFM **aligned** separators (`| :--- | :--- |`), which match none of them, so it returned **0 rows for every category**. That is why the three series froze at their Sep-29 build.

**FIX (small, in the parser).** Detection now strips spaces: `any(s in lines[i+1].replace(" ","") for s in ["|---","|:---"])`. Control: W38 md freight **0 -> 90** (== the value already in the series); full 248-doc re-extraction is **byte-identical** to the manual-workaround run. New per-source tool `scripts/extract/publishers/backfill_banchero_series.py` (`--weeks 36 37 [--dry-run]`), union-append + prefix-equality assert + idempotent.

**BACKFILLED (W36, W37):** freight 20,321 -> **20,497** (+176), ffa 7,618 -> **7,690** (+72), commodities 8,447 -> **8,519** (+72). Existing prefix of all three files is **byte-identical** to the pre-run control (`scratch/banchero_gap/backup_20261005_1550`, md5 == `control.md5`); 0 duplicate keys; every appended `rate_current`/`price_current` present **verbatim in the doc's own md** (freight 87/87 + 89/89, ffa 36/36, commodity 36/36); W37 BCI `rate_previous` 46,172 == W36 `rate_current` (consecutive).

**W39 WITHHELD** - extracts freight 108 (vs 87/89) because ~18 FFA tenor rows (`Sep-26`,`Q4 26`) misroute into `freight_benchmarks` and its `ffa_assessments` is short (18/36). Needs a render-and-look / layout fix; do NOT blind-append. Also open and untouched: `secondhand_matrix`/`vhss`/`fx` lack W39, `container_fixtures` stale at W23 (same `build_banchero_series.py` path).

**Low priority confirmed:** the tier is NOT displayed (0 `bancosta_*series` refs in index.html) and TD3C/TC1-TC11 already sit in the live feeds - KB-completeness, not a dashboard defect. Never run `stack_banchero_series.py` as-is (guarded). Changes LEFT UNCOMMITTED (on branch `main`, a parallel automation is active; "NEVER touch main"). Ledger defect list still EMPTY.

---

**THIS RUN (2026-10-05 15:1x, hourly supervisor) - ALL FOUR AUDIT JOBS VERIFIED COMPLETE; the carried Banchero series refresh is MEASURED TO BE A SCHEMA DOWNGRADE and NOT applied. Evidence `docs/banchero_refresh_not_downgrade_verdict.md`.**

No live job is running: no delegation task-log newer than 2026-09-22, no python/duckdb process at check time (a sibling automation DID commit 3d0b3e529 fix(star-asia) at 15:24 during this run - broker files), so this run kept OFF broker outputs.

**Audit freshness (all four outputs present):** text_audit.json + text_audit_recheck.json (Oct-5 00:20), table_audit.json (Oct-4 22:46), gap_verify.json + gap_verify_recheck.json (Oct-4 22:43), vision_candidates.json (Sep-23 16:42 - one-time feasibility probe, no refresh needed). qaudit_*/sweep_v2/systematic_sweep all present (Sep-22/23).

**Audit #1 (text) CLOSED - independently re-verified this run.** Chunk tier healed: manifest declares 106,174 chunks / 93 files; on disk 106,503 / 93 = **SHORT files 0** (the 17,338 shortfall recorded 2026-10-04 is gone). 6 other zero-byte files under knowledge/chunks/ are NOT manifest-declared (placeholder parent shards, not a gap). corpus text = 16,803 text.jsonl (124 empty-on-purpose image-only).

**Audit #2/#3/#4 unchanged and consistent.** corpus.duckdb (read-only): cells 6,726,703 / catalogue 189,481 / series 5,743 / series_points 1,193,579 - reconciles. EURO_DECIMAL_MISPARSE remains CLOSED (100% correct on 105,202 strict EU-decimal cells); gap_verify recheck still shows BOTH CONSTRUCT survivors false.

**Banchero NEXT-RUN target DISPROVED as a safe fix.** build_banchero_series.py does NOT emit freight at all (freight 20,321 rows, identical to delivered - the W36/W37/W39 freight gap is untouched), and its sales output is a THINNER 16-col schema (vessel/buyer/seller) vs the delivered 17-col (vessel_name/buyers/price_raw/ss) = a downgrade. newbuilding -417 / demolition +320. Running it is NOT the "would add W36/W37/W39" win the 14:2x entry assumed. Closing the freight gap needs a NEW bespoke banchero freight md consumer (owner decision; tier is not displayed, 0 index.html refs, benchmarks already in the feeds).

**Owner action needed:** decide whether to build the banchero freight consumer (new pipeline) - the only open, non-displayed, free item. Ledger defect list still EMPTY. Nothing mutated this run (read-only).

---

**THIS RUN (2026-10-05 14:2x, source-by-source, 30m job) - BANCHERO SERIES: STALE GAP + A ZEROING LANDMINE FOUND, TREE RESTORED BYTE-IDENTICAL. Evidence `docs/banchero_series_gap_verdict.md`.**

No extraction job running (live python.exe set = Hermes gateway x2 + litellm x2 + code_review_graph serve). The 30m prompt (verify xclusiv, then fearnleys/intermodal/...) is STALE - xclusiv is 266/266 and **every broker source is CLOSED** per this file. So this run verified a claim instead.

**1. The stale ACTIVE JOB block is corrected (below).** Banchero Costa is **248/248 md** (`data/extracted/llamaparse_banchero/*.md`, newest mtime Oct-3 11:06; run.log ends with the W38+W39 docs parsed, credits~2832). The "243/244 BLOCKED on credits" text is Sep-28 and no longer true.

**2. STALE SERIES GAP (real, bounded).** The 10 `bancosta_*_series.csv` were last built **Sep-29 11:53**; W36/W37/W39 md were created **Oct-3**. `bancosta_freight_rates_series.csv` (20,321 rows) ends `2026-08-31 (W35)` then jumps to `2026-09-21 (W38)` - **W36/W37/W39 have NO rows** although their md holds the tables (W36: 56 HTML tables incl TD3C/C10/BCI; W37: 58; W39: 19). 244 distinct docs in the series vs 248 PDFs; the 4 missing are exactly W36, W37, W39 + the week-39 dup.

**3. LANDMINE (root-caused; GUARD ADDED).** `scripts/extract/publishers/stack_banchero_series.py` (added whole in `be2f5818d`, 2026-09-30 - it never produced the registered series) is BROKEN for the current layout: (a) non-recursive `MD_DIR.glob("*.tables.json")` while the canonical 249 sidecars live in YEAR subdirs `md/banchero_costa/<YYYY>/`; (b) stale schema - it expects `metadata/reported_sales/freight_benchmarks`, but the sidecars are `{source_file,stem,issue_date,report_week,tables,row_counts}` (and carry ONLY sales/newbuilding/demolition, no freight). **Running it ZEROED all 10 series CSVs (freight 20,321->0).** Hit and fully reverted; a guard now refuses to write when 0 rows are parsed (verified exit=2, series untouched). Uncommitted.

**4. RESTORE PATH (reproducible).** `scratch/bancosta_dedup/PRE_<series>.csv` + `filter.py` (dedup on all columns except `source_file`) reproduces the canonical counts exactly: sales 3,244->**3,220**, newbuilding 2,391->**2,377**, demolition ->**959**. After restore **all 10 series md5-match the pre-run control** (`scratch/banchero_gap/control.md5`). `build_banchero_series.py` (committed) reads the md and emits the 7 series + sidecars, but NOT freight/ffa/commodities - no current script produces those 3 (grep of scripts/ finds none).

**5. THREE-BASELINE TEST = LOW PRIORITY.** TD3C/TC1-TC11 already sit in the feeds (`data/clarksons/fearnleys_benchmark_rates_continuous.csv`, `gibson_tanker_rates_continuous_daily.csv`, `data/derived/tanker_forward_curves*.csv`), and `index.html` references **0** `bancosta_*series` / **0** banchero md. None of the tier is displayed; the staleness is a KB-completeness item only.

**NEXT-RUN TARGET:** write a correct sidecar->series consumer (recursive glob + the real `tables/row_counts` schema) OR refresh the 7 reproducible series via `build_banchero_series.py` + `filter.py` (would add W36/W37/W39). Freight/ffa/commodities cannot be refreshed by any current script. Never run `stack_banchero_series.py` as-is (now guarded). Carried human/paid calls unchanged (iron-ore two-writer; VV image recall). Ledger defect list still EMPTY.

---

**THIS RUN (2026-10-05 14:1x, hourly supervisor) - `parse_number` x1000 REGRESSION FIXED at the root (shape-gated), validated 18/18. Evidence `docs/parse_number_shape_fix_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway x2 + litellm x2 + code_review_graph serve; the 13:44-13:46 mtime on the iron-ore chunk shards is the 13:3x run's heal, not a live job). The prior run's named NEXT-RUN item ("make parse_number's x1000 rule SHAPE-based") is now DONE and measured.

**Fix:** `scripts/process_knowledge.py::parse_number` rescaled ANY dotted value in [5,100) by 1000, so the iron-ore re-ingest turned 30.43 -> 30430.0 / 13.21 -> 13210.0 (the md was reverted last run). The rescale is now gated on shape - only a dot followed by EXACTLY three digits (thousands signature): `re.fullmatch(r"-?\d+\.\d{3}", token)`. py_compile OK; diff 8+/5-. Validated on the ACTUAL function (AST-extracted): 18/18 cases - 9.750->9750, 60.000->60000, 82.900->82900, 8.700->8700 preserved; 30.43, 13.21, 8.7, 4.999, 1.234 left untouched. Only process_knowledge.py carried the rule (the per-source copies do not) - not touched.

**Also verified this run (closes the text-audit chunk item):** manifest declares 106,174 chunks across 93 chunk files; on disk 106,503 across 93 - **SHORT files 0**. The 11 empty + 6 partial hellenic shards reported 2026-10-04 are fully healed (iron_ore 2022 17,381 / 2026 4,911; shipbuilding + vessel_valuations shards non-empty).

**NOT done:** no iron-ore md re-ingest - the fix is inert until regeneration and re-ingest is the exact operation that caused the regression; left for a controlled pass. Changes UNCOMMITTED.

---

**THIS RUN (2026-10-05 13:3x, source-by-source, 30m job) - IRON-ORE CHUNK GAP HEALED (app-visible), AND A `parse_number` x1000 REGRESSION FOUND + REVERTED. Evidence `docs/iron_ore_chunk_heal_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway + litellm + code_review_graph serve; the 13:02 mtime churn on knowledge/ was a sibling's checkout, not a job). All named sources remain CLOSED: across corpus/01-brokers, every source's md is NEWER than its newest PDF (0 newly-collected-unextracted).

**The 2026-10-04 23:5x target is done.** The 11 empty hellenic shards were already healed by commit 0924975de (shipbuilding/vessel_valuations). The ONLY short shards left were 3 iron-ore ones; ran `scripts/repair_hellenic_shards.py --categories iron_ore` (corpus/02-hellenic override, LLM off): **533/533 docs, 0 errors**. Chunks 92,299 -> 106,514; 2022 shard 6,544 -> 17,381 (155 missing docs recovered), 2026 1,752 -> 4,911 (116 recovered). Re-audit: **short shards 0, docs-with-zero-chunks 0**. Chunk text verified against the PDF (30.43 C3, 13.21 C5) - raw values CORRECT, no x1000 in any shard.

**REGRESSION (reverted):** the same run regenerated `knowledge/docs|trees/hellenic/iron_ore/**` through `process_knowledge.parse_number`, whose global rule (`35b468aa6`, 2026-06-23) multiplies any decimal in [5,100) by 1000 - RIGHT for the OCR `9.750`->9750 case, WRONG for iron ore (30.43 -> 30430.0). Verified against the rendered PDF; control doc 2022-01-04 HEAD md 87400=0 -> regenerated 87400=2. **Action:** `git checkout HEAD -- knowledge/docs/hellenic/iron_ore knowledge/trees/hellenic/iron_ore` (kept the correct CHUNK heal - that is what the app serves). Manifest kept (533 iron_ore rows: source_path reports->corpus, counts updated; 10,202 rows, 0 dup).

**OPEN / NEXT-RUN (do NOT blindly re-run the iron-ore repair - it re-corrupts md):** make `parse_number`'s x1000 rule SHAPE-based (exactly 3 decimals after the dot) or source-scoped, validated per source, then optionally re-ingest the iron-ore md. Changes this run are LEFT UNCOMMITTED (intentional vs "NEVER touch main"; sibling's run_fearnleys_normalized.py edit untouched). Ledger defect list still EMPTY.

---

**THIS RUN (2026-10-04 23:5x) - TEXT-AUDIT REFRESH: corpus text COMPLETE and unchanged; the knowledge CHUNK TIER is the open item (17,338-chunk shortfall, 11 empty + 6 partial hellenic shards, all app-referenced). Evidence `docs/text_audit_recheck_verdict.md`, `data/extracted/text_audit_recheck.json`.**

No extraction job of ours was running (live python.exe set = Hermes gateway + litellm + code_review_graph serve; no delegation task-log newer than 2026-09-22). Audit job #1 (`data/extracted/text_audit.json`) still carried its 2026-09-23 stamp while table/gap audits were refreshed 2026-10-04, so it was re-measured against the current corpus + knowledge tier.

**Corpus text: COMPLETE.** 16,803 `text.jsonl` on disk, 124 zero-byte (image-only/scanned), same population as the Sep-23 audit. No new empty or missing text.

**Knowledge chunk tier: OPEN, quantified.** Manifest declares 106,489 chunks / 93 shards; on disk 89,151 / 104 shards = **17,338 shortfall (16.3 pct), all hellenic**. 11 shards declared>0 but 0 bytes (2,456 chunks: hellenic_shipbuilding_2014/2021-2024, hellenic_vessel_valuations_2014/2021-2025) plus 6 partial shards (iron_ore 2021/2022/2026, shipbuilding 2025/2026, vessel_valuations 2026). All 11 empty shards are referenced by `index.html` QA_CHUNK_FILES (hellenic / ironOre / shipbuilding tabs, historical + deep_historical), so the app Q&A silently returns nothing for those years.

**Correction to a stale remediation:** the Sep-23 note said to "re-run the chunk compiler". That is wrong now - the `reports/hellenic -> corpus/02-hellenic` migration left `documents.jsonl` `source_path` stale (2,702 of 3,214 hellenic rows point at a missing `reports/hellenic/...` path; the `corpus/02-hellenic/...` alt exists for all 2,702). `process_knowledge.py --source hellenic` and the `repair_iron_ore_shards.py` template both resolve via that stale path and would SKIP every such doc. Correct fix: give the repair a `corpus/02-hellenic` source override, LLM off, then compact. (The prune risk of the stale paths was already measured and found non-firing prior; unchanged.)

**Nothing was mutated this run** (knowledge tier untouched; read-only audit). Next-run target: the hellenic chunk heal above (bounded, non-paid), after confirming a re-ingest does not DOWNGRADE the existing `knowledge/docs/hellenic/...` md.

---

**THIS RUN (2026-10-04 23:5x, source-by-source, 30m job) - IRON-ORE FAULT 2 BLAST RADIUS MEASURED: the reserved option (a) alone would inject ~2,707 WRONG values. Evidence `docs/iron_ore_fault2_blast_radius_verdict.md`.**

No extraction job of OURS was running (live python.exe set = Hermes gateway + litellm + code_review_graph; no broker/extraction runner). Branch is `main`; a parallel automation is active (last commit e91f66056 23:46). All named sources CLOSED and CURRENT - measured this run: across the 14 `corpus/01-brokers/*` publishers, **0 PDFs are newer than that source's newest md** (nothing newly collected is unextracted). md counts still >= distinct PDFs.

**New, measured, decision-relevant.** The carried `hellenic_iron_ore_pdf_*` two-writer item was root-caused last runs and option (a) (union-preserving upsert + re-stack) is named as its low-risk fix. This run measured the SEPARATE row-selection fault's blast radius from the 1,190 sidecars (`data/extracted/md/hellenic/iron_ore_pdf/*/*.tables.json`, the re-stack's source):

- `benchmark_indices` entries: **11,583**, all carrying a `price`.
- rows with `|change| > 0.5*price` (impossible daily change = the stats-row signature): **2,707 (23.4%)**; by unit RMB/wet-tonne 1,294 of 4,629, USD/dry-tonne 1,413 of 6,954.
- concentrated by index name: IOPI58 / IOPI62_61 / IOPI65 / IOPLI62 **395 each** + `_CFR_EQ` variants.
- ground truth (2021-07-14 sidecar IOPI58): `price=1027, change=1052, change_pct=1267, mtd=1199, ytd=1251, low_52w=1251, high_52w=1104` vs the page's `1240 / -17 / -1.4% / 1251 / 1104 / 755 / 1421` - price is the March period, change the April one, and low>high (inverted, impossible).

**Consequence:** option (a) recovers the blank `value` column (11,553 of 11,625 rows) from the sidecars, but the sidecars THEMSELVES hold the mis-selected row for those 2,707 - so option (a) alone would publish plausible-looking WRONG prices/changes. The parser value-gate (`low <= price <= high`) must land in the SAME pass. The gate is sound on this data (correct row 755<=1240<=1421 passes; stats row 1027/l.1251/h.1104 fails). The defect is LIVE in the shipped CSV (`change` imported verbatim) but **no `index.html` consumer reads that CSV (0 hits)**, so nothing user-visible is affected.

**Next-run target:** unchanged reserved human calls (the two-part iron-ore pass above, now scoped to parser + schema; the VV-matrix image-recall residual - paid). Ledger defect list remains EMPTY.

---

**THIS RUN (2026-10-04 23:1x, source-by-source, 30m job) - SESSION CLOSED OUT: NOTHING LEFT TO EXTRACT, THE LEDGER IS EMPTY, AND THE DUPLICATE-KEY CENSUS IS NOW FULLY DIAGNOSED (31 rows, all faithful or a single-date image artefact). Evidence `docs/dupe_key_census_verdict.md`.**

No extraction job of ours was running (live `python.exe` set = Hermes gateway + terminals). This run first re-verified the whole programme state, then worked the ONE open measurement thread the state filed as "NEXT RUN: diagnose the small ones".

**Liveness + coverage re-verified (measured this run).** 16,206 `.md` across `data/extracted/md/*`; every named source md >= its distinct PDFs. `tests/test_hellenic_extraction.py` = **12 passed** (Python312). DB `corpus.duckdb`: 8,144 docs / 6,726,703 cells / catalogue 189,481 / **0 doc_stems with zero cells**; series 5,743 / 1,193,579 points. corpus/books complete (12 md beside 12 PDFs). No fresh table md post-dates the DB rebuild (the newest md files are a sibling's breakwave prose insights).

**CLOSED - the apparent corpus/02-hellenic gap is pure duplication, measured.** corpus/02-hellenic holds 8,026 PDFs vs hellenic md 3,755. Not a gap: iron_ore stores each report twice (2,248 flat in `pdfs/` + the year-partitioned copies = 4,523 files) and the runner dedups to **1,182 processed / 1,190 md**; shipbuilding (1,362 files) = **139 distinct Clarkson Hellas bulletins -> 165 md** + 351 breakwave files (breakwave has its own extraction). demolition 2,141 files -> 1,613 md (multi-writer family already closed).

**CLOSED - duplicate-key census (was 265 rows, now 31), every row accounted.** Re-measured key = every column except `source_file` across all 175 series CSVs: `hellenic_vv_matrix` 15, `xclusiv_sales` 5, `star_asia_demolition` 4, `poten_top_charterers` 2, `star_asia_deals` 2, `carriers_sales` 1, `star_asia_ferrous_scrap` 1, `star_asia_snp_sales` 1. The two NOT previously diagnosed are now proven: (a) star_asia `_demolition`/`_deals`/`_snp_sales` are the **faithful W41/W42 cover misprint** - the W42 PDF's own cover literally prints `WEEK 41 - October 14, 2023` (read from pymupdf page 0), so both files stamp 2023-10-14/week 41; rows stay distinct by `source_file` (the `/snp_sales` `MSC REN V 18.5 $M` row is the same class); (b) `hellenic_vv_matrix` 15 are all on one date (2026-01-28) from the SAME file twice - the cached image transcription `..._img2.md` repeats its `Year 10` row (`['10','5','10','15','20','25']`); single-date, pre-existing, **0 consumers** (0 hits in `index.html`). The rest are the documented faithful set. No genuine dedup defect remains.

**Remaining open = human calls only (unchanged, none actionable unattended):** the `hellenic_iron_ore_pdf_*` two-writer family (schema/ownership - option (a) union-preserving upsert named, low-risk, but `--sample` ALSO re-stacks all 17 CSVs so a partial run would destroy the SMM writer's rows: it must be one controlled full pass, ~43 min, = the reserved call); the VV-matrix image-recall residual (paid); the DB `label_series` (older pipeline, read by nothing). Ledger defect list EMPTY.

**THIS RUN (2026-10-04 22:2x, source-by-source, 30m job) - GAP-VERIFY RE-CHECK against the CURRENT DB: both CONSTRUCT survivors remain FALSE CONSTRUCTS, reproduced. Evidence `docs/gap_verify_recheck_verdict.md`.**

`data/extracted/gap_verify.json` predated the 2026-10-03 DB rebuild, so its two CONSTRUCT-survivor rebuttals (ssy, carriers) were re-verified on the current DB (rebuilt 2026-10-03, v3 applied 2026-10-04 17:34). Artefact `data/extracted/gap_verify_recheck.json`.

**Live work:** a PARALLEL agent's `scripts/breakwave_insights_scraper.py --year 2026` (PID 20724, started 22:28:58, alive) was writing breakwave metadata - so this run kept OFF all breakwave/broker outputs. Our own ledger defect list is EMPTY; nothing of ours was dead or wedged.

**Claim 1 - ssy Capesize trades: PRESENT.** label_series (source='shipbrokers', doc_stem LIKE '%ssy%') = 500 issues / 14,944 cells. 14 named $/t routes each at 130-131 issues (DAMPIER/QINGDAO, RICHARDS BAY/MUNDRA + /ROTTERDAM + /FANGCHENG, TUBARAO/JAPAN + /ROTTERDAM + /QINGDAO, CAPE LAMBERT/ROTTERDAM, QUEENSLAND/JAPAN + /ROTTERDAM, NARVIK/ROTTERDAM, PUERTO BOLIVAR/ROTTERDAM, SALDAHNA BAY/QINGDAO, SEVEN ISLANDS/ROTTERDAM); T/C legs 131-132 each; Calculated Index 260.

**Claim 2 - carriers composite indices: PRESENT.** cells (doc_stem LIKE '%carrier%') = 2,623 index-name cells / 127 issues; DSPA/BSPA/TSPA/DSRA/TSRA/BSRA = 127 issues each, BNBI/DNBI/TNBI = 112 each. Only 49 carrier series are promoted under 'shipbrokers', so the sweep that queried just series/series_points missed them.

**Also fixed this run (documentation staleness, not corruption):** `data/extracted/table_audit.json`'s corpus block still printed the superseded 2026-09-23 counts (catalogue_tables 192,535 / cells 6,946,400). Back-filled to the CURRENT DB (catalogue_tables 189,481 / cells 6,726,703 / engines camelot-stream 5,386,900 + pdfplumber 1,323,087 + html-table 16,716 / shapes grid 138,577 onecol 21,804 empty 14,532 single_cell 7,669 blob 6,899 / zero-stored 14,532), and catalogue_n_cells_sum == cells reconciles True. Prior values preserved in `table_audit_rederive.json`.

**Next-run target:** unchanged carried human/display calls - the VV-matrix image-recall residual (paid); the two-writer `hellenic_iron_ore_pdf_*` family (root-caused, one controlled pass away). Ledger defect list remains EMPTY.

---

**THIS RUN (2026-10-04 22:0x, source-by-source, 30m job) - SERIES TWO-WRITER COLLISION AUDIT: the class is CONFINED, and the iron-ore fault 2 is now root-caused to the line. Evidence `docs/series_two_writer_collision_audit.md`.**

No extraction job of OURS was running: the live python.exe set is the Hermes gateway + litellm + code_review_graph serve, PLUS a sibling process `scripts/extract/dry_run_broker_simulation.py` (PID 3172, started 22:00:21, NOT ours - a parallel agent's incremental-ingest harness; it writes broker md/series, so this run kept OFF broker md/CSV outputs). All named sources CLOSED (md counts >= distinct PDFs: advanced_shipping 255, star_asia 199, ssy 531, xclusiv 272, affinity 249, agora 433, ism 116, lion 96, intermodal 258, banchero_costa 251; poten 1087, drewry 849, hellenic 3755; carriers/clarksons/gibson/baltic md dirs present). The ledger defect list is EMPTY, so this run hunted the ONE open defect class rather than inventing work.

**Audit (read-only, all 172 `data/extracted/series/*.csv`): per-column blank ratio, flag >=95%.** 21 files flagged; 20 benign (record_type-differentiated wide-union schemas where a column applies to one record type - `bancosta_newbuilding.owner/size/yard` blank because the 871 `order` rows carry that in free-text `comments`; vestigial `value_text` alternates next to a populated numeric `value`; unused/derivable `sector`, `CBM`). **The ONLY file family with the collision signature is the 5 KNOWN `hellenic_iron_ore_pdf_*` files** (indices 11,553/11,625 blank; brands 31,272/31,470; futures 2,207/2,233). **No new two-writer collision exists.** Script `scratch/empty_column_scan.py`.

**Fault 2 (row selection) COMPLETED - root cause to the line.** From `cache_mmi_iron_ore_pdf/*b472c50*.md` (2021-07-14), reproduced with the exact `parse_page2` row collection (`scratch/verify_row_selection.py`): LlamaParse emits the multi-period STATISTICS table as an HTML `<table>` (row idx 18: `IOPI58 | 58% Fe Fines | 1027 | 1052 | 1267 | 1199 | 1251 | 1251 | ...`); `parse_page2` consumes ALL HTML `<tr>`s before markdown pipe rows, and `add_idx` keeps the FIRST `(index_name, market)` match, so the statistics row beats the correct markdown daily-benchmark row at idx 207 (`1240 | -17 | -1.4% | 1251 | 1104 | 755 | 1421`). Both rows are 16 cells, so the `len>=15` gate cannot separate them. **Value-based fix:** the benchmark row satisfies `low <= price <= high` (755<=1240<=1421); the statistics row violates it (price 1027, low 1251, high 1104) - a gate in `add_idx` rejects the stats row and accepts the benchmark row (verified on IOPI62/IOPI65/IOPLI62 too). Alternative: markdown-before-HTML ordering.

**Impact = NOT displayed, low priority:** `index.html` references no `hellenic_iron_ore_pdf_*` CSV (0 hits) and the app renders iron ore from `knowledge/chunks/hellenic_iron_ore_*.jsonl` (built from RAW PDF text, CORRECT). So the wrong value lives only in the md `benchmark_indices` table + the non-displayed indices CSV. A `run_hellenic_iron_ore_pdf.py` re-run also re-stacks all 17 CSVs, so the row-selection fix and the union-preserving upsert must be applied TOGETHER in one controlled pass - the schema/ownership call stands as recorded. Not changed this run.

**Next-run target:** unchanged carried human/display calls - the VV-matrix image-recall residual (paid); the two-writer `hellenic_iron_ore_pdf_*` family (now fully root-caused, one controlled pass away); the GMS/hellenic-demolition two-writer owner call (state line ~355). Ledger defect list remains EMPTY.

---

**THIS RUN (2026-10-04 20:5x, source-by-source, 30m job) - HELLENIC VESSELSVALUE DATE CONVENTION APPLIED (was the carried "one command away" item): page-title date now wins over the filename CRAWL date, and the sales runner's missing 3x/5x dedup was ported from the matrix runner. Evidence `docs/hellenic_vv_date_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway). All named sources
CLOSED. This run took the state file's named next-target and executed it.

**Fix (2 runners, API-free).** `_title_iso_date()` added to both; `issue_date = page-title
date or filename`. The image cache is keyed on the IMAGE STEM, not the date, so the 266-entry
`cache_hellenic_vv/` served every matrix parse -> 0 LlamaParse calls.

**Second defect found + fixed:** the sales runner never got the 2026-10-03 `dedupe_report_copies`
the matrix runner did, so 6 of 261 pages (3 copies of Feb-17-2026, 5 of Mar-31-2026) landed in
`hellenic_vv_sales_series.csv` 3x/5x - measured **36 rows on 2026-02-19 (3x12)** and **45 on
2026-04-01 (5x9)**. Helper ported; rows now 12 / 9.

**Measured after (all 3 series): rows sales 2,122 -> 2,062 (-60 = the 24 + 36 de-duped rows);
matrix 12,350 (unchanged); benchmark 124. 0 files still on the crawl date; 0 source_file with
>1 issue_date; 0 page-date collisions; 0 exact-dup rows (matrix's 15 are pre-existing, in the
backup). Example: 2021-11-17 (crawl) -> 2021-11-16 (page).** md = 255 files, 0 unpadded names.
The md dir was wiped first (an unpadded-day bug in this run's first trial had left mixed names).

**NOTE for a future run:** BOTH VV runners write md to the SAME `<year>/vv_<date>.md` path -
a pre-existing collision. Sales was run LAST to keep the historical sales-format deliverable;
a run that reverses the order silently changes the md format. Candidate one-line cleanup, not done.

**ALSO THIS RUN - the carried `hellenic_iron_ore_pdf_*` two-writer family is now ROOT-CAUSED and measured (`docs/hellenic_iron_ore_two_writer_verdict.md`), not applied.** Two runners (`run_hellenic_iron_ore_pdf.py` old MMI 6-page format, `run_smm_iron_ore_daily.py` new SMM 1-page format) write the SAME 5 filenames with DIFFERENT column sets; run_smm's `upsert_rows_to_csv` rewrites with its own fieldnames and `extrasaction="ignore"`, so the other writer's columns are silently dropped. Measured empties: indices `value`/`market_type` 11,553/11,625; brands `fe_pct`/`product_type`/`change_pct` 31,272/31,470; futures `price`/`settlement` 2,207/2,233. Ground truth (page 2 of the 2021-07-14 PDF): IOPI58 prints Price 1240 / Change -17 / -1.4%, but the row carries value='' and change=1052/change_pct=1267 (the statistics table's April/May) - so BOTH a schema collision AND a row-selection fault. Fix is a schema/ownership decision (union-preserving upsert vs split files); not applied.

**Next-run target:** the ledger defect list is EMPTY. Remaining carried items are the VV-matrix
image-recall residual (paid - needs a per-page measured comparison) and the two-writer
`hellenic_iron_ore_pdf_*` family. Nothing free and unblocked remains beyond those.

---

**THIS RUN (2026-10-04 20:0x, source-by-source, 30m job) - LION DEDUP FIX CLOSED OUT: the parquet writer's latent double-count fixed, deliverables re-verified, code committed. Evidence `docs/lion_regeneration_determinism_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway + terminal). All named sources
CLOSED (lion 47 unique issues; md counts unchanged). The preceding 19:5x run root-caused lion's
"non-determinism" (the corpus now holds issue W40/2026 as TWO BYTE-IDENTICAL PDFs, so the old
`*.pdf` glob parsed it twice) and fixed `run_lion_tables.py`; it left the edit uncommitted and its
parquet-writer sibling (`run_lion.py`) still globbing without dedup.

**Closed this run:**
1. `run_lion.py` (parquet writer `lion_deals.parquet`/`lion_demometer.parquet`) now dedups
   byte-identical PDFs in `build_txt()` AND dedups the cached `*.txt` list by content in `main()`
   - mirroring `run_lion_tables.py`. Measured: corpus/01-brokers/lion **48 PDFs -> 47 unique,
   1 skipped** (`lion_2026_W40_... == lion_02_10_2026_...`). Syntax-checked. NOT re-run in full:
   its `write_md()` emits a thin pre-frontmatter md that would DOWNGRADE the richer md now on disk,
   so only the parquet path is protected (the fix's purpose).
2. Deliverables re-verified by read-back: `lion_deals_series.csv` 1,269 rows / `lion_sales_series`
   1,164 / `lion_demometer_series` 564 / `lion_demo_sales_series` 105 - **0 duplicate rows each**;
   `lion_deals.parquet` 1,145 rows / 43 issues / 0 dup; `lion_demometer.parquet` 516 / 43 / 0.
3. Committed (current branch): `run_lion_tables.py` dedup + `run_lion.py` dedup + this doc.

**ALSO THIS RUN - the carried "hellenic VesselsValue date convention" item is now MEASURED and
decision-ready (`docs/hellenic_vv_date_verdict.md`), not applied.** Both VV runners stamp the
report date from the FILENAME (crawl date), but 78 of 261 VV report pages carry a DIFFERENT own
date in their `<title>` (69 at -1d, 8 at -2d, 1 at +10d). The delivered series carry the crawl
date (77/78 differing dates present in `hellenic_vv_sales_series.csv`). Switching to the page's
own date is LOSSLESS: the 235 resolvable series files map to 235 DISTINCT page dates, 0
collisions. The exact one-expression fix is named for both runners, with the
`docs/intermodal_issue_date_verdict.md` precedent. Left unapplied (it shifts published dates =
recorded human call); matrix-image parses are already cached so applying it is API-free.

**Next-run target:** unchanged carried human/display calls - the VV date convention (now measured,
one command away); VV-matrix image-recall residual (paid). The ledger defect list remains EMPTY.

---

**THIS RUN (2026-10-04 19:2x, source-by-source, 30m job) - THE LEDGER'S LAST OPEN ITEM CLOSED AS NON-REPRODUCIBLE; THREE CARRIED "SUSPICIOUS VALUE" ITEMS RE-MEASURED AS PUBLISHER-SIDE (faithful). Evidence `docs/residual_faithful_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway). All named sources
CLOSED (md counts >= distinct PDFs: advanced_shipping 254, star_asia 198, ssy 530, xclusiv
271, affinity 248, agora 432, ism 115, lion 95, intermodal 257, banchero_costa 249, poten
1,087, breakwave 3,485, hellenic 3,755). This run worked the carried open list and MEASURED
each item against the source's own page. Result: no extraction defect to fix; the last
ledger item is gone; three "defects" are the publisher's own.

**CLOSED - `bancosta_freight_rates_series.csv` residue (numeric `unit` / `DRY_BULK` sector),
the ledger's only remaining STILL OPEN.** Measured on the current 20,321-row file: numeric
`unit` rows **0** (was 33); any `DRY_BULK` sector row **0** (was 80); sectors are
DIRTY_TANKER 6,554 / CLEAN_TANKER 5,078 / SUPRAMAX 4,397 / PANAMAX 2,158 / CAPESIZE 2,134.
Not present any more -> CLOSED, non-reproducible.

**FAITHFUL (do NOT "fix"):**
- `TC20 LR2 AG-UKC (90k) unit=usd mln 16,606,250` and `TC14-TCE MR USG-UKC usd/day
  7,390,000` (bancosta 2026-09-21 / banchero_costa_2026_W38). The PDF text layer prints
  them verbatim (p10 y=436.1 `'usd mln' '16,606,250' '16,500,000'`; y=561.8 `'usd/day'
  '7,390,000' '6,190,000'`). Internally inconsistent the publisher's way (MR basket
  28,460/day vs one MR route 7.39M/day) - a wrong PUBLISHED value is not our defect.
- star_asia `5y_history` `ALIAGA, TURKEY` year_2021 = **26** on 2026 W01/W03/W04. Rendered
  the cell (W01 p9, 600 dpi) - the ink is exactly TWO glyphs `2`,`6`; rawdict has only `'2'`
  x=243.5 and `'6'` x=249.3. The PDF prints `26`. Also confirmed GADDANI row = W01
  `460,580,540,500,450` and W05 `415,600,540,520,430` both verbatim from the page (the
  week-to-week change in a "fixed" year is the publisher re-issuing the rolling table).
- star_asia exact duplicates: `JOINT LUCK TANKER 2,063 24.12.2022 AWAITING` is printed on
  two consecutive rows of W01 p11; WHITE PALM twice on W51 p12. Faithful.
- `star_asia_2023_W41` and `_W42` both stamp issue_date 2023-10-14 / week 41 (32 rows on
  that date in the demolition series) because the W42 PDF's COVER is misprinted `WEEK 41 -
  October 14, 2023`. Our stamp is faithful to the printed cover; rows stay distinct by
  `source_file`. Not changed.

**Noted, NOT fixed (display-only):** the star_asia md carries 177 rows whose label cell
absorbed the recycling-table footnote (`TURKEY *For Non-EU ships...`). Checked first: the
typed layer is CORRECT - `star_asia_demolition_series.csv` is 3,120 rows = 194 weeks x 4
destinations x 4 segments, 0 missing cells, clean labels (built by
`extract_indicative_scrap_table`, not from the split table). No consumer reads the polluted
label; fixing it needs a liteparse re-render of 193 docs for zero data gain -> deferred.

**Next-run target:** unchanged carried human/display calls (hellenic VesselsValue date
convention; lion regeneration non-determinism - the one genuinely UNINVESTIGATED item;
VV-matrix image-recall residual - paid). The ledger defect list is now EMPTY.

---
**THIS RUN (2026-10-04 18:1x, source-by-source, 30m job) - TABLE-AUDIT `units_fixed` + `per_doc_health` RECOMPUTED ON THE CURRENT DB: the last two stale sections are closed, and the DB rebuild moved unit coverage by 0.05pp. Evidence `docs/table_audit_recompute_verdict.md`.**

No extraction job was running (live python.exe set = Hermes gateway). All named sources
CLOSED (measured: 15,521 .md across data/extracted/md/*; xclusiv 271). This run finished
the recompute the 17:1x run left half-done - its `table_audit_rederive.json` named
`units_fixed` + `per_doc_health` as `prior_still_stale`.

**unit_coverage (d6_zero.py TIER-A/B rule, re-run on data/extracted/corpus/db/corpus.duckdb):**
tables 174,949 (was 178,003); no TIER-A unit anywhere 155,751 (89.03%) [was 158,392
(88.98%)]; no TIER-A in header rows 158,212 (90.43%) [was 160,861 (90.37%)]; no TIER-B
145,567 [was 148,185]. **The parser rebuild did NOT move unit coverage - 0.05pp.** Most
unitless tables are reference BOOKS (Lloyd's Atlas 2,389; Business of Shipping 1,502; Sea
and Civilization 1,192; Maritime Economics 941; Kavussanos 591); by source shipbrokers
75,376 + hellenic 48,421 (route tables whose header carries the unit once). Non-defect.

**per_doc_health (d5_d6.py D5 block):** docs 8,144; cells 6,726,703; catalogue tables
189,481 (14,532 zero-cell 'empty' rows); numeric_share p10 0.0824 median 0.3901 p90 0.5163
max 0.7657 [was 0.0826/0.3916/0.5032/0.7657]; zero-numeric docs 513 (identical). Unchanged
within noise.

**POPULATION NOTE (skill rule):** the audit measures the EXTRACTION DB (cells/catalogue),
NOT the raw corpus tree - stated in the verdict so it is not read as a collection-coverage
number.

Artefact: `data/extracted/table_audit.json` (gitignored) updated in place; prior copies
`scratch/table_audit/table_audit.pre_unitshealth_20261004.json` + `_pre_20261004/units_fixed.pre.json`.
`recomputed_2026_10_04.prior_still_stale` is now EMPTY - all four sections current.

**SECOND FINDING - `EURO_DECIMAL_MISPARSE` (audit outstanding_gap #1) VERIFIED CLOSED on the
current DB.** The audit's rebuild note CLAIMED the fix was applied; verified the artefact on
corpus.duckdb: all **105,202 strict EU-decimal numeric cells (comma=decimal, periods=thousands)
have num_value == the European reading = 100.000%** (0 wrong, 0 null; pre-rebuild 93,076 wrong).
Ground truth (same-document page-text reconciliation - this session has NO vision tool): 20 docs
/ 3,690 strict EU cells -> the literal string is on the exact page 3,690/3,690 = 100.00%.
Spot: '-3,91%'->-3.91, '2,79%'->2.79 (advanced_shipping rendered text). The remaining ambiguous
case (comma + exactly 3 digits, 375,546 cells) is unresolvable from text alone - NOT a defect.
`outstanding_gaps[0]` marked CLOSED and `defects.EURO_DECIMAL_MISPARSE.resolved_2026_10_04`
stamped in the audit json.

**Next-run target:** the carried items are unchanged human/display calls (hellenic
VesselsValue date convention; lion regeneration; the VV-matrix image-recall residual -
paid). The table-audit stale-section thread is CLOSED.

---
**THIS RUN (2026-10-04 16:4x-18:0x, source-by-source, 30m job) - THE EMPTY `measurement_key` IS FIXED AND SHIPPED. The series layer now has 5,743 series / 1,193,579 points (was 5,241 / 1,167,616) and 118,850 fewer headerless data cells. Evidence `docs/measurement_key_verdict.md`.**

No extraction job was running (only the Hermes gateway / litellm proxies). All named
sources CLOSED. This run took the item the 15:4x run root-caused and left as "a design
decision with numbers" and made it a measured, ground-truthed fix that is now LIVE.
Branch unchanged (`auto/extract-fixes-2026-10-04`).

**The fix (3 parts, in `scripts/extract/build_series_sql.py` `col_headers`):**
1. PER-COLUMN header (above THIS column's first numeric row) - the skill doctrine - so a
   chart's tick numbers / prose higher on the page can no longer drag the table's first
   numeric row up and hide the real header row.
2. TABLE-WIDE FALLBACK for a column with no numeric cell of its own (else Clarkson
   Platou's `BUNKER PRICES` is lost - measured).
3. DATE/PERIOD GUARD: a bare date/week header (`01 Oct`, `Nov. 21`, `2021`, `Week 31`) is
   a PERIOD, not a measurement name - blanked so it cannot fragment a weekly series into
   one series per issue. MONTH-SCOPED only, so `5 YEARS`/`12 mos`/`IFO380` are not
   mistaken for dates (a looser rule wrongly blanked 8,600+ of those).

**Ablation (scratch DB copies; control = old script reproduces live 5,241/1,167,616/942,263 exactly):**
| variant | series | series_points | empty_mk |
|---|---|---|---|
| live baseline | 5,241 | 1,167,616 | 2,247 (42.9%) |
| per-column only | 5,250 | 1,106,207 (-61,409) | 1,233 |
| + loose date rule (rejected) | 5,692 | 1,193,726 | 1,839 |
| **SHIPPED (per-col + fallback + month rule)** | **5,743** | **1,193,579** | **1,796 (31.3%)** |

Cell level (population 1,635,971 labelled-numeric cells): headerless 454,396 (27.8%) ->
335,546 (20.5%); +168,381 recovered; 49,531 date-blanks; **0 non-date labels lost**.
Ground truth: Allied 03-10-2021 p9 (pymupdf word positions) recovers ±%/Min/Avg/Max and
blanks the two date columns; Clarkson Platou p2 keeps BALTIC INDEX/EXCHANGE RATE/BUNKER
PRICES and recovers FUJAIRAH. Live rebuild verified by read-back: 5,743/1,193,579/970,291,
`orphans=0 mismatched=0`. Residual: 838 cells (0.05%) net-new prose-like headers, accepted.
Pre-change live DB backed up at `scratch/meas_20261004/corpus.pre_v3.duckdb`.

**Still open (unchanged, human/display calls):** hellenic VesselsValue date convention; lion
regeneration; the VV-matrix image-recall residual (paid); the two-writer hellenic_iron_ore_pdf_*
family; date-vs-measurement classifier is now DONE (this run).

---
**THIS RUN (2026-10-04 16:5x-17:1x, overnight supervisor cron) - TABLE-AUDIT 20-DOC PROBES RECOMPUTED ON THE CURRENT DB (the two subsections the 15:4x re-derive left stale). Evidence docs/table_audit_recompute_verdict.md.**

No extraction job was running (live python.exe set = Hermes gateway + litellm proxy + code_review_graph serve). All named sources CLOSED. This run took the SPECIFIC gap flagged in table_audit_rederive.json and re-ran table_audit.json's "reproducibility_20" and "text_layer_reconciliation_20" against the current corpus.duckdb (rebuilt 2026-10-03), the phase job #2 requirement.

**Blocker found and fixed.** doc_source_map.json pointed at the PRE-migration reports/<src>/... paths; the corpus is now corpus/<NN-group>/... so all 20 sampled docs errno-2 on the first attempt. Re-resolved by basename over corpus/**.pdf -> scratch/table_audit/doc_source_map_current.json (7,539/8,144 mapped; 605 unmapped = non-PDF image-only/html docs). All 20 then resolved.

**reproducibility_20 (pdfplumber re-read, seed 20260922, 20 docs, 0 errors):** median_jaccard_distinct 0.3666, median_recall_db_in_ind 0.2895, median_numeric_recall 0.3182, median_precision_ind_in_db 1.0, db_cells 20,010 vs independent 5,380. Verdict NO FABRICATED VALUES (precision 1.0). Materially better than 2026-09-23 (numeric_recall 0.0034 -> 0.3182) post parser rebuild. CAVEAT: the 20-doc sample was REDRAWN (candidate list changed after path re-resolution) - delta is directional, not same-docs before/after.

**text_layer_reconciliation_20 (PyMuPDF, same 20 docs):** db_numeric_cells 8,061, found in text 8,061, verify_ratio 1.0 (min 1.0), 0 unreadable. Dropped-but-recoverable text tokens 1,795. Every stored numeric cell is text-backed.

**Also re-verified on the current DB (job #3 spot-check, no change):** ssy Capesize PRESENT (509 ssy docs carry Capesize labels; "SSY Atlantic/Pacific Capesize Index" across 113-114 issues, "Atlantic Capesize Index" 129); carriers composite indices PRESENT (127 carriers docs; "Index"/"Baltic CAPE Index"/"Baltic DIRTY Tanker Index" across ~125 issues). Both gap_verify CONSTRUCT survivors remain FALSE CONSTRUCTS.

**Next-run target:** unchanged - units_fixed / per_doc_health still against the 2026-09-23 DB; plus the carried-open human/display calls (hellenic VV date convention; lion; VV-matrix image recall; date-vs-measurement series header classifier).

---

**THIS RUN (2026-10-04 15:4x-16:0x, source-by-source, 30m job) - SERIES-LAYER KEY MODEL: TWO PHANTOMS CLOSED, THE 43% EMPTY `measurement_key` ROOT-CAUSED (and its one-line "fix" measured as WORSE). Evidence `docs/series_key_phantom_verdict.md`.**

No extraction job was running (the live `python.exe` set is the Hermes gateway). All named sources are CLOSED - the prompt's "next source" list is stale (xclusiv is DONE at 271 md; every broker/non-broker unit has md >= distinct PDFs). So this run took the state file's recurring "derived 764-key collisions / 43% empty `measurement_key` / DB `label_series`" item, filed as "a recorded human decision" by several prior runs, and MEASURED it. Result: two of the three are phantoms; the third is a real design call now root-caused.

**PHANTOM 1 - `DB label_series` does not exist as stale data; it is a VIEW.** `information_schema.tables` shows `label_series`, `cells`, `catalogue` all as VIEWs: `cells` = `read_parquet('.../tables.parquet')`, `label_series` = a row-label pivot over `cells`. `label_series` (1,619,891 rows) is rebuilt on every query, so it CANNOT go stale. CLOSED - do not re-flag.

**PHANTOM 2 - the "764 collisions" are a documented design, not a defect.** `(source, entity_key, measurement_key)` with >1 `series_id` = **764** triples / 2,686 series. Every one is separable: `series_id = source\x1fentity\x1fheader\x1fb<block>[ \x1f<class>]`, and 760 of 764 differ by `block_no` (repeat column blocks in one table) while 4 differ by `class_key` (Drewry AIS Crude_Aframax vs LPG_FR vs ...). `block_no`/`class_key` are IN the PK, so no two rows share a `series_id`. The "disjoint ranges" a prior run read as "not a series key" are exactly the signature of DISTINCT blocks sharing a header (or a headerless block). Sampled live: `shipbrokers / 10year us bond / '' / b2..b6` = the Allied market table's 01 Oct / 27 Aug / ±% / Min / Avg / Max columns, 155 pts each. CLOSED as a non-defect.

**ROOT-CAUSED - the 42.9% empty `measurement_key`.** Measured: **2,247 / 5,241 series** carry an empty `measurement_key`, and at cell level **1,000,707 / 2,493,286 numeric data cells (40%)** resolve to no column header. Cause (NEW): `col_headers` in `build_series_sql.py` takes the table's FIRST numeric row at TABLE grain (`group by doc,page,table_idx,engine`), so on any page where a chart's axis numbers sit ABOVE the real table, that first-numeric row is dragged into the chart and the table's own header row is excluded. Ground truth (rendered text layer), Allied Weekly Market Report 03-10-2021 p9: chart ticks (`6.90`, `95.00`, ...) occupy rows 4-15 in cols 7/8 -> table-wide `first_num=4` -> the real header row at row 16 (`01 Oct | 27 Aug | ±% | Min | Avg | Max`) is never seen, so cols 1-6 come back unlabelled.

**The one-line "fix" is WORSE, measured.** Changing the header grain to per-column (`group by 1,2,3,4,5` + `and n.col_idx=c.col_idx`) on scratch copies (live layer reproduced exactly first: `--min-points 20` -> 5,241 / 1,167,616 / 942,263):
- per-column, no threshold: series **143,945 -> 177,998** (+24%) - date-headed columns (`01 Oct`) make each week its OWN series;
- per-column, `--min-points 20`: series 5,241 -> **5,250**, but `series_points` **1,167,616 -> 1,106,207 (-61,409)** (fragmentation pushes points below the threshold).
So the blank header is NOT a one-line grain bug: the header row mixes PERIOD DATES with stats, and a correct fix must classify a date column as an axis, not a measurement name. The naive patch was **reverted** (tracked code unchanged); the live DB was restored from `scratch/serieskey_20261004/corpus.pre_headerfix.duckdb` and verified (5,241 / 1,167,616, identical value sum). Design decision left explicit with numbers.

**Provenance confirmed (not a gap):** the live series layer = `build_series_sql.py --write --min-points 20` (reproduced byte-for-byte). Earlier note that the script yields "143,783 series" was the no-threshold run; with the threshold it is exactly the live 5,241.

**Next-run target:** the remaining items are unchanged human/display calls: hellenic VesselsValue date convention; lion regeneration; the VV-matrix image-recall residual (paid, needs a per-page measured comparison); and now the date-vs-measurement header classifier for the series layer (with the numbers above). The series-layer key-model phantom is closed.

---
**THIS RUN (2026-10-04 14:5x, source-by-source, 30m job) - AFFINITY WS-ERA md RENDERING FIXED: `WS 130.63` no longer rendered as `$131`. 144 md cells -> 0. Evidence `docs/affinity_ws_verdict.md`.**

No extraction job was running (python.exe set = Hermes gateway). No source left to extract, so this run took the carried-open item "affinity WS-era md rounding (144 cells, DISPLAY ONLY)" - the md is affinity's PRIMARY deliverable and the defect was a WRONG displayed value, so it was measured and fixed rather than left as a decision.

**Defect (proven against the rendered page, not another extractor).** In the WS era (68 docs: 2021=26, 2022=42) the CLEAN card header prints `$ / WS` and some routes print `WS 130.63`. `polish_affinity_markdown.py` ran every rate through `format_rate()` (`{val:,.0f}` + `$`), so `WS 130.63` -> `$131` (lost the unit AND the decimal). Ground truth 2021-10-01 p0 panel: `490.8 747.7 'WS 130.63'` -> md `$131`; `525.1 755.8 'WS 25'` -> md `$25`; `542.3 747.7 'WS 130.71'` -> md `$131`. The md also hardcoded `Rate ($/Day)` for the CLEAN block whose printed header is `$ / WS`.

**Fix (source only).** `polish_affinity_markdown.py`: new `format_rate_cell(raw_val,val,unit_source)` renders an explicitly WS-quoted cell as `WS {val:g}` (keeps unit + decimals); new `rate_header(unit)` derives the column header from the block's printed unit; rows now carry `value_raw`/`unit`/`unit_source`. The same fix applied to `orchestrate_incremental_ingest.py` (the live incremental path renders affinity md too, same hardcoded header + `pam.format_rate`); it only sees the modern era so its behaviour is unchanged, but the renderer is now single-sourced.

**Controls (ran ORIGINAL vs PATCHED side by side).** All three series CSVs BYTE-IDENTICAL across the change (`cmp` tce/bda/indices) - the patch touches NO data. md changed in EXACTLY 68 files = {2021:26, 2022:42} = the WS era; the 2021-10-01 diff is only the 4 intended lines. `polish` is idempotent (2 passes byte-identical). Reconciliation: **4,039 / 4,039** TCE rate cells match the exact CSV + printed card, mismatches **144 -> 0**, explicit-WS cells **161**, block-header errors **0/496**.

**Second finding, fixed.** `verify_affinity.py` (after its stale counts below were relaxed) exposed that the 2026-10-02 issue's sidecar was written by the fetcher with NO top-level stamps and NO BDA `records` list that every other sidecar has. Stamped in place via the canonical resolver (`resolve_metadata` -> 2026-10-02, week 40) and regenerated its 3 BDA records; no other file touched. Also relaxed `verify_affinity.py`'s three hardcoded counts (254/247/247) that went stale when the 2026-09-25 and 2026-10-02 issues landed - now asserts `sidecars == mds` and `pdfs >= sidecars` (the 7 extra PDFs are byte-duplicates). Result: **`verify_affinity.py` 6/6 PASSED** (was failing at check 1 on a stale count, then checks 2 and 4 on the incomplete newest sidecar).

**Noted, NOT touched (pre-existing, not this fix):** `affinity_tce_series.csv` / `affinity_bda_series.csv` have TWO writers (`polish` and `run_affinity_tables`) whose `trend_wow` formatting differs (`↑ Firmer` vs `↑Firmer`), so their on-disk hashes move whenever the other writer runs. The CSV row counts match the register's refreshed values.

**Next-run target:** unchanged human/display calls (hellenic VesselsValue date convention; lion regeneration; DB `label_series`; derived 764-key collisions / 43% empty `measurement_key`), plus the VV-matrix image-recall decision. The affinity WS item is CLOSED.

---

**THIS RUN (2026-10-04 13:5x, source-by-source, 30m job) - PUSH + UNCOMMITTED CODE LANDED + ENUMERATION COVERAGE SWEEP (no gap found).**

No extraction job was running. The live `python.exe` set is the Hermes gateway, a `proxy_gateway` litellm server, and `code_review_graph serve`. A PARALLEL sibling agent committed concurrently this run (atlas book work `815d63c90`, and a `docs(state)` log `db330efc7`) - my commits sit on top of those; no collision.

**Landed the unpushed backlog (measured).** HEAD was 6 commits ahead of `origin/auto/extract-fixes-2026-10-04` (PPA backfill, cadence-generator drift, hellenic counts, star_asia deal-date flags) - now pushed. Also committed THREE finished-but-uncommitted fixes that earlier runs documented but never landed (py_compile OK; `verify_registers.py` = 0 mismatches, 170 CSVs / 599,512 rows):
1. `run_hellenic_vv_matrix.py` - `dedupe_report_copies()`: re-measured this run on the live tree, 261 HTML pages -> **255 distinct report titles, 6 extra fetch-date copies** (3 of the Feb-17-2026 report, 5 of Mar-31-2026) that were each parsed independently (tripling/quintupling one report's table). Byte-hash dedupe misses them (each fetch rewrites asset paths). Delivered series already reflect it.
2. `verify_extraction.py` - `find_db_dir()` now looks under `<out>/db` AND `<out>/corpus/db` (the live DB is at `corpus/db`; the old check answered "not built yet" for a 192,535-table / 6,946,400-cell DB).
3. `sync_extraction_register.py` + `update_extraction_register.py` - Star Asia rows refreshed to disk (snp_sales 3,717->3,575, deals 3,327->3,349, demolition 3,072->3,120).
Plus the untracked verdict doc `docs/xclusiv_apply_verify_verdict.md`.

**ENUMERATION COVERAGE SWEEP (skill rule: enumerate, never be told which) - NO GAP FOUND.** The PPA run's defect was a runner globbing subdirs it had moved out of. Swept the same class across the corpus:
- `corpus/01-brokers/*`: for every publisher, md-file count >= distinct-content PDF count (e.g. affinity 248/248, fearnleys 260/260, ism 115 md vs 112 distinct, ssy 530 vs 516). No source is under-covered. (clarksons/carriers md far exceed PDFs - HTML-sourced, not a gap.)
- Non-broker: poten 1,087, drewry 288, breakwave 299, seabrokers 98 - all covered; PPA root strays (110) are covered post-fix.
- `corpus/02-hellenic/iron_ore`: 4,521 PDFs collapse to **1,175 distinct dates** (each report stored as 2 download variants - a crawler `_hash` name + the `_compressed` original - and mirrored at `pdfs/` root and `pdfs/<year>/`); md = **1,190** >= 1,175. The exact 50% md/file ratio is the 2-variants-per-date artefact, NOT a missing half.
- `run_hellenic_iron_ore.py` globs `pdfs/*.pdf` NON-recursively while `run_hellenic_iron_ore_pdf.py` rglobs - a latent fragility, but harmless here because the root holds every report name anyway. Noted, not a data gap.

**Two residuals CLOSED as NON-defects (measured, do not re-chase).**
- `hellenic_vv_benchmark_sales_series.csv` = 124 rows AND register row = 124 - the earlier "124 vs register 141" was stale (pre-resync). Register matches disk.
- `intermodal_macro_series.csv` (4,818 rows): `wow_change_pct` is BLANK on every row, not wrong. No non-reproducible stated change exists anymore (that was the old 3,739-row schema). A blank is a missing value, not a wrong one - left alone (intermodal is a parallel-agent source anyway).

**Measured residual, NOT fixed (needs paid vision).** `hellenic_vv_matrix_series.csv` (12,350 rows / 236 dates) has rows-per-date of 1-78 (modal 78); roughly half the dates carry a partial matrix (e.g. 2021-07-20 = 1 row, 2024-09-25 = 1, 2021-10-05 = 57). Root cause is structural: the matrix comes from a RASTER companion image parsed by an external service (`get_or_parse_image_async` -> `parse_vv_matrix_markdown`), so per-week recall varies with image-parse quality. Recovering it = re-parsing ~2xx images (paid, and the user bars un-measured paid spend) OR accepting it. Flagged with a number so a future run does not re-derive it.

**Next-run target:** the same list of human/display calls (hellenic VesselsValue date convention; lion regeneration; affinity WS-era md rounding; DB `label_series`; the derived 764-key collisions), plus the VV-matrix image-recall decision above.

**THIS RUN (2026-10-04 12:4x, source-by-source, 30m job) - PPA 2013-2014 BACKFILL: the PPA extractor could not see 110 corpus files; fixed, +816 verified rows added (10 new months, 2013-03 -> 2014-07). Evidence `docs/ppa_backfill_verdict.md`.**

No extraction job was running (the python.exe set is the Hermes gateway). No broker source is left to extract, so this run took a genuine in-corpus gap rather than starting a non-existent source - found by ENUMERATION (the skill's rule), not by being told which source.

**What was wrong (measured):** `corpus/09-ppa` now holds **603 PDFs / 358 distinct contents**, but `run_ppa.py` discovered files with `CORPUS.glob("_root_pdfs/*.pdf") + CORPUS.glob("ppa_pdf/*.pdf")` = **493 / 339 distinct**. A corpus reorg had moved **110 PDFs to the corpus root**, invisible to the runner. 85 are byte-duplicates; **19 are distinct contents no runner ever saw** (md5 sweep). All 19 are **2013-2014 Port Hedland**: 10 `summary` (country x commodity grid) + 9 `detailed` (per-vessel listing).

**Fix + result:** discovery now also globs the corpus root, appended LAST to keep row order; `parse_hedland` now skips 0-table docs (`no-cargo-grid`). Re-run family A: **348 paths, 0 failed, 78.5 s -> +816 rows, diff vs installed CSV = 816 added / 0 removed; months 2013-03..2013-08 + 2014-03..2014-07; series 2013-03-01..2026-08-01 (was 2015-01); 4,591 -> 5,407 rows; 265/265 arithmetic checks pass on the 10 new docs.** Ground truth (page text): june_2013 p1 prints `22,947,021.00` -> CSV `22947021.0`. Family B (Dampier): same glob fix, 0 failed; the 2 extra docs were byte-dupes so `ppa_dampier_fy_series.csv` is **byte-identical** (control).

**Controls:** the new committed `scripts/extract/export_ppa_csv.py` reproduces the PRE-change CSV **byte-for-byte** (578,160 bytes, cmp clean) from the pre-change jsonl - so the only deliverable change is the 816 appended rows. Dedup key = value columns, first occurrence.

**Still open (carried):** the 9 "detailed" 2013-2014 per-vessel files are skipped (need their own parser - separate scope); the CSV's `source_file` column carries legacy `_root_pdfs/` paths for old rows (migration artifact, display call); the cadence-audit md still says PPA "493 PDFs" (now 603) - GENERATOR-owned (`generate_cadence_audit.py`), fix the generator not the md. All the prior STILL-OPEN items are unchanged and human/display calls: `hellenic_iron_ore_pdf_*` two-writer family, hellenic VesselsValue date convention, lion regeneration, affinity WS-era md rounding, DB `label_series`.

---
**THIS RUN (2026-10-04 12:0x, source-by-source, 30m job) - CADENCE-AUDIT GENERATOR DRIFT CLOSED: the 12-book block is now EMITTED by the generator, so regeneration is a byte no-op. Commit `d1e458876` (code + doc).**

No extraction job was running (the python.exe set is the Hermes gateway). No source is left to extract - all named sources CLOSED. This run closed the NEW HAZARD the 11:4x run flagged and could not fix.

**Reproduced the hazard (measured):** `python scripts/audit/generate_cadence_audit.py` rewrites `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` WHOLESALE. Diff vs the committed file was `122,141d120` + `53d52` = the entire books block (master-matrix row at line 53 + section 3.5, 12 rows, 20 lines) MISSING from the generator, plus a CRLF/LF flip (Python text-mode translated `
`->`

`; the committed file is LF). Net: 697 -> 676 lines on regeneration.

**Fix (source only):** added a `md_lines.append(<books matrix row>)` after the REGISTRY_DATA loop and a `md_lines.extend([...])` emitting section 3.5 (both read VERBATIM from the committed md, so byte-faithful), and made the writer `newline="
"` so output stays LF. `py_compile` OK.

**Control (measured):** re-run vs the committed baseline now differs on exactly ONE line - `hellenic_athenian_demolition_series.csv (3` -> `(2` (the generator holds the refreshed 2,916; 3,052 was the pre-dedup value; the cell truncates at the thousands comma by design). That line is a CORRECT refresh, so the regenerated file was accepted. Re-running again is a **byte no-op** (idempotent). `git status` clean on both files after commit.

**So the earlier STILL-OPEN item `cadence-audit md hardcodes ... athenian 3,052` and the books-drop hazard are BOTH closed.** The remaining `STILL-OPEN` list is unchanged and all human/display calls: `hellenic_iron_ore_pdf_*` two-writer family (5 files, 2 with 11,553/2,207 empty values - data NOT lost, no consumers; schema-choice = human call), hellenic VesselsValue date convention, lion regeneration, affinity WS-era md rounding (display only), DB `label_series`.

**Also checked + CLOSED this run (do NOT re-chase):** the `signal_vessel_counts_series.csv` HEADER-ONLY lead from the 10-03 16:xx run is already fixed - the file is now 16,058 bytes / 106 data rows (mtime 10-03 17:21) via the dedicated `run_signal_vessel_counts.py`. No action needed.

---

**THIS RUN (2026-10-04 11:1x-11:4x, source-by-source, 30m job) - IRON-ORE TWO-WRITER HAZARD MEASURED IN FULL: it is FIVE files, not one, and two are already silently damaged (11,553 + 2,207 empty values). Evidence `docs/iron_ore_two_writer_verdict.md`.**

No extraction job was running (the python.exe set is the Hermes gateway). No source is left to extract: every named source is closed, and the remaining corpus units are knowledge-tier only (`corpus/10-companies` = 1,310 md SEC filings, `corpus/11-other/panama-canal` = 1 md, `corpus/books` = md, `corpus/09-ppa` done 09-28 families A/B/C). So this run worked the last measured open hazard instead of starting a non-existent source.

**What the prior run flagged (commit 7f83a1ec6) was ONE file (`..._dashboard_series.csv`, wide-vs-long); the sweep under-measured.** `run_hellenic_iron_ore_pdf.py` (MMi) and `run_smm_iron_ore_daily.py` (SMM) both write **five** `data/extracted/series/hellenic_iron_ore_pdf_*.csv`: dashboard, indices, brands, futures, averages. The MMi runner FULL-OVERWRITES with its own fieldnames; the SMM runner reads the whole file and rewrites it under its own fieldnames (`upsert_rows_to_csv`, :605). Three of the five schemas are incompatible (MMi uses `price`/`market`, SMM uses `value`/`market_type`), so the SMM upsert's DictWriter DROPS the foreign keys and writes empty cells.

**Realized damage (measured):** `..._indices_series.csv` 11,625 rows, **11,553 empty `value`** (every MMi-era index row); `..._futures_series.csv` 2,233 rows, **2,207 empty `price`**; brands 0 empty (names align); averages 172 empty `m_minus_1`; dashboard 1.

**Ground truth (rendered PDF text layer, not another extractor):** `corpus/02-hellenic/iron_ore/pdfs/2021/2021-07-19_..._1841ecdb3610.pdf` p0 prints `IOPI58 58% Fe Fines RMB/t = 1197` (change -11, -0.91%). Delivered CSV row keeps `change=-11.0, pct=-0.9` but `value=''`. The level is absent.

**Three-baseline check - the data is NOT lost:** `hellenic_iron_ore_table_series.csv` (HTML pipeline) holds the same indices with the level intact and byte-matching the PDF (`fot_rmb_wmt=1197.0`). So re-filling `indices_series` would be worth ~zero for the KB. **No consumers:** index.html reads `data/futures|commodities|derived/` only; no script/test/app reads any `hellenic_iron_ore_pdf_*` series. The disk-driven register echoes the damaged SMM state (11,625 rows, SMM columns).

**NOT APPLIED (human design call):** two prior runs deferred this; a wrong schema choice writes wrong values. Options in the verdict: (A) namespace-split the SMM writer (`hellenic_smm_*`, precedent `hellenic_smm_market_drivers_series.csv`) then re-run MMi offline from its 1,190 cached md; (B) unify the MMi writer onto the SMM schema + upsert (`price`->`value`, `market`->`market_type`). No data or code changed this run.

**ALSO FIXED + a new drift hazard:** the cadence-audit md AND its generator (`scripts/audit/generate_cadence_audit.py`) hardcoded stale hellenic counts - corrected to measured (athenian 3,052->2,916; Best Oasis 882/859->887/863), committed as `3da98f693` (code) + `985028792` (doc). **NEW HAZARD:** the 10:51 books commit (`8c7271edc`) added the 'Maritime Reference Literature (12 Books)' section to `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` DIRECTLY, but did NOT add it to the generator - so re-running `generate_cadence_audit.py` DROPS the entire books section (measured: 25 lines removed, restored). Anyone regenerating must re-add it, or the section must be added to the generator.

**STILL OPEN (all human/display calls):** cadence-audit md hardcodes BO 882/859 + athenian 3,052 (measured 887/863, 2,916); hellenic VesselsValue date convention; lion regeneration (re-run changes values = non-determinism, uninvestigated); affinity WS-era md rounding (display only); DB `label_series`.

**THIS RUN (2026-10-04 10:1x-10:4x, source-by-source, 30m job) - HELLENIC DEMOLITION FAMILY: OWNERSHIP RESOLVED, single writer per file, 4 series RESTORED, guard test GREEN. Evidence `docs/hellenic_gms_owner_verdict.md`.**

No extraction job was running (the four `python.exe` are the Hermes gateway). This closes the previous run's OPEN "resolve the GMS owner (A or B)" decision item AND the whole `hellenic_*` demolition two-writer family.

**The decisive evidence the prior runs lacked:** the MAINTAINED cadence audit `scripts/audit/generate_cadence_audit.py` (refreshed 2026-10-03 09:59, i.e. AFTER consolidation) names the owner explicitly - `:892 hellenic_gms_demolition_series.csv` / `:893 1,092 rows` / `:894 script run_gms_demolition.py`; same for port_positions (2,905, run_gms_demolition.py) and the two Best-Oasis files (run_best_oasis_demolition.py). `scripts/orchestrate_pipeline.py:108,110` runs exactly those two as its STAGE-2 EXTRACT steps. The guard test (>=1088, >=900) and its 272-report comment agree. So the union (1,092 / 272 dates) is canonical and the 448-row file was the REGRESSION from the HTML-only `run_hellenic_demolition.py` clobbering the path. **The prior run's edit (removing run_gms_demolition.py's mirror writes) was backwards and is reverted.**

**Fix (single writer per path; re-grep confirms 1 writer each):** restored the mirror writes in `run_gms_demolition.py` (rankings_csv2/port_csv2) and `run_best_oasis_demolition.py` (p_mirror/v_mirror); retired the colliding writes in `run_hellenic_demolition.py` (GMS/port/BO - it keeps athenian) and `run_hellenic_gms_demolition.py` (now writes a `.LP-SIDECAR.csv`). py_compile OK.

**Regenerated + measured:** `run_gms_demolition.py` 247/247 + 26 HTML, 0 fail, 130 s -> 1,092 rows to BOTH gms_demolition_rankings_series.csv and hellenic_gms_demolition_series.csv; 2,905 to both port files. `run_best_oasis_demolition.py` 216/216, 0 fail -> 887 deals / 863 prices to both names. `cmp` = each mirror BYTE-IDENTICAL to its native. Row deltas: gms 448->**1,092**, port 2,931->**2,905**, BO deals 514->**887**, BO demo 233->**863**.

**Guard test: 4 failed -> 12 passed.** Stale thresholds fixed: GMS >=1088/:51 and >=900/:169 pass on 1,092; Athenian >=3000/:30 -> >=2900 (file is 2,916 post-dedup); Athenian md/sidecars ==257 -> >=550 (551/551 measured); Clarksons md glob -> rglob (180 in year subdirs). Register re-synced: `verify_registers.py` **0 mismatches, 170 CSVs / 599,512 rows** (was 597,779).

**Side effect measured:** the GMS runner's own cleanup pruned 26 broken-empty md in md/hellenic/demolition/gms (547 -> 521) - its designed behaviour, runs on every orchestrate_pipeline pass.

**STILL OPEN (all human/display calls):** `hellenic_iron_ore_pdf_dashboard_series.csv` two-writer MEASURED this run - run_hellenic_iron_ore_pdf.py FULL-OVERWRITES with WIDE per-issue `dashboard_indicators` rows (dynamic header) while run_smm_iron_ore_daily.py upserts LONG (date,indicator) rows; disk = SMM long, 138 rows. Incompatible SHAPES -> design call, left untouched; cadence-audit BO counts 882/859 vs measured 887/863 (doc stale, attribution correct); hellenic VesselsValue date convention; lion regeneration; affinity WS-era md rounding; DB `label_series`.

**THIS RUN (2026-10-04 09:3x, source-by-source, 30m job) - TWO-WRITER HAZARD SWEPT: the hellenic demolition family has 4 multi-writer files (GMS one has 3 writers / 3 schemas) and the guard test is RED. Evidence `docs/hellenic_two_writer_verdict.md`.**

No extraction job was running (the four `python.exe` are the Hermes gateway). This continues the previous run's explicit "Hazard to sweep: any series file with two writers". xclusiv is DONE (271 md) - the prompt's "next source" list is stale, do not restart it.

**Sweep of all 170 `series/*.csv` for >=2 writers** (write stmt naming the file, plus the variable-path idiom the Athenian defect hid behind): the live multi-writer set is the **hellenic demolition family**, all with divergent schemas and no dedup in the mirrors:
- `hellenic_gms_demolition_series.csv` - **3 writers**: `run_hellenic_demolition.py` (9-col, HTML-only, 448), `run_gms_demolition.py` (11-col, PDF+HTML, 1092), `run_hellenic_gms_demolition.py` (8-col).
- `hellenic_gms_port_positions_series.csv`, `hellenic_best_oasis_demolition_series.csv`, `hellenic_best_oasis_deals_series.csv` - 2 writers each, mirror schema != canonical schema.

**Measured divergence (last-writer-wins is live):** `hellenic_gms_demolition_series.csv` = 448 rows / 112 dates (2022-04..2026-09, asterisked locations) vs native `gms_demolition_rankings_series.csv` = 1092 rows / 272 dates (2021-07..2026-09, clean). 268 native dates absent from hellenic, 108 hellenic absent from native - largely date-DISJOINT, not the same slice.

**Guard test RED:** `tests/test_hellenic_extraction.py` = **4 failed, 8 passed** (Python312). #1/#2 assert the GMS file >= 1088/900; found 448. #3 asserts exactly 257 athenian md; found 551, but all 551 are **distinct content** (stale exact-count). #4 asserts flat `md/clarksons/*.md >= 170`; found 0 flat (180 exist in year subdirs - stale flat glob). **3 of 4 are stale test assumptions; #1/#2 are the real signal.**

**Root cause (git):** the test thresholds were authored 2026-09-29 23:36 (`19d434b50`) for the **272-report** population it names (246 PDF + 26 HTML); the native file reproduces it exactly. `run_hellenic_demolition.py` was created **after** (`be2f5818d` 09-30, dedup `0f71c1366`/`3db3e145f` 10-01) and derives GMS from `glob("**/*.html")` only -> 448, which last-clobbered the file. The register row (448 "Verified") is auto-synced from disk, so it echoes the regression, not an independent check.

**DECISION ITEM - data left untouched on purpose** (wrong value worse than missing; owner is a human call). Options: (A) make `run_hellenic_demolition.py` the sole owner AND parse PDFs too (restore ~1088, matches the test); (B) drop the GMS write from it, keep `run_gms_demolition.py` as owner, update the test to the 11-col schema; (C) update the test only. Not recommended to guess. Also fix the 2 stale md asserts (glob -> rglob; exact 257 -> >=550).

**Other sweep hits judged benign (measured):** `orchestrate_incremental_ingest.py` writes affinity/carriers/advanced_shipping series via a plus-dedup `upsert_rows_to_csv` and is the LIVE incremental path (CI `broker_reports_weekly.yml`); `extract_week39_supplements.py` is a one-off (only an audit references it); `strict_broker_audit.py`/`run_carriers.py` hits are prose/`print`, not writes.

**NEXT-RUN TARGET:** resolve the GMS owner (option A or B) and take the hellenic demolition family to a single writer per file, then fix the two stale md asserts. Reproduce the sweep with `python3 scratch/twowriter_sweep/sweep2.py`. Still open from earlier runs: hellenic VesselsValue date convention (human call), lion regeneration (human call), affinity WS-era md rounding (display only), DB `label_series` table (older pipeline).

**THIS RUN (2026-10-04 09:1x-09:3x, supervisor hourly) - MIRROR-WRITER SWEEP: the unswept Athenian-class hazard is CLOSED for 4 series + a stale register FIXED. Evidence `docs/mirror_writer_verify_verdict.md`.**

No extraction job was running; the machine had been idle since 2026-10-03 23:20 (nothing in the delegation logs after that).

**Register was STALE by the last in-flight change.** `verify_registers.py` showed the files the 2026-10-03 VV dedup rewrote mismatching the register: `hellenic_vv_matrix_series.csv` disk=12350 vs json=12340 and `hellenic_vv_benchmark_sales_series.csv` disk=124 vs json=141 (the dedup landed the data but the register was never re-synced). Re-ran `scripts/sync_extraction_register.py` (authoritative, disk-driven) -> `verify_registers.py` now **0 mismatches**, 170 CSVs / 597,779 rows, all checks pass.

**The Athenian last-writer-wins hazard was NOT swept - now swept and fixed (source-only, uncommitted).** `hellenic_*` demolition series are owned by `run_hellenic_demolition.py` (register counts + the 10-03 Athenian precedent confirm it), yet per-publisher runners still mirrored into the same paths with different schemas/counts: `run_gms_demolition.py` wrote the 10-col `hellenic_gms_port_positions_series.csv` (would clobber the live 7-col 2,931) and the 11-col `hellenic_gms_demolition_series.csv` (would clobber 448); `run_best_oasis_demolition.py` wrote `hellenic_best_oasis_deals_series.csv` (887 vs live 514) and `hellenic_best_oasis_demolition_series.csv` (863 vs live 233). Removed those mirror writes (own-file writes intact; `py_compile` OK; md5 of all five live hellenic_ CSVs byte-identical before/after - no data touched).

**NEXT-RUN TARGET (measured this run): `hellenic_gms_demolition_series.csv` (448 rows) still has TWO writers** - `run_hellenic_demolition.py:575` and the dedicated `run_hellenic_gms_demolition.py:319` (mtm 2026-09-30). Both are hellenic runners so the canonical owner is not self-evident - determine which produces the registered 448-row output, retire the other's write, re-verify. Also flagged, NOT fixed: `hellenic_iron_ore_pdf_dashboard_series.csv` is written by `run_hellenic_iron_ore_pdf.py` (full overwrite) AND `run_smm_iron_ore_daily.py` (upsert by key) - overwrite-vs-merge semantics, different publisher, needs an ownership decision. Still open from earlier runs (all human/display calls): hellenic VesselsValue date convention, lion series regeneration, affinity WS-era md rounding (144 cells, display only), DB `label_series` (older pipeline).

**THIS RUN (2026-10-03 22:0x-22:5x, source-by-source, 30m job) - ATHENIAN: residual CLOSED + a cross-runner shared-output regression FOUND and FIXED. Evidence `docs/athenian_verify_verdict.md`.**

The carried-forward residual "Athenian demolition regeneration" is **CLOSED**: the runner's last commit (2026-09-30) postdates the delivered CSVs (09-29), but a fresh run of `run_athenian_demolition.py` is a **byte no-op** - 257/257 docs, 0 failed, 21.8s; all four native CSVs identical (3,052 / 4,026 / 240 / 6 rows) and the 551 md + 551 sidecars **0 changed of 551**. No regeneration was due. Only 2 of 257 unique docs are raster and both are already cached -> no API spend.

**REAL DEFECT found+fixed:** `data/extracted/series/hellenic_athenian_demolition_series.csv` had **TWO writers**. `run_athenian_demolition.py`'s "legacy test mirror" block rewrote it **with no dedup**; running it overwrote the canonical **2,916-row** deduped series (register row = 2,916) with a **3,052-row** (+136 duplicate rows) variant. **Restored** by replicating the canonical dedup (imported `extract_athenian`/`publisher_branch`, same sorted-HTML order, same filename+content key): **2,916 rows / 242 issue dates / 0 dup rows / 243 source files** - matches the documented deduped state exactly. **Fixed at source** by deleting the mirror-write block; that file is owned by `run_hellenic_demolition.py` (only consumers: the 2 runners + a cadence audit reader; no app/HTML). **Control after fix:** re-ran -> exit 0, all five files byte-identical before/after, mirror stays 2,916.

**Content verification (no vision tool; text-layer substitution):** 2,916/2,916 = **100.00%** of price cells appear in their own source PDF's page-0 text; 0 mapped-source gaps.

**Other residuals are STALE - do NOT re-chase (measured this run):** star_asia_deals `arrival_date` is already ISO (**2,700 ISO / 649 blank / 0 European** - closed 09-28, the carried-forward "2,680 DD.MM.YYYY" is pre-fix); intermodal_macro 4.3 and the ism agreement tail were both **closed 09-28/09-30 as publisher-side by design** (see lines further down). Still genuinely open: hellenic VesselsValue date convention (human call), lion regeneration (human call, re-run changes values), affinity WS-era md rounding (display only), and the DB `label_series` table (older pipeline). **Hazard to sweep:** any series file with two writers (last-writer-wins) - this one is now single-writer.

**THIS RUN (2026-10-03 18:5x-19:2x, 30m job) - SERIES LAYER REFRESH: independently reproduced and COMMITTED; a PARALLEL-RUN COLLISION was caught. Evidence `docs/series_layer_refresh_verdict.md`.**

The target was ALSO worked by a SIBLING job concurrently (`scratch/series_refresh_20261003/`, 18:51-19:08, which patched `build_series_sql.py` at 18:53); both runs reached the BYTE-SAME result (series 5,241 / series_points 1,167,616 / series_daily 942,263; gate orphans=0 / mismatched=0). No corruption: the producer is deterministic and reads the unchanged `cells` (6,726,703 before and after), so writing the live DB twice is idempotent. The collision was on SHARED outputs - same script, same verdict filename, same live DB, same state file - exactly the parallel-agent hazard. No sibling process is alive now (only the 2 gateways + 2 litellm proxies).

**Independent controls this run:** the series id delimiter changed `|` -> ``, so a raw id join is 0 by construction - joined on the COMPONENT key instead: 5,239/5,241 match. 172,075 matched observations are exactly `new == old*1000` (the 1000x cell fix propagating), 0 the other way except trivial 0.0. **Ground truth without vision:** in `advanced_shipping_2022_W06` p3 the word `Kamsarmax` (x=25.0,y=284.1) shares its row with `81.666` (x=142.7,y=284.1) directly under the `Dwt` header (x=145.7); EU convention -> 81,666 t. The fetched family is now physically plausible where it was absurd: KAMSARMAX DWT 79,200..85,688, SUPRAMAX 50,029..59,963, VLCC 159,233..441,585.

**Sibling's next-target CLOSED by measurement:** nothing to export for the app - no `.html`/`.js` reads `series`/`series_points`/`series_daily`/`corpus.duckdb`, and no test/CI does either; `data/extracted/series_manifest.json` was regenerated to 5,241 entries (sibling, 19:06). **Committed this run:** code `97eb57647`. Residual: the DB's `label_series` table is from an older pipeline and was not refreshed. Still open from earlier runs: hellenic VesselsValue date convention (229 dup rows), lion series regeneration, Athenian demolition regeneration, affinity WS-era md rounding (144 cells, DISPLAY ONLY), intermodal_macro 4.3 (1,290 rows), ism agreement tail (1,178 rows), star_asia_deals `arrival_date` DD.MM.YYYY (2,680/2,727).

**THIS RUN (2026-10-03 18:4x-19:0x) - SERIES LAYER REFRESHED FROM THE REBUILT CELLS: the producer's gate now PASSES (orphans 267 -> 0). Evidence `docs/series_layer_refresh_verdict.md`.**

No extraction job was running. The 18:0x state's NEXT-RUN TARGET (refresh `series`/`series_points`/`series_daily` from the rebuilt cells, after settling ONE producer) was worked end to end.

**Blocker root-caused:** the intended producer `scripts/extract/build_series_sql.py` (its schema is the one every consumer reads) failed its gate with **orphans=267 / 162 series_ids**. Cause = the series id is a delimited string and the entity/header TEXT contains the delimiter (fearnleys `weekly report | fearnpulse`), so the old `split_part` key recovery mis-read them and the representative-spelling join silently DROPPED them (collision count under `|` was 0 -> a drop, not a merge).

**Fix:** keep the component columns beside the id and GROUP BY them (no key re-parsed from the string); id delimiter is now the unit separator `\x1f` (0/6,726,703 cells contain it); `pts_full` is a session TEMP table so the DB does not bloat; the `duplicate(series,date)` counter relabelled BY DESIGN (raw observations are kept; `series_daily` is the deduped view) - it was never the failing condition.

**Result (live `data/extracted/corpus/db/corpus.duckdb`):** series 5,280 -> **5,241**; series_points 1,212,902 -> **1,167,616**; series_daily 941,115 -> **942,263**; cells 6,726,703 (untouched). Gate **orphans=0 / mismatched=0 / integrity OK** (was exit 2); `check_measured_rules.py` = all 11 rules. Producer 218 s, offline, no API spend.

**Why the deltas are correct (measured):** the old series snapshot was built from the PRE-dedup cells; the live `cells` are the post-dedup set and are byte-identical before/after (wheat text cells 4,164 == 4,164), so this is a pure re-derivation from unchanged cells. In a 150-series random sample, **136/150 have an EXACTLY equal value set** (differ only by removed duplicate rows); the 14 that differ hold 430 new points tracking the documented parser correction (e.g. `total|b2` {16,170,500} -> {356180,2030600,3133200}; `post panamax|b1` {1.0,3.0,15.0} -> {95720,95695,93237} $/day). Net -39 series = +2 recovered orphans (capesize/kamsarmax fearnpulse) - 41 whose (entity,measurement) key no longer resolves under dedup (0.8%, noisy date-header series). `series_manifest.json` regenerated to 5,241 entries (was 2026-09-22). Backup: `scratch/series_refresh_20261003/corpus.pre_series_refresh.duckdb`. Producer patch + verdict written but **NOT committed** (hard rule).

**NEXT-RUN TARGET (measured this run): export the refreshed series layer to parquet for the app / confirm no consumer regressed.** The layer is now correct in duckdb but the app is fed by JSON/CSV; check whether any dashboard tab is meant to read these series and, if so, add the exporter. Still open from earlier runs: hellenic VesselsValue date convention (229 dup rows), lion series regeneration, Athenian demolition regeneration, affinity WS-era md rounding (144 cells, DISPLAY ONLY), intermodal_macro 4.3 (1,290 rows), ism agreement tail (1,178 rows), star_asia_deals `arrival_date` DD.MM.YYYY (2,680/2,727).

**THIS RUN (2026-10-03 18:0x-18:4x, source-by-source, 30m job) - DERIVED TABLE DB REBUILT: 40,598 cells were 1000x wrong, now fixed; 0 content lost. Evidence `docs/table_db_rebuild_verdict.md`.**

No extraction job was running (the two `python.exe` are the Hermes gateway). The state's NEXT-RUN TARGET (rebuild the derived table DB) was worked, but its PREMISE was a heuristic misfire, corrected by measurement: a full walk of `data/extracted/corpus` found **0 of 16,803 `tables.jsonl` newer than the 2026-09-23 DB build**, so the DB excludes **no** freshly-extracted corpus docs. The recent agora/xclusiv/intermodal/clarksons/signal work is the **md tier** (`.tables.json`) and series CSVs, which this builder does not read; signal's/breakwave's `tables.jsonl` are empty (HTML sources). Nothing to ADD.

**What the rebuild actually did** (`build_table_db.py --rebuild --out data/extracted/corpus`, ~25 min, offline): docs 8,144 (same); tables 192,535 -> **189,481**; cells 6,946,400 -> **6,726,703**; is_numeric 2,757,974 -> 2,648,633. `check_measured_rules.py` = all 11 rules present.

**Control 1 (no loss):** the 243,247 cells absent from the rebuilt DB were checked one by one - **243,247/243,247 have an identical `(doc,page,engine,row_idx,col_idx,value)` twin still present; 0 without a twin.** That is the `table_content_sig` dedup added 2026-09-28 (camelot returns the same region twice on a page); dropped tables are real duplicates (banchero weeklies hold 4 identical `COMMODITY PRICES/BUNKERS` tables on one page).

**Control 2 (parser fixes real):** join on value+position, 7,252,807 matched cells -> **40,598 cells had a num_value off by exactly 1000x** (0 non-1000x changes): shipbrokers 40,586 / hellenic 12. `3.370` 3.37 -> **3370.0** (BDI), `52.315` -> 52315.0 ($/day T/C). Plus **1,768 cells became numeric**, incl. **429/429 multi-period** (`153.800.000` -> 153,800,000; was 0/429 numeric) and `$ -space` currency. The delivered DB was reading 40,598 broker cells 1000x too small - exactly the silent 1000x class.

**NOT shipped on purpose:** the DB's derived series layer (`series` 5,280 / `series_points` 1,212,902 / `series_daily` 941,115 / `doc_dates` 5,216) is a snapshot from the OLD cells and was **restored**, not replaced. Reason measured: `build_series_sql.py --write` produces 143,783 series and **fails its own integrity gate** (`orphans=267`, `duplicate(series,date)=172,339`), and `build_series.py --write` writes a different schema (no `series_daily`) so it cannot refresh the layer alone. DB parquet/duckdb are git-ignored; backup + diff/control scripts in `scratch/db_rebuild_20261003/`.

**NEXT-RUN TARGET (measured this run): refresh the derived series layer from the rebuilt cells.** Settle ONE producer and make it pass its integrity gate first: reconcile `build_series.py` (schema `entity/header`, no series_daily) vs `build_series_sql.py` (schema `entity/measurement/block_no`, fails at orphans=267 / dup(series,date)=172,339). Until then the rebuilt `cells` are correct but `series`/`series_points` still reflect the pre-fix (1000x) parsing. Still open from earlier runs: hellenic VesselsValue date convention (229 dup rows), lion series regeneration, Athenian demolition regeneration, affinity WS-era md rounding (144 cells, DISPLAY ONLY, `docs/affinity_verify_verdict.md`), intermodal_macro 4.3 (1,290 rows, verify before fixing), ism agreement tail (1,178 rows), star_asia_deals `arrival_date` European DD.MM.YYYY (2,680/2,727).

**NEXT-RUN TARGET (measured 2026-10-03 16:5x): rebuild the derived table DB so it includes everything extracted since 2026-09-28.** Run `python3 scripts/extract/build_table_db.py --out data/extracted` then `python3 scripts/extract/check_measured_rules.py`. Both scripts exist (scripts/extract/, offline, no API spend). Rationale: the ledger's own recurring tell - a downstream DB layer that still excludes freshly extracted documents reads as `cells=0` and is exactly the "verify the artefact, not the intent" trap. Measure cells/tables before vs after and confirm the recent signal/agora/clarksons/intermodal/xclusiv additions become visible. Still open after that (each measured, not fixed): the hellenic VesselsValue date convention (229 dup rows), the lion series regeneration, the Athenian demolition regeneration, affinity's WS-era md rounding (144 cells - DISPLAY ONLY, decision item, `docs/affinity_verify_verdict.md`).

**THIS RUN (2026-10-03 16:3x-16:5x, source-by-source, 30m job) - SIGNAL VESSEL COUNTS: RECOVERED FROM PROSE, 0 -> 106 rows. Evidence `docs/signal_vessel_counts_verdict.md`, runner `scripts/extract/publishers/run_signal_vessel_counts.py`.**

No extraction job was running (both `python.exe` are the Hermes gateway). The state's NEXT-RUN TARGET (`signal_vessel_counts_series.csv` header-only) was REAL (67 bytes, 0 rows, mtime 10-02 22:39) but its PREMISE was a heuristic misfire - the same class as the affinity premise the prior run killed.

**The premise corrected by measurement:** the strings `Ballasters`/`Vessel Class`/`Number of Vessels` ARE in `corpus/07-signal/html/`, but a structural scan found **ZERO `<th>/<td>` cells** containing any of them (0 Ballaster, 0 Vessel Class); only **4 of 446** signal documents produced any HTML table at all, and those 4 are platform/marketing comparison tables. Signal's vessel counts are published as **PROSE** in the weekly market monitors, so `run_signal.py`'s `row_dict.get('Vessel Class'/'Ballasters'/'Number of Vessels')` could never match - the empty CSV was correct by construction and the code path was simply DEAD (not a key/shape mismatch).

**What is recoverable (measured over all 256 monitors):** 2023-2025 (and most of 2026) are QUALITATIVE only ("elevated levels", "surpassing 240 vessels", "record high") - not parsed. **2026 weeks 32/35/36/37/38 (5 docs)** use a structured template giving a per-class global ballaster count + a regional breakdown: **20 global counts**, all reconciled against the source **HTML** (20/20).

**The self-validating control:** in a full-breakdown block the stated regional counts sum EXACTLY to the stated global (2026-09-22 Capesize 236+154+125+47+27=**589**=global; Panamax=803; Supramax=757; Handysize=724). Used as a completeness flag (12/20 blocks complete, 8 are "vs the previous week" summaries) AND as a bug-catcher - it caught the W38 Panamax phrasing where the count comes BEFORE the region ("**212 in** the Indian Ocean/South Africa") vs after everywhere else; a number-after rule shifted every Panamax region by one (sum 707 != 803). Fix = content-anchored A/B rule, skipping any number followed by `%` (WoW deltas).

**Deliverables:** new bespoke per-source runner (prose-anchored, region + `regions_complete` columns); CSV 0 -> **106 rows** (20 global / 86 regional, 0 dup keys); `run_signal.py`'s dead table-key block replaced by a DELEGATION to the module so a future signal run cannot clobber it. Schema gained `region`/`regions_complete` (only consumer is `sync_extraction_register.py`, rows-only; `index.html` does not read it). Register synced: 170 CSVs / 594,207 rows; `verify_registers.py` = **0 mismatches**; register shows signal_vessel_counts = 106. Commits `778ea3480` (code) + `029e38f4e` (docs/register).

**Residuals (measured, not fixed):** the series is FORWARD-ONLY (no numeric per-class counts before 2026 W32); 8 partial regional sets flagged `regions_complete=False`; early-2026 global "fleet" totals (W27/30/31) are a different (all-class) metric left out rather than conflated. No vision tool this session - ground truth substituted with same-document reconciliation against the source HTML, stated not assumed.


**NEXT-RUN TARGET (measured 2026-10-03 16:xx): `signal_vessel_counts_series.csv` is HEADER-ONLY (67 bytes, 0 data rows; mtime 2026-10-02 22:39) while the source holds the headers it keys on.** `run_signal.py` reads `row_dict.get('Vessel Class')` / `.get('Ballasters')` / `.get('Number of Vessels')` / `.get('Count')`; over `corpus/07-signal/html/` the literal strings "Ballasters" (728), "Vessel Class" (35) and "Number of Vessels" (2) are present. So the 0 rows is a runner-vs-source key/shape mismatch (same shape as the just-fixed star_asia S&P bug: wrong header key + positional-vs-dict row access), NOT an absent source. Next step: run run_signal's HTML table parser on one ballistic-counts page, dump the actual table header keys and row shape, fix the key, and verify the recovered counts against the page text. Also still open from earlier runs: the hellenic VesselsValue date convention (229 dup rows), the lion series regeneration, the Athenian demolition regeneration, the Clarksons Desk Talk 608 -> 355 regeneration (delivered 355 - verify), and the derived DB rebuild (`python3 scripts/extract/build_table_db.py --out data/extracted` then `check_measured_rules.py`). affinity's WS-era md rounding (144 cells, `docs/affinity_verify_verdict.md`) is a display-only decision item.

**THIS RUN (2026-10-03 15:5x-16:xx, source-by-source, 30m job) - AFFINITY VERIFIED: series CSVs byte-reproducible, a 762-file flat+year mirror removed, one md defect measured. Evidence `docs/affinity_verify_verdict.md`.**

The previous run's NEXT-RUN TARGET (the stale-data-vs-committed-runner sweep) flagged affinity for a runner committed 2026-10-02 15:22 vs CSV 2026-10-01 23:12. **That premise was a heuristic misfire**: the 15:22 commit (`c25fb48ba`) is on `run_affinity.py`, the MD producer, NOT a CSV writer. `polish_affinity_markdown.py` (the CSV writer) was committed 23:14, after its 23:12 data write. The CSVs were never stale.

**REAL FINDING - flat+year mirror re-created (762 stray files).** `data/extracted/md/affinity/` held **254 flat md + 247 year md** (501 md, 254+247 sidecars, 254+247 charts), all 247 shared stems with DIFFERENT content (flat = `run_affinity.py` raw form, no frontmatter; year = `polish` frontmatter form). Every sibling source is year-only (advanced_shipping 0/253, star_asia 0/198, ssy 0/530, xclusiv 0/271, fearnleys 0/260). The flat tier appeared **2026-10-02 22:46**, AFTER the 10-01 dedup verdict that recorded affinity as year-only. Both writers `rglob("*.tables.json")` and dedup only by byte-identical stem, so the 501 sidecars would **double-count** the next run. **Quarantined the 762 flat files** to `scratch/affinity_audit/quarantine_flat/` (moved, reversible); tier restored to **247 md + 247 tables.json + 247 charts.json, year-only, 0 flat**.

**Re-ran both writers under control (offline, no spend):** `run_affinity_tables.py` (247 stamped, tce 4020, bda 741) + `polish_affinity_markdown.py` (247 md, 4020/741/494). **CONTROL: md5 of all 170 series CSVs pre vs post = 0 changed** - the three affinity CSVs are byte-reproducible. md tier: 247 md changed, **0 sidecars/charts changed**; `polish` deterministic (2 passes byte-identical). The delivered year md (misleading 10-02 00:52 mtime = a copy/check stamp) predated current `polish` output for 247/247 files; brought current. Pre-content not snapshotted (only md5) - stated.

**Content control (no vision tool; same-document PDF text reconciliation):** 2024 and 2026 docs, panel values 41 and 49, **0 unaccounted**.

**md defect measured, NOT fixed (pre-existing `polish` rendering):** in the WS-header era (all 26 of 2021 + 42 of 2022) the md rounds WS quotes to integers with a `$` prefix (WS 130.63 -> `$131`). md rate cells vs CSV: **checked 4,014, exact 3,870, mismatch 144 = exactly the WS era (2021:36, 2022:108)**; 0 mismatches 2023-2026. The CSV is exact; only the md display is lossy. Decision item.

**Housekeeping:** `scripts/verify/verify_affinity.py` repointed to `rglob` + current counts (250->254 PDFs/247 unique, hardcoded 750 BDA -> sidecar record count) - now **6/6 PASS**. `verify_registers.py` = **0 mismatches, 170 CSVs / 594,101 rows**; affinity series rows correct. Section-1 prose row (line 23) still 3,982/735/490 - stale prose, not read by the verifier.

**NEXT-RUN TARGET (measured this run): the "stale data vs committed runner" sweep.** For each broker, compared the last commit touching `scripts/extract/publishers/*<pub>*.py` against the newest `series/<pub>*.csv` mtime. Two candidates where the runner was committed >6h AFTER the delivered data (the xclusiv class - a committed fix not yet in the data): **affinity (runner 2026-10-02 15:22 vs newest CSV 2026-10-01 23:12, 16.2h)** and breakwave (18.1h; may be non-PDF). **Do affinity next**: re-run `run_affinity_tables.py` + `polish_affinity_markdown.py` (both writers - see the affinity dedup verdict), control md5s of all 170 CSVs (expect only affinity_* to move), reconcile per-doc, and check its runner's write path does NOT include corpus. All other sources are ok (gap <=0.5h or negative).

**THIS RUN (2026-10-03 15:2x-15:4x, source-by-source, 30m job) - XCLUSIV VERIFIED: the delivered series are byte-reproducible, and the md tier was brought current with a committed fix it had MISSED. Evidence `docs/xclusiv_verify_verdict.md`.**

The prompt's "xclusiv IN PROGRESS" is STALE (271 md on disk, 10 series, register CLOSED); no extraction job was running (the two `python.exe` are the Hermes gateway). So this run did the prompt's item 2/3 - VERIFY xclusiv - with a full re-run.

**Ran** `python3 scripts/extract/publishers/run_xclusiv_tables.py --all` (offline PyMuPDF, no credits): `[dedup] skipped 7 byte-identical duplicate document(s)`, **264/264 ok, 0 failed, 455.2 s**. Summary: sales 5702 / demolition prices 2082 / secondhand 8529 / demo_sales 603.

**CONTROL - numeric layer byte-identical:** all ten `xclusiv_*.csv` `md5sum -c` = OK (only 4 are written by this runner; all 4 reproduced byte-identically). Register unchanged, **170 CSVs / 594,101 rows, verify_registers.py = 0 mismatches**. Sidecar-vs-CSV reconciliation over 271 year sidecars: the ONLY docs absent from the CSVs are the **7 byte-duplicate stems** = the dedup working as designed; **no stacking gap**.

**REAL FINDING - the delivered md predated a committed fix, so the md tier was STALE.** `run_xclusiv_tables.py` was committed **2026-10-02 16:15** (`a0d2d21bc`, "clean xclusiv freight commentary"); the delivered md was written 10-01 20:35. The re-run regenerated it: **263 of 271 md changed, and 0 of 271 differ outside the Dry Bulk/Tanker Freight sections** (control = stashed pre-fix copies in `data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv/`, freight sections stripped from both). Freight-section delta: **removed 4,433 old lines (1,317 chart furniture) -> added 229 real commentary lines across 136 files**. The old predicate (`b[0] < w*0.55`) pulled chart titles/legends/axis ticks; the new (`x < 60`) takes the left-margin commentary. Content verify vs the PDF text layer: 2024-03-19 Dry Bulk 5 blocks / Tanker 4 blocks match the page **verbatim**.

**SIDE EFFECT CONTROLLED:** the runner's backward-compat branch re-created **264 flat md + 264 flat tables.json** root duplicates (previously stashed, 809 files - the flat+year mirror hazard). **Removed again**; tier restored to **271 md + 271 tables.json, year-partitioned only, 0 flat**.

**RESIDUAL (not fixed):** the register's `publishers.xclusiv` block is stale prose (sales 5713 / secondhand 8593 / demo 618 / nb_price 1397 / 21135 vs delivered 5702 / 8529 / 603 / 1379 / 20975); `verify_registers.py` checks `series_inventory`+totals (0 mismatches), not this block. No vision tool this session - substituted the PDF text layer and same-document pre/post controls, stated.

**THIS RUN (2026-10-03 14:2x, source-by-source, 30m job) - CLARKSONS DESK TALK: the sales table fused into `commentary_text` is FIXED (355 -> 352 rows). Evidence `docs/clarksons_desk_talk_fusion_verdict.md`.**

No extraction job was running (both `python.exe` are the Hermes gateway). The prompt's "xclusiv IN PROGRESS / start the next source" is STALE - xclusiv and every broker source are CLOSED in the register. The register the last run owed is already synced and verified clean. So this run closed the residual the 13:3x supervisor explicitly left open.

**Defect (content-anchored, not the loose predicate):** the 3 bulletins with `pipes=0` in their md - `2021-07-02` W27, `2021-07-09` W28, `2021-07-23` W30 (checked: exactly 3 of 165 cache files carry no `|`) - render the S&P table as column-flattened bare cells. No pipe -> the commentary guards never fired, so the table cells were appended to the commentary block. Delivered CSV held **6** such rows (a pure-cell `Desk Talk` row + a cell+prose `Tankers` row per doc, longest 4,180 chars). The supervisor's "17" used a looser vessel-token predicate and included FALSE POSITIVES: the 2026 rows name builders as real commentary (SAMSUNG HI / HYUNDAI MIPO / DAEWOO) - correct, untouched.

**Fix:** `flattened_table_cell_indices(lines)` in `run_clarksons_hellas_world_class.py` delimits the flattened block by CONTENT (VESSEL header -> BUYER, then body until the first page break / furniture / prose line), and the commentary loop skips those indices. Called ONLY when `"|" not in markdown_text`.

**Controls:** row-level set diff over all 165 docs = **removed 6, added 3, all inside the 3 docs**; other 349 rows byte-identical. Every new commentary text is an exact **suffix** of the old - **0 prose lost**. md5 of all **170** series CSVs: only desk_talk changed, other 169 byte-identical. dup keys 0, blank 0. Register re-synced **594,104 -> 594,101** / 170 CSVs, `verify_registers.py` = 0 mismatches.

**Residual (not fixed):** these 3 docs keep the publisher's own section label (the 2021-07-02/09 `Tankers` row now holds newbuilding prose); no relabel - wrong is worse than missing.

**ALSO THIS RUN - the breakwave duplicate-residue side finding is CLOSED, independently re-measured:** `corpus/02-hellenic/shipbuilding/pdfs` holds 353 breakwave-named PDFs spanning **182 distinct filename dates**. Against THREE baselines (corpus/03-breakwave file dates 291, `breakwave_fundamentals_series.csv`, `breakwave_insights_metadata.csv`) exactly 3 filename-dates looked uncovered: `2021-07-07`, `2021-09-01`, `2024-01-02`. They are **download dates, not report dates** - the files are `BreakwaveJuly62021Report`, `BreakwaveAugust312021Report`, `BreakwaveDryJanuary92024Report`; the true report dates `2021-07-06` / `2021-08-31` / `2024-01-09` are ALL present in `breakwave_fundamentals_series` and in 03-breakwave. **No gap; duplicate residue only.** (Filenames lie about dates - same lesson as the agora cover-date fix.)

**THIS RUN (2026-10-03 13:3x-13:5x, HOURLY SUPERVISOR 345bc8db9233) - HUMAN DECISION #1 TAKEN: the Clarksons Desk Talk furniture fix is now IN the delivered file (608 -> 355 rows); controls exact; one residual class measured. Evidence `docs/clarksons_desk_talk_regen_verdict.md`.**

**Why this item:** no extraction process was running; the live sibling is the 30m source-by-source job (up since 13:28:44, actively rewriting `agora_indicators_series.csv` at 13:39:18 / 13:43:01), so agora + intermodal are its thread. The parked item with a measured expectation and no owner was the committed fix `abee30d58` whose DATA regeneration was deferred as a human decision.

**Ran:** `python3 scripts/extract/publishers/run_clarksons_hellas_world_class.py` - cache-only, NO API spend, 15.0 s, 165/165 reports, 0 failures. `clarksons_desk_talk_series.csv` **608 -> 355 rows**, duplicate keys **17 -> 0**, rows matching the furniture predicate **273 -> 0**, 0 bare-date rows, 165 source files, md5 `8f76077a...` -> `ee3256c2...`. sales 1,329 / demolition 70 / macro 165 unchanged, each 0 dup keys. sectors: Demolition 130, Newbuilding 128, Tankers 39, Dry Bulk 33, General 22, Desk Talk 3.

**Controls:** (1) md5 of all 170 series CSVs pre/post my run -> only `clarksons_desk_talk` changed from my writes; the agora diff belongs to the live sibling (mtime 13:39:18 > my 13:38:55, and the clarksons runner has no agora write path). (2) old-vs-new in memory over the same 165 cached reports: sales 0 diffs, demolitions 0 diffs, macro 0 diffs; of the 80 commentary rows the new code adds, **68 are verbatim substrings of old rows** (re-segmentation) and 12 are genuine commentary the old code never emitted. (3) md tier: 690 sidecar files, 0 added / 0 removed, and regenerated md differs from old md in **0 table rows** - the diff is commentary-only.

**RESIDUAL FOUND (new, measured, NOT fixed):** 17 of the 355 delivered rows still carry sales-table text fused into `commentary_text` (avg row 1,037 chars, longest 4,180 - `NISSOS ANTIPAROS 2019 HYUNDAI HEAVY ULSAN WARTSILA WINGD 7X82-B ...`). PRE-EXISTING, a different class from furniture; needs its own page-level diagnosis.

**NOT DONE ON PURPOSE - the register sync.** `data/extracted/EXTRACTION_REGISTER.{json,md}` (12:35) still show clarksons_desk_talk at **608**; expected 608 -> 355, series total 594,263 -> 594,010. It was NOT run because the live sibling was rewriting agora at that moment and two register writers can record a transient count. **NEXT RUN: run `scripts/sync_extraction_register.py` then `scripts/extract/verify_registers.py` (expect 0 mismatches).**

**SIDE FINDING (measured, verdict = NOT a gap):** `corpus/02-hellenic/shipbuilding/pdfs` holds 347 unique PDFs, 182 of them breakwave-named, skipped by the clarksons runner with a WARNING only. 333 of 353 breakwave PDFs there are byte-twins of files already in `corpus/03-breakwave`; the 10 documents that are not (x2 copies each, also in `corpus/02-hellenic/shipbuilding/breakwave_pdfs`) have 7 of 10 dates ALREADY in `breakwave_fundamentals_series.csv`, and the other 3 appear in `breakwave_insights_metadata.csv`. Duplicate residue, not coverage loss. At most a 3-doc page spot-check. The breakwave runners read only `corpus/03-breakwave/{drybulk,tankers}/**`, so no double-ingest is possible.

**SESSION LIMITATION:** no image/vision tool - ground truth substituted with same-document content controls (per-doc old-vs-new parse, the furniture predicate, md table-row diffs), stated not silently assumed.

**THIS RUN (2026-10-03 ~13:3x, source-by-source) - AGORA date-hygiene recovery + W37/W39 recall (+94 rows). Evidence `docs/agora_date_hygiene_verdict.md`.**

Agora's delivered series was **invisible to date joins on 7 issues**: 5 named `agora_<YYYY>_w<NN>.pdf` carried BLANK issue_date AND week (235 rows), the W38 issue carried a BLANK week (47 rows), and **W37/W39 were absent entirely** (94 rows). A content sweep of the 217-PDF corpus against the series found exactly these. Convention derived from the data, not assumed: `issue_date == Friday of ISO week report_week` (**9,626 rows, 0 mismatches**). Weeks read off each DOCUMENT'S COVER, not the filename (agora filenames have lied before).

**Fix:** dated the 5 blank issues from their covers; filled W38=38; normalised `report_week` floats (`36.0`) to ints to match every other series; recovered W37/W39 by re-running the source's OWN extractor (`run_agora.build`) in-schema. **Builder validated byte-exact against the existing W36 + W35 rows (47/47 each) before it was trusted.** Controls: only date/week columns changed (all other columns byte-identical row-for-row); append-only for W37/W39. **9,908 -> 10,002 rows; blank dates 235 -> 0; blank weeks 282 -> 0; dup keys 0.** W39/W38 confirmed byte-identical to their download-named copies (no double-count). Content verified vs page text (W39 Crude `94.61/-8.38/13.26` == page `94,61/-8,38%/13,26%`). Register re-synced (agora 9,908 -> 10,002; total 594,568 -> 594,409, also picks up the parallel clarksons_desk_talk 608 -> 355 fix).

**RESIDUAL:** the stacker that builds `agora_indicators_series.csv` is NOT in `scripts/`; the delivered CSV is patched directly. Stale FLAT `source_file` paths affect every agora row (corpus-wide path item, not touched).

**THIS RUN (2026-10-03 ~12:3x, source-by-source) - INTERMODAL: the owed per-document row-count audit executed across all 16 series; TWO more recall gaps found and FIXED (+50 rows). Evidence `docs/intermodal_nb_recall_verdict.md`.**

**Instrument:** re-ran the current parser over the 255 non-dup cached md and compared PER SERIES PER DOC the parser's **UNIQUE** row count vs the delivered CSV. The first pass used the RAW count and was WRONG: `2026_W12` "32 vs 20" was 12 duplicate rows of a twice-printed tanker block, collapsed to 20 by dedup. **Dedup before believing an API-count gap.**

**Result:** 0 gaps in tanker_spot / indicative / baltic / currencies / sales / demo_prices / demo_sales. The 6 `tc_rates` gap docs are the KNOWN deliberate label-guard skips (2023 W21/24/29/30/31/33) - not reopened. Real gaps: **nb_orders (7 docs, +31)** and **nb_prices (4 docs, +19)**, all 2022-2023.

**Verified real (not a metric):** stale sidecar keys. `intermodal_2022_W03`'s sidecar `newbuilding_orders` held **0**; the PDF **page 6** prints 7 order rows. Grounded every parser row against the source PDF's OWN text layer (independent of LlamaParse): nb_orders **31/31**, nb_prices **71/71**. **Fix:** `scratch/intermodal_audit/refresh_nb.py` rewrote ONLY the correct keys (`newbuilding_orders` x7, `indicative_newbuilding` x4) from a fresh parse, then `run_intermodal_full.py --year all --stack-only`. **nb_orders 1,864 -> 1,895 (+31); nb_prices 3,170 -> 3,189 (+19); union newbuilding 5,034 -> 5,084 (+50); 0 dup keys.**

**CONTROL (byte-level):** md5 of all 170 series CSVs - **only the 3 newbuilding files changed; 167 byte-identical.**

**REGISTER:** `sync_extraction_register.py` -> **170 CSVs / 594,263 logical rows**; `verify_registers.py` = **0 mismatches**. Section-1 Intermodal row hand-updated (5,084 / 3,189 / 1,895; total **62,809 -> 62,909** across 16 series).

**RESIDUALS:** tc_rates 6 label-guard docs stay skipped (deliberate). Do NOT blanket-reparse: several series show the CSV RICHER than a fresh parse (tanker_spot 3,885 vs 3,419; indicative 2,360 vs 1,091) - the md is poorer there. No vision tool - substituted same-document PDF-text reconciliation.

**THIS RUN (2026-10-03 ~11:xx, source-by-source) - intermodal SALES (+131) AND dry-bulk TC RATES (+153) recall gaps RECOVERED (+284 rows), found by the owed per-document row-count audit. Evidence `docs/intermodal_sales_recall_verdict.md`, fix in `scripts/extract/publishers/run_intermodal_full.py`.**

**Method:** re-ran the parser over the cached md and reconciled per document against the delivered CSV (the audit the macro verdict owed). `intermodal_sales_series.csv` 3,348 vs parser 3,387. Verified against the source PDFs, not metrics: 2022 W13 page 3 prints `VLCC EASTERN JUNIPER 305,749 2007 ...` while the CSV carried only its 2 container rows; 2023 W06 page 3 prints NAVE PHOTON / STENA PROGRESS / KONSTANTIN JACOB, 13 of them absent from the CSV.

**Two causes:** (1) the delivered sidecars pre-date the 2026-10-02 md reparse for 16 docs (re-running `process_single_pdf` on W13 now writes 21 sales rows where 2 sat); (2) a REAL parser bug - in one era LlamaParse fuses the section label and inserts `Sector`/`Size` cells before `Name` (`| Sector | Size | Tankers | Name | Dwt | ... |`), shifting every header keyword 2 cols right of its value; the old map trusted the literal index and would publish the NAME as DWT and the BUILT year as NAME.

**Fix:** content-anchored shift (`_hdr_shift = name_idx - 1` only when `hdr0[0]=="sector"`, inert on the other 14 header shapes), then re-parsed the 16 docs and replaced ONLY their sidecar `secondhand_sales` key (finance keys preserved), then restacked. **sales 3,348 -> 3,479 (+131), 0 dup keys.** Control: md5 of all 16 series CSVs - **only sales changed** (restack is idempotent; tc_rates +36 / indicative +70 resolve to byte-identical files via the writer's dedup). Register re-synced: **594,010 logical rows / 170 CSVs, verify_registers.py = 0 mismatches.** Content verify vs PDF text: **301/302 = 99.7%** vessel names, **302/302 = 100%** dwt; the 1 miss is an upstream md typo (CELIUS vs PDF CELSIUS).

**ALSO THIS RUN - tc_rates dry-bulk block recovered.** `intermodal_tc_rates_series.csv` 5,080 -> **5,233 (+153)** across 18 docs; the missing block is the dry-bulk TC table (Capesize/Panamax/Supramax/Handysize x 1yr/3yr), verified printed on the PDFs (2026 W12 page 2 `180K 1yr TC 29,750`; all 8 values of 2023 W21). Applied with a class-LABEL guard: 6 docs (2023 W21/W24/W29/W30/W31/W33) SKIPPED because LlamaParse stamps one class on every dry-bulk row (76K/58K/32K labelled Capesize) - a wrong class is worse than a missing row; 9 regression docs untouched. Control: only tc_rates CSV changed; content verify 2,240/2,240 = 100% dry-bulk rates in the PDF text; 0 dup keys. Register 594,163 rows / 170 CSVs, 0 mismatches.

**RESIDUALS (measured, not fixed):** do NOT blanket-reparse - the 2026-10-02 md is POORER for some series (fresh parse gives tanker_spot 3,449 vs 3,885 delivered, indicative 1,104 vs 2,360), so recovery must stay surgical. Fused single-row sales tables (2021 W31/W34, 2022 W35) still lost. A per-page row-count audit of tc_rates/indicative is still owed.

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

> **CORRECTED 2026-10-05:** the banchero block below is STALE. Banchero Costa md is
> **248/248 DONE** (Oct-3); the credit wall was cleared. No extraction job is live.

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
