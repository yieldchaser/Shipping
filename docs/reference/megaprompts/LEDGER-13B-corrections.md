# LEDGER — Prompt 13B: Prompt 13 Corrections (C1 through C10)

Governed by `docs/megaprompts/00-GUARDRAILS.md`.
Audit findings remediation log executed continuously across C1 to C10.

---

## C1 — Pilbara: 30 Fabricated Rows Removed & Dampier June 2026 Integrated

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_pilbara_ports.py` (deleted)
  - `scripts/scrapers/fetch_ppa_iron_ore.py` (modified: added June 2026 Dampier YTD PDF source and Playwright download fallback)
  - `data/commodities/australia_ppa_iron_ore.csv` (modified: pruned 30 fabricated literal rows, parsed authentic June 2026 Dampier PDF, recalculated mom/yoy)
  - `data/provenance/manifest.json` (modified: registered Hedland through 2024-05-01 with 15 rows; registered Dampier through 2026-06-01 with 251 rows; computed notes)
- **WHAT I DID:**
  1. Removed `scripts/acquire/fetch_pilbara_ports.py` containing the literal `MONTHLY_UPDATES` list.
  2. Purged the 30 fabricated rows from `data/commodities/australia_ppa_iron_ore.csv` (27 Port Hedland rows post 2024-05, 3 Port of Dampier rows post 2026-05).
  3. Downloaded the real Port of Dampier June 2026 YTD cargo statistics PDF (`klein-stats-july-2025-to-june-2026-ytd.pdf`, 132,507 bytes) via Playwright browser and parsed 2026-06-01 (13.561 Mt iron ore / 15.429 Mt total cargo).
  4. Updated `fetch_ppa_iron_ore.py` with the June 2026 YTD PDF and Playwright browser download fallback.
  5. Recalculated intra-port `mom_pct` and `yoy_pct` across all 266 authentic observations (15 Port Hedland, 251 Port of Dampier).
  6. Updated `manifest.json` with computed notes, exact row counts, and date spans (Hedland: 2020-10-01 to 2024-05-01; Dampier: 2002-07-01 to 2026-06-01).
- **VERIFY COMMAND:**
  ```bash
  git grep "MONTHLY_UPDATES" scripts/
  ```
- **EXPECTED RESULT:** 0 matches.
- **ACTUAL RESULT:** 0 matches (exit 1 from git grep).
- **DEVIATIONS:** Port Hedland honestly ends at 2024-05-01 per GUARDRAILS §0.1 absence policy.

---

## C2 & C10.3 — Guinea: 18 Fake Data-Hub Rows Purged, Authentic Quotes Verified, Unit Corrected

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_guinea_bauxite.py` (modified: purged 18 data-hub & 6 fake mirror rows, verified 11 Jan 2026 producer rows with verbatim quotes from GMI Article #82, renamed `import_volume_mt` to `import_volume_t`, added `granularity`)
  - `data/commodities/guinea_bauxite_exports.csv` (modified: 107 authentic rows: 11 company_monthly + 96 monthly_bilateral_mirror)
  - `data/provenance/manifest.json` (modified: registered 107 rows, unit `tonnes (import_volume_t)`)
- **WHAT I DID:**
  1. Purged 18 fabricated rows citing `https://www.guineamininginsights.com/data-hub` (which is an empty landing page with no tables).
  2. Purged 6 fake trade-press mirror rows constructed with broken slugs.
  3. Preserved 96 authentic UN Comtrade bilateral import mirror rows (2017-01 to 2024-12) and 11 authentic Jan 2026 company producer export rows from GMI Article #82 (`https://www.guineamininginsights.com/news-insights-82`).
  4. Verified verbatim quotes in French for all 11 producer rows against live page text via `check_source_citations.py`.
  5. Renamed column `import_volume_mt` to `import_volume_t` to accurately reflect tonnes rather than megatonnes (C10.3).
- **VERIFY COMMAND:**
  ```bash
  python -c "import csv; r = list(csv.DictReader(open('data/commodities/guinea_bauxite_exports.csv', 'r', encoding='utf-8'))); print(len(r), 'import_volume_t' in r[0])"
  ```
- **EXPECTED RESULT:** `107 True`
- **ACTUAL RESULT:** `107 True`
- **DEVIATIONS:** Gaps in 2025 are left absent per absence policy.

---

## C3 — Fleet Supply: Signal Ocean Status-7 Classification & UNCTAD Literals Purged

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `data/reference/signal_orderbook_status_map.json` (NEW: status mapping 7->active, 1/2->orderbook, 8->scrapped, 4/5/6->unresolved with confidence note)
  - `scripts/acquire/fetch_fleet_supply.py` (modified: classified exclusively by orderBookStatusID, purged UNCTAD literals)
  - `data/supply/fleet_orderbook_and_age_profile.csv` (regenerated: Capesize status 7 only: 1,702 hulls, 12.4y avg age)
  - `data/supply/merchant_fleet_summary.json` (regenerated: all summary numbers derived from data)
  - `data/provenance/manifest.json` (registered supply series)
- **WHAT I DID:**
  1. Built `signal_orderbook_status_map.json` documenting the inferred status mapping and yearBuilt distributions.
  2. Refactored `fetch_fleet_supply.py` to filter active commercial fleet strictly on `orderBookStatusID == 7` (excluding 543 scrapped Capesize hulls and 86 unresolved hulls).
  3. Purged UNCTAD literal numbers from docstring and script body.
  4. Recomputed Capesize active fleet to exactly 1,702 hulls at avg age 12.4 y, 208 orderbook hulls, and 543 scrapped hulls excluded.
- **VERIFY COMMAND:**
  ```bash
  grep -nE "116,?000|2\.50 billion" scripts/acquire/fetch_fleet_supply.py
  ```
- **EXPECTED RESULT:** 0 matches (exit 1).
- **ACTUAL RESULT:** 0 matches.
- **DEVIATIONS:** None.

---

## C4 — Comtrade Row Selection: Strict Total Selector & Minor Bulks Re-Harvest

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/comtrade_client.py` (NEW: shared `select_total` enforcing `motCode == 0 and customsCode == 'C00' and partner2Code == 0`)
  - `tests/test_comtrade_selection.py` (NEW: unit tests for multi-row responses and selection logic)
  - `scripts/acquire/fetch_minor_bulks.py` (modified: refactored to use `comtrade_client.select_total`)
  - `data/commodities/minor_bulks_monthly.csv` (regenerated: 321 authentic rows)
- **WHAT I DID:**
  1. Created `scripts/acquire/comtrade_client.py` with `select_total` that validates unique totals and raises on ambiguity.
  2. Added unit tests in `tests/test_comtrade_selection.py` proving Turkey scrap imports, India ferts, and Turkey cement/clinker select true totals (1.84M t, 447k t, 1.89M t).
  3. Re-harvested `minor_bulks_monthly.csv` with 321 verified monthly rows.
- **VERIFY COMMAND:**
  ```bash
  python -m pytest tests/test_comtrade_selection.py -q
  ```
- **EXPECTED RESULT:** `4 passed`
- **ACTUAL RESULT:** `4 passed in 0.28s`
- **DEVIATIONS:** None.

---

## C5 — Brazil ComexStat: Matching HS 6-Digit Splicing & Seam Test Validation

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_brazil_comexstat_full.py` (modified: updated backfill to use matching HS 6-digit codes; added `source` and `method` columns)
  - `data/commodities/brazil_comexstat_exports.csv` (regenerated: 557 rows with complete metadata)
  - `data/provenance/manifest.json` (updated with 557 rows)
- **WHAT I DID:**
  1. Updated Comtrade backfill query to query matching HS 6-digit codes: iron ore `260111`, soybeans `120110`+`120190`, raw sugar `170113`+`170114`, crude `270900`, corn `100590`.
  2. Added populated `source` and `method` columns to 100% of rows.
  3. Executed the seam test at 2024-01 comparing Comtrade against ComexStat: iron ore deviation was 0.000007% (26,908,947 vs 26,908,945 t); maximum commodity deviation was 0.054% (Corn), far below the 0.5% tolerance threshold.
- **VERIFY COMMAND:**
  ```bash
  python -c "import csv; r = list(csv.DictReader(open('data/commodities/brazil_comexstat_exports.csv', 'r', encoding='utf-8'))); print(len(r), all(bool(x.get('source')) and bool(x.get('method')) for x in r))"
  ```
- **EXPECTED RESULT:** `557 True`
- **ACTUAL RESULT:** `557 True`
- **DEVIATIONS:** None.

---

## C6 — Indonesia Coal: Invented Annotations Purged & Katadata Releases Verified

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_indonesia_coal.py` (modified: purged `India (~25-28%)` constant string, removed unverified May/July 2026 rows, added verbatim Indonesian quotes for Katadata Jan/Apr 2026 releases)
  - `data/commodities/indonesia_coal_exports_monthly.csv` (regenerated: 74 authentic rows)
  - `data/provenance/manifest.json` (registered 74 rows)
- **WHAT I DID:**
  1. Purged the constant `"India (~25-28%)"` string from all rows; destination columns left empty when no partner breakdown is reported.
  2. Purged unverified May and July 2026 rows citing generic BPS index.
  3. Preserved authentic January 2022 export ban row (10.92 Mt) with explicit annotation in `method`.
  4. Sourced authentic Jan 2026 and Apr 2026 rows from Katadata releases with verbatim quotes verified by `check_source_citations.py`.
- **VERIFY COMMAND:**
  ```bash
  python -c "import csv; r = list(csv.DictReader(open('data/commodities/indonesia_coal_exports_monthly.csv', 'r', encoding='utf-8'))); print(len(r), any('~' in x.get('top_destination_1','') for x in r))"
  ```
- **EXPECTED RESULT:** `74 False`
- **ACTUAL RESULT:** `74 False`
- **DEVIATIONS:** None.

---

## C7 — Fearnleys tsId Registry & Permanent Taxonomy Mutation Test

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `data/reference/fearnleys_tsid_registry.json` (NEW: complete 34-tsId registry with route code, fearnpulse name, taxonomy description, evidence, confidence)
  - `data/reference/baltic_route_taxonomy.json` (modified: added missing BDI and TD3/TD3C route entries)
  - `tests/test_fearnleys_labels_and_ranges.py` (modified: rewritten `test_taxonomy_coherence` validating against registry and taxonomy)
  - `tests/test_taxonomy_mutation.py` (NEW: asserts all 5 planted mutations fail)
- **WHAT I DID:**
  1. Created `fearnleys_tsid_registry.json` mapping all 34 tsIds with route codes and evidence.
  2. Added `BDI` and `TD3/TD3C` entries to `baltic_route_taxonomy.json`.
  3. Rewrote `test_taxonomy_coherence` to assert exact code match against the registry and existence in taxonomy.
  4. Created `test_taxonomy_mutation.py` planting the 5 required mutations (`C3->C5`, `P2A_82->P3A_82`, `P4_82->P6_82`, bogus `C99`, `S1C->S1B`) and asserting each fails.
- **VERIFY COMMAND:**
  ```bash
  python -m pytest tests/test_taxonomy_mutation.py tests/test_fearnleys_labels_and_ranges.py -q
  ```
- **EXPECTED RESULT:** `11 passed`
- **ACTUAL RESULT:** `11 passed in 1.48s`
- **DEVIATIONS:** None.

---

## C8 — Detector Hardening, Per-Line Allowlist & Source Citation Checker

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/verify/fabrication_allowlist.txt` (modified: converted 33 bare paths to 55 exact `path:line:rule <reason>` entries)
  - `scripts/bunkers/build_bunker_cache.py` (modified: fixed line 602 F5 datetime violation)
  - `scripts/verify/check_no_fabrication.py` (modified: rejects bare paths, enforces per-line allowlist, added F1b list-of-dicts, F1 constant annotations, F3b network call rule)
  - `scripts/verify/check_source_citations.py` (NEW: live HTTP 200, verbatim substring quote match, numeric value match)
  - `tests/test_detector_mutation.py` (NEW: tests detector against Pilbara list-of-dicts, Indonesia annotation, bare path, F3b)
- **WHAT I DID:**
  1. Replaced all bare-path allowlist entries with exact `path:line:rule` entries; parser strictly raises `ValueError` on any bare path.
  2. Added F1b AST detection for list/tuple literals holding >=3 observation dicts.
  3. Added F1 AST detection for constant estimated annotations stamped into row subscripts.
  4. Added F3b rule: network calls do not exempt files containing literal observation data from provenance checks.
  5. Built `check_source_citations.py` and verified all 13 non-API live citations across Guinea and Indonesia.
  6. Built `test_detector_mutation.py` verifying detector catches all 4 planted mutation patterns.
- **VERIFY COMMAND:**
  ```bash
  python scripts/verify/check_no_fabrication.py && python scripts/verify/check_source_citations.py && python -m pytest tests/test_detector_mutation.py -q
  ```
- **EXPECTED RESULT:** 0 violations, 13 live citations verified authentic, 4 passed.
- **ACTUAL RESULT:** 0 violations, 13 live citations verified authentic, 4 passed in 0.93s.
- **DEVIATIONS:** None.

---

## C9 — Boundary Report Generator

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/verify/generate_boundary_report.py` (NEW: generates verbatim boundary report dynamically)
- **WHAT I DID:**
  1. Built `scripts/verify/generate_boundary_report.py` to inspect data files, manifest, test runners, and gates.
  2. Script outputs the entire boundary report in markdown, computing every number dynamically without human typing.
- **VERIFY COMMAND:**
  ```bash
  python scripts/verify/generate_boundary_report.py
  ```
- **EXPECTED RESULT:** Exits 0 with complete dynamically computed boundary report.
- **ACTUAL RESULT:** Exits 0 in 11.2s.
- **DEVIATIONS:** None.

---

## C10 — Small Fixes: worldsteel Dynamic Benchmark, USDA Queues, Guinea Units

- **STATUS:** DONE
- **FILES TOUCHED:**
  - `scripts/acquire/fetch_world_steel_production.py` (modified: C10.1 dynamic June 2026 benchmark from parsed DataFrame, prompt reference deleted)
  - `data/commodities/world_crude_steel_metadata.json` (regenerated: C10.1 dynamic benchmark)
  - `scripts/acquire/fetch_usda_grain_queues.py` (modified: C10.2 added `loading`, `waiting_to_load`, `in_port_4yr_avg`, `loaded_4yr_avg`, `due_4yr_avg`)
  - `data/commodities/usda_grain_vessel_loading.csv` (regenerated: C10.2 3,304 rows)
  - `data/commodities/usda_grain_vessel_loading_queues.csv` (regenerated: C10.2 3,304 rows)
  - `scripts/acquire/fetch_guinea_bauxite.py` (modified: C10.3 renamed `import_volume_mt` to `import_volume_t`)
  - `data/commodities/guinea_bauxite_exports.csv` (regenerated: C10.3 unit is tonnes)
- **WHAT I DID:**
  1. Derived June 2026 benchmark dynamically from parsed worldsteel DataFrame (155.7 Mt world total, 83.7 Mt China); removed circular prompt reference.
  2. Retained critical congestion columns in USDA grain queues (`waiting_to_load`, `loading`, and 4-year averages). Vancouver left absent as `n/a` per source.
  3. Renamed Guinea volume unit to tonnes (`import_volume_t`).
- **VERIFY COMMAND:**
  ```bash
  python -c "import json, csv; m = json.load(open('data/commodities/world_crude_steel_metadata.json', 'r', encoding='utf-8')); q = list(csv.DictReader(open('data/commodities/usda_grain_vessel_loading_queues.csv', 'r', encoding='utf-8'))); print(m['june_2026_benchmark']['world_total_mt'], len(q), 'waiting_to_load' in q[0], 'loading' in q[0])"
  ```
- **EXPECTED RESULT:** `155.7 3304 True True`
- **ACTUAL RESULT:** `155.7 3304 True True`
- **DEVIATIONS:** None.


