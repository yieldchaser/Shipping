"""Tests for kb/p7_rubric.py and kb/p7_report.py."""
from __future__ import annotations

import json
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
    monkeypatch.setattr(R.PA, "judge_answer", lambda *a, **k: dict(GOOD_JUDGE))
    rep = R.run(con=DummyCon())
    assert rep["counts"]["questions"] == 30 and rep["counts"]["graded"] == 30
    assert rep["mean_score"] == 0.9 and rep["pass"] is True
    assert rep["field_means"]["counter_argument_present"] == 0.8
    assert abs(rep["money_spent_usd"] - 0.30) < 1e-9
    assert "PASS" in R._md(rep) and "D19" in R._md(rep)


def test_run_fails_on_low_scores(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec())
    monkeypatch.setattr(R.PA, "judge_answer",
                        lambda *a, **k: {**GOOD_JUDGE, "score": 0.5})
    rep = R.run(con=DummyCon())
    assert rep["mean_score"] == 0.5 and rep["pass"] is False


def test_run_counts_ungraded_as_fail(monkeypatch):
    monkeypatch.setattr(R.PA, "analyse", lambda *a, **k: ok_rec(status="not_enough_data"))
    monkeypatch.setattr(R.PA, "judge_answer", lambda *a, **k: dict(GOOD_JUDGE))
    rep = R.run(con=DummyCon())
    assert rep["counts"]["graded"] == 0 and rep["pass"] is False
    assert rep["counts"]["not_enough_data"] == 30


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

    monkeypatch.setattr(R.PA, "judge_answer", bad)
    rep = R.run(con=DummyCon(), n=2)
    assert rep["counts"]["graded"] == 0 and rep["items"][0]["judged"] is False
    assert "judge_error" in rep["items"][0]


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
