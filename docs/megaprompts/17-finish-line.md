# 17 — FINISH LINE (continuous run)

**Read `00-GUARDRAILS.md` first.** This prompt replaces the unrun Prompts 15 and 16 as the
thing you execute; those two files stay as **detailed sub-specs** that phases below point
to. Work queue: **`docs/megaprompts/QUEUE-17.md`** (already written — every item, in order).

---

## How this run works — read this twice

### You run until the queue is empty
Do not stop at phase boundaries. Do not stop to report. Stop only when:
1. every item in `QUEUE-17.md` is `DONE` or `BLOCKED`, **and** the full gate is green, or
2. a §0.5 HARD STOP occurs.

If your context gets long, that's fine: the queue file *is* your memory. Re-read it, find
the first `TODO`, continue. Commit after each phase (stage only your own files; never
`git add -A`; never push — the operator audits and pushes).

### Proof comes from tests you write first, not from your report
**Phase 0 builds the proof machinery before any fix.** Each test is specified exactly
below. On the current code they **must fail**; record each one's failure count in the
queue as the baseline. Then the whole run is: make them pass without weakening them.

- **Test files are frozen after the Phase 0 commit.** `git diff <phase0-commit> -- tests/`
  at the end must show only *additions* (new test files or new cases), never a loosened
  assertion, a removed case or a widened allowlist without a queue line saying why.
  The operator runs exactly this diff.
- **Allowlists** (`data/reference/*_allowlist.json`) hold one entry per exception, each
  with a reason. Every entry is audited. An allowlist that grows during the run is the
  first thing checked.

### How to write the queue (token budget)
One line per item, updated in place:
```
Q-012 | DONE | tests/test_loader_contracts.py::sgx → pass | restored row.price mapping from 253691965:index.html L16636
Q-031 | BLOCKED | NQBP 403 Cloudflare; tried requests, headless, Wayback CDX (0 snapshots)
```
No prose paragraphs. No pasted logs. The proof is the named test passing, and it's
re-runnable. Screenshots only where an item says so.

### Never
- type a number, percentage, date span or row count into `index.html` markup or prose
- delete or hide a module to make a test pass. A module whose data genuinely doesn't exist
  gets an allowlist entry with the reason and a proper empty state
- invent a column mapping. Read the file's header, or restore the pre-Round-1 code

---

## PHASE 0 — Build the proof machinery (commit before any fix)

| Test | What it asserts | Baseline (measured 2026-09-11) |
|---|---|---|
| `tests/test_loader_contracts.py` | For every `fetchCSV` / `safeFetch` / `fetchCSVChunked` / `fetch(...json)` in `index.html`, every field the mapping code reads (`row.x`, `row['x']`, `r.x`) exists in that file's header, or is listed with a reason in `data/reference/loader_field_allowlist.json` (true aliases/fallbacks only). Static parse; no browser needed. | **~30 of 46 CSV loaders fail** |
| `tests/test_no_empty_modules.py` (Playwright, headed Chrome, 1920×1080) | Mount each of the 12 tabs, wait for network idle + 2 s. No *visible* element's text matches: `not available`, `Loading...`, `Insufficient`, `cache unavailable`, `No data`, `awaiting`, a KPI whose value is `—` or `-`, or an empty canvas (all pixels one colour). Exceptions only via `data/reference/allowed_empty_modules.json` (module id + reason + manifest `series_id` showing DORMANT/UNAVAILABLE). | fails on Signals (SGX FFA, SGX iron ore, lead-lag, ETF z-score), Broker Desk overview, and more |
| `tests/test_ui_copy_lint.py` (Playwright) | Visible `innerText` of every mounted tab (not tooltips) contains none of the banned internal terms (list in Phase 3). Allowlist `data/reference/copy_allowlist.json` by element id. | ~25 distinct terms present |
| `tests/test_design_lint.py` | `index.html` and injected JS strings contain none of: `border-left: [2-6]px solid <non-neutral colour>` on cards/boxes; `box-shadow: 0 0 Npx <colour>` glows; `backdrop-filter: blur`; emoji / dingbat characters; `-webkit-background-clip: text`. | 13 / 30 / 12 / 11 / 0 |
| `tests/test_layout.py` (Playwright) | At 1366×768 **and** 1920×1080: (a) the tab bar's `scrollWidth ≤ clientWidth` — every tab visible; (b) in every two-column row, the shorter column is ≥ 60% of the taller (catches Tracking's empty left column); (c) no element's text is clipped by `overflow:hidden` with an ellipsis on a tab label. | (a) fails: 1,491 px of tabs in 1,400 px |
| `tests/test_perf_budget.py` | Prompt 16 Part A acceptance — headed Chrome, "Fast 4G" throttling. | ETFs 2.1 s per revisit, Tracking 18.7 MB CSV |
| `tests/test_tooltip_coverage.py` | Prompt 16 Part B acceptance, ≥ 95% per tab after mount. | 61% of static controls |

