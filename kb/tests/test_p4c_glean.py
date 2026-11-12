"""Unit tests for kb/p4c_glean.py (free second Ultrafast pass, owner decision 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p4c_glean as GL
from extract_schema import CLAIM_KINDS, DIRECTIONS, EDGE_TYPES, EVENT_TYPES, STATIC_PROMPT


def raw_extraction(chunk="c1") -> str:
    return json.dumps({
        "no_content": False,
        "state_facts": [{
            "type": next(iter(EDGE_TYPES)), "src": "N1", "dst": "N2",
            "attrs_printed": [{"key": "rate", "value_as_printed": "USD 25,000"}],
            "valid_from_printed": "Jan 5", "valid_to_printed": "", "chunk": chunk,
            "sids": [1, 2], "confidence": 0.8}],
        "events": [{
            "type": next(iter(EVENT_TYPES)), "summary": "Sold for USD 25,000",
            "roles": [{"role": "buyer", "entity": "N2"}], "when_printed": "Jan 5",
            "magnitude_printed": "USD 25,000", "chunk": chunk, "sids": [2],
            "confidence": 0.7}],
        "claims": [{
            "kind": next(iter(CLAIM_KINDS)), "subjects": ["N1"],
            "direction": next(iter(DIRECTIONS)), "horizon_printed": "2026", "chunk": chunk,
            "sids": [1], "confidence": 0.6}],
        "new_entities": [{"id": "N1", "type": "vessel", "name": "MV Test", "chunk": chunk,
                          "sids": [1]}],
    })


def mk_pack(cid="c1", text="MV Test sold for USD 25,000 in Jan 5 2026.") -> dict:
    return {"n": 0, "pack_id": "p1", "doc_id": "d1", "ord_first": 0, "key": "p1",
            "chunk_ids": [cid], "tokens": 10,
            "doc": {"publisher": "Fearnleys", "doc_type": "broker_weekly",
                    "published_at": "2026-01-05", "heading": "Weekly"},
            "year": 2026, "section_class": "prose",
            "blocks": [{"cid": cid, "sentences": [[1, text], [2, text]]}],
            "known": [], "known_ids": []}


def test_first_pass_lines_from_stored_raw(monkeypatch):
    monkeypatch.setattr(GL.G, "raw_for", lambda *a, **k: Path("raw.json"))
    monkeypatch.setattr(GL.G, "read_raw", lambda p: (raw_extraction(), None))
    lines = GL.first_pass_lines(mk_pack(), "m", "tools")
    assert len(lines) == 4
    assert lines[0].startswith("c1 [1, 2] state_fact ")
    assert "attrs=[rate=USD 25,000]" in lines[0]
    assert "event" in lines[1] and "roles=[buyer:N2]" in lines[1]
    assert "claim" in lines[2]
    assert "new_entity" in lines[3] and "MV Test" in lines[3]


def test_first_pass_lines_empty_when_no_raw(monkeypatch):
    def boom(*a, **k):
        raise OSError("missing")
    monkeypatch.setattr(GL.G, "raw_for", boom)
    assert GL.first_pass_lines(mk_pack(), "m", "tools") == []
    monkeypatch.setattr(GL.G, "raw_for", lambda *a, **k: Path("raw.json"))
    monkeypatch.setattr(GL.G, "read_raw", lambda p: ("", None))
    assert GL.first_pass_lines(mk_pack(), "m", "tools") == []
    monkeypatch.setattr(GL.G, "read_raw", lambda p: ("not json", None))
    assert GL.first_pass_lines(mk_pack(), "m", "tools") == []
    monkeypatch.setattr(GL.G, "read_raw", lambda p: (json.dumps({"no_content": True}), None))
    assert GL.first_pass_lines(mk_pack(), "m", "tools") == []


def test_first_pass_lines_truncated_to_max_lines(monkeypatch):
    doc = json.loads(raw_extraction())
    doc["claims"] = [dict(doc["claims"][0]) for _ in range(GL.MAX_LINES + 40)]
    monkeypatch.setattr(GL.G, "raw_for", lambda *a, **k: Path("raw.json"))
    monkeypatch.setattr(GL.G, "read_raw", lambda p: (json.dumps(doc), None))
    assert len(GL.first_pass_lines(mk_pack(), "m", "tools")) == GL.MAX_LINES


def test_glean_messages_keep_system_prompt_and_add_first_pass_block():
    lines = ["c1 [1] state_fact OWNS N1 -> N2 attrs=[] from='Jan 5' to='' nums=5"]
    msgs = GL.glean_messages(mk_pack(), lines)
    assert msgs[0] == {"role": "system", "content": STATIC_PROMPT}
    user = msgs[1]["content"]
    assert '<chunk id="c1">' in user and "[1]" in user and "[2]" in user
    assert "<first_pass_records>" in user and lines[0] in user
    assert "<glean_instruction>" in user
    assert GL.GLEAN_INSTRUCTION in user


def test_glean_messages_mark_empty_first_pass():
    msgs = GL.glean_messages(mk_pack(), [])
    user = msgs[1]["content"]
    assert "none - the first answer returned nothing usable" in user
    assert GL.GLEAN_INSTRUCTION in user


def test_job_maker_keeps_ledger_key_and_tags_meta(monkeypatch):
    monkeypatch.setattr(GL, "first_pass_lines", lambda *a, **k: ["a", "b"])
    make = GL.job_maker("bulk-model", "tools")
    pack = mk_pack()
    job = make(GL.GLEAN_PASS, "m", "tools", pack)
    bulk = GL.B.make_job(GL.GLEAN_PASS, "m", "tools", pack)  # same pass/model/mode/pack
    ref = GL.B.make_job(GL.BULK_PASS, "m", "tools", pack)
    assert job["job_key"] == bulk["job_key"] != ref["job_key"], \
        "glean raws must live in their own namespace"
    assert job["messages"][0]["content"] == STATIC_PROMPT
    assert "<first_pass_records>" in job["messages"][1]["content"]
    assert job["meta"]["glean_of"] == GL.BULK_PASS
    assert job["meta"]["first_pass_records"] == 2


def test_nums_and_attrs_helpers():
    assert GL._nums("USD 25,000 on Jan 5") == "25,000,5"
    assert GL._attrs([{"key": "rate", "value_as_printed": "USD 25,000"}]) == "rate=USD 25,000"
    assert GL._attrs([]) == ""


def test_cmd_run_refuses_unknown_mode(monkeypatch):
    monkeypatch.setattr(GL.B, "load_modes", lambda: {})
    with pytest.raises(SystemExit):
        GL.cmd_run(type("A", (), {"model": "m", "bulk_model": None, "cap": 0.0,
                                  "packs": None, "limit": 0, "shard": 200})())


def test_cmd_run_calls_run_packs_with_job_maker(monkeypatch):
    seen = {}

    def fake_run(pass_name, model, cap, packs_path=None, limit=0, shard=200, job_maker=None):
        seen.update(pass_name=pass_name, model=model, cap=cap, has_maker=job_maker is not None)
        return {"pass": pass_name, "model": model, "mode": "tools", "packs": 1,
                "packs_skipped": 0, "chunks": 1, "chunks_skipped": 0, "cost_usd": 0.0,
                "wall_s": 0.0}

    monkeypatch.setattr(GL.B, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(GL.PR, "run_packs", fake_run)
    rc = GL.main(["--run", "--model", "m", "--cap", "0"])
    assert rc == 0
    assert seen == {"pass_name": GL.GLEAN_PASS, "model": "m", "cap": 0.0, "has_maker": True}


def test_cmd_prepare_writes_only_packs_with_a_first_pass(tmp_path, monkeypatch):
    src = tmp_path / "packs.jsonl"
    src.write_text(json.dumps(mk_pack("c1")) + "\n" + json.dumps(mk_pack("c2")) + "\n",
                   encoding="utf-8")
    monkeypatch.setattr(GL.B, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(GL, "first_pass_lines",
                        lambda pack, model, mode: ["x"] if pack["chunk_ids"] == ["c1"] else [])
    out = tmp_path / "packs_glean.jsonl"
    args = type("A", (), {"model": "m", "bulk_model": None, "packs": str(src),
                          "out_packs": str(out)})()
    assert GL.cmd_prepare(args) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["chunk_ids"] for r in rows] == [["c1"]]


def test_cmd_prepare_refuses_unknown_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(GL.B, "load_modes", lambda: {})
    args = type("A", (), {"model": "m", "bulk_model": None, "packs": str(tmp_path / "p.jsonl"),
                          "out_packs": str(tmp_path / "o.jsonl")})()
    with pytest.raises(SystemExit):
        GL.cmd_prepare(args)
