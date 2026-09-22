"""Identify and rerun the small tail of documents with no usable extraction.

Context: the corpus run is essentially complete (7,488 ok of 7,676 expected).
What remains is a tail found by cross-checking three sources:

  inventory (the plan) -> checkpoint (what ran) -> corpus dir (what exists)

Three distinct residual classes, kept separate because the remedy differs:

  A. genuinely absent        - no artefacts anywhere. Needs extraction.
  B. checkpoint-ok, no files - the runner recorded success but nothing is on
                               disk (a crash between write and record). Needs
                               re-extraction, and is the dangerous class because
                               it looks complete from the checkpoint alone.
  C. status=error / no-extractable-content - recorded failures. Needs a rerun.

Breakwave files known to be junk (login walls mislabeled .pdf, removed
deliberately) and documents already covered by the HTML pass are EXCLUDED, not
silently dropped: they are counted in the report.

usage:
    python scripts/extract/rerun_tail.py --list          # show the tail
    python scripts/extract/rerun_tail.py --write-list    # emit a rerun file
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

INV = "data/extracted/inventory.jsonl"
CKPT = "data/extracted/corpus_checkpoint.jsonl"
CORPUS = "data/extracted/corpus"
OUT = "data/extracted/rerun_tail.json"

# removed on purpose: breakwave scrapes that were login walls or search pages,
# not documents (67 login pages + 1 search results page)
KNOWN_JUNK_PREFIX = "breakwave"
PROVENANCE_ONLY = ("cftc",)


def stem_of(p: str) -> str:
    b = os.path.basename(p.replace("\\", "/"))
    return b[:-4] if b.lower().endswith(".pdf") else b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--write-list", action="store_true")
    a = ap.parse_args()

    inv = {}
    for line in open(INV, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("dup_of_content"):
            continue
        if any(p in (o.get("source") or "").lower() for p in PROVENANCE_ONLY):
            continue
        inv[stem_of(o.get("path", ""))] = o
    print(f"expected documents: {len(inv):,}")

    ck = {}
    for line in open(CKPT, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        o = json.loads(line)
        ck[stem_of(o.get("doc", ""))] = o

    disk = set()
    for parent in os.listdir(CORPUS):
        pp = os.path.join(CORPUS, parent)
        if not os.path.isdir(pp):
            continue
        for s in os.listdir(pp):
            if os.path.exists(os.path.join(pp, s, "text.jsonl")):
                disk.add(s)

    done = {s for s, v in ck.items() if v.get("status") in ("ok", "no-extractable-content")}
    missing = set(inv) - done

    junk = {s for s in missing if KNOWN_JUNK_PREFIX in (inv[s].get("source") or "").lower()}
    html_covered = {s for s in missing if s in disk} - junk
    genuinely_absent = missing - junk - html_covered

    cls_b = {s for s, v in ck.items() if v.get("status") == "ok"} - disk
    cls_c = {s for s, v in ck.items() if v.get("status") in ("error", "no-extractable-content")}
    cls_c = {s for s in cls_c if s not in disk}

    print(f"\n  breakwave junk, deliberately absent : {len(junk):,}")
    print(f"  covered by the HTML pass            : {len(html_covered):,}")
    print(f"  A. genuinely absent                 : {len(genuinely_absent):,}")
    print(f"  B. recorded ok but no files on disk : {len(cls_b):,}")
    print(f"  C. recorded error / no-content      : {len(cls_c):,}")

    todo = sorted(genuinely_absent | cls_b | cls_c)
    print(f"\nTOTAL TO RERUN: {len(todo):,}")
    if a.list or not a.write_list:
        for s in todo:
            src = inv.get(s, {}).get("source", "?")
            print(f"   [{src[:16]:<16}] {s[:88]}")

    if a.write_list:
        payload = [{"stem": s, "source": inv.get(s, {}).get("source"),
                    "path": inv.get(s, {}).get("path")} for s in todo]
        json.dump(payload, open(OUT, "w", encoding="utf-8"), indent=1)
        print(f"\nwrote {OUT} with {len(payload)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
