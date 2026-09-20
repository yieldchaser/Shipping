# PROMPT 01 — FOUNDATION: INTEGRITY SYSTEM, VIEW BUILD, DESIGN SYSTEM

> Read `docs/megaprompts/00-GUARDRAILS.md` first. It governs this task.
> Ledger file for this task: `docs/megaprompts/LEDGER-01-foundation.md`

This phase builds nothing user-visible except typography. It builds the machinery that
makes every later phase verifiable. Do it first and do it completely.

---

## PHASE 1.1 — Fabrication detector

Create `scripts/verify/check_no_fabrication.py`. It scans the repo and **exits non-zero**
on any violation. It must detect:

1. **F1 hardcoded series** — any dict literal in `scripts/` or `bunker_pipeline/` with
   ≥8 numeric values keyed by year or month. Allowlist file:
   `scripts/verify/fabrication_allowlist.txt` (one path + reason per line, for genuine
   static reference data like port coordinates).
2. **F2 silent fallback** — regex for `except` blocks that `return {}` / `return None` /
   `pass` where the caller then uses `or <LITERAL>`; and any `X if X else <numeric literal>`.
3. **F3 unverified provenance** — any docstring containing `authentic|verified|genuine|
   100% real|raw published` in a file that makes no network call.
4. **F5 hardcoded timestamps** — `'generated_at'` / `'as_of'` / `'last_updated'` assigned a
   string literal that looks like a date.
5. **Orphan series** — any file under `data/` that `index.html` fetches but which has no
   entry in `data/provenance/manifest.json`.

Output a table: `VIOLATION | FILE | LINE | SNIPPET`.

Run it now. **Record the full baseline violation list in the ledger.** Expect hits in at
least `scripts/analysis/generate_trade_envelopes.py`,
`scripts/geospatial/build_chokepoint_cache.py`,
`scripts/scrapers/generate_ton_mile_matrix.py`,
`bunker_pipeline/extractors/bunkerindex_forward.py`.

Do **not** fix them yet. Phase 02 does that.

---

## PHASE 1.2 — Provenance registry

1. Create `data/provenance/manifest.json` with the schema in GUARDRAILS §0.3.
2. Create `scripts/verify/build_provenance_manifest.py` which:
   - parses `index.html` for every fetched data path
   - cross-references `scripts/` to find which script writes each file
   - reads each file for row count and date span
   - emits entries with `status: "UNREGISTERED"` for anything it cannot attribute
3. Run it. **Every one of the ~84 currently-fetched files gets an entry.**
4. In the ledger, list every file that came back `UNREGISTERED` — these are files the
   frontend loads that no script in the repo produces. That list is important; do not
   silently resolve it.

There is an existing good model to copy: `scripts/etf_provenance_registry.py` enforces
`proxy_allowed: False` and `synthetic_fill_used: False` per contract. Read it. Match its
rigour. Do not duplicate it — the new manifest is repo-wide, that one stays ETF-specific.

---

## PHASE 1.3 — The `data/views/` build layer

**Problem being solved:** the page currently transfers **80.1 MB across 129 requests** on
load. `data/congestion/port_calls_daily_expanded.csv` is **56.5 MB** for only 8 months of
data (2026-01-01 → 2026-08-28, 495,600 rows, 30 columns) and is parsed in the browser on
every visit. There are 96 Chart.js canvases and 16,838 DOM nodes, all initialised on load.
We are about to wire up 350 more data files. Without this layer, every improvement makes
the site slower.

Build a three-tier loading model.

### Tier 1 — view manifests
Create `scripts/build_views.py`. For each frontend view it pre-aggregates **only the rows
and columns that view actually plots** into one small JSON under `data/views/`.

Rules:
- Target **≤ 250 KB per view manifest**. If a view exceeds it, that view is asking for too
  much and must paginate or aggregate further — report it, don't silently ship 2 MB.
- Round floats to the precision actually displayed (usually 2 dp). This alone typically
  halves payload.
- Every manifest embeds a header: `{"series_id":..., "source":..., "as_of":...,
  "row_count":..., "status":...}` read from the provenance manifest. **The UI renders the
  as-of date from this header** — no more hardcoded "generated_at".
- Deterministic output: same inputs ⇒ byte-identical file, so git diffs stay clean.

### Tier 2 — lazy per-tab loading
`index.html` must not fetch a tab's data until that tab is first opened. Cache after first
open. Chart.js instances for a tab are constructed on first open, not at page load.

### Tier 3 — drill-down only
Raw large CSVs are fetched **only** on an explicit drill-down (user clicks a port, a
vessel, a contract). Never on load.

### Acceptance
- Initial load transfer **≤ 2.5 MB**
- `loadEventEnd` **≤ 1200 ms** on localhost
- Canvases initialised at load **≤ 12**
- Every tab still renders identical content once opened

Record before/after numbers for all four metrics in the ledger. Get them with:
```js
const n=performance.getEntriesByType('navigation')[0];
const r=performance.getEntriesByType('resource');
({mb:(r.reduce((a,x)=>a+(x.transferSize||0),0)/1048576).toFixed(1),
  load:Math.round(n.loadEventEnd), reqs:r.length,
  canvases:document.querySelectorAll('canvas').length,
  dom:document.querySelectorAll('*').length})
```

### Also fix in this phase
- `port_calls_daily_expanded.csv` — 30 columns for 8 months at 56 MB. Determine which
  columns the UI uses, and emit a view manifest with only those. Keep the raw file on disk
  for drill-down; stop loading it on boot.
