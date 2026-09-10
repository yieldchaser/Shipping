# PROMPT 02 — DATA INTEGRITY PURGE & RE-ACQUISITION

> Read `docs/megaprompts/00-GUARDRAILS.md` first. It governs this task.
> Ledger: `docs/megaprompts/LEDGER-02-data-purge.md`
> Depends on: Prompt 01 complete (fabrication detector + provenance manifest must exist).

This phase removes fabricated data from the repository and replaces it with real sources.
Nothing in Phases 03–07 may render a series that has not passed through this phase.

---

## PHASE 2.1 — Quarantine the known fabrications

### 2.1.a `scripts/analysis/generate_trade_envelopes.py`

This file is the primary offender. Evidence:

- Line 141, `GUINEA_BAUXITE_HISTORICAL_KT` — a hardcoded dict of 10 years of monthly
  values. The comments name their true source:
  ```
  # 2021: Military coup year, supply maintained (Image 2 green line)
  # 2022: Dynamic Capesize adoption (Image 2 dark teal line)
  # 2023: Crossing 100 Mt annual barrier (Image 2 light cyan line)
  # 2025: Record 145 Mt annual exports (Image 2 blue line)
  # 2026: All-time record Q1-Q2 surge (Image 2 navy/black line)
  ```
  These values were read off the coloured lines of a chart image. There is **no API call
  for Guinea anywhere in the file.** The module docstring nevertheless claims
  "UN Comtrade HS 260600 + Port of Kamsar AIS water flows".

- `calibrate_guinea_2026_flows()` is validation theatre (GUARDRAILS F4). It reads Kamsar
  port calls, computes a monthly sum, **logs it, discards it**, and returns the hardcoded
  dict unchanged. The loop body contains no assignment.

- Line 53, `BRAZIL_COMEXSTAT_HISTORICAL_KT` — a second hardcoded dict. Brazil *does* call
  `https://api-comexstat.mdic.gov.br/general`, but on any exception it returns `{}` and
  the caller does `live_data.get((y,m)) or BRAZIL_COMEXSTAT_HISTORICAL_KT.get(y,{}).get(m)`
  — a silent fallback to the literal, logged as "using verified authoritative ComexStat
  ledger". It is a hardcoded dict, not a ledger.

**Actions:**
1. Move the file to `scripts/_quarantine/generate_trade_envelopes.py.QUARANTINED` with a
   header comment explaining why. Do not delete — we need the git history and the numbers
   for later comparison against real data.
2. Mark these three outputs `status: "QUARANTINED_FABRICATED"` in the provenance manifest:
   - `data/commodities/guinea_bauxite_envelope.csv`
   - `data/commodities/brazil_ore_envelope.csv`
   - `data/commodities/upstream_freight_drivers.csv`
3. Move the CSVs themselves to `data/_quarantine/`.
4. **Grep `index.html` for every reference to these three files and disable those modules**
   with an explicit empty state: *"Series withdrawn pending re-sourcing"*. Do not leave a
   chart rendering stale fabricated values. List every disabled module in the ledger.

### 2.1.b `scripts/scrapers/generate_ton_mile_matrix.py`

Its docstring claims Guinea input from "UN Comtrade monthly bilateral trade declarations"
— that is the hardcoded dict above. The model is built on fabricated inputs.

The product owner has decided this module is **cut** regardless of data quality: it is a
slider that multiplies assumptions to produce an output nobody reported, and the answer
moves because you moved the input. Quarantine the script. The
**Ton-Mile Absorption & Fleet Utilization Model Simulator** module is removed from the UI
in Prompt 03.

### 2.1.c `scripts/geospatial/build_chokepoint_cache.py`

