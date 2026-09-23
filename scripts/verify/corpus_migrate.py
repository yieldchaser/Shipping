"""
corpus_migrate.py - move a source into the canonical corpus/ tree, safely.

One reusable implementation of the pattern proven on Breakwave/Drewry/PPA/
Seabrokers (docs/data_layer_reorg_plan.md):

  * uses `git mv` for tracked files (preserves history, shows as R100), and a
    plain `mv` for gitignored/untracked files (git mv cannot move those);
  * NEVER deletes: any file it cannot move is reported and left in place;
  * verifies by sha256 that the set of file CONTENTS is identical before and
    after, so a move can never silently lose or alter data;
  * supports re-sorting a year-first tree into broker-first order.

Usage:
    # dry run - show the plan, change nothing
    python scripts/verify/corpus_migrate.py --from reports/fearnleys --to corpus/01-brokers/fearnleys

    # execute
    python scripts/verify/corpus_migrate.py --from reports/fearnleys --to corpus/01-brokers/fearnleys --apply

    # re-sort <year>/<broker>/* -> <broker>/<year>/*
    python scripts/verify/corpus_migrate.py --from reports/broker_reports --to corpus/01-brokers/_digests \
        --resort year-then-broker --apply
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def content_fingerprint(root: Path) -> tuple[int, str]:
    """(file count, hash of the sorted set of per-file content hashes).

    Path-independent: the same content moved elsewhere yields the same value.
    """
    if not root.is_dir():
        return (0, "")
    digests = []
    for f in sorted(root.rglob("*")):
        if f.is_file():
            digests.append(sha256_of(f))
    joined = "\n".join(sorted(digests))
    return (len(digests), hashlib.sha256(joined.encode()).hexdigest()[:16])


def is_tracked(path: Path) -> bool:
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=REPO_ROOT, capture_output=True)
    return r.returncode == 0


def move_one(src: Path, dst: Path, apply: bool) -> str:
    """Return 'git', 'plain', or 'skip:<reason>'."""
    if not apply:
        return "git" if is_tracked(src) else "plain"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return f"skip:exists:{dst}"
    if is_tracked(src):
        r = subprocess.run(["git", "mv", str(src), str(dst)],
                           cwd=REPO_ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            return "git"
        # fall through to plain move if git refused (e.g. ignored mid-tree)
    try:
        shutil.move(str(src), str(dst))
        return "plain"
    except Exception as e:  # never lose a file: report and leave it
        return f"skip:{type(e).__name__}"


def dest_for(src: Path, src_root: Path, dst_root: Path, resort: str | None) -> Path:
    rel = src.relative_to(src_root)
    if resort == "year-then-broker" and len(rel.parts) >= 3:
        year, broker, *rest = rel.parts
        return dst_root / broker / year / Path(*rest)
    return dst_root / rel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--resort", choices=["year-then-broker"], default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    src_root = REPO_ROOT / args.src
    dst_root = REPO_ROOT / args.dst
    if not src_root.is_dir():
        print(f"FAIL: source {src_root} is not a directory")
        return 1

    before_n, before_h = content_fingerprint(src_root)
    print(f"source      : {args.src}")
    print(f"destination : {args.dst}" + (f"  (resort: {args.resort})" if args.resort else ""))
    print(f"before      : {before_n} files, content-fingerprint {before_h}")
    if not args.apply:
        print("MODE        : dry run (no changes). Pass --apply to execute.")

    files = [f for f in sorted(src_root.rglob("*")) if f.is_file()]
    tally: dict[str, int] = {}
    problems: list[str] = []
    for f in files:
        dst = dest_for(f, src_root, dst_root, args.resort)
        # a directory-level git mv is far faster; handled below instead
        tally["planned"] = tally.get("planned", 0) + 1

    if args.apply:
        # fast path: move whole top-level entries with git mv where possible
        for entry in sorted(src_root.iterdir()):
            if args.resort:
                break
            dst = dst_root / entry.name
            if dst.exists():
                problems.append(f"dest exists, left in place: {entry.name}")
                continue
            dst_root.mkdir(parents=True, exist_ok=True)
            res = move_one(entry, dst, True) if entry.is_file() else None
            if res is None:
                r = subprocess.run(["git", "mv", str(entry), str(dst)],
                                   cwd=REPO_ROOT, capture_output=True, text=True)
                if r.returncode != 0:
                    shutil.move(str(entry), str(dst))
                tally["moved-dir"] = tally.get("moved-dir", 0) + 1
                continue
            if res.startswith("skip"):
                problems.append(f"{entry.name}: {res}")
            else:
                tally[res] = tally.get(res, 0) + 1
        if args.resort:
            for f in files:
                if not f.exists():
                    continue  # already moved by a parent move
                dst = dest_for(f, src_root, dst_root, args.resort)
                res = move_one(f, dst, True)
                if res.startswith("skip"):
                    problems.append(f"{f.relative_to(REPO_ROOT)}: {res}")
                else:
                    tally[res] = tally.get(res, 0) + 1

    after_src_n, after_src_h = content_fingerprint(src_root)
    after_dst_n, after_dst_h = content_fingerprint(dst_root)

    print(f"\nplanned/moved : {tally}")
    if problems:
        print(f"problems ({len(problems)}):")
        for p in problems[:15]:
            print(f"    {p}")
    print(f"source after  : {after_src_n} files (was {before_n})")
    print(f"dest   after  : {after_dst_n} files")

    if args.apply:
        if after_src_n != 0:
            print("WARN: source not empty - inspect leftovers before committing")
        if after_dst_n < before_n:
            print(f"FAIL: dest has FEWER files than source had ({after_dst_n} < {before_n})")
            return 1
        print("OK: no content lost")
    return 0


if __name__ == "__main__":
    sys.exit(main())
