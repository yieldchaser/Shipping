"""Paths, profile loading and page-selection rules."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = Path(__file__).resolve().parent / "profiles"
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")

CREDITS_PER_PAGE = {"fast": 1, "cost_effective": 3, "agentic": 10, "agentic_plus": 45}


def corpus_root() -> Path:
    env = os.environ.get("CORPUS_ROOT")
    if env:
        return Path(env)
    if (MAIN_CHECKOUT / "corpus").exists():
        return MAIN_CHECKOUT
    return REPO_ROOT


def resolve_pdf(path: str | Path) -> Path:
    """Absolute paths pass through; repo-relative `corpus/...` resolve against CORPUS_ROOT."""
    p = Path(path)
    if p.is_absolute():
        return p
    for base in (corpus_root(), REPO_ROOT, Path.cwd()):
        if (base / p).exists():
            return base / p
    return corpus_root() / p


def repo_relative(path: Path) -> str:
    """Repo-relative corpus path (posix) when the file lives under a known root."""
    for base in (corpus_root(), REPO_ROOT, MAIN_CHECKOUT):
        try:
            return path.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_profile(source: str) -> dict[str, Any]:
    path = PROFILE_DIR / f"{source}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No profile for source '{source}': {path}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _rule_for_year(rule: Any, year: int | None) -> dict[str, int]:
    """A rule is a dict (`drop_last`/`drop_first`) or a list of conditional dicts
    (`until_year` inclusive / `from_year` inclusive); first match wins."""
    if rule is None:
        return {}
    if isinstance(rule, dict):
        rules = [rule]
    else:
        rules = list(rule)
    for r in rules:
        if "until_year" in r and (year is None or year > r["until_year"]):
            continue
        if "from_year" in r and (year is None or year < r["from_year"]):
            continue
        return {k: int(v) for k, v in r.items() if k in ("drop_first", "drop_last", "keep_first")}
    return {}


def select_pages(total: int, rule: Any, year: int | None = None) -> list[int]:
    """Return 1-based page numbers to parse. Never returns an empty list for total >= 1."""
    r = _rule_for_year(rule, year)
    first = 1 + r.get("drop_first", 0)
    last = total - r.get("drop_last", 0)
    if r.get("keep_first"):                       # "first N pages are useful", whatever the page count
        last = min(last, first - 1 + int(r["keep_first"]))
    pages = list(range(first, last + 1))
    return pages or list(range(1, total + 1))


def pages_to_spec(pages: list[int]) -> str:
    """[1,2,3,5] -> '1-3,5' (1-based)."""
    if not pages:
        return ""
    out, start, prev = [], pages[0], pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
            continue
        out.append(f"{start}-{prev}" if prev > start else str(start))
        start = prev = p
    out.append(f"{start}-{prev}" if prev > start else str(start))
    return ",".join(out)


def spec_to_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    return pages
