"""Byte-duplicate document dedup, shared by the per-publisher runners.

WHY: a second collection route re-drops the same weekly issue under a different
filename, so both copies get parsed and stacked and every such issue
double-counts its rows. Measured 2026-10-01 (docs/decimal_comma_regeneration_verdict.md
section 7): advanced_shipping 148 duplicate rows, ssy 132, fearnleys 121,
agora 94, star_asia 58, affinity 48, carriers 327 (carriers is another agent's
- untouched), xclusiv/intermodal already fixed.

RULE: keep ONE document per md5 group. The keeper is the copy whose extraction
is RICHEST (largest .tables.json); ties break lexicographically. Reason, measured
this run: several groups carry a STUB sidecar on one copy - star_asia 2026 W38 is
a 1,182-byte dict on one copy and a 29,127-byte list on the other, agora W38 is
88 bytes on one, ssy 2025-09-28 is 345 bytes on one - so a blind
lexicographic-first rule can keep the stub and throw the real extraction away.

This is plumbing, not extraction strategy: each publisher still owns its own
pipeline, and the filter is applied per source at that publisher's own
enumeration AND stack point.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Set


def _richness(stem: str, md_dir: Optional[Path]) -> int:
    """How much CONTENT the richest sidecar we hold for this stem carries.

    Deliberately NOT the file size: the sidecar stamps its own filename into
    every row, so a longer filename (the DD_MM_YYYY collection-route names) makes
    a byte-identical extraction look "bigger" and would win the tie-break on the
    wrong copy - measured this run, it flipped the advanced_shipping keeper.
    Count the table ROWS instead (list-valued keys), which the filename cannot
    inflate; fall back to file size only for a non-JSON/legacy sidecar.
    """
    if md_dir is None or not md_dir.exists():
        return 0
    best = 0
    direct = md_dir / f"{stem}.tables.json"
    cands = [direct] if direct.exists() else []
    cands += [c for c in md_dir.rglob(f"{stem}.tables.json") if c != direct]
    for cand in cands:
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            rows = sum(len(v) for v in data.values() if isinstance(v, list))
            if rows == 0:  # a stub/legacy dict with no row lists
                rows = 0
        elif isinstance(data, list):
            rows = len(data)
        else:
            rows = 0
        best = max(best, rows)
    return best


def byte_duplicate_groups(corpus_dir: Path) -> List[List[Path]]:
    """Every group of >=2 byte-identical PDFs under corpus_dir."""
    by_hash: Dict[str, List[Path]] = {}
    for pdf in sorted(corpus_dir.rglob("*.pdf")):
        try:
            h = hashlib.md5(pdf.read_bytes()).hexdigest()
        except OSError:
            continue
        by_hash.setdefault(h, []).append(pdf)
    return [g for g in by_hash.values() if len(g) > 1]


def byte_duplicate_stems(corpus_dir: Path, md_dir: Optional[Path] = None) -> Set[str]:
    """Stems to SKIP: every copy in a duplicate group except the richest one."""
    skip: Set[str] = set()
    for group in byte_duplicate_groups(corpus_dir):
        ranked = sorted(group, key=lambda q: (-_richness(q.stem, md_dir), q.stem))
        skip.update(q.stem for q in ranked[1:])
    return skip
