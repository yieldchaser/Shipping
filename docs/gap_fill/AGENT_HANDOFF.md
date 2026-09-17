# Cargo & Trade Flows — Data Handoff for the Coding Agent
Prepared 2026-09-17 against `yieldchaser/Shipping@main`, after a full gap-fill of
`cargo_trade_flows_audit.md`. Read this before touching any scraper.

**Rules for the agent**
- Do not change a data source to an "easier" one without checking it still reproduces the
  existing series. Every source below was validated against the repo; the validation result is stated.
- Never write estimates into a row that claims a primary source. If a month cannot be fetched, leave it
  missing and log it.
- Everything marked **[recon]** was found by hand (browser DevTools, trial requests). It is not
  documented anywhere else. Use it; don't rediscover it.

---

## 0. Apply the gap-fill first (one-off)

| Patch file (in `patches/`) | Target | How |
|---|---|---|
| `australia_ppa_iron_ore__FULL_REPLACEMENT.csv` | `data/commodities/australia_ppa_iron_ore.csv` | Replace file. Hedland now 2015-08→2026-08, Dampier 2002-07→2026-08, zero gaps. Hedland 2021-07 is a press-release value (PPA never posted the PDF). |
| `minor_bulks_monthly__ADD_ROWS.csv` | `data/commodities/minor_bulks_monthly.csv` | Append. 64 rows. After this every series is continuous 2022-01→2026-07. |
| `guinea_bauxite_exports__ADD_ROWS.csv` | `data/commodities/guinea_bauxite_exports.csv` | Append (11 monthly mirror rows, GACC). |
| `guinea_bauxite_exports__REPLACE_2017_ROWS.csv` | same file | **Delete** the 12 existing 2017 `monthly_bilateral_mirror` rows (flat CIF 300.91) and insert these. |
| `brazil_comexstat_exports__ADD_ROWS.csv` | `data/commodities/brazil_comexstat_exports.csv` | Append Aug-2026. Optionally apply `__JUL26_REVISIONS.csv` (MDIC revised July). |
| `us_eia_weekly_crude_exports__ADD_ROWS.csv` | `data/commodities/us_eia_weekly_crude_exports.csv` | Append 2026-09-04, 2026-09-11. |
| `usda_ytd_grain_inspections_top20__ADD_ROWS.csv` | `data/commodities/usda_ytd_grain_inspections_top20.csv` | Append 58,937 rows (2023-2024, 2025-09-11→2025-12-31, 2026-09-10). |
| `usda_fas_outstanding_export_sales__ADD_ROWS.csv` | `data/commodities/usda_fas_outstanding_export_sales.csv` | Append week 2026-09-03. |
| `minor_bulks_turkiye_TURKSTAT_GENERAL_2013_2026.csv` | optional | Full TurkStat general-trade series for cement + scrap (identical to the Comtrade series, gap-free, fresher). |

Reference-only: `fgis_port_region_monthly_Mt.csv`, `guinea_*_vs_*.csv`, `turkstat_hs2523_hs7204_monthly_usd.csv` (special trade — do **not** use for the series, see §2.10).

Then rebuild `cargo_frontend_summary.json` (`scripts/cargo/build_cargo_cache.py`).

---

## 1. Ongoing source map (what to fetch every period)

"Lag" = when month M normally becomes available. "Auto" = can run in GitHub Actions.

