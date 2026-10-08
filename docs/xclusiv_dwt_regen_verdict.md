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

---

# clarksons regeneration (same defect, same evening)

Ran `run_clarksons.py` with OUT paths redirected to `scratch/` (180 unique reports
from 1,011 hellenic-shipbuilding + 11 broker PDFs, deduped by md5; **61 s**).

- `clarksons_sales_series.csv`: **6** rows changed (`175.085`, `65.125`, `48.012`,
  `53.840`, `49.600`, `63.800`); `clarksons_demolition_series.csv`: **1** row
  (`45.654`, ETERNAL LUCK 2023-06-02). Row counts unmoved (sales 1343, demo 120);
  **7/7** DWT transforms are exactly `period -> comma`; **0** other-column changes.
- Applied only the dwt/type changes to **6** md + `.tables.json` docs and the 2 CSVs,
  preserving the delivered **LF** EOL (no EOL churn).
- Ground truth: `2026-03-28_...bulletin-127....pdf` p1 narrative reads
  `JIN RUI (ABT, 63K DWT, 2014, JIANGSU HANTONG)` beside the table cell `63.800`.
- **Disclosed, NOT applied:** the regeneration also flipped `source_file` from
  `corpus/01-brokers/clarksons/2026/...` to `corpus/02-hellenic/shipbuilding/pdfs/...`
  on **9 other 2026 docs** (the runner's md5 dedup picked the hellenic duplicate
  copy this time). That is a path-reference change unrelated to the dwt fix and was
  deliberately left out of the commit.
