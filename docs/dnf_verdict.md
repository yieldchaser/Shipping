# DNF Analysis - "Dry Bulk Weekly Brief" - VERDICT (measured)

Runner `scripts/extract/publishers/run_dnf.py` (per-source, NOT the deleted generic
runner). Branch `auto/extract-fixes-2026-10-06-deepreview`. Survey: `docs/dnf_survey.md`.

## Result

| measured | value |
|---|---|
| documents | **38/38**, 0 failed (subprocess-per-doc, `_run_state.json` resume) |
| markdown (PRIMARY) | `data/extracted/md/dnf/<year>/<stem>.md` - **38 files, 0 under 1 KB** |
| tables sidecar | 38 `.tables.json` |
| `dnf_secondhand_transactions_series.csv` | **521 rows**, 38 issue dates 2021-07-05 .. 2022-05-09 |
| `dnf_bunker_prices_series.csv` | **273 rows**, 32 issue dates (era B) |
| bulk wall time | 115-125 s for the 38 docs (+88 non-DNF PDFs scanned and skipped) |

## Verification (no vision tool in this cron session - stated)

There is no image/vision tool available to this session, so the skill's
"render a page and LOOK" is replaced by **two real checks**, not a metric:

1. **Verbatim token reconcile against each document's OWN text layer**, per page.
   Every extracted value must appear as a literal token on the page it came from:

   | field | verbatim-in-page |
   |---|---|
   | vessel_name | **521/521 = 100.00%** |
   | dwt | **517/517 = 100.00%** |
   | price_raw | **481/481 = 100.00%** |
   | built_year (4-digit only) | **6/6 = 100.00%** |
   | bunker price value | **273/273 = 100.00%** |

   `scratch/verify_dnf.py`. Mismatches at the final run: **0**.
   (The first runs of the same check found 9 and then 2 real defects - see below -
   which is why the check is run after every change.)

2. **Pixel-INK test on a rendered page.** `page.get_pixmap(clip=<the extracted
   value's search bbox>, dpi=150)` and count ink against the page's own
   background: W26 `177,066` = 696 dark px of 1,775; W18 `206,331` = 916 of 1,976.
   The value really is drawn where it was read.

## Trial-first: what the trial caught BEFORE the bulk run

The runner was trialled on 2022 W18, 2021 W46, W50, W35 and W26 (both eras) and
compared against the page's own text. Five real bugs, each found by the check:

1. the left-hand prose/news panel and the right-hand chart panels were being read
   as table cells -> the whole page's prose leaked into `vessel_name`. Fixed by
   bounding each row to the table's own horizontal extent (from its Week column).
2. the `WEEK` column integers ("18", "17", "16") were being read as column values
   -> fixed by deriving column boundaries from the header row so the Week column
   claims them.
3. a table's **second header line** (`Price (US$)`, `of Buyer`) sat 13 pt under the
   first and bled into row 1 of era A -> first band starts at `header_y + 15`.
4. multi-word names with a trailing number were shredded across columns
   (`ZHONG XING DA 98` -> name `ZHONG XING`, dwt `98`). Fixed by clustering each
   row's tokens on x-gaps and labelling the cluster by the nearest header anchor
   instead of a fixed x-cut. (The first version of that fix compared the gap
   against the cluster's FIRST word instead of its LAST - caught by the same
   trial, and it was the defect that lost the final word of
   `SHANDONG HAI DA` and `ZHONG XING DA 98`.)
5. multi-line / right-aligned name cells joined in the wrong order
   (`NAVIOS MARCO POLO` read as `NAVIOS POLO MARCO`) -> cells are joined in
   READING order (y, then x), not x order.

Also handled: Power BI private-use icon glyphs (`U+E0xx`) dropped from cells; the
page's own `en bloc` rows keep the literal `EN BLOC` in `price_raw` with a NULL
`price_m` rather than a fabricated number.

## Faithful, NOT defects (verified against the page)

* 2021 W33-W50 print a **`£` glyph** where `$` is meant (`£19.9M`). The publisher's
  own print - preserved verbatim in `price_currency`, not rewritten.
* `UNION ERWIN` built year prints **`4022`** - the publisher's own typo, preserved
  as the raw string (not coerced to a year).
* `SILVIA GLORY` (W50) prints **no price** - left blank, not fused from a neighbour.
* the five `ORIENT *` rows (W46) print **`EN BLOC`** in the price cell - a lot sale
  with no per-vessel price; `price_m` is NULL.

## Disclosed residue (named, not hidden)

* **bunker series is 273 of an expected 288 rows.** 5 documents emit 2 of the 3
  weekly rows: `W33, W34, W35, W39, W40 (2021)`. Every emitted value is verbatim
  (273/273). The missed row is the bunker panel's oldest week, whose geometry moves
  with the Power BI panel layout on those weeks. No value is wrong - one weekly row
  per those 5 documents is missing. Fix = an era-B-early geometry pass; not worth a
  risky auto-bind in this pass.
* era A also carries a demolition table and a newbuilding-orders table (present in
  the `.md`); they are not typed (see survey section 5).
* the commodity price charts are in the `.md` as text but are not turned into series.

## Register

`docs/EXTRACTION_REGISTER.md` + `data/extracted/EXTRACTION_REGISTER.json` synced:
178 -> **180 CSVs**, 640,383 -> **641,177** rows. `scripts/extract/verify_registers.py`
= **ALL VERIFICATION CHECKS PASSED PERFECTLY (100.0% MATCH)**.

**Verdict: CONSTRUCTED (BACKFILL_ONLY).** The .md is the primary deliverable and is
complete for all 38 documents; the typed secondhand-transactions layer is exact
against the pages (100% verbatim on every field).
