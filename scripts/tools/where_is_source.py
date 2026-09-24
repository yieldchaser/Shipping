"""Locate every extraction artefact for a source, wherever it actually lives.

Run:  python3 -B scratch/where_is_source.py carriers intermodal lion clarksons
"""
from __future__ import annotations

import glob
import os
import sys

PATTERNS = [
    "data/extracted/{s}/*",
    "data/extracted/md/{s}/*",
    "data/extracted/charts/{s}/*",
    "data/extracted/series/*{s}*",
    "data/extracted/*{s}*",
    "data/derived/*{s}*",
]


def main(names):
    for s in names:
        print("=" * 72)
        print(s.upper())
        seen = set()
        for pat in PATTERNS:
            for f in sorted(glob.glob(pat.format(s=s), recursive=True)):
                if f in seen:
                    continue
                seen.add(f)
                if os.path.isdir(f):
                    n = len(os.listdir(f))
                    print(f"   DIR  {f}  ({n} files)")
                else:
                    print(f"   FILE {f}  ({os.path.getsize(f)} bytes)")
        # sample one
        for f in sorted(seen):
            if os.path.isfile(f) and f.endswith((".csv", ".json")):
                try:
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        head = [next(fh, "").rstrip() for _ in range(2)]
                    print(f"   --- head of {os.path.basename(f)}:")
                    for h in head:
                        print("       " + h[:150])
                except Exception as e:                       # noqa: BLE001
                    print("   (unreadable)", e)
                break


if __name__ == "__main__":
    main(sys.argv[1:] or ["carriers"])
