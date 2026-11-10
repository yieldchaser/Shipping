#!/usr/bin/env python3
"""
kb/backup_state.py [phase]  (docs/GRAPHRAG_BUILD_PLAN.md §10.4)

Copies the money-costing state — ledger.sqlite, raw/ responses and kb.duckdb — to
C:/Users/Dell/kb_backup/<phase>/, keeping the last 3 backups of each. Everything else
can be rebuilt from these and the corpus without new LLM calls.

Usage: python kb/backup_state.py P1   (phase defaults to the current git branch)
"""
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "kb" / "state"
BACKUP_ROOT = Path("C:/Users/Dell/kb_backup")

KEEP = 3


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else None
    if not phase:
        phase = Path(ROOT / ".git").exists() and _branch() or "unknown"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_ROOT / phase / stamp
    dest.mkdir(parents=True, exist_ok=True)

    for src in (STATE / "ledger.sqlite", STATE / "kb.duckdb"):
        if src.exists():
            shutil.copy2(src, dest / src.name)
    raw = STATE / "raw"
    if raw.exists():
        shutil.copytree(raw, dest / "raw")

    # prune to last KEEP per phase
    pd = dest.parent
    if pd.exists():
        snapshots = sorted(p for p in pd.iterdir() if p.is_dir())
        for old in snapshots[:-KEEP]:
            shutil.rmtree(old, ignore_errors=True)

    print(f"backup_state: phase={phase} -> {dest}")
    for f in sorted(dest.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(dest)} {f.stat().st_size:,}B")
    return 0


def _branch() -> str:
    import subprocess

    return subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT,
        capture_output=True, text=True,
    ).stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
