"""Repoint MOVED paths held in tracked derived JSON indexes.

Class (skill: "a path reference is THREE kinds, not one"): an explicit path
FIELD inside a derived index is a real reference. After the corpus migration
(`reports/shipbrokers/...` -> `corpus/<NN-group>/...`, and agora into year
partitions) such fields silently 404 for any consumer, and the register gate
cannot see it because it compares row COUNTS with itself.

Method (measured, no heuristics on content):
  * for every distinct value of the ledger's path fields that does NOT resolve,
    find the file by BASENAME anywhere under corpus/;
  * require EXACTLY ONE candidate and require it to exist - otherwise abort;
  * byte-replace the value in the raw file text, asserting the occurrence count
    equals the number of fields holding it;
  * CONTROL: re-parse, assert every ledger path field resolves and that nothing
    else changed; a second run is a no-op (idempotent).

Named, NOT fixed here (judgement, not mechanics): the 7 stale `pdf_path` values
in data/derived/poten_tanker_opinions_index.json carry a WRONG `year` field
("2004"/"unknown" for documents whose files live in 2014/2015/2007), so
repointing the path alone would leave the record internally inconsistent.

usage:
    python scripts/verify/repoint_stale_path_fields.py --dry-run
    python scripts/verify/repoint_stale_path_fields.py
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(".").resolve()
CORPUS = ROOT / "corpus"
FIELDS = ("source_pdf", "source_file", "pdf_path", "md_file", "local_path", "html_path")

LEDGER = [
    # (file, min expected stale occurrences - guards a silently-empty fix)
    ("data/derived/gold_standard_benchmark.json", 7),
]


def corpus_index():
    pool: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(CORPUS):
        for fn in filenames:
            rel = Path(dirpath, fn).relative_to(ROOT).as_posix()
            pool.setdefault(fn, []).append(rel)
    return pool


def collect(obj):
    out = []
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    stack.append(v)
                elif isinstance(v, str) and k in FIELDS:
                    out.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pool = corpus_index()
    print(f"corpus basenames indexed: {len(pool)}")
    total_stale = 0
    for rel, expect in LEDGER:
        p = ROOT / rel
        raw = p.read_bytes()
        vals = collect(json.loads(raw.decode("utf-8")))
        stale = sorted({v.replace(os.sep, "/") for v in vals
                        if "/" in v.replace(os.sep, "/")
                        and not v.startswith(("http", "s3"))
                        and not (ROOT / v.replace(os.sep, "/")).exists()})
        n_occ = sum(1 for v in vals if v in stale)
        print(f"\n{rel}: {len(vals)} path fields, {len(stale)} distinct stale ({n_occ} occurrences)")
        if not stale:
            print("  idempotent: nothing stale")
            continue
        if n_occ < expect:
            raise SystemExit(f"ABORT: expected >= {expect} stale occurrences, found {n_occ}")
        mapping = {}
        for v in stale:
            cand = pool.get(os.path.basename(v), [])
            if len(cand) != 1:
                raise SystemExit(f"ABORT: {v} -> {len(cand)} candidates")
            if raw.count(v.encode()) != sum(1 for x in vals if x == v):
                raise SystemExit(f"ABORT: occurrence count != field count for {v}")
            mapping[v] = cand[0]
            print(f"  {v}  ->  {cand[0]}")
        out = raw
        for old, new in mapping.items():
            out = out.replace(old.encode(), new.encode())
        post = collect(json.loads(out.decode("utf-8")))
        left = [v for v in post if "/" in v.replace(os.sep, "/")
                and not v.startswith(("http", "s3"))
                and not (ROOT / v.replace(os.sep, "/")).exists()]
        assert len(post) == len(vals), "field count drift"
        assert not left, f"still unresolved: {left[:3]}"
        print(f"  control: {len(post)} path fields (unchanged), 0 unresolved after, "
              f"{len(set(post))} distinct")
        total_stale += n_occ
        if not a.dry_run:
            p.write_bytes(out)
            print(f"  WROTE {rel}")
    print(f"\ntotal stale occurrences repointed: {total_stale}")
    if a.dry_run:
        print("dry-run: no write")


if __name__ == "__main__":
    main()
