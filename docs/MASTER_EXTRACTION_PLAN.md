# MASTER EXTRACTION PLAN - maritime knowledge base

**Read this file first. It is the single source of truth for the PDF extraction
programme, and it is written so that ANY agent can pick it up and continue without
being briefed.**

Last updated: 2026-09-24 19:40 IST
Repo: `C:/Users/Dell/Github/Shipping` — work on branch `benchmark/extraction-comparison`,
**never touch `main`**.

---

## 0. THE STANDING RULE — do not extract what we already hold

**This is the first rule of the programme and it is not a preference. It has been stated
repeatedly and it is now enforced by an executable check, not by memory.**

Before building any extraction or chart pipeline for a source, ask what the data IS:

1. **If the value is already in the feeds, our own extraction, or on a live dashboard
   tab — STOP. Do not extract its charts.** Restating a held value is effort spent for
   zero information, and it is the single largest waste risk in this corpus.
2. **The held set, measured 2026-09-24:**
   - **BDI / BCI / BPI / BSI / BHSI** — `data/extracted/series/intermodal_baltic_tc_series.csv`,
     **19,691 rows, 2,189 points per index, 2020-08 → 2026-08.**
   - **1 / 5 / 7 / 10-year time-charter averages** — same file (AVR 5TC BPI, AVR 7TC BHSI,
     AVR 10TC BSI) plus `corpus/02-hellenic/dry_charter`.
   - **Fearnleys Hasura** — the API already carries what the reports reprint. This is
     exactly why it was skipped, and why the reports' version of it must stay skipped.
3. **A bare vessel-class name is NOT proprietary.** `Capesize`, `Kamsarmax`, `Panamax`,
   `Supramax`, `Handysize`, `Aframax`, `Suezmax`, `VLCC` on a chart are the labels the
   Baltic charts use **for the indices we already hold**. An audit that treated those as
   novel marked the largest held set in the corpus as its top build target — the exact
   mistake this rule exists to prevent.
4. **What IS worth extracting is the proprietary data nobody publishes as an index:**
   newbuilding and newbuilding-series prices, sale-and-purchase prices, demolition and
   scrap values, asset and vessel valuations, steel/plate prices, forward curves on named
   vessels or routes, and any series whose only source is a broker's own chart.
5. **A single index we do not hold is still not worth a pipeline on its own.** BDTI and
   BCTI were measured as genuinely absent from `data/` on 2026-09-24 — and the verdict is
   still **do not build a dedicated extractor for them**, because they are public indices
   and they can be picked up cheaply if ever actually needed, not via a 249-document
   chart pipeline.

### The audit that enforces this

