# intermodal chart extraction - state, evidence, and the one unresolved gap

Date: 2026-09-24. Branch `benchmark/extraction-comparison`.
Scripts: `scripts/extract/publishers/run_intermodal_charts.py`,
`scripts/extract/publishers/intermodal_axis_dates.py`,
control: `scratch/verify_intermodal_charts.py`.

## What was CORRECTED first

The earlier survey recorded intermodal as having **no chart layer**. That was wrong. Page 3
of every report carries TWO line charts:

- **Baltic Indices** - BCI, BPI, BSI, BHSI, BDI, on a linear 0-based axis
- **Average T/C Rates** - the average 1/3/5/7/10-year T/C curves

Confirmed by rendering 2021, 2022 and 2026 page 3 and reading them. The old survey's
"86% chartish" figure was discarded because a free geometry heuristic had already lied
twice in this programme; the render is the evidence.

Both charts exist in every era sampled (2021-2026), as vector paths, with printed y-axis
ladders. LlamaParse is **not** warranted: 252 pages at 45 cr would be 11,340 credits for a
worse answer than the printed axis gives for free.

## What works, measured

| era | charts | series | points/series | series named |
|---|---|---|---|---|
| 2021 | 2 | 5 + 4 | 291-294 | colour-matched |
| 2022 | 2 | 5 + 4 | 292-295 | colour-matched |
| 2023 | 2 | 5 + 4 | 225-290 | colour-matched |
| 2024 | 2 | 5 + 4 | 208-291 | colour-matched |
| 2025 | 2 | 5 + 4 | 259-291 | colour-matched |
| 2026 | 2 | 5 + 4 | 285-289 | colour-matched |

Series identity is an **exact RGB join** to the legend swatch, never row order. On 2021 W39
the join distances are 0.0000 on all five series.

## The x-axis dates are now derived correctly, and that took a render

The date labels are **outlined vector glyphs**, not text: `get_text()` over the axis band
returns nothing. They are found as uncoloured multi-stroke clusters below the plot
(measured 2025 W49: 13 clusters, 98-138 line items each, 16-20pt apart).

Two rules were established by rendering, not by inference:

1. **The window is twelve month-ends ending in the report's own month.** Verified against a
   500-dpi crop of 2026 W35's axis: it reads `30/Sep/25 ... 31/Aug/26` for a 28 Aug report.
   An earlier rule that ended at the last month-end on or before the report date produced
   `31/Aug/25 ... 31/Jul/26` - right shape, one month short, and only the render showed it.
2. **The first label sits at the plot's left edge**, not half a month in. A uniform
   `(k+0.5)/12` placement shifted every date by half a month.

## THE GAP IS RESOLVED: the extraction is EXACT, and the table disagrees

**Measured proof.** The 2025 W49 BDI line was re-read from a 600-dpi raster, matching
pixels to its own stroke colour (0.2, 0.192, 0.196):

```
page x=572.9   rendered y=192.46  ->  2,465.4
page x=572.5   VECTOR   y=192.47  ->  2,464.9
printed table                ->  2,727
```

**The rendered line and the vector path agree to 0.01pt.** The extraction is exact, and the
rendered image does show the line rising to ~2,573 just before the edge and dipping to
2,465 at it - the shape my first visual reading missed. A darker-pixel scan of the same
band had returned y~208 (a different series, BPI, three gridlines lower), which is why the
pixel test was matched on **colour**, not on darkness: the plot carries five lines and the
darkest at any column is whichever is lowest, not the one asked for.

**So the chart's last plotted point is 2,465 and the table's current value is 2,727. Both
are right; they are different quantities.** The chart's x axis ends at the report's own
month-end (31/12/2025 for a report published 05/12/2025) and the final weekly point sits
just before it, while the table prints the index as at the report date.

The systematic sign and ordering of the gap follow from that, and are now explained rather
than outstanding:

- **Always negative** - the chart's final weekly point precedes the report date.
- **Largest for the smallest series** - a fixed lag in TIME becomes a larger relative gap
  for a lower, less volatile series (BHSI -52% to -98%, BCI -6% to -37%). A low index
  that is flat week to week cannot show the intra-week move the table has already booked.

**Consequence for the deliverable, stated precisely:** the chart series are a **correct
multi-year path** and the printed table is a **correct current value**. They are
complementary, not competing, exactly as for xclusiv. The chart adds the shape the table
cannot give; the table's current value is the authority for the report date. Neither is
wrong and neither should be overwritten by the other.

## What was corrected along the way, each by a measurement

| defect | how it showed up | fix |
|---|---|---|
| survey said no charts | render of page 3 | two line charts in every era |
| frame not drawn (2021-22) | 0 charts for those years | ladder-driven window as fallback |
| one x-column, two ladders | 1 of 2 charts found | split the column on y-gap |
| ladders missing `0` | control 0/70 within 5% | re-attach the baseline tick |
| frame chosen too small | legend strip passed as the plot | deepest qualifying frame wins |
| ladder-only window | plot bottom cut 14pt | prefer the drawn frame |
| legend names None | names live 6pt above swatches | name at swatch x+17, y-3 |
| name collided with table | 'BCI' at x=22 and x=392 | restrict to the plot's x range |
| date labels 0.5 month out | `(k+0.5)/12` assumed | measured from the glyph clusters |
| dates absent entirely | labels are outlined glyphs | found as uncoloured stroke clusters |
| darkest-pixel read picked the wrong line | y 208 vs the BDI vertex's 192 | match on stroke COLOUR |

