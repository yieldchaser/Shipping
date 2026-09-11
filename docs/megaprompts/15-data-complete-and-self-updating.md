# 15 — DATA COMPLETE AND SELF-UPDATING

**Read `00-GUARDRAILS.md` first.** Run after the Part-0 fix pass is committed and pushed.
Run order: **`14 → Part-0 fix → push → 15 → 16`**. This prompt absorbs Prompt 10 (data
currency). Prompt 16 absorbs Prompt 12 (tooltips + view layer).

---

## What the user sees when this is done

1. **Every module shows the latest month the free source has published** — August 2026
   wherever the source has released it — and it **stays current without anyone running
   anything**, because every fetcher is wired into a scheduled GitHub workflow.
2. **Who Feeds China shows tonnes**, not only USD — iron ore, coal, crude, soybeans, LNG,
   grain, copper concentrate and fertilisers, monthly, 2018 → August 2026.
3. **New modules** for the flows still missing: crude and product tanker flows by country
   (JODI), US LNG exports (EIA), India coal imports (TradeStat), and Australia exports by
   state and destination (ABS).
4. **Badges say `Source · through 2026-08`** instead of "LIVE OFFICIAL", and anything
   stale says so.
5. **`docs/DATA_COVERAGE.md`** — generated, not typed — a commodity × country × source ×
   `data_through` matrix, so anyone can see what's covered at a glance.

Work in the order below. Parts A and B matter most.

---

## PART A — Wire every dataset into a scheduled updater (the most important part)

### The audit (2026-09-11)
All GitHub workflows run green, but **11 Round 2 scripts are called by no workflow at all.**
When pushed, every one of these modules freezes on the day it was built:

| Script | Workflow |
|---|---|
| `scripts/acquire/fetch_indonesia_coal.py` / `fetch_bps_exim.py` | only `bps_monthly.yml` (new, never run on GitHub) |
| `fetch_argentina_grain.py` | **none** |
| `fetch_world_steel_production.py` | **none** |
| `fetch_minor_bulks.py` | **none** |
| `fetch_brazil_comexstat_full.py` | **none** |
| `fetch_china_customs_demand.py` | **none** |
| `fetch_guinea_bauxite.py` | **none** |
| `fetch_fleet_supply.py` | **none** |
| `fetch_usda_grain_queues.py` | **none** |
| `backfill_fearnleys_depth.py` (writes `fearnleys_benchmark_rates_continuous.csv`) | **none** |
| `scripts/cargo/build_cargo_cache.py` — builds the whole Cargo tab | **none** |
| `scripts/verify/build_provenance_manifest.py` | **none** |

### Two workflows will actively damage data after the push
1. **`usda_weekly.yml` → `scripts/scrapers/fetch_usda_grains.py`** downloads the old
   Socrata dataset `uiht-9xts` straight into
   `data/commodities/usda_grain_vessel_loading_queues.csv`. That dataset **ends in 2020**
   and uses `MM/DD/YYYY`. On its first Friday run it would overwrite 13's rebuilt file
   (ISO dates, 1995–2026, loading / waiting-to-load columns). **Remove that entry from
   `fetch_usda_grains.py`, and call `fetch_usda_grain_queues.py` from `usda_weekly.yml`.**
   Check the other Socrata entries in that script the same way: any file a Round 2 script
   now owns must have exactly one writer.
2. **`data_expansion.yml` runs `build_geospatial_tracker.py` daily.** Confirm the
   synthesis block removed in Prompt 14 is gone from the committed file, so the job can't
   regenerate the fake lineup CSV.

### The fix
1. Create **`.github/workflows/monthly_trade_flows.yml`**: cron on the **8th, 16th and 24th
   of each month** plus `workflow_dispatch`. Release days vary by source; three runs a
   month let each fetcher detect new periods itself. One step per fetcher, each with
   `continue-on-error: true`, writing its result (new periods / no change / error + message)
   to `data/provenance/updater_status.json`. Then `build_cargo_cache.py`, then
   `build_provenance_manifest.py`, then commit and push. Follow the commit/rebase pattern
   the existing workflows use.
