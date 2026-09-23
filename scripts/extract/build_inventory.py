"""Stage 0: inventory every PDF in the corpus.

Walks canonical PDF roots, records path/bytes/mtime/source/year.
Output: data/extracted/inventory.jsonl + summary on stdout.

Usage: python scripts/extract/build_inventory.py [--out DIR]
"""
import argparse
import glob
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOTS = [
    "reports/shipbrokers",
    "reports/poten",
    "scripts/drewry_ais_pdfs",
    "corpus/03-breakwave/drybulk",
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
    "scratch",
]

# Top-level-only PDF globs (dirs already walked recursively above would double-count)
TOP_LEVEL_GLOBS = ["reports/*.pdf"]


def md5_of(fp, chunk=1 << 20):
    h = hashlib.md5()
    with open(fp, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


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
                "md5": md5_of(fp),
                "source": parts[1] if len(parts) > 2 and parts[0] in
                ("reports", "data", "scripts") else parts[0],
                "root": root,
            })
    total_bytes = sum(r["bytes"] for r in rows)
    for pat in TOP_LEVEL_GLOBS:
        for fp in glob.glob(os.path.join(REPO, pat)):
            if fp in seen:
                continue
            seen.add(fp)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rel = os.path.relpath(fp, REPO)
            rows.append({"path": rel, "bytes": st.st_size, "mtime": st.st_mtime,
                         "md5": md5_of(fp), "source": "textbooks", "root": "reports/"})
    seen_md5 = set()
    dups = 0
    for r in rows:
        if r["md5"] in seen_md5:
            r["dup_of_content"] = True
            dups += 1
        else:
            r["dup_of_content"] = False
            seen_md5.add(r["md5"])
    with open(os.path.join(a.out, "inventory.jsonl"), "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["path"]):
            f.write(json.dumps(r) + "\n")
    print(f"PDFs: {len(rows)}  bytes: {total_bytes / 1e9:.2f} GB")
    print(f"unique content: {len(seen_md5)}  content-dups skipped: {dups}")
    by_root = {}
    for r in rows:
        by_root[r["root"]] = by_root.get(r["root"], 0) + 1
    for k in sorted(by_root):
        print(f"  {k}: {by_root[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
