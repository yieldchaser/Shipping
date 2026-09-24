# AGORA "SNAPSHOT OF COMMERCIAL INDICATORS" - verdict (source 7, COMPLETE)

213 PDFs (`corpus/01-brokers/agora/`), 2021:25 2022:37 2023:50 2024:38 2025:35
2026:28. Pipeline `scripts/extract/publishers/run_agora.py`; survey
`docs/agora_survey.md`. Output `data/extracted/md/agora/` (213 `.md` +
`.tables.json` + `.charts.json`, 7.4 MB total).

## Result (measured)

| metric | value |
|---|---|
| run_state | done **213** / failed **0**, elapsed **53 s** |
| files | 213 `.md`, 213 `.tables.json`, 213 `.charts.json` |
| data rows typed | **10,002** |
| value-shaped words seen on data pages | **42,013** |
| value-shaped words not accounted for | **3** (three literal `1.` note markers, named below) |
| sections per document | 8 in 202, 9 in 10 (a table continuing onto the next page), 7 in 1 |
| convention derived from the page | 213/213 by the semantic anchor rows, 0 by fallback |

## Independent verification (not the pipeline's own counters)

`scratch/agora/verify_sample.py 213` re-reads all 213 PDFs itself and applies
gates a wrong number convention cannot pass:

* every value word in the produced `.md` (raw form, whitespace-insensitive);
* **Crude Oil / Brent "Actual last" must parse into 20-250 USD/barrel** under the
  document's declared convention - **426/426 passed**, so the US/EU choice is
  right document by document, not by year table;
* BDI must parse into 300-6000 - **212/212 passed** (one document has no BDI);
* all seven sections present - **0 missing**.

Result: **0 failures**, 3 unexplained values, 2 tables that the publisher printed
empty (2021 W52 shows a dash in every BALTIC cell) which the `.md` now renders as
"_this table carried no numeric cells on the page_" instead of silently omitting
the section.

## Hand-read controls (page text read against the output)

| document | page says | output |
|---|---|---|
| 2021 W25 (EU) | `$74,05` / `3,36%` / `11,66%`; BDI `$3.255,00`; EUR/USD `$1,20` | identical |
| 2022 W01 (US) | `$78.96` / `4.40%` / `10.68%`; soybeans `$1,398.34` | identical |
| 2024 w32 (EU) | `76,19` / `-0,16%` / `-8,82%`; Gold `2463,3`; Aluminium `2274` | identical |
| 2025 W29 (EU) | BDI `2.030` 38,57% 15,93%; BCI `3.021`; BHSI `670`; Fujairah `$399 $510 $738` | identical |
| 2026 W23 (EU) | `92,85`; Gold `4.492,82`; Copper `13.932,00`; BDI `3.037` | identical |

**Render-and-look substitute** (no vision tool in this session, stated plainly):
page rendered at dpi=115 and each checked value's bbox pixel-tested - dark-pixel
fraction **0.120-0.145** inside the value boxes against **0.000** in genuinely
empty regions (left margin x40-90, right gap x800-830). The values are printed
exactly where the text layer says they are. (A first reference strip scored 0.09
and turned out to contain the letterhead - a bad control reads like a pass.)

## The one caveat, disclosed rather than hidden

3 values are unaccounted for in the entire corpus, all the same artefact: a bare
`1.` at x=54 on page 2 of `2021_W35`, `2022_W08` and `2022_W16`. It is a note
marker, not a data cell, and it is reported per document in the run state. It is
left in place rather than filtered out, so the count stays honest.

## The number-convention switch (the trap this source hides)

Agora writes the same field two ways in different eras, measured per document on
a semantic anchor (Crude Oil/Brent/Gas Oil/Gold/Copper "Actual last" is
USD/barrel with 2 decimals, so its separator is decisive):

| era | docs | convention | page text |
|---|---|---|---|
| 2021 W25 - 2022 W26 | 25 + 26 | **US** | `$78.96`, `4.40%`, `$1,398.34` |
| 2022 W43 - 2026 W36 | 10 + 50 + 38 + 35 + 28 | **EU** | `92,85`, `-2,07%`, `4.492,82` |

2022 W27-W42 are absent from the corpus, so the switch week is bracketed to that
gap (US at W26, EU at W43). Reading `92,85` as 9285 is a 100x error in the
plausible direction, and it is exactly what a single year-level rule would have
produced for 2022. The declared convention is recorded in every `.md` header and
in `convention_info` of every `.tables.json`.

## Layout defects found and fixed (each one measured, not guessed)

1. **Header-to-section binding.** A header group was bound to the nearest title
   in x. On 2021 W33 the STOCK MARKETS header sat nearer the USD LIBOR title, so
   all 8 stock rows were filed under USD LIBOR. Fixed with a score of
   x-gap + 3 x y-gap, plus a rule that a title to the right of a group's last
   column belongs to another table (10-YEAR BOND's title is 59 pt right of STOCK
   MARKETS' columns and won the old score).
2. **A table that continues onto the next page with no header repeated** (12
   docs; 2021 W33 puts the USD/TRY row of EXCHANGE RATE at the top of page 2 with
   the header left on page 1). Fixed by carrying the previous page's BOTTOM-band
   column layout forward - which also required not carrying the whole page, or a
   second carried table stole the row's values.
3. **A span carrying two values** (`$1.183   $1.584` in one span on the 2026
   Fujairah row) - values are read at WORD level.
4. **A label containing a value-shaped number** (`BCI T/C - 182.000 dwt` =
   182,000 dwt) - labels are matched by vocabulary and never parsed as values.
5. **Rows closer than the label offset.** The 2026 BCI row's label sits 6.8 pt
   below a bunker row's baseline, so a page-wide y-cluster lost every Baltic
   label; rows are now clustered inside their own column group.
6. **A label boundary taken from the page, not a guess.** Using a fixed 60 pt
   offset dropped every bunker port name; the column's own header left edge is
   used instead.

## Deliverable

`.md` is the primary artefact: both data pages as markdown tables (COMMODITY
FUTURES, USD LIBOR, EXCHANGE RATE, STOCK MARKETS, 10-YEAR BOND, BUNKERS, BALTIC
EXCHANGE and its T/C block) plus the cover, notes and contact pages as text.
`.tables.json` is best-effort typed with the convention recorded. `.charts.json`
is empty with the reason recorded: **no chart layer exists** - all 1,557-1,575
drawings per document are zero-width fills (row shading) plus one stroked rule
per page, and the images are the logo. Source 7 of the source-by-source
programme: DONE.
