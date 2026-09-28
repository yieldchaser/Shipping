# Series verification ledger (measured 2026-09-28, unattended run)

Scope: the 98 stacked series CSVs + 1 workbook in `data/extracted/series/` that
`docs/EXTRACTION_REGISTER.md` counts as the finished product (273,254 rows). This run did not
re-extract anything; it tested the artefacts against the register's claims and against the
programme's own independent check.

## 1. Row counts: the register matches the artefacts

98 CSVs, **273,254 data rows**, exactly the register's declared total. Every per-file count in
the register's inventory matches the file it names. (Claim verified, not assumed.)

## 2. Cross-report agreement (the only independent proof of a merge)

Computed from each merged file's own `n_reports` / `min` / `max` columns:

| file | multi-report keys | median spread | p90 | within 2% | verdict |
|---|---|---|---|---|---|
| ssy_capesize_index_series.csv | 5,827 | **0.264%** | 2.69% | 87.4% | PASS - reference implementation |
| ism_handy_freight_series.csv | 6,176 | 0.223% | 20.59% | 69.1% | tail defect, see `docs/ism_agreement_tail.md` |
| ism_coaster_freight_series.csv | 6,802 | 0.341% | 43.34% | 74.3% | tail defect, same |
| intermodal_baltic_tc_series.csv | 20,186 | **59.34%** | 141.3% | 3.2% | FAIL - see `docs/intermodal_baltic_series_verdict.md` |

The other 94 files carry one row per (key, date) and no repeat statistics, so this gate cannot
be run on them from the artefacts alone.

## 3. Continuity check (previous value vs the nearest prior issue)

An independent cross-report check available on the 11 files that carry a "previous" column:
the value labelled previous in issue N should equal the value labelled current in the nearest
earlier issue for the same key.

| file | prev rows | resolved | within 1% | median err |
|---|---|---|---|---|
| bancosta_freight_rates_series.csv | 25,518 | 24,104 | 87.4% | 0.00% |
| bancosta_fx_series.csv | 941 | 936 | 95.0% | 0.00% |
| bancosta_vhss_series.csv | 3,353 | 2,191 | 76.0% | 0.00% |
| bancosta_ffa_series.csv | 7,655 | 7,030 | 23.8% | 2.73% |
| bancosta_commodities_series.csv | 1,934 | 344 | 11.0% | 29.00% |
| intermodal_tc_rates_series.csv | 5,068 | 4,963 | 91.2% | 0.00% |
| intermodal_maritime_stocks_series.csv | 3,047 | 3,013 | 90.0% | 0.00% |
| intermodal_macro_series.csv | 3,641 | 3,624 | 49.0% | 1.04% |
| intermodal_newbuilding_prices_series.csv | 3,134 | 2,506 | 67.7% | 0.00% |
| carriers_indices_series.csv | 639 | 634 | 84.4% | 0.00% |
| carriers_tanker_tce_series.csv | 761 | 755 | 84.0% | 0.00% |

**Caveat, stated plainly:** the word "previous" does not mean the same interval in every
source (prior week, prior month, prior curve date). A low score is therefore a **candidate for
a per-source semantics check, not a proven defect** - bancosta_ffa and bancosta_commodities
are the two to check first. Six of eleven score 84-95% at 0.00% median error, which is
consistent with correct extraction and a correct key.

## 4. Defects found by this sweep

1. **intermodal chart series superseded** - 20,348 rows, held data, 25-53% off the feed.
   `docs/intermodal_baltic_series_verdict.md`.
2. **ism agreement tail** - 2,269 of 12,978 repeat readings (17.5%) disagree by >10%; the key
   omits the panel entity. `docs/ism_agreement_tail.md`.
3. **Exact duplicate rows** in 10 files (rows identical in every column):
   bancosta_commodities 106/2,319 · intermodal_indicative_values 75/2,409 ·
   intermodal_tc_rates 48/5,068 · bancosta_vhss 15/3,413 · bancosta_freight_rates 14/25,715 ·
   xclusiv_sales 5/5,713 · poten_top_charterers 2/755 · star_asia_deals 2/3,327 ·
   star_asia_ferrous_scrap 1/771 · carriers_sales 1/3,004. Each is a double count downstream.
4. **Fake dates `2026-00-00`** - 226 rows that parse as ISO but cannot be placed in time:
   intermodal_macro 92 · intermodal_maritime_stocks 72 · intermodal_bunkers 54 ·
   xclusiv_bulk_carrier_charts 8. A nulled date written as a zero month is worse than a blank.
