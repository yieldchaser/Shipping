# Baltic Shipping Dashboard

A fully automated, zero-infrastructure shipping freight intelligence platform. Tracks Baltic freight indices and shipping ETF holdings in real time, and surfaces them through a multi-tab analytical dashboard built entirely in a single `index.html` file — no server, no build step, no cost.

---

## Live Dashboard

The dashboard is served directly from this repository via GitHub Pages. Open `index.html` in any browser, or host via Pages at your own domain.

---

## What This Tracks

### Freight Indices (6 series, daily since Dec 2007)

| File | Index | Code | What it measures |
|---|---|---|---|
| `bdiy_historical.csv` | Baltic Dry Index | BDI | Headline dry bulk composite |
| `cape_historical.csv` | Baltic Capesize Index | BCI | 180,000 DWT bulk carriers (iron ore, coal) |
| `panama_historical.csv` | Baltic Panamax Index | BPI | 82,000 DWT vessels (grain, coal) |
| `suprama_historical.csv` | Baltic Supramax Index | BSI | 58,000 DWT vessels (minor bulk) |
| `cleantanker_historical.csv` | Baltic Clean Tanker Index | BCTI | Refined product tankers |
| `dirtytanker_historical.csv` | Baltic Dirty Tanker Index | BDTI | Crude oil tankers |

CSV schema: `Date (DD-MM-YYYY), Index, % Change`

### Shipping ETF Holdings (BDRY & BWET, updated each market open)

| File | ETF | What it holds |
|---|---|---|
| `bdry_holdings.csv` | Breakwave Dry Bulk Shipping ETF | Capesize, Panamax, Supramax FFA futures — front 3 months |
| `bwet_holdings.csv` | Breakwave Tanker Shipping ETF | TD3C (MEG→China) and TD20 (WAF→Continent) tanker route FFA futures |

CSV schema: `Name, Ticker, CUSIP, Lots, Price, Market_Value, Weightings`

Holdings are sorted by vessel class (nearest expiry first within each class), giving a clean term structure view of the FFA forward curve.

---

## Automation

All data is fetched and committed automatically by two GitHub Actions workflows — no manual intervention required.

