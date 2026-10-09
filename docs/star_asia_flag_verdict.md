# star_asia deals: delivered series did not carry its own impossible-date flags

**Run 2026-10-09 (source-by-source, 30m cron job). Branch `auto/extract-fixes-2026-10-08`.**
No new corpus arrivals (`git status corpus` = 0 changes; newest broker content 2026-10-06).
No extraction job in flight. All broker sources CLOSED. xclusiv 271/271 DONE
(`docs/xclusiv_verdict.md`). Register gate green before and after.

## Defect (measured)

`scripts/extract/publishers/star_asia_dates.py` was committed with
`3a6123eb4` ("flag impossible star_asia deal dates (23 future-vs-issue, 44
beaching-before-arrival) instead of leaving them clean"). That commit changed the
**code** but never regenerated the **delivered** series. The committed
`data/extracted/series/star_asia_deals_series.csv` therefore carried NONE of the
quarantine flags its own committed code produces.

Measured on the delivered CSV (3,354 rows):
- `arrival_date_note` values: EU_DDMMYYYY 2,696; UNPARSED 41; RECONSTRUCTED_8DIGIT 8; EMPTY_DASH 6; STATUS 1; blank 602.
- `beaching_date_note` values: EU_DDMMYYYY 1,739; STATUS 980; UNPARSED 24; RECONSTRUCTED_8DIGIT 6; blank 605.
- **`|FUTURE_VS_ISSUE` = 0, `|ORDER_INVALID` = 0.** 48 rows should carry a flag.

Re-feeding each row's page-raw strings (`*_raw`) through the committed module
reproduces the delivered ISO primary column **exactly (0 mismatches)** -- the
control that the module is the same producer, and that only the `*_note` column
went stale.

## Fix

Re-derived only the two `*_note` columns from the page-raw columns. Tool:
`scripts/extract/apply_star_asia_deals_dates.py` (rewritten, see below).

| measured | before | after |
|---|---|---|
| rows | 3,354 | **3,354** (unchanged) |
| rows with a changed cell | - | **48** |
| non-note cells changed | - | **0** |
| `FUTURE_VS_ISSUE` cells | 0 | **23** |
| `ORDER_INVALID` cells | 0 | **88** (= 44 rows x 2 cells) |
| ISO primary-date mismatches (control) | - | **0** |
| status mismatches (control) | - | **0** |

Notes now present: `EU_DDMMYYYY|ORDER_INVALID` 69,
`EU_DDMMYYYY|FUTURE_VS_ISSUE|ORDER_INVALID` 19, `EU_DDMMYYYY|FUTURE_VS_ISSUE` 4
(= 92 changed cells across 48 rows). `git diff --numstat` = **48 / 48**, 0
added, 0 removed. LF EOL and no BOM preserved. Second run = *"idempotent:
nothing stale, no write"*.

## Landmine caught (the rewrite)

The original `apply_star_asia_deals_dates.py` fed the PRIMARY (already-ISO) column
back into the normaliser, so on the delivered CSV every cell re-parsed as
`UNPARSED`: running it with `--apply` would have **blanked all 4,449 ISO dates**.
It also wrote a hardcoded 20-column `FIELDS` list (silently dropping `built`,
`country_destination`, `buyer_comments`, `terms`) and CRLF line endings. It is
now schema-preserving (reads the CSV's own header), `*_raw`-aware, LF, and
idempotent. Verified: the rewritten tool reproduces the surgical fix
**byte-identically** (sha256 `3cd2288f613b...`) and reports idempotent on the
fixed file.

## Notes

- The flags do not change any VALUE -- the ISO dates and statuses are unchanged
  and were already correct. They add the downstream-exclusion signal the code
  intends (beaching-before-arrival / arrival >30d after issue are the
  PUBLISHER's own year typos, verified page-faithful across eras by the module).
- Not app-displayed: `index.html` has 0 `star_asia` references.
- The three FUTURE-dated cells in the whole corpus (after this run) remain the
  same page-faithful publisher typo: FT ISLAND `arrival_date 2027-07-31` in
  star_asia 2026 W31/W33/W34 (the PDF text layer prints `31.07.2027`); they are
  now correctly flagged `|FUTURE_VS_ISSUE` rather than silently clean.
