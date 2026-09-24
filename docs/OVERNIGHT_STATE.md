# OVERNIGHT STATE - read this FIRST, then resume

**Purpose:** if the machine sleeps, a session dies, or a new context starts with no
memory of this project, this file is the single source of truth. Read it, check the
live state it tells you to check, then continue. Do not restart finished work.

Last updated: 2026-09-24 ~13:30 IST (LlamaParse banchero run IN FLIGHT - do not restart it; lion COMPLETE + verified + committed - all broker sources now built)

---

## READ THIS FIRST

**`docs/MASTER_EXTRACTION_PLAN.md` is the master resumable plan** - source
inventory, proven capabilities, cost routing policy, skip decisions, exact
commands. This file (OVERNIGHT_STATE) covers only what is in flight right now.

---

## ACTIVE JOB RIGHT NOW - do NOT duplicate

**LlamaParse escalation run for banchero_costa is RUNNING.**

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
| ism | 112/112 | `data/extracted/md/ism/` | **charts only, NO tables** (measured). 444 charts, 1,678 series, 84,035 weekly points, 0 failures, ~35 s. 96.8% labelled, 0 mislabelled, 0 unverified axes, 443/444 linear x. `docs/ism_verdict.md` (12 defects found+fixed), `docs/ism_survey.md`. |
| lion | 43/44 (1 skipped) | `data/extracted/md/lion/` + `data/extracted/lion_deals.parquet` + `lion_demometer.parquet` | 1,145 deal rows, 516 demometer rows, runner `scripts/extract/publishers/run_lion.py`. The 44th file is a star-asia reprint (RESTATEMENT, skipped). Verification found and fixed **3 en-bloc pricing defects in 38 of 1,145 rows**; demometer recall 736/736 printed numbers, 0 mismatches. `docs/lion_verdict.md`. |
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
