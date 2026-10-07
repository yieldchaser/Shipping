# corpus/archive/other/ - sub-classified (read-only fingerprint)

Measured 2026-10-07 ~03:2x IST by the hourly supervisor cron (345bc8db9233).
Read-only: no extraction, no DB writes, no commits. Branch
`auto/extract-fixes-2026-10-06-deepreview`.

## Why this exists

`docs/archive_backfill_survey.md` classified `corpus/archive/other/` (130 PDFs) as
"heterogeneous grab-bag ... not one publisher" and set it **SKIP until
sub-classified**. This run performed that sub-classification (the skill's
"enumerate, never be told which" step). It is NOT one publisher - it is five.

## Method

Per PDF: page-0 letterhead = the largest-font text spans; publisher identity =
email/website/copyright tokens across ALL pages (`pymupdf` `get_text`). Grouped by
token, then verified by document shape. 130/130 classified, 0 read failures.

## Result - 130 PDFs = 5 publications

| publisher | files | years | shape | identity tokens |
|---|---:|---|---|---|
| **Seasure** - "S&P SUMMARY SALES" | **86** | 2021(24) 2022(49) 2023(13) | 3-page weekly; per-vessel S&P deal grid: Name / Type / DWT / Yard / Built / USD mill / **VV** / **Buyer** / **Seller** / Comments + Weekly Spend charts | `seasure@seasure.co.uk`, `www.seasure.co.uk`, `info@vesselsvalue.com` |
| **DNF Analysis** - "DRY BULK WEEKLY BRIEF" | **38** | 2021(24) 2022(14) | 4-page weekly commodities brief; iron-ore port inventory (source Tathya.Earth), bunker + demolition prices | `contact@dnfanalysis.com`, `www.dnfanalysis.com` |
| UP Oil Tankers & Trading Inc - "WEEKLY HEDGING REPORT FOR EMISSIONS, FREIGHTS & BUNKERING" | 2 | 2023 | 10-page | letterhead "PREPARED BY UP OIL TANKERS & TRADING INC" |
| Psarras (Piraeus) - "BI-MONTH REPORT" | 1 | 2018 | bi-monthly S&P report | `psarras@psarrasj.gr`, `www.psarrasj.gr` |
| hellenic - "WEEKLY SHIP RECYCLING REPORT" | 1 | 2021 | 7-page recycling weekly | "hekllenic" letterhead (belongs to the held hellenic family) |

Residual 2 PDFs (exact-grouping edge cases, both clearly Seasure/DNF family):
`other_2018_Week-28-2018.pdf` (the same "DWT BLT YARD PRICE ($MIL) ... BUYER
COMMENTS" grid) and `other_2022_W06` "WEEKLY OUTLOOK WEEK-6 2022 - By Research and
Analytics team". Treating them as Seasure-family gives **Seasure 87 / DNF 38+**.

## Correction to the standing recommendation

`archive/other` is NOT unclassifiable - it is **two real recurring publications
(Seasure 86-87 weekly, DNF Analysis 38 weekly) plus 4 stragglers**. This
supersedes the survey's "SKIP until sub-classified".

## Three-baseline test (is it already ours?)

| baseline | Seasure | DNF Analysis |
|---|---|---|
| live feeds / series CSVs (`data/extracted/series/`) | none | none |
| our own extraction (md tier) | 0/86 - no `data/extracted/md/*seasure*` | 0/38 - no `*dnf*` |
| app display (`index.html`) | absent | absent |
| live collection (`corpus/01-brokers`, `11-other`) | absent | absent |

=> **GENUINELY_MISSING** from all three, for both.

## Liveness gate

Newest content: Seasure **2023-03-31**, DNF **2022-12**. Both >180 d old ->
**BACKFILL_ONLY**, never CONSTRUCT. Value = historical depth only. The Seasure
series is the richer of the two (per-vessel rows carrying BOTH buyer and seller -
allied/golden_destiny carry buyer only).

## Recommendation (input to the user's go/no-go - nothing started)

1. **Seasure "S&P SUMMARY SALES" (86-87)** - one publisher, one weekly grid, one
   number convention to fingerprint; a per-vessel S&P deal series with buyer AND
   seller. Best value if the archive backfill is extended. Runner:
   `scripts/extract/publishers/run_seasure.py` (per-source; verify number
   convention per page - do NOT assume ISO).
2. **DNF Analysis "Dry Bulk Weekly Brief" (38)** - commodities/bunker/demolition
   weekly; the iron-ore port inventory row (Dampier/Qingdao/Saldanha/Tubarao
   W/W%) is a candidate series. Second source.
3. UP Oil (2) / Psarras (1) / hellenic recycling (1) - **SKIP** (single issues,
   no cadence, or already a held family).

Same gating as the parent survey: **BACKFILL_ONLY, user gates depth, nothing
started without go/no-go.**

## Reproduce (read-only)

```
python3 scratch/other_classify.py   # letterhead groups
python3 scratch/other_ident2.py     # publisher tokens across all pages
python3 scratch/other_final.py      # per-publisher counts + year spread
```
