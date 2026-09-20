# 00 — GUARDRAILS (MANDATORY PREAMBLE FOR EVERY PROMPT)

> **This file is prepended to every task in this series. Read it fully before every phase.
> If any instruction in a task prompt conflicts with this file, THIS FILE WINS.**

---

## 0.1 The one rule that matters

**You may never invent a number.**

This repository has already been damaged by fabricated data that was presented as
authentic. A previous agent transcribed values off a chart *image* into a Python
dictionary, labelled it "UN Comtrade HS 260600 + Port of Kamsar AIS water flows", and
wrote a validation function that computed a cross-check, logged it, threw it away, and
returned the hardcoded numbers unchanged. That data is currently rendered in the UI as
real market data.

You are being asked to fix that class of problem, not repeat it.

**If you cannot source a number, the correct output is an explicit absence.** Write
`null`. Emit a row with `status: "UNAVAILABLE"`. Render "no data" in the UI. Report it in
your ledger. All of these are correct. Inventing a plausible value is the single worst
thing you can do in this codebase, and it is worse than failing the task.

---

## 0.2 Forbidden patterns

These patterns are banned. A phase containing any of them is a failed phase, regardless
of how much else works.

### F1 — Hardcoded observation data
```python
# BANNED
HISTORICAL_KT = {2024: {1: 9600.0, 2: 10100.0, ...}}
```
The same ban covers **every shape**, not only year-keyed dicts:
```python
# ALSO BANNED — caught in Prompt 13 (Pilbara), shipped as "live_ppa_archive"
MONTHLY_UPDATES = [{"date": "2026-07-01", "total_mt": 45.0, ...}, ...]
# ALSO BANNED — a constant stamped onto every row
row["top_destination_1"] = "India (~25-28%)"
```
A network call elsewhere in the file does **not** make literal data legitimate.

Hardcoding is permitted **only** for genuinely static reference metadata: port
coordinates, UN/LOCODE mappings, vessel-class DWT bands, great-circle distances,
contract tick sizes. Anything that varies with time or is *observed* must be fetched
or read from a fetched file.

### F2 — Silent fallback to a literal
```python
# BANNED
except Exception:
    return {}                      # caller then falls back to a hardcoded dict
value = live.get(k) or HARDCODED[k]

# BANNED
'diverted_pct': computed if computed else -73.1
```
If a fetch fails, the pipeline **fails loudly** and the affected series is marked
`UNAVAILABLE`. It does not quietly substitute a literal.

### F3 — Provenance claims you did not verify
Do not write "authentic", "verified", "genuine", "100% real", or name a source in a
docstring unless the code on the line below actually calls that source. If the docstring
says ComexStat, there must be a request to ComexStat.

**Citations are claims too.** A `source_url` you did not fetch, or a `source_quote` that
is not a verbatim substring of that page in its original language, is an F3 violation.
Prompt 13 shipped three Guinea URLs that return 404/403 — the slugs were constructed.
`scripts/verify/check_source_citations.py` enforces this (Prompt 13B §C8.4).

### F4 — Validation theatre
A function named `validate_*`, `calibrate_*`, `verify_*`, or `check_*` must change its
output based on what it computed, or raise. A function that computes a check, logs it,
and returns its input unchanged is banned.

### F5 — Hardcoded timestamps
```python
# BANNED
'generated_at': '2026-09-07'
```
Use `datetime.now(timezone.utc).isoformat()`.

### F6 — Deleting or "fixing" data to make a check pass
Never edit a data file so a test passes. Never drop rows to remove an outlier. Quarantine
and report instead.

This includes **reference files** and **real rows that fail a citation check**. In 13B,
two made-up codes were added to `baltic_route_taxonomy.json` so labels would pass, and 18
real Guinea rows were deleted as "no data on page" when the page plainly held them — the
quotes were wrong, not the data. When a check fails on real data, fix the citation.

### F7 — Synthesized observations
```python
# BANNED — found rendering on the Tracking tab (build_geospatial_tracker.py)
status_hash = zlib.crc32(f"{imo}_{locode}".encode()) % 100
status = "Waiting at anchor" if status_hash < 40 else "Operating at berth"
```
A hash, seed, `random`, or "simulation" is never an observation — whatever you call it,
"deterministic" or "realistic". If a field wasn't observed, it's empty or the view doesn't
exist.

