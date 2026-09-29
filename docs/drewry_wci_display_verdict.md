# Drewry WCI (displayed index) - REAL defect found and FIXED; parser root cause fixed

**Date:** 2026-09-29 (cron, unattended) · Branch `benchmark/extraction-comparison`
**Files:** `scripts/scrapers/fetch_drewry_wci.py` (parser) ·
`data/indices/drewry_wci_historical.csv` (the artefact `index.html` fetches)

## Why this was worked

`docs/OVERNIGHT_STATE.md` records xclusiv at 266/266 and every broker source CLOSED, and
`docs/EXTRACTION_REGISTER.md` marks all 27 publisher rows `CLOSED`. The ledger's last open item
(the residual ism agreement tail) was closed at 12:3x. The prompt's "next source" list is stale.
So this run went looking for a defect in an artefact that is actually **displayed**, and found one.

`data/indices/drewry_wci_historical.csv` is what the app renders (`grep index.html` ->
`fetch('data/indices/drewry_wci_historical.csv')`). It had **fused route columns**.

## The defect (user-visible)

On the 7 newest rows the two middle routes carried a neighbour's value:

| date | shanghai_rotterdam | shanghai_genoa | shanghai_la | shanghai_ny |
|---|---|---|---|---|
| 2026-09-18 (published) | **4016** | 4016 | 7712 | **7712** |
| 2026-09-18 (ground truth) | **3626** | 4016 | 7712 | **10394** |

`shanghai_rotterdam` == `shanghai_genoa` and `shanghai_ny` == `shanghai_la`. A chart drawn from
that file shows Rotterdam and Genoa as one line and LA and New York as one line.

Population: **7 of 145 rows** (2026-08-25, 09-04, 09-06, 09-07, 09-11, 09-18, 09-20), **14 cells**.
The older 138 rows are clean of this defect, and that is a proof, not a guess: the bug always
hands the *second* route named on a line the *first* route's value, so corruption always produces
`shanghai_rotterdam == shanghai_genoa`. Only those 7 rows show it.

## Root cause - the free-text fallback gave the first `$` on a line to every route on it

Reproduced against the publisher's own page (Wayback snapshot `20260912113125`, no live scrape -
the live page returned **HTTP 429**). The page carries no `<table>` at all: the assessments are in
**prose**, two routes per sentence:

```
On the Transpacific trade, rates from Shanghai to Los Angeles rose 2% to $7,352 per 40ft
container, while those from Shanghai to New York edged up 1% to $9,726 per 40ft container.

On the Asia-Europe trade route, rates from Shanghai to Genoa fell 3% to $4,216 per 40ft
container while they decreased 2% to $3,997 per 40ft container from Shanghai to Rotterdam.
```

The old fallback took `re.search(r"\$\s*([\d,]+...)")` - the **first** `$` on the line - for
*every* route whose label matched that line. So Rotterdam got Genoa's `$4,216` and New York got
Los Angeles' `$7,352`. Exactly the 14 wrong cells, and nothing else.

## The fix

`assign_route_values()`: every `$N` on the line is a candidate; a route label claims the `$N`
**nearest** it (max distance 120 chars), assigned greedily by distance so one number can be
claimed by at most one route. Content-anchored, no geometry, no fixed column.

Also fixed in the same function: the date parser. `%B` requires a full month name, so the page's
own `Our detailed assessment for Thursday, 10 Sep 2026` never matched and the regex fell through
to an unrelated date elsewhere on the page (`2026-09-29` for the 09-12 snapshot - a date from
nowhere near the assessment). It now anchors on `assessment for ... <D Mon YYYY>` first and
accepts `%d %b %Y`.

## Verification (measured, not asserted)

1. **Parser, against the publisher's own page.** Wayback snapshot `20260912113125`:

   | | composite | rotterdam | genoa | la | ny |
   |---|---|---|---|---|---|
   | before | 4476 | 4216 (Genoa's) | 4216 | 7352 | 7352 (LA's) |
   | after | 4476 | **3997** | 4216 | 7352 | **9726** |

   Every value now distinct and matching the prose sentence above, which the parser had read.
   Snapshot `20260927143251` -> composite 4468, rotterdam 3835, genoa 3485, la 7838, ny 10373;
   assessment date now parsed as `2026-09-24` (was 2026-09-29).

2. **Artefact, against the publisher's own markdown.** The 8 WCI snapshots in
   `corpus/06-drewry/opinions/2026/*wci*.md` are the publisher's own table. All 14 corrected
   cells: **14/14 verbatim** in their own source file (control = the printed `$N,NNN` string).
   2026-08-24 was already correct and was left untouched.

3. **After:** 145 rows (unchanged), `shanghai_rotterdam == shanghai_genoa` on **0** rows,
   `shanghai_la == shanghai_ny` on **0** rows, 0 blank cells.

4. **Scope:** the CSV diff is exactly 14 lines; no row added, removed or reordered.
   Reproduce: `python3 scratch/repair_wci_csv.py` (idempotent - a second run changes 0 cells).

## Still open (stated, not implied)

* The file is **one week stale**: the newest row is 2026-09-20, while the verified 2026-09-27
  snapshot exists. It was NOT added - adding a row is a collection job, and its date convention
  needs its own check.
* `drewry_wci_series.csv` (8 rows, md-derived) is the correct one and was already right; the two
  files disagree in origin (scraper vs markdown). They now agree on values.
* The scraper is **HTTP 429**-blocked on the live site from this box; it still works through
  Wayback, which is how this run reproduced and verified.
* The 138 rows older than 2026-08-25 have no ground truth in this repo, so they were not
  independently verified - but the defect's signature is absent from them (see population note).

## Lesson worth keeping

A **scraper** writing prose-derived numbers needs the same discipline as a PDF extractor: anchor
on content (the value nearest its label), never on position (the first number on the line). And
when an artefact is *displayed*, a plausible wrong number is invisible to every count-based check -
this one survived because 145 rows and a well-formed CSV both look healthy.
