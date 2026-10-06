# Best Oasis (hellenic/demolition) coverage verdict - 2026-10-06

## What was found
A date-coverage sweep of the three hellenic demolition publishers (best_oasis,
athenian, gms) found **2 genuinely unextracted best_oasis weekly reports**:

| issue_date (mtime) | report week (from PDF cover) | PDF |
|---|---|---|
| 2026-05-05 | 25 April - 01 May 2026 | `pdfs/2026-05-05_best-oasis-...-1-may-2026_..._69af36cf75f1.pdf` |
| 2026-05-16 | 09 May - 15 May 2026 | `pdfs/2026-05-16_best-oasis-...-15-may-2026_..._09cbd4b6a3cd.pdf` |

## Root cause (measured)
`scripts/extract/publishers/run_best_oasis_demolition.py:37` sets
`SOURCE_DIR = corpus/02-hellenic/demolition/pdfs/best_oasis` and `get_unique_files`
globs it **flat** (`source_dir.glob("*.pdf")`). Both reports lived only in the
**parent** dir `corpus/02-hellenic/demolition/pdfs/` (where gms/athenian best-oasis
pairs also sit), so the runner never saw them. They are real `%PDF-` files, 4 pages,
cover line present - not HTML-as-PDF, not bot-wall.

## Fix + result
Copied the 2 PDFs into the runner's source dir and re-ran the canonical pipeline:

- **219/219 succeeded, 0 failed.**
- md tier: 269 -> **271** files. **Diff of the whole md dir = exactly the 2 new
  `.md` + 2 `.tables.json`; ZERO existing md changed** (regression check:
  `md5sum` before/after, 0 content changes).
- Series (rows): `best_oasis_demolition_series` 867 -> **875** (+8 = 2 weeks x 4
  locations); `best_oasis_deals_series` 892 -> **897** (+5); `best_oasis_exchange_rates_series`
  167 -> **169** (+2); commentary +21 rows. Mirrors `hellenic_best_oasis_*` updated.
- Register synced (`sync_extraction_register.py`): **630,357 -> 630,393** rows.
  `verify_registers.py` = **ALL VERIFICATION CHECKS PASSED PERFECTLY, 0 mismatches**.

## Faithfulness check (no vision tool in cron - same-document text reconcile, as documented)
Every extracted value was checked against its own PDF text layer (`pymupdf`):

- 2026-05-16: vessels NQ ZINNIA / DONG / SRAKANE / MSC BALTIC III / HANJIN 3007 all
  present verbatim; LDTs 3,736 / 2,334 / 1,694 / 10,809 / 3,665 present
  (page prints `3,736.00`); price 415 present. Indicative prices (India 420/405/390,
  BD 470/460/435, PK 465/460/445, TR 290/280/270) and FX present.
- 2026-05-05: prices India 430/415/400, BD 470/460/435, PK 465/460/445, TR 290/280/270
  present verbatim; FX (94.88 / 122.79 / 278.77 / 45.18 / 110.17 / 103.20) present.
  Page 3 prints `LIST OF VESSELS SOLD THIS WEEK: No vessel sale to report this week`
  and the deals series correctly gained 0 rows from this issue.

## Not gaps (checked, do not reopen)
- **athenian** 257 pdf dates vs 256 md: the 1 "missing" (2026-06-13) is the file
  `..._ship-recycling-market-insight-week-2_416dd50ae58c.pdf` whose content IS held
  as `best_oasis/2026/best_oasis_2026-06-13_..._416dd50ae58c.md` (naming cross).
- **gms** 2 "missing": `2026-06-16` is hash `03f79e746643`, already extracted
  (athenian + gms-named variants); `2026-10-03` is held as
  `gms_2026-10-02_2026-10-03_gms-week-40-scarcity-puts-chattogram-on-...md` (issue_date
  2026-10-02 differs from the download-date in the filename).
- **clarksons S&P bulletin #139** (2026-07-03) is NOT missing from the corpus: it is in
  the dedicated `md/clarksons/` tier (`..._bulletin-139_weekly-sales-3rd-july-2026_e756e5e24ae9.md`);
  only the older `md/hellenic/shipbuilding/clarksons` copy stops at #138.
- **shipbuilding** "missing dates" are the 374 breakwave PDFs under
  `02-hellenic/shipbuilding/breakwave_pdfs/`, already extracted in `corpus/03-breakwave`
  -> `md/breakwave/` (188 of 192 dates covered there; the other 3 are report-date-vs-
  download-date offsets). Not a gap.

## Carried decision for the user
`run_best_oasis_demolition.py` still globs only `pdfs/best_oasis/`. New best_oasis
arrivals that land in the parent `pdfs/` will be missed again. Two options:
1. acquisition places best_oasis PDFs in `pdfs/best_oasis/` (no code change), or
2. widen `SOURCE_DIR` to also scan the parent `pdfs/` filtered to best_oasis names
   (caveat: `get_unique_files` picks the SHORTEST stem, so widening the source set can
   rename existing md and churn the tier - do not do it blindly).
The 2 recovered PDFs were left copied into `pdfs/best_oasis/` so a future re-run is
idempotent.
