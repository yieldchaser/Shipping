"""P4a step 5 — measure retrieval_recall_at_20 on the deterministic gold set.

Resumable: every finished query is appended to `kb/state/p4a_eval.jsonl`, so an interrupted run
continues where it stopped (keyed by qid + arm configuration). Writes `kb/reports/p4a_recall_eval.json`
with overall/per-stratum recall@k, arm coverage (gold found by BM25 only / dense only / both) and
timing, which the P4a gate report consumes.

Run: python kb/p4a_eval.py [--max N] [--no-dense] [--reset]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p4a_retrieve import Retriever  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "kb/reports/p4a_recall_set.json"
OUT = ROOT / "kb/reports/p4a_recall_eval.json"
PART = ROOT / "kb/state/p4a_eval.jsonl"
LOG = ROOT / "kb/logs/p4a_eval.log"
TOPK = (5, 10, 20)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def config_key(use_dense: bool) -> str:
    return "dense+rerank" if use_dense else "bm25"


def load_done(key: str) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not PART.exists():
        return done
    for line in PART.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("config") == key:
            done[rec["qid"]] = rec
    return done


def summarise(recs: list[dict], topk: tuple[int, ...] = TOPK) -> dict:
    """Aggregate per-query records into overall + per-stratum recall (pure, unit-tested)."""
    total = len(recs)
    per = defaultdict(list)
    for rec in recs:
        per[rec["stratum"]].append(rec)
    by_stratum: dict[str, dict] = {}
    for stratum, rows in sorted(per.items()):
        by_stratum[stratum] = {
            "n": len(rows),
            "recall": {f"at_{k}": round(sum(1 for c in rows if c["hit_at"][str(k)]) / len(rows), 3)
                       for k in topk},
            "hit_count": sum(1 for c in rows if c["hit"]),
            "misses": [c["qid"] for c in rows if not c["hit"]],
        }
        if any("fused_hit_at" in c for c in rows):
            fr = [c for c in rows if "fused_hit_at" in c]
            by_stratum[stratum]["fused_recall"] = {
                f"at_{k}": round(sum(1 for c in fr if c["fused_hit_at"][str(k)]) / len(fr), 3)
                for k in topk}
            by_stratum[stratum]["fused_hit_count"] = sum(1 for c in fr if c["fused_hit"])
    overall = {
        "n": total,
        "recall": {f"at_{k}": round(sum(1 for c in recs if c["hit_at"][str(k)]) / max(total, 1), 3)
                   for k in topk},
        "hit_count": sum(1 for c in recs if c["hit"]),
        "hit_at_20": round(sum(1 for c in recs if c["hit"]) / max(total, 1), 4),
        "gold_only_bm25": sum(1 for c in recs if c["arms"]["bm25"] and not c["arms"]["dense"]),
        "gold_only_dense": sum(1 for c in recs if c["arms"]["dense"] and not c["arms"]["bm25"]),
        "gold_both_arms": sum(1 for c in recs if c["arms"]["both"]),
        "mean_first_gold_rank": round(
            sum(c["first_gold_rank"] for c in recs if c["first_gold_rank"]) /
            max(sum(1 for c in recs if c["first_gold_rank"]), 1), 2),
        "mean_query_seconds": round(sum(c["timing"]["total_s"] for c in recs) / max(total, 1), 2),
    }
    fr = [c for c in recs if "fused_hit_at" in c]
    if fr:
        overall["fused_hit_at_20"] = round(sum(1 for c in fr if c["fused_hit"]) / len(fr), 4)
        overall["fused_recall"] = {
            f"at_{k}": round(sum(1 for c in fr if c["fused_hit_at"][str(k)]) / len(fr), 3)
            for k in topk}
        overall["rerank_rescued"] = sum(
            1 for c in fr if c["hit"] and not c["fused_hit"])
        overall["rerank_broken"] = sum(1 for c in fr if not c["hit"] and c["fused_hit"])
    return {"overall": overall, "by_stratum": by_stratum,
            "strata_counts": dict(Counter(c["stratum"] for c in recs))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--strata", nargs="*", default=None)
    ap.add_argument("--no-dense", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset and PART.exists():
        PART.unlink()
    use_dense = not args.no_dense
    key = config_key(use_dense)
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    queries = gold["queries"]
    if args.strata:
        queries = [q for q in queries if q["stratum"] in args.strata]
    if args.max:
        queries = queries[: args.max]
    done = load_done(key)
    log(f"{len(queries)} queries, config={key}, resuming with {len(done)} done")
    r = Retriever()
    started = time.time()
    try:
        for i, q in enumerate(queries, 1):
            if q["qid"] in done:
                continue
            try:
                res = r.search(q["query"], q["filters"], k=max(TOPK), use_dense=use_dense)
            except Exception as exc:  # noqa: BLE001
                log(f"FAIL {q['qid']}: {str(exc)[:120]}")
                raise
            hits = [h["chunk_id"] for h in res["hits"]]
            fused_hits = [h["chunk_id"] for h in res["fused_hits"]]
            gold_ids = {g["chunk_id"] for g in q["gold"]}
            first = next((n for n, cid in enumerate(hits, 1) if cid in gold_ids), None)
            first_fused = next((n for n, cid in enumerate(fused_hits, 1) if cid in gold_ids), None)
            bm_ids = set(res["arm_ids"]["bm25"])
            dn_ids = set(res["arm_ids"]["dense"])
            in_gold = gold_ids & (bm_ids | dn_ids)
            rec = {"qid": q["qid"], "stratum": q["stratum"], "config": key,
                   "gold_size": len(gold_ids), "first_gold_rank": first,
                   "fused_first_gold_rank": first_fused,
                   "hit": first is not None, "fused_hit": first_fused is not None,
                   "hit_at": {str(k): (first is not None and first <= k) for k in TOPK},
                   "fused_hit_at": {str(k): (first_fused is not None and first_fused <= k)
                                    for k in TOPK},
                   "arms": {"bm25": sum(1 for c in in_gold if c in bm_ids),
                            "dense": sum(1 for c in in_gold if c in dn_ids),
                            "both": sum(1 for c in in_gold if c in bm_ids and c in dn_ids)},
                   "top": [{"chunk_id": h["chunk_id"], "rrf": round(h["rrf"], 5),
                            "bm25_rank": h["bm25_rank"], "dense_rank": h["dense_rank"],
                            "rerank_lex": h["rerank_lex"]}
                           for h in res["hits"][:TOPK[-1]]],
                   "timing": res["timing"], "arm_sizes": res["arm_sizes"],
                   "query": q["query"], "filters": q["filters"]}
            with PART.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            done[q["qid"]] = rec
            if i % 20 == 0:
                cur = [done[q2["qid"]] for q2 in queries[:i] if q2["qid"] in done]
                log(f"{i}/{len(queries)} recall@20={sum(1 for c in cur if c['hit'])/max(len(cur),1):.3f}")
    finally:
        r.close()

    recs = [done[q["qid"]] for q in queries if q["qid"] in done]
    payload = {"phase": "P4a", "sample_seed": gold["sample_seed"], "config": key,
               "topk": list(TOPK), "wall_seconds": round(time.time() - started, 1),
               **summarise(recs, TOPK), "records": recs}
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    overall = payload["overall"]
    by_stratum = payload["by_stratum"]
    total = overall["n"]
    log(f"recall@20={overall['hit_at_20']} ({overall['hit_count']}/{total}) "
        f"fused_recall@20={overall.get('fused_hit_at_20')} "
        f"rescued={overall.get('rerank_rescued')} broken={overall.get('rerank_broken')} "
        f"bm25_only={overall['gold_only_bm25']} dense_only={overall['gold_only_dense']}")
    log(f"by stratum: " + json.dumps({k: v["recall"]["at_20"] for k, v in by_stratum.items()}))
    log(f"fused by stratum: "
        + json.dumps({k: v.get("fused_recall", {}).get("at_20") for k, v in by_stratum.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
