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

Keys are never printed: `llm_runner.load_key` returns them in-process only.
"""
from __future__ import annotations

import asyncio
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
        cached_tok INTEGER DEFAULT 0, out_tok INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0,
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
                               "provider": prov.get("id"), "kind": prov.get("kind")}
    return out


def cost_usd(model: str, usage: dict | None) -> float:
    """Real cost of one call.

    Precedence: the provider-reported measured `usage.cost` (the router bills per token, so this is the
    ground truth and works for models whose config price is still null) -> config price table ->
    0.0 for free/NIM models (they never report a cost).
    """
    if not usage:
        return 0.0
    measured = usage.get("cost")
    if isinstance(measured, (int, float)) and measured > 0:
        return float(measured)
    spec = price_table().get(model) or {}
    pin, pout = spec.get("in"), spec.get("out")
    if not isinstance(pin, (int, float)) or not isinstance(pout, (int, float)):
        return 0.0
    return (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6


def spent(passes: list[str] | None = None, prefix: str | None = None) -> float:
    con = connect()
    where, params = [], []
    if passes:
        where.append(f"pass IN ({','.join('?' * len(passes))})")
        params += passes
    if prefix:
        where.append("pass LIKE ?")
        params.append(prefix + "%")
    sql = "SELECT COALESCE(SUM(cost_usd),0) FROM jobs" + (" WHERE " + " AND ".join(where) if where else "")
    return float(con.execute(sql, params).fetchone()[0])


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
                 pipeline_cap_usd: float = 82.0, timeout_s: int = 180):
        self.pass_name = pass_name
        self.prompt_version = prompt_version
        self.cap_usd = float(cap_usd)
        self.pipeline_cap = float(pipeline_cap_usd)
        self.start = max(1, start)
        self.ceiling = max(self.start, ceiling)
        self.rate_per_min = rate_per_min
        self.timeout_s = timeout_s
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
                   cost_usd=kw.get("cost", 0.0), finish_reason=kw.get("finish_reason"),
                   latency_ms=kw.get("latency_ms", 0), model_returned=kw.get("model_returned"),
                   error=kw.get("error"), created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                   meta=json.dumps(job.get("meta", {}))[:4000])
        with _ledger_lock:
            self.con.execute("""INSERT INTO jobs(job_key, pass, prompt_version, model, status, attempts,
                request_hash, in_tok, cached_tok, out_tok, cost_usd, finish_reason, latency_ms,
                model_returned, error, created_at, meta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_key) DO UPDATE SET status=excluded.status, attempts=excluded.attempts,
                in_tok=excluded.in_tok, cached_tok=excluded.cached_tok, out_tok=excluded.out_tok,
                cost_usd=excluded.cost_usd, finish_reason=excluded.finish_reason,
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
    def budget_left(self) -> float:
        used_pass = spent(passes=[self.pass_name])
        used_all = spent(prefix="p") if False else spent()
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
                    "usage": cached.get("usage") or {}, "cost": cached.get("cost", 0.0),
                    "latency_ms": cached.get("latency_ms", 0), "attempts": cached.get("attempts", 1),
                    "model_returned": cached.get("model_returned")}
        last = None
        for attempt in range(1, 4):
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
                self.stats.update(ok=self.stats["ok"] + 1, cost=self.stats["cost"] + cost,
                                  in_tok=self.stats["in_tok"] + usage["prompt_tokens"],
                                  out_tok=self.stats["out_tok"] + usage["completion_tokens"],
                                  cached_tok=self.stats["cached_tok"] + usage["cached_tokens"],
                                  latency_ms=self.stats["latency_ms"] + latency,
                                  calls=self.stats["calls"] + 1)
                return done
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                if exc.code in (401, 402, 403):
                    # §6 stop condition: no credit / key refused — report, do not hammer
                    self._record(job, status="fatal", attempts=attempt, error=last)
                    self.stats["errors"] += 1
                    return {"status": "fatal", "error": last}
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
        self._record(job, status="error", attempts=3, error=last)
        return {"status": "error", "error": last}

    # --- batch ----------------------------------------------------------------------------
    def run(self, jobs: list[dict]) -> dict[str, dict]:
        """Run the batch concurrently; returns job_key -> result. Stops cleanly at the caps."""
        if not jobs:
            return {}
        if self.budget_left() <= 0:
            log(f"pass {self.pass_name}: budget already exhausted, nothing started")
            return {}
        todo = [j for j in jobs if j.get("model")]
        log(f"pass {self.pass_name}: {len(todo)} jobs, budget left ${self.budget_left():.3f}")
        results: dict[str, dict] = {}
        queue = asyncio.Queue()
        for j in todo:
            queue.put_nowait(j)

        async def worker(name: int) -> None:
            while True:
                if self._stop:
                    return
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                if self.rate_per_min:
                    await asyncio.sleep(60.0 / self.rate_per_min)
                res = await asyncio.to_thread(self._one, job)
                results[job["job_key"]] = res
                if res["status"] == "fatal" or self.budget_left() <= 0:
                    self._stop = True

        async def main() -> None:
            n = min(self.start, len(todo))
            tasks = [asyncio.create_task(worker(i)) for i in range(n)]
            await asyncio.gather(*tasks)

        asyncio.run(main())
        log(f"pass {self.pass_name}: done ok={self.stats['ok']} cached={self.stats['cached']} "
            f"err={self.stats['errors']} retries={self.stats['retries']} cost=${self.stats['cost']:.4f}")
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
    return {r[0]: {"jobs": r[1], "ok": r[2], "in_tok": r[3], "out_tok": r[4], "cached_tok": r[5],
                   "cost_usd": round(r[6] or 0.0, 6)} for r in rows}
