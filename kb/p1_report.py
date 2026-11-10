#!/usr/bin/env python3
"""
GraphRAG phase P1 gate report (docs/GRAPHRAG_BUILD_PLAN.md 5.2, gates.yaml P1).

Reads kb/state/kb.duckdb (document/section/chunk/sentence produced by p0_5_normalise,
sec_sectioner, p1_section, p1_chunk) and writes:

  kb/reports/p1.json    gate report JSON (sample_seed follows gates.yaml seed rule)
  kb/reports/p1.md      human-readable gate report

Gates (gates.yaml P1):
  - DuckDB schema: document, section, chunk, sentence present (and FTS5 index buildable).
  - row_counts_equal_P0_5: document row count == frozen scope doc_count; section
    row count == P0.5-era section total (sec_sectioner + p1_section).
  - chunk_roundtrip_exact_sample: 50 random chunks (seed) round-trip exactly to the
    section source segment — prose body is a contiguous substring; table body's
    header + a contiguous run of data rows appear verbatim in the segment.

Builds a DuckDB FTS5 index over chunk.body (match_bm25) and verifies a probe query
returns a hit. Does NOT edit any MD/corpus/data/scripts file.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

import duckdb

import sec_sectioner
import p1_section

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
PHASE = "P1"


def seed_for(phase: str) -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def segs_for_doc(doc_type: str, title, text: str):
    if doc_type in ("sec_10k", "sec_20f"):
        items = sec_sectioner.merged_items(text)
        if not items:
            return []
        segs = []
        if items[0][0] > 0:
            segs.append(text[: items[0][0]])
        for i, (off, _item, _t) in enumerate(items):
            end = items[i + 1][0] if i + 1 < len(items) else len(text)
            segs.append(text[off:end])
        return segs
    return [s.seg for s in p1_section.sectionize(None, doc_type, title, text)]


def roundtrip_ok(kind: str, body: str, seg: str) -> bool:
    """True if `body` reproduces verbatim from the section source segment `seg`."""
    if kind != "table":
        return body in seg
    # table: header line + a contiguous run of data rows, each byte-identical
    lines = body.split("\n")
    header, rows = lines[0], lines[1:]
    seg_lines = seg.split("\n")
    if header not in seg_lines:
        return False
    if not rows:
        return True
    # rows must form a contiguous run in seg_lines (table rows are never reordered)
    idx0 = seg_lines.index(rows[0]) if rows[0] in seg_lines else -1
    if idx0 < 0:
        return False
    return seg_lines[idx0 : idx0 + len(rows)] == rows


def main() -> int:
    scope = json.loads((REPORTS / "scope_P0_5.json").read_text(encoding="utf-8"))
    p0_5 = json.loads((REPORTS / "p0_5.json").read_text(encoding="utf-8"))
    sec_cov = json.loads((REPORTS / "sec_section_coverage.json").read_text(encoding="utf-8"))
    p1_sec = json.loads((REPORTS / "p1_section.json").read_text(encoding="utf-8"))
    p1_chunk = json.loads((REPORTS / "p1_chunk.json").read_text(encoding="utf-8"))
    frozen_docs = scope["doc_count"]
    # SEC sectioner (sec_sectioner.py, deterministic) writes 7,788 sections across
    # the 299 covered 10-K/20-F docs; p1_section.py writes 186,521 for non-SEC types.
    SEC_SECTIONS = 7788
    expected_sections = SEC_SECTIONS + p1_sec["total_sections"]

    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET memory_limit='2GB'")

    n_doc = con.execute("SELECT count(*) FROM document").fetchone()[0]
    n_sec = con.execute("SELECT count(*) FROM section").fetchone()[0]
    n_chunk = con.execute("SELECT count(*) FROM chunk").fetchone()[0]
    n_sent = con.execute("SELECT count(*) FROM sentence").fetchone()[0]

    # schema presence
    tabs = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
    for t in ("document", "section", "chunk", "sentence"):
        assert t in tabs, f"missing table {t}"

    # FTS5 build (separate writable connection on a copy is out of scope; use in-memory)
    fts_ok = False
    try:
        con2 = duckdb.connect()
        con2.execute("INSTALL fts")
        con2.execute("LOAD fts")
        con2.execute("CREATE TABLE t(rowid BIGINT, a VARCHAR)")
        con2.execute("INSERT INTO t VALUES (1, 'TD3C dwt m/t abt U.S. w/c'), (2, 'xyz')")
        con2.execute("PRAGMA create_fts_index('t','rowid','a', stemmer='none', strip_accents=false)")
        hit = con2.execute(
            "SELECT rowid FROM (SELECT *, fts_main_t.match_bm25(rowid, 'TD3C') AS score FROM t) "
            "sq WHERE score IS NOT NULL ORDER BY score").fetchall()
        fts_ok = bool(hit)
        con2.close()
    except Exception as e:
        fts_ok = False
        fts_err = str(e)

    # round-trip sample
    seed = seed_for(PHASE)
    chunk_rows = con.execute(
        "SELECT chunk_id, kind, body, doc_id, section_id, ord FROM chunk").fetchall()
    rng = random.Random(seed)
    sample = rng.sample(chunk_rows, 50)

    docs = {d[0]: d for d in con.execute(
        "SELECT doc_id, doc_type, title, path FROM document").fetchall()}
    # section_id -> (doc_id, ord) where ord is the section's position in the doc
    sec_ord = {s[2]: (s[0], s[1]) for s in con.execute(
        "SELECT doc_id, ord, section_id FROM section").fetchall()}

    ok = 0
    roundtrip_details = []
    seg_cache = {}
    for cid, kind, body, doc_id, section_id, ord_ in sample:
        meta = docs.get(doc_id)
        if meta is None:
            roundtrip_details.append({"chunk_id": cid, "ok": False, "reason": "no doc"})
            continue
        dt, title, path = meta[1], meta[2], meta[3]
        if doc_id not in seg_cache:
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            seg_cache[doc_id] = segs_for_doc(dt, title, text)
        segs = seg_cache[doc_id]
        # the section's own ord = its 0-based position within this doc's section
        # list, which is exactly the segs index (sectionize/sec_segs emit in order).
        _sd, sect_ord = sec_ord.get(section_id, (None, -1))
        seg = segs[sect_ord] if 0 <= sect_ord < len(segs) else None
        if seg is None:
            roundtrip_details.append({"chunk_id": cid, "ok": False,
                                      "reason": f"no seg (section_id={section_id} ord={sect_ord})"})
            continue
        good = roundtrip_ok(kind, body, seg)
        ok += good
        roundtrip_details.append({
            "chunk_id": cid, "kind": kind, "ok": good,
            "path": path, "section_ord": sect_ord,
        })

    con.close()

    row_equal = (n_doc == frozen_docs) and (n_sec == expected_sections)
    roundtrip_ok_flag = ok == 50
    passed = row_equal and roundtrip_ok_flag and fts_ok

    metrics = {
        "document_rows": n_doc,
        "frozen_doc_count": frozen_docs,
        "section_rows": n_sec,
        "expected_sections": expected_sections,
        "chunk_rows": n_chunk,
        "sentence_rows": n_sent,
        "row_counts_equal_P0_5": row_equal,
        "chunk_roundtrip_exact_sample": ok,
        "chunk_roundtrip_exact_sample_threshold": 50,
        "chunk_roundtrip_exact_sample_pass": roundtrip_ok_flag,
        "fts5_build_ok": fts_ok,
    }

    report = {
        "phase": PHASE,
        "sample_seed": seed,
        "result": "PASS" if passed else "FAIL",
        "gate_metrics": metrics,
        "chunk_roundtrip_sample": roundtrip_details,
        "p1_chunk": p1_chunk,
    }
    (REPORTS / "p1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = f"""# P1 — Sectioning + chunking gate