| # | Dataset / file | Source & endpoint | Cadence / lag | Auto? | Validated |
|---|---|---|---|---|---|
| 1 | Brazil exports `brazil_comexstat_exports.csv`, minor-bulks Sugar, NPK imports | MDIC ComexStat REST `POST https://api-comexstat.mdic.gov.br/general` | Monthly, ~1st–7th working day of M+1 | Yes | Exact vs repo |
| 2 | PPA `australia_ppa_iron_ore.csv` | pilbaraports.com.au PDFs (see §2.2) | Monthly, ~mid M+1 | Yes, **needs headless Chromium** | 40/40 + 178/178 exact |
| 3 | US crude exports `us_eia_weekly_crude_exports.csv` | `https://www.eia.gov/dnav/pet/hist_xls/WCREXUS2w.xls` (no key) or EIA API v2 (key) | Weekly, Wed/Thu for prior Fri | Yes | 1,742 weeks exact |
| 4 | Newcastle coal `newcastle_coal_exports.csv` | TfNSW CKAN `resource_show?id=3c5c9d89-ce54-4f72-9550-4077b7540612` → xlsx URL | Monthly, ~mid M+1 | Yes | existing script fine |
| 5 | Indonesia coal `indonesia_coal_exports_monthly.csv` | BPS `https://webapi.bps.go.id/v1/api/dataexim/` (needs `BPS_API_KEY`) | Monthly, ~mid M+1 (release ~15th–20th) | Yes | not re-checked |
| 6 | Guinea bauxite mirror (`guinea_bauxite_exports.csv`, monthly_bilateral_mirror) | chinadata.live (USD) + GACC published table (total t) + SMM (partner t) — §2.6 | Monthly, ~18th–25th of M+1 | Yes (Chromium for GACC table) | SMM ≤0.6%, derived ±2% |
| 7a | Minor bulks – Urea (India HS 3102 imports) | India TradeStat (DGCI&S) `https://tradestat.commerce.gov.in/meidb/commoditywise_import` | Monthly, ~M+1.5; latest month "(F)" provisional | Yes | 5 months exact |
| 7b | Minor bulks – Nickel ore (Philippines HS 2604 exports) | PSA OpenSTAT PXWeb API (§2.7) | Monthly, ~M+1.5; latest month suffixed "P" | Yes | 7 months exact |
| 7c | Minor bulks – Alumina (China HS 2818 imports) | chinadata.live (USD, exact) + SMM (tonnes) — §2.6 | Monthly, ~20th–31st of M+1 | Yes | chinadata within 0.1% of GACC |
| 7d | Minor bulks – Scrap (Türkiye HS 7204 imports) & Cement (Türkiye HS 2523 exports) | TurkStat Qlik, **general trade** app (§2.10) | Monthly, end of M+1 (~last working day) | **No** (engine 503s cloud IPs) | exact, 35 + 47 months |
| 7e | Minor bulks – Sugar, NPK | ComexStat (row 1) | Monthly | Yes | exact |
| 8 | Australia REQ `australia_req_commodity_exports.csv` | DISR REQ historical-data xlsx (§2.8) | Quarterly: Mar, Jun, Sep/Oct, Dec | Yes | — |
| 9 | Argentina grain `argentina_grain_*` | MAGyP embarques pages (§2.9) | Monthly, irregular (Aug-26 still 404 on 2026-09-17) | Yes | — |
| 10 | USDA FAS ESR `usda_fas_outstanding_export_sales.csv` | Socrata `https://agtransport.usda.gov/resource/885i-uek7.csv` | Weekly (Thu data, lands ~following Thu/Fri) | Yes | — |
| 11 | USDA inspections `usda_ytd_grain_inspections_top20.csv` | Socrata `5sxb-qe7q` **+** FGIS raw `https://fgisonline.ams.usda.gov/ExportGrainReport/CY{YYYY}.csv` | Weekly, Monday after the Thursday week-ending | Yes | FGIS = Socrata to 1 t |
| 12 | USDA vessel queues | `https://www.ams.usda.gov/sites/default/files/media/GTRTable19_Figure19.xlsx` | Weekly (Thu GTR) | Yes | — |
| 13 | USDA grain freight (GTR) / landed costs | AMS GTR datasets / USDA ERS | Monthly / quarterly, ERS lags 6–9 months | Yes | — |
| 14 | "Who feeds China?" `china_customs_monthly_imports.csv` | `https://chinadata.live/api/v2/trade/hs/{hs}?flow={flow}&period=all` (third-party GACC mirror, **USD value only**) | Monthly | Yes | — |
| 15 | World crude steel `world_crude_steel_monthly.csv` | worldsteel press releases `https://worldsteel.org/media/press-releases/{YYYY}/{month}-{YYYY}-crude-steel-production/` | Monthly, ~22nd–25th of M+1 | Yes | — |
| 16 | Major miners `major_miners_quarterly_shipments.csv` | SEC EDGAR 6-K exhibits (Vale, Rio Tinto, BHP) via `edgartools`; ASX announcements API (Fortescue) — §2.13 | Quarterly: ~2–4 weeks after quarter end | Yes | **All 40 current rows are placeholders — rebuild** |
| 17 | FGIS / Fearnleys / Baltic / container / Pink Sheet / SGX | unchanged, audit shows healthy | — | Yes | not touched |

---

## 2. Source notes [recon] — what a scraper must know

