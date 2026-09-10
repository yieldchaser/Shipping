# PROMPT 13 — SCRAPER BUILD: LIVE-VERIFIED TARGETS

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-13-scrapers.md`
> Run **before** Prompts 10–12. Supersedes Prompt 11 Jobs A/C/D/E/F.

**Everything below was verified live on 2026-09-10** — either by executing the endpoint and
reading the response, or by web search against multiple publishers. Previous rounds
recorded several of these as UNAVAILABLE without ever searching. That was wrong.

Build one scraper per target under `scripts/acquire/`, checkpointed, rate-limited, failing
loudly. Register each with computed `data_through` (Prompt 10).

---

# TARGET 1 — Fearnpulse: LABEL AUDIT first, then depth backfill ★★★★ DO THIS FIRST

**There are two jobs here and the first one is a live data-integrity bug, not an
enhancement. Do 1A before 1B.**

`index.html` fetches `data/clarksons/fearnleys_benchmark_rates_continuous.csv`. That file's
tsId→label map is wrong for at least six series, and the wrong labels are on screen now.

## 1A — The mislabelling (CRITICAL, currently live)

Two files in this repo disagree about what vessel class each tsId is:
- `data/clarksons/fearnleys_benchmark_rates_continuous.csv` (column headers)
- `scripts/fearnleys/fetch_dry_routes_ts.py` (its `SERIES` dict)

**Both are wired to the UI.** The values settle which is right — executed live 2026-09-10:

| tsId | CSV header says | Latest value | Reality | Verdict |
|---|---|---|---|---|
| 120654 | Pacific RV **(Supramax)** | **62,359** | Supramax Pacific RV ≈ $15–18k/day | **Capesize** — CSV wrong |
| 120655 | TCE Cont/Far East **(Supramax)** | **91,194** | Supramax fronthaul ≈ $25k/day | **Capesize** — CSV wrong |
| 10010 | Transatlantic RV **(Capesize)** | **20,195** | Cape TA RV ≈ $40–60k in this market | **Panamax** — CSV wrong |
| 10011 | TCE Cont/Far East **(Capesize)** | **30,487** | — | **Panamax** — CSV wrong |
| 10012 | TCE Far East RV (Capesize) | 22,204 | — | **Panamax** — CSV wrong |
| 10013 | TCE Far East/Cont (Capesize) | 13,299 | — | **Panamax** — CSV wrong |

`fetch_dry_routes_ts.py` labels all six correctly (`CAPESIZE_PACIFIC_RV`,
`PANAMAX_TRANSATLANTIC_RV`, …) and its docstring states they were taken from the Fearnleys
Weekly Report tiles. **Treat that script as the source of truth; the CSV headers are wrong.**

### Independent confirmation — the Baltic Exchange route taxonomy

`https://www.balticexchange.com/en/data-services/freight-derivatives-/Baltic-Forward-Assessments.html`
publishes the authoritative route list per vessel class:

```
Capesize   5TC · C3 · C5 · C7
Panamax    5TC · P1A · P2A · P3A · P6
Supramax   10TC · 11TC
Handysize  7TC
```

**Panamax has exactly four named routes, and the four Fearnleys names map onto them 1:1:**

| tsId | Fearnleys name | Baltic route | Definition | Value |
|---|---|---|---|---|
| 10011 | TCE Cont/Far East | **P2A** | Skaw-Gib delivery, Far East redelivery (fronthaul) | $30,494 |
| 10012 | TCE Far East RV | **P3A** | Japan/S-Korea transpacific round voyage | $22,204 |
| 10010 | Transatlantic RV | **P1A** | Skaw-Gibraltar transatlantic round voyage | $20,077 |
| 10013 | TCE Far East/Cont | **P6** | Spore-Japan delivery, Skaw-Passero redelivery (backhaul) | $13,299 |

The value ordering is the textbook Panamax hierarchy — **fronthaul > transpacific RV >
transatlantic RV > backhaul**. Capesize has no P-routes; its forward list is 5TC/C3/C5/C7.

Likewise, **Supramax's entire forward list is 10TC and 11TC** — there is no Supramax
"Pacific RV" or "Cont/Far East" named route, and Supramax does not trade at $91,194/day.
120654 and 120655 are the Capesize TC routes (C10 Pacific RV / C9 Cont-Far East family).

