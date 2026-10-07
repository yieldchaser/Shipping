# Exact-duplicate rows in the series CSVs — source verification (2026-10-07 07:0x run)

`docs/series_verification_ledger.md` section 4 item 3 claims the exact-duplicate
rows it found are "each a double count downstream". This run re-measured the
claim and tested it against each row's OWN source document. **The claim does not
hold for the rows that remain — a blanket dedupe would delete faithful rows.**

## Measured now (all 180 series CSVs)

7 files carry exact-duplicate rows (identical in every column), **31 rows total**:

| file | dup rows | total rows |
|---|---|---|
| hellenic_vv_matrix_series.csv | 15 | 12,350 |
| gibson_tanker_spot_series.csv | 5 | 3,602 |
| xclusiv_sales_series.csv | 5 | 5,542 |
| poten_top_charterers_series.csv | 2 | 756 |
| star_asia_deals_series.csv | 2 | 3,354 |
| carriers_sales_series.csv | 1 | 3,130 |
| star_asia_ferrous_scrap_series.csv | 1 | 771 |

(The files the ledger named as worst — bancosta_commodities 106, intermodal_indicative_values 75,
intermodal_tc_rates 48 — now carry **zero** duplicate rows; those were fixed after 2026-09-28.)

## Source check (pymupdf text layer of each row's own `source_file`)

No vision tool exists in this cron session; the skill's sanctioned substitute is the
same-document text reconciliation, used here.

| row | CSV rows matching the entity | entity occurrences in the source's own text | verdict |
|---|---|---|---|
| xclusiv JINGJIANG NANYANG (2025-11-10) | 5 (4 identical) | **4** | source repeats the name -> NOT a double count |
| xclusiv ZHOUSHAN CHANGHONG (2025-09-08) | 4 (2 identical) | **4** | source repeats -> NOT a double count |
| star_asia JOINT LUCK (2023 W01) | 5 | 2 | source mentions twice -> ambiguous |
| carriers LAMBADA (2024 W40) | 2 | 2 | ambiguous (table + narrative) |
| gibson "Dirty Tanker Spot" rows | 5 files | 0-1 | rows carry **no values at all** (category header parsed as data) |

The xclusiv cases are decisive: the publisher prints the shipyard name 4 times on
the page, the extractor produced 5 rows, 4 of them byte-identical. Removing the
"duplicates" would delete faithful rows the page actually carries.

## Verdict

- **Do NOT blanket-dedupe.** The doctrine "a wrong value is worse than a missing
  one" applies to deletion too: these are not proven double-ingests.
- Correct next step, if this is ever worth spending on, is **per-source**:
  (a) the 5 gibson rows are empty value-rows and are the only clean removal
  candidate, but confirm against the HTML first; (b) the rest need a per-file
  semantic read, not an automated dedupe.
- Nothing here changes any delivered value. 31 rows out of 641,177.

Scratch: `scratch/verify_dupes.py`, `scratch/verify_dupes2.py` (gitignored).
