# Research Mission: Recover Redacted SGX Freight-Futures Settlement Prices

Paste this whole document into your web-searching AI agent. It contains the
exact data spec, facts already verified (so no effort is wasted re-testing
dead ends), a ranked source list, a validation protocol, and an output
contract.

---

## 1. MISSION

Find **daily settlement prices** for Singapore Exchange (SGX)-cleared freight
futures ("FFA futures") covering the windows where our archive has none:

- Products / ticker prefixes:
  - `CWF*` = Capesize futures (e.g. CWFH25 = March 2025)
  - `PWF*` = Panamax, `SWF*` = Supramax, `HWF*` = Handysize
- Priority window: **2025-01-01 → 2026-03-04** (complete blackout)
- Secondary window: **pre-2024-01-19** (prices zeroed; anything earlier than
  Jan 2024 would extend deep-history)
- Any granularity helps: daily > weekly > monthly > expiry-day final
  settlements only.

## 2. WHAT WE ALREADY HOLD (do NOT re-collect)

Per product (`data/futures/sgx_*_futures_history.csv`, 324,547 rows total):

- Full daily session grid back to 2022-03 for every ticker (price mostly 0),
  with **volume and open-interest fully populated** (never redacted).
- Real nonzero settlement prices ONLY on sessions that actually cleared:
  typically ~7 days per contract life, all inside 2024 (e.g. CWFZ25:
  2024-01-19 = $21,169, 2024-06-28 = $25,054, ... 7 total).
- Daily prices Mar-2026 → today via live polling (authoritative).

## 3. VERIFIED DEAD ENDS (skip these entirely)

Tested directly against the live systems during the investigation:

1. **api.sgx.com/derivatives/v1.0/history/symbol/{ticker}** — serves volume +
   open-interest full-depth but zeroes ALL price fields
   (`daily-settlement-price-abs`, `daily-settlement-price`,
   `preliminary-settlement-price`, `last-trade-price`) outside its entitlement
   window. Verified: Jan-2025 record shows volume=70, OI=4521, every price
   field 0.0. No `days=`/`params=` variation changes this.
2. **api.sgx.com v2.0 / marketdata hosts** — HTTP 403.
3. **Wayback Machine** — 0 captures exist for
   `api.sgx.com/derivatives/v1.0/history/symbol/{c,p,s,h}wf*`. (Captures of
   OTHER tickers like ACFJ25/BZFJ24 exist — if you find ANY archived capture
   of a CWF/PWF/SWF/HWF symbol URL anywhere, that IS the jackpot: report it
   immediately with the snapshot URL.)
4. **sgx.com site bundles** — public quote widgets use the same history API.
5. **Settlement-report endpoints** (`/derivatives/daily-settlement-prices`,
   `/v1.0/reports/settlement-prices`) — SPA shell / 403; no Wayback captures
   2025–26.

Constraint: **publicly accessible sources only** — no paywalled terminals,
no leaked credentials, no ToS-circumvention tooling.

## 4. RANKED HUNT LIST (work top-down)

### Tier 1 — Official SGX publications (most authoritative)
1. SGX **"Derivatives Market Report"** / monthly & annual derivatives
   statistics (PDF/XLSX). Check whether any edition includes DAILY settlement
   price tables for FFA products, or month-end settlement tables per contract
   month. Sources: sgx.com statistics pages (current + Wayback snapshots of
   those pages from mid-2025), SGX Academy publications, SGX annual reports.
2. SGX **product information sheets / contract calendars** for freight
   futures — occasionally include "final settlement price" tables per expired
   series.
3. SGX **regulatory disclosures / notice archive** — expiry settlement
   notices sometimes quote final settlement values per contract.

### Tier 2 — Archived broker & market commentary (most likely hit rate)
Broker desks publish FFA close tables daily/weekly. Hunt 2025-dated editions:
4. **FIS (Freight Investor Services)** — daily FFA market reports / YouTube
   descriptions / newsletters mentioning SGX-cleared Capesize futures closes.
5. **Arrow Shipbroking, Braemar ACM, SSY, Clarksons, Howe Robinson** research
   PDFs archived publicly (site `research/` folders, LinkedIn posts,
   TradeWinds quoting "SGX Capesize futures settled at ...").
6. **TradeWinds / Hellenic Shipping News / Splash247** 2025 articles quoting
   specific SGX freight futures settlement numbers (searchable text!).
7. **Exchange-traded note/index documents**: Breakwave Advisors' BWET/BDRY
   index methodology docs and daily index files reference component FFA
   settlements; their fund filings (SEC EDGAR full-text search: "CWFH25",
   "Capesize futures settlement") may embed values.

### Tier 3 — Dataset mirrors
8. Nasdaq Data Link (Quandl), Kaggle, GitHub scraped-data repos: search
   "SGX freight futures", "FFA settlement prices", "CWFH25".
9. Academic datasets (SSRN papers on FFA pricing sometimes publish
   supplementary CSVs of SGX settlements).

### Tier 4 — Reconstruction fallback (clearly-labeled PROXY, not official)
10. Obtain daily **Baltic C5TC / P5TC / S5TC / H5TC weighted TC averages**
    (the actual settlement underlyings) for 2024–2026 from free mirrors:
    Hellenic Shipping News daily Baltic report articles (they print "Capesize
    5TC Average"), TradeWinds daily, archived broker morning notes. We hold
    BCI/BPI spot indices through 2025 but NOT the 5TC averages — do not
    substitute one for the other. If you recover full 5TC dailies, stop there
    and report; the proxy build happens on our side.

## 5. VALIDATION PROTOCOL (mandatory)

Any candidate dataset MUST be checked against our known anchors before being
trusted. Anchors (real SGX settlements we hold) — sample set:

| Contract | Date | Price |
|---|---|---|
| CWFZ25 | 2024-01-19 | 21,169 |
| CWFZ25 | 2024-06-28 | 25,054 |
| CWFZ25 | 2024-08-09 | 24,429 |
| CWFZ25 | 2024-12-31 | 22,336 |

(Full per-contract anchor sets available on request.) If ≥3 overlapping dates
disagree beyond rounding, the source is wrong or uses a different instrument
(OTC FFA vs SGX-cleared are NOT interchangeable) — discard it.

## 6. OUTPUT CONTRACT

Deliver findings as:

```
data/recovery/sgx_price_recovery/
  SOURCE_NOTES.md          # where each value came from, URL, retrieval date
  sgx_cwf_prices.csv       # contract,expiry_month,expiry_year,date(DD-MM-YYYY),
  sgx_pwf_prices.csv       # price,volume?,open_interest?,source_url,confidence
  sgx_swf_prices.csv
  sgx_hwf_prices.csv
```

Minimum acceptable result: even ONE recovered source (e.g. final settlement
values for expired 2025 contracts only) is valuable — report partial finds.

## 7. CONTEXT (why)

These prices power a shipping-analytics platform's expired-contract drilldown
("how did forward expectations compare to realized reality"). Volume/OI are
already complete; only the redacted price layer is missing.
