# Fearnleys Desk Truth & Utilization Pass — 2026-09-08

> **For Hermes:** execute sequentially; each task independent-committable. All edits in `C:/Users/Dell/Github/Shipping/index.html` unless noted. Server for verification: `python -m http.server 4173` (already running). Playwright python at `C:/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe`. NO fabricated data — every series shown must trace to a fetched cache. Archived desks get frozen-state treatment, never silent merge.

**Goal:** Fix truncated histories + code-speak naming across the Fearnleys desk, surface the under-used LNG/LPG series depth, upgrade Bunkers/Tracking tooltip polish toward the Intelligence-tab standard.

---

## Investigation findings (verified)

1. **TC Rates (S2) truncated history — CONFIRMED.** Chart sources `data/derived/time_charter_rates.csv` (weekly Baltic, starts 2000-01-05). The Hasura monthly archive (`data/derived/fearnleys_series_monthly.json`) carries `BULK_TC_CAPESIZE_180_000_DWT` from **1977-01** (597m), `BULK_TC_PANAMAX_75_000_DWT` from **1970-01** (681m), `BULK_TC_SUPRAMAX_58_000_DWT` from 2004-01. Pre-2000 history exists but is only visible in Series Museum. Not fabricated — real Fearnleys Hasura prints.
2. **Naming — CONFIRMED.** Overview tiles read `TANK usd [ACTIVE]` with vessel name buried in the last line; S5 dataset legends read `WET-5 / DRY-10 / PRICES / scrap tanker_india ($/ldt, right)`; S6/S7 chart labels lowercase (`lngc 174k 7y tc`).
3. **LNG/LPG under-utilization — CONFIRMED.** Cache has **71 LNG labels (50 live 2026+)** and **27 LPG (19 live)**. Desks show a single series at a time via selector; no family overlay (e.g., all LNG 1yr TC classes vs each other).
4. **Newbuilding default family** = `bulk` (2004+ classes); tanker family carries 1970-12+ (Aframax, Product) — deep history hidden behind default, not missing.
5. **S5 classes** already human-named (33 classes: `Capesize`, `VLCC`, `Aframax / LR2`…). Only dataset/tenor labels need renaming.

## Design doctrine (from user, standing)
- Names must say exactly what a series is: `Capesize TC`, `Aframax 5yr`, `Newbuilding price`.
- Intelligence tab = quality bar: detailed tooltips, values context.
- Archived = frozen-state disclosure, never silently blended.
- Effective > complicated. No vanity analytics.

---

### Task 1 — S2 TC Rates: pre-2000 archive layer (code)
**Objective:** Cape/Panamax/Supramax/Handysize TC charts include the Hasura monthly archive for months before the Baltic weekly feed begins (2000-01), as clearly-attributed datasets.

**Edit** `renderFearnTc()` (search `function renderFearnTc`):
- `fearnSeriesCache()` is already available (used in S1). Build `arch` datasets: for the selected class, map `Capesize→BULK_TC_CAPESIZE_180_000_DWT`, `Panamax→BULK_TC_PANAMAX_75_000_DWT`, `Supramax→BULK_TC_SUPRAMAX_58_000_DWT`, `Handysize→BULK_TC_HANDYSIZE_38_000_DWT`; others (VLCC/Suezmax/Aframax) get no archive (say so in meta).
- Extend `dates` domain with archive months **only older than the first Baltic date for that class** (no overlap double-plot: if a month exists in both, Baltic weekly wins, archive suppressed for that month).
- Archive dataset: `label: 'Fearnleys archive (monthly)'`, `borderDash:[6,4]`, `borderColor:'#8b949e'`, `pointRadius:0`, `spanGaps:true`, distinct color `#a371f7`.
- Meta line: append ` · pre-2000 from Fearnleys monthly archive (n=X)` when archive rows were added.
- Keep `gaps = no published print` honesty; no interpolation.

**Verify:** headless — select Capesize; chart labels[0] should be `1977-01` (or first archive month); archive dataset present with 597 pts; Baltic tenors unchanged (1Y n=2056). Screenshot. No console errors.

### Task 2 — Naming pass (code)
**Objective:** every displayed series reads as its real-world name.

