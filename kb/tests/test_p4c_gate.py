"""Tests for kb/p4c_gate.py - post-processing of P4c extraction raws into gated records."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_gate as G  # noqa: E402
import runner as R  # noqa: E402

KNOWN = [{"id": "port:NLRTM", "type": "port", "name": "Rotterdam", "key": ""}]


def make_pack():
    return {
        "n": 0, "pack_id": "p000000", "doc_id": "d1", "ord_first": 0,
        "key": "d1|a+b",
        "chunk_ids": ["a", "b"],
        "tokens": 40,
        "doc": {"publisher": "Baltic Exchange", "doc_type": "broker_weekly",
                "published_at": "2015-10-02", "heading": "T"},
        "year": 2015, "section_class": "prose",
        "blocks": [{"cid": "c1", "sentences": [[0, "Rotterdam, Netherlands handled 12 vessels in 2015."]]},
                   {"cid": "c2", "sentences": [[0, "No figures were published."]]}],
        "known": KNOWN, "known_ids": ["port:NLRTM"],
    }


def extraction(**over) -> str:
    doc = {"no_content": False, "state_facts": [], "events": [], "claims": [], "new_entities": []}
    doc.update(over)
    return json.dumps(doc)


GOOD = extraction(
    new_entities=[{"id": "N1", "type": "country", "name": "Netherlands", "chunk": "c1", "sids": [0]}],
    state_facts=[{"type": "FLAG", "src": "port:NLRTM", "dst": "N1",
                  "attrs_printed": [{"key": "metric", "value_as_printed": "12 vessels"}],
                  "valid_from_printed": "", "valid_to_printed": "", "chunk": "c1",
                  "sids": [0], "confidence": 0.9}],
)

BAD_NUMBER = extraction(
    new_entities=[{"id": "N1", "type": "country", "name": "Netherlands", "chunk": "c1", "sids": [0]}],
    state_facts=[{"type": "FLAG", "src": "port:NLRTM", "dst": "N1",
                  "attrs_printed": [{"key": "metric", "value_as_printed": "99 vessels"}],
                  "valid_from_printed": "", "valid_to_printed": "", "chunk": "c1",
                  "sids": [0], "confidence": 0.9}],
)


def stub_raw(monkeypatch, tmp_path, text):
    """Point p4c_gate.raw_for at one fixed raw file containing `text` as the assistant answer."""
    p = tmp_path / "raw.json"
    body = {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1}}
    p.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr(G, "raw_for", lambda *a, **k: p)
    return p


def test_raw_for_uses_the_runner_job_key(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RAW", tmp_path / "raw")
    pack = make_pack()
    path = G.raw_for("p4c_bulk", "DeepSeek-V4.1-Flash", "tools", pack)
    from p4b_run import make_job
    job = make_job("p4c_bulk", "DeepSeek-V4.1-Flash", "tools", pack)
    assert path == R.raw_path("p4c_bulk", job["job_key"])
    assert path.name.endswith(".json")


def test_gate_pack_keeps_valid_record_and_maps_real_chunk(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, GOOD)
    res = G.gate_pack(make_pack(), "p4c_bulk", "m", "tools")
    assert res["call"]["parse_ok"] and not res["call"]["schema_fail"]
    assert res["call"]["records_total"] == 1 and res["call"]["records_ok"] == 1
    a, b = res["chunks"]["a"], res["chunks"]["b"]
    assert a["records_ok"] == 1 and not a.get("call_failed")
    kept = a["kept"]["state_facts"]
    assert len(kept) == 1 and kept[0]["chunk"] == "a"  # prompt id c1 -> real chunk id
    assert kept[0]["dst"].startswith("country:")  # N1 handle canonicalised
    assert b["records_total"] == 0 and b["kept"]["state_facts"] == []


def test_gate_pack_drops_number_not_in_quote(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, BAD_NUMBER)
    res = G.gate_pack(make_pack(), "p4c_bulk", "m", "tools")
    a = res["chunks"]["a"]
    assert a["records_total"] == 1 and a["records_ok"] == 0 and a["gates_2_4_failed"] == 1
    assert any("number_not_in_quote" in r for r in a["reasons"])
    assert res["call"]["reasons"].get("number_not_in_quote") == 1


def test_gate_pack_blank_answer_queues_every_chunk(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, "")
    res = G.gate_pack(make_pack(), "p4c_bulk", "m", "tools")
    assert res["call"]["blank"] is True
    for cid in ("a", "b"):
        ch = res["chunks"][cid]
        assert ch["call_failed"] is True and ch["reasons"] == ["blank_answer"]


def test_gate_pack_absent_raw_is_missing_never_broken(monkeypatch, tmp_path):
    """A pack with no stored raw has not been extracted yet: not a failure, not a blank answer."""
    monkeypatch.setattr(G, "raw_for", lambda *a, **k: tmp_path / "never_written.json")
    res = G.gate_pack(make_pack(), "p4c_bulk", "m", "tools")
    assert res["call"]["missing"] is True
    assert res["call"]["blank"] is False and res["call"]["schema_fail"] is False
    for cid in ("a", "b"):
        ch = res["chunks"][cid]
        assert ch["call_failed"] is False and ch["call_missing"] is True
        assert ch["reasons"] == ["missing_raw"]
        assert ch["records_total"] == 0 and ch["gates_2_4_failed"] == 0


def test_gate_run_missing_packs_stay_out_of_the_failure_queue(monkeypatch, tmp_path):
    monkeypatch.setattr(G, "raw_for", lambda *a, **k: tmp_path / "never_written.json")
    packs = tmp_path / "packs.jsonl"
    packs.write_text(json.dumps(make_pack()) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    st = G.gate_run("p4c_bulk", "m", mode="tools", packs_path=packs, out_dir=out)
    assert st["packs"] == 1 and st["chunks"] == 2
    assert st["calls_missing"] == 1 and st["chunks_missing"] == 2
    assert st["calls_blank"] == 0 and st["chunk_failures"] == 0
    assert st["packs_answered"] == 0 and st["gate_pass_rate"] == 0.0
    assert st["chunk_failure_rate"] == 0.0
    assert (out / "failures.jsonl").read_text(encoding="utf-8") == ""
    rows = [json.loads(x) for x in (out / "gated.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["call_missing"] and not r["call_failed"] for r in rows)
    assert all("missing_raw" in r["reasons"] for r in rows)


def test_gate_pack_schema_failure_queues_every_chunk(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, "not json at all")
    res = G.gate_pack(make_pack(), "p4c_bulk", "m", "tools")
    assert res["call"]["schema_fail"] is True and res["call"]["parse_ok"] is False
    assert all(res["chunks"][c]["reasons"] == ["schema_fail"] for c in ("a", "b"))


def test_read_raw_missing_file(tmp_path):
    assert G.read_raw(tmp_path / "nope.json") == (None, None)


def test_gate_run_writes_gated_and_failures(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, BAD_NUMBER)
    packs = tmp_path / "packs.jsonl"
    packs.write_text(json.dumps(make_pack()) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    st = G.gate_run("p4c_bulk", "m", mode="tools", packs_path=packs, out_dir=out)
    assert st["packs"] == 1 and st["chunks"] == 2
    assert st["chunk_failures"] == 1  # only chunk `a` has a dropped record
    assert st["records_total"] == 1 and st["records_ok"] == 0
    gated = [json.loads(x) for x in (out / "gated.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [g["chunk_id"] for g in gated] == ["a", "b"]
    fails = [json.loads(x) for x in (out / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(fails) == 1 and fails[0]["chunk_id"] == "a"
    assert (out / "gate_stats.json").exists()
    with pytest.raises(SystemExit):
        G.gate_run("p4c_bulk", "m", mode="tools", packs_path=packs, out_dir=out)


def test_gate_run_requires_recorded_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(G, "load_modes", lambda: {})
    with pytest.raises(SystemExit):
        G.gate_run("p4c_bulk", "m", mode=None, packs_path=tmp_path / "p.jsonl",
                   out_dir=tmp_path / "out")


def test_gated_chunk_rows_carry_the_rule6_fields(monkeypatch, tmp_path):
    stub_raw(monkeypatch, tmp_path, GOOD)
    packs = tmp_path / "packs.jsonl"
    packs.write_text(json.dumps(make_pack()) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    G.gate_run("p4c_bulk", "m", mode="tools", packs_path=packs, out_dir=out)
    rows = {r["chunk_id"]: r for r in
            (json.loads(x) for x in (out / "gated.jsonl").read_text(encoding="utf-8").splitlines())}
    a = rows["a"]
    assert a["doc_type"] == "broker_weekly" and a["section_class"] == "prose"
    assert a["approx_tokens"] > 0
    assert a["records_total"] == 1 and a["records_ok"] == 1
    assert a["failed_pct"] == 0.0 and a["mean_confidence"] == 0.9
    # a chunk with no records has no confidence signal and no failure share
    b = rows["b"]
    assert b["failed_pct"] == 0.0 and b["mean_confidence"] is None
