# Agora misfiled-issue dates - one FIXED, two NAMED (measured 2026-10-08)

Per-source (agora only), content-anchored audit: for every one of the 214 distinct
`source_file` values in `data/extracted/series/agora_indicators_series.csv`, re-derive the
issue date from the document's own cover ("Week N / YYYY" -> Friday of that ISO week, the
convention the shipped series already follows: 212/213 historical dates are Fridays and
`report_week` == ISO week on 213/213) and compare against the series.

**Result: 210 / 214 documents consistent. 3 mismatches + 1 internally-inconsistent cover.**
Audit script: `scripts/extract/publishers/audit_agora_dates.py` (reuses `stack_agora_weeks.py`'s `cover_meta`).

## FIXED - the 2021 Week-52 issue was dated a full YEAR late (38 rows)

`corpus/01-brokers/agora/2022/agora_2022_W52_AGORA.-Week-52.-2021.-Snapshot-of-Commercial-Indicators.pdf`
is the publisher's **Week 52 / 2021** report, collected under a `2022_W52` filename; the
original stacker dated it from the filename -> **2022-12-30** on 38 rows.

Three independent signals agree it is the 2021 report:

| signal | evidence |
|---|---|
| cover line | "Week 52 / 2021" / "(27-31 December)" |
| **content** | Rotterdam bunkers IFO380/VLSFO/MGO = **447/571/682** - Dec-2021 levels, one week on from 2021-12-24's 432/549/656; nothing like the 2022 W52 doc's 400/559/886 (Dec-2022 levels) |
| series shape | 2021 steps W44..W51 (last 2021-12-24) then jumps to 2022-01-07 - W52/2021 is the single missing week; 2021-12-31 held 0 rows |

Fix = `scripts/extract/publishers/fix_agora_w52_2021.py` (per-source, idempotent,
cover-asserted): sets those 38 rows to **2021-12-31** (Friday of ISO wk52 2021), `report_week`
stays 52.

Measured control (before -> after, `scratch/agora_before.csv` snapshot):
* rows **10,049 -> 10,049** (unchanged; register gate still 180 CSVs / 639,749 == JSON == MD, 0 mismatches);
* **exactly 38** lines changed; every change confined to the leading `issue_date` column
  (all bytes after the first comma identical on all 38 lines); `report_week` column unchanged;
* EOL CRLF (10,050) and no-BOM preserved; second run = *"idempotent: nothing stale, no write"*.

## NAMED, NOT CHANGED (a wrong value is worse than a missing one)

**2. `agora_2023_W24_...Week-24-2023...pdf` - the cover is stale; the series is RIGHT.** The
cover prints "Week 23 / 2023 (Reference point 08th June.2023)" - identical cover text to the
real week-23 file - yet its 47 extracted rows differ from the W23 file on **116 of 126**
comparable value cells (not a restatement; a different week). So the "Week 23" cover is a
publisher copy-paste and the series date (2023-06-16 / wk24) is correct. Re-dating it to the
cover (2023-06-09) would have DUPLICATED week 23 and emptied week 24. Left as-is.

**3. `agora_2025_W38_...Week-42-2025...pdf` - ambiguous, left as-is.** Filename W38, series
date 2025-09-19 / wk38; cover prints "Week 42 / 2025 (Reference point 16 October.2025)".
Unlike case 2 there is no second document to arbitrate, and a content check is inconclusive
(Rotterdam bunkers 403/428/650 sit between neither cleanly - 2025-09-12 is 390/459/685,
2025-10-24 is 418/434/663). `issue_date` stays 2025-09-19 and wk42 (2025-10-17) stays empty;
needs its own measured fix.

**4. `agora_2026_W33_...` - cover internally inconsistent, cannot be dated.** Cover prints
"Week 33 / 2026" but its reference point 20 August 2026 is ISO week 34. `cover_meta` returns
no date, so the series keeps the W33-derived 2026-08-14. Left as-is.

## Also observed (upstream collection, not extraction)

`baltic_ncfi_series.csv` stops at **2026-09-25**. NCFI is built from
`corpus/08-baltic/ningbo/*.html` (weekly Fridays); the newest collected ningbo page is
**2026-09-25**, so the series is current with the corpus. The 2026-10-02 (Fri) page is not
collected (plausibly the Chinese National Day week, Oct 1-7). Collection lag, not an
extraction gap.

## Not a defect (re-measured today, both already closed)

* `2026-00-00` fake dates: **0** rows corpus-wide (the 2026-09-28 ledger finding is fixed).
* `star_asia_deals_series.csv` "European dates": the ISO `arrival_date`/`beaching_date`
  columns are clean; the `*_raw` columns intentionally hold the source `DD.MM.YYYY` with an
  explicit `*_status` = EU_DDMMYYYY. By design, not a defect.
* `intermodal_macro_series.csv` "change not reproducible": `latest_value`==printed col1 and
  `prior_value`==printed col2 on **223/223** rows (25 random docs, 9 indicators); the printed
  change is the publisher's own **week-over-week** metric against a value ~5 trading days back,
  usually outside the printed 5-column window. Faithful; DO NOT rewrite.
