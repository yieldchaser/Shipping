# xclusiv bulk-carrier chart series: real 200-300% defect, root-caused and fixed

Date: 2026-10-09. Branch `auto/extract-fixes-2026-10-09-deepreview`. Per-source fix;
no generic runner. Artifact: `data/extracted/series/xclusiv_bulk_carrier_charts_series.csv`
(208 rows, registered "Verified" in `docs/BROKER_STRICT_AUDIT_REPORT.md`).

## The defect (measured, not a metric artefact)

Every one of the 208 rows failed to reproduce the SAME document's own stated weekly
dry-bulk rate. Ground truth = the publisher's page-2 prose in the same PDF:

| doc | series said (old) | page-2 prose says | error |
|---|---|---|---|
| xclusiv_2025_xclusiv-2025_09_22 | Capesize 5TC **86598.4** | "C5TC avg ... at USD 25,457/day" | +240% |
| xclusiv_2026_xclusiv-2026_09_28 | Capesize 5TC **86590.1** | "C5TC ... closing the week at USD 48,954/day" | +77% |
| xclusiv_2025_xclusiv-2025_09_22 | Handysize 7TC **46790.9** | "HS7TC avg ... at USD 14,475/day" | +223% |
| xclusiv_2026_xclusiv-2026_01_05 | Handysize 7TC **26039.9** | "HS7TC avg ... at USD 12,329/day" | +111% |

Full sweep: **0 of 208 rows** matched the doc's own prose (the 2 "near" hits,
`Ultramax 11TC` 14662.4 vs 14646 and 22065.7 vs 21960, are coincidences). The values
were also a small set of repeated constants (`86598.4`/`86590.1` for Capesize across
20+ non-adjacent weeks, `39589.4`/`38750.9`, `46790.9`/`36941.3`) - a real weekly
series cannot be constant while the prose moves 22,595 -> 25,882.

## Root cause (found by reading the drawings)

`scripts/extract/publishers/run_xclusiv_vector_charts.py::extract_panel_value_from_drawings`
selected the wrong drawing:

```
if len(c) == 3 and (c[0] < 0.35 and c[1] < 0.6 and c[2] > 0.4):   # "blue/navy"
```

On the dry-bulk page each stacked chart carries FOUR series with these stroke colours:

| role | colour | shape |
|---|---|---|
| **DATA curve (the 5TC series)** | `(0.612, 0.729, 0.835)` light blue | 482-1248 line segs, spans the plot |
| Average reference | `(0.106, 0.255, 0.443)` navy | horizontal (y0==y1) |
| Min reference | `(0.271, 0.518, 0.827)` blue | horizontal |
| Max reference | `(0.498, 0.498, 0.498)` grey | horizontal |

The data curve's light blue FAILS `c[0] < 0.35` and is rejected; the navy
**Average reference line** PASSES and is chosen. Its y is constant per layout, so the
emitted "rate" was the reference line's y mapped through the hardcoded val range
-> a plausible-looking, entirely wrong constant.

This is the skill's "hardcoded geometry" + "evenly spaced rule chains exist in both
tables and charts" trap: the selector anchored on colour/geometry, not on content.

## The fix (per-source, idempotent, values-only)

1. **Code (root cause):** `run_xclusiv_vector_charts.py` now selects the light-blue
   DATA curve (`BC_DATA_COLOR = (0.612,0.729,0.835)`, largest line-segment count),
   derives `value = a*y + b` from that chart's OWN printed y-axis tick labels
   (clustered by a >40pt y-gap: 4 charts, top->bottom = Capesize/Kamsarmax/Ultramax/
   Handysize), and maps the curve's latest point. Verified the function reproduces the
   delivered values exactly.
2. **Data:** `scripts/extract/publishers/fix_xclusiv_bulk_chart_values.py` rewrites the
   delivered CSV in place, values only.

Measured on the delivered file (`git diff --numstat` = **208 changed / 208 total**):

| metric | value |
|---|---|
| rows | 208 -> 208 (identity, order, all other columns byte-identical: 0 non-value-only rows) |
| corrected (passed control) | **203** |
| blanked (control failed) | **5** (listed in `data/extracted/audit/xclusiv_bulk_carrier_charts_quarantine.json`) |
| value range before | 14,640.8 .. **86,598.4** (impossible on a 20k-100k axis) |
| value range after | 9,400.7 .. **46,591.6** (plausible $/day) |

**Control (independent, same document):** the corrected value must agree within 30%
with the pdf's own page-1 prose level (`at USD <n>/day`, which skips the
"declined by USD 1.2/day" change token). Agreement distribution of the corrected
chart read vs the doc's own prose: median **10.3%**, p90 21.3%, p99 31.8% - i.e. the
chart's latest plotted point tracks the published weekly average, as expected. The 5
failures are the tail (3 return a degenerate constant from a non-standard Capesize
layout; 2 are genuinely off) and are BLANK, never wrong.

**Idempotent:** a re-run re-parses and finds nothing stale. EOL LF + no BOM preserved.

## Register

Row count and CSV count unchanged (208 / 180), so `verify_registers.py` is unmoved:
**ALL PASSED, 180 CSVs / 639,756 rows == JSON == MD, 0 mismatches.**

## Named, NOT fixed this run

* **`xclusiv_demolition_charts_series.csv` (278 rows) shares the SAME selector** and is
  SUSPECT: heavy constant repetition (`289.7` x12, `311.0` x8, `143.5` x7 for the Dry
  index) shows the reference-line signature. Magnitudes are in-range, so it was left
  in place pending the same corrected-geometry + prose-control treatment (the
  demolition charts sit on a 200-700 axis and need their own colour/tick fingerprint).
* The **chart-curve HISTORY** (the publisher's ~5-year rolling window) remains owed -
  see `docs/xclusiv_charts_owed.md`; this series only ever held the latest point.

## Backups / evidence

* Pre-fix copy: `scratch/xclusiv_bulk_carrier_charts_series.bak.csv` (gitignored).
* Quarantine list: `data/extracted/audit/xclusiv_bulk_carrier_charts_quarantine.json`.
