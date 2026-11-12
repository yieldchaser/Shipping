"""P4c step 5: union of every extraction source into one gated, deduped record file.

Owner decision C1 makes P4c a ladder, not a single pass:
  * `p4c_bulk`        - free Ultrafast bulk extraction, every pack of the frozen scope (plan §10.3)
  * `p4c_glean`       - free Ultrafast recall pass ("facts the first pass missed"), every pack (D11)
  * `p4c_bulk_retry`  - free Ultrafast single-chunk retry of the rule-6 repair queue (plan §7.4/§7.6)
  * `p4c_esc`         - glm-5.3 escalation of what still fails, doc-value order, $17 cap (owner 3)
  * `p4c_glm2`        - glm-5.3 second extractor on the highest-value chunks, $25.25 cap (owner 4)

Every raw answer is re-gated here with the same §7.4 gates the per-pass gate run uses, so a record can
only enter the union after it passed the template-consistency checks. Kept records are then merged per
chunk across sources.

Dedupe rule (declared, deviation D13): two records are the same fact when they share closed-ontology
identity (kind, printed type, entity refs) and their evidence sentences overlap (Jaccard >= 0.3 or
containment >= 0.5) - exactly the rule P4b used to build the adjudicated gold reference. A duplicate
keeps the highest-confidence copy and the full provenance list; the number of duplicates is reported,
nothing is dropped silently.

Output `kb/state/p4c/union/gated_union.jsonl`: one row per chunk of the frozen scope, shaped like a
gate row (`kept` plus top-level kind lists) so the audit and report steps read it unchanged.

Metric note (D12): `failure_queue_max: 0.02` (gates.yaml P4c) is measured here over the union as the
share of chunks that are *broken* - every source call for the chunk broke (blank/schema-fail after the
runner's retries) or records were returned yet all failed gates 2-4. That is the pipeline repair queue.
Extraction *quality* (recall, missed facts) is measured on the gold set by `p4c_recall.py`, not hidden
inside this count.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import extract_schema as E  # noqa: E402
import extract_gates as GR  # noqa: E402
import p4b_run as B  # noqa: E402
import p4c_gate as G  # noqa: E402
import p4c_run as RUN  # noqa: E402

OUT = KB.parent / "kb/state/p4c"
UNION_DIR = OUT / "union"
KINDS = G.KINDS

ULTRAFAST = "deepseek-v4.1-flash-1017-ultrafast"
GLM = "glm-5.3"
# (pass, model) in priority order: earlier sources win confidence ties on a duplicate
SOURCE_SPEC = [
    ("p4c_bulk", ULTRAFAST),
    ("p4c_glean", ULTRAFAST),
    ("p4c_bulk_retry", ULTRAFAST),
    ("p4c_esc", GLM),
    ("p4c_glm2", GLM),
]


def source_mode(pass_name: str, model: str, modes: dict | None = None) -> str:
    modes = RUN.load_modes() if modes is None else modes
    return modes.get(model) or "tools"


def sentences_of(pack: dict) -> dict[str, list[tuple[int, str]]]:
    return {b["cid"]: [(int(s), t) for s, t in b["sentences"]] for b in pack["blocks"]}


def kept_for(pack: dict, pass_name: str, model: str, mode: str | None = None) -> dict:
    """Gate one source's stored raw for this pack and return kept records per chunk.

    Returns {"call": "ok"|"missing"|"blank"|"schema_fail", "total": n, "dropped": n,
             "chunks": {cid: {kind: [pydantic records]}}}
    """
    res = {"call": "missing", "total": 0, "dropped": 0,
           "chunks": {cid: {k: [] for k in KINDS} for cid in pack["chunk_ids"]}}
    mode = mode or source_mode(pass_name, model)
    text, _usage = G.read_raw(G.raw_for(pass_name, model, mode, pack))
    if text is None or not text.strip():
        res["call"] = "blank" if text is not None else "missing"
        return res
    ext, _err = E.parse_extraction(text)
    if ext is None:
        res["call"] = "schema_fail"
        return res
    ext, _new_ids, new_names = E.canonicalize(ext, pack.get("known") or [])
    g = GR.gate_chunk(ext, G.pack_ctx(pack, new_names))
    res["call"] = "ok"
    res["total"] = int(g.get("records_total") or 0)
    res["dropped"] = sum(1 for r in g["records"] if r.get("dropped"))
    res["new_entities"] = {k: v for k, v in new_names.items()
                           if k in (g.get("new_entities_ok") or {}) and g["new_entities_ok"][k]}
    bcid_to_chunk = {b["cid"]: cid for cid, b in zip(pack["chunk_ids"], pack["blocks"])}
    for kind in KINDS:
        for rec in g["kept"].get(kind) or []:
            cid = bcid_to_chunk.get(getattr(rec, "chunk", None))
            if cid:
                res["chunks"][cid][kind].append(rec)
    return res


def record_row(kind: str, rec, sents: list[tuple[int, str]], source: str) -> dict:
    body = rec.model_dump(mode="json") if hasattr(rec, "model_dump") else dict(rec)
    body["record_kind"] = kind  # claims carry their own `kind` (forecast/view/causal); do not clobber
    body["chunk"] = getattr(rec, "chunk", body.get("chunk"))
    body["sids"] = list(getattr(rec, "sids", body.get("sids") or []))
    body["quote"] = B.record_quote(kind, rec, sents)
    body["sources"] = [source]
    return body


def sig_of(row: dict) -> tuple:
    """Closed-ontology identity of a plain-dict record (mirror of `p4b_run.record_sig`)."""
    kind = row.get("record_kind")
    if kind == "state_facts":
        return (kind, row.get("type"), frozenset([row.get("src"), row.get("dst")]) - {None})
    if kind == "events":
        return (kind, row.get("type"),
                frozenset((r or {}).get("entity") for r in row.get("roles") or []) - {None})
    return (kind, row.get("kind"), frozenset(row.get("subjects") or []))


def same_fact(a: tuple, b: tuple, qa: str, qb: str) -> bool:
    """Dedupe rule (D13): same closed-ontology slot, compatible entity set, overlapping evidence.

    Entity sets must be nested (one a subset of the other) so a source that resolved one extra role
    still merges, while two different facts about the same vessel (different counterparties) stay
    separate - `p4b_run.records_match` alone accepts any shared entity, which is right for building
    the gold reference inside one chunk but too loose for cross-source dedupe.
    """
    if a[0] != b[0] or a[1] != b[1]:
        return False
    ea, eb = a[2], b[2]
    if bool(ea) != bool(eb):
        return False
    if ea and eb and not (ea <= eb or eb <= ea):
        return False
    return B.records_match(a, b, qa, qb)


def merge_records(acc: list[dict], rows: list[dict], source: str) -> tuple[int, int]:
    """Merge one source's rows into the accumulator; returns (added, duplicates)."""
    added = dup = 0
    for row in rows:
        sig = sig_of(row)
        hit = None
        for cur in acc:
            if same_fact(sig, cur["_sig"], row["quote"], cur["quote"]):
                hit = cur
                break
        if hit is None:
            row["_sig"] = sig
            acc.append(row)
            added += 1
            continue
        dup += 1
        hit["sources"] = sorted(set(hit["sources"]) | {source})
        ca, cb = hit.get("confidence"), row.get("confidence")
        if isinstance(cb, (int, float)) and (not isinstance(ca, (int, float)) or cb > ca):
            hit["confidence"] = cb
        # keep entity refs the other copy resolved (same identity, different printed handle)
        for key in ("entities", "subjects", "roles"):
            if not hit.get(key) and row.get(key):
                hit[key] = row[key]
    return added, dup


