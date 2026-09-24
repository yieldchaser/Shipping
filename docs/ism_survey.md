# ISM (Metal Expert, ismreport.com) - measured survey before any code

Source 8 of the source-by-source programme. 112 PDFs, no existing fetcher
(`grep -ril ism scripts/` returns nothing but a probe summary). Fingerprinted
2026-09-24 by rendering and reading pages from all four years.

## 1. What is there

| fact | measured |
|---|---|
| documents | **112** (`corpus/01-brokers/ism/<year>/*.pdf`) |
| years | **2023:37  2024:31  2025:27  2026:17** - no 2021, no 2022 |
| pages/doc | 2 (73 docs), 3 (38 docs), 6 (1 doc: `ISM_2023_holiday_special.pdf`) |
| page size | portrait A4, 595x842 pt, constant across all four years |
| text layer | median **5,439 chars/doc**, min >500 - rich, never garbled, never scanned |
| images | 1-2 per doc (logo/header) - **not** a raster source |
| vector drawings | 26-36 per page in every one of the 266 pages; 0 docs with 0 drawings |
| publisher | Metal Expert; two lines by filename: `ISM_coaster_weekNN` / `ISM_Handy_weekNN` |
| numbers | ISO (`29,580` = 29580); **no** European separators seen anywhere |

## 2. ism holds NO TABLES

A numeric-row detector (y-bands holding >=3 numeric spans) fired on 149 of 266
pages - and every one of them is a **false positive from chart x-axis tick
labels**. Verified by printing the band contents:

```
2023 holiday special p1  band y~255  n=20  [52, 8, 16, 24, 32, 40, 48, 4, 12, 20, 28, 36, ...]
2025 W21 p1              band y~186  n=18  [22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 52, 3, ...]
```

Those are the week numbers printed along a chart's x axis, evenly spaced - the
exact trap the skill warns about ("a chart's y-axis tick labels are plain
numbers; they look exactly like a card column"). **There is no table anywhere in
this source.** The deliverable is therefore chart series, not table cells.

## 3. Every chart is vector - vision is not needed

Page 1 of `2025_W21` probed with `get_drawings()`:

| drawing | colour | width | items | what it is |
|---|---|---|---|---|
| 1-5 | black | 0.12 | 1-52 `l` | axis rules, y tick marks, x tick marks |
| 6-12 | blue/red/green/cyan/amber/black/dk-green | 0.99 | 51 `l` each | **7 series polylines** |
| 13-18 | same colours | 0.99 | 1 `l` each | **6 legend swatches** |

So the axis geometry and the series values are exact path data. Ticks are drawn
as short collinear line marks (y ticks 1.5 pt wide, x ticks 1.7 pt long), which
is better ground truth than the tick *text*, whose baseline sits ~1.6 pt off the
tick it labels.

## 4. The layout is NOT stable across years - nothing may be hardcoded

Measured on the same chart family (the "round voyage TCE, $/day" panel):

| year | plot area (y) | y ticks | axis span | series count |
|---|---|---|---|---|
| 2023 W32 | 560-703 | 12 | 0-16,500 | 6 |
| 2024 W26 | 449-553 | 8 | 0-35,000 | 6 |
| 2025 W21 | 93-178 | 9 | 0-8,000 | 7 |
| 2026 W19 | 104-189 | 8 | 0-7,000 | 7 |

The plot moves ~470 pt between years and the axis span changes 5x, so any fixed
coordinate or fixed tick count is wrong. Tick counts per axis measured at
**6, 8, 9, 11 and 12** within a single page. Every threshold in the runner is
derived from the page.

## 5. Two x-axis conventions live in the same document

This is the finding that made a tick-index mapping unsafe:

* the **TCE chart** (p2) has 52 tick marks and its 52 data points sit **ON** them;
* the **billets chart** (p1) has **53** tick marks (week *boundaries*) and its
  points sit on the week *centres between* them (measured: label centre
  `327.43` = midpoint of ticks `325.19`/`329.71`).

So the week axis is anchored on the **printed labels** by least squares, not on
tick index. The fit residual then says whether the axis is even linear in week
(measured 0.013-0.037 weeks on the trial set).

## 6. Dual-axis charts, and the 10x / 50x trap

Three of the four chart families are dual-axis: left = `$/t` or `$/day`,
right = **`%`**. The right axis is labelled to the RIGHT of the plot. Matching
both axes to the labels on the left produced:

* 2023 W32: a 0-20% axis read as 0-1000 (**50x**),
* 2025 W21: a 0-40% axis read as 0-400 (**10x**).

Both are in the plausible direction and both are well-formed floats, so no
validation would have caught them. The runner now prefers the far side, and
cross-checks by requiring the % series to reconcile: freight / price must equal
the % series. Measured on the trial set: 2024 W26 `21.7 / 258.1 = 8.4%` against
a % series reading `8.4`; 2025 W21 `26.3 / 270.1 = 9.7%` against `9.8`.

## 7. Junk routed out

* no bot-wall placeholders, no HTML-served-as-PDF, no misfiled documents:
  all 112 files open and carry a real text layer
* `ISM_2023_holiday_special.pdf` is a genuine 6-page special, not junk
* a footer field reads `Coaster Freight Index, April, 11, 2025` on a **week 21**
  file (mid-May). It is a stale template field, not a date: the report week is
  taken from the FILENAME, and the chart's own last x label (21) agrees with it.
