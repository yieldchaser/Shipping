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

### Amendment 4 — the bulk extractor was running at ~10 of its 16 workers (2026-11-14)

Authority: none needed; defect fix, no gate, cap or plan change. Two defects in a row cost throughput
and neither was a model-quality problem.

**Defect.** `kb/runner.py` dispatched every job with `asyncio.to_thread`, which submits to the event
loop's **default** `ThreadPoolExecutor` — capped at `min(32, cpu_count + 4)` = **12** threads on this
8-core box. The AMD daemon asks for `KB_AMD_WORKERS` = 16 (and 32 was tried). Measured effective
in-flight concurrency (`kb/_t_threads.py`, cpu 8, default cap 12):

| requested workers | effective concurrency |
|---|---|
| 8 | 7.9 |
| 16 | 8.0 |
| 32 | 10.6 |

So the pool never saw the load the config believed it was sending. Predicted rate with ~10 real slots,
21.2 s mean ok-latency and 1.81 attempts per accepted pack is `10 × 60 / (21.2 × 1.81)` = **15.6 ok/min**
against **13.5 ok/min** observed — the shortfall was the hidden cap, not the AMD ceiling (144).

This also invalidated the earlier reading that 16 workers was optimal and 32 worse: both runs were
pinned to the same default executor, so neither preference was ever measured.

**Fix.** `run()` now builds its own `concurrent.futures.ThreadPoolExecutor(max_workers=n)` sized to the
worker count and dispatches with `loop.run_in_executor(ex, self._one, job)`. Regression test
`test_runner_concurrency_reaches_the_requested_worker_count` asserts peak concurrency ≥ 16 (it also
resets the `_SCHEMA_INIT` global, which had made the tmp-ledger variant fail only in a full-suite run).
Suite: **352 passed**.

**Measured after the fix** (fresh window, same model, same pool, 4 of 8 accounts in play at the time):

| window | accepted packs/min |
|---|---|
| pre-fix, 300 s windows (rounds at 16 workers) | 13.5 |
| post-fix, 02:51–02:53 | **≈19** (17 + 27 + 14 ok in ~3 min) |

Round 1 of the restarted daemon showed 9 attempted packs before the pool was warm; rounds 2+ recover.
No gate, threshold or cap was changed to obtain this.

**Re-tested 32/240 now that the cap is lifted** — the old "32 is worse" result was also measured under
the 12-thread default executor, so it needed a clean read. It holds, harder:

| config | accepted packs/min | notes |
|---|---|---|
| 16 workers / 120 rpm | ≈19 | 02:51–02:53: 17 + 27 + 14 ok |
| 32 workers / 240 rpm | ≈0.3 | 02:54 36 ok, 02:55 28 ok, then **2 rows in 7.5 min**; mean ok-latency 20.7–23.6 s but max 57 s, and the tail stopped draining |

32 concurrent calls against this pool starve rather than scale: the fast rows finish and the slow tail
(30–60 s) pins the workers, so accepted-per-minute collapses once the queue is saturated. Shipped
config stays `KB_AMD_WORKERS` 16 / `KB_AMD_RATE` 120, which is now a measured optimum rather than an
artifact of the executor cap.

**Clean 32-worker A/B, post-fix** (`kb/logs/p4c_d32b.log`, PID 22428): started 03:38, wrote **nothing**
for 25 min — 6 consecutive 30 s samples showed `att +0 out +0 rows +0`, `MAX(created_at)` frozen at
`03:37:14`. That is not the executor artifact; 32 remains worse even with a correctly sized pool.

### Amendment 5 — the daemon could not see a stall (2026-11-14)

Authority: none needed; defect fix, no gate, cap or plan change.

**Defect (run-stopping).** Between 03:37 and 04:14 the bulk pass added **zero** rows. Two causes, both
real and independent:

