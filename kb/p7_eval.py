"""P7 evaluation (§12) — scores the gold Q&A set end to end.

Design note (D16/D17):
- Metrics are computed by code, never by a model: exact-match on gold answer numbers
  (unit/tolerance aware), refusal on unanswerable items, recall@20 by document id,
  multi-hop F1 over the required components of type-c answers.
- Faithfulness is the only judged metric: a judge from a different model family
  than the extractor (Google `Gemma-4-31B-IT` on AMD Token Lab, family gemma;
  owner amendment 2026-11-15 replaced the NIM free tier, fallback `Qwen3.8-27B`)
  returns a supported fraction per answer from the cited evidence text;
  faithfulness = mean supported.
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
import llm_runner as LR  # noqa: E402
import money as M  # noqa: E402
import tools as T  # noqa: E402

ROOT = KB_DIR.parent
PHASE = "P7"
GOLD = ROOT / "kb" / "state" / "gold" / "gold_set.json"
OUT = ROOT / "kb" / "state" / "p7"
REPORTS = ROOT / "kb" / "reports"
JUDGE_MODEL = "Gemma-4-31B-IT"       # owner amendment 2026-11-15 (replaces NIM free tier)
JUDGE_FALLBACK_MODEL = "Qwen3.8-27B"
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
    """Every number the gold answer requires (a/b/d/f/g shapes).

    Defect 28: this read used `isinstance(v, (int, float))`, which admits `inf`. The fabrication is in
    the tolerance floor: `numbers_match` computes `lim = max(tol, abs(expected) * 1e-6)`, and
    `abs(inf) * 1e-6` is `inf`, so `lim` became `inf` and `abs(n - inf) <= inf` held for **every**
    candidate number. A gold item authored with an overflowing cell therefore graded `True` against any
    answer text at all, inflating the §12 `exact_a_b_e_g` arm; the same class of read let
    `n_docs: true`/`inf` grant a multihop component for free. `M.as_float` is the one finite-value
    rule: anything it rejects is dropped here, so the item falls through to the authored text (or
    grades as ungradable) rather than being graded against a fabricated expectation.
    """
    ans = answer_dict(it)
    out: list[float] = []
    for key in ("value", "first", "last", "pct_change", "price"):
        f = M.as_float(ans.get(key))
        if f is not None:
            out.append(f)
    if not out:
        out = gold_numbers_from_text(it.get("answer_text") or "")
    return out


NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def gold_numbers_from_text(text: str) -> list[float]:
    """Numbers found in an authored answer string. Same finite rule as `gold_numbers`: a token that
    overflows to `inf` (`float("1" + "0"*400)`) is a broken read, not a requirement."""
    out = []
    for tok in NUM.findall(text or ""):
        try:
            raw = float(tok.replace(",", ""))
        except ValueError:
            continue
        f = M.as_float(raw)   # `raw` is already a float: this is the finite-value rule, not a cast
        if f is not None:
            out.append(f)
    return out


def tolerance_of(it: dict) -> float | None:
    """The gold item's *authored* tolerance, or `None` when it does not carry one.

    Absent and unreadable are different states, and this is the read that keeps them apart. An item
    type whose authoring convention is exact match legitimately has no `tolerance` key at all (all 35
    live `c_multihop_entity` items), so `None` here means "the type declares the semantics", not "the
    read failed". A tolerance that is *present* but not a real finite number (`true`, `"0.01"`, NaN,
    inf) is a broken read - `M.as_float` collapses those to `None` too, and `tolerance_or_exact`
    refuses them rather than silently grading exact. `isinstance(tol, (int, float))` used to accept
    `true` and returned `0.0` for both cases, i.e. it invented a strict tolerance whenever the read
    failed (Defect 17 class on the grading path).
    """
    return M.as_float(answer_dict(it).get("tolerance"))


def tolerance_or_exact(it: dict) -> float:
    """The tolerance to grade with, or the exact-match floor `0.0` when the item declares none.

    Raises `ValueError` for a tolerance that is present but unreadable: that is a corrupt gold item,
    and grading it by exact match would deflate the §12 gate using an invented number.
    """
    ans = answer_dict(it)
    raw = ans.get("tolerance")
    if raw is None:
        return 0.0
    tol = M.as_float(raw)
    if tol is None:
        raise ValueError(f"gold item {it.get('id')!r} has an unreadable tolerance: {raw!r}")
    return tol


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
    tol = tolerance_or_exact(it)
    return all(numbers_match(v, tol, found) for v in exp)


MH_COMPONENTS = ("price", "publishers", "n_docs", "used_by_d", "date")
NUMERIC_COMPONENTS = ("price", "n_docs")


def multihop_components(it: dict) -> set[str]:
    """Which multihop components the gold item *requires*.

    Defect 28: presence used to be the only test, so a `n_docs`/`price` that is present but unreadable
    (`true`, `"5"`, `inf`) counted as a required component while the same value could never be
    *found*, deflating the §12 `multihop_f1` arm with a fabricated requirement. The numeric members
    go through `M.as_float`; the string/list members stay presence-tested.
    """
    ans = answer_dict(it)
    out = {k for k in MH_COMPONENTS if k not in NUMERIC_COMPONENTS
           and ans.get(k) not in (None, "", [], {})}
    for k in NUMERIC_COMPONENTS:
        if M.as_float(ans.get(k)) is not None:
            out.add(k)
    return out


def found_components(it: dict, rec: dict) -> set[str]:
    text = A.strip_cites(rec.get("answer") or "")
    low = text.lower()
    found_nums = [float(x) for x in A.numbers_in(text)]
    ans = answer_dict(it)
    out: set[str] = set()
    price = M.as_float(ans.get("price"))
    if price is not None and numbers_match(price, tolerance_or_exact(it), found_nums):
        out.add("price")
    pubs = ans.get("publishers") or []
    if pubs and any(str(p).lower() in low for p in pubs):
        out.add("publishers")
    n_docs = M.as_float(ans.get("n_docs"))
    if n_docs is not None and numbers_match(n_docs, 0.0, found_nums):
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


def judge_faithful(rec: dict, chat=None) -> float | None:
    """Faithfulness score only. See `judge_faithful_cost` to also capture the judge's spend.

    `None` means the judge could not grade the answer (it raised, or its reply was not a JSON
    verdict). `0.0` means it graded the answer and found nothing supported. Defect 21: conflating
    those two let a judge outage enter `faith_scores` as an unfaithful answer.
    """
    return judge_faithful_cost(rec, chat=chat)[0]


def judge_faithful_cost(rec: dict, chat=None) -> tuple[float | None, float | None]:
    """Judge one answer's faithfulness. Returns `(score, cost_usd)`.

    The cost is returned rather than discarded: `evaluate` used to sum only the per-record
    *answer* costs, so a judged run reported a `money_spent_usd` that excluded every judge
    call — the same class as Defect 15b (a paid phase invisible to its own report). The
    ledger stays authoritative; this keeps the report consistent with it.

    Defect 21 (P7 twin of `p6_summary.judge_node`): a judge that never answered used to return a
    **graded** `0.0`, indistinguishable from "the answer is unsupported" once `faith_scores` reaches
    `_mean` and `metrics["faithfulness"]` is compared with the §12 target of 0.95. The outage then
    surfaced only as a low faithfulness rate — misreported as unfaithfulness. An ungraded answer
    now yields `None` and is counted apart from the graded rows. One deliberate exception: a record
    with no evidence is a *measured* 0.0 (nothing is cited, so nothing in the answer can be
    supported) — a real domain zero, not a failed read, and it costs nothing because no call is made.
    """
    chat = chat or A._chat
    evidence = cite_evidence(rec)
    if not evidence:
        return 0.0, 0.0
    user = (f"QUESTION: {rec.get('question', '')}\n\n"
            f"ANSWER: {rec.get('answer', '')}\n\nEVIDENCE:\n{evidence}\n\nReturn JSON only.")
    cost: float | None = 0.0
    try:
        text, _usage, spent = chat(JUDGE_MODEL, [{"role": "system", "content": JUDGE_PROMPT},
                                                 {"role": "user", "content": user}], 400)
        cost = None if (cost is None or spent is None) else cost + float(spent)
        if not text and JUDGE_FALLBACK_MODEL:
            text, _usage, spent = chat(JUDGE_FALLBACK_MODEL,
                                       [{"role": "system", "content": JUDGE_PROMPT},
                                        {"role": "user", "content": user}], 400)
            cost = None if (cost is None or spent is None) else cost + float(spent)
    except Exception as exc:  # noqa: BLE001 - an unreadable judge is ungraded, never a graded 0.0
        rec["judge_error"] = f"{type(exc).__name__}: {exc}"
        return None, cost
    # Defect 21 (second face): `LR.parse_json_object` never raises -- unparseable text comes back as
    # `{}`. So `.get("supported", 0.0)` turned "the judge did not answer" into a GRADED 0.0, and the
    # `except (ValueError, TypeError)` clause below could never fire for the common case. The key
    # must actually be present for the answer to count as graded.
    payload = LR.parse_json_object(text)
    if "supported" not in payload:
        rec["judge_error"] = "bad_score:missing 'supported'"
        return None, cost
    val = payload["supported"]
    # Defect 22: the key being present is not enough if its value is off the prompt-declared scale.
    # `max(0.0, min(1.0, val))` coerced `{"supported": 3}` into a perfect 1.0 and `nan` into 1.0
    # (`min(1.0, nan)` is 1.0), i.e. a fabricated maximum on the `faithfulness >= 0.95` path.
    score = M.unit_score(val)
    if score is None:
        rec["judge_error"] = f"bad_score:{val!r}"
        return None, cost
    return score, cost


# --------------------------------------------------------------------------- run
def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _ratio(flags: list[bool]) -> float | None:
    return round(sum(1 for f in flags if f) / len(flags), 4) if flags else None


def build_report(items: list[dict], records: list[dict], recall_flags: list[bool],
                 mh_scores: list[float], faith_scores: list[float],
                 faith_ungraded: list[str] | None = None) -> dict:
    """Assemble the §12 metric/gate report. `faith_scores` holds GRADED rows only.

    Defect 21 (P7 twin): `faith_scores` used to absorb a judge outage as a graded 0.0. Ungraded
    rows are now passed in `faith_ungraded` and block the faithfulness gate exactly like
    `p6_summary.build_report` blocks P6 on `ungraded != 0` — a judge outage fails its own gate
    instead of masquerading as unfaithfulness.
    """
    ungraded = list(faith_ungraded or [])
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
        if key == "faithfulness" and ungraded:
            # Ungraded rows are not a metric value: the gate cannot pass on the rows the judge did
            # answer while an outage hides in the rest.
            gates[key] = {"value": value, "target": target, "pass": False,
                          "ungraded": len(ungraded), "ungraded_errors": sorted(set(ungraded))}
            continue
        gates[key] = {"value": value, "target": target,
                      "pass": None if value is None else value >= target}
    return {"phase": PHASE, "metrics": metrics, "gates": gates,
            "counts": {"items": len(items), "exact_graded": len(exact),
                       "recall_graded": len(recall_flags), "refusal_graded": len(refusals),
                       "multihop_graded": len(mh_scores), "faithfulness_graded": len(faith_scores),
                       "faithfulness_ungraded": len(ungraded)}}


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
        faith_ungraded: list[str] = []
        # `0.0` = no paid judge call made yet (measured zero); a call that cannot be priced flips the
        # whole figure to `None` (UNMEASURED) instead of shrinking it (Defect 17/21 class).
        judge_cost: float | None = 0.0
        if with_judge:
            candidates = [r for r in records if r.get("status") == "ok"]
            rng = random.Random(seed)
            sample = rng.sample(candidates, min(judge_sample, len(candidates)))
            for r in sample:
                r["faithfulness"], spent = judge_faithful_cost(r, chat=judge_chat)
                judge_cost = None if (judge_cost is None or spent is None) else judge_cost + spent
                # Defect 21: a None is an UNGRADED row (judge outage), never a graded zero. Keep it
                # out of the mean so the gate reports the outage instead of a low score.
                if r["faithfulness"] is None:
                    faith_ungraded.append(str(r.get("judge_error") or r.get("error")
                                              or "judge_did_not_grade"))
                else:
                    faith_scores.append(r["faithfulness"])
    finally:
        if own:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass

    report = build_report(items, records, recall_flags, mh, faith_scores, faith_ungraded)
    # Tri-state: an unpriced answer or judge call makes the whole spend figure UNMEASURED, never a
    # total that omits the call it could not price (Defect 17/21 class on the answer-cost limb).
    paid: float | None = 0.0
    for r in records:
        c = r.get("cost_usd")
        paid = None if (paid is None or c is None) else paid + float(c)
    cost: float | None = None if (paid is None or judge_cost is None) else paid + judge_cost
    report.update({"sample_seed": seed, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "wall_seconds": round(time.time() - t0, 1),
                   "money_spent_usd": None if cost is None else round(cost, 6),
                   "judge_cost_usd": None if judge_cost is None else round(judge_cost, 6),
                   "model": model, "judge_model": JUDGE_MODEL if with_judge else None,
                   "judged": len(faith_scores), "judged_ungraded": len(faith_ungraded),
                   "with_search": with_search,
                   "items": [{k: r.get(k) for k in ("item_id", "type", "question", "status",
                                                     "answer", "model", "escalated", "cost_usd")}
                              for r in records]})
    report["pass"] = bool(all(g["pass"] for g in report["gates"].values() if g["pass"] is not None)
                          and all(g["pass"] is True for g in report["gates"].values()))
    return report


def _md(report: dict) -> str:
    g = report["gates"]
    lines = ["# P7 eval — §12 gold-set scoring", "",
             f"- items: {report['counts']['items']} · wall: {report['wall_seconds']} s · "
             f"spend: {M.fmt_usd(report['money_spent_usd'])} "
             # Lesson 69: no default in a money renderer -- `.get('judge_cost_usd', 0.0)` printed a
             # fabricated $0.0000 if the key were ever absent. Missing now reads UNMEASURED.
             f"(judge {M.fmt_usd(report.get('judge_cost_usd'))})",
             f"- model: `{report['model']}` · judge: `{report['judge_model']}` · "
             f"judged: {report['judged']} graded"
             + (f" · {report['judged_ungraded']} UNGRADED" if report.get("judged_ungraded") else ""),
             f"- result: {'PASS' if report['pass'] else 'FAIL'}", "",
             "| metric | value | target | pass |", "|---|---|---|---|"]
    for k, target in TARGETS.items():
        v = g.get(k, {})
        lines.append(f"| {k} | {v.get('value')} | {target} | {v.get('pass')} |")
    lines += ["", "## Graded counts", ""]
    lines += [f"- {k}: {v}" for k, v in report["counts"].items()]
    if (g.get("faithfulness") or {}).get("ungraded_errors"):
        lines += ["", "## Judge outages (ungraded, not scored)",
                  ""] + [f"- {e}" for e in g["faithfulness"]["ungraded_errors"]]
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
