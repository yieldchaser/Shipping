"""Tests for kb/p4c_audit.py - seeded sampling, verdict parsing, family rule (no model calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_audit as A  # noqa: E402


def rec(kind="state_facts", **over):
    base = {"chunk": "c1", "sids": [0], "confidence": 0.9, "quote": ["Rotterdam handled 12 vessels."]}
    base.update(over)
    return base


def gated_row(cid="c1", n_facts=2):
    return {"chunk_id": cid, "doc_id": "d1", "publisher": "Baltic Exchange",
            "doc_type": "broker_weekly", "published_at": "2015-10-02",
            "state_facts": [rec() for _ in range(n_facts)], "events": [],
            "claims": [rec(kind="claims")]}


def test_model_family_and_rule():
    assert A.model_family("deepseek-v4.1-flash-1017-ultrafast") == "deepseek"
    assert A.model_family("glm-5.3") == "glm"
    assert A.model_family("nvidia/nemotron-3-ultra-550b-a55b") == "nvidia"
    assert A.judge_family_ok("glm-5.3", "deepseek-v4.1-flash-1017-ultrafast")
    assert not A.judge_family_ok("deepseek-v4-flash", "deepseek-v4.1-flash-1017-ultrafast")


def test_flat_records_one_entry_per_record():
    rows = [gated_row(n_facts=2), gated_row(cid="c2", n_facts=0)]
    flat = A.flat_records(rows)
    assert len(flat) == 4
    assert [f["kind"] for f in flat] == ["state_facts", "state_facts", "claims", "claims"]
    assert flat[0]["quote"] == "Rotterdam handled 12 vessels."
    assert flat[0]["doc_id"] == "d1" and flat[0]["index"] == 0


def test_sample_records_is_seeded_and_capped():
    flat = A.flat_records([gated_row(n_facts=30)])
    a = A.sample_records(flat, n=5, seed=1234)
    b = A.sample_records(flat, n=5, seed=1234)
    c = A.sample_records(flat, n=5, seed=999)
    assert [x["chunk_id"] for x in a] == [x["chunk_id"] for x in b]
    assert [x["index"] for x in a] == [x["index"] for x in b]
    assert [x["index"] for x in a] != [x["index"] for x in c]
    assert [x["audit_id"] for x in a] == ["a000", "a001", "a002", "a003", "a004"]
    assert len(A.sample_records(flat[:3], n=5, seed=1)) == 3


def test_parse_verdict_variants():
    assert A.parse_verdict('{"verdict": "keep", "reason": "ok"}') == ("keep", "ok")
    assert A.parse_verdict('```json\n{"verdict":"drop","reason":"number missing"}\n```')[0] == "drop"
    assert A.parse_verdict('I think {"verdict":"DROP"}') == ("drop", "")
    assert A.parse_verdict("nonsense") == (None, "")
    assert A.parse_verdict('{"verdict":"maybe"}') == (None, "")


def test_summarise_counts_wrong_conservatively(monkeypatch):
    payload = {"items": [{"audit_id": f"a{i:03d}", "chunk_id": f"c{i}", "kind": "state_facts",
                          "record": rec(), "quote": "q", "index": i} for i in range(6)]}
    raws = {0: '{"verdict":"keep"}', 1: '{"verdict":"drop","reason":"x"}',
            2: '{"verdict":"keep"}', 3: "garbage", 4: '{"verdict":"keep"}'}  # item 5 unjudged

    def fake_result(pass_name, job):
        i = payload["items"].index([it for it in payload["items"]
                                    if it["audit_id"] == job["meta"]["audit_id"]][0])
        return {"raw": raws[i]} if i in raws else None

    monkeypatch.setattr(A.B, "load_result", fake_result)
    st = A.summarise(payload, "glm-5.3", "json_schema")
    assert st["sampled"] == 6 and st["judged"] == 5
    assert st["keep"] == 3 and st["drop"] == 1 and st["unparseable"] == 1
    assert st["wrong"] == 2 and st["wrong_rate"] == 0.4


def test_plan_writes_seeded_items(monkeypatch, tmp_path):
    src = tmp_path / "gated.jsonl"
    src.write_text(json.dumps(gated_row(n_facts=4)) + "\n" + json.dumps(gated_row(cid="c2")) + "\n",
                   encoding="utf-8")
    monkeypatch.setattr(A, "OUT", tmp_path)
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")
    st = A.plan(src, n=3)
    payload = json.loads((tmp_path / "audit_items.json").read_text(encoding="utf-8"))
    assert st == {"records_available": 8, "items": 3, "out": str(tmp_path / "audit_items.json")}
    assert payload["seed"] == A.seed_for("P4C") and len(payload["items"]) == 3


def test_cmd_run_refuses_same_family(monkeypatch):
    monkeypatch.setattr(A, "_selected_extractor", lambda: "deepseek-v4-flash")
    args = type("Args", (), {"model": "deepseek-v4-pro", "extractor": None, "cap": 0.0, "limit": 0})()
    try:
        A.cmd_run(args)
    except SystemExit as exc:
        assert "family" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
