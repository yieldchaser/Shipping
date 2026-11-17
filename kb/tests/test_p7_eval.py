"""Tests for kb/p7_eval.py — §12 metric code, faithfulness judging, report + CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p7_eval as E  # noqa: E402


class DummyCon:
    def close(self):
        pass


def item(iid, typ, ans, **kw):
    d = {"id": iid, "type": typ, "question": kw.pop("q", f"question {iid}"),
         "answer": ans, "answer_text": kw.pop("answer_text", "")}
    d.update(kw)
    return d


# --------------------------------------------------------------------------- scoring
def test_gold_numbers_and_tolerance():
    it = item("G-1", "a_single_number", {"value": 24500.0, "unit": "usd/day", "tolerance": 50})
    assert E.gold_numbers(it) == [24500.0]
    assert E.tolerance_of(it) == 50.0
    assert E.numbers_match(24500.0, 50.0, [24490.0])
    assert not E.numbers_match(24500.0, 50.0, [24600.0])
    assert E.unit_of(it) == "usd/day"


def test_an_unreadable_authored_number_never_grades_a_wrong_answer_correct():
    """Defect 28. A gold number that is present but unreadable must leave the item *ungradable*.

    `gold_numbers` used `isinstance(v, (int, float))`, which admits `inf`. The item is then graded by
    `numbers_match(inf, tol, found)`, whose tolerance floor is `max(tol, abs(inf) * 1e-6) == inf`, so
    `abs(n - inf) <= inf` held for **every** candidate number and any answer text at all scored True
    on the §12 `exact_a_b_e_g` arm. `-inf` behaves the same; `nan` never matches and silently grades a
    correct answer False. All three are broken reads.
    """
    wrong = {"status": "ok", "answer": "completely wrong 12345 dollars"}
    # Non-vacuity: the real item still grades True/False as before.
    good = item("G-8", "a_single_number", {"value": 24500.0, "tolerance": 50})
    assert E.gold_numbers(good) == [24500.0]
    assert E.score_exact(good, {"status": "ok", "answer": "avg 24,500 usd/day"}) is True
    assert E.score_exact(good, wrong) is False

    for bad in (True, False, float("inf"), float("-inf"), float("nan"), "24500", [24500], {}):
        corrupt = item("G-9", "a_single_number", {"value": bad, "tolerance": 50})
        assert E.gold_numbers(corrupt) == [], bad
        # An empty expectation cannot grade, so the metric drops the item instead of crediting it.
        assert E.score_exact(corrupt, wrong) is None, bad
        assert E.score_exact(corrupt, {"status": "ok", "answer": "avg 24,500 usd/day"}) is None, bad

    # A token that overflows `float` on parse is a broken read too, not a fabricated expectation.
    assert E.gold_numbers_from_text("1" + "0" * 400) == []
    assert E.gold_numbers(item("G-10", "a_single_number", {}, answer_text="1" + "0" * 400)) == []
    # ... while real text still parses.
    assert E.gold_numbers_from_text("averaged 24,500 usd/day") == [24500.0]


def test_multihop_components_ignore_unreadable_numeric_members():
    """Defect 28 twin: a required component that is present but unreadable must not be required.

    `multihop_components` presence-tested `price`/`n_docs`, so `true`/`"5"`/`inf` inflated the
    denominator of the §12 `multihop_f1` arm with a component `found_components` could never award
    (it reads the same value through the finite rule).
    """
    good = E.multihop_components({"answer": {"price": 17.6, "n_docs": 5, "publishers": ["a"]}})
    assert good == {"price", "n_docs", "publishers"}  # non-vacuity

    for bad in (True, False, float("inf"), float("-inf"), float("nan"), "5", [5], {}):
        comps = E.multihop_components({"answer": {"price": bad, "n_docs": bad, "publishers": ["a"]}})
        assert comps == {"publishers"}, bad
        # Symmetry: the found-side reader must not award it either, or the two disagree.
        assert E.found_components({"answer": {"price": bad, "n_docs": bad}},
                                  {"status": "ok", "answer": "saw 5 docs at 17.6"}) == set(), bad

    assert E.found_components({"answer": {"n_docs": 5}},
                              {"status": "ok", "answer": "saw 5 docs"}) == {"n_docs"}

    """Absent and unreadable must not be collapsed into one invented `0.0`.

    Every live `c_multihop_entity` item (35/35) has no `tolerance` key: for that type the authoring
    convention *is* exact match, so its absence is declared semantics, not a failed read.
    """
    absent = item("G-5", "c_multihop_entity", {"price": 17.6, "publishers": ["broker_a"]})
    assert E.tolerance_of(absent) is None
    assert E.tolerance_or_exact(absent) == 0.0

    stated = item("G-6", "a_single_number", {"value": 1.0, "tolerance": 0})
    assert E.tolerance_of(stated) == 0.0          # an authored 0.0 is a real measurement
    assert E.tolerance_or_exact(stated) == 0.0

    # Present but not a real finite number: `true` used to be accepted by isinstance(True, int) and
    # grade exact; NaN/inf used to pass isinstance too. All three are broken reads, never a tolerance.
    for bad in (True, False, float("nan"), float("inf"), "0.01", [0.01]):
        corrupt = item("G-7", "a_single_number", {"value": 1.0, "tolerance": bad})
        assert E.tolerance_of(corrupt) is None, bad
        with pytest.raises(ValueError):
            E.tolerance_or_exact(corrupt)


def test_score_exact_single_number():
    it = item("G-1", "a_single_number", {"value": 24500.0, "tolerance": 10})
    assert E.score_exact(it, {"status": "ok", "answer": "Capesize averaged 24,500 usd/day."}) is True
    assert E.score_exact(it, {"status": "ok", "answer": "Capesize averaged 24,000 usd/day."}) is False
    assert E.score_exact(it, {"status": "not_in_data", "answer": "Not in the data."}) is False


def test_score_exact_window_and_as_of():
    b = item("G-2", "b_window_aggregate", {"value": 12.5, "tolerance": 0.1})
    assert E.score_exact(b, {"status": "ok", "answer": "rose 12.5 percent (12.4-12.6)"}) is True
    g = item("G-3", "g_as_known_on_date", {"value": 900.0, "tolerance": 0})
    assert E.score_exact(g, {"status": "ok", "answer": "on that date it was 900 [cite:obs:1]"}) is True


def test_score_exact_sec_section_uses_term():
    it = item("G-4", "e_sec_section", {"heading": "Fleet", "section_id": "s1", "term": "ice-class"})
    assert E.score_exact(it, {"status": "ok", "answer": "The Ice-Class fleet grew."}) is True
    assert E.score_exact(it, {"status": "ok", "answer": "Nothing relevant."}) is False
    assert E.score_exact(item("x", "f_summary_trend", {}), {}) is None


def test_multihop_f1():
    it = item("G-5", "c_multihop_entity",
              {"price": 17.6, "price_unit": "usd_m", "date": "2026-02-11",
               "publishers": ["broker_a"], "n_docs": 2, "used_by_d": "vessel:imo:1"})
    full = {"status": "ok",
            "answer": "broker_a reported 17.6 usd_m on 2026-02-11 in 2 docs on vessel:imo:1."}
    assert E.multihop_f1(it, full) == 1.0
    half = {"status": "ok", "answer": "broker_a reported 17.6 usd_m."}
    assert 0.0 < E.multihop_f1(it, half) < 1.0
    assert E.multihop_f1(it, {"status": "not_in_data", "answer": "Not in the data."}) == 0.0
    assert E.multihop_f1(item("x", "a_single_number", {}), full) is None


def test_refusal_scoring():
    it = item("G-6", "h_unanswerable", {"answerable": False, "gap_reason": "no data"})
    assert E.score_refusal(it, {"status": "not_in_data", "answer": "Not in the data."}) is True
    assert E.score_refusal(it, {"status": "ok", "answer": "It was 5."}) is False
    assert E.score_refusal(item("x", "a_single_number", {}), {}) is None


def test_recall_hit_uses_gold_doc_ids(monkeypatch):
    it = item("G-7", "a_single_number", {"value": 1}, sources=[{"doc_id": "d1"}])
    monkeypatch.setattr(E.T, "search", lambda q, k=20, con=None:
                        {"results": [{"doc_id": "d9"}, {"doc_id": "d1"}]})
    assert E.recall_hit(it, DummyCon()) is True
    monkeypatch.setattr(E.T, "search", lambda q, k=20, con=None: {"results": [{"doc_id": "d9"}]})
    assert E.recall_hit(it, DummyCon()) is False
    assert E.recall_hit(item("x", "a_single_number", {}), DummyCon()) is None


# --------------------------------------------------------------------------- judge
def _chat(replies):
    seq = list(replies)

    def chat(model, messages, max_tokens=400, **kw):
        return seq.pop(0) if seq else '{"supported": 0.0}', {}, 0.0

    return chat


def test_judge_faithful_parses_json():
    rec = {"question": "q", "answer": "a", "evidence": ["quote 1"], "sentences": []}
    assert E.judge_faithful(rec, chat=_chat(['{"supported": 0.75}'])) == 0.75
    # Defect 21: unparseable judge output is UNGRADED (None), not a graded 0.0.
    assert E.judge_faithful(rec, chat=_chat(["not json"])) is None
    assert E.judge_faithful({"evidence": []}, chat=_chat(['{"supported": 1.0}'])) == 0.0


def test_judge_faithful_rejects_an_off_scale_score():
    """Defect 22: the prompt declares `supported` in [0, 1]; a value off that scale is a failed read.

    The old `max(0.0, min(1.0, val))` coerced `{"supported": 3}` into a perfect 1.0 and `nan` into
    1.0 (`min(1.0, nan)` is 1.0) -- a fabricated maximum on the `faithfulness >= 0.95` path. Both
    must be UNGRADED (`None`) with `judge_error` set, like the missing-key case.
    """
    rec = {"question": "q", "answer": "a", "evidence": ["quote 1"], "sentences": []}
    for bad in (3, -0.4, "0.9", True, float("nan"), float("inf"), float("-inf")):
        out = dict(rec)
        assert E.judge_faithful(out, chat=_chat([json.dumps({"supported": bad})])) is None, bad
        assert out["judge_error"].startswith("bad_score"), (bad, out["judge_error"])
    # The floor stays a real measured zero, not an unusable read.
    assert E.judge_faithful(rec, chat=_chat(['{"supported": 0.0}'])) == 0.0


def test_cite_evidence_collects_quotes():
    rec = {"evidence": ["e1"], "sentences": [{"quote": "q1"}, {"quote": "q2"}]}
    txt = E.cite_evidence(rec)
    assert "e1" in txt and "q1" in txt


# --------------------------------------------------------------------------- evaluate
GOLD = [
    item("G-1", "a_single_number", {"value": 24500.0, "tolerance": 10},
         sources=[{"doc_id": "d1"}]),
    item("G-2", "b_window_aggregate", {"value": 12.5, "tolerance": 0.1}),
    item("G-3", "c_multihop_entity", {"price": 17.6, "publishers": ["broker_a"]},
         sources=[{"doc_id": "d2"}]),
    item("G-4", "h_unanswerable", {"answerable": False}),
]

REPLIES = {
    "G-1": {"status": "ok", "answer": "24,500 usd/day [cite:obs:1]", "cost_usd": 0.0},
    "G-2": {"status": "ok", "answer": "rose 12.5 percent", "cost_usd": 0.0},
    "G-3": {"status": "ok", "answer": "broker_a reported 17.6 usd_m [cite:txn:1]", "cost_usd": 0.0},
    "G-4": {"status": "not_in_data", "answer": "Not in the data.", "cost_usd": 0.0},
}


@pytest.fixture()
def patched(monkeypatch):
    monkeypatch.setattr(E.T, "connect", lambda db=None: DummyCon())
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: dict(REPLIES[q.split()[-1]]))
    monkeypatch.setattr(E.T, "search", lambda q, k=20, con=None:
                        {"results": [{"doc_id": "d1"}, {"doc_id": "d2"}]})
    return monkeypatch


def test_evaluate_metrics_and_pass(patched):
    rep = E.evaluate(GOLD, with_search=False, with_judge=False)
    assert rep["metrics"]["exact_match_numeric"] == 1.0
    assert rep["metrics"]["refusal_gap_accuracy"] == 1.0
    assert rep["metrics"]["multihop_f1"] == 1.0
    assert rep["metrics"]["retrieval_recall_at_20"] is None
    assert rep["counts"]["items"] == 4
    assert rep["phase"] == "P7" and rep["sample_seed"] == E.seed_for("P7")
    # Two independent reasons to FAIL: the skipped recall metric and the 4-item fixture against the
    # frozen `qa_gold_questions: 250` count arm (Defect 40). The count arm is reported separately;
    # this fixture legitimately cannot reach 250, and loosening the arm to make it green would be a
    # silent scope cut.
    assert rep["pass"] is False
    assert rep["gates"]["retrieval_recall_at_20"]["pass"] is None
    assert rep["question_count"]["target"] == 250 and rep["question_count"]["pass"] is False


def test_evaluate_with_search_and_judge(patched, monkeypatch):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})
    rep = E.evaluate(GOLD, with_search=True, with_judge=True, judge_chat=_chat(['{"supported": 1.0}'] * 5))
    assert rep["metrics"]["retrieval_recall_at_20"] == 1.0
    assert rep["metrics"]["faithfulness"] == 1.0
    assert rep["judged"] == 3
    # Every §12 metric arm passes on this fixture ...
    assert all(g["pass"] is True for g in rep["gates"].values()), rep["gates"]
    # ... and the run still FAILS as a whole, because 4 questions are not the frozen 250. The metric
    # arms are graded independently of the count so a smoke run cannot be presented as the §12 result.
    assert rep["question_count"] == {"value": 4, "target": 250, "pass": False}
    assert rep["pass"] is False
    assert rep["money_spent_usd"] == 0.0
    assert rep["judge_cost_usd"] == 0.0


def test_evaluate_report_spend_includes_the_judge_it_paid_for(patched, monkeypatch):
    """The report summed only per-answer costs, so a judged run hid every judge dollar."""
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"], "cost_usd": 0.01})

    def pricey_chat(model, messages, max_tokens=400, **kw):
        return '{"supported": 1.0}', {}, 0.005

    rep = E.evaluate(GOLD, with_search=False, with_judge=True, judge_chat=pricey_chat)
    assert rep["judged"] == 3
    assert rep["judge_cost_usd"] == pytest.approx(0.015)      # 3 judge calls x $0.005
    assert rep["money_spent_usd"] == pytest.approx(0.01 * 4 + 0.015)


def test_judge_faithful_cost_reports_score_and_spend(monkeypatch):
    rec = {"question": "q", "answer": "a", "evidence": ["quote 1"], "sentences": []}
    score, cost = E.judge_faithful_cost(rec, chat=_chat(['{"supported": 0.75}']))
    assert score == 0.75 and cost == 0.0                     # stub returns cost 0.0

    def paid(model, messages, max_tokens=400, **kw):
        return '{"supported": 0.5}', {}, 0.002

    score, cost = E.judge_faithful_cost(rec, chat=paid)
    assert score == 0.5 and cost == pytest.approx(0.002)
    # no evidence => no call => no spend; a MEASURED zero, not an ungraded read
    assert E.judge_faithful({"evidence": []}, chat=paid) == 0.0
    assert E.judge_faithful_cost({"evidence": []}, chat=paid) == (0.0, 0.0)


def test_judge_faithful_reports_a_judge_outage_as_ungraded(monkeypatch):
    """Defect 21 (P7 twin): a dead judge used to return a graded 0.0, i.e. 'unfaithful'."""
    rec = {"question": "q", "answer": "a", "evidence": ["quote 1"], "sentences": []}

    def dead(model, messages, max_tokens=400, **kw):
        raise RuntimeError("429 rate limited")

    assert E.judge_faithful(rec, chat=dead) is None
    assert E.judge_faithful_cost(rec, chat=dead) == (None, 0.0)

    def garbled(model, messages, max_tokens=400, **kw):
        return "the judge made no json", {}, 0.001

    score, cost = E.judge_faithful_cost(rec, chat=garbled)
    assert score is None, "an unparseable verdict is ungraded, not a 0.0 grade"
    assert cost == pytest.approx(0.001), "the call still cost money and must be booked"


def test_an_unpriceable_judge_call_makes_the_report_spend_unmeasured(patched, monkeypatch):
    """Defect 17/21 class on the money limb: `None` must not be summed as a measured `0.0`."""
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"], "cost_usd": 0.0})

    def unpriced(model, messages, max_tokens=400, **kw):
        return '{"supported": 1.0}', {}, None      # provider reported no usage

    rep = E.evaluate(GOLD, with_search=False, with_judge=True, judge_chat=unpriced)
    assert rep["judged"] == 3, "the verdict still grades; only the money is unmeasured"
    assert rep["judge_cost_usd"] is None and rep["money_spent_usd"] is None
    assert "UNMEASURED" in E._md(rep)

    def unpriced_answer(q, model=None, con=None, chat=None):
        return {**REPLIES[q.split()[-1]], "evidence": ["quote"], "cost_usd": None}

    monkeypatch.setattr(E.A, "answer_question", unpriced_answer)
    rep2 = E.evaluate(GOLD, with_search=False, with_judge=False)
    assert rep2["money_spent_usd"] is None, "one unpriced answer unmeasures the whole run"


def test_a_dead_judge_fails_its_own_gate_not_the_faithfulness_metric(patched, monkeypatch):
    """Defect 21 end to end: the outage must surface as UNGRADED, never as a low faithfulness."""
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})

    def dead(model, messages, max_tokens=400, **kw):
        raise RuntimeError("429 rate limited")

    rep = E.evaluate(GOLD, with_search=False, with_judge=True, judge_chat=dead)
    assert rep["counts"]["faithfulness_graded"] == 0
    assert rep["counts"]["faithfulness_ungraded"] == 3
    assert rep["metrics"]["faithfulness"] is None, "no grade => no mean, never a 0.0 mean"
    assert rep["gates"]["faithfulness"]["pass"] is False
    assert rep["judged"] == 0 and rep["judged_ungraded"] == 3
    assert rep["pass"] is False
    md = E._md(rep)
    assert "UNGRADED" in md and "429 rate limited" in md


def test_evaluate_handles_pipeline_errors(patched):
    def boom(q, model=None, con=None, chat=None):
        raise RuntimeError("model down")

    patched.setattr(E.A, "answer_question", boom)
    rep = E.evaluate(GOLD, with_search=False, with_judge=False)
    assert rep["metrics"]["exact_match_numeric"] == 0.0
    # Defect 7: a `model_error` is an infrastructure failure, NOT a correct refusal. Only a genuine
    # `not_in_data` answer counts, so the sole (h) item is ungraded rather than credited.
    assert rep["metrics"]["refusal_gap_accuracy"] == 0.0
    assert rep["items"][0]["status"] == "model_error"


def test_md_and_report_files(patched, monkeypatch, tmp_path):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})
    rep = E.evaluate(GOLD, with_search=True, with_judge=True, judge_chat=_chat(['{"supported": 1.0}'] * 5))
    md = E._md(rep)
    assert "| exact_match_numeric |" in md, md
    # The metric arms all pass, but the run result is FAIL on the 4-question count arm (Defect 40),
    # and both facts must be visible in the render: a smoke run cannot read as a PASS.
    assert all(g["pass"] is True for g in rep["gates"].values())
    assert "- result: FAIL" in md and "qa_gold_questions" in md, md
    assert "| exact_match_numeric | 1.0 | 0.97 | yes |" in md, md
    assert "D16" in md
    out = tmp_path / "eval.json"
    out.write_text(json.dumps(rep), encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8"))["metrics"]["refusal_gap_accuracy"] == 1.0


def test_main_cli_exit_codes(patched, monkeypatch, tmp_path):
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"items": GOLD}), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr(E, "REPORTS", tmp_path / "reports")
    rep = {"metrics": {k: 1.0 for k in E.TARGETS}, "gates": {},
           "counts": {"items": 4},
           "pass": True, "wall_seconds": 1.0, "money_spent_usd": 0.0,
           "model": "m", "judge_model": None, "judged": 0, "items": []}
    monkeypatch.setattr(E, "evaluate", lambda *a, **k: dict(rep))
    rc = E.main(["--gold", str(gold), "--out", str(out), "--report", "--no-search", "--no-judge"])
    assert rc == 0 and out.exists()
    assert (tmp_path / "reports" / "p7_eval.json").exists()
    rep_fail = dict(rep, pass_=False)
    rep_fail["pass"] = False
    monkeypatch.setattr(E, "evaluate", lambda *a, **k: rep_fail)
    assert E.main(["--gold", str(gold), "--out", str(out)]) == 1


def test_main_empty_gold(tmp_path):
    gold = tmp_path / "gold.json"
    gold.write_text('{"items": []}', encoding="utf-8")
    assert E.main(["--gold", str(gold)]) == 2


# ------------------------------------------------------------------ Defect 35
BIG = float("1" + "0" * 400)


def test_eval_mean_and_ratio_reject_unreadable_members():
    """Defect 35 (P7 eval twin of Defect 34): the producers admitted `True` and `inf`.

    `_mean` was `sum(xs)/len(xs)`: a `True` counts as 1, and one overflowed member drags the §12 arm
    past its target. `_ratio` counted *any* truthy flag -- the string `"false"` scored as a hit.
    """
    assert E._mean([0.5, 0.7]) == 0.6
    assert E._mean([0.5, True]) == 0.5
    assert E._mean([0.5, float("inf"), float("nan"), "0.7"]) == 0.5
    assert E._mean([0.5, BIG]) == 0.5
    assert E._mean([True, float("inf"), "x", None]) is None
    assert E._mean([]) is None
    assert E._ratio([True, False, True, True]) == 0.75
    assert E._ratio([True, "false", 1, None, BIG]) == 1.0, "only real bools count"
    assert E._ratio([]) is None and E._ratio(["false", 0]) is None
    assert E._r(BIG) == "n/a" and E._r(float("nan")) == "n/a" and E._r(0.75) == "0.75"
    assert E._json_safe({"a": [1.0, BIG], "b": float("nan")}) == {"a": [1.0, None], "b": None}


def test_an_unreadable_faithfulness_score_cannot_pass_the_gate(patched, monkeypatch):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"], "cost_usd": 0.0})
    # a judge reply whose `supported` literal overflows to inf -> `unit_score` rejects -> UNGRADED
    rep = E.evaluate(GOLD, with_search=False, with_judge=True,
                     judge_chat=_chat(['{"supported": 1' + "0" * 400 + '}'] * 5))
    assert rep["counts"]["faithfulness_graded"] == 0
    assert rep["metrics"]["faithfulness"] is None
    assert rep["gates"]["faithfulness"]["pass"] is False
    assert rep["pass"] is False


def test_no_unreadable_value_reaches_the_eval_artefact(patched, monkeypatch, tmp_path):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})
    rep = E.evaluate(GOLD, with_search=True, with_judge=False)
    rep["wall_seconds"] = BIG
    rep["metrics"] = {k: BIG for k in E.TARGETS}
    rep["counts"]["items"] = BIG
    rep["gates"] = {k: {"value": BIG, "target": t, "pass": True} for k, t in E.TARGETS.items()}
    md = E._md(rep)
    assert "inf" not in md and "Infinity" not in md and "nan" not in md
    assert "wall: n/a s" in md
    for k in E.TARGETS:
        assert f"| {k} | n/a | {E.TARGETS[k]} | n/a |" in md, md
    assert "- items: n/a" in md
    # an honest run still renders its real numbers and derives real verdicts
    good = E.evaluate(GOLD, with_search=True, with_judge=False)
    gmd = E._md(good)
    assert "| refusal_gap_accuracy | 1.0 | 0.95 | yes |" in gmd
    # a faithfulness outage keeps its deliberate ungraded NO, and a low-but-read value is a real NO
    low = dict(good)
    low["gates"] = {"faithfulness": {"value": 0.5, "target": 0.95, "pass": False},
                    "refusal_gap_accuracy": {"value": 1.0, "target": 0.95, "pass": True}}
    lmd = E._md(low)
    assert ("| faithfulness | 0.5 | 0.95 | NO |" in lmd
            and "| refusal_gap_accuracy | 1.0 | 0.95 | yes |" in lmd)
    ung = dict(good)
    ung["gates"] = {"faithfulness": {"value": 0.99, "target": 0.95, "pass": False, "ungraded": 2}}
    assert "| faithfulness | 0.99 | 0.95 | NO |" in E._md(ung)


def test_main_json_artefact_never_writes_infinity(patched, monkeypatch, tmp_path):
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"items": GOLD}), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr(E, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(E, "evaluate", lambda *a, **k: {
        "metrics": {k: BIG for k in E.TARGETS}, "gates": {}, "counts": {"items": BIG},
        "pass": False, "wall_seconds": BIG, "money_spent_usd": None,
        "model": "m", "judge_model": None, "judged": 0, "items": [{"cost_usd": BIG}]})
    assert E.main(["--gold", str(gold), "--out", str(out), "--report",
                   "--no-search", "--no-judge"]) == 1
    for path in (out, tmp_path / "reports" / "p7_eval.json"):
        text = path.read_text(encoding="utf-8")
        assert "Infinity" not in text and "NaN" not in text, path
        assert json.loads(text)["items"][0]["cost_usd"] is None
    assert "n/a" in (tmp_path / "reports" / "p7_eval.md").read_text(encoding="utf-8")
