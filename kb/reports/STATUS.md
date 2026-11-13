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
| P4a | done | PASS (**recall@20 0.900** ≥ 0.85, 180/200; fused-only pre-rerank 0.815; $0 spend) | commit (this phase) |
| gold | done | PASS (250/250 items, all 8 strata on target, 250/250 re-verified from DB, seed 2888775339, $0) | commit (this phase) |
| P4b | done | **PASS** (120 gold chunks / 29 packed calls; chosen `deepseek-v4.1-flash-1017-ultrafast` P 0.922 R 0.536 F1 0.678; 5/5 `gates.yaml` rows pass; $4.75 total) | checkpoint C1 now |
| P4c | **running** (AMD Token Lab bulk pass, resumable daemon) | — | owner amendment 2026-11-13 (Amendment 1 in `C1_APPROVED.md`): bulk extractor moved off congested Ultrafast to the **8-account AMD Token Lab pool** (`DeepSeek-V4.1-Flash`, fallback `DeepSeek-V4-Flash`). AMD is **paid**, not free: measured $0.28/M in, $0.0056/M cached, $0.56/M out = $0.00134/accepted pack ⇒ ~$31.5 for the remaining 23,488 packs, booked at $31.25. Transport parity vs P4b scorer PASS at 0.92. Then union → precision gate → escalation ladder ($11, D12 cap-prioritised) → audit/recall/report. Gleaning and the glm-5.3 second extractor are booked at $0 and deferred to a post-C2 owner decision |
| P5 | scaffolded (code + 20 tests, `5e720111cb` chain) | — | gated on P4c PASS; tables `edge`/`event`/`record_txn` still empty |
| P6 | scaffolded (code + 28 tests) | — | gated on P5 |
| P7 | scaffolded (tools/ask/eval/analyst/discovery/rubric/report, 98 tests, `edc962ad70`) | — | gated on P5+P6; checkpoint C2 after |
| P8 | not started | — | `kb/update.py` + `kb_*.yml` CI + snapshot publish, after C2 approval |

## Spend

Real gateway numbers, `GET http://127.0.0.1:4100/stats` at end of P4b (2026-11-12):

| Metric | Value | Cap |
|---|---|---|
| Enclave (agent, paid V4 Pro) | $66.04 (**over cap by $0.04**, unchanged since P2) | $66.00 |
| Ultrafast (free flash) | 611,858 output tok today (free) | 4,800,000/day |
| NVIDIA NIM (free third provider) | $0.00 — all P4a embedding calls | free (~40 req/min) |
| Pipeline (cumulative stage LLM spend) | **$4.75** (P4b: refs $3.11, candidates $0.61, hole-fill $0.12, adjudication $0.05) | $82 |

P4a spent **$0**: chunking/indexing/retrieval/eval are deterministic Python + DuckDB + numpy; the
only model use is the free NIM embedding endpoint (220,150 vectors, 99,069,064 tokens, 2,302
requests, 4,720.6 s). The enclave number above is cumulative agent (spine) spend, not pipeline
spend — no new paid calls were made in P4a.

P4b spent **$4.75** of the $82 pipeline cap (ledger `kb/state/ledger.sqlite`,
measured `usage.cost`): references $3.114 (glm-5.3 $2.361 + deepseek-v4-pro $0.753), superseded
reference supplement $0.861, candidate bake-off $0.608, candidate hole-fill $0.119, third-family
adjudication $0.053. Free tiers (Ultrafast, NIM) carried 1,464 of the 2,240 calls at $0.
Gateway `/stats` after P4b: enclave (agent spine) $66.04/66.00 unchanged -- no paid agent calls;
Ultrafast output today 1,268,319/4,800,000 tokens.

Live pipeline spend 2026-11-13T22:15Z: read it from the ledger, not from this file —
`kb/state/ledger.sqlite` is the authority (sum `cost_usd` over all passes, or the query in the AMD
amendment section below). At the last measurement: **$4.7680** ledger-measured for all passes up to
the AMD cut-over, plus a small amount of live AMD bulk spend; against the $82 cap that leaves ≈$77.2.

Read the gateway counter correctly: `http://127.0.0.1:4100/stats` counts **agent-spine** calls only
(`agent_gateway_usage.jsonl`, prompt >12k tokens/call). **Extraction calls bypass the gateway
entirely** — both the old Ultrafast route and the current AMD Token Lab route — so pipeline bulk spend
never appears there and the gateway's 76 USD agent cap is untouched by bulk. Do not read the gateway's
per-day token line as the pipeline's bulk budget. Enclave cap still exhausted at $66.0408/66.00, so the
agent spine itself runs on the free tier -- keep agent turns lean while the bulk pass runs.

