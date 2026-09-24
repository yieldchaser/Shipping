# xclusiv chart extraction - PROVEN, and what a roll-out actually costs

Date: 2026-09-24. Commit: see git log. Status: capability verified on TWO layouts;
roll-out NOT started, because it does not fit the remaining credit budget.

## What is proven

`specialized_chart_parsing` (tier `agentic_plus`) returns vector-chart series as
STRUCTURED TABLES in the items tree. Verified twice, on deliberately different layouts:

| era | doc | tables | TCE-like series recovered |
|---|---|---|---|
| 2026 | xclusiv_2026_08_31 | 6 | 3 |
| 2026 | 22_09_2026 (Sep) | 6 | 3 |
| 2022 | xclusiv_weekly_2022_12_19 | 5 | 3 |
| 2022 | xclusiv_weekly_2022_12_27 | 5 | 3 |

Chart page is **page 3 in every sampled era** (2022, 2023, 2024, 2025, 2026), so a
single-page target is sufficient corpus-wide.

## The 2022 layout is DIFFERENT - and yields MORE

2022 page 3 carries four charts with different series names and a wider date range:

```
2022: Crude Tanker Spot Earnings    VLCC (TCE) / SUEZMAX (TCE) / AFRAMAX (TCE)
      Product Tanker Spot Earnings  MR (TCE) / MR ATLANTIC (EGC TCE) / PAC BASKET
      Tanker 1y TC (Crude)          VLCC 1y TC / SUEZMAX 1y TC / AFRAMAX 1y TC
      Tanker 1y TC (Product)        MR 1y TC / MR1 1y TC
      x-axis Nov-20 -> Jul-22,  y-axis -30,000 -> 70,000

2026: five series, x-axis Aug-21 -> Aug-26, y-axis 0 -> 385,000
```

Recovered 2022 series (excerpt):
```python
['Month', 'VLCC (TD3C)', 'SUEZMAX (TD20)', 'AFRAMAX (TD7)']
['Dec-20', '8000', '3000', '-1000']      ['Feb-21', '1000', '1000', '-6000']

['Month', 'VLCC 1y TC (Eco)', 'SUEZMAX 1y TC (Eco)', 'AFRAMAX 1y TC (Eco)']
['Dec-20', '25,000', '19,500', '16,500']  ['Feb-21', '26,500', '19,000', '16,000']
```

## NEGATIVE TCE IS REAL - an earlier doubt was wrong

The 2026 extraction produced `VLCC TCE: -10000`, `Min: -32000`, and I flagged those as
"unusual, deserves scrutiny". They are genuine market values, not parser errors. The
2022 extraction independently confirms it across many periods:

```
VLCC (TD3C):  -2000, -5000, -2000, -1000
AFRAMAX (TD7): -1000, -6000, 15000, -2000
```

Independent corroboration from the rendered 2022 page: the prose states
*"VLCC average T/C ended the week up at USD -22,707/day"* - a negative TCE printed on
the page itself. **Lesson: an unusual value is not a wrong value. Check it against the
source before doubting the extraction.**

## Chart values are chart-resolution, not dollar-precision

Cross-checked against the prose on the same page (2026): VLCC 335,000 chart vs
334,066 stated (0.3%); MR Pacific 42,000 vs 42,677 (1.6%); Suezmax 180,000 vs 184,914
(2.7%). MR Atlantic is 13% out because its axis is compressed (~125k span).

So the chart gives the **shape and level** of a multi-year series; the prose gives
dollar precision for the current week. They are complementary and cross-check each
other. Always store both.

## COST - why the roll-out is not simply started

```
266 docs x 1 chart page x 45 cr = 11,970 credits   -> EXCEEDS remaining budget (~7,000)
cost_effective tier (3 cr)      =    798 credits   -> but NO chart parsing at that tier
```

`cost_optimizer` is rejected below `agentic` (HTTP 422), and the only tier with
`specialized_chart_parsing` is `agentic_plus` at 45 cr/page.

Options, for the user to choose:
1. **Ration by recency** - most recent N documents first. 2026 alone is 40 docs =
   1,800 cr; 2025 adds 51 = +2,295; 2024 adds 51 = +2,295.
2. **Rotate keys** - the user has 4-5 accounts x 10,000 credits. With key rotation the
   full 11,970 cr is affordable in 2 accounts, but only with no overlap/spoilage.
3. **Skip the roll-out** - the local `.charts.json` already covers xclusiv, and the
   payback is on the multi-year series specifically.
4. **Dedupe first** - consecutive weekly reports repeat largely the SAME series with
   one new point each. The marginal value of parsing all 266 may be far lower than the
   count suggests; a sampled/quarterly cadence may capture the same shape.

**Recommendation: option 4 first (dedupe/justify), then option 1 (recency-ordered),
and rotate keys only if the resulting spend is acceptable.** Spending 12,000 credits to
learn a curve that changes by one point per week is not obviously good engineering.
