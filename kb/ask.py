"""P7 answer engine (plan §8, §9): tools + answer contract + CLI.

Design note (5 lines):
1. Deterministic skeleton, LLM only where language is required: a heuristic `search`
   always runs, an LLM planner may add up to two typed tool calls, and an LLM composer
   writes the answer from the tool results only.
2. Answer contract: every number must occur in a tool result (numeric match with unit /
   rounding tolerance), every claim sentence must carry a `[cite:kind:id]` handle that
   resolves through the `cite` tool; a sentence failing either check is dropped, and one
   regeneration is attempted before the answer degrades to "not in the data".
3. "What did we know on D" is enforced by `as_of=D` filters (published_at <= D) on every
   tool that accepts a window, never by asking the model to remember.
4. Declared gaps (`gaps` tool / v_gaps) are surfaced in the answer when they cover the
   window, so a refusal can name what is missing instead of inventing.
5. Default model is the bulk model on the AMD Token Lab pool (owner amendment to D10; PAID, measured
   $0.28/M in, $0.0056/M cached, $0.56/M out -- not a free tier); one glm-5.3 escalation is
   allowed only when the number post-check fails and the pipeline budget still has room.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools as T  # noqa: E402
import llm_runner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P7_DIR = ROOT / "kb/state/p7"
CALL_LOG = P7_DIR / "calls.jsonl"
LEDGER = None  # resolved to runner.LEDGER on first book; tests point this at a scratch file
PASS_NAME = "p7_ask"

DEFAULT_MODEL = "DeepSeek-V4.1-Flash"  # AMD Token Lab bulk model (owner amendment to D10; PAID,
# measured $0.28/M in, $0.0056/M cached, $0.56/M out -- not a free tier)
ESCALATION_MODEL = "glm-5.3"
MAX_TOOL_CALLS = 4
MAX_ANSWER_CHARS = 1200
NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
CITE = re.compile(r"\[cite:([a-z]+:[^\]]+)\]")
DATE = re.compile(r"\b(?:as (?:known|of)(?: on)?|on)\s+(\d{4}-\d{2}-\d{2})", re.I)

NOT_IN_DATA = "Not in the data."

PLANNER_SYSTEM = (
    "You plan tool calls for a maritime-shipping question-answering system.\n"
    "Available tools (JSON arguments):\n" + json.dumps(T.TOOLS, indent=1) + "\n"
    "Reply with ONLY a JSON array of at most 2 calls, each {\"tool\": name, \"args\": {...}}. "
    "Prefer `search` for text, `sql` over v_* views for numbers, `graph`/`ppr` for entities, "
    "`summary` for trends, `gaps` for coverage. Reply [] if `search` alone suffices. "
    "Never write prose, never invent tool names.")

COMPOSER_SYSTEM = (
    "You answer maritime shipping questions using ONLY the tool results provided.\n"
    "Rules: (1) every sentence must end with one or more citation handles copied exactly "
    "from the results, written as [cite:kind:id]; (2) every number you write must appear "
    "verbatim in a cited result, with its unit; (3) no outside knowledge, no estimates, no "
    "rounding beyond the printed precision; (4) if the results do not contain the answer, "
    "reply exactly 'NOT_IN_DATA'; (5) max 4 sentences.")

ANSWER_FMT = (
    "Format: first line ANSWER: <one-sentence answer with numbers and [cite:...] handles>; "
    "then up to 3 lines each starting '- ' with a supporting fact and its [cite:...] handle.")


# --------------------------------------------------------------- utilities
def as_of_of(question: str) -> str | None:
    """Extract an explicit 'as known on D' date from the question, if any."""
    m = DATE.search(question or "")
    return m.group(1) if m else None


def numbers_in(text: str) -> list[float]:
    out = []
    for tok in NUM.findall(text or ""):
        tok = tok.replace(",", "").rstrip(".")
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out


def _result_numbers(obj) -> list[float]:
    """All numeric tokens in a tool result (strings scanned, floats taken directly)."""
    vals: list[float] = []

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            vals.append(float(x))
        elif isinstance(x, str):
            vals.extend(numbers_in(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(obj)
    return vals


def result_numbers(results: list[dict]) -> list[float]:
    vals = []
    for r in results:
        vals.extend(_result_numbers(r.get("result")))
    return vals


def number_ok(value: float, have: list[float]) -> bool:
    if not have:
        return False
    for h in have:
        if abs(value - h) <= max(1e-9, 0.005 * abs(value), 0.5 if abs(value) >= 100 else 0.01):
            return True
    return False


def strip_cites(text: str) -> str:
    """Remove [cite:kind:id] handles so their ids are not mistaken for answer numbers."""
    return CITE.sub(" ", text or "")


def numbers_supported(answer_text: str, have: list[float]) -> tuple[bool, list[float]]:
    missing = [v for v in numbers_in(strip_cites(answer_text)) if not number_ok(v, have)]
    return (not missing), missing


def parse_answer(text: str) -> dict:
    """Split the composer reply into sentences, their citations and the answer line."""
    raw = (text or "").strip()
    if not raw:
        return {"status": "empty", "answer": "", "sentences": [], "cites": []}
    if re.search(r"\bNOT_IN_DATA\b", raw):
        return {"status": "not_in_data", "answer": NOT_IN_DATA, "sentences": [], "cites": []}
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    sentences = []
    for ln in lines:
        body = re.sub(r"^(answer:|-|\*|\d+\.)\s*", "", ln, flags=re.I).strip()
        if not body:
            continue
        cites = [c.strip() for c in CITE.findall(body)]
        sentences.append({"sentence": body, "cites": cites})
    answer = ""
    for s in sentences:
        if s["sentence"].lower().startswith(("answer", "the ", "as of", "on ")):
            answer = s["sentence"]
            break
    if not answer and sentences:
        answer = sentences[0]["sentence"]
    return {"status": "ok", "answer": answer, "sentences": sentences,
            "cites": [c for s in sentences for c in s["cites"]]}


def contract_filter(parsed: dict, have: list[float], resolve) -> tuple[dict, dict]:
    """Apply number + citation rules sentence by sentence; drop failures."""
    kept, dropped = [], {"number_not_in_results": 0, "no_cite": 0, "cite_unresolved": 0}
    for s in parsed.get("sentences", []):
        if not s["cites"]:
            dropped["no_cite"] += 1
            continue
        resolved, bad = [], []
        for h in s["cites"]:
            info = resolve(h)
            (bad if info is None else resolved).append(h if info is None else info)
        if bad:
            dropped["cite_unresolved"] += len(bad)
            continue
        ok, _missing = numbers_supported(s["sentence"], have)
        if not ok:
            dropped["number_not_in_results"] += 1
            continue
        kept.append({"sentence": s["sentence"], "cites": resolved})
    text = " ".join(s["sentence"] for s in kept).strip()
    status = "ok" if kept else "not_in_data"
    return ({"status": status, "answer": text if kept else NOT_IN_DATA, "sentences": kept},
            dropped)


# ------------------------------------------------------------------ engine
def _book(model: str, usage: dict, cost: float, *, status: str = "ok", prompt_version: str = "p7-v1",
          error: str | None = None, latency_ms: int = 0, job_key: str | None = None) -> float:
    """Book one P7 model call into the shared `jobs` ledger. Returns the booked cost.

    Defect 15b: P7 used to record spend ONLY in `calls.jsonl` (see `_log_call`), so every P7 call
    -- the bulk writer on the PAID AMD route, the escalation, and the Gemma judge -- was invisible
    to `runner.spent()`, to the global pipeline cap in §7.5 and to `/stats`. This books the same
    call in the one authoritative ledger, priced by `runner.cost_usd` (measured `usage.cost` first,
    then the cache-aware config tariff). Best-effort by design: an unwritable ledger must never
    fail an answer, but it must also never silently pretend the call was free -- the JSONL call log
    remains the per-call trace.
    """
    usage = usage or {}
    cost = float(cost or 0.0)
    try:
        import runner as R
        key = job_key or R.job_key(PASS_NAME, prompt_version, model,
                                   hashlib.sha256(json.dumps(usage, sort_keys=True).encode()
                                                  ).hexdigest()[:16], uuid.uuid4().hex[:8])
        path = LEDGER or R.LEDGER
        if LEDGER is None:
            con = R.connect()
        else:  # scratch ledger (tests): create the same schema locally
            import sqlite3
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(path), timeout=60.0, check_same_thread=False)
            con.execute("""CREATE TABLE IF NOT EXISTS jobs(
                job_key TEXT PRIMARY KEY, pass TEXT, prompt_version TEXT, model TEXT, status TEXT,
                attempts INTEGER DEFAULT 0, request_hash TEXT, in_tok INTEGER DEFAULT 0,
                cached_tok INTEGER DEFAULT 0, out_tok INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0,
                finish_reason TEXT, latency_ms INTEGER, model_returned TEXT, error TEXT,
                created_at TEXT, meta TEXT)""")
        with R._ledger_lock:
            con.execute(
                """INSERT INTO jobs(job_key, pass, prompt_version, model, status, attempts,
                       request_hash, in_tok, cached_tok, out_tok, cost_usd, finish_reason,
                       latency_ms, model_returned, error, created_at, meta)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(job_key) DO UPDATE SET status=excluded.status,
                       in_tok=excluded.in_tok, cached_tok=excluded.cached_tok,
                       out_tok=excluded.out_tok, cost_usd=excluded.cost_usd, error=excluded.error""",
                (key, PASS_NAME, prompt_version, model, status, 1, "",
                 int(usage.get("prompt_tokens") or 0), int(usage.get("cached_tokens") or 0),
                 int(usage.get("completion_tokens") or 0), cost,
                 usage.get("finish_reason"), int(latency_ms or 0), None, error,
                 time.strftime("%Y-%m-%dT%H:%M:%S"), json.dumps({"source": "ask"})[:2000]))
            con.commit()
            con.close()
    except Exception:  # noqa: BLE001 - ledger write is best-effort; never break an answer
        pass
    return cost


def _chat(model: str, messages: list[dict], max_tokens: int = 400,
          timeout_s: int = 180) -> tuple[str, dict, float]:
    t0 = time.time()
    try:
        body = llm_runner.chat(model, messages, max_tokens=max_tokens, temperature=0.0,
                               timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001 - bill the attempt, then let the caller degrade
        _book(model, {}, 0.0, status="error", error=f"{type(exc).__name__}: {exc}",
              latency_ms=int((time.time() - t0) * 1000))
        raise
    text = ""
    try:
        text = body["choices"][0]["message"].get("content") or ""
    except Exception:  # noqa: BLE001
        text = ""
    usage = body.get("usage") or {}
    cost = 0.0
    try:
        import runner as R
        # Delegate to the one authoritative pricer: it prefers the provider-reported measured
        # `usage.cost`, then the cache-aware config tariff. A flat in/out computation here would
        # over-charge cache hits and ignore measured cost (Defect 14 class, found when the judge
        # moved onto the PAID AMD route with a 2%-of-input cache rate).
        cost = R.cost_usd(model, usage)
    except Exception:  # noqa: BLE001 - unknown model / unreadable config
        cost = 0.0
    latency_ms = int((time.time() - t0) * 1000)
    _book(model, usage, cost, latency_ms=latency_ms)
    _log_call({"model": model, "usage": usage, "cost_usd": round(cost, 6),
               "latency_ms": latency_ms})
    return text, usage, round(cost, 6)


def _log_call(rec: dict) -> None:
    P7_DIR.mkdir(parents=True, exist_ok=True)
    rec = dict(rec)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with CALL_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def default_calls(question: str, as_of: str | None) -> list[dict]:
    """Deterministic baseline tool calls that never depend on the model."""
    filters = {"published_to": as_of} if as_of else None
    return [{"tool": "search", "args": {"query": question, "k": 12, "filters": filters}}]


def plan_calls(question: str, as_of: str | None, model: str, chat=None) -> list[dict]:
    """Planner tool calls only. See `plan_calls_cost` to also capture the planner's spend."""
    return plan_calls_cost(question, as_of, model, chat=chat)[0]


