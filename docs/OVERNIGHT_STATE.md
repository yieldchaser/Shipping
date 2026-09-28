# OVERNIGHT STATE - read this FIRST, then resume

**Purpose:** if the machine sleeps, a session dies, or a new context starts with no
memory of this project, this file is the single source of truth. Read it, check the
live state it tells you to check, then continue. Do not restart finished work.

**NEXT SOURCE - corrected 2026-09-28 14:5x:** `corpus/09-ppa` families A+B are now BUILT
and verified (`docs/ppa_verdict.md`, `docs/ppa_survey.md`, runner
`scripts/extract/publishers/run_ppa.py`). Do NOT redo them. The remaining work on this
source is **family C - the 152 per-vessel "Cargo, GRT and DWT Statistics by Commodity
Group" PDFs (5-10 pages each, borderless, Vessel / Arrival / Departure / Import / Export /
GRT / DWT / Destination-Origin / Cargo)** - a genuinely missing grain (vessel-level port
calls) that needs its own measured pipeline. Then `corpus/02-hellenic` ~2,798 without md.
Earlier lead (still true) - do NOT start `corpus/04-poten`. It was the
suggested "biggest first" target but the three-baseline test shows it is ALREADY fully
extracted (1,087/1,087 md + tables.json, 1,087-row opinions metadata, already in the app,
already `CLOSED` in the register). Measured coverage of every corpus folder is in
`docs/corpus_coverage_gaps.md`. The real gaps, in order: ~~`corpus/09-ppa` 493 PDFs
with ZERO output~~ **DONE 2026-09-28** (families A+B; family C still open - see the top of
this file), then **`corpus/02-hellenic` ~2,798 without md** (run the three-baseline test per
sub-publication FIRST - the register already claims 992 hellenic series, so much of it may
already be ours).

**PPA IS 87.6 PCT ALREADY EXTRACTED - 2026-09-28 14:33 (supervisor 345bc8db9233).** Do NOT build a from-zero
493-document PPA runner. Measured read-only: corpus/09-ppa holds 493 files but only
**339 distinct contents** (154 are byte-duplicates); the DB already holds **297** of them
(**228,280 cells, 1,335 tables**), i.e. **87.6 pct**. Only **42** distinct documents are
missing - the Port of Dampier FY cargo-statistics one-pagers FY2015-16..FY2025-26. The md
tier IS genuinely 0 pct (no data/extracted/md/ppa*). PPA is already DISPLAYED via
`data/commodities/australia_ppa_iron_ore.csv` (423 rows to 2026-08-01). Full evidence:
`docs/PPA_ALREADY_EXTRACTED_FINDING.md`, `data/extracted/supervisor_verify_20260928_1420.json`,
file list `scratch/supervisor_verify/ppa_42_files.json`. Scope the PPA work to 42 docs.

Last updated: 2026-09-28 14:55 IST (ppa families A+B BUILT + verified, 0 failures, 100% arithmetic pass - see docs/ppa_verdict.md) (banchero BLOCKED - LlamaParse credits exhausted, see
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