2. Secrets needed: `BPS_API_KEY`, `EIA_API_KEY`, `COMTRADE_API_KEY` — all already exist
   as repo secrets. Pass them as env vars. Never echo them.
3. Fearnleys: the daily `data_expansion.yml` refreshes `fearnpulse_dry_routes_full.csv`,
   but the 34-series continuous CSV has no refresher. Add an **incremental** refresh
   (append new dates only; never re-download 28 years every day) to the daily job.
4. Each fetcher must be **idempotent**: re-running with no new source data changes nothing
   and makes no commit.
5. Test it for real: once pushed, run `gh workflow run monthly_trade_flows.yml` and paste
   the run URL and `updater_status.json` into the ledger.

---

## PART B — Pull the latest month now, and label currency honestly

### B1. August 2026 is already out for some sources — pull it
Checked 2026-09-11:

| Source | Latest in repo | Available now |
|---|---|---|
| Brazil ComexStat API (`api-comexstat.mdic.gov.br/general`) | 2026-07 | **2026-08** — responding again, iron ore Aug = 34.4 Mt |
| China customs, national tonnes (GACC bulletin, Part C1) | — | **2026-08** |
| chinadata.live (USD by origin) | 2026-07 | 2026-07 (up to date) |
| Port Hedland PDFs | 2026-07 | Aug not published yet (404) |
| BPS Indonesia | 2026-07 | Aug due mid-September |
| worldsteel | 2026-07 | Aug due late September |

Use ComexStat directly for 2024 → latest. The Comtrade backfill stays for 2017–2023.

### B2. Data currency (absorbs Prompt 10 §10.1–10.3)
- Every manifest entry gets **`data_through`** (computed from the file — never typed),
  **`staleness_sla_days`** (weekly 14, monthly 45, quarterly 120, daily 5) and
  **`staleness_state`** (FRESH ≤ SLA · AGEING ≤ 2× · STALE ≤ 6× · DORMANT beyond).
- **42 of 112 series currently have no computable date span** (mostly JSON views). Give
  each a real `data_through`, or mark it `reference` (static data, no SLA).