Queue items Q-001 … Q-007. **Commit as `test(phase0): proof machinery (expected to fail)`**
and record the commit hash at the top of the queue file.

---

## PHASE 1 — Restore every blank module (highest user impact)

**Root cause, verified:** Round 1's foundation commit `d21185f31` rewrote the data loaders
with guessed column names. Before it, the page read the files' real columns — for SGX,
`row.price` (`git show 253691965:index.html`, around line 6873 and the `sgxFiles` block at
~16636) — so SGX curves and ~30 other modules have rendered empty since Round 1 went live.
**The data itself is intact** (e.g. `sgx_cape_futures.csv` now ~9,175 rows, collected daily
since March, appended every night by the collector).

For every loader failing `test_loader_contracts.py`:
1. Read the file's real header.
2. If the pre-Round-1 `index.html` (`253691965`) had a working mapping for that file,
   restore its logic. Cite the old line in the queue.
3. Otherwise map from the header. Where the file is **long format** (e.g.
   `australia_ppa_iron_ore.csv`: `port` + `iron_ore_exports_mt`; `brazil_comexstat_exports.csv`:
   `commodity` + `metric_tonnes`), pivot it in code — don't invent wide columns.

Known specifics:
- SGX futures (7 files): `settlement` → `price`. SGX iron-ore curve
  (`data/commodities/sgx_iron_ore_forward_curve.csv`): `fef_settle` / `m65f_settle` / …
- Broker Desk Overview "cache unavailable": `renderFearnOverview` (`index.html` ~47935)
  reads `cache.meta.labels_cached` etc. Make it match the real structure of the file it
  loads.
- Signals: lead-lag "Insufficient overlapping data", ETF premium/discount z-score stuck on
  "Loading…". Trace both to their inputs.

Done when `test_loader_contracts.py` and `test_no_empty_modules.py` pass. Screenshot the
Signals tab and the Broker Desk overview.

---

## PHASE 2 — Everything updates itself (deadline: before 2026-09-17)

Execute **Prompt 15 Part A exactly** (11 unscheduled fetchers; `usda_weekly.yml` overwriting
the rebuilt USDA queue file; `generate_stable_imo()`; incremental Fearnleys refresh;
`monthly_trade_flows.yml`).

Plus **Braemar**:
- `data/clarksons/braemar_live_rates.json` was captured **once** (10 Sep) and never
  refreshed, yet it's labelled "Live GraphQL Feed". The endpoint
  (`POST https://api.braemarscreen.com/api/graphql`, query `homepageMarkets`) is live and
  **does update daily**: Cape Sep was $53,250 on 10 Sep and $51,250 on 11 Sep.
- Write `scripts/scrapers/fetch_braemar_strip.py` (appends a dated snapshot to
  `data/clarksons/braemar_strip_history.csv`). Schedule it daily after London close
  (≈ 17:45 UTC).
