# xclusiv charts - what is being missed, measured on a rendered page

## The finding
Xclusiv page 3 ("Freight Market - Wet") carries FIVE time-series charts, each
plotting roughly five years of history:

    chart                 y-axis            x-range            legend
    VLCC TCE              $/day 360k..-60k  Apr '21 .. Apr '26  TCE / Average / Min / Max
    Suezmax TCE           same              Apr '21 .. Apr '26  same
    Aframax TCE           same              Apr '21 .. Apr '26  same
    MR Atlantic Basket    $/day 75k..-5k    (shorter)           same
    MR Pacific Basket     $/day 75k..-5k    (shorter)           same

Confirmed VECTOR, not raster - page segment counts 8992 / 11354 / 719 / 2198 / 207 -
so advanced_shipping's axis-calibration method applies directly.

## Why this matters
The PROSE on the same page gives only THIS WEEK's values:
    219,233  453,227  104,294  100,179   (VLCC)
    117,640   98,909  136,371  382,654   (Suezmax)
    110,265  126,913  136,742  120,827   (Aframax)
    153,488  109,205  146,825  131,200   (Products/LR2/LR1)
     76,581   44,143   31,414   92,363   (MR)
Those ARE extracted (the prose-anchored pipeline, 69% labelled).

The CHARTS give the FULL 2021-2026 series for each class and route. That history
appears nowhere else in the documents and is not in our data. So the highest-value
content in this publisher is precisely the part that was skipped.

## This is the parity gap made concrete
advanced_shipping got chart values. xclusiv - which has MORE chart content, on
more pages (2,3,4,7,8), in vector form - got none. The skip was justified by
generalising star_asia's finding ("its charts restate its tables", verified on one
page) to a publisher whose charts plainly do NOT restate anything: they plot five
years the prose never mentions.

## What extraction requires (the method already proven on source 1)
1. Locate each chart's plot area (axis lines / bounding rules).
2. Read the y-axis tick labels, cluster their y-positions, and fit
   value = m*y + c per chart. On source 1 this gave e.g.
   value = -3.3148*y + 1224.08 with max_err 0.039.
   Per-chart fitting is mandatory: forcing one scale across stacked charts gave
   max_err 124.5.
3. Read the x-axis labels for date anchoring.
4. Extract the series polyline from the vector drawings, and map each vertex's y
   through the fitted calibration.
5. Separate the TCE series from the Average / Min / Max reference lines, which are
   drawn in different styles - do NOT let a reference line be emitted as data.
6. VERIFY by comparing a chart-derived value against the prose value for the same
   week on the same page. The prose is independently extracted, so it is a real
   control rather than a self-check.

## Status
Not started beyond rendering the chart pages and reading one. The five chart pages
of 2026 W17 are rendered at scratch/bench/png/xclusiv_charts/.
