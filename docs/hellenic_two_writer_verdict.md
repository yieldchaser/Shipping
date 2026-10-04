# Hellenic demolition family - multi-writer / multi-schema hazard + a RED guard test (2026-10-04 cron)

No extraction job was running (the four `python.exe` are the Hermes gateway). No vision
tool in this session; ground truth is measured file/row counts, the repo's own guard test,
and git history - all stated.

This continues the previous run's explicit "Hazard to sweep: any series file with two
writers (last-writer-wins)" (the Athenian mirror fix, `docs/athenian_verify_verdict.md`).

## 1. Sweep result: 4 series files in the hellenic demolition family have >=2 writers

Method: for all 170 `data/extracted/series/*.csv`, find every script with a write statement
naming the file (and, because the Athenian defect hid behind a path VARIABLE, every script
that builds a `... / "<name>"` path and then writes it).

| file | writers | schemas seen | current rows |
|---|---|---|---|
| `hellenic_gms_demolition_series.csv` | 3 | **3 different** | 448 |
| `hellenic_gms_port_positions_series.csv` | 2 | 2 | 2931 |
| `hellenic_best_oasis_demolition_series.csv` | 2 | 2 | 233 |
| `hellenic_best_oasis_deals_series.csv` | 2 | 2 | 514 |

Writers:
- `run_hellenic_demolition.py` (HTML-only dedup pass; canonical per the Athenian fix) - 9-col GMS.
- `run_gms_demolition.py` (native PDF+HTML pass) - **11-col** GMS (`+volume,issue`); mirror-writes the same file.
- `run_hellenic_gms_demolition.py` (separate HTML runner) - **8-col** GMS (no `report_week`).
- `run_best_oasis_demolition.py` - mirror-writes the two `hellenic_best_oasis_*` files with a DIFFERENT schema than the canonical (canonical carries `report_week,wow_change_pct`; mirror carries `hms_80_20,shredded`).

`gms_port_positions`, `best_oasis_*`, `athenian` are the same class the previous run fixed on
the Athenian file - the fix removed ONE instance; four remain.

## 2. The GMS file is measurably divergent (last-writer-wins is live)

`hellenic_gms_demolition_series.csv` (448) vs the native `gms_demolition_rankings_series.csv` (1092):

| measure | hellenic_gms (448) | gms_demolition_rankings (1092) |
|---|---|---|
| rows | 448 | 1092 |
| distinct issue dates | 112 | **272** |
| date span | 2022-04-04 .. 2026-09-26 | 2021-07-05 .. 2026-09-25 |
| schema cols | 9 | 11 |
| locations | incl. `Turkey*`,`Pakistan*` | clean `Turkey,Pakistan,...` |

The two are largely **date-disjoint** (268 native dates absent from hellenic; 108 hellenic
dates absent from native; only 4 shared). They are not the same publication slice.

## 3. The guard test `tests/test_hellenic_extraction.py` is RED (4 failures)

Run with the Python312 interpreter (`python -m pytest tests/test_hellenic_extraction.py`):
`4 failed, 8 passed`.

1. `test_hellenic_demolition_series_integrity` - asserts `hellenic_gms_demolition_series.csv >= 1088`; found 448.
2. `test_gms_demolition_rankings_series_integrity` - asserts `>= 900`; found 448.
3. `test_athenian_demolition_world_class_integrity` - asserts **exactly 257** athenian md files; found **551**. Measured: all 551 are **distinct content** (0 duplicate md5) - not a flat/year duplication. The `==257` exact-count assert is stale.
4. `test_markdown_and_sidecars_existence` - asserts `data/extracted/md/clarksons/*.md >= 170` (flat glob); found 0 flat, but **180 exist in year subdirs** (`clarksons/2021..2026`). Stale flat-glob assumption.

3 of 4 are stale test assumptions (layout / exact-count drift). #1/#2 are the real signal.

## 4. Root cause of the GMS regression (git history)

- The test thresholds were authored 2026-09-29 23:36 (`19d434b50`), asserting the **272-report**
  population the test comment names: "246 native PDFs + 26 2021 HTML articles" = 272 dates.
  The native file reproduces it exactly (272 dates / 1088 distinct `(date,location,rank)`).
- `run_hellenic_demolition.py` was created **after** that (`be2f5818d` 2026-09-30, then the
  dedup commits `0f71c1366` / `3db3e145f` 2026-10-01). It derives GMS from
  `DEMO_DIR.glob("**/*.html")` **only** (HTML articles), so it emits a sparse, asterisked set
  (448 rows / 112 dates).
- Therefore: the file held the full ~1092-row weekly series when the test was written; the
  later HTML-only writer last-clobbered it down to 448. The register row (`448`, "Verified")
  is auto-synced from disk (`sync_extraction_register.py`), so it simply echoes the regression
  rather than being an independent check.

**No single current producer yields the test's expected contract**: the canonical
`run_hellenic_demolition.py` emits 9-col/448 (HTML only), while `run_gms_demolition.py`
emits 11-col/1092 (PDF+HTML). The 9-col schema the test reads (`location,sentiment,...`)
cannot come from the 11-col producer unmodified.

## 5. Decision item (NOT fixed - deliberately)

Two producers with contradictory contracts, a red guard test, and a register that mirrors
disk make this a judgement call, not a mechanical fix. Options:
- **(A)** Make `run_hellenic_demolition.py` the sole owner and let it parse PDFs too (union ->
  restore ~1088) - keeps one producer, matches the test population.
- **(B)** Remove the GMS write from `run_hellenic_demolition.py`; keep `run_gms_demolition.py`
  as owner; then update the test to the 11-col schema.
- **(C)** Update the test only (treat 448 HTML-set as canonical) - contradicts the 272-report
  comment, so not recommended.

Data left untouched on purpose: a wrong value is worse than a missing one, and the correct
owner is a human call. Same for the two stale md asserts (#3/#4) - fix the glob/count once
the owner is decided.

## 6. Evidence / reproduction
- sweep: `scratch/twowriter_sweep/sweep2.py` -> `scratch/twowriter_sweep/results2.json`
- tests: `python312 -m pytest tests/test_hellenic_extraction.py -q` -> 4 failed, 8 passed
- divergence: row/date/schema counts above, measured with csv.DictReader

## 7. Other sweep hits - judged benign (measured)

- `orchestrate_incremental_ingest.py` writes `affinity_bda/tce_series.csv`, `carriers_sales_series.csv`,
  `advanced_shipping_{demo_sales,newbuilding,secondhand_matrix}_series.csv` via a
  **`upsert_rows_to_csv(...)`** helper (plus-dedup, non-destructive). It IS live
  (`run_master_pipeline.py` + `.github/workflows/broker_reports_weekly.yml`). Upsert by
  `(issue_date, ...)` key is the intended incremental path, not a clobber. Last run already
  proved the affinity CSVs byte-reproducible. No action.
- `extract_week39_supplements.py` (bancosta/clarksons) is referenced only by
  `audit_hardcoded_years.py` - not in CI or `run_master_pipeline.py`. A one-off; low risk.
- `strict_broker_audit.py` hits on `lion_*_series.csv` are audit-REPORT text prose, not writes.
  False positive.
- `run_carriers.py:545` hit on `carriers_sales_series.csv` is a `print()`. False positive.

Net: the unmitigated hazard is the **hellenic demolition family** (section 1-4) - 4 files,
3 writers on the GMS one, no dedup in the mirror writers, and the guard test red.
