# MASTER HANDOFF — Shipping maritime knowledge-base extraction

**THIS IS THE AUTHORITATIVE CURRENT-STATE DOCUMENT.** Read it top to bottom before
touching anything. `docs/MASTER_EXTRACTION_PLAN.md` is now historical context and points
here; this file supersedes it.

Written: **2026-09-25 00:40 IST**
Repo: `C:/Users/Dell/Github/Shipping`
Written for: **a different agent harness (Google Antigravity)** picking this up cold.

---

## 0. READ THIS FIRST — five things that will waste your time if you don't know them

1. **Do NOT extract data we already hold.** The user has stated this five or six times.
   Baltic Dry / Capesize / Panamax / Supramax / Handysize / Tanker Dry / Clean Tanker and
   the 1/5/7/10-year time-charter averages are ALL already held. Chart work on them
   restates what we have and is worth zero. This is also why the Fearnleys Hasura API
   was skipped. Run the audit (section 9) before building any chart pipeline.
2. **Source by source. One bespoke pipeline per publisher. Never a generic runner.** A
   previous mass-extraction attempt produced garbage and the user corrected this twice.
   Number conventions are literally opposite between publishers (advanced_shipping uses
   European `60.000` = sixty thousand; star_asia uses ISO `29,580`). A shared numeric
   parser is a guaranteed 1000x error somewhere.
3. **Render the page and LOOK at it.** Six instruments gave confidently wrong readings
   during this work. Every single one was caught by rendering a page and looking at it.
   Never trust a count, a detector, or an audit verdict.
4. **A wrong value is worse than a missing one.** Never assign a label by row order or
   regex match order — only by geometry or exact-vocabulary match. Incomplete label
   detection must return NOTHING, never a fallback guess.
5. **The working tree is dirty.** 1,170 changed files. The branch IS pushed (see section 2)
   but 148 commits exist on it that are NOT on main, and the working tree carries
   uncommitted work. Do not assume anything is safe because it looks committed — check.

---

## 1. THE GOAL, as a close condition

Build a deep, interconnected maritime knowledge base. Phase order is
**(1) data extraction → (2) depth of knowledge → (3) interconnectivity.**

**The user is emphatic that phase 1 is EXTRACTION ONLY and that depth comes LATER, gated
by him.** Do not start building the knowledge graph, embeddings, or prose synthesis
while extraction is still open on a source. An earlier attempt to jump to depth is why
the current plan is source-by-source and measured.

### The ultimate structure — what this is becoming

```
corpus/                       PDFs + HTML, the GROUND TRUTH. Never edited.
  01-brokers/                 the shipbroker weeklies — the active programme
  02..09, 11, archive, books  the rest; 9 of 10 groups already held, see §3
  _MANIFEST.json              group / publisher / cadence / liveness rule

        │  extraction (this programme, per-source, bespoke)
        ▼
data/extracted/
  md/<source>/                prose + *.tables.json + *.charts.json  (faithful, per doc)
  charts/<source>/            vector chart series, calibrated from the printed axis
  llamaparse_<source>/        cloud outputs + _run_state.json (resumable)
  series/<source>_*.csv       THE TIME SERIES — the stacking product, see §9a
  │                           (*.parquet where a source stores tables that way)
  ▼
data/                         the LIVE product the dashboard already renders
  indices/ flows/ etf/ futures/ commodities/ bunkers/ views/ derived/
  │                           339 feed CSVs, 131 files the app actually fetches
  ▼
knowledge/                    the KB tier — PHASE 2, NOT STARTED, user-gated
  docs/  chunks/  manifests/  1,081 + 35 files exist, written by ANOTHER agent branch
  │                           (agent/antigravity LightRAG layer). Not this programme.
  ▼
graph / spine / multi-hop     PHASE 3, the other agent's "Decision 3/4" work
```

**Three things to understand about that picture:**
1. **`corpus/` is ground truth and `data/extracted/` is derived.** A PDF is never
   overwritten; extraction writes beside it. If a value is ever wrong, the PDF settles it.
2. **The dashboard is not the goal, it is the current product.** `data/` is already
   live at `yieldchaser.github.io/Shipping/` and being pushed to by scheduled GitHub
   Actions. Extraction adds to what the app can show; it does not replace the app.
3. **The KB tier is a separate programme on a separate branch.** Do not merge
   `knowledge/` work into extraction commits, and do not let an extraction commit
   depend on it.

### What "properly extracted" means, per source

A broker source counts as **properly extracted** only when all of these hold:

- **Text** — faithful prose, complete, nothing dropped.
- **Tables** — structured values, correctly labelled.
- **Chart values** — plotted series as numbers, **but only for series we do not already
  hold** (section 0 rule 1).
- **A time series that demonstrably stacks.** This is the real bar. The master plan says
  it explicitly: *do not call a source closed until its repeated tables demonstrably
  stack into a time series.* The validation is a **cross-report agreement check**: each
  weekly report redraws the same window, so the same calendar position measured in two
  different reports must agree. Correct is **~1% median spread**. This is the only
  independent proof, because no per-document metric can see a join error.
- **Verified by looking at the rendered page**, not by counting files.

**Current honest count against that bar: 1 of 15 broker sources fully closed (ssy).
intermodal is extracted but its agreement check fails at 58.2%.** See section 4.

---

## 2. GIT STATE — read this before committing anything

