"""
build_corpus_inventory.py

Inventory of bulk vendor files that live under corpus/ but are deliberately NOT
tracked by git (they total ~555 MB; tracking them would break pushes).

Why this exists:
  Drewry AIS PDFs and Pilbara Ports Authority throughput PDFs previously lived in
  scripts/drewry_ais_pdfs/ and scratch/ppa_pdf/ - BOTH gitignored, both
  conventionally disposable. 769 real data files were one cleanup away from
  silent destruction, with nothing in git recording that they had ever existed.

  They now live in corpus/ (durable, non-disposable), and this script records a
  per-file inventory WITH sha256 into corpus/_inventory_untracked.json, which IS
  tracked. Loss is therefore detectable, and any file can be re-verified or
  re-fetched from source.

Usage:
    python scripts/verify/build_corpus_inventory.py            # write
    python scripts/verify/build_corpus_inventory.py --check    # verify only, exit 1 on drift
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

CORPUS_ROOT = REPO_ROOT / "corpus"
OUT_PATH = CORPUS_ROOT / "_inventory_untracked.json"

# (canonical path relative to repo root, where it was moved from)
UNTRACKED_SOURCES = [
    ("corpus/06-drewry/ais", "scripts/drewry_ais_pdfs"),
    ("corpus/09-ppa/ppa_pdf", "scratch/ppa_pdf"),
    ("corpus/09-ppa/_root_pdfs", "scratch/*.pdf (loose)"),
]


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def tracked_set() -> set[str]:
    """Every path git currently tracks. One call - much faster than per-file."""
    r = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT,
                       capture_output=True, text=True, errors="ignore")
    return {ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()}


def scan() -> dict:
    """Inventory every file under corpus/ that git does NOT track.

    Deliberately derived from git rather than a hardcoded list: the whole point
    is that a bulk vendor tree can sit in a durable location while staying
    untracked (~3.9 GB of PDFs), and we still want its existence, size and
    sha256 recorded so loss is detectable.
    """
    tracked = tracked_set()
    entries: list[dict] = []
    groups: list[dict] = []
    if not CORPUS_ROOT.is_dir():
        return {"groups": groups, "entries": entries}

    for sub in sorted(p for p in CORPUS_ROOT.iterdir() if p.is_dir()):
        n = 0
        total = 0
        for f in sorted(sub.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
            if rel in tracked:
                continue
            size = f.stat().st_size
            n += 1
            total += size
            entries.append({
                "path": rel,
                "bytes": size,
                "sha256": sha256_of(f),
            })
        groups.append({"path": str(sub.relative_to(REPO_ROOT)).replace("\\", "/"),
                       "untracked_files": n, "untracked_bytes": total})
    return {"groups": groups, "entries": entries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the on-disk state matches the committed inventory")
    args = ap.parse_args()

    current = scan()

    if args.check:
        if not OUT_PATH.exists():
            print(f"FAIL: inventory missing at {OUT_PATH}")
            return 1
        recorded = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        rec = {e["path"]: e for e in recorded.get("entries", [])}
        cur = {e["path"]: e for e in current["entries"]}
        missing = sorted(set(rec) - set(cur))
        added = sorted(set(cur) - set(rec))
        changed = sorted(p for p in set(rec) & set(cur)
                         if rec[p]["sha256"] != cur[p]["sha256"])
        print(f"recorded={len(rec)} on_disk={len(cur)}")
        print(f"missing={len(missing)} added={len(added)} changed={len(changed)}")
        for label, items in (("MISSING", missing), ("CHANGED", changed)):
            for p in items[:10]:
                print(f"  {label}: {p}")
        for p in added[:10]:
            print(f"  ADDED (new file, re-run without --check to record): {p}")
        if missing or changed:
            print("FAIL: untracked corpus inventory has drifted")
            return 1
        print("OK: inventory matches")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    for g in current["groups"]:
        print(f"  {g['path']:<28} untracked={g['untracked_files']:<6} "
              f"bytes={g['untracked_bytes']:>13,}")
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}  ({len(current['entries'])} untracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
