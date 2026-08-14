# ETF Price Translator Rebuild: Implementation Brief for Coding Agent

## Mission

Rebuild the ETF simulation system so it can support a real decision workflow for BDRY and BWET:

> Given an explicit view on the relevant freight forward contracts, estimate the conditional ETF return and price impact using the actual disclosed futures book, current collateral, fees, contract multipliers, and roll mechanics.

This is **not** a request to invent a directional forecasting model for freight. The product should be explicit that it translates a user's contract-level or curve-level thesis into a conditional ETF forecast. A separate alpha layer may later decide which freight contracts are likely to rise.

The current UI is implemented in `index.html`. Preserve its general visual language and existing ETF tab behavior, but prioritize financial correctness over retaining the current simulator architecture.

## Working Rules

1. Read `AGENTS.md`, `README.md`, `DATASETS.md`, `ETF_SIMULATION_SPECIFICATION.md`, and the ETF-related code/data before editing.
2. Inspect the actual data schemas before designing the model. Do not infer units from field names alone.
3. Do not silently substitute hard-coded values when source data is absent. Mark the output unavailable or degraded, show the reason, and use an explicitly labelled fallback only if the user can see and accept it.
4. Keep the current feature scoped to BDRY and BWET. Do not redesign unrelated dashboard modules.
5. Treat all current claims of validation as untrusted until reproduced by tests written during this task.
6. Keep a financial-model changelog in the final handoff: assumptions, data sources, and anything still estimated rather than observed.

## Verified Audit Findings: Current State Is Not Trade-Ready

The following were verified from the current implementation and must be fixed or deliberately retired.

### 1. Deconstruction uses a synthetic book rather than actual holdings

`predictETFPortfolioHoldings` uses fixed target lots:

- BDRY: Capesize 45, Panamax 52, Supramax 15.
- BWET: TD3C 85, TD20 12.

It distributes these values across generated prompt and next-quarter months. This does not reproduce the daily disclosed holdings in:

- `data/etf/bdry_holdings.csv`
- `data/etf/bwet_holdings.csv`
- `data/etf/bdry_holdings_history.csv`
- `data/etf/bwet_holdings_history.csv`

The rebuilt engine must use the latest valid disclosed positions for live scenarios, and the disclosure valid on each historical date for backtests.

### 2. The forward simulator does not use forward curves

The current forward path hard-codes ETF base prices, contract rates, start date, shocks, and deterministic innovations. It does not consume `DATA.sgx` despite the specification claiming it does.

The rebuilt model must not describe itself as curve-driven unless the projected return truly derives from loaded curve data and disclosed positions.

### 3. BWET has no live tanker-curve integration

The repo currently includes dry-bulk SGX CSVs, but no equivalent live TD3C/TD20 curve dataset. Do not pretend a curve exists.

Implement one of these two honest outcomes:

- Preferred: add a documented, reproducible data pipeline for TD3C and TD20 settlement/curve history, with contract identifiers, units, and as-of timestamps.
- Interim: support BWET only as a manual contract-shock translator based on latest disclosed contract marks, clearly marked `Manual scenario: tanker curve feed unavailable`.

### 4. Historical replay claims are unreliable

An independent reproduction of the current JavaScript replay over the included 39 holdings dates gave:

| ETF | Current replay R-squared | Mean spread | Maximum absolute spread |
| --- | ---: | ---: | ---: |
| BDRY | 87.65% | -263 bps | 763 bps |
| BWET | 59.57% | +8,353 bps | 12,025 bps |

The BWET result materially contradicts the current specification claim of 92.75% R-squared and +101 bps. The existing model must not retain those validation claims unless new reproducible tests generate them.

### 5. Current roll implementation is incomplete

The forward BDRY path does not roll Supramax into a deferred contract, uses calendar days rather than trading/business days, and applies hard-coded carry penalties. A valid roll module must handle every held contract consistently and distinguish:

- observed position changes from disclosures;
- index-mandated roll schedule, if independently documented and encoded;
- inferred roll behavior, clearly labelled as an assumption.

### 6. Existing tests are UI/runtime tests, not financial validation

`scratch/simulate_dom_runtime.js` passing 16,907 assertions proves controls and DOM arithmetic execute. It does not prove data usage, financial correctness, calibration, or forecasting quality. Retain useful UI tests, but add independent model tests described below.

## Product Definition

Build two related but clearly separated capabilities.

### A. Actual-Book Scenario Translator

Input:

