# drewry WCI - the 90 withheld captures are the PUBLISHER'S OWN BLANKS (verified by reading all 90)

Status: **CLOSED as NOT-A-DEFECT.** The ledger's last open drewry item was "90 incomplete
captures by year 2021:30 2022:19 2023:21 2024:11 2025:9" - i.e. a suspicion that our parser is
dropping lane levels the publisher printed. It is not. Every one of the 203 missing lane-slots
was read against the capture's own page.

Population the query covered: the checkpoint's **231 distinct captures**
(`data/extracted/wci_backfill/checkpoint.jsonl`, deduped by `ts`, latest record wins) and its
**231 cached HTML bodies** (`scratch/wci/raw/<ts>.html`, 18 MB). Nothing was re-fetched; the
whole audit is offline and read-only.

## Method

For every capture whose record is `complete == false`, its own cached page was re-parsed and its
assessment paragraph read. Each missing lane was classified by what the page does with it:

| class | rule | count |
|---|---|---|
| **STABLE_BLANK** | the sentence says `remain(ed) stable` / `hovered around previous week's level` / `declined 1% each` (no level) | **138** |
| **NAMED_NO_VALUE** | the lane is named with a percentage but no `$` level anywhere in its sentence | **14** |
| **UNNAMED** | the lane is not named in the assessment paragraph at all | **51** |
| **HAS_VALUE** | the lane is named AND a `$` level is printed for it | **0** |

So of 203 missing lane-slots across the 90 captures, **zero carry a level the parser dropped.**

Whole-page control (not just the paragraph): searching the *entire* flattened page for a `$`
within 140 characters after a lane mention returned **4 hits, all false positives** - in each the
`$` belongs to a following clause naming a DIFFERENT lane:

* `2021-09-09` (`shanghai_ny`): "...and New York to Rotterdam grew 1% each per 40ft box
  respectively. **However, rates from Rotterdam to Shanghai dropped 1% or $21 to $1,626**" - the
  `$1,626` is Rotterdam->Shanghai, and it IS in the record.
* `2021-10-14` (`shanghai_genoa`, `rotterdam_shanghai`): "...declined 1% respectively per 40ft
  container. **However, rates on New York to Rotterdam nudged up by 3% or $38**".

## The 8 captures with no lane level at all

8 captures record only the composite index. Four of them are **partial Wayback bodies** - the
snapshot holds the headline and one `$` (the composite) and no narrative at all
(`2021-01-21`, `2021-02-11`, `2021-03-18`, `2021-04-15`). The other four ARE full prints whose
publisher stated no lane level, e.g. `2022-05-19`: *"Rates on Shanghai - Rotterdam, Rotterdam -
Shanghai, Shanghai - Genoa, Shanghai - Los Angeles, Shanghai - New York, Rotterdam - New York and
New York - Rotterdam hovered around previous weeks level."* Verified by reading each.

## The 59 blank `rotterdam_shanghai` cells in the SHIPPED file

`data/indices/drewry_wci_historical.csv` (121 rows) is blank on `rotterdam_shanghai` for 59 rows,
2021-06-24 .. 2026-09-24. Measured against each row's own capture: **20 named with no level**
("hovered around previous weeks level", "declined 1% each"), **38 not named**, **1 capture date
absent from the cache**, and **0 with a printed level**. All five OTHER lanes are blank on **0**
rows. A blank here is faithful, and it is the reason the contract test (below) exempts this lane
from the no-blank rule.

## Continuity of the era, stated against the population that was measured

Era = the displayed range, 2021-05-20 .. 2026-09-24 = **280 Thursdays**:

| | count | by year |
|---|---|---|
| displayed in the CSV | **121** | |
| a capture IS held but the print is withheld (publisher-blank, or the 1 numeric-gated print) | **67** | 2021:20 2022:16 2023:15 2024:9 2025:7 |
| **no Wayback capture at all** | **92** | 2021:7 2022:16 2023:18 2024:15 2025:21 2026:15 |

The 92 are an ARCHIVE-side gap: Wayback holds no 200-status capture of the WCI page for those
weeks, so no parser change can fill them. Note the 2026:15 is partly an artefact of the merge
tier: rows dated >= 2026-08-01 come from the `corpus/06-drewry/opinions/**_drewry_wci.md` tier
(5 files), not from a snapshot.

