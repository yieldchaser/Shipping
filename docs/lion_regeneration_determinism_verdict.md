# lion regeneration "non-determinism" - ROOT-CAUSED and FIXED (2026-10-04)

Status: root cause proven, fix applied to the runner source, output regenerated and verified.
Run by: overnight supervisor cron (345bc8db9233). Branch untouched by this run (no git ops).

## The item

`docs/OVERNIGHT_STATE.md` carried "lion regeneration non-determinism - the one genuinely
UNINVESTIGATED item": re-running the lion runner changed the delivered series values/row counts.

## Root cause (measured, not guessed)

The delivered lion series on disk (written 2026-10-04 18:40) had MORE rows than the
2026-10-03 dedup verdict (`docs/lion_dedup_verdict.md`) recorded, and duplicate keys had
reappeared:

| series | 2026-10-03 post-dedup | 2026-10-04 18:40 delivered | dup keys |
|---|---|---|---|
| lion_deals_series | 1,241 | 1,297 | 28 |
| lion_sales_series | 1,136 | 1,192 | 28 |
| lion_demometer_series | 552 | 576 | 12 |
| lion_demo_sales_series | 105 | 105 | 0 |

Every one of the new duplicate rows belongs to issue W40 (2026-10-02). The corpus now holds
that ONE issue as TWO files:

    corpus/01-brokers/lion/2026/lion_02_10_2026_lion_shipbrokers_weekly_market_report_week_40_2026.pdf
    corpus/01-brokers/lion/2026/lion_2026_W40_Lion-Weekly-Report-02-October-2026-W40.pdf

Both are BYTE-IDENTICAL: sha256 f6f19434443cd370be0109bd415ee4c6c8063d2565c376703dcdcd5979194806,
`cmp` clean. They are the same issue collected under the old (`lion_YYYY_WNN_...`) and the new
fetcher (`lion_DD_MM_YYYY_...`) naming conventions.

`scripts/extract/publishers/run_lion_tables.py` line 711 globbed every `*.pdf` with no content
dedup, so W40 was parsed twice and each of its rows emitted twice. That is the WHOLE of the
"non-determinism": the runner is deterministic given a unique input set; the input set was not
unique.

## The fix

`scripts/extract/publishers/run_lion_tables.py`: after the glob, drop PDFs whose sha256 was
already seen, printing `[dup-input] skipping byte-identical copy: <dup> == <kept>`. Conservative:
only EXACT byte-duplicates are dropped, never distinct content.

## Verification (two passes, controls)

Command: `python3 scripts/extract/publishers/run_lion_tables.py`

    [dup-input] skipping byte-identical copy: lion_2026_W40_Lion-Weekly-Report-02-October-2026-W40.pdf == lion_02_10_2026_lion_shipbrokers_weekly_market_report_week_40_2026.pdf

| series | before | after | rows removed | rows added | dup keys after |
|---|---|---|---|---|---|
| lion_deals_series | 1,297 | 1,269 | 28 | 0 | 0 |
| lion_sales_series | 1,192 | 1,164 | 28 | 0 | 0 |
| lion_demometer_series | 576 | 564 | 12 | 0 | 0 |
| lion_demo_sales_series | 105 | 105 | 0 | 0 | 0 |

The after-counts are exactly the 2026-10-03 post-dedup counts PLUS the single W40 issue
(deals 1,241+28, sales 1,136+28, demometer 552+12, demo_sales 105+0). Every removed row is the
W40 duplicate; `rows_added` is 0 on all four (no value invented, nothing else dropped).
Control: `lion_demo_sales_series.csv` is byte-identical across the change
(sha256 9c302d6fed083ce680c4b80ef689807169d105a7adb977341a4a7bedc76feece).

Determinism proven: a SECOND consecutive run produced `lion_deals_series.csv` with the identical
sha256 (90043a06d7f69c68570e2786ada37a27986384e3d76833fcbfedee4171f6f467).

`data/extracted/md/lion/` still holds 48 `.md` files (47 rewritten this run, count unchanged).

## Still open (not this run's scope)

- The DUPLICATE CORPUS FILE itself is left in place (corpus is the user's data; the runner now
  tolerates it). If the fetcher keeps emitting the new naming alongside the old, more issues will
  become two-file duplicates; the dedup is content-based so it already covers that.
- The runner edit is UNCOMMITTED (this cron run is barred from git operations). Next code run
  should commit it on the extraction branch.
- `run_lion.py` (the parquet writer: lion_deals.parquet / lion_demometer.parquet, dated 2026-09-24)
  does NOT have the dedup; if it is re-run it will double W40 in the parquet.

## Follow-up (2026-10-04 20:0x, next 30m run) - latent dedup bug in the PARQUET writer closed + code committed

The item above left two sub-items open; this run closed both.

**1. `run_lion.py` (the parquet writer: `lion_deals.parquet` / `lion_demometer.parquet`) now
has the same content-dedup.** It was the flagged latent bug ("if re-run it will double W40 in
the parquet"). Added in two places, mirroring `run_lion_tables.py`:
- `build_txt()` dedups byte-identical PDFs from the corpus glob before writing a `.txt`
  (`[dup-input] skipping byte-identical copy: ...`);
- `main()` dedups the cached `*.txt` list by content (`[dup-txt] ...`), so a stale duplicate
  text cache cannot re-introduce the double.

Measured on the current corpus: `corpus/01-brokers/lion` = **48 PDFs -> 47 unique, 1 skipped**
(`lion_2026_W40_Lion-Weekly-Report-02-October-2026-W40.pdf == lion_02_10_2026_lion_shipbrokers_weekly_market_report_week_40_2026.pdf`).
Syntax-checked (`ast.parse`). NOTE: `run_lion.py`'s `write_md()` emits a THIN md format (no
frontmatter) that predates the richer `run_lion_tables.py` output now on disk, so the full
runner is NOT re-run here (re-running would downgrade the md); the fix protects the parquet path.

**2. Deliverables verified healthy on disk (read-back):** `lion_deals_series.csv` 1,269 rows,
`lion_sales_series.csv` 1,164, `lion_demometer_series.csv` 564, `lion_demo_sales_series.csv`
105 - **0 exact duplicate rows** in each; `lion_deals.parquet` 1,145 rows / 43 issues / 0 dup
rows, `lion_demometer.parquet` 516 / 43 / 0.

**3. Code committed** on the extraction branch: `scripts/extract/publishers/run_lion_tables.py`
(the dedup from the run above) + `scripts/extract/publishers/run_lion.py` (this fix).

Remaining (unchanged, human call): the duplicate corpus PDF itself is left in place (content
dedup now tolerant of it; if the fetcher keeps emitting both naming conventions the dedup covers it).
