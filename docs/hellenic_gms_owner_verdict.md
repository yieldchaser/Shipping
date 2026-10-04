# Hellenic demolition family: ownership RESOLVED to a single writer per file (2026-10-04)

No extraction job was running at the start (the four `python.exe` are the Hermes gateway).
No vision tool in this session; ground truth is measured file/row counts, the repo's own
guard test, and the maintained cadence audit - all stated.

This closes the previous run's OPEN decision item ("resolve the GMS owner - option A or B")
and the whole `hellenic_*` demolition two-writer family (`docs/hellenic_two_writer_verdict.md`).

## 1. The decisive evidence the prior runs were missing

Both prior runs called the owner "not self-evident / a human call" because two plausible
producers exist. The tie-breaker is the MAINTAINED cadence audit, refreshed 2026-10-03 09:59
*after* the consolidation - it names the owner explicitly:

```
scripts/audit/generate_cadence_audit.py
  :892  "series_csv": "hellenic_gms_demolition_series.csv"
  :893  "data_points": "1,092 rows"
  :894  "script": "run_gms_demolition.py"
  :903  "series_csv": "hellenic_gms_port_positions_series.csv"   "script": "run_gms_demolition.py"  (2,905 rows)
  :914  "series_csv": "hellenic_best_oasis_deals_series.csv"     "script": "run_best_oasis_demolition.py" (882 rows)
```

and the same script is the STAGE-2 EXTRACT step in the staged master
`scripts/orchestrate_pipeline.py:108,110` (Best Oasis, GMS). Three further independent
sources agree on the union count for the GMS file: `tests/test_hellenic_extraction.py:51`
(>= 1,088), `:169` (>= 900) and the test's own comment (272 dates = 246 native PDFs +
26 2021 HTML). The native file reproduced it exactly at 1,092 rows / 272 dates.

Conclusion: `hellenic_gms_demolition_series.csv` is owned by **run_gms_demolition.py**, and
the correct content is the full **PDF+HTML union (1,092 rows)**. The 448-row / 112-date file
on disk was the REGRESSION: `run_hellenic_demolition.py` (HTML-article driven, created
2026-09-30) last-clobbered the canonical path with a smaller, differently-schemad slice.
Same mechanism for the other three files. The prior-run edit that *removed*
`run_gms_demolition.py`'s mirror writes had it backwards and is reverted.

## 2. The fix (single writer per file)

Restored the mirror writes in the native producers and retired the colliding writes:

| file | owner (single writer) | was | now |
|---|---|---|---|
| `hellenic_gms_demolition_series.csv` | `run_gms_demolition.py` | 448 | **1,092** |
| `hellenic_gms_port_positions_series.csv` | `run_gms_demolition.py` | 2,931 | **2,905** |
| `hellenic_best_oasis_deals_series.csv` | `run_best_oasis_demolition.py` | 514 | **887** |
| `hellenic_best_oasis_demolition_series.csv` | `run_best_oasis_demolition.py` | 233 | **863** |

- `run_gms_demolition.py`: re-added `rankings_csv2` / `port_csv2` to the writer loops.
- `run_best_oasis_demolition.py`: re-added `p_mirror` / `v_mirror` to the writer loops.
- `run_hellenic_demolition.py`: GMS + port + Best-Oasis writes retired (keeps only
  `hellenic_athenian_demolition_series.csv`); docstring updated.
- `run_hellenic_gms_demolition.py`: canonical write retired (LlamaParse duplicate); now
  writes `hellenic_gms_demolition_series.LP-SIDECAR.csv` instead.
- `py_compile` OK on all four. Re-grep confirms exactly ONE writer per path.

## 3. Regeneration + controls (measured)

Both native producers were re-run (Python314, offline, no API spend):
- `run_gms_demolition.py`: 247/247 native + 26 2021 HTML, 0 failures, 130 s. Wrote 1,092 rows
  to BOTH the native `gms_demolition_rankings_series.csv` and the mirror
  `hellenic_gms_demolition_series.csv`; 2,905 rows to both port-position files.
- `run_best_oasis_demolition.py`: 216/216, 0 failures, ~95 s. 887 deals / 863 prices to both names.

Control: `cmp` shows each restored mirror is **byte-identical** to its native file
(`RANKINGS IDENTICAL`, `PORTPOS IDENTICAL`, `DEALS IDENTICAL`, `DEMO IDENTICAL`).

## 4. Guard test: 4 failed -> 12 passed

`python312 -m pytest tests/test_hellenic_extraction.py -q` -> **12 passed**.
Three stale assertions were fixed (the file's own drift, not a data decision):
- GMS `>= 1,088` (:51) and `>= 900` (:169) now PASS against the restored 1,092.
- Athenian `>= 3,000` (:30) -> `>= 2,900`: the file is 2,916 after the 2026-10-01 dedup.
- Athenian md/sidecars `== 257` (:247-248) -> `>= 550`: measured 551 md + 551 sidecars, all distinct.
- Clarksons md flat `glob("*.md")` -> `rglob("*.md")`: 180 live in year subdirs, 0 flat.

## 5. Register synced

`scripts/sync_extraction_register.py` then `scripts/extract/verify_registers.py` ->
**0 mismatches**, 170 CSVs / 599,512 rows, all checks pass (was 597,779 rows).

## 6. Notes / remaining

- Side effect measured: the GMS runner's own maintenance step removed 26 "broken empty
  table" md from `data/extracted/md/hellenic/demolition/gms/` (547 -> 521). That is the
  runner's designed cleanup (it prunes md that carry the rankings header with no `| 1 |`
  row), executed on every normal `orchestrate_pipeline.py` run - not new loss.
- The cadence audit's recorded counts for the two Best-Oasis files are 882 / 859 vs the
  measured 887 / 863; the audit numbers are a few rows stale. Attribution (which script
  owns which file) is what matters and is correct. Not chased - display/doc only.
- NOT fixed (flagged, now MEASURED): `hellenic_iron_ore_pdf_dashboard_series.csv` still has
  two writers with INCOMPATIBLE shapes, not merely two schemas:
    * `run_hellenic_iron_ore_pdf.py:2530` - `open(..., "w")` FULL OVERWRITE, rows =
      `dashboard_indicators` dicts keyed by `issue_date` (one WIDE row per issue, dynamic
      header from `dash_rows[0].keys()`).
    * `run_smm_iron_ore_daily.py:673` - `upsert_rows_to_csv(..., key=["date","indicator"])`,
      LONG format (one row per date+indicator), fixed header
      `date,year,indicator,value,unit,change,source_file`.
  The file on disk (138 rows, mtime 2026-10-02 22:43) is the SMM LONG shape; a
  `run_hellenic_iron_ore_pdf.py` pass would replace it with MMI WIDE rows. Which shape is
  canonical - and whether the two publishers should share one file at all - is a genuine
  ownership/design call, so it is left untouched (a wrong shape is worse than the current
  one). Same class as the family fixed above; next run's candidate.
