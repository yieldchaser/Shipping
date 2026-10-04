# GAP-verify re-check against the CURRENT corpus DB (2026-10-04 22:3x)

Run: 2026-10-04 ~22:2x-22:3x (overnight supervisor cron). No extraction job of
ours was running; a PARALLEL agent's `scripts/breakwave_insights_scraper.py
--year 2026` (PID 20724, started 22:28:58) was live, so this run kept OFF all
breakwave/broker outputs. DB read-only.

## Why
`data/extracted/gap_verify.json` was generated 2026-09-22, i.e. against the
PRE-rebuild corpus.duckdb. The DB was rebuilt 2026-10-03 and the v3 views applied
2026-10-04 17:34. Its two CONSTRUCT-survivor rebuttals were therefore re-verified
on the current DB. Artefact `data/extracted/gap_verify_recheck.json`.

## Current DB headline counts (vs the numbers gap_verify was written against)
  catalogue 189,481 | cells 6,726,703 | series 5,743 | series_points 1,193,579 | label_series 1,619,891
  (gap_verify 2026-09-22 baselines: series 5,123 / points 1,193,415 - points +164, series +620.)

## Claim 1 - ssy named Capesize trades = PRESENT (reconfirmed)
label_series, source='shipbrokers', doc_stem LIKE '%ssy%': 500 issues / 14,944 labelled cells.
14 named $/t routes present, each at 130-131 issues (DAMPIER/QINGDAO, RICHARDS BAY/MUNDRA,
RICHARDS BAY/ROTTERDAM, RICHARDS BAY/FANGCHENG, TUBARAO/JAPAN, TUBARAO/ROTTERDAM, TUBARAO/QINGDAO,
CAPE LAMBERT/ROTTERDAM, QUEENSLAND/JAPAN, QUEENSLAND/ROTTERDAM, NARVIK/ROTTERDAM,
PUERTO BOLIVAR/ROTTERDAM, SALDAHNA BAY/QINGDAO, SEVEN ISLANDS/ROTTERDAM).
T/C legs present: T/C TRANSATLANTIC ROUND 132, T/C TRIP CONT/FAR EAST 131,
T/C TRANSPACIFIC ROUND 131, T/C TRIP FAR EAST/CONT 131. 'Calculated Index' 260 issues.
=> NOT genuinely missing. Matches gap_verify's "131-132 labelled issues per route".

## Claim 2 - carriers composite indices = PRESENT (reconfirmed)
cells, doc_stem LIKE '%carrier%': 2,623 index-name cells across 127 issues.
Per index (distinct issues): DSPA/BSPA/TSPA/DSRA/TSRA/BSRA = 127 each; BNBI/DNBI/TNBI = 112 each.
series layer holds only 49 carrier-mention series under 'shipbrokers' - the composite
indices are NOT promoted, but their raw cells exist. Matches gap_verify's "112-136 issues per index".
=> NOT genuinely missing; the sweep queried only series/series_points.

## Verdict
BOTH CONSTRUCT survivors remain FALSE CONSTRUCTS on the current DB. gap_verify reproduced.
