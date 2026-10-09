# star_asia_deals LDT: the period-thousands 1000x defect (FIXED 2026-10-09 cron)

Same defect class as `docs/carriers_dwt_convention_verdict.md`, fixed in its OWN
per-source pass. Rule obeyed: ONE SOURCE at a time.

## The defect (page-verified)

`star_asia_deals_series.csv :: ldt` is an integer count, but a FEW rows print the
European period-thousands form (`3.905`) where the rest of the SAME page prints the
ISO comma form (`7,290`, `2,075`). The builder's `parse_clean_num()` strips only the
comma, so `3.905` was stored as **3.905 LDT** (a silent 1000x error).

Ground truth (rendered text of the SAME document):
* page 13 of `star_asia_2023_W21_...Week-21.pdf`: `KAI HANG 3 / CONTAINER / 3.905`
  beside `XIANG JIANG 6 ... 7,290` and `WINWIN ... 2,075`.
* page 14 of `star_asia_2024_W42_...Week-42.pdf`: `HAI BO / BARGE / 8.678` beside
  `BEREG MATCHY ... 7,263`, `ANDULUS 1 ... 6,064`.

## The fix (surgical on the delivered series)

12 cells corrected (ldt only, values only):

| vessel | occurrences | 3.905-style -> fixed | weeks |
|---|---|---|---|
| KAI HANG 3 | 3 | 3.905 -> 3905 | 2023 W21/W22/W25 |
| HAI BO | 2 | 8.678 -> 8678 | 2024 W42/W43 |
| HARMONY 1 | 2 | 10.317 -> 10317 | 2024 W42/W43 |
| NING HUA | 2 | 9.713 -> 9713 | 2024 W47/W48 |
| KHOZAN MARU | 3 | 9.962 -> 9962 | 2026 W03/W04/W05 |

## Verification

* **Control 12/12:** every corrected cell's raw period-thousands token is present
  verbatim in its OWN source PDF's text layer.
* `git diff --numstat` = `12/12`; line-by-line diff: **exactly 12 lines changed, each
  ONLY in the `ldt` column**; LF + quoted-field layout byte-preserved (+12 bytes).
* Register gate: **ALL PASSED**, 180 CSVs / **639,749** logical rows == JSON == MD
  (row counts unmoved).
* Faithful decimals NOT touched: 69 further non-integer `ldt` cells are the
  publisher's OWN decimals (`7,553.35`, `22,142.80`, `2,181.45`) - verified on the
  page, NOT a defect.

## LANDMINE (worth telling the user - do NOT regen star_asia from repo code)

The delivered `star_asia_deals_series.csv` is a **24-column** file
(`... built, country_destination, buyer_comments, terms`), but the repo's builder
`scripts/extract/publishers/run_star_asia_tables.py` writes only **20 columns**
(its `deals_headers` ends at `beaching_date_note`). No script in the repo constructs
the 24-col header. Regenerating the tier from repo code therefore LOSES those 4
columns AND produced a materially DIFFERENT `star_asia_demolition_series.csv`
(2,007 cells differ: issue_date/report_week/price/source_file) against the delivered
file. **The current producer of the delivered star_asia CSVs is NOT in the repo.**

For this reason the fix above is surgical on the delivered series and the repo runner
was deliberately left UNPATCHED (patching code that does not produce the delivered
file cannot be verified). If/ when the real producer is restored, its ldt parser
needs the same shape rule (pure `\d{1,3}\.\d{3}` -> strip the period; everything else,
including faithful decimals, unchanged).
