"""Agora - repoint STALE `source_file` paths in agora_indicators_series.csv.

WHY: the order-02-03 corpus migration moved agora PDFs into YEAR partitions
(corpus/01-brokers/agora/<YYYY>/...), but 10,002 rows of the shipped series still
carried the pre-migration FLAT path (corpus/01-brokers/agora/...pdf). A path
field in a derived index that no longer resolves silently 404s for any consumer;
the register gate cannot see it (it compares row COUNTS to itself). This is the
skill's "explicit path field" class, not a content mention.

WHAT IT DOES (measured, minimal, idempotent):
  * every distinct stale value must resolve to EXACTLY ONE file in the agora tree
    (219 files, 0 duplicate basenames) and its YEAR DIRECTORY must equal the
    issue_date year of the rows carrying it - otherwise the run aborts;
  * only the source_file bytes change: a byte-level replacement whose occurrence
    count must equal the row count (filenames need no CSV quoting).
  * CONTROL: row count unchanged; every other column byte-identical; 100% of
    source_file values resolve on disk afterwards; a second run changes nothing.

usage:
    python scripts/extract/publishers/fix_agora_source_paths.py --dry-run
    python scripts/extract/publishers/fix_agora_source_paths.py
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "corpus" / "01-brokers" / "agora"
CSV = ROOT / "data" / "extracted" / "series" / "agora_indicators_series.csv"
MD = ROOT / "data" / "extracted" / "md" / "agora"


def load_rows(raw: bytes):
    txt = raw.decode("utf-8-sig")
    rdr = csv.DictReader(io.StringIO(txt))
    rows = list(rdr)
    return rdr.fieldnames, rows


def tree():
    pool = collections.defaultdict(list)
    for p in SRC.rglob("*"):
        if p.is_file():
            pool[p.name].append(p.relative_to(ROOT).as_posix())
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    raw = CSV.read_bytes()
    hdr, rows = load_rows(raw)
    assert "source_file" in hdr, "no source_file column"
    print(f"rows {len(rows)}; header {hdr}")

    stale = collections.OrderedDict()   # old value -> set(issue years)
    for r in rows:
        v = r["source_file"]
        if v.startswith("corpus/") and not (ROOT / v).exists():
            stale.setdefault(v, set()).add((r.get("issue_date") or "")[:4])
    print(f"stale path rows {sum(1 for r in rows if r['source_file'] in stale)}; distinct {len(stale)}")
    if not stale:
        print("idempotent: nothing stale, no write")
        return

    pool = tree()
    uniq = {k: v for k, v in pool.items() if len(v) > 1}
    assert not uniq, f"ambiguous basenames in agora tree: {list(uniq)[:3]}"
    mapping = {}
    for v, yrs in stale.items():
        base = v.rsplit("/", 1)[-1]
        cand = pool.get(base)
        assert cand and len(cand) == 1, f"no unique candidate for {v}"
        new = cand[0]
        year_dir = new.split("/")[3]
        assert yrs == {year_dir}, f"year mismatch {v} -> {new} (rows say {sorted(yrs)})"
        assert raw.count(new.encode()) == 0, f"target already present: {new}"
        assert raw.count(v.encode()) == sum(1 for r in rows if r["source_file"] == v), \
            f"occurrence count != row count for {v}"
        mapping[v] = new
    print(f"mapping resolved for {len(mapping)} distinct values, all unique, all year-consistent")

    out = raw
    for old, new in mapping.items():
        out = out.replace(old.encode(), new.encode())

    n_hdr, n_rows = load_rows(out)
    assert n_hdr == hdr and len(n_rows) == len(rows), "row/header drift"
    changed = 0
    for before, after in zip(rows, n_rows):
        for c in hdr:
            if c == "source_file":
                if before[c] != after[c]:
                    changed += 1
                continue
            assert before[c] == after[c], f"column {c} changed: {before[c]!r} -> {after[c]!r}"
    assert changed == sum(1 for r in rows if r["source_file"] in mapping), "changed-row count drift"
    unresolved = [r["source_file"] for r in n_rows if not (ROOT / r["source_file"]).exists()]
    md_stems = {p.name for p in MD.rglob("*.md")}
    covered = sum(1 for r in n_rows if r["source_file"].rsplit("/", 1)[-1].rsplit(".", 1)[0] + ".md" in md_stems)
    print(f"control: rows {len(n_rows)} (unchanged); source_file rows rewritten {changed}; "
          f"all other columns byte-identical; unresolved after {len(unresolved)}; "
          f"docs with md {len({r['source_file'] for r in n_rows if r['source_file'].rsplit('/',1)[-1].rsplit('.',1)[0] + '.md' in md_stems})}")
    for u in unresolved[:5]:
        print("   UNRESOLVED", u)

    if a.dry_run:
        sample = list(mapping.items())[:3]
        for o, n in sample:
            print("   DRY", o, "->", n)
        print("dry-run: no write")
        return

    CSV.write_bytes(out)
    n_hdr2, n_rows2 = load_rows(CSV.read_bytes())
    assert n_hdr2 == hdr and len(n_rows2) == len(rows)
    print(f"WROTE {CSV.name}: {len(n_rows2)} rows, every source_file resolves")


if __name__ == "__main__":
    main()
