# Star Asia demolition deals: `arrival_date` / `beaching_date` normalised

**Verdict: the ledger defect is REAL but the extractor was FAITHFUL.** The two columns held the
publisher's own European `DD.MM.YYYY` strings and free-text STATUS words, so an ISO date join
dropped every value. Nothing was wrong with the parse: the strings appear **verbatim** in the
source PDF text layer. Fixed 2026-09-28 by reformatting only - no value was guessed.

Ledger item: `docs/series_verification_ledger.md` 4.5 (and entry 5 of section 4).
Source: `data/extracted/series/star_asia_deals_series.csv` - 3,327 rows, 192 source PDFs.

## What was wrong (measured before the fix)

| column | non-empty cells | European `DD.MM.YYYY` | STATUS words | malformed year | `-` |
|---|---|---|---|---|---|
| `arrival_date` | 2,727 | 2,681 (2,673 four-digit-year + 8 recoverable) | 1 | 39 | 6 |
| `beaching_date` | 2,725 | 1,736 (1,730 + 6 recoverable) | 965 | 24 | 0 |

* The 966 STATUS cells in full: `AWAITING` 901, `ARRESTED` 24, `AWATIING` 17,
  `AWAITING*` 14, `AWAIITNG` 3, `AWATING` 2, `AWAITNG` 1, `AWAITING` 2, `BEACHED` 1,
  `ÀWAITING` 1 - the typos are the publisher's own. All but one `NIL` sit in
  `beaching_date`.
* Ambiguity resolved by measurement, not assumption: of the 2,680 European arrival values the
  **first component exceeds 12 in 1,546 cases and the second component never does**, so the
  order is unambiguously `DD.MM.YYYY`.

## Why this is not an extraction defect

1. `star_asia_2022_W29_Market-report-Week-29.pdf` page 11-12 prints exactly `03.07.2022` and
   `12.07.2022`, the values stored for PISC. Same for 3 further documents read at span level.
2. Every one of the **77** non-canonical non-status values was located **verbatim (77/77)** in
   its own source PDF's text layer.
3. For the **63** values that cannot be a real date, a same-page control was run: its
   per-character glyph advance is 0.928-1.053x (median 1.006) the advance of the clean dates
   printed on the same page in the same font. A dropped glyph would have made the span wider
   than its text. **No glyph is missing - the publisher's page really renders `05.02.206`.**

## The fix

`scripts/extract/publishers/star_asia_dates.py` (new, single-sourced) + one call in
`run_star_asia_tables.py` at the single `all_deals_series.extend(...)` choke point, so future
full runs produce the same result. Header widened by 6 audit columns
(`arrival_date_raw`, `arrival_date_status`, `arrival_date_note`, and the `beaching_` trio).

* `DD.MM.YYYY` / `DD-MM-YYYY` with a 4-digit year -> ISO `YYYY-MM-DD`.
* exactly 8 digits, punctuation-only separators -> read as DDMMYYYY, note
  `RECONSTRUCTED_8DIGIT` (recovers `14.102025` -> 2025-10-14, `11..02.2024` -> 2024-02-11,
  `31-03-2023` -> 2023-03-31).
* status words -> a canonical `*_status` token, out of the date column.
* anything else -> left **UNPARSED**, the printed value kept in `*_raw`. Never guessed.

## Result (after)

| column | non-empty | now ISO | STATUS | UNPARSED | `-` |
|---|---|---|---|---|---|
| `arrival_date` | 2,727 | **2,681** (2,673 EU + 8 reconstructed) | 1 (`NIL`) | 39 | 6 |
| `beaching_date` | 2,725 | **1,736** (1,730 EU + 6 reconstructed) | **965** | 24 | 0 |

**4,417 date cells are now ISO-joinable** (was 0), 966 cells are typed status, 63 remain
unparsed, 6 empty. Statuses: AWAITING 939, ARRESTED 24, NIL 2, BEACHED 1.

## Verification (independent script, not the fixer)

`scripts/extract/verify_star_asia_deals_dates.py` - **PASS, all checks green**:

* row count unchanged: 3,327 -> 3,327;
* **39,924 context cells** (12 non-date columns x 3,327 rows) byte-identical;
* 0 non-ISO primary date cells remain;
* 0 rows where `*_raw` differs from the previous primary value (proves reformat-only, and the
  `ÀWAITING` accent is preserved in `_raw`, folded only for classification).

## The 63 quarantined cells - a publisher-side defect worth knowing about

24 distinct corrupted values across 21 vessels, e.g. `05.02.206` x4, `07.04.2206` x6,
`04.09.3023` x4, `02.02.20323` x4, `26.07.203` x4, `29.02.2022` x2 (Feb 29 in a non-leap
year). Full list with row numbers, vessel and source file:
`data/extracted/audit/star_asia_deals_dates_quarantine.json`.

**Recovery was attempted and rejected on evidence**: these rows reprint week over week, so a
same-vessel well-formed date with the same day-and-month elsewhere in the series would
corroborate a value. Only **2 of 63** qualify, so recovering the rest would be guessing.
A wrong year is worse than a missing one - left as printed.
