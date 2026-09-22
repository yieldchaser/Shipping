"""Repair checkpoint rows that claim success but have no artefacts.

The failure mode: a worker extracts charts page-by-page, then dies (timeout or
memory) before writing text.jsonl. Because it died, no row is written for that
attempt - but the document may ALREADY have an earlier row, or the counts skew,
so the runner treats it as done and `--resume` skips it forever. The result is a
document that reports success and has no text, which is invisible to any check
that trusts the checkpoint.

Action: find rows whose document has no text.jsonl on disk, and rewrite the
checkpoint keeping only rows that still have artefacts. Documents whose rows are
dropped are then picked up by the next `--resume` run.

usage:
    python scripts/extract/repair_checkpoint.py --report
    python scripts/extract/repair_checkpoint.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
from extract_all import safe_stem  # noqa: E402

CORPUS = "data/extracted/corpus"
CKPT = "data/extracted/corpus_checkpoint.jsonl"


def scan_disk() -> set[str]:
    disk: set[str] = set()
    for root, _dirs, files in os.walk(CORPUS):
        if "text.jsonl" not in files:
            continue
        leaf = safe_stem(os.path.basename(root))
        for cand in (leaf, safe_stem(leaf + ".pdf"), leaf[:40], leaf[:60]):
            disk.add(cand)
    return disk


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    disk = scan_disk()
    rows, keep, dropped = [], [], []
    for line in open(CKPT, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        o = json.loads(line)
        rows.append(o)
        doc = o.get("doc", "")
        stem = safe_stem(doc.split("/")[-1])
        has = stem in disk or stem[:40] in disk or stem[:60] in disk
        # only trust the presence check for rows recorded as ok; error rows are
        # supposed to be revisited and must stay visible
        if o.get("status") == "ok" and not has:
            dropped.append((doc, o.get("status"), o.get("pages"), o.get("tables")))
        else:
            keep.append(o)

    print(f"checkpoint rows      : {len(rows):,}")
    print(f"  kept               : {len(keep):,}")
    print(f"  dropped (ok, no artefacts): {len(dropped):,}")
    for d, s, p, t in dropped:
        print(f"     {d[:80]}  status={s} pages={p} tables={t}")

    if not a.apply:
        print("\n(report only; re-run with --apply to rewrite)")
        return 0

    shutil.copy(CKPT, CKPT + ".bak")
    with open(CKPT, "w", encoding="utf-8") as f:
        for o in keep:
            f.write(json.dumps(o) + "\n")
    print(f"\nrewrote {CKPT} ({len(keep)} rows); backup at {CKPT}.bak")
    print("dropped documents will be picked up by the next --resume run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