`scripts/tools/audit_chart_legends.py` reads every chart legend **off the rendered PDF
page** (a swatch's colour matched to the word printed beside it) and classifies each
series as HOLD (already held, with the holding file cited) / NOVEL (proprietary) /
UNKNOWN. Run it before building any chart pipeline. It is the check that must be passed
before a source earns extraction effort.

**Measured 2026-09-24 across 8 sources, 1,001 legend swatches:**

| source | swatches | held | **proprietary** |
|---|---|---|---|
| xclusiv | 260 | 21 | **0** |
| intermodal | 159 | 13 | **0** |
| advanced_shipping | 136 | 5 | **0** |
| banchero_costa | 94 | 14 | 1 (Plate) |
| ism | 73 | 3 | **0** |
| fearnleys | 16 | 3 | **0** |
| affinity / agora / star_asia / lion / clarksons | 0 | - | **0** |

**Zero proprietary chart series across the whole broker corpus.** The unknowns are chart
region headings (`Bangladesh`, `India`, `Pakistan`), commodities (`Brent`, `Gold`, `MGO`),
route names (`Azov`, `BlSea`, `Danube/POC`) — not index series. **No broker chart in this
corpus is worth a dedicated extraction pipeline.** The remaining value is in the
PROPRIETARY TABLES (newbuilding prices, S&P, demolition values), which is table work, not
chart work.

Two bugs in that audit are worth keeping, because both would have produced a wrong
priority: the held-key table compared normalised labels against raw keys, so `B.D.I`
silently missed; and the novel-detector matched bare class names, so the held Baltic
indices were reported as the top build target.

---

## 1. THE GOAL (what "done" means for a source)

For every broker source, the knowledge base should hold, for every document:

1. **Text** — faithful prose, complete, nothing dropped.
2. **Tables** — structured table values, correctly labelled (a wrong label is worse
   than a missing one: never assign a label by row order or regex match order, only by
   geometry or exact-vocabulary match).
3. **Chart values** — the plotted series as numbers, **but only where the series is data
   we do not already hold.** See section 0: a chart of BDI/BCI/BPI/BSI/BHSI or of a
   1/5/7/10-year T/C average is a restatement of a held value and must NOT be extracted.
   The measured audit found **zero proprietary chart series** in this broker corpus, so
   chart work here is a small exception, not a pipeline.

A source is **PERFECTED** only when all three are verified **by looking at the rendered
page**, not by counting rows. Files existing is not correctness.

---

## 2. PROVEN CAPABILITIES (evidence-backed — do not re-litigate)

| capability | evidence | cost |
|---|---|---|
| Clean PDFs → text + tables | local pymupdf/liteparse/camelot, 1,727 docs processed | free |
| **Ciphered text layer → real tables** | banchero 2026 W03: **13/13** vs ground truth | 3 cr/page |
| **Vector chart → numeric series** | xclusiv: 5 TCE series recovered, **validated against the page prose** (VLCC 335,000 vs 334,066 stated) | 45 cr/page |
| Detect which pages are broken | local PyMuPDF scan, free | free |

**Chart values are chart-resolution, not dollar-precision.** They recover the SHAPE and
LEVEL of a multi-year series (~2-5% of axis range). Prose gives dollar precision for the
current week. They are complementary and cross-check each other — always cross-check.

---

## 3. COST ROUTING POLICY (the decision framework)

**Default: do NOT use the cloud. Local extraction is free and sufficient for clean PDFs.**

Escalate a page to LlamaParse **only** when a local check proves the text layer is
unreadable — specifically:
* glyph-ciphered table text (punctuation soup where the page renders values), or
* a vector chart whose series we need and cannot geometry-fit.

**Never** send a whole document when a page range will do. Measure first:

```bash
python3 scripts/tools/measure_paid_surface.py <source>   # free, local
```

"A page you skip is a page you don't pay for."

### Tier selection
| tier | cr/page | use |
|---|---|---|
| cost_effective | 3 | **default for ciphered text** — passed 13/13 |
| agentic | 18 | only if cost_effective fails a gate |
| agentic_plus | 45 | **charts only** (`specialized_chart_parsing`) |

`cost_optimizer` **cannot** be enabled below agentic (API returns 422) and is redundant
with page targeting. Caching makes an identical re-run free for 48h, but **any option
change busts the cache**.

### Measured paid surface — CORRECTED, calibrated detector, all 15 sources

`data/derived/paid_surface_by_source.json`. This is the authoritative table.

```
source              docs   pages   flagged   pct
banchero_costa       243    3753      662    17.6%   <- the real cipher
intermodal           252    2002       25     1.2%
affinity             250     334        7     2.1%
star_asia            193    3421       24     0.7%
agora                213    1071        5     0.5%
xclusiv              266    2123        4     0.2%
fearnleys            257    6052        4     0.1%
advanced_shipping    249    2456        0     0.0%
carriers             129     386        0     0.0%
ssy                  519     519        0     0.0%
ism                  112     266        0     0.0%
lion                  44     148        0     0.0%
clarksons             10      35        0     0.0%
bancosta / general    2      21        0     0.0%
------------------------------------------------
TOTAL               3237   28,250      731     2.6%
```

**The cipher is a banchero problem (662 pages), not a corpus-wide one.** Everything
else is clean: 0.0–2.1% at most. The whole corpus paid surface is **731 pages**, of
which 662 (91%) is banchero. Spending is therefore targeted, not blanket.

> **The first detector was BROKEN — these numbers replace it.** It flagged any
> punctuation-dense span with no lowercase, so it fired on ordinary table headers
> (`± (%)`, `± ($)`, `(30K)`) and reported advanced_shipping at 807 pages (32.9%).
> Rendered page 1: perfectly clean (BDI 1.501/1.460, Capesize 18,608).
> `scripts/tools/calibrate_cipher_detector.py` now calibrates before any reading is
> trusted: banchero W03 detected (recall kept), advanced_shipping/agora zero false
> positives. **Correcting it cut banchero 1,074 → 662 pages, saving ~1,236 credits on
> the in-flight run alone.**
>
> **Lesson:** a check that surprises you is a check to verify first. Two separate
> instruments (the cipher detector, the completeness auditor's byte threshold) were
> wrong tonight, and both were caught only by rendering a page and looking.

---

## 4. SOURCE INVENTORY AND STATUS

> **Status corrected 2026-09-24 15:40 against ARTEFACTS on disk, not against this
> document's earlier claims.** Three verdicts below were wrong and are now fixed:
> intermodal HAS a chart layer (two line charts on page 3, every era); ssy is now
> complete; lion and carriers are definitively chart-free, confirmed by rendering.

### Sources CLOSED end-to-end, verified

| source | docs | text | tables | chart values | time series |
|---|---|---|---|---|---|
| **ssy** | 519 | 519 `.md` | inline | **519/519, 65,869 pts, 1,432 series, 0 cr** | **8,881 keys, cross-report agreement 0.26%** |
| advanced_shipping | 249 | yes | 249 | yes | local |
| affinity | 250 | yes | 250 | yes | local |
| agora | 213 | yes | 213 | **none exist** (no chart layer, render-verified) | n/a |
| fearnleys | 257 | yes | 257 | yes | Hasura redundancy — skip by decision |
| ism | 112 | yes | inline in `.md` | 4 charts x 3 series | local |
| star_asia | 193 | yes | 193 | yes | local |
| xclusiv | 266 | yes | 266 | **6/6 years, 13 series, 936 pts, 270 cr** | sampled, see §9 |
| banchero_costa | 243 | 243 via LlamaParse | 243 | FFA on p14, 64 outputs | 13/13 gate |
| carriers | 129 | 129 | 129 | **none exist** (render-verified, pure tables) | 2,866 sales rows |
| intermodal | 252 | 252 | 252 | **2 charts x 9 series, 252/252, 0 cr** | in progress |
| lion | 44 | 43 | parquet | **none exist** (render-verified) | 1,145 + 516 rows |

**ssy is the reference implementation for closing a source.** Its extractor
(`scripts/extract/publishers/run_ssy_charts.py`) is vector-only, 0 credits, and its merge
(`merge_ssy_charts.py`) carries a self-validating agreement check: each weekly report
redraws the same window, so repeated readings of one calendar position must agree, and
they do to a **median 0.26%**. That check is what caught four merge defects a
per-document metric could not see.

### NOT started

| source | docs | why |
|---|---|---|
| clarksons | 10 | render-verified: 2 S&P tables, **no charts** |
| bancosta / general_broker | 2 | singletons |

### Per-source detail
`docs` = PDFs in corpus. `.md` = local extraction present.

| source | docs | local .md | status / next action |
|---|---|---|---|
| advanced_shipping | 249 | 249 | END-TO-END. 0.0% cipher. Known cosmetic defects documented (`prose_merge_verdict.md`). |
| star_asia | 193 | 193 | END-TO-END. 24 flagged pages (0.7%) to triage. |
| ssy | 519 | 519 | PARTIAL: chart values only. 0% cipher. |
| xclusiv | 266 | 266 | END-TO-END (local). 4 flagged pages. **LlamaParse chart series proven on 2 docs — roll out next.** |
| fearnleys | 257 | 257 | SKIP by decision (Hasura redundancy). 4 flagged pages. |
| affinity | 250 | 250 | END-TO-END. 7 flagged pages to triage. |
| agora | 213 | 213 | **END-TO-END, no charts to extract.** Verified by rendering: page 1 is a title page (logo, quote, intro note); the 682/794 drawing fills on pages 2-3 are table-row shading (429/517 measured as zero-height fills) and the only image on each page is the logo. Each of the 213 `.charts.json` correctly records `"charts": []` with that reason. The audit's "PARTIAL: no chart values" verdict is a FALSE ALARM - there is no chart layer to miss. 0.0% cipher. |
| banchero_costa | 243 | 243 (prose) | **LlamaParse COMPLETE.** 243/243 accounted: **166 cloud-parsed, 77 skipped as measured-clean, 0 failed.** Final gate **13/13** vs ground truth. 166 `.md` + 166 `.items.json`, 0 files containing glyph-cipher soup. ~938 pages / **~2,814 credits**. |
| intermodal | 252 | **252** | **COMPLETE 2026-09-24.** All 20 T/C fields on **252/252** documents (was 180). 252 `.md`, 21–33 KB. 251 distinct assessment dates, 2021-07-06 → 2026-09-18. Also captured 71 docs' extra 6-month dry-bulk rows (284 values). `02400a120`. |
| ism | 112 | 112 | PARTIAL: no table files. 0% cipher. |
| lion | 44 | 43 | **DONE 2026-09-24** (in-flight cron, verified): `md/lion/` 43 files + `lion_deals.parquet` 1,145 rows + `lion_demometer.parquet` 516 rows + `lion_summary.json`. Runner `run_lion.py`. 3 en-bloc pricing defects found and fixed (38 rows). `docs/lion_verdict.md`. 0% cipher. Note: the audit's "no tables" verdict refers to per-issue `*table*.json` sidecars, which lion stores as parquet instead — **the audit under-reports lion; read `docs/lion_verdict.md` before concluding it is incomplete.** |
| carriers | 129 | **129** | **COMPLETE 2026-09-24.** 2,866 S&P sales across 126 issues, 2021–2026, every row keyed to its issue date. 0 non-numeric prices, 2/2866 missing DWT. Verified: 0 field mismatches over 113 records in 5 documents against each PDF's own text layer. `2a8d93c49`. |
| clarksons | 10 | 0 | Tiny, 0% cipher. Low priority. |
| bancosta / general_broker | 2 | 0 | Singletons, 0% cipher. Low priority. |
| gibson, allied, anchor, golden_destiny, other | — | — | **STOPPED publishers** (archive/). Backfill only if <180d. |

---

## 5. SKIP DECISIONS (do not relitigate)

* **fearnleys** — SKIPPED. The Hasura API already delivers their data
  (563,000+ rows held). PDF text is redundant. User explicitly instructed this.
* **agora** — 0 ciphered pages. No cloud spend; it only needs a vision spot-check.
* **prose-merged tables in advanced_shipping** — declared cosmetic, abandoned by
  decision (`docs/prose_merge_verdict.md`). Zero incremental value; the fused panel is
  Baltic data already held in `08-baltic` (3,038 files) and already displayed.

---

## 6. HOW TO VERIFY (non-negotiable)

1. **Render the page and LOOK at it.** Every real bug found in this programme was found
   by looking; four of our own detectors were confidently wrong.
2. **Cross-check chart values against the prose on the same page.** They state the same
   quantity two ways.
3. **Never trust a count.** "Files exist" is not "values are correct". A broken check
   also condemns correct work — when a check surprises you, verify the CHECK against the
   rendered document first.
4. **Control tests cut both ways** — they catch complete-looking wrong output AND a
   subtly-buggy control condemning correct output. When a control disagrees, suspect the
   control.

---

## 7. CREDENTIALS

LlamaParse key lives in the Hermes secrets file, **read directly by scripts**:

```bash
python3 scripts/tools/set_llama_key.py --key llx-...   # add / rotate
python3 scripts/tools/set_llama_key.py --check         # verify (prefix/tail only)
```

* `~/.hermes/.env` is **not** exported into terminal subprocesses — a key there is
  invisible to `os.environ` unless Hermes happens to have reloaded. Scripts therefore
  read the file directly (see `get_api_key()` in any runner).
* Never print, commit, or log the value. Never `sed -i` that file (converts CRLF→LF).
* The user rotates across **11 free Google accounts, 10,000 credits each** — a pool of
  **110,000 credits**. **Treat keys as burnable — rotate rather than reuse.** Abundant
  budget removes the *cost* objection to a cloud parse but never the *evidence*
  requirement: escalate only what a local check has measured to fail, and never spend on
  data we already hold.
* **ALWAYS PACE YOURSELF, AND KEEP GOING — quiet is not stopped.** A run at ~30-50s/doc
  looks idle to a human. Prove liveness from state, never from "I can't see it".

---

## 8. IN-FLIGHT WORK (check before starting anything)

### banchero_costa LlamaParse run — FINISHED
```
python3 -c "import json;st=json.load(open('data/extracted/llamaparse_banchero/_run_state.json'));print(len(st['done']),'done',len(st['failed']),'failed',len(st.get('skipped_clean',{})),'skipped')"
```
**Result: 243/243 accounted — 166 parsed, 77 skipped as measured-clean, 0 failed.**
Final verification gate 13/13 vs ground truth. 166 `.md` + 166 `.items.json`;
**0 of 166 files still contain glyph-cipher soup.** ~938 pages / ~2,814 credits.

**Credit reconciliation, stated honestly:** the calibrated map measures **662** ciphered
pages, but the run paid **938**. The reason is ordering: the detector fix landed
*mid-run*, so documents processed before it used the wider broken map. Correcting the
detector first would have saved ~1,236 credits. The lesson for the next paid run is
**calibrate the routing map BEFORE the first document, not during it.**

Two of the 166 outputs are bunker-price reports rather than tanker-rate reports
(e.g. 2021 W39 is `# COMMODITY PRICES` with IFO 380 Rotterdam 448.0, +82.1% YoY). That
is correct extraction of a different section, not a failure.

### paid-surface scan
`python3 scripts/tools/measure_paid_surface.py` → `data/derived/paid_surface_by_source.json`
(run with the CALIBRATED detector; `scripts/tools/calibrate_cipher_detector.py` proves it
against known-ciphered and known-clean pages before any reading is trusted).

---

## 9. NEXT ACTIONS IN ORDER

1. **xclusiv chart roll-out** — the capability is PROVEN (5 TCE series recovered and
   validated against the page prose) but only on 2 documents. Verify on 3+ years first,
   then run across chart pages, most-recent-first. ~45 cr/page.
2. ~~**advanced_shipping control** — 1 doc, the one with the Ship Recycling Gaddani/Turkey
   merge.~~ **CORRECTED 2026-09-24: that premise was WRONG.** Gaddani does not appear in
   advanced_shipping at all — 0 of its 249 documents or table files contain it. The merge
   is in **star_asia** (191 of 193 documents mention Gaddani), and it is a LOCAL CELL-BOUNDARY
   defect, not a cipher problem, so it needs no cloud credits:
   ```
   truth :  GADDANI, PAKISTAN | 550~560  540~550  520~530  580~590  STABLE
   ours  :  GADDANI, PAKISTAN TURKEY *For Non-EU... | 550~560 ...
   ```
   Measured scope: **17 of 1,187 yard-label cells (1.4%)** carry a value or the next row's
   yard into the label cell. 416 Gaddani rows pair correctly with PAKISTAN. Worth fixing
   locally, not worth 45 cr/page.
3. Triage the small flagged sets: intermodal 25, star_asia 24, affinity 7, agora 5,
   xclusiv 4, fearnleys 4. **Total 69 pages ≈ 207 cr** — cheap. (Note: intermodal's
   flagged pages were the 6-month rows, now captured — re-measure before spending.)
4. Chart values owed for: agora (213), ssy (519).
5. ism needs table sidecars; clarksons (10) and the two singletons are low priority.
6. Vision spot-check a sample from each completed source before calling it closed.
7. Corpus groups outside 01-brokers are a SEPARATE programme: 03-breakwave 18,566 ·
   08-baltic 3,038 · 02-hellenic 14,130 · 07-signal 2,400 · 06-drewry 829 · 09-ppa 493.

## 9a. TIME-SERIES REQUIREMENT (the user's stated goal)
Weekly PDFs repeat the same structure, so extraction must land in a shape that builds
series across issues — not one-off prose. Required per source:
* a **stable date/issue key** per document (the run_state files carry this);
* **repeatable table columns** across issues (same routes, same fields week to week);
* **chart series keyed by date** so multi-year curves concatenate.

xclusiv is the proof this works: 5 named panels (VLCC / Suezmax / Aframax / MR Atlantic
Basket / MR Pacific Basket) recovered with a `Date` column spanning Aug-21 → Aug-26, plus
per-panel Average/Min/Max reference lines. The same concatenation must be verified for
the other sources once their chart values exist. **Do not call a source closed until its
repeated tables demonstrably stack into a time series.**

---

## 10. HARD LESSONS (do not relearn)

* **SOURCE BY SOURCE ONLY.** No generic cross-publisher runner — a previous
  mass-extraction attempt produced garbage. Measurement scripts may be shared; the
  extraction strategy must be per-source.
* **A wrong value is worse than a missing one.** Record unlabelled values as
  values-without-subject rather than guessing a label.
* **Render and look.** Always.
* **Check the existing EXTRACTION, not just the existing INGESTION** — a source was
  wrongly declared "skipped" while 257 finished `.md` files sat on disk.
* **Wasted-spend pattern to avoid:** the first test cost 160 credits because it used
  plain `agentic`, cost optimizer off, no page targeting. Always set page targeting.
* **Numbers convention differs per publisher** — advanced_shipping uses European
  (`60.000`=60000), star_asia ISO (`29,580`=29580). Derive per source; never share a
  numeric parser.
* Emojis are banned in this repo. Commits: branch only, code and data separate.
* `max_workers=2`, CPU-only, 8.3 GB RAM — do not run two heavy local jobs at once.