## AMD amendment (owner, 2026-11-13) — measured route facts

`kb/reports/C1_APPROVED.md` "Amendment 1" is the record of authority; this section is the live
measurement behind it. Gates are unchanged by the amendment — only the provider changed.

| fact | measured value |
|---|---|
| provider | `amd_tokenlab`, base `https://api.tokenlab.amd.com/v1`, `kind: paid` |
| models | `DeepSeek-V4.1-Flash` (`tools`), fallback `DeepSeek-V4-Flash` (`json_object`) |
| key pool | **8 verified accounts** `AMD_TOKENLAB_API_KEY_1..8`, all individually valid, 160 RPM aggregate |
| tariff | in **$0.28/M**, cached in **$0.0056/M**, out **$0.56/M** (NOT free) |
| fit quality | exact (max abs err $0.000000) over 11 stored parity usages; replicated in code to $0.000000000 |
| unit cost | **$0.001249/call**, **$0.00134 per accepted pack** at real pack depth (live daemon window: **$0.000871/pack**) |
| projection | 24,671 packs remaining ≈ **$21.48**; all 24,978 ≈ **$21.76** (booked $31.25, so ≈$9.5 of headroom) |
| refusal mode | uniform `HTTP 429` `model_concurrency_rate_limit_exceeded` — **model-wide ceiling 144**, not per-key quota |
| throughput | worker-bound, not ceiling-bound: 4 workers → 2.67 ok/min, **16 workers → 11.00 ok/min**, 32 → 9.60; default now 16 (measured 2026-11-13, 300 s windows) |
| acceptance rate | 0.948 ok/call at 16 workers (net of retries), attempts/ok 2.19; flat in pacing (8 s/5 s/3 s rungs 9/16, 9/16, 7/16) ⇒ retries, not pacing |
| auth errors | full-pool probe (8 calls × **all 8 keys** = 64 calls): **zero 401/403**, ok 39 / 429 25 = 0.609, distinct key fingerprints `_1` c37b2d4c … `_8` b01e6947; a lone transient 401 is soft, rotates key, never fatal |
| throughput shape | gate drop rate 0.0; 5.6 records per accepted pack; 825 out tok per accepted pack |

Soft-auth hardening (this round): `_provider_spec` published its config cache non-atomically, so a
concurrent worker could observe a half-built cache — the model then looked like an unknown provider
(`key_pool_size` returned 1, turning a transient 401 into a fatal §6 stop) and `load_key` fell through
to the router key against the AMD base URL, itself a 401 generator. The cache is now built off to the
side and published in one assignment; a 30-round × 8-thread cold-cache stress test sees
`("amd_tokenlab", 8)` on every worker. `p4c_run` and the daemon now also name the **P4c** modes file in
their `SystemExit` text rather than P4b.

### Amendment 2 — truncated responses are retried, not accepted (2026-11-13)

Authority: plan §7.2 sets `max_tokens` 2,500 and §7.4 gate 1 (verbatim, L420) says *"A blank or
truncated response is retried, at most 3 times."* The §7.2 cap was applied to the AMD bulk pass, and
every schema failure measured on it was a **cap truncation**, not model quality:

| fact | measured value |
|---|---|
| cause | 400-pack sample: 18 schema failures, **every one** `finish_reason='length'` at exactly 2,500 completion tokens |
| rate | 76 / 1,244 accepted `p4c_bulk` AMD raws truncated (6.1%); 195 truncations across all `p4c_*` passes, $0.1474 spent on them |
| leak | `runner._one` writes the raw and records `status='ok'` **before** parsing ⇒ truncation was invisible to `done_n`/`has_raw`; with `records_total == 0` also invisible to `ladder.triggers` (all three branches guarded by `if total`), a truncated chunk could be neither re-extracted nor escalated |
| fix 1 | `p4b_run.MODEL_MAX_TOKENS` 2,500 → **8,000** for `glm-5.3`, `DeepSeek-V4.1-Flash`, `DeepSeek-V4-Flash` |
| fix 2 | new `p4b_run.stored_usable`; `p4c_run.has_raw`/`pending` now route through it, so a truncated or blank raw stays pending and is re-requested |
| fix 3 | `p4c_daemon.done_n` excludes `finish_reason='length'` |
| blast radius | nil for passed gates: exact-case AMD ids exist only in `p4c_*` passes (P4b/P4a raws are all lowercase model ids, and `kb/state/p4b/modes.json` has no AMD entry) |
| re-key cost | `key_variant` embeds `mt{cap}`, so the cap raise orphans the 1,244 stored AMD bulk raws for re-extraction — ≈**$1.08** at the live rate, and required by §7.4 gate 1 for the 76 truncated ones |

