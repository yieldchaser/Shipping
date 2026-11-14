"""P4c gate report: merge bulk + ladder gated output into per-chunk final status and judge the gates.

Pure post-processing, no model calls. Inputs are the JSONL files the gate step wrote
(`gated.jsonl` for the bulk pass and one for each rung of the escalation ladder, later rungs taking
precedence only when they make a chunk fully clean), plus `audit.json` from `p4c_audit.py` and the
per-pass run state files. Output is `kb/reports/p4c.json` + `.md` with the `gates.yaml` rows, real
coverage of the frozen scope (declared, never hidden), ten sampled chunks with their source paths, real
money from the ledger and wall time per pass.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import runner as R  # noqa: E402

ROOT = KB.parent
OUT = ROOT / "kb/state/p4c"
REPORTS = ROOT / "kb/reports"
DB = ROOT / "kb/state/kb.duckdb"
PHASE = "P4C"
GATED = OUT / "gated.jsonl"
UNION_GATED = OUT / "union/gated_union.jsonl"
UNION_STATS = OUT / "union/union_stats.json"
LADDER_PLAN = OUT / "ladder_plan.json"
RECALL = OUT / "recall.json"
AUDIT = OUT / "audit.json"
REPORT_JSON = REPORTS / "p4c.json"
REPORT_MD = REPORTS / "p4c.md"

SCOPE_CHUNKS = 86607
SCOPE_DOCS = 16945
SCOPE_PUBLISHERS = 59
SCOPE_DOC_TYPES = 19
SCOPE_YEARS = 24
PASSES = ("p4c_bulk", "p4c_bulk_retry", "p4c_glean", "p4c_esc", "p4c_glm2")
KINDS = ("state_facts", "events", "claims")
GATES = {"failure_queue_max": 0.02, "random_audit_records": 200,
         "random_audit_wrong_max": 0.03,
         "judge_family_differs_from_extractor": True,
         "coverage_of_frozen_scope_reported": True}


def seed_for(phase: str = PHASE) -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def chunk_state(chunk: dict) -> dict:
    """One chunk's gate outcome as a comparable status (clean / no_content / failed + counts).

    Two different questions, answered separately so neither can be mistaken for the other:

    * ``clean``  - strict quality: *every* record the model returned survived gates 2-4. This is
      what decides whether a later ladder rung may replace the bulk verdict.
    * ``broken`` - the D12 repair queue: every source call for the chunk broke, or records came
      back and *all* of them failed gates 2-4. This is the quantity the frozen gate key
      ``failure_queue_max`` is bound to (see ``p4c_union`` L299, and the key's own name).
      "Missing" (never extracted) is not broken, and neither is a chunk that kept some records.
    """
    failed = bool(chunk.get("call_failed")) or int(chunk.get("gates_2_4_failed") or 0) > 0
    kept = chunk.get("kept") or {}
    counts = {k: len(kept.get(k) or []) for k in KINDS}
    total = int(chunk.get("records_total") or 0)
    missing = bool(chunk.get("call_missing"))
    broken = bool(chunk.get("call_failed")) or (total > 0 and sum(counts.values()) == 0)
    # A missing chunk is *not* clean: `merge` lets a clean later rung replace an earlier verdict, so
    # calling "never extracted" clean would let an empty rung row overwrite real records.
    return {"chunk_id": chunk.get("chunk_id"), "clean": not failed and not missing, "broken": broken,
            "call_failed": bool(chunk.get("call_failed")), "missing": missing,
            "records_total": total,
            "records_ok": int(chunk.get("records_ok") or 0),
            "dropped": int(chunk.get("gates_2_4_failed") or 0),
            "no_content": bool(chunk.get("no_content")),
            "kept": counts,
            "gated": chunk}


def _row_chunks(row: dict):
    """Yield (chunk_id, chunk, doc_id) from either gated shape.

    `p4c_gate.gate_run` writes one flat row per pack-chunk; older pack-shaped fixtures nest the
    verdicts under `chunks`. Accept both so the report cannot silently merge zero rows.
    """
    nested = row.get("chunks")
    if isinstance(nested, dict):
        for cid, chunk in nested.items():
            yield cid, chunk, row.get("doc_id")
        return
    cid = row.get("chunk_id")
    if cid:
        yield cid, row, row.get("doc_id")


def merge(gated_paths: list[Path]) -> dict:
    """{chunk_id: final status}; a later rung replaces a chunk only when it comes out clean."""
    final: dict[str, dict] = {}
    order: list[str] = []
    rows = 0
    merged = 0
    for path in gated_paths:
        for row in load_jsonl(path):
            rows += 1
            for cid, chunk, doc_id in _row_chunks(row):
                merged += 1
                st = chunk_state(chunk)
                st["doc_id"] = doc_id
                st["rung"] = path.parent.name
                prev = final.get(cid)
                if prev is None:
                    final[cid] = st
                    order.append(cid)
                elif st["clean"]:
                    st["was_failed"] = not prev["clean"]
                    final[cid] = st
    return {"chunks": final, "order": order, "gated_rows": rows,
            "merged_chunks": merged,
            "rungs": [str(p.parent.name) for p in gated_paths]}



def merge_union(path: Path) -> dict:
    """{chunk_id: final status} from `p4c_union.gated_union.jsonl` (D13 merged record set).

    The union rows already carry the *post-ladder, deduped* kept records, so they are the truth for
    records and the D12 failure queue; the per-rung gated files stay the truth for ladder provenance.
    """
    final: dict[str, dict] = {}
    order: list[str] = []
    rows = 0
    for row in load_jsonl(path):
        rows += 1
        kept = {k: len((row.get("kept") or {}).get(k) or []) for k in KINDS}
        n = int(row.get("records_total") or 0)
        broken = bool(row.get("call_broken"))
        missing = bool(row.get("call_missing"))
        st = {"chunk_id": row["chunk_id"], "doc_id": row.get("doc_id"),
              "clean": not broken and not missing, "broken": broken, "missing": missing,
              "kept": kept,
              "records_total": n, "records_ok": int(row.get("records_ok") or 0),
              "dropped": int(row.get("gates_dropped") or 0),
              "no_content": bool(row.get("no_content")),
              "call_failed": broken,
              "was_failed": False, "rung": "union"}
        prev = final.get(row["chunk_id"])
        if prev is None:
            order.append(row["chunk_id"])
        final[row["chunk_id"]] = st
    return {"chunks": final, "order": order, "gated_rows": rows, "merged_chunks": rows,
            "rungs": [str(path.parent.name)]}


def union_stats(path: Path = UNION_STATS) -> dict:
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False}
    return {"present": True, "chunks": st.get("chunks"), "records": st.get("records"),
            "by_kind": st.get("by_kind"), "records_per_source": st.get("records_per_source"),
            "duplicates": st.get("duplicates"), "duplicates_rate": st.get("duplicates_rate"),
            "dropped_by_gates": st.get("dropped_by_gates"),
            "broken_chunks": st.get("broken_chunks"),
            "failure_queue_rate": st.get("failure_queue_rate"),
            "sources": st.get("sources")}


def rule6(path: Path = LADDER_PLAN) -> dict:
    """D12: rule-6 escalation queue as planned by `p4c_ladder.py` (declared partial coverage)."""
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False}
    q = plan.get("queue") or {}
    esc = plan.get("escalation") or {}
    retry = plan.get("retry") or {}
    return {"present": True, "gated_chunks": q.get("chunks"), "queue": q.get("queue"),
            "queue_rate": q.get("queue_rate"), "triggers": q.get("triggers"),
            "retry_singles": retry.get("selected"), "retry_unmatched": retry.get("unmatched"),
            "escalation_picked": esc.get("picked"), "escalation_skipped": esc.get("skipped"),
            "escalation_est_usd": esc.get("est_usd"), "escalation_cap_usd": esc.get("cap_usd"),
            "escalation_model": esc.get("model"), "partial_coverage": esc.get("partial_coverage")}


def recall(path: Path = RECALL) -> dict:
    try:
        rc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False}
    return {"present": True, "strict": rc.get("union"), "sources": rc.get("sources"),
            "baseline_replayed": rc.get("baseline_replayed_p4b_cand_recall"),
            "baseline_p4b_report": rc.get("p4b_report_recall"),
            "gain_vs_replayed": rc.get("recall_gain_vs_replayed_baseline"),
            "gain_vs_p4b_report": rc.get("recall_gain_vs_p4b_report"),
            "reference_records": rc.get("reference_records")}


def doc_meta(packs_path: Path) -> dict[str, dict]:
    """doc_id -> document metadata, because the gated rows only carry the chunk-level verdicts."""
    meta: dict[str, dict] = {}
    with packs_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            doc = pack.get("doc") or {}
            meta[pack["doc_id"]] = {"publisher": doc.get("publisher"),
                                    "doc_type": doc.get("doc_type"),
                                    "published_at": doc.get("published_at"),
                                    "heading": doc.get("heading")}
    return meta


def coverage(chunks: dict, meta: dict) -> dict:
    # "Extracted" means a call actually answered: a chunk whose row is a `missing` placeholder was
    # never extracted and must not be counted as covered (D12 / L438 partial coverage).
    live = [c for c in chunks.values() if not c.get("missing")]
    covered = [c["doc_id"] for c in live if c["doc_id"]]
    docs = sorted(set(covered))
    pubs = sorted({(meta.get(d) or {}).get("publisher") for d in docs} - {None})
    types = sorted({(meta.get(d) or {}).get("doc_type") for d in docs} - {None})
    years = sorted({str((meta.get(d) or {}).get("published_at") or "")[:4] for d in docs} - {"", "None"})
    total = len(live)
    return {"chunks": total, "scope_chunks": SCOPE_CHUNKS,
            "rows": len(chunks), "missing_chunks_rows": len(chunks) - total,
            "chunk_coverage": round(total / SCOPE_CHUNKS, 4),
            "docs": len(docs), "scope_docs": SCOPE_DOCS,
            "doc_coverage": round(len(docs) / SCOPE_DOCS, 4),
            "publishers": pubs, "publisher_count": len(pubs), "scope_publishers": SCOPE_PUBLISHERS,
            "doc_types": types, "doc_type_count": len(types), "scope_doc_types": SCOPE_DOC_TYPES,
            "years": years, "year_count": len(years),
            "partial": total < SCOPE_CHUNKS,
            "missing_chunks": SCOPE_CHUNKS - total}


def totals(chunks: dict) -> dict:
    by_kind = {k: sum(c["kept"][k] for c in chunks.values()) for k in KINDS}
    rec_ok = sum(c["records_ok"] for c in chunks.values())
    rec_total = sum(c["records_total"] for c in chunks.values())
    clean = sum(1 for c in chunks.values() if c["clean"])
    broken = [c for c in chunks.values() if c.get("broken")]
    strict_failed = [c for c in chunks.values() if not c["clean"] and not c.get("missing")]
    missing = [c for c in chunks.values() if c.get("missing")]
    n = len(chunks)
    extracted = n - len(missing)
    return {"chunks": n, "chunks_extracted": extracted, "chunks_missing": len(missing),
            "chunks_clean": clean, "chunks_failed": len(broken),
            "chunks_broken": len(broken),
            "chunks_no_content": sum(1 for c in chunks.values() if c["no_content"]),
            # frozen gate: `failure_queue_max` is the D12 repair queue (broken chunks / chunks).
            # Denominator = rows merged, identical to `p4c_union` L297 (broken_chunks / chunks),
            # so the frozen key reads the same number whichever export `build()` consumes.
            "failure_queue_rate": round(len(broken) / max(1, n), 4),
            "failure_queue_rate_extracted": round(len(broken) / max(1, extracted), 4),
            # strict quality reading: chunks where >=1 returned record failed gates 2-4. Reported,
            # never gated - rule 6 does not queue these, so spend cannot move this number.
            "chunks_strict_failed": len(strict_failed),
            "strict_failure_rate": round(len(strict_failed) / max(1, extracted), 4),
            "records_total": rec_total, "records_kept": sum(by_kind.values()),
            "records_dropped": sum(c["dropped"] for c in chunks.values()),
            "record_drop_rate": round(sum(c["dropped"] for c in chunks.values()) / max(1, rec_total), 4),
            "by_kind": by_kind,
            "recovered_by_ladder": sum(1 for c in chunks.values() if c["clean"] and c.get("was_failed"))}


def ladder_stats(chunks: dict) -> dict:
    by_rung: dict[str, int] = {}
    for c in chunks.values():
        by_rung[c["rung"]] = by_rung.get(c["rung"], 0) + 1
    return {"final_rung": by_rung,
            "still_failed": sum(1 for c in chunks.values() if c.get("broken")),
            "recovered": sum(1 for c in chunks.values() if c["clean"] and c.get("was_failed"))}


def audit_gate(audit_path: Path = AUDIT) -> dict:
    try:
        a = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False}
    return {"present": True, "judge": a.get("model"), "judge_family": a.get("judge_family"),
            "extractor": a.get("extractor_model"), "extractor_family": a.get("extractor_family"),
            "sampled": a.get("sampled"), "judged": a.get("judged"), "drop": a.get("drop"),
            "unparseable": a.get("unparseable"), "wrong": a.get("wrong"),
            "wrong_rate": a.get("wrong_rate")}


def gate_rows(st: dict, audit: dict, cov: dict) -> dict:
    rows = {
        "failure_queue_max": {"required": GATES["failure_queue_max"],
                              "measured": st["failure_queue_rate"],
                              "pass": st["failure_queue_rate"] <= GATES["failure_queue_max"]},
        "random_audit_records": {"required": GATES["random_audit_records"],
                                 "measured": audit.get("sampled") or 0,
                                 "pass": bool(audit.get("present")) and (audit.get("sampled") or 0)
                                 >= GATES["random_audit_records"]},
        "random_audit_wrong_max": {"required": GATES["random_audit_wrong_max"],
                                   "measured": audit.get("wrong_rate"),
                                   "pass": audit.get("present") and
                                   (audit.get("wrong_rate") is not None) and
                                   audit["wrong_rate"] <= GATES["random_audit_wrong_max"]},
        "judge_family_differs_from_extractor": {
            "required": GATES["judge_family_differs_from_extractor"],
            "measured": bool(audit.get("present")) and audit.get("judge_family") !=
            audit.get("extractor_family") and audit.get("judge_family") is not None,
            "pass": bool(audit.get("present")) and audit.get("judge_family") !=
            audit.get("extractor_family") and audit.get("judge_family") is not None},
        "coverage_of_frozen_scope_reported": {"required": GATES["coverage_of_frozen_scope_reported"],
                                              "measured": cov["chunks"] > 0,
                                              "pass": cov["chunks"] > 0},
    }
    return {"rows": rows, "all_pass": all(r["pass"] for r in rows.values())}


def cost() -> dict:
    per_pass = {p: round(R.spent(passes=[p]), 6) for p in PASSES + ("p4c_audit",)}
    return {"per_pass": per_pass, "total_usd": round(sum(per_pass.values()), 6)}


def wall() -> dict:
    out = {}
    for p in PASSES + ("p4c_audit",):
        path = OUT / f"run_{p}.json"
        try:
            st = json.loads(path.read_text(encoding="utf-8"))
            out[p] = {"wall_s": st.get("wall_s"), "packs": st.get("packs"),
                      "cost_usd": st.get("cost_usd"),
                      "rate_packs_per_min": st.get("rate_packs_per_min")}
        except (OSError, ValueError):
            out[p] = None
    return out


def doc_paths(doc_ids: list[str]) -> dict[str, str]:
    """Source paths for the sampled chunks (read-only; DuckDB takes one writer at a time)."""
    if not doc_ids or not DB.exists():
        return {}
    import duckdb
    con = duckdb.connect(str(DB), read_only=True)
    try:
        q = "SELECT doc_id, path FROM document WHERE doc_id IN (" + ",".join("?" for _ in doc_ids) + ")"
        return {r[0]: r[1] for r in con.execute(q, doc_ids).fetchall()}
    finally:
        con.close()


def sample_chunks(chunks: dict, n: int = 10) -> list[dict]:
    """Seeded sample of clean chunks that actually kept records - the report shows ten of them."""
    pool = [c for c in chunks.values() if c["clean"] and sum(c["kept"].values()) > 0]
    rng = random.Random(seed_for(PHASE + "_sample"))
    picked = rng.sample(pool, min(n, len(pool))) if pool else []
    return [{"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "records": sum(c["kept"].values()),
             "kept": c["kept"]} for c in picked]


def build(gated_paths: list[Path], packs_path: Path, audit_path: Path = AUDIT,
          union_path: Path = UNION_GATED, ladder_path: Path = LADDER_PLAN,
          recall_path: Path = RECALL) -> dict:
    merged = merge(gated_paths)
    union_merged = merge_union(union_path) if union_path.exists() else None
    chunks = (union_merged or merged)["chunks"]
    meta = doc_meta(packs_path)
    cov = coverage(chunks, meta)
    st = totals(chunks)
    audit = audit_gate(audit_path)
    gates = gate_rows(st, audit, cov)
    picks = sample_chunks(chunks)
    paths = doc_paths([p["doc_id"] for p in picks])
    for p in picks:
        p["source_path"] = paths.get(p["doc_id"])
        p["publisher"] = (meta.get(p["doc_id"]) or {}).get("publisher")
        p["doc_type"] = (meta.get(p["doc_id"]) or {}).get("doc_type")
        p["published_at"] = (meta.get(p["doc_id"]) or {}).get("published_at")
    urep = union_stats(union_path.parent / "union_stats.json") if union_merged else {"present": False}
    rep = {"phase": PHASE, "sample_seed": seed_for(PHASE),
           "generated": dt.datetime.now().isoformat(timespec="seconds"),
           "scope": {"chunks": SCOPE_CHUNKS, "docs": SCOPE_DOCS, "publishers": SCOPE_PUBLISHERS,
                     "doc_types": SCOPE_DOC_TYPES},
           "coverage": cov, "extraction": st, "ladder": ladder_stats(chunks),
           "rule6": rule6(ladder_path), "union": urep, "recall": recall(recall_path),
           "gated_source": "union" if union_merged else "rungs",
           "audit": audit, "gate_results": gates["rows"], "all_pass": gates["all_pass"],
           "cost": cost(), "wall": wall(), "rungs": merged["rungs"],
           "gated_rows": merged["gated_rows"], "merged_chunks": merged["merged_chunks"],
           "sample": picks}
    return rep


def _md(rep: dict) -> str:
    st, cov, ga = rep["extraction"], rep["coverage"], rep["gate_results"]
    lines = ["# P4c - full-scope extraction (plan §7, §10.3)", "",
             f"Seed `{rep['sample_seed']}` (phase `{rep['phase']}`). Generated {rep['generated']}.", "",
             "## Design note", "",
             "Bulk step runs the selected extractor over the frozen prose scope in ~3.5k-token packed "
             "calls (same document, static prompt, known entities, temp 0). Chunks that lose any record "
             "to gates 2-4 or come back blank/schema-broken go to a failure queue, retried one chunk per "
             "call by the same model and then by the escalation model; only a fully clean retry replaces "
             "the bulk verdict. Everything below is computed from stored raws - no re-calls. 200 stored "
             "records are re-judged by another family for the audit gate.", "",
             "Deviations declared: **D11** the owner overrode plan §7.6 (no blanket gleaning) - a free "
             "gleaning pass re-reads every chunk with its own first-pass answer in the prompt and keeps "
             "only missed records; it runs through the identical gates. **D10/D11** escalation to "
             "`glm-5.3` (owner choice, not nemotron) is cap-prioritised, so escalation coverage is "
             "partial by design (**D12**). **D14** the spare budget funds a second extractor "
             "(`glm-5.3`) on the highest-value chunks, quota-split across SEC/fleet, broker forecasts, "
             "fixtures and S&P. **D13** the union dedupes the same kind+type with overlapping quotes, "
             "keeps the highest-confidence copy and the provenance of every copy.", "",
             "## Scope coverage (declared)", "",
             "| metric | covered | frozen scope | share |", "|---|---|---|---|",
             f"| chunks | {cov['chunks']:,} | {cov['scope_chunks']:,} | {cov['chunk_coverage']:.2%} |",
             f"| documents | {cov['docs']:,} | {cov['scope_docs']:,} | {cov['doc_coverage']:.2%} |",
             f"| publishers | {cov['publisher_count']} | {cov['scope_publishers']} | - |",
             f"| doc types | {cov['doc_type_count']} | {cov['scope_doc_types']} | - |",
             f"| years | {cov['year_count']} | {SCOPE_YEARS} (1986-2026) | - |", "",
             (f"**Partial: {cov['missing_chunks']:,} scope chunks not covered** (declared, not hidden)."
              if cov["partial"] else "**Full scope covered.**"), "",
             "## Extraction", "",
             "| metric | value |", "|---|---|",
             f"| chunks attempted | {st['chunks']:,} |",
             f"| chunks clean (every returned record survived gates 2-4) | {st['chunks_clean']:,} |",
             f"| chunks escalated then clean | {st['recovered_by_ladder']:,} |",
             f"| broken chunks (D12 failure queue, gated) | {st['chunks_broken']:,} "
             f"({st['failure_queue_rate']:.2%}) |",
             f"| chunks with >=1 dropped record (diagnostic, **not** gated) | "
             f"{st['chunks_strict_failed']:,} ({st['strict_failure_rate']:.2%}) |",
             f"| chunks answering `no_content` | {st['chunks_no_content']:,} |",
             f"| records kept | {st['records_kept']:,} (state_facts {st['by_kind']['state_facts']:,}, "
             f"events {st['by_kind']['events']:,}, claims {st['by_kind']['claims']:,}) |",
             f"| records dropped by gates | {st['records_dropped']:,} "
             f"({st['record_drop_rate']:.2%} of attempted records) |",
             f"| final rung | {json.dumps(rep['ladder']['final_rung'])} |", "",
             "## Gates (`kb/gates.yaml` P4c)", "",
             "| gate | required | measured | pass |", "|---|---|---|---|"]
    for name, row in ga.items():
        req = row["required"]
        meas = row["measured"]
        lines.append(f"| `{name}` | {req} | {meas} | {'PASS' if row['pass'] else 'FAIL'} |")
    lines += ["", f"**all_pass: {rep['all_pass']}**", "",
              f"Final record set read from: **{rep['gated_source']}**.", ""]
    u = rep.get("union") or {}
    if u.get("present"):
        rps = u.get("records_per_source") or {}
        lines += ["## Union of extraction passes (D13)", "",
                  "| metric | value |", "|---|---|",
                  f"| records after merge | {u.get('records'):,} |",
                  f"| duplicates removed | {u.get('duplicates')} ({u.get('duplicates_rate')}) |",
                  f"| records per source | {json.dumps(rps)} |",
                  f"| records dropped by gates | {u.get('dropped_by_gates')} |",
                  f"| broken chunks (D12) | {u.get('broken_chunks')} "
                  f"({u.get('failure_queue_rate')}) |", ""]
    r6 = rep.get("rule6") or {}
    if r6.get("present"):
        lines += ["## Rule-6 escalation queue (D12)", "",
                  "| metric | value |", "|---|---|",
                  f"| chunks in the bulk gate | {r6.get('gated_chunks')} |",
                  f"| chunks triggering rule 6 | {r6.get('queue')} ({r6.get('queue_rate')}) |",
                  f"| triggers | {json.dumps(r6.get('triggers'))} |",
                  f"| free retry singles | {r6.get('retry_singles')} "
                  f"(unmatched {r6.get('retry_unmatched')}) |",
                  f"| escalated to `{r6.get('escalation_model')}` | {r6.get('escalation_picked')} "
                  f"(skipped by cap {r6.get('escalation_skipped')}) |",
                  f"| escalation spend | ${r6.get('escalation_est_usd')} of "
                  f"${r6.get('escalation_cap_usd')} cap |",
                  f"| partial coverage declared | {r6.get('partial_coverage')} |", ""]
    rc = rep.get("recall") or {}
    if rc.get("present"):
        strict = rc.get("strict") or {}
        lines += ["## Recall on the 120-chunk gold set (strict, same harness as P4b)", "",
                  f"Union recall **{strict.get('recall')}** (candidates {strict.get('candidates')}, "
                  f"matched {strict.get('matched')}, reference {strict.get('reference')}) vs replayed "
                  f"P4b baseline {rc.get('baseline_replayed')} -> gain "
                  f"**{rc.get('gain_vs_replayed')}**; vs P4b report recall "
                  f"{rc.get('baseline_p4b_report')} -> gain {rc.get('gain_vs_p4b_report')}.", ""]
    lines += ["", "## Audit", ""]
    a = rep["audit"]
    if a.get("present"):
        rate = a.get("wrong_rate")
        rate_s = f"{rate:.2%}" if isinstance(rate, (int, float)) else "n/a"
        lines += [f"Judge `{a['judge']}` ({a['judge_family']} family) vs extractor `{a['extractor']}` "
                  f"({a['extractor_family']} family): {a['sampled']} sampled, {a['judged']} judged, "
                  f"{a['drop']} dropped, {a['unparseable']} unparseable -> wrong rate "
                  f"**{rate_s}** (max {GATES['random_audit_wrong_max']:.0%})."]
    else:
        lines += ["Audit not run yet (`kb/state/p4c/audit.json` missing) - gate rows above fail on purpose."]
    lines += ["", "## Money and wall time", "",
              "| pass | cost USD | wall s | packs | packs/min |", "|---|---|---|---|---|"]
    for p, w in rep["wall"].items():
        w = w or {}
        lines.append(f"| `{p}` | ${rep['cost']['per_pass'].get(p, 0):.4f} | {w.get('wall_s', '-')} | "
                     f"{w.get('packs', '-')} | {w.get('rate_packs_per_min', '-')} |")
    lines += [f"| **total** | **${rep['cost']['total_usd']:.4f}** | | | |", "",
              "## Ten sampled chunks (seeded)", "",
              "| chunk | publisher | type | date | records | source path |", "|---|---|---|---|---|---|"]
    for s in rep["sample"]:
        lines.append(f"| `{s['chunk_id']}` | {s['publisher']} | {s['doc_type']} | "
                     f"{str(s['published_at'])[:10]} | {s['records']} | `{s['source_path']}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c gate report (pure post-processing)")
    ap.add_argument("--gated", nargs="*", default=None,
                    help="gated.jsonl files in ladder order; default: bulk + any esc dirs present")
    ap.add_argument("--packs", default=str(OUT / "packs.jsonl"))
    ap.add_argument("--audit", default=str(AUDIT))
    ap.add_argument("--union", default=str(UNION_GATED),
                    help="p4c_union.gated_union.jsonl; used as the final record set when present")
    ap.add_argument("--ladder-plan", default=str(LADDER_PLAN))
    ap.add_argument("--recall", default=str(RECALL))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.gated:
        paths = [Path(p) for p in args.gated]
    else:
        paths = [GATED] + [d / "gated.jsonl" for d in sorted(OUT.glob("esc*")) if (d / "gated.jsonl").exists()]
    paths = [p for p in paths if p.exists()]
    if not paths:
        raise SystemExit(f"no gated output under {OUT}: run kb/p4c_gate.py first")
    rep = build(paths, Path(args.packs), Path(args.audit), Path(args.union),
                Path(args.ladder_plan), Path(args.recall))
    if args.write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
        REPORT_MD.write_text(_md(rep), encoding="utf-8")
    print(json.dumps({"gates": {k: v["pass"] for k, v in rep["gate_results"].items()},
                      "all_pass": rep["all_pass"],
                      "failures": rep["extraction"]["failure_queue_rate"],
                      "coverage": rep["coverage"]["chunk_coverage"],
                      "cost_usd": rep["cost"]["total_usd"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
