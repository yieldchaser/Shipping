# hellenic VesselsValue date convention - APPLIED (2026-10-04)

Status: **APPLIED on branch `auto/extract-fixes-2026-10-04`**. The carried item
("hellenic VesselsValue date convention - human call") was reduced to a measured
finding on 2026-10-04 20:0x and applied this run. The change shifts published
dates from the CRAWL date to the report's OWN date, matches the repo's shipped
`docs/intermodal_issue_date_verdict.md` precedent ("parse the publisher's own
cover line first, then the filename"), and is reversible on the branch. Data
CSVs are gitignored; only the two runners and this doc are committed.

## The finding (unchanged)

Both VV runners derived the report date from the FILENAME's `YYYY-MM-DD` prefix -
the CRAWL/fetch date, not the report's own date. Measured over the 261 VV report
pages (`corpus/02-hellenic/vessel_valuations/**/*weekly-vessel-valuations-report*.html`)
by parsing each page's own `<title>`:

| filename date vs page-title date | files |
|---|---|
| identical | 182 |
| **differ** | **78** |
| page title has no parseable date | 1 (`2026-09-29`, empty `<title>`) |

Direction of the 78 differences (page - filename, days): **-1 -> 69, -2 -> 8, +10 -> 1**
(the signature of a next-day crawl; the single +10 outlier is
`2022-07-16_...report-july-26-2022.html`, whose own title `July 26 2022` is authoritative).

Example: `2021-11-17_weekly-vessel-valuations-report-november-16-2021.html` ->
`<title>` `Weekly Vessel Valuations Report, November 16 2021`; the series stamped `2021-11-17`.

## The fix

In both runners the page's own title date is preferred, the filename is the fallback:

- `run_hellenic_vv_matrix.py`: new `_title_iso_date()` (built on the existing
  `page_title()` + `_title_date_token()`); `process_vv_item_async()` now sets
  `issue_date = _title_iso_date(page_title(h_path)) or filename_date or "UNKNOWN"`.
- `run_hellenic_vessel_valuations.py`: new `_page_title()`, `_title_date_token()`,
  `_title_iso_date()`; `parse_vv_html()` uses the same expression.

The 1 file with no parseable title falls back to its filename date, as before.

## A second, pre-existing defect found and fixed

The **sales** runner (`hellenic_vv_sales_series.csv`) had never received the
2026-10-03 dedup that the **matrix** runner got (`dedupe_report_copies`, see the
docstring in `run_hellenic_vv_matrix.py`). The collector stores 6 of the 261 pages
as copies under different names - 3 copies of the Feb 17 2026 report (all saved
`2026-02-19`) and 5 of the Mar 31 2026 report (all saved `2026-04-01`). Before the
fix these landed in the sales series 3x/5x, stamped with the crawl date: measured
**36 rows on 2026-02-19 (3 x 12)** and **45 rows on 2026-04-01 (5 x 9)**. The
dedup helper was ported to the sales runner and applied in `process_all()`.

## Measured result

| series | rows before | rows after | distinct dates | exact-dup rows | page-date collisions |
|---|---|---|---|---|---|
| `hellenic_vv_sales_series.csv` | 2,122 | **2,062** | 253 | 0 | **0** |
| `hellenic_vv_matrix_series.csv` | 12,350 | 12,350 | 236 | 15 (pre-existing) | **0** |
| `hellenic_vv_benchmark_sales_series.csv` | 124 | 124 | 42 | 0 | **0** |

- Sales rows fell 60 = 24 (Feb-17 3x -> 1x) + 36 (Mar-31 5x -> 1x). 2026-02-17 now
  holds 12 rows and 2026-03-31 holds 9 (was 36 / 45).
- All three series: **0 rows whose `source_file` maps to more than one `issue_date`**,
  **0 files still stamped with the crawl date**, **0 page-date collisions** (two
  different files resolving to the same page date).
- Of the 78 differing files, 71 are present in the sales series on their page
  date (the other 7 = 6 copies dropped by the dedup + 1 week with 0 deals);
  matrix 64/78 (rest carry no companion image), benchmark 18/78.
- Spot value: `2021-11-16` is present for its file; `2021-11-17` is gone.
- The matrix series' 15 exact-duplicate rows are **pre-existing** (identical count
  in the pre-fix backup `scratch/vvdate/hellenic_vv_matrix_series.csv`) - not
  introduced here.

## API cost

**Zero.** The matrix-image parses are cached in `data/extracted/cache_hellenic_vv/`
(266 entries) and the cache key is the IMAGE STEM (`img_path.stem`), not the date,
so the date change does not invalidate it - the re-run hit cache for every file.
The sales runner is pure HTML. No LlamaParse call was made (the whole matrix run
finished in seconds with 0 failure prints).

## Deliverable state

`data/extracted/md/hellenic/vessel_valuations/<year>/vv_<date>.md` = **255 files**
(2021:25 2022:46 2023:51 2024:48 2025:48 2026:37), 0 unpadded-name files.
Note: BOTH runners write md to the same `<year>/vv_<date>.md` path (a pre-existing
collision); the sales runner was run LAST so the surviving md is the sales format
(deals), matching the historical state. This pass wiped the directory first because
an unpadded-day bug in this run's first trial had left mixed names/formats.

## How to reproduce

```
PY312="/c/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe"   # llama_parse
"$PY312" scripts/extract/publishers/run_hellenic_vv_matrix.py
python3 scripts/extract/publishers/run_hellenic_vessel_valuations.py       # bs4 only
```

## Rollback

`git revert` the commit restores the filename-date convention; the CSVs/md rebuild
identically from the cached image parses (API-free).
