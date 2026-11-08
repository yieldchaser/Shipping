"""Tripwire: checks the build agent has not weakened the rules. Run before every phase gate.

Exit code 0 = clean; 1 = violation (the agent must stop and write kb/reports/BLOCKED.md).

Checks:
  1. The frozen files are identical to origin/main:
     kb/gates.yaml, kb/tripwire.py, docs/GRAPHRAG_AGENT_TASK.md, docs/GRAPHRAG_BUILD_PLAN.md
  2. Protected input paths are unchanged against origin/main (corpus/, data/, scripts/, existing workflows).
  3. Checkpoint approval files exist only if the owner wrote them in chat (the agent records the
     owner's words; the file must carry the line 'owner_message:').
  4. The frozen P0.5 scope file, once written, has not shrunk.
  5. Every gate JSON in kb/reports/ reports a 'sample_seed' that matches the seed rule (no hand-picked samples).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ["kb/gates.yaml", "kb/tripwire.py", "docs/GRAPHRAG_AGENT_TASK.md", "docs/GRAPHRAG_BUILD_PLAN.md"]
PROTECTED = ["corpus", "data", "scripts", ".github/workflows"]
ALLOWED_NEW_WORKFLOWS = ("kb_",)
# Local run-state/log files that ingest scripts rewrite on every run; uncommitted changes to them are not edits.
LOCAL_STATE_NAMES = ("_run_state.json",)
LOCAL_STATE_SUFFIXES = (".log",)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def seed_for(phase):
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def main():
    bad = []
    git("fetch", "-q", "origin", "main")
    for f in FROZEN:
        if git("diff", "--name-only", "origin/main", "--", f).strip():
            bad.append(f"frozen file changed vs origin/main: {f}")
    for line in git("diff", "--name-status", "origin/main", "--", *PROTECTED).splitlines():
        status, _, path = line.partition("\t")
        name = Path(path).name
        committed = bool(git("diff", "--name-only", "origin/main", "HEAD", "--", path).strip())
        if not committed and (name in LOCAL_STATE_NAMES or name.endswith(LOCAL_STATE_SUFFIXES)):
            continue
        if path.startswith(".github/workflows/") and status == "A" and name.startswith(ALLOWED_NEW_WORKFLOWS):
            continue
        bad.append(f"protected path changed: {status} {path}")
    for p in sorted((ROOT / "kb/reports").glob("C*_APPROVED.md")):
        if "owner_message:" not in p.read_text(encoding="utf-8", errors="ignore"):
            bad.append(f"{p.name} has no recorded owner_message")
    scope = ROOT / "kb/reports/scope_P0_5.json"
    if scope.exists():
        rel = "kb/reports/scope_P0_5.json"
        adds = git("log", "--diff-filter=A", "--format=%H", "--", rel).split()
        try:
            now = json.loads(scope.read_text(encoding="utf-8"))
            if adds:
                first = json.loads(git("show", f"{adds[-1]}:{rel}"))
                if len(now.get("chunk_ids", [])) < len(first.get("chunk_ids", [])):
                    bad.append("frozen P0.5 scope shrank since it was first committed")
        except ValueError:
            bad.append("scope_P0_5.json unreadable")
    for g in sorted((ROOT / "kb/reports").glob("P*.json")):
        try:
            d = json.loads(g.read_text(encoding="utf-8"))
        except ValueError:
            bad.append(f"{g.name} is not valid JSON")
            continue
        if "sample_seed" in d and d["sample_seed"] != seed_for(d.get("phase", g.stem)):
            bad.append(f"{g.name}: sample_seed does not follow the seed rule")
    if bad:
        print("TRIPWIRE FAILED")
        for b in bad:
            print(" -", b)
        return 1
    print("tripwire clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
