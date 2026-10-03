# affinity VERIFY - 2026-10-03 (source-by-source, 30m job)

Trigger: the previous run's NEXT-RUN TARGET, the "stale data vs committed runner"
sweep. It flagged affinity because a file matching
`scripts/extract/publishers/*affinity*.py` was committed **2026-10-02 15:22**
while the newest `series/affinity_*.csv` mtime was **2026-10-01 23:12** (16.2 h).

## The sweep's premise was a heuristic MISFIRE for affinity

Measured: the 15:22 commit is `c25fb48ba` on **`run_affinity.py`**, which is the
**MD producer** (`emit()` writes `data/extracted/md/affinity/<stem>.md`), NOT a
writer of the series CSVs. The three CSVs are written by
`polish_affinity_markdown.py` (all three) and `run_affinity_tables.py` (tce+bda).
`polish` was last committed **2026-10-01 23:14:39** - AFTER its own data write at
23:12. So the CSVs were never stale against a committed fix. The sweep compared a
filename glob (`*affinity*.py`) rather than the actual writer.

## REAL finding: a flat+year mirror had been re-created (762 stray files)

Measured on disk before any change:

| tier | md | tables.json | charts.json |
|---|---|---|---|
| flat (`md/affinity/<stem>.*`) | 254 | 254 | 254 |
| year (`md/affinity/<YYYY>/<stem>.*`) | 247 | 247 | 247 |

* All 247 shared stems have **different** flat-vs-year content (not byte-twins):
  flat = `run_affinity.py` raw form (`# <stem>`, `## Cards`, a `source:` geometry
  line, no frontmatter); year = `polish` form (YAML frontmatter with
  `issue_date`/`report_week`/`source_file`, `## Market Indices`, commentary).
* **Every sibling source is year-only**: advanced_shipping flat=0/year=253,
  star_asia 0/198, ssy 0/530, xclusiv 0/271, fearnleys 0/260. affinity was the
  only outlier.
* The flat tier was written **2026-10-02 22:46** (md mtimes), i.e. AFTER the
  10-01 dedup verdict that recorded affinity as year-only with no flat copies.
* The orchestrator writes affinity md to `MD_DIR/"affinity"/year_str` (line 507);
  the year tier is the canonical, frontmatter-bearing deliverable.
* **Hazard**: both `run_affinity_tables.py` and `polish_affinity_markdown.py`
  iterate `OUT_MD.rglob("*.tables.json")` and dedup only by byte-identical stem.
  With 501 sidecars (254 flat + 247 year) present, the next run of either writer
  would process every canonical doc TWICE and roughly double the CSV.

**Action**: quarantined the 762 flat files to
`scratch/affinity_audit/quarantine_flat/` (moved, not deleted - reversible).
`_run_state.json` kept. md tier restored to **247 md + 247 tables.json + 247
charts.json, year-partitioned only, 0 flat**.

## Re-ran both writers under a control (offline, no spend)

```
run_affinity_tables.py   -> 247 sidecars stamped, tce 4020, bda 741, dedup skipped 0
polish_affinity_markdown -> 247 md polished, tce 4020, bda 741, indices 494
```

**CONTROL (byte-level).** md5 of all **170** series CSVs pre vs post:
**0 changed** - the three affinity CSVs (4020 / 741 / 494) are **byte-reproducible
from the delivered artefacts**. Same control on the md tier: 247 `.md` changed,
**0 sidecars and 0 charts changed**. `polish` is deterministic - two consecutive
passes produced byte-identical output (0/247 changed).

The delivered year `.md` predated the current `polish` output for **247/247**
files (their 10-02 00:52 mtime is misleading - a copy/check stamp, see the
OVERNIGHT_STATE mtime lesson; content was pre-normalization). The re-run brought
them current. Pre-content was NOT snapshotted (only md5), so the textual delta is
not byte-diffable - stated, not assumed.

## Content control (no vision tool this session - substituted same-document reconciliation)

Panel numbers (span x >= 590) read from each source PDF's own text layer vs the md:

| doc | panel values | unaccounted in md |
|---|---|---|
| affinity_2024_Affinity-Tanker-Weekly-05.01.2024-HSN | 41 | **0** |
| affinity_19_09_2026_..._18_september_2026 | 49 | **0** |

(`4,899`/`1,943` etc. are present - thousands-separated.)

## md defect found, measured, NOT fixed (pre-existing, in `polish`)

In the **WS-header era** (the 68 docs the affinity_verdict already documents: all
26 of 2021 + 42 of 2022) the card header is `$ / WS` and the md renders WS-quoted
rates **rounded to an integer with a `$` prefix**, losing both the unit and the
decimal:

```
PDF panel   CSV (exact)   md (polish)
WS 130.63   130.63        $131
WS 119.56   119.56        $120
WS 212.14   212.14        $212
```

Reconciliation of every md rate cell against the CSV: **checked 4,014, exact
3,870, mismatch 144** - and the 144 are **exactly the WS era**: 2021 = 36,
2022 = 108. Zero mismatches in 2023-2026. The **CSV is exact and byte-reproducible**;
only the md *display* is lossy/mislabelled. This is a `polish` rendering choice,
not introduced by this run. Fixing it is a `polish` md-render change (preserve the
unit + decimal) - left as a decision, the primary deliverable is unaffected.

## Housekeeping

* `scripts/verify/verify_affinity.py` repointed off the quarantined flat tier:
  `OUT_MD.glob` -> `OUT_MD.rglob`, corpus target 250 -> 254 PDFs / 247 unique,
  BDA row check now against the sidecar record count instead of a hardcoded 750.
  Now **6/6 PASS** against the year tier.
* Register: `verify_registers.py` = **0 mismatches**, **170 CSVs / 594,101 logical
  rows**; affinity series rows correct (tce 4,020 / bda 741 / indices 494).
  Section-1 prose row (line 23) still says 3,982/735/490 and "245 .md" - stale
  prose, the same residual class as xclusiv's publisher block; `verify_registers`
  does not read it.

## Result

affinity: **CLOSED**. 247 unique docs, md tier year-only (0 flat), 3 series CSVs
byte-reproducible, register clean. Open items: the WS-era md rounding (above) and
the stale Section-1 prose row.
