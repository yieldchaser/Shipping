# Quarantined: fearnleys_md chart and prose series (2026-10-12)

These six files were produced by the old `scripts/extract/publishers/run_fearnleys_md_full_power.py`
and `export_fearnleys_md_excel.py` (now `scripts/_quarantine/export_fearnleys_md_excel.py.QUARANTINED`).
They are wrong and must not be used, cited or fed to the GraphRAG build.

| File | How it was made | Why it is wrong |
|---|---|---|
| `fearnleys_md_coal_futures_spread_series.csv` | Line end-points read off `P5 vs Newcastle Coal Futures Spread Lead.png` with hardcoded axis ranges | The real chart axes are 5,000–25,000 (left, steps of 2,000) and −15 to 10 (right). For 2026-10-07 the CSV stores P5 = 10,273.97 while the chart shows about 19,100, and a spread of −20.82, below the axis minimum. |
| `fearnleys_md_tc_vs_asset_series.csv` | Same method on the four "1yr TC vs asset" charts | Hardcoded axis ranges, not the printed ticks. |
| `fearnleys_md_vessel_tightness_series.csv` | Same method on the tightness and ballaster/laden charts | Hardcoded ranges; the fallback path stores raw pixel y positions as values. |
| `fearnleys_md_macro_correlations_series.csv` | Same method on the iron ore, copper and steel-mill lead charts | Hardcoded axis ranges. |
| `fearnleys_md_shipment_volumes_series.csv` | Regex over the weekly prose | The regex grabs the wrong number. For 2026-06-17 it stores Panamax YTD volume growth 4.6%, but the report says volumes were up 5.2% and that 4.6% is supply growth; the Capesize 5.8% / 1.5% sentence is missed entirely. |
| `fearnleys_md_master_econometric_series.xlsx` | Workbook of the five CSVs plus a hand-typed chart-recurrence sheet | Built on the above. |

All Fearnleys research charts are raster PNGs with no embedded data, so no exact values can be read from
them. What the fearnleys-md pipeline now keeps is exact only: the report text, the API data tables, the
printed Cape composite-model tables (transcribed and verified against OCR), and the chart titles and
images. See `data/extracted/md/fearnleys-md/<year>/<stem>.tables.json`.
