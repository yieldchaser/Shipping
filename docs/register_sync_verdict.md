# EXTRACTION_REGISTER staleness - VERDICT (2026-10-03, hourly supervisor run)

Scope: the authoritative ledger `docs/EXTRACTION_REGISTER.md` + `data/extracted/EXTRACTION_REGISTER.json`.
Trigger: `docs/OVERNIGHT_STATE.md` flagged the register's banchero-costa block as stale; this run
re-measured the WHOLE register against disk instead of that one block.

## What was measured (before)

- Instrument: `scripts/extract/verify_registers.py` and a direct csv.reader reconciliation of every
  `data/extracted/series/*.csv`. Logical rows (csv.reader), not raw lines.
- `data/extracted/EXTRACTION_REGISTER.json` `updated_at` was **2026-09-30 07:42Z**.
- `series_inventory`: 165 entries, **106 of them disagreed with disk**; 5 series on disk were in
  NEITHER structure (`hellenic_smm_market_drivers`, `poten_fleet_delivery_schedule`,
  `poten_fleet_statistics`, `poten_tanker_orderbook_age`, `poten_vlcc_historical_rates`).
- `master_series_inventory` (the structure `verify_registers.py` checks): 104 entries, **85 disagreed**.
- Worst deviations: `best_oasis_market_commentary` declared 9,838 vs disk **1,027** (-8,811);
  `gms_market_commentary` declared 9,399 vs disk **1,257** (-8,142);
  `hellenic_iron_ore_daily` declared 3,300 vs disk **1,175**; `bancosta_vhss` declared 1,714 vs **469**.
- `docs/EXTRACTION_REGISTER.md` Section 2 header read "(273,254 Total Rows across 98 CSVs + 1 Master
  Workbook)" while its own table footer read 596,632 and the table listed 166 series. Internally
  contradictory, and 98 vs 170 CSVs on disk.
- `verify_registers.py`: "Mismatches with JSON: 152, Mismatches with MD: 85".

## Two defects found in the synchronizer itself

The right fix is to RE-RUN the builder, never hand-edit. `scripts/sync_extraction_register.py` is that
builder, and it had two bugs, both measured:

1. `count_file_rows()` counted **raw lines minus one header line**. Any series whose text fields hold
   embedded newlines (multi-line broker commentary) is inflated. First run through it produced
   **615,101 rows against 592,848 logical csv.reader records across the same 170 files - a +22,253
   phantom overcount**. Patched to use `csv.reader` (logical rows).
2. The JSON writer updated `series_inventory` but never `master_series_inventory` nor the
   `total_master_stacked_rows` / `total_stacked_rows` / `total_master_series_csvs` / `total_series_csvs`
   totals, so `verify_registers.py` kept reporting mismatches after a "successful" sync (152 of them).
   Patched: the JSON block now also rebuilds `master_series_inventory` (file / target_metric / rows /
   columns / status) and the stacked totals from the same disk read.

## After

```
Discovered 170 CSV series and 2 XLSX workbooks.
Total CSV Data Rows on Disk: 592,848
SYNCHRONIZATION COMPLETE: 170 CSV series, 593,153 total rows.
```

`scripts/extract/verify_registers.py`:

```
Disk CSV count: 170, Disk logical rows: 592,848
JSON total_master_stacked_rows: 592,848
JSON master_series_inventory items: 170
MD Section 2 CSV count: 170
Mismatches with JSON: 0
Mismatches with MD: 0
ALL VERIFICATION CHECKS PASSED PERFECTLY (100.0% MATCH)!
```

Control on the `.md` rewrite: `git diff` touches ONLY Section 2 (header, 170 rows, TOTAL) plus three
SSY count strings (`ssy_route_rates` 5,190 -> 5,160, `ssy_capesize_index_time_series` 519 -> 516, and
the same pair inside Section 3 item 13). Sections 1, 3 and 4 are otherwise intact; 259 -> 266 lines.
Pre-fix copies (md5 `3dae65bcd0fdc80ee33daba4757d7b35` md /
`8089877a8bf30eb37f601a2a902393c4` json) in `scratch/register_sync/PRE_*`. Evidence artefact:
`data/extracted/register_audit.json`.

## Residual (disclosed, NOT fixed this run)

- **`intermodal_macro_series.csv`:** register 3,787 vs disk **4,803** (+1,016). A CONCURRENT agent
  (cron `12f7fa574166` "Unattended: source-by-source", run `20261003_091957`) rewrote
  `intermodal_macro` / `intermodal_bunkers` / `intermodal_maritime_stocks` at **09:32:56**, after this
  sync's 09:30 disk read. Re-syncing now would put two writers on the same two register files.
  **Action: re-run `python3 scripts/sync_extraction_register.py` after the intermodal thread lands.**
- The OTHER live threads observed: cron `12f7fa574166` (intermodal, active), and the banchero
  LlamaParse watchdog (`c0400ecf1a0b`) which restarted its parse at 09:26 as pid 20720 - that pid was
  already gone by 09:38, so the banchero parse is dying again on restart.
