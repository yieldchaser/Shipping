# carriers DWT/LDT: the period-thousands 1000x defect (FIXED 2026-10-09 cron)

Run: scheduled source-by-source job. Rule obeyed: ONE SOURCE at a time, no generic
runner. Nothing was left to EXTRACT (re-verified: every broker source CLOSED, register
gate green, no W41 arrival); this run spent its time on a MEASURED numeric defect in
the carriers series.

## The defect (page-verified)

DWT and LDT are INTEGER counts, but the publisher is not consistent about the thousands
separator. Most rows print the ISO form (`206,204`) which the extractor's
`parse_numeric()` handles by stripping the comma; SOME rows -- and, for the 2023 W51 and
2024 W01 files, an ENTIRE DWT column -- print the European PERIOD form (`206.204`).
`parse_numeric()` keeps the period as a decimal point, so `206.204` became **206.204
DWT**: a silent 1000x error in the plausible direction (both are well-formed floats).

Ground truth (rendered text of the SAME document that was flagged):
* `corpus/01-brokers/carriers/2023/carriers_2023_W51_WK-51-23-CARRIERS_SP-MARKET-REPORT.pdf`
  page 1 prints `BEKS BROWN / BC / 206.204 / 2005 / ...` -- BEKS BROWN is a real ~206,000
  DWT Newcastlemax, so `206.204` == 206,204 DWT.
* The same page's demolition table prints `SSL DELHI / CV / 33.912 / 10.669` (DWT / LDT).

## Blast radius (measured)

Every non-integer `dwt`/`ldt` cell in the carriers series is a period-thousands misread
(a correct DWT/LDT is always an integer). Across all 9 carriers series:
* `carriers_sales_series.csv` :: `dwt` -- **22** non-integer rows.
* `carriers_demolition_series.csv` :: `dwt` **5** (incl. one legit `972.0`, see below)
  + `ldt` **4**.
* No other carriers series carries a non-integer dwt/ldt.

## The fix (per-source, in the runner)

Added `parse_count()` to `scripts/extract/publishers/run_carriers_complete.py` and used
it for the DWT (sales line 355, demolition line 469) and LDT (demolition line 470) fields
only. It derives the convention from the token SHAPE:
```
\d{1,3}(?:\.\d{3})+   -> EU period-thousands -> strip periods
\d{1,3}(?:,\d{3})+    -> ISO comma-thousands  -> strip commas
otherwise             -> parse_numeric()      (unchanged fallback)
```
Regenerated the whole tier into `scratch/` (136 PDFs, 2m27s, same byte-duplicate skips)
and diffed BEFORE touching the tree.

## Verification (control on the same documents)

* Row counts IDENTICAL to the delivered series (sales 3061, demo 174, newbuilding 299,
  bspa 731, bda 366, indices 1834, weighted 655, tc_period 3144, tanker_tce 786).
* **7 of 9 series byte-identical**; only `carriers_sales_series.csv` (**21** rows) and
  `carriers_demolition_series.csv` (**9** rows) changed -- and ONLY in `dwt`/`ldt`.
  `git diff --numstat` = `21/21` + `5/5` (the demolition rows pair dwt+ldt on 3 lines).
* **Same-document control 30/30:** every corrected cell's raw period-thousands token is
  present verbatim in its OWN source PDF's text layer.
* Register gate `scripts/extract/verify_registers.py`: **ALL PASSED**, 180 CSVs /
  **639,749** logical rows == JSON == MD (row counts unmoved; values only).
* Blast radius: `index.html` fetches no carriers series -> not app-displayed.

## NAMED, NOT auto-fixed (a wrong value beats a guess)

* `NAVIOS HELIOS` (2025 W41) is stored as `77.75` and stays so. The page prints exactly
  `77.75` -- only TWO fraction digits, so the shape rule (which requires a 3-digit group)
  correctly declines it. `77.75` is still an impossible DWT (NAVIOS HELIOS is a 2005
  Panamax, true ~77,750), but the publisher's PRESSED token is truncated, and 77,750
  cannot be derived from `77.75` (x100 gives 7,775, x1000 gives 77,750 but the token lost
  the digit). Left page-faithful.
* `carriers_demolition` 2025 W06 `972.0` -- an integer, a legitimately small demolition
  unit; not a period-thousands token; untouched.

## Same defect class in ANOTHER source (NAMED, separate per-source pass)

`star_asia_deals_series.csv` :: `ldt` carries the same signature: 12 rows whose token is
period-thousands, e.g. page 14 of `star_asia_2024_W42_Market-report-Week-42.pdf` prints
`HAI BO / BARGE / 8.678 / 13.10.2024 / AWAITING` (adjacent rows print commas: `7,263`,
`1,721`, `6,064`). Per the ONE-SOURCE rule this is left to its own carriers-independent
pass (`run_star_asia_*`), not bundled here.