## Shipped this run (code + test only, no data rewrite)

`scripts/scrapers/fetch_drewry_wci.py` - `upsert_wci_rows()` dedupes by DATE alone (last row
wins), so a misparsed date could overwrite a real print with no trace. It now reports every
merge: rows in/out, how many the date dedupe discarded, which dates had a **stored value
replaced** (with before -> after), and any date that is **not a Thursday** (the index is assessed
on Thursdays, so a non-Thursday date is a parse artefact). Printed as `[wci-upsert]` lines and
kept in module-level `UPSERT_REPORT`.

CONTROLS (all on a temp copy; the real CSV sha256 was identical before and after -
`de1aeea74e5503a5...`):

| control | result |
|---|---|
| re-upsert the file's own 121 rows | 242 in -> 121 out, 121 discarded, **0 shadowed**, 0 non-Thursday, output **byte-identical** to the input |
| mutate a stored value (`2026-09-24 shanghai_la 7838 -> 7949`) | reported: `[!] 1 date(s) had a STORED value REPLACED` with both values |
| add a non-Thursday date (`2021-05-21`) | reported: `[!] 1 row(s) are NOT a Thursday: ['2021-05-21']` |

NEW TEST `tests/test_drewry_wci_contract.py` (4 tests): canonical header, every date a Thursday,
dates unique and strictly increasing, the five core lanes never blank.
`pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py
tests/test_drewry_wci_contract.py` = **38 passed** (Python 3.12).

## Reproduce

```
PY=/c/Users/Dell/AppData/Local/Programs/Python/Python312/python.exe
$PY scratch/wci/read_incomplete.py      # re-parse all 231 cached bodies -> scratch/wci/incomplete_pages.json
$PY scratch/wci/classify3.py            # the 138 / 14 / 51 / 0 classification
$PY scratch/wci/incomplete_verdict.py   # the whole-page sweep + the low-dollar captures
$PY scratch/wci/rs_blank.py             # the 59 blank rotterdam_shanghai cells
$PY scratch/wci/continuity.py           # the 280-Thursday partition
$PY scratch/wci/ctl_upsert.py           # the 3 upsert controls
```

## CDX re-check: is the archive holding captures we never processed?

Asked and answered for the year that matters most. A year-scoped CDX query on the tool's own
pattern (`drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry*`,
2021, status 200, no digest collapse) returns **125 snapshots over 36 ISO weeks**; the checkpoint
holds **the same 36 ISO weeks** - **0 archived weeks are missing from it**. So the 89 snapshot
timestamps that are not in the checkpoint are extra captures INSIDE weeks we already have
(`backfill_wci_history.one_per_week()` deliberately keeps the earliest capture of each week),
not weeks we skipped.

The other two patterns in `WCI_WAYBACK_URL_PATTERNS` (`*world-container-index*`,
`*container-index*`) have NOT been checked: every attempt returned **HTTP 503** from
archive.org today (the wide queries are throttled; year-scoped ones are not). That is the one
remaining, bounded, archive-side check:

```
$PY -c "import sys;sys.path.insert(0,'scripts/scrapers');
from fetch_drewry_wci import fetch_wayback_cdx
print(len(fetch_wayback_cdx('drewry.co.uk/*world-container-index*', from_year=2021, limit=2000)))"
```

If those patterns DO hold captures in the 92 never-archived weeks, they would be fetched by the
existing resumable tool and would extend the series; nothing else here needs re-doing.

## Not actionable, do not re-chase

* The `2025-03-06` numeric-gated print is the publisher's own blank (Genoa "remained stable") -
  correctly withheld.
* The 92 never-archived Thursdays cannot be recovered from Wayback. `corpus/06-drewry/opinions/`
  holds only 5 WCI `.md` files (2026-08-20 .. 2026-09-24), so there is no corpus-side backfill
  path for the early years either.
* A full CDX re-enumeration (2021-2026, 3 URL patterns) is running to check whether the archive
  holds captures our checkpoint never processed; the one known example is `20210326142307`, which
  is NOT in the checkpoint.
