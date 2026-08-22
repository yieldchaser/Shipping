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
   **api2.sgx.com** — exists (used by EOD scrapers) but returns 404 on the
   history path; it fronts a different service.
3. **Wayback Machine** — 0 captures exist for
   `api.sgx.com/derivatives/v1.0/history/symbol/{c,p,s,h}wf*`. (Captures of
   OTHER tickers like ACFJ25/BZFJ24 exist — if you find ANY archived capture
   of a CWF/PWF/SWF/HWF symbol URL anywhere, that IS the jackpot: report it
   immediately with the snapshot URL.)
4. **sgx.com site bundles** — public quote widgets use the same history API.
5. **Settlement-report endpoints** (`/derivatives/daily-settlement-prices`,
   `/v1.0/reports/settlement-prices`) — SPA shell / 403; no Wayback captures
   2025–26.
6. **links.sgx.com free tick archive** (`/1.0.0/derivatives-historical/{sessionId}/WEBPXTICK_DT.zip`,
   session IDs are sequential integers — 5420 = 2023-05-16, 5943 =
   2025-05-16; inner CSV names embed dates, so IDs map to dates via ranged
   reads). The archive RETAINS 2025 sessions (~20 MB/session), but a full
   symbol scan of session 5963 (2025-06-13, 236 MB of ticks) shows **zero
   freight products**: all 103 symbol stems are equity-index/rates futures.
   Freight FFAs are excluded from the public tick feed by design. TC.txt is a
   small trade-amendments log with no settlements.

### Where a LOGIN actually gets you the prices (official, paid)

7. **SGX Data Desk — <https://sgxdatadesk.com>** — SGX's official data shop;
   account creation + order flow for "Derivatives Data Products"
   (open interest, exposure, EOD/history datasets). This and
   **<https://www.sgx.com/data-connectivity/historical-data>** (Derivatives
   Historical Data: WEBPXTICK tick files + EOD/settlement series, licensed
   per range/market) are THE legitimate purchase routes. Expect a licensing
   agreement, per-dataset pricing, and no-redistribution terms — fine for our
   internal display use. If ordering, ask specifically for **daily settlement
   prices for freight/freight-futures products, 2024-01-01 → 2026-03-31,
   all contract months**.
8. **Interactive Brokers is a dead end**: IBKR carries SGX equity/index
   derivatives (A50, Nifty, Nikkei-on-SGX) but does NOT offer SGX freight
   futures/FFAs at all — those clear through SGX Clear via specialist
   intermediaries (KGI Securities Singapore, SSY Futures, FIS, Clarksons).
   A brokerage account would only ever give your own statements, never
   exchange-wide expired-contract settlement archives.

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
7. **KGI Securities Singapore** (<https://www.kgieworld.sg/futures/sgx-ffa-futures-and-options>)
   actively brokers SGX FFAs — mine their daily/weekly close sheets and
   market-commentary pages for 2025.
8. **Signal Ocean FFA Report (powered by SSY)** — commercial but covers
   "expired and non-expired" FFA prices across all four vessel classes; a
   paid-plan sample/trial could legitimately fill the gap
   (<https://www.thesignalgroup.com/newsroom/forward-freight-agreement-ffa-and-freight-risk-management-a-powerful-mix>).
9. **Exchange-traded note/index documents**: Breakwave Advisors' BWET/BDRY
   index methodology docs and daily index files reference component FFA
   settlements; their fund filings (SEC EDGAR full-text search: "CWFH25",
   "Capesize futures settlement") may embed values.

### Tier 3 — Dataset mirrors
10. Nasdaq Data Link (Quandl), Kaggle, GitHub scraped-data repos: search
    "SGX freight futures", "FFA settlement prices", "CWFH25".
11. Academic datasets (SSRN papers on FFA pricing sometimes publish
    supplementary CSVs of SGX settlements).
12. **EEX also clears dry-bulk FFAs** (same underlying Baltic indices) — check
    whether EEX publishes free daily settlement files that include their dry
    freight contracts; values differ from SGX marks only by clearing-basis
    convention and are usually identical to the index-based fixings.

### Tier 4 — Reconstruction fallback (clearly-labeled PROXY, not official)
13. Obtain daily **Baltic C5TC / P5TC / S5TC / H5TC weighted TC averages**
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
