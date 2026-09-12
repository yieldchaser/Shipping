# 17 — FINISH LINE (continuous run)

**Read `00-GUARDRAILS.md` first.** Execute this prompt against the work queue
**`docs/megaprompts/QUEUE-17.md`**. Prompts 15 and 16 remain as sub-specs that phases point to.

Four appendices carry the measured evidence. **Read them before Phase 0 — they are the ground truth
for this run, produced by clicking through every tab and reading the live DOM on 2026-09-11/12:**

| Appendix | Contents |
|---|---|
| `17-APPENDIX-A-loader-map.md` | Every broken data loader: real file header, the fields the code wrongly reads, and the pre-Round-1 implementation to restore |
| `17-APPENDIX-B-ui-baseline.md` | Per-tab measured counts and the exact offending items (empty states, dashes, internal wording, pills, accents, glows, clipped text, untipped controls, click failures) |
| `17-APPENDIX-C-freshness-and-wiring.md` | Frozen view layer, 35 unscheduled writers, the USDA workflow that destroys data, hand-typed data files, on-screen data-quality defects |
| `17-APPENDIX-D-design.md` | Design tokens, components, and the Tracking rebuild with a wireframe |

---

## How this run works

### Run until the queue is empty
Do not stop at phase boundaries, do not stop to report. Stop only when every queue item is `DONE`
or `BLOCKED` **and** the full gate is green, or on a §0.5 HARD STOP. The queue file is your memory:
if context runs short, re-read it, find the first `TODO`, continue. Commit after each phase (stage
only your own files, never `git add -A`, never push — the operator audits and pushes).

### Phase 0 writes the tests, and the tests must be at least as strict as the audit
Write the proof machinery **before any fix**. On today's code each test must fail, and
**it must report at least the counts in Appendix B §B1 for every tab**. A test that reports fewer
findings than the appendix is too weak — tighten it until it matches or exceeds, and record the
number it found next to the appendix number in the queue.

- **Test files are frozen after the Phase 0 commit.** At the end, `git diff <phase0-commit> -- tests/`
  must show additions only — never a loosened assertion, a deleted case, or a threshold moved. The
  operator runs exactly that diff.
- **Allowlists** live in `data/reference/ui_test_allowlist.json`, one entry per exception, each with
  a `reason` of at least 15 characters naming why it is legitimate. Entries are audited one by one.
  Start it with only what Appendix B/C marks as legitimate (control labels like "Playback Speed:
  1.0x", "Last 30 days"; the Intelligence tab's own API-key setting; vessel-consumption assumption
  constants; Leaflet canvases).

### Queue economy
One line per item: `Q-012 | DONE | tests/test_ui_tabs.py::test_charts_have_data[signals] → pass |
restored row.price mapping (App A §A0)`. No prose, no pasted logs. Screenshots only where asked.

### Never
- type a number, percentage, date span or row count into `index.html` markup or prose
- delete or hide a module to make a test pass — if data genuinely doesn't exist, give it a real
  empty state and an allowlist entry with the reason
- invent a column mapping — use Appendix A, or the file's real header
- weaken a test, or add an allowlist entry without a reason line in the queue

---

## PHASE 0 — Proof machinery (commit before any fix)

Build with Playwright (already used by `tests/test_phase8_regression_and_design.py`), a session
fixture serving the repo over `http.server`, and one **mount helper** that: opens the tab, waits for
network idle, **scrolls the whole panel top → bottom → top** (five Signals charts only render when
scrolled into view — see Appendix C §C6), then waits 1 s. Every check below runs per tab, and again
for every sub-tab/sub-view (Broker Desk 12, Tracking 5+, Bunkers 5, Cargo 6, ETFs, Signals).

