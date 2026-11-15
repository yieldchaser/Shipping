"""P4c escalation ladder: rule-6 failure queue, free single-chunk retry, capped glm-5.3 escalation.

DESIGN NOTE
Plan §7.4 rule 6 escalates a chunk when (a) more than 30% of its records failed gates 2-4, (b) the
mean record confidence is below 0.5, or (c) it is a long SEC MD&A-class chunk whose kept-record
count is under half the pilot median for its section type. This module implements that test over the
gated bulk output, puts every firing chunk through the free Ultrafast single-chunk retry rung first
(one free retry, per owner decision 3), and only then spends money. The paid rung is glm-5.3
(owner decision 3: nemotron is excluded from extraction escalation) inside the escalation booking
read from `kb/config.yaml` (`budget.passes.escalation_plus_gleaning`, `escalation_cap()`),
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

import money as M  # noqa: E402

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


def escalation_cap() -> float | None:
    """The escalation booking from `kb/config.yaml` `budget.passes.escalation_plus_gleaning`.

    This module shipped a literal `ESC_CAP_USD = 17.0` while the booking it spends has since been
    amended down to 11 (the AMD bulk pass, being paid, had to come out of the other bookings - see the
    rebooking block in config). A hardcoded cap is the same defect class as a hardcoded spend: the
    number is a *denominator the owner reads in the ladder plan*, and a stale one silently authorises
    6 dollars more escalation than was ever booked.

    Returns `None` when the config cannot be read or does not hold a numeric booking. A fallback
    constant was the previous behaviour and is exactly the defect: an unreadable config would resolve
    to `$11` and the plan would print a cap the owner never booked. `None` forces the caller to
    refuse (`rank_escalation`) or to pass `--cap` explicitly, and renders as `UNMEASURED`.
    """
    try:
        import yaml
        cfg = yaml.safe_load((KB / "config.yaml").read_text(encoding="utf-8")) or {}
        v = (((cfg.get("budget") or {}).get("passes") or {})
             .get("escalation_plus_gleaning"))
    except (OSError, ValueError, ImportError, AttributeError, TypeError):
        return None
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return float(v)


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
    """{chunk_id: gate row}, later passed wins (retry/escalation rungs override the bulk row).

    NOTE: this materialises every row of every supplied file. It is retained for callers that
    genuinely need the whole merged map, but the plan path does NOT use it any more: at the frozen
    scope (86,607 chunks) each retained row costs ~9.6 KB (the gate row carries the `records`
    verdict list), so the merged map alone projects to ~834 MB. See cmd_plan for the streaming
    equivalent.
    """
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
        if row.get("call_missing"):
            # Never-extracted chunk: it has no records because it was never asked, so letting it
            # into the pilot median would drag rule 6c down and escalate chunks that are fine.
            continue
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
    """Rule-6 queue over all gated chunks: ordered list of {chunk_id, doc_id, triggers}.

    Rows that are `call_missing` (pack never extracted - Defect 10) are not "gated" in any useful
    sense: nothing was asked, so nothing failed. They are excluded from the queue and its rate.

    NOTE: materialises `rows`. At the frozen scope a gate row costs ~9.6 KB (it carries the
    `records` verdict list), so this cost ~834 MB for 86,607 chunks. `build_queue_stream` is the
    memory-safe equivalent used by cmd_plan.
    """
    rows = [r for r in rows if not r.get("call_missing")]
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


def _has_duplicate_chunk_ids(path: Path) -> bool:
    """True if a gate file repeats a chunk_id (dict-based readers keep only the last one)."""
    seen: set[str] = set()
    for row in load_gated(path):
        cid = row["chunk_id"]
        if cid in seen:
            return True
        seen.add(cid)
    return False


def _merged_rows(paths):
    """Stream gate rows with later files winning per chunk_id, in first-appearance order.

    Equivalent to iterating `gated_chunk_map(paths=paths).values()`: dict insertion order is the
    first appearance of each chunk_id across the concatenated files, and the stored value is its
    last occurrence. Retains only chunk-id strings plus the override rows from the later files
    (bounded by the union of those files: in the step-4b shape that is the retry rung, a few
    thousand rows, not the frozen scope). Duplicated chunk_ids are pathological — the gate writer
    emits one row per chunk — so that case falls back to the materialising map and stays exact.
    """
    paths = [Path(p) for p in paths]
    if not paths:
        return
    if len(paths) == 1:
        yield from load_gated(paths[0])
        return
    if any(_has_duplicate_chunk_ids(p) for p in paths):
        yield from gated_chunk_map(paths=paths).values()
        return

    override: dict[str, dict] = {}
    later_order: list[str] = []
    for p in paths[1:]:
        for row in load_gated(p):
            cid = row["chunk_id"]
            if cid not in override:
                later_order.append(cid)
            override[cid] = row

    first_ids: set[str] = set()
    for row in load_gated(paths[0]):
        cid = row["chunk_id"]
        first_ids.add(cid)
        yield override[cid] if cid in override else row
    # Chunks that only a later file introduced keep the later files' first-appearance order.
    for cid in later_order:
        if cid not in first_ids:
            yield override[cid]


def section_medians_stream(rows) -> dict[str, float]:
    """Streaming `section_medians`: keeps only the per-bucket median inputs."""
    buckets: dict[str, list[int]] = {}
    for row in rows:
        if row.get("call_missing"):
            continue
        if int(row.get("approx_tokens") or 0) < LONG_TOKENS:
            continue
        key = f"{row.get('doc_type') or '?'}/{row.get('section_class') or '?'}"
        buckets.setdefault(key, []).append(int(row.get("records_ok") or 0))
    return {k: float(statistics.median(v)) for k, v in buckets.items() if v}


def build_queue_stream(paths) -> dict:
    """Streaming `build_queue` over gated files (later file wins). Same result, bounded memory."""
    med = section_medians_stream(_merged_rows(paths))
    queue, counts, n = [], {}, 0
    for row in _merged_rows(paths):
        if row.get("call_missing"):
            continue
        n += 1
        trig = triggers(row, med)
        if not trig:
            continue
        for t in trig:
            counts[t] = counts.get(t, 0) + 1
        queue.append({"chunk_id": row["chunk_id"], "doc_id": row.get("doc_id"),
                      "triggers": trig})
    return {"queue": queue, "medians": med, "trigger_counts": counts,
            "chunks_gated": n, "queue_rate": round(len(queue) / max(1, n), 4)}


def _single_meta(pack: dict, cid: str, gold: set[str], n: int) -> dict:
    sp = R.single_pack(pack, cid, n)
    tier = HV.TIERS[HV.tier_of(sp, gold)]
    # `cost` is projected money: route it through money.round_usd so the precision lives in one place
    # and the projection cannot be rounded with a per-file literal that outlives the house rule
    # (Defect 17 class). `score` is a ranking score, not money, and keeps its own rounding.
    return {"n": n, "chunk_id": cid, "doc_id": pack["doc_id"], "tier": tier,
            "score": round(HV.score_of(sp), 4), "cost": M.round_usd(HV.est_cost(sp))}


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


def rank_escalation(packs_path: Path = PACKS, queue=(), cap: float | None = None) -> dict:
    """Doc-value-ordered, cap-bounded selection of the chunks that go to glm-5.3.

    `cap=None` (the default) reads the booking from config rather than trusting the old literal, so a
    caller that forgets to pass one still cannot overrun the rebooked escalation line.
    `escalation_cap()` is tri-state: it returns `None` when the config is unreadable. That must never
    become a fallback constant (a cap the owner never booked) nor `0.0` (which would make every chunk
    "unaffordable" and report a fabricated "cap exhausted" verdict). It is a hard error instead.
    """
    cap = escalation_cap() if cap is None else cap
    if cap is None:
        raise ValueError("p4c_ladder: escalation cap unreadable; pass --cap explicitly")
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
        # Projected tier money: `round(..., 4)` flattens a sub-cent estimate into the measured-zero
        # value `0.0`; `M.round_usd` keeps 6 places so the projection stays distinguishable
        # (Defect 17 class). `calls` is a count, not money, and is untouched.
        t["est_cost"] = M.round_usd(t["est_cost"] + m["cost"])
    return {"picked": picked, "spent": M.round_usd(spent), "cap": cap,
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
    # `:.2f` here was a lossy read of a real number: a sub-cent tier estimate printed as `$0.00`, the
    # measured-zero string, and the cap printed with `:.0f` even though it is a dollar figure read from
    # config. Money goes through money.fmt_usd so "not measured" and "measured zero" stay distinct in
    # the plan the owner reads (Defect 17 class, Lesson 69).
    esc = plan["escalation"]
    lines = [f"gated chunks {plan['queue']['chunks_gated']} queue "
             f"{len(plan['queue']['queue'])} ({plan['queue']['queue_rate'] * 100:.1f}%) "
             f"triggers {plan['queue']['trigger_counts']}",
             f"free retry singles {plan['retry']['singles']} "
             f"(unmatched {plan['retry']['unmatched']})",
             f"glm-5.3 escalation {len(esc['picked'])} calls "
             f"est {M.fmt_usd(esc.get('spent'))}/{M.fmt_usd(esc.get('cap'))} "
             f"skipped {esc['skipped']}"]
    for tier, t in sorted(esc["tiers"].items()):
        name = next(k for k, v in HV.TIERS.items() if v == tier)
        lines.append(f"  {name:<16} calls {t['calls']:>5} est {M.fmt_usd(t.get('est_cost'))}")
    return "\n".join(lines)


def cmd_plan(args) -> int:
    # Streaming: at the frozen scope (86,607 chunks) retaining gate rows costs ~9.6 KB each, so
    # `build_queue(load_gated(...))` alone projects to ~834 MB and the merged esc map doubles it.
    # build_queue_stream holds only chunk-id strings plus the overriding (later-file) rows.
    q = build_queue_stream([Path(args.gated)])
    retry = plan_retry(Path(args.packs), q["queue"], Path(args.retry_out))
    # The escalation rung is a quality backstop for chunks the free retry did NOT cure, so when a
    # post-retry gate slice is supplied it overrides the bulk row per chunk. Sourcing esc from the
    # pre-retry rows spends the (capped) esc booking re-buying chunks the free retry already fixes.
    esc_gated = getattr(args, "esc_gated", None)
    if esc_gated:
        esc_q = build_queue_stream([Path(args.gated), Path(esc_gated)])["queue"]
    else:
        esc_q = q["queue"]
    esc = rank_escalation(Path(args.packs), esc_q, args.cap) if args.cap is not None else None
    if esc is None:
        # Resolve the booking before any ranking/writing so an unreadable config aborts cleanly
        # instead of booking against a fallback cap (Defect 17 class). `--cap` bypasses the read.
        cap = escalation_cap()
        if cap is None:
            raise SystemExit("p4c_ladder: cannot read budget.passes.escalation_plus_gleaning from "
                             "kb/config.yaml; pass --cap explicitly")
        esc = rank_escalation(Path(args.packs), esc_q, cap)
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
                           "partial_coverage": True, "out": str(args.esc_out),
                           "esc_source": str(esc_gated or args.gated)}}
    Path(args.plan).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: rule-6 queue + retry/escalation plan")
    ap.add_argument("--gated", default=str(GATED))
    ap.add_argument("--esc-gated", default=None,
                    help="post-retry gate slice that overrides --gated when ranking escalation")
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--plan", default=str(PLAN))
    ap.add_argument("--retry-out", default=str(RETRY_PACKS))
    ap.add_argument("--esc-out", default=str(ESC_PACKS))
    ap.add_argument("--cap", type=float, default=None,
                    help="escalation booking cap in USD; default = config budget.passes."
                         "escalation_plus_gleaning")
    ap.add_argument("--plan-only", action="store_true", help="rank and report, write no packs")
    return cmd_plan(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
