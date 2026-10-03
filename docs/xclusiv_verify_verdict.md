# Xclusiv — verification re-run (2026-10-03, source-by-source cron)

**Verdict: the delivered xclusiv series are REPRODUCIBLE and CORRECT. The delivered md tier was STALE against a committed fix and has been brought current.**

## What was run

`python3 scripts/extract/publishers/run_xclusiv_tables.py --all` (offline PyMuPDF, no API spend, no credits).

- `[dedup] skipped 7 byte-identical duplicate document(s)`; **264 canonical PDFs**, **264 ok, 0 failed**, **455.2 s**.
- Summary printed: S&P Sales deals **5702**, Indicative Demolition Price points **2082**, Indicative Secondhand Price points **8529**, Demolition Sales deals **603**.

## Control — the numeric deliverable is byte-identical

All ten `data/extracted/series/xclusiv_*.csv` `md5sum -c` → **OK, every one unchanged** (PRE md5s at `scratch/xclusiv_audit/PRE_md5.txt`). The runner rewrites only 4 of the 10 (sales / demolition / secondhand / demo_sales); those 4 came back byte-identical, so **the typed series layer equals the current code's output over the canonical 264 PDFs**. Register unchanged: **170 CSVs / 594,101 logical rows**, `verify_registers.py` = **0 mismatches**.

Sidecar reconciliation (271 year-partitioned `.tables.json` vs the stacked CSVs): the ONLY docs whose sidecar rows are absent from the CSVs are the **7 byte-duplicate stems** — i.e. the dedup working exactly as designed. **No stacking gap.**

## The md tier WAS stale — a committed fix not yet applied to the data

`run_xclusiv_tables.py` was committed at **2026-10-02 16:15** (`a0d2d21bc fix(format): ... clean xclusiv freight commentary`); the delivered md was written **2026-10-01 20:35**. Re-running therefore regenerated the md.

- **263 of 271** md files changed. Control (stashed pre-fix copies at `data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv/`): with the **Dry Bulk Freight / Tanker Freight** sections stripped from both sides, **0 of 271 files differ**. The change is confined to exactly those two sections — nothing else lost or touched.
- Freight-section line delta across the corpus: **removed 4,433 old lines** (1,317 matching chart furniture — `$/day ... Spot Earnings`, `... 1y TC`, `BASKET`, axis/tick labels), **added 229 real commentary lines across 136 files**. The old section held chart-titles/legends/y-axis ticks pulled in by the previous `b[0] < w*0.55` predicate; the new `x < 60` predicate takes the left-margin commentary column.
- **Content verify (no vision tool in this session — stated, substituted with the PDF text layer):** for `xclusiv_2024_xclusiv-2024_03_19`, the regenerated md's Dry Bulk (5 blocks: Capesize/Panamax/Ultramax/Supramax/Handysize) and Tanker (4 blocks: VLCC/Suezmax/Aframax/Products) sections match the PDF pages 2/3 left-column text **verbatim**.

## Side effect controlled

The runner's "sync to top-level OUT_MD for backward-compatibility" branch re-created **264 flat `.md` + 264 flat `.tables.json`**. Those root duplicates had previously been stashed (809 files, `data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/xclusiv/`) — the flat+year mirror hazard. **Removed again**; the tier is back to **271 `.md` + 271 `.tables.json`, year-partitioned only, 0 flat**. min md size 3,331 B.

## Residuals (measured, not fixed)

- The register's **`publishers.xclusiv` block is stale prose**: `sales_rows 5713 / secondhand 8593 / demo_sales 618 / nb_price 1397 / rows_extracted 21135` vs delivered **5702 / 8529 / 603 / 1379 / 20975**. Pre-existing; `verify_registers.py` checks `series_inventory` + totals (0 mismatches), not this block. Left for a human, not hand-edited.
- No vision tool this session; ground truth substituted with the PDF text layer and same-document pre/post controls, as stated.
