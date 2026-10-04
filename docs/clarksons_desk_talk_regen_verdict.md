# Clarksons Desk Talk - data regeneration of the furniture fix (HUMAN DECISION #1, taken)

Run: 2026-10-03 13:38 local (HOURLY SUPERVISOR 345bc8db9233). Branch untouched; nothing committed.

## Why this and not something else

The box had no extraction process. The live sibling is the 30m `source-by-source` job
(running since 13:28:44, actively rewriting `agora_indicators_series.csv` at 13:39:18 and
13:43:01), so agora and the intermodal thread are its work. The parked item with a measured
expectation and no owner was human decision #1: the committed fix `abee30d58` removed page
furniture in code, but the delivered files were deliberately left carrying it.

## Command and cost

    python3 scripts/extract/publishers/run_clarksons_hellas_world_class.py

Reads `data/extracted/cache_clarksons_hellas/*.md` (cache-only, NO API spend). 15.0 s,
165 reports parsed, 0 failures. Writes 4 clarksons series CSVs + regenerates the md sidecars in
`data/extracted/md/hellenic/shipbuilding/clarksons/**` and `data/extracted/md/clarksons/**`.

## Result (the delivered artefact of record)

| metric | before | after |
|---|---|---|
| `clarksons_desk_talk_series.csv` rows | 608 | **355** |
| duplicate keys (key = every column except source_file) | 17 | **0** |
| rows matching the fix's furniture predicate | 273 | **0** |
| bare-date-only rows | - | **0** |
| distinct source_file | 165 | 165 |
| distinct issue_date | 165 | 165 |
| md5 | 8f76077ad786a50028d5d698a4100206 | ee3256c2bd168a1764bb0ab176f39af8 |

sectors retained: Demolition 130, Newbuilding 128, Tankers 39, Dry Bulk 33, General 22, Desk Talk 3.
sales 1,329 / demolition 70 / macro 165 rows, each 0 duplicate keys.

## Controls

1. **Fleet-wide md5 control, 170 series CSVs, pre/post my run.** Exactly one file changed that my
   run wrote: `clarksons_desk_talk_series.csv`. `agora_indicators_series.csv` also differs from my
   pre-snapshot, but its mtimes are 13:39:18 and 13:43:01 - AFTER my run's writes (13:38:55) - and
   the clarksons runner has no agora write path (verified by reading every `open(...)`/`.write*` in
   it). That diff is the live sibling's, not mine.
2. **Old-vs-new in memory, same 165 cached reports** (`scratch/clarksons_regen/control_old_vs_new.py`,
   loading the pre-fix runner from `git show abee30d58^:` and the current one):
   sales differing docs **0**, demolitions **0**, macro **0**. Commentary 608 -> 355: 333 dropped,
   80 added; **68 of the 80 additions are verbatim substrings of the old rows** (re-segmentation, not
   new content) and 12 are genuine commentary the old code never emitted at all
   (e.g. "Speculative Thrill! With China implementing new lockdown regulations...").
3. **The 333 dropped rows.** 286 match the furniture predicate; the other 47 are date-only lines
   ("**06 August 2021**"), which the fix drops by design. 0 remaining in the delivered file.
4. **md tier.** 690 md-sidecar files across the two roots: **0 added, 0 removed**. Regenerating md from
   the old parse vs the new parse for every report (`control_mdtier.py`): the generator code is
   byte-identical and **0 table rows were added or removed** - the md diff is confined to commentary
   lines. 263 report pairs changed on disk, more than the 131 the fix explains: the md tier was stale
   beyond the fix (intermediate parser improvements never re-written). 0 table rows moved, so the
   regeneration is content-safe.

## Residual found (new, measured - a DIFFERENT class, not fixed here)

**17 of the 355 delivered rows still carry sales-table text fused into `commentary_text`.**
Average delivered row length is 1,037 chars; the longest three are 3,259 / 3,454 / 4,180 chars and the
4,180-char one begins `NISSOS ANTIPAROS 2019 HYUNDAI HEAVY ULSAN WARTSILA WINGD 7X82-B Scrubber &
BWTS fitted NISSOS SANTORINI ...` before the real sentence. This is **pre-existing, not introduced**:
68 of the 80 changed rows are re-segmented old text, i.e. the old blocks carried the same fusion.
Not fixed here - it needs its own measured page-level diagnosis, and the fix is commentary-parsing,
which is not this run's mandate.

## Register - NOT synced here, deliberately

`data/extracted/EXTRACTION_REGISTER.{json,md}` were last written 12:35 and still list
`clarksons_desk_talk_series.csv` at **608** rows. Expected delta: 608 -> 355, series total
594,263 -> 594,010 logical rows (170 CSVs). The sync was **not** run: the live sibling was rewriting
`agora_indicators_series.csv` (13:39:18, 13:43:01) and two agents writing the register at once can
record a transient count. **Next run must run** `scripts/sync_extraction_register.py` then
`scripts/extract/verify_registers.py` (expect 0 mismatches) - the sibling's own sync will pick the
clarksons 355 up automatically, since the register reads disk truth.

## Session limitation, stated

No image/vision tool in this session. Ground truth was substituted with same-document content
controls (per-document old-vs-new parse comparison, the fix's own furniture predicate, table-row
diffs on the md), not with a rendered-page look.

## Side finding: 353 breakwave PDFs are filed inside the hellenic/shipbuilding tree

While checking the runner's skips: `corpus/02-hellenic/shipbuilding/pdfs` (the Clarksons PDF root)
holds **347 unique PDFs of which 182 are breakwave-named** and are skipped with only a WARNING line
("Cache missing"), because no clarksons cache exists for them. Not a clarksons loss - but worth
measuring before anyone calls it one.

| root | breakwave-named PDFs | byte-twin of a `corpus/03-breakwave` file | not held by content |
|---|---|---|---|
| `corpus/03-breakwave` | 304 (299 distinct md5) | - | - |
| `corpus/02-hellenic/shipbuilding/pdfs` | 353 | 333 | 20 |
| `corpus/02-hellenic/shipbuilding/breakwave_pdfs` | 351 | 331 | 20 |

The 20 are the SAME 10 documents x 2 copies. Of those 10 dates, **7 already have rows in
`breakwave_fundamentals_series.csv`** (2022-08-30, 2023-07-11, 2023-11-14, 2024-02-13, 2024-10-01,
2025-01-14, 2026-04-07, 8-10 rows each) and 3 do not (2022-06-30, 2022-11-01, 2025-03-26); all three
appear in `breakwave_insights_metadata.csv`. The breakwave runners read ONLY
`corpus/03-breakwave/{drybulk,tankers}/**`, so these copies cannot be double-ingested.

**Verdict: duplicate collection residue, not a coverage gap.** Worth at most a 3-document page
spot-check; do not build anything. Evidence: `scratch/clarksons_regen/{breakwave_twin_check.py,
breakwave_orphans.json,breakwave_dupes.py}`.
