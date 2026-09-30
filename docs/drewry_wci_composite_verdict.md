# Drewry WCI: the composite was the publisher's YEAR-TO-DATE AVERAGE on 49 archived pages

Measured 2026-09-30, unattended run. No network spend: every number below comes from the
local Wayback cache (`scratch/wci/raw/`, 231 captures) and the publisher's own page text.

## The defect (found by reading a page, not by a metric)

`data/indices/drewry_wci_historical.csv` is fetched by `index.html`, so every value in it is
user-visible. Six of its 75 rows carried the wrong composite - and the wrong value was in the
**plausible** direction, so no count-based check could see it.

| date | displayed | the page prints | error |
|---|---|---|---|
| 2023-01-05 | 2135.0 | 2,135.16 | -0.01% |
| 2023-06-22 | 1822.0 | 1,535.75 | **+18.6%** |
| 2023-06-29 | 1809.0 | 1,494.46 | **+21.0%** |
| 2023-08-03 | 1770.0 | 1,761.33 | +0.5% |
| 2023-09-07 | 1769.0 | 1,680.73 | +5.3% |
| 2023-09-14 | 1763.0 | 1,561.30 | **+12.9%** |

Every wrong number is the publisher's own **year-to-date average**, printed two sentences after
the week's level:

    Drewry's composite World Container index increased 4.7% or $255 to $5,726.99 per 40ft container.
    The composite index increased 4.7% or $255 this week, and also, remains 285.4% higher ...
    The average composite index of the WCI, assessed by Drewry for year-to-date, is $5,143 per 40ft container ...

**Root cause, reproduced not guessed.** `COMPOSITE_PAT` bounded its gap with a period-free
character class (`[^.]{0,120}?`) - it forbade a PERIOD. So on every page whose change carries a
decimal ("increased **4.7%** or $255 to $5,726.99") the headline failed to match, the regex fell
through to the next sentence matching `composite index ... $N per 40ft`, and that sentence is the
year-to-date average.

**Scope, measured on all 228 cached pages with a parse (`scratch/wci/census_comp.py`):**
49 pages took the year-to-date average; 6 of them were in the displayed file; the rest (2021-2022)
were already withheld by the pre-2023 gate.

## The fix

The publisher always prints the level's unit right after the number, and the year-to-date sentence
is distinguished by WORDS, not by punctuation: the pattern's gap now allows periods, and the first
match whose preceding 90 characters contain no `average` / `year-to-date` / `ytd` wins.

### Independent control (page text only - no parser input, no pairing guesswork)

The LATER week's page prints both the % and the $ change from the week before, so
`level_new = level_old x (1 + pct/100)` and `level_new - level_old = printed $change`.
Over consecutive weekly prints (6-8 days apart), on the same 57-58 pairs:

