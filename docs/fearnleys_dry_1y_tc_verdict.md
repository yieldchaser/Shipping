# Fearnleys Dry-Bulk 1-Year T/C - delivered-tier fix (measured 2026-10-09)

Branch `auto/extract-fixes-2026-10-09` (NOT main). Unattended source-by-source run.
Liveness at start: no `run_*` extraction of ours; newest collected broker content
still **2026-10-02** (W40) - **W41 not arrived** (checked by FILENAME, not
`git status corpus`, which is blind to gitignored corpus PDFs).

## What was wrong

Two CODE fixes to `scripts/extract/publishers/run_fearnleys_normalized.py` were
committed during the previous run and **never became data**:

* `861054ddc` "anchor Dry 1Y TC rows to the 1 Year T/C block" (era-A unsigned
  positive changes; size-as-value; size-overwrite).
* `8872218c4` "recover the Dry Bulk 1Y TC first page on the 2024/2025 Fearnpulse
  layout".

The delivered `data/extracted/series/fearnleys_rates_series.csv` still carried the
pre-fix values.

## The delivered file is a MULTI-ERA ACCUMULATED MERGE - so a full regen was NOT applied

A pure current-code extraction (260 docs after 3 byte-identical duplicate skips)
yields **10,438 rows**. The delivered CSV holds **17,076 rows** and is a merge
accumulated across code eras, so **6,645 keys exist only in the delivered file** -
rows whose sections the current code no longer emits, e.g. `Capesize Spot` 583,
`Panamax Spot` 656, `Dry Indices` 219, `1 Year T/C Crude` 666, `Fleet Availability`
439, `LNG Spot` 76, `LNG 1Y TC` 38 (`Dry Spot` 887 is the current section for the
same routes). Several other sections are smaller in current code (`LPG Spot`
1,764 -> 551, `Bunker Prices` 1,381 -> 249, `Exchange Rates` 883 -> 511).

The delivered **markdown** tier is likewise not this runner's output: **257 of 260**
`data/extracted/md/fearnleys/*/*.md` differ structurally from a fresh run (delivered
= raw span dump, e.g. `fearnleys_2021_W46...md`; the runner writes frontmatter +
6-pillar normalized markdown). A full regeneration would therefore RESTRUCTURE the
tier, not surgically fix it, and was deliberately **not** run.

## Fix applied (surgical, section-scoped, idempotent)

`scripts/extract/publishers/apply_fearnleys_1y_tc_fix.py` merges ONLY
`section == "Dry 1Y TC"` rows from a fresh current-code extraction onto the
delivered CSV: add new keys, overwrite matching keys whose cells differ. It never
deletes a row and never touches any other section, so the accumulated multi-era
rows above are preserved untouched.

**Measured result (`--check` == the applied write):**

| metric | value |
|---|---|
| delivered rows | 17,076 -> **17,083** (+7, 0 deleted) |
| changed rows | **183** |
| changed cells | **212** |
| sections affected | **`02 Dry Bulk / Dry 1Y TC` only** |
| non-Dry-1Y-TC lines in `git diff` | **0** added, **0** removed |
| EOL / BOM | LF preserved, no BOM (17,084 LF) |
| idempotency | 2nd run = *"idempotent: nothing stale, no write"* |

* **+7 rows** = the recovered first page of the 2024/2025 Fearnpulse 1Y T/C block:
  `2026-09-23 Newcastlemax 50,383`; `2026-10-01` Newcastlemax 47,345 / Kamsarmax
  23,000 / Ultramax 20,000 / Capesize 34,678 / Panamax 20,500 / Supramax 18,000.
* **183 changes** = the size-published-as-price bug and its siblings, e.g.
  `2021-07-28 Capesize value 180.0 -> 27,500.0` (180 = the vessel size, not a
  $/day 1Y T/C), `2022-10-12 Ultramax value 64.0 -> 17,500.0` with `size 180' -> 64'`,
  and unsigned positive changes that read 0.0 -> e.g. `750.0`.

### Control (vision unavailable in the cron session - same-document reconciliation substituted)

Every new/added `value`, formatted with thousands separators, was checked against
the text layer of **its own** source PDF: **190 / 190 present verbatim** across
**86 distinct documents**. (The removed values did not need a separate token test -
180 / 208 / 82 / 64 / 75 / 58 are the vessel sizes that were being read as prices.)

Not app-displayed: `index.html` consumes Hasura-derived `fearnleys_*.json/csv`
(`fearnleys_desk_tenor.json`, `fearnleys_dry_routes_daily.json`, ...);
`fearnleys_rates_series.csv` appears only in audit/orchestrator scripts.

## Register kept consistent

The +7 rows break the register count, so it was updated with the artefacts:
`data/extracted/EXTRACTION_REGISTER.json` (`fearnleys_rates_series.csv` 17,076 ->
17,083; `total_master_stacked_rows` 639,749 -> 639,756) and
`docs/EXTRACTION_REGISTER.md` (Section 2 row + the Fearnleys publisher row, which
also carried a stale 14,669). `python3 scripts/extract/verify_registers.py` ->
**ALL VERIFICATION CHECKS PASSED PERFECTLY**: disk **639,756** == JSON == MD,
0 mismatches, 0 control chars, no emoji.

## Named, NOT changed

* Full md-tier regeneration (257/260 files restructure) - not a surgical fix.
* Era-2022 first-page rows remain unrecovered: on the 2022 layout the same
  two-page split exists but the page holding the 1Y T/C block is labelled
  `01 Tankers` by the chapter detector, and that page also carries the tanker
  `1 Year T/C (USD/Day)` table AND dry-bulk COMMENTARY words (`Capesize`,
  `Panamax`) after the block - so a naive chapter flip or gate widening risks
  binding commentary prose as a rate. Page-level chapter inference cannot separate
  them; needs line-level chapter tracking. Left open (low value: fearnleys is
  Hasura-redundant / SKIP-by-decision).

## Reproduce

```
python3 scripts/extract/publishers/apply_fearnleys_1y_tc_fix.py --fresh-csv scratch/fl_base/out_series.csv --check
python3 scripts/extract/verify_registers.py
```
