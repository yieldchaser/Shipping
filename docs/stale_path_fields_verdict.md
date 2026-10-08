# Stale path fields in derived indexes: agora repointed (10,002 rows); the other kinds measured CLEAN

**Date:** 2026-10-08 16:4x · **Branch:** `auto/extract-fixes-2026-10-08` · job: unattended source-by-source (30m)

## Why this was looked at

The skill rule *"a path reference is THREE kinds, not one"* says a corpus migration must be swept for
**explicit path fields inside derived indexes** - not only for code imports, not only for content mentions.
The register gate cannot see this class: it compares row COUNTS of a CSV against itself.

## Sweep result (measured this run)

| artefact class | path-style values | unresolved | verdict |
|---|---|---|---|
| 180 `data/extracted/series/*_series.csv` + `data/derived/*.csv` | 72,676 | **10,048** | all in ONE file: `agora_indicators_series.csv` -> FIXED |
| all `.md` frontmatter under `data/extracted/md/` (29,065 files) | 14,506 | **0** | CLEAN |
| 121 tracked JSON indexes (`data/extracted/*.json`, `data/derived/*.json`, `corpus/_MANIFEST.json`) | 1,116 | **24** (3 files) | 7 fixed, 7 named, 10 untracked |

Bare-basename `source_file` values (489,493 across the series CSVs) are the deliberate house convention,
not a defect; only PATH-shaped values are reported above.

## Defect 1 - agora `source_file` pointed at the PRE-MIGRATION flat layout (FIXED)

`agora_indicators_series.csv` (10,049 rows) carried, on **10,002 rows / 213 distinct values**, the
pre-migration flat path (year partition missing):

```
before:  corpus/01-brokers/agora/agora_2021_W25_AGORA.-Week-25.-2021.-Snapshot-of-Commercial-Indicators.pdf   -> 404
after:   corpus/01-brokers/agora/2021/agora_2021_W25_AGORA.-Week-25.-2021.-Snapshot-of-Commercial-Indicators.pdf
```

The 47 newest rows (the W40 append of the 14:2x run, written by `stack_agora_weeks.py` through
`pdf.relative_to(ROOT)`) already used the correct form, so the file was internally inconsistent:
47 rows resolved, 10,002 did not.

**Fix - `scripts/extract/publishers/fix_agora_source_paths.py` (per-source, idempotent).** Preconditions,
all asserted before any write:
* every distinct stale value resolves to **exactly ONE** file in `corpus/01-brokers/agora` (219 files,
  **0** duplicate basenames) -> 213/213;
* the target YEAR DIRECTORY equals the `issue_date` year of the rows carrying it -> **0** mismatches;
* replacement is BYTE-LEVEL and the raw occurrence count equals the row count -> 213/213 equal
  (these filenames need no CSV quoting).

**Control after the write:** rows 10,049 -> **10,049** (unchanged); `source_file` rows rewritten
**10,002**; every other column byte-identical across all 10,049 rows; unresolved after = **0**; all
**214** distinct source docs still have an `.md`. EOL/BOM untouched (10,050 CRLF lines, no BOM).
Second run: *"stale path rows 0; idempotent: nothing stale, no write"*.

**Register gate after the fix:** `scripts/extract/verify_registers.py` = **ALL PASSED** -
180 CSVs / **641,107** logical rows == JSON == MD, 0 mismatches (values-only change, counts unmoved).
`git diff --numstat` = **10,002 changed lines, 0 added / 0 removed**. `index.html` references agora
**0** times, so nothing displayed changed - the gain is that consumers resolving the field no longer 404.

## Defect 2 - `data/derived/gold_standard_benchmark.json` (FIXED, 7 fields)

3 distinct stale values (the pre-migration `reports/shipbrokers/<pub>/<year>/...` prefix), 7 occurrences.
All 3 documents exist and resolve by UNIQUE basename: star_asia W35 and advanced_shipping W36 under
`corpus/01-brokers/...`; allied W07 2024 under `corpus/archive/allied/...`. Genealogy matters here - a
blanket `reports/shipbrokers/ -> corpus/01-brokers/` prefix rewrite would have produced a WRONG path for
allied, which is why the repair resolves by unique basename and asserts it rather than by prefix.

Repair tool: `scripts/verify/repoint_stale_path_fields.py` (explicit ledger, exact replacements,
occurrence-count assertions, idempotent). A stale path inside a BENCHMARK file is a measurement hazard:
ground truth that cannot be located shows up as a smaller benchmark, not as an error.

## Defect 3 - `data/derived/poten_tanker_opinions_index.json` (NAMED, NOT CHANGED - judgement needed)

7 of 1,099 `pdf_path` values do not resolve. All 7 DO resolve by unique basename, but the record own
`year` field contradicts the real location, so repointing the path alone would leave the record
internally inconsistent. The stored path year is wrong in every case:

