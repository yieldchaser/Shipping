# Affinity stale-vs-runner re-check - VERIFIED, 2026-10-03 16:2x IST

Target (OVERNIGHT_STATE "NEXT-RUN TARGET"): affinity was the top candidate where the
runner was committed AFTER the delivered data (run_affinity.py c25fb48ba 2026-10-02
15:22 vs newest series CSV 2026-10-01 23:12, 16.2 h).

## What ran (a sibling job, not this supervisor)
At 16:20:16 a sibling Hermes cron job launched
`python3 scripts/extract/publishers/polish_affinity_markdown.py`
(PID 25860 -> child 24852); it had exited by 16:22:3x. This supervisor did NOT start a
competing run (two writers on the same files is the standing prohibition).

## Independent verification by this supervisor (all read-only)
- CSV control: md5 of ALL 170 `data/extracted/series/*.csv`, snapshot pre-run (16:12,
  before the sibling's 16:21 CSV write) vs post-run (16:2x) -> diff EMPTY. The 3
  affinity CSVs were rewritten (mtime 16:21) but are BYTE-IDENTICAL to the pre-run
  files. Row counts 4,020 / 741 / 494 unchanged. So the delivered series were already
  current w.r.t. the committed runner; the "16.2 h stale" candidate is CLOSED with no
  data change (reproducibility proven).
- md tier normalized: before = 254 flat `.md` (raw run_affinity.py layout, incl. 7
  residue stems) + 247 year-partitioned `.md`; after = 0 flat + 247 year + 0 `_nan_`
  residue. `.../2026/affinity_19_09_2026_affinity_tanker_weekly_18_september_2026.md`
  now carries canonical frontmatter + `## Market Indices / BDA / TCE / Commentary`
  sections; 0 of 247 files carry the raw `card panel:` / `source: corpus/...` dump
  line. This matches every other broker (flat md = 0 for star_asia 198, ssy 530,
  agora 217, intermodal 257, xclusiv 271, clarksons 180).
- Series integrity: 4,020 / 741 / 494 rows, each spanning exactly 247 distinct
  `source_file` stems; exact-duplicate rows = 0 (matches `docs/affinity_dedup_verdict.md`).
- Register: `scripts/extract/verify_registers.py` -> 170 CSVs / 594,101 logical rows,
  0 mismatches (JSON and MD), 0 control characters, no emojis. PASSED. No register
  write was needed.

## Verdict
affinity: CLOSED for the stale-vs-runner check. Series byte-reproducible, md tier back
to the single canonical year-partitioned layout, 0 duplicate rows, register consistent.

Evidence: `scratch/affinity_recheck_20261003/{pre,post}_series.md5`.