- **Mixed date formats.** `data/futures/sgx_cape_futures_history.csv` (and its panamax /
  supramax / handysize siblings) contain both ISO `2018-01-19` and DD-MM-YYYY `08-09-2026`
  in the same date column. Normalise **all** date columns repo-wide to ISO `YYYY-MM-DD` in
  the view build. Report the count of rows repaired per file. **Do not edit the raw source
  files** — normalise on read.
- `data/commodities/usda_fas_outstanding_export_sales.csv` is unsorted (first row
  2026-08-27, last 1999-09-02). Sort on read.

---

## PHASE 1.4 — Design system

The current UI reads as unpolished for measurable reasons. Fix them globally.

### Typography — the biggest single problem
Measured across Signals + Tracking + Bunkers: **64.1% of all text is under 11px.**
2,080 elements at 9px, 496 at 10px, 1,252 at 11px, only 210 at 12px or larger.
Everything is the same size, so nothing is emphasised and the eye has no entry point.
Density without hierarchy reads as clutter, not sophistication.

Define CSS custom properties and apply repo-wide:

| Token | Size | Use |
|---|---|---|
| `--fs-micro` | 11px | table cells, chip labels, axis ticks — **hard floor, nothing smaller** |
| `--fs-body` | 13px | body text, tooltips, descriptions |
| `--fs-label` | 12px | field labels, column headers (uppercase, letterspaced) |
| `--fs-subhead` | 15px | card titles |
| `--fs-section` | 20px | section headings |
| `--fs-hero` | 32px | primary KPI numbers |
| `--fs-hero-lg` | 44px | the single headline number on a tab |

**No font-size below 11px may remain anywhere.** Verify:
```js
[...document.querySelectorAll('*')].filter(e=>e.innerText&&!e.children.length&&parseFloat(getComputedStyle(e).fontSize)<11).length
// must be 0
```

### Layout — kill the twin-pane whitespace bug
Both Tracking and Bunkers use fixed-height sibling panes locked to each other:
```
tracking-workstation 1360x1283 → left-pane 560x1283, right-pane 784x1283
  chokepoint-dir-list  h=700  content=2500   ← clipped, 546px dead space below
bunkers-workstation   1360x807 → left-pane 500x807, right-pane 844x807
  bunkers-table-wrap   h=660  content=2764
  bunkers-chart-drawer h=411                 ← 396px dead space
```
Replace with CSS Grid where each pane sizes to its own content, with independent internal
scroll regions. **No pane may have more than 48px of trailing empty space.** Verify by
measuring `scrollHeight - lastChild.offsetBottom` per pane and recording it.

### Other global fixes
- Replace **Unicode block-character sparklines** (`▁▁▁▁▁███▆▆▇▇`) with real inline SVG
  sparklines. They currently appear as text glyphs in table columns.
- Add an outlier guard on all price tables. Currently rendering Civitavecchia VLSFO at
  `$275.00` and Djibouti MGO at `$2175.00` with no flag.
- Standardise every status badge on the **Series Museum** pattern, which is already the
  best thing in the codebase and must become the house standard:
  `ACTIVE | BULK | Panamax (75 000 dwt) | TC · usd · 681m | 1970-01→2026-09 | P88`
  i.e. status, family, name, unit, observation count, exact span, completeness percentile.

---

## PHASE 1.5 — Tooltip system

Current state: **1,908 rich tooltips + 2,353 `title` attributes.** Quality varies wildly —
Broker Desk averages 159 chars and explains methodology; Tracking averages 46 chars across
2,216 and mostly explains our own rendering pipeline.

**The gold standard is the INTELLIGENCE tab.** Study its tooltips before writing any.
They answer three beats in ~85 characters: *what it is → where it came from → what it
means for you.*

Build one shared tooltip component. Rules, to be enforced in every later phase:

1. **Every plotted number, axis, badge, chip and control gets a tooltip.** A new user must
   be able to explore the entire terminal from hover alone.
2. **Three beats, 60–160 characters:** what the number is → its source and span → why it
   matters to a dry bulk / tanker trader.
3. **Never describe the UI.** Delete every "re-renders from cache" / "switches this
   section's view/parameter". Nobody cares about our rendering pipeline.
4. **Never put a data caveat in a tooltip.** These currently exist and must move onto the
   axis, the series badge, or the empty state:
   - `"Δ source: month-over-month VLSFO change (fallback, not a 7-day reading)"` ×9
   - `"null — no verified indication (never 0-filled)"` ×10
   - `"No monthly history"` ×10
   - `"PortWatch does not publish LNG port calls."` — on an LNG filter chip that exists anyway
   A tooltip is opt-in; a data gap is a fact about the chart. **Design around the gap, do
   not apologise for it in hover text.** If PortWatch has no LNG calls, either remove the
   chip or label it "fixtures only" on its face.
5. **Provenance is mandatory** — source + as-of date in every data tooltip, pulled from the
   view manifest header. This is now a fabrication control, not a nicety.

Deliverable this phase: the component + the written standard at
`docs/TOOLTIP_STANDARD.md`. The rewrite of all existing tooltips happens per-tab in
Phases 03–07.

---

## PHASE 1.6 — Commit and stop

```
git add -A
git commit -m "feat(foundation): provenance registry, fabrication detector, data/views build layer, design system

- scripts/verify/check_no_fabrication.py: detects F1-F6 forbidden patterns
- data/provenance/manifest.json: per-series source, span, status
- scripts/build_views.py: pre-aggregated view manifests, <=250KB each
- design tokens: 11px floor, 7-step scale; grid panes replace fixed-height twins
- tooltip component + docs/TOOLTIP_STANDARD.md

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Then STOP.** Print:
- baseline fabrication violations found (full list)
- before/after load metrics (4 numbers)
- count of files still `UNREGISTERED` in provenance
- count of elements still under 11px (must be 0)
