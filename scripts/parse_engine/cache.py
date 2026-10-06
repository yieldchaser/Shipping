"""On-disk cache of external parse results: .parse_cache/<sha256>/<engine>_<tier>_<version>_<pages>.json"""
from __future__ import annotations

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


def cache_path(sha256: str, engine: str, tier: str, version: str, pages: str, root: Path | None = None) -> Path:
    name = f"{_slug(engine)}_{_slug(tier)}_{_slug(version)}_{_slug(pages.replace(',', '+'))}.json"
    return (root or cache_root()) / sha256 / name


def cache_get(sha256: str, engine: str, tier: str, version: str, pages: str, root: Path | None = None) -> dict[str, Any] | None:
    p = cache_path(sha256, engine, tier, version, pages, root)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def cache_put(sha256: str, engine: str, tier: str, version: str, pages: str, payload: dict[str, Any], root: Path | None = None) -> Path:
    p = cache_path(sha256, engine, tier, version, pages, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return p