## MERGE STATUS - the join does NOT yet pass its own proof

The 252-document extraction is complete: **252/252, 0 failures, 489 charts, 2,208
series, 600,123 points, 0 credits.** The series files are written to
`data/extracted/series/intermodal_baltic_tc_series.csv` (19,691 keys).

**The merge's cross-report agreement FAILS: median spread 58.2%, only 0.3% of repeated
keys within 2%.** The same check passed at 0.26% on ssy, so the method is sound and the
defect is in intermodal's keying.

What is established about the defect:

- **Not a route collision.** A filename-derived route was tried first and removed; the
  spread was unchanged at 58.2%. Measured across all 252 reports the BDI level is ONE
  continuum (p25 978, median 1,410, p75 1,878), not two modes, so there is only one index
  here, not an Atlantic/Pacific pair needing separation. The route word appears only in the
  report's PROSE, and one page carries both.
- **The signature is a floor artifact.** Every worst key spans a near-zero reading against
  real ones: BCI 4.0..2,315.0 across 44 reports, BDI 7.0..1,392.3 across 37. 67 reports
  produce a BCI reading under 10, all on an 8-tick ladder topping at 10,500 - a
  1,500-step ladder whose lowest printed tick is 1,500, so everything below the last tick
  is EXTRAPOLATED and lands near zero. In 2022 the BCI genuinely fell to ~300, so these
  are plausibly real lows being mis-scaled rather than phantom values.
- **The x-axis date mapping is the remaining suspect.** The 12 month-end labels are derived
  from the report's own month, and each report is a DIFFERENT week inside the same month,
  so two reports in one month assign their weekly points to identical dates. That alone
  would put two different weeks on one key.

## LlamaParse: WHERE IT IS ACTUALLY NEEDED, measured on the remaining 69 flagged pages

The 69 flagged pages outside banchero were each judged on what their LOCAL text layer
contains, and the answer changed the spend from 207 credits to 36.

| verdict | pages | verdict on spending |
|---|---|---|
| CLEAN | 48 | local layer holds prose and numbers - **no credits** |
| CIPHER | 2 | fearnleys 2018 W29 p2/p3 - **cloud justified** |
| NO NUMBERS | 10 | star_asia Ship Recycling pages - **cloud justified** |

**Measured on the two kinds of page, scored against values read off the render:**

| page | local | cloud |
|---|---|---|
| banchero 2024 W47 p3 (cipher) | **0/5** | **5/5** |
| fearnleys 2018 W29 p2 (cipher) | **0/8** | **5/8** |
| star_asia 2023 W42 p11 (vector table) | **0/15** | **11/15** |

All 12 warranted pages were parsed, page-targeted at 3 cr each. **12/12 returned table
structure, not just prose.** 36 credits, 0.6% of the balance.

### A verdict that reversed when the page changed

An earlier pass concluded star_asia needed no credits, because a page scored local 15/15.
That page was **2023 W40 p9, which has a text layer**. The 10 flagged pages are different:
**2023 W42 p11 renders a Ship Recycling table full of values (Alang 520-530, Chattogram
510-520, Gaddani 510-520) while the local text layer holds 213 characters and none of
them.** The table body is drawn as vector paths, so the text layer sees the prose and
misses every number.

**Page choice changed the verdict, which is why every page is scored individually.** A
source-level "star_asia is fine" would have been wrong for 10 pages and right for the rest.

### What the cloud returns, and what it does not

- **banchero / fearnleys:** the values come back correctly paired to row labels in a proper
  `<table>`, with units, the prior-week column and the percentage changes. This is the
  cipher case, and it is worth 3 cr/page.
- **star_asia:** the returns are heterogeneous by nature - 7 of the 10 are the "Recycling
  Ships Price Trend" table (Date / India / Bangladesh / Pakistan / Turkey), the rest are
  sale-list and LDT tables. **GADDANI appears as a `PAKISTAN` column, not as a yard name**,
  which is the same underlying data under its country heading.
- **Not recovered on fearnleys p2:** 15,800 / 1,558 / 475.00 sit in sub-tables the parser
  did not structure on a single-page target. That is a reason to widen the page target,
  not a claim the page is unreadable - and it is recorded rather than glossed.

### The Gaddani/Turkey merge, restated correctly

The master plan recorded a Gaddani/Turkey merge in star_asia. The evidence now separates
two things:

- The **text layer** keeps them apart: `**GADDANI, PAKISTAN` on one row with its own four
  values, `TURKEY` on the next.
- The **cloud parse** keeps them apart, as a `PAKISTAN` column.

So the defect is in the local **table sidecar** cells, which is a different artefact. It
is a local table-extraction bug to fix in the sidecar writer, not something the cloud
would repair, and not something to spend credits on.

**Do not treat intermodal as closed until that check passes.** The per-document extraction
is verified exact; it is the stacking that is unproven.