def plan_calls_cost(question: str, as_of: str | None, model: str,
                    chat=None) -> tuple[list[dict], float]:
    """Plan tool calls. Returns `(calls, cost_usd)` — the planner is a paid call too (Defect 19)."""
    chat = chat or _chat
    user = (f"Question: {question}\n"
            + (f"Knowledge cutoff: only documents published on or before {as_of} may be used.\n" if as_of else "")
            + "Plan tool calls as a JSON array.")
    try:
        text, _usage, cost = chat(model, [{"role": "system", "content": PLANNER_SYSTEM},
                                          {"role": "user", "content": user}], 300)
    except Exception:  # noqa: BLE001 - planner is optional
        return [], 0.0
    spent = round(float(cost or 0.0), 6)
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return [], spent
    try:
        raw = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return [], spent
    calls = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool") or "").strip()
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        if name not in T.TOOL_NAMES:
            continue
        if as_of and name in ("search", "graph", "ppr", "gaps"):
            if name == "search":
                fl = dict(args.get("filters") or {})
                fl.setdefault("published_to", as_of)
                args["filters"] = fl
            else:
                w = list(args.get("window") or [None, None])[:2]
                w = [w[0], as_of]
                args["window"] = w
        calls.append({"tool": name, "args": args})
        if len(calls) >= 2:
            break
    return calls, spent


