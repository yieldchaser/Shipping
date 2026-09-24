# xclusiv charts: the roll-out is NOT worth 12,000 credits

Date: 2026-09-24. Status: capability PROVEN, economics DISPROVED. Recommendation: do not
run the 266-document roll-out. Spend ~1,000 credits instead.

## The capability is real

`specialized_chart_parsing` (tier `agentic_plus`, 45 cr/page) returns vector-chart
series as structured tables. Verified on both eras, 2/2 documents each:

| era | doc | tables | TCE-like series |
|---|---|---|---|
| 2026 | 08_31, 22_09 | 6 | 3 |
| 2022 | 12_19, 12_27 | 5 | 3 |

Chart page is **page 3 in every sampled era** (2022–2026).

## Why the 266-document roll-out is poor engineering

### 1. The series are ROLLING WINDOWS, not cumulative history

Measured spans of the paid documents:

```
2022-12-19 report  ->  Apr-21 .. Oct-22
2022-12-27 report  ->  Apr-21 .. Oct-22      <- SAME window, one week later
2026-08-31 report  ->  Aug-21 .. Feb-26
2026-09-22 report  ->  Mar-22 .. Sep-26
```

Each report carries roughly a **2-year trailing window**. Consecutive reports therefore
cover the SAME dates. Parsing all 266 documents would re-read the same overlapping
window ~250 times.

### 2. A later report strictly dominates an earlier one

A 2026 report already contains Aug-21→Feb-26, which covers nearly all of what the 2022
reports (Apr-21→Oct-22) contain. So the marginal value of an older document is
**recovering the small slice the newer window no longer covers** - and 2021's charts
(6 pages, different layout, no date labels on p3) need their own handling.

### 3. Weekly reports revise the SAME 13 sampled points rather than adding new ones

Comparing two consecutive 2022 reports directly:

```
total data points across series  : 52
shared with the previous report  : 52   (100%)
genuinely NEW points             : 0    (0.0%)
existing points that CHANGED     : 51   (98%)
```

Example (`VLCC 1y TC Eco`): `Dec-21 27,000 -> 24,000`, `Oct-21 25,000 -> 23,000`.

**Interpretation, established by rendering the page and counting:** the chart plots a
dense weekly line, but its x-axis carries only **13 labels at 2-month intervals**
(Dec-20 ... Dec-22) with a 0–60,000 y-axis. The parser therefore returns 13 SAMPLED
readings at the labelled positions, and a one-week shift of the line moves those
readings. That is why 98% "change": they are not revisions, they are re-samplings.

**Consequence:** 266 x 45 = **11,970 credits** buys a curve that a handful of documents
already carries, at ~1/13th resolution. That is not a good trade.

## What the paid samples already give us, for ~270 credits

Four documents (2022 x2, 2026 x2) already delivered 4 series x ~13 points each, plus
the wet secondhand price table with 12m change, 12m diff and 2-year averages:

```python
['Month', 'VLCC 1y TC (Eco)', 'SUEZMAX 1y TC (Eco)', 'AFRAMAX 1y TC (Eco)']
['Dec-20', '25,000', '19,500', '16,500']  ['Oct-22', '47,500', '38,000', '37,500']
```

## RECOMMENDATION

**Do not run the 266-document roll-out.** Instead:

1. **Annual snapshot, ~12 documents** - one per year (2021 needs its own page/layout
   check; 2022-2026 are all page 3). 12 x 45 = **540 credits**. Because windows are
   ~2 years and roll forward, a yearly cadence loses at most one year of overlap and
   captures the full long-run shape.
2. **Spend the remaining budget on sources that need it** - the remaining 69 flagged
   pages across intermodal/star_asia/affinity/agora/xclusiv/fearnleys is ~207 credits,
   and the advanced_shipping control is ~12.
3. **Keep the 4 paid documents as the validated reference set** for the series names,
   the sampled-point caveat, and the negative-TCE finding.

If the user later decides the full history is worth it, key rotation makes it
affordable (2 accounts) - but it should be a deliberate choice about needing weekly
resolution, not a default. The marginal point per week is not currently worth 45 credits.
