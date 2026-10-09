# xclusiv_demolition_charts_series.csv: real ~42% defect, root-caused and fixed

Date: 2026-10-09. Branch `auto/extract-fixes-2026-10-09-deepreview`. Per-source fix;
no generic runner. Artefact: `data/extracted/series/xclusiv_demolition_charts_series.csv`
(278 rows, registered "Verified" in `docs/EXTRACTION_REGISTER.md`). Companion to
`docs/xclusiv_bulk_charts_verdict.md` (same class, sibling series).

## The defect (measured against the publisher's own printed numbers)

Every one of the 278 rows failed to reproduce the SAME document's own printed
demolition price - **0/278 within 5%**, median error **-41.6%**, worst -66.2%:

| doc | segment | series said | the page prints (India) | error |
|---|---|---|---|---|
| xclusiv_2024_xclusiv-2024_01_08 | Dry Demolition Index | **331.5** | 530 | -37.5% |
| xclusiv_2024_xclusiv-2024_01_08 | Tanker Demolition Index | **355.2** | 535 | -33.6% |
| xclusiv_2026_xclusiv-2026_09_28 | Dry Demolition Index | **388.0** | 460 | -15.7% |
| xclusiv_2026_xclusiv-2026_09_28 | Tanker Demolition Index | **407.3** | 480 | -15.1% |

Ground truth is TEXT on the page, not another extractor: the demolition page of
each report carries a "Demolition Market" chart whose data labels are printed
number words (`530 510 520 360` = India/Bangladesh/Pakistan/Turkey, verified
positionally against the chart legend). Magnitudes were in-range (131-407 on a
200-700 axis), which is exactly why this survived an earlier audit: the values
were plausible, just uniformly ~40% low.

## Root cause

`run_xclusiv_vector_charts.py` reads the demolition panel with:

```
dry_val  = extract_panel_value_from_drawings(drawings_demo, 135.0, 225.0, 700.0, 200.0)
tank_val = extract_panel_value_from_drawings(drawings_demo, 375.0, 465.0, 700.0, 200.0)
```

`extract_panel_value_from_drawings` maps the selected curve's latest y through
`val_bot + (y_max - y) * (val_top - val_bot) / (y_max - y_min)` - a **HARDCODED**
y-band (135..225) against a hardcoded value range (700..200).

Measured from the page: the demo page stacks a 52-week per-country price chart on
the LEFT (x 44-281, y-axis ticks 700..200 at y 161.2..269.7 in 2024, **250..550 in
2026** - the axis ITSELF moves between eras) and a "Demolition Market" snapshot
chart on the RIGHT. The hardcoded band does not match the real plotted band, so
the value is systematically low. (The colour filter also accepts the wrong
candidate in general - `c[0]<0.35 and c[1]<0.6 and c[2]>0.4` - but here the
accepted drawing happens to be the correct entity; see below.)

## Which entity the series actually is

Legend swatch geometry (drawings, x left of each label) maps the four series
colours to countries:

| swatch x | colour | country |
|---|---|---|
| 50.5 | (0.271, 0.518, 0.827) | **India** - the one the extractor selects |
| 98.3 | (0.0, 0.125, 0.376) | Bangladesh |
| 169.7 | (0.749, 0.749, 0.749) | Pakistan |
| 230.0 | (0.612, 0.729, 0.835) | Turkey |

So `Dry Demolition Index` / `Tanker Demolition Index` are the **India** bulkers /
tankers demolition prices - one country grain, not an index. Confirmed by
re-fitting each chart's axis from its own printed ticks and reading the India
curve: India is the best of the four (median abs err 3.81%, 238/278 within 5%)
against Bangladesh 5.28%, Pakistan 5.43%, Turkey 44.02% (residual = plotted point
vs printed label; the label is the exact value, so the label is what we ship).

## The fix (per-source, idempotent, values-only)

1. **Code (root cause):** `run_xclusiv_vector_charts.py` no longer reads this panel
   by geometry. `extract_india_demolition_values()` reuses THIS source's own text
   parser (`run_xclusiv_tables.extract_indicative_demolition`, which reads the
   printed labels) and takes the `country == "India"` rows. Rationale: the value
   the series wants is printed as text on the same page, so geometry is pure risk
   - the skill's "bar chart with printed values needs no vision" rule.
2. **Data:** `scripts/extract/publishers/fix_xclusiv_demolition_chart_values.py`
   rewrites the delivered CSV in place, values only.

Measured on the delivered file (`git diff --numstat` = **278 changed / 278 total**):

| metric | value |
|---|---|
| rows | 278 -> 278 (order, and every non-value column byte-identical) |
| columns that changed | **`price_usd_per_ldt` only** |
| corrected | **278** |
| blanked (control failed) | **0** |
| value range before | 131.3 .. 407.3 |
| value range after | **370.0 .. 535.0** ($/LDT, matching the publisher) |

**Control (same document, independent of the fix):** every new value is the exact
number printed on THAT PDF's own demolition page - verified by regex against
`page.get_text()`: **278/278**. No row was blanked and the quarantine list is empty.

**Code == data (no divergence):** driving the patched `run_xclusiv_vector_charts.py`
extractor over the same 139 documents reproduces the shipped file **278/278**
exactly.

**Idempotent:** a re-run prints "idempotent: nothing stale, no write". EOL LF +
no BOM preserved.

## Register

Row count and CSV count unchanged (278 / 180), so `verify_registers.py` is unmoved:
**ALL PASSED, 180 CSVs / 639,756 rows == JSON == MD, 0 mismatches.**

## Named, NOT fixed

* **This series is now a duplicate of the India rows of `xclusiv_demolition_series.csv`**
  (2,082 rows, 4 countries, exact, 2021-07-26..2026-09-28). Both are correct now,
  but the chart series carries one country of data that the text series already
  holds in full. Consolidating (dropping the chart series) is a REGISTER change and
  is left to the user.
* The **chart-curve HISTORY** (the publisher's rolling 52-week window, one value
  per country per week) remains owed - see `docs/xclusiv_charts_owed.md`; this
  series only ever held the latest point.
* `extract_panel_value_from_drawings` itself is now unused by the demolition path
  but is left in place (still referenced by legacy helpers) - a dead-code cleanup
  rather than a correctness fix.

## Backups / evidence

* Pre-fix copy: `scratch/xclusiv_demolition_charts_series.bak.csv` (gitignored).
* Quarantine list (empty): `data/extracted/audit/xclusiv_demolition_charts_quarantine.json`.