```
current branch        : benchmark/extraction-comparison
branch HEAD           : 86d527584  "handoff: self-consistent git state..."
local main            : a95695158
origin/main           : a95695158   (in sync — main is NOT behind)
main..HEAD            : 148 commits on the branch that are NOT on main
origin/benchmark/extraction-comparison
                      : EXISTS. Pushed 2026-09-25 ~00:57 IST, exit 0, ~9.4 minutes
                        for 40,313 corpus files. GitHub warned that
                        data/derived/fearnleys_fixtures_full.csv is 62.23 MB, over the
                        50 MB recommended maximum — that is why the push is slow, not a
                        failure. A PR can be opened at:
                        https://github.com/yieldchaser/Shipping/pull/new/benchmark/extraction-comparison
working tree          : 1,170 changed files
                        1,153 modified
                        16 untracked
                        1 deleted  (scripts/extract/build_series_wrong_gate.py)
```

**CRITICAL: the 147 branch commits are unpushed and exist only on this machine.**
If this machine is lost, that work is lost. Pushing the branch is the single highest
value action available right now.

**CRITICAL: `corpus/` is tracked ON THE BRANCH (40,313 files) but NOT on main (0
files).** The diff `main..HEAD` therefore shows 40,313 corpus files. That is not data
loss, it is the branch carrying a tree that main does not have. Do not "clean this up"
by checking out main — that would appear to delete the corpus.

**Untracked files (16)** — these are real work not yet committed:
```
corpus/01-brokers/_digests/bancosta/                             (new folder)
corpus/01-brokers/_digests/general_broker/2026/...carriers_...w38.md
corpus/01-brokers/_digests/intermodal/2026/...intermodal_...w38....md
corpus/01-brokers/_digests/ssy/2026/...atlantic_...21_september_2026.md
corpus/01-brokers/_digests/ssy/2026/...pacific_...21_september_2026.md
corpus/01-brokers/_digests/star_asia/2026/...week_37.md
corpus/01-brokers/_digests/xclusiv/2026/...21st_september_2026.md
docs/intermodal_column_defect_FOUND.md
docs/parser_multiperiod_fix_state.md
docs/ssy_fix_applied.md
scripts/data/
scripts/extract/publishers/merge_source_charts.py     <- EMPTY-OUTPUT merger, see 4.3
scripts/extract/publishers/star_asia.py
scripts/tools/survey_outside_brokers.py
scripts/verify/verify_advanced_shipping.py
scripts/verify/verify_star_asia.py
```

**Modified but uncommitted, by area:** `knowledge/docs` 1,081 · `knowledge/chunks` 35 ·
`corpus/01-brokers` 27 · `scripts/extract` 12 · `scripts/verify` 2 · plus singles.

**One GitHub Actions run was triggered and completed during this session:**
- `daily_update.yml` (Daily Baltic Index Update), run ID `36037578405`, conclusion
  `success`, 27/27 steps, pushed `1ec547adf` to main. Since then main has advanced
  further to `a95695158` via other scheduled runs.
- This ran the scrapers on GitHub's runner, not locally. It refreshed indices, flows,
  bunkers, Fearnleys, Intermodal TC, ETF quotes, SGX iron ore, Capital Link, Alibra,
  Gibson tanker curves, and rebuilt the frontend view layer.

**Commit hygiene rules in force:** branch only, never disturb main · code and data
commits separate · **no emojis anywhere** (hard rule, repo tests enforce zero) ·
never `setx` · never print or commit the API key.

---

## 3. THE CORPUS

`C:/Users/Dell/Github/Shipping/corpus` — **9,708 PDFs + 9,974 HTML files, 13 groups.**

| group | pdf | html | what it is |
|---|---|---|---|
| **01-brokers** | **2,739** | 0 | **the shipbroker weeklies — this is the active work** |
| 02-hellenic | 3,969 | 3,204 | Hellenic Shipping News streams (iron_ore, demolition, shipbuilding, charter) |
| 03-breakwave | 302 | 3,221 | Breakwave Advisors research |
| 04-poten | 1,087 | 0 | Poten & Partners tanker opinions, 2005-2026 |
| 05-seabrokers | 97 | 0 | offshore market intelligence, monthly |
| 06-drewry | 276 | 0 | Drewry maritime intelligence |
| 07-signal | 9 | 511 | The Signal Group |
| 08-baltic | 0 | 3,038 | Baltic Exchange fixture archive |
| 09-ppa | 493 | 0 | Pilbara Ports Authority throughput |
| 11-other | — | — | Panama Canal advisories (new) |
| archive | 724 | 0 | STOPPED publishers — historical use only, must not enter the live pipeline |
| books | 12 | 0 | foundational maritime economics literature |

**Also present:** `corpus/_MANIFEST.json` (generated_for 2026-09-23, stale_threshold_days
200, 12 groups, each with publisher/cadence/notes) and `corpus/_inventory_untracked.json`.

**A scare worth recording:** at 23:56 on 2026-09-24 six folders
(`02-hellenic 03-breakwave 05-seabrokers 07-signal 08-baltic books`) disappeared from
disk, then returned. The pattern was exact: **every folder that had HTML files was gone;
every PDF-only folder survived.** Cause never established. **`corpus/` has 0 tracked
files on main, so git cannot restore it.** If folders vanish again, do not assume a
recovery path exists. Disk was 95% full (27 GB free) at the time.

**01-brokers is the ground truth for the active programme.** PDFs are authoritative;
`_digests/` under each publisher holds the derived markdown.

### 01-brokers inventory — 15 folders, 2,739 PDFs

| broker | pdfs | years |
|---|---|---|
| ssy | 519 | 2021-2026 |
| fearnleys | 257 | 2018-2026 |
| intermodal | 252 | 2021-2026 |
| affinity | 250 | 2021-2026 |
| advanced_shipping | 249 | 2021-2026 |
| banchero_costa | 243 | 2021-2026 |
| agora | 213 | 2021-2026 |
| star_asia | 193 | 2021-2026 |
| xclusiv | 266 | 2021-2026 |
| carriers | 129 | 2021-2026 |
| ism | 112 | 2023-2026 |
| lion | 44 | 2024-2026 |
| clarksons | 10 | 2026 |
| bancosta | 1 | 2026 (singleton) |
| general_broker | 1 | 2026 (singleton) |

