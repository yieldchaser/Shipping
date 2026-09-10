# PROMPT 04 — BROKER DESK: ABSORB, DEEPEN, MAKE IT THE HOUSE STANDARD

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-04-broker-desk.md`
> Depends on: Prompts 01, 02, 03 complete.

---

## Context: this is already the best tab. Protect it.

BROKER DESK is the most rigorously built surface in the repository. Its conventions are
what every other tab is being rebuilt toward. **Before changing anything, study and
preserve these three things:**

1. **Series Museum's catalogue card** — the house standard for data provenance:
   ```
   ACTIVE | BULK | Panamax (75 000 dwt) | TC · usd · 681m | 1970-01→2026-09 | P88
   STALE  | S&P  | Kamsarmax            | DRY-5 · usd · 602m | 1976-01→2026-02 | P82
   ```
   Status, family, series name, unit, observation count, exact span, completeness
   percentile. Freshness rule already in use: `ACTIVE ≤45d · STALE 45–365d · ARCHIVED >365d`.
2. **Its honesty about gaps** — `"gaps = no published print (no interpolation)"`,
   `"2Y/3Y weekly only since 2021"`, `"each tile carries its own launch date because the
   source started these assessments at different dates; per-series depth is shown, never
   averaged away."` This is exactly right and must not be softened.
3. **Backtest Lab's framing** — `Trough - Accumulation Zone · 777 obs · 1M fwd hit 70%`,
   `n=1984 daily scores 2018-03-22 → 2026-08-10`, and explicitly *"forwards realized, not
   forecasts."*

Its tooltips average 159 characters and explain methodology. That is the target for the
whole app.

**Do not restructure the existing subtabs.** You are absorbing modules into them.

---

## PHASE 4.1 — Receive the 13 modules from SIGNALS

| Incoming module | Destination subtab | Instruction |
|---|---|---|
| FearnPulse 56-Year 1Y TC Benchmarks (1970–2026) | TC Rates | Broker Desk's TC Rates already offers `Baltic Weekly (2000+)` / `Fearnleys Monthly (1977+)` source toggle. **Merge into that toggle** — do not add a second chart. |
| Daily Spot vs Period Term Arbitrage (2000–2026) | TC Rates | new panel below the rate chart |
| Live Period TCE Rate Matrix (Weekly Alibra) | TC Rates | new panel; label source Alibra + poll date |
| Commercial Fixture Analytics & Top Charterers League (1974–2026) | Fixtures Tape | merge with existing tape |
| Tanker FFA Forward Term Structures (22-month) | Tanker Routes | new panel |
| Tonnage Basin Arbitrage (Atlantic vs Pacific TC) | Dry Routes | new panel |
| LPG Freight & Charter Rates (Ras Tanura → Chiba spot vs TC) | LPG Desk | merge into existing families |
| LNG Carrier Long-Term Period Rates (7Y/10Y TC) & NB Prices | LNG Desk | merge into existing families |
| Vessel Valuations & Capital Yield | S&P & Assets | |
| Shipping Market Cycle Quadrant | S&P & Assets | |
| 50-Year Secondhand vs NB Parity (1976–2026) | S&P & Assets | Broker Desk already has a parity ratio panel — **merge, keep the better one, record which won** |
| Secondhand S&P Deal Ledger | S&P & Assets | |
| Global Ship Demolition & Scrap Matrix ($/LDT) | S&P & Assets | Broker Desk already overlays demolition on the tenor ladder — merge |

For every merge: pick the better implementation, delete the loser, record the decision and
reasoning in the ledger. Do not ship two charts of the same series.

---

## PHASE 4.2 — Wire the unused broker data

These files are on disk and currently unrendered. Row counts verified.

