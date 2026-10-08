# xclusiv sales DWT regeneration verdict (2026-10-08)

**Action: the delivered xclusiv sales data was REGENERATED to apply the code fix
`5c0a1e933` (period-thousands dwt). Not a new human decision: the code was already
fixed at HEAD and verified on one document; this run applied it to the delivered flies.**

## The defect (re-measured, not taken on trust)
`data/extracted/series/xclusiv_sales_series.csv` `DWT` held **126** raw
period-thousands values (`209.325`, `82.245`, ...) among 5,274 comma rows, and the
vessel TYPE had collapsed to the `Handysize` fallback for every one of them.

Ground truth: `corpus/01-brokers/xclusiv/2021/xclusiv_2021_xclusiv_weekly_2021_08_02.pdf`
page index 3 (`get_text()`) literally prints `HARK OLDENDORFF` / `209.325` — a
period as the thousands separator. A 209,325 dwt ship is a **Capesize**, not a
Handysize, which is the independent confirmation that the period is a separator.

## What was regenerated
Ran `run_xclusiv_tables.py` (single-process, OUT paths redirected to `scratch/`)
over all 264 corpus PDFs: **264 ok, 0 failed, 660 s**. Row counts identical
(sales 5542, demolition 2082, secondhand 8529, demo_sales 603, baltic 1015,
newbuilding 1379).

Copied back only what changed in content:
- `data/extracted/series/xclusiv_sales_series.csv`
- **8** `md/xclusiv/**/*.md` + their `.tables.json` sidecars (2021-08-02, 08-09,
  08-23, 08-30, 09-06, 09-13, 09-27; 2022-01-24). The overnight log named 5 issues;
  the measured set is 8.
- Every other xclusiv CSV and all 256 other md files are **byte-identical** to HEAD
  (no EOL churn — verified).

## Verification (measured)
- `git diff --stat`: exactly 17 files (8 md + 8 tables.json + 1 csv). No other tree change.
- Sales CSV: 5542 -> **5542** rows; **126** rows changed; **126/126** DWT changes are
  exactly `period -> comma` of the old value; **0** changes in any other column.
- `DWT` period-values remaining: **0** (was 126).
- Control unchanged: the comma-era 2026-09-28 `GCL HAZIRA` row still reads `81,986 / Kamsarmax`.
- TYPE now consistent with the dwt band (150k-260k -> Capesize/Gas/Suezmax; 75k-150k -> Panamax/Kamsarmax).

## Out of scope
- clarksons_sales_series.csv (6 rows, same class) - regenerated separately.
- The 7 `.md` files in `md/xclusiv/2026/` with no scratch match are pre-existing
  duplicate-stem leftovers (unaffected 2026 docs); left untouched.
- Pre-existing non-defects seen in the column and NOT introduced here: a handful of
  ordinal tokens (`2nd`,`9th`) with blank dwt, and 2 rows with a fused `"93,237 82,269"`.
