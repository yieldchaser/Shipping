# carriers_newbuilding_series.csv - two measured defects, FIXED 2026-10-07

Carried forward as "DISCLOSED not fixed" by `docs/carriers_sales_regen_verdict.md`
(which counted it as 1 bad row). Re-measured this run: it was **3 wrong-value rows
plus 7 spurious rows**, in two different documents. Both fixed at the code level in
`scripts/extract/publishers/run_carriers_complete.py`; the whole carriers tier was
regenerated from HEAD (136 PDFs, 3 byte-dup skips, 109 s) into a scratch dir FIRST
and diffed before touching the tree.

## Defect A - European decimal comma published as a 10x/1000x price (3 rows)

`parse_numeric` strips the comma, so the MIL$ column's European form was read as an
integer. Measured on the publisher's own page text (control = the SAME document):

| doc | type | printed | stored before | stored after |
|---|---|---|---|---|
| 2024 W51 | BC 82,000 | `37,3 EACH` | 373.0 | **37.3** |
| 2024 W51 | BC 63,500 | `35,3 EACH` | 353.0 | **35.3** |
| 2025 W38 | CV 8,000 TEU | `117,5 EACH` | 1175.0 | **117.5** |

Fix: the row's price now goes through the shape-based `parse_price_mill` (already
in this file and already used for the S&P price column), which takes a
`1-3 digits , 1-2 digits` token as a decimal and a `,NNN` group as thousands.
Verified no other token changes: of 170 distinct `price_raw` values, exactly these
3 differ between `parse_numeric` and `parse_price_mill`.

## Defect B - the BSPA/BDA assessment table leaked into Newbuilding (7 rows, 2024 W07)

2024 W07 stacks a Secondhand/BSPA assessment table DIRECTLY below the Newbuilding
table with NO section caption of its own, so the anchor-derived "newbuilding" band
swallowed it. 6 vessel-class assessment rows (`VLCC 305000 / 104.795`, AFRAMAX,
MR PRODUCT, CAPESIZE, PANAMAX, SUPRAMAX) and the header line
`Size / Size (MT) / Price in $m / Sentiment` were published as newbuilding orders.
3 of them carried a price (`15000`/`6000`/`7000` = the LDT range of the BDA table)
and 3 were blank.

Fix: `extract_newbuilding_rows` truncates its band at the OTHER table's own header
text - a line carrying both `Price in $m` and `Sentiment` (unique to that table).
Derived from the page, no coordinate or font size hardcoded. W07 now yields exactly
its 2 real newbuilding orders (LNG 230 EACH; CHEMICAL TANKER 6 / 38,000 DWT).

## Result and verification

- `carriers_newbuilding_series.csv` 306 -> **299** rows (7 removed).
- Control: the other **8 carriers series are byte-identical** to before (sales 3061,
  demolition 174, bspa 731, bda 366, indices 1834, weighted 655, tc_period 3144,
  tanker_tce 786 - unchanged).
- Re-derive control: every priced row's `price_usd_mill` recomputed from its own
  `price_raw` via HEAD `parse_price_mill` -> **256 priced rows, 0 mismatch**.
- The `.md` for W07 also loses the 7 spurious lines (the md is the primary
  deliverable and renders the RAW token, so the 3 price fixes do not show in md).
- Register gate re-run: `scripts/extract/verify_registers.py` = ALL PASSED,
  180 CSVs / **640,870** logical rows (was 640,877; delta -7) == JSON == MD.
