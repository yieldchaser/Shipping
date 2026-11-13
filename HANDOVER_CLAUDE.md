# Status & Infrastructure Handover (November 13, 2026)

## 1. System Stability & Lock Remediation
* **OS / Memory**: Cleared 6.1 GB dead storage (purged 5.66 GB stale `.tmp.driveupload` chunks + temp files). C: drive free space at ~11 GB. Chrome `HighEfficiencyModeEnabled=1` enabled in registry. 20 dead/orphaned background processes purged.
* **SQLite Concurrency**: Patched `kb/runner.py` with `PRAGMA journal_mode=WAL;` and `busy_timeout=60000;`. DDL table/index creation moved to one-time initialization guard `init_ledger()`. `sqlite3.OperationalError: disk I/O error` fully eliminated.

## 2. Gateway & Credentials State
* **Agent Gateway (`agent_gateway.py` on port 4100)**: Active background daemon. Cap raised from $66 to $76 (unlocked $9.96 Enclave balance for spinal agent commands). Fallback model set to `cyberouter/deepseek-v4.1-flash` ($0.30/$1.20) to prevent timeouts and rapid drain.
* **AMD Token Lab Added (paid inference route — NOT free)**:
  * **8 accounts** registered (`_1`..`_8`); all individually valid; 160 RPM aggregate. One more ref
    name (`_9`) is probed by the rotation but is not present.
  * Stored in `~/.dsh/.credentials.yaml` as `AMD_TOKENLAB_API_KEY_1` .. `_8`. Never print or commit a key.
  * **Verified API Model Identifiers on AMD**:
    - `DeepSeek-V4.1-Flash` (the API model ID for 1017; note: passing `-1017` returns 404). Function-calling preflight tested and passed (`tools` mode).
    - `DeepSeek-V4-Flash` (0731; preflight passed, responds in <0.7s at 7% utilization). Fallback id; `json_object` mode.
  * `kb/config.yaml`: Provider `amd_tokenlab` registered with `base_url: https://api.tokenlab.amd.com/v1`,
    `kind: paid`, `price_in: 0.28`, `price_cached: 0.0056`, `price_out: 0.56` (per 1M tokens).
  * `kb/llm_runner.py`: Automatic round-robin rotation active across the `AMD_TOKENLAB_API_KEY_*` pool.
    `key_pool_size("auto", "DeepSeek-V4.1-Flash")` must return 8 before any pass; the runner uses that
    to decide that an auth failure is a soft, rotatable failure rather than a fatal §6 stop.
  * Rejection profile: **every** refusal observed is `HTTP 429`
    `model_concurrency_rate_limit_exceeded` — a shared model-wide concurrency limit of 144. That is not
    per-key quota, so more keys or slower pacing do not fix it; retries and wave-based back-off do.
* **Ultrafast Status**: Severely congested (5/5 slots full, 47 in line on `ultrafast.trytokenfactory.dev`). Generates 300s stream timeouts. Excluded from bulk extraction. Its config entry and its 1,490 stored raws stay for the record; no new Ultrafast calls are made.

## 3. Shipping GraphRAG Build Status
* **Branch**: `kb-build` in `C:\Users\Dell\Github\Shipping`.
* **Workload Remaining**: ~24,670 packs of the 24,978 frozen scope (1,490 Ultrafast raws + the growing
  AMD count, counted model-scoped from the ledger). Measured **825 output tokens per accepted pack**.
* **Throughput**: worker-bound, not ceiling-bound. Measured 2026-11-13 (real packs, 300 s windows):
  4 workers / 6 rpm → **2.67 ok/min**, 16 workers / 120 rpm → **11.00 ok/min** (chosen), 32 / 240 →
  9.60. The optimum is the code default in `kb/p4b_run.runner_for`; `KB_AMD_WORKERS` / `KB_AMD_RATE`
  override it. At 16 workers the remaining scope is **≈1.6 days wall**, not the ~5.6 days the
  original 4-worker setting implied. Overnight runs go faster under `powercfg`-free conditions only —
  no special flags needed.
* **Launch Command**:
  ```bash
  cmd /c "cd /d C:\Users\Dell\Github\Shipping && python -X utf8 -u kb/p4c_daemon.py --pass p4c_bulk --model DeepSeek-V4.1-Flash --quota 0 --chunk 400 --shard 200 --cap 31.25 >> kb/logs/p4c_bulk_daemon.log 2>&1"
  ```
  Use the exact API id `DeepSeek-V4.1-Flash`. The string `DeepSeek-V4.1-Flash-1017` 404s on this
  provider. Fallback id is `DeepSeek-V4-Flash`. `--quota 0` means "no daily token ceiling": AMD's
  limiter is a **shared model concurrency ceiling of 144**, not a per-key daily quota. Every one of the
  8 accounts is individually valid; a transient 401/403/429 on one call is a soft failure — the runner
  rotates to the next key and continues, and must never treat it as fatal for the shard.
* **Quality & Budget Policy**: Bulk extraction on AMD Token Lab is **paid, not free**. Measured tariff
  $0.28/M in, $0.0056/M cached in, $0.56/M out ⇒ $0.001249/call and **$0.000871 per accepted pack**
  live at 16 workers (parity harness: $0.00134); the remaining scope projects to **≈$21.5**, inside the
  `p4c_bulk_extraction` booking ($31.25). The $82 pipeline cap is
  held by rebooking the glm-5.3 second extractor to $0 (the AMD pass IS the second extractor) and
  trimming the escalation line to $11. The enclave agent reserve is untouched by bulk — extraction
  bypasses the gateway entirely. Verify both the tariff and the pool size before any relaunch:
  `python -X utf8 -u kb/_t_cost.py` and `python -X utf8 -u kb/_t_pool.py`.
