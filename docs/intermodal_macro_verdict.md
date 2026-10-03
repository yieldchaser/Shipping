# intermodal_macro_series.csv - verdict: ledger 4.3 was a REAL extraction defect (FIXED)

**Date:** 2026-09-28  ·  **Source:** `corpus/01-brokers/intermodal` (252 PDFs, 2021-2026)
**File:** `data/extracted/series/intermodal_macro_series.csv`  ·  **Runner:**
`scripts/extract/publishers/run_intermodal_finance.py`

## The ledger claim, and what was actually wrong

Ledger 4.3 said: "1,290 of 3,739 rows whose stated change is not reproducible from
`latest_value`/`prior_value`, blank on 2,075." Re-measured on the live file: **1,379**
non-reproducible, **2,075 blank**. The count was stale; the blank column was real and the
diagnosis behind it was wrong.

**The real defect: EVERY positive change was silently dropped.** Measured before the fix:
2,075 of 3,739 rows had a blank `wow_change_pct`, and of the 1,664 that survived **0 were
positive** - the publisher prints a change on essentially every row.

Root cause is the regex in `parse_finance_page`:

```python
pattern = re.escape(ind) + r"[\s\n]+([0-9.,]+)[\s\n]+([0-9.,]+)?(?:[\s\n]+[0-9.,]+)*(?:[\s\n]+([-+]?[0-9.]+%))?"
```

Two compounding faults:
1. the greedy middle group `(?:[\s\n]+[0-9.,]+)*` **swallows a bare positive number**
   (`1.7%` -> the `1.7` is eaten as a value cell, leaving `%` with no preceding `\s`), so the
   trailing `%` group never matches;
2. a negative change cannot be eaten that way because `[0-9.,]+` cannot start with `-`.
   Net effect: **only sign-prefixed (negative) changes survived.**

A second, independent fault: a value cell can be **TEXT** - the publisher writes
`mrkt closed` (23x), `market closed` (3x) and once `mrkt close` on holidays - which stopped a
number-only scan mid-row and lost that row's change too.

## Fix

The macro block is now a **content-anchored row parse** over the finance page's text lines:
anchor on the indicator label plus the requirement that the *next* cell is a value (number or a
known non-numeric marker), then read cells forward until a `%` cell is found, skipping text
value cells. No row order, no geometry, no sign requirement. Doubled periods (`2..756`) are
normalised. `NONNUM` was derived from the corpus (4 distinct break tokens measured across 252
documents), not guessed.

## Measured before / after

| metric | before | after |
|---|---|---|
| rows | 3,739 | **3,739** (unchanged) |
| `wow_change_pct` blank | 2,075 | **0** |
| positive changes | 0 | **2,061** |
| `latest_value` changed | - | **0** |
| `prior_value` changed | - | **6** (all `''` -> a value printed on the page) |
| change strings verbatim in the source page text | 1,664 / 3,739 | **3,739 / 3,739** |

## Verification

1. **Verbatim recall.** Every captured `wow_change_pct` string is present literally in the
   source PDF's own finance-page text layer: **3,739 / 3,739**, 0 not found.
2. **Control (same-document).** 125 of 126 series CSVs are byte-identical (md5) before/after;
   only `intermodal_macro_series.csv` differs. `intermodal_maritime_stocks_series.csv` and
   `intermodal_bunkers_series.csv` are byte-identical, proving the other branches of
   `parse_finance_page` were untouched.
3. **Key set.** The 60/136 `(issue_date, indicator)` key differences vs a pre-run snapshot are
   entirely the earlier **4.4** date fix (e.g. `2021-10-07` -> `2023-02-28`), not this change.
4. **Rows previously blank, read on the page:**
   `intermodal_2024_W21` S&P 500 -> `-0.5%`, Nasdaq -> `-11.0%`;
   `intermodal_2024_W29` Nikkei -> `-2.7%`. All match the rendered text.
   The 6 recovered `prior_value`s also check out - e.g. `2024_W27` Nasdaq row is
   `20,391.97 / mrkt closed / 20,186.63 / ...`, so the 2nd cell is text and the real prior is
   the 3rd. The old code returned `''`; the new code returns `20,186.63`.

## The semantics behind "not reproducible" (NOT an extraction defect)

