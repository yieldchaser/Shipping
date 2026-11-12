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


NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
# NIM model ids are full org/model ids (contain "/"); they are NOT prefixed with
# cyberouter/. Router ids have no "/" and take the cyberouter/ prefix.
NIM_MODEL_GLOBS = ("nvidia/", "mistralai/", "stepfun-ai/", "z-ai/", "deepseek-ai/")

CONFIG = Path(__file__).resolve().parent / "config.yaml"
_PROVIDER_CACHE: dict[str, dict] | None = None


def _provider_spec(model: str) -> dict | None:
    """The kb/config.yaml provider block that owns `model`, if any (base_url / kind / key name)."""
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is None:
        _PROVIDER_CACHE = {}
        try:
            if yaml is not None and CONFIG.exists():
                cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
                for prov in cfg.get("providers") or []:
                    for spec in prov.get("models") or []:
                        _PROVIDER_CACHE[spec["id"]] = {"id": prov.get("id"), "kind": prov.get("kind"),
                                                       "base_url": prov.get("base_url")}
        except Exception:
            _PROVIDER_CACHE = {}
    return _PROVIDER_CACHE.get(model)


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


def _ref(name: str) -> str:
    return (_read_credentials().get("refs") or {}).get(name) or ""


def is_nim_model(model: str) -> bool:
    """True if `model` is a full NIM org/model id (routed to NVIDIA, never prefixed)."""
    return "/" in model or model.startswith(NIM_MODEL_GLOBS)


def load_key(provider: str = "router", model: str = "") -> str:
    """Return the key for `provider` without exposing it in logs.

    provider 'nim' -> env NVIDIA_API_KEY, else refs.NVIDIA_API_KEY.
    provider 'ultrafast' -> env ULTRAFAST_API_KEY, else refs.ULTRAFAST_API_KEY.
    provider 'router' -> env ROUTER_API_KEY -> refs.ENCLAVE_API_KEY -> refs.ULTRAFAST_API_KEY.
    If provider is inferred ('auto'), a NIM model id selects the NIM key and a model owned by
    another configured provider (e.g. the free Ultrafast tier) selects that provider's key."""
    spec = _provider_spec(model)
    if provider == "auto" and spec:
        provider = spec.get("id") or provider
    if provider == "nim" or (provider == "auto" and is_nim_model(model)):
        if os.environ.get("NVIDIA_API_KEY"):
            return os.environ["NVIDIA_API_KEY"]
        k = _ref("NVIDIA_API_KEY")
        if k:
            return k
        raise NoKeyError("no NVIDIA key: set NVIDIA_API_KEY or refs.NVIDIA_API_KEY in ~/.dsh/.credentials.yaml")
    if provider == "ultrafast":
        if os.environ.get("ULTRAFAST_API_KEY"):
            return os.environ["ULTRAFAST_API_KEY"]
        k = _ref("ULTRAFAST_API_KEY")
        if k:
            return k
        raise NoKeyError("no Ultrafast key: set ULTRAFAST_API_KEY or refs.ULTRAFAST_API_KEY")
    if os.environ.get("ROUTER_API_KEY"):
        return os.environ["ROUTER_API_KEY"]
    for name in ("ENCLAVE_API_KEY", "ULTRAFAST_API_KEY"):
        k = _ref(name)
        if k:
            return k
    raise NoKeyError("no router key: set ROUTER_API_KEY or refs.*_API_KEY in ~/.dsh/.credentials.yaml")


def base_url(model: str = "") -> str:
    if is_nim_model(model):
        return os.environ.get("NVIDIA_BASE_URL") or NIM_BASE_URL
    spec = _provider_spec(model)
    if spec and spec.get("base_url") and spec.get("id") != "enclave":
        return spec["base_url"]
    return os.environ.get("ROUTER_BASE_URL") or DEFAULT_BASE_URL


def _model_id(model: str) -> str:
    if is_nim_model(model):
        return model  # full org/model id, no prefix
    spec = _provider_spec(model)
    if spec and spec.get("id") not in (None, "enclave"):
        return model  # provider-local id served unprefixed (e.g. Ultrafast)
    return model if model.startswith(MODEL_PREFIX) else f"{MODEL_PREFIX}{model}"


def chat(model: str, messages: list[dict], max_tokens: int = 16, temperature: float = 0.0,
         timeout_s: int = 120, provider: str = "auto", extra_body: dict | None = None) -> dict:
    """One non-streaming chat completion. Returns the whole JSON body (never the key).

    provider 'nim' routes to NVIDIA (OpenAI-compatible); 'router' to Enclave;
    'auto' (default) infers from the model id. extra_body merges arbitrary OpenAI
    fields (e.g. chat_template_kwargs for Nemotron)."""
    key = load_key(provider, model)
    body = {
        "model": _model_id(model),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra_body:
        body.update(extra_body)
    req = urllib.request.Request(
        f"{base_url(model)}/chat/completions",
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


def nim_smoke(model: str, max_tokens: int = 16, timeout_s: int = 180,
              extra_body: dict | None = None) -> dict:
    """One NIM completion (never charges; $0). Returns {status, model_returned, usage, error}."""
    out = {"status": "ok", "model_returned": None, "usage": None, "error": None}
    try:
        data = chat(
            model,
            [{"role": "user", "content": "Reply with exactly one word: READY"}],
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            provider="nim",
            extra_body=extra_body,
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
    except Exception as e:
        out.update(status="error", error=f"{type(e).__name__}: {e}")
        return out


if __name__ == "__main__":
    import pprint

    result = smoke_test()
    # The model text is not the key; this is safe. The key never appears anywhere.
    pprint.pprint(result)
    ok = result["status"] == "ok"
    sys.exit(0 if ok else 1)
