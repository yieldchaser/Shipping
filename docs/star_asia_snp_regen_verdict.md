# Star Asia S&P series regeneration - supervisor run 2026-10-03 17:25-17:40 IST

## What was parked
The 3-hourly deep-review job fixed `run_star_asia_tables.py` at 15:29
(commit `886f1addb`, verified before/after harness) but deliberately did NOT write
`data/extracted/**`, leaving "regenerate the series" as a human decision. At the
17:24 hourly check the delivered `star_asia_snp_sales_series.csv` was still 0 rows
(mtime 2026-10-02 08:39). Code fixed, data not rebuilt = in-flight work parked.

## Action (local, no PDF re-parse cost beyond free pymupdf text, no credits)
`python3 scripts/extract/publishers/run_star_asia_tables.py` -> 197 PDFs (2 byte-dup
skipped), 197 sidecars updated, 387 indicative tables repaired. Exit 0.

## Measured result
| series | before | after |
|---|---|---|
| star_asia_snp_sales_series.csv | 0 rows | **3,575 rows / 192 docs / 0 dup rows** |
| star_asia_deals_series.csv | 3,349 rows | 3,349 rows (byte-identical, md5 9aefc3a3) |
| star_asia_demolition_series.csv | 3,116 rows | 3,120 rows (+4, repaired indicative tables) |

Ground truth: sidecar row 1 of `star_asia_2022_W29_...` = THERESA SHANDONG / KMAX /
82,000 / 2012 / CHINA / 22.0 / GREEK BUYERS; the rebuilt CSV row 1 is identical.

## Register
`sync_extraction_register.py` + `verify_registers.py` -> 170 CSVs / 597,786 logical
rows / 0 mismatches (JSON and MD), 0 control chars, no emojis. Section-1 Star Asia
line corrected 3,717 -> 3,575 (snp), 3,120 (demolition), 3,349 (deals); the
"17,079 rows total across 10 series" parenthetical -> 16,994 (summed from disk).
A star_asia substitution block was added to `sync_extraction_register.py` so the
Section-1 line stays disk-derived on every future sync (it previously updated only
ssy/carriers/lion/best_oasis); the hardcode in
`scripts/extract/update_extraction_register.py:155` was corrected to match.

Left uncommitted on branch `auto/extract-fixes-2026-10-03-star-asia-snp` (no git
write performed by this run).
