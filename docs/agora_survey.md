# AGORA "SNAPSHOT OF COMMERCIAL INDICATORS" - survey (measured, not estimated)

Source 7 of the source-by-source programme. 213 PDFs under
`corpus/01-brokers/agora/`, years 2021:25 2022:37 2023:50 2024:38 2025:35 2026:28.
Every number below was measured by running the script named beside it. No vision
tool exists in this unattended session, so "look at the page" is replaced by the
documented substitute: full-page line/span dumps with coordinates
(`scratch/agora/dump.py`, `outline.py`), a drawing-geometry dump (`geom.py`) and a
whole-corpus token census (`census.py`, `convention.py`). Stated plainly because
the skill forbids reporting a metric as if it were a look.

## What the document IS

Landscape (841.9 x 595.3 pt), **5 pages** in 205/213 docs and 6 in 8 docs
(2021 x3, 2022 x1, 2023 x2 - measured with `outline.py`). Fixed structure, in
this order:

| page | content | data? |
|---|---|---|
| 0 | cover: title, week, a quotation, introductory note | no |
| 1 | COMMODITY FUTURES (15 rows), USD LIBOR (12 months), EXCHANGE RATE (3 pairs) | **yes** |
| 2 | STOCK MARKETS (8 indices), 10-YEAR BOND, BUNKERS (4 ports), BALTIC EXCHANGE (5 indices + 4 T/C) | **yes** |
| 3 | Notes (numbered definitions of the 15 commodities) | no |
| 4 | CONTACT DETAILS (desks, e-mails) | no |

Section-title census over all 213 docs (exact string present in the page text):
`COMMODITY FUTURES` 213/213, `USD LIBOR` 213/213, `10-YEAR BOND` 213/213,
`STOCK MARKETS` 213/213, `BALTIC` 213/213, `Notes :` 213/213.

**Page order is NOT stable.** The 6-page documents insert the introductory note
as a separate page, so page index 1 is a prose page in them (measured on
`2022_W10`, whose page 1 holds only the intro note). Route pages by CONTENT
(the page carrying `COMMODITY FUTURES` is the first data page), never by index.

## NO CHARTS

`geom.py` on every page: the 1,557-1,575 drawings per document are all
**zero-width `re` fill items with `color=None`** (table row shading) plus exactly
ONE stroked 0.75pt black line per page. There is no plot area, no axis, no series
path. The 5 embedded images per document are the same 692x190 logo on every page;
2025+ adds 6 small (147-512 px) logos on page 4. `.charts.json` is emitted empty
with that reason recorded.

## THE HAZARD: two number conventions, switching mid-2022

Agora writes the same field two ways in different eras. Anchored on a SEMANTIC
row (Crude Oil / Brent / Gas Oil / Gold / Copper "Actual last" is USD/barrel with
2 decimals, so its separator is decisive), measured per document by
`scratch/agora/era_convention.py`:

| era | docs | convention | page text |
|---|---|---|---|
| 2021 W25 - 2022 W26 | 25 + 26 | **US** | `$78.96`, `4.40%`, `$1,398.34`, `$9,610.00` |
| 2022 W43 - 2026 W36 | 10 + 50 + 38 + 35 + 28 | **EU** | `92,85`, `-2,07%`, `4.492,82`, `13.932,00` |

* 2022 W27-W42 are **absent from the corpus**, so the exact switch week is not
  observable; the switch is bracketed to that gap (US at W26, EU at W43).
* `2022_W52_...-Week-52.-2021-...pdf` is a 2021 report misfiled in the 2022
  folder and reads EU, like its year.
* 2022 W10 was the only document the anchor failed on - because it is a 6-page
  file whose page 1 is prose. With content-based page routing it resolves.

Reading `92,85` as 9285, or `4.492,82` as 4.49282, is the silent 1000x error the
skill warns about, in the plausible direction. **The convention is therefore
derived per document from the page itself** (the anchor rows above), not from a
year table, and the document's own `convention` is recorded in the output.

Sub-hazard inside the EU era: thousands separators appear only above ~1,000 and
not even always then - the same 2026 page prints `1073,12` (no separator) next to
`4.492,82` (separator). Both are comma-decimal; the parse rule is "comma present
-> comma is the decimal point; a lone period is a thousands separator".

## Other measured hazards

* **A span can carry TWO values.** 2026 bunkers row `Fujairah` has
  `$1.183   $1.584` in ONE span (VLSFO and MGO fused) because the two cells wrap
  together. Values must therefore be read at WORD level (`get_text("words")`),
  each with its own bbox, never at span level.
* **A label can contain a number that looks like a value.**
  `BCI T/C - 182.000 dwt` carries `182.000` = 182,000 dwt. Label text is never
  fed to the value parser; it is matched by vocabulary instead.
* **A month annotation sits mid-row** in COMMODITY FUTURES: `(Jun 21)` at
  x~290-322, between the label column and the Unit column, on its own y. It is
  parenthesised and is excluded from values by that rule.
* **Header rows wrap**: 2023-2026 print `Exchange - Currency&` / `Unit` on two
  lines, 2021 prints it on one; `10-YEAR BOND` / `YIELD` likewise. Column bands
  are derived from whichever header line exists on that page.
* **`% 4-weekly` for the 2026 EXCHANGE RATE row EUR/USD is `-1,10%`** while the
  USD/INR row shows `0,65%` - sign is part of the cell, not a separate column.
* The value columns are right-aligned, so the x of a value depends on its width
  (`4.492,82` starts at x=520.9, `92,85` at x=544.9). Column bands must be
  defined by the HEADER positions, never by where a particular value happens to
  start.

## Column map (from the 2026 W23 page dump, confirmed on 2021 and 2022)

| section | label col | value columns (header x) |
|---|---|---|
| COMMODITY FUTURES | Commodity x~123 (+ Unit x~363, month x~290) | Actual last 519-535, % weekly 592, % 4-weekly 662-667 |
| USD LIBOR | x~87-116 | Actual last 181-200, % weekly 254-267, % 4-weekly 320-338 |
| EXCHANGE RATE | x~498 | Actual last 587-596, % weekly 662-669, % 4-weekly 734-747 |
| STOCK MARKETS | Country x~22, Index x~85 | Actual last 267-296, % weekly 334-342, % 4-weekly 399-412 |
| 10-YEAR BOND | Country x~515 | Actual last 604-611, % weekly 670-678, % 4-weekly 732-745 |
| BUNKERS | Port x~610 | IFO380 676-680, VLSFO 723-728, MGO 771-776 |
| BALTIC EXCHANGE | BDI/BCI/BPI/BSI/BHSI x~17 | Actual last 87-93, % weekly 149-157, % 4-weekly 214-226 |
| BALTIC T/C | `BCI T/C - 182.000 dwt` x~283 | Actual last 405, % weekly 466-471, % 4-weekly 533-535 |

## Deliverable

`.md` is the primary artefact: the two data pages as markdown tables plus the
prose/notes/contact pages as text. `.tables.json` carries typed rows per section
with the document's own convention recorded. `.charts.json` empty (no charts).
