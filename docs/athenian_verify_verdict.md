# Athenian demolition - verification + a cross-runner shared-output regression (2026-10-03 22:0x-22:5x IST)

Cron run, branch `auto/extract-fixes-2026-10-03-star-asia-snp`. No vision tool in this
session, so ground truth is the same-document PDF **text-layer** reconciliation (stated,
not assumed).

## 1. The carried-forward residual "Athenian demolition regeneration" is CLOSED

The state file listed it as still-open because the runner's last commit
(`be2f5818d`, 2026-09-30 16:34, "broker consolidation, routing fixes, hardcoded-year
elimination") postdates the delivered CSVs (2026-09-29 22:29). Measured this run:

- corpus `corpus/02-hellenic/demolition/pdfs/athenian`: **318 raw PDFs -> 257 unique**
  (sha256). Only **2** are raster (page-0 text < 50 chars) and both are already in
  `data/extracted/cache_athenian/` -> **no LlamaParse / no API spend**.
- `python3 scripts/extract/publishers/run_athenian_demolition.py` -> **257/257 succeeded,
  0 failed, 21.8 s**.
- **CONTROL, before vs after:** all four native CSVs are **byte-identical**
  (`athenian_indicative_demolition_series` 3,052 rows, `..._yearly_demolition_volume`
  4,026, `..._historical_demolition_prices` 240, `..._market_commentary` 6). The md tier
  (551 md / 551 sidecars) is **byte-identical** too (0 changed of 551).
  => The delivered data already equals what the current runner produces. **No regeneration
  was needed.** Residual closed.

## 2. REAL DEFECT (found + fixed): a shared output written by two runners

`data/extracted/series/hellenic_athenian_demolition_series.csv` had **two writers**:

- `run_hellenic_demolition.py` (canonical): dedups by filename AND
  `(sha256, issue_date, publisher_branch)`. Its own comment documents the fix:
  "the Athenian twins put 384 duplicate rows ... 3,300 -> 2,916 rows with the same 242
  issue dates".
- `run_athenian_demolition.py` (a "Synchronize legacy test mirror" block): writes the SAME
  file with **no dedup**.

Running the athenian runner therefore **regressed the canonical file**: it overwrote the
delivered **2,916-row** deduped series with its own **3,052-row** variant (**+136 duplicate
rows**), drifting it from the register. Measured: register row for that file = **2,916**;
after the athenian run the file held **3,052**.

**Restored** by replicating the canonical dedup (imported `extract_athenian` /
`publisher_branch` from `run_hellenic_demolition.py`, same sorted-HTML order, same
filename + content key). Result: **2,916 rows, 242 issue dates, 0 fully-duplicate rows,
243 source files** - matches the documented deduped state exactly (241 dates x 12 rows +
1 date x 24 rows).

**Fixed at source:** the mirror-write block was removed from
`run_athenian_demolition.py`; that file is owned by `run_hellenic_demolition.py`.
The only consumers are the two runners + `scripts/audit/generate_cadence_audit.py`
(reads it); no app/HTML consumer.

**CONTROL after the fix:** re-ran `run_athenian_demolition.py` -> exit 0, writes only its
four native CSVs, and **all five files byte-identical before/after** (the mirror stays at
2,916). Log no longer prints "Synchronized ... rows".

## 3. Content verification (text-layer, no vision)

Every price cell of the restored series reconciled against its own source PDF's page-0
text: **2,916 / 2,916 = 100.00 %** appear in the text layer; 0 mapped-source gaps.

## Residuals / notes
- The other four hellenic demolition CSVs were untouched (best_oasis 233/514,
  gms 448/2931) - this run modified only the athenian producer + the one shared file.
- The register already carried 2,916, so no `sync_extraction_register.py` change was due;
  the delivered register row was correct, the on-disk file had been wrong.
- Same hazard class worth checking elsewhere: any series file with two writers
  (last-writer-wins). This one is now single-writer.