5. **star_asia_deals_series.csv has two mis-typed date columns**: `arrival_date` is European
   `DD.MM.YYYY` (708 distinct values, e.g. `13.06.2025`), so any ISO-based join silently drops
   all 2,727 of them; `beaching_date` holds free-text STATUS, not dates - 901 rows read
   `AWAITING`, 24 `ARRESTED`, 17 `AWATIING` (the source's own typo).

## 5. Not verified / limits of this run

- No image/vision tool exists in the cron session, so "render and look" was substituted with
  the same-document text reconciliation (intermodal verdict, section 5). Say so rather than
  implying a look happened.
- The agreement gate in section 2 could only be run on the four files that carry repeat
  statistics. A per-source gate for the other 94 would need the mergers re-run with the
  statistics retained - that is the highest-value next verification step.
- Section 3 scores are upper-bound-sensitive to each source's own "previous" semantics.

## 6. Reproduce

```
python3 scratch/measure_agreement.py   # the gate, on the 4 files that carry min/max
python3 scratch/continuity_sweep.py    # section 3
python3 scratch/dup_sweep.py           # section 4.3
python3 scratch/baddate2.py            # section 4.4
python3 scratch/score_all_indices.py   # intermodal chart series vs the held feeds
```

## 7. Internal consistency sweep: does each file's change column equal current - previous?

Run over every series CSV carrying a (current, previous, change) triple, 20+ rows:
**11 files are 98.3-100% consistent** - bancosta_freight_rates (24,685 rows, 99.7%),
advanced_shipping_secondhand_matrix (7,968, 99.6%), bancosta_ffa (7,648, 99.1%),
intermodal_tc_rates (5,051, 99.9%), intermodal_maritime_stocks (3,118, 99.5%),
intermodal_demolition_prices and intermodal_demolition (1,996 each, 100.0%),
intermodal_baltic_indices (1,237, 99.8%), intermodal_currencies (652, 98.9%),
carriers_dry_weighted_routes (605, 98.7%), carriers_indices (638, 98.3%).
**Four files are not:**

1. **intermodal_indicative_values_series.csv - one-column shift on 295 rows.**
   The report prints `| Capesize | 180k | 37.5 | 37.1 | 1.0% | 27.6 | 31.1 | 36.1 |` (Vessel 5
   yrs old, Jul-21 avg / Jun-21 avg / +/-% / 2020 / 2019 / 2018). The series row is
   `current=180.0, prev_month=37.5, change=37.1` - the vessel SIZE was consumed as the price
   and the whole triple shifted one column left (implied change (37.5-37.1)/37.1 = 1.08% vs
   the printed 1.0%). Of 554 inconsistent rows, **295 fit the shift exactly**; the remaining
   259 (tanker table, other age profiles) are unexplained. The result looks plausible - 180 $M
   for a 5-year Capesize is high, not absurd - which is why no count-based check caught it.
2. **carriers_tanker_tce_series.csv - 510 of 768 rows.** `week_change` does not equal
   `current_value - prev_value`. The TCE family is scaled in thousands while the change is in
   units: `VLCC TCE 25.29 / 29.388 / -4098`, `SUEZ TCE 55.492 / 77.385 / -21893`. A
   1000x-class unit mix inside one row. The Baltic index rows in the same file are fine
   (`1373 / 1447 / -74`).
3. **intermodal_newbuilding_prices_series.csv - 893 rows (28.0%) have
   `price_previous_usd_m = 0.0`**, and `intermodal_newbuilding_series.csv` repeats the same
   893 rows (17.8%). A missing previous price written as a zero, not a blank: any derived
   percentage from it is undefined, and the register's own `pct_change` column sits beside it.
4. **intermodal_macro_series.csv - 1,290 of 3,739 rows** state a change that cannot be
   reproduced from `latest_value` and `prior_value` (`10year US Bond 1.431 / 1.48 / -6.8%` where
   the pair implies -3.31%; `CAC40 6552.86 / 6553.82 / -1.1%` implies -0.01%), and the change
   is **blank on 2,075 rows**. Either the printed change is over a different window than the
   prior column, or the columns are mis-paired.

**One flag was my own instrument, not a defect - recorded so nobody chases it.**
`intermodal_tanker_spot_series.csv` scored 3.8% because my checker paired `change_pct` with
`ws_points_current`; the report's change belongs to the TCE column (`VLCC 265k MEG-SPORE`:
WS 32/33, TCE -5195/-775, change -570.3% = the TCE pair). The file is correct.

---

# UPDATE 2026-09-28 ~12:4x - defect 4.2 (ism) is FIXED; re-measured

The ism merged series were re-keyed and rebuilt (no re-extraction). Full detail in
`docs/ism_series_fix_verdict.md`. Summary against this ledger's own gate:

| file | rows | p90 spread | within 2% | rows >10% |
|---|---|---|---|---|
| ism_coaster_freight_series.csv | 13,281 -> **12,319** | 43.34% -> **6.06%** | 74.3% -> **83.4%** | 1,233 -> **481** |
| ism_handy_freight_series.csv | 18,833 -> **17,629** | 20.59% -> **11.83%** | 69.1% -> **73.9%** | 1,036 -> **697** |

Two root causes, both in the merger, both measured:
1. the key omitted the panel ENTITY (as diagnosed in `docs/ism_agreement_tail.md`) - fixed by
   deriving the entity from the chart's own sibling labels;
2. **new finding** - multi-year COMPARATIVE charts plot several years on one repeating
   52-week x axis (154 points = 52+52+50 = 2021,2022,2023, confirmed by the chart's own tick
   labels), and the merger assigned the year from the week number alone, fusing three years
   onto one date. This was the larger of the two.
Also fixed: the 2,356 `% of freight costs in CFR price` rows carried unit `$/t`; now `%`.

**This ledger's section 1 counts are now stale.** Re-measured across `data/extracted/series/`:
**100 CSVs, 277,005 data rows** (was recorded as 98 CSVs / 273,254 rows). The ism change alone
removes 2,166 rows; the other files have grown since that count was taken.

Still open here: the residual ism tail (1,178 rows) is a DIFFERENT class - outlier reports
drawn on a different axis (e.g. `2023_W38` uses ticks `71,64,...,15` where every other report
uses `75,65,...,15`), plus some TCT route series. Not fixed, not dropped.
