# census tail - star_asia valuation matrix + hellenic iron-ore table (2026-10-03)

**Status: both EXECUTED and PROVEN, LOSSLESS.** These were the two small remaining un-diagnosed
census items (13 + 10 duplicate rows).

## star_asia_valuation_matrix_series.csv - 3,245 -> 3,232 (-13)

All 13 duplicate rows come from the 2023 W41 / W42 PDF pair:

    star_asia_2023_W41_Market-report-Week-41.pdf
    star_asia_2023_W42_Market-report-Week-42.pdf

The two files are NOT byte-identical (md5 `eca6dc09` vs `f18a3945`) but **both covers read
"WEEK 41 - October 14, 2023"** - the W42-named file is a misfiled Week-41 report (same convention as
the agora W34/W35 pair). Both parse to `issue_date 2023-10-14 / report_week 41` and carry the same
valuation matrix, so every matrix row is written twice. The commentary differs, but the matrix is
identical, so dropping one copy loses no distinct value.

## hellenic_iron_ore_table_series.csv - 5,624 -> 5,614 (-10)

Multiple Wayback captures of the SAME MMI daily index page: `2026-03-19` from three captures
(03-17 / 03-18 / 03-19), `2026-06-08` from four (06-04 / 06-05 / 06-08), `2024-06-27` from two.
Same class as baltic_ncfi (HTML captures), not a parse defect.

## Fix - controlled row-filter (lossless)

Key = every column except `source_file`; one row kept per key (lexicographically-first `source_file`).

## Control

* Full-column key: removed 13 / 10, `POST minus PRE` = **0 added** on both; post dup keys 0.
* Entity sets identical pre/post, 0 PRE-only / 0 POST-only:
  star_asia (issue_date, sector, vessel_type, size_dwt_teu) = 3,232;
  hellenic_iron_ore (issue_date, index_family, index_code, fe_grade) = 5,601.

## Writers (guards NOT yet wired - noted for a future pass)

`run_star_asia_world_class.py` (and `stack_unstacked_tables.py`) write the valuation matrix;
`run_hellenic_iron_ore_images.py` (and `stack_unstacked_tables.py`) write the iron-ore table. Neither
runner is patched here, so a future re-run would reintroduce the duplicates; the delivered CSVs are
the artefact of record.

## Notes

* `data/extracted/**` is gitignored - the deduped CSVs are working-tree artefacts, NOT committed.
* Pre-fix copies `scratch/census_tail/PRE_*.csv`; filter `scratch/census_tail/filter.py`.