### Corpus groups outside 01-brokers are ALREADY HELD — do not rebuild

Measured 2026-09-24 with `scripts/tools/survey_outside_brokers.py`, testing three
baselines: the live feeds (`data/**/*.csv`), our own extraction, and what `index.html`
actually fetches for display.

**9 of 10 groups are already held.** Only `archive/` (725 files) is a candidate, and the
manifest's own liveness rule says a stopped publisher must not enter the live pipeline.
Examples: hellenic already yields 992 series; breakwave and signal render on live
dashboard tabs; baltic has 3,038 HTML fixture circulars already ingested. **Re-check all
three baselines before building anything outside 01-brokers.**

---

## 4. PER-SOURCE STATUS — measured against the artefacts, 2026-09-25

### 4.1 Artefact counts on disk

| broker | pdfs | `.md` | table sidecars | chart files |
|---|---|---|---|---|
| advanced_shipping | 249 | 249 | 249 | 249 |
| affinity | 250 | 250 | 250 | 250 |
| agora | 213 | 213 | 213 | 213 |
| banchero_costa | 243 | 243 | 243 | 0 |
| carriers | 129 | 129 | 0 (parquet instead) | 0 |
| clarksons | **10** | **0** | 0 | 0 |
| fearnleys | 257 | 257 | 257 | 257 |
| intermodal | 252 | 252 | 0 | 252 |
| ism | 112 | 112 | 0 | 112 |
| lion | 44 | 43 | 0 (parquet instead) | 0 |
| ssy | 519 | 519 | 519 | 521 |
| star_asia | 193 | 193 | 193 | 193 |
| xclusiv | 266 | 266 | 266 | 266 |
| bancosta | 1 | 0 | 0 | 0 |
| general_broker | 1 | 0 | 0 | 0 |
| **TOTAL** | **2,739** | **2,726** | **2,190** | **2,313** |

### 4.2 The two real time series

- **`data/extracted/series/ssy_capesize_index_series.csv`** (534,816 bytes) — **CLOSED.**
  8,881 keys, 65,869 points, 1,432 series, 0 credits. Cross-report agreement
  **median 0.26%, p90 2.7%, 87.5% within 2%**. This is the reference implementation.
- **`data/extracted/series/intermodal_baltic_tc_series.csv`** (1,010,016 bytes) —
  **OPEN.** 19,691 rows, 9 series (BDI/BCI/BPI/BSI/BHSI + AVR 5TC/7TC/10TC + average),
  2,189 points each, 2020-08-31 → 2026-08-31. Re-measured just now: **19,074 keys carry
  more than one report; median spread 58.2%, p90 114.6%, only 0.3% within 2%.** The
  merge was NEVER re-run after the three fixes described in 4.4, so this is the
  pre-fix number.

### 4.3 Seven empty series files — DELETE THESE, do not complete them

```
data/extracted/series/advanced_shipping_chart_series.csv    48 bytes
data/extracted/series/affinity_chart_series.csv             48 bytes
data/extracted/series/agora_chart_series.csv                48 bytes
data/extracted/series/fearnleys_chart_series.csv            48 bytes
data/extracted/series/ism_chart_series.csv                  48 bytes
data/extracted/series/star_asia_chart_series.csv            48 bytes
data/extracted/series/xclusiv_chart_series.csv              48 bytes
```

48 bytes = header row, **zero data rows.** They were produced by
`scripts/extract/publishers/merge_source_charts.py` (UNTRACKED) which walked a
`.charts.json` shape that does not exist. **They are not evidence of anything and must
not be mistaken for progress.** They are also unnecessary: the legend audit (section 9)
found **zero proprietary chart series in the broker corpus**, so there is nothing in
those charts worth stacking. Delete the files and the script.

### 4.4 intermodal — the one genuinely open extraction

Extraction itself is **exact**: 252/252 documents, 489 charts, 2,208 series, 600,123
points, 0 credits, and a 600-dpi pixel re-read matched the vector path to **0.01pt**.

Three defects were found and FIXED IN CODE but the batch was never re-run:
1. **x-axis date labels are outlined glyphs with no text layer.** They are rotated ~45°
   and their bounding boxes **interleave** (label 1 spans x 356.9-375.2, label 2 spans
   372.6-393.4 — a 2.6pt overlap). Clustering on x-overlap fused neighbours and found
   only 4-5 of 12 labels; the code then silently fell back to a **uniform 19.66pt grid
   starting at the frame edge — identical in every report** — which made one calendar
   date read as 21 different values. Fixed by clustering on **CENTRE**, and the uniform
   fallback was **removed entirely**. Incomplete detection now returns nothing.
2. **Daily vs weekly resolution.** The chart plots **weekly** points (~5 per month, ~262
   over 12 months). The code was interpolating to daily, inventing precision — W22 and W27
   gave 931 vs 960 for the same week. Fixed by dating points to the **month**.
3. A ±3-day join window was tested and made it worse (42.4%).

**Next action for intermodal:** re-run the batch with the fixed extractor, then re-measure
the agreement. The remaining suspect is **sub-floor extrapolation** on ladders whose
lowest printed tick sits above zero. The specific next measurement, not another inference
from aggregates: **count the points falling below the lowest printed tick on a real ladder.**

### 4.5 Sources extracted, with their specific caveats