C1 gate unchanged; no gate value was lowered. The cap raise is the literal §7.2→§7.4 reconciliation:
the plan's 2,500-token cap produces truncated JSON on this corpus, and the plan's own gate says
truncated responses are retried.

### Amendment 3 — ledger timestamps are measured on the ledger's own clock (2026-11-14)

Authority: none needed; this is a defect fix with no gate, cap or plan change. `kb/runner.py:194`
stamps `jobs.created_at` with `time.strftime("%Y-%m-%dT%H:%M:%S")` — **naive local time**, no offset.
`p4c_daemon` compared that column against a **UTC** ISO string. The two disagree on the *date*, not
merely the offset, so:

| symptom | measured | truth |
|---|---|---|
| spurious stall | `[stall] errors 223/400, no quota regime` and a 20-min back-off | only **67** rows were `error`; `created_at >= t0` also matched the previous run's 156 errors |
| quota meter dead | `[round 1] day_out 827658` frozen at the pre-restart value, `out_tok +0` | `substr(created_at,1,10)` was a UTC date the ledger never stores; `day_out_tokens` returned 0 for every fresh row |
| clock skew | daemon UTC `2026-11-13T20:03Z` vs ledger local `2026-11-14T01:30` | 5h05m apart |

Fix: `ledger_now()`/`now()`/`next_midnight()` on the local clock, used by the round start `t0`, the
error window and the midnight boundary; `_ledger_day_utc`→`_ledger_day`. Regression tests
`test_ledger_clock_is_naive_local_not_utc` and `test_ledger_error_window_counts_only_this_round`
(351 tests pass). Post-fix round prints `errors 0, day_out 657091` — both meters live.

Consequence for the record: the stalled daemon had already written 333 usable raws before it backed
off; those are kept and counted, since the resume is key-exact (`done 333` on restart, not 0).

## P4b numbers (extraction bake-off, plan §10.2)

| metric | value |
|---|---|
| gold set | 120 chunks in 29 packed calls, 9 doc types, 12 years, 19 publishers, mean pack depth 4.14 (seed 2432301201) |
| references (2 families) | `deepseek-v4-pro` (DeepSeek) 176 records / `glm-5.3` (Zhipu) 381; 38 pairs agreed outright, 304 disagreements adjudicated |
| adjudicator (3rd family) | `nvidia/nemotron-3-ultra-550b-a55b` (NVIDIA, free NIM), fallback `gpt-oss-120b`; 1,150 calls, keep 273 / drop 31 (89.8% lenient) |
| candidates scored | 6 (deepseek-v4-flash, deepseek-v4.1-flash, glm-5.3-flash, gpt-oss-120b, nemotron-ultra, ultrafast) |
| **selected extractor** | **`deepseek-v4.1-flash-1017-ultrafast`** (free Ultrafast tier, `tools` transport) -- precision 0.922 (95% CI 0.883-0.949, n=257 judged), recall 0.536, F1 **0.678** (best candidate; next best glm-5.3-flash 0.585) |
| gate rows | `extraction_gold_chunks` 120/120, `reference_models_distinct_families` 2/2, `chosen_bulk_gate_pass_rate` 1.00 >= 0.95, `chosen_bulk_precision` 0.9222 >= 0.92, `chosen_bulk_f1_within_best` gap 0.000 <= 0.03 -> **all_pass true** |
| record drop rate (plan §7.4) | 0.092 <= 0.30; clean-call 0.385 and chunk gate 0.849 reported audit-only (D10) |
| measured cost | $0.000000/chunk (free tier), mean latency 3,051 ms, p95 3,947 ms |
| P4c feasibility | 20,920 packed calls / 26,961,696 output tokens at gold pack depth; free tier 4.8 M out-tok/day => **5.62 days wall alone**; mixed pool (free primary + `deepseek-v4-flash` overflow, 82.2% of corpus) $55.29 => $60.04 cumulative, inside the $82 cap |
| wall time | references 28.6 s, candidate bake-off 568.1 s; hole-fill and adjudication ran as separate resumable steps and are not separately instrumented in the report |
| tests | 82 passed (`kb/tests/test_p4b.py`) |

