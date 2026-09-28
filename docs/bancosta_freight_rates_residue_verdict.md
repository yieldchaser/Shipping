# bancosta_freight_rates - the DRY_BULK residue: FIXED and verified

**Run 2026-09-29 02:3x.** Parser: `scripts/extract/publishers/run_banchero_world_class_llama.py`
(`extract_structured_tables_from_md`). Rebuilt from the **cached** markdown - no LlamaParse spend.
Stack: `scripts/extract/publishers/stack_banchero_series.py`.

## What was assigned (measured by the previous run)

`bancosta_freight_rates_series.csv` held **80 rows / 10 docs** with `sector=DRY_BULK` that are not
dry-bulk freight benchmarks, in five classes. Re-measured this run with `scratch/bancosta_fb_classes.py`
before touching anything - **identical to the brief**: FX 8/2, chart rows 25/5, commodity-with-unit
13/2, container TC 24/2, banners 10/3.

## Root cause (one sentence)

Branch 11 ("Freight Benchmarks") gates on the **header string alone**
(`w-o-w`/`y-o-y` + a unit or a date token) and assigns `sector` from `ctx` alone, so every table the
specific branches failed to claim landed there as DRY_BULK. The specific branches failed because their
gates were **ctx-only**, and the heading tracker does not carry the block name: the VHSS table sits under
`CONTAINERSHIP MARKET`, the FREIGHTOS table has no heading of its own, and the 2021 FX table's heading is
`INTEREST RATES / CURRENCIES` (branch 9 looked for `EXCHANGE RATES`).

## The fix - content anchors, never ctx or geometry

1. **Branch 9 (FX)** now requires a real `XXX/YYY` row, and its ctx test accepts `CURRENC`
   (the 2021 heading is `INTEREST RATES / CURRENCIES`).
2. **Branch 7 (VHSS)** gained a row anchor `^(ConTex|NNNN teu)`. The table's own header is `VHSS` but
   the heading is `CONTAINERSHIP MARKET`.
3. **Branch 8 (FREIGHTOS)** also accepts `freightos` in the table's own header.
4. **Branch 10 (commodity)** now also fires when the unit sits **inside each row** - the 2023/2024 era
   prints `| Benchmark | 14-Jun | 7-Jun | W-o-W | Y-o-Y |` with the unit cell in the row.
5. **New branch 10c** claims the commodity **chart** tables (`| Commodity / Fuel | ... |` with no Unit
   column) and routes them to `chart_series`; all-empty banner rows are dropped, not published.

## Measured result (before -> after)

| artefact | before | after | delta |
|---|---|---|---|
| freight_rates rows | 20,329 | **20,249** | **-80** |
| freight_rates `sector=DRY_BULK` | 80 | **0** | -80 |
| bancosta_fx_series rows | 968 | **976** | +8 |
| bancosta_vhss_series rows | 3,413 | **3,427** | +14 |
| bancosta_commodities_series rows | 8,435 | **8,447** | +12 |
| sidecar `freightos_index` rows | 2,261 | **2,271** | +10 |
| sidecar `chart_series` rows | 38,204 | **39,425** | +1,221 |

`freight_rates` now carries no DRY_BULK sector at all (CAPESIZE 2,134 / PANAMAX 2,159 /
SUPRAMAX 4,419 / CLEAN_TANKER 4,924 / DIRTY_TANKER 6,613). DRY_BULK was only ever the misroute fallback.

## Controls

* **Function-level control** (original `HEAD` parser vs fixed parser, all 244 cached docs, `scratch/bwc_orig.py`):
  the **only** key that lost rows anywhere is `freight_benchmarks`, on **exactly the 10 named docs**,
  **-80 rows total**. Every other change in every other doc is additive. No doc lost a single row from
  `reported_sales`, `ffa_assessments`, `newbuilding_prices`, `demolition_assessments`,
  `secondhand_assessments`, `container_fixtures`, `currencies`, `vhss_contex`, `commodity_prices`
  or `chart_series`.
