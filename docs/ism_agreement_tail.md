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

---

# RE-MEASURED 2026-09-30 11:4x IST - THE RESIDUAL IS THE PUBLISHER'S OWN AXIS, NOT OUR PARSE

The previous section left one instruction: *name the failing REPORTS and read them*. Done - two of
them were read against their own rendered pages, and the residual is **not** an extraction defect.

## 1. Who actually disagrees (census over the raw charts, restricted to CALENDAR-YEAR overlays)

A cross-report comparison is only valid where the week label names a real date, so the census was
restricted to charts whose `x_scale` is `first_label=1, last_label=52` and whose series label matches
`^(19|20)\d\d year$`. `scratch/ism_tail_census2.py`, read-only:

| measured | value |
|---|---|
| year-line keys | 17,928 |
| keys seen in >= 2 reports (comparable) | 4,489 |
| rows disagreeing with the cross-report median by >2% | **1,231 = 8.5%** |
| reports never an outlier | **65 of 84** |

The tail is report-level, not label-level: each year label carries 8-10% (`2022 year` 314/3,096,
`2024 year` 304/3,460, `2023 year` 284/3,549, `2025 year` 167/1,965, `2021 year` 142/1,716,
`2026 year` 20/663). The reports carrying it, measured:

`ism_2024_W41` 139/286 (49%) · `ism_2023_W36` 127/140 (91%) · `ism_2023_W38` 127/140 (91%) ·
`ism_2026_W19` 121/122 (99%) · `ism_2023_W27` 120/125 (96%) · `ism_2025_W44` 114/268 (43%) ·
`ism_2025_W41` 111/265 (42%) · `ism_2026_W06` 81/199 (41%) · `ism_2024_W50` 55/266 (21%) ·
`ism_2024_W48` 53/110 (48%) · `ism_2023_W50` 48/204 (24%) · `ism_2024_W01` 48/154 (31%)

## 2. CONTROL 1 - the drawn path, recomputed by hand (ism_2024_W42)

`Wheat / corn, 5-6,000t, Izmail / Odesa - Bari / Ortona`, page 1. The page prints its y labels as
positioned text (`100` y292.9 · `90` y310.2 · `80` y327.8 · `70` y345.4 · `60` y362.8 · `50` y380.4 ·
`40` y398.0 · `30` y415.3 · `20` y432.9 -> 17.5 pt per 10 units) and its gridlines at
419.5/402.2/384.6/367.0/349.7/332.1/314.5/297.2 with the axis line at 437.1 = value 20. The grey
`2022 year` path (`pymupdf get_drawings`, colour 0.651) starts `(326, 393.4)` -> **45.0** and reaches
`(366, 407.4)` -> **37.0**; the CSV for that document says week 1 = **45.0** and week 10 = **37.0**.
Faithful.
Also measured on that page: the grey path is drawn as ONE path with two subpaths (x 326-366 and
x 460-553 = weeks 1-10 and 31-52), so the "hole" the CSV shows is the publisher's own line break
(Mar-Jul 2022, the Odesa blockade), not a dropped line.

## 3. CONTROL 2 - the page's own labels vs the extractor's labels (the real cause)

`Corn / soybeans, 10,000t, POC - Alexandria / Beirut`, page 1, read as positioned text:

| doc | y labels printed ON THE PAGE (top -> bottom) | extractor's `raw` | CSV value, 2025 line, wk 10/16/20/30 |
|---|---|---|---|
| ism_2026_W19 | 45,40,35,30,25,20,15,10 | 45,40,35,30,25,20,15,10 | 18.5 / 18.0 / 18.0 / 18.8 |
| ism_2026_W23 | **50,45,40,35,30,25,20,15** | 50,45,40,35,30,25,20,15 | **23.0 / 22.5 / 22.0 / 23.0** |

The extractor reproduces each page's own labels exactly, and the two pages label the SAME plot box
with axes one 5-unit step apart (top label at y 673.7 vs y 675.7 - 2 pt apart) while the plotted line
sits in the same place. An independent calibration fitted **only from each page's printed labels**
(`scratch/ism_page_control.py`, extractor code not reused) reproduces the CSV exactly: W19
18.6/18.0/18.0/18.8, W23 2024 = 36.5/29.5/23.5/22.0 and 2025 = 23.0/22.5/22.0/23.0.
So the ~4-5 unit disagreement between issues is a **publisher-side axis label shift**, and no
re-extraction of the PDF can remove it.

## 4. The one lever that IS ours (measured, NOT applied)

The pooled value is picked at the *edge* of the cluster instead of the consensus. Measured on the
merged files: of the multi-report rows whose cluster spreads >2%, the chosen value sits at `min` or
`max` on **1,139 / 1,598 (71%)** of `ism_handy` and **635 / 969 (66%)** of `ism_coaster`; among the
`n_reports >= 3` subset, **925 / 1,384** and **363 / 697**. Choosing the reading closest to the
cluster median (recording the dissent) would cut the cross-report spread on those rows. That changes
~2-8% of rows and was deliberately NOT written this run - do it as a trialled change with the
agreement gate re-measured before/after, never by hand-editing the CSV.

## 5. Shipped this run (code only)

`data/extracted/md/ism/` was reorganised into `2023/ 2024/ 2025/ 2026/` subdirectories at 11:35 today
(by a parallel process, not this run), which silently broke the stacker: `run_ism_series.py` globbed
`ISM_DIR.glob("*.charts.json")` non-recursively and would have found **0** charts and rewritten both
CSVs empty. Fixed to `rglob`, and PROVEN by re-running it: it found all **114** charts and reproduced
both files **byte-identically** (`ism_coaster_freight_series.csv` sha256 `021d2a5f7498...`,
`ism_handy_freight_series.csv` sha256 `85bf1052b538...`, unchanged). The same latent breakage was
fixed in `normalize_xclusiv_md.py` (top-level `*.md` = 0, recursive = 271) and
`build_banchero_series.py` (0 vs 247). Note for future audits: this dir tree is shared - another
agent moved 114 files while this run was measuring them, so always glob recursively.