Caveats declared in `kb/reports/p4b.md`: reference set is glm-shaped (381 vs 176 records) so absolute F1 is not truth, only the relative ranking is used; per-model coverage 109-120/120 with hole-fill call for the missing packs; precision gate point estimate sits inside its own 95% sampling interval; 12 of 24 corpus years represented in the gold draw.

P3 spent **$0**: seed/resolve/tag are deterministic Python + DuckDB; the only model use is the
resolution judge and the merge auditor, both on free NVIDIA NIM
(`nvidia/nemotron-3-ultra-550b-a55b`, thinking disabled). The enclave number above is cumulative
agent (spine) spend, not pipeline spend — no new paid calls were made in P3.

## C1 owner decisions (2026-11-12, `kb/reports/C1_APPROVED.md`)

1. Bulk extraction on the free Ultrafast tier, shape (a), wall time acceptable.
2. Recall gap vs the glm reference (0.536 vs 0.909) closed by a **free gleaning pass** over every
   chunk after bulk, merged + deduped, same precision gate (plan §7.6 blanket-gleaning override).
3. Escalation model = `glm-5.3` (not nemotron), inside $17, gate-failing chunks only, one free retry
   first, prioritised by document value; cap-prioritised partial coverage accepted (D12).
4. Leftover budget (~$40 of the $82) = `glm-5.3` second extractor on the highest-value chunks
   (SEC MD&A/fleet, broker forecasts, fixtures, S&P), union with Ultrafast output, recall gain
   reported on the gold set.
5. Judge/auditor = `glm-5.3` (different family from the extractor).
6. All 304 adjudicated flags accepted as labelled (keep 273 / drop 31).

## P4c run status (live)

Bulk pass over the frozen 86,607-chunk / 24,978-pack scope on the AMD Token Lab pool, resumable
daemon `kb/p4c_daemon.py --pass p4c_bulk --model DeepSeek-V4.1-Flash --quota 0 --chunk 400 --shard 200
--cap 31.25` (log `kb/logs/p4c_bulk_daemon.log`, state `kb/state/p4c/run_p4c_bulk.json`).

- Raws stored 2026-11-13T22:37Z: **1,595 / 24,978** = 1,490 Ultrafast raws from the abandoned free run
  plus **105 AMD raws**. Raw files and ledger agree exactly (`p4c_bulk` ok rows 1,595, raw files 1,595,
  zero orphans either way), and the daemon counts progress model-scoped from the ledger
  (`status='ok' AND model=?`), so the stale Ultrafast raws no longer inflate the AMD cursor.
- Live AMD measurement at 2026-11-13T23:10Z (307 ok raws, all errors `HTTP 429` attempts 5, **zero
  401/403**): **$0.000871 per accepted pack**, 825 output tok per accepted pack. Throughput is
  **worker-bound, not ceiling-bound**: the original 4-worker setting delivered 2.67 ok/min (measured
  180 s window); **16 workers delivers 11.00 ok/min** (300 s window), 32 regresses to 9.60. Optimum is
  now the code default (`KB_AMD_WORKERS` / `KB_AMD_RATE` override it). Extrapolated: remaining 24,671
  packs ≈ **$21.48** (inside the $31.25 booking, ≈$9.5 headroom) and **≈1.6 days wall** at 16 workers
  — down from the 5.6-day projection the 4-worker rate implied. Ledger pipeline total **$5.0421 / $82**
  ⇒ $76.96 left. `--quota 0` means "no daily token ceiling", i.e. the AMD pool has no free-tier reset
  to wait for; the limiter is the shared concurrency ceiling, which we were not close to touching.
- AMD refusal is the shared concurrency ceiling (144), so the pool degrades and recovers in waves
  rather than draining a per-key daily quota. The daemon treats an error rate above 50% in a window as
  a stall, backs off 20 min, and resumes; already-stored packs are skipped free on the next sweep.
- Cost is real and is charged per accepted pack, not per call: the failed 429 calls cost nothing and
  the ok calls average $0.00134/pack. Budget is enforced per pass against the $31.25 booking.
- Progress is measured in **accepted packs**, not attempted: acceptance ≈0.56/call at 8.1 s/pack wall,
  so the remaining 23,488 packs are on the order of 2 days wall clock at full concurrency. The daemon
  must survive UTC-midnight windows; `--quota 0` makes that a no-op, and any restart resumes from the
  ledger, never from pack 1.