def _run_calls(calls: list[dict], con) -> list[dict]:
    out = []
    for c in calls:
        try:
            res = T.dispatch(c["tool"], c["args"], con=con)
            out.append({"tool": c["tool"], "args": c["args"], "result": res})
        except Exception as exc:  # noqa: BLE001
            out.append({"tool": c["tool"], "args": c["args"], "error": f"{type(exc).__name__}: {exc}"})
    return out


def _trim_results(results: list[dict], budget: int = 14000) -> list[dict]:
    """Keep tool results inside the composer's context budget (drop tail of long lists)."""
    out = []
    spent = 0
    for r in results:
        txt = json.dumps(r.get("result"), ensure_ascii=False, default=str)
        if spent + len(txt) > budget:
            if isinstance(r.get("result"), dict):
                r = dict(r)
                for key in ("results", "rows", "nodes", "edges", "gaps"):
                    if isinstance(r["result"].get(key), list):
                        r["result"] = dict(r["result"])
                        r["result"][key] = r["result"][key][:5]
            txt = json.dumps(r.get("result"), ensure_ascii=False, default=str)
            if spent + len(txt) > budget:
                continue
        spent += len(txt)
        out.append(r)
    return out


def compose(question: str, results: list[dict], as_of: str | None, model: str,
            chat=None, hint: str | None = None) -> tuple[str, dict, float]:
    chat = chat or _chat
    payload = json.dumps(_trim_results(results), ensure_ascii=False, default=str)
    user = (f"Question: {question}\n"
            + (f"Only documents published on or before {as_of} may be used.\n" if as_of else "")
            + (f"{hint}\n" if hint else "")
            + f"Tool results:\n{payload}\n\n{ANSWER_FMT}")
    max_tok = 800 if model == ESCALATION_MODEL else 500
    text, usage, cost = chat(model, [{"role": "system", "content": COMPOSER_SYSTEM},
                                     {"role": "user", "content": user}], max_tok)
    return text, usage or {}, float(cost or 0.0)


