# Fearnleys survey (source 5) - MEASURED

> **SUPERSEDED FOR EXTRACTION: this source is SKIPPED** (user decision 03:05,
> `docs/fearnleys_verdict.md`) - the publisher is already ingested structurally
> from its own Hasura backend, so the PDFs are a worse copy. The layout
> measurements below are kept because they transfer to other sources, and
> because they CORRECT the first version of this survey (see below).
> The in-flight extraction is recorded in `docs/fearnleys_extraction_record.md`.

257 PDFs: 2018:1 2021:26 2022:49 2023:49 2024:48 2025:48 2026:36
Fingerprint of all 257: `scratch/fearnleys/fingerprint.jsonl` (pages, chars,
value-shaped lines per layout, printable ratio).

## THREE payload shapes, and a correction to the first survey

The first survey (02:52) concluded "Era B (2021-2022) = 1-page posters, PROSE
only, no table". That was WRONG - the probe read the first 22 lines of the page
and stopped, and the rate table sits BELOW the commentary. Measured now: those
files carry a full rate table (84 rows) with the SAME routes and the SAME vessel
sizes as the 2026 cards. The limitation was the probe, not the document.

| shape | n | pages | what it is | typed rows/doc |
|---|---|---|---|---|
| A-cards | 130 | 19-20 | fearnpulse.com HTML page printed to PDF | 30-92 (71-73 typical) |
| B-rows | 57 | 1 | 2021-2022 landscape poster: prose + rate table | 84 |
| printer | 46 | 7 (26 docs) or 19-20 (20 docs) | fearnpulse.com/print, A4 portrait | 84 (7pp) |
| image-only | 23 | 19 (12), 441 (6), 20 (3), 1, 8 | content is a RASTER; text layer = browser header/footer only | 0 - QUARANTINED |
| garbled | 1 | 3 | 2018 W29, custom font encoding to control chars | 0 - QUARANTINED |

## Geometry is NOT stable - and neither is font size

Three different layouts across five years, none of which survives a hardcoded
coordinate or a hardcoded size:

* **A-cards (2023-2026)**: card label x=57.8, value x=57.8 about 27pt below it,
  vessel size and change in the right column (x~470-522). Card pitch 105pt.
  Cards STRADDLE PAGE BREAKS (2026 W18: 'VLCC' label p3 y=767, value p4 y=29).
* **B-rows (2021-2022 poster)**: label x=260.2, value x=676.5, change
  x~1518-1574, all on the SAME y, pitch 70pt. One page, ~7700pt tall.
* **printer (7pp, 2021-2023)**: label x=105.3, value x=302.3, change x~700,
  same-y rows, pitch 38.8pt.

**The size trap.** `fearnleys_2023_W39` is the A-cards layout rendered at ~10%
scale: card fonts are 1.5 / 1.8 / 1.3pt where 2026 W18 has 15 / 18 / 13.5pt.
The POSITIONS are identical (label x=58.3, size x~512, 105pt pitch). An 18pt
size threshold returned **0 rows** on that file while returning 71 on 2026 W18 -
one whole document silently lost. It also splits words into fragments
('W' + 'AF/FEAST', '$37' + ',000', '1 Y' + 'ear T' + '/C').

So the pipeline anchors on POSITION + CONTENT only: fragments on one baseline
are merged, a value is a cell whose text IS a number, a label is the nearest
text cell in the same column above it, and the section tiers are derived from
the document's own heading sizes.

## Charts

RASTER in every era (1 embedded image per page in A-cards; the posters carry
3-5). No chart series are taken. The axis tick labels ARE text and are excluded
explicitly: they form a chain of plain numbers in one narrow column, which the
cross-page label carry-over once attached to a real card label ('Spread
MGO/380 CST' -> tick '2500'), producing one phantom row in 71.

## Numbers

ISO/US in every era: `$67,028`, `$13.24`, `$27000.0`, `WS 21.0`, `4.14%`. The
advanced_shipping European parser must NOT be reused. Change cells carry an
up/down arrow as a PRIVATE-USE-AREA glyph after a newline (chr(0xF062)); a plain
strip() leaves it in place and EVERY change is dropped.

## Content

Tankers (dirty/clean spot WS by route, 1yr T/C), Dry Bulk (Capesize/Panamax/
Supramax TCE, 1yr T/C, BDI), Gas (LPG/LNG spot, FOB propane/butane),
Newbuilding, Sale & Purchase, Market Brief (FX, SOFR, Brent, bunkers).
