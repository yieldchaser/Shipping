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
