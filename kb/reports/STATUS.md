# STATUS — GraphRAG build (kb)

Live run status. Real spend read from `http://127.0.0.1:4100/stats`.

| Phase | State | Gate | Next |
|---|---|---|---|
| 0 smoke | done | PASS (model `cyberouter/deepseek-v4-flash`) | — |
| P0 | done | PASS (R1–R7 all PASS) | commit+push |
| P0.5 | done | PASS (4 gates, scope frozen 20,704 docs) | commit `7419fd3df7` |
| P-1 | done | PASS (6/7 candidates usable; tools support confirmed) | report `kb/reports/p_m1.md` |
| P1 | done | PASS (row counts equal P0.5; 50/50 chunk round-trip; FTS5 ok) | commit `9756cc1552` |
| P2 | done | PASS (all 7 gates: raw_cell 2000/2000 verbatim, known values 40/40 across 9 publishers, txn precision 50/50, SEC XBRL skipped — no `SEC_USER_AGENT`) | commit `1e726a6661` |
| P3 | done | PASS (merge audit 300 pairs, precision **0.99** ≥ 0.98, 0 conflicting IMO/CIK, 305 merges; tagger 185,454 chunks) | commit (this phase) |
| P4a | not started | — | retrieval + recall@20 |
| gold | not started | — | |
| P4b | not started | — | checkpoint C1 after |
| P4c | not started | — | |
| P5 | not started | — | |
| P6 | not started | — | |
| P7 | not started | — | checkpoint C2 after |
| P8 | not started | — | |

## Spend

Real gateway numbers, `GET http://127.0.0.1:4100/stats` at end of P3 (2026-11-12):

| Metric | Value | Cap |
|---|---|---|
| Enclave (agent, paid V4 Pro) | $66.04 (**over cap by $0.04**) | $66.00 |
| Ultrafast (free flash) | 285,429 output tok today (free) | 4,800,000/day |
| NVIDIA NIM (free third provider) | $0.00 | free (~40 req/min) |
| Pipeline (P3 stage LLM spend) | $0.00 — NIM judge only, free | $82 |

P3 spent **$0**: seed/resolve/tag are deterministic Python + DuckDB; the only model use is the
resolution judge and the merge auditor, both on free NVIDIA NIM
(`nvidia/nemotron-3-ultra-550b-a55b`, thinking disabled). The enclave number above is cumulative
agent (spine) spend, not pipeline spend — no new paid calls were made in P3.

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

- Tripwire clean at P3 (`python kb/tripwire.py` → `tripwire clean`), after `git merge origin/main` with
  the automated `data/` sync commits (protected tree, no local data edits kept).
- DB state at P3 PASS: `entity` 73,427 (vessel 68,623 · company 3,101 · port 1,472 · route 110 · country 72
  · commodity 48 · index 1) · `alias` 71,260 · `merge_log` run=`p3` 22,848 decisions / 305 merges
  (splink_auto 256, judge_same 32, company_exact_name 17) · chunk tags on 185,454 of 318,232 chunks
  (115,118 multi-entity) · observation/series/transaction unchanged from P2.
- Identity invariants at P3 PASS (checked over *all* merges, not the sample): `merges_with_conflicting_imo_or_cik`
  0 · `entities_merged_into_multiple_targets` 0 · `merges_without_alias_covering_target` 0 ·
  `vessel_alias_over_limit` 0 · `sec_cik_duplicates` 0 · 305 entities `status='merged'` (undoable via
  `merge_log` + alias `valid_to`).
- Merge audit (gates.yaml P3): 300 of 305 merges sampled (seed 2,726,325,733 = `seed_for("P3")`, stratified
  by method, largest-remainder), judged by NIM `nemotron-3-ultra-550b` with the plan §6.4 rubric:
  same 297 / different 3 / unsure 0 → precision 0.99. The 3 "different" are built-year boundary cases
  (e.g. `Uzava` 2007 vs 2008) where the judge read the ±1-year tolerance as a contradiction — strict
  scoring, kept as-is. Owner review sample of 30 written to `kb/reports/p3_owner_sample.json` for C1.
- Tagging precision-first filters (plan D8: identity from keys, never names): 2,527 implausible vessel
  patterns, 1,171 generic company patterns, 1,311,642 ambiguous single-token tags skipped without in-chunk
  corroboration; 131,730 ambiguous hits accepted after corroboration. Concession documented in
  `kb/reports/upstream_defects.md` §5.
- Upstream defects (logged, not patched): see `kb/reports/upstream_defects.md` — SEC XBRL skipped (no
  `SEC_USER_AGENT`), `seabrokers_fleet_moves_series` has no numeric column, no sidecar `fixtures` block,
  some sidecar `source_file` unresolved to a `document`, name-heavy vessel identity material (P3).
- Branch `kb-build`. Next: P4a (retrieval + recall@20).
