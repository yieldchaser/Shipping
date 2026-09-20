# 16 — FAST, CLEAN, EXPLAINED

**Read `00-GUARDRAILS.md` first.** Run after Prompt 15. Absorbs Prompt 12 (tooltips +
view layer). Design reference: the `Inspiration/` folder in the repo root (34 screenshots
of Signal Ocean, Kpler, Vortexa, Braemar). Look at them before starting Part C.

---

## What the user sees when this is done

1. **Every tab switch is instant.** No freeze on first open, none on return. Tracking opens
   as fast as the others.
2. **Every number, chart, control and badge has a tooltip**: what it is, source and date,
   why it matters.
3. **No generic-AI design**: no coloured left-border accent cards, no glows, no glass blur,
   no shouting status pills, no emoji. Dense, neutral, professional, like the
   `Inspiration/` references.

---

## PART A — Speed (measured 2026-09-11, local build, all 12 tabs, cold then warm)

| Tab | Cold switch | Warm (return) switch | Cause to investigate |
|---|---|---|---|
| **ETFs** | 1.9 s worst block, 2.5 s of long tasks | **2.1 s click handler every revisit** | re-renders everything on every visit |
| Indices | 0.88 s click handler | 0.18 s | |
| Signals | 0.67 s of long tasks | 0.76 s | |
| Cargo | 0.36 s | | |
| Bunkers | 0.22 s | | |
| Dashboard / Yearly / Seasonality / Broker Desk / Offshore | < 0.15 s | | fine |

**Tracking** measured light in a hidden pane, but that's misleading: its cost is data.
Opening it loads:
- `data/geospatial/voyage_history_fixturegrounded.csv` — **18.7 MB, 354,333 rows**,
  parsed on the main thread
- `data/congestion/portwatch_port_congestion.csv` — 7.8 MB
- `data/derived/port_stress_summary.json` — 1.8 MB, **fetched twice**
- `data/views/signal/vessel_voyages_lookup.json` 1.4 MB, `live_fleet_positions.json` 0.95 MB

And at **boot**, `data/bunkers/bunker_frontend_summary.json` (**4.4 MB**) loads before any
tab is opened. The Round 1 boot budget was 0.22 MB. The session total after visiting all
tabs is **55 MB**.

### Fix
1. **Never re-render a tab whose data hasn't changed.** Render once, cache the DOM and
   charts, and on return only toggle visibility. That fixes ETFs and Signals on revisit.
2. **No raw file over 250 KB is fetched on tab open** (Prompt 12 Part B). Voyage history
   becomes a per-vessel lookup: a small searchable index plus a per-IMO shard fetched when
   a vessel is opened. Congestion and port stress get view manifests of 250 KB or less.
   Remove the duplicate `port_stress_summary.json` fetch.
3. **Boot loads only what the Dashboard shows.** Bunker summary moves to lazy on-open.
4. **Heavy parsing happens off the main thread** (a Web Worker) or ahead of time in the
   build scripts.
5. Shard the lookup tables over 250 KB (Prompt 12's list: `vessel_lookup.json` 5.6 MB etc.).

### Acceptance — measured with real headed Chrome (Playwright), network throttled to "Fast 4G"
- No tab switch (cold) has a long task over **200 ms**; warm switches have none over 50 ms.
- Boot transfer **≤ 0.5 MB**; cumulative transfer after all 12 tabs **≤ 8 MB**.
- Commit `tests/test_perf_budget.py`, which runs this measurement and fails over budget.
  It's part of the gate from now on.
- Ledger: a before/after table with the same columns as above.

---

## PART B — Tooltips (absorbs Prompt 12 Part A)

Measured: 617 of 1,005 static buttons, selects, inputs and table headers carry a tooltip
(61%). Dynamically rendered elements are extra and unmeasured.

1. Standard: three beats, 60–160 characters — **what the number is → source and
   `data_through` → why it matters to a dry-bulk or tanker trader.** No UI mechanics
   ("Click to view…").
2. Coverage **≥ 95% per tab, measured after the tab mounts**: every plotted series, axis,
   legend entry, KPI, badge, chip, filter and control, including dynamically rendered ones.
3. Source and `data_through` come from the manifest at render time, never typed.
4. Fix the SHA-256 hash that leaks into a user-facing tooltip (Prompt 12 §A.1).
5. `tests/test_tooltip_coverage.py` (Playwright): mounts each tab and asserts ≥ 95%.

---

## PART C — Remove generic-AI design

Counted in `index.html` on 2026-09-11:

| Pattern | Count | Replace with |
|---|---|---|
| Coloured left-border accent on cards/boxes (`border-left: 3–6px solid <accent>`) — incl. every "Why this matters for freight" box | 13+ (plus JS-injected) | no side bar; a plain caption in muted text, or a hairline full border |
| Coloured glow `box-shadow: 0 0 Npx <colour>` | 30 | none, or a neutral 1px border |
| Glassmorphism `backdrop-filter: blur` | 12 | solid surface colour |
| All-caps status pills ("LIVE OFFICIAL", "LIVE HARBOR MASTER"…) | 22 | the provenance line from Prompt 15 B2 |
| Emoji / dingbat characters in markup | 11 | remove (13B claimed zero — re-check including JS strings) |
| Gratuitous badges next to titles ("98% GLOBAL OUTPUT", "182.8 MT ANNUAL RECORD", "7 TRADE BASINS") | several | delete; the title says what it is |

House style, from `Inspiration/`: one accent colour used sparingly for the active state
and the current-year line; neutral greys for everything else; 1px hairline borders; tabular
numerals for every figure; compact spacing; sentence-case labels; no decorative icons.

`tests/test_design_lint.py` greps `index.html` **and** the injected JS strings for every
pattern in the table above and fails on any hit. It's part of the gate.

---

## Gate and boundary

Full `pytest tests/ -q` including the three new tests · detector · citation check ·
12-tab regression. Report: the before/after speed table, per-tab tooltip coverage, the
design-lint result, and screenshots of Tracking, ETFs and two Cargo modules.