Two violations, file otherwise sound (its `CHOKEPOINTS_CONFIG` literals are port
coordinates and categories — legitimate static reference data, keep them):
- Line 442: `'generated_at': '2026-09-07'` → `datetime.now(timezone.utc).isoformat()`
- Lines 446–447: `red_sea_bab['baseline_change_pct'] if red_sea_bab else -73.1` and the
  same for `suez` → if the computation is unavailable, emit `null` and have the UI render
  "—", never a literal. **Note: −73.1% is currently displayed in the Tracking KPI strip.**
  Determine and record in the ledger whether the live UI value is computed or the fallback.

### 2.1.d `bunker_pipeline/extractors/bunkerindex_forward.py`

The scraper itself is honest — it genuinely fetches
`bunkerindex.com/center_table_forward_prices_month_{1..12}_home.php` and discards
paywalled rows. Two problems:
- Module docstring line 3 advertises a "Synthetic Projection Engine" that "projects forward
  curves by mapping regional spot basis differentials and benchmark forward slopes". That
  code is no longer present, but the stored data carries its fingerprint: all six hubs share
  an identical curve slope to five decimal places (m2/m1 = 0.95594–0.95595, m12/m11 =
  0.99180–0.99182). Six independent fuel markets cannot have identical curve shapes.
- `fetch_all_forward_curves()` docstring asserts "100% genuine raw published data", which
  is not supportable as written.

**Action:** rewrite both docstrings to describe exactly what the code does. Mark
`data/bunkers/bunker_forward_curves_12m.csv` as `status: "ESTIMATED"` with
`derivation: "single modelled slope applied to each hub's spot price; provenance
unresolved between BunkerIndex methodology and a removed local projection engine"` until
Phase 2.2 resolves it.

---

## PHASE 2.2 — Re-acquisition

Build one script per source under `scripts/acquire/`. Each must: fetch, validate, write
CSV, register provenance, and **fail loudly** on error. No fallbacks to literals, ever.

### JOB A — Guinea bauxite exports, monthly, 2017 → present ★ highest priority
We currently have **nothing** real. Try in order and record every attempt with the exact
URL, status code and response shape in the ledger:

1. **UN Comtrade** — `https://comtradeapi.un.org/data/v1/get/C/M/HS`, reporter Guinea
   (`324`), HS `260600`, flow `X`, monthly.
   **Critical check: does Guinea actually report monthly?** Many West African states report
   annually or not at all. Verify before assuming.
2. **China mirror (most likely to succeed)** — same API, reporter China (`156`),
   flow `M` (imports), partner Guinea (`324`), HS `260600`. China reports reliably and
   monthly and takes roughly 70% of Guinean bauxite. A partner-side mirror is a legitimate,
   citable method — register it as `status: "LIVE"` with
   `notes: "China-reported imports from Guinea; mirror statistic, not Guinea-reported exports"`.
3. **China GACC** — monthly bauxite imports by origin. `chinadata.live/api/v2/` or GACC direct.
4. **Guinea EITI** — `https://opendataitie-guinee.org/` production/export datasets (CSV/XLSX).

Deliverable: `data/commodities/guinea_bauxite_exports.csv` with a per-row `source` column.
If all four fail, write **no file** and register `status: "UNAVAILABLE"`. Do not
reconstruct from the quarantined dict.

### JOB B — Brazil iron ore exports, verify and backfill
1. Test `POST https://api-comexstat.mdic.gov.br/general` with the payload already in the
   quarantined script. Report status code and row count.
2. **Note the hostname discrepancy:** the discovery doc lists `api.comexstat.mdic.gov.br`
   (dot), the script uses `api-comexstat.mdic.gov.br` (hyphen). Test both.
3. Pull the **full monthly history 2017-01 → present in one go** and persist it, so the
   frontend never depends on a live call.
4. Same call, different NCM, for grains: soybeans `1201`, corn `1005`.

Deliverable: `data/commodities/brazil_exports_monthly.csv` (commodity, date, volume_kt,
usd_fob, source).

