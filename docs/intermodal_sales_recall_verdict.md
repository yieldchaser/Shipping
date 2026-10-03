# intermodal secondhand-sales - recall gap RECOVERED (+131 rows)

*Run: 2026-10-03 (source-by-source, unattended). Writer: scripts/extract/publishers/run_intermodal_full.py*

## How it was found

Not by a metric - by RE-RUNNING the parser over the cached markdown and reconciling
per document against the delivered CSV (the "full row-count audit per series" the
2026-10-03 macro verdict owed). `intermodal_sales_series.csv` held **3,348** rows; the
current parser yields **3,387**.

The gap was verified against the source PDFs, not the md:

- `intermodal_2022_W13` page 3 (PDF text) prints the Tanker table
  `VLCC EASTERN JUNIPER 305,749 2007 ...`, `VLCC TOKIO`, the HAFNIA block, etc.
  The delivered CSV for that document carried **only 2 rows** (the containers
  JAN / VEGA SACHSEN). `EASTERN JUNIPER` is absent from the whole CSV.
- `intermodal_2023_W06` page 3 prints `NAVE PHOTON`, `ADVENTURE`,
  `KONSTANTIN JACOB`, `STENA PROGRESS`... The CSV carried **5** rows; 13 were missing.

Two independent years, two PDFs, both read directly.

## Two defects, one of which is a parser bug

1. **Stale sidecars.** The delivered sidecars (`data/extracted/md/intermodal/<year>/*.tables.json`)
   pre-date the 2026-10-02 markdown reparse for 16 documents, so their `secondhand_sales`
   key is short. Re-running `process_single_pdf` on `intermodal_2022_W13` writes **21**
   sales rows into the sidecar where 2 sat before.
2. **Mangled-header misalignment (a real parser bug).** In one era LlamaParse fuses the
   section label into the header and inserts `Sector`/`Size` cells AHEAD of `Name`:
   `| Sector | Size | Tankers | Name | Dwt | Built | ... |`. The DATA row is unchanged
   (its first cell is the size/type code), so every header keyword sits 2 columns to the
   RIGHT of the value it names. The old map trusted the literal index, so a re-run would
   have published the vessel NAME as the DWT and the BUILT year as the NAME - a wrong
   value, worse than a missing one. Measured on 2022 W13: 19 rows shifted.

## The fix (content-anchored, per the skill)

`run_intermodal_full.py` section 6 now derives the shift from the page instead of
trusting the header index:

```python
_hdr_shift = 0
if hdr0 and hdr0[0].strip().lower() == "sector" and "name" in col_map and col_map["name"] > 1:
    _hdr_shift = col_map["name"] - 1      # cells before 'Name' are spurious
if _hdr_shift:
    col_map = {k: (i - _hdr_shift if i - _hdr_shift >= 0 else 0) for k, i in col_map.items()}
```

For every normal header (`Size|Name|Dwt|...`, `Type|Name|...`, `Bulk Carriers Size|...`)
`_hdr_shift == 0`, so the change is inert on 14 of the 30 header shapes present in the
corpus; it only fires on the `Sector|Size|...` family (W13/W17/W24 2022, W06 2023, the
`Sector|Size|Containers|Name|Teu` container family, W20/W49).

Then the 16 affected documents' cached md were re-parsed and **only** their
`tables["secondhand_sales"]` key replaced (the finance keys `maritime_stocks` /
`bunker_prices` / `macro_indicators` are preserved - a plain `process_single_pdf`
re-run would clobber them), and the series restacked via
`build_all_series_from_sidecars()`.

## Measured result

| | before | after |
|---|---|---|
| `intermodal_sales_series.csv` | 3,348 | **3,479** (**+131**) |
| docs refreshed | - | 16 |
| duplicate full-row keys | 0 | 0 |

**Control:** md5 of all 16 `intermodal_*_series.csv` before/after - **only
`intermodal_sales_series.csv` changed**. `write_series_csv` dedups exact rows, so the
staleness of `tc_rates` (+36) and `indicative_values` (+70) resolves to a byte-identical
file; a blanket re-stack is idempotent everywhere but sales. Register re-synced:
**594,010 logical rows / 170 CSVs**, `verify_registers.py` = **0 mismatches**.

