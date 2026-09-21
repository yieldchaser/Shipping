"""Stage 0: inventory every PDF in the corpus.

Walks canonical PDF roots, records path/bytes/mtime/source/year.
Output: data/extracted/inventory.jsonl + summary on stdout.

Usage: python scripts/extract/build_inventory.py [--out DIR]
"""
import argparse
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOTS = [
    "reports/shipbrokers",
    "reports/poten",
    "scripts/drewry_ais_pdfs",
    "reports/drybulk",
    "reports/tankers",
    "reports/breakwave",
    "reports/hellenic",
    "data/reports/seabrokers",
    "data/cftc_statements",
    "reports/fearnleys",
    "reports/seabrokers",
    "reports/signal",
    "reports/drewry",
    "docs",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seen = set()
    rows = []
    for root in ROOTS:
        full = os.path.join(REPO, root)
        if not os.path.isdir(full):
            continue
        for fp in glob.glob(os.path.join(full, "**", "*.pdf"), recursive=True):
            if fp in seen:
                continue
            seen.add(fp)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rel = os.path.relpath(fp, REPO)
            parts = rel.split(os.sep)
            rows.append({
                "path": rel,
                "bytes": st.st_size,
                "mtime": st.st_mtime,
                "source": parts[1] if len(parts) > 2 and parts[0] in
                ("reports", "data", "scripts") else parts[0],
                "root": root,
            })
    total_bytes = sum(r["bytes"] for r in rows)
    with open(os.path.join(a.out, "inventory.jsonl"), "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["path"]):
            f.write(json.dumps(r) + "\n")
    print(f"PDFs: {len(rows)}  bytes: {total_bytes / 1e9:.2f} GB")
    by_root = {}
    for r in rows:
        by_root[r["root"]] = by_root.get(r["root"], 0) + 1
    for k in sorted(by_root):
        print(f"  {k}: {by_root[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
