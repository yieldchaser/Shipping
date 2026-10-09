# Freshness by CONTENT: every live source's newest collected issue is stacked (2026-10-09 11:5x cron)

Branch `auto/extract-fixes-2026-10-08` (NOT main). No extraction runner of ours is live
(`tasklist` python.exe = 5 low-memory Hermes/gateway procs). Corpus complete; **no W41 arrival**
(newest collected broker content = **2026-10-02**, week 40).

## Method (content, not count, not mtime)

- Newest issue per source is read from the **shipped series' own `source_file` / `issue_date`**
  (`scratch/newest_inseries.py`), so a PDF that is only sitting as `.md` but never stacked is
  visible as a gap.
- Cross-checked against the corpus tree by FILENAME (`git status corpus` is blind here - corpus
  PDFs are gitignored).
- Register gate re-run independently: `python3 scripts/extract/verify_registers.py`.

## Result: newest stacked issue per source (from the series themselves)

| source | newest stacked issue | report week |
|---|---|---|
| advanced_shipping | 2026-10-02 | W40 |
| affinity | 2026-10-02 | - |
| agora | 2026-10-02 | W40 |
| banchero_costa | 2026-09-28 | W39 |
| best_oasis / hellenic recycling | 2026-10-03 | - |
| carriers | 2026-09-28 | W39 |
| clarksons | 2026-10-02 | - |
| drewry | 2026-10-01 | - |
| fearnleys (record only) | 2026-10-01 | W40 |
| gibson | 2026-10-02 | - |
| gms | 2026-10-02 | - |
| intermodal | 2026-09-29 | W39 |
| lion | 2026-10-02 | W40 |
| poten | 2026-09-18 | - |
| seabrokers | 2026-09-01 | monthly |
| signal | 2026-09-29 | - |
| ssy | 2026-09-25 | - |
| star_asia | 2026-10-02 | W40 |
| xclusiv | 2026-09-28 | - |

**Every source's newest collected issue is present in its shipped series.** Two sources are
older than the W40 cluster and both are conventions/gaps already recorded, not extraction gaps:
`seabrokers` is monthly (Sep report published 2026-09-01; current at 45 days), `poten`'s weekly
op-ed stops 2026-09-18 in the corpus (2026-09-25 / 2026-10-02 not collected - an upstream
collection gap, `docs/OVERNIGHT_STATE.md`).

## Register gate (independent re-run)

```
Disk CSV count: 180, Disk logical rows: 639,749
JSON total_master_stacked_rows: 639,749 ; JSON total_series_csvs: 180
Control characters in MD: 0 ; Emojis: False
ALL VERIFICATION CHECKS PASSED PERFECTLY (100.0% MATCH)!
```

The prior run's `count_rows()` fix held: `scripts/audit_series_inventory.py` reports
**639,749** and **0** files flagged stale (was 661,127 / 10 flagged before the fix).

## Disclosed, not fixed (unchanged, the USER's calls)

- allied en-bloc 42-row residual (needs a vision render pass; the 32 plausible lots cannot be
  bound from text when a page prints >=2 `en bloc` amounts) - `docs/allied_enbloc_residual_verdict.md`.
- hellenic bare-name `source_file` (3 builders; 427/448 ambiguous under `corpus/`).
- inventory / DB rebuild (UPSTREAM store pipeline).
- digest-tier stale `raw_pdf_path` (needs HSN/network).

## Reproduce

```
python3 scratch/newest_inseries.py                      # newest stacked issue per source
python3 scripts/extract/verify_registers.py             # register gate
python3 scripts/audit_series_inventory.py               # count-vs-register (fixed instrument)
```
