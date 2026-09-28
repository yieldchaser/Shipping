# bancosta_commodities_series.csv - verdict: the file was largely MIS-PARSED (fixed)

**Date:** 2026-09-29 ~00:1x IST - closes the `bancosta_ffa` / `bancosta_commodities` check that
`docs/series_verification_ledger.md` section 3 named as "the two to check first".

## What the ledger said, and what was actually wrong

The ledger flagged these two files only because their cross-issue continuity score was low
(`bancosta_ffa` 23.8% within 1%, `bancosta_commodities` 11.0%). It explicitly said a low score
is "a candidate for a per-source semantics check, not a proven defect". Reading the files and
the source pages shows the two are completely different cases:

* **`bancosta_ffa_series.csv` - the low score is the PUBLISHER's, not ours (mostly).** The page
  prints a `previous` column that does not reproduce the prior issue's own `current` column.
  Ground truth, page 10 of two consecutive issues:
  `2021_W26` prints `Aug-21 | 2-Jul 31,643 | 25-Jun 36,064`; `2021_W27` prints
  `Aug-21 | 9-Jul 35,129 | 2-Jul 37,107`. Both sidecars store exactly what their own page
  prints (verified by reading the PDF text layer), so the 2-Jul point was restated by 17%
  between the two issues. Each row is internally consistent with its own printed W-o-W
  (`(31643-36064)/36064 = -12.26%` vs the printed `-12.3%`). A column swap was ruled out: the
  sign of `current - previous` matches the printed W-o-W on **7,475 / 7,500 rows (99.67%)**.
* **`bancosta_commodities_series.csv` - a REAL, large extraction defect.** Not a semantics
  question at all.

## The commodities defect (measured against the printed page)

`2022_W02` page 12 ("COMMODITY PRICES") prints, for the OIL & GAS block:

```
| Crude Oil ICE Brent  | usd/bbl | 86.1  | 81.8  | +5.3% | +53.7% |
| Crude Oil Shanghai   | rmb/bbl | 533.4 | 515.7 | +3.4% | +60.3% |
```

The sidecar stored `item="rmb/bbl", unit=533.4, price_current=515.7, price_previous="+3.4%"`
- the whole row shifted one column RIGHT and the item label **lost**. Root cause: the parser
assumed every row carries a leading category cell. That is true for the BUNKERS block
(`<category>|<item>|<unit>|...`) but false for OIL & GAS / AGRICULTURAL / COAL / IRON ORE &
STEEL, which are `<item>|<unit>|...`. Three further faults fell out of the same code path:

1. **the branch gate matched the word "category"**, and the markdown renders the commodity
   *charts* as `| Category | Date | Value |` tables - so **chart points were parsed as prices**
   (`item="Jul-20"`, `unit=380`, empty values). 1,297 of 2,319 rows were this junk;
2. for the eras whose price table header is `| BUNKERS | Unit | <d> | <d> | W-o-W | Y-o-Y |`
   (no "category"/"item" in it) the branch never fired, so the real commodity table fell through
   to the **freight-benchmarks** branch and was filed there as `sector="DRY_BULK"` with shifted
   fields (`rate_current="usd/t"`, `unit="Rotterdam"`);
3. the same block can appear twice in the restored cover-to-cover markdown, double-counting rows.

## The fix

`scripts/extract/publishers/run_banchero_world_class_llama.py`, commodity branch only:

* **anchor on the UNIT cell, never on a column index** (`^[A-Za-z]{2,4}/[A-Za-z0-9]{1,8}$`);
  the item is the nearest non-empty cell to its left, the values are the two cells to its right.
  This is layout-independent across all four shapes the publisher uses;
* gate on `"unit" + "w-o-w"`, **not** on the word "category" - which excludes the chart tables;
* take the block name from the table header, else from the markdown heading context
  (`## OIL & GAS`), else from a real `Category` column; a row with no unit cell is a banner;
* require the current value to be numeric, which drops chart-axis tick rows by content;
* dedupe rows identical in every field within one document.

Rebuilt from the **cached markdown** (244 sidecars) and re-stacked - **no API spend** (the
banchero LlamaParse account is still out of credits).

