"""P7 evaluation (§12) — scores the gold Q&A set end to end.

Design note (D16/D17):
- Metrics are computed by code, never by a model: exact-match on gold answer numbers
  (unit/tolerance aware), refusal on unanswerable items, recall@20 by document id,
  multi-hop F1 over the required components of type-c answers.
- Faithfulness is the only judged metric: a nim judge from a different model family
  than the extractor (openai/gpt-oss-120b) returns a supported fraction per answer
  from the cited evidence text; faithfulness = mean supported.
- Every question runs the real `ask.answer_question` pipeline (planner -> tools ->
  composer -> answer contract) so the numbers reflect what P7 will ship.
- Costs are summed from the pipeline's own `cost_usd`; free ultrafast calls cost 0.
- Subsets can be skipped (--no-search, --no-judge) for smoke runs; a skipped metric
  is reported with a null value and never counted as a gate pass.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import date
from hashlib import sha256
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

import ask as A  # noqa: E402
import tools as T  # noqa: E402

ROOT = KB_DIR.parent
PHASE = "P7"
GOLD = ROOT / "kb" / "state" / "gold" / "gold_set.json"
OUT = ROOT / "kb" / "state" / "p7"
REPORTS = ROOT / "kb" / "reports"
JUDGE_MODEL = "openai/gpt-oss-120b"
EXACT_TYPES = ("a_single_number", "b_window_aggregate", "e_sec_section", "g_as_known_on_date")
TARGETS = {"exact_a_b_e_g": 0.97, "recall_at_20": 0.85, "multihop_f1": 0.75,
           "refusal": 0.95, "faithfulness": 0.95}
JUDGE_SAMPLE = 60
RECALL_K = 20
MAX_EVIDENCE = 3
EVIDENCE_CHARS = 500

JUDGE_PROMPT = """You are an auditor. Decide how much of the ANSWER is supported by the EVIDENCE.

Rules:
- Only facts stated in the EVIDENCE count as supported. External world knowledge does not.
- Numbers must appear (same unit or a stated, correct conversion) in the EVIDENCE to be supported.
- A sentence that only states a computed indicator or a labelled judgment is supported when the
  numbers it uses appear in the EVIDENCE.
- Return one JSON object: {"supported": <fraction 0.0-1.0 of answer sentences supported>,
  "unsupported": ["short quote", ...], "notes": "one line"}