* **Series-CSV md5 control**: **4 of 10** bancosta series CSVs changed (freight_rates, fx, vhss,
  commodities); **6 byte-identical** (sales, ffa, newbuilding, demolition, secondhand_matrix,
  container_fixtures).

## Verified against the source pages (LlamaParse read is ground truth - the PDF text layer is ciphered)

No vision tool in this session, so every value was reconciled against the document's own cached
page text, cell by cell:

* 2021_W46 FX - page prints USD/EUR 1.13 | 1.15, CNY/USD 6.39 | 6.38, JPY/USD 113.98 | 113.85,
  KRW/USD 1,187 | 1,179 -> **all four exact** in `bancosta_fx_series.csv` (W47 likewise).
* 2022_W43 VHSS - page prints ConTex index 974 | 1,093, 4250 teu 31,810 | 35,850,
  1100 teu 12,727 | 14,275 -> **all exact** in `bancosta_vhss_series.csv` (7 rows).
* 2022_W43 FREIGHTOS - page prints FBX index 3,329 | 3,369, China-WCNA 2,494 | 2,470,
  China-ECNA 5,644 | 5,689 -> **all exact** in the sidecar `freightos_index` (10 rows).
* 2024_W24 commodity - page prints Steam Coal Richards Bay usd/t 110.1 | 110.1,
  Iron Ore SGX 62% 107.5 | 108.7, Coking Coal Australia SGX 252.0 | 251.0 -> **all exact** in
  `bancosta_commodities_series.csv` under categories COAL / IRON ORE & STEEL.
* 2026_W38 VHSS - page prints ConTex index 1,646 | 1,644, 4250 teu 59,300 | 59,250 -> **exact**.

## The +1,221 chart_series rows are a second, measured fix, not a side effect

Making branch 9 content-anchored (needed so the 2021 FX table is claimed) also stopped it claiming the
FX heading's own **chart** table. Branch 9 only ever emits `XXX/YYY` rows, so any table it claimed without
such a row was read and **silently discarded**. Example: 2026_W24 `## JPY/USD EXCHANGE RATE` /
`| Date | Value |` (Jan-21 103, Mar-21 108, ...) - 4 rows dropped before, present now as
`chart_series` with `chart_name=EXCHANGE RATES__JPY/USD EXCHANGE RATE`. 194 docs recover rows; the
recovered rows were eyeballed and are genuine date/value chart series.

## STILL OPEN in this file (measured this run, NOT fixed - next targets)

1. **Chart tables published as container indices.** The same root cause in branches 7/8: they claim the
   chart tables under the VHSS / FREIGHTOS headings and read them positionally.
   Measured: `freightos_index` **502 of 2,271 rows** across 145 docs (456 with a numeric "unit",
   40 empty, 6 dates) and `vhss_contex` **1,713 of 3,427 rows** across 218 docs
   (1,641 numeric unit, 57 dates, 15 other) - e.g. segment `Jul-20`, unit `8000`.
   Criterion: the unit cell is neither a unit token nor a period label.
2. **A second residue in `freight_rates` itself: 125 rows / 52 docs** whose `unit` cell is not a unit.
   Three shapes: (a) the leaked **sub-header row** of a 2022-2026 tanker table
   (`AFRAMAX | Unit | 3-Jul | 26-Jun | W-o-W | Y-o-Y` published as a data row) - the `category unit`
   header shape, 25 firings corpus-wide; (b) the 2021 era's 7-column
   `Category | Name | Unit | ...` table, where the label spans two cells so every row is one column
   left - 28 rows on 2021_W46 alone; (c) empty rows (`AFRAMAX | | | |`).
   **These pre-date this fix** - the function-level control proves this run removed exactly 80 rows and
   added none.

## Reproduce

```
# rebuild sidecars from the cached markdown (no API spend)
/c/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe scratch/bancosta_rebuild.py
python3 scripts/extract/publishers/stack_banchero_series.py
python3 scratch/bancosta_fb_classes.py      # prints an empty Series -> 0 DRY_BULK residue
```
