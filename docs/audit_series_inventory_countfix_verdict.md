# Verdict: scripts/audit_series_inventory.py counted the WRONG thing (detector bug, register was right)

**Run:** 2026-10-09 ~10:5x IST, branch `auto/extract-fixes-2026-10-08`.
**Class:** a detector that lies - the register gate it contradicts was exact.

## What it reported
Running `python3 scripts/audit_series_inventory.py` printed:

    Found 180 CSV series and 3 XLSX series on disk.
    Total CSV data rows on disk: 661,127
    --- 10 Series with OUTDATED row counts in register ---
      * best_oasis_market_commentary_series.csv: register has 1,039, disk has 9,945 (diff: +8,906)
      * gms_market_commentary_series.csv:          register 1,262, disk 9,432 (+8,170)
      * hellenic_iron_ore_daily_series.csv:        register 1,175, disk 4,770 (+3,595)
      * hellenic_iron_ore_commentary_series.csv:   register 1,179, disk 1,839 (+660)
      * bancosta_demolition_series.csv:            register   959, disk   974 (+15)
      * drewry_ais_crude_vlcc / drybulk_handysize / lpg_fr / product_lr2: +8/+4/+8/+8
      * seabrokers_renewables_and_ets_series.csv:  register    16, disk    20 (+4)

Read naively this says the tracked register is stale by ~21k rows and should be "fixed".

## Why it is wrong (measured)
`count_rows()` counted **physical lines** (`for _ in f`). A CSV row whose quoted field
contains an embedded newline spans several physical lines, so this over-counts exactly
those files - the prose/commentary series (long quoted blobs) plus a few wreck-report cells.
The same +22,253-class phantom overcount is documented in
`scripts/sync_extraction_register.py`'s own docstring, which deliberately uses `csv.reader`.

Re-counted every one of the 10 flagged files with `csv.reader` (logical rows, header excluded):

| series | register | csv.reader | physical lines |
|---|---|---|---|
| best_oasis_market_commentary | 1,039 | **1,039** | 9,945 |
| gms_market_commentary | 1,262 | **1,262** | 9,432 |
| hellenic_iron_ore_daily | 1,175 | **1,175** | 4,770 |
| hellenic_iron_ore_commentary | 1,179 | **1,179** | 1,839 |
| bancosta_demolition | 959 | **959** | 974 |
| drewry_ais_crude_vlcc | 32 | **32** | 40 |
| seabrokers_renewables_and_ets | 16 | **16** | 20 |

Every register count is EXACT. Across all 180 series: logical total = **639,749**;
physical-line total = **661,127**; the +21,378 delta is confined to **those 10 files**.

## Consistency of the register (unchanged, just confirmed)
- `data/extracted/series/*.csv` logical rows = **639,749** == `EXTRACTION_REGISTER.json`
  `total_master_stacked_rows` (639,749) == `.md` Section 2 CSV sum.
- +305 Master Workbook rows = **640,054** == JSON `total_rows_extracted` == the .md
  Section 2 grand total. **No register change was needed or made.**

## Fix
`scripts/audit_series_inventory.py` `count_rows()` now uses `csv.reader` (header skipped),
matching the sanctioned sync script; the unused `import os` was dropped so `ruff check`
is green. One file, +13/-6 lines (`git diff --numstat`).

## Control (before vs after, SAME register file)
- before: `Total CSV data rows on disk: 661,127` + **10** series flagged OUTDATED
- after:  `Total CSV data rows on disk: 639,749` + **0** flagged, 0 missing either way
- `ruff check scripts/audit_series_inventory.py` -> All checks passed.

Lesson (the project's recurring one): a detector's output is not evidence. This one
manufactured a data-integrity alarm that would have sent a naive "fix" to rewrite the
register with 21k phantom rows.
