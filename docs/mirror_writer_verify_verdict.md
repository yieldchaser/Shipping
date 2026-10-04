# Mirror-writer (last-writer-wins) sweep - 2026-10-04

Scope: every `data/extracted/series/*.csv` (170 files), for the class of defect
fixed for the Athenian mirror on 2026-10-03 (two runners writing one path ->
last writer wins). Read-only on corpus.duckdb; no git operations; no API spend.
No live extraction job was running (machine idle since 2026-10-03 23:20).

## Method
For each series filename, find every script under `scripts/` that contains the
exact quoted literal AND opens it for write (`to_csv` / `open(...,"w")` /
`writerow`) within 400 chars. Substring false positives (e.g.
`best_oasis_deals_series.csv` inside `hellenic_best_oasis_deals_series.csv`)
were excluded by requiring the exact quoted literal.

## Result A - register was STALE by the last in-flight change (FIXED)
`verify_registers.py` (before): rows on disk were 7 fewer than the register.
Two mismatches, both the files the 2026-10-03 VV dedup rewrote:
  hellenic_vv_matrix_series.csv           disk=12350 vs json=12340
  hellenic_vv_benchmark_sales_series.csv  disk=124   vs json=141
Re-synced with `scripts/sync_extraction_register.py` (authoritative, disk-driven).
`verify_registers.py` (after): 0 mismatches, "ALL VERIFICATION CHECKS PASSED".
Register total_master_stacked_rows 597,779 == disk logical rows 597,779.

## Result B - hellenic_* mirrors had TWO writers, divergent (FIXED for 3)
The `hellenic_*` demolition series are owned by `run_hellenic_demolition.py`
(its docstring lists them; the register's canonical counts match its output;
the Athenian fix already removed the Athenian mirror from its own runner).
The per-publisher runners still mirrored into the same paths, with DIFFERENT
schemas/counts - a real last-writer-wins hazard:

| path | owner (kept) | redundant writer (removed) | live rows | other writer would write |
|---|---|---|---|---|
| hellenic_gms_port_positions_series.csv | run_hellenic_demolition.py (7-col) | run_gms_demolition.py (10-col, port_csv2) | 2,931 | 2,905 (10-col) |
| hellenic_gms_demolition_series.csv | hellenic runners | run_gms_demolition.py (rankings_csv2) | 448 | 1,092 (11-col) |
| hellenic_best_oasis_deals_series.csv | run_hellenic_demolition.py | run_best_oasis_demolition.py (v_mirror) | 514 | 887 |
| hellenic_best_oasis_demolition_series.csv | run_hellenic_demolition.py | run_best_oasis_demolition.py (p_mirror) | 233 | 863 |
| hellenic_athenian_demolition_series.csv | run_hellenic_demolition.py | (run_athenian_demolition.py mirror) | 2,916 | - already fixed 10-03 |

Fix applied (uncommitted, matches the Athenian precedent): removed the
`for ... in [own, mirror]` mirror writes from `run_gms_demolition.py` (port +
rankings) and `run_best_oasis_demolition.py` (demolition + deals). Own-file
writes left intact. `py_compile` OK on both. Control: md5 of all five
hellenic_ live CSVs byte-identical before vs after (no data touched).

## Result C - one overlap REMAINS (needs an ownership call, NOT edited)
`hellenic_gms_demolition_series.csv` (448 rows, live mtime 2026-10-02 22:24) is
still written by BOTH:
  - scripts/extract/publishers/run_hellenic_demolition.py:575
  - scripts/extract/publishers/run_hellenic_gms_demolition.py:319 (a dedicated
    runner, mtime 2026-09-30)
Both are "hellenic" runners, so the canonical owner is not self-evident.
Next run: determine which produces the registered 448-row output, retire the
other's write, and re-verify. Do NOT edit blind.

## Not real (scanned and cleared)
- `orchestrate_incremental_ingest.py` appears for many series: generic
  orchestrator, not a per-source writer of those names.
- `scripts/audit/*` mentions are readers/records, not writers.
- `stack_unstacked_tables.py`, `extract_week39_supplements.py`,
  `process_banchero_2026_w36_w38.py`, `build_banchero_series.py`,
  `run_clarksons.py`, `run_lion_tables.py`, `run_carriers.py`,
  `run_hellenic_iron_ore_pdf.py`, `run_smm_iron_ore_daily.py`: mention but do
  not both open the same path for write in the overlap set after checking the
  exact-literal rule (flagged here for completeness; each writes a distinct
  path or a single-owner pair).

Note: `hellenic_iron_ore_pdf_dashboard_series.csv` is written by
`run_hellenic_iron_ore_pdf.py` (full rewrite, `"w"`) AND
`run_smm_iron_ore_daily.py` (upsert by key) - flagged, NOT fixed: the two have
different semantics (overwrite vs merge) and a different publisher (SMM vs the
Hellenic iron-ore PDF), so it needs an explicit ownership decision.
