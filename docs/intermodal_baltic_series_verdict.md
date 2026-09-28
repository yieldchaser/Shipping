# intermodal - the Baltic chart series is superseded (measured 2026-09-28)

**Verdict: `data/extracted/series/intermodal_baltic_tc_series.csv` is NOT a deliverable.**
It is redundant (every series in it is held elsewhere), inaccurate (25-53% median error),
stale, and it fails the programme's own cross-report agreement gate. Do not re-run it.

Artefact: 20,348 rows, 9 series, dates 2020-05-18 -> 2026-08-30.
Producer: `scripts/extract/publishers/merge_intermodal_charts.py` (from the 252 `*.charts.json`).

## 1. Every series in it is held

| chart series | held file | points | range |
|---|---|---|---|
| BDI | `data/indices/bdiy_historical.csv` | 10,521 | 1985-01-04 .. 2026-09-21 |
| BCI | `data/indices/cape_historical.csv` | 4,341 | 2008-10-06 .. 2026-09-21 |
| BPI | `data/indices/panama_historical.csv` | 4,341 | 2008-10-06 .. 2026-09-21 |
| BSI | `data/indices/suprama_historical.csv` | 4,340 | 2008-10-06 .. 2026-09-21 |
| BHSI | `data/indices/handysize_historical.csv` | 4,319 | 2008-10-06 .. 2026-09-21 |

The remaining four (AVR 5TC BPI, AVR 7TC BHSI, AVR 10TC BSI, Average of the 5 T/C) are the
time-charter averages already declared held in `docs/MASTER_EXTRACTION_PLAN.md` section 0.
So the standing rule ("do not extract what we already hold") applies to all 9.

## 2. It is wrong against those feeds

Median absolute error vs the held feed, 1,887 points per series (2021-07 .. 2026-09):

| series | median err | points within 2% |
|---|---|---|
| BDI | 26.71% | 3.6% |
| BCI | 27.28% | 2.9% |
| BPI | 24.57% | 2.3% |
| BSI | 31.17% | 1.5% |
| BHSI | 53.49% | 0.2% |

## 3. It fails the programme's own agreement gate

Cross-report agreement on repeated (series, date) keys, computed from the file's own
`n_reports` / `min` / `max` columns:

- keys seen in more than one report: 20,186
- median relative spread **59.34%**, p90 141.3%, max 7,626%
- within 2%: 646 / 20,186 = **3.2%**

`docs/MASTER_HANDOFF.md` recorded 58.2% as the PRE-fix number and said the merge was never
re-run. The artefact on disk still carries that number.

## 4. It is stale, and the reason is visible in the artefacts

- Last dated point 2026-08-30; the intermodal corpus runs to the week-38 issue (2026-09-23).
- `date_labels` is **empty** on the newest report's charts, and the merger only dates points
  where labels were detected (597,663 of 600,123 points carry a date = 99.6%), so the most
  recent weeks are dropped rather than mis-dated.
- Code/artefact ordering: `*.charts.json` written Sep 24 20:49 - Sep 25 14:35; merger output
  Sep 25 22:37; `run_intermodal_charts.py` and `merge_intermodal_charts.py` last modified
  Sep 26 18:55. **The whole chart layer is PRE-FIX and was never re-run.**

## 5. Same-document control (no vision tool in this session)

This session has no image/vision tool, so the "render and look" step was substituted with the
real check the doctrine allows: reconcile every value the page prints against the extracted
rows. Source: the week-38 issue `intermodal_23_09_2026_...week_38_2026...md`, whose Baltic
table prints, for 18/09/2026: BDI 3,370 / BCI 5,768 / BPI 2,251 / BSI 1,767 / BHSI 988, with
TCEs 48,812 / 20,262 / 20,298 / 17,776, and Capesize 180K 1yr TC 44,750.

| path | BDI at that issue | verdict |
|---|---|---|
| held feed `bdiy_historical.csv` @ 2026-09-18 | 3,370.0 | EXACT |
| table-derived `intermodal_baltic_indices_series.csv` @ 2026-09-23 | 3,370.0 (all 5 indices + TCEs exact) | EXACT |
| chart-derived `intermodal_baltic_tc_series.csv` | **no row at all in 2026-09-10..2026-09-21** | absent |

The table path is independently confirmed by two sources agreeing exactly (the broker's own
printed page and the held feed). The chart path agrees with neither.

## 6. What this means for the "CLOSED" claim

`docs/EXTRACTION_REGISTER.md` marks Intermodal `CLOSED` on "61,181 rows across 16 series"
and lists `intermodal_baltic_tc_series.csv` (20,348 rows) first among its deliverables. The
table layer is sound - but the **20,348 chart rows are not a deliverable**: they are held
data, wrong, and stale. Intermodal's real output is its table layer, 40,833 rows across the
15 table-derived series (verified exact above).

`docs/MASTER_EXTRACTION_PLAN.md` section 0 cites this same file as *"the held set"* for
BDI/BCI/BPI/BSI/BHSI. That citation is wrong and is corrected in that file: the held set is
`data/indices/*.csv`, which carries 40 years of it, not a broker's chart re-read.

**Recommended action, deliberately NOT taken unilaterally:** the file has no consumer (only
`merge_intermodal_charts.py` / `run_intermodal_tables.py` write it; `index.html` does not
fetch it), so retiring it is safe - but it belongs to another workstream's tree, so this run
records the verdict and leaves the file in place. Whoever owns the register should either
delete it or mark it superseded, and drop it from the row count.

## 7. Separate defect found while checking: exact duplicate rows

Swept all 99 series CSVs for rows identical in every column:

| file | rows | exact dupes | % |
|---|---|---|---|
| bancosta_commodities_series.csv | 2,319 | 106 | 4.6% |
| intermodal_indicative_values_series.csv | 2,409 | 75 | 3.1% |
| intermodal_tc_rates_series.csv | 5,068 | 48 | 0.9% |
| bancosta_vhss_series.csv | 3,413 | 15 | 0.4% |
| bancosta_freight_rates_series.csv | 25,715 | 14 | 0.1% |
| xclusiv_sales_series.csv | 5,713 | 5 | 0.1% |
| poten_top_charterers_series.csv | 755 | 2 | 0.3% |
| star_asia_deals_series.csv | 3,327 | 2 | 0.1% |
| star_asia_ferrous_scrap_series.csv | 771 | 1 | 0.1% |
| carriers_sales_series.csv | 3,004 | 1 | 0.0% |

10 of 99 files; not systemic, but each is a double-count in any downstream series. In
`intermodal_tc_rates_series.csv` the duplicates are whole blocks of Tanker rows repeated
verbatim on the same issue.

## 8. How to reproduce

```
python3 scratch/measure_agreement.py     # agreement gate on the merged series that carry min/max
python3 scratch/score_all_indices.py     # 5 chart series vs the held feeds
python3 scratch/dup_sweep.py             # exact-duplicate sweep over all 99 series
```
`scratch/` is gitignored; the three scripts are the measurement, not the pipeline.