| rule | printed % reproduced | printed $ change reproduced |
|---|---|---|
| before (the displayed values' rule) | 12/57 | 51/57 |
| after | 43/58 | **58/58** |

The 15 residual `%` misses are the control's own extractor: it takes the FIRST percent in the
sentence, which on some pages is the "remains 224% higher than a year ago" comparison. The `$`
change has no such ambiguity and is 58/58.

## Two further defects the fix exposed

1. **The contamination gate's 2-decimal tell was mis-scoped.** It tests every value for more than
   one decimal place ("a methodology number, not a printed level"). MEASURED on the pages: every
   ROUTE is a whole dollar ("$1,313 per 40ft box") while the composite is printed to 2 dp
   ("$1,535.75 per 40ft container"). Applying the tell to the composite dropped **12 real prints,
   all 12 with the 2 dp in the composite alone** (`scratch/wci/gate_probe.py`). Re-scoped to the
   route values.
2. **The checkpoint's `rotterdam_shanghai` cells were stale.** The displayed file held `5.0` on
   2023-06-29 and `16.0` on 2023-09-07 - the printed CHANGE, not the level. The page says
   "rates on Rotterdam - Shanghai inched up 1% or $5 **and stood at $575**" and "diminished 3% or
   $16 **and stood at $500**". The current parser returns 575 / 500 correctly; the displayed file
   predated that rule. Re-parse + re-stack corrected both.

## A gate added: FUSED PAIR

Two staged prints handed one lane another lane's level, and the pair is visible as two equal
values:

    2023-02-23  page: "On Shanghai - New York and Shanghai - Rotterdam, rates fell by 4% to
                $2,881 and $1,633 per feu, respectively"   ->  Rotterdam was given 2,881
    2023-09-21  page: "Shanghai - Genoa and Shanghai - Rotterdam dropped 10% or $167 and $127 to
                $1,531 and $1,172 per 40ft container"      ->  Rotterdam was given 1,531

MEASURED on the 76 staged prints: exactly 2 rows carry an equal tracked-route pair and BOTH are
these fusions. The stack now rejects such a row (census key `fused`); a wrong value is worse than
a missing one. **The lane rule for that shape is still open** - it is "k labels, 2k numbers where
the changes come first": `dropped 10% or $167 and $127 to $L1 and $L2`.

## Result

`data/indices/drewry_wci_historical.csv`: **75 -> 80 rows**, 2023-01-05 .. 2026-09-24.

* **8 cells corrected**: the 6 composites above + the 2 `rotterdam_shanghai` cells (575 / 500).
* **5 rows added** (2023-01-12, 2023-02-16, 2023-03-02, 2023-03-30, 2025-07-03).
* Staging `data/audit/drewry_wci_real_rows_from_wayback.csv`: 68 -> **74 gate-passing prints**
  (census: `incomplete` 107, `pre_era` 30, `numeric` 5, `contam` 0, `fused` 2, `fetch_failed` 1).
* Startup gates: 0 duplicate dates, 0 fused pairs, 0 rows whose composite equals a route value.
* **Every displayed value reconciled against its OWN page: 408/408 = 100.00%**
  (`scratch/wci/final_verify.py`; the one initial miss was the publisher printing `$7827` with no
  thousands comma on 2024-06-27, not a wrong value).
* The publisher-markdown tier keeps authority for dates >= 2026-08-01: 2026-09-03, 2026-09-10 and
  2026-09-24 were left untouched; the staged 2026-08-06 print was skipped because it is the same
  week as the displayed 2026-07-30 print.

## Withheld, stated not implied

* **2021-2022 (30 complete records) is still withheld**, and `--era-from` CANNOT reach it: a hard
  `page_date < 2023-01-01` cut sits above the era gate. MEASURED: `--era-from 2021-01-01` still
  yields 2023-01-05..2026-09-24 with `pre_era` 30, and produces a byte-identical stage.
  Next run: trial those 30 against their pages, then remove the hard cut.
  Starting evidence that the trial will now go better: the 2021-2022 pages carry the full route
  prose (so the parser's route layer is fine - 4/4 correct on the two pages read by eye), and the
  composite on those pages was the SAME year-to-date-average defect, now fixed.
* **Pre-trial of the 2021-2022 era, run AFTER the fix (measurement only, nothing shipped):**
  68 cached pre-2023 prints; on 45 consecutive-week pairs the printed $ change is reproduced
  **45/45** and the printed % **43/45**, and every value of the first 40 pre-2023 prints appears
  verbatim on its own page (0 missing) - `scratch/wci/era2021_ctl.py`. For comparison the same
  control on the 2023+ prints is 56/56 and 49/56. That is the trial's precondition met, not the
  trial: the 30 gate-passing records still need their lane values read against the pages.
* 107 snapshots parse without all five core values (the publisher printed only the composite, or
  only a route subset, that week) and 5 fail the numeric spread gate.
* 1 snapshot failed to fetch.

## Files

* `scripts/scrapers/fetch_drewry_wci.py` - composite anchor + average exclusion.
* `scripts/scrapers/backfill_wci_history.py` - `PARSER_VERSION` 5 -> 7, 2 dp tell re-scoped to
  routes, `fused` gate.
* Probes (gitignored, on disk for the next run): `scratch/wci/census_comp.py`, `census_lanes.py`,
  `blast.py`, `weekctl2.py`, `gate_probe.py`, `merge_display.py`, `final_verify.py`,
  `final_control.py`.

**Lesson, the same one as the 138 fabricated rows:** a scraper that reads PROSE needs the same
content anchor as a PDF extractor. "Nearest to the label" was not enough here - the publisher
prints two different composite-like numbers in the same paragraph, and only the unit and the word
"average" separate them. And a plausible wrong number is invisible to every count-based check:
145 well-formed rows and a valid CSV looked perfectly healthy.
