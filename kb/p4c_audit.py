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
import money as M  # noqa: E402
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

JUDGE_PROMPT = """You audit extracted records against the frozen acceptance contract (plan §7.4).

For each item you get: publisher, doc type, date, the quoted sentence(s), and one extracted record
JSON. Judge ONLY these three code-checkable rules. Do not judge tone, wording, paraphrase,
completeness, role semantics, whether an entity is the "right kind", or anything the contract below
does not state - the contract is the whole standard, not a starting point.

RULE 3 - printed numbers. Collect the numbers that are printed in these fields only:
`attrs_printed[].value_as_printed`, `valid_from_printed`, `valid_to_printed`, `when_printed`,
`magnitude_printed`, `horizon_printed`. Every number token in them must appear in the quoted
sentence(s), matching as printed. A number that is absent from the quote fails.
Ignore whether descriptive words around a number appear; only the number tokens matter here. A value
with no digit in it (e.g. `"the decade ahead"`) has no number tokens and cannot fail this rule.

RULE 4 - entity references. `src`, `dst`, `roles[].entity` and `subjects[]` must each be either an
existing id (any id of the form `type:NAME`, e.g. `company:cik0000913290`, `country:IN`,
`route:TC5`, `commodity:crude_oil`) or a newly proposed entity (an id whose name part begins with
`new:`). Existing ids resolve against a document-wide catalog, so they need NOT appear in the quote.
A NEW id is accepted when it appears as a key of `new_entities_verified` - that map lists exactly the
new entities the acceptance code already verified against their OWN cited sentences, so treat its
keys as resolved and do not re-test them against `quote`. Only if a `new:` id is ABSENT from
`new_entities_verified` may you test its printed name against `quote` (slug `_` renders as a space,
and an abbreviation counts as present if its letters occur in the quote).

RULE 1 - schema. `direction` must be one of `up`, `down`, `flat`, `mixed`, `na`. Nothing else.

- keep: no printed number token is missing from the quote, every reference resolves under rule 4, and
  `direction` (if present) is a legal value. Length, style, and omitted detail do not matter.
- drop: at least one number token is absent from the quote, or a `new:` id is absent from
  `new_entities_verified` AND its printed name is absent from the quote, or `direction` is not one of
  the five legal values. Name the rule in `reason`. A word-only value such as `"the decade ahead"`
  carries no number token, so it cannot fail rule 3.

Answer with JSON only: {"verdict": "keep" | "drop", "reason": "<=12 words, name the rule"}
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


def row_kept(row: dict) -> dict:
    """Kept records per kind, tolerating both row shapes.

    Gate rows (`p4c_gate.gated.jsonl`) carry only `kept`; union rows
    (`p4c_union.gated_union.jsonl`) carry `kept` plus the same three lists spread at top level. Read
    `kept` first so neither shape is missed, and fall back to the spread keys for any older row.
    """
    kept = row.get("kept")
    if isinstance(kept, dict):
        return {kind: kept.get(kind) or [] for kind in ("state_facts", "events", "claims")}
    return {kind: row.get(kind) or [] for kind in ("state_facts", "events", "claims")}


def iter_rows(path: Path):
    """Stream gate/union rows so the audit plan never holds the whole export in memory."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def row_new_entities(row: dict) -> dict[str, str]:
    """The gate-verified new-entity catalog this row carries: `new:` id -> printed name.

    Defect 39. `extract_gates.gate_chunk` (frozen) verifies §7.4 rule 4 for a new entity against the
    entity's *own* cited sentences: `new_ok[ne.id] = bool(ne.name and search(ne.name, quote_for(
    ne.sids, ne_sents)))` (extract_gates.py:246-258), and `p4c_union.kept_for` keeps only the ids that
    passed (`p4c_union.py:147-148`). The audit item previously carried neither that catalog nor those
    sentences, so the judge re-tested rule 4 against the *record's* quote - evidence the contract never
    consults - and dropped 8 of 200 compliant records for "new entity name absent from quote". The
    full-population check (`kb/state/tmp/union_literal_full.py` over all 183,486 union records) finds
    0 dangling `new:` refs, 0 illegal `direction`, 0 numbers outside their quote: the drops were the
    instrument, not the records.
    """
    ne = row.get("new_entities")
    return {str(k): str(v) for k, v in ne.items()} if isinstance(ne, dict) else {}


def flat_row_records(row: dict) -> list[dict]:
    """One entry per kept record of a single row, with the quote the gate accepted for it."""
    out = []
    kept = row_kept(row)
    new_entities = row_new_entities(row)
    for kind in ("state_facts", "events", "claims"):
        for i, rec in enumerate(kept[kind]):
            quote = "; ".join(rec.get("quote") or []) if isinstance(rec.get("quote"), list) \
                else str(rec.get("quote") or "")
            out.append({"chunk_id": row.get("chunk_id"), "doc_id": row.get("doc_id"),
                        "kind": kind, "index": i, "quote": quote,
                        "publisher": row.get("publisher"), "doc_type": row.get("doc_type"),
                        "published_at": row.get("published_at"),
                        "new_entities_verified": new_entities, "record": rec})
    return out


def flat_records(rows: list[dict]) -> list[dict]:
    """One entry per kept extracted record, with the quote the gate accepted for it."""
    out = []
    for row in rows:
        out.extend(flat_row_records(row))
    return out


