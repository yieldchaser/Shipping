# Frontend data-integrity scanner - verdict: the only CRITICAL was the scanner's OWN bug

**Date:** 2026-10-01  ·  **Branch:** current (`auto/extract-fixes-2026-10-01-ism-tier-drift`) · `main` NOT touched
**File:** `scripts/check_frontend_data_integrity.py`
**Reproduce:** `python3 scripts/check_frontend_data_integrity.py` (now exits 0); controls `scratch/ctl_scanner.py`, `scratch/date_blindspot.py`

## What was found

Running the repo's own frontend integrity scanner (it "exits non-zero if any CRITICAL finding
exists. Designed for CI") off `index.html`'s `safeFetch` targets produced:

```
 ! data/views/signals/cape_ffa_distribution.json: DUPLICATE COLUMNS ['max:7634', 'min:-243'] — frontend sees shadowed empties
 ! data/views/signals/cape_ffa_distribution.json: ZERO DATA ROWS (header only)
```

**Both are false.** The scanner regexes EVERY `safeFetch('data/... | knowledge/...')` target - 39 of
them - and then hands each one to `pd.read_csv`. One target is not a CSV:
`data/views/signals/cape_ffa_distribution.json` (fetched at `index.html:18683`, a real displayed
view). Measured:

```
pd.read_csv('data/views/signals/cape_ffa_distribution.json') -> shape (0, 158)
cols: ['{"as_of":"2026-09-10"', 'by_month:{"Apr":{"count":18', 'max:3850', ...]
```

The JSON is parsed as a one-line CSV: 0 rows, 158 pseudo-columns, which is exactly a
"duplicate columns / zero rows" hit. **The file is fine** - `json.load` gives 6 top-level keys
(`as_of`, `by_month`, `by_quarter`, `cal`, `generated_at`, `source`) and all 12 months carry
`count=18`. The scanner was reporting its own instrument error as a data defect.

This matters because the tool exits 1 for CI: a red gate that no data can clear trains everyone to
ignore it, and it hid the fact that **every real CSV target passes**.

## The fix (two instrument bugs, one file)

1. **Dispatch by suffix.** `scan_csv` for `.csv`, new `scan_json` for `.json`
   (exists / non-empty / `json.load` parses / payload non-empty). The JSON is now validated as
   JSON rather than mis-parsed as CSV.
2. **Date column, case-insensitively.** `scan_csv` required a column named exactly `date`, so
   **3 of its own targets** were reported "no date column" and then *skipped entirely* - they spell
   it `Date`. Measured on those 3: 0 unparseable dates, monotonic, spans
   2005-09-30..2025-12-31 / 1996-01-01..2026-08-01 / 2026-03-13..2026-09-30. No data defect, but a
   blind spot that had been silently shrinking the check's own coverage.

## Measured before / after

| measure | before | after |
|---|---|---|
| targets scanned | 39 | 39 |
| targets actually VALIDATED | 27 | **31** (30 csv + 1 json) |
| JSON targets validated as JSON | 0 (mis-read as CSV) | **1** |
| "no date column" warnings | 11 | **8** (the 8 genuinely have none) |
| CRITICAL findings | **2 (both false)** | **0** |
| exit code | **1** | **0** |

Remaining 8 warnings are true statements about files with no date column at all
(`chokepoint_transit_metrics` keys on `chokepoint`; `tanker_forward_curves*` on `snapshot_date`;
`usda_bunker_fuel_daily` on `Day/Month/Year`; the two `*_Daily.csv` on `Rate Date`; the two
`*_holdings.csv` are snapshots). Left as warnings - each would need a per-file date rule, and
`(may be intentional)` is the honest verdict.

## Controls (scratch/ctl_scanner.py, 7 fixture targets in a temp root)

The fix must not mask real defects. Every control still fires:

| fixture | expected | observed |
|---|---|---|
| `dup.csv` (two `value` columns) | CRITICAL duplicate columns | **CRITICAL duplicate columns** |
| `empty.csv` (header only) | CRITICAL zero rows | **CRITICAL zero rows** |
| `missing.csv` (not on disk) | CRITICAL file missing | **CRITICAL file missing** |
| `bad.json` (`{not json,,,`) | CRITICAL unparseable | **CRITICAL unparseable JSON** |
| `emptyobj.json` (`{}`) | CRITICAL empty payload | **CRITICAL empty JSON payload** |
| `good.csv` | OK | **OK** |
| `good.json` | OK | **OK** |
| (any CRITICAL present) | exit 1 | **exit 1** |

Real-repo run after the fix: **39 targets (38 csv / 1 json), 31 OK, 0 CRITICAL, exit 0.**

## Also measured this run (no action taken, recorded so nobody re-derives it)

* `data/provenance/manifest.json` is fresh for this series (`indices_drewry_wci_historical`
  `row_count` **135**, span 2021-05-20..2026-09-24, matching the file exactly).
  `scripts/verify/audit_manifest_staleness.py`: **111 of 112 entries agree**; the single stale one is
  `bunkers_bunker_prices_daily` (registry 1218 rows / end 2026-09-30 vs disk **1260 / 2026-10-01**).
  Regenerable with `scripts/verify/build_provenance_manifest.py` - NOT run here (it rewrites the
  whole 112-entry registry) and NOT hand-edited.
* `data/derived/held_data_catalog.json` (mtime 2026-09-30) is still stale for the same series
  (`rows: 145`, `end_sample: 2026-09-20` vs the file's **135 / 2026-09-24**). **No builder for this
  file exists anywhere in the repo** (grep over `scripts/`, `data/derived/`; the only mention is
  prose in `scripts/extract/update_extraction_register.py`), and nothing reads it - `index.html`
  does not reference it. Left alone: hand-editing a derived artefact is against the rule, and there
  is nothing to regenerate it with.
* The state file's adjacent note - *"`run_ism.py main()` defaults its doc list to
  `ROOT.rglob('*.pdf')` (every PDF in the repo)"* - **does not hold.** `run_ism.py:42` is
  `ROOT = Path('corpus/01-brokers/ism')`, so the default is scoped to the ism corpus folder, and
  `run_ism.py:662` is the only `ROOT.rglob` in the whole publishers directory. No code change made.
* `data/views/signals/cape_ffa_distribution.json` is a 12-month percentile view built by
  `scripts/acquire/build_signals_views.py`, `generated_at 2026-09-10`. No workflow runs that
  builder, and the distribution is computed over 2008-2026 spot history, so the view is
  structurally stable; its `as_of` lag is reported, not treated as a defect.
