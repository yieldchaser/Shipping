# PROMPT 07 — NEW TAB: CARGO & TRADE FLOWS

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-07-cargo.md`
> Depends on: Prompts 01, 02, 03 complete. **Prompt 02 Jobs A, B and D must have reported back.**

---

## Why this tab exists

Every rate on every other tab is downstream of one question: **what physically moves, from
where, in what volume.** That data currently sits orphaned inside a Signals accordion called
"Upstream Commodity Flows & Port Logistics", which is the wrong home — it is not a trading
signal, it is the demand driver underneath the signals.

It does not belong in TRACKING (vessels and ports) or BROKER DESK (rates and assets).
It gets its own tab. Position it **after TRACKING, before BUNKERS** in the nav.

**This tab's question:** *what cargo is moving, from which origin, and is that normal for
the time of year?*

---

## ⚠ Hard precondition

Three of the series this tab was going to be built on were **quarantined in Prompt 02 as
fabricated** — Guinea bauxite, Brazil iron ore envelope, and the upstream freight driver
matrix. The Guinea numbers were transcribed off a chart image.

**Do not un-quarantine them. Do not reconstruct them. Do not "estimate" replacements.**

Build this tab only from series that Prompt 02 re-acquired and registered with
`status: "LIVE"` or a properly documented `status: "ESTIMATED"`. Any series still
`UNAVAILABLE` gets a visible empty state saying so, naming the source we tried and failed
to reach. An honest gap on this tab is worth more than the entire rest of it.

---

## Design reference — the seasonal envelope is this tab's whole grammar

`Inspiration/` images `HN-0BL4awAAh6c5.jpg` (wheat), `HPl_oNDaoAA_y3_.jpg` (sulphur on
water), `HRB7GH5bkAIqwvq (1).jpg` (Brazil iron ore), `HRBi9G-a8AAK2dq.jpg` (Guinea bauxite)
all use one pattern, and it is the right default for every chart on this tab:

- grey shaded band = previous 5-year min/max range
- orange line = previous 5-year average
- current year bold, prior year secondary
- older years greyed in the legend and **click-toggleable back on**
- unit selector (Kt / Mt), frequency tabs (D / W / M / Q / Y), YoY toggle, CSV download

It answers *"is this volume normal?"* instantly. A bare line never does. Build this as one
reusable component and use it everywhere on this tab.

Also see `HQoKTiRa4AIcErr.png`: stacked cargo tonnage by vessel class (Capesize /
Newcastlemax / VLOC / Valemax) with a **freight rate overlaid on a right axis** (C14 China–
Brazil round voyage). Volume and the price it drives, on one chart. That is the pattern for
the flagship module below.

---

## PHASE 7.1 — Tab scaffold

Create the tab, nav entry, lazy-load path, and the reusable **SeasonalEnvelope** component
described above. Component contract: takes a monthly or weekly series plus its
`hist_5y_min/max/mean`, renders band + mean + current + prior years with toggles, and reads
its provenance header for the source strip. Every chart on this tab uses it.

---

## PHASE 7.2 — Receive the 9 modules from SIGNALS

| Module | Rebuild note |
|---|---|
| Brazilian Bulk Seaborne Exports (MDIC ComexStat) | **rebuild on Prompt 02 Job B output** — the old envelope CSV is quarantined |
| Pilbara Ports (Port Hedland & Dampier) & Miner Shipments | `australia_ppa_iron_ore.csv` + `major_miners_quarterly_shipments.csv` |
| US Gulf Coast (PADD 3) Seaborne Petroleum Exports (EIA weekly) | `us_eia_weekly_crude_exports.csv`, 75 KB, real |
| USDA Bulk Grain Ocean Freight (US Gulf vs PNW to Japan) | `usda_bulk_grain_ocean_rates.csv` |
| USDA Grain Vessel Loading & Port Queues (Gulf vs PNW) | `usda_grain_vessel_loading_queues.csv` (108 KB) |
| Landed Soybean Transportation Cost to China (US vs Brazil) | `usda_us_vs_brazil_landed_costs.csv` (49 KB) |
| Cargo Demand Drivers — World Bank Commodity Prices | `data/macro/commodities_monthly.csv` |
| Leading Restocking Pressures (Port Stocks vs Spot Rates) | `data/derived/iron_ore_restocking.csv` |
| Capital Link Container Index (CLCI) & Global Container Freight | 21-year continuous benchmark |

Every one converts to the SeasonalEnvelope pattern where it is a volume series.

---

## PHASE 7.3 — Wire the unused flow data

| File | Rows | Span | Module |
|---|---|---|---|
| `usda_fas_outstanding_export_sales.csv` | **68,181** | 1999 → 2026 | **Weekly export commitments by commodity × destination.** The single biggest unused cargo dataset we hold. Note: the file is **unsorted** (first row 2026-08-27, last 1999-09-02) — sort on read. |
| `usda_ytd_grain_inspections_top20.csv` | 18,152 | 2025 → 2026 | Grain inspections by port |
| `usda_grain_vessel_loading.csv` | — | 1995 → 2026 | 31-year loading queue history |
| `newcastle_coal_exports.csv` | — | — | Australian thermal coal |
| `australia_req_commodity_exports.csv` | — | 2000 → 2026 | Quarterly official forecasts, 15-sheet model |
| `data/cache/req_jun2026_hist.xlsx` | — | 2000 → 2026 | REQ historical workbook |
| Prompt 02 Job A output | — | — | Guinea bauxite **if and only if re-acquired** |
| Prompt 02 Job B output | — | — | Brazil iron ore + soy + corn |
| Prompt 02 Job D output | — | — | USDA FAS API, Argentina/Rosario |

---

## PHASE 7.4 — Flagship module: Origin → Freight

Build one module that earns the tab: **cargo volume by origin, stacked, with the
corresponding freight route overlaid on a right axis.**

- Brazil iron ore exports vs **C3 (Tubarão–Qingdao)**
- West Australia iron ore (Port Hedland) vs **C5 (Dampier–Qingdao)**
- Guinea bauxite vs **C14 / Atlantic Capesize** — *only if Job A succeeded*
- US Gulf grain vs **Panamax USG–Japan**

We already hold both sides: the volume series above, and the route rates in
`fearnleys_benchmark_rates_continuous.csv` (34 curves, 1,158 dates, 2018–2026) which
explicitly includes C3 (`tsId 10001`), C5 (`tsId 10002`) and Newcastle/Qingdao coal
(`tsId 10003`).

This is the chart that shows *why* freight moved, which is the entire purpose of the tab.

**Constraint:** plot only what was reported. Do **not** compute ton-miles, do not build a
utilisation model, do not add a slider. The Ton-Mile Absorption Simulator was deleted in
Prompt 03 for exactly this reason — a model whose output moves because you moved its input
is a toy, and its Guinea input was fabricated. Volume and rate, both observed, side by side.
Correlation is for the reader to see, not for us to assert.

---

## PHASE 7.5 — Commodity coverage: the fixture-derived flow matrix ★

**The problem this solves.** We hold a *complete* cargo taxonomy but volume series for only
a handful of commodities. Signal Ocean's taxonomies cover **154 dry bulk nodes** and
**1,212 tanker nodes** — every grain (barley, corn, oats, rice, rye, sorghum, soybeans,
wheat), every coal grade (anthracite, metallurgical, thermal), every iron ore form
(concentrate, fines, lumps, pellets, magnetite), bauxite, alumina, all 11 fertilizers,
every steel product, petcoke, scrap, nickel ore, spodumene, and on the wet side gasoline
by RON grade, ULSD, jet, naphtha, condensate, fuel oil, LPG grades.

But national-customs volume series exist for maybe eight of them. Acquiring 150+ national
export series is not realistic, and most do not exist as free monthly APIs.

**We already hold observed flows for all of them — in the fixture ledger.**
`data/derived/fearnleys_fixtures_full.csv` has 540,640 broker-reported fixtures with a
`commodity` column. These are *reported cargo movements*, not a model. Aggregating them by
commodity, month and trade lane gives genuine coverage across the whole taxonomy.

### Verified state of that column — read this before building

Sampled 250,002 rows:
```
BLANK commodity : 151,215  (60% — this is the headline problem)
Coal 6,801 · Grain 2,333 · CPP 2,300 · Wheat 2,110 · Iron Ore 1,502 · Bulk 1,281
Grains 1,279 · General Cargo 1,172 · Steels 1,058 · Clinker 1,040 · "44,000 MT LPG" 1,020
Dirty 1,017 · DPP 979 · Corn 821 · "GRAIN CLEAN" 805 · Steel 621 · Gypsum 606
ULSD 576 · Urea 569 · Petcoke 567 · Bauxite 550 · Salt 542 · Crude Oil 531 · Cement 516
```

Three data-quality facts you must handle, and must **not** paper over:
1. **60% of fixtures have no commodity.** Report the coverage rate on the chart itself.
   Never imply the matrix is complete.
2. **Values are unnormalised.** `Grain` / `Grains` / `GRAIN CLEAN`, `Steel` / `Steels`,
   `General Cargo` / `GENERAL CARGO` / `General cargo`. Quantity is sometimes glued into
   the field (`"44,000 MT LPG"`). Trade shorthand appears alongside commodity names
   (`CPP` = clean petroleum products, `DPP` = dirty petroleum products, `UMS` = unleaded
   motor spirit).
3. **Load/discharge ports are mostly trading regions, not ports.** 1,418 distinct
   `load_port` values, **81% blank**, and the top values are `MEG`, `USG`, `WAFR`, `BOT`,
   `CPC`, `AG`, `ECM`, plus country names (`BRAZIL`, `NIGERIA`, `GUYANA`). **Do not
   attempt a naive join to the 12,060-port database.** Build a region normaliser
   (MEG → Middle East Gulf, USG → US Gulf, WAFR → West Africa, ECM → East Coast Mexico …)
   and aggregate at **trade-lane level**, which is the resolution the data actually supports.

### Build
1. **A normalisation map**, `data/reference/commodity_normalisation.json`, from raw fixture
   strings → Signal taxonomy nodes. Hand-authored, versioned, reviewable. This is
   legitimate reference data (GUARDRAILS F1 permits static reference mappings) — but it maps
   labels, it **never invents a volume**.
2. **Commodity Flow Matrix** — fixture count and, where the rate/quantity field allows,
   tonnage, by commodity × month × trade lane. Filterable down the taxonomy tree
   (Energy → Coal → Metallurgical). Every cell shows its underlying fixture count so the
   user can see thin data as thin.
3. **Coverage panel** — for each taxonomy node: do we have (a) a national volume series,
   (b) fixture-derived flow only, or (c) nothing. This makes the gap visible and turns
   "what should we acquire next" into a data question instead of a guess.
4. **Unclassified bucket rendered explicitly** — the 60% blank is shown as its own band,
   never silently dropped. A matrix that hides 60% of its input is a lie by omission.

### On acquiring more commodity sources
The recommendation is **fixture-derived first, targeted acquisition second**. Once the
coverage panel exists, acquisition becomes evidence-led: chase a national customs series
only for commodities that are both high-tonnage and thin in fixtures. Do **not** open a
generic hunt for 150 national export APIs — most do not exist free, and the ones that do
are already listed in `docs/Newest Data/Maritime_Data_Discovery_Report.md`.

**On ports: no acquisition is needed.** We hold 12,060 routing ports, 2,752 terminals and
2,066 PortWatch ports. The constraint has never been port coverage — it is that the UI
renders 36 of them. That is a rendering problem, solved in Prompt 05.

---

## PHASE 7.6 — Provenance discipline

This tab is where fabrication happened. It carries the strictest display rules in the app:

- **Every** chart shows a source strip: source name, fetch method, span, as-of date.
- Any `ESTIMATED` series carries a visible **EST.** badge and its derivation is one hover away.
- Any `UNAVAILABLE` series renders an explicit empty state naming the source we tried.
- A mirror statistic (e.g. China-reported imports standing in for Guinea-reported exports)
  must say so on the chart, not only in the manifest.

---

## PHASE 7.7 — Verify and stop

- Every rendered series resolves to a provenance entry with status LIVE or ESTIMATED.
- No series traces back to `data/_quarantine/`.
- `python scripts/verify/check_no_fabrication.py` exits 0.
- No text below 11px; no pane with >48px trailing space.

```
git commit -m "feat(cargo): new Cargo & Trade Flows tab on re-sourced primary data

- SeasonalEnvelope component (5y range band, 5y mean, YoY toggles) as the tab default
- 9 upstream modules relocated from signals and rebuilt
- 68,181-row USDA export commitments wired; grain inspections; REQ; Newcastle coal
- flagship origin-to-freight module: cargo volume vs its Baltic route rate
- quarantined series render explicit empty states, never reconstructed

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print every series on the tab with its status and source, and list any that
render an empty state.