def _resolver(con, cache: dict):
    def resolve(handle: str):
        if handle in cache:
            return cache[handle]
        try:
            cache[handle] = T.cite(handle, con=con)
            return cache[handle]
        except Exception:  # noqa: BLE001
            cache[handle] = None
            return None

    return resolve


def answer_question(question: str, model: str = DEFAULT_MODEL, escalate: bool = True,
                    con=None, chat=None, db=None) -> dict:
    """Full P7 pipeline for one question. Returns the answer record (never raises on model errors)."""
    chat = chat or _chat
    t0 = time.time()
    own = con is None
    con = con or T.connect(db or T.KB_DB)
    as_of = as_of_of(question)
    calls = default_calls(question, as_of)
    spent = 0.0  # Defect 19: every paid call in this pipeline must reach the record's cost
    try:
        planned, plan_cost = plan_calls_cost(question, as_of, model, chat=chat)
        calls += planned
        spent += plan_cost
    except Exception:  # noqa: BLE001 - planning is optional
        pass
    calls = calls[:MAX_TOOL_CALLS]
    results = _run_calls(calls, con)
    have = result_numbers(results)
    resolve = _resolver(con, {})
    record = {"question": question, "as_of": as_of, "model": model, "escalated": False,
              "tool_calls": [{"tool": c.get("tool"), "args": c.get("args"), "error": c.get("error")}
                             for c in results]}
    text, usage = "", {}
    try:
        text, usage, cost = compose(question, results, as_of, model, chat=chat)
        spent += float(cost or 0.0)
    except Exception as exc:  # noqa: BLE001
        record.update(status="model_error", answer=NOT_IN_DATA, error=f"{type(exc).__name__}: {exc}",
                      elapsed_s=round(time.time() - t0, 2), cost_usd=round(spent, 6))
        return record
    parsed = parse_answer(text)
    final, dropped = contract_filter(parsed, have, resolve)
    record["checks"] = {"dropped": dropped, "first_pass_status": final["status"]}

    if final["status"] != "ok" and escalate and model != ESCALATION_MODEL:
        hint = ("Your previous attempt failed the answer contract"
                + (f" (numbers not present in results: {dropped and 'see tool results'})" if dropped else "")
                + ". Copy numbers verbatim from the tool results and cite every sentence.")
        try:
            text2, usage2, cost2 = compose(question, results, as_of, ESCALATION_MODEL, chat=chat, hint=hint)
            spent += float(cost2 or 0.0)
            parsed2 = parse_answer(text2)
            final2, dropped2 = contract_filter(parsed2, have, resolve)
            record["escalated"] = True
            record["escalation_checks"] = {"dropped": dropped2, "status": final2["status"]}
            if final2["status"] == "ok":
                final, dropped, text, usage = final2, dropped2, text2, usage2
                record["model"] = ESCALATION_MODEL
            else:
                record["cost_usd"] = round(spent, 6)
                record.update(status="not_in_data", answer=NOT_IN_DATA,
                              sentences=[], cites=[],
                              elapsed_s=round(time.time() - t0, 2))
                return record
        except Exception as exc:  # noqa: BLE001
            record["escalation_error"] = f"{type(exc).__name__}: {exc}"

    if final["status"] == "ok" and len(final["answer"]) > MAX_ANSWER_CHARS:
        final["answer"] = final["answer"][:MAX_ANSWER_CHARS].rsplit(" ", 1)[0]
    record.update(status=final["status"], answer=final["answer"],
                  sentences=final.get("sentences", []),
                  cites=[h for s in final.get("sentences", []) for h in s["cites"]],
                  raw_reply=text[:2000], usage=usage,
                  cost_usd=round(spent, 6),
                  elapsed_s=round(time.time() - t0, 2))
    if own:
        con.close()
    return record


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kb.ask", description="Ask a shipping question.")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-escalate", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)
    q = " ".join(args.question).strip()
    rec = answer_question(q, model=args.model, escalate=not args.no_escalate, db=args.db)
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
    else:
        print(rec["answer"])
        if rec.get("sentences"):
            for s in rec["sentences"]:
                handles = ", ".join(c if isinstance(c, str) else c.get("id", "") for c in s["cites"])
                print(f"  - {s['sentence']}")
                print(f"    sources: {handles}")
        print(f"[status={rec['status']} model={rec.get('model')} "
              f"escalated={rec.get('escalated')} cost=${rec.get('cost_usd', 0)} "
              f"elapsed={rec.get('elapsed_s')}s]")
    return 0 if rec["status"] in ("ok", "not_in_data") else 1


if __name__ == "__main__":
    raise SystemExit(main())