1. **Provider brownout.** A raw-bytes probe (`kb/_t_body.py`) showed the AMD gateway answering
   `HTTP 429 {"error":{"message":"Model 'DeepSeek-V4.1-Flash' is at its concurrency limit (144) …"}}`
   for 2 of 3 sequential calls, and one call hanging **60.5 s** then `TimeoutError`. This is the shared
   model-wide pool (144) being consumed by other tenants, not our pacing: a **single** concurrent call
   was refused. Nothing on our side can raise that ceiling; §7.5 "partial coverage beats lower quality"
   and the provider-pool rule apply — wait it out and keep resumability.
2. **The stall detector was blind to exactly this failure.** `ledger_errors` counts rows by
   `jobs.created_at`, and `runner._record` deliberately does **not** refresh `created_at` on the
   re-processing UPDATE (the P4b key-stability contract, `kb/runner.py:197-209`). A pack that fails,
   is retried and fails again keeps its **original** timestamp, so `errs` stayed `0` while `attempted`
   was `1` and `scope_done` sat frozen at `1349`. The `errs / attempted > STALL_ERROR_RATE` rule could
   never fire, and the log shows the loop grinding: `attempted 2 packs … errors 0` with `out_tok +0`.
   Compounding it, `timeout_s=300` x 5 attempts meant **one** hung pack could burn 25 min of a shard.

**Fix.**
* `kb/p4b_run.runner_for` AMD branch: `timeout_s` 300 -> **120** (`KB_AMD_TIMEOUT` overrides). A healthy
  AMD pack answers in 5-60 s (p95 ~ 61 s; observed max 57-61 s), so 120 s admits every real answer and
  fails fast on a black hole.
* `kb/p4c_daemon.run`: progress guard. A round that adds neither a stored raw nor an output token is
  `barren`; `UNPRODUCTIVE_ROUNDS = 3` consecutive barren rounds triggers the same 20 min back-off as the
  error-rate rule. Productivity is the only signal that cannot be spoofed by the ledger's stale stamps.

Tests: `test_run_backs_off_when_rounds_add_neither_raw_nor_tokens` (the exact regression) and
`test_run_does_not_back_off_while_rounds_stay_productive` (a healthy run must not nap). Suite:
`test_p4b + test_p4c_run + test_p4c_daemon` = **54 passed**; daemon file **16 passed**.

**Honest state at 04:15.** The brownout is still active: the restarted 16-worker daemon logged
`batch 1 packs 1/200 … wall 102s` then `att +0 out +0 rows +0` for 2.5 min, and the sequential probe is
still 429-dominant. This is a **provider-side** outage of the shared AMD pool - no code change can make
those calls succeed. The run is resumable from the ledger at `done 1363 / 24978`, and the daemon now
backs off instead of pinning a shard. Throughput figure to reuse when the pool recovers: **~19-22
accepted packs/min** at 16/120.

### Amendment 6 — host reboot, resumable restart (2026-11-14)

Authority: none needed; host event, no gate, cap or plan change.

A scheduled Windows update restarted the host at **04:45**. The daemon (PID 30280) died with it; a
`Get-CimInstance` sweep at 08:42 confirmed no `kb/*` python process survived. Nothing was lost:

| check | value |
|---|---|
| ledger integrity | intact; `p4c_bulk` ok rows 1,713, `MAX(created_at)` `2026-11-14T03:37:14` |
| key-exact usable raws (`p4c_run.done_packs`) | **1,374 / 24,978** |
| gateway | port 4100 up, enclave $68.87 / $76 |
| disk / memory | 10.17 GB free; 10+ GB RAM free after the reboot |

The 2,634 "banked" figure counts ledger `status='ok'` rows over all passes and models; the gateable
number is the key-exact one (1,374), because raising `max_tokens` to 8,000 orphaned the pre-cap AMD
keys (Amendment 2) and 1,490 of the ok rows are the abandoned Ultrafast raws. Both are true statements
about different things; the run resumes on the key-exact one.

