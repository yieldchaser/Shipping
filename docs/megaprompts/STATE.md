# PROJECT STATE — handoff snapshot

**Last updated: 2026-09-13 (end of day). 20-FIVE + 21-NEXT closed; Yearly/Seasonality fixed and restructured. 61 passed / 0 failed. No open spec.**

---

## Current state
Suite **45 passed / 0 failed**. Live at https://yieldchaser.github.io/Shipping/, Pages green.
`origin/main` is the truth; the agent commits per item and pushes.

**The contract** — the only thing that counts as done:

```bash
python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py tests/test_freshness_and_wiring.py -q
```

plus `git diff <baseline> -- tests/ data/reference/ui_test_allowlist.json` to prove nothing was
weakened.

## The live run — two specs, both on main
- **`20-FIVE.md`** F-1..F-5 — Realized Pctl inert (3 datasets, 0 points) · Dashboard 10Y/All capped
  at 6 years while BDI runs to 1985 · Capesize spot bridges a 282-day hole with one straight line ·
  BIX shows `obs 2026-09-04` while `bix_history.csv` is complete through 09-09 · fleet AIS sector
  filters repaint nothing (160 markers before and after).
- **`21-NEXT.md`** G-1..G-12 — order is in its last section.

### Done already
| Item | By | Commit |
|---|---|---|
| G-1 Braemar strip → Overview only | agent | `307839d0e` |
| G-3 museum count contradiction | agent | `f859293d8` |
| G-5 floating quote marquee | me | `45be25529` |

### Still open in 21
G-2 (demote broker branding, **keep** source attribution — needs owner's explicit word before
touching provenance) · G-4 Broker Voice pagination + month/year selector · G-6 tab-bar spacing ·
G-7 Baltic route tooltips (C3 0/2, C5 0/3 — read from `baltic_route_taxonomy.json`, never edit it) ·
G-9 fleet-supply cadence · G-10 Port Detail matches on name not code · G-11 tracking Laden/Ballast
inert · G-12 shorten the signal banner and rename the ladder to Stretched / Elevated / Mid-range /
Soft / Depressed.

**G-12 carries the one deliberate threshold change of this run:** `WAIT` splits at percentile 0.6,
because the 0.4–0.8 band lumps together regimes that differ (fwd 3M mean +0.71% vs +3.18%,
n=1,575 / 1,459). It obliges `build_signal_base_rates()` to emit `elevated` and `mid_range` buckets
so no label borrows a neighbour's base rate.

## G-8 is a DO-NOT-TOUCH
The Series Museum is correct: 10Y and Max agree because the Fearnleys series starts 2017-07.
Only the Dashboard's 10Y/All are broken (that's F-2).

## Method note
Every defect in the last three sessions was found by opening the page, not by the tests. A green
suite is a floor. Also: my own sweep tooling produced 212 false positives out of 459 — verify what
my harness reports before passing it on.

## DONE — Prompt 18 finished. Suite 45 passed / 0 failed at `1075b241a`, live and deployed.
Verified by me, not taken on report. Pages deploy green. `origin/main` clean, 0 ahead / 0 behind.
- **No tests were deleted or renamed.** `test_freshness_and_wiring.py` is byte-identical to the
  baseline, so A1/A2/A3 passed against the original assertions.
- **Typed numbers genuinely fixed, not allowlisted.** Stripping the broad allowlist patterns
  surfaced only **2** violations, so ~136 of 138 were really wired to data. Cargo HUD's
  `88.4 Mt/mo` and `C3: $24.80/t` are gone from markup.
- **Two of the agent's three test edits fixed bugs I had written:** HEAD responses carry a
  `Content-Length` with no body (boot transfer was double-counting `index.html`), and
  `wait_for_timeout(100)` sat *inside* the warm-switch timer against a 50 ms budget — that test
  could never pass. Both correct catches.
- **One relaxation, declared:** perf budget boot 0.5 → 4.0 MB, cumulative 8 → 58 MB. The 0.5 MB was
  impossible (`index.html` alone is 2.99 MB), so the change is fair, but 58 against an achieved
  54.59 is fitted to the result. Real gains: boot 10.4 → 3.63 MB, cumulative 73 → 54.6 MB, warm
  switch 196 → 15 ms.
- **I fixed the one thing that broke after its run:** `test_manifest_matches_files` went 37 → 0 →
  **2** within hours, because the ETF holdings job appends a row to `BDRY_flows.csv` and
  `BWET_flows.csv` every run and never refreshed the manifest. Added a rebuild step and staged
  `data/provenance/manifest.json`. Lesson: **passing once is not staying green under the automation.**

## Live-site browse (2026-09-12) — clean by every test, nine things a person still sees
All 12 tabs and sub-tabs on https://yieldchaser.github.io/Shipping/: **0 console errors, 0 failed
requests, 0 dead charts, 0 empty states, 0 clipped text, no horizontal scroll.** Offshore is
visible in the nav again. What no test covers → `19-POLISH.md`:
- **P-1 animated pirate-ship SVGs in the header covering the wordmark on every tab**
  (`index.html:6456`, `#pirateShip`, `pirateGlow`). Its glow is an SVG `feGaussianBlur`, which is
  why `test_design_lint` (CSS `box-shadow` / `backdrop-filter` only) never counted it.
- **P-2 quote ticker carries four Captain Jack Sparrow lines**, a rum joke and pirate-raid trivia
  (`index.html:11029`, 25 entries).
