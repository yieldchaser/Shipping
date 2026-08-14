# Institutional Data Gap Request Packet: Breakwave Shipping ETFs

**Target Funds:**
- **Amplify Breakwave Dry Bulk Shipping ETF (NYSE Arca: BDRY)** (CUSIP: 032108103)
- **Amplify Breakwave Tanker Shipping ETF (NYSE Arca: BWET)** (CUSIP: 032108202)

**Addressed To:**
- **Amplify Investments LLC / Amplify Commodity Trust** (Fund Sponsor & CPO)
- **Breakwave Advisors LLC** (Commodity Trading Advisor / Index Provider)
- **U.S. Bancorp Fund Services, LLC** (Transfer Agent & Fund Administrator)
- **Marex Financial Ltd** (Futures Commission Merchant & Clearing Broker)

**Date of Request:** August 14, 2026  
**Document Classification:** Formal Data Specification & Access Request  

---

## 1. Executive Summary & Purpose of Request

This formal request specifies the primary accounting data feeds required to achieve complete, bit-for-bit daily Net Asset Value (NAV) reconciliation and deterministic roll attribution for the Amplify Breakwave Shipping ETFs (BDRY and BWET).

While monthly accounting statements (under CFTC Rule 4.22(h)) and SEC Form 10-Q/10-K filings provide certified quarterly and monthly ledger balances, daily public disclosures lack line-item cash collateral interest credits, daily expense vouchers, Authorized Participant (AP) share capital transactions, and intraday roll execution blotters. Access to the five specific data streams detailed below is required to close these unobserved accounting residuals.

---

## 2. Itemized Data Stream Specifications

### Stream 1: Historical Daily NAV, Total Net Assets, & Shares Outstanding
* **Owning Entities:** Amplify Investments LLC / U.S. Bancorp Fund Services / Foreside Fund Services
* **Required Coverage Period:**
  - **BDRY:** March 22, 2018 (Inception) to Present
  - **BWET:** May 3, 2023 (Inception) to Present
* **Required Cadence:** Daily (Every NYSE Arca trading day)
* **Required Schema & Fields:**
  1. `TradeDate` (YYYY-MM-DD)
  2. `FundTicker` (`BDRY` / `BWET`)
  3. `FundCUSIP`
  4. `OfficialNAVPerShare` (USD, 4 decimal places)
  5. `TotalFundNetAssets` (USD Net Asset Value at 4:00 PM ET valuation close)
  6. `SharesOutstanding` (Exact integer shares issued and outstanding as of valuation cutoff)
  7. `PreviousDayNAVPerShare` (USD)
  8. `DailyNAVPercentageChange` (%)
* **Delivery Format:** Standard delimited CSV / JSON API endpoint / secure SFTP.

---

### Stream 2: Daily Authorized Participant (AP) Creation & Redemption Ledger
* **Owning Entities:** Foreside Fund Services, LLC (Distributor) / DTCC NSCC CNS Feed
* **Required Coverage Period:** Inception to Present (Daily)
* **Required Schema & Fields:**
  1. `SettlementDate` (YYYY-MM-DD)
  2. `OrderDate` (YYYY-MM-DD)
  3. `FundTicker` (`BDRY` / `BWET`)
  4. `APParticipantName` / `MPID` (e.g. Virtu, Jane Street, Citadel, Flow Traders)
  5. `OrderType` (`CREATION` / `REDEMPTION`)
  6. `BasketsTransacted` (Integer basket count; 1 basket = 25,000 shares)
  7. `SharesIssuedOrRetired` (Integer share count)
  8. `CashInLieuAmountUSD` (USD cash delivered/received in lieu of constituent contracts)
  9. `TransactionFeeChargedUSD` (Standard $500/basket creation/redemption fee)
  10. `NetCashFlowImpactUSD` (Net capital flow into/out of fund)
* **Delivery Format:** Daily AP Activity CSV / NSCC Participant Data Feed.

---

### Stream 3: Portfolio Composition & Creation Basket Files (PCF)
* **Owning Entities:** U.S. Bancorp Fund Services, LLC (Fund Administrator)
* **Required Coverage Period:** Inception to Present (Daily Point-in-Time)
* **Required Schema & Fields:**
  1. `AsOfDate` (YYYY-MM-DD)
  2. `FundTicker` (`BDRY` / `BWET`)
  3. `ConstituentSecurityType` (`COMMODITY_FUTURES` / `MONEY_MARKET` / `CASH_EQUIVALENT`)
  4. `ContractIdentifier` (Full Contract Name, Ticker, Exchange Product Code, CUSIP)
  5. `ClearingExchange` (`NYMEX` / `SGX` / `ICE`)
  6. `StripMonthYear` (e.g. `AUG26`, `SEP26`, `OCT26`)
  7. `TotalFundLots` (Total open contracts held by fund)
  8. `LotsPerCreationBasket` (Component lots per 25,000 share creation unit)
  9. `OfficialClosingMarkPrice` (USD/day or USD/MT settlement price)
  10. `ContractMultiplier` (1.0 for Dry Bulk, 1,000.0 for Tankers)
  11. `ContractNotionalValueUSD`
  12. `CashComponentPerCreationUnit` (Estimated and actual cash per basket)
