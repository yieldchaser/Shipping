# Intermodal newbuilding recall verdict (2026-10-03)

## What was owed
The 2026-10-03 intermodal sales/tc-rates run closed two recall gaps but left a
per-document row-count audit of the REMAINING series owed. This run executed that
audit across all 16 intermodal series.

## The audit (instrument)
`scratch/intermodal_audit/audit_all_dedup.py` re-runs the current parser
(`run_intermodal_full.parse_all_intermodal_tables`) over the 255 non-duplicate
cached md files and compares, PER SERIES PER DOCUMENT, the parser's **unique**
row count (deduped on the full column tuple) against the delivered CSV row count.

The first pass used the RAW parser row count and was WRONG: `intermodal_2026_W12`
showed "32 rows vs 20 CSV", but 12 of the 32 were the same tanker block appearing
twice in the md (an exact repeat). Deduping on the column tuple collapsed 32 -> 20
and the "gap" vanished. **A raw parser count double-counts repeated md blocks;
dedup before believing a gap.**

## Result (deduped, 255 docs)
| series | csv | parsed_unique | gap docs | recoverable |
|---|---|---|---|---|
| tanker_spot | 3,885 | 3,419 | 0 | 0 |
| **tc_rates** | 5,233 | 5,125 | 6 | 48 |
| indicative | 2,360 | 1,091 | 0 | 0 |
| baltic | 1,255 | 1,073 | 0 | 0 |
| currencies | 684 | 680 | 0 | 0 |
| sales | 3,479 | 3,367 | 0 | 0 |
| **nb_prices** | 3,170 | 3,030 | 4 | 19 |
| **nb_orders** | 1,864 | 1,873 | 7 | 31 |
| demo_prices | 2,040 | 1,952 | 0 | 0 |
| demo_sales | 580 | 570 | 0 | 0 |

- The 6 `tc_rates` gap docs are exactly the KNOWN label-guard skips (2023 W21/W24/
  W29/W30/W31/W33) - LlamaParse stamps one class on every dry-bulk row there;
  deliberately skipped (a wrong class is worse than a missing row). Not reopened.
- The remaining real candidate gaps: **nb_orders (7 docs, +31)** and
  **nb_prices (4 docs, +19)** - all 2022-2023.

## Verified real, not a metric
Cause is the same stale-sidecar class as the earlier sales fix: the sidecar's
`newbuilding_orders` / `indicative_newbuilding` key predates the current parser.
`intermodal_2022_W03`'s sidecar held **0** newbuilding orders; the source PDF
**page 6** prints 7 order rows (Asiatic Lloyd / PZM / NYK / MSC / X-Press /
Sea Consortium), and `pymupdf` page text (INDEPENDENT of LlamaParse) contains
every size+yard token.

Per-doc grounding of the parser's rows against the SOURCE PDF's own text layer
(size + yard / vessel_type + size):
- nb_orders, 7 docs: **7/7, 6/6, 4/4, 4/4, 4/4, 3/3, 3/3 = 31/31 grounded** (one
  token miss - "Japanese (Doun Kisen)" is printed only as prose "Japanese Doun
  Kisen" in that doc; the row's size+yard are grounded).
- nb_prices, 4 docs: **18/18, 18/18, 18/18, 17/17 grounded**.

## Fix
`scratch/intermodal_audit/refresh_nb.py` rewrote ONLY the correct sidecar table keys
for those 11 docs (`newbuilding_orders` x7, `indicative_newbuilding` x4) from a
fresh parse, then `run_intermodal_full.py --year all --stack-only` re-stacked.

| series | before | after | delta |
|---|---|---|---|
| intermodal_newbuilding_orders_series.csv | 1,864 | **1,895** | +31 |
| intermodal_newbuilding_prices_series.csv | 3,170 | **3,189** | +19 |
| intermodal_newbuilding_series.csv (union) | 5,034 | **5,084** | +50 |

0 duplicate keys on all three.

## Control (byte-level)
md5 of all 170 series CSVs before/after: **only the 3 newbuilding files changed**;
the other **167 byte-identical**.

## Delivered-row content verify
Rows now in the delivered CSVs for the 11 gap docs, checked against the source PDF
text layer: nb_orders **31/31 = 100%**, nb_prices **71/71 = 100%**.

## Register
`scripts/sync_extraction_register.py` re-run: 170 CSVs / **594,263 logical rows**;
`verify_registers.py` = **0 mismatches**. Section-1 Intermodal row hand-updated to
5,084 / 3,189 / 1,895 and total **62,809 -> 62,909 rows across 16 series**.

## Residuals (measured, not fixed)
- tc_rates 6 label-guard docs (2023 W21/W24/W29/W30/W31/W33) still skipped - the
  one documented, deliberate guard.
- Several series show CSV RICHER than a fresh parse (tanker_spot 3,885 vs 3,419;
  indicative 2,360 vs 1,091; 30/244/38 "regress" docs). This is the known fact
  that the current md is POORER than the sidecars for those series; do NOT
  blanket-reparse them.
- No vision tool in this session - substituted same-document PDF-text
  reconciliation, and say so.
