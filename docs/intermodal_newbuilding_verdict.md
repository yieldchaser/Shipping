# Intermodal indicative newbuilding prices - one-column shift, fixed and verified

**2026-09-28 (unattended run).** Source: `corpus/01-brokers/intermodal` (252 reports,
2021-2026). Artefacts: `data/extracted/series/intermodal_newbuilding_prices_series.csv`
and `intermodal_newbuilding_series.csv`. Runner:
`scripts/extract/publishers/run_intermodal_full.py`. No API spend - the whole job was
rebuilt from the **cached** LlamaParse markdown (`--reparse-only`, 252/252, 0 failures,
72 s).

## The defect: every row was shifted one column left

The ledger (`docs/series_verification_ledger.md` 7.3) recorded this file as *"893 rows
(28.0%) have `price_previous_usd_m = 0.0` - a missing previous written as a zero"*. That
diagnosis was **wrong, and far too small**. The real defect is a one-column shift on
**every row of the file**.

The parser read `cols[1..5]` positionally:

```python
v_type = cols[1]; size = cols[2]; curr = cols[3]; prev = cols[4]; pct = cols[5]
```

but the table prints the vessel NAME in `cols[0]` and the SIZE in `cols[1]`. So:

| published column | actually held |
|---|---|
| `vessel_type` | the vessel **SIZE** (`205k`) - the name was dropped entirely |
| `size` | the **current price** |
| `price_current_usd_m` | the **previous price** |
| `price_previous_usd_m` | the **±%** |
| `pct_change` | the **2020 average** |

Source page (intermodal_2021_W26, page 5) vs what was published:

```
PAGE:       | Newcastlemax | 205k | 62.5 | 62.5 | 0.0% | 51 | 54 | 51 |
PUBLISHED:  vessel_type=205k  size=62.5  cur=62.5  prev=0.0  pct=51
```

The `0.0` in the `previous` column was simply the printed ±% of an unchanged price - which
is exactly why a count-based check saw "893 missing previous values" instead of a shift.

**Measured, before -> after:**

| measure | before | after |
|---|---|---|
| `intermodal_newbuilding_prices_series.csv` rows | 3,194 | **3,134** |
| `vessel_type` holding a size/price instead of a name | 1,408 | **0** |
| rows with a blank `previous` | 60 | **0** |
| rows whose (cur, prev, pct) triple is self-consistent | 1,603 | **3,112** |
| `intermodal_newbuilding_series.csv` rows | 5,027 | **4,967** |

1,603 of the old rows *were* internally consistent (when prev == cur the shift still
"adds up"), which is why the file passed every automated gate it was given.

## The fix: anchor on the ±% cell, not on a column index

Layout is not stable across years - four shapes were measured in the cached markdown:

| era | cells | shape |
|---|---|---|
| 2021/2022 | 8 | `name | size | cur | prev | ±% | 2020 | 2019 | 2018` |
| 2023_W18 | 8 | `"Newcastlemax 205k" | cur | prev | ±% | 2022 | 2021 | 2020` |
| 2023_W20+ | 13 | `"Bulkers"` fused with the row, then `name | size | cur | prev | ±% | ...` |
| 2023_W48+ | 12 | `name | size | cur | prev | ±% | YTD H | YTD L | 5Y H | 5Y L | 2022 | 2021 | 2020` |

The one landmark present in **all four** is the `±%` cell, so the parser now finds it and
walks back two cells for `current`, one for `previous`, then takes the name/size cells
before it (splitting `"Newcastlemax 205k"` when the publisher fuses them). Rows with no
`±%` cell (a whole column dropped by LlamaParse in one issue) fall back to the size cell as
the anchor.

Two more things the fix had to get right:

* **the section label can share a row with data.** In 2023_W20 the grid row is
  `Bulkers | Newcastlemax | 205k | 65.0 | 64.5 | 0.8% | ...`. The old loop skipped any row
  whose first cell was `Bulkers`, silently losing 138 documents' Newcastlemax rows.
* **the section label is not a reliable sector.** In `intermodal_2021_W38` the publisher
  prints the `Bulkers`/`Tankers`/`Gas` rows *after* the data rows, so a positional sector
  labelled all 13 rows "Bulkers" (VLCC and LNG included). The sector is now derived from the
  vessel name (40 rows were mislabelled).

