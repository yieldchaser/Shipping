# Milestone 3 Deliverable: Authoritative Data Acquisition Report

**Target Assets:** Breakwave Dry Bulk Shipping ETF (**BDRY**) & Breakwave Tanker Shipping ETF (**BWET**)  
**Milestone:** Milestone 3 (Authoritative Data Acquisition Only)  
**Accounting Engine Status:** **"Authoritative-data feasibility audit complete; acquisition blocked pending external access or licensing."**  
**Date:** August 14, 2026  

---

## 1. Executive Summary

Milestone 3 focuses exclusively on authoritative data acquisition and objective categorization of all data streams required to unfreeze specific legs of the Breakwave ETF accounting waterfall.

In accordance with strict financial accounting directives:
- **Zero Synthetic Defaults:** No spot index proxies (BDI, BCI, BPI, BSI, BDTI, BCTI), no inferred shares, no forward-filled NAVs, and no synthetic execution prices were used.
- **Zero Engine / UI Alterations:** The accounting engine, UI simulator, and scenario controls remained 100% frozen and unmodified.
- **Cryptographic Provenance:** Every on-disk dataset has been audited and cataloged with immutable SHA-256 checksums, retrieval URLs, and schema definitions in [`data/manifests/data_acquisition_manifest.json`](file:///C:/Users/Dell/Github/Shipping/data/manifests/data_acquisition_manifest.json).

---

## 2. Comprehensive Data Stream Classification Matrix

| Priority & Stream Name | Classification | Primary Source Entity | Upstream URL / Access Method | Local File Path / Status | Unfreezing Recommendation |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **P1.1: SEC Form 10-Q Shares** | `PARTIAL` | SEC EDGAR / Amplify ETF Trust | [SEC EDGAR Browse](https://www.sec.gov/edgar/browse/?CIK=0001719543) | `docs/BDRY-BWET_Form10-Q_March-31-2026.pdf` | **Quarterly point-in-time balance sheet fixtures only.** |
| **P1.2: Daily Transfer Agent Shares Ledger** | `INACCESSIBLE` | U.S. Bancorp Fund Services / Foreside | Institutional Custodian API Feed | *Proprietary (Confidential)* | **CANNOT UNFREEZE daily share accounting or per-share fund-level NAV conversion.** |
| **P1.3: Inferred Shares from Flow / NAV** | `REJECTED` | Synthetic Mathematical Division | N/A | *Strictly Prohibited* | **REJECTED (Violates non-inference accounting standard).** |
| **P2.1: BDRY Official NAV History** | `AVAILABLE` | Amplify ETFs / U.S. Bank Global Fund Services | [Amplify BDRY Disclosures](https://amplifyetfs.com/bdry/) | `data/etf/BDRY_flows.csv`<br>`data/flows/BDRY_flows.json` | **UNFREEZE official published per-share NAV performance comparison.** |
| **P2.2: BWET Official NAV History** | `AVAILABLE` | Amplify ETFs / U.S. Bank Global Fund Services | [Amplify BWET Disclosures](https://amplifyetfs.com/bwet/) | `data/etf/BWET_flows.csv`<br>`data/flows/BWET_flows.json` | **UNFREEZE official published per-share NAV performance comparison.** |
| **P2.3: Daily Total Net Assets in USD** | `PARTIAL` | Amplify ETF Trust | Public Daily CSV Disclosures | Quarterly in 10-Q (Daily unobserved) | **DO NOT UNFREEZE total dollar NAV waterfall without daily shares ledger.** |
| **P3.1: SEC 10-Q Balance Sheet Cash** | `PARTIAL` | SEC EDGAR / Amplify ETF Trust | [SEC EDGAR Browse](https://www.sec.gov/edgar/browse/?CIK=0001719543) | `docs/BDRY-BWET_Form10-Q_March-31-2026.pdf` | **UNFREEZE quarterly balance sheet baseline fixtures.** |
| **P3.2: Daily Marex FCM Margin Cash** | `INACCESSIBLE` | Marex Financial Ltd (FCM) | Client Clearing Portal / MT940 SWIFT | *Proprietary (Confidential)* | **CANNOT UNFREEZE daily broker collateral / variation margin transfers.** |
| **P3.3: Daily Custody Interest & OpEx Ledgers** | `INACCESSIBLE` | U.S. Bank Global Fund Services | Institutional Custody Ledger Access | *Proprietary (Confidential)* | **CANNOT UNFREEZE daily cash interest or fund expense waterfall legs.** |
| **P3.4: Synthetic Fixed Yield & OpEx Compounding** | `REJECTED` | Synthetic Fixed APY/TER Models | N/A | *Strictly Prohibited* | **REJECTED (Masks SOFR fluctuations, fee waivers, and non-linear billings).** |
| **P4.1: SGX Cleared Dry Bulk FFA Curves** | `AVAILABLE` | Singapore Exchange (SGX) Clearing | [SGX Freight Derivatives](https://www.sgx.com/derivatives/products/freight) | `data/futures/sgx_cape_futures.csv`<br>`sgx_panamax_futures.csv`<br>`sgx_supramax_futures.csv`<br>`sgx_handysize_futures.csv` | **UNFREEZE dry bulk freight forward valuation benchmarks.** |
| **P4.2: Historical Cleared Tanker FFA Curves** | `INACCESSIBLE` | CME Group / ICE / Baltic Exchange | CME DataMine / Baltic API Feed | *Commercial License ($15k+/yr)* | **CANNOT UNFREEZE historical BWET forward curve reconstruction.** |
| **P4.3: Spot Baltic Index Tanker Proxies** | `REJECTED` | Spot Freight Indices (BDTI / BCTI) | N/A | *Strictly Prohibited* | **REJECTED (Spot ignores term structure contango/backwardation & damping).** |
| **P5.1: BDRY Daily Holdings Disclosures** | `AVAILABLE` | Amplify ETFs / Breakwave Advisors | [Amplify BDRY Disclosures](https://amplifyetfs.com/bdry/) | `data/etf/bdry_holdings_history.csv` | **UNFREEZE retained futures variation margin accounting ($\Delta \text{VM}_{\text{retained}}$).** |
| **P5.2: BWET Daily Holdings Disclosures** | `AVAILABLE` | Amplify ETFs / Breakwave Advisors | [Amplify BWET Disclosures](https://amplifyetfs.com/bwet/) | `data/etf/bwet_holdings_history.csv` | **UNFREEZE retained futures variation margin accounting ($\Delta \text{VM}_{\text{retained}}$).** |
| **P5.3: Intraday Roll Trade Execution Logs** | `INACCESSIBLE` | Marex Financial Ltd / Execution Desk | Broker FIX Drop Copies / Confirmations | *Proprietary (Confidential)* | **CANNOT UNFREEZE deterministic roll transaction drag attribution.** |
| **P5.4: Synthetic Mid-Settlement Roll Executions** | `REJECTED` | Synthetic 4:00 PM Mid-Mark Execution | N/A | *Strictly Prohibited* | **REJECTED (Falsely assumes zero execution slippage/spread cost).** |

---

## 3. Cryptographic Provenance & Manifest Registry

Summary of files cryptographically registered in [`data/manifests/data_acquisition_manifest.json`](file:///C:/Users/Dell/Github/Shipping/data/manifests/data_acquisition_manifest.json):

```text
========================================================================================================================
FILE PATH                                | SHA-256 CHECKSUM (FIRST 16 HEX) | FILE SIZE  | TOTAL ROWS | DATE RANGE
------------------------------------------------------------------------------------------------------------------------
data/etf/bdry_holdings_history.csv       | a7ecfa98e004368b...             | 49.3 KB    | 657        | 2026-06-21 to 2026-08-13
data/etf/bwet_holdings_history.csv       | b520694f877f1afa...             | 35.1 KB    | 468        | 2026-06-21 to 2026-08-13
data/etf/BDRY_flows.csv                  | 82c89e23748516b2...             | 104.2 KB   | 2,100      | 2018-03-23 to 2026-08-12
data/etf/BWET_flows.csv                  | 68c19aaedf862989...             | 39.8 KB    | 820        | 2023-05-04 to 2026-08-12
data/etf/bdry_liquidity.csv              | 1b472383309ff1da...             | 74.5 KB    | 2,109      | 2018-03-22 to 2026-08-13
data/etf/bwet_liquidity.csv              | 82c8d9ed223e9a41...             | 28.6 KB    | 823        | 2023-05-03 to 2026-08-13
data/futures/sgx_cape_futures.csv        | b75037d45763b652...             | 448.2 KB   | 7,819      | 2018-04-01 to 2024-12-31
data/futures/sgx_panamax_futures.csv     | d8e03e5c9a09962a...             | 524.1 KB   | 9,091      | 2018-04-01 to 2024-12-31
data/futures/sgx_supramax_futures.csv    | fb79ea1bc465d648...             | 220.8 KB   | 3,823      | 2018-04-01 to 2024-12-31
data/futures/sgx_handysize_futures.csv   | 990bc1e1f13b194d...             | 519.4 KB   | 9,043      | 2018-04-01 to 2024-12-31
docs/BDRY-BWET_Form10-Q_March-31-2026.pdf| 03b887f58a9bfdb4...             | 1.15 MB    | N/A (PDF)  | As of March 31, 2026
========================================================================================================================
```

---

## 4. Institutional Data Gap Analysis

### Gap 1: Daily Shares Outstanding & AP Basket Settlement Timing
- **Institutional Owner:** U.S. Bancorp Fund Services, LLC / Foreside Fund Services, LLC / Depository Trust & Clearing Corporation (DTCC).
- **Access Barrier:** Real-time NSCC Continuous Net Settlement (CNS) daily participant reports are restricted to registered Authorized Participants (Virtu, Citadel, Jane Street) and fund custodians.
- **Accounting Consequence:** Prevents exact day-by-day conversion of total dollar fund NAV to per-share NAV when basket creations occur mid-session.
- **Resolution Plan:** Request monthly SEC Form N-PORT filings from EDGAR (which report month-end total net assets and exact shares outstanding).

### Gap 2: Daily Custody Bank Interest Credits & FCM Broker Cash Transfers
- **Institutional Owner:** U.S. Bank Global Fund Services (Custodian) and Marex Financial Ltd (FCM).
- **Access Barrier:** Daily MT940 bank statement SWIFT messages and daily FCM commodity equity run sheets are confidential client records.
- **Accounting Consequence:** Daily overnight repo interest credits ($\sim 4.85\%\text{ APY}$) and daily custody billing debits ($\sim 3.50\%\text{ TER}$) cannot be validated with independent daily vouchers.
- **Resolution Plan:** Reconcile on quarterly Form 10-Q balance sheet cycles; preserve `PARTIAL_DISCLOSURE_UNRECONCILED` labeling for daily sessions.

### Gap 3: Intraday Roll Trade Execution Fill Prices
- **Institutional Owner:** Marex Financial Ltd / Breakwave Advisors Execution Desk.
- **Access Barrier:** Broker trade confirmation tickets and FIX drop copy feeds are internal trading records.
- **Accounting Consequence:** Transaction slippage and execution drag during quarterly rolls cannot be separated from pure market delta.
- **Resolution Plan:** Maintain explicit disclaimer that roll execution drag is unobserved and not synthetically estimated.

---

## 5. Leg-by-Leg Unfreezing Recommendations

| Accounting Engine Leg | Status | Unfreezing Action & Justification |
| :--- | :---: | :--- |
| **Leg 1: Point-in-Time Contract Marks & Holdings Valuation** | **UNFREEZE** | Fully supported by daily disclosed contract lots and exchange marks in `bdry_holdings_history.csv` / `bwet_holdings_history.csv`. |
| **Leg 2: Retained Futures Variation Margin ($\Delta \text{VM}_{\text{retained}}$)** | **UNFREEZE** | Fully supported by prior-day quantity $Q_{i, t-1}$ and daily price deltas $(P_{i, t} - P_{i, t-1})$. |
| **Leg 3: Official NAV Benchmark Performance Tracking** | **UNFREEZE** | Fully supported by 2,100 BDRY sessions and 820 BWET sessions in `BDRY_flows.csv` / `BWET_flows.csv`. |
| **Leg 4: Form 10-Q Balance Sheet Recomputation** | **UNFREEZE** | Fully supported by atomic inputs in `scripts/test_10q_dynamic_engine.py`. |
| **Leg 5: Daily Fund-Level Total Dollar NAV Waterfall** | **KEEP FROZEN** | **Frozen** due to unobserved daily custody cash vouchers and unobserved daily share count ledgers. |
| **Leg 6: Deterministic Roll Cost Attribution** | **KEEP FROZEN** | **Frozen** due to unobserved intraday trade execution fill prices. |
| **Leg 7: Forward Scenario Forecasting & Predictive Signals** | **KEEP FROZEN** | **Strictly suspended** per financial governance standards. |
