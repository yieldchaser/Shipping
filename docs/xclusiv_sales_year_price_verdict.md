# xclusiv_sales_series.csv - vessel YEAR published as the price, FIXED 2026-10-07

Carried forward as "DISCLOSED not fixed" by `docs/carriers_sales_regen_verdict.md`
("5 rows, same class"). Re-measured this run: the >=1000 rows are 5, but the real
defect is **2 rows** whose `PRICE_USD_MILL` is the vessel's own YEAR, plus the
`ENBLOC`-propagation rows which are by design (see below).

## The defect (measured against the page, control = the SAME document)

`xclusiv_2026_xclusiv-2026_08_03.pdf` page 6, TANKER SALES table. `get_text()`
shows the price cell for DELTA AMAZON literally reading `2015 Units: 120` - the
vessel YEAR (already its own YEAR column) is repeated as the first token of the
price cell. `parse_price_mill` took the FIRST number, so the year became the price:

| vessel | YEAR | price cell | stored before | stored after |
|---|---|---|---|---|
| DELTA AMAZON | 2015 | `2015 Units: 120` | 2015.0 | **120.0** |
| DELTA ANGELICA | 2012 | `2012 Units: 116` | 2012.0 | **116.0** |

Ground truth is the same page's own narrative: *"the VLCCs 'DELTA AMAZON' - 320K/2015
Jinhai Heavy and 'DELTA APOLLONIA' - 320K/2015 ... were sold to ADNOC for USD **120**
mills each"* and *"'DELTA ANGELICA' - 320K/2012 HHI and 'DELTA GLORY' - 320K/2012 HHI
were acquired by ADNOC for USD **116** mills each"*. (DELTA APOLLONIA / DELTA GLORY
remain blank - that is a missing value, not a wrong one, the safe failure mode.)

## Fix

`extract_sales_tables` in `scripts/extract/publishers/run_xclusiv_tables.py` now
drops a leading token equal to the row's OWN `YEAR` before parsing the price, so
the year can never become the price. Anchored on the row's own year field - not on
a position or a fixed digit count.

## NOT changed on purpose - the `ENBLOC` rows

The other 3 rows `>= 1000` are `AMUNDSEN / AQUITAINE / ARDECHE` at `2,350 ENBLOC`
(2023-10-16). The page prints `2,350` in the `PRICE (usd mills)` column on the
ARDECHE row, and the same page's narrative reads *"Frontline's move to purchase 24
VLCCs from Euronav for USD 2.35 billion"* (2.35 bn = 2,350 m). The value is faithful
to the printed table; the propagation to the sibling rows is the file's existing,
deliberate `ENBLOC` semantics. Left as-is - not a parsing defect.

## Verification

- Regenerated the whole xclusiv table tier from HEAD (264 PDFs after dedup, 8 workers,
  492 s). Diff against the pre-run backup: **only `xclusiv_sales_series.csv` differs
  in content (2 rows); the other 5 series are content-identical.**
- The 2026-08-03 `.md` and `.tables.json` now print `$120.0M` / `$116.0M` instead of
  `$2015.0M` / `$2012.0M`.
- Register gate re-run: ALL PASSED, 180 CSVs / 640,870 logical rows == JSON == MD
  (row count unchanged - 2 values corrected).
