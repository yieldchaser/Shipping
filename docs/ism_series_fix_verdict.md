# ism merged series: key fix + multi-year axis fix (measured 2026-09-28)

Status: **FIXED and re-measured.** Supersedes the "not yet fixed" status in
`docs/ism_agreement_tail.md` and item 5 of `docs/series_verification_ledger.md`.
No re-extraction was needed - the fix is entirely in the merger
`scripts/extract/publishers/run_ism_series.py`, which rebuilds both CSVs from the
112 existing `.charts.json` in ~6 s.

## Why it was worth doing

ism is a **charts-only** source (no tables) and its route freight rates are the
publisher's own - they are NOT held data in any feed. Unlike intermodal's
superseded Baltic chart series, this data is the deliverable.

## The two defects

### 1. The key omitted the panel ENTITY (the documented defect)
The merge keyed on `(segment, chart_title, series_label, date)`. The chart title
is not a stable entity:

* the SAME cargo appears under **different** titles - `Russian billets: weight of
  freight in CFR Marmara price` and `Russian steel billets: ...`;
* one title is **reused across different cargoes** - `Ukrainian corn: weight of
  freight in CFR Egypt price` (2024 W17) vs the same title carrying
  `French wheat, calc. CFR Algeria` four weeks later.

The identity lives in the **sibling labels**. `chart_entity()` now derives it
from the chart's own siblings (preferring a `CFR` label, falling back to a
`Freight rate ...` label), and the key became
`(segment, entity or title, series_label, date)`.

### 2. Multi-year COMPARATIVE charts collapsed onto one year (found by measurement)
This one was NOT in the earlier diagnosis, and it was the bigger of the two.

A comparative chart plots several years on **one repeating 52-week x axis**. The
holiday special's Aussie-iron-ore chart has 154 points and its own tick labels
read `1,9,17,...,49 | 5,13,...,45 | 1,9,...` - a 52-point period, i.e.
52 + 52 + 50 = 2021, 2022, 2023. The merger inferred the year from the week
number alone (`rep_yr - 1 if wk > rep_wk else rep_yr`), so all three years
mapped to the same ISO date and 2021/2022/2023 values were fused into one
"series".

Proof (the same chart, same week, three values):
```
key ('Coaster','Aussie iron ore, CFR China','% of freight costs in CFR price','2023-01-23')
values [3.9, 4.8, 12.5]   <- all three from ONE chart, ONE week, three years
```
That 124% "spread" is three different years, not a value error. The fix reads
the declared span from the title (`in 2021-2023`) and assigns
`year = first_year + index // 52`, with the 52-week period corroborated by the
chart's own tick pitch rather than assumed.

### 3. (bonus) the `%` rows carried the wrong unit
`unit` was inferred from the chart title, which never contains `%`, so all 2,356
`% of freight costs in CFR price` rows were labelled `$/t`. Unit is now taken
from the series label.

## Measured result (the same agreement gate, before vs after)

| file | rows before | rows after | multi-report rows | p50 | p90 | within 2% | rows >10% |
|---|---|---|---|---|---|---|---|
| ism_coaster_freight_series.csv | 13,281 | **12,319** | 6,802 -> 5,876 | 0.341% -> **0.298%** | 43.34% -> **6.06%** | 74.3% -> **83.4%** | 1,233 -> **481** |
| ism_handy_freight_series.csv | 18,833 | **17,629** | 6,176 -> 6,116 | 0.223% -> **0.189%** | 20.59% -> **11.83%** | 69.1% -> **73.9%** | 1,036 -> **697** |
| **combined** | 32,114 | **29,948** | - | - | - | - | 2,269 -> **1,178 (-48%)** |

The single largest offender, `% of freight costs in CFR price`, went
**735 -> 100 bad rows (-86%)**. Coaster p90 fell from 43.3% to 6.1%.

## What is still wrong (measured, NOT fixed)

The residual 1,178 rows are a **different** defect class, localised but not
repaired:

1. **`20XX year` labels (~514 rows, 44% of the residual).** These are the
   multi-year comparative charts whose series are already named by year, so the
   key is right. Two reports disagree on the same (panel, year, date) because
   one report's chart is drawn on a **different axis**. Example, route
   `Urea, 5-6,000t, Damietta - Seville (2500x/2500x), $/t`: every report gives
   the `2022 year` range `40.5..58.5` with tick labels
   `75,65,55,45,35,25,15`, while `2023_W38` alone gives `27.0..52.6` with ticks
   `71,64,57,50,43,36,29,22,15`. The outlier is a specific report, not the key.
2. **TCT / route series**: `Supramax, ECSA - Cont (bss dely APS)` 84/222,
   `Handysize, BlSea - EMed (bss dely psg Canakkale)` 72/150,
   `Freight rate, billets, 5-6,000t, Novo - Marmara, $/t` 64/168.

A wrong value is worse than a missing one, so no outlier was dropped or
"repaired" by position.

## Method note (stated plainly)

This cron session has **no image/vision tool**. "Render and look" was therefore
substituted with: reading the chart's own tick labels and axis metadata out of
`.charts.json`, tracing every disagreeing value back to its source chart file
(`scratch/ism_keytrace2.py`), and confirming the 52-week period from the tick
labels themselves. That is a real check, but it is **not** a look at a rendered
page, and it should be repeated visually before this source is called perfect.

## Reproduce

```
python3 scripts/extract/publishers/run_ism_series.py   # rebuild both CSVs (~6s)
python3 scratch/ism_gate_cmp.py                        # before/after agreement gate
python3 scratch/ism_by_label.py                        # worst labels
python3 scratch/ism_keytrace2.py                       # which chart produced a key
python3 scratch/ism_pct_axes.py                        # the 108 %-charts' axes (all verified)
```