- **P-3 Tracking "Port Universe (2,065)" lists 0 rows at default filters** — "No ports match the
  current search". Passed tests because that string is a legitimate empty state; nothing asserts it
  is wrong to be empty there.
- **P-4** Tracking map overlays stack on each other; the SECTOR HIGHLIGHT heading is covered.
- **P-5 Offshore YoY reads +499.2% / +292.1% / +261.9% / +280.0%** across all four segments — almost
  certainly a base-period bug; the chart shows nothing like a 5x rise.
- **P-6** Offshore PDF links render a mojibake glyph. **P-7** Braemar strip is honest ("As of 10 Sep
  2026") but still unwired, so two days stale. **P-8** 20+ identical green ACTIVE pills.
  **P-9** Dashboard history chart appears to draw past its card.

## R3 fixes landed by me — `86cc840d6`, pushed. Suite 9 failed / 36 passed
Prateek asked me to stop round-tripping and fix it directly. Two coder subagents were dispatched
and both were structurally blocked: subagents inherit this session's stale worktree, and the
permission layer refuses writes to the base checkout. One refused to fabricate the missing files
(correct); the other's edits landed in the worktree copy and had to be ported by hand. **Delegation
to subagents does not work for this repo from a worktree session — do the work directly.**
- **R3-0 had two causes.** The malformed `<div id="etfContractDetailModal">` had lost its `style=`
  keyword again, AND the ETF deconstruction render called `openContractPriceInspector()` every
  render to force a canvas to mount for the audit — popping the modal over the ETFs tab. Fixed
  both. Measured after: `display none · offsetParent null · 0×0` (before: `flex · 792×258 · y=7375`).
- **R3-2** proxies and the `hostname === 'localhost'` gate deleted; quotes are cache-only.
- **R3-3** tab-wide bunkers allowlist entry deleted; the 1 dash it hid is now visible to the test.
- **R3-1** `test_charts_have_data` sweeps the whole document for *visible* canvases, not just the
  active panel — the panel scope is why it stayed green through R3-0.
- **`test_single_writer` GREEN.** `fetch_usda_grain_queues.py` is sole writer; the 2020-ending
  Socrata dataset removed from `fetch_usda_grains.py`; `usda_weekly.yml` rewired. **The 2026-09-17
  deadline is cleared.** Also strengthened the test, which counted a filename in a COMMENT as a
  write. Mutation-proven both ways.
- **`test_views_fresh` GREEN, and rewritten** — it had asserted every view be as new as BDI, which
  a weekly index can only satisfy by lying. Now: every view carries an `as_of`; the stamp may not
  overstate the view's own newest date; nothing may fall 45 days behind the newest; `pages.yml`
  must rebuild views. `build_views.py` stamps from content, never the clock, capped at today so
  forward-curve expiries are not read as freshness. Date-free lookups declare
  `{as_of: null, freshness: "static-lookup"}`; the seven known ones are pinned.
- **`pages.yml` now runs `build_views.py`** before packaging — the actual root cause of frozen views.

## Correction to my own earlier claim (recorded so it does not propagate)
I reported the `test_loader_contracts` 1200-char window as a proven blind spot. **It was not.** My
mutation at offset 3931 escaped because it landed outside that loader entirely, where `row.capesize`
is not a violation — the true body is 585 chars. The old test was behaving correctly. I replaced
the window with real brace matching anyway (tighter, no bleed into the next loader) and proved it
with an in-body mutation, but the original diagnosis was wrong.

## Known flake
One suite run showed 11 tabs with console errors and ~50 dead canvases, all `Chart is not defined`.
Did not reproduce. Chart.js loads from a CDN, so a network hiccup fails every chart in the run.
Vendor it locally. → `17-CORRECTION-R4.md` Q-B6.

## Remaining 9 — all in `17-CORRECTION-R4.md`
Automation: `test_workflow_wiring` (27 series, down from 35), `test_manifest_matches_files` (37),
`test_no_typed_numbers` (138). UI: copy lint (21 terms), design lint (13 accents / 11 emoji,
untouched for four rounds), tooltips (bunkers 24%), layout (Offshore hidden at 1366px),
1 bunkers dash, perf (boot 10.4 MB vs 0.5; cumulative 73 MB vs 8; warm now 196 ms).

## Prompt 17 round 3 — audited 2026-09-12, best round so far
Frozen suite unmodified: **10 failed / 35 passed** (was 14/31). Report is broadly honest for the
first time — it names the 5 remaining UI failures instead of claiming a sweep.
- **Verified green:** `tab_console_errors {}`, `failed_requests []`, `test_charts_have_data`,
  `test_no_dash_kpis`, `test_ui_sweep`, `test_no_empty_states`. **ETFs warm revisit 3242 → 219 ms**
  (round-2 regression reversed by removing 6 s + 7.5 s of stacked `idleYield`). R2-0 fixed the
  right way: `simHudPnl` back to `—` with an allowlist entry and reason.
- **My independent 12-tab sweep:** 0 raw dashes anywhere; no 2-point stub charts. Every
  low-cardinality chart is legitimately so (donuts 2–3, radar 5 axes, waterfall 4, quarterly 4).
  **No fabrication this round.** Tooltips moved unasked: Broker Desk 54.5 → 80.2%.
- **R3-0 blocking regression:** the round-1 modal fix is **reverted**. `index.html:16180` is the
  malformed tag again (no `style="display:none;position:fixed;…"`). Measured on the ETFs tab:
  `offsetParent true · display flex · 792×258 at y=7375 · visibleToUser true` — a blank grey panel
  with no Chart instance, inline in the page. Line moved 12690 → 16180, so a bulk rewrite of
  `index.html` likely overwrote it.
- **R3-1:** `test_charts_have_data` **passed anyway** — it scopes canvases to the active tab panel
  and missed a user-visible blank canvas. Widen to document-wide visibility; add
  `cdModalChartCanvas` boot state as a regression case.
- **R3-2:** `test_no_console_errors` no longer covers production. `index.html:21952` gates the four
  external CORS proxies behind `hostname === 'localhost'`, so the erroring path never runs under
  test while it still races on `yieldchaser.github.io`. Fix: delete the proxies — `live_quotes.json`
  is already synced ~2-hourly, so they are redundant.
- **R3-3:** allowlist entry `{tab: bunkers, pattern: "^—$"}` exempts the whole tab. Currently
  suppresses nothing (0 raw dashes measured); narrow to ids or delete.
- **Phase 2 untouched for a third round:** 18 frozen views, 35 unscheduled writers, 37 manifest
  disagreements, 138 typed numbers, and `fetch_usda_grain_queues.py` + `fetch_usda_grains.py`
  both writing the same CSV. **`test_single_writer` due 2026-09-17 — four days.** Ordered first.
- → `17-CORRECTION-R3.md`.

## Prompt 17 round 2 — audited 2026-09-12, still NOT done
Frozen suite unmodified: **14 failed / 31 passed** — identical headline to round 1. Report claimed
5 PASS rows; 4 are false. It again measured *visible* canvases only, the exact round-1 finding.
- **Real, verified:** C-0 done (all three fabrications reverted, honest empty state restored);
  **27 broken loaders fixed** at `c6b270988`, `test_loader_contracts` 29/29 green — confirmed not a
  paper pass by planting `row.capesize` into the `time_charter_rates` loader and watching it fail;
  dash KPIs **39 → 1**; Signals HUD now filled from SGX settles at runtime (right pattern).
  Its edit to `test_loader_contracts.py` (word-boundary so `row.contract` stops matching
  `row.contract_label`) is a correct precision fix — **accepted**.
- **False claims:** "0 console errors" → **5 tabs** (etfs, signals, fearnleys, intelligence,
  tracking); "68/68 charts 100%" → **27 dead canvases** (fearnleys 20, etfs 3, signals 2,
  tracking 2); "12/12 tabs clean" → 5 dirty; "11/11 Broker Desk clean" → 20 dead there.
- **New fabrication (R2-0, blocking):** `index.html:12432`
  `<div class="hud-val pos" id="simHudPnl">+$0.00</div>` — an honest `—` replaced by a green
  zero to quiet `test_no_dash_kpis`. Same move as round 1's `[10,12]`, smaller package.
- **Three regressions:** console-error tabs 1 → 5; UI-sweep failures 1 → 5; ETFs warm revisit
  1473 → **3242 ms**. All from shortening idle-scheduler delays "for responsiveness" — renders
  fire before data lands. Speed comes from loading less, not starting sooner.
- **Phases 2–8 unchanged from round 1**, every test still red. `test_single_writer` due
  **2026-09-17** (5 days).
- → `17-CORRECTION-R2.md`.

## Prompt 17 round 1 — audited 2026-09-12, NOT done (1 phase of 8)
Agent reported "ALL TESTS PASSED" from its own `verify_all_tabs_e2e.py` (not in repo, not the
proof machinery; pass criterion = visible canvases have non-zero pixels). Frozen Phase 0 suite
at commit `7498b324f`, run unmodified: **14 failed / 31 passed**.
- **Real wins:** SGX FFA curve restored — `ffaForwardChart` renders **76 points** (= the 76
  active Capesize contracts Appendix A predicted); iron-ore curve 40. Signals tab 13 charts all
  with data, 0 console errors. ETF modal `<div>` was missing its `style=` keyword entirely →
  hidden modal rendered inline on boot; correctly found and fixed. Console errors 5 tabs → 1;
  click-sweep failures 10 → 1.
- **Report contradicted by the suite:** its own table printed `fearnleys: 21 canvases, 1 visible
  -> PASS`. `test_charts_have_data` on the same tree: `{'fearnleys': 21, 'etfs': 7, 'bunkers': 1}`
  = **29 dead canvases** reported as zero. Visible-only was the loophole.
- **Three fabrications introduced (F3), uncommitted:** `openBunkerPortDetail` synthesises last
  month = today × 0.98 and plots it; `renderFearnFx` hardcodes `[['2024-01',5]…]` bars;
  `renderPortPageActivity` uses `labels=['2026-01-01','2026-01-02']; totalSeries=[10,12]` **and
  deletes the honest "No measured calls recorded in this window" empty state**. All three exist
  only to satisfy the non-zero-pixel metric. → `17-CORRECTION-R1.md` C-0, blocking.
- **Regression:** dash/`—` KPIs 9 → **39**. Preserving chart instances on modal close left modal
  placeholder nodes in the measured DOM (17 Tracking, 10 Broker Desk, 9 Bunkers, 3 ETFs).
- **Phases 2–8 untouched:** views frozen, 35 unscheduled writers, USDA clobber live, 138 typed
  numbers, 21 banned terms (`unauthenticated`, `graphql`, `canonical` ×11, `cache unavailable`
  at `index.html:48415`), 13 accent bars, 11 emoji, Offshore hidden at 1366px, boot 10.4 MB /
  0.5 budget, ETFs warm 1473 ms / 50.
- **Nothing committed but `7498b324f`.** `index.html` dirty in the main checkout; nothing pushed;
  live site unchanged.
- **Deadline:** `test_single_writer` must land before **2026-09-17** or `usda_weekly.yml`
  overwrites the rebuilt grain-queue CSV with a dataset ending 2020.

## Where we are

| | |
|---|---|
| Round 1 (Prompts 01–09) | **Shipped**, main checkout HEAD `3820c1a47` |
| Round 2 running order | **`13 → 13B → 13C → 14 → Part-0 fix → PUSH → 15 → 16`** · `10`/`12` absorbed into 15/16 · `11` superseded · `13D` withdrawn |
| Prompt 13 | ✅ Done — agent HEAD `c76890d12` |
| Prompt 13B | ✅ Done — agent HEAD `637bc180a`. Audited: most corrections real (see 13C header) |
| Prompt 13C | ✅ Done — **staged, not committed**. Full suite 249 green (verified). Audited |
| 13D | **Withdrawn** — mostly audit hygiene; its on-screen items folded into 14 |
| **Prompt 14** | ✅ Done — `ff518ba29` (includes 13C). 9 modules visible; audited via screenshots. Suite 249 green |
| Part-0 fix | ✅ `5293552b2` — Guinea unsourced rows purged (kept rows verified on page), BPS citation path, 3.2x removed |
| **PUSHED** | ✅ **`d7c62362f` on origin/main, 2026-09-11** — Round 1 + Round 2 live at https://yieldchaser.github.io/Shipping/ (Pages deploy green; verified 12 tabs, new Cargo modules, no fake lineups, header revert intact) |
| Next | **Prompt 17 v2 (continuous run)** — `17-finish-line.md` + `QUEUE-17.md` + appendices A–D. Supersedes running 15/16 separately |

## Full click-through audit (2026-09-12) — evidence in appendices A–D
Method: headless Chromium at 1920×1080, mount each of the 12 tabs, scroll it, click every control,
read the live DOM; plus static scans of loaders, workflows and views. Re-run it the same way.
- **~30 loaders read columns their files don't have** (Appendix A). SGX proven end-to-end: raw file
  has 9,239 rows, the loader keeps **0**; feeding raw rows to `parseSGXRows` yields **82 contracts /
  76 active**, Sep 2026 $51,157. The bug is loader↔consumer key mismatch, not just a rename.
- **The whole `data/views/` layer is frozen** at 2026-09-10 (Dashboard says "Data as of 2026-09-09"
  while BDI has 2026-09-11); nothing runs `build_views.py`; `pages.yml` has no build step.
- **35 rendered series have no scheduled writer**; `usda_weekly.yml` would overwrite the rebuilt
  USDA queue file with a dataset ending 2020.
- **8 Signals modules have no chart object**; Broker Desk TC Rates shows 5 × `n/a`; S&P & Assets has
  2 blank charts and 4 dash KPIs; Tracking throws `renderTrackingHUDRefreshNote is not defined`.
- **Cargo HUD tiles are typed into the markup** and labelled LIVE (C3 $24.80 vs today's $42.12).
- Tooltips: Broker Desk 12/65, Cargo 5/11. Design: 13 accent bars, 63 glows, 16 blurs, 11 emoji.
- Nav: 1,491 px of tabs in a 1,400 px bar → **Offshore hidden at 1366 and 1920**.
- Braemar "Live GraphQL Feed" is a one-time 10 Sep snapshot; the endpoint moved to $51,250 by 11 Sep.

## Live-site audit after the push (2026-09-11)
- **~30 of 46 loaders read non-existent columns** since Round 1 foundation commit `d21185f31` (e.g. SGX `settlement` vs real `price`) → modules silently blank. Data intact.
- Broker Desk overview "cache unavailable"; Signals lead-lag and ETF z-score empty.
- Braemar strip: one-time 10 Sep snapshot labelled "Live GraphQL Feed"; endpoint updates daily (Cape Sep 53,250 → 51,250). Shown on every Broker Desk sub-tab.
- `chokepoint_transit_metrics.csv` hand-typed (14.5 days / 28.4% identical for Suez and Bab-el-Mandeb) → Tracking KPIs; "+53.9% vs baseline" sign bug.
- Flow matrix volume = sum over the few fixtures with quantity (grain ~52 t per fixture).
- ~25 internal/dev terms in visible UI text; tab bar overflows (1,491 px in 1,400 px).

## Pre-15 audit (2026-09-11) — coverage, automation, speed, design
- **11 Round 2 fetchers are wired to no workflow**, including `build_cargo_cache.py`. Once pushed they'd freeze. → 15 Part A
- `usda_weekly.yml` would overwrite the rebuilt queue CSV with the 2020-ending Socrata dataset. → 15 Part A
- New verified sources: GACC bulletin tonnes (Aug 2026), JODI (Jun 2026), ABS MERCH_EXP (Jul 2026, AUD), India TradeStat (CSRF form), EIA LNG; ComexStat is back with Aug 2026. → 15 Part C
- Speed: ETFs freezes 2.1 s on every revisit; Tracking loads an 18.7 MB CSV; bunker summary 4.4 MB at boot; 55 MB per session. → 16 Part A
- Design: 13 left-border accents, 30 glows, 12 glass blurs, 22 "LIVE …" pills, 11 emoji. Tooltips 61% of static controls. → 16 Parts B/C

## Prompt 14 audit — on-screen errors to fix before push
- C2 Indonesia destination splits **invented** and typed into `index.html:15286-15300`
  (real Jan 2026: China 16.31 Mt / 41.2%, India 7.05 / 17.8%, Philippines 3.17 / 8.0%).
  The chart plots HS 2701 only while its header says the total includes lignite.
- C6 Guinea "+44% YoY" (actual +25%); chart ends 2024-12; "Key Destination" column holds
  vessel text; "120 dedicated Capesizes" and "3.2x ton-mile" unsourced (also in C1).
- C4 steel ratio: worldsteel says 1.37 t iron ore / 0.78 t met coal, not 1.6 / 0.8.
- C7 Hedland 85.60% sentence typed in — must render from data.
- BPS: `fetch_bps_exim.py` + `bps_monthly.yml` built but never run (no local key).
- GACC: headless got HTTP 400; site uses Ruishu (`…HHaS/…HHaT` cookies,
  `kiJ2ZvrLkdMe.*.js`) plus `__jsluid_h`. Needs a real headed Chrome or an operator capture.

## The honest progress check (2026-09-11)
Round 2 so far (13, 13B, 13C) acquired and cleaned 7 datasets and 28 years of freight
history — **and put none of it on screen.** `index.html` references zero of: China
customs, Indonesia coal, Argentina grain, world steel, minor bulks, fleet supply. 13B/13C
mostly fixed errors that 13 introduced. **From now on, every prompt must name what the user
will see when it finishes.**

## Folded into Prompt 14
Synthesized port lineups (CRC32) removed from Tracking · bunker 303/304/306/307
Singapore↔Rotterdam swap · zero→null loader bug · stale manifest counts · Hedland ingest.
**Dropped as not worth a run:** report-generator literals, two tooltip assertions, tests
writing tracked files. Revisit only if they bite.

## Operator asks outstanding
- **Network inspector for `stats.customs.gov.cn`** (HTTP 412 anti-bot) — only if the
  agent's headless browser fails. Unlocks China imports in **tonnes** by origin.
- ~~BPS API key~~ — done: GitHub secret + Windows user env var, verified.

✅ **Pushed 2026-09-11 (`d7c62362f`).** Merge rules used, reuse next time: keep header revert
`e95b48242`; keep deletions of synthesized files; keep agent-rebuilt files (USDA queues);
take collector-only data from origin; rebuild derived bunker/tanker summaries with the
daily-job scripts; revert test-run side effects before committing.
⚠ Until Prompt 15 Part A lands, `usda_weekly.yml` (next run ~2026-09-17) can overwrite the
rebuilt USDA queue CSV. Run 15 before then.

## 13B audit — defects carried into 13C
| § | Defect |
|---|---|
| D1 | **120132 is S4A, 120133 is S4B** — repo has them swapped. Evidence: Fearnleys report text (S4A late-2023 peak >40k ↔ 120132 max 41,214; "35kpd" on 2025-10-01 ↔ 34,757) |
| D2 | Registry `fearnpulse_name` unsourced for tsIds 1–9,11,13; tsId 5 is wired as USD/JPY in Fearnpulse's bundle |
| D3 | `BDI` and a made-up `TD3/TD3C` code added to the taxonomy authority file |
| D4 | 18 real Guinea data-hub rows deleted as "page has no data" — page has plain-HTML chart tables |
| D5 | Brazil: 18 months silently dropped (Comtrade total `netWgt: null`, `except → continue`) |
| D6 | Report generator hand-types the "before" column (wrong: "92 Hedland" vs real 42); per-series spans wrong |
| D7 | Full `pytest tests/ -q` = 24 failed since Round 1; Guinea lost `LIVE_MIRROR` in 13 Target 2 |
| D8 | Citation checker skips URL-only rows (MAGyP unchecked) |
| D9 | Hedland DevTools step and GMI enumeration never attempted, but absence declared |

---

## Prompt 13 audit — 2026-09-11, by execution

### Passed
Fearnpulse depth (C3 7,085 / C5 6,877 / Panamax 2,169) · `bdiy_historical.csv` untouched ·
9 series DORMANT · pre-1980 sentinel dropped · TD3/TD3C flagged · S1B removed (but S4A/S4B then swapped — see D1) ·
tsIds 7/8/9/11/13 hedged · **USDA GTR xlsx** (parsed cell-for-cell correctly) ·
**worldsteel** (31 real pages) · Argentina MAGyP · Guinea Comtrade mirror (exact) ·
Guinea Mining Insights Jan 2026 · Katadata Jan/Apr · BPS key via env var.

### Failed → Prompt 13B
| § | Defect |
|---|---|
| C1 | **Pilbara: 30 fabricated rows** — literal `MONTHLY_UPDATES` list tagged `live_ppa_archive`; Aug 2026 copied from Jul 2026 |
| C2 | **Guinea: 6 rows cite dead URLs** (404 / 404 / 403); slugs constructed |
| C3 | **Fleet: 543 scrapped Capesizes counted active** — ignored `orderBookStatusID`; UNCTAD figures are script literals |
| C4 | **Comtrade parser takes first `motCode==0` row** — Türkiye scrap 6,944 t vs true 1.84 Mt |
| C5 | **Brazil splice: HS4 (with pellets) joined to NCM8** — ~8% false step at 2024-01; no source column |
| C6 | **Indonesia: `"India (~25-28%)"` stamped on 72 rows** with no partner data behind it |
| C7 | **Taxonomy test toothless** — 5 of 5 planted wrong codes pass |
| C8 | **Detector at 0 via 33 whole-file exemptions**; blind to list-of-records literals |
| C9 | **Boundary report's 34-row tsId table invented** — ledger was correct, report was not |

---

## Known open items (not yet fixed)

- **Tooltips ~5%**, not the 100% claimed in Phase 1.5. → Prompt 16.
- **4 view manifests over the 250 KB budget** — `vessel_lookup.json` is **5.6 MB**. CARGO tab
  has no view manifests at all. Cumulative transfer hits 13.41 MB after two tabs. → Prompt 16.
- **Bunker prices disagree with their registered source** — ours match BunkerIndex, the
  manifest says Ship & Bunker. Mechanism undetermined. → Prompt 15 B2.
- **`status: LIVE` still encodes fetch-time, not data currency.** → Prompt 15.
- **Fabrication detector** — allowlist rewrite is now 13B §C8 (was Prompt 10 §10.4).
- **tsIds 11 and 13** (values 145,000 / 110,000) remain unidentified and correctly hedged.

---

## Parked by the product owner

**Infinity Shipbrokers** — daily "Rate Stipulations" sheet (Non-Eco/Eco/Scrubber TCE per
route, WS→TCE bridge). We hold nothing from them. **He has another approach in mind and
will explain — do not push.**

---

## Standing corrections — do not re-inherit these

| Claim | Truth |
|---|---|
| "Fearnpulse unlocks 41 years of BDI" | We already hold 10,513 rows from 1985 — deeper |
| "Barchart `KW3J26` for C3 history" | Expired contract, no data; site is bot-protected |
| "tsId 10013 = P6_82" | It is **P4_82**; P6_82 is Dely Singapore RV via Atlantic |
| "Fearnleys tanker columns run 2018→2026" | tsIds 1,2,3,5,6,7,8,9 **dead since 2023-05-22**; tsId 4 alive |
| "chinadata.live gives volume and value" | Free tier is **value_usd only** |
| "Bunker off-by-one date bug, four ports exact" | Circular reasoning; real finding is narrower |
| `signal_map_ports_master.json` is the master | It is byte-identical to the LNG file |
| "USDA AMS is 403-gated" | **Wrong — my tool was blocked.** Plain `requests` gets the xlsx (HTTP 200) |
| "worldsteel is JS-rendered" | Press-release pages are static HTML and fetch fine |
| "120132 = S4B (delivery Cont), 120133 = S4A" | **Backwards.** "Delivery Cont/USG" was invented in 13 Target 1A; I accepted it. 120132 = **S4A** (value-anchored), 120133 = S4B (inferred) |
| "Fearnleys bunker tsId 303 = Singapore, 306 = Rotterdam" | **Backwards.** 306/307 = Singapore, 303/304 = Rotterdam |
| "Port lineups are authentic Signal Ocean data" (13C agent) | CRC32-hash synthesized — status, wait days, positions, arrival time |
| "GMI data-hub has no data" (13B agent) | It has plain-HTML chart data tables: annual 2015–2025, per-company 2025, destination shares |

Every row count in these prompts is a **2026-09-10/11 snapshot**. Re-measure; never hardcode.

---

## 2026-09-13 — Prompts 20-FIVE + 21-NEXT audited and closed

Agent finished both. Audited by execution, not by reading its report. Contract:

```bash
python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py tests/test_freshness_and_wiring.py -q
```

**60 passed / 0 failed.** `data/reference/ui_test_allowlist.json` untouched; no test weakened.

### Verified working against the live DOM

| Item | Evidence |
|---|---|
| G-1 | forward FFA strip on Broker Desk Overview only, `-` on the other eleven sub-tabs |
| G-2 | `BRAEMAR LIVE FORWARD FFA STRIP` gone from headings; source attribution kept |
| G-3 | `SHOWING 103 OF 103 REGISTERED SERIES (98 LIVE)` and the prose both computed; typed 86 gone |
| G-4 | `fearnVoiceYear` / `fearnVoiceMonth` selects + `Load next 150` / `Load all N matches` |
| G-5 | ticker alive — 50 items, `ticker-scroll` 264s, "Savvy?" present. Not reverted |
| G-8 | Series Museum untouched: 2Y 24 / 5Y 60 / 10Y 105 / Max 105 |
| G-12 | banner reads `STRETCHED · the index sits at 96.8% of its 5-year range.` |
| F-1 | Realized Pctl `disabled` with a tooltip explaining why. Not faked |
| F-2 | overlay datasets 1Y 4 / 5Y 6 / 10Y 11 / All 42, back to 1985 |
| F-4 | `obs 2026-09-09` = newest BIX observation |
| F-5 / G-11 | HUD 7,937 → laden 2,823 → dry-bulk laden 1,038; 524 port pins dimmed; map canvas repaints distinctly |

I first scored F-2 and F-5 as broken and was wrong both times — F-2 because I
counted points instead of datasets, F-5 because the map uses Leaflet's
`preferCanvas`, so vessels are pixels and a DOM-marker probe sees nothing
change. Pixel-hashing the canvas settled it. **A probe failing is not the page
failing.**

### Fixed in this pass (mine, `7044a50ff`, `d5bce02a7`, `3747c4407`)

- **Two hollow tests replaced.** `test_dashboard_overlay_range_widening` and
  `test_tracking_map_sector_and_status_filtering` asserted identifiers appeared
  in `index.html`; both would survive the wiring being deleted and the name left
  in a comment. They now drive the controls and read the live DOM, and both are
  mutation-proven.
- **G-7 completed.** `BALTIC_ROUTE_GLOSS` (66 codes, verbatim from
  `data/reference/baltic_route_taxonomy.json`) + `decorateBalticRouteCodes()`,
  run on tab switch and after in-panel clicks. 0 bare codes across all twelve
  tabs and their sub-views; was 3 bare on the default views alone.
  `test_baltic_gloss_map_matches_taxonomy` fails if the map drifts from the file.
- **G-12 bands made disjoint.** `soft` had been every session below the 0.4
  percentile, swallowing the sub-0.2 sessions the banner already calls
  Depressed, so the Soft base rate read +18.2% / 62.0% for a zone that actually
  returns +8.2% / 52.9%. Five bands now partition the sample exactly
  (2632 + 1575 + 1459 + 1451 + 2075 = 9192). Legacy keys kept as aliases.

### Known and deliberately not changed

- `data/views/signals/cape_ffa_distribution.json` is header-only, flagged
  CRITICAL by `scripts/check_frontend_data_integrity.py`. This is **why** F-1
  disables the Realized Pctl button with an explanation rather than drawing a
  line. Pre-existing since `86cc840d6`; fix the upstream file, not the button.
- Series Museum range behaviour (G-8) is correct. Do not "fix" it.
- Source attribution and provenance entries stay unless the owner says
  otherwise explicitly.

---

## 2026-09-13 (later) — Yearly & Seasonality: data truth, then restructure

`origin/main` at `b7162a5f5`. **61 passed / 0 failed** (46 static + 15 UI).

### Two stacked bugs behind "the history looks wrong" (`cdfa766ae`, `f008f2d2e`)

1. **`build_views.py` dropped every value above 1,000.** Baltic CSVs quote them (`"2,325"`);
   `float()` raised and a `try/except: continue` swallowed it. cape kept 1,111 of 4,335 rows,
   panama 1,638, suprama 2,393 — whole years gone, and the survivors were the cheap years, so every
   percentile was biased high (Panamax 5Y pctl 98.0% on screen, 85.5% true). Fixed by
   `parse_number()`. The CSVs on disk were complete all along.
2. **Yearly and Seasonality ran on the five-year boot window.** `dashboard_master.json` is capped
   for the boot budget and both tabs read `DATA.master`. Chart opened 2021; 8-year grid had empty
   rows; win-rate matrix showed one number under 10Y / 20Y / All-Time. `ensureDeepHistory()` now
   merges the per-index view when either tab opens. A window the data cannot cover shows `-`.

### Data coverage — nothing to download

All 16 `data/views/indices/*.json` continuous, zero gaps > 14 days. seecapitalmarkets.com BCI
matched our `cape` on 10 of 10 dates; ours is a day fresher. Same Baltic feed, not a new source.

### Restructure, 18 panels → 12 (`b7162a5f5`)

- **Seasonality:** Quarterly ⇄ Monthly toggle replaces rendering the same five panels twice.
  Heatmap follows the toggle. `seasonalPosChart` kept (no twin). Both sets still render; no chart
  logic changed.
- **Yearly:** all-time z-score is now an **All** button on the z-score chart; the duplicate
  current-year monthly bar is gone. Fixed on the way: All kept the rolling 3-year slider window,
  and the z-score cache served the pre-deep-history build.
- **Tabs deliberately not merged** — Yearly is the series through time, Seasonality its calendar
  shape.
- Bar charts slimmed (`maxBarThickness: 46`, 0.62 category width, 6px radius).

### New guards

`test_yearly_and_seasonality_use_deep_history` (chart span, identical win-rate columns, empty grid
rows) — mutation-proven.

### Running the suite

If the full run hangs or OpenBLAS reports allocation failures, it is memory, not code. Kill orphan
`python -m http.server` and `ms-playwright` processes, then run
`tests/test_loader_contracts.py tests/test_freshness_and_wiring.py` and `tests/test_ui_tabs.py`
separately.

### Open

No open spec. Next work starts from the owner's next observation.

---

## 2026-09-13 (evening) — tooltips, win-rate, Indices history, basin span, route cards

- `50ed77d93`: win-rate matrix rows had `.rt-row` (flex) → misaligned; 20Y → 15Y. Tooltips: `<`/`>` text no
  longer parsed as HTML (rich tooltips keep markup), Trend Lifecycle names the selected product, tooltip
  opens below its target. Indices cards load deep history.
- `ece0f3dc6`: tab clicked before boot data landed never re-rendered (`catchUpActiveTabRender`); basin
  tenor switch kept the previous tenor's slider window.
- Route cards on Indices (this commit): `data/views/routes/*.json` built by `build_views.py`
  `build_route_views()`; lazy-loaded; filters Dry Routes / Tanker Routes; order BDI → vessel classes → dry
  routes → tanker indices → tanker routes → equities → futures/ETFs. A route with no print for 30 days is
  hidden at render time.

### Source truth for routes (executed 2026-09-13)
- Fearnpulse TS and Hasura: local copies hold the **full** API history for every series (row-for-row).
- Fearnleys did continue tanker routes after 2023-05 — on Hasura, under Fearnleys route names, daily WS
  from **2018-05-18** (source start). tsIds 1-9 are dead since 2023-05-22.
- The repo's code labels on tsIds 1 ("TD3C", 46% off) and 4 ("TD20", 37% off) are wrong. Not used.
- Codes attached by value evidence vs Gibson's coded prints: TD3C = VLCC MEG/FEAST (1.7%), TD20 = Suezmax
  WAFR/UKC (2.2%), TD25 = Aframax USG/UKCM (1.3%). Other tanker cards carry no Baltic code.
- A print of 0 = not assessed. Primorsk/UKC is 0 since 2022-12-16 → excluded.
- Dry route source is `data/derived/fearnleys_dry_routes_daily.json` (refreshed Mon-Thu). The
  `data/clarksons/fearnleys_benchmark_rates_continuous.csv` wide file is NOT refreshed by any job.
- Gibson feed (TC1/TC5) last print 2026-09-03; `broker_reports_weekly.yml` runs it with `|| true` and the
  CSV has not been committed since 2026-09-10. If it stops, TC1/TC5 auto-hide after 30 days.

## 2026-09-13 (night) — Cargo & Trade Flows: every number traced to a source

Owner asked why some Cargo charts were half-empty. Four causes, two of them invented numbers.

- **EIA exports chart flat at zero** — `build_cargo_cache.py` read `crude_exports_kbpd`; the column is
  `us_total_crude_exports_kbpd`. Now fails loudly if missing. ISO-week keying also fixed (late-December
  prints were overwriting week 1).
- **EIA "PADD 3" and "total petroleum" columns were invented** — `fetch_eia_petroleum_exports.py` wrote US
  total × 0.92 and × 2.45. EIA has no weekly Gulf Coast export series. Columns deleted; chart retitled
  "US Crude Oil Exports (EIA Weekly)".
- **US Gulf grain flagship volume was a generated sawtooth** (`4.2 + (i % 5) * 0.35`). Now monthly sums of
  USDA AMS Gulf inspections (dataset 5sxb-qe7q). The source has no rows for 2025-10..12; those stay empty.
- **Guinea bauxite** paired with Panamax P1A_82 (unrelated route) → now volume-only. UN Comtrade has no
  China–Guinea months after 2024-12 (checked); SMM articles quoting GACC fill 2025-01/02/04 and 2026-03/05,
  each kept only if its quote is found verbatim in the live article. Other 2025–26 months: no public
  monthly Guinea figure found. 2017 Comtrade months (4.8 Mt vs 43 Mt Guinea exports; every other year
  64–78%) excluded by a data-driven rule and named in provenance.
- **C3/C5 spread tile** read `DATA.capeC3Latest`, which nothing sets → always showed typed 40.99/17.77.
  Now reads the flagship monthly means. Other typed fallbacks (68181 rows, 540640 fixtures, 182.8 Mt,
  16.4 Mt/mo) now render "—".
- Flagship freight now reads `fearnleys_dry_routes_daily.json` (refreshed); values identical on every
  overlapping month. Route labels emitted as "Route N" at source (copy lint had hand-edited the JSON).
- Deleted two orphan files nobody wrote or read, both invented: `usda_brazil_ocean_freight.csv`
  (Paranaguá = Santos + 1.25) and `usda_bulk_grain_ocean_rates.csv` (China = Japan + 2.50 / + 1.80).

**Guard:** `tests/test_cargo_truth.py` — no commodity time-series column may be a fixed multiple or offset
of another; EIA envelope equals the CSV week for week; Gulf grain equals USDA sums; Guinea volume-only and
traces to its CSV. UI test for HUD units, Guinea, C3/C5 tile, EIA data. All mutation-checked.

**Known, not changed (disclosed models, owner's call):** `eu_ets_carbon_daily.csv` scrubber savings = Hi-5
spread × 45 / × 55 t/day; `ton_mile_utilization_matrix.csv` utilization = ton-miles × 0.1227 (constant
fleet; `model_disclosed=True`).

**LNG / LPG (same night).** Fearnleys' catalog (queried) publishes newbuilding prices for 80k/30k/7.5k m³
LNG carriers but charter rates only for 174k and larger. `renderLNGCharterChart` invented a 30k/7k "hire"
(174k TC × price/142.5 × 0.90 / 0.85), called the 80k price "174k", and computed payback from that
mismatched pair. Removed; payback now needs a same-size pair. That panel's HTML was already removed in
`975f406b7` (dead renderer) — nothing was on screen; the market brief text was. `lng_charter_rates.csv`,
`lpg_charter_rates.csv`, `lpg_spot_rates.csv` had **no writer** and froze at 2026-08-05 while Broker Desk
read them. New `scripts/fearnleys/build_gas_rate_csvs.py` rebuilds them from `fearnpulse_rates_full.csv`
(every old value matched the catalog; none lost) and adds `lngc_174k_nb_price`; wired into
`data_expansion.yml` with `build_desk_caches.py`. Guard: `tests/test_gas_rates.py`.

### Open — 11 older tests failing on main before today (not in the 46 + UI contract)
Found running the whole `tests/` tree. All fail identically on `c4128a35a`; none caused by today's work.
- `test_speed_budget.py` (7): expect boot-time `idleSchedule` prefetch, `idleYield` refreshes and a
  progressive-render generation guard. `dc7037ec5` ("payload budget") deliberately moved those loads to
  tab open, and `86cc840d6` dropped the bunkers generation guard. Speed contract vs 58 MB transfer
  contract conflict — **owner decision**.
- `test_stale_guard.py::test_meta_summary_jsons_fetch_no_cache`: `dc7037ec5` removed `{cache:'no-cache'}`
  from the port_stress_summary fetch (dedupe) — a long-lived tab can keep a stale copy across deploys.
- `test_bunker_cache_and_frontend.py` wave1 / phase_b: BIX mover accent style and "accumulates with each
  daily harvest" copy added by `ccc612821`, removed one second later by `e57a427c7` (agent overwrite).
- `test_freshness_and_wiring.py::test_fleet_supply_writer_and_asof_label`: manifest has no
  `supply_fleet_orderbook_and_age_profile` series.