* **Delivery Format:** Daily Portfolio Composition File (PCF) format / XML / CSV.

---

### Stream 4: Daily Custody Cash, FCM Margin Equity, & Expense Accrual Ledger
* **Owning Entities:** U.S. Bank National Association (Custodian) & Marex Financial Ltd (FCM)
* **Required Coverage Period:** Inception to Present (Daily)
* **Required Schema & Fields:**
  1. `StatementDate` (YYYY-MM-DD)
  2. `FundTicker` (`BDRY` / `BWET`)
  3. `CustodyCashBalanceUSD` (Unencumbered cash held at U.S. Bank)
  4. `MoneyMarketSharesAGPXX` (Shares held in Invesco Government & Agency Portfolio)
  5. `GrossInterestCreditUSD` (Daily overnight repo sweep and Treasury yield credit)
  6. `FCMInitialMarginRequirementUSD` (Margin required by exchange clearing house)
  7. `FCMSegregatedCashEquityUSD` (Total collateral balance held at Marex)
  8. `FCMVariationMarginSettlementUSD` (Daily net cash wire for futures mark-to-market)
  9. `DailySponsorFeeAccrualUSD` (Amplify management fee: greater of 0.15%/0.30% p.a. or contractual min)
  10. `DailyCTAFeeAccrualUSD` (Breakwave CTA license fee: 1.45% p.a.)
  11. `DailyCTAFeeWaiverUSD` (Contractual fee waiver applied under 3.50% expense cap)
  12. `DailyOtherOperatingExpensesUSD` (Custody, legal, audit, administration accruals)
* **Delivery Format:** Daily Custodial General Ledger Extract (MT940 / CSV) & FCM Clearing Statements.

---

### Stream 5: Roll Calendar & Intraday Trade Execution Blotters
* **Owning Entities:** Breakwave Advisors LLC (CTA) & Marex Financial Ltd (Executing Broker)
* **Required Coverage Period:** Quarterly Roll Windows (March, June, September, December 2018–2026)
* **Required Schema & Fields:**
  1. `ExecutionDate` (YYYY-MM-DD)
  2. `ExecutionTimestampUTC` (HH:MM:SS.fff)
  3. `FundTicker` (`BDRY` / `BWET`)
  4. `OrderType` (`CALENDAR_SPREAD` / `OUTRIGHT_BUY` / `OUTRIGHT_SELL`)
  5. `PromptContractCode` (Expiring prompt strip)
  6. `ForwardContractCode` (Deferred replacement strip)
  7. `ExecutedLots` (Number of lots transacted)
  8. `ExecutedPriceOrSpread` (Executed price per unit / spread differential)
  9. `BrokerCommissionExchangeFeesUSD` (Execution brokerage and exchange clearing fee)
  10. `RollScheduleTargetPercentage` (Target % roll completed on trade date)
* **Delivery Format:** Post-Trade Broker Confirmation Blotter / FIX Drop Copy Logs / CSV.

---

## 3. Data Integration & Impact Summary

```text
===================================================================================================================================
DATA STREAM                    | UNLOCKED ACCOUNTING CAPABILITY                   | RESOLVED RESIDUAL
-------------------------------+--------------------------------------------------+------------------------------------------------
Stream 1: Daily NAV & Shares   | Exact fund-level total dollar NAV to per-share   | Eliminates missing daily denominator and
                               | conversion on all interim business days.         | resolves daily tracking error.
-------------------------------+--------------------------------------------------+------------------------------------------------
Stream 2: AP Creation/Redemp   | Exact cash flow and share capital timing         | Isolates capital flow impact from investment
                               | attribution on creation/redemption dates.        | performance.
-------------------------------+--------------------------------------------------+------------------------------------------------
Stream 3: Portfolio PCF Files  | Point-in-time exact basket sizing and underlying | Validates daily target weights (50/40/10 &
                               | contract settlement mark audit trail.            | 90/10) without interpolation.
-------------------------------+--------------------------------------------------+------------------------------------------------
Stream 4: Cash & Expense GL    | Daily interest yield and expense waterfall       | Resolves unobserved cash interest sweep and
                               | decomposition down to the single dollar.         | contractual 3.50% expense cap waivers.
-------------------------------+--------------------------------------------------+------------------------------------------------
Stream 5: Roll Trade Blotters  | Deterministic roll cost attribution and exact    | Separates term-structure roll yield from
                               | intraday transaction drag measurement.           | execution slippage / broker transaction drag.
===================================================================================================================================
```

---

## 4. Contact & Submission Route

Please direct data delivery manifests, secure SFTP credentials, or institutional API keys to:
* **Project Repository:** `yieldchaser/Shipping`
* **Secure Archive Location:** `data/etf/raw_holdings/` and `data/custody_ledgers/`
