# 17 — APPENDIX B: measured UI baseline (2026-09-12, headless Chromium 1920x1080, local build of commit 48540a62c)

Produced by mounting each tab, scrolling it, clicking every control once, and reading the live DOM.

**Use as the acceptance floor: the Phase 0 tests must detect at least these items. A test run that reports fewer findings than this table on today's code is too weak and must be tightened.**

## B1 — Per-tab counts

| tab | tooltips on controls | empty states | dash/'n/a' KPIs | banned terms | pills/badges | left-accent cards | glows | blurs | console errors | clipped text |
|---|---|---|---|---|---|---|---|---|---|---|
| dashboard | 42/48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| yearly-dash | 16/16 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| seasonality | 37/37 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| indices | 38/38 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| etfs | 94/95 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| signals | 79/83 | 4 | 6 | 0 | 1 | 0 | 0 | 0 | 2 | 0 |
| fearnleys | 12/65 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 3 | 2 |
| intelligence | 27/38 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| tracking | 82/85 | 1 | 1 | 1 | 2 | 4 | 33 | 4 | 2 | 0 |
| cargo | 5/11 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| bunkers | 80/103 | 0 | 1 | 2 | 0 | 0 | 1 | 2 | 2 | 20 |
| offshore | 25/25 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

**Navigation:** at 1366 px the bar needs 1491 px of 1366 px — **Offshore is hidden**. At 1920 px the bar is capped at 1400 px and still needs 1491 px — **Offshore is hidden**.

## B2 — Exact findings per tab

### dashboard
- **Controls with no tooltip** (6): `2021`, `2022`, `2023`, `2024`, `2025`, ``

### yearly-dash

### seasonality
- **KPI values showing a dash or n/a** (1):
  - `=-`

### indices

### etfs
- **Console errors / warnings** (1):
  - `WARNING [stale-guard] 5 broken/blank canvas(es) on "etfs" -> re-render`
- **KPI values showing a dash or n/a** (1):
  - `=-`
- **Tooltips that only describe the interaction** (4):
  - `Toggle brief expansion`
  - `Toggle Copilot expansion`
  - `Toggle Scenario Translator expansion`
  - `Toggle Simulator expansion`
- **Controls with no tooltip** (1): ``

### signals
- **Console errors / warnings** (2):
  - `ERROR [SignalsTab Seasonal] TypeError: Cannot read properties of undefined (reading 'color')
    at renderSeasonalChart (http://127.0.0.1:8765/index.html:31302:84)
    at http://127.0.0.1:8765/index.h`
  - `WARNING [stale-guard] 10 broken/blank canvas(es) on "signals" -> re-render`
- **Empty-state text visible** (4):
  - `Insufficient overlapping data for this pair.`
  - `Loading…`
  - `SGX FFA data not available yet. Data populates after the first daily update run.`
  - `SGX Iron Ore forward curve data not available.`
- **KPI values showing a dash or n/a** (6):
  - `=-`
  - `ioFwdHudLump=—`
  - `ioFwdHudOI=—`
  - `ioFwdHudPrompt=—`
  - `ioFwdHudRegime=—`
  - `ioFwdHudSpread=—`
- **All-caps pills / count badges** (1):
  - `40 TENORS`
- **Tooltips that only describe the interaction** (1):
  - `Select any active forward contract (40 tenors) or browse historical/expired contracts from`
