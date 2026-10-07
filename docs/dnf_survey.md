# DNF Analysis - "Dry Bulk Weekly Brief" (corpus/archive/other) - SOURCE SURVEY

Measured 2026-10-07 by the 30-minute source-by-source cron job.
Runner: `scripts/extract/publishers/run_dnf.py` (per-source). Read-only survey; no
bulk run at survey time.

## 1. Count + fingerprint (measured)

**38 documents**, 2021 W26 - 2022 W18. Enumerated by CONTENT token
(`dnfanalysis` anywhere in the document text), not by filename - the filenames
(`other_<year>_...`) carry no publisher. `corpus/archive/other` holds 130 PDFs in
5 publications; DNF is 38 of them (per `docs/archive_other_survey.md`).

**TWO LAYOUT ERAS - the geometry is NOT stable, and the column ORDER flips:**

| era | docs | pages/doc | masthead | S&P table header order |
|---|---|---|---|---|
| A | 6 (2021 W26-W32) | 7 | `DRY BULK WEEKLY` | Week \| Ships Sold \| **Built** \| **DWT** \| Reported Price (US$) \| Country/Region of Buyer \| Owner \| Notes |
| B | 32 (2021 W33 - 2022 W18) | 4 | `DRY BULK WEEKLY BRIEF` | WEEK \| Vessel Name \| **DWT** \| **Built** \| Reported Price |

The **Built and DWT columns swap order between the eras** (measured data rows:
era A built x~201 / dwt x~235; era B dwt x~436-499 / built x~474-546). A fixed
x-cut would silently swap the year into the tonnage on one era. Every threshold
in the runner is derived from the page's own header row instead.

Era B's masthead is also a Power BI dashboard whose text layer is column-major and
whose panels overlap in x - the chart axis values sit in the same x range as the
table columns, so a page is parsed **panel-by-panel, bounded by the table's own
header row and its Week column**, not by a whole-page geometry.

- Text layer: fully digital, no OCR needed. Era B docs are `Power BI Desktop`
  exports (a `SegoeUI 9.0` producer stamp on every page).
- Numbers: **ISO** ("206,331" = 206331, "26.5" = 26.5). Verified against the
  rendered values.
- Currency: **the page's own token**. Era A prints `$26,500,000`; era B prints
  `$26.5M`; and 2021 W33-W50 print a stray `£19.9M` glyph where `$` is meant -
  that is the PUBLISHER's own print, so it is preserved verbatim in
  `price_currency`, never silently rewritten to `$`.
- Chart values: era B prints chart values as positioned TEXT (Iron Ore / Coal /
  Soybeans), so they need no vision - but they are not extracted here (see 4).

## 2. Recurring tables (all 38 docs)

| table | docs | shape |
|---|---|---|
| Latest Transactions / Latest Secondhand Transactions | **38/38** | per-vessel sale: name, DWT, built, printed price (+ buyer country and owner in era A) |
| Demolition Prices for Bulkcarriers ($/LDT) | 38/38 | 3-4 breaker countries + WoW% (layout differs per era) |
| Latest Orders / Newbuilding Market Price | 6/38 | era A only |
| Average bunker Prices ($/t) | 32/38 (era B) | VLSFO / MGO / IFO380 x last 3 weeks |
| Changes in Iron Ore Port Inventory Index | part of era B | 5 ports W/W% (Dampier, Qingdao-Dongjiakou, Qingdao-Qianwan, Saldanha, Tubarao) |

## 3. Three-baseline test - is it already ours?

* live feeds / `data/extracted/series/` - **absent**
* our own extraction (`data/extracted/md/dnf*`) - **absent before this run**
* app display (`index.html`) - **absent**
* live collection (`corpus/01-brokers`, `11-other`) - **absent**

=> **GENUINELY_MISSING**. It is also the only unextracted DNF-family body: the
`other_2022_W06_Week-6-2022.pdf` and `other_2021_Week-28-2018.pdf` edge cases named
in the parent survey are Seasure/other family, not DNF.

## 4. Liveness gate

Newest content **2022-05-09** (>500 days) => **BACKFILL_ONLY**, never CONSTRUCT.
Value = historical depth (a weekly per-vessel S&P deal series with a printed
price, plus 3-grade weekly bunkers).

## 5. Deliberately NOT typed (in the .md only)

* the three commodity price charts (Iron Ore / Coal / Soybeans) - positioned text,
  but "Price This Month / Last 30 days" with a mixed month/day axis that changes
  wording per week; the axis semantics would have to be read per document and the
  series is restated public index data
* the W33+ demolition table (column set changes: `PLVw/LVw/CVw/WoW%w` in 2021 vs
  `DPCV/DPW%` in 2022) - the .md carries it; a typed version needs its own era
  handling and was not worth the risk in this pass
