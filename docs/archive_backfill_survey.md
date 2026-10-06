# Archive backfill survey (corpus/archive/) - read-only fingerprint

Measured 2026-10-06 ~21:0x IST, source-by-source 30m cron run. Branch
`auto/extract-fixes-2026-10-06-deepreview`. NO extraction performed - this is the
input for the user's go/no-go on the archive backfill.

## 0. CORRECTION to the standing count: 615 unextracted, not 724

`corpus/archive/` holds 724 PDFs across 5 sources. Matching every archive PDF
stem against all 28,320 md stems under `data/extracted/md/` (year-partitioned):

| archive source | PDFs | exact-stem md exists | unmatched |
|---|---:|---:|---:|
| golden_destiny | 252 | 0 | **252** |
| allied | 203 | 0 | **203** |
| gibson | 109 | **109** | 0 |
| anchor | 30 | 0 | **30** |
| other | 130 | 0 | **130** |
| **TOTAL** | 724 | 109 | **615** |

**gibson is already extracted** (109/109). `data/extracted/md/gibson/` holds 265 md
spanning 2021-2026; the archive/gibson PDFs are the 2021-2023 slice of a source
that is LIVE (its md runs to 2026, fed from `corpus/01-brokers/gibson/html/`).
gibson is therefore neither archive-only nor a gap. Recount the remaining body as
**615 PDFs**.

## 1. Per-source fingerprint (pymupdf, sampled across ALL year dirs, seeded)

| source | PDFs | years (n) | pages/doc | chars/pg | imgs/doc | vector draws/doc | numeric tokens/doc |
|---|---:|---|---:|---:|---:|---:|---:|
| golden_destiny | 252 | 2021(49) 2022(100) 2023(57) 2024(46) | 4-9 (main), 1 (Special Ed) | 1700-2050 | 14-20 | 1000 (main) / 260 (1-pg) | 800-990 |
| allied | 203 | 2021(50) 2022(97) 2023(49) 2024(7) | 9 (SnP Stats), 12-14 (Review) | 2500-3600 | 24-160 | 1650-6600 | 1350-2240 |
| anchor | 30 | 2021(26) 2022(4) | 3-4 | 950-1490 | 3-4 | 78-736 | 84-308 |
| other | 130 | 2018(2) 2021(49) 2022(64) 2023(15) | 3-4 | 550-4200 | 3-10 | 67-809 | 80-660 |

## 2. Document classes and number convention (PER SOURCE, measured)

**golden_destiny** - "Weekly S&P Market Report" (Sale & Purchase). Two classes:
- `Weekly-SP-Market-Report` (multi-page 4-9): rich prose + VECTOR charts (~1000 drawings/page) + S&P deal tables. The S&P weekly deal grid is the deliverable shape (same as the existing `<source>_sales_series.csv` family).
- `Special-Edition-Weekly-SP-Market-Trends` (**81 of 252**): single page, ~1500 chars, one chart row, 112 numeric tokens. Chart-only one-pagers.
- **Numbers are MIXED and the convention flips.** 2021 is pure ISO (period-thousands 0, comma-decimals 0). 2022-2024 show BOTH period-thousands (10-20 hits) and comma-decimals (3-14 hits) in the same doc -> the publisher writes prices as `34,5` (comma decimal = European) while some tonnage columns use `166,000` (comma thousands = ISO). **Do NOT apply one global switch - derive per page / per column, exactly the skill's "parse by shape" rule.**

**allied** - two classes:
- `ALLIED-SnP-Statistics-Week-NN` (9 pages, ~1360 numeric tokens, 80 images): DENSE S&P statistics tables.
- `ALLIED-Weekly-Market-Report` (2021-22) / `Allied-Weekly-Market-Review-Week-NN` (2023-24): 12-14 pages, 2000+ numeric tokens.
- **Numbers are pure ISO** everywhere (period-thousands 0, comma-decimals 0; comma-thousands present). Cleanest convention of the four - the same ISO assumption the other broker runners already use.

**anchor** - `WEEKLY-MARKET-REPORT-WKnn`, 3-4 pages. VECTOR charts (700+ drawings). Numbers **MIXED in the same document**: European comma-decimals (14-31 hits) alongside ISO comma-thousands (33-88 hits). Same hazard as golden_destiny.

**other** - heterogeneous grab-bag: `MID-JULY-2018-SP-REPORT`, `Week-28-2018`, `Weekly-Brief-Week-33`, `01-Oct-2021`, `17-March-2023`. Numbers pure ISO. **Needs sub-classification by publisher before it can be a single measured pipeline** - it is not one source.

## 3. Three-baseline test (is it already ours?)

| baseline | golden_destiny | allied |
|---|---|---|
| live feeds / corpus series CSVs | none (`ls data/extracted/series \| grep -i golden` = 0) | none |
| our own extraction (md tier) | 0/252 | 0/203 |
| app display (index.html) | not rendered | not rendered |

=> **GENUINELY_MISSING** for golden_destiny + allied. (grep hits for "anchor" in
drewry/bancosta CSVs are the word *anchorage* in text, not the publisher.)

## 4. Liveness gate

Newest content across the whole archive = **2024** (golden_destiny W40, allied W05)
-> ~700+ days old. Per the liveness gate, every one of these is **BACKFILL_ONLY,
never CONSTRUCT**: none can extend a series forward. All four are S&P / market
backfill, valuable only as historical depth.

## 5. Recommendation / the open decision

Per-source measured, not started. Ordering and shape if the user green-lights:
1. **allied (203)** - simplest convention (pure ISO), dense tabular S&P data, is
   a genuine historical S&P statistics + market-review set absent from all three
   baselines. Best value-per-effort. Two doc classes -> one runner with a
   per-class template.
2. **golden_destiny (252)** - S&P weekly deal grid + vector charts; 81 of 252 are
   chart-only one-pagers. Needs the mixed number-convention treatment. Runner must
   branch main-report vs special-edition.
3. **anchor (30)** - small; 2021-2022 weekly market report; its timeframe largely
   overlaps what is already held. SKIP unless a specific gap is named.
4. **other (130)** - SKIP until sub-classified; it is not one publisher.

**Nothing is starting on this without the user's go/no-go** (the user gates depth,
and this is BACKFILL_ONLY). This survey is the missing input for that decision:
615 PDFs (not 724), 3 real sources, gibson already done.
