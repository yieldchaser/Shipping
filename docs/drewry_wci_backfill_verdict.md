# Drewry WCI: the Wayback history backfill, trialed and shipped

Measured 2026-09-29 on this box. Source: the publisher's own archived pages
(231 weekly captures, 2021-2026) plus the publisher's markdown tier already in
`corpus/06-drewry/opinions/2026/`. No paid API was used.

`data/indices/drewry_wci_historical.csv` (the file `index.html` fetches at line
18908 as `DATA.drewry_wci`) goes **17 rows -> 75 rows**, 2023-01-05 .. 2026-09-24.

## 1. The recorded diagnosis was wrong - the defect is SENTENCE scope

OVERNIGHT_STATE said *"`assign_route_values()` assigns each route to the first
line that mentions it, so a stray earlier mention blocks the correct later
assignment"*, and prescribed "make the assignment global across lines".

Reproduced against the archived 2024-04-18 page: the whole assessment is **ONE
text line**, so no line-scoping change could have mattered. The real bug was
that the `respectively` rule paired the k-th label with the k-th `$` across a
**multi-sentence paragraph**:

> "...from Shanghai to New York decreased 5% or $257 to $4,453 ... Shanghai to
> Los Angeles dropped 4% or $147 to $3,487 ... **Likewise, rates on Shanghai to
> Rotterdam and Shanghai to Genoa declined 2% to $2,989 and $3,577 per feu
> respectively.** Conversely, rates from Rotterdam to New York increased by 3%
> or $67 to $2,291 per 40ft container."

Inside its own sentence the list is 2 labels / 2 values and unambiguous;
across the paragraph Genoa was handed the $2,291 that belongs to
Rotterdam-New York, and Rotterdam-Shanghai the $708 of Los Angeles-Shanghai.
Fix: assign inside the sentence. 2024-04-18 then reads 2719 / R 2989 / G 3577 /
LA 3487 / NY 4453 with Rotterdam-Shanghai correctly NULL ("remained stable").

## 2. The trial found three more shapes, each on a real archived page

| page | what the publisher prints | what the parser gave | fix |
|---|---|---|---|
| 2024-04-25 | "from **Rotterdam to New York** and Shanghai to Los Angeles decreased 3% to $2,214 and **$3,395** respectively" | LA 2214 | ordinal over **every** lane named, not only the tracked ones: an untracked lane still consumes its slot |
| 2026-03-05 | "Shanghai to Los Angeles increased 10% to **$2,402**, while those on Shanghai to New York increased 7% to **$2,977**" | LA 2977 / NY 2402 (swapped) | clause-local pairing (one clause, one lane, one level) |
| 2026-07-30 | "declined 6% to **$5,630** per 40ft container from Shanghai to Genoa and decreased 3% to **$4,677** ... on Shanghai to Rotterdam" | G 4677 / R 5630 (swapped) | same - distance alone had crossed the clause boundary |
| 2025-01-30 | "...reduced 2% or $46 to $2,732 ... followed by rates from Shanghai to New York and Shanghai to Los Angeles, which decreased 1% to **$6,288** and **$4,771** ... respectively" | LA 6288 / NY 2732 | ordinal, with the pool = values introduced by "to/at/reach" (the level, never the "or $X" change) |
| 2023-09-07 | "Rates on Rotterdam - Shanghai diminished 3% or $16 **and stood at $500**" | RS 16 | a clause carrying only the CHANGE takes its LEVEL from the next lane-less clause |
| 2023-09-14 | "rates on Shanghai - Rotterdam and Shanghai - Genoa decreased by 10% to $1,299 and $1,698 ... respectively" | R 1299 and G 1299 | lane lists separated by an EN DASH, not "to", must also be enumerated |

The clause boundaries are not invented: a census over all 231 cached pages
(`scratch/wci/census_shapes.py`) measured **75** multi-lane sentences of the
"one clause per lane" shape, **34+3** parallel lane-then-value lists and **10**
`respectively` lists whose lanes and values interleave.

## 3. Verification (all measured, none asserted)

1. **Publisher markdown control, 40/40 route values.** The 8 WCI snapshots the
   publisher itself published in `corpus/06-drewry/opinions/2026/` carry a
   route/value table. Running the patched extractor over that markdown
   reproduces **40 of 40** printed values (`scratch/wci/check_md_control.py`).
   This is the regression gate: it read 40/40 before the four fixes and 40/40
   after, so the 2026 era did not move.
2. **Page trials, 7/7 exact.** Every defect above, plus 2024-04-18, read back
   value-for-value against the archived page it came from.
