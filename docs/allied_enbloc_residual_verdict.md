# allied_sales_series.csv - the 6 page-confirmed en-bloc RESIDUALS are FIXED (2026-10-07 21:xx cron)

**Source:** `corpus/archive/allied` (203 PDFs, 2021-2024, BACKFILL_ONLY).
**File changed:** `data/extracted/series/allied_sales_series.csv` (3,218 rows) + runner
`scripts/extract/publishers/run_allied.py`.
**Context:** this executes **route 2** of `docs/allied_enbloc_residual_page_evidence.md`
(the run of 02:4x that classified the 7 residual `>USD 200m` rows from their own page
text but deferred the write). It is not a new policy: it is the **same class of fix** the
02:1x run already applied to **52** rows (`docs/allied_enbloc_verdict.md`) - the only
difference is that for these rows the table parser put the AMOUNT in the row but dropped
the words `en bloc`/`in cash`, so `_lot_binding()`'s own-cell marker scan skipped them.

## The 6 rows fixed (price_usd_m blanked, group_total_mil set)

| row | before price_usd_m | after | page evidence (verbatim, whitespace-normalised) |
|---|---|---|---|
| `MP THE GRONK` | 242.0 | **group_total_mil=242.0** | 4 `MP THE …` PMAX unpriced, footer `Containers $ 242.0m MSC` |
| `JUDITH SCHULTE` | 260.0 | **group_total_mil=260.0** | `POST PMAX JUDITH SCHULTE` + `JOHANNA SCHULTE` unpriced, footer `$ 260.0m en bloc undisclosed` |
| `HL AQUAMARINE` | 291.0 | **group_total_mil=291.0** | 5 `HL …` VLOC unpriced, footer `$291.0m en bloc Golden Ocean` |
| `GASLOG SYDNEY` | 284.0 | **group_total_mil=284.0** | `LNG GASLOG SYDNEY` + `GASLOG SARATOGA` unpriced, footer `CDB Leasing $ 284.0m en bloc` |
| `SKS DEE` | 239.0 | **group_total_mil=239.0** | 8 `SKS …` AFRA unpriced, footer `$ 239.0m in cash & 5.5 millions shares TORM A/S` |
| `HARRISON BAY` | 238.0 | **group_total_mil=238.0** | 6 `… BAY` MR unpriced, footer `International Seaways $ 238.0m en bloc` |

**Deliberately NOT fixed:** `HYUNDAI SAMHO 8196` (234.0). Its page prints
`declaration of purchase option Coolco $ 234.0m each` - `each` makes it a genuine
per-vessel price, so it must stay in `price_usd_m`.

## How it was applied

A page-verified override table `VERIFIED_LOT_TOTALS` added to `run_allied.py`, applied
in `deal_rows()` AFTER `_lot_binding()`. Full runner re-run from scratch
(`_run_state.json` / `_deals.jsonl` cleared and backed up to `scratch/allied_fix/`):
**203/203 docs, 0 failures, 340 s.**

## Verification

* **Exactly 12 field changes on exactly 6 rows.** Field-level diff of before/after CSV:
  row count 3,218 -> 3,218, key set `(source_file,name,dwt,price_raw)` identical;
  every change is `price_usd_m: X -> ''` paired with `group_total_mil: '' -> X`. No other
  column touched. `group_total_mil` set on **58** rows (was 52; +6).
* `price_usd_m` **max is now 234.0** (was 291.0), and the only `>200m` row is the
  correctly-kept `HYUNDAI SAMHO 8196`.
* **Control (same-document):** each of the 6 group totals is printed joined to
  `en bloc`/`in cash` in its OWN document (re-derived from the PDF text layer).
* **Control (untouched tiers):** all **203 `.md` and 203 `.tables.json` md5-identical**
  to before the run (same result the 02:1x re-run produced).
* **Register gate** (`scripts/extract/verify_registers.py`): ALL PASSED, 180 CSVs /
  **640,870** logical rows == JSON == MD, 0 mismatches, 0 control chars/emoji. Row count
  unchanged, so nothing in the register needed editing.
* **Blast radius:** `index.html` contains no `allied_sales`/`group_total_mil` reference,
  so these values are not app-displayed.

## Residual DISCLOSED and still open (needs a page render)

The same text-only rule (`own table row prints no money` AND
`stored price equals an amount printed joined to en bloc/in cash` AND
`no competing each/p-v for that amount`) fires on **42 rows** still carrying a
per-vessel-column value (`scratch/allied_strict_rule.py`, log
`scratch/allied_fix/strict_rule.log`). It is NOT applied, because it over-fires:

* **10 of the 42 have no unpriced sibling fleet on the page**
  (`TSUNEISHI ZHOUSHAN SS-312` 35.0, `YZJ2015-2075` 80.0, `BALTIC SOUTH` 160.0 …) -
  these look like NEWBUILDING hull rows whose own printed price happens to equal some
  other lot's `en bloc` amount -> false positives, exactly the over-fire the 02:4x run
  measured (its Rule A fired on 55, Rule B on 14 and missed 4 confirmed lots).
* **32 of the 42 have >=1 unpriced same-size sibling** and are plausible lots, but the
  binding of a footer amount to a specific fleet cannot be settled from text when a page
  prints >=2 `en bloc` amounts, and 2 of this run's candidates collide with a legit
  per-vessel price of the same value (`ARCTIC BREEZE` 24.0 vs `KMAX DERBY` 24.0;
  `PACIFIC 07` 16.0 vs `MR OLYMPIC GLORY` 16.0).

Per the standing rule **"a wrong value is worse than a missing one"**, those 32 are left
unchanged. They are mechanically bindable with one render pass (dpi=115) - that remains
the user's call.

Also note: `ELANDRA BLU` 24.0 (2023 W13) is **not a defect** - its page prints
`Viken $ 24.0m p/v` (`p/v` = per vessel), so a per-vessel value is correct there.

## Reproduce

```
python3 scripts/extract/publishers/run_allied.py            # 203 docs, ~340 s, resumable
python3 scratch/allied_strict_rule.py                       # the 42-row residual (over-fires)
python3 scripts/extract/verify_registers.py                 # register gate
```