def union_pack(pack: dict, sources: list[tuple[str, str]], modes: dict | None = None) -> dict:
    """Merge every source for one pack into one row per chunk (call-level stats kept alongside)."""
    sents = sentences_of(pack)
    bcid = {cid: b["cid"] for cid, b in zip(pack["chunk_ids"], pack["blocks"])}
    doc = pack.get("doc") or {}
    acc: dict[str, dict] = {}
    stats = {"calls": {}, "total": 0, "dropped": 0, "added": Counter(), "duplicates": 0,
             "new_entities": {}}
    for cid in pack["chunk_ids"]:
        acc[cid] = {k: [] for k in KINDS}
    for pass_name, model in sources:
        got = kept_for(pack, pass_name, model, source_mode(pass_name, model, modes))
        stats["calls"][pass_name] = got["call"]
        stats["total"] += got["total"]
        stats["dropped"] += got["dropped"]
        stats["new_entities"].update(got.get("new_entities") or {})
        for cid, kinds in got["chunks"].items():
            for kind in KINDS:
                rows = [record_row(kind, rec, sents[bcid[cid]], pass_name) for rec in kinds[kind]]
                if not rows:
                    continue
                added, dup = merge_records(acc[cid][kind], rows, pass_name)
                stats["added"][pass_name] += added
                stats["duplicates"] += dup
    statuses = list(stats["calls"].values())
    non_missing = [v for v in statuses if v != "missing"]
    all_blank = bool(non_missing) and all(v in ("blank", "schema_fail") for v in non_missing)
    rows = []
    for cid in pack["chunk_ids"]:
        kinds = acc[cid]
        kept = {}
        for kind in KINDS:
            for row in kinds[kind]:
                row.pop("_sig", None)
            kept[kind] = kinds[kind]
        n = sum(len(v) for v in kept.values())
        prov: Counter = Counter()
        for kind in KINDS:
            for row in kept[kind]:
                prov.update(row["sources"])
        # D12: "broken" = every source that answered this pack broke, or records came back and all
        # failed gates 2-4. "missing" is not broken - it just has not been extracted yet.
        broken = all_blank or (stats["total"] > 0 and n == 0)
        rows.append({
            "chunk_id": cid, "doc_id": pack["doc_id"],
            "publisher": doc.get("publisher"), "doc_type": doc.get("doc_type"),
            "published_at": doc.get("published_at"), "ord": pack.get("ord_first"),
            "year": pack.get("year"), "section_class": pack.get("section_class"),
            "no_content": n == 0 and bool(non_missing) and not broken,
            "records_total": n, "records_ok": n,
            "gates_dropped": stats["dropped"],
            "call_broken": broken,
            "call_missing": not non_missing,
            "new_entities": stats["new_entities"],
            "provenance": dict(prov),
            "calls": dict(stats["calls"]),
            "kept": kept,
            **kept,
        })
    return {"rows": rows, "stats": stats}