Daemon relaunched at **08:46** (PID 11992, `KB_AMD_*` cleared to defaults 16/120/120), log
`kb/logs/p4c_bulk16.log`, previous log preserved as `kb/logs/p4c_bulk16.pre-reboot.log`. Startup line
proves the resume path: `[start] pass p4c_bulk model DeepSeek-V4.1-Flash packs 24978 done 1374 quota 0/day`
— it restarts from the ledger, never from pack 1.

**Interim gate read on the banked slice (zero spend).** Key-exact AMD subset (1,366 packs at 04:40,
4,826 chunks) gated to `kb/state/p4c/interim/`: **0 blank, 0 schema_fail** -> gate 1 pass rate **1.000**,
record drop rate **0.101** (`entity_unresolved` 998, `number_not_in_quote` 287, `sid_missing` 78,
`quote_empty` 76). The Amendment 2 cap fix is therefore holding across the whole banked slice, not just
the 400-pack sample it was measured on. Fail reasons are the expected gate-2/4 drops the retry +
escalation rungs exist to absorb.

### Amendment 7 — dense scheduling, real throughput, and crash-resilient relaunch (2026-11-14)

Authority: none needed; scheduler, measurement and process-supervision fix, no gate, cap or plan change.

**Defect 1 — the daemon re-walked a finished head.** The monotonic cursor assumed the pending packs
were contiguous behind the cursor. They are not: after the cap change (Amendment 2) the frozen scope is
key-exact-pending in windows 0-6 (1-10 each), **all of windows 7-123 at 200 pending each**, and window
124 at 178 - 23,595 of 24,978 packs (94.5%) pending, but the *head* of the list is largely cached. A
`start`-anchored walk therefore burned its whole round on a cached head and dispatched nothing; the
`[round N]` line that would have shown this was never reached because the process crashed first (below).
Fix: `dense=True` (now the daemon default) re-derives the pending set from the ledger every round and
batches it contiguously, ignoring `start` and skipping the cursor advance entirely. A monotonic cursor
would step over the sparse tail, so the dense path never touches it. First live batch after the fix:
`[10:28:05] pass p4c_bulk: 200 jobs, budget left $71.521` - full width, 200 jobs / 715 chunks.
Verified by `kb/tests/test_p4c_run.py` (dense batches behind a finished head; `pending_shards` skip of
cached packs; `limit`/`shard` honoured) and `kb/tests/test_p4c_daemon.py` (empty dense round backs off
instead of advancing).

**Defect 2 — the recorded pool throughput was measuring the wrong thing.** Amendment 3-era probes
(`kb/_t_conc.py`) reported `n=8 -> 119.7`, `n=16 -> 129.6` accepted calls/min. Those probes sent
`max_tokens=8`: they measured admission into the shared model pool, not 8,000-token extraction. A/B on
real pending packs with the real prompt (`kb/_t_ab.py`, key-exact accounting):

| workers / rate | packs | ok | wall | ok/min | attempts/ok | latency p50 / p90 / max |
|---|---|---|---|---|---|---|
| 16 / 120 rpm | 100 | 86 | 571 s | **9.0** | 1.86 | 21.3 s / 51.2 s / 60.9 s |
| 48 / 600 rpm | 150 | 76 | 394 s | **11.6** | 7.16 | 20.8 s / 50.0 s / 59.9 s |

At 48 workers 74% of attempts are rejected (429/503) to buy 2.6 extra ok/min, and each reject burns a
worker slot; 16 is the throughput/quality sweet spot and stays the setting. Live daemon batches
confirm the corrected number rather than the probe: 190/200 ok in 733 s (15.6 ok/min), 166/200 in
1441 s (6.9/min), 176/200 in 404 s (26/min) - pooled 532/600 ok in 2,578 s = **12.4 ok/min**, and the
spread tracks the provider's congested/clear cycles, not our worker count. A recent 600-row ledger
sample shows why worker count cannot help: ok latency p50 **13.0 s**, p90 46.9 s, but 542/600 accepted,
so a nominal 16 in-flight calls should yield ~50-70 ok/min. It yields ~12. The gap is not our pool
(already sized to 16 via `b958cc2650`), not the rate limiter, and not the GIL: an extra independent
16-worker extractor run concurrently changed nothing. The campus AMD endpoint caps *admitted*
concurrency far below the nominal 144, and excess calls are rejected in ~1 s. Raising workers only
converts successes into rejects while the accepted rate holds - so 16 workers / 120 rpm is final. Cost
tracks completions, not attempts, so rejects are free in dollars but not in wall time; at ~12 ok/min
the remaining 23,285 packs is **~32 h** of wall clock, so the §7.5 partial-coverage clause is the live
question, not the budget.

