# carriers - duplicate-key regeneration VERDICT (2026-10-03)

**Status: EXECUTED and PROVEN.** The two-rule duplicate guard committed at `57d064c09`
(`run_carriers_complete.py`) was APPLIED to the delivered data by re-running the source's own
pipeline. The earlier run shipped only the CODE fix and left the delivered CSVs stale, flagged as
"human decision #1". That decision is now taken: the delivered CSVs ARE the artefact the app/DB read,
and `data/extracted/**` is gitignored, so a re-run is the only way the fix reaches them.

## Command

    export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"
    python3 scripts/extract/publishers/run_carriers_complete.py

136 corpus PDFs, 133 processed, 3 SKIP lines (one per byte-identical pair). The module REBUILDS all
nine series with `open(..., "w")` (no merge-map), so the guard takes effect in one pass.

## Measured before -> after (delivered `data/extracted/series/carriers_*_series.csv`)

| series | before | after | removed |
|---|---|---|---|
| carriers_sales | 3,130 | 3,061 | 69 |
| carriers_dry_tc_period | 3,216 | 3,144 | 72 |
| carriers_indices | 1,876 | 1,834 | 42 |
| carriers_tanker_tce | 804 | 786 | 18 |
| carriers_bspa | 749 | 731 | 18 |
| carriers_dry_weighted_routes | 670 | 655 | 15 |
| carriers_bda | 375 | 366 | 9 |
| carriers_newbuilding | 312 | 306 | 6 |
| carriers_demolition | 178 | 174 | 4 |
| **total** | **11,310** | **11,057** | **253** |

## Control

Key = every column except `source_file`. `PRE minus POST` is an exact multiset count of **253 removed,
0 added** on all nine series (per-series removed == per-series delta, added == 0 everywhere).
The three skipped stems:

    carriers_2026_W35_WK-35-26-CARRIERS_SP-MARKET-REPORT.pdf   (keeper 15_09_2026_..._week_37 (2).pdf, covers Week 35)
    carriers_2026_W38_WK-38-26-CARRIERS_SP-MARKET-REPORT.pdf.pdf   (keeper ...REPORT.pdf)
    general_broker_28_09_2026_carriers_sales_purchase_market_report_week_39.pdf   (keeper carriers_2026_W39_...)

## Residual - 1 duplicate key REMAINS in carriers_sales (publisher-side, NOT a parser defect)

`carriers_sales_series.csv` still holds one duplicate key (the earlier sandbox reported 0 - it missed
this). Both rows are from the SAME document, same page:

    issue_date=2024-09-30 week=40 section=tankers page=1 LAMBADA TANKER 104,866 2006
    Samsung Heavy Inds - Geoje 30.00 UNDISCLOSED
    source_file=carriers_2024_W40_WK-40-24-CARRIERS_SP-MARKET-REPORT.pdf (x2, page 1)

The source page prints the vessel TWICE: positioned-text bboxes at y=303.5 AND y=337.7 (34.2 pt apart
= 3 row pitches), x0 identical (52.2), separated by ELIJAH (y=314.9) and ES SPIRIT (y=326.3) in the
same "Tankers / LPG Vessels Reported Sold" table. This is a PUBLISHER double print in the PDF, and our
row is faithful. Left AS-IS: suppressing it would be a judgement call on a single row, the byte-pair
guard cannot see it (one document, not a copy), and the source genuinely lists it twice. Recorded so
the next census does not re-flag it as an extraction bug.

## Notes

* `data/extracted/**` is gitignored (`.gitignore:73`), so the regenerated CSVs are working-tree
  deliverables - they are NOT committed. Only docs/scripts are versioned.
* md tier: 133 flat `.md` + 133 `.tables.json` written for the 133 processed docs. The 3 skipped
  stems had NO md on disk, so no orphan md/sidecar to quarantine (unlike ssy/affinity/fearnleys).
  An older year-subdir mirror (137 md) still exists alongside the flat dir, as for ssy/ism; not
  restructured here.
