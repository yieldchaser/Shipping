# AFFINITY TANKER WEEKLY - survey (measured, not estimated)

Source 6 of the source-by-source programme. 250 PDFs under
`corpus/01-brokers/affinity/`, years 2021:26 2022:47 2023:50 2024:50 2025:42 2026:35.

Every number below was measured by running the scripts named beside it. No
vision tool exists in the unattended session, so "look at the page" is replaced
by the documented substitute: full-page span dumps with coordinates
(`scratch/affinity/dump.py`), font/flag maps (`fonts.py`) and a value-level
reconcile against the extracted rows (`recon.py`). Stated plainly because the
skill forbids reporting a metric as if it were a look.

## What the document IS

A landscape one-pager (842.0 x 595.3 pt), published weekly. Two regions:

| region | x | content |
|---|---|---|
| prose | 16.7 - 589.9 | tanker market commentary, TWO columns (col A x~17, col B x~307) |
| card panel | 596.8 - 832.0 | four stacked data cards, grey background rect y 94.6 - 561.4 |

Page 0 is the data page. 84 of 250 docs carry a SECOND page that is the legal
disclaimer only ("The information contained in this report is the property of
Affinity (Shipping) LLP...", 3,110-3,143 chars, no numbers). Page count varies
WITHIN a year (2022-01-21 is 1 page, 2022-06-10 is 2), so page count is not an
era marker - route page >= 1 by content.

## The four cards (constant vocabulary, 250/250 docs)

Measured by exact-vocabulary match inside the panel rect (`vocab.py`):
`BDTI`, `BCTI`, `BDA`, `BALTIC TCE DIRTY`, `BALTIC TCE CLEAN` are present in
**250/250** documents. Column headers: `Route` 250/250, `$ / Day` 250/250,
`W-O-W` 250/250, and `Qnt` 186 + `Qty` 64 = 250 (the only header variation).

1. **BDTI / BCTI** - two index levels on one row (date, BDTI, BCTI), then a
   `Δ W-O-W` row whose cells are arrows `↑Firmer` / `↓Softer`.
2. **BDA** - `(USD/LDT)`, columns `TKR/LRG | TKR/MED | TKR/SML`; row
   `This week` (2021-2023) or a bare date (2024+), then a `Δ W-O-W` row.
3. **BALTIC TCE DIRTY** - `Route | Qty | $ / Day | W-O-W`; rows `TD3C`, `TD7`,
   `TD15`, `TD19`, `TD20`, `TD22`, `TD25`, `TD26`, `TD27`.
4. **BALTIC TCE CLEAN** - same columns, `$ / WS` where the route is quoted in
   Worldscale (68 docs); rows `TC1`, `TC2`, `TC5`, `TC6`, `TC7`, `TC8`, `TC9`,
   `TC14`.

## Layout is NOT stable - three traps, all measured

* **Font size changes per document.** Modal card size is 9.0 in 2021, 8.6 in
  2022-30.09, 8.3 in 2023-01.09, 8.0 in 2023-31.03 and 2021-07-16 is 9.7.
  A fixed size threshold deletes whole cards. In 2021 prose and card data are
  BOTH 9.0 pt, so size cannot separate them at all.
* **The panel rect is the only stable separator.** Measured identical
  `(596.8, 94.6, 832.0, 561.4)` in **250/250** documents (`census.py`). The
  boundary is read off the page (largest grey fill on the right), never typed.
* **Card titles are NOT always bold.** 4/250 docs (2021-07-02, 2021-10-15,
  2022-01-14, 2022-01-28) render `BDTI`/`BDA`/... in plain Calibri 9.0, not
  Calibri-Bold 10.0. Bold/size detection therefore mis-fires on 1.6% of the
  corpus; exact vocabulary is used instead (`odd.py`, `vocab.py`).

## Other measured hazards

* **A card header date WRAPS across spans and rows**: 2026 reads `18/09/202`
  then `6` on the next y. Same for `31/10/202` + `5` (2025). Merge by column.
* **Cells WRAP VERTICALLY AROUND their own data row.** The columns are narrow,
  so a long value is split over the line above and the line below. Three shapes
  were measured on real pages:
  - description: `ME Gulf / US` (y-5.4) | `TD1` row | `Gulf` (y+5.4)
    (2022-07-29)
  - value: `WS` (y-5.4) | `TC6` row | `221.88` (y+5.4) (2022-07-29)
  - date: `01/04/` + `2022`, split across the header row (2022-04-08); and
    `15/12/202` + `3` (2023-12-15), `18/09/202` + `6` (2026-09-19).
  Reading row-by-row therefore loses the description on TD1 and the value on
  TC6. Fragments are attached to the nearest data row within 8pt of y (the row
  pitch is 16.5pt, so the window is unambiguous) and joined in y order.

  A first pass also claimed 2026 `TD19`/`TD27` were "missing their route name".
  That was WRONG - it came from my own `grep -v '[A-Z][a-z]'` filter, which
  deleted `Med / Med` and `Guyana / UKC` because they start with a capital
  followed by a lower-case letter. Verified by re-reading the raw spans: both
  names are present at the same y as their code. Lesson restated: a probe that
  filters can lie exactly like a probe that stops early.
* **A value and its arrow can share one span**: 2021 `WS 130.63 ↑Firmer` at
  x 747.7-825.3. Split before parsing.
* **The first header cell is literally `#####`** in 2021 (Excel's "column too
  narrow" rendering). It is the route-code column, not a value.
* **Numbers are ISO/US**: `280,000` = two hundred eighty thousand, `591.6` =
  591.6. European parsing must NOT be reused here. Cross-check that the
  convention is right: 2026 TD3C `ME Gulf / China` = 1,241,097 $/day and the
  prose of the same page says VLCC rates "have surpassed USD 1 Mn per day".

## Charts

NONE. Page 0 carries 14-20 vector drawings and they are all single horizontal
rules spanning the panel (card separators) plus two small teal underlines below
the section titles - verified by dumping every drawing's geometry
(`geom.py`). Images are the logo only. So there is no chart layer to extract and
`.charts.json` is emitted empty with that reason recorded.

## Deliverable

`.md` is the primary artefact (prose + the four cards as markdown tables).
The typed card rows in `.tables.json` are best-effort and labelled as such.

## Trial result (measured)

Before the bulk run the pipeline was trialled on documents from 2021, 2022,
2023 and 2026, then on seeded random samples of 30 and 60 documents
(`scratch/affinity/sample_check.py`, `scratch/affinity/verify2.py`):

* 60/60 documents: 0 exceptions, 4/4 cards parsed, **0 value-shaped words in the
  card panel unaccounted for**, 0 route rows without a description.
* Every hand-read value matched: 2021-10-01 BDTI 626 / BCTI 496, BDA
  591.6/597.0/595.8 with deltas -1.3/-2.0/-2.2, TD1 -15,692 and TC6
  `WS 130.63`; 2026-09-19 BDTI 4899 / BCTI 1943, TD3C 1,241,097.
* 2022-07-29 TD1 `ME Gulf / US Gulf` / -15,955 and TC6 `WS 221.88`, and
  2022-04-08 TD1 `ME Gulf / US Gulf` / -16,968 and TC8 `40.64` - the exact
  values the vertical-wrap defects had been dropping - now match.
* With no vision tool available, the render-and-look step is replaced by the
  documented substitute (`scratch/affinity/inktest.py`): page 0 rendered at
  dpi=115 and each hand-read value's bbox pixel-tested against the card panel's
  own background. Dark-pixel fraction inside the value boxes is 0.21-0.33
  against 0.064 for an empty panel strip, so the values are genuinely printed
  where the text layer says they are.
