# intermodal_indicative_values_series.csv - defect fixed (measured 2026-09-28)

Closes item 7.1 (one-column shift) and item 4.3 (exact duplicate rows) of
`docs/series_verification_ledger.md`. No re-extraction was needed: the fix is in
`scripts/extract/publishers/run_intermodal_full.py`, which rebuilds the 8 intermodal
series CSVs from the **cached LlamaParse markdown** (`--reparse-only`) - 252 docs,
0 failures, 35.5 s. No API credits were spent.

## What was wrong

**1. One column shift (the ledger's 7.1).** The Bulker "Indicative Market Values
(5 yrs old)" table is emitted by LlamaParse with a SEPARATE size cell that the header
row does not name. The parser read that cell as the price, shifting the whole row one
column left and silently dropping the last year.

Ground truth, rendered page text of `intermodal_2021_W26` p3:

```
180k  37.5  37.1  1.0%  27.6  31.1  36.1     (Jul-21 avg / Jun-21 avg / +/-% / 2020 / 2019 / 2018)
```

Old CSV row: `current=180.0, prev_month=37.5, change=37.1, y1=1.0, y2=27.6, y3=31.1`
- 180.0 is the vessel SIZE, not a price; the 2018 value (36.1) was lost.

Measured scale: **537 rows** (all of `Capesize`, `Capesize Eco`, `Kamsarmax`,
`Ultramax`, `Handysize` in the 2021-2022 issues where the size is a separate cell).

**2. Two more shapes the position-based parser could not see.** All measured in the
cached markdown, same publisher, same table:

| shape | example | old parser did |
|---|---|---|
| A `name｜size｜cur｜prev｜pct｜y1｜y2｜y3` | 2021_W26 bulker | read size as the price (defect 1) |
| B `name｜size｜cur｜pct｜y1｜y2｜y3` (prev-month cell dropped by LlamaParse) | 2024_W11 bulker, 2024_W21 tanker | read the +/-% as the prev price and the 2023 value as the change |
| C `''｜name｜size｜cur｜prev｜pct｜...` (leading empty cell) | 2021_W50 tanker LR1/MR | emitted `sector=Tanker, vessel_class=''`, `current=1.0` (from the string `LR1`), `prev=75.0` (from `75KT DH`) |

**3. A spreadsheet error published as a price.** `intermodal_2025_W27` prints the
literal string `#DIV/0!` for the bulker current month AND the +/-% - in the PDF
itself. `parse_float('#DIV/0!')` returns **0.0**, so the old code published four
$0m prices.

**4. Exact duplicate rows.** The cached markdown for some issues contains the same
table TWICE (measured: `intermodal_2024_W21` md carries the tanker indicative table
at byte 9014 and again at 12374), so every row was emitted twice:
**75 duplicate rows** in this file, **48** in `intermodal_tc_rates_series.csv`, 0 in
the other six.

## The fix (content-anchored, not position-anchored)

`parse_indicative_row()` anchors on CONTENT instead of position:
- the tail starts at the first cell that is a plain number **or** a spreadsheet error
  token; everything before it is the label/size (so shape A, B and C all map right);
- the `+/-%` cell is found by its `%`, so a dropped prev-month cell cannot shift the
  years;
- when the `+/-%` is an error token the row is mapped by its known 6-slot tail and the
  missing values stay **NULL** - never 0.0;
- `write_series_csv()` drops rows identical in every column (double counts).

Plus a recovery pass, `recover_missing_prev_month()`: for a row whose prev-month cell
LlamaParse dropped, the value IS on the page, so it is recovered from the report's own
PDF text layer by searching for the exact numeric run
`[current, <one number>, pct, y1, y2, y3]` and requiring **exactly one match in the
whole document**. No unique match -> left blank. **14 values recovered.**

## Verification (no vision tool in this cron session - stated, not implied)

1. **Trial before bulk**: `2021_W26` parsed and compared line-by-line against the
   rendered page text - all 10 rows exact (tanker unchanged, bulker corrected).
2. **Independent source of truth**: for 24 documents sampled across all six years
   (2021-2026), the extracted value tuple was searched as a CONSECUTIVE numeric run in
   the PDF's own text layer (`pymupdf`, i.e. not the LlamaParse markdown the parser
   consumed): **219/219 rows (100.0%)**.
3. **Internal consistency** (`change == (cur-prev)/prev`, tolerance 0.25 pp):
   **2,319/2,329 = 99.57%**, against **554/2,403 = 23.0%** before.
4. **The recovered prev-month values were checked against the page**: 2024_W11
   bulker = 57.6 / 34.5 / 32.1 / 27.0, which are exactly the numbers printed on that
   page, and they reproduce the printed +/-% (61.0/57.6 = +5.9%).
5. **Control**: the 6 other intermodal series CSVs the same function writes are
   byte-identical (sha256) before and after, so the change is surgical.

| measure | before | after |
|---|---|---|
| rows | 2,409 | **2,333** |
| exact duplicate rows | 75 | **0** |
| rows where `change` != (cur-prev)/prev | 554 (23.0%) | **10 (0.43%)** |
| empty prev-month values | 0 (they were WRONG, not empty) | **0** (14 recovered from the page) |
| prices equal to a vessel size | 537 | **0** |
| published `$0m` prices | 4 | **0** (NULL) |
| distinct vessel_class keys | 15 (4 naming variants per entity) | **10** (+2 for 4 rows, see below) |

## What is NOT fixed, and why

- **The remaining 10 inconsistent rows are not defects.** They differ by 0.26-0.31 pp
  because the publisher computes `+/-%` on unrounded values and prints one decimal
  (e.g. 24.5/23.8 prints 3.2%, exact 2.94%). Listed in full in the run log.
- **4 rows still carry a size-less key** (`LR1`, `MR`; 2022_W26 and 2022_W51). The
  source markdown for those two rows has NO size cell at all (verified by reading the
  raw HTML `<tr>`: `['', 'LR1', '39.5', '37.4', '5.7%', ...]`). The values are right;
  only the label is short. Left as-is rather than guessed from position.
- `intermodal_baltic_tc_series.csv` (20,348 rows) is untouched - already judged
  superseded/held data in `docs/intermodal_baltic_series_verdict.md`.
- **No re-extraction**: the LlamaParse markdown is the same one the previous run used.
  If a document's cached markdown were re-fetched, shapes could differ again - the
  content-anchored parser is written to survive that, but it has only been measured on
  the 252 cached documents in this tree.

## Reproduce

```
python3 scripts/extract/publishers/run_intermodal_full.py --year all --reparse-only --workers 4
python3 scripts/extract/publishers/run_intermodal_full.py --stack-only
```
(Python 3.12 - the Hermes venv python3 cannot import `llama_parse`.)
