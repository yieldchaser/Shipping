# affinity WS-era md rendering — FIXED (source-by-source, 30m job)

Date: 2026-10-04 (run after the 13:5x push/sweep run). Branch `auto/extract-fixes-2026-10-04`.

## Trigger

The carried-open item "affinity WS-era md rounding (144 cells, DISPLAY ONLY,
`docs/affinity_verify_verdict.md`)" — previously left as a decision item. The md
tier is affinity's PRIMARY deliverable, and the defect was a wrong display value,
so this run measured it and fixed it.

## The defect (proven against the rendered page)

In the WS era the CLEAN card is headed `$ / WS` and some routes are quoted in
Worldscale. `polish_affinity_markdown.py` ran every rate through `format_rate()`,
which formats `{val:,.0f}` with a `$` prefix, so a printed `WS 130.63` became
`$131` — losing BOTH the unit and the decimal.

Ground truth from the RENDERED page text layer (not another extractor), 2021-10-01,
page 0 panel (`pymupdf`, spans x>560, y-ordered):

```
422.1 755.3  '$ / WS'          <- CLEAN block header (md printed 'Rate ($/Day)')
490.8 747.7  'WS 130.63'       TC6   (md printed '$131')
525.1 755.8  'WS 25'           TC8   (md printed '$25')
542.3 747.7  'WS 130.71'       TC9   (md printed '$131')
```

The DIRTY block header prints `$ / Day`; the CLEAN block header prints `$ / WS`.
The md hardcoded `Rate ($/Day)` for both.

## Measured scope

| metric | value |
|---|---|
| docs in the WS era | **68** (2021 = 26, 2022 = 42; none 2023+) |
| TCE rate cells reconciled | **4,039** |
| md cells mismatching the exact CSV, BEFORE | **144** |
| md cells mismatching, AFTER | **0** |
| cells whose printed text carries an explicit `WS ` prefix (`unit_source='explicit-ws'`) | **161** |
| rate-column headers wrong, BEFORE | 68 CLEAN blocks (all WS era) |
| rate-column headers wrong, AFTER | **0** (496/496 block headers correct) |

## Fix (source only; `polish` renders, `run_affinity_tables` only stamps)

`polish_affinity_markdown.py`:
- new `format_rate_cell(raw_val, val, unit_source)` — an explicitly WS-quoted
  cell is rendered verbatim as `WS {val:g}` (keeps unit + decimals); every other
  cell is unchanged, so non-WS-era markdown is byte-identical.
- new `rate_header(unit)` — the Rate column header comes from the block's printed
  unit (`$ / WS` vs `$ / Day`) instead of a hardcoded `$/Day`.
- `dirty_rows` / `clean_rows` now carry `value_raw`, `unit`, `unit_source`.

`orchestrate_incremental_ingest.py` (the live incremental path renders affinity md
too, with the same hardcoded header + `pam.format_rate`) — carries the same three
fields and now calls `pam.format_rate_cell` / `pam.rate_header`. It only sees the
modern (non-WS) era, so behaviour there is unchanged; the code is now single-sourced.

## Controls (run the ORIGINAL code and the PATCHED code side by side)

| control | result |
|---|---|
| `affinity_tce_series.csv` orig vs patched | **byte-identical** (cmp) |
| `affinity_bda_series.csv` orig vs patched | **byte-identical** |
| `affinity_indices_series.csv` orig vs patched | **byte-identical** |
| md files changed by the patch | **exactly 68** = {2021: 26, 2022: 42} = the WS era |
| 2021-10-01 md diff | only the 4 intended lines (header + 3 WS cells) |
| `polish` determinism (2 consecutive passes) | md byte-identical, CSVs byte-identical |

The patch touches NO series data: all three CSVs are byte-reproducible across the
code change. (Note: `affinity_tce_series.csv` and `affinity_bda_series.csv` have
TWO writers — `polish` and `run_affinity_tables` — and their `trend_wow` formatting
differs (`↑ Firmer` vs `↑Firmer`); the on-disk hashes therefore move whenever the
other writer runs. That churn is pre-existing and unrelated to this fix.)

## Second finding + fix: the newest issue's sidecar was incomplete

`verify_affinity.py` (after its stale counts were relaxed — see below) exposed that
the 2026-10-02 issue's sidecar
(`affinity_03_10_2026_affinity_tanker_weekly_2_october_2026.tables.json`) was
written by the fetcher with NO top-level stamps (`stem`/`source_file`/`issue_date`/
`report_week` all null) and NO BDA `records` list that every other sidecar carries.
Stamped in place with the canonical resolver (`run_affinity_tables.resolve_metadata`
-> `2026-10-02`, week 40) and regenerated its 3 BDA records in the canonical shape.
No other file touched.

Also relaxed `verify_affinity.py`'s three hardcoded counts (254 PDFs / 247 sidecars
/ 247 md) that went stale when the 2026-09-25 and 2026-10-02 issues landed. It now
asserts the real invariants: `sidecars == mds`, and `pdfs >= sidecars` (the 7 extra
PDFs are byte-duplicates of processed issues).

## Result

- `scripts/verify/verify_affinity.py` = **6/6 PASSED** (was failing at check 1 on a
  stale count, then check 2 and check 4 on the incomplete newest sidecar).
- Reconciliation: **4,039 / 4,039** TCE rate cells match the exact CSV + printed
  card; header errors **0**.

**affinity: CLOSED for this defect.** The md now reproduces the publisher's own
`$ / WS` unit and the printed decimals.
