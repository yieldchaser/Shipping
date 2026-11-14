"""P4c step 2: parse + gate the raw extraction calls into one gated record stream per chunk.

Plan §7.4/§7.5: every raw answer is kept, every record must clear gates 1-7, and a chunk whose
call produced a blank/unparseable answer, or whose records failed the quote/number/entity gates,
lands in the failure queue that P4c escalates. This module is pure post-processing: it reads the
packs written by `p4c_pack.py` and the raws the runner stored under `kb/state/raw/<pass>/`, and it
never calls a model. Same inputs -> same gated output, so it can be replayed after a crash and it
is what the gate report measures.

Call shape is identical to P4b (same `make_job`, same `key_variant`, same mode detection), so the
P4b bake-off raws and the P4c full-scope raws live in the same namespace and a P4b pack replayed
through this module produces exactly the records the bake-off scorer saw.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

from extract_gates import gate_chunk  # noqa: E402
from extract_schema import canonicalize, parse_extraction  # noqa: E402
from p4b_run import make_job  # noqa: E402  (identical job keys / prompts as P4b)
from p4c_run import load_modes  # noqa: E402  (P4c has its own transport map: p4c/modes.json)
from runner import raw_path  # noqa: E402

ROOT = KB.parent
OUT = ROOT / "kb/state/p4c"

BULK_PASS = "p4c_bulk"       # plan §10.3 bulk extraction pass
ESC_PASS = "p4c_esc"         # escalation for chunks the bulk pass could not extract
KINDS = ("state_facts", "events", "claims")


def load_packs(path: Path | None = None):
    """Yield packs from packs.jsonl one at a time (full scope is ~21k packs, ~100 MB)."""
    path = path or (OUT / "packs.jsonl")
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def published_of(pack: dict) -> dt.date | None:
    raw = (pack.get("doc") or {}).get("published_at")
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def pack_ctx(pack: dict, new_names: dict[str, str] | None = None) -> dict:
    """Gate context for one P4c pack: all blocks share the pack's document metadata."""
    published = published_of(pack)
    known = {k["id"] for k in pack.get("known") or []}
    parts = [{"chunk_id": block["cid"], "sentences": [(int(s), t) for s, t in block["sentences"]],
              "known_ids": known, "published_at": published} for block in pack["blocks"]]
    return {"chunks": parts, "known_ids": known, "new_names": dict(new_names or {})}


def raw_for(pass_name: str, model: str, mode: str, pack: dict) -> Path:
    """Path of the runner's stored raw answer for this pack (same key the runner wrote)."""
    job = make_job(pass_name, model, mode, pack)
    return raw_path(pass_name, job["job_key"])