| source | state | caveat you must know |
|---|---|---|
| **ssy** | **CLOSED, the reference** | 519/519. Nothing outstanding. |
| advanced_shipping | text+tables+charts | 0.0% cipher. Known cosmetic prose-merged table, declared cosmetic and abandoned by decision (`docs/prose_merge_verdict.md`) because the content is Baltic data already held in `08-baltic`. Uses **European number convention** — `60.000` = 60000. |
| affinity | text+tables+charts | 7 flagged pages, triaged clean. |
| agora | text+tables, **no chart layer exists** | 213/213. The 682/794 drawing fills are table-row shading (429/517 measured zero-height); the only image is the logo. Each `.charts.json` correctly records `"charts": []`. A prior audit reporting "missing chart values" here is a **false alarm**. |
| fearnleys | **SKIPPED BY DECISION** | Hasura API already carries their data (563,000+ rows held). Do not relitigate. Has genuine ciphered pages (2018 W29 p2 emits `\x1b\x06`, `\x17`, `\x1f\x04`) — 2 such pages were cloud-parsed as a control. |
| ism | text + 4 charts × 3 series | **No table sidecars.** 216 inline markdown table rows instead. A prior audit calling this "missing tables" was a **false alarm**. |
| star_asia | text+tables+charts | 24 flagged pages, 10 of which were proven real gaps and cloud-parsed. The Gaddani/Turky merge is HERE, not in advanced_shipping. |
| xclusiv | text+tables+charts | **Rolling ~2-year windows, NOT cumulative.** This is why the 11,970-credit roll-out was rejected and annual sampling (270 cr, 6/6 years, 13 series, 936 points, 2019-10→2026-04) was shipped instead. |
| banchero_costa | **LlamaParse COMPLETE** | 243/243 accounted: **166 cloud-parsed, 77 skipped as measured-clean, 0 failed.** Gate **13/13** vs ground truth. 0 of 166 outputs still contain glyph-cipher soup. **~938 pages / ~2,814 credits paid against a calibrated map that measured only 662** — the detector fix landed mid-run. Lesson: **calibrate the routing map BEFORE the first document.** |
| carriers | text+tables, no chart layer | 2,866 S&P sales across 126 issues, 2021-2026, every row keyed to its issue date. 0 non-numeric prices, 2/2866 missing DWT. Page 1 verified pure table: 711 drawings, 660 of them thin rules. |
| intermodal | **OPEN**, see 4.4 | 252/252 markdown, all 20 T/C fields on every document. |
| lion | text+tables, no chart layer | 43 `.md` + `lion_deals.parquet` 1,145 rows + `lion_demometer.parquet` 516 rows. Stores tables as **parquet, not sidecars** — an audit that only counts `*table*.json` under-reports lion. Read `docs/lion_verdict.md`. |
| **clarksons** | **NOT STARTED** | 10 PDFs, 0 `.md`. Render-verified: page 2 has two S&P tables (FLC HAPPINESS, COLUMBIA RIVER) and **zero plots**. 0% cipher. Lowest-effort remaining item. |
| bancosta / general_broker | NOT STARTED | 1 PDF each. Singletons. |

---

## 5. THE STANDING RULE — do not extract what we already hold

This is enforced in `docs/MASTER_EXTRACTION_PLAN.md` section 0 and by an executable
audit. It is the user's most-repeated instruction.

**The held set, measured:**
- BDI / BCI / BPI / BSI / BHSI — `data/extracted/series/intermodal_baltic_tc_series.csv`,
  **19,691 rows, 2,189 points each, 2020-08 → 2026-08.**
- 1/5/7/10-year T/C averages — same file (AVR 5TC BPI, AVR 7TC BHSI, AVR 10TC BSI) plus
  `corpus/02-hellenic/dry_charter`.
- Fearnleys Hasura API values — the API already carries them.

**A bare vessel-class name is NOT proprietary.** `Capesize`, `Kamsarmax`, `Panamax`,
`Supramax`, `Handysize`, `Aframax`, `Suezmax`, `VLCC` on a chart are the labels the Baltic
charts use **for the indices we already hold**.

**What IS worth extracting:** newbuilding and newbuilding-series prices, sale-and-purchase
prices, demolition/scrap values, asset and vessel valuations, steel/plate prices, forward
curves on named vessels or routes — anything whose only source is a broker's own table or
chart.

**The measured result, 1,001 legend swatches across 8 sources:**

| source | swatches | held | **proprietary** |
|---|---|---|---|
| xclusiv | 260 | 21 | **0** |
| intermodal | 159 | 13 | **0** |
| advanced_shipping | 136 | 5 | **0** |
| banchero_costa | 94 | 14 | 1 (Plate) |
| ism | 73 | 3 | **0** |
| fearnleys | 16 | 3 | **0** |
| affinity, agora, star_asia, lion, clarksons | 0 | — | **0** |

**ZERO proprietary chart series in the entire broker corpus.** The unrecognised labels
are region headings (`Bangladesh`, `India`, `Pakistan`), commodities (`Brent`, `Gold`,
`MGO`) and route names (`Azov`, `BlSea`, `Danube/POC`). **No broker chart here is worth a
dedicated extraction pipeline.** The remaining value is in the **PROPRIETARY TABLES** —
newbuilding prices, S&P, demolition values — which is table work, not chart work.

**BDTI and BCTI** are genuinely absent from `data/` (verified by scanning every CSV), but
they are public indices and **still not worth a 249-document pipeline**. Note they DO
render on the live dashboard — see section 10.

---

## 6. CREDENTIALS — LlamaParse

- Stored in `C:\Users\Dell\AppData\Local\hermes\.env` under `LLAMA_CLOUD_API_KEY`.
- File state: **25,459 bytes, 506 CRLF line endings.** Verify with
  `python3 -B scripts/tools/set_llama_key.py --check`.