- Daemon bug fixed at restart (`f2eefdc9ae`): a shard window whose packs were all cached made
  `pack_shards` restart at pack 1 every round, so the daemon spun with 0 attempted packs. Windows
  now carry a pack offset (`run_packs(start=) -> start_next`), the driver advances its cursor and
  only backs off after a full sweep.
- Hardening this round: the soft-auth path can no longer terminate the pass on one transient 401 (the
  profile-cache race above), and the three post-P4b modules (`p4c_gate`, `p4c_glean`, `p4c_daemon`)
  now read the **P4c** modes file, which is what actually carries `DeepSeek-V4.1-Flash`; reading P4b's
  bake-off map had made the daemon abort with "no transport mode".
- Real-data rehearsal of the post-processing path (partial raws, no extra spend): `p4c_union.build` ->
  2,555 records / 376 ok calls / 500 gate drops / 121 dedupes; `p4c_gate.gate_run` -> 86,607 chunk
  rows; `p4c_ladder.build_queue` -> 140 trigger chunks (131 `fail_pct`, 12 `low_confidence`),
  `plan_retry` 140 singles, `rank_escalation` priced all 140 at $3.13 -> extrapolated trigger rate
  (~0.37/pack, ~9.1k chunks, ~$204) confirms the **$11** escalation booking covers only a prioritised
  slice (D12) — the shortfall is stated, not hidden, and is a C2 agenda item.
- Remaining ladder: `p4c_union` -> precision gate -> `p4c_bulk_retry` -> `p4c_esc` ($11) ->
  union -> `p4c_audit` -> `p4c_recall` -> `p4c_report.py --write` -> tripwire -> commit+push.
  `--glean` and `p4c_glm2` are booked at $0 and deferred to a post-C2 owner decision (Amendment 1).

## P4c scaffold (code, committed)

While waiting at C1: `kb/p4c_pack.py` (packing, dry run 1,149 packs / 4,000 chunks / 794 docs, mean
depth 3.48, mean 1,081 tokens), `kb/p4c_gate.py` (plan §7.4 gates 1-7 on stored raws, prompt-cid ->
real-chunk mapping, gated JSONL + failure queue + stats, `--out-dir` per ladder rung) and
`kb/p4c_run.py` (streaming resumable bulk pass, shard=200 packs, real ledger spend per batch,
single-chunk escalation ladder, per-pass `run_<pass>.json`). Tests
`kb/tests/test_p4c_{pack,gate,run}.py` 26 passed. Zero-spend replay check:
`kb/p4c_gate.py` reproduces the P4b scorer exactly on the 13 stored ultrafast packed raws
(53/53 chunks, records_total/records_ok identical) -> post-processing path validated before any
bulk call.

Added since: `kb/p4c_audit.py` (200 seeded stored records re-judged by a different model family,
wrong-rate gate vs `random_audit_wrong_max` 0.03, refuses a same-family judge) and
`kb/p4c_report.py` (merges bulk + ladder gated JSONL into per-chunk final status, declared coverage
of the frozen scope, gate rows, per-pass ledger spend + wall time, ten seeded sample chunks with
source paths, writes `kb/reports/p4c.json`/`.md` with `phase`/`sample_seed` for the tripwire). Tests
`kb/tests/test_p4c_{audit,report}.py` 14 passed; full suite **128 passed**; tripwire clean. No model
calls made; no gate crossed.

End-to-end (fake-raw) smoke of the whole post-processing path found and fixed one real bug: the gate
writes one flat row per pack-chunk, while `p4c_report.merge` only read the nested `chunks` fixture
shape, so a real run would have merged **zero** rows and reported 0% failure/coverage. `merge` now
accepts both shapes (`_row_chunks`), reports `merged_chunks` next to `gated_rows`, and has a flat-row
regression test; the smoke also caught the scope year count (24 years, 1986-2026) and the report now
renders that constant instead of the 41-year span. Six synthetic packs / 24 chunks went through
`p4c_gate.py --out-dir` and `p4c_report.py --md` cleanly (schema pass rate 1.0, gates correctly FAIL
on the partial slice), then all synthetic state was deleted.

