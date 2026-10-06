# GOLDEN_DESTINY (corpus/archive/golden_destiny) - extraction survey

Measured 2026-10-06 source-by-source cron run. Companion to
`docs/archive_backfill_survey.md` (which fingerprinted the whole archive).

## Corpus
- **252 PDFs**, year-partitioned: 2021 (49), 2022 (100), 2023 (57), 2024 (46).
- Two document classes:
  - `Weekly-SP-Market-Report` (multi-page, 4-9 pp): prose-anchored S&P deals
    (secondhand sales, en-bloc groups, newbuilding orders, demolition).
  - `Special-Edition-Weekly-SP-Market-Trends` (**1 pp**): aggregate stat cards
    ("Average Number of Weekly Reported Transactions per month / year").
- vector charts (draws 250-1066/page); NOT a raster source.

## Deal shape (prose, not a grid) - measured
Each secondhand deal is 3-4 text lines:
```
<NAME>
<dwt> DWT BLT <yy> <yard> ... <engine> <BHP>
SOLD FOR ABT US $<x> MIL TO <BUYER>[. conditions]      (or "AN UNDISCLOSED PRICE")
<per-unit value US$/Dwt|Cbm|Teu, or N/A>
```
EN-BLOC: one SOLD line can cover SEVERAL preceding vessels.
- `... $17.00 MIL EACH TO UAE BYRS` (2023 W20, OLYMPIUS+VICTORIUS) = per vessel.
- `... $70,5 MIL TO UNDISCLOSED BYRS` (2023 W20, SEA PROTEUS/PLUTO/VENUS) = a
  GROUP TOTAL -> must NOT sit in a per-vessel price column (lion lesson).

## Number convention - MIXED in the SAME document
Measured 2023 W20: comma-decimals (`15,8`=15.8) AND period-thousands
(`252.000`=252000) AND period-decimal prices (`26.5`) coexist. Parse BY SHAPE:
- comma+period -> last separator is decimal;
- comma with 3 trailing digits -> thousands (`166,000`);
- comma with !=3 trailing -> decimal (`15,8`);
- period with exactly 3 trailing digits -> thousands (`252.000`);
- otherwise a lone period is a real decimal (`26.5`).

## Deliverable
- `.md` = full page text = PRIMARY (per-source rule; md tier was 0/252).
- `.tables.json` = parsed prose deals.
- `data/extracted/series/golden_destiny_sales_series.csv` = deal series.

## Liveness
Newest content 2024 -> ~700+ d -> **BACKFILL_ONLY**, never CONSTRUCT.
