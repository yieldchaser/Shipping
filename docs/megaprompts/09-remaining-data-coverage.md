# PROMPT 09 — REMAINING DATA COVERAGE & SOURCE DISCOVERY

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-09-coverage.md`
> Depends on: Prompts 01–07 complete. Run **before** Prompt 08 verification.

Prompts 03–07 assigned homes to the modules that already existed. This prompt covers the
datasets that exist on disk but were never assigned to any tab, and then goes looking for
what we still do not have.

**Goal: zero orphaned datasets. Every file under `data/` is either rendered, or registered
with an explicit written reason why it is not.**

---

## PHASE 9.1 — Coverage census

Produce `docs/DATA_COVERAGE.md`, a table of **every** file under `data/`:

| file | MB | rows | span | status | rendered in | reason if not |
|---|---|---|---|---|---|---|

`status` ∈ `RENDERED · REFERENCE · DRILLDOWN_ONLY · QUARANTINED · NOT_RENDERED`.

`NOT_RENDERED` requires a written reason. Acceptable reasons: superseded by a better
series, raw source behind a derived file that is rendered, out of scope (PDF corpora),
awaiting acquisition. **"Didn't get to it" is not a reason** — those go in Phase 9.2.

Baseline for comparison: **436 files on disk, 84 wired (19.3%)** at project start.
Report the new percentage.

---

## PHASE 9.2 — Assign the orphans

These 15 datasets have confirmed homes. Build them.

### A. Equities & Owners → **BROKER DESK, new subtab**
Sits naturally beside *S&P & Assets*: who owns the ships, what the owners are worth.

| File | Rows | Content |
|---|---|---|
| `data/equities/maritime_universe_catalog.csv` | 175 | master cross-map: company → sector → SEC CIK → foreign ticker |
| `data/equities/sec_master_filing_catalog.csv` | **92,200** | SEC filing index 1995–2026, 92 issuers (10-K, 10-Q, 20-F, 40-F, 6-K, 8-K, Form 4, 13D/G, 424B) |
| `data/equities/sec_xbrl_financials.csv` | 10,462 | standardised balance sheet / income / cash flow |
| `data/equities/foreign_maritime_financials.csv` | **55,041** | 82 foreign-listed issuers (Oslo, Tokyo, Seoul, London, ASX, Singapore, India, Taiwan) |
| `data/equities/foreign_maritime_metrics.csv` | 82 | live EV, market cap, P/E, P/B, dividend yield, 52w range |
| `data/equities/sec_form4_insider_trades.parquet` | 741 | insider open-market buys/sells |
| `data/equities/sec_exhibit99_announcements.parquet` | 688 | fleet employment tables, earnings releases |

Build: company picker off the 175-company universe → financials, filing timeline, insider
activity. Cross-link to the Capital Link sector indices already in INDICES (do **not**
restructure INDICES; link to it).

**Do not compute valuations, fair values, or price targets.** Render reported figures only.
Ratios that are pure arithmetic on reported inputs (P/E from reported EPS) are fine and must
be marked `is_derived: true` with inputs named.

### B. Panama Canal → **TRACKING, chokepoints**
| File | Content |
|---|---|
| `data/clarksons/panama_gatun_lake_water_level_history.csv` | **22,531 daily readings, 1965-01-01 → 2026-09-08 (61.5 years)** |
| `data/clarksons/panama_gatun_water_level_projection.csv` | projected levels, freshwater surcharge %, max draft (Neopanamax 49.0ft / Panamax 39.5ft) |
| `data/clarksons/panama_canal_operational_statistics.json` | 8 datasets: monthly transits, cargo tons, PCUMS tonnage, lock-type split, **transits by market segment** (dry bulk / tanker / LNG / LPG / container / vehicle), flag-state traffic, 152-country cargo, 316 directional commodity flows |

Gatun lake level is the physical constraint that drives Panama draft restrictions, booking
auctions and freshwater surcharges — and therefore Cape-vs-Panama routing. Plot it as a
seasonal envelope (61 years gives an exceptional band) with the draft-restriction
thresholds marked as reference lines. Pair it with transit counts on the same view.

The market-segment transit split feeds directly into the chokepoint sector filters that
already exist in Tracking.

### C. Published port lineups → **TRACKING, port queues**
| File | Content |
|---|---|
| `data/clarksons/pilbara_port_hedland_lineup_20260909.json` | 46 movements / 35 vessels, berth allocations, agents, DWT |
| `data/clarksons/pilbara_current_shipping_schedule.pdf` | official PPA shipping program (link, do not parse) |
| `data/clarksons/pilbara_port_hedland_live_tracking.json` | 34 vessels AIS-matched |
| `data/clarksons/newcastle_harbour_vessel_movements.json` | **208 movements, 198 coal terminal ops**, berth-level (PWCS Kooragang K3–K10, Carrington D2–D6, NCIG N2–N3), 95.5% matched to the Signal registry |
| `data/clarksons/brazil_tubarao_vports_lineup.json` | 33 vessels, Vitória/Tubarão, ETA/ETB/ETS, tonnages |
| `data/clarksons/global_chokepoint_queues_pdm_tubarao_rbct.json` | live Capesize/VLOC queues at Ponta da Madeira, Tubarão, Richards Bay |

These are **officially published berth-level lineups** — higher authority than AIS
inference. Use them as the ground truth for those ports and as a cross-check on the Signal
Ocean queue. Where they disagree, show both and label each source. Do not silently prefer one.

Berth taxonomy is already documented in `docs/MARITIME_INTELLIGENCE_MASTER_DISCOVERY.md` §6
(BHP Nelson Point NPA–NPD, FMG Herb Elliott FIA–FID/AP1–AP5, Roy Hill SP1–SP2).

### D. Drewry container & multipurpose → **CARGO & TRADE FLOWS, new section**
| File | Content |
|---|---|
| `drewry_intra_asia_container_index.csv` | 24 weekly, 9 routes, US$/40ft |
| `drewry_port_throughput_indices.csv` | 25 monthly, global + Greater China / N.America / Europe, >340 ports |
| `drewry_breakbulk_transport_indices.csv` | **49 monthly, 2022-08 → 2026-08**, project cargo + general cargo |
| `drewry_airfreight_price_index.csv` | 24 monthly, US$/kg, 3 corridors |
| `drewry_cancelled_sailings_tracker.json` | alliance schedule reliability by carrier group |
| `data/indices/drewry_wci_historical.csv` | 149 weekly WCI prints (already rendered — link, don't duplicate) |

Container throughput is a cargo-flow measure, which is why it belongs here rather than in
INDICES. Airfreight is the modal-substitution signal and belongs beside it.

### E. CFTC fund positioning → **ETFS tab (addition only)**
`data/cftc_statements/parsed/bdry_monthly_cftc_ledger.csv` (100 rows) plus the 144-file
statement corpus. Monthly CFTC filings for BDRY: fund assets, net futures commitments,
margin equity.

**This is the one permitted change to an otherwise-untouched tab.** Add a positioning panel;
do not restructure anything else in ETFS. If adding it risks the existing layout, put it in
BROKER DESK → Equities & Owners instead and record the decision.

### F. Contract rulebooks → **REFERENCE layer**
`data/rulebooks/` + `scripts/contract_spec_registry.py` + `data/sgx_exhaustive_probe_report.json`
(contract multipliers 1,000 MT/lot, settlement tick sizes, cleared universes).

Not a chart. Wire it into **tooltips and drill-downs** on SIGNALS' FFA and iron ore curves,
so hovering a contract shows its real specification. This is exactly the "every little thing
has a proper tooltip" requirement — contract specs are the substance behind those tooltips.

### G. `data/derived/timesfm_probe_results.csv` → **NOT_RENDERED, deliberately**
1,760 rows of Google TimesFM zero-shot forecasts over Baltic indices, 2020–2024.

**Do not render this.** A model forecast displayed alongside observed data will be read as
data, which is the same failure mode as the fabricated Guinea series in a more respectable
coat. Register it `NOT_RENDERED` with reason: *"model output, not observation; rendering it
beside reported series would misrepresent it."* If it is ever surfaced, it needs its own
clearly-labelled experimental area — not this project.

---

## PHASE 9.3 — Discovery: what we still do not have

The product owner asked that gaps be actively discovered rather than quietly tolerated.
`docs/Newest Data/Maritime_Data_Discovery_Report.md` already documents four hard gaps with
no free source. Re-test each — the report is from 2026-08-25 and access changes.

| Gap | Last known status | Re-test |
|---|---|---|
| **Route-level TCE** (Baltic TD3C, TD6, C3, C5) | no free API; ICE/Baltic ~$15–30k/yr | Confirm still gated. **We now hold `fearnleys_benchmark_rates_continuous.csv` with C3 (`tsId 10001`), C5 (`tsId 10002`) and Newcastle/Qingdao coal (`tsId 10003`) — check how much of the perceived gap is already closed by data we own.** |
| **Shipyard orderbook / delivery schedules** | Clarksons + VesselsValue only; UNCTADstat annual | Re-test UNCTADstat bulk CSV. Check whether `signal_vessels_*.json` carries build year and yard — if so we can derive fleet age profile and a partial orderbook ourselves. |
| **Dry bulk / tanker port congestion** | all commercial; free options container-only | We now hold PortWatch + Signal live positions + published lineups. Assess whether we can compute congestion directly and stop calling it a gap. |
| **Guinea weekly bauxite** | Reuters/EITI only | Covered by Prompt 02 Job A — record final outcome here. |

Also test these, which the discovery report lists as available but which we do not appear to
ingest: **UNCTADstat** (fleet, shipbuilding, demolition — free CSV/Excel),
**VesselAPI** free tier (vessel specs/ownership), **EconDB / Linerlytica** (container, free).

Output: `docs/DATA_GAPS.md` — for each gap, what we tested, the result, and whether it is
closable with data already on disk. **Do not sign up for anything paid. Do not create
accounts. Report the cost and let the owner decide.**

---

## PHASE 9.4 — Verify and stop

- `docs/DATA_COVERAGE.md` accounts for **every** file under `data/`.
- Zero files with status `NOT_RENDERED` and a blank reason.
- New coverage percentage recorded against the 19.3% baseline.
- All 15 orphans from Phase 9.2 either rendered or explicitly deferred with a reason.

```
git commit -m "feat(coverage): assign 15 orphaned datasets, add coverage census and gap report

- Broker Desk: Equities & Owners subtab (175 companies, 92k SEC filings, 55k foreign financials)
- Tracking: Panama Canal 61.5yr Gatun levels + segment transits; published berth lineups
- Cargo: Drewry container / throughput / breakbulk / airfreight / cancelled sailings
- ETFs: CFTC fund positioning panel
- contract rulebooks wired into FFA tooltips and drill-downs
- timesfm probe deliberately not rendered (model output, not observation)
- docs/DATA_COVERAGE.md and docs/DATA_GAPS.md

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print the coverage percentage before and after, and the gap-report summary.