**This is the labelling authority. Use it, not the CSV headers.**

Bonus: the same page carries a **live index ticker** — BDI, BCI, BPI, BSI, BHSI, BCTI,
BAI00, BLNG — free and unauthenticated. Cross-check: Baltic showed **BDI 3,521** on
2026-09-10 and Fearnpulse `11323` returned exactly **3,521** for the same date, which
independently validates that tsId as the real BDI. We already ingest this via
`blacksun-api.balticexchange.com/api/ticker` (discovery doc §5) — verify that pipeline is
still running and covers all eight indices.

Two more with wrong labels or missing units:

| tsId | CSV header | Latest | Problem |
|---|---|---|---|
| 11 | 1 Year TC — **LR1** | **145,000** | LR1 1-yr TC ≈ $30–35k/day. 145,000 is not a TC rate — likely a vessel price ($145m) or a different asset entirely |
| 13 | 1 Year TC — **Handy** | **110,000** | Handy 1-yr TC ≈ $14.5k/day. Same problem |
| 1–9 | MEG/Japan (VLCC) etc. | 30, 40, 275… | These are **Worldscale points, not $/day**. Unit is not recorded anywhere |

**Work for 1A:**
1. Re-derive the tsId→label→class→unit map from `fetch_dry_routes_ts.py` plus the Fearnleys
   Weekly Report tiles. For any tsId neither source covers, use a magnitude sanity check
   against the known class ranges (Cape 5TC ≈ $38k, Panamax ≈ $20k, Supramax ≈ $17.7k,
   Handy ≈ $14.5k as of Sep 2026) and record the reasoning.
2. **Add an explicit `unit` to every series** — `usd/day`, `usd/tonne`, `worldscale`,
   `usd_million`, `index`. A Worldscale 275 rendered on a $/day axis is meaningless.
3. Rebuild the CSV with corrected headers, and add a regression test asserting each series'
   median falls inside its class's plausible band.
4. Audit the UI for anywhere these six render, and correct the on-screen labels.

## 1B — Depth backfill

We call the endpoint with `last=260`. That is a row limit we chose. Verified: omitting
`last` entirely and `last=50000` return identical full history.

```
GET https://fearnpulse.com/api/marketapi/TS?id={tsId}          # full series, oldest-first
Referer: https://fearnpulse.com/fearnleys-weekly-report
→ {"columns":["tsid","value","date","jobid"],"data":[[10001,41.727,1788998400000,18],...]}
```
`date` is epoch ms. Row order is **oldest-first without `last`, newest-first with it** —
`fetch_dry_routes_ts.py` already handles both; reuse its normaliser.

Real gains, measured against what we already hold:

| tsId | Series | We hold | Available | Gain |
|---|---|---|---|---|
| **10001** | **C3 Tubarão/Qingdao** | **260** | **7,085** | **1998-05-06 →, 28 yrs** |
| **10002** | **C5 Australia/China** | **260** | **6,877** | **1999-03-01 →, 27 yrs** |
| **10003** | Newcastle/Qingdao coal | 260 | **6,877** | 1999-03-01 → |
| 10010–10013 | Panamax route TCEs | 260 each | **2,169** each | 2018-01-02 → |
| 11325 | (unlabelled, Cape-scale $/day) | — | 3,129 | 2014-02-24 → |
| 11328 / 11329 | (unlabelled, VLCC/Suezmax-scale) | — | 1,834 / 1,602 | 2019 / 2020 → |
| 4 | WAF/UKC Suezmax (Worldscale) | 260 | 1,161 | 2004-01-07 → |
| 13 | (mislabelled — see 1A) | 260 | 1,616 | 1995-03-29 → |

**❌ BDI is NOT a gain — we already have better.** Fearnpulse `11323` returns 10,446 rows
from 1985-01-04. Our `data/indices/bdiy_historical.csv` already holds **10,513 rows,
1985-01-04 → 2026-09-09**. An earlier draft of this prompt claimed Fearnpulse "unlocks 41
years of BDI". That was wrong — we had it, and ours is marginally deeper. **Do not
overwrite `bdiy_historical.csv`**; use Fearnpulse only to cross-validate it.

## ⚠ Dead series — stop rendering them as current

