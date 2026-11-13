"""Unit tests for `p4c_union` - merge/dedupe determinism and the audit-compatible row shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb"))

import p4c_audit as A  # noqa: E402
import p4c_union as U  # noqa: E402


def pack(cid: str = "c1", chunk_id: str = "chunk_a") -> dict:
    return {"n": 0, "pack_id": "p000000", "doc_id": "doc_a", "ord_first": 0,
            "key": f"doc_a|{chunk_id}", "chunk_ids": [chunk_id], "tokens": 10,
            "doc": {"publisher": "broker_x", "doc_type": "broker_report",
                    "published_at": "2024-01-05", "heading": "h"},
            "year": 2024, "section_class": "mdna",
            "blocks": [{"cid": cid, "sentences": [[1, "The ship SHIP TWO was sold for $10m."],
                                                   [2, "Delivery is due in 2025."]]}],
            "known": [{"id": "E1", "type": "vessel", "name": "SHIP ONE", "key": "imo1"}]}


def rec_row(rkind: str, **body) -> dict:
    base = {"record_kind": rkind, "chunk": "c1", "sids": [1], "quote": "The ship SHIP TWO was sold for $10m.",
            "sources": ["p4c_bulk"], "confidence": 0.8}
    base.update(body)
    return base


def test_sig_of_mirrors_p4b_record_sig():
    r = rec_row("state_facts", type="OWNS", src="E1", dst="E2")
    assert U.sig_of(r) == ("state_facts", "OWNS", frozenset(["E1", "E2"]))
    ev = rec_row("events", type="sale", roles=[{"entity": "E1", "role": "seller"},
                                               {"entity": "E2", "role": "buyer"}])
    assert U.sig_of(ev) == ("events", "sale", frozenset(["E1", "E2"]))
    cl = rec_row("claims", kind="forecast", subjects=["E1"])
    assert U.sig_of(cl) == ("claims", "forecast", frozenset(["E1"]))


def test_merge_dedupes_same_fact_and_keeps_provenance():
    acc: list[dict] = []
    first = rec_row("state_facts", type="OWNS", src="E1", dst="E2", sources=["p4c_bulk"])
    assert U.merge_records(acc, [first], "p4c_bulk") == (1, 0)
    dup = rec_row("state_facts", type="OWNS", src="E1", dst="E2", sources=["p4c_glean"],
                  confidence=0.9)
    assert U.merge_records(acc, [dup], "p4c_glean") == (0, 1)
    assert len(acc) == 1
    assert acc[0]["sources"] == ["p4c_bulk", "p4c_glean"]
    assert acc[0]["confidence"] == 0.9  # highest-confidence copy wins
    other = rec_row("state_facts", type="OWNS", src="E1", dst="E3")
    assert U.merge_records(acc, [other], "p4c_glean") == (1, 0)
    assert len(acc) == 2


def test_merge_keeps_records_with_identical_identity_but_different_evidence():
    acc: list[dict] = []
    a = rec_row("claims", kind="view", subjects=["E1"])
    b = rec_row("claims", kind="view", subjects=["E1"],
                quote="Delivery is due in 2025.", sids=[2])
    U.merge_records(acc, [a], "p4c_bulk")
    assert U.merge_records(acc, [b], "p4c_glean") == (1, 0)  # no sentence overlap -> distinct fact


def test_union_pack_merges_two_sources(monkeypatch):
    p = pack()

    def fake_kept_for(pack_, pass_name, model, mode=None):
        base = {"call": "ok", "total": 1, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [], "events": [], "claims": []}}}
        if pass_name == "p4c_bulk":
            base["chunks"]["chunk_a"]["state_facts"] = [_Model(state_facts=True)]
        elif pass_name == "p4c_glm2":
            base["chunks"]["chunk_a"]["state_facts"] = [_Model(state_facts=True),
                                                       _Model(dst="E3")]
            base["new_entities"] = {"E9": "SHIP TWO"}
        return base

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1"), ("p4c_glm2", "m2")], modes={"m1": "tools",
                                                                          "m2": "tools"})
    row = got["rows"][0]
    assert row["chunk_id"] == "chunk_a"
    assert row["records_total"] == 2  # duplicate collapsed, distinct second record kept
    # provenance counts contributing records per source: the dup carries both, the extra one only glm2
    assert row["provenance"]["p4c_bulk"] == 1
    assert row["provenance"]["p4c_glm2"] == 2
    assert got["stats"]["duplicates"] == 1
    assert row["new_entities"] == {"E9": "SHIP TWO"}
    assert row["kept"]["state_facts"] == row["state_facts"]


def test_union_pack_flags_broken_chunk_when_every_call_failed(monkeypatch):
    p = pack()

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "schema_fail", "total": 0, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [], "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1"), ("p4c_glm2", "m2")],
                       modes={"m1": "tools", "m2": "tools"})
    row = got["rows"][0]
    assert row["call_broken"] is True
    assert row["no_content"] is False  # broken != legitimately empty
    assert row["records_total"] == 0


def test_build_writes_audit_compatible_rows(monkeypatch, tmp_path):
    packs = tmp_path / "packs.jsonl"
    packs.write_text(json.dumps(pack()) + "\n", encoding="utf-8")

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "ok", "total": 1, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [_Model(state_facts=True)],
                                                  "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    monkeypatch.setattr(U.RUN, "load_modes", lambda: {"m1": "tools"})
    out = U.build([("p4c_bulk", "m1")], packs, tmp_path / "union")
    assert out["chunks"] == 1 and out["records"] == 1
    assert out["coverage_complete"] is False  # limited run
    assert out["failure_queue_rate"] == 0.0
    rows = [json.loads(line) for line in
            (tmp_path / "union/gated_union.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    flat = A.flat_records(rows)  # the audit step must see the union records unchanged
    assert len(flat) == 1
    assert flat[0]["kind"] == "state_facts"
    assert flat[0]["quote"] == "The ship SHIP TWO was sold for $10m."
    assert flat[0]["record"]["record_kind"] == "state_facts"


def test_parse_sources_accepts_defaults_and_overrides():
    assert [p for p, _ in U.parse_sources(None)] == [p for p, _ in U.SOURCE_SPEC]
    assert U.parse_sources("p4c_bulk,p4c_glm2:glm-5.3") == [("p4c_bulk", U.AMD),
                                                            ("p4c_glm2", "glm-5.3")]


class _Model:
    """Minimal stand-in for a pydantic extraction record (only what the union reads)."""

    def __init__(self, state_facts: bool = True, dst: str = "E2"):
        self.chunk = "c1"
        self.sids = [1]
        self.confidence = 0.7
        self.type = "OWNS"
        self.src = "E1"
        self.dst = dst

    def model_dump(self, mode: str = "json") -> dict:
        return {"chunk": self.chunk, "sids": self.sids, "confidence": self.confidence,
                "type": self.type, "src": self.src, "dst": self.dst}


def test_kept_for_reads_a_stored_raw(monkeypatch):
    p = pack()
    answer = json.dumps({"no_content": False, "state_facts": [
        {"type": "OWNS", "src": "E1", "dst": "N#1", "sids": [1], "confidence": 0.9,
         "chunk": "c1", "attr_notes": ""}], "events": [], "claims": [],
        "new_entities": [{"id": "N#1", "type": "vessel", "name": "SHIP TWO",
                          "chunk": "c1", "sids": [1]}]})
    monkeypatch.setattr(U.G, "raw_for", lambda *a, **k: Path("unused.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (answer, {}))
    got = U.kept_for(p, "p4c_bulk", "m1", "tools")
    assert got["call"] == "ok"
    assert got["total"] == 1 and got["dropped"] == 0
    assert len(got["chunks"]["chunk_a"]["state_facts"]) == 1


def test_kept_for_reports_blank_and_missing(monkeypatch):
    p = pack()
    monkeypatch.setattr(U.G, "raw_for", lambda *a, **k: Path("unused.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (None, None))
    assert U.kept_for(p, "p4c_bulk", "m1", "tools")["call"] == "missing"
    monkeypatch.setattr(U.G, "read_raw", lambda path: ("   ", {}))
    assert U.kept_for(p, "p4c_bulk", "m1", "tools")["call"] == "blank"
