# Duplicate-key census in data/extracted/series/*.csv - CLOSED (2026-10-04 23:1x)

The state's "NEXT RUN: diagnose the small ones" item (OVERNIGHT_STATE line
~592, the 265-row census) is here re-measured on the CURRENT files and every
remaining row is accounted for by source evidence. **No genuine dedup defect
remains.**

## Current census (all 175 `data/extracted/series/*.csv`, key = every column
except `source_file`)

**31 duplicate-key rows** (was 265 at the older census). Per file:

| file | dup-key rows | verdict |
|---|---|---|
| `hellenic_vv_matrix_series.csv` | 15 | single-date image artefact (below) |
| `xclusiv_sales_series.csv` | 5 | left-as-is faithful (previous run) |
| `star_asia_demolition_series.csv` | 4 | faithful W41/W42 cover misprint |
| `poten_top_charterers_series.csv` | 2 | left-as-is faithful (previous run) |
| `star_asia_deals_series.csv` | 2 | faithful W41/W42 cover misprint |
| `carriers_sales_series.csv` | 1 | documented publisher LAMBADA double print |
| `star_asia_ferrous_scrap_series.csv` | 1 | left-as-is faithful (previous run) |
| `star_asia_snp_sales_series.csv` | 1 | NEW: faithful W41/W42 cover misprint |

## The two that were NOT previously diagnosed

**star_asia `_demolition` 4 / `_deals` 2 / `_snp_sales` 1 - FAITHFUL.**
All 7 rows carry `issue_date 2023-10-14`, `report_week 41` but come from TWO
DISTINCT source files:
`star_asia_2023_W41_Market-report-Week-41.pdf` and
`star_asia_2023_W42_Market-report-Week-42.pdf`.
Verified from the page: the **W42 PDF's own cover prints
`WEEK 41 - October 14, 2023`** (`pymupdf` page-0 text of
`corpus/01-brokers/star_asia/2023/star_asia_2023_W42_Market-report-Week-42.pdf`).
Our stamp is faithful to the printed cover; the rows stay distinct by
`source_file`. `/snp_sales` (vessel `MSC REN V`, 18.5 $M) is the same class -
it appears in both under the same misprinted date.

**hellenic_vv_matrix 15 - single-date image-transcription artefact (NOT fixed).**
All 15 are on one date, `2026-01-28`, and all report the SAME `source_file`
twice. Traced to the cached parse
`data/extracted/cache_hellenic_vv/2026-01-28_..._img2.md`, whose markdown
repeats its `Year 10` row (`year rows found: ['10','5','10','15','20','25']`,
`Counter({'10':2})`). The 4,613-byte source `.html` holds 0 tables, so the
series is built from the embedded image parse. Single-date, pre-existing
(the 20:5x run noted "matrix's 15 are pre-existing"), and **no consumer reads
the file** (0 hits in `index.html`). Recorded, not chased - with no vision tool
the image itself cannot be re-read to decide faithful-vs-artefact, and the fix
is worth zero to any display.

## Method
`scratch`-free inline scan: for each CSV, key = all columns except `source_file`,
count keys with >1 row. Ground truth for the star_asia rows: the PDF's own
cover line, read with `pymupdf`.