- **Controls with no tooltip** (4): `1Y`, `3Y`, `1Y`, `3Y`
- **Clicking a control produced an error or an empty state** (1):
  - `BDRY Dry Bulk Basis` → ["WARNING [stale-guard] 10 broken/blank canvas(es) on \"signals\" -> re-render", "ERROR [SignalsTab Seasonal] TypeError: Cannot read properties of undefined (reading 'color')\n    at renderSeasonalChart (http://127.0.0.1

### fearnleys
- **Console errors / warnings** (3):
  - `WARNING Canvas2D: Multiple readback operations using getImageData are faster with the willReadFrequently attribute set to true. See: https://html.spec.whatwg.org/multipage/canvas.html#concept-canvas-w`
  - `WARNING [stale-guard] 5 broken/blank canvas(es) on "fearnleys" -> re-render`
  - `WARNING [stale-guard] 7 broken/blank canvas(es) on "fearnleys" -> re-render`
- **Internal wording in visible text** (2):
  - `graphql — Live GraphQL Feed`
  - `unauthenticat — Unauthenticated broker forward curve · Cape / Panamax / Supramax / Handysize tenors`
- **Text clipped by its container** (2):
  - `COASTER Europe (3 500-5 000 cbm)`
  - `VLGC: 88,000 cbm Panamax, LPG DF`
- **Controls with no tooltip** (53): `DRY BULK
usd
ACTIVE
Capesize`, `DRY BULK
usd
ACTIVE
Panamax `, `DRY BULK
usd
ACTIVE
Supramax`, `DRY BULK
usd
ACTIVE
Handysiz`, `TANKER
usd
ACTIVE
VLCC
130,0`, `TANKER
usd
ACTIVE
Suezmax
82`, `TANKER
usd
ACTIVE
Aframax
58`, `NEWBUILDING
usd
ACTIVE
Kamsa`, `NEWBUILDING
usd
ACTIVE
Newca`, `NEWBUILDING
usd
ACTIVE
Ultra`, `NEWBUILDING
usd
ACTIVE
VLCC
`, `NEWBUILDING
usd
ACTIVE
Suezm`, `NEWBUILDING
usd
ACTIVE
Afram`, `NEWBUILDING
usd
ACTIVE
Produ`, `NEWBUILDING
usd
ACTIVE
LNGC `, `NEWBUILDING
usd
ACTIVE
VLGC:`, `NEWBUILDING
usd
ACTIVE
MGC: `, `NEWBUILDING
usd
ACTIVE
16,00`, `NEWBUILDING
usd
ACTIVE
21,00`, `NEWBUILDING
usd
ACTIVE
9,000`
- **Clicking a control produced an error or an empty state** (2):
  - `S&P & Assets` → ["Loading…"]
  - `Fixtures Tape` → ["Coverage 2024 forward · earlier years are sparse department scraps · rate numeric where parseable (92% text/RNR historic"]

### intelligence
- **Controls with no tooltip** (11): `Groq (Ultra Fast - GPT OSS 1`, `llama-3.3-70b-versatile (Cus`, `on`, `on`, `on`, `on`, `on`, `on`, `on`, `on`, `on`

### tracking
- **Console errors / warnings** (2):
  - `WARNING [expanded refresh] ReferenceError: renderTrackingHUDRefreshNote is not defined
    at http://127.0.0.1:8765/index.html:17718:21`
  - `WARNING [stale-guard] 1 broken/blank canvas(es) on "tracking" -> re-render`
- **Empty-state text visible** (1):
  - `awaiting disruptions feed`
- **KPI values showing a dash or n/a** (1):
  - `hudDisruptionsActive=—`
- **Internal wording in visible text** (1):
  - `own series — Source: AIS Daily Transit Observation & IMF PortWatch (2019–2026) · baseline lines are computed from the chart`
- **All-caps pills / count badges** (2):
  - `ACTIVE REROUTING`
  - `LIVE FLEET AIS`
- **Cards with a coloured left accent bar** (4):
  - `{"id": "cpDrawerNote", "cls": "cp-spec-strip", "color": "rgb(77, 154, 255)", "text": "Red Sea Rerouting Crisis: Houthi strikes force Asia-Europe v"}`
  - `{"id": "", "cls": "cp-annotation-card", "color": "rgb(77, 154, 255)", "text": "Red Sea Missile Attacks & Galaxy Leader Hijack\n2023-11-19 → "}`
  - `{"id": "", "cls": "cp-annotation-card", "color": "rgb(77, 154, 255)", "text": "Naval Escort Operations (Prosperity Guardian & Aspides)\n2024"}`
  - `{"id": "", "cls": "cp-annotation-card", "color": "rgb(77, 154, 255)", "text": "Sinking of MV Tutor in Red Sea\n2024-06-12 → 2026-09-10\nUncre"}`
- **Controls with no tooltip** (3): `on`, `on`, `on`
- **Clicking a control produced an error or an empty state** (1):
  - `All` → ["WARNING [stale-guard] 1 broken/blank canvas(es) on \"tracking\" -> re-render"]

### cargo
- **Internal wording in visible text** (2):
  - `audit — EST. AUDIT`
  - `zero ton-mile — Observed volumes vs observed freight · Zero ton-mile sliders · Honest empty states`
- **All-caps pills / count badges** (1):
  - `LIVE PAIRED`
- **Controls with no tooltip** (6): `Flagship: Origin → Freight`, `Commodity Flow Matrix (540k `, `Seasonal Export Basins`, `Grain Logistics & Queues (US`, `Demand Drivers & Costs`, `View All Modules`
- **Clicking a control produced an error or an empty state** (7):
  - `Commodity Flow Matrix (540k Fixtures)` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `View All Modules` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `Brazil Ore vs C3` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `WA Ore vs C5` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `Newcastle Coal` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `USG Grain vs Panamax` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)"]
  - `Guinea Bauxite (Mirror)` → ["Source: UN Comtrade China Mirror (HS 260600) + Broker Fixtures (Conakry direct UNAVAILABLE)", "UNAVAILABLE", "⚠ Official Direct Conakry Customs Series: UNAVAILABLE"]

