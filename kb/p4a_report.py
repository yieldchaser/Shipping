"""P4a gate report — retrieval_recall_at_20 against kb/gates.yaml (threshold 0.85).

Consumes: kb/reports/p4a_index.json (FTS5 build), p4a_embed.json (dense vectors),
p4a_embed_link.json (chunk.vec_row linking), p4a_recall_set.json (gold questions),
p4a_recall_eval.json (measured recall). Emits the gate artefacts kb/reports/p4a.json and
kb/reports/p4a.md, including 10 deterministically sampled queries with their source paths.

Run: python kb/p4a_report.py
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kb"))
import money as M  # noqa: E402
REPORTS = ROOT / "kb/reports"
GATES = ROOT / "kb/gates.yaml"
METRIC = "retrieval_recall_at_20"
SAMPLE_N = 10


def load(name: str) -> dict:
    path = REPORTS / name
    if not path.exists():
        raise SystemExit(f"missing input report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def pick_samples(queries: list[dict], eval_by_qid: dict[str, dict], rng: random.Random,
                 n: int = SAMPLE_N) -> list[dict]:
    """Stratified deterministic sample: spread across strata, keep hits and misses visible."""
    by_stratum: dict[str, list[dict]] = {}
    for q in queries:
        rec = eval_by_qid.get(q["qid"])
        if rec:
            by_stratum.setdefault(q["stratum"], []).append({**q, "recall": rec})
    picks: list[dict] = []
    strata = sorted(by_stratum)
    i = 0
    while len(picks) < n and any(by_stratum[s] for s in strata):
        stratum = strata[i % len(strata)]
        pool = by_stratum[stratum]
        if pool:
            picks.append(pool.pop(rng.randrange(len(pool))))
        i += 1
    return picks


def money_total(*sources: dict) -> float | None:
    """Sum `money_spent_usd` across the P4a producer reports, tri-state.

    Defect 19/17 class: `x.get("money_spent_usd", 0.0)` reports a measured `$0.00` when a producer
    never wrote the key at all — an absent measurement rendered as a spend. A key present with `0.0`
    is a writer-declared zero (p4a_embed: NIM free tier) and must stay `0.0`. Any source missing the
    key makes the whole total `UNMEASURED`; it must never be silently dropped from the sum.

    Defect 35 (limb 3): the present-value branch was a bare `float(v)`, so a corrupted producer value
    (`"abc"`, `null`-adjacent junk, a 401-digit literal) raised out of the report instead of reading
    as the unmeasured spend it is. Each reading goes through `money.as_float`; unreadable -> `None`.
    """
    total: float | None = 0.0
    for src in sources:
        if "money_spent_usd" not in src:
            return None
        f = M.as_float(src.get("money_spent_usd"))
        if f is None:
            return None
        if total is not None:
            total += f
    return total


def recall_rate(value) -> float | None:
    """Read a measured `[0, 1]` recall ratio out of the on-disk eval artefact.

    Defect 31, Defect 24/26 class: `round(float(overall["hit_at_20"]), 4)` reads the gate operand
    straight out of `p4a_recall_eval.json`, and `float()` is not a guard — a 401-digit literal, or a
    JSON `1e999`, becomes `inf`, and `inf >= 0.85` is True. The P4a gate then printed `PASSED`,
    stored `verdict: "PASSED"` and exited 0 on a measurement it could not read. A recall ratio *is* a
    `[0, 1]` score, so the single-sourced scale rule applies (`money.unit_score`); an unreadable or
    off-scale operand is UNMEASURED (`None`) and the verdict must fail closed.
    """
    return M.unit_score(value)


def gate_verdict(hit: float | None, threshold: float | None) -> str:
    """The P4a gate rule. UNMEASURED is never a pass — `None >= threshold` would raise, and any
    truthiness fallback (`hit or 0.0`, `float(hit)`) re-admits the fabrication this module fixes.

    Defect 26 pattern: the guard sits at the *verdict* as well as at the artefact reader. Both
    operands are re-read through the one implementation of each rule — `money.unit_score` for the
    `[0, 1]` recall ratio, `money.as_float` for the authored gate threshold — so a caller that
    reaches this function without going through `recall_rate` still cannot PASS on a broken read.
    Unreadable ⇒ `FAILED`: no verdict this module cannot compute is ever reported as a pass.
    """
    h = M.unit_score(hit)
    th = M.as_float(threshold)
    if h is None or th is None:
        return "FAILED"
    return "PASSED" if h >= th else "FAILED"


def _r(v: float | None) -> str:
    """A reported-not-gated measurement: `n/a` when unreadable, never `None` and never `inf`.

    Defect 35 (limb 3): the old body tested `v is None` only, so a non-finite read (`inf` from an
    overflowed byte/seconds division) rendered the literal text `inf` into p4a.md where a human reads
    a timing. Read through the single-sourced guard instead: unmeasured -> `n/a`, a real read renders.
    """
    return "n/a" if M.as_float(v) is None else f"{v}"


def _wall_total(*readings) -> float | None:
    """Sum the phase wall-clock readings; unreadable readings contribute nothing, all-unreadable -> None.

    Defect 35 (limb 3): the old body was `round(float(a.get("wall_seconds", 0.0)) + float(...) + ...)`.
    `float()` raised `ValueError` on a corrupted string reading (killing the report before the artefact
    was written) and passed `float("1" + "0"*400)` -> `inf` straight through, so `json.dumps` emitted
    the non-standard `Infinity` token and made `p4a.json` unparseable. Each reading goes through
    `money.as_float`, so a broken reading is unavailable, never a fabricated number and never a raise.
    `None` only when *no* producer wrote a readable timing -- otherwise this is a partial total of the
    readings that do exist.
    """
    total = None
    for r in readings:
        f = M.as_float(r)
        if f is not None:
            total = f if total is None else total + f
    return None if total is None else round(total, 1)


def _json_safe(obj):
    """A report tree safe to `json.dumps`: a non-finite float is unmeasured (`null`), never `Infinity`.

    Defect 35 (limb 3): `json.dumps(records)` emits native `Infinity`/`NaN` tokens for a non-finite
    float, which no strict JSON reader accepts. Shared guard, same shape as `p7_report._json_safe`.
    """
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and M.as_float(obj) is None:
        return None
    return obj


def main() -> int:
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))
    # Defect 31 sibling: the threshold is an authored gate operand read out of the frozen gates file
    # through a bare `float()`. Unreadable -> `None`, and `gate_verdict` then fails closed, so P4a
    # can never PASS on a threshold nobody could read.
    threshold = M.as_float(gates["P4a"][METRIC])
    gold = load("p4a_recall_set.json")
    evaluation = load("p4a_recall_eval.json")
    index = load("p4a_index.json")
    embed = load("p4a_embed.json")
    link = load("p4a_embed_link.json") if (REPORTS / "p4a_embed_link.json").exists() else {}

    seed = int(gold["sample_seed"])
    assert seed == int(evaluation["sample_seed"]), "gold set and eval disagree on seed"
    queries = gold["queries"]
    eval_by_qid = {r["qid"]: r for r in evaluation.get("records", [])}
    if not eval_by_qid:
        raise SystemExit("p4a_recall_eval.json has no per-query records; rerun kb/p4a_eval.py")

    rng = random.Random(seed)
    samples = pick_samples(queries, eval_by_qid, rng)
    sample_records = []
    for s in samples:
        rec = s["recall"]
        top1 = rec["top"][0] if rec["top"] else {}
        gold0 = s["gold"][0]
        sample_records.append({
            "qid": s["qid"], "stratum": s["stratum"], "query": s["query"],
            "filters": s["filters"], "gold_size": rec["gold_size"],
            "hit_at": rec["first_gold_rank"], "hit": rec["hit"],
            "fused_hit_at": rec.get("fused_first_gold_rank"),
            "fused_hit": rec.get("fused_hit"),
            "gold_source_path": gold0["path"], "gold_chunk_id": gold0["chunk_id"],
            "top1_chunk_id": top1.get("chunk_id"), "top1_bm25_rank": top1.get("bm25_rank"),
            "top1_dense_rank": top1.get("dense_rank"),
            "top1_rerank_lex": top1.get("rerank_lex"),
            "arms": rec["arms"],
        })

    overall = evaluation["overall"]
    # Defect 31: both gate operands are on-disk numbers; read them through the one ratio rule and
    # fail the verdict closed when the read is broken (see `recall_rate`/`gate_verdict`).
    metric_raw = recall_rate(overall.get("hit_at_20"))
    fused_raw = recall_rate(overall.get("fused_hit_at_20"))
    metric_value = None if metric_raw is None else round(metric_raw, 4)
    fused_value = None if fused_raw is None else round(fused_raw, 4)
    verdict = gate_verdict(metric_value, threshold)
    gold_by_stratum: dict[str, list[int]] = {}
    for q in queries:
        gold_by_stratum.setdefault(q["stratum"], []).append(len(q["gold"]))
    mean_gold = {s: round(sum(v) / len(v), 2) for s, v in gold_by_stratum.items()}
    # Defect 19/17 class: `float(x.get("money_spent_usd", 0.0))` would report a measured `$0.00` when
    # a producer never wrote the key at all — an absent measurement rendered as a spend. A key that
    # *is* present with `0.0` is a writer-declared zero (p4a_embed: NIM free tier) and stays `0.0`.
    money = money_total(embed, index)
    eval_records = evaluation.get("records", [])
    mean_rerank_s = round(sum(c["timing"].get("rerank_s", 0.0) for c in eval_records) /
                          max(len(eval_records), 1), 3)
    # Defect 35 (limb 3): bare `float(a.get(k, 0.0)) + ...` raised on a corrupted reading and let a
    # non-finite one through to `json.dumps` (native `Infinity` token, unparseable p4a.json). The
    # readings delegate to `money.as_float`; an unavailable one contributes nothing.
    wall = _wall_total(embed.get("wall_seconds"), evaluation.get("wall_seconds"),
                       index.get("build_seconds", index.get("wall_seconds")))
    records = {
        "phase": "P4a",
        "sample_seed": seed,
        METRIC: metric_value,
        "threshold": threshold,
        "recall_at_5": recall_rate(overall["recall"]["at_5"]),
        "recall_at_10": recall_rate(overall["recall"]["at_10"]),
        "recall_at_20": recall_rate(overall["recall"]["at_20"]),
        "fused_recall_at_20": fused_value,
        "fused_recall_at_5": recall_rate(overall.get("fused_recall", {}).get("at_5")),
        "fused_recall_at_10": recall_rate(overall.get("fused_recall", {}).get("at_10")),
        "rerank_rescued": overall.get("rerank_rescued"),
        "rerank_broken": overall.get("rerank_broken"),
        "repair_history": [
            {"step": "as first measured", "recall_at_20": 0.715,
             "defect": "section labels pinned one week of a month-recurring heading; numeric "
                       "questions rendered from raw internal tokens; arm coverage computed on the "
                       "fused head instead of the 150-candidate arms"},
            {"step": "after label + question-text repair, gold capped at 20", "recall_at_20": 0.695,
             "defect": "cap created false negatives for strata whose answer set is larger "
                       "(company/vessel questions have 13-288 correct chunks)"},
            {"step": "gold uncapped, pre-rerank (fused top-20)", "recall_at_20": fused_value,
             "defect": "RRF dilution: gold found only by BM25 lands at fused rank 21-132"},
            {"step": "after §5.5 rerank stage (this gate)", "recall_at_20": metric_value,
             "defect": "none — rerank stage from plan §5.5 step 4, implemented deterministically"},
        ],
        "queries_total": overall["n"],
        "hits_total": overall["hit_count"],
        "by_stratum": evaluation["by_stratum"],
        "arm_coverage": {"gold_only_bm25": overall["gold_only_bm25"],
                         "gold_only_dense": overall["gold_only_dense"],
                         "gold_both_arms": overall["gold_both_arms"]},
        "mean_first_gold_rank": overall["mean_first_gold_rank"],
        "mean_query_seconds": overall["mean_query_seconds"],
        "recall_set": {"mean_gold_chunks_by_stratum": mean_gold,
                       "label_fix": "section_lookup gold = every same-heading section of the "
                                    "publisher's docs in the asked month; numeric_series questions "
                                    "rendered from expanded series vocabulary; no cap on gold size"},
        "retrieval_config": {"bm25_top_k": 150, "dense_top_k": 150, "rrf_k": 60,
                             "rerank_window": 40, "rerank": "deterministic lexical-overlap reranker "
                                                            "(plan 5.5 step 4 substitute, D9)",
                             "eval_top_k": 20,
                             "gate_measured_on": "reranked top-20; fused-only number reported too"},
        "rerank_detail": {"window": 40,
                          "score": "query content tokens found (1 each) + adjacent-token bigrams "
                                   "found (2 each) over context_prefix + body; RRF score is the "
                                   "tie-break; no candidate outside the fused top 40 can enter",
                          "mean_rerank_seconds": mean_rerank_s},
        "index": {"chunks_indexed": index.get("chunks_indexed") or index.get("chunks"),
                  "build_seconds": index.get("build_seconds"),
                  "db_file_bytes": index.get("db_file_bytes"),
                  "probe_latency_s": (round(sum(p["seconds"] for p in index["probes"]) /
                                             max(len(index.get("probes") or [1]), 1), 2)
                                      if index.get("probes") else None)},
        "embedding": {"model": embed.get("model"), "dims": embed.get("dims"),
                      "rows": embed.get("rows"), "requests": embed.get("requests_total"),
                      "tokens": embed.get("tokens_total"), "wall_seconds": embed.get("wall_seconds"),
                      "rows_per_second": embed.get("rows_per_second")},
        "link": link,
        "samples": sample_records,
        "money_spent_usd": money,
        "wall_seconds": wall,
        "verdict": verdict,
    }
    # Defect 35 (limb 3): `json.dumps(records)` writes native `Infinity`/`NaN` tokens for a non-finite
    # float, which no strict JSON reader accepts; sanitise before the artefact hits disk.
    (REPORTS / "p4a.json").write_text(json.dumps(_json_safe(records), indent=1), encoding="utf-8")

    lines = [
        "# P4a — retrieval layer (plan §5.2–§5.5)",
        "",
        "Design note: P4a builds layer B of the plan — 318,232 chunks are indexed in DuckDB FTS5",
        "(BM25 over `body` **and** `context_prefix`, because §5.3 makes the prefix part of the",
        "retrieval unit and section-lookup questions are only findable through it) and every",
        "distinct chunk text (220,150 after `norm_sha` dedup) gets one unit-norm 2048-d",
        "`nemotron-3-embed-1b` vector in an fp16 memmap, so a query runs filters → BM25 top150",
        "+ dense top150 → RRF(k=60) → §5.5 rerank of the fused top 40 → top20. `ARM_K=150`,",
        "`RRF_K=60`, the window and the rerank scoring rule were fixed before this measurement run,",
        "and the report prints both the fused-only and the reranked recall, because the two differ.",
        "The gold questions are generated mechanically (vessel/company entity ids, unique printed",
        "cells, section headings) with `seed_for(\"P4a\")`, so labels are exact chunk ids and a rerun",
        "on the same KB reproduces the same 200 questions. The full 250-question Q&A gold set",
        "(§12.1) is built after P4a and reuses these strata.",
        "Measurement-set repair: the first run scored 0.715 and the misses were traced to four",
        "faults in the *question set*, not the retriever, and were fixed before this measurement.",
        "(a) `section_lookup` labels marked the one week a heading was sampled from as the only",
        "correct answer although the same heading repeats in every report of that month, so a",
        "correct hit in a sibling week counted as a miss — gold is now every chunk of that heading",
        "for that publisher in the asked month (38/50 questions span more than one document).",
        "(b) `numeric_series` questions were rendered from raw internal tokens (`change_wow`,",
        "`m_minus_1`, `1-Oct-21 vector_estimate`), which no analyst would type and which embed",
        "badly — they now read in report spelling, e.g. \"the IOPi65 Eq USD DMT for 1-Oct-21 vector",
        "estimate in the Metals Market Index (MMi) daily report published 05 August 2024\"; labels",
        "are unchanged (the unique printed cell of that document). (c) the arm-coverage statistic",
        "was computed on the fused top-20 instead of the 150-candidate arms, so `gold_only_*` read",
        "0 for a structural reason; it is now computed from the arms. (d) gold was capped at 20",
        "labels per question, which made a correct answer a false negative whenever the same fact is",
        "printed in more than 20 chunks (company/vessel strata run to 150-288 correct chunks); the",
        "cap is removed and gold now lists every correct chunk. `ARM_K`, `RRF_K`, filters, rankers",
        "and thresholds were not touched by any repair: 0.715 (first run) → 0.695 (capped, repaired",
        f"labels) → 0.815 (uncapped, pre-rerank) → {metric_value} (this gate, with §5.5 rerank).",
        "Deviations: (D4) local-CPU embedding (Qwen3-Embedding-0.6B) was infeasible here — >100 h",
        "for 220 k chunks on this 8 GB i3 — so the free NIM `nemotron-3-embed-1b` endpoint is used;",
        "(D5) NIM exposes no rerank model (`/v1/models` serves embeddings and reward models only), so",
        "the plan's `bge-reranker-v2-m3` cross-encoder cannot be called; (D9) the §5.5 rerank stage is",
        "therefore a deterministic lexical reranker over the same top-40 window — it scores each",
        "candidate by how much of the question it contains (content tokens, plus adjacent-token",
        "bigrams at double weight) over `context_prefix + body`, breaks ties on the RRF score, and can",
        f"only reorder the fused head (it moved {overall.get('rerank_rescued')} queries from miss to hit and",
        f"{overall.get('rerank_broken')} from hit to miss); it costs"
        f" {mean_rerank_s} s per query and adds no LLM call; (D7) dense scoring batches vectors 4,000",
        "rows at a time instead of 20,000 after a 156 MiB numpy allocation failed on this machine's",
        "free RAM — identical arithmetic, smaller peak allocation, no effect on ranking.",
        "",
        f"Gate: `{METRIC}` = **{_r(metric_value)}** (threshold {threshold}) → **{verdict}**",
        "",
        f"- questions: {overall['n']} · hits@20: {overall['hit_count']}"
        f" · recall@5/10/20: {_r(recall_rate(overall.get('recall', {}).get('at_5')))}"
        f"/{_r(recall_rate(overall.get('recall', {}).get('at_10')))}"
        f"/{_r(recall_rate(overall.get('recall', {}).get('at_20')))}"
        f" · same but pre-rerank (fused only): {_r(fused_value)}",
        f"- rerank stage: window 40, rescued {overall.get('rerank_rescued')},"
        f" broke {overall.get('rerank_broken')}, {mean_rerank_s} s/query",
        f"- arm coverage: gold found by BM25 only {overall['gold_only_bm25']},"
        f" dense only {overall['gold_only_dense']}, both {overall['gold_both_arms']}",
        f"- mean first-gold rank {overall['mean_first_gold_rank']}"
        f" · mean query {overall['mean_query_seconds']} s",
        f"- FTS index: {records['index']['chunks_indexed']} chunks in"
        f" {records['index']['build_seconds']} s, warm probe latency"
        f" {records['index']['probe_latency_s']} s, DB file"
        # Defect 35 (limb 3): the size is read from an on-disk artefact, so it goes through the same
        # guard -- an unreadable byte count renders `n/a`, never `inf` GB and never `0.00` GB.
        f" {_r(round((M.as_float(records['index'].get('db_file_bytes')) or 0.0) / 1e9, 2))} GB",
        f"- vectors: {embed.get('rows')} rows × {embed.get('dims')} d, {embed.get('model')},"
        f" {embed.get('requests_total')} requests, {embed.get('tokens_total')} tokens, $0 (NIM free tier)",
        f"- spend {M.fmt_usd(money)} · wall {_r(wall)} s",
        "",
        "## Per stratum",
        "",
        "| stratum | n | recall@5 | recall@10 | recall@20 | fused recall@20 (pre-rerank) |",
        "|---|---|---|---|---|---|",
    ]
    for name, row in evaluation["by_stratum"].items():
        fused_cell = recall_rate(row.get("fused_recall", {}).get("at_20"))
        lines.append(f"| {name} | {row['n']}"
                     f" | {_r(recall_rate(row.get('recall', {}).get('at_5')))}"
                     f" | {_r(recall_rate(row.get('recall', {}).get('at_10')))}"
                     f" | {_r(recall_rate(row.get('recall', {}).get('at_20')))}"
                     f" | {_r(fused_cell)} |")
    lines += ["", "## Repair history", "",
              "| measurement | recall@20 | what was wrong |", "|---|---|---|"]
    for h in records["repair_history"]:
        lines.append(f"| {h['step']} | {_r(recall_rate(h['recall_at_20']))} | {h['defect']} |")
    lines += ["", "## Sampled records", ""]
    for s in sample_records:
        mark = "hit" if s["hit"] else "MISS"
        rank = s["hit_at"] if s["hit_at"] else "-"
        lines.append(f"### {s['qid']} · {s['stratum']} · {mark} @ {rank}")
        lines.append(f"- Q: {s['query']}")
        lines.append(f"- filters: `{json.dumps(s['filters'])}`")
        lines.append(f"- gold ({s['gold_size']}): `{s['gold_source_path']}` chunk `{s['gold_chunk_id']}`")
        fused_mark = (f"fused rank {s['fused_hit_at']}" if s["fused_hit"]
                      else "not in fused top-20")
        lines.append(f"- {fused_mark} → reranked rank {rank}")
        lines.append(f"- top1: `{s['top1_chunk_id']}` (bm25 rank {s['top1_bm25_rank']},"
                     f" dense rank {s['top1_dense_rank']}, rerank lex"
                     f" {s['top1_rerank_lex']}); arms hit bm25/dense {s['arms']['bm25']}/{s['arms']['dense']}")
        lines.append("")
    (REPORTS / "p4a.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"P4a {verdict}: {METRIC}={_r(metric_value)} ({overall['hit_count']}/{overall['n']})"
          f" wall {_r(wall)}s samples {len(sample_records)}")
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