**Defect 4 - two argument errors found while hardening.** `kb/p4c_supervisor.py` had a flat 20 s
restart with no cap, so a permanent fault (revoked key, full disk) would spin forever; it now uses an
exponential back-off capped at 300 s that resets only after a child has stayed up 120 s, so a crash
loop slows down and stays visible in `kb/logs/p4c_bulk_supervisor.log` instead of hammering the host.
`kb/llm_runner.py` rotated its multi-key index with an unguarded read-modify-write from the runner's
thread pool: concurrent `load_key` calls could read the same index and duplicate a key or lose an
increment. Never fatal for a shard (any pool key works) but it defeats even rotation on a long run;
now guarded by a lock covering only the two dict ops, never I/O. Tests:
`kb/tests/test_llm_runner_keys.py` (even rotation + 16-thread evenness),
`kb/tests/test_p4c_supervisor.py` (restart-then-success, escalating back-off, no `--start` cursor).
Full suite **358 passed** plus the new cases.

### Amendment 8 — two silent downstream defects found during the bulk wait (2026-11-14)

Both were found by reading the P4c→P5 contract while the bulk pass ran, not by a test failure: neither
raised an exception, both would have degraded the published KB without any gate going red. Fixing them
now, while they cost nothing, is the whole point of hardening the chain before the raws land.

**Defect 5 — the audit labelled the wrong extractor.** `kb/p4c_audit._selected_extractor()` resolved
the model under audit from `kb/reports/p4b.json`'s winner (`deepseek-v4.1-flash-1017-ultrafast`), but
the P4c records actually under audit are produced by the **P4c bulk** pass over the AMD pool
(`DeepSeek-V4.1-Flash`). The `gates.yaml` family check still passed (both are `deepseek`), so the gate
would not have gone red — the report would simply have named a model that produced none of the audited
records, and a later re-point of P4b's winner could have flipped the judge into a same-family
violation that the check was meant to catch. It now resolves from `p4c_union.SOURCE_SPEC`'s `p4c_bulk`
entry, falling back to `p4b.json` only if that entry disappears. The report's markdown also no longer
hardcodes `different family: yes`; it prints the computed comparison, so a violation is legible instead
of asserted-away. Tests: `test_selected_extractor_is_the_p4c_bulk_source`.

**Defect 6 — P5 silently dropped every record that cited a declared new entity.** Union rows
(`p4c_union.gated_union.jsonl`, which wins precedence in `p5_build.default_gated_paths`) carry the
approved ids as `new_entities`, but `provision_new_entities` read only the per-rung gate-row keys
`new_entities_ok` + `new_names`. With the union export present it therefore provisioned **nothing**;
every kept record citing a `type:new:...` id then failed `build_rows`' known-set check, was counted as
`dangling_entity:...`, and was dropped. Measured on the real 300-pack rehearsal slice: **2,807 of
10,324 kept records (27.2%) cite a `new:` id**, and 3,463 gate rows carry at least one approved new
entity (22,934 ids); on the probe union export the old path provisioned **0**, the new path provisions
**9**. This is why the defect mattered: a quarter of the graph would have vanished while the P5 gates
(`records_without_code_sliced_quote`, `dangling_entity_ids`) still read clean, because the drop is
counted before the rows exist. `row_new_entities()` now accepts both shapes. Tests:
`test_row_new_entities_accepts_union_and_gate_shapes`,
`test_union_shaped_new_entity_is_provisioned_and_resolves`.

