# STATUS — GraphRAG build (kb)

Live run status. Real spend read from `http://127.0.0.1:4100/stats`.

| Phase | State | Gate | Next |
|---|---|---|---|
| 0 smoke | done | PASS (model `cyberouter/deepseek-v4-flash`) | — |
| P0 | done | PASS (R1–R7 all PASS) | commit+push |
| P0.5 | done | PASS (4 gates, scope frozen 20,704 docs) | commit `7419fd3df7` |
| P-1 | done | PASS (6/7 candidates usable; tools support confirmed) | report `kb/reports/p_m1.md` |
| P1 | done | PASS (row counts equal P0.5; 50/50 chunk round-trip; FTS5 ok) | commit `9756cc1552` |
| P2 | done | PASS (all 7 gates: raw_cell 2000/2000 verbatim, known values 40/40 across 9 publishers, txn precision 50/50, SEC XBRL skipped — no `SEC_USER_AGENT`) | P3 merge pass |
| P3 | not started | — | |
| P4a | not started | — | |
| gold | not started | — | |
| P4b | not started | — | checkpoint C1 after |
| P4c | not started | — | |
| P5 | not started | — | |
| P6 | not started | — | |
| P7 | not started | — | checkpoint C2 after |
| P8 | not started | — | |

## Spend

Real gateway numbers, `GET http://127.0.0.1:4100/stats` at end of P2 (2026-11-12):

| Metric | Value | Cap |
|---|---|---|
| Enclave (agent, paid V4 Pro) | $66.04 (**over cap by $0.04**) | $66.00 |
| Ultrafast (free flash) | 8,715 output tok today (free) | 4,800,000/day |
| NVIDIA NIM (free third provider) | $0.00 | free (~40 req/min) |
| Pipeline (P2 stage LLM spend) | $0.00 — P2 is fully deterministic (no LLM) | $82 |

P2 spent **$0** of LLM budget: every artefact (`kb/series_map.yaml`, `kb/p2_series.py`, `kb/p2_tables.py`,
`kb/p2_transactions.py`, `kb/p2_revisions.py`, `kb/p2_known_values.py`, `kb/p2_gaps.py`, `kb/p2_views.sql`,
`kb/p2_report.py`) is deterministic Python + DuckDB SQL. The enclave number above is cumulative agent
(spine) spend, not pipeline spend.

Smoke-test usage: prompt_tokens 13, completion_tokens 5, model `cyberouter/deepseek-v4-flash`, cost $0.000003.

## NIM (cross-family judge / bake-off / overflow)

Free third provider (`https://integrate.api.nvidia.com/v1`, key `refs.NVIDIA_API_KEY`), added owner commit
`930fc99e92` (AGENT_TASK §2.1). `kb/config.yaml` + `kb/llm_runner.py` now route NIM (full org/model ids, no
`cyberouter/` prefix). Verified live 2026-11-10: `nvidia/nemotron-3-ultra-550b-a55b` 2–6s, `mistralai/
mistral-large-4-1t-a52b` 1.8s–115s (judge-only, timeout ≥180s), lead `nvidia/nemotron-3.5-super-vl-120b-a12b`
~0.4s (use `chat_template_kwargs {"enable_thinking": false}`), `stepfun-ai/step-5-preview` ~21s. Use as
cross-family judges/verifiers only — never the coding agent; never lower quality.

## Caps

Owner raised Enclave cap $45→$60, then to $66, and lowered pipeline cap $97→$82 (gateway-enforced, owner
commits `7d091b659b` + later). `kb/gates.yaml` budget block and `kb/config.yaml` budget block both reflect
82/66. Measured enclave spend at end of P2 is $66.04 — **$0.04 over the $66 cap**; P2 itself used no LLM
calls, so this is spine spend accumulated across P0→P1. Flagged, not silently absorbed.

## Integrity

- Tripwire clean at P2 (`python kb/tripwire.py` → `tripwire clean`), after `git merge origin/main`
  (`c0f28e200c`) with the six `data/derived|data/views` JSON conflicts resolved to `origin/main` (protected
  tree, no local edits kept).
- DB state at P2 PASS: `series` 29,827 · `observation` 1,762,388 · `transaction` 43,412 · `mention` 45,259 ·
  `entity` 12,911 (provisional vessels) · `corpus_known_gaps` 12 · 10 `v_*` views · doc/section/chunk
  unchanged from P1 (20,704 / 194,309 / 318,232).
- Series coverage: 115 loadable stems loaded, 23 skipped by `series_map.yaml`, 28 deferred to D9
  (transaction tables), `skipped_nonnum=400`, `nodate=0`, `unresolved_doc=338`.
- §4.5 revisions: 136,914 `supersedes` links, 1,577,084 groups, 48,390 resightings, 0 bad.
- Upstream defects (logged, not patched): see `kb/reports/upstream_defects.md` — SEC XBRL skipped (no
  `SEC_USER_AGENT`), `seabrokers_fleet_moves_series` has no numeric column, no sidecar `fixtures` block,
  some sidecar `source_file` unresolved to a `document` (358 rows).
- Branch `kb-build`. Next: P3 (entity resolution + merge gates).