- ETF: BDRY or BWET.
- As-of date, defaulting to the latest valid holdings disclosure.
- Contract-level percentage shocks, or vessel-class/curve-bucket shocks that expand transparently into contract shocks.
- Optional holding period in trading days.
- Share count and optional target ETF price.

Output:

- As-of disclosure date and market-data timestamp.
- Exact disclosed holdings used, including contract identifier, expiry, lots, mark, multiplier, notional, and portfolio weight.
- Separate futures exposure, collateral/cash, and non-futures components. Do not double-count a fund-NAV-like `Cash & Other` row if the source feed uses it as a balancing item.
- Conditional ETF return, price, and dollar PnL.
- Per-contract contribution to NAV return.
- Roll/carry contribution, separately shown and explained.
- Data-quality status: `live`, `stale`, `partial`, or `manual scenario`.
- An uncertainty/error band based on validated historical tracking error, not arbitrary chart noise.

The core one-period calculation should be economically consistent:

```text
futures_pnl_i = quantity_i * multiplier_i * (scenario_mark_i - current_mark_i)
nav_return = (sum(futures_pnl_i) + collateral_income - fees - verified_other_effects) / nav_base
etf_price_projected = etf_price_base * (1 + nav_return)
```

Use the correct market convention for each contract. Preserve native units internally where possible. Any conversion from Worldscale or USD/MT to a TCE equivalent must not be used as a substitute for the contract's actual PnL multiplier.

### B. Historical Accounting Replay and Validation

For every valid consecutive historical disclosure date:

1. Use only information available on the start-of-period/as-of date.
2. Map positions by stable identifier (`Ticker`, `CUSIP`, or a normalized contract key), not presentation names alone.
3. Compute the return from held contracts' observed mark changes using start-of-period exposure.
4. Separately account for contracts entering/leaving the book and for roll transactions. Do not call a newly introduced contract's previous price equal to its current price without explicitly categorizing it.
5. Align ETF market prices to actual trading days, correctly deal with non-trading disclosure dates, and document treatment of splits/reverse splits.
6. Report both price-level tracking and return tracking.

Required metrics:

- count of valid observations;
- missing-price and unmatched-contract counts;
- return correlation and R-squared;
- MAE and RMSE of daily returns;
- mean, median, and maximum absolute tracking spread in bps;
- cumulative simulated versus actual return;
- a date-by-date reconciliation export;
- results by ETF, separately.

Do not market a short 39-observation sample as proof of forecast skill. It can validate accounting logic, but not a predictive edge. Make this limitation visible in the UI and documentation.

## Data and Contract Mapping Requirements

### Holdings

Use actual holdings data from the ETF feeds. Normalize each row into a stable schema such as:

```text
as_of_date, etf, contract_id, route_class, expiry, quantity, mark, unit,
multiplier, disclosed_market_value, asset_type, is_cash, is_collateral
```

Create deterministic mapping rules and unit tests for at least:

- BDRY Capesize 5TC;
- BDRY Panamax 5TC;
- BDRY Supramax 58TC;
- BWET TD3C;
- BWET TD20;
- AGPXX/collateral rows;
- `Cash & Other` balancing rows.

The UI must surface unmapped rows and their value weight. Do not omit them silently.

### Futures marks and curves

- BDRY: map holdings tickers to the corresponding SGX curve/settlement series. Verify contract codes, expiry conventions, and dates.
- BWET: either implement a real source as noted above or restrict the model to manual shocks based on disclosed marks.
- Historical replay must use point-in-time marks. It must not use a current curve to value a historical portfolio.
- Record a market-data as-of timestamp and freshness status.

### ETF market prices

Use `data/etf/bdry_liquidity.csv` and `data/etf/bwet_liquidity.csv` only after checking whether the series are split-adjusted. The backtest must have an explicit corporate-action policy and tests that exercise it.

## Roll and Carry Requirements

Do not assume a universal `20 business day linear quarterly roll` unless it is independently established for each fund/index and documented with a source.

Implement roll in two layers:

1. Historical replay: observed holdings changes are authoritative. Attribute PnL across retained contracts, exits, and new contracts without inventing an intra-period schedule.
2. Forward scenario: if a documented target roll methodology exists, model it parametrically; otherwise use the latest disclosed book and let the user select an explicit roll assumption.

For every forward scenario, show:

- which contracts are being reduced/increased;
- quantities before and after;
- whether the roll schedule is observed, documented, or assumed;
- carry from the actual curve difference and contract quantities;
- a lot-conservation check for each rolling exposure bucket.