Full suite after both fixes: **369 passed**.

**Defect 7 — union records carried prompt-local chunk labels, so P5 rejected every record.** Found by
running the real end-to-end P5 build over a 40-pack union slice pulled from the live ledger (zero spend,
`kb/state/p4c/_vfy_union`) instead of trusting the unit fixtures. Result was `INSERTED {edge 0, event 0,
claim 0}` with `drops {chunk_mismatch: 234}` — **100% of records dropped**. Cause: the extractor only
ever sees prompt-local block labels (`c2`, `c3`), and `p4c_union.record_row` re-derived each record from
the raw transport copy, leaving `body["chunk"]` as that label. `p4c_gate._as_dict` already overrode
`row["chunk"] = cid` with the real DB chunk id, and `kept_for` mapped the labels correctly — but
`record_row` reintroduced the stale one, and the union export has first precedence in P5's
`default_gated_paths()`. P5's `chunk_mismatch` then rejects the record, so the graph would have shipped
**empty** while all three P5 gates (`records_without_code_sliced_quote`, `dangling_entity_ids`, coverage)
still read clean — a total silent loss, strictly worse than Defect 6. Fix: `record_row` takes the real
`cid` and stamps it, both call sites (`p4c_union.union_pack`, `p4c_recall.item_rows`) pass the id they
already have in scope, so no caller can regress. Same real-data slice after the fix:
**`INSERTED {edge 11, event 116, claim 107, event_role 59, record_txn 14}`, drops `{}`, quote/dangling
gates 0**. Tests: `test_record_row_stamps_the_real_chunk_id_not_the_prompt_label`,
`test_union_pack_rows_carry_ids_that_match_their_pack`. Full suite: **371 passed**.

Note for the record: Defects 5-7 were all found by *executing* the contract against real ledger data
during the wait, not by the test suite, which was green throughout. That is why the chain is being
rehearsed on live AMD raws before the bulk pass finishes rather than after.

**Operational hazard found the same way: a P5 rehearsal mutates the live KB.** `p5_build.build()` opens
`kb/state/kb.duckdb` **read-write** (`connect(db)` at L605, `ensure_schema` L606, then `DELETE`/`INSERT`
per batch) — there is no `--db` sandbox for a dry run, so the proof run above wrote 11 edges / 116
events / 107 claims / 59 event_roles / 14 record_txns into the production database and provisioned 114
provisional `%:new:%` entities. Reverted exactly (graph tables were empty beforehand and the `%:new:%`
ids were created by the run): now `edge 0, event 0, event_role 0, claim 0, record_txn 0`, entities
73,427 = 59,216 / 13,906 / 305, `%:new:%` 0. The real P5 pass rewrites its scope by `chunk_id`, so a
rehearsal cannot corrupt final output once the full run follows — but **any future slice rehearsal must
be rolled back by hand before P5 is declared done**, and P5's own gates cannot detect the leftovers
because they count the slice they were handed, not the table state.

**Defect 8 — the P4c audit read the wrong row shape, so the §11 200-record gate could never be met.**
Found by rehearsing `kb/p4c_audit.py --plan` against the real interim gate rows during the bulk wait
(zero spend). `flat_records` read `row["state_facts"] / ["events"] / ["claims"]` at the row's top level,
but `p4c_gate.py` writes those lists **inside `kept`** — top-level kinds are absent on every one of the
4,826 real rows. Result: `--plan` reported `records_available 0 / items 0`, so `--run` would have judged
nothing, `audit.json` would carry `wrong_rate 0.0`, and any reader that did not check `sampled` would see
a clean audit; `p4c_report.gate_rows` (L271-274) does check `sampled >= 200`, so the gate failed loudly
instead of passing vacuously — but with no error message pointing at the cause, that reads as "audit not
run" forever. The unit fixture built the top-level shape itself, so the suite was green throughout. Fix:
new `row_kept(row)` accepts both shapes (`kept` first, then the spread keys), and `flat_records` goes
through it; union rows, which carry `kept` *and* the spread lists, are counted once. Also added
`default_gated()`, which prefers `union/gated_union.jsonl` over `gated.jsonl` — the audit must judge the
same record set P5 loads, otherwise it would score records the union had already deduped away. Proof on
real data: `records_available` **0 → 10,324**, `items 200`. Four new tests, one building the row exactly
as `p4c_gate` writes it. Full suite **374 passed**. That is now **four** silent-loss-or-quality-gate
defects (5, 6, 7, 8) the green suite did not catch and that only surfaced from running the chain on real
ledger data.

