# ism - the merged series agree at the median but 17.5% of repeat readings do not (found 2026-09-28)

Status: **defect characterised, not yet fixed.** Unlike intermodal's chart series, ism's are
NOT held data (the legend audit found 0 held / 0 proprietary swatches for ism but its route
freight rates are the publisher's own), so this fix is worth doing.

## Measured

Agreement gate on the merged files, from their own `n_reports` / `min_value` / `max_value`:

| file | multi-report keys | median spread | p90 | within 2% |
|---|---|---|---|---|
| ism_handy_freight_series.csv | 6,176 | 0.223% | 20.59% | 69.1% |
| ism_coaster_freight_series.csv | 6,802 | 0.341% | 43.34% | 74.3% |

The median is good; the tail is not. Of 12,978 multi-report rows, **2,269 (17.5%) disagree by
more than 10%**. The offending rows are concentrated in 57 labels; the top one alone is
735 rows:

| rows >10% spread | series label |
|---|---|
| 735 | `% of freight costs in CFR price` |
| 121 / 112 / 99 / 94 / 88 | `2022 year` / `2025 year` / `2024 year` / `2021 year` / `2023 year` |
| 84 | `Supramax, ECSA - Cont (bss dely APS)` |
| 82 | `Freight rate, billets, 5-6,000t, Novo - Marmara, $/t` |

## Root cause: the key omits the panel's ENTITY

The merge keys on `(segment, chart_title, series_label, date)`. For a chart whose title is
`Ukrainian corn: weight of freight in CFR Egypt price`, one report (2024 W17) holds:

```
label=% of freight costs in CFR price        axis=secondary  range 12.3..26.8
label=Ukr corn, calc. CFR Egypt, $/t         axis=primary    range 193.0..265.0
label=Freight rate, corn, 25-30,000t, Odesa  axis=primary    range 25.1..65.3
```

and four weeks later (2024 W21) the SAME title holds:

```
label=% of freight costs in CFR price        axis=secondary  range 4.5..12.3
label=French wheat, calc. CFR Algeria, $/t   axis=primary    range 232.1..298.0
label=Freight rate, wheat, 25-30,000t, Rouen axis=primary    range 12.3..34.3
```

The publisher reuses the panel and its title but plots a DIFFERENT commodity/route; the
identity lives only in the sibling labels (`Ukr corn, calc. CFR Egypt` vs `French wheat,
calc. CFR Algeria`). `% of freight costs in CFR price` names a MEASUREMENT, not an entity, so
keying on it fuses Ukrainian corn-to-Egypt with French wheat-to-Algeria and the spread
explodes - the same class of error as the mineral-spec table where one row's five columns
became one "series".

## Proposed fix (next run, one source)

Key the series on `(panel entity from the sibling 'calc. CFR <place>' / route label,
measurement label, date)` instead of on the chart title; where no sibling identifies the
entity, emit the value **unlabelled** rather than under a guess (a wrong label is worse than a
missing one). Re-measure the same gate: the target is the ssy reference, ~1% median and
within 2% for the bulk of keys.

## Reproduce

```
python3 scratch/measure_agreement.py   # the gate on both ism files
python3 scratch/diag_ism.py            # worst keys, by label
python3 scratch/quant_ism.py           # 2,269/12,978 rows >10%
python3 scratch/diag_ism2.py           # the sibling-label evidence above
```


---

# RE-MEASURED 2026-09-30 11:1x IST - the tail is SMALLER than this doc records, and it is NAMED

The re-key fix (2026-09-28, `docs/ism_series_fix_verdict.md`) moved this far more than the
section-2 table of `docs/series_verification_ledger.md` records. Measured today with the ledger's
own instrument (`scratch/measure_agreement.py`) and re-attributed row by row
(`scratch/ism_tail_now.py`), read-only:

| file | multi-report keys | p50 | p90 | within 2% | >10% spread | this doc said |
|---|---|---|---|---|---|---|
| ism_handy_freight_series.csv | 6,169 | 0.181% | 11.76% | 74.1% | 723 = 11.7% | p90 20.59%, 69.1%, 17.5% |
| ism_coaster_freight_series.csv | 5,927 | 0.293% | 5.67% | 83.7% | 476 = 8.0% | p90 43.34%, 74.3%, same |

## What is left, by label

The `20XX year` labels dominate BOTH files - 285 of handy's 723 (39%) and 304 of coaster's 476 -
followed by specific route labels (`Supramax, ECSA - Cont (bss dely APS)` 83; `Freight rate,
billets, 5-6,000t, Novo - Marmara, $/t` 65). Handy's tail is 286 rows of `$/day` against 391 of `$/t`.

**Leading hypothesis, to be tested on a page before any fix:** the `20XX year` families are a
multi-year OVERLAY - the chart plots 2021..2025 as separate lines against the same x-axis - so a
series keyed on `(date, '2022 year')` fuses the 2022 line of a 2023 report with the 2022 line of a
2026 report, which are different points on the publisher's own axis. That makes the residual a KEY
defect (the overlay year belongs in the point's date, not in the series name), not an extraction
error - and it explains why the earlier fix removed the generic part of the tail and left this
block. **Read one such chart page's legend and axis first; do not re-key from this note alone.**
