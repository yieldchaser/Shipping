# Data Acquisition Audit & Sourcing Assessment

**Date:** August 14, 2026  
**Status:** Accounting Engine Frozen; Sourcing Assessment Completed  
**Target Funds:** Amplify Breakwave Dry Bulk Shipping ETF (**BDRY**) & Amplify Breakwave Tanker Shipping ETF (**BWET**)  

---

## 1. Executive Summary

In accordance with strict quantitative finance accounting governance, the ETF accounting engine has been frozen under the canonical status:
> **"Partial accounting decomposition; not a validated NAV reconstruction; not trade-ready."**

This document establishes the official data inventory, identifies exact data gaps between public daily snapshot disclosures and full custody accounting ledgers, and specifies the sourcing requirements for authoritative data acquisition.

---

## 2. Authoritative Data Sourcing Assessment Matrix

| Data Dimension | Public Sourced Artifacts Available on Disk | Coverage / Date Span | Missing Elements (Data Gaps) | Required Authoritative Source Plan |
| :--- | :--- | :--- | :--- | :--- |
| **1. Daily Shares Outstanding** | Periodic SEC Form 10-Q filings (March 31, 2026: 4,275,040 BDRY; 475,100 BWET). | Quarterly snapshot dates only. | **Daily share count time series is unobserved.** Daily basket creations/redemptions cannot be verified without dated share ledgers. | Ingest monthly SEC Form N-PORT disclosures or transfer agent (Foreside / U.S. Bancorp) daily share capital ledgers. |
| **2. Official Daily NAV & Net Assets** | `data/etf/BDRY_flows.csv` (2,100 dates) & `BWET_flows.csv` (820 dates). | BDRY: 2018-03-23 to 2026-08-12<br>BWET: 2023-05-04 to 2026-08-12 | Daily Net Assets in total dollars requires multiplying NAV by daily shares. Missing Sunday disclosures (e.g. 2026-06-21). | Official NAV per share is verified from fund administrator records. Total Net Assets ($) will be linked once daily share ledgers are ingested. |
| **3. Daily Custody & FCM Cash Ledgers** | Form 10-Q Balance Sheets (AGPXX money market + Marex broker cash). | Quarterly snapshot dates only. | **Daily bank interest credits and daily custodian operating expense bills are unobserved.** | Ingest daily custody bank cash balance reports and FCM margin equity statements from U.S. Bank Global Fund Services and Marex Financial Ltd. |
| **4. FFA Settlement Curves** | `data/futures/sgx_*.csv` (29,776 contract settlement rows across Cape, Pana, Supra, Handy). | 2018 to 2026 daily exchange clearing settlements. | **Intraday trade fill execution prices for contract rolls are unobserved.** Public disclosures only show 4:00 PM EST marks. | Ingest intraday trade confirmation logs / FIX execution feeds from Marex Financial Ltd. |
| **5. Secondary Market ETF Closes** | `data/etf/bdry_liquidity.csv` (2,109 dates) & `bwet_liquidity.csv` (823 dates). | BDRY: 2018-03-22 to 2026-08-13<br>BWET: 2023-05-03 to 2026-08-13 | Exchange market holidays (e.g. NYSE holiday on 2026-08-11) produce missing market closes. | Fully decoupled: market holidays affect secondary market spreads only, not fund NAV accounting. |

---

## 3. Strict Non-Substitution & Gating Governance

1. **Zero Synthetic Proxies:**
   - Spot indices (BDI, BCI, BPI, BSI) and period time-charter rates (Fearnleys, Alibra) will **never** be substituted for exact FFA marks (Capesize 5TC, Panamax 5TC/4TC, Supramax 10TC, VLCC TD3C, Suezmax TD20).
2. **Zero Fabricated Share Defaults:**
   - No hardcoded share assumptions ($3.8\text{M} / 200\text{k}$) will be used. In the absence of daily share ledgers, fund-level total dollar NAV is left as `NaN` / `MISSING_INPUT`.
3. **Zero Look-Ahead Initialization:**
   - On non-trading days where NAV is absent, records remain `NaN` without forward or backward lookups.
4. **Frozen Engine Status:**
   - All predictive forecasting, alpha betting, and trading features remain strictly suspended until the authoritative data streams above are secured.
