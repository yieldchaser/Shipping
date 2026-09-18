# Cargo & Trade Flows tab — audit, verified root causes, and work order
Reviewed 69 screenshots of `#tab-cargo` (yieldchaser.github.io/Shipping, 17 Sep 2026) and cross-checked against
the code and data on `main`: `index.html`, `scripts/cargo/build_cargo_cache.py`,
`data/cargo/commodity_flow_matrix.json`, `data/derived/fearnleys_fixtures_full.csv`,
`data/commodities/*.csv`.

**How to read this file**
- **[VERIFIED]** — I found the defect in the code/data; the cause is stated with file and line/row evidence.
  Fix as described, but confirm the evidence yourself first.
- **[INVESTIGATE]** — the screen looks wrong; you have better access than I do. Check it, then either fix it or
  reply with evidence that it is correct.
- Every item says what "done" means.

**Standing rules for this round**
1. No fabricated, simulated, estimated, defaulted or placeholder value may be displayed without a visible label.
2. A tab with no data renders an explicit empty state. Never leave the previous dataset on screen.
3. Every value badge prints the period the value belongs to.
4. No hardcoded numbers, dates, row counts or spans in the UI or builders — derive from the data.
5. If a series can be extended with more effort (older customs files, older PPA/worldsteel/FBX history),
   extend it rather than starting at an arbitrary recent date.
6. Where a number is computed, not reported (mirror, derived, share-based), label it in the card, not only in a
   tooltip.

---

# P0 — wrong numbers currently on screen

## 1. [VERIFIED] Brazil seasonal envelopes are corrupted by a unit heuristic
`build_cargo_cache.py` → `process_brazil_exports()`:
```python
mt = val / 1_000_000.0 if val > 50_000 else val / 1000.0
```
Any month below 50,000 t is treated as if it were already in kt, inflating it 1000×.
Evidence from `brazil_comexstat_exports.csv`:
- Soybeans 2021-01 = **49,499.05 t** → rendered as **49.5 Mt** (this is the impossible January max on screen 9490).
- Raw Sugar 2023-02 = **5,612.40 t** → rendered as **5.61 Mt** (the February max on screens 9491 and the Minor
  Bulks sugar panel).
- Crude Oil 2022-02 = **0.03 t** → ≈0 Mt (the zero floor of the crude band on screen 9489).

**Fix**: delete the heuristic. Units are known per file — convert explicitly (`metric_tonnes / 1e6`). Audit every
other `if val >` unit guess in the builders and remove them too.
**Done when**: no envelope band can be outside the min/max of that commodity's own yearly values (add a unit test),
and the soybean January max is ≈2.9 Mt.

## 2. [VERIFIED] Two bad source rows in `brazil_comexstat_exports.csv`
`Crude Oil 2022-02 = 0.03 t` and `Raw Sugar 2023-02 = 5,612.40 t` are both wrong (real values are ~4–6 Mt and
~1.5 Mt). Re-pull those months from ComexStat and add a validator rule: a monthly value below 20% of the trailing
12-month median fails the build.
Also: the `2026-07` and `2026-08` rows have **empty `source` and `method`** columns — backfill them.

## 3. [VERIFIED] Barley and Sorghum tabs keep the Soybeans chart
`index.html` → `renderUsdaExportSalesChart()`:
```javascript
var env = envs && envs[_usdaSalesCmd];
if (env) { ...render... }      // no else: canvas and badge keep the previous commodity
```
and `build_cargo_cache.py` → `process_usda_export_commitments()` only emits an envelope when
`len(w_dict) >= 50`, so commodities whose name doesn't match or that have fewer weeks never appear.
**Fix**: (a) in the builder, log the distinct `commodity` values found in
`usda_fas_outstanding_export_sales.csv` and map the tab labels to them exactly (FAS names them e.g. "Barley",
"Sorghum" — confirm); (b) in the UI, destroy the chart and show "No FAS commitments reported for X" when the
envelope is missing. Apply the same empty-state rule to every toggle in the tab.
**Done when**: each of the five tabs either shows its own series or an explicit empty state, and the badge name
always matches the selected tab.

