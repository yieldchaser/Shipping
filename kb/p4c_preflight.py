"""P4c transport preflight: prove today's transport for the two models P4c now needs.

Reuses the tested P4b probe (`detect_mode`: one tiny call per transport, first parseable wins), but
points the state paths at `kb/state/p4c` so the modes P4c runs with are the modes that were probed.
Owner decision (C1) as amended 2026-11-13: bulk + gleaning = free AMD Token Lab pool
(`DeepSeek-V4.1-Flash`, exact API id; `DeepSeek-V4-Flash` is the fallback id), escalation = paid
glm-5.3. The Ultrafast id is not probed: it is excluded as congested.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4b_run as B  # noqa: E402

OUT = KB.parent / "kb/state/p4c"
MODELS = ["DeepSeek-V4.1-Flash", "DeepSeek-V4-Flash", "glm-5.3"]


def main(models=None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    B.STATE = OUT
    B.MODES_FILE = OUT / "modes.json"
    print(f"preflight models: {models or MODELS}", flush=True)
    rc = B.cmd_preflight(models or MODELS)
    print((OUT / "modes.json").read_text(encoding="utf-8"), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main([m for m in sys.argv[1:] if not m.startswith("-")] or None))
