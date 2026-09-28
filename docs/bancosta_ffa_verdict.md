# bancosta FFA / FX tier - 5 mis-parse defects found, fixed and verified

**Date:** 2026-09-29 · Run: unattended cron (source-by-source)
**Parser:** `scripts/extract/publishers/run_banchero_world_class_llama.py`, FFA branch + FX branch
**Rebuilt from the CACHED LlamaParse markdown - no API spend** (244 sidecars via
`scratch/bancosta_rebuild.py`, then `scripts/extract/publishers/stack_banchero_series.py`).

## What the previous run left open

`docs/bancosta_commodities_verdict.md` closed with three measured leftovers in this source:
"93 FFA rows whose `tenor` is a currency pair; 60 FFA rows with a `%` in `rate_previous`
(32 from 2026_W19); 33 numeric `unit` values and 80 `DRY_BULK` rows left in freight_rates."
Re-measured here on the current files, the first two counts do not reproduce as stated, and the
defect behind them is **bigger and has five distinct causes**, all in the FFA branch.

## The root cause: the FFA branch keyed on `ctx` alone

`ctx = f"{current_h1} / {current_h2} / {current_h3}".upper()`. The heading tracker keeps
`h1 = "DRY BULK FFA ASSESSMENTS"` while `h2/h3` move on, so the branch condition
`elif "FFA" in ctx or "PREMIUM" in header_str:` fired on tables that are **not** FFA
assessments. Measured by dumping every FFA-branch firing across the corpus:
**1,881 tables / 244 docs**. Header signatures:

| tables | header | verdict |
|---|---|---|
| 861 | `date value` | legitimate FFA forward-curve chart series |
| 605 | `tenor unit <d> <d> w-o-w premium` | legitimate assessments |
| 212 | `category unit <d> <d> w-o-w premium` | legitimate assessments |
| 140 | `route / benchmark unit <d> <d> w-o-w premium` | legitimate assessments |
| 21 | `capesize forward curve (usd/day) capesize ...` | doubled header, emitted nothing |
| **7** | **`currencies <d> <d> w-o-w y-o-y`** | **the EXCHANGE RATES table - misfiled as FFA** |
| **8** | **`category date`** | chart table |
| **5** | **`category value`** | chart table |
| **2** | **`category <5 dates>`** | chart table - curve titles published as tenors |
| **1** | **`route / benchmark jpy/usd exchange rate`** | chart table |
| **4** | **`currency <d> <d> w-o-w premium`** | 2026_W19 FFA table with NO tenor column |

## The five defects and what each cost

1. **EXCHANGE RATES tables filed as FFA (7 docs, 28 rows).** In the 7 issues where the FX table's
   `ctx` still carried the FFA `h1`, the FFA branch swallowed it *before* the FX branch could see
   it (`elif` order). The rows were stored with a one-column shift - `tenor="CNY/USD"`,
   `unit=6.90`, `rate_current=6.87`, `rate_previous="+0.4%"`, `change_wow="+6.9%"` - and, because
   the FX branch never ran, those 7 documents were **entirely absent from
   `bancosta_fx_series.csv`**. Confirmed: 236 of 244 md documents carry a `CURRENCIES` table and
   exactly 7 were missing from the FX CSV.
2. **Chart tables published as assessments (16 tables).** `| Category | Mar-24 | Sep-24 | ... |`
   and `| JPY/USD EXCHANGE RATE | Feb-22 | Jun-22 | Oct-22 |` rows are chart points. Nine of them
   surfaced in the CSV as tenors `CAPESIZE FORWARD CURVE (USD/DAY)` / `JPY/USD EXCHANGE RATE`.
3. **All-empty section rows (4).** `| **Capesize** | | | | | |` inside a real FFA table was emitted
   as an assessment with every value blank (`2024_W34`).
4. **A table with no tenor column (2026_W19, 32 rows).** LlamaParse returned
   `Unit | 11-May | 4-May | W-o-W | Premium` - the Tenor column is gone from the page read. A
   positional read shifted **every value one place**: `tenor="usd/day"`, `unit="43,753"`,
   `rate_current="41,899"`, `rate_previous="+4.4%"`, `change_wow="-3.1%"`.
5. **A transposed chart table in the FX branch (1 row).** The same heading also carries
   `| JPY/USD EXCHANGE RATE | Feb-22 | Jun-22 | Oct-22 |` / `| 110 | 120 | 150 | 130 |`, which the
   FX branch (keyed on `"EXCHANGE RATES" in ctx`) published as `currency_pair="110"`.

