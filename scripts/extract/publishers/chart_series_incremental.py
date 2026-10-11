"""Shared helpers for the NEW-ONLY mode of the free vector chart engines.

The chart engines (ssy, intermodal, xclusiv, ism) were written as full rebuilds: read every
report, stack, overwrite the series CSV. In CI only the newly downloaded reports are on
disk, so a full rebuild there would destroy history. New-only mode instead:

  1. selects only the reports newer than the series already on disk,
  2. builds rows for them with the engine's own extractor,
  3. UPSERTS them into the existing CSV by the engine's natural key.

Upsert policy: a key that already exists is KEPT untouched (history is never rewritten,
including the aggregate n_reports / median of earlier stacking); a key that does not exist
is appended. Re-running with the same reports is therefore a no-op.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

Row = Dict[str, str]


def corpus_base(repo: Path) -> Path:
    """Root that holds corpus/ : $CORPUS_ROOT when set (worktrees), else the repo."""
    env = os.environ.get("CORPUS_ROOT")
    return Path(env) if env else repo


def read_rows(path: Path) -> Tuple[List[str], List[Row]]:
    """(fieldnames, rows) of an existing series CSV, or ([], []) when absent."""
    path = Path(path)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        return list(rd.fieldnames or []), list(rd)


def write_rows(path: Path, fields: Sequence[str], rows: Iterable[Row]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in fields})


def _text(r: Row, fields: Sequence[str]) -> Row:
    return {c: "" if r.get(c) is None else str(r.get(c)) for c in fields}


def upsert_new_keys(
    existing: List[Row],
    produced: List[Row],
    key_fn: Callable[[Row], tuple],
    fields: Sequence[str],
    sort_key: Optional[Callable[[Row], tuple]] = None,
) -> Tuple[List[Row], int, int]:
    """Merge `produced` into `existing`: keep every existing row, append unseen keys.

    Returns (merged_rows, n_added, n_kept_existing_for_produced_keys).
    `sort_key` re-sorts the merged rows when the engine's full rebuild sorts its output;
    leave it None to append in arrival order.
    """
    seen = {key_fn(r) for r in existing}
    merged = list(existing)
    added = kept = 0
    for r in produced:
        r = _text(r, fields)
        k = key_fn(r)
        if k in seen:
            kept += 1
            continue
        seen.add(k)
        merged.append(r)
        added += 1
    if sort_key is not None:
        merged.sort(key=sort_key)
    return merged, added, kept


def compare_overlap(
    existing: List[Row],
    produced: List[Row],
    key_fn: Callable[[Row], tuple],
    value_cols: Sequence[str],
    tol: float = 0.0,
) -> Dict[str, object]:
    """Compare produced rows to existing rows on overlapping keys.

    A value matches when |produced - existing| <= tol. Returns counts plus the list of
    differences, so a dry run can state zero-diff or show exactly what moved.
    """
    by_key = {key_fn(r): r for r in existing}
    overlap = 0
    diffs = []
    for p in produced:
        k = key_fn(p)
        e = by_key.get(k)
        if e is None:
            continue
        overlap += 1
        for c in value_cols:
            try:
                pv, ev = float(p[c]), float(e[c])
            except (TypeError, ValueError, KeyError):
                if str(p.get(c)) != str(e.get(c)):
                    diffs.append((k, c, p.get(c), e.get(c)))
                continue
            if abs(pv - ev) > tol:
                diffs.append((k, c, pv, ev))
    new_only = sum(1 for p in produced if key_fn(p) not in by_key)
    return {"produced": len(produced), "overlap": overlap, "new_keys": new_only,
            "diffs": diffs}
