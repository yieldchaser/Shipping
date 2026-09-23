"""
refscan.py - find every code/workflow reference to a set of paths.

Used during the corpus reorganisation (docs/data_layer_reorg_plan.md) to prove
BEFORE a move that every consumer of a path is known, and AFTER a move that no
stale reference remains.

Usage:
    python scripts/verify/refscan.py broker_reports reports/drewry
    python scripts/verify/refscan.py --stale corpus/05-seabrokers   # look for OLD paths
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_DIRS = ("scripts", ".github")
CODE_SUFFIXES = {".py", ".yml", ".yaml"}
# lines that mention a path but are metadata/catalog, not a data location
NOISE = ("ais_manifest", "_catalog.json")


def iter_code_files():
    for base in CODE_DIRS:
        root = REPO_ROOT / base
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in CODE_SUFFIXES:
                yield p


def scan(terms: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {t: [] for t in terms}
    for p in iter_code_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = p.relative_to(REPO_ROOT)
        for i, line in enumerate(text.splitlines(), 1):
            if any(n in line for n in NOISE):
                continue
            for t in terms:
                if t in line:
                    hits[t].append(f"{rel}:{i}: {line.strip()[:120]}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="+")
    ap.add_argument("--stale", action="store_true",
                    help="report which terms still appear (non-zero exit if any do)")
    args = ap.parse_args()

    hits = scan(args.terms)
    total = 0
    for t in args.terms:
        print(f"=== {t} : {len(hits[t])} refs ===")
        for h in hits[t][:10]:
            print(f"    {h}")
        if len(hits[t]) > 10:
            print(f"    ... and {len(hits[t]) - 10} more")
        total += len(hits[t])

    if args.stale:
        if total:
            print(f"STALE: {total} reference(s) to moved path(s) remain")
            return 1
        print("OK: no stale references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
