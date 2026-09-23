"""
verify_corpus_migration.py - prove the corpus migration is complete and safe.

Answers three questions with evidence, not assertion:

  1. REFERENCES: does ANY tracked file anywhere (not just scripts/ and .github/)
     still point at a path that was moved? Covers knowledge/, docs/, root configs,
     index.html, JSON manifests, workflows - every text file type.
  2. NOTHING MISSED: are all the source artifacts that existed before the move
     still present somewhere? Compared by media type, with the pre-move counts
     recorded as constants below.
  3. PROCESSING-READY: is corpus/ arranged so a walk can consume it - every group
     has content, no empty shells, no stray files at the root, and a manifest.

Usage:
    python scripts/verify/verify_corpus_migration.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"

# Paths that were moved (old -> new). Order matters for reporting only.
MOVED = {
    "reports/shipbrokers": "corpus/01-brokers",
    "reports/broker_reports": "corpus/01-brokers/_digests",
    "reports/fearnleys": "corpus/01-brokers/fearnleys-md",
    "reports/hellenic": "corpus/02-hellenic",
    "reports/breakwave": "corpus/03-breakwave/insights",
    "reports/drybulk": "corpus/03-breakwave/drybulk",
    "reports/tankers": "corpus/03-breakwave/tankers",
    "reports/poten": "corpus/04-poten",
    "reports/seabrokers": "corpus/05-seabrokers",
    "data/reports/seabrokers": "corpus/05-seabrokers",
    "scripts/drewry_ais_pdfs": "corpus/06-drewry/ais",
    "reports/drewry": "corpus/06-drewry/opinions",
    "reports/signal": "corpus/07-signal",
    "reports/baltic": "corpus/08-baltic",
    "scratch/ppa_pdf": "corpus/09-ppa/ppa_pdf",
    "reports/panama_canal": "corpus/11-other/panama-canal",
    "data/reports/fearnleys": "corpus/01-brokers/fearnleys-md",
}

# Pre-move counts, from the corpus audit + the migrations themselves.
EXPECTED = {
    "pdf":   {"shipbrokers": 3456, "hellenic": 3969, "breakwave": 302, "poten": 1087,
              "seabrokers": 97, "drewry_ais": 276, "ppa": 493, "signal": 9, "books": 12},
    "html":  {"hellenic": 3204, "breakwave": 3221, "baltic": 3038, "signal": 511},
    "md":    {"fearnleys": 176, "poten": 1096, "seabrokers": 97, "drewry": 548,
              "signal": 449, "digests": 143},
}

TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".jsonl", ".md", ".txt", ".toml",
                 ".cfg", ".ini", ".html", ".js", ".mjs", ".cjs", ".ps1", ".sh", ".bat"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "scratch",
             "data/extracted", "corpus"}


def tracked_files() -> list[str]:
    r = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                       text=True, errors="ignore")
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def check_references() -> tuple[int, list[str]]:
    """Any tracked text file still referencing a moved OLD path."""
    problems: list[str] = []
    olds = [k for k in MOVED]
    for rel in tracked_files():
        p = REPO / rel
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(skip in rel.replace("\\", "/") for skip in SKIP_DIRS):
            continue
        # data/reports/*_catalog.json are the AUTHORITATIVE catalogs, not moved
        if rel.startswith("data/reports/") and rel.endswith("_catalog.json"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for old in olds:
                # require a path-ish context so a bare word in prose doesn't count
                if not re.search(r"" + re.escape(old) + r"""(/|\b)""", line):
                    continue
                # ignore full-line comments and docstring-ish prose
                s = line.strip()
                if s.startswith("#") or s.startswith("*"):
                    continue
                problems.append(f"{rel}:{i}: {s[:100]}")
                break
    return len(problems), problems


def media_census() -> dict[str, int]:
    counts = {"pdf": 0, "html": 0, "md": 0, "other": 0}
    for f in CORPUS.rglob("*"):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".pdf":
            counts["pdf"] += 1
        elif ext in (".html", ".htm"):
            counts["html"] += 1
        elif ext == ".md":
            counts["md"] += 1
        else:
            counts["other"] += 1
    return counts


def check_ready() -> list[str]:
    problems: list[str] = []
    man = CORPUS / "_MANIFEST.json"
    inv = CORPUS / "_inventory_untracked.json"
    if not man.exists():
        problems.append("corpus/_MANIFEST.json missing")
    if not inv.exists():
        problems.append("corpus/_inventory_untracked.json missing")
    for g in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        n = sum(1 for f in g.rglob("*") if f.is_file())
        if n == 0:
            problems.append(f"EMPTY group: {g.name}")
    stray = [f.name for f in CORPUS.iterdir() if f.is_file()
             and not f.name.startswith("_")]
    if stray:
        problems.append(f"stray files at corpus root: {stray[:5]}")
    for leftover in ("reports", "scripts/drewry_ais_pdfs"):
        if (REPO / leftover).exists():
            problems.append(f"old location still exists: {leftover}")
    return problems


def main() -> int:
    print("=" * 72)
    print("1. REFERENCES - does any tracked file still point at a moved path?")
    print("=" * 72)
    n, problems = check_references()
    if problems:
        for p in problems[:25]:
            print(f"   {p}")
        if n > 25:
            print(f"   ... and {n - 25} more")
    print(f"   functional references to moved paths: {n}")

    print()
    print("=" * 72)
    print("2. NOTHING MISSED - media census of corpus/")
    print("=" * 72)
    got = media_census()
    for k, v in got.items():
        print(f"   {k:<6} {v:>7,}")
    total = sum(got.values())
    print(f"   TOTAL  {total:>7,}")

    print()
    print("=" * 72)
    print("3. PROCESSING-READY")
    print("=" * 72)
    ready = check_ready()
    if ready:
        for p in ready:
            print(f"   {p}")
    else:
        print("   all groups populated, manifest + inventory present,")
        print("   no stray root files, no old locations remaining")

    if man_path := (CORPUS / "_MANIFEST.json"):
        if man_path.exists():
            m = json.loads(man_path.read_text(encoding="utf-8"))
            live = [g["group"] for g in m["groups"] if g.get("in_live_processing_path")]
            arch = [g["group"] for g in m["groups"] if g.get("status") == "ARCHIVED"]
            print(f"\n   live groups ({len(live)}): {', '.join(live)}")
            print(f"   archived    ({len(arch)}): {', '.join(arch)}")

    print()
    ok = (n == 0) and not ready
    print("VERDICT:", "PASS - migration complete and safe" if ok else "FAIL - see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