3. **Independent % control, 127/128 = 99.22%.** The publisher prints each lane's
   % change verbatim. Two parses from adjacent archived weeks imply a change; if
   the parser is right it reproduces the % the PUBLISHER printed - a different
   number, from a different week's document, matched in the lane's own clause
   (`scratch/wci/verify_pct.py`). Start to finish this went **87.5% -> 99.2%**.
   The 3 residual flags (2023-12-21 LA, 2025-01-30 NY, 2025-03-27 R) are lanes
   whose clause prints only a lane list and no %; their implied changes are
   1.2-5.8% and 2025-03-27 was read back by eye ("decreased 4% to $2,370 and
   $3,622 ... respectively" -> parsed 2370 / 3622, correct).
4. **Gate census on the shipped set:** 231 snapshots, 1 fetch failure, 109
   without all five values, 30 pre-2023, 6 numeric-gate, 0 composite-gate,
   5 contamination-gate, **68 shipped**.
5. **Displayed artefact checks:** 75 rows, dates sorted, 0 duplicate dates,
   0 rows with `shanghai_rotterdam == shanghai_genoa` (the 2026-09 fused
   signature), 0 rows where composite equals a route value, 0 two-decimal
   values, and the 8 markdown-tier rows >= 2026-08-01 byte-identical.
6. **The 10 rows already committed are byte-identical**; the staged set is a
   strict superset (10 -> 17 -> 68 rows as each parser fix landed).

## 4. What shipped, and the one correction

`data/indices/drewry_wci_historical.csv`: **17 -> 75 rows** (+58 dates), one
correction (`scratch/wci/merge_display.py` prints every conflict):

| date | column | was | now | why |
|---|---|---|---|---|
| 2026-07-30 | shanghai_rotterdam / shanghai_genoa | 5630 / 4677 | 4677 / 5630 | the clause-scope defect; the page prints 6% -> $5,630 from Shanghai to Genoa and 3% -> $4,677 on Shanghai to Rotterdam |

Staging file `data/audit/drewry_wci_real_rows_from_wayback.csv` now holds all 68.

## 5. What is deliberately NOT shipped

* **2021-2022 (30 records with all five values).** Their prose era was never
  trialed and does not parse: 2021 captures yield a route value of 78 or a
  composite equal to a route. They stay behind the hard pre-2023 gate. This is
  the honest choice - a wrong value is worse than a missing one.
* **1 snapshot with a fetch error, 109 without all five values.** Most archive
  captures of that era are bot-wall or truncated pages.
* **Coverage gaps are the ARCHIVE's, not the parser's:** 231 archived weekly
  captures exist for 2021-2026 (~38/year, not 52), so the 75 rows carry five
  gaps > 45 days (2023-01-19 -> 06-22 154d, 2025-05-08 -> 07-10 63d,
  2025-07-10 -> 09-25 77d, 2025-09-25 -> 2026-01-08 105d,
  2026-03-12 -> 05-14 63d). Extending them means more Wayback collection, not
  more parsing. The live Drewry site still returns HTTP 429 from this box.

## 6. Tooling left behind (reusable)

`scripts/scrapers/backfill_wci_history.py`:
* `--fetch` resumable append-only JSONL checkpoint; `--refresh` re-parses every
  snapshot that has no good record from the CURRENT `PARSER_VERSION` (now 5);
* a **local HTML cache** in `scratch/wci/raw/` (231 files): a parser change
  re-parses the whole archive offline in ~20 s instead of re-fetching;
* retry-with-backoff on the fetch (Wayback refused connections - WinError 10061
  - when hit at 0.5 s intervals, and the run wrote 74 error records);
* **an error record can never beat a parse**: `do_stack` keeps the last record
  that HAS values, so a failed re-fetch cannot erase the parse it replaced
  (this had already silently clobbered 22 good parses mid-run);
* `--era-from YYYY-MM-DD` makes the display gate explicit and auditable.

`scripts/scrapers/fetch_drewry_wci.py`: four measured rules (sentence scope,
ordinal over untracked lanes, clause scope, level-in-next-clause) and
`to_rx` extended to `to|at|reach` because this publisher writes "to reach
$11,173" and "held steady at $7,904" as well as "to $4,453".

## 7. Traps that cost time here (do not relearn)

* **A backslash written through the tool's JSON transport arrives folded.**
  Building replacement text inside a patch script produced a literal
  **backspace byte** for `\b` and silently disabled `label_rx` - the regex
  matched nothing and the code still ran. Build such edits with `chr(92)` and
  assert `b.count(chr(8)) == 0` on the written file.
* **A heredoc over ~5 KB silently breaks the shell.** Write the block in two
  `cat >` / `cat >>` chunks.
* **A fix you wrote is not a fix you ran.** After every patch: re-run the
  control BEFORE and AFTER, on the SAME document that was rendered.
* **The verifier is code too.** Two of its seven "mismatches" were its own
  clause-crossing % picker, and tightening it moved the number 99.2 -> 97.7 ->
  99.2. Attribute every flag to a page before believing it.