| Test | Fails when |
|---|---|
| `test_loader_contracts.py` (static) | a loader reads a field absent from the file's header (Appendix A). Baseline: **27 loaders + the SGX group** |
| `test_no_console_errors` | any `pageerror`, `console.error`, or a `[stale-guard] … blank canvas(es)` warning (the page's own blank-chart detector) |
| `test_no_failed_requests` | any request ≥ 400 |
| `test_no_empty_states` | visible text matches `not available / Loading… / Insufficient / unavailable / no data / awaiting / NaN / undefined / null / Invalid Date` |
| `test_no_dash_kpis` | a KPI value is `—`, `-`, `n/a`, `NaN`, `$NaN` |
| `test_charts_have_data` | a visible canvas has no Chart instance, or its datasets hold < 2 non-null points (exclude Leaflet via allowlist) |
| `test_ui_copy_lint` | visible text contains an internal term (Phase 3 list), an all-caps status pill, a count badge, a file path (`data/…`, `.json`, `.csv`), `tsid`, or a number with > 4 decimals |
| `test_no_typed_numbers` (static) | markup text outside `<script>` contains a value with a unit (`Mt`, `%`, `$`, `/day`, `days`, `NM`) that isn't an allowlisted control label |
| `test_design_lint` (static + computed) | coloured left-edge accent (border-left ≥ 2 px, non-grey, other borders thinner), `box-shadow: 0 0 …` glow, `backdrop-filter: blur`, emoji/dingbat, gradient text. Baseline: **13 accents / 30+33 glows / 12+4 blurs / 11 emoji** |
| `test_tooltip_coverage` | < 95% of visible controls carry a tooltip, or a tooltip starts with "Click/Toggle/Select/Tap", or is < 20 chars. Baseline: Broker Desk **12/65**, Cargo **5/11**, Intelligence **27/38** |
| `test_layout` | tab bar `scrollWidth > clientWidth` at 1366 **and** 1920 (Offshore is hidden at both today); a panel scrolls horizontally; leaf text is clipped (Bunkers: 20 today); in a two-column row the shorter column < 60% of the taller |
| `test_ui_sweep` | clicking any control raises an error or reveals a new empty state (Appendix B lists today's: Broker Desk "S&P & Assets" → "Loading…", Cargo sub-views → "UNAVAILABLE", …) |
| `test_views_fresh` (static) | a `data/views/*.json` `as_of` is older than the newest date in the source it derives from (today: dashboard 2026-09-09 vs BDI 2026-09-11) |
| `test_workflow_wiring` (static) | a file loaded by `index.html` has no writer script invoked by any workflow or by the `pages.yml` build step (today: 35) |
| `test_single_writer` (static) | two scripts write the same data file (today: `fetch_usda_grains.py` vs `fetch_usda_grain_queues.py`) |
| `test_manifest_matches_files` (static) | manifest `row_count` / `date_span` disagree with the file |
| `test_perf_budget` | boot transfer > 0.5 MB, cumulative over 12 tabs > 8 MB, any cold tab switch with a long task > 200 ms, any warm switch > 50 ms (today: 55 MB, ETFs 2.1 s warm) |

Commit as `test(phase0): proof machinery (expected to fail)` and record the hash in the queue.

---

## PHASE 1 — Nothing on screen is blank or wrong-by-omission

1. **Every loader in Appendix A.** Restore the pre-Round-1 mapping where the appendix shows one;
   otherwise map from the real header. Pivot the long-format files (§A3) rather than inventing wide
   columns. Start with §A0 (SGX, 7 files, `settlement` → `price`) — it alone restores the SGX FFA
   forward curve and the iron-ore term structure, and the underlying data is intact and growing
   daily (~9,175 rows in the cape file).
2. **The eight Signals modules with no chart object** (Appendix C §C6): FFA term structure BDRY and
   BWET, BDI daily-change contribution, lead-lag correlation, ETF premium/discount z-score, ETF fund
   flow signals, plus the two SGX curves from item 1.
3. **Broker Desk**: overview "· cache unavailable" (`renderFearnOverview`, ~47935); TC Rates' five
   `n/a` KPIs; the spot-vs-period chart drawing only one of its three legend series; S&P & Assets'
   two blank charts, four `—` KPIs and stuck "Loading…".
4. **Tracking**: `renderTrackingHUDRefreshNote is not defined`; "awaiting disruptions feed";
   `hudDisruptionsActive = —`.
5. **Cargo**: the HUD tiles must render from data (Phase 4 item 2 removes the typed values).
6. Whatever else `test_no_empty_states`, `test_charts_have_data` and `test_ui_sweep` report.

Done when those four tests pass on every tab **and every sub-view**.

---

## PHASE 2 — It keeps itself up to date (do before 2026-09-17)

Appendix C is the specification. In order:
1. **`pages.yml` build step** (§C1) — every view/cache builder runs at deploy, so what is published
   is built from the newest data. The Dashboard has been frozen at 2026-09-09 since Round 1.
2. **`usda_weekly.yml`** (§C4) — stop `fetch_usda_grains.py` overwriting the rebuilt queue file;
   call `fetch_usda_grain_queues.py`. One writer per file, enforced by `test_single_writer`.
3. **Schedule the 35 unscheduled writers** (§C2) — verify the real writer of each file first; then
   Prompt 15 Part A's `monthly_trade_flows.yml` plus the nightly jobs. `generate_stable_imo()` goes.
4. **Braemar** (§C3) — a daily fetch after the London close appending to a dated history; the
   30-minute intraday probe for one session to settle whether it is a live mark or a daily close;
   label it with what you find; show it once, on Broker Desk → Overview, with an SGX comparison.
5. **Say what is static** — Signal Ocean positions and any other one-time snapshot get a real
   as-of label, not "LIVE FLEET AIS", until something refreshes them.

---

## PHASE 3 — The dashboard speaks to a trader

Banned in visible text (Appendix B lists every instance and where):
unauthenticated · GraphQL · Hasura · API · cache · pipeline · harvest · scrape/scraper · reverse-engineer ·
fixture-grounded · canonical · taxonomy · audit · disclosure · "data reality" · honest · fabricat* ·
synthetic · quarantine · operator · "network inspection" · pending · "editorial estimate" ·
"computed from the chart's own series" · "no external lookup" · "zero ton-mile sliders" · "Rule:" lines ·
file paths and `tsid` · all-caps pills (LIVE OFFICIAL / LIVE HARBOR MASTER / LIVE MIRROR STATISTIC /
LIVE SUPPLY REGISTRY / LIVE MULTIPLES / LIVE 5Y ENVELOPES / LIVE PAIRED / LIVE FLEET AIS /
ACTIVE REROUTING / EST. AUDIT / UNCLASSIFIED BUCKET / HIGH COVERAGE / FROZEN / MODELLED) ·
count badges beside titles (540k Broker Fixtures, 14 Flow Datasets, 40 TENORS, 15 Active Pricing
Modules, 7 TRADE BASINS, 98% GLOBAL OUTPUT, 182.8 MT ANNUAL RECORD).

Replace each module footer with `Source: <publisher> · through <data_through>` from the manifest
(amber when stale, red when dormant). Keep the Intelligence tab's API-key setting (allowlist).
Delete the Cargo "Fixture Data Reality … AUDIT DISCLOSURE" block and the "Signal Ocean Taxonomy
Audit" block; rename "Canonical Commodity" → "Commodity"; the unclassified row becomes
"Not specified in fixture".

---

## PHASE 4 — Numbers that are wrong, typed, or unlabelled

1. **`chokepoint_transit_metrics.csv`** (§C5): build it from a script and register it, or delete it.
   Compute the Cape delay from real distances at a stated speed and show the formula in the tooltip;
   drop the tonne-mile expansion KPI (no source); take the transit count from PortWatch.
2. **Cargo HUD tiles** (§C5): remove every typed number from markup; render from data; if a value
   can't be computed the tile doesn't exist. Today they claim C3 $24.80 / C5 $10.60 while the same
   repo shows C3 $42.12 and C5 $17.85.
3. **"52.8 transits/day (+53.9% vs baseline)"** beside a KPI reading −51.9% — fix the sign and add a
   test that the panel and the KPI agree.
4. **Commodity Flow Matrix volumes** (§C6): report fixtures-with-quantity and median parcel size;
   treat parcels outside 1,000–450,000 t as unparseable; find the "Other Minor Cargoes 3,269.6 Mt"
   unit error; drop the "Unspecified → Unspecified" corridor column.
5. **LNG Desk default series** (§C6): $1,000/day with ATL 0 is broken — choose a defensible default
   and add a per-asset-class plausibility band, reporting (not hiding) anything outside it.
6. **Route identity**: Broker Desk tiles truncate to "SUPRAMAX TRANSATL…" three times over, so S4A
   and S4B are indistinguishable. Show the full route and append the official Baltic code as a muted
   suffix ("US Gulf → Skaw-Passero · S4A") **only** where `fearnleys_tsid_registry.json` says
   `verified`/`inferred`, or where the route text matches `baltic_route_taxonomy.json` exactly.
   Tooltip carries the official description. Never guess a code.
7. Numbers on screen are formatted: no "35.18357925 Mt/mo".

---

## PHASE 5 — Layout and design (Appendix D)

1. Rename the tab to **"Cargo"** and tighten padding until all 12 tabs fit at 1366 px.
2. **Rebuild Tracking** to the §D4 wireframe: KPI strip, filter bar, 460 px left panel with
   sub-views that always have a default selection, map filling the rest, detail drawer under the
   map. No page scroll for the primary view at 1920×1080; left panel must not scroll sideways.
3. Apply §D2/§D3 tokens and components; design lint to zero; fix the 20 clipped Bunkers values and
   the clipped LPG labels.
4. Tooltips to ≥ 95% per tab, three beats, with source and date (Prompt 16 Part B).

## PHASE 6 — Speed
Prompt 16 Part A: ETFs re-rendering on every revisit (2.1 s), Tracking's 18.7 MB voyage CSV, the
duplicated `port_stress_summary.json` fetch, the 4.4 MB bunker summary at boot, 55 MB per session.

## PHASE 7 — Complete and current data
Prompt 15 Parts B–D: August 2026 where published (ComexStat already has it), GACC tonnes, JODI,
EIA LNG, India TradeStat, ABS, and the generated `docs/DATA_COVERAGE.md`.

## PHASE 8 — Final
Full `pytest tests/ -q` green · detector · citations · `git diff <phase0> -- tests/` additions only ·
screenshots of all 12 tabs and every sub-view at 1920×1080 into `docs/screenshots/17/` ·
last queue line: DONE/BLOCKED counts and the final commit hash.
