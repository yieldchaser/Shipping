# ism residual agreement tail - verdict: PUBLISHER-SIDE, not an extraction defect

**Date:** 2026-09-28 · Closes the last open item in `docs/series_verification_ledger.md`
**Supersedes the "still wrong (measured, NOT fixed)" section of `docs/ism_series_fix_verdict.md`.**

## What the residual is

Re-measured on the current files (spread = |max-min| / |min| over the merge's own
`n_reports` / `min_value` / `max_value`):

| file | rows | multi-report rows | rows >10% spread |
|---|---|---|---|
| ism_coaster_freight_series.csv | 12,319 | 5,876 | 485 |
| ism_handy_freight_series.csv | 17,629 | 11,992 | 723 |
| **combined** | **29,948** | - | **1,208 (10.1% of multi-report, 4.0% of all rows)** |

The earlier fix took this from 2,269 to ~1,178; the small difference from 1,178 is my
denominator (`|min|`), stated here so the number is reproducible.

## The method (this cron session has NO image/vision tool)

"Render and look" was replaced by the strongest available equivalent: **re-derive every
series straight from the PDF's own vector drawings** and compare it to what the extractor
wrote. For each chart I take its recorded plot rectangle and its fitted axis
(`value = a*y + b`), pull the line segments inside that rectangle from
`page.get_drawings()` grouped by stroke colour, map their y through the axis, and compare
min/max to the stored series. That is an independent path into the same data - the JSON's
values are never used to produce the control values.

```
python3 scratch/ism_geom_audit_all.py     # all ism charts: 1,460 series across 110 documents
python3 scratch/ism_geom_audit.py         # the Damietta/Urea chart alone: 37 reports, 128 series
```

## Result

* **1,395 / 1,460 series (95.5%) re-derive exactly** (tolerance 0.35 units).
* The **65 exceptions are a known flaw in MY control, not extraction errors**: on
  `Average round voyage TCE ...` the series `Gulf of Finland (St-Pb) - ARA RV` is drawn in
  **black (0,0,0)**, the same colour as the chart frame, so the colour-keyed grouping merges
  the line with the frame (200 segments spanning the whole plot instead of 102). The stored
  values (7,517..11,951.7) are a correct subset of that merge. Verified by inspection.
* For the largest residual class (the `20XX year` comparative charts) I checked the
  representative chart `Urea, 5-6,000t, Damietta - Seville` across **all 37 reports that
  carry it: 128 / 128 series faithful.**

## Why the disagreement is the publisher's

The same nominal series disagrees between reports, and **both sides are geometrically
faithful**:

| | 2023 year, week 14 | its own axis | re-derived from the PDF drawings |
|---|---|---|---|
| ism_2023_W14 | 40.5 | 15..75, ticks `75,65,55,45,35,25,15` | **40.5** (exact) |
| ism_2023_W38 | 23.0 | 15..71, ticks `71,64,57,50,43,36,29,22,15` | **23.0** (exact) |

Both tick sets are read verbatim from the page's positioned text (`x~41.5`), and each fit
reproduces its own page to `maxres_pct` 0.003. The blue (2023) line genuinely sits at a
different height in each document. Across the 37 reports carrying this chart, **29 agree on
40.5** and the rest are scattered (31.5 x4, 24.0 x2, 18.0, 23.0) - the signature of a
publisher who redraws/revises a chart, not of a systematic parser bug.

## Verdict and what was done

**PUBLISHER_INCONSISTENT.** No value was dropped, repaired or re-keyed: the stored value is
what that report's page actually plots, and a wrong value is worse than a missing one. The
merge already exposes the disagreement through `n_reports` / `min_value` / `max_value` /
`value_sd`, so downstream can filter on spread without any change to the data.

**Recommendation (not actioned - needs the user):** if a single canonical series is wanted
for these keys, take the majority value across reports (e.g. median of the per-report
values) and record the dissenting report ids, rather than averaging. Do not do this silently
inside the extractor.

**Still worth a human eye:** this run's control is geometric, not visual. A rendered-page
check of `Urea, 5-6,000t, Damietta - Seville` in `ism_2023_W14` and `ism_2023_W38` would
close the last gap in confidence.

---

## UPDATE 2026-09-29 (later cron run): superseded on ACTION, confirmed on DIAGNOSIS

This run's PUBLISHER_INCONSISTENT conclusion stands and is now confirmed from the
publisher's own **page text** (not geometry alone): the publisher relabels its own
year-comparison lines between issues, and one TCT line changes level mid-2025 while its five
siblings stay identical to the digit. See
**`docs/ism_series_value_provenance_verdict.md`**.

Its RECOMMENDATION ("take the median across reports") was measured to be wrong and was NOT
followed: where restatements contradict each other a median is a value no page ever printed.
The merge now takes the value **verbatim from the best-carrying issue** (`value_report` names
it), with the restatement band kept in `min_value`/`max_value`/`value_sd`. That run also
found and fixed a separate real defect: `unit` was wrong on 16,985 rows.