- **Overview tiles** (`renderFearnOverview`): label row becomes `〈Human desk〉 · 〈unit〉` where human desk map = `TANK→Tanker, BULK→Dry Bulk, LNG→LNG, LPG→LPG, NEWBUILDING→Newbuilding, S&P→S&P / Resale, counts→Counts`. The existing bold colored token keeps the desk color; the vessel/route name line moves UP directly under the label row (it's the actual series name) — swap order so name sits above the big value.
- **S5** (`renderFearnAc`): dataset label map `DRY-5→5yr old`, `DRY-10→10yr old`, `DRY-15→15yr old`, `DRY-RESALE→Resale`, `-CN→ (CN basis)`, `-JP→ (JP basis)` suffixes, `WET-*` same pattern, `PRICES→Newbuilding price`, scrap → `Demolition scrap (India, $/ldt)` / `(Alang…) per key` — keys: `dry_india→India`, `tanker_india→India` (check `fearnleys_asset_curves.json` `scrap` keys; use exact names). Keep TENOR_COLORS keyed on RAW tenor codes (map labels after color lookup).
- **S6/S7** (`renderFearnGas`): pretty-label helper `prettyGasLabel(k)`: strip type prefix, replace `_`→space, title-case vessel words (VLGC, MGC, HDY, ETH, LGC, SR, COASTER, TFDE, MEGI, XDF, LNGC, ST, CBM, KM3 kept uppercase), append unit from cache ` (usd/day)` when subtype is BROKER/CALCULATED TC, ` (usd)` for SPOT/FOB/MARKET. Use in chart dataset label + KPI title + selector options (selector keeps full key in `value`).
- **S4** pills: `bulk→Dry Bulk`, `tanker→Tankers`, `gas→Gas`, `other→Other/Container`.

**Verify:** headless screenshots S1/S5/S6/S7 — no `WET-5`, no `scrap tanker_india`, no lowercase `lngc 174k` labels remain; overview tiles read `Tanker · usd` + vessel name prominent.

### Task 3 — LNG/LPG family overlay (code)
**Objective:** each gas desk gains a "Family View" chart: all live series of one subtype family on one chart.

- New section block in S6/S7 under the existing single-series view: header `〈LNG/LPG〉 TC Tenor Family` and `〈LNG/LPG〉 Spot & FOB Family`, each a `chart-canvas-wrap` 280px canvas `fearnLngTcFamily`, `fearnLngSpotFamily` (S7: `fearnLpgTcFamily`, `fearnLpgSpotFamily`).
- Renderer `renderFearnGasFamily(kind)`: pick live (`last>='2025-01'`) labels grouped: TC family = subtype BROKER/CALCULATED with `TC` in key; Spot/FOB = subtype SPOT or FOB/MARKET. One dataset per label, `prettyGasLabel`, PALETTE rotation, `spanGaps:true`, tooltip `$` suffix. Cap at 12 datasets (meta discards with `+N more in Museum`).
- Wire into `renderFearnSection` for ids 6/7 (before/after existing render call).
- Add meta line: `n series · monthly Fearnleys prints · gaps = no print`.

**Verify:** headless S6: TC family chart shows ≥6 datasets (1YR TFDE, 3YR, 5YR, MEGI 1YR/3YR/5YR, 7YR 174K, 120-130K…) with 2011→2026 coverage; S7 spot family ≥7 datasets. 0 errors. Screenshot.

### Task 4 — Bunkers + Tracking tooltip/context polish (code, Intelligence-bar raise)
**Objective:** bring context-rich tooltips (the Intelligence-tab tell) to Bunkers & Tracking heads.

- Bunkers KPI cards: add `data-tooltip` (repo uses a global tooltip system — grep `data-tooltip=` for the pattern; verify how tooltips bind, likely a delegated listener) with real context: e.g. Global VLSFO card → `Global average VLSFO, $/mt, Ship & Bunker daily RPC composite · 〈obs date〉 · 〈chg vs prev obs〉 · source: 482k-row RPC archive`. Use values from `DATA.bunkerSummary.kpis` (never invented).
- Tracking KPI cards: tooltips already have `data-tt-title/desc` (audit showed). Raise: add `data-tt-val` freshness (lineup snapshot date) where missing.
- Do NOT add new fabricated context; only re-surface what's in the caches.

**Verify:** hover simulation (dispatch mouseover) or DOM check that tooltips exist on all bunker KPI cards; screenshot with tooltip forced visible (repo may expose `window.showTip`— grep first).

### Task 5 — Verification & ship
- `C:/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_fearnleys_desk.py tests/test_fearnleys_wave3.py tests/test_bunker_cache_and_frontend.py -q` → all pass (tests read caches, not UI, so UI changes shouldn't break; if a marker test greps index.html for removed strings, update test to new markers).
- Full sweep headless: tabs 0 console errors; Fearnleys sections 1–11 re-render clean.
- Commit per task (`fix(fearnleys): ...` / `feat(fearnleys): ...`), push `main`, watch `gh run list` deploy green, hash-check live.

## Out of scope (deliberate)
- No new data files; everything sourced from existing caches.
- No tearing down section structure (11 sections stay); this is truth+depth+polish, not layout churn.
- Museum stays the full-catalog browser; desks get the curated overlays.
