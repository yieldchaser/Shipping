# ALLIED (corpus/archive/allied) - per-source survey

Measured 2026-10-06 source-by-source cron run. 203 PDFs, 2021-2024
(`2021:50 2022:97 2023:49 2024:7`). Two document classes, both from
Allied Shipbroking Inc.

| class | pages/doc | content |
|---|---|---|
| `ALLIED-SnP-Statistics-Week-NN` | 9 | dense aggregate S&P statistics (sector fleet tables, sales/month, values) |
| `ALLIED-Weekly-Market-Report` (2021-22) / `Allied-Weekly-Market-Review` (2023-24) | 12-14 | prose, indices (BDI/BCI/...), TCE tables, indicative values, **Reported Transactions** (deals) |

## Number convention
**Pure ISO everywhere** (period-thousands absent, comma-decimals absent;
comma-thousands present e.g. `318,744`). Simplest convention of the 4 archive
sources - the same ISO assumption the existing broker runners use.

## The Reported Transactions table (the deliverable shape)
Matches the existing `<source>_sales_series.csv` family. Columns:
`Size | Name | Dwt (or TEU/CBM) | Built | Shipbuilder | M/E or Coating or Gear |
Price | Buyers | Comments`.

Layout is **NOT stable across years - derive columns from each page's own
header row** (skill rule):
- 2021 pages print an **M/E** column; 2024 dropped it and added **Coating**.
- A single page carries **multiple sub-tables**, each with its own header row
  and its own column x-positions: on 2021 W26 page 6 there are two secondhand
  headers (one with `Coating`, one with `Gear`) and page 7 a **container** header
  (`TEU` in place of `Dwt`); 2024 page 8 has `TEU` and `CBM` tables.
- The parser therefore segments every page by header row and derives a separate
  column geometry per header.

### Column assignment: nearest header anchor
Neither a midpoint cut nor a header-left cut works: values sit at varying
offsets from their header (`NISSOS` starts 27 pt LEFT of the `Name` header;
`$` starts 5 pt left of `Price`), and wrapped Shipbuilder/Coating text extends
across a midpoint. The rule that holds is **assign each word to the column
whose header x-start is nearest** to the word's x-start.

## Known best-effort residuals (disclosed, not hidden)
The `.md` (full page text) is EXACT and is the primary deliverable. The typed
`allied_sales_series.csv` deals layer is best-effort:
- **Container sub-tables** (`SUB`/`FEEDER` rows): the publisher prints TEU and
  Built as one text token (`26642009`), so `dwt` is blank and `built` is fused.
- **En-bloc rows**: a group price sits on the lead row only; member rows show
  `each` and a blank price.
- `N/A` / `rgn $` rows carry no numeric price (the page has none).

## Liveness gate
Newest archive content = 2024 (~700 d) -> **BACKFILL_ONLY, never CONSTRUCT**.
