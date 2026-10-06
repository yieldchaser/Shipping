"""LiteParse (`lit` CLI) wrapper with on-disk caching. Free, but cached for reproducible runs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from scripts.parse_engine.cache import cache_get, cache_put


def lit_version() -> str:
    exe = shutil.which("lit")
    if not exe:
        raise RuntimeError("`lit` CLI (LiteParse) not found on PATH")
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8")
    return (out.stdout or out.stderr).strip().split()[-1]


def _run(args: list[str]) -> str:
    exe = shutil.which("lit")
    if not exe:
        raise RuntimeError("`lit` CLI (LiteParse) not found on PATH")
    proc = subprocess.run([exe, "parse", *args, "-q"], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"lit parse failed ({proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout


def parse_page(pdf: Path, sha256: str, page: int, fmt: str = "markdown", use_cache: bool = True) -> dict[str, Any]:
    """Parse a single 1-based page. fmt is 'markdown' or 'json'. Returns the cached payload."""
    version = lit_version()
    spec = str(page)
    engine = f"liteparse-{fmt}"
    if use_cache:
        hit = cache_get(sha256, engine, "free", version, spec)
        if hit is not None:
            hit["cache_hit"] = True
            return hit
    out = _run([str(pdf), "--format", fmt, "--target-pages", spec])
    payload: dict[str, Any] = {"api": "cli", "engine": engine, "tier": "free", "version_resolved": version,
                               "pages": spec, "format": fmt}
    if fmt == "json":
        payload["json"] = json.loads(out)
    else:
        payload["markdown"] = out
    cache_put(sha256, engine, "free", version, spec, payload)
    payload["cache_hit"] = False
    return payload