**Defect 9 — `failure_queue_max` had two definitions in one file.** `p4c_report.chunk_state` (L66-77)
computed a failed chunk as `call_failed OR gates_2_4_failed > 0` — *any* dropped record — giving
**0.1281** (618/4,826) on the interim slice, while `merge_union` (L137) computed `clean = not
call_broken` — the D12 repair queue — giving **0.0346** (167/4,826). `build()` (L339) silently switched
between them depending on whether `union/gated_union.jsonl` existed, so the gated number was a function of
which export happened to be on disk. Ruling: unify on the **repair-queue** metric. Three independent
reasons, none of them "the number is smaller":
1. The frozen key is bound to it in code: `p4c_union.py` L299 emits `failure_queue_max = 0.02` next to
   `broken_chunks / chunks` (L297-298), and L23-27 spells out the definition — every source call broke, or
   records came back and all failed gates 2-4 — adding that extraction quality "is measured on the gold set
   by `p4c_recall.py`, not hidden inside this count".
2. The per-record number is **unreachable at 2% by construction**. Cross-tab on the interim slice:
   `broken_and_unqueued 0` (all 167 broken chunks are rule-6 queued) but `report_failed_and_unqueued 216`
   — those 216 kept ≥3 records with 10-25% dropped, so rule 6 never queues them and no amount of escalation
   can move their count. A gate that cannot be satisfied by any available action is mis-specified.
3. The report already labelled the number "chunks still failing (failure queue)" / "broken chunks (D12)"
   (L397-402, L425-426); the rungs path was the outlier against its own prose.
Both readings still **FAIL** 0.02 on the partial slice, so no gate is traded down. Implementation: `chunk_state`
now returns `broken` alongside `clean`; `totals` reports `failure_queue_rate` (gated, 0.0346) and keeps the
strict reading under `chunks_strict_failed` / `strict_failure_rate` (0.1281) as an explicitly **ungated**
diagnostic; `ladder_stats.still_failed` uses the queue sense; the MD table shows both, labelled. Proof:
rungs fallback moved 0.1281 → 0.0346, exactly matching the union path, while the strict figure stayed visible
at 0.1281. `chunks_clean` still means "every returned record survived gates 2-4" and still governs ladder
precedence, so no rung can overwrite a clean verdict on the strength of the looser reading. One test rewritten
to the unified definition plus a new test pinning that a chunk keeping ≥1 record is *never* in the queue;
full suite **375 passed**. Threshold untouched at 0.02 (`kb/gates.yaml` L4: lowering never).

**Follow-up audit: no other consumer re-read the stale label.** Checked every reader of a record's
`chunk` field after the fix. `p4c_gate._as_dict` (L168-170) already stamped the real id, and
`p4b_run.split_gate` (L640-654) matches on the prompt id only *inside* one pack and re-keys the output
dict by the real `cid`, so P4b was never affected. `p4c_report.merge_union` (L123-148) reads only counts
(`records_total`, `records_ok`, `gates_dropped`) plus the row's own `chunk_id`, never a nested record's
`chunk`. `p4c_recall.item_rows` uses the real id passed in and now passes it through. `p4c_highvalue`
touches `chunk_ids` only. So the union export and the recall scorer are the field's only two readers and
both are fixed.