- **NEVER print the value, never commit it, never leave it in a temp file, never use
  `sed -i` on that `.env`** — it converts CRLF to LF and corrupted the file once before.
- `~/.hermes/.env` is **not exported into terminal subprocesses**, so `os.environ` cannot
  see it. Scripts read the file directly via `get_api_key()`.
- Rotate with: `python3 -B scripts/tools/set_llama_key.py --key llx-...`
- The user rotates across ~5 free Google accounts at 10,000 credits each. **Treat keys as
  burnable — rotate rather than reuse.**

**Balance: ~3,520 of 10,000 used on the last key, ~6,480 remaining.** A third key was
rotated in during this session. Total programme spend ≈3,264 credits.

**Why the balance sat still for hours, answered with measurement** (scripts committed as
`cloud_vs_local.py`, `score_cloud_vs_local.py`):

| page | local text layer | LlamaParse cost_effective |
|---|---|---|
| banchero 2024 W47 p3 (cipher) | **0/5** | **5/5** |
| fearnleys 2018 W29 p2 (cipher) | **0/8** | **5/8** |
| star_asia 2023 W42 p11 (vector table) | **0/15** | **11/15** |

Scores are against values read off the rendered page. **ssy (519pp) and intermodal (252pp)
cost 0 credits** because they were vector charts with printed axes — geometry reads those
exactly and free. Spending 45 cr/page there would have bought worse data.

**The 69 flagged pages outside banchero were triaged individually: 48 CLEAN, 2 CIPHER,
10 NO NUMBERS. 12 were cloud-parsed at 3 cr = 36 credits. 12/12 returned table
structure.** The other 57 got no spend.

**One verdict reversed when the page changed, and it matters:** an earlier pass concluded
star_asia needed no credits because a page scored local 15/15 — but that was 2023 W40 p9,
which HAS a text layer. The 10 flagged pages do not. **A source-level verdict would have
been wrong for 10 pages.** Score every page on its own.

---

## 7. LlamaParse usage policy

**Default: do NOT use the cloud.** Local extraction is free and sufficient for clean
PDFs. Escalate a page only when a local check proves the text layer is unreadable:
glyph-ciphered table text, or a vector chart whose series we need and cannot geometry-fit.

### The LOCAL engine ladder, and the flags that decide whether it is cheap

The most expensive discovery in the whole extraction work was a **default**, not a
missing package. `liteparse` is the fast local path, and out of the box it is ~20x
slower than it needs to be on this corpus.

| flag | default | measured effect | use |
|---|---|---|---|
| `ocr_enabled` | **ON** | **43 of every 45 seconds** per doc spent attempting OCR that this corpus does not need. **0 of 312 sampled pages across 7 sources genuinely required it.** | **set `False` ALWAYS** |
| `extract_blocks` | — | **~4s per PAGE** (40s for a 10-page file) against the library's own claim of 2-5ms/page. Only needed for typed table cells, which another tool supplies. | **`False` on the hot path** |
| `output_format` | unset | `get_page(i).markdown` returns **EMPTY** without it, producing a 319-byte "successful" file. | **always explicit** |

**Measured result of `ocr_enabled=False`:** 45s → **2.2s per document**, byte-identical
output. The full advanced_shipping run went from **~3 hours to 8.2 minutes.**
**Set these flags on EVERY publisher, every time — they are not saved in a config the
tool reads, they are call arguments.**

Do not guess which knob is hot: time each phase separately. Two separate wrong
suspicions (chart extraction, then blocks) came before the flag was found.

**Engine ladder for this corpus (digitally-born, CPU-only):**
PyMuPDF for text (strongest single extractor, 100% cell recall on 3 of 5 golden pages) ·
**pdf-inspector** for typed table cells (best measured: kept the index column and row
labels liteparse dropped) · **liteparse** for fast markdown with the flags above ·
**camelot `flavor="stream"`** for schema (87-100% on text-layer tables) · **pdfplumber**
as union partner · **Tabula** needs a JRE on PATH and silently returns nothing without it ·
**Docling is audit-only** — best recall but ~1900 s/doc on CPU, never bulk.

**The accuracy lever:** tables give **schema**, the text layer gives **recall**. Extract
both, then reconcile: for every table cell containing a digit, check whether that value
exists in the page text. Store a `text_verified` ratio per table. On one broker page that
check recovered **65 values the grid had silently dropped.**

| tier | cr/page | use |
|---|---|---|
| `cost_effective` | 3 | **default for ciphered text** — passed 13/13 |
| `agentic` | 18 | only if cost_effective fails a gate |
| `agentic_plus` | 45 | **charts only** (`specialized_chart_parsing`) |

- `cost_optimizer` **cannot** be enabled below agentic (API returns HTTP 422) and is
  redundant with page targeting.
- **Page targeting is the cost lever:** `page_ranges.target_pages: "1,3,5-10"`.
  *Every page you skip is a page you don't pay for.*
- 48-hour caching makes an identical re-run free, but **any option change busts the cache.**
- A plain `agentic` test with no page targeting cost 160 credits. **Always page-target.**
- Free local scan first: `python3 scripts/tools/measure_paid_surface.py <source>`

**Calibrated paid surface, 3,237 docs / 28,250 pages / 731 flagged (2.6%):**
banchero 662 (17.6%) · intermodal 25 · star_asia 24 · affinity 7 · agora 5 ·
xclusiv 4 · fearnleys 4 · advanced_shipping 0 · carriers 0 · ssy 0 · ism 0 · lion 0 ·
clarksons 0. **The cipher is a banchero problem, not a corpus-wide one.**

