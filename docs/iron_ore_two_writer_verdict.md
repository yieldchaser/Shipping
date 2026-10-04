# Iron-ore series two-writer hazard - the full family (measured 2026-10-04 11:xx)

Runner pair: `scripts/extract/publishers/run_hellenic_iron_ore_pdf.py` (MMi, the
dominant producer) and `scripts/extract/publishers/run_smm_iron_ore_daily.py`
(SMM). The prior run (commit 7f83a1ec6) flagged ONE file (`..._dashboard_series.csv`)
as a two-writer/wide-vs-long hazard. Measurement shows the hazard is **FIVE files**,
and one of them has already been silently damaged.

## The five colliding paths (single writer each = not true here)

Both runners write the same five `data/extracted/series/hellenic_iron_ore_pdf_*.csv`:

| file | MMi runner schema | SMM runner schema |
|---|---|---|
| ..._dashboard_series.csv | wide per-issue `dashboard_indicators` (dynamic header) | long `date,year,indicator,value,unit,change,source_file` |
| ..._indices_series.csv | `...market,fe_content,unit,price,change,change_pct,mtd,ytd,low_52w,high_52w...` | `...market_type,fe_content,value,change,change_pct...` |
| ..._brands_series.csv | `...brand,market_type,fe_pct,product_type,price,unit...` | same names (schemas align) |
| ..._futures_series.csv | `date,year,exchange,contract,price,unit,change,change_pct,settlement` | same names |
| ..._averages_series.csv | `...m_minus_4..m_minus_1,mtd,qtd,ytd` | same names |

The MMi runner writes by **full overwrite** with its own `fieldnames`; the SMM
runner **reads the whole file and rewrites it** under its own `fieldnames`
(`upsert_rows_to_csv`, `run_smm_iron_ore_daily.py:605`). The two schemas are
incompatible on three of the five.

## Realized damage (measured, not estimated)

Where the schemas diverge, the SMM upsert's `DictWriter` DROPS the foreign keys
(`price`, `market`) and emits empty cells - a silent recall loss:

| file | rows | empty value/price |
|---|---|---|
| `hellenic_iron_ore_pdf_indices_series.csv` | 11,625 | **11,553 empty `value`** (all MMi-era index rows) |
| `hellenic_iron_ore_pdf_futures_series.csv` | 2,233 | **2,207 empty `price`** |
| `hellenic_iron_ore_pdf_brands_series.csv` | 31,470 | 0 (names align) |
| `hellenic_iron_ore_pdf_averages_series.csv` | 11,556 | 172 empty `m_minus_1` |
| `hellenic_iron_ore_pdf_dashboard_series.csv` | 138 | 1 |

## Ground truth (rendered PDF text, not another extractor)

`corpus/02-hellenic/iron_ore/pdfs/2021/2021-07-19_..._1841ecdb3610.pdf` page 0 prints
`IOPI58 58% Fe Fines RMB/t` = **1197**, change **-11**, **-0.91%**.

Delivered CSV row `2021-07-19, IOPI58`: `value=''`, `change=-11.0`, `pct=-0.9`.
The change survived; **the level (1197) is absent** from `value`. Same shape at
2021-07-14 (`value=''`, change 1052.0 = the level misfiled).

## The saving grace (three-baseline check: the value is NOT lost)

`hellenic_iron_ore_table_series.csv` (a third, HTML-driven pipeline) holds the same
indices with a richer schema and the level intact:
`2021-07-14 ... IOPI58 ... fot_rmb_wmt=1240.0`; `2021-07-19 ... fot_rmb_wmt=1197.0`
- byte-matches the PDF ground truth. So the corpus does NOT lose the MMi index
levels; only `..._indices_series.csv` / `..._futures_series.csv` are internally
incomplete. **Fixing by re-fill would be worth ~zero for the KB** (data already held).

## Consumers

None. `index.html` reads `data/futures/`, `data/commodities/`, `data/derived/` only;
no script/test/app reads any `hellenic_iron_ore_pdf_*` series (grep). The register
(`EXTRACTION_REGISTER.json`, disk-driven) currently records the SMM schema + 11,625
rows for indices, i.e. it echoes the post-upsert (damaged) state.

## Recommendation (human design call - not applied)

The MMi runner is the dominant producer (sampled 119/120 corpus PDFs are 6-page MMi;
`run_hellenic_iron_ore_pdf.py` is the MMi pipeline) and owns the richer index schema.
Two clean options:

- **A (namespace split, preferred):** give the SMM writer its own names
  (`hellenic_smm_indices_series.csv` etc. - precedent: `hellenic_smm_market_drivers_series.csv`),
  then re-run the MMi runner offline from its 1,190 cached md to restore the five
  `hellenic_iron_ore_pdf_*` files with the level present.
- **B (unify):** make the MMi runner write the shared files with the SMM schema
  (`price`->`value`, `market`->`market_type`) and upsert, so both datasets merge;
  drops `mtd/ytd/low_52w/high_52w` (already in `table_series`).

Not applied this run: two prior runs deferred this as a design call and a wrong
schema choice writes wrong values (worse than missing). No data changed.
