# hellenic `iron_ore_pdf_indices` - fault 2 blast radius MEASURED (2026-10-04)

Follow-up to `docs/hellenic_iron_ore_two_writer_verdict.md`. That doc root-caused the
two-writer family and named option (a) (union-preserving upsert + re-stack) as the
low-risk repair, but flagged a second, independent **row-selection fault** in the
`run_hellenic_iron_ore_pdf.py` indices parse as "fix-ready, needs the cached
markdown". This run measured that fault's blast radius from the sidecars on disk.
**Nothing changed unattended** - this makes the reserved call decision-ready.

## Population and method

Every recovered value would come from the 1,190 sidecars in
`data/extracted/md/hellenic/iron_ore_pdf/<year>/*.tables.json` (the source of the
re-stack). Read all `benchmark_indices` entries (11,583) and tested each row for the
signature of the mis-selected multi-period statistics row:

- `|change| > 0.5 * price` - a daily change cannot be half the price (measured on RMB
  and USD rows alike; independent of number convention).

Ground truth anchor: `2021-07-14_..._b472c50b9ce5` page 2 prints IOPI58
`Price 1240 | Change -17 | -1.4% | MTD 1251 | YTD 1104 | Low 755 | High 1421`.

## Measured result

| metric | value |
|---|---|
| `benchmark_indices` entries across sidecars | **11,583** |
| of which carry a `price` | **11,583 (100%)** |
| rows with `\|change\| > 0.5 * price` (impossible) | **2,707 (23.4%)** |
| RMB/wet-tonne rows | 4,629 (bad 1,294) |
| USD/dry-tonne rows | 6,954 (bad 1,413) |

Bad rows concentrate by index name: **IOPI58, IOPI62_61, IOPI65, IOPLI62 (395 each)**
plus their `_CFR_EQ` variants (IOPI62_61_CFR_EQ 395, IOPI58_CFR_EQ 395, IOPI65_CFR_EQ
395, IOPLI62_CFR_EQ 110), then IOSI65 (60) / IOSI62_61 (58).

Ground-truth example (sidecar `2021-07-14`, IOPI58):
`price=1027, change=1052, change_pct=1267, mtd=1199, ytd=1251, low_52w=1251, high_52w=1104`
vs page `price 1240, change -17, -1.4%, mtd 1251, ytd 1104, low 755, high 1421`.
Both symptoms of the mis-selection are visible: `price` is the **March** period (1027),
`change`/`change_pct` are the **April/May** period (1052/1267), and `low_52w > high_52w`
(1251 > 1104) - an inversion impossible in a correct row.

## Consequence for option (a) - it is NOT sufficient on its own

The re-stack recovers the lost `value` column from the sidecars, but the sidecars
THEMSELVES hold the mis-selected row for these indices. Applying option (a) alone
would publish **~11,553 recovered benchmark prices of which ~2,707 carry an impossible
`change`** (and shifted `change_pct`/`mtd`/`ytd`/`low`/`high`) - i.e. it would move a
blank into a plausible-looking wrong number, the exact failure mode the skill warns
about. The parser row-selection fix (the value gate `low <= price <= high` named in the
two-writer verdict) MUST land in the SAME pass as the schema change.

Note the gate is sound against this data: on 2021-07-14 the correct IOPI58 row
(755 <= 1240 <= 1421) passes while the statistics row (1027, low 1251, high 1104)
violates it - so it accepts the benchmark row and rejects the stats row, as intended.

## Live status of the defect

The shipped `data/extracted/series/hellenic_iron_ore_pdf_indices_series.csv` imports the
sidecar's `change`/`change_pct` verbatim for the old-format rows (verified: 2021-07-14
row carries `change=1052`), so the 2,707 impossible changes are **live in the CSV**, not
just in the sidecar. `value` is blank on 11,553 of 11,625 rows. **No `index.html`
consumer references this CSV (0 hits)**, so nothing user-visible is affected today.

## Revised scope of the reserved pass (measured, not estimated)

1. parser fix: value-gate the indices row selection (`run_hellenic_iron_ore_pdf.py`, `add_idx`);
2. schema fix: union-preserving `upsert_rows_to_csv` in `run_smm_iron_ore_daily.py`;
3. controlled order: `run_hellenic` re-stack (pure sidecar read - no PDF parse, fast) then
   `run_smm_iron_ore_daily.py` (its own 1-page PDFs, ~72 SMM rows).

Steps 1+2 are prerequisites for each other; doing only 2 injects 2,707 wrong values.
