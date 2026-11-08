"""Provider-agnostic LLM runner for the GraphRAG pipeline (plan §7.5, §10.3).

Step-0 scope: key loading + a one-shot chat helper + a smoke test. The full
asyncio runner (ledger, budget guard, drift guard, concurrency ramp) is added in
P-1/P4a on top of these two pieces; nothing here makes a paid call except the
explicit `smoke_test`.

Key rules (never break):
  - The key is never printed, logged, copied to another file or committed.
  - ROUTER_API_KEY from the environment wins; else refs.ENCLAVE_API_KEY (then
    refs.ULTRAFAST_API_KEY) from ~/.dsh/.credentials.yaml.
  - ROUTER_BASE_URL defaults to https://router.enclave.ai/v1.
  - Router model ids carry the "cyberouter/" prefix.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is available in the harness
    yaml = None

DEFAULT_BASE_URL = "https://router.enclave.ai/v1"
MODEL_PREFIX = "cyberouter/"


class NoKeyError(RuntimeError):
    """Raised when no router key can be found (a §6 stop condition)."""


def _read_credentials() -> dict:
    """Read ~/.dsh/.credentials.yaml. Never returns a key to the caller directly;
    returns the whole structure so the caller picks the ref name. Keys stay in-process."""
    f = Path.home() / ".dsh" / ".credentials.yaml"
    if not f.exists():
        return {}
    try:
        if yaml is None:
            return {}
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_key() -> str:
    """Return a router key without exposing it in logs. Order:
    env ROUTER_API_KEY -> refs.ENCLAVE_API_KEY -> refs.ULTRAFAST_API_KEY."""
    if os.environ.get("ROUTER_API_KEY"):
        return os.environ["ROUTER_API_KEY"]
    refs = _read_credentials().get("refs") or {}
    for name in ("ENCLAVE_API_KEY", "ULTRAFAST_API_KEY"):
        k = refs.get(name)
        if k:
            return k
    raise NoKeyError("no router key: set ROUTER_API_KEY or refs.*_API_KEY in ~/.dsh/.credentials.yaml")


def base_url() -> str:
    return os.environ.get("ROUTER_BASE_URL") or DEFAULT_BASE_URL


def _model_id(model: str) -> str:
    return model if model.startswith(MODEL_PREFIX) else f"{MODEL_PREFIX}{model}"


def chat(model: str, messages: list[dict], max_tokens: int = 16, temperature: float = 0.0,
         timeout_s: int = 120) -> dict:
    """One non-streaming chat completion. Returns the whole JSON body (never the key)."""
    key = load_key()
    body = {
        "model": _model_id(model),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        f"{base_url()}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def smoke_test(model: str = "deepseek-v4-flash", max_tokens: int = 5) -> dict:
    """One 5-token request (plan §7 step 0). Returns {status, model_returned, usage, error}."""
    out = {"status": "ok", "model_returned": None, "usage": None, "error": None}
    try:
        data = chat(
            model,
            [{"role": "user", "content": "Reply with exactly one word: READY"}],
            max_tokens=max_tokens,
        )
        out["model_returned"] = data.get("model")
        out["usage"] = data.get("usage")
        return out
    except NoKeyError as e:
        out.update(status="no_key", error=str(e))
        return out
    except urllib.error.HTTPError as e:
        out.update(status="http_error", error=f"{e.code} {e.reason}")
        return out
    except Exception as e:  # transient network / timeout / decode
        out.update(status="error", error=f"{type(e).__name__}: {e}")
        return out


if __name__ == "__main__":
    import pprint

    result = smoke_test()
    # The model text is not the key; this is safe. The key never appears anywhere.
    pprint.pprint(result)
    ok = result["status"] == "ok"
    sys.exit(0 if ok else 1)
