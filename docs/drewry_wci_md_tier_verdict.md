# Drewry WCI MARKDOWN tier repaired: print date + the fused lane values (2026-09-30)

`docs/drewry_wci_date_key_verdict.md` closed the displayed **CSV**
(`data/indices/drewry_wci_historical.csv`, 105 rows) and named one item as left
open: *"the 9 corpus md files for 2026 carry the PRE-FIX fused table ... The CSV
is repaired; the md tier (which feeds the knowledge chunks) is not."* This run
fixes that tier.

## The defect (measured on the files as found)

Population: **every `_drewry_wci.md` in the corpus - 9 files, all in
`corpus/06-drewry/opinions/2026/`** (the WCI md tier holds no other year).

| measure | before |
|---|---|
| `shanghai_rotterdam == shanghai_genoa` | **9 / 9** |
| `shanghai_la == shanghai_ny` | **7 / 9** |
| a lane left blank | **2 / 9** (`shanghai_la` in the 08-20 pair) |
| filename date == the print's own date | **0 / 9** - the file name is the RUN date |
| distinct prints held | **5** (2026-08-20, 09-03, 09-10, 09-17, 09-24) |

So the tier held **5 prints in 9 files** - the 3 Sep print 3x, the 17 Sep print
2x, the 20 Aug print 2x - each named by the day it was collected, and every one
of them carrying its neighbour lane's level (e.g. the 3 Sep file read
Rotterdam **4,368** / New York **7,185** where the page prints **4,092** and
**9,587**).

**Why it mattered rather than being cosmetic:** `scratch/wci/merge_display.py`
gives this tier **AUTHORITY for dates >= 2026-08-01** (`MD_CUTOFF`), so a
re-run of the display merge would have re-imported the fused numbers over the
repaired CSV.

## The fix

New `scripts/scrapers/repair_wci_md_tier.py` (committed). Per file:

1. **Print date** from the page's own phrase (`World Container Index - 03 Sep`),
   content-anchored, never a hard-coded map; it must be a **Thursday** 0-10 days
   before the file's own date and must be **unique** on the page.
2. **Values** from the repaired CSV row for that print date (the CSV's own 5
   values were verified verbatim on their pages in the earlier run).
3. Rewrite the frontmatter `date`, the H1 and the values table; then rename the
   file to the print's date. Files of the same print are collapsed to one **only
   after their bodies are proven identical** (date lines blanked and compared).

Applied: **9 files -> 5 files, 5 prints**, 4 duplicate files removed, 25 lines
changed in total (15 date/title lines + 10 value cells).

| file (before) | print (after) | value cells corrected |
|---|---|---|
| 2026-08-24 | **2026-08-20** | `shanghai_rotterdam` 4955 -> **4401**, `shanghai_la` blank -> **6802** |
| 2026-09-04 | **2026-09-03** | `shanghai_rotterdam` 4368 -> **4092**, `shanghai_ny` 7185 -> **9587** |
| 2026-09-06, 09-07 | (dropped - identical body to the kept 09-03 file) | |
| 2026-09-11 | **2026-09-10** | `shanghai_rotterdam` 4216 -> **3997**, `shanghai_ny` 7352 -> **9726** |
| 2026-09-18 | **2026-09-17** | `shanghai_rotterdam` 4016 -> **3626**, `shanghai_ny` 7712 -> **10394** |
| 2026-09-20 | (dropped - identical body to the kept 09-17 file) | |
| 2026-08-25 | (dropped - identical body to the kept 08-20 file) | |
| 2026-09-25 | **2026-09-24** | `shanghai_rotterdam` 3835 -> **3485**, `shanghai_ny` 7838 -> **10373** |

## Controls (each measured, after the change)

* **PROSE WITNESS - the page's own words.** Every one of the 5 values is printed
  verbatim in the file's OWN commentary prose (written from the page, untouched
  by this repair): `$4,465` / `$4,092` / `$4,368` / `$7,185` / `$9,587` for the
  3 Sep print, etc. **5/5 files, 5/5 values each.** This is the witness that
  caught the defect family in the first place: both fused numbers WERE on the
  page, so a recall check could not see them.
* **NOTHING ELSE CHANGED - git HEAD as the before-witness** (independent
  verifier `scratch/wcimd/verify_md_tier.py`, does not reuse the repair code):
  exactly **5 lines differ** per file (3 date lines + 2 value cells);
  the commentary is **byte-identical to HEAD in 5/5**.
* **TABLE == CSV**: 5/5 files, every key, after the repair.
* **NAME == the page's own phrase, and a Thursday**: 5/5; **0 duplicate prints**.
* **IDEMPOTENT**: a second run reports `0` value cells changed and writes
  nothing; the repaired files are a fixed point.
* **THIRD WITNESS (where a capture is held)** - re-parsing
  `scratch/wci/raw/*.html` with the CURRENT `extract_assessments()`:
  the 09-03 (20260906154018), 09-10 (20260911023308) and 09-24 (20260927090016)
  captures reproduce the repaired five values **exactly**; the 08-20 captures
  (`20260820134100`, `20260824120054`) reproduce 4/5 and leave `shanghai_la`
  unparsed (see open item 1); no capture is held for the 09-17 print, which rests
  on CSV + its own prose (both agree: 3626 / 4016 / 7712 / 10394).

No network was used; no API spend. No vision tool in this session, so the
render-and-look step is substituted by the page's own prose + the page's own
printed date phrase + the cached-page re-parse above.

## Open, named (not fixed here)

1. **A parser RECALL gap, not a wrong value**: of the 26 cached 2026 capture
   pages, **8 leave at least one of the four lane values unparsed** (2025-12-25
   la+ny; 2026-02-12 la+ny; 03-26 rotterdam+la; 04-16 la in both captures;
   04-30 rotterdam; 08-20 la in both captures). Verified for the **08-20** print
   against its own prose, which prints the missing lane (`$6,802`): the value is
   on the page and the parser does not recover it. The displayed CSV has **0
   blank cells**, so this is a fallback-covered hole, not a displayed defect -
   but it is the same "second lane named after `and`" shape the parser already
   had to be taught once.
2. `upsert_wci_rows()` still dedupes by date only. With correct page dates that
   is sufficient; a Thursday assertion on the stored date would make this whole
   defect class unable to reappear silently.
3. Standing ledger items unchanged: 107 snapshots incomplete + 4 numeric-gated +
   1 fetch failure (all pre-2023, named in the stack's gate census), and the
   2021-07-01 "k labels, 2k numbers" lane shape.