| File | Rows | Span | Use |
|---|---|---|---|
| `data/derived/fearnleys_fixtures_full.csv` | **540,640** | 2019-03 → 2026-09 | Fixtures Tape: full searchable fixture ledger |
| `data/derived/fearnpulse_rates_full.csv` | **305,341** | **1977-01 → 2026-09** | TC Rates: 49-year benchmark history |
| `data/derived/fearnpulse_dry_routes_full.csv` | 20,769 | 1999-03 → 2026-09 | Dry Routes |
| `data/derived/fearnleys_broker_comments.csv` | 11,717 | — | Broker Voice: extend the archive |
| `data/derived/fearnleys_snp_transactions.csv` | 2,592 | multi-year | S&P & Assets: deal ledger |
| `data/clarksons/gibson_tanker_rates_continuous_daily.csv` | 1,495 days | 2020 → 2026 | **Tanker Routes: 9 routes × ~1,003 continuous days** (TD3C, TD20, TD25, TC1, TC5, MR USG/Brazil, Handy Clean, 2× dirty products) |
| `data/clarksons/fearnleys_benchmark_rates_continuous.csv` | 1,158 dates | 2018-05 → 2026-09 | 34 benchmark curves |
| `data/clarksons/braemar_live_rates.json` | 20 tenors | live | **Free, unauthenticated GraphQL FFA curve** — Cape/Panamax/Supramax/Handysize, Sep-2026 → Cal-2027. Add as a live forward strip. |
| `data/clarksons/gibson_all_reports_catalog.json` | 548 reports | 2016 → 2026 | Broker Voice: catalogue |
| `data/derived/vessel_valuations.csv` | 20,499 | 1970-12 → 2026-08 | S&P: 56 years of asset values |

**Fixtures Tape is the biggest single win here.** 540,640 fixtures is a genuine
institutional dataset — vessel, DWT, charterer, cargo, load/discharge port, laycan, rate.
Build it as a properly filterable, paginated tape with charterer league tables and
route-frequency analysis. Do **not** load 540k rows into the browser — Prompt 01 Tier 1
gives you a view manifest; raw rows come on drill-down only.

**Note a discrepancy to record:** the audit doc claims the fixtures file spans 1974–2026,
but the date column actually spans 2019-03-21 → 2026-09-09. Determine whether there is a
separate laycan/fixture-date column carrying the longer history, and record the truth in
the provenance manifest. Do not repeat the doc's claim without verifying it.

---

## PHASE 4.3 — Deepen the three specials

**Series Museum** — extend the catalogue to cover **every** series in
`data/provenance/manifest.json`, not just broker series. It becomes the app-wide data
catalogue, and the place a user goes to ask "where did this number come from?".
Add: a filter by status, a search box, and a click-through to the chart that uses each series.

**Backtest Lab** — currently scores the macro health regime against realised forwards.
Extend to let the user pick any series from the museum as the signal, keeping the same
honest framing (`n=`, `obs`, realised not forecast). Do not add optimisation or parameter
fitting — that manufactures overfit results, which is the same disease as fabricated data
in a different coat.

**Broker Voice** — currently Fearnleys weekly comments. Extend with the Gibson catalogue
(548 reports) and, if Prompt 02 registered them, the shipbroker markdown archives already
on disk. Full-text search across commentary. **PDF processing and knowledge-graph work is
explicitly out of scope for this entire prompt series** — link to documents, do not parse
them.

---

## PHASE 4.4 — Quality pass

- Type scale, 11px floor.
- Grid panes — no fixed-height twins, no trailing whitespace over 48px.
- Tooltips: this tab's existing 31 are the model. Extend the same quality to every new
  panel. Every number gets one.
- Every panel carries a Series Museum badge with source and as-of.
- Real SVG sparklines, not Unicode blocks.

---

## PHASE 4.5 — Verify and stop

Verification: no module from the Phase 4.1 table appears in both SIGNALS and BROKER DESK.
Grep each by name; expect exactly one definition each.

```
git commit -m "feat(broker-desk): absorb 13 modules from signals, wire 540k fixtures + gibson routes

- TC Rates: fearnpulse 1977-2026 merged into source toggle; spot-vs-period arb; alibra matrix
- Fixtures Tape: 540,640-row fixture ledger, charterer league, route frequency
- Tanker Routes: gibson 9-route continuous daily; tanker FFA term structure
- S&P & Assets: 56-year valuations, deal ledger, demolition matrix merged
- Series Museum extended to the full provenance manifest

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print: modules absorbed, merge decisions (winner + reason), new data files wired
with row counts.