### 2.1 Brazil ComexStat
- Body example: `{"flow":"export","monthDetail":true,"period":{"from":"2026-07","to":"2026-08"},"filters":[{"filter":"ncm","values":["26011100"]}],"details":["ncm"],"metrics":["metricFOB","metricKG"]}`. Imports: `"flow":"import"` and add `"metricCIF"` (repo NPK value = **CIF**, verified exact).
- **Rate limit**: HTTP 429 ("tente novamente em 10 segundos") — space calls ≥15 s, retry with back-off.
- `period.from`/`to` spanning two calendar years returned an **empty list**. Query one year per call.
- Filter `"heading"` / `"sh4"` did not work; pass explicit 8-digit NCM lists. Sugar 1701 = `17011200,17011300,17011400,17019100,17019900`. NPK 3105 = `31051000,31052000,31053000,31054000,31055100,31055900,31056000,31059011,31059019,31059090`.
- MDIC revises the prior month (July-26 iron ore 35.18 → 35.00 Mt). Re-pull the last 2 months each run and overwrite.

### 2.2 Pilbara Ports Authority
- Site is behind **Imperva/Incapsula**: plain HTTP gets a 212-byte JS challenge with status 200. Detect it (body < 1 kB or no `%PDF` header) and never treat it as data.
- Headless Chromium passes the challenge: load `https://www.pilbaraports.com.au/` first, wait ~5 s, then use the same browser context for everything (`context.request.get` for PDFs).
- Index pages (crawl all `a[href*='.pdf']`):
  - Hedland: `/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports`
  - Dampier: `/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports`
- File names are unreliable (`_1.pdf`, `-(1).pdf`, 2023 files in `/2022/`, one Hedland file under `/photo gallery/`). **Assign port by index page, date by text inside the PDF.**
- Hedland monthly: "Cargo Stats by Destination" PDF. Use the destination page (text contains `by Destination`); header `Departure Date: MM/DD/YYYY to …` (the origin page uses DD/MM). Sum the **Iron Ore** column over countries; the printed "Total" row misparses in some layouts — use the row sum.
- Cross-check file: "Cargo, GRT and DWT statistics by commodity type" (vessel level; Iron Ore group footer `N distinct visit(s)…` → 3rd decimal number = export tonnes).
- Dampier: no monthly PDFs; **financial-year YTD tables** (`YYYY - YYYY FINANCIAL YEAR`, rows by month name, column 1 = IRON ORE, column 10 = TOTAL CARGO, `-` = 0). The same month appears in several YTD files; keep the one from the file with the most months.
- Not published anywhere on the site: Hedland 2021-07 (filled from press: 44.3 Mt).
- A working implementation is in `scripts/fetch_australia_ppa.py` of this package; if Imperva blocks the GitHub runner, run it locally.

### 2.3 EIA
- The xls has sheet `Data 1`, skip 2 rows. Weekly values are Friday-dated.

### 2.4 Newcastle
- CKAN `last_modified` tells whether the new month is in; the xlsx name is dated (`port-of-newcastle_YYYYMMDD.xlsx`). Aug-26 not yet on 2026-09-17.

### 2.5 USDA
- **Inspections**: Socrata `5sxb-qe7q` only holds 2025-01-02 onward and is **missing 2025-09-11 → 2025-12-31 upstream**. FGIS raw yearly CSVs (`CY2023.csv` … `CY2026.csv`, ~10–12 MB, latin-1) contain every certificate. Mapping: `Thursday`→date, `Pounds`/2204.62262→mt, `Grain`,`Class`,`SubClass`,`Destination`,`AMS Reg` (strip spaces). USDA `week` = ISO week − 1 (0 → 53). Use FGIS as the fallback for any week Socrata lacks. FGIS files get revised (Jan-25 Gulf: repo 6.24 vs FGIS 7.39 Mt) — decide whether to re-pull the current year each week.
- **Socrata paging**: order by a unique key (`date DESC, :id`), otherwise `$offset` pages repeat/skip rows.
- **FAS ESR** `885i-uek7`: new week appears ~1 week after the Thursday.
- **Vessel queues** GTR Table 19: new row every Thursday GTR.

### 2.6 China customs (GACC) — Guinea bauxite by partner, China alumina imports — ZERO-TOUCH DESIGN
**Constraint**: the GACC query platform (`stats.customs.gov.cn`) is the only official source of partner-level tonnes, and every query sits behind a human slider CAPTCHA (`/queryData/toCaptchaView`). Do **not** automate or solve it. (Its data call `POST /queryData/getQueryDataListByWhere` also carries an anti-bot token; replays return an empty body.) The design below reaches the same numbers from four public channels, each verified on 2026-09-17.