def iter_flat_records(path: Path):
    """Stream `flat_records` over a file, yielding records in file order."""
    for row in iter_rows(path):
        yield from flat_row_records(row)


def count_records(path: Path) -> int:
    """Number of records `flat_records` would return, without retaining any of them."""
    return sum(len(flat_row_records(row)) for row in iter_rows(path))


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
            "quote": item.get("quote"),
            "new_entities_verified": item.get("new_entities_verified") or {},
            "record": rec}
    return [{"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": json.dumps(body, ensure_ascii=False, indent=1)}]


def judge_extra(model: str) -> dict:
    """Transport for a *judge* call. Must never carry the extractor's `record_extraction` tool.

    Defect 37: `make_job` built `extra_body` from `B.model_extra(mode, [], model)` where `mode` came
    from `modes.json` - the mode the *extractor* negotiated (`tools` for `glm-5.3`). That attaches
    `tools=[record_extraction]` plus a `tool_choice` forcing it, so every judge call was compelled to
    call the extraction function and returned an extraction body (`{"claims": [], ..., "no_content":
    true}`) instead of a verdict. `parse_verdict` could not read one of them, `summarise` counts an
    unreadable verdict as wrong, and the audit reported `wrong_rate 1.0` on 184/200 judged items -
    a failing gate produced by the harness, not by the records.

    A judge answers in JSON and uses no tools. Measured on `glm-5.3` (probe
    `kb/state/tmp/audit_transport_probe.out.txt`): `response_format=json_object` and
    `reasoning_effort=minimal` both return a clean `{"verdict": ...}` with 0 tool calls.
    """
    return {"response_format": {"type": "json_object"}, **B.REASONING_EXTRA.get(model, {})}


def judge_prompt_version() -> str:
    """Cache tag derived from the prompt itself.

    Defect 38: the raw ledger is keyed by `job_key`, which carried the hard-coded literal
    `"audit-v2"`. Rewriting `JUDGE_PROMPT` (Defect 37 follow-up: hold the judge to the frozen
    §7.4 contract instead of asking it for tone/paraphrase evidence the contract never gates)
    left the tag unchanged, so `runner.run` would have replayed the *old* verdicts from disk and
    the new prompt would have measured nothing. Hashing the prompt makes the tag move with it.
    """
    import hashlib
    return "audit-" + hashlib.sha256(JUDGE_PROMPT.encode("utf-8")).hexdigest()[:12]


def make_job(item: dict, model: str, mode: str) -> dict:
    key = f"{item['chunk_id']}|{item['kind']}|{item['index']}"
    return {"job_key": R.job_key(PASS, model, judge_prompt_version(), mode, key), "model": model,
            "messages": item_messages(item),
            "extra_body": judge_extra(model),
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


def default_gated() -> Path:
    """The audit judges the record set that survives into the graph: union export first, else gate rows.

    Same precedence as `p5_build.default_gated_paths()` so the audit and the graph describe one body of
    records — auditing `gated.jsonl` after the union has deduped and merged would score records that
    were replaced.
    """
    union = OUT / "union/gated_union.jsonl"
    return union if union.exists() else OUT / "gated.jsonl"


def plan(gated: Path | None = None, n: int = RECORDS_TARGET) -> dict:
    """Seeded sample of `n` records, selected without materialising the export.

    The selection is the same one `sample_records(flat_records(all_rows))` makes — indices drawn from
    `random.Random(seed).sample(range(total), n)`, then walked in ascending order — so the chosen
    records and their `audit_id`s are byte-identical to the in-memory version. It is computed in two
    streaming passes (count, then pick) to keep peak memory at O(n) instead of O(records): the full
    scope is ~52k records and the whole-file load peaked near 0.9 GB on a box with ~1 GB free.
    """
    gated = gated or default_gated()
    total = count_records(gated)
    seed = seed_for()
    if total <= n:
        wanted = set(range(total))
    else:
        wanted = set(random.Random(seed).sample(range(total), n))
    picked = []
    for i, rec in enumerate(iter_flat_records(gated)):
        if i in wanted:
            picked.append(rec)
    for i, item in enumerate(picked):
        item["audit_id"] = f"a{i:03d}"
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT_ITEMS.write_text(json.dumps({"phase": PHASE, "seed": seed, "records_available":
                                       total, "items": picked}, indent=1), encoding="utf-8")
    return {"records_available": total, "items": len(picked), "out": str(AUDIT_ITEMS)}


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
            # `round(R.spent(...), 6)` collapsed "no measurement" to the measured-zero string `0.0`.
            # The audit's spend is owner-facing (it sits beside the §11 gate verdict), so an
            # unpriced/sumless ledger must read UNMEASURED, not free (Defect 17 class, Lesson 69).
            "ok": runner.stats.get("ok"), "cost_usd": M.round_usd(R.spent_exact(passes=[PASS])),
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
    # Unreadable cap/ledger -> `None`: bail out and say so, rather than book a judge pass against a
    # fabricated $0.0 headroom (Defect 17 class: `max(0.0, None - x)` either raises or lies).
    cap = B.cap_arg(args.cap)
    if cap is None:
        raise SystemExit("cannot price this audit run: pipeline cap or ledger sum unreadable "
                         "(pass --cap to run anyway)")
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
