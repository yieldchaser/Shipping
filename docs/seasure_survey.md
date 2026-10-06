# Seasure Summary Sales - per-source survey + extraction (corpus/archive/other)

Measured 2026-10-07 by the source-by-source cron (job 12f7fa574166). Branch
`auto/extract-fixes-2026-10-06-deepreview`. Source: `corpus/archive/other/`.
Runner: `scripts/extract/publishers/run_seasure.py` (per-source, not generic).

## What it is

`corpus/archive/other/` was carved by the hourly job into 5 publications. This is the
largest recurring one: **Seasure "Summary Sales", 86 PDFs, 2021(24) 2022(49) 2023(13)**.
3 pages per doc, every one. Identified by `seasure` / `summary sales` in the text layer
(the 8 unclassified `other_YYYY_Week-NN` files and dnf/psarras/upoil/hellenic are NOT Seasure
and the runner skips them: `is_seasure()` gate).

## Three-baseline test (is it already ours?)

Absent from the live feeds/series CSVs, from our md tier, and from `index.html`
(measured by the hourly sub-classification, `docs/archive_other_survey.md`).
=> **GENUINELY_MISSING**. Newest content **2023-03-31** -> **BACKFILL_ONLY** (>180 d).
Value = historical depth only; never CONSTRUCT.

## Shape / layout (rendered-page fingerprint)

* Page 1: Summary Sales deal grid, sections **BULKER / TANKER / CONTAINER**, plus a
  right-hand vector "Weekly Spend by Country / Ship Type" bar chart (phase 1 = md; chart not
  typed). Pages 2-3: PERIOD / CHARTERING / NEWBUILDINGS / CURRENCIES / INDICES tables.
* Grid columns (x0, pdf pt), **verified identical in 2021 and 2023** samples:
  `Name~17  Type~107  DWT~150  Yard~182  Built~240  USD mill~276  Comments~313  VV~383  Buyer~404  Seller~497`.
  Anchors are re-derived per page from that page's OWN header tokens (self-calibrating), not hardcoded.
* The grid is a TEXT-LAYER table (positioned text, 1 embedded raster = the logo). The **Yard** and
  **Comments** columns WRAP onto extra lines, so linear text order is unusable - extraction assigns
  words to the nearest row by y and to their column by an x-boundary derived from the header anchors.
* Row pitch ~7.9 pt; a **`-1.5%` / `+2.4%` weekly-change token** is printed in the VV x-column,
  ~7.6 pt below the last row of each section - it is NOT deal data (excluded by band + percent filter).

## Number convention

**ISO** in both years: `58,100` = 58100 DWT (comma = thousands); `15.8` = 15.8 USD mill (period =
decimal). No European mixing. Percentages (`-1.5%`) are section change markers.

## Measured extraction result (trial + reconcile)

* Trial on 2 docs from different years (2021-10-01, 2023-02-03), rows compared to the rendered page
  text: **2021 18/18 rows, 2023 12/12 rows**; name_verbatim 18/18 and 12/12; price_verbatim 18/18 and 12/12.
  Spot values match the page exactly (e.g. Conrad 207,600 DWT / 55.0 USDm / VV 58.6 / USA -> Oceanbulk).
* Two real bugs found by the trial and fixed before bulk: (1) header tokens are one-per-dict-line, so
  same-line detection missed the header -> now grouped by y; (2) a greedy row band absorbed the next
  section heading + repeated header row + the percent token into the last row of a section (produced
  `dwt=None`, `VV=-1.5`) -> tight bands (hi <= ry+7.0) + heading/header/percent exclusion.

## Deliverables

* `data/extracted/md/seasure/<year>/<stem>.md` (PRIMARY full text) + `.tables.json` (deals)
* `data/extracted/series/seasure_sales_series.csv` - one row per vessel:
  issue_date, section, vessel_name, type, dwt, yard, built_year, price_usd_m, price_raw, comments,
  vv_raw, buyer, seller, source_file, page. (Richer than allied/golden_destiny: carries BOTH buyer and seller.)
