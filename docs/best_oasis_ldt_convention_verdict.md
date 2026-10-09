# Best Oasis deals tier - LDT separator defect (page + cross-publisher confirmed)

**Status: FIXED (code + delivered data). 2 files, 1 cell each. Register gate green.**

## The defect (measured)
`run_best_oasis_demolition.py` parsed the LDT cell with
`re.sub(r"[^\d.]", "", ldt_raw)` then `float(...)` - i.e. it stripped commas
(so ISO thousands like `8,015` -> 8015 was correct) but KEPT a dot, assuming a
dot is always a decimal point. Best Oasis mixes separators in the SAME LDT
column: most rows print ISO (`8,015`, `23,038`), but at least one prints EU
period-thousands. So the delivered series shipped:

    2024-03-01,EL YOUSSEF,MPP,7422049,1975,GERMANY,1.995,... (ldt)
                                                  ^^^^^ = 1,995 LDT read as 1.995

A 1000x error in the plausible direction: `1.995` is a well-formed float.

## Ground truth (two independent publishers, no vision needed)
1. **Best Oasis 2024-03-01, page index 7** (`pymupdf` text layer):
   `EL YOUSSEF / MPP / 7422049 / 1975 / GERMANY / 1.995 / DELIVERED /
   ALIAGA, TURKIYE / UNDISCLOSED` sits beside `8,015`, `3,104`, `23,038`,
   `8,920`, `11,486`, `1,010`, `2,127`, `3,535`, `2,234` - the column's own
   numbers are tonnes, and OSCAR 1 in the same table prints `1,010` WITH a
   comma. `1.995` is that publisher's period form of 1,995.
2. **Intermodal 2024 W09** independently lists the same vessel:
   `EL YOUSSEF ... dwt 4106, ldt 1995, year_built 1975, GENERAL CARGO`.
   Two publishers agree on 1995.

## Blast radius (measured corpus-wide)
A sweep of all 174 `*_series.csv` for `^<int>\.<exactly 3 digits>$` inside
columns whose modal value form is `<int>.0` (integer-as-float) found EXACTLY
this one value, in the two byte-identical mirrors:
- `data/extracted/series/best_oasis_deals_series.csv`
- `data/extracted/series/hellenic_best_oasis_deals_series.csv`

After the fix the same sweep returns **0** corpus-wide.

## The fix
- **Code** (`run_best_oasis_demolition.py`, ldt block): shape-based -
  `^\d{1,3}(?:\.\d{3})+$` -> strip the dots (a thousands token; LDT is integer
  tonnes). A real fraction (`197.74`) or an already-float form (`1000.0`) is
  untouched.
- **Data** (`scripts/extract/publishers/fix_best_oasis_ldt.py`, per-source,
  idempotent): rewrote the one cell to the column's own form `1995.0`.

## Verification (control)
- `git diff --numstat` = **1/1** in each file; the single changed line is the
  EL YOUSSEF row and the ONLY changed field is `ldt` (`1.995` -> `1995.0`);
  every other byte of the line identical.
- Rows **897 -> 897** (unchanged); CRLF preserved; no BOM; the mirrors stay
  byte-identical (sha256 `d1d76c4a26...`).
- 2nd run prints *"idempotent: nothing stale, no write"* (0 cells).
- `verify_registers.py` -> **ALL PASSED**, 180 CSVs / **639,756** == JSON == MD.
- Not app-displayed (`index.html` 0 `best_oasis` refs) - a correctness repair
  in a "Verified" series, not a visible change.

## Not touched
The neighbouring ISO rows (`8015.0`, `3104.0`, `23038.0`) are already correct;
only the period-form token moved.
