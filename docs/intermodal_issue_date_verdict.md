# Ledger 4.4 re-diagnosed: the fake date was a SYMPTOM - the real defect was a wrong `issue_date`

**Verdict: CLOSED. The `2026-00-00` rows were the smaller half of the defect.** Ledger 4.4
recorded "230 rows with a fake date". Measured against the source pages, the same builders had
also written a **wrong** date on 251 further rows, because their date parser searched the report's
body prose instead of its cover line. Both halves are fixed at the source, in each publisher's own
runner, with no LlamaParse spend.

## What was measured before the fix

`issue_date` was checked against the publisher's own cover line - `Week NN | <Weekday><D><ord>
<Month> <YYYY>`, e.g. `Week 06 | Tuesday13th February 2024` - which is present and **unique on
page 0 of 252/252** intermodal reports. That is the report's own statement of its date, so it is
the ground truth for this test.

| series file | rows | wrong date | fake `2026-00-00` |
|---|---|---|---|
| intermodal_bunkers_series.csv | 2,260 | 27 | 54 |
| intermodal_macro_series.csv | 3,739 | 44 | 92 |
| intermodal_maritime_stocks_series.csv | 3,119 | 38 | 72 |
| intermodal_demo_sales_series.csv | 577 | 16 | 0 |
| intermodal_demolition_prices_series.csv | 2,016 | 72 | 0 |
| intermodal_newbuilding_orders_series.csv | 1,786 | 54 | 0 |
| **intermodal total** | **13,497** | **251** | **218** |
| xclusiv_bulk_carrier_charts_series.csv | 216 | 0 | 8 |
| xclusiv_demolition_charts_series.csv | 282 | 0 | 4 |

The other nine intermodal series (`tc_rates`, `tanker_spot`, `indicative_values`, `sales`,
`newbuilding`, `newbuilding_prices`, `demolition`, `baltic_indices`, `currencies`) were already
correct - which is exactly why a count-based sweep saw only the 230 fake rows and missed the 251
wrong ones: the wrong values are well-formed ISO dates.

## The three root causes

1. **`run_intermodal_full.py::extract_report_metadata`** searched pages 0-1 with a loose
   `LONG_DATE_RX` (`\d{1,2} <Month> <YYYY>`). On 9 documents that matched **body prose**, not the
   cover. `intermodal_2024_W06` page 2 says *"On Friday, February 9th, the BDTI settled at..."*,
   so the whole report was dated **2024-02-09** while its cover says **13th February 2024**. The
   worst cases were months/years out, not days:

   | document | shipped date | cover line |
   |---|---|---|
   | intermodal_2022_W06 | 2021-10-07 | 15th February 2022 |
   | intermodal_2023_W08 | 2025-03-31 | 28th February 2023 |
   | intermodal_2024_W06/W07/W08/W10/W11/W12 | 2024-02-09/16/23, 03-08/15/22 | 13/20/27 Feb, 12/19/26 Mar 2024 |
   | intermodal_23_09_2026_...week_38_2026 | 2026-09-23 | 22nd September 2026 |

2. **`run_intermodal_finance.py::extract_meta`** used the same loose text regex, and where it
   failed it wrote the literal `"2026-00-00"` - the fake dates on `bunkers` / `macro` /
   `maritime_stocks` (6 documents x 3 series).

3. **`run_xclusiv_vector_charts.py::extract_date_and_week`** accepted only the `YYYY_MM_DD`
   filename form, but xclusiv names its files `DD_MM_YYYY`
   (`xclusiv_15_09_2026_...weekly_14th_september_2026.pdf`), so it fell through to
   `"2026-00-00"`. `run_xclusiv_tables.py` already handled `DD_MM_YYYY` and is the control: it
   gives **2026-09-15 / 2026-09-22** for exactly these two files.

## The fix

* **Cover line first.** All three date parsers now try the publisher's cover line before anything
  else, then the filename, then loose text. Verified present and unique on page 0 of 252/252
  intermodal reports.
* **A filename never outranks the publisher's own cover.** One document
  (`intermodal_23_09_2026_...`) carries `23_09_2026` in its filename while its cover says
  22 September 2026; the cover wins.
* **An unknown date is written BLANK, never `2026-00-00`.** A zero month parses as a real ISO
  date and sorts as if it were in 2026, which is worse than a blank.
* **Three orphan series brought onto the same code path.** `intermodal_demo_sales_series.csv`,
  `intermodal_demolition_prices_series.csv` and `intermodal_newbuilding_orders_series.csv` had no
  current writer at all (their mtime was 2026-09-27, stale relative to the recent intermodal
  fixes). They are projections of the same sidecar tables as the union files, so they are now
  written by `build_all_series_from_sidecars()` alongside them - one code path, one date rule.

No API spend: rebuilt from the **cached** LlamaParse markdown via
`run_intermodal_full.py --reparse-only` / `--stack-only`.

## Verification (after)

| check | result |
|---|---|
| intermodal rows with `issue_date` == the document's own cover line | **40,636 / 40,636 across 16 series; 0 wrong, 0 fake** |
| `report_week` == the cover's `Week NN` | 252 / 252 |
| cover line parseable | 252 / 252 PDFs |
| row counts vs pre-fix and vs the ledger | unchanged: tanker_spot 3,818 / tc_rates 5,020 / indicative_values 2,333 / baltic_indices 1,240 / currencies 672 / sales 3,315 / newbuilding 4,967 / newbuilding_prices 3,134 / demolition 2,593 / bunkers 2,260 / macro 3,739 / maritime_stocks 3,119 |
| control - other series CSVs byte-identical (md5) | **110 of 119 unchanged**; only the intermodal files (and the two xclusiv files) differ |
| `intermodal_newbuilding_orders_series.csv` | 1,786 -> **1,833** (+47). Not drift: all **1,833** rows are present in the union file `intermodal_newbuilding_series.csv` (which carries 1,833 `reported_order` rows). The old split file was 47 rows short of the union; the two are now consistent. |
| xclusiv chart series | 12 fake rows -> see `issue_date` now equal to the sibling `run_xclusiv_tables.py` value (2026-09-15 / 2026-09-22) |

**Lesson for this ledger:** `2026-00-00` was the visible tip. The dangerous half of the same
defect was 251 rows carrying a *plausible* ISO date taken from body prose - invisible to every
count-based check, and it moved `intermodal_2022_W06` back to **2021-10-07**. When a fake-date
defect is found, re-derive every date in that source from the publisher's own cover, do not just
blank the fake ones.
