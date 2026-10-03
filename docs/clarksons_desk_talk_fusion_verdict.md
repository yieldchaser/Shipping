# Clarksons Desk Talk: sales-table fused into commentary - FIXED (2026-10-03)

Follows the residual left open by the 13:3x supervisor run in
`docs/clarksons_desk_talk_regen_verdict.md` ("17 of the 355 delivered rows still
carry sales-table text fused into `commentary_text`"). That figure was a loose
predicate; the content-anchored measurement below finds a smaller, exact class.

## The defect (measured, not inferred)

Three bulletins - `2021-07-02` (W27), `2021-07-09` (W28), `2021-07-23` (W30) - are
the only documents in the 165-report corpus whose markdown carries **no pipe
character** (`pipes=0`, checked on all 165 cached `.md`). In those three the S&P
sales table is rendered as **column-flattened bare cells** (a `VESSEL / DWT / BLT
/ DETAILS / SS/DD / PRICE / BUYER` header, then 7-9 lines per vessel:

```
85 'NISSOS ANTIPAROS'
86 '318,744'
87 '2019 HYUNDAI HEAVY ULSAN'
88 'WARTSILA WINGD 7X82-B'
...
93 'en bloc'
94 'NORWEGIANS'
```

No pipe -> the commentary builder's table guards never fired, so those cell
lines were appended to the running commentary block. `clarksons_desk_talk_series.csv`
carried **6** such rows: per document a `Desk Talk` row that was pure cell text,
plus a `Tankers` row that was the cell block fused onto the following
newbuilding prose (e.g. `NISSOS ANTIPAROS 2019 HYUNDAI HEAVY ULSAN WARTSILA
WINGD 7X82-B Scrubber & BWTS fitted ... In tankers, STX Jinhae have announced
...`, 4,180 chars).

The earlier "17 rows" count used a looser vessel-token predicate and included
**false positives**: the 2026 rows (`2026-03-07`, `2026-05-29`) are genuine
market commentary that merely names builders (`SAMSUNG HI`, `HYUNDAI MIPO`,
`DAEWOO (DSME)`). Those are correct and were NOT touched.

## The fix

`scripts/extract/publishers/run_clarksons_hellas_world_class.py`:

- new `flattened_table_cell_indices(lines)` - delimits the flattened block by
  content: from the literal `VESSEL` header to `BUYER`, then body lines until the
  first page break / page furniture / prose line (commentary wraps at ~120 chars,
  cells are short). No geometry, no fixed size.
- the commentary loop now enumerates line indices and skips any line in that set.
- the helper is invoked **only when `"|" not in markdown_text`**, so every
  pipe-table report is provably untouched.

## Verification (controls, not metrics)

- **Row-level set diff** old-vs-new over all 165 docs
  (key = issue_date, report_week, sector, commentary_text, source_file):
  **removed 6, added 3, and every removed/added row is in one of the 3 docs**;
  the other 349 commentary rows are byte-identical. 355 -> **352** rows.
- **No prose lost:** every new commentary text is an exact **suffix** of the old
  text for the same (doc, sector) - only the leading cell prefix was removed
  (2021-07-02 Tankers 4,180 -> 4,040 chars; 2021-07-09 1,028 -> 896;
  2021-07-23 954 -> 898). Tail sentences intact.
- **CSV control:** md5 of all **170** series CSVs pre/post - **only
  `clarksons_desk_talk_series.csv` changed; the other 169 byte-identical**
  (sales 1,329 / demolition 70 / macro 165 unchanged).
- **Sidecar md:** `data/extracted/md/clarksons/2021/<doc>.md` now shows clean
  prose under `### Tankers`; the engine details remain in the sales-table
  section (correct).
- **Hygiene:** dup keys **0**, blank commentary **0**; the only remaining row
  whose commentary starts with a builder token is genuine prose (`Hyundai have
  announced an order at their Hyundai Vinashin facility...`).
- **Register:** re-synced; **594,104 -> 594,101** logical rows / 170 CSVs,
  `verify_registers.py` = **0 mismatches**.

## Residual (measured, NOT fixed)

- The flattened-doc rows keep the publisher's own section label: the
  2021-07-02/09 `Tankers` row now carries newbuilding prose (the flattened md
  loses the `Newbuilding` header). Left as-is - a wrong relabel is worse than the
  publisher's own heading.
- The `Desk Talk`/`Tankers` sector for these three docs is coarse, but the
  delivered text is now clean.
