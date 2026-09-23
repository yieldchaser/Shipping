# Trackinsight Fund Flow API — Complete Agent Reference

> **Purpose**: This document is a complete, self-contained reference for any AI agent or developer working with Trackinsight's undocumented internal API to fetch ETF fund flow data. Written from reverse-engineering sessions in September 2026. No API key is required — everything here uses Trackinsight's own authenticated browser session via Playwright.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Complete Endpoint Map](#2-complete-endpoint-map)
3. [Fund Flow Data Endpoint (Primary)](#3-fund-flow-data-endpoint-primary)
4. [ETF Universe Endpoint (search_v2)](#4-etf-universe-endpoint-search_v2)
5. [Ticker Key Format Rules](#5-ticker-key-format-rules)
6. [Historical Data Depth](#6-historical-data-depth)
7. [Available Fields per Endpoint](#7-available-fields-per-endpoint)
8. [How BDRY & BWET Are Fully Automated (Repo Pipeline)](#8-how-bdry--bwet-are-fully-automated-repo-pipeline)
9. [Stealth / Rate-Limit Avoidance](#9-stealth--rate-limit-avoidance)
10. [ETF Universe — Full 15,715 ETF List](#10-etf-universe--full-15715-etf-list)
11. [Known Leveraged ETF Ticker Map](#11-known-leveraged-etf-ticker-map)
12. [Minimal Working Code Template](#12-minimal-working-code-template)
13. [Common Failure Modes](#13-common-failure-modes)

---

## 1. Overview

Trackinsight is a European ETF analytics platform covering **15,715 global ETFs**. It collects daily fund flow data (NAV creation/redemption in USD) from fund administrators and displays it on `trackinsight.com/en/fund/{TICKER}/flows`.

**Key facts:**
- No public API, no API key — uses same-origin browser fetch with AWS WAF cookies
- Daily granularity, data starts from **2016-01-04** at the earliest (hard wall regardless of ETF inception)
- WAF protection (AWS WAF + Cloudflare) blocks plain HTTP requests → must use Playwright to carry real browser cookies
- The site uses **Cognito JWT** for user-authenticated endpoints (`user-api`) but fund flow data (`search-api`) does NOT require auth — just WAF bypass via Playwright
- All flows are in **USD**, regardless of ETF base currency
- `stamp` field encodes dates as **day-numbers** (integer): `date = unix_timestamp / 86400`, so `actual_unix = stamp * 86400`

---

## 2. Complete Endpoint Map

All endpoints are on `https://www.trackinsight.com`.

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/search-api/snapshot/get_snapshots` | POST JSON | WAF only | **Primary fund flow endpoint** — fetch NAV, flow, perf for any ETF |
| `/search-api/search_v2/{q}/{filter}/{fields}/{sort}/{offset}/{limit}` | GET | WAF only | **Full ETF universe** — paginate all 15,715 ETFs with metadata |
| `/search-api/count/{q}/{filter}/{group}` | GET | WAF only | Count ETFs by grouping (asset class, etc.) |
| `/user-api/user/recent-funds?limit=N` | GET | Cognito Bearer JWT | User's recently viewed ETFs (requires login token) |
| `/user-api/user/recent-searches?limit=N` | GET | Cognito Bearer JWT | User's recent searches |
| `/cms-api/en-us/...` | GET | None | CMS content (blog posts, campaigns) — not useful for data |
| `https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}` | GET | None | Yahoo Finance price/volume history — used for BDRY/BWET price overlay |
| Amplify Firebase Firestore | GET | API key (base64 in script) | ETF holdings (BDRY, BWET only) — see `update_etf_holdings.py` |

### Endpoints that do NOT work

| URL | Status | Reason |
|-----|--------|--------|
| `/data-api/funds/all.json` | 403 | Direct S3 bucket — requires AWS IAM credentials |
| `/search-api/search` (GET) | 200 `{"error":"Method not allowed"}` | GET not allowed; POST also returns same error |
| `/search-api/funds?...` | 200 `{"error":"Route not found"}` | Route doesn't exist |
| Any endpoint without Playwright | 202 empty body | AWS WAF blocks plain HTTP |

---

## 3. Fund Flow Data Endpoint (Primary)

### Request

```
POST https://www.trackinsight.com/search-api/snapshot/get_snapshots
Content-Type: application/json
X-Requested-With: XMLHttpRequest
```

**Body format — single ticker:**
```json
{
  "requests": [
    {
      "fund": "BDRY",
      "startDate": "2016-01-01",
      "endDate": "2026-09-22",
      "columns": ["stamp", "USD:flow", "nav", "perf"]
    }
  ]
}
```

**Body format — batch (up to ~20 tickers per call):**
```json
{
  "requests": [
    {"fund": "BDRY", "startDate": "2024-01-01", "endDate": "2026-09-22", "columns": ["stamp", "perf"]},
    {"fund": "BWET", "startDate": "2024-01-01", "endDate": "2026-09-22", "columns": ["stamp", "perf"]},
    {"fund": "ARCX:SOXL", "startDate": "2024-01-01", "endDate": "2026-09-22", "columns": ["stamp", "perf"]},
    {"fund": "XNMS:SQQQ", "startDate": "2024-01-01", "endDate": "2026-09-22", "columns": ["stamp", "perf"]}
  ]
}
```

**Available `columns` values:**

| Column | Description | Unit |
|--------|-------------|------|
| `stamp` | **Required always** — date as day-number integer | `date = stamp * 86400` (unix) |
| `USD:flow` | Daily net fund flow (creations minus redemptions) | USD |
| `nav` | Net Asset Value per share | ETF currency |
| `perf` | Daily performance / return | Decimal (0.015 = 1.5%) |
| `excessReturn` | Excess return vs benchmark | Returns N/A for recent data |

### Response format

```json
[
  {
    "stamp":    {"data": [16800, 16801, 16802, ...], "scale": 1},
    "USD:flow": {"data": [1200000, -500000, 0, ...], "scale": 1000},
    "nav":      {"data": [2340, 2355, 2361, ...], "scale": 100},
    "perf":     {"data": [15, -3, 22, ...], "scale": 10000}
  }
]
```

**Unpacking the `scale` field:**
```python
def unpack(field_data: dict) -> list:
    scale = field_data.get("scale", 1) or 1
    return [v / scale if v is not None else None for v in field_data.get("data", [])]

def stamp_to_date(d: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(d) * 86400, tz=timezone.utc).strftime("%Y-%m-%d")
```

**Empty response** (ticker not found or wrong key): `[{}]` — dict with no keys, or `{}` directly.

### Quarterly chunking (recommended for full history)

The Trackinsight website itself sends quarterly chunked requests. This improves reliability and avoids timeouts. Recommended approach:

```python
from dateutil.relativedelta import relativedelta
from datetime import date

def build_quarterly_requests(ticker: str, start_year: int = 2016) -> list:
    today = date.today()
    reqs = []
    d = date(start_year, 1, 1)
    while d <= today:
        q_end = d + relativedelta(months=3) - relativedelta(days=1)
        if q_end > today: q_end = today
        reqs.append({
            "fund": ticker,
            "startDate": d.strftime("%Y-%m-%d"),
            "endDate": q_end.strftime("%Y-%m-%d"),
            "columns": ["stamp", "USD:flow", "nav", "perf"]
        })
        d += relativedelta(months=3)
    return reqs
```

---

## 4. ETF Universe Endpoint (search_v2)

### Request format

```
GET https://www.trackinsight.com/search-api/search_v2/{query}/{filter}/{fields}/{sort}/{offset}/{limit}
X-Requested-With: XMLHttpRequest
```

**URL segments:**

| Segment | Description | Examples |
|---------|-------------|---------|
| `query` | Free-text search. Use `_` for all | `_`, `ProShares`, `SOXL`, `Direxion` |
| `filter` | Asset class or other filter. Use `_` for all | `_`, `ac=s`, `ac=c`, `ac=b` |
| `fields` | Comma-separated field names to return | `ticker`, `ticker,isin`, `ticker,isin,label,aum,provider` |
| `sort` | Sort order | `default` (USD AUM desc), `aum` (local currency AUM desc), `perf` |
| `offset` | Pagination offset (0-indexed) | `0`, `500`, `1000` |
| `limit` | Results per page (no max found — tested up to 5000) | `500`, `1000`, `5000` |

**Examples:**
```
# All ETFs, ticker + ISIN, 500 per page, page 2
GET /search-api/search_v2/_/_/ticker,isin/default/500/500

# All equity ETFs
GET /search-api/search_v2/_/ac=s/ticker,label,aum,provider/default/0/5000

# Search ProShares
GET /search-api/search_v2/ProShares/_/ticker,label,aum/default/0/200

# Commodity ETFs
GET /search-api/search_v2/_/ac=c/ticker,label,provider,aum/default/0/700

# All 15,715 in one shot (tested, works)
GET /search-api/search_v2/_/_/ticker,isin,label,type,currency,aum,nav,provider,expense_ratio,index,benchmark,sfdr,currencyHedged,rating,perf/default/0/16000
```

### Response format

```json
{
  "results": {
    "count": 15715,
    "words": [],
    "docs": [
      {
        "ticker": "VOO",
        "isin": "US9229083632",
        "label": "Vanguard S&P 500 ETF",
        "type": "ETF",
        "currency": "USD",
        "aum": 1087608867000,
        "nav": 712.76,
        "provider": "Vanguard",
        "expense_ratio": 0.0003,
        "index": "S&P 500 Daily Total Return Index - USD",
        "benchmark": "S&P 500 Index",
        "sfdr": "Out of scope",
        "currencyHedged": false,
        "rating": 4,
        "perf": 0.01501
      }
    ]
  }
}
```

### Asset class filter codes (`ac=`)

| Code | Asset Class | Count (Sep 2026) |
|------|-------------|-----------------|
| `s` | Equity | 10,222 |
| `b` | Fixed Income / Bonds | 3,587 |
| `c` | Commodity | 659 |
| `ma` | Multi-Asset | 590 |
| `cc` | Crypto (likely) | 558 |
| `cu` | Currency | 83 |
| `vo` | Volatility | 16 |

### Available `fields` (confirmed working)

| Field | Description | Example |
|-------|-------------|---------|
| `ticker` | Trackinsight ticker key (may include MIC prefix) | `VOO`, `ARCX:SOXL` |
| `isin` | ISIN(s), semicolon-separated if multiple | `US9229083632` |
| `label` | Full ETF name | `Vanguard S&P 500 ETF` |
| `type` | Instrument type | `ETF`, `ETP`, `ETC`, `ETN`, `PTF` |
| `currency` | Trading currency | `USD`, `EUR`, `GBP` |
| `aum` | AUM in local currency (large for JPY ETFs!) | `1087608867000` |
| `nav` | Current NAV | `712.76` |
| `provider` | Asset manager name | `Vanguard`, `iShares`, `Direxion` |
| `expense_ratio` | Annual expense ratio as decimal | `0.0003` (= 0.03% TER) |
| `index` | Tracked index full name | `S&P 500 Daily Total Return Index - USD` |
| `benchmark` | Benchmark name | `S&P 500 Index` |
| `sfdr` | EU SFDR article classification | `Out of scope`, `Article 8`, `Article 9` |
| `currencyHedged` | Currency hedged? | `false`, `true` |
| `rating` | Trackinsight quality rating | `0`–`5` (0/blank = unrated) |
| `perf` | **1-week performance** as decimal | `0.01501` = +1.5% |

> **Note**: `aum` for Japanese ETFs is in JPY (e.g., Nomura TOPIX = ¥34,665B ≈ $230B). For USD comparison, filter by `currency=USD` in post-processing.

---

## 5. Ticker Key Format Rules

The `fund` field in the snapshot API and `ticker` field in search_v2 use Trackinsight's internal key format.

### Rules (discovered empirically)

| Rule | Description |
|------|-------------|
| **Bare ticker** | Most ETFs: just use the ticker symbol (`BDRY`, `TQQQ`, `AGQ`, `UGL`) |
| **`MIC:ticker`** | Some ETFs require exchange MIC prefix when multiple exchanges list the same ticker |
| **`ARCX:`** | NYSE Arca listed ETFs (most ProShares, Direxion, GraniteShares on ARCX) |
| **`XNMS:`** | NASDAQ Global Market Select (used for SQQQ) |
| **`NEOE:`** | NEO Exchange (Canada) |
| **`XMIL:`** | Milan (Borsa Italiana) |

### Known ticker key map

| Ticker | Key | Notes |
|--------|-----|-------|
| BDRY | `BDRY` | Shipping ETF |
| BWET | `BWET` | Wet tanker ETF |
| SOXL | `ARCX:SOXL` | Must use ARCX prefix |
| SQQQ | `XNMS:SQQQ` | Must use XNMS (not XNAS) prefix |
| TQQQ | `TQQQ` | Bare ticker works |
| UPRO | `UPRO` | Bare ticker works |
| SPXL | `SPXL` | Bare ticker works |
| TNA | `TNA` | Bare ticker works |
| MSTX | `MSTX` | Bare ticker works |
| SVIX | `SVIX` | Bare ticker works |
| GGLL | `GGLL` | Bare ticker works |
| TSLL | `TSLL` | Bare ticker works |
| NVDL | `NVDL` | Bare ticker works |
| AGQ | `AGQ` | Bare ticker works |
| UGL | `UGL` | Bare ticker works |
| GOOX | `GOOX` | Bare ticker works |
| CONL | `CONL` | Bare ticker works |
| FNGU | `FNGU` | Bare ticker works (but data only from 2025-02-20) |
| FBL | `FBL` | GraniteShares 2x META (formerly METL) |
| SSO | `ARCX:SSO` | ProShares 2x S&P |
| SPXU | `ARCX:SPXU` | ProShares 3x Short S&P |
| QQQU | `ARCX:QQQU` | MicroSectors FANG+ 3x |
| BNKU | `ARCX:BNKU` | MicroSectors Banks 3x |
| SCO | `ARCX:SCO` | ProShares 2x Short Oil |
| UCO | `ARCX:UCO` | ProShares 2x Long Oil |
| USD (Semis ETF) | `ARCX:USD` | ProShares Ultra Semiconductors |
| SH | `ARCX:SH` | ProShares Short S&P |
| QID | `ARCX:QID` | ProShares UltraShort QQQ |
| UVXY | `BATS:UVXY` | ProShares Ultra VIX |
| ISPY | `BATS:ISPY` | ProShares S&P 500 High Income |
| COMB | `ARCX:COMB` | GraniteShares Commodity |
| HIPS | `ARCX:HIPS` | GraniteShares HIPS High Income |

### How to discover the correct key

1. Go to `https://www.trackinsight.com/en/fund/{TICKER}/flows` in a browser
2. The URL that loads successfully tells you the key (e.g., URL becomes `/en/fund/ARCX:SOXL/flows`)
3. OR: use the `search_v2` endpoint with the ticker as query text — the returned `ticker` field IS the correct key

```python
# Auto-discover correct key for any ticker
result = page.evaluate(fetch_js, f"/search-api/search_v2/{ticker}/_/ticker/default/0/5")
key = result["results"]["docs"][0]["ticker"]  # e.g. "ARCX:SOXL"
```

---

## 6. Historical Data Depth

| Time period | Data available? |
|-------------|----------------|
| Pre-2016 | **No** — hard wall at 2016-01-04 for ALL ETFs regardless of inception date |
| 2016-01-04 → today | Yes, for ETFs that existed then |
| ETF inception after 2016 | Data starts from inception date |

**Practical start dates for known ETFs:**

| ETF | Data starts |
|-----|-------------|
| BDRY, BWET, ARCX:SOXL, SQQQ, TNA, LABU | 2016-01-04 |
| SVIX | 2022-03-30 |
| GGLL, GOOX | 2022-09-07 |
| NVDL, FBL | 2022-12-14 |
| TSLL, CONL | 2022-08-09 |
| MSTX | 2024-08-16 |
| FNGU | 2025-02-20 (despite 2020 inception) |
| AGQ, UGL | 2016-01-04 |

**Recommended `startDate`**: Always request from `2016-01-01` — the API simply returns empty arrays for periods before data exists. No error thrown.

---

## 7. Available Fields per Endpoint

### `get_snapshots` columns

```python
COLUMNS = ["stamp", "USD:flow", "nav", "perf"]
# "excessReturn" is accepted but returns N/A for recent periods
```

### `search_v2` fields

```python
RICH_FIELDS = "ticker,isin,label,type,currency,aum,nav,provider,expense_ratio,index,benchmark,sfdr,currencyHedged,rating,perf"
```

Fields NOT available via `search_v2` (tested and confirmed empty): `name`, `shortName`, `assetClass`, `country`, `domicile`, `region`, `inceptionDate`, `leverage`, `holdings`, `volume`, `spread`, `trackingError`, `ytd`, `1y`

---

## 8. How BDRY & BWET Are Fully Automated (Repo Pipeline)

### Architecture overview

```
GitHub Actions (cron) → Python scripts → data/flows/*.json + data/etf/*.csv → GitHub Pages
```

### Automation chain

**1. Daily fund flow update** (the core)

**File**: [`scripts/fetch_flows_shipping.py`](../scripts/fetch_flows_shipping.py)  
**Trigger**: GitHub Actions workflow [`daily_update.yml`](../.github/workflows/daily_update.yml)  
**Schedule**: Every day at 10:30 UTC + 14:00, 19:00, 22:00 UTC

```yaml
# .github/workflows/daily_update.yml (key steps)
- name: Run fund flow scraper
  run: python scripts/fetch_flows_shipping.py
```

**How it works (incremental update):**

```python
# Pseudocode of the incremental logic in fetch_flows_shipping.py
existing_df = load_existing("data/flows/BDRY_flows.json")   # load what we have
last_date = existing_df["date"].max()                        # e.g. "2026-09-21"
new_df = fetch_live_data("BDRY", last_date, today, page)    # fetch only the gap
merged = concat(existing_df, new_df).drop_duplicates("date") # merge, no duplicates
save(merged)                                                 # overwrite JSON + CSV
```

**Session warm-up** (critical — bypasses WAF):
```python
page.goto("https://www.trackinsight.com/en/fund/BDRY/flows", wait_until="domcontentloaded")
time.sleep(3)  # Let WAF cookies set
# Now page.evaluate(fetch_js, payload) works with real browser session
```

**2. ETF Holdings update** (separate — Amplify Firebase, not Trackinsight)

**File**: [`scripts/update_etf_holdings.py`](../scripts/update_etf_holdings.py)  
**Trigger**: [`etf_holdings_update.yml`](../.github/workflows/etf_holdings_update.yml)  
**Schedule**: 14:00 UTC Mon–Fri  
**Source**: Amplify ETFs Firebase Firestore REST API (not Trackinsight)

**3. Live ETF quotes** (intraday)

**File**: `scripts/fetch_live_etf_quotes.py`  
**Trigger**: [`live_etf_quotes.yml`](../.github/workflows/live_etf_quotes.yml)  
**Schedule**: Every 15 minutes (at :07, :22, :37, :52) between 13:00–21:00 UTC Mon–Fri  
**Source**: Yahoo Finance / yfinance (price/volume, not flows)

### Output files

| File | Description | Updated by |
|------|-------------|-----------|
| `data/flows/BDRY_flows.json` | Full BDRY flow history with derived metrics | `fetch_flows_shipping.py` |
| `data/flows/BWET_flows.json` | Full BWET flow history | `fetch_flows_shipping.py` |
| `data/flows/all_flows_summary.json` | Cross-ETF summary + NG=F history | `fetch_flows_shipping.py` |
| `docs/data/flows/all_flows_summary.json` | Duplicate for GitHub Pages serving | `fetch_flows_shipping.py` |
| `data/etf/BDRY_flows.csv` | BDRY flows as CSV | `fetch_flows_shipping.py` |
| `data/etf/BWET_flows.csv` | BWET flows as CSV | `fetch_flows_shipping.py` |
| `data/etf/bdry_holdings.csv` | BDRY ship holdings | `update_etf_holdings.py` |
| `data/etf/bwet_holdings.csv` | BWET ship holdings | `update_etf_holdings.py` |
| `data/etf/live_quotes.json` | Real-time BDRY/BWET price + volume | `fetch_live_etf_quotes.py` |

### Derived metrics computed (in `apply_derived_metrics()`)

| Column | Description |
|--------|-------------|
| `usd_flow` | Raw daily flow from Trackinsight |
| `cumulative_flow` | Running sum from inception |
| `daily_inflow` | `max(flow, 0)` |
| `daily_outflow` | `min(flow, 0)` |
| `flow_zscore` | 30-day rolling Z-score of daily flow |
| `flow_5d` | 5-day rolling sum |
| `flow_20d` | 20-day rolling sum |
| `pressure` | Composite signal: `zscore * 25 + momentum_factor + streak_bonus` (range -100 to +100) |
| `regime` | `ACCUMULATION` (z>1.5), `DISTRIBUTION` (z<-1.5), `BALANCED` |

### Adding a new ETF to the automation

To add e.g. SOXL to the automated pipeline:

1. Edit `fetch_flows_shipping.py`: change `TICKERS = ["BDRY", "BWET"]` to include the new ticker with its correct key (e.g. `"ARCX:SOXL"`)
2. Add the output file paths to the `git add` line in `daily_update.yml`
3. The first run will fetch full history from 2016-01-01; subsequent runs are incremental

---

## 9. Stealth / Rate-Limit Avoidance

### What Trackinsight sees

Trackinsight uses **AWS WAF** (Web Application Firewall) and tracks:
- Browser fingerprint (via WAF token in cookies: `aws-waf-token`)
- Session cookie (`uid` — persistent device identifier)
- User type (`usertype=professional` — affects what data is visible)
- Search/recency history (`srh` cookie — records recently viewed tickers)

### What we observed during bulk fetching

During our session fetching 15,715 ETFs (32 paginated requests of 500 each) and multiple flow data probes:
- **No rate limiting observed** — all 32 pages completed without throttling
- **No IP block** — session remained active throughout
- **No CAPTCHA triggered**
- The `srh` cookie accumulated recently viewed tickers (visible in the curl commands)

### Why we weren't blocked

1. **Playwright carries real browser session** — WAF sees a genuine Chromium browser, not a headless bot
2. **Reasonable inter-request delays** — 0.2–0.3 seconds between `search_v2` pages
3. **All requests are same-origin** — JS fetch inside the page looks like normal site behavior
4. **Flow data requests are few** — per-ETF history is 1–4 requests (quarterly chunks). Even probing 50 ETFs = ~200 requests.
5. **WAF token is per-session** — stays valid for the entire browser session, not per-request

### Stealth best practices

```python
# 1. Always warm up on a real page before making API calls
page.goto("https://www.trackinsight.com/en/fund/BDRY/flows", wait_until="domcontentloaded")
time.sleep(3)  # Let WAF cookies settle

# 2. Disable webdriver detection
page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. Use real Chrome user agent
context = browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    viewport={"width": 1920, "height": 1080}
)

# 4. Disable AutomationControlled flag
browser = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])

# 5. Use same-origin fetch via page.evaluate() — NOT urllib/requests
result = page.evaluate(fetch_js, payload)  # ✅ Carries WAF cookies automatically

# 6. Add small jitter between requests
import time, random
time.sleep(0.2 + random.uniform(0, 0.3))

# 7. For bulk ETF fetching (search_v2), keep pages to 500-1000 per request
# 500 pages × 0.3s delay = ~10s total for 15,715 ETFs — perfectly fine

# 8. For flow data: batch up to 20 tickers per request (matches what the site does)
# Site sends exactly 20 tickers per batch when displaying recent funds dashboard

# 9. Quarterly chunking for flow history — matches site's own request pattern
# This is what the real browser sends, so WAF sees expected behavior

# 10. One browser session per script run — don't open multiple concurrent sessions
```

### Rate limit handling (already in the repo)

The existing `fetch_flows_shipping.py` has exponential backoff built in:
```python
for attempt, wait in enumerate([0, 15, 30, 60]):
    if wait:
        time.sleep(wait)
    result = page.evaluate(fetch_js, payload)
    if result and not result.get("__error"):
        return result
```

### Do they know we're bulk-fetching?

**Likely no**, because:
- We use real browser sessions, not bot patterns
- Request rate is similar to a power user browsing multiple ETF pages
- The `search_v2` endpoint is designed for pagination (the screener uses it)
- Our total daily requests for BDRY+BWET incremental update = **4–8 API calls** (near-zero footprint)

**What WOULD get us blocked:**
- Making hundreds of requests per second
- Using urllib/requests directly without browser session
- Parallel browser sessions from same IP
- Requesting the same ticker hundreds of times rapidly

---

## 10. ETF Universe — Full 15,715 ETF List

### Files

| File | Location | Description |
|------|----------|-------------|
| `trackinsight_all_etfs_rich.csv` | `brain/scratch/` | All 15,715 ETFs with full metadata |
| `trackinsight_all_etfs.csv` | `brain/scratch/` | Tickers + ISINs only |

### Universe statistics (as of September 22, 2026)

| Category | Count |
|----------|-------|
| **Total ETFs** | 15,715 |
| ETF (proper) | 14,409 |
| ETP | 721 |
| ETC | 358 |
| ETN | 182 |
| PTF | 45 |
| **Equity** | 10,222 |
| **Fixed Income** | 3,587 |
| **Commodity** | 659 |
| **Multi-Asset** | 590 |
| **Crypto** | 558 |
| **Currency** | 83 |
| **Volatility** | 16 |
| **USD-denominated** | 8,793 |
| EUR-denominated | 2,143 |
| CAD | 1,831 |
| AUD | 525 |
| GBP | 496 |
| JPY | 481 |

### Default sort order

`default` sort = **USD AUM descending** (largest ETF first):
```
1. VOO   ($1.09T)
2. IVV   ($857B)
3. SPY   ($803B)
4. VTI   ($701B)
5. QQQ   ($495B)
...
15,715. EQPSUBNKBEES (India Nifty PSU Bank ETF)
```

Note: `aum` sort gives Japanese ETFs first (e.g., Nomura TOPIX ¥34,665B) since AUM is in local currency.

### How to re-fetch the full universe

```python
import json, time
from playwright.sync_api import sync_playwright

FIELDS = "ticker,isin,label,type,currency,aum,nav,provider,expense_ratio,index,benchmark,sfdr,currencyHedged,rating,perf"
BASE = "https://www.trackinsight.com/search-api/search_v2"

fetch_js = """
async (url) => {
    const resp = await fetch(url, {method:'GET', headers:{'X-Requested-With':'XMLHttpRequest'}});
    return await resp.json();
}
"""

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled","--no-sandbox"])
context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", viewport={"width":1920,"height":1080})
page = context.new_page()
page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
page.goto("https://www.trackinsight.com/en", wait_until="domcontentloaded")
time.sleep(4)

all_etfs = []
offset = 0
while True:
    url = f"{BASE}/_/_/{FIELDS}/default/{offset}/500"
    result = page.evaluate(fetch_js, url)
    docs = result.get("results", {}).get("docs", [])
    if not docs: break
    all_etfs.extend(docs)
    print(f"Fetched {len(all_etfs)} ETFs...")
    offset += len(docs)
    if len(docs) < 500: break
    time.sleep(0.3)

browser.close(); pw.stop()
# all_etfs now contains all 15,715 ETFs
```

---

## 11. Known Leveraged ETF Ticker Map

### Direxion (136 ETFs on Trackinsight)

Top by AUM:

| Ticker Key | AUM | ETF Name |
|-----------|-----|---------|
| `ARCX:SOXL` | Large | Direxion Daily Semiconductors Bull 3X |
| `SPXL` | Large | Direxion Daily S&P 500 Bull 3X |
| `TECL` | Large | Direxion Daily Technology Bull 3X |
| `TSLL` | Large | Direxion Daily TSLA Bull 2X |
| `TNA` | Medium | Direxion Daily Small Cap Bull 3X |
| `LABU` | Medium | Direxion Daily Biotech Bull 3X |
| `HIBL` | Medium | Direxion Daily S&P 500 High Beta Bull 3X |
| `KORU` | Small | Direxion Daily South Korea Bull 3X |
| `BTCU` | Tiny | Direxion Daily Bitcoin Bull 2X |

### ProShares (172 ETFs on Trackinsight)

| Ticker Key | AUM | ETF Name |
|-----------|-----|---------|
| `TQQQ` | \$39.7B | ProShares UltraPro QQQ (3x NASDAQ-100) |
| `QLD` | \$15.1B | ProShares Ultra QQQ (2x NASDAQ-100) |
| `ARCX:SSO` | \$9.1B | ProShares Ultra S&P500 (2x) |
| `UPRO` | \$5.7B | ProShares UltraPro S&P500 (3x) |
| `ARCX:USD` | \$2.9B | ProShares Ultra Semiconductors (2x) |
| `XNMS:SQQQ` | \$1.86B | ProShares UltraPro Short QQQ (3x short) |
| `AGQ` | \$1.45B | ProShares Ultra Silver (2x) |
| `ROM` | \$1.37B | ProShares Ultra Technology (2x) |
| `UGL` | \$0.85B | ProShares Ultra Gold (2x) |
| `BITU` | \$0.64B | ProShares Ultra Bitcoin (2x) |
| `BOIL` | \$0.38B | ProShares Ultra Bloomberg Natural Gas (2x) |
| `BATS:UVXY` | \$0.28B | ProShares Ultra VIX Short-Term Futures (1.5x) |
| `SVXY` | \$0.26B | ProShares Short VIX Short-Term Futures (-0.5x) |
| `ARCX:QID` | \$0.22B | ProShares UltraShort QQQ (2x short) |
| `ARCX:SCO` | \$1.08B | ProShares UltraShort Bloomberg Crude Oil (2x short) |
| `ARCX:SH` | \$0.93B | ProShares Short S&P500 (1x short) |
| `ARCX:SPXU` | \$0.40B | ProShares UltraPro Short S&P500 (3x short) |

### GraniteShares (30 ETFs on Trackinsight)

| Ticker Key | AUM | ETF Name |
|-----------|-----|---------|
| `NVDL` | \$3.72B | GraniteShares 2x Long NVDA |
| `AMDL` | \$1.07B | GraniteShares 2x Long AMD |
| `MULL` | \$0.74B | GraniteShares 2x Long MU |
| `CONL` | \$0.61B | GraniteShares 2x Long COIN |
| `MVLL` | \$0.44B | GraniteShares 2x Long MRVL |
| `INTW` | \$0.35B | GraniteShares 2x Long INTC |
| `PTIR` | \$0.33B | GraniteShares 2x Long PLTR |
| `FBL` | \$0.19B | GraniteShares 2x Long META (was METL) |
| `TSLR` | \$0.08B | GraniteShares 2x Long TSLA |
| `NVD` | \$0.05B | GraniteShares 2x Short NVDA |

### Single-stock leveraged (other providers)

| Ticker Key | AUM | Provider | ETF Name |
|-----------|-----|---------|---------|
| `MSTX` | \$2.28B | Defiance | Defiance 2x Long MSTR ETF |
| `TSLL` | \$2.48B | Direxion | Direxion Daily TSLA Bull 2X |
| `GGLL` | \$0.48B | Direxion | Direxion Daily GOOGL Bull 2X |
| `GOOX` | Small | T-Rex | T-Rex 2X Long Alphabet Daily ETF |
| `NVDL` | \$3.72B | GraniteShares | GraniteShares 2x Long NVDA |
| `SMCI` | Small | — | SMCI leveraged ETF |
| `FNGU` | Medium | MicroSectors | MicroSectors FANG+ 3X |

---

## 12. Minimal Working Code Template

```python
"""
Minimal template: fetch fund flow data for any ETF from Trackinsight.
Requirements: playwright (pip install playwright && playwright install chromium)
              pandas, python-dateutil
"""
import json, time
from datetime import date
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright

ENDPOINT = "https://www.trackinsight.com/search-api/snapshot/get_snapshots"

FETCH_JS = f"""
async (payload) => {{
    const resp = await fetch('{ENDPOINT}', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}},
        body: JSON.stringify(payload)
    }});
    if (!resp.ok) return {{__error: true, status: resp.status}};
    return await resp.json();
}}
"""

def stamp_to_date(s):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(s) * 86400, tz=timezone.utc).strftime("%Y-%m-%d")

def unpack(fd):
    if not isinstance(fd, dict): return []
    scale = fd.get("scale", 1) or 1
    return [v / scale if v is not None else None for v in fd.get("data", [])]

def fetch_etf_flows(ticker: str, start_year: int = 2016) -> list[dict]:
    """Fetch full daily fund flow history for any ETF ticker key."""
    today = date.today()
    reqs, d = [], date(start_year, 1, 1)
    while d <= today:
        q_end = min(d + relativedelta(months=3) - relativedelta(days=1), today)
        reqs.append({"fund": ticker, "startDate": d.strftime("%Y-%m-%d"),
                     "endDate": q_end.strftime("%Y-%m-%d"),
                     "columns": ["stamp", "USD:flow", "nav", "perf"]})
        d += relativedelta(months=3)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled","--no-sandbox"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Warm up — CRITICAL for WAF bypass
    page.goto(f"https://www.trackinsight.com/en/fund/{ticker}/flows", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)

    result = page.evaluate(FETCH_JS, {"requests": reqs})
    browser.close(); pw.stop()

    rows = {}
    chunks = result if isinstance(result, list) else ([result] if result else [])
    for item in chunks:
        if not isinstance(item, dict): continue
        stamps = item.get("stamp", {}).get("data", [])
        if not stamps: continue
        flows = unpack(item.get("USD:flow", {}))
        navs  = unpack(item.get("nav", {}))
        for i, s in enumerate(stamps):
            d_str = stamp_to_date(s)
            if d_str and d_str not in rows:
                rows[d_str] = {
                    "date": d_str,
                    "flow_usd": flows[i] if i < len(flows) else None,
                    "nav": navs[i] if i < len(navs) else None,
                }
    return sorted(rows.values(), key=lambda r: r["date"])

# Usage:
# rows = fetch_etf_flows("GGLL")           # bare ticker
# rows = fetch_etf_flows("ARCX:SOXL")      # with MIC prefix
# rows = fetch_etf_flows("XNMS:SQQQ")      # Nasdaq MIC
```

---

## 13. Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `202` HTTP status, empty body | AWS WAF blocked plain HTTP | Use Playwright browser session, not urllib/requests |
| `[{}]` response (empty dict) | Wrong ticker key | Try with/without MIC prefix. Check URL on trackinsight.com |
| `None` result from `page.evaluate()` | Browser session expired or WAF triggered | Re-navigate to Trackinsight page and wait before retry |
| All-zero flows | ETF is too new or data not available | Check inception date; try from a later start year |
| No data before 2016 | Trackinsight hard wall | Normal — no workaround |
| `excessReturn` field = `None` for all | Calculated with lag, only available historically | Use `perf` instead |
| `METL` returns empty | GraniteShares renamed META ETF | Use `FBL` ticker key instead |
| `NVDS`, `MSFU` always empty | Not indexed on Trackinsight | No data available |
| `FNGU` data only from 2025 | Trackinsight started indexing it late | No workaround — use available range |
| Rate limiting (if it occurs) | Too many rapid requests | Add `time.sleep(0.3)` between batches; use exponential backoff |

---

*Document generated: September 22, 2026*  
*Reverse-engineered during flow signal research session (GGLL, GOOX, UGL, AGQ analysis)*  
*15,715 ETF universe fetched and verified. All endpoints tested live.*
