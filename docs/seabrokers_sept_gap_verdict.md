# Seabrokers September 2026 gap - verdict (2026-10-08)

**Gap:** every `seabrokers_*_series.csv` stopped at **report_date 2026-08-01**. The
**September 2026** report (`corpus/05-seabrokers/pdfs/2026-09-01_market-report-september-2026.pdf`,
arrived 2026-10-02) existed as LlamaParse md + cache + catalog row, but its data was
never stacked. Same class as the agora 2026-10-08 W40 gap.

## Root cause (measured)
The 8 seabrokers series come from `data/extracted/seabrokers_extended.parquet` via
`scripts/extract/publishers/export_seabrokers_series.py`. That parquet (mtime
2026-09-22, **max report_date 2026-08-01**) was built by the scratch pipeline
`scratch/seabrokers_ext/{01_inventory,02_extract,03_build}.py`, whose input is the
store tier `data/extracted/corpus/seabrokers/<doc>/` - which held only **96 docs**
(max 2026-08-01). The September doc was never extracted into the store.
Separately, the reused ledger `data/derived/seabrokers_osv_dayrates.csv` **already
held** Sept (375 rows, max 2026-09-01) - the parquet simply predated it.

## Fix (local, no API spend)
1. `python3 scripts/extract/extract_all.py corpus/05-seabrokers/pdfs/2026-09-01_market-report-september-2026.pdf --out <tmp>` -> **32 s**, 15 pages, text 87 KB / tables 79 KB (August: 90/71 KB). Placed at `data/extracted/corpus/seabrokers/2026-09-01_market-report-september-2026/` (store now 97 docs).
2. Re-ran `02_extract.py` (8 s) -> `rows.jsonl` 16,125 -> **16,323** (+198, 0 removed).
3. Re-ran `03_build.py` -> parquet 16,323 rows.
4. Re-ran `export_seabrokers_series.py` -> 8 CSVs.

## Measured result (per-series, pure additions)
| series | before | after | +rows |
|---|---|---|---|
| osv_spot_rates | 1,855 | 1,875 | +20 |
| osv_monthly_history | 6,280 | 6,364 | +84 |
| osv_utilisation | 2,304 | 2,328 | +24 |
| rigs_market | 4,467 | 4,482 | +15 |
| snp_auctions | 251 | 281 | +30 |
| fleet_moves | 197 | 203 | +6 |
| feature_vessels | 64 | 75 | +11 |
| renewables_and_ets | 16 | 16 | 0 |

`git diff --numstat` on the 7 changed CSVs: **+200 / -0** (no existing row altered;
the renewables file was restored byte-identical). Register total 640,917 -> **641,107** (+190).

## Verification
- **Control:** diff of each changed CSV vs its pre-fix copy, sorted and `tr -d '\r'`
  (pandas writes CRLF; git normalises to LF): **0 removals, all additions at
  report_date 2026-09-01**. (Raw byte diff was 100% lines = EOL artifact.)
- **Two engines agree + match the PDF:**
  - PDF text layer (pymupdf): utilisation `SEP 2026` = **87 / 79 / 52 / 61**;
    avg rates = **£18,250 / £22,275 / £66,231 / £110,702**; feature vessel
    `ACE ARISTOTELIS` (`Breeze Z4423 PSV`). All present.
  - Series rows carry exactly those values (period 2026-09).
  - S&P auctions: 30 Bourbon results (Evolution 808 @ 52.06 USDm, etc.) - matches
    the md "Newbuilds, Conversions, S&P". Fleet moves: BEAR/BOKA FULMAR/BOULDER
    arrivals, MH FREEDOM/PACIFIC DISCOVERY/SKANDI HERA departures - matches the page.
- **Register gate GREEN:** 180 CSVs / **641,107** logical rows == JSON == MD, 0 mismatches.

## Note
The extended-parquet pipeline lived only in `scratch/` (gitignored). Copied to
`scripts/extract/publishers/seabrokers_ext/` so the rebuild is reproducible.
`data/extracted/**` is gitignored, so the store doc + parquet are local artefacts;
the source PDF is tracked under `corpus/`.
