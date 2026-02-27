# Shipping

> *"I am a Man of Fortune, and I must seek my Fortune."*
> — Henry Avery, 1694

A fully automated, zero-infrastructure shipping freight intelligence platform. Tracks Baltic freight indices, shipping ETF holdings, and a proprietary dry bulk composite — surfaced through a multi-tab analytical dashboard built entirely in a single `index.html` file. No server, no build step, no cost.

---

## Live Dashboard

Served directly from this repository via GitHub Pages. Open `index.html` in any browser.

---

## What This Tracks

### Freight Indices — 6 series, daily since Dec 2007

| File | Index | Code | What it measures |
|---|---|---|---|
| `bdiy_historical.csv` | Baltic Dry Index | BDI | Headline dry bulk composite |
| `cape_historical.csv` | Baltic Capesize Index | BCI | 180,000 DWT bulk carriers (iron ore, coal) |
| `panama_historical.csv` | Baltic Panamax Index | BPI | 82,000 DWT vessels (grain, coal) |
| `suprama_historical.csv` | Baltic Supramax Index | BSI | 58,000 DWT vessels (minor bulk) |
| `cleantanker_historical.csv` | Baltic Clean Tanker Index | BCTI | Refined product tankers |
| `dirtytanker_historical.csv` | Baltic Dirty Tanker Index | BDTI | Crude oil tankers |

CSV schema: `Date (DD-MM-YYYY), Index, % Change`

### BDRY Spot Composite — 7th product, computed client-side

A proprietary index replicating the **Solactive Breakwave Dry Freight Futures Index** methodology using daily spot values:

```
BDRY_Spot(t) = 0.50 × BCI(t) + 0.40 × BPI(t) + 0.10 × BSI(t)
```

Available from October 2008 (~4,198 data points). No new file — computed in the browser from the three existing CSVs on every page load. Selectable as a 7th product across all tabs. Useful for comparing against the BDRY ETF price to monitor premium/discount to spot.

### Shipping ETF Holdings — updated each market open

| File | ETF | What it holds |
|---|---|---|
| `bdry_holdings.csv` | Breakwave Dry Bulk Shipping ETF (BDRY) | Capesize 5TC, Panamax 5TC, Supramax 58 FFA futures — front 5 months |
| `bwet_holdings.csv` | Breakwave Tanker Shipping ETF (BWET) | TD3C (MEG→China, 270kt VLCC) and TD20 (WAF→Continent, 130kt Suezmax) FFA futures |

CSV schema: `Name, Ticker, CUSIP, Lots, Price, Market_Value, Weightings`

Holdings sorted by vessel class → contract month (nearest expiry first). BDRY weights: **50% Capesize, 40% Panamax, 10% Supramax** — confirmed Solactive index methodology (ISIN DE000SLA4BY3). BWET weights: **90% TD3C, 10% TD20** (ISIN DE000SL0HLG3, Excess Return index).

---

## Automation

