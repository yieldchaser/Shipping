# Fearnleys (source 5) - ALREADY EXTRACTED; the numbers were the redundant part

## CORRECTION to the earlier "SKIPPED" verdict in this file's history

An earlier version of this document said fearnleys was SKIPPED as redundant. That
was based on the NUMBERS being already ingested, which is true - and it was
written WITHOUT CHECKING whether an extraction already existed. It did:

    data/extracted/md/fearnleys/   : 257 .md files, 11 MB
    _run_state.json                : done=257, failed=0

So the work was already done. The correct statement is not "skipped" but
"already extracted, and only the numbers would have been redundant".

## What the existing extraction contains (verified by reading it)

Structure of a 2026 document's .md:
    # <stem>
    source: `corpus/...` | pages: N | era: A-cards
    ## Typed rows (era A-cards) - 71        (a table of page/chapter/section/
                                            label/value/size/change, e.g.
                                            | 2 | Rates | Dirty | MEG/WEST | 375 | 280' | 50 |)
    ## Full page text
    ### Page 1 ... ### Page N              (one section per page)

The COMMENTARY - the part that matters, because the numeric side is already held
- IS present and clean. Verified by opening page 2 of a 2026 document and finding
a complete, well-formed paragraph:

    Aframax / Rates
    "The majority of the publicly reported West Africa cargoes have either fixed
     away or may have relets to utilise. As a result, we are likely pushing into
     the 27-30 September fixing window. ... Aframaxes are surging in the
     Mediterranean ..."

Vessel-class headings present in the corpus: Aframax (8 hits in one doc),
Suezmax (8), VLCC (11), North Sea (6), Mediterranean (3), Dry Bulk (3).

The documents were classified by era during that extraction:
    A-cards   (2023-2026, 19-20pp, HTML printed to PDF, cards)
    B-rows    (2021-2022, 1pp posters, 84 rows)
    C-garbled (2018, a third shape)

## The numbers question, settled
The 2023-2026 PDFs are an HTML print of the publisher's own Fearnpulse web app
(the footer carries its report URL). The numeric side is already ingested from the
same backend via Hasura:

    data/derived/fearnleys_broker_comments.csv    11,733 rows
    data/derived/fearnleys_fixtures_full.csv     549,480 rows
    data/derived/fearnleys_snp_transactions.csv    2,643 rows
    data/derived/fearnleys_catalog.csv               357 rows

So no numeric extraction is needed from these PDFs. The existing extraction
already records the card values anyway (harmlessly, as an appendix table); they
should simply not be treated as the data source.

## Known defect, low priority
The "Full page text" sections carry some non-commentary noise that a cleaner pass
could strip:
  * UI artefacts that survive the print: 'Click rate to view graph'
  * rate-card values interpolated as bare lines (MEG/WEST / 375 / 280' / 50)
  * chart axis labels (Jul '25, Aug '25, 0, 500, 1000 ...)
None of it corrupts the commentary, and since the numeric side is duplicated from
Hasura, cleaning it is cosmetic rather than corrective.

## Scope note carried over
The user noted the S&P deal data has not updated for a couple of days. That is a
SYNC failure in the fetch_fearnleys_snp.py pipeline and is NOT something PDF
extraction fixes. Investigate the fetcher separately if it persists.
