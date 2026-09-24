# Banchero Costa (source 7) - COMPLETE and verified

## Result
data/extracted/md/banchero_costa/   : 243 .md + 243 .tables.json
  243/243 documents, 0 failures, 15 seconds.

Route tally across the corpus: {'text': 243, 'image-heavy': 156, 'garbled': 59}
(the routes are PER-ROW classifications, see below)

## The approach: reuse, don't redo
Banchero already had a complete per-document extraction in the repository:

    data/extracted/corpus/shipbrokers/banchero_costa_<yr>_<wk>/
        text.jsonl   (bbox, text, max_font, page, route)
        tables.jsonl, pages.jsonl, charts/
    data/extracted/banchero_deals.parquet   3,120 deal rows,
                                            report_date 2021-06-28 -> 2026-08-24
        cols: vessel, imo, vessel_type, dwt, built, buyer, seller,
              price_usd_m, ss_due, dd_due, delivery, comments, yard

Verified by reading it before building on it: the commentary prose is intact and
matches the rendered page. So the only MISSING piece was the .md TARGET FORMAT.
Re-reading 243 PDFs would have duplicated good existing work.

`scripts/extract/publishers/banchero_md.py` converts the existing text.jsonl into
.md rather than re-extracting. Headings are derived from max_font (measured: titles
22-28pt against ~11pt body prose, so a 13pt threshold separates them) instead of a
per-document hardcode.

## Verification against a rendered page (2026 W20, read by eye)
    section title "CHINA SOYBEAN IMPORTS"                 PRESENT
    prose opening "Soybeans are one of the most"          PRESENT
    statistic "+4.6% year-on-year to 159.9 mln tonnes"    PRESENT
    "accounted for 73.2% of global soybean exports"       PRESENT
    "Rizhao (9.6 mln t in Jan-Dec 2025)"                  PRESENT
    banner furniture "MARKET REPORT"                      correctly stripped

## The 'garbled' route is NOT a prose defect - checked, not assumed
59 documents carry a 'garbled' route, so this was investigated rather than waved
through. The flag applies PER ROW, not per document. The garbled rows are CHART
AXIS LABELS:

    '!\n"!#!!!\n$!#!!!\n%!#!!!\n&!#!!!'          short punctuation runs
    '67"\'%F\n!"#$#%&\n"\'#-\'"\n(I)H*'            axis tick sequences

The PROSE rows in those same documents are clean. Measured on
banchero_costa_2024_W47 (a 'garbled' doc): the .md is 32,475 bytes with 2,157
alphabetic words and a VOWEL RATIO of 0.36 against ~0.38 for English, i.e. real
English text, not mojibake. Sample prose from it:

    "In Jan-Dec 2023, global crude oil loadings went up +4.7% y-o-y to 2186.8 mln
     tonnes, excluding all cabotage trade, according to vessels tracking data from
     Refinitiv. ..."
    "Dongjiakou (31.7), Dalian (29.5), Qingdao (28.1), Zhanjiang (23.5), ..."

This matches the known Banchero glyph issue: its charts map glyphs to ASCII
punctuation, which `decode_mojibake.py` structurally cannot fix (0 Latin-Extended
glyphs present). It affects chart axis labels only, and the chart values are not
needed - the deal ledger is already extracted to parquet.

## Status
Banchero Costa is the 7th source done. No numeric extraction from the PDFs is
needed: the deal ledger already exists in structured form.

## Carried-forward cleanups (unchanged, still open)
- 22 scripts still reference the DELETED `reports/` directory, including
  update_intermodal_tc_rates.py (intermodal's live pipeline cannot update until
  that path is fixed) and banchero_deals.parquet's own source_file column.
- The Fearnleys S&P sync has not updated for days - a fetcher failure, not a PDF
  problem.