### Rows deliberately dropped (73)

A wrong value is worse than a missing one. Dropped and counted:

| reason | rows |
|---|---|
| a fused header artefact used as a vessel name (`VesselBulkersTankersGas`, `SizeNewcastlemax`, `Vessel`) | 54 |
| `±%` that does not reproduce from (cur-prev)/prev - LlamaParse rotates cells across rows in ~6 issues (2023_W40, 2023_W43, 2023_W45, 2025_W13, 2026_W10) | 10 |
| no anchor cell at all / no name cell | 9 |

### A second defect found on the way: malformed `<td` tags

`extract_grids()` repaired only the **first** cell of a row written as `td>` (missing the
opening `<`). Two documents write **every** cell that way, so the whole data block parsed as
one cell per row and the values were lost (101 such lines in `intermodal_2021_W38`, 14 in
`2021_W30`). Repairing all of them recovered 2021_W38's 13 newbuilding rows.

## Verification

No image/vision tool exists in this cron session, so "render a page and look at it" is
**substituted** with the same-document text reconciliation the skill prescribes - stated
plainly rather than implied.

**1. Reconcile every published row against the PDF's own text layer.**
For each of the 3,134 rows, the `(current, previous)` pair must appear as a *consecutive*
numeric run in the source PDF's text (`scripts/audit/verify_intermodal_newbuilding.py`, pymupdf):

```
published rows: 3134   docs: 252   pdf-missing: 0
(cur, prev) found as a consecutive run in the PDF text layer: 3132/3134 = 99.94%
```

The 2 that do not match:
* `intermodal_2022_W19` Newcastlemax `66.75 / 66.5` - that issue prints **comma decimals**
  (`66,75`). The extracted value is right; the checker's ISO comparison is what fails.
* `intermodal_2024_W31` VLCC `129.0 / 129.5` - a **real residual**. LlamaParse dropped the
  whole ±% column for that issue, so `previous` picked up the YTD-high cell. The page prints
  `129.0 | 129.0 | 0.0%`, i.e. the correct `previous` is **129.0**. One row in 3,134 (0.03%),
  reported rather than hand-patched.

**2. Recover the `previous` values LlamaParse dropped.** `recover_nb_previous()` anchors on
`[current, <one number>, ±%]` in the document's numeric stream and requires **exactly one**
match (same doctrine as the existing `recover_missing_prev_month`). 6 values recovered;
blank `previous` cells 60 -> 0.

**3. Control.** All 10 other intermodal series CSVs are **byte-identical** to their
pre-run md5 (`scratch/intermodal_ctrl/`): tanker_spot, tc_rates, indicative_values,
baltic_indices, currencies, sales, newbuilding_orders, demolition, demolition_prices,
demo_sales. Only the two newbuilding files changed.

**4. Spot-check against the printed page** (three eras, text layer read directly):

```
2021_W26  Newcastlemax 205k  cur 62.5   prev 62.5   pct 0.0%   <- page: 62.5 | 62.5 | 0.0%
2021_W26  VLCC          300k cur 98.5   prev 97.5   pct 1.0%   <- page: 98.5 | 97.5 | 1.0%
2021_W38  Handysize     38k  cur 29.0   prev 28.5   pct 1.8%   <- page: 29.0 | 28.5 | 1.8%
2024_W31  Capesize      180k cur 76.5   prev 76.5              <- page: 76.5 | 76.5 | 0.0%
```

## Reproduce

```
PY312=/c/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe   # llama_parse lives here
$PY312 scripts/extract/publishers/run_intermodal_full.py --year all --reparse-only   # 252/252, 0 credits
$PY312 scripts/audit/verify_intermodal_newbuilding.py
    # 1. the 99.94% text reconciliation   2. continuity: prev vs the previous issue's current
```

## Open, measured, not fixed

* the single `intermodal_2024_W31` VLCC `previous` (129.5 should be 129.0), above;
* the 2020/2019/2018 (or 2022/2021/2020) year-average columns on the right of this table are
  still not captured - the sibling `intermodal_indicative_values_series.csv` does carry three
  `avg_prev_year_*` columns, so the schema is there if the columns are wanted. They are NOT
  captured now because the trailing columns are rotated in the same ~6 corrupt issues, so
  they cannot be validated the way `current`/`previous` can.