**Channel A — chinadata.live (exact USD, automated, plain HTTP)**
- `GET https://chinadata.live/api/v2/trade/hs/{code}?flow=import&period={all|YYYY}` accepts 4-, 6- and **8-digit** codes. Use `26060000` (bauxite) and `28182000` (alumina).
- `monthly[]` = China total import value per month, from 2021-01. Verified against the user's GACC exports: within 0.1% for every month (small GACC revisions).
- `latest_partners[]` = partner split (USD) **for the last month of the requested period only**; `period=all` → latest month, `period=2025` → Dec-2025. Guinea = `partner_code 221`. Verified: Guinea 2025 total and Australia Dec-2025 match GACC to the dollar.
- No quantities anywhere in this API. Poll after ~20th of M+1 and **store Guinea USD for the new month each run** — history cannot be re-pulled later.

**Channel B — GACC published monthly tables (official total tonnes, automated, headless Chromium)**
- Index per year: `http://www.customs.gov.cn/customs/302249/zfxxgk/fdzdgknr/302274/302277/{YYYY}/index.html` (older year example: `…/302277/6348926/index.html` = 2025). Preliminary tables ("统计快讯"): `…/302274/302275/index.html`.
- First request returns HTTP 412 + JS challenge; headless Chromium passes it (load `http://www.customs.gov.cn/customs/302249/zfxxgk/2799825/302274/index.html`, wait ~6 s, then navigate). Plain HTTP fails.
- Table to use: link text `（14）{YYYY}年{M}月进口主要商品量值表（美元值）` (published ~18th of M+1; article URL pattern `/customs/{YYYY-MM}/18/article_*.html`).
- Row `铝矿砂及其精矿 | 万吨 | qty | value(千美元) | ytd qty | ytd value | yoy% …` → China total bauxite imports. Unit 万吨 = 10 kt. Verified Jan-2025: 1,621 万吨 vs query platform 16.14 Mt.
- **Alumina (氧化铝) is not in any published table** — only in the query platform.

**Channel C — SMM (secondary, quotes GACC partner tonnes, automated)**
- SMM (`news.metal.com`) publishes monthly "Monthly Import Data of Bauxite in China for {Month} {Year} (Including Country Rankings)", "[Aluminum Express - {Month} Bauxite Imports] According to the General Administration of Customs…", and alumina import/export analyses.
- Discovery without a paid search API: Google News RSS works, e.g. `https://news.google.com/rss/search?q=China+bauxite+imports+Guinea+site:news.metal.com&hl=en-US&gl=US&ceid=US:en` (also try `alumina imports`). Filter by pubDate ≥ 15th of M+1.
- Article pages return gzip — request with compression enabled (`curl --compressed` / `requests` handles it). Parse sentences like "imported X million mt of bauxite from Guinea" / "alumina imports … X mt".
- Accuracy vs the user's GACC exports: SMM Guinea figures within 0.6% for 8 overlapping months (see `guinea_bauxite_exports__GACC_vs_SMM_REVISIONS.csv`).

**Channel D — derived Guinea tonnes (automated fallback when SMM has no article)**
- `guinea_t = china_total_t (B) × guinea_usd / china_total_usd (A) × 0.982`
- Backtest on 19 months (2025-01→2026-07): the raw ratio over-states by +1.8% median (Guinea ore is cheaper than the average origin), range −0.5%…+3.9%; the 0.982 factor removes the bias (residual about ±2%). Label `method = derived_value_share`, never as GACC.
- **Do not derive alumina** this way: alumina unit value swung $420–$2,000/t across 2025 months (small specialty cargoes), so value ÷ price is unreliable. Leave tonnes null if SMM is silent.

**Precedence (write the best available, overwrite when better arrives)**
1. User GACC export (if ever supplied) or UN Comtrade (reporter 156 once it catches up, 12–18 months later) — `provenance = GACC`.
2. SMM quote (C) — `provenance = SMM/GACC`.
3. Derived (A+B+D) — `provenance = derived_value_share`, bauxite only.
Keep `value_usd` from A in every case. Re-evaluate the last 3 months on every run.