- **Intraday test:** a temporary workflow polls every 30 minutes, 07:00–17:30 UTC, for one
  London trading day. If `price` ever differs from `prevClose` intraday, it's a live mark;
  if not, it's a daily close. Record which in the queue and label it accordingly
  ("Braemar close · 11 Sep"). Delete the temporary workflow afterwards.
- It's not the same as SGX: Cape Sep 10 Sep — Braemar $53,250 vs SGX settlement $51,829.
  Show it **once**, on Broker Desk → Overview, with an SGX comparison column. Remove it
  from every other Broker Desk sub-tab.

---

## PHASE 3 — The dashboard speaks to a trader, not to us

Visible text must never describe *how we got the data* or *our internal checks*. That
belongs in a tooltip, in plain words, if anywhere.

**Banned in visible text** (the `test_ui_copy_lint.py` list): unauthenticated · GraphQL ·
Hasura · API · cache · pipeline · harvest · scrape/scraper/scraping · reverse-engineer ·
fixture-grounded · canonical · taxonomy (alignment/audit) · audit · disclosure · "data
reality" · honest · fabricat* · synthetic · quarantine · operator · "network inspection" ·
pending · "editorial estimate" · "computed from the chart's own series" · "no external
lookup" · "zero ton-mile sliders" · "Rule:" lines · all-caps status pills (LIVE OFFICIAL,
LIVE HARBOR MASTER, LIVE MIRROR STATISTIC, LIVE SUPPLY REGISTRY, LIVE MULTIPLES, LIVE 5Y
ENVELOPES, ACTIVE REROUTING, AUDIT DISCLOSURE, UNCLASSIFIED BUCKET, HIGH COVERAGE) ·
count badges next to titles ("15 Active Pricing Modules", "540,640 BROKER FIXTURES",
"40 TENORS", "7 TRADE BASINS", "98% GLOBAL OUTPUT", "182.8 MT ANNUAL RECORD").

The Intelligence tab's "API key stored in your browser" setting is a real user feature:
allowlist that element.

**Replacement pattern** for every module footer:
`Source: <publisher> · through <data_through>` — one muted line, from the manifest.
STALE → amber text with age; DORMANT → red. (That's Prompt 15 Part B2's provenance line.)

Specific rewrites:
- **Commodity Flow Matrix** (Cargo): delete the "Fixture Data Reality … 53.2% Unclassified
  … AUDIT DISCLOSURE" block. Column "Canonical Commodity" → "Commodity". The unclassified
  row becomes an ordinary last row: "Not specified in fixture", with a tooltip. Delete the
  "Primary Trade Corridor" column — it reads "Unspecified Origin → Unspecified Destination"
  on almost every row. Delete the "Coverage Status" badges.
  **Fix the volume column**: `total_qty_mt` sums only fixtures that report a quantity (grain:
  50,132 fixtures → 2.6 Mt ≈ 52 t per fixture — impossible for a bulk fixture). Show
  *fixtures with quantity reported* and the *median parcel size*, and drop parcels outside
  1,000 t–450,000 t (dry) as unparseable. "Other Minor Cargoes 3,269.6 Mt" is a unit error:
  find it.
- Delete the "Signal Ocean Taxonomy Audit: National Customs Series vs Fixture Coverage" block.
- Braemar header text ("Unauthenticated broker forward curve · …", "Live GraphQL Feed") →
  "Braemar forward FFA · close <date>".
- `"Source: … (Fearnleys Hasura monthly). Frozen-state display…"` → the standard provenance line.

---

## PHASE 4 — Numbers that are wrong or typed