def read_raw(path: Path) -> tuple[str | None, dict | None]:
    """Return (answer_text, usage) from a stored raw; (None, None) if absent/unreadable."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(doc, dict):
        return None, None
    resp = doc.get("response") or doc
    if not isinstance(resp, dict):
        return None, None
    choices = resp.get("choices") or (doc.get("choices") if isinstance(doc.get("choices"), list) else [])
    text = None
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        text = msg.get("content")
        if text is None:
            text = choices[0].get("text")
    if text is None:
        text = doc.get("raw") or doc.get("text")
    return (text if isinstance(text, str) else None), (resp.get("usage") or doc.get("usage"))


def gate_pack(pack: dict, pass_name: str, model: str, mode: str) -> dict:
    """Parse + gate one pack. Returns {chunks: {cid: gated_chunk}, call: {...}} for the pack."""
    out = {"pack_key": pack["key"], "doc_id": pack["doc_id"], "chunks": {},
           "call": {"parse_ok": False, "schema_fail": False, "blank": False, "missing": False,
                    "records_total": 0, "records_ok": 0, "no_content": False, "reasons": {}}}
    path = raw_for(pass_name, model, mode, pack)
    text, _usage = read_raw(path)
    call = out["call"]
    if text is None:
        # No stored raw at all: this pack has not been extracted yet (or its pass never ran).
        # Same split as `p4c_union.kept_for` L85: missing != broken. A missing pack must never
        # enter the D12 repair queue, or every not-yet-covered pack inflates it.
        call["missing"] = True
        for cid in pack["chunk_ids"]:
            out["chunks"][cid] = _empty_chunk(pack, cid, reason="missing_raw",
                                              call_failed=False, call_missing=True)
        return out
    if not text.strip():
        call["blank"] = True
        for block, cid in zip(pack["blocks"], pack["chunk_ids"]):
            out["chunks"][cid] = _empty_chunk(pack, cid, reason="blank_answer")
        return out
    ext, err = parse_extraction(text)
    if ext is None:
        call["schema_fail"] = True
        call["error"] = str(err)[:200]
        for cid in pack["chunk_ids"]:
            out["chunks"][cid] = _empty_chunk(pack, cid, reason="schema_fail")
        return out
    call["parse_ok"] = True
    ext, _new_ids, new_names = canonicalize(ext, pack.get("known") or [])
    g = gate_chunk(ext, pack_ctx(pack, new_names))
    reasons = Counter()
    for rec in g["records"]:
        for r in rec.get("reasons") or []:
            reasons[r.split(":")[0] if ":" in r else r] += 1
    call["records_total"] = g["records_total"]
    call["records_ok"] = g["records_ok"]
    call["no_content"] = bool(g.get("no_content"))
    call["reasons"] = dict(reasons)
    for block, cid in zip(pack["blocks"], pack["chunk_ids"]):
        pid = block["cid"]
        recs = [r for r in g["records"] if r.get("chunk") == pid]
        kept = {kind: [_as_dict(rec, cid) for rec in (g["kept"].get(kind) or [])
                       if getattr(rec, "chunk", None) == pid] for kind in KINDS}
        out["chunks"][cid] = {
            "chunk_id": cid, "doc_id": pack["doc_id"],
            "publisher": (pack.get("doc") or {}).get("publisher"),
            "doc_type": (pack.get("doc") or {}).get("doc_type"),
            "published_at": (pack.get("doc") or {}).get("published_at"),
            "section_class": pack.get("section_class"),
            "approx_tokens": _approx_tokens(block.get("sentences") or []),
            "no_content": bool(g.get("no_content")),
            "records_total": len(recs),
            "records_ok": sum(1 for r in recs if not r.get("dropped")),
            "gates_2_4_failed": sum(1 for r in recs if r.get("dropped")),
            "failed_pct": round(sum(1 for r in recs if r.get("dropped")) / len(recs), 6) if recs else 0.0,
            "mean_confidence": _mean_confidence(recs),
            "records": recs,
            "kept": kept,
            "new_entities_ok": dict(g.get("new_entities_ok") or {}),
            "new_names": {k: v for k, v in new_names.items() if k in (g.get("new_entities_ok") or {})},
            "reasons": [r for rec in recs for r in (rec.get("reasons") or [])],
            "call_failed": False, "call_missing": False,
        }
    return out


def _approx_tokens(sentences) -> int:
    """Cheap chunk length proxy for the plan §7.4 "long SEC MD&A chunk" trigger (chars / 4)."""
    return int(sum(len(str(t)) for _sid, t in sentences) / 4)


def _mean_confidence(records) -> float | None:
    vals = [r.get("confidence") for r in records if r.get("confidence") is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def _as_dict(rec, cid: str) -> dict:
    """Kept records come back as pydantic models; store them as plain rows under their real chunk."""
    row = rec.model_dump(mode="json") if hasattr(rec, "model_dump") else dict(rec)
    row["chunk"] = cid
    return row


def _empty_chunk(pack: dict, cid: str, reason: str, call_failed: bool = True,
                 call_missing: bool = False) -> dict:
    """A chunk row with no records. `call_failed` marks the D12 repair queue (blank / schema_fail);
    a chunk whose pass simply has no stored raw yet is `call_missing`, never `call_failed`."""
    block = next((b for b, c in zip(pack.get("blocks") or [], pack.get("chunk_ids") or [])
                  if c == cid), {})
    return {"chunk_id": cid, "doc_id": pack["doc_id"],
            "publisher": (pack.get("doc") or {}).get("publisher"),
            "doc_type": (pack.get("doc") or {}).get("doc_type"),
            "published_at": (pack.get("doc") or {}).get("published_at"),
            "section_class": pack.get("section_class"),
            "approx_tokens": _approx_tokens(block.get("sentences") or []),
            "no_content": False, "records_total": 0, "records_ok": 0, "gates_2_4_failed": 0,
            "failed_pct": 0.0, "mean_confidence": None,
            "records": [], "kept": {k: [] for k in KINDS}, "new_entities_ok": {}, "new_names": {},
            "reasons": [reason], "call_failed": bool(call_failed),
            "call_missing": bool(call_missing)}


def gate_run(pass_name: str, model: str, mode: str | None = None,
             packs_path: Path | None = None, limit: int = 0, out_dir: Path | None = None) -> dict:
    """Gate every pack of one pass. Writes gated.jsonl + failures.jsonl + gate_stats.json."""
    mode = mode or load_modes().get(model)
    if not mode:
        raise SystemExit(f"no transport mode recorded for {model}; run the transport preflight")
    out_dir = out_dir or OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    gated_p, fail_p = out_dir / "gated.jsonl", out_dir / "failures.jsonl"
    for p in (gated_p, fail_p):
        if p.exists() and p.stat().st_size:
            raise SystemExit(f"refusing to append: {p} already exists (delete it first)")
    st = {"pass": pass_name, "model": model, "mode": mode, "packs": 0, "packs_seen": 0,
          "chunks": 0, "chunk_failures": 0, "calls_blank": 0, "calls_schema_fail": 0,
          "calls_missing": 0, "chunks_missing": 0,
          "records_total": 0, "records_ok": 0, "no_content_chunks": 0,
          "reasons": Counter(), "fail_reasons": Counter()}
    with gated_p.open("a", encoding="utf-8") as gf, fail_p.open("a", encoding="utf-8") as ff:
        for pack in load_packs(packs_path):
            st["packs_seen"] += 1
            res = gate_pack(pack, pass_name, model, mode)
            call = res["call"]
            st["packs"] += 1
            st["calls_blank"] += int(call["blank"])
            st["calls_schema_fail"] += int(call["schema_fail"])
            st["calls_missing"] += int(call.get("missing", False))
            st["records_total"] += call["records_total"]
            st["records_ok"] += call["records_ok"]
            for r, n in (call["reasons"] or {}).items():
                st["reasons"][r] += n
            for cid in pack["chunk_ids"]:
                ch = res["chunks"][cid]
                st["chunks"] += 1
                st["no_content_chunks"] += int(ch["no_content"])
                st["chunks_missing"] += int(ch.get("call_missing", False))
                gf.write(json.dumps({"pack_key": res["pack_key"], **ch}, ensure_ascii=False) + "\n")
                bad = ch.get("call_failed") or ch["gates_2_4_failed"] > 0
                if bad:
                    st["chunk_failures"] += 1
                    for r in ch["reasons"]:
                        st["fail_reasons"][r.split(":")[0] if ":" in r else r] += 1
                    ff.write(json.dumps({"pack_key": res["pack_key"], "chunk_id": cid,
                                         "doc_id": ch["doc_id"], "reasons": ch["reasons"],
                                         "call_failed": bool(ch.get("call_failed")),
                                         "call_missing": bool(ch.get("call_missing")),
                                         "records_total": ch["records_total"]}, ensure_ascii=False)
                                + "\n")
            if limit and st["packs"] >= limit:
                break
    stats = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in st.items()}
    # missing packs are not answered calls: they are outside this pass' coverage, not failures.
    answered = st["packs"] - st["calls_blank"] - st["calls_schema_fail"] - st["calls_missing"]
    stats["packs_answered"] = answered
    stats["gate_pass_rate"] = round(st["packs"] and answered / st["packs"], 6)
    stats["record_drop_rate"] = round(1 - (st["records_ok"] / st["records_total"]), 6) \
        if st["records_total"] else 0.0
    stats["chunk_failure_rate"] = round(st["chunk_failures"]
                                        / max(1, st["chunks"] - st["chunks_missing"]), 6)
    stats["out"] = str(gated_p)
    (out_dir / "gate_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def cmd_gate(args) -> int:
    st = gate_run(args.pass_name or BULK_PASS, args.model, mode=args.mode,
                  packs_path=args.packs, limit=args.limit,
                  out_dir=args.out_dir)
    print("packs", st["packs"], "chunks", st["chunks"], "chunk failures", st["chunk_failures"],
          "(rate", st["chunk_failure_rate"], ")")
    print("calls blank", st["calls_blank"], "schema_fail", st["calls_schema_fail"],
          "missing", st["calls_missing"], "chunks missing", st["chunks_missing"],
          "gate pass rate", st["gate_pass_rate"], "record drop rate", st["record_drop_rate"])
    print("reasons", st["reasons"])
    print("fail reasons", st["fail_reasons"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: gate one extraction pass into gated records")
    ap.add_argument("--pass", dest="pass_name", default=BULK_PASS)
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", default=None, help="defaults to the recorded transport mode")
    ap.add_argument("--packs", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="where to write gated.jsonl/failures.jsonl; one dir per ladder rung")
    ap.add_argument("--limit", type=int, default=0)
    return cmd_gate(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