**Export format if the user does supply files** (optional, quarterly is enough): GB18030 CSV, header `数据年月,商品编码,商品名称,贸易伙伴编码,贸易伙伴名称,第一数量,第一计量单位,…,美元|人民币`; 千克 = kg; Guinea = `几内亚` (exclude `几内亚比绍`, `巴布亚新几内亚`). If the last header is `人民币`, convert with FRED `EXCHUS` monthly (`https://fred.stlouisfed.org/graph/fredgraph.csv?id=EXCHUS`). Alumina code `28182000` (the repo series is labelled HS 2818 — pick one definition).

### 2.7 PSA OpenSTAT (Philippines)
- `POST https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/{table}` with JSON query, `"response":{"format":"csv"}`. **403 unless a User-Agent header is set** (e.g. `curl/8.5.0`). Decode latin-1.
- Quantity tables `2L/IMT/QPE/…`, FOB tables `2L/IMT/FOB/…`. Table IDs change per year (2026 `0012L4DXQD5`/`0012L4DXVD5`, 2025 `0022L4DXQD4`/`0022L4DXVD4`, 2022 `0052L4DXQD1`/`0052L4DXVD1`) — list `2L/IMT/QPE` to discover the current year's ID each January.
- The commodity dimension has no value list in metadata. Get codes by requesting all commodities for one country/period in json-stat2 and reading `dimension['Commodity Code'].category.label`; select labels starting `2604`. **The selection uses the index keys, not the labels.** Codes differ by year (`26040000001/2` in 2025–26, `2604000001` in 2022).
- Quantity is kg; sum across all countries. Month columns look like `2026 JulyP` (P = preliminary).

### 2.8 Australia REQ
- `fetch_australia_req.py` has the **June-2026 xlsx URLs hard-coded**. The September 2026 REQ (due late Sep/early Oct) adds 2026 Q2. The agent must discover the latest release from the DISR REQ landing page instead of hard-coding.

### 2.9 Argentina MAGyP
- Monthly pages live in crop-year folders: `.../embarques_interanual/mensual-2025-2026/07_julio_2025-2026.php`. The folder rolls over with the marketing year; the existing script discovers links from the index — keep that, don't hard-code.
- Aug-2026 page returned 404 on 2026-09-17 (not yet published).

### 2.10 TurkStat (Türkiye cement exports, scrap imports)
- Old `biruni.tuik.gov.tr/disticaretapp` redirects to a **Qlik Sense mashup**: `https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1` (general trade) / `report_type=2` (special trade).
- Data goes over a WebSocket (`wss://bi.tuik.gov.tr/app/{appId}?…&qlik-csrf-token=…`). From this analysis environment the engine handshake returned **HTTP 503** every time, so a cloud runner will likely fail; an ordinary browser works.
- App IDs:
  - General trade (**use this**): `bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42` — has `MIKTAR_1` (kg), `DOLAR`.
  - General trade, second app: `5c4bcee9-7cec-4c39-98b7-ab35ae0938fd` — no quantity field.
  - Special trade: `8db826a9-59f2-4a33-a91e-88ca417dddf9` (has quantity) and `9a61ad7c-bf94-4990-85ba-8abb18372a4b` (no quantity).
- Key fields: `YIL` (year), `AY` (month), `TARIFE4`, `IHRITH_FLAG` (1 = exports, 2 = imports), `MIKTAR_1` (kg), `DOLAR` (USD), `ULKE_KODU/ULKE_ADI`.
- **General trade equals the repo/Comtrade series exactly** (cement 35 months, scrap 47 months). Special trade cement is 0.925× — do not mix the two.
- The Report builder's Excel export only has USD; quantity is only reachable through the engine (`createCube` with `Sum({<[TARIFE4]={'2523'}>} [MIKTAR_1])`).
- Current method: user runs `scripts/tuik_browser_pull.js` in DevTools on the `report_type=1` page (downloads `tuik_by_flow.csv`, 1 row per year×month×flow). Agent: write the ingester for that CSV (kg ÷ 1000 = t). If the agent wants to try automation, a headful Playwright session that loads the mashup page and runs the same JS via `page.evaluate` is the only route; test from the GitHub runner before relying on it.
- Secondary for scrap only: SteelOrbis monthly article "Turkey's scrap imports … TUIK" (rounded to 0.01 Mt; USD exact).