## The fix (content anchors, never geometry or ctx alone)

* FFA branch: route a table to `currencies` when its header is `currencies` **or every data row
  starts with an uppercase `XXX/YYY` pair** (uppercase on purpose - a rate *unit* is `usd/day`,
  and a case-insensitive test matched the unit, which initially sent 2026_W19's whole FFA table
  into the FX tier). Require a `premium` column for an assessment table; a table under the FFA
  heading without one is a chart table and its rows go to `chart_series`. Handle the
  `currency`-header variant (no tenor column) by reading cell 0 as the unit. Skip all-empty rows.
* FX branch: accept only rows whose first cell is a real `XXX/YYY` pair.
* Thresholds are derived from the table (its header, its row shape), not from a coordinate, so
  they survive the era changes documented in `docs/OVERNIGHT_STATE.md`.

## Measured result

| measure | before | after |
|---|---|---|
| `bancosta_ffa_series.csv` rows | 7,659 | **7,618** |
| currency-pair `tenor` rows | 28 | **0** |
| curve-title `tenor` rows | 9 | **0** |
| blank-`unit` assessment rows | 4 | **0** |
| 2026_W19 rows read one column left | 32 | **0** (32 corrected, verbatim 32/32) |
| `bancosta_fx_series.csv` rows | 941 | **968** |
| docs missing from the FX tier (of 236 with a CURRENCIES table) | 7 | **0** |
| junk `currency_pair` values | 1 (`110`) | **0** |

Row accounting for the 41 removed FFA rows, by class: 28 FX + 9 chart-title + 4 empty.
Per-document ffa deltas: the 7 FX docs and `2024_W34` 36 -> 32; `2025_W11` 41 -> 32;
`2023_W05` 36 -> 32; `2026_W19` 32 -> 32 (values corrected).

## Verification

* **Value grounding.** The 28 recovered FX rows are the printed table: `| USD/EUR | 1.00 | 1.00 |`
  etc. **28/28 verbatim in the source page text** (3 of them carry `**bold**`/`~~strike~~` markup in
  the md - the numbers are exact). The 32 corrected 2026_W19 rows are **32/32 verbatim** in the
  page text: `| usd/day | 43,753 | 41,899 | +4.4% | -3.1% |`.
* **Control (same document, before vs after).** 19 of 245 sidecars changed, and the diff is
  confined to **three keys only**: `ffa_assessments` (10 docs), `currencies` (7), `chart_series`
  (13 - the recovered chart tables). No other key in any sidecar moved.
* **Series control.** **8 of 10** bancosta series CSVs are **byte-identical** (md5); only
  `bancosta_ffa_series.csv` and `bancosta_fx_series.csv` differ, and every other tier
  (sales 4,567 / freight 20,329 / newbuilding 1,952 / demolition 1,282 / secondhand 1,911 /
  container 922 / vhss 3,413 / commodities 8,435) has the same row count as before.
* **Scripts:** `scratch/bancosta_ffa/{diag,dump_ffa,analyze,ffa_contam,ffa_rowdiff,verify_fx,
  final_verify}.py`. The dump hook is `BC_DUMP_FFA=<path>` (inert unless set).

## Left as printed (NOT repaired, deliberately)

`banchero_costa_2025_W30` prints its FFA tenors as **`ul-25`, `lug-25`, `iep-25`, `oct-25`,
`ec-25`, `1 26`, `2 26`, `3 26`** - 32 rows. The garbled labels are in LlamaParse's own raw
read (`data/extracted/llamaparse_banchero_v2/`), i.e. they come from the page, not from this
pipeline. Mapping them to Jul/Sep/Oct/Dec/Jul and Q1-Q3 26 would be a guess, and a wrong label
is worse than a missing one, so they are left verbatim. Recovering them needs a re-parse
(credits) or vision.

2026_W19's 32 corrected rows carry `tenor = ""`: the tenor column does not exist in the page
read, so the tenor is genuinely unknown. The values are exact; only the label is missing.

## Not touched / still open in this source

* `freight_rates` residue (numeric `unit`, `DRY_BULK` rows) - separate branch (11), not measured
  to closure in this run.
* `banchero_costa` LlamaParse is still credit-blocked (HTTP 402) - only the user can rotate the key.
