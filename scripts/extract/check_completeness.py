"""Completeness check: is every expected document actually extracted?

Compares three sources, because each can disagree with the others:

  inventory.jsonl        - the plan (one row per PDF found, dup_of_content flags copies)
  corpus_checkpoint.jsonl - what the runner recorded
  corpus/<parent>/<stem>/ - the artefacts that actually exist on disk

Keys are compared on STEM (basename without .pdf) rather than full paths: the
inventory stores `data\\reports\\seabrokers\\pdfs\\x.pdf`, the checkpoint stores
`parent/stem`, and the corpus directory nests as `corpus/<parent>/<stem>/`.
Comparing raw paths across those three makes every document look missing, which
is a false alarm I hit once already.
"""
from __future__ import annotations

import collections
import json
import os
import sys

INV = "data/extracted/inventory.jsonl"
CKPT = "data/extracted/corpus_checkpoint.jsonl"
CORPUS = "data/extracted/corpus"
PROVENANCE_ONLY = ("cftc",)


def stem_of(p: str) -> str:
    b = os.path.basename(p.replace("\\", "/"))
    if b.lower().endswith(".pdf"):
        b = b[:-4]
    return b


def main() -> int:
    # ---- plan
    inv_rows = []
    for line in open(INV, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            inv_rows.append(json.loads(line))
        except Exception:
            pass
    uniq = [r for r in inv_rows if not r.get("dup_of_content")]
    expected, prov = set(), set()
    for r in uniq:
        s = stem_of(r.get("path", ""))
        if any(p in (r.get("source") or "").lower() for p in PROVENANCE_ONLY):
            prov.add(s)
        else:
            expected.add(s)
    print(f"inventory rows        : {len(inv_rows):,}")
    print(f"  unique (non-dup)    : {len(uniq):,}")
    print(f"  provenance-only     : {len(prov):,}")
    print(f"  EXPECTED to extract : {len(expected):,}")

    # ---- checkpoint
    ck: dict[str, dict] = {}
    torn = 0
    for line in open(CKPT, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            torn += 1
            continue
        ck[stem_of(o.get("doc", ""))] = o
    st = collections.Counter(v.get("status") for v in ck.values())
    print(f"\ncheckpoint unique     : {len(ck):,}   torn lines: {torn}")
    for k, v in st.most_common():
        print(f"     {k:<26}{v:>7,}")

    # ---- artefacts on disk
    disk = set()
    for parent in os.listdir(CORPUS):
        pp = os.path.join(CORPUS, parent)
        if not os.path.isdir(pp):
            continue
        for stem in os.listdir(pp):
            if os.path.exists(os.path.join(pp, stem, "text.jsonl")):
                disk.add(stem)
    print(f"artefacts on disk     : {len(disk):,}")

    # ---- the actual answers
    done = {s for s, v in ck.items() if v.get("status") in ("ok", "no-extractable-content")}
    missing = expected - done
    print(f"\nEXPECTED but not in checkpoint : {len(missing):,}")
    for m in sorted(missing)[:12]:
        print(f"   {m[:96]}")

    declared_ok_no_files = {s for s, v in ck.items() if v.get("status") == "ok"} - disk
    print(f"\ncheckpoint says ok, NO text.jsonl on disk : {len(declared_ok_no_files):,}")
    for m in sorted(declared_ok_no_files)[:12]:
        print(f"   {m[:96]}")

    extra = disk - set(ck)
    print(f"\non disk but not in checkpoint : {len(extra):,}  (HTML pass and recovered docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
