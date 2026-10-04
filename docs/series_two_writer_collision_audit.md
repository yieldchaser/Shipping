# Series two-writer collision audit — the class is CONFINED (2026-10-04)

Bounded, read-only sweep to find whether the silent column-loss defect just
root-caused for the `hellenic_iron_ore_pdf_*` family (two runners writing one CSV
with different schemas + `extrasaction="ignore"`) exists anywhere else in
`data/extracted/series/` (172 CSVs).

## Method

Per-column blank ratio for every series CSV; flag any column blank on >=95% of
the file's rows. That is the measurable signature of a schema collision: one
writer's whole column family goes blank while the sibling writer's columns carry
the same entity's data. (Writer-count by grepping the file name is too noisy -
the register/audit/orchestrator scripts merely *mention* the filenames.)

Script: `scratch/empty_column_scan.py`.

## Result: 21 files flagged, 20 benign

The only file family with the collision signature is the 5 **known**
`hellenic_iron_ore_pdf_*` files:

| file | rows | blank columns (>=95%) |
|---|---|---|
| `hellenic_iron_ore_pdf_indices_series.csv` | 11,625 | `market_type`/`value` 11,553 (99.4%) |
| `hellenic_iron_ore_pdf_brands_series.csv` | 31,470 | `fe_pct`/`product_type`/`change_pct` 31,272 (99.4%) |
| `hellenic_iron_ore_pdf_futures_series.csv` | 2,233 | `price`/`settlement` 2,207 (98.8%) |

The other 18 are benign, checked one by one:

- **record_type-differentiated files** - a wide union schema where a column
  applies to only one `record_type`. `bancosta_newbuilding` (`owner`/`size`/`yard`
  blank on all 2,377 rows because the 871 `order` rows carry that info inside the
  free-text `comments` field, e.g. "Wisdmom Marine signed with Tsuneishi Zhoushan
  3 x Kamsarmax"); `bancosta_demolition` (`vessel_name` etc. populated on the 7
  `demolition_deal` rows only); `clarksons_snp_sales` (`gear_cranes`/
  `special_coating` never populated by the source).
- **vestigial alternates** - a second representation of a value already present:
  `seabrokers_rigs_market.value_text` (numeric `value` is populated, 130000.0) and
  `seabrokers_fleet_moves.value_text` (the info is in `note`).
- **unused/derivable** - `intermodal_newbuilding_orders.sector` (blank; `vessel_type`
  is populated), `advanced_shipping_sales.CBM` (container hulls only),
  `star_asia_ferrous_scrap.domestic_price_local_cur` (subset rows).

**Verdict: no new two-writer collision. The class is confined to the known
hellenic iron-ore family.**

## Bonus: fault 2 (row selection) COMPLETED root cause

The prior run's verdict named a second fault in `run_hellenic_iron_ore_pdf.py`'s
`benchmark_indices` parse but left the mechanism open ("needs the cached
markdown"). Reproduced here from `cache_mmi_iron_ore_pdf/*b472c50*.md`
(2021-07-14) with the exact `parse_page2` row collection
(`scratch/verify_row_selection.py`):

- The LlamaParse markdown embeds the **multi-period statistics table as an HTML
  `<table>`** (row index 18: `IOPI58 | 58% Fe Fines | 1027 | 1052 | 1267 | 1199 |
  1251 | 1251 | 149.38 ...`).
- `parse_page2` builds `all_rows` by consuming **all HTML `<tr>`s FIRST, then the
  markdown pipe rows**. The correct daily benchmark row is markdown, at index
  **207**: `IOPI58 | 58% Fe Fines | **1240** | **-17** | **-1.4%** | 1251 | 1104 |
  755 | 1421 | ...`.
- `add_idx` dedups on `(index_name, market)` and keeps the **FIRST** match, so the
  statistics row wins -> `price=1027, change=1052, change_pct=1267`.

Both rows are 16 cells, so the `len(tds) >= 15` gate cannot separate them.

**Exact, value-based fix** (doctrine: label/gate by VALUE, not order/position):
the benchmark row satisfies `low <= price <= high` (755 <= 1240 <= 1421), the
statistics row violates it (`price=1027`, `low=1251`, `high=1104`). A gate in
`add_idx` - reject only when `low` and `high` are both present and not
`min(low,high) <= price <= max(low,high)` - rejects every statistics row and
accepts the daily benchmark row (verified against IOPI62 856<=1558<=1680, IOPI65
921<=1808<=1894, IOPLI62 862<=1868<=1868). Alternative: process markdown rows
before HTML `<tr>`s.

## Impact: NOT displayed — low priority

- `index.html` does not reference any `hellenic_iron_ore_pdf_*` CSV
  (`grep extracted/series index.html` = 0).
- The app renders iron ore from `knowledge/chunks/hellenic_iron_ore_<year>.jsonl`,
  which is built from the **raw PDF text** and is CORRECT
  ("1558 1808 1240 ... -17 -1.35%").
- So the wrong value lives only in the md `benchmark_indices` table and the
  non-displayed indices CSV.

Because a re-run of `run_hellenic_iron_ore_pdf.py` also re-stacks ALL 17 CSVs -
which, without the union-preserving upsert, would re-introduce the collision -
the two fixes are entangled and the schema/ownership call stands as recorded.
Both row-selection fix and union fix are named here so the next run can apply
them together in one controlled pass.