---

## 8. WHAT TO DO NEXT, in this order

**0. VERIFY THE BRANCH IS PUSHED and current.**
`git ls-remote --heads origin | grep benchmark` — the branch now EXISTS on origin
(pushed 2026-09-25, exit 0), but at `0c5320d00`, which is **two commits behind** local
HEAD. Push again before relying on origin:
```bash
git push origin benchmark/extraction-comparison
```
**Do NOT merge it to main yet.** It carries 148 commits and 40,313 corpus files. That
is a review decision, not an extraction decision, and the user has not made it.

**CONCURRENT BRANCHES ON ORIGIN — mostly DISCARDED earlier work. The user's own
judgement, not an inference from commit messages.** The user has stated that the
**Muse, Claude, and the earlier Antigravity branches are earlier work that has been
discarded.** Treat them as dead unless he says otherwise. They are recorded here only so
nobody mistakes them for live work or re-does what was already thrown away.

| branch | commits | files vs main | status |
|---|---|---|---|
| `agent/antigravity` | 6 | 9,887 | **discarded per the user** (a newer Antigravity workstream is starting) |
| `agent/muse-spark` | 28 | 9,896 | **discarded per the user** |
| `claude/maritime-kb-inventory-hzbhlx` | 28 | 9,876 | **discarded per the user** |
| `claude/investigate-failed-runs-31vpb` | 1 | 65,703 | superseded |
| `session/agent_4987ef96-...`, `session/agent_704f43e2-...` | 12 / 11 | ~65,698 | session branches, not workstreams |
| `auto/extract-fixes-2026-09-21` / `-09-22` | 12 / 35 | 337 / 442 | earlier auto-fix passes |

**Do NOT read these as a competing source of truth, do NOT merge them, and do NOT try to
reconcile against them.** If a discarded branch is the only place some code exists, that
code is gone for a reason — ask the user, do not resurrect it.

The one thing worth keeping from the measurement: **this branch's extraction pipelines
appear on NO other branch** — `run_ssy_charts.py`, `run_intermodal_charts.py`,
`merge_ssy_charts.py`, `audit_chart_legends.py`. The 56 overlapping files were shared
infrastructure and generated data (`docs/EXTRACTION_RUNBOOK.md`, `docs/alibra_data/**`,
`scripts/analysis/*`, five loose scrapers). So there is no extraction work to lose to
them.

**FOUR CRON JOBS ARE RUNNING AGAINST THIS REPO — all currently FAILING.** This is the
single most important operational fact and it was absent from the earlier draft.

| job_id | name | schedule | last status |
|---|---|---|---|
| `345bc8db9233` | Corpus extraction orchestrator (hourly) | every 60m | **error** |
| `d77cc9df53c4` | Extraction deep review + fix (3-hourly) | every 180m | **error** |
| `12f7fa574166` | Unattended: source-by-source (30m) | every 30m | **error** |
| `c0400ecf1a0b` | Watchdog: banchero LlamaParse (script-only) | every 30m | **delivery_failed** |

- The first three all fail with **`RuntimeError: HTTP 429: Go usage limit exceeded`** —
  they run on `deepseek-v4.1-flash` via `opencode-go` and are being rate-limited. They are
  NOT doing work. **If the user says "nothing is running", this is why: they are erroring,
  not extracting.** Either raise the provider quota or pause them, because on every retry
  they will burn a turn and change nothing.
- All three have `workdir: C:\Users\Dell\Github\Shipping`, `continuity: true`,
  `deliver: origin`, toolsets limited to `terminal` + `files`.
- `c0400ecf1a0b` fails with **`no delivery target resolved for deliver=all`** — a config
  bug, not a script bug. It also points at a run that is **FINISHED** (banchero 243/243),
  so it has nothing left to watch. **Delete it or pause it.**

**THE 1,170 DIRTY FILES ARE NOT MINE.** 1,100 of them have an mtime of 2026-09-25 00:xx,
i.e. they were written by one of the other agents while this session was running. They
break down as `knowledge/docs` 1,081 · `knowledge/chunks` 35 · `corpus/01-brokers` 27 ·
`scripts/extract` 12 · `scripts/verify` 2 · singles. **Do not commit or revert them as
if they were extraction work — they are another workstream's output and will conflict if
you sweep them into your own commit.** The genuinely mine-and-uncommitted set is the
**16 untracked files** listed above, and they are small.

**1. DELETE the 7 empty 48-byte series files and `merge_source_charts.py`.** They are
false evidence. Section 4.3.

**2. ADD A DATE KEY TO THE TABLE SIDECARS. This is the unlock for everything.**
Measured: the sidecars are `{"header": [...], "rows": [[...]]}` and **none of the 2,190
carries a `date` / `issue_date` / `as_of` / `report_date` field.** Without a per-document
date, nothing can stack into a series. The date is already available in the filename and
in the `_run_state.json` for every source, so this is a **deterministic join, not
re-extraction.** Do this for ONE source first, then the rest.

**3. BUILD PER-SOURCE table→series mergers, one source at a time**, each gated on the
ssy cross-report agreement check. Target ~1% median spread. Same discipline as ssy:
route/scope in the key, year from the series, rebase detection. Stop at the first
source that cannot pass the gate.

**4. FINISH intermodal** — re-run the fixed extractor, re-measure agreement, and do the
direct count of points below the lowest printed tick (section 4.4).

**5. THEN** clarksons (10 PDFs, 0 md, 0% cipher — the lowest-effort item remaining) and
the 2 singletons.

**Do NOT** start anything in `corpus/` outside 01-brokers without re-running the
three-baseline check in section 3. 9 of 10 are already held.