## P4b numbers (extraction bake-off, plan §10.2)

**Defect 3 — fatal interpreter abort.** The daemon died at 09:56:12 with
`Fatal Python error: PyEval_SaveThread: ... the GIL is released (the current Python thread state is
NULL)`, thread dumps showing pool threads parked in `llm_runner.chat` SSL reads. That is an
interpreter-level abort, not a Python exception: it cannot be caught in-process, so recovery must live
outside the process. Fix: `kb/p4c_supervisor.py`, a thin wrapper that restarts the daemon after any
non-zero exit with a 20 s back-off and appends every launch/exit to
`kb/logs/p4c_bulk_supervisor.log`, so a crash loop is visible instead of a silent stall. The daemon was
relaunched under it at **10:27** (supervisor PID 5396, daemon child PID 20396); the ledger is the
resume point, so a crash now costs only the in-flight batch. Batch yield from the crashed 09:50 run
(same ledger, since 09:45): `ok 59` / `error 5` (all `HTTP 429`, `attempts=5`) - progress, not loss.

| check | value |
|---|---|
| key-exact usable raws | **1,810 / 24,978** at relaunch (`done 1810`) |
| pending | 23,595 packs (94.5%) |
| `p4c_bulk` sub-ledger | $2.79 of the $31.25 booking; pipeline $7.57 of $82 |
| tests | `kb/tests/test_p4c_run.py` + `kb/tests/test_p4c_daemon.py` 30 passed |

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
- **Downstream chain smoke-tested on real AMD raws while the bulk pass runs (2026-11-14T12:35Z, no extra spend).**
  Ran the whole post-processing path over the first 300 AMD-scoped packs (`packs.jsonl`, limit 300):
  `p4c_gate` → 1,091 chunks, **calls blank 0, schema_fail 0, gate pass rate 1.0**, record drop rate 0.1024;
  chunk failures 124 (0.1137) with reasons `entity_unresolved 219 / number_not_in_quote 61 / sid_missing 13 /
  quote_empty 12`. The 1.0 parse rate is the material result: the AMD transport (tools mode, `max_tokens` 8000)
  is producing well-formed JSON on every call, so §7.4 gate 1's retry path is not being exercised at scale.
  `p4c_union` over the same slice → 2,088 records, 111 duplicates, 251 gate drops, `call_status {ok: 300,
  missing: 1,200}` (missing = the 18,000 packs not yet extracted, correct for a 300-pack slice).
  `p4c_ladder --plan-only` on the slice's **gate** rows → **118 queued chunks (10.8%)**, triggers
  `fail_pct 81 / thin_long_sec 37 / low_confidence 9`, priced at **$2.68** (tiers `sec_mda_fleet` 46,
  `other` 50, `sp_index` 13, `broker_forecast` 5, `fixtures_tc` 4).
- Extrapolating that 10.8% queue rate and $2.68/1,091-chunk price to the frozen 86,607-chunk scope gives
  ~9.4k escalation chunks ≈ **$213 against the $11 booking** — confirming (again, now on real raws rather
  than the rehearsal) that D12's cap-prioritised escalation covers only the top slice, and that the
  uncovered remainder is a C2 agenda item stated honestly rather than silently dropped.
- Remaining ladder: `p4c_union` -> precision gate -> `p4c_bulk_retry` -> `p4c_esc` ($11) ->
  union -> `p4c_audit` -> `p4c_recall` -> `p4c_report.py --write` -> tripwire -> commit+push.
  `--glean` and `p4c_glm2` are booked at $0 and deferred to a post-C2 owner decision (Amendment 1).
- Operationally hardened while waiting: the extraction daemon and a progress sampler are launched
  **detached** (`Start-Process`), not as children of a foreground shell, because foreground `pwsh`
  children are reaped when the call returns (this is exactly what killed the 11:08 supervisor). Only one
  supervisor runs at a time — the 11:11 pair was explicitly killed when the detached pair started, so the
  pool is never double-subscribed and spend never double-counts. The sampler appends one JSON line per
  10 min to `kb/logs/p4c_monitor.log` (`done`, `pct`, `attempts`, `out_tok`, `pipeline_spend`).
