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
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

OUT_PATH = REPO_ROOT / "corpus" / "_inventory_untracked.json"

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


def scan() -> dict:
    entries: list[dict] = []
    groups: list[dict] = []
    for rel, origin in UNTRACKED_SOURCES:
        root = REPO_ROOT / rel
        if not root.is_dir():
            groups.append({"path": rel, "moved_from": origin, "exists": False,
                           "files": 0, "bytes": 0})
            continue
        n = 0
        total = 0
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            size = f.stat().st_size
            n += 1
            total += size
            entries.append({
                "path": str(f.relative_to(REPO_ROOT)).replace("\\", "/"),
                "bytes": size,
                "sha256": sha256_of(f),
            })
        groups.append({"path": rel, "moved_from": origin, "exists": True,
                       "files": n, "bytes": total})
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
        print(f"  {g['path']:<32} files={g['files']:<5} bytes={g['bytes']:>12,}  (was {g['moved_from']})")
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}  ({len(current['entries'])} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
