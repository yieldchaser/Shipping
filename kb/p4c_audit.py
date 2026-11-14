"""P4c step 4: seeded random audit of stored extractions, judged by another model family.

Plan §7.5 / `gates.yaml` P4c: 200 randomly chosen extracted records are re-judged by a model whose
family differs from the extractor's, and at most 3% may be wrong. The audit is pure post-processing
of the gated output: the judge only sees the sentence(s) the extractor quoted plus the record it
wrote, so it can check "is every element of this record actually in the quote" without seeing the
document or the extractor's reasoning. Sampling is seeded (`P4C`) so the same 200 records are judged
however often the audit is re-planned; the sampled item file is written first, so a judge run that
dies can be resumed from the ledger without re-sampling.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import llm_runner as LR  # noqa: E402
import p4b_run as B  # noqa: E402
import p4c_union as U  # noqa: E402
import runner as R  # noqa: E402
from extract_schema import parse_extraction  # noqa: E402

OUT = KB.parent / "kb/state/p4c"
PASS = "p4c_audit"
PHASE = "P4C"
AUDIT_ITEMS = OUT / "audit_items.json"
AUDIT_JSON = OUT / "audit.json"
AUDIT_MD = KB.parent / "kb/reports/p4c_audit.md"

RECORDS_TARGET = 200

JUDGE_PROMPT = """You audit extracted records against the sentences the extractor quoted.

For each item you get: publisher, doc type, date, the quoted sentence(s), and one extracted record
JSON. Decide whether the quote supports the record exactly as written:
- keep: every printed number, direction and entity in the record occurs in the quote
- drop: something in the record is absent, altered, or contradicted by the quote

