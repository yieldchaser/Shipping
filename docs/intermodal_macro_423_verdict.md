# Ledger 4.3 - `intermodal_macro_series.csv` - VERDICT: FAITHFUL numbers, mismatched pairing (not a defect)

Measured 2026-10-06 05:0x. Ledger 4.3 recorded "1,290 of 3,739 rows whose stated change is
not reproducible from `latest_value`/`prior_value`, blank on 2,075". Re-measured on the
current file (4,818 rows, rebuilt since the ledger note): **0 blank**, and the change is
non-reproducible from latest/prior on **4,418 / 4,818 = 91.7%** - the defect is real AND
systematic, not random noise. VERIFIED against the source page before any fix.

## Ground truth (the page's own table)

`corpus/01-brokers/intermodal/2021/intermodal_2021_W26_...pdf` p7 prints the macro table as
**five DAILY date columns plus a W-O-W change %**:

```
2-Jul-21    1-Jul-21   30-Jun-21   29-Jun-21   28-Jun-21   W-O-W Change %
10year US Bond   1.431  1.480  1.443  1.480  1.478   -6.8%
S&P 500       4,352.34  4,319.94  4,297.50  4,291.80  4,280.70  1.7%
Nasdaq       14,639.33  14,522.38  14,503.95  14,528.34  14,500.51  1.9%
Dow Jones    34,786.35  34,633.53  34,502.51  34,292.29  34,283.27  1.0%
```

The same 5-daily + W-O-W shape holds in **2023 W08** (`24-Feb-23 .. 20-Feb-23`) and
**2025 W10** (`7-Mar-25 .. 3-Mar-25`) - the layout is stable across eras.

## What the extractor did

* `latest_value` = the most recent DAY column (2-Jul) - **exact from the page**.
* `prior_value` = the previous DAY column (1-Jul) - **exact from the page**.
* `wow_change_pct` = the printed W-O-W Change % - **exact from the page**.

All three fields are individually faithful. The change is not reproducible from the pair
because the pair is **day-over-day** while the % is **week-over-week**:

* 2021 W26 S&P: 4,352.34 vs prior-day 4,319.94 = **+0.75%**, page prints **1.7%**
  (1.7% reproduces against ~4,280 = the 28-Jun column, i.e. a week back).
* 2023 W08 S&P: 3,982.24 vs 3,970.04 = **+0.31%**, page prints **-2.4%**.

The W-O-W baseline (same weekday, one week earlier) is **not among the five printed columns
at any of the three years checked** - it is the publisher's own computation against an
unshown value, so `wow_change_pct` is NOT derivable from the grid at all.

## Verdict

**NOT a number defect - a schema/semantic mismatch plus data loss.** No value is wrong; the
CSV merely (a) names a day-over-day prior beside a week-over-week % (implying a relation that
does not hold), and (b) retains only **2 of the 5** printed daily points per indicator per
week.

Any fix must therefore be a **re-key to the date columns** (one row per indicator x print
date, 5 points/week), with the W-O-W % carried as the publisher's own field and its
"vs unshown week-ago" baseline documented - never recomputed from latest/prior. Follows the
skill rule "a series is (row label, column header)": here the header is the DATE. Deferred to
the per-source runner (`scripts/extract/publishers/run_intermodal_full.py`); VERIFIED first,
not fixed blind - consistent with the four prior "defects" that looked real and were faithful.


---

## FIXED 2026-10-06 11:xx - re-keyed to the date columns (ledger 4.3 closed)

Implemented in the source's OWN runner, `scripts/extract/publishers/run_intermodal_finance.py`
(not `run_intermodal_full.py` - that file does not write this series). New output file
`data/extracted/series/intermodal_macro_daily_series.csv` - one row per **indicator x print
date**, so the series key is now `(row label, column header = the DATE)` as the skill
requires. The wide file `intermodal_macro_series.csv` is left byte-identical
(md5 `cceecc8098203c6c7b4cd1c7b7100271`, 4,818 rows) - no downstream consumer breaks.

