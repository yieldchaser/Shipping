# allied_sales_series.csv - en-bloc LOT TOTALS removed from the per-vessel price column (FIXED)

**Date:** 2026-10-07  ·  **Source:** `corpus/archive/allied` (203 PDFs, 2021-2024, BACKFILL_ONLY)
**File:** `data/extracted/series/allied_sales_series.csv`  ·  **Runner:**
`scripts/extract/publishers/run_allied.py`
**Input to this work:** `docs/allied_enbloc_price_finding.md` (hourly supervisor, read-only).

## The defect (lion-class: a FLEET/LOT total sitting in a per-vessel price column)

allied prints a multi-ship lot's transaction value ONCE, in the Price column, next to the
words `en bloc`. The parser read that amount as the price of whichever row it landed on.
15 rows exceeded USD 200m (max **660.0** for an MR-class row); a 2016 MR is ~USD 30m and a
VLCC ~USD 80m, so those were not per-vessel prices.

Confirmed against the source pages (pymupdf `page.get_text`, no vision tool in this session):

- `STH OSLO` 2022-08-21 - page prints `$ 330.0m  en bloc`; 9 `STH *` UMAX on the page,
  220 + 110 cash+shares = 330 -> the lot total.
- `KOOL FIRN` 2022-11-06 - `en bloc     $ 660.0m` for the 4 `KOOL *` LNG.
- `ISTANBUL` 2022-08-21 - `$ 222.5m en bloc` (SUEZ lot).
- `DAEWOO 5497` 2021-11-21 - `$ 245.0m en bloc`.

## The fix (content-anchored, no row order, no geometry)

`_lot_binding()` groups CONSECUTIVE rows on a page that share the SAME size class AND the
SAME fleet name-prefix and that CONTAIN `en bloc` in the run's price cells; the lot's value
is the ONE money amount among those rows. The row carrying it is blanked in `price_usd_m`
and recorded in a new **`group_total_mil`** column. A CERTAIN own-cell
(`$ 245.0m en bloc` in one cell) always binds.

Two guards, both forced by measurement - a looser rule was built, measured, and REJECTED:
- A run holding MORE THAN ONE amount is ambiguous -> leave every row unlabelled.
- A page-text "nearest money to en bloc" binder mis-fired (blanked `ERAWAN 10` $12.0m and
  `DOLPHIN 03` $18.0m - two separate sales sharing a page with a lot). Rejected;
  a wrong value is worse than a missing one.

## Measured before / after

| metric | before | after |
|---|---|---|
| rows | 3,218 | 3,218 (unchanged) |
| `price_usd_m` max | **660.0** | **291.0** |
| rows > USD 200m | **15** | **7** |
| lot totals moved to `group_total_mil` | 0 | **52** |

**Verification.**
1. **md control:** all 203 `.md` byte-identical (md5, before vs after) - the primary
   deliverable is untouched; only the series CSV changed.
2. **Re-run:** 203/203 docs, 0 failed, 202 s (`scratch/allied_rerun.log`).
3. **Neighbour control (per page):** legit per-vessel prices on a lot's page are preserved -
   `RIDGEBURY SATURN` $18.0m, `RIDGEBURY MARY SELENA` $31.0m, `LESSLEY` $45.0m, `ERAWAN 10`
   $12.0m all kept.
4. `verify_registers.py` = **ALL CHECKS PASSED** (177 CSVs / 638,931 rows, 0 mismatches).

## Residual - 7 rows still > USD 200m (read and classified by eye, NOT auto-bound)

| row | page shows | verdict |
|---|---|---|
| `HYUNDAI SAMHO 8196` 234.0 | `$ 234.0m  each`, buyer Coolco, NO `en bloc` on page | **LEGIT** - haul `each` price, KEPT |
| `HARRISON BAY` 238.0 | `$ 238.0m \| en bloc`, Intl Seaways | lot total, not bound (fleet-name run split from its marker row) |
| `JUDITH SCHULTE` 260.0 | `$ 260.0m  \| en bloc` | lot total |
| `HL AQUAMARINE` 291.0 | `$291.0m en bloc`, Golden Ocean | lot total |
| `GASLOG SYDNEY` 284.0 | `$ 284.0m \| en bloc` (GASLOG SYDNEY + SARATOGA) | lot total |
| `MP THE GRONK` 242.0 | Containers sub-table, buyer MSC; `en bloc` belongs to a `$ 7.0m` | unresolved - possible mis-assignment |
| `SKS DEE` 239.0 | `$ 239.0m in cash & 5.5m shares`, TORM A/S; per-vessel `$ 10.0/13.5/14.0m each` | package total (no `en bloc` phrase) |

These are named, measured and left unlabelled on purpose: binding them needs a page render
(a vision pass) - the automated binders that would catch them also mis-fire on legit prices.

## Reproduce

```
python3 scripts/extract/publishers/run_allied.py           # 203/203, rebuilds the CSV
python3 scripts/extract/verify_registers.py                # ALL PASSED
python3 scratch/enbloc_fleet.py                            # the run-binding rule, read-only
python3 scratch/check7.py                                  # the 7 residual page windows
```
