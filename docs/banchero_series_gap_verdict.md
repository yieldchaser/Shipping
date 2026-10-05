# Banchero Costa series tier - stale gap + a zeroing landmine (measured 2026-10-05)

## What was checked
The 30m prompt asked to verify xclusiv then start fearnleys/intermodal/etc. The state
file (`docs/OVERNIGHT_STATE.md`) is the truth: xclusiv is 266/266 DONE and **every
broker source is CLOSED**. So this run verified a claim instead: is banchero Costa
complete? Its state-file "ACTIVE JOB" entry still says *"243/244, BLOCKED on credits"*
(Sep-28) - that is STALE.

## Measured state of banchero Costa
| item | measured |
|---|---|
| PDFs | **248** (`corpus/01-brokers/banchero_costa`) |
| LlamaParse md | **248** (`data/extracted/llamaparse_banchero/*.md`), newest mtime Oct-3 11:06 |
| run.log | last line = the W38+W39 docs parsed (`done=168 failed=31`, credits~2832) - the credit wall was cleared; the mojibake prose tier IS complete |
| series CSVs | 10 files, 45,838 rows; newest build mtime **Sep-29 11:53** |

So: **md is 248/248 DONE**, but the state file's ACTIVE-JOB block points at a job that
finished on Oct-3. Corrected in the state file this run.

## The stale gap (real)
The series were last stacked **Sep-29**; W36/W37/W39 md were created **Oct-3**. The
freight series ends `2026-08-31 (W35)` then jumps to `2026-09-21 (W38)` - **W36, W37
and W39 have NO freight rows**, although their md carries the tables (W36: 56 HTML
tables incl TD3C/C10 Pacific/BCI; W37: 58; W39: 19). Measured per-DOC: 244 distinct
docs in `bancosta_freight_rates_series.csv` vs 248 PDFs; the 4 missing are exactly
W36, W37, W39 and the week-39 duplicate.

## The landmine (root-caused; a guard was added)
`scripts/extract/publishers/stack_banchero_series.py` (added whole in commit
`be2f5818d`, 2026-09-30 - it never produced the registered series) is BROKEN for the
current layout:
1. **Non-recursive glob.** `MD_DIR.glob("*.tables.json")` over
   `data/extracted/md/banchero_costa/`, but the canonical sidecars live in YEAR
   subdirs `md/banchero_costa/<YYYY>/` (**249** of them). It finds 0-2.
2. **Stale schema.** It expects `metadata/reported_sales/freight_benchmarks/...`; the
   actual sidecars are `{source_file, stem, issue_date, report_week, tables,
   row_counts}` - so even the canonical sidecars parse to 0 rows. (The sidecars carry
   only sales/newbuilding/demolition; NO freight/ffa/commodities.)

**Running it ZEROED all 10 banchero series CSVs** (freight 20,321->0, sales 3,220->0,
...). Hit and fully reverted this run.

- **Guard added**: the script now refuses to write when it parsed 0 rows
  (`SystemExit(2)`), verified (exit=2, series untouched). Uncommitted.

## Restore path used (and how to reproduce it)
The canonical series are reproducible from `scratch/bancosta_dedup/`:
`PRE_<series>.csv` (pre-dedup) + `filter.py` (de-dups on all columns except
`source_file`). Applied: sales 3,244->**3,220**, newbuilding 2,391->**2,377**,
demolition ->**959** - exactly the registered counts. After restore **all 10 series
md5-match the pre-run control** (`scratch/banchero_gap/control.md5`).

Note the odd pair: `build_banchero_series.py` (git-committed) reads the md and writes
7 series (sales/newbuilding/demolition/secondhand/container/vhss/fx) + sidecars, but
**does NOT emit freight/ffa/commodities**. No script in the CURRENT tree produces those 3 big series
(20,321 / 7,618 / 8,447 rows): a grep of `scripts/` for `bancosta_freight`/`bancosta_commodities`
returns only the broken `stack_banchero_series.py` and two register/audit readers. They are
frozen artifacts with no current regenerator.

## Three-baseline test (why this is LOW priority even so)
- **Feeds**: TD3C/TC1-TC11 etc. already exist in `data/clarksons/fearnleys_benchmark_rates_continuous.csv`,
  `data/clarksons/gibson_tanker_rates_continuous_daily.csv`, `data/derived/tanker_forward_curves*.csv`.
