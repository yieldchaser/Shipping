# carriers - delivered series regenerated from HEAD (2026-10-07)

## Why

A prior (18:03 IST) review measured that the **delivered** carriers series were
STALE relative to the code at HEAD. The 2026-10-05 price fix (`a33b4e44f`,
cherry of `f81eb2e7b`) and the two-rule duplicate guard (`57d06409`) had been
committed to `run_carriers_complete.py`, but the delivered CSVs were regenerated
in the SAME session from the PRE-fix script revision `57d06409^`, re-introducing
exactly the values the fixes had corrected. Row count matched the recorded total,
so the restore looked clean and was committed 2026-10-06 (`017ae47e7`).

The prior review left it as "needs human regeneration" (rule 3f). It is NOT a new
convention decision: the convention and its page verification already exist in
`a33b4e44f` ("verified on the rendered W39-2026 page ... xclusiv prints as
'USD 38 mills'"; "verified on the rendered W46-2023 page: MAGIC MOON"). Regenerating
executes an already-made decision. Done here.

## Method

Ran `scripts/extract/publishers/run_carriers_complete.py` at HEAD into a **scratch**
output dir (module OUT_MD/OUT_SERIES redirected), then diffed against the delivered
files before touching the tree. 136 PDFs discovered, 3 byte-identical duplicates
skipped, 133 md + 9 series produced, 109.0 s.

## Measured result

| series | delivered | regenerated | dup rows removed |
|---|---|---|---|
| carriers_sales | 3,130 | **3,061** | 69 |
| carriers_demolition | 178 | **174** | 4 |
| carriers_newbuilding | 312 | **306** | 6 |
| carriers_bspa | 749 | **731** | 18 |
| carriers_bda | 375 | **366** | 9 |
| carriers_indices | 1,876 | **1,834** | 42 |
| carriers_dry_weighted_routes | 670 | **655** | 15 |
| carriers_dry_tc_period | 3,216 | **3,144** | 72 |
| carriers_tanker_tce | 804 | **786** | 18 |
| **total** | | | **253** |

The 253 removed rows are exactly the duplicate-guard's target: 3 pairs of
**byte-identical** PDFs (same md5) resolving to the SAME (issue_date, report_week) -
`carriers_2026_W35` == `15_09_2026_...week_37 (2)`, `carriers_2026_W38` == `....pdf.pdf`,
`carriers_2026_W39` == `general_broker_28_09_2026_...week_39`. Verified md5:
`c0ca7320cdb269874e30c7b8869a65bf` on both W35 files, both dated 2026-09-01/wk35.
The remaining rows of each duplicate pair are retained under the canonical filename.
This matches commit `57d06409`'s own message ("253 duplicate-key rows removed across
the nine carriers series") exactly.

### Value corrections (carriers_sales only)

214 rows changed, and **only** the `price_usd_mill` column differed (0 changes to any
other column). Direction: full-dollar / 1000x values -> millions.

* `GCL HAZIRA` 38,000,000.0 -> 38.0 ; `SEA RUNNER` 20,500,000.0 -> 20.5
* `MAGIC MOON` (2023-11-13) 1180.0 -> 11.8 ; `NAVIOS HELIOS` 825.0 -> 8.25
* `OSAKA STAR` 34,000,000.0 -> 34.0 ; `BW JAPAN` 38,250,000.0 -> 38.25
* `DAEBO GLADSTONE` 21,000,000.0 -> 21.0

`price_usd_mill >= 1000`: **282 -> 0**. New max price_usd_mill = **585.0**
(plausible per-vessel ceiling; the old max was a group total in raw dollars).

## Verification (three independent checks)

1. **Shape rule, whole file.** Re-derived the expected value from each row's own
   `price_raw` with the HEAD `parse_price_mill`: **2,842 priced rows checked, 0
   mismatches** against the delivered values.
2. **Source text layer (control = the SAME documents the changed rows came from).**
   `pymupdf` page text of `carriers_2026_W39_...pdf` contains `GCL HAZIRA`,
   `38,000,000`, `SEA RUNNER`, `20,500,000`; of `...week_37 (1).pdf` contains
   `OSAKA STAR`, `34,000,000`, `BW JAPAN`, `38,250,000`.
3. **Register gate.** `scripts/extract/verify_registers.py` = ALL PASSED,
   180 CSVs / **640,877** logical rows == JSON == MD, 0 mismatches (was 641,130;
   delta 253 = the duplicate removals).

Byte-level scoping: the 8 non-sales series differ from the delivered files by
**row removal only** (0 value changes, confirmed by full-tuple diff).

## Blast radius

Not app-displayed: `index.html` fetches no carriers series and no `data/views/**` or
`data/derived/*` artefact embeds `price_usd_mill`. `md/carriers/*.md` needs no
change - it renders the RAW token (`38,000,000`), which was always correct.

## Register tooling

`scripts/sync_extraction_register.py` updated only `carriers_sales_series.csv` in
Section 1 but left the hardcoded "(10,818 total rows across 9 series)" phrase stale
(it was already wrong - the true pre-fix sum was 10,944). Extended it with the same
pattern it already uses for star_asia, so the phrase is now computed from disk
(correct value 11,057). Verified idempotent (md5 stable across a second run).

## Not actioned, disclosed

* `carriers_newbuilding_series.csv` `price_usd_mill` - 4 rows still wrong in BOTH old
  and new output: `'117,5 EACH' -> 1175.0` (should be 117.5m, 2025 W38) and
  `15000/6000/7000 -> 15000.0` (2024 W07, looks like column bleed). That code path
  (line ~574) still calls `parse_numeric`. Unchanged by this regeneration; left for a
  follow-up because it is a new parsing decision, not a stale-deliverable one.
* `xclusiv_sales_series.csv` `PRICE_USD_MILL` - 5 rows, same class; different runner.
* `data/extracted/carriers/carriers_sales_series.csv` (legacy mirror written by
  `run_singletons.py`, outside the register) not touched; not read by the app.
