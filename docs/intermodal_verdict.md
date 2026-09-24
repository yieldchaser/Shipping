# Intermodal (source 6) - COMPLETE, 100% control agreement

## Result
data/extracted/intermodal_tc_rates_v2.csv
  252 documents, 2021-07-06 -> 2026-09-18  (5+ years)
  180 of 252 with all 20 fields; 0 failures; both table pages found on all 252.

CONTROL TEST vs the pre-existing 49-row CSV, over the 47 overlapping weeks:
  compared 846 values   agree 846   = 100.0%
  every field 47/47 = 100% (aframax, capesize, handy_tanker, handysize, mr,
  panamax, suezmax, supramax, vlcc, each 1yr and 3yr)

Gain: the old CSV covered 18 months (2025-03-07 -> 2026-09-11); this covers
5+ years. The old file is left untouched as the reference.

## How it was finally got right
THE EXTRACTION WAS CORRECT EARLIER THAN I REALISED; the MEASUREMENT was broken.

1. The 20 inherited RATE_FIELDS span TWO tables on TWO pages, which is why a
   single-page extractor capped at exactly 12/20:
     page 2 'Tanker Market'   -> 300k/150k/110k/75k/52k/36k   (12 fields)
     page 3 'Dry Bulk Market' -> 180k/76k/58k/32k             (8 fields)
   Anchor each table by a label only it carries: '300k Nyr TC' vs '180k Nyr TC'.
   This also resolves the shared-'Panamax' trap: tanker 75k and dry bulk 76k,
   so a pattern accepting 7[56]k matches both and only page context separates them.

2. The date header format CHANGED between years: 2025 writes 07/03/25 (8 chars),
   2026 writes 08/05/2026 (10 chars). A regex demanding dd/mm/yy found NOTHING in
   2026 and returned 0/20 with no error at all. Page 3 also uses uppercase K
   (180K) where page 2 uses lowercase (300k).

3. THE CONTROL WAS COMPARING THE WRONG ROWS. The known-good CSV dates a report by
   its ASSESSMENT date - the current-week column header inside the table (07/03/25
   for W10) - while the extractor was taking a long-form date from the body text,
   which is the publication date, offset by a week. With a +-7-day matching window
   the control paired old 2025-03-07 with the WRONG v2 row (W09, dated 2025-03-04,
   holding 44,750) instead of W10 (44,500). That produced a reported 61.9%
   agreement and nearly got correct work condemned as broken.

   Fixed by taking the date from the table header's current-week column, choosing
   the LOWEST dd/mm/yy row on the page since the banner carries one higher up.
   Agreement went 61.9% -> 100.0% with NO change to any extracted value.

## The lesson, and it cuts both ways
A control test is the only thing that distinguishes a complete-looking extraction
from a correct one - it caught the first backfill being 16.5% wrong while reporting
252/252 with no failures. But a control test with a subtle MATCHING bug will also
condemn a correct extraction, silently, and that is what happened here for several
rounds. Both failure modes look identical from the outside: a plausible percentage.

So the rule is: when a control disagrees, verify the DISAGREEMENT ITSELF against a
rendered page before touching the extractor. On 2025 W10 the extractor's output
matched the page exactly while the control said 61.9% - the document settled it.

## Method note
Reused the pre-existing validated patterns from update_intermodal_tc_rates.py
(they fired 20/20 on PDF text in every year) rather than writing a parallel parser.
Only that script's INPUT PATH was broken - it reads reports/broker_reports/2026, a
directory deleted in the corpus migration; 22 scripts still reference it. Fixing
that path for the live pipeline is a separate, still-open cleanup.
