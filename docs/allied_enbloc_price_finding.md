# Finding: allied_sales_series.csv - en-bloc/fleet totals in the per-vessel price column

Author: hourly overnight supervisor (run 2026-10-07 01:20-02:12 IST). Read-only verification.
Source of truth: the PDF text layer (pymupdf page.get_text()), not another extractor.

## Measured
- `data/extracted/series/allied_sales_series.csv`: 3,218 rows. 2,427 non-blank `price_usd_m`.
  Median 20.0, p99 152.0, **max 660.0**. **15 rows > 200** and 1 > 500.
- golden_destiny_sales_series.csv (5,320 rows): median 18.5, p99 93.0, max 213.0, only 1 row > 200.

## The defect (lion-class: a FLEET TOTAL printed as one vessel's price)
Each high row is one member of a multi-ship lot on the same page:
- STH OSLO (UMAX 60,404, 2018, 2022_W32, page 8) — CSV price 330.0. The page prints
  literally `$ 330.0m  en bloc` with comment `eco, cash & shares deal, US$ 220 mill cash &
  US$ 110 mill in newly issued shares`. 220 + 110 = 330 -> the number is the STH-fleet
  en-bloc total (STH ATHENS/CHIBA/LONDON/OSLO/MONTREAL/NEW YORK/SYDNEY/TOKYO), not OSLO's price.
- SEAWAYS LIBERTY (VLCC 300,932, 2016, 2021_W42) 380.0 — sister SEAWAYS TRITON / DIAMOND HEAD on page.
- HAFNIA SIRIUS (MR 25,196, 2016, 2022_W13) 252.4 — sisters HAFNIA SPARK/STELLAR/SAIPH.
- MAERSK CUMULUS (MR 39,999, 2016, 2022_W23) 230.0 — sisters MAERSK NIMBUS/STRATUS.
- KOOL FIRN (LNG 93,025, 2020, 2022_W44) 660.0 — LNG, no partner shown on that page.
(An MR product tanker is ~USD 30m and a VLCC ~USD 80m; 230-660 for those classes is not a
per-vessel price.)

## Impact / scope
15 rows >USD 200m = 0.6% of priced rows. The number IS printed in the source (not fabricated),
but it is a group total in a per-vessel column — the exact error the project burned 38 rows on
for lion (`docs/lion_verdict.md`). allied's own verdict claimed en-bloc *members* carry a blank
price; the "`$ X en bloc`" form (total on the fleet's first/representative row) was not handled.

## NOT fixed here
Out of the supervisor's lane (the extraction agent owns series + register). Recommend: detect
rows whose printed price co-occurs with `en bloc` / a fleet of >=2 same-class sisters on the page,
move the amount to a `group_total_mil` column, blank `price_usd_m` for members. allied is
BACKFILL_ONLY, so this is a correctness fix, not a series extension.
