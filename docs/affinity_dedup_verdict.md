# affinity byte-duplicate dedup - VERIFIED, 2026-10-01 23:2x

Second source of the pending corpus-wide dedup re-runs (ssy was the first,
`docs/ssy_dedup_verdict.md`).

## Measured before

| series | rows | duplicate rows (source_file is a skipped stem) |
|---|---|---|
| `affinity_tce_series.csv` | 4,058 | **38** |
| `affinity_bda_series.csv` | 747 | **6** |
| `affinity_indices_series.csv` | 498 | **4** |
| total | 5,303 | **48** (matches the census) |

254 corpus PDFs / 7 md5 duplicate groups / 247 unique documents. Groups are the
`affinity_2026_nan_*` twins and the `DD_MM_YYYY` collection-route twins
(`affinity_26_09_2026_..._25_september_2026` == `affinity_2026_..._25.09.2026`).

## Why it had not been fixed by wiring the first runner

`run_affinity_tables.py` had the filter (and it filters `stamp_and_stack()` correctly,
name-slice, so dotted filenames are safe) - but it writes only tce + bda. The file that
writes **all three** series (and rewrites the md) is the SECOND writer,
`polish_affinity_markdown.py`, which had no filter and would have re-added the rows.
It was patched first, then run:

```
[dedup] skipped 3 byte-identical duplicate sidecar(s)
Processing 247 canonical Affinity reports...
Successfully polished 247 Markdown files with clean two-column commentary.
Saved 4020 rows to affinity_tce_series.csv
Saved 741 rows to affinity_bda_series.csv
Saved 494 rows to affinity_indices_series.csv
```

Only 3 sidecars were skipped because the script's own pre-existing cleanup already
removes the flat-dir `*_nan_*` copies - the remaining 3 non-`_nan_` pairs are the ones
the md5 filter catches.

## The control

Pre-fix file minus the rows whose `source_file` is a skipped stem must equal the post-fix
file as an exact multiset on every column:

```
affinity_tce_series.csv:     pre=4058 dropped=38 expected=4020 post=4020  ADDED=0 REMOVED=0  PASS
affinity_bda_series.csv:     pre=747  dropped=6  expected=741  post=741   ADDED=0 REMOVED=0  PASS
affinity_indices_series.csv: pre=498  dropped=4  expected=494  post=494   ADDED=0 REMOVED=0  PASS
OVERALL: PASS
```

Nothing else moved: no value was re-parsed differently and no row was lost.

## md tier

**13 orphan md/sidecar/chart files for skipped stems quarantined** to
`scratch/dedup_ssy/quarantine_affinity/`. Post: `data/extracted/md/affinity/` **247 `.md`
+ 247 `.tables.json`** = exactly one file set per canonical report. affinity writes md to
`<year>/` subdirs only (no flat copies, unlike ssy/ism), so there is no flat+year mirror
here.

The 5 `_nan_` strays existed because this script's own cleanup unlinks
`OUT_MD.glob("*_nan_*")` - the **flat dir only** - so `_nan_` twins sitting in `<year>/`
survive every run. Recorded, not fixed in code.

## Status

affinity: 254 PDFs / 247 unique, 4,020 + 741 + 494 rows, 0 duplicate rows. CLOSED.
Pre-fix copies `scratch/dedup_ssy/PRE_affinity_*.csv`; pre-patch code
`scratch/dedup_ssy/polish_affinity_markdown.py.bak`. `data/extracted/` is gitignored, so
the corrected CSVs are disk-only.
