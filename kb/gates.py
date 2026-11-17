"""Read the frozen gate thresholds from `kb/gates.yaml` — single source, fail-closed.

Every gate module used to carry its own literal copy of the thresholds it enforced. That is the
Defect-40 family in its purest form: a literal in the instrument certifies nothing, because editing
the frozen file would not move the verdict, and editing the code could silently lower a gate.

Rules:
- Thresholds are READ, never hardcoded. Unreadable file / missing key ⇒ `None` ⇒ the gate fails
  closed (`p4a_report.gate_verdict` precedent).
- Boolean-valued keys (`..._reported`, `..._checked`) are booleans, not numbers; `M.as_float` rejects
  bool on purpose, so they get their own reader.
- A count key (`qa_gold_questions`, `analyst_mode_questions`, ...) must be a finite integer.
"""
from __future__ import annotations

import sys
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

import money as M  # noqa: E402

GATES = KB_DIR / "gates.yaml"


def _block(phase: str) -> dict:
    """The raw mapping for one phase, or `{}` when the frozen file cannot be read."""
    try:
        import yaml
        data = yaml.safe_load(GATES.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, ImportError, AttributeError):
        return {}
    got = data.get(phase) if isinstance(data, dict) else None
    return got if isinstance(got, dict) else {}


def threshold(phase: str, key: str) -> float | None:
    """Frozen numeric threshold, or `None` (gate fails closed)."""
    return M.as_float(_block(phase).get(key))


def count_threshold(phase: str, key: str) -> int | None:
    """Frozen count threshold: a finite integer, else `None`.

    Same idiom as the scanner's `_count`: a float that is not integral is a broken read, not 30.
    """
    f = M.as_float(_block(phase).get(key))
    if f is None or not f.is_integer():
        return None
    return int(f)


def flag_threshold(phase: str, key: str) -> bool | None:
    """Frozen boolean requirement (`analyst_backtest_hit_rate_reported`, ...), else `None`."""
    v = _block(phase).get(key)
    return v if isinstance(v, bool) else None
