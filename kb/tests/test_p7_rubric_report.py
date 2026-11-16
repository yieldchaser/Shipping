"""Tests for kb/p7_rubric.py and kb/p7_report.py."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p7_rubric as R  # noqa: E402
import p7_report as P  # noqa: E402


class DummyCon:
    def close(self):
        raise AssertionError("run() must not close a caller-owned connection")


def ok_rec(**kw):
    rec = {"status": "ok", "answer": "facts ... [cite:obs:1]", "model": "ultrafast",
           "escalated": False, "cost_usd": 0.01, "confidence": 0.6,
           "indicators": {"indicators": [{"name": "earnings_pct_rank", "status": "ok"}]},
           "dropped": {"sentences": 0}}
    rec.update(kw)
    return rec


GOOD_JUDGE = {"facts_cited": 1.0, "indicators_correct": 1.0, "judgment_reasoned": 0.9,
              "counter_argument_present": 0.8, "score": 0.9, "notes": "fine"}


# ------------------------------------------------------------------ p7_rubric
def test_questions_grid():
    qs = R.questions(30)
    assert len(qs) == 30
    assert [q["id"] for q in qs][:3] == ["A-001", "A-002", "A-003"]
    assert len({q["question"] for q in qs}) == 30
    assert len({q["segment"] for q in qs}) >= 10
    assert all("{seg}" not in q["question"] for q in qs)
    assert len(R.questions(5)) == 5


def test_rubric_fields():
    got = R.rubric_fields(dict(GOOD_JUDGE))
    assert got["score"] == 0.9 and got["notes"] == "fine"
    part = R.rubric_fields({"facts_cited": 1.0, "indicators_correct": 0.5,
                            "judgment_reasoned": 0.5, "counter_argument_present": 0.0})
    assert part["score"] == 0.5
    assert R.rubric_fields({})["score"] is None


def test_run_grades_and_passes(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), 0.0))
    rep = R.run(con=DummyCon())
    assert rep["counts"]["questions"] == 30 and rep["counts"]["graded"] == 30
    assert rep["mean_score"] == 0.9 and rep["pass"] is True
    assert rep["field_means"]["counter_argument_present"] == 0.8
    assert abs(rep["money_spent_usd"] - 0.30) < 1e-9
    assert "PASS" in R._md(rep) and "D19" in R._md(rep)


def test_run_fails_on_low_scores(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost",
                        lambda *a, **k: ({**GOOD_JUDGE, "score": 0.5}, 0.0))
    rep = R.run(con=DummyCon())
    assert rep["mean_score"] == 0.5 and rep["pass"] is False


def test_run_counts_ungraded_as_fail(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec(status="not_enough_data"))
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), 0.0))
    rep = R.run(con=DummyCon())
    assert rep["counts"]["graded"] == 0 and rep["pass"] is False
    assert rep["counts"]["not_enough_data"] == 30


# ------------------------------------------------------------------ Defect 17
def test_clamp_score_rejects_unusable_judge_scores():
    """An LLM-provided score is untrusted input; only numbers inside [0, 1] are usable."""
    assert R.clamp_score(0.9) == 0.9
    assert R.clamp_score(1) == 1.0
    assert R.clamp_score(0.0) == 0.0
    assert R.clamp_score(3) is None, "an off-scale score is a failed read, never a coerced 1.0"
    assert R.clamp_score(-2) is None, "an off-scale score is never a coerced 0.0"
    assert R.clamp_score(None) is None
    assert R.clamp_score("0.9") is None, "a stringified number is not a usable score"
    assert R.clamp_score(True) is None, "bool is an int subclass but not a score"
    assert R.clamp_score(float("nan")) is None
    assert R.clamp_score(float("inf")) is None, "min(1.0, inf) is 1.0 -- a fabricated maximum"
    assert R.clamp_score(float("-inf")) is None


def test_rubric_fields_clamps_every_field():
    got = R.rubric_fields({"facts_cited": 5, "indicators_correct": "1.0",
                           "judgment_reasoned": 0.4, "counter_argument_present": True,
                           "score": 99})
    assert got["facts_cited"] is None, "off-scale field is a failed read, not a coerced 1.0"
    assert got["indicators_correct"] is None
    assert got["counter_argument_present"] is None
    assert got["judgment_reasoned"] == 0.4
    # `score` is unusable, so it falls back to the mean of the fields that *were* readable -- never
    # to a coerced 1.0 (Defect 22).
    assert got["score"] == 0.4, "unusable judge score falls back to readable fields only"
    assert not isinstance(got["score"], bool)


def test_run_does_not_let_an_out_of_range_score_pass_the_gate(monkeypatch):
    """Defect 17/22: `"score": 3` used to be clamped to 1.0 and flip PASS on its own."""
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost",
                        lambda *a, **k: ({"facts_cited": 3, "indicators_correct": 3,
                                          "judgment_reasoned": 3, "counter_argument_present": 3,
                                          "score": 3}, 0.0))
    rep = R.run(con=DummyCon())
    # Every field is off the declared scale, so nothing was actually graded: the honest report is
    # UNGRADED, which must not be able to read as a PASS.
    assert rep["counts"]["graded"] == 0
    assert rep["mean_score"] is None
    assert rep["field_means"]["facts_cited"] is None


def test_run_marks_an_unusable_judge_verdict_ungraded(monkeypatch):
    """No usable score *and* no usable fields: the judge effectively did not grade."""
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost",
                        lambda *a, **k: ({"score": "0.9", "facts_cited": "yes",
                                          "indicators_correct": None}, 0.0))
    rep = R.run(con=DummyCon(), n=4)
    c = rep["counts"]
    assert c["graded"] == 0 and c["ungraded_ok"] == 4 and c["ok"] == 4
    assert c["buckets_sum"] == c["questions"] and c["balanced"] is True
    assert rep["pass"] is False, "ungraded-but-ok rows must block the gate"
    md = R._md(rep)
    assert "UNBALANCED" not in md and "balanced" in md


def test_rubric_fields_falls_back_to_the_field_mean_when_score_is_missing():
    """A judge that omits `score` but scores every field is still graded, by the field mean."""
    got = R.rubric_fields({**GOOD_JUDGE, "score": "0.9"})
    assert got["score"] == pytest.approx(0.925)
    assert got["facts_cited"] == 1.0


def test_run_buckets_always_sum_to_the_question_count(monkeypatch):
    """Every question lands in exactly one bucket, whatever the producer/judge combination."""
    statuses = ["ok", "not_enough_data", "not_in_data", "malformed", "weird_status"]
    seq = iter(statuses)

    def analyse(*a, **k):
        return ok_rec(status=next(seq))

    monkeypatch.setattr(R.PA, "analyse", analyse)
    monkeypatch.setattr(R.PA, "judge_answer_cost",
                        lambda *a, **k: ({**GOOD_JUDGE, "score": 3}, 0.0))
    rep = R.run(con=DummyCon(), n=5)
    c = rep["counts"]
    assert c["questions"] == 5 and c["buckets_sum"] == 5 and c["balanced"] is True
    assert c["graded"] == 1 and c["ungraded_ok"] == 1, "the unrecognised status is not silently ok"
    assert c["not_enough_data"] == 1 and c["not_in_data"] == 1 and c["malformed"] == 1
    assert rep["pass"] is False


def test_run_judge_error_is_counted_and_blocks_the_gate(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())

    def bad(*a, **k):
        raise ValueError("bad json")

    monkeypatch.setattr(R.PA, "judge_answer_cost", bad)
    rep = R.run(con=DummyCon(), n=3)
    c = rep["counts"]
    assert c["ungraded_ok"] == 3 and c["judge_error"] == 3 and c["graded"] == 0
    assert c["buckets_sum"] == 3 and c["balanced"] is True
    assert rep["pass"] is False
    assert "ungraded: 3" in R._md(rep)


def test_run_records_errors(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(R.PA, "analyse", boom)
    rep = R.run(con=DummyCon(), n=3)
    assert rep["counts"]["failures"] == 3 and rep["pass"] is False
    assert all(i["status"] == "error" for i in rep["items"])


def test_run_judge_error_is_ungraded(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())

    def bad(*a, **k):
        raise ValueError("bad json")

    monkeypatch.setattr(R.PA, "judge_answer_cost", bad)
    rep = R.run(con=DummyCon(), n=2)
    assert rep["counts"]["graded"] == 0 and rep["items"][0]["judged"] is False
    assert "judge_error" in rep["items"][0]


# ------------------------------------------------------------------ Defect 19 (rubric half)
def test_run_report_spend_includes_the_rubric_judge(monkeypatch):
    """The rubric report summed only analyst costs, so every judge dollar was invisible."""
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), 0.004))
    rep = R.run(con=DummyCon())
    assert rep["counts"]["graded"] == 30
    assert rep["judge_cost_usd"] == pytest.approx(0.004 * 30)
    assert rep["money_spent_usd"] == pytest.approx(0.01 * 30 + 0.004 * 30)
    md = R._md(rep)
    assert "analyst $0.3000 + judge $0.1200" in md, md


def test_an_unpriced_judge_call_leaves_the_judge_cost_unmeasured(monkeypatch):
    """`judge_cost` must carry its own tri-state, independently of the analyst money.

    `judge_answer_cost` returns `(verdict, None)` when the call succeeded but its price could not
    be read (Defect 17/21 class: an unreadable price on a *made* call). Folding that `None` to
    `0.0` would book the judge as free in the C2 approval artefact -- the same fabricated
    measured-zero the cap readers were fixed for.
    """
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), None))
    rep = R.run(con=DummyCon(), n=2)
    assert rep["counts"]["graded"] == 2, "the verdict still grades; only the money is unmeasured"
    assert rep["judge_cost_usd"] is None
    assert rep["money_spent_usd"] is None, "an unmeasured judge dollar must not vanish from the total"
    assert "UNMEASURED" in R._md(rep)


def test_a_measured_zero_judge_cost_is_not_unmeasured(monkeypatch):
    """The `None` guard must not swallow a genuine `0.0` — a judged call really can be free."""
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), 0.0))
    rep = R.run(con=DummyCon(), n=2)
    assert rep["judge_cost_usd"] == 0.0
    assert rep["money_spent_usd"] == pytest.approx(0.01 * 2), "only the judge was free, not the analyst"


def test_unmeasured_analyst_money_does_not_hide_a_measured_judge_cost(monkeypatch):
    """The two axes are independent: one unmeasured item must not null the judge's own figure.

    `money_spent_usd` goes `None` (some analyst call is unpriced), but `judge_cost_usd` was fully
    priced and must still be reported as the number it measured.
    """
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec(cost_usd=None))
    monkeypatch.setattr(R.PA, "judge_answer_cost", lambda *a, **k: (dict(GOOD_JUDGE), 0.004))
    rep = R.run(con=DummyCon(), n=2)
    assert rep["money_spent_usd"] is None
    assert rep["judge_cost_usd"] == pytest.approx(0.008)


def _fenced(model, messages, max_tokens=500, **kw):
    return ('```json\n{"score": 1.0}\n```', {}, 0.0)


def test_judge_answer_cost_accumulates_the_fallback_attempt():
    """A blank first reply falls back to the other family: both calls are spend."""
    import p7_analyst as PA

    seen = []

    def chat(model, messages, max_tokens=500, **kw):
        seen.append(model)
        return ("", {}, 0.001) if len(seen) == 1 else ('{"score": 1.0}', {}, 0.002)

    verdict, cost = PA.judge_answer_cost("q", {"answer": "a"}, chat=chat)
    assert seen == [PA.JUDGE_MODEL, PA.JUDGE_FALLBACK_MODEL]
    assert verdict == {"score": 1.0} and cost == pytest.approx(0.003)
    # the score-only wrapper keeps its old contract, fenced reply included (Defect 16)
    assert PA.judge_answer("q", {"answer": "a"}, chat=_fenced) == {"score": 1.0}


def test_main_writes_out(tmp_path, monkeypatch):
    rep = R.run.__self__ if False else None  # noqa: F841 - keep linters quiet
    monkeypatch.setattr(R, "run", lambda **k: {"phase": "P7", "pass": True,
                                               "counts": {"questions": 30, "graded": 30},
                                               "mean_score": 0.9})
    out = tmp_path / "rubric.json"
    rc = R.main(["--out", str(out)])
    assert rc == 0 and json.loads(out.read_text(encoding="utf-8"))["mean_score"] == 0.9
    monkeypatch.setattr(R, "run", lambda **k: {"phase": "P7", "pass": False})
    assert R.main(["--out", str(tmp_path / "x.json")]) == 1


# ------------------------------------------------------------------ p7_report
def good_eval():
    return {"metrics": {k: min(1.0, v + 0.01) for k, v in P.TARGETS.items()},
            "counts": {"items": 250}, "model": "ultrafast", "judge_model": "gpt-oss-120b"}


def good_rubric():
    return {"mean_score": 0.86, "counts": {"graded": 30},
            "field_means": {"facts_cited": 0.95}, "judge_model": "gpt-oss-120b"}


def good_backtest():
    return {"segments": [{"segment": "capesize", "dates": 20, "n": 30, "hits": 18},
                         {"segment": "vlcc", "dates": 20, "n": 10, "hits": 6}]}


def good_discovery(n: int = 30):
    return {"counts": {"findings": n, "survivors": n + 5, "written": n + 5},
            "findings": [{"kind": "lead_lag", "a": "commodity_iron_ore", "b": "freight_dry",
                          "stat": 0.4, "q": 0.01, "n": 30, "window_from": "2020-01-01",
                          "window_to": "2024-12-01", "evidence": ["series:a", "series:b"]}
                         for _ in range(n)],
            "questions": [{"id": f"Q-{i:02d}", "kind": "lead_lag", "hops": 3,
                           "question": f"question {i}"} for i in range(20)]}


def test_build_passes():
    rep = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 12.5, 100.0)
    assert rep["pass"] is True and rep["gate"]["p7"] is True
    assert rep["counts"]["eval_items"] == 250 and rep["counts"]["discovered_links"] == 35
    assert rep["money_spent_usd"] == 12.5 and rep["wall_seconds"] == 100.0


@pytest.mark.parametrize("mutate", ["eval", "rubric", "backtest", "discovery"])
def test_build_fails_per_component(mutate):
    ev, rb, bt, dc = good_eval(), good_rubric(), good_backtest(), good_discovery()
    if mutate == "eval":
        ev["metrics"]["recall_at_20"] = 0.10
    elif mutate == "rubric":
        rb["counts"]["graded"] = 29
    elif mutate == "backtest":
        bt = {"dates": 5, "hit_rate": 0.5, "n": 5}
    else:
        dc = good_discovery(29)
    rep = P.build(ev, rb, bt, dc, 1.0)
    assert rep["pass"] is False and rep["checks"][mutate]["ok"] is False
    assert "FAIL" in P._md(rep)


def test_build_all_missing():
    rep = P.build(None, None, None, None, 0.0)
    assert rep["pass"] is False
    assert all(not c["ok"] for c in rep["checks"].values())
    md = P._md(rep)
    for d in ("D16", "D17", "D18", "D19", "D20"):
        assert d in md


def test_a_bool_or_nonfinite_metric_can_never_pass_a_gate():
    """Defect 24: the gate-verdict read of an on-disk metric was a bare `isinstance(v, (int, float))`.

    `isinstance(True, (int, float))` is True, so an artefact JSON holding `"recall_at_20": true` read as
    the number 1 and passed a §12 target; `inf >= target` is also True, so an overflow-to-inf metric
    passed. Both then flipped `report["pass"]` and the C2 packet's `Recommend publishing the snapshot
    and starting P8.` — the one line that authorises the release. NaN was silently a FAIL, which is the
    same broken read from the other side. This is the Defect-23 shape moved from money/config reads to
    the gate-verdict reads, so the read must go through `money.unit_score`.
    """
    # Non-vacuity: a real in-range metric still reads as itself, and the shared grade rule is reached.
    assert P._metric(0.96) == 0.96
    assert P._metric(1.0) == 1.0
    assert P._metric(0) == 0.0
    # Broken reads: bool, non-finite, non-numeric, and off a `[0, 1]` metric scale.
    for bad in (True, False, float("nan"), float("inf"), float("-inf"), "0.96", [0.96], None, 1.5, -0.1):
        assert P._metric(bad) is None, bad

    # Every metric of the eval artefact, one arm per bad value.
    for bad in (True, float("nan"), float("inf"), "0.96"):
        ev = good_eval()
        for k in P.TARGETS:
            ev["metrics"][k] = bad
        c = P.check_eval(ev)
        assert c["ok"] is False, (bad, k)
        assert all(g["ok"] is False for g in c["gates"].values()), (bad, c["gates"])

    # The rubric mean is a gate input too (`>= RUBRIC_TARGET`), same three broken reads.
    for bad in (True, float("nan"), float("inf"), "0.86"):
        c = P.check_rubric({"mean_score": bad, "counts": {"graded": 30}})
        assert c["ok"] is False, bad
    assert P.check_rubric(good_rubric())["ok"] is True  # non-vacuity: the good arm still passes

    # End to end: the poisoned metric reaches the owner-facing recommendation line.
    ev = good_eval()
    ev["metrics"]["recall_at_20"] = float("inf")
    rep = P.build(ev, good_rubric(), good_backtest(), good_discovery(), 1.0, 1.0)
    assert rep["pass"] is False and rep["gate"]["p7"] is False
    c2 = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), ev)
    assert "Do not publish yet." in c2 and "Recommend publishing" not in c2
    # Defect 34 changed this render from the raw `inf` to the unmeasured `n/a` (the guarded read now
    # reaches the packet); the arm is still visibly FAIL and still does not authorise the release.
    assert "n/a (target 0.85) — FAIL" in c2 and "inf (target 0.85)" not in c2


def test_gate_operand_counts_reject_unreadable_artefact_values():
    """Defect 27: the §12/§13 *count* operands were read out of on-disk artefact JSON raw.

    `items`, `graded`, `dates`, `n`, `hits`, `hops`, `survivors` and `written` are compared
    (`count > 0`, `graded >= 30`, `dates >= 20`, `hops >= 3`, `written == survivors`). Raw, an
    artefact holding `true` read as 1 and one holding an overflow-to-`inf` read as a huge number, so
    `inf >= 20`, `inf >= 30`, `inf > 0` and `True > 0` all PASSED a gate the artefact cannot support;
    a string count (`"20"`) raised `TypeError` straight out of `main()` instead of producing a FAIL
    packet, and `inf` in a `sum()` fabricated a `hit_rate`. The read must go through the single
    numeric guard, so unreadable ⇒ None ⇒ the arm FAILS as unmeasured.
    """
    # Non-vacuity: a real count still reads as itself, and each arm still passes on good data.
    assert P._count(250) == 250
    assert P._count(30.0) == 30
    assert P.check_eval(good_eval())["items"] == 250
    assert P.check_rubric(good_rubric())["graded"] == 30
    assert P.check_backtest(good_backtest())["ok"] is True
    assert P.check_discovery(good_discovery())["ok"] is True
    # The boundary arms still pass: exactly the minimum is a pass, one under is a fail.
    assert P.check_rubric({"mean_score": 0.86, "counts": {"graded": 30}})["ok"] is True
    assert P.check_rubric({"mean_score": 0.86, "counts": {"graded": 29}})["ok"] is False
    assert P.check_backtest({"dates": 20, "hit_rate": 0.5, "n": 5})["ok"] is True
    assert P.check_backtest({"dates": 19, "hit_rate": 0.5, "n": 5})["ok"] is False

    # Broken reads: bool, non-finite, non-numeric, a container, and off a count's own value domain.
    bad = (True, False, float("inf"), float("-inf"), float("nan"), "20", [20], 1.5, -0.1)
    for b in bad:
        assert P._count(b) is None, b
    assert P._count(None) is None

    # Each gate operand, one arm per broken value — asserted separately so a bool arm cannot mask a
    # later non-finite one.
    for b in bad:
        c = P.check_eval({"metrics": good_eval()["metrics"], "counts": {"items": b}})
        assert c["ok"] is False, ("eval items", b)
        assert c["items"] is None, ("eval items", b)
    for b in bad:
        c = P.check_rubric({"mean_score": 0.86, "counts": {"graded": b}})
        assert c["ok"] is False, ("rubric graded", b)
        assert c["graded"] is None, ("rubric graded", b)
    for b in bad:
        c = P.check_backtest({"dates": b, "hit_rate": 0.5, "n": 5})
        assert c["ok"] is False, ("backtest dates", b)
        assert c["dates"] is None, ("backtest dates", b)

    # The multi-segment aggregate: `inf` used to win `max()` on dates, and `inf`/`True` in `sum()`
    # fabricated `hit_rate` (`nan`/`1.0`) out of the counts.
    for b in bad:
        c = P.check_backtest({"segments": [{"dates": b, "n": 1, "hits": 1}]})
        assert c["dates"] is None and c["ok"] is False, ("multi dates", b)
        c = P.check_backtest({"segments": [{"dates": 20, "n": b, "hits": 1}]})
        assert c["hit_rate"] is None and c["ok"] is False, ("multi n", b)
        c = P.check_backtest({"segments": [{"dates": 20, "n": 10, "hits": b}]})
        assert c["hit_rate"] is None and c["ok"] is False, ("multi hits", b)
    # A segment that is not a row dict is a broken read too, not an AttributeError.
    assert P.check_backtest({"segments": [None, "capesize"]})["dates"] is None

    # The reported-not-gated rate must still not render a raw `inf`/`True`/`"0.5"`/`1.5`.
    for b in bad:
        assert P.check_backtest({"dates": 20, "hit_rate": b, "n": 5})["hit_rate"] is None, b
    assert P.check_backtest({"dates": 20, "hit_rate": 0.5, "n": 5})["hit_rate"] == 0.5

    # Discovery: `hops` used to be read with `or 0` (so an unreadable hop count read as 0 and passed
    # nothing) and `written == survivors` compared raw counts.
    for b in bad:
        dc = good_discovery()
        dc["questions"][0]["hops"] = b
        c = P.check_discovery(dc)
        assert c["hops_ok"] is False and c["ok"] is False, ("hops", b)
    for key in ("survivors", "written"):
        for b in bad:
            dc = good_discovery()
            dc["counts"][key] = b
            assert P.check_discovery(dc)["ok"] is False, (key, b)
            assert P.check_discovery(dc)[key] is None, (key, b)
    # Non-vacuity on the equality arm: `written == survivors` still passes on coherent counts.
    assert P.check_discovery(good_discovery())["ok"] is True

    # End to end: one broken count no longer passes the §13 gate or reaches the approval packet.
    rep = P.build(good_eval(), {"mean_score": 0.86, "counts": {"graded": float("inf")}},
                  good_backtest(), good_discovery(), 1.0, 1.0)
    assert rep["pass"] is False and rep["gate"]["p7"] is False
    c2 = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), good_eval())
    assert "Do not publish yet." in c2 and "Recommend publishing" not in c2
    assert rep["checks"]["rubric"]["graded"] is None
    # A raw `inf` count must never render, and no string count may crash a report render.
    rep2 = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 1.0)
    assert rep2["pass"] is True  # non-vacuity: the good report still passes

    # Render side: the reported-not-gated rate and the per-question hop counts go straight into the
    # markdown, so an unmeasured read must print as `n/a` — never `inf`/`True`/`None`.
    assert P._r(None) == "n/a"
    assert P._r(0.5) == "0.5" and P._r(20) == "20"
    dq = good_discovery()
    dq["questions"][0]["hops"] = float("inf")
    dq["counts"]["written"] = float("inf")
    c2 = P._c2_md(rep, dq, good_rubric(), {"dates": 20, "hit_rate": float("inf"), "n": 5},
                  good_eval())
    md = P._md(P.build(good_eval(), good_rubric(), {"dates": 20, "hit_rate": float("inf"), "n": 5},
                       dq, 1.0))
    for text in (c2, md):
        assert "inf" not in text and "True" not in text
        assert "n/a" in text


def test_mean_never_lets_a_broken_value_poison_the_average():
    """`inf` in `sum()` yields `inf`, not a crash — so one unreadable member silently became the mean.

    `_mean` is a display-side aggregate over artefact metrics, but it is the same read: a `True`, a
    NaN or an overflow-to-inf member must be dropped as unread, never averaged in. A bool-first
    assertion loop would mask the later non-finite arm, so each arm is asserted separately.
    """
    assert P._mean([0.5, 0.7]) == 0.6  # non-vacuity
    assert P._mean([0.5, True]) == 0.5
    assert P._mean([0.5, float("inf")]) == 0.5
    assert P._mean([0.5, float("nan")]) == 0.5
    assert P._mean([0.5, "0.7"]) == 0.5
    assert P._mean([]) is None
    assert P._mean([True, float("inf"), "x", None]) is None


def test_no_unreadable_artefact_read_reaches_the_c2_packet_or_p7_json():
    """Defect 34: the render/verdict surface reprinted the *raw* artefact read.

    The Defect-27 fix guarded the count *operands*, and `_r` was written to stop an unmeasured value
    printing — but `_r` only checked `isinstance(None, ...)`-style `v is None`, and the render sites for
    the gate table, the rubric mean, the finding statistics and `main()`'s JSON never called it at all.
    So an artefact holding an overflow-to-`inf` metric, or a YAML `true`, or a quoted `"0.5"`, rendered
    verbatim into `p7.md` and into `C2_EVAL.md` — the owner's approval packet — and `json.dumps` wrote
    the non-standard `Infinity` token into `kb/reports/p7.json`, making that file unparseable JSON. The
    verdicts already failed closed; the *rendering* did not, so a broken read looked like a measurement.
    """
    BIG = float("1" + "0" * 400)
    assert BIG == float("inf")  # the overflow this whole family is about
    # `_r` is the guard: a real read renders as itself, an unreadable read says so.
    assert P._r(0.5) == "0.5" and P._r(20) == "20" and P._r(0.0) == "0.0"
    for bad in (None, True, False, BIG, float("inf"), float("-inf"), float("nan"), "0.5", [0.5]):
        assert P._r(bad) == "n/a", bad
    # Dates are text, not counts: the honest ISO string survives, a sentinel reads as unmeasured.
    assert P._text("2020-01-01") == "2020-01-01" and P._text(None) == "n/a"

    ev = good_eval()
    for k in P.TARGETS:
        ev["metrics"][k] = BIG
    rb = good_rubric()
    rb["mean_score"] = BIG
    bt = {"dates": 20, "hit_rate": BIG, "n": 5}
    dc = good_discovery()
    for f in dc["findings"]:
        f["stat"], f["q"], f["n"] = BIG, True, BIG

    # The verdict was already fail-closed; assert it still is, so the render fix cannot have loosened it.
    rep = P.build(ev, rb, bt, dc, BIG, BIG)
    assert rep["pass"] is False and rep["gate"]["p7"] is False
    assert rep["checks"]["eval"]["ok"] is False and rep["checks"]["rubric"]["ok"] is False
    assert rep["checks"]["eval"]["gates"]["exact_a_b_e_g"]["value"] is None
    assert rep["checks"]["rubric"]["mean_score"] is None

    md = P._md(rep)
    c2 = P._c2_md(rep, dc, rb, bt, ev)
    for text in (md, c2):
        assert "inf" not in text and "Infinity" not in text and "NaN" not in text, text
        assert "True" not in text and "None" not in text, text
    # The gate table renders the guarded read, and the finding statistics render as unmeasured.
    assert "| exact_a_b_e_g | n/a | 0.97 | NO |" in md
    assert "- exact_a_b_e_g: n/a (target 0.97) — FAIL" in c2
    assert "stat n/a · q n/a · n n/a" in c2
    # A real read is still a real read: the good arm renders its numbers, not `n/a`.
    good_md = P._md(P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 1.0, 2.0))
    assert "| exact_a_b_e_g | 0.98 | 0.97 | yes |" in good_md
    assert "mean 0.86 over 30 graded" in good_md

    # The written artefact stays valid JSON: `Infinity`/`NaN` are not JSON, so they serialise as null.
    payload = json.dumps(P._json_safe(rep), indent=1, default=str)
    assert "Infinity" not in payload and "NaN" not in payload
    loaded = json.loads(payload)
    assert loaded["checks"]["eval"]["gates"]["exact_a_b_e_g"]["value"] is None
    assert loaded["wall_seconds"] == 0.0  # a broken wall read is unmeasured, never `inf` seconds
    assert loaded["money_spent_usd"] is None
    # `main()` sums each artefact's `wall_seconds`; a string there used to raise straight out of it.
    assert P._json_safe({"a": [1.0, BIG], "b": BIG}) == {"a": [1.0, None], "b": None}


def test_c2_packet_contents():
    dc = good_discovery()
    rep = P.build(good_eval(), good_rubric(), good_backtest(), dc, 3.0)
    md = P._c2_md(rep, dc, good_rubric(), good_backtest(), good_eval())
    assert "C2 evaluation" in md and "Recommend publishing" in md
    assert md.count("lead_lag** commodity_iron_ore") == 30
    assert "Q-19" in md and "C2_APPROVED.md" in md


def test_load_and_spend():
    assert P.load_json(Path("does-not-exist.json"), {"x": 1}) == {"x": 1}
    assert isinstance(P.spend_usd(), float)


def test_unreadable_ledger_reports_unmeasured_not_zero(monkeypatch):
    """Defect 17 class, second site: an unreadable ledger must NOT print `$0.0000`.

    `money_spent_usd` appears in the C2 packet, the owner's approval artefact. A false `$0.0000`
    there is a confident claim about money in the one document whose job is to justify publishing,
    and it is indistinguishable from "measured, and it was zero".
    """
    def boom(*a, **k):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(P.sqlite3, "connect", boom)
    assert P.spend_usd() is None

    rep = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), P.spend_usd(), 100.0)
    assert rep["money_spent_usd"] is None
    assert "$" not in P.spend_text(rep) and "UNMEASURED" in P.spend_text(rep)
    assert "UNMEASURED" in P._md(rep)
    c2 = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), good_eval())
    assert "UNMEASURED" in c2 and "$0.0000" not in c2
    # An unmeasured spend is not a gate: the other four components still decide PASS on their own.
    assert rep["pass"] is True


def test_measured_zero_spend_still_prints_a_dollar_figure():
    """The None path must not swallow a genuine 0.0 — these are different states."""
    rep = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 0.0, 1.0)
    assert rep["money_spent_usd"] == 0.0
    assert P.spend_text(rep) == "$0.0000"


def test_real_tiny_spend_never_renders_as_the_measured_zero_string():
    """Defect-17 class, third instance: `$0.0000` is a claim, and it must be true.

    `None` (unmeasured) and `0.0` (measured zero) were already distinct. The third state hid inside
    the second: a real nonzero spend small enough that a fixed `:.4f` flattens it to the exact string
    reserved for measured zero. One P7 judge call really costs `$0.000019`, and the whole P6 phase
    `$0.000013` — both used to print as `$0.0000`, i.e. "free", in the owner's approval artefact.
    """
    tiny = 1.9e-05  # a real single judge call
    rep = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), tiny, 1.0)
    # The field must survive storage: `round(1.9e-05, 4) == 0.0` is how the value was destroyed.
    assert rep["money_spent_usd"] not in (0.0, None), "4 dp laundered a real spend into zero"
    assert P.spend_text(rep) != "$0.0000"
    assert P.spend_text(rep) == "$0.00002"
    c2 = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), good_eval())
    line = c2.splitlines()[2]
    assert "spend $0.00002 of the $82 cap" in line
    assert "spend $0.0000 " not in line


def test_three_spend_states_are_three_distinct_c2_lines():
    """Unmeasured / measured-zero / real-tiny must be three visibly different approval lines."""
    dc, rb, bt, ev = good_discovery(), good_rubric(), good_backtest(), good_eval()
    lines = []
    for v in (None, 0.0, 1.9e-05):
        rep = P.build(ev, rb, bt, dc, v, 1.0)
        lines.append(P._c2_md(rep, dc, rb, bt, ev).splitlines()[2])
    assert len(set(lines)) == 3, lines
    assert "UNMEASURED (ledger unreadable)" in lines[0]
    assert "$0.0000 " in lines[1]
    assert "$0.00002" in lines[2]


def test_cap_comes_from_config_not_a_hardcoded_string(monkeypatch):
    """The C2 packet's `$82 cap` denominator must be read, not typed.

    The cap lives in `kb/config.yaml` `budget.pipeline_cap_usd`, and the project has already amended
    it once. A stale hardcoded denominator turns "spend of cap" into a false claim in the artefact
    that authorises publishing, and it is the kind of number a reader never re-checks.
    """
    assert P.pipeline_cap() == 82.0  # committed value
    monkeypatch.setattr(P, "pipeline_cap", lambda: 95.0)
    rep = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 1.0, 1.0)
    assert rep["pipeline_cap_usd"] == 95.0
    line = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), good_eval()).splitlines()[2]
    assert "of the $95 cap" in line and "$82" not in line
    # An unreadable cap degrades to a plain amount rather than inventing a denominator.
    monkeypatch.setattr(P, "pipeline_cap", lambda: None)
    rep2 = P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 1.0, 1.0)
    line2 = P._c2_md(rep2, good_discovery(), good_rubric(), good_backtest(), good_eval()).splitlines()[2]
    assert "spend $1.0000 ·" in line2 and "cap" not in line2


def test_a_bool_or_nan_cap_is_unmeasured_not_one_dollar(monkeypatch, tmp_path):
    """A YAML `pipeline_cap_usd: true` must not read as a `$1` cap; nor may NaN render as `$nan`.

    `isinstance(True, (int, float))` is True, so the old `isinstance(cap, (int, float))` guard in
    `spend_text_full` accepted a bool and printed "of the $1 cap" in the approval packet — a
    denominator the owner never booked, in the one artefact where a denominator is trusted. NaN is
    the same broken read from the other side.
    """
    assert P._cap_num(True) is None
    assert P._cap_num(False) is None
    assert P._cap_num(float("nan")) is None
    assert P._cap_num(float("inf")) is None
    assert P._cap_num("82") is None
    assert P._cap_num(82) == 82.0

    # Both routes are guarded: the report-supplied cap and the config fallback.
    rep = dict(P.build(good_eval(), good_rubric(), good_backtest(), good_discovery(), 1.0, 1.0))
    rep["pipeline_cap_usd"] = True
    monkeypatch.setattr(P, "pipeline_cap", lambda: True)
    line = P._c2_md(rep, good_discovery(), good_rubric(), good_backtest(), good_eval()).splitlines()[2]
    assert "$1 cap" not in line and "cap" not in line, line
    assert "spend $1.0000 ·" in line, line
    # `spend_text_full` itself, not only the packet line: unmeasured spend stays unmeasured and the
    # bool cap adds no denominator rider.
    assert P.spend_text_full({"money_spent_usd": 1.0, "pipeline_cap_usd": True}) == "$1.0000"
    assert P.spend_text_full({"money_spent_usd": 1.0, "pipeline_cap_usd": 82}) == \
        "$1.0000 of the $82 cap"
    assert P.spend_text_full({"money_spent_usd": None, "pipeline_cap_usd": 82}) == \
        "UNMEASURED (ledger unreadable) of the $82 cap"


def test_allowance_from_config_is_a_bool_guarded_float_or_none(monkeypatch, tmp_path):
    """`p4b_run.p4c_allowance` is the second reader of the P4c bulk booking: `true` is not `$1`.

    Same defect shape as the cap readers: a bare `float(v) if v is not None` accepts a YAML bool. The
    allowance is a denominator in the P4b projection, so it must be unmeasured when config is
    unreadable or holds a non-number — never a fallback constant.
    """
    import p4b_run as B  # noqa: PLC0415

    assert B.p4c_allowance() == 31.25
    assert B.M.as_float(True) is None
    assert B.M.as_float(31.25) == 31.25
    # Unreadable config -> None (no `22.0`-style fallback, which is what froze a stale denominator
    # into the committed reports/p4b.json in the first place).
    monkeypatch.setattr(B, "ROOT", tmp_path)
    assert B.p4c_allowance() is None




def test_main_write_and_exit(tmp_path):
    ev = tmp_path / "eval.json"
    rb = tmp_path / "rubric.json"
    bt = tmp_path / "backtest.json"
    dc = tmp_path / "discovery.json"
    for path, data in ((ev, good_eval()), (rb, good_rubric()), (bt, good_backtest()),
                       (dc, good_discovery())):
        path.write_text(json.dumps(data), encoding="utf-8")
    out, md, c2 = tmp_path / "p7.json", tmp_path / "p7.md", tmp_path / "C2_EVAL.md"
    rc = P.main(["--eval", str(ev), "--rubric", str(rb), "--backtest", str(bt),
                 "--discovery", str(dc), "--out", str(out), "--md", str(md),
                 "--c2", str(c2), "--write"])
    assert rc == 0 and out.exists() and md.exists() and c2.exists()
    assert json.loads(out.read_text(encoding="utf-8"))["pass"] is True
    assert "PASS" in md.read_text(encoding="utf-8")
    # a failing eval must exit 1 and still write the FAIL packet
    ev.write_text(json.dumps({"metrics": {}, "counts": {"items": 0}}), encoding="utf-8")
    assert P.main(["--eval", str(ev), "--rubric", str(rb), "--backtest", str(bt),
                   "--discovery", str(dc), "--out", str(out), "--md", str(md),
                   "--c2", str(c2), "--write"]) == 1
    assert "FAIL" in md.read_text(encoding="utf-8")