**Never weaken a test that guards against fabrication.** If an anti-fabrication test fails,
the data is presumed guilty. 13C removed `port_lineups_active` from a banned list, calling it
"authentic Signal Ocean data"; it was CRC32-synthesized. Loosening such a test needs proof that
the data is observed, and the proof goes in the ledger.

**Absence needs an attempt log.** Any `UNAVAILABLE` or "left absent" must name the §0.66
rungs tried and what each returned. "Honestly ends at 2024-05" with no attempt is not honest.

---

## 0.3 Provenance is mandatory

Every dataset this project renders must have a registered provenance record. Create and
maintain `data/provenance/manifest.json`. Every series gets one entry:

```json
{
  "series_id": "guinea_bauxite_exports_monthly",
  "display_name": "Guinea Bauxite Exports (Monthly)",
  "status": "LIVE | STALE | UNAVAILABLE | ESTIMATED",
  "source_name": "UN Comtrade",
  "source_url": "https://comtradeapi.un.org/data/v1/get/C/M/HS",
  "fetch_method": "REST API",
  "fetch_script": "scripts/acquire/fetch_guinea_bauxite.py",
  "output_file": "data/commodities/guinea_bauxite_exports.csv",
  "row_count": 116,
  "date_span": ["2017-01-01", "2026-08-01"],
  "last_fetched_utc": "2026-09-10T14:02:11Z",
  "unit": "kt",
  "is_derived": false,
  "derivation": null,
  "notes": ""
}
```

Rules:
- `status: "ESTIMATED"` requires a non-empty `derivation` explaining the method **and**
  the UI must show an "EST." badge wherever that series is plotted.
- `is_derived: true` requires `derivation` naming every input series_id.
- A series with no provenance entry **must not be rendered**.

---

## 0.4 The execution ledger — how you prove what you did

Before you begin, create `docs/megaprompts/LEDGER-<phase>.md` (e.g. `LEDGER-03-signals.md`).

**Append an entry after every discrete step.** Not at the end — as you go.

```markdown
## STEP 3.4 — Move Bollinger Bands module to Signals
- STATUS: DONE | PARTIAL | SKIPPED | BLOCKED
- FILES TOUCHED: index.html (lines ~18400-18520)
- WHAT I DID: moved the module markup + its renderer fn; rebound to bdiy_historical.csv
- VERIFY COMMAND: `grep -n "renderBollinger" index.html`
- EXPECTED RESULT: exactly 1 definition, inside the tab-signals panel
- ACTUAL RESULT: 1 definition at line 18402  ✔
- DEVIATIONS: none
```

Rules for the ledger:
- **`SKIPPED` and `BLOCKED` are acceptable outcomes. Concealing them is not.**
  If you skip something, say so and say why. You will not be penalised for an honest
  skip. You will be caught on a concealed one — every claim in this ledger will be
  re-run during the verification phase.
- Every step needs a `VERIFY COMMAND` that a third party can run to check your claim.
- If `ACTUAL RESULT` does not match `EXPECTED RESULT`, write it down anyway and mark
  `PARTIAL`.

---

## 0.5 Phase discipline and when to stop — REVISED 2026-09-10

Each prompt is divided into numbered PHASES / TARGETS.

**After each phase, always:**
1. Append the ledger entries for that phase.
2. Run the phase's verification block **and the global gate below**.
3. Commit, staging only files you created or modified. Never `git add -A`.

**Then — run straight on to the next phase within the same prompt.** Stop only at a
**prompt boundary**, or on a **hard stop condition** below.

This replaces the earlier "stop after every phase" rule. The stops were there to catch
fabrication; that job now belongs to the machine gate, which is faster and stricter than a
human reading a summary.

### The global gate — must pass before every commit

```bash
python scripts/verify/check_no_fabrication.py          # must exit 0
python -m pytest tests/ -q                              # must be green — the WHOLE suite
python tests/test_phase8_regression_and_design.py       # 12 tabs, 0 console errors
```
**The whole suite, not a chosen subset.** Through Round 1 and Prompts 13/13B, only
hand-picked test files were run while `pytest tests/ -q` sat at 24 failures, and every
ledger said "gates pass". The boundary-report generator now runs the gate itself.
Plus, for any phase touching data:
- every series you touched has a provenance entry with computed `data_through`
- **taxonomy coherence** — see §0.55

### HARD STOP conditions — halt and report immediately

Stop mid-prompt, without finishing the phase, if any of these occur:
1. The global gate fails and you cannot fix it **within the same phase**.
2. You are about to delete or overwrite data you did not create in this phase.
3. A source returns data that **contradicts** a figure quoted in the prompt (e.g. a row
   count or a value materially different from what the prompt states). That is a finding,
   and the specification may be wrong — do not paper over it.
