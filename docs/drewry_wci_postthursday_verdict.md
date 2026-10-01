# Drewry WCI — the backfill never took the week's OWN print (pv18 + post-Thursday candidates)

Measured 2026-10-01, unattended run. Branch `auto/extract-fixes-2026-10-01-wci-postthu`.
**Displayed series: 121 -> 135 rows. CELL CORRECTIONS 0, ROWS ADDED 14.**

## The defect, and how it was seen

`backfill_wci_history.one_per_week()` keeps the **earliest capture of each ISO week**.
The WCI assessment is published **ON Thursday**, so a Mon-Wed capture shows the
**previous** week's assessment — and the week's own print, although the archive holds
it, was **never fetched**. Seen by eye, not by a metric, on 2022-W02:

| capture | the page's own sentence | parsed page_date |
|---|---|---|
| `20220112103127` (Wed 12 Jan, the earliest of W02 — the one that WAS taken) | "Our detailed assessment for **Thursday, 6 January 2022**" | 2022-01-06 |
| `20220114134343` (Fri 14 Jan, **never fetched**) | "Our detailed assessment for **Thursday, 13 January 2022**" | **2022-01-13** |

The same shape explains the earlier "90 incomplete captures": a week whose earliest
capture predates publication has no capture of its own print at all.

## The archive-side enumeration (CDX was down; timemap worked)

`https://web.archive.org/cdx/search/cdx` returned **HTTP 503 "Internet Archive:
Temporarily Offline"** (the 503 body is an HTML page, 11,832 bytes) for every pattern,
while `/wayback/available`, a snapshot fetch and `archive.org/` all returned 200. The
definitive capture list came from **`https://web.archive.org/web/timemap/json/<exact url>`**:
**1,053 rows, 1,033 status-200, 252 distinct ISO weeks, 2017-06-16 .. 2026-09-27**.

Gap measured against the checkpoint (231 captures / 231 ISO weeks):

* timemap weeks the checkpoint does not hold: **23** — **all of them 2017-2020**
  (2017:2 2018:1 2019:6 2020:14). **Zero in the displayed era.** The era gap is
  archive-side for this URL, exactly as the previous run concluded.
* Of the **280 Thursdays** in the displayed era: **187** had a page_date, **93** did not;
  of those 93, **60** sit in an ISO week the archive DOES hold a capture for.

## The fix (two parts, both measured)

**1. `candidates()` — two snapshots per ISO week instead of one.** The earliest capture
(unchanged) PLUS the earliest capture in `(that week's Thursday 12:00, +7 days]`, which
is the capture that carries the week's own print. Bounded: 231 -> **384** snapshots.
Trial over the 93 no-page_date Thursdays (22 network fetches, the rest already cached):
**32 printed the target Thursday, 16 of them complete**.

**2. `pv18` STABILITY GUARD** (`fetch_drewry_wci.extract_assessments`). A tracked lane the
page prints as "remained stable" (no level, no `$`) is no longer handed **another lane's**
level by the `respectively`/ordinal logic. It fires only when **every** mention of that
lane on the page is a stability mention with no `$` in its own clause, so
"*remained stable at $6,818*" (a real print) is untouched.

CONTROL — all **274** cached pages parsed with the pre-pv18 module and with the patched
module: **0 parser errors, exactly 2 values moved**, both of them a lane the page prints
with no level:

| page | column | before | after | the page says |
|---|---|---|---|---|
| 2024-12-05 | `shanghai_ny` | 2649 | **None** | "*...Rotterdam to Shanghai and Rotterdam to New York reduced 1% to $514 and $2,649 ... whereas those from Los Angeles to Shanghai and Shanghai to New York **remained stable**.*" `2,649` occurs **once** in the whole page and belongs to **Rotterdam-New York**. |
| 2025-03-06 | `shanghai_genoa` | 845 | **None** | the known publisher-blank; 845 is New York-Rotterdam's level (already withheld by the numeric gate, now actually correct). |

## The run (resumable, cached; no API spend)

