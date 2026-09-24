# Chart-layer survey: what is real, what the machine got wrong

Date: 2026-09-24. Free (geometry only, no credits). Sources under review are the four
the completeness audit flagged as "missing CHART-VALUES" plus clarksons.

## Verified by RENDERING (the only reliable test)

| source | verdict | evidence |
|---|---|---|
| **ssy** | **CHARTS REAL** | Rendered p1: a 12-month line chart of the Atlantic Capesize Index, three series (2024 blue / 2025 red / 2026 teal), y-axis 0-20k, x-axis Oct-25..Aug-26. Values already in the local `.md` (Calculated Index 18,137 / 17,887; T/C 93,150 / 87,650). |
| **banchero_costa** | **CHARTS REAL, ALREADY EXTRACTED** | Rendered p14: FFA forward curves (Capesize/Panamax/Supramax/Handysize) + JPY/USD. **64 LlamaParse outputs already contain FFA** and the local `.md` for 2026 W02 has the FFA table. |
| **clarksons** | **NO CHARTS** | Rendered p2: two clean S&P tables (FLC HAPPINESS, COLUMBIA RIVER), zero plots. The survey's "94.4% chartish" was WRONG. |
| **carriers p1** | **NO CHARTS** | Rendered p1: pure S&P table, 711 drawing objects of which 660 are thin rules. The survey's "100% chartish" was WRONG. |
| intermodal | **LIKELY CHARTS** | p8 has 12 images + 263 drawings; not yet rendered and confirmed. |
| lion | UNCONFIRMED | p1 has 1 image + 65 drawings; not yet rendered. |

## The lesson, twice over

The first survey used `drawing count > 100 OR images > 1` as a chart signal. It reported
carriers "86.7% chartish" and clarksons "94.4% chartish" - both **pure tables**, proven by
rendering. Rewriting it to require area-bearing shapes made it worse, not better
(carriers 100%), because table row fills are area-bearing too.

**A drawing count is not a chart.** Real charts need axis labels in a regular vertical
sequence plus a plotted polyline, and even that needed confirming by eye. Rendering is
the only test that has not lied in this project, and it is free.

So the survey script is retained as a *candidate finder* only. **Never treat its verdict
as a fact** - it produced two false positives in its first two versions.

## What this means for the plan

* **ssy** is the genuine next source: 519 documents, charts confirmed, and the chart
  series values are NOT yet extracted (the `.md` has the table values and the Calculated
  Index, but not the plotted monthly series).
* **banchero** needs nothing more - its charts are already captured.
* **clarksons and carriers page 1** have no charts; do not spend credits on them.
* intermodal and lion need one render each to settle.