4. You cannot source a number and a downstream module depends on it.
5. You are about to write a label, class, unit or route code **you cannot evidence**.
   Hedge it explicitly (`Unverified …`, `mislabelled …`) and flag it — never guess quietly.
6. Two authoritative sources disagree and you cannot determine which is right.

### What "done" means at a prompt boundary
Print: phases completed · gate results · every HARD STOP hit and how it was resolved ·
everything you hedged or could not evidence · files changed. **Then stop and wait.**

**Every number in the boundary report comes from `scripts/verify/generate_boundary_report.py`,
pasted verbatim.** You may add prose around it. You may not type a number, a table, a row
count or a date span by hand. The Prompt 13 report contained a 34-row tsId table that
existed nowhere in the repo and contradicted the agent's own ledger; this rule exists
because of it. If the script does not compute something you want to show, extend the script.

**Allowlist entries are `path:line:rule`, never a bare path.** Exempting a whole file makes
every future violation in it invisible.

---

## 0.55 Taxonomy coherence — every code must match its own definition

Any label carrying an official route/contract code (`C3`, `P1A_82`, `S4B`, `TD3C`,
`TC2_37`, …) **must** be validated against `data/reference/baltic_route_taxonomy.json`:
the code's description in that file must be consistent with the words in your label.

Add this as a permanent test. It is not optional, and it is exactly the class of error a
human skim will miss:

> **Worked example of the failure it catches.** Target 1A labelled tsId 120132
> *"Supramax Transatlantic RV Delivery Cont **(S1B)**"*. But the taxonomy the same task had
> just scraped defines **S1B = "Canakkale trip via Med or Bl Sea to China-South Korea"** —
> a Med/Black Sea fronthaul, not a transatlantic round voyage. The correct code is **S4B**
> ("Skaw-Passero trip to US Gulf" = delivered Continent). And tsId 120133, labelled
> *"Delivery USG (S4B)"*, should be **S4A** ("US Gulf trip to Skaw-Passero"). The codes were
> shifted by one, the unit tests passed anyway, and nothing caught it.

A code whose description does not support the label is a **HARD STOP condition 5**: hedge
it or leave it uncoded. Never attach a plausible-looking code to make a header look
complete.

---

## 0.6 No regressions

Tabs **DASHBOARD, YEARLY, SEASONALITY, INDICES, ETFS, INTELLIGENCE, OFFSHORE** are
working and are **out of scope**. Do not restructure them. You may only touch them where
a prompt explicitly says so (e.g. the global type scale in Phase 1).

Before finishing any phase, confirm:
- every tab still switches
- no new console errors (`refreshVisibleCharts` already throws one known
  `Cannot read properties of undefined (reading 'label')` — do not add more, and fix that
  one if your phase touches its code path)
- no data file that was previously rendering has stopped rendering

---

## 0.65 Every number in these prompts is a snapshot — re-verify it

All row counts, date spans and file sizes quoted across prompts 01–09 were measured on
**2026-09-10**. Harvesters run daily; several of these files grow every day. Some numbers
quoted in `docs/AUDIT_UNRENDERED_DATA_SOURCES.md` and
`docs/MARITIME_INTELLIGENCE_MASTER_DISCOVERY.md` were already stale when those documents
were written.

Known drift found while writing these prompts, as examples of the problem:
- `port_lineups_active.csv` — audit doc says 740 hulls / 40 ports; actual on 2026-09-10 is
  **1,568 rows / 36 ports**
- `gibson_tanker_rates_continuous_daily.csv` — doc says 1,495 days; actual **1,568 rows**
- `signal_map_ports_*.json` — doc implies four lists of 118/113/73/150; they are actually
  **four copies of the same 2,752 rows** differing only in a per-row `zoomIndex` weight

Therefore:
1. **Treat every quoted figure as an approximate expectation, not a fact.** Measure the
   real file at build time and record what you found in the ledger.
2. **Never hardcode a row count, port count or vessel count into the UI.** Compute it from
   the data at build time. A tab that says "221 Ports" in static text is wrong the moment
   the harvester adds one.
3. If your measurement differs materially from the prompt's figure, **that is a finding —
   write it in the ledger.** It is not a reason to stop.

---

## 0.66 Scraping escalation ladder — work the gate before declaring defeat

