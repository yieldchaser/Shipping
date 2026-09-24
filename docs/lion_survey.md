# LION Shipbrokers - measured survey (source 9, started 2026-09-24)

Counted and probed before any code. **The ism approach does NOT transfer**: lion
is a different source with a different shape, and it contains real tables.

## 1. What is there

| fact | measured |
|---|---|
| documents | **44** (`corpus/01-brokers/lion/`) |
| years | **2024:1  2025:12  2026:31** - a recent, live publication |
| pages/doc | 2 (4), 3 (36), 4 (3), **20 (1)** |
| text layer | median **10,225 chars/doc**, min 7,658 - roughly double ism's |
| filenames | `lion_<year>_W<nn>_Lion-Weekly-Report-<date>-W<nn>.pdf` |
| publisher | Lion Shipbrokers (Athens); `lionshipbrokers.gr` |

## 2. Two DIFFERENT documents live in this source

**(a) The 2025/2026 weeklies (43 docs, 2-4 pages) - prose.**
Page 0 = market commentary (bulkers, tankers, containers) plus a "Quote of the
week". Pages 1-2 = **Sale & Purchase and demolition deal narratives**, e.g.

```
M/V ANDIAMO (63,562 dwt, blt 2019 Shin Kasado/Japan, NKK ss due 11/2029
dd due 03/2027, 5ho/5ha, Cr 4X30.7t, B&W 6S50ME-B9) - sold for $30.5 mill
to undisclosed buyers
M/T BOW CEDAR (37,455 dwt, blt 1996 Floro/Norway, DNV ss/dd due 04/2026,
ice class 1C, 48x stainless steel tanks) - demo for $937 per lt
```

Drawings per page are minimal (`l:1, re:59` on p0 - layout boxes and a logo),
so **there are no vector charts** in these. The extractable value is the deal
records: vessel name, DWT, built, yard, class due dates, price, buyer.
This is the same shape as `banchero_costa`'s deals, which already has
`scripts/extract/banchero_deals.py` - read that before writing anything.

**(b) `lion_2024_W31_Market-report-Week-31.pdf` (20 pages) - a multi-publisher digest WITH TABLES.**
This one document is not a Lion weekly. It reprints other houses' material - its
page 3 is headed `Shipbroking (www.star-asia.com.sg)` and carries
`Baltic Exchange Dry Bulk Indices`, `Dry Bulk Values (Weekly)` and
`Bulker 12 months T/C rates average (in USD/day)`.

## 3. There ARE real tables (unlike ism)

Numeric-row bands on page 3 of the 2024 digest, printed with their x positions -
these span the full page width and hold different values per column, which is
what a table looks like (a chart's tick labels are a single evenly spaced row):

```
y~ 192  n=5  [(164,'1,675'), (244,'1,834'), (323,'1,128'), (404,'-8.67%'), (499,'+48.49%')]
y~ 357  n=6  [(146,'180,000'), (237,'76'), (323,'77'), (394,'64'), (461,'45'), (534,'29')]
y~ 504  n=6  [(137,'180,000'), (200,'22,000'), (263,'22,000'), (329,'15,000'), (424,'0'), (504,'+46.67%')]
```

26 of 44 documents report >=3 such pages, but per the ism lesson that metric is
**not** trusted: on ism the same detector fired on 149/266 pages and every hit
was a chart tick row. Each candidate must be confirmed by reading the page.

## 4. OPEN - do this first next run

1. Render page 3 of `lion_2024_W31_Market-report-Week-31.pdf` and the pages of
   the 2025/2026 weeklies that report numeric bands, and LOOK. Confirm which are
   tables and which are chart tick labels.
2. Decide the target. Candidate ranking, per the standing rule of testing every
   table against three baselines (feeds, our own extraction, what the app shows):
   * the reprinted `Baltic Exchange` indices and the `star-asia` page are likely
     **RESTATEMENT** - star_asia is already extracted (193/193) and the Baltic
     indices already exist in a dedicated corpus folder. Check before building.
   * Lion's OWN S&P and demolition deal records are the part no other source
     holds, and they repeat every week - the likely CONSTRUCT target.
3. Only then build `scripts/extract/publishers/run_lion.py`.

## 5. Not yet measured

* whether the 2025/2026 weeklies carry a table as well as prose
* whether the deal narratives are consistent enough across 43 docs to parse
  into typed fields, or need per-era templates
* whether the 2024 digest's tables are image or text layer (its page 3 has 453
  vector drawings, so it is text/vector, not scanned)

---

## 6. RESOLVED 2026-09-24 - see `docs/lion_verdict.md`

All four OPEN items are closed, with measurements:

1. **Rendered and inspected.** The 2025/2026 weeklies hold **no table and no
   chart** other than the demometer; the numeric bands the survey flagged are the
   demometer rows and the deal narratives. The 2024 digest's page 3 is a
   star-asia reprint (already extracted 193/193) - **RESTATEMENT**, skipped.
2. **Target decided by the three-baseline test.** The demometer is a
   RESTATEMENT (country demolition rates are already in
   `data/derived/scrappage_prices.csv` from Hellenic GMS reports and already
   rendered by `index.html`); it tracks that feed within ~$10/LDT. Lion's **own
   S&P deal tape is the genuinely missing part**: of 1,117 deal vessels only 92
   appear in banchero_costa's 2,920, and fearnleys' name overlap is charter
   fixtures, not sales.
3. **Built and run:** `scripts/extract/publishers/run_lion.py` (self-contained,
   PDF -> text -> parse -> parquet + summary + markdown). 43/44 issues,
   516 demometer rows, 1,145 deal rows.
4. **The deal narratives ARE consistent enough to type**, but three en-bloc
   pricing defects were found and fixed first (38 rows; see the verdict). The
   typed layer is best-effort; the `.md` is the primary deliverable.

An extraction of this source already existed in `data/extracted/` from 2026-09-22
(parquet + summary, never committed, never verdicted). It was **verified rather
than rebuilt**: the defects above were found by verifying it, and it is now
reproducible from a committed runner.
