# PROMPT 03 — SIGNALS TAB: STRIP TO DERIVATIVES & TECHNICALS

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-03-signals.md`
> Depends on: Prompts 01 and 02 complete.

---

## Context: why this tab is the way it is

SIGNALS was the original "boss tab" — for a long time it was the only analytical tab.
BROKER DESK, TRACKING and BUNKERS were later carved out of it. **But nothing was ever
removed from SIGNALS**, so the new tabs duplicated rather than replaced.

Today SIGNALS holds **38 charts** in four accordion groups. Only one of those groups
belongs here.

| Accordion group | Truth |
|---|---|
| Derivatives & Technicals | **genuinely SIGNALS — keep** |
| Physical Freight & Cargo | belongs to BROKER DESK |
| Vessel Capital Cycle | belongs to BROKER DESK |
| Upstream Commodity Flows & Port Logistics | splits between CARGO, TRACKING, BUNKERS |

**This tab's single question after the rebuild:**
*What is the market pricing, and how stretched is that pricing?*
If a module does not answer that, it leaves.

---

## PHASE 3.1 — Full module disposition

Work through this table exactly. Every row is a decision already made — do not
re-litigate, but **do** record in the ledger if a module turns out not to exist or to be
already broken.

### KEEP in SIGNALS (15 modules)
| Module | Notes |
|---|---|
| SGX FFA Forward Curve | Cape/Panamax/Supramax/Handysize selector + 1W/2W/1M/3M compare. Already good — preserve behaviour |
| Contract History Close / Contract History | drill-down from the curve |
| SGX Iron Ore Forward Term Structure (62% FEF vs 65% M65F & Lump) 40 tenors | real exchange data, verified |
| Iron Ore Contract Settlement History | drill-down |
| FFA Term Structure — BDRY & BWET Curve Shape | |
| Futures vs Spot Basis Arbitrage | |
| Cape / Panamax Ratio | |
| Bollinger Bands (20-day, 2σ) | |
| Historical Volatility (annualised, log-return σ × √252) | |
| Rate-of-Change Heatmap — All Products × Timeframes | |
| Seasonal Pattern — Avg Intra-Year ± 1σ | |
| BDI Daily Change — Vessel Class Contribution | |
| Lead-Lag Correlation (cross-correlation of log returns) | |
| ETF Premium/Discount Z-Score | |
| ETF Fund Flow Signals — Momentum & Divergence | |

### MOVE to BROKER DESK (Prompt 04 receives these)
| Module | Target subtab |
|---|---|
| FearnPulse 56-Year 1Y TC Benchmarks (1970–2026) | TC Rates |
| Daily Spot vs Period Term Arbitrage (2000–2026) | TC Rates |
| Live Period TCE Rate Matrix (Weekly Alibra) | TC Rates |
| Commercial Fixture Analytics & Top Charterers League (1974–2026) | Fixtures Tape |
| Tanker FFA Forward Term Structures (22-month) | Tanker Routes |
| Tonnage Basin Arbitrage (Atlantic vs Pacific TC) | Dry Routes |
| LPG Freight & Charter Rates (Ras Tanura → Chiba) | LPG Desk |
| LNG Carrier Long-Term Period Rates (7Y/10Y TC) & NB Prices | LNG Desk |
| Vessel Valuations & Capital Yield | S&P & Assets |
| Shipping Market Cycle Quadrant | S&P & Assets |
| 50-Year Secondhand Asset Valuations vs NB Parity (1976–2026) | S&P & Assets |
| Secondhand S&P Deal Ledger | S&P & Assets |
| Global Ship Demolition & Scrap Matrix ($/LDT) | S&P & Assets |

### MOVE to CARGO & TRADE FLOWS (Prompt 07 receives these)
| Module | Note |
|---|---|
| Brazilian Bulk Seaborne Exports (MDIC ComexStat) | **rebuild on Prompt 02 Job B output** |
| Pilbara Ports (Port Hedland & Dampier) & Miner Shipments | |
| US Gulf Coast (PADD 3) Seaborne Petroleum Exports (EIA weekly) | |
| USDA Bulk Grain Ocean Freight (US Gulf vs PNW to Japan) | |
| USDA Grain Vessel Loading & Port Queues (Gulf vs PNW) | |
| Landed Soybean Transportation Cost to China (US vs Brazil) | |
| Cargo Demand Drivers — World Bank Commodity Prices | |
| Leading Restocking Pressures (Port Stocks vs Spot Rates) | |
| Capital Link Container Index (CLCI) & Global Container Freight | |

### MOVE to TRACKING (Prompt 05)
| Module |
|---|
| Global Port Activity Monitor — Calls & Dry-Bulk Tonnage (IMF PortWatch) |

### MOVE to BUNKERS (Prompt 06)
| Module |
|---|
| EU ETS Maritime Carbon (€/t CO₂) & Scrubber Hi-5 Fuel Economics |

### DELETE OUTRIGHT
| Module | Reason |
|---|---|
| **Ton-Mile Absorption & Fleet Utilization Model Simulator** | Product owner decision. It is a slider that multiplies assumptions into an output nobody reported — you set the input, it shows you your input. Its Guinea input was fabricated (Prompt 02). Remove the module, its renderer, its controls and its data binding. |

---

## PHASE 3.2 — Execution method (important)

**Do not delete-and-rewrite. Move.**

For each moved module, in one atomic step per module:
1. Locate the markup block, its renderer function, its control handlers and its data binding.
2. Cut all four into the destination tab's panel.
3. Rebind to the destination tab's lazy-load path (Prompt 01 Tier 2).
4. Verify the module renders **identically** in its new home — same series, same span,
   same interactions.
5. Ledger entry with a grep proving exactly one definition now exists.

**Where BROKER DESK already has a better implementation** (it usually does — its TC Rates
and Tanker Routes are more rigorous than the Signals equivalents), **delete the Signals
version instead of moving it**, and record in the ledger which implementation won and why.
The product owner has explicitly approved deletion over keeping both.

After all moves, SIGNALS keeps **one** accordion group or, better, drops accordions
entirely — 13 modules do not need to be hidden behind collapsibles. Currently all 38 charts
render and are then hidden, which is why this tab is the heaviest in the app.

---

## PHASE 3.3 — Rebuild quality pass on what remains

- **Lazy-init every chart.** Today 38 canvases construct at page load inside collapsed
  accordions. After Prompt 01 Tier 2, only visible charts construct.
- **Rewrite every tooltip** to the Prompt 01 §1.5 standard. SIGNALS currently has 356 rich
  tooltips averaging 92 chars; many describe UI mechanics. Every plotted point, axis, legend
  entry and control gets a three-beat tooltip: what it is → source and span → why it matters.
- **Apply the type scale.** No text below 11px.
- **Provenance strip** on every chart: source name + as-of date, read from the view manifest
  header. Series Museum badge format.
- The known console error `[refreshVisibleCharts dashboard] TypeError: Cannot read
  properties of undefined (reading 'label')` originates near `index.html:37821` in the
  chart repaint path. **Fix it in this phase** — you will be touching that code.

### Two additions worth making while you are here
1. **FFA vs realised spot distribution.** We hold 183k rows of Cape FFA history and
   full spot history. Render, per contract month (M+1…M+6, Q1–Q4, Cal), the current FFA
   price as a marker over a violin/box of historical realised settlements. This converts
   "Q1 is $31,850" into "Q1 is priced at the 85th percentile of its history" — the single
   highest-value analytical addition available from data already on disk.
2. **Curve regime badge.** Label the FFA curve Contango / Backwardation / Flat with the
   slope value, the way the SGX iron ore file already does with its `fef_curve_regime`
   column. Reuse that column rather than recomputing.

---

## PHASE 3.4 — Verify and stop

```js
// exactly 13-15 canvases in signals, none constructed until the tab opens
document.getElementById('tab-signals').querySelectorAll('canvas').length
// no module appears in two tabs — run for each moved module name
```

Ledger must contain, for all 38 original modules, a row: `module → disposition → verified`.

```
git commit -m "refactor(signals): strip to derivatives & technicals, redistribute 24 modules

- keep 13 pricing/technical modules; drop accordions
- move 13 to broker desk, 9 to cargo, 1 to tracking, 1 to bunkers
- delete ton-mile simulator (fabricated inputs, circular output)
- add FFA-vs-realised-spot distribution; curve regime badge
- lazy chart init; tooltips rewritten to standard; type scale applied

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print the 38-row disposition table with verification status.
