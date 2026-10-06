"""LlamaCloud key pool with persistent per-month exhaustion state. Never logs full keys."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.parse_engine.cache import cache_root


def mask(key: str) -> str:
    return key[:7] + "..."


def key_id(key: str) -> str:
    """State id: 7-char prefix plus short digest (disambiguates, reveals nothing usable)."""
    import hashlib

    return f"{mask(key)}#{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def _env_keys() -> list[str]:
    raw = os.environ.get("LLAMA_CLOUD_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    i = 1
    while os.environ.get(f"LLAMA_CLOUD_API_KEY_{i}"):
        keys.append(os.environ[f"LLAMA_CLOUD_API_KEY_{i}"].strip())
        i += 1
    return keys


def load_keys() -> list[str]:
    keys = _env_keys()
    if not keys:
        from scripts.extract.llama_manager import KEY_POOL  # fallback only

        keys = [k["api_key"] for k in KEY_POOL]
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class KeyPool:
    def __init__(self, keys: list[str] | None = None, state_path: Path | None = None):
        self.keys = keys if keys is not None else load_keys()
        self.state_path = state_path or (cache_root() / "_llama_key_state.json")
        self.state = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"exhausted": {}}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def is_exhausted(self, key: str) -> bool:
        rec = self.state["exhausted"].get(key_id(key))
        return bool(rec) and rec.get("month") == _month()

    def mark_exhausted(self, key: str, reason: str = "402") -> None:
        self.state["exhausted"][key_id(key)] = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "month": _month(),
            "reason": reason,
        }
        self._save()

    def available(self) -> list[str]:
        return [k for k in self.keys if not self.is_exhausted(k)]

    def current(self) -> str | None:
        avail = self.available()
        return avail[0] if avail else None
