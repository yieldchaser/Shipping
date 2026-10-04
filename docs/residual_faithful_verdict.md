# Residual re-measurement verdict (2026-10-04 19:2x, unattended run)

No extraction job was running (live python.exe set = Hermes gateway). All named sources
are CLOSED (md counts >= distinct PDFs). This run took the OPEN items still carried in
`docs/series_verification_ledger.md` and `docs/MASTER_EXTRACTION_PLAN.md` item 2 and
MEASURED each against the source's own page. Result: the last open ledger item is a
non-reproducible residue (already gone), and three carried "suspicious value" items are
FAITHFUL to the publisher. Evidence below is page-level, not a re-run of a metric.

## 1. bancosta freight_rates residue (numeric `unit` / `DRY_BULK` sector) - CLOSED
Ledger's only remaining "STILL OPEN" (`docs/bancosta_ffa_verdict.md` line 119: branch 11).
Measured on the current file (`data/extracted/series/bancosta_freight_rates_series.csv`,
20,321 rows):

| check | result |
|---|---|
| rows whose `unit` matches a bare number | **0** (was 33 numeric units) |
| sector values | DIRTY_TANKER 6,554 / CLEAN_TANKER 5,078 / SUPRAMAX 4,397 / PANAMAX 2,158 / CAPESIZE 2,134 |
| any `DRY_BULK` sector row | **0** (was 80) |
| units | usd/day 14,366, ws 5,010, usd/t 661, usd/mt 241, days 42, usd mln 1 |

The residue named by the ledger is not present any more (the FFA-branch fix + later
reruns cleared it). CLOSED as non-reproducible.

### The two genuine-looking outliers are FAITHFUL to the publisher
Spotting them required no vision - the source text layer carries the values.

* `TC20 LR2 AG-UKC (90k) | unit=usd mln | 16,606,250 | 16,500,000`
  `banchero_costa_2026_W38` p10, text layer at y=436.1: `'usd' 'mln' '16,606,250' '16,500,000'`
  (Calibri 7.1, char bboxes 182..217). The publisher prints it verbatim.
* `TC14-TCE MR USG-UKC | unit=usd/day | 7,390,000 | 6,190,000`
  same page, y=561.8: `'usd/day' '7,390,000' '6,190,000'` (Calibri 7.1). Verbatim.
Both are the publisher's own magnitudes (the row set is internally inconsistent: MR basket
28,460/day vs a single MR route at 7.39M/day). A wrong PUBLISHED value is not our defect;
storing it faithfully is correct. Do NOT "fix" these.

## 2. star_asia 5-year history, `ALIAGA, TURKEY` year_2021 = 26 - FAITHFUL
`data/extracted/series/star_asia_5y_history_series.csv` records 2026 W01/W03/W04
`26,320,250,320,370` and 2026 W05+ `240,330,310,320,360`. The 2021 column is a fixed
year, so a change looked like a defect. It is not ours.

Rendered the cell (`star_asia_2026_W01_Market-report-Week-1-2.pdf` p9, x 228-272, y 602-615
at 600 dpi) and read the ink: exactly TWO glyphs, a `2` and a `6`. The text layer agrees -
rawdict has only `'2'` (x=243.5) and `'6'` (x=249.3), nothing after. The PDF literally
prints `26`.

Separately confirmed the parsed rows match the page for both eras:
* W01 p9 y=540 header `DESTINATION 2021 2022 2023 2024 2025`; GADDANI row y=591.4 =
  `460 580(2022, y+1.6 offset) 540 500 450` = series `460,580,540,500,450`.
* W05 p9 y=538 header identical; GADDANI y=589 = `415 600 540 520 430` = series verbatim.
So the week-to-week change in a "fixed" year is the PUBLISHER re-issuing the rolling
5-year table, not our mis-parse. W01-W04 (Week 1-2 double issue + W03/W04) share one
table; W05 onward another.

## 3. star_asia recycling-yard label fusion - DISPLAY-ONLY, no data loss (NOT fixed)
`md/star_asia/**` carries 177 rows whose label cell absorbed the table footnote, e.g.
`| TURKEY *For Non-EU ships. For E.U. Ship, the prices are about USD 20-30/ton less |`
and `| GADDANI, PAKISTAN TURKEY |` (1 doc). The md is rendered by
`run_star_asia.py:build_md` (liteparse markdown); the footnote sits in the label column on
the same y as the Turkiye row's numbers, so liteparse merges them.

Checked before treating it as worth fixing (skill rule): the typed layer is CORRECT.
`data/extracted/series/star_asia_demolition_series.csv` is 3,120 rows = 194 weeks x 4
destinations x 4 segments, ZERO weeks with a missing cell, and carries the four yards
(Alang / Chattogram / Gaddani / Aliaga) with clean labels - it is built by
`extract_indicative_scrap_table`, not from the split table. The polluted label lives only
in the generic `.tables.json` (1 of 5,566 tables has a data-row header: the CHATTOGRAM
continuation) and the md. **No consumer reads the polluted label.** Fixing it needs a
liteparse re-render of 193 docs for a display-only gain - deferred, not zero-cost.

## Method note
No vision tool in this session. Every "faithful" call above is backed by the source's own
TEXT LAYER (word bboxes) or by a rendered-glyph pixel read (ASCII ink profile), which is
the documented substitute for looking. Population of each claim is stated.

## 4. star_asia duplicate-key + exact-duplicate sweep - all PUBLISHER-side, not ours
Duplicate-key sweep over the 10 star_asia series (key = issue_date, report_week, source_file):

| file | rows | exact dups | distinct docs |
|---|---|---|---|
| star_asia_deals_series.csv | 3,349 | 2 | 195 |
| star_asia_ferrous_scrap_series.csv | 771 | 1 | 124 |
| (other 8 files) | - | 0 | - |

* `star_asia_2023_W41` and `star_asia_2023_W42` BOTH carry issue_date 2023-10-14 /
  week 41 -> the demolition series has 32 rows on 2023-10-14 instead of 16. Cause: the
  W42 PDF's COVER is misprinted - p0 reads `WEEK 41 - October 14, 2023` on the W42 file
  too (its commentary and recycling prices differ from W41's, so it is a distinct issue).
  Our stamp is faithful to the printed cover. The rows stay distinguishable by
  `source_file`. NOT changed: inventing a corrected date would store a date the publisher
  never printed.
* Exact duplicates are printed twice by the publisher: `JOINT LUCK TANKER 2,063 24.12.2022
  AWAITING` appears on TWO consecutive rows of star_asia_2023_W01 p11 (text layer), and
  WHITE PALM twice on W51 p12. Our duplicate is faithful.

## Bottom line
Every carried "suspicious" item measured this run resolves to the publisher or to a
non-reproducible note. No extraction defect was found to fix; nothing was changed in the
data. The ledger's last open item (bancosta freight_rates residue) is CLOSED.
