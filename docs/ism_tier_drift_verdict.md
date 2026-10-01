# ism - the shipped series no longer matched the chart tier (found 2026-10-01 18:2x, fixed)

Status: **FIXED and shipped.** Branch `auto/extract-fixes-2026-10-01-ism-tier-drift`.
This closes the item `docs/series_verification_ledger.md` still listed as "the only open item".

## What was wrong

The ism `.charts.json` tier was **re-extracted today at 13:06** (all 230 sidecars re-stamped)
by the rewritten `scripts/extract/publishers/run_ism.py` (commit `c3e7f3337`, 13:30). That
rewrite changed the sidecar `date` field, and the change broke the downstream stacker without
touching any chart-calibration code.

Two defects, both measured:

**(D1) the sidecar `date` became a `YYYY-01-01` placeholder.** `resolve_ism_meta()` has three
branches; the fallback for a filename with a WEEK but no explicit DMY/YMD date (`ism_YYYY_Wnn_...`,
the majority style) returned `iso_date = f"{year}-01-01"`. Measured: **226 of 230** sidecars
carried it, and it shipped verbatim into the `.md` frontmatter (`issue_date: "2023-01-01"`).
The real date was recoverable - the `week` was already computed and stored; it just was not used.

**(D2) the stacker's fallback mis-derived the report week.** `run_ism_series.parse_doc_meta()`
tried `date` first with `(20\d\d)\s*W(\d{1,2})`. That regex matched the OLD `date` ("2023 W14");
against the new `2023-01-01` it fails, so parsing fell through to the filename regex
`(20\d\d).*?week[-_ ]?(\d{1,2})`, which latches onto the TRAILING `weekNN` token. For a name
whose `Wnn` differs from `weekNN` (e.g. `ism_2025_W34_ISM_coaster_week35`) that yields the WRONG
week, moving the report's ISO date and therefore which issue `pick_observation()` treats as
"nearest".

## Measured impact (before any fix)

Re-running the shipped stacker against the re-extracted tier produced, vs the committed CSVs:

| | committed (2026-09-30) | raw re-run (broken) |
|---|---|---|
| ism_handy_freight_series.csv | 17,968 rows | 18,016 rows |
| ism_coaster_freight_series.csv | 12,319 rows | 12,529 rows |
| handy series points whose VALUE changed | - | **633** |
| coaster series points whose VALUE changed | - | **204** |

**837 published series points silently changed value**, caused entirely by the date metadata -
not by any chart being re-read differently.

**(D3, adjacent) every report is written twice.** `extract_single_ism_doc()` writes the `.md`
AND the `.charts.json` to BOTH the flat dir and the year subdir ("Save both flat and year
subdirectories"). The tier therefore holds **230 files for 115 reports**. The stacker's
recursive glob saw each report twice and doubled `n_reports`. Left in place (deliberate in the
new extractor, and other consumers may read the flat layout); the stacker now dedupes.

## The fix

1. `run_ism.py resolve_ism_meta()` - when a week is known and no explicit date is, derive the
   ISO Monday: `datetime.date.fromisocalendar(year, week, 1)`. Unit-checked:
   `ism_2023_W14_ISM-coasters-for-Hellenic_week-14.pdf -> 2023-04-03` (cover text confirms
   "week 14"); `ism_2025_W34_..._week35.pdf -> 2025-08-18`.
2. Re-extracted all **115/115** ism docs ($0, PyMuPDF, 0 failures). Wrong `issue_date`s:
   **226 -> 4** (the 4 are the week-less holiday specials, x2 copies).
3. `run_ism_series.py` - `parse_doc_meta()` now prefers the sidecar's own `year`/`week` fields
   (unambiguous) over any regex; the chart glob dedupes by content hash.

## Verified after the fix

| | value | check |
|---|---|---|
| ism_handy 17,968 rows | sha `c764bb00d778...` | **0 series keys added/removed, 0 VALUE changed** vs committed; only 611 `n_reports` corrected (were doubled) |
| ism_coaster 12,462 rows | sha `07d32cd48132...` | +143 rows, **0 removed, 0 value changed** |
| the +143 rows | `Wheat, 25-30,000 t, Constanta - EgyptMed (8000x/5000x), $/t` / `2024..2026 year` | traced to the new **2026 W39** issue; values 11.2-23.0 sit inside that chart's printed axis `10..30`; `verified=True`; segment `Coaster` (correct) |
| agreement gate (ledger instrument) | handy within-2% **74.1% -> 74.9%**, p90 11.76 -> 11.35 | coaster 83.7% unchanged, p90 5.67 unchanged |

The `wheat` route also legitimately appears in handy (280 rows, 6 year-lines, values 11.0-34.0
against its own `10..38` axis) - the two publications share the route, they are not a duplicate.

## Reproduce

```
python3 scripts/extract/publishers/run_ism.py --docs $(find corpus/01-brokers/ism -name '*.pdf')
python3 scripts/extract/publishers/run_ism_series.py
python3 scratch/measure_agreement.py
```
Control copies of the pre-fix code: `scratch/ism_dup/run_ism.py.bak`, `run_ism_series.py.bak`;
the pre-fix CSVs: `scratch/ism_pretest/`.

## Residual (unchanged, already root-caused)

The ism agreement tail is the publisher's own axis-label shift between issues, measured and
read on 2026-09-30 (see the lower sections of `docs/ism_agreement_tail.md`); §4 there flags one
lever that IS ours (choose the reading nearest the cluster median). It was **not** applied:
`pick_observation()` deliberately prefers the week's OWN issue over older restatements, and the
median would report a value the publisher never printed that week. Left as a documented,
unapplied option rather than a silent regression.
