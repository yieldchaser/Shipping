# PROJECT STATE — handoff snapshot

**Last updated: 2026-09-12 (Prompt 17 round 1 audited).** Update this file at every prompt boundary.

---

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
