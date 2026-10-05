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