- **App**: `index.html` references **0** `bancosta_*series` and **0** banchero md -
  none of this tier is displayed.
So the 3-week staleness is invisible to the dashboard; it is a KB-completeness item,
not a display defect.

## Next step (clear, bounded, but needs an owner decision)
Write a correct sidecar->series consumer (recursive glob + the real
`{tables,row_counts}` schema) OR refresh the 7 reproducible series via
`build_banchero_series.py` + `filter.py` (this WOULD add W36/W37/W39). Freight/ffa/
commodities cannot be refreshed by any current script. Do NOT run
`stack_banchero_series.py` as-is (now guarded).

---

## FOLLOW-UP RUN (2026-10-05 15:5x) - ROOT CAUSE FOUND, W36/W37 BACKFILLED, W39 WITHHELD

**The mystery of "no script produces freight/ffa/commodities" is solved: the
generator exists, it had simply gone DEAD on the current md format.**

### Root cause (measured, reproduced)
`run_banchero_world_class_llama.py::extract_structured_tables_from_md` detects a
markdown table by looking for the substrings `"| ---"`, `"|:---"`, `"|---"` in the
row below the header. The md tier later began emitting GFM **aligned** separators
(`| :--- | :--- |`), none of which match. On the current md the function returned
**0 rows for EVERY category** (freight/ffa/commodity/sales) - so no one could
regenerate the frozen three.

Evidence chain (control = the same doc):
- W38 md -> freight **0** (raw) vs **90** (after `| :---` normalisation) - and 90
  is EXACTLY the row count already in `bancosta_freight_rates_series.csv`.
- Full 248-doc re-extraction: freight 20,713 / ffa 7,708 / commodity 8,582, and
  per-week 2026 counts reproduce the existing series **exactly for W02-W35 and
  W38** (ffa 36, commodity 34-36 each), proving the extractor is correct once the
  separator is seen.

### Fix (small, safe)
The detection line in `extract_structured_tables_from_md` was changed to `any(s in lines[i+1].replace(" ", "") for s in ["|---", "|:---"])`. After the
fix the raw W38 md yields freight 90 / ffa 36 / commodity 36 / sales 23, and a
full 248-doc re-extraction is **byte-identical** to the manual-workaround run.
New tool: `scripts/extract/publishers/backfill_banchero_series.py`
(`--weeks 36 37 [--dry-run]`, union-append, prefix-equality asserted, idempotent).

### Backfill applied (W36, W37 only)
| series | before | added | after | weeks added |
|---|---|---|---|---|
| bancosta_freight_rates_series.csv | 20,321 | **+176** | 20,497 | 36, 37 |
| bancosta_ffa_series.csv | 7,618 | **+72** | 7,690 | 36, 37 |
| bancosta_commodities_series.csv | 8,447 | **+72** | 8,519 | 36, 37 |

Verification: the pre-existing prefix of all three files is **byte-identical** to
the pre-run control (`scratch/banchero_gap/backup_20261005_1550`, md5 matches
`scratch/banchero_gap/control.md5`); 0 duplicate keys on all-but-`source_file`;
and every appended `rate_current`/`price_current` is present **verbatim in the
doc's own md** - freight 87/87 + 89/89, ffa 36/36, commodity 36/36. Cross-week
sanity: W37 BCI `rate_previous` = 46,172 = W36's `rate_current` (consecutive).

### W39 WITHHELD (needs a look, not appended)
`banchero_costa_2026_W39_Bancosta-Weekly-2026-39` extracts freight **108** (vs
87/89) because ~18 FFA forward-curve rows (`Sep-26`, `Q4 26`, ...) were misrouted
into `freight_benchmarks` (sector SUPRAMAX), and its `ffa_assessments` is short
(18 vs the usual 36). The W39 doc is a shorter, differently-laid-out report (19
tables). Do NOT blind-append W39: it needs a render-and-look / layout-specific
fix. (Also still open: `secondhand_matrix`/`vhss`/`fx` lack W39 and
`container_fixtures` is stale at W23 - all from the same `build_banchero_series.py`
path, not touched this run.)

### Still low priority
Three-baseline test unchanged: the freight/ffa/commodity tier is **not displayed**
(0 `bancosta_*series` refs in index.html) and TD3C/TC1-TC11 already sit in the
live feeds. This is a KB-completeness fix, not a dashboard one. Never run
`stack_banchero_series.py` as-is (guarded).
