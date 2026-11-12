"""P4c recall measurement on the frozen 120-chunk gold set (C1 owner decision 2 and 4).

DESIGN NOTE
The owner asked for a recall gain measurement after the cleaning/gleaning pass and for the second
extractor, so P4c needs one scorer that answers "did this source surface more of the reference facts
on the gold chunks than the P4b candidate did?". Inputs are all local and free: the 120 gold items
(`kb/state/gold/p4b_items.json`), the pack that owns each gold chunk (so the scorer re-gates stored
raws exactly like the extraction saw them), and the reference records rebuilt from the stored
`p4b_ref` raws via `p4b_run.build_reference` (two-model agreement + adjudicated keeps). A candidate
record matches a reference record with the P4b identity+evidence rule (`records_match`), so the
baseline number stays directly comparable with the P4b bake-off recall (0.5362 for Ultrafast).
Recall is the C1 metric here; precision is the separate random audit (`p4c_audit.py`) plus the
optimistic `matched/candidates` ratio reported alongside so an inflated recall cannot hide behind
lower precision. One source row per pass:model plus a `union` row over all sources, which is what
P4c actually publishes. Recall gain is reported against the replayed `p4b_cand` baseline, and in
absolute points against the P4b report value.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4b_run as B  # noqa: E402
import p4c_union as U  # noqa: E402

STATE = KB / "state"
GOLD = STATE / "gold"
ITEMS = GOLD / "p4b_items.json"
PACKS = STATE / "p4c" / "packs.jsonl"
OUT = STATE / "p4c" / "recall.json"
AUDIT_SAMPLE = 10
KINDS = U.KINDS
DEFAULT_SOURCES = [("p4b_cand", "deepseek-v4.1-flash-1017-ultrafast"),
                   ("p4c_bulk", "deepseek-v4.1-flash-1017-ultrafast"),
                   ("p4c_glean", "deepseek-v4.1-flash-1017-ultrafast"),
                   ("p4c_bulk_retry", "deepseek-v4.1-flash-1017-ultrafast"),
                   ("p4c_esc", "glm-5.3"),
                   ("p4c_glm2", "glm-5.3")]


def chunk_index(items: list[dict], packs_path: Path = PACKS) -> dict:
    """{chunk_id: pack row} for the gold chunks only - one streaming pass over the pack file."""
    want = {it["chunk_id"] for it in items}
    found: dict[str, dict] = {}
    with packs_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            for cid in pack["chunk_ids"]:
                if cid in want:
                    found[cid] = pack
            if len(found) == len(want):
                break
    return found


def pack_sentences(pack: dict, cid: str) -> list[tuple[int, str]]:
    """[(sid, text)] of one DB chunk inside its pack block."""
    idx = pack["chunk_ids"].index(cid)
    return [(int(s), t) for s, t in pack["blocks"][idx]["sentences"]]


def item_rows(kept: dict, cid: str, sents: list[tuple[int, str]], source: str) -> list[dict]:
    """Flatten one chunk of `p4c_union.kept_for` output to score rows."""
    rows = []
    for kind in KINDS:
        for rec in kept["chunks"].get(cid, {}).get(kind) or []:
            rows.append(U.record_row(kind, rec, sents, source))
    return rows


def flat_candidates(rows: list[dict]) -> list[tuple]:
    """[(sig, quote, kind, row)] - the tuple shape `records_match`/`match_lists` expect."""
    return [(U.sig_of(r), r.get("quote", ""), r["record_kind"], r) for r in rows]


def score(chunk_candidates: dict, reference: dict) -> dict:
    """Recall/precision/F1 of {chunk_id: [cand tuples]} against the rebuilt reference set.

    `reference` is `p4b_run.build_reference` output: {chunk_id: {"records": [...]}}. Recall counts
    matched reference records over all reference records; `precision_optimistic` is
    matched/candidates (no third-family adjudication of the unmatched ones, so it is a lower bound
    on wrongness and is reported as such).
    """
    tp = cand_n = ref_n = 0
    per_chunk = []
    for cid, cand in chunk_candidates.items():
        ref = [(u["sig"], u["quote"], u["kind"], u["rec"])
               for u in reference.get(cid, {}).get("records", [])]
        matched, _unmatched = B.match_lists(cand, ref)
        tp += matched
        cand_n += len(cand)
        ref_n += len(ref)
        per_chunk.append({"chunk_id": cid, "candidates": len(cand), "reference": len(ref),
                          "matched": matched,
                          "recall": round(matched / len(ref), 4) if ref else None})
    recall = tp / ref_n if ref_n else 0.0
    precision = tp / cand_n if cand_n else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"candidates": cand_n, "reference": ref_n, "matched": tp,
            "recall": round(recall, 4), "precision_optimistic": round(precision, 4),
            "f1_optimistic": round(f1, 4), "per_chunk": per_chunk}


def source_candidates(pack: dict, cid: str, pass_name: str, model: str) -> list[tuple]:
    """Kept records of one stored pass:model p4c raw for one chunk, re-gated, as scoring tuples."""
    got = U.kept_for(pack, pass_name, model)
    sents = pack_sentences(pack, cid)
    return flat_candidates(item_rows(got, cid, sents, pass_name))


def p4b_candidates(items: list[dict], pass_name: str, model: str) -> dict:
    """Kept records of a stored P4b raw per gold chunk.

    P4b ran one chunk per pack (`p4b_items.json` -> its own packs), so its raw job keys never match
    P4c packs; the baseline is therefore replayed through `p4b_run.evaluate`, which rebuilds the P4b
    packs from the same items and gates the raws exactly as the report did.
    """
    ev = B.evaluate(pass_name, model, items)
    out = {}
    for it in items:
        cid = it["chunk_id"]
        sents = [(int(s), t) for s, t in it["sentences"]]
        g = ev["chunks"].get(cid)
        out[cid] = B.flat_records(g, sents) if g else []
    return out, ev


def cand_adjudication() -> dict:
    """{(model, chunk_id, idx): keep|drop} of the P4b candidate adjudication, if it exists."""
    path = B.STATE / "adjudication.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8")).get("candidate_items", [])
    return {(d["meta"]["model"], d["meta"]["chunk_id"], d["meta"]["idx"]): d["decision"]
            for d in items}


def union_candidates(pack: dict, cid: str, sources: list[tuple]) -> list[tuple]:
    """Merged (deduped) records of all sources for one chunk, as scoring tuples."""
    res = U.union_pack(pack, sources)
    rows = [r for r in res["rows"] if r["chunk_id"] == cid]
    if not rows:
        return []
    row = rows[0]
    flat = []
    for kind in KINDS:
        for rec in row["kept"].get(kind) or []:
            flat.append((U.sig_of(rec), rec["quote"], rec["record_kind"], rec))
    return flat


def measure(items: list[dict], packs: dict, reference: dict, sources: list[tuple]) -> dict:
    """Every source plus the union, all scored on the same items/reference."""
    out = {"sources": [], "per_chunk_source": {}}
    c_adj = cand_adjudication()
    for pass_name, model in sources:
        replay = None
        if pass_name.startswith("p4b_"):
            cand, ev = p4b_candidates(items, pass_name, model)
            replay = B.score_model(items, ev, reference,
                                  c_adj if pass_name.startswith("p4b_cand") else None)
        else:
            cand = {}
            for it in items:
                cid = it["chunk_id"]
                pack = packs.get(cid)
                if pack is None:
                    cand[cid] = []
                    continue
                cand[cid] = source_candidates(pack, cid, pass_name, model)
        sc = score(cand, reference)
        sc.pop("per_chunk", None)
        sc.update({"pass": pass_name, "model": model})
        if replay is not None:
            # P4b-style recall counts adjudicator-kept candidate records found by no reference model
            # as true positives in both numerator and denominator, so it is not comparable with the
            # strict per-source recall; carried only to prove the replay reproduces the P4b report.
            sc["p4b_style_recall"] = replay.get("recall")
            sc["p4b_style_precision"] = replay.get("precision")
        out["sources"].append(sc)
        out["per_chunk_source"][f"{pass_name}:{model}"] = {
            cid: len(v) for cid, v in cand.items()}
    # the union can only merge P4c raws (P4b raws are keyed to P4b packs), so the baseline is reported
    # as its own source row and the union row covers the P4c ladder sources only
    p4c_sources = [(p, m) for p, m in sources if not p.startswith("p4b_")]
    union_cand = {}
    for it in items:
        cid = it["chunk_id"]
        pack = packs.get(cid)
        union_cand[cid] = union_candidates(pack, cid, p4c_sources) if pack else []
    sc = score(union_cand, reference)
    sc.pop("per_chunk", None)
    sc.update({"pass": "union", "model": "+".join(sorted({m for _p, m in p4c_sources}))})
    out["union"] = sc
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: gold-set recall per source and for the union")
    ap.add_argument("--items", default=str(ITEMS))
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--sources", default="", help="pass:model,... (default: the P4c ladder)")
    args = ap.parse_args()
    items = json.loads(Path(args.items).read_text(encoding="utf-8"))
    sources = U.parse_sources(args.sources) if args.sources else DEFAULT_SOURCES
    packs = chunk_index(items, Path(args.packs))
    missing = [it["chunk_id"] for it in items if it["chunk_id"] not in packs]
    reference = B.build_reference(items)
    res = measure(items, packs, reference, sources)
    base = next((s for s in res["sources"] if s["pass"] == "p4b_cand"), None)
    p4b_report = KB / "reports" / "p4b.json"
    p4b_recall = None
    if p4b_report.exists():
        p4b_recall = json.loads(p4b_report.read_text(encoding="utf-8")).get(
            "selected", {}).get("recall")
    payload = {
        "gold_items": len(items),
        "gold_chunks_found_in_packs": len(items) - len(missing),
        "missing_chunks": missing[:AUDIT_SAMPLE],
        "reference_records": sum(len(v.get("records", [])) for v in reference.values()),
        "sources": res["sources"],
        "union": res["union"],
        "baseline_replayed_p4b_cand_recall": base["recall"] if base else None,
        "baseline_p4b_style_recall": (base or {}).get("p4b_style_recall"),
        "p4b_report_recall": p4b_recall,
    }
    if base:
        payload["recall_gain_vs_replayed_baseline"] = round(res["union"]["recall"] - base["recall"], 4)
    if p4b_recall:
        payload["recall_gain_vs_p4b_report"] = round(res["union"]["recall"] - p4b_recall, 4)
    Path(args.out).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    for s in res["sources"]:
        print(f"{s['pass']}:{s['model']} recall {s['recall']:.4f} cand {s['candidates']} "
              f"ref {s['reference']} matched {s['matched']}")
    u = res["union"]
    print(f"union recall {u['recall']:.4f} cand {u['candidates']} matched {u['matched']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
