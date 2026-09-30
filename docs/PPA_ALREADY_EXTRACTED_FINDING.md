# 09-ppa is NOT a zero-output gap - measured 2026-09-28 14:2x (supervisor run 345bc8db9233)

`docs/corpus_coverage_gaps.md` states: "`corpus/09-ppa` 493 PDFs, ZERO output -
largest fully-unbuilt PDF corpus". **That claim is false at the table layer.**
It was derived from a `glob` count of `data/extracted/md/*` only, which never
queries the database, the corpus extraction tree, or the app - the exact
single-baseline error the corpus-pdf-extraction skill warns about.

## Measured, read-only (`corpus.duckdb`, `data/extracted/**`)

| side | measure | value |
|---|---|---|
| corpus | PDF files under `corpus/09-ppa` | **493** |
| corpus | distinct `sha256` contents | **339** (154 files are byte-duplicates) |
| corpus | subdirs | `ppa_pdf/` 326 (hash-named `xxxxxxxxxxxx.pdf`), `_root_pdfs/` 167 (named) |
| DB | documents with cells (`source LIKE '%ppa%'`) | **297** |
| DB | cells | **228,280** |
| DB | tables (catalogue) | **1,335** |
| DB | distinct source labels | 117 |
| both | distinct contents already extracted | **297 / 339 = 87.6 pct** |
| both | distinct contents MISSING | **42** |

Robustness: the 42 survives exact-stem AND normalised 45-char-prefix matching,
so it is not a filename artefact. Every DB stem is a subset of the corpus stems
(0 DB docs are absent from disk).

## What the missing 42 actually are

Port of Dampier / Pilbara Port Authority **financial-year cargo statistics**
one-pagers, FY2015-16 through FY2025-26: one page each, ONE table, months as
rows x commodities as columns (IRON ORE, SALT, CONDENSATE, LNG, LPG, AMMONIUM,
GENERAL, PETROLEUM, TOTAL, number of vessels). 54 files including duplicates,
4,596 B to 185,661 B. Sample: `dampier_2026_june.pdf`,
`klein-stats-july-2025-to-june-2026-ytd.pdf`,
`ppa_dampier_klein_stats_july_2024_to_june_2025_ytd_pdf.pdf`.

The DB's existing ppa sources already carry this schema: IRON ORE 533 cells,
SALT 510, CONDENSATE 106, LNG 107, LPG present, AMMONIUM 10, and 1,276
`NUMBER OF` / `NO. OF` vessel-count header cells. This is an ADDITIONAL-YEAR
gap, not a missing schema.

## The md tier really is absent

There is no `data/extracted/md/ppa*` directory. So the honest split is: ppa's
**table tier is 87.6 pct built**, ppa's **markdown tier is 0 pct built**. The
coverage doc measured only the second and reported it as the whole story.

## Second and third baselines

2. **The app already DISPLAYS ppa.** `data/commodities/australia_ppa_iron_ore.csv`,
   423 rows, monthly, columns date/port/total_throughput_mt/iron_ore_exports_mt/
   destinations_t/mom_pct/yoy_pct/provenance; last row `2026-08-01, Port of
   Dampier, 14.841, 12.8` provenance `live_ppa_dampier_fy`. `index.html` fetches
   it at line 19029 and renders it at 19030, 30647, 50012 and 50680.
3. **The corpus extraction tree** holds 130 `data/extracted/corpus/<ppa_*>/`
   document directories with `tables.jsonl`.

## Consequences for the live run

A **from-zero 493-document `run_ppa.py`** (being authored right now by cron job
`12f7fa574166`) duplicates 87.6 pct of work already in the DB. Correct scope:

1. Start from the **42 missing contents**, not 493. File list:
   `scratch/supervisor_verify/ppa_42_files.json`, unrepresented stems in
   `scratch/supervisor_verify/ppa_unrepresented.txt`.
2. Check each against the DB before extracting: several FYs may already be
   restatements of the monthly `cargo_grt_and_dwt_statistics_by_commodity_type_*`
   documents that ARE extracted.
3. The md tier is the genuine 0 pct - that is where a runner adds value.

## Evidence commands

```
python3 scratch/supervisor_verify/verify_ppa_gap.py
python3 scratch/supervisor_verify/verify_euro_live.py
python3 scratch/supervisor_verify/verify_series_leak_live.py
```
Machine-readable record: `data/extracted/supervisor_verify_20260928_1420.json`.

## The 42 contents resolve to a CONTIGUOUS 10-YEAR HOLE (measured 14:37)

FY header read from page 1 of every one of the 339 distinct contents
(`scratch/supervisor_verify/ppa_fy_map.json`).

Dampier FY cargo-statistics sheets the DB ALREADY holds:
`2002-03, 2003-04, 2004-05, 2005-06, 2006-07, 2007-08, 2008-09, 2009-10,
2010-11, 2011-12, 2012-13, 2013-14, 2014-15, 2015-16, 2025-26`.

FY sheets MISSING: `2016-17, 2017-18, 2018-19, 2019-20, 2020-21, 2021-22,
2022-23, 2023-24, 2024-25` (contiguous), plus `2026-27` (YTD, 2 files).

So the correction is narrower and far more useful than "493 documents":
**one contiguous 10-year hole in one monthly series.** FY2025-26 is already in
the DB, so the series is not even open-ended - it is a single gap.

Two of the 42 are not FY sheets at all:
- `_root_pdfs/ppa_hedland_commodity_latest.pdf` - a Wayback Machine capture
  whose page 1 is the Internet Archive donation banner (junk front matter).
  Port Hedland content IS in the DB under other sources (238 `ppa_pdf` cells
  mention HEDLAND), so treat as restatement/junk, not a new series.
- `_root_pdfs/test_download.pdf` - an ASX (`asx.com.au`) site
  general-conditions page mis-downloaded as a PDF. **Route as junk.**
