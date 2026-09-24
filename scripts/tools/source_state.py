"""What is ACTUALLY on disk, per source. Reads artefacts, never the plan's claims.

Run from the repo root:  python3 -B scratch/source_state.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

CORPUS = "corpus/01-brokers"
MD = "data/extracted/md"
CHARTS = "data/extracted/charts"
SERIES = "data/extracted/series"


def n(pat):
    return len(glob.glob(pat, recursive=True))


def main():
    rows = []
    for src in sorted(os.listdir(CORPUS)):
        p = f"{CORPUS}/{src}"
        if not os.path.isdir(p):
            continue
        rows.append({
            "source": src,
            "pdfs": n(f"{p}/**/*.pdf"),
            "md": n(f"{MD}/{src}/*.md"),
            "md_charts": n(f"{MD}/{src}/*.charts.json"),
            "ext_charts": n(f"{CHARTS}/{src}/*.charts.json"),
            "sidecar_tables": n(f"{MD}/{src}/*table*.json"),
            "csv": n(f"{MD}/{src}/*.csv"),
            "parquet": n(f"{MD}/{src}/*.parquet"),
        })
    hdr = ("source", "pdfs", "md", "md_charts", "ext_charts", "sidecar_tables", "csv", "parquet")
    w = max(len(r["source"]) for r in rows) + 1
    print("".join(h.rjust(11 if h != "source" else w) for h in hdr))
    for r in rows:
        print(r["source"].ljust(w) + "".join(
            str(r[h]).rjust(11 if h != "source" else w) for h in hdr[1:]))
    print()
    print("series files:")
    for f in sorted(glob.glob(f"{SERIES}/*")):
        with open(f, encoding="utf-8", errors="replace") as fh:
            lines = sum(1 for _ in fh)
        print(f"   {f}  ({lines} lines)")
    print()
    print("other bulk artefacts:")
    for pat in ("data/extracted/*/*.parquet", "data/extracted/*/*.csv",
                "data/extracted/llamaparse_*/*.md", "data/extracted/llamaparse_*/*.json"):
        c = n(pat)
        if c:
            print(f"   {pat} -> {c}")


if __name__ == "__main__":
    main()