## Measured, before -> after

| measure | before | after |
|---|---|---|
| `bancosta_commodities_series.csv` rows | 2,319 | **8,435** |
| rows whose `unit` is a NUMBER (shift signature) | 1,285 | **0** |
| rows with a `%` sitting in `price_previous` | 611 | **0** |
| rows with an empty `price_current` | 273 | **0** |
| chart-axis junk rows (item numeric / `Jul-20`-shaped / empty value) | 984 | **0** |
| exact duplicate rows | 106 | **0** |
| `category = GENERAL` (block name not resolved) | 1,297 | **33** (3 docs) |
| `bancosta_freight_rates_series.csv` rows | 25,715 | **20,329** |

`bancosta_ffa_series.csv` was **not** changed (7,659 rows, byte-identical): its values are
faithful, and "fixing" a publisher restatement would corrupt it.

## Controls

* **Value control, against the rendered page.** For `2022_W02` page 12 the four OIL & GAS /
  bunker rows were compared to the printed text: `Crude Oil ICE Brent usd/bbl 86.1/81.8`,
  `Crude Oil Shanghai rmb/bbl 533.4/515.7`, `Nat Gas Henry Hub usd/mmbtu 4.37/3.83`,
  `Gasoil ICE usd/t 749.3/712.5` - **4/4 exact**.
* **Baseline control.** The unmodified parser reproduces the on-disk `.tables.json` byte-exact
  from the on-disk markdown, so every diff is attributable to this change.
* **Series control.** After the rebuild + restack, **2 of 132 series CSVs changed**
  (`bancosta_commodities`, `bancosta_freight_rates`); the other **130 are byte-identical**.
* **No legitimate freight row was lost.** In `2021_W26` every genuine sector count is unchanged
  (CAPESIZE 6, PANAMAX 6, SUPRAMAX 19, DIRTY_TANKER 28, CLEAN_TANKER 27); the only rows that
  left `freight_benchmarks` are the mis-filed commodity ones carrying `sector="DRY_BULK"` and
  shifted values. Same for `2023_W12`.
* **Coverage gain, not just cleanliness.** Documents from 2023 and 2024 previously yielded
  **0** commodity rows; they now yield 35 each.

## Still open in this source (measured, NOT fixed)

1. **`bancosta_ffa_series.csv` - 93 rows whose `tenor` is a currency pair** (`CNY/USD`,
   `JPY/USD`, `KRW/USD`, `USD/EUR`): currency rows mis-filed into the FFA block.
2. **`bancosta_ffa_series.csv` - 60 rows with a `%` in `rate_previous`** (32 of them from
   `2026_W19`, the rest 4 each from ~7 documents): a one-column shift in that document's FFA
   table, the same class as the commodities defect.
3. **`bancosta_freight_rates_series.csv` - 33 numeric `unit` values and 80 `DRY_BULK` rows**
   remain (0.4% of the file) - a residue of the same mis-filing in eras not yet checked.
4. The 2026 markdown itself is degraded in places (`**tterdam**` for `**Rotterdam**`), i.e. a
   source-markdown defect, not a parser one.

## Note on display value

`index.html` references `bancosta` only as a **search keyword**, never as a data source, so
these series are not rendered in the app. The benchmarks they carry (bunkers, Brent/WTI, coal,
iron ore, grains) are largely restatements of public data already held in `data/bunkers/`,
`data/macro/commodities_monthly.csv` and `data/commodities/`. The fix was still worth doing -
the file is published as a deliverable and was recorded "Verified" while 55% of its rows were
shifted - but it should not be treated as new data.

## Reproduce

```
python3 scratch/bancosta_control.py        # baseline: unmodified parser == on-disk sidecars
python3 scratch/bancosta_full_compare.py   # 244-doc before/after, per-key control
python3 scratch/bancosta_fb_check.py       # freight_benchmarks: what moved, sector by sector
python3 scratch/bancosta_value_check.py    # 2022_W02 values vs the printed page
python3 scratch/bancosta_rebuild.py        # rebuild the 244 sidecars from cached markdown
python3 scripts/extract/publishers/stack_banchero_series.py
```
