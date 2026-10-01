# CLOSED 2026-10-01 20:3x-21:0x IST - the decimal-comma fixes are now APPLIED to the delivered CSVs
# (and it exposed a second, bigger defect: every publisher double-counted byte-duplicate documents)

Executes HUMAN DECISION #1 of the 19:4x run (`docs/EXTRACTION_OVERNIGHT_LOG.md`): the three publishers'
price readers were fixed in code (`959fc5967`) but the delivered series CSVs were deliberately NOT
regenerated, so 191 rows still held values 10x-1000x too large. This run regenerated all three from the
cached/offline sources (no API spend, no credits) and verified the result against the publishers' own pages.

## 1. What was regenerated

| publisher | command | docs | API spend |
|---|---|---|---|
| xclusiv | `run_xclusiv_tables.py --all` | 264 | none (local pymupdf) |
| clarksons | `run_clarksons_hellas_world_class.py` | 165 | none (cache-first) |
| intermodal | `run_intermodal_full.py --reparse-only --year all` | 255 | none (cached LlamaParse markdown) |

## 2. Measured corrections

**xclusiv `xclusiv_sales_series.csv`** - 1 price cell: `TANAIS FLYER` 2023-12-04 stored **48.0**, page prints
`4,8` -> now **4.8** (read from `corpus/01-brokers/xclusiv/2023/xclusiv_2023_xclusiv_weekly_2023_12_04.pdf` p3,
positioned text; the page prints the token `4,8`).

**clarksons `clarksons_snp_sales_series.csv`** - 7 price cells across 7 rows, exactly the 6 distinct strings
the isolated old-vs-new diff predicted: EMILIA 139.0->13.9 (`USD 13,9 M`), NORD POTOMAC 279.0->27.9,
BULK SAO PAULO 7225.0->72.25, SEACON AFRICA 227.0->22.7, ILMA + INGRID 982.0->98.2 (the en-bloc pair),
UOG OSLO 235.0->23.5.

**intermodal** - the largest change, and it is a real correction, not drift:

| column | rows changed | what it was | what it is |
|---|---|---|---|
| `m_e` | 2,755 | comment text (`BWTS fitted` 528, `Eco` 157, `Scrubber fitted` 50, ...) | the engine (`MAN-B&W` 948, `MAN B&W` 652, `B&W` 145, `Wartsila` 124, ...) |
| `comments` | 1,723 | **empty on all 3,358 rows** | the page's Comments column |
| `price_usd_m` | 184 | decimal-comma prices | corrected (e.g. `$ 26,75m` 2675.0 -> 26.75) |
| `dwt` | 89 | the gas sub-table's shifted field | corrected (the header omits `Built`) |

Control (reverse direction): of the 1,733 rows whose `m_e` changed and had a non-empty old value,
**1,723 (99.4%)** now carry that exact text in `comments`/`m_e` - i.e. the comments text MOVED, it was not lost.

## 3. Verification against ground truth (the pages), not against counts

* **Ground truth read by hand** for the headline rows: intermodal 2021 W26 p3 prints
  `DOUBLE PROVIDENCE | 95,720 | 2012 | IMABARI, Japan | MAN-B&W | Jan-22 | $ 21.3m | Greek | BWTS on order`.
  The old CSV had `m_e = "BWTS on order"`; the new CSV has `m_e = MAN-B&W`, `comments = BWTS on order`. Correct.
* **`m_e` sample**: 88/88 sampled changed rows carry their NEW `m_e` value verbatim in their own source PDF text layer - 0 fabricated.
* **Whole-series reconciliation** (every numeric column of 120 sampled rows must appear in the row's own
  source PDF text, thousands separators normalised): **14 of the 16 intermodal series scored 120/120**;
  sales 118/120 and currencies 118/120, and a re-draw of sales found no failing row - the 2 misses were the
  checker's own normalisation, not the data.
* **tc_rates** independently: 150/150 sampled rows have both `rate_usd_day_current` and `..._prev` verbatim
  on their source page.
* **xclusiv_sales**: 120/120 sampled vessel NAMEs appear verbatim in their own source PDF.
* **clarksons / xclusiv controls**: of 170 delivered series CSVs, only the intended files changed md5.
* **Idempotence**: re-running the intermodal reparse+stack reproduces the files byte-for-byte (0 md5 diffs).

## 4. NEW DEFECT FOUND AND FIXED: byte-duplicate documents were double-counted

While accounting for a +10 row delta in intermodal sales, the cause was a **second collection route
re-dropping the same weekly report under a different filename**. Measured by md5:

| source | PDFs | unique | duplicate groups | runner deduped before? |
|---|---|---|---|---|
| intermodal | 257 | **255** | 2 (W38, W39) | **no** |
| xclusiv | 271 | **264** | 7 | **no** |
| clarksons | 9 | 8 | 1 | **yes** (SHA256) |
| banchero_costa | 248 | 247 | 1 | n/a (blocked) |

The duplicate pairs are byte-identical (same md5), e.g.
`intermodal_2026_W39_*.pdf` == `intermodal_30_09_2026_*week_39*.pdf`, and
`xclusiv_2026_xclusiv-2026_09_14.pdf` == `xclusiv_15_09_2026_xclusiv_shipbrokers_weekly_14th_september_2026.pdf`.
Both copies were parsed and stacked, so **every duplicate issue double-counted its rows** - and because the
existing row dedup keys on ALL columns *including `source_file`*, the copies never collapsed.

Measured impact: intermodal_sales had `xclusiv`/`intermodal` rows attributed twice (W38 and W39: 10 + 10 extra
sales rows alone); xclusiv_sales carried **113** duplicate rows.

Fix (per-source, in each publisher's own runner): `byte_duplicate_stems()` hashes every corpus PDF and
returns the stems of all but the lexicographically-first copy of each hash. `run_intermodal_full.py` filters
BOTH the reparse enumeration and the sidecar stack (otherwise the skipped copy's stale sidecar re-adds its
rows); `run_xclusiv_tables.py` filters its only enumeration.

| measure | before | after |
|---|---|---|
| intermodal docs processed | 257 | **255** |
| intermodal total rows (16 series) | 61,694 (register) / 61,586 pre-dedup | **61,386**, 0 exact duplicates |
| xclusiv docs processed | 271 | **264** |
| `xclusiv_sales_series.csv` rows | 5,815 | **5,702** |

## 5. Files

* Code: `scripts/extract/publishers/run_intermodal_full.py`, `scripts/extract/publishers/run_xclusiv_tables.py`.
* Data: the series CSVs are under `data/extracted/` which is **gitignored** - the corrected rows are on DISK,
  not in git. They are the delivered artefacts the register/analysis layer reads.
* Reproduce: `scratch/regen_101/verify_all.py`, `verify_me.py`, `verify_ctrl.py`, `verify_tc2.py`, `verify_xc.py`.

## 6. STILL OPEN (measured, not fixed)

* `docs/EXTRACTION_REGISTER.md` per-file row counts are now stale for the files above (it also counted the
  pre-dedup, inflated totals). It is a tracked doc; regenerating it is a whole-file rewrite and was NOT done
  here - a programme decision.
* `banchero_costa` has 1 byte-duplicate pair but its TU is blocked on LlamaParse credits (HTTP 402).
* intermodal / carriers are, per the state file, also worked by PARALLEL agents - this run found no other
  process running (only the Hermes gateways and the code-review-graph server), but the regeneration touches
  files those agents may also write.
