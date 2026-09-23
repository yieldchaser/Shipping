# Fearnleys survey (source 5) - IN PROGRESS

257 PDFs, 2018-2026 (2026: 36 docs).

## THE KEY FINDING: two completely different document types

The year-audit caught a structural break that would have wasted a bulk run:

  yr    pp  vec rast   font sizes
  2018   3   3    0    4.7-6.0
  2021   1   1    1    18.7 20.0 21.2 26.2 30.0 40.0   <- poster-sized
  2022   1   1    1    18.7 20.0 21.2 26.2 30.0 40.0   <- poster-sized
  2023  20   0    0     8.0  9.0  9.6 10.5 11.2 12.0
  2024  19   0    0     8.0  9.0  9.6 10.5 11.2 12.0
  2025  19   0    0     8.0  9.0  9.6 10.5 11.2 12.0
  2026  19   0    0     8.0  9.0  9.6 11.2 12.0

### Era A - 2023-2026 (19-20pp): an HTML page PRINTED to PDF, cards not tables
Read by eye from 2026 W18 page 3:
  footer: https://fearnpulse.com/fearnleys-weekly-report?user=...&date=2026-04-29
  header: '29/04/2026, 18:42   Fearnleys Weekly Report | Fearnpulse'
  a UI artefact survives the print: 'Click rate to view graph'
The data sits in UI CARDS with a clean 4-LINE REPEATING pattern, verified as
selectable text (every probe hit):
      WAF/USAC            220    130'   22.5
      Sidi Kerir/W Med    260    135'   20
      N. Afr/Euromed      300     80'   10
      UK/Cont             240     80'   10
      Caribs/USG          500     70'   85
  -> (route, value, size, change) tuples. This is NOT a table-parser problem.
  NOTE this is the same HTML-as-PDF pattern seen in seabrokers, so treat it as a
  known document class rather than a novel one.

### Era B - 2021-2022 (1pp posters): PROSE commentary, xclusiv-like
      Week 40 - October 06, 2021 / Printer version / Tankers / Comments
      VLCC / 'A busy week on the whole, but VLCC rates very much like an arm
      wrestle, edging to the ow...' / Suezmax / 'The Suezmax market looks to...'
  No cards, no table. Vessel-class headings above prose paragraphs.

## Numbers
ISO/US leaning (US-thousands 3-6 per doc, European thousands 0, European
decimals 0-1). Must be re-measured per era before parsing - the two eras are
different authors' pipelines.

## Strategy (two extractors, one per era, do NOT force one over both)
- Era A: walk the card text in reading order and cut the 4-line repeating pattern
  into (route, value, size, change). Validate by checking the pattern holds for
  every card and that values are plausible magnitudes.
- Era B: prose extraction as for xclusiv - headings define the subject, and any
  numeric rates in the paragraph attach to the nearest preceding heading.
- The 2018 3-page docs are a third shape; handle after the two main eras.

## OPEN
- Confirm the 4-line pattern holds across many Era A documents, not just page 3 of
  one file. Count how many cards per document and where the pattern breaks.
- Confirm Era B prose actually carries numeric rates or only commentary. If only
  commentary, Era B yields text for the knowledge base but no typed series.