**Suggested first source for step 2+3:** **advanced_shipping** (249 documents, all four
of its bulkers charts are held indices, tables are the real prize, 0.0% cipher, no paid
surface) — or **carriers**, which already has a proven date-keyed 2,866-row S&P series and
is the template to copy.

---

## 9. THE AUDITS — run these, they are the gates

| script | what it does |
|---|---|
| `scripts/tools/audit_chart_legends.py` | **Run before any chart pipeline.** Reads every legend off the PDF page (swatch colour → the word printed beside it) and classifies HOLD / NOVEL / UNKNOWN. This is the enforcement of section 5. |
| `scripts/tools/survey_outside_brokers.py` | Three-baseline check for the non-broker corpus groups. |
| `scripts/tools/measure_paid_surface.py` | Free local estimate of which pages genuinely need the cloud. Run the CALIBRATED detector. |
| `scripts/tools/calibrate_cipher_detector.py` | Proves the cipher detector against known-ciphered and known-clean pages BEFORE any reading is trusted. |
| `scripts/tools/verify_flagged_pages.py` | Renders flagged pages and scores the local text layer. |
| `scripts/tools/cloud_vs_local.py` / `score_cloud_vs_local.py` | The measured cloud-vs-local comparison. `--force <file.pdf>:<page>`. |
| `scripts/extract/publishers/merge_ssy_charts.py` | **The reference merger.** Carries the self-validating agreement check. Copy its structure. |
| `scripts/extract/publishers/run_ssy_charts.py` | **The reference extractor.** Vector-only, 0 credits, handles two layout eras. |
| `scripts/verify/verify_advanced_shipping.py`, `verify_star_asia.py` | UNTRACKED, newly written. |

---

## 10. KNOWN OPEN DEFECTS — do not rediscover these

1. **intermodal agreement 58.2%** — see 4.4. The one real open extraction.
2. **The dashboard shows duplicated percentile windows.** On the BDTI and BCTI tabs, all-time
   Pctl, 10Y Pctl and 5Y Pctl read the SAME value (100.0% and 98.4% respectively), and
   "vs 5Y mean" is byte-identical to "vs 10Y mean" (+286.0% / +119.7%). Consistent with
   one un-windowed series labelled three times. The 20D change and Z-scores DO differ, so
   the per-day data is real — it is specifically the multi-window comparisons that do not
   separate. **NOT YET INVESTIGATED.** I was mid-report on this when asked to trigger the
   update instead.
3. **BDTI/BCTI already render on the dashboard.** I declared them "not held" after
   scanning `data/**/*.csv` only. The app holds them somewhere that scan did not reach.
   My error.
4. **star_asia Gaddani/Turkey merge** — 17 of 1,187 yard-label cells (1.4%). A LOCAL
   cell-boundary defect in the table sidecar writer, not a cipher problem, so **no cloud
   credits**. 416 Gaddani rows pair correctly. The text layer and the cloud parse BOTH
   keep GADDANI and TURKEY apart (`**GADDANI, PAKISTAN` on its own row; the cloud returns
   it as a `PAKISTAN` column) — so the defect is purely in the sidecar cells.
5. **22 scripts still point at a deleted `reports/` path**, including intermodal's live
   pipeline. Stale provenance strings; the data itself is good.
6. **290 unextracted seabrokers chart pages · 850 bot-walled docs · 17 zero-byte
   knowledge chunks.**
7. **Fearnleys S&P sync is a fetcher failure, not a PDF problem.**
8. **Advanced Shipping Ship Recycling table p9 merges Gaddani+Turkey** in every strategy
   (a footnote overlay) — a different defect from #4, also unvalidated.
9. **Mojibake residual, deliberately unfixed:** `W`→`t`/`T`→`d` variant B · ambiguous
   `\x11` · 58-59 banchero files mapping glyphs to ASCII punctuation. **Only LlamaParse
   solved this class (13/13).**
10. **Watchdog cron** `c0400ecf1a0b` ("Watchdog: banchero LlamaParse (script-only)") —
    **BROKEN: `delivery_failed` / "no delivery target resolved for deliver=all"**, and
    it watches a run that is FINISHED. Delete or pause it.
11. **xclusiv: 22 scripts with the stale `reports/` path** — same as #5.
12. **THREE CRON JOBS ARE 429-FAILING** — `345bc8db9233` (hourly), `d77cc9df53c4` (3-hourly),
    `12f7fa574166` (30m), all `deepseek-v4.1-flash` via `opencode-go`, all
    `RuntimeError: HTTP 429: Go usage limit exceeded`. They have been firing and failing
    instead of extracting. This is the answer to "I don't see anything running."
13. **Six older agent branches on origin, DISCARDED per the user** — see section 8.
    `agent/antigravity`, `agent/muse-spark`, `claude/maritime-kb-inventory-hzbhlx` and
    three others. Treat as dead; do not merge, do not reconcile, do not resurrect code
    that only exists there. The 1,170 dirty files in the working tree are output from
    that discarded workstream, not unfinished extraction work of mine.

---

## 11. HARD LESSONS — rules, not narrative

- **Source by source. One pipeline per publisher. Generic runners are banned.** A prior
  mass run produced garbage and the user corrected this twice.
- **Check what we already hold BEFORE building.** Test three baselines: the live feeds,
  our own extraction, what the app displays. A feed-only comparison ranked a source as
  the top target while 992 of its series already existed.
- **Render and look.** Six instruments lied during this work. Every one was caught by eye.
- **A check that surprises you is a check to verify first** — verify the CHECK against the
  rendered document before believing it.