Ladder command sequence (each rung gated into its own dir, later rungs replace a chunk only when
clean): `p4c_run.py --run --pass p4c_bulk --model M` -> `p4c_gate.py --pass p4c_bulk --model M` ->
`p4c_run.py --escalate --pass p4c_bulk_retry --model M --failures kb/state/p4c/failures.jsonl` ->
`p4c_gate.py --pass p4c_bulk_retry --model M --packs kb/state/p4c/singles_p4c_bulk_retry.jsonl
--out-dir kb/state/p4c/esc_retry` -> repeat for the escalation model into `esc_esc` ->
`p4c_audit.py --plan` + `--run` -> `p4c_report.py --write`.

## P4a numbers (retrieval layer, plan §5.2–§5.5)

| metric | value |
|---|---|
| `retrieval_recall_at_20` | **0.900** (180/200, threshold 0.85) → PASSED |
| recall@5 / @10 (reranked) | 0.815 / 0.840 |
| fused-only recall@20 (pre-rerank) | 0.815 |
| rerank stage (D9, deterministic; D5: no NIM reranker) | window 40, rescued 18, broke 1, 0.078 s/query |
| per stratum recall@20 | vessel 0.945 · company 1.000 · numeric 0.817 · section 0.880 |
| chunks indexed (FTS5) / embedded vectors | 318,232 / 220,150 (98,082 `norm_sha` dups share a row) |
| mean query time / mean first gold rank | 2.3 s / 2.37 |
| build wall time | 5,537 s (embed 4,721 s + index 357 s + eval 460 s) |
| spend | $0.00 (NIM free); KB DB 4.73 GB, vectors fp16 0.84 GB |

Repair trail (all measurement-set defects, retriever untouched): 0.715 → 0.695 (labels + question
text repaired, gold still capped at 20) → 0.815 (cap removed) → **0.900** (+ §5.5 rerank stage).

Smoke-test usage: prompt_tokens 13, completion_tokens 5, model `cyberouter/deepseek-v4-flash`, cost $0.000003.

## Gold Q&A set numbers (250 questions, plan §12.1)

| metric | value |
|---|---|
| items / strata | 250 / 8, every stratum on target (a 50, b 25, c 35, d 25, e 35, f 25, g 15, h 40) |
| re-verified from DB | 250/250 (`verification.passed`), 0 failures |
| sample_seed | 2888775339 (`seed_for("GOLD_SET")`) |
| judge-graded strata | 50 (d 25 + f 25, `judge_only: true`) |
| build wall time | 30.6 s, $0 (DB reads only, no LLM) |
| question text | deterministic templates over DB locks; no LLM fact creation |
| SEC stratum | prose/section lookup, not XBRL (deviation D6 — no `SEC_USER_AGENT`) |
| occurrences | 2 repair rounds: `build_e` term-uniqueness (pool terms were never unique in-doc) → body-derived rare terms unique to one section; h pools 27→40 candidates via invented tokens checked on a single distinctive word; flat `f` windows rejected (`first != last`); junk-glyph SEC headings rejected; h family caps made target-proportional so `--max-per-type` slices stay balanced |

Files: `kb/state/gold/gold_set.json` (source of truth for P7), `kb/reports/gold_set.{json,md}`
(report with 10 sampled records + 25-question C1 packet).

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
- Branch `kb-build`. **At checkpoint C1** — `kb/reports/C1_REVIEW.md` written (generator
  `kb/c1_review.py`, tests `kb/tests/test_c1_review.py`, 86 tests pass). Hard stop, waiting for the
  owner's chat reply; on reply write it verbatim into `kb/reports/C1_APPROVED.md` under
  `owner_message:` and continue with P4c.
- C1 review packet: (1) `kb/reports/p4b_flagged.md` -- 30 flagged reference records, seed 15063620,
  pool 304 (keep 273 / drop 31), half adjudicator-drops; (2) `kb/reports/p3_owner_sample.json` -- P3
  owner merge sample; (3) `kb/reports/gold_set.md` §"C1 sample packet" -- 25 gold questions;
  (4) `kb/reports/p4b.md` -- bake-off table, selected model, P4c feasibility and the open budget /
  wall-time / mixed-pool decision (options a/b/c in `## Selected model`, not self-approved).
- Also note: `kb/config.yaml` line 60 was invalid YAML at `origin/main` (unquoted `note:` containing
  `chat_template_kwargs {"enable_thinking": false}`), which broke every `yaml.safe_load` path; fixed by
  quoting the note (only change in that file).
- `origin/main` advanced while P4b ran (daily data commits); merged `origin/main` into `kb-build`
  (`581b92fe7a`) before the gate so tripwire compares clean again. The 3 dirty `data/ffa_live/*`
  refresh artifacts were restored to HEAD before the merge (regenerated upstream, not agent edits).
