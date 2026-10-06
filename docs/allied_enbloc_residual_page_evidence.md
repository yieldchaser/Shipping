# allied - en-bloc residual: per-row PAGE evidence + why no automatic binder is trusted

**Date:** 2026-10-07 (cron 02:4x)  **Source:** `corpus/archive/allied` (203 PDFs, 2021-2024, BACKFILL_ONLY)
**File under review:** `data/extracted/series/allied_sales_series.csv` (3,218 rows)
**Runner:** `scripts/extract/publishers/run_allied.py`
**Context:** the 7 rows > USD 200m that the 2026-10-07 02:1x allied fix left unlabelled
(`docs/allied_enbloc_verdict.md` residual table). This run read each row's OWN page text
layer to classify it - the vision substitute the skill mandates when the cron session has no
image tool (it has none: only `terminal` + `process_manage`).

## The 7 residuals, classified from the page text (verbatim quotes)

| row | csv price | page (0-based) | page text (verbatim, whitespace-normalised) | verdict |
|---|---|---|---|---|
| `HYUNDAI SAMHO 8196` | 234.0 | 7 | `... LNG HYUNDAI SAMHO 8196 80,690 2025 ... LNG HYUNDAI SAMHO 8197 80,690 2025 ... declaration of purchase option Coolco $ 234.0m each` | **LEGIT per-vessel** (`each`) - KEEP |
| `GASLOG SYDNEY` | 284.0 | 8 | `LNG GASLOG SYDNEY 82,010 2013 ... 151,900 LNG GASLOG SARATOGA 81,855 2014 ... 151,990 CDB Leasing $ 284.0m en bloc rgn $ 61.0m en bloc JP Morgan` | **LOT TOTAL** (2 LNG, CDB Leasing) |
| `JUDITH SCHULTE` | 260.0 | 8 | `POST PMAX JUDITH SCHULTE 9,403 2013 ... POST PMAX JOHANNA SCHULTE 9,403 2013 ... Containers Gas Carriers $ 260.0m en bloc undisclosed` | **LOT TOTAL** (2 container, undisclosed) |
| `HL AQUAMARINE` | 291.0 | 9 | `VLOC HL PEARL 207,999 2020 ... HL SAPPHIRE ... HL AQUAMARINE ... HL DIAMOND ... HL EMERALD ... Bulk Carriers Containers Tankers - Continued Gas Carriers $291.0m en bloc Golden Ocean` | **LOT TOTAL** (5 HL VLOC, Golden Ocean) |
| `HARRISON BAY` | 238.0 | 8 | `MR EXCELSIOR BAY ... CRYSTAL BAY ... HARRISON BAY 49,990 2015 ... SAINT ALBANS BAY ... JENNINGS BAY ... LAFAYETTE BAY ... International Seaways $ 238.0m en bloc` | **LOT TOTAL** (6 BAY MR, Intl Seaways) |
| `SKS DEE` | 239.0 | 8 | `AFRA SKS DOKKA 119,950 2010 ... SKS DELTA ... SKS DOURO ... SKS DEE ... SKS DONGGANG ... SKS DODA ... SKS DEMINI ... SKS DOYLES ... China Tankers $ 239.0m in cash & 5.5 millions shares TORM A/S ... $ 10.0m each $ 13.5m each Stainless Tankers $ 14.0m each` | **PACKAGE TOTAL** (8 SKS AFRA, TORM A/S; note `in cash & shares`, no `en bloc` word) |
| `MP THE GRONK` | 242.0 | 7 (row stored on page 7; the amount is on page 8) | p8: `PMAX MP THE EDELMAN 5,060 2005 ... MP THE BRONK ... MP THE BRADY ... MP THE BELICHICK ... Containers $ 242.0m MSC rgn $ 7.0m en bloc Chinese` | **LOT TOTAL** (4 MP THE PMAX, MSC) |

=> 6 of 7 are lot/package totals wrongly sitting in the per-vessel price column; 1
(`HYUNDAI SAMHO 8196`, 234.0) is a genuine per-vessel `each` price and must be KEPT.
The row data carries the giveaway: a lot row's `price_raw` has the amount but the
`en bloc` word was dropped by the row parser, so `_lot_binding()` (which scans the run's
own price cells for `en bloc`) never sees a marker and skips the run.

## Why NO automatic binder was applied this run (measured, not asserted)

Rule A - "the row's price X appears in the page text immediately joined to `en bloc` or
`in cash`, and X is NOT printed with `each` on that page":
- fires on **55 rows** (`scratch/allied_footer_lot_audit.py`). Far too broad: it also
  catches legit single-ship sales whose page merely contains another lot's `$X en bloc`.

Rule B - Rule A **AND** the row is in a consecutive same-Size / same first-name-token run
of >=2 rows whose only priced row it is (`scratch/allied_footer_lot_audit2.py`):
- fires on **14 rows**. Still not safe in EITHER direction:
  * it **MISSES 4 of the 6 confirmed lots** (`GASLOG SYDNEY` - sibling also priced at 61.0;
    `JUDITH SCHULTE`, `MP THE GRONK`, `HARRISON BAY` - run/price assignment quirks);
  * it still includes a mis-parsed case (`GALAXY` 23.0: the page rows read
    `EASTERLY BEECH GALAXY` / `EASTERLY LIME GALAXY`, so the stored name `GALAXY` is wrong).
- A rule that both over-fires and misses the confirmed set cannot be trusted to write values.

Per the standing rule "a wrong value is worse than a missing one", the values were **left
unchanged**. Binding them needs either a page render (vision) or a per-row verified override.

## 14 structural candidates (page-text en bloc/in cash + fleet lot) - OPEN, unverified-by-eye

`GALAXY`(23.0), `ARCTIC BREEZE`(24.0), `ELANDRA BLU`(37.0), `GOLDEN CECILIE`(63.0),
`ALPINE PEMBROKE`(130.0, 4 LR1), `MP THE VRABEL`(121.0), `IVS HAYAKITA`(46.5),
`NCC NAJD`(34.0), `EASTERN OASIS`(42.0), `ALPINE PEMBROKE`(65.0, W51),
`XING HE HAI`(52.5), `PACIFIC 07`(16.0) [+ the run members].
Most read as genuine 2-4 ship lots with unpriced siblings; each still needs a render to
bind safely. Recorded so a future vision pass is mechanical.

## Recommendation (needs the user)

Two safe routes, in preference order:
1. **Vision pass** (the state's own call): render the 7 pages above + the 14 candidate pages
   at dpi=115 and confirm each `en bloc`/`in cash` amount belongs to the fleet on that page,
   then blank `price_usd_m` and set `group_total_mil` in one pass.
2. **Verified override**: add the 6 confirmed rows as an explicit, page-evidenced
   `(source_file, name) -> group_total` table applied after `_lot_binding()` in
   `run_allied.py`. Deterministic (the 203-PDF corpus is static) and touches exactly 6 rows.
   Not done this run because it would fix 6 of ~20 same-class rows and look inconsistent
   without the vision pass covering the rest.

## Reproduce

```
python3 scratch/allied_footer_lot_audit.py     # Rule A: 55 candidates
python3 scratch/allied_footer_lot_audit2.py    # Rule B: 14 candidates (misses 4 confirmed)
# page-text reads for the 7 residuals are cached in scratch/allied_resid/*.txt
```
