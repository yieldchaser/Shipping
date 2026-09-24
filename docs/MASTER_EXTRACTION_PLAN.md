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

### Measured paid surface
**RE-MEASURING with a calibrated detector — see the warning below before trusting any
number here.** `data/derived/paid_surface_by_source.json` is authoritative once the
current scan completes.

```
banchero_costa   1074 of 3753 pages (28.6%)   <- CONFIRMED real: LlamaParse recovered
                                                 the values 13/13 where the text layer
                                                 read `!"#$#%&`
affinity           27 of  334 pages  (8.1%)   <- pending re-measure
agora               0 of 1071 pages  (0.0%)   <- pending re-measure
clarksons           0 of   35 pages  (0.0%)   <- pending re-measure
lion                1 of  148 pages  (0.7%)   <- pending re-measure
advanced_shipping 807 of 2456 pages (32.9%)   <- ** WRONG, FALSE POSITIVES **
carriers          127 of  386 pages (32.9%)   <- ** SUSPECT, likely false positives **
```

> **WARNING — the first detector was BROKEN and its numbers must not be reused.**
> It flagged any span that was punctuation-dense with no lowercase, so it fired on
> ordinary table headers like `± (%)` and `± ($)`. That reported a 32.9% paid surface
> for advanced_shipping — whose pages render perfectly (verified by rendering page 1
> and looking: clean prose, BDI 1.501/1.460, Capesize 18,608).
>
> `scripts/tools/calibrate_cipher_detector.py` now calibrates the instrument against
> KNOWN-CIPHERED pages (banchero W03) **and** KNOWN-CLEAN pages before any reading is
> trusted. The fixed rule requires: no whitespace, length >= 6, and >= 2 strong markers
> `!"#$&*`. Calibration: banchero detected (recall kept), advanced_shipping and agora
> zero false positives.
>
> **Lesson:** a check that surprises you is a check to verify first. A broken detector
> condemns correct work — this one nearly caused a needless 807-page cloud spend.

---

## 4. SOURCE INVENTORY AND STATUS

`docs` = PDFs in corpus. `.md` = local extraction present. Run
`python3 scripts/tools/measure_paid_surface.py` for current flag counts.

| source | docs | local .md | status / next action |
|---|---|---|---|
| advanced_shipping | 249 | 249 | **the benchmark source.** .md + tables + calibrated charts. Known defects: 221 tables with chart-axis runs merged, 237 with page banner as header, Ship Recycling table merges Gaddani+Turkey. Control test with LlamaParse owed. |
| star_asia | 193 | 193 | 3,640 tables, ISO numbers, charts RASTER. Re-verify charts. |
| ssy | 519 | 519 | 5,920 route rows, 1 page/doc, **two-column page**. Charts outstanding. |
| xclusiv | 266 | 266 | prose clean. **Charts now proven recoverable** (45 cr/page) — 5 TCE series x ~6 years. Roll out across all docs once verified on more years. |
| fearnleys | 257 | 257 | **SKIP — redundant.** Hasura API already ingests their data (comments 11,733 / fixtures 549,480 / SNP 2,643, plus 08-baltic BDI+BDTI). Do not spend here. |
| banchero_costa | 243 | 243 (prose) | **IN FLIGHT** — LlamaParse filling the ciphered tables. See section 8. |
| intermodal | 252 | **0** | Two tables on two pages (12 tanker + 8 dry-bulk fields). Parser exists (`intermodal_v2.py`); build the `.md`. |
| affinity | 250 | 250 | 8.1% pages flagged — triage those pages, don't re-run the source. |
| agora | 213 | 213 | **0.0% flagged — clean.** No spend. Spot-check by eye and close. |
| lion | 44 | **0** | Local tables exist (`lion_deals` 1,145 rows). Build `.md`. |
| ism | 112 | 112 | Complete + verified per OVERNIGHT_STATE. |
| carriers | 129 | **0** | Not yet started. Recon first. |
| clarksons | 10 | 0 | tiny, 0% flagged. Low priority. |
| bancosta / general_broker | 1 each | 0 | singletons, low priority. |
| gibson, allied, anchor, golden_destiny, other | — | — | **STOPPED publishers** (archive/). Backfill only if <180d. |

Total: **15 broker sources, 3,739 PDFs** (plus 03-breakwave 18,566 / 08-baltic 3,038 /
06-drewry 829 / 07-signal 2,400 / 09-ppa 493 in other corpus groups).

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

## 8. CURRENT IN-FLIGHT WORK (check before starting anything)

### banchero_costa LlamaParse run
```bash
tail -5 data/extracted/llamaparse_banchero/run.log
python3 -c "import json;st=json.load(open('data/extracted/llamaparse_banchero/_run_state.json'));print(len(st['done']),'done',len(st['failed']),'failed')"
```
* runner: `scripts/extract/publishers/run_banchero_llamaparse.py --tier cost_effective`
* watchdog: cron `c0400ecf1a0b` every 30m — silent when healthy, restarts if dead
* watchdog source: `scripts/tools/watch_banchero_run.py` (Python, **not** .sh — the
  scheduler runs .sh through WSL bash which has no distro installed here)
* **Do NOT start a second runner** — two concurrent runs double-spend credits.
* When dead: `python3 scripts/tools/watch_banchero_run.py` (resumes, never restarts
  from zero).

### paid-surface scan
`python3 scripts/tools/measure_paid_surface.py` → `data/derived/paid_surface_by_source.json`

---

## 9. NEXT ACTIONS IN ORDER

1. Finish banchero (in flight).
2. **Verify the xclusiv chart extraction across more years** — one document is not a
   corpus. Render the chart, compare against prose, all 5 series, 3+ years.
3. If it holds: roll `specialized_chart_parsing` across xclusiv's chart pages
   (~5 pages x 266 docs = 1,330 pages ≈ 59,850 cr — **must be gated and rationed**;
   prioritise recent years first, most-recent-first).
4. **advanced_shipping control** — 1 doc, the one with the Ship Recycling Gaddani/Turkey
   merge. ~12 cr. Answers whether our benchmark source is actually complete.
5. Triage affinity's 27 flagged pages.
6. Build `.md` for intermodal, lion, carriers.
7. Vision spot-check agora (should take one look).

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