| tsId | CSV label | Last print |
|---|---|---|
| 1, 2, 3 | MEG/Japan, MEG/Singapore, WAF/China VLCC | **2023-05-22** |
| 5, 6 | Market Brief, Cross Med Aframax | **2023-05-22** |
| 7, 8, 9 | 1-Yr TC VLCC / Suezmax / Aframax | **2023-05-22** |
| 11319 | (index-scale, 9,586 rows from 1985) | **2023-03-24** |
| 11326 | (Handy-scale $/day) | **2025-04-11** |

Fearnleys stopped publishing most of the tanker set in May 2023. **Correction to earlier
specs, including my own: the tanker columns do NOT run 2018→2026.** Mark them `DORMANT`
(Prompt 10). `gibson_tanker_rates_continuous_daily.csv` — already on disk, 9 routes,
current — is the live replacement for that coverage.

## ⚠ Corrupt dates in the source

tsId **11** returns a first date of **1866-02-19**. That is a sentinel or corrupt row, not
history. **Reject any row before 1980** at ingest and log it. A naive backfill would put an
1866 point on a chart and blow out every axis.

## ❌ What is NOT available here

**Baltic vessel-class indices before 2008.** Our `cape_historical.csv`,
`panama_historical.csv`, `suprama_historical.csv` and `handysize_historical.csv` all start
**2008-10-06**. I swept tsIds 11315–11335 and 1–16; Fearnpulse carries **no BCI/BPI/BSI/BHSI
series reaching earlier**. The nearest candidates start 2014 (11325) and 2018 (11324, 11327).

This is expected rather than a scraping failure: the Baltic Exchange re-based these indices
onto timecharter baskets at different dates (BCI→5TC in 2014, BSI→10TC in 2015, BPI→5TC in
2020), so a continuous pre-2008 series on today's definition does not exist. If earlier
history is wanted it has to come from the Baltic Exchange directly and will be on a
different basis — **it must not be silently splined onto the current series.**

## Work for 1B

1. Probe **all 34 tsIds** in the CSV plus the id ranges swept above; record rows, first,
   last, alive/dead, inferred class, unit.
2. Rebuild the file at full depth with corrected labels from 1A.
3. Reject pre-1980 rows; mark dead series DORMANT.
4. Reuse `fetch_dry_routes_ts.py`'s existing `--backfill` path — it already omits `last`
   and normalises row order. Do not write a second client.

**Do not use Barchart.** An earlier draft suggested it; the symbol cited (`KW3J26`) is an
**expired contract showing "No data to display"**, the site is bot-protected, and
per-contract-month symbols are the wrong shape for a continuous series.

---

# TARGET 2 — Guinea bauxite, monthly ★★★

Ministry of Mines and Geology publishes monthly; multiple outlets republish with
**per-company tonnage and vessel counts**.

| Period | Exports | Detail |
|---|---|---|
| Jan 2026 | **20.26 Mt** | +46,764 t alumina; **SMB 6.57 Mt across 32 vessels** |
| Q1 2026 | 60.9 Mt | vs 48.6 Mt Q1 2025 |
| Q2 2026 | 53.9 Mt | vs 51.2 Mt |
| H1 2026 | **114.8 Mt** | vs 99.8 Mt |
| Q3 2026 | 39.41 Mt | cumulative to end-Sep **139.21 Mt** |
| Q1 2025 | 48.6 Mt | **312 vessels** vs 225 in Q1 2024 |

The quarantined fabricated series implied H1 2026 ≈ 106.7 Mt vs a real 114.8 Mt, and Jan
2026 of 17.3 Mt vs a real 20.26 Mt — roughly **8% low**.

Sources, priority order:
1. `https://www.guineamininginsights.com/` — crawl `news-insights-*`; richest structure
   (per-company tonnage + vessel counts).
2. `https://www.mysteel.net/news/` and `/analysis/` — monthly/quarterly coverage.
3. Reuters, Mining Weekly, AlCircle, African Mining Market — same ministry release.
4. Ministry direct (DGM statistics bulletin PDF) — authoritative if found.

Keep the UN Comtrade China-mirror as an independent cross-check. Two methods that agree
beat one; where they disagree, show both.

**Deliverable:** ≥60 monthly points, columns `[date, tonnes, vessels, company, source_url,
publisher, source_quote, method]`.

---

# TARGET 3 — Pilbara Ports (Hedland + Dampier) ★★★

