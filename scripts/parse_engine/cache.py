"""On-disk cache of external parse results: .parse_cache/<sha256>/<engine>_<tier>_<version>_<pages>.json"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.parse_engine.config import REPO_ROOT


def cache_root() -> Path:
    import os

    return Path(os.environ.get("PARSE_CACHE_DIR", REPO_ROOT / ".parse_cache"))


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.+-]+", "-", str(value)).strip("-") or "na"


def config_hash(config: dict[str, Any]) -> str:
    """Short hash of the effective request configuration (prompt, output options, tier, version...)."""
    blob = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def cache_path(sha256: str, engine: str, tier: str, version: str, pages: str, root: Path | None = None,
               cfg_hash: str = "") -> Path:
    name = f"{_slug(engine)}_{_slug(tier)}_{_slug(version)}_{_slug(pages.replace(',', '+'))}"
    if cfg_hash:
        name += f"_{_slug(cfg_hash)}"
    return (root or cache_root()) / sha256 / (name + ".json")


def cache_get(sha256: str, engine: str, tier: str, version: str, pages: str, root: Path | None = None,
              cfg_hash: str = "") -> dict[str, Any] | None:
    p = cache_path(sha256, engine, tier, version, pages, root, cfg_hash)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def cache_put(sha256: str, engine: str, tier: str, version: str, pages: str, payload: dict[str, Any],
              root: Path | None = None, cfg_hash: str = "") -> Path:
    p = cache_path(sha256, engine, tier, version, pages, root, cfg_hash)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return p
