# MASTER EXTRACTION PLAN - maritime knowledge base

**Read this file first. It is the single source of truth for the PDF extraction
programme, and it is written so that ANY agent can pick it up and continue without
being briefed.**

Last updated: 2026-09-24 13:15 IST
Repo: `C:/Users/Dell/Github/Shipping` — work on branch `benchmark/extraction-comparison`,
**never touch `main`**.

---

## 1. THE GOAL (what "done" means for a source)

For every broker source, the knowledge base should hold, for every document:

1. **Text** — faithful prose, complete, nothing dropped.
2. **Tables** — structured table values, correctly labelled (a wrong label is worse
   than a missing one: never assign a label by row order or regex match order, only by
   geometry or exact-vocabulary match).
3. **Chart values** — the plotted series estimated as numbers, because a chart is data
   we currently hold nowhere.

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

### How many are DONE PROPERLY END-TO-END?

**5 of 11 sources with output, by content audit** (`scripts/tools/audit_completeness.py`,
which checks markdown is non-trivial *per source*, tables contain real rows, and chart
JSON contains a real series of >= 3 points):

| verdict | sources |
|---|---|
| **END-TO-END (text + tables + chart values)** | **advanced_shipping, affinity, fearnleys, star_asia, xclusiv** |
| PARTIAL | agora, ssy (chart values only), ism (tables), banchero_costa (in flight) |

**Two known audit limitations, stated so the count is not over-trusted:**
* The audit looks for `*table*.json` sidecars. **lion** stores its tables as **parquet**
  (`lion_deals.parquet`, `lion_demometer.parquet`) and is therefore reported as having no
  tables when it is in fact COMPLETE and verified (`docs/lion_verdict.md`). Treating the
  audit as gospel would wrongly condemn it.
* `fearnleys_cleaned` is an intermediate copy of `fearnleys`, not a separate source —
  do not count it twice.

**Caveats stated honestly:**
* **xclusiv** is marked end-to-end because its 265 `.charts.json` files exist and are
  non-empty — but those are the *local* chart extractions. The richer LlamaParse TCE
  series (5 series x ~6 years, validated against page prose) exists only for 2 test
  documents so far. See section 9.
* **fearnleys** is deliberately SKIPPED for data (Hasura API already ingests it) — it is
  listed complete on its own terms, not as a priority.
* **ssy** was briefly reported as "0/519 text" — that was the AUDITOR's bad fixed
  byte-threshold, not a real gap. Verified by reading a file: 1,384 bytes holding a
  10-row table + calculated index + T/C rates. ssy is 1 page/doc, so small is correct.
  Only its chart values are outstanding.
* Corpus groups outside 01-brokers (03-breakwave 18,566 · 08-baltic 3,038 ·
  06-drewry 829 · 07-signal 2,400 · 09-ppa 493 · 02-hellenic 14,130) are **not** covered
  by this audit and are a separate programme.

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
| agora | 213 | 213 | PARTIAL: no chart values. 5 flagged pages. Needs chart work. |
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
* The user rotates across ~5 free Google accounts, 10,000 credits each. **Treat keys as
  burnable** — rotate rather than reuse.
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
