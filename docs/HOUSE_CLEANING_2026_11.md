# House-cleaning pass, November 2026

A record of the clean-up done on 19–22 Nov 2026: what was found, what was changed, what was deliberately **not** done and why, and what still needs a person.

- **PR #54** (merged into `main`): data fixes, the tab restructure, and the Bunkers and Broker Desk passes.
- **PR #55** (merged): relative live cutoffs, EU ETS key wiring, the AIS-derived voyage history, and the fixes for three failing workflows (section 2a).
- **PR #56** (merged): installs the parquet engine the voyage-history builder needs in CI.
- **Regression tests:** `tests/test_house_cleaning_2026_11.py` and `tests/test_pages_artifact.py`.

## How the work was done

- **Screenshots.** Every tab was served locally and screenshotted at 1600 px and at 820 px wide. The Broker Desk and Bunkers tabs were also captured sub-view by sub-view.
- **Data checks.** Every number that looked odd was traced back to its data file and the script that writes it. GitHub Actions run logs were used to date when a feed broke.
- **Baseline tests.** The full test suite was run before any change: 22 failed / 1078 passed. Most of the failures are network- or CDN-blocked in the cloud sandbox.
  - After each batch of changes, the suite was re-run and compared against this baseline.
  - Final result: the same 22 failures and no new ones, plus `test_views_fresh` fixed by PR #55.
- **Merge conflicts.** Generated data files that conflicted with bot commits on `main` were regenerated with the builder scripts, never merged by hand.

## 1. Data that was wrong

