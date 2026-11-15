"""Defect 16: the cross-family judge's fenced verdict must parse, not score 0.0.

Gemma-4-31B-IT (owner amendment 2026-11-15) returns ```json fenced objects. Before the fix,
`p7_analyst.judge_answer` raised JSONDecodeError and `p7_eval.judge_faithful` floored every
verdict to 0.0 — a judge that never grades is indistinguishable from a judge that says no.
"""
from __future__ import annotations

import kb.llm_runner as L
import kb.p7_analyst as PA
import kb.p7_eval as E

FENCED = '```json\n{\n  "facts_cited": 1,\n  "indicators_correct": 1,\n  "judgment_reasoned": 0,\n  "counter_argument_present": 0,\n  "score": 0.5,\n  "notes": "no judgment"\n}\n```'


def test_parse_json_object_unwraps_a_fence():
    assert L.parse_json_object(FENCED)["score"] == 0.5
    assert L.parse_json_object('```\n{"supported": 0.75}\n```') == {"supported": 0.75}
    assert L.parse_json_object('Sure, here you go:\n{"a": 1}') == {"a": 1}
    assert L.parse_json_object('{"a": 1}') == {"a": 1}
    assert L.parse_json_object("not json at all") == {}
    assert L.parse_json_object("") == {}
    assert L.parse_json_object(None) == {}
    assert L.parse_json_object("[1, 2]") == {}


def test_judge_answer_parses_a_fenced_verdict():
    def chat(model, messages, max_tokens=500, **kw):
        return FENCED, {"prompt_tokens": 1, "completion_tokens": 1}, 0.0

    rec = {"answer": "flat", "indicators": {"indicators": []}}
    out = PA.judge_answer("q", rec, chat=chat)
    assert out["score"] == 0.5
    assert out["judgment_reasoned"] == 0


def test_judge_faithful_parses_a_fenced_verdict():
    def chat(model, messages, max_tokens=400, **kw):
        return '```json\n{"supported": 0.75}\n```', {}, 0.0

    rec = {"question": "q", "answer": "a", "evidence": ["quote"], "sentences": []}
    assert E.judge_faithful(rec, chat=chat) == 0.75


def test_p6_judge_node_parses_a_fenced_verdict(monkeypatch):
    import kb.p6_summary as P

    def fake_chat(model, messages, **kw):
        return {"choices": [{"message": {"content": '```json\n{"verdict": "supported", "score": 1.0, "why": "ok"}\n```'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    monkeypatch.setattr(P, "chat", fake_chat)
    monkeypatch.setattr(P, "_log", lambda *a, **k: 0.0)
    out = P.judge_node("spot was 5 [obs:1]", [{"kind": "obs", "ref": "1", "text": "value 5"}])
    assert out["score"] == 1.0 and out["verdict"] == "supported", out
