# Xclusiv chart series: fake dates removed, `report_week` finally populated

**Verdict: the ledger's item 4.4 does not reproduce as written (230 rows).** Measured across the
whole series tier - **119 CSVs, 334,358 date-shaped cells** - only **12** calendar-invalid date
cells existed, all `2026-00-00` in the two Xclusiv *chart* files. The 218 rows the ledger
attributed to `intermodal_macro` (92), `intermodal_maritime_stocks` (72) and `intermodal_bunkers`
(54) **are not in those files**: their `issue_date` columns are 100% well-formed ISO on all
3,739 / 3,119 / 2,260 rows, and the read-only corpus DB holds no `2026-00-00` in any date column
either. The 12 real ones are now fixed, and a **second defect found in the same pass** -
`report_week` was `0` on all 498 rows - is fixed too.

Ledger item: `docs/series_verification_ledger.md` 4.4.

## What was actually wrong

| file | rows | what | before | after |
|---|---|---|---|---|
| `xclusiv_bulk_carrier_charts_series.csv` | 216 | `issue_date` fake | `2026-00-00` x4 | `2026-09-15` / `2026-09-22` |
| `xclusiv_bulk_carrier_charts_series.csv` | 216 | `issue_date` **wrong** | `2025-12-10` x4 | `2026-04-20` |
| `xclusiv_demolition_charts_series.csv` | 282 | `issue_date` fake | `2026-00-00` x4 | `2026-09-15` / `2026-09-22` |
| `xclusiv_demolition_charts_series.csv` | 282 | `issue_date` **wrong** | `2025-12-10` x2 | `2026-04-20` |
| both | 498 | `report_week` | `0` on **all 498** | ISO week, 1-53 |

The 4 + 2 `2025-12-10` values were worse than the fake ones: a plausible date four months before
the file's own name (`xclusiv-2026_04_20.pdf`), read off a page-1 date string. A wrong date
sorts into the right place and never looks broken.

## Why it happened and what fixed it

`run_xclusiv_vector_charts.py` derived the date from page-1 prose and wrote `2026-00-00` when it
failed (2 documents x 2 series). It was patched at 20:47 to prefer the date in the filename and
to write BLANK rather than a fake date - **but the patch was never run**: the CSVs on disk were
dated 2026-09-26, nine hours older than the fix. A fixed parser with stale output is
indistinguishable from an unfixed defect; the files were regenerated from the patched parser.

`report_week` was derived only from a week number in the filename, which no Xclusiv filename
carries, so the column was `0` on every row. Added `derive_report_week(iso_date)`: the ISO week
of `(issue_date - 7 days)`, used **only** when the filename has no week number.

## Verification

**Same-document control for the week derivation.** `run_xclusiv_tables.py` writes the same
week for the same documents. For the 261 issue dates both tiers date, the derivation agrees on
**257 (98.5%)**; the four disagreements are implausible control values (week 6 for `2021-11-29`,
week 1 for `2022-03-28`, week 2 for `2022-07-11`). For the two documents in question the control
says 37 and 38 and the derivation says 37 and 38.

**Independent filename check.** Every row's `issue_date` was compared against the date encoded
in its own `source_file`: **498/498 agree, 0 mismatches** (was 6).

`scratch/sup/verify_xclusiv_charts.py` - **PASS**:

* row counts unchanged: 216 and 282;
* 0 calendar-invalid `issue_date` rows; 0 blank `report_week`;
* 1,992 non-date cells byte-identical; 0 chart values changed;
* every `report_week` equals `derive_report_week(issue_date)`.

**Corpus re-measurement:** 0 calendar-invalid date cells remain across 334,358 date-shaped cells
in 119 series CSVs.

## Operational note

Two instances of the same runner were found writing the same two CSVs (PIDs 21072 and 24488);
the older, untracked one was killed - each writes its whole file at the end, so two writers on
one path is a real interleaving risk, not just a last-writer-wins race.
