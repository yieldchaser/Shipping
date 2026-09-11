# PROMPT 10 — DATA CURRENCY & TRUTH-IN-LABELLING

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-10-currency.md`
> Depends on: Prompts 01–09 complete (HEAD `3820c1a47`).

Phases 01–09 fixed *fabricated* data. This phase fixes *stale* data being labelled fresh —
a different lie with the same effect on a trader.

---

## The defect, proven

`data/provenance/manifest.json`, entry `commodities_usda_grain_vessel_loading_queues`:

```json
{
  "status": "LIVE",
  "date_span": ["01/01/1998", "12/31/2020"],
  "last_fetched_utc": "2026-09-07T12:24:53Z",
  "row_count": 3117
}
```

**The manifest knows the data ends in 2020 and calls it LIVE anyway.** `status` is
recording "we ran the script recently", not "the data is current". Those are different
facts and only the second one matters to a user.

The UI inherits the lie: the Cargo tab renders this series under a **LIVE** badge.

### Confirmed staleness across the commodity set (measured 2026-09-10)

| Series | Rows | Data ends | Age | Manifest says |
|---|---|---|---|---|
| `usda_fas_outstanding_export_sales` | 68,181 | 2026-08-27 | 14 d | LIVE ✅ correct |
| `usda_ytd_grain_inspections_top20` | 18,152 | 2026-08-27 | 14 d | LIVE ✅ |
| `us_eia_weekly_crude_exports` | 1,856 | 2026-08-28 | 13 d | LIVE ✅ |
| `usda_bulk_grain_ocean_rates` | 138 | 2026-08-20 | 21 d | LIVE ✅ |
| `usda_grain_vessel_loading` | 3,113 | 2026-08-13 | 28 d | LIVE ✅ |
| `commodities_monthly` (World Bank) | 800 | 2026-08-01 | 40 d | LIVE ⚠ |
| `brazil_comexstat_exports` | **124** | 2026-07-01 | **71 d** | LIVE ❌ |
| `newcastle_coal_exports` | 103 | 2026-07-01 | **71 d** | LIVE ❌ |
| `major_miners_quarterly_shipments` | 40 | 2026-06-30 | 72 d | LIVE ⚠ (quarterly) |
| `australia_ppa_iron_ore` | 265 | 2026-05-01 | **132 d** | LIVE ❌ |
| `australia_req_commodity_exports` | 725 | 2026-03-01 | 193 d | LIVE ⚠ (quarterly) |
| `usda_us_vs_brazil_landed_costs` | 650 | 12/31/2025 | **253 d** | LIVE ❌ |
| `usda_grain_vessel_loading_queues` | 3,117 | 12/31/2020 | **2,079 d** | LIVE ❌❌ |
| `guinea_bauxite_exports` | **24** | 2024-12-01 | **648 d** | (separate entry says UNAVAILABLE) |

---

## PHASE 10.1 — Split freshness from fetch-time

Add two required fields to every manifest entry:

```json
"data_through": "2026-08-27",        // max date INSIDE the file, ISO, computed not typed
"staleness_sla_days": 21,            // expected max age for this series' publication cadence
"staleness_state": "FRESH"           // FRESH | AGEING | STALE | DORMANT — computed
```

Rules:
- `data_through` is **computed** by parsing the file. Never hand-written.
- `staleness_state` derives from `data_through` vs `staleness_sla_days`:
  `FRESH` ≤ SLA · `AGEING` ≤ 2×SLA · `STALE` ≤ 6×SLA · `DORMANT` > 6×SLA.
- SLA is set from real publication cadence, not hope: weekly series 14 d, monthly 45 d,
  quarterly 120 d, daily 5 d.
- **`status: "LIVE"` now requires `staleness_state` of FRESH or AGEING.** A series that is
  STALE or DORMANT cannot be LIVE, regardless of when the script last ran.

## PHASE 10.2 — Make the UI tell the truth

- Every series badge shows **`data_through`**, not fetch time. "USDA · through 2026-08-27"
  is useful; "LIVE" is not.
- `STALE` renders an amber badge, `DORMANT` a red one, both with the age in days.
- **Remove every UI claim that overstates span.** The Cargo tab currently titles a module
  *"USDA Grain Vessel Loading & Port Queues (31-Year History 1995–2026)"* over a file that
  stops in 2020. Titles must be generated from `date_span`, never typed by hand.
- Any module whose only series is DORMANT renders an empty state, not a chart of old data.

## PHASE 10.25 — Bunker prices disagree with their own registered source

`data/bunkers/bunker_prices_daily.csv` is registered in the manifest as:

```json
"source_name": "Ship & Bunker",
"source_url":  "https://shipandbunker.com",
"fetch_script":"scripts/expansion_bunker_prices.py",
"last_fetched_utc": "2026-09-09T06:33:55Z"
```

**But our values do not match Ship & Bunker's published assessment for the same date.**
Cross-checked 2026-09-10 against a broker rate sheet that republishes Ship & Bunker, and
against BunkerIndex's own published table:

| Port · VLSFO, 2026-09-09 | Ours | Ship & Bunker (registered source) | BunkerIndex |
|---|---|---|---|
| Rotterdam | **695.0** | **701.00** | **695.00** |
| Singapore | 850.0 | 856.00 | 856.50 |
| Houston | 728.0 | 737.50 | — |
| Fujairah | 867.5 | 887.00 | 884.00 |

Rotterdam matches **BunkerIndex exactly** and misses Ship & Bunker by 6.00. Rotterdam
IFO380 is ours 585.0 vs BunkerIndex 588.00; MGO ours 1370.0 vs 1373.50. Close but not
identical across grades, so it is not a clean single-source match either.

Two candidate explanations, and **you must determine which before changing anything**:
1. **False provenance (GUARDRAILS F3)** — the manifest says Ship & Bunker but the scraper
   actually reads BunkerIndex, or a blend.
2. **Publication-lag misdating** — `last_fetched_utc` is **06:33 UTC**, likely before Ship &
   Bunker's same-day assessment publishes, so the previous day's print gets stamped with
   today's date.

**Work:**
- Read `scripts/expansion_bunker_prices.py` and establish which host it actually requests.
- Fetch that host live and compare to what we stored for the same date.
- Fix whichever is wrong: correct the provenance, or correct the date stamping, or both.
- If we genuinely use two assessors, **split them into two series with two badges** and show
  the spread. Never blend assessors into one line.
- Move the scheduled fetch to after the source's publication time, and record that time.

> ⚠ **Correction to how this was first reported.** It was initially described to the product
> owner as a confirmed "off-by-one date-stamp bug, four ports matching exactly". That
> conclusion was reached by adding each port's *published daily change* to our stored value
> and recovering the Ship & Bunker figure — which is circular, because two assessors that
> track each other will always reconcile that way. The verified fact is narrower and is
> stated above: **our numbers disagree with the source the manifest names.** The mechanism
> is not yet established. Establish it before you fix it.

---

## PHASE 10.3 — Fix the broken date formats

Prompt 01 Phase 1.3 required repo-wide ISO normalisation on read. Two files still carry
US `MM/DD/YYYY` and are consequently mis-sorted and mis-parsed:
- `data/commodities/usda_grain_vessel_loading_queues.csv`
- `data/commodities/usda_us_vs_brazil_landed_costs.csv`

Normalise on read, report rows repaired, and add a unit test that fails if any date column
anywhere in `data/` parses as non-ISO.

## PHASE 10.4 — Finish the fabrication purge

`python scripts/verify/check_no_fabrication.py` currently reports **56 violations**.
Prompt 02 Phase 2.3 required exit 0. Two things are true at once: some are real, most are
false positives. Do both jobs.

### Real violations — fix
1. **`scripts/analysis/cascade_extractor_v2.py`** — the same disease as the Guinea series.
   Line ~139 comment: *"Hard anchor points visually identified from report text & chart
   peaks"*, followed by hardcoded dicts for Alang / Chattogram / Gadani, then a synthesised
   monthly shape:
   ```python
   factor = 1.15 if m in [4, 5, 11] else (0.80 if m in [7, 8] else 1.0)
   val = base_monthly * (1.3 if m in [5, 9] else 0.8)
   ```
   That invents a seasonal curve on top of numbers read off a chart.
   **Mitigating fact: its output goes to `data/derived/cascade_dry_run/` and is NOT
   rendered** — `index.html` fetches `data/derived/scrappage_prices.csv` instead. So this
   is contained, but it must be quarantined like `generate_trade_envelopes.py` was, and
   `scrappage_prices.csv` must be traced to its true source and registered.
2. **`scripts/bunkers/build_bunker_cache.py:602`** — `'as_of': '2026-09-05'` hardcoded
   timestamp still present (GUARDRAILS F5).
3. **Orphan** — `data/views/signal/live_fleet_positions.json` is fetched by `index.html`
   but unregistered in the manifest.

### False positives — tighten the detector
The F2 rule flags ordinary conditional expressions. These are **not** violations and the
detector must stop reporting them:
```python
radius = 0.08 if status == "Waiting at anchor" else 0.02   # geometry constant
pages  = int(sys.argv[1]) if len(sys.argv) > 1 else 3      # CLI default
max_m  = now.month if y == now.year else 12                # calendar logic
years_lookback = 25 if backfill else 2                     # mode switch
```
Narrow F2 to its actual target: a fallback **to a literal that substitutes for fetched
observation data**. Test: does the literal end up in a column that gets plotted? If not,
it is control flow, not fabrication.

**After tightening, the detector must exit 0 — and the ledger must list every rule change
with justification**, so nobody can silence a real finding by loosening a rule.

---

## PHASE 10.5 — Verify and stop

- Every manifest entry has computed `data_through`, `staleness_sla_days`, `staleness_state`.
- No entry is `LIVE` while `STALE`/`DORMANT`.
- No hand-typed span appears in any UI title.
- `check_no_fabrication.py` exits 0, with every rule change justified in the ledger.
- All date columns parse as ISO.

```
git commit -m "fix(provenance): separate data currency from fetch time; finish fabrication purge

- manifest: computed data_through, staleness_sla_days, staleness_state
- LIVE now requires FRESH/AGEING; 6 series reclassified STALE/DORMANT
- UI badges show data_through; titles generated from date_span not hand-typed
- quarantine cascade_extractor_v2 (chart-peak anchors + synthesised seasonal shape)
- remove hardcoded as_of in build_bunker_cache
- narrow F2 detector to observation-data fallbacks only

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print the full staleness table: series → data_through → age → old status → new status.
