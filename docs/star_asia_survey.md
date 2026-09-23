# Star Asia survey (source 2)

Measured 2026-09-24. 193 PDFs at corpus/01-brokers/star_asia
(2022:17 2023:49 2024:48 2025:47 2026:32), live, newest W38 21-Sep-2026.

## Layout
- 16-21 pages per document.
- Page 1 is prose (market commentary); data pages are deeper in.
- Raster-heavy pages land on 4/7/9/11/12 consistently across 2024 and 2026.
  2022 is looser (an earlier era).

## Charts: raster, and mostly REDUNDANT
ZERO vector chart pages in any year - unlike advanced_shipping, whose charts are
vector. The vector axis-calibration method therefore does not apply.

Checked 2026 W19 p11 by rendering it and reading it:
  * the page carries a "Reported Sales" table AND a bar chart
  * the TABLE is selectable text: JENNY LUCKY / GAS CRUSADER / DONG YONG,
    LDT 7,176 / 1,526 / 2,334, prices 460 / 550, DELIVERED GADANI etc
  * the CHART's printed data labels (1,312,861 / 782,877 / 518,090 ...) are NOT
    text - they are part of the raster image
  * but the chart is titled "Comparison of Total LDT Sold, 5 Years (2022-2026)",
    i.e. an AGGREGATE of the Reported Sales deals we already extract as text

So the chart adds no new information beyond the table it summarises. Same
pattern as the advanced_shipping fused panel: the graphic duplicates data held
as text.

## Numbers
ISO / US convention: 29,580 means 29580 (comma = thousands).
NOT the European 60.000 = 60000 convention. Do NOT reuse that parser path.
Spot-verified: page text contains 1,526 / 2,334 / 7,176 as expected.

## Strategy for Star Asia
1. Extract the TEXT tables (reported sales, price tables, S&P grids) - these
   carry the unique vessel-level deal data.
2. Do NOT use vision for charts by default: the charts are aggregates of the
   tables. Revisit only if a chart is found carrying a series absent from text.
3. Reuse from source 1: the resumable runner, the pdf-inspector + liteparse
   value-anchored table merge, the render-and-look verification loop.
4. Set ocr_enabled=False (the 20x speedup; 0 of 312 sampled pages needed OCR).

## Open item
Pages 4/7/9/12 rendered but not all read yet - confirm each holds a text table
before declaring the publisher chart-free. Do not assume from one page.
