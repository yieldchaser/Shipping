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
    assert E.judge_faithful(rec, chat=_chat(["not json"])) == 0.0
    assert E.judge_faithful({"evidence": []}, chat=_chat(['{"supported": 1.0}'])) == 0.0


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
    assert rep["metrics"]["exact_a_b_e_g"] == 1.0
    assert rep["metrics"]["refusal"] == 1.0
    assert rep["metrics"]["multihop_f1"] == 1.0
    assert rep["metrics"]["recall_at_20"] is None
    assert rep["counts"]["items"] == 4
    assert rep["phase"] == "P7" and rep["sample_seed"] == E.seed_for("P7")
    assert rep["pass"] is False          # skipped metric never passes the gate


def test_evaluate_with_search_and_judge(patched, monkeypatch):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})
    rep = E.evaluate(GOLD, with_search=True, with_judge=True, judge_chat=_chat(['{"supported": 1.0}'] * 5))
    assert rep["metrics"]["recall_at_20"] == 1.0
    assert rep["metrics"]["faithfulness"] == 1.0
    assert rep["pass"] is True and rep["judged"] == 3
    assert rep["money_spent_usd"] == 0.0


def test_evaluate_handles_pipeline_errors(patched):
    def boom(q, model=None, con=None, chat=None):
        raise RuntimeError("model down")

    patched.setattr(E.A, "answer_question", boom)
    rep = E.evaluate(GOLD, with_search=False, with_judge=False)
    assert rep["metrics"]["exact_a_b_e_g"] == 0.0
    assert rep["metrics"]["refusal"] == 1.0          # model_error counts as refusal
    assert rep["items"][0]["status"] == "model_error"


def test_md_and_report_files(patched, monkeypatch, tmp_path):
    monkeypatch.setattr(E.A, "answer_question",
                        lambda q, model=None, con=None, chat=None: {
                            **REPLIES[q.split()[-1]], "evidence": ["quote"]})
    rep = E.evaluate(GOLD, with_search=True, with_judge=True, judge_chat=_chat(['{"supported": 1.0}'] * 5))
    md = E._md(rep)
    assert "| exact_a_b_e_g |" in md, md
    assert "PASS" in md, (rep["pass"], rep["metrics"], md)
    assert "D16" in md
    out = tmp_path / "eval.json"
    out.write_text(json.dumps(rep), encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8"))["metrics"]["refusal"] == 1.0


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