Ours stops **2026-05-01**. The source never stopped.
- **Aug 2026**: Port Hedland **45.0 Mt** total, **44.2 Mt iron ore** (−4% YoY), imports 250 kt.
  Dampier **14.7 Mt** (+3% YoY), imports 115 kt.
- Jul 2026: Pilbara total 63.8 Mt.

URL pattern (release month = data month + 1), both confirmed live:
```
.../news/2026/may/april-2026-shipping-figures
.../news/2026/june/may-2026-shipping-figures
```
Base: `https://www.pilbaraports.com.au/about-pilbara-ports/news,-media-and-statistics/news/`

**Obstacle:** Incapsula gate — a plain fetch returns empty. §6 of the discovery doc records
that **static PDF assets bypass it**. Try full browser headers first, then the linked PDF.
Mirrors carrying the same figures within days: container-news.com, porttechnology.org,
australianmining.com.au, geomechanics.io.

**Add Dampier as its own series** — only Hedland is captured today.

---

# TARGET 4 — USDA grain vessel queues ★★

Ours stops **12/31/2020**. Source has published continuously.

- **Structured Excel:** `https://www.ams.usda.gov/services/transportation-analysis/gtr-datasets`
  — weekly vessel activity, Gulf / PNW / Vancouver BC.
- **Weekly PDF, predictable:** `https://www.ams.usda.gov/sites/default/files/media/GTR{MMDDYYYY}.pdf`
  Confirmed live: `GTR05142026.pdf`, `GTR06112026.pdf`, `GTR08202026.pdf`.

Validate against: w/e 2026-07-23 → 25 Gulf vessels loaded, 41 expected next 10 days;
w/e 2026-08-13 → 29 loaded, 31 expected.

Rebuild 1998 → current with **ISO dates** (the current file is `MM/DD/YYYY` and mis-sorts).
This also removes the false "31-Year History 1995–2026" UI claim over a file ending in 2020.

---

# TARGET 5 — China demand side (GACC) ★★★★ biggest structural gap

**We have almost no China import data. China is ~75% of seaborne iron ore and ~60% of
bauxite. This is the demand side of the entire dry bulk market and it is missing.**

**`https://chinadata.live/` — REST API, no key required, free CSV download.**
GACC monthly imports by HS chapter, **Jan 2018 → latest published month**.

Pull monthly import volume **and** value for at least:

| Commodity | HS | Why |
|---|---|---|
| Iron ore | 2601 | Capesize demand, #1 driver |
| Coal (bituminous / thermal / coking) | 2701 | Panamax/Supramax |
| Bauxite | 2606 | validates the Guinea mirror from the buy side |
| Alumina | 2818 | pairs with bauxite |
| Soybeans | 1201 | Panamax grain |
| Crude oil | 2709 | VLCC demand |
| LNG / LPG | 2711 | gas carriers |
| Fertiliser / urea | 3102 / 3105 | Handy/Supra, zero coverage today |
| Steel products | 72 | export side, Supramax |

**By origin country where the API exposes it** — Australia vs Brazil iron ore split is a
direct C3-vs-C5 signal.

---

# TARGET 6 — Indonesia coal ★★★ world's largest thermal coal exporter, zero coverage

Confirmed monthly, from BPS (Statistics Indonesia):
- May 2026: **40.49 Mt** (+8.5% MoM, 2026 high)
- Jan 2026: **29.53 Mt**
- Jan–May 2026: 143.56 Mt / US$9.75 bn
- Jan–Jul 2026: **201.47 Mt** (−6.17% YoY), US$14.47 bn

Sources: BPS (`bps.go.id`) trade statistics; ESDM/Minerba for production and the 2026
~600 Mt approval cap; `databoks.katadata.co.id` publishes monthly buyer breakdowns;
Mysteel for analysis.

Indonesia→China and Indonesia→India are the two largest Panamax/Supramax coal lanes in the
world and we currently render nothing.

---

# TARGET 7 — Argentina grain ★★ complete blank today

Rosario Board of Trade / Rosario Grain Exchange (BCR), monthly:
- Jul 2026 corn: **5.14 Mt** — monthly record (prev. 5.08 Mt in Apr 2026)
- H1 2026: **60.7 Mt** total grain — corn 21.0, soy 20.1, wheat 11.1, sunflower 4.4
- Mar–Jul 2026 corn: 22.21 Mt

