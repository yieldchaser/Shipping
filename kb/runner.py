"""Pipeline LLM runner: ledger, budget guard, drift guard, concurrency ramp (plan §7.5).

Every paid/free extraction call in layer C goes through this module so spend is auditable and
interrupted runs resume for free (plan §10.2). Not a generic HTTP client: `llm_runner.chat` does the
request, this module owns the accounting.

Guarantees:
  - Ledger: SQLite `kb/state/ledger.sqlite`, table `jobs` with the exact §7.5 columns. One row per
    `job_key` = sha256(model | prompt_version | pass | packed chunk shas), committed after every
    response, so a re-run of a finished key makes no call.
  - Raw responses: `kb/state/raw/<pass>/<job_key>.json` (never committed) — gates can be re-run free.
  - Budget guard: live spend = ledger sum of the pipeline passes; each pass has a hard cap and the
    pipeline global cap ($82) is enforced on top. The runner stops cleanly (partial coverage) at
    either cap instead of overshooting.
  - Drift guard: `model_returned` per requested model is pinned on first success; a change pauses
    that model and reports it.
  - Concurrency: starts at `start` workers, ramps while the error rate stays under 2% (cap `ceiling`),
    exponential backoff with jitter on 429/5xx. Free NIM capacity is used before paid (plan §7.5).
  - Soft auth failures (owner directive 2026-11-13, multi-key free pools): on 401/402/403 the runner
    retries, and `llm_runner.load_key` rotates to the next key in the pool, instead of ending the
    shard. Only when every attempt in the ladder failed for that reason does the job settle as
    `status="fatal"` — a single-key paid provider still stops at §6 on its first refused call.

Keys are never printed: `llm_runner.load_key` returns them in-process only.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import random
import sqlite3
import threading
import time
import urllib.error
from pathlib import Path

import yaml

import llm_runner as LR
import money as M

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "kb/state"
LEDGER = STATE / "ledger.sqlite"
RAW = STATE / "raw"
CONFIG = ROOT / "kb/config.yaml"
LOG = ROOT / "kb/logs/runner.log"

_ledger_lock = threading.Lock()


def job_key(*parts: str) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


_SCHEMA_INIT = False


def init_ledger() -> None:
    global _SCHEMA_INIT
    if _SCHEMA_INIT:
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(LEDGER, timeout=60.0)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.execute("""CREATE TABLE IF NOT EXISTS jobs(
        job_key TEXT PRIMARY KEY, pass TEXT, prompt_version TEXT, model TEXT, status TEXT,
        attempts INTEGER DEFAULT 0, request_hash TEXT, in_tok INTEGER DEFAULT 0,
        cached_tok INTEGER DEFAULT 0, out_tok INTEGER DEFAULT 0, cost_usd REAL,
        finish_reason TEXT, latency_ms INTEGER, model_returned TEXT, error TEXT,
        created_at TEXT, meta TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS jobs_pass ON jobs(pass)")
    con.commit()
    con.close()
    _SCHEMA_INIT = True


def connect() -> sqlite3.Connection:
    init_ledger()
    con = sqlite3.connect(LEDGER, timeout=60.0, check_same_thread=False)
    con.execute("PRAGMA busy_timeout=60000")
    return con


def price_table() -> dict:
    """{model: {in, out, provider}} from kb/config.yaml (providers is a list, prices per 1M tok)."""
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    out = {}
    for prov in (cfg.get("providers") or []):
        for spec in (prov.get("models") or []):
            out[spec["id"]] = {"in": spec.get("price_in"), "out": spec.get("price_out"),
                               "cached": spec.get("price_cached"),
                               "provider": prov.get("id"), "kind": prov.get("kind")}
    return out


def _tokens(usage: dict, key: str) -> float | None:
    """A token count reported in `usage`, or `None` when the reported value is unreadable.

    Tri-state, matching the money contract: the key being *absent* (or explicitly null) is the
    documented absent-key convention - that count was not reported, so it contributes no tokens
    (`0.0`). A *present* value that cannot be read as a finite number (a `bool`, a string, `NaN`,
    `inf`) is a broken read, not a zero, and poisons the price for the whole call.
    """
    v = usage.get(key)
    if v is None:
        return 0.0
    return M.as_float(v)


def cost_usd(model: str, usage: dict | None) -> float | None:
    """Real cost of one call, or `None` when it cannot be measured.

    Precedence: the provider-reported measured `usage.cost` (the router bills per token, so this is the
    ground truth and works for models whose config price is still null) -> config price table ->
    `None` when neither source can price the call.

    Defect 17/21 class: this used to return `0.0` for both "the route is genuinely free" and "no
    measurement exists", so an empty/absent `usage` block, an unknown model id, or a config price
    that is still `null` all booked as *measured zero* — a fabricated measurement that understates
    spend and lets a pass run past the §7.5 cap unnoticed. Two states are now distinct:

        None  -> unmeasured (no usage reported, unknown model, config price null)
        0.0   -> measured zero (the config tariff for that model is an explicit 0.0)

    A provider-reported number is authoritative even when it is exactly zero; free in-process routes
    (`nim`, `ultrafast`) are priced from their explicit `0.0` config tariff, not from silence.

    Defect 23 (same class, the *config* arm): every numeric below is a read of an external source -
    the provider's `usage` block and `kb/config.yaml` - and each was tested with a bare
    `isinstance(x, (int, float))`, which `bool` passes (`price_in: true` books a $1/M tariff) and
    which lets `float("1" + "0"*400) == inf` through untouched, booking an infinite cost into the
    ledger. `float(usage.get("prompt_tokens", 0) or 0)` is the same fabrication from the other side:
    a *present but unreadable* token count silently became a zero token count, understating the call.
    All of it now goes through the single guard (`money.as_float`), with the one documented
    convention kept explicit: a key that is *absent* (or explicitly null) contains no reported
    count, which is the absent-key case, not a failed read. A `usage.cost` that is present but
    unreadable is likewise a broken measurement - the tariff is not substituted for it.
    """
    if not usage:
        return None
    if "cost" in usage and usage["cost"] is not None:
        # Present-and-reported: authoritative, even when exactly 0.0. If it is present but
        # unreadable, that is a broken measurement - do NOT substitute the config tariff, which
        # would report a different (fabricated) number for a call the provider did price.
        return M.as_float(usage["cost"])
    spec = price_table().get(model) or {}
    pin, pout = M.as_float(spec.get("in")), M.as_float(spec.get("out"))
    if pin is None or pout is None:
        return None
    ptok, otok, ctok = (_tokens(usage, k) for k in ("prompt_tokens", "completion_tokens",
                                                    "cached_tokens"))
    if ptok is None or otok is None or ctok is None:
        return None  # a reported count was unreadable: this call cannot be priced
    pcached = M.as_float(spec.get("cached"))
    if pcached is None and spec.get("cached") is not None:
        # The config declares a cached tariff (present) but it cannot be read: the call's price is
        # unmeasurable. Silently ignoring it would bill the cached prefix at the full input rate --
        # a fabricated, higher number -- so the whole call is UNMEASURED instead.
        return None
    if pcached is not None and 0 < ctok <= ptok:
        # Cache-aware tariff: cached prefix tokens are billed at the discounted cached rate
        # (AMD Token Lab: in $0.28/M vs cached $0.0056/M). Only used when the config records one.
        return ((ptok - ctok) * pin + ctok * pcached + otok * pout) / 1e6
    return (ptok * pin + otok * pout) / 1e6


def spent_rows(passes: list[str] | None = None, prefix: str | None = None) -> tuple[float | None, int]:
    """The measured cost sum and the number of ledger rows that matched the filter.

    `n` counts *matching rows*, including a row whose `cost_usd` is SQL NULL (a call that failed
    before the provider reported any usage, e.g. an HTTP 429 with retries exhausted): such a row
    contributes nothing to the SUM but is still a row the pass wrote. `test_p7_ask` pins exactly that
    (`rows == 1 and total is None`), so do not "fix" `n` into a priced-row count.

    The earlier note here claimed the ledger had no NULL `cost_usd` at all (28,856 of 28,856 rows).
    That is no longer true: the live ledger carries a handful of NULL-cost rows, all of them
    costless failures. `COALESCE(...,0)` therefore has two distinct firing cases, and conflating
    them was the original defect - `spent()` reported the measured-zero string `0.0` for a pass that
    was never priced, was never run, or whose rows were replaced. "Unmeasured" and "measured zero"
    are different claims, and an owner-facing spend field must not conflate them (Defect 17 class,
    Lesson 69). This returns `(None, 0)` when *no row matched*: unmeasured, not free. A pass whose
    rows all matched but were all NULL also yields `(None, n)` - the sum is unmeasured while the
    rows are real - and a pass with at least one priced row yields that measured total.
    """
    con = connect()
    where, params = [], []
    if passes:
        where.append(f"pass IN ({','.join('?' * len(passes))})")
        params += passes
    if prefix:
        where.append("pass LIKE ?")
        params.append(prefix + "%")
    tail = " WHERE " + " AND ".join(where) if where else ""
    n = int(con.execute("SELECT COUNT(*) FROM jobs" + tail, params).fetchone()[0])
    if not n:
        return None, 0
    total = con.execute("SELECT SUM(cost_usd) FROM jobs" + tail, params).fetchone()[0]
    return (float(total) if total is not None else None), n


def spent_exact(passes: list[str] | None = None, prefix: str | None = None) -> float | None:
    """`spent()` that keeps "no measurement" distinct from "measured zero": `None` when absent."""
    return spent_rows(passes, prefix)[0]


def spent(passes: list[str] | None = None, prefix: str | None = None) -> float:
    """Arithmetic spend, collapsing an absent measurement to `0.0`.

    This is the wrong function for anything the owner reads: use `spent_exact()` for reports and
    render through `money.fmt_usd`, so an unmeasured pass prints `UNMEASURED` rather than `$0.0000`.
    Kept `float`-returning so budget arithmetic (`budget_left`, daemon caps) is never handed a None.
    """
    total = spent_exact(passes, prefix)
    return 0.0 if total is None else total


def pipeline_cap() -> float | None:
    """The §7.5 global pipeline cap, authored in `kb/config.yaml` `budget.pipeline_cap_usd`.

    `None` when the config or the key is unreadable: budget arithmetic then refuses to run (see
    `Runner.budget_left`) instead of substituting a made-up `$82` that a raised cap would contradict.
    """
    try:
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        v = (cfg.get("budget") or {}).get("pipeline_cap_usd")
    except (OSError, ValueError):
        return None
    return M.as_float(v)


def raw_path(pass_name: str, key: str) -> Path:
    p = RAW / pass_name / f"{key}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def done_keys(pass_name: str) -> dict[str, dict]:
    con = connect()
    rows = con.execute("SELECT job_key, status, model_returned, in_tok, out_tok, cost_usd FROM jobs WHERE pass=?",
                       [pass_name]).fetchall()
    return {r[0]: {"status": r[1], "model_returned": r[2], "in_tok": r[3], "out_tok": r[4], "cost": r[5]}
            for r in rows}


class BudgetExceeded(RuntimeError):
    pass


class Runner:
    """Runs a batch of extraction jobs for one pass, resumable and budget-capped."""

    def __init__(self, pass_name: str, prompt_version: str, cap_usd: float,
                 start: int = 8, ceiling: int = 48, rate_per_min: int | None = None,
                 pipeline_cap_usd: float | None = None, timeout_s: int = 180, attempts: int = 3):
        self.pass_name = pass_name
        self.prompt_version = prompt_version
        self.cap_usd = float(cap_usd)
        # §7.5 global cap is authored in `kb/config.yaml` `budget.pipeline_cap_usd`; a hardcoded
        # literal here would silently diverge from the gate the tripwire checks (Lesson 69: a
        # default argument in a money path is a fabricated measurement).
        if pipeline_cap_usd is None:
            pipeline_cap_usd = pipeline_cap()
        self.pipeline_cap = None if pipeline_cap_usd is None else float(pipeline_cap_usd)
        self.start = max(1, start)
        self.ceiling = max(self.start, ceiling)
        self.rate_per_min = rate_per_min
        self.timeout_s = timeout_s
        self.attempts = max(1, int(attempts))
        self.con = connect()
        self.prices = price_table()
        self.drift: dict[str, str] = {}
        self.stats = {"calls": 0, "ok": 0, "cached": 0, "errors": 0, "retries": 0, "cost": 0.0,
                      "in_tok": 0, "out_tok": 0, "cached_tok": 0, "latency_ms": 0}
        self._stop = False

    # --- ledger ---------------------------------------------------------------------------
    def _record(self, job: dict, **kw) -> None:
        row = dict(job_key=job["job_key"], pass_=self.pass_name, prompt_version=self.prompt_version,
                   model=job["model"], status=kw.get("status", "ok"), attempts=kw.get("attempts", 1),
                   request_hash=job.get("request_hash", ""), in_tok=kw.get("in_tok", 0),
                   cached_tok=kw.get("cached_tok", 0), out_tok=kw.get("out_tok", 0),
                   cost_usd=kw.get("cost"), finish_reason=kw.get("finish_reason"),
                   latency_ms=kw.get("latency_ms", 0), model_returned=kw.get("model_returned"),
                   error=kw.get("error"), created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                   meta=json.dumps(job.get("meta", {}))[:4000])
        with _ledger_lock:
            self.con.execute("""INSERT INTO jobs(job_key, pass, prompt_version, model, status, attempts,
                request_hash, in_tok, cached_tok, out_tok, cost_usd, finish_reason, latency_ms,
                model_returned, error, created_at, meta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_key) DO UPDATE SET status=excluded.status, attempts=excluded.attempts,
                in_tok=excluded.in_tok, cached_tok=excluded.cached_tok, out_tok=excluded.out_tok,
                -- Defect 17/19 class (real cost dropped): a FAILED re-attempt books no cost, and this
                -- upsert keys on the same `job_key`. Plain `cost_usd=excluded.cost_usd` therefore
                -- replaced an earlier measured cost for that job with NULL. Reachable whenever the
                -- ledger says `ok` but the raw JSON is gone (e.g. the planned scratch raw-dir
                -- cleanup): `_cached` then re-calls, and a failure erases spend that really happened.
                -- COALESCE keeps the earlier measurement; a brand-new failed row is still NULL.
                cost_usd=COALESCE(excluded.cost_usd, jobs.cost_usd),
                finish_reason=excluded.finish_reason,
                latency_ms=excluded.latency_ms, model_returned=excluded.model_returned,
                error=excluded.error""",
                (row["job_key"], row["pass_"], row["prompt_version"], row["model"], row["status"],
                 row["attempts"], row["request_hash"], row["in_tok"], row["cached_tok"], row["out_tok"],
                 row["cost_usd"], row["finish_reason"], row["latency_ms"], row["model_returned"],
                 row["error"], row["created_at"], row["meta"]))
            self.con.commit()

    def _cached(self, job: dict) -> dict | None:
        con = connect()
        r = con.execute("SELECT status FROM jobs WHERE job_key=?", [job["job_key"]]).fetchone()
        if not r or r[0] != "ok":
            return None
        p = raw_path(self.pass_name, job["job_key"])
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None

    # --- cheap helpers --------------------------------------------------------------------
    def budget_left(self) -> float | None:
        """Headroom under both the per-pass cap and the §7.5 pipeline cap.

        `None` means the pipeline cap itself could not be read — a budget that cannot be measured
        must not be reported as `0.0`, because callers treat `<= 0` as "stop" and `0.0` would read as
        a legitimately exhausted budget. Callers decide: `p4b_run` refuses to start, the daemon
        re-reads the config on its next tick.
        """
        used_pass = spent(passes=[self.pass_name])
        used_all = spent()
        if self.pipeline_cap is None:
            return None
        return min(self.cap_usd - used_pass, self.pipeline_cap - used_all)

    def _check_drift(self, job: dict, returned: str | None) -> None:
        if not returned:
            return
        pinned = self.drift.get(job["model"])
        if pinned is None:
            self.drift[job["model"]] = returned
        elif pinned != returned:
            self._stop = True
            log(f"DRIFT {job['model']}: pinned {pinned} returned {returned}; pausing pass")

    @staticmethod
    def _usage(body: dict) -> dict:
        u = body.get("usage") or {}
        cached = 0
        det = u.get("prompt_tokens_details") or {}
        if isinstance(det, dict):
            cached = det.get("cached_tokens") or 0
        cached = cached or u.get("cached_tokens") or 0
        return {"prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                "cached_tokens": cached, "cost": u.get("cost")}

    def _one(self, job: dict) -> dict:
        """One call with retries. Returns {status, raw, body, usage, cost, latency_ms, attempts, error}."""
        cached = self._cached(job)
        if cached is not None:
            self.stats["cached"] += 1
            return {"status": "cached", "raw": cached.get("raw"), "body": cached.get("body"),
                    "usage": cached.get("usage") or {}, "cost": cached.get("cost"),
                    "latency_ms": cached.get("latency_ms", 0), "attempts": cached.get("attempts", 1),
                    "model_returned": cached.get("model_returned")}
        last = None
        soft_auth = LR.key_pool_size("auto", job["model"]) > 1
        n_att = max(2, self.attempts) if soft_auth else self.attempts
        for attempt in range(1, n_att + 1):
            t0 = time.time()
            try:
                body = LR.chat(job["model"], job["messages"], max_tokens=job.get("max_tokens", 2500),
                               temperature=job.get("temperature", 0.0), timeout_s=self.timeout_s,
                               extra_body=job.get("extra_body"))
                latency = int((time.time() - t0) * 1000)
                choice = (body.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                calls = msg.get("tool_calls") or []
                raw = None
                if calls:
                    raw = (calls[0].get("function") or {}).get("arguments")
                if raw is None:
                    raw = msg.get("content")
                usage = self._usage(body)
                cost = cost_usd(job["model"], body.get("usage") or usage)
                returned = body.get("model")
                self._check_drift(job, returned)
                done = {"status": "ok", "raw": raw, "body": body, "usage": usage, "cost": cost,
                        "latency_ms": latency, "attempts": attempt, "model_returned": returned,
                        "finish_reason": choice.get("finish_reason")}
                if not raw or not str(raw).strip():
                    last = f"blank response (finish={choice.get('finish_reason')})"
                    raise ValueError(last)
                raw_path(self.pass_name, job["job_key"]).write_text(json.dumps(done), encoding="utf-8")
                self._record(job, status="ok", attempts=attempt, in_tok=usage["prompt_tokens"],
                             cached_tok=usage["cached_tokens"], out_tok=usage["completion_tokens"],
                             cost=cost, finish_reason=done.get("finish_reason"), latency_ms=latency,
                             model_returned=returned)
                self.stats.update(ok=self.stats["ok"] + 1,
                                  # Tri-state: one unpriced call makes the running figure
                                  # UNMEASURED (`None`) rather than a total that quietly omits it.
                                  cost=(None if (self.stats["cost"] is None or cost is None)
                                        else self.stats["cost"] + cost),
                                  in_tok=self.stats["in_tok"] + usage["prompt_tokens"],
                                  out_tok=self.stats["out_tok"] + usage["completion_tokens"],
                                  cached_tok=self.stats["cached_tok"] + usage["cached_tokens"],
                                  latency_ms=self.stats["latency_ms"] + latency,
                                  calls=self.stats["calls"] + 1)
                return done
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                if exc.code in (401, 402, 403):
                    # §6 stop condition: no credit / key refused. A single-key provider stops here; a
                    # multi-account free pool (owner directive 2026-11-13) is a soft failure: the next
                    # attempt runs through `load_key` again, which rotates to the next key in the pool.
                    if not soft_auth:
                        self._record(job, status="fatal", attempts=attempt, error=last)
                        self.stats["errors"] += 1
                        return {"status": "fatal", "error": last}
                    self.stats["retries"] += 1
                    time.sleep(min(10, (2 ** attempt) * 0.5) + random.random())
                    continue
                if exc.code == 429 or exc.code >= 500:
                    self.stats["retries"] += 1
                    time.sleep(min(30, (2 ** attempt) * 0.5) + random.random())
                    continue
                self.stats["errors"] += 1
                self._record(job, status="error", attempts=attempt, error=last)
                return {"status": "error", "error": last}
            except Exception as exc:  # network, timeout, decode, blank
                last = f"{type(exc).__name__}: {exc}"
                self.stats["retries"] += 1
                time.sleep(min(30, (2 ** attempt) * 0.5) + random.random())
        self.stats["errors"] += 1
        final = "fatal" if soft_auth and (last or "").startswith("HTTP 40") else "error"
        self._record(job, status=final, attempts=n_att, error=last)
        return {"status": final, "error": last}

    # --- batch ----------------------------------------------------------------------------
    def run(self, jobs: list[dict]) -> dict[str, dict]:
        """Run the batch concurrently; returns job_key -> result. Stops cleanly at the caps."""
        if not jobs:
            return {}
        left = self.budget_left()
        if left is None:
            log(f"pass {self.pass_name}: pipeline cap unreadable, nothing started")
            return {}
        if left <= 0:
            log(f"pass {self.pass_name}: budget already exhausted, nothing started")
            return {}
        todo = [j for j in jobs if j.get("model")]
        # `budget left` is a *headroom*, not a spend: it is derived from the cap and is defined
        # whenever the cap is, so a plain figure is honest here.
        log(f"pass {self.pass_name}: {len(todo)} jobs, budget left {M.fmt_usd(self.budget_left())}")
        results: dict[str, dict] = {}
        queue = asyncio.Queue()
        for j in todo:
            queue.put_nowait(j)

        async def worker(name: int, ex: concurrent.futures.ThreadPoolExecutor) -> None:
            loop = asyncio.get_running_loop()
            while True:
                if self._stop:
                    return
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                if self.rate_per_min:
                    await asyncio.sleep(60.0 / self.rate_per_min)
                res = await loop.run_in_executor(ex, self._one, job)
                results[job["job_key"]] = res
                if res["status"] == "fatal" or (self.budget_left() or 0.0) <= 0:
                    self._stop = True

        async def main() -> None:
            n = min(self.start, len(todo))
            # `asyncio.to_thread` would use the loop's *default* executor, capped at
            # min(32, cpu_count + 4) — 12 on the 8-core build box, so 16 requested workers measured
            # as ~10.6 real in-flight calls and the batch ran at 13.5 ok/min instead of ~22. Size the
            # pool to the worker count we actually asked for.
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=n, thread_name_prefix=f"kb-{self.pass_name}") as ex:
                tasks = [asyncio.create_task(worker(i, ex)) for i in range(n)]
                await asyncio.gather(*tasks)

        asyncio.run(main())
        # `self.stats['cost']` is accumulated in-process from real `usage.cost` readings, so a genuine
        # zero is possible and must keep reading as `$0.0000`; `:.4f` would flatten a sub-cent batch
        # to that same string (Defect 17 class, Lesson 69).
        log(f"pass {self.pass_name}: done ok={self.stats['ok']} cached={self.stats['cached']} "
            f"err={self.stats['errors']} retries={self.stats['retries']} "
            f"cost={M.fmt_usd(self.stats['cost'])}")
        return results


def summarise_ledger(passes: list[str] | None = None) -> dict:
    con = connect()
    sql = "SELECT pass, COUNT(*), SUM(status='ok'), SUM(in_tok), SUM(out_tok), SUM(cached_tok), SUM(cost_usd) FROM jobs"
    params = []
    if passes:
        sql += f" WHERE pass IN ({','.join('?' * len(passes))})"
        params = passes
    sql += " GROUP BY pass ORDER BY pass"
    rows = con.execute(sql, params).fetchall()
    # A row exists but its `cost_usd` is NULL => the call was booked without a measurement; `None`
    # keeps that distinct from a measured `0.0` row (`money.round_usd` passes None through).
    return {r[0]: {"jobs": r[1], "ok": r[2], "in_tok": r[3], "out_tok": r[4], "cached_tok": r[5],
                   "cost_usd": M.round_usd(r[6])} for r in rows}