### JOB C — Bunker forward curve truth
1. Pull all 12 months from BunkerIndex. **Do the six unmasked hubs (Busan, Fujairah, Hong
   Kong, Kaohsiung, Rotterdam, Singapore) genuinely share an identical slope?** If yes,
   it is BunkerIndex's model and we label it `ESTIMATED` and cite them. If no, our stored
   file is a stale artefact of the removed projection engine and must be replaced.
2. Find and record BunkerIndex's **methodology statement**. Are these derived from swaps,
   or from a term-structure model?
3. Record actual publication frequency. Our stored snapshot is a single day, 2026-09-05.
4. **★ Highest value item in this job:** find a genuinely exchange-traded bunker forward.
   Check **SGX Marine Fuel 0.5% FOB Singapore futures** — likely ticker `MFB` or similar —
   and Platts/Argus free indications. We already successfully ingest SGX `FEF`, `M65F` and
   `LPF` with settle, open interest and volume; if the marine fuel contract can be pulled
   the same way, we get a real cleared forward curve and the modelled one is deleted
   outright rather than relabelled.

### JOB D — Grain flows
1. **USDA FAS Export Sales API** — `https://apps.fas.usda.gov/OpenData/` (free API key).
   Weekly commitments by commodity × destination.
2. Brazil soy/corn — covered by Job B.
3. **Argentina** — Rosario Board of Trade (BCR) or INDEC monthly grain exports. This is a
   complete blank for us today and it is a major Panamax demand driver.

### JOB E — Wire the Signal Ocean layer
The product owner has approved **full publication** of this data. No permission questions
remain. These files exist on disk and are currently unused:

| File | Content |
|---|---|
| `signal_vessels_dry_bulk.json` (13.5 MB) | 33,559 bulkers |
| `signal_vessels_tankers.json` (8.4 MB) | 19,862 tankers |
| `signal_vessels_lpg.json` / `_lng.json` | 2,464 LPG + 1,371 LNG |
| `signal_distance_ports.json` (2.7 MB) | 12,060 routing ports |
| `signal_map_ports_master.json` | 2,752 terminals with GIS polygons |
| `signal_map_ports_{dry_bulk,tankers,lng,lpg}.json` | 118 / 113 / 73 / 150 by asset class |
| `signal_ports_by_asset_class.csv` | pre-flattened asset-class port table |
| `signal_live_fleet_positions_*.json` (4 files) | 7,937 live positions |
| `signal_charterers` / `_commercial_operators` / `_operational_statuses` / `_cargo_types_*` | reference taxonomies |

This phase only **registers them in the provenance manifest and builds their view
manifests**. Prompt 05 renders them.

Also documented and available for refresh (see
`docs/MARITIME_INTELLIGENCE_MASTER_DISCOVERY.md` §1):
`POST /api/distanceTool/vessels/positions` with `{"imoList":[...]}` — 100 IMOs per call,
sub-500 ms, no search-quota deduction. Build a refresh script but **rate-limit politely**
and do not run it in a tight loop.

---

## PHASE 2.3 — Verify and stop

Run `python scripts/verify/check_no_fabrication.py`. **It must now exit 0.**
If it does not, the remaining violations are listed in the ledger with a reason — do not
suppress them by editing the allowlist unless the item is genuinely static reference data.

Record in the ledger, per source A–E: attempted URLs, HTTP status, rows retrieved, span,
final `status`. **A failed acquisition honestly recorded is a success for this phase.**

```
git commit -m "fix(data): quarantine fabricated trade-envelope series, re-source from primary APIs

- quarantine generate_trade_envelopes.py: Guinea series was transcribed from a chart image
- quarantine generate_ton_mile_matrix.py: model built on those inputs
- remove hardcoded timestamp and -73.1 fallbacks from build_chokepoint_cache.py
- correct false provenance docstrings in bunkerindex_forward.py
- add scripts/acquire/: guinea, brazil, bunker-forward, grain, signal-ocean registration

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print a table of every series touched: old status → new status → row count → span.