**Content verification (eye-substitute per skill: no vision tool in this session):** every
vessel_name and dwt of the 16 refreshed documents reconciled against the **PDF text layer**
(PyMuPDF) - **301/302 = 99.7%** vessel names present, **302/302 = 100.0%** dwt present. The
single miss is `CELIUS MESSINA` (2022 W25) where the LlamaParse markdown itself reads
`CELIUS` and the PDF reads `CELSIUS` - an upstream md char error, faithfully copied, not a
parser defect.

## Disclosed residuals (measured, NOT fixed)

- **Do NOT blanket-reparse.** The 2026-10-02 markdown is POORER than the delivered
  sidecars for some series: a fresh parse yields **3,449** tanker_spot rows against 3,885
  delivered, and **1,104** indicative rows against 2,360. Those series are correct on disk;
  a full reparse would lose data. The recovery above is surgical for that reason.
- **Fused single-row tables still unrecovered:** `intermodal_2021_W31`, `_W34`, `_2022_W35`
  collapse a whole sales table into one space-joined header row (no `<br>`), so the table is
  lost. Small (~3 docs); needs positional splitting.
- **tc_rates +36 / indicative +70 inside the sidecars** equal the delivered file after
  dedup, so they are not a gap - but a per-page row-count audit of those two series (the
  parser yields 5,225 tc_rates rows, 26 docs short for other reasons) is still owed.

---

## Same audit, second series: dry-bulk TC RATES RECOVERED (+153 rows)

`intermodal_tc_rates_series.csv` was **5,080** rows; the parser's per-document UNIQUE
count (deduped the way the writer does) yields more on **24** documents. The missing block
is the **dry-bulk Time-Charter table** (Capesize/Panamax/Supramax/Handysize x 1yr/3yr TC),
absent from those sidecars. Verified against the PDFs, not metrics:

- `intermodal_2026_W12` page 2 prints `180K 1yr TC 29,750`, `180K 3yr TC 23,500`,
  `76K 1yr TC 16,250`, `58K`, `32K` ... The delivered CSV for that document held **12**
  rows, all Tanker.
- `intermodal_2023_W21`: all 8 dry-bulk current rates (15,750 / 16,750 / 12,000 /
  12,250 / 13,000 / 11,750 / 11,500 / 9,500) are printed on page 2 - all 8 present.

**Applied with a LABEL guard.** 6 documents (2023 W21/W24/W29/W30/W31/W33) were SKIPPED
because the LlamaParse markdown itself corrupted the class column - it stamps a single
`Capesize`/`Handysize`/`Panamax` on every dry-bulk row (e.g. W21 md line 165-171 carry
`**Capesize**` for the 76K/58K/32K rows, which are Panamax/Supramax/Handysize). Adding
those rows would publish a wrong class, so they are left missing (a wrong value is worse
than a missing one). 9 further documents are REGRESSION docs where the current md is
poorer than the delivered CSV (parser_unique < csv) - untouched.

| | before | after |
|---|---|---|
| `intermodal_tc_rates_series.csv` | 5,080 | **5,233** (+153) |
| documents refreshed | - | 18 |
| duplicate full-row keys | 0 | 0 |

**Control:** md5 of all 16 `intermodal_*_series.csv` before/after - only
`intermodal_tc_rates_series.csv` changed; `intermodal_sales_series.csv` stayed 3,479.

**Content verification:** every dry-bulk `rate_usd_day_current` of the 245 documents that
now carry dry-bulk TC rows reconciled against the **PDF text layer** - **2,240/2,240 =
100.0%** present. Class distribution is sane (Capesize 539 / Panamax 549 / Supramax 541 /
Handysize 581); the only garbled-class rows (28 fused `CapesizePanamaxSupramaxHandysize`
+ 2 `Capasize`) live in **untouched** documents (2021 W29, 2024 W46, 2025 W27, 2025 W04) -
pre-existing md artefacts, not introduced here.

Register re-synced: **594,163 logical rows / 170 CSVs**, `verify_registers.py` = **0
mismatches**. Combined with the sales recovery: intermodal +284 rows this run
(3,348->3,479 sales; 5,080->5,233 tc_rates).

### Still owed after this run
- The 6 label-corrupt documents and the 9 regression documents need a class-label fix
  (derive the class from the size token on the page) before their dry-bulk rows can be
  recovered - the same content-anchored principle as the sales shift fix.
- `indicative_values` and `nb_orders` also carry parser_unique > csv; not yet audited.
