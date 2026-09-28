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

---

# Family C - the per-vessel register (added 2026-09-28, same run)

Runner: `scripts/extract/publishers/run_ppa_vessels.py`. The 152 `Cargo, GRT and DWT
Statistics by Commodity Group` PDFs (Port Hedland), 5-10 pages each, no ruling lines.

## Result

| measured | value |
|---|---|
| documents parsed | **151 / 152** (1 skipped, see below) |
| failures | **0** |
| pages parsed | **1,122** |
| rows extracted | **41,875** -> **38,097** unique after dedupe |
| vessel rows with an unparseable date | 3 (rejected) |
| vessel rows with no numeric GRT/DWT | 0 |
| unique vessel names | **4,253** |
| months | **138**, 2015-01 -> 2026-08 |
| cargo groups | Iron Ore 33,383 / General 980 / Containers 891 / Hydrocarbon 891 / Salt 648 / Manganese Ore 316 / Spodumene Concentrate 288 / Copper Concentrates 256 / +9 smaller |
| wall time | 104.6 s |
| output | `data/extracted/ppa/ppa_hedland_vessel_calls.csv` |

Grain: `(date, cargo_group, vessel, country, arrival_date, departure_date, import_volume,
export_volume, grt, dwt)`. Rows carrying `export_volume` are LOAD (destination country);
rows carrying `import_volume` are DISCHARGE (origin country). The 2015-era files also carry
`arrival_no` (`PHPA-2015-00210`).

## The control that makes this trustworthy

Family C is a **per-vessel** table; family A is a **per-country** table, in a different
document, parsed by a different code path. Summing family C's individual Iron Ore
`export_volume` cells for a month must therefore reproduce family A's Iron Ore LOAD total.

| measured | value |
|---|---|
| months compared | 132 |
| **exact to the tonne (diff < 1 t)** | **128 / 132** |
| max relative difference | 0.73% |
| disagreements | 4 |

The 4 disagreements (2017-11, 2018-11, 2021-09, 2022-11) are **corpus restatements, not
parse errors**: for each, the two families come from two DIFFERENT documents that state
different figures for the same month, and each document is internally consistent (family A's
country rows sum exactly to its own printed Total; family C's vessel rows sum to its own).
Both readings are kept.

## Defects found and fixed by the trial (each cost a re-measure)

1. `cargo_group` was always NULL - the group label sits alone ~20 pt above its first vessel
   row, so it belonged to no date-anchored row and was dropped. Leftover words now form
   their own rows.
2. Group state was reset on every page. The label appears only where a group STARTS, so
   continuation pages lost it: Iron Ore exports read 1.84 M t against a true 49.88 M t.
3. `Arrival No.` (the 2015 layout) was written into `arrival_date` and overwrote the real
   date, because a dict-order walk let a later band win. Fields are now assigned in band
   order and never overwritten.
4. Vessel names were truncated to the first word (`WUGANG` for `WUGANG HAOYUN`): column
   bands were assigned by containment, and the narrow `Vessel` header band (47.6-72.5 pt)
   did not reach the second word. Assignment is now by column START.
5. The header anchor was the word `Vessel`; one 2016-02 file prints no `Vessel` header at
   all, and `min(y)` of the anchors picked the TITLE line (`Cargo, GRT and DWT ...`).
   The anchor is now the lowest header word above the first data row, with the
   reporting-period line excluded.

## Skipped document (named)

`corpus/09-ppa/ppa_pdf/a2c617ad59c5.pdf` (2016-02, 9 pages) - its header prints no `Vessel`
column, so the vessel names have no label. Left unlabelled rather than guessed, per the
project rule that a wrong value is worse than a missing one. 1 of 152 documents.