Columns: `issue_date, report_week, category, indicator, print_date, day_offset, value,
is_latest, wow_change_pct, source_file`. `day_offset` 0 = the newest printed day,
`is_latest` marks it. `wow_change_pct` is carried verbatim as the publisher's own field -
NEVER recomputed (its baseline is a week-ago value the report does not print).

### Measured result
| metric | value |
|---|---|
| daily rows | **22,760** (18 indicators, 4,552 indicator-rows x 5 days) |
| wide rows | 4,818 (unchanged; control md5 byte-identical) |
| control: `day_offset 0` value == wide `latest_value` | **4,552 / 4,552, 0 mismatch** |
| print_date strictly decreasing with day_offset | **0 violations / 4,552** |
| coverage of the 18 five-column indicators | **4,552 / 4,568 = 99.65%** |
| blank daily values (publisher's "mrkt closed") | 27 |
| print_date range | 2021-06-28 .. 2026-09-25 |

### Trial against the RENDERED page text (the control that points at the same document)
Sampled across seven years, values read from the PDF's own text layer (no vision tool in
this session):

| doc | dates recovered | 10year US Bond daily values | page |
|---|---|---|---|
| 2021 W26 | 02,01,30,29,28-Jul-21 | 1.431 / 1.480 / 1.443 / 1.480 / 1.478 | exact |
| 2022 W04 | 28,27,26,25,24-Jan-22 | 1.782 / 1.807 / 1.848 / 1.783 / 1.735 | exact |
| 2023 W08 | 24,23,22,21,20-Feb-23 | 3.949 / 3.879 / 3.923 / 3.955 / 3.828 | exact |
| 2023 W22 | 02,01,31,30,29-May-23 | 3.691 / 3.608 / 3.637 / 3.700 / 3.810 | exact |
| 2024 W21 | 31,30,29,28,27-May-24 | 4.503 / 4.550 / 4.616 / 4.548 / 4.461 | exact |
| 2025 W10 | 07,06,05,04,03-Mar-25 | 4.318 / 4.282 / 4.267 / 4.210 / 4.180 | exact |
| 2026 W10 | 06,05,04,03,02-Mar-26 | 4.132 / 4.146 / 4.082 / 4.057 / 4.052 | exact |

### Three real defects the trial/verification found and fixed (each silently lost whole docs)
1. **Kerned month.** The text layer prints `2-J un-23` (space inside "Jun") on 25 documents
   from 2023 W22 on; the month in a date is NOT stable. Fixed by matching/parsing the
   whitespace-stripped form (the same trick the label keys already used).
2. **Header fused onto the last date.** From 2024 on the block prints
   `20-May-24 W-O-W Change %` on ONE line (2024 W20 onwards), so the newest date was
   dropped by a "skip the header line" rule. Fixed by stripping the header words from each
   candidate line and testing whatever date remains.
3. **Two dates fused onto one line.** 7 documents (2024 W21/W47, 2025 W12/W46/W47/W48 + a
   `_compressed` copy) print `29-May-24 28-May-24` - fixed by `findall` per line, PREPENDED
   (the backward walk must not `reverse()`, or it flips the two dates: measured, it swapped
   the 28th and 29th).

### Residual (documented, not guessed)
* 16 rows / 1 document, `intermodal_2025_W07`: the block prints the five dates AND a stray
  `7-Feb-25` (the W-O-W baseline date, 14-Feb minus a week) after the header, giving 6 date
  tokens against 5 value columns. Left UNKEYED rather than trimmed - trimming to "newest N"
  would silently mis-key the separate two-column Brent/WTI table, and a wrong print_date is
  worse than a missing one.
* 250 rows (125 `Brent` + 125 `WTI`) come from the separate **Basic Commodities Weekly
  Summary** two-column table ("Oil Brent $"), not the five-column macro table, so they are
  not keyed here. They remain in the wide file.