### 2.11 UN Comtrade (keep only where nothing better exists)
- Preview API `https://comtradeapi.un.org/public/v1/preview/C/M/HS?…&period=YYYYMM` accepts **one period per call**.
- India reporter code is **699** (356 returns nothing).
- The "missing months" were not 429s: Comtrade returns `primaryValue` with `netWgt`/`qty` null or 0. The scraper dropped them silently.
- Comtrade monthly coverage stops early: China 2818 → Dec-24; China←Guinea 260600 → Mar-25; Philippines 2604 → Sep-25; Türkiye 2523/7204 → Dec-25. Hence the national sources above.

### 2.12 World Steel
- URL pattern works per month; `fetch_world_steel_production.py` hard-codes 2024/2025/2026 loops (2026 capped at 7 months). Generalise to "all months up to latest available"; history before 2024 was never ingested (optional backfill).

### 2.13 Major miners (quarterly production / shipments)
- Checked on EDGAR full-text search (2026-09-17):
  - **Vale S.A.** CIK `917851` — quarterly "Production and Sales Report" furnished as **6-K** (e.g. filed 2026-04-17, 2026-07-22; a 6-K/A the same day). Filer agent prefix `0001292814`.
  - **Rio Tinto plc** CIK `863064` (and Rio Tinto Ltd `887028`) — quarterly operations review as **6-K** exhibit (1Q26 filed 2026-04-21 `ex1d21rt1q26results.htm`; 2Q26 filed 2026-07-15 `ex991results.htm`). Pilbara shipments are reported on a 100% basis.
  - **BHP Group Ltd** CIK `811809` — operational review as **6-K** (e.g. 2026-04-22, 2026-07-17). BHP's fiscal year ends 30 June, so "Q4 FY26" = Apr–Jun 2026. WAIO figures are given on both 100% and BHP-share basis — pick one and label it.
  - **Fortescue** is **not an SEC filer**. Use the ASX API: `GET https://asx.api.markitdigital.com/asx-research/1.0/companies/fmg/announcements?count=20` (JSON; the public endpoint returns only the ~5 most recent items, so poll weekly around the end of Jan/Apr/Jul/Oct and match headline "Quarterly"). PDF: `https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{documentKey}` (verified 200, application/pdf). Needs a browser-like User-Agent.
- `edgartools` works for listing 6-K filings and downloading attachments, but these reports are **not XBRL** — values must be parsed from the HTML/PDF tables (text search around "Iron ore", "shipments", "sales", "Pilbara", "WAIO"). SEC requires a descriptive User-Agent with contact email and ≤10 requests/s.
- Not every field exists every quarter: C1/unit costs are half-yearly for BHP and Rio; Fortescue reports C1 quarterly; guidance changes only occasionally. Allow nulls instead of carrying numbers forward.
- Backfill: same sources go back many years; rebuild 2024 Q1 onward first and set `provenance` to the filing accession / ASX document key.

---

## 3. Bugs found in the repo (point fixes — agent to implement)