def build(sources: list[tuple[str, str]] | None = None, packs_path: Path | None = None,
          out_dir: Path | None = None, limit: int = 0) -> dict:
    sources = sources or SOURCE_SPEC
    out_dir = out_dir or UNION_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    modes = RUN.load_modes()
    stats = {
        "sources": [{"pass": p, "model": m, "mode": source_mode(p, m, modes)} for p, m in sources],
        "chunks": 0, "docs": set(), "chunks_with_records": 0, "broken_chunks": 0,
        "missing_chunks": 0,
        "records": 0, "by_kind": Counter(), "records_per_source": Counter(),
        "duplicates": 0, "dropped_by_gates": 0, "call_status": Counter(),
        "by_doc_type": Counter(), "by_publisher": Counter(), "new_entities": 0,
        "chunks_by_records": Counter(),
    }
    tmp = out_dir / "gated_union.jsonl.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        for i, pack in enumerate(G.load_packs(packs_path)):
            if limit and i >= limit:
                break
            got = union_pack(pack, sources, modes)
            for row in got["rows"]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            st = got["stats"]
            stats["chunks"] += len(got["rows"])
            stats["docs"].add(pack["doc_id"])
            for row in got["rows"]:
                n = row["records_total"]
                stats["records"] += n
                stats["records_per_source"].update(row["provenance"])
                stats["chunks_by_records"][min(n, 10)] += 1
                if n:
                    stats["chunks_with_records"] += 1
                if row["call_broken"]:
                    stats["broken_chunks"] += 1
                if row["call_missing"]:
                    stats["missing_chunks"] += 1
                stats["by_doc_type"][row["doc_type"]] += n
                stats["by_publisher"][row["publisher"]] += n
                for kind in KINDS:
                    stats["by_kind"][kind] += len(row["kept"][kind])
            stats["duplicates"] += st["duplicates"]
            stats["dropped_by_gates"] += st["dropped"]
            stats["call_status"].update(st["calls"].values())
            stats["new_entities"] += len(st["new_entities"])
            if (i + 1) % 500 == 0:
                print(f"union: packs={i + 1} chunks={stats['chunks']} records={stats['records']}",
                      flush=True)
    tmp.replace(out_dir / "gated_union.jsonl")
    out = dict(stats)
    out["docs"] = len(stats["docs"])
    out["by_kind"] = dict(stats["by_kind"])
    out["records_per_source"] = dict(stats["records_per_source"])
    out["duplicates_rate"] = (round(stats["duplicates"] / stats["records"], 4)
                              if stats["records"] else None)
    out["missing_rate"] = (round(stats["missing_chunks"] / stats["chunks"], 4)
                           if stats["chunks"] else None)
    out["failure_queue_rate"] = (round(stats["broken_chunks"] / stats["chunks"], 4)
                                 if stats["chunks"] else None)
    out["failure_queue_max"] = 0.02
    out["coverage_complete"] = ((not limit) and stats["chunks"] >= RUN.FULL_SCOPE_CHUNKS
                                and stats["missing_chunks"] == 0)
    out["call_status"] = dict(stats["call_status"])
    out["chunks_by_records"] = {str(k): v for k, v in sorted(stats["chunks_by_records"].items())}
    out["by_doc_type"] = {k: v for k, v in stats["by_doc_type"].items() if v}
    (out_dir / "union_stats.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("by_doc_type",)}, indent=2)[:1200])
    return out


def parse_sources(text: str | None) -> list[tuple[str, str]]:
    if not text:
        return list(SOURCE_SPEC)
    known = dict(SOURCE_SPEC)
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            p, m = chunk.split(":", 1)
            out.append((p.strip(), m.strip()))
        elif chunk in known:
            out.append((chunk, known[chunk]))
        else:
            raise SystemExit(f"unknown source {chunk!r}; use pass:model or {sorted(known)}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", default=None, help="comma list of pass:model (default: full ladder)")
    ap.add_argument("--packs", default=None, type=Path)
    ap.add_argument("--out-dir", default=None, type=Path)
    ap.add_argument("--limit", type=int, default=0, help="packs, for a dry run")
    args = ap.parse_args(argv)
    build(parse_sources(args.sources), args.packs, args.out_dir, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