- **Ceiling is generation-throughput bound, not admission-bound (measured 2026-11-14T11:12Z, `kb/_t_tps.py`).**
  800 recent `p4c_bulk`/`DeepSeek-V4.1-Flash` ok rows: per-call output rate p10 **17.3**, p50 **31.4**,
  p90 **49.7** tok/s. The pool is 8 accounts (`AMD_TOKENLAB_API_KEY_1..8`), so aggregate generation
  capacity is at most ~8 × 31.4 = **~251 tok/s**. Live ledger: 3,334,669 out_tok over 2,540 done packs =
  **1,313 tok/pack**. 251 / 1,313 = **11.5 packs/min predicted** against **12.4 packs/min observed** —
  we are running at ~100% of what eight accounts can physically stream. This supersedes the earlier
  "provider admitted-concurrency cap" reading: admission (HTTP 429 / ceiling 144) is a *symptom* of the
  same saturation, and it explains why 48 workers and two concurrent 16-worker extractors both failed to
  beat 16 — there is no unused capacity to claim. **Worker count cannot be tuned past this; only more
  accounts raise it.** At 12.4 ok/min the remaining ~22,438 packs are ≈ **30 h** wall, and the wall-clock
  cost is fixed by provider streaming, not by our scheduling. §7.5 "partial coverage beats lower quality"
  (plan L438) is therefore the live lever if the owner wants P4c inside a shorter window than 30 h.
- **Bulk pass resume after the 04:45 host update restart (2026-11-14, ledger is the resume point).**
  Three detached processes only — supervisor PID 5888, daemon child PID 25088, progress sampler
  PID 21584 — and exactly one supervisor at a time, so the AMD pool is never double-subscribed and
  spend never double-counts. Observed mid-window: `done` (key-exact, model-scoped)
  **3,942 @ 13:22 → 4,539 @ 14:15**, i.e. **~11.3 ok/min** sustained, right at the ~11.5/min
  generation-bound prediction above; `attempts` 11,412 → 12,604; `out_tok` 4,594,619 → 5,196,044;
  pipeline spend **$9.5434 → $10.1157**. Latest batch line
  `[14:04:35] done ok=328 cached=0 err=72 retries=686 cost=$0.3142`, budget left **$67.631**.
  Rate since: **4,640 @ 14:25 → 4,804 @ 14:36 → 4,912 @ 14:46 → 5,051 @ 14:57 → 5,138 @ 15:07**
  (~11.6 ok/min over 14:25→14:57, then a slower 15:07 window at ~8.4), `attempts` 12,923 → 13,950,
  `out_tok` 5,274,220 → 5,765,128, pipeline spend **$10.1933 → $10.6646**; 20.57% of packs banked.
  `kb/logs/p4c_bulk16.err.log` mtime is frozen at **11:06:32** (my own force-kill dump, not a crash), so
  there has been no spontaneous interpreter abort since the detached relaunch. Remaining ~20.4k packs
  ⇒ **~30 h** wall at this rate; nothing about worker count can shorten it (see the ceiling bullet).
- **P4c→P5 contract checked before P5 runs: no `rungs/` files are required.** `p5_build.default_gated_paths()`
  lists `rungs/p4c_bulk|p4c_bulk_retry|p4c_esc|p4c_glm2.jsonl` after the union export, but no script writes
  them, and `load_gated` skips missing files. That is benign rather than a latent break: `p4c_union.build`
  does **not** read rung files at all — it replays the ledger by `(pass, model)` from `SOURCE_SPEC` and
  emits one row per chunk — and its `union/gated_union.jsonl` is first in precedence, so every source
  (bulk, retry, escalation) reaches P5 through the union row's merged `kept` records regardless. The rung
  paths remain a fallback for a per-rung rebuild. Contract closed; no code change needed.

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