### `daily_update.yml` — Index Scraper
- **Schedule:** 6:00 AM UTC and 6:00 PM UTC, every day
- **Source:** [stockq.org](https://en.stockq.org)
- **Script:** `update_indices.py`
- **Logic:** Scrapes all 6 indices, deduplicates by date, appends new rows, commits `*.csv`
- **Manual trigger:** Actions → Daily Baltic Index Update → Run workflow

### `etf_holdings_update.yml` — ETF Holdings Scraper
- **Schedule:** 1:00 PM UTC Monday–Friday (≈ 8:30 AM EST)
- **Source:** Amplify ETFs master holdings CSV (`amplifyetfs.com`)
- **Script:** `update_etf_holdings.py`
- **Logic:** Downloads master CSV, filters to BDRY and BWET, sorts by vessel class → contract month, commits
- **Manual trigger:** Actions → ETF Holdings Update (BDRY/BWET) → Run workflow

---

## Repository Structure

```
baltic-indices-data/
│
├── index.html                  # Full dashboard — self-contained, CDN-only dependencies
│
├── bdiy_historical.csv         # Baltic Dry Index history (from Dec 2007)
├── cape_historical.csv         # Capesize history (from Oct 2008)
├── panama_historical.csv       # Panamax history (from Oct 2008)
├── suprama_historical.csv      # Supramax history (from Oct 2008)
├── cleantanker_historical.csv  # Clean Tanker history (from Jan 2008)
├── dirtytanker_historical.csv  # Dirty Tanker history (from Dec 2007)
│
├── bdry_holdings.csv           # BDRY FFA curve holdings (updated daily)
├── bwet_holdings.csv           # BWET FFA curve holdings (updated daily)
│
├── update_indices.py           # Index scraper
├── update_etf_holdings.py      # ETF holdings scraper
│
├── Shipping_Main.xlsm          # Offline Excel analysis workbook
│
└── .github/workflows/
    ├── daily_update.yml        # Cron: 6AM + 6PM UTC daily
    └── etf_holdings_update.yml # Cron: 1PM UTC Mon–Fri
```

---

## Dashboard Tabs

Built on Chart.js 4.4.0 and PapaParse. All data fetched client-side — no backend. The global **Index:** dropdown in the header switches the active product across all tabs instantly. **7 products** available: BDI, Capesize, Panamax, Supramax, Clean Tanker, Dirty Tanker, BDRY Spot Composite.

---

### 📊 Dashboard

Main overview for the selected index.

- **Hero KPI + signal badge** — algorithmic signal based on percentile and Z-score:
  - `⛔ SELL` — 5Y pctl > 80%
  - `💎 GOLDEN DIP` — 5Y pctl < 20%, Z < −0.5, all-time pctl > 40%
  - `🔥 CATCHING KNIFE` — 5Y pctl < 10%, Z < −0.6
  - `⚠️ VALUE TRAP` — 5Y pctl < 30%, all-time pctl < 30%
  - `🔹 ACCUMULATE` — 5Y pctl < 40%
  - `⏳ WAIT` — all other
- **6 stat cards:** All-Time Pctl, 10Y Pctl, 5Y Pctl, Z-Score, 52-Week Drawdown, 20D RoC
- **Historical Context Strip:** 5Y avg, current vs 5Y avg %, current vs 10Y avg %
- **Current Year vs Historical Overlay chart** — current year vs user-selected prior years
- **Drawdown from 52-Week High chart** — last 3 years
- **Recent Daily Changes table** — last 10 sessions: day Δ, day Δ%, 5D change %
- **Yearly Performance table** (collapsible) — annual avg, YoY%, min, max, range%
- **Index Correlation Matrix** — Pearson correlation, switchable All Time / 5Y / 1Y

---

### 📅 Yearly

- **Historical Price chart** — full history with rolling average. Toggle: **5Y Avg / 10Y Avg / All-Time Avg**. Dual-handle range slider to zoom any date window
- **Z-Score (Rolling 252-Day)** — all 7 products, selected product thicker. Range slider defaults to last 3 years
- **Historical Z-Score (All Time from 2008)** — same, range slider defaults to full history
- **Multi-Year Rates** — annual averages by product, all years
- **Shipping Rates — Current Year Monthly Bar** — MoM colour coding
- **Rates — All Products Multi-Year Overlay** — last 4 years by trading day
- **Drawdown % (52-Week Rolling, Last 5 Years)**

---

### 📆 Monthly

- **Monthly Bar Chart** — last 12 months, MoM colour coding
- **Monthly Trend** — last 3 years area chart
- **Monthly Area Comparison** — current vs prior year
- **Monthly Data Grid** — last 5 years × 12 months heatmap, 5Y avg row, MoM% row

---

### 📊 Quarterly

- **Win Rate KPI cards** — historical probability each quarter beats the prior
- **Quarterly Heatmap** — all years × Q1–Q4, absolute or QoQ % (switchable)
- **Spaghetti Chart** — Q1/Q2/Q3/Q4 across all years as 4 coloured lines
- **Quarterly Area Comparison** — current vs prior year
- **Quarterly Trend** — last 5 years
- **Quarterly Bar Chart** — last 4 quarters, QoQ colour
- **Quarterly Area Comparison** — current year vs 5Y seasonal average
- **Quarterly Data Grid** — last 8 years with full-year avg and YoY%

---

### 🌡️ Heatmaps

- **Monthly Heatmap** — year × month, absolute value or MoM% (toggle). Normalised per-column so Jan values compare across all years cleanly

---

### 📈 Indices

All 6 base indices as individual chart cards (BDRY Spot is a composite — available via global selector but not shown here as a standalone card):
- Current value, day change %
- **Dual-handle date range slider** — drag to zoom any window, defaults to last 5 years
- Stats strip: All-Time High, All-Time Low, Current vs ATH, YTD %

---

### 🏦 ETFs

**BDRY and BWET ETF cards:**
- Live price + day change (Yahoo Finance via proxy, best-effort)
- Holdings table — FFA contracts sorted by vessel class → expiry month (Feb → Mar → Apr → May → Jun), cash last
- Donut chart — futures allocation by vessel class (cash excluded, normalised to 100%)
- Metrics strip — Total Futures, Collateral Cash, Futures/AUM ratio

**BDRY Liquidity Tracker** (below ETF cards):

A personal position-sizing model applied to BDRY's full daily history (22 March 2018 → present, ~1,994 days), fetched live from Yahoo Finance on tab open.

| Field | Formula |
|---|---|
| Dollar Value Traded | `Close × Volume` |
| Tier % | Volume < 50K → **2%** · < 100K → **3.5%** · < 500K → **5%** · ≥ 500K → **6.5%** |
| Possible Shares | `floor(Volume × Tier%)` |
| Safe Liquidity | `Possible Shares × Close` |
| Day Change % | `(Close − PrevClose) / PrevClose × 100` |

- **KPI strip** — today's values for all 6 fields
- **Safe Liquidity chart** — historical $ tradeable size over time
- **Volume chart** — daily bars coloured by tier, with 50K/100K/500K threshold lines overlaid
- **Full data table** — all rows newest-first, scrollable, all columns colour-coded
- **Window toggle:** 1Y / 3Y / All
- **CSV download** — exports currently filtered window

---

### 🎯 Signals

Five analytical signal charts:

#### 1. Bollinger Bands (20-Day, 2σ)
Price with upper (+2σ), 20D SMA, and lower (−2σ) bands. Window: **1Y / 3Y / 5Y**. Lower band touches after extended selloffs = mean-reversion long candidates. Upper band = overbought exit trigger.

#### 2. Cape / Panamax Ratio
Ratio time series (left axis) + all-time historical mean (yellow dashed) + rolling 252D percentile rank (right axis). Window: **3Y / 5Y / All**. Proxy for iron ore demand (Cape) vs grain/coal/minor bulk (Panamax). Ratio spikes = China infrastructure cycle. Compressions = grain/coal dominance.

#### 3. Rate-of-Change Heatmap
7 products × 6 timeframes (5D / 10D / 20D / 60D / 90D / 1Y). Each cell % change, divergent colour scale (red ≤ −15% → green ≥ +15%). Cross-product momentum divergences readable at a glance.

#### 4. Seasonal Decomposition
Historical average intra-year pattern (yellow dashed) ± 1σ bands, with current year overlaid in product colour. X-axis = trading day of year with month labels. Shows whether the current year is tracking above/below seasonal norm and by how much.

#### 5. FFA Term Structure — BDRY & BWET
Forward curves from live ETF holdings CSVs. BDRY: Capesize / Panamax / Supramax curves. BWET: TD3C / TD20 curves. Slope labels below each chart:
- `📉 Backwardation` — spot tightness, positive roll yield for longs
- `📈 Contango` — oversupply, negative roll yield
- `➡️ Flat` — within ±1.5% front-to-back

---

## Statistics Reference

| Metric | Calculation |
|---|---|
| **Percentile Rank** | Fraction of historical values ≤ current within lookback window |
| **Z-Score (Dashboard)** | `(current − mean of same calendar trading day, all prior years) / stddev` |
| **Z-Score (Rolling 252D)** | `(current − trailing 252D mean) / trailing 252D stddev` |
| **52-Week Drawdown** | `(current − max over trailing 365 calendar days) / max` |
| **Rate of Change (20D)** | `(current − value 20 trading days ago) / value 20 trading days ago × 100` |
| **Bollinger Bands** | SMA(20) ± 2 × population stddev(20) |
| **Cape/Panamax Percentile** | Percentile rank of ratio vs trailing 252D of ratio values |
| **Seasonal Avg** | Mean of `value[trading_day_N]` across all historical years except current |
| **FFA Slope** | `(back_month − front_month) / front_month × 100` |
| **BDRY Spot** | `0.50 × BCI + 0.40 × BPI + 0.10 × BSI` (Solactive methodology) |
| **Safe Liquidity** | `floor(Volume × tier%) × Close` |

---

## Dependencies

| | Version | Used for |
|---|---|---|
| [Chart.js](https://www.chartjs.org/) | 4.4.0 | All charts |
| [PapaParse](https://www.papaparse.com/) | 5.4.1 | CSV parsing |
| [allorigins.win](https://allorigins.win/) | — | CORS proxy — Yahoo Finance price + BDRY liquidity data |

Python (scrapers only, GitHub Actions):
```
requests · beautifulsoup4 · pandas · lxml · openpyxl
```

---

## Running Scrapers Locally

```bash
pip install requests beautifulsoup4 pandas lxml openpyxl

python update_indices.py       # update all 6 Baltic indices
python update_etf_holdings.py  # update BDRY and BWET holdings
```

Both scripts are idempotent — safe to re-run, deduplicate by date before writing.

---

## Data Sources

| Data | Source | Freshness |
|---|---|---|
| Baltic freight indices | [stockq.org](https://en.stockq.org) | 2× daily (6AM + 6PM UTC) |
| BDRY / BWET holdings | [amplifyetfs.com](https://amplifyetfs.com) | Each market open Mon–Fri |
| BDRY ETF price (live) | Yahoo Finance v8 API via allorigins proxy | On ETF tab open |
| BDRY liquidity history | Yahoo Finance v8 API via allorigins proxy | On ETF tab open, `range=10y` |

---

## Notes

- CSV dates are in `DD-MM-YYYY` format
- BDI history starts **December 2007** — tail end of the commodity supercycle peak (~10,000+)
- BDRY Spot composite starts **October 2008** (earliest date all three dry bulk components overlap)
- Tanker indices have slightly shorter history — BCTI from Jan 2008, BDTI from Dec 2007
- The FFA term structure chart is only as fresh as the last `bdry_holdings.csv` / `bwet_holdings.csv` commit — check the commit timestamp to confirm
- `Shipping_Main.xlsm` is an offline Excel workbook for ad-hoc analysis consuming the same CSV data