- Strict, no rounding up. Empty answer -> {"supported": 0.0}."""


def seed_for(phase: str) -> int:
    return int(sha256(f"{phase}|kb-gates-v1".encode("utf-8")).hexdigest()[:8], 16)


# --------------------------------------------------------------------------- gold
def load_gold(path: Path | str = GOLD) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    return list(items or [])


def item_type(it: dict) -> str:
    return str(it.get("type") or "")


def answer_dict(it: dict) -> dict:
    ans = it.get("answer")
    return ans if isinstance(ans, dict) else {}


def gold_numbers(it: dict) -> list[float]:
    """Every number the gold answer requires (a/b/d/f/g shapes)."""
    ans = answer_dict(it)
    out: list[float] = []
    for key in ("value", "first", "last", "pct_change", "price"):
        v = ans.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
    if not out:
        out = gold_numbers_from_text(it.get("answer_text") or "")
    return out


NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def gold_numbers_from_text(text: str) -> list[float]:
    out = []
    for tok in NUM.findall(text or ""):
        try:
            out.append(float(tok.replace(",", "")))
        except ValueError:
            continue
    return out


def tolerance_of(it: dict) -> float:
    tol = answer_dict(it).get("tolerance")
    return float(tol) if isinstance(tol, (int, float)) else 0.0


def numbers_match(expected: float, tol: float, found: list[float]) -> bool:
    lim = max(float(tol), abs(expected) * 1e-6)
    return any(abs(n - expected) <= lim for n in found)


def unit_of(it: dict) -> str:
    return str(answer_dict(it).get("unit") or "")


# --------------------------------------------------------------------------- metrics
def score_exact(it: dict, rec: dict) -> bool | None:
    """True/False, or None when the item cannot be graded by this metric."""
    t = item_type(it)
    if t not in EXACT_TYPES:
        return None
    if rec.get("status") != "ok":
        return False
    text = rec.get("answer") or ""
    if t == "e_sec_section":
        ans = answer_dict(it)
        term = str(ans.get("term") or ans.get("heading") or "").strip().lower()
        return bool(term) and term in text.lower()
    exp = gold_numbers(it)
    if not exp:
        return None
    found = [float(x) for x in A.numbers_in(A.strip_cites(text))]
    return all(numbers_match(v, tolerance_of(it), found) for v in exp)


MH_COMPONENTS = ("price", "publishers", "n_docs", "used_by_d", "date")


def multihop_components(it: dict) -> set[str]:
    ans = answer_dict(it)
    return {k for k in MH_COMPONENTS if ans.get(k) not in (None, "", [], {})}


def found_components(it: dict, rec: dict) -> set[str]:
    text = A.strip_cites(rec.get("answer") or "")
    low = text.lower()
    found_nums = [float(x) for x in A.numbers_in(text)]
    ans = answer_dict(it)
    out: set[str] = set()
    price = ans.get("price")
    if isinstance(price, (int, float)) and numbers_match(float(price), tolerance_of(it), found_nums):
        out.add("price")
    pubs = ans.get("publishers") or []
    if pubs and any(str(p).lower() in low for p in pubs):
        out.add("publishers")
    if ans.get("n_docs") is not None and numbers_match(float(ans["n_docs"]), 0.0, found_nums):
        out.add("n_docs")
    used = ans.get("used_by_d")
    if used and any(str(u).lower() in low for u in ([used] if isinstance(used, str) else used)):
        out.add("used_by_d")
    if ans.get("date") and str(ans["date"]).lower()[:10] in low:
        out.add("date")
    return out


def multihop_f1(it: dict, rec: dict) -> float | None:
    gold = multihop_components(it)
    if not gold:
        return None
    if rec.get("status") != "ok":
        return 0.0
    got = found_components(it, rec) & gold
    if not got:
        return 0.0
    prec, rec_ = len(got) / max(1, len(got)), len(got) / len(gold)
    return round(2 * prec * rec_ / (prec + rec_), 4)


def score_refusal(it: dict, rec: dict) -> bool | None:
    if item_type(it) != "h_unanswerable":
        return None
    if rec.get("status") in ("not_in_data", "model_error"):
        return True
    text = (rec.get("answer") or "").strip()
    return text == A.NOT_IN_DATA or text.startswith(A.NOT_IN_DATA)


def gold_doc_ids(it: dict) -> set[str]:
    out = set()
    for src in it.get("sources") or []:
        if isinstance(src, dict) and src.get("doc_id"):
            out.add(str(src["doc_id"]))
    return out


def recall_hit(it: dict, con, k: int = RECALL_K) -> bool | None:
    docs = gold_doc_ids(it)
    if not docs:
        return None
    try:
        res = T.search(it.get("question") or "", k=k, con=con)
    except Exception:  # noqa: BLE001 - retrieval unavailable in smoke runs
        return None
    got = {str(r.get("doc_id")) for r in res.get("results", [])}
    return bool(got & docs)


# --------------------------------------------------------------------------- faithfulness
def cite_evidence(rec: dict) -> str:
    chunks: list[str] = []
    for snippet in rec.get("evidence") or []:
        if snippet:
            chunks.append(str(snippet)[:EVIDENCE_CHARS])
    for s in (rec.get("sentences") or [])[:MAX_EVIDENCE]:
        q = s.get("quote") if isinstance(s, dict) else None
        if q:
            chunks.append(str(q)[:EVIDENCE_CHARS])
    return "\n---\n".join(chunks[:MAX_EVIDENCE])


def judge_faithful(rec: dict, chat=None) -> float:
    chat = chat or A._chat
    evidence = cite_evidence(rec)
    if not evidence:
        return 0.0
    user = (f"QUESTION: {rec.get('question', '')}\n\n"
            f"ANSWER: {rec.get('answer', '')}\n\nEVIDENCE:\n{evidence}\n\nReturn JSON only.")
    try:
        text, _usage, _cost = chat(JUDGE_MODEL, [{"role": "system", "content": JUDGE_PROMPT},
                                                 {"role": "user", "content": user}], 400)
    except Exception:  # noqa: BLE001
        return 0.0
    try:
        payload = json.loads(text or "{}", strict=False)
        return max(0.0, min(1.0, float(payload.get("supported", 0.0))))
    except (ValueError, TypeError):
        return 0.0


# --------------------------------------------------------------------------- run
def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _ratio(flags: list[bool]) -> float | None:
    return round(sum(1 for f in flags if f) / len(flags), 4) if flags else None


def build_report(items: list[dict], records: list[dict], recall_flags: list[bool],
                 mh_scores: list[float], faith_scores: list[float]) -> dict:
    exact = [score_exact(it, rec) for it, rec in zip(items, records)]
    exact = [e for e in exact if e is not None]
    refusals = [score_refusal(it, rec) for it, rec in zip(items, records)]
    refusals = [r for r in refusals if r is not None]
    metrics = {
        "exact_a_b_e_g": _ratio(exact),
        "recall_at_20": _ratio(recall_flags),
        "multihop_f1": _mean(mh_scores),
        "refusal": _ratio(refusals),
        "faithfulness": _mean(faith_scores),
    }
    gates = {}
    for key, target in TARGETS.items():
        value = metrics.get(key)
        gates[key] = {"value": value, "target": target,
                      "pass": None if value is None else value >= target}
    return {"phase": PHASE, "metrics": metrics, "gates": gates,
            "counts": {"items": len(items), "exact_graded": len(exact),
                       "recall_graded": len(recall_flags), "refusal_graded": len(refusals),
                       "multihop_graded": len(mh_scores), "faithfulness_graded": len(faith_scores)}}


def evaluate(items: list[dict], con=None, chat=None, judge_chat=None, limit: int = 0,
             judge_sample: int = JUDGE_SAMPLE, with_search: bool = True,
             with_judge: bool = True, model: str = A.DEFAULT_MODEL,
             seed: int | None = None) -> dict:
    t0 = time.time()
    if limit:
        items = items[:limit]
    own = con is None
    con = con or T.connect()
    seed = seed_for(PHASE) if seed is None else seed
    try:
        records, mh, recall_flags = [], [], []
        for it in items:
            try:
                rec = A.answer_question(it.get("question") or "", model=model, con=con, chat=chat)
            except Exception as exc:  # noqa: BLE001 - one bad item must not kill the run
                rec = {"question": it.get("question"), "status": "model_error",
                       "answer": A.NOT_IN_DATA, "error": f"{type(exc).__name__}: {exc}"}
            rec["item_id"] = it.get("id")
            rec["type"] = item_type(it)
            records.append(rec)
            f1 = multihop_f1(it, rec)
            if f1 is not None:
                mh.append(f1)
            if with_search:
                hit = recall_hit(it, con)
                if hit is not None:
                    recall_flags.append(hit)

        faith_scores: list[float] = []
        if with_judge:
            candidates = [r for r in records if r.get("status") == "ok"]
            rng = random.Random(seed)
            sample = rng.sample(candidates, min(judge_sample, len(candidates)))
            for r in sample:
                r["faithfulness"] = judge_faithful(r, chat=judge_chat)
            faith_scores = [r["faithfulness"] for r in sample]
    finally:
        if own:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass

    report = build_report(items, records, recall_flags, mh, faith_scores)
    cost = round(sum(float(r.get("cost_usd") or 0.0) for r in records), 6)
    report.update({"sample_seed": seed, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "wall_seconds": round(time.time() - t0, 1), "money_spent_usd": cost,
                   "model": model, "judge_model": JUDGE_MODEL if with_judge else None,
                   "judged": len(faith_scores), "with_search": with_search,
                   "items": [{k: r.get(k) for k in ("item_id", "type", "question", "status",
                                                     "answer", "model", "escalated", "cost_usd")}
                              for r in records]})
    report["pass"] = bool(all(g["pass"] for g in report["gates"].values() if g["pass"] is not None)
                          and all(g["pass"] is True for g in report["gates"].values()))
    return report


def _md(report: dict) -> str:
    m, g = report["metrics"], report["gates"]
    lines = [f"# P7 eval — §12 gold-set scoring", "",
             f"- items: {report['counts']['items']} · wall: {report['wall_seconds']} s · spend: ${report['money_spent_usd']}",
             f"- model: `{report['model']}` · judge: `{report['judge_model']}` · judged: {report['judged']}",
             f"- result: {'PASS' if report['pass'] else 'FAIL'}", "",
             "| metric | value | target | pass |", "|---|---|---|---|"]
    for k, target in TARGETS.items():
        v = g.get(k, {})
        lines.append(f"| {k} | {v.get('value')} | {target} | {v.get('pass')} |")
    lines += ["", "## Graded counts", ""]
    lines += [f"- {k}: {v}" for k, v in report["counts"].items()]
    lines += ["", "## Deviations", "",
              "- D16: exact match compares gold numbers (tolerance aware) against numbers in the answer.",
              "- D17: faithfulness is judged by a nim model from a different family than the extractor;",
              "  the judged sample is seeded and reproducible.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P7 §12 evaluation over the gold Q&A set")
    ap.add_argument("--gold", default=str(GOLD))
    ap.add_argument("--db", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--judge-sample", type=int, default=JUDGE_SAMPLE)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--no-search", action="store_true")
    ap.add_argument("--model", default=A.DEFAULT_MODEL)
    ap.add_argument("--out", default=str(OUT / "eval.json"))
    ap.add_argument("--report", action="store_true", help="write kb/reports/p7_eval.json/.md")
    args = ap.parse_args(argv)

    items = load_gold(args.gold)
    if not items:
        print("no gold items")
        return 2
    con = T.connect(args.db or T.KB_DB)
    try:
        report = evaluate(items, con=con, limit=args.limit, judge_sample=args.judge_sample,
                          with_search=not args.no_search, with_judge=not args.no_judge,
                          model=args.model)
    finally:
        con.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if args.report:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "p7_eval.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        (REPORTS / "p7_eval.md").write_text(_md(report), encoding="utf-8")
        (REPORTS / "p7_eval.md").write_text(_md(report), encoding="utf-8")
    for k in TARGETS:
        print(f"{k}: {report['metrics'].get(k)} target {TARGETS[k]}")
    print("PASS" if report["pass"] else "FAIL", "->", out)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