- **Cross-report agreement is the only independent proof** of a merge. Per-document
  extraction can be flawless while the stacked series is garbage. On ssy this check found
  four merge defects in sequence: median spread went 48.8% → 4.8% → 0.80% → 0.26%.
- **A detector that falls back to a uniform assumption is worse than one that fails
  loudly.** A partial label detection silently spread dates evenly, making one date read
  as 21 values. **When detection is incomplete, return NOTHING.**
- **Do not manufacture precision the page does not carry.** Weekly points dated daily
  invented values; date to the resolution the axis supports.
- **Number format is a per-publisher hazard and a silent 1000x error.** advanced_shipping
  writes `60.000` = sixty thousand AND `34,5` = 34.5 in the same document. Reading
  `60.000` as `60.0` is plausible-looking and no automated check catches it.
- **A library default can cost 20x.** liteparse's `ocr_enabled` defaults to ON and spent
  43 of every 45 seconds per document on OCR that 0 of 312 sampled pages needed. Setting
  it False took a ~3-hour run to 8.2 minutes with byte-identical output. **Set the flags
  explicitly on every publisher; they are call arguments, not saved config.**
- **The chart's last point and the table's current value are different quantities.** The
  axis runs to the report's month-end, so the final plotted point precedes the report
  date. The gap is one-signed. Do not gate on it, do not let either overwrite the other.
- **An unusual value is not a wrong value.** A 90,279 ssy peak and negative xclusiv TCE
  values were both real. Crop the render and look before "fixing" anything.
- **A publisher that rebases an index is a data fact, not a bug.** SSY rebases between
  editions with a byte-identical legend. Detection belongs in the merge.
- **Shadow strokes are not extra data.** Grey twins at 0.00pt offset with identical
  vertex counts are contrast shadows — drop them.
- **Calibrate the routing map BEFORE the first document, not during.** Mid-run detector
  fixes cost ~1,236 wasted credits on banchero.
- **Quiet is not stopped.** A run at 30-50s/doc looks idle. Prove liveness from
  advancing state counters, never from `ps`. The user reports "nothing is running" when
  he cannot see progress, so always show PIDs and log timestamps.
- **Long runs must persist partial output.** One 29-minute run died on an HTTP 422 and
  lost everything because it wrote the parquet only at the end.
- **One subprocess per document with a hard timeout** — a segfault should cost one
  document, not the run. Append-only JSONL checkpoint + `--resume`.
- **`max_workers=2`, CPU-only, 8.3 GB RAM.** Do not run two heavy local jobs at once.
- **Emails are banned in this repo** — hard rule, tests enforce zero.
- **Never use `setx`** (truncates PATH at 1024 chars).
- **A 600-dpi pixel re-read matched the vector path to 0.01pt** and settled a disagreement
  the eye could not. That is the final arbiter.

---

## 12. KEY FILE LOCATIONS

**Documents**
```
docs/MASTER_HANDOFF.md                        <- THIS FILE, authoritative
docs/MASTER_EXTRACTION_PLAN.md                <- historical; section 0 has the held-set rule
docs/intermodal_charts_STATE.md               <- intermodal open state + the cloud-spend findings
docs/chart_layer_survey.md                    <- what is real vs what the machine got wrong
docs/lion_verdict.md                          <- read before calling lion incomplete
docs/banchero_cipher_forensics.md
docs/flagged_page_triage.md
docs/xclusiv_charts_PROVEN.md / _ROLLOUT_VERDICT.md
docs/OVERNIGHT_STATE.md
docs/prose_merge_verdict.md
```

**Extractors (per publisher, under `scripts/extract/publishers/`)**
```
run_ssy_charts.py          <- reference extractor, 519/519, 0 credits
merge_ssy_charts.py        <- reference merger, has the agreement gate
run_intermodal_charts.py   <- fixed but NOT re-run
merge_intermodal_charts.py
intermodal_axis_dates.py
run_carriers.py            <- the date-keyed S&P template, 2,866 rows
run_banchero_llamaparse.py <- page-routed resumable cloud runner
run_xclusiv_annual_charts.py / merge_xclusiv_charts.py / test_xclusiv_charts.py
run_intermodal_md.py / intermodal_v2.py
merge_source_charts.py     <- UNTRACKED, produced empty output, DELETE
```

**State files (resume from these)**
```
data/extracted/charts/ssy/_run_state.json              519/519
data/extracted/charts/intermodal/_run_state.json
data/extracted/llamaparse_banchero/_run_state.json      243/243 complete
data/extracted/llamaparse_flagged/_run_state.json       12/12, all with tables
data/derived/ssy_charts_run.log
data/derived/flagged_cloud_run.log
data/derived/flagged_triage.log
data/derived/paid_surface_by_source.json
data/derived/flagged_pages_manifest.json
data/derived/flagged_verdict.json
data/derived/chart_legend_audit.json
data/derived/chart_value_gaps.json
data/derived/outside_brokers_survey.json
data/derived/cloud_vs_local.json
```

**Series**
```
data/extracted/series/ssy_capesize_index_series.csv         CLOSED
data/extracted/series/intermodal_baltic_tc_series.csv      OPEN, 58.2%
data/extracted/series/*_chart_series.csv                   7 EMPTY FILES, delete
```

---

## 13. A NOTE TO THE NEXT AGENT

The user has been patient through a long session but has repeatedly had to correct the
same class of mistake: **building something we already have, or trusting an instrument
that had not been verified.** He has said so directly, and he is right to. When you
report status, report what is **verified**, and where something is not finished, say so
plainly rather than rounding up — he treats a false "done" much more seriously than an
honest "open".

He wants proof of liveness, not reassurance. He reads the master document and will notice
if it drifts from the artefacts. **Update this document in the same commit as any result
it describes.**
