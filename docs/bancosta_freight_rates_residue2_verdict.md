# CLOSED 2026-09-29 11:4x IST - bancosta freight_rates SECOND residue: 125 non-unit rows

Follows `docs/bancosta_freight_rates_residue_verdict.md` (the 80-row DRY_BULK misroute).
The state file recorded a second residue: **125 rows / 52 docs whose `unit` is not a unit**.
Re-measured this run into three classes, all in branch 11 of
`scripts/extract/publishers/run_banchero_world_class_llama.py`.

## Root cause: a FIXED column index in a table that redesigns across years

Branch 11 read `r[0]=route, r[1]=unit, r[2]=current, r[3]=previous, r[4]=wow, r[5]=yoy`.
That is correct only for the 6-column era. Two earlier shapes exist in the SAME source:

* 2021-2022 publish a **7-column** grid
  `| Category | Name | Unit | <d> | <d> | W-o-W | Y-o-Y |`
  (2021_W46 page 6, and `DELAYS AT TURKISH STRAITS` in 2021_W36/W39/W40/W47, whose row is
  `| Northbound | | days | 2.0 | 2.0 | +0.0% | +100.0% |` - 8 cells with a blank Name).
* Result: the **Name landed in `unit`**, the unit token in `rate_current`, current in
  `rate_previous`, previous in `change_wow`, and **W-o-W and Y-o-Y were dropped**.
  e.g. the page prints `TC1  MEG-Japan ( 75k) | ws | 113.2 | 115.4 | -1.9% | +37.9%`
  and the sidecar stored `unit="MEG-Japan (75k)", current="ws", previous="113.2", wow="115.4"`.

A third shape leaked the table's own **sub-header row** as data
(`AFRAMAX | Unit | 3-Jul | 26-Jun | W-o-W | Y-o-Y`), and a fourth is a fully empty row.

## Fix: anchor the UNIT column on CONTENT, not on index

```
ui = next((k for k, c in enumerate(r) if c.strip().lower() in FREIGHT_UNIT_TOKENS), None)
if ui is None: continue          # header / banner / empty row - not data
route_name = r[0:ui] joined      # "<code>" + "<name>", hyphenating a leading "TCE"
unit, current, previous, wow, yoy = r[ui], r[ui+1], r[ui+2], r[ui+3], r[ui+4]
```

`FREIGHT_UNIT_TOKENS = {ws, usd/day, usd/mt, usd/t, days, usd mln, usd/feu, points, index, idx, cbm}`.
A row with no unit token is a leaked header/banner/empty row and is dropped.
The `<code>` + `TCE <name>` join is hyphenated because the publisher's own page prints
`TC1-TCE` / `TC6-TCE` (verified in the 2021_W46 PDF text layer and the 2025_W10 markdown),
matching the 2024+ era's single-cell `TD15-TCE WAF-China`.

## Measured

| measure | before | after |
|---|---|---|
| `bancosta_freight_rates_series.csv` rows | 20,249 | **20,321** |
| rows whose `unit` is not a unit | 125 | **0** |
| leaked sub-header rows (`unit` = "Unit" or a date) | 68 | **0** |
| fully empty rows | 21 | **0** |
| shifted rows (unit token sitting in `rate_current`) | 33 | **0** |
| distinct `unit` values | 44 | **6** (all valid) |
| docs losing a real route code | - | **0** |

## Controls

1. **Cache-only rebuild reproduces the on-disk output byte-exact** BEFORE the patch
   (all 10 series CSVs md5-identical) - so any later change is the patch, not drift.
2. After the patch: **9 of 10 series CSVs byte-identical**; only `freight_rates` changed.
3. **Every one of the 196 newly-added rows verified verbatim**: its `rate_current`,
   `rate_previous` AND `change_wow` each appear as a token in the publisher's own PDF text
   layer (`pymupdf get_text`) or, where that page's text layer omits the table
   (2025_W10), in the LlamaParse pixel-read markdown. 196/196, 0 misses.
4. **Removed rows are junk**: 124 rows = 62 leaked header rows + 35 shifted rows
   (re-aligned in the added set) + 21 empty rows + 6 exact duplicates. Classifier found
   **0 rows with a real route code** removed, and no document lost a real route.
5. Ground truth read from the rendered page text for 2021_W46 page 6: all 27 CLEAN_TANKER
   rows now match the printed table exactly (`TC1 MEG-Japan (75k) | ws | 113.2 | 115.4 |
   -1.9% | +37.9%`, `TC11-TCE SK-Spore (40 k) | usd/day | 822 | -244 | +436.9% | -43.2%`, ...).

Rebuilt from the **cached** markdown (`run_banchero_world_class_llama.py` re-runs
`build_final_md_and_tables` for every doc whose raw md already exists) - **no API spend**.

## STILL OPEN in bancosta (measured, NOT fixed)

* Target #1, same root cause in branches 7/8: chart tables published as container indices -
  `freightos_index` 502 of 2,271 rows / 145 docs and `vhss_contex` 1,713 of 3,427 rows /
  218 docs have a `unit` cell that is neither a unit token nor a period label.
* The bancosta LlamaParse credit block (HTTP 402) - only the user can rotate the key.
