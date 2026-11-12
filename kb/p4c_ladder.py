"""P4c escalation ladder: rule-6 failure queue, free single-chunk retry, capped glm-5.3 escalation.

DESIGN NOTE
Plan §7.4 rule 6 escalates a chunk when (a) more than 30% of its records failed gates 2-4, (b) the
mean record confidence is below 0.5, or (c) it is a long SEC MD&A-class chunk whose kept-record
count is under half the pilot median for its section type. This module implements that test over the
gated bulk output, puts every firing chunk through the free Ultrafast single-chunk retry rung first
(one free retry, per owner decision 3), and only then spends money. The paid rung is glm-5.3
(owner decision 3: nemotron is excluded from extraction escalation) inside the booked $17 cap,
ordered by document value exactly as the bulk high-value selection is ordered (gold chunks, SEC
MD&A/fleet, broker forecasts, fixtures/TC, S&P, rest) so a capped rung buys the most valuable
chunks first and reports the remainder as declared partial coverage (D12). Chunk length, failure
percentage and confidence are supplied by `p4c_gate`, which is the only writer of `gated.jsonl`.
Cost per single-chunk call uses the same ledger-fitted glm-5.3 tariff as the second-extractor
selection (`p4c_highvalue.est_cost`) with no cache credit, so the plan cannot quietly overrun.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4c_highvalue as HV  # noqa: E402
import p4c_run as R  # noqa: E402

STATE = KB / "state"
OUT = STATE / "p4c"
GATED = OUT / "gated.jsonl"
PACKS = OUT / "packs.jsonl"
PLAN = OUT / "ladder_plan.json"
RETRY_PACKS = OUT / "singles_retry.jsonl"
ESC_PACKS = OUT / "singles_esc.jsonl"

RETRY_PASS = "p4c_bulk_retry"
ESC_PASS = "p4c_esc"
ESC_MODEL = "glm-5.3"
ESC_CAP_USD = 17.0

FAIL_PCT_MAX = 0.30
CONF_MIN = 0.5
LONG_TOKENS = 600
THIN_FRAC = 0.5


def load_gated(path: Path = GATED):
    """Stream the per-chunk gate rows of one gated pass (one JSON object per chunk)."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if "chunk_id" in row:
                    yield row
                else:  # pack-level row: flatten its chunk map
                    yield from (row.get("chunks") or {}).values()


def gated_chunk_map(path: Path | None = None, paths=()) -> dict[str, dict]:
    """{chunk_id: gate row}, later passed wins (retry/escalation rungs override the bulk row)."""
    out: dict[str, dict] = {}
    for p in paths:
        for row in load_gated(Path(p)):
            out[row["chunk_id"]] = row
    if path is not None:
        for row in load_gated(Path(path)):
            out[row["chunk_id"]] = row
    return out


def section_medians(rows) -> dict[str, float]:
    """Pilot median kept-record count for long chunks, per doc_type/section class (rule 6c)."""
    buckets: dict[str, list[int]] = {}
    for row in rows:
        if int(row.get("approx_tokens") or 0) < LONG_TOKENS:
            continue
        key = f"{row.get('doc_type') or '?'}/{row.get('section_class') or '?'}"
        buckets.setdefault(key, []).append(int(row.get("records_ok") or 0))
    return {k: float(statistics.median(v)) for k, v in buckets.items() if v}


def triggers(row: dict, medians: dict[str, float]) -> list[str]:
    """Rule 6 sub-triggers for one gated chunk row (empty list = no escalation)."""
    out: list[str] = []
    total = int(row.get("records_total") or 0)
    if total and float(row.get("failed_pct") or 0.0) > FAIL_PCT_MAX:
        out.append("fail_pct")
    conf = row.get("mean_confidence")
    if total and conf is not None and float(conf) < CONF_MIN:
        out.append("low_confidence")
    dtype = (row.get("doc_type") or "").lower()
    if dtype.startswith("sec") and int(row.get("approx_tokens") or 0) >= LONG_TOKENS:
        key = f"{row.get('doc_type') or '?'}/{row.get('section_class') or '?'}"
        med = medians.get(key)
        if med and int(row.get("records_ok") or 0) < THIN_FRAC * med:
            out.append("thin_long_sec")
    return out


def build_queue(rows) -> dict:
    """Rule-6 queue over all gated chunks: ordered list of {chunk_id, doc_id, triggers}."""
    rows = list(rows)
    med = section_medians(rows)
    queue, counts = [], {}
    for row in rows:
        trig = triggers(row, med)
        if not trig:
            continue
        for t in trig:
            counts[t] = counts.get(t, 0) + 1
        queue.append({"chunk_id": row["chunk_id"], "doc_id": row.get("doc_id"),
                      "triggers": trig})
    return {"queue": queue, "medians": med, "trigger_counts": counts,
            "chunks_gated": len(rows),
            "queue_rate": round(len(queue) / max(1, len(rows)), 4)}