| stored `pdf_path` | stored `year` | file actually at |
|---|---|---|
| `corpus/04-poten/pdfs/unknown/Tanker_Opinion_20070413.pdf` | (none) | `corpus/04-poten/pdfs/2007/` |
| `corpus/04-poten/pdfs/unknown/Tanker_Opinion_20150130.pdf` | (none) | `corpus/04-poten/pdfs/2015/` |
| `corpus/04-poten/pdfs/2004/Weekly-Opinion-Feb-6.pdf` | 2004 | `corpus/04-poten/pdfs/2015/` |
| `corpus/04-poten/pdfs/2004/A-Mulligan-for-Capesize-Owners.pdf` | 2004 | `corpus/04-poten/pdfs/2015/` |
| `corpus/04-poten/pdfs/2004/Let-it-Float-Let-it-Float-Let-it-Float.pdf` | 2004 | `corpus/04-poten/pdfs/2014/` |
| `corpus/04-poten/pdfs/2004/Panamaxes-Cleaning-Up-Their-Act.pdf` | 2004 | `corpus/04-poten/pdfs/2014/` |
| `corpus/04-poten/pdfs/2004/West-AfriCAN-Go-East.pdf` | 2004 | `corpus/04-poten/pdfs/2014/` |

The filenames embed the truth (`Tanker_Opinion_20070413` = 2007-04-13, `Tanker_Opinion_20150130` =
2015-01-30) and the `pdf_url` upload directories agree (`uploads/2015/02`, `uploads/2015/01`,
`uploads/2015/04`), so the 2004 label is simply wrong. Left untouched under *"a wrong value is worse
than a missing one"*: setting the correct `year` needs the publisher's own publication date, not an
inference from a folder name.

## Defect 4 - `data/extracted/secondhand_deals_summary.json` (10 values) - NOT TRACKED

All 10 path values are pre-migration, in the old backslash form pointing at `reports/shipbrokers/other/2021/...`;
both documents exist at `corpus/archive/other/2021/...`. `git ls-files --error-unmatch` = **not tracked**,
built by a scratch script (`scratch/sweep2/build_v2.py`), so there is nothing in the repo to fix.
Reported only in case a local consumer reads it.

## This cycle freshness re-check (no extraction or stacking gap)

`git status corpus` = **0 changes** -> no new arrivals (newest broker content still 2026-10-06).
Re-running `scratch/freshness_sweep.py` flagged 11 sources as "md date newer than series max"; each was
calibrated against the DOCUMENT OWN date (publication date != report date) - the method that found the
seabrokers and agora gaps in earlier runs:

| source | flagged | calibration (measured) | gap? |
|---|---|---|---|
| xclusiv | md 2026-09-29 vs 2026-09-28 | cover reads "weekly 28th September" = series max | no |
| ssy | md 2026-09-28 vs 2026-09-25 | `ssy_28_09_2026_...pdf` frontmatter = issue_date 2026-09-25, week 39, index 18443 = the week 39 the series holds | no |
| ism | md 2026-09-28 vs 2026-09-21 | newest `value_report` in both series = `..._week_39`; W39 chart dates end 2026-09-21 | no |
| intermodal | md 2026-09-30 vs 2026-09-29 | W39 report IS stacked (`intermodal_2026_W39_...pdf` appears in all 16 series); the `30_09_2026` md is that same document md-tier name | no |
| affinity | md 2026-10-03 vs 2026-10-02 | cover "2 October 2026" (W40) = series max | no |
| baltic | md 2026-10-02 vs 2026-09-25 | newest ningbo source file in the corpus = 2026-09-25; the 2026-10-02 W40 reports ARE catalogued in `baltic_reports_metadata.csv` | no |
| fearnleys | md 2026-10-02 vs 2026-10-01 | newest file is the SnP *comment* (commentary tier, no numeric series); the rates series max 2026-10-01 = the newest rates report | no |
| poten | md 2026-09-18 vs 2026-09-11 | the 09-18 issue contains NO delivery-schedule table (0 hits for "delivery" in its md), so `poten_fleet_delivery_schedule_series` correctly ends 2026-09-11; `poten_opinions_metadata` DOES hold 2026-09-18 | no |
| breakwave, hellenic | md "2026-12-01" / "2026-12-09" | date-regex artefacts on odd filenames; both dates lie in the FUTURE of the run day | no |
| advanced_shipping | no date column in its series | - | n/a |

Also measured: `corpus/01-brokers/*` pdf-vs-md stem parity = **0 unextracted docs** except the known
byte-duplicate / rename cases (banchero 1, fearnleys 2, affinity 7, star_asia 1), as in earlier runs.

## Reproduce

```
python scripts/extract/publishers/fix_agora_source_paths.py --dry-run     # idempotent report
python scripts/verify/repoint_stale_path_fields.py --dry-run              # gold_standard ledger
python scripts/extract/verify_registers.py                                # gate
python scratch/freshness_sweep.py ; python scratch/gap_candidates.py <source> <series_max_date>
python scratch/md_path_scan.py ; python scratch/json_path_scan.py         # path-field sweep
```
