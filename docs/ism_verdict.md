# ISM (Metal Expert, ismreport.com) - extraction verdict

Source 8 of the source-by-source programme. Pipeline:
`scripts/extract/publishers/run_ism.py` (per-source, no shared runner).
Output: `data/extracted/md/ism/` - 112 `.md` + 112 `.charts.json`.
Extracted 2026-09-24, 112/112 documents, **0 failures**, whole corpus in ~35 s.

## What was delivered

ism holds **no tables**, so the deliverable is chart series:

| metric | measured |
|---|---|
| documents | **112 / 112** |
| charts | **444** |
| series | **1,678** |
| weekly data points | **84,035** |
| series labelled from a legend swatch | **1,624 (96.8%)** |
| series mislabelled | **0** |
| duplicate series | **0** |
| axis scales verified (residual < 0.5% of span) | **444 / 444** |
| x scales linear in week | **443 / 444** |
| week alignment (data grid vs whole weeks) | median **0.061**, max 0.349 weeks |
| failures / quarantined documents | **0** |

The 54 unlabelled series are all cases where the publisher drew a polyline with
**no legend swatch of that colour** (verified: 0 of them share a colour with a
labelled series). They are kept, with their values and stroke colour, and each
affected document carries a warning. Per the standing rule, a missing label is
preferred to a wrong one.

## How it was verified (no vision tool in this session)

This session had **no image/vision tool**, so the state file's substitute rule
was applied - real content checks instead of a look, and it is stated plainly
here rather than reported as a look.

1. **The % reconciliation is the strong check.** Every dual-axis chart carries
   `freight rate / price * 100` alongside a `% of freight costs` series, so the
   two independently-scaled axes must agree. Measured across **108 charts**:
   median error **0.11 pp**, max **0.44 pp**, **108/108 within 1 pp**.
   A wrong scale on either axis breaks this immediately.
2. **The week axis is anchored on the publisher's own printed labels** and the
   fit residual is reported per chart (0.013-0.037 weeks on the trial set).
3. **Prose cross-check.** Independent values read from the same documents:
   * 2025 W21 fertilisers chart last point `22.5 $/t` against prose
     "transportation of 3-5,000 t of bulk fertilizers from Klaipeda to ARAG
     already costs **low EUR 20s/t**";
   * 2023 W32 Izmail/Reni-Bari chart last point `59.0 $/t` against prose
     "rates ... from Reni or Izmail to EMed have inched up to **$56-58/t**".
4. **Chart titles and axis tick labels were read back** from the output and
   compared with the rendered page text (`page.get_text()`), which is the
   strongest available substitute for reading the image.

## Defects found and fixed during the trial (all measured, all in the runner)

Every one of these produced plausible-looking numbers while being wrong.

| # | defect | how it was caught | effect if shipped |
|---|---|---|---|
| 1 | right-hand axis labels matched to the LEFT labels | printing the resolved tick values | 2023 W32 read a **0-20%** axis as 0-1000 (**50x**); 2025 W21 read a **0-40%** axis as 0-400 (**10x**) |
| 2 | N line segments read as N points | comparing point x against tick x | every series **lost its last week** and shifted one week back |
| 3 | series rejected because the plot's TOP edge was used as its bottom | 0 series extracted | total failure, silent |
| 4 | week unwrap compared a raw week to an unwrapped one | fit residual 120 weeks | 7 spurious wraps; every week number wrong |
| 5 | wrap applied to the float before rounding | a week numbered **53** | a week that does not exist |
| 6 | legend label taken from the first text span only | reading the labels back | `'Gulf of Finland (St-Pb)'` for two different routes |
| 7 | legend entries that wrap onto 2 lines | 25 charts with duplicate names | labels truncated at the first line |
| 8 | horizontal (row) legends merged | reading the .md | 280 year-comparison charts labelled `'2023 year 2024 year 2025 year'` |
| 9 | bar groups drawn as fill + outline + shadow | duplicate series | the same series shipped 2-3x under one label |
| 10 | 2023 bars carry a FILL and no stroke colour | 2023 charts missing series | a third of the series silently absent |
| 11 | tick-chain cap of 90 items | 0 charts on a 6-page special | a 156-tick x axis dropped the whole page |
| 12 | legend band unbounded in x and y | a whole sentence used as a label | prose adopted as a route name; a stray `%` routed a $/day series onto the percent axis |

## Known gaps (measured, not estimated)

* **`ism_2026_W02_ISM_Handy_week2.pdf` produced 0 charts.** Its page 0 carries
  **0 vector drawings and one 461x308 JPEG** - the chart is a raster image in
  that one file, unlike the other 111. 1 of 112 documents.
* **1 chart of 444 has a non-linear x scale** (residual >= 0.5 weeks). It is
  flagged in its own `.charts.json` warning list and its week labels are the
  publisher's printed ones.
* **54 series (3.2%) are unlabelled** - no legend swatch of that colour exists
  on the page. Values and colours are kept; the document carries a warning.
* The footer field `Coaster Freight Index, April, 11, 2025` appears on a
  **week 21** file (mid-May). It is a stale template field; the report week is
  taken from the filename and the chart's own last x label agrees with it.
* `ISM_2023_holiday_special.pdf` is a genuine 6-page special (156-tick axes,
  155 bars per series), not junk. It yields 5 charts.

## Numbers convention

ISO throughout - no European separators seen in 112 documents. `%` axis labels
are stripped to their numeric value and the unit is carried in the axis record
(`is_percent: true`), never silently rescaled.