## Forward Scenario Rules

The forward engine must be a conditional scenario model, not a fake prediction.

- A manual shock scenario should be deterministic and reproducible.
- If stochastic paths are kept, generate many paths with a documented calibrated distribution, cross-contract correlation, and a seed shown to the user. Display percentiles, not one arbitrary path.
- Do not create a synthetic `Mkt Price` series for the future. Label all forward ETF values as `model-implied conditional price`.
- Do not hard-code August 2026 prices, dates, forward levels, carry, or volatility parameters.
- Trading-day calendars must exclude weekends and preferably exchange holidays when the source calendar is available.

## UI Requirements

Retain the useful interaction model where practical, but replace misleading labels.

Required UI elements:

- a prominent `Actual disclosed book` versus `Benchmark approximation` badge;
- as-of timestamps and stale-data warning;
- an expandable reconciliation table showing source rows and mapping status;
- a per-contract shock table and contribution table;
- a clearly labelled `Conditional scenario, not a price forecast` notice;
- model quality panel with the latest reproducible replay metrics;
- disabled/degraded states when required data is absent;
- downloadable reconciliation/backtest CSV.

Do not display a precise projected ETF dollar price without displaying the data quality and validation band beside it.

## Implementation Plan

Work in small, testable steps. Before implementation, write a concise design note in the PR/handoff that identifies files to change and validates data assumptions.

Suggested sequence:

1. Build a pure calculation module, separate from DOM rendering, for normalized holdings, contract mapping, PnL, attribution, and backtesting.
2. Add fixtures derived from the included BDRY/BWET data. Include edge cases for new contracts, missing closes, non-trading disclosure dates, and cash rows.
3. Implement historical replay first. Make its reconciliation table/export correct before adding any forward simulation.
4. Add actual-book scenario translation using the latest disclosure.
5. Add BDRY curve-driven forward scenarios only after contract mappings are verified.
6. Implement BWET curve integration, or intentionally limit it to manual scenarios with a visible warning.
7. Wire the UI to the validated calculation module.
8. Update the specification so every claim maps to tested behavior and current data.

## Non-Negotiable Acceptance Tests

### Financial correctness

- Every holdings row is either mapped, explicitly excluded with a reason, or flagged as unmapped. Total source value reconciles to modelled plus excluded value.
- Every scenario contribution sums to total NAV return within numerical tolerance.
- Contract multipliers and units are tested independently for each instrument type.
- Cash/collateral is neither omitted nor double-counted.
- Forward scenarios read current data rather than literals embedded in the simulation code.
- No synthetic future market-price line is presented as actual market data.
- All stated performance metrics are generated by a reproducible test or script from repository data.

### Backtest integrity

- Backtest produces BDRY and BWET results independently.
- A test fails if an unavailable prior contract price is silently replaced with the current price without a recorded roll/new-position classification.
- A test fails if historical dates use future data.
- A test fails if a non-trading-day price is silently substituted without the selected alignment policy being recorded.
- A test covers a split/reverse-split adjustment if present in source ETF price history.
- The current unsupported BWET `R-squared = 92.75%` claim is removed until independently reproduced.

### UI/runtime

- Existing DOM/runtime checks continue to pass, adjusted only where labels or legitimate behavior changed.
- New tests check displayed data quality, as-of dates, model status, and reconciliation values.

## Explicit Non-Goals

- Do not claim the system predicts freight direction or offers investment advice.
- Do not build a broad machine-learning forecaster in this task.
- Do not add fake precision through arbitrary volatility, carry, or arbitrage-noise constants.
- Do not use the BDRY 50/40/10 or BWET 90/10 target weights as a substitute for daily disclosed holdings.
- Do not expand to shipping equities, vessel ownership models, or unrelated dashboard data.

## Required Handoff Back to the Director/Verifier

When finished, provide:

1. Files changed and a one-sentence purpose for each.
2. Exact commands run and their results.
3. A table of reproducible historical replay metrics for BDRY and BWET.
4. A data-source and unit/multiplier mapping table.
5. Open assumptions, known limitations, and any missing external tanker data.
6. Screenshots or a concise UI walkthrough of the new model-status and reconciliation views.
7. A statement of whether the result is ready for: `accounting replay only`, `conditional scenario translation`, or `trade-decision support`.

Do not call the system trade-decision-ready unless it has a documented, reproducible, point-in-time backtest with acceptable error for both ETFs and clearly disclosed limits.
