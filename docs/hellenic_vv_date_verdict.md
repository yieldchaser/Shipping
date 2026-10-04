# hellenic VesselsValue date convention - MEASURED (2026-10-04)

The item carried in `docs/OVERNIGHT_STATE.md` as "hellenic VesselsValue date convention
(229 dup rows) - human call" is here reduced to a measured, decision-ready finding. No
delivered series was rewritten by this run: the convention is a recorded human call and the
change shifts published dates, so it is documented with the exact fix rather than applied
unattended.

## What the runners stamp today

Both VV runners derive the report date from the FILENAME's `YYYY-MM-DD` prefix:

- `run_hellenic_vessel_valuations.py:253-254` (`-> hellenic_vv_sales_series.csv`)
- `run_hellenic_vv_matrix.py:284-285` (`-> hellenic_vv_matrix_series.csv`,
  `hellenic_vv_benchmark_sales_series.csv`)

That prefix is the CRAWL/fetch date, not the report's own date.

## The page carries its own date - and it differs on 78 of 261 files

Measured over the 261 VV report pages (`corpus/02-hellenic/vessel_valuations/**/*weekly-vessel-valuations*.html`),
extracting the page's own `<title>` (`"Weekly Vessel Valuations Report, November 16 2021"`):

| comparison (filename date vs page title date) | files |
|---|---|
| identical | **182** |
| differ | **78** |
| page title has no parseable date | 1 (`2026-09-29`, empty `<title>`) |

Direction of the 78 differences (page - filename, days): **-1 -> 69, -2 -> 8, +10 -> 1**.
i.e. the filename is the day after (or two days after) the report's own date - the signature
of a next-day crawl. The single +10 outlier is `2022-07-16_...report-july-26-2022.html`
(file stamped 10 days BEFORE its own report date; the page title `July 26 2022` is authoritative).

Example (ground truth read from the page, not another extractor):
`2021-11-17_weekly-vessel-valuations-report-november-16-2021.html` -> `<title>` and `<h1>` both
`Weekly Vessel Valuations Report, November 16 2021`; the series stamps `2021-11-17`.

## The delivered series carry the crawl date

- `hellenic_vv_sales_series.csv`: **77 of the 78** differing crawl-dates are present in the
  series (`2021-11-17` yes / `2021-11-16` no); 2,122 rows, 253 distinct dates.
- `hellenic_vv_matrix_series.csv`: 66 of 78 present; 12,350 rows, 236 distinct dates.
- `hellenic_vv_benchmark_sales_series.csv`: 24 of 78 present; 124 rows, 42 distinct dates.

## Switching to the page's own date is LOSSLESS

For the 236 `source_file` values in `hellenic_vv_matrix_series.csv`, 235 resolve to a page
title date and those 235 page dates are **all distinct -> 0 collisions**. A switch therefore
only shifts those dates earlier by 1-2 days; it drops no rows and merges no weeks. The 1
unresolved file (`2026-09-29`, no page title) falls back to the filename.

## The exact fix (one expression per runner)

`run_hellenic_vv_matrix.py` already has `page_title()` and `_title_date_token()`; add an
ISO converter and change line 285 from

```python
issue_date = m_date.group(1) if m_date else "UNKNOWN"
```
to prefer the page's own title date, falling back to the filename:
```python
issue_date = _title_iso_date(page_title(h_path)) or (m_date.group(1) if m_date else "UNKNOWN")
```
and the same one-line change at `run_hellenic_vessel_valuations.py:254`.

**Precedent:** `docs/intermodal_issue_date_verdict.md` (2026-09-28) applied exactly this rule -
"parse the publisher's own cover line first, then the filename; an unknown date is written
BLANK" - and is the repo's established convention. The 2026-10-03 dedup
(`dedupe_report_copies`) deliberately left the date convention untouched because it was scoped
to collapsing the 3x/5x copies; it does not bless the crawl date.

## Recommendation

Apply the one-line change in both runners and re-run (the 261 matrix-image parses are already
cached in `data/extracted/cache_hellenic_vv/` - 266 entries - so the re-run is API-free). It is
the publisher's own date, matches the intermodal precedent, and is measured lossless. Held as a
human call only because it shifts published dates; the change is reversible on the branch.
