# hellenic `iron_ore_pdf_*` two-writer family - ROOT-CAUSED (2026-10-04)

The carried item "the `hellenic_iron_ore_pdf_*` two-writer family (5 files, 2 with
11,553/2,207 empty values)" is here root-caused and measured. **Not changed** - the
repair is a schema/ownership decision the human list reserved. Evidence below is
reproducible from the files on disk plus the source PDF's own text layer.

## The two writers

Two runners write the SAME five CSV filenames in `data/extracted/series/`:

| file | `run_hellenic_iron_ore_pdf.py` (old MMI 6-page format) | `run_smm_iron_ore_daily.py` (new SMM 1-page format) |
|---|---|---|
| `..._indices_series.csv` | `date,year,index_name,`**`market`**,`fe_content`,`unit,`**`price`**,`change`,`change_pct,`**`mtd,ytd,low_52w,high_52w`**`,source_file` | `date,year,index_name,`**`market_type`**,`fe_content,`**`value`**,`unit,change,change_pct,source_file` |
| `..._brands_series.csv` | `date,year,market_type,`**`benchmark_grade`**`,brand,price,unit,change,`**`diff_to_benchmark`**`,source_file` | `date,year,brand,market_type,`**`fe_pct,product_type`**`,price,unit,change,`**`change_pct`**`,source_file` |
| `..._futures_series.csv` | `date,year,exchange,contract,unit,`**`closing_price`**`,change,change_pct,`**`vol_traded_k_lots,open_positions_k_lots,day_low,day_high`**`,source_file` | `date,year,exchange,contract,`**`price`**,`unit,change,change_pct,`**`settlement`**`,source_file` |
| `..._averages_series.csv` | same schema as SMM -> **no loss** | same schema |
| `..._dashboard_series.csv` | dynamic keys | `date,year,indicator,value,unit,change,source_file` |

Bold = columns present in one writer and absent from the other.

## The mechanism (data loss on write)

`run_smm_iron_ore_daily.py` writes via `upsert_rows_to_csv()` (line 605). It reads
the existing rows as dicts, then writes them back with **its own** `all_fields` and
`csv.DictWriter(..., extrasaction="ignore")`:

```
sorted_rows = sorted(existing_rows.values(), ...)
writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
writer.writerows(sorted_rows)          # old-schema keys are silently DROPPED
```

So the moment `run_smm` first ran, every pre-existing old-format row lost the columns
that only `run_hellenic` produces (`market`/`price`/`mtd`/`ytd`/`low_52w`/`high_52w`,
`benchmark_grade`/`diff_to_benchmark`, `closing_price`/`vol_traded_k_lots`/...), and
gained the SMM-only columns as blanks. The keys common to both (`change`,
`change_pct`, `price` in brands) survived.

## Measured loss (current files on disk)

| file | rows | columns effectively empty |
|---|---|---|
| `indices_series.csv` | 11,625 | `market_type` **11,553** (99.4%), `value` **11,553** (99.4%) |
| `brands_series.csv` | 31,470 | `fe_pct` **31,272**, `product_type` **31,272**, `change_pct` **31,272** |
| `futures_series.csv` | 2,233 | `price` **2,207**, `settlement` **2,207** |
| `dashboard_series.csv` | 138 | 1 row (a fully blank row) |
| `averages_series.csv` | 11,556 | none beyond genuine era gaps |

Only the 72 rows written by the SMM runner (2026-09-14 onward, keyed on
`market_type='port_spot'` etc.) carry `value`.

## Ground truth read from the page (not another extractor)

`corpus/02-hellenic/iron_ore/pdfs/2021/2021-07-14_..._b472c50b9ce5.pdf`, page 2
(`pymupdf` text layer). The **benchmark** table prints IOPI58:
`58% Fe Fines | Price 1240 | Change -17 | Change % -1.4% | MTD 1251 | YTD 1104 | Low 755 | High 1421`
(RMB/wet tonne), plus the USD CFR-equivalent `181.87 / -2.69 / -1.5% / 183.71 / 161.71`.

The delivered `indices_series.csv` row for that date/name is:
`{'index_name':'IOPI58','fe_content':'58% Fe Fines','unit':'RMB/wet tonne',`
`'value':'','change':'1052.0','change_pct':'1267.0'}`.

So **`value` is empty** (should be 1240) and **`change`/`change_pct` are not this
row's** values - 1052 and 1267 are the **April and May** figures from the separate
multi-period statistics table (same page, `pymupdf` lines 474/475: IOPI58 March 1027,
April 1052, May 1267, June 1199, MTD 1251, YTD 1104). A consumer reading
`indices.change` gets a wrong number; `indices.value` gets nothing.

Two independent faults are therefore visible on that one cell:
1. the **schema collision** above (the old `price` column is gone, `value` blank), and
2. a **row-selection** fault in `run_hellenic_iron_ore_pdf.py`'s indices parse (it
   matched the statistics table's IOPI58 row for `change`/`change_pct`, not the
   benchmark row). Confirming fault 2 fix-ready needs the cached markdown
   (`data/extracted/cache_mmi_iron_ore_pdf/`), which is present, so a re-run is API-free.

## Why not fixed unattended

This is an ownership/schema decision, not a one-line bug: the two runners cannot both
write one file without loss. Options:
- **(a) union-preserving upsert** - change `upsert_rows_to_csv` to write
  `all_fields = existing_header ∪ new_fields` so neither writer drops the other's
  columns, then re-run `run_hellenic` (cached, free) then `run_smm`.
- **(b) split the files** per era (e.g. `..._indices_series.csv` vs
  `..._indices_smm_series.csv`) - cleanest, but renames outputs a consumer might read.
- **(c) retire `run_hellenic_iron_ore_pdf.py`** for these five files and accept loss of
  the old-format columns (rejected: it discards the IOPI benchmark price history).

No consumer in `index.html` references these five CSVs (0 hits); references are tooling
only (`sync_extraction_register.py`, `generate_cadence_audit.py`), so (a) is low-risk.

`averages_series.csv` is already schema-compatible and needs no change.
