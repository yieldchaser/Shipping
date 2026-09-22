"""Identify the residual documents with no usable extraction.

Compares three sources that can each disagree:
  inventory.jsonl          - the plan
  corpus_checkpoint.jsonl  - what the runner recorded
  corpus/ recursive scan   - the artefacts that actually exist

Key normalisation is the whole difficulty, and each of these traps produced a
FALSE "missing" while this was written:
  1. inventory stores `data\\reports\\<src>\\pdfs\\<stem>.pdf`, the checkpoint
     stores `<source>/<stem>` - compare on stem, never on full path.
  2. on-disk stems are sanitised by safe_stem() (trailing dots stripped), so
     `<stem>.` on disk is `<stem>` - apply the same function to both sides.
  3. two layouts exist: corpus/<source>/<stem>/ and corpus/<stem>.pdf/<stem>/,
     and some directory names are truncated - so scan recursively and index
     stems at full length plus 40/60-character prefixes.

Output classes, kept separate because the remedy differs:
  breakwave junk  - login walls mislabeled .pdf, removed deliberately
  html-covered    - already extracted by the HTML pass
  recorded ok but no files - a crash between write and record (the dangerous
                             class, because the checkpoint alone looks clean)
  genuinely absent - needs extraction
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from extract_all import safe_stem  # noqa: E402

INV = "data/extracted/inventory.jsonl"
CKPT = "data/extracted/corpus_checkpoint.jsonl"
CORPUS = "data/extracted/corpus"
PROVENANCE_ONLY = ("cftc",)
JUNK_SOURCE = "breakwave"


def raw_stem(p: str) -> str:
    b = os.path.basename((p or "").replace("\\", "/"))
    return b[:-4] if b.lower().endswith(".pdf") else b


def load_inventory() -> dict[str, dict]:
    inv = {}
    for line in open(INV, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("dup_of_content"):
            continue
        if any(p in (o.get("source") or "").lower() for p in PROVENANCE_ONLY):
            continue
        inv[safe_stem(raw_stem(o.get("path", "")))] = o
    return inv


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
    ap.add_argument("--json", action="store_true", help="emit machine-readable output")
    a = ap.parse_args()

    inv = load_inventory()
    disk = scan_disk()
    ck = {}
    for line in open(CKPT, encoding="utf-8", errors="replace"):
        if line.strip():
            o = json.loads(line)
            ck[raw_stem(o.get("doc", ""))] = o

    def covered(s: str) -> bool:
        return s in disk or s[:40] in disk or s[:60] in disk

    missing = [s for s in inv if not covered(s)]
    junk = [s for s in missing if JUNK_SOURCE in (inv[s].get("source") or "").lower()]
    rest = [s for s in missing if s not in junk]

    cls_b = [s for s, v in ck.items() if v.get("status") == "ok" and s not in disk]
    result = {
        "expected": len(inv),
        "breakwave_junk": len(junk),
        "genuinely_absent": len(rest),
        "recorded_ok_but_no_files": len(cls_b),
        "documents": [
            {
                "stem": s,
                "source": inv[s].get("source"),
                "bytes": inv[s].get("bytes"),
                "path": inv[s].get("path"),
                "pdf_present": os.path.exists(inv[s].get("path", "")),
            }
            for s in sorted(rest)
        ],
    }
    if a.json:
        print(json.dumps(result, indent=1))
        return 0

    print(f"expected documents        : {result['expected']:,}")
    print(f"  breakwave junk (chosen) : {result['breakwave_junk']:,}")
    print(f"  genuinely absent        : {result['genuinely_absent']:,}")
    print(f"  recorded ok, no files   : {result['recorded_ok_but_no_files']:,}")
    print()
    for d in result["documents"]:
        print(f"  [{str(d['source'])[:14]:<14}] pdf_present={str(d['pdf_present']):<5} "
              f"{(d['bytes'] or 0)/1e6:8.2f} MB  {d['stem'][:64]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
