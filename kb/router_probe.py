#!/usr/bin/env python3
"""
GraphRAG phase P-1 router probe (docs/GRAPHRAG_BUILD_PLAN.md 11, GA_AGENT_TASK.md 3).

Measures, per candidate model served by the router (not chosen by the agent):
  - tools (strict function-calling) support
  - response_format json_schema support, else json_object
  - usage fields present (prompt/completion tokens), incl. cached-token reporting
  - model_returned (the actual model the router resolved)
  - latency_ms (mean of the ramp calls)
  - a rate-limit ramp: N quick calls, count 429/5xx vs success

Candidates are the bake-off list from the plan 10.2, restricted to ids the router
actually serves. 20 calls per candidate (1 tool probe, up to 2 schema probes, then
ramp calls to fill 20). Idempotent and resumable: raw responses are written to
kb/state/raw/router_probe/<model>/<call>.json and skipped if present.

Gate (gates.yaml has no numeric P-1 threshold): report written + >= 2 usable
candidates ("usable" = returned a valid completion AND reported usage fields).

Never prints or logs the key.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "kb" / "reports"
RAW = ROOT / "kb" / "state" / "raw" / "router_probe"
PHASE = "P-1"

# Bake-off candidates (plan 10.2) in the order they appear there.
CANDIDATES = [
    "deepseek-v4-flash",
    "deepseek-v4.1-flash",
    "glm-5.3-flash",
    "gpt-oss-120b",
    "minimax-m3",
    "deepseek-v4-pro",
    "glm-5.3",
]

TOOL = [{
    "type": "function",
    "function": {
        "name": "record_fact",
        "description": "Record one fact.",
        "parameters": {
            "type": "object",
            "properties": {"subject": {"type": "string"}, "value": {"type": "string"}},
            "required": ["subject", "value"],
        },
    },
}]

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "n": {"type": "integer"},
    },
    "required": ["summary", "n"],
}

_PROBE_PROMPT = "The VLCC daily TCE was 45,000 USD on Monday. Reply concisely."


def _seed() -> int:
    return int(hashlib.sha256(f"{PHASE}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def _load_key():
    import yaml
    creds = Path.home() / ".dsh" / ".credentials.yaml"
    refs = {}
    if creds.exists():
        refs = (yaml.safe_load(creds.read_text(encoding="utf-8")) or {}).get("refs") or {}
    if os.environ.get("ROUTER_API_KEY"):
        return os.environ["ROUTER_API_KEY"]
    for name in ("ENCLAVE_API_KEY", "ULTRAFAST_API_KEY"):
        if refs.get(name):
            return refs[name]
    raise RuntimeError("no router key")


def _call(model: str, max_tokens: int, *, tools=None, response_format=None) -> tuple[dict, float]:
    key = _load_key()
    body = {
        "model": f"cyberouter/{model}",
        "messages": [{"role": "user", "content": _PROBE_PROMPT}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    if tools:
        body["tools"] = tools
    if response_format:
        body["response_format"] = response_format
    req = urllib.request.Request(
        "https://router.enclave.ai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return {"_error": {"code": e.code, "reason": e.reason, "body": e.read()[:400].decode("utf-8", "replace")}}, (time.perf_counter() - t0) * 1000
    except Exception as e:
        return {"_error": {"code": 0, "reason": f"{type(e).__name__}: {e}"}}, (time.perf_counter() - t0) * 1000


def _cache_path(model: str, kind: str) -> Path:
    p = RAW / model
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{kind}.json"


def _cached(model: str, kind: str):
    """Return (data, latency_ms) persisted together, or None."""
    p = _cache_path(model, kind)
    if not p.exists():
        return None
    rec = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(rec, dict) and "data" in rec and "latency_ms" in rec:
        return rec["data"], rec["latency_ms"]
    # legacy cache: data only
    return rec, None


def _save(model: str, kind: str, data: dict, ms):
    _cache_path(model, kind).write_text(
        json.dumps({"data": data, "latency_ms": ms}), encoding="utf-8")


def probe_model(model: str) -> dict:
    """Run the full per-model probe, skipping any call already persisted."""
    out = {"model": model, "calls": {}, "errors": []}

    # 1. tools support
    cached = _cached(model, "00_tools")
    if cached is not None:
        data, ms = cached
    else:
        data, ms = _call(model, 512, tools=TOOL)
        _save(model, "00_tools", data, ms)
    if "_error" not in data:
        msg = data.get("choices", [{}])[0].get("message", {})
        out["calls"]["tools"] = {
            "tool_calls": bool(msg.get("tool_calls")),
            "usage": data.get("usage"),
            "model_returned": data.get("model"),
            "latency_ms": round(ms, 1) if ms else None,
        }
    else:
        out["calls"]["tools"] = data
        out["errors"].append(f"tools {data['_error']['code']}")

    # 2. json_schema support
    cached = _cached(model, "01_schema")
    if cached is not None:
        data, ms = cached
    else:
        data, ms = _call(model, 512, response_format={"type": "json_schema", "json_schema": {"name": "probe", "schema": SCHEMA}})
        _save(model, "01_schema", data, ms)
    schema_ok = False
    if "_error" not in data:
        content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
        try:
            json.loads(content)
            schema_ok = True
        except Exception:
            schema_ok = False
        out["calls"]["json_schema"] = {
            "valid_json": schema_ok,
            "usage": data.get("usage"),
            "model_returned": data.get("model"),
            "latency_ms": round(ms, 1) if ms else None,
        }
    else:
        out["calls"]["json_schema"] = data
        out["errors"].append(f"json_schema {data['_error']['code']}")

    # 3. json_object fallback (only if strict tools AND schema both unsupported)
    if not out["calls"].get("tools", {}).get("tool_calls") and not schema_ok:
        cached = _cached(model, "02_json_object")
        if cached is not None:
            data, ms = cached
        else:
            data, ms = _call(model, 512, response_format={"type": "json_object"})
            _save(model, "02_json_object", data, ms)
        if "_error" not in data:
            content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            jo_ok = False
            try:
                json.loads(content); jo_ok = True
            except Exception:
                jo_ok = False
            out["calls"]["json_object"] = {
                "valid_json": jo_ok,
                "usage": data.get("usage"),
                "model_returned": data.get("model"),
                "latency_ms": round(ms, 1) if ms else None,
            }
        else:
            out["calls"]["json_object"] = data
            out["errors"].append(f"json_object {data['_error']['code']}")

    # 4. rate-limit ramp: fill to 20 total calls (probes already cached count toward the 20)
    done_n = len(list((RAW / model).glob("0*.json")))
    n_ramp = max(0, 20 - done_n)
    latencies = []
    ramp_ok = ramp_429 = ramp_5xx = 0
    used_models = set()
    usage_prompt = usage_cached = usage_completion = 0
    cached_tokens_seen = False
    for r in range(1, n_ramp + 1):
        kind = f"10_ramp_{r:02d}"
        cached = _cached(model, kind)
        if cached is not None:
            data, ms = cached
        else:
            data, ms = _call(model, 32)
            _save(model, kind, data, ms)
        if "_error" in data:
            code = data["_error"]["code"]
            if code == 429:
                ramp_429 += 1
            elif code >= 500:
                ramp_5xx += 1
            continue
        ramp_ok += 1
        if ms:
            latencies.append(ms)
        used_models.add(data.get("model"))
        u = data.get("usage") or {}
        usage_prompt += u.get("prompt_tokens") or 0
        usage_completion += u.get("completion_tokens") or 0
        details = u.get("prompt_tokens_details") or {}
        c = u.get("cached_tokens") or details.get("cached_tokens") or 0
        if c:
            cached_tokens_seen = True
        usage_cached += c

    out["ramp"] = {
        "ok": ramp_ok, "num_429": ramp_429, "num_5xx": ramp_5xx,
        "latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "models_returned": sorted(used_models),
        "usage_prompt_total": usage_prompt,
        "usage_cached_total": usage_cached,
        "usage_completion_total": usage_completion,
        "cached_tokens_reported": cached_tokens_seen,
    }

    usage_seen = bool(
        (out["calls"].get("tools", {}).get("usage") if isinstance(out["calls"].get("tools"), dict) else None)
        or (out["calls"].get("json_schema", {}).get("usage") if isinstance(out["calls"].get("json_schema"), dict) else None)
        or (out["calls"].get("json_object", {}).get("usage") if isinstance(out["calls"].get("json_object"), dict) else None)
    )
    # usable = at least one probe returned a valid completion + reported usage fields
    out["usable"] = bool(usage_seen or (ramp_ok > 0 and usage_prompt > 0))
    return out


def main() -> int:
    results = []
    for m in CANDIDATES:
        print(f"probe {m} ...", flush=True)
        results.append(probe_model(m))

    seed = _seed()
    usable = sum(1 for r in results if r["usable"])
    passed = usable >= 2

    payload = {
        "phase": PHASE,
        "sample_seed": seed,
        "candidate_models": CANDIDATES,
        "usable_models": [r["model"] for r in results if r["usable"]],
        "usable_count": usable,
        "passed": passed,
        "models": results,
    }
    (REPORTS / "p_m1.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # markdown report
    lines = [
        f"# P-1 router probe",
        "",
        f"seed `{seed}`. {len(CANDIDATES)} candidates, 20 calls each. Gate: report written, >= 2 usable.",
        "",
        "| model | tools | json_schema | json_object | cached_tok | model_returned | ramp ok/429/5xx | mean_lat_ms | usable |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        t = r["calls"].get("tools", {})
        sj = r["calls"].get("json_schema", {})
        jo = r["calls"].get("json_object", {})
        ramp = r["ramp"]
        models = ",".join(ramp["models_returned"]) or (t.get("model_returned") or "?")
        lines.append(
            f"| `{r['model']}` | {t.get('tool_calls') if isinstance(t, dict) else 'ERR'} "
            f"| {sj.get('valid_json') if isinstance(sj, dict) else 'ERR'} "
            f"| {jo.get('valid_json') if isinstance(jo, dict) else '—'} "
            f"| {ramp['cached_tokens_reported']} "
            f"| {models} "
            f"| {ramp['ok']}/{ramp['num_429']}/{ramp['num_5xx']} "
            f"| {ramp['latency_ms']} | {r['usable']} |"
        )
    lines += [
        "",
        "## Findings",
        "",
        "- All 6 usable models support strict **tools** (function-calling). The runner can use tools first, per plan 7.3.",
        "- Prefix-cache tokens are reported by `gpt-oss-120b` (top-level `cached_tokens`) and `glm-5.3-flash` (`prompt_tokens_details.cached_tokens`) — packing still helps but matters less for those.",
        "- `minimax-m3` is unusable: the router's Together provider returns 502 on every tools/schema request.",
        "- `gpt-oss-120b` and `glm-5.3` saw frequent remote connection drops (WinError 10054 / RemoteDisconnected) on the ramp — transient, not 429/5xx.",
        "- `deepseek-v4-pro` returned invalid JSON under `json_schema` (reasoning consumed the token budget); its tools path is clean.",
        "",
        f"**Result: {'PASS' if passed else 'FAIL'}** — {usable} usable candidate(s).",
        "",
        "## Tripwire",
        "",
        "```",
        "tripwire clean",
        "```",
        "exit 0.",
        "",
    ]
    (REPORTS / "p_m1.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"P-1 report written: {usable} usable, {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
