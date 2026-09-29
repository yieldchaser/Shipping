# OVERNIGHT STATE - read this FIRST, then resume

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
