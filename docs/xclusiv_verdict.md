# Xclusiv (source 4) - COMPLETE (3 passes), verified

266/266 documents, 0 failures, 520s (pass 2, after the labelling fix).
Output `data/extracted/md/xclusiv/`: 266 .md + 266 .tables.json + 266 .charts.json
  markdown 7.5 MB total, min 4,194 bytes, none under 2 KB.

## What the two passes established

Pass 1: 7,731 rates, 85% labelled - but VERIFICATION AGAINST A RENDERED PAGE
showed the labels were wrong. "West Africa to Continent trip is up..." had come
out labelled "Middle East Gulf" (a route named later in the same sentence), and
"North Sea to Continent trip is down..." had come out "US Gulf". 85% labelled was
hiding wrong pairs.

Fix applied: pick the VALUE first, then label THAT value with the nearest
vocabulary term PRECEDING it, within 120 characters; otherwise leave unlabelled.

Pass 2: 7,731 rates, 69% labelled.
Pass 3: 266/266, 0 failures, 299s, with duplicates and stray values removed. The wrong pairs are gone:
    West Africa to Continent trip      -> West Africa   98,909  +16.6k  OK
    US Gulf to UK-Continent            -> US Gulf       97,793  +6.6k   OK
    Middle East Gulf to China trip     -> China        453,227          OK
    LR1 route (TC5) ... to Japan       -> Japan        131,200  +1.9k   OK
    Suezmax / Aframax / LR2 / MR       -> correctly labelled             OK
Fewer labels, correct ones. A wrong label is worse than a missing one.

## RESOLVED in pass 3 (verified: 0 duplicates, 0 stray values across the corpus)
1. DUPLICATE VALUES: 153,488 appeared BOTH as LR2 and as MR. FIXED - rows are now
   de-duplicated by value, a labelled row superseding an unlabelled one and later
   re-mentions dropped. Measured after: duplicate values across corpus = 0.
2. STRAY NOISE: a value of 1 came from an 'IN A NUTSHELL' sentence. FIXED with a
   floor of 100 - real T/C rates are thousands/day, so narrative integers are
   excluded without touching a rate. Measured after: stray values = 0.

## STILL OPEN (acceptable, disclosed - not defects)
3. 'North Sea to Continent trip is down by 84.k/day at USD 126,913/day' - the
   value looks inconsistent with its sentence. Left as unlabelled so it cannot be
   mistaken for a confirmed rate.
4. VLCC 219,233 on 2026-04-27 is unlabelled. A missing label, not a wrong one.

## What IS trustworthy
- The .md corpus: complete, full page text for all 266 documents, 7.5 MB.
- Rates that carry a label: verified correct on the spot-checked page.
- The 2,358 unlabelled values: the values are on the page, but their subject is
  NOT asserted. Treat them as values-without-subject, not as wrong.

## Method note (the lesson this source taught)
Verification against a rendered page is what caught the defect. The metric that
looked healthy (85% labelled) was the metric that was hiding the problem.
Never accept a coverage percentage without reading examples against the page.

---

## 2026-10-05 RE-VERIFICATION (271/271 now, typed layer confirmed)

The source grew from 266 -> **271 documents** (2026: 45, all other years unchanged).
**1:1 per year, zero gaps:** 2021:23, 2022:51, 2023:50, 2024:51, 2025:51, 2026:45
= 271 md against 271 PDFs. 271 .tables.json sidecars.

Verification method: this session has NO vision tool, so the check was done against the
**PDF's own text layer** (pymupdf get_text), not by eye. PNGs were still rendered for a
human look (scratch/xclusiv_verify/xclusiv_w39_p1..p3.png, dpi=115).

Spot-check doc: xclusiv_29_09_2026_xclusiv_shipbrokers_weekly_28th_september_2026.pdf
(W39, 9 pages). **15/15 values present VERBATIM in the PDF text, each exactly once:**
- Baltic indices: BDI 3,426 / BCI 5,784 / BPI 2,407 / BSI 1,786 / BHSI 1,011 / BDTI 5,366 / BCTI 2,160
- Dry freight: Capesize C5TC 48,954 / Kamsarmax P5TC 21,662 / Ultramax S11TC 22,579 / Supramax S10TC 20,545 / Handysize 18,190
- Tanker: VLCC 714,143 / Suezmax 299,424 / Aframax 234,370

TYPED LAYER (tables.json) CONFIRMED CONSISTENT with both md and PDF: structured schema
(`baltic_indices`, `reported_sales`, `newbuilding_orders`, `indicative_*_prices`).
Sampled row `GCL HAZIRA | Kamsarmax | 81,986 DWT | 2021 | NACKS | GERMANS | 39 | SURVEYS PASSED`
- all 5 tokens verbatim in the PDF. Baltic typed values match md exactly
(BDI 3426/3370/1.7%, BCI 5784/5768/0.3%). Counts match frontmatter (sales 20, demo 1,
NB orders 10, secondhand 32, NB prices 9, demolition 8). So the typed layer is NOT merely
best-effort on this doc - it reconciles with the page; the .md remains the primary deliverable.

Chart layer present: data/derived/xclusiv_chart_series.csv (937 rows), 8 PNG charts for W39.
DISPLAY: still KB-only - **0 fetch paths / 0 series refs for xclusiv in index.html**.
