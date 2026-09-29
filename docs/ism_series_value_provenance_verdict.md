# ism series - two real defects fixed; the residual spread is PUBLISHER-SIDE (page-verified)

**Date:** 2026-09-29 (cron, unattended) · Runner: `scripts/extract/publishers/run_ism_series.py`
**Rebuilt from the CACHED `.charts.json` - no API spend.**
Supersedes the *recommendation* in `docs/ism_residual_verdict.md` (that run proposed a
median across reports; this run measured that a median fabricates values and replaced it).

## Scope

The only open item in `docs/series_verification_ledger.md` was the residual ism agreement
tail. It was measured, diagnosed to the page, and closed. Two REAL defects were found and
fixed on the way; the spread itself is the publisher's.

Row counts are unchanged: `ism_handy_freight_series.csv` **17,629**,
`ism_coaster_freight_series.csv` **12,319** (29,948 total). The register stays valid.

## Defect 1 - the `unit` column was wrong on 16,985 rows (57%)  [FIXED]

`build_rows()` computed the unit from a variable named `title` that is **not a parameter** -
it is the chart loop's variable from the enclosing `main()` scope. Python resolves it at call
time, so every row got the unit of whichever chart happened to be processed **last**.

| | before | after |
|---|---|---|
| handy units | `%` 1,058, `$/day` 16,571 | `%` 1,058, `$/t` 14,668, `$/day` 1,903 |
| coaster units | `%` 1,130, `$/day` 11,189 | `%` 1,130, `$/t` 7,637, `$/day` 3,296, `EUR/t` 256 |

`$/t` never appeared at all before, although 16,985 rows carry a route title **and** a series
label that both end in `$/t` (e.g. `Freight rate, corn, 50-65,000t, USG - S.China, $/t`).

Fix: `unit_for(title, [label])`, derived from the page - the series label's own unit suffix
first (a CFR-weight chart carries a `%` line *and* a `$/t` line, so the unit is a property of
the SERIES, not the chart), then the chart title (`$/day`/`TCE`/`TCT`, `EUR`/`EUR` sign, `$/t`).

**Control:** 24,409 rows carry a printed unit suffix on their own label or title. Re-checked
against it: **0 real mismatches**. (A first pass reported 256 "mismatches"; all 256 are my
control not testing the `EUR` sign that the code does test - `Coal, 3-5,000t, Rostov bb -
Samsun / Trabzon (2000c/2000x), EUR/t`.)

## Defect 2 - the `value` was a median across restatements that CONTRADICT each other  [FIXED]

ism redraws every chart every week over a rolling 52-week window, so one
`(route, series label, week)` is restated by up to 45 issues, and the merge kept the
**median**. Where the restatements agree that is harmless; where they disagree the median is
a number **no page ever printed**.

Measured on the TCT chart (`TCT rates dynamics, $/day`): of 1,495 restated points, **24.6%
differ by >2%** between the week's own issue and the latest one, and **14.6% by >10%**.

Also measured: both window EDGES are unreliable. The newest point of the week's own issue is
provisional - `ism_2024_W21` prints **17,035** for a week every later issue prints as
**19,546** - and the oldest point of a later issue is expiring. 14 observations corpus-wide
(0.02%) are drawn outside their own chart's printed axis, all negative freight rates.

Fix, in `pick_observation()`:
1. drop observations drawn outside their own chart's printed y-axis span (14 corpus-wide);
2. prefer an observation that is NOT the first/last point of its series;
3. among those, the issue **nearest** the observation date (ties -> earlier);
4. if every observation is an edge, fall back to the nearest anyway.

The value is now **verbatim from a named issue**, and `value_report` names that issue.
`min_value` / `max_value` / `value_sd` / `n_reports` still carry the full restatement band,
and `value_edge` (0/1) says whether the chosen value came from a window edge.

## Controls (all measured, none estimated)

* **PROVENANCE (the decisive one):** for every one of the **29,948** emitted values, the
  value is present **verbatim** in the `series` array of the report named in `value_report` -
  **29,948 / 29,948 = 100.00%**. (`scratch/ism_provenance_control.py`)
* **No fabricated values remain:** 0 rows with a negative `value`, 0 with a negative
  `min_value` (was 14 observations below their chart's own zero).
* **Surgical:** relative change vs the previous file - p50 **0.0000**, p90 **0.0016**
  (handy) / **0.0033** (coaster), p99 0.12-0.15, max 0.47. Only **736 rows** move by >5%
  (465 handy + 271 coaster) - exactly the rows where the median was splitting contradictory
  restatements. Row keys and row counts are identical.
* **Unit control:** 24,409 rows, 0 real mismatches (above).

## The residual spread is the PUBLISHER's, verified against the pages

`docs/ism_residual_verdict.md` concluded PUBLISHER_INCONSISTENT from geometry alone. This run
read the publisher's own page text and found the two mechanisms, both verbatim on the page:

**(a) The publisher RELABELS its own year-comparison lines.** Chart
`Fertilizers, 4,000t, Klaipeda - N.Spain (2500x/2500x), $/t`:

| issue | legend printed on the page | the cyan line, weeks 1-12 |
|---|---|---|
| `ism_2023_W50` | `2020 year / 2021 year / 2022 year` | 57, 57, 57, 56, 55, 55, 53, 52, 52, 55, 52, 52 |
| `ism_2024_W01` | `2022 year / 2023 year / 2024 year` | 37, 34, 34, 32, 32, 30, 30, 29, 29, 29, 29, 29 |

The line `ism_2023_W50` labels `2021 year` carries **exactly** the values `ism_2024_W01`
labels `2022 year`. Legend labels are assigned by matching the stroke COLOUR to the legend
swatch (`run_ism.py`), so this is not an order-based mis-join - the two issues genuinely
disagree about which year the same curve is. Both axis label sets are printed on the page
(`15,23,31,39,47,55,63` in W01; `25..65` step 5 in W50) and both fits verify
(`maxres_pct` 0.086 and 0.003).

**(b) One TCT line changes LEVEL mid-2025 while its five siblings stay identical.** Chart
`TCT rates dynamics, $/day`, value at the same ISO week 2025-03-31:

| line | `ism_2025_W18` | `ism_2025_W22` | `ism_2025_W26` |
|---|---|---|---|
| Handysize, BlSea - EMed | 5,486.1 | 5,486.2 | 5,486.1 |
| **Supramax, ECSA - Cont (bss dely APS)** | **14,246.6** | **7,999.5** | **7,999.4** |
| Supramax, Continent - EMed | 13,528.5 | 13,528.7 | 13,528.6 |
| Handysize, Continent - EMed | 12,020.6 | 12,020.7 | 12,020.5 |
| Supramax, PG (excl. I/I) - India | 10,512.7 | 10,512.8 | 10,512.6 |
| Supramax, Indo - India | 13,025.8 | 13,025.8 | 13,025.9 |

Five of six lines agree to the digit across the three issues; only ECSA-Cont changes, by
-44%, and its new value matches no other line on the chart (so it is not a colour
permutation). The rebuilt ECSA-Cont series now shows a single visible break at 2025-04-28
(14,246.6 -> 6,994.1) and is smooth either side of it - faithful to what each issue printed.

**Consequence:** the >10% spread flags (`n_reports>1`) stand at **665 handy / 453 coaster**.
They are a record of the publisher's own restatement band, not an extraction error, and are
preserved deliberately in `min_value` / `max_value` / `value_sd`.
