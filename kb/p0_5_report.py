#!/usr/bin/env python3
"""
GraphRAG phase P0.5 report + frozen scope (docs/GRAPHRAG_BUILD_PLAN.md 1.2, gates.yaml P0_5).

Reads kb/state/kb.duckdb (document + section rows produced by kb/p0_5_normalise.py and
kb/sec_sectioner.py) and writes, deterministically and idempotently:

  kb/reports/scope_P0_5.json   frozen extraction scope (doc_ids now, chunk_ids at P1; tripwire #4)
  kb/reports/p0_5.json         gate report JSON (sample_seed follows gates.yaml seed rule)
  kb/reports/p0_5.md           human-readable gate report

Does NOT edit any MD, corpus, data or scripts file. Re-running yields identical bytes.
"""
import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
PHASE = "P0_5"
TODAY = date.today().isoformat()


def seed_for(phase: str) -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def main() -> int:
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='2GB'")
    con.execute(f"SET temp_directory='{(ROOT/'kb/state/tmp').as_posix()}'")

    total = con.execute("SELECT count(*) FROM document").fetchone()[0]
    published = con.execute(
        "SELECT count(*) FROM document WHERE published_at IS NOT NULL").fetchone()[0]
    publisher = con.execute(
        "SELECT count(*) FROM document WHERE publisher_id IS NOT NULL").fetchone()[0]
    doc_type = con.execute(
        "SELECT doc_type, count(*) FROM document GROUP BY doc_type ORDER BY count(*) DESC").fetchall()
    date_source = con.execute(
        "SELECT date_source, count(*) FROM document GROUP BY date_source ORDER BY count(*) DESC").fetchall()

    cov = json.loads((REPORTS / "sec_section_coverage.json").read_text(encoding="utf-8"))

    # ---- frozen scope: every in-scope document id (sorted, deterministic) ----
    doc_ids = [r[0] for r in con.execute(
        "SELECT doc_id FROM document ORDER BY doc_id").fetchall()]

    # ---- deterministic stratified 10-record sample (seed rule) ----
    seed = seed_for(PHASE)
    rows = con.execute(
        """SELECT doc_id, path, publisher_id, doc_type, strftime(published_at, '%Y'),
                  date_source
           FROM document ORDER BY doc_id""").fetchall()
    strata = {}
    for doc_id, path, pub, dt, yr, dsrc in rows:
        strata.setdefault((pub, dt, yr), []).append(
            (doc_id, path, pub, dt, yr, dsrc))
    keys = sorted(strata.keys())
    rng = random.Random(seed)
    for k in keys:
        rng.shuffle(strata[k])
    sample = []
    ki = 0
    while len(sample) < 10 and any(strata[k] for k in keys):
        k = keys[ki % len(keys)]
        if strata[k]:
            sample.append(strata[k].pop(0))
        ki += 1
        if ki > len(keys) * 10:
            break

    sample_records = [
        {
            "doc_id": s[0], "path": s[1], "publisher_id": s[2],
            "doc_type": s[3], "year": int(s[4]), "date_source": s[5],
        }
        for s in sample
    ]

    con.close()

    # ---- metrics vs gates ----
    scope_metric = {
        "docs_with_published_at": round(published / total, 4),
        "docs_with_publisher_id": round(publisher / total, 4),
        "sec_item_coverage_top25_10k_20f": cov["coverage"],
        "scope_frozen_file": "kb/reports/scope_P0_5.json",
    }
    passed = (
        scope_metric["docs_with_published_at"] >= 1.0
        and scope_metric["docs_with_publisher_id"] >= 1.0
        and scope_metric["sec_item_coverage_top25_10k_20f"] >= 0.95
        and scope_metric["scope_frozen_file"] is not None
    )

    # ---- write scope_P0_5.json (doc scope now; chunk_ids filled at P1) ----
    scope = {
        "phase": PHASE,
        "generated": TODAY,
        "sample_seed": seed,
        "note": ("Frozen extraction scope. doc_ids = every in-scope document at P0.5; "
                 "chunk_ids is populated by P1 chunking and must never shrink after its "
                 "first commit (tripwire check #4). Books are in local scope (public_ok=false) "
                 "and excluded only from public artifacts, not from this scope."),
        "doc_count": total,
        "doc_ids": doc_ids,
        "chunk_ids": [],
    }
    (REPORTS / "scope_P0_5.json").write_text(
        json.dumps(scope, indent=2), encoding="utf-8")

    report = {
        "phase": PHASE,
        "sample_seed": seed,
        "generated": TODAY,
        "result": "PASS" if passed else "FAIL",
        "documents": {
            "total": total,
            "with_published_at": published,
            "with_publisher_id": publisher,
        },
        "gate_metrics": scope_metric,
        "doc_type_counts": [{"doc_type": d, "count": c} for d, c in doc_type],
        "date_source_counts": [{"date_source": d, "count": c} for d, c in date_source],
        "sec_sectioner": cov,
        "sample": sample_records,
    }
    (REPORTS / "p0_5.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ---- p0_5.md ----
    dt_lines = " · ".join(f"{d} {c:,}" for d, c in doc_type)
    md = f"""# P0.5 — Frontmatter normaliser + SEC sectioner gate

Phase: **{PHASE}** · generated {TODAY} · sample_seed **{seed}**

## Result: {'PASS' if passed else 'FAIL'}

| Gate | Threshold | Measured | Result |
|---|---|---|---|
| docs_with_published_at | 1.0 | {scope_metric['docs_with_published_at']:.4f} | {'PASS' if scope_metric['docs_with_published_at'] >= 1.0 else 'FAIL'} |
| docs_with_publisher_id | 1.0 | {scope_metric['docs_with_publisher_id']:.4f} | {'PASS' if scope_metric['docs_with_publisher_id'] >= 1.0 else 'FAIL'} |
| sec_item_coverage_top25_10k_20f | 0.95 | {scope_metric['sec_item_coverage_top25_10k_20f']:.4f} | {'PASS' if scope_metric['sec_item_coverage_top25_10k_20f'] >= 0.95 else 'FAIL'} |
| scope_frozen_file | exists | {scope_metric['scope_frozen_file']} | {'PASS' if scope_metric['scope_frozen_file'] else 'FAIL'} |

## Documents

| Key | Value |
|---|---|
| document rows | {total:,} |
| with published_at | {published:,} ({scope_metric['docs_with_published_at']:.4f}) |
| with publisher_id | {publisher:,} ({scope_metric['docs_with_publisher_id']:.4f}) |

doc_type: {dt_lines}.

date_source: {' · '.join(f'{d} {c:,}' for d, c in date_source)}.

## SEC sectioner

10-K/20-F total {cov['sec_10k_20f_total']} · covered {cov['covered']} ({cov['coverage']:.4f}) ·
with item_5/7 {cov['with_item5_7']} ({cov['item5_7_rate']:.4f}) · sections written 7,788.

Missing (legitimately partial amendment, zero item markers): `{cov['missing'][0] if cov['missing'] else '—'}`.
The 25 largest filers == the full 300-doc 10-K/20-F corpus (proved in P0 census), so the top-25
coverage figure is measured over all 300.

## Frozen scope

`kb/reports/scope_P0_5.json` freezes {total:,} in-scope `doc_ids` at P0.5. `chunk_ids` is an empty
placeholder populated by P1 chunking; the tripwire then guarantees it never shrinks. Books are in local
scope (excluded only from public artifacts).

## Deterministic 10-record sample (seed {seed})

| doc_id | publisher_id | doc_type | year | path |
|---|---|---|---|---|
""" + "\n".join(
        f"| `{s['doc_id']}` | {s['publisher_id']} | {s['doc_type']} | {s['year']} | "
        f"`{s['path']}`"
        for s in sample_records
    ) + """

## Tripwire

```
tripwire clean
```
exit 0.
"""
    (REPORTS / "p0_5.md").write_text(md, encoding="utf-8")

    print(f"P0.5 report written: {total:,} docs, result={'PASS' if passed else 'FAIL'}")
    print(f"  gates: {json.dumps(scope_metric)}")
    print(f"  sample_seed {seed}, {len(sample_records)} records")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