`backfill_wci_history.py --fetch --refresh` -> **384 snapshots, 226 complete prints**,
**15 fetch failures** (WinError 10061, archive.org throttling) left for a later resume,
0 parser errors.
`--stack --era-from 2021-01-01` -> staged prints **120 -> 135**;
census `{"snapshots": 384, "fetch_failed": 15, "incomplete": 143, "pre_era": 0,
"numeric": 1, "composite": 0, "contam": 0, "fused": 0, "withheld": 0}` — the single
`numeric` rejection is the 2024-12-05 print, now correctly 4-of-5 instead of 5-of-5 with
one wrong lane.

**Every value of the 15 new rows was reconciled against its own archived page**: each
level appears **inside its own lane's clause** (symmetric window + destination-only form
such as "*those to Genoa edged up 1% to $3,075*") — **15 clean, 0 misassigned, 0 without
page text**; 12 of the 15 were also read sentence-by-sentence by eye, and all 15
composites are printed verbatim (`$9,817.72`, `$1,806.43`, `$1,768.33`, then whole dollars).

`merge_display.py`: **CELL CORRECTIONS 0**, **ROWS ADDED 14**, md-tier rows
(2026-08-06, 08-20, 09-03, 09-10, 09-24) untouched, `2026-08-27` skipped as same-week as an
md print. The displayed file diff is **exactly 14 added lines, 0 removed**.

VERIFIED after the merge: **135 rows**, dates unique and strictly increasing, **all
Thursdays**, 2021-05-20 .. 2026-09-24, **0 blank core cells**, 63 blank `rotterdam_shanghai`
(the publisher's own blanks). `pytest tests/test_drewry_wci_contract.py
tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **38 passed**
(Python 3.12). `data/provenance/manifest.json` regenerated **after** pytest
(`indices_drewry_wci_historical` `row_count` **121 -> 135**; the only other lines that moved
are 4 unrelated `last_fetched_utc` ticks from other pipelines).

## The 15 failed fetches were retried inside the same run

A second `--fetch --refresh` took all **15** (0 remaining): **6 of them are COMPLETE prints** -
but every one of those 6 prints a Thursday that already had a row, so the STAGE stayed at
**135 rows** (`fetch_failed` 15 -> 1, `incomplete` 143 -> 151). The only stage movement is
**5 rows whose `source_snapshot` becomes the print's own capture** (2024-02-22
`20240226152424` -> `20240222191835`, 2024-02-29, 2024-04-04, 2024-09-26, 2026-03-05) -
provenance only, **values identical on every row** (`merge_display.py` re-run: 0 cell
corrections, 0 rows added against the already-merged 135).

## Still open (measured, not fixed)
* **33 era Thursdays have NO archived capture in their own ISO week** and 17 more have only
  pre-Thursday captures: archive-side, unfixable by any parser change for this URL.
* The two wildcard patterns (`*world-container-index*`, `*container-index*`) remain
  unchecked because the CDX endpoint is offline; the timemap endpoint only enumerates an
  **exact** URL.

## Reproduce

```
scratch/wci/timemap_probe.py          # timemap -> the definitive capture list
scratch/wci/tm_gap3.py                # per-Thursday classification of the gap
scratch/wci/look_case.py              # the by-eye 2022-W02 control
scratch/wci/trial_window.py           # the 93-Thursday trial (22 fetches)
scratch/wci/pv18_measure.py           # old vs new parser over all cached pages
scratch/wci/verify_new_rows.py        # per-lane reconciliation of the 15 new rows
scripts/scrapers/backfill_wci_history.py --fetch --refresh
scripts/scrapers/backfill_wci_history.py --stack --era-from 2021-01-01
scratch/wci/merge_display.py --apply
```

## Note on branches

The repo's **own automation** committed the two patched scrapers to **`main`** as
`f6a980a71` (it runs `git add -A` + commit + `pull --rebase origin main`) before this run
could branch; measured from `git log --name-only f6a980a71` and the reflog. The **data**
changes are committed on `auto/extract-fixes-2026-10-01-wci-postthu`. Nothing was pushed
and no merge was performed by this run.