Also **USDA FAS GAIN reports** — free PDFs, predictable paths, e.g.
`https://www.fas.usda.gov/data/gain-report/2026/07/Grain%20and%20Feed%20Update_Buenos%20Aires_Argentina_AR2026-0011.pdf`

Argentina is the up-river Panamax/Handy market. Its absence is why our grain picture is
US-only.

---

# TARGET 8 — Steel production ★★

worldsteel's own dataset is paywalled (€1,590) but **monthly press releases are free**:
`https://worldsteel.org/media/press-releases/2026/{month}-2026-crude-steel-production/`
(confirmed for March, April, May, June, July 2026). June 2026 world crude steel: **155.7 Mt**
across 70 reporting countries, +1.7% YoY.

Free republisher with a longer series: `https://www.steelonthenet.com/resources/market-data/production.html`

Steel output is the demand function for iron ore and coking coal — it belongs beside them.

---

# TARGET 9 — Fleet supply side ★★ the other half of the market

We model demand and render almost nothing on supply. Free sources:
- **UNCTADstat merchant fleet** — `https://unctadstat.unctad.org/datacentre/reportInfo/US.MerchantFleet`
  and `https://stats.unctad.org/fleet` — fleet by type and flag, deliveries, demolition.
  Annual, but authoritative and free. World fleet 1 Jan 2026: **~116,000 vessels,
  2.5 bn dwt** (+85 m dwt YoY); tankers + bulkers = 69% of capacity. 91% of 2025
  completions built in China/Korea/Japan; 80% of recycling in India/Bangladesh/Türkiye.
- **UNCTAD Review of Maritime Transport** — annual PDF, Chapter II, full fleet tables.
- **`signal_vessels_*.json` already on disk** — 57,256 vessels. If they carry build year and
  yard, we can derive **fleet age profile and a partial orderbook ourselves**. Check the
  schema before calling orderbook a gap.

---

# TARGET 10 — Remaining minor bulks

| Commodity | Source to test | Note |
|---|---|---|
| **Sugar** | Brazil ComexStat NCM **1701** | Brazil is #1 exporter; fold into the ComexStat run |
| **Urea / fertiliser** | Comtrade HS 3102/3105; India + Brazil as importers | large Handy/Supra trade, zero coverage |
| **Alumina** | Comtrade HS 2818 + GACC (Target 5) | pairs with bauxite |
| **Nickel ore** | Indonesia/Philippines exports (BPS, Target 6) | Supramax, Indonesian export bans move this market |
| **Scrap steel** | Comtrade HS 7204 (Türkiye as importer) | Türkiye is the global scrap buyer |
| **Cement / clinker** | Comtrade HS 2523 | Handy trade |

---

# TARGET 11 — Brazil ComexStat full history ★★

Endpoint works; the pull was just too narrow (**124 rows, 2024-01 → 2026-07**).
Re-run `POST https://api-comexstat.mdic.gov.br/general` for **201701 → current**, looping
year by year if the window is capped, for NCM **2601** (iron ore), **1201** (soy),
**1005** (corn), **1701** (sugar). Capture `metricKG` and `fobValue`.

---

## Rules for this phase

1. **"Unavailable" is a conclusion you must earn.** Log every URL, status and response
   shape. One 403 or empty body is a gate to work around, not an answer.
   Two cautionary examples from writing this prompt: a Barchart symbol was cited without
   opening it and turned out to be an expired contract; and `last=260` was assumed to be
   the endpoint's ceiling when it was just the number we asked for.
2. **Every row carries `source_url`.** Prose-derived rows also carry `publisher` and
   `source_quote`.
3. **Never blend methods in one series.** Ministry-reported, mirror-derived and
   fixture-derived are separate series with separate badges.
4. **Cross-validate; surface conflicts.** Disagreement between publishers is information.
5. **Be polite.** Rate-limit, cache, real User-Agent, honour robots.txt.

## Verify and stop

Per target: URLs tried → status → rows → span → `data_through` → validation against the
figures quoted above.

```
git commit -m "feat(acquire): fearnpulse full-history backfill + china/indonesia/argentina/guinea/pilbara scrapers

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print before/after rows and `data_through` for every target, plus the full
34-tsId alive/dead probe table from Target 1.