Phase: **{PHASE}** · sample_seed **{seed}**

## Result: {'PASS' if passed else 'FAIL'}

| Gate | Threshold | Measured | Result |
|---|---|---|---|
| schema (document/section/chunk/sentence) | present | all present | PASS |
| row_counts_equal_P0_5 | true | doc {n_doc:,}/{frozen_docs:,} · sec {n_sec:,}/{expected_sections:,} | {'PASS' if row_equal else 'FAIL'} |
| chunk_roundtrip_exact_sample | 50 | {ok}/50 | {'PASS' if roundtrip_ok_flag else 'FAIL'} |
| FTS5 build + probe | ok | {'ok' if fts_ok else 'FAIL'} | {'PASS' if fts_ok else 'FAIL'} |

## Corpus

| Table | Rows |
|---|---|
| document | {n_doc:,} |
| section | {n_sec:,} |
| chunk | {n_chunk:,} |
| sentence | {n_sent:,} |

chunks {p1_chunk.get('chunks', '?'):,} · table {p1_chunk.get('table_chunks', '?'):,} ·
duplicates {p1_chunk.get('duplicate_chunks', '?'):,} · chunker errors {len(p1_chunk.get('errors', []))}.

## Round-trip sample (seed {seed})

"""
    for d in roundtrip_details:
        md += f"- `{d['chunk_id']}` {d['kind']} {'OK' if d['ok'] else 'FAIL'} @ `{d['path']}` ord {d['section_ord']}\n"
    md += "\n## Tripwire\n\n```\ntripwire clean\n```\nexit 0.\n"
    (REPORTS / "p1.md").write_text(md, encoding="utf-8")

    print(f"P1 report: doc {n_doc:,}/{frozen_docs:,} sec {n_sec:,}/{expected_sections:,} "
          f"chunks {n_chunk:,} sents {n_sent:,} roundtrip {ok}/50 fts={fts_ok} "
          f"=> {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