1. **`data/derived/chokepoint_transit_metrics.csv` is hand-typed.** No script builds it, it's
   unregistered in the manifest, and Bab-el-Mandeb and Suez carry identical
   `avg_rerouting_voyage_days_added = 14.5` and `implied_tonne_mile_expansion_pct = 28.4`.
   These drive Tracking's "Cape voyage delay +14.5 days" and "Tonne-mile expansion +28.4%" KPIs.
   - **Cape delay**: compute it from real distances. `data/geospatial/signal_distance_ports.json`
     or great-circle via waypoints for a stated reference voyage (e.g. Singapore → Rotterdam via
     Suez vs via the Cape) at a stated speed. Show the formula in the tooltip.
   - **Tonne-mile expansion**: no source → remove it.
   - `daily_transit_count` must come from PortWatch (it already feeds the 7D rate, 25.4/day),
     not the CSV's 14.2.
   - Build the file from a script, register it, or delete it.
2. **Bab el-Mandeb detail box says "52.8 transits/day (+53.9% vs baseline)"** while the KPI
   beside it says −51.9%. Fix the calculation and add a test: current / baseline − 1 must
   agree between the box and the KPI.
3. **Milestone text "adding an editorial estimate of about +14.5 days"** — delete; use the
   computed number from item 1.
4. **Baltic route codes on screen.** Wherever a route series is shown (Broker Desk dry and
   tanker routes, TC rates, Fearnleys series, Signals FFA), append the official code as a
   small muted suffix ("Tubarão → Qingdao · C3") **only** when
   `data/reference/fearnleys_tsid_registry.json` has confidence `verified` or `inferred` (or,
   for other feeds, when its route text matches `baltic_route_taxonomy.json` word for word).
   The tooltip shows the official Baltic description. Timecharter baskets are named as
   baskets: C5TC, P5TC/P4TC, S10TC, H7TC. **Never guess a code.** Anything without evidence
   gets no code.

---

## PHASE 5 — Layout and design

1. **Tab bar**: rename "Cargo & Trade Flows" → **"Cargo"** and tighten tab padding so all 12
   tabs fit at 1366 px (`test_layout.py` (a)).
2. **Tracking — rebuild the layout on the Signal Ocean pattern** (`Inspiration/Screenshot
   (9232).png`, `(9248).png`). Today it has an empty left column under a small chart, map
   chips cramped over the map, and a long right column. Target:
   - A full-height workspace under the tab bar, with **no page scroll for the primary view at
     1920×1080**. Left panel 440–480 px: a compact filter row (sector · window · search) and
     sub-views as tabs (Ports · Port calls · Chokepoints · Disruptions · Vessels) that render
     **inside the left panel**. The map fills the rest and reacts to the selection.
   - Details (a port's call history, a chokepoint's transit series) open **in the left panel or
     a drawer under the map**, not as new full-width sections that leave a column empty.
   - Sector filter chips move from floating over the map into the filter row. Legend: small,
     bottom-left.
   - KPI strip: one row, at most 6, value + one short label each.
   - Milestones: a plain table (dates · event · source link), no cards.
   - Screenshot at 1920×1080 and 1366×768.
3. **Design lint to zero** — Prompt 16 Part C. Reference style: Kpler's chart
   (`Inspiration/HN-0BL4awAAh6c5.jpg`) — neutral grey 5-year band, one accent line, thin
   gridlines, a control panel on the left, no decoration.
4. **Empty space**: `test_layout.py` (b) ≥ 60% column balance. Also no card with a fixed
   height and a short body.

---

## PHASE 6 — Speed and tooltips
Execute **Prompt 16 Parts A and B exactly**. Tracking's 18.7 MB voyage CSV and the double
`port_stress_summary.json` fetch are fixed here if Phase 5 hasn't already.

## PHASE 7 — Complete and current data
Execute **Prompt 15 Parts B, C and D exactly** (August 2026 pulls; GACC tonnes; JODI; EIA LNG;
TradeStat; ABS; coverage matrix), rendering each into the redesigned layout.

## PHASE 8 — Final gate
- `pytest tests/ -q` (all, including Phase 0 tests) · detector · citations — all green.
- `git diff <phase0-commit> -- tests/` shows additions only.
- Screenshots of all 12 tabs at 1920×1080 → `docs/screenshots/17/`.
- Last line of `QUEUE-17.md`: counts of DONE / BLOCKED, and the final commit hash.