1. **`major_miners_quarterly_shipments.csv` is not real data.** All 40 rows have `provenance=editorial_estimate_diagnostic`; `scripts/scrapers/fetch_major_miners_production.py` writes a hard-coded `EDITORIAL` list (typed-in numbers) whenever no IR feed parses — and none does. The audit rated this "Current / 0 gaps". Rebuild from filings per §2.13; until then the UI must say "illustrative".
2. **Guinea 2017 mirror rows**: tonnes = value ÷ a fixed 300.91 USD/t → volumes 6× too low (4.8 vs 27.6 Mt). Replacement rows supplied. Check whatever produced them for the same constant.
3. **Minor bulks**: `fetch_minor_bulks.py` hard-codes periods `2022-01 → 2026-07` (line ~125) — it will never pick up August. It also drops value-only Comtrade months silently. Series should move to the sources in §1 row 7.
4. **Minor bulks sugar definition break**: 2022 rows are all NCM 1701; 2026 rows are raw sugar only (17011300+17011400). Pick one and restate.
5. **`build_cargo_cache.py` ~L1160**: `len(gulf_weeks[m]) >= 4` discards real months. Use ≥3 or prorate by weeks present.
6. **`build_cargo_cache.py` ~L1110**: Pilbara corridor uses Hedland only. Now that Hedland is complete this is fine, but document it (or use Hedland + Dampier).
7. **`fetch_china_customs_demand.py` ~L203**: HS 72 rows get `date = "1-01"` and value 0 (month string without year; chinadata's HS-2 payload differs). 103 corrupt rows.
8. **`fetch_china_customs_demand.py`**: bauxite and alumina only from 2025 although chinadata.live has 2021-01 onward. It also uses 4-digit `2818`/`2606`; chinadata accepts 8-digit `28182000`/`26060000`, which match the minor-bulks and Guinea series definitions.
9. **Fearnleys fixtures**: max date 2026-12-18 (future) — date parse bug in `daily_fearnleys_sync.py`.
10. **USDA vessel queues**: week-00 parsing via `%W` drops 5 weeks (1999, 2010, 2016, 2021×2). Use the row date directly.
11. **FAS/Socrata paging**: order by a unique key (see §2.5).
12. **Hard-coded dates**: `fetch_australia_req.py` (Jun-2026 URLs), `fetch_world_steel_production.py` (2024–2026 loops), `fetch_argentina_grain.py` metadata block (`latest_month_july_2026`, fixed figures `jul_2026_corn_record_mt` etc.) — these go stale next month.
13. **Orphaned scripts** (never scheduled): `fetch_china_customs_demand.py`, `fetch_argentina_grain.py`, `fetch_world_steel_production.py`, `fetch_minor_bulks.py`. Wire them into a workflow after fixing #3/#12.
14. **Audit mislabels**: script is `fetch_un_comtrade_bauxite.py`, not `fetch_guinea_bauxite.py`; `fetch_australia_ppa.py` / `fetch_brazil_comexstat.py` are not at the paths the audit lists — confirm real paths.
15. **UI**: add `spanGaps: true` on flagship line datasets; Guinea corridor freight axis is 100% null by design — show a label instead of an empty axis.
16. **Scrapers must fail loudly** on bot-wall pages (PPA 212-byte challenge), CAPTCHA pages, CNY-instead-of-USD exports, and value-only rows.

---

## 4. Scheduling suggestion
- Weekly (Mon): ComexStat (last 2 months), PPA, Newcastle, BPS, India TradeStat, PSA, MAGyP, worldsteel, chinadata, REQ-discovery.
- Weekly (Tue & Fri): EIA; USDA inspections (Socrata + FGIS fallback), FAS ESR, GTR queues.
- Each run: log which expected months are still missing (Section 1 lag column) instead of silently skipping.

---

## 4b. Zero-touch plan for the three "manual" items

| Item | Why it isn't a plain cloud scraper | Zero-touch route |
|---|---|---|
| China GACC (Guinea bauxite by partner, alumina) | Query platform requires a human slider CAPTCHA on every query — do **not** bypass | Four-channel design in §2.6: chinadata.live USD (exact) + GACC published table total tonnes (Chromium) + SMM partner tonnes (Google News RSS discovery) + calibrated value-share fallback; Comtrade/user export overwrite later. No human step needed. |
| TurkStat Qlik (cement/scrap) | Engine WebSocket returned HTTP 503 from a cloud IP; browsers on residential IPs work | (1) Try once on GitHub Actions: Playwright loads `?report_type=1`, waits for the page, runs `scripts/tuik_browser_pull.js` logic via `page.evaluate`, captures the download. (2) If 503: run the same job on a **self-hosted GitHub Actions runner** on the owner's PC (scheduled, no human steps). (3) Scrap-only secondary: SteelOrbis monthly article. |
| PPA (Imperva) | Plain HTTP gets a JS challenge | Headless Chromium passed it from a cloud sandbox; use it on GitHub Actions. Fallback: same self-hosted runner. |

A self-hosted runner on the owner's machine removes every IP-based block in one step. The GACC CAPTCHA is avoided entirely by §2.6.


## 4c. MANDATORY end-to-end proof on GitHub Actions (do this before relying on any scraper)

Nobody has tested these jobs on GitHub-hosted runners yet. The agent must prove each one:

1. Build the scraper, then add a `workflow_dispatch` workflow `scraper_smoke_test.yml` that runs **each source separately** on `ubuntu-latest` (install Playwright Chromium + `poppler-utils` where needed).
2. Each job must assert real data, not just HTTP 200:
   - PPA: at least one PDF whose first bytes are `%PDF`, and the parsed latest Hedland month equals the value already in the CSV (e.g. 2026-08 = 46.605 Mt).
   - TurkStat: the Qlik cube returns ≥ 300 rows and 2026-07 cement exports = 2,494,622 t (general trade).
   - GACC published table (§2.6 B): the (14) table for 2026-01 parses `铝矿砂及其精矿` with a numeric quantity.
   - SMM via Google News RSS: at least one article found for the last 60 days and a number parsed.
   - chinadata.live, ComexStat, PSA, India TradeStat, EIA, FGIS, USDA Socrata, TfNSW, MAGyP, worldsteel, EDGAR, ASX: fetch the latest period and compare with the CSV.
3. Record the result per source in `docs/scraper_smoke_test.md` (pass/fail, HTTP status, error text). Save failing HTML responses as workflow artifacts.
4. Decision per source:
   - **Pass** → schedule it on GitHub-hosted runners.
   - **Fail with a block (403/412/503, challenge page, empty WebSocket)** → (a) switch the job to a self-hosted runner if the owner has installed one, **and** (b) turn on the fallback in §4d so the series never stalls.
5. Re-run the smoke test monthly; alert (open a GitHub issue) when a source flips from pass to fail.

## 4d. Fallback sources (automated, no human step) — measured accuracy

Use the fallback only when the primary fails or is late; mark `provenance` accordingly and let the primary overwrite later.

| Primary | Fallback | How to reach it | Measured vs primary |
|---|---|---|---|
| PPA PDFs (Hedland iron ore, Dampier iron ore/total) | PPA monthly throughput media release as republished by Port Technology International, Australian Mining, mining.com.au | Google News RSS `https://news.google.com/rss/search?q=%22Port+Hedland%22+iron+ore+exports+Pilbara+Ports&hl=en-US&gl=US&ceid=US:en`; parse "handled X million tonnes … including Y million tonnes of iron ore" | 2026-07 Hedland 44.2 vs 44.225; 2026-08 46.6 vs 46.605; Dampier total 14.7 vs 14.692, 14.8 vs 14.841 → ≤0.3%. No destination split. |
| TurkStat Qlik — **scrap** imports (HS 7204) | SteelOrbis monthly article "Turkey's scrap imports … according to TUIK" (`steelorbis.com/steel-news/latest-news/…`) | Google News RSS `q=Turkey+scrap+imports+TUIK+steelorbis`; parse month volume ("… to X million mt") and value ("… totaled $X million"). When a month is only given as YTD, derive = YTD − previous YTD | 2026-01…07: tonnes within 0.4% (0.01 Mt rounding), USD within 0.05% |
| TurkStat Qlik — **cement** exports (HS 2523) | No equal-quality public substitute found. Candidates for the agent to backtest before use: (1) UN Comtrade reporter 792 (exact, but currently ~8–9 months late — use as delayed overwrite); (2) mirror estimate from partner imports (Eurostat Comext API for EU reporters + US Census trade API, partner Türkiye, HS 2523) scaled by their historical share — accept only if backtest error ≤ 5% over 24 months; (3) TürkÇimento (turkcimento.org.tr) sector statistics — check whether monthly export tonnes are published | If none passes, leave the month empty until TurkStat or Comtrade provides it; do not invent |
| GACC query platform (Guinea bauxite, alumina) | §2.6 channels A–D | — | SMM ≤0.6%; derived ±2% (bauxite only) |
| Any other job | Keep the previous value empty and alert | — | — |

For cement this means: **if GitHub-hosted runners are blocked by TurkStat, the self-hosted runner is the only zero-touch primary** — tell the owner.

## 5. What the user (not the agent) has to do

| When | Task | Output to drop in the repo / hand to agent |
|---|---|---|
| Optional, quarterly | Only to replace SMM/derived bauxite and alumina figures with exact GACC values: stats.customs.gov.cn → Import · **US dollars** · months · **Monthly Display** · Commodity `26060000` / `28182000`, Trading partner blank → Export | CSVs → `scratch/gacc/` |
| Monthly — **only if the smoke test (§4c) shows TurkStat is blocked on GitHub and no self-hosted runner is installed** (cement only; scrap has a fallback) | Open `bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1`, F12 → Console, paste `scripts/tuik_browser_pull.js` | `tuik_by_flow.csv` → `scratch/tuik/` |
| Only if PPA blocks the GitHub runner | Run `python scripts/fetch_australia_ppa.py` locally | commit updated CSV |
| Once, optional | Install a GitHub self-hosted runner on your PC (Settings → Actions → Runners) so IP-blocked jobs run there automatically |  — |
| Once | Set `BPS_API_KEY` secret (already used) ; optional `COMTRADE_API_KEY`; optional `EIA_API_KEY` | — |

Everything else is automatic.