## 4. [VERIFIED] Fixture matrix volumes and vessel classes are not real measurements
From `commodity_flow_matrix.json` and the ledger:
- The ledger has **no quantity column**. Cargo size is embedded in free text:
  `commodity = "12,000 MT PPL"`, `"1,800 MT Butane"`. Grain/coal/ore rows mostly have no MT token, so their
  volume sums are near-zero (Grain 50,577 fixtures → `total_qty_mt: 2615.4`), while LPG rows parse and are then
  scaled as if they were kilotonnes (Butane 730 fixtures → 1,769.6 on screen).
- Limestone 1,934 fixtures → 220 Mt (114 kt per Supramax) is the same unit defect in the other direction.
- `top_vessel_classes` is degenerate: Grain = Panamax 50,577 (i.e. **all** fixtures), Coal = Capesize 22,217
  (all fixtures) — the class is being assigned by commodity rule, not read from the ledger's `segment` column
  (which contains real values: `HGC`, `VLGC`, `SGC`, …).
- `recent_monthly_fixtures` is an all-zero array for Grain and Coal — the monthly trend is broken.

**Fix**:
- Parse quantity with its unit from the text (`([\d,]+)\s*(MT|KT|CBM|BBLS)`), store `qty_t` and `qty_source`,
  count how many fixtures have a parsed quantity, and **display coverage** ("volume from 8,412 of 50,577
  fixtures") next to any volume. Never sum nulls as zero.
- Derive vessel class from `segment` (and DWT where present), not from the commodity.
- Fix `recent_monthly_fixtures` (it is keyed to months but never filled for most commodities).
- Add a cargo-size sanity test per class (e.g. Capesize 120–220 kt, Panamax 55–90 kt, Supramax 30–65 kt,
  Handysize 15–40 kt); fail the build when a group's mean size is outside its band.
**Done when**: every displayed volume has a coverage figure, and no group's mean cargo size is physically impossible.

## 5. [VERIFIED] Corridors are not unparsed data — the mapper is failing
The ledger **does** carry `load_port` and `discharge_port` (`Ruwais → Options East`, `Sines → Terneuzen`,
`Singapore → OPTS China`), yet `commodity_flow_matrix.json` shows
`"Unspecified Origin -> Unspecified Destination": 495,144 of 546,131` fixtures.
**Fix**: build a port → region gazetteer (start from the most frequent 300 raw strings, which will cover the bulk),
normalise "OPTS/Options/Opts X" to "options — X region", and report mapping coverage in the card.
**Done when**: mapped corridors exceed 60% of classified fixtures, and the card shows the mapped share.

## 6. [VERIFIED] 53.2% of fixtures are unclassified (290,570 of 546,131)
Metadata confirms it. The classifier only reads the `commodity` text; the ledger also has `department`
(`LPG`, …), `segment`, `charterer`, `route`, and a `comment` that repeats the original cargo description.
**Fix**: extend the classifier to use those fields; track `unclassified_pct` over time in the build log; target
under 25%. Keep the unclassified bucket visible and honest.

## 7. [VERIFIED] The freight spread badge/series is hardcoded to fall back to 0
`index.html` line ~17873:
```javascript
gulfPnwSpread: parseFloat(row.Gulf_PNW_Spread || ... || 0) || null
```
and the badge prints `+$${latest.spread ?? 0}/MT`, which is why screens 9516–9519 read **"Spread: +$0/MT"** with
no yellow line. **Fix**: compute `spread = gulfToJapan - pnwToJapan` when the column is absent, and render "—"
when either leg is missing. Never print `+$0` as a fallback.

## 8. [VERIFIED] Number formatting uses the browser locale
`index.html` contains 24 bare `toLocaleString()` calls (e.g. the commitments badge), which on an en-IN browser
prints `1,87,49,824 MT`, `2,90,570`, `45,59,421`, `13,49,049 MT/wk`. **Fix**: pass `'en-US'` everywhere (or a
shared `fmt()` helper) and prefer Mt/kt over raw digits.

## 9. [INVESTIGATE] Port Hedland destination panel shows the wrong month (screens 9492–9494)
Title reads "July 2026" and the badge "LIVE 2026-07 DISCLOSURE", but the numbers are August (China 38.00 Mt of
46.60 Mt total; our Hedland July total is 44.225 Mt). Check which row the panel reads and derive the label from it.

## 10. [INVESTIGATE] "Port of Dampier" tab renders the Hedland chart (screen 9493)
Selecting Dampier leaves the Hedland series and the "Port Hedland: 46.6 Mt/mo" badge. Dampier data exists
(2002-07 → 2026-08, iron ore and total throughput). Fix the toggle; show iron ore and total separately, since the
KPI strip conflates them (item 12).

## 11. [INVESTIGATE] Major-miners chart mixes bases and hides illustrative rows (screen 9494)
- "Major Miners: 284.14 Mt (2026 Q2)" adds Rio Pilbara (100%), Vale (100%), BHP (equity share) and Fortescue
  (100%) — four bases. Sum one basis or stop summing.
- The 26 `illustrative_prior_estimate` rows are drawn identically to the 14 filing-verified rows. Hatch/grey them,
  add a legend entry, and put provenance in the tooltip.
- Vale (Brazil) sits inside a card titled "Pilbara Ports … & Miner Shipments" — retitle or split.

## 12. [VERIFIED] KPI strip mixes iron ore with total throughput
"Iron Ore Run-Rate 95.9 Mt/mo — Brazil 34.4 | Pilbara 61.5": 61.5 = Hedland iron ore 46.605 + Dampier **total
throughput** 14.841. Dampier iron ore is 12.800, so the like-for-like figure is 59.4 Mt.
Also in the strip: "USDA Grain Commitments 68.3k Records" is a row count, not a market metric (replace with
outstanding commitments in Mt + week-ending date); "546k Fixtures" vs the section header "540,640" (the JSON says
546,131 total and 255,561 classified — pick one definition and label it); "C3 vs C5 … (2026-09 average)" is a
partial month — label MTD or use the last full week.

## 13. [INVESTIGATE] "Port Stock 65% Est (Mt)" and the Capesize spot spike (screen 9526)
An estimated inventory series is plotted next to real prices, dotted, with large gaps. Either source it (Mysteel /
SteelHome weekly China port iron-ore inventory) and label it, or remove it. Separately, the Capesize spot line
peaks near **$120,000/day**, while the 2018–2026 record is about $86,000/day (Oct-2021) — check for a unit or
outlier defect, and don't start the axis at −$20,000/day.

---

# P1 — missing data, stale provenance, broken features

## 14. [VERIFIED] Provenance strings are hardcoded and stale
`build_cargo_cache.py` hardcodes provenance text, e.g. the Guinea pair:
```python
"volume_source": "UN Comtrade (Reporter: China, Partner: Guinea HS 260600) to 2024-12; SMM reports of GACC data after"
```
and Brazil `"span": "2024–2026"`, USDA commitments `"span": "1999–2026"`, plus the UI's hardcoded
"68,181 historical weekly rows" and "18,152 rows" (inspections, now 77,695 certificates).
The node-audit tiles repeat the same stale story: Bauxite/Alumina "UN Comtrade Mirror HS 260600", Fertilizers /
Cement / Scrap / Nickel "Fixture derived", Crude "EIA … (PADD 3)" (WCREXUS2 is the **US total**, not PADD 3),
Coal omitting Indonesia BPS, Grains omitting FGIS and MAGyP.
**Fix**: derive every provenance string, span, as-of date and row count from the data at build time, from one
source registry shared with the scrapers. Delete every hardcoded span/row-count/source sentence in `index.html`
and the builders.
**Done when**: changing a source in the registry changes the tiles and footers with no other edit.

## 15. [VERIFIED] Destination data is computed but never shown
`process_usda_export_commitments()` builds `top_destinations` per commodity, yet the card titled
"Weekly by Commodity × Destination" shows totals only. Either show the destination breakdown or retitle.

## 16. [INVESTIGATE] Series start later than the available data
Check each and extend (or state why not):
- Hedland flagship starts 2023-01 (data from 2015-08); Dampier from 2002-07.
- Guinea mirror chart starts 2023-01 (mirror data now 2017-01) and the bar/CIF chart starts 2023-08.
- "Who feeds China" starts 2023-08 (chinadata.live has 2021-01).
- World crude steel starts 2024-01 (worldsteel publishes decades — backfill 2015+).
- Argentina MAGyP starts 2023-08 (older crop-year folders exist).
- FBX tab shows only 2026-03 → 2026-09 while the card claims "21Y CONTINUOUS BENCHMARK / 2005–2026".
- Minor-bulk panels say "5Y Historical Range" but Alumina/Nickel/Urea/Fertiliser/Sugar only have 2022–2025.
  Backfill 2017–2021 from the same national sources, or rename the control to the actual span.

## 17. [INVESTIGATE] Guinea flagship card content
Provenance text, the "2017 is left out" note and "HS 260600" are all superseded. The Ministry of Mines ledger
(182.8 Mt 2025; SMB 70.0 / Other 37.4 / Chalco 22.1 / CBG 17.4) has **no document link** — add the publication URL
and date or remove the table. Add one line explaining why China's imports (148.8 Mt) differ from Guinea's exports
(182.8 Mt). For the empty freight panel, confirm whether any Baltic/FFA West-Africa bauxite route exists; if not,
say so in the panel instead of leaving it blank.

## 18. [INVESTIGATE] USDA vessel queues — PNW (screen 9517)
Only "Vessels In Port" is drawn; "Loaded (Past 7 Days)" and "Vessels Due (Next 10 Days)" are blank in GTR for PNW,
yet the badge prints "0 Due (Next 10D)" as if it were a real zero. Show "n/a" and note the reporting difference.
There is also a visible gap around 2025-12 — backfill those weeks.

## 19. [INVESTIGATE] Indonesia coal headline definition (screens 9496–9497)
Subtitle says the official headline excludes lignite; the badge "38.9 Mt/mo" includes it (ex-lignite 29.02 Mt).
Pick one, label it, show both in the tooltip.

## 20. [INVESTIGATE] Australia REQ card (screens 9500–9504)
Titled "& FORECASTS" with no forecast drawn (REQ publishes two years of forecasts — add as a dashed series or drop
the word). Tab tooltips show filler text ("Maritime intelligence module and analytics view for LNG/Met Coal") and
appear on the wrong tab. Latest bar is 2026 Q1 but the badge doesn't say so; x-axis labels stop at 2025 Q4.

## 21. [INVESTIGATE] Landed soybean transport cost (screen 9525)
No as-of period on "US $110.2/MT | Brazil $131.6/MT | Spread −$21.4/MT" — USDA ERS lags 6–9 months, so the period
must be visible. X-axis labels stop at 2025-03 while the series continues.

## 22. [INVESTIGATE] Taxonomy grouping errors in the matrix
- Salt, Gypsum, "General Minerals" sit under **Steel & Metals** (screen 9482).
- Iron Ore / Iron Ore Fines / Iron Ore Pellets are separate rows; Coal is split into Coal / Met Coal / Thermal /
  Anthracite; "Fertilizers (Combined)" duplicates Urea and Phosphate. Roll up to parent groups with drill-down.
- Potash shows 47 fixtures — a major Panamax/Supramax trade, so the classifier is missing it.
- "Coverage Status" prints HIGH COVERAGE / BROKER REPORTED with no stated rule — define it or remove it.

## 23. [VERIFIED] The matrix has no usable time dimension
`recent_months` runs 2020-01 → 2026-xx but `recent_monthly_fixtures` is zero-filled for the major commodities, so
every count on screen is all-time. **Fix**: populate the monthly arrays and add a period selector (last 4 weeks /
12 months / YoY) plus a vessel-class split, so the matrix can be compared with BCI/BPI/BSI/BHSI.

---

# P2 — labels and presentation

24. Corridor titles vs data: "US Gulf Coast Terminals (Mississippi River) → Japan / South Korea" plots all Gulf
    inspections to all destinations; same for Newcastle → Qingdao and Hedland → Qingdao. Either filter to the
    corridor's destinations (FGIS has destination; PPA has destination JSON; Newcastle has destinations) or
    retitle as "basin volume (all destinations)".
25. The USG legend still says "top-20 destinations" — no longer true after the FGIS backfill.
26. Badges missing periods: "Alumina 0.37 Mt/mo", "Sugar 2.22 Mt/mo", "Newcastle Coal 12.63 Mt/mo (2026)",
    "Iron Ore 34.41 Mt/mo (2026)", "China 76.9 Mt", world-steel YoY.
27. Flagship provenance prints "As-of 2026-09-08" while data runs to 2026-09-10/16 — derive it.
28. Minor-bulks footer "UN Comtrade Bilateral Customs Ledgers & MDIC ComexStat" is stale; show per-panel sources.
29. Newcastle card titled "Thermal & Met Coal" but the series is total port coal with no split.
30. Russian coal tagged "Rail/Overland" in the who-feeds-China card, though most Russia→China coal is seaborne.
31. Year toggles read "2024, 2023, 2022, 2024" (duplicate label, 2021 missing) on several seasonal cards.
32. Raw axis numbers ("7500000 MT", "40000000 MT") — format as Mt/kt.
33. The "Site updated: reload for the latest build" toast covers chart area in several screens — auto-dismiss or
    move it.
34. Sugar is defined two ways (all NCM 1701 vs raw 17011300+17011400) and the two charts look identical; define
    once and label. Alumina is labelled HS 2818 but filled from `28182000` — state it.
35. "Who feeds China" is USD value, not tonnes, with the disclaimer in small text; put "value, not tonnage" in the
    card title, and consider adding tonnes (a quarterly GACC export can include iron ore `26011100`, coal
    `27011100`, soybeans `12019000` by partner).

---

# Structural work — what the tab needs to actually predict BDI / BDTI

36. **Ton-miles, not just tonnes.** Add an origin→discharge distance matrix and publish monthly ton-miles per
    corridor and per vessel class. Volume alone does not drive the indices.
37. **Tanker demand is effectively absent** (1,595 crude and 47 LNG fixtures in the whole ledger). Add official
    series: EIA weekly US crude/product exports by PADD; China crude/LPG/product imports (chinadata.live value,
    GACC quarterly export for tonnes); India PPAC monthly crude imports by source; Japan METI and Korea KESIS
    crude/LNG imports; JODI monthly. Present them as ton-mile proxies for VLCC/Suezmax/Aframax lanes.
38. **Supply side.** Congestion (you already have USDA queues; add China iron-ore/coal port waiting if a free
    feed exists) and fleet growth/deliveries/scrapping (UNCTAD and Equasis publish free aggregates).
39. **Lead/lag panel.** For each corridor, show the correlation of volume and ton-miles against the matching
    Baltic route at 0/2/4/8-week lags, computed from data already stored.
40. **Data-quality strip per card**: source, as-of, and the share of the displayed series that is reported vs
    derived vs illustrative. This tab mixes all three today and the distinction is invisible.

---

# Verification required before you report back
1. **Tests**: envelope containment (item 1); cargo-size bands per vessel class (item 4); no chart may render a
   series whose commodity/port label differs from the selected toggle (items 3, 10); every badge value traceable
   to a row in the underlying CSV; no `toLocaleString()` without a locale; no hardcoded span/row-count strings.
2. **Validator additions**: near-zero monthly outliers (item 2), impossible cargo sizes (item 4), envelope
   containment (item 1).
3. **Screenshots**: re-run the Playwright pass over every card listed here and attach before/after images for
   items 1–13.
4. **Report**: for each [INVESTIGATE] item, state what you found (fixed / not a defect + evidence). For item 16,
   list which history backfills succeeded and which sources refused to go further back.
5. **No new placeholders**: if a fix cannot be completed, leave the card empty with an explicit "no data" state
   rather than a default value.