A 403, an empty body, or a "navigation denied" is **step 1 of 8**, not an answer. Climb the
ladder in order and record the rung reached for every target in your ledger.

**Rung 1 — Real headers.** Full browser header set, not just a User-Agent: `Accept`,
`Accept-Language`, `Accept-Encoding`, `Referer` from the site's own domain, `Sec-Fetch-*`.
Many WAFs pass on headers alone.

**Rung 2 — The asset, not the page.** HTML pages are gated far more often than the files
they link to. Go straight for the `.pdf` / `.xlsx` / `.csv` / `.json`. If the listing page
is 403 but you can guess the file path, try the file.

**Rung 3 — Embedded state in the HTML.** Modern sites ship their data inside the document.
Fetch the raw HTML and grep for:
`__NEXT_DATA__` · `window.__INITIAL_STATE__` · `window.__NUXT__` · `self.__wrap` ·
`<script type="application/json">` · `application/ld+json`
The full dataset is often sitting in one JSON blob with no API call needed.

**Rung 4 — DevTools network inspection. ★ the highest-yield technique, use it.**
Open the page in a real browser with DevTools → **Network**, filter to **Fetch/XHR**,
reload, and read what the page calls to populate itself. Then:
- **Right-click the request → Copy as cURL** and replay it from Python/`requests`.
- Strip headers one at a time to find the minimum set that still returns 200.
- Look at the query parameters: limits, date ranges, page sizes. **Raise them.**
  *(This exact move is what unlocked Fearnpulse — `last=260` was a limit we set ourselves;
  removing it returned 27 years instead of one.)*
- Check for a **paging cursor** and loop it to dump the whole dataset.

**Rung 5 — Documented API surface.** Try `/api/docs`, `/api/v1`, `/api/v2`, `/swagger.json`,
`/openapi.json`, `robots.txt`, `sitemap.xml`. `robots.txt` frequently names paths the site
would rather you not enumerate — which is also a map of what exists.

**Rung 6 — Mirrors and republishers.** Trade press reprints official releases within days,
usually unprotected. For any government or association release, search the headline figure
and take it from whoever republished it — with `source_url` and `publisher` recorded.

**Rung 7 — Wayback Machine.** `http://archive.org/wayback/available?url=…` and
`https://web.archive.org/web/{timestamp}/{url}`. Works on pages now gated, and is the
standard route to historical snapshots of a page that only shows "latest".

**Rung 8 — Ask the operator for a screenshot.** Only after 1–7. Say precisely what you need
(see below). A screenshot of a rendered table is a legitimate input **for structure and for
validating a scraper** — it is *never* a substitute for the data itself.

> ⚠ **The hard line, and it is the whole reason this project exists.**
> A screenshot may be used to (a) learn a page's structure, (b) find the API behind it, or
> (c) sanity-check that a scraper's output matches what a human sees. **Numbers must never
> be transcribed from a screenshot into a data file.** That is precisely how
> `GUINEA_BAUXITE_HISTORICAL_KT` was created — *"Image 2 green line"* — and it was ~8% wrong.
> If you find yourself typing a number you read off an image, stop and go back to rung 4.

### What to ask the operator for
When you reach rung 8, ask for one of these specifically — vague requests waste their time:
1. **DevTools → Network → Fetch/XHR**, page reloaded, so the data call is visible.
2. **The response preview** of the one request that carries the data.
3. **Copy as cURL** of that request, pasted as text.
4. The **rendered page** where you need structure, not values.

---

## 0.7 Environment facts

- The site is **one static file**, `index.html` (~2.8 MB), served by GitHub Pages.
  No backend, no server-side rendering. Any "API" is a static file fetch.
- Python pipelines live in `scripts/` and `bunker_pipeline/`, run by GitHub Actions.
- Data lives under `data/`. **436 files exist; only 84 are wired into the frontend.**
- The repo is a git worktree setup. Commit on the current branch; do not force-push.
- Chart library is Chart.js. Map library is Leaflet.
- **Never commit a file over 90 MB.** If a build artifact exceeds it, shard it.

---

## 0.8 Definition of done for any phase

- [ ] Every step in the phase has a ledger entry with a working VERIFY COMMAND
- [ ] `python scripts/verify/check_no_fabrication.py` passes (built in Phase 1)
- [ ] `data/provenance/manifest.json` updated for every series touched
- [ ] No forbidden pattern F1–F6 introduced (grep proofs in ledger)
- [ ] No regression per §0.6
- [ ] Committed
- [ ] Summary printed and **STOPPED**
