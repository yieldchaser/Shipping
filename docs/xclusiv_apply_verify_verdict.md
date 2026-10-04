# Xclusiv doubled-text-layer fix: APPLIED TO DELIVERED DATA + verified

Run: hourly supervisor cron 345bc8db9233, 2026-10-04 ~11:49-12:02 IST.

The 3-hourly deep-review job (09:50 run, commit 429e5556b on branch
auto/extract-fixes-2026-10-04) fixed the parser defect in
scripts/extract/publishers/run_xclusiv_tables.py (_dedupe_words) but LEFT THE
DELIVERED CSVs UNCHANGED - it flagged a one-publisher re-run as a human item.
That parked apply-and-verify was the highest-value open action with no design
decision attached, so the supervisor applied it this run.

## Defect (ground truth = rendered PDF page 4 of xclusiv_2021_weekly_2021_10_4.pdf)
The page draws every word twice at ~0.12pt offset; the runner bucketed both.

## Action
python3 scripts/extract/publishers/run_xclusiv_tables.py --all
(local PDFs, 0 LlamaParse credits, 264 docs, 8 workers, 546.7s, EXIT=0).

## Measured result (before vs after; backups in scratch/sup_xclusiv_apply_20261004/)
- 4 series CSVs rewritten; row counts UNCHANGED: sales 5,703 / demolition 2,083 /
  secondhand 8,530 / demo_sales 604.
- xclusiv_sales_series.csv: exactly 18 data lines changed, all on issue 2021-10-04
  (the one overprinted page). 0 changes in the other 3 CSVs.
- All 18 vessel NAMES now single (was "CONRAD CONRAD", "AMIRA AMIRA ILHAM ILHAM", ...).
  Example: CONRAD | Capesize | 207,647 | 2017 | CHINA | SWS | JP MORGAN | $54 | 54.0.
- Residual (disclosed, NOT fixable by same-string dedupe): 3 rows keep doubled
  NON-name fields - OCEAN GINGER (price/comment tail) and the SHUANG XIN HUA XI /
  XIN SHUANG HUA XI pair, whose two overlapping layers carry DIFFERENT vessels
  (93,237 vs 82,269 DWT). Left as-is, not guessed.

## Determinism control
CSV diff confined to the single page; deep-review had already shown 25/25 sampled
PDFs byte-identical pre/post and 0 differences across the other 5 extractors.

## Side effect I introduced and REVERTED
The runner also syncs a top-level copy of each .md/.tables.json "for backward-
compatibility" into data/extracted/md/xclusiv/. No other publisher keeps top-level
copies (advanced_shipping/star_asia/fearnleys/intermodal/banchero all = 0 top-level),
and xclusiv pre-run = 0. The re-run created 264 top-level .md + 264 .tables.json;
ALL were removed (0 older than 11:49 remained). Year-dir md = 271 restored.

## Integrity
scripts/extract/verify_registers.py: 170 CSVs / 599,512 rows, JSON+MD mismatches = 0.
No git operations performed (data/extracted is gitignored).