def _single_meta(pack: dict, cid: str, gold: set[str], n: int) -> dict:
    sp = R.single_pack(pack, cid, n)
    tier = HV.TIERS[HV.tier_of(sp, gold)]
    return {"n": n, "chunk_id": cid, "doc_id": pack["doc_id"], "tier": tier,
            "score": round(HV.score_of(sp), 4), "cost": round(HV.est_cost(sp), 6)}


def plan_retry(packs_path: Path = PACKS, queue=(), out_path: Path = RETRY_PACKS) -> dict:
    """Write one single-chunk pack per queued chunk (the free retry rung)."""
    wanted = {q["chunk_id"] for q in queue}
    written = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with packs_path.open("r", encoding="utf-8") as fh, out_path.open("w", encoding="utf-8") as w:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            for cid in pack["chunk_ids"]:
                if cid not in wanted:
                    continue
                sp = R.single_pack(pack, cid, written)
                w.write(json.dumps(sp, ensure_ascii=False) + "\n")
                written += 1
    return {"singles": written, "unmatched": len(wanted) - written, "out": str(out_path)}


def rank_escalation(packs_path: Path = PACKS, queue=(), cap: float = ESC_CAP_USD) -> dict:
    """Doc-value-ordered, cap-bounded selection of the chunks that go to glm-5.3."""
    wanted = {q["chunk_id"] for q in queue}
    gold = HV.load_gold_chunk_ids()
    meta: list[dict] = []
    with packs_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            for cid in pack["chunk_ids"]:
                if cid in wanted:
                    meta.append(_single_meta(pack, cid, gold, len(meta)))
    meta.sort(key=lambda m: (m["tier"], -m["score"], m["cost"], m["chunk_id"]))
    picked, spent = [], 0.0
    for m in meta:
        if spent + m["cost"] > cap:
            continue
        picked.append(m)
        spent += m["cost"]
    tiers = {}
    for m in picked:
        t = tiers.setdefault(m["tier"], {"calls": 0, "est_cost": 0.0})
        t["calls"] += 1
        t["est_cost"] = round(t["est_cost"] + m["cost"], 4)
    return {"picked": picked, "spent": round(spent, 4), "cap": cap,
            "candidates": len(meta), "skipped": len(meta) - len(picked),
            "tiers": tiers, "unmatched_queue": len(wanted) - len(meta)}


def write_escalation(picked, packs_path: Path = PACKS, out_path: Path = ESC_PACKS) -> int:
    want = {m["chunk_id"]: m for m in picked}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with packs_path.open("r", encoding="utf-8") as fh, out_path.open("w", encoding="utf-8") as w:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            for cid in pack["chunk_ids"]:
                if cid not in want:
                    continue
                sp = R.single_pack(pack, cid, written)
                w.write(json.dumps(sp, ensure_ascii=False) + "\n")
                written += 1
    return written


def summarise(plan: dict) -> str:
    lines = [f"gated chunks {plan['queue']['chunks_gated']} queue "
             f"{len(plan['queue']['queue'])} ({plan['queue']['queue_rate'] * 100:.1f}%) "
             f"triggers {plan['queue']['trigger_counts']}",
             f"free retry singles {plan['retry']['singles']} "
             f"(unmatched {plan['retry']['unmatched']})",
             f"glm-5.3 escalation {len(plan['escalation']['picked'])} calls "
             f"est ${plan['escalation']['spent']:.2f}/${plan['escalation']['cap']:.0f} "
             f"skipped {plan['escalation']['skipped']}"]
    for tier, t in sorted(plan["escalation"]["tiers"].items()):
        name = next(k for k, v in HV.TIERS.items() if v == tier)
        lines.append(f"  {name:<16} calls {t['calls']:>5} est ${t['est_cost']:.2f}")
    return "\n".join(lines)


def cmd_plan(args) -> int:
    rows = load_gated(Path(args.gated))
    q = build_queue(rows)
    retry = plan_retry(Path(args.packs), q["queue"], Path(args.retry_out))
    esc = rank_escalation(Path(args.packs), q["queue"], args.cap)
    if not args.plan_only:
        esc_written = write_escalation(esc["picked"], Path(args.packs), Path(args.esc_out))
    else:
        esc_written = 0
    full = {"queue": q, "retry": retry, "escalation": {**esc, "packs_written": esc_written}}
    print(summarise(full))
    plan = {"queue": {k: v for k, v in q.items() if k != "queue"},
            "queue_head": q["queue"][:5], "retry": retry,
            "escalation": {**{k: v for k, v in esc.items() if k != "picked"},
                           "packs_written": esc_written, "model": ESC_MODEL,
                           "pass": ESC_PASS, "retry_pass": RETRY_PASS,
                           "partial_coverage": True, "out": str(args.esc_out)}}
    Path(args.plan).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: rule-6 queue + retry/escalation plan")
    ap.add_argument("--gated", default=str(GATED))
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--plan", default=str(PLAN))
    ap.add_argument("--retry-out", default=str(RETRY_PACKS))
    ap.add_argument("--esc-out", default=str(ESC_PACKS))
    ap.add_argument("--cap", type=float, default=ESC_CAP_USD)
    ap.add_argument("--plan-only", action="store_true", help="rank and report, write no packs")
    return cmd_plan(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