### `daily_update.yml` — Index Scraper
- **Schedule:** 6:00 AM UTC and 6:00 PM UTC, every day
- **Source:** [stockq.org](https://en.stockq.org) index pages for BDI, BCI, BPI, BSI, BCTI, BDTI
- **Script:** `update_indices.py`
- **Logic:** Scrapes all available historical rows, deduplicates against existing CSV by date, appends new rows, commits `*.csv`
- **Trigger manually:** Actions → Daily Baltic Index Update → Run workflow

### `etf_holdings_update.yml` — ETF Holdings Scraper
- **Schedule:** 1:00 PM UTC Monday–Friday (≈ 8:30 AM EST, near US market open)
- **Source:** Amplify ETFs master holdings CSV feed (`amplifyetfs.com`)
- **Script:** `update_etf_holdings.py`
- **Logic:** Downloads the full Amplify master CSV, filters to BDRY and BWET rows, sorts by vessel class → contract month (nearest first), saves `bdry_holdings.csv` and `bwet_holdings.csv`, commits
- **Trigger manually:** Actions → ETF Holdings Update (BDRY/BWET) → Run workflow

---

## Repository Structure

```
baltic-indices-data/
│
├── index.html                  # Full dashboard — self-contained, no dependencies except CDN
│
├── bdiy_historical.csv         # Baltic Dry Index history
├── cape_historical.csv         # Capesize history
├── panama_historical.csv       # Panamax history
├── suprama_historical.csv      # Supramax history
├── cleantanker_historical.csv  # Clean Tanker history
├── dirtytanker_historical.csv  # Dirty Tanker history
│
├── bdry_holdings.csv           # BDRY ETF holdings (FFA curve, updated daily)
├── bwet_holdings.csv           # BWET ETF holdings (FFA curve, updated daily)
│
├── update_indices.py           # Index scraper (runs via GitHub Actions)
├── update_etf_holdings.py      # ETF holdings scraper (runs via GitHub Actions)
│
├── Shipping_Main.xlsm          # Excel model (offline analysis workbook)
│
└── .github/workflows/
    ├── daily_update.yml        # Cron job for index scraping (6AM + 6PM UTC)
    └── etf_holdings_update.yml # Cron job for ETF holdings (1PM UTC Mon–Fri)
```

---

## Dashboard Tabs

The dashboard is built on Chart.js 4.4.0 and PapaParse. All CSV files are fetched client-side — no backend. Switching products via the global **Index:** dropdown in the header re-renders all charts for that product instantly.

---

### 📊 Dashboard

The main overview tab for the currently selected index.

- **Hero KPI block:** Current price, day-over-day % change, and an algorithmic signal badge
- **Signal badge logic:**
  - `⛔ SELL (Overheated)` — 5Y percentile > 80%
  - `💎 GOLDEN DIP` — 5Y pctl < 20%, Z-score < −0.5, all-time pctl > 40%
  - `🔥 CATCHING KNIFE` — 5Y pctl < 10%, Z-score < −0.6
  - `⚠️ VALUE TRAP` — 5Y pctl < 30%, all-time pctl < 30%
  - `🔹 ACCUMULATE` — 5Y pctl < 40%
  - `⏳ WAIT` — all other conditions
- **6 stat cards:** All-Time Percentile, 10Y Percentile, 5Y Percentile, Z-Score (vs same calendar trading day across all years), 52-Week Drawdown, 20D Rate of Change
- **Historical Context Strip:** 5Y average, current vs 5Y avg %, current vs 10Y avg %
- **Current Year vs Historical Overlay chart:** Current year plotted against user-selected prior years (checkboxes). Defaults to last 3 prior years
- **Drawdown from 52-Week High chart:** Rolling drawdown %, last 3 years
- **Recent Daily Changes table:** Last 10 sessions with day Δ, day Δ%, 5D change %
- **Yearly Performance table** (collapsible): Annual avg, YoY%, min, max, range% for every year on record
- **Index Correlation Matrix:** Pearson correlation between all 6 indices — switchable between All Time, Last 5Y, Last 1Y

---

### 📅 Yearly

Deep historical analysis for the selected index.

- **Historical Price chart:** Full price history with a rolling average overlay. Toggle between **5Y Avg**, **10Y Avg**, and **All-Time Avg** rolling window. Dual-handle range slider to zoom into any date window
- **Z-Score (Rolling 252-Day) chart:** All 6 products' rolling Z-scores plotted together. The selected product is drawn thicker. Dual-handle range slider — defaults to last 3 years
- **Historical Z-Score (All Time from 2008) chart:** Same as above but full history. Slider defaults to all-time
- **Multi-Year Rates chart:** Annual average values per product, all years on a single line chart
- **Shipping Rates — Current Year Monthly Bar:** Monthly average for the current year as a bar chart, coloured green/red by MoM direction
- **Rates — All Products Multi-Year Overlay:** Last 4 years of all 6 products overlaid by trading day
- **Drawdown % (52-Week Rolling, Last 5 Years):** Rolling 52-week drawdown area chart

---

### 📆 Monthly

- **Monthly Bar Chart (Last 12 Months):** Monthly averages, MoM colour coding
- **Monthly Trend (Last 3 Years):** Area line chart of monthly averages
- **Monthly Area Comparison — Current vs Prior Year:** Side-by-side overlay of current year and last year by calendar month
- **Monthly Data Grid:** Heatmap table — last 5 years × 12 months with a 5Y average row and MoM% row at the bottom

---

### 📊 Quarterly

- **Win Rate KPI cards:** Historical probability of Q1/Q2/Q3/Q4 being higher than the prior quarter, for the selected index
- **Quarterly Heatmap:** All years × Q1–Q4, coloured by absolute value or QoQ % (switchable via heatmap view selector)
- **Spaghetti Chart:** Q1/Q2/Q3/Q4 average values plotted across all years as 4 coloured lines
- **Quarterly Area Comparison — Current vs Prior Year**
- **Quarterly Trend (Last 5 Years)**
- **Quarterly Bar Chart (Last 4 Quarters, QoQ Colour)**
- **Quarterly Area Comparison — Current Year vs 5Y Seasonal Average**
- **Quarterly Data Grid (Last 8 Years):** With full-year average and YoY %

---

### 🌡️ Heatmaps

- **Monthly Heatmap:** Year × month grid, colour-coded by absolute value or MoM % (toggle in header). Column colouring normalised per-month so you can compare Jan across all years
- **Monthly Absolute Values:** Always-on absolute value version alongside the switchable view

---

### 📈 Indices

All 6 indices displayed simultaneously as individual chart cards in a 2-column grid. Each card shows:
- Current value, day change %
- Price chart with **dual-handle date range slider** (drag to zoom any period — defaults to last 5 years)
- Stats strip: All-Time High, All-Time Low, Current vs ATH, YTD %

---

### 🏦 ETFs

Live BDRY and BWET ETF cards:
- **Live price + day change** fetched from Yahoo Finance via proxy (best-effort, may show "unavailable" if proxy rate-limited)
- **Holdings table:** All FFA contracts sorted by vessel class → nearest expiry
- **Donut chart:** Futures notional allocation by vessel class (excludes collateral cash, normalised to 100% of futures)
- **Metrics strip:** Total Futures notional, Collateral Cash, Futures/AUM ratio

---

### 🎯 Signals

Five analytical signal charts for trading edge:

#### 1. Bollinger Bands (20-Day, 2σ)
Price line with upper band (+2σ, red dashed), 20D SMA (yellow dashed), and lower band (−2σ, green dashed). Bands fill with a soft colour between them. Window toggle: **1Y / 3Y / 5Y**. In freight markets — which are mean-reverting — lower band touches after extended selloffs are historically strong entry candidates. Upper band touches in overbought conditions are exit triggers.

#### 2. Cape / Panamax Ratio
Cape index divided by Panamax index, plotted as a ratio time series (left axis) with the all-time historical mean overlaid (yellow dashed). Rolling 252-day percentile rank of the ratio on the right axis (purple dashed). Window toggle: **3Y / 5Y / All**.

**What it signals:** The ratio is a direct proxy for iron ore demand (Capesize) vs grain/coal/minor bulk demand (Panamax). Ratio spikes typically indicate China infrastructure/steel demand surges. Ratio compressions indicate grain/coal cycle dominance. The percentile rank tells you where the current relative strength sits in historical context.

#### 3. Rate-of-Change Heatmap
A 6 × 6 grid: all 6 products (rows) × 6 timeframes (5D, 10D, 20D, 60D, 90D, 1Y). Each cell shows the % return coloured on a divergent scale (deep red ≤ −15% → neutral 0% → deep green ≥ +15%).

**What it signals:** Read cross-product momentum divergences at a glance. Example: Capesize green across all timeframes while Clean Tanker is red = dry bulk/tanker divergence, potential relative value opportunity. A product green short-term but red long-term = mean-reversion bounce candidate.

#### 4. Seasonal Decomposition
For the selected product, plots the **average intra-year pattern** computed from all historical years except the current year (yellow dashed baseline), with ±1σ bands shaded around it. The **current year's actual price path** is overlaid in the product colour. X-axis is trading day of year with approximate month labels.

**What it signals:** Shows whether the current year is tracking above or below the historical seasonal norm, and by how much. A move more than 1σ below the seasonal average in months that are historically strong is a potential mean-reversion long. The seasonal pattern in dry bulk is well-documented (weak Jan–Feb, strong Q4).

#### 5. FFA Term Structure — BDRY & BWET
Side-by-side forward curves built directly from the live ETF holdings CSVs. Plots contract price (y-axis) vs expiry month (x-axis) for each vessel class:
- **BDRY:** Capesize 5TC, Panamax 5TC, Supramax 58 — three separate curves
- **BWET:** TD3C (MEG→China), TD20 (WAF→Continent) — two separate curves

Below each chart: a slope label per vessel class showing the **curve structure** with front-to-back % slope:
- `📉 Backwardation` — front month higher than back months (spot tightness, bullish carry)
- `📈 Contango` — back months higher than front (oversupply, negative carry)
- `➡️ Flat` — within ±1.5%

**What it signals:** Backwardation = physical market is tight right now, longs collect positive roll yield. Contango = market expects improvement but current spot is weak, shorts collect roll yield. The shape of the curve across vessel classes tells you where the tightness is concentrated (e.g. Capesize in backwardation while Panamax in contango = iron ore specific, not broad dry bulk).

---

## Statistics Reference

| Metric | Calculation |
|---|---|
| **Percentile Rank** | Fraction of all historical daily values (within the lookback window) that are ≤ current value |
| **Z-Score (Dashboard)** | `(current − mean of same calendar trading day across all prior years) / stddev` |
| **Z-Score (Rolling 252D)** | `(current − mean of trailing 252 days) / stddev of trailing 252 days` |
| **52-Week Drawdown** | `(current − max over trailing 365 calendar days) / max` |
| **Rate of Change (20D)** | `(current − value 20 trading days ago) / value 20 trading days ago × 100` |
| **Bollinger Bands** | SMA(20) ± 2 × population stddev(20) |
| **Rolling Autocorrelation** | Pearson correlation between `returns[t]` and `returns[t-1]` over trailing window |
| **Cape/Panamax Percentile** | Percentile rank of current ratio vs trailing 252 trading days of ratio values |
| **Seasonal Avg** | Mean of `value[trading_day_N]` across all historical years except current |
| **FFA Slope** | `(back_month_price − front_month_price) / front_month_price × 100` |

---

## Dependencies

| Dependency | Version | How used |
|---|---|---|
| [Chart.js](https://www.chartjs.org/) | 4.4.0 | All charts |
| [PapaParse](https://www.papaparse.com/) | 5.4.1 | CSV parsing |
| [allorigins.win](https://allorigins.win/) | — | CORS proxy for Yahoo Finance ETF price fetch |

Python (scrapers only, run inside GitHub Actions — not needed to use the dashboard):

```
requests
beautifulsoup4
pandas
lxml
openpyxl
```

---

## Running Scrapers Locally

```bash
pip install requests beautifulsoup4 pandas lxml openpyxl

# Update all 6 Baltic indices
python update_indices.py

# Update BDRY and BWET ETF holdings
python update_etf_holdings.py
```

Both scripts are idempotent — safe to re-run at any time. They deduplicate by date before writing.

---

## Data Sources

| Data | Source | Notes |
|---|---|---|
| Baltic freight indices | [stockq.org](https://en.stockq.org) | Scraped 2× daily |
| BDRY / BWET holdings | [amplifyetfs.com](https://amplifyetfs.com) master CSV | Scraped each market open Mon–Fri |
| ETF live prices | Yahoo Finance v8 API (via allorigins proxy) | Best-effort, client-side only |

---

## Notes

- All timestamps in the CSVs are in `DD-MM-YYYY` format
- The BDI history goes back to **December 2007** — the tail end of the commodity supercycle peak (BDI ~10,000+)
- Tanker indices (BCTI, BDTI) have shorter history than dry bulk indices as data availability varies by source
- The `Shipping_Main.xlsm` workbook is an offline Excel model that consumes the same CSV data for deeper ad-hoc analysis
- The FFA term structure in the Signals tab is only as current as the last ETF holdings commit — check the last commit timestamp on `bdry_holdings.csv` / `bwet_holdings.csv` to confirm freshness