### bunkers
- **Console errors / warnings** (2):
  - `WARNING Canvas2D: Multiple readback operations using getImageData are faster with the willReadFrequently attribute set to true. See: https://html.spec.whatwg.org/multipage/canvas.html#concept-canvas-w`
  - `WARNING [stale-guard] 3 broken/blank canvas(es) on "bunkers" -> re-render`
- **KPI values showing a dash or n/a** (1):
  - `=—`
- **Internal wording in visible text** (2):
  - `harvest — Archive 2025-09-09 to 2026-09-09 · accumulates with each daily harvest`
  - `harvest — Daily Spot Indications across 213 Ports, 12M Forward Delivery Curves, Scrubber TCE Economics & FuelEU / EU ETS`
- **Text clipped by its container** (20):
  - `+2.17 (+0.16%)`
  - `-0.50 (-0.06%)`
  - `-0.98 (-0.15%)`
  - `-1.34 (-0.22%)`
  - `-12.00 (-0.80%)`
  - `-2.25 (-0.35%)`
  - `-2.38 (-0.36%)`
  - `-3.21 (-0.37%)`
  - `-3.55 (-0.38%)`
  - `-4.14 (-0.58%)`
  - `-4.45 (-0.31%)`
  - `-4.95 (-0.57%)`
  - `-7.73 (-0.52%)`
  - `-8.45 (-1.07%)`
- **Tooltips that only describe the interaction** (1):
  - `Select bunker supply port or regional benchmark to plot.`
- **Controls with no tooltip** (23): `World`, `World3`, `APAC`, `EMEA`, `Americas`, `MidGulf`, `VLSFO`, `IFO380`, `MGO`, `Region`, `VLSFO`, `IFO380`, `MGO`, `All Regions (213 Ports)`, `Asia-Pacific (APAC)`, `Europe, MidEast, Africa`, `Americas`, `All Grades`, `VLSFO`, `MGO`
- **Clicking a control produced an error or an empty state** (10):
  - `Alt Fuels (4)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `Global Average Bunker Price
Global 20 Po` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `Max (3Y)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `1Y (Daily)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `6M (Daily)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `VLSFO (0.5%)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `MGO (0.1%)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `HSFO (IFO380)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `Hi-5 Spread` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]
  - `Biofuel (B24)` → ["Verified alt-fuel indications — 4 of 213 ports (LNG: 1 · MEOH: 4 · EUA: 0). Null = no quote, never 0."]

### offshore