Printed numbers must match as printed. Do not add facts from outside the quote. Answer with JSON only:
{"verdict": "keep" | "drop", "reason": "<=12 words"}
"""


def seed_for(phase: str = PHASE) -> int:
    return int(__import__("hashlib").sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def model_family(model: str) -> str:
    """Leading vendor token of the model id, not the router/provider id."""
    return model.split("/")[0].split("-")[0].lower()


def judge_family_ok(judge: str, extractor: str) -> bool:
    return model_family(judge) != model_family(extractor)


def load_gated(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def flat_records(rows: list[dict]) -> list[dict]:
    """One entry per kept extracted record, with the quote the gate accepted for it."""
    out = []
    for row in rows:
        for kind in ("state_facts", "events", "claims"):
            for i, rec in enumerate((row.get(kind) or [])):
                quote = "; ".join(rec.get("quote") or "") if isinstance(rec.get("quote"), list) \
                    else str(rec.get("quote") or "")
                out.append({"chunk_id": row.get("chunk_id"), "doc_id": row.get("doc_id"),
                            "kind": kind, "index": i, "quote": quote,
                            "publisher": row.get("publisher"), "doc_type": row.get("doc_type"),
                            "published_at": row.get("published_at"), "record": rec})
    return out


def sample_records(records: list[dict], n: int = RECORDS_TARGET, seed: int | None = None) -> list[dict]:
    """Seeded sample, ordered deterministically so a re-plan yields byte-identical items."""
    seed = seed_for() if seed is None else seed
    if len(records) <= n:
        picked = list(records)
    else:
        idx = sorted(random.Random(seed).sample(range(len(records)), n))
        picked = [records[i] for i in idx]
    for i, item in enumerate(picked):
        item["audit_id"] = f"a{i:03d}"
    return picked


def item_messages(item: dict) -> list[dict]:
    rec = json.loads(json.dumps(item["record"], default=str))
    body = {"publisher": item.get("publisher"), "doc_type": item.get("doc_type"),
            "published_at": item.get("published_at"), "kind": item.get("kind"),
            "quote": item.get("quote"), "record": rec}
    return [{"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": json.dumps(body, ensure_ascii=False, indent=1)}]


def make_job(item: dict, model: str, mode: str) -> dict:
    key = f"{item['chunk_id']}|{item['kind']}|{item['index']}"
    return {"job_key": R.job_key(PASS, model, "audit-v1", mode, key), "model": model,
            "messages": item_messages(item),
            "extra_body": B.model_extra(mode, [], model),
            "max_tokens": 300, "temperature": 0.0,
            "meta": {"chunk_id": item["chunk_id"], "kind": item["kind"], "audit_id": item["audit_id"]}}


def parse_verdict(text: str) -> tuple[str | None, str]:
    """Judge answers JSON; tolerate a code fence or a leading sentence."""
    raw = (text or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None, ""
    try:
        doc = json.loads(raw[start:end + 1])
    except ValueError:
        return None, ""
    verdict = str(doc.get("verdict") or "").lower().strip()
    if verdict not in ("keep", "drop"):
        return None, str(doc.get("reason") or "")
    return verdict, str(doc.get("reason") or "")


def plan(gated: Path | None = None, n: int = RECORDS_TARGET) -> dict:
    gated = gated or OUT / "gated.jsonl"
    records = flat_records(load_gated(gated))
    items = sample_records(records, n=n)
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT_ITEMS.write_text(json.dumps({"phase": PHASE, "seed": seed_for(), "records_available":
                                       len(records), "items": items}, indent=1), encoding="utf-8")
    return {"records_available": len(records), "items": len(items), "out": str(AUDIT_ITEMS)}


def run_judge(model: str, cap: float, limit: int = 0) -> dict:
    modes = json.loads((OUT / "modes.json").read_text(encoding="utf-8")) if (OUT / "modes.json").exists() else {}
    mode = modes.get(model) or B.load_modes().get(model)
    if not mode:
        raise SystemExit(f"no transport mode recorded for judge {model}; run the transport preflight")
    payload = json.loads(AUDIT_ITEMS.read_text(encoding="utf-8"))
    items = payload["items"][:limit] if limit else payload["items"]
    jobs = [make_job(it, model, mode) for it in items]
    runner = B.runner_for(PASS, model, cap)
    t0 = time.time()
    runner.run(jobs)
    return {"model": model, "mode": mode, "jobs": len(jobs),
            "ok": runner.stats.get("ok"), "cost_usd": round(R.spent(passes=[PASS]), 6),
            "wall_s": round(time.time() - t0, 1)}


def summarise(payload: dict, model: str, mode: str) -> dict:
    rows = []
    for item in payload["items"]:
        res = B.load_result(PASS, make_job(item, model, mode))
        raw = (res or {}).get("raw") or ""
        verdict, reason = parse_verdict(raw)
        rows.append({"audit_id": item["audit_id"], "chunk_id": item["chunk_id"],
                     "doc_id": item.get("doc_id"), "kind": item["kind"],
                     "verdict": verdict, "reason": reason, "judged": res is not None,
                     "raw": raw[:2000]})
    judged = [r for r in rows if r["judged"]]
    drops = [r for r in judged if r["verdict"] == "drop"]
    unparsed = [r for r in judged if r["verdict"] is None]
    wrong = len(drops) + len(unparsed)  # conservative: a verdict we cannot read is not a pass
    return {"model": model, "sampled": len(payload["items"]), "judged": len(judged),
            "keep": len(judged) - len(drops) - len(unparsed), "drop": len(drops),
            "unparseable": len(unparsed), "wrong": wrong,
            "wrong_rate": round(wrong / max(1, len(judged)), 4), "rows": rows}


def cmd_run(args) -> int:
    extractor = args.extractor or _selected_extractor()
    if not judge_family_ok(args.model, extractor):
        raise SystemExit(f"judge {args.model} shares {model_family(args.model)} family with extractor "
                         f"{extractor}: gates.yaml requires a different family")
    payload = json.loads(AUDIT_ITEMS.read_text(encoding="utf-8"))
    cap = args.cap if args.cap is not None else max(0.0, B.PIPELINE_CAP - R.spent())
    run = run_judge(args.model, cap, limit=args.limit)
    st = summarise(payload, args.model, run["mode"])
    st.update({"phase": PHASE, "seed": payload["seed"], "extractor_model": extractor,
               "judge_family": model_family(args.model),
               "extractor_family": model_family(extractor), "run": run,
               "gate": {"random_audit_records": RECORDS_TARGET,
                        "sampled": st["sampled"],
                        "random_audit_wrong_max": 0.03,
                        "measured_wrong_rate": st["wrong_rate"],
                        "pass": st["sampled"] >= RECORDS_TARGET and st["wrong_rate"] <= 0.03}})
    AUDIT_JSON.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    AUDIT_MD.write_text(_md(st), encoding="utf-8")
    print(json.dumps({k: st[k] for k in ("sampled", "judged", "drop", "unparseable", "wrong",
                                        "wrong_rate")}, indent=2))
    return 0


def _selected_extractor() -> str:
    """The model that actually produced the gated records under audit.

    P4c's bulk extractor is the P4c ladder's own source, not P4b's selection: the pass under audit is
    `p4c_bulk` (see `p4c_run.BULK_PASS`) over the AMD pool. Resolve it from `p4c_union.SOURCE_SPEC`
    so this label cannot silently drift back to the P4b winner the way it did while P4b's report was
    the only source; fall back to `p4b.json` only if the union spec has no bulk entry.
    """
    try:
        for pass_name, model in U.SOURCE_SPEC:
            if pass_name == "p4c_bulk":
                return model
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        rep = json.loads((KB.parent / "kb/reports/p4b.json").read_text(encoding="utf-8"))
        return rep["selected"]["model"]
    except (OSError, ValueError, KeyError):
        raise SystemExit("no extractor model given and no p4c_bulk source in p4c_union.SOURCE_SPEC")


def _md(st: dict) -> str:
    return "\n".join([
        "# P4c random audit", "",
        f"- judge: `{st['model']}` ({st['judge_family']} family) vs extractor "
        f"`{st['extractor_model']}` ({st['extractor_family']} family) — different family: "
        f"{'yes' if st['judge_family'] != st['extractor_family'] else 'NO (gate violation)'}",
        f"- sample: {st['sampled']} records of {json.loads(AUDIT_ITEMS.read_text())['records_available']}"
        f" available (seed {st['seed']})",
        f"- judged: {st['judged']}, keep {st['keep']}, drop {st['drop']}, "
        f"unparseable {st['unparseable']} -> **wrong {st['wrong']} "
        f"({st['wrong_rate']:.2%})**, gate {st['gate']['random_audit_wrong_max']:.0%}",
        "", "| audit id | chunk | kind | verdict | reason |", "|---|---|---|---|---|",
    ] + [f"| {r['audit_id']} | `{r['chunk_id']}` | {r['kind']} | {r['verdict'] or 'unparseable'} | "
         f"{r['reason'][:70]} |" for r in st["rows"][:40]]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: seeded audit of stored extractions")
    ap.add_argument("--plan", action="store_true", help="sample the audit items (free)")
    ap.add_argument("--run", action="store_true", help="judge the sampled items")
    ap.add_argument("--model", default=None)
    ap.add_argument("--extractor", default=None)
    ap.add_argument("--records", type=int, default=RECORDS_TARGET)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cap", type=float, default=None)
    ap.add_argument("--gated", default=None)
    args = ap.parse_args()
    if args.plan:
        print(json.dumps(plan(Path(args.gated) if args.gated else None, n=args.records), indent=2))
        return 0
    if not args.model:
        raise SystemExit("--run needs --model (judge model, different family from the extractor)")
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
