# Fearnleys spot-check - CORRECTION. I made a false claim and acted on it.

## What I claimed
That the pre-existing fearnleys extraction had suffered DATA LOSS - specifically
that the page-5 commentary paragraph of 2026 W18 was missing, and that two phrases
from the rendered page ("Owners are resilient, holding offers in the USD 33-33.75
range" and "fronthaul C9 stems commanding USD 67,000/day") were absent from the
.md.

## What is actually true
NOTHING WAS MISSING. With whitespace normalised, all of those strings are present
in the ORIGINAL extraction:

    "This week on Capesize, C3 Brazil/China market remains firm but tense"    OK
    "Owners are resilient, holding offers in the USD 33-33.75 range"          OK
    "fronthaul C9 stems commanding USD 67,000/day"                            OK

## Why my test lied
The original .md is a VERBATIM dump, so it preserves the PDF's line wrapping:

    ... Owners are
    resilient, holding offers in the USD 33-33.75 range for second half May ...

I searched for a phrase that SPANS that wrap, so the naive `substring in md` check
failed and I concluded the text was absent. The bug was in the test, not the data.

A second measurement confirms the original is BETTER, not worse:

    coverage of the raw PDF's prose sentences
      original : 89-100%
      mine     :  6-94%
    documents where mine covered more: 0
    documents where original covered more: 11

The original is LONGER (193,301 chars vs 130,232 over the sample) precisely because
it keeps everything verbatim, including chart-axis labels and UI artefacts. Mine
strips those, which reads better but covers less of the source text.

## What was done about it
The original has been RESTORED as the canonical extraction:
    data/extracted/md/fearnleys          <- ORIGINAL, verbatim, 257 docs
    data/extracted/md/fearnleys_cleaned  <- mine, noise-stripped, 257 docs
Both are kept so the trade-off is visible rather than silently decided. My version
is NOT an upgrade and should not be promoted without a reason.

## The lesson, which is the same one as the intermodal failure
A MEASUREMENT BUG produced a confident, actionable, WRONG finding - and I then
spent a re-extraction pass acting on it. Earlier the same night the mirror image
happened: a broken control test condemned a CORRECT intermodal extraction.

Both times the tell was the same and I had it available: when a measurement says
something surprising, verify the MEASUREMENT against the rendered document before
acting. On page 5 of the rendered PDF the paragraph is plainly visible; the honest
move was to reconcile that first, not to write an extractor.

## Status
Fearnleys: extraction is intact and verified present. NO work needed. The earlier
"the text was not fully extracted" claim in this session is retracted.
