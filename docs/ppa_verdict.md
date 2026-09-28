# PPA verdict - source 09-ppa (Pilbara Ports Authority), built 2026-09-28

Runner: `scripts/extract/publishers/run_ppa.py` (per-source, resumable, JSONL checkpoint).
Survey: `docs/ppa_survey.md`. Corpus: `corpus/09-ppa`, 493 PDFs.

## Result

| family | docs parsed | arithmetic checks | failures | output |
|---|---|---|---|---|
| A Port Hedland cargo by origin/destination | **255 / 255** | **6,210 / 6,210 (100.000%)** | 0 | `data/extracted/ppa/ppa_hedland_trade_series.csv` |
| B Port of Dampier financial year | **83 / 83** | **873 / 873 (100.000%)** | 0 | `data/extracted/ppa/ppa_dampier_fy_series.csv` |
| junk | 3 | - | - | skipped by content check |

Total wall time for the whole corpus: **33.5 s** (family A) + **16.3 s** (family B).
Zero failed documents, zero unhandled exceptions.

## The validation is arithmetic, not a metric

Every family-A table prints a **Total row AND a Total column**; every family-B table prints
a **TOTALS: row**. Each parsed table is checked by summing its own printed numbers:
column totals summed down the country rows, row totals summed across the commodity columns,
month rows summed against the printed TOTAL CARGO. Tolerance is
`max(1.5 t, 1e-6 * printed)` - the publisher rounds each monthly figure independently, and
6 of the 13 months of the FY2025-26 Dampier table are off by exactly +/-1 tonne.
The gate found **four real defects during the build**, each fixed and re-measured:
a column bridged by the wider TOTALS-row numbers; vessel counts and the publisher's own
Validation/Variance columns counted as cargo; a 2024-05 file with no Total column at all
reported as three phantom row mismatches; and a commodity column that is empty in every
month row (LPG in FY2026-27) collapsing into its neighbour.

## Independent control (a different extractor, same PDFs)

`data/commodities/australia_ppa_iron_ore.csv` was produced earlier by
`scripts/scrapers/fetch_ppa_iron_ore.py` with a completely different method (locate the
Iron Ore column by its header x-position, take the value in that x-band).

| control | months compared | agree within 0.001 Mt | max abs diff |
|---|---|---|---|
| Port Hedland Iron Ore LOAD total | 126 | **126 / 126** | 0.0005 Mt |
| Port of Dampier Iron Ore | 290 | **289 / 290** | 0.0005 Mt |

The single disagreement is **not a parse error**: October 2016 exists as two different
Wayback snapshots that state different figures for the same month
(`..._20170308022755_dampier_stats_pdf.pdf` -> Iron Ore 12,387,733, Total Cargo 15,227,823;
`..._20200403121126_port_of_dampier_2016_17_figures_pdf.pdf` -> Iron Ore 12,586,905,
Total Cargo 15,427,360). Both parse correctly and both are kept; the series carries two
conflicting values for 2016-10. That is a corpus restatement, not an extraction defect.

## Coverage

* **Hedland**: 4,591 unique rows, **133 months, 2015-01 -> 2026-08**. 140 calendar months
  fall in that span, so **7 are genuinely absent from the corpus** (2015-09..2016-01,
  2016-03, 2021-07) - a collection gap, not an extraction gap. LOAD 3,071 rows over 12
  commodity labels and 36 countries; DISCHARGE 1,520 rows over 5 commodity labels and 32
  countries.
* **Dampier**: 4,344 unique rows, **290 months, 25 financial years, FY2002-03 -> FY2026-27**,
  20 metric columns.

## Known limitations (stated, not hidden)

1. Commodity labels are recorded **exactly as printed**, so era renames survive as separate
   labels: `Spodumene` / `Spodumene Concentrate` / `Spodumene DSO`, `AMMONIA` / `AMMONIUM`,
   `PETROLEUM IN` / `PETROLEUM PRODUCTS` / `PETROLEUM OUT`, `No. OF ARRIVALS` /
   `NUMBER OF ARRIVALS`. Deliberate: a normalisation map would be a judgement, not a reading.
2. The Dampier CSV carries the publisher's own `Validation` and `Variance` columns
   (20 rows) and, in 7 documents, a numeric `MONTH` column. They are kept for traceability;
   filter them out before charting.
3. The corpus holds duplicate copies of many months (both `_root_pdfs/` and `ppa_pdf/`).
   The published CSVs are deduplicated on the series key, which dropped 3,792 of 8,383
   Hedland rows and 6,172 of 10,516 Dampier rows.
4. **Family C (152 per-vessel register documents, 5-10 pages each) is NOT built.** It is a
   different table (Vessel / Arrival / Departure / Import / Export / GRT / DWT /
   Destination-Origin / Cargo) with no ruling lines and needs its own pipeline.
5. This session had **no vision tool**. Substituted: the arithmetic self-check above (every
   printed total reconciled against the numbers it totals) plus the independent-extractor
   control. No claim here rests on an unverified rendering.
