# Seabrokers extended-series rebuild (per-source pipeline)

Source of the 8 `seabrokers_*_series.csv` in `data/extracted/series/`.
Re-run order (local, CPU, no API):

1. `python3 scripts/extract/extract_all.py <page.pdf> --out scratch/seabrokers_store`
   then move `<out>/<source>/<stem>/` into `data/extracted/corpus/seabrokers/<stem>/`
   (the store tier is `data/extracted/corpus/seabrokers`, 97 docs).
2. `python3 scripts/extract/publishers/seabrokers_ext/02_extract.py`  -> scratch/seabrokers_ext/rows.jsonl
3. `python3 scripts/extract/publishers/seabrokers_ext/03_build.py`    -> data/extracted/seabrokers_extended.parquet
4. `python3 scripts/extract/publishers/export_seabrokers_series.py`   -> the 8 series CSVs

`02_extract.py` also reuses `data/derived/seabrokers_osv_dayrates.csv` (OSV spot-rates ledger).
Paths in these scripts are relative to the repo root. Copied from scratch/ 2026-10-08
(sept-2026 gap fix); see `docs/seabrokers_sept_gap_verdict.md`.