| Area | What was wrong | Fix |
|---|---|---|
| Dashboard | The All-Time, 10Y and 5Y percentiles, the 10Y mean and the seasonal z-score were computed on the 5-year boot slice, so the same number appeared under three headings. | Load the product's full history view, then re-render. |
| BDRYFF / BWETFF futures | Solactive closes are stamped at 00:00 Berlin time but were read as UTC. Every row landed a day early: Sundays appeared, Fridays never did, and each week had a Sunday/Monday duplicate. Correlations with spot read about 0. | Convert in Berlin time. Let the batch close overwrite a same-day live quote. `scripts/repair/fix_solactive_dates.py` (idempotent) rebased the history. BDRYFF vs BDI correlation went from 0.09 to 0.44. |
| BWET premium/discount | Six rows were month/day-swapped and dated December 2026. | Removed them; the ingester now rejects future dates. |
| Cargo flagship corridors | Capped at a literal `"2026-09"`. The HUD had a typed-in fallback spread, and the fixture badge (547k) disagreed with the KPI (596k). | Capped at the current month instead; both values are now computed from data. |
| Bunkers headline | Showed the Oct 26 port average as today's price after the port feed stopped (see section 4). | Falls back to BunkerIndex World and says so. CI raises a warning while the port feed is stale. |
| EU ETS card | Hard-coded €72.50, and the "voyage penalty" was a literal $1,850. | Read from `eu_ets_carbon_daily.csv`, with its date shown and a "stale" flag. |
| Bunker forward curve | Its "as of" date was borrowed from another file. A spot anchor from a different feed was spliced in, creating a false "backwardation". | Uses the curve's own date. The anchor is used only if observed within 10 days of the curve. |
| Hi-5 spread | Computed from VLSFO and HSFO quotes a month apart (Augusta showed −$68). | Only same-week quotes are used. |
| Singapore bunker volumes | The "5-year envelope" was built on about two years of data, and its "latest actuals" line picked the oldest value. | Replaced with one line per year. |
| Fearnleys monthly series | 62 tanker routes switched from TCE ($/day) to WS/USD in 2023-05 under the same name and were merged into one series. Exact-zero "no assessment" days were averaged into monthly means (53 series affected). Example: VLCC MEG/FEAST TCE for 2023-03 showed $39,137; the true figure is $78,188. | One series per unit (sharing codes with the daily cache), and zero prints dropped when the month has real prints. |
| Broker Desk units | Every series is tagged "usd". LPG time-charter hire is quoted per month but was labelled per day, about thirty times too high. LNG placeholder prints of 0 and $1,000 were drawn as real rates. | Units inferred per series; placeholder runs are cut and noted in the legend. |
| Tanker Routes | Said "data to 2026-12-01" because a fixture count is stamped at its loading month. | Only assessment rows set the date. |
| Fleet orderbook | Stamped "as of" the current month and badged LIVE, but it is a one-off 2026-09 registry pull. | Labelled as a 2026-09 snapshot. |
| Vessel voyage history | No script wrote this view (stuck at 2026-09-25), and all 19,529 legs had departure = arrival + 3 days exactly, i.e. synthetic. | Rebuilt from the AIS archive (PR #55); the synthetic legs were dropped. |
| Offshore / ETFs | The offshore YoY label was wrong ("vs Aug '25 trough"), and ETF outflow bars had the wrong sign. | Fixed. |

## 2. Automation

- **Cargo workflow.** It was red on every run for 7+ weeks even though all scrapers succeeded. The freshness guard treated one cycle of publisher lag as a failure. Data one cycle behind is now reported as **LAG**; only data further behind fails the run.
- **Bunker collectors.** The forward-curve and sales-volume collectors existed but were never scheduled. They now run daily in `daily_update.yml`.
- **ICAP EUA backfill.** It had a hard-coded `C:\Users\Dell\...` path. It is now portable and runs weekly as a keyless fallback.
- **EU ETS live fetch (PR #55).** The workflow never passed `OILPRICE_API_KEY` to the script, so it could not run in CI; the rows up to 2026-09-03 came from local runs. The secret is now mapped into the step.
- **Voyage history (PR #55).** `scripts/geospatial/build_vessel_port_calls.py` rebuilds it daily in `scheduled_pipeline_sync.yml`, offline from the AIS archive.

## 2a. Failing workflows fixed (22 Nov)

Each fix was merged to `main`, and a run of each workflow was then watched to success.

| Workflow | Failure | Cause | Fix |
|---|---|---|---|
| Fast GitHub Pages Deploy | 8 failed deploys, 18–22 Nov: "No artifacts named github-pages were found" | The deploy step ran in the same job as the upload and asked for the artifact about 0.3 s after it finished, before GitHub had registered it. The artifact was 427 MB. | Upload and deploy are now separate jobs (`deploy` needs `build`), as in GitHub's Pages starter workflow. Raw files the site never loads are stripped before upload (parquet, the duplicate `bunker_master_historical.csv` copies, `port_calls_daily*`, the full Fearnleys dumps). The artifact is now 172 MB. `tests/test_pages_artifact.py` fails if a served page references a stripped file. |
| Scheduled Pipeline Sync | Crash on `15-03-2010` (21 Nov) | `backtest_macro_health_radar.py` let pandas guess the BDRYFF date format from the first row. After the Solactive date rebase that row became `01-03-2010`, which was read month-first. | The script now parses DD-MM-YYYY day-first explicitly. |
| Scheduled Pipeline Sync | `ImportError` on parquet (22 Nov, first run after #55) | The new voyage-history builder reads the AIS parquet archive, but the workflow installed no parquet engine. | `pyarrow` added to the install step (PR #56). |
| Broker Voice Sync | Every run since 19 Nov | `git add data/extracted/charts` exits 1: the path matches the `data/extracted/*` ignore rule, although its 1,795 files are tracked. | Falls back to `git add -u`. |

Runs watched to success: Pages 3270, 3275 and 3277; Pipeline Sync 74; Broker Voice Sync 140. Pages runs marked "cancelled" are deploys superseded by a newer one (`cancel-in-progress`), not failures.

Also fixed: one older `|| true` in `broker_voice_sync.yml` (on the paragraph clean-up step) silently swallowed failures and kept `test_broker_voice_workflow_runs_daily_and_fails_loudly` red. It now logs a warning, like the neighbouring steps, and the test passes.

## 3. UI and layout

- **Tabs.** 12 → 11: Yearly is folded into the Dashboard, and `switchTab('yearly-dash')` still works.
  - The tab bar is grouped: Markets | Instruments & desk | Physical | Research.
  - Sector pills show only on the tabs they drive.
- **Chart presets.** Several charts drew 18–40 years of data under a highlighted 3M or 1Y button. Fixed.
- **Bunkers.**
  - The filter toolbar is regrouped; the search box no longer sits alone on its own row.
  - The layout stacks below 1100 px.
  - Region/Grade/Status pills now show which is selected; they were targeting a non-existent class.
  - Composite cards respond to clicks.
  - The movers table shows 1W/1M/3M changes instead of repeating the strip above it.
- **Broker Desk.**
  - Seven sections had lost their titles; restored.
  - The Overview opens on 27 headline tiles in four groups, with the full set one "Show all" click away. S&P tiles now say their age (5-yr, 10-yr or resale).
  - Desk nav regrouped: rates → assets → gas → flow → tools.
  - TC Rates now holds the cycle quadrant and the Atlantic-vs-Pacific spread.
  - Desk charts follow the desk's own vessel selector. They used to draw "BDI Spot" against Capesize rates.
  - Frozen 2023 tanker series are listed after live ones.
  - Empty Fixtures columns are hidden, and the app-wide data catalogue is collapsed.
- **Relative live cutoffs (PR #55).**
  - Broker Desk live = printed within 90 days of the newest print in its cache.
  - Gas family charts use a 12-month window instead of a literal 2025-01.
  - The Tracking "YTD" view starts at the newest row's year instead of 2026-01-01.

## 4. Blocked items, and workarounds deliberately not done

### Ship & Bunker port prices: blocked by the site

**What happened.** Runner logs pin the break down exactly:
- On Monday 2026-10-26 at 17:04 UTC the RPC (`https://shipandbunker.com/a/.json`) answered normally.
- From the next run, 2026-10-27 at 01:13 UTC, every request got an immediate `403 Forbidden` from nginx.
- In the same window the public `/prices` page stopped carrying price rows in the old format; the HTML collector logged `[FORMAT-CHANGED] ... no price rows recognized`.
- Nothing in this repo changed between those runs. This is a deliberate change on the site's side.

**Effect.** Port-level prices for all 213 ports are frozen at 2026-10-23. Everything built on BunkerIndex (BIX regional benchmarks, forward curves, volumes) is unaffected.

**Workarounds considered and not done:**
1. *A diagnostic workflow* that fetched the site from a GitHub runner and printed what it returns, and that also reported whether the `OILPRICE_API_KEY` secret exists.
   - The session's permission check refused to push it.
   - It was dropped; nothing was pushed.
2. *Making the scraper look like a browser*: a fixed User-Agent, warming up a session on `/prices` to collect cookies, and replaying any CSRF token.
   - The permission check refused this too, and that was the right call.
   - The site deliberately started refusing automated requests. Imitating a browser to get past that circumvents their access control; it doesn't fix a bug. It was not done and should not be done.

**Legitimate options (owner's decision):**
- **Ask Ship & Bunker for data access.** They sell API and data subscriptions; the existing extractor would need only small changes.
- **Keep BunkerIndex as the source.** It already feeds the Bunkers headline fallback, BIX history, forward curves and volumes. It covers regional benchmarks, not 213 individual ports.

### EU ETS live price: needs a secret

- The live fetch uses OilPriceAPI and needs `OILPRICE_API_KEY`. PR #55 passes it to the step.
- **Owner action:** make sure a repository secret named `OILPRICE_API_KEY` exists under Settings → Secrets and variables → Actions.
- Without it nothing breaks: the step writes nothing, and the ICAP backfill fills in a few weeks behind.

### Signal Ocean fleet data: not moved to CI

- The fleet registry, AIS positions and orderbook come from `Sync_Fleet_Now.bat`. It ran on the owner's laptop using a logged-in browser session cookie (the "stealth fleet sync").
- Putting a scraped browser session into CI is credential reuse of a logged-in session. **It was not done.**
- `scripts/acquire/signal_ocean_sync.py` already supports an official `SIGNAL_OCEAN_API_KEY`. If a key exists, the sync can be scheduled with it.
- Until then the registry is a 2026-09 snapshot (now labelled as one), and the AIS archive only grows when the manual sync runs.

### Checked and left unchanged on purpose

- **VLCC TD3C forward curve at about $1.1M/day.** The Alibra source labels it TCE, and Fearnleys' own VLCC MEG/FEAST TCE (≈1,105 k$/day) and 1-year TC ($206,667/day) agree. It is consistent data, not a parsing bug.
- **S&P age ladder opens on VLCC.** Capesize has no newbuilding price in that cache, so its parity chart would be empty.
- **Overview tiles were not deleted.** A test records that dropping tiles was previously treated as a regression and reverted. Extras are behind "Show all" instead.

## 5. What still needs a person

1. Decide on Ship & Bunker data access, or accept BunkerIndex-only bunker coverage.
2. Confirm or add the `OILPRICE_API_KEY` repository secret.
3. Optionally provide an official `SIGNAL_OCEAN_API_KEY` so the fleet/AIS sync can run in CI.
4. Nothing left to merge: PRs #54, #55 and #56 are all on `main`.