The column is headed **"W-O-W Change %"** - a WEEK-over-week change. The CSV's `prior_value`
is the **previous DAY** (the table's 2nd daily column). They were never supposed to reconcile.

Independent cross-document control: the printed change vs the **previous report's own
`latest_value`** (the prior week's Friday close), on 6-8 day gaps only:

| | agreement |
|---|---|
| TOTAL | **3,160 / 3,447 = 91.7%** |
| S&P 500 99.6 · FTSE 100 99.6 · CAC40 99.6 · Won/$ 100.0 · Yuan/$ 97.4 · Nasdaq 97.8 · FTSE All-Share 97.8 · 10y Bond 97.0 · Dow 96.3 · Brent 95.5 · DJ US Maritime 94.8 · WTI 94.6 · Hang Seng 92.2 | |
| **Nikkei 52.2%** · **Xetra Dax 57.3%** | |

Three reference hypotheses were tested (previous report's col1 / same-row col1-vs-col5 /
previous report's col5). H1 fits 12 of 16 indicators at 95-100%; **Nikkei and Xetra Dax fit no
hypothesis** (their best is ~59%). Their extracted values and changes are verbatim on the page
(checked: `2021_W27` Nikkei `27,940.42 ... -2.3%`), so this is a **publisher-side
inconsistency** in those two markets' change column, not an extraction error. Left as printed.

## Deliverable

The `.md` / `.tables.json` tier is the primary deliverable and now carries the complete macro
row (sidecar `macro_indicators` re-written for all 252 documents). No value was rewritten: the
fix only **recovers** printed values that were being dropped.


---

## ADDENDUM 2026-10-03 - currency-block recall gap RECOVERED (+1,016 rows) + a silent no-op path fixed

**Re-measured on the live file, in a fresh session.** Ledger 4.3 is closed and the semantics
section above is confirmed correct by rendering the page: the finance page's macro table prints
**five consecutive daily columns** (`2-Jul-21 | 1-Jul-21 | 30-Jun-21 | 29-Jun-21 | 28-Jun-21`)
plus a printed **W-O-W Change %** column. The CSV's `prior_value` is therefore the **previous
DAY**, and `wow_change_pct` is the **week-over-week** change - they were never supposed to
reconcile. Confirmed verbatim on two years: `2021_W26` 10y Bond `1.431 / 1.480 / -6.8%` and
`2026_W26` `4.372 / 4.392 / -1.8%`, both exactly as printed. **Not a defect.**

### The defect that WAS real: 4 of the 7 published currencies were silently dropped

The finance page prints a **7-row currency block**: `€ / $`, `£ / $`, `$ / ¥`, `$ / NoK`,
`Yuan / $`, `Won / $`, `$ INDEX`. The runner's hardcoded `INDICATORS` allowlist listed only the
three ASCII-named ones (`Yuan / $`, `Won / $`, `$ INDEX`), so **`€ / $`, `£ / $`, `$ / ¥`,
`$ / NoK` were dropped on every issue** - with no comment and no mention in this verdict.

Checked against the "already held?" doctrine before fixing:
- `intermodal_currencies_series.csv` (a separate writer, `run_intermodal_full.py`) holds a
  **different** table - `USD/BDT`, `USD/INR`, `USD/PKR`, `USD/TRY` - not these four.
- `index.html` does not consume `intermodal_macro_series.csv` at all.
So the four were genuinely missing (not a restatement of held data).

**Fix:** added the four labels to `INDICATORS`, anchored on the exact bytes the PDF text layer
emits (`'€ / $'`, `'£ / $'`, `'$ / ¥'`, `'$ / NoK'`). Re-ran
`run_intermodal_finance.py` (255 reports, no API spend).

| metric | before | after |
|---|---|---|
| macro rows | 3,787 | **4,803** (+1,016 = 4 x 254) |
| distinct indicators | 16 | **20** |
| duplicate keys (`issue_date`,`indicator`) | 0 | **0** |

**Verification (content, not count):** for every one of the **1,016** new rows the source PDF
page was re-read and the label line was confirmed to be followed by exactly the two values and
the printed change the CSV carries - **1,016 / 1,016 = 100.0% verbatim**, 0 mismatches (a first
pass showed 90 "mismatches" that were pure float-format artefacts, `1.40` vs `1.4`; comparing
numerically cleared them).

**Control (same-document):** `intermodal_maritime_stocks_series.csv` and
`intermodal_bunkers_series.csv` are **byte-identical** (md5 unchanged), proving the stocks and
bunkers branches of `parse_finance_page` were untouched. No other indicator count moved.

### Second finding: the sidecar enrichment was a silent no-op (verdict claim was false)

This verdict's "Deliverable" section claimed the sidecar `macro_indicators` was "re-written for
all 252 documents". **Measured: 0 of 256 sidecars contained the key.** Cause: the runner wrote
its sidecar to `data/extracted/md/intermodal/<stem>.tables.json` (FLAT), but `run_intermodal_full.py`
writes them **year-partitioned** (`.../md/intermodal/<year>/<stem>.tables.json`), so
`sidecar_path.exists()` was False for every document and the block never ran.

**Fix:** the runner now writes to the year-partitioned path (mirroring `run_intermodal_full.py`).
Verified: **255 sidecars now carry `macro_indicators`** (was 0), e.g. `2021_W26` carries 18
macro rows including `€ / $ 1.19 / 1.18 / -0.6%` and `$ / NoK 0.12 / 0.12 / -1.5%`, both exactly
as printed. The series CSVs are byte-identical across this change (md5 `e64c2c05...`).

**Disclosed residual (not fixed):** `run_intermodal_full.py` rebuilds its sidecar as a *fresh*
dict (no merge), so the next `run_intermodal_full.py` pass would CLOBBER `macro_indicators` again.
No script reads the key (checked: only `run_intermodal_finance.py` writes it), so this is
write-only enrichment; fixing it durably needs a merge in `run_intermodal_full.py`.