- `status: LIVE` requires FRESH or AGEING.
- Replace the all-caps status pills ("LIVE OFFICIAL", "LIVE HARBOR MASTER", "LIVE
  MIRROR STATISTIC" — 22 of them) with one neutral provenance line:
  **`Source · through 2026-08`**. STALE shows amber with the age; DORMANT shows red.
- Module titles that state a span ("31-Year History 1995–2026") are generated from
  `date_span`.
- Finish Prompt 10 §10.25 (bunker source mismatch) and §10.3 (`MM/DD/YYYY` files:
  `usda_us_vs_brazil_landed_costs.csv`, plus anything the Socrata fetcher still writes).

---

## PART C — Close the remaining coverage gaps (sources verified 2026-09-11)

All of these fetched successfully from a plain script on 2026-09-11 unless noted.

### C1. China imports in tonnes — GACC monthly bulletin (highest value)
The query platform is bot-protected, but **the bulletin pages are static HTML**:
- Index: `http://english.customs.gov.cn/statics/report/preliminary.html` (latest months)
  and `.../monthly.html` (the full bulletin, year selector 2018–2026).
- The row **"(6) China's Major Imports by Quantity and Value (in USD)"** links each month
  to a page like
  `http://english.customs.gov.cn/Statics/1c29d265-76bf-4a44-9867-224c6ba7ec52.html`
  (August 2026). The hrefs are unquoted in the HTML, so parse accordingly.
- The table has columns: commodity · unit (**10,000 tons**) · month quantity · month value ·
  YTD quantity · YTD value · YoY %. Rows include iron ores, coal and lignite, crude
  petroleum, refined products, natural gases, soya beans, grain food, copper ores,
  fertilizers, logs.
- For history, use the monthly bulletin's **"(14) Major Import Commodities in Quantity and
  Value"** for each year back to 2018.

Output `data/commodities/china_major_imports_tonnes.csv`. Wire it into **Who Feeds China**:
national tonnes as the main line. Keep the chinadata.live by-origin shares as a separate,
clearly labelled **USD** view. By-origin *tonnes* remain unavailable without the query
platform; say so in one line.

### C2. Crude and product tanker flows by country — JODI Oil
`https://www.jodidata.org/_resources/files/downloads/oil-data/world_primary_csv.zip`
(23 MB zip, CSV columns `REF_AREA, TIME_PERIOD, ENERGY_PRODUCT, FLOW_BREAKDOWN,
UNIT_MEASURE, OBS_VALUE, ASSESSMENT_CODE`). Latest period **2026-06**. Also a secondary
(products) file on the same downloads page. Build a **Tanker Flows** module in Cargo:
crude exports for the main exporters (Saudi Arabia, Russia, Iraq, UAE, US, Brazil, Norway,
Kuwait, Canada) and imports for the main importers (China, India, Japan, Korea, EU members,
US), monthly, kb/d. Respect `ASSESSMENT_CODE` (JODI's data-quality flag): show it, and
don't treat estimated values as reported.

### C3. US LNG exports — EIA
Monthly by point of exit: `https://www.eia.gov/dnav/ng/ng_move_poe2_a_EPG0_ENG_Mmcf_m.htm`.
Use the EIA API with `EIA_API_KEY` for the series; the HTML is the fallback. By
destination country if available. **LNG Exports** module: monthly, with a seasonal envelope.

### C4. India coal imports — Ministry of Commerce TradeStat
`https://tradestat.commerce.gov.in/meidb/commodity_wise_all_countries_import` — a normal
form with a CSRF token (GET the page, read the token, POST the form). HS 2701 (and 2702),
monthly, **quantity and value by origin country**. That covers Indonesia / Australia /
Russia / South Africa → India, the second-largest coal lane. Add it to the Indonesia Coal
module as "India's side", or give it its own module.

### C5. Australia exports by commodity, destination and state — ABS
`https://data.api.abs.gov.au/rest/data/ABS,MERCH_EXP/all?startPeriod=2026-07&endPeriod=2026-07`
with header `Accept: application/vnd.sdmx.data+csv`. Dimensions: `COMMODITY_SITC` (337
codes), `COUNTRY_DEST` (200), `STATE_ORIGIN` (11), monthly, **AUD thousands only — no
tonnes**. Data through **2026-07**. Use it for destination mix and state split: Queensland
vs NSW coal (SITC 321/322), iron ore (281), LNG (343), wheat (041), bauxite/alumina
(285). Label everything as value.

### C6. Parked — say so honestly in DATA_COVERAGE.md
- **China imports by origin in tonnes** — GACC query platform (Ruishu anti-bot).
- **Queensland port tonnes** (NQBP) — Cloudflare. ABS covers the value side.
- **Ukraine / Russia grain** — minagro.gov.ua is behind Cloudflare. Check whether Comtrade
  has monthly Ukraine exports (reporter 804, HS 1001/1005) with an acceptable lag. If so,
  use it; if not, park it.

The operator can do a browser capture for any of these later. Don't block on them.

---

## PART D — Coverage matrix, generated

`scripts/verify/build_coverage_matrix.py` → `docs/DATA_COVERAGE.md`. One row per
commodity × flow (export / import) × country: source, unit (tonnes vs value),
`data_through`, `staleness_state`, updater workflow, and module. Built from the manifest
plus a small reference map of commodity → series_id. Run it inside `monthly_trade_flows.yml`
too. **This is the answer to "is everything covered?", and it must never be typed by hand.**

---

## Gate and boundary

- Full `pytest tests/ -q` green · `check_no_fabrication.py` exit 0 ·
  `check_source_citations.py` exit 0 · 12-tab regression.
- `monthly_trade_flows.yml` has run once on GitHub, green (paste the run URL).
- Boundary report: `DATA_COVERAGE.md` pasted in full, plus screenshots of Who Feeds China
  (tonnes), Tanker Flows, LNG Exports and India Coal.
